"""P07 conditional SQL: strictly harmless single-command guarded session statements."""
from __future__ import annotations
import gzip
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import verify
import server_migration_pull as pull


class GuardedSessionStatementsTest(unittest.TestCase):
    def test_advisory_comparator_refuses_to_promote_even_exact_sql(self):
        source_sql="CREATE TABLE t (id int);\nINSERT INTO t VALUES (1);\n"
        with tempfile.TemporaryDirectory() as directory:
            left,right=Path(directory)/"source.sql.gz",Path(directory)/"target.sql.gz"
            for p in (left,right):
                with gzip.open(p,"wt",encoding="utf-8") as output:
                    output.write(source_sql)
            outcome=pull.guarded_export_comparison_advisory(left,right)
            self.assertEqual(outcome["status"],"MATCH_ADVISORY_NOT_MIGRATION_PASS")
            self.assertEqual(outcome["comparison_mode"],"CANONICAL_SQL_EXACT")
            self.assertFalse(outcome["cutover_allowed"])
            with gzip.open(right,"wt",encoding="utf-8") as output:
                output.write("CREATE TABLE t (id int, note varchar(20));\n"
                             "INSERT INTO t VALUES (1);\n")
            difference=pull.guarded_export_comparison_advisory(left,right)
            self.assertEqual(difference["status"],"BLOCKED")
            self.assertFalse(difference["cutover_allowed"])

    def test_safe_single_terminal_semicolon_only(self):
        allowed = (
            "'SELECT 1;'",
            "'SELECT @flag ;'",
            "'SET @alpha=1,@beta=0;'",
            "'SET @first=@second,@third=NULL;'",
            "'SET SESSION FOREIGN_KEY_CHECKS=0;'",
        )
        for literal in allowed:
            with self.subTest(literal=literal):
                self.assertTrue(verify._cross_engine_safe_dynamic_branch(literal))

    def test_side_effects_unknown_control_and_multi_statements_rejected(self):
        dangerous = (
            "'SELECT 1; DROP TABLE t;'",
            "'SELECT 1;-- comment'",
            "'SET @a=1; UPDATE t SET x=2'",
            "'SET @a=1;SELECT 1'",
            "'SET @a=1; SET @b=1'",
            "'SET @a=1;;'",
            "'SET GLOBAL sql_mode=0;'",
            "'SET @a=IF(1,2,3);'",
            "'SET @a=(SELECT COUNT(*) FROM t);'",
            "'SET @a=1, @b=LOAD_FILE(/etc/passwd);'",
            "'SELECT SLEEP(10);'",
            "'SELECT 1 /* leaked */'",
            "'SELECT 1\\nDROP TABLE t'",
            "'ALTER TABLE t ADD COLUMN y INT;'",
            "'INSERT INTO t VALUES(1);'",
            "'SET @q=1, @other=NOW();'",
        )
        for literal in dangerous:
            with self.subTest(literal=literal):
                self.assertFalse(verify._cross_engine_safe_dynamic_branch(literal))

    def test_mariadb_sandbox_banner_and_quoted_semicolon_remain_safe(self):
        sample=(
            "/*M!999999\\- enable the sandbox mode */\n"
            "CREATE TABLE t (id int, note text);\n"
            "INSERT INTO t VALUES (1,'quoted; value');\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            a,b=Path(directory)/"a.sql.gz",Path(directory)/"b.sql.gz"
            for path in (a,b):
                with gzip.open(path,"wt",encoding="utf-8") as stream:
                    stream.write(sample)
            self.assertFalse(verify.sql_unproven_side_effects(a))
            self.assertEqual(pull.compare_database_dumps(a,b),"CANONICAL_SQL_EXACT")

    def test_stacked_privileged_command_cannot_hide_after_sql(self):
        baseline="CREATE TABLE t (id int);\n"
        statements=(
            "INSERT INTO t VALUES (1); GRANT ALL ON *.* TO 'x'@'y';",
            "SET @x=1; SET GLOBAL sql_mode='';",
            "SELECT 1; REVOKE ALL ON *.* FROM 'x'@'y';",
        )
        for statement in statements:
            with self.subTest(prefix=statement.split()[0]), tempfile.TemporaryDirectory() as d:
                a,b=Path(d)/"a.sql.gz",Path(d)/"b.sql.gz"
                for path in (a,b):
                    with gzip.open(path,"wt",encoding="utf-8") as stream:
                        stream.write(baseline+statement+"\n")
                with self.assertRaisesRegex(
                    pull.PullMigrationError,"UNPROVEN_PRIVILEGED_SQL"
                ):
                    pull.compare_database_dumps(a,b)

    def test_exact_or_logically_matching_dump_never_ignores_privileged_sql(self):
        # Identical dumps are not enough to prove a privileged statement safe
        # across MySQL/MariaDB, and logical DDL+DML parity omits these commands.
        baseline = "CREATE TABLE t (id int);\nINSERT INTO t VALUES (1);\n"
        unsafe = (
            "GRANT ALL ON *.* TO 'example'@'localhost';",
            "REVOKE ALL ON *.* FROM 'example'@'localhost';",
            "SET GLOBAL sql_mode='';",
            "SET @@GLOBAL.foreign_key_checks=0;",
            "/*!50003 SET GLOBAL sql_mode='' */;",
            "/*!50003 EXECUTE not_proven */;",
            "PREPARE test FROM @p;",
            "CALL rotate_data();",
            "UPDATE t SET id=2;",
            "DELETE FROM t;",
            "SELECT 1 INTO OUTFILE '/tmp/fake';",
        )
        with tempfile.TemporaryDirectory() as directory:
            a = Path(directory) / "source.sql.gz"
            b = Path(directory) / "target.sql.gz"
            for statement in unsafe:
                with self.subTest(statement=statement.split()[0]):
                    for f,sql in ((a,baseline+statement+"\n"), (b,baseline)):
                        with gzip.open(f,"wt",encoding="utf-8") as stream:
                            stream.write(sql)
                    with self.assertRaisesRegex(
                        pull.PullMigrationError, "UNPROVEN_PRIVILEGED_SQL"
                    ):
                        pull.compare_database_dumps(a,b)
                    # Even matching same guarded SQL on both sides must not
                    # bypass source/target engine-specific execution guards.
                    with gzip.open(b,"wt",encoding="utf-8") as stream:
                        stream.write(baseline+statement+"\n")
                    with self.assertRaisesRegex(
                        pull.PullMigrationError, "UNPROVEN_PRIVILEGED_SQL"
                    ):
                        pull.compare_database_dumps(a,b)

    def test_complete_safe_guard_sequence_can_be_compared_across_engines(self):
        source = (
            "CREATE TABLE t (id int);\n"
            "/*!50003 SELECT COUNT(*) INTO @present FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA='example_db' AND TABLE_NAME='t' */;\n"
            "/*!50003 SET @query=IF(@present,'SET @alpha=1,@beta=0;', 'SELECT 1;') */;\n"
            "/*!50003 PREPARE stmt FROM @query */;\n"
            "/*!50003 EXECUTE stmt */;\n"
            "/*!50003 DEALLOCATE PREPARE stmt */;\n"
            "INSERT INTO t VALUES (1);\n"
        )
        target = "CREATE TABLE t (id int);\nINSERT INTO t VALUES (1);\n"
        with tempfile.TemporaryDirectory() as directory:
            left,right=(Path(directory)/"left.sql.gz",Path(directory)/"right.sql.gz")
            for p,sql in ((left,source),(right,target)):
                with gzip.open(p,"wt",encoding="utf-8") as stream:
                    stream.write(sql)
            diagnostic=verify.sql_dynamic_guard_flow_diagnostic(left)
            self.assertIn("safe_assignment=1",diagnostic)
            self.assertIn("outcome=RECOGNIZED",diagnostic)
            self.assertEqual(len(verify._cross_engine_known_dynamic_guard_lines(left)),5)
            self.assertEqual(
                verify.sql_cross_engine_known_format_fingerprint(left),
                verify.sql_cross_engine_known_format_fingerprint(right),
            )
            self.assertEqual(pull.compare_database_dumps(left,right),
                "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT")

    def test_identical_dump_cannot_bypass_unrecognized_guard(self):
        sql=(
            "CREATE TABLE t (id int);\n"
            "/*!50003 SET @q=IF(@flag,'SELECT 1; SELECT 2','SELECT 0') */;\n"
            "INSERT INTO t VALUES (1);\n"
        )
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/"a.sql.gz",Path(d)/"b.sql.gz"
            for target in (a,b):
                with gzip.open(target,"wt",encoding="utf-8") as output:
                    output.write(sql)
            self.assertEqual(verify.sql_fingerprint(a),verify.sql_fingerprint(b))
            with self.assertRaisesRegex(pull.PullMigrationError,"CONDITIONAL_DDL"):
                pull.compare_database_dumps(a,b)

    def test_one_unsafe_branch_blocks_even_when_original_rows_are_equal(self):
        def check(unsafe):
            source=(
                "CREATE TABLE t (id int);\n"
                "/*!50003 SELECT COUNT(*) INTO @present FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA='example_db' AND TABLE_NAME='t' */;\n"
                "/*!50003 SET @query=IF(@present,'"+unsafe+"', 'SELECT 1;') */;\n"
                "/*!50003 PREPARE stmt FROM @query */;\n"
                "/*!50003 EXECUTE stmt */;\n"
                "/*!50003 DEALLOCATE PREPARE stmt */;\n"
                "INSERT INTO t VALUES (1);\n"
            )
            target="CREATE TABLE t (id int);\nINSERT INTO t VALUES (1);\n"
            with tempfile.TemporaryDirectory() as directory:
                a,b=Path(directory)/"a.sql.gz",Path(directory)/"b.sql.gz"
                for p,sql in ((a,source),(b,target)):
                    with gzip.open(p,"wt",encoding="utf-8") as stream:
                        stream.write(sql)
                self.assertFalse(verify._cross_engine_known_dynamic_guard_lines(a))
                with self.assertRaises(pull.PullMigrationError):
                    pull.compare_database_dumps(a,b)
        for unsafe in (
            "SET @alpha=1; DROP TABLE t",
            "SELECT 1; UPDATE t SET id=2",
            "SET GLOBAL FOREIGN_KEY_CHECKS=0",
            "SET @alpha=NOW()",
            "CREATE TRIGGER hacked BEFORE INSERT ON t FOR EACH ROW SET @x=1",
        ):
            with self.subTest(unsafe=unsafe):
                check(unsafe)


if __name__ == "__main__":
    unittest.main()
