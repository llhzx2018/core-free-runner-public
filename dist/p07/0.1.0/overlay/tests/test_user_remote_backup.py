from __future__ import annotations

import os
import unittest

from tests.test_user_entry import UserEntryTests


class BeginnerRemoteBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = UserEntryTests(
            methodName="test_symlink_entry_resolves_real_root_and_version"
        )
        self.harness.setUp()
        core = self.harness.root / "bin" / "vfops"
        original = core.read_text(encoding="utf-8")
        storage_case = r'''  storage)
    if [[ "${VFOPS_TEST_STORAGE_FAIL:-0}" == "1" ]]; then
      printf 'raw-storage-private-detail should-not-surface\n' >&2
      printf 'VFOPS_DIAGNOSTIC_V1 stage=STORAGE_PUSH error_class=STORAGE_ERROR blocker=REMOTE_TRANSFER_FAILED cleanup=NOT_REPORTED exit_code=4\n' >&2
      exit 4
    fi
    printf '{"schema":"vf-server-ops.storage-result.v1","status":"PASS"}\n'
    ;;
'''
        core.write_text(
            original.replace("  restore)\n", storage_case + "  restore)\n", 1),
            encoding="utf-8",
        )
        os.chmod(core, 0o755)
        self.storage_config = self.harness.tmp / "storage.json"

    def tearDown(self) -> None:
        self.harness.tearDown()

    def test_no_storage_config_adds_no_extra_question(self) -> None:
        proc = self.harness._run("2\n1\ny\n\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("备份完成 ✓", proc.stdout)
        self.assertIn("状态：已验证，可恢复", proc.stdout)
        self.assertNotIn("是否再保存一份到远程", proc.stdout)
        log = self.harness.log.read_text(encoding="utf-8")
        self.assertNotIn("storage --config", log)

    def test_configured_remote_is_one_question_and_uses_auto_target(self) -> None:
        self.storage_config.write_text("{}\n", encoding="utf-8")
        proc = self.harness._run(
            "2\n1\ny\n\n0\n",
            {"VFOPS_STORAGE_CONFIG": str(self.storage_config)},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("备份完成 ✓", proc.stdout)
        self.assertIn("状态：已验证，可恢复", proc.stdout)
        self.assertNotIn("是否再保存一份到远程", proc.stdout)
        log = self.harness.log.read_text(encoding="utf-8")
        self.assertNotIn("storage --config", log)

    def test_remote_failure_never_demotes_verified_local_backup(self) -> None:
        self.storage_config.write_text("{}\n", encoding="utf-8")
        proc = self.harness._run(
            "2\n1\ny\n\n0\n",
            {
                "VFOPS_STORAGE_CONFIG": str(self.storage_config),
                "VFOPS_TEST_STORAGE_FAIL": "1",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("备份完成 ✓", proc.stdout)
        self.assertIn("状态：已验证，可恢复", proc.stdout)
        self.assertNotIn("raw-storage-private-detail", proc.stdout + proc.stderr)
        log = self.harness.log.read_text(encoding="utf-8")
        self.assertNotIn("storage --config", log)


if __name__ == "__main__":
    unittest.main()
