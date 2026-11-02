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


if __name__ == "__main__":
    unittest.main()
