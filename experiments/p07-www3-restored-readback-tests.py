"""Synthetic-only tests for CP2 scratch readback. No real databases."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

FILE=Path(__file__).with_name("p07-www3-restored-readback.py")
spec=importlib.util.spec_from_file_location("p07_readback",FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TestReadback(unittest.TestCase):
    def test_valid_success_never_claims_content_parity(self):
        output=io.StringIO()
        with mock.patch.object(m,"preflight",return_value=("p07scratch-abcdef123456","p07stage-abcdef123456","unused",2)), \
             mock.patch.object(m,"database_readback",return_value=(2,6,17,2,"a"*64)), \
             mock.patch.object(sys,"argv",[str(FILE),"--verify-restored-read-only"]), \
             contextlib.redirect_stdout(output):
            self.assertEqual(m.main(),0)
        data=output.getvalue()
        self.assertIn("RESTORED_DATABASE_READBACK=PASS",data)
        self.assertIn("SOURCE_TARGET_ROW_CONTENT_PARITY=NOT_VERIFIED",data)
        self.assertIn("SOURCE_RAW_BYTES_TO_DB_PARITY=NOT_VERIFIED",data)
        self.assertIn("CUTOVER_ALLOWED=NO",data)
        self.assertNotIn("unused",data)

    def test_wrong_base_table_count_blocks(self):
        with mock.patch.object(m,"preflight",return_value=("p07scratch-abcdef123456","p07stage-abcdef123456","unused",3)), \
             mock.patch.object(m,"database_readback",return_value=(2,6,17,2,"a"*64)), \
             mock.patch.object(sys,"argv",[str(FILE),"--verify-restored-read-only"]):
            with self.assertRaisesRegex(m.Blocked,"RESTORED_TABLES_DIFFER"):
                m.main()

    def test_read_only_queries_and_nonempty_row_counts(self):
        original=tempfile.TemporaryDirectory
        calls=[]
        def fake_run(argv,**kwargs):
            self.assertEqual(argv[0],"mariadb")
            self.assertIn("--defaults-extra-file=",argv[1])
            self.assertEqual(kwargs["stdin"],subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"],subprocess.DEVNULL)
            sql=argv[-1]
            self.assertTrue(sql.startswith("SELECT "))
            calls.append(sql)
            if "SELECT TABLE_NAME" in sql: value=b"wp_a\nwp_b\n"
            elif "information_schema.COLUMNS" in sql: value=b"5\n"
            elif "wp_a" in sql: value=b"2\n"
            elif "wp_b" in sql: value=b"7\n"
            else: raise AssertionError("unexpected SQL")
            return subprocess.CompletedProcess(argv,0,value,b"")
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.object(m.base,"_cloudpanel_metadata_counts",return_value=("1","1")), \
                 mock.patch.object(m.base,"_master_sql_presence",return_value=("1","1")), \
                 mock.patch.object(m.tempfile,"TemporaryDirectory",
                    side_effect=lambda **kw: original(prefix=kw["prefix"],dir=home)), \
                 mock.patch.object(m.subprocess,"run",side_effect=fake_run):
                result=m.database_readback("p07scratch-abcdef123456",
                                          "p07stage-abcdef123456","synthetic")
            self.assertEqual(list(Path(home).glob("p07-readback-*")),[])
        self.assertEqual(result[:4],(2,5,9,2))
        self.assertEqual(len(calls),4)

    def test_rejects_sql_error_and_malicious_table_name(self):
        with tempfile.TemporaryDirectory() as home:
            original=tempfile.TemporaryDirectory
            with mock.patch.object(m.base,"_cloudpanel_metadata_counts",return_value=("1","1")), \
                 mock.patch.object(m.base,"_master_sql_presence",return_value=("1","1")), \
                 mock.patch.object(m.tempfile,"TemporaryDirectory",
                    side_effect=lambda **kw: original(prefix=kw["prefix"],dir=home)), \
                 mock.patch.object(m.subprocess,"run",
                    return_value=subprocess.CompletedProcess([],0,b"bad;DROP\n",b"")):
                with self.assertRaisesRegex(m.Blocked,"TABLE_NAMES_REQUIRE_EXPLICIT"):
                    m.database_readback("p07scratch-abcdef123456",
                                        "p07stage-abcdef123456","synthetic")
            with mock.patch.object(m.base,"_cloudpanel_metadata_counts",return_value=("1","1")), \
                 mock.patch.object(m.base,"_master_sql_presence",return_value=("1","1")), \
                 mock.patch.object(m.tempfile,"TemporaryDirectory",
                    side_effect=lambda **kw: original(prefix=kw["prefix"],dir=home)), \
                 mock.patch.object(m.subprocess,"run",
                    return_value=subprocess.CompletedProcess([],1,b"",b"secret")):
                with self.assertRaisesRegex(m.Blocked,"READ_ONLY_QUERY_FAILED"):
                    m.database_readback("p07scratch-abcdef123456",
                                        "p07stage-abcdef123456","synthetic")

if __name__=="__main__":
    unittest.main()
