"""Synthetic read-only source/CP2 paired DB parity test, no servers."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest import mock

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location("p07_twopending",
    ROOT/"p07-two-pending-live-db-parity.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
def sha(x):
    return hashlib.sha256(x.encode("ascii")).hexdigest()
def payload(mode,tablename="a",count=2,hashvalue="f"*64):
    name=sha(tablename)
    col=sha("col")
    lines=["MODE="+mode,"SCANNED_TABLES=1","SCANNED_COLUMNS=1",
           "SCANNED_ROWS="+str(count),
           "ROW_FINGERPRINTS="+json.dumps({name:[count,hashvalue,"a"*64,
                                                 {col:"b"*64}]}),
           "READ_ONLY_TRANSACTION=YES",
           "CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY=YES"]
    return "\n".join(lines)+"\n"
def state(domain,mid,length,index,db="db1"):
    sites=[{"domain":"example.test","stage_status":"PULLED_STAGED"}
           for _ in range(length)]
    sites[index]={"domain":domain,"stage_status":"PENDING",
                  "site_user":"user1","mysql_databases":[db]}
    return {
       "schema":"vf-server-ops.server-migration.target-pull.v1",
       "migration_id":mid,"status":"PREPARE_FAILED","cutover_prohibited":(mid==m.LEGACY9),
       "source_runtime_frozen":False,"dns_changed_by_p07":False,
       "source_delete_allowed":False,"existing_target_overwrite_allowed":False,
       "target_server_identity":"TARGETX",
       "source_runtime_path":"/var/lib/vf-server-ops/pull-source/"+mid+"/runtime",
       "source":{"id":"source-test"},"sites":sites,
       "partial_parent_migration_id":m.ORIGINAL17 if mid==m.LEGACY9 else None}
class FakeMigration:
    @staticmethod
    def target_identity():return "TARGETX"
class Inventory:
    @staticmethod
    def build_manifest(_):return {"discovery_source":"cloudpanel_db+vhost",
      "sites":[{"domain":"unzip.kewaro.com","site_user":"user1","mysql_databases":["db2"]},
               {"domain":"ilovem3u8.kewaro.com","site_user":"user1","mysql_databases":["db3"]}]}
class Tests(unittest.TestCase):
    def test_parsed_defensive_worker_output(self):
        values, mp=m.parsed(payload("SOURCE"),"SOURCE")
        self.assertEqual(values["SCANNED_ROWS"],2)
        self.assertEqual(len(mp),1)
        for text in (payload("SOURCE")+"password=secret\n",
                     payload("SOURCE").replace("MODE=SOURCE","MODE=TARGET"),
                     payload("SOURCE").replace('"b"*64',''),
                     payload("SOURCE").replace("SCANNED_ROWS=2","SCANNED_ROWS=999")):
            if text==payload("SOURCE"):continue
            with self.assertRaises(m.Block):m.parsed(text,"SOURCE")
        bad=payload("SOURCE").replace("f"*64,"x"*64)
        with self.assertRaises(m.Block):m.parsed(bad,"SOURCE")
    def test_exact_site_scopes_and_not_ready(self):
        for domain,mid,length,idx,count in m.SITES:
            rows=state(domain,mid,length,idx)
            with mock.patch.object(m,"private_state",return_value=rows):
                result=m.preflight(FakeMigration,Inventory,domain,mid,length,idx,count)
            self.assertEqual(result[1],"db1")
            self.assertIn(result[2],("db2","db3"))
            self.assertEqual(result[3],
                "/var/lib/vf-server-ops/pull-source/"+mid+"/runtime")
        # The older original-seventeen has cutover_prohibited=False
        # (bool(remainder_parent)), whereas the newer child has True.
        # Keep this exact historical-state invariant without enabling cutover.
        old=state("ilovem3u8.kewaro.com",m.ORIGINAL17,17,7)
        self.assertIs(old["cutover_prohibited"],False)
        with mock.patch.object(m,"private_state",return_value=old):
            self.assertEqual(m.preflight(
                FakeMigration,Inventory,"ilovem3u8.kewaro.com",
                m.ORIGINAL17,17,7,42)[2],"db3")
        old["cutover_prohibited"]=True
        with mock.patch.object(m,"private_state",return_value=old):
            with self.assertRaisesRegex(m.Block,"MIGRATION_SAFETY"):
                m.preflight(FakeMigration,Inventory,"ilovem3u8.kewaro.com",
                            m.ORIGINAL17,17,7,42)
        rows=state("unzip.kewaro.com",m.LEGACY9,9,6)
        rows["cutover_prohibited"]=False
        with mock.patch.object(m,"private_state",return_value=rows):
            with self.assertRaisesRegex(m.Block,"MIGRATION_SAFETY"):
                m.preflight(FakeMigration,Inventory,
                            "unzip.kewaro.com",m.LEGACY9,9,6,12)
        rows=state("unzip.kewaro.com",m.LEGACY9,9,6)
        rows["existing_target_overwrite_allowed"]=True
        with mock.patch.object(m,"private_state",return_value=rows):
            with self.assertRaisesRegex(m.Block,"MIGRATION_SAFETY"):
                m.preflight(FakeMigration,Inventory,"unzip.kewaro.com",m.LEGACY9,9,6,12)
        rows=state("unzip.kewaro.com",m.LEGACY9,9,6)
        class EmptyInventory:
            @staticmethod
            def build_manifest(_):return {"discovery_source":"cloudpanel_db+vhost",
             "sites":[{"domain":"unzip.kewaro.com","site_user":"user1","mysql_databases":[]}]}
        with mock.patch.object(m,"private_state",return_value=rows):
            self.assertIsNone(m.preflight(
                FakeMigration,EmptyInventory,"unzip.kewaro.com",m.LEGACY9,9,6,12)[2])
    def test_legacy_guard_failure_does_not_print_private_state(self):
        old=state("ilovem3u8.kewaro.com",m.ORIGINAL17,17,7)
        old.pop("cutover_prohibited")
        old["source"]={"private_secret":"SENSITIVE_SOURCE"}
        out=io.StringIO()
        with mock.patch.object(m,"private_state",return_value=old), \
             contextlib.redirect_stdout(out):
            with self.assertRaisesRegex(m.Block,"MIGRATION_SAFETY"):
                m.preflight(FakeMigration,Inventory,"ilovem3u8.kewaro.com",
                            m.ORIGINAL17,17,7,42)
        data=out.getvalue()
        self.assertIn("FAILED_STATE_GUARDS=CUTOVER_PROHIBITED_MARKER",data)
        self.assertIn("ORIGINAL_CUTOVER_MARKER=MISSING",data)
        self.assertNotIn("SENSITIVE_SOURCE",data)
        self.assertNotIn("TARGETX",data)
        self.assertNotIn("user1",data)
        old["cutover_prohibited"]=False
        old["source_delete_allowed"]=True
        old["existing_target_overwrite_allowed"]=True
        out=io.StringIO()
        with mock.patch.object(m,"private_state",return_value=old), \
             contextlib.redirect_stdout(out):
            with self.assertRaisesRegex(m.Block,"MIGRATION_SAFETY"):
                m.preflight(FakeMigration,Inventory,"ilovem3u8.kewaro.com",
                            m.ORIGINAL17,17,7,42)
        self.assertIn("SOURCE_DELETE_FORBIDDEN",out.getvalue())
        self.assertIn("TARGET_OVERWRITE_FORBIDDEN",out.getvalue())
        self.assertNotIn("ORIGINAL_CUTOVER_MARKER=",out.getvalue())

    def test_equal_and_changed_real_boundaries(self):
        domain,mid,length,idx,expected=m.SITES[0]
        origin=state(domain,mid,length,idx)
        old=payload("SOURCE",count=3,hashvalue="a"*64)
        local=payload("TARGET",count=2,hashvalue="b"*64)
        class Remote:
            @staticmethod
            def target_identity():return "TARGETX"
            @staticmethod
            def source_remote(_src,cmd,**kw):
                self.assertIn("PYTHONDONTWRITEBYTECODE=1",cmd)
                self.assertIn("source",cmd)
                self.assertNotIn("db2",cmd)
                return subprocess.CompletedProcess([],0,old,"")
        out=io.StringIO()
        with mock.patch.object(m,"preflight",
            return_value=(origin,"db1","db2",origin["source_runtime_path"])), \
             mock.patch.object(m.subprocess,"run",
               return_value=subprocess.CompletedProcess([],0,local,"")), \
             mock.patch.object(m,"parsed",side_effect=lambda text,mode:
               ({"SCANNED_TABLES":12,"SCANNED_COLUMNS":12,
                 "SCANNED_ROWS":3 if mode=="SOURCE" else 2},
                {sha("a"):[3 if mode=="SOURCE" else 2,
                           "a"*64 if mode=="SOURCE" else "b"*64,"c"*64,{sha("x"):"d"*64}]})), \
             contextlib.redirect_stdout(out):
            self.assertEqual(m.compare_one(Remote,Inventory,domain,mid,length,idx,expected),
                             "DIFFER")
        log=out.getvalue()
        self.assertIn("SOURCE_EXCESS_ROWS_IN_SHARED_TABLES=1",log)
        self.assertIn("LIVE_SOURCE_VS_EXISTING_TARGET=DIFFER_ADVISORY",log)
        self.assertIn("SITE_DATABASE_PARITY=ADVISORY_COMPLETE",log)
        self.assertNotIn("db1",log)
        self.assertNotIn("db2",log)
    def test_parse_distinct_missing_columns(self):
        p=payload("SOURCE")
        other=payload("SOURCE",tablename="other")
        a,mp=m.parsed(p,"SOURCE")
        b,mp2=m.parsed(other,"SOURCE")
        self.assertEqual(len(set(mp)-set(mp2)),1)
        self.assertEqual(a,b)
    def test_scope_and_writes_never_authorized(self):
        contents=(ROOT/"p07-two-pending-live-db-worker.py").read_text()
        self.assertIn("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",contents)
        self.assertIn("ROLLBACK",contents)
        self.assertIn('return source_auth(domain,db)',contents)
        self.assertIn('"unzip.kewaro.com","ilovem3u8.kewaro.com"',contents)
        for pattern in ("DROP DATABASE", "CREATE DATABASE", "INSERT INTO", "UPDATE ",
                        "DELETE FROM", "source_freeze(", "cutover_migration("):
            self.assertNotIn(pattern,contents)
        wrapper=(ROOT/"p07-two-pending-live-db-parity.py").read_text()
        for pattern in ("import_database(", "resume_prepare_migration(",
                        "systemctl restart", "cutover_migration(", "source_freeze(",
                        "shutil.copyfile(", "os.replace("):
            self.assertNotIn(pattern,wrapper)
        self.assertIn("CUTOVER_ALLOWED=NO",wrapper)
        self.assertIn("SOURCE_SNAPSHOTS_AND_TARGET_SNAPSHOTS_SIMULTANEOUS=NO",
                      wrapper)
    def test_exact_arg_first(self):
        with mock.patch.object(sys,"argv",["tool","--restore"]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"verify_file") as verify:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_SCOPED_READONLY_ARG_REQUIRED"):
                m.main()
            verify.assert_not_called()
    def test_specific_site_execution_avoids_rescanning_unzip(self):
        fake=types.ModuleType("server_migration_pull")
        fake.target_identity=lambda:"TARGETX"
        fake.source_remote=lambda *a,**k:None
        inv=types.ModuleType("inventory")
        inv.build_manifest=Inventory.build_manifest
        calls=[]
        def one(migration,inventory,*args):
            calls.append(args)
            self.assertEqual(args[0],"ilovem3u8.kewaro.com")
            self.assertEqual(args[1],m.ORIGINAL17)
            return "MATCH"
        result=io.StringIO()
        from unittest.mock import Mock
        status=Mock(returncode=0,stdout="0.1.0-release113")
        with mock.patch.object(sys,"argv",["tool","--compare-ilovem3u8-only-read-only"]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"verify_file"), \
             mock.patch.object(m.Path,"is_file",return_value=True), \
             mock.patch.object(m.Path,"read_bytes",return_value=b"mock"), \
             mock.patch.object(m,"gitblob",return_value=m.ENGINE_BLOB), \
             mock.patch.object(m.subprocess,"run",return_value=status), \
             mock.patch.object(m,"compare_one",side_effect=one), \
             mock.patch.dict(sys.modules,{"server_migration_pull":fake,
                                          "inventory":inv}), \
             contextlib.redirect_stdout(result):
            self.assertEqual(m.main(),0)
        self.assertEqual(len(calls),1)
        self.assertIn("SITE_COUNT=1",result.getvalue())
        self.assertIn("CUTOVER_ALLOWED=NO",result.getvalue())
if __name__=="__main__":
    unittest.main()
