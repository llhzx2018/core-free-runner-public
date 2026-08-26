from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "core_agent_runtime_ab.py"
SPEC = importlib.util.spec_from_file_location("core_agent_runtime_ab", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RuntimeABHarnessTests(unittest.TestCase):
    def test_test_count_uses_machine_evidence_without_persisting_logs(self):
        evidence = {
            "checks": [
                {"stdout": "", "stderr": "Ran 153 tests in 0.1s\nOK"},
                {"stdout": "unrelated", "stderr": ""},
            ]
        }
        self.assertEqual(MODULE._test_count(evidence), 153)

    def test_verification_result_is_public_safe_summary(self):
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw)
            (source / "scripts").mkdir()
            (source / "scripts" / "verify.py").write_text(
                "from pathlib import Path\n"
                "import json\n"
                "out=Path('.evidence/verification.json')\n"
                "out.parent.mkdir()\n"
                "out.write_text(json.dumps({'status':'PASS','checks':[{'stdout':'Ran 7 tests','stderr':'PRIVATE-LINE'}]}))\n",
                encoding="utf-8",
            )
            result = MODULE.run_verification(source, "a" * 40)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["test_count"], 7)
        self.assertNotIn("PRIVATE-LINE", repr(result))
        self.assertIn("private_evidence_sha256", result)

    def test_invalid_sha_is_rejected_before_source_execution(self):
        args = type("Args", (), {
            "baseline": Path("baseline"),
            "candidate": Path("candidate"),
            "baseline_sha": "not-a-sha",
            "candidate_sha": "b" * 40,
            "timeout": 1,
            "expect_baseline_version": "1.0.0",
            "expect_candidate_version": "1.1.0rc1",
        })()
        with self.assertRaisesRegex(RuntimeError, "INVALID_SOURCE_SHA"):
            MODULE.build_report(args)


if __name__ == "__main__":
    unittest.main()
