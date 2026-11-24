#!/usr/bin/env python3
"""Review-only Owner PR-comment intake for the existing Public Hosted test workflow.

No scheduler, credential, shell from input, persistent queue, or extra Runner.
Only the designated merged Public PR #4475 comment thread is eligible.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from shared_test_router import InvalidTask, route, validate

OWNER = "llhzx2018"
CONTROL_PR = 4475
PREFIX = "VFTEST_REQUEST_V1\n"
MAX_BODY_BYTES = 3000
TEST_IDS = {"git-integrity", "python-syntax"}
PROJECT_REPOS = {
    "P01": {"vf-startnew"},
    "P02": {"vf-doc"},
    "P07": {"vf-server-ops"},
    "P08": {"vf-adops"},
    "S01": {"vf-tools-theme", "vf-tools-ops", "vf-tools-m3u8"},
}


def parse_owner_comment(event: dict, *, actor: str, triggering_actor: str) -> dict:
    if not isinstance(event, dict) or event.get("action") != "created":
        raise InvalidTask("COMMENT_EVENT_NOT_CREATED")
    issue, comment = event.get("issue"), event.get("comment")
    if not isinstance(issue, dict) or not isinstance(comment, dict):
        raise InvalidTask("COMMENT_IDENTITY_MISSING")
    if (type(issue.get("number")) is not int or issue["number"] != CONTROL_PR
            or not isinstance(issue.get("pull_request"), dict)):
        raise InvalidTask("NOT_APPROVED_CONTROL_PR")
    if (actor != OWNER or triggering_actor != OWNER
            or not isinstance(comment.get("user"), dict)
            or comment["user"].get("login") != OWNER
            or type(comment.get("id")) is not int or comment["id"] <= 0):
        raise InvalidTask("COMMENT_OWNER_NOT_VERIFIED")
    body = comment.get("body")
    if (not isinstance(body, str) or len(body.encode("utf-8")) > MAX_BODY_BYTES
            or not body.startswith(PREFIX)):
        raise InvalidTask("INVALID_REQUEST_BODY")
    try:
        request = json.loads(body[len(PREFIX):])
    except (ValueError, UnicodeError) as exc:
        raise InvalidTask("INVALID_REQUEST_JSON") from exc
    job = validate(request)
    repo = job["source"]["repo"].split("/", 1)[-1]
    if repo not in PROJECT_REPOS[job["project"]]:
        raise InvalidTask("PROJECT_REPO_MISMATCH")
    if (job["privacy"] != "PUBLIC_SAFE" or job["profile"] != "light"
            or job["allow_public_ephemeral"] is not False
            or job["kind"] not in {"lint", "unit"}
            or job["test_id"] not in TEST_IDS or route(job) != "PUBLIC_HOSTED"):
        raise InvalidTask("PUBLIC_SAFE_ONLY")
    if job["source"]["tree_sha"] is None:
        raise InvalidTask("EXACT_TREE_REQUIRED")
    return {
        "project": job["project"], "repo": repo, "source_sha": job["source"]["sha"],
        "tree_sha": job["source"]["tree_sha"], "test_id": job["test_id"],
        "task_id": job["task_id"], "comment_id": str(comment["id"]),
    }


def main() -> int:
    try:
        if os.environ.get("GITHUB_EVENT_NAME") != "issue_comment":
            raise InvalidTask("NOT_COMMENT_EVENT")
        event_file = Path(os.environ["GITHUB_EVENT_PATH"])
        if event_file.is_symlink() or not event_file.is_file() or event_file.stat().st_size > 100_000:
            raise InvalidTask("UNTRUSTED_EVENT_FILE")
        values = parse_owner_comment(
            json.loads(event_file.read_text(encoding="utf-8")),
            actor=os.environ.get("GITHUB_ACTOR", ""),
            triggering_actor=os.environ.get("GITHUB_TRIGGERING_ACTOR", ""),
        )
        output_file = Path(os.environ["GITHUB_OUTPUT"])
        with output_file.open("a", encoding="utf-8") as f:
            for key, value in values.items():
                f.write(key + "=" + value + "\n")
        print("VFTEST_OWNER_COMMENT_ADMISSION=PASS")
        print("VFTEST_COMMENT_ID=" + values["comment_id"])
        return 0
    except (InvalidTask, KeyError, TypeError, ValueError, OSError):
        # Never expose the raw public comment body, a URL, or any secret.
        print("VFTEST_OWNER_COMMENT_ADMISSION=BLOCKED")
        return 2


if __name__ == "__main__":
    sys.exit(main())
