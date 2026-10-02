#!/usr/bin/env python3
import json
import pathlib
import re
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

    def test_toolbox_has_five_visible_items(self):
        self.assertEqual(self.data["project"]["toolbox_visible_items"], 5)
        self.assertEqual(
            self.data["slots"][2]["server_initialization_contract"],
            "STANDALONE_TOP_LEVEL_YN_V1",
        )

    def test_public_entry_is_single_toolbox(self):
        self.assertTrue(self.data["project"]["public_entry"].endswith("/installers/p07-toolbox.sh"))

    def test_slot1_network_node_is_routed(self):
        s = self.data["slots"][0]
        self.assertEqual(s["internal_version"], "0.1.0-rc10")
        self.assertEqual(s["integration_state"], "PUBLIC_DISTRIBUTED")

    def test_slot2_vps_audit_is_exact_pinned(self):
        s = self.data["slots"][1]
        self.assertEqual(s["internal_version"], "2.2.2-rc2-chinese-first")
        self.assertEqual(s["installer_mode"], "PINNED_EXACT_SCRIPT")
        self.assertEqual(s["public_version"], "V2.2.2")
        self.assertEqual(len(s["sha256"]), 64)
        self.assertIn("machine_performance_verdict", s["capabilities"])
        self.assertIn("cloudpanel_wordpress_fit", s["capabilities"])
        self.assertIn("visible_reference_lines", s["capabilities"])
        self.assertIn("reference_cli", s["capabilities"])
        self.assertIn("semantic_terminal_colors", s["capabilities"])
        self.assertIn("pty_color_preservation", s["capabilities"])

    def test_slot3_matches_current_published_distribution(self):
        s = self.data["slots"][2]
        release = self.data["release"]
        self.assertEqual(s["internal_version"], release["slot3_build"])
        self.assertEqual(s["source_main_commit"], release["slot3_source_main_commit"])
        self.assertEqual(s["integration_state"], "RELEASED_TO_PUBLIC_MAIN")
        self.assertEqual(s["terminal_ui_color_system"], "CANONICAL_V1")
        self.assertEqual(
            s["full_server_migration_integration_commit"],
            "5c447fc99030f75c098934ddb9aa300b934564bb",
        )

    def test_slot4_rc20_is_publicly_distributed(self):
        s = self.data["slots"][3]
        self.assertEqual(s["internal_version"], "0.1.0-rc20")
        self.assertEqual(s["integration_state"], "PUBLIC_DISTRIBUTED")

    def test_beginner_public_names_hide_project_code(self):
        self.assertEqual(self.data["project"]["public_ui_name"], "服务器工具箱")
        self.assertTrue(self.data["project"]["user_facing_project_code_hidden"])
        self.assertEqual(self.data["slots"][2]["name"], "网站与数据")
        self.assertEqual(self.data["slots"][3]["name"], "服务器维护与安全")
        self.assertEqual(
            self.data["slots"][2]["beginner_naming_contract"],
            "BEGINNER_PURPOSE_FIRST_NO_PROJECT_CODE_V1",
        )
        self.assertEqual(
            self.data["slots"][2]["website_management_contract"],
            "GROUPED_SITE_TOOLS_ROLE_CLEAR_V2",
        )
        self.assertEqual(
            self.data["slots"][2]["migration_dependency_contract"],
            "LAZY_ONLY_AFTER_ACTION_SELECT_V1",
        )
        self.assertEqual(
            self.data["release"]["release29_distribution_status"],
            "PASS",
        )

    def test_release_is_published(self):
        release = self.data["release"]
        self.assertEqual(self.data["release_blockers"], [])
        self.assertEqual(release["tag"], "p07-v0.1.0")
        self.assertEqual(release["status"], "PUBLISHED")
        self.assertRegex(release["slot3_build"], r"^0\.1\.0-release[0-9]+$")
        self.assertEqual(release["slot3_distribution"], "PUBLIC_MAIN")
        self.assertEqual(
            release["public_distribution_commit"],
            release["current_public_main_commit"],
        )
        self.assertRegex(release["public_distribution_commit"], r"^[0-9a-f]{40}$")

    def test_production_build_has_independent_owner_verified_evidence(self):
        p = self.data["production"]
        match = re.fullmatch(r"0\.1\.0-release([0-9]+)", p["slot3_build"])
        self.assertIsNotNone(match)
        install_key = f"release{match.group(1)}_install_status"
        self.assertIn(install_key, p)
        self.assertIn("OWNER_VERIFIED", p[install_key])
        self.assertFalse(p["migration_executed"])
        self.assertFalse(p["dns_write"])
        self.assertFalse(p["source_delete"])

    def test_safety_boundaries(self):
        safety = self.data["safety"]
        self.assertFalse(safety["automatic_dns_mutation"])
        self.assertFalse(safety["automatic_source_delete"])
        self.assertFalse(safety["resource_safe_apply_auto_run"])

if __name__ == "__main__":
    unittest.main()
