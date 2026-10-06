from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ops_diagnostics", ROOT / "lib" / "ops_diagnostics.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OpsDiagnosticsPhpFpmTests(unittest.TestCase):
    def _config_dir(self, text: str) -> tempfile.TemporaryDirectory:
        td = tempfile.TemporaryDirectory()
        Path(td.name, "site.conf").write_text(text, encoding="utf-8")
        return td

    def test_no_php_fastcgi_backend_is_not_a_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            status, detail = MODULE.php_fpm_health(Path(td))
        self.assertEqual(status, "OK")
        self.assertIn("未发现需要 PHP-FPM", detail)

    def test_cloudpanel_tcp_fastcgi_backend_is_healthy_when_port_accepts(self) -> None:
        with self._config_dir(
            "server { server_name example.com; fastcgi_pass 127.0.0.1:19001; }"
        ) as td, mock.patch.object(
            MODULE, "tcp_listener_ready", return_value=True
        ) as ready:
            status, detail = MODULE.php_fpm_health(Path(td))
        self.assertEqual(status, "OK")
        self.assertIn("已验证 1 个 FastCGI 后端", detail)
        ready.assert_called_once_with(19001)

    def test_cloudpanel_tcp_fastcgi_backend_warns_when_listener_is_missing(self) -> None:
        with self._config_dir(
            "server { server_name example.com; fastcgi_pass localhost:18001; }"
        ) as td, mock.patch.object(
            MODULE, "tcp_listener_ready", return_value=False
        ):
            status, detail = MODULE.php_fpm_health(Path(td))
        self.assertEqual(status, "WARN")
        self.assertIn("127.0.0.1:18001", detail)

    def test_unix_fastcgi_backend_remains_supported(self) -> None:
        with self._config_dir(
            "server { server_name example.com; fastcgi_pass unix:/run/php/php8.4-fpm.sock; }"
        ) as td, mock.patch.object(
            MODULE, "unix_listener_ready", return_value=True
        ) as ready:
            status, detail = MODULE.php_fpm_health(Path(td))
        self.assertEqual(status, "OK")
        self.assertIn("已验证 1 个 FastCGI 后端", detail)
        ready.assert_called_once_with(Path("/run/php/php8.4-fpm.sock"))

    def test_duplicate_fastcgi_backends_are_deduplicated(self) -> None:
        with self._config_dir(
            """
            server { fastcgi_pass 127.0.0.1:13001; }
            server { fastcgi_pass 127.0.0.1:13001; }
            """
        ) as td, mock.patch.object(
            MODULE, "tcp_listener_ready", return_value=True
        ) as ready:
            backends = MODULE.php_fpm_backends(Path(td))
            status, _ = MODULE.php_fpm_health(Path(td))
        self.assertEqual(backends, [("tcp", "13001")])
        self.assertEqual(status, "OK")
        ready.assert_called_once_with(13001)



class OpsDiagnosticsBackupCoverageTests(unittest.TestCase):
    def _write_backup(self, root: Path, name: str, domain: str, created_at: str, *, status: str = "PASS") -> Path:
        package = root / name
        package.mkdir(parents=True)
        (package / "manifest.json").write_text(
            __import__("json").dumps({
                "site": {"domain": domain},
                "created_at": created_at,
                "backup_kind": "automatic",
            }),
            encoding="utf-8",
        )
        (package / "verification.json").write_text(
            __import__("json").dumps({"status": status}),
            encoding="utf-8",
        )
        return package

    def test_current_site_domains_uses_current_inventory(self) -> None:
        payload = '{"sites":[{"domain":"b.example"},{"domain":"a.example"},{"domain":"a.example"}]}'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bin").mkdir()
            (root / "bin" / "vfops").write_text("#!/bin/sh\n", encoding="utf-8")
            with mock.patch.object(MODULE, "ROOT", root), \
                 mock.patch.object(MODULE, "run", return_value=(0, payload)) as run:
                domains = MODULE.current_site_domains()
            self.assertEqual(domains, ["a.example", "b.example"])
            run.assert_called_once_with(
                [str(root / "bin/vfops"), "inventory", "--compact"],
                timeout=15,
            )

    def test_unreadable_backup_storage_is_unknown_not_zero_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "not-a-directory"
            path.write_text("x", encoding="utf-8")
            status, detail = MODULE.local_backup_health(["a.example"], path)
        self.assertEqual(status, "WARN")
        self.assertIn("不能判断覆盖率", detail)
        self.assertNotIn("0/1", detail)

    def test_partial_coverage_is_warning_and_lists_missing_sites(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_backup(root, "a", "a.example", "2026-10-06T05:00:00+00:00")
            self._write_backup(root, "b", "b.example", "2026-10-06T05:05:00+00:00")
            status, detail = MODULE.local_backup_health(
                ["a.example", "b.example", "c.example"],
                root,
                __import__("datetime").datetime(2026, 10, 6, 6, 0, tzinfo=__import__("datetime").timezone.utc),
            )
        self.assertEqual(status, "WARN")
        self.assertIn("2/3 已验证", detail)
        self.assertIn("c.example", detail)

    def test_all_current_sites_fresh_is_ok(self) -> None:
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_backup(root, "a", "a.example", "2026-10-06T05:00:00+00:00")
            self._write_backup(root, "b", "b.example", "2026-10-06T04:30:00+00:00")
            status, detail = MODULE.local_backup_health(
                ["a.example", "b.example"],
                root,
                datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc),
            )
        self.assertEqual(status, "OK")
        self.assertIn("2/2 已验证", detail)
        self.assertIn("最旧约 1.5 小时前", detail)

    def test_complete_but_stale_coverage_remains_warning(self) -> None:
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_backup(root, "a", "a.example", "2026-10-01T05:00:00+00:00")
            self._write_backup(root, "b", "b.example", "2026-10-06T05:00:00+00:00")
            status, detail = MODULE.local_backup_health(
                ["a.example", "b.example"],
                root,
                datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc),
            )
        self.assertEqual(status, "WARN")
        self.assertIn("2/2 已验证", detail)
        self.assertIn("最旧约", detail)

    def test_failed_or_unrelated_backup_does_not_satisfy_current_site(self) -> None:
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_backup(root, "failed", "a.example", "2026-10-06T05:00:00+00:00", status="FAIL")
            self._write_backup(root, "other", "other.example", "2026-10-06T05:00:00+00:00")
            status, detail = MODULE.local_backup_health(
                ["a.example"],
                root,
                datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc),
            )
        self.assertEqual(status, "WARN")
        self.assertIn("0/1 已验证", detail)
        self.assertIn("a.example", detail)




if __name__ == "__main__":
    unittest.main()
