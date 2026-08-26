from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "workflow_archive.py"
SPEC = importlib.util.spec_from_file_location("workflow_archive", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkflowArchiveTests(unittest.TestCase):
    def test_repository_archive_manifest_is_exact(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(MODULE.verify(root), [])

    def test_manifest_contains_only_public_safe_metadata(self):
        root = Path(__file__).resolve().parents[1]
        value = MODULE.build_manifest(root)
        raw = json.dumps(value, ensure_ascii=False)
        self.assertEqual(value["entry_count"], 209)
        self.assertEqual(value["category_counts"]["historical-version"], 170)
        self.assertNotIn("secret", raw.lower())
        self.assertNotIn("private_data", raw.lower())

    def test_current_core_agent_harness_remains_active(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / ".github/workflows/core-agent-current-verify.yml").is_file())
        for name in MODULE.HISTORICAL_CORE_AGENT_NAMES:
            self.assertFalse((root / ".github/workflows" / name).exists())

    def test_p02_historical_workflows_are_not_registered(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(list((root / ".github/workflows").glob("p02*.yml")), [])
        archived = list((root / MODULE.ARCHIVE_BATCH / "historical-version" / "p02").glob("p02*.yml"))
        self.assertEqual(len(archived), 83)

    def test_p03_historical_workflows_are_not_registered(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(list((root / ".github/workflows").glob("p03*.yml")), [])
        archived = list((root / MODULE.ARCHIVE_BATCH / "historical-version" / "p03").glob("p03*.yml"))
        self.assertEqual(len(archived), 78)

    def test_active_source_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            destination = root / MODULE.ARCHIVE_BATCH / "temporary" / "temp-example.yml"
            destination.parent.mkdir(parents=True)
            destination.write_text("name: archived\n", encoding="utf-8")
            manifest = MODULE.build_manifest(root)
            target = root / MODULE.MANIFEST_PATH
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(manifest), encoding="utf-8")
            active = root / ".github/workflows/temp-example.yml"
            active.parent.mkdir(parents=True)
            active.write_text("name: active\n", encoding="utf-8")
            failures = MODULE.verify(root)
        self.assertTrue(any(item.startswith("SOURCE_STILL_ACTIVE") for item in failures))


if __name__ == "__main__":
    unittest.main()
