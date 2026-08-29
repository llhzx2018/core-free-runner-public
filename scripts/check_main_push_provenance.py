from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import quote


SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _failure(code: str, detail: str = "") -> str:
    return code if not detail else f"{code}:{detail}"


def fetch_commit_pulls(repository: str, sha: str) -> list[dict]:
    encoded_repository = quote(repository, safe="/")
    url = f"https://api.github.com/repos/{encoded_repository}/commits/{sha}/pulls"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "vf-public-runner-main-provenance-v1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("commit pulls response is not a list")
    return payload


def verify_main_push_provenance(
    repository: str,
    sha: str,
    pull_loader=fetch_commit_pulls,
) -> list[str]:
    if not repository or "/" not in repository:
        return [_failure("MAIN_PUSH_REPOSITORY_INVALID", repository)]
    if not SHA_RE.fullmatch(sha):
        return [_failure("MAIN_PUSH_SHA_INVALID", sha)]

    pulls = pull_loader(repository, sha)
    for pull in pulls:
        if not isinstance(pull, dict):
            continue
        base = pull.get("base") or {}
        if (
            pull.get("merged_at")
            and pull.get("merge_commit_sha") == sha
            and base.get("ref") == "main"
        ):
            return []

    return [_failure("MAIN_PUSH_NOT_FROM_MERGED_PR", sha)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify that a Public Runner main push SHA is the merge result of a PR targeting main."
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args(argv)

    try:
        failures = verify_main_push_provenance(args.repository, args.sha)
    except urllib.error.HTTPError as exc:
        print("MAIN_PUSH_PROVENANCE=BLOCKED_INFRA")
        print(f"BLOCK=GITHUB_HTTP_{exc.code}")
        return 78
    except Exception as exc:
        print("MAIN_PUSH_PROVENANCE=BLOCKED_INFRA")
        print(f"BLOCK=GITHUB_READ_{type(exc).__name__}")
        return 78

    if failures:
        print("MAIN_PUSH_PROVENANCE=FAIL")
        for failure in failures:
            print(f"FAIL={failure}")
        return 1

    print("MAIN_PUSH_PROVENANCE=PASS")
    print(f"REPOSITORY={args.repository}")
    print(f"SOURCE_SHA={args.sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
