#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ephemeral_lane_worktree.py"


class EphemeralLaneWorktreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "runner-test@example.invalid")
        self.git("config", "user.name", "Runner Test")
        (self.repo / "VERSION").write_text("1.2.3\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("original\n", encoding="utf-8")
        self.git("add", "VERSION", "tracked.txt")
        self.git("commit", "-q", "-m", "fixture")
        self.sha = self.git("rev-parse", "HEAD").stdout.strip()
        self.tree = self.git("rev-parse", "HEAD^{tree}").stdout.strip()
        self.spec = self.dir / "lane.json"
        self.spec.write_text(json.dumps({
            "schema": "vf-ephemeral-lane-spec/v1",
            "lane_id": "runner-helper-test",
            "project_id": "P99",
            "repository": "example/private-product",
            "target_version": "1.2.3",
            "target_sha": self.sha,
            "target_tree": self.tree,
            "source_versions": ["1.2.2"],
            "schema_version": "1",
            "candidate_run": "",
            "previous_lane": {},
            "extra": {},
        }), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            text=True,
            capture_output=True,
            check=True,
        )

    def run_helper(self, *args):
        return subprocess.run(
            ["python3", str(SCRIPT), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_verify_exact_clean_worktree(self):
        result = self.run_helper(
            "verify", "--spec", self.spec, "--repo", self.repo,
            "--version-file", "VERSION",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["actual_sha"], self.sha)
        self.assertEqual(payload["actual_tree"], self.tree)
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["version_files"]["VERSION"], "1.2.3")

    def test_verify_rejects_dirty_source(self):
        (self.repo / "generated.tmp").write_text("dirty\n", encoding="utf-8")
        result = self.run_helper(
            "verify", "--spec", self.spec, "--repo", self.repo,
            "--version-file", "VERSION",
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["failure_class"], "HARNESS_IDENTITY_OR_BINDING")
        self.assertIn("WORKTREE_DIRTY", payload["failures"])

    def test_verify_rejects_version_mismatch(self):
        (self.repo / "VERSION").write_text("1.2.4\n", encoding="utf-8")
        result = self.run_helper(
            "verify", "--spec", self.spec, "--repo", self.repo,
            "--version-file", "VERSION", "--allow-dirty",
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertTrue(any("VERSION_MISMATCH" in x for x in payload["failures"]))

    def test_isolated_run_cannot_pollute_source_checkout(self):
        result = self.run_helper(
            "run-isolated", "--spec", self.spec, "--repo", self.repo,
            "--label", "mutation-proof", "--",
            "python3", "-c",
            "from pathlib import Path; Path('tracked.txt').write_text('mutated\\n'); Path('generated.tmp').write_text('x\\n')",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["status"], "PASS")
        self.assertTrue(payload["isolated_dirty"])
        self.assertTrue(payload["source_unchanged"])
        self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"), "original\n")
        self.assertFalse((self.repo / "generated.tmp").exists())
        self.assertEqual(self.git("status", "--porcelain").stdout, "")

    def test_failed_isolated_command_is_not_called_product_failure(self):
        result = self.run_helper(
            "run-isolated", "--spec", self.spec, "--repo", self.repo,
            "--label", "unknown-failure", "--",
            "python3", "-c", "raise SystemExit(7)",
        )
        self.assertEqual(result.returncode, 7)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["failure_class"], "UNRESOLVED_TEST_FAILURE")
        self.assertEqual(payload["command_exit_code"], 7)
        self.assertEqual(
            payload["next_classification"],
            ["PRODUCT", "CONTRACT", "HARNESS", "ENVIRONMENT"],
        )
        self.assertEqual(self.git("status", "--porcelain").stdout, "")


if __name__ == "__main__":
    unittest.main()
