"""P07 empty CP2: MariaDB tuning being unsupported is a safe noncritical skip."""
import re
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
CODE = (ROOT / "bin" / "vfops-init-ui").read_text(encoding="utf-8")
M = re.search(r"(?ms)^mariadb_tuning_safe_skip\(\) \{\n.*?^\}\n", CODE)
assert M, "MariaDB-only skip guard not present"
HELPER = M.group(0)


class MariaDBInitSkipTests(unittest.TestCase):
    def shell(self, reasons, engine):
        proc = subprocess.run(
            ["bash", "-c", HELPER + '\nmariadb_tuning_safe_skip "$1" "$2"', "_",
             reasons, engine], capture_output=True, text=True, timeout=5)
        return proc.returncode

    def test_real_cp2_dual_reason_is_safe_to_skip(self):
        self.assertEqual(self.shell(
            "MYSQL_FLAVOR_NOT_SUPPORTED,MYSQL_CONFIG_NOT_FOUND",
            "MariaDB（已安装）"), 0)

    def test_reason_order_and_single_reason(self):
        for r in ("MYSQL_FLAVOR_NOT_SUPPORTED",
                  "MYSQL_CONFIG_NOT_FOUND,MYSQL_FLAVOR_NOT_SUPPORTED"):
            with self.subTest(r=r):
                self.assertEqual(self.shell(r, "MariaDB 11.8"), 0)

    def test_does_not_mask_true_non_mariadb_blockers(self):
        for r in ("MYSQL_CONFIG_NOT_FOUND",
                  "MYSQL_FLAVOR_NOT_SUPPORTED,MYSQL_LOCAL_ADMIN_TOOLING_MISSING",
                  "MYSQL_FLAVOR_NOT_SUPPORTED,MYSQL_CONFIG_NOT_FOUND,MYSQL_CONNECTION_FAILED",
                  "", "PROFILE_CALIBRATION_STATE:FAILED"):
            with self.subTest(r=r):
                self.assertNotEqual(self.shell(r, "MariaDB 11.8"), 0)

    def test_no_skip_on_other_database_engines(self):
        for engine in ("MySQL（已安装）", "Percona", "未安装或暂无法识别", ""):
            with self.subTest(engine=engine):
                self.assertNotEqual(self.shell(
                    "MYSQL_FLAVOR_NOT_SUPPORTED,MYSQL_CONFIG_NOT_FOUND", engine), 0)

    def test_state_path_keeps_original_migration_readiness_gate(self):
        self.assertIn('mariadb_tuning_safe_skip "$block_reasons" "$(database_engine_current)"', CODE)
        self.assertIn('[[ "$status" == "CLOUDPANEL_READY" ]] && resource_result_complete', CODE)
        self.assertIn("RESOURCE_STATE='SKIPPED_MARIADB_UNCALIBRATED'", CODE)
        self.assertIn("已跳过 MySQL/Percona 自动调优", CODE)


if __name__ == "__main__":
    unittest.main()
