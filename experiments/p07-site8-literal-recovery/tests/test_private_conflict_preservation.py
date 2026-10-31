"""Synthetic only: no actual customer data, DB import, production file or SSH."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import private_conflict_preservation as mod


def cell(typ, value):
    return {"type": typ, "value": value}


def entry(i, value):
    return {"pk": [cell("INT", str(i))], "cells": {
        "id": cell("INT", str(i)), "payload": cell("TEXT", value)}}


def sample():
    source = [entry(i, "equal") for i in range(1, 1005)]
    target = deepcopy(source)
    for i in range(1005, 1011):
        source.append(entry(i, "source private original "+str(i)))
        target.append(entry(i, "target private original "+str(i)))
    source.extend(entry(i, "source-only "+str(i)) for i in range(1011, 1014))
    target.extend(entry(i, "target-only "+str(i)) for i in range(1014, 1019))
    counts = {"identical": 1004, "source_only": 3,
              "target_only": 5, "different": 6}
    return source, target, counts


class DualOriginalPreservationTests(unittest.TestCase):
    def test_site8_category_counts_preserve_both_conflicting_versions(self):
        src, tgt, expected = sample()
        old_src, old_tgt = deepcopy(src), deepcopy(tgt)
        b = mod.compile_bundle(src, tgt, expected, ["id"])
        self.assertEqual(b["counts"], expected)
        self.assertEqual(b["unresolved_conflict_count"], 6)
        self.assertEqual(len(b["source_only_originals"]), 3)
        self.assertEqual(len(b["target_only_originals"]), 5)
        self.assertEqual(len(b["conflicting_dual_originals"]), 6)
        for pair in b["conflicting_dual_originals"]:
            self.assertEqual(pair["source_original"]["pk"],
                             pair["target_original"]["pk"])
            self.assertNotEqual(pair["source_original"]["cells"]["payload"],
                                pair["target_original"]["cells"]["payload"])
            self.assertEqual(pair["resolution"], "UNRESOLVED_KEEP_BOTH")
        self.assertEqual(src, old_src)
        self.assertEqual(tgt, old_tgt)
        self.assertTrue(mod.compare_to_inputs(b, src, tgt, expected, ["id"]))
        for key in ("actual_original_sql_restores_verified",
                    "snapshot_time_consistency_verified",
                    "operator_conflict_policy_verified",
                    "data_writes_allowed", "migration_resume_allowed",
                    "cutover_allowed"):
            self.assertIs(b[key], False, key)
        self.assertEqual(b["verification"], "NOT_A_PASS_GATE")

    def test_output_is_order_independent_and_binds_full_snapshot(self):
        src, tgt, counts = sample()
        a = mod.compile_bundle(src, tgt, counts, ["id"])
        b = mod.compile_bundle(list(reversed(src)), list(reversed(tgt)),
                               counts, ["id"])
        self.assertEqual(a, b)
        src[0]["cells"]["payload"] = cell("TEXT", "changed-identical-row")
        self.assertFalse(mod.compare_to_inputs(a, src, tgt, counts, ["id"]))
        with self.assertRaises(mod.PreservationBlocked):
            mod.compile_bundle(src, tgt, counts, ["id"])

    def test_reject_counts_duplicates_pk_spoofing_and_column_type_drift(self):
        src, tgt, counts = sample()
        attacks = []
        duplicate = deepcopy(src)
        duplicate.append(deepcopy(duplicate[0]))
        attacks.append((duplicate, tgt, counts))
        spoof = deepcopy(src)
        spoof[0]["cells"]["id"] = cell("INT", "999999")
        attacks.append((spoof, tgt, counts))
        drift = deepcopy(tgt)
        drift[0]["cells"]["payload"] = cell("BINARY", "00ff")
        attacks.append((src, drift, counts))
        wrong = dict(counts, different=5)
        attacks.append((src, tgt, wrong))
        for a, b, c in attacks:
            with self.subTest(index=len(a), counts=c):
                with self.assertRaises(mod.PreservationBlocked):
                    mod.compile_bundle(a, b, c, ["id"])

    def test_private_disk_artifact_exclusive_permissions_and_readback(self):
        src, tgt, expected = sample()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.chmod(root, 0o700)
            dest = root / "conflicts"
            b = mod.compile_bundle(src, tgt, expected, ["id"])
            report = mod.save_private(b, dest, source_rows=src,
                                      target_rows=tgt, expected=expected,
                                      pk_columns=["id"])
            self.assertEqual(report["status"], "PRIVATE_PLAINTEXT_ARTIFACT_WRITTEN")
            self.assertFalse(report["at_rest_encryption"])
            self.assertFalse(report["cutover_allowed"])
            self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o700)
            for file in dest.iterdir():
                self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
            loaded = json.loads((dest / "originals.json").read_text())
            self.assertEqual(loaded["conflicting_dual_originals"],
                             b["conflicting_dual_originals"])
            result = mod.verify_private(dest)
            self.assertTrue(result["artifact_bytes_verified"])
            self.assertFalse(result["original_sql_restore_verified"])
            self.assertEqual(result["verification"], "NOT_A_PASS_GATE")
            with self.assertRaises(mod.PreservationBlocked):
                mod.save_private(b, dest, source_rows=src,
                                 target_rows=tgt, expected=expected,
                                 pk_columns=["id"])
            self.assertTrue(mod.verify_private(dest)["artifact_bytes_verified"])

    def test_modified_bundle_cannot_be_written_without_input_binding(self):
        src, tgt, expected = sample()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.chmod(root, 0o700)
            b = mod.compile_bundle(src, tgt, expected, ["id"])
            b["conflicting_dual_originals"][0]["target_original"]["cells"]["payload"] = cell("TEXT", "forged")
            with self.assertRaisesRegex(mod.PreservationBlocked,
                                        "PRESERVATION_INPUT_BINDING_UNPROVEN"):
                mod.save_private(b, root / "artifact", source_rows=src,
                                 target_rows=tgt, expected=expected, pk_columns=["id"])
            self.assertFalse((root / "artifact").exists())

    def test_post_write_byte_tamper_is_detected_without_echoing_content(self):
        src, tgt, expected = sample()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.chmod(root, 0o700)
            dest = root / "artifact"
            b = mod.compile_bundle(src, tgt, expected, ["id"])
            mod.save_private(b, dest, source_rows=src, target_rows=tgt,
                             expected=expected, pk_columns=["id"])
            p = dest / "originals.json"
            before = p.read_bytes()
            p.write_bytes(before + b"UNTRUSTED_SYNTHETIC_SECRET")
            result = mod.verify_private(dest)
            self.assertFalse(result["artifact_bytes_verified"])
            self.assertNotIn("UNTRUSTED_SYNTHETIC_SECRET", json.dumps(result))

    def test_unsafe_parent_symlink_and_wrong_permissions_fail_before_write(self):
        src, tgt, expected = sample()
        b = mod.compile_bundle(src, tgt, expected, ["id"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.chmod(root, 0o700)
            bad = root / "bad"
            bad.mkdir(mode=0o755)
            link = root / "link"
            link.symlink_to(bad, target_is_directory=True)
            for path in (bad / "out", link / "out"):
                with self.subTest(path=path.name):
                    with self.assertRaises(mod.PreservationBlocked):
                        mod.save_private(b, path, source_rows=src,
                                         target_rows=tgt, expected=expected,
                                         pk_columns=["id"])
            self.assertFalse((bad / "out").exists())

    def test_conflict_policy_is_never_implied_even_if_no_conflicts(self):
        src, tgt, expected = sample()
        tgt = deepcopy(src)
        counts = {"identical": len(src), "source_only": 0,
                  "target_only": 0, "different": 0}
        result = mod.compile_bundle(src, tgt, counts, ["id"])
        self.assertEqual(result["unresolved_conflict_count"], 0)
        self.assertFalse(result["migration_resume_allowed"])
        self.assertFalse(result["actual_original_sql_restores_verified"])


if __name__ == "__main__":
    unittest.main()
