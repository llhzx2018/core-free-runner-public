"""17-site batch recovery synthetic integration; never creates live databases."""
from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_final_db_batch as batch
import migration_final_db_shadow as shadow
import server_migration as legacy
import server_migration_pull as pull

MID="pull-20261101T045943Z-923729a1"
IDENTITY="sha256:cp2"
SQL="CREATE TABLE t (id int);\nINSERT INTO t VALUES (1);\n"


class FinalShadowBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        patch=mock.patch.object(legacy,"STATE_ROOT",self.root/"migration-state")
        patch.start()
        self.addCleanup(patch.stop)
        # Both pull CLI and legacy marker owner use separate Python module
        # pointers. Bind them to the same test-only root to avoid real paths.
        pull_root=mock.patch.object(pull,"STATE_ROOT",self.root/"migration-state")
        pull_root.start()
        self.addCleanup(pull_root.stop)
        self.sites=[]
        self.configs={}
        self.original={}
        self.sources={}
        for i in range(17):
            domain=f"site{i:02}.example.test"
            site_root=self.root/f"site{i:02}"
            site_root.mkdir()
            dbs=[f"origdb{i}"] if i in (4,14) else []
            site={
                "domain":domain,"site_root":str(site_root),
                "mysql_databases":dbs,"stage_status":"PULLED_STAGED",
            }
            self.sites.append(site)
            if dbs:
                db=dbs[0]
                config=site_root/"wp-config.php"
                config.write_text(
                    f"define('DB_NAME', '{db}');\n"
                    f"define('DB_USER', 'origuser{i}');\n"
                    f"define('DB_PASSWORD', 'origpass{i}');\n",
                    encoding="utf-8",
                )
                self.configs[domain]=config
                self.original[domain]=config.read_bytes()
                marker=legacy.target_db_marker(MID,domain,db,1)
                legacy.atomic_private_json(marker,{
                    "domain":domain,"database":db,
                    "created_by_migration":MID,
                    "username":f"origuser{i}","password":f"origpass{i}",
                })
                source=legacy.state_dir(MID)/"mysql"/"final"/f"source{i}.sql.gz"
                source.parent.mkdir(parents=True,exist_ok=True)
                with gzip.open(source,"wt",encoding="utf-8") as stream:
                    stream.write(SQL)
                self.sources[domain]=source
        self.state={
            "migration_id":MID,"sites":self.sites,
            "status":"CUTOVER_RUNNING","source_runtime_frozen":True,
            "target_runtime_activated":False,"target_server_identity":IDENTITY,
            "source_delete_allowed":False,
            "dns_changed_by_p07":False,
            "existing_target_overwrite_allowed":False,
        }
        with mock.patch.object(shadow.cloudpanel,"add_database"), \
             mock.patch.object(shadow.cloudpanel,"import_database"), \
             mock.patch.object(shadow.cloudpanel,"export_database") as export:
            def readback(db,output):
                for site in self.sites:
                    if site["mysql_databases"]:
                        original, candidate=shadow.shadow_identity(self.state,site)
                        if db==candidate:
                            shutil.copyfile(self.sources[site["domain"]],output)
                            return output
                raise AssertionError("unknown shadow")
            export.side_effect=readback
            for site in self.sites:
                if site["mysql_databases"]:
                    result=shadow.stage_frozen_source_shadow(
                        self.state,site,self.sources[site["domain"]],
                        actual_target_identity=IDENTITY)
                    self.assertEqual(result["status"],"STAGED_VERIFIED_NOT_ACTIVATED")
        # Keep live readback fixture available during batch preflight and
        # activation; a receipt alone no longer authorizes a config switch.
        live_export=mock.patch.object(
            shadow.cloudpanel,"export_database",side_effect=readback
        )
        live_export.start()
        self.addCleanup(live_export.stop)

    def test_all_17_sites_preflight_then_switch_two_dbs_with_no_cutover(self):
        before=copy.deepcopy(self.state)
        with mock.patch.object(shadow.cloudpanel,"delete_database") as delete, \
             mock.patch.object(shadow.cloudpanel,"import_database") as imp:
            result=batch.switch_verified_shadow_batch(
                self.state,actual_target_identity=IDENTITY,
                expected_site_count=17)
            delete.assert_not_called()
            imp.assert_not_called()
        self.assertEqual(result["status"],"SWITCHED_VERIFIED_NOT_ACTIVATED")
        self.assertEqual(result["site_count"],17)
        self.assertEqual(result["database_count"],2)
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["runtime_activated"])
        self.assertEqual(self.state,before)
        for site in self.sites:
            if site["mysql_databases"]:
                self.assertNotEqual(
                    self.configs[site["domain"]].read_bytes(),
                    self.original[site["domain"]],
                )
        receipt=batch._receipt_path(MID)
        self.assertEqual(receipt.stat().st_mode & 0o777,0o600)
        self.assertEqual(receipt.parent.stat().st_mode & 0o777,0o700)
        journal=receipt.read_text()
        self.assertNotIn("origpass",journal)
        self.assertNotIn("shadow_password",journal)
        with self.assertRaisesRegex(
            pull.PullMigrationError,"FINAL_MYSQL_SAFE_REPLACEMENT_NOT_IMPLEMENTED"
        ):
            pull.require_non_destructive_final_db_plan(self.state)

    def test_one_shadow_changed_before_batch_switch_blocks_all_sites(self):
        """All sites preflight must reject a changed shadow before any switch."""
        staged = [site for site in self.sites if site["mysql_databases"]]
        target_db = shadow.shadow_identity(self.state, staged[-1])[1]
        def changed_export(db, output):
            if db == target_db:
                with gzip.open(output, "wt", encoding="utf-8") as stream:
                    stream.write("CREATE TABLE t (id int);\nINSERT INTO t VALUES (9);\n")
                return output
            domain = staged[0]["domain"]
            shutil.copyfile(self.sources[domain], output)
            return output
        with mock.patch.object(
            shadow.cloudpanel, "export_database", side_effect=changed_export
        ):
            with self.assertRaises(batch.BatchBlocked):
                batch.switch_verified_shadow_batch(
                    self.state, actual_target_identity=IDENTITY,
                    expected_site_count=17,
                )
        for domain, config in self.configs.items():
            self.assertEqual(config.read_bytes(), self.original[domain])

    def test_frozen_shadow_transaction_connects_existing_verified_stages(self):
        with (mock.patch.object(pull, "target_identity", return_value=IDENTITY),
             mock.patch.object(pull, "stage_frozen_final_mysql_shadows",
                 return_value={"status": "ALL_SHADOW_DATABASES_STAGED_NOT_ACTIVATED",
                               "database_count": 2, "app_config_modified": False,
                               "cutover_allowed": False}) as stage):
            result = pull.run_frozen_final_mysql_shadow_transaction(
                self.state, expected_site_count=17)
            self.assertEqual(result["database_count"], 2)
            self.assertFalse(result["cutover_allowed"])
            stage.assert_called_once()
            undone = pull.rollback_frozen_final_mysql_shadow_transaction(
                self.state, expected_site_count=17)
            self.assertEqual(undone["status"], "FINAL_MYSQL_APP_MAPPING_ROLLED_BACK")
        for domain, config in self.configs.items():
            self.assertEqual(config.read_bytes(), self.original[domain])

    def test_existing_cutover_recovery_detects_and_undoes_shadow_journal(self):
        before=copy.deepcopy(self.state)
        self.assertTrue(pull.recover_shadow_application_mappings_if_present(self.state))
        batch.switch_verified_shadow_batch(
            self.state,actual_target_identity=IDENTITY,expected_site_count=17)
        with mock.patch.object(pull,"target_identity",return_value=IDENTITY):
            self.assertTrue(
                pull.recover_shadow_application_mappings_if_present(self.state)
            )
        self.assertEqual(self.state,before)
        for domain,config in self.configs.items():
            self.assertEqual(config.read_bytes(),self.original[domain])
        self.assertEqual(
            batch._read_receipt(batch._receipt_path(MID))["status"],"ROLLED_BACK"
        )

    def test_corrupt_shadow_recovery_receipt_cannot_claim_success(self):
        batch.switch_verified_shadow_batch(
            self.state,actual_target_identity=IDENTITY,expected_site_count=17)
        journal=batch._receipt_path(MID)
        journal.write_text("{not json",encoding="utf-8")
        with mock.patch.object(pull,"target_identity",return_value=IDENTITY), \
             mock.patch.object(batch.shadow,"rollback_shadow_application") as undo:
            self.assertFalse(pull.recover_shadow_application_mappings_if_present(self.state))
            undo.assert_not_called()
        self.assertTrue(any(
            config.read_bytes()!=self.original[domain]
            for domain,config in self.configs.items()
        ))

    def test_after_successful_smoke_pre_dns_manual_db_rollback_is_allowed(self):
        """CUTOVER_PREP_READY retains frozen source; DB journal stays readable."""
        batch.switch_verified_shadow_batch(
            self.state, actual_target_identity=IDENTITY, expected_site_count=17
        )
        self.state["status"] = "CUTOVER_PREP_READY"
        before = copy.deepcopy(self.state)
        with mock.patch.object(pull, "target_identity", return_value=IDENTITY):
            result = pull.rollback_frozen_final_mysql_shadow_transaction(
                self.state, expected_site_count=17,
            )
        self.assertEqual(result["status"], "FINAL_MYSQL_APP_MAPPING_ROLLED_BACK")
        self.assertEqual(self.state, before)
        for domain, config in self.configs.items():
            self.assertEqual(config.read_bytes(), self.original[domain])

    def test_post_dns_and_running_target_cannot_use_pre_dns_db_rollback(self):
        batch.switch_verified_shadow_batch(
            self.state, actual_target_identity=IDENTITY, expected_site_count=17
        )
        self.state["status"] = "CUTOVER_PREP_READY"
        for key, value in (
            ("target_runtime_activated", True),
            ("source_runtime_frozen", False),
            ("dns_changed_by_p07", True),
        ):
            original = self.state[key]
            self.state[key] = value
            with self.subTest(key=key), mock.patch.object(
                batch, "rollback_verified_shadow_batch"
            ) as rollback:
                with self.assertRaises(pull.PullMigrationError):
                    pull.rollback_frozen_final_mysql_shadow_transaction(
                        self.state, expected_site_count=17
                    )
                rollback.assert_not_called()
            self.state[key] = original
        self.assertTrue(any(
            config.read_bytes() != self.original[domain]
            for domain, config in self.configs.items()
        ))

    def test_second_site_failure_forces_reverse_rollback_across_all_sites(self):
        real=shadow.activate_verified_shadow
        calls=[]
        def fail_second(state,site,*,actual_target_identity):
            calls.append(site["domain"])
            if len(calls)==2:
                raise shadow.ShadowBlocked("SYNTHETIC_SECOND_SITE_FAILED")
            return real(state,site,actual_target_identity=actual_target_identity)
        with mock.patch.object(batch.shadow,"activate_verified_shadow",side_effect=fail_second), \
             mock.patch.object(shadow.cloudpanel,"delete_database") as delete:
            with self.assertRaisesRegex(
                batch.BatchBlocked,"FINAL_SHADOW_BATCH_FAILED_ROLLED_BACK"
            ):
                batch.switch_verified_shadow_batch(
                    self.state,actual_target_identity=IDENTITY,
                    expected_site_count=17)
            delete.assert_not_called()
        self.assertEqual(len(calls),2)
        for domain,path in self.configs.items():
            self.assertEqual(path.read_bytes(),self.original[domain])
        self.assertEqual(batch._read_receipt(batch._receipt_path(MID))["status"],"ROLLED_BACK")

    def test_all_site_preflight_fails_before_first_mapping_changes(self):
        second=[s for s in self.sites if s["mysql_databases"]][-1]
        _original, shadow_db=shadow.shadow_identity(self.state,second)
        shadow._marker(self.state,second,shadow_db).unlink()
        with mock.patch.object(batch.shadow,"activate_verified_shadow") as switch:
            with self.assertRaisesRegex(
                batch.BatchBlocked,"FINAL_SHADOW_BATCH_SITE_PROOF_INVALID"
            ):
                batch.switch_verified_shadow_batch(
                    self.state,actual_target_identity=IDENTITY,
                    expected_site_count=17)
            switch.assert_not_called()
        for domain,path in self.configs.items():
            self.assertEqual(path.read_bytes(),self.original[domain])
        self.assertFalse(batch._receipt_path(MID).exists())

    def test_crashed_batch_recovers_switched_site_without_committed_count(self):
        first=[s for s in self.sites if s["mysql_databases"]][0]
        shadow.activate_verified_shadow(self.state,first,actual_target_identity=IDENTITY)
        _rows, selected, fingerprint=batch._safe_scope(self.state,IDENTITY,17)
        legacy.atomic_private_json(batch._receipt_path(MID),{
            "schema":"vf-server-ops.final-shadow-batch.v1",
            "migration_id":MID,"target_server_identity":IDENTITY,
            "inventory_sha256":fingerprint,
            "site_count":17,"db_domains":[s["domain"] for s in selected],
            "status":"SWITCHING","last_committed_domain_count":0,
            "cutover_allowed":False,
        })
        result=batch.rollback_verified_shadow_batch(
            self.state,actual_target_identity=IDENTITY,
            expected_site_count=17)
        self.assertEqual(result["status"],"ROLLED_BACK")
        self.assertFalse(result["cutover_allowed"])
        for domain,path in self.configs.items():
            self.assertEqual(path.read_bytes(),self.original[domain])
        # Explicit rollback remains idempotent after a fully restored batch.
        again=batch.rollback_verified_shadow_batch(
            self.state,actual_target_identity=IDENTITY,
            expected_site_count=17)
        self.assertEqual(again["status"],"ROLLED_BACK")

    def test_external_edit_reports_partial_rollback_without_overwriting_owner(self):
        batch.switch_verified_shadow_batch(
            self.state,actual_target_identity=IDENTITY,
            expected_site_count=17)
        first=next(s for s in self.sites if s["mysql_databases"])
        first_config=self.configs[first["domain"]]
        first_config.write_text("define('DB_NAME','owner-edited');\n")
        with self.assertRaisesRegex(batch.BatchBlocked,"FINAL_SHADOW_BATCH_ROLLBACK_PARTIAL"):
            batch.rollback_verified_shadow_batch(
                self.state,actual_target_identity=IDENTITY,
                expected_site_count=17)
        self.assertIn("owner-edited",first_config.read_text())
        other=next(domain for domain in self.configs if domain!=first["domain"])
        self.assertEqual(self.configs[other].read_bytes(),self.original[other])
        journal=batch._read_receipt(batch._receipt_path(MID))
        self.assertEqual(journal["status"],"ROLLBACK_PARTIAL")
        self.assertEqual(journal["rollback_failed_site_count"],1)

    def test_batch_rollback_receipt_binds_original_owner_map_immutably(self):
        """A forged new owner id must not permit replaying a different task."""
        original_owners = {
            site["domain"]: MID
            for site in self.sites if site["mysql_databases"]
        }
        self.state["original_db_migration_owners"] = {
            domain: "pull-20261101T052411Z-35663c25"
            for domain in original_owners
        }
        # A forged per-site owner cannot match the saved individual original
        # database receipts, even if the logical SQL content is unchanged.
        with mock.patch.object(batch.shadow, "activate_verified_shadow") as change:
            with self.assertRaises(batch.BatchBlocked):
                batch.switch_verified_shadow_batch(
                    self.state, actual_target_identity=IDENTITY,
                    expected_site_count=17,
                )
            change.assert_not_called()
        self.assertFalse(batch._receipt_path(MID).exists())
        self.state["original_db_migration_owners"] = original_owners
        result = batch.switch_verified_shadow_batch(
            self.state, actual_target_identity=IDENTITY, expected_site_count=17,
        )
        self.assertEqual(result["status"], "SWITCHED_VERIFIED_NOT_ACTIVATED")
        self.state["original_db_migration_owners"] = {
            site["domain"]: "pull-20261101T052411Z-35663c25"
            for site in self.sites if site["mysql_databases"]
        }
        with mock.patch.object(batch.shadow, "rollback_shadow_application") as undo:
            with self.assertRaises(batch.BatchBlocked):
                batch.rollback_verified_shadow_batch(
                    self.state, actual_target_identity=IDENTITY,
                    expected_site_count=17,
                )
            undo.assert_not_called()
        self.state["original_db_migration_owners"] = original_owners
        rolled_back = batch.rollback_verified_shadow_batch(
            self.state, actual_target_identity=IDENTITY, expected_site_count=17,
        )
        self.assertEqual(rolled_back["status"], "ROLLED_BACK")

    def test_duplicate_attempt_is_blocked_even_after_successful_rollback(self):
        batch.switch_verified_shadow_batch(
            self.state,actual_target_identity=IDENTITY,
            expected_site_count=17)
        batch.rollback_verified_shadow_batch(
            self.state,actual_target_identity=IDENTITY,
            expected_site_count=17)
        with mock.patch.object(batch.shadow,"activate_verified_shadow") as switch:
            with self.assertRaisesRegex(
                batch.BatchBlocked,"FINAL_SHADOW_BATCH_PREVIOUS_ATTEMPT_RECOVERY_REQUIRED"
            ):
                batch.switch_verified_shadow_batch(
                    self.state,actual_target_identity=IDENTITY,
                    expected_site_count=17)
            switch.assert_not_called()

    def _clear_synthetic_shadow_receipts(self):
        for site in self.sites:
            if site["mysql_databases"]:
                _, db=shadow.shadow_identity(self.state,site)
                shadow._marker(self.state,site,db).unlink()
        self.state["source"]={
            "host":"old.example.test","ssh_user":"root","ssh_port":22,
        }

    def test_frozen_source_two_shadow_imports_staged_without_config_switch(self):
        self._clear_synthetic_shadow_receipts()
        created=[]
        def transfer(_source,_remote,local):
            with gzip.open(local,"wt",encoding="utf-8") as stream:
                stream.write(SQL)
        def stage(_state,site,_dump,*,actual_target_identity):
            created.append(site["domain"])
            self.assertEqual(actual_target_identity,IDENTITY)
            return {"status":"STAGED_VERIFIED_NOT_ACTIVATED"}
        with mock.patch.object(pull,"target_identity",return_value=IDENTITY), \
             mock.patch.object(pull,"remote_staging_root",return_value="/private/staging"), \
             mock.patch.object(pull,"source_export_database") as export, \
             mock.patch.object(pull,"pull_path",side_effect=transfer) as transfer_call, \
             mock.patch.object(pull,"source_remote") as cleanup, \
             mock.patch.object(shadow,"stage_frozen_source_shadow",side_effect=stage), \
             mock.patch.object(shadow.cloudpanel,"delete_database") as delete:
            result=pull.stage_frozen_final_mysql_shadows(
                self.state,expected_site_count=17)
            self.assertEqual(export.call_count,2)
            self.assertEqual(transfer_call.call_count,2)
            self.assertEqual(cleanup.call_count,2)
            delete.assert_not_called()
        self.assertEqual(result["database_count"],2)
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["app_config_modified"])
        self.assertEqual(len(created),2)
        for domain,path in self.configs.items():
            self.assertEqual(path.read_bytes(),self.original[domain])
        with self.assertRaisesRegex(
            pull.PullMigrationError,"FINAL_MYSQL_SAFE_REPLACEMENT_NOT_IMPLEMENTED"
        ):
            pull.require_non_destructive_final_db_plan(self.state)

    def test_shadow_stage_second_db_error_preserves_existing_configs(self):
        self._clear_synthetic_shadow_receipts()
        imports=[]
        def transfer(_source,_remote,local):
            with gzip.open(local,"wt",encoding="utf-8") as stream:
                stream.write(SQL)
        def stage(_state,site,_dump,*,actual_target_identity):
            imports.append(site["domain"])
            if len(imports)==2:
                raise shadow.ShadowBlocked("synthetic failure")
            return {"status":"STAGED_VERIFIED_NOT_ACTIVATED"}
        with mock.patch.object(pull,"target_identity",return_value=IDENTITY), \
             mock.patch.object(pull,"remote_staging_root",return_value="/private/staging"), \
             mock.patch.object(pull,"source_export_database"), \
             mock.patch.object(pull,"pull_path",side_effect=transfer), \
             mock.patch.object(pull,"source_remote") as cleanup, \
             mock.patch.object(shadow,"stage_frozen_source_shadow",side_effect=stage), \
             mock.patch.object(batch.shadow,"activate_verified_shadow") as switch:
            with self.assertRaisesRegex(
                pull.PullMigrationError,"FINAL_SHADOW_STAGING_RECOVERY_REQUIRED"
            ):
                pull.stage_frozen_final_mysql_shadows(
                    self.state,expected_site_count=17)
            self.assertEqual(cleanup.call_count,2)
            switch.assert_not_called()
        self.assertEqual(len(imports),2)
        for domain,path in self.configs.items():
            self.assertEqual(path.read_bytes(),self.original[domain])

    def test_final_shadow_staging_checks_all_original_receipts_before_export(self):
        self._clear_synthetic_shadow_receipts()
        last=[s for s in self.sites if s["mysql_databases"]][-1]
        legacy.target_db_marker(MID,last["domain"],last["mysql_databases"][0],1).unlink()
        with mock.patch.object(pull,"target_identity",return_value=IDENTITY), \
             mock.patch.object(pull,"source_export_database") as export:
            with self.assertRaisesRegex(
                pull.PullMigrationError,"FINAL_SHADOW_ORIGINAL_APP_OR_DB_UNVERIFIED"
            ):
                pull.stage_frozen_final_mysql_shadows(
                    self.state,expected_site_count=17)
            export.assert_not_called()
        for domain,path in self.configs.items():
            self.assertEqual(path.read_bytes(),self.original[domain])

    def _prepared_single_migration(self):
        # The common fixture has already staged shadow DBs for transaction
        # tests. A legitimate PREPARED pre-freeze task must have *no* shadow
        # markers yet; any previous attempt must fail closed.
        for site in self.sites:
            if site["mysql_databases"]:
                _, name = shadow.shadow_identity(self.state, site)
                shadow._marker(self.state, site, name).unlink()
        state=copy.deepcopy(self.state)
        state["status"]="PREPARED"
        state["source_runtime_frozen"]=False
        state["source_runtime_path"]="/root/vfops/old-source-helper.py"
        state["source"]={"host":"old.example.test"}
        state["source_server_identity"]="sha256:old-test"
        return state

    def test_pre_freeze_db_cutover_checks_all_17_ownership_receipts(self):
        state=self._prepared_single_migration()
        with mock.patch.object(pull,"target_identity",return_value=IDENTITY):
            pull.require_non_destructive_final_db_plan(state)
            state["original_db_migration_owners"]={
                row["domain"]:MID for row in state["sites"]
                if row["mysql_databases"]
            }
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "FINAL_MYSQL_SAFE_REPLACEMENT_NOT_IMPLEMENTED",
            ):
                pull.require_non_destructive_final_db_plan(state)
            state.pop("original_db_migration_owners")
            state["partial_parent_migration_id"]=MID
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "FINAL_MYSQL_SAFE_REPLACEMENT_NOT_IMPLEMENTED",
            ):
                pull.require_non_destructive_final_db_plan(state)
            state.pop("partial_parent_migration_id")
            last=next(row for row in state["sites"] if row["mysql_databases"])
            last["stage_status"]="PENDING"
            with self.assertRaisesRegex(
                pull.PullMigrationError,"FINAL_MYSQL_SITE_NOT_STAGED",
            ):
                pull.require_non_destructive_final_db_plan(state)
            last["stage_status"]="PULLED_STAGED"
            self.configs[last["domain"]].write_text(
                "define('DB_NAME', 'not-original');\n"
            )
            with self.assertRaisesRegex(
                pull.PullMigrationError,"FINAL_MYSQL_ORIGINAL_APP_CONFIG_UNVERIFIED",
            ):
                pull.require_non_destructive_final_db_plan(state)
        self.assertFalse(batch._receipt_path(MID).exists())

    def test_prepared_single_task_cutover_uses_shadow_phase_not_old_db_import(self):
        state=self._prepared_single_migration()
        state["source_runtime_path"]="/root/test/source.py"
        original_state=copy.deepcopy(state)
        def freeze(current):
            current["source_runtime_frozen"]=True
        with mock.patch.object(pull,"load_state",return_value=state), \
             mock.patch.object(pull,"save_state"), \
             mock.patch.object(pull,"require_mariadb_target"), \
             mock.patch.object(pull,"target_identity",return_value=IDENTITY), \
             mock.patch.object(pull,"refresh_migration_assets_from_source",
                 return_value={
                     "external_added_paths":[],"sqlite_added_paths":[],
                     "runtime_assets_changed":False,
                 }), \
             mock.patch.object(pull,"ensure_source_http_baseline"), \
             mock.patch.object(pull,"pre_cutover_reconcile",
                 return_value={"status":"PASS","failures":[]}), \
             mock.patch.object(pull,"freeze_old_server",side_effect=freeze) as freezer, \
             mock.patch.object(pull,"pull_site_files"), \
             mock.patch.object(pull,"sync_external_assets",return_value=[]), \
             mock.patch.object(pull,"sync_sqlite_assets",return_value=0), \
             mock.patch.object(pull,"sync_site_databases") as legacy_import, \
             mock.patch.object(pull,"run_frozen_final_mysql_shadow_transaction",
                 return_value={
                     "status":"FINAL_MYSQL_SHADOW_TRANSACTION_VERIFIED_NOT_CUTOVER",
                     "source_runtime_frozen":True,
                     "original_databases_retained":True,
                     "cutover_allowed":False,"database_count":2,
                 }) as shadow_phase, \
             mock.patch.object(pull,"activate_target_runtime"), \
             mock.patch.object(pull,"target_smoke",
                 return_value={"pass":17,"fail":0,"failures":[]}):
            result=pull.cutover_migration(
                MID,f"CUTOVER_PULL:{MID}"
            )
            freezer.assert_called_once()
            shadow_phase.assert_called_once_with(
                state,expected_site_count=17
            )
            legacy_import.assert_not_called()
        self.assertEqual(result["status"],"CUTOVER_PREP_READY")
        self.assertEqual(result["mysql_final_count"],2)
        self.assertFalse(result["mysql_shadow_transaction"]["cutover_allowed"])
        self.assertEqual(self.configs[next(iter(self.configs))].read_bytes(),
                         self.original[next(iter(self.configs))])
        self.assertEqual(original_state["source_runtime_frozen"],False)

    def test_17_site_scope_and_identity_drift_block_before_any_switch(self):
        with mock.patch.object(batch.shadow,"activate_verified_shadow") as switch:
            with self.assertRaises(batch.BatchBlocked):
                batch.switch_verified_shadow_batch(
                    self.state,actual_target_identity=IDENTITY,
                    expected_site_count=16)
            with self.assertRaises(batch.BatchBlocked):
                batch.switch_verified_shadow_batch(
                    self.state,actual_target_identity="sha256:other",
                    expected_site_count=17)
            self.sites[0]["stage_status"]="PENDING"
            with self.assertRaises(batch.BatchBlocked):
                batch.switch_verified_shadow_batch(
                    self.state,actual_target_identity=IDENTITY,
                    expected_site_count=17)
            switch.assert_not_called()
        self.assertFalse(batch._receipt_path(MID).exists())


if __name__ == "__main__":
    unittest.main()
