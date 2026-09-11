from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Menu3ModularTests(unittest.TestCase):
    def test_top_level_menu_is_thin_and_task_oriented(self) -> None:
        proc = subprocess.run(
            ["bash", str(ROOT / "bin/vfops-user")],
            input="0\n",
            text=True,
            capture_output=True,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for text in (
            "1. 服务器 / 网站概览",
            "2. 备份网站",
            "3. 恢复网站",
            "4. 迁移网站到新服务器",
            "5. 自动备份 / 远程灾备",
            "6. CloudPanel 网站工具",
        ):
            self.assertIn(text, proc.stdout)

    def test_top_level_routes_to_separate_modules(self) -> None:
        text = (ROOT / "bin/vfops-user").read_text(encoding="utf-8")
        self.assertIn("vfops-site-ui", text)
        self.assertIn("vfops-migrate-ui", text)
        self.assertIn("vfops-auto-backup", text)
        self.assertIn("vfops-cloudpanel-ui", text)
        self.assertIn("--advanced", text)

    def test_restore_ui_exposes_restore_as_and_preserves_no_overwrite(self) -> None:
        text = (ROOT / "bin/vfops-site-ui").read_text(encoding="utf-8")
        self.assertIn("恢复为新网站（推荐，可在本机测试）", text)
        self.assertIn("RESTORE_AS:", text)
        self.assertIn("restore_as_verified.py", text)
        self.assertIn("自动完成本机文件、数据库、Host 与 SNI/vhost 验证", text)
        self.assertIn("失败会回滚本次新建目标", text)
        self.assertIn("无需先在 CloudPanel 手工创建空网站", text)
        self.assertIn("按原域名恢复", text)
        self.assertIn("P07 不会覆盖", text)
        self.assertIn("DNS：未修改", text)

    def test_cloudpanel_tools_do_not_expose_destructive_delete_actions(self) -> None:
        text = (ROOT / "bin/vfops-cloudpanel-ui").read_text(encoding="utf-8")
        self.assertIn("修复网站权限", text)
        self.assertIn("清理 Varnish 缓存", text)
        self.assertIn("查看 SSL 状态", text)
        self.assertNotIn("site:delete", text)
        self.assertNotIn("db:delete", text)
        self.assertNotIn("  6. 删除网站", text)
        self.assertNotIn("  6. 删除数据库", text)

    def test_migration_preserves_source_dns_and_target_collision_boundaries(self) -> None:
        text = (ROOT / "bin/vfops-migrate-ui").read_text(encoding="utf-8")
        self.assertIn("TARGET_SITE_CONFLICT", text)
        self.assertIn("P07 不会覆盖", text)
        self.assertIn("DNS：未修改", text)
        self.assertIn("SOURCE：保留", text)
        self.assertIn("ssh-copy-id", text)


if __name__ == "__main__":
    unittest.main()
