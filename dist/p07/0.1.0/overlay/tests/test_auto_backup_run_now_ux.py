#!/usr/bin/env python3
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MENU = ROOT / "bin" / "vfops-auto-backup"


class AutoBackupRunNowUxContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = MENU.read_text(encoding="utf-8")
        run_match = re.search(r"\nrun_now\(\) \{\n(?P<body>.*?)\n\}\n\ndisable_auto\(\)", cls.text, re.S)
        if not run_match:
            raise AssertionError("run_now function not found")
        cls.body = run_match.group("body")

        enable_match = re.search(r"\nenable_or_update\(\) \{\n(?P<body>.*?)\n\}\n\nrun_now\(\)", cls.text, re.S)
        if not enable_match:
            raise AssertionError("enable_or_update function not found")
        cls.enable_body = enable_match.group("body")

        verify_match = re.search(r"\nfirst_verification_passed\(\) \{\n(?P<body>.*?)\n\}\n\nprepare_first_run_config\(\)", cls.text, re.S)
        if not verify_match:
            raise AssertionError("first_verification_passed function not found")
        cls.verify_body = verify_match.group("body")

    def test_fail_exit_code_is_structured_not_treated_as_transport_failure(self):
        self.assertIn('if [[ $rc -ne 0 && $rc -ne 12 ]]', self.body)
        self.assertIn("vf-server-ops.auto-backup-run.v1", self.body)
        self.assertIn("自动备份返回格式异常", self.body)

    def test_partial_remote_failure_has_actionable_result(self):
        self.assertIn("Google：", self.body)
        self.assertIn("B2：", self.body)
        self.assertIn("双副本：", self.body)
        self.assertIn("先选择“1. 设置 / 检查异地备份”", self.body)
        self.assertIn("retry_label='3. 首次验证'", self.body)
        self.assertIn("retry_label='3. 继续验证'", self.body)
        self.assertIn("retry_label='3. 立即备份全部网站'", self.body)

    def test_failure_preserves_successful_copies_and_safety_boundary(self):
        self.assertIn("已成功的本地备份 / 远程副本会保留", self.body)
        self.assertIn("失败运行不会执行本地自动清理", self.body)
        self.assertIn("DNS 未修改", self.body)
        self.assertIn("源服务器保留", self.body)
        self.assertIn("不会因本次结果删除已有手工 / 迁移备份", self.body)

    def test_busy_is_safe_yield_with_retry_guidance(self):
        self.assertIn("服务器忙，已安全让路", self.body)
        self.assertIn("无需修复", self.body)
        self.assertIn("等待下一次计划任务", self.body)

    def test_raw_json_is_not_echoed_on_expected_fail(self):
        self.assertNotIn('printf \'%s\\n\' "$output"', self.body)
        self.assertIn('2>/dev/null', self.body)

    def test_unexpected_engine_rc_is_fail_closed_without_raw_payload_echo(self):
        self.assertIn("自动备份执行失败，未取得可读结果", self.body)
        self.assertIn("不会把这次执行标记为成功", self.body)
        self.assertIn("查看备份状态", self.body)
        self.assertIn("设置 / 检查异地备份", self.body)
        self.assertNotIn('printf \'%s\\n\' "$output"', self.body)

    def test_first_run_uses_one_local_generation(self):
        self.assertIn("--keep-last 1", self.text)
        self.assertNotIn("--keep-last 7", self.text)
        self.assertIn("远端副本不随本地 1 代策略自动删除", self.text)

    def test_first_run_refreshes_current_cloudpanel_site_set_before_scheduler(self):
        self.assertIn('if [[ "$verify_mode" == "smoke" ]]', self.body)
        self.assertIn("正在准备当前全部网站的完整验证配置", self.body)
        self.assertIn("prepare_first_run_config", self.body)
        self.assertIn("不会安装定时任务（Cron）", self.body)

    def test_first_real_remote_check_starts_with_one_site(self):
        self.assertIn("prepare_smoke_run_config", self.text)
        self.assertIn("先选一个较小的网站验证 Google + B2 整条链路", self.text)
        self.assertIn("run_now smoke", self.text)
        self.assertIn("run_now full", self.text)
        self.assertIn("全部网站真实双远程备份通过后，才显示自动备份开关", self.text)

    def test_first_scheduler_enable_requires_current_inventory_exactly_verified(self):
        self.assertIn('sites_raw="$(inventory_sites)"', self.enable_body)
        self.assertIn('first_verification_passed "$sites_raw"', self.enable_body)
        self.assertIn("当前全部网站必须先完成一次真实双远程备份验证", self.enable_body)
        self.assertIn("网站列表刚发生变化，也必须重新验证", self.enable_body)
        self.assertIn("旧的通过结果不会覆盖新站点", self.enable_body)
        self.assertIn("定时任务：未安装", self.enable_body)
        self.assertIn("没有修改定时任务（Cron）", self.enable_body)

    def test_first_verification_compares_configured_and_verified_sets_to_current_inventory(self):
        self.assertIn("expected={x.strip()", self.verify_body)
        self.assertIn("configured={x for x in p.get('sites',[])", self.verify_body)
        self.assertIn("if configured != expected", self.verify_body)
        self.assertIn("verified.add(row['domain'])", self.verify_body)
        self.assertIn("verified == expected", self.verify_body)
        for key in ("local_backup", "google", "b2", "dual_remote"):
            self.assertIn(key, self.verify_body)


if __name__ == "__main__":
    unittest.main()
