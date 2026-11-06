"""Issue #287: exact private guard repro, one capture, zero import or SQL leak."""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import migration_private_sql_repro as repro
import server_migration_pull as pull

MID = "pull-20261106T065804Z-1aef6d0e"
DOMAIN = "ilovem3u8.kewaro.com"


def source_sql(groups: int = 3) -> str:
    lines = [
        "-- MySQL dump 10.13 Distrib 8.0.45",
        "-- Server version 8.0.45",
        "CREATE TABLE business_table (business_id int);",
        "INSERT INTO business_table VALUES (123456789);",
    ]
    lines.append(
        "/*!50003 SELECT COUNT(*) INTO @present FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA='very_private_schema' AND TABLE_NAME='business_table' */;"
    )
    for i in range(groups):
        lines.extend((
            "/*!50003 SET @statement%d=IF(@present,"
            "'SET SESSION SQL_MODE=CONCAT(''SECRET_ACCOUNT_VALUE'',''STRICT'');',"
            "'SELECT 1;') */;" % i,
            "/*!50003 PREPARE stmt%d FROM @statement%d */;" % (i, i),
            "/*!50003 EXECUTE stmt%d */;" % i,
            "/*!50003 DEALLOCATE PREPARE stmt%d */;" % i,
        ))
    return "\n".join(lines) + "\n"


def target_sql() -> str:
    return (
        "-- MariaDB dump 10.19 Distrib 11.8.3-MariaDB\n"
        "-- Server version 11.8.3-MariaDB\n"
        "CREATE TABLE business_table (business_id int);\n"
        "INSERT INTO business_table VALUES (123456789);\n"
    )


def write_sql(path: Path, content: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(content)


def state() -> dict:
    rows = [{
        "domain": f"unrelated{i}.example",
        "stage_status": "PULLED_STAGED" if i < 7 else "PENDING",
        "mysql_databases": [],
    } for i in range(18)]
    rows[7] = {
        "domain": DOMAIN, "stage_status": "PENDING",
        "mysql_databases": ["private_kewaro_db"],
    }
    return {
        "schema": pull.SCHEMA, "status": "PREPARE_FAILED",
        "migration_id": MID,
        "sites": rows,
        "last_sql_guard_failure": {"reason": "CONDITIONAL_DDL"},
        "source_runtime_frozen": False,
        "target_runtime_activated": False,
        "target_server_identity": "CP2-SAME-OWNER",
        "source": {"host": "old.example"},
        "source_runtime_path": "/remote/private/helper",
    }


class PrivateReproTests(unittest.TestCase):
    def test_one_capture_exact_three_groups_redacted_and_kept_only_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            source, target = root / "source.sql.gz", root / "target.sql.gz"
            write_sql(source, source_sql())
            write_sql(target, target_sql())
            result = repro.capture_private_repro(root, source, target)
            self.assertEqual(result["status"], "PRIVATE_MINIMAL_REPRO_CAPTURED_NOT_VERIFIED")
            self.assertEqual(result["observed_if_groups"], 3)
            self.assertEqual(result["guard_lines"], 13)
            self.assertIn("probe=1 assignment=3 safe_assignment=0", result["reproduced_guard_flow"])
            self.assertIn("outcome=UNSAFE_BRANCH", result["reproduced_guard_flow"])
            self.assertEqual(result["environment"]["source_server_version"], "8.0.45")
            self.assertEqual(result["environment"]["target_server_version"], "11.8.3")
            self.assertFalse(result["db_reimport_allowed"])
            self.assertFalse(result["migration_resume_allowed"])
            self.assertFalse(result["cutover_allowed"])
            printed = json.dumps(result)
            for secret in ("SECRET_ACCOUNT_VALUE", "very_private_schema", "business_table",
                           "private_kewaro_db", "123456789", "present0"):
                self.assertNotIn(secret, printed)
            for branch in result["branches"]:
                self.assertEqual(branch["yes"]["guard_verdict"], "UNPROVEN")
                self.assertIn("CONCAT", branch["yes"]["tokens"])
                self.assertIn("STRING_LITERAL", branch["yes"]["tokens"])
            private = root / "private-sql-repro"
            self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o700)
            for name in ("guarded_fragments.NEVER_EXECUTE.txt", "private_receipt.json"):
                p = private / name
                self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
                self.assertFalse(p.is_symlink())
            fragment = (private / "guarded_fragments.NEVER_EXECUTE.txt").read_text()
            self.assertIn("SECRET_ACCOUNT_VALUE", fragment)
            self.assertIn("very_private_schema", fragment)
            self.assertNotIn("INSERT INTO business_table", fragment)
            self.assertNotIn("CREATE TABLE business_table", fragment)
            prior = fragment
            with self.assertRaisesRegex(repro.PrivateSqlReproBlocked,
                                        "PRIVATE_REPRO_ALREADY_PRESENT_NO_OVERWRITE"):
                repro.capture_private_repro(root, source, target)
            self.assertEqual(
                (private / "guarded_fragments.NEVER_EXECUTE.txt").read_text(), prior
            )

    def test_no_partial_capture_on_two_guard_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            a, b = root / "a.sql.gz", root / "b.sql.gz"
            write_sql(a, source_sql(groups=2))
            write_sql(b, target_sql())
            with self.assertRaisesRegex(repro.PrivateSqlReproBlocked,
                                        "PRIVATE_REPRO_THREE_COMPLETE_GROUPS_NOT_OBSERVED"):
                repro.capture_private_repro(root, a, b)
            self.assertFalse((root / "private-sql-repro").exists())

    def test_permissions_and_symlinks_block_before_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o755)
            a, b = root / "a.sql.gz", root / "b.sql.gz"
            write_sql(a, source_sql())
            write_sql(b, target_sql())
            with self.assertRaisesRegex(repro.PrivateSqlReproBlocked,
                                        "PRIVATE_REPRO_MIGRATION_ROOT_UNSAFE"):
                repro.capture_private_repro(root, a, b)
            os.chmod(root, 0o700)
            alias = root / "alias"
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(repro.PrivateSqlReproBlocked):
                repro.capture_private_repro(alias, a, b)
            self.assertFalse((root / "private-sql-repro").exists())

    def test_exact_original_18_site_scope_rejected_before_source_or_target(self):
        base = state()
        for drift in ("different_migration", "wrong_domain", "wrong_target",
                      "preexisting_capture", "unproven_guard"):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                os.chmod(root, 0o700)
                row = json.loads(json.dumps(base))
                mid, domain = MID, DOMAIN
                if drift == "different_migration":
                    mid = "pull-some-other-migration"
                elif drift == "wrong_domain":
                    domain = "unrelated8.example"
                elif drift == "wrong_target":
                    row["target_server_identity"] = "DIFFERENT"
                elif drift == "preexisting_capture":
                    (root / "private-sql-repro").mkdir(mode=0o700)
                elif drift == "unproven_guard":
                    row["last_sql_guard_failure"]["reason"] = "UNVERIFIED"
                with (
                    mock.patch.object(pull, "load_state", return_value=row),
                    mock.patch.object(pull, "target_identity", return_value="CP2-SAME-OWNER"),
                    mock.patch.object(pull, "state_dir", return_value=root),
                    mock.patch.object(pull, "source_export_database") as source_export,
                    mock.patch.object(pull.cloudpanel, "export_database") as target_export,
                    mock.patch.object(pull, "save_state") as state_write,
                ):
                    with self.assertRaises(pull.PullMigrationError):
                        pull.diagnose_sql_difference(mid, domain, capture_private_repro=True)
                    source_export.assert_not_called()
                    target_export.assert_not_called()
                    state_write.assert_not_called()

    def test_real_diagnostic_path_captures_once_never_imports(self):
        private_state = state()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            def pull_source(_source, _remote, local):
                write_sql(Path(local), source_sql())
            def export_target(_db, local, **_kw):
                write_sql(Path(local), target_sql())
            with (
                mock.patch.object(pull, "load_state", return_value=private_state),
                mock.patch.object(pull, "target_identity", return_value="CP2-SAME-OWNER"),
                mock.patch.object(pull, "state_dir", return_value=root),
                mock.patch.object(pull, "source_export_helper_matches_current", return_value=True),
                mock.patch.object(pull, "source_export_database"),
                mock.patch.object(pull, "pull_path", side_effect=pull_source),
                mock.patch.object(pull.sql_diff_probe, "require_nonempty_source_schema",
                                  return_value=42),
                mock.patch.object(pull.cloudpanel, "export_database",
                                  side_effect=export_target),
                mock.patch.object(pull.sql_diff_probe, "diagnostic", return_value={
                    "schema": "SQL_DIFF_EVIDENCE_V2", "verification": "NOT_A_PASS_GATE",
                }),
                mock.patch.object(pull, "guarded_export_comparison_advisory", return_value={
                    "status": "BLOCKED", "cutover_allowed": False,
                }),
                mock.patch.object(pull, "source_remote") as remote_cleanup,
                mock.patch.object(pull, "save_state") as state_write,
                mock.patch.object(pull.legacy, "target_create_database_local") as import_db,
            ):
                result = pull.diagnose_sql_difference(
                    MID, DOMAIN, capture_private_repro=True
                )
                self.assertEqual(result["status"], "ADVISORY_DIAGNOSTIC_ONLY")
                self.assertEqual(result["private_repro"]["observed_if_groups"], 3)
                self.assertFalse(result["migration_state_modified"])
                self.assertFalse(result["database_writes_performed"])
                self.assertEqual(remote_cleanup.call_count, 1)
                import_db.assert_not_called()
                state_write.assert_not_called()
            self.assertTrue((root / "private-sql-repro" /
                             "guarded_fragments.NEVER_EXECUTE.txt").is_file())

if __name__ == "__main__":
    unittest.main()
