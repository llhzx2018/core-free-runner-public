#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tempfile
import unittest

from tests.test_backup import BackupTest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "vfops"


class NewSiteMigrationTest(unittest.TestCase):
    def make_package(self, base: Path, system_cron: bool = False) -> Path:
        source = base / "source-root"
        output = base / "backups"
        helper = BackupTest()
        _, fake_export = helper.make_cloudpanel_fixture(source)

        pm2 = source / "home/alice/.pm2/dump.pm2"
        pm2.write_text(
            json.dumps([
                {
                    "name": "api",
                    "pm_exec_path": "/home/alice/htdocs/example.com/server.js",
                    "pm_cwd": "/home/alice/htdocs/example.com",
                    "env": {"TOKEN": "PRIVATE-PM2-SECRET"},
                }
            ]),
            encoding="utf-8",
        )
        if system_cron:
            cron_d = source / "etc/cron.d"
            cron_d.mkdir(parents=True, exist_ok=True)
            (cron_d / "shared").write_text("0 * * * * alice /home/alice/shared-job\n", encoding="utf-8")

        proc = helper.run_backup(source, fake_export, output)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return Path(proc.stdout.strip())

    def make_target(self, base: Path) -> Path:
        root = base / "target-root"
        root.mkdir()
        (root / ".vfops-controlled-cloudpanel-target").write_text(
            "VF_SERVER_OPS_CONTROLLED_CLOUDPANEL_TARGET_V1\n", encoding="utf-8"
        )
        (root / "etc/nginx/sites-enabled").mkdir(parents=True)
        (root / "etc/nginx/ssl-certificates").mkdir(parents=True)
        (root / "etc/os-release").write_text(
            'ID=debian\nVERSION_ID="12"\nPRETTY_NAME="Debian GNU/Linux 12"\n', encoding="utf-8"
        )
        (root / "etc/hostname").write_text("target-cloudpanel-host\n", encoding="utf-8")
        (root / "home/clp/htdocs/app/data").mkdir(parents=True)
        (root / "home/clp/htdocs/app/VERSION").write_text("2.5.0\n", encoding="utf-8")
        db = sqlite3.connect(root / "home/clp/htdocs/app/data/db.sq3")
        db.executescript(
            """
            CREATE TABLE site (id INTEGER PRIMARY KEY, domain_name TEXT, user TEXT, type TEXT, vhost_template TEXT);
            CREATE TABLE php_settings (site_id INTEGER, php_version TEXT);
            CREATE TABLE database (site_id INTEGER, name TEXT, user_name TEXT, password TEXT);
            """
        )
        db.commit()
        db.close()
        return root

    def make_fake_clpctl(self, base: Path) -> Path:
        script = base / "fake-migration-clpctl"
        script.write_text(
            r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import shutil
import sqlite3
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
    handle.write(json.dumps({"command": cmd, "domain": args.get("domainName"), "database": args.get("databaseName")}, sort_keys=True) + "\n")

panel = root / "home/clp/htdocs/app/data/db.sq3"

def connect():
    return sqlite3.connect(panel)

if cmd == "site:add:php":
    domain = args["domainName"]
    user = args["siteUser"]
    site = root / "home" / user / "htdocs" / domain
    site.mkdir(parents=True, exist_ok=False)
    (site / "index.html").write_text("cloudpanel bootstrap\n", encoding="utf-8")
    conn = connect()
    conn.execute("INSERT INTO site(id, domain_name, user, type, vhost_template) VALUES (1, ?, ?, 'php', 'Generic')", (domain, user))
    conn.execute("INSERT INTO php_settings(site_id, php_version) VALUES (1, ?)", (args["phpVersion"],))
    conn.commit()
    conn.close()
    vhost = root / "etc/nginx/sites-enabled" / f"{domain}.conf"
    vhost.write_text(
        "server {\n"
        "  listen 443 ssl;\n"
        f"  server_name {domain} www.{domain};\n"
        f"  root /home/{user}/htdocs/{domain}/public;\n"
        f"  fastcgi_pass unix:/run/php/php{args['phpVersion']}-fpm.sock;\n"
        f"  ssl_certificate /etc/nginx/ssl-certificates/{domain}.crt;\n"
        f"  ssl_certificate_key /etc/nginx/ssl-certificates/{domain}.key;\n"
        "}\n",
        encoding="utf-8",
    )
    sys.exit(0)

if cmd == "db:add":
    conn = connect()
    row = conn.execute("SELECT id FROM site WHERE domain_name=?", (args["domainName"],)).fetchone()
    if not row:
        sys.exit(7)
    conn.execute(
        "INSERT INTO database(site_id, name, user_name, password) VALUES (?, ?, ?, ?)",
        (row[0], args["databaseName"], args["databaseUserName"], args["databaseUserPassword"]),
    )
    conn.commit()
    conn.close()
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

if cmd == "site:install:certificate":
    domain = args["domainName"]
    shutil.copy2(Path(args["certificate"]), root / "etc/nginx/ssl-certificates" / f"{domain}.crt")
    shutil.copy2(Path(args["privateKey"]), root / "etc/nginx/ssl-certificates" / f"{domain}.key")
    sys.exit(0)

if cmd == "site:delete":
    domain = args.get("domainName", "")
    site = root / "home/alice/htdocs" / domain
    if site.exists():
        shutil.rmtree(site)
    conn = connect()
    row = conn.execute("SELECT id FROM site WHERE domain_name=?", (domain,)).fetchone()
    if row:
        conn.execute("DELETE FROM database WHERE site_id=?", (row[0],))
        conn.execute("DELETE FROM php_settings WHERE site_id=?", (row[0],))
        conn.execute("DELETE FROM site WHERE id=?", (row[0],))
    conn.commit()
    conn.close()
    (root / "etc/nginx/sites-enabled" / f"{domain}.conf").unlink(missing_ok=True)
    sys.exit(0)

sys.exit(0)
''',
            encoding="utf-8",
        )
        script.chmod(0o700)
        return script

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
    path.unlink(missing_ok=True)
    sys.exit(0)
if len(args) == 3:
    source = Path(args[2])
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

    def make_fake_curl(self, base: Path) -> Path:
        script = base / "fake-curl"
        script.write_text(
            "#!/usr/bin/env sh\nif [ \"${VFOPS_FAKE_CURL_FAIL:-0}\" = \"1\" ]; then printf '503'; exit 22; fi\nprintf '200'\n",
            encoding="utf-8",
        )
        script.chmod(0o700)
        return script

    def confirmation(self, package: Path) -> str:
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        return f"MIGRATE_NEW_SITE:{manifest['site']['domain']}:{manifest['backup_id']}"

    def env(self, base: Path, target: Path, curl_fail: bool = False) -> dict[str, str]:
        env = os.environ.copy()
        env["VFOPS_FAKE_TARGET_ROOT"] = str(target)
        env["VFOPS_FAKE_DB_STATE"] = str(base / "db-state")
        env["VFOPS_FAKE_CLPCTL_LOG"] = str(base / "clpctl.log")
        env["VFOPS_FAKE_RUNTIME_LOG"] = str(base / "runtime.log")
        if curl_fail:
            env["VFOPS_FAKE_CURL_FAIL"] = "1"
        return env

    def run_migration(
        self,
        package: Path,
        target: Path,
        base: Path,
        env: dict[str, str],
        confirm: str,
        *,
        defer_runtime: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        command = [
                str(CLI), "migrate", "apply-new-site",
                "--package", str(package),
                "--target-root", str(target),
                "--target-ip", "203.0.113.10",
                "--confirm", confirm,
                "--clpctl", str(self.make_fake_clpctl(base)),
                "--crontab", str(self.make_fake_crontab(base)),
                "--runuser", str(self.make_fake_runuser(base)),
                "--pm2", "pm2",
                "--chown", str(self.make_fake_chown(base)),
                "--curl", str(self.make_fake_curl(base)),
            ]
        if defer_runtime:
            command.append("--defer-runtime")
        return subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_new_site_migration_reaches_technical_cutover_ready_without_dns_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            target = self.make_target(base)
            proc = self.run_migration(package, target, base, self.env(base, target), self.confirmation(package))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("PRIVATE-RECOVERY-DB-SECRET", proc.stdout + proc.stderr)
            self.assertNotIn("PRIVATE-PM2-SECRET", proc.stdout + proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "TECHNICAL_CUTOVER_READY")
            self.assertEqual(result["restore_status"], "RESTORE_VERIFIED")
            self.assertEqual(result["runtime_status"], "RUNTIME_ACTIVATED")
            self.assertEqual(result["cross_server_status"], "PASS")
            self.assertEqual(result["http_https_status"], "PASS")
            self.assertTrue(result["technical_cutover_ready"])
            self.assertTrue(result["owner_cutover_gate_required"])
            self.assertFalse(result["dns_changed"])
            self.assertFalse(result["old_server_delete_requested"])
            self.assertFalse(result["existing_site_overwrite_allowed"])

            site = target / "home/alice/htdocs/example.com"
            self.assertTrue((site / "public/index.php").is_file())
            self.assertTrue((target / "var/spool/cron/crontabs/alice").is_file())
            self.assertTrue((target / "home/alice/.pm2/dump.pm2").is_file())

            evidence = Path(result["evidence_path"])
            self.assertTrue(evidence.is_dir())
            self.assertEqual(stat.S_IMODE(evidence.stat().st_mode), 0o700)
            for name in ("source-site.json", "target-inventory.json", "migration-result.json"):
                path = evidence / name
                self.assertTrue(path.is_file())
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_staged_migration_defers_runtime_system_cron_and_http_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base, system_cron=True)
            target = self.make_target(base)
            proc = self.run_migration(
                package,
                target,
                base,
                self.env(base, target),
                self.confirmation(package),
                defer_runtime=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "MIGRATION_STAGED")
            self.assertEqual(result["runtime_status"], "RUNTIME_DEFERRED")
            self.assertEqual(result["http_https_status"], "DEFERRED_WITH_RUNTIME")
            self.assertEqual(result["cross_server_status"], "PASS")
            self.assertTrue(result["staged_for_cutover"])
            self.assertTrue(result["runtime_deferred"])
            self.assertFalse(result["technical_cutover_ready"])
            self.assertFalse((target / "var/spool/cron/crontabs/alice").exists())
            self.assertFalse((target / "home/alice/.pm2/dump.pm2").exists())

    def test_wrong_migration_confirmation_blocks_before_target_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            target = self.make_target(base)
            proc = self.run_migration(package, target, base, self.env(base, target), "WRONG")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("explicit confirmation required", proc.stderr)
            self.assertFalse((target / "home/alice/htdocs/example.com").exists())
            self.assertFalse((base / "clpctl.log").exists())

    def test_http_probe_failure_retains_restored_target_but_never_marks_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            target = self.make_target(base)
            proc = self.run_migration(package, target, base, self.env(base, target, curl_fail=True), self.confirmation(package))
            self.assertNotEqual(proc.returncode, 0)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "NEW_SITE_MIGRATION_NOT_READY")
            self.assertIn("HTTP_HTTPS_TARGET_PROBE_NOT_PASS", result["blockers"])
            self.assertFalse(result["technical_cutover_ready"])
            self.assertFalse(result["dns_changed"])
            self.assertTrue((target / "home/alice/htdocs/example.com/public/index.php").is_file())
            self.assertTrue(Path(result["evidence_path"]).is_dir())

    def test_system_cron_becomes_manual_runtime_gate_and_blocks_cutover_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base, system_cron=True)
            target = self.make_target(base)
            proc = self.run_migration(package, target, base, self.env(base, target), self.confirmation(package))
            self.assertNotEqual(proc.returncode, 0)
            result = json.loads(proc.stdout)
            self.assertEqual(result["runtime_status"], "MANUAL_GATE_REQUIRED")
            self.assertIn("RUNTIME_MANUAL_GATE_REQUIRED", result["blockers"])
            self.assertFalse(result["technical_cutover_ready"])
            self.assertFalse((target / "var/spool/cron/crontabs/alice").exists())
            self.assertFalse((target / "home/alice/.pm2/dump.pm2").exists())


if __name__ == "__main__":
    unittest.main()
