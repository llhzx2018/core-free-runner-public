"""17-site synthetic final-sync crash/rollback gate. No server writes."""
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
import migration_chain_execution_scope as owners
import migration_chain_final_saga as saga
import server_migration as legacy
from tests.test_migration_chain_execution_scope import three_partial_tasks


def plan():
    parent, child, tail = three_partial_tasks()
    with tempfile.TemporaryDirectory() as tmp:
        scope = owners.scope(parent, child, tail, root=Path(tmp),
                             private_owner=os.geteuid())
    return saga.operation_plan(scope)


class CrossOwnerSagaTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ,
                                   {"P07_SYNTHETIC_SAGA_FIXTURE": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.directory.chmod(0o700)
        self.plan = plan()

    def _begin(self):
        return saga.start_synthetic_rehearsal(
            self.plan, self.directory, synthetic_authority=True)

    def test_14_of_17_distinct_owners_with_all_final_phases_and_hard_gate(self):
        p = self.plan
        self.assertEqual(p["site_count"], 17)
        self.assertEqual(p["step_count"], 21)
        self.assertEqual(len(p["pending_domains"]), 3)
        self.assertEqual(p["status"],
                         "LOCKED_AWAITING_ORIGINAL_RECOVERY_AND_FINAL_PROOF")
        self.assertFalse(p["cutover_allowed"])
        self.assertFalse(p["source_freeze_allowed"])
        self.assertFalse(p["recovery_snapshots_verified"])
        self.assertEqual(p["steps"][-4:],
                         [{"phase": phase, "domain": "", "owner": "", "index": -1}
                          for phase in saga.PHASES[1:]])
        self.assertEqual(len(set((row["domain"], row["owner"])
                                 for row in p["steps"][:17])), 17)

    def test_durable_synthetic_run_executes_all_steps_once_no_cutover(self):
        self._begin()
        applied = []
        result = saga.execute_synthetic_rehearsal(
            self.plan, self.directory,
            apply=lambda row: applied.append((row["phase"], row["domain"])),
            compensate=lambda _: self.fail("rollback must not run"))
        self.assertEqual(result["step_count"], 21)
        self.assertFalse(result["cutover_allowed"])
        self.assertEqual(len(applied), 21)
        self.assertEqual(saga.inspect_recovery(self.plan, self.directory)
                         ["completed_count"], 21)
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "CHAIN_SAGA_PRIOR_INTENT_RECOVERY_REQUIRED"):
            saga.execute_synthetic_rehearsal(
                self.plan, self.directory,
                apply=lambda _: self.fail("must not replay"),
                compensate=lambda _: self.fail("must not compensate"))

    def test_failed_inflight_file_step_is_rolled_back_in_reverse_order(self):
        self._begin()
        modified = set()
        order = []

        def apply(row):
            key = (row["phase"], row["domain"])
            order.append(("apply", key))
            modified.add(key)
            if len([x for x in order if x[0] == "apply"]) == 4:
                raise RuntimeError("synthetic interruption after a write")

        def rollback(row):
            key = (row["phase"], row["domain"])
            order.append(("rollback", key))
            modified.discard(key)
            return True

        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "CHAIN_SAGA_REHEARSAL_FAILED_ROLLED_BACK"):
            saga.execute_synthetic_rehearsal(
                self.plan, self.directory, apply=apply, compensate=rollback)
        self.assertEqual(modified, set())
        applied = [key for verb, key in order if verb == "apply"]
        restored = [key for verb, key in order if verb == "rollback"]
        self.assertEqual(restored, list(reversed(applied)))
        result = saga.inspect_recovery(self.plan, self.directory)
        self.assertEqual(result["status"], "REHEARSAL_ROLLED_BACK")
        self.assertEqual(result["rolled_back_count"], 4)
        self.assertEqual(result["uncertain_count"], 0)

    def test_incomplete_rollback_retains_receipt_without_retry(self):
        self._begin()
        called = []

        def apply(row):
            called.append(row["domain"])
            raise RuntimeError("synthetic failure")

        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "CHAIN_SAGA_REHEARSAL_PARTIAL_RECOVERY_REQUIRED"):
            saga.execute_synthetic_rehearsal(
                self.plan, self.directory, apply=apply,
                compensate=lambda _: False)
        report = saga.inspect_recovery(self.plan, self.directory)
        self.assertEqual(report["status"], "MANUAL_RECOVERY_REQUIRED")
        self.assertEqual(report["uncertain_count"], 1)
        self.assertEqual(len(called), 1)
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "CHAIN_SAGA_PRIOR_INTENT_RECOVERY_REQUIRED"):
            saga.execute_synthetic_rehearsal(
                self.plan, self.directory,
                apply=lambda _: self.fail("unproven write replay"),
                compensate=lambda _: True)

    def test_crashed_after_intent_before_completion_is_not_replayed(self):
        self._begin()
        path = self.directory / "journal.json"
        before = saga._read_receipt(path)
        before["steps"][0]["status"] = "INTENT_RESERVED"
        saga._save(path, before)
        report = saga.inspect_recovery(self.plan, self.directory)
        self.assertEqual(report["status"], "MANUAL_RECOVERY_REQUIRED")
        self.assertEqual(report["uncertain_count"], 1)
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "CHAIN_SAGA_PRIOR_INTENT_RECOVERY_REQUIRED"):
            saga.execute_synthetic_rehearsal(
                self.plan, self.directory,
                apply=lambda _: self.fail("crash must block retries"),
                compensate=lambda _: self.fail("no blind rollback"))

    def test_duplicate_attempt_and_missing_fixture_gate_fail_closed(self):
        self._begin()
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "CHAIN_SAGA_EXISTING_ATTEMPT_RETAINED"):
            self._begin()
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED"):
                saga.start_synthetic_rehearsal(
                    self.plan, self.directory, synthetic_authority=True)
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED"):
                saga.execute_synthetic_rehearsal(
                    self.plan, self.directory, apply=lambda _: None,
                    compensate=lambda _: True)

    def test_rehearsal_refuses_persistent_or_unrecognized_root(self):
        # Restrict synthetic callbacks to a real ephemeral sandbox even when
        # an environment variable is accidentally set on a live machine.
        with mock.patch.object(saga.tempfile, "gettempdir",
                               return_value="/var/lib/vf-server-ops"):
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "CHAIN_SAGA_REAL_FILESYSTEM_ROOT_DENIED"):
                saga.start_synthetic_rehearsal(
                    self.plan, self.directory, synthetic_authority=True)
        self.assertFalse((self.directory / "journal.json").exists())

    def test_tampered_or_symlinked_receipt_and_plan_block_before_callback(self):
        for kind in ("hash", "owner", "status", "symlink", "mode"):
            with self.subTest(kind=kind):
                with tempfile.TemporaryDirectory() as tmp:
                    folder = Path(tmp)
                    folder.chmod(0o700)
                    saga.start_synthetic_rehearsal(
                        self.plan, folder, synthetic_authority=True)
                    path = folder / "journal.json"
                    if kind == "symlink":
                        original = folder / "original.json"
                        path.rename(original)
                        path.symlink_to(original)
                    elif kind == "mode":
                        path.chmod(0o644)
                    else:
                        doc = json.loads(path.read_text())
                        if kind == "hash":
                            doc["plan_sha256"] = "0" * 64
                        elif kind == "owner":
                            doc["steps"][0]["owner"] = "pull-fake"
                        else:
                            doc["status"] = "PRODUCTION_PASS"
                        legacy.atomic_private_json(path, doc)
                    with self.assertRaises(saga.SagaBlocked):
                        saga.execute_synthetic_rehearsal(
                            self.plan, folder,
                            apply=lambda _: self.fail("no callback"),
                            compensate=lambda _: self.fail("no rollback"))

    def test_executable_schema_cannot_be_inferred_from_locked_plan(self):
        mutated = copy.deepcopy(self.plan)
        mutated["cutover_allowed"] = True
        with self.assertRaises(saga.SagaBlocked):
            saga.start_synthetic_rehearsal(
                mutated, self.directory, synthetic_authority=True)
        mutated = copy.deepcopy(self.plan)
        mutated["source_freeze_allowed"] = True
        with self.assertRaises(saga.SagaBlocked):
            saga.start_synthetic_rehearsal(
                mutated, self.directory, synthetic_authority=True)

    def test_unverified_or_duplicate_site_owner_blocks_journal_creation(self):
        parent, child, tail = three_partial_tasks()
        with tempfile.TemporaryDirectory() as tmp:
            report = owners.scope(parent, child, tail, root=Path(tmp),
                                  private_owner=os.geteuid())
        for kind in ("duplicate", "missing", "owner"):
            forged = copy.deepcopy(report)
            if kind == "duplicate":
                forged["sites"][1]["domain"] = forged["sites"][0]["domain"]
            elif kind == "missing":
                forged["sites"].pop()
            else:
                forged["sites"][0]["owner_migration_id"] = "invalid"
            with self.subTest(kind=kind), self.assertRaises(saga.SagaBlocked):
                saga.operation_plan(forged)


    def test_real_pull_wired_to_private_shadow_only_without_delete(self):
        import server_migration_pull as pull
        parent, _, _ = three_partial_tasks()
        step = self.plan["steps"][0]
        transfers = []

        def fake_pull(source, remote, target, **kw):
            transfers.append((remote, target, kw))
            (target / "index.html").write_text("synthetic")
        with mock.patch.object(pull, "pull_path", side_effect=fake_pull):
            outcome = saga.stage_isolated_site_files(
                self.plan, step, parent, self.directory,
                synthetic_authority=True)
        self.assertEqual(outcome["status"],
                         "PRIVATE_STAGE_SOURCE_PARITY_NOT_PROVEN")
        self.assertFalse(outcome["cutover_allowed"])
        self.assertTrue(outcome["original_target_untouched"])
        self.assertEqual(len(transfers), 1)
        self.assertIs(transfers[0][2]["delete"], False)
        self.assertTrue(str(transfers[0][1]).startswith(str(self.directory)))
        self.assertNotEqual(str(transfers[0][1]),
                            parent["sites"][0]["site_root"])
        with mock.patch.object(pull, "pull_path") as blocked:
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "PREVIOUS_FILE_INTENT_RETAINED"):
                saga.stage_isolated_site_files(
                    self.plan, step, parent, self.directory,
                    synthetic_authority=True)
            blocked.assert_not_called()

    def test_source_contract_and_identity_drift_block_before_any_pull(self):
        import server_migration_pull as pull
        parent, _, _ = three_partial_tasks()
        step = self.plan["steps"][0]
        for case in ("root", "source", "target", "owner"):
            broken = copy.deepcopy(parent)
            if case == "root":
                broken["sites"][0]["site_root"] += "-changed"
            elif case == "source":
                broken["source"]["host"] = "203.0.113.34"
            elif case == "target":
                broken["target_server_identity"] = "sha256:other"
            else:
                broken["migration_id"] = "pull-other"
            with self.subTest(case=case), mock.patch.object(
                pull, "pull_path"
            ) as transfer:
                with self.assertRaises(saga.SagaBlocked):
                    saga.stage_isolated_site_files(
                        self.plan, step, broken, self.directory,
                        synthetic_authority=True)
                transfer.assert_not_called()
        self.assertEqual(list(self.directory.glob("site-*.json")), [])

    def test_partial_file_shadow_retained_and_never_retried(self):
        import server_migration_pull as pull
        parent, _, _ = three_partial_tasks()
        step = self.plan["steps"][0]
        with mock.patch.object(pull, "pull_path", side_effect=OSError("fake")):
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "SHADOW_RECOVERY_REQUIRED"):
                saga.stage_isolated_site_files(
                    self.plan, step, parent, self.directory,
                    synthetic_authority=True)
        receipts = list(self.directory.glob("site-*.json"))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(json.loads(receipts[0].read_text())["status"],
                         "RECOVERY_REQUIRED_RETAIN_SHADOW")
        with mock.patch.object(pull, "pull_path") as transfer:
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "PREVIOUS_FILE_INTENT_RETAINED"):
                saga.stage_isolated_site_files(
                    self.plan, step, parent, self.directory,
                    synthetic_authority=True)
            transfer.assert_not_called()

    def test_original_site_contract_digest_cannot_be_forged(self):
        parent, child, tail = three_partial_tasks()
        with tempfile.TemporaryDirectory() as tmp:
            report = owners.scope(parent, child, tail, root=Path(tmp),
                                  private_owner=os.geteuid())
        report["sites"][0]["site_contract_sha256"] = "0" * 64
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "CHAIN_SAGA_SCOPE_DIGEST_DRIFT"):
            saga.operation_plan(report)


    def test_all_21_step_plan_rehash_refuses_tampered_steps_before_write(self):
        for kind in ("phase", "contract", "blockers", "flag"):
            forged = copy.deepcopy(self.plan)
            if kind == "phase":
                forged["steps"][0]["phase"] = "DATABASE_SHADOWS"
            elif kind == "contract":
                forged["steps"][0]["site_contract_sha256"] = "0" * 64
            elif kind == "blockers":
                forged["blockers"].append("INVENTED")
            else:
                forged["recovery_snapshots_verified"] = True
            with self.subTest(kind=kind), self.assertRaises(saga.SagaBlocked):
                saga.start_synthetic_rehearsal(
                    forged, self.directory, synthetic_authority=True)
        self.assertFalse((self.directory / "journal.json").exists())

    def test_reverse_compensation_abandons_private_stage_without_deletion(self):
        import server_migration_pull as pull
        parent, _, _ = three_partial_tasks()
        step = self.plan["steps"][0]

        def fake_copy(source, remote, destination, **options):
            (destination / "index.html").write_text("fixture")
        with mock.patch.object(pull, "pull_path", side_effect=fake_copy):
            saga.stage_isolated_site_files(
                self.plan, step, parent, self.directory,
                synthetic_authority=True)
        self.assertIs(saga.abandon_isolated_site_file_shadow(
            self.plan, step, self.directory, synthetic_authority=True), True)
        self.assertIs(saga.abandon_isolated_site_file_shadow(
            self.plan, step, self.directory, synthetic_authority=True), False)
        shadow = next(self.directory.glob("site-*-shadow"))
        self.assertEqual((shadow / "index.html").read_text(), "fixture")
        record = json.loads(next(self.directory.glob("site-*.json")).read_text())
        self.assertEqual(record["status"], "ABANDONED_RETAINED_NOT_PROMOTED")

    def test_unknown_write_receipt_must_not_claim_rollback_success(self):
        import server_migration_pull as pull
        parent, _, _ = three_partial_tasks()
        step = self.plan["steps"][0]
        with mock.patch.object(pull, "pull_path", side_effect=OSError("crash")):
            with self.assertRaises(saga.SagaBlocked):
                saga.stage_isolated_site_files(
                    self.plan, step, parent, self.directory,
                    synthetic_authority=True)
        self.assertIs(saga.abandon_isolated_site_file_shadow(
            self.plan, step, self.directory, synthetic_authority=True), False)
        record = json.loads(next(self.directory.glob("site-*.json")).read_text())
        self.assertEqual(record["status"], "RECOVERY_REQUIRED_RETAIN_SHADOW")


    def _stage_with_original_target(self):
        import server_migration_pull as pull
        parent, _, _ = three_partial_tasks()
        step = self.plan["steps"][0]
        paths = saga._synthetic_target_paths(self.directory, step)
        paths["target"].mkdir(mode=0o700)
        (paths["target"] / "index.html").write_text("original-target")
        (paths["target"] / "preserve.txt").write_text("preserve-existing")
        def fake_copy(source, remote, destination, **kwargs):
            self.assertFalse(kwargs["delete"])
            (destination / "index.html").write_text("new-source")
        with mock.patch.object(pull, "pull_path", side_effect=fake_copy):
            saga.stage_isolated_site_files(
                self.plan, step, parent, self.directory,
                synthetic_authority=True)
        return step, paths

    def test_synthetic_target_recovery_replace_and_exact_reverse_rollback(self):
        step, paths = self._stage_with_original_target()
        original = saga._synthetic_tree_hash(paths["target"])
        receipt = saga.snapshot_isolated_target(
            self.plan, step, self.directory, synthetic_authority=True)
        self.assertEqual(receipt["status"], "RECOVERY_POINT_VERIFIED")
        self.assertTrue(receipt["target_recovery_verified"])
        self.assertEqual(saga._synthetic_tree_hash(paths["snapshot"]), original)
        self.assertEqual((paths["target"] / "index.html").read_text(),
                         "original-target")
        switched = saga.replace_isolated_target_from_stage(
            self.plan, step, self.directory, synthetic_authority=True)
        self.assertEqual(switched["status"], "PROMOTED_NOT_CUTOVER")
        self.assertEqual((paths["target"] / "index.html").read_text(),
                         "new-source")
        self.assertFalse((paths["target"] / "preserve.txt").exists())
        self.assertEqual((paths["held"] / "preserve.txt").read_text(),
                         "preserve-existing")
        restored = saga.rollback_isolated_target_replacement(
            self.plan, step, self.directory, synthetic_authority=True)
        self.assertEqual(restored["status"], "ROLLED_BACK_VERIFIED")
        self.assertFalse(restored["cutover_allowed"])
        self.assertEqual(saga._synthetic_tree_hash(paths["target"]), original)
        self.assertEqual((paths["target"] / "index.html").read_text(),
                         "original-target")
        self.assertEqual((paths["target"] / "preserve.txt").read_text(),
                         "preserve-existing")
        self.assertEqual((paths["failed"] / "index.html").read_text(),
                         "new-source")
        self.assertEqual(saga._synthetic_tree_hash(paths["snapshot"]), original)
        with self.assertRaisesRegex(saga.SagaBlocked, "UNCERTAIN_OR_ALREADY_DONE"):
            saga.rollback_isolated_target_replacement(
                self.plan, step, self.directory, synthetic_authority=True)

    def test_original_target_drift_blocks_promotion_without_write(self):
        step, paths = self._stage_with_original_target()
        saga.snapshot_isolated_target(
            self.plan, step, self.directory, synthetic_authority=True)
        (paths["target"] / "preserve.txt").write_text("concurrently-changed")
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "TARGET_DRIFT_BEFORE_OVERWRITE"):
            saga.replace_isolated_target_from_stage(
                self.plan, step, self.directory, synthetic_authority=True)
        self.assertEqual((paths["target"] / "preserve.txt").read_text(),
                         "concurrently-changed")
        self.assertFalse(paths["held"].exists())
        self.assertFalse(paths["next"].exists())

    def test_source_stage_tamper_blocks_recovery_point_creation(self):
        step, paths = self._stage_with_original_target()
        (paths["shadow"] / "index.html").write_text("changed-after-staging")
        with self.assertRaisesRegex(saga.SagaBlocked, "CHAIN_SAGA_STAGE_DRIFT"):
            saga.snapshot_isolated_target(
                self.plan, step, self.directory, synthetic_authority=True)
        self.assertFalse(paths["snapshot"].exists())
        self.assertFalse(paths["journal"].exists())

    def test_symlink_in_target_blocks_snapshot_before_receipt(self):
        step, paths = self._stage_with_original_target()
        (paths["target"] / "link").symlink_to(paths["shadow"] / "index.html")
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "CHAIN_SAGA_TREE_SYMLINK_OR_SPECIAL"):
            saga.snapshot_isolated_target(
                self.plan, step, self.directory, synthetic_authority=True)
        self.assertFalse(paths["journal"].exists())
        self.assertFalse(paths["snapshot"].exists())

    def test_hardlink_target_blocks_snapshot_before_receipt(self):
        step, paths = self._stage_with_original_target()
        os.link(paths["target"] / "index.html", paths["target"] / "duplicate")
        with self.assertRaisesRegex(saga.SagaBlocked, "HARDLINK_UNSAFE"):
            saga.snapshot_isolated_target(
                self.plan, step, self.directory, synthetic_authority=True)
        self.assertFalse(paths["journal"].exists())

    def test_snapshot_failure_retains_intent_and_never_retries(self):
        step, paths = self._stage_with_original_target()
        with mock.patch.object(saga.shutil, "copytree",
                               side_effect=OSError("synthetic failure")):
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "RECOVERY_COPY_UNKNOWN"):
                saga.snapshot_isolated_target(
                    self.plan, step, self.directory, synthetic_authority=True)
        receipt = json.loads(paths["journal"].read_text())
        self.assertEqual(receipt["status"], "RECOVERY_UNKNOWN_RETAIN_EVIDENCE")
        self.assertFalse(receipt["target_recovery_verified"])
        self.assertEqual((paths["target"] / "index.html").read_text(),
                         "original-target")
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "RECOVERY_ALREADY_ATTEMPTED"):
            saga.snapshot_isolated_target(
                self.plan, step, self.directory, synthetic_authority=True)

    def test_crash_between_two_renames_keeps_unknown_receipt(self):
        step, paths = self._stage_with_original_target()
        saga.snapshot_isolated_target(
            self.plan, step, self.directory, synthetic_authority=True)
        real_rename = saga.os.rename
        calls = []
        def fail_second(src, dst):
            calls.append((src, dst))
            if len(calls) == 2:
                raise OSError("synthetic crash gap")
            return real_rename(src, dst)
        with mock.patch.object(saga.os, "rename", side_effect=fail_second):
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "PROMOTION_STATE_UNKNOWN"):
                saga.replace_isolated_target_from_stage(
                    self.plan, step, self.directory, synthetic_authority=True)
        self.assertEqual(len(calls), 2)
        self.assertFalse(paths["target"].exists())
        self.assertEqual((paths["held"] / "preserve.txt").read_text(),
                         "preserve-existing")
        self.assertEqual(json.loads(paths["journal"].read_text())["status"],
                         "PROMOTION_UNKNOWN_MANUAL_RECONCILIATION")
        with self.assertRaises(saga.SagaBlocked):
            saga.rollback_isolated_target_replacement(
                self.plan, step, self.directory, synthetic_authority=True)
        self.assertTrue(paths["held"].exists())

    def test_post_promotion_concurrent_edit_blocks_rollback(self):
        step, paths = self._stage_with_original_target()
        saga.snapshot_isolated_target(
            self.plan, step, self.directory, synthetic_authority=True)
        saga.replace_isolated_target_from_stage(
            self.plan, step, self.directory, synthetic_authority=True)
        (paths["target"] / "index.html").write_text("changed-by-other-user")
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "ROLLBACK_POST_WRITE_DRIFT"):
            saga.rollback_isolated_target_replacement(
                self.plan, step, self.directory, synthetic_authority=True)
        self.assertEqual((paths["target"] / "index.html").read_text(),
                         "changed-by-other-user")
        self.assertTrue(paths["held"].exists())
        self.assertEqual(json.loads(paths["journal"].read_text())["status"],
                         "PROMOTED_NOT_CUTOVER")

    def test_unknown_rollback_does_not_claim_success_or_replay(self):
        step, paths = self._stage_with_original_target()
        saga.snapshot_isolated_target(
            self.plan, step, self.directory, synthetic_authority=True)
        saga.replace_isolated_target_from_stage(
            self.plan, step, self.directory, synthetic_authority=True)
        with mock.patch.object(saga.os, "rename",
                               side_effect=OSError("injected rollback failure")):
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "ROLLBACK_STATE_UNKNOWN"):
                saga.rollback_isolated_target_replacement(
                    self.plan, step, self.directory, synthetic_authority=True)
        self.assertEqual(json.loads(paths["journal"].read_text())["status"],
                         "ROLLBACK_UNKNOWN_MANUAL_RECONCILIATION")
        with self.assertRaisesRegex(saga.SagaBlocked,
                                    "UNCERTAIN_OR_ALREADY_DONE"):
            saga.rollback_isolated_target_replacement(
                self.plan, step, self.directory, synthetic_authority=True)
        self.assertEqual((paths["target"] / "index.html").read_text(), "new-source")
        self.assertTrue(paths["held"].exists())

    def test_real_source_cannot_be_called_by_synthetic_shadow(self):
        import server_migration_pull as pull
        parent, _, _ = three_partial_tasks()
        parent["source"]["host"] = "45.76.171.57"
        parent["source"]["ip"] = "45.76.171.57"
        with mock.patch.object(pull, "pull_path") as transfer:
            with self.assertRaisesRegex(saga.SagaBlocked,
                                        "SYNTHETIC_REMOTE_REQUIRED"):
                saga.stage_isolated_site_files(
                    self.plan, self.plan["steps"][0], parent, self.directory,
                    synthetic_authority=True)
            transfer.assert_not_called()


class ThreeOriginalDatabaseGateTests(unittest.TestCase):
    """The failed parent/child/tail are NOT a synthetic CUTOVER_RUNNING task."""

    def setUp(self):
        import migration_chain_consolidation as con
        self.con = con
        self.originals = three_partial_tasks()
        with tempfile.TemporaryDirectory() as tmp:
            self.report = owners.scope(
                *self.originals, root=Path(tmp),
                private_owner=os.geteuid())
        self.plan = saga.operation_plan(self.report)

    def _bind(self, originals=None, plan=None):
        return self.con.bind_locked_original_database_scope(
            self.plan if plan is None else plan,
            *(self.originals if originals is None else originals))

    def test_three_db_origins_bound_to_real_tasks_with_no_data_writes(self):
        import migration_final_db_batch as batch
        import migration_final_db_shadow as shadow
        import server_migration_pull as pull
        snapshot = copy.deepcopy(self.originals)
        with mock.patch.object(batch, "switch_verified_shadow_batch") as switch, \
             mock.patch.object(shadow, "_read_verified_shadow") as shadow_read, \
             mock.patch.object(pull, "sync_site_databases") as import_db, \
             mock.patch.object(pull, "source_remote") as source_ssh, \
             mock.patch.object(pull, "save_state") as save:
            gate = self._bind()
        for handler in (switch, shadow_read, import_db, source_ssh, save):
            handler.assert_not_called()
        self.assertEqual(self.originals, snapshot)
        self.assertEqual(gate["site_count"], 17)
        self.assertEqual(gate["database_count"], 3)
        self.assertEqual(gate["original_task_count"], 3)
        self.assertEqual({
            row["domain"]: row["original_owner"]
            for row in gate["databases"]}, {
            "ilovem3u8.kewaro.com": self.originals[0]["migration_id"],
            "unzip.kewaro.com": self.originals[1]["migration_id"],
            "www3.m3u8.one": self.originals[2]["migration_id"],
        })
        self.assertEqual(gate["pending_database_domains"], [
            "ilovem3u8.kewaro.com", "unzip.kewaro.com", "www3.m3u8.one"])
        self.assertFalse(gate["cutover_allowed"])
        self.assertFalse(gate["cross_task_batch_execution_allowed"])
        self.assertFalse(gate["database_writes_performed"])
        self.assertEqual(len(gate["scope_sha256"]), 64)
        exported = json.dumps(gate)
        for raw in ("db7", "db14", "db16", "origpass",
                    "shadow_password", "/home/"):
            self.assertNotIn(raw, exported)

    def test_preadopted_or_forged_site_contract_cannot_upgrade_readiness(self):
        for case in ("db_name", "site_stage", "site_root", "source",
                     "target", "source_frozen", "activated", "status",
                     "fake_owner", "add_database", "tail_link",
                     "tail_cutover", "child_guard", "false_prepared"):
            with self.subTest(case=case):
                originals = copy.deepcopy(self.originals)
                if case == "db_name":
                    originals[1]["sites"][6]["mysql_databases"] = ["surprise"]
                elif case == "site_stage":
                    originals[1]["sites"][6]["stage_status"] = "PULLED_STAGED"
                elif case == "site_root":
                    originals[0]["sites"][7]["site_root"] += "-new"
                elif case == "source":
                    originals[2]["source"]["ip"] = "203.0.113.25"
                elif case == "target":
                    originals[2]["target_server_identity"] = "sha256:other"
                elif case == "source_frozen":
                    originals[0]["source_runtime_frozen"] = True
                elif case == "activated":
                    originals[2]["target_runtime_activated"] = True
                elif case == "status":
                    originals[0]["status"] = "CUTOVER_RUNNING"
                elif case == "fake_owner":
                    originals[1]["migration_id"] = originals[2]["migration_id"]
                elif case == "tail_link":
                    originals[2]["partial_parent_migration_id"] = "pull-foreign"
                elif case == "tail_cutover":
                    originals[2]["cutover_prohibited"] = False
                elif case == "child_guard":
                    originals[1]["last_sql_guard_failure"]["reason"] = "UNKNOWN"
                elif case == "false_prepared":
                    originals[2]["status"] = "PREPARED"
                else:
                    originals[2]["sites"][1]["mysql_databases"].append("extra")
                with self.assertRaises(self.con.ConsolidationBlocked):
                    self._bind(originals=originals)

    def test_locked_plan_forgery_and_missing_db_are_hard_failures(self):
        for case in ("sha", "phase", "cutover", "missing_db"):
            with self.subTest(case=case):
                plan = copy.deepcopy(self.plan)
                originals = copy.deepcopy(self.originals)
                if case == "sha":
                    plan["plan_sha256"] = "0" * 64
                elif case == "phase":
                    plan["steps"][17]["phase"] = "PREPARED"
                elif case == "cutover":
                    plan["cutover_allowed"] = True
                else:
                    originals[2]["sites"][1]["mysql_databases"] = []
                with self.assertRaises(self.con.ConsolidationBlocked):
                    self._bind(plan=plan, originals=originals)

    def test_identical_db_name_in_two_independent_tasks_is_collision(self):
        originals = copy.deepcopy(self.originals)
        # A forged plan cannot hide the original database identity conflict.
        originals[2]["sites"][1]["mysql_databases"] = ["db7"]
        with self.assertRaises(self.con.ConsolidationBlocked):
            self._bind(originals=originals)



class ThreeOwnerPrivateWarmFileStageTests(unittest.TestCase):
    """Real pull primitive, isolated no-overwrite CP2 storage, mocked transport."""

    def setUp(self):
        import migration_chain_private_file_stage as warm
        self.warm = warm
        self.originals = tuple(three_partial_tasks())
        self.plan = plan()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / self.plan["steps"][0]["owner"]
        self.state.mkdir(mode=0o700)
        self.target = self.originals[0]["target_server_identity"]
        self.scope = mock.patch.object(legacy, "STATE_ROOT", self.root)
        self.scope.start()
        self.addCleanup(self.scope.stop)

    def _stage(self, **kw):
        return self.warm.stage_private_seventeen_site_warm_copy(
            self.plan, self.originals,
            root=self.state, actual_target_identity=self.target,
            authorize_private_copy=True, **kw)

    def test_real_pull_wired_for_all_17_and_no_target_mutation(self):
        calls = []
        def fake_pull(source, remote, folder, **kwargs):
            calls.append((source["host"], remote, kwargs))
            (folder / "index.php").write_text("synthetic wordpress", encoding="utf-8")
        import server_migration_pull as pull
        with mock.patch.object(pull, "pull_path",
                               side_effect=fake_pull) as copy_source, \
             mock.patch.object(pull, "freeze_old_server") as freeze, \
             mock.patch.object(pull, "save_state") as state_write, \
             mock.patch.object(pull.cloudpanel, "import_database") as sql_write:
            result = self._stage()
        self.assertEqual(result["status"], "ALL_17_PRIVATE_WARM_COPIES_NOT_FINAL")
        self.assertEqual(len(calls), 17)
        self.assertEqual(copy_source.call_count, 17)
        self.assertTrue(all(c[1].endswith("/") for c in calls))
        self.assertTrue(all(c[2]["delete"] is False for c in calls))
        self.assertTrue(all(c[0].endswith(".example.test") for c in calls))
        self.assertFalse(result["source_target_final_parity"])
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["existing_target_modified"])
        freeze.assert_not_called()
        sql_write.assert_not_called()
        state_write.assert_not_called()
        verified = self.warm.verify_private_seventeen_site_warm_copy(
            self.plan, root=self.state)
        self.assertEqual(verified["site_count"], 17)
        self.assertEqual(verified["source_final_snapshot"], "NOT_VERIFIED")
        with mock.patch.object(pull, "pull_path") as repeat:
            with self.assertRaisesRegex(
                self.warm.WarmStageBlocked, "PRIOR_ATTEMPT_RETAINED"
            ):
                self._stage()
            repeat.assert_not_called()

    def test_failure_at_site_four_retains_intent_and_prevents_replay(self):
        import server_migration_pull as pull
        visits = []
        def interrupted(_source, _remote, folder, **_kw):
            visits.append(folder)
            (folder / "index.php").write_text("copy", encoding="utf-8")
            if len(visits) == 4:
                raise RuntimeError("private rsync failure")
        with mock.patch.object(pull, "pull_path", side_effect=interrupted):
            with self.assertRaisesRegex(
                self.warm.WarmStageBlocked, "RETAIN_EVIDENCE"
            ):
                self._stage()
        private = self.state / self.warm.ROOT_NAME
        journal = json.loads((private / "journal.json").read_text())
        self.assertEqual(journal["status"], "INTERRUPTED_RETAIN_PRIVATE_STAGE")
        self.assertEqual(len(journal["completed"]), 3)
        self.assertTrue(journal["active_domain"])
        with mock.patch.object(pull, "pull_path") as repeat:
            with self.assertRaisesRegex(
                self.warm.WarmStageBlocked, "PRIOR_ATTEMPT_RETAINED"
            ):
                self._stage()
            repeat.assert_not_called()

    def test_tampered_private_copy_is_not_a_valid_receipt(self):
        import server_migration_pull as pull
        def fake_pull(source, remote, folder, **kw):
            (folder / "index.php").write_text("copy", encoding="utf-8")
        with mock.patch.object(pull, "pull_path", side_effect=fake_pull):
            self._stage()
        directory = self.state / self.warm.ROOT_NAME
        subdir = next(p for p in directory.iterdir() if p.is_dir())
        (subdir / "index.php").write_text("CHANGED", encoding="utf-8")
        with self.assertRaisesRegex(
            self.warm.WarmStageBlocked, "PRIVATE_COPY_CHANGED"
        ):
            self.warm.verify_private_seventeen_site_warm_copy(
                self.plan, root=self.state)

    def test_scope_drift_and_missing_explicit_intent_before_any_transfer(self):
        import server_migration_pull as pull
        for case in ("no_consent", "bad_target", "bad_owner",
                     "unsafe_path", "source_changed", "plan_forgery"):
            with self.subTest(case=case):
                originals = copy.deepcopy(self.originals)
                plan_data = copy.deepcopy(self.plan)
                target = self.target
                consent = True
                if case == "no_consent":
                    consent = False
                elif case == "bad_target":
                    target += "wrong"
                elif case == "bad_owner":
                    originals[0]["migration_id"] = "foreign-owner"
                elif case == "unsafe_path":
                    originals[0]["sites"][0]["site_root"] = "/etc"
                elif case == "source_changed":
                    originals[1]["source"]["host"] = "different-source"
                else:
                    plan_data["cutover_allowed"] = True
                with mock.patch.object(pull, "pull_path") as transfer:
                    with self.assertRaises(self.warm.WarmStageBlocked):
                        self.warm.stage_private_seventeen_site_warm_copy(
                            plan_data, tuple(originals),
                            root=self.state,
                            actual_target_identity=target,
                            authorize_private_copy=consent)
                    transfer.assert_not_called()
                self.assertFalse((self.state / self.warm.ROOT_NAME).exists())

    def test_symlinked_or_group_writable_parent_blocks(self):
        import server_migration_pull as pull
        unsafe = self.root / "unsafe"
        unsafe.mkdir()
        for root in (unsafe, self.root / "symlink"):
            with self.subTest(root=root):
                if root.name == "symlink":
                    root.symlink_to(unsafe)
                else:
                    root.chmod(0o770)
                with mock.patch.object(legacy, "state_dir", return_value=root), \
                     mock.patch.object(pull, "pull_path") as transfer:
                    with self.assertRaises(self.warm.WarmStageBlocked):
                        self.warm.stage_private_seventeen_site_warm_copy(
                            self.plan, self.originals, root=root,
                            actual_target_identity=self.target,
                            authorize_private_copy=True)
                    transfer.assert_not_called()


class WarmCopyCliBridgeTests(unittest.TestCase):
    """Existing P07 CLI binds the three original owners to private-only mode."""

    def setUp(self):
        import server_migration_pull as pull
        self.pull = pull
        self.originals = tuple(three_partial_tasks())
        self.plan = plan()

    def test_bad_confirmation_aborts_before_state_or_network(self):
        with mock.patch.object(self.pull, "load_state") as read, \
             mock.patch.object(self.pull, "target_identity") as identity:
            with self.assertRaisesRegex(
                self.pull.PullMigrationError, "EXPLICIT_PRIVATE_SCOPE"
            ):
                self.pull.chain_private_file_warm_stage(
                    "a", "b", "c", confirm="CUTOVER_PULL:abc")
            read.assert_not_called()
            identity.assert_not_called()

    def test_cli_stage_uses_private_staging_only_and_verify_is_read_only(self):
        import migration_chain_private_file_stage as warm
        by_id = {s["migration_id"]: s for s in self.originals}
        with mock.patch.object(self.pull, "load_state",
                               side_effect=by_id.__getitem__), \
             mock.patch.object(self.pull, "target_identity",
                               return_value=self.originals[0]["target_server_identity"]), \
             mock.patch.object(self.pull.migration_chain_execution_scope,
                               "scope", return_value={"final_sync_plan": self.plan}), \
             mock.patch.object(warm, "stage_private_seventeen_site_warm_copy",
                               return_value={"status": "PRIVATE_NOT_FINAL"}) as staged, \
             mock.patch.object(warm, "verify_private_seventeen_site_warm_copy",
                               return_value={"status": "VERIFIED_NOT_FINAL"}) as verified:
            mids = [x["migration_id"] for x in self.originals]
            out = self.pull.chain_private_file_warm_stage(
                *mids, confirm="PRESTAGE_17_FILES_PRIVATE_ONLY")
            self.assertEqual(out["status"], "PRIVATE_NOT_FINAL")
            self.assertIs(staged.call_args.kwargs["authorize_private_copy"], True)
            self.assertEqual(staged.call_args.args[1], self.originals)
            self.assertEqual(
                staged.call_args.kwargs["actual_target_identity"],
                self.originals[0]["target_server_identity"])
            check = self.pull.chain_private_file_warm_stage(
                *mids, verify_only=True)
            self.assertEqual(check["status"], "VERIFIED_NOT_FINAL")
            verified.assert_called_once()
            staged.assert_called_once()


if __name__ == "__main__":
    unittest.main()
