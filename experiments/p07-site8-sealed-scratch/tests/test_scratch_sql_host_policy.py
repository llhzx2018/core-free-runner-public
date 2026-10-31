"""Synthetic-only host SQL safety checks, no private backup or external DB."""
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
import scratch_guard_quarantine as quarantine

TABLE = b"CREATE TABLE alpha (id INT PRIMARY KEY, body TEXT);\n"
ROW = b"INSERT INTO alpha VALUES (1,'normal SQL; SELECT 1; text');\n"
GUARDED = (
    b"/*!50003 SELECT COUNT(*) INTO @flag FROM INFORMATION_SCHEMA.TABLES "
    b"WHERE TABLE_SCHEMA='vfops_r5_scratch' AND TABLE_NAME='alpha' */;\n"
    b"/*!50003 SET @cmd = IF(@flag,'DROP TABLE alpha','SELECT 1') */;\n"
    b"/*!50003 PREPARE stmt FROM @cmd */;\n"
    b"/*!50003 EXECUTE stmt */;\n"
    b"/*!50003 DEALLOCATE PREPARE stmt */;\n"
)


def backed(root: str, value: bytes) -> Path:
    file = Path(root) / "private-synthetic.sql.gz"
    with gzip.open(file, "wb") as f:
        f.write(value)
    return file


class HostSqlPreflightContractTests(unittest.TestCase):
    def test_benign_dump_and_literal_data_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            sql = backed(tmp, TABLE + ROW)
            self.assertEqual(policy.preflight_sql(sql), len(TABLE + ROW))

    def test_client_meta_commands_and_delimiter_refused(self):
        for danger in (
            b"\\! touch /tmp/host-file\n",
            b"\\. /tmp/private.sql\n",
            b"\\C utf8\n",
            b"delimiter $$\n",
            b"SOURCE /tmp/private.sql\n",
            b"system whoami\n",
            b"TEE /tmp/log\n",
        ):
            with self.subTest(kind=danger.split(b" ")[0]):
                with tempfile.TemporaryDirectory() as tmp:
                    sql = backed(tmp, TABLE + danger)
                    with self.assertRaisesRegex(
                        policy.HostPolicyBlocked,
                        "SCRATCH_SQL_CLIENT_CONTROL_REFUSED",
                    ):
                        policy.preflight_sql(sql)

    def test_host_file_and_privileged_sql_refused(self):
        for danger in (
            b"SELECT 1 INTO OUTFILE '/tmp/host-file';\n",
            b"SELECT 1 INTO DUMPFILE '/tmp/host-file';\n",
            b"LOAD DATA LOCAL INFILE '/tmp/secret' INTO TABLE alpha;\n",
            b"INSTALL PLUGIN x SONAME 'evil.so';\n",
            b"CREATE FUNCTION x RETURNS STRING SONAME 'evil.so';\n",
            b"SET GLOBAL max_connections=1;\n",
            b"GRANT ALL ON *.* TO 'x'@'localhost';\n",
            b"CREATE USER 'x'@'localhost';\n",
            b"SHUTDOWN;\n",
            b"/*!50003 SELECT 1 INTO OUTFILE '/tmp/host-file' */;\n",
        ):
            with self.subTest(kind=danger[:36]):
                with tempfile.TemporaryDirectory() as tmp:
                    sql = backed(tmp, TABLE + danger)
                    with self.assertRaisesRegex(
                        policy.HostPolicyBlocked,
                        "SCRATCH_SQL_HOST_ACCESS_REFUSED",
                    ):
                        policy.preflight_sql(sql)

    def test_quarantined_full_guard_removed_but_normal_data_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            sql = backed(tmp, TABLE + GUARDED + ROW)
            original = sql.read_bytes()
            plan = quarantine.plan(sql)
            self.assertEqual(plan["removed"], 1)
            self.assertEqual(policy.preflight_sql(sql, quarantine_plan=plan),
                             len(TABLE + ROW))
            self.assertEqual(sql.read_bytes(), original)

    def test_quarantine_must_not_hide_unguarded_host_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            sql = backed(tmp, TABLE + GUARDED +
                         b"SELECT 1 INTO OUTFILE '/tmp/not-allowed';\n" + ROW)
            plan = quarantine.plan(sql)
            with self.assertRaisesRegex(policy.HostPolicyBlocked,
                                        "SCRATCH_SQL_HOST_ACCESS_REFUSED"):
                policy.preflight_sql(sql, quarantine_plan=plan)

    def test_unsupported_line_content_never_reaches_native_daemon(self):
        with tempfile.TemporaryDirectory() as tmp:
            sql = backed(tmp, TABLE + b"\\! run-on-host\n")
            with mock.patch.object(native, "_binaries") as bins, \
                 mock.patch.object(native, "_identity") as identity:
                with self.assertRaises(policy.HostPolicyBlocked):
                    native.restore_one(sql, 1)
                bins.assert_not_called()
                identity.assert_not_called()

    def test_unsupported_line_content_never_starts_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            sql = backed(tmp, TABLE + b"DELIMITER //\n")
            with mock.patch.object(isolated, "_credentials_and_name") as credentials, \
                 mock.patch.object(isolated, "_docker") as docker:
                with self.assertRaises(policy.HostPolicyBlocked):
                    isolated._restore_one(sql, 1)
                credentials.assert_not_called()
                docker.assert_not_called()

    def test_invalid_quarantine_plan_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            sql = backed(tmp, TABLE + ROW)
            with self.assertRaisesRegex(policy.HostPolicyBlocked,
                                        "SCRATCH_QUARANTINE_STREAM_UNPROVEN"):
                policy.preflight_sql(sql, quarantine_plan={"removed": 9})

    def test_uncompressed_limit_is_enforced_before_execution(self):
        with mock.patch.object(policy, "MAX_UNCOMPRESSED", 5):
            with self.assertRaisesRegex(policy.HostPolicyBlocked,
                                        "SCRATCH_SQL_UNCOMPRESSED_LIMIT"):
                policy.inspect_lines([b"1234", b"56789"])


if __name__ == "__main__":
    unittest.main()
