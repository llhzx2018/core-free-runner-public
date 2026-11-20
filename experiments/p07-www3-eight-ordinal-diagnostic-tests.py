"""Synthetic-only read-only www3 8-ordinal fresh-drift diagnostic gates."""
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
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
m=load("p07-www3-eight-ordinal-diagnostic.py","p07_eight_advisory")
worker=load("p07-www3-eight-ordinal-type-worker.py","p07_eight_worker")
ORDS=(17,39,60,69,70,71,78,139)
DIFF_COLS=(2,4,1,1,11,5,7,1)
def sha(x):
    return hashlib.sha256(x.encode("ascii")).hexdigest()
def payload(mode,*,change=False,extra_rows=False,type_change=False):
    maps={};types_map={}; ordids={}
    rows=0;cols=0
    for pos,(ordinal,width) in enumerate(zip(ORDS,DIFF_COLS)):
        name="wp_test_"+str(ordinal)
        ident=sha(name)
        ordids[str(ordinal)]=ident
        columns={};meta={}
        count=2+(1 if extra_rows and pos in (0,2,3) else 0)
        rows+=count;cols+=width
        for i in range(width):
            c=sha("field_"+str(ordinal)+"_"+str(i))
            columns[c]="f"*64 if change else "a"*64
            typ="varchar" if type_change and pos==0 and i==0 else "text"
            meta[c]=[typ,"utf8mb4","utf8mb4_bin","YES","-","-","-","-"]
        maps[ident]=[count,"d"*64 if change else "b"*64,"e"*64,columns]
        types_map[ident]=meta
    return "\n".join((
        "FULL_BASE_TABLES=157",
        "TARGETED_ORDINALS=17,39,60,69,70,71,78,139",
        "ORDINAL_TABLE_IDS="+json.dumps(ordids,sort_keys=True,separators=(",",":")),
        "COLUMN_TYPES="+json.dumps(types_map,sort_keys=True,separators=(",",":")),
        "MODE="+mode,"SCANNED_TABLES=8",
        "SCANNED_COLUMNS="+str(cols),
        "SCANNED_ROWS="+str(rows),
        "ROW_FINGERPRINTS="+json.dumps(maps,sort_keys=True,separators=(",",":")),
        "READ_ONLY_TRANSACTION=YES",
        "CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY=YES"
    ))+"\n"

class Tests(unittest.TestCase):
    def test_exact_sha_sorted_8_ordinals(self):
        table_names=["wp_probe_"+str(i).zfill(3) for i in range(157)]
        order=sorted(table_names,key=sha)
        selected=worker.select_current_eight_ordinals(table_names)
        self.assertEqual(selected,[order[i-1] for i in ORDS])
        self.assertNotEqual(selected,[sorted(table_names)[i-1] for i in ORDS])
        with self.assertRaises(SystemExit):
            worker.select_current_eight_ordinals(table_names[:-1])
    def test_strict_parser_eight_scope_and_data_shapes(self):
        val,table,meta,ordids=m.parsed(payload("SOURCE",change=True),"SOURCE")
        self.assertEqual(val["SCANNED_ROWS"],16)
        self.assertEqual(val["SCANNED_COLUMNS"],32)
        self.assertEqual(len(table),8)
        self.assertEqual(set(ordids),{str(x) for x in ORDS})
        for broken in (
            payload("SOURCE")+"PASSWORD=secret\n",
            payload("SOURCE").replace("SCANNED_TABLES=8","SCANNED_TABLES=7"),
            payload("SOURCE").replace("FULL_BASE_TABLES=157","FULL_BASE_TABLES=155"),
            payload("SOURCE").replace("TARGETED_ORDINALS=17,39,60,69,70,71,78,139",
                                      "TARGETED_ORDINALS=17,39,60"),
            payload("TARGET"),
        ):
            with self.assertRaises(m.Blocked):
                m.parsed(broken,"SOURCE")
    def execute(self,source_opts=None,target_opts=None):
        source_opts=source_opts or {}
        target_opts=target_opts or {}
        s=payload("SOURCE",**source_opts)
        t=payload("TARGET",**target_opts)
        state={"migration_id":m.base.MID,"sites":[{},{
            "domain":m.base.DOMAIN,"mysql_databases":["source_private"]}],
            "source":{"fake":True},"target_server_identity":"stable"}
        fake=types.ModuleType("server_migration_pull")
        fake.target_identity=lambda:"stable"
        calls=[]
        def remote(src,cmd,timeout,check):
            calls.append((cmd,timeout,check))
            return subprocess.CompletedProcess([],0,s,"")
        fake.source_remote=remote
        output=io.StringIO()
        with mock.patch.object(sys,"argv",["tool","--diagnose-eight-current-difference-tables-read-only"]), \
             mock.patch.object(m.readback,"preflight",
                 return_value=("p07scratch-abcdef123456","p07stage-abcdef123456",
                               "PASSWORD_PRIVATE",157)), \
             mock.patch.object(m.readback,"read_private",return_value=state), \
             mock.patch.object(m.base,"_cloudpanel_metadata_counts",return_value=("1","1")), \
             mock.patch.object(m.base,"_master_sql_presence",return_value=("1","1")), \
             mock.patch.dict(sys.modules,{"server_migration_pull":fake}), \
             mock.patch.object(m.subprocess,"run",
                 return_value=subprocess.CompletedProcess([],0,t,"")), \
             contextlib.redirect_stdout(output):
            self.assertEqual(m.compare(),0)
        return output.getvalue(),calls
    def test_three_count_deltas_eight_value_tables_and_32_columns(self):
        text,calls=self.execute({"change":True,"extra_rows":True,
                                 "type_change":True})
        self.assertIn("CURRENT_SOURCE_TARGETED_TABLES=8",text)
        self.assertIn("SOURCE_EXCESS_ROWS_IN_SHARED_TABLES=3",text)
        self.assertIn("TARGET_EXCESS_ROWS_IN_SHARED_TABLES=0",text)
        self.assertIn("ROW_COUNT_DIFFERING_TABLES=3",text)
        self.assertIn("ROW_VALUE_MULTISETS_DIFFERING_TABLES=8",text)
        self.assertIn("DIFFERING_FIELD_COUNT=32",text)
        self.assertIn("DATA_TYPE_CHANGED_FIELD_COUNT=1",text)
        self.assertIn("ORDINAL_17_SOURCE_ROWS=3",text)
        self.assertIn("ORDINAL_17_RESTORED_ROWS=2",text)
        self.assertIn("ORDINAL_70_DIFFERING_COLUMNS=11",text)
        self.assertIn("VALUE_DIFFERENCE_CAUSE=NOT_PROVEN",text)
        self.assertIn("SNAPSHOTS_SIMULTANEOUS=NO",text)
        self.assertIn("CUTOVER_ALLOWED=NO",text)
        self.assertEqual(len(calls),1)
        self.assertIn("--only-eight-current-difference-tables",calls[0][0])
        for secret in ("PASSWORD_PRIVATE","source_private","wp_test_","ROW_FINGERPRINTS="):
            self.assertNotIn(secret,text)
    def test_less_or_no_diffs_do_not_false_block(self):
        text,_=self.execute()
        self.assertIn("EIGHT_TABLE_ROW_VALUE_FINGERPRINT=MATCH_ADVISORY_ONLY",text)
        self.assertIn("DIFFERING_FIELD_COUNT=0",text)
    def test_immutability_and_read_only_workload(self):
        data=(ROOT/"p07-www3-eight-ordinal-type-worker.py").read_text()
        self.assertIn("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",data)
        self.assertIn('script.write(b"ROLLBACK;',data)
        self.assertIn("ROW_COUNT_CAP",data)
        self.assertIn("select_current_eight_ordinals(all_tables)",data)
        self.assertNotIn("DROP DATABASE",data)
        self.assertNotIn("CREATE DATABASE",data)
        self.assertNotIn("INSERT INTO",data)
        self.assertNotIn("UPDATE ",data)
        path=(ROOT/"p07-www3-eight-ordinal-diagnostic.py").read_text()
        self.assertIn("OLD_SERVER_DATABASE_WRITES=NONE",path)
        self.assertIn("CUTOVER_ALLOWED=NO",path)
    def test_explicit_readonly_arg_required(self):
        with mock.patch.object(sys,"argv",["tool","--apply"]), \
             mock.patch.object(m.readback,"preflight") as check:
            with self.assertRaisesRegex(m.Blocked,"EXPLICIT_READ_ONLY_CONTENT_ARG_REQUIRED"):
                m.compare()
            check.assert_not_called()

if __name__=="__main__":
    unittest.main()
