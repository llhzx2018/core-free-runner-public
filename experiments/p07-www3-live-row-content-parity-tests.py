"""Bounded synthetic tests: content parity labels, sensitive-output safety and negatives."""
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

MAIN=Path(__file__).with_name("p07-www3-live-row-content-parity.py")
spec=importlib.util.spec_from_file_location("p07_row_check",MAIN)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def result(mode,rows=7,hash_val=None,cell_sig=None):
    table=hashlib.sha256(b"wp_posts").hexdigest()
    col="a"*64
    val=hash_val or "b"*64
    colmap={hashlib.sha256(b"id").hexdigest():cell_sig or "c"*64}
    lines=[
      "MODE="+mode,
      "SCANNED_TABLES=1",
      "SCANNED_COLUMNS=3",
      "SCANNED_ROWS="+str(rows),
      "ROW_FINGERPRINTS="+json.dumps({table:[rows,val,col,colmap]}),
      "READ_ONLY_TRANSACTION=YES",
      "CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY=YES",
    ]
    return "\n".join(lines)+"\n"

class Tests(unittest.TestCase):
    def test_strict_output_suppresses_unknown_lines(self):
        meta,maprows=m.parsed(result("SOURCE"),"SOURCE")
        self.assertEqual(meta["SCANNED_ROWS"],7)
        self.assertEqual(len(maprows),1)
        for wrong in (
          result("SOURCE")+"password=unsafe\n",
          result("SOURCE").replace("READ_ONLY_TRANSACTION=YES","READ_ONLY_TRANSACTION=NO"),
          result("SOURCE").replace("SCANNED_ROWS=7","SCANNED_ROWS=8"),
          result("SOURCE").replace('"b"*64',''),
        ):
            if wrong==result("SOURCE"): continue
            with self.assertRaises(m.Blocked):
                m.parsed(wrong,"SOURCE")
        with self.assertRaises(m.Blocked):
            m.parsed(result("SOURCE"),"TARGET")

    def test_mode_requires_exact_argument(self):
        with mock.patch.object(sys,"argv",[str(MAIN),"--unsafe"]), \
             mock.patch.object(m.readback,"preflight") as preflight:
            with self.assertRaisesRegex(m.Blocked,"EXPLICIT_READ_ONLY_CONTENT_ARG_REQUIRED"):
                m.compare()
            preflight.assert_not_called()

    def test_existing_workflow_only_reads_independent_transactions(self):
        worker=Path(__file__).with_name("p07-www3-content-worker.py").read_text()
        self.assertIn("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",worker)
        self.assertIn("SET SESSION time_zone=",worker)
        self.assertIn("ROLLBACK",worker)
        self.assertIn("ROW_BYTES_CAP=16*1024*1024",worker)
        self.assertIn("source_auth(domain,db)",worker)
        self.assertIn("target_auth(domain,db)",worker)
        self.assertIn("hashlib.sha256(b",worker)
        self.assertNotIn("DROP DATABASE",worker)
        self.assertNotIn("CREATE DATABASE",worker)
        self.assertNotIn("INSERT INTO",worker)

    def run_compare(self,old_rows,old_hash,old_cell_sig=None):
        state={"migration_id":m.base.MID,"sites":[{},{
            "domain":m.base.DOMAIN,"mysql_databases":["www3data"]}],
            "source":{"mock_source":True},"target_server_identity":"same-target"}
        raw_target=result("TARGET",7,"b"*64)
        raw_source=result("SOURCE",old_rows,old_hash,old_cell_sig)
        remote_mod=types.ModuleType("server_migration_pull")
        remote_mod.target_identity=lambda:"same-target"
        calls=[]
        def transport(source,cmd,timeout,check):
            calls.append((source,cmd,timeout,check))
            return subprocess.CompletedProcess([],0,raw_source,"")
        remote_mod.source_remote=transport
        output=io.StringIO()
        with mock.patch.object(sys,"argv",[str(MAIN),"--compare-live-source-rows-read-only"]), \
             mock.patch.object(m.readback,"preflight",
                 return_value=("p07scratch-abcdef123456","p07stage-abcdef123456",
                               "PRIVATE_NEVER_PRINT",1)), \
             mock.patch.object(m.readback,"read_private",return_value=state), \
             mock.patch.object(m.base,"_cloudpanel_metadata_counts",return_value=("1","1")), \
             mock.patch.object(m.base,"_master_sql_presence",return_value=("1","1")), \
             mock.patch.dict(sys.modules,{"server_migration_pull":remote_mod}), \
             mock.patch.object(m.subprocess,"run",
                 return_value=subprocess.CompletedProcess([],0,raw_target,"")), \
             contextlib.redirect_stdout(output):
            self.assertEqual(m.compare(),0)
        self.assertEqual(len(calls),1)
        self.assertIn("python3 -B -c",calls[0][1])
        out=output.getvalue()
        self.assertNotIn("PRIVATE_NEVER_PRINT",out)
        self.assertNotIn("wp_posts",out)
        self.assertNotIn("b"*64,out)
        self.assertIn("CUTOVER_ALLOWED=NO",out)
        self.assertIn("ORIGINAL_SQL_EXPORT_ROW_CONTENT_PARITY=NOT_VERIFIED",out)
        return out

    def test_advisory_match_never_promotes_cutover(self):
        out=self.run_compare(7,"b"*64)
        self.assertIn("ROW_VALUE_MULTISETS_DIFFERING_TABLES=0",out)
        self.assertIn("COLUMN_VALUE_DISTRIBUTION_DIFFERING_TABLES=0",out)
        self.assertIn("LIVE_SOURCE_TARGET_ROW_VALUE_FINGERPRINT=MATCH_ADVISORY_ONLY",out)
        self.assertIn("SNAPSHOTS_SIMULTANEOUS=NO",out)

    def test_equal_rows_but_differing_content_is_detected(self):
        out=self.run_compare(7,"c"*64)
        self.assertIn("ROW_COUNT_DIFFERING_TABLES=0",out)
        self.assertIn("ROW_VALUE_MULTISETS_DIFFERING_TABLES=1",out)
        self.assertIn("ROW_COMBINATION_ONLY_DIFFERING_TABLES=1",out)
        self.assertIn("LIVE_SOURCE_TARGET_ROW_VALUE_FINGERPRINT=DIFFER_ADVISORY",out)

    def test_cell_distribution_changes_in_one_column(self):
        out=self.run_compare(7,"d"*64,"e"*64)
        self.assertIn("ROW_VALUE_MULTISETS_DIFFERING_TABLES=1",out)
        self.assertIn("COLUMN_VALUE_DISTRIBUTION_DIFFERING_TABLES=1",out)
        self.assertIn("COLUMN_VALUE_DISTRIBUTION_DIFFERING_COLUMNS=1",out)
        self.assertIn("ROW_COMBINATION_ONLY_DIFFERING_TABLES=0",out)
        self.assertIn("DIFFERING_TABLE_ORDINAL_COLUMN_COUNTS=1:1",out)
        self.assertNotIn("wp_posts",out)

    def test_source_time_drift_remains_advisory(self):
        out=self.run_compare(8,"b"*64)
        self.assertIn("ROW_COUNT_DIFFERING_TABLES=1",out)
        self.assertIn("SOURCE_MAY_CHANGE_AFTER_READ=YES",out)


def current_worker_reply(mode,changed=False):
    """Synthetic 157-table read-only fingerprints; no server or real SQL."""
    rows={}
    for i in range(157):
        table=hashlib.sha256(("wp_test_"+str(i)).encode()).hexdigest()
        column=hashlib.sha256(b"id").hexdigest()
        value=("e" if changed and i==3 else "b")*64
        rows[table]=[1,value,"c"*64,{column:"d"*64}]
    return "\n".join((
        "MODE="+mode,
        "SCANNED_TABLES=157",
        "SCANNED_COLUMNS=157",
        "SCANNED_ROWS=157",
        "ROW_FINGERPRINTS="+json.dumps(rows,sort_keys=True),
        "READ_ONLY_TRANSACTION=YES",
        "CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY=YES",
    ))+"\n"


class CurrentCandidateTests(unittest.TestCase):
    def run_current(self,*,different=False,relation_status="CONNECTED_NOT_CUTOVER_READY"):
        mid="pull-20261102T005644Z-7178c7d5"
        db="p07aaaaaaaaaa1"
        src={"migration_id":mid,"mysql_databases":["www3data"]}
        panel={"mysql_databases":[db]}
        state={"migration_id":mid,"target_server_identity":"cp2",
               "source_runtime_frozen":False,
               "dns_changed_by_p07":False,
               "cutover_prohibited":True,
               "source_runtime_path":"/var/lib/vf-server-ops/pull-source/"+mid+"/runtime",
               "source":{"host":"old.example.test"}}
        relation={"JOURNAL_STATUS":relation_status,
                  "CURRENT_CONFIG_READBACK":"CANDIDATE_MATCH",
                  "CANDIDATE_DB_IN_CP2_SITE_PANEL":"YES",
                  "SOURCE_DB_IN_CP2_PANEL":"NO",
                  "UNCLASSIFIED_CP2_SITE_DB_COUNT":0}
        scope=types.SimpleNamespace(
            www3_context=lambda:(src,panel,Path("/tmp/private"),Path("/tmp/config"),
                                 "cp2"),
            candidate_relation=lambda *args:relation,
            www3_candidate_credentials=lambda *args:(
                db,"p07u888888881","PASSWORD_NEVER_ECHO"),
            pinned=lambda *args:types.SimpleNamespace(
                secure_state=lambda *args:state),
            BASE=Path("unused"),BASE_BLOB="unused",ROOT=Path("/tmp"))
        remote_mod=types.ModuleType("server_migration_pull")
        remote_mod.target_identity=lambda:"cp2"
        calls=[]
        def source_remote(source,cmd,timeout,check):
            calls.append(("remote",source,cmd,timeout,check))
            return subprocess.CompletedProcess([],0,
                current_worker_reply("SOURCE",different),"")
        remote_mod.source_remote=source_remote
        def candidate_run(argv,**kwargs):
            calls.append(("local",argv,kwargs))
            return subprocess.CompletedProcess([],0,
                current_worker_reply("TARGET"),"")
        output=io.StringIO()
        with mock.patch.object(sys,"argv",[str(MAIN),
            "--compare-current-candidate-source-rows-read-only"]), \
             mock.patch.object(m,"current_candidate_context",return_value=scope), \
             mock.patch.dict(sys.modules,{"server_migration_pull":remote_mod}), \
             mock.patch.object(m.subprocess,"run",side_effect=candidate_run), \
             mock.patch.object(m.readback,"preflight") as scratch, \
             contextlib.redirect_stdout(output):
            if relation_status!="CONNECTED_NOT_CUTOVER_READY":
                with self.assertRaisesRegex(
                        m.Blocked,"CURRENT_CANDIDATE_NOT_JOURNAL_BOUND"):
                    m.compare_current_candidate()
                self.assertEqual(calls,[])
                scratch.assert_not_called()
                return None
            self.assertEqual(m.compare_current_candidate(),0)
            scratch.assert_not_called()
        local=[c for c in calls if c[0]=="local"]
        remote=[c for c in calls if c[0]=="remote"]
        self.assertEqual(len(local),1)
        self.assertEqual(len(remote),1)
        self.assertEqual(local[0][1][3],"target-current")
        self.assertEqual(local[0][2]["env"]["P07_CURRENT_CANDIDATE_PASSWORD"],
                         "PASSWORD_NEVER_ECHO")
        self.assertNotIn("PASSWORD_NEVER_ECHO",repr(local[0][1]))
        self.assertNotIn("PASSWORD_NEVER_ECHO",remote[0][2])
        result=output.getvalue()
        self.assertIn("CANDIDATE_TABLES=157",result)
        self.assertIn("SOURCE_TABLES=157",result)
        self.assertNotIn("PASSWORD_NEVER_ECHO",result)
        self.assertNotIn("wp_test_",result)
        self.assertIn("CUTOVER_ALLOWED=NO",result)
        self.assertIn("SOURCE_EXPORT_SNAPSHOT_PARITY=NOT_VERIFIED",result)
        self.assertIn("SNAPSHOTS_SIMULTANEOUS=NO",result)
        return result

    def test_current_candidate_identical_values_never_cutover(self):
        text=self.run_current()
        self.assertIn("LIVE_CONTENT_FINGERPRINT=MATCH_ADVISORY_ONLY",text)

    def test_current_candidate_changed_values_are_detected(self):
        text=self.run_current(different=True)
        self.assertIn("LIVE_CONTENT_FINGERPRINT=DIFFER_ADVISORY",text)
        self.assertIn("ROW_VALUE_DIFF_TABLES=1",text)

    def test_unverified_connection_never_runs_source_or_sql(self):
        self.assertIsNone(self.run_current(relation_status="INTENT_RESERVED"))

if __name__=="__main__":
    unittest.main()
