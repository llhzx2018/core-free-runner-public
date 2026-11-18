"""Build/byte-verify isolated unpublished P07-M01/M02/M04 UX candidates.

No system package manager, real module root, installer, network or GitHub write.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_p07_ux_prepublication_candidates.py"
spec = importlib.util.spec_from_file_location("p07_ux_builder", SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class UXPrepublicationBundleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="p07-ux-prepublication-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.run_build(self.output)

    def run_build(self, directory):
        p = subprocess.run([sys.executable, "-B", str(SCRIPT),
                            "--output-dir", str(directory)],
                           capture_output=True, text=True, timeout=20,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("P07_UX_UNPUBLISHED_THREE_MODULE_PACKAGE_CANDIDATES=PASS", p.stdout)
        self.assertIn("P07_FORMAL_RELEASE_DISTRIBUTION_PRODUCTION=NOT_RUN", p.stdout)

    def bundle(self, code):
        names = list(self.output.glob(f"{code}-*-DEV-ONLY.zip"))
        self.assertEqual(len(names), 1, names)
        return names[0]

    def test_three_module_zips_are_complete_and_signed(self):
        for code, version in (("P07-M01", "0.1.0-ux3"),
                              ("P07-M02", "2.1.1-ux3"),
                              ("P07-M04", "0.1.0-ux5")):
            with self.subTest(module=code):
                artifact = self.bundle(code)
                builder.verify_zip(artifact, code, version)
                with zipfile.ZipFile(artifact) as zipf:
                    names = set(zipf.namelist())
                    self.assertIn("SHA256SUMS", names)
                    self.assertIn("VERSION", names)
                    self.assertIn("PREPUBLISH_METADATA.json", names)
                    metadata = json.loads(zipf.read("PREPUBLISH_METADATA.json"))
                    self.assertEqual(metadata["status"], "DEVELOPMENT_STAGING_ONLY")
                    self.assertFalse(metadata["formal_release"])
                    self.assertFalse(metadata["production_run"])
                    if code == "P07-M01":
                        self.assertIn("MANIFEST.sha256", names)
                        self.assertIn("uninstall.sh", names)
                        self.assertIn("lib/core-pin.env", names)
                    if code == "P07-M04":
                        self.assertIn("MANIFEST.gitblob", names)
                        self.assertIn("lib/resource_apply.py", names)
                        self.assertIn("security-audit.sh", names)

    def test_build_twice_produces_identical_zip_bytes(self):
        second = self.root / "build-again"
        second.mkdir()
        self.run_build(second)
        for file in self.output.iterdir():
            self.assertEqual(file.read_bytes(), (second / file.name).read_bytes(), file.name)

    def test_master_sha256s_match_all_three_real_zip_files(self):
        lines = (self.output / "SHA256SUMS").read_text().splitlines()
        self.assertEqual(len(lines), 3)
        for line in lines:
            digest, name = line.split("  ")
            self.assertEqual(digest, hashlib.sha256((self.output / name).read_bytes()).hexdigest())
            self.assertIn("DEV-ONLY", name)

    def test_modified_archive_member_is_rejected(self):
        artifact = self.bundle("P07-M02")
        changed = self.root / "tampered.zip"
        with zipfile.ZipFile(artifact) as source, zipfile.ZipFile(changed, "w") as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == "vps-audit.sh":
                    data += b"\n# unexpected external modification\n"
                target.writestr(info, data)
        with self.assertRaisesRegex(ValueError, "tamper|mismatch"):
            builder.verify_zip(changed, "P07-M02", "2.1.1-ux3")

    def test_reject_wrong_module_identity_and_unexpected_output_files(self):
        with self.assertRaises(ValueError):
            builder.verify_zip(self.bundle("P07-M02"), "P07-M04", "0.1.0-ux5")
        nonempty = self.root / "not-empty"
        nonempty.mkdir()
        (nonempty / "kept").write_text("do not overwrite")
        p = subprocess.run([sys.executable, "-B", str(SCRIPT),
                            "--output-dir", str(nonempty)],
                           capture_output=True, text=True, timeout=15)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("must be empty", p.stderr)
        self.assertEqual((nonempty / "kept").read_text(), "do not overwrite")

    def test_current_published_files_are_still_unchanged(self):
        b = (ROOT / "packages/p07-network-node/0.1.0-ux2")
        m = builder.verified_inventory(b, "MANIFEST.sha256",
                                       builder.SHA256_LINE, builder.sha256)
        self.assertEqual(m["VERSION"], b"0.1.0-ux2\n")
        old_care = (ROOT / "packages/p07-system-care/0.1.0-ux4")
        cm = builder.verified_inventory(old_care, "MANIFEST.gitblob",
                                        builder.GITBLOB_LINE, builder.blob)
        self.assertEqual(cm["VERSION"], b"0.1.0-ux4\n")
        self.assertNotEqual(m["vf-node.sh"], builder.make_m01()["vf-node.sh"])
        self.assertNotEqual(cm["vf-system-care.sh"], builder.make_m04()["vf-system-care.sh"])

    def test_real_shell_help_and_version_work_from_extracted_zip(self):
        for code, entry, args, expected in (
            ("P07-M01", "vf-node.sh", ("--help",), "网络代理节点"),
            ("P07-M02", "vps-audit.sh", ("--version",), "V2.1.1"),
            ("P07-M04", "vf-system-care.sh", ("--version",), "0.1.0-ux5"),
        ):
            with self.subTest(module=code):
                location = self.root / ("extract-" + code)
                with zipfile.ZipFile(self.bundle(code)) as z:
                    z.extractall(location)
                p = subprocess.run(["bash", str(location / entry), *args],
                                   capture_output=True, text=True, timeout=15,
                                   env={**os.environ, "NO_COLOR": "1"})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertIn(expected, p.stdout)
                self.assertNotIn("\033[", p.stdout)

    def test_synthetic_independent_switch_and_failure_rollback(self):
        """A synthetic atomic pointer, NOT a test of real installer or Production."""
        fixture = self.root / "five-modules"
        for code in ("P07-M01", "P07-M02", "P07-M03", "P07-M04", "P07-M05"):
            root = fixture / code
            (root / "releases" / "previous").mkdir(parents=True)
            (root / "releases" / "previous" / "MARK").write_text("untouched-" + code)
            (root / "current").symlink_to("releases/previous", target_is_directory=True)
        def digest_tree(path):
            out = []
            for p in sorted(path.rglob("*")):
                if p.is_file():
                    out.append((str(p.relative_to(path)),
                                hashlib.sha256(p.read_bytes()).hexdigest()))
            return out
        for code in ("P07-M01", "P07-M02", "P07-M04"):
            before = {x: digest_tree(fixture / x) for x in ("P07-M01", "P07-M02", "P07-M03", "P07-M04", "P07-M05") if x != code}
            root = fixture / code
            next_dir = root / "releases" / "candidate"
            next_dir.mkdir()
            (next_dir / "MARK").write_bytes(self.bundle(code).read_bytes()[:64])
            tmp_link = root / "future"
            tmp_link.symlink_to("releases/candidate", target_is_directory=True)
            os.replace(tmp_link, root / "current")
            self.assertEqual((root / "current").resolve(), next_dir.resolve())
            # A simulated failure must restore this module's previous symlink.
            tmp_link.symlink_to("releases/previous", target_is_directory=True)
            os.replace(tmp_link, root / "current")
            self.assertEqual((root / "current").resolve(),
                             (root / "releases/previous").resolve())
            for other, files in before.items():
                self.assertEqual(files, digest_tree(fixture / other), other)

if __name__ == "__main__":
    unittest.main()
