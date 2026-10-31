"""Fail-closed P07 preparation retry protecting existing target business data.

Synthetic only. No real database, VPS or production credential involved.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
import server_migration as engine
import server_migration_pull as pull


class ResumeDataProtectionTests(unittest.TestCase):
    def test_prior_sql_guard_blocks_before_status_change_or_connection(self):
        state = {
            "schema": pull.SCHEMA,
            "status": "PREPARE_FAILED",
            "migration_id": "synthetic",
            "last_sql_guard_failure": {
                "reason": "CONDITIONAL_DDL", "flow": "SQL_GUARD_FLOW_V1_UNAVAILABLE",
            },
        }
        before = json.dumps(state, sort_keys=True)
        with (
            mock.patch.object(pull,"load_state",return_value=state),
            mock.patch.object(pull,"save_state") as save,
            mock.patch.object(pull,"cloudpanel_database_server_ready_local") as server,
            mock.patch.object(pull,"require_mariadb_target") as engine_guard,
            mock.patch.object(pull,"refresh_migration_assets_from_source") as refresh,
        ):
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "PREPARE_RESUME_SQL_GUARD_AND_RECOVERY_PROOF_REQUIRED",
            ):
                pull.resume_prepare_migration("synthetic")
            save.assert_not_called()
            server.assert_not_called()
            engine_guard.assert_not_called()
            refresh.assert_not_called()
        self.assertEqual(before,json.dumps(state,sort_keys=True))

    def test_legacy_missing_sql_guard_does_not_resume_partial_staged_migration(self):
        state = {
            "schema": pull.SCHEMA,
            "status": "PREPARE_FAILED",
            "migration_id": "synthetic-old-migration",
            "last_sql_guard_failure": None,
            "cutover_prohibited": False,
            "sites": [
                {"domain": f"site{i}.example.test",
                 "stage_status": "PULLED_STAGED" if i <= 7 else "PENDING"}
                for i in range(1, 18)
            ],
        }
        before = json.dumps(state, sort_keys=True)
        with (
            mock.patch.object(pull, "load_state", return_value=state),
            mock.patch.object(pull, "save_state") as save,
            mock.patch.object(pull, "cloudpanel_database_server_ready_local") as server,
            mock.patch.object(pull, "require_mariadb_target") as guard,
            mock.patch.object(pull, "refresh_migration_assets_from_source") as refresh,
            mock.patch.object(pull, "source_probe") as remote,
            mock.patch.object(pull, "create_target_site") as create,
            mock.patch.object(pull, "sync_site_databases") as import_db,
        ):
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "PREPARE_RESUME_PARTIAL_STATE_RECOVERY_PROOF_REQUIRED",
            ):
                pull.resume_prepare_migration("synthetic-old-migration")
            for action in (save, server, guard, refresh, remote, create, import_db):
                action.assert_not_called()
        self.assertEqual(before, json.dumps(state, sort_keys=True))

    def test_failed_parent_status_does_not_misreport_cutover_unblocked(self):
        state = {
            "schema": pull.SCHEMA,
            "status": "PREPARE_FAILED",
            "migration_id": "synthetic-old-migration",
            "cutover_prohibited": False,
            "last_sql_guard_failure": None,
            "sites": [
                {"domain": "example.test", "stage_status": "PULLED_STAGED"},
                {"domain": "later.example.test", "stage_status": "PENDING"},
            ],
        }
        before = json.dumps(state, sort_keys=True)
        result = pull.summary(state)
        self.assertIs(result["cutover_prohibited"], True)
        self.assertEqual(
            result["prepare_failure_provenance"],
            "MISSING_PARTIAL_STATE_RECOVERY_REQUIRED",
        )
        self.assertFalse(result["existing_target_overwrite_allowed"])
        self.assertFalse(result["source_delete_allowed"])
        self.assertEqual(before, json.dumps(state, sort_keys=True))

    def test_cutover_is_blocked_by_failed_stage_without_production_calls(self):
        state = {
            "schema": pull.SCHEMA,
            "status": "PREPARE_FAILED",
            "migration_id": "synthetic-old-migration",
            "cutover_prohibited": False,
            "sites": [{"domain": "example.test", "stage_status": "PENDING"}],
        }
        with (
            mock.patch.object(pull, "load_state", return_value=state),
            mock.patch.object(pull, "require_mariadb_target") as engine,
            mock.patch.object(pull, "save_state") as save,
            mock.patch.object(pull, "freeze_old_server") as freeze,
        ):
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "not ready for final synchronization",
            ):
                pull.cutover_migration(
                    "synthetic-old-migration", "CUTOVER_PULL:synthetic-old-migration"
                )
            engine.assert_not_called()
            save.assert_not_called()
            freeze.assert_not_called()

    def test_owned_database_marker_never_allows_cleanup_or_import(self):
        with tempfile.TemporaryDirectory() as root:
            basedir=Path(root)
            site=basedir/"home"/"owner"/"htdocs"/"synthetic.example"
            site.mkdir(parents=True)
            dump=basedir/"source.sql.gz"
            dump.write_bytes(b"synthetic-no-private-SQL")
            # Derive marker only under isolated, patched state root.
            with mock.patch.object(engine,"STATE_ROOT",basedir/"state"):
                marker=engine.target_db_marker(
                    "synthetic","synthetic.example","synthetic_db",1
                )
                engine.atomic_private_json(marker,{
                    "domain":"synthetic.example",
                    "database":"synthetic_db",
                    "username":"owner","password":"secret-only-local",
                    "created_by_migration":"synthetic",
                })
                protected=marker.read_bytes()
                with (
                    mock.patch.object(engine.site_lifecycle,"cleanup_database") as delete,
                    mock.patch.object(engine.cloudpanel,"add_database") as create,
                    mock.patch.object(engine.cloudpanel,"import_database") as import_sql,
                    mock.patch.object(engine.app_config,"rewrite_application_database_config") as config,
                ):
                    with self.assertRaisesRegex(
                        engine.ServerMigrationError,
                        "TARGET_DATABASE_HAS_PRIOR_MIGRATION_MARKER_RECOVERY_REQUIRED",
                    ):
                        engine.target_create_database_local(
                            "synthetic","synthetic.example",site,"synthetic_db",1,dump
                        )
                    delete.assert_not_called()
                    create.assert_not_called()
                    import_sql.assert_not_called()
                    config.assert_not_called()
                self.assertEqual(marker.read_bytes(),protected)
                self.assertTrue(dump.is_file())

    def test_tampered_marker_blocks_before_any_database_operation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            site=root/"site"
            site.mkdir()
            dump=root/"dump.sql.gz"
            dump.write_bytes(b"fake")
            with mock.patch.object(engine,"STATE_ROOT",root/"state"):
                marker=engine.target_db_marker("synthetic","synthetic.example","synthetic_db",1)
                marker.parent.mkdir(parents=True,exist_ok=True)
                marker.write_text('{"created_by_migration":"OTHER_MIGRATION"}')
                with (
                    mock.patch.object(engine.site_lifecycle,"cleanup_database") as delete,
                    mock.patch.object(engine.cloudpanel,"add_database") as create,
                    mock.patch.object(engine.cloudpanel,"import_database") as import_sql,
                ):
                    with self.assertRaisesRegex(
                        engine.ServerMigrationError,
                        "ownership is unverified",
                    ):
                        engine.target_create_database_local(
                            "synthetic","synthetic.example",site,"synthetic_db",1,dump
                        )
                    delete.assert_not_called()
                    create.assert_not_called()
                    import_sql.assert_not_called()


if __name__=="__main__":
    unittest.main()
