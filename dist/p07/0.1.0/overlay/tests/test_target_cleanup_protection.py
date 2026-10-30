"""Adversarial no-delete regression for failed migration cleanup.

Synthetic-only, never contacts CloudPanel or real databases. This tests the
legacy source-push cleanup route that is independent of target-pull resume.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import server_migration as engine


class RetainTargetCleanupTests(unittest.TestCase):
    def _run(self, databases, *, marker_kind="owned"):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            with mock.patch.object(engine, "STATE_ROOT", path / "state"):
                site = engine.target_site_marker("mid-safe", "example.test")
                db = engine.target_db_marker("mid-safe", "example.test", "site_db", 1)
                content = {
                    "domain": "example.test",
                    "created_by_migration": "mid-safe" if marker_kind == "owned" else "untrusted"
                }
                engine.atomic_private_json(site, content)
                engine.atomic_private_json(db, {
                    "domain": "example.test", "database": "site_db",
                    "created_by_migration": "mid-safe"
                })
                before = (site.read_bytes(), db.read_bytes())
                with (
                    mock.patch.object(engine.site_lifecycle, "cleanup_database") as drop_db,
                    mock.patch.object(engine.site_lifecycle, "cleanup_site") as drop_site,
                    mock.patch.object(engine.cloudpanel, "add_database") as add_db,
                    mock.patch.object(engine.cloudpanel, "import_database") as import_db,
                ):
                    result = engine.target_cleanup_site_local(
                        "mid-safe", "example.test", databases
                    )
                    for forbidden in (drop_db, drop_site, add_db, import_db):
                        forbidden.assert_not_called()
                self.assertEqual((site.read_bytes(), db.read_bytes()), before)
                self.assertEqual(result, {
                    "status": "RETAINED_RECOVERY_REQUIRED",
                    "database_cleanup": False,
                    "site_cleanup": False,
                    "data_writes_performed": False,
                    "source_deleted": False,
                    "dns_changed": False,
                    "recovery_proof": "NOT_ESTABLISHED",
                    "secrets_emitted": False,
                })
                return result

    def test_owned_target_with_data_must_not_be_deleted(self):
        self._run(["site_db"])

    def test_foreign_site_marker_must_not_be_deleted(self):
        self._run(["site_db"], marker_kind="foreign")

    def test_multiple_legacy_cleanup_targets_still_retained(self):
        self._run(["site_db", "additional_db"])

    def test_even_empty_database_list_cannot_delete_site(self):
        self._run([])

    def test_invalid_migration_id_refuses_before_any_deletion(self):
        with mock.patch.object(engine.site_lifecycle, "cleanup_site") as clear:
            with self.assertRaises(engine.ServerMigrationError):
                engine.target_cleanup_site_local("../bad", "example.test", [])
            clear.assert_not_called()

    def test_invalid_database_name_refuses(self):
        with mock.patch.object(engine.site_lifecycle, "cleanup_database") as clear:
            with self.assertRaises(engine.ServerMigrationError):
                engine.target_cleanup_site_local("mid-safe", "example.test", ["../secret"])
            clear.assert_not_called()

    def test_no_data_returned_for_secret_marker(self):
        value = self._run(["site_db"])
        self.assertFalse(value["secrets_emitted"])
        self.assertNotIn('"password":', json.dumps(value).lower())


if __name__ == "__main__":
    unittest.main()
