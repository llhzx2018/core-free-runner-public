"""P07-M02 服务器性能检测 · independent immutable and atomic module tests."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLBOX = ROOT / "installers/p07-toolbox.sh"


def source() -> str:
    return TOOLBOX.read_text(encoding="utf-8")


class M02IndependentTests(unittest.TestCase):
    def test_m02_has_private_root_and_sha256_pinned_exact_build(self):
        s = source()
        self.assertIn('M02_ROOT="/opt/vfops-modules/m02"', s)
        self.assertRegex(s, r'VPS_AUDIT_SHA256="[a-f0-9]{64}"')
        self.assertIn('VPS_AUDIT_BUILD_EXPECTED="2.1.0-rc7-field"', s)
        self.assertIn("flock -x", s)
        self.assertIn('mv -Tf -- "$link" "$current"', s)
        self.assertIn('m02_verified_current', s)

    def test_m02_install_code_never_calls_other_module_installers(self):
        s = source()
        part = s[s.index("m02_verified_current() {"):s.index("local_server_ops_version() {")]
        self.assertIn('"$M02_ROOT/current/vps-audit.sh"', part)
        for forbidden in ("ensure_server_ops_current",
                          "ensure_system_care_current", "VF_NODE_INSTALLER",
                          "SYSTEM_CARE_INSTALLER", "M05_RUNTIME",
                          "/opt/vf-server-ops", "/opt/vf-system-care",
                          "/opt/vf-network-node"):
            self.assertNotIn(forbidden, part)

    def test_syntax(self):
        p = subprocess.run(["bash", "-n", str(TOOLBOX)],
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(p.returncode, 0, p.stderr)

    @unittest.skipUnless(os.getenv("P07_M02_HOSTED_NATIVE_TEST") == "1",
                         "only disposable, dedicated hosted runner root")
    def test_native_first_install_no_other_module_writes_and_failed_reuse(self):
        # Hosted runner only, no real owner VPS or production directories.
        self.assertEqual(os.geteuid(), 0)
        with tempfile.TemporaryDirectory(prefix="p07-m02-standalone-") as base:
            root = Path(base)
            module_root = root / "modules"
            module_root.mkdir()
            markers = {}
            for name in ("m01", "m03", "m04", "m05"):
                folder = module_root / name
                folder.mkdir()
                marker = folder / "BUILD_ID"
                marker.write_text(name + "-UNCHANGED")
                markers[name] = marker
            original = {key: hashlib.sha256(m.read_bytes()).hexdigest()
                        for key, m in markers.items()}
            t = source()
            settings = "\n".join(line for line in t.splitlines()
                                 if re.match(r'^VPS_AUDIT_(PUBLIC|EXPECTED|BUILD_EXPECTED|URL|SHA256)=', line))
            frompos = t.index("sha256_file() {")
            until = t.index("local_server_ops_version() {", frompos)
            functions = t[frompos:until]
            harness = root / "run.sh"
            harness.write_text(
                "#!/usr/bin/env bash\nset -Eeuo pipefail\n"
                + settings + "\n"
                + "M02_ROOT=" + "'" + str(module_root / "m02") + "'\n"
                + "C_RED=''; C_GREEN=''; C_CYAN=''; C_RESET=''\n"
                + "say() { printf '%s\\n' \"$*\"; }\n"
                + "screen_clear() { :; }\n"
                + functions + "\nensure_m02_current\n"
            )
            for i in range(2):
                proc = subprocess.run(["bash", str(harness)],
                                      capture_output=True, text=True, timeout=90)
                self.assertEqual(proc.returncode, 0, proc.stderr)
            current = module_root / "m02/current"
            self.assertTrue(current.is_symlink())
            self.assertEqual(os.readlink(current), "releases/2.1.0-rc7-field")
            exact = (module_root / "m02/releases/2.1.0-rc7-field/vps-audit.sh")
            self.assertTrue(exact.is_file())
            self.assertEqual({key: hashlib.sha256(m.read_bytes()).hexdigest()
                              for key, m in markers.items()}, original)
            with exact.open("ab") as handle:
                handle.write(b"\n# corrupted test fixture\n")
            bad = subprocess.run(["bash", str(harness)],
                                 capture_output=True, text=True, timeout=20)
            self.assertEqual(bad.returncode, 13)
            self.assertEqual(os.readlink(current), "releases/2.1.0-rc7-field")
            self.assertEqual({key: hashlib.sha256(m.read_bytes()).hexdigest()
                              for key, m in markers.items()}, original)


if __name__ == "__main__":
    unittest.main()
