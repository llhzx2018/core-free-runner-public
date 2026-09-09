#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

import backup_frontend


class BackupFrontendTest(unittest.TestCase):
    def test_wordpress_credentials_are_discovered_by_exact_database_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wp-config.php").write_text(
                "define('DB_NAME', 'prod_db');\n"
                "define('DB_USER', 'prod_user');\n"
                "define('DB_PASSWORD', 'PRIVATE-WP-PASSWORD');\n",
                encoding="utf-8",
            )
            found = backup_frontend.discover_credentials(root, ["prod_db"])
            self.assertEqual(found["prod_db"]["user_name"], "prod_user")
            self.assertEqual(found["prod_db"]["password"], "PRIVATE-WP-PASSWORD")

    def test_dotenv_database_url_and_ghost_json_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("DATABASE_URL=mysql://env_user:p%40ss@127.0.0.1/env_db\n", encoding="utf-8")
            (root / "config.production.json").write_text(
                json.dumps({"database": {"connection": {"database": "ghost_db", "user": "ghost_user", "password": "ghost-secret"}}}),
                encoding="utf-8",
            )
            found = backup_frontend.discover_credentials(root, ["env_db", "ghost_db"])
            self.assertEqual(found["env_db"], {"user_name": "env_user", "password": "p@ss"})
            self.assertEqual(found["ghost_db"]["user_name"], "ghost_user")

    def test_conflicting_credentials_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("DB_DATABASE=prod\nDB_USERNAME=one\nDB_PASSWORD=first\n", encoding="utf-8")
            (root / "wp-config.php").write_text(
                "define('DB_NAME','prod');define('DB_USER','two');define('DB_PASSWORD','second');",
                encoding="utf-8",
            )
            with self.assertRaises(backup_frontend.DiscoveryError):
                backup_frontend.discover_credentials(root, ["prod"])

    def test_current_panel_schema_preloads_0600_recovery_then_deletes_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            site = base / "site"
            site.mkdir()
            (site / "wp-config.php").write_text(
                "define('DB_NAME','prod');define('DB_USER','app');define('DB_PASSWORD','PRIVATE-TEMP-SECRET');",
                encoding="utf-8",
            )
            run = base / "run"
            run.mkdir()
            old_tmp = os.environ.get("VFOPS_RECOVERY_TMPDIR")
            os.environ["VFOPS_RECOVERY_TMPDIR"] = str(run)
            seen: list[Path] = []

            def fake_build(root, domain, output, clpctl, kind, recovery=None):
                self.assertIsNotNone(recovery)
                recovery = Path(recovery)
                seen.append(recovery)
                self.assertEqual(stat.S_IMODE(recovery.stat().st_mode), 0o600)
                payload = json.loads(recovery.read_text(encoding="utf-8"))
                self.assertEqual(payload["databases"][0]["password"], "PRIVATE-TEMP-SECRET")
                return base / "backup-ok"

            try:
                with mock.patch.object(backup_frontend, "_site_from_inventory", return_value=(site, ["prod"])), \
                     mock.patch.object(backup_frontend, "_panel_schema_needs_recovery", return_value=True), \
                     mock.patch.object(backup_frontend.package_engine, "build_backup", side_effect=fake_build):
                    result = backup_frontend.build_backup_with_discovery(base, "example.test", base / "out", "clpctl", "automatic")
                self.assertEqual(result, base / "backup-ok")
                self.assertTrue(seen)
                self.assertFalse(seen[0].exists())
                self.assertEqual(list(run.iterdir()), [])
            finally:
                if old_tmp is None:
                    os.environ.pop("VFOPS_RECOVERY_TMPDIR", None)
                else:
                    os.environ["VFOPS_RECOVERY_TMPDIR"] = old_tmp

    def test_missing_app_credentials_never_weakens_canonical_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            site = base / "site"
            site.mkdir()
            with mock.patch.object(backup_frontend, "_site_from_inventory", return_value=(site, ["prod"])), \
                 mock.patch.object(backup_frontend, "_panel_schema_needs_recovery", return_value=True), \
                 mock.patch.object(
                     backup_frontend.package_engine,
                     "build_backup",
                     side_effect=RuntimeError("portable database recovery credentials unavailable: prod; provide --db-recovery-file"),
                 ):
                with self.assertRaisesRegex(RuntimeError, "could not be discovered safely"):
                    backup_frontend.build_backup_with_discovery(base, "example.test", base / "out", "clpctl")


if __name__ == "__main__":
    unittest.main()
