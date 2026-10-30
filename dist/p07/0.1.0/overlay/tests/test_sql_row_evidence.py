"""Synthetic privacy-safe row-tuple comparison cases; never run on real DB."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import sql_row_evidence as rows
import sql_diff_evidence as evidence

BASE = "CREATE TABLE \x60private_orders\x60 (\x60id\x60 INT, \x60v\x60 TEXT);\n"
SECOND = "CREATE TABLE \x60private_empty\x60 (\x60id\x60 INT);\n"
SOURCE = BASE + SECOND + "INSERT INTO \x60private_orders\x60 VALUES (1,'a'),(2,'b');\n"
SAME_DIFFERENT_GROUPING = (
    BASE + SECOND + "INSERT INTO \x60private_orders\x60 VALUES\n(2,'b');\n"
    + "INSERT INTO \x60private_orders\x60 VALUES\n(1,'a');\n"
)


class SQLRowEvidenceTests(unittest.TestCase):
    def check(self, source: str, target: str, *, include_full: bool = False):
        with tempfile.TemporaryDirectory() as directory:
            a = Path(directory) / "source.sql.gz"
            b = Path(directory) / "target.sql.gz"
            for file, content in ((a, source), (b, target)):
                with gzip.open(file, "wt", encoding="utf-8") as out:
                    out.write(content)
            names = {"private_empty", "private_orders"}
            result = rows.diagnostic(a, b, names, names)
            if include_full:
                result = (result, evidence.diagnostic(a, b))
            return result

    def assert_private(self, result):
        serialized = json.dumps(result, ensure_ascii=False)
        for secret in ("private_orders", "private_empty", "secret-token", "'a'", "'b'"):
            self.assertNotIn(secret, serialized)

    def test_grouping_and_statement_order_do_not_hide_same_rows(self):
        result, full = self.check(SOURCE, SAME_DIFFERENT_GROUPING, include_full=True)
        self.assertEqual(result["comparison"], "ROW_TUPLES_EQUAL_NOT_VERIFIED")
        self.assertEqual(result["source_row_tuples"], 2)
        self.assertEqual(result["target_row_tuples"], 2)
        self.assertEqual(result["differing_tables"], 0)
        self.assertEqual(result["tables_examined"], 2)
        self.assertEqual(full["data_content"]["comparison"], "FINGERPRINT_DIFFER")
        self.assertEqual(full["row_tuples"]["comparison"], "ROW_TUPLES_EQUAL_NOT_VERIFIED")
        self.assertEqual(full["verification"], "NOT_A_PASS_GATE")
        self.assert_private(full)

    def test_one_changed_literal_is_localized_with_ordinal_not_name(self):
        changed = SAME_DIFFERENT_GROUPING.replace("'a'", "'changed'")
        result = self.check(SOURCE, changed)
        self.assertEqual(result["comparison"], "ROW_TUPLES_DIFFER")
        self.assertEqual(result["same_count_content_drift_tables"], 1)
        self.assertEqual(result["row_count_drift_tables"], 0)
        self.assertEqual(result["differing_table_ordinals"], [
            {"table_ordinal": 2, "source_rows": 2, "target_rows": 2,
             "difference_class": "ROW_CONTENT_DIFFER"},
        ])
        self.assert_private(result)

    def test_missing_row_or_extra_duplicate_does_not_equal(self):
        examples = (
            BASE + SECOND + "INSERT INTO \x60private_orders\x60 VALUES (1,'a');\n",
            SOURCE + "INSERT INTO \x60private_orders\x60 VALUES (1,'a');\n",
            SOURCE.replace("(2,'b')", "(1,'a')"),
        )
        for changed in examples:
            with self.subTest(case=len(changed)):
                result = self.check(SOURCE, changed)
                self.assertEqual(result["comparison"], "ROW_TUPLES_DIFFER")
                self.assertGreater(result["row_count_drift_tables"] +
                                   result["same_count_content_drift_tables"], 0)

    def test_quoted_semicolons_commas_escaped_quotes_are_literal_bytes(self):
        payload = r"INSERT INTO \x60private_orders\x60 VALUES (1,'it\'s ; c,\\d');".replace(r"\x60", "\x60")
        same = payload.replace("VALUES ", "VALUES\n")
        first = BASE + SECOND + payload + "\n"
        second = BASE + SECOND + same + "\n"
        self.assertEqual(self.check(first, second)["comparison"], "ROW_TUPLES_EQUAL_NOT_VERIFIED")
        changed = second.replace(r"\\d", r"\\e")
        self.assertEqual(self.check(first, changed)["comparison"], "ROW_TUPLES_DIFFER")

    def test_column_orders_and_insert_modes_are_not_equivalent(self):
        col = BASE + SECOND + "INSERT INTO \x60private_orders\x60 (id,v) VALUES (1,'a');\n"
        changed_order = BASE + SECOND + "INSERT INTO \x60private_orders\x60 (v,id) VALUES (1,'a');\n"
        self.assertEqual(self.check(col, changed_order)["comparison"], "ROW_TUPLES_DIFFER")
        replace = col.replace("INSERT INTO", "REPLACE INTO")
        self.assertEqual(self.check(col, replace)["comparison"], "ROW_TUPLES_DIFFER")
        no_columns = col.replace(" (id,v)", "")
        self.assertEqual(self.check(col, no_columns)["comparison"], "ROW_TUPLES_DIFFER")

    def test_genuine_mutating_sql_or_insert_select_does_not_fall_back_to_equality(self):
        bad = (
            "INSERT INTO \x60private_orders\x60 SELECT 1,'a';",
            "UPDATE \x60private_orders\x60 SET id=2;",
            "DELETE FROM \x60private_orders\x60;",
            "LOAD DATA INFILE '/tmp/secret-token' INTO TABLE \x60private_orders\x60;",
            "INSERT INTO \x60private_orders\x60 VALUES (1,'a'); DELETE FROM \x60private_orders\x60;",
            "INSERT INTO \x60private_orders\x60 VALUES (1,CONCAT('a','b'));",
            "INSERT INTO \x60private_orders\x60 VALUES (1,'a' /* private comment */);",
            "INSERT INTO \x60private_orders\x60 VALUES (1,'a')--private-comment\n;",
            "INSERT INTO \x60private_orders\x60 VALUES (1,'a') # private-comment\n;",
        )
        for sql in bad:
            with self.subTest(case=sql[:25]):
                result = self.check(SOURCE, BASE + SECOND + sql + "\n")
                self.assertEqual(result["comparison"], "UNAVAILABLE")
                self.assert_private(result)

    def test_incomplete_or_multiline_quoted_data_is_unproven(self):
        examples = (
            "INSERT INTO \x60private_orders\x60 VALUES (1,'a')",
            "INSERT INTO \x60private_orders\x60 VALUES (1,'a\nnew line');",
            "INSERT INTO \x60private_orders\x60 VALUES (1,'a\\\nnew line');",
            "INSERT INTO \x60private_orders\x60 VALUES (1,'a'),",
            "INSERT INTO \x60private_orders\x60 VALUES (1, (SELECT 2));",
        )
        for sql in examples:
            with self.subTest(sql=sql[:30]):
                result = self.check(SOURCE, BASE + SECOND + sql + "\n")
                self.assertEqual(result["comparison"], "UNAVAILABLE")

    def test_unknown_table_identity_never_approves(self):
        target = BASE + SECOND + "INSERT INTO \x60not_in_schema\x60 VALUES (1,'x');\n"
        result = self.check(SOURCE, target)
        self.assertEqual(result, {
            "comparison": "UNAVAILABLE", "reason": "ROW_REFERENCES_UNKNOWN_TABLE",
        })

    def test_extra_or_missing_schema_table_is_unavailable(self):
        with tempfile.TemporaryDirectory() as root:
            left = Path(root) / "left.sql.gz"
            right = Path(root) / "right.sql.gz"
            for p in (left, right):
                with gzip.open(p, "wt", encoding="utf-8") as out:
                    out.write(SOURCE)
            self.assertEqual(rows.diagnostic(left, right, {"a"}, {"b"}),
                             {"comparison": "UNAVAILABLE", "reason": "TABLE_IDENTITY_UNPROVEN"})

    def test_zero_rows_are_not_promoted_to_proof(self):
        result = self.check(BASE + SECOND, BASE + SECOND)
        self.assertEqual(result["comparison"], "NO_INSERT_ROWS")
        self.assertEqual(result["verification"], "NOT_A_PASS_GATE")

    def test_forty_two_tables_locate_change_without_exposing_names(self):
        defs = "".join("CREATE TABLE \x60private_%02d\x60 (\x60id\x60 INT);\n" % i for i in range(42))
        left = defs + "INSERT INTO \x60private_33\x60 VALUES (7);\n"
        right = defs + "INSERT INTO \x60private_33\x60 VALUES (8);\n"
        with tempfile.TemporaryDirectory() as root:
            a = Path(root) / "a.sql.gz"
            b = Path(root) / "b.sql.gz"
            for path, content in ((a, left), (b, right)):
                with gzip.open(path, "wt", encoding="utf-8") as out:
                    out.write(content)
            names = {"private_%02d" % i for i in range(42)}
            result = rows.diagnostic(a, b, names, names)
        self.assertEqual(result["tables_examined"], 42)
        self.assertEqual(result["differing_tables"], 1)
        self.assertEqual(result["differing_table_ordinals"][0]["table_ordinal"], 34)
        self.assert_private(result)

    def test_statement_size_is_bounded_and_error_privacy_safe(self):
        with patch.object(rows, "_LIMIT", 24):
            result = self.check(SOURCE, SAME_DIFFERENT_GROUPING)
        self.assertEqual(result, {
            "comparison": "UNAVAILABLE", "reason": "STATEMENT_TOO_LARGE",
        })


if __name__ == "__main__":
    unittest.main()
