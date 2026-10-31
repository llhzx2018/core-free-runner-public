"""Synthetic-only: a failed parent never silently stages wrong remaining sites."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import server_migration_pull as pull
from tests.test_migration_remainder import blocked_parent


def site(number: int) -> dict:
    return {
        "domain": f"site{number}.example.test",
        "site_user": f"user{number}",
        "site_root": f"/home/user{number}/htdocs/site{number}.example.test",
        "document_root": f"/home/user{number}/htdocs/site{number}.example.test/public",
        "mysql_databases": [f"site_{number}_db"],
        "runtime": {"type": "php", "version": "8.3", "app_port": None},
    }


class ExactRemainderIdentityTests(unittest.TestCase):
    def setUp(self):
        self.old = [site(i) for i in range(9, 18)]
        self.domains = [entry["domain"] for entry in self.old]
        self.fresh = deepcopy(self.old)

    def test_exact_site_inventory_passes_and_no_mutation(self):
        snapshot = json.dumps(self.old, sort_keys=True)
        pull.require_remainder_exact_source_scope(self.old, self.fresh, self.domains)
        self.assertEqual(json.dumps(self.old, sort_keys=True), snapshot)
        self.assertEqual(self.fresh, self.old)

    def test_each_structural_or_database_identity_drift_blocks(self):
        for key, value in (
            ("site_user", "other-user"),
            ("site_root", "/home/other/path"),
            ("document_root", "/home/other/public"),
            ("mysql_databases", ["different_db"]),
            ("runtime", {"type": "php", "version": "8.2"}),
        ):
            with self.subTest(field=key):
                fresh = deepcopy(self.old)
                fresh[2][key] = value
                with self.assertRaisesRegex(pull.PullMigrationError,
                                            "REMAINDER_SOURCE_SITE_STRUCTURE_CHANGED"):
                    pull.require_remainder_exact_source_scope(self.old, fresh,
                                                              self.domains)

    def test_missing_duplicate_extra_reordered_and_blocked_site_are_refused(self):
        attacks = []
        attacks.append(self.fresh[:8])
        attacks.append(self.fresh + [site(18)])
        swapped = deepcopy(self.fresh)
        swapped[0], swapped[1] = swapped[1], swapped[0]
        attacks.append(swapped)
        injected = deepcopy(self.fresh)
        injected[0] = site(8)
        attacks.append(injected)
        duplicate = deepcopy(self.fresh)
        duplicate[4] = deepcopy(duplicate[3])
        attacks.append(duplicate)
        for attack in attacks:
            with self.subTest(length=len(attack)):
                with self.assertRaises(pull.PullMigrationError):
                    pull.require_remainder_exact_source_scope(
                        self.old, attack, self.domains)

    def test_required_parent_snapshot_must_exist(self):
        for missing in (None, [], {}, "sample"):
            with self.subTest(kind=type(missing).__name__):
                with self.assertRaisesRegex(pull.PullMigrationError,
                                            "REMAINDER_SOURCE_SCOPE_UNPROVEN"):
                    pull.require_remainder_exact_source_scope(
                        missing, self.fresh, self.domains)

    def test_drift_blocks_before_local_preflight_or_any_target_writes(self):
        bad = deepcopy(self.fresh)
        bad[0]["mysql_databases"] = ["unexpected_business_database"]
        parent = blocked_parent()
        with (
            mock.patch.object(pull, "source_probe",
                              return_value={"source_server_identity": "same",
                                            "sites": bad}) as probe,
            mock.patch.object(pull, "target_preflight_local") as preflight,
            mock.patch.object(pull, "stage_source_runtime") as stage,
            mock.patch.object(pull, "save_state") as save,
            mock.patch.object(pull, "create_target_site") as create,
            mock.patch.object(pull, "sync_site_databases") as db,
        ):
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "REMAINDER_SOURCE_SITE_STRUCTURE_CHANGED",
            ):
                pull.prepare_migration(
                    parent["source"], self.domains, "PREPARE_PULL_MIGRATION",
                    remainder_parent=parent["migration_id"],
                    expected_source_identity="same",
                    expected_remainder_sites=self.old,
                )
            probe.assert_called_once()
            for action in (preflight, stage, save, create, db):
                action.assert_not_called()

    def test_no_parent_reference_cannot_forge_remainder_snapshot(self):
        with (
            mock.patch.object(pull, "source_probe",
                              return_value={"source_server_identity": "same",
                                            "sites": deepcopy(self.fresh)}),
            mock.patch.object(pull, "target_preflight_local") as preflight,
        ):
            with self.assertRaisesRegex(
                pull.PullMigrationError, "REMAINDER_SCOPE_WITHOUT_PARENT_REFUSED",
            ):
                pull.prepare_migration(
                    {}, self.domains, "PREPARE_PULL_MIGRATION",
                    expected_remainder_sites=self.old,
                )
            preflight.assert_not_called()


if __name__ == "__main__":
    unittest.main()
