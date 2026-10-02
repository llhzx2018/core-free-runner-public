from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Release11BeginnerIaTests(unittest.TestCase):
    def test_slot3_is_only_website_and_data(self) -> None:
        text = (ROOT / "bin" / "vfops-user").read_text(encoding="utf-8")
        for label in (
            "网站与数据概况",
            "备份与恢复",
            "服务器迁移",
            "网站创建与维护",
            "面板账号与安全（CloudPanel）",
        ):
            self.assertIn(label, text)
        self.assertIn("backup_menu()", text)
        self.assertIn("立即备份一个网站", text)
        self.assertIn("从备份恢复网站", text)
        self.assertNotIn('8) run_module "$DIAG_UI"', text)
        self.assertNotIn('10) run_module "$SELFCHECK_UI"', text)
        self.assertNotIn('11) run_module "$INIT_UI"', text)

    def test_selfcheck_is_runtime_accurate_and_chinese(self) -> None:
        text = (ROOT / "bin" / "vfops-selfcheck-ui").read_text(encoding="utf-8")
        self.assertNotIn("docs/authority/P07_INTEGRATION_MANIFEST.json", text)
        self.assertIn("重新安装工具运行文件", text)
        self.assertIn("确认重新安装工具运行文件？[y/N]", text)
        self.assertNotIn("输入“修复”继续", text)
        self.assertNotIn("输入 REPAIR", text)

    def test_backup_package_metadata_is_snapshot_not_external_symlink(self) -> None:
        text = (ROOT / "lib" / "package_core.py").read_text(encoding="utf-8")
        self.assertIn("copy_private_follow(root, source, target)", text)
        self.assertIn("backup package contains external symlink", text)
        self.assertIn('failures.append(f"symlink:', text)

    def test_restore_failure_is_translated_for_user(self) -> None:
        site_ui = (ROOT / "bin" / "vfops-site-ui").read_text(encoding="utf-8")
        failure_ui = (ROOT / "lib" / "restore_failure_ui.sh").read_text(encoding="utf-8")
        self.assertIn('source "$ROOT_DIR/lib/restore_failure_ui.sh"', site_ui)
        self.assertIn("备份文件完整性复检失败，已停止恢复", failure_ui)
        self.assertIn("更新服务器工具箱后重新备份一次", failure_ui)
        self.assertNotIn("sed -n '1,8p'", site_ui + failure_ui)

    def test_python_renderers_do_not_print_literal_shell_color_tokens(self) -> None:
        for relative in ("bin/vfops-site-ui", "bin/vfops-auto-backup", "bin/vfops-history-ui"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn('replace("\\\\033", chr(27))', text, relative)
        diagnostics = (ROOT / "bin" / "vfops-diagnostics-ui").read_text(encoding="utf-8")
        self.assertIn('colors={"OK":"","WARN":"","ERROR":""}', diagnostics)
        self.assertIn('reset=""', diagnostics)


if __name__ == "__main__":
    unittest.main()
