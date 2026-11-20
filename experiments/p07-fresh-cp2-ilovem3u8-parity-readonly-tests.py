"""P07 clean CP2 failed-import incident: nonmutating/read-only boundary tests."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("p07_cp2_incident",
    HERE/"p07-fresh-cp2-ilovem3u8-parity-readonly.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def state():
    rows=[{"domain":"site"+str(i),"stage_status":"PULLED_STAGED"} for i in range(7)]
    rows.append({"domain":m.DOMAIN,"stage_status":"PENDING"})
    rows.extend({"domain":"pending"+str(i),"stage_status":"PENDING"} for i in range(9))
    return {
       "status":"PREPARE_FAILED",
       "schema":"vf-server-ops.server-migration.target-pull.v1",
       "migration_id":m.INCIDENT_MID,
       "last_sql_guard_failure":{"reason":"CONDITIONAL_DDL",
            "flow":"SQL_GUARD_FLOW_V1 safe_assignment=0 outcome=UNSAFE_BRANCH"},
       "source_runtime_frozen":False,
       "target_runtime_activated":False,
       "dns_changed_by_p07":False,
       "source_delete_allowed":False,
       "existing_target_overwrite_allowed":False,
       "source_runtime_path":
          "/var/lib/vf-server-ops/pull-source/"+m.INCIDENT_MID+"/runtime",
       "sites":rows}
def pair(data):
    return types.SimpleNamespace(
       STATE_ROOT=Path("/root"),
       private_state=lambda _:data)
class Tests(unittest.TestCase):
    def test_import_pinned_only_no_actions(self):
        x=m.load_pair()
        self.assertEqual(x.ORIGINAL17,m.INCIDENT_MID)
        self.assertEqual(x.SITES,((m.DOMAIN,m.INCIDENT_MID,17,7,42),))
        self.assertEqual(x.ENGINE_BLOB,"71fb59ad7d005b88e39cbeed4b3302c7f313bd06")
    def test_exact_owner_incident_accepts_readonly_proof(self):
        m.check_incident(pair(state()))
    def test_guard_outcome_must_be_failed_conditional(self):
        s=state()
        s["last_sql_guard_failure"]={"reason":"UNKNOWN"}
        with self.assertRaisesRegex(m.Block,"EXPECTED_CLEAN_CP2_GUARD_INCIDENT_MISSING"):
            m.check_incident(pair(s))
        s["last_sql_guard_failure"]={"reason":"CONDITIONAL_DDL"}
        s["status"]="PREPARED"
        with self.assertRaisesRegex(m.Block,"EXPECTED_CLEAN_CP2_GUARD_INCIDENT_MISSING"):
            m.check_incident(pair(s))
    def test_no_overwrite_and_no_cutover_marker(self):
        s=state();s["existing_target_overwrite_allowed"]=True
        with self.assertRaisesRegex(m.Block,"MIGRATION_SAFETY_BOUNDARY_CHANGED"):
            m.check_incident(pair(s))
        s=state();s["source_runtime_frozen"]=True
        with self.assertRaisesRegex(m.Block,"MIGRATION_SAFETY_BOUNDARY_CHANGED"):
            m.check_incident(pair(s))
        s=state();s["cutover_prohibited"]=True
        with self.assertRaisesRegex(m.Block,"CUTOVER_BOUNDARY_CHANGED"):
            m.check_incident(pair(s))
    def test_7_staged_only_and_domain_required(self):
        s=state();s["sites"][7]["stage_status"]="PULLED_STAGED"
        with self.assertRaisesRegex(m.Block,"CLEAN_CP2_7_STAGED_10_PENDING_CHANGED"):
            m.check_incident(pair(s))
        s=state();s["sites"][7]["domain"]="wrong.example"
        with self.assertRaisesRegex(m.Block,"CLEAN_CP2_7_STAGED_10_PENDING_CHANGED"):
            m.check_incident(pair(s))
    def test_source_runtime_not_borrowed_from_old_cp2(self):
        s=state();s["source_runtime_path"]=s["source_runtime_path"].replace(
             m.INCIDENT_MID,"pull-20261028T103425Z-98050c76")
        with self.assertRaisesRegex(m.Block,"SOURCE_TEMPORARY_RUNTIME_IDENTITY_CHANGED"):
            m.check_incident(pair(s))
    def test_cli_rejects_resume_before_sql(self):
        with mock.patch.object(sys,"argv",["tool","--resume"]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"load_pair") as loader:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_CLEAN_CP2_READONLY_ONLY"):
                m.main()
            loader.assert_not_called()
    def test_script_contains_no_mutating_operations(self):
        code=(HERE/"p07-fresh-cp2-ilovem3u8-parity-readonly.py").read_text()
        for word in ("sync_site_databases(","target_create_database_local(",
                     "source_export_database(","cloudpanel.export_database(",
                     "resume_prepare_migration(","cutover_migration(",
                     "CREATE DATABASE","ALTER TABLE","DROP DATABASE",
                     "GRANT ","UPDATE ","DELETE FROM"):
            self.assertNotIn(word,code)
        for marker in ("SOURCE_BUSINESS_DB_WRITES=NONE","TARGET_DB_WRITES=NONE",
                       "SITE_CONFIG_AND_DNS_WRITES=NONE",
                       "SQL_CONDITIONAL_DDL_SEMANTICS_VERIFIED=NO",
                       "CUTOVER_ALLOWED=NO"):
            self.assertIn(marker,code)
if __name__=="__main__":unittest.main()
