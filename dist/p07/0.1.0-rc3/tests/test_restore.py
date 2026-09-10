#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "vfops"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import package as package_engine  # noqa: E402
from tests.test_backup import BackupTest  # noqa: E402


class RestorePlanTest(unittest.TestCase):
    def make_verified_package(self, base: Path) -> Path:
        helper = BackupTest("test_local_backup_is_atomic_private_and_verified")
        rootfs = base / "source-rootfs"
        output = base / "backups"
        _, fake_clpctl = helper.make_cloudpanel_fixture(rootfs)
        proc = helper.run_backup(rootfs, fake_clpctl, output)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return Path(proc.stdout.strip())

    def run_plan(self, package: Path, target_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(CLI), "restore", "plan",
                "--package", str(package),
                "--target-root", str(target_root),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def tree_snapshot(self, root: Path) -> list[tuple[str, int, int]]:
        result: list[tuple[str, int, int]] = []
        for path in sorted(root.rglob("*")):
            stat_result = path.lstat()
            result.append((str(path.relative_to(root)), stat_result.st_mode, stat_result.st_size))
        return result

    def reseal_package(self, package: Path) -> None:
        (package / "checksums.sha256").unlink(missing_ok=True)
        (package / "verification.json").unlink(missing_ok=True)
        package_engine.write_checksums(package)
        verification = package_engine.verify_package(package)
        self.assertEqual(verification["status"], "PASS")
        package_engine.write_json_private(package / "verification.json", verification)

    def test_restore_plan_is_zero_write_and_contains_full_action_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_verified_package(base)
            target = base / "target-rootfs"
            target.mkdir()
            before = self.tree_snapshot(target)

            proc = self.run_plan(package, target)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("PRIVATE-RECOVERY-DB-SECRET", proc.stdout + proc.stderr)
            self.assertNotIn("SYNTHETIC-PRIVATE-KEY", proc.stdout + proc.stderr)
            plan = json.loads(proc.stdout)

            self.assertEqual(plan["schema"], "vf-server-ops.restore-plan.v1")
            self.assertEqual(plan["mode"], "DRY_RUN")
            self.assertFalse(plan["writes_performed"])
            self.assertFalse(plan["target_site_exists"])
            self.assertFalse(plan["owner_overwrite_gate_required"])
            self.assertFalse(plan["existing_site_overwrite_allowed"])
            self.assertEqual(plan["blockers"], [])
            self.assertIn(plan["status"], ("READY", "READY_WITH_GATES"))
            self.assertEqual(before, self.tree_snapshot(target))

            action_types = [item["type"] for item in plan["actions"]]
            self.assertIn("cloudpanel_site_prepare", action_types)
            self.assertIn("restore_site_files", action_types)
            self.assertIn("mysql_prepare_and_import", action_types)
            self.assertIn("restore_sqlite", action_types)
            self.assertIn("reconcile_cron", action_types)
            self.assertIn("restore_pm2_runtime", action_types)
            self.assertIn("reconcile_vhost", action_types)
            self.assertIn("install_ssl_certificate", action_types)
            self.assertIn("permissions_reconcile", action_types)
            self.assertIn("post_restore_verify", action_types)

            mysql = next(item for item in plan["actions"] if item["type"] == "mysql_prepare_and_import")
            self.assertEqual(mysql["database"], "example_prod")
            self.assertEqual(mysql["private_recovery_row"], "CAPTURED_RAW_ROW")
            self.assertFalse(mysql["credentials_emitted"])

            private = plan["private_recovery_metadata"]
            self.assertTrue(private["present"])
            self.assertIn("password", private["database_fields"])
            self.assertFalse(private["values_emitted"])

    def test_existing_target_is_blocked_during_zero_write_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_verified_package(base)
            target = base / "target-rootfs"
            existing = target / "home/alice/htdocs/example.com"
            existing.mkdir(parents=True)
            sentinel = existing / "DO_NOT_TOUCH.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            before = self.tree_snapshot(target)

            proc = self.run_plan(package, target)
            self.assertEqual(proc.returncode, 6)
            plan = json.loads(proc.stdout)
            self.assertTrue(plan["target_site_exists"])
            self.assertFalse(plan["owner_overwrite_gate_required"])
            self.assertFalse(plan["existing_site_overwrite_allowed"])
            self.assertIn("TARGET_SITE_ALREADY_EXISTS", plan["blockers"])
            self.assertNotIn("OWNER_OVERWRITE_GATE_REQUIRED", plan["gates"])
            self.assertEqual(plan["status"], "BLOCKED")
            self.assertIn("target site already exists", proc.stderr)
            self.assertIn("blocker=TARGET_STATE_CONFLICT", proc.stderr)
            self.assertEqual(before, self.tree_snapshot(target))
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")

    def test_archive_path_escape_is_blocked_even_when_package_is_resealed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_verified_package(base)
            archive_path = package / "files/site.tar.gz"

            with tarfile.open(archive_path, "w:gz") as archive:
                good = b"safe\n"
                good_info = tarfile.TarInfo("site/ok.txt")
                good_info.size = len(good)
                archive.addfile(good_info, io.BytesIO(good))

                bad = b"escape\n"
                bad_info = tarfile.TarInfo("site/../escape.txt")
                bad_info.size = len(bad)
                archive.addfile(bad_info, io.BytesIO(bad))

            self.reseal_package(package)
            target = base / "target-rootfs"
            target.mkdir()
            before = self.tree_snapshot(target)

            proc = self.run_plan(package, target)
            self.assertEqual(proc.returncode, 6)
            plan = json.loads(proc.stdout)
            self.assertEqual(plan["status"], "BLOCKED")
            self.assertTrue(any(item.startswith("ARCHIVE_PATH_ESCAPE:") for item in plan["blockers"]))
            self.assertEqual(before, self.tree_snapshot(target))
            self.assertFalse((target / "escape.txt").exists())

    def test_tampered_package_is_rejected_before_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_verified_package(base)
            target = base / "target-rootfs"
            target.mkdir()
            (package / "manifest.json").write_text("{}\n", encoding="utf-8")

            proc = self.run_plan(package, target)
            self.assertEqual(proc.returncode, 6)
            self.assertIn("failed fresh verification", proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_missing_private_db_metadata_becomes_reconciliation_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_verified_package(base)
            private_meta = package / "metadata/cloudpanel-private.json"
            private_meta.unlink()
            manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
            manifest["contents"]["metadata"]["cloudpanel_private_metadata"] = {
                "included": False,
                "status": "REMOVED_FOR_TEST",
                "file": None,
                "tables": {},
            }
            package_engine.write_json_private(package / "manifest.replacement.json", manifest)
            os.replace(package / "manifest.replacement.json", package / "manifest.json")
            self.reseal_package(package)

            target = base / "target-rootfs"
            target.mkdir()
            proc = self.run_plan(package, target)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            plan = json.loads(proc.stdout)
            self.assertEqual(plan["status"], "READY_WITH_GATES")
            self.assertIn("DATABASE_CREDENTIAL_RECONCILIATION:example_prod", plan["gates"])
            self.assertIn("DATABASE_CREDENTIAL_RECONCILIATION_REQUIRED", plan["gates"])


if __name__ == "__main__":
    unittest.main()
