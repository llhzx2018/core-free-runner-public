"""P07 MariaDB 10.11 future fresh-server bootstrap policy; no VPS calls."""
import pathlib
import sys
import unittest
import subprocess
from unittest import mock

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"lib"))
import server_migration as m


class MariaDBDefaultPolicy(unittest.TestCase):
    def test_remote_and_local_use_single_cloudpanel_engine(self):
        self.assertEqual(m.CLOUDPANEL_BOOTSTRAP_DB_ENGINE,"MARIADB_10.11")
        for cloud in ("","vultr","do","aws"):
            script=m.cloudpanel_bootstrap_script(cloud)
            self.assertIn("DB_ENGINE=MARIADB_10.11",script)
            self.assertNotIn("DB_ENGINE=MYSQL_",script)
            self.assertIn("sha256sum -c",script)
            self.assertNotIn("| bash",script)
        pull=(ROOT/"lib/server_migration_pull.py").read_text(encoding="utf8")
        self.assertIn("legacy.cloudpanel_bootstrap_script(cloud_hint)",pull)
        self.assertIn("cloudpanel_ready_local()",pull)

    def test_existing_production_is_never_in_place_reinstalled(self):
        ui=(ROOT/"bin/vfops-init-ui").read_text(encoding="utf8")
        self.assertIn("database_engine_current() {",ui)
        self.assertIn("mariadbd --version",ui)
        self.assertIn("全新服务器默认 MariaDB 10.11",ui)
        self.assertIn("初始化绝不卸载或替换生产数据库",ui)
        self.assertIn("当前数据库：$current_db_engine",ui)
        self.assertIn("MYSQL_FLAVOR_NOT_SUPPORTED",ui)
        self.assertIn("已跳过 MySQL/Percona 自动调优",ui)
        self.assertIn("record_action KEEP 'CloudPanel' '已安装并健康，不重复安装'",ui)

    def test_new_server_target_rejects_mysql_before_migration_writes(self):
        import server_migration_pull as pull
        with mock.patch.object(pull.shutil, "which", side_effect=lambda name: "/usr/sbin/mysqld" if name == "mysqld" else None), mock.patch.object(
            pull.subprocess, "run",
            return_value=subprocess.CompletedProcess(["mysqld", "--version"], 0, "mysqld  Ver 8.4.4 for Linux on x86_64 (Percona)", ""),
        ):
            self.assertEqual(pull.local_target_db_engine_version(), "MYSQL_OR_PERCONA")
            with self.assertRaisesRegex(pull.PullMigrationError, "NEW_SERVER_REQUIRES_MARIADB_10_11"):
                pull.require_mariadb_1011_target()

    def test_new_server_target_accepts_exact_mariadb_1011(self):
        import server_migration_pull as pull
        with mock.patch.object(pull.shutil, "which", side_effect=lambda name: "/usr/sbin/mariadbd" if name == "mariadbd" else None), mock.patch.object(
            pull.subprocess, "run",
            return_value=subprocess.CompletedProcess(["mariadbd", "--version"], 0, "mariadbd  Ver 10.11.14-MariaDB-0+deb12u2 for debian-linux-gnu on x86_64", ""),
        ):
            self.assertEqual(pull.local_target_db_engine_version(), "MARIADB_10.11")
            self.assertIsNone(pull.require_mariadb_1011_target())

    def test_other_mariadb_and_unreadable_are_fail_closed(self):
        import server_migration_pull as pull
        with mock.patch.object(pull, "local_target_db_engine_version", return_value="MARIADB_OTHER"):
            with self.assertRaises(pull.PullMigrationError):
                pull.require_mariadb_1011_target()
        with mock.patch.object(pull, "local_target_db_engine_version", return_value="UNKNOWN"):
            with self.assertRaises(pull.PullMigrationError):
                pull.require_mariadb_1011_target()

    def test_preflight_resume_cutover_have_target_engine_guards(self):
        pull=(ROOT/"lib/server_migration_pull.py").read_text(encoding="utf8")
        self.assertIn("def require_mariadb_1011_target()",pull)
        self.assertIn("def target_preflight_local(",pull)
        self.assertIn("def resume_prepare_migration(",pull)
        self.assertIn("def cutover_migration(",pull)
        self.assertGreaterEqual(pull.count("    require_mariadb_1011_target()"),3)

    def test_migration_safety_preserved(self):
        code=(ROOT/"lib/server_migration.py").read_text(encoding="utf8")
        self.assertIn("CLOUDPANEL_BOOTSTRAP_DB_ENGINE",code)
        self.assertIn("target is not empty enough for automatic CloudPanel bootstrap",code)
        self.assertIn("installer_checksum_verified",code)
        self.assertIn("source_changed",code)

if __name__=="__main__":
    unittest.main()
