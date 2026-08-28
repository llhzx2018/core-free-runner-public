from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_estate_anti_drift.py"
SPEC = importlib.util.spec_from_file_location("check_estate_anti_drift", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _registry() -> dict:
    return {
        "schema": "vf.git-repository-registry.v1",
        "repositories": [
            {"repository": "llhzx2018/vf-start", "source_class": "VF_OWNED", "lifecycle": "ACTIVE", "route_status": "CURRENT_ROUTE"},
            {"repository": "llhzx2018/vf-forge", "source_class": "VF_OWNED", "lifecycle": "HISTORICAL", "route_status": "NON_AUTHORITY"},
            {"repository": "llhzx2018/core-agent", "source_class": "VF_OWNED", "lifecycle": "ACTIVE", "route_status": "CURRENT_ROUTE"},
            {"repository": "llhzx2018/core-updates", "source_class": "VF_OWNED", "lifecycle": "ACTIVE", "route_status": "CURRENT_ROUTE"},
            {"repository": "llhzx2018/core-free-runner-public", "source_class": "VF_OWNED", "lifecycle": "ACTIVE", "route_status": "CURRENT_ROUTE"},
            {"repository": "llhzx2018/core-free-runner-private", "source_class": "VF_OWNED", "lifecycle": "ACTIVE", "route_status": "CURRENT_ROUTE"},
            {"repository": "llhzx2018/gov-doc", "source_class": "VF_OWNED", "lifecycle": "ACTIVE", "route_status": "CURRENT_ROUTE"},
            {"repository": "llhzx2018/NotionNext", "source_class": "EXTERNAL_FORK", "lifecycle": "REFERENCE", "route_status": "NON_AUTHORITY", "upstream": "notionnext-org/NotionNext"},
            {"repository": "llhzx2018/core-test-runner", "source_class": "VF_OWNED", "lifecycle": "DELETED", "route_status": "TOMBSTONE"},
        ],
    }


def _authority() -> dict:
    return {
        "schema": "vf-agent-infra-authority/2",
        "status": "CURRENT",
        "public_runner": "llhzx2018/core-free-runner-public",
        "private_runner": "llhzx2018/core-free-runner-private",
        "hard_rules": {"allow_third_runner": False, "allow_third_credential": False},
        "legacy_runner_tombstone": {
            "canonical_id": "llhzx2018/core-test-runner",
            "state": "DELETED",
            "current_route": False,
            "compatibility_policy": "TOMBSTONE_AND_MIGRATION_EVIDENCE_ONLY",
        },
    }


class EstateAntiDriftTests(unittest.TestCase):
    def test_current_repository_workflows_are_read_only(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(MODULE.verify_local_workflows(root), [])

    def test_current_authority_invariants_pass(self):
        self.assertEqual(MODULE.verify_registry(_registry()), [])
        self.assertEqual(MODULE.verify_infra_authority(_authority()), [])

    def test_deleted_runner_cannot_reactivate(self):
        value = _registry()
        legacy = next(item for item in value["repositories"] if item["repository"] == "llhzx2018/core-test-runner")
        legacy["lifecycle"] = "ACTIVE"
        legacy["route_status"] = "CURRENT_ROUTE"
        failures = MODULE.verify_registry(value)
        self.assertIn("LEGACY_RUNNER_REACTIVATED", failures)

    def test_p03_cannot_silently_return_to_current_route(self):
        value = _registry()
        p03 = next(item for item in value["repositories"] if item["repository"] == "llhzx2018/vf-forge")
        p03["lifecycle"] = "ACTIVE"
        p03["route_status"] = "CURRENT_ROUTE"
        failures = MODULE.verify_registry(value)
        self.assertIn("P03_ROUTE_NOT_RETIRED", failures)

    def test_external_fork_cannot_become_authority(self):
        value = _registry()
        fork = next(item for item in value["repositories"] if item["repository"] == "llhzx2018/NotionNext")
        fork["lifecycle"] = "ACTIVE"
        fork["route_status"] = "CURRENT_ROUTE"
        failures = MODULE.verify_registry(value)
        self.assertTrue(any(item.startswith("EXTERNAL_FORK_ROUTE") for item in failures))

    def test_dynamic_observation_cannot_enter_registry(self):
        value = _registry()
        value["repositories"][0]["main_sha"] = "0" * 40
        failures = MODULE.verify_registry(value)
        self.assertTrue(any(item.startswith("REGISTRY_DYNAMIC_FIELD") for item in failures))

    def test_legacy_runner_active_key_is_rejected(self):
        value = _authority()
        value["legacy_runner"] = "llhzx2018/core-test-runner"
        self.assertIn("LEGACY_RUNNER_ACTIVE_KEY_PRESENT", MODULE.verify_infra_authority(value))

    def test_write_capable_current_workflow_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "runner-selftest-current.yml").write_text(
                "name: bad\npermissions:\n  contents: write\nsteps:\n  - run: git push origin HEAD:main\n",
                encoding="utf-8",
            )
            (workflows / "core-agent-current-verify.yml").write_text(
                "permissions:\n  contents: read\nref: main\nrun: git -C source rev-parse HEAD\n",
                encoding="utf-8",
            )
            failures = MODULE.verify_local_workflows(root)
        self.assertTrue(any(item.startswith("CURRENT_WORKFLOW_CONTENTS_WRITE") for item in failures))
        self.assertTrue(any(item.startswith("CURRENT_WORKFLOW_DIRECT_GIT_PUSH") for item in failures))

    def test_hardcoded_core_agent_sha_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "core-agent-current-verify.yml").write_text(
                "permissions:\n  contents: read\nenv:\n  CORE_AGENT_SOURCE_SHA: " + "a" * 40 + "\nref: main\nrun: git -C source rev-parse HEAD\n",
                encoding="utf-8",
            )
            failures = MODULE.verify_local_workflows(root)
        self.assertIn("CORE_AGENT_CURRENT_HARDCODED_SHA", failures)


if __name__ == "__main__":
    unittest.main()
