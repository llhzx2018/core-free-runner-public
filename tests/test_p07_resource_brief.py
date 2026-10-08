#!/usr/bin/env python3
"""Isolated UI tests. No real MySQL, PHP, CloudPanel, services or config writes."""
import importlib.util
import pathlib
import sys
import unittest

SRC=pathlib.Path(__file__).resolve().parents[1]/"packages/p07-system-care/0.1.0-rc44/lib"
sys.path.insert(0,str(SRC))
import resource_brief as rb

class CompactResourceTest(unittest.TestCase):
    def setUp(self):
        self.snap={"cpu_count":1,"memory_mib":1966,"swap_mib":2047,"cloudpanel_present":True,"mysql_present":True}
        self.plan={"eligible":True,"mysql_changes":[{"change":False}],"php_changes":[{"change":True}]*16,"block_reasons":[]}

    def test_below_nominal_2048_does_not_falsely_mark_unavailable(self):
        output=rb.compact_view(self.snap,self.plan,"overview")
        self.assertIn("符合初步条件",output)
        self.assertIn("PHP 16 项",output)
        self.assertNotIn("不可自动调整",output)
        self.assertNotIn("低于 CloudPanel 2GB",output)

    def test_real_plan_blocker_respected(self):
        self.plan["eligible"]=False
        self.plan["block_reasons"]=["MYSQL_NOT_DETECTED","PROFILE_CALIBRATION_STATE:CANDIDATE"]
        output=rb.compact_view(self.snap,self.plan,"overview")
        self.assertIn("只允许查看，不可自动调整",output)
        self.assertIn("未检测到 MySQL",output)
        self.assertNotIn("涉及调整",output)

    def test_plan_matches_overview(self):
        self.assertIn("通过初步校验",rb.compact_view(self.snap,self.plan,"plan"))
        self.plan["eligible"]=False
        self.assertIn("当前不可应用",rb.compact_view(self.snap,self.plan,"plan"))

    def test_verified_result_is_compact_and_no_long_path(self):
        output=rb.compact_result({"state":"APPLIED_VERIFIED","profile_id":"VF-RP-2G-1C-BALANCED","backup_dir":"/var/lib/vf-system-care/resource-backups/20261008-999999-VF-RP-2G-1C-BALANCED"})
        self.assertIn("配置已应用且验证通过",output)
        self.assertIn("恢复副本",output)
        self.assertNotIn("/var/lib/",output)
        self.assertLessEqual(len(output.splitlines()),3)

    def test_unverified_result_does_not_claim_pass(self):
        with self.assertRaises(ValueError):
            rb.compact_result({"state":"IN_PROGRESS","backup_dir":"/tmp/nonexistent"})

if __name__=="__main__":
    unittest.main()
