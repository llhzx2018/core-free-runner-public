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

import auto_backup


class AutoBackupTests(unittest.TestCase):
    def _write_config(self, root: Path, *, enabled: bool = True) -> Path:
        cfg = root / "auto-backup.json"
        payload = {
            "schema": auto_backup.CONFIG_SCHEMA,
            "enabled": enabled,
            "sites": ["example.com"],
            "daily_at": "03:30",
            "source_root": "/",
            "local_backup_dir": str(root / "backups"),
            "storage_config": str(root / "storage.json"),
            "remote_targets": ["google", "b2"],
            "local_keep_last": 7,
            "manual_backups_protected": True,
        }
        cfg.write_text(json.dumps(payload), encoding="utf-8")
        return cfg

    def _run(self, root: Path, cfg: Path):
        return auto_backup.run_once(
            cfg, "clpctl", "rclone",
            lock_file=root / "locks" / "auto.lock",
            state_file=root / "state" / "last.json",
            proc_root=root / "empty-proc",
        )

    def test_config_requires_google_plus_b2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root)
            payload = json.loads(cfg.read_text(encoding="utf-8")); payload["remote_targets"] = ["google"]
            cfg.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(auto_backup.AutoBackupError): auto_backup.validate_config(cfg)

    def test_schedule_collision_recommends_stagger(self):
        with tempfile.TemporaryDirectory() as td:
            cron = Path(td) / "cloudpanel-backup"
            cron.write_text("30 3 * * * root /usr/local/bin/cloudpanel-backup\n", encoding="utf-8")
            result = auto_backup.schedule_collisions("03:30", [cron])
            self.assertEqual(result["status"], "COLLISION")
            self.assertEqual(result["collision_count"], 1)
            self.assertNotEqual(result["recommended_at"], "03:30")

    def test_non_backup_cron_does_not_collide(self):
        with tempfile.TemporaryDirectory() as td:
            cron = Path(td) / "normal"
            cron.write_text("30 3 * * * root /usr/local/bin/report-health\n", encoding="utf-8")
            self.assertEqual(auto_backup.schedule_collisions("03:30", [cron])["status"], "CLEAR")

    def test_busy_defers_without_backup_or_upload(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root)
            with mock.patch.object(auto_backup, "storage_structure") as storage, \
                 mock.patch.object(auto_backup, "_busy_processes", return_value=[{"pid": 99, "class": "P07_BACKUP_RESTORE_MIGRATION"}]), \
                 mock.patch.object(auto_backup.package_engine, "build_backup") as build, \
                 mock.patch.object(auto_backup.storage_engine, "push") as push:
                result = auto_backup.run_once(cfg, "clpctl", "rclone", root / "auto.lock", root / "state.json", root / "proc")
            self.assertEqual(result["status"], "SKIPPED_BUSY")
            storage.assert_not_called(); build.assert_not_called(); push.assert_not_called()
            self.assertEqual(json.loads((root / "state.json").read_text())["status"], "SKIPPED_BUSY")

    def test_dual_pass_then_prunes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root)
            package = root / "backups" / "example-backup"; package.mkdir(parents=True)
            calls = []
            def fake_push(config_path, package_dir, target, rclone):
                calls.append(target); return {"status": "PASS", "account_id": target + "-a"}
            with mock.patch.object(auto_backup, "storage_structure", return_value={"dual_remote_configured": True}), \
                 mock.patch.object(auto_backup, "_busy_processes", return_value=[]), \
                 mock.patch.object(auto_backup.package_engine, "build_backup", return_value=package), \
                 mock.patch.object(auto_backup.storage_engine, "push", side_effect=fake_push), \
                 mock.patch.object(auto_backup, "prune_local", return_value=["old-auto"]) as prune:
                result = self._run(root, cfg)
            self.assertEqual(result["status"], "PASS"); self.assertEqual(calls, ["google", "b2"]); prune.assert_called_once()
            self.assertEqual(result["sites"][0]["dual_remote"], "PASS")

    def test_b2_failure_keeps_local_and_skips_prune(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root)
            package = root / "backups" / "example-backup"; package.mkdir(parents=True)
            calls = []
            def fake_push(config_path, package_dir, target, rclone):
                calls.append(target)
                if target == "google": return {"status": "PASS", "account_id": "google-a"}
                raise auto_backup.storage_engine.StorageError("b2 unavailable")
            with mock.patch.object(auto_backup, "storage_structure", return_value={"dual_remote_configured": True}), \
                 mock.patch.object(auto_backup, "_busy_processes", return_value=[]), \
                 mock.patch.object(auto_backup.package_engine, "build_backup", return_value=package), \
                 mock.patch.object(auto_backup.storage_engine, "push", side_effect=fake_push), \
                 mock.patch.object(auto_backup, "prune_local") as prune:
                result = self._run(root, cfg)
            self.assertEqual(result["status"], "FAIL"); self.assertEqual(calls, ["google", "b2"]); prune.assert_not_called(); self.assertTrue(package.exists())

    def test_google_failure_still_attempts_b2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root)
            package = root / "backups" / "example-backup"; package.mkdir(parents=True)
            calls = []
            def fake_push(config_path, package_dir, target, rclone):
                calls.append(target)
                if target == "google": raise auto_backup.storage_engine.StorageError("google unavailable")
                return {"status": "PASS", "account_id": "b2-dr"}
            with mock.patch.object(auto_backup, "storage_structure", return_value={"dual_remote_configured": True}), \
                 mock.patch.object(auto_backup, "_busy_processes", return_value=[]), \
                 mock.patch.object(auto_backup.package_engine, "build_backup", return_value=package), \
                 mock.patch.object(auto_backup.storage_engine, "push", side_effect=fake_push), \
                 mock.patch.object(auto_backup, "prune_local") as prune:
                result = self._run(root, cfg)
            self.assertEqual(result["status"], "FAIL"); self.assertEqual(calls, ["google", "b2"]); prune.assert_not_called(); self.assertTrue(package.exists())

    def test_install_disable_owned_cron_and_disabled_status(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root); cron = root / "cron" / "vf-server-ops-auto-backup"
            script = root / "auto_backup.py"; script.write_text("# test\n"); log = root / "log" / "auto.log"
            with mock.patch.object(auto_backup, "DEFAULT_CONFIG", cfg), mock.patch.object(auto_backup, "storage_structure", return_value={"dual_remote_configured": True}), mock.patch.object(auto_backup.os, "geteuid", return_value=0):
                self.assertEqual(auto_backup.install_cron(cfg, cron, script, "/usr/bin/python3", log, auto_backup.CONFIRM_ENABLE)["status"], "ENABLED")
                self.assertTrue(cron.read_text().startswith(auto_backup.CRON_MARKER + "\n"))
                self.assertEqual(auto_backup.disable(cfg, cron, auto_backup.CONFIRM_DISABLE)["status"], "DISABLED")
                self.assertEqual(auto_backup.status(cfg, cron, root / "missing-state.json")["status"], "DISABLED")

    def test_install_refuses_foreign_cron_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root); cron = root / "foreign-cron"
            cron.write_text("# somebody else\n30 3 * * * root backup-other\n"); script = root / "auto_backup.py"; script.write_text("# test\n")
            with mock.patch.object(auto_backup, "DEFAULT_CONFIG", cfg), mock.patch.object(auto_backup, "storage_structure", return_value={"dual_remote_configured": True}), mock.patch.object(auto_backup.os, "geteuid", return_value=0):
                with self.assertRaises(auto_backup.AutoBackupError): auto_backup.install_cron(cfg, cron, script, "/usr/bin/python3", root / "log", auto_backup.CONFIRM_ENABLE)
            self.assertTrue(cron.read_text().startswith("# somebody else"))

    def test_disable_refuses_foreign_cron_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root); cron = root / "foreign-cron"
            cron.write_text("# somebody else\n* * * * * root true\n")
            with mock.patch.object(auto_backup.os, "geteuid", return_value=0):
                with self.assertRaises(auto_backup.AutoBackupError): auto_backup.disable(cfg, cron, auto_backup.CONFIRM_DISABLE)
            self.assertTrue(cron.exists())


if __name__ == "__main__": unittest.main()
