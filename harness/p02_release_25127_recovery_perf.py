#!/usr/bin/env python3
"""P02 2.5.127 exact-source isolated PHP/SQLite recovery and search regression proof.

PUBLIC-SAFE TEST CODE ONLY: disposable localhost server, synthetic content,
no live production credentials, no live server writes, no private files in Git.
"""
from __future__ import annotations
import hashlib
import html
import http.cookiejar
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

OLD = "2.5.124"
TARGET = "2.5.127"
SECRET = "P02-SYNTHETIC-RELEASE-RESTORE-ONLY"
FIXTURE = b"P02 synthetic file content for one-off backup-restore replay. 25127"
OLD_SHA = "c30e9a5a5d8380443f564c0e56606c13edb31da3482c1704deecdcf9c1ff7a56"
TARGET_SHA = "bd90624278e570d4b01013f84dffce31367c601eaf785051d12db9d3dbf4d596"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

class Site:
    def __init__(self, site, port):
        self.site = site
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies), NoRedirect())
        self.process = None
        self.csrf = ""

    def start(self, inject=None):
        assert self.process is None
        env = os.environ.copy()
        if inject:
            env["VFTB_TEST_MODE"] = "1"
            env["VFTB_TEST_RESTORE_FAIL_STAGE"] = inject
        self.process = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{self.port}", "-t", str(self.site)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        for _ in range(80):
            try:
                status, _ = self.request("/setup.php", timeout=2)
                if status in (200, 303, 404):
                    return
            except Exception:
                pass
            time.sleep(0.15)
        raise RuntimeError("PHP server could not start")

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            self.process = None

    def request(self, path, body=None, headers=None, timeout=25):
        h = dict(headers or {})
        if body is not None:
            h.setdefault("Origin", self.base)
        req = urllib.request.Request(
            self.base + path, data=body, headers=h,
            method="POST" if body is not None else "GET")
        try:
            resp = self.opener.open(req, timeout=timeout)
            return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def get_json(self, path):
        status, b = self.request(path)
        obj = json.loads(b)
        assert status == 200 and obj.get("ok") is True, (path, status, obj.get("error"))
        return obj

    def post_json(self, action, data, route="api.php", expect_success=True):
        payload = json.dumps(data, ensure_ascii=False).encode()
        status, b = self.request(
            f"/{route}?action={action}", payload, {
                "Content-Type": "application/json",
                "X-CSRF-Token": self.csrf,
            }, timeout=60)
        obj = json.loads(b)
        if expect_success:
            assert status in (200, 201) and obj.get("ok") is True, (
                action, status, obj.get("error"))
        return status, obj

    def auth(self):
        info = self.get_json("/api.php?action=session")
        if not info["site"]["auth"]:
            status, login = self.post_json("login", {"password": SECRET})
            assert status == 200 and login["ok"]
            info = self.get_json("/api.php?action=session")
        assert info["site"]["auth"]
        self.csrf = info["csrf"]
        return info

    def install(self, ver):
        status, page = self.request("/setup.php")
        assert status == 200, ("SETUP_HTTP", status)
        token = re.search(r'name="setup_csrf" value="([^"]+)"', page.decode())
        assert token, "SETUP_CSRF_REQUIRED"
        payload = urllib.parse.urlencode({
            "setup_csrf": html.unescape(token.group(1)),
            "password": SECRET, "password_confirm": SECRET,
        }).encode()
        status, _ = self.request("/setup.php", payload, {
            "Content-Type": "application/x-www-form-urlencoded"
        })
        assert status == 303, ("SETUP_FAILED", ver, status)
        info = self.auth()
        assert info["version"] == ver, (ver, info.get("version"))
        assert self.get_json("/api.php?action=health")["version"] == ver
        print("P02_RELEASE_REAL_SETUP_" + ver.replace(".", "_") + "=PASS")

    def create_fixture(self):
        category = self.post_json(
            "category_save", {"name": "P02 synthetic performance/recovery test", "icon": "folder"})[1]
        cid = category["id"]
        material_id = None
        for i in range(35):
            row = self.post_json("content_save", {
                "category_id": cid,
                "title": f"P02PERF25127 synthetic searchable item {i:02}",
                "content": f"Performance fixture number {i:02}, no private data.",
                "content_mode": "article", "content_format": "markdown",
                "primary_action": "read", "status": "active"
            })[1]
            if material_id is None:
                material_id = row["id"]
        tab = self.post_json("create", {}, route="scratch-action.php")[1]["tab"]
        tabid = int(tab["id"])
        self.post_json("save", {
            "id": tabid, "content": "P02 synthetic scratch ORIGINAL",
            "cursor_pos": 0, "scroll_top": 0
        }, route="scratch-action.php")
        return cid, material_id, tabid

    def search(self):
        samples = []
        for j in range(35):
            q = urllib.parse.quote("P02PERF25127")
            t = time.perf_counter()
            result = self.get_json(f"/api.php?action=library_search&q={q}&limit=50")
            duration = (time.perf_counter() - t) * 1000
            assert len(result["items"]) >= 30, ("SEARCH_WRONG_RESULT",len(result["items"]))
            if j >= 5:
                samples.append(duration)
        return samples

    def get_item(self, itemid):
        return self.get_json(f"/api.php?action=content_get&id={itemid}")["item"]

    def get_scratch(self, tabid):
        data = self.get_json("/scratch-action.php?action=list")["data"]
        found = [x for x in data["open"] if x["id"] == tabid]
        assert len(found) == 1
        return found[0]

    def upload_file(self, itemid):
        boundary = "P02SyntheticBoundary25127"
        b = boundary.encode()
        payload = (
            b"--" + b + b"\r\n" +
            b'Content-Disposition: form-data; name="item_id"\r\n\r\n' +
            str(itemid).encode() + b"\r\n" +
            b"--" + b + b"\r\n" +
            b'Content-Disposition: form-data; name="attachment"; filename="p02-synthetic.txt"\r\n' +
            b"Content-Type: text/plain\r\n\r\n" + FIXTURE + b"\r\n" +
            b"--" + b + b"--\r\n")
        status, result = self.request(
            "/api.php?action=attachment_upload", payload, {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-CSRF-Token": self.csrf,
            }, timeout=60)
        obj = json.loads(result)
        assert status == 201 and obj.get("ok") and obj.get("attachments"), (
            "ATTACHMENT_UPLOAD",status,obj.get("error"))
        aid = int(obj["attachments"][0]["id"])
        self.verify_file(aid)
        return aid

    def verify_file(self, attachment_id):
        status, data = self.request(f"/file.php?id={attachment_id}&download=1")
        assert status == 200 and data == FIXTURE, ("ATTACHMENT_BYTES_LOST",status)

    def check_saved(self, itemid, tabid, body):
        assert self.get_item(itemid)["content"] == body
        assert self.get_scratch(tabid)["content"] == "P02 synthetic scratch ORIGINAL"

    def create_backup(self):
        filename = self.post_json("backup", {"note": "P02 synthetic recovery proof"})[1]["filename"]
        inspection = self.post_json("backup_inspect", {"filename": filename})[1]["inspection"]
        assert inspection.get("restorable") is True, ("BACKUP_INSPECT",inspection.get("restorable"))
        return filename

    def restore(self, filename, success=True):
        self.post_json("reauth", {"password": SECRET})
        code, result = self.post_json(
            "backup_restore", {"filename": filename, "confirmation": "恢复"},
            expect_success=success)
        if success:
            assert code == 200 and result["ok"] is True, ("RESTORE_HTTP",code,result)
            self.auth()
        else:
            assert code != 200 or not result.get("ok"), ("EXPECTED_RESTORE_FAILURE",code)
        return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def stats(samples):
    x = sorted(samples)
    return {
        "p50_ms": round(statistics.median(x), 2),
        "p95_ms": round(x[int(0.95*(len(x)-1))], 2),
        "max_ms": round(max(x), 2)
    }

def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: harness.py <official v2.5.124 FULL> <exact v2.5.127 FULL>")
    old_zip, target_zip = map(Path,sys.argv[1:])
    assert digest(old_zip) == OLD_SHA, "OFFICIAL_BASELINE_SHA_MISMATCH"
    assert digest(target_zip) == TARGET_SHA, "EXACT_TARGET_FULL_SHA_MISMATCH"
    with tempfile.TemporaryDirectory(prefix="p02-release-restore-perf-") as tmp:
        old_root=Path(tmp)/"old";old_root.mkdir()
        target_root=Path(tmp)/"target";target_root.mkdir()
        with zipfile.ZipFile(old_zip) as z:z.extractall(old_root)
        with zipfile.ZipFile(target_zip) as z:z.extractall(target_root)
        assert (old_root/"VERSION.txt").read_text().strip() == OLD
        assert (target_root/"VERSION.txt").read_text().strip() == TARGET
        sites=[Site(old_root,18991),Site(target_root,18992)]
        try:
            values=[]
            for site,ver in zip(sites,[OLD,TARGET]):
                site.start()
                site.install(ver)
                cid,item,tab=site.create_fixture()
                numbers=site.search()
                values.append(stats(numbers))
                if ver==TARGET:
                    assert (target_root/"assets/w1/w1-search.js").is_file()
                    # This is an actual user data backup + inspect + restore rehearsal.
                    file_id=site.upload_file(item)
                    filename=site.create_backup()
                    original=site.get_item(item)["content"]
                    site.post_json("content_save", {
                        "id": item, "category_id": cid,
                        "title": "P02PERF25127 synthetic searchable item 00",
                        "content": "MUTATED content discarded by restoration",
                        "content_mode": "article", "content_format": "markdown",
                        "primary_action": "read", "status": "active"
                    })
                    site.post_json("save", {
                        "id": tab, "content": "MUTATED scratch discarded by restoration",
                        "cursor_pos": 0,"scroll_top":0
                    },route="scratch-action.php")
                    assert site.get_item(item)["content"].startswith("MUTATED")
                    result=site.restore(filename)
                    site.check_saved(item,tab,original)
                    site.verify_file(file_id)
                    print("P02_FORMAL_REAL_RESTORE_MATERIAL_SCRATCH_ATTACHMENT=PASS")
                    # Fail injection tests rollback without a phantom success or orphaned DB.
                    fail_backup=site.create_backup()
                    site.post_json("content_save", {
                        "id": item,"category_id":cid,
                        "title":"P02PERF25127 synthetic searchable item 00",
                        "content":"P02_UNCOMMITTED_MUTATION_MUST_SURVIVE_FAILED_RESTORE",
                        "content_mode":"article","content_format":"markdown",
                        "primary_action":"read","status":"active"
                    })
                    site.stop()
                    site.start(inject="after-old-move")
                    site.auth()
                    err=site.restore(fail_backup,success=False)
                    site.stop()
                    site.start()
                    site.auth()
                    assert site.get_item(item)["content"] == "P02_UNCOMMITTED_MUTATION_MUST_SURVIVE_FAILED_RESTORE"
                    site.verify_file(file_id)
                    print("P02_FORMAL_FAILED_RESTORE_PRESERVES_CURRENT_DB_AND_ATTACHMENT=PASS")
                    site.restore(fail_backup)
                    site.check_saved(item,tab,original)
                    site.verify_file(file_id)
                    print("P02_FORMAL_RESTORE_RETRY_RECOVERS_FROM_FAILURE=PASS")
                    verify=subprocess.run(
                        ["php",str(target_root/"cli/verify.php")],
                        capture_output=True,text=True,timeout=40,cwd=target_root)
                    if verify.returncode != 0:
                        raise AssertionError("CLI_VERIFY_FAILED: "+verify.stdout[-400:]+" "+verify.stderr[-400:])
                    assert json.loads(verify.stdout)["ok"] is True
                    print("P02_FORMAL_POST_RESTORE_SQLITE_CLI_VERIFY=PASS")
            baseline,target=values
            print("P02_FORMAL_PERF_BASELINE="+json.dumps(baseline,sort_keys=True))
            print("P02_FORMAL_PERF_TARGET="+json.dumps(target,sort_keys=True))
            assert target["p50_ms"] <= max(250,baseline["p50_ms"]*2.5), "P02_SEARCH_P50_PERFORMANCE_REGRESSION"
            assert target["p95_ms"] <= max(600,baseline["p95_ms"]*3.0), "P02_SEARCH_P95_PERFORMANCE_REGRESSION"
            print("P02_FORMAL_ISOLATED_SEARCH_PERF_REGRESSION=PASS")
        finally:
            for site in sites:site.stop()
    print("P02_FORMAL_SYNTHETIC_DATA_CLEANED=PASS")

if __name__=="__main__":
    main()
