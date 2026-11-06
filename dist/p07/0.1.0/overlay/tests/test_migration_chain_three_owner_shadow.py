"""Three original owner Shadow application transaction: isolated real file IO.

No old VPS, CP2, DNS or real CloudPanel is accessed. The synthetic test
fixture explicitly manufactures CUTOVER_RUNNING only in memory. The real
historic owner states remain PREPARE_FAILED / partial, so the implementation
refuses them rather than mutating their status or bypassing original guards.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest import TestCase, mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import app_config
import migration_chain_consolidation as consolidated
import migration_chain_final_saga as saga
import migration_chain_three_owner_shadow as triple
import migration_final_db_shadow as shadow
import migration_three_site_window as window
import server_migration as legacy
import server_migration_pull as pull
from tests.test_migration_chain_execution_scope import three_partial_tasks
from tests.test_migration_chain_final_saga import plan as original_plan

SQL = "CREATE TABLE t (id INT);\nINSERT INTO t VALUES (1);\n"


class OriginalThreeOwnerShadowTransactionTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.states_dir = self.root / "states"
        self.states_dir.mkdir(mode=0o700)
        states_patch = mock.patch.object(legacy, "STATE_ROOT", self.states_dir)
        states_patch.start()
        self.addCleanup(states_patch.stop)

        self.tasks = list(three_partial_tasks())
        self.tasks_byid = {s["migration_id"]: s for s in self.tasks}
        self.base = copy.deepcopy(original_plan())
        self.target = self.tasks[0]["target_server_identity"]
        self.sources = {}
        self.original_bytes = {}
        self.configs = {}
        self.shadows = {}
        self.selected_sites = []

        # Synthetic transition states in temporary memory only. The module
        # must NOT ever create these states for real historical owner tasks.
        for state in self.tasks:
            state["status"] = "CUTOVER_RUNNING"
            state["source_runtime_frozen"] = True
            state["target_runtime_activated"] = False
            state["dns_changed_by_p07"] = False
            state["source_delete_allowed"] = False
            state["existing_target_overwrite_allowed"] = False
            state.pop("cutover_prohibited", None)
            state.pop("partial_parent_migration_id", None)

        sites_scope = []
        for step in self.base["steps"][:17]:
            state = self.tasks_byid[step["owner"]]
            site = state["sites"][step["index"]]
            site["stage_status"] = "PULLED_STAGED"
            domain = site["domain"]
            if domain in window.OWNER_SITES:
                folder = self.root / "isolated-app" / domain
                folder.mkdir(mode=0o700, parents=True)
                site["site_root"] = str(folder)
                site["document_root"] = str(folder)
                config = folder / "wp-config.php"
                idx = window.OWNER_SITES.index(domain)
                db = site["mysql_databases"][0]
                config.write_text(
                    f"define('DB_NAME', '{db}');\n"
                    f"define('DB_USER', 'olduser{idx}');\n"
                    f"define('DB_PASSWORD', 'oldpass{idx}');\n",
                    encoding="utf-8")
                self.configs[domain] = config
                self.original_bytes[domain] = config.read_bytes()
                self.selected_sites.append((state, site))
                marker = legacy.target_db_marker(
                    state["migration_id"], domain, db, 1)
                legacy.atomic_private_json(marker, {
                    "domain": domain, "database": db,
                    "created_by_migration": state["migration_id"],
                    "username": f"olduser{idx}",
                    "password": f"oldpass{idx}",
                })
                dump = legacy.state_dir(state["migration_id"]) / (
                    f"sql-source-{idx}.sql.gz")
                with gzip.open(dump, "wt", encoding="utf8") as file:
                    file.write(SQL)
                self.sources[domain] = dump
            new_sha = hashlib.sha256(
                saga._encoded(consolidated._site_contract(site))
            ).hexdigest()
            step["site_contract_sha256"] = new_sha
            sites_scope.append((
                domain, step["owner"], step["index"],
                site["stage_status"], new_sha,
            ))
        self.base["pending_domains"] = []
        self.base["scope_sha256"] = hashlib.sha256(saga._encoded({
            "sites": sites_scope,
            "source": self.base["source_identity_sha256"],
            "target": self.base["target_identity_sha256"],
        })).hexdigest()
        self.base["plan_sha256"] = hashlib.sha256(saga._encoded({
            "scope": self.base["scope_sha256"],
            "steps": self.base["steps"],
            "pending": self.base["pending_domains"],
            "blockers": self.base["blockers"],
        })).hexdigest()
        saga.validate_locked_plan(self.base)
        self.tasks = tuple(self.tasks)

        def export(db, output):
            for state, site in self.selected_sites:
                candidate = shadow.shadow_identity(state, site)[1]
                if db == candidate:
                    shutil.copyfile(self.sources[site["domain"]], output)
                    return output
            raise AssertionError("No matching synthetic owner shadow")

        current = mock.patch.object(
            shadow.cloudpanel, "export_database", side_effect=export)
        current.start()
        self.addCleanup(current.stop)
        with mock.patch.object(shadow.cloudpanel, "add_database"), \
             mock.patch.object(shadow.cloudpanel, "import_database"):
            for state, site in self.selected_sites:
                result = shadow.stage_frozen_source_shadow(
                    state, site, self.sources[site["domain"]],
                    actual_target_identity=self.target)
                self.assertEqual(
                    result["status"], "STAGED_VERIFIED_NOT_ACTIVATED")
                self.shadows[site["domain"]] = result["shadow_database"]
        self.parent_dir = self.states_dir / self.tasks[0]["migration_id"]
        # The original helper may have created a 0755 synthetic owner
        # directory. A real cross-task transaction MUST refuse that; the
        # isolated fixture must explicitly meet its 0700 private boundary.
        self.parent_dir.chmod(0o700)
        # The exact public DNS resolver is separately unit tested. Here
        # only the new cross-owner invocation boundary is under test;
        # synthetic fixtures must never access external DNS.
        route_patch = mock.patch.object(
            pull, "require_old_source_route_before_manual_rollback")
        self.route_probe = route_patch.start()
        self.addCleanup(route_patch.stop)

    def switch(self, *, confirm=triple.SWITCH_CONFIRM):
        return triple.switch_three_owner_shadows(
            self.base, self.tasks,
            actual_target_identity=self.target, confirmation=confirm)

    def rollback(self, *, confirm=triple.RESTORE_CONFIRM):
        return triple.rollback_three_owner_shadows(
            self.base, self.tasks,
            actual_target_identity=self.target, confirmation=confirm)

    def assert_original_configs(self):
        for domain, original in self.original_bytes.items():
            self.assertEqual(self.configs[domain].read_bytes(), original)

    def test_pre_dns_route_checked_for_each_original_owner(self):
        self.switch()
        self.assertEqual(
            [call.args[0]["migration_id"]
             for call in self.route_probe.call_args_list],
            [state["migration_id"] for state in self.tasks])
        self.route_probe.reset_mock()
        self.rollback()
        self.assertEqual(
            [call.args[0]["migration_id"]
             for call in self.route_probe.call_args_list],
            [state["migration_id"] for state in self.tasks])
        self.assert_original_configs()

    def test_manual_dns_change_blocks_switch_before_config_or_journal_write(self):
        for rejected in self.tasks:
            with self.subTest(owner=rejected["migration_id"]):
                self.route_probe.reset_mock()
                def changed(state):
                    if state["migration_id"] == rejected["migration_id"]:
                        raise pull.PullMigrationError(
                            "MANUAL_ROLLBACK_PRE_DNS_SOURCE_ROUTE_UNPROVEN")
                self.route_probe.side_effect = changed
                with self.assertRaisesRegex(
                    triple.ThreeOwnerShadowBlocked,
                    "THREE_SHADOW_MANUAL_DNS_ROUTE_UNVERIFIED"
                ):
                    self.switch()
                self.assert_original_configs()
                self.assertFalse((self.parent_dir / triple.NAME).exists())
        self.route_probe.side_effect = None

    def test_manual_dns_change_blocks_pre_dns_rollback_until_reconciled(self):
        self.switch()
        receipt = self.parent_dir / triple.NAME
        self.route_probe.side_effect = pull.PullMigrationError(
            "MANUAL_ROLLBACK_PRE_DNS_SOURCE_ROUTE_UNPROVEN")
        with self.assertRaisesRegex(
            triple.ThreeOwnerShadowBlocked,
            "THREE_SHADOW_MANUAL_DNS_ROUTE_UNVERIFIED"
        ):
            self.rollback()
        self.assertEqual(
            json.loads(receipt.read_text())["status"],
            "THREE_SHADOW_CONFIGS_SWITCHED_PRE_DNS")
        for domain, config in self.configs.items():
            self.assertIn(self.shadows[domain].encode(), config.read_bytes())
        self.route_probe.side_effect = None
        self.assertEqual(self.rollback()["status"],
                         "THREE_SHADOW_CONFIGS_RESTORED")
        self.assert_original_configs()

    def test_three_independent_original_owners_success_and_full_reverse(self):
        self.assertEqual(
            triple.inspect_three_owner_shadows(
                self.base, self.tasks, actual_target_identity=self.target
            )["status"], "NO_ATTEMPT")
        before = copy.deepcopy(self.tasks)
        with mock.patch.object(shadow.cloudpanel, "delete_database") as dele, \
             mock.patch.object(shadow.cloudpanel, "add_database") as add, \
             mock.patch.object(shadow.cloudpanel, "import_database") as imp:
            result = self.switch()
            self.assertEqual(
                result["status"], "THREE_SHADOW_CONFIGS_SWITCHED_PRE_DNS")
            self.assertFalse(result["cutover_allowed"])
            self.assertFalse(result["target_runtime_activated"])
            for domain, config in self.configs.items():
                self.assertNotEqual(config.read_bytes(), self.original_bytes[domain])
                self.assertIn(self.shadows[domain].encode(), config.read_bytes())
            journal = self.parent_dir / triple.NAME
            self.assertEqual(journal.stat().st_mode & 0o777, 0o600)
            raw = journal.read_text()
            self.assertNotIn("oldpass", raw)
            self.assertNotIn("shadow_password", raw)
            self.assertEqual(json.loads(raw)["last_committed_count"], 3)
            self.assertEqual(
                triple.inspect_three_owner_shadows(
                    self.base, self.tasks, actual_target_identity=self.target
                )["status"], "THREE_SHADOW_CONFIGS_SWITCHED_PRE_DNS")
            restored = self.rollback()
            self.assertEqual(
                restored["status"], "THREE_SHADOW_CONFIGS_RESTORED")
            self.assertTrue(restored["original_application_mappings_restored"])
            for effect in (dele, add, imp):
                effect.assert_not_called()
        self.assert_original_configs()
        self.assertEqual(before, self.tasks)
        # Idempotent explicit rollback remains safe; switch must never replay.
        self.assertEqual(self.rollback()["status"], "THREE_SHADOW_CONFIGS_RESTORED")
        with self.assertRaisesRegex(
            triple.ThreeOwnerShadowBlocked,
            "PREVIOUS_ATTEMPT_RECONCILIATION_REQUIRED"
        ):
            self.switch()
        self.assert_original_configs()

    def test_second_owner_failure_after_config_write_rolls_back_all_three(self):
        calls = []
        real = shadow.activate_verified_shadow
        def interrupted(state, site, *, actual_target_identity):
            calls.append(site["domain"])
            result = real(
                state, site, actual_target_identity=actual_target_identity)
            if len(calls) == 2:
                raise RuntimeError("private crash between marker and journal")
            return result
        with mock.patch.object(
            shadow, "activate_verified_shadow", side_effect=interrupted):
            with self.assertRaisesRegex(
                triple.ThreeOwnerShadowBlocked,
                "SWITCH_FAILED_ALL_RESTORED"):
                self.switch()
        self.assertEqual(len(calls), 2)
        self.assert_original_configs()
        receipt = json.loads((self.parent_dir / triple.NAME).read_text())
        self.assertEqual(receipt["status"], "THREE_SHADOW_CONFIGS_RESTORED")
        self.assertEqual(receipt["last_committed_count"], 1)
        self.assertEqual(receipt["rollback_failed_count"], 0)
        self.assertFalse(receipt["cutover_allowed"])

    def test_third_owner_failure_reverse_order_including_crash_gap(self):
        order = []
        actual_activate = shadow.activate_verified_shadow
        actual_rollback = shadow.rollback_shadow_application
        def broken(state, site, *, actual_target_identity):
            order.append(("activate", site["domain"]))
            result = actual_activate(
                state, site, actual_target_identity=actual_target_identity)
            if len([x for x in order if x[0] == "activate"]) == 3:
                raise OSError("simulated third owner crash")
            return result
        def reverse(state, site, *, actual_target_identity):
            order.append(("rollback", site["domain"]))
            return actual_rollback(
                state, site, actual_target_identity=actual_target_identity)
        with mock.patch.object(
            shadow, "activate_verified_shadow", side_effect=broken
        ), mock.patch.object(
            shadow, "rollback_shadow_application", side_effect=reverse
        ):
            with self.assertRaisesRegex(
                triple.ThreeOwnerShadowBlocked,
                "SWITCH_FAILED_ALL_RESTORED"):
                self.switch()
        self.assertEqual(
            [name for verb, name in order if verb == "rollback"],
            list(reversed(window.OWNER_SITES)))
        self.assert_original_configs()

    def test_partial_rollback_requires_explicit_resume_from_private_receipt(self):
        real_activate = shadow.activate_verified_shadow
        real_restore = shadow.rollback_shadow_application
        def broken_activate(state, site, *, actual_target_identity):
            outcome = real_activate(
                state, site, actual_target_identity=actual_target_identity)
            if site["domain"] == "www3.m3u8.one":
                raise RuntimeError("interrupted after third change")
            return outcome
        def broken_restore(state, site, *, actual_target_identity):
            if site["domain"] == "unzip.kewaro.com":
                raise RuntimeError("transient recovery IO failure")
            return real_restore(
                state, site, actual_target_identity=actual_target_identity)
        with mock.patch.object(
            shadow, "activate_verified_shadow", side_effect=broken_activate
        ), mock.patch.object(
            shadow, "rollback_shadow_application", side_effect=broken_restore
        ):
            with self.assertRaisesRegex(
                triple.ThreeOwnerShadowBlocked, "PARTIAL_RECOVERY_REQUIRED"):
                self.switch()
        journal = self.parent_dir / triple.NAME
        self.assertEqual(json.loads(journal.read_text())["status"],
                         "ROLLBACK_PARTIAL_RECOVERY_REQUIRED")
        with mock.patch.object(shadow.cloudpanel, "delete_database") as dele, \
             mock.patch.object(shadow.cloudpanel, "import_database") as imp:
            self.assertEqual(self.rollback()["status"],
                             "THREE_SHADOW_CONFIGS_RESTORED")
            dele.assert_not_called()
            imp.assert_not_called()
        self.assert_original_configs()

    def test_crash_gap_explicit_rollback_ignores_unreliable_completed_counter(self):
        state, site = self.selected_sites[0]
        shadow.activate_verified_shadow(
            state, site, actual_target_identity=self.target)
        selected, sha = triple._scope(self.base, self.tasks, self.target)
        digest = triple._fingerprint(sha, selected, self.target)
        record = {
            "schema": triple.SCHEMA,
            "status": "SWITCHING",
            "plan_sha256": sha,
            "inventory_sha256": digest,
            "target_identity_sha256":
                hashlib.sha256(self.target.encode()).hexdigest(),
            "domains": [row["domain"] for _state, row, _step in selected],
            "original_owners": [
                state["migration_id"] for state, _row, _step in selected],
            "last_committed_count": 0,
            "old_databases_retained": True,
            "shadow_databases_retained": True,
            "target_runtime_activated": False,
            "dns_changed": False,
            "cutover_allowed": False,
        }
        legacy.atomic_private_json(self.parent_dir / triple.NAME, record)
        self.assertEqual(self.rollback()["status"],
                         "THREE_SHADOW_CONFIGS_RESTORED")
        self.assert_original_configs()

    def test_all_three_shadow_live_preflight_blocks_first_config_switch(self):
        old = shadow.cloudpanel.export_database.side_effect
        third = self.shadows["www3.m3u8.one"]
        def changed_shadow(name, filename):
            if name == third:
                with gzip.open(filename, "wt", encoding="utf8") as out:
                    out.write("CREATE TABLE t (id INT);\nINSERT INTO t VALUES (999);\n")
                return filename
            return old(name, filename)
        with mock.patch.object(
            shadow.cloudpanel, "export_database", side_effect=changed_shadow
        ), mock.patch.object(
            shadow, "activate_verified_shadow") as activate:
            with self.assertRaisesRegex(
                triple.ThreeOwnerShadowBlocked,
                "ORIGINAL_PRIVATE_OR_LIVE_PROOF_INVALID"):
                self.switch()
            activate.assert_not_called()
        self.assert_original_configs()
        self.assertFalse((self.parent_dir / triple.NAME).exists())

    def test_owner_gate_stays_closed_for_actual_historical_tasks(self):
        historical = tuple(three_partial_tasks())
        with mock.patch.object(shadow, "activate_verified_shadow") as act, \
             mock.patch.object(shadow.cloudpanel, "import_database") as imp:
            with self.assertRaisesRegex(
                triple.ThreeOwnerShadowBlocked,
                "ORIGINAL_CUTOVER_GATE_NOT_MET"):
                triple.switch_three_owner_shadows(
                    original_plan(), historical,
                    actual_target_identity=self.target,
                    confirmation=triple.SWITCH_CONFIRM)
            act.assert_not_called()
            imp.assert_not_called()

    def test_wrong_confirmation_owner_contract_and_identity_all_block(self):
        with mock.patch.object(shadow, "activate_verified_shadow") as activate:
            with self.assertRaisesRegex(
                triple.ThreeOwnerShadowBlocked,
                "EXPLICIT_SWITCH_CONFIRMATION_REQUIRED"):
                self.switch(confirm="MIGRATE_NOW")
            with self.assertRaisesRegex(
                triple.ThreeOwnerShadowBlocked,
                "CP2_IDENTITY_CHANGED"):
                triple.switch_three_owner_shadows(
                    self.base, self.tasks,
                    actual_target_identity="sha256:different",
                    confirmation=triple.SWITCH_CONFIRM)
            changed = copy.deepcopy(self.base)
            changed["steps"][7]["owner"] = self.tasks[1]["migration_id"]
            with self.assertRaises(triple.ThreeOwnerShadowBlocked):
                triple.switch_three_owner_shadows(
                    changed, self.tasks, actual_target_identity=self.target,
                    confirmation=triple.SWITCH_CONFIRM)
            activate.assert_not_called()
        self.assert_original_configs()

    def test_receipt_identity_tamper_rejects_recovery_without_overwrite(self):
        self.switch()
        journal = self.parent_dir / triple.NAME
        record = json.loads(journal.read_text())
        record["inventory_sha256"] = "f"*64
        legacy.atomic_private_json(journal, record)
        with mock.patch.object(shadow, "rollback_shadow_application") as inverse:
            with self.assertRaisesRegex(
                triple.ThreeOwnerShadowBlocked,
                "PRIVATE_RECEIPT_SCOPE_DRIFT"):
                self.rollback()
            inverse.assert_not_called()
        self.assertEqual(json.loads(journal.read_text())["status"],
                         "THREE_SHADOW_CONFIGS_SWITCHED_PRE_DNS")


if __name__ == "__main__":
    import unittest
    unittest.main()
