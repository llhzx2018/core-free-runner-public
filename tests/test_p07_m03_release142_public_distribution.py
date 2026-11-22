"""P07-M03 网站与数据 / D04 服务器迁移 official142 public path.

Uses genuine anonymous GitHub Releases, isolated program directories, and
independent canaries; no CloudPanel, Owner VPS, website, SQL or DNS changes.
"""
from __future__ import annotations

import hashlib
import os
import re
import shlex
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOLBOX=ROOT/"installers/p07-toolbox.sh"
WRAPPER=ROOT/"installers/p07-m03-release142-atomic.sh"
OLD141=ROOT/"installers/p07-m03-release141-atomic.sh"
OLD140=ROOT/"installers/p07-m03-release140-atomic.sh"
BUILD="0.1.0-release142"
OLD_BUILD="0.1.0-release141"
ZIP_SHA="dc6978463e8e73a224e7cccb2bdffe9710bc3bb478076b670703bbb164bda87e"
RUNTIME_BLOB="cc3d90839bf71ea9139f5fc0d1c6cb12403b58e0"
INSTALLER_BLOB="faadb1c6945b967ff5a06a730f2503f1ccd0de88"
WRAPPER_BLOB="1f10b7ce1d87b4b806cdd78455bfdbcf17276876"
RELEASE="p07-m03-v0.1.0-release142-20261120"


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()


def env_for(root: Path) -> dict[str,str]:
    return dict(os.environ,P07_ALLOW_NONROOT="1",P07_NO_EXEC="1",
                PYTHONDONTWRITEBYTECODE="1",NO_COLOR="1",
                P07_INSTALL_DIR=str(root/"current"),
                P07_PREVIOUS_DIR=str(root/"previous"),
                P07_BIN_LINK=str(root/"bin/vfops"))


def run(*args:str, env:dict[str,str]|None=None, timeout:int=240)->subprocess.CompletedProcess:
    return subprocess.run(args,env=env,cwd=ROOT,text=True,capture_output=True,
                          timeout=timeout,check=False)


class Official142PublicDistribution(unittest.TestCase):
    def test_exact_release142_remains_verified_for_upgrade(self):
        toolbox=TOOLBOX.read_text(encoding="utf-8")
        wrapper=WRAPPER.read_text(encoding="utf-8")
        self.assertEqual(git_blob(WRAPPER.read_bytes()),WRAPPER_BLOB)
        for token in (
            f'M03_OFFICIAL142_BUILD="{BUILD}"',
            f'M03_OFFICIAL142_MANIFEST_BLOB="{RUNTIME_BLOB}"',
            'M03_OFFICIAL141_BUILD="0.1.0-release141"',
            'M03_OFFICIAL141_MANIFEST_BLOB="6a3a949064ffb8fe1df56e7bc555173b5ca9cf3b"',
            'M03_OFFICIAL140_BUILD="0.1.0-release140"',
            'M03_PREVIOUS_BUILD="0.1.0-release139"',
        ):
            self.assertIn(token,toolbox)
        for token in (
            f"BUILD='{BUILD}'",
            f"RELEASE='{RELEASE}'",
            "ZIP_NAME='P07-M03-0.1.0-release142.zip'",
            f"ZIP_SHA256='{ZIP_SHA}'",
            f"RUNTIME_BLOB='{RUNTIME_BLOB}'",
            f"INSTALLER_BLOB='{INSTALLER_BLOB}'",
            "releases/assets/769843045",
            '"0.1.0-release141":"6a3a949064ffb8fe1df56e7bc555173b5ca9cf3b"',
            '"0.1.0-release142":"cc3d90839bf71ea9139f5fc0d1c6cb12403b58e0"',
        ):
            self.assertIn(token,wrapper)
        self.assertNotIn("gh auth",wrapper)
        self.assertNotIn("git clone",wrapper)
        self.assertIn('flock -x "$m03_lock_fd"',wrapper)
        self.assertIn('mv -nT -- "$m03_previous" "$m03_archive"',wrapper)
        for script in (TOOLBOX,WRAPPER,OLD141,OLD140):
            r=run("bash","-n",str(script),timeout=15)
            self.assertEqual(r.returncode,0,r.stderr)

    def test_real_140_141_142_anonymous_upgrade_preserves_all_canaries(self):
        with tempfile.TemporaryDirectory(prefix="p07-142-public-history-") as tmp:
            root=Path(tmp)
            for mod in ("m01","m02","m04","m05","website","db","dns"):
                f=root/"canaries"/mod; f.parent.mkdir(parents=True,exist_ok=True)
                f.write_text("PRESERVE_"+mod,encoding="utf-8")
            def canary():
                return hashlib.sha256(b"".join(
                    (root/"canaries"/mod).read_bytes()
                    for mod in ("m01","m02","m04","m05","website","db","dns")
                )).hexdigest()
            before=canary()
            env=env_for(root)
            for script,version in (
                (OLD140,"0.1.0-release140"),
                (OLD141,"0.1.0-release141"),
            ):
                r=run("bash",str(script),"install",env=env)
                self.assertEqual(r.returncode,0,r.stderr[-1200:])
                self.assertEqual((root/"current/BUILD_ID").read_text().strip(),version)
            self.assertEqual((root/"previous/BUILD_ID").read_text().strip(),"0.1.0-release140")
            (root/"previous.preserved-0.1.0-release139").mkdir()
            (root/"previous.preserved-0.1.0-release139/OWNER_CANARY").write_text("KEEP")
            upgrade=run("bash",str(WRAPPER),"install",env=env)
            self.assertEqual(upgrade.returncode,0,(upgrade.stdout+upgrade.stderr)[-2100:])
            self.assertEqual((root/"current/BUILD_ID").read_text().strip(),BUILD)
            self.assertEqual((root/"previous/BUILD_ID").read_text().strip(),OLD_BUILD)
            self.assertEqual((root/"previous.preserved-0.1.0-release140/BUILD_ID").read_text().strip(),"0.1.0-release140")
            self.assertEqual((root/"previous.preserved-0.1.0-release139/OWNER_CANARY").read_text(),"KEEP")
            version=run(str(root/"bin/vfops"),"--build-id",env=env,timeout=15)
            self.assertEqual(version.returncode,0,version.stderr[-300:])
            self.assertEqual(version.stdout.strip(),BUILD)
            self.assertEqual(canary(),before)
            self.assertTrue((root/"current/components/p07-m03-migration-readiness.sh").is_file())

    def test_real_published_142_clean_full_install_and_idempotence(self):
        """The exact public142 package must also FULL-install on an empty VPS slot."""
        with tempfile.TemporaryDirectory(prefix="p07-142-public-clean-") as tmp:
            root=Path(tmp);env=env_for(root)
            first=run("bash",str(WRAPPER),"install",env=env)
            self.assertEqual(first.returncode,0,(first.stdout+first.stderr)[-1600:])
            self.assertEqual((root/"current/BUILD_ID").read_text().strip(),BUILD)
            self.assertFalse((root/"previous").exists())
            self.assertTrue((root/"current/components/p07-m03-migration-readiness.sh").is_file())
            self.assertEqual(
                git_blob((root/"current/.runtime-manifest.gitblob").read_bytes()),
                RUNTIME_BLOB,
            )
            version=run(str(root/"bin/vfops"),"--build-id",env=env,timeout=15)
            self.assertEqual(version.returncode,0,version.stderr[-300:])
            self.assertEqual(version.stdout.strip(),BUILD)
            before=(root/"current/.runtime-manifest.gitblob").read_bytes()
            again=run("bash",str(WRAPPER),"install",env=env)
            self.assertEqual(again.returncode,0,(again.stdout+again.stderr)[-1600:])
            self.assertEqual((root/"current/BUILD_ID").read_text().strip(),BUILD)
            self.assertEqual((root/"current/.runtime-manifest.gitblob").read_bytes(),before)

    def test_unknown_backup_refuses_without_moving_it(self):
        with tempfile.TemporaryDirectory(prefix="p07-142-unknown-") as tmp:
            root=Path(tmp);env=env_for(root)
            r=run("bash",str(OLD141),"install",env=env)
            self.assertEqual(r.returncode,0,r.stderr[-1000:])
            prev=root/"previous";prev.mkdir()
            (prev/"BUILD_ID").write_text("UNVERIFIED\n")
            marker=(root/"current/.runtime-manifest.gitblob").read_bytes()
            fail=run("bash",str(WRAPPER),"install",env=env)
            self.assertNotEqual(fail.returncode,0)
            self.assertEqual((prev/"BUILD_ID").read_text(),"UNVERIFIED\n")
            self.assertEqual((root/"current/.runtime-manifest.gitblob").read_bytes(),marker)
            self.assertFalse((root/"previous.preserved-0.1.0-release140").exists())

    def test_previous_archive_collision_stays_untouched(self):
        with tempfile.TemporaryDirectory(prefix="p07-142-collision-") as tmp:
            root=Path(tmp);env=env_for(root)
            for old in (OLD140,OLD141):
                r=run("bash",str(old),"install",env=env)
                self.assertEqual(r.returncode,0,r.stderr[-1000:])
            archive=root/"previous.preserved-0.1.0-release140";archive.mkdir()
            (archive/"OWNER_CANARY").write_text("KEEP")
            fail=run("bash",str(WRAPPER),"install",env=env)
            self.assertNotEqual(fail.returncode,0)
            self.assertEqual((archive/"OWNER_CANARY").read_text(),"KEEP")
            self.assertEqual((root/"current/BUILD_ID").read_text().strip(),OLD_BUILD)
            self.assertEqual((root/"previous/BUILD_ID").read_text().strip(),"0.1.0-release140")

    def test_corrupt_official_142_zip_digest_stops_preinstall(self):
        with tempfile.TemporaryDirectory(prefix="p07-142-badsha-") as tmp:
            root=Path(tmp);env=env_for(root)
            source=WRAPPER.read_text(encoding="utf-8")
            self.assertEqual(source.count(ZIP_SHA),1)
            bad=root/"tampered-digest.sh"
            bad.write_text(source.replace(ZIP_SHA,"0"*64,1))
            fail=run("bash",str(bad),"install",env=env)
            self.assertNotEqual(fail.returncode,0)
            self.assertFalse((root/"current").exists())
            self.assertFalse((root/"previous").exists())
            self.assertFalse((root/"bin/vfops").exists())


    def test_release146_public_entry_and_real_145_upgrade(self):
        wrapper = ROOT / "installers/p07-m03-release146-atomic.sh"
        older_wrapper = ROOT / "installers/p07-m03-release144-atomic.sh"
        previous_wrapper = ROOT / "installers/p07-m03-release145-atomic.sh"
        toolbox = TOOLBOX.read_text(encoding="utf-8")
        stable_version = "0.1.0-release146"
        previous_version = "0.1.0-release145"
        self.assertIn(f'VF_SERVER_OPS_BUILD_EXPECTED="{stable_version}"', toolbox)
        self.assertIn(f'VF_SERVER_OPS_INSTALLER_BLOB="{git_blob(wrapper.read_bytes())}"', toolbox)
        self.assertIn("installers/p07-m03-release146-atomic.sh", toolbox)
        with tempfile.TemporaryDirectory(prefix="p07-146-public-") as temp:
            root = Path(temp)
            env = env_for(root)
            canaries = {}
            for module in ("m01", "m02", "m04", "m05", "website", "database", "dns"):
                marker = root / f"keep-{module}"
                marker.write_bytes(f"preserved {module}\n".encode())
                canaries[marker] = marker.read_bytes()
            for entry, version in (
                (OLD141, OLD_BUILD),
                (WRAPPER, BUILD),
                (older_wrapper, "0.1.0-release144"),
                (previous_wrapper, previous_version),
            ):
                applied = run("bash", str(entry), "install", env=env)
                self.assertEqual(applied.returncode, 0, (applied.stdout + applied.stderr)[-1600:])
                self.assertEqual((root / "current/BUILD_ID").read_text().strip(), version)
            helpers = []
            for name in ("p07_git_blob_sha1", "m03_verified_current", "ensure_server_ops_current"):
                match = re.search(rf"(?ms)^{name}\(\) \{{\n.*?^\}}$", toolbox)
                self.assertIsNotNone(match, name)
                helpers.append(match.group().replace("/opt/vf-server-ops", str(root / "current")))
            pins = "\n".join(re.findall(r"(?m)^(?:VF_SERVER_OPS|M03_)[A-Z0-9_]*=.*$", toolbox))
            harness = root / "toolbox-upgrade.sh"
            harness.write_text(
                "set -euo pipefail\nC_RED='' C_RESET=''\n" + pins + "\n" +
                'say() { printf "%s\\n" "$*"; }\n' +
                'curl() { [[ "$1" == -fsSL && "$2" == "$VF_SERVER_OPS_INSTALLER" && "$3" == -o ]]; '
                'cp -- "$P07_TEST_WRAPPER" "$4"; }\n' +
                "\n".join(helpers) + "\nensure_server_ops_current\n",
                encoding="utf-8",
            )
            env["PATH"] = str(root / "bin") + os.pathsep + env["PATH"]
            env["P07_TEST_WRAPPER"] = str(wrapper)
            noninteractive = run("bash", str(harness), env=env)
            self.assertEqual(noninteractive.returncode, 7, noninteractive.stderr)
            self.assertEqual((root / "current/BUILD_ID").read_text().strip(), previous_version)
            upgrade = subprocess.run(
                ["script", "-qec", "bash " + shlex.quote(str(harness)), "/dev/null"],
                input="y\n", env=env, text=True, capture_output=True, timeout=240,
            )
            self.assertEqual(upgrade.returncode, 0, (upgrade.stdout + upgrade.stderr)[-1600:])
            self.assertIn("已核验旧正式版 0.1.0-release145", upgrade.stdout)
            self.assertEqual((root / "current/BUILD_ID").read_text().strip(), stable_version)
            self.assertEqual((root / "previous/BUILD_ID").read_text().strip(), previous_version)
            self.assertEqual(
                (root / "previous.preserved-0.1.0-release141/BUILD_ID").read_text().strip(), OLD_BUILD
            )
            self.assertEqual(
                (root / "previous.preserved-0.1.0-release142/BUILD_ID").read_text().strip(), BUILD
            )
            self.assertEqual(
                (root / "previous.preserved-0.1.0-release144/BUILD_ID").read_text().strip(),
                "0.1.0-release144",
            )
            current = (root / "current/.runtime-manifest.gitblob").read_bytes()
            self.assertIn(f'VF_SERVER_OPS_MANIFEST_BLOB="{git_blob(current)}"', toolbox)
            self.assertTrue((root / "current/lib/migration_safe_batch_cli.py").is_file())
            self.assertTrue((root / "current/lib/migration_batch_withdraw.py").is_file())
            again = run("bash", str(wrapper), "install", env=env)
            self.assertEqual(again.returncode, 0, (again.stdout + again.stderr)[-1600:])
            self.assertEqual((root / "current/.runtime-manifest.gitblob").read_bytes(), current)
            for marker, value in canaries.items():
                self.assertEqual(marker.read_bytes(), value)


if __name__=="__main__":
    unittest.main()
