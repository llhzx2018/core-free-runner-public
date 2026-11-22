"""P07-M03 网站与数据 / D04 服务器迁移 · real public release139 gate.

Run on ephemeral GitHub Ubuntu runner: isolated sandbox, actual published
GitHub release138 and 138 assets, no Owner SQL/site/CloudPanel/DNS writes.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "installers/p07-m03-release139-atomic.sh"
OLD = ROOT / "installers/p07-m03-release138-atomic.sh"
RESTORE = ROOT / "installers/p07-m03-restore-previous.sh"
TOOLBOX = ROOT / "installers/p07-toolbox.sh"
TAG = "p07-m03-d04-v0.1.0-release139-noncutover-20261118"
SHA = "419d9ff3aa4f4f37ac450b8dc6767a759fe64e701e5683b71fd1b0841dec97bf"
MANIFEST = "efdfff0b4348b334bbbc2da26d40280338fc7868"
BUILD = "0.1.0-release139"


def run(*args: str, env=None, timeout=120):
    return subprocess.run(args, env=env, text=True, capture_output=True,
                          timeout=timeout, cwd=ROOT)


class P07Official139(unittest.TestCase):
    def test_exact_official_remote_release_and_single_public_wrapper(self):
        # Authenticated read-only GH_TOKEN avoids unauthenticated GitHub rate limits.
        remote = subprocess.run(
            ["gh", "api", "repos/llhzx2018/core-free-runner-public/releases/tags/" + TAG],
            capture_output=True, text=True, check=True, timeout=30,
        )
        data = json.loads(remote.stdout)
        self.assertFalse(data["draft"])
        self.assertFalse(data["prerelease"])
        assets = {a["name"]: a for a in data["assets"]}
        self.assertEqual(set(assets), {"P07-M03-0.1.0-release139.zip", "SHA256SUMS"})
        self.assertEqual(assets["P07-M03-0.1.0-release139.zip"]["digest"], "sha256:" + SHA)
        self.assertEqual(assets["P07-M03-0.1.0-release139.zip"]["id"], 762286729)
        self.assertGreater(assets["P07-M03-0.1.0-release139.zip"]["size"], 500000)
        wrapper = WRAPPER.read_text(encoding="utf-8")
        toolbox = TOOLBOX.read_text(encoding="utf-8")
        self.assertIn("ZIP_SHA256='" + SHA + "'", wrapper)
        self.assertIn("RUNTIME_BLOB='" + MANIFEST + "'", wrapper)
        self.assertIn("INSTALLER_BLOB='c00812cf9bb3452dc4a295d635afd3624e0a3b01'", wrapper)
        self.assertIn("releases/assets/762286729", wrapper)
        # Historical release139 ZIP and wrapper remain immutable.
        # Historical 139 ZIP/wrapper stay immutable; current Toolbox now targets 142.
        self.assertIn('VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release144"', toolbox)
        self.assertIn('M03_OFFICIAL140_BUILD="0.1.0-release140"', toolbox)
        self.assertIn('M03_PREVIOUS_BUILD="0.1.0-release139"', toolbox)
        self.assertIn("installers/p07-m03-release144-atomic.sh", toolbox)
        self.assertIn('M03_LEGACY138_BUILD="0.1.0-release138"', toolbox)
        self.assertIn('M03_LEGACY137_BUILD="0.1.0-release137"', toolbox)
        self.assertIn('M03_BOOTSTRAP_BUILD="0.1.0-release136"', toolbox)
        self.assertIn('M03_LEGACY135_BUILD="0.1.0-release135"', toolbox)
        self.assertIn('M03_LEGACY115_BUILD="0.1.0-release115"', toolbox)
        self.assertIn('M03_ROLLBACK_INSTALLER_REF="main"', toolbox)
        self.assertIn('M03_ROLLBACK_INSTALLER_BLOB="48fca0b7ac6fa3358912ef1f3a146d37a20b99c2"', toolbox)
        for script in (WRAPPER, OLD, RESTORE, TOOLBOX):
            result = run("bash", "-n", str(script), timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("systemctl stop clp-nginx", wrapper)

    def test_real_public_release139_full_and_reject_untrusted_hash(self):
        with tempfile.TemporaryDirectory(prefix="p07-139-pub-") as tmp:
            root = Path(tmp)
            env = dict(os.environ, P07_ALLOW_NONROOT="1", P07_NO_EXEC="1",
                       PYTHONDONTWRITEBYTECODE="1", NO_COLOR="1",
                       P07_INSTALL_DIR=str(root/"live"),
                       P07_PREVIOUS_DIR=str(root/"previous"),
                       P07_BIN_LINK=str(root/"bin"/"vfops"))
            result = run("bash", str(WRAPPER), "install", env=env, timeout=180)
            self.assertEqual(result.returncode, 0, result.stderr[-1800:])
            self.assertEqual((root/"live/BUILD_ID").read_text().strip(), BUILD)
            self.assertTrue((root/"live/lib/migration_readiness_cli.py").is_file())
            self.assertFalse((root/"previous").exists())
            entry = run("bash", str(root/"live/bin/vfops-migrate-ui"),
                        env=env, timeout=10)
            self.assertEqual(entry.returncode, 0, entry.stderr[-1000:])
            self.assertIn("先检查旧 VPS 和新机数据库选项", entry.stdout)
            # A different new location with a corrupted advertised SHA is refused
            # before a target directory is created or a real business is touched.
            altered = WRAPPER.read_text().replace(SHA, "0"*64)
            self.assertNotEqual(altered, WRAPPER.read_text())
            bad = root/"bad-wrapper.sh"
            bad.write_text(altered)
            wrong = dict(env, P07_INSTALL_DIR=str(root/"bad-live"),
                         P07_PREVIOUS_DIR=str(root/"bad-prev"),
                         P07_BIN_LINK=str(root/"bin"/"bad-vfops"))
            fail = run("bash", str(bad), "install", env=wrong, timeout=180)
            self.assertNotEqual(fail.returncode, 0)
            self.assertFalse((root/"bad-live").exists())
            self.assertEqual((root/"live/BUILD_ID").read_text().strip(), BUILD)

    def test_real_138_to_139_then_guarded_previous_restore_and_cancellation(self):
        self.assertTrue(shutil.which("sudo"), "Ubuntu runner must support isolated root restore")
        with tempfile.TemporaryDirectory(prefix="p07-139-rollback-") as tmp:
            root = Path(tmp)
            (root/"bin").mkdir()
            (root/"canary").mkdir()
            for n in ("m01","m02","m04","m05","business"):
                (root/"canary"/n).write_text("unchanged-" + n)
            def fingerprint():
                return hashlib.sha256(b"".join(
                    (root/"canary"/n).read_bytes() for n in
                    ("m01","m02","m04","m05","business")
                )).hexdigest()
            before = fingerprint()
            env = dict(os.environ, P07_ALLOW_NONROOT="1", P07_NO_EXEC="1",
                       PYTHONDONTWRITEBYTECODE="1", NO_COLOR="1",
                       P07_INSTALL_DIR=str(root/"live"),
                       P07_PREVIOUS_DIR=str(root/"previous"),
                       P07_BIN_LINK=str(root/"bin"/"vfops"))
            p = run("bash", str(OLD), "install", env=env, timeout=180)
            self.assertEqual(p.returncode, 0, p.stderr[-1800:])
            self.assertEqual((root/"live/BUILD_ID").read_text().strip(), "0.1.0-release138")
            p = run("bash", str(WRAPPER), "install", env=env, timeout=180)
            self.assertEqual(p.returncode, 0, p.stderr[-1800:])
            self.assertEqual((root/"live/BUILD_ID").read_text().strip(), BUILD)
            self.assertEqual((root/"previous/BUILD_ID").read_text().strip(), "0.1.0-release138")
            s = RESTORE.read_text(encoding="utf-8")
            replacements = {
                "M03_ROOT='/opt/vf-server-ops'": "M03_ROOT='" + str(root/"live") + "'",
                "M03_PREVIOUS='/opt/vf-server-ops.previous'": "M03_PREVIOUS='" + str(root/"previous") + "'",
                "M03_ENTRY='/usr/local/bin/vfops'": "M03_ENTRY='" + str(root/"bin"/"vfops") + "'",
                "M03_LOCK='/opt/vf-server-ops.rollback.lock'": "M03_LOCK='" + str(root/"rollback.lock") + "'",
            }
            for old,new in replacements.items():
                self.assertEqual(s.count(old),1)
                s=s.replace(old,new)
            isolated = root/"restore-test.sh"
            isolated.write_text(s)
            bad = run("sudo", "bash", str(isolated), "restore-previous",
                      "0.1.0-release138", "NO_CONFIRM", timeout=30)
            self.assertNotEqual(bad.returncode,0)
            self.assertEqual((root/"live/BUILD_ID").read_text().strip(),BUILD)
            result = run("sudo", "bash", str(isolated), "restore-previous",
                         "0.1.0-release138", "P07-M03:0.1.0-release138", timeout=60)
            self.assertEqual(result.returncode,0,result.stderr[-1600:])
            self.assertEqual((root/"live/BUILD_ID").read_text().strip(),"0.1.0-release138")
            self.assertEqual((root/"previous/BUILD_ID").read_text().strip(),BUILD)
            back = run("sudo", "bash", str(isolated), "restore-previous",
                       BUILD, "P07-M03:"+BUILD, timeout=60)
            self.assertEqual(back.returncode,0,back.stderr[-1600:])
            self.assertEqual((root/"live/BUILD_ID").read_text().strip(),BUILD)
            self.assertEqual((root/"previous/BUILD_ID").read_text().strip(),"0.1.0-release138")
            self.assertEqual(before, fingerprint())


if __name__ == "__main__":
    unittest.main()
