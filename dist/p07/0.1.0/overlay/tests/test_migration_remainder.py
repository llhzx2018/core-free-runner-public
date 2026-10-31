"""Fail-closed tests for staging the untouched suffix after an SQL-guard stop.

Only synthetic migration-state fixtures are used; no VPS, CloudPanel or DB.
"""
from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_remainder as remainder
import server_migration_pull as pull


def blocked_parent() -> dict:
    sites = [
        {"domain": f"site{i}.example.test", "site_user": f"user{i}",
         "stage_status": "PULLED_STAGED" if i <= 7 else "PENDING"}
        for i in range(1, 18)
    ]
    return {
        "schema": pull.SCHEMA,
        "migration_id": "pull-20261028T103425Z-98050c76",
        "status": "PREPARE_FAILED",
        "last_sql_guard_failure": {"reason": "CONDITIONAL_DDL"},
        "source": {"host": "old.example.test", "ip": "192.0.2.3",
                   "ssh_user": "root", "ssh_port": 22},
        "source_server_identity": "sha256:sourcetest",
        "source_runtime_frozen": False,
        "target_runtime_activated": False,
        "dns_changed_by_p07": False,
        "source_delete_allowed": False,
        "existing_target_overwrite_allowed": False,
        "sites": sites,
    }


class RemainderScopeTests(unittest.TestCase):
    def test_scope_selects_only_sites_after_blocker_and_does_not_mutate(self):
        parent = blocked_parent()
        original = copy.deepcopy(parent)
        plan = remainder.select(parent)
        self.assertEqual(plan["status"], "STAGING_SCOPE_ONLY")
        self.assertEqual(plan["already_staged_sites"], 7)
        self.assertEqual(plan["blocked_site"], "site8.example.test")
        self.assertEqual(plan["remaining_sites"], 9)
        self.assertEqual(
            plan["candidate_domains"],
            [f"site{i}.example.test" for i in range(9, 18)],
        )
        self.assertFalse(plan["cutover_allowed"])
        self.assertFalse(plan["existing_target_overwrite_allowed"])
        self.assertFalse(plan["blocked_site_retry_allowed"])
        self.assertEqual(parent, original)

    def test_fail_closed_for_unsafe_parent_states(self):
        for key, value in (
            ("status", "PREPARED"),
            ("source_runtime_frozen", True),
            ("source_runtime_frozen", None),
            ("target_runtime_activated", True),
            ("dns_changed_by_p07", True),
            ("source_delete_allowed", True),
            ("existing_target_overwrite_allowed", True),
            ("partial_parent_migration_id", "another"),
        ):
            with self.subTest(key=key):
                parent = blocked_parent()
                parent[key] = value
                with self.assertRaises(remainder.RemainderBlocked):
                    remainder.select(parent)

    def test_guard_failure_must_be_proven_not_a_generic_prepare_failure(self):
        for guard in (None, {}, {"reason": "OTHER"}, "CONDITIONAL_DDL"):
            with self.subTest(guard=guard):
                parent = blocked_parent()
                parent["last_sql_guard_failure"] = guard
                with self.assertRaises(remainder.RemainderBlocked):
                    remainder.select(parent)

    def test_rejects_noncontiguous_or_ambiguous_progress(self):
        for kind in ("late_staged", "no_suffix", "no_prefix", "unknown_stage",
                     "duplicate_domain", "duplicate_user"):
            with self.subTest(kind=kind):
                parent = blocked_parent()
                rows = parent["sites"]
                if kind == "late_staged":
                    rows[10]["stage_status"] = "PULLED_STAGED"
                elif kind == "no_suffix":
                    parent["sites"] = rows[:8]
                elif kind == "no_prefix":
                    rows[0]["stage_status"] = "PENDING"
                elif kind == "unknown_stage":
                    rows[9]["stage_status"] = "RESTORED"
                elif kind == "duplicate_domain":
                    rows[9]["domain"] = rows[0]["domain"]
                elif kind == "duplicate_user":
                    rows[9]["site_user"] = rows[0]["site_user"]
                with self.assertRaises(remainder.RemainderBlocked):
                    remainder.select(parent)


class RemainderIntegrationTests(unittest.TestCase):
    def test_plan_is_local_read_only_and_no_remote_calls(self):
        parent = blocked_parent()
        with mock.patch.object(pull, "load_state", return_value=parent), \
             mock.patch.object(pull, "source_probe") as probe, \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(pull, "target_preflight_local") as preflight:
            result = pull.remainder_scope(parent["migration_id"])
        self.assertEqual(result["remaining_sites"], 9)
        probe.assert_not_called()
        save.assert_not_called()
        preflight.assert_not_called()

    def test_remainder_prepare_uses_new_scoped_state_not_parent_resume(self):
        parent = blocked_parent()
        original = copy.deepcopy(parent)
        sentinel = {"migration_id": "new-child", "status": "PREPARED"}
        with mock.patch.object(pull, "load_state", return_value=parent), \
             mock.patch.object(pull, "prepare_migration", return_value=sentinel) as prep, \
             mock.patch.object(pull, "resume_prepare_migration") as resume, \
             mock.patch.object(pull, "save_state") as save:
            value = pull.prepare_remainder(
                parent["migration_id"], "STAGE_REMAINDER:" + parent["migration_id"]
            )
        self.assertEqual(value, sentinel)
        self.assertEqual(parent, original)
        resume.assert_not_called()
        save.assert_not_called()
        self.assertEqual(prep.call_args.args[:3], (
            parent["source"],
            [f"site{i}.example.test" for i in range(9, 18)],
            "PREPARE_PULL_MIGRATION",
        ))
        self.assertEqual(prep.call_args.kwargs["remainder_parent"], parent["migration_id"])
        self.assertEqual(prep.call_args.kwargs["expected_source_identity"],
                         parent["source_server_identity"])
        self.assertEqual(
            [s["domain"] for s in prep.call_args.kwargs["expected_remainder_sites"]],
            [f"site{i}.example.test" for i in range(9, 18)],
        )

    def test_wrong_confirmation_does_not_read_or_mutate_parent(self):
        with mock.patch.object(pull, "load_state") as read, \
             mock.patch.object(pull, "prepare_migration") as prepare:
            with self.assertRaisesRegex(pull.PullMigrationError, "CONFIRMATION"):
                pull.prepare_remainder("some-id", "wrong")
        read.assert_not_called()
        prepare.assert_not_called()

    def test_child_state_is_tagged_before_any_site_import(self):
        import tempfile
        parent_id = "parent-immutable"
        plan = {"status": "READY", "source_server_identity": "source-id",
                "sites": [{"domain": "site9.example.test", "site_user": "user9"}],
                "external_assets": [], "sqlite_assets": [], "runtime_assets": {}}
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(pull, "source_probe", return_value=plan), \
                 mock.patch.object(pull, "target_preflight_local",
                                   return_value={"target_identity": "target-id"}), \
                 mock.patch.object(pull, "migration_id", return_value="child-id"), \
                 mock.patch.object(pull, "state_dir",
                                   return_value=Path(directory) / "child-id"), \
                 mock.patch.object(pull, "stage_source_runtime",
                                   return_value="/var/lib/vf-server-ops/source/runtime"), \
                 mock.patch.object(pull, "ensure_old_server_rsync",
                                   return_value={"status": "READY"}), \
                 mock.patch.object(pull, "save_state") as save, \
                 mock.patch.object(pull, "resume_prepare_migration",
                                   return_value={"status": "PREPARED"}):
                pull.prepare_migration(
                    {}, ["site9.example.test"], "PREPARE_PULL_MIGRATION",
                    remainder_parent=parent_id,
                    expected_source_identity="source-id",
                    expected_remainder_sites=plan["sites"],
                )
        child = save.call_args.args[0]
        self.assertEqual(child["partial_parent_migration_id"], parent_id)
        self.assertIs(child["cutover_prohibited"], True)
        self.assertIs(child["existing_target_overwrite_allowed"], False)
        self.assertIs(child["source_runtime_frozen"], False)
        self.assertEqual(child["sites"][0]["stage_status"], "PENDING")

    def test_source_identity_drift_stops_before_target_preflight_or_state_write(self):
        with mock.patch.object(pull, "source_probe", return_value={
            "status": "READY", "source_server_identity": "different",
        }), mock.patch.object(pull, "target_preflight_local") as target, \
             mock.patch.object(pull, "save_state") as save:
            with self.assertRaisesRegex(pull.PullMigrationError, "SOURCE_SERVER_CHANGED"):
                pull.prepare_migration(
                    {}, ["site9.example.test"], "PREPARE_PULL_MIGRATION",
                    remainder_parent="parent-id",
                    expected_source_identity="expected",
                )
        target.assert_not_called()
        save.assert_not_called()

    def test_partial_child_cutover_is_hard_blocked_before_side_effects(self):
        for field, value in (("partial_parent_migration_id", "parent-id"),
                             ("cutover_prohibited", True)):
            with self.subTest(field=field):
                state = {"status": "PREPARED", field: value}
                with mock.patch.object(pull, "load_state", return_value=state), \
                     mock.patch.object(pull, "require_mariadb_target") as engine, \
                     mock.patch.object(pull, "save_state") as save, \
                     mock.patch.object(pull, "freeze_old_server") as freeze:
                    with self.assertRaisesRegex(pull.PullMigrationError, "PARTIAL_REMAINDER"):
                        pull.cutover_migration("child-id", "CUTOVER_PULL:child-id")
                engine.assert_not_called()
                save.assert_not_called()
                freeze.assert_not_called()

    def test_cli_remainder_plan_is_available_without_remote_writes(self):
        parent = blocked_parent()
        with mock.patch.object(pull, "load_state", return_value=parent), \
             mock.patch.object(pull, "source_probe") as probe, \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(sys, "argv", ["server_migration_pull.py", "remainder-plan",
                                           "--migration-id", parent["migration_id"]]):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(pull.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["remaining_sites"], 9)
        probe.assert_not_called()
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
