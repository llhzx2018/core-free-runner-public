"""P07-M03 网站与数据: never delete rollback snapshot or preexisting stage.

Safe sandbox test: all paths are disposable, no network or CloudPanel action.
"""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "installers/p07-final.sh"


class M03PreviousSnapshotProtection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.current = self.root / "m03"
        self.current.mkdir()
        (self.current / "BUILD_ID").write_text("0.1.0-release115\n")
        self.previous = self.root / "m03.previous"
        self.stage = self.root / "m03.new"
        self.link = self.root / "vfops"
        self.sibling = self.root / "m04"
        self.sibling.mkdir()
        (self.sibling / "BUILD_ID").write_text("M04_UNCHANGED")
        self.env = {
            **os.environ,
            "P07_INSTALL_DIR": str(self.current),
            "P07_PREVIOUS_DIR": str(self.previous),
            "P07_BIN_LINK": str(self.link),
            "P07_ALLOW_NONROOT": "1",
            "P07_NO_EXEC": "1",
            "NO_COLOR": "1",
        }

    def invoke(self):
        return subprocess.run(
            ["bash", str(SCRIPT)], env=self.env,
            capture_output=True, text=True, timeout=15)

    def assert_preserved(self):
        self.assertEqual((self.current / "BUILD_ID").read_text(),
                         "0.1.0-release115\n")
        self.assertEqual((self.sibling / "BUILD_ID").read_text(),
                         "M04_UNCHANGED")

    def test_existing_previous_backup_is_never_deleted(self):
        self.previous.mkdir()
        (self.previous / "OWNER_BACKUP").write_text("important original")
        p = self.invoke()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("存在上次升级的恢复目录", p.stderr)
        self.assertEqual((self.previous / "OWNER_BACKUP").read_text(),
                         "important original")
        self.assert_preserved()

    def test_symlink_to_other_module_is_refused_not_followed(self):
        self.previous.symlink_to(self.sibling, target_is_directory=True)
        p = self.invoke()
        self.assertNotEqual(p.returncode, 0)
        self.assertTrue(self.previous.is_symlink())
        self.assert_preserved()

    def test_old_stage_is_never_cleared(self):
        self.stage.mkdir()
        (self.stage / "OWNER_STAGED").write_text("unrelated")
        p = self.invoke()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("目标临时目录已有内容", p.stderr)
        self.assertEqual((self.stage / "OWNER_STAGED").read_text(),
                         "unrelated")
        self.assert_preserved()


if __name__ == "__main__":
    unittest.main()
