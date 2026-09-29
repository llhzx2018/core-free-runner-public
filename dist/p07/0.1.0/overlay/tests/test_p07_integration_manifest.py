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
        self.assertEqual(self.data["project"]["user_interface_language"], "zh-CN-first")

    def test_exactly_four_top_level_slots(self):
        slots = self.data["slots"]
        self.assertEqual([s["slot"] for s in slots], [1, 2, 3, 4])
        self.assertEqual(len(slots), 4)

    def test_public_entry_is_single_toolbox(self):
        self.assertTrue(self.data["project"]["public_entry"].endswith("/installers/p07-toolbox.sh"))

    def test_slot1_network_node_is_chinese_first_and_distributed(self):
        s = self.data["slots"][0]
        self.assertEqual(s["internal_version"], "0.1.0-rc10")
        self.assertEqual(s["integration_state"], "PUBLIC_DISTRIBUTED")
        self.assertEqual(s["terminal_ui_language"], "ZH_FIRST_V1")

    def test_slot2_vps_audit_is_chinese_first_exact_pinned(self):
        s = self.data["slots"][1]
        self.assertEqual(s["internal_version"], "2.2.2-rc2-chinese-first")
        self.assertEqual(s["installer_mode"], "PINNED_EXACT_SCRIPT")
        self.assertEqual(s["public_version"], "V2.2.2")
        self.assertEqual(len(s["sha256"]), 64)
        self.assertEqual(s["terminal_ui_language"], "ZH_FIRST_V1")
        self.assertIn("semantic_terminal_colors", s["capabilities"])
        self.assertIn("pty_color_preservation", s["capabilities"])

    def test_slot3_release5_global_chinese_candidate(self):
        s = self.data["slots"][2]
        self.assertEqual(s["internal_version"], "0.1.0-release5")
        self.assertEqual(s["integration_state"], "RELEASE_CANDIDATE_FOR_PUBLIC_MAIN")
        self.assertEqual(s["source_main_commit"], "eaed2a423cfec7bcf4e57b3aa0d38c6db610606e")
        self.assertEqual(s["terminal_ui_color_system"], "CANONICAL_V1")
        self.assertEqual(s["terminal_ui_language"], "ZH_FIRST_V2_GLOBAL_P07")
        self.assertEqual(s["install_mode"], "CURRENT_RUNTIME_LAZY_V1")

    def test_slot4_rc17_is_chinese_first_and_distributed(self):
        s = self.data["slots"][3]
        self.assertEqual(s["internal_version"], "0.1.0-rc17")
        self.assertEqual(s["integration_state"], "PUBLIC_DISTRIBUTED")
        self.assertEqual(s["terminal_ui_language"], "ZH_FIRST_V1")

    def test_release_stays_v010_while_slot3_build_advances(self):
        self.assertEqual(self.data["release_blockers"], [])
        self.assertEqual(self.data["release"]["tag"], "p07-v0.1.0")
        self.assertEqual(self.data["release"]["status"], "PUBLISHED")
        self.assertEqual(self.data["release"]["slot3_build"], "0.1.0-release5")

    def test_production_is_not_claimed_upgraded_before_owner_verification(self):
        p = self.data["production"]
        self.assertEqual(p["slot3_build"], "0.1.0-release3")
        self.assertEqual(p["release3_install_status"], "OWNER_VERIFIED")
        self.assertEqual(p["release5_install_status"], "NOT_YET_OWNER_VERIFIED")

    def test_safety_boundaries(self):
        safety = self.data["safety"]
        self.assertFalse(safety["automatic_dns_mutation"])
        self.assertFalse(safety["automatic_source_delete"])
        self.assertFalse(safety["resource_safe_apply_auto_run"])

if __name__ == "__main__":
    unittest.main()
