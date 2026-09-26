#!/usr/bin/env python3
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "authority" / "P07_INTEGRATION_MANIFEST.json"

class P07IntegrationManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_single_product_identity(self):
        self.assertEqual(self.data["project"]["id"], "P07")
        self.assertEqual(self.data["project"]["public_version"], "V0.1.0")
        self.assertEqual(self.data["project"]["release_state"], "FINAL_RELEASE_CANDIDATE")

    def test_exactly_four_top_level_slots(self):
        slots = self.data["slots"]
        self.assertEqual([s["slot"] for s in slots], [1, 2, 3, 4])
        self.assertEqual(len(slots), 4)

    def test_public_entry_is_single_toolbox(self):
        self.assertTrue(self.data["project"]["public_entry"].endswith("/installers/p07-toolbox.sh"))

    def test_slot1_network_node_is_routed(self):
        s = self.data["slots"][0]
        self.assertEqual(s["internal_version"], "0.1.0-rc9")
        self.assertEqual(s["integration_state"], "ROUTED")

    def test_slot2_vps_audit_is_exact_pinned(self):
        s = self.data["slots"][1]
        self.assertEqual(s["internal_version"], "2.1.0-rc7-field")
        self.assertEqual(s["installer_mode"], "PINNED_EXACT_SCRIPT")
        self.assertEqual(len(s["sha256"]), 64)

    def test_slot3_contains_full_server_migration_candidate(self):
        s = self.data["slots"][2]
        self.assertEqual(s["integration_state"], "FINAL_RELEASE_CANDIDATE")
        self.assertEqual(s["full_server_migration_integration_commit"], "5c447fc99030f75c098934ddb9aa300b934564bb")
        self.assertEqual(s["internal_version"], "0.1.0-release1")

    def test_slot4_rc15_is_integrated(self):
        s = self.data["slots"][3]
        self.assertEqual(s["internal_version"], "0.1.0-rc15")
        self.assertEqual(s["integration_state"], "PRODUCTION_INSTALLED")

    def test_release_is_not_prematurely_claimed(self):
        self.assertIn("FINAL_PUBLIC_DISTRIBUTION_GATE", self.data["release_blockers"])
        self.assertIn("FORMAL_TAG_RELEASE", self.data["release_blockers"])

    def test_safety_boundaries(self):
        safety = self.data["safety"]
        self.assertFalse(safety["automatic_dns_mutation"])
        self.assertFalse(safety["automatic_source_delete"])
        self.assertFalse(safety["resource_safe_apply_auto_run"])

if __name__ == "__main__":
    unittest.main()
