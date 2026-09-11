from __future__ import annotations

import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import restore_as
import site_lifecycle


class RestoreAsTests(unittest.TestCase):
    def make_package(self, base: Path, *, databases: int = 1) -> Path:
        package = base / "backup"
        (package / "files").mkdir(parents=True)
        (package / "mysql").mkdir()
        (package / "metadata").mkdir()
        (package / "files/site.tar.gz").write_bytes(b"placeholder")
        mysql = []
        for index in range(databases):
            name = f"source_db_{index + 1}"
            dump = package / "mysql" / f"{name}.sql.gz"
            with gzip.open(dump, "wt", encoding="utf-8") as handle:
                handle.write("CREATE TABLE demo(id INT);\nINSERT INTO demo VALUES (1);\n")
            mysql.append({"database": name, "file": f"mysql/{name}.sql.gz"})
        manifest = {
            "schema": "vf-server-ops.backup-package.v1",
            "backup_id": "example.com_20260910T000000Z",
            "site": {
                "domain": "example.com",
                "domains": ["example.com", "www.example.com"],
                "site_user": "alice",
                "site_root": "/home/alice/htdocs/example.com",
                "document_root": "/home/alice/htdocs/example.com/public",
                "runtime": {"type": "php", "version": "8.4", "app_port": "UNKNOWN"},
            },
            "contents": {
                "files_archive": "files/site.tar.gz",
                "mysql": mysql,
                "sqlite": [],
                "metadata": {},
            },
        }
        (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return package

    def make_target(self, base: Path) -> Path:
        target = base / "target"
        target.mkdir()
        (target / restore_as.CONTROLLED_MARKER).write_text(
            restore_as.CONTROLLED_MARKER_VALUE + "\n", encoding="utf-8"
        )
        return target

    def confirmation(self, package: Path, target_domain: str) -> str:
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        return restore_as.expected_confirm(manifest, target_domain)

    def common_patches(self, target: Path, package: Path, *, wp: bool = True):
        identity = site_lifecycle.TargetSiteIdentity(
            domain="restore.example.com",
            site_user="p07restore",
            site_password="generated-site-password",
            site_root="/home/p07restore/htdocs/restore.example.com",
        )

        def create_site(_source, ident, **_kwargs):
            root = target / ident.site_root.lstrip("/")
            root.mkdir(parents=True)
            (root / "index.html").write_text("cloudpanel bootstrap\n", encoding="utf-8")

        def extract(_archive, staged):
            public = staged / "public"
            public.mkdir(parents=True)
            (public / "index.php").write_text("<?php echo 'ok';\n", encoding="utf-8")
            if wp:
                (staged / "wp-config.php").write_text(
                    "<?php\n"
                    "define('DB_NAME', 'source_db_1');\n"
                    "define('DB_USER', 'source_user');\n"
                    "define('DB_PASSWORD', 'source-secret');\n",
                    encoding="utf-8",
                )
            else:
                (staged / ".env").write_text(
                    "DB_DATABASE=source_db_1\nDB_USERNAME=source_user\nDB_PASSWORD=source-secret\n"
                    "APP_URL=https://example.com\n",
                    encoding="utf-8",
                )

        return identity, [
            mock.patch.object(restore_as.package_engine, "verify_package", return_value={"status": "PASS"}),
            mock.patch.object(restore_as.site_lifecycle, "ensure_domain_available"),
            mock.patch.object(restore_as.site_lifecycle, "derive_target_identity", return_value=identity),
            mock.patch.object(restore_as, "source_vhost_template", return_value="Generic"),
            mock.patch.object(restore_as.site_lifecycle, "create_site", side_effect=create_site),
            mock.patch.object(restore_as.restore_plan, "inspect_archive", return_value={"blockers": []}),
            mock.patch.object(restore_as.restore_apply, "extract_site_archive", side_effect=extract),
            mock.patch.object(restore_as.verify_engine, "verify_files", return_value={"status": "PASS"}),
            mock.patch.object(restore_as.verify_engine, "verify_sqlite", return_value={"status": "PASS"}),
            mock.patch.object(restore_as.cloudpanel, "add_database"),
            mock.patch.object(restore_as.cloudpanel, "import_database"),
            mock.patch.object(restore_as, "verify_imported_database"),
            mock.patch.object(restore_as.restore_new, "reconcile_site_ownership"),
            mock.patch.object(
                restore_as,
                "reconcile_wordpress_domain",
                return_value={"home": "https://restore.example.com", "siteurl": "https://restore.example.com"},
            ),
            mock.patch.object(restore_as.cloudpanel, "reset_permissions"),
        ]

    def _run_with_patches(self, patches, callback):
        entered = []
        try:
            for patcher in patches:
                entered.append(patcher.start())
            return callback(entered)
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def test_same_vps_restore_as_new_domain_creates_new_site_and_database_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = self.make_package(base)
            target = self.make_target(base)
            source = target / "home/alice/htdocs/example.com"
            source.mkdir(parents=True)
            sentinel = source / "SOURCE_SENTINEL"
            sentinel.write_text("preserve\n", encoding="utf-8")
            identity, patches = self.common_patches(target, package)

            result = self._run_with_patches(
                patches,
                lambda entered: restore_as.restore_as(
                    package,
                    "restore.example.com",
                    target,
                    "clpctl",
                    self.confirmation(package, "restore.example.com"),
                ),
            )

            self.assertEqual(result["status"], "RESTORE_AS_VERIFIED")
            self.assertEqual(result["source_domain"], "example.com")
            self.assertEqual(result["target_domain"], "restore.example.com")
            self.assertEqual(result["target_site_user"], identity.site_user)
            self.assertNotEqual(result["target_site_user"], "alice")
            self.assertNotEqual(result["target_database"], "source_db_1")
            self.assertNotEqual(result["target_database_user"], "source_user")
            self.assertFalse(result["source_ssl_reused"])
            self.assertIn("NOT_REUSED", result["ssl_status"])
            self.assertFalse(result["dns_changed"])
            self.assertFalse(result["source_deleted"])
            self.assertFalse(result["existing_site_overwrite_allowed"])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
            restored = target / identity.site_root.lstrip("/")
            self.assertTrue((restored / "public/index.php").is_file())
            config = (restored / "wp-config.php").read_text(encoding="utf-8")
            self.assertIn(result["target_database"], config)
            self.assertIn(result["target_database_user"], config)
            self.assertNotIn("source-secret", config)

    def test_dotenv_application_config_is_remapped_without_source_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = self.make_package(base)
            target = self.make_target(base)
            identity, patches = self.common_patches(target, package, wp=False)
            result = self._run_with_patches(
                patches,
                lambda _entered: restore_as.restore_as(
                    package,
                    "restore.example.com",
                    target,
                    "clpctl",
                    self.confirmation(package, "restore.example.com"),
                ),
            )
            self.assertEqual(result["application_config_mode"], "DOTENV")
            env = (target / identity.site_root.lstrip("/") / ".env").read_text(encoding="utf-8")
            self.assertIn(result["target_database"], env)
            self.assertIn(result["target_database_user"], env)
            self.assertIn("https://restore.example.com", env)
            self.assertNotIn("source-secret", env)

    def test_existing_target_domain_blocks_before_cloudpanel_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = self.make_package(base)
            target = self.make_target(base)
            with mock.patch.object(restore_as.package_engine, "verify_package", return_value={"status": "PASS"}), mock.patch.object(
                restore_as.site_lifecycle,
                "ensure_domain_available",
                side_effect=site_lifecycle.SiteLifecycleError("target domain already exists in CloudPanel"),
            ), mock.patch.object(restore_as.site_lifecycle, "create_site") as create:
                with self.assertRaises(restore_as.RestoreAsError):
                    restore_as.restore_as(
                        package,
                        "restore.example.com",
                        target,
                        "clpctl",
                        self.confirmation(package, "restore.example.com"),
                    )
            create.assert_not_called()

    def test_invalid_target_domain_fails_before_cloudpanel_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = self.make_package(base)
            target = self.make_target(base)
            with mock.patch.object(restore_as.site_lifecycle, "create_site") as create:
                with self.assertRaises(ValueError):
                    restore_as.restore_as(package, "../bad", target, "clpctl", "WRONG")
            create.assert_not_called()

    def test_multi_database_backup_fails_before_site_creation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = self.make_package(base, databases=2)
            target = self.make_target(base)
            with mock.patch.object(restore_as.package_engine, "verify_package", return_value={"status": "PASS"}), mock.patch.object(
                restore_as.site_lifecycle, "ensure_domain_available"
            ), mock.patch.object(restore_as.site_lifecycle, "create_site") as create, mock.patch.object(
                restore_as.restore_plan, "inspect_archive", return_value={"blockers": []}
            ):
                with self.assertRaisesRegex(restore_as.RestoreAsError, "multi-database"):
                    restore_as.restore_as(
                        package,
                        "restore.example.com",
                        target,
                        "clpctl",
                        self.confirmation(package, "restore.example.com"),
                    )
            create.assert_not_called()

    def test_database_import_is_reexported_and_fingerprint_verified(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = self.make_package(base)
            source = package / "mysql/source_db_1.sql.gz"

            def export(_database, output, **_kwargs):
                shutil.copy2(source, output)
                return Path(output)

            with mock.patch.object(restore_as.cloudpanel, "export_database", side_effect=export):
                restore_as.verify_imported_database(package, "source_db_1", "target_db", "clpctl")

    def test_database_fingerprint_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = self.make_package(base)

            def export(_database, output, **_kwargs):
                with gzip.open(output, "wt", encoding="utf-8") as handle:
                    handle.write("CREATE TABLE changed(id INT);\n")
                return Path(output)

            with mock.patch.object(restore_as.cloudpanel, "export_database", side_effect=export):
                with self.assertRaisesRegex(restore_as.RestoreAsError, "fingerprint"):
                    restore_as.verify_imported_database(package, "source_db_1", "target_db", "clpctl")

    def test_wordpress_config_rewrite_is_exact_and_secret_safe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "wp-config.php"
            path.write_text(
                "<?php\ndefine('DB_NAME','old');\ndefine(\"DB_USER\", \"oldu\");\ndefine('DB_PASSWORD','oldp');\n",
                encoding="utf-8",
            )
            restore_as.rewrite_wordpress_config(path, "newdb", "newuser", "new-secret")
            text = path.read_text(encoding="utf-8")
            self.assertIn("define('DB_NAME', 'newdb');", text)
            self.assertIn("define('DB_USER', 'newuser');", text)
            self.assertIn("define('DB_PASSWORD', 'new-secret');", text)

    def test_wordpress_domain_reconcile_uses_serialization_safe_search_replace(self) -> None:
        responses = [
            "https://example.com",
            "https://example.com",
            "",
            "https://restore.example.com",
            "https://restore.example.com",
        ]
        calls = []

        def fake_run(_user, _root, args, **_kwargs):
            calls.append(args)
            return responses.pop(0)

        with mock.patch.object(restore_as, "_run_wp", side_effect=fake_run):
            result = restore_as.reconcile_wordpress_domain(
                "p07restore", Path("/tmp/site"), "example.com", "restore.example.com"
            )
        self.assertEqual(result["home"], "https://restore.example.com")
        search = next(call for call in calls if call and call[0] == "search-replace")
        self.assertIn("--all-tables-with-prefix", search)
        self.assertIn("--skip-columns=guid", search)
        self.assertIn("--precise", search)

    def test_failure_after_commit_rolls_back_created_target_and_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = self.make_package(base)
            target = self.make_target(base)
            source = target / "home/alice/htdocs/example.com"
            source.mkdir(parents=True)
            sentinel = source / "SOURCE_SENTINEL"
            sentinel.write_text("preserve\n", encoding="utf-8")
            identity, patches = self.common_patches(target, package)
            cleanup_db = mock.patch.object(restore_as.site_lifecycle, "cleanup_database", return_value=True)

            def cleanup_site(domain, **_kwargs):
                restored = target / identity.site_root.lstrip("/")
                if restored.exists():
                    shutil.rmtree(restored)
                return True

            cleanup_site_patch = mock.patch.object(restore_as.site_lifecycle, "cleanup_site", side_effect=cleanup_site)
            patches[-2] = mock.patch.object(
                restore_as,
                "reconcile_wordpress_domain",
                side_effect=restore_as.RestoreAsError("synthetic WP failure"),
            )
            patches.extend([cleanup_db, cleanup_site_patch])
            with self.assertRaisesRegex(restore_as.RestoreAsError, "WORDPRESS_DOMAIN_REMAP"):
                self._run_with_patches(
                    patches,
                    lambda _entered: restore_as.restore_as(
                        package,
                        "restore.example.com",
                        target,
                        "clpctl",
                        self.confirmation(package, "restore.example.com"),
                    ),
                )
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
            self.assertFalse((target / identity.site_root.lstrip("/")).exists())


if __name__ == "__main__":
    unittest.main()
