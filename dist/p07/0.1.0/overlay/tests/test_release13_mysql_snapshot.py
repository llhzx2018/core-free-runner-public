from __future__ import annotations

import gzip
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "lib"))

import diagnostics
import package as package_engine


class Release13ImmutableMysqlSnapshotTests(unittest.TestCase):
    def test_delayed_atomic_cloudpanel_export_becomes_package_owned_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            out = base / "staging" / "mysql"
            out.parent.mkdir(parents=True)
            fake = base / "fake-clpctl"
            fake.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import gzip
                    import os
                    from pathlib import Path
                    import sys
                    import time

                    args = dict(
                        item[2:].split("=", 1)
                        for item in sys.argv[2:]
                        if item.startswith("--") and "=" in item
                    )
                    target = Path(args["file"])
                    target.parent.mkdir(parents=True, exist_ok=True)

                    with gzip.open(target, "wb") as handle:
                        handle.write(b"CREATE TABLE demo(id INT);\\n")

                    pid = os.fork()
                    if pid == 0:
                        # Detach inherited subprocess pipes so the parent clpctl
                        # command can really return while this helper is still alive.
                        for fd in (0, 1, 2):
                            try:
                                os.close(fd)
                            except OSError:
                                pass
                        time.sleep(2.4)
                        replacement = target.with_name(target.name + ".late")
                        with gzip.open(replacement, "wb") as handle:
                            handle.write(
                                b"CREATE TABLE demo(id INT);\\n"
                                b"INSERT INTO demo VALUES (1);\\n"
                            )
                        os.replace(replacement, target)
                        os._exit(0)
                    raise SystemExit(0)
                    """
                ),
                encoding="utf-8",
            )
            fake.chmod(0o700)

            rows = package_engine._export_mysql_via_cloudpanel(
                ["example_prod"], out, str(fake)
            )
            self.assertEqual(rows[0]["method"], "clpctl_db_export_immutable_snapshot")
            exported = out / "example_prod.sql.gz"
            with gzip.open(exported, "rb") as handle:
                payload = handle.read()
            self.assertIn(b"CREATE TABLE demo", payload)
            self.assertIn(b"INSERT INTO demo VALUES (1)", payload)

            # The package file is no longer the path handed to CloudPanel.
            # It must remain byte-stable after the external export workdir is gone.
            digest_before = package_engine._core.sha256_file(exported)
            import time
            time.sleep(0.5)
            digest_after = package_engine._core.sha256_file(exported)
            self.assertEqual(digest_before, digest_after)

    def test_mysql_post_commit_checksum_failure_gets_specific_machine_code(self) -> None:
        stderr = (
            "ERROR: backup failed post-commit fresh verification: "
            "checksum:mysql/example_prod.sql.gz"
        )
        self.assertEqual(
            diagnostics.infer_blocker(stderr),
            "MYSQL_SNAPSHOT_CHANGED",
        )

    def test_beginner_terminal_diagnostic_hides_engineering_tokens(self) -> None:
        script = textwrap.dedent(
            f"""\
            source {ROOT / 'lib' / 'terminal_ui.sh'}
            ui_safe_diagnostic 'VFOPS_DIAGNOSTIC_V1 stage=BACKUP error_class=BACKUP_ERROR blocker=MYSQL_SNAPSHOT_CHANGED cleanup=NOT_REPORTED exit_code=4'
            """
        )
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        proc = subprocess.run(
            ["bash", "-c", script],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("阶段：备份", proc.stdout)
        self.assertIn("原因：MySQL 数据库导出在封存时仍发生变化", proc.stdout)
        self.assertNotIn("BACKUP", proc.stdout)
        self.assertNotIn("MYSQL_SNAPSHOT_CHANGED", proc.stdout)
        self.assertNotIn("原因代码", proc.stdout)


if __name__ == "__main__":
    unittest.main()
