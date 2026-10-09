#!/usr/bin/env python3
"""P07 rc53: local fake references only; no network, no Production, no writes."""
import hashlib
import io
import json
import os
import pathlib
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = ROOT / "packages/p07-system-care/0.1.0-rc53"
import sys
sys.path.insert(0, str(PKG / "lib"))
import intrusion_verify as v


class SafeOriginValidation(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.home = pathlib.Path(self.dir.name)
        self.root = self.home / "sample.example"
        (self.root / "wp-includes").mkdir(parents=True)
        (self.root / "wp-content/plugins/vf-ops/includes").mkdir(parents=True)
        (self.root / "wp-content/wflogs").mkdir(parents=True)
        (self.root / "wp-config.php").write_text("do-not-read", encoding="utf8")
        (self.root / "wp-includes/version.php").write_text(
            "<?php\n$wp_version = '6.8.3';\n$wp_local_package = 'zh_CN';\n",
            encoding="utf8")
        (self.root / "wp-includes/demo.php").write_text("<?php echo 1;", encoding="utf8")
        (self.root / "wp-content/plugins/vf-ops/vf-ops.php").write_text(
            "<?php\n/*\nPlugin Name: VF Ops\nVersion: 1.21.1073\n*/\n", encoding="utf8")
        (self.root / "wp-content/plugins/vf-ops/includes/panel.php").write_text(
            "<?php echo 'valid';", encoding="utf8")
        (self.root / "wp-content/wflogs/config-synced.php").write_text(
            "<?php /* dynamic */", encoding="utf8")
        self.env = mock.patch.dict(os.environ, {"P07_IE_DISCOVERY_HOME": str(self.home)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.baseline = {str(self.root): {"files": {}}}

    def event(self, path):
        return {"site_root": str(self.root), "site": "sample.example",
                "relative_path": path, "type": "MODIFIED_PHP"}

    def fake_wp(self, url, cap):
        self.assertTrue(url.startswith("https://api.wordpress.org/core/checksums/1.0/?"))
        self.assertIn("version=6.8.3", url)
        self.assertIn("locale=zh_CN", url)
        valid = {f"wp-includes/unrelated-{i}.php": "0" * 32 for i in range(230)}
        valid["wp-includes/demo.php"] = hashlib.md5(
            (self.root / "wp-includes/demo.php").read_bytes()).hexdigest()
        valid["wp-includes/version.php"] = hashlib.md5(
            (self.root / "wp-includes/version.php").read_bytes()).hexdigest()
        return json.dumps({"checksums": valid}).encode()

    def test_wp_release_checksum_matches_and_reports_only_file_identity(self):
        result, reason = v.source_result(self.event("wp-includes/demo.php"),
                                         self.baseline, {}, self.fake_wp)
        self.assertEqual(result, "一致")
        self.assertIn("非安全证明", reason)
        self.assertEqual((self.root / "wp-config.php").read_text(), "do-not-read")

    def test_modified_core_does_not_get_false_pass(self):
        def mismatch(url, cap):
            j = json.loads(self.fake_wp(url, cap))
            j["checksums"]["wp-includes/demo.php"] = "0" * 32
            return json.dumps(j).encode()
        result, reason = v.source_result(self.event("wp-includes/demo.php"),
                                         self.baseline, {}, mismatch)
        self.assertEqual(result, "不一致")
        self.assertIn("不同", reason)

    def test_wordfence_no_false_verified(self):
        def fail_fetch(*args):
            raise AssertionError("dynamic file must not trigger download")
        result, reason = v.source_result(
            self.event("wp-content/wflogs/config-synced.php"),
            self.baseline, {}, fail_fetch)
        self.assertEqual(result, "未核验")
        self.assertIn("无固定", reason)

    def test_vf_release_archive_digest_is_verified_before_file(self):
        plugin = (self.root / "wp-content/plugins/vf-ops/includes/panel.php").read_bytes()
        primary = (self.root / "wp-content/plugins/vf-ops/vf-ops.php").read_bytes()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("vf-ops/includes/panel.php", plugin)
            z.writestr("vf-ops/vf-ops.php", primary)
        raw = buffer.getvalue()
        data = {
            "component_id": "S01-C02", "package_slug": "vf-ops",
            "repository": "llhzx2018/vf-tools-ops",
            "target_version": "1.21.1073", "release_tag": "v1.21.1073",
            "asset_name": "vf-tools-ops_V1.21.1073.zip",
            "asset_sha256": hashlib.sha256(raw).hexdigest(),
            "asset_bytes": len(raw),
        }
        def fetch(url, cap):
            if "raw.githubusercontent.com" in url:
                return json.dumps(data).encode()
            self.assertIn("/releases/download/v1.21.1073/", url)
            return raw
        result, reason = v.source_result(
            self.event("wp-content/plugins/vf-ops/includes/panel.php"),
            self.baseline, {}, fetch)
        self.assertEqual(result, "一致")
        self.assertIn("正式发布包", reason)
        data["asset_sha256"] = "0" * 64
        result, reason = v.source_result(
            self.event("wp-content/plugins/vf-ops/includes/panel.php"),
            self.baseline, {}, fetch)
        self.assertEqual(result, "未核验")

    def test_different_version_cannot_guess_previous_release(self):
        (self.root / "wp-content/plugins/vf-ops/vf-ops.php").write_text(
            "<?php /*\nVersion: 1.21.1072\n*/", encoding="utf8")
        def fetch(url, cap):
            if "raw.githubusercontent.com" in url:
                return json.dumps({
                    "component_id": "S01-C02", "package_slug": "vf-ops",
                    "repository": "llhzx2018/vf-tools-ops", "target_version": "1.21.1073",
                    "release_tag": "v1.21.1073"}).encode()
            raise AssertionError("must not download wrong-version package")
        outcome, reason = v.source_result(
            self.event("wp-content/plugins/vf-ops/vf-ops.php"), self.baseline, {}, fetch)
        self.assertEqual(outcome, "未核验")

    def test_symlink_escape_and_traversal_fail_closed(self):
        result, reason = v.source_result(self.event("../secrets.php"), self.baseline, {})
        self.assertEqual(result, "未核验")
        (self.root / "wp-includes/out.php").symlink_to(self.root / "wp-includes/demo.php")
        result, reason = v.source_result(self.event("wp-includes/out.php"),
                                         self.baseline, {}, self.fake_wp)
        self.assertEqual(result, "未核验")
        self.assertIsNone(v.safe_relative("/etc/passwd"))
        self.assertIsNone(v.safe_relative("wp-content/../secrets.php"))

    def test_no_rewrite_scans_and_explicit_owner_trigger(self):
        shell = (PKG / "intrusion-evidence.sh").read_text(encoding="utf8")
        self.assertIn("V 只读核验文件来源", shell)
        self.assertIn('python3 "$SCRIPT_DIR/lib/intrusion_verify.py"', shell)
        self.assertIn('confirm_numeric', shell)
        self.assertIn('helper report --overview', shell)
        ov = (PKG / "lib/intrusion_evidence.py").read_text(encoding="utf8")
        self.assertNotIn("来源类别：{source_hint(path)}", ov)
        src = (PKG / "lib/intrusion_verify.py").read_text(encoding="utf8")
        for prohibited in ("subprocess.", "os.system(", "exec(", "eval(", "write_json(", "write_events("):
            self.assertNotIn(prohibited, src)

if __name__ == "__main__":
    unittest.main()
