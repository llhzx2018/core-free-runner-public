"""Synthetic P07 CP2 three-pending-sites pre-cutover readiness (no SSH/DB/HTTP)."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("p07_three_pending",
 HERE/"p07-pending-three-runtime-readonly.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
MIDS={
 "ORIGINAL17":"pull-20261101T045943Z-923729a1",
 "LEGACY9":"pull-20261101T052411Z-35663c25",
 "LAST2":"pull-20261102T005644Z-7178c7d5",
}
DOMAINS=[row[0] for row in m.THREE]
def old_site(domain,status="PENDING",user="site"):
    return {"domain":domain,"stage_status":status,"site_user":user,
        "runtime":{"type":"php","version":"8.4"}}
class Base:
    JOBS=tuple((name,mid,{"ORIGINAL17":17,"LEGACY9":9,"LAST2":2}[name])
               for name,mid in MIDS.items())
    SCHEMA="vf-server-ops.server-migration.target-pull.v1"
    EXPECTED_STAGED=set("site"+str(i)+".example.test" for i in range(14))
    EXPECTED_PENDING=set(DOMAINS)
    allrecords={}
    @classmethod
    def secure_state(cls,path):
        return cls.allrecords[path.parent.name]
class Smoke:
    PHP=m.re.compile("[0-9]+\\.[0-9]+$")
    @staticmethod
    def inventory():
        return {d:[{"domain":d,"site_user":"site","runtime":{
            "type":"php","version":"8.4"},
            "mysql_databases":(["real-db","scratch-db"] if d==DOMAINS[0]
                               else ["real-db"])}] for d in DOMAINS}
    @staticmethod
    def safe_entry_metadata(row):
        return {"index.php":True,"index.html":False}
    @staticmethod
    def vhost(domain):return "FOUND",["/run/php/instance.sock"]
    @staticmethod
    def service(service):return "ACTIVE"
    @staticmethod
    def backend_status(*args):return "UNIX_POOL_AND_SOCKET_CONFIRMED"
def fixture():
    staged=sorted(Base.EXPECTED_STAGED)
    # The original17 owns all sites, the nine-site child has 6 staged
    # and 3 pending, and the independent two-site tail has 1 staged +1 pending.
    original=[old_site(x,"PULLED_STAGED") for x in staged[:7]]+[
        old_site(x) for x in staged[7:]]+[old_site(x) for x in DOMAINS]
    legacy=[old_site(x,"PULLED_STAGED") for x in staged[7:13]]+[
        old_site(DOMAINS[1]),old_site(staged[13]),old_site(DOMAINS[2])]
    tail=[old_site(staged[13],"PULLED_STAGED"),old_site(DOMAINS[2])]
    assert len(original)==17 and len(legacy)==9 and len(tail)==2
    out={}
    for key,mid,n in Base.JOBS:
        rows={"ORIGINAL17":original,"LEGACY9":legacy,"LAST2":tail}[key]
        out[key]={
          "schema":Base.SCHEMA,"migration_id":mid,
          "status":"PREPARE_FAILED","sites":rows,
          "source_runtime_frozen":False,"target_runtime_activated":False,
          "dns_changed_by_p07":False,"source_delete_allowed":False,
          "existing_target_overwrite_allowed":False,
          "cutover_prohibited":key!="ORIGINAL17",
          "target_server_identity":"TARGETX",
          "partial_parent_migration_id":(
            None if key=="ORIGINAL17" else MIDS["ORIGINAL17"]),
        }
    return out
class Tests(unittest.TestCase):
    def test_classify_pending_three_static_config_only(self):
        obj=old_site(DOMAINS[0])
        row=Smoke.inventory()[DOMAINS[0]][0]
        outcome=m.assess(Smoke,obj,row)
        self.assertEqual(outcome["SITE_FILES_ENTRY_PRESENT"],"YES")
        self.assertEqual(outcome["PHP_OR_OTHER_RUNTIME_MATCH"],"YES")
        self.assertEqual(outcome["NGINX_VHOST"],"FOUND")
        self.assertEqual(outcome["FPM_SERVICE"],"ACTIVE")
        self.assertEqual(outcome["APPLICATION_DB_CONFIG_MAPPING"],"NOT_VERIFIED")
        self.assertEqual(outcome["HTTP_APP_FUNCTIONALITY"],"NOT_TESTED")
    def test_missing_entry_and_wrong_runtime_remain_review(self):
        class Missing(Smoke):
            @staticmethod
            def safe_entry_metadata(row):return {"index.php":False}
        site=old_site(DOMAINS[1])
        target={"runtime":{"type":"php","version":"8.3"},"site_user":"site"}
        result=m.assess(Missing,site,target)
        self.assertEqual(result["SITE_FILES_ENTRY_PRESENT"],"NO")
        self.assertEqual(result["PHP_OR_OTHER_RUNTIME_MATCH"],"NO")
        self.assertEqual(result["LOCAL_FILES_VHOST_FPM_EVIDENCE"],"GAP")
        class RobotsOnly(Smoke):
            @staticmethod
            def safe_entry_metadata(row):
                return {"index.php":False,"index.html":False,"robots.txt":True}
            @staticmethod
            def service(service):return "UNKNOWN"
        target["runtime"]["version"]="8.4"
        noindex=m.assess(RobotsOnly,site,target)
        self.assertEqual(noindex["SITE_FILES_ENTRY_PRESENT"],"NO")
        self.assertEqual(noindex["LOCAL_FILES_VHOST_FPM_EVIDENCE"],"GAP")
        class DeadFpm(Smoke):
            @staticmethod
            def service(service):return "NOT_ACTIVE"
        bad=m.assess(DeadFpm,site,target)
        self.assertEqual(bad["LOCAL_FILES_VHOST_FPM_EVIDENCE"],"GAP")
    def test_scan_three_records_is_readonly_scoped(self):
        items={dom:({"ilovem3u8.kewaro.com":"ORIGINAL17",
                     "unzip.kewaro.com":"LEGACY9",
                     "www3.m3u8.one":"LAST2"}[dom],old_site(dom))
               for dom in DOMAINS}
        calls=[]
        def classify(site,expected,dbs,label):
            calls.append((site["domain"],expected,label))
            return "PANEL_DB_STRUCTURAL_CANDIDATE_ONLY"
        with mock.patch.object(m,"status_scope",return_value=items), \
             mock.patch.object(m,"panel_db_candidate",side_effect=classify):
            output=m.scan(Base,Smoke)
        self.assertEqual(len(output),3)
        self.assertEqual(set(DOMAINS),{x[0] for x in output})
        self.assertEqual(calls,[
            (DOMAINS[0],2,"ORIGINAL17"),(DOMAINS[1],1,"LEGACY9"),
            (DOMAINS[2],1,"LAST2")])

    def test_current_17_site_scope_and_independent_tail_owner(self):
        records=fixture()
        Base.allrecords={MIDS[key]:record for key,record in records.items()}
        items=m.status_scope(Base)
        self.assertEqual(len(items),17)
        self.assertEqual(set(items),Base.EXPECTED_STAGED|Base.EXPECTED_PENDING)
        self.assertEqual({d for d,(label,row) in items.items()
                          if row["stage_status"]=="PENDING"},Base.EXPECTED_PENDING)
        self.assertEqual(items[DOMAINS[2]][0],"LAST2")
        self.assertEqual(items[DOMAINS[1]][0],"LEGACY9")
        self.assertEqual(items[DOMAINS[0]][0],"ORIGINAL17")

    def test_changed_safety_state_or_tail_parent_is_blocked(self):
        records=fixture()
        Base.allrecords={MIDS[key]:record for key,record in records.items()}
        records["ORIGINAL17"]["source_delete_allowed"]=True
        with self.assertRaisesRegex(m.Block,"MIGRATION_ID_OR_SAFETY_BOUNDARY_CHANGED"):
            m.status_scope(Base)
        records["ORIGINAL17"]["source_delete_allowed"]=False
        records["LAST2"]["partial_parent_migration_id"]=MIDS["LEGACY9"]
        with self.assertRaisesRegex(m.Block,"PARENT_MIGRATION_CHAIN_CHANGED"):
            m.status_scope(Base)

    def test_panel_db_count_and_identity_gaps_remain_unverified(self):
        site=old_site(DOMAINS[1])
        self.assertEqual(m.panel_db_candidate(site,1,[],"LEGACY9"),
                         "CP2_DATABASE_COUNT_GAP")
        self.assertEqual(m.panel_db_candidate(site,1,["db","db"],"LEGACY9"),
                         "CP2_DATABASE_DUPLICATE")
        site["mysql_databases"]=["expected"]
        self.assertEqual(m.panel_db_candidate(site,1,["different"],"LEGACY9"),
                         "SOURCE_TARGET_DB_NAME_DIFFERENCE")
        self.assertEqual(m.panel_db_candidate(site,1,["expected"],"LEGACY9"),
                         "PANEL_DB_STRUCTURAL_CANDIDATE_ONLY")
        self.assertEqual(m.panel_db_candidate(old_site(DOMAINS[0]),2,
                         ["original","scratch"],"ORIGINAL17"),
                         "PANEL_DB_STRUCTURAL_CANDIDATE_ONLY")

    def test_operator_never_opens_http_or_sql_or_copies_files(self):
        source=(HERE/"p07-pending-three-runtime-readonly.py").read_text()
        for token in ("source_remote(","pull_path(","cloudpanel.add_database(",
                      "cloudpanel.export_database(","isolated_import(",
                      "subprocess.run([\"curl\"", "head_local(", "response_headers_local(",
                      "cutover_migration(", "freeze_old_server(", "CREATE DATABASE",
                      "UPDATE ", "INSERT INTO", "DELETE FROM"):
            self.assertNotIn(token,source)
        self.assertIn("DATABASE_SQL_QUERIES_AND_WRITES=NONE",source)
        self.assertIn("APPLICATION_DB_CONFIG_MAPPING",source)
        self.assertIn("CUTOVER_ALLOWED=NO",source)
    def test_invalid_arg_first(self):
        with mock.patch.object(sys,"argv",["operator","--migrate"]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"pinned") as x:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_PENDING_THREE_READONLY_ARG_REQUIRED"):
                m.main()
            x.assert_not_called()
if __name__=="__main__":
    unittest.main()
