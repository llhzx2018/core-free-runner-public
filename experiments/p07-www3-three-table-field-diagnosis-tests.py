"""Synthetic-only 3-table/4-field diagnosis. Never touches real databases."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import types
import unittest
from unittest import mock

P=Path(__file__).with_name("p07-www3-three-table-field-diagnosis.py")
spec=importlib.util.spec_from_file_location("p07_4field",P)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
W=Path(__file__).with_name("p07-www3-three-table-type-worker.py")
wspec=importlib.util.spec_from_file_location("p07_3work",W)
worker=importlib.util.module_from_spec(wspec)
wspec.loader.exec_module(worker)

def sha(x):
    return hashlib.sha256(x.encode("ascii")).hexdigest()
names={39:"wp_39",60:"wp_60",69:"wp_69"}
colnames={39:["k","v"],60:["m"],69:["n"]}
table_data_types={39:["varchar","datetime"],60:["decimal"],69:["longtext"]}
ordids={str(k):sha(n) for k,n in names.items()}

def payload(mode,mutate=True):
    hashes={}
    metadata={}
    for t,table in names.items():
        cols={}
        cmeta={}
        for j,name in enumerate(colnames[t]):
            ident=sha(name)
            sig=("f"*64 if mutate else "a"*64)
            cols[ident]=sig
            dtype=table_data_types[t][j]
            cmeta[ident]=[dtype,"utf8mb4" if dtype in ("varchar","longtext") else "-",
                         "utf8mb4_bin" if dtype in ("varchar","longtext") else "-",
                         "YES","-","-","-" if dtype not in ("datetime",) else "6",
                         "255" if dtype in ("varchar",) else "-"]
        hashes[sha(table)]=[2,"d"*64 if mutate else "c"*64,"b"*64,cols]
        metadata[sha(table)]=cmeta
    return "\n".join([
      "FULL_BASE_TABLES=157","TARGETED_ORDINALS=39,60,69",
      "ORDINAL_TABLE_IDS="+json.dumps(ordids,sort_keys=True,separators=(",",":")),
      "COLUMN_TYPES="+json.dumps(metadata,sort_keys=True,separators=(",",":")),
      "MODE="+mode,
      "SCANNED_TABLES=3","SCANNED_COLUMNS=4","SCANNED_ROWS=6",
      "ROW_FINGERPRINTS="+json.dumps(hashes,sort_keys=True,separators=(",",":")),
      "READ_ONLY_TRANSACTION=YES",
      "CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY=YES"
    ])+"\n"

class Tests(unittest.TestCase):
    def test_hash_sorted_ordinals_match_original_full_probe(self):
        # Previous DIFFERING_TABLE_ORDINAL_COLUMN_COUNTS used sorted opaque
        # SHA256 identity, not alphabetically sorted SQL names. Reproduce it.
        nameset=["wp_probe_"+str(i).zfill(3) for i in range(157)]
        from_probe=sorted(nameset,key=lambda name:sha(name))
        selection=worker.select_previous_mismatch_ordinals(sorted(nameset))
        self.assertEqual(selection,[from_probe[i] for i in (38,59,68)])
        # The regression must genuinely distinguish the two sort orders.
        self.assertNotEqual(selection,[sorted(nameset)[i] for i in (38,59,68)])
        for ordinal,name in zip((39,60,69),selection):
            self.assertEqual(from_probe.index(name)+1,ordinal)
        with self.assertRaises(SystemExit):
            worker.select_previous_mismatch_ordinals(nameset[:156])

    def test_worker_type_metadata_with_strict_whitelist(self):
        tablecols={"wp_39":["a","b"],"wp_60":["c"],"wp_69":["d"]}
        rows=[
          "wp_39\ta\tvarchar\tutf8mb4\tutf8mb4_bin\tYES\t-\t-\t-\t255",
          "wp_39\tb\tdatetime\t-\t-\tNO\t-\t-\t6\t-",
          "wp_60\tc\tdecimal\t-\t-\tYES\t10\t2\t-\t-",
          "wp_69\td\tlongtext\tutf8mb4\tutf8mb4_bin\tYES\t-\t-\t-\t4294967295",
        ]
        with mock.patch.object(worker,"sql_read",return_value="\n".join(rows)):
            result=worker.targeted_types(["mariadb"],"source",list(tablecols),tablecols)
        self.assertEqual(len(result),3)
        self.assertEqual(result[sha("wp_39")][sha("a")][0],"varchar")
        self.assertEqual(result[sha("wp_60")][sha("c")][5],"2")
        with mock.patch.object(worker,"sql_read",return_value="\n".join(rows[:-1])):
            with self.assertRaises(SystemExit):
                worker.targeted_types(["mariadb"],"source",list(tablecols),tablecols)

    def test_parsing_rejects_extra_keys_and_hash_mismatch(self):
        meta,rows,types,ordinals=mod.parsed(payload("SOURCE"),"SOURCE")
        self.assertEqual(len(rows),3)
        self.assertEqual(meta["SCANNED_ROWS"],6)
        self.assertEqual(ordinals,ordids)
        for bad in (
            payload("SOURCE")+"password=sensitive\n",
            payload("SOURCE").replace("FULL_BASE_TABLES=157","FULL_BASE_TABLES=156"),
            payload("SOURCE").replace("TARGETED_ORDINALS=39,60,69","TARGETED_ORDINALS=39,60"),
            payload("SOURCE").replace("MODE=SOURCE","MODE=TARGET"),
        ):
            with self.assertRaises(mod.Blocked):
                mod.parsed(bad,"SOURCE")

    def test_exact_four_fields_and_no_secrets_in_output(self):
        from types import SimpleNamespace
        state={"migration_id":mod.base.MID,
               "sites":[{},{"domain":mod.base.DOMAIN,"mysql_databases":["www3data"]}],
               "source":{"fake":True},"target_server_identity":"stable"}
        transport=types.ModuleType("server_migration_pull")
        transport.target_identity=lambda:"stable"
        calls=[]
        def fetch(src,cmd,timeout,check):
            calls.append((src,cmd,timeout,check))
            return subprocess.CompletedProcess([],0,payload("SOURCE",True),"")
        transport.source_remote=fetch
        buffer=io.StringIO()
        with mock.patch.object(sys,"argv",[str(P),"--diagnose-three-table-field-types-read-only"]), \
             mock.patch.object(mod.readback,"preflight",return_value=("p07scratch-abcdef123456",
                 "p07stage-abcdef123456","SENSITIVE_PASSWORD",157)), \
             mock.patch.object(mod.readback,"read_private",return_value=state), \
             mock.patch.object(mod.base,"_cloudpanel_metadata_counts",return_value=("1","1")), \
             mock.patch.object(mod.base,"_master_sql_presence",return_value=("1","1")), \
             mock.patch.dict(sys.modules,{"server_migration_pull":transport}), \
             mock.patch.object(mod.subprocess,"run",
                 return_value=subprocess.CompletedProcess([],0,payload("TARGET",False),"")), \
             contextlib.redirect_stdout(buffer):
            self.assertEqual(mod.compare(),0)
        output=buffer.getvalue()
        self.assertIn("DIFFERING_FIELD_COUNT=4",output)
        self.assertIn("DATA_TYPE_CHANGED_FIELD_COUNT=0",output)
        self.assertIn("CHARSET_CHANGED_FIELD_COUNT=0",output)
        ords=re.findall(r"DIFFERING_FIELD_\d+_TABLE_ORDINAL=(\d+)",output)
        self.assertEqual(sorted(ords),["39","39","60","69"])
        self.assertIn("SOURCE_MAY_CHANGE_AFTER_READ=YES",output)
        self.assertIn("CUTOVER_ALLOWED=NO",output)
        self.assertNotIn("SENSITIVE_PASSWORD",output)
        self.assertNotIn("www3data",output)
        self.assertNotIn("wp_39",output)
        self.assertNotIn("ROW_FINGERPRINTS=",output)
        self.assertEqual(len(calls),1)
        self.assertIn("--only-three-known-difference-tables",calls[0][1])
        self.assertNotIn("UPDATE ",calls[0][1])

    def test_fewer_or_more_differing_fields_blocks(self):
        state={"migration_id":mod.base.MID,
               "sites":[{},{"domain":mod.base.DOMAIN,"mysql_databases":["www3data"]}],
               "source":{"fake":True},"target_server_identity":"stable"}
        fake=types.ModuleType("server_migration_pull")
        fake.target_identity=lambda:"stable"
        fake.source_remote=lambda *a,**k:subprocess.CompletedProcess([],0,payload("SOURCE",False),"")
        with mock.patch.object(sys,"argv",[str(P),"--diagnose-three-table-field-types-read-only"]), \
             mock.patch.object(mod.readback,"preflight",return_value=("p07scratch-abcdef123456",
                 "p07stage-abcdef123456","synthetic",157)), \
             mock.patch.object(mod.readback,"read_private",return_value=state), \
             mock.patch.object(mod.base,"_cloudpanel_metadata_counts",return_value=("1","1")), \
             mock.patch.object(mod.base,"_master_sql_presence",return_value=("1","1")), \
             mock.patch.dict(sys.modules,{"server_migration_pull":fake}), \
             mock.patch.object(mod.subprocess,"run",
                 return_value=subprocess.CompletedProcess([],0,payload("TARGET",False),"")):
            with self.assertRaises(mod.Blocked):
                mod.compare()

    def test_writes_are_never_authorized_in_command_paths(self):
        workertext=W.read_text()
        self.assertIn("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",workertext)
        self.assertIn("ROLLBACK",workertext)
        self.assertIn("select_previous_mismatch_ordinals(all_tables)",workertext)
        self.assertIn("for i in (38,59,68)",workertext)
        self.assertNotIn("DROP DATABASE",workertext)
        self.assertNotIn("CREATE DATABASE",workertext)
        self.assertNotIn("INSERT INTO",workertext)

if __name__=="__main__":
    unittest.main()
