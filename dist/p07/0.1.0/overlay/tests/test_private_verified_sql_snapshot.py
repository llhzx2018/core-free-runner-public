"""Synthetic-only chain of custody for private SQL backups (NO real SQL)."""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import private_sql_literal_reconcile as inspect
import private_recovery_gate as gate
from tests.test_private_sql_literal_reconcile import dump, pack, SITE


class VerifiedSQLSnapshotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        os.chmod(self.root, 0o700)
        self.source, self.a = pack(self.root / "source", "verified-source", dump(True, unsafe=True))
        self.target, self.b = pack(self.root / "target", "verified-target", dump(False))
        patch = mock.patch.object(gate.package_core, "verify_package_stable",
                                  return_value={"status": "PASS"})
        patch.start()
        self.addCleanup(patch.stop)

    def test_full_private_copy_matches_original_and_wipes_temporary_path(self):
        saved = None
        original = (self.a.read_bytes(), self.b.read_bytes())
        with inspect._verified_sealed_pair(self.source, self.target, SITE) as (
                left, right, a, b, digest):
            saved = a.parent
            self.assertEqual(a.read_bytes(), original[0])
            self.assertEqual(b.read_bytes(), original[1])
            self.assertEqual(stat.S_IMODE(a.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(b.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(saved.stat().st_mode), 0o700)
            self.assertEqual(digest, (inspect._digest(a), inspect._digest(b)))
            # After a sealed proof, subsequent changes to originals cannot
            # affect the already pinned inspected input bytes.
            with gzip.open(self.a, "wt") as out:
                out.write(dump(True) + "INSERT INTO `delta` VALUES (99,'late');\n")
            self.assertEqual(a.read_bytes(), original[0])
        self.assertFalse(saved.exists())

    def test_original_sql_mutation_before_copy_fails_closed(self):
        original_copy = inspect._private_copy
        changed = {"done": False}
        def injected(path, dest):
            if not changed["done"]:
                changed["done"] = True
                with gzip.open(path, "wt") as stream:
                    stream.write(dump(True) + "INSERT INTO `delta` VALUES(99,'new');\n")
            return original_copy(path, dest)
        with mock.patch.object(inspect, "_private_copy", side_effect=injected):
            report = inspect.evaluate(self.source, self.target, SITE, 4,
                                      private_output=self.root / "no_artifact",
                                      confirm="PRESERVE_PRIVATE_SQL_LITERALS_ONLY")
        self.assertEqual(report["status"], "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE")
        self.assertFalse((self.root / "no_artifact").exists())
        self.assertFalse(report["migration_resume_allowed"])

    def test_second_package_integrity_verification_is_mandatory(self):
        counter = {"n": 0}
        def verifier(path):
            counter["n"] += 1
            return {"status": "FAIL"} if counter["n"] == 3 else {"status": "PASS"}
        with mock.patch.object(gate.package_core, "verify_package_stable",
                               side_effect=verifier):
            report = inspect.evaluate(self.source, self.target, SITE, 4)
        self.assertEqual(counter["n"], 3)
        self.assertEqual(report["status"], "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE")
        self.assertFalse(report["original_sql_restored"])

    def test_sealed_data_is_the_only_sql_opened_by_parser(self):
        visited = []
        schema_read = inspect.schema._schema_statements
        def record(path):
            visited.append(path)
            self.assertEqual(path.parent.name.startswith("vfops-private-sql-"), True)
            self.assertNotIn(path, (self.a, self.b))
            return schema_read(path)
        with mock.patch.object(inspect.schema, "_schema_statements",
                               side_effect=record):
            report = inspect.evaluate(self.source, self.target, SITE, 4)
        self.assertEqual(report["status"], "PRIVATE_SQL_LITERALS_CAPTURED_NOT_RESTORED")
        self.assertGreaterEqual(len(visited), 2)
        self.assertFalse(report["cutover_allowed"])

    def test_copy_size_limit_prevents_output_before_parser(self):
        with mock.patch.object(inspect, "_MAX_PRIVATE_SQL_BYTES", 4):
            report = inspect.evaluate(self.source, self.target, SITE, 4,
                                      private_output=self.root / "nothing",
                                      confirm="PRESERVE_PRIVATE_SQL_LITERALS_ONLY")
        self.assertEqual(report["status"], "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE")
        self.assertFalse((self.root / "nothing").exists())

    def test_private_artifact_remains_bound_to_pinned_backup_hash(self):
        bundle, src, tgt, counts, keys, proof = inspect.extract_verified(
            self.source, self.target, SITE, 4)
        self.assertEqual(proof["source_sql_sha256"], inspect._digest(self.a))
        self.assertEqual(proof["target_sql_sha256"], inspect._digest(self.b))
        self.assertEqual(bundle["verified_backup_sql_identity_digests"], proof)
        self.assertFalse(bundle["actual_original_sql_restores_verified"])
        self.assertFalse(bundle["cutover_allowed"])


if __name__ == "__main__":
    unittest.main()
