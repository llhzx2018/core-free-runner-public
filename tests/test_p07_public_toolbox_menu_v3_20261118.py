"""Public P07 toolbox five-module terminal UX: only safe menu, help and no-write paths."""
from __future__ import annotations
import fcntl
import math
import os
import re
import struct
import termios
import unicodedata
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
            if data!=b"0\n":
                raise AssertionError("only safe zero-exit PTY input allowed")
            sent=False
            end=time.monotonic()+8
            while time.monotonic()<end:
                readable,_,_=select.select([master],[],[],0.1)
                if readable:
                    try: out.extend(os.read(master,65536))
                    except OSError: break
                    if not sent and "请选择 [0-5]：".encode("utf-8") in out:
                        # Bash prints the prompt just before entering read;
                        # writing beforehand can race with shell TTY setup.
                        time.sleep(0.08)
                        os.write(master,data)
                        sent=True
                if proc.poll() is not None: break
            self.assertTrue(sent,"menu did not show owner prompt")
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

    def test_actual_main_and_m03_route_fit_both_terminal_sizes(self):
        # Real complete public entry, only no-write paths (main invalid input,
        # M03 version selector, then 0 return); no installer or business action.
        def cells(line):
            return sum(0 if unicodedata.combining(c) else
                       2 if ord(c)>127 and unicodedata.east_asian_width(c) in ("W","F","A")
                       else 1 for c in line)

        for cols in (80,40):
            for color_mode in ("NO_COLOR","TERM_DUMB"):
                with self.subTest(cols=cols,color_mode=color_mode):
                    master,slave=pty.openpty()
                    fcntl.ioctl(slave,termios.TIOCSWINSZ,
                                struct.pack("HHHH",24,cols,0,0))
                    env={**os.environ,"TERM":"xterm"}
                    env.pop("NO_COLOR",None)
                    if color_mode=="NO_COLOR":
                        env["NO_COLOR"]="1"
                    else:
                        env["TERM"]="dumb"
                    proc=subprocess.Popen(["bash",str(SHELL)],stdin=slave,
                          stdout=slave,stderr=slave,env=env)
                    os.close(slave)
                    output=bytearray()

                    def observe(prompt,answer,assertions):
                        target=prompt.encode("utf-8")
                        end=time.monotonic()+8
                        while time.monotonic()<end:
                            pos=output.find(target)
                            if pos>=0:
                                stop=pos+len(target)
                                screen=bytes(output[:stop]).decode("utf-8","replace")
                                del output[:stop]
                                self.assertNotIn("\033[",screen)
                                lines=screen.replace("\r","").splitlines()
                                width=max([cells(line) for line in lines]+[0])
                                rows=sum(max(1,math.ceil(cells(line)/cols)) for line in lines)
                                self.assertLessEqual(width,cols,screen)
                                self.assertLessEqual(rows,24,screen)
                                for token in assertions:
                                    self.assertIn(token,screen)
                                os.write(master,(answer+"\n").encode())
                                return
                            ready,_,_=select.select([master],[],[],0.1)
                            if ready:
                                try: output.extend(os.read(master,65536))
                                except OSError: break
                            if proc.poll() is not None: break
                        self.fail("Expected actual menu prompt missing")

                    try:
                        observe("请选择 [0-5]：","3",
                                ["功能：5 项","0. 退出"])
                        observe("请选择 [0-2]：","0",
                                ["进入正式版","0.1.0-release146","独立维护版",
                                 "0.1.0-release147-rc4","迁移未验收","0. 返回"])
                        observe("请选择 [0-5]：","0",["功能：5 项"])
                        self.assertEqual(proc.wait(timeout=5),0)
                    finally:
                        if proc.poll() is None:
                            proc.kill();proc.wait(timeout=2)
                        os.close(master)

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

    def test_module_error_errexit_isolated_from_real_toolbox_menu(self):
        # Exercise the exact Bash menu and real shell option semantics.
        # External module operations are deliberately replaced with exit codes:
        # this is failure propagation coverage, not business acceptance.
        code=SHELL.read_text(encoding="utf-8")
        menu="main_menu() {"+code.split("main_menu() {",1)[1].split("\n}\n",1)[0]+"\n}\n"
        routes=(("1","run_network_node","网络代理节点"),
                ("2","run_vps_audit","服务器性能检测"),
                ("3\n1","run_server_ops","网站与数据"),
                ("3\n2","run_m03_owner_trial","网站与数据"),
                ("4","run_system_care","服务器维护与安全"),
                ("5","run_server_init","新服务器初始化"))
        for selection,expected,label in routes:
            for rc in (0,13):
                with self.subTest(route=expected,rc=rc):
                    prelude="""set -Eeuo pipefail
C_YELLOW='' C_RESET='' C_GRAY=''
VF_SERVER_OPS_BUILD_EXPECTED=stable M03_OWNER_TRIAL_BUILD=trial
say() { printf '%s\\n' "$*"; }
screen_clear() { :; }
show_header() { :; }
show_menu() { printf 'MENU_READY\\n'; }
pause_menu() { :; }
"""
                    # Actual module wrappers restore errexit before returning.
                    # Isolating the call must preserve both this behavior and its status.
                    stubs="\n".join(f'{name}() {{ printf "\\nCALL:{name}\\n"; set -e; return {rc}; }}'
                                     for _,name,_ in routes)
                    issue="show_module_issue() {"+code.split("show_module_issue() {",1)[1].split("\n}\n",1)[0]+"\n}\n"
                    result=subprocess.run(["bash","-c",prelude+stubs+"\n"+issue+menu+"\nmain_menu\n"],
                        input=selection+"\n0\n",text=True,capture_output=True,timeout=5,
                        env={**os.environ,"NO_COLOR":"1","TERM":"dumb"})
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertEqual(result.stdout.count("MENU_READY"),2,result.stdout)
                    self.assertEqual([line for line in result.stdout.splitlines() if line.startswith("CALL:")],
                                     ["CALL:"+expected])
                    if rc:
                        self.assertIn("未完成 · "+label,result.stdout)
                    else:
                        self.assertNotIn("未完成 · ",result.stdout)

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
        self.assertIn("exact_confirm",(
            ROOT/"packages/p07-network-node/0.1.0-ux2/lib/common.sh").read_text())
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
