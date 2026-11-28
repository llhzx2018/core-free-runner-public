#!/usr/bin/env python3
"""P07-M01 网络代理节点 / P07-M02 服务器性能检测 public Toolbox UX2 gate."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOLBOX=ROOT/"installers/p07-toolbox.sh"

class P07OriginalVersionsUX2Distribution(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.source=TOOLBOX.read_text(encoding="utf-8")

    def test_main_menu(self)->None:
        for marker in ("网络代理节点", "服务器性能检测", "网站与数据",
                       "服务器维护与安全", "新服务器初始化", "0."):
            self.assertIn(marker,self.source)
        self.assertIn('VF_NODE_EXPECTED="0.1.0-ux3"',self.source)
        self.assertIn('VPS_AUDIT_BUILD_EXPECTED="2.1.1-ux4"',self.source)
        self.assertIn('M01_PREVIOUS_BUILD="0.1.0-ux2"',self.source)
        self.assertIn('VPS_AUDIT_PREVIOUS_BUILD="2.1.1-ux2"',self.source)

    def test_readonly(self)->None:
        m1=(ROOT/"packages/p07-network-node/0.1.0-ux2/vf-node.sh").read_text()
        m2=(ROOT/"experiments/p07-vps-audit-v21-ux2.sh").read_text()
        self.assertIn("查看原作者作品版本（只读）",m1)
        self.assertIn("查看原作者 YABS 版本（只读）",m2)
        self.assertIn("node_original_version_query",m1)
        self.assertIn("show_yabs_original_version",m2)

    def test_write_confirmation(self)->None:
        route=(ROOT/'installers/p07-three-ux-owner-route.py').read_text()
        self.assertIn('确认仅升级本模块？[y/N]',route)
        self.assertIn('if answer.lower()!="y":blocked',route)
        self.assertIn('p07_three_ux_route P07-M01',self.source)
        self.assertIn('p07_three_ux_route P07-M02',self.source)

    def test_cancel_eof_invalid(self)->None:
        route=(ROOT/'installers/p07-three-ux-owner-route.py').read_text()
        self.assertIn('except EOFError:',route)
        self.assertIn('if not sys.stdin.isatty() or not sys.stdout.isatty():',route)
        self.assertIn('if answer.lower()!="y":blocked',route)
        self.assertIn('无效选择，请输入 0-5。',self.source)

    def test_success(self)->None:
        self.assertIn('M01_PREVIOUS_BUILD="0.1.0-ux2"',self.source)
        self.assertIn('VPS_AUDIT_PREVIOUS_BUILD="2.1.1-ux2"',self.source)
        self.assertIn('P07_THREE_ROUTE_BLOB=',self.source)
        self.assertIn('p07_three_ux_route P07-M02',self.source)
        self.assertIn("--rollback-m01",self.source)
        self.assertIn("--rollback-m02",self.source)

    def test_failure_block(self)->None:
        route=(ROOT/'installers/p07-three-ux-owner-route.py').read_text()
        self.assertIn('if actual!=expected:blocked',route)
        self.assertIn('installer.verify_saved(',route)
        self.assertIn('verified_new(home,module,conf)',route)
        self.assertIn('新版安装目录异常',route)
        self.assertIn('P07_THREE_ROUTE_BLOB=',self.source)

    def test_no_color_non_tty(self)->None:
        p=subprocess.run(["bash",str(TOOLBOX),"--help"],capture_output=True,text=True,
                         env={**os.environ,"NO_COLOR":"1","TERM":"dumb"},timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertNotIn("\x1b[",p.stdout)
        self.assertIn("P07-M01",p.stdout)
        self.assertIn("P07-M02",p.stdout)

if __name__=="__main__":
    unittest.main()
