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

    def test_owned_database_marker_never_allows_cleanup_or_import(self):
        with tempfile.TemporaryDirectory() as root:
            basedir=Path(root)
            site=basedir/"home"/"owner"/"htdocs"/"synthetic.example"
            site.mkdir(parents=True)
            dump=basedir/"source.sql.gz"
            dump.write_bytes(b"synthetic-no-private-SQL")
            marker=engine.target_db_marker("synthetic","synthetic.example","synthetic_db",1)
            # The marker path is derived from STATE_ROOT, hence patch it.
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
                        "TARGET_DATABASE_OWNERSHIP_UNVERIFIED",
                    ):
                        engine.target_create_database_local(
                            "synthetic","synthetic.example",site,"synthetic_db",1,dump
                        )
                    delete.assert_not_called()
                    create.assert_not_called()
                    import_sql.assert_not_called()


if __name__=="__main__":
    unittest.main()
