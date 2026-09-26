#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.test_backup import BackupTest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "vfops"
sys.path.insert(0, str(ROOT / "lib"))
import restore_new as restore_engine


class NewSiteRestoreTest(unittest.TestCase):
    def make_package(self, base: Path) -> Path:
        source = base / "source-root"
        output = base / "backups"
        helper = BackupTest()
        _, fake_export = helper.make_cloudpanel_fixture(source)
        proc = helper.run_backup(source, fake_export, output)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return Path(proc.stdout.strip())

    def make_target(self, base: Path) -> Path:
        root = base / "target-root"
        root.mkdir()
        (root / ".vfops-controlled-cloudpanel-target").write_text(
            "VF_SERVER_OPS_CONTROLLED_CLOUDPANEL_TARGET_V1\n", encoding="utf-8"
        )
        return root

    def make_fake_clpctl(self, base: Path) -> Path:
        script = base / "fake-new-site-clpctl"
        script.write_text(
            r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import shutil
import sys

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
args = {}
for item in sys.argv[2:]:
    if item.startswith("--") and "=" in item:
        key, value = item[2:].split("=", 1)
        args[key] = value
root = Path(os.environ["VFOPS_FAKE_TARGET_ROOT"])
state = Path(os.environ["VFOPS_FAKE_DB_STATE"])
state.mkdir(parents=True, exist_ok=True)
log = Path(os.environ["VFOPS_FAKE_CLPCTL_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "command": cmd,
        "domain": args.get("domainName"),
        "database": args.get("databaseName"),
        "database_user": args.get("databaseUserName"),
    }, sort_keys=True) + "\n")

fail = os.environ.get("VFOPS_FAIL_COMMAND")
if fail == cmd:
    sys.exit(9)

if cmd == "db:add" and os.environ.get("VFOPS_REJECT_LEGACY_DB_USER") == "1":
    if "_" in args.get("databaseUserName", ""):
        sys.exit(9)

if cmd.startswith("site:add:"):
    domain = args["domainName"]
    user = args["siteUser"]
    site = root / "home" / user / "htdocs" / domain
    site.mkdir(parents=True, exist_ok=False)
    (site / "index.html").write_text("cloudpanel bootstrap\n", encoding="utf-8")
    sys.exit(0)

if cmd == "db:import":
    shutil.copy2(Path(args["file"]), state / f"{args['databaseName']}.sql.gz")
    sys.exit(0)

if cmd == "db:export":
    source = state / f"{args['databaseName']}.sql.gz"
    if not source.is_file():
        sys.exit(8)
    target = Path(args["file"])
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    sys.exit(0)

if cmd == "db:delete":
    (state / f"{args['databaseName']}.sql.gz").unlink(missing_ok=True)
    sys.exit(0)

if cmd == "site:delete":
    domain = args.get("domainName", "")
    htdocs = root / "home" / "alice" / "htdocs" / domain
    if htdocs.exists():
        shutil.rmtree(htdocs)
    sys.exit(0)

sys.exit(0)
''',
            encoding="utf-8",
        )
        script.chmod(0o700)
        return script

    def env(self, base: Path, target: Path, fail: str | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env["VFOPS_FAKE_TARGET_ROOT"] = str(target)
        env["VFOPS_FAKE_DB_STATE"] = str(base / "db-state")
        env["VFOPS_FAKE_CLPCTL_LOG"] = str(base / "clpctl.log")
        if fail:
            env["VFOPS_FAIL_COMMAND"] = fail
        return env

    def confirmation(self, package: Path) -> str:
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        return f"RESTORE_NEW_SITE:{manifest['site']['domain']}:{manifest['backup_id']}"

    def run_restore(self, package: Path, target: Path, fake: Path, env: dict[str, str], confirm: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(CLI), "restore", "apply-new-site",
                "--package", str(package),
                "--target-root", str(target),
                "--clpctl", str(fake),
                "--confirm", confirm,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_new_site_restore_handles_cloudpanel_created_directory_and_verifies_before_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            target = self.make_target(base)
            fake = self.make_fake_clpctl(base)
            env = self.env(base, target)
            proc = self.run_restore(package, target, fake, env, self.confirmation(package))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("PRIVATE-RECOVERY-DB-SECRET", proc.stdout + proc.stderr)
            self.assertNotIn("SYNTHETIC-PRIVATE-KEY", proc.stdout + proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "NEW_SITE_RESTORE_VERIFIED")
            self.assertEqual(result["restore_verify_status"], "RESTORE_VERIFIED")
            self.assertTrue(result["owner_confirmation_verified"])
            self.assertFalse(result["existing_site_overwrite_allowed"])
            self.assertTrue(result["site_ownership_reconciled"])
            self.assertEqual(result["site_ownership_source"], "CLOUDPANEL_BOOTSTRAP_UID_GID")
            self.assertIn("site_ownership_reconciled_from_cloudpanel_bootstrap", result["steps"])
            self.assertEqual(result["failure_cleanup_contract"], "CREATED_DATABASE_DELETE_ATTEMPT; SITE_DELETE_REQUESTED")
            self.assertFalse(result["cron_enabled"])
            self.assertFalse(result["pm2_started"])
            self.assertFalse(result["dns_changed"])
            self.assertFalse(result["cutover_ready"])

            site = target / "home/alice/htdocs/example.com"
            self.assertTrue((site / "public/index.php").is_file())
            self.assertFalse((site / "index.html").exists())
            self.assertFalse(any(item.name.startswith(".vfops-bootstrap-") for item in site.parent.iterdir()))
            evidence = target / "var/lib/vf-server-ops/restored-metadata" / package.name
            self.assertTrue(evidence.is_dir())

            commands = [json.loads(line)["command"] for line in (base / "clpctl.log").read_text(encoding="utf-8").splitlines()]
            self.assertIn("site:add:php", commands)
            self.assertIn("db:add", commands)
            self.assertIn("db:import", commands)
            self.assertIn("site:install:certificate", commands)
            self.assertIn("db:export", commands)  # post-restore verify

    def test_legacy_database_user_rejected_by_cloudpanel_is_remapped_and_wp_config_updated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source-root"
            output = base / "backups"
            helper = BackupTest()
            site_root, fake_export = helper.make_cloudpanel_fixture(source)
            (site_root / "wp-config.php").write_text(
                "<?php\n"
                "define('DB_NAME', 'example_prod');\n"
                "define('DB_USER', 'example_user');\n"
                "define('DB_PASSWORD', 'PRIVATE-RECOVERY-DB-SECRET');\n",
                encoding="utf-8",
            )
            proc = helper.run_backup(source, fake_export, output)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            package = Path(proc.stdout.strip())

            target = self.make_target(base)
            fake = self.make_fake_clpctl(base)
            env = self.env(base, target)
            env["VFOPS_REJECT_LEGACY_DB_USER"] = "1"

            restored = self.run_restore(package, target, fake, env, self.confirmation(package))
            self.assertEqual(restored.returncode, 0, restored.stderr)
            result = json.loads(restored.stdout)
            self.assertTrue(result["database_identity_remapped"])
            self.assertEqual(result["application_config_mode"], "WORDPRESS_WP_CONFIG")
            self.assertEqual(result["application_config_file"], "wp-config.php")

            config = (target / "home/alice/htdocs/example.com/wp-config.php").read_text(encoding="utf-8")
            self.assertNotIn("example_user", config)
            self.assertNotIn("PRIVATE-RECOVERY-DB-SECRET", config)
            self.assertRegex(config, r"define\('DB_USER', 'p07u[A-Za-z0-9]+'\);")

            rows = [json.loads(line) for line in (base / "clpctl.log").read_text(encoding="utf-8").splitlines()]
            db_adds = [row for row in rows if row["command"] == "db:add"]
            self.assertEqual(len(db_adds), 2)
            self.assertEqual(db_adds[0]["database_user"], "example_user")
            self.assertNotIn("_", db_adds[1]["database_user"])

    def test_site_ownership_reconciliation_uses_bootstrap_identity_without_following_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            staged = base / "staged"
            staged.mkdir()
            regular = staged / "payload.txt"
            regular.write_text("payload\n", encoding="utf-8")
            nested = staged / "nested"
            nested.mkdir()
            link = staged / "payload-link"
            link.symlink_to("payload.txt")
            reference = base / "cloudpanel-bootstrap"
            reference.mkdir()
            ref = reference.stat()
            calls: list[tuple[Path, int, int, bool]] = []

            def capture(path: os.PathLike[str] | str, uid: int, gid: int, *, follow_symlinks: bool = True) -> None:
                calls.append((Path(path), uid, gid, follow_symlinks))

            with mock.patch.object(restore_engine.os, "chown", side_effect=capture):
                uid, gid = restore_engine.reconcile_site_ownership(staged, reference)

            self.assertEqual((uid, gid), (ref.st_uid, ref.st_gid))
            touched = {item[0] for item in calls}
            self.assertTrue({staged, regular, nested, link}.issubset(touched))
            self.assertTrue(all(item[1:3] == (ref.st_uid, ref.st_gid) for item in calls))
            self.assertTrue(all(item[3] is False for item in calls))

    def test_site_ownership_reconciliation_fails_closed_on_chown_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            staged = base / "staged"
            staged.mkdir()
            (staged / "payload.txt").write_text("payload\n", encoding="utf-8")
            reference = base / "cloudpanel-bootstrap"
            reference.mkdir()
            with mock.patch.object(restore_engine.os, "chown", side_effect=PermissionError("denied")):
                with self.assertRaisesRegex(restore_engine.NewSiteRestoreError, "ownership reconciliation failed"):
                    restore_engine.reconcile_site_ownership(staged, reference)

    def test_wrong_owner_confirmation_blocks_before_site_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            target = self.make_target(base)
            fake = self.make_fake_clpctl(base)
            env = self.env(base, target)
            proc = self.run_restore(package, target, fake, env, "WRONG")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("explicit confirmation required", proc.stderr)
            self.assertFalse((base / "clpctl.log").exists())
            self.assertFalse((target / "home").exists())

    def test_existing_target_site_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            target = self.make_target(base)
            existing = target / "home/alice/htdocs/example.com"
            existing.mkdir(parents=True)
            keep = existing / "keep.txt"
            keep.write_text("preserve\n", encoding="utf-8")
            fake = self.make_fake_clpctl(base)
            env = self.env(base, target)
            proc = self.run_restore(package, target, fake, env, self.confirmation(package))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("refuses overwrite", proc.stderr)
            self.assertEqual(keep.read_text(encoding="utf-8"), "preserve\n")
            self.assertFalse((base / "clpctl.log").exists())

    def test_db_import_failure_deletes_created_database_before_site_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            target = self.make_target(base)
            fake = self.make_fake_clpctl(base)
            env = self.env(base, target, fail="db:import")
            proc = self.run_restore(package, target, fake, env, self.confirmation(package))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("cleanup=DATABASE_DELETE_REQUESTED;SITE_DELETE_REQUESTED", proc.stderr)
            self.assertFalse((target / "home/alice/htdocs/example.com").exists())
            commands = [json.loads(line)["command"] for line in (base / "clpctl.log").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(commands[-2:], ["db:delete", "site:delete"])

    def test_restore_verify_failure_deletes_imported_database_before_site_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
            database = manifest["contents"]["mysql"][0]["database"]
            target = self.make_target(base)
            fake = self.make_fake_clpctl(base)
            env = self.env(base, target, fail="db:export")
            proc = self.run_restore(package, target, fake, env, self.confirmation(package))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("stage=RESTORE_VERIFY_MYSQL", proc.stderr)
            self.assertIn("cleanup=DATABASE_DELETE_REQUESTED;SITE_DELETE_REQUESTED", proc.stderr)
            self.assertFalse((base / "db-state" / f"{database}.sql.gz").exists())
            self.assertFalse((target / "home/alice/htdocs/example.com").exists())
            commands = [json.loads(line)["command"] for line in (base / "clpctl.log").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(commands[-2:], ["db:delete", "site:delete"])

    def test_controlled_target_marker_is_required_for_non_root_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            target = base / "target-root"
            target.mkdir()
            fake = self.make_fake_clpctl(base)
            env = self.env(base, target)
            proc = self.run_restore(package, target, fake, env, self.confirmation(package))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("target marker is missing", proc.stderr)
            self.assertFalse((base / "clpctl.log").exists())


if __name__ == "__main__":
    unittest.main()