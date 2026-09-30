from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MainMenuRouteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.user = (ROOT / "bin" / "vfops-user").read_text(encoding="utf-8")
        cls.site = (ROOT / "bin" / "vfops-site-ui").read_text(encoding="utf-8")
        cls.common = (ROOT / "lib" / "cloudpanel_ui_common.sh").read_text(encoding="utf-8")

    def test_five_top_level_routes_and_backup_group_are_wired(self) -> None:
        expected = (
            '1) run_module "$SITE_UI" overview ;;',
            '2) backup_menu ;;',
            '3) run_module "$MIGRATE_UI" ;;',
            '4) run_module "$CLOUDPANEL_UI" site ;;',
            '5) run_module "$CLOUDPANEL_UI" admin ;;',
        )
        for route in expected:
            self.assertIn(route, self.user)
        for route in (
            '1) run_module "$SITE_UI" backup ;;',
            '2) run_module "$SITE_UI" restore ;;',
            '3) run_module "$AUTO_UI" ;;',
        ):
            self.assertIn(route, self.user)
        self.assertNotIn('8) run_module "$DIAG_UI" ;;', self.user)
        self.assertNotIn('11) run_module "$INIT_UI" ;;', self.user)


    def test_child_entry_clears_parent_screen(self) -> None:
        self.assertIn("ui_screen_clear", self.user)
        self.assertIn("ui_result_error '功能没有正常完成'", self.user)

    def test_module_failure_is_visible_and_does_not_kill_main_menu(self) -> None:
        self.assertIn('set +e\n  bash "$file" "$@"\n  rc=$?\n  set -e', self.user)
        self.assertIn("ui_result_error '功能没有正常完成'", self.user)
        self.assertIn('主菜单仍可继续使用', self.user)
        self.assertIn('return 0', self.user)

    def test_restore_empty_state_waits_for_owner_to_read_it(self) -> None:
        self.assertIn("没有发现已验证、可恢复的 P07 本地备份。", self.site)
        self.assertIn("返回后进入“备份与恢复”，选择“立即备份一个网站”。", self.site)
        self.assertIn("ui_empty_state 'P07 · 恢复网站'", self.site)

    def test_backup_empty_site_state_waits_before_main_menu_redraw(self) -> None:
        self.assertIn("没有发现 CloudPanel 网站。\\n'; pause; return 2", self.site)

    def test_cloudpanel_site_empty_state_waits_before_main_menu_redraw(self) -> None:
        self.assertIn("没有发现 CloudPanel 网站。\\n'; pause; return 2", self.common)


if __name__ == "__main__":
    unittest.main()
