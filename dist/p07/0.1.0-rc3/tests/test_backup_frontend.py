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
import diagnostics


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

    def test_temp_recovery_is_deleted_when_database_export_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            site = base / "site"
            site.mkdir()
            (site / ".env").write_text("DB_DATABASE=prod\nDB_USERNAME=app\nDB_PASSWORD=PRIVATE-FAIL-SECRET\n", encoding="utf-8")
            run = base / "run"
            run.mkdir()
            old_tmp = os.environ.get("VFOPS_RECOVERY_TMPDIR")
            os.environ["VFOPS_RECOVERY_TMPDIR"] = str(run)

            def fail_export(root, domain, output, clpctl, kind, recovery=None):
                self.assertIsNotNone(recovery)
                self.assertTrue(Path(recovery).is_file())
                raise RuntimeError("CloudPanel database export failed: prod (exit 1)")

            try:
                with mock.patch.object(backup_frontend, "_site_from_inventory", return_value=(site, ["prod"])), \
                     mock.patch.object(backup_frontend, "_panel_schema_needs_recovery", return_value=True), \
                     mock.patch.object(backup_frontend.package_engine, "build_backup", side_effect=fail_export) as build:
                    with self.assertRaisesRegex(RuntimeError, "database export failed"):
                        backup_frontend.build_backup_with_discovery(base, "example.test", base / "out", "clpctl")
                self.assertEqual(build.call_count, 1)
                self.assertEqual(list(run.iterdir()), [])
            finally:
                if old_tmp is None:
                    os.environ.pop("VFOPS_RECOVERY_TMPDIR", None)
                else:
                    os.environ["VFOPS_RECOVERY_TMPDIR"] = old_tmp

    def test_missing_app_credentials_fail_before_repeating_expensive_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            site = base / "site"
            site.mkdir()
            with mock.patch.object(backup_frontend, "_site_from_inventory", return_value=(site, ["prod"])), \
                 mock.patch.object(backup_frontend, "_panel_schema_needs_recovery", return_value=True), \
                 mock.patch.object(backup_frontend.package_engine, "build_backup") as build:
                with self.assertRaisesRegex(RuntimeError, "could not be discovered safely"):
                    backup_frontend.build_backup_with_discovery(base, "example.test", base / "out", "clpctl")
                build.assert_not_called()

    def test_database_export_failures_are_not_retried_as_recovery_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            site = base / "site"
            site.mkdir()
            with mock.patch.object(backup_frontend, "_site_from_inventory", return_value=(site, ["prod"])), \
                 mock.patch.object(backup_frontend, "_panel_schema_needs_recovery", return_value=False), \
                 mock.patch.object(
                     backup_frontend.package_engine,
                     "build_backup",
                     side_effect=RuntimeError("CloudPanel database export failed: prod (exit 1)"),
                 ) as build:
                with self.assertRaisesRegex(RuntimeError, "database export failed"):
                    backup_frontend.build_backup_with_discovery(base, "example.test", base / "out", "clpctl")
                self.assertEqual(build.call_count, 1)
            rendered = diagnostics.render("backup", 4, "ERROR: CloudPanel database export failed: prod (exit 1)")
            self.assertIn("stage=DATABASE", rendered)
            self.assertIn("blocker=DB_EXPORT_FAILED", rendered)

            invalid = diagnostics.render("backup", 4, "ERROR: MySQL gzip validation failed: prod")
            self.assertIn("blocker=DB_EXPORT_INVALID", invalid)

    def test_inventory_site_user_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            payload = {
                "sites": [{
                    "domain": "example.test",
                    "domains": ["example.test"],
                    "site_user": "../../outside",
                    "document_root": "/home/alice/htdocs/example.test/public",
                    "mysql_databases": ["prod"],
                }]
            }
            with mock.patch.object(backup_frontend.inventory, "build_manifest", return_value=payload):
                with self.assertRaises(backup_frontend.DiscoveryError):
                    backup_frontend._site_from_inventory(root, "example.test")

    def test_external_document_root_and_symlink_site_root_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external_payload = {
                "sites": [{
                    "domain": "example.test",
                    "domains": ["example.test"],
                    "site_user": "UNKNOWN",
                    "document_root": "/etc",
                    "mysql_databases": ["prod"],
                }]
            }
            with mock.patch.object(backup_frontend.inventory, "build_manifest", return_value=external_payload):
                with self.assertRaises(backup_frontend.DiscoveryError):
                    backup_frontend._site_from_inventory(root, "example.test")

            htdocs = root / "home/alice/htdocs"
            htdocs.mkdir(parents=True)
            outside = base / "outside"
            outside.mkdir()
            (htdocs / "example.test").symlink_to(outside, target_is_directory=True)
            symlink_payload = {
                "sites": [{
                    "domain": "example.test",
                    "domains": ["example.test"],
                    "site_user": "alice",
                    "document_root": "/home/alice/htdocs/example.test/public",
                    "mysql_databases": ["prod"],
                }]
            }
            with mock.patch.object(backup_frontend.inventory, "build_manifest", return_value=symlink_payload):
                with self.assertRaises(backup_frontend.DiscoveryError):
                    backup_frontend._site_from_inventory(root, "example.test")

    def test_document_root_fallback_normalizes_to_cloudpanel_site_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            site_root = root / "home/alice/htdocs/example.test"
            (site_root / "public").mkdir(parents=True)
            (site_root / ".env").write_text("DB_DATABASE=prod\nDB_USERNAME=app\nDB_PASSWORD=secret\n", encoding="utf-8")
            payload = {
                "sites": [{
                    "domain": "example.test",
                    "domains": ["example.test", "www.example.test"],
                    "site_user": "UNKNOWN",
                    "document_root": "/home/alice/htdocs/example.test/public",
                    "mysql_databases": ["prod"],
                }]
            }
            with mock.patch.object(backup_frontend.inventory, "build_manifest", return_value=payload):
                resolved, databases = backup_frontend._site_from_inventory(root, "www.example.test")
            self.assertEqual(resolved, site_root)
            self.assertEqual(databases, ["prod"])
            self.assertEqual(backup_frontend.discover_credentials(resolved, databases)["prod"]["user_name"], "app")

    def test_alias_backup_uses_canonical_domain_in_recovery_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            site_root = root / "home/alice/htdocs/example.test"
            site_root.mkdir(parents=True)
            (site_root / "wp-config.php").write_text(
                "define('DB_NAME','prod');define('DB_USER','app');define('DB_PASSWORD','PRIVATE-ALIAS-SECRET');",
                encoding="utf-8",
            )
            payload = {
                "sites": [{
                    "domain": "example.test",
                    "domains": ["example.test", "www.example.test"],
                    "site_user": "alice",
                    "document_root": "/home/alice/htdocs/example.test/public",
                    "mysql_databases": ["prod"],
                }]
            }
            captured: list[dict] = []

            def fake_build(source_root, selected_domain, output, clpctl, kind, recovery=None):
                self.assertEqual(selected_domain, "www.example.test")
                self.assertIsNotNone(recovery)
                recovery_path = Path(recovery)
                captured.append(json.loads(recovery_path.read_text(encoding="utf-8")))
                return Path(tmp) / "backup-ok"

            with mock.patch.object(backup_frontend.inventory, "build_manifest", return_value=payload), \
                 mock.patch.object(backup_frontend, "_panel_schema_needs_recovery", return_value=True), \
                 mock.patch.object(backup_frontend.package_engine, "build_backup", side_effect=fake_build):
                result = backup_frontend.build_backup_with_discovery(
                    root, "www.example.test", Path(tmp) / "out", "clpctl"
                )
            self.assertEqual(result, Path(tmp) / "backup-ok")
            self.assertEqual(captured[0]["domain"], "example.test")
            self.assertNotEqual(captured[0]["domain"], "www.example.test")


if __name__ == "__main__":
    unittest.main()
