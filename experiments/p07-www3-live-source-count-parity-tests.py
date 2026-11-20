"""Synthetic current-source count parity: no real database or server access."""
import ast
import base64
import contextlib
import hashlib
import json
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest import mock

FILE=Path(__file__).with_name("p07-www3-live-source-count-parity.py")
spec=importlib.util.spec_from_file_location("p07_counts",FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def sample_counts(rows=198642):
    ids=[hashlib.sha256(("wp_"+str(i).zfill(3)).encode()).hexdigest() for i in range(157)]
    data=dict.fromkeys(ids,0)
    for key in ids[:73]:
        data[key]=1
    data[ids[73]]=rows-73
    return data


def encoded_counts(data):
    return base64.b64encode(json.dumps(data,sort_keys=True,
        separators=(",",":")).encode("ascii")).decode("ascii")


class Tests(unittest.TestCase):
    def test_remote_has_valid_syntax_and_no_write_sql(self):
        ast.parse(m.REMOTE)
        self.assertNotIn("INSERT INTO ",m.REMOTE)
        self.assertNotIn("DROP DATABASE ",m.REMOTE)
        self.assertNotIn("CREATE DATABASE ",m.REMOTE)
        self.assertIn('env["MYSQL_PWD"]',m.REMOTE)
        self.assertIn('SELECT COUNT(*)',m.REMOTE)
        self.assertIn("inventory.build_manifest",m.REMOTE)
        self.assertIn('tables=sorted(names.splitlines())',m.REMOTE)
        self.assertIn('LIVE_SOURCE_COUNT_MAP_B64',m.REMOTE)

    def test_source_output_strict_sanitization(self):
        msg="\n".join([
            "LIVE_SOURCE_SITE_BINDING=PASS",
            "LIVE_SOURCE_TABLES=157",
            "LIVE_SOURCE_COLUMNS=1848",
            "LIVE_SOURCE_TOTAL_ROWS=198642",
            "LIVE_SOURCE_NONEMPTY_TABLES=74",
            "LIVE_SOURCE_ROWCOUNT_FINGERPRINT="+"a"*64,
            "LIVE_SOURCE_COUNT_MAP_B64="+encoded_counts(sample_counts()),
        ])
        self.assertEqual(m.parse_remote(msg)["LIVE_SOURCE_TOTAL_ROWS"],"198642")
        self.assertEqual(len(m.source_count_map(encoded_counts(sample_counts()),157,198642,74)),157)
        with self.assertRaises(m.Blocked):
            m.source_count_map(encoded_counts(sample_counts()),157,198643,74)
        with self.assertRaises(m.Blocked):
            m.source_count_map("!!!",157,198642,74)
        for bad in (msg+"\npassword=secret",msg.replace("LIVE_SOURCE_TABLES=157","LIVE_SOURCE_TABLES=157\nLIVE_SOURCE_TABLES=157"),
                    msg.replace("LIVE_SOURCE_SITE_BINDING=PASS","LIVE_SOURCE_SITE_BINDING=FAIL")):
            with self.assertRaises(m.Blocked):
                m.parse_remote(bad)

    def run_case(self,source_rows,source_hash,source_map=None):
        from types import SimpleNamespace
        state={"sites":[{},{"mysql_databases":["www3_source"]}],
               "target_server_identity":"target","source":{"stub":True}}
        remote_lines=[
            "LIVE_SOURCE_SITE_BINDING=PASS","LIVE_SOURCE_TABLES=157",
            "LIVE_SOURCE_COLUMNS=1848",
            "LIVE_SOURCE_TOTAL_ROWS="+str(source_rows),
            "LIVE_SOURCE_NONEMPTY_TABLES=74",
            "LIVE_SOURCE_ROWCOUNT_FINGERPRINT="+source_hash,
            "LIVE_SOURCE_COUNT_MAP_B64="+encoded_counts(source_map if source_map is not None else sample_counts(source_rows)),
        ]
        transport=types.ModuleType("server_migration_pull")
        transport.target_identity=lambda:"target"
        called=[]
        def remote(source,command,timeout,check):
            called.append((source,command,timeout,check))
            return subprocess.CompletedProcess([],0,"\n".join(remote_lines)+"\n","")
        transport.source_remote=remote
        output=io.StringIO()
        with mock.patch.dict(sys.modules,{"server_migration_pull":transport}), \
             mock.patch.object(m.readback,"preflight",
                 return_value=("p07scratch-abcdef123456","p07stage-abcdef123456","synthetic",157)), \
             mock.patch.object(m.readback,"database_readback",
                 return_value=(157,1848,198642,74,"a"*64,sample_counts())), \
             mock.patch.object(m.readback,"read_private",return_value=state), \
             mock.patch.object(sys,"argv",[str(FILE),"--compare-current-source-counts-read-only"]), \
             contextlib.redirect_stdout(output):
            self.assertEqual(m.compare(),0)
        self.assertEqual(len(called),1)
        self.assertEqual(called[0][0],{"stub":True})
        self.assertIn("PYTHONDONTWRITEBYTECODE=1",called[0][1])
        self.assertIn("python3 -B -c",called[0][1])
        self.assertNotIn("synthetic",output.getvalue())
        self.assertIn("CUTOVER_ALLOWED=NO",output.getvalue())
        self.assertIn("SOURCE_TARGET_ROW_CONTENT_PARITY=NOT_VERIFIED",output.getvalue())
        return output.getvalue()

    def test_counts_match_is_advisory_not_content_pass(self):
        out=self.run_case(198642,"a"*64)
        self.assertIn("LIVE_SOURCE_VS_RESTORED_COUNT_PARITY=MATCH",out)
        self.assertIn("LIVE_SOURCE_EQUALS_ORIGINAL_EXPORT_SNAPSHOT=NOT_VERIFIED",out)
        self.assertIn("MISMATCHED_TABLE_COUNTS=0",out)

    def test_live_source_drift_is_not_called_corruption(self):
        out=self.run_case(198650,"b"*64)
        self.assertIn("LIVE_SOURCE_VS_RESTORED_COUNT_PARITY=DIFFER",out)
        self.assertIn("MISMATCHED_TABLE_COUNTS=1",out)
        self.assertIn("SOURCE_EXCESS_ROWS_IN_SHARED_TABLES=8",out)
        self.assertIn("TARGET_EXCESS_ROWS_IN_SHARED_TABLES=0",out)
        self.assertIn("SOURCE_TARGET_ROW_CONTENT_PARITY=NOT_VERIFIED",out)

    def test_equal_global_total_but_two_offsetting_table_differences(self):
        source=sample_counts()
        keys=[k for k,v in source.items() if v>0]
        source[keys[0]]+=1
        source[keys[-1]]-=1
        self.assertEqual(sum(source.values()),198642)
        self.assertEqual(sum(v>0 for v in source.values()),74)
        out=self.run_case(198642,"b"*64,source)
        self.assertIn("CURRENT_SOURCE_ROWS=198642",out)
        self.assertIn("RESTORED_TARGET_ROWS=198642",out)
        self.assertIn("LIVE_SOURCE_VS_RESTORED_COUNT_PARITY=DIFFER",out)
        self.assertIn("MISMATCHED_TABLE_COUNTS=2",out)
        self.assertIn("SOURCE_EXCESS_ROWS_IN_SHARED_TABLES=1",out)
        self.assertIn("TARGET_EXCESS_ROWS_IN_SHARED_TABLES=1",out)
        self.assertIn("SOURCE_TARGET_ROW_CONTENT_PARITY=NOT_VERIFIED",out)

    def test_unexpected_argument_never_opens_database(self):
        with mock.patch.object(sys,"argv",[str(FILE),"--unsafe"]), \
             mock.patch.object(m.readback,"preflight") as preflight:
            with self.assertRaisesRegex(m.Blocked,"EXPLICIT_COMPARISON_ARG_REQUIRED"):
                m.compare()
            preflight.assert_not_called()

if __name__=="__main__":
    unittest.main()
