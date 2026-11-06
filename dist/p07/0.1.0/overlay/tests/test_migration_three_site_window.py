"""P07 exact original-owner final-window scope: synthetic no-server tests."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_three_site_window as window
import server_migration_pull as pull
from unittest import mock
from tests.test_migration_chain_final_saga import plan


class ThreeSiteWindowAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.locked = plan()

    def test_three_source_exports_are_private_prestage_only(self):
        import gzip
        import json
        import os
        import tempfile
        import migration_chain_execution_scope as execution
        from tests.test_migration_chain_execution_scope import three_partial_tasks
        states = three_partial_tasks()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / states[0]["migration_id"]).mkdir(mode=0o700)
            report = execution.scope(
                *states, root=root, private_owner=os.geteuid())
            by_id = {state["migration_id"]: state for state in states}
            original = [__import__("copy").deepcopy(state) for state in states]

            def write_fake_source_dump(source, remote, local, **kwargs):
                with gzip.open(local, "wt", encoding="utf-8") as out:
                    out.write("CREATE TABLE posts (id INT);\n")
                    out.write("INSERT INTO posts VALUES (1);\n")
            with mock.patch.object(pull, "STATE_ROOT", root), \
                 mock.patch.object(pull, "load_state", side_effect=by_id.__getitem__), \
                 mock.patch.object(pull, "target_identity",
                                   return_value=states[0]["target_server_identity"]), \
                 mock.patch.object(pull.migration_chain_execution_scope,
                                   "scope", return_value=report), \
                 mock.patch.object(pull, "stage_source_runtime",
                                   return_value="/var/lib/vf-server-ops/pull-source/p07-test/runtime") as helper, \
                 mock.patch.object(pull, "source_export_database") as export, \
                 mock.patch.object(pull, "pull_path", side_effect=write_fake_source_dump) as transfer, \
                 mock.patch.object(pull, "freeze_old_server") as freeze, \
                 mock.patch.object(pull, "save_state") as state_write, \
                 mock.patch.object(pull.cloudpanel, "import_database") as db_write:
                arguments = [state["migration_id"] for state in states]
                result = pull.chain_prestage_three_source_dumps(
                    *arguments, confirm="PRESTAGE_THREE_SOURCE_DUMPS_ONLY")
                self.assertEqual(result["status"],
                                 "THREE_SOURCE_DUMPS_PRESTAGED_NOT_FINAL")
                self.assertEqual(result["domain_count"], 3)
                self.assertFalse(result["source_writes_frozen"])
                self.assertFalse(result["source_target_final_parity_verified"])
                self.assertFalse(result["cutover_allowed"])
                self.assertEqual(export.call_count, 3)
                self.assertEqual(transfer.call_count, 3)
                helper.assert_called_once()
                freeze.assert_not_called()
                state_write.assert_not_called()
                db_write.assert_not_called()
                journal = (root / states[0]["migration_id"]
                           / "three-source-dumps-prestage-v1" / "journal.json")
                data = json.loads(journal.read_text())
                self.assertEqual(len(data["completed"]), 3)
                self.assertTrue(all(not site["source_target_parity_verified"]
                                    for site in data["completed"]))
                self.assertEqual(list(states), original)
                with self.assertRaisesRegex(
                        pull.PullMigrationError, "PRIOR_ATTEMPT_RETAINED"):
                    pull.chain_prestage_three_source_dumps(
                        *arguments, confirm="PRESTAGE_THREE_SOURCE_DUMPS_ONLY")
                self.assertEqual(export.call_count, 3)
                self.assertEqual(transfer.call_count, 3)

    def test_source_prestage_requires_exact_confirmation_before_any_remote(self):
        with mock.patch.object(pull, "load_state") as load, \
             mock.patch.object(pull, "stage_source_runtime") as stage:
            with self.assertRaisesRegex(
                    pull.PullMigrationError, "EXPLICIT_SCOPE_REQUIRED"):
                pull.chain_prestage_three_source_dumps(
                    "parent", "child", "tail", confirm="CUTOVER")
            load.assert_not_called()
            stage.assert_not_called()

    def test_remote_export_failure_leaves_intent_and_blocks_retry(self):
        import json
        import os
        import tempfile
        import migration_chain_execution_scope as execution
        from tests.test_migration_chain_execution_scope import three_partial_tasks
        states = three_partial_tasks()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / states[0]["migration_id"]).mkdir(mode=0o700)
            report = execution.scope(
                *states, root=root, private_owner=os.geteuid())
            by_id = {state["migration_id"]: state for state in states}
            def broken_export(*_args, **_kwargs):
                raise pull.PullMigrationError("simulated private export failure")
            with mock.patch.object(pull, "STATE_ROOT", root), \
                 mock.patch.object(pull, "load_state", side_effect=by_id.__getitem__), \
                 mock.patch.object(pull, "target_identity",
                                   return_value=states[0]["target_server_identity"]), \
                 mock.patch.object(pull.migration_chain_execution_scope,
                                   "scope", return_value=report), \
                 mock.patch.object(pull, "stage_source_runtime",
                                   return_value="/var/lib/vf-server-ops/pull-source/p07-test/runtime"), \
                 mock.patch.object(pull, "source_export_database",
                                   side_effect=broken_export) as export:
                args = [state["migration_id"] for state in states]
                with self.assertRaisesRegex(
                        pull.PullMigrationError, "private export failure"):
                    pull.chain_prestage_three_source_dumps(
                        *args, confirm="PRESTAGE_THREE_SOURCE_DUMPS_ONLY")
                journal = (root / states[0]["migration_id"]
                           / "three-source-dumps-prestage-v1" / "journal.json")
                self.assertEqual(json.loads(journal.read_text())["status"],
                                 "SOURCE_EXPORT_AND_TRANSFER_INTENT")
                with self.assertRaisesRegex(
                        pull.PullMigrationError, "PRIOR_ATTEMPT_RETAINED"):
                    pull.chain_prestage_three_source_dumps(
                        *args, confirm="PRESTAGE_THREE_SOURCE_DUMPS_ONLY")
                self.assertEqual(export.call_count, 1)

    def test_operator_scope_exposes_exact_owner_window_without_execution(self):
        from tests.test_migration_chain_execution_scope import three_partial_tasks
        states = three_partial_tasks()
        locked = window.owner_window_scope(
            self.locked, window.OWNER_SITES,
            whole_server_outage_approved=True,
        )
        scope = {"pending_count": 3, "final_sync_plan": self.locked}
        with mock.patch.object(pull, "load_state", side_effect=states), \
             mock.patch.object(pull, "target_identity",
                               return_value=states[0]["target_server_identity"]), \
             mock.patch.object(pull.migration_chain_execution_scope, "scope",
                               return_value=scope):
            result = pull.chain_execution_scope(
                states[0]["migration_id"], states[1]["migration_id"],
                states[2]["migration_id"])
        self.assertEqual(result["owner_final_window"], locked)
        self.assertFalse(result["owner_final_window"]["source_pause_performed"])

    def test_exact_three_site_approval_is_non_executable(self):
        result = window.owner_window_scope(self.locked, window.OWNER_SITES)
        self.assertEqual(result["approved_sites"], list(window.OWNER_SITES))
        self.assertEqual(result["other_sites_unaffected_count"], 14)
        self.assertEqual(result["status"], "OWNER_APPROVAL_BOUND_EXECUTION_BLOCKED")
        for key in ("global_nginx_stop_allowed",
                    "legacy_global_source_freeze_allowed",
                    "source_pause_performed", "source_pause_now_allowed",
                    "old_server_shutdown_allowed",
                    "source_data_delete_allowed",
                    "target_existing_db_overwrite_allowed",
                    "automatic_dns_change_allowed",
                    "cutover_allowed", "writes_performed"):
            self.assertIs(result[key], False, key)

    def test_all_17_site_outage_approval_does_not_authorize_cutover(self):
        approved = window.owner_window_scope(
            self.locked, window.OWNER_SITES,
            whole_server_outage_approved=True,
        )
        limited = window.owner_window_scope(
            self.locked, window.OWNER_SITES,
        )
        self.assertEqual(approved["approved_sites"], list(window.OWNER_SITES))
        self.assertTrue(approved["whole_server_outage_owner_approved"])
        self.assertEqual(approved["approved_outage_scope"],
                         "ALL_17_SITE_BRIEF_MAINTENANCE")
        self.assertEqual(approved["outage_site_count"], 17)
        self.assertEqual(approved["other_sites_unaffected_count"], 0)
        self.assertEqual(
            approved["other_sites_outside_database_reconciliation_count"], 14
        )
        self.assertEqual(limited["outage_site_count"], 3)
        self.assertNotEqual(approved["identity_sha256"],
                            limited["identity_sha256"])
        self.assertNotEqual(approved["outage_identity_sha256"],
                            limited["outage_identity_sha256"])
        self.assertFalse(approved["requires_independent_site_scoped_pause_resume"])
        self.assertTrue(approved["requires_global_pause_and_verified_restore"])
        for field in (
            "global_nginx_stop_allowed",
            "legacy_global_source_freeze_allowed",
            "source_pause_now_allowed",
            "source_pause_performed",
            "old_server_shutdown_allowed",
            "source_data_delete_allowed",
            "target_existing_db_overwrite_allowed",
            "automatic_dns_change_allowed",
            "cutover_allowed",
            "writes_performed",
        ):
            self.assertIs(approved[field], False, field)

    def test_outage_approval_must_be_literal_boolean(self):
        for bad in ("yes", 1, None, [], {}):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(
                        window.WindowBlocked,
                        "P07_WINDOW_OUTAGE_APPROVAL_TYPE_INVALID"):
                    window.owner_window_scope(
                        self.locked, window.OWNER_SITES,
                        whole_server_outage_approved=bad)

    def test_outage_permission_cannot_override_plan_drift(self):
        altered = copy.deepcopy(self.locked)
        altered["source_freeze_allowed"] = True
        with self.assertRaises(Exception):
            window.owner_window_scope(
                altered, window.OWNER_SITES,
                whole_server_outage_approved=True)
        altered = self._plan_with_pending(["unzip.kewaro.com"])
        result = window.owner_window_scope(
            altered, window.OWNER_SITES,
            whole_server_outage_approved=True)
        self.assertFalse(result["source_pause_now_allowed"])

    def test_broader_scope_wrong_order_or_duplicate_rejected(self):
        invalid = (
            tuple(s["domain"] for s in self.locked["steps"][:17]),
            tuple(reversed(window.OWNER_SITES)),
            window.OWNER_SITES[:2],
            window.OWNER_SITES + (window.OWNER_SITES[0],),
            list(window.OWNER_SITES),
        )
        for scope in invalid:
            with self.subTest(scope=scope), self.assertRaises(window.WindowBlocked):
                window.owner_window_scope(self.locked, scope)

    def _plan_with_pending(self, pending):
        """Rehash the existing locked plan for a changed staging state."""
        import hashlib, json
        changed = copy.deepcopy(self.locked)
        changed["pending_domains"] = list(pending)
        canonical = json.dumps({
            "scope": changed["scope_sha256"], "steps": changed["steps"],
            "pending": changed["pending_domains"],
            "blockers": changed["blockers"]
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        changed["plan_sha256"] = hashlib.sha256(canonical).hexdigest()
        return changed

    def test_owner_approval_survives_all_three_sites_becoming_staged(self):
        for pending in (window.OWNER_SITES[:2], window.OWNER_SITES[:1], ()):
            with self.subTest(pending=pending):
                plan = self._plan_with_pending(pending)
                result = window.owner_window_scope(plan, window.OWNER_SITES)
                self.assertEqual(result["pending_site_count"], len(pending))
                self.assertEqual(result["approved_sites"], list(window.OWNER_SITES))
                self.assertFalse(result["source_pause_now_allowed"])
                self.assertFalse(result["cutover_allowed"])

    def test_new_unapproved_pending_site_rejected_even_with_rehashed_plan(self):
        other = next(step["domain"] for step in self.locked["steps"][:17]
                     if step["domain"] not in window.OWNER_SITES)
        plan = self._plan_with_pending([other])
        with self.assertRaisesRegex(window.WindowBlocked, "PENDING_SCOPE_CHANGED"):
            window.owner_window_scope(plan, window.OWNER_SITES)

    def test_unverified_plan_staging_flag_rejected(self):
        broken = copy.deepcopy(self.locked)
        broken["source_freeze_allowed"] = True
        with self.assertRaises(Exception):
            window.owner_window_scope(broken, window.OWNER_SITES)
        broken = copy.deepcopy(self.locked)
        broken["cutover_allowed"] = True
        with self.assertRaises(Exception):
            window.owner_window_scope(broken, window.OWNER_SITES)

    def test_duplicate_original_owner_and_plan_drift_rejected(self):
        broken = copy.deepcopy(self.locked)
        two = [s for s in broken["steps"][:17]
               if s["domain"] in window.OWNER_SITES]
        two[1]["owner"] = two[0]["owner"]
        with self.assertRaises(Exception):
            window.owner_window_scope(broken, window.OWNER_SITES)
        broken = copy.deepcopy(self.locked)
        broken["plan_sha256"] = "0" * 64
        with self.assertRaises(Exception):
            window.owner_window_scope(broken, window.OWNER_SITES)



class SeventeenSiteSourceMaintenanceAssemblyTests(unittest.TestCase):
    """Pre-failure source inventory creates a locked 17-site stop plan."""

    def setUp(self):
        from tests.test_migration_chain_execution_scope import three_partial_tasks
        self.originals = list(three_partial_tasks())
        for task in self.originals:
            # PREPARE_FAILED can occur before target staging of runtime assets.
            task["runtime_assets"] = {
                "system_cron": [], "user_cron": [], "pm2": [],
            }
            task.pop("pending_system_cron", None)
            task.pop("pending_user_cron", None)
            task.pop("pending_pm2", None)
        self.locked = plan()

    def test_all_original_17_owners_one_source_control_no_execution(self):
        orig = self.originals
        user = orig[0]["sites"][0]["site_user"]
        cron_user = orig[2]["sites"][1]["site_user"]
        system = {"path": "/etc/cron.d/p07-test"}
        orig[0]["runtime_assets"]["system_cron"].append(system)
        orig[1]["runtime_assets"]["system_cron"].append(copy.deepcopy(system))
        orig[2]["runtime_assets"]["user_cron"].append({
            "user": cron_user,
            "path": f"/var/spool/cron/crontabs/{cron_user}",
        })
        orig[0]["runtime_assets"]["pm2"].append({
            "user": user,
            "dump": f"/home/{user}/.pm2/dump.pm2",
            "node_runtime": f"/home/{user}/.nvm/versions/node/v22.0.0",
        })
        before = copy.deepcopy(orig)
        with mock.patch.object(pull, "freeze_old_server") as freeze, \
             mock.patch.object(pull, "source_python") as ssh, \
             mock.patch.object(pull, "save_state") as state_write:
            res = window.assemble_seventeen_site_source_maintenance(
                self.locked, tuple(orig))
        self.assertEqual(res["site_count"], 17)
        self.assertEqual(res["original_task_count"], 3)
        self.assertEqual(res["system_cron_count"], 1)
        self.assertEqual(res["user_cron_count"], 1)
        self.assertEqual(res["pm2_count"], 1)
        self.assertEqual(res["status"], "CONTROL_ASSEMBLED_EXECUTION_BLOCKED")
        self.assertEqual(len(res["control"]["sites"]), 17)
        self.assertEqual(len({s["domain"] for s in res["control"]["sites"]}), 17)
        self.assertEqual(res["control"]["pending_system_cron"],
                         [{"source_path": "/etc/cron.d/p07-test",
                           "activated": False}])
        for key in ("source_pause_performed", "source_pause_allowed",
                    "source_final_snapshot_verified",
                    "target_database_writes_performed", "cutover_allowed"):
            self.assertIs(res[key], False)
        self.assertEqual(before, orig)
        for action in (freeze, ssh, state_write):
            action.assert_not_called()

    def test_missing_original_inventory_fails_closed(self):
        self.originals[1]["runtime_assets"].pop("system_cron")
        with self.assertRaisesRegex(
            window.WindowBlocked, "INVENTORY_UNVERIFIED"
        ):
            window.assemble_seventeen_site_source_maintenance(
                self.locked, tuple(self.originals))

    def test_incomplete_target_staging_can_be_absent_but_cannot_disagree(self):
        task = self.originals[0]
        path = "/etc/cron.d/p07-synthetic"
        task["runtime_assets"]["system_cron"].append({"path": path})
        # No pending runtime inventory is expected before an early SQL guard.
        res = window.assemble_seventeen_site_source_maintenance(
            self.locked, tuple(self.originals))
        self.assertEqual(res["system_cron_count"], 1)
        task["pending_system_cron"] = [
            {"source_path": path, "staged_target": "/tmp/staged", "activated": False}
        ]
        window.assemble_seventeen_site_source_maintenance(
            self.locked, tuple(self.originals))
        task["pending_system_cron"][0]["source_path"] = "/etc/cron.d/other"
        with self.assertRaisesRegex(
            window.WindowBlocked, "TARGET_STAGE_DRIFT"
        ):
            window.assemble_seventeen_site_source_maintenance(
                self.locked, tuple(self.originals))

    def test_overlapping_pm2_source_runtime_conflict_blocks(self):
        user = self.originals[0]["sites"][0]["site_user"]
        fixture = {
            "user": user, "dump": f"/home/{user}/.pm2/dump.pm2",
            "node_runtime": f"/home/{user}/.nvm/versions/node/v20.0.0",
        }
        self.originals[0]["runtime_assets"]["pm2"].append(fixture)
        self.originals[1]["runtime_assets"]["pm2"].append({
            **fixture, "node_runtime": f"/home/{user}/.nvm/versions/node/v22.0.0",
        })
        with self.assertRaisesRegex(
            window.WindowBlocked, "OVERLAP_CONFLICT"
        ):
            window.assemble_seventeen_site_source_maintenance(
                self.locked, tuple(self.originals))

    def test_unsafe_path_or_unowned_user_rejected(self):
        for path in ("/etc/cron.d/../shadow", "/etc/cron.d//double"):
            with self.subTest(path=path):
                tasks = copy.deepcopy(self.originals)
                tasks[0]["runtime_assets"]["system_cron"].append({"path": path})
                with self.assertRaises(window.WindowBlocked):
                    window.assemble_seventeen_site_source_maintenance(
                        self.locked, tuple(tasks))
        tasks = copy.deepcopy(self.originals)
        tasks[0]["runtime_assets"]["pm2"].append({
            "user": "unowned-user",
            "dump": "/home/unowned-user/.pm2/dump.pm2",
            "node_runtime": "/home/unowned-user/.nvm/versions/node/v20.0.0",
        })
        with self.assertRaisesRegex(
            window.WindowBlocked, "USER_SCOPE_INVALID"
        ):
            window.assemble_seventeen_site_source_maintenance(
                self.locked, tuple(tasks))

    def test_site_or_source_drift_blocks_control(self):
        for kind in ("site", "source", "runtime", "plan"):
            with self.subTest(kind=kind):
                original = copy.deepcopy(self.originals)
                locked = copy.deepcopy(self.locked)
                if kind == "site":
                    original[1]["sites"][0]["document_root"] = "/wrong"
                elif kind == "source":
                    original[2]["source"]["host"] = "different-host"
                elif kind == "runtime":
                    original[0]["source_runtime_frozen"] = True
                else:
                    locked["source_freeze_allowed"] = True
                with self.assertRaises(Exception):
                    window.assemble_seventeen_site_source_maintenance(
                        locked, tuple(original))


if __name__ == "__main__":
    unittest.main()
