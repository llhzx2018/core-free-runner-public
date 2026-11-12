"""P07 independent M02 rollback and immutable M03 installer: offline negatives."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
TOOLBOX = ROOT / 'installers/p07-toolbox.sh'

def fn(source, name):
    a = re.search(r'^' + re.escape(name) + r'\(\) \{\s*$', source, re.M)
    if not a:
        raise AssertionError(name)
    z = re.search(r'^}\s*$', source[a.end():], re.M)
    if not z:
        raise AssertionError(name + ' end')
    return source[a.start():a.end() + z.end()]

class M02CrossVersionRollback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='p07-m02-upgrade-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base/'m02'
        (self.root/'releases').mkdir(parents=True)
        self.siblings = {}
        for key in ('m01','m03','m04','m05'):
            location=self.base/key
            location.mkdir()
            (location/'KEEP').write_text(key + ':UNCHANGED')
            self.siblings[key]=location/'KEEP'
        self.before=self.sibling_hashes()
        self.first, self.second='2.2.0-rc11','2.2.0-rc12'
        for build in (self.first,self.second):
            folder=self.root/'releases'/build
            folder.mkdir()
            script=folder/'vps-audit.sh'
            script.write_text('#!/bin/bash\ncase "$1" in\n'
                              '  --version) echo V2.2.0 ;;\n'
                              f'  --build-id) echo {build} ;;\n'
                              '  *) exit 13 ;;\nesac\n')
            script.chmod(0o755)
            (folder/'MANIFEST.sha256').write_text(
                hashlib.sha256(script.read_bytes()).hexdigest()+'  vps-audit.sh\n')
        (self.root/'current').symlink_to('releases/'+self.second)
        source=TOOLBOX.read_text(encoding='utf-8')
        funcs=[fn(source,x) for x in ('sha256_file','m02_verified_current','rollback_m02_current')]
        # Only the test copy is rewritten to a disposable path and unprivileged id.
        funcs[-1]=funcs[-1].replace('/opt/vfops-modules',str(self.base)).replace('$(id -u)','0')
        self.runner=self.base/'rollback-test.sh'
        self.runner.write_text('#!/bin/bash\nset -Eeuo pipefail\n'
            +'M02_ROOT='+shlex.quote(str(self.root))+'\n'
            +'VPS_AUDIT_BUILD_EXPECTED=2.1.0-rc7-field\n'
            +'VPS_AUDIT_EXPECTED=V2.1.0\n'
            +'VPS_AUDIT_SHA256=d1846e751bba5c860c623e3db26641908e27ca43b39cf37016758853b65a952d\n'
            +'say() { printf "%s\\n" "$*"; }\n'
            +'\n'.join(funcs)+'\nrollback_m02_current "$1" "$2"\n')

    def sibling_hashes(self):
        return {x:hashlib.sha256(p.read_bytes()).hexdigest() for x,p in self.siblings.items()}

    def invoke(self, build, confirm):
        return subprocess.run(['bash',str(self.runner),build,confirm],capture_output=True,text=True,timeout=20)

    def test_rollback_and_forward_across_valid_builds_only_m02_changes(self):
        for build in (self.first,self.second,self.first):
            p=self.invoke(build,'P07-M02:'+build)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(os.readlink(self.root/'current'),'releases/'+build)
            self.assertEqual(self.sibling_hashes(),self.before)

    def test_invalid_confirmation_missing_build_and_tamper_are_rejected(self):
        pointer=os.readlink(self.root/'current')
        for build,confirm in ((self.first,'P07-M02:wrong'),('missing','P07-M02:missing'),('../m03','P07-M02:../m03')):
            self.assertEqual(self.invoke(build,confirm).returncode,13)
            self.assertEqual(os.readlink(self.root/'current'),pointer)
        file=self.root/'releases'/self.first/'vps-audit.sh'
        file.write_bytes(file.read_bytes()+b'\n# tamper\n')
        self.assertEqual(self.invoke(self.first,'P07-M02:'+self.first).returncode,13)
        self.assertEqual(os.readlink(self.root/'current'),pointer)
        self.assertEqual(self.sibling_hashes(),self.before)

    def test_symlink_manifest_is_rejected(self):
        manifest=self.root/'releases'/self.first/'MANIFEST.sha256'
        manifest.unlink()
        manifest.symlink_to(self.siblings['m01'])
        self.assertEqual(self.invoke(self.first,'P07-M02:'+self.first).returncode,13)
        self.assertEqual(os.readlink(self.root/'current'),'releases/'+self.second)
        self.assertEqual(self.sibling_hashes(),self.before)

class M03ImmutableInstaller(unittest.TestCase):
    def test_pinned_source_and_no_execution_if_corrupt(self):
        source=TOOLBOX.read_text(encoding='utf-8')
        self.assertRegex(source,r'VF_SERVER_OPS_INSTALLER_REF="[a-f0-9]{40}"')
        self.assertRegex(source,r'VF_SERVER_OPS_INSTALLER_BLOB="[a-f0-9]{40}"')
        body=fn(source,'ensure_server_ops_current')
        self.assertIn('p07_git_blob_sha1 "$tmp"',body)
        self.assertLess(body.index('p07_git_blob_sha1 "$tmp"'), body.index('P07_TOOLBOX_PARENT=1 P07_NO_EXEC=1 bash "$tmp"'))
        with tempfile.TemporaryDirectory(prefix='p07-m03-immutable-') as t:
            folder=Path(t)
            marker=folder/'MALICIOUS_EXECUTION'
            fake_download='#!/bin/bash\ntouch '+shlex.quote(str(marker))+'\n'
            script=folder/'test.sh'
            body=body.replace('/opt/vf-server-ops',str(folder/'no-current'))
            script.write_text('#!/bin/bash\nset -Eeuo pipefail\n'
                +'VF_SERVER_OPS_INSTALLER=https://example.invalid/installer\n'
                +'VF_SERVER_OPS_INSTALLER_BLOB='+('0'*40)+'\n'
                +'C_RED=""; C_RESET=""\n'
                +'say() { printf "%s\\n" "$*"; }\n'
                +'m03_verified_current() { return 1; }\n'
                +'p07_git_blob_sha1() { echo wrong; }\n'
                +'curl() { [[ "$3" == "-o" ]] || return 1; printf "%s" '
                +shlex.quote(fake_download)+' > "$4"; }\n'
                +body+'\nensure_server_ops_current\n')
            p=subprocess.run(['bash',str(script)],capture_output=True,text=True,timeout=15)
            self.assertEqual(p.returncode,6,p.stderr)
            self.assertFalse(marker.exists())

if __name__=='__main__': unittest.main()
