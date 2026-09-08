#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

RUNTIME = Path(os.environ.get("P07_RC3_RUNTIME", "/tmp/p07-rc3"))


class ImmediateBackupUxTests(unittest.TestCase):
    def _run_menu(self, payload, rc: int, *, malformed: bool = False) -> str:
        with tempfile.TemporaryDirectory(prefix="p07-run-now-ux-") as td:
            root = Path(td)
            (root / "bin").mkdir()
            (root / "lib").mkdir()

            menu_src = RUNTIME / "bin" / "vfops-auto-backup"
            self.assertTrue(menu_src.is_file(), f"missing runtime menu: {menu_src}")
            menu = root / "bin" / "vfops-auto-backup"
            shutil.copy2(menu_src, menu)
            menu.chmod(0o755)

            result_file = root / "result.txt"
            if malformed:
                result_file.write_text(str(payload), encoding="utf-8")
            else:
                result_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            engine = root / "lib" / "auto_backup.py"
            engine.write_text(
                "#!/usr/bin/env python3\n"
                "import os,sys\n"
                "if len(sys.argv) > 1 and sys.argv[1] == 'run':\n"
                "    print(open(os.environ['P07_TEST_RESULT_FILE'], encoding='utf-8').read(), end='')\n"
                "    raise SystemExit(int(os.environ['P07_TEST_RESULT_RC']))\n"
                "print('{}')\n"
                "raise SystemExit(0)\n",
                encoding="utf-8",
            )
            engine.chmod(0o755)

            for name in ("vfops", "vfops-storage-setup"):
                path = root / "bin" / name
                path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                path.chmod(0o755)

            auto_cfg = root / "auto-backup.json"
            auto_cfg.write_text("{}\n", encoding="utf-8")
            state = root / "state.json"
            storage = root / "storage.json"
            storage.write_text("{}\n", encoding="utf-8")

            env = os.environ.copy()
            env.update({
                "VFOPS_AUTO_BACKUP_CONFIG": str(auto_cfg),
                "VFOPS_AUTO_BACKUP_STATE": str(state),
                "VFOPS_STORAGE_CONFIG": str(storage),
                "P07_TEST_RESULT_FILE": str(result_file),
                "P07_TEST_RESULT_RC": str(rc),
            })

            proc = subprocess.run(
                ["bash", str(menu)],
                input="3\n\n0\n",
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return proc.stdout + proc.stderr

    def test_partial_b2_failure_is_structured_actionable_and_secret_safe(self):
        payload = {
            "schema": "vf-server-ops.auto-backup-run.v1",
            "status": "FAIL",
            "sites": [{
                "domain": "example.com",
                "local_backup": "PASS",
                "google": "PASS",
                "b2": "FAIL",
                "dual_remote": "FAIL",
                "client_secret": "DO-NOT-PRINT-RUN-SECRET",
            }],
            "dns_changed": False,
            "source_deleted": False,
        }
        output = self._run_menu(payload, 12)
        self.assertIn("自动备份结果", output)
        self.assertIn("example.com", output)
        self.assertIn("本地：PASS", output)
        self.assertIn("Google：PASS", output)
        self.assertIn("B2：FAIL", output)
        self.assertIn("双副本：FAIL", output)
        self.assertIn("最终：FAIL", output)
        self.assertIn("设置 / 检查 Google + B2", output)
        self.assertIn("立即完整备份一次", output)
        self.assertIn("已成功的本地备份 / 远程副本会保留", output)
        self.assertIn("失败运行不会执行本地自动清理", output)
        self.assertIn("DNS 未修改", output)
        self.assertIn("SOURCE 保留", output)
        self.assertNotIn("DO-NOT-PRINT-RUN-SECRET", output)
        self.assertNotIn('"schema"', output)

    def test_busy_is_safe_yield_not_failure(self):
        payload = {
            "schema": "vf-server-ops.auto-backup-run.v1",
            "status": "SKIPPED_BUSY",
            "reason": "BACKUP_RESTORE_MIGRATION_OR_STORAGE_ACTIVE",
            "sites": [],
            "dns_changed": False,
            "source_deleted": False,
        }
        output = self._run_menu(payload, 0)
        self.assertIn("服务器忙，已安全让路", output)
        self.assertIn("无需修复", output)
        self.assertIn("等待下一次计划任务", output)
        self.assertIn("DNS 未修改", output)
        self.assertIn("SOURCE 保留", output)

    def test_malformed_failure_is_fail_closed_without_raw_payload_echo(self):
        marker = "MALFORMED-DO-NOT-PRINT-SECRET"
        output = self._run_menu(marker, 12, malformed=True)
        self.assertIn("自动备份返回格式异常", output)
        self.assertIn("不会把这次执行标记为成功", output)
        self.assertIn("查看自动备份状态", output)
        self.assertIn("SOURCE 保留", output)
        self.assertNotIn(marker, output)

    def test_unexpected_engine_rc_is_fail_closed_without_raw_payload_echo(self):
        marker = "UNEXPECTED-RC-DO-NOT-PRINT-SECRET"
        output = self._run_menu(marker, 2, malformed=True)
        self.assertIn("自动备份执行失败，未取得可读结果", output)
        self.assertIn("不会把这次执行标记为成功", output)
        self.assertIn("查看自动备份状态", output)
        self.assertIn("设置 / 检查 Google + B2", output)
        self.assertIn("DNS 未修改", output)
        self.assertIn("SOURCE 保留", output)
        self.assertNotIn(marker, output)

    def test_pass_is_structured_and_requires_no_action(self):
        payload = {
            "schema": "vf-server-ops.auto-backup-run.v1",
            "status": "PASS",
            "sites": [{
                "domain": "example.com",
                "local_backup": "PASS",
                "google": "PASS",
                "b2": "PASS",
                "dual_remote": "PASS",
            }],
            "dns_changed": False,
            "source_deleted": False,
        }
        output = self._run_menu(payload, 0)
        self.assertIn("最终：PASS", output)
        self.assertIn("本次本地 + Google + B2 已完成；无需操作", output)
        self.assertIn("SOURCE 保留", output)


if __name__ == "__main__":
    unittest.main()
