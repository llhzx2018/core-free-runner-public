"""One-shot P07 existing 17-site delivery operator tests; no real VPS IO."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_chain_execution_scope as scope_mod
import migration_chain_private_file_stage as files
import migration_chain_private_resource_stage as assets
import migration_three_site_window as owner
import server_migration as legacy
import server_migration_pull as pull
from tests.test_migration_chain_execution_scope import three_partial_tasks


class ExistingSeventeenSiteDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.states = tuple(three_partial_tasks())
        self.byid = {s["migration_id"]: s for s in self.states}
        self.ids = tuple(s["migration_id"] for s in self.states)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parent = self.root / self.ids[0]
        self.parent.mkdir(mode=0o700)
        self.targets = [
            mock.patch.object(pull, "STATE_ROOT", self.root),
            mock.patch.object(legacy, "STATE_ROOT", self.root),
            mock.patch.object(pull, "load_state", side_effect=self.byid.__getitem__),
            mock.patch.object(pull, "target_identity",
                              return_value=self.states[0]["target_server_identity"]),
        ]
        for p in self.targets:
            p.start()
            self.addCleanup(p.stop)

    def run_delivery(self, action="status", confirm=None):
        return pull.chain_seventeen_site_delivery(
            *self.ids, action=action, confirm=confirm)

    def test_status_has_single_entry_and_no_source_or_target_mutation(self):
        with mock.patch.object(pull, "source_remote") as source, \
             mock.patch.object(pull, "source_python") as source_helper, \
             mock.patch.object(pull, "save_state") as state_writes, \
             mock.patch.object(pull, "source_nginx_stop") as stop, \
             mock.patch.object(pull.cloudpanel, "import_database") as sql_write:
            report = self.run_delivery()
        self.assertEqual(report["status"], "17_SITE_DELIVERY_NOT_CUTOVER_READY")
        self.assertEqual(report["site_count"], 17)
        self.assertEqual(report["original_task_count"], 3)
        self.assertEqual(report["staged_site_count"], 14)
        self.assertEqual(report["pending_site_count"], 3)
        self.assertFalse(report["cutover_allowed"])
        self.assertFalse(report["writes_performed"])
        self.assertEqual(len(report["remaining_final_gates"]), 4)
        self.assertFalse(report["private_site_warm_attempt_exists"])
        for op in (source, source_helper, state_writes, stop, sql_write):
            op.assert_not_called()
        for leak in ("old.example.test", "origpass", "/home/"):
            self.assertNotIn(leak, json.dumps(report))

    def test_read_only_freeze_preview_deduplicates_original_source_inventory(self):
        import migration_chain_source_pause as pause
        for state in self.states:
            state["runtime_assets"]={"system_cron":[],"user_cron":[],"pm2":[]}
        with mock.patch.object(pull,"source_python") as ssh, \
             mock.patch.object(pull,"source_nginx_stop") as stop, \
             mock.patch.object(pull,"save_state") as saved:
            result=self.run_delivery("pause-preview")
        self.assertEqual(result["status"],"SOURCE_PAUSE_PREVIEW_ONLY")
        self.assertEqual(result["site_count"],17)
        self.assertEqual(result["original_task_count"],3)
        self.assertFalse(result["source_runtime_paused"])
        self.assertFalse(result["source_business_writes_paused"])
        self.assertFalse(result["cutover_allowed"])
        for op in (ssh,stop,saved):
            op.assert_not_called()

    def test_live_source_pause_not_implicitly_authorized_by_delivery_entry(self):
        from contextlib import ExitStack
        for state in self.states:
            state["runtime_assets"]={"system_cron":[],"user_cron":[],"pm2":[]}
        with mock.patch.object(pull,"source_python") as ssh, \
             mock.patch.object(pull,"freeze_old_server") as freeze:
            with self.assertRaisesRegex(
                pull.PullMigrationError, "ACTION_UNSUPPORTED"
            ):
                self.run_delivery("pause-source")
            ssh.assert_not_called()
            freeze.assert_not_called()

    def test_wrong_private_preparation_confirm_rejected_before_read(self):
        with mock.patch.object(pull, "load_state") as state, \
             mock.patch.object(pull, "target_identity") as identity:
            for action, confirmation in (
                ("private-prestage", None),
                ("private-prestage", "CUTOVER"),
                ("verify-private", "PRESTAGE_EXISTING_17_SITES_PRIVATE_ONLY"),
                ("bad-command", None),
            ):
                with self.assertRaises(pull.PullMigrationError):
                    self.run_delivery(action, confirmation)
            state.assert_not_called()
            identity.assert_not_called()

    def test_single_private_preparation_invokes_existing_three_primitives_once(self):
        before = copy.deepcopy(self.states)
        with mock.patch.object(
                files, "stage_private_seventeen_site_warm_copy",
                return_value={"site_count":17,"cutover_allowed":False}) as stage_files, \
             mock.patch.object(
                assets, "stage_original_private_resources",
                return_value={"resource_count":3,"cutover_allowed":False}) as stage_assets, \
             mock.patch.object(pull, "chain_prestage_three_source_dumps",
                return_value={"domain_count":3,"cutover_allowed":False}) as dumps, \
             mock.patch.object(files, "verify_private_seventeen_site_warm_copy",
                return_value={"site_count":17}) as check_files, \
             mock.patch.object(assets, "verify_original_private_resources",
                return_value={"resource_count":3}) as check_assets, \
             mock.patch.object(pull, "_verify_three_owner_private_sql_dumps",
                return_value={"database_count":3}) as check_sql, \
             mock.patch.object(pull, "source_nginx_stop") as stop, \
             mock.patch.object(pull, "save_state") as saved:
            report = self.run_delivery(
                "private-prestage",
                "PRESTAGE_EXISTING_17_SITES_PRIVATE_ONLY")
        self.assertEqual(report["status"],
                         "17_SITE_PRIVATE_PRESTAGE_VERIFIED_NOT_CUTOVER")
        self.assertEqual(report["site_file_count"],17)
        self.assertEqual(report["private_resource_count"],3)
        self.assertEqual(report["original_database_count"],3)
        self.assertFalse(report["source_target_final_parity"])
        self.assertFalse(report["cutover_allowed"])
        stage_files.assert_called_once()
        stage_assets.assert_called_once()
        dumps.assert_called_once()
        check_files.assert_called_once()
        check_assets.assert_called_once()
        check_sql.assert_called_once()
        stop.assert_not_called()
        saved.assert_not_called()
        self.assertEqual(before, self.states)

    def test_partial_private_preparation_aborts_no_replay(self):
        with mock.patch.object(
                files, "stage_private_seventeen_site_warm_copy",
                return_value={"site_count":17,"cutover_allowed":False}) as f, \
             mock.patch.object(
                assets, "stage_original_private_resources",
                side_effect=assets.ResourceStageBlocked("partial")) as a, \
             mock.patch.object(pull, "chain_prestage_three_source_dumps") as dumps:
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "PARTIAL_RECONCILIATION_REQUIRED"):
                self.run_delivery("private-prestage",
                                  "PRESTAGE_EXISTING_17_SITES_PRIVATE_ONLY")
            f.assert_called_once()
            a.assert_called_once()
            dumps.assert_not_called()
        (self.parent / "p07-17-site-private-warm-stage-v1").mkdir()
        with mock.patch.object(
                files, "stage_private_seventeen_site_warm_copy") as again:
            with self.assertRaisesRegex(
                pull.PullMigrationError, "PRIOR_ATTEMPT_RETAIN"):
                self.run_delivery("private-prestage",
                                  "PRESTAGE_EXISTING_17_SITES_PRIVATE_ONLY")
            again.assert_not_called()

    def test_target_mismatch_rejected_before_ssh_or_private_write(self):
        with mock.patch.object(pull,"target_identity",
                               return_value="changed-cp2"), \
             mock.patch.object(pull,"source_remote") as ssh:
            with self.assertRaisesRegex(
                pull.PullMigrationError, "TARGET_IDENTITY_CHANGED"):
                self.run_delivery()
            ssh.assert_not_called()

    def populate_private_source_receipt(self):
        folder = self.parent / "three-source-dumps-prestage-v1"
        folder.mkdir(mode=0o700)
        plan = scope_mod.scope(*self.states)["final_sync_plan"]
        completed = []
        for i,domain in enumerate(owner.OWNER_SITES):
            name = f"{i + 1:020x}.sql.gz"
            target = folder / name
            with gzip.open(target, "wb") as stream:
                stream.write(b"CREATE TABLE posts (id INT);\n")
            target.chmod(0o600)
            completed.append({
                "domain":domain,
                "original_owner":self.ids[i],
                "dump_basename":name,
                "dump_bytes":target.stat().st_size,
                "dump_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
                "final_snapshot":False,
                "source_target_parity_verified":False,
            })
        legacy.atomic_private_json(folder / "journal.json", {
            "schema":"p07.chain-three-source-dumps-prestage.v1",
            "status":"THREE_SOURCE_DUMPS_PRESTAGED_NOT_FINAL",
            "plan_sha256":plan["plan_sha256"],
            "target_identity_sha256":plan["target_identity_sha256"],
            "source_runtime_frozen":False,
            "cutover_allowed":False,
            "completed":completed,
        })
        return plan,folder

    def test_real_private_sql_readback_checks_checksum_and_no_final_claim(self):
        plan,folder = self.populate_private_source_receipt()
        result = pull._verify_three_owner_private_sql_dumps(plan,self.ids[0])
        self.assertEqual(result["database_count"],3)
        self.assertFalse(result["source_frozen"])
        self.assertFalse(result["final_source_parity"])
        self.assertFalse(result["cutover_allowed"])
        changed = folder / "00000000000000000001.sql.gz"
        changed.write_bytes(b"tampered dump")
        with self.assertRaisesRegex(
            pull.PullMigrationError, "CONTENT_CHANGED|FILE_UNSAFE"):
            pull._verify_three_owner_private_sql_dumps(plan,self.ids[0])

    def test_symlink_private_dump_rejected_before_sql_interpretation(self):
        plan, folder = self.populate_private_source_receipt()
        target = folder / "00000000000000000001.sql.gz"
        target.unlink()
        target.symlink_to(folder / "00000000000000000002.sql.gz")
        with self.assertRaisesRegex(
            pull.PullMigrationError,"FILE_UNSAFE"):
            pull._verify_three_owner_private_sql_dumps(plan,self.ids[0])


if __name__ == "__main__":
    unittest.main()
