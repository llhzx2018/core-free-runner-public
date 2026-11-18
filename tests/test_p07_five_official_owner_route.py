"""Owner-choice public Toolbox route: real isolated old→new, tamper and five-module safety.

No CloudPanel, external network, Owner server, or GitHub write. Official exact ZIP
bytes are deterministically reproduced by the already-published bundle builder.
"""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
ROUTE=ROOT/"installers/p07-three-ux-owner-route.py"
INSTALLER=ROOT/"installers/p07-three-ux-atomic.py"
BUILDER=ROOT/"scripts/build_p07_ux_three_release_candidates.py"
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
route=load("p07_official_owner_route",ROUTE)
atomic=load("p07_pinned_atomic",INSTALLER)
builder=load("p07_pinned_builder",BUILDER)
class TTY(io.StringIO):
    def isatty(self):return True

class FiveModuleOwnerRoute(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="p07-five-owner-route-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.modules=self.root/"five"
        self.modules.mkdir()
        self.oldbase=route.BASE
        self.atomic_base=atomic.BASE
        route.BASE=self.modules
        atomic.BASE=self.modules
        self.addCleanup(lambda:setattr(route,"BASE",self.oldbase))
        self.addCleanup(lambda:setattr(atomic,"BASE",self.atomic_base))
        self.zips=self.root/"official"
        self.zips.mkdir()
        self.archive={}
        for module,name,build,entry,maker in builder.MODULES:
            p=self.zips/f"{module}-{build}.zip"
            files=builder.build_payload(module,name,build,entry,maker)
            digest=builder.output_zip(p,module,files)
            self.assertEqual(digest,route.MODULES[module]["sha"])
            self.archive[module]=p
        with patch.object(route,"fetch",side_effect=self.fake_fetch), \
             patch.object(route,"get_installer",return_value=atomic):
            pass
        for mod in ("m01","m02","m03","m04","m05"):
            d=self.modules/mod
            d.mkdir()
            (d/"CANARY").write_text("keep-"+mod)
        self.mock_fetch=patch.object(route,"fetch",side_effect=self.fake_fetch)
        self.mock_get=patch.object(route,"get_installer",return_value=atomic)
        self.mock_fetch.start()
        self.mock_get.start()
        self.addCleanup(self.mock_get.stop)
        self.addCleanup(self.mock_fetch.stop)

    def fake_fetch(self,url,dest,expected,kind="sha256"):
        self.assertEqual(kind,"sha256")
        modules=[m for m,c in route.MODULES.items() if url.endswith("/"+c["filename"])]
        self.assertEqual(len(modules),1,url)
        mod=modules[0]
        data=self.archive[mod].read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),expected)
        dest.write_bytes(data)

    def before(self):
        return {m:(self.modules/m/"CANARY").read_bytes()
                for m in ("m01","m02","m03","m04","m05")}

    def old_install(self,module):
        config=route.MODULES[module]
        home=self.modules/config["slot"]
        old=home/"releases"/config["previous"]
        old.mkdir(parents=True)
        if module in ("P07-M01","P07-M04"):
            src=(ROOT/"packages/p07-network-node/0.1.0-ux2"
                 if module=="P07-M01" else ROOT/"packages/p07-system-care/0.1.0-ux4")
            manifest=("MANIFEST.sha256" if module=="P07-M01" else "MANIFEST.gitblob")
            for line in (src/manifest).read_text().splitlines():
                digest,name=line.split("  ",1)
                dest=old/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(src/name,dest)
            shutil.copy2(src/manifest,old/manifest)
        else:
            src=ROOT/"experiments/p07-vps-audit-v21-ux2.sh"
            data=src.read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),
                "18a7a7dc401772fda7344845b952bc307a46f05443d086ec5e38a1954308587d")
            (old/"vps-audit.sh").write_bytes(data)
            (old/"MANIFEST.sha256").write_text(
                "18a7a7dc401772fda7344845b952bc307a46f05443d086ec5e38a1954308587d  vps-audit.sh\n")
        (home/"current").symlink_to("releases/"+config["previous"])
        atomic.verify_saved(old,config["previous"],module)
        return home,old

    def invoke(self,module,answer="y\n"):
        stdin=TTY(answer)
        stdout=TTY()
        with patch.object(route.sys,"argv",[str(ROUTE),module]), \
             patch.object(route.sys,"stdin",stdin),patch.object(route.sys,"stdout",stdout), \
             patch.object(route.os,"geteuid",return_value=0), \
             patch.object(atomic.os,"geteuid",return_value=0):
            return route.main()

    def test_main_menu_has_all_three_explicit_module_targets(self):
        self.assertEqual(set(route.MODULES),{"P07-M01","P07-M02","P07-M04"})
        for module in route.MODULES:
            self.assertIn("ONLY",module+"_ONLY")
        self.assertIn("three-ux-owner-route.py",(ROOT/"installers/p07-toolbox.sh").read_text())

    def test_readonly_immutable_source_pins(self):
        self.assertEqual(hashlib.sha1(b"blob "+str(INSTALLER.stat().st_size).encode()+b"\0"+
                    INSTALLER.read_bytes()).hexdigest(),route.INSTALLER_GIT_BLOB)
        self.assertEqual(len(route.MODULES),3)
        for module,config in route.MODULES.items():
            self.assertRegex(config["sha"],r"^[0-9a-f]{64}$")
            self.assertRegex(config["meta"],r"^[0-9a-f]{64}$")

    def test_write_confirmation_y_then_new_module_verified(self):
        for module in route.MODULES:
            with self.subTest(module=module):
                home,old=self.old_install(module)
                before=self.before()
                self.assertEqual(self.invoke(module),0)
                self.assertEqual(os.readlink(home/"current"),"releases/"+route.MODULES[module]["version"])
                route.verified_new(home,module,route.MODULES[module])
                self.assertEqual(self.before(),before)
                self.assertEqual(self.invoke(module),0)

    def test_cancel_does_not_change_old_module(self):
        for module in route.MODULES:
            with self.subTest(module=module):
                home,old=self.old_install(module)
                before=self.before()
                with self.assertRaises(route.Blocked):
                    self.invoke(module,answer="n\n")
                self.assertEqual(os.readlink(home/"current"),"releases/"+route.MODULES[module]["previous"])
                self.assertEqual(self.before(),before)

    def test_invalid_or_eof_confirmation_cannot_upgrade_any_module(self):
        for answer in ("x\n", ""):
            for module in route.MODULES:
                with self.subTest(answer=repr(answer), module=module):
                    home, _ = self.old_install(module)
                    before = self.before()
                    with self.assertRaisesRegex(route.Blocked, "取消|输入|未确认"):
                        self.invoke(module, answer=answer)
                    self.assertEqual(os.readlink(home / "current"),
                                     "releases/" + route.MODULES[module]["previous"])
                    self.assertEqual(self.before(), before)

    def test_failure_rejects_tampered_old_and_keeps_four_siblings(self):
        for module in route.MODULES:
            with self.subTest(module=module):
                home,old=self.old_install(module)
                before=self.before()
                victim=(old/route.MODULES[module]["entry"])
                victim.write_bytes(victim.read_bytes()+b"# tampered")
                with self.assertRaises(atomic.Rejected):
                    self.invoke(module)
                self.assertEqual(os.readlink(home/"current"),"releases/"+route.MODULES[module]["previous"])
                self.assertEqual(self.before(),before)

    def test_tampered_new_release_is_rejected_before_launch(self):
        module="P07-M01"
        home,old=self.old_install(module)
        self.assertEqual(self.invoke(module),0)
        entry=home/"current/vf-node.sh"
        entry.write_bytes(entry.read_bytes()+b"# tampered")
        with self.assertRaises(route.Blocked):
            self.invoke(module)
        self.assertEqual(os.readlink(home/"current"),"releases/"+route.MODULES[module]["version"])

    def test_non_tty_upgrade_rejects_without_writes(self):
        module="P07-M04"
        home,old=self.old_install(module)
        stdin=io.StringIO("y\n")
        stdout=io.StringIO()
        with patch.object(route.sys,"argv",[str(ROUTE),module]), \
             patch.object(route.sys,"stdin",stdin),patch.object(route.sys,"stdout",stdout):
            with self.assertRaises(route.Blocked):
                route.main()
        self.assertEqual(os.readlink(home/"current"),"releases/"+route.MODULES[module]["previous"])

if __name__=="__main__":unittest.main()
