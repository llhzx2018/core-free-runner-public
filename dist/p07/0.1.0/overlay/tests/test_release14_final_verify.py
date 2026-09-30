from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import diagnostics
import package_core


class Release14FinalVerifyTests(unittest.TestCase):
    def test_stable_verify_accepts_only_after_two_consecutive_passes(self) -> None:
        fail = {
            "schema": package_core.VERIFY_SCHEMA,
            "status": "FAIL",
            "checksum_files_checked": 3,
            "failures": ["archive:invalid"],
        }
        passed = {
            "schema": package_core.VERIFY_SCHEMA,
            "status": "PASS",
            "checksum_files_checked": 3,
            "failures": [],
        }
        with patch.object(package_core, "verify_package", side_effect=[fail, passed, passed]) as mocked:
            result = package_core.verify_package_stable(
                Path("/synthetic"),
                attempts=4,
                delay_seconds=0,
                consecutive_passes=2,
            )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(mocked.call_count, 3)

    def test_stable_verify_fails_closed_when_failure_persists(self) -> None:
        fail = {
            "schema": package_core.VERIFY_SCHEMA,
            "status": "FAIL",
            "checksum_files_checked": 4,
            "failures": ["mysql:example.sql.gz"],
        }
        with patch.object(package_core, "verify_package", return_value=fail) as mocked:
            result = package_core.verify_package_stable(
                Path("/synthetic"),
                attempts=4,
                delay_seconds=0,
                consecutive_passes=2,
            )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(mocked.call_count, 4)

    def test_failure_categories_are_specific_and_sanitized(self) -> None:
        cases = {
            ("checksum:mysql/example.sql.gz",): "MYSQL_SNAPSHOT_CHANGED",
            ("checksum:sqlite/app.sqlite",): "SQLITE_SNAPSHOT_CHANGED",
            ("checksum:files/site.tar.gz",): "SITE_SNAPSHOT_CHANGED",
            ("checksum:metadata/vhost/site.conf",): "METADATA_SNAPSHOT_CHANGED",
            ("checksum:manifest.json",): "MANIFEST_CHANGED",
            ("checksum:other.bin",): "PACKAGE_FILE_CHANGED",
            ("mysql:example.sql.gz",): "MYSQL_SNAPSHOT_INVALID",
            ("sqlite:app.sqlite",): "SQLITE_SNAPSHOT_INVALID",
            ("archive:empty",): "SITE_ARCHIVE_EMPTY",
            ("archive:invalid",): "SITE_ARCHIVE_INVALID",
            ("checksums:missing",): "CHECKSUM_INDEX_MISSING",
            ("checksums:invalid-line",): "CHECKSUM_INDEX_INVALID",
            ("symlink:metadata/vhost/site.conf",): "EXTERNAL_LINK_FOUND",
        }
        for failures, expected in cases.items():
            with self.subTest(failures=failures):
                self.assertEqual(
                    package_core.verification_failure_code(list(failures)),
                    expected,
                )

    def test_diagnostics_prefers_structured_post_commit_category(self) -> None:
        stderr = (
            "ERROR: backup failed post-commit fresh verification "
            "[SITE_ARCHIVE_INVALID]: archive:invalid"
        )
        self.assertEqual(diagnostics.infer_blocker(stderr), "SITE_ARCHIVE_INVALID")

    def test_beginner_ui_explains_site_archive_failure_without_machine_token(self) -> None:
        script = textwrap.dedent(
            f"""\
            source {ROOT / 'lib' / 'terminal_ui.sh'}
            ui_safe_diagnostic 'VFOPS_DIAGNOSTIC_V1 stage=BACKUP error_class=BACKUP_ERROR blocker=SITE_ARCHIVE_INVALID cleanup=NOT_REPORTED exit_code=4'
            """
        )
        proc = subprocess.run(
            ["bash", "-c", script],
            text=True,
            capture_output=True,
            check=False,
            env={"NO_COLOR": "1", "PATH": "/usr/bin:/bin"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("阶段：备份", proc.stdout)
        self.assertIn("原因：网站文件压缩包无法完整读取", proc.stdout)
        self.assertNotIn("SITE_ARCHIVE_INVALID", proc.stdout)
        self.assertNotIn("原因代码", proc.stdout)


if __name__ == "__main__":
    unittest.main()
