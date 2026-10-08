#!/usr/bin/env python3
"""Isolated no-change safety regression: never touch production services or files."""
import contextlib
import io
import pathlib
import sys
import unittest
from unittest import mock

P = pathlib.Path(__file__).resolve().parents[1] / "packages/p07-system-care/0.1.0-rc45/lib"
sys.path.insert(0, str(P))
import resource_apply as engine
import resource_brief as ui


class NoChangeRegression(unittest.TestCase):
    def setUp(self):
        self.plan = {"eligible": True, "block_reasons": [], "mysql_changes": [], "php_changes": []}
        self.snapshot = {
            "cpu_count": 1, "memory_mib": 1966, "swap_mib": 2047,
            "cloudpanel_present": True, "mysql_present": True,
        }
        self.rec = {"profile_id": "VF-RP-2G-1C-BALANCED"}

    def test_zero_change_overview_is_not_an_action(self):
        display = ui.compact_view(self.snapshot, self.plan, "overview")
        self.assertIn("当前配置符合建议，无需修改", display)
        self.assertNotIn("涉及调整", display)
        self.assertNotIn("配置已应用", display)
        with mock.patch.object(ui.profile, "detect_snapshot", return_value=self.snapshot), \
             mock.patch.object(ui.profile, "recommend", return_value=self.rec), \
             mock.patch.object(ui.engine, "build_plan", return_value=self.plan):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ui.main.__name__, "main")
                with mock.patch.object(sys, "argv", ["resource_brief.py", "overview"]):
                    self.assertEqual(ui.main(), 4)

    def test_zero_change_result_requires_no_backup(self):
        output = ui.compact_result({
            "state": "UNCHANGED_VERIFIED",
            "backup_dir": None, "profile_id": self.rec["profile_id"],
        })
        self.assertIn("配置已核对，无需修改", output)
        self.assertNotIn("恢复副本", output)
        self.assertNotIn("已应用", output)

    def test_zero_change_engine_must_not_write_or_reload(self):
        state = {
            "version": "8.4.0", "version_comment": "Percona",
            "max_connections": 100, "max_used_connections": 2,
        }
        with mock.patch.object(engine.os, "geteuid", return_value=0), \
             mock.patch.object(engine.rp, "detect_snapshot", return_value=self.snapshot), \
             mock.patch.object(engine.rp, "recommend", return_value=self.rec), \
             mock.patch.object(engine, "build_plan", return_value=self.plan), \
             mock.patch.object(engine, "_mysql_client", return_value=(["/usr/bin/false"], {})), \
             mock.patch.object(engine, "_mysql_runtime_state", return_value=state), \
             mock.patch.object(engine, "_validate_mysql") as syntax, \
             mock.patch.object(engine, "_verify_services") as health, \
             mock.patch.object(engine, "_apply_plan_files") as writes, \
             mock.patch.object(engine, "_set_mysql_globals") as mysql, \
             mock.patch.object(engine, "_reload_php") as php:
            output = engine.production_apply(
                "balanced", engine.APPLY_TOKEN, require_tty=False)
            self.assertEqual(output["state"], "UNCHANGED_VERIFIED")
            self.assertIsNone(output["backup_dir"])
            syntax.assert_called_once_with()
            health.assert_called_once_with([])
            writes.assert_not_called()
            mysql.assert_not_called()
            php.assert_not_called()

    def test_runtime_difference_does_not_trigger_false_keep(self):
        self.plan["mysql_changes"] = [{
            "key": "max_connections", "current_numeric": 100, "effective_numeric": 100,
            "change": False, "ceiling": 100, "new_raw": "100",
        }]
        runtime = {
            "max_connections": 150, "version": "8.4.0",
            "version_comment": "Percona", "max_used_connections": 2,
        }
        with mock.patch.object(engine.rp, "detect_snapshot", return_value=self.snapshot), \
             mock.patch.object(engine.rp, "recommend", return_value=self.rec), \
             mock.patch.object(engine, "build_plan", return_value=self.plan), \
             mock.patch.object(engine, "_mysql_client", return_value=(["/usr/bin/false"], {})), \
             mock.patch.object(engine, "_mysql_runtime_state", return_value=runtime), \
             mock.patch.object(engine, "_apply_plan_files", side_effect=RuntimeError("write path reached")), \
             mock.patch.object(engine.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "write path reached"):
                engine.production_apply("balanced", engine.APPLY_TOKEN, require_tty=False)


if __name__ == "__main__":
    unittest.main()
