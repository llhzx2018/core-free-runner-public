"""P07-M04 服务器维护与安全: dedicated rc83 package & zero M03 installers."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "packages/p07-system-care"
OLD = BASE / "0.1.0-rc82"
NEW = BASE / "0.1.0-rc83"
INSTALLER = ROOT / "installers/p07-system-care-rc83-isolated.sh"


def git_blob_sha1(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


class IndependentM04Tests(unittest.TestCase):
    def test_new_m04_candidate_has_complete_verified_24_file_manifest(self):
        lines = (NEW / "MANIFEST.gitblob").read_text().strip().splitlines()
        self.assertEqual(len(lines), 24)
        paths = []
        for line in lines:
            match = re.fullmatch(r"([0-9a-f]{40})  ([a-zA-Z0-9._/-]+)", line)
            self.assertIsNotNone(match, line)
            sha, name = match.groups()
            self.assertNotIn("..", Path(name).parts)
            self.assertTrue((NEW / name).is_file(), name)
            self.assertEqual(git_blob_sha1((NEW / name).read_bytes()), sha)
            paths.append(name)
        self.assertEqual(len(set(paths)), len(paths))
        self.assertEqual((NEW / "VERSION").read_text(), "0.1.0-rc83\n")

    def test_m04_main_menu_and_support_no_longer_call_m03(self):
        text = (NEW / "vf-system-care.sh").read_text()
        for forbidden in ("ensure_vfops_tools", "run_vfops_tool",
                          "VFOPS_INSTALLER", "VFOPS_DIR",
                          "VFOPS_BUILD_EXPECTED", "vfops-selfcheck-ui",
                          "vfops-history-ui", "vfops-diagnostics-ui"):
            self.assertNotIn(forbidden, text)
        for own in ("run_action_friendly audit.sh", "selfcheck_local_module",
                    "recent_local_actions", "P07-M04 服务器维护与安全"):
            self.assertIn(own, text)

    def test_old_rc82_is_unchanged_and_new_rc83_has_separate_identity(self):
        old = (OLD / "vf-system-care.sh").read_text()
        self.assertIn("ensure_vfops_tools", old)
        self.assertIn("run_vfops_tool", old)
        self.assertNotEqual(
            git_blob_sha1(old.encode()), git_blob_sha1((NEW / "vf-system-care.sh").read_bytes())
        )
        self.assertEqual((OLD / "VERSION").read_text(), "0.1.0-rc82\n")

    def test_m04_entry_works_in_isolation_without_m03(self):
        script = NEW / "vf-system-care.sh"
        result = subprocess.run(
            ["bash", str(script), "--version"], capture_output=True, text=True,
            timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("服务器维护与安全 0.1.0-rc83", result.stdout)
        contract = subprocess.run(
            ["bash", str(script), "--ui-contract"], capture_output=True, text=True,
            timeout=15, check=False,
        )
        self.assertEqual(contract.returncode, 0, contract.stderr)
        self.assertIn("P07_BEGINNER_ZH_V1", contract.stdout)

    def test_m04_menu_own_selfcheck_without_installed_m03(self):
        result = subprocess.run(
            ["bash", str(NEW / "vf-system-care.sh"), "menu"],
            input="7\n0\n", text=True, capture_output=True, timeout=15, check=False,
            env={**os.environ, "P07_FORCE_INTERACTIVE": "1", "NO_COLOR": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("P07-M04 服务器维护与安全", result.stdout)
        self.assertIn("本模块基础文件与版本检查通过", result.stdout)

    def test_m04_installer_pinned_and_bounded_to_module_root(self):
        source = INSTALLER.read_text()
        self.assertIn("P07-M04", source)
        self.assertIn("'/opt/vfops-modules/m04'", source)
        self.assertIn("MANIFEST_BLOB='f82c9e42297c45a54ec6dc2fc4d705cad316dfce'", source)
        self.assertIn("PIN_REF='3174bdebac97cbf1e2ca1d09038c2616576c518f'", source)
        self.assertIn("flock -x", source)
        self.assertIn("mv -Tf", source)
        for forbidden in ("ensure_server_ops_current", "VFOPS_INSTALLER",
                          "/opt/vf-server-ops", "/usr/local/bin/vfops",
                          "P07_SYSTEM_CARE_ROOT=/opt/vf-system-care"):
            self.assertNotIn(forbidden, source)
        check = subprocess.run(["bash", "-n", str(INSTALLER)],
                               capture_output=True, text=True, timeout=15)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_candidate_rejects_unapproved_action(self):
        result = subprocess.run(
            ["bash", str(INSTALLER), "migrate"], capture_output=True,
            text=True, check=False, timeout=15,
        )
        self.assertEqual(result.returncode, 13)
        self.assertIn("没有运行其他模块", result.stderr)


if __name__ == "__main__":
    unittest.main()
