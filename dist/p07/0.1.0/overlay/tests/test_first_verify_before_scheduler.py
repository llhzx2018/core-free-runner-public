#!/usr/bin/env python3
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MENU = ROOT / "bin" / "vfops-auto-backup"


def function_body(text: str, name: str, next_name: str) -> str:
    match = re.search(rf"\n{name}\(\) \{{\n(?P<body>.*?)\n\}}\n\n{next_name}\(\)", text, re.S)
    if not match:
        raise AssertionError(f"function {name} not found")
    return match.group("body")


class FirstVerifyBeforeSchedulerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = MENU.read_text(encoding="utf-8")
        cls.prepare = function_body(cls.text, "prepare_first_run_config", "setup_storage")
        cls.status = function_body(cls.text, "show_status", "enable_or_update")
        cls.enable = function_body(cls.text, "enable_or_update", "run_now")
        cls.run_now = function_body(cls.text, "run_now", "disable_auto")

    def test_first_run_can_create_config_without_installing_cron(self):
        self.assertIn("storage_preflight", self.prepare)
        self.assertIn("inventory_sites", self.prepare)
        self.assertIn('configure --config "$CONFIG"', self.prepare)
        self.assertIn("--daily-at '03:30'", self.prepare)
        self.assertIn("首次验证配置：已就绪", self.prepare)
        self.assertIn("定时任务：尚未安装", self.prepare)
        self.assertNotIn("install-cron", self.prepare)
        self.assertNotIn("ENABLE_DUAL_REMOTE_AUTOBACKUP", self.prepare)

    def test_run_now_bootstraps_first_verification_when_config_missing(self):
        self.assertIn('if [[ ! -f "$CONFIG" ]]', self.run_now)
        self.assertIn("prepare_first_run_config", self.run_now)
        self.assertIn("不会安装 Cron", self.run_now)
        self.assertIn("本次仅做真实验证", self.run_now)
        self.assertIn("schedule_active", self.run_now)

    def test_first_scheduler_enable_requires_previous_real_dual_remote_pass(self):
        self.assertIn("if ! p07_cron_owned && ! first_verification_passed", self.enable)
        self.assertIn("首次启用定时备份前，当前全部 CloudPanel 网站必须先完成一次真实双远程备份验证", self.enable)
        self.assertIn("定时任务：未安装", self.enable)
        self.assertIn("没有修改 Cron", self.enable)
        self.assertIn("install-cron", self.enable)

    def test_pass_without_scheduler_gives_correct_next_action(self):
        self.assertIn("当前全部网站本地 + Google + B2 真实验证已通过", self.run_now)
        self.assertIn("定时备份仍未开启", self.run_now)
        self.assertIn("选择“2. 启用 / 更新自动备份”", self.run_now)
        self.assertIn("本次验证不会创建或修改 P07 Cron", self.run_now)

    def test_status_distinguishes_ready_and_verified_without_schedule(self):
        self.assertIn("READY_NO_SCHEDULE", self.status)
        self.assertIn("VERIFIED_NO_SCHEDULE", self.status)
        self.assertIn("远程已就绪 · 待首次验证", self.status)
        self.assertIn("首次验证已通过 · 定时未开启", self.status)
        self.assertIn("通过后再选择“2. 启用 / 更新自动备份”", self.status)

    def test_safety_boundaries_remain_explicit(self):
        self.assertIn("没有修改 Cron", self.enable)
        self.assertIn("DNS 未修改", self.enable)
        self.assertIn("源服务器保留", self.enable)
        self.assertIn("本次验证不会创建或修改 P07 Cron", self.run_now)
        self.assertIn("DNS 未修改", self.run_now)
        self.assertIn("源服务器保留", self.run_now)


if __name__ == "__main__":
    unittest.main()
