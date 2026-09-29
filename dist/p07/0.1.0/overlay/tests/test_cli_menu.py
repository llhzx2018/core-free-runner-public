#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import pty
import select
import subprocess
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "vfops"


class CliMenuTest(unittest.TestCase):
    def test_no_arg_non_tty_stays_noninteractive(self) -> None:
        proc = subprocess.run(
            [str(CLI)], cwd=ROOT, text=True, capture_output=True, check=False, timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("用法：", proc.stdout)
        self.assertIn("vfops menu", proc.stdout)
        self.assertNotIn("请选择 [0-5/h]", proc.stdout)

    def test_status_reports_real_preproduction_closure_without_release_claim(self) -> None:
        proc = subprocess.run(
            [str(CLI), "status"], cwd=ROOT, text=True, capture_output=True, check=False, timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("发布状态：已正式发布", proc.stdout)
        self.assertIn("自动修改 DNS：禁止", proc.stdout)
        self.assertIn("自动删除源服务器：禁止", proc.stdout)
        self.assertIn("最终 DNS 切换：仅人工确认", proc.stdout)
        self.assertIn("版本：0.1.0", proc.stdout)
        self.assertNotIn("NOT_PRODUCTION", proc.stdout)

    def test_help_explains_result_semantics(self) -> None:
        proc = subprocess.run(
            [str(CLI), "--help"], cwd=ROOT, text=True, capture_output=True, check=False, timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("结果含义：", proc.stdout)
        self.assertIn("备份已创建，不等于备份已验证", proc.stdout)
        self.assertIn("TECHNICAL_CUTOVER_READY", proc.stdout)
        self.assertIn("不代表已经批准 DNS 切换", proc.stdout)
        self.assertIn("NOT_RUN / UNKNOWN / BLOCKED / FAIL 都不等于 PASS", proc.stdout)

    def test_no_arg_tty_opens_five_item_menu_and_exits_cleanly(self) -> None:
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(ROOT)
            os.execv(str(CLI), [str(CLI)])
        output = bytearray(); status: int | None = None; deadline = time.monotonic() + 15; sent_exit = False
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([fd], [], [], 0.25)
                if ready:
                    try: chunk = os.read(fd, 65536)
                    except OSError: chunk = b""
                    if chunk:
                        output.extend(chunk)
                        if b"[0-5/h]" in output and not sent_exit:
                            os.write(fd, b"0\n"); sent_exit = True
                waited, raw_status = os.waitpid(pid, os.WNOHANG)
                if waited == pid: status = raw_status; break
            if status is None:
                try: os.kill(pid, 15)
                except ProcessLookupError: pass
                _, status = os.waitpid(pid, 0); self.fail("interactive menu did not exit within timeout")
        finally:
            try: os.close(fd)
            except OSError: pass
        text = output.decode("utf-8", errors="replace").replace("\r", "")
        self.assertTrue(sent_exit, text); self.assertTrue(os.WIFEXITED(status), text); self.assertEqual(os.WEXITSTATUS(status), 0, text)
        for marker in ("CloudPanel 备份 · 恢复 · 迁移工具", "1. 服务器检查", "2. 网站备份", "3. 网站恢复", "4. 服务器迁移", "5. 备份/恢复验证", "创建可验证备份", "在新服务器运行，主动读取旧服务器并完成迁入与验证", "0. 退出", "h. 高级命令帮助"):
            self.assertIn(marker, text)

    def test_backup_submenu_exposes_clear_local_and_remote_workflows(self) -> None:
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(ROOT); os.execv(str(CLI), [str(CLI)])
        output = bytearray(); status: int | None = None; deadline = time.monotonic() + 15; stage = "MAIN"
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([fd], [], [], 0.25)
                if ready:
                    try: chunk = os.read(fd, 65536)
                    except OSError: chunk = b""
                    if chunk:
                        output.extend(chunk); text = output.decode("utf-8", errors="replace").replace("\r", "")
                        if stage == "MAIN" and "请选择 [0-5/h]" in text: os.write(fd, b"2\n"); stage = "BACKUP"
                        elif stage == "BACKUP" and "5. 从远程取回并验证备份" in text: os.write(fd, b"0\n"); stage = "RETURNED"
                        elif stage == "RETURNED" and text.count("请选择 [0-5/h]") >= 2: os.write(fd, b"0\n"); stage = "EXIT_SENT"
                waited, raw_status = os.waitpid(pid, os.WNOHANG)
                if waited == pid: status = raw_status; break
            if status is None:
                try: os.kill(pid, 15)
                except ProcessLookupError: pass
                _, status = os.waitpid(pid, 0); self.fail("backup submenu navigation did not exit within timeout")
        finally:
            try: os.close(fd)
            except OSError: pass
        text = output.decode("utf-8", errors="replace").replace("\r", "")
        self.assertEqual(stage, "EXIT_SENT", text); self.assertTrue(os.WIFEXITED(status), text); self.assertEqual(os.WEXITSTATUS(status), 0, text)
        for marker in ("[网站备份]", "1. 创建并验证本地备份", "2. 上传已验证备份到加密远程", "3. 查看远程存储状态 / Google 配额", "4. 列出可恢复的远程备份", "5. 从远程取回并验证备份"):
            self.assertIn(marker, text)
        self.assertGreaterEqual(text.count("请选择 [0-5/h]"), 2, text)

    def test_restore_submenu_separates_restore_and_runtime_workflows(self) -> None:
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(ROOT); os.execv(str(CLI), [str(CLI)])
        output = bytearray(); status: int | None = None; deadline = time.monotonic() + 15; stage = "MAIN"
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([fd], [], [], 0.25)
                if ready:
                    try: chunk = os.read(fd, 65536)
                    except OSError: chunk = b""
                    if chunk:
                        output.extend(chunk); text = output.decode("utf-8", errors="replace").replace("\r", "")
                        if stage == "MAIN" and "请选择 [0-5/h]" in text: os.write(fd, b"3\n"); stage = "RESTORE"
                        elif stage == "RESTORE" and "4. 激活运行环境：恢复用户 Cron / PM2" in text: os.write(fd, b"0\n"); stage = "RETURNED"
                        elif stage == "RETURNED" and text.count("请选择 [0-5/h]") >= 2: os.write(fd, b"0\n"); stage = "EXIT_SENT"
                waited, raw_status = os.waitpid(pid, os.WNOHANG)
                if waited == pid: status = raw_status; break
            if status is None:
                try: os.kill(pid, 15)
                except ProcessLookupError: pass
                _, status = os.waitpid(pid, 0); self.fail("restore submenu navigation did not exit within timeout")
        finally:
            try: os.close(fd)
            except OSError: pass
        text = output.decode("utf-8", errors="replace").replace("\r", "")
        self.assertEqual(stage, "EXIT_SENT", text); self.assertTrue(os.WIFEXITED(status), text); self.assertEqual(os.WEXITSTATUS(status), 0, text)
        self.assertIn("1. 先检查：生成恢复计划（零写入）", text)
        self.assertIn("2. 执行恢复：恢复到全新 CloudPanel 站点", text)
        self.assertIn("3. 运行环境检查：Cron / PM2 计划（零写入）", text)
        self.assertIn("4. 激活运行环境：恢复用户 Cron / PM2", text)


if __name__ == "__main__":
    unittest.main()
