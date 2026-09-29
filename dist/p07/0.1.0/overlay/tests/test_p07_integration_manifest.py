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
        self.assertEqual(self.data["project"]["release_state"], "RELEASED")

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
        self.assertEqual(s["internal_version"], "2.2.2-rc1-semantic-color")
        self.assertEqual(s["installer_mode"], "PINNED_EXACT_SCRIPT")
        self.assertEqual(s["public_version"], "V2.2.2")
        self.assertEqual(len(s["sha256"]), 64)
        self.assertIn("semantic_terminal_colors", s["capabilities"])
        self.assertIn("pty_color_preservation", s["capabilities"])

    def test_slot3_release3_is_public_distribution_candidate(self):
        s = self.data["slots"][2]
        self.assertEqual(s["internal_version"], "0.1.0-release3")
        self.assertEqual(s["integration_state"], "RELEASE_CANDIDATE_FOR_PUBLIC_MAIN")
        self.assertEqual(s["source_main_commit"], "424b539b331236d85a35b310943b810046be0927")
        self.assertEqual(s["terminal_ui_color_system"], "CANONICAL_V1")
        self.assertEqual(s["full_server_migration_integration_commit"], "5c447fc99030f75c098934ddb9aa300b934564bb")

    def test_slot4_rc16_is_publicly_distributed(self):
        s = self.data["slots"][3]
        self.assertEqual(s["internal_version"], "0.1.0-rc16")
        self.assertEqual(s["integration_state"], "PUBLIC_DISTRIBUTED")

    def test_release_stays_v010_while_slot3_build_advances(self):
        self.assertEqual(self.data["release_blockers"], [])
        self.assertEqual(self.data["release"]["tag"], "p07-v0.1.0")
        self.assertEqual(self.data["release"]["status"], "PUBLISHED")
        self.assertEqual(self.data["release"]["slot3_build"], "0.1.0-release3")

    def test_production_is_not_claimed_upgraded_before_owner_verification(self):
        p = self.data["production"]
        self.assertEqual(p["slot3_build"], "0.1.0-release1")
        self.assertEqual(p["release3_install_status"], "NOT_YET_OWNER_VERIFIED")

    def test_safety_boundaries(self):
        safety = self.data["safety"]
        self.assertFalse(safety["automatic_dns_mutation"])
        self.assertFalse(safety["automatic_source_delete"])
        self.assertFalse(safety["resource_safe_apply_auto_run"])

if __name__ == "__main__":
    unittest.main()
