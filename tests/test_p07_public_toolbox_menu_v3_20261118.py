"""Public P07 toolbox five-module terminal UX: only safe menu, help and no-write paths."""
from __future__ import annotations
import os
from pathlib import Path
import pty
import select
import subprocess
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
SHELL=ROOT/"installers/p07-toolbox.sh"

class ToolboxTerminalUX(unittest.TestCase):
    def run_safe(self,*args,input_text=""):
        return subprocess.run(["bash",str(SHELL),*args],input=input_text,
          text=True,capture_output=True,timeout=12,
          env={**os.environ,"NO_COLOR":"1","TERM":"dumb"})

    def run_pty_selection(self,data:bytes):
        master,slave=pty.openpty()
        proc=subprocess.Popen(["bash",str(SHELL)],stdin=slave,
          stdout=slave,stderr=slave,env={**os.environ,"NO_COLOR":"1","TERM":"dumb"})
        os.close(slave)
        out=bytearray()
        try:
            os.write(master,data)
            end=time.monotonic()+8
            while time.monotonic()<end:
                readable,_,_=select.select([master],[],[],0.1)
                if readable:
                    try: out.extend(os.read(master,65536))
                    except OSError: break
                if proc.poll() is not None: break
            self.assertIsNotNone(proc.poll(),"no-write menu hung")
            self.assertEqual(proc.wait(timeout=1),0)
            return out.decode("utf-8","replace")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)
            os.close(master)

    def test_main_menu_five_clear_actions_and_no_implicit_install(self):
        out=self.run_pty_selection(b"0\n")
        self.assertIn("服务器工具箱",out)
        self.assertIn("功能：5 项",out)
        for i,label in enumerate(("网络代理节点","服务器性能检测","网站与数据",
                                   "服务器维护与安全","新服务器初始化"),1):
            self.assertIn(f"{i}. {label}",out)
        self.assertIn("0. 退出",out)
        self.assertLess(out.index("1. 网络代理节点"),out.index("5. 新服务器初始化"))
        self.assertNotIn("\033[",out)

    def test_readonly_modules_status_returns_without_install(self):
        p=self.run_safe("--modules")
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("P07-M01 网络代理节点",p.stdout)
        self.assertIn("P07-M05 新服务器初始化",p.stdout)

    def test_write_confirmation_remains_owned_by_independent_module(self):
        code=SHELL.read_text(encoding="utf-8")
        menu=code.split("main_menu() {",1)[1].split("\n}\n",1)[0]
        self.assertIn("run_server_ops",menu)
        self.assertIn("run_server_init",menu)
        self.assertNotIn("apt-get",menu)
        self.assertNotIn("mysql ",menu)
        self.assertIn("确认仅升级 P07-M03 网站与数据",code)
        self.assertIn("[[ ! -t 0 || ! -t 1 ]]",code)

    def test_cancel_eof_invalid_input_without_unsafe_fallback(self):
        for args,input_text in (([],""),([], "9\n"),(["--unknown"],"")):
            with self.subTest(args=args,input_text=input_text):
                p=self.run_safe(*args,input_text=input_text)
                self.assertNotEqual(p.returncode,0)
                self.assertIn("终端" if not args else "未知参数",p.stderr)

    def test_successful_version_help_clear_five_independent_modules(self):
        a=self.run_safe("--version")
        b=self.run_safe("--help")
        self.assertEqual(a.returncode,0,a.stderr)
        self.assertEqual(b.returncode,0,b.stderr)
        self.assertIn("服务器工具箱 V0.1.0",a.stdout)
        self.assertIn("五模块独立安装和升级",b.stdout)
        self.assertIn("5. 新服务器初始化",b.stdout)

    def test_error_recovery_does_not_display_internal_exit_code_in_menu(self):
        code=SHELL.read_text(encoding="utf-8")
        fn=code.split("show_module_issue() {",1)[1].split("\n}\n",1)[0]
        self.assertIn("未完成",fn)
        self.assertIn("不自动重试或执行其他模块",fn)
        self.assertNotIn("退出码",fn)
        menu=code.split("main_menu() {",1)[1].split("\n}\n",1)[0]
        self.assertIn("show_module_issue '新服务器初始化'",menu)

    def test_m01_m02_m04_existing_independent_menus_have_clear_safe_exit(self):
        m01=(ROOT/"packages/p07-network-node/0.1.0-ux2/vf-node.sh").read_text()
        m02=(ROOT/"experiments/p07-vps-audit-v21-ux2.sh").read_text()
        m04=(ROOT/"packages/p07-system-care/0.1.0-ux4/vf-system-care.sh").read_text()
        for source,token,back in (
            (m01,"当前状态","0. 返回工具箱"),
            (m02,"查看原作者 YABS 版本","0. 返回工具箱"),
            (m04,"检查服务器健康（完整）","ui_menu_back 0 '返回工具箱'")):
            self.assertIn(token,source)
            self.assertIn(back,source)
        self.assertIn("exact_confirm",m01)
        self.assertIn("confirm_numeric",(
            ROOT/"packages/p07-system-care/0.1.0-ux4/lib/common.sh").read_text())
        self.assertIn("menu()",m04)

    def test_m01_m02_m04_help_paths_do_not_start_server_actions(self):
        for path,expected in (
            ("packages/p07-network-node/0.1.0-ux2/vf-node.sh","vf-node"),
            ("experiments/p07-vps-audit-v21-ux2.sh","服务器性能检测"),
            ("packages/p07-system-care/0.1.0-ux4/vf-system-care.sh","服务器维护与安全")):
            with self.subTest(path=path):
                p=subprocess.run(["bash",str(ROOT/path),"--help"],
                    capture_output=True,text=True,timeout=12,
                    env={**os.environ,"NO_COLOR":"1","TERM":"dumb"})
                self.assertEqual(p.returncode,0,p.stderr)
                self.assertIn(expected,p.stdout)
                self.assertNotIn("\033[",p.stdout)

    def test_no_color_and_non_tty_never_emit_ansi_or_clean_screen(self):
        for flag in ("--help","--version","--modules"):
            p=self.run_safe(flag)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertNotIn("\033[",p.stdout)
        code=SHELL.read_text(encoding="utf-8")
        self.assertIn("screen_clear() { if [[ -t 0 && -t 1",code)
        self.assertIn("NO_COLOR",code)

if __name__=="__main__":
    unittest.main()
