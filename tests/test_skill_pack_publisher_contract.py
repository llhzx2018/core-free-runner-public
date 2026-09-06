from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "gov-doc-skill-pack-publish.yml"
TRIGGER_SCRIPT = ROOT / "scripts" / "check_runner_trigger_scope.py"

SPEC = importlib.util.spec_from_file_location("check_runner_trigger_scope_for_publisher", TRIGGER_SCRIPT)
assert SPEC and SPEC.loader
TRIGGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRIGGER)


class SkillPackPublisherContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_publisher_is_manual_only(self) -> None:
        state = TRIGGER.classify(WORKFLOW)
        self.assertTrue(state["workflow_dispatch"])
        self.assertFalse(state["pull_request"])
        event = TRIGGER.event_block(WORKFLOW)
        self.assertNotIn("push:", event)

    def test_required_identity_and_confirmation_inputs_exist(self) -> None:
        for name in ("exact_source_sha", "pack_version", "build_id", "confirm_publish"):
            self.assertRegex(self.text, rf"(?m)^      {re.escape(name)}:$")
        self.assertIn("PUBLISH_BLOCK=EXPLICIT_CONFIRMATION_REQUIRED", self.text)
        self.assertIn("EXPECTED_GOV_DOC_SHA: ${{ inputs.exact_source_sha }}", self.text)
        self.assertIn("VF_SKILL_PACK_VERSION: ${{ inputs.pack_version }}", self.text)
        self.assertIn("VF_SKILL_BUILD_ID: ${{ inputs.build_id }}", self.text)

    def test_skill_set_and_asset_counts_are_manifest_driven(self) -> None:
        self.assertNotRegex(self.text, r"manifest\['skill_count'\]\s*==\s*11")
        self.assertNotRegex(self.text, r"len\(manifest\['skills'\]\)\s*==\s*11")
        self.assertNotIn("expected_assets = 16", self.text)
        self.assertNotIn("Expected Current Skills: `11`", self.text)
        self.assertIn("skill_count = manifest['skill_count']", self.text)
        self.assertIn("expected_assets = skill_count + 5", self.text)
        self.assertIn("len(all_zips) == skill_count + 1", self.text)

    def test_no_individual_skill_version_is_pinned_in_publisher(self) -> None:
        self.assertNotIn("skill-topic", self.text)
        self.assertNotIn("skill-book", self.text)
        self.assertNotRegex(self.text, r"assert .*version.*==\s*['\"]V\d")

    def test_distribution_mirror_remains_pr_gated(self) -> None:
        self.assertIn("GOV_DOC_DISTRIBUTION_MERGE_GATE=PENDING_PR", self.text)
        self.assertIn("'base': 'main'", self.text)
        self.assertNotIn("/merges", self.text)


if __name__ == "__main__":
    unittest.main()
