#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import google_device_oauth as oauth


class GoogleDeviceOAuthTests(unittest.TestCase):
    def _device(self, expires_in: int = 30) -> dict[str, object]:
        return {
            "device_code": "SYNTH_DEVICE_SECRET",
            "user_code": "P07-TEST",
            "verification_url": "https://www.google.com/device",
            "expires_in": expires_in,
            "interval": 1,
        }

    def test_friendly_error_messages_cover_expected_terminal_states(self) -> None:
        expected = {
            "access_denied": "已被拒绝",
            "expired_token": "已过期",
            "invalid_client": "Client ID",
            "unauthorized_client": "TVs and Limited Input devices",
            "invalid_grant": "已经失效",
            "temporarily_unavailable": "暂时不可用",
        }
        for code, text in expected.items():
            with self.subTest(code=code):
                message = oauth.friendly_oauth_error(code)
                self.assertIn(text, message)
                self.assertIn("没有修改配置", message)

    def test_access_denied_is_fail_closed(self) -> None:
        with mock.patch.object(oauth, "post_form", side_effect=[self._device(), {"error": "access_denied"}]), \
             mock.patch.object(oauth.time, "monotonic", side_effect=[100.0, 100.0]):
            with self.assertRaises(oauth.OAuthError) as ctx:
                oauth.authorize("CLIENT")
        self.assertIn("已被拒绝", str(ctx.exception))

    def test_slow_down_is_automatic_and_then_succeeds(self) -> None:
        success = {
            "access_token": "ACCESS_SECRET",
            "refresh_token": "REFRESH_SECRET",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        stderr = io.StringIO()
        calls: list[tuple[str, dict[str, str]]] = []

        def fake_post(url: str, payload: dict[str, str], timeout: int = 20):
            calls.append((url, payload.copy()))
            if len(calls) == 1:
                return self._device()
            if len(calls) == 2:
                return {"error": "slow_down"}
            return success

        with mock.patch.object(oauth, "post_form", side_effect=fake_post), \
             mock.patch.object(oauth.time, "monotonic", side_effect=[100.0, 100.0, 100.0]), \
             mock.patch.object(oauth.time, "sleep") as sleep, \
             contextlib.redirect_stderr(stderr):
            token = oauth.authorize("CLIENT")
        self.assertEqual(token["refresh_token"], "REFRESH_SECRET")
        sleep.assert_called_once_with(6)
        self.assertIn("已自动放慢等待", stderr.getvalue())
        for _url, payload in calls:
            self.assertNotIn("client_secret", payload)

    def test_timeout_has_recovery_next_action(self) -> None:
        with mock.patch.object(oauth, "post_form", return_value=self._device(expires_in=1)), \
             mock.patch.object(oauth.time, "monotonic", side_effect=[10.0, 12.0]):
            with self.assertRaises(oauth.OAuthError) as ctx:
                oauth.authorize("CLIENT")
        message = str(ctx.exception)
        self.assertIn("超时", message)
        self.assertIn("重新进入初始化", message)

    def test_network_error_does_not_echo_request_payload(self) -> None:
        with mock.patch.object(oauth.urllib.request, "urlopen", side_effect=OSError("SYNTH_SECRET_NETWORK_DETAIL")):
            with self.assertRaises(oauth.OAuthError) as ctx:
                oauth.post_form(oauth.TOKEN_ENDPOINT, {"client_id": "DO_NOT_ECHO"})
        message = str(ctx.exception)
        self.assertIn("网络请求失败", message)
        self.assertNotIn("DO_NOT_ECHO", message)
        self.assertNotIn("SYNTH_SECRET_NETWORK_DETAIL", message)

    def test_blank_client_id_fails_before_network(self) -> None:
        with mock.patch.object(oauth, "post_form") as post:
            with self.assertRaises(oauth.OAuthError):
                oauth.authorize("   ")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
