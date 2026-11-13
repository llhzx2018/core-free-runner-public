"""P07-M02 服务器性能检测 · 真实正式 v21 派生的完整验机输出 UX V3 正反例。

在合成 shell 中调用原始结果渲染函数；不会在当前机器跑 fio/网络测速。
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/p07-vps-audit-v21-ux1.sh"


class P07M02TerminalUXV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.render_function = "render_terminal_summary() {" + cls.source.split(
            "\nrender_terminal_summary() {", 1)[1].split("\nprintf '%s%s服务器性能检测", 1)[0]

    def run_cli(self, *arguments):
        return subprocess.run(["bash", str(SOURCE), *arguments],
                              capture_output=True, text=True,
                              env={**os.environ, "NO_COLOR": "1"}, timeout=6)

    def render(self):
        shell = r'''
set -Eeuo pipefail
RESET=''; BOLD=''; CYAN=''
VERSION='V2.1.1'
BASE_GRADE='良好'; BASE_SCORE='88'
FIO_VERDICT='可用'; ROUTE_VERDICT='证据不足'
FINAL_RECOMMEND='适合轻量网站'
START_EPOCH=10; end_epoch=30
rule(){ printf '%s\n' '----------------------------------------'; }
'''
        p = subprocess.run(["bash", "-c", shell + self.render_function +
                            "\nrender_terminal_summary\n"],
                           capture_output=True, text=True,
                           env={**os.environ, "NO_COLOR": "1"}, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_main_menu(self):
        p = self.run_cli("--help")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("默认：完整验机", p.stdout)
        self.assertIn("实时展示各项测试进度和原始结果", p.stdout)
        self.assertIn("系统配置、CPU、磁盘 I/O、网络", p.stdout)
        self.assertNotIn("请选择", p.stdout)

    def test_readonly(self):
        for arg in ("--version", "--build-id", "--help"):
            with self.subTest(arg=arg):
                p = self.run_cli(arg)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertNotIn("正在完整验机", p.stdout)
                self.assertNotIn("增强磁盘低负载测试", p.stdout)
        self.assertIn("V2.1.1", self.run_cli("--version").stdout)
        self.assertIn("2.1.1-ux1", self.run_cli("--build-id").stdout)

    def test_write_confirmation(self):
        # The user explicitly picks M02 in Toolbox; full benchmark uses
        # bounded ephemeral local disk file and retains its own cleanup.
        self.assertIn("FIO_TEST_MIB=", self.source)
        self.assertIn("FIO_TIMEOUT_SEC=", self.source)
        self.assertIn("trap cleanup EXIT INT TERM", self.source)
        self.assertIn("run_base\n", self.source)
        self.assertNotIn("apt-get install", self.source)
        self.assertNotIn("reboot", self.source)

    def test_cancel_eof_invalid(self):
        for invalid in ("--unknown", "9", "apply"):
            with self.subTest(invalid=invalid):
                p = self.run_cli(invalid)
                self.assertEqual(p.returncode, 2)
                self.assertIn("未知参数", p.stderr)
                self.assertNotIn("正在完整验机", p.stdout)

    def test_success(self):
        result = self.render()
        self.assertIn("验机结论", result)
        self.assertIn("综合评级       : 良好", result)
        self.assertIn("建议           : 适合轻量网站", result)
        self.assertIn("本次耗时       : 20 秒", result)
        self.assertNotIn("Markdown 报告", result)

    def test_failure_block(self):
        result = self.render()
        self.assertIn("三网回程       : 证据不足", result)
        self.assertIn("未取得证据的项目标为证据不足", result)
        self.assertIn('if (( base_rc != 0 ));', self.source)
        self.assertIn('exit "$base_rc"', self.source)

    def test_no_color_non_tty(self):
        self.assertNotIn("\x1b", self.render())
        for argument in ("--version", "--build-id", "--help"):
            p = self.run_cli(argument)
            self.assertNotIn("\x1b", p.stdout)
            self.assertEqual(p.returncode, 0)
        self.assertIn("write_markdown\n", self.source)
        self.assertLess(self.source.index("render_terminal_summary\nwrite_markdown"),
                        self.source.index("write_markdown\nend_epoch")
                        if "write_markdown\nend_epoch" in self.source
                        else len(self.source))


if __name__ == "__main__":
    unittest.main()
