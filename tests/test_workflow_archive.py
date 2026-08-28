from __future__ import annotations

import importlib.util
import json
import re
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
        self.assertEqual(value["schema"], "core-free-runner-workflow-archive/v11")
        self.assertEqual(value["entry_count"], 507)
        self.assertEqual(value["category_counts"]["historical-version"], 382)
        self.assertEqual(value["category_counts"]["late-active"], 86)
        self.assertEqual(value["delta"]["git_tree_sha"], MODULE.LATE_BATCH_TREE_SHA)
        self.assertEqual(value["delta"]["source_commit"], MODULE.LATE_BATCH_SOURCE_COMMIT)
        self.assertEqual(value["active_current_workflows"], sorted(MODULE.ACTIVE_CURRENT_WORKFLOW_NAMES))

        v10 = MODULE.build_v10_manifest(root)
        raw = json.dumps(v10, ensure_ascii=False)
        self.assertEqual(v10["entry_count"], 421)
        allowed_keys = {"source_path", "archive_path", "category", "source_commit", "bytes", "sha256"}
        for entry in v10["entries"]:
            self.assertEqual(set(entry), allowed_keys)
            self.assertNotIn("\n", entry["source_path"])
            self.assertNotIn("\n", entry["archive_path"])
            self.assertEqual(len(entry["source_commit"]), 40)
            self.assertEqual(len(entry["sha256"]), 64)
        self.assertNotIn("${{ secrets.", raw.lower())
        self.assertNotIn("private_data", raw.lower())

    def test_late_active_batch_is_tree_locked(self):
        root = Path(__file__).resolve().parents[1]
        archived = list((root / MODULE.LATE_BATCH).glob("*.yml"))
        self.assertEqual(len(archived), 86)
        self.assertEqual(MODULE._git_tree_sha(root, MODULE.LATE_BATCH), MODULE.LATE_BATCH_TREE_SHA)
        active = {path.name for path in (root / ".github/workflows").glob("*.yml")}
        self.assertTrue(active.isdisjoint({path.name for path in archived}))

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

    def test_p04_historical_workflows_are_not_registered(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(list((root / ".github/workflows").glob("p04*.yml")), [])
        archived = list((root / MODULE.ARCHIVE_BATCH / "historical-version" / "p04").glob("p04*.yml"))
        self.assertEqual(len(archived), 67)

    def test_p05_historical_workflows_are_not_registered(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(list((root / ".github/workflows").glob("p05*.yml")), [])
        archived = list((root / MODULE.ARCHIVE_BATCH / "historical-version" / "p05").glob("p05*.yml"))
        self.assertEqual(len(archived), 17)

    def test_p06_historical_workflows_are_not_registered(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(list((root / ".github/workflows").glob("p06*.yml")), [])
        archived = list((root / MODULE.ARCHIVE_BATCH / "historical-version" / "p06").glob("p06*.yml"))
        self.assertEqual(len(archived), 62)

    def test_p01_historical_workflows_are_not_registered(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(list((root / ".github/workflows").glob("p01*.yml")), [])
        archived = list((root / MODULE.ARCHIVE_BATCH / "historical-version" / "p01").glob("p01*.yml"))
        self.assertEqual(len(archived), 58)

    def test_s01_historical_workflows_are_not_registered(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(list((root / ".github/workflows").glob("s01*.yml")), [])
        archived = list((root / MODULE.ARCHIVE_BATCH / "historical-version" / "s01").glob("s01*.yml"))
        self.assertEqual(len(archived), 6)

    def test_active_current_workflow_allowlist_is_exact(self):
        root = Path(__file__).resolve().parents[1]
        active = {path.name for path in (root / ".github/workflows").glob("*.yml")}
        self.assertEqual(active, MODULE.ACTIVE_CURRENT_WORKFLOW_NAMES)
        archived = list((root / MODULE.ARCHIVE_BATCH / "historical-version" / "public-infrastructure").glob("*.yml"))
        self.assertEqual(len(archived), 2)

    def test_current_actions_use_approved_node24_pins(self):
        root = Path(__file__).resolve().parents[1]
        approved = {
            "actions/checkout": {
                "d23441a48e516b6c34aea4fa41551a30e30af803",  # releases-v6 Node24
                "3d3c42e5aac5ba805825da76410c181273ba90b1",  # v7.0.1 Node24
            },
            "actions/setup-python": {
                "5fda3b95a4ea91299a34e894583c3862153e4b97",  # v7.0.0 Node24
            },
            "actions/upload-artifact": {
                "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",  # v7.0.1 Node24
            },
        }
        pattern = re.compile(
            r"^\s*uses:\s*(actions/(?:checkout|setup-python|upload-artifact))@([^\s#]+)",
            re.MULTILINE,
        )
        found: list[tuple[str, str, str]] = []
        for path in sorted((root / ".github/workflows").glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            for action, ref in pattern.findall(text):
                found.append((path.name, action, ref))
                self.assertRegex(ref, r"^[0-9a-f]{40}$")
                self.assertIn(ref, approved[action])
        for action in approved:
            self.assertTrue(any(found_action == action for _, found_action, _ in found))

    def test_active_source_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            destination = root / MODULE.ARCHIVE_BATCH / "temporary" / "temp-example.yml"
            destination.parent.mkdir(parents=True)
            destination.write_text("name: archived\n", encoding="utf-8")
            active = root / ".github/workflows/temp-example.yml"
            active.parent.mkdir(parents=True)
            active.write_text("name: active\n", encoding="utf-8")
            failures = MODULE.verify(root)
        self.assertTrue(any(item.startswith("SOURCE_STILL_ACTIVE") for item in failures))


if __name__ == "__main__":
    unittest.main()
