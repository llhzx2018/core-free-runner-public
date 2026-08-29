from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_main_push_provenance.py"
SPEC = importlib.util.spec_from_file_location("check_main_push_provenance", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


SHA = "a" * 40


class MainPushProvenanceTests(unittest.TestCase):
    def test_merged_pr_to_main_passes(self):
        def loader(repository: str, sha: str):
            self.assertEqual(repository, "llhzx2018/core-free-runner-public")
            self.assertEqual(sha, SHA)
            return [
                {
                    "merged_at": "2026-08-29T00:00:00Z",
                    "merge_commit_sha": SHA,
                    "base": {"ref": "main"},
                }
            ]

        self.assertEqual(
            MODULE.verify_main_push_provenance(
                "llhzx2018/core-free-runner-public", SHA, loader
            ),
            [],
        )

    def test_empty_associated_prs_are_rejected(self):
        failures = MODULE.verify_main_push_provenance(
            "llhzx2018/core-free-runner-public", SHA, lambda repository, sha: []
        )
        self.assertIn(f"MAIN_PUSH_NOT_FROM_MERGED_PR:{SHA}", failures)

    def test_pr_to_other_base_is_rejected(self):
        failures = MODULE.verify_main_push_provenance(
            "llhzx2018/core-free-runner-public",
            SHA,
            lambda repository, sha: [
                {
                    "merged_at": "2026-08-29T00:00:00Z",
                    "merge_commit_sha": SHA,
                    "base": {"ref": "develop"},
                }
            ],
        )
        self.assertIn(f"MAIN_PUSH_NOT_FROM_MERGED_PR:{SHA}", failures)

    def test_mismatched_merge_sha_is_rejected(self):
        failures = MODULE.verify_main_push_provenance(
            "llhzx2018/core-free-runner-public",
            SHA,
            lambda repository, sha: [
                {
                    "merged_at": "2026-08-29T00:00:00Z",
                    "merge_commit_sha": "b" * 40,
                    "base": {"ref": "main"},
                }
            ],
        )
        self.assertIn(f"MAIN_PUSH_NOT_FROM_MERGED_PR:{SHA}", failures)

    def test_invalid_identity_is_rejected_before_network(self):
        self.assertTrue(
            MODULE.verify_main_push_provenance(
                "bad-repository", SHA, lambda repository, sha: []
            )[0].startswith("MAIN_PUSH_REPOSITORY_INVALID")
        )
        self.assertTrue(
            MODULE.verify_main_push_provenance(
                "llhzx2018/core-free-runner-public", "not-a-sha", lambda repository, sha: []
            )[0].startswith("MAIN_PUSH_SHA_INVALID")
        )


if __name__ == "__main__":
    unittest.main()
