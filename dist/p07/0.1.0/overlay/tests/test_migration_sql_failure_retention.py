"""Private SQL failure retention and fail-closed 18-site resume regression."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import migration_sql_failure_retention as retention
import diagnostics


class SqlRetentionTests(unittest.TestCase):
    def test_private_failed_import_receipt_atomic_no_rewrite(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            os.chmod(root, 0o700)
            paths = [root / f"{i}.sql.gz" for i in ("source", "import", "target")]
            for i, p in enumerate(paths):
                p.write_bytes(b"private_sql_bytes_" + bytes([48+i]))
                os.chmod(p, 0o644)
            result = retention.retain_failed_import(
                migration_id="pull-20261106T065804Z-1aef6d0e",
                domain="ilovem3u8.kewaro.com", database="kewaro-ilovem3u8",
                phase="prepare", source_dump=paths[0], import_dump=paths[1],
                target_dump=paths[2], reason="CONDITIONAL_DDL",
            )
            journal = root / result["receipt"]
            evidence = json.loads(journal.read_text())
            self.assertEqual(result["status"], "RETAINED_NOT_RECOVERED")
            self.assertFalse(result["db_reimport_allowed"])
            self.assertFalse(result["cutover_allowed"])
            self.assertEqual(evidence["files"]["source"]["status"], "RETAINED")
            self.assertEqual(evidence["files"]["target"]["status"], "RETAINED")
            self.assertEqual(stat.S_IMODE(journal.stat().st_mode), 0o600)
            for path in paths:
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertNotIn("private_sql_bytes", json.dumps(evidence))
            self.assertNotIn("sha256", json.dumps(result))
            with self.assertRaisesRegex(retention.SqlFailureEvidenceBlocked,
                                        "SQL_EVIDENCE_RECEIPT_ALREADY_EXISTS"):
                retention.retain_failed_import(
                    migration_id="pull-20261106T065804Z-1aef6d0e",
                    domain="ilovem3u8.kewaro.com", database="kewaro-ilovem3u8",
                    phase="prepare", source_dump=paths[0], import_dump=paths[1],
                    target_dump=paths[2], reason="CONDITIONAL_DDL",
                )

    def test_symlink_rejected_without_following(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            os.chmod(root, 0o700)
            real = root / "actual"
            real.write_bytes(b"private-data")
            link = root / "source.sql.gz"
            link.symlink_to(real)
            imported = root / "import.sql.gz"
            imported.write_bytes(b"private-data")
            target = root / "target.sql.gz"
            target.write_bytes(b"private-data")
            with self.assertRaises(retention.SqlFailureEvidenceBlocked):
                retention.retain_failed_import(
                    migration_id="pull-test", domain="example.com", database="db",
                    phase="prepare", source_dump=link, import_dump=imported,
                    target_dump=target, reason="CONDITIONAL_DDL")
            self.assertTrue(link.is_symlink())
            self.assertEqual(real.read_bytes(), b"private-data")

    def test_nonprivate_directory_and_missing_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            os.chmod(root, 0o755)
            a,b,c = (root / "source.sql.gz",root / "import.sql.gz",root / "target.sql.gz")
            with self.assertRaisesRegex(retention.SqlFailureEvidenceBlocked,"DIRECTORY_UNSAFE"):
                retention.retain_failed_import(migration_id="pull-a",
                    domain="site.example",database="db",phase="prepare",
                    source_dump=a,import_dump=b,target_dump=c,reason="CONDITIONAL_DDL")
            os.chmod(root,0o700)
            with self.assertRaisesRegex(retention.SqlFailureEvidenceBlocked,"SOURCE_NOT_RETAINED"):
                retention.retain_failed_import(migration_id="pull-a",
                    domain="site.example",database="db",phase="prepare",
                    source_dump=a,import_dump=b,target_dump=c,reason="CONDITIONAL_DDL")

    def test_exact_sql_blocker_diagnostic_and_negative_case(self):
        error=("ERROR: MySQL verification failed [CONDITIONAL_DDL] "
               "[SQL_GUARD_FLOW_V1 probe=1 assignment=3 safe_assignment=0 "
               "prepare=3 execute=3 deallocate=3 unknown_set=0 unknown_control=0 "
               "recognized=0 outcome=UNSAFE_BRANCH]\n")
        result=diagnostics.render("server-migrate.prepare",13,error)
        self.assertIn("stage=DATABASE",result)
        self.assertIn("error_class=MIGRATION_ERROR",result)
        self.assertIn("blocker=SQL_CONDITIONAL_DDL_UNPROVEN",result)
        self.assertNotIn("UNCLASSIFIED_FAILURE",result)
        self.assertEqual(diagnostics.infer_blocker(
            "ERROR: unrelated [CONDITIONAL_DDL] fake\n"),"UNCLASSIFIED_FAILURE")
        self.assertEqual(diagnostics.infer_blocker(
            "ERROR: PREPARE_RESUME_SQL_GUARD_AND_RECOVERY_PROOF_REQUIRED\n"),
            "SQL_RECOVERY_PROOF_REQUIRED")

    def test_current_18_site_task_exposes_only_first_failed_db(self):
        from tests.test_server_migration_pull import pull
        names = [f"staged{i}.example.test" for i in range(7)]
        sites = [
            {"domain": value, "stage_status": "PULLED_STAGED", "mysql_databases": []}
            for value in names
        ]
        sites.append({
            "domain": "ilovem3u8.kewaro.com",
            "stage_status": "PENDING",
            "mysql_databases": ["kewaro-ilovem3u8"],
            "failed_prepare_sql_evidence": {
                "status": "RETAINED_NOT_RECOVERED",
                "source_dump_retained": True,
                "target_dump_retained": True,
                "receipt": "private-digest-filename",
                "password": "SECRET_NEVER_EXPOSE",
            },
        })
        sites += [
            {"domain": f"unmigrated{i}.example.test",
             "stage_status": "PENDING", "mysql_databases": []}
            for i in range(10)
        ]
        state = {
            "schema": pull.SCHEMA,
            "status": "PREPARE_FAILED",
            "last_sql_guard_failure": {"reason":"CONDITIONAL_DDL"},
            "sites": sites,
        }
        self.assertEqual(len(sites),18)
        with mock.patch.object(pull,"post_migration_audit",return_value={}):
            view = pull.summary(state)
        self.assertEqual(view["site_count"],18)
        self.assertEqual(view["first_failed_sql_site"],"ilovem3u8.kewaro.com")
        self.assertEqual(view["first_failed_sql_evidence"]["status"],"RETAINED_NOT_RECOVERED")
        self.assertNotIn("SECRET_NEVER_EXPOSE",json.dumps(view))
        self.assertNotIn("private-digest-filename",json.dumps(view))
        sites[7]["stage_status"]="PULLED_STAGED"
        with mock.patch.object(pull,"post_migration_audit",return_value={}):
            view = pull.summary(state)
        self.assertIsNone(view["first_failed_sql_site"])

    def test_actual_database_sync_comparison_failure_retains_and_blocks_retry(self):
        from tests.test_server_migration_pull import pull
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            root.chmod(0o700)
            (root/"mysql").mkdir(mode=0o700)
            site={"domain":"ilovem3u8.kewaro.com",
                  "site_root":str(root/"site"),
                  "mysql_databases":["kewaro-ilovem3u8"],
                  "stage_status":"PENDING"}
            state={"migration_id":"pull-20261106T065804Z-1aef6d0e",
                   "source":{},"source_runtime_frozen":False,
                   "target_runtime_activated":False,
                   "status":"PREPARING","sites":[site]}
            def transfer(_src,_remote,dest):
                Path(dest).write_bytes(b"private_source_export")
            def export(_db,dest,**_kw):
                Path(dest).write_bytes(b"private_target_export")
            fail=pull.PullMigrationError(
                "MySQL verification failed [CONDITIONAL_DDL] "
                "[SQL_GUARD_FLOW_V1 probe=1 assignment=3 safe_assignment=0 "
                "prepare=3 execute=3 deallocate=3 unknown_set=0 unknown_control=0 "
                "recognized=0 outcome=UNSAFE_BRANCH]")
            with mock.patch.object(pull,"state_dir",return_value=root),\
                 mock.patch.object(pull,"remote_staging_root",return_value="/source/temp"),\
                 mock.patch.object(pull,"source_export_database"),\
                 mock.patch.object(pull,"pull_path",side_effect=transfer),\
                 mock.patch.object(pull,"progress_note"),\
                 mock.patch.object(pull.sql_diff_probe,"require_nonempty_source_schema",return_value=42),\
                 mock.patch.object(pull.sql_diff_probe,"require_source_import_utf8_integrity",return_value=42),\
                 mock.patch.object(pull.legacy,"target_create_database_local",return_value={"application_config_mode":"SAFE"}) as imported,\
                 mock.patch.object(pull.cloudpanel,"export_database",side_effect=export),\
                 mock.patch.object(pull,"compare_database_dumps",side_effect=fail),\
                 mock.patch.object(pull,"source_remote",return_value=None):
                with self.assertRaisesRegex(pull.PullMigrationError,"CONDITIONAL_DDL"):
                    pull.sync_site_databases(state,site,phase="prepare")
                imported.assert_called_once()
            folder=root/"mysql"/"prepare"
            self.assertEqual(len(list(folder.glob("*-source.sql.gz"))),1)
            self.assertEqual(len(list(folder.glob("*-target.sql.gz"))),1)
            self.assertEqual(len(list(folder.glob("*-import.sql.gz"))),1)
            self.assertEqual(len(list(folder.glob("*-sql-failure.json"))),1)
            self.assertEqual(site["failed_prepare_sql_evidence"]["status"],
                             "RETAINED_NOT_RECOVERED")
            self.assertEqual(site["stage_status"],"PENDING")
            self.assertNotIn("mysql_verification",site)
            # A failed old checkpoint is not automatically resumable.
            blocked_state=dict(state,status="PREPARE_FAILED",
                 last_sql_guard_failure={"reason":"CONDITIONAL_DDL"})
            with mock.patch.object(pull,"load_state",return_value=blocked_state),\
                 mock.patch.object(pull,"save_state") as save:
                with self.assertRaisesRegex(pull.PullMigrationError,
                    "PREPARE_RESUME_SQL_GUARD_AND_RECOVERY_PROOF_REQUIRED"):
                    pull.resume_prepare_migration(blocked_state["migration_id"])
                save.assert_not_called()

if __name__=="__main__":
    unittest.main()
