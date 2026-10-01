from __future__ import annotations

from contextlib import nullcontext
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

    def test_nginx_reload_prefers_active_systemd_after_syntax_pass(self) -> None:
        calls = [
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="active\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        ]
        with mock.patch.object(restore_as_verified, "_run", side_effect=calls) as run:
            mode = restore_as_verified._reload_nginx(
                "/usr/sbin/nginx",
                systemctl="/usr/bin/systemctl",
            )
        self.assertEqual(mode, "SYSTEMD")
        self.assertEqual(run.call_args_list[0].args[0], ["/usr/sbin/nginx", "-t"])
        self.assertEqual(
            run.call_args_list[1].args[0],
            ["/usr/bin/systemctl", "is-active", "nginx"],
        )
        self.assertEqual(
            run.call_args_list[2].args[0],
            ["/usr/bin/systemctl", "reload", "nginx"],
        )

    def test_nginx_reload_falls_back_to_direct_signal_without_active_systemd(self) -> None:
        calls = [
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 3, stdout="inactive\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        ]
        with mock.patch.object(restore_as_verified, "_run", side_effect=calls) as run:
            mode = restore_as_verified._reload_nginx(
                "/usr/sbin/nginx",
                systemctl="/usr/bin/systemctl",
            )
        self.assertEqual(mode, "DIRECT_SIGNAL")
        self.assertEqual(
            run.call_args_list[2].args[0],
            ["/usr/sbin/nginx", "-s", "reload"],
        )

    def test_nginx_systemd_reload_failure_uses_managed_main_hup_fallback(self) -> None:
        calls = [
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="active\n", stderr=""),
            subprocess.CompletedProcess(
                [],
                1,
                stdout="",
                stderr="Job type reload is not applicable for unit nginx.service.",
            ),
            subprocess.CompletedProcess([], 0, stdout="active\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="active\n", stderr=""),
        ]
        with mock.patch.object(
            restore_as_verified,
            "_run",
            side_effect=calls,
        ) as run, mock.patch.object(restore_as_verified.time, "sleep"):
            mode = restore_as_verified._reload_nginx(
                "/usr/sbin/nginx",
                systemctl="/usr/bin/systemctl",
            )
        self.assertEqual(mode, "SYSTEMD_MAIN_HUP")
        self.assertEqual(
            run.call_args_list[3].args[0],
            ["/usr/bin/systemctl", "is-active", "nginx"],
        )
        self.assertEqual(
            run.call_args_list[4].args[0],
            [
                "/usr/bin/systemctl",
                "kill",
                "--kill-whom=main",
                "--signal=HUP",
                "nginx",
            ],
        )
        self.assertEqual(
            run.call_args_list[5].args[0],
            ["/usr/bin/systemctl", "is-active", "nginx"],
        )

    def test_nginx_managed_hup_failure_is_safe_and_fail_closed(self) -> None:
        calls = [
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="active\n", stderr=""),
            subprocess.CompletedProcess([], 1, stdout="", stderr="reload command failed"),
            subprocess.CompletedProcess([], 0, stdout="active\n", stderr=""),
            subprocess.CompletedProcess(
                [],
                1,
                stdout="",
                stderr="Main PID unavailable INTERNAL_SECRET_DETAIL",
            ),
        ]
        with mock.patch.object(restore_as_verified, "_run", side_effect=calls):
            with self.assertRaises(restore_as_verified.RestoreAsVerificationError) as caught:
                restore_as_verified._reload_nginx(
                    "/usr/sbin/nginx",
                    systemctl="/usr/bin/systemctl",
                )
        message = str(caught.exception)
        self.assertIn("mode=SYSTEMD_MAIN_HUP", message)
        self.assertIn("reason=PID_UNAVAILABLE", message)
        self.assertNotIn("INTERNAL_SECRET_DETAIL", message)

    def test_nginx_systemd_reload_failure_is_classified_and_does_not_fallback(self) -> None:
        calls = [
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="active\n", stderr=""),
            subprocess.CompletedProcess(
                [],
                1,
                stdout="",
                stderr="Access denied INTERNAL_SECRET_DETAIL",
            ),
        ]
        with mock.patch.object(restore_as_verified, "_run", side_effect=calls) as run:
            with self.assertRaises(restore_as_verified.RestoreAsVerificationError) as caught:
                restore_as_verified._reload_nginx(
                    "/usr/sbin/nginx",
                    systemctl="/usr/bin/systemctl",
                )
        message = str(caught.exception)
        self.assertIn("mode=SYSTEMD", message)
        self.assertIn("reason=PERMISSION_DENIED", message)
        self.assertNotIn("INTERNAL_SECRET_DETAIL", message)
        self.assertEqual(len(run.call_args_list), 3)

    def test_nginx_reload_preflight_failure_is_fail_closed(self) -> None:
        proc = subprocess.CompletedProcess([], 1, stdout="", stderr="bad config")
        with mock.patch.object(restore_as_verified, "_run", return_value=proc):
            with self.assertRaisesRegex(
                restore_as_verified.RestoreAsVerificationError,
                "nginx reload preflight failed",
            ):
                restore_as_verified._reload_nginx("/usr/sbin/nginx")

    def test_curl_failure_class_is_safe_and_bounded(self) -> None:
        self.assertEqual(restore_as_verified._curl_failure_class(7), "CONNECT_FAILED")
        self.assertEqual(restore_as_verified._curl_failure_class(28), "TIMEOUT")
        self.assertEqual(restore_as_verified._curl_failure_class(52), "EMPTY_REPLY")
        self.assertEqual(restore_as_verified._curl_failure_class(99), "OTHER")

    def test_http_probe_forces_direct_no_proxy_loopback(self) -> None:
        proc = subprocess.CompletedProcess([], 0, stdout="200", stderr="")
        with mock.patch.object(restore_as_verified, "_run", return_value=proc) as run:
            rc, code = restore_as_verified._http_code(
                "/usr/bin/curl",
                "restore.example.com",
                "http",
                80,
            )
        self.assertEqual((rc, code), (0, "200"))
        command = run.call_args.args[0]
        self.assertIn("--noproxy", command)
        self.assertIn("*", command)
        self.assertIn("--resolve", command)
        self.assertIn("restore.example.com:80:127.0.0.1", command)

    def test_http_probe_retries_transient_local_failure(self) -> None:
        with mock.patch.object(
            restore_as_verified,
            "_http_code",
            side_effect=[(7, "000"), (0, "301")],
        ) as probe, mock.patch.object(restore_as_verified.time, "sleep") as sleep:
            rc, code = restore_as_verified._http_probe(
                "/usr/bin/curl",
                "restore.example.com",
                "http",
                80,
                addresses=("127.0.0.1",),
                attempts_per_address=2,
                delay=0.01,
            )
        self.assertEqual((rc, code), (0, "301"))
        self.assertEqual(probe.call_count, 2)
        sleep.assert_called_once()

    def test_nginx_listener_discovery_uses_only_target_server_blocks(self) -> None:
        nginx_dump = """
server {
    listen 80;
    listen [::]:80;
    server_name other.example.com;
}
server {
    listen 192.0.2.44:80;
    listen [2001:db8::44]:80;
    listen 443 ssl;
    server_name restore.example.com www.restore.example.com;
    location / { try_files $uri =404; }
}
"""
        proc = subprocess.CompletedProcess([], 0, stdout=nginx_dump, stderr="")
        with mock.patch.object(restore_as_verified, "_run", return_value=proc):
            http = restore_as_verified._nginx_target_listener_addresses(
                "/usr/sbin/nginx",
                "restore.example.com",
                80,
            )
            https = restore_as_verified._nginx_target_listener_addresses(
                "/usr/sbin/nginx",
                "restore.example.com",
                443,
            )
        self.assertEqual(http, ["192.0.2.44", "2001:db8::44"])
        self.assertEqual(https, ["127.0.0.1"])

    def test_nginx_listener_discovery_maps_wildcards_to_loopback(self) -> None:
        nginx_dump = """
server {
    listen 80;
    listen [::]:80;
    server_name restore.example.com;
}
"""
        proc = subprocess.CompletedProcess([], 0, stdout=nginx_dump, stderr="")
        with mock.patch.object(restore_as_verified, "_run", return_value=proc):
            addresses = restore_as_verified._nginx_target_listener_addresses(
                "/usr/sbin/nginx",
                "restore.example.com",
                80,
            )
        self.assertEqual(addresses, ["127.0.0.1", "::1"])

    def test_http_probe_tries_discovered_listener_addresses(self) -> None:
        with mock.patch.object(
            restore_as_verified,
            "_http_code",
            side_effect=[(7, "000"), (0, "200")],
        ) as probe:
            rc, code = restore_as_verified._http_probe(
                "/usr/bin/curl",
                "restore.example.com",
                "http",
                80,
                addresses=("192.0.2.44", "192.0.2.45"),
                attempts_per_address=1,
            )
        self.assertEqual((rc, code), (0, "200"))
        self.assertEqual(probe.call_args_list[0].kwargs["address"], "192.0.2.44")
        self.assertEqual(probe.call_args_list[1].kwargs["address"], "192.0.2.45")

    def test_local_verification_accepts_https_sni_probe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = self.base_result(root)
            with mock.patch.object(
                restore_as_verified,
                "_nginx_target_listener_addresses",
                side_effect=[["192.0.2.44"], ["192.0.2.44"]],
            ), mock.patch.object(
                restore_as_verified,
                "_http_probe",
                side_effect=[(0, "200"), (0, "302")],
            ):
                verified = restore_as_verified.verify_local_restore(root, result)
            self.assertEqual(verified["status"], "PASS")
            self.assertEqual(verified["host"]["http_code"], "200")
            self.assertEqual(verified["host"]["mode"], "LOCAL_HTTP_NGINX_LISTENER")
            self.assertEqual(verified["host"]["listener_candidates"], 1)
            self.assertEqual(verified["sni"]["mode"], "LOCAL_HTTPS_SNI")
            self.assertGreaterEqual(verified["files"]["file_count"], 1)
            self.assertFalse(verified["dns_changed"])
            self.assertFalse(verified["source_deleted"])

    def test_local_verification_allows_tls_deferred_only_with_target_vhost(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = self.base_result(root)
            with mock.patch.object(
                restore_as_verified,
                "_nginx_target_listener_addresses",
                side_effect=[["127.0.0.1"], ["127.0.0.1"]],
            ), mock.patch.object(
                restore_as_verified,
                "_http_probe",
                side_effect=[(0, "200"), (35, "000")],
            ), mock.patch.object(
                restore_as_verified,
                "_nginx_has_target_vhost",
                return_value=True,
            ):
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
                "_nginx_target_listener_addresses",
                return_value=[],
            ), mock.patch.object(
                restore_as_verified,
                "_nginx_has_target_vhost",
                return_value=False,
            ):
                with self.assertRaisesRegex(
                    restore_as_verified.RestoreAsVerificationError,
                    "target_vhost=MISSING",
                ):
                    restore_as_verified.verify_local_restore(root, result)

    def test_present_vhost_without_http_listener_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = self.base_result(root)
            with mock.patch.object(
                restore_as_verified,
                "_nginx_target_listener_addresses",
                return_value=[],
            ), mock.patch.object(
                restore_as_verified,
                "_nginx_has_target_vhost",
                return_value=True,
            ):
                with self.assertRaisesRegex(
                    restore_as_verified.RestoreAsVerificationError,
                    "target_listener=MISSING",
                ):
                    restore_as_verified.verify_local_restore(root, result)

    def test_failed_http_probe_reports_present_target_vhost(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = self.base_result(root)
            with mock.patch.object(
                restore_as_verified,
                "_nginx_target_listener_addresses",
                return_value=["192.0.2.44"],
            ), mock.patch.object(
                restore_as_verified,
                "_http_probe",
                return_value=(7, "000"),
            ):
                with self.assertRaisesRegex(
                    restore_as_verified.RestoreAsVerificationError,
                    "target_transport=CONNECT_FAILED",
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
            with mock.patch.object(
                restore_as_verified,
                "_database_compat_context",
                return_value=nullcontext(),
            ), mock.patch.object(
                restore_as_verified.restore_as,
                "restore_as",
                return_value=engine,
            ), mock.patch.object(
                restore_as_verified,
                "_reload_nginx",
                return_value="SYSTEMD",
            ) as reload_nginx, mock.patch.object(
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
            reload_nginx.assert_called_once_with(
                "/usr/sbin/nginx",
                systemctl="/usr/bin/systemctl",
            )
            self.assertEqual(result["status"], "RESTORE_AS_VERIFIED")
            self.assertEqual(result["local_verification"]["status"], "PASS")
            self.assertEqual(result["nginx_reload"], {"status": "PASS", "mode": "SYSTEMD"})
            self.assertEqual(result["machine_verification_scope"], "FILES_DB_APP_HOST_SNI")

    def test_local_verification_failure_rolls_back_only_new_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "home/alice/htdocs/example.com"
            source.mkdir(parents=True)
            sentinel = source / "SOURCE_SENTINEL"
            sentinel.write_text("preserve\n", encoding="utf-8")
            engine = self.base_result(root)
            with mock.patch.object(
                restore_as_verified,
                "_database_compat_context",
                return_value=nullcontext(),
            ), mock.patch.object(
                restore_as_verified.restore_as,
                "restore_as",
                return_value=engine,
            ), mock.patch.object(
                restore_as_verified,
                "_reload_nginx",
            ), mock.patch.object(
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
