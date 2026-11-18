#!/usr/bin/env python3
"""Single-use P08 PR#66 FULL-installer HTTP Origin portability proof, isolated only."""
from __future__ import annotations
import http.client
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("P08_ISOLATED_INSTALL_TEST") != "YES":
    raise SystemExit("P08_R177_ISOLATED_GITHUB_ACTIONS_ONLY")
if len(sys.argv) != 2:
    raise SystemExit("P08_R177_EXTRACTED_FULL_REQUIRED")
root = Path(sys.argv[1]).resolve(strict=True)
temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
if temp not in root.parents or not (root / "FULL_MANIFEST.json").is_file() or (root / ".env").exists():
    raise SystemExit("P08_R177_REFUSE_UNSAFE_SITE")

with tempfile.TemporaryDirectory(prefix="p08-r177-https-", dir=temp) as folder:
    prepend = Path(folder) / "https.php"
    prepend.write_text("<?php $_SERVER['HTTPS']='on';\n", encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen(
        ["php", "-d", "auto_prepend_file=" + str(prepend),
         "-S", f"127.0.0.1:{port}", "-t", str(root / "public")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    def request(method: str, origin: str | None = None, payload: dict | None = None,
                cookie: str = "", host: str = "adops.lanlihong.com"):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=12)
        headers = {"Host": host}
        if origin is not None:
            headers["Origin"] = origin
        if cookie:
            headers["Cookie"] = cookie
        data = urllib.parse.urlencode(payload).encode() if payload is not None else None
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            conn.request(method, "/setup.php", body=data, headers=headers)
            res = conn.getresponse()
            return res.status, dict(res.getheaders()), res.read().decode("utf-8")
        finally:
            conn.close()

    try:
        for attempt in range(120):
            if proc.poll() is not None:
                raise AssertionError("P08_R177_PHP_PROCESS_EARLY_EXIT")
            try:
                initial_status, _, _ = request("GET")
                if initial_status == 200:
                    break
            except OSError:
                pass
            time.sleep(0.1)
        else:
            raise AssertionError("P08_R177_CLEAN_FULL_GET_NOT_READY")
        def fresh():
            status, headers, html = request("GET")
            assert status == 200, "P08_R177_FRESH_GET_FAILED"
            assert "VF AdOps 0.1.8" in html, "P08_R177_VISIBLE_VERSION_MISMATCH"
            m = re.search(r'name="csrf" value="([a-f0-9]{64})"', html)
            assert m, "P08_R177_CSRF_TOKEN_MISSING"
            cookie = headers.get("Set-Cookie", "").split(";", 1)[0]
            assert cookie.startswith("adops_setup="), "P08_R177_COOKIE_MISSING"
            return m.group(1), cookie
        def post(origin, expect, host="adops.lanlihong.com"):
            csrf, cookie = fresh()
            data = {
                "csrf": csrf, "site_name": "AdOps Isolated",
                "owner_username": "synthetic_owner",
                "owner_email": "owner@isolated.example.test",
                "owner_password": "Synthetic_Offline_Password1!",
                "owner_confirm": "Synthetic_Offline_Password1!",
                "db_driver": "mariadb", "db_host": "127.0.0.1",
                "db_port": "3306", "db_database": "invalid;schema",
                "db_username": "synthetic", "db_password": "Synthetic_DB_Not_Real1!",
            }
            status, _, html = request("POST", origin=origin, payload=data, cookie=cookie, host=host)
            assert status == expect, f"P08_R177_EXPECT_{expect}_GOT_{status}"
            if expect == 422:
                assert "数据库名称不合格" in html and 'name="db_driver"' in html, "P08_R177_NOT_INSTALL_PREFLIGHT"
            if expect == 403:
                assert "安全拒绝提交" in html and "重新打开当前 HTTPS 安装页" in html, "P08_R177_WRONG_REJECTION"
                assert 'name="db_password"' not in html, "P08_R177_BAD_FORM_ON_REJECT"
            assert "Synthetic_DB_Not_Real1!" not in html, "P08_R177_SECRET_REFLECTED"
            assert not (root / ".env").exists(), "P08_R177_UNEXPECTED_INSTALL"
        for origin in ("https://adops.lanlihong.com",
                       "https://adops.lanlihong.com:443",
                       "HTTPS://ADOPS.LANLIHONG.COM:443"):
            post(origin, 422)
        print("P08_R177_REAL_EXTRACTED_FULL_HTTPS_SAME_ORIGIN_POST_RETRY=PASS")
        for origin in ("https://other.example.test", "http://adops.lanlihong.com",
                       "https://adops.lanlihong.com:444",
                       "https://adops.lanlihong.com/path",
                       "https://user@adops.lanlihong.com",
                       "null"):
            post(origin, 403)
        print("P08_R177_REAL_EXTRACTED_FULL_HTTPS_WRONG_ORIGIN_FAIL_CLOSED=PASS")
        post("https://adops.lanlihong.com", 403, host="other.example.test")
        print("P08_R177_REAL_EXTRACTED_FULL_HOST_MISMATCH_FAIL_CLOSED=PASS")
        print("P08_R177_NO_PERSISTENT_DATA_WRITES_AND_SECRET_LEAK=PASS")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=6)
