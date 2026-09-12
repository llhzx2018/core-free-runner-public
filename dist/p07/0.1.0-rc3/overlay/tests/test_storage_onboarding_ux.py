#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
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
        self.assertIn("首次使用前请先准备", self.setup)
        self.assertIn("Google：OAuth Client ID + Client Secret", self.setup)
        self.assertIn("B2：Bucket + Application Key ID + Application Key", self.setup)
        self.assertIn("Recovery Key：P07 自动生成，无需提前准备", self.setup)
        self.assertIn("已准备好，一键初始化 Google + B2", self.setup)
        self.assertIn("查看完整准备教程", self.setup)

    def test_google_tutorial_is_embedded_before_secret_prompts(self) -> None:
        tutorial = self.setup.find("https://console.cloud.google.com/")
        secret_prompt = self.setup.find("OAuth Client Secret（输入不回显）")
        self.assertGreaterEqual(tutorial, 0)
        self.assertGreater(secret_prompt, tutorial)
        self.assertIn("Google Drive API", self.setup)
        self.assertIn("TVs and Limited Input devices", self.setup)
        self.assertIn("Client ID + Client Secret", self.setup)
        self.assertIn("不回显、不写日志、不放命令行参数", self.setup)

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

    def test_google_secret_is_hidden_and_not_passed_in_argv(self) -> None:
        self.assertIn("GOOGLE_CLIENT_SECRET", self.setup)
        self.assertIn("IFS= read -rs client_secret", self.setup)
        self.assertIn("printf '%s\\n' \"$client_secret\" | python3 \"$GOOGLE_OAUTH_HELPER\" --client-id \"$client_id\"", self.setup)
        self.assertNotIn("--client-secret", self.setup)
        self.assertIn("google_client_secret_obscured", self.setup)
        self.assertIn("client_secret\\0%s\\0", self.setup)

    def test_google_oauth_contract_uses_secret_only_for_token_polling(self) -> None:
        self.assertRegex(self.oauth, r"def authorize\(client_id: str, client_secret: str\)")
        self.assertIn('DEVICE_ENDPOINT, {"client_id": client_id, "scope": DRIVE_SCOPE}', self.oauth)
        self.assertIn('"client_secret": client_secret', self.oauth)
        self.assertIn("client_secret = sys.stdin.readline()", self.oauth)
        self.assertNotIn("--client-secret", self.oauth)

    def test_existing_source_import_and_safety_routes_remain(self) -> None:
        self.assertIn("从已有 P07 服务器导入", self.setup)
        self.assertIn("import_from_source", self.setup)
        self.assertIn("DNS：未修改", self.setup)
        self.assertIn("SOURCE：保留", self.setup)
        self.assertIn("rollback_fresh", self.setup)
        self.assertIn("rollback_target", self.setup)
        self.assertIn("TARGET 安装后复核失败，正在恢复安装前配置", self.setup)


if __name__ == "__main__":
    unittest.main()
