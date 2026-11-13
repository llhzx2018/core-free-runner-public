"""P07-M01 网络代理节点（V2Ray）独立候选真实 SSH 菜单安全正反例。

原菜单函数在隔离 bash 中运行，所有可能写入的下游服务动作
均替换为临时文件 synthetic stub；不安装、停止、重启真实节点。
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packages/p07-network-node/0.1.0-ux1"
SCRIPT = PKG / "vf-node.sh"


class P07M01TerminalUXV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.functions = "show_header() {" + cls.source.split(
            "show_header() {", 1)[1].split("\nusage() {", 1)[0]

    def menu(self, choices="0\n", *, managed=False, healthy=False,
             external=False, command_rc=0):
        with tempfile.TemporaryDirectory() as dirname:
            temp = Path(dirname)
            state = temp / "node.env"
            if managed:
                state.write_text("INSTALL_STATUS=BROKEN\n", encoding="utf-8")
            for name in ("install.sh", "status.sh", "share.sh", "uninstall.sh"):
                (temp / name).write_text(
                    "#!/bin/bash\n"
                    f"echo ACTION:{name}\n"
                    f"exit {command_rc if name == 'status.sh' else 0}\n",
                    encoding="utf-8",
                )
            stubs = r'''
set -Eeuo pipefail
C_CYAN=''; C_RESET=''; C_BOLD=''; C_GRAY=''
C_GREEN=''; C_YELLOW=''; C_RED=''; C_MAGENTA=''
VF_NODE_VERSION='0.1.0-ux1'
PORT=443
say(){ printf '%s\n' "$*"; }
ok(){ printf 'GOOD:%s\n' "$*"; }
warn(){ printf 'WARN:%s\n' "$*"; }
info(){ printf 'INFO:%s\n' "$*"; }
fail(){ printf 'FAIL:%s\n' "$*" >&2; }
pause_if_tty(){ :; }
load_state(){ PORT=443; }
node_healthy(){ [[ "$P07_TEST_HEALTH" == 1 ]]; }
port_in_use_udp(){ return 0; }
v2ray_cli(){ [[ "$P07_TEST_EXTERNAL" == 1 ]]; }
restart_managed_node(){ printf 'ACTION:restart\n'; return 0; }
'''
            env = dict(os.environ, NO_COLOR="1",
                       VF_NODE_STATE_FILE=str(state),
                       SCRIPT_DIR=str(temp),
                       P07_TEST_HEALTH="1" if healthy else "0",
                       P07_TEST_EXTERNAL="1" if external else "0")
            p = subprocess.run(
                ["bash", "-c", stubs + self.functions + "\nmenu_loop\n"],
                input=choices, text=True, capture_output=True,
                env=env, timeout=8
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout

    def test_main_menu(self):
        out = self.menu()
        self.assertIn("网络代理节点", out)
        self.assertIn("当前状态：未安装", out)
        self.assertIn("1. 安装节点", out)
        self.assertIn("2. 查看节点状态", out)
        self.assertIn("3. 查看分享链接", out)
        self.assertIn("0. 返回工具箱", out)
        self.assertEqual(sum("  1." in line for line in out.splitlines()), 1)
        self.assertNotIn("ACTION:", out)

    def test_readonly(self):
        out = self.menu("1\n0\n", managed=True, healthy=True)
        self.assertIn("运行正常", out)
        self.assertIn("无需重复安装", out)
        self.assertNotIn("ACTION:install", out)
        self.assertNotIn("ACTION:restart", out)

    def test_write_confirmation(self):
        no = self.menu("1\nn\n0\n")
        self.assertIn("确认继续？[y/N]", no)
        self.assertIn("已取消；没有安装节点", no)
        self.assertNotIn("ACTION:install", no)
        yes = self.menu("1\ny\n0\n")
        self.assertIn("ACTION:install.sh", yes)
        self.assertNotIn("ACTION:restart", yes)

    def test_cancel_eof_invalid(self):
        self.assertNotIn("ACTION:", self.menu("0\n"))
        self.assertNotIn("ACTION:", self.menu(""))
        invalid = self.menu("9\n0\n")
        self.assertIn("无效选择，请输入 0-4", invalid)
        self.assertNotIn("ACTION:", invalid)

    def test_success(self):
        out = self.menu("1\ny\n0\n", managed=True, healthy=False)
        self.assertIn("确认修复？[y/N]", out)
        self.assertIn("ACTION:restart", out)
        self.assertIn("节点自动修复完成", out)
        self.assertNotIn("ACTION:install.sh", out)

    def test_failure_block(self):
        external = self.menu("1\n0\n", external=True)
        self.assertIn("不接管", external)
        self.assertNotIn("ACTION:install.sh", external)
        rejected = self.menu("1\nn\n0\n", managed=True)
        self.assertIn("已取消；服务没有改变", rejected)
        self.assertNotIn("ACTION:restart", rejected)
        failed = self.menu("2\n0\n", command_rc=9)
        self.assertIn("操作未完成", failed)
        self.assertIn("ACTION:status.sh", failed)

    def test_no_color_non_tty(self):
        out = self.menu("0\n")
        self.assertNotIn("\x1b", out)
        self.assertNotIn("长期稳定基线", out)
        p = subprocess.run(
            ["bash", str(SCRIPT), "--version"],
            capture_output=True, text=True, env={**os.environ, "NO_COLOR": "1"},
            timeout=5,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("0.1.0-ux1", p.stdout)

    def test_candidate_manifest_integrity(self):
        for line in (PKG / "MANIFEST.sha256").read_text().splitlines():
            if not line:
                continue
            expected, rel = line.split("  ", 1)
            actual = hashlib.sha256((PKG / rel).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, rel)


if __name__ == "__main__":
    unittest.main()
