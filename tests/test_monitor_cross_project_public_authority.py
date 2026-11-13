"""Positive and denial fixtures: read-only refs, scope binding, caching."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "monitor_cross_project_public_authority.py"
SPEC = importlib.util.spec_from_file_location("vf_monitor", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules["vf_monitor"] = module
SPEC.loader.exec_module(module)

A = "a" * 40
B = "b" * 40
C = "c" * 40


class FakeRefs:
    def __init__(self):
        self.refs = {(module.GOV_REPO, "refs/heads/main"): B}
        for t in module.TARGETS:
            self.refs[(t.repo, f"refs/pull/{t.pr}/head")] = A
            self.refs[(t.repo, "refs/heads/" + module.BRANCH)] = A

    def __call__(self, repo, refs):
        return {ref: self.refs[(repo, ref)] for ref in refs}


class MonitorTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeRefs()
        self.t = module.TARGETS[0]
        self.prref = (self.t.repo, f"refs/pull/{self.t.pr}/head")
        self.branchref = (self.t.repo, "refs/heads/" + module.BRANCH)

    def test_eight_current_targets(self):
        v = module.discover(self.fake)
        self.assertEqual(v["count"], "8")
        self.assertEqual(len(v["matrix"]["include"]), 8)
        self.assertEqual({x["id"] for x in v["matrix"]["include"]}, set(module.INDEX))
        self.assertEqual(v["gov_sha"], B)

    def test_source_and_policy_recheck_success(self):
        module.verify_current(self.t, A, B, "pr", self.fake)

    def test_product_ref_advanced_rejected(self):
        self.fake.refs[self.prref] = C
        self.fake.refs[self.branchref] = C
        with self.assertRaisesRegex(module.MonitorError, "SOURCE_ADVANCED"):
            module.verify_current(self.t, A, B, "pr", self.fake)

    def test_gov_policy_advanced_rejected(self):
        self.fake.refs[(module.GOV_REPO, "refs/heads/main")] = C
        with self.assertRaisesRegex(module.MonitorError, "SOURCE_ADVANCED"):
            module.verify_current(self.t, A, B, "pr", self.fake)

    def test_source_ref_and_branch_mismatch(self):
        self.fake.refs[self.branchref] = C
        with self.assertRaisesRegex(module.MonitorError, "PR_BRANCH_SOURCE_MISMATCH"):
            module.discover(self.fake)

    def test_deleted_branch_rejected(self):
        del self.fake.refs[self.branchref]
        with self.assertRaises(KeyError):
            module.discover(self.fake)

    def test_deleted_pr_ref_rejected(self):
        del self.fake.refs[self.prref]
        with self.assertRaises(KeyError):
            module.discover(self.fake)

    def test_invalid_source_sha(self):
        self.fake.refs[self.prref] = "not-a-sha"
        with self.assertRaisesRegex(module.MonitorError, "INVALID_EXACT_SHA"):
            module.discover(self.fake)

    def test_invalid_governance_sha(self):
        self.fake.refs[(module.GOV_REPO, "refs/heads/main")] = "x" * 40
        with self.assertRaisesRegex(module.MonitorError, "INVALID_EXACT_SHA"):
            module.discover(self.fake)

    def test_static_owner_and_repo_allowlist(self):
        self.assertEqual(len({(t.repo, t.pr) for t in module.TARGETS}), 8)
        self.assertTrue(all(t.repo.startswith("llhzx2018/") for t in module.TARGETS))

    def test_cache_roundtrip_and_tamper(self):
        sig = module.marker_signature(self.t, A, B, "pr")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"marker"
            module.write_marker(path, sig)
            module.verify_marker(path, sig)
            path.write_text("forged", encoding="utf-8")
            with self.assertRaisesRegex(module.MonitorError, "CACHE_INVALID"):
                module.verify_marker(path, sig)

    def test_cache_invalidated_when_product_changes(self):
        self.assertNotEqual(module.marker_signature(self.t, A, B, "pr"),
                            module.marker_signature(self.t, C, B, "pr"))

    def test_cache_invalidated_when_policy_changes(self):
        self.assertNotEqual(module.marker_signature(self.t, A, B, "pr"),
                            module.marker_signature(self.t, A, C, "pr"))

    def test_cache_mode_is_bound(self):
        self.assertNotEqual(module.marker_signature(self.t, A, B, "pr"),
                            module.marker_signature(self.t, A, B, "main"))

    def test_cache_invalid_mode_rejected(self):
        with self.assertRaisesRegex(module.MonitorError, "MODE_INVALID"):
            module.marker_signature(self.t, A, B, "injected")

    def test_cache_missing_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(module.MonitorError, "CACHE_INVALID"):
                module.verify_marker(Path(d)/"missing", "f" * 64)

    def test_private_read_token_required(self):
        with self.assertRaisesRegex(module.MonitorError, "PRIVATE_READ_CAPABILITY"):
            module.git_refs(module.GOV_REPO, ("refs/heads/main",), "")

    def test_unapproved_repository_rejected(self):
        with self.assertRaisesRegex(module.MonitorError, "UNTRUSTED_GIT_REPOSITORY"):
            module.git_refs("evil/private", ("refs/heads/main",), "fake")

    def test_unapproved_ref_rejected(self):
        with self.assertRaisesRegex(module.MonitorError, "UNTRUSTED_GIT_REFERENCE"):
            module.git_refs(self.t.repo, ("refs/heads/production",), "fake")

    def test_read_only_git_refs_success(self):
        text = A + "\trefs/pull/" + str(self.t.pr) + "/head\n"
        with patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=text)) as mocked:
            refs = module.git_refs(self.t.repo, (f"refs/pull/{self.t.pr}/head",), "fake")
        self.assertEqual(refs[f"refs/pull/{self.t.pr}/head"], A)
        argv = mocked.call_args.args[0]
        self.assertIn("ls-remote", argv)
        self.assertNotIn("fake", " ".join(argv))

    def test_git_ref_mismatch_rejected(self):
        with patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=A + "\trefs/heads/other\n")):
            with self.assertRaisesRegex(module.MonitorError, "UNEXPECTED_GIT_REF_OUTPUT"):
                module.git_refs(module.GOV_REPO, ("refs/heads/main",), "fake")

    def test_git_ref_missing_rejected(self):
        with patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="")):
            with self.assertRaisesRegex(module.MonitorError, "GIT_REF_INCOMPLETE"):
                module.git_refs(module.GOV_REPO, ("refs/heads/main",), "fake")

    def test_git_permission_denial_rejected(self):
        with patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=128, stdout="")):
            with self.assertRaisesRegex(module.MonitorError, "READ_ONLY_GIT_REF_DENIED"):
                module.git_refs(module.GOV_REPO, ("refs/heads/main",), "fake")


if __name__ == "__main__":
    unittest.main()
