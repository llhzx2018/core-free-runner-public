"""Exact-owner private resource pre-copy, independent no-live-migration tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_chain_private_resource_stage as warm
import server_migration as legacy
import server_migration_pull as pull
from tests.test_migration_chain_resource_bindings import fixture


class PrivateOriginalResourceStageTests(unittest.TestCase):
    def setUp(self):
        self.tasks, self.plan = fixture()
        self.tasks = tuple(self.tasks)
        for task in self.tasks:
            task["source_runtime_path"] = (
                f"/var/lib/vf-server-ops/pull-source/{task['migration_id']}/runtime"
            )
        # Historical P07 source records do not contain the kind key.
        self.tasks[0]["external_assets"][0].pop("kind")
        self.tasks[2]["external_assets"][0].pop("kind")
        self.target = self.tasks[0]["target_server_identity"]
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.parent = root / self.plan["steps"][0]["owner"]
        self.parent.mkdir(mode=0o700)
        self.state = mock.patch.object(legacy, "STATE_ROOT", root)
        self.state.start()
        self.addCleanup(self.state.stop)
        self.visits = []
        self.snapshots = []
        self.cleanup = []

    def fake_kind(self, _source, remote):
        return "DIRECTORY" if remote.endswith("/assets") else "FILE"

    def fake_source_python(self, *args, **kwargs):
        self.snapshots.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    def fake_pull(self, source, remote, local, **kwargs):
        self.visits.append((remote, local, kwargs))
        if remote.endswith(".sqlite"):
            with sqlite3.connect(local) as db:
                db.execute("CREATE TABLE payload (id INTEGER PRIMARY KEY, value TEXT)")
                db.execute("INSERT INTO payload(value) VALUES ('copy')")
        elif remote.endswith("/"):
            (local / "asset.txt").write_text("directory data")
        else:
            local.write_text("single asset")

    def fake_cleanup(self, _source, command, **kwargs):
        self.cleanup.append(command)
        return SimpleNamespace(returncode=0)

    def stage(self, **kwargs):
        return warm.stage_original_private_resources(
            self.plan, self.tasks, root=self.parent,
            actual_target_identity=self.target, authorize_private_copy=True,
            **kwargs,
        )

    def _patch_transport(self, **overrides):
        return [
            mock.patch.object(pull, "source_path_kind",
                              side_effect=overrides.get("kind", self.fake_kind)),
            mock.patch.object(pull, "source_python",
                              side_effect=overrides.get("snapshot", self.fake_source_python)),
            mock.patch.object(pull, "pull_path",
                              side_effect=overrides.get("copy", self.fake_pull)),
            mock.patch.object(pull, "source_remote",
                              side_effect=overrides.get("cleanup", self.fake_cleanup)),
            mock.patch.object(pull, "save_state"),
            mock.patch.object(pull, "freeze_old_server"),
            mock.patch.object(pull.cloudpanel, "import_database"),
        ]

    def test_three_owner_external_and_sqlite_snapshot_private_only(self):
        from contextlib import ExitStack
        original = copy.deepcopy(self.tasks)
        with ExitStack() as stack:
            patches = [stack.enter_context(p) for p in self._patch_transport()]
            result = self.stage()
            self.assertEqual(result["resource_count"], 3)
            self.assertEqual(result["external_count"], 2)
            self.assertEqual(result["sqlite_count"], 1)
            self.assertTrue(result["source_private_sqlite_snapshots_attempted"])
            self.assertFalse(result["existing_target_modified"])
            self.assertFalse(result["source_final_parity"])
            self.assertFalse(result["cutover_allowed"])
            self.assertEqual(len(self.visits), 3)
            self.assertEqual(len(self.snapshots), 1)
            self.assertEqual(len(self.cleanup), 1)
            self.assertIn("rm -f", self.cleanup[0])
            self.assertNotIn("store.sqlite", self.cleanup[0])
            self.assertTrue(all(k["delete"] is False for _, _, k in self.visits))
            for unexpected in patches[-3:]:
                unexpected.assert_not_called()
            self.assertEqual(self.tasks, original)
            proof = warm.verify_original_private_resources(
                self.plan, self.tasks, root=self.parent)
            self.assertEqual(proof["resource_count"], 3)
            self.assertEqual(proof["status"],
                             "ALL_ORIGINAL_PRIVATE_RESOURCES_VERIFIED_NOT_FINAL")
            self.assertFalse(proof["writes_performed"])
            receipt=json.loads((self.parent/warm.ROOT_NAME/"journal.json").read_text())
            self.assertNotIn("active_remote_sqlite_snapshot",receipt)
            with self.assertRaisesRegex(
                warm.ResourceStageBlocked, "PREVIOUS_ATTEMPT_RETAINED"):
                self.stage()
            self.assertEqual(len(self.visits), 3)

    def test_failure_at_resource_two_preserves_intent_no_auto_retry(self):
        from contextlib import ExitStack
        def broken(source, remote, local, **kwargs):
            self.fake_pull(source, remote, local, **kwargs)
            if len(self.visits) == 2:
                raise RuntimeError("secret test exception")
        with ExitStack() as stack:
            for patch in self._patch_transport(copy=broken):
                stack.enter_context(patch)
            with self.assertRaisesRegex(
                warm.ResourceStageBlocked, "RECOVERY_REQUIRED"):
                self.stage()
            stage = self.parent / warm.ROOT_NAME
            receipt = json.loads((stage / "journal.json").read_text())
            self.assertEqual(receipt["status"],
                             "INTERRUPTED_KEEP_ALL_PRIVATE_EVIDENCE")
            self.assertEqual(len(receipt["completed"]), 1)
            with self.assertRaisesRegex(
                warm.ResourceStageBlocked, "PREVIOUS_ATTEMPT_RETAINED"):
                self.stage()
            with self.assertRaises(warm.ResourceStageBlocked):
                warm.verify_original_private_resources(
                    self.plan, self.tasks, root=self.parent)

    def test_drift_or_source_failure_aborts_and_never_modifies_target(self):
        from contextlib import ExitStack
        for kind in ("SYMLINK", "MISSING", "OTHER"):
            with self.subTest(kind=kind):
                temp = tempfile.TemporaryDirectory()
                self.addCleanup(temp.cleanup)
                parent = Path(temp.name) / self.plan["steps"][0]["owner"]
                parent.mkdir(mode=0o700)
                # Rebind the current original parent to a fresh isolated state.
                with mock.patch.object(legacy, "STATE_ROOT", Path(temp.name)), ExitStack() as stack:
                    for p in self._patch_transport(kind=lambda _s, _p: kind):
                        stack.enter_context(p)
                    with self.assertRaises(warm.ResourceStageBlocked):
                        warm.stage_original_private_resources(
                            self.plan, self.tasks, root=parent,
                            actual_target_identity=self.target,
                            authorize_private_copy=True)
                    self.assertEqual(len(list(
                        parent.glob("*/resource-*"))), 0)

    def test_sqlite_corruption_refused_and_private_copy_tampering_detected(self):
        from contextlib import ExitStack
        def bad_copy(source, remote, local, **kwargs):
            self.visits.append((remote, local, kwargs))
            if remote.endswith(".sqlite"):
                local.write_bytes(b"invalid db")
            elif remote.endswith("/"):
                (local / "asset.txt").write_text("normal")
            else:
                local.write_text("file")
        with ExitStack() as stack:
            for p in self._patch_transport(copy=bad_copy):
                stack.enter_context(p)
            with self.assertRaisesRegex(
                warm.ResourceStageBlocked, "RECOVERY_REQUIRED"):
                self.stage()
        journal = json.loads(
            (self.parent / warm.ROOT_NAME / "journal.json").read_text())
        self.assertFalse(journal["cutover_allowed"])
        self.assertEqual(self.cleanup,[])
        self.assertTrue(journal["active_remote_sqlite_snapshot"].endswith(".sqlite"))
        self.assertNotEqual(
            journal["status"], "ALL_ORIGINAL_PRIVATE_RESOURCES_STAGED_NOT_FINAL")

    def test_failed_source_sqlite_snapshot_retains_remote_path_not_deleted(self):
        from contextlib import ExitStack
        def failed_snapshot(*args, **kwargs):
            self.snapshots.append((args,kwargs))
            return SimpleNamespace(returncode=13)
        with ExitStack() as stack:
            for p in self._patch_transport(snapshot=failed_snapshot):
                stack.enter_context(p)
            with self.assertRaisesRegex(
                warm.ResourceStageBlocked, "RECOVERY_REQUIRED"):
                self.stage()
        receipt=json.loads(
            (self.parent/warm.ROOT_NAME/"journal.json").read_text())
        self.assertEqual(receipt["status"],
                         "INTERRUPTED_KEEP_ALL_PRIVATE_EVIDENCE")
        self.assertEqual(len(self.snapshots),1)
        self.assertEqual(self.cleanup,[])
        self.assertTrue(receipt["active_remote_sqlite_snapshot"].endswith(".sqlite"))
        self.assertFalse(receipt["cutover_allowed"])

    def test_interrupted_sqlite_copy_never_removes_source_snapshot(self):
        from contextlib import ExitStack
        def broken_transfer(source, remote, local, **kwargs):
            self.visits.append((remote,local,kwargs))
            if remote.endswith(".sqlite"):
                raise OSError("private transport failed")
            if remote.endswith("/"):
                (local/"asset.txt").write_text("public synthetic")
            else:
                local.write_text("synthetic")
        with ExitStack() as stack:
            for p in self._patch_transport(copy=broken_transfer):
                stack.enter_context(p)
            with self.assertRaisesRegex(
                warm.ResourceStageBlocked, "RECOVERY_REQUIRED"):
                self.stage()
        receipt=json.loads(
            (self.parent/warm.ROOT_NAME/"journal.json").read_text())
        self.assertEqual(receipt["status"],
                         "INTERRUPTED_KEEP_ALL_PRIVATE_EVIDENCE")
        self.assertEqual(self.cleanup,[])
        self.assertEqual(len(self.snapshots),1)
        self.assertIn("resource-warm-",
                      receipt["active_remote_sqlite_snapshot"])
        self.assertNotIn("private transport failed",json.dumps(receipt))

    def test_cleanup_failure_retained_without_false_completion(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for p in self._patch_transport(
                cleanup=lambda *args, **kwargs: SimpleNamespace(returncode=1)
            ):
                stack.enter_context(p)
            with self.assertRaisesRegex(
                warm.ResourceStageBlocked, "TEMP_CLEANUP_RECOVERY_REQUIRED"):
                self.stage()
        journal = json.loads(
            (self.parent / warm.ROOT_NAME / "journal.json").read_text())
        self.assertEqual(
            journal["status"], "SOURCE_PRIVATE_SNAPSHOT_CLEANUP_UNVERIFIED")
        self.assertFalse(journal["cutover_allowed"])

    def test_metadata_drift_and_missing_confirmation_refused_before_write(self):
        for change in ("no_auth", "wrong_target", "changed_owner", "bad_path",
                       "bad_plan", "missing_helper"):
            with self.subTest(change=change):
                original = copy.deepcopy(self.tasks)
                p = copy.deepcopy(self.plan)
                target = self.target
                yes = True
                if change == "no_auth":
                    yes = False
                elif change == "wrong_target":
                    target = "other"
                elif change == "changed_owner":
                    original[0]["migration_id"] = "foreign-owner"
                elif change == "bad_path":
                    original[0]["external_assets"][0]["path"] = "/etc/passwd"
                elif change == "missing_helper":
                    original[1].pop("source_runtime_path")
                else:
                    p["cutover_allowed"] = True
                with mock.patch.object(pull, "pull_path") as copy_source, \
                     mock.patch.object(pull, "source_path_kind") as probe:
                    with self.assertRaises(warm.ResourceStageBlocked):
                        warm.stage_original_private_resources(
                            p, tuple(original), root=self.parent,
                            actual_target_identity=target,
                            authorize_private_copy=yes)
                    copy_source.assert_not_called()
                    probe.assert_not_called()
                self.assertFalse((self.parent / warm.ROOT_NAME).exists())



class ResourceCliBridgeTests(unittest.TestCase):
    def setUp(self):
        self.originals, self.plan = fixture()
        self.originals = tuple(self.originals)

    def test_authorization_check_before_any_state_or_remote(self):
        with mock.patch.object(pull, "load_state") as state, \
             mock.patch.object(pull, "target_identity") as target:
            with self.assertRaisesRegex(
                pull.PullMigrationError, "EXPLICIT_PRIVATE_SCOPE"
            ):
                pull.chain_private_resource_warm_stage(
                    "parent", "child", "tail", confirm="CUTOVER")
            state.assert_not_called()
            target.assert_not_called()

    def test_existing_entry_wires_to_private_stage_and_verify_only(self):
        by_id = {x["migration_id"]: x for x in self.originals}
        ids = tuple(x["migration_id"] for x in self.originals)
        with mock.patch.object(pull, "load_state",
                               side_effect=by_id.__getitem__), \
             mock.patch.object(pull, "target_identity",
                               return_value=self.originals[0]["target_server_identity"]), \
             mock.patch.object(pull.migration_chain_execution_scope,
                               "scope", return_value={"final_sync_plan": self.plan}), \
             mock.patch.object(warm, "stage_original_private_resources",
                               return_value={"status": "PRIVATE_STAGED_NOT_FINAL"}) as stage, \
             mock.patch.object(warm, "verify_original_private_resources",
                               return_value={"status": "PRIVATE_VERIFIED_NOT_FINAL"}) as verify:
            result = pull.chain_private_resource_warm_stage(
                *ids, confirm="PRESTAGE_17_RESOURCES_PRIVATE_ONLY")
            self.assertEqual(result["status"], "PRIVATE_STAGED_NOT_FINAL")
            self.assertIs(stage.call_args.kwargs["authorize_private_copy"], True)
            self.assertEqual(stage.call_args.args[1], self.originals)
            checked = pull.chain_private_resource_warm_stage(
                *ids, verify_only=True)
            self.assertEqual(checked["status"], "PRIVATE_VERIFIED_NOT_FINAL")
            verify.assert_called_once()
            stage.assert_called_once()


if __name__ == "__main__":
    unittest.main()
