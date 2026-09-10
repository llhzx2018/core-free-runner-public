from __future__ import annotations

import gzip
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib"))

import cloudpanel
import package as package_facade
import package_core
import restore_apply
import restore_apply_core


class CloudPanelIntegrationTests(unittest.TestCase):
    def test_backup_core_database_export_is_routed_through_adapter(self) -> None:
        self.assertIs(package_core.export_mysql, package_facade.export_mysql)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "mysql"

            def fake_export(database: str, target: Path, *, clpctl: str = "clpctl") -> Path:
                target.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(target, "wb") as handle:
                    handle.write(b"SELECT 1;\n")
                return target

            with mock.patch.object(cloudpanel, "export_database", side_effect=fake_export) as export:
                result = package_facade.export_mysql(["example_db"], out, "/usr/bin/clpctl")
            export.assert_called_once()
            self.assertEqual(result[0]["database"], "example_db")
            self.assertEqual(result[0]["method"], "clpctl_db_export")

    def test_restore_core_command_runner_is_routed_through_adapter(self) -> None:
        self.assertIs(restore_apply_core.run_clpctl, restore_apply.run_clpctl)
        with mock.patch.object(cloudpanel, "run") as run:
            restore_apply.run_clpctl("/usr/bin/clpctl", ["site:delete", "--domainName=example.com"], timeout=25)
        run.assert_called_once_with(
            ["site:delete", "--domainName=example.com"],
            clpctl="/usr/bin/clpctl",
            timeout=25,
            operation="site:delete",
        )

    def test_restore_adapter_converts_failure_without_secret_output(self) -> None:
        secret = "never-print-this"
        failure = cloudpanel.CloudPanelError("db:import", 9)
        with mock.patch.object(cloudpanel, "run", side_effect=failure):
            with self.assertRaises(restore_apply.SandboxRestoreError) as ctx:
                restore_apply.run_clpctl(
                    "/usr/bin/clpctl",
                    ["db:import", "--databaseName=db", f"--file=/tmp/{secret}"],
                )
        self.assertNotIn(secret, str(ctx.exception))
        self.assertIn("db:import", str(ctx.exception))
        self.assertIn("exit 9", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
