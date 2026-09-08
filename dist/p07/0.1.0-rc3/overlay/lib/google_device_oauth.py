#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEVICE_ENDPOINT = "https://oauth2.googleapis.com/device/code"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
USER_AGENT = "VF-Server-Ops/0.1.0"


class OAuthError(RuntimeError):
    pass


def friendly_oauth_error(code: str, phase: str = "token") -> str:
    code = (code or "unknown_error").strip()
    if phase == "device":
        mapping = {
            "invalid_client": "Google OAuth Client ID 无效；请确认使用你自己的 TVs and Limited Input devices Client。",
            "unauthorized_client": "这个 Google OAuth Client 不能使用 Device Authorization；请确认 Client 类型为 TVs and Limited Input devices。",
            "invalid_request": "Google 拒绝了 Device OAuth 请求；请检查 Client ID 后重新进入初始化。",
            "access_denied": "Google Device OAuth 请求被拒绝；没有修改配置。",
        }
    else:
        mapping = {
            "access_denied": "Google 授权已被拒绝；没有修改配置。重新进入初始化后可以再次授权。",
            "expired_token": "Google 一次性授权已过期；没有修改配置。请重新进入初始化获取新的授权代码。",
            "invalid_client": "Google OAuth Client ID / Secret 验证失败；请检查你自己的 OAuth Client 信息。",
            "unauthorized_client": "这个 Google OAuth Client 不能完成 Device Authorization；请确认 Client 类型为 TVs and Limited Input devices。",
            "invalid_grant": "Google 授权会话已经失效；没有修改配置。请重新进入初始化获取新的授权代码。",
            "invalid_request": "Google 授权请求无效；没有修改配置。请重新进入初始化。",
            "temporarily_unavailable": "Google OAuth 暂时不可用；没有修改配置。请稍后重新进入初始化。",
        }
    return mapping.get(code, f"Google 授权失败（{code}）；没有修改配置。")


def post_form(url: str, payload: dict[str, str], timeout: int = 20) -> dict[str, object]:
    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OAuthError(f"Google OAuth 请求失败（HTTP {exc.code}）；没有修改配置。") from None
        if isinstance(data, dict):
            return data
        raise OAuthError(f"Google OAuth 请求失败（HTTP {exc.code}）；没有修改配置。") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OAuthError("Google OAuth 网络请求失败；请检查 VPS 网络后重新进入初始化。") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OAuthError("Google OAuth 返回了无法识别的数据；没有修改配置。") from exc
    if not isinstance(data, dict):
        raise OAuthError("Google OAuth 返回格式异常；没有修改配置。")
    return data


def authorize(client_id: str, client_secret: str) -> dict[str, str]:
    device = post_form(DEVICE_ENDPOINT, {"client_id": client_id, "scope": DRIVE_SCOPE})
    device_code = str(device.get("device_code") or "")
    user_code = str(device.get("user_code") or "")
    verification_url = str(device.get("verification_url") or device.get("verification_uri") or "https://www.google.com/device")
    try:
        expires_in = int(device.get("expires_in") or 1800)
        interval = max(1, int(device.get("interval") or 5))
    except (TypeError, ValueError) as exc:
        raise OAuthError("Google OAuth 返回的等待时间异常；没有修改配置。") from exc
    if not device_code or not user_code:
        raise OAuthError(friendly_oauth_error(str(device.get("error") or "device_authorization_failed"), phase="device"))
    print("", file=sys.stderr)
    print("Google 官方浏览器授权", file=sys.stderr)
    print("----------------------------------------", file=sys.stderr)
    print(f"1. 打开：{verification_url}", file=sys.stderr)
    print(f"2. 输入一次性代码：{user_code}", file=sys.stderr)
    print("3. 在 Google 页面确认授权；P07 会在这里自动继续。", file=sys.stderr)
    print("", file=sys.stderr)
    deadline = time.monotonic() + expires_in
    current_interval = interval
    slow_down_notified = False
    while time.monotonic() < deadline:
        token = post_form(TOKEN_ENDPOINT, {"client_id": client_id, "client_secret": client_secret, "device_code": device_code, "grant_type": GRANT_TYPE})
        error = str(token.get("error") or "")
        if error == "authorization_pending":
            time.sleep(current_interval)
            continue
        if error == "slow_down":
            current_interval += 5
            if not slow_down_notified:
                print("Google 要求降低轮询频率，P07 已自动放慢等待，不需要重新操作。", file=sys.stderr)
                slow_down_notified = True
            time.sleep(current_interval)
            continue
        if error:
            raise OAuthError(friendly_oauth_error(error))
        access_token = str(token.get("access_token") or "")
        refresh_token = str(token.get("refresh_token") or "")
        token_type = str(token.get("token_type") or "Bearer")
        try:
            token_expires = int(token.get("expires_in") or 3600)
        except (TypeError, ValueError):
            token_expires = 3600
        if not access_token or not refresh_token:
            raise OAuthError("Google 授权完成但没有返回可复用的 Refresh Token；没有修改配置。请重新授权。")
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=token_expires)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return {"access_token": access_token, "token_type": token_type, "refresh_token": refresh_token, "expiry": expiry}
    raise OAuthError("Google 授权等待超时；没有修改配置。请重新进入初始化获取新的授权代码。")


def main() -> int:
    parser = argparse.ArgumentParser(description="P07 Google Drive device OAuth helper")
    parser.add_argument("--client-id", required=True)
    args = parser.parse_args()
    client_id = args.client_id.strip()
    client_secret = sys.stdin.readline().rstrip("\r\n")
    if not client_id or not client_secret:
        print("ERROR: Google OAuth Client ID / Secret 不能为空。", file=sys.stderr)
        return 13
    try:
        token = authorize(client_id, client_secret)
    except OAuthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 13
    finally:
        client_secret = ""
    print(json.dumps(token, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
