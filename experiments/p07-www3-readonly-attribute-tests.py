#!/usr/bin/env python3
"""Synthetic-only tests: redacted www3 SQL attribute classification."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).with_name("p07-www3-existing-scratch-parity-readonly.py")
spec = importlib.util.spec_from_file_location("p07_www3_readonly", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
classify = module._column_attribute_delta_groups


class AttributeEvidenceTests(unittest.TestCase):
    def test_default_change_does_not_misclassify_embedded_keyword(self):
        self.assertEqual(
            classify("varchar(20) NOT NULL DEFAULT 'COLLATE x'",
                     "varchar(20) NOT NULL DEFAULT 'COLLATE y'"),
            {"DEFAULT"},
        )

    def test_collation_delta(self):
        self.assertEqual(
            classify("varchar(20) COLLATE utf8mb4_general_ci",
                     "varchar(20) COLLATE utf8mb4_unicode_ci"),
            {"COLLATION"},
        )

    def test_charset_delta(self):
        self.assertEqual(
            classify("varchar(20) CHARACTER SET utf8mb4",
                     "varchar(20) CHARACTER SET latin1"),
            {"CHARSET"},
        )

    def test_nullability_delta(self):
        self.assertEqual(classify("int NOT NULL", "int NULL"), {"NULLABILITY"})

    def test_default_expression_delta(self):
        self.assertEqual(
            classify("int DEFAULT (uuid())", "int DEFAULT (now())"),
            {"DEFAULT"},
        )

    def test_unsigned_delta(self):
        self.assertEqual(
            classify("bigint UNSIGNED NOT NULL", "bigint NOT NULL"),
            {"UNSIGNED_ZEROFILL"},
        )

    def test_comment_literal_does_not_count_as_default(self):
        self.assertEqual(
            classify("text COMMENT 'DEFAULT a'", "text COMMENT 'DEFAULT b'"),
            {"COMMENT"},
        )

    def test_timestamp_on_update_delta(self):
        self.assertEqual(
            classify("timestamp ON UPDATE CURRENT_TIMESTAMP(6)",
                     "timestamp ON UPDATE CURRENT_TIMESTAMP(3)"),
            {"ON_UPDATE"},
        )

    def test_unparsed_constraint_fails_closed(self):
        self.assertEqual(
            classify("int NOT NULL CHECK (x > 0)",
                     "int NOT NULL CHECK (x > 1)"),
            {"OTHER_OR_UNPARSED"},
        )

    def test_multiple_changes_all_retained(self):
        self.assertEqual(
            classify("varchar(20) NOT NULL DEFAULT 'a' COLLATE abc",
                     "varchar(20) NULL DEFAULT 'b' COLLATE xyz"),
            {"NULLABILITY", "DEFAULT", "COLLATION"},
        )

    def test_no_delta_is_never_reported_as_approved(self):
        self.assertEqual(classify("int NOT NULL", "int NOT NULL"),
                         {"OTHER_OR_UNPARSED"})



class RiskDetailSyntheticTests(unittest.TestCase):
    def test_numeric_default_quotation_is_not_approved(self):
        self.assertEqual(
            module._attribute_detail_categories("int NOT NULL DEFAULT 0",
                                                "int NOT NULL DEFAULT '0'"),
            {"DEFAULT_NUMERIC_QUOTING_UNPROVEN"},
        )

    def test_changed_default_value_is_distinct_from_formatting(self):
        self.assertEqual(
            module._attribute_detail_categories("int DEFAULT 0", "int DEFAULT 1"),
            {"DEFAULT_EXPRESSION_OR_LITERAL_CHANGED"},
        )

    def test_missing_default_is_separate_blocker(self):
        self.assertEqual(
            module._attribute_detail_categories("int NOT NULL DEFAULT 0",
                                                "int NOT NULL"),
            {"DEFAULT_PRESENCE_OR_MULTIPLE"},
        )

    def test_on_update_precision_change_keeps_risk(self):
        self.assertEqual(
            module._attribute_detail_categories(
                "timestamp ON UPDATE CURRENT_TIMESTAMP(6)",
                "timestamp ON UPDATE CURRENT_TIMESTAMP(3)"),
            {"ON_UPDATE_EXPRESSION_OR_LITERAL_CHANGED"},
        )

    def test_on_update_removed_is_separate_blocker(self):
        self.assertEqual(
            module._attribute_detail_categories(
                "timestamp ON UPDATE CURRENT_TIMESTAMP",
                "timestamp"),
            {"ON_UPDATE_PRESENCE_OR_MULTIPLE"},
        )

    def test_unrecognized_sql_change_never_approved(self):
        self.assertEqual(
            module._attribute_detail_categories(
                "int CHECK (x > 0)", "int CHECK (x > 1)"),
            {"UNRECOGNIZED_TOKENS_CHANGED"},
        )

    def test_only_presentation_change_remains_unproven(self):
        self.assertEqual(
            module._attribute_detail_categories(
                "int DEFAULT 0", "int  DEFAULT 0"),
            {"PRESENTATION_OR_CASE_UNPROVEN"},
        )

    def test_literal_sql_keywords_do_not_escape_group(self):
        self.assertEqual(
            module._attribute_detail_categories(
                "text DEFAULT 'ON UPDATE source'",
                "text DEFAULT 'ON UPDATE target'"),
            {"DEFAULT_EXPRESSION_OR_LITERAL_CHANGED"},
        )

    def test_classification_never_executes_sql_or_requires_server(self):
        source="varchar(20) NOT NULL DEFAULT 'source'"
        target="varchar(20) DEFAULT 'target'"
        self.assertEqual(
            module._attribute_detail_categories(source, target),
            {"NULLABILITY_PRESENCE_OR_MULTIPLE",
             "DEFAULT_EXPRESSION_OR_LITERAL_CHANGED"},
        )

    def test_mysql8_to_mariadb_collation_is_not_approved(self):
        self.assertEqual(
            module._collation_risk_class(
                "ENGINE=InnoDB COLLATE=utf8mb4_0900_ai_ci;",
                "ENGINE=InnoDB COLLATE=utf8mb4_uca1400_ai_ci;"),
            "MYSQL0900_TO_UCA1400",
        )

    def test_different_collation_same_charset_still_risky(self):
        self.assertEqual(
            module._collation_risk_class(
                "COLLATE=utf8mb4_general_ci;",
                "COLLATE=utf8mb4_unicode_ci;"),
            "SAME_CHARSET_DIFFERENT_RULE",
        )

    def test_unknown_collation_does_not_become_safe(self):
        self.assertEqual(
            module._collation_risk_class("COLLATE=custom_a", "COLLATE=custom_b"),
            "OTHER_OR_UNPROVEN",
        )

    def test_missing_collation_is_not_approved(self):
        self.assertEqual(
            module._collation_risk_class("ENGINE=InnoDB", "COLLATE=utf8mb4_uca1400_ai_ci"),
            "TARGET_ONLY",
        )

    def test_multiple_collation_values_is_unproven(self):
        self.assertEqual(
            module._collation_risk_class(
                "COLLATE=utf8mb4_general_ci COLLATE=utf8mb4_bin",
                "COLLATE=utf8mb4_unicode_ci"),
            "OTHER_OR_UNPROVEN",
        )


if __name__ == "__main__":
    unittest.main()
