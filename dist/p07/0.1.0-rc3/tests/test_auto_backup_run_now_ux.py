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
CRON_MARKER = "# P07 VF Server Ops automatic dual-remote backup"


class ImmediateBackupUxTests(unittest.TestCase):
    def _run_menu(
        self,
        payload,
        rc: int,
        *,
        malformed: bool = False,
        preconfigured: bool = True,
        cron_owned: bool = False,
        menu_input: str = "3\n\n0\n",
        status_payload: dict | None = None,
    ) -> tuple[str, bool, bool]:
        with tempfile.TemporaryDirectory(prefix="p07-run-now-ux-") as td:
            root = Path(td)
            (root / "bin").mkdir()
            (root / "lib").mkdir()
            (root / "fakebin").mkdir()

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

            status_file = root / "status.txt"
            if status_payload is None:
                status_payload = {
                    "schema": "vf-server-ops.auto-backup-status.v1",
                    "status": "ATTENTION",
                    "enabled": True,
                    "cron_installed": False,
                    "storage_state": "CONFIGURED",
                    "sites": ["example.com"],
                    "last_run": None,
                }
            status_file.write_text(json.dumps(status_payload, ensure_ascii=False), encoding="utf-8")

            engine = root / "lib" / "auto_backup.py"
            engine.write_text(
                "#!/usr/bin/env python3\n"
                "import json,os,sys\n"
                "from pathlib import Path\n"
                "cmd=sys.argv[1] if len(sys.argv)>1 else ''\n"
                "if cmd == 'configure':\n"
                "    cfg=Path(sys.argv[sys.argv.index('--config')+1])\n"
                "    cfg.parent.mkdir(parents=True,exist_ok=True)\n"
                "    cfg.write_text('{}\\n',encoding='utf-8')\n"
                "    print('{}')\n"
                "    raise SystemExit(0)\n"
                "if cmd == 'run':\n"
                "    print(open(os.environ['P07_TEST_RESULT_FILE'], encoding='utf-8').read(), end='')\n"
                "    raise SystemExit(int(os.environ['P07_TEST_RESULT_RC']))\n"
                "if cmd == 'status':\n"
                "    print(open(os.environ['P07_TEST_STATUS_FILE'], encoding='utf-8').read(), end='')\n"
                "    raise SystemExit(12)\n"
                "if cmd == 'schedule-check':\n"
                "    print(json.dumps({'status':'CLEAR','requested_at':'03:30','recommended_at':'03:30','collision_count':0}))\n"
                "    raise SystemExit(0)\n"
                "if cmd == 'install-cron':\n"
                "    cron=Path(sys.argv[sys.argv.index('--cron-file')+1])\n"
                "    cron.write_text(os.environ['P07_TEST_CRON_MARKER']+'\\n',encoding='utf-8')\n"
                "    print('{}')\n"
                "    raise SystemExit(0)\n"
                "print('{}')\n"
                "raise SystemExit(0)\n",
                encoding="utf-8",
            )
            engine.chmod(0o755)

            core = root / "bin" / "vfops"
            core.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "if [[ ${1:-} == storage ]]; then\n"
                "  printf '%s\\n' '{\"accounts\":[{\"provider\":\"google\",\"enabled\":true,\"health\":\"OK\"},{\"provider\":\"b2\",\"enabled\":true,\"health\":\"OK\"}]}'\n"
                "  exit 0\n"
                "fi\n"
                "if [[ ${1:-} == inventory ]]; then\n"
                "  printf '%s\\n' '{\"sites\":[{\"domain\":\"example.com\"}]}'\n"
                "  exit 0\n"
                "fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            core.chmod(0o755)

            setup = root / "bin" / "vfops-storage-setup"
            setup.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            setup.chmod(0o755)

            rclone = root / "fakebin" / "rclone"
            rclone.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            rclone.chmod(0o755)

            auto_cfg = root / "auto-backup.json"
            if preconfigured:
                auto_cfg.write_text("{}\n", encoding="utf-8")
            state = root / "state.json"
            storage = root / "storage.json"
            storage.write_text("{}\n", encoding="utf-8")
            cron = root / "p07.cron"
            if cron_owned:
                cron.write_text(CRON_MARKER + "\n", encoding="utf-8")

            env = os.environ.copy()
            env.update({
                "PATH": str(root / "fakebin") + os.pathsep + env.get("PATH", ""),
                "VFOPS_AUTO_BACKUP_CONFIG": str(auto_cfg),
                "VFOPS_AUTO_BACKUP_STATE": str(state),
                "VFOPS_AUTO_BACKUP_CRON": str(cron),
                "VFOPS_STORAGE_CONFIG": str(storage),
                "P07_TEST_RESULT_FILE": str(result_file),
                "P07_TEST_RESULT_RC": str(rc),
                "P07_TEST_STATUS_FILE": str(status_file),
                "P07_TEST_CRON_MARKER": CRON_MARKER,
            })

            proc = subprocess.run(
                ["bash", str(menu)],
                input=menu_input,
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return proc.stdout + proc.stderr, auto_cfg.exists(), cron.exists()

    def test_first_verification_can_run_before_scheduler_and_keeps_cron_absent(self):
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
        output, config_exists, cron_exists = self._run_menu(payload, 0, preconfigured=False)
        self.assertTrue(config_exists)
        self.assertFalse(cron_exists)
        self.assertIn("尚未启用定时备份", output)
        self.assertIn("首次验证配置：READY", output)
        self.assertIn("定时任务：尚未安装", output)
        self.assertIn("最终：PASS", output)
        self.assertIn("定时备份仍未开启", output)
        self.assertIn("选择“2. 启用 / 更新自动备份”", output)
        self.assertIn("本次验证不会创建或修改 P07 Cron", output)

    def test_first_scheduler_enable_is_blocked_until_previous_dual_remote_pass(self):
        payload = {"schema": "vf-server-ops.auto-backup-run.v1", "status": "FAIL", "sites": []}
        status_payload = {
            "schema": "vf-server-ops.auto-backup-status.v1",
            "status": "ATTENTION",
            "enabled": True,
            "cron_installed": False,
            "storage_state": "CONFIGURED",
            "sites": ["example.com"],
            "last_run": {"status": "FAIL", "sites": []},
        }
        output, _, cron_exists = self._run_menu(
            payload,
            12,
            preconfigured=True,
            menu_input="2\n\n0\n",
            status_payload=status_payload,
        )
        self.assertFalse(cron_exists)
        self.assertIn("首次启用定时备份前，必须先完成一次真实双远程备份验证", output)
        self.assertIn("定时任务：未安装", output)
        self.assertIn("没有修改 Cron", output)
        self.assertIn("SOURCE 保留", output)

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
        output, _, _ = self._run_menu(payload, 12)
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
        self.assertIn("定时备份仍未开启", output)
        self.assertNotIn("DO-NOT-PRINT-RUN-SECRET", output)
        self.assertNotIn('"schema"', output)

    def test_busy_is_safe_yield_not_failure_for_enabled_scheduler(self):
        payload = {
            "schema": "vf-server-ops.auto-backup-run.v1",
            "status": "SKIPPED_BUSY",
            "reason": "BACKUP_RESTORE_MIGRATION_OR_STORAGE_ACTIVE",
            "sites": [],
            "dns_changed": False,
            "source_deleted": False,
        }
        output, _, cron_exists = self._run_menu(payload, 0, cron_owned=True)
        self.assertTrue(cron_exists)
        self.assertIn("服务器忙，已安全让路", output)
        self.assertIn("无需修复", output)
        self.assertIn("等待下一次计划任务", output)
        self.assertIn("DNS 未修改", output)
        self.assertIn("SOURCE 保留", output)

    def test_malformed_failure_is_fail_closed_without_raw_payload_echo(self):
        marker = "MALFORMED-DO-NOT-PRINT-SECRET"
        output, _, _ = self._run_menu(marker, 12, malformed=True)
        self.assertIn("自动备份返回格式异常", output)
        self.assertIn("不会把这次执行标记为成功", output)
        self.assertIn("查看自动备份状态", output)
        self.assertIn("SOURCE 保留", output)
        self.assertIn("定时任务：未开启", output)
        self.assertNotIn(marker, output)

    def test_unexpected_engine_rc_is_fail_closed_without_raw_payload_echo(self):
        marker = "UNEXPECTED-RC-DO-NOT-PRINT-SECRET"
        output, _, _ = self._run_menu(marker, 2, malformed=True)
        self.assertIn("自动备份执行失败，未取得可读结果", output)
        self.assertIn("不会把这次执行标记为成功", output)
        self.assertIn("查看自动备份状态", output)
        self.assertIn("设置 / 检查 Google + B2", output)
        self.assertIn("DNS 未修改", output)
        self.assertIn("SOURCE 保留", output)
        self.assertIn("定时任务：未开启", output)
        self.assertNotIn(marker, output)

    def test_pass_with_existing_scheduler_remains_structured_and_requires_no_action(self):
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
        output, _, cron_exists = self._run_menu(payload, 0, cron_owned=True)
        self.assertTrue(cron_exists)
        self.assertIn("最终：PASS", output)
        self.assertIn("定时保护保持启用，无需操作", output)
        self.assertIn("SOURCE 保留", output)


if __name__ == "__main__":
    unittest.main()
