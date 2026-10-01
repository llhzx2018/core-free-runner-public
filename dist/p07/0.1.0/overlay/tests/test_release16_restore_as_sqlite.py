from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import restore_as
import restore_apply
import site_lifecycle
import verify


class Release16RestoreAsSqliteTests(unittest.TestCase):
    def _sqlite(self, path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE demo(value TEXT)")
        conn.execute("INSERT INTO demo(value) VALUES (?)", (value,))
        conn.commit()
        conn.close()

    def _package(self, base: Path) -> Path:
        package = base / "backup"
        (package / "files").mkdir(parents=True)
        (package / "sqlite").mkdir(parents=True)

        canonical = package / "sqlite" / "01_app.sqlite"
        self._sqlite(canonical, "canonical")

        stale_dir = base / "archive-source"
        stale = stale_dir / "data" / "app.sqlite"
        self._sqlite(stale, "stale")
        (stale_dir / "data" / "app.sqlite-wal").write_bytes(b"stale-wal")
        (stale_dir / "data" / "app.sqlite-shm").write_bytes(b"stale-shm")
        (stale_dir / "public").mkdir(parents=True)
        (stale_dir / "public" / "index.php").write_text("<?php echo 'ok';\n", encoding="utf-8")

        archive = package / "files" / "site.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(stale_dir, arcname="site", recursive=True)

        manifest = {
            "schema": "vf-server-ops.backup-package.v1",
            "backup_id": "example.com_20261001T000000Z",
            "site": {
                "domain": "example.com",
                "domains": ["example.com"],
                "site_user": "alice",
                "site_root": "/home/alice/htdocs/example.com",
                "document_root": "/home/alice/htdocs/example.com/public",
                "runtime": {"type": "php", "version": "8.4", "app_port": "UNKNOWN"},
            },
            "contents": {
                "files_archive": "files/site.tar.gz",
                "mysql": [],
                "sqlite": [
                    {
                        "source": "/home/alice/htdocs/example.com/data/app.sqlite",
                        "file": "sqlite/01_app.sqlite",
                        "method": "sqlite_backup_api_delete_journal",
                    }
                ],
                "metadata": {},
            },
        }
        (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return package

    def _target(self, base: Path) -> Path:
        target = base / "target"
        target.mkdir()
        (target / restore_as.CONTROLLED_MARKER).write_text(
            restore_as.CONTROLLED_MARKER_VALUE + "\n",
            encoding="utf-8",
        )
        return target

    def test_restore_as_replaces_archived_live_sqlite_and_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = self._package(base)
            target = self._target(base)
            identity = site_lifecycle.TargetSiteIdentity(
                domain="restore.example.com",
                site_user="p07restore",
                site_password="generated-site-password",
                site_root="/home/p07restore/htdocs/restore.example.com",
            )

            def create_site(_source, ident, **_kwargs):
                final = target / ident.site_root.lstrip("/")
                final.mkdir(parents=True)
                (final / "index.html").write_text("bootstrap\n", encoding="utf-8")

            confirm = restore_as.expected_confirm(
                json.loads((package / "manifest.json").read_text(encoding="utf-8")),
                "restore.example.com",
            )

            with (
                mock.patch.object(restore_as.package_engine, "verify_package", return_value={"status": "PASS"}),
                mock.patch.object(restore_as.site_lifecycle, "ensure_domain_available"),
                mock.patch.object(restore_as.site_lifecycle, "derive_target_identity", return_value=identity),
                mock.patch.object(restore_as, "source_vhost_template", return_value="Generic"),
                mock.patch.object(restore_as.site_lifecycle, "create_site", side_effect=create_site),
                mock.patch.object(restore_as.restore_new, "reconcile_site_ownership"),
                mock.patch.object(restore_as.cloudpanel, "reset_permissions"),
            ):
                result = restore_as.restore_as(
                    package,
                    "restore.example.com",
                    target,
                    "clpctl",
                    confirm,
                )

            self.assertEqual(result["status"], "RESTORE_AS_VERIFIED")
            restored = target / identity.site_root.lstrip("/")
            db = restored / "data" / "app.sqlite"
            self.assertTrue(db.is_file())
            for suffix in ("-wal", "-shm", "-journal"):
                self.assertFalse(db.with_name(db.name + suffix).exists())

            conn = sqlite3.connect(db)
            try:
                value = conn.execute("SELECT value FROM demo").fetchone()[0]
                self.assertEqual(value, "canonical")
                self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                conn.close()

    def test_file_verifier_excludes_sqlite_main_and_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = self._package(base)
            manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
            staged = base / "staged"
            restore_apply.extract_site_archive(package / "files" / "site.tar.gz", staged)
            restore_apply.restore_sqlite(
                package,
                manifest,
                staged,
                "/home/alice/htdocs/example.com",
            )
            files = verify.verify_files(
                package,
                manifest,
                staged,
                "/home/alice/htdocs/example.com",
            )
            sqlite_result = verify.verify_sqlite(
                package,
                manifest,
                staged,
                "/home/alice/htdocs/example.com",
            )
            self.assertEqual(files["status"], "PASS", files)
            self.assertEqual(sqlite_result["status"], "PASS", sqlite_result)
            self.assertGreaterEqual(files["sqlite_archive_copies_excluded"], 4)

    def test_restore_as_source_contains_canonical_sqlite_restore_stage(self) -> None:
        text=(ROOT / "lib" / "restore_as.py").read_text(encoding="utf-8")
        self.assertIn('failure_stage = "SQLITE_SNAPSHOT_RESTORE"', text)
        self.assertIn("restore_apply.restore_sqlite(package_dir, manifest, staged_site, source_site_root)", text)
        self.assertLess(
            text.index("restore_apply.restore_sqlite(package_dir, manifest, staged_site, source_site_root)"),
            text.index("verify_engine.verify_sqlite(package_dir, manifest, staged_site, source_site_root)"),
        )

    def test_beginner_ui_has_restore_stage_messages(self) -> None:
        text=(ROOT / "lib" / "restore_failure_ui.sh").read_text(encoding="utf-8")
        self.assertIn("SQLITE_SNAPSHOT_RESTORE)", text)
        self.assertIn("SQLite 数据库快照恢复没有完成", text)
        self.assertIn("APPLICATION_CONFIG_REMAP)", text)
        self.assertIn("网站数据库配置无法安全改写到新数据库", text)


if __name__ == "__main__":
    unittest.main()
