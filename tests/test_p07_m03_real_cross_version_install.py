"""P07-M03 网站与数据: physical upgrade + rollback, not a synthetic pointer swap.

Build a complete manifest-verified release114 fixture on a disposable host,
install the REAL SHA-pinned public release115 runtime with the EXISTING M03
installer, reject damaged prior source, and restore previous in both directions
with the EXISTING standalone rollback script. Older fixture bytes are synthetic:
this does not claim to reproduce the historical official release114 package.
No CloudPanel, websites, MySQL, migrations, DNS or Owner machines are used.
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


def install_fixture(root: Path):
    (root / "bin").mkdir(parents=True)
    (root / "lib").mkdir()
    (root / "BUILD_ID").write_text(OLD_BUILD + "\n")
    script = root / "bin/vfops-user"
    script.write_text(
        "#!/usr/bin/env bash\n"
        'home="$(cd "$(dirname "$0")/.." && pwd)"\n'
        'case "$1" in\n'
        ' --version) echo "VF Server Ops 0.1.0" ;;\n'
        ' --build-id) cat "$home/BUILD_ID" ;;\n'
        ' *) exit 13 ;;\n'
        'esac\n'
    )
    script.chmod(0o755)
    for i in range(55):
        (root / "lib" / f"source{i:02d}.py").write_text(
            f"# disposable validated M03 previous build fixture {i}\n"
        )
    files = sorted([*root.glob("lib/*.py"),root / "BUILD_ID",script])
    rows = [blob(p.read_bytes())+"  "+p.relative_to(root).as_posix()
            for p in files]
    (root / ".runtime-manifest.gitblob").write_text("\n".join(rows)+"\n")


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
        install_fixture(self.current)
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
        original=(self.current/"lib/source00.py").read_bytes()
        (self.current/"lib/source00.py").write_bytes(original+b"# modified\n")
        fake_env={**self.env,"P07_PUBLIC_ROOT":"https://127.0.0.1:1"}
        result=self.install(fake_env,timeout=40)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("原运行时归属或完整性无法确认",result.stderr)
        self.assertFalse(self.previous.exists())
        self.verified_build(self.current,OLD_BUILD)
        self.assert_preserved()

    def test_02_real_release115_installer_from_valid_older_fixture_and_back(self):
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
        print("P07_M03_REAL_RELEASE115_PHYSICAL_UPGRADE_FROM_VALID_OLDER_FIXTURE=PASS",
              flush=True)

        rollback=self.rollback_script()
        bad=self.rollback(rollback,OLD_BUILD,"P07-M03:wrong")
        self.assertEqual(bad.returncode,13,bad.stderr)
        self.verified_build(self.current,NEW_BUILD)
        self.assert_preserved()

        old_file=self.previous/"lib/source00.py"
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
        print("P07_M03_REAL_RELEASE115_PHYSICAL_ROLLBACK_AND_REVERSE=PASS",flush=True)
        print("P07_M03_OTHER_FOUR_MODULES_AND_WEBSITE_FIXTURE_UNCHANGED=PASS",flush=True)


if __name__ == "__main__":
    unittest.main()
