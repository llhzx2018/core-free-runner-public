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


if __name__ == "__main__":
    unittest.main()
