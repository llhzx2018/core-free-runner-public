"""Advisory diagnostic must stay redacted and never approve SQL parity."""
from __future__ import annotations

import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
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


    def test_three_unsafe_dynamic_ddl_branches_are_classified_without_names(self):
        source = "CREATE TABLE \u0060secret\u0060 (\u0060id\u0060 INT);\n"
        for idx, command in enumerate((
            "CREATE TABLE hidden (x INT)",
            "ALTER TABLE hidden ADD COLUMN token TEXT",
            "DROP TABLE hidden",
        ), start=1):
            source += (
                f"/*!80000 SET @q{idx}=IF(@flag, '{command}', 'SELECT 1') */;\n"
            )
        result = self.probe(source, "CREATE TABLE \u0060secret\u0060 (\u0060id\u0060 INT);\n")
        guard = result["dynamic_guard"]
        self.assertEqual(guard["recognized_unsafe"], 3)
        self.assertEqual(guard["unsafe_yes_branches"], 3)
        self.assertEqual(guard["unsafe_no_branches"], 0)
        self.assertEqual(guard["unsafe_branch_classes"]["DDL_CREATE"], 1)
        self.assertEqual(guard["unsafe_branch_classes"]["DDL_ALTER"], 1)
        self.assertEqual(guard["unsafe_branch_classes"]["DDL_DROP"], 1)
        self.assertEqual(result["schema"], "SQL_DIFF_EVIDENCE_V2")
        self.assertEqual(result["verification"], "NOT_A_PASS_GATE")
        for secret in ("hidden", "token", "secret", "flag", "q1"):
            self.assertNotIn(secret, json.dumps(result))

    def test_unsafe_data_and_session_classifications_do_not_authorize(self):
        source = (
            "CREATE TABLE \u0060private_table\u0060 (\u0060id\u0060 INT);\n"
            "/*!50003 SET @q=IF(@found, 'UPDATE private_table SET id=7', 'SET @x=1') */;\n"
            "/*!50003 SET @r=IF(@found, 'SET GLOBAL sql_notes=0', 'SELECT 1') */;\n"
        )
        result = self.probe(source, "CREATE TABLE \u0060private_table\u0060 (\u0060id\u0060 INT);\n")
        guard = result["dynamic_guard"]
        self.assertEqual(guard["recognized_unsafe"], 2)
        self.assertEqual(guard["unsafe_branch_classes"]["DATA_MUTATION"], 1)
        self.assertEqual(guard["unsafe_branch_classes"]["SESSION_UNPROVEN"], 1)
        self.assertEqual(guard["recognized_safe"], 0)
        self.assertEqual(result["verification"], "NOT_A_PASS_GATE")
        self.assertNotIn("private_table", json.dumps(result))

    def test_dml_fingerprint_equal_is_advisory_and_redacted(self):
        info = [
            {"objects": ["super_private_table"], "data_hash": "PRIVATE_HASH", "data_statements": 4},
            {"objects": ["super_private_table"], "data_hash": "PRIVATE_HASH", "data_statements": 4},
        ]
        with patch.object(evidence.verify, "sql_data_fingerprint", side_effect=info):
            result = evidence.data_content_evidence(Path("left.sql"), Path("right.sql"))
        self.assertEqual(result["comparison"], "FINGERPRINT_EQUAL_NOT_VERIFIED")
        self.assertEqual(result["source_dml_statements"], 4)
        self.assertEqual(result["target_dml_statements"], 4)
        self.assertNotIn("PRIVATE_HASH", json.dumps(result))
        self.assertNotIn("super_private_table", json.dumps(result))

    def test_dml_fingerprint_changed_or_empty_never_equals(self):
        base = {"objects": ["private"], "data_hash": "hash_a", "data_statements": 1}
        different = {"objects": ["private"], "data_hash": "hash_b", "data_statements": 1}
        with patch.object(evidence.verify, "sql_data_fingerprint", side_effect=[base, different]):
            changed = evidence.data_content_evidence(Path("left.sql"), Path("right.sql"))
        self.assertEqual(changed["comparison"], "FINGERPRINT_DIFFER")
        empty = {"objects": ["private"], "data_hash": "empty", "data_statements": 0}
        with patch.object(evidence.verify, "sql_data_fingerprint", side_effect=[empty, empty]):
            none = evidence.data_content_evidence(Path("left.sql"), Path("right.sql"))
        self.assertEqual(none["comparison"], "NO_DML_STATEMENTS")
        self.assertNotIn("private", json.dumps(changed))
        self.assertNotIn("private", json.dumps(none))

    def test_unavailable_data_fingerprint_does_not_erase_schema_evidence(self):
        with patch.object(evidence.verify, "sql_data_fingerprint",
                          side_effect=evidence.verify.RestoreVerifyError("private SQL string")):
            result = self.probe(
                "CREATE TABLE \u0060private\u0060 (\u0060id\u0060 INT);\n",
                "CREATE TABLE \u0060private\u0060 (\u0060id\u0060 INT);\n",
            )
        self.assertEqual(result["data_content"], {
            "comparison": "UNAVAILABLE",
            "source_reason": "OTHER_VERIFIER_FAILURE",
            "target_reason": "OTHER_VERIFIER_FAILURE",
        })
        self.assertEqual(result["schema_difference"]["mismatched_tables"], 0)
        self.assertEqual(result["verification"], "NOT_A_PASS_GATE")
        self.assertNotIn("private", json.dumps(result))


    def test_table_option_difference_has_redacted_reason_classes(self):
        base = "CREATE TABLE `private_table` (`id` INT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n"
        engine = base.replace("InnoDB", "Aria")
        result = self.probe(base, engine)
        opts = result["schema_difference"]
        self.assertEqual(opts["changed_options"], 1)
        self.assertEqual(opts["changed_option_classes"]["ENGINE"], 1)
        self.assertEqual(opts["changed_option_classes"]["OTHER_OR_UNPARSED"], 0)
        self.assertEqual(result["verification"], "NOT_A_PASS_GATE")
        other = self.probe(base, base.replace(" ENGINE=InnoDB", " ENGINE=InnoDB ROW_FORMAT=DYNAMIC"))
        self.assertEqual(other["schema_difference"]["changed_option_classes"]["ROW_FORMAT"], 1)
        unknown = self.probe(base, base.replace("utf8mb4;", "utf8mb4 COMMENT='private message';"))
        self.assertEqual(unknown["schema_difference"]["changed_option_classes"]["OTHER_OR_UNPARSED"], 1)
        self.assertNotIn("private_table", json.dumps(unknown))
        self.assertNotIn("private message", json.dumps(unknown))

    def test_unsafe_if_has_specific_redacted_reason_without_approval(self):
        source = "CREATE TABLE `private_table` (`id` INT);\n"
        source += "/*!50003 SET @a=IF(@flag, 'SET GLOBAL sql_notes=0', 'SELECT 1') */;\n"
        source += "/*!50003 SET @b=IF(@flag, 'SET SESSION group_concat_max_len=8', 'SELECT 1') */;\n"
        source += "/*!50003 SET @c=IF(@flag, 'SELECT secret FROM elsewhere', 'SELECT 1') */;\n"
        result = self.probe(source, "CREATE TABLE `private_table` (`id` INT);\n")
        guard = result["dynamic_guard"]
        reasons = guard["unsafe_branch_reasons"]
        self.assertEqual(guard["recognized_unsafe"], 3)
        self.assertEqual(reasons["GLOBAL_OR_PERSIST"], 1)
        self.assertEqual(reasons["SESSION_GRAMMAR_UNPROVEN"], 1)
        self.assertEqual(reasons["READ_GRAMMAR_UNPROVEN"], 1)
        self.assertEqual(sum(reasons.values()), 3)
        self.assertEqual(result["verification"], "NOT_A_PASS_GATE")
        self.assertNotIn("elsewhere", json.dumps(result))

    def test_multi_statement_branch_stays_unsafe_and_redacted(self):
        source = (
            "CREATE TABLE `private_table` (`id` INT);\n"
            "/*!50003 SET @a=IF(@flag, 'SET @x=1; DROP TABLE private_table', 'SELECT 1') */;\n"
        )
        result = self.probe(source, "CREATE TABLE `private_table` (`id` INT);\n")
        self.assertEqual(result["dynamic_guard"]["unsafe_branch_reasons"]["CONTROL_OR_MULTISTATEMENT"], 1)
        self.assertEqual(result["dynamic_guard"]["unsafe_control_or_multi"], 1)
        self.assertEqual(result["verification"], "NOT_A_PASS_GATE")

    def test_data_unavailable_reasons_are_source_target_specific_and_redacted(self):
        errors = [
            evidence.verify.RestoreVerifyError("multiline SQL data requires manual cross-engine verification"),
            evidence.verify.RestoreVerifyError("unrecognized SQL data command in cross-engine verification"),
        ]
        with patch.object(evidence.verify, "sql_data_fingerprint", side_effect=errors):
            result = evidence.data_content_evidence(Path("source.sql"), Path("target.sql"))
        self.assertEqual(result, {
            "comparison": "UNAVAILABLE",
            "source_reason": "MULTILINE_DML_UNPROVEN",
            "target_reason": "DML_COMMAND_UNRECOGNIZED",
        })
        with patch.object(evidence.verify, "sql_data_fingerprint", side_effect=[
            evidence.verify.RestoreVerifyError("private token 12345"),
            {"objects": [], "data_hash": "internal", "data_statements": 0},
        ]):
            unknown = evidence.data_content_evidence(Path("source.sql"), Path("target.sql"))
        self.assertEqual(unknown["source_reason"], "OTHER_VERIFIER_FAILURE")
        self.assertEqual(unknown["target_reason"], "NONE")
        self.assertNotIn("private token", json.dumps(unknown))

    def test_source_export_sanity_rejects_empty_and_corrupt_gzip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "source-good.sql.gz"
            with gzip.open(good, "wt", encoding="utf-8") as handle:
                handle.write(
                    "CREATE TABLE `one` (`id` INT);\n"
                    "INSERT INTO `one` VALUES (1);\n"
                    "CREATE TABLE `two` (`id` INT);\n"
                )
            self.assertEqual(evidence.require_nonempty_source_schema(good), 2)

            header_only = root / "source-header.sql.gz"
            with gzip.open(header_only, "wt", encoding="utf-8") as handle:
                handle.write("-- private header only\n")
            with self.assertRaisesRegex(
                evidence.AdvisoryDiagnosticUnavailable,
                "SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA",
            ):
                evidence.require_nonempty_source_schema(header_only)

            corrupt = root / "source-corrupt.sql.gz"
            corrupt.write_bytes(b"not a compressed SQL dump")
            with self.assertRaises(evidence.AdvisoryDiagnosticUnavailable):
                evidence.require_nonempty_source_schema(corrupt)

    def test_source_export_sanity_rejects_data_only_without_ddl(self):
        with tempfile.TemporaryDirectory() as directory:
            dump = Path(directory) / "private.sql.gz"
            with gzip.open(dump, "wt", encoding="utf-8") as handle:
                handle.write("INSERT INTO `private_table` VALUES (1);\n")
            with self.assertRaisesRegex(
                evidence.AdvisoryDiagnosticUnavailable,
                "SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA",
            ) as caught:
                evidence.require_nonempty_source_schema(dump)
            self.assertNotIn("private_table", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
