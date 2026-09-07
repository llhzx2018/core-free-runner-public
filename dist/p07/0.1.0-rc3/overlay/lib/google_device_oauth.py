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


def post_form(url: str, payload: dict[str, str], timeout: int = 20) -> dict[str, object]:
    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
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
            raise OAuthError(f"Google OAuth HTTP {exc.code}") from None
        if isinstance(data, dict):
            return data
        raise OAuthError(f"Google OAuth HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OAuthError("Google OAuth network request failed") from exc

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OAuthError("Google OAuth returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise OAuthError("Google OAuth returned an invalid response")
    return data


def authorize(client_id: str, client_secret: str) -> dict[str, str]:
    device = post_form(
        DEVICE_ENDPOINT,
        {"client_id": client_id, "scope": DRIVE_SCOPE},
    )
    device_code = str(device.get("device_code") or "")
    user_code = str(device.get("user_code") or "")
    verification_url = str(
        device.get("verification_url")
        or device.get("verification_uri")
        or "https://www.google.com/device"
    )
    try:
        expires_in = int(device.get("expires_in") or 1800)
        interval = max(1, int(device.get("interval") or 5))
    except (TypeError, ValueError) as exc:
        raise OAuthError("Google OAuth returned invalid timing metadata") from exc
    if not device_code or not user_code:
        err = str(device.get("error") or "device_authorization_failed")
        raise OAuthError(f"Google device authorization failed: {err}")

    print("", file=sys.stderr)
    print("Google 官方浏览器授权", file=sys.stderr)
    print("----------------------------------------", file=sys.stderr)
    print(f"1. 打开：{verification_url}", file=sys.stderr)
    print(f"2. 输入一次性代码：{user_code}", file=sys.stderr)
    print("3. 在 Google 页面确认授权；P07 会在这里自动继续。", file=sys.stderr)
    print("", file=sys.stderr)

    deadline = time.monotonic() + expires_in
    current_interval = interval
    while time.monotonic() < deadline:
        token = post_form(
            TOKEN_ENDPOINT,
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "device_code": device_code,
                "grant_type": GRANT_TYPE,
            },
        )
        error = str(token.get("error") or "")
        if error == "authorization_pending":
            time.sleep(current_interval)
            continue
        if error == "slow_down":
            current_interval += 5
            time.sleep(current_interval)
            continue
        if error:
            raise OAuthError(f"Google authorization failed: {error}")

        access_token = str(token.get("access_token") or "")
        refresh_token = str(token.get("refresh_token") or "")
        token_type = str(token.get("token_type") or "Bearer")
        try:
            token_expires = int(token.get("expires_in") or 3600)
        except (TypeError, ValueError):
            token_expires = 3600
        if not access_token or not refresh_token:
            raise OAuthError("Google authorization did not return a reusable token")
        expiry = (
            datetime.now(timezone.utc) + timedelta(seconds=token_expires)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return {
            "access_token": access_token,
            "token_type": token_type,
            "refresh_token": refresh_token,
            "expiry": expiry,
        }

    raise OAuthError("Google authorization timed out before approval")


def main() -> int:
    parser = argparse.ArgumentParser(description="P07 Google Drive device OAuth helper")
    parser.add_argument("--client-id", required=True)
    args = parser.parse_args()

    client_id = args.client_id.strip()
    client_secret = sys.stdin.readline().rstrip("\r\n")
    if not client_id or not client_secret:
        print("ERROR: Google OAuth Client ID / Secret is required", file=sys.stderr)
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
