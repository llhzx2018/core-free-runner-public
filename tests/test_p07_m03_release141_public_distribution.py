"""P07-M03 网站与数据：正式 release141 公共匿名工具箱分发真实机验。

No Owner VPS, CloudPanel, DNS, production credentials, business SQL, or source
checkout. Uses official public immutable ZIP, isolated install paths and canaries.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "installers/p07-m03-release141-atomic.sh"
OLD = ROOT / "installers/p07-m03-release140-atomic.sh"
OLDER = ROOT / "installers/p07-m03-release139-atomic.sh"
TOOLBOX = ROOT / "installers/p07-toolbox.sh"
BUILD = "0.1.0-release141"
OLD_BUILD = "0.1.0-release140"
ZIP_SHA = "22c23818bc7268e6d3d95bc2552f42a5a3c12e97e387fdc542d59934c658b6d1"
RUNTIME_BLOB = "6a3a949064ffb8fe1df56e7bc555173b5ca9cf3b"
INSTALLER_BLOB = "e2994e434fb7fb8c9f2cc33d986e5b269300acc0"
RELEASE = "p07-m03-v0.1.0-release141-limited-20261119"


def run(*args: str, env: dict[str, str] | None = None, timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, env=env, text=True,
                          capture_output=True, timeout=timeout, check=False)


def env_for(path: Path) -> dict[str, str]:
    return dict(os.environ, P07_ALLOW_NONROOT="1", P07_NO_EXEC="1",
                PYTHONDONTWRITEBYTECODE="1", NO_COLOR="1",
                P07_INSTALL_DIR=str(path / "current"),
                P07_PREVIOUS_DIR=str(path / "previous"),
                P07_BIN_LINK=str(path / "bin" / "vfops"))


class Official141PublicDistribution(unittest.TestCase):
    def test_current_pin_and_exact_reusable_prior_and_legacy_trust(self) -> None:
        toolbox = TOOLBOX.read_text(encoding="utf-8")
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn('VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release142"', toolbox)
        self.assertIn('M03_OFFICIAL141_BUILD="0.1.0-release141"', toolbox)
        self.assertIn('M03_OFFICIAL141_MANIFEST_BLOB="6a3a949064ffb8fe1df56e7bc555173b5ca9cf3b"', toolbox)
        self.assertIn('M03_OFFICIAL140_BUILD="0.1.0-release140"', toolbox)
        self.assertIn('M03_OFFICIAL140_MANIFEST_BLOB="239bd543e4f64449ca498c1d67ccb7471abbee66"', toolbox)
        self.assertIn('M03_PREVIOUS_BUILD="0.1.0-release139"', toolbox)
        self.assertIn('VF_SERVER_OPS_MANIFEST_BLOB="cc3d90839bf71ea9139f5fc0d1c6cb12403b58e0"', toolbox)
        self.assertIn('VF_SERVER_OPS_INSTALLER_BLOB="1f10b7ce1d87b4b806cdd78455bfdbcf17276876"', toolbox)
        self.assertIn("installers/p07-m03-release142-atomic.sh", toolbox)
        for key, value in (
            ("BUILD", BUILD),
            ("RELEASE", RELEASE),
            ("ZIP_NAME", "P07-M03-0.1.0-release141.zip"),
            ("ZIP_SHA256", ZIP_SHA),
            ("RUNTIME_BLOB", RUNTIME_BLOB),
            ("INSTALLER_BLOB", INSTALLER_BLOB),
        ):
            self.assertIn(f"{key}='{value}'", wrapper)
        self.assertIn("releases/assets/767910493", wrapper)
        self.assertIn('[[ "$actual_sha" == "$ZIP_SHA256" ]]', wrapper)
        for script in (WRAPPER, OLD, OLDER, TOOLBOX):
            checked = run("bash", "-n", str(script), timeout=15)
            self.assertEqual(checked.returncode, 0, checked.stderr[-1000:])
        self.assertNotIn("gh auth", wrapper)
        self.assertNotIn("git clone", wrapper)

    def test_actual_official140_to_public141_atomic_and_module_canaries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p07-m03-public141-") as tmp:
            root = Path(tmp)
            (root / "canary").mkdir()
            for part in ("m01", "m02", "m04", "m05", "business"):
                (root / "canary" / part).write_text("keep-" + part, encoding="utf-8")
            def snapshot() -> str:
                return hashlib.sha256(b"".join(
                    (root / "canary" / n).read_bytes()
                    for n in ("m01", "m02", "m04", "m05", "business")
                )).hexdigest()
            untouched = snapshot()
            env = env_for(root)
            first = run("bash", str(OLDER), "install", env=env)
            self.assertEqual(first.returncode, 0, first.stderr[-1800:])
            self.assertEqual((root / "current/BUILD_ID").read_text().strip(), "0.1.0-release139")
            initial = run("bash", str(OLD), "install", env=env)
            self.assertEqual(initial.returncode, 0, initial.stderr[-1800:])
            self.assertEqual((root / "current/BUILD_ID").read_text().strip(), OLD_BUILD)
            self.assertEqual((root / "previous/BUILD_ID").read_text().strip(), "0.1.0-release139")
            upgrade = run("bash", str(WRAPPER), "install", env=env)
            self.assertEqual(upgrade.returncode, 0, upgrade.stderr[-1800:])
            self.assertEqual((root / "current/BUILD_ID").read_text().strip(), BUILD)
            self.assertEqual((root / "previous/BUILD_ID").read_text().strip(), OLD_BUILD)
            self.assertEqual((root / "previous.preserved-0.1.0-release139/BUILD_ID").read_text().strip(), "0.1.0-release139")
            self.assertEqual(snapshot(), untouched)
            version = run(str(root / "bin/vfops"), "--build-id", env=env, timeout=15)
            self.assertEqual(version.returncode, 0, version.stderr[-900:])
            self.assertEqual(version.stdout.strip(), BUILD)
            self.assertTrue((root / "current/components/p07-m03-failed-task-ux.sh").is_file())

    def test_unknown_backup_is_preserved_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p07-m03-unverified141-") as tmp:
            root=Path(tmp)
            env=env_for(root)
            initial=run("bash",str(OLD),"install",env=env)
            self.assertEqual(initial.returncode,0,initial.stderr[-1000:])
            previous=root/"previous"
            previous.mkdir()
            (previous/"BUILD_ID").write_text("UNVERIFIED\n",encoding="utf-8")
            before=(root/"current/.runtime-manifest.gitblob").read_bytes()
            refused=run("bash",str(WRAPPER),"install",env=env)
            self.assertNotEqual(refused.returncode,0)
            self.assertIn("恢复目录",refused.stdout+refused.stderr)
            self.assertEqual((previous/"BUILD_ID").read_text(),"UNVERIFIED\n")
            self.assertEqual((root/"current/.runtime-manifest.gitblob").read_bytes(),before)
            self.assertFalse((root/"previous.preserved-0.1.0-release139").exists())

    def test_verified_backup_collision_stops_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p07-m03-collision141-") as tmp:
            root=Path(tmp)
            env=env_for(root)
            for script in (OLDER,OLD):
                result=run("bash",str(script),"install",env=env)
                self.assertEqual(result.returncode,0,result.stderr[-1000:])
            archive=root/"previous.preserved-0.1.0-release139"
            archive.mkdir()
            (archive/"canary").write_text("DO_NOT_OVERWRITE",encoding="utf-8")
            refused=run("bash",str(WRAPPER),"install",env=env)
            self.assertNotEqual(refused.returncode,0)
            self.assertEqual((archive/"canary").read_text(),"DO_NOT_OVERWRITE")
            self.assertEqual((root/"previous/BUILD_ID").read_text().strip(),"0.1.0-release139")
            self.assertEqual((root/"current/BUILD_ID").read_text().strip(),OLD_BUILD)

    def test_recover_original_backup_if_inner_installer_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p07-m03-recovery141-") as tmp:
            root=Path(tmp)
            env=env_for(root)
            for script in (OLDER,OLD):
                result=run("bash",str(script),"install",env=env)
                self.assertEqual(result.returncode,0,result.stderr[-1000:])
            content=WRAPPER.read_text(encoding="utf-8")
            expected='P07_PUBLIC_ROOT="file://$tmp/files" P07_NO_EXEC=1 bash "$tmp/files/installers/p07-final.sh"'
            self.assertEqual(content.count(expected),1)
            faulty=root/"injected-inner-error.sh"
            faulty.write_text(content.replace(expected,"false",1),encoding="utf-8")
            result=run("bash",str(faulty),"install",env=env)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((root/"current/BUILD_ID").read_text().strip(),OLD_BUILD)
            self.assertEqual((root/"previous/BUILD_ID").read_text().strip(),"0.1.0-release139")
            self.assertFalse((root/"previous.preserved-0.1.0-release139").exists())

    def test_corrupt_official_digest_stops_before_any_install(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p07-m03-corrupt141-") as tmp:
            root = Path(tmp)
            source = WRAPPER.read_text(encoding="utf-8")
            self.assertEqual(source.count(ZIP_SHA), 1)
            bad = root / "invalid.sh"
            bad.write_text(source.replace(ZIP_SHA, "0" * 64, 1), encoding="utf-8")
            env = env_for(root)
            failed = run("bash", str(bad), "install", env=env)
            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse((root / "current").exists())
            self.assertFalse((root / "previous").exists())
            self.assertFalse((root / "bin/vfops").exists())


if __name__ == "__main__":
    unittest.main()
