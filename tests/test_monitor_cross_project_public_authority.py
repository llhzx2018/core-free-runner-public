"""Synthetic positive + denial fixtures for the long-lived GOV-DOC monitor."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "monitor_cross_project_public_authority.py"
SPEC = importlib.util.spec_from_file_location("vf_monitor", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules["vf_monitor"] = module
SPEC.loader.exec_module(module)

A = "a" * 40
B = "b" * 40
C = "c" * 40


class FakeGitHub:
    def __init__(self):
        self.responses = {"/repos/llhzx2018/gov-doc/branches/main": {"commit": {"sha": B}}}
        for t in module.TARGETS:
            self.responses[f"/repos/{t.repo}/pulls/{t.pr}"] = {
                "number": t.pr, "state": "open", "merged": False,
                "user": {"login": "llhzx2018"},
                "head": {"repo": {"full_name": t.repo}, "ref": module.BRANCH, "sha": A},
                "base": {"ref": "main"},
            }
            self.responses[f"/repos/{t.repo}/branches/main"] = {"commit": {"sha": C}}

    def __call__(self, path):
        return self.responses[path]


class MonitorTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()
        self.t = module.TARGETS[0]
        self.url = f"/repos/{self.t.repo}/pulls/{self.t.pr}"

    def test_every_target_discovered(self):
        v = module.discover(self.gh)
        self.assertEqual(v["count"], "8")
        self.assertEqual(len(v["matrix"]["include"]), 8)
        self.assertEqual(v["gov_sha"], B)
        self.assertEqual({x["id"] for x in v["matrix"]["include"]}, set(module.INDEX))

    def test_valid_head_and_policy_current(self):
        module.verify_current(self.t, A, B, "pr", self.gh)

    def test_updated_head_blocks_stale_pass(self):
        self.gh.responses[self.url]["head"]["sha"] = C
        with self.assertRaisesRegex(module.MonitorError, "SOURCE_ADVANCED"):
            module.verify_current(self.t, A, B, "pr", self.gh)

    def test_updated_public_policy_blocks_stale_pass(self):
        self.gh.responses["/repos/llhzx2018/gov-doc/branches/main"]["commit"]["sha"] = C
        with self.assertRaisesRegex(module.MonitorError, "SOURCE_ADVANCED"):
            module.verify_current(self.t, A, B, "pr", self.gh)

    def test_pr_owner_must_match(self):
        self.gh.responses[self.url]["user"]["login"] = "outsider"
        with self.assertRaisesRegex(module.MonitorError, "TARGET_PR_SCOPE_UNTRUSTED"):
            module.discover(self.gh)

    def test_pr_repo_must_match(self):
        self.gh.responses[self.url]["head"]["repo"]["full_name"] = "outsider/fork"
        with self.assertRaisesRegex(module.MonitorError, "TARGET_PR_SCOPE_UNTRUSTED"):
            module.discover(self.gh)

    def test_pr_ref_must_match(self):
        self.gh.responses[self.url]["head"]["ref"] = "feature/unsafe"
        with self.assertRaisesRegex(module.MonitorError, "TARGET_PR_SCOPE_UNTRUSTED"):
            module.discover(self.gh)

    def test_pr_base_must_match(self):
        self.gh.responses[self.url]["base"]["ref"] = "releases"
        with self.assertRaisesRegex(module.MonitorError, "TARGET_PR_SCOPE_UNTRUSTED"):
            module.discover(self.gh)

    def test_closed_unmerged_fails_closed(self):
        self.gh.responses[self.url]["state"] = "closed"
        with self.assertRaisesRegex(module.MonitorError, "TARGET_PR_CLOSED_UNMERGED"):
            module.discover(self.gh)

    def test_merged_target_transitions_to_main(self):
        self.gh.responses[self.url]["state"] = "closed"
        self.gh.responses[self.url]["merged"] = True
        v = module.discover(self.gh)
        self.assertEqual(v["matrix"]["include"][0]["sha"], C)
        self.assertEqual(v["matrix"]["include"][0]["mode"], "main")
        module.verify_current(self.t, C, B, "main", self.gh)

    def test_invalid_main_sha_rejected(self):
        self.gh.responses["/repos/llhzx2018/gov-doc/branches/main"]["commit"]["sha"] = "not-a-sha"
        with self.assertRaisesRegex(module.MonitorError, "INVALID_EXACT_SHA"):
            module.discover(self.gh)

    def test_invalid_pr_sha_rejected(self):
        self.gh.responses[self.url]["head"]["sha"] = "x" * 40
        with self.assertRaisesRegex(module.MonitorError, "INVALID_EXACT_SHA"):
            module.discover(self.gh)

    def test_pr_identity_rejected(self):
        self.gh.responses[self.url]["number"] = 100
        with self.assertRaisesRegex(module.MonitorError, "PR_IDENTITY_CHANGED"):
            module.discover(self.gh)

    def test_marker_roundtrip_and_tamper(self):
        sig = module.marker_signature(self.t, A, B, "pr")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "proof"
            module.write_marker(p, sig)
            module.verify_marker(p, sig)
            p.write_text("forged", encoding="utf-8")
            with self.assertRaisesRegex(module.MonitorError, "CACHE_INVALID"):
                module.verify_marker(p, sig)

    def test_marker_new_commit_invalidates(self):
        sig = module.marker_signature(self.t, A, B, "pr")
        changed = module.marker_signature(self.t, C, B, "pr")
        self.assertNotEqual(sig, changed)

    def test_marker_new_policy_invalidates(self):
        self.assertNotEqual(module.marker_signature(self.t, A, B, "pr"),
                            module.marker_signature(self.t, A, C, "pr"))

    def test_marker_mode_invalidates(self):
        self.assertNotEqual(module.marker_signature(self.t, A, B, "pr"),
                            module.marker_signature(self.t, A, B, "main"))

    def test_marker_unknown_mode_denied(self):
        with self.assertRaisesRegex(module.MonitorError, "MODE_INVALID"):
            module.marker_signature(self.t, A, B, "other")

    def test_missing_api_token_denied(self):
        with self.assertRaisesRegex(module.MonitorError, "PRIVATE_READ_CAPABILITY_NOT_INJECTED"):
            module.github_json("/repos/llhzx2018/gov-doc/branches/main", "")

    def test_untrusted_api_target_denied(self):
        with self.assertRaisesRegex(module.MonitorError, "UNTRUSTED_GITHUB_API_PATH"):
            module.github_json("/repos/example/secret/../evil", "fake")

    def test_marker_missing_denied(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(module.MonitorError, "CACHE_INVALID"):
                module.verify_marker(Path(d) / "missing", "1" * 64)

    def test_all_target_branch_specs_are_unique(self):
        self.assertEqual(len({(t.repo, t.pr) for t in module.TARGETS}), 8)


if __name__ == "__main__":
    unittest.main()
