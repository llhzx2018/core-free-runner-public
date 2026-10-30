"""Synthetic-only contract and native database scratch engine tests."""
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
import server_migration_pull as pull

SQL = (
    "CREATE TABLE alpha (id INT NOT NULL PRIMARY KEY, body TEXT);\n"
    "INSERT INTO alpha VALUES (1,'synthetic');\n"
    "CREATE TABLE beta (id INT NOT NULL PRIMARY KEY);\n"
)


def sql_file(root: Path, sql: str = SQL) -> Path:
    path = root / "private-synthetic.sql.gz"
    with gzip.open(path, "wt", encoding="utf-8") as out:
        out.write(sql)
    return path


class NativeRestoreContractTests(unittest.TestCase):
    def test_denied_confirmation_is_before_reading_backups_or_native_engine(self):
        with mock.patch.object(native.private_recovery_gate, "evaluate") as gate, \
             mock.patch.object(native, "_binaries") as engines:
            result = native.rehearse(Path("/private/a"), Path("/private/b"),
                                      "example.test", "WRONG")
        gate.assert_not_called()
        engines.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["cutover_allowed"])

    def test_no_engine_must_not_open_scratch(self):
        with mock.patch.object(native.private_recovery_gate, "evaluate",
                               return_value={"source_backup_integrity": "PASS",
                                             "target_backup_integrity": "PASS",
                                                 "status": "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
                                                 "dynamic_unsafe": 0}), \
             mock.patch.object(native, "_binaries",
                               side_effect=native.Blocked("NATIVE_MARIADB_BINARIES_UNAVAILABLE")), \
             mock.patch.object(native.tempfile, "TemporaryDirectory") as temp:
            r = native.rehearse(Path("/a"), Path("/b"), "example.test",
                                "NATIVE_RESTORE_SCRATCH_ONLY")
        self.assertEqual(r["reason"], "NATIVE_MARIADB_BINARIES_UNAVAILABLE")
        temp.assert_not_called()

    def test_no_root_user_or_unknown_unprivileged_identity(self):
        with mock.patch.object(native.os, "geteuid", return_value=0), \
             mock.patch.object(native.pwd, "getpwnam",
                               return_value=mock.Mock(pw_uid=0, pw_gid=0)):
            with self.assertRaisesRegex(native.Blocked, "UNPRIVILEGED"):
                native._identity()

    def test_native_restore_reports_imports_only_not_data_semantics_or_cutover(self):
        with tempfile.TemporaryDirectory() as d:
            path = sql_file(Path(d))
            with mock.patch.object(native.private_recovery_gate, "evaluate",
                                   return_value={"source_backup_integrity": "PASS",
                                                 "target_backup_integrity": "PASS",
                                                 "status": "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
                                                 "dynamic_unsafe": 0}), \
                 mock.patch.object(native.private_recovery_gate, "_input_package",
                                   side_effect=[({}, path), ({}, path)]), \
                 mock.patch.object(native, "_binaries", return_value={}), \
                 mock.patch.object(native, "restore_one", side_effect=[2, 2]) as restore:
                e = native.rehearse(Path("/a"), Path("/b"), "example.test",
                                    "NATIVE_RESTORE_SCRATCH_ONLY")
        self.assertEqual(restore.call_count, 2)
        self.assertTrue(e["actual_source_restore_verified"])
        self.assertTrue(e["actual_target_restore_verified"])
        for key in ("migration_resume_allowed", "cutover_allowed",
                    "row_data_and_trigger_semantics_verified",
                    "cross_engine_business_semantics_verified",
                    "unsafe_dynamic_sql_approved",
                    "production_database_writes_performed"):
            self.assertFalse(e[key])

    def test_source_import_failure_never_starts_target_import(self):
        with tempfile.TemporaryDirectory() as d:
            sql = sql_file(Path(d))
            with mock.patch.object(native.private_recovery_gate, "evaluate",
                                   return_value={"source_backup_integrity": "PASS",
                                                 "target_backup_integrity": "PASS",
                                                 "status": "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
                                                 "dynamic_unsafe": 0}), \
                 mock.patch.object(native.private_recovery_gate, "_input_package",
                                   side_effect=[({}, sql), ({}, sql)]), \
                 mock.patch.object(native, "_binaries", return_value={}), \
                 mock.patch.object(native, "restore_one",
                                   side_effect=native.Blocked("NATIVE_SQL_IMPORT_FAILED")) as run:
                e = native.rehearse(Path("/a"), Path("/b"), "example.test",
                                    "NATIVE_RESTORE_SCRATCH_ONLY")
        self.assertEqual(e["reason"], "NATIVE_SQL_IMPORT_FAILED")
        self.assertEqual(run.call_count, 1)
        self.assertFalse(e["actual_source_restore_verified"])
        self.assertFalse(e["actual_target_restore_verified"])

    def test_unrecognized_client_output_cannot_be_pass(self):
        with mock.patch.object(native, "_run",
                               return_value=mock.Mock(returncode=0, stdout=b"SECRET\n")):
            result = native._client({"mariadb": "/tmp/fake"}, Path("/tmp/private.sock"),
                                    Path("/tmp"), 1001, 1001, "SELECT 1")
        self.assertEqual(result, b"SECRET\n")
        self.assertFalse(native._report("NOT_PROVEN")["cutover_allowed"])

    def test_migration_command_is_read_only_and_returns_13_on_block(self):
        with mock.patch.object(pull.native_scratch_restore, "rehearse",
                               return_value=native._report("NOT_INSTALLED")), \
             mock.patch.object(pull, "source_probe") as source, \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(sys, "argv", [
                 "server_migration_pull.py", "native-restore",
                 "--source-package", "/synthetic/a",
                 "--target-package", "/synthetic/b",
                 "--site", "example.test",
                 "--confirm", "NATIVE_RESTORE_SCRATCH_ONLY"
             ]):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                rc = pull.main()
        self.assertEqual(rc, 13)
        self.assertEqual(json.loads(buffer.getvalue())["status"], "BLOCKED")
        source.assert_not_called()
        save.assert_not_called()


@unittest.skipUnless(os.environ.get("P07_R5_NATIVE_INTEGRATION") == "1",
                     "native MariaDB installation integration only in isolated public Runner")
class NativeRestoreRealEngineTests(unittest.TestCase):
    def test_two_independent_native_mariadb_datadirs_and_sql_import(self):
        with tempfile.TemporaryDirectory() as d:
            path = sql_file(Path(d))
            self.assertEqual(native.restore_one(path, 2), 2)
            self.assertEqual(native.restore_one(path, 2), 2)

    def test_bad_sql_refuses_and_cleans_daemon_and_datadir(self):
        with tempfile.TemporaryDirectory() as d:
            path = sql_file(Path(d),
                            "CREATE TABLE alpha (id INT); INVALID_R5_SYNTHETIC_SQL;\n")
            with self.assertRaisesRegex(native.Blocked, "IMPORT_FAILED"):
                native.restore_one(path, 1)


if __name__ == "__main__":
    unittest.main()
