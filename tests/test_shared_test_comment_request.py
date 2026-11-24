import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from shared_test_comment_request import OWNER, CONTROL_PR, PREFIX, parse_owner_comment, InvalidTask


def request():
    return {
        "schema": "vf-shared-test-job/v1", "task_id": "vf-p02-20261124-comment-01",
        "project": "P02",
        "source": {"repo": "llhzx2018/vf-doc", "sha": "a" * 40, "tree_sha": "b" * 40},
        "test_id": "git-integrity", "kind": "unit", "privacy": "PUBLIC_SAFE",
        "profile": "light", "timeout_seconds": 90, "submitted_at": 1,
        "allow_public_ephemeral": False,
    }


def event(job=None):
    return {
        "action": "created",
        "issue": {"number": CONTROL_PR, "pull_request": {"url": "PR_METADATA_ONLY"}},
        "comment": {"id": 771, "user": {"login": OWNER},
                    "body": PREFIX + json.dumps(job if job is not None else request())},
    }


def admit(e):
    return parse_owner_comment(e, actor=OWNER, triggering_actor=OWNER)


class TestOwnerCommentGateway(unittest.TestCase):
    def test_valid_owner_comment_exact_source_and_safe_metadata(self):
        got = admit(event())
        self.assertEqual(got["repo"], "vf-doc")
        self.assertEqual(got["comment_id"], "771")
        self.assertEqual(got["source_sha"], "a" * 40)
        self.assertEqual(got["tree_sha"], "b" * 40)
        self.assertEqual(got["test_id"], "git-integrity")
        self.assertNotIn("command", got)

    def test_foreign_actor_and_rerun_actor_refused(self):
        with self.assertRaisesRegex(InvalidTask, "COMMENT_OWNER_NOT_VERIFIED"):
            parse_owner_comment(event(), actor="other", triggering_actor=OWNER)
        with self.assertRaisesRegex(InvalidTask, "COMMENT_OWNER_NOT_VERIFIED"):
            parse_owner_comment(event(), actor=OWNER, triggering_actor="other")
        v = event()
        v["comment"]["user"]["login"] = "other"
        with self.assertRaisesRegex(InvalidTask, "COMMENT_OWNER_NOT_VERIFIED"):
            admit(v)

    def test_wrong_issue_not_pr_and_edit_event_refused(self):
        v = event()
        v["issue"]["number"] = CONTROL_PR + 1
        with self.assertRaisesRegex(InvalidTask, "NOT_APPROVED_CONTROL_PR"):
            admit(v)
        v = event()
        v["issue"].pop("pull_request")
        with self.assertRaisesRegex(InvalidTask, "NOT_APPROVED_CONTROL_PR"):
            admit(v)
        v = event()
        v["action"] = "edited"
        with self.assertRaisesRegex(InvalidTask, "COMMENT_EVENT_NOT_CREATED"):
            admit(v)

    def test_private_heavy_ephemeral_and_restore_refused(self):
        for field, value in (("privacy", "PRIVATE_EVIDENCE"), ("privacy", "PRIVATE_SOURCE"),
                             ("profile", "heavy"), ("allow_public_ephemeral", True),
                             ("kind", "install_restore")):
            j = request()
            j[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(InvalidTask):
                    admit(event(j))

    def test_source_repo_spoof_and_unpinned_tree_refused(self):
        for repo in ("llhzx2018/vf-adops", "attacker/vf-doc"):
            j = request()
            j["source"]["repo"] = repo
            with self.assertRaises(InvalidTask):
                admit(event(j))
        j = request()
        j["source"]["tree_sha"] = None
        with self.assertRaisesRegex(InvalidTask, "EXACT_TREE_REQUIRED"):
            admit(event(j))

    def test_shell_unknown_fields_and_unknown_test_refused(self):
        j = request()
        j["shell"] = "echo unsafe"
        with self.assertRaisesRegex(InvalidTask, "INVALID_FIELDS"):
            admit(event(j))
        j = request()
        j["test_id"] = "run-any-command"
        with self.assertRaisesRegex(InvalidTask, "PUBLIC_SAFE_ONLY"):
            admit(event(j))

    def test_invalid_json_prefix_length_and_replay_not_created_refused(self):
        v = event()
        v["comment"]["body"] = PREFIX + "not-json"
        with self.assertRaisesRegex(InvalidTask, "INVALID_REQUEST_JSON"):
            admit(v)
        v = event()
        v["comment"]["body"] = "unapproved " + v["comment"]["body"]
        with self.assertRaisesRegex(InvalidTask, "INVALID_REQUEST_BODY"):
            admit(v)
        v = event()
        v["comment"]["body"] += " " * 4000
        with self.assertRaisesRegex(InvalidTask, "INVALID_REQUEST_BODY"):
            admit(v)
        v = event()
        v["comment"]["id"] = 0
        with self.assertRaisesRegex(InvalidTask, "COMMENT_OWNER_NOT_VERIFIED"):
            admit(v)


if __name__ == "__main__":
    unittest.main()
