"""P07 public toolbox single anonymous install entry: real repo + negative fixtures."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_p07_public_install_contract as public_contract


class PublicSingleEntryTests(unittest.TestCase):
    def setUp(self):
        self.assertIn("STRUCTURAL_PASS", public_contract.validate())

    def fixture(self, directory):
        root = Path(directory)
        for name in (*public_contract.DOCUMENTS, public_contract.TOOLBOX,
                     "installers/p07-m03-release146-atomic.sh"):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        return root

    def update(self, root, file, before, after):
        path = root / file
        text = path.read_text(encoding="utf-8")
        self.assertIn(before, text)
        path.write_text(text.replace(before, after, 1), encoding="utf-8")

    def test_one_correct_public_command_has_no_user_login(self):
        self.assertIn("STRUCTURAL_PASS", public_contract.validate())
        self.assertIn("core-free-runner-public/main/installers/p07-toolbox.sh",
                      public_contract.COMMAND)

    def test_wrong_user_public_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp)
            self.update(root, "README.md", public_contract.COMMAND,
                        public_contract.COMMAND.replace("p07-toolbox.sh", "p07-custom.sh"))
            with self.assertRaisesRegex(public_contract.PublicInstallContractError, "公共 SSH"):
                public_contract.validate(root)

    def test_second_command_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp)
            file = root / "docs/authority/P07_PUBLIC_INSTALL_CONTRACT.md"
            with file.open("a", encoding="utf-8") as f:
                f.write("\n" + public_contract.COMMAND + "\n")
            with self.assertRaisesRegex(public_contract.PublicInstallContractError, "唯一正确"):
                public_contract.validate(root)

    def test_private_bootstrap_or_gh_auth_is_rejected(self):
        for injected in ("\ngh auth login --web\n",
                         "\ngit clone https://github.com/owner/private\n",
                         "\nGH_TOKEN=secret\n",
                         "\n# core-free-runner-private\n"):
            with self.subTest(injected=injected):
                with tempfile.TemporaryDirectory() as tmp:
                    root = self.fixture(tmp)
                    with (root / public_contract.TOOLBOX).open("a", encoding="utf-8") as f:
                        f.write(injected)
                    with self.assertRaisesRegex(public_contract.PublicInstallContractError,
                                                "用户认证或私有仓"):
                        public_contract.validate(root)

    def test_wrong_m03_version_pin_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp)
            self.update(root, public_contract.TOOLBOX,
                        'VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release146"',
                        'VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release143"')
            with self.assertRaisesRegex(public_contract.PublicInstallContractError,
                                        "目标构建与实际安装器版本"):
                public_contract.validate(root)

    def test_old_zip_hash_removed_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp)
            self.update(root, "installers/p07-m03-release146-atomic.sh",
                        "ZIP_SHA256='7b3e46c651c5ce3597e4ab535fbdc734023fc1b706fe85189a344ee600514321'",
                        "ZIP_SHA256='UNKNOWN'")
            with self.assertRaisesRegex(public_contract.PublicInstallContractError,
                                        "ZIP SHA256"):
                public_contract.validate(root)

    def test_m05_ux12_recognizes_ux11_and_requires_interactive_upgrade(self):
        toolbox = (ROOT / public_contract.TOOLBOX).read_text(encoding="utf-8")
        self.assertIn('M05_BUILD_EXPECTED="0.1.0-m05-ux12-apt-failstop"', toolbox)
        self.assertIn('M05_PREVIOUS_OFFICIAL_BUILD="0.1.0-m05-ux11-toolbox-lock"', toolbox)
        self.assertIn('M05_BUNDLE_SHA256="424ff9b90d9ce1c5d2b8de9773fb3350d959d8a5f030580e568918a7bc66d279"', toolbox)
        self.assertIn("p07-m05-v0.1.0-ux12-apt-failstop-20261122/P07-M05-0.1.0-m05-ux12-apt-failstop.zip", toolbox)
        self.assertIn('M05_UPGRADE_FROM17="0.1.0-m05-ux10-bootstrap-ux-failstop"', toolbox)
        self.assertIn('"releases/$M05_UPGRADE_FROM17")', toolbox)
        pins = "\n".join(re.findall(r"(?m)^M05_[A-Z0-9_]+=.*$", toolbox))
        ensure = re.search(r"(?ms)^ensure_m05_current\(\) \{\n.*?^\}$", toolbox)
        self.assertIsNotNone(ensure)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "current").symlink_to("releases/0.1.0-m05-ux11-toolbox-lock")
            script = "\n".join((
                "set -euo pipefail",
                pins,
                'M05_ROOT="$P07_TEST_ROOT"',
                'say() { printf "%s\\n" "$*"; }',
                "m05_verified_current() { return 0; }",
                'curl() { echo "unexpected download"; return 1; }',
                ensure.group(),
                "ensure_m05_current",
            ))
            run = subprocess.run(
                ["bash", "-c", script], stdin=subprocess.DEVNULL, text=True,
                capture_output=True, env={**os.environ, "P07_TEST_ROOT": tmp}, timeout=10,
            )
            self.assertEqual(run.returncode, 7, run.stderr)
            self.assertIn("发现官方旧版 0.1.0-m05-ux11-toolbox-lock", run.stdout)
            self.assertIn("请在交互式 SSH 中确认升级", run.stdout)
            self.assertNotIn("unexpected download", run.stdout)
            self.assertEqual((Path(tmp) / "current").readlink(),
                             Path("releases/0.1.0-m05-ux11-toolbox-lock"))

    def test_public_toolbox_missing_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp)
            (root / public_contract.TOOLBOX).unlink()
            with self.assertRaisesRegex(public_contract.PublicInstallContractError,
                                        "缺少正式公共分发文件"):
                public_contract.validate(root)


if __name__ == "__main__":
    unittest.main()
