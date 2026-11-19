"""P07 public toolbox single anonymous install entry: real repo + negative fixtures."""
from __future__ import annotations

from pathlib import Path
import shutil
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
                     "installers/p07-m03-release140-atomic.sh"):
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
                        'VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release140"',
                        'VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release141"')
            with self.assertRaisesRegex(public_contract.PublicInstallContractError,
                                        "目标构建与实际安装器版本"):
                public_contract.validate(root)

    def test_old_zip_hash_removed_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp)
            self.update(root, "installers/p07-m03-release140-atomic.sh",
                        "ZIP_SHA256='8633631f76ca5ecd1a3c79e2edb64438eb920b6c5407fa5d5057611f9a7e77b8'",
                        "ZIP_SHA256='UNKNOWN'")
            with self.assertRaisesRegex(public_contract.PublicInstallContractError,
                                        "ZIP SHA256"):
                public_contract.validate(root)

    def test_public_toolbox_missing_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp)
            (root / public_contract.TOOLBOX).unlink()
            with self.assertRaisesRegex(public_contract.PublicInstallContractError,
                                        "缺少正式公共分发文件"):
                public_contract.validate(root)


if __name__ == "__main__":
    unittest.main()
