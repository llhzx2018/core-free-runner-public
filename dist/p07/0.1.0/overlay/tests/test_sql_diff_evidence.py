"""Advisory diagnostic must stay redacted and never approve SQL parity."""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import sql_diff_evidence as evidence


class SqlDiffEvidenceTests(unittest.TestCase):
    def probe(self, source: str, target: str):
        files = {"source.sql": source, "target.sql": target}
        with patch.object(
            evidence, "open",
            side_effect=lambda path, *_args, **_kw: io.StringIO(files[path.name]),
            create=True,
        ):
            return evidence.diagnostic(Path("source.sql"), Path("target.sql"))

    def test_safe_and_unrecognized_if_syntax_remain_distinct(self):
        prefix = (
            "CREATE TABLE `secret_table` (`id` INT NOT NULL);\n"
            "/*!50003 SELECT COUNT(*) INTO @found FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA='private_schema' AND TABLE_NAME='secret_table' */;\n"
        )
        suffix = (
            "/*!50003 PREPARE stmt FROM @query */;\n"
            "/*!50003 EXECUTE stmt */;\n"
            "/*!50003 DEALLOCATE PREPARE stmt */;\n"
        )
        safe = self.probe(
            prefix + "/*!50003 SET @query=IF(@found, 'SET @checked=1', 'SELECT 1') */;\n" + suffix,
            "CREATE TABLE `secret_table` (`id` INT NOT NULL);\n",
        )
        unknown = self.probe(
            prefix + '/*!50003 SET @query=IF(@found, "SET @checked=1", "SELECT 1") */;\n' + suffix,
            "CREATE TABLE `secret_table` (`id` INT NOT NULL);\n",
        )
        self.assertEqual(safe["dynamic_guard"]["recognized_safe"], 1)
        self.assertEqual(unknown["dynamic_guard"]["double_quoted_if"], 1)
        self.assertEqual(unknown["dynamic_guard"]["recognized_safe"], 0)
        self.assertEqual(unknown["verification"], "NOT_A_PASS_GATE")
        for record in (safe, unknown):
            self.assertNotIn("private_schema", json.dumps(record))
            self.assertNotIn("secret_table", json.dumps(record))
            self.assertNotIn("checked", json.dumps(record))

    def test_mysql_8x_versioned_set_guard_is_counted_not_silently_skipped(self):
        source = (
            "CREATE TABLE `private_table` (`id` INT NOT NULL);\n"
            "/*!80000 SET @private_query=IF(@private_found, "
            "'ALTER TABLE private_table ADD COLUMN secret INT', 'SELECT 1') */;\n"
        )
        result = self.probe(
            source, "CREATE TABLE `private_table` (`id` INT NOT NULL);\n",
        )
        self.assertEqual(result["dynamic_guard"]["recognized_unsafe"], 1)
        self.assertEqual(result["dynamic_guard"]["other_unknown_set"], 0)
        self.assertEqual(result["verification"], "NOT_A_PASS_GATE")
        self.assertNotIn("private_table", json.dumps(result))
        self.assertNotIn("secret", json.dumps(result))

    def test_column_index_and_table_option_differences_are_independent(self):
        left = (
            "CREATE TABLE `private_table` (\n"
            "`id` INT NOT NULL,\n"
            "`secret_column` TEXT,\n"
            "KEY `idx_a` (`id`)\n"
            ") ENGINE=InnoDB;\n"
        )
        right = left.replace("TEXT", "LONGTEXT").replace("idx_a", "idx_b").replace("InnoDB", "Aria")
        result = self.probe(left, right)
        self.assertEqual(result["schema_difference"]["mismatched_tables"], 1)
        self.assertEqual(result["schema_difference"]["changed_columns"], 1)
        self.assertEqual(result["schema_difference"]["changed_indexes"], 1)
        self.assertEqual(result["schema_difference"]["changed_options"], 1)
        for secret in ("private_table", "secret_column", "idx_a", "idx_b"):
            self.assertNotIn(secret, json.dumps(result))

    def test_known_integer_display_width_difference_remains_equal(self):
        source = "CREATE TABLE `private_table` (`id` BIGINT NOT NULL);\n"
        target = "CREATE TABLE `private_table` (`id` BIGINT(20) NOT NULL);\n"
        result = self.probe(source, target)
        self.assertEqual(result["schema_difference"]["mismatched_tables"], 0)

    def test_unbalanced_statement_is_not_a_positive_result(self):
        result = self.probe("CREATE TABLE `hidden` (`id` INT)", "")
        self.assertEqual(result["verification"], "UNAVAILABLE")
        self.assertNotIn("hidden", json.dumps(result))

    def test_non_table_schema_differences_are_counted(self):
        result = self.probe(
            "DROP TABLE IF EXISTS `secret`;\nCREATE TABLE `secret` (`id` INT);\n",
            "CREATE TABLE `secret` (`id` INT);\n",
        )
        self.assertEqual(result["schema_difference"]["other_schema_source_only"], 1)
        self.assertEqual(result["schema_difference"]["mismatched_tables"], 0)


if __name__ == "__main__":
    unittest.main()
