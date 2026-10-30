"""Exact multiset instance counts, private evidence and conservative denial."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import sql_multiset_evidence as multi
import sql_diff_evidence as whole

DDL = "CREATE TABLE \x60table_private\x60 (\x60id\x60 INT, \x60payload\x60 TEXT);\n"
D1 = "INSERT INTO \x60table_private\x60 VALUES (1,'a'),(2,'b'),(3,'c');\n"


class MultisetEvidenceTests(unittest.TestCase):
    def compare(self, left, right, whole_diagnostic=False):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d)/"source.sql.gz", Path(d)/"target.sql.gz"
            for f, body in ((source,DDL+left), (target,DDL+right)):
                with gzip.open(f,"wt",encoding="utf-8") as out:
                    out.write(body)
            names = {"table_private"}
            return (whole.diagnostic(source,target) if whole_diagnostic
                    else multi.diagnostic(source,target,names,names))

    def test_only_two_extra_target_records(self):
        left = "INSERT INTO \x60table_private\x60 VALUES (1,'a'),(2,'b');\n"
        right = left.replace("(2,'b')", "(2,'b'),(3,'c'),(4,'d')")
        evidence=self.compare(left,right)
        self.assertEqual(evidence["source_only_tuple_instances"],0)
        self.assertEqual(evidence["target_only_tuple_instances"],2)
        self.assertEqual(evidence["shared_tuple_instances"],2)
        self.assertEqual(evidence["differing_table_ordinals"][0]["difference_class"],
                         "TARGET_EXTRA_ONLY")
        self.assertEqual(evidence["verification"],"NOT_A_PASS_GATE")
        self.assertNotIn("table_private",str(evidence))
        self.assertNotIn("'d'",str(evidence))

    def test_net_plus_two_can_hide_large_bidirectional_difference(self):
        left="INSERT INTO \x60table_private\x60 VALUES (1,'a'),(2,'b'),(3,'c'),(4,'d');\n"
        right="INSERT INTO \x60table_private\x60 VALUES (1,'a'),(5,'e'),(6,'f'),(7,'g'),(8,'h'),(9,'i');\n"
        evidence=self.compare(left,right)
        self.assertEqual(evidence["source_only_tuple_instances"],3)
        self.assertEqual(evidence["target_only_tuple_instances"],5)
        self.assertEqual(evidence["shared_tuple_instances"],1)
        self.assertEqual(evidence["differing_table_ordinals"][0]["difference_class"],
                         "BIDIRECTIONAL_DIFFERENCE")

    def test_duplicate_tuple_multiplicity_not_lost(self):
        left="INSERT INTO \x60table_private\x60 VALUES (1,'a'),(1,'a');\n"
        right="INSERT INTO \x60table_private\x60 VALUES (1,'a');\n"
        result=self.compare(left,right)
        self.assertEqual(result["source_only_tuple_instances"],1)
        self.assertEqual(result["target_only_tuple_instances"],0)
        self.assertEqual(result["shared_tuple_instances"],1)
        self.assertEqual(result["differing_table_ordinals"][0]["difference_class"],
                         "SOURCE_EXTRA_ONLY")

    def test_group_and_statement_order_do_not_matter(self):
        src="INSERT INTO \x60table_private\x60 VALUES (1,'a'),(2,'b');\n"
        dest="INSERT INTO \x60table_private\x60 VALUES\n(2,'b');\nINSERT INTO \x60table_private\x60 VALUES (1,'a');\n"
        output=self.compare(src,dest,whole_diagnostic=True)
        self.assertEqual(output["row_multiset"]["comparison"],
                         "ROW_MULTISET_EQUAL_NOT_VERIFIED")
        self.assertEqual(output["row_tuples"]["comparison"],
                         "ROW_TUPLES_EQUAL_NOT_VERIFIED")
        self.assertEqual(output["data_content"]["comparison"],"FINGERPRINT_DIFFER")
        self.assertEqual(output["verification"],"NOT_A_PASS_GATE")
        self.assertNotIn("table_private",json.dumps(output))

    def test_changed_field_even_with_same_count(self):
        src="INSERT INTO \x60table_private\x60 VALUES (1,'a'),(2,'b');\n"
        dest=src.replace("'b'","'changed-secret'")
        x=self.compare(src,dest)
        self.assertEqual(x["source_only_tuple_instances"],1)
        self.assertEqual(x["target_only_tuple_instances"],1)
        self.assertNotIn("changed-secret",json.dumps(x))

    def test_unknown_dml_and_sql_injection_fail_closed(self):
        examples=(
            "INSERT INTO \x60table_private\x60 SELECT 1,'p';\n",
            "DELETE FROM \x60table_private\x60;\n",
            "UPDATE \x60table_private\x60 SET id=1;\n",
            "INSERT INTO \x60table_private\x60 VALUES (1,'p'); DROP TABLE \x60table_private\x60;\n",
            "INSERT INTO \x60table_private\x60 VALUES (1,CONCAT('p','q'));\n",
            "INSERT INTO \x60table_private\x60 VALUES (1,'q\nr');\n",
        )
        for bad in examples:
            with self.subTest(item=bad[:20]):
                result=self.compare(D1,bad)
                self.assertEqual(result["comparison"],"UNAVAILABLE")
                self.assertNotIn("table_private",json.dumps(result))

    def test_table_identity_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"dump.sql.gz"
            with gzip.open(p,"wt",encoding="utf-8") as out:out.write(DDL+D1)
            result=multi.diagnostic(p,p,{"x"},{"y"})
            self.assertEqual(result["comparison"],"UNAVAILABLE")
            self.assertEqual(result["reason"],"TABLE_IDENTITY_UNPROVEN")

    def test_cardinality_limit_refused_without_mutating_outputs(self):
        with patch.object(multi,"MAX_DISTINCT_ROWS",1):
            r=self.compare(D1,D1)
        self.assertEqual(r,{"comparison":"UNAVAILABLE","reason":"DISTINCT_ROW_LIMIT"})
        with patch.object(multi,"MAX_TOTAL_ROWS",2):
            r=self.compare(D1,D1)
        self.assertEqual(r,{"comparison":"UNAVAILABLE","reason":"TOTAL_ROW_LIMIT"})

    def test_no_records_is_not_positive_verification(self):
        r=self.compare("","")
        self.assertEqual(r["comparison"],"NO_INSERT_ROWS")
        self.assertEqual(r["verification"],"NOT_A_PASS_GATE")


if __name__=="__main__":
    unittest.main()
