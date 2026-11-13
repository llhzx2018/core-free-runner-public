"""P07-M04 服务器维护与安全：对已修复 ux3 实际源码和清单的七场景 UX V3 验收。"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packages/p07-system-care/0.1.0-ux3"
SCRIPT = PKG / "vf-system-care.sh"


class P07M04TerminalUX3FieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = SCRIPT.read_text(encoding="utf-8")
        cls.menu_function = "menu() {" + cls.ui.split(
            "\nmenu() {", 1)[1].split('\ncase "${1:-menu}" in', 1)[0]
        cls.check_function = "selfcheck_local_module() {" + cls.ui.split(
            "\nselfcheck_local_module() {", 1)[1].split("\nrecent_local_actions() {", 1)[0]

    def run_menu(self, selection="0\n", *, wordpress=False):
        stubs = r'''
set -Eeuo pipefail
show_header(){ printf 'PAGE:服务器维护与安全\n'; }
ui_menu_good(){ printf 'MENU:%s:%s\n' "$1" "$2"; }
ui_menu_warn(){ printf 'MENU:%s:%s\n' "$1" "$2"; }
ui_menu_info(){ printf 'MENU:%s:%s\n' "$1" "$2"; }
ui_menu_back(){ printf 'MENU:%s:%s\n' "$1" "$2"; }
ui_prompt(){ printf 'PROMPT:%s\n' "$1"; }
ui_attention(){ printf 'ATTENTION:%s\n' "$1"; }
wordpress_present(){ [[ "$P07_TEST_WP" = 1 ]]; }
screen_clear(){ :; }
run_action_friendly(){ printf 'ACTION:own-%s\n' "$1"; }
pause_menu(){ :; }
updates_flow_beginner(){ printf 'ACTION:updates\n'; }
cleanup_flow_beginner(){ printf 'ACTION:cleanup\n'; }
resource_flow_beginner(){ printf 'ACTION:resources\n'; }
wordpress_flow_beginner(){ printf 'ACTION:wordpress\n'; }
selfcheck_local_module(){ printf 'ACTION:module-selfcheck\n'; }
recent_local_actions(){ printf 'ACTION:own-history\n'; }
'''
        p = subprocess.run(
            ["bash", "-c", stubs + self.menu_function + "\nmenu\n"],
            input=selection, text=True, capture_output=True,
            env={**os.environ, "NO_COLOR": "1", "P07_TEST_WP": "1" if wordpress else "0"},
            timeout=8)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_main_menu(self):
        out = self.run_menu("0\n")
        self.assertIn("PAGE:服务器维护与安全", out)
        self.assertIn("MENU:1:检查服务器健康（完整）", out)
        self.assertIn("MENU:2:检查并安装系统更新", out)
        self.assertIn("MENU:3:扫描并清理磁盘空间", out)
        self.assertIn("MENU:7:检查本模块（只读）", out)
        self.assertIn("MENU:0:返回工具箱", out)
        self.assertNotIn("安全边界：", out)
        self.assertNotIn("ACTION:", out)

    def test_readonly(self):
        out = self.run_menu("1\n0\n")
        self.assertIn("ACTION:own-audit.sh", out)
        self.assertNotIn("ACTION:updates", out)
        self.assertNotIn("ACTION:own-history", out)
        self.assertNotIn("ACTION:cleanup", out)

    def test_write_confirmation(self):
        out = self.run_menu("2\n0\n")
        self.assertIn("ACTION:updates", out)
        self.assertNotIn("ACTION:cleanup", out)
        updates = (PKG / "updates.sh").read_text()
        self.assertIn("confirm_numeric '将刷新 APT 列表", updates)
        self.assertIn("security_install_preflight", updates)
        self.assertIn("run_action_friendly cleanup.sh safe", self.ui)
        self.assertIn("run_action_friendly resource-apply.sh apply", self.ui)
        self.assertNotIn('curl -fsSL "$VFOPS_INSTALLER"', self.ui)

    def test_cancel_eof_invalid(self):
        self.assertNotIn("ACTION:", self.run_menu("0\n"))
        self.assertNotIn("ACTION:", self.run_menu(""))
        wrong = self.run_menu("9\n0\n")
        self.assertIn("ATTENTION:无效选择，请输入 0-8。", wrong)
        self.assertNotIn("ACTION:", wrong)

    def test_success(self):
        out = self.run_menu("7\n0\n")
        self.assertIn("ACTION:module-selfcheck", out)
        self.assertNotIn("ACTION:updates", out)
        stubs = r'''
set -Eeuo pipefail
screen_clear(){ :; }
ui_title(){ :; }
ui_rule(){ :; }
ui_bad(){ echo "BAD:$1"; }
ui_attention(){ echo "ATTENTION:$1"; }
ui_good(){ echo "GOOD:$1"; }
pause_menu(){ :; }
SCRIPT_DIR="$P07_PACKAGE"
VERSION='0.1.0-ux3'
'''
        p = subprocess.run(["bash", "-c", stubs + self.check_function +
                            "\nselfcheck_local_module\n"],
                           capture_output=True, text=True,
                           env={**os.environ, "P07_PACKAGE": str(PKG)}, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("本模块基础文件与版本检查通过", p.stdout)

    def test_failure_block(self):
        self.assertNotIn("ensure_vfops_tools", self.ui)
        self.assertNotIn("VFOPS_INSTALLER", self.ui)
        stubs = r'''
set -Eeuo pipefail
screen_clear(){ :; }
ui_title(){ :; }
ui_rule(){ :; }
ui_bad(){ echo "BAD:$1"; }
ui_attention(){ echo "ATTENTION:$1"; }
ui_good(){ echo "GOOD:$1"; }
pause_menu(){ :; }
SCRIPT_DIR='/nonexistent/p07-m04-missing'
VERSION='0.1.0-ux3'
'''
        p = subprocess.run(["bash", "-c", stubs + self.check_function +
                            "\nselfcheck_local_module\n"],
                           capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("模块版本文件缺失", p.stdout)
        self.assertIn("本模块检查失败", p.stdout)
        self.assertNotIn("正在同步", p.stdout)

    def test_no_color_non_tty(self):
        out = self.run_menu()
        self.assertNotIn("\x1b", out)
        for arg, expected in (("--version", "0.1.0-ux3"),
                              ("--ui-contract", "P07_BEGINNER_ZH_V1")):
            p = subprocess.run(["bash", str(SCRIPT), arg],
                               capture_output=True, text=True,
                               env={**os.environ, "NO_COLOR": "1"}, timeout=5)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn(expected, p.stdout)

    def test_candidate_manifest_integrity(self):
        for line in (PKG / "MANIFEST.gitblob").read_text().splitlines():
            if not line:
                continue
            expected, rel = line.split("  ", 1)
            raw = (PKG / rel).read_bytes()
            blob = b"blob " + str(len(raw)).encode() + b"\0" + raw
            self.assertEqual(expected, hashlib.sha1(blob).hexdigest(), rel)


if __name__ == "__main__":
    unittest.main()
