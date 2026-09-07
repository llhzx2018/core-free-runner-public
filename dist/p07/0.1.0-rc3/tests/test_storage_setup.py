#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
BASE_LIB = ROOT.parent / "0.1.0-rc2" / "vf-server-ops" / "lib"
OVERLAY_LIB = ROOT / "overlay" / "lib"
sys.path.insert(0, str(BASE_LIB))
sys.path.insert(0, str(OVERLAY_LIB))
import storage_setup


class Proc:
    def __init__(self, rc=0, out=""):
        self.returncode = rc
        self.stdout = out
        self.stderr = ""


class StorageSetupTests(unittest.TestCase):
    def test_list_remotes_only_returns_names(self):
        with mock.patch.object(storage_setup, "run", return_value=Proc(0, "gdrive:\ngdrive-crypt:\nb2-crypt:\n")):
            self.assertEqual(storage_setup.list_remotes("rclone"), ["gdrive", "gdrive-crypt", "b2-crypt"])

    def test_verify_google_pair_requires_drive_and_matching_crypt(self):
        def fake_run(_rclone, args, timeout=30):
            if args[:2] == ["config", "redacted"]:
                mapping = {
                    "gdrive": "[gdrive]\ntype = drive\n",
                    "gdrive-crypt": "[gdrive-crypt]\ntype = crypt\nremote = gdrive:backup\npassword = *** ENCRYPTED ***\n",
                }
                return Proc(0, mapping[args[2]])
            if args[0] == "about": return Proc(0, '{"free": 10000000000}')
            if args[:2] == ["backend", "encode"]: return Proc(0, "encoded")
            return Proc(1, "")
        with mock.patch.object(storage_setup, "run", side_effect=fake_run):
            result = storage_setup.verify_google_pair("rclone", "gdrive", "gdrive-crypt")
        self.assertEqual(result["direct"], "gdrive")

    def test_verify_b2_crypt_requires_b2_underlying(self):
        def fake_run(_rclone, args, timeout=30):
            if args[:2] == ["config", "redacted"]:
                mapping = {
                    "b2": "[b2]\ntype = b2\naccount = XXX\nkey = XXX\n",
                    "b2-crypt": "[b2-crypt]\ntype = crypt\nremote = b2:backup\npassword = XXX\n",
                }
                return Proc(0, mapping[args[2]])
            if args[:2] == ["backend", "encode"]: return Proc(0, "encoded")
            return Proc(1, "")
        with mock.patch.object(storage_setup, "run", side_effect=fake_run):
            self.assertEqual(storage_setup.verify_b2_crypt("rclone", "b2-crypt"), {"direct":"b2","crypt":"b2-crypt"})

    def test_google_crypt_must_point_to_selected_google(self):
        def fake_run(_rclone, args, timeout=30):
            if args[:2] == ["config", "redacted"]:
                if args[2] == "g1": return Proc(0, "type = drive\n")
                if args[2] == "gcrypt": return Proc(0, "type = crypt\nremote = g2:path\n")
            return Proc(1, "")
        with mock.patch.object(storage_setup, "run", side_effect=fake_run):
            with self.assertRaises(storage_setup.SetupError): storage_setup.verify_google_pair("rclone", "g1", "gcrypt")

    def test_build_config_has_no_secret_fields(self):
        payload = storage_setup.build_config("gdrive", "gdrive-crypt", "b2-crypt")
        raw = json.dumps(payload).lower()
        self.assertNotIn("token", raw); self.assertNotIn("password", raw); self.assertNotIn("secret_key", raw)
        self.assertEqual(payload["google_pool"][0]["quota_remote"], "gdrive")
        self.assertEqual(payload["backblaze_b2"]["remote"], "b2-crypt")

    def test_configure_writes_0600_only_after_both_verify(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "storage.json"
            with mock.patch.object(storage_setup, "verify_google_pair", return_value={"direct":"gdrive","crypt":"gdrive-crypt","quota":{}}), mock.patch.object(storage_setup, "verify_b2_crypt", return_value={"direct":"b2","crypt":"b2-crypt"}), mock.patch.object(storage_setup.os, "geteuid", return_value=0):
                result = storage_setup.configure("rclone", out, "gdrive", "gdrive-crypt", "b2-crypt")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
            self.assertFalse(result["secrets_written_to_p07_config"])

    def test_configure_does_not_write_when_b2_verify_fails(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "storage.json"
            with mock.patch.object(storage_setup, "verify_google_pair", return_value={"direct":"gdrive","crypt":"gdrive-crypt","quota":{}}), mock.patch.object(storage_setup, "verify_b2_crypt", side_effect=storage_setup.SetupError("bad b2")):
                with self.assertRaises(storage_setup.SetupError): storage_setup.configure("rclone", out, "gdrive", "gdrive-crypt", "b2-crypt")
            self.assertFalse(out.exists())


if __name__ == "__main__": unittest.main()
