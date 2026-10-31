"""Synthetic scratch-only host SQL lexical boundary regression tests.

No network, VPS, DB process, real backup or production filesystem paths.
"""
from __future__ import annotations

import gzip
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import scratch_sql_host_policy as policy
import native_scratch_restore as native
import isolated_db_restore as isolated

BENIGN = (
    b"-- synthetic mysqldump\n"
    b"CREATE TABLE alpha (\n"
    b" id INT PRIMARY KEY,\n"
    b" content TEXT\n"
    b");\n"
    b"INSERT INTO alpha VALUES (1,'SELECT 1 INTO OUTFILE \\'fake\\';\n"
    b"\n"
    b"LOAD DATA LOCAL INFILE forbidden in literal'),\n"
    b"(2,'this value contains -- not a comment');\n"
    b"/* LOAD DATA LOCAL INFILE should be masked */\n"
    b"/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;\n"
)


def backed(tmp: str, sql: bytes) -> Path:
    path = Path(tmp) / "fixture.sql.gz"
    with gzip.open(path, "wb") as stream:
        stream.write(sql)
    return path


class MultiLineHostSqlTests(unittest.TestCase):
    def test_realistic_sql_dump_and_long_literals_preserve_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            file = backed(folder, BENIGN)
            with policy.sealed_sql_stream(file) as sealed:
                self.assertEqual(sealed.read_bytes(), BENIGN)
                self.assertEqual(policy.preflight_sql(file), len(BENIGN))

    def test_multiline_and_comment_split_host_operations_rejected(self):
        for payload in (
            b"LOAD\nDATA LOCAL INFILE '/tmp/not-real' INTO TABLE alpha;\n",
            b"LOAD/**/DATA LOCAL INFILE '/tmp/not-real' INTO TABLE alpha;\n",
            b"SELECT 1\nINTO\nOUTFILE '/tmp/not-real';\n",
            b"SELECT\n'normal'\nINTO /* c */ DUMPFILE '/tmp/not-real';\n",
            b"SELECT LOAD_FILE('/tmp/not-real');\n",
            b"SELECT\n LOAD_FILE('/tmp/not-real');\n",
            b"SET /*comment*/ GLOBAL max_connections=1;\n",
            b"GRANT\n ALL ON *.* TO 'x'@'localhost';\n",
            b"CREATE/* comment */USER 'x'@'localhost';\n",
            b"PREPARE stmt FROM @cmd;\n",
            b"/*!50003 EXECUTE stmt */;\n",
            b"CREATE FUNCTION x RETURNS STRING\nSONAME 'libplugin.so';\n",
            b"SELECT 1; /*c*/ LOAD DATA INFILE '/tmp/x' INTO TABLE alpha;\n",
            b"/* comment */\nLOAD DATA INFILE '/tmp/x' INTO TABLE alpha;\n",
        ):
            with self.subTest(payload=payload[:30]), tempfile.TemporaryDirectory() as folder:
                file = backed(folder, BENIGN + payload)
                with self.assertRaisesRegex(
                    policy.HostPolicyBlocked, "SCRATCH_SQL_HOST_ACCESS_REFUSED"
                ):
                    policy.preflight_sql(file)

    def test_unknown_executable_guard_context_fails_closed(self):
        for payload in (
            b"SELECT 1 /*!50003 INTO OUTFILE '/tmp/x' */;\n",
            b"/*M!50003\n EXECUTE stmt */;\n",
            b"/*!50003 LOAD DATA INFILE '/tmp/x' INTO TABLE a */;\n",
        ):
            with self.subTest(payload=payload[:30]), tempfile.TemporaryDirectory() as folder:
                file = backed(folder, payload)
                with self.assertRaises(policy.HostPolicyBlocked):
                    policy.preflight_sql(file)

    def test_truncated_quote_and_comment_are_never_approved(self):
        for payload in (
            b"INSERT INTO alpha VALUES ('unclosed\n",
            b"/* unclosed SQL comment\n",
            b"INSERT INTO alpha VALUES ('last escaped byte\\",
        ):
            with self.subTest(payload=payload[:30]), tempfile.TemporaryDirectory() as folder:
                file = backed(folder, payload)
                with self.assertRaisesRegex(
                    policy.HostPolicyBlocked, "SCRATCH_SQL_LEXICAL_BOUNDARY_UNPROVEN"
                ):
                    policy.preflight_sql(file)

    def test_entire_stream_examined_before_native_and_docker_engine(self):
        with tempfile.TemporaryDirectory() as folder:
            file = backed(folder, BENIGN + b"LOAD\nDATA INFILE '/tmp/no' INTO TABLE alpha;")
            for runner, name in (
                (lambda: native.restore_one(file, 1), native),
                (lambda: isolated._restore_one(file, 1), isolated),
            ):
                with self.subTest(engine=name.__name__):
                    with mock.patch.object(name, "_restore_one_sealed") as engine:
                        with self.assertRaises(policy.HostPolicyBlocked):
                            runner()
                        engine.assert_not_called()

    def test_statement_limit_blocks_without_any_approved_engine(self):
        with mock.patch.object(policy, "MAX_STATEMENT_BYTES", 10):
            with self.assertRaisesRegex(policy.HostPolicyBlocked, "SCRATCH_SQL_STATEMENT_TOO_LARGE"):
                policy.inspect_lines([b"INSERT INTO table VALUES(1)"])

    def test_unrecognized_binary_line_never_becomes_client_meta(self):
        data = b"CREATE TABLE alpha (id INT);\nINSERT INTO alpha VALUES (1);\n"
        self.assertEqual(policy.inspect_lines(data.splitlines(keepends=True)), len(data))


if __name__ == "__main__":
    unittest.main()
