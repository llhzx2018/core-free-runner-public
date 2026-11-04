"""Synthetic P07 CP2 three-pending-sites pre-cutover readiness (no SSH/DB/HTTP)."""
import contextlib
import hashlib
import json
import os
import tempfile
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
        def classify(site,dbs):
            calls.append((site["domain"],len(dbs)))
            return "SOURCE_DECLARED_DB_REGISTERED_IN_CP2"
        with mock.patch.object(m,"status_scope",return_value=items), \
             mock.patch.object(m,"panel_db_candidate",side_effect=classify):
            output=m.scan(Base,Smoke)
        self.assertEqual(len(output),3)
        self.assertEqual(set(DOMAINS),{x[0] for x in output})
        self.assertEqual(calls,[
            (DOMAINS[0],2),(DOMAINS[1],1),(DOMAINS[2],1)])

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

    def test_site_db_vs_isolated_scratch_inventory(self):
        site=old_site(DOMAINS[0])
        site["mysql_databases"]=["main-db"]
        # A scratch DB is not required to be registered with the site.
        self.assertEqual(m.panel_db_candidate(site,["main-db"]),
                         "SOURCE_DECLARED_DB_REGISTERED_IN_CP2")
        self.assertEqual(m.panel_db_candidate(site,["main-db","other"]),
                         "ADDITIONAL_CP2_REGISTERED_DB_REVIEW_REQUIRED")
        self.assertEqual(m.panel_db_candidate(site,[]),
                         "SOURCE_DECLARED_DB_NOT_REGISTERED_IN_CP2")
        self.assertEqual(m.panel_db_candidate(site,["other"]),
                         "SOURCE_CP2_SITE_DB_IDENTITY_DIFFERENCE")
        self.assertEqual(m.panel_db_candidate(site,["main-db","main-db"]),
                         "CP2_SITE_DB_DUPLICATE")
        self.assertEqual(m.panel_db_candidate(site,["main-db",""]),
                         "CP2_SITE_DB_INVENTORY_INVALID")
        site["mysql_databases"]=[]
        self.assertEqual(m.panel_db_candidate(site,["main-db"]),
                         "SOURCE_SITE_DB_DECLARATION_EMPTY")
        site["mysql_databases"]=["main-db","main-db"]
        self.assertEqual(m.panel_db_candidate(site,["main-db"]),
                         "SOURCE_SITE_DB_DECLARATION_DUPLICATE")

    def test_unregistered_www3_db_not_falsely_accepted(self):
        site=old_site(DOMAINS[2])
        site["mysql_databases"]=["real-site-db"]
        self.assertEqual(m.panel_db_candidate(site,[]),
                         "SOURCE_DECLARED_DB_NOT_REGISTERED_IN_CP2")


    def www3_recovery_fixture(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root=Path(td.name)
        transactions=root/"target-transactions"
        transactions.mkdir(mode=0o700)
        folder=transactions/"www3-source-rule-connection-v1"
        folder.mkdir(mode=0o700)
        wp=root/"wp-config.php"
        original=b"<?php define('DB_NAME','original');"
        candidate=b"<?php define('DB_NAME','candidate');"
        wp.write_bytes(candidate)
        wp.chmod(0o600)
        def write_private(path,content):
            path.write_bytes(content)
            path.chmod(0o600)
        write_private(folder/"original.php",original)
        write_private(folder/"candidate.php",candidate)
        journal={
            "schema":"p07.www3.config-connection.v1",
            "target_identity":"target-identity",
            "config_path":str(wp),
            "status":"CONNECTED_NOT_CUTOVER_READY",
            "cutover_allowed":False,
            "database_writes":False,
            "migration_state_promoted":False,
            "original_sha256":hashlib.sha256(original).hexdigest(),
            "candidate_sha256":hashlib.sha256(candidate).hexdigest()
        }
        def receipt(name,data):
            p=transactions/("www3-hex-scratch-"+name+".json")
            write_private(p,json.dumps(data).encode())
            return p
        common={
          "migration_id":"current-tail","domain":"www3.m3u8.one",
          "source_database":"original","target_server_identity":"target-identity",
        }
        receipt("candidate",{
          **common,"schema":"p07.www3.source-rule-candidate.v1",
          "status":"VERIFIED_STATIC_COPY_NOT_ACTIVATED",
          "scratch_database":"candidate",
          "cutover_allowed":False,"website_activated":False,
          "original_database_modified":False
        })
        receipt("quarantine",{
          **common,"schema":"p07.www3.quarantined-static-copy.v1",
          "scratch_database":"earlier"
        })
        write_private(folder/"journal.json",json.dumps(journal).encode())
        source={"migration_id":"current-tail","mysql_databases":["original"]}
        panel={"mysql_databases":["candidate","earlier"]}
        return source,panel,transactions,wp,journal

    def test_www3_current_candidate_and_previous_scratch_relation(self):
        source,panel,transactions,wp,_=self.www3_recovery_fixture()
        result=m.candidate_relation(source,panel,transactions,wp,
                                    "target-identity",os.getuid())
        self.assertEqual(result["SOURCE_DB_IN_CP2_PANEL"],"NO")
        self.assertEqual(result["CANDIDATE_DB_IN_CP2_SITE_PANEL"],"YES")
        self.assertEqual(result["OLD_SCRATCH_IN_CP2_SITE_PANEL"],"YES")
        self.assertEqual(result["UNCLASSIFIED_CP2_SITE_DB_COUNT"],0)
        self.assertEqual(result["CURRENT_CONFIG_READBACK"],"CANDIDATE_MATCH")
        self.assertEqual(result["JOURNAL_STATUS"],"CONNECTED_NOT_CUTOVER_READY")
        self.assertEqual(result["SOURCE_TARGET_DB_PARITY"],"NOT_VERIFIED")
        self.assertEqual(result["CUTOVER_ALLOWED"],"NO")
        self.assertNotIn("original",repr(result.values()))
        self.assertNotIn("candidate",repr(result.values()))

    def test_www3_journal_hash_and_guard_fail_closed(self):
        source,panel,transactions,wp,journal=self.www3_recovery_fixture()
        folder=transactions/"www3-source-rule-connection-v1"
        path=folder/"journal.json"
        journal["cutover_allowed"]=True
        path.write_bytes(json.dumps(journal).encode())
        with self.assertRaisesRegex(m.Block,"JOURNAL_IDENTITY_OR_GUARD"):
            m.candidate_relation(source,panel,transactions,wp,
                                 "target-identity",os.getuid())
        journal["cutover_allowed"]=False
        path.write_bytes(json.dumps(journal).encode())
        (folder/"candidate.php").write_bytes(b"tampered")
        with self.assertRaisesRegex(m.Block,"BACKUP_HASH_CHANGED"):
            m.candidate_relation(source,panel,transactions,wp,
                                 "target-identity",os.getuid())

    def test_www3_unrecognized_current_config_and_receipt_fail_closed(self):
        source,panel,transactions,wp,_=self.www3_recovery_fixture()
        wp.write_bytes(b"<?php define('DB_NAME','unexpected');")
        with self.assertRaisesRegex(m.Block,"CONFIG_BYTES_OUTSIDE_RECOVERY"):
            m.candidate_relation(source,panel,transactions,wp,
                                 "target-identity",os.getuid())
        (transactions/"www3-hex-scratch-candidate.json").unlink()
        wp.write_bytes((transactions/"www3-source-rule-connection-v1"/"candidate.php").read_bytes())
        with self.assertRaisesRegex(m.Block,"UNIQUE_CANDIDATE_RECEIPT"):
            m.candidate_relation(source,panel,transactions,wp,
                                 "target-identity",os.getuid())

    def test_www3_symlinked_private_receipt_never_followed(self):
        source,panel,transactions,wp,_=self.www3_recovery_fixture()
        path=transactions/"www3-hex-scratch-candidate.json"
        target=transactions/"outside.json"
        path.rename(target)
        path.symlink_to(target)
        with self.assertRaisesRegex(m.Block,"WWW3_PRIVATE_FILE_UNSAFE"):
            m.candidate_relation(source,panel,transactions,wp,
                                 "target-identity",os.getuid())

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
        self.assertIn("SOURCE_TARGET_DB_PARITY",source)
        self.assertIn("SITE_FILES_DB_CRON_DNS_WRITES=NONE",source)
    def test_invalid_arg_first(self):
        with mock.patch.object(sys,"argv",["operator","--migrate"]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"pinned") as x:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_PENDING_THREE_READONLY_ARG_REQUIRED"):
                m.main()
            x.assert_not_called()
if __name__=="__main__":
    unittest.main()
