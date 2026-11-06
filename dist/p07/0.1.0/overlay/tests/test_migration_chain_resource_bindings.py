"""17-site original external/SQLite resource ownership, no real server access."""
from __future__ import annotations

import copy
import json
import os
import sqlite3
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_chain_asset_audit as assets
import migration_chain_consolidation as consolidated
import migration_chain_execution_scope as ownership
import migration_chain_final_saga as saga
import server_migration_pull as pull
from tests.test_migration_chain_execution_scope import three_partial_tasks


def fixture():
    parent, child, tail = three_partial_tasks()
    parent["external_assets"] = [{
        "path": "/home/owner0/assets", "user": "owner0", "kind": "DIRECTORY"
    }]
    parent["sqlite_assets"] = []
    child["external_assets"] = []
    child["sqlite_assets"] = [{
        "path": "/home/owner8/data/store.sqlite", "user": "owner8",
        "mode": 0o600,
    }]
    tail["external_assets"] = [{
        "path": "/home/owner16/catalog.txt", "user": "owner16", "kind": "FILE"
    }]
    tail["sqlite_assets"] = []
    with tempfile.TemporaryDirectory() as temp:
        scope = ownership.scope(parent, child, tail, root=Path(temp),
                                private_owner=os.geteuid())
    return (parent, child, tail), saga.operation_plan(scope)


class OriginalResourceBindingsTests(unittest.TestCase):
    def test_three_original_tasks_bound_without_state_or_network_writes(self):
        tasks, plan = fixture()
        original = copy.deepcopy(tasks)
        with mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(pull, "source_remote") as remote, \
             mock.patch.object(pull, "sync_external_assets") as ext, \
             mock.patch.object(pull, "sync_sqlite_assets") as sqlite:
            result = assets.bind_original_resources(plan, *tasks)
        self.assertEqual(result["schema"],
                         "P07_CHAIN_ORIGINAL_RESOURCE_BINDINGS_V1")
        self.assertEqual(result["resource_count"], 3)
        self.assertEqual(result["external_count"], 2)
        self.assertEqual(result["sqlite_count"], 1)
        self.assertEqual(
            {x["owner"] for x in result["resources"]},
            {t["migration_id"] for t in tasks},
        )
        self.assertEqual(len({
            (x["owner"], x["resource_index"], x["kind"])
            for x in result["resources"]
        }), 3)
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["recovery_points_verified"])
        self.assertFalse(result["writes_performed"])
        self.assertEqual(tasks, original)
        for call in (save, remote, ext, sqlite):
            call.assert_not_called()
        as_json = json.dumps(result)
        for secret in ("/home/", "store.sqlite", "catalog.txt", "password"):
            self.assertNotIn(secret, as_json)

    def test_cross_task_owner_cannot_be_adopted_or_deduplicated(self):
        tasks, plan = fixture()
        tasks[0]["external_assets"][0]["user"] = "owner8"
        tasks[0]["external_assets"][0]["path"] = "/home/owner8/assets"
        with self.assertRaisesRegex(assets.ResourceOwnerBlocked,
                                    "RESOURCE_CROSS_TASK_OWNER_CONFLICT"):
            assets.bind_original_resources(plan, *tasks)

    def test_same_path_in_multiple_tasks_must_not_pick_first_owner(self):
        tasks, plan = fixture()
        duplicate = copy.deepcopy(tasks[0]["external_assets"][0])
        tasks[0]["external_assets"].append(duplicate)
        with self.assertRaisesRegex(assets.ResourceOwnerBlocked,
                                    "RESOURCE_PATH_OVERLAP_UNPROVEN"):
            assets.bind_original_resources(plan, *tasks)

    def test_nested_external_or_sqlite_inside_external_is_blocked(self):
        tasks, plan = fixture()
        tasks[0]["sqlite_assets"] = [{
            "path": "/home/owner0/assets/app.sqlite",
            "user": "owner0", "mode": 0o600,
        }]
        with self.assertRaisesRegex(assets.ResourceOwnerBlocked,
                                    "RESOURCE_PATH_OVERLAP_UNPROVEN"):
            assets.bind_original_resources(plan, *tasks)

    def test_path_traversal_and_outside_home_fail_closed(self):
        for path in ("/etc/passwd", "/home/owner0/../owner1/assets",
                     "/home/owner0//assets", "/home/owner0/./assets",
                     "/home/owner0", "relative/backup"):
            with self.subTest(path=path):
                tasks, plan = fixture()
                tasks[0]["external_assets"][0]["path"] = path
                with self.assertRaises(assets.ResourceOwnerBlocked):
                    assets.bind_original_resources(plan, *tasks)

    def test_site_contract_and_target_identity_changed_before_snapshot(self):
        for change in ("site", "target", "source", "plan"):
            with self.subTest(change=change):
                tasks, plan = fixture()
                if change == "site":
                    tasks[0]["sites"][0]["runtime"]["version"] = "8.4"
                elif change == "target":
                    tasks[1]["target_server_identity"] = "sha256:wrong"
                elif change == "source":
                    tasks[2]["source"]["host"] = "other.example.test"
                else:
                    plan["steps"][0]["site_contract_sha256"] = "f" * 64
                with self.assertRaises(assets.ResourceOwnerBlocked):
                    assets.bind_original_resources(plan, *tasks)

    def test_metadata_change_is_digest_change_not_unverified_parity(self):
        tasks, plan = fixture()
        before = assets.bind_original_resources(plan, *tasks)
        tasks[0]["external_assets"][0]["optional_note"] = "changed"
        after = assets.bind_original_resources(plan, *tasks)
        self.assertNotEqual(before["inventory_sha256"],
                            after["inventory_sha256"])
        self.assertFalse(after["recovery_points_verified"])

    def test_sqlite_mode_and_unknown_external_type_are_not_accepted(self):
        for mode in (0o666, -1, 0o1000, "0600"):
            with self.subTest(mode=mode):
                tasks, plan = fixture()
                tasks[1]["sqlite_assets"][0]["mode"] = mode
                with self.assertRaisesRegex(assets.ResourceOwnerBlocked,
                                            "RESOURCE_SQLITE_MODE_UNSAFE"):
                    assets.bind_original_resources(plan, *tasks)
        tasks, plan = fixture()
        tasks[2]["external_assets"][0]["kind"] = "UNKNOWN"
        with self.assertRaisesRegex(assets.ResourceOwnerBlocked,
                                    "RESOURCE_EXTERNAL_KIND_UNVERIFIED"):
            assets.bind_original_resources(plan, *tasks)

    def test_missing_inventory_and_duplicate_owner_are_rejected(self):
        tasks, plan = fixture()
        tasks[1].pop("sqlite_assets")
        with self.assertRaisesRegex(assets.ResourceOwnerBlocked,
                                    "RESOURCE_INVENTORY_MISSING_OR_UNBOUNDED"):
            assets.bind_original_resources(plan, *tasks)
        tasks, plan = fixture()
        tasks[2]["migration_id"] = tasks[0]["migration_id"]
        with self.assertRaises(assets.ResourceOwnerBlocked):
            assets.bind_original_resources(plan, *tasks)



class ResourceRecoveryRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.environment = mock.patch.dict(os.environ, {
            "P07_SYNTHETIC_SAGA_FIXTURE": "1",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.directory.chmod(0o700)
        self.tasks, self.plan = fixture()
        self.bindings = assets.bind_original_resources(
            self.plan, *self.tasks)
        for item in self.bindings["resources"]:
            paths = saga._resource_sandbox_paths(self.directory, item)
            paths["base"].mkdir(mode=0o700)
            paths["source"].mkdir(mode=0o700)
            paths["target"].mkdir(mode=0o700)
            if item["kind"] == "SQLITE":
                for key, value in (("source", "new"), ("target", "old")):
                    with sqlite3.connect(str(
                        paths[key] / "data.sqlite"
                    )) as conn:
                        conn.execute("CREATE TABLE records (name TEXT)")
                        conn.execute("INSERT INTO records VALUES (?)", (value,))
            else:
                (paths["source"] / "entry.txt").write_text("new")
                (paths["target"] / "entry.txt").write_text("old")
                (paths["target"] / "preserve.txt").write_text("keep")

    def snapshot(self):
        return {
            (item["owner"], item["source_path_sha256"]):
            saga._resource_fingerprint(
                item["kind"],
                saga._resource_sandbox_paths(self.directory, item)["target"])
            for item in self.bindings["resources"]
        }

    def test_entire_external_and_sqlite_reversible_rehearsal(self):
        before = self.snapshot()
        result = saga.rehearse_bound_resources(
            self.plan, self.bindings, self.tasks, self.directory,
            synthetic_authority=True)
        self.assertEqual(result["status"],
                         "ALL_RESOURCE_PROMOTIONS_VERIFIED_NOT_CUTOVER")
        self.assertEqual(result["resource_count"], 3)
        self.assertFalse(result["cutover_allowed"])
        self.assertNotEqual(self.snapshot(), before)
        journal = json.loads((self.directory /
                              "resource-rehearsal.json").read_text())
        self.assertTrue(all(
            x["status"] == "PROMOTED_VERIFIED"
            for x in journal["items"]))
        restored = saga.rollback_rehearsed_resources(
            self.plan, self.bindings, self.tasks, self.directory,
            synthetic_authority=True)
        self.assertEqual(restored["status"],
                         "ROLLED_BACK_VERIFIED_NOT_CUTOVER")
        self.assertEqual(restored["restored_count"], 3)
        self.assertEqual(self.snapshot(), before)
        for item in self.bindings["resources"]:
            paths = saga._resource_sandbox_paths(self.directory, item)
            self.assertTrue(paths["recovery"].exists())
            self.assertTrue(paths["failed"].exists())
            self.assertTrue(paths["source"].exists())
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "ROLLBACK_RECEIPT_UNVERIFIED"):
            saga.rollback_rehearsed_resources(
                self.plan, self.bindings, self.tasks, self.directory,
                synthetic_authority=True)

    def test_known_downstream_failure_reverse_restores_first_resource(self):
        before = self.snapshot()
        result = saga.rehearse_bound_resources(
            self.plan, self.bindings, self.tasks, self.directory,
            synthetic_authority=True, fail_after_promotions=1)
        self.assertEqual(result["status"],
                         "ROLLED_BACK_VERIFIED_NOT_CUTOVER")
        self.assertEqual(result["restored_count"], 1)
        self.assertEqual(self.snapshot(), before)
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "RESOURCE_EXISTING_ATTEMPT_RETAINED"):
            saga.rehearse_bound_resources(
                self.plan, self.bindings, self.tasks, self.directory,
                synthetic_authority=True)

    def test_crash_between_renames_never_guesses_rollback(self):
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "RESOURCE_PROMOTION_UNCERTAIN"):
            saga.rehearse_bound_resources(
                self.plan, self.bindings, self.tasks, self.directory,
                synthetic_authority=True, interrupt_after_rename=True)
        journal = json.loads((self.directory /
                              "resource-rehearsal.json").read_text())
        self.assertEqual(journal["status"], "RECOVERY_REQUIRED")
        self.assertEqual(journal["items"][0]["status"],
                         "PROMOTION_UNKNOWN_RETAIN_EVIDENCE")
        first = saga._resource_sandbox_paths(
            self.directory, self.bindings["resources"][0])
        self.assertFalse(first["target"].exists())
        self.assertTrue(first["held"].exists())
        with self.assertRaises(saga.SagaBlocked):
            saga.rollback_rehearsed_resources(
                self.plan, self.bindings, self.tasks, self.directory,
                synthetic_authority=True)

    def test_corrupt_sqlite_blocks_before_journal_or_promotion(self):
        item = next(x for x in self.bindings["resources"]
                    if x["kind"] == "SQLITE")
        source = saga._resource_sandbox_paths(
            self.directory, item)["source"] / "data.sqlite"
        source.write_bytes(b"not-a-sqlite-database")
        with self.assertRaises(saga.SagaBlocked):
            saga.rehearse_bound_resources(
                self.plan, self.bindings, self.tasks, self.directory,
                synthetic_authority=True)
        self.assertFalse((self.directory / "resource-rehearsal.json").exists())

    def test_resource_symlink_and_ownership_forgery_block_early(self):
        item = self.bindings["resources"][0]
        path = saga._resource_sandbox_paths(self.directory, item)
        (path["target"] / "link").symlink_to(
            path["source"] / "entry.txt" if item["kind"] != "SQLITE"
            else path["source"] / "data.sqlite")
        with self.assertRaises(saga.SagaBlocked):
            saga.rehearse_bound_resources(
                self.plan, self.bindings, self.tasks, self.directory,
                synthetic_authority=True)
        self.assertFalse((self.directory / "resource-rehearsal.json").exists())
        forged = copy.deepcopy(self.bindings)
        forged["resources"][0]["owner"] = "pull-changed"
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "RESOURCE_BINDINGS_CHANGED"):
            saga.rehearse_bound_resources(
                self.plan, forged, self.tasks, self.directory,
                synthetic_authority=True)

    def test_snapshot_failure_retains_intent_and_no_automatic_retry(self):
        with mock.patch.object(saga, "_copy_recovery_resource",
                               side_effect=OSError("failure")):
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "SNAPSHOT_RECOVERY_REQUIRED"):
                saga.rehearse_bound_resources(
                    self.plan, self.bindings, self.tasks, self.directory,
                    synthetic_authority=True)
        state = json.loads((self.directory /
                            "resource-rehearsal.json").read_text())
        self.assertEqual(state["status"], "RECOVERY_REQUIRED")
        self.assertEqual(state["items"][0]["status"],
                         "RECOVERY_UNKNOWN_RETAIN_EVIDENCE")
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "RESOURCE_EXISTING_ATTEMPT_RETAINED"):
            saga.rehearse_bound_resources(
                self.plan, self.bindings, self.tasks, self.directory,
                synthetic_authority=True)

    def test_modified_recovery_copy_refuses_rollback_before_overwrite(self):
        before = self.snapshot()
        saga.rehearse_bound_resources(
            self.plan, self.bindings, self.tasks, self.directory,
            synthetic_authority=True)
        item = next(x for x in self.bindings["resources"]
                    if x["kind"] == "EXTERNAL_ASSET")
        paths = saga._resource_sandbox_paths(self.directory, item)
        (paths["recovery"] / "entry.txt").write_text("tampered-backup")
        mutated_target = self.snapshot()
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "ROLLBACK_CONCURRENT_DRIFT"):
            saga.rollback_rehearsed_resources(
                self.plan, self.bindings, self.tasks, self.directory,
                synthetic_authority=True)
        self.assertEqual(self.snapshot(), mutated_target)
        self.assertNotEqual(mutated_target, before)
        journal = json.loads((self.directory /
                              "resource-rehearsal.json").read_text())
        self.assertEqual(journal["status"],
                         "ALL_RESOURCE_PROMOTIONS_VERIFIED_NOT_CUTOVER")

    def test_locked_database_boundary_reverses_assets_without_db_operations(self):
        import migration_final_db_batch as batch
        import migration_final_db_shadow as shadow
        before = self.snapshot()
        db_scope = consolidated.bind_locked_original_database_scope(
            self.plan, *self.tasks)
        staged = saga.rehearse_bound_resources(
            self.plan, self.bindings, self.tasks, self.directory,
            synthetic_authority=True)
        self.assertEqual(staged["resource_count"], 3)
        self.assertNotEqual(self.snapshot(), before)
        with mock.patch.object(batch, "switch_verified_shadow_batch") as switch, \
             mock.patch.object(batch, "rollback_verified_shadow_batch") as rb, \
             mock.patch.object(shadow, "activate_verified_shadow") as activate, \
             mock.patch.object(pull, "source_remote") as ssh, \
             mock.patch.object(pull, "sync_site_databases") as db_import:
            result = saga.reject_unverified_original_db_and_restore_resources(
                self.plan, db_scope, self.bindings, self.tasks,
                self.directory, synthetic_authority=True)
        for operation in (switch, rb, activate, ssh, db_import):
            operation.assert_not_called()
        self.assertEqual(result["status"],
                         "RESOURCE_ROLLBACK_VERIFIED_DATABASE_UNTOUCHED_NOT_CUTOVER")
        self.assertEqual(result["database_count"], 3)
        self.assertEqual(result["restored_resource_count"], 3)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["www3_reconnected"])
        self.assertFalse(result["database_writes_performed"])
        db_receipt = json.loads((self.directory /
                                 "locked-db-boundary.json").read_text())
        self.assertTrue(db_receipt["resource_rollback_verified"])
        self.assertFalse(db_receipt["database_writes_performed"])
        for item in self.bindings["resources"]:
            paths = saga._resource_sandbox_paths(self.directory, item)
            self.assertTrue(paths["failed"].exists())
            self.assertTrue(paths["recovery"].exists())
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "DB_BOUNDARY_PRIOR_ATTEMPT_RETAINED"):
            saga.reject_unverified_original_db_and_restore_resources(
                self.plan, db_scope, self.bindings, self.tasks,
                self.directory, synthetic_authority=True)

    def test_changed_database_owner_blocks_boundary_before_any_rollback(self):
        db_scope = consolidated.bind_locked_original_database_scope(
            self.plan, *self.tasks)
        saga.rehearse_bound_resources(
            self.plan, self.bindings, self.tasks, self.directory,
            synthetic_authority=True)
        after = self.snapshot()
        forged = copy.deepcopy(db_scope)
        forged["databases"][0]["original_owner"] = "pull-forged"
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "DB_ORIGINAL_SCOPE_CHANGED"):
            saga.reject_unverified_original_db_and_restore_resources(
                self.plan, forged, self.bindings, self.tasks,
                self.directory, synthetic_authority=True)
        self.assertEqual(self.snapshot(), after)
        self.assertFalse((self.directory / "locked-db-boundary.json").exists())

    def test_corrupt_independent_recovery_blocks_db_boundary_success(self):
        db_scope = consolidated.bind_locked_original_database_scope(
            self.plan, *self.tasks)
        saga.rehearse_bound_resources(
            self.plan, self.bindings, self.tasks, self.directory,
            synthetic_authority=True)
        item = next(x for x in self.bindings["resources"]
                    if x["kind"] == "EXTERNAL_ASSET")
        paths = saga._resource_sandbox_paths(self.directory, item)
        (paths["recovery"] / "entry.txt").write_text("tampered")
        after = self.snapshot()
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "DB_RESOURCE_REVERSE_RECOVERY_REQUIRED"):
            saga.reject_unverified_original_db_and_restore_resources(
                self.plan, db_scope, self.bindings, self.tasks,
                self.directory, synthetic_authority=True)
        self.assertEqual(self.snapshot(), after)
        recorded = json.loads((self.directory /
                               "locked-db-boundary.json").read_text())
        self.assertEqual(recorded["status"], "RESOURCE_RECOVERY_REQUIRED")
        self.assertFalse(recorded["resource_rollback_verified"])
        self.assertFalse(recorded["database_writes_performed"])
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "DB_BOUNDARY_PRIOR_ATTEMPT_RETAINED"):
            saga.reject_unverified_original_db_and_restore_resources(
                self.plan, db_scope, self.bindings, self.tasks,
                self.directory, synthetic_authority=True)

    def test_incomplete_resource_stage_refuses_database_handoff(self):
        db_scope = consolidated.bind_locked_original_database_scope(
            self.plan, *self.tasks)
        with self.assertRaises(saga.SagaBlocked):
            saga.reject_unverified_original_db_and_restore_resources(
                self.plan, db_scope, self.bindings, self.tasks,
                self.directory, synthetic_authority=True)
        self.assertFalse((self.directory / "locked-db-boundary.json").exists())

    def test_rehearsal_has_no_real_source_or_target_write_entrypoint(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "REAL_EXECUTION_NOT_WIRED"):
                saga.rehearse_bound_resources(
                    self.plan, self.bindings, self.tasks, self.directory,
                    synthetic_authority=True)
        self.assertFalse((self.directory / "resource-rehearsal.json").exists())
        with mock.patch.object(pull, "source_remote") as remote, \
             mock.patch.object(pull, "sync_external_assets") as external, \
             mock.patch.object(pull, "sync_sqlite_assets") as sql, \
             mock.patch.object(pull, "save_state") as save:
            saga.rehearse_bound_resources(
                self.plan, self.bindings, self.tasks, self.directory,
                synthetic_authority=True)
            for fn in (remote, external, sql, save):
                fn.assert_not_called()



class HistoricalResourceKindCompatibilityTests(unittest.TestCase):
    """Legacy original states omit external kind; preserve exact metadata."""

    def setUp(self):
        self.originals, self.plan = fixture()
        self.originals[0]["external_assets"][0].pop("kind")
        self.originals[2]["external_assets"][0].pop("kind")

    def test_original_target_pull_shape_binds_without_fabricating_kind(self):
        with mock.patch.object(pull, "source_remote") as ssh, \
             mock.patch.object(pull, "save_state") as persist:
            evidence = assets.bind_original_resources(
                self.plan, *self.originals)
        self.assertEqual(evidence["external_count"], 2)
        self.assertEqual(evidence["sqlite_count"], 1)
        self.assertEqual(evidence["historical_external_kind_missing_count"], 2)
        self.assertFalse(evidence["live_source_types_verified"])
        self.assertFalse(evidence["source_frozen"])
        self.assertFalse(evidence["cutover_allowed"])
        self.assertTrue(all(
            r["source_kind_declared"] is None
            for r in evidence["resources"]
            if r["kind"] == "EXTERNAL_ASSET"))
        ssh.assert_not_called()
        persist.assert_not_called()

    def test_readonly_source_type_proof_no_path_or_secret_leaks(self):
        probe_calls = []
        def probe(_source, path):
            probe_calls.append(path)
            return ("DIRECTORY" if path.endswith("/assets") else "FILE")
        with mock.patch.object(pull, "source_remote") as ssh, \
             mock.patch.object(pull, "save_state") as save_state, \
             mock.patch.object(pull, "sync_external_assets") as ext, \
             mock.patch.object(pull, "sync_sqlite_assets") as sqlite:
            proof = assets.verify_original_resource_source_types(
                self.plan, *self.originals, source_path_probe=probe)
        self.assertEqual(len(probe_calls), 3)
        self.assertEqual(proof["resource_count"], 3)
        self.assertEqual(proof["historical_external_kind_missing_count"], 2)
        self.assertTrue(proof["live_source_types_verified"])
        self.assertFalse(proof["source_file_parity_verified"])
        self.assertFalse(proof["cutover_allowed"])
        self.assertFalse(proof["source_writes_performed"])
        self.assertFalse(proof["target_writes_performed"])
        s = json.dumps(proof)
        for private in ("/home/", "store.sqlite", "catalog.txt", "password"):
            self.assertNotIn(private, s)
        for action in (ssh, save_state, ext, sqlite):
            action.assert_not_called()

    def test_external_or_sqlite_missing_symlink_and_mismatched_kind_fail(self):
        for kind, code in (
            ("MISSING", "RESOURCE_LIVE_SOURCE_TYPE_UNSAFE"),
            ("SYMLINK", "RESOURCE_LIVE_SOURCE_TYPE_UNSAFE"),
            ("DIRECTORY", "RESOURCE_LIVE_SOURCE_KIND_CHANGED"),
        ):
            with self.subTest(kind=kind):
                def probe(_source, path):
                    if "store.sqlite" in path:
                        return kind
                    return "DIRECTORY" if path.endswith("/assets") else "FILE"
                with self.assertRaisesRegex(assets.ResourceOwnerBlocked, code):
                    assets.verify_original_resource_source_types(
                        self.plan, *self.originals, source_path_probe=probe)

    def test_explicit_type_mismatch_and_unreachable_source_fail_closed(self):
        self.originals[2]["external_assets"][0]["kind"] = "DIRECTORY"
        def probe(_source, path):
            return "DIRECTORY" if path.endswith("/assets") else "FILE"
        with self.assertRaisesRegex(
            assets.ResourceOwnerBlocked, "RESOURCE_LIVE_SOURCE_KIND_CHANGED"
        ):
            assets.verify_original_resource_source_types(
                self.plan, *self.originals, source_path_probe=probe)
        with self.assertRaisesRegex(
            assets.ResourceOwnerBlocked, "RESOURCE_LIVE_SOURCE_TYPE_READBACK_UNAVAILABLE"
        ):
            assets.verify_original_resource_source_types(
                self.plan, *self.originals,
                source_path_probe=mock.Mock(side_effect=OSError("secret host")))

    def test_cli_offline_summary_redacted_and_live_ssh_opt_in_only(self):
        by_id = {s["migration_id"]: s for s in self.originals}
        with mock.patch.object(pull, "load_state",
                               side_effect=by_id.__getitem__), \
             mock.patch.object(pull, "target_identity",
                               return_value=self.originals[0]["target_server_identity"]), \
             mock.patch.object(pull.migration_chain_execution_scope,
                               "scope", return_value={"final_sync_plan": self.plan}), \
             mock.patch.object(pull, "source_path_kind") as remote:
            ids = [s["migration_id"] for s in self.originals]
            out = pull.chain_original_resource_type_readiness(*ids)
            self.assertEqual(out["resource_count"], 3)
            self.assertNotIn("resources", out)
            remote.assert_not_called()
            remote.side_effect = lambda src, path: (
                "DIRECTORY" if path.endswith("/assets") else "FILE"
            )
            live = pull.chain_original_resource_type_readiness(
                *ids, verify_live_source=True)
            self.assertTrue(live["live_source_types_verified"])
            self.assertEqual(remote.call_count, 3)
            self.assertFalse(live["cutover_allowed"])


if __name__ == "__main__":
    unittest.main()
