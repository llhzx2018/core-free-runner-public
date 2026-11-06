"""Three-task business assets: do not conflate staging receipts with final transfer."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_chain_asset_audit as audit
import migration_chain_consolidation as chain
from tests.test_migration_chain_consolidation import full_three_tasks


def prepared():
    a, b, tail = full_three_tasks()
    plan = chain.consolidate(a, b, tail)
    owners = {
        record["domain"]: record["origin_migration_id"]
        for record in plan["sites"]
    }
    for task in (a, b, tail):
        task["external_assets"] = []
        task["sqlite_assets"] = []
        task["runtime_assets"] = {
            "system_cron": [], "user_cron": [], "pm2": [],
        }
        task["pending_system_cron"] = []
        task["pending_user_cron"] = []
        task["pending_pm2"] = []
        task["source_http_baseline_required"] = True
        task["source_http_baseline"] = {
            domain: {"status": "PASS", "http_code": "200"}
            for domain, mid in owners.items()
            if mid == task["migration_id"]
        }
        task["source_external_listeners"] = []
    return a, b, tail, plan


class ChainAssetsTests(unittest.TestCase):
    def test_missing_assets_are_reported_not_forged(self):
        a, b, tail = full_three_tasks()
        before = copy.deepcopy((a, b, tail))
        plan = chain.consolidate(a, b, tail)
        result = audit.audit(a, b, tail, plan)
        self.assertEqual(result["status"], "REQUIRES_ASSET_RECONCILIATION")
        self.assertIn("ASSET_INVENTORY_UNAVAILABLE", result["blockers"])
        self.assertIn("SOURCE_HTTP_BASELINE_UNVERIFIED", result["blockers"])
        self.assertIn("RUNTIME_INVENTORY_UNAVAILABLE", result["blockers"])
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["source_freeze_allowed"])
        self.assertFalse(result["writes_performed"])
        self.assertEqual((a, b, tail), before)

    def test_provenance_coverage_can_be_structurally_valid_but_not_final_proof(self):
        a, b, tail, plan = prepared()
        result = audit.audit(a, b, tail, plan)
        self.assertEqual(result["site_count"], 17)
        self.assertEqual(result["source_task_count"], 3)
        self.assertEqual(result["status"], "STRUCTURAL_CONSISTENT_NOT_FINAL_VERIFIED")
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["counts"]["unproven_baselines"], 0)
        self.assertFalse(result["source_live_snapshot_proved"])
        self.assertFalse(result["file_hashes_proved"])
        self.assertFalse(result["sqlite_final_snapshot_proved"])
        self.assertFalse(result["runtime_stage_reusable"])
        self.assertFalse(result["cutover_allowed"])

    def test_same_external_and_sqlite_path_deduplicates_only_identical_metadata(self):
        a, b, tail, plan = prepared()
        for task in (a, b, tail):
            task["external_assets"] = [{"path": "/home/shared/files", "kind": "DIRECTORY"}]
            task["sqlite_assets"] = [{"path": "/home/shared/data.sqlite"}]
        result = audit.audit(a, b, tail, plan)
        self.assertEqual(result["status"], "STRUCTURAL_CONSISTENT_NOT_FINAL_VERIFIED")
        self.assertEqual(result["counts"]["external_paths"], 1)
        self.assertEqual(result["counts"]["sqlite_paths"], 1)
        self.assertEqual(result["counts"]["duplicate_compatible_external"], 2)
        self.assertEqual(result["counts"]["duplicate_compatible_sqlite"], 2)
        tail["external_assets"][0]["kind"] = "FILE"
        tail["sqlite_assets"][0]["format"] = "unknown"
        bad = audit.audit(a, b, tail, plan)
        self.assertIn("ASSET_PATH_METADATA_CONFLICT", bad["blockers"])
        self.assertEqual(bad["status"], "REQUIRES_ASSET_RECONCILIATION")
        self.assertFalse(bad["cutover_allowed"])

    def test_cron_conflict_or_duplicate_staging_cannot_be_reused(self):
        a, b, tail, plan = prepared()
        for task in (a, b):
            task["runtime_assets"]["user_cron"] = [
                {"path": "/var/spool/cron/crontabs/admin", "user": "admin"}
            ]
            task["pending_user_cron"] = [
                {"user": "admin", "source_path": "/var/spool/cron/crontabs/admin",
                 "staged_target": "/tmp/one.cron", "activated": False}
            ]
        result = audit.audit(a, b, tail, plan)
        self.assertIn("RUNTIME_RESTAGING_REQUIRED", result["blockers"])
        self.assertEqual(result["counts"]["duplicate_compatible_runtime"], 1)
        self.assertFalse(result["runtime_stage_reusable"])
        b["runtime_assets"]["user_cron"][0]["path"] = "/other"
        b["pending_user_cron"][0]["activated"] = True
        changed = audit.audit(a, b, tail, plan)
        self.assertIn("RUNTIME_STAGING_UNVERIFIED", changed["blockers"])

    def test_pending_stage_missing_and_http_baseline_missing_are_blockers(self):
        a, b, tail, plan = prepared()
        a["runtime_assets"]["system_cron"] = [{"path": "/etc/cron.d/checker"}]
        b["source_http_baseline"].pop("unzip.kewaro.com", None)
        r = audit.audit(a, b, tail, plan)
        self.assertIn("RUNTIME_STAGING_COUNT_MISMATCH", r["blockers"])
        self.assertIn("SOURCE_HTTP_BASELINE_UNVERIFIED", r["blockers"])
        self.assertEqual(r["counts"]["unproven_baselines"], 1)
        self.assertFalse(r["cutover_allowed"])

    def test_locked_candidate_exposes_structural_blockers_without_secrets(self):
        a, b, tail, plan = prepared()
        tail["source_http_baseline"].pop("www3.m3u8.one")
        local = {
            "schema": "P07_17_SITE_LOCAL_OWNERSHIP_EVIDENCE_V1",
            "status": "LOCAL_MARKERS_AND_APP_BINDINGS_ONLY_NOT_CUTOVER_READY",
            "site_count": 17, "database_count": 3,
            "contract_sha256": plan["site_contract_sha256"],
            "local_target_identity_match": True,
            "all_migration_markers_owned": True,
            "all_database_app_bindings_checked": True,
            "cutover_allowed": False,
        }
        with mock.patch.object(
            chain, "local_target_marker_proof", return_value=local,
        ):
            locked = chain.build_locked_execution_candidate(
                a, b, tail,
                proposed_migration_id="pull-20261101T160000Z-cafe2026",
                local_target_identity="sha256:cp2",
            )
        self.assertEqual(locked["asset_audit"]["status"],
                         "REQUIRES_ASSET_RECONCILIATION")
        self.assertIn("SOURCE_HTTP_BASELINE_UNVERIFIED",
                      locked["asset_audit"]["blockers"])
        self.assertFalse(locked["cutover_allowed"])
        self.assertFalse(locked["all_source_http_baselines_fresh"])
        self.assertNotIn("/home/", str(locked["asset_audit"]))


if __name__ == "__main__":
    unittest.main()
