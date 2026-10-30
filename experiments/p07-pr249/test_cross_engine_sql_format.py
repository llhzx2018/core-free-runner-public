"""Known MySQL 8.4 -> MariaDB 11.8 dump-shape equivalence, fail closed."""
from __future__ import annotations

import gzip
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from server_migration_pull import PullMigrationError, compare_database_dumps, verify_engine

SOURCE = r"""
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!50503 SET NAMES utf8mb4 */;
CREATE DATABASE /*!32312 IF NOT EXISTS*/ \x60demo\x60 /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE \x60demo\x60;
DROP TABLE IF EXISTS \x60t0\x60;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE \x60t0\x60 (
  \x60id\x60 bigint unsigned NOT NULL AUTO_INCREMENT,
  \x60value\x60 longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (\x60id\x60),
  KEY \x60idx_value\x60 (\x60id\x60)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
LOCK TABLES \x60t0\x60 WRITE;
/*!40000 ALTER TABLE \x60t0\x60 DISABLE KEYS */;
INSERT INTO \x60t0\x60 VALUES (1,'single quote: \'quote\'');
/*!40000 ALTER TABLE \x60t0\x60 ENABLE KEYS */;
UNLOCK TABLES;
""".replace(r"\x60", "\x60")

TARGET = r"""
/*M!999999\- enable the sandbox mode */
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8mb4 */;
CREATE DATABASE /*!32312 IF NOT EXISTS*/ \x60demo\x60 /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */;
USE \x60demo\x60;
DROP TABLE IF EXISTS \x60t0\x60;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE \x60t0\x60 (
  \x60id\x60 bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  \x60value\x60 longtext DEFAULT NULL,
  PRIMARY KEY (\x60id\x60),
  KEY \x60idx_value\x60 (\x60id\x60)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
LOCK TABLES \x60t0\x60 WRITE;
/*!40000 ALTER TABLE \x60t0\x60 DISABLE KEYS */;
SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
INSERT INTO \x60t0\x60 VALUES
(1,'single quote: \'quote\'');
/*!40000 ALTER TABLE \x60t0\x60 ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
""".replace(r"\x60", "\x60")


class KnownDumpFormatVerificationTests(unittest.TestCase):
    def verify(self, source: str, target: str) -> str:
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "source.sql.gz"
            right = Path(directory) / "target.sql.gz"
            with gzip.open(left, "wt", encoding="utf-8") as handle:
                handle.write(source)
            with gzip.open(right, "wt", encoding="utf-8") as handle:
                handle.write(target)
            return compare_database_dumps(left, right)

    def diagnostic(self, source: str, target: str) -> str:
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "source.sql.gz"
            right = Path(directory) / "target.sql.gz"
            with gzip.open(left, "wt", encoding="utf-8") as handle:
                handle.write(source)
            with gzip.open(right, "wt", encoding="utf-8") as handle:
                handle.write(target)
            return verify_engine.sql_cross_engine_known_format_diagnostic(left, right)

    def test_dynamic_guard_flow_classification_is_redacted_and_fail_closed(self):
        safe = SOURCE + self._interleaved_session_guards()
        unsafe = safe.replace("'SET @checked=2'", "'ALTER TABLE t0 DROP COLUMN PRIVATE_VALUE'")
        missing = safe.replace("/*!50003 DEALLOCATE PREPARE stmt_b */;\n", "")
        for source, outcome, recognized in (
            (safe, "RECOGNIZED", 13),
            (unsafe, "UNSAFE_BRANCH", 0),
            (missing, "UNBALANCED_STAGES", 0),
        ):
            with self.subTest(outcome=outcome):
                with tempfile.TemporaryDirectory() as directory:
                    left = Path(directory) / "source.sql.gz"
                    with gzip.open(left, "wt", encoding="utf-8") as handle:
                        handle.write(source)
                    diagnostic = verify_engine.sql_dynamic_guard_flow_diagnostic(left)
                self.assertIn("SQL_GUARD_FLOW_V1", diagnostic)
                self.assertIn("assignment=3", diagnostic)
                self.assertIn(f"recognized={recognized}", diagnostic)
                self.assertIn(f"outcome={outcome}", diagnostic)
                for secret in ("PRIVATE_VALUE", "checked=2", "demo", "stmt_b"):
                    self.assertNotIn(secret, diagnostic)
        with self.assertRaisesRegex(PullMigrationError, r"SQL_GUARD_FLOW_V1.*outcome=UNSAFE_BRANCH") as raised:
            self.verify(unsafe, TARGET)
        self.assertNotIn("PRIVATE_VALUE", str(raised.exception))

    def test_dynamic_guard_flow_unknown_set_is_redacted(self):
        source = SOURCE + "/*!50003 SET @PRIVATE_TOKEN = UNKNOWN_SYNTAX('SECRET_VALUE') */;\n"
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "source.sql.gz"
            with gzip.open(left, "wt", encoding="utf-8") as handle:
                handle.write(source)
            diagnostic = verify_engine.sql_dynamic_guard_flow_diagnostic(left)
        self.assertIn("unknown_set=1", diagnostic)
        self.assertIn("outcome=UNKNOWN_CONTROL_GRAMMAR", diagnostic)
        self.assertNotIn("PRIVATE_TOKEN", diagnostic)
        self.assertNotIn("SECRET_VALUE", diagnostic)

    def test_private_schema_shape_diagnostic_emits_counts_only(self):
        source = SOURCE.replace(
            "\x60value\x60 longtext CHARACTER SET",
            "\x60flag\x60 tinyint NOT NULL DEFAULT '987654',\n"
            "  \x60value\x60 longtext CHARACTER SET",
        ) + "\n/*!50003 CREATE*/ /*!50017 DEFINER=\x60PRIVATE_USER\x60@\x60HOST\x60*/ /*!50003 TRIGGER private_trigger BEFORE INSERT ON x FOR EACH ROW SET @v=1 */;\n"
        target = TARGET.replace(
            "\x60value\x60 longtext DEFAULT NULL",
            "\x60flag\x60 tinyint(4) NOT NULL DEFAULT 987654,\n"
            "  \x60value\x60 longtext DEFAULT NULL",
        )
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "source.sql.gz"
            right = Path(directory) / "target.sql.gz"
            for path, content in ((left, source), (right, target)):
                with gzip.open(path, "wt", encoding="utf-8") as handle:
                    handle.write(content)
            diagnostic = verify_engine.sql_cross_engine_shape_diagnostic(left, right)
        self.assertIn("SQL_SHAPE_V1", diagnostic)
        self.assertIn("int_default_quoted=1:0", diagnostic)
        self.assertIn("int_default_plain=0:1", diagnostic)
        self.assertIn("guard_compound=1:0", diagnostic)
        self.assertIn("guard_compound_trigger=1:0", diagnostic)
        for secret in ("987654", "PRIVATE_USER", "private_trigger", "HOST"):
            self.assertNotIn(secret, diagnostic)

    def test_privacy_safe_profile_equivalent_known_format(self):
        diagnostic = self.diagnostic(SOURCE, TARGET)
        self.assertIn("SQL_CANON_V2 parse=OK:OK", diagnostic)
        self.assertIn("schema=EQUAL(", diagnostic)
        self.assertIn("data=EQUAL(", diagnostic)
        self.assertNotIn("demo", diagnostic)
        self.assertNotIn("single quote", diagnostic)

    def test_privacy_safe_profile_flags_data_mismatch(self):
        changed = TARGET.replace("single quote:", "PRIVATE_CHANGE_MARKER:")
        diagnostic = self.diagnostic(SOURCE, changed)
        self.assertIn("parse=OK:OK", diagnostic)
        self.assertIn("schema=EQUAL(", diagnostic)
        self.assertIn("data=DIFFER(", diagnostic)
        self.assertNotIn("PRIVATE_CHANGE_MARKER", diagnostic)
        with self.assertRaisesRegex(PullMigrationError, r"SQL_CANON_V2 parse=OK:OK.*data=DIFFER") as caught:
            self.verify(SOURCE, changed)
        self.assertNotIn("PRIVATE_CHANGE_MARKER", str(caught.exception))

    def test_privacy_safe_profile_flags_guarded_schema_change(self):
        changed = TARGET.replace("ENABLE KEYS", "DISABLE KEYS")
        diagnostic = self.diagnostic(SOURCE, changed)
        self.assertIn("versioned=DIFFER(", diagnostic)
        self.assertNotIn("ENABLE KEYS", diagnostic)

    def test_privacy_safe_profile_reports_parse_status_without_literals(self):
        broken = TARGET + "INSERT INTO `t0` VALUES ('PRIVATE_MARKER'" 
        diagnostic = self.diagnostic(SOURCE, broken)
        self.assertIn("parse=OK:UNTERMINATED_STATEMENT", diagnostic)
        self.assertNotIn("PRIVATE_MARKER", diagnostic)

    def _dynamic_session_guard(self) -> str:
        # The same statement/user-variable names are intentionally reused:
        # source MySQL dump controls can repeat a prepared session fragment.
        return (
            "/*!50003 SELECT COUNT(*) INTO @found FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA='demo' AND TABLE_NAME='t0' */;\n"
            "/*!50003 SET @query = IF(@found, 'SET @checked=1', 'SELECT 1') */;\n"
            "/*!50003 PREPARE stmt FROM @query */;\n"
            "/*!50003 EXECUTE stmt */;\n"
            "/*!50003 DEALLOCATE PREPARE stmt */;\n"
            "/*!50003 SET @query = IF(@found, 'SET @checked=2', 'SELECT 1') */;\n"
            "/*!50003 PREPARE stmt FROM @query */;\n"
            "/*!50003 EXECUTE stmt */;\n"
            "/*!50003 DEALLOCATE PREPARE stmt */;\n"
        )

    def _interleaved_session_guards(self) -> str:
        # The source-only control flow is one metadata probe, three guarded
        # assignments and exactly three matched PREPARE/EXECUTE/DEALLOCATE
        # cycles. Completion order can differ from assignment order.
        return (
            "/*!50003 SELECT COUNT(*) INTO @found FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA='demo' AND TABLE_NAME='t0' */;\n"
            "/*!50003 SET @query_a = IF(@found, 'SET @checked=1', 'SELECT 1') */;\n"
            "/*!50003 SET @query_b = IF(@found, 'SET @checked=2', 'SELECT 1') */;\n"
            "/*!50003 SET @query_c = IF(@found, 'SET @checked=3', 'SELECT 1') */;\n"
            "/*!50003 PREPARE stmt_a FROM @query_a */;\n"
            "/*!50003 PREPARE stmt_b FROM @query_b */;\n"
            "/*!50003 PREPARE stmt_c FROM @query_c */;\n"
            "/*!50003 EXECUTE stmt_c */;\n"
            "/*!50003 EXECUTE stmt_a */;\n"
            "/*!50003 EXECUTE stmt_b */;\n"
            "/*!50003 DEALLOCATE PREPARE stmt_b */;\n"
            "/*!50003 DEALLOCATE PREPARE stmt_c */;\n"
            "/*!50003 DEALLOCATE PREPARE stmt_a */;\n"
        )

    def test_interleaved_three_session_only_guards_are_format_metadata(self):
        self.assertEqual(
            self.verify(SOURCE + self._interleaved_session_guards(), TARGET),
            "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
        )

    def test_interleaved_guards_refuse_ddl_global_and_orphaned_activity(self):
        safe = self._interleaved_session_guards()
        examples = (
            safe.replace("'SET @checked=2'", "'ALTER TABLE t0 DROP COLUMN value'"),
            safe.replace("'SET @checked=2'", "'SET GLOBAL sql_log_bin=0'"),
            safe.replace("/*!50003 EXECUTE stmt_a */;\n", ""),
            safe.replace("/*!50003 PREPARE stmt_b FROM @query_b */;\n", ""),
            safe.replace("/*!50003 DEALLOCATE PREPARE stmt_c */;\n", ""),
            safe.replace("/*!50003 SET @query_c = IF", "/*!80003 SET @query_c = IF"),
            safe + "/*!50003 EXECUTE unexpected_stmt */;\n",
        )
        for item in examples:
            with self.subTest(item_size=len(item)):
                with self.assertRaises(PullMigrationError):
                    self.verify(SOURCE + item, TARGET)

    def test_interleaved_guards_never_hide_row_or_index_drift(self):
        safe_source = SOURCE + self._interleaved_session_guards()
        for target in (
            TARGET.replace("idx_value", "index_changed"),
            TARGET.replace("single quote:", "changed row:"),
        ):
            with self.assertRaises(PullMigrationError):
                self.verify(safe_source, target)

    def test_ordered_session_only_prepared_dump_control_is_format_metadata(self):
        source = SOURCE + self._dynamic_session_guard()
        self.assertEqual(
            self.verify(source, TARGET), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
        )

    def test_dynamic_dump_control_with_ddl_remains_blocked(self):
        source = SOURCE + self._dynamic_session_guard().replace(
            "'SET @checked=1'", "'ALTER TABLE t0 DROP COLUMN value'",
        )
        with self.assertRaises(PullMigrationError):
            self.verify(source, TARGET)

    def test_dynamic_dump_control_with_global_assignment_remains_blocked(self):
        source = SOURCE + self._dynamic_session_guard().replace(
            "'SET @checked=1'", "'SET GLOBAL sql_log_bin=0'",
        )
        with self.assertRaises(PullMigrationError):
            self.verify(source, TARGET)

    def test_dynamic_dump_control_unmatched_and_reordered_pairs_remain_blocked(self):
        source = SOURCE + self._dynamic_session_guard().replace(
            "/*!50003 DEALLOCATE PREPARE stmt */;\n", "", 1,
        )
        with self.assertRaises(PullMigrationError):
            self.verify(source, TARGET)

        source = SOURCE + self._dynamic_session_guard().replace(
            "/*!50003 EXECUTE stmt */;", "/*!50003 EXECUTE other_stmt */;", 1,
        )
        with self.assertRaises(PullMigrationError):
            self.verify(source, TARGET)

    def test_dynamic_dump_control_wrong_probe_or_version_remains_blocked(self):
        source = SOURCE + self._dynamic_session_guard().replace(
            "information_schema.TABLES", "private_table",
        )
        with self.assertRaises(PullMigrationError):
            self.verify(source, TARGET)
        source = SOURCE + self._dynamic_session_guard().replace("/*!50003", "/*!80003")
        with self.assertRaises(PullMigrationError):
            self.verify(source, TARGET)

    def test_dynamic_dump_control_never_masks_changed_schema_or_rows(self):
        source = SOURCE + self._dynamic_session_guard()
        self.assertEqual(
            self.verify(source, TARGET), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
        )
        with self.assertRaises(PullMigrationError):
            self.verify(source, TARGET.replace("idx_value", "idx_changed"))
        with self.assertRaises(PullMigrationError):
            self.verify(source, TARGET.replace("single quote:", "modified row:"))

    def test_whitelisted_high_version_session_only_is_export_metadata(self):
        source = SOURCE.replace("/*!50503 SET NAMES utf8mb4 */;", "/*!80015 SET NAMES utf8mb4 */;")
        self.assertNotEqual(source, SOURCE)
        self.assertEqual(self.verify(source, TARGET), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT")

    def test_unrecognized_high_version_guard_stays_blocked(self):
        target = TARGET + "/*!80015 SET @unknown_session=12345 */;\n"
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, target)

    def test_default_integer_widths_are_export_metadata(self):
        # MySQL 8.4 omits legacy widths; MariaDB 11.8 writes them back.
        source = SOURCE.replace(
            "\x60id\x60 bigint unsigned NOT NULL",
            "\x60id\x60 int unsigned NOT NULL",
        ).replace(
            "\x60value\x60 longtext CHARACTER SET",
            "\x60active\x60 tinyint NOT NULL,\n  \x60small\x60 smallint unsigned NOT NULL,\n"
            "  \x60medium\x60 mediumint NOT NULL,\n  \x60value\x60 longtext CHARACTER SET",
        )
        target = TARGET.replace(
            "\x60id\x60 bigint(20) unsigned NOT NULL",
            "\x60id\x60 int(10) unsigned NOT NULL",
        ).replace(
            "\x60value\x60 longtext DEFAULT NULL",
            "\x60active\x60 tinyint(4) NOT NULL,\n  \x60small\x60 smallint(5) unsigned NOT NULL,\n"
            "  \x60medium\x60 mediumint(9) NOT NULL,\n  \x60value\x60 longtext DEFAULT NULL",
        )
        self.assertNotEqual(source, SOURCE)
        self.assertNotEqual(target, TARGET)
        self.assertEqual(self.verify(source, target), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT")

    def test_integer_defaults_unquoted_by_mariadb_are_equal(self):
        # MariaDB 11.8's own compatibility guide documents that its
        # SHOW CREATE TABLE unquotes integer DEFAULT values printed by MySQL.
        source = SOURCE.replace(
            "\x60value\x60 longtext CHARACTER SET",
            "\x60flag\x60 tinyint NOT NULL DEFAULT '0',\n"
            "  \x60signed\x60 int NOT NULL DEFAULT '-4',\n"
            "  \x60value\x60 longtext CHARACTER SET",
        )
        target = TARGET.replace(
            "\x60value\x60 longtext DEFAULT NULL",
            "\x60flag\x60 tinyint(4) NOT NULL DEFAULT 0,\n"
            "  \x60signed\x60 int(11) NOT NULL DEFAULT -4,\n"
            "  \x60value\x60 longtext DEFAULT NULL",
        )
        self.assertEqual(self.verify(source, target), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT")

    def test_different_integer_default_value_still_blocks(self):
        source = SOURCE.replace(
            "\x60value\x60 longtext CHARACTER SET",
            "\x60flag\x60 tinyint NOT NULL DEFAULT '0',\n"
            "  \x60value\x60 longtext CHARACTER SET",
        )
        target = TARGET.replace(
            "\x60value\x60 longtext DEFAULT NULL",
            "\x60flag\x60 tinyint(4) NOT NULL DEFAULT 1,\n"
            "  \x60value\x60 longtext DEFAULT NULL",
        )
        with self.assertRaises(PullMigrationError):
            self.verify(source, target)

    def test_string_default_quotes_are_semantic(self):
        source = SOURCE.replace(
            "\x60value\x60 longtext CHARACTER SET",
            "\x60flag\x60 varchar(20) NOT NULL DEFAULT '0',\n"
            "  \x60value\x60 longtext CHARACTER SET",
        )
        target = TARGET.replace(
            "\x60value\x60 longtext DEFAULT NULL",
            "\x60flag\x60 varchar(20) NOT NULL DEFAULT 0,\n"
            "  \x60value\x60 longtext DEFAULT NULL",
        )
        with self.assertRaises(PullMigrationError):
            self.verify(source, target)

    def test_explicit_inherited_char_and_text_collations_are_equivalent(self):
        source = SOURCE.replace(
            "  PRIMARY KEY",
            "  \x60title\x60 varchar(180) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,"
            "\n  \x60flag\x60 char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,"
            "\n  \x60extra\x60 text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,"
            "\n  PRIMARY KEY",
        )
        target = TARGET.replace(
            "  PRIMARY KEY",
            "  \x60title\x60 varchar(180) NOT NULL,"
            "\n  \x60flag\x60 char(1) DEFAULT NULL,"
            "\n  \x60extra\x60 text NOT NULL,"
            "\n  PRIMARY KEY",
        )
        self.assertEqual(self.verify(source, target), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT")

    def test_cross_engine_numeric_defaults_exact_lexical_tokens_only(self):
        source = SOURCE.replace(
            "  PRIMARY KEY",
            "  \x60price\x60 decimal(9,2) DEFAULT '0.00',"
            "\n  \x60ratio\x60 double DEFAULT '-2.5',"
            "\n  PRIMARY KEY",
        )
        target = TARGET.replace(
            "  PRIMARY KEY",
            "  \x60price\x60 decimal(9,2) DEFAULT 0.00,"
            "\n  \x60ratio\x60 double DEFAULT -2.5,"
            "\n  PRIMARY KEY",
        )
        self.assertEqual(self.verify(source, target), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT")
        for bad in ("0.01", "1.00", "0", "00.00"):
            with self.subTest(bad=bad), self.assertRaises(PullMigrationError):
                self.verify(source, target.replace("DEFAULT 0.00,", f"DEFAULT {bad},"))
        with self.assertRaises(PullMigrationError):
            self.verify(source.replace("DEFAULT '0.00'", "DEFAULT '00.00'"), target)

    def test_fractional_numeric_default_spelling_on_numeric_type_variants(self):
        # The source-only quote is harmless only for a canonical, identical
        # numeric literal on a numeric column, even with legacy type syntax.
        source = SOURCE.replace(
            "  PRIMARY KEY",
            "  \x60int_fraction\x60 int DEFAULT '0.00',"
            "\n  \x60double_long\x60 double precision DEFAULT '-2.5',"
            "\n  \x60spaced_precision\x60 decimal(12, 6) NOT NULL DEFAULT '0.000000',"
            "\n  PRIMARY KEY",
        )
        target = TARGET.replace(
            "  PRIMARY KEY",
            "  \x60int_fraction\x60 int DEFAULT 0.00,"
            "\n  \x60double_long\x60 double precision DEFAULT -2.5,"
            "\n  \x60spaced_precision\x60 decimal(12, 6) NOT NULL DEFAULT 0.000000,"
            "\n  PRIMARY KEY",
        )
        self.assertEqual(
            self.verify(source, target), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
        )
        for bad in ("0.01", "1.00", "00.00", "0"):
            with self.subTest(bad=bad), self.assertRaises(PullMigrationError):
                self.verify(source, target.replace("DEFAULT 0.00,", f"DEFAULT {bad},"))
        bad_string_source = source.replace(
            "\x60int_fraction\x60 int DEFAULT '0.00'",
            "\x60int_fraction\x60 varchar(10) DEFAULT '0.00'",
        )
        bad_string_target = target.replace(
            "\x60int_fraction\x60 int DEFAULT 0.00",
            "\x60int_fraction\x60 varchar(10) DEFAULT 0.00",
        )
        with self.assertRaises(PullMigrationError):
            self.verify(bad_string_source, bad_string_target)

    def test_decimal_default_scanner_respects_column_boundaries_and_literals(self):
        # A DECIMAL column may include additional unchanged attributes before
        # its quoted numeric DEFAULT. Only the quote is export presentation.
        source = SOURCE.replace(
            "  PRIMARY KEY",
            "  \x60a\x60 decimal(18,8) NOT NULL COMMENT 'price (in cents), DEFAULT ''9.99''' DEFAULT '0.00000000',"
            "\n  \x60b\x60 decimal(12, 6) EXTRA_ATTR DEFAULT '-2.500000',"
            "\n  \x60c\x60 varchar(10) DEFAULT '0.00',"
            "\n  \x60d\x60 decimal(9,2) COMMENT 'DEFAULT ''8.88''',"
            "\n  PRIMARY KEY",
        )
        target = TARGET.replace(
            "  PRIMARY KEY",
            "  \x60a\x60 decimal(18,8) NOT NULL COMMENT 'price (in cents), DEFAULT ''9.99''' DEFAULT 0.00000000,"
            "\n  \x60b\x60 decimal(12, 6) EXTRA_ATTR DEFAULT -2.500000,"
            "\n  \x60c\x60 varchar(10) DEFAULT '0.00',"
            "\n  \x60d\x60 decimal(9,2) COMMENT 'DEFAULT ''8.88''',"
            "\n  PRIMARY KEY",
        )
        self.assertEqual(
            self.verify(source, target), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
        )
        # Material differences, noncanonical numerics and string defaults fail.
        for changed in (
            target.replace("DEFAULT 0.00000000,", "DEFAULT 0.00000001,"),
            target.replace("DEFAULT -2.500000,", "DEFAULT -2.600000,"),
            target.replace("KEY \x60idx_value\x60", "KEY \x60idx_changed\x60"),
            target.replace("DEFAULT '0.00',", "DEFAULT 0.00,"),
            target.replace("DEFAULT '0.00',", "DEFAULT '1.00',"),
            target.replace("COMMENT 'DEFAULT ''8.88'''", "COMMENT 'DEFAULT ''7.77'''"),
        ):
            with self.assertRaises(PullMigrationError):
                self.verify(source, changed)
        with self.assertRaises(PullMigrationError):
            self.verify(
                source.replace("DEFAULT '0.00000000',", "DEFAULT '00.00000000',"),
                target,
            )

    def test_inherited_charset_never_hides_explicit_collation_change(self):
        source = SOURCE.replace(
            "  PRIMARY KEY",
            "  \x60title\x60 varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,"
            "\n  PRIMARY KEY",
        )
        target = TARGET.replace(
            "  PRIMARY KEY",
            "  \x60title\x60 varchar(100),"
            "\n  PRIMARY KEY",
        )
        self.assertEqual(self.verify(source, target), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT")
        with self.assertRaises(PullMigrationError):
            self.verify(source.replace(
                "varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                "varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci",
            ), target)
        with self.assertRaises(PullMigrationError):
            self.verify(source.replace(
                "varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                "varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci",
            ), target)
        with self.assertRaises(PullMigrationError):
            self.verify(source.replace(
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,\n  PRIMARY KEY",
                "CHARACTER SET utf8mb4,\n  PRIMARY KEY",
            ), target)
        with self.assertRaises(PullMigrationError):
            self.verify(source, target.replace("COLLATE=utf8mb4_unicode_ci", "COLLATE=utf8mb4_general_ci"))

    def test_integer_leading_zero_default_not_collapsed(self):
        source = SOURCE.replace(
            "\x60value\x60 longtext CHARACTER SET",
            "\x60flag\x60 tinyint NOT NULL DEFAULT '00',\n"
            "  \x60value\x60 longtext CHARACTER SET",
        )
        target = TARGET.replace(
            "\x60value\x60 longtext DEFAULT NULL",
            "\x60flag\x60 tinyint(4) NOT NULL DEFAULT 0,\n"
            "  \x60value\x60 longtext DEFAULT NULL",
        )
        with self.assertRaises(PullMigrationError):
            self.verify(source, target)

    def test_nondefault_integer_widths_remain_strict(self):
        target = TARGET.replace("\x60id\x60 bigint(20) unsigned", "\x60id\x60 bigint(18) unsigned")
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, target)

    def test_unsigned_default_width_cannot_hide_zerofill(self):
        source = SOURCE.replace("\x60id\x60 bigint unsigned", "\x60id\x60 int unsigned")
        target = TARGET.replace("\x60id\x60 bigint(20) unsigned", "\x60id\x60 int(10) unsigned ZEROFILL")
        with self.assertRaises(PullMigrationError):
            self.verify(source, target)

    def test_guard_statement_shape_classification_is_redacted(self):
        source = SOURCE + "/*!50003 SET @hidden_var = 123456 */;\n"
        target = TARGET
        text = self.diagnostic(source, target)
        self.assertIn("guard_set=DIFFER(", text)
        self.assertNotIn("@hidden_var", text)
        self.assertNotIn("123456", text)

    def test_equivalent_full_schema_and_rows(self):
        self.assertEqual(
            self.verify(SOURCE, TARGET), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT"
        )

    def test_multiple_rows_cross_engine_line_wrap_are_equal(self):
        tick = lambda value: value.replace(r"\x60", "\x60")
        src = SOURCE.replace(
            tick(r"INSERT INTO \x60t0\x60 VALUES (1,'single quote: \'quote\'');"),
            tick(r"INSERT INTO \x60t0\x60 VALUES (1,'single quote: \'quote\''),(2,'second, data; unchanged');"),
        )
        dst = TARGET.replace(
            tick(r"INSERT INTO \x60t0\x60 VALUES") + "\n" + r"(1,'single quote: \'quote\'');",
            tick(r"INSERT INTO \x60t0\x60 VALUES") + "\n" +
            r"(1,'single quote: \'quote\'')," + "\n" +
            r"(2,'second, data; unchanged');",
        )
        self.assertNotEqual(src, SOURCE)
        self.assertNotEqual(dst, TARGET)
        self.assertEqual(self.verify(src, dst), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT")
        with self.assertRaises(PullMigrationError):
            self.verify(src, dst.replace("second, data;", "second, altered;"))


    def test_live_source_counter_drift_never_passes_as_dump_format(self):
        # A live old server can advance its next ID after the initial pull.
        # The next AUTO_INCREMENT value is material and is never normalized.
        drifted_source = SOURCE.replace(
            "AUTO_INCREMENT=2 DEFAULT", "AUTO_INCREMENT=900 DEFAULT",
        )
        self.assertNotEqual(drifted_source, SOURCE)
        with self.assertRaises(PullMigrationError):
            self.verify(drifted_source, TARGET)

    def test_new_live_source_rows_are_not_original_import_snapshot(self):
        # The unchanged import-time source snapshot is still equivalent.
        self.assertEqual(
            self.verify(SOURCE, TARGET), "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
        )
        # A fresh export performed later is not an import-time comparison.
        # Even when both dumps contain the same number of data statements,
        # changed row content and a later counter must remain a failure.
        live_source = SOURCE.replace(
            "AUTO_INCREMENT=2 DEFAULT", "AUTO_INCREMENT=900 DEFAULT",
        ).replace("single quote:", "new live content:")
        self.assertEqual(live_source.count("INSERT INTO"), SOURCE.count("INSERT INTO"))
        with self.assertRaises(PullMigrationError):
            self.verify(live_source, TARGET)

    def test_changed_data_literal_blocks(self):
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, TARGET.replace("single quote:", "altered quote:"))

    def test_lost_index_blocks(self):
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, TARGET.replace("KEY \x60idx_value\x60 (\x60id\x60)", "KEY \x60idx_other\x60 (\x60id\x60)"))

    def test_changed_collation_blocks(self):
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, TARGET.replace("COLLATE=utf8mb4_unicode_ci", "COLLATE=utf8mb4_general_ci"))

    def test_vendor_guarded_ddl_change_blocks(self):
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, TARGET.replace("ENABLE KEYS", "DISABLE KEYS"))

    def test_unknown_guard_does_not_disappear(self):
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, TARGET.replace("INSERT INTO", "/*!50000 SET @unsafe=1 */;\nINSERT INTO"))

    def test_noninherited_explicit_charset_does_not_disappear(self):
        target = TARGET.replace("longtext DEFAULT NULL", "longtext CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci")
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, target)

    def test_unterminated_data_literal_blocks(self):
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, TARGET.replace("single quote: \\'quote\\'", "broken ' literal"))

    def test_zerofill_display_width_not_normalized(self):
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, TARGET.replace("bigint(20) unsigned", "bigint(20) ZEROFILL"))

    def test_session_names_charset_does_not_disappear(self):
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, TARGET.replace("SET NAMES utf8mb4", "SET NAMES latin1"))

    def test_zerofill_display_width_is_not_harmless(self):
        source = SOURCE.replace("bigint unsigned NOT NULL", "bigint unsigned ZEROFILL NOT NULL")
        target = TARGET.replace("bigint(20) unsigned NOT NULL", "bigint(20) unsigned ZEROFILL NOT NULL")
        with self.assertRaises(PullMigrationError):
            self.verify(source, target)

    def test_unmatched_trigger_blocks(self):
        with self.assertRaises(PullMigrationError):
            self.verify(SOURCE, TARGET + "CREATE TRIGGER bogus BEFORE INSERT ON \x60t0\x60 FOR EACH ROW SET @x=1;\n")


if __name__ == "__main__":
    unittest.main()
