"""P07 www3 targeted four field value deltas; synthetic-only, no external VPS."""
import base64
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
def load(name,label):
    spec=importlib.util.spec_from_file_location(label,ROOT/name)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj
m=load("p07-www3-fourfield-value-difference.py","p07_value_delta")
fixture=load("p07-www3-three-table-field-diagnosis-tests.py","p07_3table_fixture")
worker=load("p07-www3-fourfield-values-worker.py","p07_four_worker")
def identity(raw):
    return hashlib.sha256(raw.encode("ascii")).hexdigest()

def selection():
    return {identity(fixture.names[k]):[identity(x) for x in fixture.colnames[k]]
            for k in (39,60,69)}

def values(mode, change):
    groups={}
    for tid,ids in selection().items():
        groups[tid]={}
        for col in ids:
            counts={"a"*64:1,"b"*64:1}
            if change and col==identity("k"):
                counts={"a"*64:1,"c"*64:1}
            groups[tid][col]={"rows":2,"nonnull":2,"bytes":40 if not change else 42,
                               "counts":counts}
    return "\n".join([
        "MODE="+mode,"TARGETED_TABLES=3","TARGETED_COLUMNS=4",
        "TARGETED_ROWS=6","VALUES="+json.dumps(groups,sort_keys=True,separators=(",",":")),
        "READ_ONLY_TRANSACTION=YES","CONTENT_COMPARISON_ADVISORY_ONLY=YES"
    ])+"\n"

class Tests(unittest.TestCase):
    def test_selector_rejects_bad_and_accepts_opaque_hashes(self):
        names=[f"wp_{i:03d}" for i in range(157)]
        byhash=worker.select_previous_mismatch_ordinals(names)
        columns={t:["a","b"] for t in names}
        picked={identity(t):[identity("a")] for t in byhash}
        picked[identity(byhash[0])]=[identity("a"),identity("b")]
        enc=base64.b64encode(json.dumps(picked).encode()).decode()
        result,p=worker.requested_columns(enc,names,columns)
        self.assertEqual(result,byhash)
        self.assertEqual(sorted(map(len,p.values())),[1,1,2])
        for invalid in ("!!",base64.b64encode(b"{}").decode()):
            with self.assertRaises(SystemExit):
                worker.requested_columns(invalid,names,columns)

    def test_parser_validates_four_field_hash_counters_and_no_unexpected_output(self):
        values_map=m.parse_value_output(values("SOURCE",True),"SOURCE",selection(),6)
        self.assertEqual(len(values_map),3)
        for bad in (values("SOURCE",True)+"password=secret\n",
                    values("SOURCE",True).replace("TARGETED_COLUMNS=4","TARGETED_COLUMNS=5"),
                    values("SOURCE",True).replace("TARGETED_ROWS=6","TARGETED_ROWS=7"),
                    values("SOURCE",True).replace("READ_ONLY_TRANSACTION=YES","READ_ONLY_TRANSACTION=NO")):
            with self.assertRaises(m.Blocked):m.parse_value_output(bad,"SOURCE",selection(),6)
        with self.assertRaises(m.Blocked):
            m.parse_value_output(values("SOURCE",True),"TARGET",selection(),6)

    def test_sql_value_reader_is_read_only_and_hex_binary(self):
        source=(ROOT/"p07-www3-fourfield-values-worker.py").read_text()
        self.assertIn("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",source)
        self.assertIn("HEX(CAST(",source)
        self.assertIn("ROLLBACK;",source)
        self.assertNotIn("INSERT INTO ",source)
        self.assertNotIn("DELETE FROM ",source)
        self.assertNotIn("DROP TABLE ",source)
        self.assertNotIn("UPDATE ",source)
        self.assertIn("OUTPUT_BYTES_CAP=1024*1024*1024",source)

    def test_exact_delta_counts_and_no_business_content(self):
        state={"migration_id":m.base.MID,
               "sites":[{},{"domain":m.base.DOMAIN,"mysql_databases":["www3data"]}],
               "source":{"stub":True},"target_server_identity":"expected"}
        remote=types.ModuleType("server_migration_pull")
        remote.target_identity=lambda:"expected"
        remote_calls=[]
        def remote_fn(src,command,timeout,check):
            remote_calls.append(command)
            response=fixture.payload("SOURCE",True) if len(remote_calls)==1 else values("SOURCE",True)
            return subprocess.CompletedProcess([],0,response,"")
        remote.source_remote=remote_fn
        local_calls=[]
        def local_fn(*a,**kwargs):
            local_calls.append(a[0])
            response=fixture.payload("TARGET",False) if len(local_calls)==1 else values("TARGET",False)
            return subprocess.CompletedProcess([],0,response,"")
        buff=io.StringIO()
        with mock.patch.dict(sys.modules,{"server_migration_pull":remote}), \
             mock.patch.object(m.readback,"preflight",return_value=(
                "p07scratch-abcdef123456","p07stage-abcdef123456","TOP_SECRET",157)), \
             mock.patch.object(m.readback,"read_private",return_value=state), \
             mock.patch.object(m.base,"_cloudpanel_metadata_counts",return_value=("1","1")), \
             mock.patch.object(m.base,"_master_sql_presence",return_value=("1","1")), \
             mock.patch.object(m.subprocess,"run",side_effect=local_fn), \
             mock.patch.object(sys,"argv",[str(ROOT/"p07-www3-fourfield-value-difference.py"),
                "--compare-four-differing-field-values-read-only"]), \
             contextlib.redirect_stdout(buff):
            self.assertEqual(m.compare(),0)
        result=buff.getvalue()
        self.assertIn("FOUR_FIELD_VALUE_MULTISET_DIFFERING_FIELDS=1",result)
        self.assertIn("SOURCE_ONLY=1",result)
        self.assertIn("TARGET_ONLY=1",result)
        self.assertIn("NO_RAW_COLUMN_VALUES_OR_DIGESTS_OUTPUT=YES",result)
        self.assertIn("CUTOVER_ALLOWED=NO",result)
        self.assertNotIn("TOP_SECRET",result)
        self.assertNotIn("www3data",result)
        self.assertNotIn("ROW_FINGERPRINTS=",result)
        self.assertNotIn("VALUES=",result)
        self.assertEqual(len(remote_calls),2)
        self.assertIn("--four-field-values-only",remote_calls[1])
        self.assertEqual(len(local_calls),2)

    def test_wrong_cli_never_initiates_read(self):
        with mock.patch.object(sys,"argv",["prog","--not-authorized"]), \
             mock.patch.object(m.readback,"preflight") as read:
            with self.assertRaises(m.Blocked):m.compare()
            read.assert_not_called()

if __name__=="__main__":
    unittest.main()
