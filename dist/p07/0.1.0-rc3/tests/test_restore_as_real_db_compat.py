from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import cloudpanel
import package as package_engine
import restore_as
import restore_as_verified
import site_lifecycle


class RestoreAsRealDbCompatTests(unittest.TestCase):
    def make_package(self, base: Path, target_domain: str) -> tuple[Path, site_lifecycle.TargetSiteIdentity]:
        package = base / "backup"
        package.mkdir()
        backup_id = "www.123.com_20260911T131602Z"
        manifest = {
            "schema": package_engine.PACKAGE_SCHEMA,
            "backup_id": backup_id,
            "site": {"domain": "www.123.com"},
            "contents": {"mysql": [], "metadata": {}},
        }
        (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        identity = site_lifecycle.derive_target_identity(target_domain, backup_id)
        return package, identity

    def test_db_import_is_staged_private_under_target_site_home_and_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "target"
            root.mkdir()
            package, identity = self.make_package(Path(td), "www.444.com")
            site_root = root / identity.site_root.lstrip("/")
            site_root.mkdir(parents=True)
            source = Path(td) / "source.sql.gz"
            source.write_bytes(b"synthetic-sql")
            seen: dict[str, object] = {}

            def fake_import(database, dump, *, clpctl="clpctl"):
                staged = Path(dump)
                seen["database"] = database
                seen["path"] = staged
                seen["mode"] = staged.stat().st_mode & 0o777
                seen["uid"] = staged.stat().st_uid
                seen["gid"] = staged.stat().st_gid
                seen["content"] = staged.read_bytes()

            with mock.patch.object(restore_as.cloudpanel, "import_database", side_effect=fake_import):
                with restore_as_verified._database_compat_context(package, "www.444.com", root):
                    restore_as.cloudpanel.import_database("target_db", source, clpctl="clpctl")
                    staged = Path(seen["path"])
                    self.assertTrue(staged.is_file())
                    self.assertEqual(staged.parent.parent, site_root.parent.parent)
                    workdir = staged.parent
                self.assertFalse(workdir.exists())

            owner = site_root.stat()
            self.assertEqual(seen["database"], "target_db")
            self.assertEqual(seen["mode"], 0o600)
            self.assertEqual((seen["uid"], seen["gid"]), (owner.st_uid, owner.st_gid))
            self.assertEqual(seen["content"], b"synthetic-sql")

    def test_db_export_uses_site_private_workdir_then_copies_to_requested_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "target"
            root.mkdir()
            package, identity = self.make_package(Path(td), "www.444.com")
            site_root = root / identity.site_root.lstrip("/")
            site_root.mkdir(parents=True)
            requested = Path(td) / "root-private" / "verify.sql.gz"
            seen: dict[str, Path] = {}

            def fake_export(database, output, *, clpctl="clpctl"):
                staged = Path(output)
                seen["path"] = staged
                staged.write_bytes(b"verified-export")
                return staged

            with mock.patch.object(restore_as.cloudpanel, "export_database", side_effect=fake_export):
                with restore_as_verified._database_compat_context(package, "www.444.com", root):
                    result = restore_as.cloudpanel.export_database("target_db", requested, clpctl="clpctl")
                    staged = seen["path"]
                    self.assertTrue(staged.is_file())
                    self.assertEqual(staged.parent.parent, site_root.parent.parent)
                    workdir = staged.parent
                self.assertFalse(workdir.exists())

            self.assertEqual(result, requested)
            self.assertEqual(requested.read_bytes(), b"verified-export")
            self.assertEqual(requested.stat().st_mode & 0o777, 0o600)

    def test_cloudpanel_error_detail_walks_restore_as_cause_chain_without_output(self) -> None:
        try:
            try:
                raise cloudpanel.CloudPanelError("db_import", 1)
            except cloudpanel.CloudPanelError as inner:
                raise restore_as.RestoreAsError("outer restore failure") from inner
        except restore_as.RestoreAsError as outer:
            self.assertEqual(restore_as_verified._cloudpanel_error_detail(outer), ("db_import", "1"))

    def test_cloudpanel_error_detail_handles_unknown_exit(self) -> None:
        error = cloudpanel.CloudPanelError("db_export")
        self.assertEqual(restore_as_verified._cloudpanel_error_detail(error), ("db_export", "UNKNOWN"))


if __name__ == "__main__":
    unittest.main()
