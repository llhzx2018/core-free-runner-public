"""P07 M01/M02/M04 next-UX source-candidate tests. Never install on a host.

Existing published package files and manifests remain immutable. Each tested
candidate is mounted over a throwaway copy of its own module for real Bash UX.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import tempfile
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


def run_menu(script: Path, answers: bytes = b"0\n", timeout: float = 7.0) -> str:
    parent, slave = pty.openpty()
    child = subprocess.Popen(["bash", str(script)], stdin=slave, stdout=slave,
                             stderr=slave, env=ENV)
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

    def test_m02_ux4_menu_and_identity(self):
        script = ROOT / "experiments/p07-vps-audit-v21-ux4.sh"
        p = run_command(script, "--build-id")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "2.1.1-ux4")
        out = run_menu(script, b"9\n0\n")
        self.assertIn("开始完整 VPS 验机", out)
        self.assertIn("选择无效", out)
        self.assertIn("0. 返回工具箱", out)
        self.assertNotIn("\x1b", out)
        self.assertNotIn("增强 Markdown 报告", out)

    def m02_ux4_render(self, target, fail=False, directory_collision=False):
        # Actual original report writers with synthetic measurement inputs,
        # not a CPU/network benchmark or full installation test.
        source = (ROOT / "experiments/p07-vps-audit-v21-ux4.sh").read_text()
        begin = source.index("write_markdown(){")
        end = source.index("render_terminal_summary()", begin)
        fragment = source[begin:end]
        base = self.root / "base.txt"
        fio = self.root / "fio.tsv"
        route = self.root / "route.tsv"
        base.write_text("原始基础测量数据\n")
        fio.write_text("4k\t4|10|100|20|200\n")
        route.write_text("北京电信\t电信CN2\t优质\n")
        env = {**ENV, "REPORT_DIR": str(target), "BASE_PLAIN": str(base),
               "FIO_TSV": str(fio), "ROUTE_TSV": str(route)}
        prelude = """set -uo pipefail
VERSION=V2.1.1
STAMP=fixture
BASE_GRADE=良好 BASE_SCORE=88 FIO_VERDICT=可用
ROUTE_VERDICT=证据不足 FINAL_RECOMMEND=适合轻量网站
START_EPOCH=10 end_epoch=30
"""
        if fail:
            prelude += 'ln(){ return 1; }\n'
        if directory_collision:
            prelude += 'mkdir -- "$REPORT_DIR/p07-vps-audit-v21_${STAMP}_$$.md"\n'
        return subprocess.run(["bash", "-c", prelude+fragment+"\nwrite_markdown\n"],
                              capture_output=True,text=True,env=env,timeout=8)

    def test_m02_ux4_report_conclusion_first_and_raw_preserved(self):
        target=self.root/"reports"
        target.mkdir()
        p=self.m02_ux4_render(target)
        self.assertEqual(p.returncode,0,p.stderr)
        files=list(target.glob("*.md"))
        self.assertEqual(len(files),1)
        report=files[0].read_text()
        self.assertLess(report.index("## 验机结论"),report.index("## 基础与网络验机输出"))
        for item in ("综合评级：良好","基础得分：88","三网回程：证据不足",
                     "建议：适合轻量网站","本次耗时：20 秒","原始基础测量数据",
                     "| 4k | 4 | 10 | 100 | 20 | 200 |","北京电信"):
            self.assertIn(item,report)
        self.assertIn(str(files[0]),p.stdout)
        self.assertEqual(files[0].stat().st_mode & 0o777,0o600)
        self.assertFalse(list(target.glob(".p07-report.*")))

    def test_m02_ux4_report_failure_never_advertises_success(self):
        target=self.root/"reports"
        target.mkdir()
        p=self.m02_ux4_render(target,fail=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("报告未保存",p.stderr)
        self.assertNotIn("增强 Markdown 报告",p.stdout)
        self.assertEqual(list(target.iterdir()),[])
        p=self.m02_ux4_render(target/"missing")
        self.assertNotEqual(p.returncode,0)
        self.assertIn("无法创建报告",p.stderr)
        p=self.m02_ux4_render(target,directory_collision=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("报告未保存",p.stderr)
        entries=list(target.iterdir())
        self.assertEqual(len(entries),1)
        self.assertTrue(entries[0].is_dir())
        self.assertEqual(list(entries[0].iterdir()),[])

    def test_m02_ux4_actual_atomic_install_in_disposable_root(self):
        # Existing public product UX gate, no new workflow or Runner.
        # Refuse execution as root on an ordinary machine with an existing host.
        if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
            self.skipTest("real root installer proof requires disposable GitHub-hosted runner")
        cmd=["python3","-B",str(ROOT/"tests/p07_m02_ux4_actual_atomic_gate.py")]
        if os.geteuid()!=0:
            cmd=["sudo","-n",*cmd]
        p=subprocess.run(cmd,text=True,capture_output=True,timeout=150)
        self.assertEqual(p.returncode,0,p.stderr[-1500:])
        for marker in ("M02_OFFICIAL_UX3_TO_EXACT_UX4_REAL_ATOMIC=PASS",
                       "M02_BAD_ARCHIVE_RESEALED_OLD_AND_FAILED_SWITCH=PASS",
                       "M02_ROLLBACK_REUPGRADE_FRESH_INSTALL_FOUR_SIBLINGS=PASS"):
            self.assertIn(marker,p.stdout)
        print(p.stdout, end="")

    def test_m02_ux4_real_menu_40_and_80_columns(self):
        import fcntl,struct,termios,unicodedata
        script=ROOT/"experiments/p07-vps-audit-v21-ux4.sh"
        for cols in (40,80):
            with self.subTest(cols=cols):
                master,slave=pty.openpty()
                fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack("HHHH",24,cols,0,0))
                proc=subprocess.Popen(["bash",str(script)],stdin=slave,stdout=slave,stderr=slave,env=ENV)
                os.close(slave)
                data=bytearray();sent=False
                try:
                    until=time.monotonic()+7
                    while time.monotonic()<until:
                        ready,_,_=select.select([master],[],[],0.1)
                        if ready:
                            try:data.extend(os.read(master,65536))
                            except OSError:break
                        if not sent and "请选择 [0-2]：".encode() in data:
                            os.write(master,b"0\n");sent=True
                        if proc.poll() is not None and not ready:break
                    self.assertTrue(sent)
                    self.assertEqual(proc.wait(timeout=2),0)
                    out=data.decode("utf-8","replace")
                    self.assertNotIn("\x1b",out)
                    self.assertIn("0. 返回工具箱",out)
                    self.assertNotIn("增强 Markdown 报告",out)
                    widths=[sum(2 if unicodedata.east_asian_width(c) in ("W","F") else 1 for c in line) for line in out.splitlines()]
                    self.assertLessEqual(max(widths),cols,out)
                    self.assertLessEqual(len(widths),24,out)
                finally:
                    if proc.poll() is None:
                        proc.kill();proc.wait(timeout=2)
                    os.close(master)

    def test_m02_ux4_result_page_in_actual_40_80_pty(self):
        import errno,fcntl,re,struct,termios,unicodedata
        src=(ROOT/"experiments/p07-vps-audit-v21-ux4.sh").read_text()
        summary=src[src.index("result_line() {"):src.index("\nprintf '%s%s服务器性能检测")]
        disk=src[src.index("print_fio_row(){"):src.index("\nprint_fio(){")]
        route_row=src[src.index("print_route_row(){"):src.index("\nprint_three_carrier_route(){")]
        recommendation="适合轻量网站；数据库/混合磁盘负载需观察；请结合实际业务决定"
        for cols in (40,80):
            for color in (False,True):
                for route in ("证据不足","有效 12/12，优质 10/12"):
                    with self.subTest(cols=cols,color=color,route=route):
                        master,slave=pty.openpty()
                        fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack("HHHH",24,cols,0,0))
                        env={**os.environ,"TERM":"xterm","BASE_GRADE":"良好","BASE_SCORE":"88",
                             "FIO_VERDICT":"可用","ROUTE_VERDICT":route,"FINAL_RECOMMEND":recommendation}
                        env.pop("NO_COLOR",None)
                        if not color:env["NO_COLOR"]="1"
                        prelude=r'''
set -euo pipefail
rule(){ printf '%s\n' '--------------------------------'; }
BOLD= CYAN= RESET=
if [[ -t 0 && -t 1 && -z "${NO_COLOR:-}" ]]; then
  BOLD=$'\033[1m'; CYAN=$'\033[36m'; RESET=$'\033[0m'
fi
end_epoch=408 START_EPOCH=0
'''
                        p=subprocess.Popen(["bash","-c",prelude+summary+"\n"+disk+"\n"+route_row+
                            '\nrender_terminal_summary\nprint_fio_row 4k 4 123.45 30000 67.89 16000\nprint_route_row 北京电信 电信CN2 优质\n'],
                            stdin=slave,stdout=slave,stderr=slave,env=env)
                        os.close(slave);data=bytearray()
                        try:
                            until=time.monotonic()+5
                            while time.monotonic()<until:
                                ready,_,_=select.select([master],[],[],0.1)
                                if ready:
                                    try:data.extend(os.read(master,65536))
                                    except OSError as exc:
                                        if exc.errno!=errno.EIO:raise
                                        break
                                if p.poll() is not None and not ready:break
                            self.assertEqual(p.wait(timeout=2),0)
                            raw=data.decode()
                            self.assertEqual("\x1b[" in raw,color)
                            plain=re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]","",raw)
                            lines=plain.splitlines()
                            widths=[sum(2 if ord(c)>127 and unicodedata.east_asian_width(c) in ("W","F","A") else 1 for c in l) for l in lines]
                            self.assertLessEqual(max(widths),cols,plain)
                            self.assertLessEqual(len(lines),24,plain)
                            flat="".join(l.lstrip() for l in lines)
                            for expected in (recommendation,route,"123.45","30000","67.89","16000","北京电信","电信CN2","缺少证据的项目不计为通过"):
                                self.assertIn(expected,flat)
                        finally:
                            if p.poll() is None:p.kill();p.wait(timeout=2)
                            os.close(master)

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


if __name__ == "__main__":
    unittest.main()
