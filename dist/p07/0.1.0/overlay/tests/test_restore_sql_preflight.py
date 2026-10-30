"""Synthetic proof that no unsafe guarded SQL reaches either restore engine."""
from __future__ import annotations

import gzip
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import isolated_db_restore as container
import native_scratch_restore as native
import restore_sql_preflight as preflight

SAFE = "CREATE TABLE alpha (id INT PRIMARY KEY);\nINSERT INTO alpha VALUES (1);\n"
DANGEROUS = (
    "/*!50003 SET @cmd = IF(@somevar,'DROP TABLE alpha','SELECT 1') */;\n"
    "CREATE TABLE alpha (id INT PRIMARY KEY);\n"
)


def make_sql(root: Path, name: str, contents: str) -> Path:
    path = root / name
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(contents)
    return path


def safe_evidence(unsafe: int = 0) -> dict:
    return {
        "status": "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
        "source_backup_integrity": "PASS",
        "target_backup_integrity": "PASS",
        "dynamic_unsafe": unsafe,
    }


class DynamicGuardPreflightTests(unittest.TestCase):
    def test_no_guard_passes_preimport_syntax_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = make_sql(Path(tmp), "a.sql.gz", SAFE)
            b = make_sql(Path(tmp), "b.sql.gz", SAFE)
            self.assertIsNone(preflight.require_no_unsafe_dynamic_guard(a, b))

    def test_unsafe_guard_on_either_side_fails_before_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            safe = make_sql(Path(tmp), "safe.sql.gz", SAFE)
            bad = make_sql(Path(tmp), "bad.sql.gz", DANGEROUS)
            for a, b in ((safe, bad), (bad, safe)):
                with self.subTest(source=a.name):
                    with self.assertRaisesRegex(preflight.GuardBlocked, "RESTORE_UNSAFE"):
                        preflight.require_no_unsafe_dynamic_guard(a, b)

    def test_unavailable_guards_do_not_leak_private_sql(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = make_sql(Path(tmp), "a.sql.gz", SAFE)
            b = Path(tmp) / "private-unavailable.sql.gz"
            with self.assertRaises(preflight.GuardBlocked) as raised:
                preflight.require_no_unsafe_dynamic_guard(a, b)
        self.assertEqual(str(raised.exception), "RESTORE_DYNAMIC_SQL_GUARD_UNAVAILABLE")

    def test_missing_advisory_unsafe_count_blocks_without_engine(self):
        for module in (native, container):
            with self.subTest(module=module.__name__):
                evidence = safe_evidence()
                del evidence["dynamic_unsafe"]
                with mock.patch.object(module.private_recovery_gate, "evaluate", return_value=evidence), \
                     mock.patch.object(module, "_binaries" if module is native else "_docker_ready") as engine:
                    result = module.rehearse(Path("/a"), Path("/b"), "example.test",
                                "NATIVE_RESTORE_SCRATCH_ONLY" if module is native else "ISOLATED_RESTORE_ONLY")
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["cutover_allowed"])
                engine.assert_not_called()

    def test_known_source_unsafe_guard_blocks_before_any_engine(self):
        for module in (native, container):
            with self.subTest(module=module.__name__):
                with mock.patch.object(module.private_recovery_gate, "evaluate",
                                       return_value=safe_evidence(3)), \
                     mock.patch.object(module, "_binaries" if module is native else "_docker_ready") as engine:
                    result = module.rehearse(Path("/a"), Path("/b"), "example.test",
                                "NATIVE_RESTORE_SCRATCH_ONLY" if module is native else "ISOLATED_RESTORE_ONLY")
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["cutover_allowed"])
                engine.assert_not_called()

    def test_target_guard_blocks_both_backends_before_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = make_sql(Path(tmp), "a.sql.gz", SAFE)
            b = make_sql(Path(tmp), "b.sql.gz", DANGEROUS)
            for module in (native, container):
                with self.subTest(module=module.__name__):
                    with mock.patch.object(module.private_recovery_gate, "evaluate",
                                           return_value=safe_evidence()), \
                         mock.patch.object(module.private_recovery_gate, "_input_package",
                                           side_effect=[({}, a), ({}, b)]), \
                         mock.patch.object(module, "_binaries" if module is native else "_docker_ready"), \
                         mock.patch.object(module, "restore_one" if module is native else "_restore_one") as restore:
                        result = module.rehearse(Path("/a"), Path("/b"), "example.test",
                                    "NATIVE_RESTORE_SCRATCH_ONLY" if module is native else "ISOLATED_RESTORE_ONLY")
                    self.assertEqual(result["reason"], "RESTORE_UNSAFE_OR_UNPROVEN_DYNAMIC_SQL_GUARD")
                    restore.assert_not_called()

    def test_injected_malformed_counter_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = make_sql(Path(tmp), "a.sql.gz", SAFE)
            b = make_sql(Path(tmp), "b.sql.gz", SAFE)
            with mock.patch.object(preflight.sql_diff_evidence, "dynamic_guard_syntax_counts",
                    return_value={"recognized_unsafe": False, "other_unknown_set": 0, "double_quoted_if": 0}):
                with self.assertRaisesRegex(preflight.GuardBlocked, "UNPROVEN"):
                    preflight.require_no_unsafe_dynamic_guard(a, b)


if __name__ == "__main__":
    unittest.main()
