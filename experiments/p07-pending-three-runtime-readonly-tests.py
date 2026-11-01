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
 "ORIGINAL17":"pull-20261028T103425Z-98050c76",
 "LEGACY9":"pull-20261031T094144Z-d045fa5a",
 "LAST2":"pull-20261031T095604Z-edae3c44",
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
            "mysql_databases":["real-db"]}] for d in DOMAINS}
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
    a=[]
    for key,mid,n in Base.JOBS:
        rows=[]
        for name in Base.EXPECTED_STAGED:
            rows.append(old_site(name,"PULLED_STAGED"))
        if key=="ORIGINAL17":
            rows=rows[:7]+[old_site(DOMAINS[0])]+[old_site("filler.example.test","PULLED_STAGED")]*9
        if key=="LEGACY9":
            rows=[old_site("filler.example.test","PULLED_STAGED")]*6+[old_site(DOMAINS[1])]+[old_site("filler.example.test","PULLED_STAGED")]*2
        if key=="LAST2":
            rows=[old_site("updates.kewaro.com","PULLED_STAGED"),old_site(DOMAINS[2])]
        obj={
          "schema":Base.SCHEMA,"migration_id":mid,
          "status":"PREPARE_FAILED","sites":rows,
          "source_runtime_frozen":False,"target_runtime_activated":False,
          "dns_changed_by_p07":False,"source_delete_allowed":False,
          "existing_target_overwrite_allowed":False,
          "cutover_prohibited":key!="ORIGINAL17",
          "target_server_identity":"TARGETX",
          "partial_parent_migration_id":
            None if key=="ORIGINAL17" else
            MIDS["ORIGINAL17"] if key=="LEGACY9" else MIDS["LEGACY9"],
        }
        a.append((key,obj))
    return dict(a)
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
    def test_scan_three_records_is_readonly_scoped(self):
        items={dom:({"ilovem3u8.kewaro.com":"ORIGINAL17",
                   "unzip.kewaro.com":"LEGACY9",
                   "www3.m3u8.one":"LAST2"}[dom],old_site(dom))
               for dom in DOMAINS}
        calls=[]
        def scratch(site,mid,dirname,status,dbs):
            calls.append((site["domain"],mid,dirname,status))
            return "ISOLATED_SOURCE_SNAPSHOT" if dirname else "EXISTING_CP2_DB"
        with mock.patch.object(m,"status_scope",return_value=items), \
             mock.patch.object(m,"scratch_link",side_effect=scratch):
            output=m.scan(Base,Smoke)
        self.assertEqual(len(output),3)
        self.assertEqual(set(DOMAINS),{x[0] for x in output})
        self.assertEqual(calls[0][0],"ilovem3u8.kewaro.com")
        self.assertEqual(calls[1][0],"unzip.kewaro.com")
        self.assertEqual(calls[2][0],"www3.m3u8.one")
        self.assertEqual(calls[0][1],MIDS["ORIGINAL17"])
        self.assertEqual(calls[2][1],MIDS["LAST2"])
    def test_failed_safe_state_does_not_trigger_sql(self):
        records=fixture()
        # Replace historical fixture with actual full unique 17-site scope.
        a=[]
        staged=sorted(Base.EXPECTED_STAGED)
        records["ORIGINAL17"]["sites"]=[old_site(x,"PULLED_STAGED") for x in staged[:7]]+[old_site(DOMAINS[0])]+[old_site(x,"PULLED_STAGED") for x in staged[7:]]
        records["ORIGINAL17"]["sites"]+= [old_site("other1.example.test","PULLED_STAGED"),old_site("other2.example.test","PULLED_STAGED")]
        records["LEGACY9"]["sites"]=[old_site("other1.example.test","PULLED_STAGED")]*6+[old_site(DOMAINS[1])]+[old_site("other2.example.test","PULLED_STAGED")]*2
        records["LAST2"]["sites"]=[old_site("updates.kewaro.com","PULLED_STAGED"),old_site(DOMAINS[2])]
        # The parser must reject incorrect aggregate domain identities.
        Base.allrecords={MIDS[key]:record for key,record in records.items()}
        with self.assertRaisesRegex(m.Block,"17_SITE_FINAL_SCOPE_CHANGED"):
            m.status_scope(Base)
        records["ORIGINAL17"]["source_delete_allowed"]=True
        with self.assertRaisesRegex(m.Block,"MIGRATION_ID_OR_SAFETY_BOUNDARY_CHANGED"):
            m.status_scope(Base)
    def test_unsafe_isolated_registration_fails_closed(self):
        site=old_site(DOMAINS[1])
        with self.assertRaisesRegex(m.Block,"UNZIP_REGISTERED_DB_SCOPE_CHANGED"):
            m.scratch_link(site,MIDS["LEGACY9"],None,None,[])
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
