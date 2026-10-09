"""P07 MariaDB 10.11 future fresh-server bootstrap policy; no VPS calls."""
import pathlib
import sys
import unittest

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

    def test_migration_safety_preserved(self):
        code=(ROOT/"lib/server_migration.py").read_text(encoding="utf8")
        self.assertIn("CLOUDPANEL_BOOTSTRAP_DB_ENGINE",code)
        self.assertIn("target is not empty enough for automatic CloudPanel bootstrap",code)
        self.assertIn("installer_checksum_verified",code)
        self.assertIn("source_changed",code)

if __name__=="__main__":
    unittest.main()
