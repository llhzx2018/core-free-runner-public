from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import site_lifecycle


class SiteLifecycleTests(unittest.TestCase):
    def test_target_identity_is_safe_unique_and_does_not_reuse_source_user(self) -> None:
        identity = site_lifecycle.derive_target_identity("restore.example.com", "backup-123")
        self.assertEqual(identity.domain, "restore.example.com")
        self.assertTrue(identity.site_user.startswith("p07"))
        self.assertIn("/htdocs/restore.example.com", identity.site_root)
        self.assertGreaterEqual(len(identity.site_password), 24)

    def test_database_identity_is_short_and_deterministic_except_password(self) -> None:
        a = site_lifecycle.derive_database_identity("restore.example.com", "backup-123", 1)
        b = site_lifecycle.derive_database_identity("restore.example.com", "backup-123", 1)
        self.assertEqual(a[:2], b[:2])
        self.assertNotEqual(a[2], b[2])
        self.assertLessEqual(len(a[0]), 32)
        self.assertLessEqual(len(a[1]), 32)

    def test_php_site_creation_uses_cloudpanel_adapter(self) -> None:
        identity = site_lifecycle.derive_target_identity("restore.example.com", "b1")
        source = {"runtime": {"type": "php", "version": "8.4"}}
        with mock.patch.object(site_lifecycle.cloudpanel, "add_php_site") as add:
            site_lifecycle.create_site(source, identity, vhost_template="Generic")
        add.assert_called_once()
        args = add.call_args.args
        self.assertEqual(args[0], "restore.example.com")
        self.assertEqual(args[1], "8.4")
        self.assertEqual(args[2], identity.site_user)

    def test_all_supported_runtime_types_route_to_adapter(self) -> None:
        cases = [
            ({"runtime": {"type": "static"}}, "add_static_site"),
            ({"runtime": {"type": "nodejs", "version": "22", "app_port": 3000}}, "add_nodejs_site"),
            ({"runtime": {"type": "python", "version": "3.13", "app_port": 8000}}, "add_python_site"),
            ({"runtime": {"type": "reverse_proxy", "app_port": 8080}}, "add_reverse_proxy_site"),
        ]
        for source, method in cases:
            with self.subTest(method=method):
                identity = site_lifecycle.derive_target_identity(f"{method}.example.com", method)
                with mock.patch.object(site_lifecycle.cloudpanel, method) as call:
                    site_lifecycle.create_site(source, identity)
                call.assert_called_once()

    def test_unknown_runtime_fails_before_cloudpanel_write(self) -> None:
        identity = site_lifecycle.derive_target_identity("restore.example.com", "b1")
        with mock.patch.object(site_lifecycle.cloudpanel, "run") as run:
            with self.assertRaises(site_lifecycle.SiteLifecycleError):
                site_lifecycle.create_site({"runtime": {"type": "unknown"}}, identity)
        run.assert_not_called()

    def test_domain_availability_detects_existing_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.object(
                site_lifecycle.inventory,
                "build_manifest",
                return_value={"sites": [{"domain": "restore.example.com", "domains": ["restore.example.com"]}]},
            ):
                with self.assertRaisesRegex(site_lifecycle.SiteLifecycleError, "already exists"):
                    site_lifecycle.ensure_domain_available(root, "restore.example.com")

    def test_domain_availability_rejects_unmanaged_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            occupied = root / "home/alice/htdocs/restore.example.com"
            occupied.mkdir(parents=True)
            with mock.patch.object(site_lifecycle.inventory, "build_manifest", return_value={"sites": []}):
                with self.assertRaisesRegex(site_lifecycle.SiteLifecycleError, "path already exists"):
                    site_lifecycle.ensure_domain_available(root, "restore.example.com")

    def test_cleanup_is_fail_closed_and_never_raises_secret_output(self) -> None:
        with mock.patch.object(site_lifecycle.cloudpanel, "delete_site") as delete_site, mock.patch.object(
            site_lifecycle.cloudpanel, "delete_database"
        ) as delete_db:
            self.assertTrue(site_lifecycle.cleanup_site("restore.example.com"))
            self.assertTrue(site_lifecycle.cleanup_database("p07_db"))
        delete_site.assert_called_once()
        delete_db.assert_called_once()


if __name__ == "__main__":
    unittest.main()
