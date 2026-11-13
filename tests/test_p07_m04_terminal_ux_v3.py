"""P07-M04 服务器维护与安全：真实候选包 UX V3 安全终端正反例。"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packages/p07-system-care/0.1.0-ux1"
SCRIPT = PKG / "vf-system-care.sh"


class P07M04TerminalUXV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = SCRIPT.read_text(encoding="utf-8")
        cls.menu_function = "menu() {" + cls.ui.split(
            "\nmenu() {", 1)[1].split('\ncase "${1:-menu}" in', 1)[0]
        cls.check_function = "m04_module_selfcheck() {" + cls.ui.split(
            "\nm04_module_selfcheck() {", 1)[1].split("\nrun_vfops_tool() {", 1)[0]
        cls.dependencies_function = "ensure_vfops_tools() {" + cls.ui.split(
            "\nensure_vfops_tools() {", 1)[1].split("\nm04_module_selfcheck() {", 1)[0]

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
m04_module_selfcheck(){ printf 'ACTION:module-selfcheck\n'; }
run_vfops_tool(){ printf 'ACTION:optional-history\n'; }
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
        self.assertIn("MENU:1:查看服务器状态（只读）", out)
        self.assertIn("MENU:2:检查并安装系统更新", out)
        self.assertIn("MENU:3:扫描并清理磁盘空间", out)
        self.assertIn("MENU:7:检查本模块文件（只读）", out)
        self.assertIn("MENU:0:返回工具箱", out)
        self.assertNotIn("安全边界：", out)
        self.assertNotIn("ACTION:", out)

    def test_readonly(self):
        out = self.run_menu("1\n0\n")
        self.assertIn("ACTION:own-status.sh", out)
        self.assertNotIn("ACTION:updates", out)
        self.assertNotIn("ACTION:optional-history", out)
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
ui_page(){ :; }
ui_attention(){ echo "ATTENTION:$1"; }
ui_good(){ echo "GOOD:$1"; }
SCRIPT_DIR="$P07_PACKAGE"
'''
        p = subprocess.run(
            ["bash", "-c", stubs + self.check_function + "\nm04_module_selfcheck\n"],
            capture_output=True, text=True,
            env={**os.environ, "P07_PACKAGE": str(PKG)}, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("本模块文件检查通过", p.stdout)

    def test_failure_block(self):
        p = subprocess.run(["bash", "-c", r'''
set -Eeuo pipefail
VFOPS_DIR="$P07_TMP"
VFOPS_BUILD_EXPECTED='0.1.0-release115'
ui_attention(){ echo "ATTENTION:$1"; }
ui_note(){ echo "NOTE:$1"; }
vfops_build_current(){ return 1; }
''' + self.dependencies_function + "\nif ensure_vfops_tools vfops-history-ui; then exit 11; fi\n"],
            capture_output=True, text=True,
            env={**os.environ, "P07_TMP": "/nonexistent/p07-test-m04"}, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("不会自动安装或升级网站与数据", p.stdout)
        self.assertNotIn("正在同步", p.stdout)
        self.assertNotIn("ACTION:", p.stdout)

    def test_no_color_non_tty(self):
        out = self.run_menu()
        self.assertNotIn("\x1b", out)
        for arg, expected in (("--version", "0.1.0-ux1"),
                              ("--ui-contract", "P07_TERMINAL_UX_V3")):
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
