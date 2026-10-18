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
        self.assertEqual(s["internal_version"], "0.1.0-rc13")
        self.assertEqual(s["installer_blob"], "f09997b9bc2178dfc0aeceb6c7c53564ebe54fb3")
        self.assertEqual(s["integration_state"], "PUBLIC_DISTRIBUTED")

    def test_slot2_vps_audit_is_exact_pinned(self):
        s = self.data["slots"][1]
        self.assertEqual(s["internal_version"], "2.1.0-rc7-field")
        self.assertEqual(s["installer_mode"], "PINNED_EXACT_SCRIPT")
        self.assertEqual(s["public_version"], "V2.1.0")
        self.assertIn("p07-vps-audit-v21.sh", s["source_url"])
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

    def test_slot4_current_system_care_is_publicly_distributed(self):
        s = self.data["slots"][3]
        self.assertEqual(s["internal_version"], "0.1.0-rc56")
        self.assertEqual(s["installer_blob"], "6cd0cdf36d8b2384b553793e0ef1006221c052d5")
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
            "GROUPED_SITE_TOOLS_SINGLE_LINE_TWO_COLUMN_V4",
        )
        self.assertEqual(
            self.data["slots"][2]["migration_dependency_contract"],
            "LAZY_ONLY_AFTER_ACTION_SELECT_V1",
        )
        self.assertEqual(
            self.data["release_history"]["release32"]["release29_distribution_status"],
            "PASS",
        )
        self.assertEqual(self.data["release_history"]["release32"]["kind"], "HISTORICAL_SNAPSHOT_NOT_CURRENT")

    def test_release_is_published(self):
        release = self.data["release"]
        self.assertEqual(self.data["release_blockers"], [])
        self.assertEqual(release["tag"], "p07-v0.1.0-release87-security-hardening")
        self.assertEqual(release["status"], "PUBLISHED")
        self.assertRegex(release["slot3_build"], r"^0\.1\.0-release[0-9]+$")
        self.assertEqual(release["slot3_distribution"], "PUBLIC_MAIN")
        self.assertNotIn("current_public_main_commit", release)
        current_build = (ROOT / "BUILD_ID").read_text(encoding="utf-8").strip()
        self.assertNotIn("candidate", self.data)
        # Release87 is publicly published; release86 is historical.
        self.assertEqual(current_build, "0.1.0-release87")
        self.assertEqual(release["slot3_build"], current_build)
        self.assertEqual(self.data["release_history"]["release86"]["slot3_build"], "0.1.0-release86")
        self.assertEqual(self.data["release_history"]["release85"]["slot3_build"], "0.1.0-release85")
        self.assertEqual(release["system_care_build"], self.data["slots"][3]["internal_version"])
        self.assertEqual(release["new_vps_mariadb_1011_owner_real"], "NOT_RUN")
        self.assertEqual(release["cross_engine_mysql_to_mariadb_real"], "NOT_RUN")
        self.assertRegex(release["public_distribution_commit"], r"^[0-9a-f]{40}$")

    def test_production_build_has_independent_owner_verified_evidence(self):
        p = self.data["production"]
        self.assertEqual(p["record_kind"], "HISTORICAL_SNAPSHOT_NOT_CURRENT")
        self.assertIn("2026-09-29", p["applies_to"])
        self.assertEqual(self.data["owner_real_evidence"]["release87_new_vps_mariadb_1011"], "NOT_RUN")
        match = re.fullmatch(r"0\.1\.0-release([0-9]+)", p["slot3_build"])
        self.assertIsNotNone(match)
        install_key = f"release{match.group(1)}_install_status"
        self.assertIn(install_key, p)
        self.assertIn("OWNER_VERIFIED", p[install_key])
        self.assertFalse(p["migration_executed"])
        self.assertFalse(p["dns_write"])
        self.assertFalse(p["source_delete"])

    def test_release_snapshot_has_provenance_without_fake_live_head(self):
        release = self.data["release"]
        self.assertRegex(release["slot3_source_main_commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(release["public_distribution_commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(release["runtime_manifest_blob"], r"^[0-9a-f]{40}$")
        self.assertRegex(release["overlay_manifest_blob"], r"^[0-9a-f]{40}$")
        self.assertNotIn("current_public_main_commit", release)
        self.assertEqual(self.data["project"]["toolbox_visible_items"], 5)
        self.assertEqual(self.data["release_history"]["release32"]["slot3_build"], "0.1.0-release32")
        self.assertEqual(self.data["release_history"]["release85"]["kind"], "HISTORICAL_SNAPSHOT_NOT_CURRENT")

    def test_readme_renders_five_live_menu_entries_and_no_retired_current_claim(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for label in ("网络代理节点", "服务器性能检测", "网站与数据",
                      "服务器维护与安全", "新服务器初始化"):
            self.assertIn(label, readme)
        for build in ("0.1.0-rc13", "2.1.0-rc7-field",
                      "0.1.0-release87", "0.1.0-rc56"):
            self.assertIn(build, readme)
        self.assertIn("NOT_RUN", readme)
        self.assertNotIn("当前正式版本：`V0.1.0`。\\n\\n## 唯一入口", readme)
        self.assertNotIn("当前 Owner Test Candidate", readme)

    def test_owner_acceptance_does_not_transfer_release68_real_to_mariadb(self):
        acceptance = (ROOT / "docs/authority/USER_ACCEPTANCE.md").read_text(encoding="utf-8")
        matrix = (ROOT / "docs/authority/ACCEPTANCE_MATRIX.md").read_text(encoding="utf-8")
        self.assertIn("release87 MariaDB", acceptance)
        self.assertIn("NOT_RUN", acceptance)
        self.assertIn("## Historical guided-init16 acceptance layer", matrix)
        self.assertIn("HISTORICAL_OWNER_REAL_PASS_FOR_EXACT_SOURCE", matrix)
        self.assertIn("MACHINE_PASS / OWNER_REAL_PARTIAL", matrix)
        self.assertEqual(self.data["release"]["system_care_real_mutation_ci"], "MACHINE_PASS_2026-10-17")

    def test_safety_boundaries(self):
        safety = self.data["safety"]
        self.assertFalse(safety["automatic_dns_mutation"])
        self.assertFalse(safety["automatic_source_delete"])
        self.assertFalse(safety["resource_safe_apply_auto_run"])

if __name__ == "__main__":
    unittest.main()
