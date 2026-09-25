#!/usr/bin/env python3
import importlib.util
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION = os.environ.get("P07_SYSTEM_CARE_VERSION", "0.1.0-rc14")
LIB = ROOT / "packages" / "p07-system-care" / VERSION / "lib"

spec_rp = importlib.util.spec_from_file_location("resource_profile", LIB / "resource_profile.py")
rp = importlib.util.module_from_spec(spec_rp)
assert spec_rp.loader is not None
spec_rp.loader.exec_module(rp)
sys.modules["resource_profile"] = rp

spec_ra = importlib.util.spec_from_file_location("resource_apply", LIB / "resource_apply.py")
ra = importlib.util.module_from_spec(spec_ra)
assert spec_ra.loader is not None
spec_ra.loader.exec_module(ra)

MYSQL = """[mysqld]
table_open_cache = 4000
innodb_buffer_pool_size = 512M
tmp_table_size = 128M
max_heap_table_size = 128M
max_connections = 512
"""

POOL = """[www3.example.com]
listen = 127.0.0.1:18003
pm = ondemand
pm.max_children = 250
pm.process_idle_timeout = 10s
pm.max_requests = 100
"""


def fixture(root, *, cpu=1, mem=2048, max_children=250, duplicate_mysql=False):
    mysql = root / "etc/mysql/mysql.conf.d/mysqld.cnf"
    mysql.parent.mkdir(parents=True)
    body = MYSQL + ("\nmax_connections = 999\n" if duplicate_mysql else "")
    mysql.write_text(body)
    pool = root / "etc/php/8.3/fpm/pool.d/www3.example.com.conf"
    pool.parent.mkdir(parents=True)
    pool.write_text(POOL.replace("pm.max_children = 250", f"pm.max_children = {max_children}"))
    snap = {
        "cpu_count": cpu, "memory_mib": mem, "swap_mib": 2048, "load1": 0.5,
        "php_pool_count": 1, "php_worker_rss_mib_p75": 140, "mysql_rss_mib": 400,
        "cloudpanel_present": True, "mysql_present": True, "mysql_flavor": "mysql",
        "php_active_versions": ["8.3", "8.4"], "php_referenced_versions": ["8.3"],
        "php_referenced_pools": [{
            "version": "8.3", "pool": "www3.example.com",
            "file": "/etc/php/8.3/fpm/pool.d/www3.example.com.conf",
        }],
    }
    return snap, rp.recommend(snap, "balanced"), mysql, pool


class ResourceApplyTests(unittest.TestCase):
    def test_1c2g_plan_is_eligible_and_cap_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); snap,rec,_,_=fixture(root)
            plan=ra.build_plan(snap,rec,root=root)
            self.assertTrue(plan["eligible"]); self.assertTrue(plan["cap_only"])
            self.assertEqual({x["key"]:x["new_raw"] for x in plan["mysql_changes"]},{
                "innodb_buffer_pool_size":"256M","max_connections":"80",
                "tmp_table_size":"32M","max_heap_table_size":"32M","table_open_cache":"1000"})
            self.assertEqual(plan["php_changes"][0]["effective"],2)

    def test_uncalibrated_4g_is_preview_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); snap,_,_,_=fixture(root,cpu=2,mem=4096)
            plan=ra.build_plan(snap,rp.recommend(snap,"balanced"),root=root)
            self.assertFalse(plan["eligible"])
            self.assertIn("PROFILE_NOT_PRODUCTION_CALIBRATED",plan["block_reasons"])

    def test_cap_only_never_increases_lower_existing_values(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); snap,rec,mysql,_=fixture(root,max_children=1)
            mysql.write_text("""[mysqld]
table_open_cache = 500
innodb_buffer_pool_size = 128M
tmp_table_size = 16M
max_heap_table_size = 16M
max_connections = 40
""")
            plan=ra.build_plan(snap,rec,root=root)
            self.assertTrue(plan["eligible"])
            self.assertTrue(all(not x["change"] for x in plan["mysql_changes"]))
            self.assertFalse(plan["php_changes"][0]["change"])
            self.assertEqual(plan["php_changes"][0]["effective"],1)

    def test_duplicate_mysql_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); snap,rec,_,_=fixture(root,duplicate_mysql=True)
            plan=ra.build_plan(snap,rec,root=root)
            self.assertFalse(plan["eligible"])
            self.assertTrue(any(x.startswith("MYSQL_CONFIG_KEY_COUNT:max_connections:2") for x in plan["block_reasons"]))

    def test_synthetic_apply_and_rollback_restore_exact_bytes(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as bd:
            root=pathlib.Path(td); snap,rec,mysql,pool=fixture(root)
            before_mysql=mysql.read_bytes(); before_pool=pool.read_bytes()
            plan=ra.build_plan(snap,rec,root=root)
            state=ra.synthetic_apply(plan,root,pathlib.Path(bd)/"backup")
            self.assertIn("256M",mysql.read_text())
            self.assertIn("max_connections = 80",mysql.read_text())
            self.assertIn("pm.max_children = 2",pool.read_text())
            ra.synthetic_rollback(state)
            self.assertEqual(mysql.read_bytes(),before_mysql)
            self.assertEqual(pool.read_bytes(),before_pool)

    def test_mariadb_apply_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); snap,rec,_,_=fixture(root); snap["mysql_flavor"]="mariadb"
            plan=ra.build_plan(snap,rec,root=root)
            self.assertFalse(plan["eligible"])
            self.assertIn("MYSQL_FLAVOR_NOT_SUPPORTED",plan["block_reasons"])

    def test_unused_php_is_suggestion_not_automatic_disable(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); snap,rec,_,_=fixture(root)
            plan=ra.build_plan(snap,rec,root=root)
            self.assertIn("php8.4-fpm",plan["unused_php_services"])
            self.assertFalse(plan["automatic_service_disable"])


if __name__=="__main__":
    unittest.main()
