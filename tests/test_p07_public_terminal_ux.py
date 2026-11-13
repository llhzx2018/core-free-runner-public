"""P07 public Toolbox UX V3 PR machine guard: positive and negative fixtures only."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_p07_public_terminal_ux as ux


class PublicTerminalUXV3Tests(unittest.TestCase):
    def setUp(self):
        ux.load_and_check()

    def test_public_toolbox_and_module_ownership(self):
        self.assertEqual(ux.source_owner("installers/p07-toolbox.sh"), "P07-TOOLBOX")
        self.assertEqual(ux.source_owner("installers/vf-node.sh"), "P07-M01")
        self.assertEqual(ux.source_owner("installers/p07-vpscheck.sh"), "P07-M02")
        self.assertEqual(ux.source_owner("experiments/p07-vps-audit-v227-r1.sh"), "P07-M02")
        self.assertEqual(ux.source_owner("installers/p07.sh"), "P07-M03")
        self.assertEqual(ux.source_owner("installers/p07-system-care.sh"), "P07-M04")

    def test_no_user_visible_change_requires_no_extra_review(self):
        self.assertEqual(ux.validate_pr(
            ["installers/p07-toolbox.sh"],
            {"installers/p07-toolbox.sh": 'M05_BUILD_EXPECTED="0.1.0-test"'}),
            "P07_PUBLIC_UI_CHANGE=N_A")
        self.assertEqual(ux.validate_pr(
            ["docs/authority/P07_TERMINAL_UX_ADOPTION.md"], {}),
            "P07_PUBLIC_UI_CHANGE=N_A")

    def test_user_facing_change_without_review_fails(self):
        with self.assertRaisesRegex(ux.PublicUXError, "缺少 UX PR 证据"):
            ux.validate_pr(
                ["installers/p07-toolbox.sh"],
                {"installers/p07-toolbox.sh": 'say "请选择功能 [0-5]："'},
            )
        with self.assertRaisesRegex(ux.PublicUXError, "缺少 UX PR 证据"):
            ux.validate_pr(
                ["installers/vf-node.sh"], {"installers/vf-node.sh": 'printf "菜单\\n"'})

    def test_unregistered_public_menu_is_blocked(self):
        with self.assertRaisesRegex(ux.PublicUXError, "未登记 UI 模块归属"):
            ux.source_owner("installers/p07-new-menu.sh")

    def fixtures(self, directory):
        root = Path(directory)
        files = [
            ux.DOC, ux.WORKFLOW, "AGENTS.md", *ux.PUBLIC_ROUTES,
            "tests/test_p07_public_terminal_ux.py",
        ]
        for file in files:
            dest = root / file
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / file, dest)
        return root

    def valid_review(self):
        return {
            "schema": "vf.p07.public-ux-review.v1",
            "module_id": "P07-TOOLBOX",
            "reference": "redhat-nmtui",
            "production_run": False,
            "changed_surfaces": ["installers/p07-toolbox.sh"],
            "scenario_tests": {
                scenario: {
                    "file": "tests/test_p07_public_terminal_ux.py",
                    "test": "test_public_toolbox_and_module_ownership",
                } for scenario in ux.SCENARIOS
            },
        }

    def test_complete_review_accepts_structural_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.fixtures(temp)
            ux.load_and_check(root)
            review = root / "docs/ux-reviews/p07-toolbox.json"
            review.parent.mkdir(parents=True, exist_ok=True)
            review.write_text(json.dumps(self.valid_review(), ensure_ascii=False),
                              encoding="utf-8")
            result = ux.validate_pr(
                ["installers/p07-toolbox.sh", "docs/ux-reviews/p07-toolbox.json"],
                {"installers/p07-toolbox.sh": 'say "请选择功能 [0-5]："'},
                root,
            )
            self.assertIn("STRUCTURAL_PASS", result)

    def test_missing_seventh_scenario_and_fake_test_function_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.fixtures(temp)
            review = root / "docs/ux-reviews/p07-toolbox.json"
            review.parent.mkdir(parents=True, exist_ok=True)
            data = self.valid_review()
            data["scenario_tests"].pop("no_color_non_tty")
            review.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            changed = ["installers/p07-toolbox.sh", "docs/ux-reviews/p07-toolbox.json"]
            text = {"installers/p07-toolbox.sh": 'printf "菜单\\n"'}
            with self.assertRaisesRegex(ux.PublicUXError, "七场景"):
                ux.validate_pr(changed, text, root)
            data = self.valid_review()
            data["scenario_tests"]["readonly"]["test"] = "test_nonexistent_method"
            review.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ux.PublicUXError, "测试函数缺失"):
                ux.validate_pr(changed, text, root)

    def test_actual_m01_m04_module_package_menus_are_checked(self):
        self.assertEqual(ux.source_owner(
            "packages/p07-network-node/0.1.0-ux1/vf-node.sh"), "P07-M01")
        self.assertEqual(ux.source_owner(
            "packages/p07-system-care/0.1.0-ux1/vf-system-care.sh"), "P07-M04")
        with self.assertRaisesRegex(ux.PublicUXError, "缺少 UX PR 证据"):
            ux.validate_pr(
                ["packages/p07-network-node/0.1.0-ux1/vf-node.sh"],
                {"packages/p07-network-node/0.1.0-ux1/vf-node.sh":
                    'say "请选择节点操作"'})
        with self.assertRaisesRegex(ux.PublicUXError, "缺少 UX PR 证据"):
            ux.validate_pr(
                ["packages/p07-system-care/0.1.0-ux1/vf-system-care.sh"],
                {"packages/p07-system-care/0.1.0-ux1/vf-system-care.sh":
                    'ui_menu_info 1 "查看服务器状态"'})

    def test_package_glob_removed_from_ci_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.fixtures(temp)
            wf = root / ux.WORKFLOW
            script = wf.read_text(encoding="utf-8")
            self.assertIn("packages/p07-network-node/**/vf-node.sh", script)
            self.assertIn("packages/p07-system-care/**/vf-system-care.sh", script)
            wf.write_text(script.replace(
                "packages/p07-network-node/**/vf-node.sh",
                "installers/vf-node.sh"), encoding="utf-8")
            with self.assertRaisesRegex(ux.PublicUXError, "CI 接线缺失"):
                ux.load_and_check(root)

    def test_new_p07_terminal_entry_must_still_trigger_pr_ci(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.fixtures(temp)
            workflow = root / ux.WORKFLOW
            content = workflow.read_text(encoding="utf-8")
            self.assertIn("installers/p07-*.sh", content)
            self.assertIn("experiments/p07-*.sh", content)
            workflow.write_text(content.replace(
                "installers/p07-*.sh", "installers/p07-toolbox.sh"),
                encoding="utf-8")
            with self.assertRaisesRegex(ux.PublicUXError, "CI 接线缺失"):
                ux.load_and_check(root)

    def test_missing_ci_or_agents_pointer_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.fixtures(temp)
            (root / ux.WORKFLOW).unlink()
            with self.assertRaisesRegex(ux.PublicUXError, "缺少"):
                ux.load_and_check(root)
        with tempfile.TemporaryDirectory() as temp:
            root = self.fixtures(temp)
            f = root / "AGENTS.md"
            f.write_text(f.read_text(encoding="utf-8").replace(
                "P07_TERMINAL_UX_ADOPTION.md", "NO_UX_LINK.md"), encoding="utf-8")
            with self.assertRaisesRegex(ux.PublicUXError, "未接线"):
                ux.load_and_check(root)


if __name__ == "__main__":
    unittest.main()
