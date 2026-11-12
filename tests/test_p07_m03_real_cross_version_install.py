"""P07-M03 网站与数据: *actual* official release114 -> release115 upgrade/rollback.

Reconstruct exact previously published release114 using its immutable historic
Git checkout, SHA-256 verified original base TAR and SHA-1 Git-blob verified
runtime overlay. Execute the production installer source for release115 then
its guarded previous-runtime rollback twice. All installs remain disposable.
No CloudPanel, websites, MySQL, migrations, DNS or Owner machines are used.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tarfile
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "installers/p07-final.sh"
RESTORER = ROOT / "installers/p07-m03-restore-previous.sh"
OLD_BUILD = "0.1.0-release114"
NEW_BUILD = "0.1.0-release115"


def blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def tree_identity(root: Path) -> str:
    h = hashlib.sha256()
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root).as_posix().encode()
        h.update(relative + b"\0")
        if item.is_symlink():
            h.update(b"L" + os.readlink(item).encode())
        elif item.is_file():
            h.update(b"F" + item.read_bytes())
        else:
            h.update(b"D")
    return h.hexdigest()


HISTORY_SOURCE = "9561d8a30d6cadda40442461e54cf8d35d551eda"
OLD_BASE_SHA256 = "de28a5e9dada500357be725e78e9e5cbacd51d26f1ec9bbb55ff92d21d49ada5"
OLD_MANIFEST_SHA1 = "ac4086db6a20859a8f101d2aeec588e42e0b5b40"


def install_verified_release114(root: Path):
    # The source checkout is pinned by the workflow and checked independently.
    historic=ROOT / "historical_m03"
    source=historic/"dist/p07/0.1.0/overlay"
    base=historic/"dist/p07/0.1.0-rc2/P07_VF_SERVER_OPS_0.1.0-rc2.tar.gz"
    self_head=subprocess.run(["git","-C",str(historic),"rev-parse","HEAD"],
                             capture_output=True,text=True,timeout=10,check=True)
    if self_head.stdout.strip()!=HISTORY_SOURCE:
        raise AssertionError("Historical M03 source drift")
    tar_bytes=base.read_bytes()
    if hashlib.sha256(tar_bytes).hexdigest()!=OLD_BASE_SHA256:
        raise AssertionError("Original M03 base archive SHA256 mismatch")
    if root.exists() or root.is_symlink():
        raise AssertionError("Historic M03 target not empty")
    with tempfile.TemporaryDirectory(prefix="p07-m03-base-extract-") as temp:
        with tarfile.open(base,"r:gz") as archive:
            archive.extractall(temp,filter="data")
        published_base=Path(temp)/"vf-server-ops"
        if not (published_base/"VERSION").is_file():
            raise AssertionError("Historic M03 base structure missing")
        shutil.copytree(published_base,root,symlinks=False)
    manifest=(source/"RUNTIME.gitblob").read_bytes()
    if blob(manifest)!=OLD_MANIFEST_SHA1:
        raise AssertionError("Historical release114 manifest mismatch")
    rows=manifest.decode("utf-8").splitlines()
    if not 50<=len(rows)<=240:
        raise AssertionError("Historical M03 manifest row limit")
    seen=set()
    for row in rows:
        match=re.fullmatch(r"([0-9a-f]{40})  ((?:bin|lib)/[A-Za-z0-9_./-]+|BUILD_ID)",row)
        if match is None:
            raise AssertionError("Bad historical M03 manifest")
        expected,name=match.groups()
        if ".." in Path(name).parts or name in seen:
            raise AssertionError("Duplicate / escaped historic path")
        seen.add(name)
        original=source/name
        if original.is_symlink() or not original.is_file():
            raise AssertionError("Missing historic source "+name)
        data=original.read_bytes()
        if blob(data)!=expected:
            raise AssertionError("Historic public source blob mismatch "+name)
        installed=root/name
        installed.parent.mkdir(parents=True,exist_ok=True)
        installed.write_bytes(data)
        if name.startswith("bin/"):
            installed.chmod(0o755)
    (root/".runtime-manifest.gitblob").write_bytes(manifest)
    if (root/"BUILD_ID").read_text().strip()!=OLD_BUILD:
        raise AssertionError("Historical M03 installed build mismatch")
    v=subprocess.run(["bash",str(root/"bin/vfops-user"),"--version"],
                     capture_output=True,text=True,timeout=15)
    if v.returncode or v.stdout.strip()!="VF Server Ops 0.1.0":
        raise AssertionError("Historical M03 original runtime version failed")


@unittest.skipUnless(os.getenv("P07_M03_NATIVE_FULL") == "1" and
                     os.getenv("GITHUB_ACTIONS") == "true",
                     "only disposable hosted M03 full upgrade runner")
class M03ActualRuntimeUpgrade(unittest.TestCase):
    def setUp(self):
        self.assertEqual(os.geteuid(), 0)
        self.temp = tempfile.TemporaryDirectory(prefix="p07-m03-full-upgrade-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.current = self.base / "m03"
        self.previous = self.base / "m03.previous"
        self.link = self.base / "bin/vfops"
        self.link.parent.mkdir()
        self.siblings={}
        for module in ("m01", "m02", "m04", "m05"):
            path=self.base / module
            path.mkdir()
            (path / "BUILD_ID").write_text(module+"-unchanged\n")
            (path / "OWNED").write_text(module + ": private module assets\n")
            self.siblings[module]=path
        self.data=self.base / "website-data"
        self.data.mkdir()
        (self.data / "do-not-touch.sqlite").write_bytes(b"preserved unrelated website fixture")
        self.external=[self.data / "do-not-touch.sqlite"]
        self.env={**os.environ,
                  "P07_INSTALL_DIR":str(self.current),
                  "P07_PREVIOUS_DIR":str(self.previous),
                  "P07_BIN_LINK":str(self.link),
                  "P07_NO_EXEC":"1",
                  "NO_COLOR":"1"}
        install_verified_release114(self.current)
        self.link.symlink_to(self.current/"bin/vfops-user")
        self.sibling_before={n:tree_identity(p) for n,p in self.siblings.items()}
        self.data_before={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in self.external}

    def install(self,env=None,timeout=240):
        return subprocess.run(["bash",str(INSTALLER)],
                              env=env or self.env,capture_output=True,
                              text=True,timeout=timeout)

    def assert_preserved(self):
        self.assertEqual(self.sibling_before,
                         {n:tree_identity(p) for n,p in self.siblings.items()})
        self.assertEqual(self.data_before,
                         {str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in self.external})
        self.assertEqual(os.readlink(self.link),
                         str(self.current/"bin/vfops-user"))

    def verified_build(self,root,expected):
        self.assertEqual((root / "BUILD_ID").read_text().strip(),expected)
        p=subprocess.run(["bash",str(root/"bin/vfops-user"),"--build-id"],
                         capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(p.stdout.strip(),expected)

    def rollback_script(self):
        script=RESTORER.read_text()
        substitutions={
            "M03_ROOT='/opt/vf-server-ops'":"M03_ROOT='"+str(self.current)+"'",
            "M03_PREVIOUS='/opt/vf-server-ops.previous'":"M03_PREVIOUS='"+str(self.previous)+"'",
            "M03_ENTRY='/usr/local/bin/vfops'":"M03_ENTRY='"+str(self.link)+"'",
            "M03_LOCK='/opt/vf-server-ops.rollback.lock'":"M03_LOCK='"+str(self.base/"rollback.lock")+"'",
        }
        for before,after in substitutions.items():
            self.assertEqual(script.count(before),1)
            script=script.replace(before,after)
        out=self.base/"m03-rollback.sh"
        out.write_text(script)
        return out

    def rollback(self,script,build,confirm):
        return subprocess.run(["bash",str(script),"restore-previous",build,confirm],
                              capture_output=True,text=True,timeout=30)

    def test_01_damaged_existing_manifest_denied_before_download(self):
        original=(self.current/"lib/server_migration.py").read_bytes()
        (self.current/"lib/server_migration.py").write_bytes(original+b"# modified\n")
        fake_env={**self.env,"P07_PUBLIC_ROOT":"https://127.0.0.1:1"}
        result=self.install(fake_env,timeout=40)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("原运行时归属或完整性无法确认",result.stderr)
        self.assertFalse(self.previous.exists())
        self.verified_build(self.current,OLD_BUILD)
        self.assert_preserved()

    def test_02_real_official_release114_to115_install_and_reverse(self):
        # First show an invalid download does not consume/move the valid older runtime.
        bad_env={**self.env,"P07_PUBLIC_ROOT":"https://127.0.0.1:1"}
        failed=self.install(bad_env,timeout=75)
        self.assertNotEqual(failed.returncode,0)
        self.verified_build(self.current,OLD_BUILD)
        self.assertFalse(self.previous.exists())
        self.assert_preserved()

        # Actual current official source: base tar.gz + pinned runtime overlay +
        # full install/manifest verification + physical previous-directory swap.
        installed=self.install(timeout=240)
        self.assertEqual(installed.returncode,0,installed.stderr[-1800:])
        self.verified_build(self.current,NEW_BUILD)
        self.verified_build(self.previous,OLD_BUILD)
        self.assertTrue((self.current/".runtime-manifest.gitblob").is_file())
        self.assert_preserved()
        print("P07_M03_REAL_RELEASE114_TO_RELEASE115_PHYSICAL_UPGRADE=PASS",
              flush=True)

        rollback=self.rollback_script()
        bad=self.rollback(rollback,OLD_BUILD,"P07-M03:wrong")
        self.assertEqual(bad.returncode,13,bad.stderr)
        self.verified_build(self.current,NEW_BUILD)
        self.assert_preserved()

        old_file=self.previous/"lib/server_migration.py"
        original=old_file.read_bytes()
        old_file.write_bytes(original+b"# corrupt previous\n")
        corrupt=self.rollback(rollback,OLD_BUILD,"P07-M03:"+OLD_BUILD)
        self.assertEqual(corrupt.returncode,13,corrupt.stderr)
        self.verified_build(self.current,NEW_BUILD)
        old_file.write_bytes(original)
        self.assert_preserved()

        restored=self.rollback(rollback,OLD_BUILD,"P07-M03:"+OLD_BUILD)
        self.assertEqual(restored.returncode,0,restored.stderr)
        self.verified_build(self.current,OLD_BUILD)
        self.verified_build(self.previous,NEW_BUILD)
        self.assert_preserved()
        forward=self.rollback(rollback,NEW_BUILD,"P07-M03:"+NEW_BUILD)
        self.assertEqual(forward.returncode,0,forward.stderr)
        self.verified_build(self.current,NEW_BUILD)
        self.verified_build(self.previous,OLD_BUILD)
        self.assert_preserved()
        print("P07_M03_REAL_RELEASE114_115_PHYSICAL_ROLLBACK_AND_REVERSE=PASS",flush=True)
        print("P07_M03_OTHER_FOUR_MODULES_AND_WEBSITE_FIXTURE_UNCHANGED=PASS",flush=True)


if __name__ == "__main__":
    unittest.main()
