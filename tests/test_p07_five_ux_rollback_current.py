"""Verify current P07 standalone UX rollback paths on disposable directories only."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_p07_five_official_owner_route import atomic,builder,route

ROOT=Path(__file__).resolve().parents[1]
TOOLBOX=ROOT/"installers/p07-toolbox.sh"

def function(src,name):
    marker=name+"() {"
    if src.count(marker)!=1:raise AssertionError("ambiguous function "+name)
    tail=src.split(marker,1)[1]
    if "\n}\n" not in tail:raise AssertionError("no closing brace")
    return marker+tail.split("\n}\n",1)[0]+"\n}\n"

class P07RollbackCurrent(unittest.TestCase):
    def test_current_m02_manifest_and_actual_bidirectional_rollback(self):
        with tempfile.TemporaryDirectory(prefix="p07-m02-verified-") as path:
            base=Path(path)
            root=base/"modules"
            root.mkdir()
            oldbase=atomic.BASE
            self.addCleanup(lambda:setattr(atomic,"BASE",oldbase))
            atomic.BASE=root
            config=route.MODULES["P07-M02"]
            z=base/"new.zip"
            data=builder.build_payload("P07-M02",config["label"],config["version"],
                                       config["entry"],builder.dev.make_m02)
            digest=builder.output_zip(z,"P07-M02",data)
            self.assertEqual(digest,config["sha"])
            old=root/"m02/releases/2.1.1-ux2"
            old.mkdir(parents=True)
            olddata=(ROOT/"experiments/p07-vps-audit-v21-ux2.sh").read_bytes()
            oldsha=hashlib.sha256(olddata).hexdigest()
            (old/"vps-audit.sh").write_bytes(olddata)
            (old/"MANIFEST.sha256").write_text(oldsha+"  vps-audit.sh\n")
            (root/"m02/current").symlink_to("releases/2.1.1-ux2")
            with patch.object(atomic.os,"geteuid",return_value=0):
                atomic.install("P07-M02",z,digest)
            self.assertEqual(os.readlink(root/"m02/current"),"releases/2.1.1-ux3")
            source=TOOLBOX.read_text()
            functions="\n".join(function(source,x) for x in (
                "m02_verified_new_release","m02_verified_current",
                "rollback_m02_current"))
            # Only the hardcoded /opt ownership guard is redirected to our
            # disposable module root; the real rollback logic remains exact.
            functions=functions.replace(
                " -d /opt/vfops-modules && ! -L /opt/vfops-modules",
                " -d "+str(root)+" && ! -L "+str(root))
            preamble="""#!/usr/bin/env bash
set -Eeuo pipefail
id() { echo 0; }
say() { printf '%s\n' "$*"; }
sha256_file() { sha256sum "$1" | awk '{print $1}'; }
"""
            values={
                "M02_ROOT":str(root/"m02"),
                "P07_M02_META_SHA256":config["meta"],
                "VPS_AUDIT_BUILD_EXPECTED":config["version"],
                "VPS_AUDIT_EXPECTED":"V2.1.1",
                "VPS_AUDIT_BOOTSTRAP_BUILD":"2.1.0-rc7-field",
                "VPS_AUDIT_BOOTSTRAP_SHA256":"d1846e751bba5c860c623e3db26641908e27ca43b39cf37016758853b65a952d",
                "VPS_AUDIT_PREVIOUS_BUILD":"2.1.1-ux2",
                "VPS_AUDIT_PREVIOUS_SHA256":oldsha,
                "VPS_AUDIT_LEGACY1_BUILD":"2.1.1-ux1",
                "VPS_AUDIT_LEGACY1_SHA256":"7b083e4cf105d40b04b4cbe898fb6b9e1bb7f1ef3385bc1d20829796f6852013",
            }
            env={**os.environ,**values,"NO_COLOR":"1"}
            def run(cmd):
                p=subprocess.run(["bash","-c",preamble+functions+"\n"+cmd],
                                 capture_output=True,text=True,env=env,timeout=12)
                return p.returncode
            self.assertEqual(run("m02_verified_current"),0)
            self.assertEqual(run("rollback_m02_current 2.1.1-ux2 P07-M02:2.1.1-ux2"),0)
            self.assertEqual(run("m02_verified_current"),0)
            self.assertNotEqual(run("rollback_m02_current 2.1.1-ux3 WRONG"),0)
            self.assertEqual(os.readlink(root/"m02/current"),"releases/2.1.1-ux2")
            self.assertEqual(run("rollback_m02_current 2.1.1-ux3 P07-M02:2.1.1-ux3"),0)
            self.assertEqual(run("m02_verified_current"),0)
            target=root/"m02/current/vps-audit.sh"
            target.write_bytes(target.read_bytes()+b"\n# altered")
            self.assertNotEqual(run("m02_verified_current"),0)
            self.assertNotEqual(run("rollback_m02_current 2.1.1-ux3 P07-M02:2.1.1-ux3"),0)

    def test_m01_and_m04_restore_commands_use_pinned_python_atomic_installer(self):
        script=TOOLBOX.read_text()
        for module,prefix in (("P07-M01","M01"),("P07-M04","M04")):
            with self.subTest(module=module):
                self.assertIn(module+":python3",script)
                expected=("p07_owned_helper "+module+' "$'+prefix+'_INSTALLER_URL" "$'
                          +prefix+'_INSTALLER_BLOB" python3 rollback')
                self.assertIn(expected,script)
                self.assertIn('python3 -B "$tmp" "$module" rollback "$build" --confirm "$confirm"',script)

if __name__=="__main__":unittest.main()
