"""Synthetic parent + failed partial-child recovery. No live server or DB."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_chain_recovery as chain
import server_migration_pull as pull

PARENT = "pull-20261101T045943Z-923729a1"
CHILD = "pull-20261101T052411Z-35663c25"
DOMAINS = (
    "123.kewaro.com","123.m3u8.one","assetbox.kewaro.com",
    "doc.kewaro.com","domain.kewaro.com","example.cloudpanel.io",
    "forge.kewaro.com","ilovem3u8.kewaro.com","infra.kewaro.com",
    "lib.kewaro.com","press.kewaro.com","seo.kewaro.com",
    "start.kewaro.com","textbox.kewaro.com","unzip.kewaro.com",
    "updates.kewaro.com","www3.m3u8.one",
)


def two_tasks():
    src={"host":"old.example.test","ip":"192.0.2.10",
         "ssh_user":"root","ssh_port":22}
    def row(i,domain,staged):
        return {
          "domain":domain,"site_user":f"owner{i}",
          "site_root":f"/home/owner{i}/htdocs/{domain}",
          "document_root":f"/home/owner{i}/htdocs/{domain}",
          "mysql_databases":["db"+str(i)] if i in (7,14,16) else [],
          "runtime":{"type":"php","version":"8.3"},
          "stage_status":"PULLED_STAGED" if staged else "PENDING"}
    parent={
        "schema":pull.SCHEMA,"migration_id":PARENT,
        "status":"PREPARE_FAILED",
        "last_sql_guard_failure":{"reason":"CONDITIONAL_DDL"},
        "source":src,"source_server_identity":"sha256:source",
        "target_server_identity":"sha256:cp2",
        "source_runtime_frozen":False,
        "target_runtime_activated":False,"dns_changed_by_p07":False,
        "source_delete_allowed":False,
        "existing_target_overwrite_allowed":False,
        "sites":[row(i,domain,i<7) for i,domain in enumerate(DOMAINS)],
    }
    child=copy.deepcopy(parent)
    child["migration_id"]=CHILD
    child["sites"]=copy.deepcopy(parent["sites"][8:])
    for i,entry in enumerate(child["sites"]):
        entry["stage_status"]="PULLED_STAGED" if i<6 else "PENDING"
    child["partial_parent_migration_id"]=PARENT
    child["cutover_prohibited"]=True
    return parent,child


class ChainTests(unittest.TestCase):
    def test_child_and_parent_remain_linked_after_independent_db_recovery(self):
        import migration_db_adoption
        a,b=two_tasks()
        self.assertEqual(chain.select(a,b)["staged_count"],13)
        def rec(state,idx,domain):
            from tests.test_migration_db_adoption import proof
            row=state["sites"][idx]
            p=proof(domain,state["migration_id"],row["mysql_databases"][0])
            return migration_db_adoption.stage_existing_verified_site(state,domain,p)
        parent_done=rec(a,7,"ilovem3u8.kewaro.com")
        parent_scope=chain.select(parent_done,b)
        self.assertEqual(parent_scope["staged_count"],14)
        self.assertEqual(parent_scope["blocker_stage_adopted"],[True,False])
        child_done=rec(b,6,"unzip.kewaro.com")
        child_scope=chain.select(a,child_done)
        self.assertEqual(child_scope["staged_count"],14)
        self.assertEqual(child_scope["blocker_stage_adopted"],[False,True])
        pair=chain.select(parent_done,child_done)
        self.assertEqual(pair["staged_count"],15)
        self.assertEqual(pair["blocker_stage_adopted"],[True,True])
        self.assertEqual(pair["blocked_sites"],[
            "ilovem3u8.kewaro.com","unzip.kewaro.com"])
        self.assertEqual(pair["uncreated_candidate_domains"],[
            "updates.kewaro.com","www3.m3u8.one"])
        self.assertFalse(pair["consolidated_cutover_allowed"])
        self.assertEqual(a["sites"][7]["stage_status"],"PENDING")
        self.assertEqual(b["sites"][6]["stage_status"],"PENDING")

    def test_forged_staged_flag_without_db_recovery_proof_does_not_count(self):
        a,b=two_tasks()
        a["sites"][7]["stage_status"]="PULLED_STAGED"
        with self.assertRaises(chain.ChainRecoveryBlocked):
            chain.select(a,b)
        a,b=two_tasks()
        b["sites"][6]["stage_status"]="PULLED_STAGED"
        with self.assertRaises(chain.ChainRecoveryBlocked):
            chain.select(a,b)

    def test_tail_stage_after_two_owned_db_adoptions_creates_only_two_sites(self):
        import migration_db_adoption
        from tests.test_migration_db_adoption import proof
        a,b=two_tasks()
        a=migration_db_adoption.stage_existing_verified_site(
            a,"ilovem3u8.kewaro.com",
            proof("ilovem3u8.kewaro.com",PARENT,"db7"))
        b=migration_db_adoption.stage_existing_verified_site(
            b,"unzip.kewaro.com",proof("unzip.kewaro.com",CHILD,"db14"))
        with mock.patch.object(pull,"load_state",side_effect=[a,b]), \
             mock.patch.object(pull,"target_identity",return_value="sha256:cp2"), \
             mock.patch.object(pull,"prepare_migration",return_value={"status":"PREPARED"}) as stage, \
             mock.patch.object(pull,"save_state") as save, \
             mock.patch.object(pull,"sync_site_databases") as import_existing:
            result=pull.prepare_chain_tail(PARENT,CHILD,
                "STAGE_CHAIN_TAIL:"+PARENT+":"+CHILD)
        self.assertEqual(result["status"],"PREPARED")
        self.assertEqual(stage.call_args.args[1],
            ["updates.kewaro.com","www3.m3u8.one"])
        self.assertEqual(stage.call_args.kwargs["remainder_parent"],PARENT)
        save.assert_not_called()
        import_existing.assert_not_called()

    def test_exact_17_site_result_is_non_executable(self):
        a,b=two_tasks()
        before=copy.deepcopy((a,b))
        result=chain.select(a,b)
        self.assertEqual(result["status"],"RECOVERY_PROOF_REQUIRED")
        self.assertEqual(result["site_count"],17)
        self.assertEqual(result["staged_count"],13)
        self.assertEqual(result["blocked_sites"],
                         ["ilovem3u8.kewaro.com","unzip.kewaro.com"])
        self.assertEqual(result["uncreated_candidate_domains"],
                         ["updates.kewaro.com","www3.m3u8.one"])
        for name in ("guarded_database_retry_allowed",
                     "consolidated_cutover_allowed",
                     "partial_child_cutover_allowed",
                     "state_writes_performed","database_writes_performed"):
            self.assertIs(result[name],False)
        self.assertEqual((a,b),before)

    def test_rejects_false_parent_or_child_status_or_invalid_guard(self):
        for key,value,who in (
            ("status","PREPARED",0),
            ("status","PREPARED",1),
            ("last_sql_guard_failure",{"reason":"UNKNOWN"},0),
            ("last_sql_guard_failure",{"reason":"UNKNOWN"},1),
            ("source_runtime_frozen",True,0),
            ("source_runtime_frozen",True,1),
            ("target_runtime_activated",True,1),
            ("dns_changed_by_p07",True,1),
            ("existing_target_overwrite_allowed",True,0),
            ("source_delete_allowed",True,1),
            ("cutover_prohibited",False,1),
            ("partial_parent_migration_id","other",1),
        ):
            with self.subTest(key=key,value=value,who=who):
                a,b=two_tasks()
                (a,b)[who][key]=value
                with self.assertRaises(chain.ChainRecoveryBlocked):
                    chain.select(a,b)

    def test_rejects_identity_drift(self):
        for key,value,who in (
            ("source_server_identity","changed",1),
            ("target_server_identity","changed",1),
            ("source",{"host":"other","ip":"192.0.2.11",
                       "ssh_user":"root","ssh_port":22},1),
            ("migration_id",PARENT,1),
        ):
            with self.subTest(key=key):
                a,b=two_tasks()
                (a,b)[who][key]=value
                with self.assertRaises(chain.ChainRecoveryBlocked):
                    chain.select(a,b)

    def test_rejects_source_site_contract_change(self):
        for key,value in (
            ("domain","other.example.org"),("site_user","rogue"),
            ("site_root","/tmp/invalid"),("mysql_databases",["rogue_db"]),
            ("runtime",{"type":"php","version":"7.0"}),
        ):
            with self.subTest(key=key):
                a,b=two_tasks()
                b["sites"][1][key]=value
                with self.assertRaises(chain.ChainRecoveryBlocked):
                    chain.select(a,b)

    def test_rejects_unbalanced_staging_and_child_lists(self):
        a,b=two_tasks()
        b["sites"][0]["stage_status"]="PENDING"
        with self.assertRaises(chain.ChainRecoveryBlocked):
            chain.select(a,b)
        a,b=two_tasks()
        b["sites"].pop()
        with self.assertRaises(chain.ChainRecoveryBlocked):
            chain.select(a,b)
        a,b=two_tasks()
        b["sites"][-1]["stage_status"]="PULLED_STAGED"
        with self.assertRaises(chain.ChainRecoveryBlocked):
            chain.select(a,b)
        a,b=two_tasks()
        a["sites"][0]["stage_status"]="PENDING"
        with self.assertRaises(chain.ChainRecoveryBlocked):
            chain.select(a,b)

    def test_chain_tail_uses_exact_two_uncreated_domains(self):
        a,b=two_tasks()
        original=copy.deepcopy((a,b))
        with mock.patch.object(pull,"load_state",side_effect=[a,b]), \
             mock.patch.object(pull,"target_identity",return_value="sha256:cp2"), \
             mock.patch.object(pull,"prepare_migration",return_value={"status":"PREPARED"}) as prepare, \
             mock.patch.object(pull,"resume_prepare_migration") as resume, \
             mock.patch.object(pull,"save_state") as save:
            result=pull.prepare_chain_tail(PARENT,CHILD,"STAGE_CHAIN_TAIL:"+PARENT+":"+CHILD)
        self.assertEqual(result,{"status":"PREPARED"})
        self.assertEqual((a,b),original)
        prepare.assert_called_once()
        args=prepare.call_args
        self.assertEqual(args.args[:3],(
            a["source"],["updates.kewaro.com","www3.m3u8.one"],
            "PREPARE_PULL_MIGRATION",
        ))
        self.assertEqual(args.kwargs["remainder_parent"],PARENT)
        self.assertEqual(args.kwargs["expected_source_identity"],"sha256:source")
        self.assertEqual([x["domain"] for x in args.kwargs["expected_remainder_sites"]],
                         ["updates.kewaro.com","www3.m3u8.one"])
        resume.assert_not_called()
        save.assert_not_called()

    def test_chain_tail_rejects_unauthorized_write_before_state_read(self):
        with mock.patch.object(pull,"load_state") as load, \
             mock.patch.object(pull,"prepare_migration") as prepare, \
             mock.patch.object(pull,"target_identity") as identify:
            with self.assertRaisesRegex(pull.PullMigrationError,"CONFIRMATION"):
                pull.prepare_chain_tail(PARENT,CHILD,"wrong")
        load.assert_not_called()
        prepare.assert_not_called()
        identify.assert_not_called()

    def test_chain_tail_local_target_identity_mismatch_prevents_any_write(self):
        a,b=two_tasks()
        with mock.patch.object(pull,"load_state",side_effect=[a,b]), \
             mock.patch.object(pull,"target_identity",return_value="sha256:other"), \
             mock.patch.object(pull,"prepare_migration") as prepare, \
             mock.patch.object(pull,"source_probe") as probe:
            with self.assertRaisesRegex(pull.PullMigrationError,
                                        "LOCAL_TARGET_IDENTITY_CHANGED"):
                pull.prepare_chain_tail(PARENT,CHILD,"STAGE_CHAIN_TAIL:"+PARENT+":"+CHILD)
        prepare.assert_not_called()
        probe.assert_not_called()

    def test_chain_tail_existing_destination_stays_fail_closed(self):
        # The scoped tail must reuse ordinary target preflight, which rejects
        # any destination website, system user, home path or database collision.
        a,b=two_tasks()
        with mock.patch.object(pull,"load_state",side_effect=[a,b]), \
             mock.patch.object(pull,"target_identity",return_value="sha256:cp2"), \
             mock.patch.object(pull,"source_probe",return_value={
                 "source_server_identity":"sha256:source",
                 "sites":copy.deepcopy(a["sites"][-2:])
             }), \
             mock.patch.object(pull,"target_preflight_local",
                 side_effect=pull.PullMigrationError("TARGET_ALREADY_EXISTS")) as target, \
             mock.patch.object(pull,"stage_source_runtime") as runtime, \
             mock.patch.object(pull,"save_state") as save:
            with self.assertRaisesRegex(pull.PullMigrationError,"TARGET_ALREADY_EXISTS"):
                pull.prepare_chain_tail(PARENT,CHILD,"STAGE_CHAIN_TAIL:"+PARENT+":"+CHILD)
        target.assert_called_once()
        runtime.assert_not_called()
        save.assert_not_called()

    def test_no_cutover_freeze_until_safe_final_sql_replacement_exists(self):
        for status in ("PREPARED","CUTOVER_FAILED_ROLLED_BACK"):
            with self.subTest(status=status):
                state={
                    "schema":pull.SCHEMA,"migration_id":PARENT,
                    "status":status,"source_runtime_frozen":False,
                    "sites":[{"domain":"db.example.test","site_user":"dbuser",
                              "mysql_databases":["existing_db"]}],
                }
                with mock.patch.object(pull,"load_state",return_value=state), \
                     mock.patch.object(pull,"require_mariadb_target") as dbengine, \
                     mock.patch.object(pull,"save_state") as save, \
                     mock.patch.object(pull,"freeze_old_server") as freeze, \
                     mock.patch.object(pull,"refresh_migration_assets_from_source") as probe, \
                     mock.patch.object(pull,"source_remote") as remote:
                    with self.assertRaisesRegex(
                        pull.PullMigrationError,
                        "FINAL_MYSQL_SAFE_REPLACEMENT_NOT_IMPLEMENTED",
                    ):
                        pull.cutover_migration(PARENT,"CUTOVER_PULL:"+PARENT)
                self.assertEqual(state["status"],status)
                dbengine.assert_not_called()
                save.assert_not_called()
                freeze.assert_not_called()
                probe.assert_not_called()
                remote.assert_not_called()

    def test_no_bypass_even_with_claimed_replacement_state_flag(self):
        state={
            "sites":[{"domain":"db.example.test","mysql_databases":["existing_db"]}],
            "final_database_replacement_verified":True,
            "shadow_database_swap_confirmed":True,
        }
        with self.assertRaisesRegex(
            pull.PullMigrationError,"FINAL_MYSQL_SAFE_REPLACEMENT_NOT_IMPLEMENTED"
        ):
            pull.require_non_destructive_final_db_plan(state)
        with self.assertRaisesRegex(
            pull.PullMigrationError,"FINAL_MYSQL_DATABASE_SCOPE_UNVERIFIED"
        ):
            pull.require_non_destructive_final_db_plan({"sites":[{"mysql_databases":None}]})

    def test_one_command_diagnoses_both_guards_without_state_or_db_writes(self):
        a,b=two_tasks()
        original=copy.deepcopy((a,b))
        example={
            "status":"ADVISORY_DIAGNOSTIC_ONLY",
            "evidence":{
                "verification":"NOT_A_PASS_GATE",
                "dynamic_guard":{
                    "recognized_unsafe":3,"recognized_safe":0,
                    "unsafe_branch_classes":{"DANGEROUS_SQL":100},
                    "sensitive_business_value":"MUST_NEVER_LEAK",
                },
                "schema_difference":{"source_tables":42,"target_tables":42,
                    "changed_columns":42,"private_query":"DO_NOT_OUTPUT"},
                "source_export_readback":{"attempts":1,"source_tables":42,
                    "secret":"DO_NOT_OUTPUT"}
            }
        }
        with mock.patch.object(pull,"load_state",side_effect=[a,b]), \
             mock.patch.object(pull,"target_identity",return_value="sha256:cp2"), \
             mock.patch.object(pull,"diagnose_sql_difference",
                 side_effect=[example,example]) as diagnostic, \
             mock.patch.object(pull,"save_state") as save, \
             mock.patch.object(pull,"sync_site_databases") as importer, \
             mock.patch.object(pull,"freeze_old_server") as freeze:
            result=pull.diagnose_chain_sql(PARENT,CHILD)
        self.assertEqual(result["status"],"ADVISORY_ONLY")
        self.assertFalse(result["conditional_ddl_semantics_verified"])
        self.assertFalse(result["cutover_allowed"])
        self.assertEqual([item["domain"] for item in result["sites"]],
            ["ilovem3u8.kewaro.com","unzip.kewaro.com"])
        self.assertEqual([
            c.args for c in diagnostic.call_args_list],[
            (PARENT,"ilovem3u8.kewaro.com"),
            (CHILD,"unzip.kewaro.com"),
        ])
        self.assertEqual(result["sites"][0]["dynamic_guard_counts"],{
            "recognized_unsafe":3,"recognized_safe":0,
        })
        self.assertNotIn("MUST_NEVER_LEAK",str(result))
        self.assertNotIn("DO_NOT_OUTPUT",str(result))
        self.assertEqual((a,b),original)
        save.assert_not_called()
        importer.assert_not_called()
        freeze.assert_not_called()

    def test_chain_sql_preflight_rejects_all_before_any_network_read(self):
        for mode in ("target_drift","missing_db","child_wrong_guard"):
            a,b=two_tasks()
            identity="sha256:cp2"
            if mode=="target_drift":
                identity="sha256:unknown"
            elif mode=="missing_db":
                b["sites"][6]["mysql_databases"]=[]
            else:
                b["last_sql_guard_failure"]={"reason":"OTHER"}
            with self.subTest(mode=mode), \
                 mock.patch.object(pull,"load_state",side_effect=[a,b]), \
                 mock.patch.object(pull,"target_identity",return_value=identity), \
                 mock.patch.object(pull,"diagnose_sql_difference") as diag, \
                 mock.patch.object(pull,"source_remote") as remote:
                with self.assertRaises(pull.PullMigrationError):
                    pull.diagnose_chain_sql(PARENT,CHILD)
            diag.assert_not_called()
            remote.assert_not_called()

    def test_chain_sql_invalid_counter_never_leaks_private_values(self):
        a,b=two_tasks()
        with mock.patch.object(pull,"load_state",side_effect=[a,b]), \
             mock.patch.object(pull,"target_identity",return_value="sha256:cp2"), \
             mock.patch.object(pull,"diagnose_sql_difference",return_value={
                "status":"ADVISORY_DIAGNOSTIC_ONLY",
                "evidence":{"dynamic_guard":{"recognized_unsafe":"SQL PRIVATE"}}
             }):
            with self.assertRaisesRegex(pull.PullMigrationError,"COUNTERS_UNVERIFIED"):
                pull.diagnose_chain_sql(PARENT,CHILD)

    def test_cli_does_not_call_remote_or_mutate(self):
        a,b=two_tasks()
        with mock.patch.object(pull,"load_state",side_effect=[a,b]), \
             mock.patch.object(pull,"save_state") as save, \
             mock.patch.object(pull,"source_remote") as remote, \
             mock.patch.object(pull,"sync_site_databases") as importer, \
             mock.patch.object(pull,"freeze_old_server") as freeze:
            plan=pull.chain_recovery_scope(PARENT,CHILD)
        self.assertEqual(plan["staged_count"],13)
        save.assert_not_called()
        remote.assert_not_called()
        importer.assert_not_called()
        freeze.assert_not_called()

if __name__=="__main__":
    unittest.main()
