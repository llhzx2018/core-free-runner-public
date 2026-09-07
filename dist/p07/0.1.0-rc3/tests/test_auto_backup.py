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
        cfg.write_text(json.dumps({
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
        }), encoding="utf-8")
        return cfg

    def _run(self, root: Path, cfg: Path):
        return auto_backup.run_once(cfg, "clpctl", "rclone", root / "locks" / "auto.lock", root / "state" / "last.json", root / "empty-proc")

    def test_config_requires_google_plus_b2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root)
            payload = json.loads(cfg.read_text()); payload["remote_targets"] = ["google"]
            cfg.write_text(json.dumps(payload))
            with self.assertRaises(auto_backup.AutoBackupError): auto_backup.validate_config(cfg)

    def test_schedule_collision_recommends_stagger(self):
        with tempfile.TemporaryDirectory() as td:
            cron = Path(td) / "backup"
            cron.write_text("30 3 * * * root /usr/local/bin/cloudpanel-backup\n")
            result = auto_backup.schedule_collisions("03:30", [cron])
            self.assertEqual(result["status"], "COLLISION")
            self.assertNotEqual(result["recommended_at"], "03:30")

    def test_recommendation_avoids_other_backup_job_too(self):
        with tempfile.TemporaryDirectory() as td:
            cron = Path(td) / "backup"
            cron.write_text(
                "30 3 * * * root /usr/local/bin/cloudpanel-backup\n"
                "15 4 * * * root /usr/local/bin/restic-backup\n",
                encoding="utf-8",
            )
            result = auto_backup.schedule_collisions("03:30", [cron])
            recommended = auto_backup._time_minutes(result["recommended_at"])
            self.assertGreater(auto_backup._minute_distance(recommended, auto_backup._time_minutes("03:30")), auto_backup.COLLISION_WINDOW_MINUTES)
            self.assertGreater(auto_backup._minute_distance(recommended, auto_backup._time_minutes("04:15")), auto_backup.COLLISION_WINDOW_MINUTES)

    def test_non_backup_cron_does_not_collide(self):
        with tempfile.TemporaryDirectory() as td:
            cron = Path(td) / "normal"; cron.write_text("30 3 * * * root /usr/local/bin/report-health\n")
            self.assertEqual(auto_backup.schedule_collisions("03:30", [cron])["status"], "CLEAR")

    def test_busy_defers_without_backup_or_upload(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root)
            with mock.patch.object(auto_backup, "_busy_processes", return_value=[{"pid": 99, "class": "BACKUP_RESTORE_MIGRATION_OR_STORAGE"}]), \
                 mock.patch.object(auto_backup.package_engine, "build_backup") as build, \
                 mock.patch.object(auto_backup.storage_engine, "push") as push:
                result = auto_backup.run_once(cfg, "clpctl", "rclone", root / "auto.lock", root / "state.json", root / "proc")
            self.assertEqual(result["status"], "SKIPPED_BUSY")
            build.assert_not_called(); push.assert_not_called()
            self.assertEqual(json.loads((root / "state.json").read_text())["status"], "SKIPPED_BUSY")

    def test_busy_scanner_recognizes_storage_and_cloudpanel_backup(self):
        with tempfile.TemporaryDirectory() as td:
            proc = Path(td)
            for pid, cmd in [("101", b"/opt/vf-server-ops/bin/vfops\x00storage\x00push\x00"), ("102", b"/usr/bin/cloudpanel-backup\x00")]:
                p = proc / pid; p.mkdir(); (p / "cmdline").write_bytes(cmd)
            found = auto_backup._busy_processes(proc)
            self.assertEqual({x["pid"] for x in found}, {101, 102})

    def test_dual_pass_then_prunes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root); package = root / "backups" / "pkg"; package.mkdir(parents=True)
            calls = []
            def push(_cfg, _pkg, target, _rclone): calls.append(target); return {"status":"PASS","account_id":target}
            with mock.patch.object(auto_backup, "storage_structure", return_value={"dual_remote_configured": True}), mock.patch.object(auto_backup, "_busy_processes", return_value=[]), mock.patch.object(auto_backup.package_engine, "build_backup", return_value=package), mock.patch.object(auto_backup.storage_engine, "push", side_effect=push), mock.patch.object(auto_backup, "prune_local", return_value=["old"]) as prune:
                result = self._run(root, cfg)
            self.assertEqual(result["status"], "PASS"); self.assertEqual(calls, ["google", "b2"]); prune.assert_called_once()

    def test_one_remote_failure_keeps_local_and_skips_prune(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root); package = root / "backups" / "pkg"; package.mkdir(parents=True)
            calls = []
            def push(_cfg, _pkg, target, _rclone):
                calls.append(target)
                if target == "google": return {"status":"PASS","account_id":"g"}
                raise auto_backup.storage_engine.StorageError("down")
            with mock.patch.object(auto_backup, "storage_structure", return_value={"dual_remote_configured": True}), mock.patch.object(auto_backup, "_busy_processes", return_value=[]), mock.patch.object(auto_backup.package_engine, "build_backup", return_value=package), mock.patch.object(auto_backup.storage_engine, "push", side_effect=push), mock.patch.object(auto_backup, "prune_local") as prune:
                result = self._run(root, cfg)
            self.assertEqual(result["status"], "FAIL"); self.assertEqual(calls, ["google", "b2"]); prune.assert_not_called(); self.assertTrue(package.exists())

    def test_google_failure_still_attempts_b2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root); package = root / "backups" / "pkg"; package.mkdir(parents=True)
            calls = []
            def push(_cfg, _pkg, target, _rclone):
                calls.append(target)
                if target == "google": raise auto_backup.storage_engine.StorageError("down")
                return {"status":"PASS","account_id":"b2"}
            with mock.patch.object(auto_backup, "storage_structure", return_value={"dual_remote_configured": True}), mock.patch.object(auto_backup, "_busy_processes", return_value=[]), mock.patch.object(auto_backup.package_engine, "build_backup", return_value=package), mock.patch.object(auto_backup.storage_engine, "push", side_effect=push), mock.patch.object(auto_backup, "prune_local") as prune:
                result = self._run(root, cfg)
            self.assertEqual(result["status"], "FAIL"); self.assertEqual(calls, ["google", "b2"]); prune.assert_not_called()

    def test_storage_failure_writes_fail_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root)
            with mock.patch.object(auto_backup, "_busy_processes", return_value=[]), mock.patch.object(auto_backup, "storage_structure", side_effect=auto_backup.AutoBackupError("bad storage")):
                result = self._run(root, cfg)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(json.loads((root / "state" / "last.json").read_text())["status"], "FAIL")

    def test_install_disable_owned_cron_and_disabled_status(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root); cron = root / "cron" / "p07"; script = root / "auto.py"; script.write_text("#x\n")
            with mock.patch.object(auto_backup, "DEFAULT_CONFIG", cfg), mock.patch.object(auto_backup, "storage_structure", return_value={}), mock.patch.object(auto_backup.os, "geteuid", return_value=0):
                self.assertEqual(auto_backup.install_cron(cfg, cron, script, "/usr/bin/python3", root / "log", auto_backup.CONFIRM_ENABLE)["status"], "ENABLED")
                self.assertEqual(auto_backup.disable(cfg, cron, auto_backup.CONFIRM_DISABLE)["status"], "DISABLED")
                self.assertEqual(auto_backup.status(cfg, cron, root / "state")["status"], "DISABLED")

    def test_foreign_cron_is_never_overwritten_or_removed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); cfg = self._write_config(root); cron = root / "cron"; cron.write_text("# foreign\n30 3 * * * root backup\n"); script = root / "auto.py"; script.write_text("#x\n")
            with mock.patch.object(auto_backup, "DEFAULT_CONFIG", cfg), mock.patch.object(auto_backup, "storage_structure", return_value={}), mock.patch.object(auto_backup.os, "geteuid", return_value=0):
                with self.assertRaises(auto_backup.AutoBackupError): auto_backup.install_cron(cfg, cron, script, "/usr/bin/python3", root / "log", auto_backup.CONFIRM_ENABLE)
                with self.assertRaises(auto_backup.AutoBackupError): auto_backup.disable(cfg, cron, auto_backup.CONFIRM_DISABLE)
            self.assertTrue(cron.read_text().startswith("# foreign"))


if __name__ == "__main__": unittest.main()
