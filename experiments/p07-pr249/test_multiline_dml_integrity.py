"""Strict multiline INSERT recognition: only exact logical data, fail closed."""
from __future__ import annotations

import gzip
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import verify

SCHEMA = "CREATE TABLE \x60secret\x60 (\x60id\x60 INT, \x60body\x60 TEXT);\n"


class MultilineDataIntegrityTests(unittest.TestCase):
    def fingerprint(self, data: str, zipped: bool = True):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / ("private.sql.gz" if zipped else "private.sql")
            if zipped:
                with gzip.open(path, "wt", encoding="utf-8") as handle:
                    handle.write(data)
            else:
                path.write_text(data, encoding="utf-8")
            return verify.sql_data_fingerprint(path)

    def test_multiline_values_whitespace_equivalent_to_single_line(self):
        left = SCHEMA + "INSERT INTO \x60secret\x60 VALUES (1,'first'),(2,'semi;colon');\n"
        right = SCHEMA + "INSERT INTO \x60secret\x60 VALUES\n(1, 'first'),\n(2, 'semi;colon');\n"
        self.assertEqual(self.fingerprint(left), self.fingerprint(right))
        self.assertEqual(self.fingerprint(left)["data_statements"], 1)

    def test_multiple_rows_and_statements_preserve_count(self):
        base = SCHEMA + "INSERT INTO \x60secret\x60 VALUES (1,'x');\nINSERT INTO \x60secret\x60 VALUES\n(2, 'y');\n"
        same_other_order = SCHEMA + "INSERT INTO \x60secret\x60 VALUES (2,'y');\nINSERT INTO \x60secret\x60 VALUES (1,'x');\n"
        self.assertEqual(self.fingerprint(base), self.fingerprint(same_other_order))
        self.assertEqual(self.fingerprint(base)["data_statements"], 2)
        different = base.replace("'y'", "'z'")
        self.assertNotEqual(self.fingerprint(base), self.fingerprint(different))

    def test_changed_or_missing_row_is_never_equal(self):
        source = SCHEMA + "INSERT INTO \x60secret\x60 VALUES\n(1,'unmodified'),\n(2,'same');\n"
        for target in (
            source.replace("unmodified", "tampered"),
            source.replace(",\n(2,'same')", ""),
            source + "INSERT INTO \x60secret\x60 VALUES (3,'extra');\n",
            source.replace("2,'same'", "1,'same'"),
        ):
            with self.subTest(target=target[-45:]):
                self.assertNotEqual(self.fingerprint(source), self.fingerprint(target))

    def test_escaped_quotes_backslash_commas_and_semicolon(self):
        source = SCHEMA + r"INSERT INTO \x60secret\x60 VALUES (1,'it\'s ; hello, world \\bye');" + "\n"
        target = SCHEMA + r"INSERT INTO \x60secret\x60 VALUES" + "\n" + r"(1,'it\'s ; hello, world \\bye');" + "\n"
        self.assertEqual(self.fingerprint(source), self.fingerprint(target))
        other = target.replace(r"\\bye", r"\\changed")
        self.assertNotEqual(self.fingerprint(source), self.fingerprint(other))

    def test_unknown_commands_and_multiple_statement_injection_fail(self):
        cases = (
            "INSERT INTO \x60secret\x60 SELECT * FROM \x60other\x60;\n",
            "UPDATE \x60secret\x60 SET \x60id\x60=4;\n",
            "DELETE FROM \x60secret\x60;\n",
            "INSERT INTO \x60secret\x60 VALUES (1,'x'); DROP TABLE \x60secret\x60;\n",
            "INSERT INTO \x60secret\x60 VALUES (1,'x');INSERT INTO \x60secret\x60 VALUES (2,'y');\n",
            "INSERT INTO \x60secret\x60 VALUES (1,'x' /*comment*/);\n",
            "INSERT INTO \x60secret\x60 VALUES (1,'x') #comment\n;\n",
            "INSERT INTO \x60secret\x60 VALUES (1,'x') --comment\n;\n",
        )
        for bad in cases:
            with self.subTest(bad=bad[:40]):
                with self.assertRaises(verify.RestoreVerifyError):
                    self.fingerprint(SCHEMA + bad)

    def test_unterminated_or_split_literal_refused(self):
        cases = (
            "INSERT INTO \x60secret\x60 VALUES\n(1,'x')\n",
            "INSERT INTO \x60secret\x60 VALUES (1,'unterminated\nstill quoted');\n",
            "INSERT INTO \x60secret\x60 VALUES (1,'escape\\\ncontinued');\n",
            "INSERT INTO \x60secret\x60 VALUES (1,'semi;literal'); INSERT INTO \x60secret\x60 VALUES (2,'x');",
        )
        for bad in cases:
            with self.subTest(bad=bad[:45]):
                with self.assertRaises(verify.RestoreVerifyError):
                    self.fingerprint(SCHEMA + bad)

    def test_size_limit_is_fail_closed(self):
        with patch.object(verify, "_DATA_FINGERPRINT_MAX_STATEMENT", 24):
            with self.assertRaisesRegex(verify.RestoreVerifyError, "exceeds safe limit"):
                self.fingerprint(SCHEMA + "INSERT INTO \x60secret\x60 VALUES (12345, 'long');\n")

    def test_malformed_gzip_and_unproven_grammar_not_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            bad = Path(root) / "broken.sql.gz"
            bad.write_bytes(b"not gzip")
            with self.assertRaises(verify.RestoreVerifyError):
                verify.sql_data_fingerprint(bad)
        with self.assertRaisesRegex(verify.RestoreVerifyError, "grammar is unproven"):
            self.fingerprint(SCHEMA + "INSERT INTO \x60secret\x60 (id,body) SELECT 1,'x';\n")

    def test_quoted_multiline_never_hides_real_data_change(self):
        source = SCHEMA + "INSERT INTO \x60secret\x60 VALUES (1,'x');\n"
        changed = SCHEMA + "INSERT INTO \x60secret\x60 VALUES\n(1,'x ');\n"
        self.assertNotEqual(self.fingerprint(source), self.fingerprint(changed))

    def test_plain_and_gz_have_identical_content_fingerprint(self):
        dump = SCHEMA + "INSERT INTO \x60secret\x60 VALUES\n(1,'x'),\n(2,'y');\n"
        self.assertEqual(self.fingerprint(dump, zipped=True), self.fingerprint(dump, zipped=False))


if __name__ == "__main__":
    unittest.main()
