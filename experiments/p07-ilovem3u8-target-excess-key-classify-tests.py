"""Synthetic only, no database/SSH actions: ilovem3u8 target excess row classifier."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parent
def importp(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
m=importp("p07-ilovem3u8-target-excess-key-classify.py","p07_pk_classify")
p=importp("p07-two-pending-live-db-parity.py","p07_pair")
w=importp("p07-ilovem3u8-single-table-pk-worker.py","p07_pk_worker")
def sha(x):
    return hashlib.sha256(x.encode("ascii")).hexdigest()
TABLE=sha("table_0")
def tables(mode,extra=0,changed=True):
    rows={}
    for i in range(42):
        ident=sha("table_"+str(i))
        count=(3+extra if i==0 else 1)
        v=("a"*64 if mode=="SOURCE" or not changed else "f"*64) if i==0 else "b"*64
        rows[ident]=[count,v,"c"*64,{sha("col"):v}]
    return "\n".join([
        "MODE="+mode,"SCANNED_TABLES=42","SCANNED_COLUMNS=42",
        "SCANNED_ROWS="+str(sum(v[0] for v in rows.values())),
        "ROW_FINGERPRINTS="+json.dumps(rows,separators=(",",":")),
        "READ_ONLY_TRANSACTION=YES",
        "CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY=YES",
    ])+"\n"
def keys(mode,extra=0,mutate=False,source_only=False):
    rows={sha("k"+str(i)):sha("row"+str(i)) for i in range(3)}
    if extra:
        rows[sha("k3")]=sha("row3")
        rows[sha("k4")]=sha("row4")
    if mutate:rows[sha("k1")]=sha("tampered")
    if source_only:
        rows[sha("k0_unique")]=rows.pop(sha("k0"))
    return json.dumps({"MODE":mode,
        "TABLE_ID":TABLE,"TABLES_SCANNED":42,
        "PRIMARY_KEY_COLUMN_COUNT":1,"ROW_COUNT":len(rows),
        "ROWS":rows,"READ_ONLY_TRANSACTION":"YES"})+"\n"
class Tests(unittest.TestCase):
    def test_two_target_only_keys_with_shared_rows_identical(self):
        result=m.decide(p,tables("SOURCE"),tables("TARGET",extra=2),
                        keys("SOURCE"),keys("TARGET",extra=2))
        self.assertEqual(result["SOURCE_ONLY_PRIMARY_KEYS"],0)
        self.assertEqual(result["TARGET_ONLY_PRIMARY_KEYS"],2)
        self.assertEqual(result["SHARED_KEY_CHANGED_ROW_CONTENT"],0)
        self.assertEqual(result["CONFLICT_CLASSIFICATION"],
               "TARGET_ONLY_TWO_KEYS_WITH_IDENTICAL_SHARED_ROWS_ADVISORY")
        self.assertEqual(result["DIFFERING_TABLE_COUNT"],1)
    def test_shared_key_modified_does_not_pass(self):
        result=m.decide(p,tables("SOURCE"),tables("TARGET",extra=2),
                        keys("SOURCE"),keys("TARGET",extra=2,mutate=True))
        self.assertEqual(result["SHARED_KEY_CHANGED_ROW_CONTENT"],1)
        self.assertEqual(result["CONFLICT_CLASSIFICATION"],
                         "UNRESOLVED_PRIMARY_KEY_OR_SHARED_ROW_DIFFERENCE")
    def test_source_only_key_is_not_hidden_by_extra_target_rows(self):
        result=m.decide(p,tables("SOURCE"),tables("TARGET",extra=2),
                        keys("SOURCE"),keys("TARGET",extra=2,source_only=True))
        self.assertEqual(result["SOURCE_ONLY_PRIMARY_KEYS"],1)
        self.assertEqual(result["TARGET_ONLY_PRIMARY_KEYS"],3)
        self.assertEqual(result["CONFLICT_CLASSIFICATION"],
                         "UNRESOLVED_PRIMARY_KEY_OR_SHARED_ROW_DIFFERENCE")
    def test_tables_rows_or_pk_snapshot_changed_is_blocked(self):
        with self.assertRaisesRegex(m.Block,"ONE_TABLE_TWO_ROW_DRIFT_SCOPE_CHANGED"):
            m.decide(p,tables("SOURCE"),tables("TARGET",extra=1),
                     keys("SOURCE"),keys("TARGET",extra=2))
        with self.assertRaisesRegex(m.Block,"PK_SNAPSHOT_ROW_COUNT_CHANGED"):
            m.decide(p,tables("SOURCE"),tables("TARGET",extra=2),
                     keys("SOURCE"),keys("TARGET"))
        with self.assertRaisesRegex(m.Block,"FULL_SCHEMA_OR_TABLE_IDENTITIES_CHANGED"):
            m.decide(p,tables("SOURCE").replace('"c"*64',''),
                     tables("TARGET",extra=2),keys("SOURCE"),keys("TARGET",extra=2))
    def test_output_parser_rejects_unverified_rows(self):
        pks=keys("SOURCE")
        obj=m.parsed_keys(pks,"SOURCE",TABLE)
        self.assertEqual(obj["ROW_COUNT"],3)
        for broken in (pks.replace('"SOURCE"','"TARGET"'),
                       pks.replace('"ROW_COUNT": 3','"ROW_COUNT": 8'),
                       pks.replace(TABLE,"0"*64),
                       pks.replace('"ROWS"','"PASSWORD"')):
            with self.assertRaises(m.Block):
                m.parsed_keys(broken,"SOURCE",TABLE)
    def test_worker_allows_only_one_site_and_readonly(self):
        for bad in ("other.test","ilovem3u8.m3u8.one"):
            with self.assertRaisesRegex(w.Block,"SITE_OR_TABLE_SCOPE_INVALID"):
                w.scan_rows(None,"source",bad,"db",TABLE)
        source=(ROOT/"p07-ilovem3u8-single-table-pk-worker.py").read_text()
        self.assertIn("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",source)
        self.assertIn("ROLLBACK",source)
        assert "INSERT INTO" not in source
        assert "UPDATE " not in source
        assert "DROP TABLE" not in source
        operator=(ROOT/"p07-ilovem3u8-target-excess-key-classify.py").read_text()
        self.assertIn("EXPORTED_SQL_SNAPSHOT_PARITY=NOT_VERIFIED",operator)
        self.assertIn("MIGRATION_STATE_WRITES=NONE",operator)
        self.assertIn("CUTOVER_ALLOWED=NO",operator)
    def test_wrong_flag_does_not_read_sources(self):
        with mock.patch.object(sys,"argv",["probe","--restore"]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"load") as validate:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_READONLY_CONFLICT_CLASSIFICATION_ARG_REQUIRED"):
                m.main()
            validate.assert_not_called()
if __name__=="__main__":
    unittest.main()
