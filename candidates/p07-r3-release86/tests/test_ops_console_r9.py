from __future__ import annotations
import json, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class OpsConsoleR9Tests(unittest.TestCase):
    def test_ops_tools_are_kept_out_of_slot3_menu(self):
        text=(ROOT/"bin/vfops-user").read_text(encoding="utf-8")
        for route in (
            '8) run_module "$DIAG_UI" ;;',
            '9) run_module "$HISTORY_UI" ;;',
            '10) run_module "$SELFCHECK_UI" ;;',
            '11) run_module "$INIT_UI" ;;',
        ):
            self.assertNotIn(route,text)
        for tool in ("vfops-diagnostics-ui","vfops-history-ui","vfops-selfcheck-ui","vfops-init-ui"):
            self.assertTrue((ROOT/"bin"/tool).is_file())
        self.assertIn("网站与数据",text)

    def test_history_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"events.jsonl"
            subprocess.run(["python3",str(ROOT/"lib/ops_history.py"),"--file",str(p),"append","--action","备份网站","--result","成功"],check=True)
            out=subprocess.check_output(["python3",str(ROOT/"lib/ops_history.py"),"--file",str(p),"list","--json"],text=True)
            rows=json.loads(out); self.assertEqual(rows[0]["action"],"备份网站"); self.assertEqual(rows[0]["result"],"成功")
            self.assertEqual(oct(p.stat().st_mode & 0o777),"0o600")

    def test_diagnostics_is_read_only_shape(self):
        out=subprocess.check_output(["python3",str(ROOT/"lib/ops_diagnostics.py"),"--json"],text=True)
        data=json.loads(out)
        self.assertEqual(data["schema"],"p07.ops-diagnostics.v1")
        self.assertIn(data["verdict"],{"OK","WARN","ERROR"})
        keys={x["key"] for x in data["checks"]}
        self.assertTrue({"p07","cloudpanel","nginx","mysql","php","disk","memory","swap","backup"} <= keys)

    def test_safety_model_is_shared(self):
        ui=(ROOT/"lib/terminal_ui.sh").read_text(encoding="utf-8")
        self.assertIn("ui_safety_tier()",ui)
        self.assertIn("ui_confirm_exact()",ui)
        migrate=(ROOT/"bin/vfops-migrate-ui").read_text(encoding="utf-8")
        self.assertIn('--confirm "CUTOVER_PULL:$mid"',migrate)
        self.assertIn("DNS_UPDATED:",migrate)
        auto=(ROOT/"bin/vfops-auto-backup").read_text(encoding="utf-8")
        self.assertIn("--confirm DISABLE_DUAL_REMOTE_AUTOBACKUP",auto)
        self.assertIn("ui_safety_tier danger",auto)

    def test_selfcheck_and_init_are_guarded(self):
        selfcheck=(ROOT/"bin/vfops-selfcheck-ui").read_text(encoding="utf-8")
        init=(ROOT/"bin/vfops-init-ui").read_text(encoding="utf-8")
        self.assertIn("现在重新安装工具运行文件？[y/N]",selfcheck)
        self.assertNotIn("ui_menu_info 1 '重新检查'",selfcheck)
        self.assertIn("apply_basic_settings_for_init",init)
        self.assertIn("BOOTSTRAP_LOCAL_CLOUDPANEL",init)
        self.assertIn("record_action SKIP 'DNS' '未修改'",init)
        self.assertIn("record_action SKIP '旧服务器' '未删除'",init)
        self.assertIn("record_action SKIP '网站 Nginx' '未自动停止或重启'",init)

if __name__=="__main__":
    unittest.main()
