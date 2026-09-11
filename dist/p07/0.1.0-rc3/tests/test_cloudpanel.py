from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib"))
import cloudpanel


class CloudPanelAdapterTests(unittest.TestCase):
    def _ok(self, stdout: str = ""):
        return mock.patch.object(
            cloudpanel.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["clpctl"], 0, stdout=stdout, stderr=""),
        )

    def test_php_site_command_is_centralized_and_validated(self) -> None:
        with self._ok() as run:
            cloudpanel.add_php_site("www.example.com", "8.4", "example", "secret", vhost_template="Generic")
        args = run.call_args.args[0]
        self.assertEqual(args[0:2], ["clpctl", "site:add:php"])
        self.assertIn("--domainName=www.example.com", args)
        self.assertIn("--phpVersion=8.4", args)
        self.assertIn("--vhostTemplate=Generic", args)
        self.assertIn("--siteUser=example", args)

    def test_all_supported_site_types_have_adapters(self) -> None:
        with self._ok() as run:
            cloudpanel.add_static_site("static.example.com", "static", "pw")
            cloudpanel.add_nodejs_site("node.example.com", "22", 3000, "node", "pw")
            cloudpanel.add_python_site("py.example.com", "3.13", 8000, "py", "pw")
            cloudpanel.add_reverse_proxy_site("proxy.example.com", "http://127.0.0.1:8080", "proxy", "pw")
        commands = [call.args[0][1] for call in run.call_args_list]
        self.assertEqual(commands, [
            "site:add:static",
            "site:add:nodejs",
            "site:add:python",
            "site:add:reverse-proxy",
        ])

    def test_database_lifecycle_commands_are_centralized(self) -> None:
        with tempfile.TemporaryDirectory() as td, self._ok() as run:
            dump = Path(td) / "db.sql.gz"
            dump.write_bytes(b"placeholder")
            cloudpanel.add_database("www.example.com", "example_db", "example_user", "secret")
            cloudpanel.import_database("example_db", dump)
            cloudpanel.delete_database("example_db", force=True)
        commands = [call.args[0][1] for call in run.call_args_list]
        self.assertEqual(commands, ["db:add", "db:import", "db:delete"])
        self.assertIn("--force", run.call_args_list[-1].args[0])

    def test_database_export_requires_nonempty_output(self) -> None:
        def fake_run(command, **kwargs):
            target = next(x.split("=", 1)[1] for x in command if x.startswith("--file="))
            Path(target).write_bytes(b"dump")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as td, mock.patch.object(cloudpanel.subprocess, "run", side_effect=fake_run):
            target = cloudpanel.export_database("example_db", Path(td) / "db.sql.gz")
            self.assertEqual(target.read_bytes(), b"dump")

    def test_certificate_and_lets_encrypt_commands(self) -> None:
        with self._ok() as run:
            cloudpanel.install_certificate("www.example.com", "/tmp/key.pem", "/tmp/cert.pem")
            cloudpanel.install_lets_encrypt("www.example.com", subject_alt_names=["example.com"])
        self.assertEqual(run.call_args_list[0].args[0][1], "site:install:certificate")
        self.assertEqual(run.call_args_list[1].args[0][1], "lets-encrypt:install:certificate")
        self.assertIn("--subjectAlternativeName=example.com", run.call_args_list[1].args[0])

    def test_permissions_varnish_and_template_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as td, self._ok("Generic\n") as run:
            template = Path(td) / "template.tpl"
            template.write_text("#{}\nserver {}\n", encoding="utf-8")
            cloudpanel.import_vhost_templates()
            cloudpanel.list_vhost_templates()
            cloudpanel.add_vhost_template("My Application", template)
            cloudpanel.view_vhost_template("My Application")
            cloudpanel.delete_vhost_template("My Application")
            cloudpanel.reset_permissions("/home/example/htdocs/www.example.com", directories="750", files="640")
            cloudpanel.purge_varnish("all")
        self.assertEqual([c.args[0][1] for c in run.call_args_list], [
            "vhost-templates:import",
            "vhost-templates:list",
            "vhost-template:add",
            "vhost-template:view",
            "vhost-template:delete",
            "system:permissions:reset",
            "varnish-cache:purge",
        ])

    def test_panel_user_lifecycle_and_security_commands(self) -> None:
        with self._ok("john.doe\n") as run:
            cloudpanel.add_panel_user(
                "john.doe",
                "john@example.com",
                "John",
                "Doe",
                "secret",
                role="user",
                sites=["www.example.com"],
            )
            cloudpanel.list_panel_users()
            cloudpanel.reset_panel_user_password("john.doe", "new-secret")
            cloudpanel.disable_panel_user_mfa("john.doe")
            cloudpanel.delete_panel_user("john.doe")
            cloudpanel.enable_panel_basic_auth("gate", "auth-secret")
            cloudpanel.disable_panel_basic_auth()
            cloudpanel.update_cloudflare_ips()
        commands = [call.args[0][1] for call in run.call_args_list]
        self.assertEqual(commands, [
            "user:add",
            "user:list",
            "user:reset:password",
            "user:disable:mfa",
            "user:delete",
            "cloudpanel:enable:basic-auth",
            "cloudpanel:disable:basic-auth",
            "cloudflare:update:ips",
        ])
        self.assertIn("--sites=www.example.com", run.call_args_list[0].args[0])

    def test_delete_site_requires_explicit_force_flag(self) -> None:
        with self._ok() as run:
            cloudpanel.delete_site("www.example.com")
            cloudpanel.delete_site("www.example.com", force=True)
        self.assertNotIn("--force", run.call_args_list[0].args[0])
        self.assertIn("--force", run.call_args_list[1].args[0])

    def test_invalid_inputs_fail_before_clpctl(self) -> None:
        with mock.patch.object(cloudpanel.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                cloudpanel.add_php_site("../../etc/passwd", "8.4", "u", "pw")
            with self.assertRaises(ValueError):
                cloudpanel.add_nodejs_site("node.example.com", "22", 70000, "node", "pw")
            with self.assertRaises(ValueError):
                cloudpanel.add_database("www.example.com", "bad/name", "user", "pw")
            with self.assertRaises(ValueError):
                cloudpanel.add_panel_user("user", "not-an-email", "A", "B", "pw")
            with self.assertRaises(ValueError):
                cloudpanel.add_panel_user("user", "u@example.com", "A", "B", "pw", role="owner")
        run.assert_not_called()

    def test_failures_never_echo_command_output_or_secret(self) -> None:
        secret = "super-secret-value"
        with mock.patch.object(
            cloudpanel.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["clpctl"], 9, stdout=secret, stderr=secret),
        ):
            with self.assertRaises(cloudpanel.CloudPanelError) as ctx:
                cloudpanel.add_database("www.example.com", "db", "user", secret)
        self.assertNotIn(secret, str(ctx.exception))
        self.assertIn("db_add", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
