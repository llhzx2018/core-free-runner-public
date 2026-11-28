"""P07 M01/M02/M04 next-UX source-candidate tests. Never install on a host.

Existing published package files and manifests remain immutable. Each tested
candidate is mounted over a throwaway copy of its own module for real Bash UX.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import tempfile
import struct
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
NETWORK_OLD = ROOT / "packages/p07-network-node/0.1.0-ux2"
NETWORK_NEW = ROOT / "packages/p07-network-node/0.1.0-ux3/vf-node.sh"
AUDIT_OLD = ROOT / "experiments/p07-vps-audit-v21-ux2.sh"
AUDIT_NEW = ROOT / "experiments/p07-vps-audit-v21-ux3.sh"
CARE_OLD = ROOT / "packages/p07-system-care/0.1.0-ux4"
CARE_NEW = ROOT / "packages/p07-system-care/0.1.0-ux5/vf-system-care.sh"
ENV = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "P07_FORCE_INTERACTIVE": "1"}


def run_command(script: Path, *args: str, input_text: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(script), *args], input=input_text,
                          text=True, capture_output=True, timeout=8, env=ENV)


def run_menu(script: Path, answers: bytes = b"0\n", timeout: float = 7.0, *,
             columns: int = 80) -> str:
    parent, slave = pty.openpty()
    try:
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, columns, 0, 0))
        rows, cols, _, _ = struct.unpack("HHHH", fcntl.ioctl(slave, termios.TIOCGWINSZ, bytes(8)))
        if (rows, cols) != (24, columns):
            raise AssertionError("PTY window size was not applied")
        child = subprocess.Popen(["bash", str(script)], stdin=slave, stdout=slave,
                                 stderr=slave, env={**ENV, "COLUMNS": str(columns), "LINES": "24"})
    except BaseException:
        os.close(parent)
        os.close(slave)
        raise
    os.close(slave)
    output = bytearray()
    try:
        # Wait for the real menu prompt before answering. Early PTY input can
        # be consumed by Bash/terminal setup and leave a safe 0 menu hanging.
        # Never inject options other than the test's 0/invalid input queue.
        queue = [x + b"\n" for x in answers.split(b"\n") if x]
        if any(x not in (b"0\n", b"9\n") for x in queue):
            raise AssertionError("non-safe menu answer rejected")
        sent = 0
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([parent], [], [], 0.1)
            if ready:
                try:
                    output.extend(os.read(parent, 65536))
                except OSError:
                    break
                prompts = output.decode("utf-8", "replace").count("请选择 [")
                if prompts > sent and sent < len(queue):
                    # Give Bash a moment to enter read(1): the prompt is
                    # printed just before the line editor starts consuming.
                    time.sleep(0.08)
                    os.write(parent, queue[sent])
                    sent += 1
            if child.poll() is not None:
                break
        if child.poll() is None:
            raise AssertionError("menu did not exit via 0 or EOF: " +
                                 output[-450:].decode("utf-8", "replace"))
        if child.wait(timeout=1) != 0:
            raise AssertionError("menu returned failure: " + output[-450:].decode("utf-8", "replace"))
        return output.decode("utf-8", "replace")
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2)
        os.close(parent)


def published_blob_unchanged(package: Path) -> None:
    manifest = (package / "MANIFEST.sha256").read_text()
    entry = next(x for x in manifest.splitlines() if x.endswith("  vf-node.sh"))
    wanted = entry.split()[0]
    found = hashlib.sha256((package / "vf-node.sh").read_bytes()).hexdigest()
    if found != wanted:
        raise AssertionError("published M01 manifest and entrypoint changed")


class CandidateSandbox(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="p07-ux-candidate-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(NETWORK_OLD, self.root / "m01")
        shutil.copy2(NETWORK_NEW, self.root / "m01/vf-node.sh")
        shutil.copytree(CARE_OLD, self.root / "m04")
        shutil.copy2(CARE_NEW, self.root / "m04/vf-system-care.sh")
        shutil.copy2(AUDIT_NEW, self.root / "audit.sh")
        self.m01 = self.root / "m01/vf-node.sh"
        self.m02 = self.root / "audit.sh"
        self.m04 = self.root / "m04/vf-system-care.sh"

    def test_m01_main_menu(self):
        out = run_menu(self.m01)
        self.assertIn("网络代理节点", out)
        self.assertIn("当前状态", out)
        self.assertIn("0. 返回工具箱", out)

    def test_m01_readonly(self):
        p = run_command(self.m01, "--version")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("Network Node", p.stdout)

    def test_m01_write_confirmation(self):
        code = self.m01.read_text()
        self.assertIn("确认继续？[y/N]", code)
        self.assertIn("确认修复？[y/N]", code)
        self.assertIn("run_and_pause bash", code)
        self.assertIn("uninstall.sh", code)
        published_blob_unchanged(NETWORK_OLD)

    def test_m01_cancel_eof_invalid(self):
        p = run_command(self.m01, "unknown")
        self.assertNotEqual(p.returncode, 0)
        out = run_menu(self.m01, b"9\n0\n")
        self.assertIn("无效选择", out)

    def test_m01_success(self):
        p = run_command(self.m01, "--help")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("查看节点状态", p.stdout)

    def test_m01_failure_block(self):
        self.assertIn("请先检查节点状态，再决定是否重试", self.m01.read_text())
        self.assertIn("exact_confirm", (NETWORK_OLD / "lib/common.sh").read_text())

    def test_m01_no_color_non_tty(self):
        p = run_command(self.m01, "--help")
        self.assertNotIn("\033[", p.stdout)
        out = run_menu(self.m01)
        self.assertNotIn("\033[", out)

    def test_m02_main_menu(self):
        out = run_menu(self.m02)
        self.assertIn("完整验机会使用 CPU、磁盘和网络资源", out)
        self.assertIn("0. 返回工具箱", out)

    def test_m02_readonly(self):
        p = run_command(self.m02, "--version")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("V2.1.1", p.stdout)

    def test_m02_write_confirmation(self):
        # This is a read-only menu; selected benchmark is the sole test start.
        code = self.m02.read_text()
        self.assertIn("1) return 0", code)
        self.assertIn("show_vps_audit_menu || exit 0", code)
        self.assertIn("P07_FIO_TIMEOUT_SEC", code)
        self.assertEqual(run_menu(self.m02).count("开始完整 VPS 验机"), 1)

    def test_m02_cancel_eof_invalid(self):
        p = run_command(self.m02, "--unknown")
        self.assertNotEqual(p.returncode, 0)
        out = run_menu(self.m02, b"9\n0\n")
        self.assertIn("选择无效", out)

    def test_m02_success(self):
        p = run_command(self.m02, "--build-id")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "2.1.1-ux3")

    def test_m02_failure_block(self):
        code = self.m02.read_text()
        self.assertIn("完整性校验失败，已停止", code)
        self.assertIn("return 5", code)
        self.assertIn("返回工具箱", code)

    def test_m02_no_color_non_tty(self):
        for arg in ("--help", "--build-id", "--version"):
            p = run_command(self.m02, arg)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("\033[", p.stdout)
        self.assertNotIn("\033[", run_menu(self.m02))

    def test_m01_ux4_menu_state_change_stops_before_write(self):
        source=(ROOT/"packages/p07-network-node/0.1.0-ux4/vf-node.sh").read_text()
        select=source[source.index("menu_state_unchanged() {"):source.index("\n# P07-M01")]
        # Actual menu functions, controlled observations, no service writes.
        for before,after in (("HEALTHY","ABSENT"),("ABSENT","EXTERNAL"),
                             ("MANAGED_UNHEALTHY","HEALTHY")):
            shell=r'''
set -Eeuo pipefail
warn(){ printf '%s\n' "$*"; }
info(){ printf '%s\n' "$*"; }
pause_if_tty(){ :; }
node_menu_state(){ printf '%s' "$AFTER"; }
run_and_pause(){ printf 'UNEXPECTED_ACTION\n'; }
repair_managed_install(){ printf 'UNEXPECTED_ACTION\n'; }
'''+select+'\ninstall_from_menu\n'
            p=subprocess.run(["bash","-c",shell],input="y\n",text=True,
                capture_output=True,timeout=5,
                env={**ENV,"P07_NODE_DISPLAY_STATE":before,"AFTER":after})
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn("节点状态已变化",p.stdout)
            self.assertNotIn("UNEXPECTED_ACTION",p.stdout)

    def test_m01_ux4_state_change_after_confirmation_stops_repair(self):
        source=(ROOT/"packages/p07-network-node/0.1.0-ux4/vf-node.sh").read_text()
        select=source[source.index("menu_state_unchanged() {"):source.index("\n# P07-M01")]
        state=self.root/"node-state-count"
        shell=r'''
set -Eeuo pipefail
warn(){ printf '%s\n' "$*"; }
info(){ printf '%s\n' "$*"; }
pause_if_tty(){ :; }
node_menu_state(){
  if [[ -e "$COUNT_FILE" ]]; then printf 'EXTERNAL'
  else : > "$COUNT_FILE"; printf 'MANAGED_UNHEALTHY'; fi
}
run_and_pause(){ printf 'UNEXPECTED_ACTION\n'; }
repair_managed_install(){ printf 'UNEXPECTED_ACTION\n'; }
'''+select+'\ninstall_from_menu\n'
        p=subprocess.run(["bash","-c",shell],input="y\n",text=True,capture_output=True,
            timeout=5,env={**ENV,"COUNT_FILE":str(state),"P07_NODE_DISPLAY_STATE":"MANAGED_UNHEALTHY"})
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("确认修复",p.stdout)
        self.assertIn("节点状态已变化",p.stdout)
        self.assertNotIn("UNEXPECTED_ACTION",p.stdout)

    def test_m01_ux4_actual_menu_and_plain_output(self):
        root=self.root/"m01-ux4"
        shutil.copytree(NETWORK_OLD,root)
        overlay=ROOT/"packages/p07-network-node/0.1.0-ux4"
        for name in ("vf-node.sh","lib/common.sh"):
            shutil.copy2(overlay/name,root/name)
        (root/"VERSION").write_text("0.1.0-ux4\n")
        out=run_menu(root/"vf-node.sh",b"9\n0\n")
        self.assertIn("当前状态",out)
        self.assertIn("0. 返回工具箱",out)
        self.assertNotIn("\x1b",out)
        p=run_command(root/"vf-node.sh","--version")
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(p.stdout.strip(),"VF Network Node 0.1.0-ux4")

    def test_m01_ux4_exact_actual_atomic_install_and_rollback(self):
        if os.environ.get("GITHUB_ACTIONS")!="true" or os.environ.get("RUNNER_ENVIRONMENT")!="github-hosted":
            self.skipTest("actual root proof needs disposable hosted runner")
        cmd=["python3","-B",str(ROOT/"tests/p07_m01_ux4_actual_atomic_gate.py")]
        if os.geteuid()!=0:cmd=["sudo","-n",*cmd]
        p=subprocess.run(cmd,text=True,capture_output=True,timeout=150)
        self.assertEqual(p.returncode,0,p.stderr[-2000:])
        self.assertIn("M01_EXACT_OFFICIAL_UPGRADE_ROLLBACK_FRESH=PASS",p.stdout)
        self.assertIn("M01_TAMPER_REFUSAL_FAILED_SWITCH_FOUR_SIBLINGS=PASS",p.stdout)
        print(p.stdout,end="")

    def test_m04_main_menu(self):
        out = run_menu(self.m04)
        self.assertIn("本页只显示最近缓存", out)
        self.assertIn("0. 返回工具箱", out)

    def test_m04_readonly(self):
        p = run_command(self.m04, "--help")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("WordPress 网站安全", p.stdout)

    def test_m04_write_confirmation(self):
        code = self.m04.read_text()
        self.assertIn("run_action_friendly updates.sh security", code)
        self.assertIn("run_action_friendly cleanup.sh safe", code)
        self.assertIn("resource-apply.sh apply", code)
        self.assertIn("confirm_numeric", (CARE_OLD / "lib/common.sh").read_text())

    def test_m04_cancel_eof_invalid(self):
        out = run_menu(self.m04, b"9\n0\n")
        self.assertIn("无效选择", out)
        self.assertIn("0. 返回工具箱", out)

    def test_m04_success(self):
        p = run_command(self.m04, "--version")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("服务器维护与安全", p.stdout)

    def test_m04_failure_block(self):
        p = run_command(self.m04, "--unknown")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("未知命令", p.stderr)
        self.assertIn("暂无最近检查结果", self.m04.read_text())

    def test_m04_no_color_non_tty(self):
        for arg in ("--help", "--version"):
            p = run_command(self.m04, arg)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("\033[", p.stdout)
        self.assertNotIn("\033[", run_menu(self.m04))


    def test_m01_ux4_real_terminal_40_and_80_columns(self):
        root = self.root / "m01-ux4-width"
        shutil.copytree(NETWORK_OLD, root)
        overlay = ROOT / "packages/p07-network-node/0.1.0-ux4"
        for name in ("vf-node.sh", "lib/common.sh"):
            shutil.copy2(overlay / name, root / name)
        (root / "VERSION").write_text("0.1.0-ux4\n")
        for cols in (40, 80):
            with self.subTest(columns=cols):
                out = run_menu(root / "vf-node.sh", b"9\n0\n", columns=cols)
                self.assertIn("网络代理节点", out)
                self.assertIn("当前状态", out)
                self.assertIn("无效选择", out)
                self.assertIn("0. 返回工具箱", out)
                self.assertNotIn("\x1b", out)

if __name__ == "__main__":
    unittest.main()
