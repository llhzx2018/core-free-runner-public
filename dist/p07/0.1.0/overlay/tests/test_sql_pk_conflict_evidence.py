"""Synthetic private primary-key overlap classification, never production data."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import sql_pk_conflict_evidence as pk
import sql_diff_evidence as diff

DDL = "CREATE TABLE \x60private_t\x60 (\x60id\x60 int NOT NULL, \x60v\x60 text, PRIMARY KEY (\x60id\x60)) ENGINE=InnoDB;\n"
DDL2 = "CREATE TABLE \x60empty_t\x60 (\x60id\x60 int NOT NULL, PRIMARY KEY (\x60id\x60)) ENGINE=InnoDB;\n"
OTHER = "CREATE TABLE \x60no_key\x60 (\x60item\x60 TEXT);\n"
NAMES = { "private_t", "empty_t", "no_key" }


class PKConflictTests(unittest.TestCase):
    def compare(self, source, target, *, schema_source=DDL+DDL2+OTHER,
                schema_target=DDL+DDL2+OTHER, full=False):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/"a.sql.gz",Path(tmp)/"b.sql.gz"
            for path,body in ((a,schema_source+source),(b,schema_target+target)):
                with gzip.open(path,"wt",encoding="utf-8") as f:f.write(body)
            return diff.diagnostic(a,b) if full else pk.diagnostic(a,b)

    def test_primary_key_conflicts_in_both_directions(self):
        source="INSERT INTO \x60private_t\x60 VALUES (1,'same'),(2,'old'),(3,'source');\n"
        target="INSERT INTO \x60private_t\x60 VALUES (1,'same'),(2,'new'),(4,'target'),(5,'more');\n"
        data=self.compare(source,target,full=True)
        v=data["pk_conflicts"]
        self.assertEqual(v["comparison"],"PK_LITERAL_DIFFER")
        self.assertEqual(v["tables_examined"],3)
        self.assertEqual(v["pk_tables_evaluable"],2)
        self.assertEqual(v["pk_tables_unavailable"],1)
        self.assertEqual(v["source_only_keys"],1)
        self.assertEqual(v["target_only_keys"],2)
        self.assertEqual(v["same_key_changed_literals"],1)
        self.assertEqual(v["identical_key_identical_literals"],1)
        self.assertEqual(v["differing_table_ordinals"],[{
            "table_ordinal":3, "source_only_keys":1,"target_only_keys":2,
            "same_key_changed_literals":1,"identical_key_identical_literals":1,
        }])
        self.assertEqual(data["verification"],"NOT_A_PASS_GATE")
        serialized=json.dumps(data)
        for secret in ["private_t","old","new","source","target","'same'"]:
            self.assertNotIn('"'+secret+'"',serialized)

    def test_extra_rows_are_not_same_pk_changes(self):
        left="INSERT INTO \x60private_t\x60 VALUES (1,'a'),(2,'b');\n"
        right="INSERT INTO \x60private_t\x60 VALUES (1,'a'),(2,'b'),(3,'x'),(4,'y');\n"
        v=self.compare(left,right)
        self.assertEqual((v["source_only_keys"],v["target_only_keys"],v["same_key_changed_literals"]),(0,2,0))

    def test_grouping_and_insert_column_order_do_not_misclassify(self):
        left="INSERT INTO \x60private_t\x60 (id,v) VALUES (1,'a'),(2,'b');\n"
        right="INSERT INTO \x60private_t\x60 (v,id) VALUES ('b',2);\nINSERT INTO \x60private_t\x60 (v,id) VALUES ('a',1);\n"
        v=self.compare(left,right)
        self.assertEqual(v["comparison"],"PK_LITERAL_EQUAL_NOT_VERIFIED")
        self.assertEqual(v["identical_key_identical_literals"],2)
        self.assertEqual(v["differing_pk_tables"],0)

    def test_composite_explicit_primary_key(self):
        table="CREATE TABLE \x60private_t\x60 (\x60tenant\x60 INT NOT NULL, \x60id\x60 INT NOT NULL, \x60body\x60 TEXT, PRIMARY KEY (\x60tenant\x60,\x60id\x60));\n"
        left="INSERT INTO \x60private_t\x60 VALUES (1,1,'same'),(1,2,'old');\n"
        right="INSERT INTO \x60private_t\x60 VALUES (1,1,'same'),(1,2,'new');\n"
        v=self.compare(left,right,schema_source=table,schema_target=table)
        self.assertEqual(v["same_key_changed_literals"],1)
        self.assertEqual(v["source_only_keys"],0)
        self.assertEqual(v["target_only_keys"],0)

    def test_missing_key_or_partial_data_never_passes(self):
        missing="CREATE TABLE \x60private_t\x60 (\x60id\x60 int NOT NULL,\x60v\x60 text);\n"
        out=self.compare("","",schema_source=missing,schema_target=missing)
        self.assertEqual(out["comparison"],"UNAVAILABLE")
        self.assertEqual(out["pk_tables_evaluable"],0)
        left="INSERT INTO \x60private_t\x60 (id) VALUES (1);\n"
        out=self.compare(left,left)
        self.assertEqual(out["comparison"],"UNAVAILABLE")
        self.assertEqual(out["reason"],"INCOMPLETE_ROW_COLUMNS_UNPROVEN")

    def test_unsupported_primary_key_prefix_inline_and_case_fail_closed(self):
        bad=[
            "CREATE TABLE \x60private_t\x60 (\x60id\x60 int PRIMARY KEY, \x60v\x60 text);\n",
            "CREATE TABLE \x60private_t\x60 (\x60id\x60 varchar(64), \x60v\x60 text, PRIMARY KEY (\x60id\x60(8)));\n",
            "CREATE TABLE \x60private_t\x60 (\x60id\x60 int, \x60v\x60 text, PRIMARY KEY (\x60id\x60 DESC));\n",
        ]
        for ddl in bad:
            with self.subTest(case=len(ddl)):
                out=self.compare("","",schema_source=ddl,schema_target=ddl)
                self.assertEqual(out["pk_tables_evaluable"],0)
                self.assertEqual(out["comparison"],"UNAVAILABLE")

    def test_duplicate_primary_keys_and_null_refused(self):
        duplicates="INSERT INTO \x60private_t\x60 VALUES (1,'a'),(1,'a');\n"
        ordinary="INSERT INTO \x60private_t\x60 VALUES (1,'a');\n"
        d=self.compare(duplicates,ordinary)
        self.assertEqual(d["comparison"],"UNAVAILABLE")
        self.assertEqual(d["reason"],"DUPLICATE_PRIMARY_KEY_IN_EXPORT")
        d=self.compare("INSERT INTO \x60private_t\x60 VALUES (NULL,'a');\n",ordinary)
        self.assertEqual(d["reason"],"PRIMARY_KEY_LITERAL_UNPROVEN")

    def test_unknown_statements_are_unavailable(self):
        ordinary="INSERT INTO \x60private_t\x60 VALUES (1,'a');\n"
        for bad in (
            "UPDATE \x60private_t\x60 SET id=2;\n",
            "DELETE FROM \x60private_t\x60 WHERE id=1;\n",
            "INSERT INTO \x60private_t\x60 SELECT 1,'a';\n",
            "INSERT INTO \x60private_t\x60 VALUES (1,CONCAT('a','b'));\n",
            "INSERT INTO \x60private_t\x60 VALUES (1,'x'); DROP TABLE \x60private_t\x60;\n",
        ):
            with self.subTest(case=bad[:24]):
                d=self.compare(bad,ordinary)
                self.assertEqual(d["comparison"],"UNAVAILABLE")
                self.assertNotIn("private_t",json.dumps(d))

    def test_sql_literal_representation_is_not_semantic_primary_key_equality(self):
        a="INSERT INTO \x60private_t\x60 VALUES (01,'v');\n"
        b="INSERT INTO \x60private_t\x60 VALUES (1,'v');\n"
        d=self.compare(a,b)
        self.assertEqual(d["comparison"],"PK_LITERAL_DIFFER")
        self.assertEqual((d["source_only_keys"],d["target_only_keys"]),(1,1))
        self.assertEqual(d["semantics"],"DUMP_SQL_LITERAL_PK_ONLY")

    def test_forty_two_tables_output_ordinal_only(self):
        def definitions():
            return "".join("CREATE TABLE \x60t_%02d\x60 (\x60id\x60 INT, \x60v\x60 TEXT, PRIMARY KEY (\x60id\x60));\n" % i for i in range(42))
        d=definitions()
        left="INSERT INTO \x60t_03\x60 VALUES (1,'original');\n"
        right="INSERT INTO \x60t_03\x60 VALUES (1,'edited');\n"
        r=self.compare(left,right,schema_source=d,schema_target=d)
        self.assertEqual(r["tables_examined"],42)
        self.assertEqual(r["differing_table_ordinals"][0]["table_ordinal"],4)
        self.assertNotIn("t_03",json.dumps(r))

    def test_limits_fail_closed(self):
        text="INSERT INTO \x60private_t\x60 VALUES (1,'a'),(2,'b');\n"
        with patch.object(pk,"MAX_ROWS",1):
            d=self.compare(text,text)
        self.assertEqual(d["reason"],"TOTAL_ROW_LIMIT")
        with patch.object(pk,"MAX_PK_TABLE_ROWS",1):
            d=self.compare(text,text)
        self.assertEqual(d["reason"],"TABLE_ROW_LIMIT")

    def test_schema_differences_refuse_before_row_matching(self):
        target=DDL.replace("text","varchar(42)")
        d=self.compare("","",schema_source=DDL,schema_target=target)
        self.assertEqual(d["comparison"],"UNAVAILABLE")
        self.assertEqual(d["pk_tables_evaluable"],0)


if __name__=="__main__":
    unittest.main()
