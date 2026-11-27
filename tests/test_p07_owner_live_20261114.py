"""P07 owner-terminal regressions: no real journal/system mutations in tests.

Tests:
- M03 formally released legacy identity pinned, unknown build still fail-closed.
- M04's journalctl *mock* returns freed 0B/positive/error: no false success.
- Toolbox 0/Enter/NO_COLOR and M05's existing-host description.
A separate runner workflow exercises actual old formal M03 install/upgrade.
"""
from __future__ import annotations

import os
import pty
import select
import time
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
        self.assertIn('M03_LEGACY135_BUILD="0.1.0-release135"', content)
        # release142 remains a verified predecessor, not the current build.
        self.assertIn('M03_OFFICIAL142_BUILD="0.1.0-release142"', content)
        self.assertIn('M03_OFFICIAL142_MANIFEST_BLOB="cc3d90839bf71ea9139f5fc0d1c6cb12403b58e0"', content)
        self.assertIn('M03_OFFICIAL140_BUILD="0.1.0-release140"', content)
        self.assertIn('M03_OFFICIAL141_BUILD="0.1.0-release141"', content)
        self.assertIn('M03_PREVIOUS_BUILD="0.1.0-release139"', content)
        self.assertIn('M03_LEGACY138_BUILD="0.1.0-release138"', content)
        self.assertIn('m03_verified_current || return 13', content)
        self.assertIn('    *) return 1 ;;', content)
        self.assertIn('逐文件核验的正式旧版才可升级', content)

    def test_toolbox_blank_enter_is_not_an_error_and_m05_intent_is_true(self):
        # Exercise the actual public menu: blank Enter must redisplay rather
        # than dispatch any module. Verify the M05 task, not padding or color.
        master, slave = pty.openpty()
        proc = subprocess.Popen(["bash", str(TOOLBOX)], stdin=slave,
                                stdout=slave, stderr=slave,
                                env={**os.environ, "NO_COLOR":"1", "TERM":"xterm"})
        os.close(slave)
        output = bytearray()
        prompt = "请选择 [0-5]：".encode()
        sent = 0
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    try:
                        output.extend(os.read(master, 65536))
                    except OSError:
                        break
                if output.count(prompt) > sent and sent < 2:
                    os.write(master, b"\n" if sent == 0 else b"0\n")
                    sent += 1
                if proc.poll() is not None:
                    break
            self.assertEqual(sent, 2)
            self.assertEqual(proc.wait(timeout=2), 0)
            rendered = output.decode("utf-8", "replace")
            self.assertEqual(rendered.count("请选择 [0-5]："), 2)
            self.assertNotIn("无效选择", rendered)
            self.assertIn("5. 新服务器初始化", rendered)
            self.assertIn("空机安装", rendered)
            self.assertIn("现有环境检查", rendered)
            self.assertNotIn("\x1b", rendered)
            self.assertIn('--check-m03)', TOOLBOX.read_text())
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)
            os.close(master)

    def test_write_confirmation_kept_for_disk_and_module_upgrades(self):
        script = JOURNAL_SCRIPT.read_text()
        toolbox = TOOLBOX.read_text()
        self.assertIn("confirm_numeric '清理软件安装缓存，并把系统运行日志保留最近 14 天？'", script)
        self.assertIn("P07_CLEANUP_CONFIRMED=1 clean_journal", script)
        route=(ROOT/'installers/p07-three-ux-owner-route.py').read_text()
        self.assertIn('p07_three_ux_route P07-M04',toolbox)
        self.assertIn('确认仅升级本模块？[y/N]',route)
        self.assertIn("确认仅升级 P07-M03 网站与数据？[y/N]", toolbox)

    def test_bad_numeric_input_still_reports_invalid_not_silent(self):
        text = TOOLBOX.read_text()
        self.assertIn('      "") continue ;;', text)
        self.assertIn('无效选择，请输入 0-5。', text)
        self.assertIn('read -r choice || return 0', text)

    def test_no_color_non_tty_maintains_explicit_safety(self):
        text = TOOLBOX.read_text()
        # Pipes and redirected output must stay plain even without NO_COLOR.
        for no_color in (False, True):
            env = {**os.environ, "TERM":"xterm"}
            env.pop("NO_COLOR", None)
            if no_color:
                env["NO_COLOR"] = "1"
            for args in (["--help"], ["--version"], ["--modules"], []):
                with self.subTest(no_color=no_color, args=args):
                    proc = subprocess.run(["bash", str(TOOLBOX), *args],
                        input="", capture_output=True, text=True, env=env, timeout=10)
                    self.assertEqual(proc.returncode, 0 if args else 2)
                    self.assertNotIn("\x1b", proc.stdout + proc.stderr)
                    if not args:
                        self.assertIn("交互式终端", proc.stderr)
            # stdout is a terminal but stdin is redirected: must not color or clear.
            master, slave = pty.openpty()
            proc = subprocess.Popen(["bash", str(TOOLBOX), "--help"],
                stdin=subprocess.DEVNULL, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            chunks = bytearray()
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            chunks.extend(os.read(master, 65536))
                        except OSError:
                            break
                    if proc.poll() is not None and not ready:
                        break
                self.assertEqual(proc.wait(timeout=2), 0)
                self.assertIn("新服务器初始化", chunks.decode("utf-8", "replace"))
                self.assertNotIn(b"\x1b", chunks)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=2)
                os.close(master)
        self.assertIn('p07_three_ux_route P07-M04',text)
        route=(ROOT/'installers/p07-three-ux-owner-route.py').read_text()
        self.assertIn('升级需要在交互式 SSH 中由本人确认',route)
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
