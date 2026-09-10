#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "vfops"


class BackupTest(unittest.TestCase):
    def make_cloudpanel_fixture(self, base: Path) -> tuple[Path, Path]:
        (base / "etc/nginx/sites-enabled").mkdir(parents=True)
        (base / "etc/nginx/ssl-certificates").mkdir(parents=True)
        (base / "etc").mkdir(exist_ok=True)
        (base / "etc/os-release").write_text('ID=debian\nVERSION_ID="12"\nPRETTY_NAME="Debian GNU/Linux 12"\n', encoding="utf-8")
        (base / "etc/hostname").write_text("fixture-host\n", encoding="utf-8")
        (base / "home/clp/htdocs/app/data").mkdir(parents=True)
        (base / "home/clp/htdocs/app/VERSION").write_text("2.5.0\n", encoding="utf-8")
        panel_db = base / "home/clp/htdocs/app/data/db.sq3"
        conn = sqlite3.connect(panel_db)
        conn.executescript("""
            CREATE TABLE site (id INTEGER PRIMARY KEY, domain_name TEXT, user TEXT, type TEXT, vhost_template TEXT);
            CREATE TABLE php_settings (site_id INTEGER, php_version TEXT);
            CREATE TABLE database (site_id INTEGER, name TEXT, user_name TEXT, password TEXT);
            INSERT INTO site VALUES (1, 'example.com', 'alice', 'php', 'Generic');
            INSERT INTO php_settings VALUES (1, '8.4');
            INSERT INTO database VALUES (1, 'example_prod', 'example_user', 'PRIVATE-RECOVERY-DB-SECRET');
        """)
        conn.commit(); conn.close()
        cert = base / "etc/nginx/ssl-certificates/example.com.crt"
        key = base / "etc/nginx/ssl-certificates/example.com.key"
        cert.write_text("-----BEGIN CERTIFICATE-----\nSYNTHETIC-CERT\n-----END CERTIFICATE-----\n", encoding="utf-8")
        key.write_text("-----BEGIN PRIVATE KEY-----\nSYNTHETIC-PRIVATE-KEY\n-----END PRIVATE KEY-----\n", encoding="utf-8"); key.chmod(0o600)
        vhost = base / "etc/nginx/sites-enabled/example.com.conf"
        vhost.write_text("""
            server {
              listen 443 ssl;
              server_name example.com www.example.com;
              root /home/alice/htdocs/example.com/public;
              fastcgi_pass unix:/run/php/php8.4-fpm.sock;
              ssl_certificate /etc/nginx/ssl-certificates/example.com.crt;
              ssl_certificate_key /etc/nginx/ssl-certificates/example.com.key;
            }
        """, encoding="utf-8")
        site_root = base / "home/alice/htdocs/example.com"
        (site_root / "public").mkdir(parents=True)
        (site_root / "public/index.php").write_text("<?php echo 'ok';\n", encoding="utf-8")
        (site_root / ".env").write_text("APP_SECRET=LOCAL-BACKUP-SECRET\n", encoding="utf-8")
        data_dir = site_root / "data"; data_dir.mkdir()
        app_db = data_dir / "app.sqlite"; app = sqlite3.connect(app_db)
        app.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"); app.execute("INSERT INTO items(name) VALUES ('fixture')"); app.commit(); app.close()
        (data_dir / "not-sqlite.db").write_text("plain text", encoding="utf-8")
        cron_dir = base / "var/spool/cron/crontabs"; cron_dir.mkdir(parents=True)
        (cron_dir / "alice").write_text("*/5 * * * * /home/alice/bin/task --token PRIVATE\n", encoding="utf-8")
        pm2_dir = base / "home/alice/.pm2"; pm2_dir.mkdir(parents=True)
        (pm2_dir / "dump.pm2").write_text(json.dumps([{"name": "api", "env": {"TOKEN": "PRIVATE"}}]), encoding="utf-8")
        fake_clpctl = base / "fake-clpctl"
        fake_clpctl.write_text("""#!/usr/bin/env python3
import gzip
import pathlib
import sys
args = dict(item[2:].split('=', 1) for item in sys.argv[2:] if item.startswith('--') and '=' in item)
out = pathlib.Path(args['file'])
out.parent.mkdir(parents=True, exist_ok=True)
with gzip.open(out, 'wb') as handle:
    handle.write(b'-- vf fixture dump\\nCREATE TABLE demo(id INT);\\n')
""", encoding="utf-8")
        fake_clpctl.chmod(0o700)
        return site_root, fake_clpctl

    def make_real_cloudpanel_database_schema(self, base: Path) -> None:
        panel_db = base / "home/clp/htdocs/app/data/db.sq3"; conn = sqlite3.connect(panel_db)
        conn.executescript("""
            DROP TABLE database;
            CREATE TABLE database (id INTEGER PRIMARY KEY, site_id INTEGER, database_server_id INTEGER, created_at TEXT, updated_at TEXT, name TEXT);
            INSERT INTO database VALUES (1, 1, 1, '2026-09-06', '2026-09-06', 'example_prod');
        """); conn.commit(); conn.close()

    def make_db_recovery_file(self, path: Path, mode: int = 0o600) -> Path:
        path.write_text(json.dumps({"schema":"vf-server-ops.database-recovery-input.v1","domain":"example.com","databases":[{"name":"example_prod","user_name":"real_example_user","password":"PRIVATE-EXPLICIT-DB-RECOVERY-SECRET"}]}), encoding="utf-8")
        path.chmod(mode); return path

    def run_backup(self, base: Path, fake_clpctl: Path, output: Path, recovery_file: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy(); env["VFOPS_NOW"] = "2026-09-05T12:00:00+00:00"
        command = [str(CLI),"backup","--site","example.com","--root",str(base),"--output-dir",str(output),"--clpctl",str(fake_clpctl)]
        if recovery_file is not None: command.extend(["--db-recovery-file", str(recovery_file)])
        return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, env=env)

    def test_local_backup_is_atomic_private_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "rootfs"; output = Path(tmp) / "backups"; _, fake_clpctl = self.make_cloudpanel_fixture(base)
            proc = self.run_backup(base, fake_clpctl, output); self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("PRIVATE-RECOVERY-DB-SECRET", proc.stdout + proc.stderr); self.assertNotIn("SYNTHETIC-PRIVATE-KEY", proc.stdout + proc.stderr)
            package = Path(proc.stdout.strip()); self.assertTrue(package.is_dir()); self.assertEqual(stat.S_IMODE(package.stat().st_mode), 0o700)
            self.assertFalse(any(path.name.startswith(".") and ".tmp-" in path.name for path in output.iterdir()))
            manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8")); verify = json.loads((package / "verification.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema"], "vf-server-ops.backup-package.v1"); self.assertEqual(manifest["site"]["site_root"], "/home/alice/htdocs/example.com")
            self.assertTrue(manifest["security"]["contains_sensitive_data"]); self.assertTrue(manifest["security"]["contains_recovery_secrets"]); self.assertTrue(manifest["security"]["remote_storage_requires_encryption"]); self.assertTrue(manifest["security"]["ssl_private_key_included"]); self.assertTrue(manifest["security"]["cloudpanel_private_metadata_included"]); self.assertEqual(verify["status"], "PASS")
            self.assertNotIn("PRIVATE-RECOVERY-DB-SECRET", json.dumps(manifest))
            with tarfile.open(package / "files/site.tar.gz", "r:gz") as archive:
                names = archive.getnames(); self.assertIn("site/.env", names); self.assertIn("site/public/index.php", names)
            mysql_dump = package / "mysql/example_prod.sql.gz"
            with gzip.open(mysql_dump, "rb") as handle: self.assertIn(b"CREATE TABLE", handle.read())
            sqlite_files = list((package / "sqlite").glob("*")); self.assertEqual(len(sqlite_files), 1); self.assertIn("app.sqlite", sqlite_files[0].name)
            conn = sqlite3.connect(sqlite_files[0]); self.assertEqual(conn.execute("SELECT name FROM items").fetchone()[0], "fixture"); conn.close()
            self.assertTrue((package / "metadata/cron").is_dir()); self.assertTrue((package / "metadata/pm2/dump.pm2").is_file()); self.assertTrue((package / "metadata/vhost/example.com.conf").is_file())
            ssl_files = list((package / "metadata/ssl").iterdir()); self.assertEqual(len(ssl_files), 2); self.assertTrue(any("private_key" in item.name for item in ssl_files)); self.assertTrue(any("certificate" in item.name for item in ssl_files)); self.assertTrue(all(stat.S_IMODE(item.stat().st_mode) == 0o600 for item in ssl_files))
            private_meta = package / "metadata/cloudpanel-private.json"; self.assertEqual(stat.S_IMODE(private_meta.stat().st_mode), 0o600)
            private_payload = json.loads(private_meta.read_text(encoding="utf-8")); self.assertEqual(private_payload["schema"], "vf-server-ops.cloudpanel-private-metadata.v1"); self.assertEqual(private_payload["tables"]["database"][0]["user_name"], "example_user"); self.assertEqual(private_payload["tables"]["database"][0]["password"], "PRIVATE-RECOVERY-DB-SECRET")
            self.assertEqual(stat.S_IMODE((package / "manifest.json").stat().st_mode), 0o600); self.assertEqual(stat.S_IMODE((package / "checksums.sha256").stat().st_mode), 0o600)
            second = self.run_backup(base, fake_clpctl, output); self.assertNotEqual(second.returncode, 0); self.assertIn("backup already exists", second.stderr)

    def test_real_cloudpanel_schema_requires_private_recovery_input_and_merges_it_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "rootfs"; output = Path(tmp) / "backups"; _, fake_clpctl = self.make_cloudpanel_fixture(base); self.make_real_cloudpanel_database_schema(base)
            blocked = self.run_backup(base, fake_clpctl, output); self.assertNotEqual(blocked.returncode, 0); self.assertIn("portable database recovery credentials unavailable: example_prod", blocked.stderr); self.assertNotIn("PRIVATE-EXPLICIT-DB-RECOVERY-SECRET", blocked.stdout + blocked.stderr)
            if output.exists(): self.assertFalse(any(path.is_dir() and not path.name.startswith(".") for path in output.iterdir()))
            recovery = self.make_db_recovery_file(Path(tmp) / "db-recovery.json"); proc = self.run_backup(base, fake_clpctl, output, recovery); self.assertEqual(proc.returncode, 0, proc.stderr); self.assertNotIn("PRIVATE-EXPLICIT-DB-RECOVERY-SECRET", proc.stdout + proc.stderr)
            package = Path(proc.stdout.strip()); manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8")); self.assertNotIn("PRIVATE-EXPLICIT-DB-RECOVERY-SECRET", json.dumps(manifest))
            summary = manifest["contents"]["metadata"]["cloudpanel_private_metadata"]; self.assertEqual(summary["database_recovery_input_count"], 1); self.assertEqual(summary["status"], "CAPTURED_READ_ONLY_WITH_PRIVATE_RECOVERY_INPUT")
            private_payload = json.loads((package / "metadata/cloudpanel-private.json").read_text(encoding="utf-8")); row = private_payload["tables"]["database"][0]; self.assertEqual(row["user_name"], "real_example_user"); self.assertEqual(row["password"], "PRIVATE-EXPLICIT-DB-RECOVERY-SECRET")

    def test_database_recovery_input_rejects_group_world_readable_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "rootfs"; output = Path(tmp) / "backups"; _, fake_clpctl = self.make_cloudpanel_fixture(base); self.make_real_cloudpanel_database_schema(base); recovery = self.make_db_recovery_file(Path(tmp) / "db-recovery.json", mode=0o644)
            proc = self.run_backup(base, fake_clpctl, output, recovery); self.assertNotEqual(proc.returncode, 0); self.assertIn("permissions must not allow group/world access", proc.stderr); self.assertNotIn("PRIVATE-EXPLICIT-DB-RECOVERY-SECRET", proc.stdout + proc.stderr)

    def test_unknown_mysql_blocks_incomplete_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "rootfs"; output = Path(tmp) / "backups"; _, fake_clpctl = self.make_cloudpanel_fixture(base); (base / "home/clp/htdocs/app/data/db.sq3").unlink()
            proc = self.run_backup(base, fake_clpctl, output); self.assertNotEqual(proc.returncode, 0); self.assertIn("MySQL association is UNKNOWN", proc.stderr)
            if output.exists(): self.assertFalse(any(path.is_dir() and not path.name.startswith(".") for path in output.iterdir()))


if __name__ == "__main__":
    unittest.main()
