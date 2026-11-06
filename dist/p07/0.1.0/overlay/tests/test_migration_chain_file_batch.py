"""17-site cross-owner file batch integration: isolated filesystem only."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_chain_file_batch as batch
import migration_chain_final_saga as saga
from tests.test_migration_chain_final_saga import plan as original_plan


class SeventeenSiteFileBatchTests(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, {
            "P07_SYNTHETIC_SAGA_FIXTURE":"1"
        })
        patch.start()
        self.addCleanup(patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.plan = original_plan()
        self.expected = {}
        self.paths = []
        for i, step in enumerate(self.plan["steps"][:17]):
            paths = saga._synthetic_target_paths(self.root, step)
            paths["shadow"].mkdir(mode=0o700)
            paths["target"].mkdir(mode=0o700)
            (paths["shadow"]/"index.html").write_bytes(
                f"stage source {i}".encode())
            (paths["target"]/"index.html").write_bytes(
                f"original CP2 {i}".encode())
            (paths["target"]/"preserve.txt").write_bytes(
                f"original protected {i}".encode())
            digest = saga._synthetic_tree_hash(paths["shadow"])
            saga._save(paths["stage"], {
                "schema":"P07_CHAIN_FILE_SHADOW_V1",
                "status":"PRIVATE_STAGE_SOURCE_PARITY_NOT_PROVEN",
                "plan_sha256":self.plan["plan_sha256"],
                "site_contract_sha256":step["site_contract_sha256"],
                "original_owner":step["owner"],
                "domain":step["domain"],
                "private_shadow_only":True,
                "original_target_untouched":True,
                "cutover_allowed":False,
                "stage_readback_sha256":digest,
            })
            self.expected[i] = saga._synthetic_tree_hash(paths["target"])
            self.paths.append(paths)

    def _assert_originals(self):
        for i, paths in enumerate(self.paths):
            self.assertEqual(
                saga._synthetic_tree_hash(paths["target"]),self.expected[i])
            self.assertEqual(
                (paths["target"]/"preserve.txt").read_text(),
                f"original protected {i}")

    def test_full_17_sites_3_owners_preflight_promote_and_exact_reverse(self):
        first = batch.rehearse_seventeen_site_files(
            self.plan,self.root,synthetic_authority=True)
        self.assertEqual(first["promoted_count"],17)
        self.assertEqual(first["recovery_points_verified"],17)
        self.assertEqual(first["status"],
                         "ALL_17_SITE_FILES_PROMOTED_NOT_CUTOVER")
        self.assertFalse(first["cutover_allowed"])
        self.assertEqual(len({
            step["owner"] for step in self.plan["steps"][:17]}),3)
        for i, paths in enumerate(self.paths):
            self.assertEqual(
                (paths["target"]/"index.html").read_text(),
                f"stage source {i}")
            self.assertEqual(saga._synthetic_tree_hash(paths["snapshot"]),
                             self.expected[i])
            self.assertEqual(saga._synthetic_tree_hash(paths["held"]),
                             self.expected[i])
        report = batch.inspect_seventeen_site_files(self.plan,self.root)
        self.assertEqual(report["promoted_count"],17)
        self.assertEqual(report["uncertain_count"],0)
        restored = batch.rollback_seventeen_site_files(
            self.plan,self.root,synthetic_authority=True)
        self.assertEqual(restored["restored_count"],17)
        self._assert_originals()
        self.assertEqual(
            batch.inspect_seventeen_site_files(self.plan,self.root)
                 ["rolled_back_count"],17)
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "ROLLBACK_STATE_CHANGED"):
            batch.rollback_seventeen_site_files(
                self.plan,self.root,synthetic_authority=True)

    def test_known_injected_failure_automatically_reverses_completed_steps(self):
        outcome = batch.rehearse_seventeen_site_files(
            self.plan,self.root,synthetic_authority=True,
            fail_after_promotions=5)
        self.assertEqual(outcome["status"],
                         "KNOWN_FAILURE_FILE_TARGETS_RESTORED_NOT_CUTOVER")
        self.assertEqual(outcome["restored_count"],5)
        self.assertEqual(outcome["recovery_points_verified"],17)
        self._assert_originals()
        report = batch.inspect_seventeen_site_files(self.plan,self.root)
        self.assertEqual(report["rolled_back_count"],5)
        self.assertEqual(report["promoted_count"],0)
        self.assertEqual(report["uncertain_count"],0)
        for paths in self.paths:
            self.assertTrue(paths["snapshot"].exists())

    def test_forged_owner_and_unverified_last_stage_fail_before_any_receipt(self):
        fake=copy.deepcopy(self.plan)
        fake["steps"][16]["site_contract_sha256"]="0"*64
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "LOCKED_PLAN_DIGEST_DRIFT"):
            batch.rehearse_seventeen_site_files(
                fake,self.root,synthetic_authority=True)
        self.assertFalse((self.root/batch.FILE).exists())
        (self.paths[-1]["shadow"]/"index.html").write_text("tampered")
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "STAGE_DRIFT"):
            batch.rehearse_seventeen_site_files(
                self.plan,self.root,synthetic_authority=True)
        self.assertFalse((self.root/batch.FILE).exists())
        self._assert_originals()

    def test_crash_after_first_promotion_does_not_rollback_or_replay_unknown(self):
        actual=saga.replace_isolated_target_from_stage
        attempts=[]
        def interruption(*args,**kwargs):
            attempts.append(args[1]["domain"])
            if len(attempts)==2:
                raise OSError("synthetic uncertain target write")
            return actual(*args,**kwargs)
        with mock.patch.object(saga,"replace_isolated_target_from_stage",
                               side_effect=interruption):
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "PROMOTION_UNKNOWN_RETAIN_EVIDENCE"):
                batch.rehearse_seventeen_site_files(
                    self.plan,self.root,synthetic_authority=True)
        self.assertEqual(
            (self.paths[0]["target"]/"index.html").read_text(),
            "stage source 0")
        self.assertEqual(
            (self.paths[0]["held"]/"preserve.txt").read_text(),
            "original protected 0")
        report=batch.inspect_seventeen_site_files(self.plan,self.root)
        self.assertEqual(report["status"],"MANUAL_RECOVERY_REQUIRED")
        self.assertEqual(report["uncertain_count"],1)
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "PREVIOUS_ATTEMPT_RETAINED"):
            batch.rehearse_seventeen_site_files(
                self.plan,self.root,synthetic_authority=True)
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "ROLLBACK_STATE_CHANGED"):
            batch.rollback_seventeen_site_files(
                self.plan,self.root,synthetic_authority=True)

    def test_snapshot_failure_leaves_all_targets_untouched_and_retains_intent(self):
        actual=saga.snapshot_isolated_target
        called=[]
        def failure(*args,**kwargs):
            called.append(args[1]["domain"])
            if len(called)==7:
                raise OSError("synthetic snapshot uncertainty")
            return actual(*args,**kwargs)
        with mock.patch.object(saga,"snapshot_isolated_target",
                               side_effect=failure):
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "SNAPSHOT_UNKNOWN_RETAIN_EVIDENCE"):
                batch.rehearse_seventeen_site_files(
                    self.plan,self.root,synthetic_authority=True)
        self._assert_originals()
        report=batch.inspect_seventeen_site_files(self.plan,self.root)
        self.assertEqual(report["status"],"MANUAL_RECOVERY_REQUIRED")
        self.assertEqual(report["uncertain_count"],1)
        self.assertEqual(report["promoted_count"],0)

    def test_damaged_last_recovery_blocks_entire_17_site_reverse_preflight(self):
        batch.rehearse_seventeen_site_files(
            self.plan,self.root,synthetic_authority=True)
        last=self.paths[-1]["snapshot"]/"index.html"
        last.write_text("tampered after promotion")
        with self.assertRaises(saga.SagaBlocked):
            batch.rollback_seventeen_site_files(
                self.plan,self.root,synthetic_authority=True)
        for i,paths in enumerate(self.paths):
            self.assertEqual(
                (paths["target"]/"index.html").read_text(),
                f"stage source {i}")
        self.assertEqual(batch.inspect_seventeen_site_files(
            self.plan,self.root)["rolled_back_count"],0)

    def test_without_fixture_gate_no_real_server_operation(self):
        with mock.patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(
                saga.SagaBlocked,"REAL_EXECUTION_NOT_WIRED"):
                batch.rehearse_seventeen_site_files(
                    self.plan,self.root,synthetic_authority=True)
        self.assertFalse((self.root/batch.FILE).exists())
        self._assert_originals()


    def _prepare_three_owner_resources(self):
        import sqlite3
        import migration_chain_asset_audit as assets
        import migration_chain_consolidation as consolidated
        from tests.test_migration_chain_resource_bindings import fixture
        tasks, resource_plan = fixture()
        self.assertEqual(self.plan["plan_sha256"],
                         resource_plan["plan_sha256"])
        bindings = assets.bind_original_resources(
            resource_plan, *tasks)
        for item in bindings["resources"]:
            paths = saga._resource_sandbox_paths(self.root, item)
            paths["base"].mkdir(mode=0o700)
            paths["source"].mkdir(mode=0o700)
            paths["target"].mkdir(mode=0o700)
            if item["kind"] == "SQLITE":
                for name, contents in (("source","new"),
                                       ("target","original")):
                    with sqlite3.connect(
                        str(paths[name] / "data.sqlite")) as conn:
                        conn.execute("CREATE TABLE records (name TEXT)")
                        conn.execute("INSERT INTO records VALUES (?)",
                                     (contents,))
            else:
                (paths["source"] / "entry.txt").write_text("new")
                (paths["target"] / "entry.txt").write_text("original")
                (paths["target"] / "preserve.txt").write_text("keep")
        original_resources = [
            saga._resource_fingerprint(
                item["kind"],
                saga._resource_sandbox_paths(self.root,item)["target"]
            ) for item in bindings["resources"]
        ]
        db_scope = consolidated.bind_locked_original_database_scope(
            resource_plan, *tasks)
        return tasks, bindings, db_scope, original_resources

    def test_entire_locked_three_database_boundary_restores_resources_then_17_files(self):
        tasks, bindings, db_scope, before = \
            self._prepare_three_owner_resources()
        import migration_final_db_batch as db_batch
        import migration_final_db_shadow as db_shadow
        import server_migration_pull as pull
        site = batch.rehearse_seventeen_site_files(
            self.plan, self.root, synthetic_authority=True)
        self.assertEqual(site["promoted_count"],17)
        resources=saga.rehearse_bound_resources(
            self.plan, bindings, tasks, self.root,
            synthetic_authority=True)
        self.assertEqual(resources["resource_count"],3)
        with mock.patch.object(db_batch,"switch_verified_shadow_batch") as switch, \
             mock.patch.object(db_shadow,"activate_verified_shadow") as activate, \
             mock.patch.object(pull,"source_remote") as remote, \
             mock.patch.object(pull,"sync_site_databases") as db_import:
            restored=batch.rehearse_locked_database_full_reverse(
                self.plan, db_scope, bindings, tasks, self.root,
                synthetic_authority=True)
        for no_db_write in (switch,activate,remote,db_import):
            no_db_write.assert_not_called()
        self.assertEqual(restored["status"],
            "ALL_RESOURCES_AND_17_FILES_RESTORED_NOT_CUTOVER")
        self.assertEqual(restored["restored_file_site_count"],17)
        self.assertEqual(restored["restored_external_sqlite_count"],3)
        self.assertFalse(restored["cutover_allowed"])
        self._assert_originals()
        for i,item in enumerate(bindings["resources"]):
            self.assertEqual(
                saga._resource_fingerprint(
                    item["kind"],
                    saga._resource_sandbox_paths(
                        self.root,item)["target"]),
                before[i])
        receipt = json.loads(
            (self.root/"full-cross-owner-rollback.json").read_text())
        self.assertTrue(receipt["resource_rollback_verified"])
        self.assertTrue(receipt["file_rollback_verified"])
        self.assertFalse(receipt["database_writes_performed"])
        self.assertFalse(receipt["www3_reconnected"])

    def test_missing_resource_recovery_refuses_all_reversals_before_first_write(self):
        tasks, bindings, db_scope, _ = \
            self._prepare_three_owner_resources()
        batch.rehearse_seventeen_site_files(
            self.plan,self.root,synthetic_authority=True)
        saga.rehearse_bound_resources(
            self.plan,bindings,tasks,self.root,synthetic_authority=True)
        row=bindings["resources"][-1]
        location=saga._resource_sandbox_paths(self.root,row)
        if row["kind"] == "SQLITE":
            # Change physical SQLite copy without updating the receipt.
            with (location["recovery"]/"data.sqlite").open("ab") as dest:
                dest.write(b"tampered")
        else:
            (location["recovery"]/"intruder.txt").write_text("tampered")
        with self.assertRaises(saga.SagaBlocked):
            batch.rehearse_locked_database_full_reverse(
                self.plan,db_scope,bindings,tasks,self.root,
                synthetic_authority=True)
        self.assertFalse(
            (self.root/"full-cross-owner-rollback.json").exists())
        self.assertEqual(
            batch.inspect_seventeen_site_files(self.plan,self.root)
                ["promoted_count"],17)
        for i,paths in enumerate(self.paths):
            self.assertEqual(
                (paths["target"]/"index.html").read_text(),
                f"stage source {i}")


if __name__ == "__main__":
    unittest.main()
