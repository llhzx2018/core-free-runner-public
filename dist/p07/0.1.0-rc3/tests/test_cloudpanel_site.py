from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import cloudpanel_site


class CloudPanelSiteUserTests(unittest.TestCase):
    def _ok(self):
        return mock.patch.object(
            cloudpanel_site.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["runuser"], 0, stdout="", stderr=""),
        )

    def test_permissions_run_as_site_user(self) -> None:
        with self._ok() as run:
            cloudpanel_site.reset_permissions("alice", "/home/alice/htdocs/example.com")
        args = run.call_args.args[0]
        self.assertEqual(args[:5], ["runuser", "-u", "alice", "--", "clpctl"])
        self.assertEqual(args[5], "system:permissions:reset")
        self.assertIn("--directories=770", args)
        self.assertIn("--files=660", args)

    def test_varnish_runs_as_site_user(self) -> None:
        with self._ok() as run:
            cloudpanel_site.purge_varnish("alice", "all")
        args = run.call_args.args[0]
        self.assertEqual(args[2], "alice")
        self.assertEqual(args[5], "varnish-cache:purge")
        self.assertIn("--purge=all", args)

    def test_database_site_user_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as td, self._ok() as run:
            dump = Path(td) / "dump.sql.gz"
            dump.write_bytes(b"dump")
            cloudpanel_site.import_database("alice", "example_db", dump)
        self.assertEqual(run.call_args.args[0][5], "db:import")

    def test_invalid_site_user_fails_before_execution(self) -> None:
        with mock.patch.object(cloudpanel_site.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                cloudpanel_site.purge_varnish("../../root", "all")
        run.assert_not_called()

    def test_failure_does_not_echo_output(self) -> None:
        secret = "private-output"
        with mock.patch.object(
            cloudpanel_site.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["runuser"], 9, stdout=secret, stderr=secret),
        ):
            with self.assertRaises(cloudpanel_site.CloudPanelSiteUserError) as ctx:
                cloudpanel_site.purge_varnish("alice", "all")
        self.assertNotIn(secret, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
