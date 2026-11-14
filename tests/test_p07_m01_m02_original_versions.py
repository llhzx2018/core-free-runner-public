#!/usr/bin/env python3
"""P07-M01 网络代理节点 + P07-M02 服务器性能检测: 原作者版本只读菜单。

All remote responses are local synthetic fixtures. Never contact a live VPS, run
a remote script, install packages, change a proxy service, or run a benchmark.
"""
from __future__ import annotations

import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
M01 = ROOT / "packages/p07-network-node/0.1.0-ux2/vf-node.sh"
M02 = ROOT / "experiments/p07-vps-audit-v21-ux2.sh"


class OriginalAuthorVersionMenusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = tempfile.TemporaryDirectory(prefix="p07-original-versions-")
        self.addCleanup(self.work.cleanup)
        self.workdir = Path(self.work.name)
        fake = self.workdir / "curl"
        fake.write_text("""#!/bin/sh
case "$*" in
  *xyz690/v2ray/commits*) printf '[{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]' ;;
  *v2fly/v2ray-core/releases*) printf '[{"tag_name":"v5.56.0","prerelease":true},{"tag_name":"v5.53.0","prerelease":false}]' ;;
  *masonr/yet-another-bench-script*) printf 'YABS_VERSION="v2026-10-31"\\n' ;;
  *) printf 'Unexpected URL\\n' >&2; exit 45 ;;
esac
""", encoding="utf-8")
        fake.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": str(self.workdir) + os.pathsep + os.environ.get("PATH", ""),
            "NO_COLOR": "1",
            "TERM": "dumb",
            "HOME": str(self.workdir),
        }

    def call(self, source: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(source), *args],
            capture_output=True,
            text=True,
            timeout=12,
            cwd=self.workdir,
            env=env or self.env,
            check=False,
        )

    def test_main_menu(self) -> None:
        m1 = M01.read_text(encoding="utf-8")
        m2 = M02.read_text(encoding="utf-8")
        self.assertIn("5. 查看原作者作品版本（只读）", m1)
        self.assertIn("5) node_original_version_menu", m1)
        self.assertIn("2. 查看原作者 YABS 版本（只读）", m2)
        self.assertIn("1. 开始完整 VPS 验机", m2)
        self.assertIn("0. 返回工具箱", m2)

    def test_readonly(self) -> None:
        a = self.call(M01, "originals", "author")
        b = self.call(M02, "--original-versions")
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertIn("aaaaaaaaaaaa", a.stdout)
        self.assertIn("v2026-10-31", b.stdout)
        self.assertIn("非发行版", a.stdout)
        self.assertIn("不下载执行", b.stdout)
        self.assertEqual(list(self.workdir.iterdir()), [self.workdir / "curl"])

    def test_write_confirmation(self) -> None:
        node = M01.read_text(encoding="utf-8")
        self.assertIn("将安装新的 V2Ray 节点，确认继续？[y/N]", node)
        self.assertIn("确认修复？[y/N]", node)
        self.assertIn("run_and_pause bash", node)
        originals = node.split("node_original_version_query() {", 1)[1].split("node_original_version_menu()", 1)[0]
        self.assertNotIn("source <(", originals)
        self.assertNotIn("| bash", originals)
        self.assertNotIn("systemctl", originals)
        self.assertNotIn("apt-get", originals)

    def test_cancel_eof_invalid(self) -> None:
        # Non-TTY uses explicit read-only API and never waits for a prompt.
        a = self.call(M01, "originals", "unknown")
        self.assertEqual(a.returncode, 2)
        # EOF/invalid choices are handled before any test or node update.
        self.assertIn("read -r selection || return 0", M01.read_text(encoding="utf-8"))
        self.assertIn("read -r option || return 1", M02.read_text(encoding="utf-8"))
        self.assertIn("选择无效", M02.read_text(encoding="utf-8"))

    def test_success(self) -> None:
        a = self.call(M01, "originals", "core")
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertIn("v5.56.0（预发布）", a.stdout)
        self.assertIn("最新正式版本：v5.53.0", a.stdout)
        self.assertIn("本页只读", a.stdout)

    def test_failure_block(self) -> None:
        (self.workdir / "curl").write_text("#!/bin/sh\nexit 22\n", encoding="utf-8")
        a = self.call(M01, "originals", "core")
        b = self.call(M02, "--original-versions")
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertIn("无法读取 GitHub 官方版本", a.stdout)
        self.assertIn("无法获取原作者脚本版本", b.stdout)
        self.assertNotIn("最新公开发布：", a.stdout)
        self.assertNotIn("原作者脚本当前版本：", b.stdout)

    def test_no_color_non_tty(self) -> None:
        a = self.call(M01, "--version")
        b = self.call(M02, "--build-id")
        c = self.call(M02, "--original-versions")
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertEqual(c.returncode, 0, c.stderr)
        self.assertIn("0.1.0-ux2", a.stdout)
        self.assertIn("2.1.1-ux2", b.stdout)
        for result in (a, b, c):
            self.assertNotIn("\x1b[", result.stdout)

    def test_real_pty_menu_only_queries_originals(self) -> None:
        # A pseudo-terminal drives the actual M02 selection 2 then 0.
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            ["bash", str(M02)],
            cwd=self.workdir,
            env=self.env,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
        os.close(slave)
        try:
            os.write(master, b"2\n0\n")
            output = bytearray()
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                r, _, _ = select.select([master], [], [], 0.2)
                if r:
                    try:
                        output.extend(os.read(master, 4096))
                    except OSError:
                        break
                if proc.poll() is not None:
                    break
            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)
            self.assertIn(b"v2026-10-31", output)
            self.assertNotIn(b"YABS test", output)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)
            os.close(master)


if __name__ == "__main__":
    unittest.main()
