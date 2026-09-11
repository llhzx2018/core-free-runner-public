from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import restore_as_verified


class RestoreAsVerifiedTests(unittest.TestCase):
    def base_result(self, root: Path) -> dict:
        site = root / "home/p07restore/htdocs/restore.example.com"
        site.mkdir(parents=True)
        (site / "index.php").write_text("<?php echo 'ok';\n", encoding="utf-8")
        return {
            "schema": "vf-server-ops.restore-as-result.v1",
            "status": "RESTORE_AS_VERIFIED",
            "backup_id": "example.com_20260910T000000Z",
            "source_domain": "example.com",
            "target_domain": "restore.example.com",
            "target_site_user": "p07restore",
            "target_site_root": "/home/p07restore/htdocs/restore.example.com",
            "target_database": "p07_target_1",
            "target_database_user": "p07u_target_1",
            "application_config_mode": "WORDPRESS_WP_CONFIG",
            "wordpress_urls": {
                "home": "https://restore.example.com",
                "siteurl": "https://restore.example.com",
            },
            "database_import_verified_before_transform": True,
            "source_ssl_reused": False,
            "dns_changed": False,
            "source_deleted": False,
            "existing_site_overwrite_allowed": False,
        }

    def test_local_verification_accepts_https_sni_probe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = self.base_result(root)
            calls = [
                subprocess.CompletedProcess([], 0, stdout="200", stderr=""),
                subprocess.CompletedProcess([], 0, stdout="302", stderr=""),
            ]
            with mock.patch.object(restore_as_verified, "_run", side_effect=calls):
                verified = restore_as_verified.verify_local_restore(root, result)
            self.assertEqual(verified["status"], "PASS")
            self.assertEqual(verified["host"]["http_code"], "200")
            self.assertEqual(verified["sni"]["mode"], "LOCAL_HTTPS_SNI")
            self.assertGreaterEqual(verified["files"]["file_count"], 1)
            self.assertFalse(verified["dns_changed"])
            self.assertFalse(verified["source_deleted"])

    def test_local_verification_allows_tls_deferred_only_with_target_vhost(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = self.base_result(root)
            calls = [
                subprocess.CompletedProcess([], 0, stdout="200", stderr=""),
                subprocess.CompletedProcess([], 35, stdout="000", stderr="tls unavailable"),
                subprocess.CompletedProcess(
                    [],
                    0,
                    stdout="server { listen 80; server_name restore.example.com www.restore.example.com; }\n",
                    stderr="",
                ),
            ]
            with mock.patch.object(restore_as_verified, "_run", side_effect=calls):
                verified = restore_as_verified.verify_local_restore(root, result)
            self.assertEqual(verified["sni"]["status"], "PASS")
            self.assertEqual(verified["sni"]["mode"], "TARGET_VHOST_PRESENT_TLS_DEFERRED")
            self.assertEqual(
                verified["sni"]["certificate_trust"],
                "DEFERRED_UNTIL_TARGET_DNS_CERTIFICATE",
            )

    def test_missing_host_route_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = self.base_result(root)
            with mock.patch.object(
                restore_as_verified,
                "_run",
                return_value=subprocess.CompletedProcess([], 7, stdout="000", stderr="connect failed"),
            ):
                with self.assertRaisesRegex(
                    restore_as_verified.RestoreAsVerificationError,
                    "Host routing",
                ):
                    restore_as_verified.verify_local_restore(root, result)

    def test_success_is_returned_only_after_local_verification(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            engine = self.base_result(root)
            local = {
                "status": "PASS",
                "files": {"status": "PASS", "file_count": 1},
                "database": {"status": "PASS", "source_match_before_transform": True},
                "application": {"status": "PASS", "mode": "WORDPRESS_WP_CONFIG"},
                "host": {"status": "PASS", "mode": "LOCAL_HTTP_RESOLVE", "http_code": "200"},
                "sni": {"status": "PASS", "mode": "LOCAL_HTTPS_SNI", "http_code": "200"},
            }
            with mock.patch.object(restore_as_verified.restore_as, "restore_as", return_value=engine), mock.patch.object(
                restore_as_verified,
                "verify_local_restore",
                return_value=local,
            ):
                result = restore_as_verified.restore_as_verified(
                    root / "backup",
                    "restore.example.com",
                    root,
                    "clpctl",
                    "CONFIRM",
                )
            self.assertEqual(result["status"], "RESTORE_AS_VERIFIED")
            self.assertEqual(result["local_verification"]["status"], "PASS")
            self.assertEqual(result["machine_verification_scope"], "FILES_DB_APP_HOST_SNI")

    def test_local_verification_failure_rolls_back_only_new_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "home/alice/htdocs/example.com"
            source.mkdir(parents=True)
            sentinel = source / "SOURCE_SENTINEL"
            sentinel.write_text("preserve\n", encoding="utf-8")
            engine = self.base_result(root)
            with mock.patch.object(restore_as_verified.restore_as, "restore_as", return_value=engine), mock.patch.object(
                restore_as_verified,
                "verify_local_restore",
                side_effect=restore_as_verified.RestoreAsVerificationError("probe failed"),
            ), mock.patch.object(
                restore_as_verified.site_lifecycle,
                "cleanup_database",
                return_value=True,
            ) as cleanup_db, mock.patch.object(
                restore_as_verified.site_lifecycle,
                "cleanup_site",
                return_value=True,
            ) as cleanup_site:
                with self.assertRaisesRegex(
                    restore_as_verified.RestoreAsVerificationError,
                    "rollback=PASS",
                ):
                    restore_as_verified.restore_as_verified(
                        root / "backup",
                        "restore.example.com",
                        root,
                        "clpctl",
                        "CONFIRM",
                    )
            cleanup_db.assert_called_once_with("p07_target_1", clpctl="clpctl")
            cleanup_site.assert_called_once_with("restore.example.com", clpctl="clpctl")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")


if __name__ == "__main__":
    unittest.main()
