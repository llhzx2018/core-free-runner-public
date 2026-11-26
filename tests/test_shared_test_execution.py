import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from shared_test_execution import discover_stack, run_trusted_phase

class SharedExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}

    def run_phase(self, source, **kwargs):
        return run_trusted_phase([sys.executable, "-c", source],
                                 cwd=self.root, env=self.env,
                                 phase="synthetic", timeout=kwargs.pop("timeout", 5), **kwargs)

    def test_real_process_and_explicit_environment(self):
        r = self.run_phase("import os; assert 'GITHUB_TOKEN' not in os.environ; print('raw-private')")
        self.assertTrue(r.ok)
        self.assertIn(b"raw-private", r.private_output)
        self.assertNotIn("raw-private", json.dumps(r.receipt()))

    def test_failure_classification_not_raw_output(self):
        r = self.run_phase("import sys; print('Permission denied: private-file'); sys.exit(7)")
        self.assertFalse(r.ok)
        self.assertEqual((r.exit_code, r.reason), (7, "PERMISSION_DENIED"))
        self.assertNotIn("private-file", json.dumps(r.receipt()))

    def test_actual_junit_failure(self):
        p = self.root / "report.xml"
        r = self.run_phase("from pathlib import Path; import sys; Path('report.xml').write_text('<testsuite><testcase name=\"test_login\"><failure message=\"expected response status 200\"/></testcase></testsuite>'); sys.exit(1)",
                           junit=p, known_names=frozenset({"test_login"}))
        self.assertEqual(r.reason, "REPORTED_TEST_FAILURE")
        self.assertEqual(r.report["failures"][0]["test"], "test_login")

    def test_zero_exit_with_failed_or_missing_report_is_not_pass(self):
        p = self.root / "report.xml"
        r = self.run_phase("pass", junit=p)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "REPORT_INCONSISTENT_OR_MISSING")
        r = self.run_phase("from pathlib import Path; Path('report.xml').write_text('<testsuite><testcase name=\"test_a\"><failure/></testcase></testsuite>')", junit=p)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "REPORT_INCONSISTENT_OR_MISSING")

    def test_timeout_is_not_test_pass(self):
        r = self.run_phase("import time; time.sleep(30)", timeout=1)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "PROCESS_TIMEOUT")

    def test_stale_or_symlink_report_denied(self):
        p = self.root / "report.xml"
        p.write_text("<testsuite/>")
        with self.assertRaisesRegex(ValueError, "REPORT_ALREADY_EXISTS"):
            self.run_phase("pass", junit=p)
        p.unlink()
        p.symlink_to(self.root / "absent")
        with self.assertRaisesRegex(ValueError, "REPORT_ALREADY_EXISTS"):
            self.run_phase("pass", junit=p)

    def test_missing_executable(self):
        r = run_trusted_phase([str(self.root / "absent")], cwd=self.root,
                              env=self.env, phase="synthetic", timeout=2)
        self.assertEqual(r.reason, "EXECUTABLE_MISSING")
        self.assertFalse(r.ok)

    def test_stack_detection_is_only_advisory(self):
        (self.root / "composer.json").write_text('{"require":{"laravel/framework":"*"},"require-dev":{"phpunit/phpunit":"*"}}')
        (self.root / "package.json").write_text('{"devDependencies":{"vue":"*","vitest":"*","@playwright/test":"*","vite":"*"}}')
        (self.root / "Dockerfile").touch()
        (self.root / "tests").mkdir()
        (self.root / "tests/test_a.py").touch()
        (self.root / "bin").mkdir()
        (self.root / "bin/check.sh").touch()
        self.assertEqual(set(discover_stack(self.root)), {"php","composer","laravel","phpunit","node","vue","vitest","vite","playwright","docker","python","shell"})
        self.assertNotIn("mysql", discover_stack(self.root))

if __name__ == "__main__":
    unittest.main()
