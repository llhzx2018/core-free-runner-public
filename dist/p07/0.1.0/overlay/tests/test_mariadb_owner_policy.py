"""P07 OS-matched MariaDB bootstrap and live endpoint guards; no VPS calls."""
import pathlib
import sys
import unittest
import subprocess
from unittest import mock

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"lib"))
import server_migration as m


class MariaDBDefaultPolicy(unittest.TestCase):
    def test_cloudpanel_engine_selection_is_os_matched(self):
        for os_id, version_id, expected in (
            ("debian", "13", "MARIADB_11.8"),
            ("debian", "12", "MARIADB_10.11"),
            ("ubuntu", "22.04", "MARIADB_10.11"),
            ("ubuntu", "24.04", "MARIADB_10.11"),
        ):
            with self.subTest(os=(os_id, version_id)):
                self.assertEqual(m.cloudpanel_db_engine_for_os(os_id, version_id), expected)
                for cloud in ("", "vultr", "do", "aws"):
                    script = m.cloudpanel_bootstrap_script(cloud, expected)
                    self.assertIn(f"DB_ENGINE={expected}", script)
                    self.assertNotIn("DB_ENGINE=MYSQL_", script)
                    self.assertIn("sha256sum -c", script)
                    self.assertNotIn("| bash", script)
        for os_id, version_id in (("debian", "11"), ("ubuntu", "26.04"), ("other", "1")):
            with self.assertRaises(m.ServerMigrationError):
                m.cloudpanel_db_engine_for_os(os_id, version_id)
        with self.assertRaises(m.ServerMigrationError):
            m.cloudpanel_bootstrap_script("vultr", "MYSQL_8.4")
        pull = (ROOT / "lib/server_migration_pull.py").read_text(encoding="utf8")
        self.assertIn('legacy.cloudpanel_bootstrap_script(cloud_hint, preflight["db_engine"])', pull)
        self.assertIn("cloudpanel_ready_local()", pull)

    def test_existing_production_is_never_in_place_reinstalled(self):
        ui=(ROOT/"bin/vfops-init-ui").read_text(encoding="utf8")
        self.assertIn("database_engine_current() {",ui)
        self.assertIn("mariadbd --version",ui)
        self.assertIn("Debian 13：11.8",ui)
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
            with mock.patch.object(pull, "required_mariadb_engine_local", return_value="MARIADB_11.8"):
                with self.assertRaisesRegex(pull.PullMigrationError, "NEW_SERVER_REQUIRES_MARIADB_11_8"):
                    pull.require_mariadb_target()

    def test_new_server_target_accepts_exact_mariadb_1011(self):
        import server_migration_pull as pull
        with mock.patch.object(pull.shutil, "which", side_effect=lambda name: "/usr/sbin/mariadbd" if name == "mariadbd" else None), mock.patch.object(
            pull.subprocess, "run",
            return_value=subprocess.CompletedProcess(["mariadbd", "--version"], 0, "mariadbd  Ver 10.11.14-MariaDB-0+deb12u2 for debian-linux-gnu on x86_64", ""),
        ):
            self.assertEqual(pull.local_target_db_engine_version(), "MARIADB_10.11")
            with mock.patch.object(pull, "local_target_active_db_engine_version", return_value="MARIADB_10.11"):
                with mock.patch.object(pull, "required_mariadb_engine_local", return_value="MARIADB_10.11"):
                    self.assertIsNone(pull.require_mariadb_target())

    def test_other_mariadb_and_unreadable_are_fail_closed(self):
        import server_migration_pull as pull
        with mock.patch.object(pull, "required_mariadb_engine_local", return_value="MARIADB_11.8"):
            with mock.patch.object(pull, "local_target_db_engine_version", return_value="MARIADB_OTHER"):
                with self.assertRaises(pull.PullMigrationError):
                    pull.require_mariadb_target()
            with mock.patch.object(pull, "local_target_db_engine_version", return_value="UNKNOWN"):
                with self.assertRaises(pull.PullMigrationError):
                    pull.require_mariadb_target()

    def test_preflight_resume_cutover_have_target_engine_guards(self):
        pull=(ROOT/"lib/server_migration_pull.py").read_text(encoding="utf8")
        self.assertIn("def require_mariadb_target()",pull)
        self.assertIn("def target_preflight_local(",pull)
        self.assertIn("def resume_prepare_migration(",pull)
        self.assertIn("def cutover_migration(",pull)
        self.assertGreaterEqual(pull.count("    require_mariadb_target()"),3)

    def test_running_server_version_is_queried_via_unprivileged_argv_socket(self):
        import server_migration_pull as pull
        fake = subprocess.CompletedProcess(
            [], 0, "10.11.14-MariaDB-0+deb12u2\tDebian 12\n", ""
        )
        with mock.patch.object(pull.shutil, "which", side_effect=lambda name: "/usr/bin/mariadb" if name == "mariadb" else None), mock.patch.object(
            pull.subprocess, "run", return_value=fake
        ) as run:
            self.assertEqual(pull.local_target_active_db_engine_version(), "MARIADB_10.11")
            args = run.call_args.args[0]
            self.assertIn("--no-defaults", args)
            self.assertIn("--protocol=socket", args)
            self.assertIn("--user=root", args)
            self.assertFalse(any("password=" in value.lower() for value in args))

    def test_mariadb_binary_with_wrong_or_unreachable_live_server_is_blocked(self):
        import server_migration_pull as pull
        for live in ("MYSQL_OR_PERCONA", "MARIADB_OTHER", "UNKNOWN"):
            with self.subTest(live=live), mock.patch.object(
                pull, "local_target_db_engine_version", return_value="MARIADB_10.11"
            ), mock.patch.object(
                pull, "local_target_active_db_engine_version", return_value=live
            ):
                with mock.patch.object(pull, "required_mariadb_engine_local", return_value="MARIADB_10.11"):
                    with self.assertRaisesRegex(pull.PullMigrationError, "NEW_SERVER_REQUIRES_MARIADB_10_11"):
                        pull.require_mariadb_target()

    def test_live_socket_rejects_mysql_other_mariadb_and_connection_failure(self):
        import server_migration_pull as pull
        with mock.patch.object(pull.shutil, "which", return_value="/usr/bin/mariadb"):
            for version, expected in (
                ("8.4.4\tPercona Server\n", "MYSQL_OR_PERCONA"),
                ("10.6.18-MariaDB\tDebian\n", "MARIADB_OTHER"),
                ("10.11.14-MariaDB\tDebian\n", "MARIADB_10.11"),
                ("11.8.3-MariaDB\tDebian\n", "MARIADB_11.8"),
            ):
                with self.subTest(version=version), mock.patch.object(
                    pull.subprocess, "run",
                    return_value=subprocess.CompletedProcess([], 0, version, ""),
                ):
                    self.assertEqual(pull.local_target_active_db_engine_version(), expected)
            with mock.patch.object(
                pull.subprocess, "run",
                return_value=subprocess.CompletedProcess([], 1, "", "Access denied"),
            ):
                self.assertEqual(pull.local_target_active_db_engine_version(), "UNKNOWN")

    def test_debian13_mariadb_118_daemon_and_socket_must_agree(self):
        import server_migration_pull as pull
        with mock.patch.object(pull, "required_mariadb_engine_local", return_value="MARIADB_11.8"):
            with mock.patch.object(pull, "local_target_db_engine_version", return_value="MARIADB_11.8"):
                with mock.patch.object(pull, "local_target_active_db_engine_version", return_value="MARIADB_11.8"):
                    self.assertIsNone(pull.require_mariadb_target())
                with mock.patch.object(pull, "local_target_active_db_engine_version", return_value="MARIADB_10.11"):
                    with self.assertRaisesRegex(pull.PullMigrationError, "NEW_SERVER_REQUIRES_MARIADB_11_8"):
                        pull.require_mariadb_target()
            with mock.patch.object(pull, "local_target_db_engine_version", return_value="MARIADB_10.11"):
                with self.assertRaisesRegex(pull.PullMigrationError, "NEW_SERVER_REQUIRES_MARIADB_11_8"):
                    pull.require_mariadb_target()

    def test_debian13_active_mariadb_version_is_detected(self):
        import server_migration_pull as pull
        with mock.patch.object(pull.shutil, "which", return_value="/usr/sbin/mariadbd"), mock.patch.object(
            pull.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 0, "mariadbd  Ver 11.8.3-MariaDB for debian-linux-gnu on x86_64", ""),
        ):
            self.assertEqual(pull.local_target_db_engine_version(), "MARIADB_11.8")

    def test_mariadb_tuning_skip_does_not_claim_apply_pass(self):
        ui=(ROOT/"bin/vfops-init-ui").read_text(encoding="utf8")
        self.assertIn("SKIPPED_MARIADB_UNCALIBRATED", ui)
        self.assertIn("if [[ \"$block_reasons\" == 'MYSQL_FLAVOR_NOT_SUPPORTED' ]]; then", ui)
        self.assertIn("record_action SKIP '性能配置'", ui)
        self.assertIn("基础初始化完成（MariaDB 性能调优未执行）", ui)
        self.assertIn("RESOURCE_STATE='BLOCKED'", ui)

    def test_migration_safety_preserved(self):
        code=(ROOT/"lib/server_migration.py").read_text(encoding="utf8")
        self.assertIn("CLOUDPANEL_BOOTSTRAP_DB_ENGINE",code)
        self.assertIn("target is not empty enough for automatic CloudPanel bootstrap",code)
        self.assertIn("installer_checksum_verified",code)
        self.assertIn("source_changed",code)

if __name__=="__main__":
    unittest.main()
