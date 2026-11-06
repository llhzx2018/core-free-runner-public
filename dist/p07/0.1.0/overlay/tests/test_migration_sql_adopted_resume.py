"""P07 original 18-site safe first-copy continuation after strict DB re-adoption.

Production DB writes and remote sources are mocked. Nothing here authorizes
final source freeze, DNS, data overwrite or loosening SQL guard.
"""
from __future__ import annotations
import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"lib"))
from tests.test_server_migration_pull import pull

MID="pull-20261106T065804Z-1aef6d0e"
DOMAIN="ilovem3u8.kewaro.com"
DB="kewaro-ilovem3u8"

def fixture():
    sites=[]
    for i in range(18):
        domain=DOMAIN if i==7 else f"s{i}.example.test"
        dbs=[DB] if i==7 else (
            [f"db{i}"] if i in (15,17) else [])
        row={"domain":domain,"site_user":f"user{i}",
             "site_root":f"/home/user{i}/htdocs/{domain}",
             "document_root":f"/home/user{i}/htdocs/{domain}",
             "mysql_databases":dbs,
             "stage_status":"PULLED_STAGED" if i<8 else "PENDING"}
        sites.append(row)
    checkpoint={
        "schema":"P07_EXISTING_DB_ADOPTION_CHECKPOINT_V1",
        "status":"SOURCE_TARGET_PREPARE_READBACK_PASS",
        "db_reimported":False,
        "cutover_allowed":False,
        "snapshot_is_atomic_across_servers":False,
        "target_dump_sha256":"c"*64,
    }
    sites[7]["database_adoption"]=checkpoint
    sites[7]["mysql_verification"]=[{
        "database":DB,"phase":"prepare","status":"PASS",
        "mode":"CANONICAL_SQL_EXACT",
        "recovered_from_failed_guard":True,
        "config_mode":"PREEXISTING_OWNED_DB_NO_REIMPORT",
    }]
    return {
        "schema":pull.SCHEMA,"migration_id":MID,"status":"PREPARE_FAILED",
        "source":{},"source_server_identity":"sha256:old",
        "target_server_identity":"sha256:cp2",
        "source_runtime_frozen":False,"target_runtime_activated":False,
        "dns_changed_by_p07":False,"source_delete_allowed":False,
        "existing_target_overwrite_allowed":False,
        "last_sql_guard_failure":{"reason":"CONDITIONAL_DDL",
                                  "flow":"SQL_GUARD_FLOW_V1_UNAVAILABLE"},
        "sites":sites,"external_assets":[],"sqlite_assets":[],
        "runtime_assets":{},
    }

class AdoptedResumeTests(unittest.TestCase):
    def test_default_resume_guards_remain_enforced(self):
        state=fixture()
        with mock.patch.object(pull,"load_state",return_value=state),\
             mock.patch.object(pull,"target_identity") as identity,\
             mock.patch.object(pull,"save_state") as save:
            with self.assertRaisesRegex(pull.PullMigrationError,
                "PREPARE_RESUME_SQL_GUARD_AND_RECOVERY_PROOF_REQUIRED"):
                pull.resume_prepare_migration(MID)
            identity.assert_not_called()
            save.assert_not_called()

    def test_scope_negative_before_remote_or_write(self):
        base=fixture()
        cases={
            "non18": lambda x:x["sites"].pop(),
            "wrong_db": lambda x:x["sites"][7]["database_adoption"].update(db_reimported=True),
            "missing_checkpoint":lambda x:x["sites"][7].pop("database_adoption"),
            "unverified_sql":lambda x:x["sites"][7]["mysql_verification"][0].update(mode="UNKNOWN"),
            "suffix_already_staged":lambda x:x["sites"][8].update(stage_status="PULLED_STAGED"),
            "activated_target":lambda x:x.update(target_runtime_activated=True),
            "wrong_target_id":lambda x:x.update(target_server_identity="different"),
        }
        for label,make in cases.items():
            with self.subTest(label=label):
                state=copy.deepcopy(base)
                make(state)
                with mock.patch.object(pull,"target_identity",return_value="sha256:cp2"),\
                     mock.patch.object(pull,"source_probe") as probe,\
                     mock.patch.object(pull,"save_state") as save,\
                     mock.patch.object(pull,"create_target_site") as create:
                    with self.assertRaises(pull.PullMigrationError):
                        pull._verify_adopted_failed_sql_resume_scope(state,DOMAIN)
                    probe.assert_not_called()
                    save.assert_not_called()
                    create.assert_not_called()

    def safe_preflight(self,state):
        def from_source(_source,names):
            return {"source_server_identity":"sha256:old",
                    "sites":[copy.deepcopy(next(row for row in state["sites"] if row["domain"]==n))
                             for n in names],
                    "capacity_estimate":{"target_required_bytes":1}}
        return mock.patch.multiple(
            pull,
            target_identity=mock.DEFAULT,
            _private_marker_readback=mock.DEFAULT,
            source_probe=mock.DEFAULT,
            target_preflight_local=mock.DEFAULT,
        ), from_source

    def test_exact_18_site_preflight_rejects_remaining_conflict(self):
        state=fixture()
        with mock.patch.object(pull,"target_identity",return_value="sha256:cp2"),\
             mock.patch.object(pull,"_private_marker_readback",return_value={
                 "username":"old_user","password":"private"}),\
             mock.patch.object(pull.legacy,"verify_target_site_creation",return_value=[]),\
             mock.patch.object(pull.app_config,"verify_rewritten_application_database_config",return_value=True),\
             mock.patch.object(pull,"source_probe",side_effect=lambda _s,n:{
                "source_server_identity":"sha256:old",
                "sites":[copy.deepcopy(next(row for row in state["sites"] if row["domain"]==i)) for i in n],
             }),\
             mock.patch.object(pull,"target_preflight_local",
                               side_effect=pull.PullMigrationError("TARGET_ALREADY_EXISTS")) as preflight:
            with self.assertRaisesRegex(pull.PullMigrationError,"TARGET_ALREADY_EXISTS"):
                pull._verify_adopted_failed_sql_resume_scope(state,DOMAIN)
            preflight.assert_called_once()

    def test_verified_resume_skips_first_eight_and_retains_guard_history(self):
        state=fixture()
        changed=[]
        def from_source(_source,names):
            return {
                "source_server_identity":"sha256:old",
                "sites":[copy.deepcopy(next(row for row in state["sites"] if row["domain"]==n))
                         for n in names],
            }
        with mock.patch.object(pull,"load_state",return_value=state),\
             mock.patch.object(pull,"target_identity",return_value="sha256:cp2"),\
             mock.patch.object(pull,"_private_marker_readback",return_value={
                 "username":"old_user","password":"private"}),\
             mock.patch.object(pull.legacy,"verify_target_site_creation",return_value=[]),\
             mock.patch.object(pull.app_config,"verify_rewritten_application_database_config",return_value=True),\
             mock.patch.object(pull,"source_probe",side_effect=from_source),\
             mock.patch.object(pull,"target_preflight_local",return_value={"status":"READY"}),\
             mock.patch.object(pull,"cloudpanel_database_server_ready_local",return_value=True),\
             mock.patch.object(pull,"require_mariadb_target"),\
             mock.patch.object(pull,"progress_note"),\
             mock.patch.object(pull,"refresh_migration_assets_from_source",return_value={}),\
             mock.patch.object(pull,"ensure_source_http_baseline"),\
             mock.patch.object(pull,"create_target_site",side_effect=lambda mid,row: changed.append(row["domain"])),\
             mock.patch.object(pull,"pull_site_files"),\
             mock.patch.object(pull,"sync_site_databases",return_value=0),\
             mock.patch.object(pull,"sync_external_assets",return_value=0),\
             mock.patch.object(pull,"sync_sqlite_assets",return_value=0),\
             mock.patch.object(pull,"stage_runtime_assets"),\
             mock.patch.object(pull,"pre_cutover_reconcile",return_value={"status":"PASS"}),\
             mock.patch.object(pull,"save_state"):
            result=pull.resume_prepare_migration(MID,verified_adoption=DOMAIN)
        self.assertEqual(result["status"],"PREPARED")
        self.assertEqual(len(changed),10)
        self.assertNotIn(DOMAIN,changed)
        self.assertEqual(result["sql_guard_recovery_history"]["reason"],"CONDITIONAL_DDL")
        self.assertFalse(result["sql_guard_recovery_history"]["cutover_allowed"])
        self.assertTrue(all(x["stage_status"]=="PULLED_STAGED" for x in result["sites"]))

    def test_confirmation_required_before_any_network_or_state(self):
        with mock.patch.object(pull,"load_state") as load:
            with self.assertRaisesRegex(pull.PullMigrationError,
                                        "ADOPTED_RESUME_EXPLICIT_CONFIRMATION_REQUIRED"):
                pull.resume_after_verified_adoption(MID,DOMAIN,"wrong")
            load.assert_not_called()

if __name__=="__main__":
    unittest.main()
