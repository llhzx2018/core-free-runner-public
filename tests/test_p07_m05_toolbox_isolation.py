"""P07-M05 新服务器初始化 Toolbox: self-owned verified new releases.

Disposable isolated fixtures ONLY. No VPS or private product source required.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
TOOLBOX=HERE/"installers/p07-toolbox.sh"


def function_body(source: str, name: str) -> str:
    start=source.find(name+"() {\n")
    if start<0: raise AssertionError("missing P07 function: "+name)
    end=re.search(r"^}\s*$",source[start:],re.M)
    if end is None: raise AssertionError("unclosed function: "+name)
    return source[start:start+end.end()]


def assert_independent(body: str) -> None:
    for prohibited in ("ensure_server_ops_current","ensure_system_care_current",
                       "server_ops_root","P07_SYSTEM_CARE_ROOT=",
                       "P07_SYSTEM_CARE_ENTRY=",'bash "$init_ui"',
                       "run_server_ops","run_system_care"):
        if prohibited in body:
            raise AssertionError("P07-M05 dispatch invokes unrelated module")
    if ('"$M05_RUNTIME" menu' not in body or
            "ensure_m05_current" not in body):
        raise AssertionError("missing standalone version ownership")


class ToolboxFiveModuleIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.source=TOOLBOX.read_text()
        self.body=function_body(self.source,"run_server_init")
        self.helper=function_body(self.source,"m05_verified_current")
        self.install_helper=function_body(self.source,"ensure_m05_current")
        self.module=self.folder/"m05"
        self.marker=self.folder/"m05-menu-called"

    def module_fixture(self, build="0.1.0-m05-candidate1", actual_version=None):
        if actual_version is None: actual_version=build
        release=self.module/"releases"/build
        (release/"bin").mkdir(parents=True)
        (release/"lib").mkdir(parents=True)
        payload={
            "MODULE_ID":b"P07-M05\n",
            "MODULE_BUILD_ID":(build+"\n").encode(),
            "VERSION":b"0.1.0\n",
            "BUILD_ID":(build+"\n").encode(),
            "bin/vfops-init-ui":b"#!/bin/bash\nexit 0\n",
            "bin/vfops-init-core":b"#!/bin/bash\nexit 0\n",
        }
        for i in range(16):
            payload["lib/fixture%02d.py"%i]=(str(i)+"\n").encode()
        entry=(
            "#!/bin/bash\n"
            "if [[ \"$1\" == '--version' ]]; then echo "
            + shlex.quote("P07-M05 新服务器初始化 "+actual_version)
            + "\nelse echo 'menu' > " + shlex.quote(str(self.marker)) + "\nfi\n"
        ).encode()
        payload["bin/vfops-init-entry"]=entry
        for name,contents in payload.items():
            target=release/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(contents)
            if name.startswith("bin/"): target.chmod(0o755)
        manifest={
            "schema":"vf.p07.module-bundle.v1",
            "module_id":"P07-M05",
            "module_build_id":build,
            "entrypoint":"bin/vfops-init-entry",
            "installation_isolation":"P07-M05_ONLY",
            "files":{k:hashlib.sha256(v).hexdigest() for k,v in payload.items()},
        }
        (release/"MODULE_MANIFEST.json").write_text(
            json.dumps(manifest,ensure_ascii=False),encoding="utf-8")
        (self.module/"current").symlink_to("releases/"+build)
        return release

    def harness(self) -> Path:
        path=self.folder/"entry-test.sh"
        path.write_text(
            "#!/bin/bash\nset -Eeuo pipefail\n"
            + "M05_ROOT=" + shlex.quote(str(self.module)) + "\n"
            + 'M05_RUNTIME="$M05_ROOT/current/bin/vfops-init-entry"\n'
            + 'M05_BUNDLE_URL=""\nM05_BUNDLE_SHA256=""\n'
            + "C_YELLOW=''\nC_RED=''\nC_RESET=''\n"
            + "screen_clear() { :; }\n"
            + 'say() { printf \'%s\\n\' "$*"; }\n'
            + self.helper + "\n" + self.install_helper + "\n" + self.body + "\nrun_server_init\n"
        )
        return path

    def invoke(self):
        return subprocess.run(["bash",str(self.harness())],capture_output=True,
                              text=True,timeout=15)

    def test_legacy_cross_module_dispatch_would_fail(self):
        legacy='run_server_init() {\n  ensure_server_ops_current\n  ensure_system_care_current\n}\n'
        with self.assertRaises(AssertionError):
            assert_independent(legacy)

    def test_m05_candidate_dispatch_is_owned_and_not_cross_module(self):
        assert_independent(self.body)
        self.assertIn("MODULE_MANIFEST.json",self.helper)
        self.assertIn('"$M05_RUNTIME" --version',self.helper)

    def test_missing_m05_does_not_install_other_modules(self):
        result=self.invoke()
        self.assertEqual(result.returncode,7,result.stderr)
        self.assertIn("尚未正式分发",result.stdout)

    def test_valid_manifest_and_current_build_use_private_menu(self):
        self.module_fixture()
        result=self.invoke()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.marker.read_text().strip(),"menu")

    def test_valid_independently_upgraded_newer_build_still_runs(self):
        self.module_fixture(build="0.1.0-m05-candidate2")
        result=self.invoke()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(self.marker.exists())

    def test_corrupted_module_file_is_rejected_without_launch(self):
        release=self.module_fixture()
        (release/"lib/fixture00.py").write_text("altered")
        result=self.invoke()
        self.assertEqual(result.returncode,13,result.stderr)
        self.assertFalse(self.marker.exists())

    def test_wrong_reported_version_is_rejected_without_launch(self):
        self.module_fixture(actual_version="WRONG")
        result=self.invoke()
        self.assertEqual(result.returncode,13,result.stderr)
        self.assertFalse(self.marker.exists())

    def test_unlisted_payload_is_rejected_before_root_cli(self):
        release=self.module_fixture()
        (release/"lib/extra.py").write_text("print('not declared')\\n")
        result=self.invoke()
        self.assertEqual(result.returncode,13,result.stderr)
        self.assertFalse(self.marker.exists())

    def test_unlisted_directory_is_rejected_before_root_cli(self):
        release=self.module_fixture()
        (release/"lib/undeclared").mkdir()
        result=self.invoke()
        self.assertEqual(result.returncode,13,result.stderr)
        self.assertFalse(self.marker.exists())

    def test_symlinked_lib_parent_with_valid_file_hashes_is_rejected(self):
        release=self.module_fixture()
        owned=self.folder/"same-bytes-library"
        (release/"lib").rename(owned)
        (release/"lib").symlink_to(owned,target_is_directory=True)
        result=self.invoke()
        self.assertEqual(result.returncode,13,result.stderr)
        self.assertFalse(self.marker.exists())

    def test_symlinked_release_directory_is_rejected(self):
        release=self.module_fixture()
        moved=self.folder/"real-release"
        release.rename(moved)
        release.symlink_to(moved,target_is_directory=True)
        result=self.invoke()
        self.assertEqual(result.returncode,13,result.stderr)
        self.assertFalse(self.marker.exists())

    def test_symlinked_module_root_is_rejected(self):
        self.module_fixture()
        real=self.folder/"real-module"
        self.module.rename(real)
        self.module.symlink_to(real,target_is_directory=True)
        result=self.invoke()
        self.assertEqual(result.returncode,13,result.stderr)
        self.assertFalse(self.marker.exists())


if __name__=="__main__":
    unittest.main()
