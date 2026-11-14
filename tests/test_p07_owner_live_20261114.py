"""P07 owner-terminal regressions: no real journal/system mutations in tests.

Tests:
- M03 formally released legacy identity pinned, unknown build still fail-closed.
- M04's journalctl *mock* returns freed 0B/positive/error: no false success.
- Toolbox 0/Enter/NO_COLOR and M05's existing-host description.
A separate runner workflow exercises actual old formal M03 install/upgrade.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLBOX = ROOT / "installers/p07-toolbox.sh"
JOURNAL_SCRIPT = ROOT / "packages/p07-system-care/0.1.0-ux4/cleanup.sh"


class P07OwnerLiveRegression(unittest.TestCase):
    def test_m03_legacy115_is_pinned_not_wildcard(self):
        content = TOOLBOX.read_text()
        self.assertIn('M03_LEGACY115_BUILD="0.1.0-release115"', content)
        self.assertIn('M03_LEGACY115_MANIFEST_BLOB="4acbaca22aac0da681b34376e2cc86d876593181"', content)
        self.assertIn('M03_BOOTSTRAP_BUILD="0.1.0-release135"', content)
        self.assertIn('VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release136"', content)
        self.assertIn('m03_verified_current || return 13', content)
        self.assertIn('    *) return 1 ;;', content)
        self.assertIn('逐文件核验的正式旧版才可升级', content)

    def test_toolbox_blank_enter_is_not_an_error_and_m05_intent_is_true(self):
        text = TOOLBOX.read_text()
        self.assertIn('      "") continue ;;', text)
        self.assertIn('新服务器初始化      ${C_GRAY}空机安装/现有环境检查', text)
        self.assertNotIn('新服务器初始化      ${C_GRAY}系统更新/CloudPanel/数据库选择', text)
        self.assertIn('--check-m03)', text)

    def test_write_confirmation_kept_for_disk_and_module_upgrades(self):
        script = JOURNAL_SCRIPT.read_text()
        toolbox = TOOLBOX.read_text()
        self.assertIn("confirm_numeric '清理软件安装缓存，并把系统运行日志保留最近 14 天？'", script)
        self.assertIn("P07_CLEANUP_CONFIRMED=1 clean_journal", script)
        self.assertIn("确认升级 P07-M04 服务器维护与安全？[y/N]", toolbox)
        self.assertIn("确认仅升级 P07-M03 网站与数据？[y/N]", toolbox)

    def test_bad_numeric_input_still_reports_invalid_not_silent(self):
        text = TOOLBOX.read_text()
        self.assertIn('      "") continue ;;', text)
        self.assertIn('无效选择，请输入 0-5。', text)
        self.assertIn('read -r choice || return 0', text)

    def test_no_color_non_tty_maintains_explicit_safety(self):
        text = TOOLBOX.read_text()
        self.assertIn('[[ -t 1 && -z "${NO_COLOR:-}" ]]', text)
        self.assertIn("非交互模式不自动升级 P07-M04", text)
        self.assertIn("需要本人在交互式 SSH 终端确认升级", text)

    def _fake_journal(self, lines: list[str], status: int = 0):
        self.assertTrue(shutil.which("sudo"), "registered Ubuntu runner needs sudo")
        with tempfile.TemporaryDirectory(prefix="p07-owner-journal-mock-") as folder:
            binary = Path(folder) / "journalctl"
            binary.write_text("#!/bin/sh\n" +
                "case \"$1\" in\n" +
                "  --vacuum-time=14d)\n" +
                "".join("    printf '%s\\n' " + repr(line) + "\n" for line in lines) +
                f"    exit {status} ;;\n" +
                "  *) exit 31 ;;\n" +
                "esac\n")
            binary.chmod(0o755)
            env_path = f"{folder}:{os.environ['PATH']}"
            proc = subprocess.run([
                "sudo", "-n", "env", f"PATH={env_path}", "NO_COLOR=1",
                "P07_CLEANUP_CONFIRMED=1", "bash", str(JOURNAL_SCRIPT), "journal",
            ], capture_output=True, text=True, timeout=20)
            self.assertNotIn("\x1b", proc.stdout + proc.stderr)
            return proc

    def test_zero_freed_is_not_claimed_as_cleaned(self):
        proc = self._fake_journal([
            "Vacuuming done, freed 0B of archived journals from /var/log/journal.",
            "Vacuuming done, freed 0B of archived journals from /run/log/journal.",
        ])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("释放 0B", proc.stdout)
        self.assertIn("活动日志仍保留", proc.stdout)
        self.assertNotIn("旧系统日志已清理", proc.stdout)

    def test_positive_freed_reports_old_archives_only(self):
        proc = self._fake_journal([
            "Vacuuming done, freed 0B of archived journals.",
            "Vacuuming done, freed 1.5M of archived journals.",
        ])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("旧归档日志已回收", proc.stdout)
        self.assertNotIn("活动日志已删除", proc.stdout)

    def test_failed_journal_vacuum_is_not_reported_success(self):
        proc = self._fake_journal(["journalctl: permission denied"], status=1)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("旧日志清理未成功", proc.stderr)
        self.assertNotIn("旧归档日志已回收", proc.stdout)
        self.assertNotIn("释放 0B", proc.stdout)


if __name__ == "__main__":
    unittest.main()
