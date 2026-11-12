"""P07-M01 网络代理节点（V2Ray） unified Toolbox dispatcher isolation."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLBOX = ROOT / "installers/p07-toolbox.sh"


def function_from(text: str, fn: str) -> str:
    p = re.search(r"^" + re.escape(fn) + r"\(\) \{\s*$", text, re.M)
    if p is None:
        raise AssertionError("missing function " + fn)
    closing = re.search(r"^}\s*$", text[p.end():], re.M)
    if closing is None:
        raise AssertionError("missing close for " + fn)
    return text[p.start():p.end() + closing.end()]


class M01UnifiedDispatch(unittest.TestCase):
    def test_only_m01_own_installer_and_own_runtime_are_called(self):
        s = TOOLBOX.read_text(encoding="utf-8")
        self.assertIn('M01_ROOT="/opt/vfops-modules/m01"', s)
        self.assertRegex(s, r'M01_INSTALLER_BLOB="[0-9a-f]{40}"')
        self.assertRegex(s, r'M01_INSTALLER_URL="https://raw.githubusercontent.com/.*/[0-9a-f]{40}/installers/p07-vf-node-independent-rc13.sh"')
        self.assertIn('M01_RUNTIME="$M01_ROOT/current/vf-node.sh"', s)
        segment = s[s.index("m01_verified_current() {"):s.index("sha256_file() {")]
        self.assertIn('bash "$M01_RUNTIME"', segment)
        for foreign in ("ensure_server_ops_current", "ensure_system_care_current",
                        "SYSTEM_CARE_INSTALLER", "VPS_AUDIT_URL", "M05_RUNTIME",
                        "VF_NODE_INSTALLER", "/opt/vf-network-node",
                        "/opt/vf-server-ops", "/opt/vf-system-care"):
            self.assertNotIn(foreign, segment)

    def test_offline_script_syntax(self):
        p = subprocess.run(["bash", "-n", str(TOOLBOX)], capture_output=True,
                           text=True, timeout=15)
        self.assertEqual(p.returncode, 0, p.stderr)

    @unittest.skipUnless(os.getenv("P07_M01_HOSTED_UNIFIED") == "1",
                         "dedicated hosted temporary runner only")
    def test_native_manager_only_install_and_corrupted_release_fail_closed(self):
        self.assertEqual(os.geteuid(), 0)
        modules = Path("/opt/vfops-modules")
        m01 = modules / "m01"
        self.assertFalse(m01.exists() or m01.is_symlink(),
                         "do not touch a pre-existing real module")
        others = {}
        for name in ("m02", "m03", "m04", "m05"):
            folder = modules / name
            self.assertFalse(folder.exists() or folder.is_symlink(),
                             "do not touch a pre-existing sibling")
            folder.mkdir(parents=True)
            marker = folder / "BUILD_ID"
            marker.write_text(name + "-UNCHANGED")
            others[name] = marker
        before = {n: hashlib.sha256(p.read_bytes()).hexdigest()
                  for n, p in others.items()}
        source = TOOLBOX.read_text()
        defs = "\n".join(line for line in source.splitlines() if re.match(
            r"^(M01_|VF_NODE_EXPECTED=)", line
        ))
        funcs = "\n".join(function_from(source, fn) for fn in (
            "sha256_file", "p07_git_blob_sha1",
            "m01_verified_current", "ensure_m01_current"
        ))
        with tempfile.TemporaryDirectory(prefix="p07-m01-unified-test-") as tmp:
            harness = Path(tmp) / "dispatch.sh"
            harness.write_text(
                "#!/usr/bin/env bash\nset -Eeuo pipefail\n"
                + defs + "\n"
                + "C_RED=''; C_RESET=''; C_GREEN=''\n"
                + "say() { printf '%s\\n' \"$*\"; }\n"
                + funcs + "\nensure_m01_current\n"
            )
            try:
                for _ in range(2):
                    p = subprocess.run(["bash", str(harness)], capture_output=True,
                                       text=True, timeout=160)
                    self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(os.readlink(m01 / "current"), "releases/0.1.0-rc13")
                entry = m01 / "current/vf-node.sh"
                result = subprocess.run(["bash", str(entry), "--version"],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(before, {n: hashlib.sha256(p.read_bytes()).hexdigest()
                                          for n, p in others.items()})
                with (m01/"releases/0.1.0-rc13/status.sh").open("ab") as file:
                    file.write(b"\n# synthetic tamper\n")
                failed = subprocess.run(["bash", str(harness)], capture_output=True,
                                        text=True, timeout=45)
                self.assertEqual(failed.returncode, 13, failed.stderr)
                self.assertEqual(before, {n: hashlib.sha256(p.read_bytes()).hexdigest()
                                          for n, p in others.items()})
            finally:
                for path in (m01, *(modules / x for x in others)):
                    subprocess.run(["rm", "-rf", "--", str(path)], timeout=20, check=True)


if __name__ == "__main__":
    unittest.main()
