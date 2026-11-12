"""P07 Toolbox keeps independent future module releases instead of downgrading.

No VPS, GitHub network or root required. Fixtures model already signed &
installed per-module releases with their own complete local manifests.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOLBOX=ROOT/"installers/p07-toolbox.sh"


def fn(source,name):
    a=re.search(r"^"+re.escape(name)+r"\(\) \{\s*$",source,re.M)
    if not a: raise AssertionError(name)
    b=re.search(r"^}\s*$",source[a.end():],re.M)
    if not b: raise AssertionError(name+" end")
    return source[a.start():a.end()+b.end()]


def git_blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()


class InstalledIndependentBuilds(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=TOOLBOX.read_text()
        self.releases={}

        node=self.root/"m01/releases/0.1.0-rc99"
        (node/"lib").mkdir(parents=True)
        p={"VERSION":b"0.1.0-rc99\n",
           "vf-node.sh":b"#!/bin/bash\necho 'VF Network Node 0.1.0-rc99'\n"}
        for i in range(8):
            p["lib/file%02d.sh"%i]=(str(i)+"\n").encode()
        self._manifest(node,p,"MANIFEST.sha256","sha256")
        (node.parent.parent/"current").symlink_to("releases/0.1.0-rc99")

        vps=self.root/"m02/releases/2.2.0-rc99"
        vps.mkdir(parents=True)
        audit=b"#!/bin/bash\ncase \"$1\" in\n --version) echo 'V2.2.0';;\n --build-id) echo '2.2.0-rc99';;\nesac\n"
        (vps/"vps-audit.sh").write_bytes(audit)
        (vps/"vps-audit.sh").chmod(0o755)
        (vps/"MANIFEST.sha256").write_text(hashlib.sha256(audit).hexdigest()+"  vps-audit.sh\n")
        (vps.parent.parent/"current").symlink_to("releases/2.2.0-rc99")

        care=self.root/"m04/releases/0.1.0-rc99"
        (care/"lib").mkdir(parents=True)
        c={"VERSION":b"0.1.0-rc99\n",
           "vf-system-care.sh":b"#!/bin/bash\nif [[ \"$1\" == '--version' ]]; then echo '服务器维护与安全 0.1.0-rc99'; else echo P07_BEGINNER_ZH_V1; fi\n"}
        for i in range(18):
            c["lib/file%02d.py"%i]=(str(i)+"\n").encode()
        self._manifest(care,c,"MANIFEST.gitblob","blob")
        (care.parent.parent/"current").symlink_to("releases/0.1.0-rc99")
        self.releases.update(M01=node,M02=vps,M04=care)

    def _manifest(self,where,payload,manifest,algorithm):
        for path,data in payload.items():
            loc=where/path
            loc.parent.mkdir(parents=True,exist_ok=True)
            loc.write_bytes(data)
            if path.endswith(".sh"): loc.chmod(0o755)
        hashes=[]
        for name,data in sorted(payload.items()):
            sha=hashlib.sha256(data).hexdigest() if algorithm=="sha256" else git_blob(data)
            hashes.append(sha+"  "+name)
        (where/manifest).write_text("\n".join(hashes)+"\n")

    def run_check(self,which,ensure=False):
        names={"M01":("m01_verified_current","ensure_m01_current"),
               "M02":("m02_verified_current","ensure_m02_current"),
               "M04":("m04_verified_current","ensure_m04_current")}
        source=self.source
        vars=(
            "M01_ROOT="+shlex.quote(str(self.root/"m01")),
            'M01_RUNTIME="$M01_ROOT/current/vf-node.sh"',
            "M01_MANIFEST_SHA256=" + shlex.quote("1ca3dc95a5cc6e5aa35c9b7ead415d3b6ea6c6eb9e8307a76310d146ab53c47f"),
            'VF_NODE_EXPECTED="0.1.0-rc13"',
            "M02_ROOT="+shlex.quote(str(self.root/"m02")),
            'VPS_AUDIT_BUILD_EXPECTED="2.1.0-rc7-field"',
            'VPS_AUDIT_SHA256="d1846e751bba5c860c623e3db26641908e27ca43b39cf37016758853b65a952d"',
            "M04_ROOT="+shlex.quote(str(self.root/"m04")),
            'M04_RUNTIME="$M04_ROOT/current/vf-system-care.sh"',
            'M04_BUILD_EXPECTED="0.1.0-rc83"',
            'M04_UI_BLOB="f140f1158351f9dce2e9f9159611af57047424b1"',
            "C_RED=''; C_RESET=''",
        )
        functions=["sha256_file","p07_git_blob_sha1",
                   *[n for pair in names.values() for n in pair]]
        action=names[which][1 if ensure else 0]
        script=self.root/"readback.sh"
        script.write_text(
            "#!/bin/bash\nset -Eeuo pipefail\n"
            + "\n".join(vars)
            + "\nsay() { :; }\n"
            + "\n".join(fn(source,name) for name in functions)
            + "\n"+action+"\n"
        )
        return subprocess.run(["bash",str(script)],capture_output=True,text=True,timeout=20)

    def test_valid_newer_m01_m02_m04_versions_are_accepted_without_toolbox_upgrade(self):
        for module in ("M01","M02","M04"):
            with self.subTest(module=module):
                self.assertEqual(self.run_check(module).returncode,0)
                self.assertEqual(self.run_check(module,ensure=True).returncode,0)

    def test_tampered_newer_release_is_refused_not_downgraded(self):
        paths={"M01":self.releases["M01"]/"lib/file00.sh",
               "M02":self.releases["M02"]/"vps-audit.sh",
               "M04":self.releases["M04"]/"lib/file00.py"}
        for module,path in paths.items():
            before=path.read_bytes()
            path.write_bytes(before+b"\n# tampered\n")
            with self.subTest(module=module):
                self.assertNotEqual(self.run_check(module).returncode,0)
                self.assertEqual(self.run_check(module,ensure=True).returncode,13)
                self.assertIn(b"# tampered",path.read_bytes())
            path.write_bytes(before)

    def test_m03_own_manifest_never_reinstalls_over_unverified_module(self):
        s=self.source
        self.assertIn("m03_verified_current() {",s)
        self.assertIn("m03_verified_current; then",s)
        self.assertIn("拒绝降级覆盖",s)
        self.assertIn("MODULE_MANIFEST.json",s)
        self.assertIn("m05_verified_current",s)


if __name__=="__main__":
    unittest.main()
