"""Bounded P07 schema-metadata diff and no-mutation security tests."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parent
def module(filename,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/filename)
    x=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(x)
    return x
w=module("p07-fresh-cp2-schema-readonly-worker.py","p07_schema_worker")
o=module("p07-fresh-cp2-schema-parity-readonly.py","p07_schema_operator")
class Checks(unittest.TestCase):
    def test_safe_static_sql(self):
        q=w.query_statement("COLUMNS","TABLE_SCHEMA",("TABLE_NAME","COLUMN_NAME"),"safe-db")
        self.assertTrue(q.startswith("SELECT IF("))
        self.assertIn("FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='safe-db'",q)
        self.assertNotIn("UPDATE ",q)
        for db in ("a' OR 1=1","x;DROP TABLE z",""):
            with self.assertRaises(w.Block):
                w.query_statement("COLUMNS","TABLE_SCHEMA",("TABLE_NAME",),db)
    def test_raw_values_are_digest_only(self):
        item=w.category_fingerprint(
            [b"V616263\tV313233",b"V616263\tV343536"],("A","B"))
        self.assertEqual(item["count"],2)
        self.assertEqual(len(item["objects"]),1)
        self.assertNotIn("abc",str(item))
        self.assertNotIn("123",str(item))
        self.assertEqual(w.decode_line(b"N\tV30",2),[None,"0"])
        with self.assertRaises(w.Block):
            w.decode_line(b"raw\tV30",2)
    def test_parser_rejects_missing_category(self):
        obj={"mode":"source","categories":{}}
        with self.assertRaises(o.Block):
            o.unpack(json.dumps(obj)+"\n","source")
    def test_parser_rejects_faked_count(self):
        obj={"mode":"source","categories":{
            name:{"count":0,"objects":{}} for name in o.CATEGORIES}}
        with self.assertRaises(o.Block):
            o.unpack(json.dumps(obj)+"\n","source")
    def test_differences_detected_even_equal_counts(self):
        def blank():
            return {name:{"count":1,"objects":{"a"*64:[1,"b"*64]}}
                    for name in o.CATEGORIES}
        a=blank();b=blank();b["INDEXES"]["objects"]["a"*64][1]="c"*64
        d=o.diff(a,b)
        self.assertEqual(d["INDEXES"],(1,1,0,0,1))
        self.assertTrue(all(v[-1]==0 for k,v in d.items() if k!="INDEXES"))
    def test_cli_no_write_or_cutover(self):
        with mock.patch.object(sys,"argv",["operator","--resume"]), \
             mock.patch.object(o.os,"geteuid",return_value=0), \
             mock.patch.object(o,"load_incident") as load:
            with self.assertRaises(o.Block):
                o.main()
            load.assert_not_called()
        code=(ROOT/"p07-fresh-cp2-schema-parity-readonly.py").read_text()
        for word in ("resume_prepare_migration(","cutover_migration(",
                     "source_export_database(","target_create_database_local(",
                     "cloudpanel.import_database(", "source_freeze("):
            self.assertNotIn(word,code)
        self.assertIn("CUTOVER_ALLOWED=NO",code)
        self.assertIn("MIGRATION_STATUS_WRITES=NONE",code)
if __name__=="__main__":
    unittest.main()
