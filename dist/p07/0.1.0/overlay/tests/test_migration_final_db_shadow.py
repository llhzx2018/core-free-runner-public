"""Isolated final MySQL shadow staging: the original target DB is immutable."""
from __future__ import annotations

import copy
import gzip
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_final_db_shadow as shadow
import server_migration as legacy
import server_migration_pull as pull


MID = "pull-20261101T045943Z-923729a1"
DOMAIN = "example.cloudpanel.io"
IDENTITY = "sha256:cp2"
SQL = "CREATE TABLE t (id int);\nINSERT INTO t VALUES (1);\n"


class FinalShadowStageTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name)
        patcher = mock.patch.object(legacy, "STATE_ROOT", self.root / "states")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.site_root = self.root / "site"
        self.site_root.mkdir()
        self.config = self.site_root / "wp-config.php"
        self.config.write_text(
            "define('DB_NAME', 'origdb');\n"
            "define('DB_USER', 'origuser');\n"
            "define('DB_PASSWORD', 'origpw');\n",
            encoding="utf-8",
        )
        self.original_config = self.config.read_bytes()
        self.site = {
            "domain": DOMAIN, "site_root": str(self.site_root),
            "mysql_databases": ["origdb"], "stage_status": "PULLED_STAGED"
        }
        self.state = {
            "migration_id": MID, "sites": [self.site],
            "status": "CUTOVER_RUNNING", "source_runtime_frozen": True,
            "target_runtime_activated": False, "dns_changed_by_p07": False,
            "source_delete_allowed": False, "existing_target_overwrite_allowed": False,
            "target_server_identity": IDENTITY,
        }
        old = legacy.target_db_marker(MID, DOMAIN, "origdb", 1)
        legacy.atomic_private_json(old, {
            "domain": DOMAIN, "database": "origdb",
            "username": "origuser", "password": "origpw",
            "created_by_migration": MID,
        })
        self.original_marker = old
        self.original_marker_bytes = old.read_bytes()
        self.sql = legacy.state_dir(MID) / "mysql" / "final" / "source.sql.gz"
        self.sql.parent.mkdir(parents=True)
        with gzip.open(self.sql, "wt", encoding="utf-8") as out:
            out.write(SQL)
        # A staging receipt cannot remain valid without a second real-time
        # dump read immediately before modifying the application config.
        def current_shadow_export(db, output):
            shutil.copyfile(self.sql, output)
            return output
        live_export = mock.patch.object(
            shadow.cloudpanel, "export_database", side_effect=current_shadow_export
        )
        live_export.start()
        self.addCleanup(live_export.stop)

    def run_stage(self, *, export=True, fail_import=False):
        def target_export(db, file):
            shutil.copyfile(self.sql, file)
            return file
        with mock.patch.object(shadow.cloudpanel, "add_database") as create, \
             mock.patch.object(shadow.cloudpanel, "import_database") as imp, \
             mock.patch.object(shadow.cloudpanel, "export_database",
                               side_effect=(target_export if export else OSError("test"))) as exp, \
             mock.patch.object(shadow.cloudpanel, "delete_database") as dele:
            if fail_import:
                imp.side_effect = shadow.cloudpanel.CloudPanelError("fake")
            if export:
                result = shadow.stage_frozen_source_shadow(
                    self.state, self.site, self.sql, actual_target_identity=IDENTITY)
            else:
                with self.assertRaisesRegex(shadow.ShadowBlocked, "SHADOW_IMPORT_OR_VERIFICATION_FAILED"):
                    shadow.stage_frozen_source_shadow(
                        self.state, self.site, self.sql, actual_target_identity=IDENTITY)
                result = None
            dele.assert_not_called()
            return result, create, imp, exp

    def test_shadow_create_failure_preserves_prior_intent_and_never_retries(self):
        # A CloudPanel error may occur after an actual CREATE. The receipt
        # must exist BEFORE the call so the next run cannot re-create the DB.
        import json
        _, shadow_name = shadow.shadow_identity(self.state, self.site)
        marker = shadow._marker(self.state, self.site, shadow_name)
        self.assertFalse(marker.exists())

        def ambiguous_create(domain, database, username, password):
            self.assertTrue(marker.is_file())
            receipt = json.loads(marker.read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "CREATE_INTENT_RESERVED")
            self.assertEqual(receipt["shadow_database"], database)
            self.assertFalse(receipt["active_app_config_unchanged"] is False)
            raise shadow.cloudpanel.CloudPanelError("synthetic ambiguous create")

        with mock.patch.object(shadow.cloudpanel, "add_database",
                               side_effect=ambiguous_create) as create, \
             mock.patch.object(shadow.cloudpanel, "import_database") as imported:
            with self.assertRaisesRegex(
                shadow.ShadowBlocked,
                "SHADOW_DATABASE_CREATE_UNCERTAIN_RETAIN_INTENT"
            ):
                shadow.stage_frozen_source_shadow(
                    self.state, self.site, self.sql,
                    actual_target_identity=IDENTITY)
            self.assertEqual(create.call_count, 1)
            imported.assert_not_called()
            self.assertEqual(json.loads(marker.read_text())["status"],
                             "CREATE_INTENT_RESERVED")
            with self.assertRaisesRegex(
                shadow.ShadowBlocked, "SHADOW_ALREADY_CREATED_REIMPORT_FORBIDDEN"
            ):
                shadow.stage_frozen_source_shadow(
                    self.state, self.site, self.sql,
                    actual_target_identity=IDENTITY)
            self.assertEqual(create.call_count, 1)
            imported.assert_not_called()
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.assertEqual(self.original_marker.read_bytes(),
                         self.original_marker_bytes)

    def test_shadow_success_transitions_from_reserved_intent(self):
        import json
        _, shadow_name = shadow.shadow_identity(self.state, self.site)
        marker = shadow._marker(self.state, self.site, shadow_name)
        states = []

        def observe_create(domain, database, username, password):
            states.append(json.loads(marker.read_text())["status"])

        with mock.patch.object(shadow.cloudpanel, "add_database",
                               side_effect=observe_create) as create, \
             mock.patch.object(shadow.cloudpanel, "import_database"), \
             mock.patch.object(shadow.verify, "sql_fingerprint",
                               return_value=("test-fingerprint", 2)), \
             mock.patch.object(pull, "compare_database_dumps",
                               return_value="MATCH"):
            staged = shadow.stage_frozen_source_shadow(
                self.state, self.site, self.sql,
                actual_target_identity=IDENTITY)
        self.assertEqual(states, ["CREATE_INTENT_RESERVED"])
        self.assertEqual(create.call_count, 1)
        self.assertEqual(staged["status"], "STAGED_VERIFIED_NOT_ACTIVATED")
        self.assertEqual(json.loads(marker.read_text())["status"],
                         "STAGED_VERIFIED_NOT_ACTIVATED")
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_original_db_owned_by_different_migration_is_preserved(self):
        """A consolidated 17-site transaction must not seek its own old DB marker."""
        real_owner = "pull-20261101T052411Z-35663c25"
        old_receipt = self.original_marker.read_bytes()
        owned_path = legacy.target_db_marker(
            real_owner, DOMAIN, "origdb", 1,
        )
        import json
        original = json.loads(old_receipt)
        original["created_by_migration"] = real_owner
        legacy.atomic_private_json(owned_path, original)
        self.original_marker.unlink()
        self.state["original_db_migration_owners"] = {DOMAIN: real_owner}
        self.assertEqual(
            shadow.original_database_owner(self.state, self.site),
            real_owner,
        )
        result, create, imported, exported = self.run_stage()
        self.assertEqual(result["status"], "STAGED_VERIFIED_NOT_ACTIVATED")
        self.assertEqual(create.call_count, 1)
        self.assertEqual(imported.call_count, 1)
        self.assertEqual(owned_path.read_bytes(), json.dumps(
            original, ensure_ascii=False, indent=2, sort_keys=True
        ).encode() + b"\n")
        self.assertFalse(self.original_marker.exists())
        switched = shadow.activate_verified_shadow(
            self.state, self.site, actual_target_identity=IDENTITY,
        )
        self.assertFalse(switched["cutover_allowed"])
        self.assertNotEqual(self.config.read_bytes(), self.original_config)
        restored = shadow.rollback_shadow_application(
            self.state, self.site, actual_target_identity=IDENTITY,
        )
        self.assertEqual(restored["status"], "APP_SWITCH_ROLLED_BACK")
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.assertFalse(self.original_marker.exists())

    def test_original_owner_map_must_cover_all_database_sites_without_fallback(self):
        foreign = "pull-20261101T052411Z-35663c25"
        bad_maps = (
            {}, {DOMAIN: "not-a-migration"},
            {DOMAIN: foreign, "forged.example.test": MID},
        )
        for mapping in bad_maps:
            with self.subTest(mapping=mapping):
                self.state["original_db_migration_owners"] = mapping
                with mock.patch.object(shadow.cloudpanel, "add_database") as create:
                    with self.assertRaises(shadow.ShadowBlocked):
                        shadow.stage_frozen_source_shadow(
                            self.state, self.site, self.sql,
                            actual_target_identity=IDENTITY,
                        )
                    create.assert_not_called()
        self.state["original_db_migration_owners"] = {DOMAIN: foreign}
        with mock.patch.object(shadow.cloudpanel, "add_database") as create:
            with self.assertRaisesRegex(
                shadow.ShadowBlocked, "SHADOW_ORIGINAL_DATABASE_UNOWNED",
            ):
                shadow.stage_frozen_source_shadow(
                    self.state, self.site, self.sql,
                    actual_target_identity=IDENTITY,
                )
            create.assert_not_called()
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_shadow_rows_modified_after_stage_are_blocked_before_any_config_switch(self):
        self.run_stage()
        original = self.config.read_bytes()
        def drifted_export(_db, output):
            with gzip.open(output, "wt", encoding="utf-8") as stream:
                stream.write("CREATE TABLE t (id int);\nINSERT INTO t VALUES (2);\n")
            return output
        with mock.patch.object(
            shadow.cloudpanel, "export_database", side_effect=drifted_export
        ), mock.patch.object(
            shadow.app_config, "rewrite_application_database_config"
        ) as rewrite:
            with self.assertRaisesRegex(
                shadow.ShadowBlocked, "SHADOW_FRESH_READBACK_CONTENT_CHANGED"
            ):
                shadow.activate_verified_shadow(
                    self.state, self.site, actual_target_identity=IDENTITY
                )
            rewrite.assert_not_called()
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(self.original_marker.read_bytes(), self.original_marker_bytes)
        _, shadow_name = shadow.shadow_identity(self.state, self.site)
        marker = shadow._marker(self.state, self.site, shadow_name)
        self.assertIn("STAGED_VERIFIED_NOT_ACTIVATED", marker.read_text())
        self.assertFalse(marker.with_suffix(".original.bak").exists())

    def test_missing_shadow_snapshot_proof_fails_closed(self):
        import json
        self.run_stage()
        _, shadow_name = shadow.shadow_identity(self.state, self.site)
        marker = shadow._marker(self.state, self.site, shadow_name)
        data = json.loads(marker.read_text())
        data.pop("target_snapshot_sha256")
        legacy.atomic_private_json(marker, data)
        with mock.patch.object(shadow.cloudpanel, "export_database") as read:
            with self.assertRaisesRegex(
                shadow.ShadowBlocked, "SHADOW_VERIFIED_RECEIPT_INVALID"
            ):
                shadow.activate_verified_shadow(
                    self.state, self.site, actual_target_identity=IDENTITY
                )
            read.assert_not_called()
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_new_shadow_is_verified_but_never_activated_or_cutover(self):
        result, create, imp, exp = self.run_stage()
        self.assertEqual(result["status"], "STAGED_VERIFIED_NOT_ACTIVATED")
        self.assertEqual(result["verification_mode"], "CANONICAL_SQL_EXACT")
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["app_config_modified"])
        self.assertTrue(result["old_database_retained"])
        self.assertNotEqual(result["shadow_database"], "origdb")
        self.assertEqual(create.call_count, 1)
        self.assertEqual(imp.call_count, 1)
        self.assertEqual(exp.call_count, 1)
        self.assertEqual(imp.call_args.args[0], result["shadow_database"])
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.assertEqual(self.original_marker.read_bytes(), self.original_marker_bytes)
        self.assertEqual(self.state["status"], "CUTOVER_RUNNING")
        marker = shadow._marker(self.state, self.site, result["shadow_database"])
        self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
        self.assertEqual(marker.parent.stat().st_mode & 0o777, 0o700)
        self.assertIn("STAGED_VERIFIED_NOT_ACTIVATED", marker.read_text())
        self.assertIn('"active_app_config_unchanged": true', marker.read_text())
        with self.assertRaisesRegex(pull.PullMigrationError, "FINAL_MYSQL_SAFE_REPLACEMENT_NOT_IMPLEMENTED"):
            pull.require_non_destructive_final_db_plan(self.state)

    def test_second_run_never_reimports_or_overwrites_shadow(self):
        self.run_stage()
        with mock.patch.object(shadow.cloudpanel, "add_database") as create, \
             mock.patch.object(shadow.cloudpanel, "import_database") as imp:
            with self.assertRaisesRegex(shadow.ShadowBlocked, "SHADOW_ALREADY_CREATED"):
                shadow.stage_frozen_source_shadow(
                    self.state, self.site, self.sql, actual_target_identity=IDENTITY)
            create.assert_not_called()
            imp.assert_not_called()

    def test_unverified_import_preserves_both_databases_and_blocks_retry(self):
        self.run_stage(export=False)
        _, name = shadow.shadow_identity(self.state, self.site)
        marker = shadow._marker(self.state, self.site, name)
        self.assertIn("IMPORTED_UNVERIFIED", marker.read_text())
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.assertEqual(self.original_marker.read_bytes(), self.original_marker_bytes)
        with mock.patch.object(shadow.cloudpanel, "import_database") as imp:
            with self.assertRaisesRegex(shadow.ShadowBlocked, "SHADOW_ALREADY_CREATED"):
                shadow.stage_frozen_source_shadow(
                    self.state, self.site, self.sql, actual_target_identity=IDENTITY)
            imp.assert_not_called()

    def test_requires_frozen_source_and_exact_target_identity(self):
        mutations = [
            {"source_runtime_frozen": False},
            {"source_runtime_frozen": None},
            {"status": "PREPARED"},
            {"target_runtime_activated": True},
            {"dns_changed_by_p07": True},
            {"source_delete_allowed": True},
            {"existing_target_overwrite_allowed": True},
            {"cutover_prohibited": True},
            {"partial_parent_migration_id": MID},
        ]
        with mock.patch.object(shadow.cloudpanel, "add_database") as create:
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    state = dict(self.state, **mutation)
                    with self.assertRaises(shadow.ShadowBlocked):
                        shadow.stage_frozen_source_shadow(
                            state, self.site, self.sql, actual_target_identity=IDENTITY)
            with self.assertRaisesRegex(shadow.ShadowBlocked, "SHADOW_TARGET_IDENTITY_CHANGED"):
                shadow.stage_frozen_source_shadow(
                    self.state, self.site, self.sql, actual_target_identity="sha256:other")
            create.assert_not_called()

    def test_original_marker_app_mapping_and_source_dump_are_guarded(self):
        with mock.patch.object(shadow.cloudpanel, "add_database") as create:
            for source in (self.original_marker, self.config):
                if source == self.original_marker:
                    old = source.read_bytes()
                    source.unlink()
                else:
                    old = source.read_bytes()
                    source.write_text("define('DB_NAME', 'wrong');")
                with self.assertRaises(shadow.ShadowBlocked):
                    shadow.stage_frozen_source_shadow(
                        self.state, self.site, self.sql, actual_target_identity=IDENTITY)
                source.write_bytes(old)
            foreign = self.root / "foreign.sql.gz"
            shutil.copyfile(self.sql, foreign)
            with self.assertRaisesRegex(shadow.ShadowBlocked, "SHADOW_SOURCE_DUMP_UNOWNED"):
                shadow.stage_frozen_source_shadow(
                    self.state, self.site, foreign, actual_target_identity=IDENTITY)
            create.assert_not_called()

    def test_cross_database_or_executable_routines_never_enter_real_shadow_db(self):
        forbidden=(
            "CREATE DATABASE otherdb;",
            "DROP DATABASE otherdb;",
            "USE otherdb;",
            "/*!50003 CREATE TRIGGER audit BEFORE INSERT ON t FOR EACH ROW SET @x=1 */;",
            "CREATE PROCEDURE bad() DELETE FROM t;",
            "DROP TABLE otherdb.t;",
            "INSERT INTO otherdb.t VALUES (1);",
            "SOURCE /tmp/untrusted.sql",
            "DELIMITER ;;",
            "LOCK TABLES otherdb.t WRITE;",
        )
        with mock.patch.object(shadow.cloudpanel, "add_database") as create, \
             mock.patch.object(shadow.cloudpanel, "import_database") as imp:
            for sql in forbidden:
                with self.subTest(command=sql.split()[0]):
                    with gzip.open(self.sql, "wt", encoding="utf-8") as stream:
                        stream.write("CREATE TABLE t (id int);\n"+sql+"\n")
                    with self.assertRaises(shadow.ShadowBlocked):
                        shadow.stage_frozen_source_shadow(
                            self.state,self.site,self.sql,
                            actual_target_identity=IDENTITY)
            create.assert_not_called()
            imp.assert_not_called()
        self.assertEqual(self.original_marker.read_bytes(),self.original_marker_bytes)
        self.assertEqual(self.config.read_bytes(),self.original_config)

    def test_unsafe_dynamic_sql_never_creates_shadow(self):
        with gzip.open(self.sql, "wt", encoding="utf-8") as out:
            out.write(
                "CREATE TABLE t (id int);\n"
                "/*!50003 SET @query=IF(@present,'DROP TABLE t;', 'SELECT 1;') */;\n"
            )
        with mock.patch.object(shadow.cloudpanel, "add_database") as create:
            with self.assertRaisesRegex(shadow.ShadowBlocked, "SHADOW_SQL_GUARD_UNPROVEN"):
                shadow.stage_frozen_source_shadow(
                    self.state, self.site, self.sql, actual_target_identity=IDENTITY)
            create.assert_not_called()

    def test_shadow_config_switch_and_explicit_rollback_preserve_old_database(self):
        self.run_stage()
        owner_before=self.config.stat()
        result=shadow.activate_verified_shadow(
            self.state,self.site,actual_target_identity=IDENTITY)
        self.assertEqual(result["status"], "APP_SWITCH_VERIFIED_NOT_ACTIVATED")
        _, name=shadow.shadow_identity(self.state,self.site)
        receipt, marker, owned=shadow._read_verified_shadow(
            self.state,self.site,IDENTITY)
        self.assertEqual(receipt["status"],"APP_SWITCH_VERIFIED_NOT_ACTIVATED")
        self.assertIn(name,self.config.read_text())
        self.assertNotEqual(self.config.read_bytes(),self.original_config)
        self.assertEqual(self.config.stat().st_uid,owner_before.st_uid)
        self.assertEqual(self.config.stat().st_gid,owner_before.st_gid)
        self.assertEqual(self.config.stat().st_mode & 0o777, owner_before.st_mode & 0o777)
        backup=marker.with_suffix(".original.bak")
        self.assertEqual(backup.read_bytes(),self.original_config)
        self.assertEqual(backup.stat().st_mode & 0o777,0o600)
        with mock.patch.object(shadow.cloudpanel,"delete_database") as delete, \
             mock.patch.object(shadow.cloudpanel,"import_database") as imp:
            undone=shadow.rollback_shadow_application(
                self.state,self.site,actual_target_identity=IDENTITY)
            self.assertEqual(undone["status"],"APP_SWITCH_ROLLED_BACK")
            self.assertEqual(self.config.read_bytes(),self.original_config)
            self.assertEqual(self.config.stat().st_uid,owner_before.st_uid)
            self.assertEqual(self.config.stat().st_gid,owner_before.st_gid)
            self.assertEqual(self.config.stat().st_mode & 0o777, owner_before.st_mode & 0o777)
            self.assertEqual(self.original_marker.read_bytes(),self.original_marker_bytes)
            imp.assert_not_called()
            delete.assert_not_called()
        # No second activation after rollback, and the two DBs are retained.
        with self.assertRaisesRegex(shadow.ShadowBlocked,"SHADOW_SWITCH_RECEIPT_NOT_READY"):
            shadow.activate_verified_shadow(
                self.state,self.site,actual_target_identity=IDENTITY)

    def test_shadow_config_rewrite_failure_rolls_back_original(self):
        self.run_stage()
        original=shadow.app_config.rewrite_application_database_config
        def bad_rewrite(*args,**kwargs):
            # A failure after our own completed rewrite can restore the
            # verified shadow mapping to the private original backup.
            original(*args,**kwargs)
            raise shadow.app_config.AppConfigError("test")
        with mock.patch.object(shadow.app_config,"rewrite_application_database_config",
                               side_effect=bad_rewrite):
            with self.assertRaisesRegex(shadow.ShadowBlocked,
                                        "SHADOW_SWITCH_FAILED_ROLLED_BACK"):
                shadow.activate_verified_shadow(
                    self.state,self.site,actual_target_identity=IDENTITY)
        self.assertEqual(self.config.read_bytes(),self.original_config)
        self.assertEqual(self.original_marker.read_bytes(),self.original_marker_bytes)
        receipt, marker, _=shadow._read_verified_shadow(self.state,self.site,IDENTITY)
        self.assertEqual(receipt["status"],"APP_SWITCH_ROLLED_BACK")

    def test_unrecognized_config_during_activation_never_overwrites_owner(self):
        self.run_stage()
        def external_drift(*args,**kwargs):
            self.config.write_text("define('DB_NAME', 'owner-changed');\n")
            raise shadow.app_config.AppConfigError("test")
        with mock.patch.object(shadow.app_config,"rewrite_application_database_config",
                               side_effect=external_drift):
            with self.assertRaisesRegex(shadow.ShadowBlocked,
                                        "SHADOW_SWITCH_PARTIAL_ROLLBACK_REQUIRED"):
                shadow.activate_verified_shadow(
                    self.state,self.site,actual_target_identity=IDENTITY)
        self.assertIn("owner-changed",self.config.read_text())
        self.assertEqual(self.original_marker.read_bytes(),self.original_marker_bytes)
        _, name=shadow.shadow_identity(self.state,self.site)
        marker=shadow._marker(self.state,self.site,name)
        self.assertIn("APP_SWITCH_PENDING",marker.read_text())
        self.assertTrue(marker.with_suffix(".original.bak").is_file())

    def test_shadow_config_owner_change_blocks_unsafe_rollback(self):
        self.run_stage()
        shadow.activate_verified_shadow(
            self.state,self.site,actual_target_identity=IDENTITY)
        self.config.write_text("define('DB_NAME', 'owner-changed');\n")
        with self.assertRaisesRegex(
            shadow.ShadowBlocked,"SHADOW_CONFIG_OWNER_CHANGED_NO_OVERWRITE"
        ):
            shadow.rollback_shadow_application(
                self.state,self.site,actual_target_identity=IDENTITY)
        self.assertIn("owner-changed",self.config.read_text())
        self.assertEqual(self.original_marker.read_bytes(),self.original_marker_bytes)

    def test_shadow_config_rollback_denied_after_target_runtime_activation(self):
        self.run_stage()
        shadow.activate_verified_shadow(
            self.state,self.site,actual_target_identity=IDENTITY)
        self.state["target_runtime_activated"]=True
        with self.assertRaisesRegex(shadow.ShadowBlocked,"SHADOW_SWITCH_BOUNDARY_UNVERIFIED"):
            shadow.rollback_shadow_application(
                self.state,self.site,actual_target_identity=IDENTITY)
        self.state["target_runtime_activated"]=False
        self.assertEqual(
            shadow.rollback_shadow_application(
                self.state,self.site,actual_target_identity=IDENTITY)["status"],
            "APP_SWITCH_ROLLED_BACK"
        )

    def test_multiple_dbs_or_shadow_identity_collisions_are_rejected(self):
        for database_list in ([], ["origdb", "other"]):
            state=copy.deepcopy(self.state)
            site=state["sites"][0]
            site["mysql_databases"]=database_list
            with self.assertRaisesRegex(shadow.ShadowBlocked, "SHADOW_REQUIRES_SINGLE_DATABASE_SITE"):
                shadow.shadow_identity(state,site)
        origin, final = shadow.shadow_identity(self.state,self.site)
        state=copy.deepcopy(self.state)
        state["sites"].append({"domain":"second.example.test",
                               "mysql_databases":[final]})
        with self.assertRaisesRegex(shadow.ShadowBlocked,"SHADOW_IDENTITY_COLLISION"):
            shadow.shadow_identity(state,state["sites"][0])


if __name__ == "__main__":
    unittest.main()
