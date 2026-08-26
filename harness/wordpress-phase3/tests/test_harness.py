from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts/validate_job.py"
EXTRACTOR_PATH = ROOT / "scripts/safe_extract.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_module("validate_job", VALIDATOR_PATH)
EXTRACTOR = load_module("safe_extract", EXTRACTOR_PATH)


class HarnessContractTests(unittest.TestCase):
    def test_example_manifest_is_valid(self):
        data = json.loads((ROOT / "templates/job.example.json").read_text(encoding="utf-8"))
        VALIDATOR.validate(data)

    def test_source_path_escape_is_rejected(self):
        data = json.loads((ROOT / "templates/job.example.json").read_text(encoding="utf-8"))
        data["source"] = {"mode": "local_directory", "path": "../private", "exact_sha": "a" * 40}
        with self.assertRaises(SystemExit):
            VALIDATOR.validate(data)

    def test_zip_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr("../escape.txt", "unsafe")
            with self.assertRaises(SystemExit):
                EXTRACTOR.extract(archive, root / "out")

    def test_images_are_pinned(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("mariadb:11.8.8", compose)
        self.assertIn("wordpress:7.0.2-php8.4-apache", compose)
        self.assertNotIn(":latest", compose)

    def test_shell_scripts_parse(self):
        for path in (ROOT / "scripts/run_job.sh", ROOT / "scripts/runner_smoke.sh"):
            result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

