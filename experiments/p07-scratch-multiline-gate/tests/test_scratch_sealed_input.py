"""Synthetic-only invariant: SQL checked is exactly SQL consumed by scratch engines."""
from __future__ import annotations

import gzip
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import scratch_sql_host_policy as policy
import scratch_guard_quarantine as quarantine
import native_scratch_restore as native
import isolated_db_restore as isolated

SAFE = b"CREATE TABLE alpha (id INT PRIMARY KEY);\nINSERT INTO alpha VALUES(1);\n"
UNSAFE = b"\\! touch /tmp/p07-not-allowed\n"
GUARDED = (
    b"/*!50003 SELECT COUNT(*) INTO @flag FROM INFORMATION_SCHEMA.TABLES "
    b"WHERE TABLE_SCHEMA='vfops_r5_scratch' AND TABLE_NAME='alpha' */;\n"
    b"/*!50003 SET @cmd = IF(@flag,'DROP TABLE alpha','SELECT 1') */;\n"
    b"/*!50003 PREPARE stmt FROM @cmd */;\n"
    b"/*!50003 EXECUTE stmt */;\n"
    b"/*!50003 DEALLOCATE PREPARE stmt */;\n"
)


def fixture(directory: Path, data: bytes) -> Path:
    path = directory / "synthetic.sql.gz"
    with gzip.open(path, "wb") as stream:
        stream.write(data)
    return path


class SealedInputTests(unittest.TestCase):
    def test_approved_bytes_are_pinned_even_if_original_is_replaced(self):
        with tempfile.TemporaryDirectory() as name:
            original = fixture(Path(name), SAFE)
            with policy.sealed_sql_stream(original) as approved:
                self.assertEqual(approved.read_bytes(), SAFE)
                self.assertEqual(approved.stat().st_mode & 0o777, 0o600)
                self.assertEqual(approved.parent.stat().st_mode & 0o777, 0o700)
                # Once sealed, modifying the gzip cannot affect executed bytes.
                fixture(Path(name), SAFE + UNSAFE)
                self.assertEqual(approved.read_bytes(), SAFE)
                sealed_path = approved
            self.assertFalse(sealed_path.exists())
            self.assertFalse(sealed_path.parent.exists())

    def test_original_blank_and_whitespace_bytes_survive_sealed_stream(self):
        # A blank/whitespace line may be part of an SQL literal. Dropping it
        # before import mutates the SQL and invalidates an exact-restore claim.
        samples = (
            b"\n",
            b"   \n",
            b"\t\r\n",
            b"CREATE TABLE alpha (id INT);\r\n",
            b"  \r\n",
            b"INSERT INTO alpha VALUES(1);\n",
        )
        original_bytes = b"".join(samples)
        with tempfile.TemporaryDirectory() as temp:
            sql = fixture(Path(temp), original_bytes)
            with policy.sealed_sql_stream(sql) as sealed:
                self.assertEqual(sealed.read_bytes(), original_bytes)
                self.assertEqual(policy.preflight_sql(sql), len(original_bytes))

    def test_multiline_literal_with_whitespace_only_line_preserved_exactly(self):
        # Sealing is *not* a SQL parser. It must never delete a line from an
        # originally valid or invalid SQL string while claiming byte identity.
        original_bytes = (
            b"CREATE TABLE alpha (body TEXT);\n"
            b"INSERT INTO alpha VALUES('first\n"
            b"   \n"
            b"third');\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            sql = fixture(Path(temp), original_bytes)
            with policy.sealed_sql_stream(sql) as sealed:
                self.assertEqual(sealed.read_bytes(), original_bytes)

    def test_host_command_never_yields_a_sealed_path(self):
        with tempfile.TemporaryDirectory() as name:
            original = fixture(Path(name), SAFE + UNSAFE)
            seen = False
            with self.assertRaisesRegex(
                policy.HostPolicyBlocked, "SCRATCH_SQL_CLIENT_CONTROL_REFUSED"
            ):
                with policy.sealed_sql_stream(original):
                    seen = True
            self.assertFalse(seen)

    def test_native_and_docker_receive_sealed_sql_not_gzip(self):
        with tempfile.TemporaryDirectory() as name:
            original = fixture(Path(name), SAFE)
            for runner, helper in (
                (lambda: native.restore_one(original, 1), native),
                (lambda: isolated._restore_one(original, 1), isolated),
            ):
                with self.subTest(engine=helper.__name__):
                    with mock.patch.object(helper, "_restore_one_sealed") as use:
                        use.side_effect = lambda sealed, count: (
                            self.assertEqual(sealed.read_bytes(), SAFE) or count
                        )
                        self.assertEqual(runner(), 1)
                        use.assert_called_once()
                        self.assertFalse(use.call_args.args[0].exists())

    def test_native_and_docker_refuse_unsafe_sql_before_engine(self):
        with tempfile.TemporaryDirectory() as name:
            original = fixture(Path(name), SAFE + UNSAFE)
            for runner, helper in (
                (lambda: native.restore_one(original, 1), native),
                (lambda: isolated._restore_one(original, 1), isolated),
            ):
                with self.subTest(engine=helper.__name__):
                    with mock.patch.object(helper, "_restore_one_sealed") as engine:
                        with self.assertRaises(policy.HostPolicyBlocked):
                            runner()
                        engine.assert_not_called()

    def test_quarantine_seals_only_modified_table_flow_never_original(self):
        with tempfile.TemporaryDirectory() as name:
            original = fixture(Path(name), SAFE + GUARDED)
            backup_bytes = original.read_bytes()
            plan = quarantine.plan(original)
            self.assertEqual(plan["removed"], 1)
            with policy.sealed_sql_stream(original, quarantine_plan=plan) as approved:
                self.assertEqual(approved.read_bytes(), SAFE)
            self.assertEqual(original.read_bytes(), backup_bytes)
            with mock.patch.object(native, "_restore_one_sealed", return_value=1) as engine:
                self.assertEqual(native.restore_one(original, 1, quarantine_plan=plan), 1)
                engine.assert_called_once()
            self.assertEqual(original.read_bytes(), backup_bytes)

    def test_quarantine_rejects_modified_input_before_engine(self):
        with tempfile.TemporaryDirectory() as name:
            original = fixture(Path(name), SAFE + GUARDED)
            plan = quarantine.plan(original)
            fixture(Path(name), SAFE + GUARDED + b"SELECT 2;\n")
            with mock.patch.object(native, "_restore_one_sealed") as engine:
                with self.assertRaisesRegex(
                    policy.HostPolicyBlocked, "SCRATCH_QUARANTINE_STREAM_UNPROVEN"
                ):
                    native.restore_one(original, 1, quarantine_plan=plan)
                engine.assert_not_called()


if __name__ == "__main__":
    unittest.main()
