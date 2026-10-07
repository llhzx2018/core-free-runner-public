from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ContextualBackupMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.auto = (ROOT / "bin" / "vfops-auto-backup").read_text(encoding="utf-8")
        cls.storage = (ROOT / "bin" / "vfops-storage-setup").read_text(encoding="utf-8")

    def test_auto_backup_menu_is_state_aware(self) -> None:
        for marker in (
            "first_backup_pass_recorded",
            "storage_ready=0",
            "first_pass=0",
            "cron_ready=0",
            "下一步：先完成 Google + B2 异地备份设置；完成前不显示备份执行和定时开关。",
            "首次验证：立即备份全部网站",
            "通过后才显示自动备份开关。",
            "开启自动备份",
            "修改自动备份",
            "关闭自动备份",
        ):
            self.assertIn(marker, self.auto)
        self.assertIn('[[ "$cron_ready" -eq 1 ]] && disable_auto', self.auto)
        self.assertIn('[[ "$first_pass" -eq 1 ]] && enable_or_update', self.auto)

    def test_remote_storage_menu_changes_with_setup_state(self) -> None:
        for marker in (
            "状态：尚未设置",
            "开始设置异地备份",
            "从仍在线的旧 P07 服务器导入",
            "状态：Google + B2 已就绪",
            "不再显示首次准备教程和旧服务器导入入口",
            "检查当前设置",
            "重新设置异地备份",
            "状态：已有设置，但健康检查未通过",
        ):
            self.assertIn(marker, self.storage)
        self.assertNotIn("立即完整备份一次", self.storage)


if __name__ == "__main__":
    unittest.main()
