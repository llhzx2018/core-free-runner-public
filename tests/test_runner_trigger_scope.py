from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_runner_trigger_scope.py"
SPEC = importlib.util.spec_from_file_location("check_runner_trigger_scope", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RunnerTriggerScopeTests(unittest.TestCase):
    def test_no_legacy_quarantine_remains(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(MODULE.QUARANTINED_WORKFLOWS, ())
        self.assertEqual(MODULE.verify_quarantine(root), [])

    def test_unscoped_pull_request_is_classified(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "workflow.yml"
            path.write_text(
                "name: example\non:\n  pull_request:\npermissions:\n  contents: read\n",
                encoding="utf-8",
            )
            state = MODULE.classify(path)
        self.assertTrue(state["pull_request"])
        self.assertFalse(state["paths"])

    def test_manual_workflow_is_not_a_pull_request_trigger(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "workflow.yml"
            path.write_text(
                "name: example\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n",
                encoding="utf-8",
            )
            state = MODULE.classify(path)
        self.assertTrue(state["workflow_dispatch"])
        self.assertFalse(state["pull_request"])


if __name__ == "__main__":
    unittest.main()
