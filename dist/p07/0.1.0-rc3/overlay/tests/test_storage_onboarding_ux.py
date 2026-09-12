#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "bin" / "vfops-storage-setup"
OAUTH = ROOT / "lib" / "google_device_oauth.py"


class StorageOnboardingUXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.setup = SETUP.read_text(encoding="utf-8")
        cls.oauth = OAUTH.read_text(encoding="utf-8")

    def test_first_screen_is_preparation_first(self) -> None:
        self.assertIn("首次使用前只需要准备", self.setup)
        self.assertIn("Google：OAuth Client ID", self.setup)
        self.assertIn("B2：Bucket + Application Key ID + Application Key", self.setup)
        self.assertIn("Recovery Key：P07 自动生成，无需提前准备", self.setup)
        self.assertIn("已准备好，一键初始化 Google + B2", self.setup)
        self.assertIn("查看准备教程", self.setup)

    def test_google_tutorial_is_embedded_before_secret_prompts(self) -> None:
        self.assertIn("https://console.cloud.google.com/", self.setup)
        self.assertIn("Google Drive API", self.setup)
        self.assertIn("TVs and Limited Input devices", self.setup)
        self.assertIn("P07 不再要求 Client Secret", self.setup)

    def test_b2_tutorial_is_embedded_and_specific(self) -> None:
        self.assertIn("https://secure.backblaze.com/", self.setup)
        self.assertIn("Application Keys", self.setup)
        self.assertIn("Read and Write", self.setup)
        self.assertIn("List All Bucket Names", self.setup)
        self.assertIn("Application Key 明文通常只显示一次", self.setup)

    def test_recovery_key_is_generated_not_requested(self) -> None:
        self.assertIn("generate_recovery_key", self.setup)
        self.assertIn("secrets.token_urlsafe(48)", self.setup)
        self.assertNotIn("Recovery Key（输入不回显）", self.setup)
        self.assertNotIn("请再输入一次确认", self.setup)
        self.assertIn("只显示这一次", self.setup)
        self.assertIn("P07 不会把这个明文 Key 写入服务器配置", self.setup)

    def test_recovery_key_is_revealed_only_after_health_pass(self) -> None:
        health = self.setup.find('if ! storage_health_pass "$CONFIG" "$rclone_config"; then')
        reveal = self.setup.find('print_recovery_key_once "$recovery_key"')
        self.assertGreaterEqual(health, 0)
        self.assertGreater(reveal, health)

    def test_google_device_oauth_no_longer_uses_client_secret(self) -> None:
        self.assertRegex(self.oauth, r"def authorize\(client_id: str\)")
        self.assertNotIn('"client_secret": client_secret', self.oauth)
        self.assertNotIn("sys.stdin.readline", self.oauth)
        self.assertNotIn("Client ID / Secret", self.oauth)

    def test_setup_does_not_prompt_for_google_client_secret(self) -> None:
        prompt_lines = [line for line in self.setup.splitlines() if "printf" in line or "read " in line]
        joined = "\n".join(prompt_lines)
        self.assertNotIn("Client Secret（输入不回显）", joined)
        self.assertNotRegex(joined, re.compile(r"GOOGLE_CLIENT_SECRET"))

    def test_existing_source_import_and_safety_routes_remain(self) -> None:
        self.assertIn("从已有 P07 服务器导入", self.setup)
        self.assertIn("import_from_source", self.setup)
        self.assertIn("DNS：未修改", self.setup)
        self.assertIn("SOURCE：保留", self.setup)
        self.assertIn("rollback_fresh", self.setup)
        self.assertIn("rollback_target", self.setup)


if __name__ == "__main__":
    unittest.main()
