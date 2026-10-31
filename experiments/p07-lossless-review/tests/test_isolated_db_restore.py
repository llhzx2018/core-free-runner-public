"""R4 Docker-memory SQL restore: synthetic-only tests, never production backup."""
from __future__ import annotations

import gzip
import io
import json
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import isolated_db_restore as iso
import server_migration_pull as pull

SQL = "CREATE TABLE apple (id INT NOT NULL PRIMARY KEY, title VARCHAR(50));\nINSERT INTO apple VALUES (1,'synthetic');\nCREATE TABLE banana (id INT NOT NULL PRIMARY KEY);\n"


class R4IsolationContractTests(unittest.TestCase):
    def test_confirmation_required_before_access_to_backups_or_docker(self):
        with mock.patch.object(iso.private_recovery_gate, "evaluate") as private, \
             mock.patch.object(iso, "_docker_ready") as backend:
            v = iso.rehearse(Path("/secret/a"), Path("/secret/b"), "example.test", "WRONG")
        private.assert_not_called()
        backend.assert_not_called()
        self.assertEqual(v["status"], "BLOCKED")
        self.assertFalse(v["cutover_allowed"])

    def test_invalid_backups_cannot_start_containers(self):
        with mock.patch.object(iso.private_recovery_gate, "evaluate",
                               return_value={"source_backup_integrity": "FAIL",
                                             "target_backup_integrity": "PASS",
                                                 "status": "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
                                                 "dynamic_unsafe": 0}), \
             mock.patch.object(iso, "_docker_ready") as backend:
            v = iso.rehearse(Path("/a"), Path("/b"), "example.test", "ISOLATED_RESTORE_ONLY")
        backend.assert_not_called()
        self.assertEqual(v["reason"], "BOTH_PRIVATE_BACKUPS_MUST_VERIFY_FIRST")

    def test_backend_unavailable_reports_fixed_block_not_migration_pass(self):
        with mock.patch.object(iso.private_recovery_gate, "evaluate",
                               return_value={"source_backup_integrity": "PASS",
                                             "target_backup_integrity": "PASS",
                                                 "status": "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
                                                 "dynamic_unsafe": 0}), \
             mock.patch.object(iso, "_docker_ready",
                               side_effect=iso.Blocked("ISOLATED_CONTAINER_RUNTIME_NOT_INSTALLED")):
            v = iso.rehearse(Path("/a"), Path("/b"), "example.test", "ISOLATED_RESTORE_ONLY")
        self.assertFalse(v["actual_source_restore_verified"])
        self.assertFalse(v["migration_resume_allowed"])
        self.assertFalse(v["production_database_writes_performed"])
        self.assertEqual(v["reason"], "ISOLATED_CONTAINER_RUNTIME_NOT_INSTALLED")
        self.assertNotIn("/a", json.dumps(v))

    def test_a_verified_import_is_not_a_cutover_authorization(self):
        with tempfile.TemporaryDirectory() as d:
            a = Path(d) / "a.sql.gz"
            b = Path(d) / "b.sql.gz"
            for path in (a, b):
                with gzip.open(path, "wt") as f:
                    f.write(SQL)
            with mock.patch.object(iso.private_recovery_gate, "evaluate",
                                   return_value={"source_backup_integrity": "PASS",
                                                 "target_backup_integrity": "PASS",
                                                 "status": "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
                                                 "dynamic_unsafe": 0}), \
                 mock.patch.object(iso.private_recovery_gate, "_input_package",
                                   side_effect=[({}, a), ({}, b)]), \
                 mock.patch.object(iso, "_docker_ready"), \
                 mock.patch.object(iso, "_restore_one", side_effect=[2, 2]) as restore:
                result = iso.rehearse(Path("/private/A"), Path("/private/B"),
                                      "example.test", "ISOLATED_RESTORE_ONLY")
        self.assertEqual(restore.call_count, 2)
        self.assertTrue(result["actual_source_restore_verified"])
        self.assertTrue(result["actual_target_restore_verified"])
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["cross_engine_business_semantics_verified"])
        self.assertFalse(result["conflict_decisions_verified"])
        self.assertFalse(result["dynamic_sql_guards_approved"])
        self.assertFalse(result["production_database_writes_performed"])

    def test_container_command_has_no_network_or_host_mount_and_must_cleanup(self):
        with mock.patch.object(iso, "_credentials_and_name",
                               return_value=("vfops-r4-synthetic", "synthetic-temp-only")), \
             mock.patch.object(iso, "_docker",
                               return_value=mock.Mock(returncode=0, stdout=b"container")) as docker, \
             mock.patch.object(iso, "_wait_ready"), \
             mock.patch.object(iso, "_query_count", side_effect=[1, 2]), \
             mock.patch.object(iso, "_stream_sql"):
            self.assertEqual(iso._restore_one_sealed(Path("/not-read"), 2), 2)
        args = docker.call_args_list[0].args
        self.assertIn("--network", args)
        self.assertIn("none", args)
        self.assertIn("--read-only", args)
        self.assertIn("--cap-drop", args)
        self.assertIn("ALL", args)
        self.assertIn("--pull", args)
        self.assertIn("never", args)
        self.assertIn("--user", args)
        self.assertIn("999:999", args)
        self.assertNotIn("--volume", args)
        self.assertNotIn("-v", args)
        self.assertNotIn("--publish", args)
        self.assertNotIn("-p", args)
        self.assertIn("--skip-networking", args)
        self.assertEqual(docker.call_args_list[-1].args[:4],
                         ("rm", "--force", "--volumes", "vfops-r4-synthetic"))

    def test_wrong_table_count_refuses_and_removes_ephemeral_container(self):
        with mock.patch.object(iso, "_docker", return_value=mock.Mock(returncode=0, stdout=b"x")) as docker, \
             mock.patch.object(iso, "_wait_ready"), \
             mock.patch.object(iso, "_query_count", side_effect=[1, 1]), \
             mock.patch.object(iso, "_stream_sql"):
            with self.assertRaisesRegex(iso.Blocked, "TABLE_COUNT"):
                iso._restore_one_sealed(Path("/synthetic"), 2)
        self.assertEqual(docker.call_args_list[-1].args[0], "rm")

    def test_cli_denied_restore_is_exit_13_and_no_migration_state(self):
        with mock.patch.object(pull.isolated_db_restore, "rehearse",
                               return_value=iso._report("NO_DOCKER")), \
             mock.patch.object(pull, "load_state") as load, \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(sys, "argv", [
                 "server_migration_pull.py", "isolated-restore",
                 "--source-package", "/synthetic/a",
                 "--target-package", "/synthetic/b",
                 "--site", "example.test", "--confirm", "ISOLATED_RESTORE_ONLY"]):
            out = io.StringIO()
            with redirect_stdout(out):
                exitcode = pull.main()
        self.assertEqual(exitcode, 13)
        self.assertEqual(json.loads(out.getvalue())["status"], "BLOCKED")
        load.assert_not_called()
        save.assert_not_called()


@unittest.skipUnless(os.environ.get("P07_R4_DOCKER_INTEGRATION") == "1",
                     "real ephemeral MariaDB integration enabled only in public Runner")
class DockerRealMariaDBIntegrationTests(unittest.TestCase):
    def test_actual_native_sql_import_and_independent_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.sql.gz"
            with gzip.open(path, "wt", encoding="utf-8") as f:
                f.write(SQL)
            iso._docker_ready()
            self.assertEqual(iso._restore_one(path, 2), 2)
            self.assertEqual(iso._restore_one(path, 2), 2)

    def test_sql_import_error_fail_closed_with_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.sql.gz"
            with gzip.open(path, "wt", encoding="utf-8") as f:
                f.write("CREATE TABLE apple (id INT); INVALID_SYNTHETIC_STATEMENT;\n")
            with self.assertRaisesRegex(iso.Blocked, "SQL_IMPORT_FAILED"):
                iso._restore_one(path, 1)


if __name__ == "__main__":
    unittest.main()
