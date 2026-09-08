#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
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
                name = args[2]
                mapping = {
                    "gdrive": "[gdrive]\ntype = drive\n",
                    "gdrive-crypt": "[gdrive-crypt]\ntype = crypt\nremote = gdrive:backup\npassword = *** ENCRYPTED ***\n",
                }
                return Proc(0, mapping[name])
            if args[0] == "about":
                return Proc(0, '{"free": 10000000000}')
            if args[:2] == ["backend", "encode"]:
                return Proc(0, "encoded")
            return Proc(1, "")
        with mock.patch.object(storage_setup, "run", side_effect=fake_run):
            result = storage_setup.verify_google_pair("rclone", "gdrive", "gdrive-crypt")
        self.assertEqual(result["direct"], "gdrive")
        self.assertEqual(result["crypt"], "gdrive-crypt")

    def test_verify_b2_crypt_requires_b2_underlying(self):
        def fake_run(_rclone, args, timeout=30):
            if args[:2] == ["config", "redacted"]:
                name = args[2]
                mapping = {
                    "b2": "[b2]\ntype = b2\naccount = XXX\nkey = XXX\n",
                    "b2-crypt": "[b2-crypt]\ntype = crypt\nremote = b2:backup\npassword = XXX\n",
                }
                return Proc(0, mapping[name])
            if args[:2] == ["backend", "encode"]:
                return Proc(0, "encoded")
            return Proc(1, "")
        with mock.patch.object(storage_setup, "run", side_effect=fake_run):
            result = storage_setup.verify_b2_crypt("rclone", "b2-crypt")
        self.assertEqual(result, {"direct": "b2", "crypt": "b2-crypt"})

    def test_google_crypt_must_point_to_selected_google(self):
        def fake_run(_rclone, args, timeout=30):
            if args[:2] == ["config", "redacted"]:
                name = args[2]
                if name == "g1": return Proc(0, "type = drive\n")
                if name == "gcrypt": return Proc(0, "type = crypt\nremote = g2:path\n")
            return Proc(1, "")
        with mock.patch.object(storage_setup, "run", side_effect=fake_run):
            with self.assertRaises(storage_setup.SetupError):
                storage_setup.verify_google_pair("rclone", "g1", "gcrypt")

    def test_host_binding_is_deterministic_and_not_plain_machine_id(self):
        with tempfile.TemporaryDirectory() as td:
            machine_id = Path(td) / "machine-id"
            machine_id.write_text("machine-secret-looking-id\n", encoding="utf-8")
            first = storage_setup.host_binding(machine_id)
            second = storage_setup.host_binding(machine_id)
            self.assertEqual(first, second)
            self.assertRegex(first, r"^sha256:[0-9a-f]{64}$")
            self.assertNotIn("machine-secret-looking-id", first)

    def test_host_binding_fails_closed_when_machine_id_missing_or_empty(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing"
            with self.assertRaises(storage_setup.SetupError):
                storage_setup.host_binding(missing)
            empty = Path(td) / "empty"
            empty.write_text("\n", encoding="utf-8")
            with self.assertRaises(storage_setup.SetupError):
                storage_setup.host_binding(empty)

    def test_build_config_has_no_secret_fields_and_host_bound_fresh_provenance(self):
        binding = "sha256:" + "a" * 64
        payload = storage_setup.build_config("gdrive", "gdrive-crypt", "b2-crypt", binding)
        raw = json.dumps(payload).lower()
        self.assertNotIn("token", raw)
        self.assertNotIn("password", raw)
        self.assertNotIn("secret_key", raw)
        self.assertEqual(payload["google_pool"][0]["quota_remote"], "gdrive")
        self.assertEqual(payload["backblaze_b2"]["remote"], "b2-crypt")
        self.assertEqual(
            payload["setup_provenance"],
            {"version": 1, "mode": storage_setup.PROVENANCE_FRESH, "host_binding": binding},
        )

    def test_provenance_rejects_invalid_binding(self):
        with self.assertRaises(storage_setup.SetupError):
            storage_setup.provenance_payload("machine-id-plain-text")
        with self.assertRaises(storage_setup.SetupError):
            storage_setup.provenance_payload("sha256:abc")

    def test_configure_writes_0600_only_after_host_and_both_remotes_verify(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "storage.json"
            machine_id = root / "machine-id"
            machine_id.write_text("host-a\n", encoding="utf-8")
            with mock.patch.object(storage_setup, "verify_google_pair", return_value={"direct":"gdrive","crypt":"gdrive-crypt","quota":{}}), \
                 mock.patch.object(storage_setup, "verify_b2_crypt", return_value={"direct":"b2","crypt":"b2-crypt"}), \
                 mock.patch.object(storage_setup.os, "geteuid", return_value=0):
                result = storage_setup.configure("rclone", out, "gdrive", "gdrive-crypt", "b2-crypt", machine_id)
            self.assertEqual(result["status"], "PASS")
            payload = json.loads(out.read_text())
            self.assertEqual(payload["schema"], storage_setup.SCHEMA)
            self.assertEqual(payload["setup_provenance"]["mode"], storage_setup.PROVENANCE_FRESH)
            self.assertEqual(payload["setup_provenance"]["host_binding"], storage_setup.host_binding(machine_id))
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
            self.assertTrue(result["setup_provenance"]["local_host_bound"])
            self.assertNotIn("host_binding", result["setup_provenance"])
            self.assertFalse(result["secrets_written_to_p07_config"])

    def test_copied_fresh_config_does_not_match_another_host_binding(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_id = root / "source-machine-id"
            target_id = root / "target-machine-id"
            source_id.write_text("source-vps\n", encoding="utf-8")
            target_id.write_text("target-vps\n", encoding="utf-8")
            source_binding = storage_setup.host_binding(source_id)
            target_binding = storage_setup.host_binding(target_id)
            payload = storage_setup.build_config("gdrive", "gdrive-crypt", "b2-crypt", source_binding)
            self.assertNotEqual(payload["setup_provenance"]["host_binding"], target_binding)

    def test_configure_does_not_write_when_b2_verify_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "storage.json"
            machine_id = root / "machine-id"
            machine_id.write_text("host-a\n", encoding="utf-8")
            with mock.patch.object(storage_setup, "verify_google_pair", return_value={"direct":"gdrive","crypt":"gdrive-crypt","quota":{}}), \
                 mock.patch.object(storage_setup, "verify_b2_crypt", side_effect=storage_setup.SetupError("bad b2")):
                with self.assertRaises(storage_setup.SetupError):
                    storage_setup.configure("rclone", out, "gdrive", "gdrive-crypt", "b2-crypt", machine_id)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
