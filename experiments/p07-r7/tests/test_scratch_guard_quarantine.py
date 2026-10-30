"""R7 strict quarantine stream: original dump never altered or auto-approved."""
from __future__ import annotations

import gzip
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import native_scratch_restore as native
import scratch_guard_quarantine as quarantine
import server_migration_pull as pull

GUARD = b"/*!50003 SET @cmd = IF(@flag,'DROP TABLE alpha','SELECT 1') */;\n"
BASE = b"CREATE TABLE alpha (id INT NOT NULL PRIMARY KEY, body TEXT);\n"
INSERT = b"INSERT INTO alpha VALUES (1,'private synthetic');\n"
SAFE = BASE + INSERT
UNSAFE = BASE + GUARD + INSERT


def sql_file(parent: Path, name: str, contents: bytes) -> Path:
    path = parent / name
    with gzip.open(path, "wb") as handle:
        handle.write(contents)
    return path


class R7QuarantineTests(unittest.TestCase):
    def test_exact_guard_is_omitted_only_from_stream_original_stays_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            a = sql_file(Path(root), "a.sql.gz", UNSAFE)
            data = a.read_bytes()
            p = quarantine.plan(a)
            self.assertEqual(p["removed"], 1)
            out = b"".join(quarantine.filtered_bytes(a, p))
            self.assertEqual(out, SAFE)
            self.assertEqual(a.read_bytes(), data)
            self.assertNotIn("private", json.dumps({"removed": p["removed"]}))

    def test_no_unsafe_guards_produces_identical_stream(self):
        with tempfile.TemporaryDirectory() as root:
            a = sql_file(Path(root), "a.sql.gz", SAFE)
            p = quarantine.plan(a)
            self.assertEqual(p["removed"], 0)
            self.assertEqual(b"".join(quarantine.filtered_bytes(a, p)), SAFE)

    def test_unverified_guard_multistatement_is_not_selectively_edited(self):
        with tempfile.TemporaryDirectory() as root:
            contents = BASE + b"/*!50003 SET @cmd = IF(@a,'DROP TABLE alpha','SELECT 1') */; DROP TABLE alpha;\n" + INSERT
            a = sql_file(Path(root), "a.sql.gz", contents)
            with self.assertRaises(quarantine.QuarantineBlocked):
                quarantine.plan(a)

    def test_quarantine_does_not_erase_risky_looking_row_literals(self):
        with tempfile.TemporaryDirectory() as root:
            payload = BASE + b"INSERT INTO alpha VALUES (1,'/*!50003 SET @danger=IF(1,2,3) */;');\n"
            a = sql_file(Path(root), "a.sql.gz", payload)
            with self.assertRaises(quarantine.QuarantineBlocked):
                quarantine.plan(a)

    def test_digest_change_after_plan_invalidates_transient_stream(self):
        with tempfile.TemporaryDirectory() as root:
            a = sql_file(Path(root), "a.sql.gz", UNSAFE)
            p = quarantine.plan(a)
            sql_file(Path(root), "a.sql.gz", UNSAFE + b"--changed\n")
            with self.assertRaisesRegex(quarantine.QuarantineBlocked, "SOURCE_CHANGED"):
                b"".join(quarantine.filtered_bytes(a, p))

    def test_unsafe_guard_evidence_is_not_original_restore(self):
        with tempfile.TemporaryDirectory() as root:
            a = sql_file(Path(root), "a.sql.gz", UNSAFE)
            b = sql_file(Path(root), "b.sql.gz", SAFE)
            evidence = {
                "status": "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
                "source_backup_integrity": "PASS", "target_backup_integrity": "PASS",
                "dynamic_unsafe": 1,
            }
            with mock.patch.object(native.private_recovery_gate, "evaluate",
                                   return_value=evidence), \
                 mock.patch.object(native.private_recovery_gate, "_input_package",
                                   side_effect=[({}, a), ({}, b)]), \
                 mock.patch.object(native, "_binaries", return_value={}), \
                 mock.patch.object(native, "restore_one", side_effect=[1, 1]) as imp:
                report = native.rehearse_quarantined(Path("/a"), Path("/b"),
                                                      "example.test", "QUARANTINED_SCRATCH_ONLY")
        self.assertTrue(report["scratch_imports_completed"])
        self.assertEqual(report["source_guarded_set_lines_omitted"], 1)
        self.assertEqual(report["target_guarded_set_lines_omitted"], 0)
        self.assertFalse(report["actual_source_restore_verified"])
        self.assertFalse(report["actual_target_restore_verified"])
        self.assertFalse(report["migration_resume_allowed"])
        self.assertFalse(report["cutover_allowed"])
        self.assertEqual(imp.call_count, 2)
        self.assertEqual(imp.call_args.kwargs["quarantine_plan"]["removed"], 0)

    def test_wrong_confirmation_never_reads_private_backup(self):
        with mock.patch.object(native.private_recovery_gate, "evaluate") as ev, \
             mock.patch.object(native, "_binaries") as bins:
            report = native.rehearse_quarantined(Path("/a"), Path("/b"),
                                                   "example.test", "WRONG")
        self.assertFalse(report["cutover_allowed"])
        ev.assert_not_called()
        bins.assert_not_called()

    def test_child_import_not_started_when_classifier_fails(self):
        with tempfile.TemporaryDirectory() as root:
            a = sql_file(Path(root), "a.sql.gz", UNSAFE)
            b = sql_file(Path(root), "b.sql.gz", UNSAFE)
            evidence = {
                "status": "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
                "source_backup_integrity": "PASS", "target_backup_integrity": "PASS",
                "dynamic_unsafe": 3,
            }
            with mock.patch.object(native.private_recovery_gate, "evaluate", return_value=evidence), \
                 mock.patch.object(native.private_recovery_gate, "_input_package",
                                   side_effect=[({}, a), ({}, b)]), \
                 mock.patch.object(native, "restore_one") as imp:
                report = native.rehearse_quarantined(Path("/a"), Path("/b"),
                                               "example.test", "QUARANTINED_SCRATCH_ONLY")
            self.assertEqual(report["status"], "BLOCKED")
            imp.assert_not_called()

    def test_migration_cli_only_reports_scratch_approval(self):
        e = native._report("NONE")
        e.update({"scratch_imports_completed": True,
                  "actual_source_restore_verified": False,
                  "actual_target_restore_verified": False})
        with mock.patch.object(pull.native_scratch_restore, "rehearse_quarantined",
                               return_value=e), \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(pull, "source_probe") as probe, \
             mock.patch.object(sys, "argv",
                   ["server_migration_pull.py", "scratch-restore-quarantined",
                    "--source-package", "/private/a",
                    "--target-package", "/private/b",
                    "--site", "example.test", "--confirm", "QUARANTINED_SCRATCH_ONLY"]):
            out = io.StringIO()
            with redirect_stdout(out):
                code = pull.main()
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out.getvalue())["cutover_allowed"])
        save.assert_not_called()
        probe.assert_not_called()


@unittest.skipUnless(os.environ.get("P07_R7_NATIVE_QUARANTINE_ENGINE") == "1",
                     "real scratch engine is only enabled on synthetic public Runner")
class R7ScratchNativeIntegration(unittest.TestCase):
    def test_original_guarded_set_is_omitted_only_in_scratch_import(self):
        with tempfile.TemporaryDirectory() as root:
            a = sql_file(Path(root), "a.sql.gz", UNSAFE)
            p = quarantine.plan(a)
            self.assertEqual(p["removed"], 1)
            self.assertEqual(native.restore_one(a, 1, quarantine_plan=p), 1)


if __name__ == "__main__":
    unittest.main()
