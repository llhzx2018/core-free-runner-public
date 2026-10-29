"""SQL diagnostic command must never perform migration or persist data."""
from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import server_migration_pull as migration


class SQLDiagnosticCommandTests(unittest.TestCase):
    def state(self):
        return {
            "status": "PREPARE_FAILED",
            "migration_id": "pull-test-diagnostic",
            "source": {"host": "example.invalid"},
            "source_runtime_path": "/private/source-runtime",
            "sites": [
                {"domain": "site.example", "mysql_databases": ["private_database"]},
            ],
        }

    def test_only_selected_database_is_exported_and_no_state_is_mutated(self):
        state = self.state()
        original = deepcopy(state)
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_database") as export_old,
            patch.object(migration, "pull_path") as pull,
            patch.object(migration.cloudpanel, "export_database") as export_new,
            patch.object(migration.sql_diff_probe, "diagnostic", return_value={
                "schema": "SQL_DIFF_EVIDENCE_V1", "verification": "NOT_A_PASS_GATE",
            }),
            patch.object(migration, "source_remote") as cleanup,
            patch.object(migration, "save_state") as state_write,
            patch.object(migration, "tempfile") as temporary,
            patch.object(migration.os, "chmod"),
        ):
            temporary.TemporaryDirectory.return_value.__enter__.return_value = "/tmp/test-private-probe"
            result = migration.diagnose_sql_difference("pull-test-diagnostic", "site.example")
        self.assertEqual(result["status"], "ADVISORY_DIAGNOSTIC_ONLY")
        self.assertFalse(result["database_writes_performed"])
        self.assertFalse(result["migration_state_modified"])
        self.assertEqual(state, original)
        state_write.assert_not_called()
        export_old.assert_called_once()
        pull.assert_called_once()
        export_new.assert_called_once()
        cleanup.assert_called_once()
        self.assertEqual(export_old.call_args.args[1], "private_database")
        self.assertEqual(export_new.call_args.args[0], "private_database")
        self.assertNotIn("private_database", str(result))

    def test_missing_site_is_rejected_before_any_export(self):
        with (
            patch.object(migration, "load_state", return_value=self.state()),
            patch.object(migration, "source_export_database") as export_old,
        ):
            with self.assertRaisesRegex(migration.PullMigrationError, "SITE_NOT_IN_MIGRATION"):
                migration.diagnose_sql_difference("pull-test-diagnostic", "unknown.example")
            export_old.assert_not_called()

    def test_non_failed_migration_is_rejected_before_any_export(self):
        state = self.state()
        state["status"] = "PREPARED"
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_database") as export_old,
        ):
            with self.assertRaisesRegex(migration.PullMigrationError, "REQUIRES_PREPARE_FAILED"):
                migration.diagnose_sql_difference("pull-test-diagnostic", "site.example")
            export_old.assert_not_called()

    def test_multiple_databases_are_rejected_before_any_export(self):
        state = self.state()
        state["sites"][0]["mysql_databases"].append("other_database")
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_database") as export_old,
        ):
            with self.assertRaisesRegex(migration.PullMigrationError, "SINGLE_DATABASE_REQUIRED"):
                migration.diagnose_sql_difference("pull-test-diagnostic", "site.example")
            export_old.assert_not_called()


if __name__ == "__main__":
    unittest.main()
