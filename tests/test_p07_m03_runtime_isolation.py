"""P07-M03 网站与数据: actual installer uses its own root, never siblings.

This deliberately installs only the pinned public *stable* M03 runtime in a
disposable temporary folder. It does not start migration or touch CloudPanel.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "installers/p07-final.sh"


class M03OwnInstallationBoundary(unittest.TestCase):
    def test_m03_installer_has_only_module_root_and_rollback_paths(self):
        s = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"', s)
        self.assertIn('PREVIOUS_DIR="${P07_PREVIOUS_DIR:-/opt/vf-server-ops.previous}"', s)
        self.assertIn('BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"', s)
        for foreign in ("vf-node.sh", "/opt/vf-system-care",
                        "/opt/vfops-modules/m01", "/opt/vfops-modules/m02",
                        "/opt/vfops-modules/m04", "/opt/vfops-modules/m05",
                        "p07-toolbox.sh"):
            self.assertNotIn(foreign, s)
        self.assertIn("verify_installed_current", s)
        self.assertIn("OLD_MOVED=1", s)
        self.assertIn("NEW_INSTALLED=1", s)
        self.assertIn("恢复安装前的旧版本目录", s)

    @unittest.skipUnless(os.getenv("P07_M03_DISPOSABLE_RUNNER")=="1",
                         "hosted disposable runner only")
    def test_exact_stable_m03_install_and_idempotent_use_keep_four_siblings(self):
        with tempfile.TemporaryDirectory(prefix="p07-m03-isolated-") as work:
            root=Path(work)
            modules=root/"modules"
            modules.mkdir()
            markers={}
            for name in ("m01","m02","m04","m05"):
                loc=modules/name
                loc.mkdir()
                p=loc/"BUILD_ID"
                p.write_text(name + "-UNCHANGED")
                markers[name]=p
            before={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in markers.items()}
            target=modules/"m03"
            previous=modules/"m03.previous"
            entry=root/"bin/vfops"
            entry.parent.mkdir()
            env={**os.environ,
                 "P07_INSTALL_DIR":str(target),
                 "P07_PREVIOUS_DIR":str(previous),
                 "P07_BIN_LINK":str(entry),
                 "P07_ALLOW_NONROOT":"1",
                 "P07_NO_EXEC":"1",
                 "NO_COLOR":"1"}
            for attempt in range(2):
                p=subprocess.run(["bash",str(INSTALLER)],env=env,capture_output=True,
                                 text=True,timeout=240,check=False)
                self.assertEqual(p.returncode,0,
                                 "M03 attempt %s: %s"%(attempt,p.stderr[-1500:]))
            self.assertEqual((target/"BUILD_ID").read_text().strip(),
                             "0.1.0-release115")
            self.assertFalse(previous.exists() or previous.is_symlink())
            v=subprocess.run(["bash",str(target/"bin/vfops-user"),"--build-id"],
                             env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(v.returncode,0,v.stderr)
            self.assertIn("0.1.0-release115",v.stdout)
            self.assertEqual(before,{n:hashlib.sha256(p.read_bytes()).hexdigest()
                                     for n,p in markers.items()})
            # Corrupt only the *disposable* M03 build identity: installer should
            # refuse an unreachable manifest without swapping its private root.
            (target/"BUILD_ID").write_text("synthetic-corrupt\n")
            fail_env={**env,"P07_PUBLIC_ROOT":"https://127.0.0.1:1"}
            failed=subprocess.run(["bash",str(INSTALLER)],env=fail_env,
                                  capture_output=True,text=True,timeout=75)
            self.assertNotEqual(failed.returncode,0)
            self.assertEqual((target/"BUILD_ID").read_text().strip(),"synthetic-corrupt")
            self.assertFalse(previous.exists() or previous.is_symlink())
            self.assertEqual(before,{n:hashlib.sha256(p.read_bytes()).hexdigest()
                                     for n,p in markers.items()})


if __name__=="__main__":
    unittest.main()
