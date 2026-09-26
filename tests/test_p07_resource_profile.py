#!/usr/bin/env python3
import importlib.util
import os
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION = os.environ.get("P07_SYSTEM_CARE_VERSION", "0.1.0-rc14")
MODULE = ROOT / "packages" / "p07-system-care" / VERSION / "lib" / "resource_profile.py"
spec = importlib.util.spec_from_file_location("p07_resource_profile", MODULE)
rp = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(rp)


def snap(cpu, mem, *, swap=0, load=0.0, pools=1, rss=96, mysql_rss=0, cloudpanel=False):
    return {
        "cpu_count": cpu, "memory_mib": mem, "swap_mib": swap,
        "load1": load, "load5": load, "load15": load,
        "php_pool_count": pools, "php_worker_rss_mib_p75": rss,
        "mysql_rss_mib": mysql_rss,
        "php_active_versions": ["8.3", "8.4"],
        "php_referenced_versions": ["8.3"],
        "cloudpanel_present": cloudpanel,
    }


class ResourceProfileTests(unittest.TestCase):
    def test_production_calibrated_1c2g_balanced(self):
        r = rp.recommend(snap(1, 2048, swap=2048, pools=16, rss=140, mysql_rss=400, cloudpanel=True), "balanced")
        self.assertEqual(r["profile_id"], "VF-RP-2G-1C-BALANCED")
        self.assertEqual(r["mysql"], {
            "innodb_buffer_pool_size_mib": 256, "max_connections": 80,
            "tmp_table_size_mib": 32, "max_heap_table_size_mib": 32,
            "table_open_cache": 1000,
        })
        self.assertEqual(r["php"]["hot_pool_max_children"], 2)
        self.assertEqual(r["php"]["unused_active_versions"], ["8.4"])
        self.assertEqual(r["evidence"]["production_calibration"], "1C_2G_BALANCED_REFERENCE")

    def test_1g_cloudpanel_is_explicitly_below_vendor_minimum(self):
        r = rp.recommend(snap(1, 1024, cloudpanel=True), "balanced")
        self.assertIn("BELOW_CLOUDPANEL_MINIMUM_RAM", r["notes"])
        self.assertEqual(r["mysql"]["innodb_buffer_pool_size_mib"], 128)
        self.assertEqual(r["mysql"]["max_connections"], 40)

    def test_cloudpanel_2g_band_does_not_false_warn_for_reserved_memory(self):
        r = rp.recommend(snap(1, 1950, cloudpanel=True), "balanced")
        self.assertEqual(r["hardware"]["band"], "2G")
        self.assertNotIn("BELOW_CLOUDPANEL_MINIMUM_RAM", r["notes"])

    def test_2c4g_and_4c8g_balanced_baselines(self):
        r4 = rp.recommend(snap(2, 4096, swap=2048, rss=100), "balanced")
        self.assertEqual(r4["mysql"]["innodb_buffer_pool_size_mib"], 512)
        self.assertEqual(r4["mysql"]["max_connections"], 120)
        self.assertEqual(r4["php"]["hot_pool_max_children"], 4)
        r8 = rp.recommend(snap(4, 8192, swap=1024, rss=100), "balanced")
        self.assertEqual(r8["mysql"]["innodb_buffer_pool_size_mib"], 1024)
        self.assertEqual(r8["mysql"]["max_connections"], 200)
        self.assertEqual(r8["php"]["hot_pool_max_children"], 8)

    def test_modes_are_ordered(self):
        s = snap(2, 4096, rss=110)
        c = rp.recommend(s, "conservative")
        b = rp.recommend(s, "balanced")
        p = rp.recommend(s, "performance")
        for key in ("innodb_buffer_pool_size_mib", "max_connections"):
            self.assertLessEqual(c["mysql"][key], b["mysql"][key])
            self.assertLessEqual(b["mysql"][key], p["mysql"][key])
        self.assertLessEqual(c["php"]["hot_pool_max_children"], b["php"]["hot_pool_max_children"])
        self.assertLessEqual(b["php"]["hot_pool_max_children"], p["php"]["hot_pool_max_children"])

    def test_worker_rss_reduces_aggregate_budget(self):
        small = rp.recommend(snap(2, 4096, rss=80), "balanced")
        large = rp.recommend(snap(2, 4096, rss=200), "balanced")
        self.assertGreater(small["php"]["aggregate_children_budget"], large["php"]["aggregate_children_budget"])

    def test_custom_large_memory_is_bounded(self):
        r = rp.recommend(snap(8, 16384, swap=1024, rss=128), "balanced")
        self.assertEqual(r["hardware"]["band"], "Custom")
        self.assertGreaterEqual(r["mysql"]["innodb_buffer_pool_size_mib"], 1536)
        self.assertLessEqual(r["mysql"]["innodb_buffer_pool_size_mib"], 4096)
        self.assertLessEqual(r["mysql"]["max_connections"], 300)
        self.assertLessEqual(r["php"]["hot_pool_max_children"], 12)

    def test_matrix_has_all_requested_hardware_cells(self):
        rows = rp.matrix("balanced")
        self.assertEqual(len(rows), 12)
        cells = {(r["hardware"]["memory_mib"], r["hardware"]["cpu_count"]) for r in rows}
        self.assertEqual(cells, {(m, c) for m in (1024, 2048, 4096, 8192) for c in (1, 2, 4)})

    def test_engine_is_read_only_contract(self):
        r = rp.recommend(snap(1, 2048), "balanced")
        self.assertEqual(r["write_boundary"], "READ_ONLY_RECOMMENDATION")


if __name__ == "__main__":
    unittest.main()
