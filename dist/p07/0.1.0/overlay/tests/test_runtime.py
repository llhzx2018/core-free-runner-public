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

from tests.test_restore_new import NewSiteRestoreTest
from tests.test_backup import BackupTest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "vfops"
sys.path.insert(0, str(ROOT / "lib"))
import runtime as runtime_engine


class RuntimeActivationTest(unittest.TestCase):
    def prepare_restored_target(self, base: Path) -> tuple[Path, Path, Path]:
        helper = NewSiteRestoreTest()
        package = helper.make_package(base)
        target = helper.make_target(base)
        fake_clpctl = helper.make_fake_clpctl(base)
        env = helper.env(base, target)
        restore = helper.run_restore(package, target, fake_clpctl, env, helper.confirmation(package))
        self.assertEqual(restore.returncode, 0, restore.stderr)
        return package, target, fake_clpctl

    def make_fake_crontab(self, base: Path) -> Path:
        script = base / "fake-crontab"
        script.write_text(
            r'''#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
import sys
root = Path(os.environ["VFOPS_FAKE_TARGET_ROOT"])
args = sys.argv[1:]
user = args[1] if len(args) >= 2 and args[0] == "-u" else ""
path = root / "var/spool/cron/crontabs" / user
if len(args) == 3 and args[2] == "-l":
    if path.is_file():
        print(path.read_text(encoding="utf-8"), end="")
        sys.exit(0)
    sys.exit(1)
if len(args) == 3 and args[2] == "-r":
    if os.environ.get("VFOPS_FAIL_CRON_ROLLBACK") == "1":
        sys.exit(7)
    path.unlink(missing_ok=True)
    sys.exit(0)
if len(args) == 3:
    source = Path(args[2])
    if os.environ.get("VFOPS_FAIL_CRON_ROLLBACK") == "1" and source.name == "crontab.rollback":
        sys.exit(7)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, path)
    sys.exit(0)
sys.exit(9)
''',
            encoding="utf-8",
        )
        script.chmod(0o700)
        return script

    def make_fake_runuser(self, base: Path) -> Path:
        script = base / "fake-runuser"
        script.write_text(
            r'''#!/usr/bin/env python3
import os
from pathlib import Path
import sys
log = Path(os.environ["VFOPS_FAKE_RUNTIME_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write("runuser " + " ".join(sys.argv[1:]) + "\n")
if os.environ.get("VFOPS_FAIL_RUNUSER") == "1":
    sys.exit(8)
sys.exit(0)
''',
            encoding="utf-8",
        )
        script.chmod(0o700)
        return script

    def make_fake_chown(self, base: Path) -> Path:
        script = base / "fake-chown"
        script.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        script.chmod(0o700)
        return script

    def make_nvm_pm2(self, home_root: Path, user: str, version: str) -> Path:
        pm2 = home_root / user / ".nvm" / "versions" / "node" / f"v{version}" / "bin" / "pm2"
        pm2.parent.mkdir(parents=True, exist_ok=True)
        pm2.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        pm2.chmod(0o700)
        return pm2

    def confirmation(self, package: Path) -> str:
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        return f"ACTIVATE_RUNTIME:{manifest['site']['domain']}:{manifest['backup_id']}"

    def env(
        self,
        base: Path,
        target: Path,
        fail_runuser: bool = False,
        fail_cron_rollback: bool = False,
    ) -> dict[str, str]:
        env = os.environ.copy()
        env["VFOPS_FAKE_TARGET_ROOT"] = str(target)
        env["VFOPS_FAKE_RUNTIME_LOG"] = str(base / "runtime.log")
        if fail_runuser:
            env["VFOPS_FAIL_RUNUSER"] = "1"
        if fail_cron_rollback:
            env["VFOPS_FAIL_CRON_ROLLBACK"] = "1"
        return env

    def run_runtime(
        self,
        package: Path,
        target: Path,
        crontab: Path,
        runuser: Path,
        chown: Path,
        env: dict[str, str],
        confirm: str,
        *,
        defer_system_cron: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        command = [
                str(CLI), "runtime", "apply-new-site",
                "--package", str(package), "--target-root", str(target), "--confirm", confirm,
                "--crontab", str(crontab), "--runuser", str(runuser), "--pm2", "pm2", "--chown", str(chown),
            ]
        if defer_system_cron:
            command.append("--defer-system-cron")
        return subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_runtime_plan_detects_user_crontab_and_pm2_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, target, _ = self.prepare_restored_target(base)
            proc = subprocess.run(
                [str(CLI), "runtime", "plan", "--package", str(package), "--target-root", str(target)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            plan = json.loads(proc.stdout)
            self.assertEqual(plan["status"], "READY")
            self.assertIsNotNone(plan["user_crontab"])
            self.assertTrue(plan["pm2"]["ready"])
            self.assertEqual(plan["manual_cron"], [])
            self.assertFalse(plan["writes_performed"])

    def test_pm2_dump_node_versions_reads_only_valid_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dump = Path(tmp) / "dump.pm2"
            dump.write_text(
                json.dumps([
                    {"name": "a", "node_version": "22.14.0", "env": {"PRIVATE": "do-not-read"}},
                    {"name": "b", "node_version": "v24.1.0"},
                    {"name": "c", "node_version": "../../bin/sh"},
                    {"name": "d", "node_version": "22.14.0"},
                ]),
                encoding="utf-8",
            )
            self.assertEqual(runtime_engine.pm2_dump_node_versions(dump), ["22.14.0", "24.1.0"])

    def test_site_user_nvm_pm2_selects_matching_dump_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "home"
            wanted = self.make_nvm_pm2(home, "alice", "22.14.0")
            self.make_nvm_pm2(home, "alice", "24.1.0")
            dump = base / "dump.pm2"
            dump.write_text(json.dumps([{"name": "worker", "node_version": "22.14.0"}]), encoding="utf-8")
            resolved, path_env = runtime_engine.resolve_site_user_nvm_pm2("alice", dump, home_root=home)
            self.assertEqual(resolved, str(wanted))
            self.assertTrue(path_env.startswith(str(wanted.parent) + ":"))
            self.assertIn("/usr/bin", path_env)

    def test_site_user_nvm_pm2_fails_closed_when_target_version_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "home"
            self.make_nvm_pm2(home, "alice", "24.1.0")
            dump = base / "dump.pm2"
            dump.write_text(json.dumps([{"name": "worker", "node_version": "22.14.0"}]), encoding="utf-8")
            with self.assertRaisesRegex(runtime_engine.RuntimeActivationError, "matching site-user NVM PM2 version is unavailable"):
                runtime_engine.resolve_site_user_nvm_pm2("alice", dump, home_root=home)

    def test_site_user_nvm_pm2_fails_closed_on_ambiguous_unversioned_dump(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "home"
            self.make_nvm_pm2(home, "alice", "22.14.0")
            self.make_nvm_pm2(home, "alice", "24.1.0")
            dump = base / "dump.pm2"
            dump.write_text(json.dumps([{"name": "worker"}]), encoding="utf-8")
            with self.assertRaisesRegex(runtime_engine.RuntimeActivationError, "multiple site-user NVM PM2 binaries are ambiguous"):
                runtime_engine.resolve_site_user_nvm_pm2("alice", dump, home_root=home)

    def test_site_user_nvm_pm2_rejects_invalid_site_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dump = Path(tmp) / "dump.pm2"
            dump.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(runtime_engine.RuntimeActivationError, "site user is invalid"):
                runtime_engine.resolve_site_user_nvm_pm2("../root", dump, home_root=Path(tmp) / "home")

    def test_runtime_apply_installs_user_cron_and_resurrects_pm2_without_secret_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, target, _ = self.prepare_restored_target(base)
            crontab = self.make_fake_crontab(base)
            runuser = self.make_fake_runuser(base)
            chown = self.make_fake_chown(base)
            env = self.env(base, target)
            proc = self.run_runtime(package, target, crontab, runuser, chown, env, self.confirmation(package))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("PRIVATE", proc.stdout + proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "RUNTIME_ACTIVATED")
            self.assertTrue(result["cron_installed"])
            self.assertTrue(result["pm2_started"])
            self.assertEqual(result["pm2_execution_mode"], "EXPLICIT_OR_SANDBOX_PM2")
            self.assertFalse(result["dns_changed"])
            installed_cron = target / "var/spool/cron/crontabs/alice"
            self.assertTrue(installed_cron.is_file())
            self.assertIn("--token PRIVATE", installed_cron.read_text(encoding="utf-8"))
            pm2_dump = target / "home/alice/.pm2/dump.pm2"
            self.assertTrue(pm2_dump.is_file())
            self.assertIn("pm2 resurrect", (base / "runtime.log").read_text(encoding="utf-8"))

    def test_existing_nonempty_target_crontab_blocks_before_pm2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, target, _ = self.prepare_restored_target(base)
            existing = target / "var/spool/cron/crontabs/alice"
            existing.parent.mkdir(parents=True)
            existing.write_text("0 1 * * * /do/not/replace\n", encoding="utf-8")
            crontab = self.make_fake_crontab(base)
            runuser = self.make_fake_runuser(base)
            chown = self.make_fake_chown(base)
            env = self.env(base, target)
            proc = self.run_runtime(package, target, crontab, runuser, chown, env, self.confirmation(package))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("refusing replacement", proc.stderr)
            self.assertEqual(existing.read_text(encoding="utf-8"), "0 1 * * * /do/not/replace\n")
            self.assertFalse((target / "home/alice/.pm2/dump.pm2").exists())

    def test_pm2_failure_rolls_back_new_crontab_dump_and_new_pm2_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, target, _ = self.prepare_restored_target(base)
            crontab = self.make_fake_crontab(base)
            runuser = self.make_fake_runuser(base)
            chown = self.make_fake_chown(base)
            env = self.env(base, target, fail_runuser=True)
            proc = self.run_runtime(package, target, crontab, runuser, chown, env, self.confirmation(package))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("PM2 resurrect failed", proc.stderr)
            self.assertIn("cleanup=PARTIAL", proc.stderr)  # fake runuser also fails cleanup commands
            self.assertFalse((target / "var/spool/cron/crontabs/alice").exists())
            self.assertFalse((target / "home/alice/.pm2").exists())
            log = (base / "runtime.log").read_text(encoding="utf-8")
            self.assertIn("pm2 resurrect", log)
            self.assertIn("pm2 delete all", log)
            self.assertIn("pm2 kill", log)

    def test_pm2_failure_does_not_kill_preexisting_pm2_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, target, _ = self.prepare_restored_target(base)
            existing_home = target / "home/alice/.pm2"
            existing_home.mkdir(parents=True, exist_ok=True)
            marker = existing_home / "preexisting-state"
            marker.write_text("keep\n", encoding="utf-8")
            crontab = self.make_fake_crontab(base)
            runuser = self.make_fake_runuser(base)
            chown = self.make_fake_chown(base)
            env = self.env(base, target, fail_runuser=True)
            proc = self.run_runtime(package, target, crontab, runuser, chown, env, self.confirmation(package))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("PM2 resurrect failed", proc.stderr)
            self.assertTrue(marker.is_file())
            self.assertFalse((existing_home / "dump.pm2").exists())
            log = (base / "runtime.log").read_text(encoding="utf-8")
            self.assertIn("pm2 resurrect", log)
            self.assertNotIn("pm2 delete all", log)
            self.assertNotIn("pm2 kill", log)

    def test_cron_rollback_failure_does_not_skip_pm2_cleanup_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, target, _ = self.prepare_restored_target(base)
            crontab = self.make_fake_crontab(base)
            runuser = self.make_fake_runuser(base)
            chown = self.make_fake_chown(base)
            env = self.env(base, target, fail_runuser=True, fail_cron_rollback=True)
            proc = self.run_runtime(package, target, crontab, runuser, chown, env, self.confirmation(package))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("PM2 resurrect failed", proc.stderr)
            self.assertIn("cleanup=PARTIAL", proc.stderr)
            log = (base / "runtime.log").read_text(encoding="utf-8")
            self.assertIn("pm2 resurrect", log)
            self.assertIn("pm2 delete all", log)
            self.assertIn("pm2 kill", log)
            self.assertFalse((target / "home/alice/.pm2").exists())

    def test_wrong_confirmation_blocks_all_runtime_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, target, _ = self.prepare_restored_target(base)
            crontab = self.make_fake_crontab(base)
            runuser = self.make_fake_runuser(base)
            chown = self.make_fake_chown(base)
            env = self.env(base, target)
            proc = self.run_runtime(package, target, crontab, runuser, chown, env, "WRONG")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("explicit confirmation required", proc.stderr)
            self.assertFalse((target / "var/spool/cron/crontabs/alice").exists())
            self.assertFalse((target / "home/alice/.pm2/dump.pm2").exists())

    def test_server_cutover_can_activate_user_runtime_while_deferring_system_cron(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source-root"
            output = base / "backups"
            helper = BackupTest()
            _, fake_export = helper.make_cloudpanel_fixture(source)
            cron_d = source / "etc/cron.d"
            cron_d.mkdir(parents=True, exist_ok=True)
            (cron_d / "shared").write_text("* * * * * alice /home/alice/shared-job\n", encoding="utf-8")
            backup = helper.run_backup(source, fake_export, output)
            self.assertEqual(backup.returncode, 0, backup.stderr)
            package = Path(backup.stdout.strip())

            target = NewSiteRestoreTest().make_target(base)
            (target / "home/alice/htdocs/example.com").mkdir(parents=True)
            crontab = self.make_fake_crontab(base)
            runuser = self.make_fake_runuser(base)
            chown = self.make_fake_chown(base)
            env = self.env(base, target)
            proc = self.run_runtime(
                package, target, crontab, runuser, chown, env,
                self.confirmation(package),
                defer_system_cron=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "RUNTIME_ACTIVATED")
            self.assertTrue(result["system_cron_deferred"])
            self.assertTrue(result["manual_cron_remaining"])
            self.assertTrue(result["cron_installed"])
            self.assertFalse((target / "etc/cron.d/shared").exists())

    def test_system_cron_source_becomes_manual_gate_not_automatic_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source-root"
            output = base / "backups"
            helper = BackupTest()
            _, fake_export = helper.make_cloudpanel_fixture(source)
            cron_d = source / "etc/cron.d"
            cron_d.mkdir(parents=True, exist_ok=True)
            (cron_d / "shared").write_text("* * * * * alice /home/alice/shared-job\n", encoding="utf-8")
            backup = helper.run_backup(source, fake_export, output)
            self.assertEqual(backup.returncode, 0, backup.stderr)
            package = Path(backup.stdout.strip())

            target = NewSiteRestoreTest().make_target(base)
            (target / "home/alice/htdocs/example.com").mkdir(parents=True)
            proc = subprocess.run(
                [str(CLI), "runtime", "plan", "--package", str(package), "--target-root", str(target)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            plan = json.loads(proc.stdout)
            self.assertEqual(plan["status"], "READY_WITH_MANUAL_GATES")
            self.assertTrue(any(item["reason"] == "SYSTEM_CRON_REQUIRES_MANUAL_RECONCILIATION" for item in plan["manual_cron"]))


if __name__ == "__main__":
    unittest.main()