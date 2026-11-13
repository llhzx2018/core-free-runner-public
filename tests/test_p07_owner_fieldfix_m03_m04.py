"""P07 owner-field regression: run the REAL M04 menu and M03 guard, not stubbed functions.

No VPS/CloudPanel/Migration writes; all M03 failures stop before any installation.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
M04_OLD=ROOT/"packages/p07-system-care/0.1.0-ux2/vf-system-care.sh"
M04_NEW=ROOT/"packages/p07-system-care/0.1.0-ux3/vf-system-care.sh"
M03=ROOT/"installers/p07-m03-release135-repair.sh"

class P07OwnerFieldFixTests(unittest.TestCase):
    def run_m04(self, source, input_data, **env):
        return subprocess.run(
            ["bash",str(source),"menu"],input=input_data,text=True,capture_output=True,
            env={**os.environ,"NO_COLOR":"1","P07_FORCE_INTERACTIVE":"1",**env},timeout=8
        )

    def test_old_m04_menu_reproduces_owner_crash(self):
        r=self.run_m04(M04_OLD,"0\n")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("ui_prompt: command not found",r.stderr)

    def test_fixed_m04_real_menu_exit_and_no_implicit_action(self):
        r=self.run_m04(M04_NEW,"0\n")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("服务器维护与安全",r.stdout)
        self.assertIn("请选择 [0-8]：",r.stdout)
        self.assertNotIn("ACTION:",r.stdout)
        self.assertNotIn("\x1b[",r.stdout)

    def test_fixed_m04_real_menu_invalid_and_eof(self):
        r=self.run_m04(M04_NEW,"9\n0\n")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("无效选择，请输入 0-8",r.stdout)
        eof=self.run_m04(M04_NEW,"")
        self.assertEqual(eof.returncode,0,eof.stderr)
        self.assertNotIn("command not found",eof.stderr)

    def m03_stub(self, code):
        with tempfile.TemporaryDirectory(prefix="p07-m03-failclosed-") as td:
            script=Path(td)/"curl"
            script.write_text("#!/usr/bin/env bash\n"+code+"\n",encoding="utf8")
            script.chmod(0o755)
            return subprocess.run(
                ["bash",str(M03),"install"],capture_output=True,text=True,timeout=12,
                env={**os.environ,"P07_ALLOW_NONROOT":"1","PATH":str(Path(td))+":"+os.environ["PATH"],
                     "NO_COLOR":"1"}
            )

    def test_m03_unreachable_official_asset_is_distinct_and_failclosed(self):
        r=self.m03_stub("exit 22")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("DOWNLOAD_UNAVAILABLE",r.stderr)
        self.assertNotIn("已完成本模块升级",r.stdout)

    def test_m03_wrong_download_bytes_are_never_executed(self):
        r=self.m03_stub('for a in "$@"; do if [[ "$prev" == "-o" ]]; then printf not-a-zip >"$a"; exit 0; fi; prev="$a"; done; exit 23')
        self.assertNotEqual(r.returncode,0)
        self.assertIn("HASH_MISMATCH",r.stderr)
        self.assertNotIn("开始仅升级本模块",r.stdout)

    def test_m03_help_and_version_do_not_download_or_install(self):
        for arg in ("--help","--version"):
            r=subprocess.run(["bash",str(M03),arg],capture_output=True,text=True,timeout=3)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn("P07-M03 网站与数据",r.stdout)

if __name__=="__main__":
    unittest.main()
