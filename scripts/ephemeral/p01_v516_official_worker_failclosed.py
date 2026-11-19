#!/usr/bin/env python3
"""One-off fail-closed official 2.47.516 installed MAJOR CLI proof.

A real published FULL is installed in a disposable self-hosted PHP test
site. A missing v517 official MAJOR and Owner claim MUST NOT mutate data.
"""
import hashlib
import http.cookiejar
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

URL = "http://127.0.0.1:19416/setup.php"
VERSION = "2.47.516"


def call(*args, cwd=None, timeout=35):
    return subprocess.run(args, cwd=cwd, check=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout).stdout


def main():
    official = Path(os.environ["RUNNER_TEMP"]) / "VF-Start-V2.47.516-FULL.zip"
    expected = "016edb85c7cfa48bf939d69fce1f0925f6f50647fded286a5b6df3789ca580ce"
    assert official.is_file() and hashlib.sha256(official.read_bytes()).hexdigest() == expected
    with tempfile.TemporaryDirectory(prefix="p01-v516-official-negative-") as tmp:
        site = Path(tmp)
        call("unzip", "-q", str(official), "-d", str(site))
        assert (site / "VERSION.txt").read_text().strip() == VERSION
        worker = site / "app/bin/p01-major-apply-worker.php"
        assert worker.is_file(), "PUBLISHED_V516_WORKER_MUST_EXIST"
        call("php8.3", "-l", str(worker))
        web = subprocess.Popen(
            ["php8.3", "-S", "127.0.0.1:19416", "-t", "."],
            cwd=site, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        try:
            jar = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            page = None
            for _ in range(35):
                try:
                    page = opener.open(URL, timeout=4).read().decode("utf-8")
                    break
                except (OSError, urllib.error.URLError):
                    time.sleep(.5)
            assert page is not None, "OFFICIAL_V516_SETUP_UNAVAILABLE"
            m = re.search(r'name="setup_csrf"\s+value="([^"]+)"', page)
            assert m, "OFFICIAL_V516_CSRF_ABSENT"
            data = urllib.parse.urlencode({
                "setup_csrf": m.group(1),
                "site_title": "One-off issued 516 safety",
                "admin_password": "BridgePassword-2026!",
                "admin_password_confirm": "BridgePassword-2026!",
            }).encode()
            opener.open(urllib.request.Request(URL, data=data), timeout=20).read()
            check = call("php8.3", "cli/verify.php", cwd=site).decode()
            assert "VERIFY_PASS=YES" in check, "ISSUED_V516_INSTALLED_SITE_FAIL"
            db = Path(call("php8.3", "-r",
                           'require $argv[1]."/app/bootstrap.php";echo VF_DB_FILE;',
                           str(site)).decode())
            assert db.is_file(), "INSTALLED_V516_DB_MISSING"
            before = hashlib.sha256(db.read_bytes()).hexdigest()
            process = subprocess.run(
                ["php8.3", str(worker)], cwd=site,
                stdin=subprocess.DEVNULL, capture_output=True,
                timeout=35, text=True
            )
            assert process.returncode != 0, "WORKER_WITHOUT_OWNER_CONSENT_EXECUTED"
            assert process.stderr.strip() == "P01_MAJOR_APPLY_FAIL_CLOSED_RECOVERY_REQUIRED", (
                "WORKER_MUST_SHOW_ONLY_GENERIC_RECOVERY_MESSAGE"
            )
            after = hashlib.sha256(db.read_bytes()).hexdigest()
            assert before == after, "OLD_SQLITE_BYTES_MUTATED_BY_UNAPPROVED_APPLY"
            updates = site / "private/updates"
            for file in ("p01-major-execution-claim.json",
                         "p01-major-owner-intent.json",
                         "p01-major-write-hold.json"):
                assert not (updates / file).exists(), file + "_CREATED_WITHOUT_OWNER"
            verify = call("php8.3", "cli/verify.php", cwd=site).decode()
            assert "VERIFY_PASS=YES" in verify, "OLD_V516_SITE_UNUSABLE_AFTER_DENIAL"
            print("P01_ISSUED_V516_ACTUAL_INSTALLED_APPLY_WORKER_FAIL_CLOSED=PASS",
                  flush=True)
            print("P01_ISSUED_V516_OLD_DB_OWNER_AND_RUNTIME_SURVIVE_NO_RELEASE=PASS",
                  flush=True)
            print("P01_ISSUED_V516_NO_OWNER_CLAIM_NO_STALE_WRITE_HOLD=PASS",
                  flush=True)
            print("P01_V517_OFFICIAL_ISSUANCE_REQUIRED_BEFORE_REAL_APPLY=YES",
                  flush=True)
        finally:
            web.terminate()
            try:
                web.wait(timeout=8)
            except subprocess.TimeoutExpired:
                web.kill()
                web.wait()


if __name__ == "__main__":
    main()
