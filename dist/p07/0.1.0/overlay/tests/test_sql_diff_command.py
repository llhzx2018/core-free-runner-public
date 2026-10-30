"""SQL diagnostic command must never perform migration or persist data."""
from __future__ import annotations

from copy import deepcopy
import gzip
import subprocess
import sys
import tempfile
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
            patch.object(migration, "source_export_helper_matches_current", return_value=True),
            patch.object(migration, "source_export_database") as export_old,
            patch.object(migration, "pull_path") as pull,
            patch.object(migration.sql_diff_probe, "require_nonempty_source_schema", return_value=42),
            patch.object(migration.cloudpanel, "export_database") as export_new,
            patch.object(migration.sql_diff_probe, "diagnostic", return_value={
                "schema": "SQL_DIFF_EVIDENCE_V2", "verification": "NOT_A_PASS_GATE",
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

    def test_advisory_retries_an_unusable_export_once_then_diagnoses(self):
        state = self.state()
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_helper_matches_current", return_value=True),
            patch.object(migration, "source_export_database") as export_old,
            patch.object(migration, "pull_path") as pull,
            patch.object(migration.sql_diff_probe, "require_nonempty_source_schema",
                         side_effect=[migration.sql_diff_probe.AdvisoryDiagnosticUnavailable("invalid"), 42]),
            patch.object(migration.cloudpanel, "export_database") as export_new,
            patch.object(migration.sql_diff_probe, "diagnostic",
                         return_value={"schema": "SQL_DIFF_EVIDENCE_V2",
                                       "verification": "NOT_A_PASS_GATE"}) as diagnostic,
            patch.object(migration, "source_remote") as cleanup,
            patch.object(migration, "save_state") as state_write,
            patch.object(migration, "tempfile") as temporary,
            patch.object(migration.os, "chmod"),
        ):
            temporary.TemporaryDirectory.return_value.__enter__.return_value = "/tmp/test-private-probe"
            result = migration.diagnose_sql_difference("pull-test-diagnostic", "site.example")
        self.assertEqual(export_old.call_count, 2)
        self.assertEqual(pull.call_count, 2)
        self.assertNotEqual(export_old.call_args_list[0].args[2],
                            export_old.call_args_list[1].args[2])
        export_new.assert_called_once()
        diagnostic.assert_called_once()
        self.assertEqual(result["evidence"]["source_export_readback"],
                         {"attempts": 2, "source_tables": 42})
        self.assertEqual(cleanup.call_count, 2)
        state_write.assert_not_called()
        self.assertNotIn("private_database", str(result))

    def test_advisory_double_invalid_export_does_not_touch_target(self):
        state = self.state()
        original = deepcopy(state)
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_helper_matches_current", return_value=True),
            patch.object(migration, "source_export_database") as export_old,
            patch.object(migration, "pull_path") as pull,
            patch.object(migration.sql_diff_probe, "require_nonempty_source_schema",
                         side_effect=migration.sql_diff_probe.AdvisoryDiagnosticUnavailable("invalid")),
            patch.object(migration.cloudpanel, "export_database") as target_export,
            patch.object(migration.sql_diff_probe, "diagnostic") as diagnostic,
            patch.object(migration, "source_remote") as cleanup,
            patch.object(migration, "save_state") as state_write,
            patch.object(migration, "tempfile") as temporary,
            patch.object(migration.os, "chmod"),
        ):
            temporary.TemporaryDirectory.return_value.__enter__.return_value = "/tmp/test-private-probe"
            result = migration.diagnose_sql_difference("pull-test-diagnostic", "site.example")
        self.assertEqual(export_old.call_count, 2)
        self.assertEqual(pull.call_count, 2)
        target_export.assert_not_called()
        diagnostic.assert_not_called()
        self.assertEqual(result["evidence"]["verification"], "SOURCE_EXPORT_UNUSABLE")
        self.assertEqual(result["evidence"]["data_content"]["comparison"], "UNAVAILABLE")
        self.assertEqual(
            result["evidence"]["source_export_readback"],
            {"attempts": 2, "source_tables": None},
        )
        self.assertIsNone(result["evidence"]["source_export_readback"]["source_tables"])
        self.assertEqual(cleanup.call_count, 2)
        state_write.assert_not_called()
        self.assertEqual(state, original)
        self.assertNotIn("private_database", str(result))

    def test_stale_advisory_helper_is_ephemeral_and_state_is_immutable(self):
        state = self.state()
        original = deepcopy(state)
        new_runtime = "/var/lib/vf-server-ops/pull-source/probe-" + "a" * 32 + "/runtime"
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_helper_matches_current",
                         side_effect=[False, True]) as identity,
            patch.object(migration, "stage_source_runtime", return_value=new_runtime) as stage,
            patch.object(migration, "source_export_database") as export_old,
            patch.object(migration, "pull_path"),
            patch.object(migration.sql_diff_probe, "require_nonempty_source_schema", return_value=42),
            patch.object(migration.cloudpanel, "export_database"),
            patch.object(migration.sql_diff_probe, "diagnostic",
                         return_value={"schema": "SQL_DIFF_EVIDENCE_V2", "verification": "NOT_A_PASS_GATE"}),
            patch.object(migration, "source_remote") as remove_dump,
            patch.object(migration, "cleanup_probe_runtime") as cleanup,
            patch.object(migration, "save_state") as write_state,
            patch.object(migration, "tempfile") as temporary,
            patch.object(migration.os, "chmod"),
        ):
            temporary.TemporaryDirectory.return_value.__enter__.return_value = "/tmp/test-private-probe"
            result = migration.diagnose_sql_difference("pull-test-diagnostic", "site.example")
        self.assertEqual(state, original)
        self.assertEqual(identity.call_count, 2)
        stage.assert_called_once()
        self.assertEqual(export_old.call_args.args[0]["source_runtime_path"], new_runtime)
        self.assertEqual(export_old.call_count, 1)
        cleanup.assert_called_once_with(state["source"], new_runtime)
        remove_dump.assert_called_once()
        write_state.assert_not_called()
        self.assertTrue(result["source_temporary_helper_written"])
        self.assertTrue(result["source_helper_cleanup_attempted"])
        self.assertFalse(result["migration_state_modified"])
        self.assertFalse(result["database_writes_performed"])
        self.assertNotIn("private_database", str(result))

    def test_failed_stale_helper_attestation_never_reads_target_or_mutates_state(self):
        state = self.state()
        original = deepcopy(state)
        new_runtime = "/var/lib/vf-server-ops/pull-source/probe-" + "b" * 32 + "/runtime"
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_helper_matches_current",
                         side_effect=[False, False]),
            patch.object(migration, "stage_source_runtime", return_value=new_runtime),
            patch.object(migration, "source_export_database") as export_old,
            patch.object(migration.cloudpanel, "export_database") as target_export,
            patch.object(migration, "cleanup_probe_runtime") as cleanup,
            patch.object(migration, "save_state") as write_state,
        ):
            with self.assertRaisesRegex(migration.PullMigrationError, "SQL_DIAGNOSTIC_HELPER_UNVERIFIED"):
                migration.diagnose_sql_difference("pull-test-diagnostic", "site.example")
        self.assertEqual(state, original)
        export_old.assert_not_called()
        target_export.assert_not_called()
        write_state.assert_not_called()
        cleanup.assert_called_once_with(state["source"], new_runtime)

    def test_pinned_source_helper_no_schema_marker_is_fixed_and_nonsecret(self):
        state = self.state()
        source = state["source"]
        known = subprocess.CompletedProcess(
            [], 13, "", "ERROR: SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA\n",
        )
        with patch.object(migration, "source_python", return_value=known):
            with self.assertRaisesRegex(
                migration.PullMigrationError, "^SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA$",
            ):
                migration.source_export_database(
                    state, "private_database",
                    "/var/lib/vf-server-ops/pull-source/pull-test/data/dump.sql.gz",
                )
        # Anything other than the exact pinned helper marker remains an
        # ordinary export failure and must never echo remote stderr.
        for response in (
            subprocess.CompletedProcess([], 13, "", "ERROR: SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA\nPRIVATE_SECRET"),
            subprocess.CompletedProcess([], 13, "", "Authentication failed PRIVATE_SECRET"),
            subprocess.CompletedProcess([], 1, "", "ERROR: SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA"),
        ):
            with self.subTest(response=response.returncode), patch.object(
                migration, "source_python", return_value=response
            ):
                with self.assertRaises(migration.PullMigrationError) as caught:
                    migration.source_export_database(
                        state, "private_database",
                        "/var/lib/vf-server-ops/pull-source/pull-test/data/dump.sql.gz",
                    )
                self.assertIn("old-server MySQL export failed", str(caught.exception))
                self.assertNotIn("PRIVATE_SECRET", str(caught.exception))
                self.assertNotIn("NO_TABLE_SCHEMA", str(caught.exception))
        self.assertEqual(source, state["source"])

    def test_pinned_source_rejects_first_export_then_second_is_accepted(self):
        state = self.state()
        original = deepcopy(state)
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_helper_matches_current", return_value=True),
            patch.object(migration, "source_export_database",
                         side_effect=[migration.PullMigrationError("SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA"), None]) as source_export,
            patch.object(migration, "pull_path") as transfer,
            patch.object(migration.sql_diff_probe, "require_nonempty_source_schema", return_value=42),
            patch.object(migration.cloudpanel, "export_database") as target_export,
            patch.object(migration.sql_diff_probe, "diagnostic",
                         return_value={"schema": "SQL_DIFF_EVIDENCE_V2",
                                       "verification": "NOT_A_PASS_GATE"}),
            patch.object(migration, "source_remote") as cleanup,
            patch.object(migration, "save_state") as save,
            patch.object(migration, "tempfile") as temporary,
            patch.object(migration.os, "chmod"),
        ):
            temporary.TemporaryDirectory.return_value.__enter__.return_value = "/tmp/test-private-probe"
            result = migration.diagnose_sql_difference("pull-test-diagnostic", "site.example")
        self.assertEqual(source_export.call_count, 2)
        self.assertEqual(transfer.call_count, 1)
        target_export.assert_called_once()
        self.assertEqual(cleanup.call_count, 2)
        self.assertEqual(result["evidence"]["source_export_readback"],
                         {"attempts": 2, "source_tables": 42})
        self.assertEqual(state, original)
        save.assert_not_called()
        self.assertNotIn("private_database", str(result))

    def test_pinned_source_rejects_both_exports_so_count_remains_unknown(self):
        state = self.state()
        original = deepcopy(state)
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_helper_matches_current", return_value=True),
            patch.object(migration, "source_export_database",
                         side_effect=migration.PullMigrationError("SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA")) as export,
            patch.object(migration, "pull_path") as transfer,
            patch.object(migration.cloudpanel, "export_database") as target_export,
            patch.object(migration, "source_remote") as cleanup,
            patch.object(migration, "save_state") as save,
            patch.object(migration, "tempfile") as temporary,
            patch.object(migration.os, "chmod"),
        ):
            temporary.TemporaryDirectory.return_value.__enter__.return_value = "/tmp/test-private-probe"
            result = migration.diagnose_sql_difference("pull-test-diagnostic", "site.example")
        self.assertEqual(export.call_count, 2)
        self.assertEqual(cleanup.call_count, 2)
        self.assertEqual(result["evidence"]["verification"], "SOURCE_EXPORT_UNUSABLE")
        self.assertEqual(result["evidence"]["source_export_readback"],
                         {"attempts": 2, "source_tables": None})
        transfer.assert_not_called()
        target_export.assert_not_called()
        save.assert_not_called()
        self.assertEqual(state, original)

    def test_auth_and_transport_export_errors_never_retry(self):
        state = self.state()
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_helper_matches_current", return_value=True),
            patch.object(migration, "source_export_database",
                         side_effect=migration.PullMigrationError("old-server MySQL export failed")) as export,
            patch.object(migration, "pull_path") as transfer,
            patch.object(migration.cloudpanel, "export_database") as target_export,
            patch.object(migration, "source_remote") as cleanup,
            patch.object(migration, "save_state") as save,
            patch.object(migration, "tempfile") as temporary,
            patch.object(migration.os, "chmod"),
        ):
            temporary.TemporaryDirectory.return_value.__enter__.return_value = "/tmp/test-private-probe"
            with self.assertRaisesRegex(
                migration.PullMigrationError, "^SQL_DIAGNOSTIC_EXPORT_UNAVAILABLE$",
            ):
                migration.diagnose_sql_difference("pull-test-diagnostic", "site.example")
        export.assert_called_once()
        transfer.assert_not_called()
        target_export.assert_not_called()
        cleanup.assert_called_once()
        save.assert_not_called()

    def test_expected_table_count_requires_complete_source_readback(self):
        state = self.state()
        original = deepcopy(state)
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_helper_matches_current", return_value=True),
            patch.object(migration, "source_export_database") as source_export,
            patch.object(migration, "pull_path") as transfer,
            patch.object(migration.sql_diff_probe, "require_nonempty_source_schema",
                         side_effect=[41, 42]),
            patch.object(migration.cloudpanel, "export_database") as target_export,
            patch.object(migration.sql_diff_probe, "diagnostic",
                         return_value={"schema": "SQL_DIFF_EVIDENCE_V2",
                                       "verification": "NOT_A_PASS_GATE"}) as advisory,
            patch.object(migration, "source_remote") as cleanup,
            patch.object(migration, "save_state") as save,
            patch.object(migration, "tempfile") as temporary,
            patch.object(migration.os, "chmod"),
        ):
            temporary.TemporaryDirectory.return_value.__enter__.return_value = "/tmp/test-private-probe"
            result = migration.diagnose_sql_difference(
                "pull-test-diagnostic", "site.example", expected_source_tables=42,
            )
        self.assertEqual(source_export.call_count, 2)
        self.assertEqual(transfer.call_count, 2)
        target_export.assert_called_once()
        advisory.assert_called_once()
        self.assertEqual(cleanup.call_count, 2)
        self.assertEqual(
            result["evidence"]["source_export_readback"],
            {"attempts": 2, "source_tables": 42, "expected_source_tables": 42,
             "source_table_count_matches_expectation": True},
        )
        self.assertEqual(result["evidence"]["verification"], "NOT_A_PASS_GATE")
        self.assertFalse(result["migration_state_modified"])
        self.assertFalse(result["database_writes_performed"])
        save.assert_not_called()
        self.assertEqual(state, original)
        self.assertNotIn("private_database", str(result))

    def test_two_partial_exports_never_run_target_comparison(self):
        state = self.state()
        original = deepcopy(state)
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_helper_matches_current", return_value=True),
            patch.object(migration, "source_export_database") as export_old,
            patch.object(migration, "pull_path") as transfer,
            patch.object(migration.sql_diff_probe, "require_nonempty_source_schema",
                         side_effect=[40, 41]),
            patch.object(migration.cloudpanel, "export_database") as target_export,
            patch.object(migration.sql_diff_probe, "diagnostic") as diagnostic,
            patch.object(migration, "source_remote") as cleanup,
            patch.object(migration, "save_state") as save,
            patch.object(migration, "tempfile") as temporary,
            patch.object(migration.os, "chmod"),
        ):
            temporary.TemporaryDirectory.return_value.__enter__.return_value = "/tmp/test-private-probe"
            result = migration.diagnose_sql_difference(
                "pull-test-diagnostic", "site.example", expected_source_tables=42,
            )
        self.assertEqual(export_old.call_count, 2)
        self.assertEqual(transfer.call_count, 2)
        self.assertEqual(cleanup.call_count, 2)
        target_export.assert_not_called()
        diagnostic.assert_not_called()
        save.assert_not_called()
        self.assertEqual(state, original)
        self.assertEqual(result["evidence"]["verification"], "SOURCE_TABLE_COUNT_MISMATCH")
        self.assertEqual(result["evidence"]["source_export_readback"], {
            "attempts": 2, "source_tables": 41, "expected_source_tables": 42,
            "source_table_count_matches_expectation": False,
        })
        self.assertEqual(result["evidence"]["data_content"]["comparison"], "UNAVAILABLE")
        self.assertNotIn("private_database", str(result))

    def test_partial_export_then_unusable_export_still_never_passes(self):
        state = self.state()
        with (
            patch.object(migration, "load_state", return_value=state),
            patch.object(migration, "source_export_helper_matches_current", return_value=True),
            patch.object(migration, "source_export_database") as export_old,
            patch.object(migration, "pull_path"),
            patch.object(migration.sql_diff_probe, "require_nonempty_source_schema",
                         side_effect=[41, migration.sql_diff_probe.AdvisoryDiagnosticUnavailable("incomplete")]),
            patch.object(migration.cloudpanel, "export_database") as target_export,
            patch.object(migration.sql_diff_probe, "diagnostic") as diagnostic,
            patch.object(migration, "source_remote"),
            patch.object(migration, "save_state") as save,
            patch.object(migration, "tempfile") as temporary,
            patch.object(migration.os, "chmod"),
        ):
            temporary.TemporaryDirectory.return_value.__enter__.return_value = "/tmp/test-private-probe"
            result = migration.diagnose_sql_difference(
                "pull-test-diagnostic", "site.example", expected_source_tables=42,
            )
        self.assertEqual(export_old.call_count, 2)
        self.assertEqual(result["evidence"]["verification"], "SOURCE_TABLE_COUNT_MISMATCH")
        self.assertEqual(result["evidence"]["source_export_readback"]["attempts"], 2)
        target_export.assert_not_called()
        diagnostic.assert_not_called()
        save.assert_not_called()

    def test_invalid_expected_count_rejected_before_state_or_source_access(self):
        with (
            patch.object(migration, "load_state") as load,
            patch.object(migration, "stage_source_runtime") as stage,
            patch.object(migration, "source_export_database") as export_old,
        ):
            for bad in (0, -1, 100001, True, False, "42", 42.0):
                with self.subTest(value=bad), self.assertRaisesRegex(
                    migration.PullMigrationError, "^SQL_DIAGNOSTIC_EXPECTED_TABLES_INVALID$"
                ):
                    migration.diagnose_sql_difference(
                        "pull-test-diagnostic", "site.example",
                        expected_source_tables=bad,
                    )
            load.assert_not_called()
            stage.assert_not_called()
            export_old.assert_not_called()

    def test_source_helper_refuses_header_only_export(self):
        output = Path("/var/lib/vf-server-ops/pull-source/test/source.sql.gz")
        with (
            patch.object(migration.cloudpanel, "export_database") as export_old,
            patch.object(migration.sql_diff_probe, "require_nonempty_source_schema",
                         side_effect=migration.sql_diff_probe.AdvisoryDiagnosticUnavailable("invalid")),
            patch.object(migration.Path, "mkdir"),
            patch.object(migration.os, "chmod"),
        ):
            with self.assertRaisesRegex(
                migration.PullMigrationError, "SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA",
            ):
                migration.source_export_db("private_database", output)
            export_old.assert_called_once()


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


    def test_incomplete_source_export_blocks_before_target_db_import(self):
        state = {
            "migration_id": "pull-private-example",
            "source": {"host": "example.invalid"},
        }
        site = {
            "domain": "site.example",
            "site_root": "/private/site",
            "mysql_databases": ["private_database"],
        }
        with tempfile.TemporaryDirectory() as directory:
            def supply_header_only(_source, _remote, local_path):
                with gzip.open(local_path, "wt", encoding="utf-8") as handle:
                    handle.write("-- a nonempty but unusable SQL export\\n")

            with (
                patch.object(migration, "state_dir", return_value=Path(directory)),
                patch.object(migration, "source_export_database"),
                patch.object(migration, "pull_path", side_effect=supply_header_only),
                patch.object(migration, "source_remote") as cleanup,
                patch.object(migration, "progress_note"),
                patch.object(migration.legacy, "target_create_database_local") as mutation,
                patch.object(migration.cloudpanel, "export_database") as target_export,
            ):
                with self.assertRaisesRegex(
                    migration.PullMigrationError,
                    "old-server MySQL export has no verifiable table schema",
                ):
                    migration.sync_site_databases(state, site, phase="prepare")
                mutation.assert_not_called()
                target_export.assert_not_called()
                cleanup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
