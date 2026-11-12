"""P07-M04 unified Toolbox route: independent staged installer, no M03 fallback."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

TOOLBOX = Path(__file__).resolve().parents[1] / "installers/p07-toolbox.sh"


class UnifiedM04Route(unittest.TestCase):
    def test_pinned_installer_and_own_directory(self):
        text = TOOLBOX.read_text()
        self.assertIn("M04_ROOT=\"/opt/vfops-modules/m04\"", text)
        self.assertIn("M04_INSTALLER_BLOB=\"d39cef5d0915a99753d688f10fb1dbe74c0dac98\"", text)
        self.assertIn("M04_BUILD_EXPECTED=\"0.1.0-rc83\"", text)
        self.assertNotIn("ensure_system_care_current", text)
        fn = text[text.index("run_system_care() {"):text.index("\nmain_menu() {")]
        self.assertIn('ensure_m04_current', fn)
        self.assertIn('bash "$M04_RUNTIME" menu', fn)
        self.assertNotIn("ensure_server_ops_current", fn)

    def test_bad_legacy_cross_upgrade_is_rejected_by_scope(self):
        text = TOOLBOX.read_text()
        body = text[text.index("ensure_m04_current() {"):text.index("\nmain_menu() {")]
        for forbidden in ("VF_SERVER_OPS_INSTALLER", "VFOPS_DIR",
                          "ensure_server_ops_current", "P07_SYSTEM_CARE_ROOT",
                          "run_server_init", "VPS_AUDIT_URL"):
            self.assertNotIn(forbidden, body)

    @unittest.skipUnless(os.getenv("P07_M04_HOSTED_NATIVE_TEST") == "1",
                         "only ephemeral root-owned GitHub runner")
    def test_actual_m04_toolbox_candidate_installs_and_reuses_own_runtime(self):
        self.assertEqual(os.geteuid(), 0)
        module = Path("/opt/vfops-modules/m04")
        if module.exists() or module.is_symlink():
            self.fail("disposable runner already has M04; refuse overwrite")
        text = TOOLBOX.read_text()
        defs = "\n".join(l for l in text.splitlines()
                         if re.match(r'^M04_(BUILD_EXPECTED|INSTALLER_URL|INSTALLER_BLOB|UI_BLOB|ROOT|RUNTIME)=', l))
        begin = text.index("p07_git_blob_sha1() {")
        end = text.index("\nmain_menu() {", begin)
        funcs = text[begin:end]
        with tempfile.TemporaryDirectory(prefix="p07-m04-routing-") as work:
            script = Path(work) / "run.sh"
            script.write_text(
                "#!/usr/bin/env bash\nset -Eeuo pipefail\n" + defs + "\n"
                + "C_RED=''; C_RESET=''\n"
                + "say() { printf '%s\\n' \"$*\"; }\n"
                + "screen_clear() { :; }\n"
                + funcs + "\nensure_m04_current\n"
            )
            try:
                for trial in range(2):
                    p = subprocess.run(["bash", str(script)], capture_output=True,
                                       text=True, check=False, timeout=180)
                    self.assertEqual(p.returncode, 0, p.stderr)
                entry = module / "current/vf-system-care.sh"
                self.assertTrue(entry.is_file())
                self.assertEqual(os.readlink(module / "current"), "releases/0.1.0-rc83")
                version = subprocess.run(["bash", str(entry), "--version"],
                                         capture_output=True, text=True, check=False)
                self.assertEqual(version.returncode, 0, version.stderr)
                self.assertIn("0.1.0-rc83", version.stdout)
            finally:
                # The test runner is an ephemeral disposable host, not OWNER VPS.
                subprocess.run(["rm", "-rf", str(module)], check=True, timeout=20)


if __name__ == "__main__":
    unittest.main()
