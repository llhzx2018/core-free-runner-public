#!/usr/bin/env python3
"""Fail-closed read-only current PR/public-authority monitor for eight repos.

Emits only non-secret repo IDs, SHAs and PASS tokens. Private source is checked
out transiently by Actions and erased, never persisted in the public repo.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

OWNER = "llhzx2018"
GOV_REPO = "llhzx2018/gov-doc"
SHA = re.compile(r"^[0-9a-f]{40}$")
BRANCH = "governance/20261113-gov-doc-public-ci-bridge"


class MonitorError(RuntimeError):
    pass


@dataclass(frozen=True)
class Target:
    id: str
    repo: str
    pr: int
    profile: str
    workflow: str


TARGETS = (
    Target("P01", "llhzx2018/vf-start", 1976, "web_existing", ".github/workflows/repository-health.yml"),
    Target("P02", "llhzx2018/vf-library", 265, "web_existing", ".github/workflows/repository-health.yml"),
    Target("P04", "llhzx2018/vf-infra", 77, "web_existing", ".github/workflows/ci.yml"),
    Target("P07", "llhzx2018/vf-server-ops", 319, "cli", ".github/workflows/ci.yml"),
    Target("P08", "llhzx2018/vf-adops", 28, "web_existing", ".github/workflows/p08-isolated-first-install.yml"),
    Target("S01-C01", "llhzx2018/vf-tools-theme", 382, "wordpress_static", ".github/workflows/s01-static-modernization-contract.yml"),
    Target("S01-C02", "llhzx2018/vf-tools-ops", 434, "wordpress_static", ".github/workflows/s01-static-modernization-contract.yml"),
    Target("S01-C03", "llhzx2018/vf-tools-m3u8", 191, "wordpress_static", ".github/workflows/s01-static-modernization-contract.yml"),
)
INDEX = {t.id: t for t in TARGETS}
assert len(INDEX) == len(TARGETS) == 8


def git_refs(repo: str, refs: tuple[str, ...], token: str) -> dict:
    """Discover only preapproved PR+branch refs using existing Contents:read."""
    if not token:
        raise MonitorError("PRIVATE_READ_CAPABILITY_NOT_INJECTED")
    if repo not in {GOV_REPO, *(t.repo for t in TARGETS)}:
        raise MonitorError("UNTRUSTED_GIT_REPOSITORY")
    allowed = {"refs/heads/main"} if repo == GOV_REPO else {
        f"refs/pull/{t.pr}/head" for t in TARGETS if t.repo == repo
    } | {"refs/heads/" + BRANCH}
    if not refs or any(ref not in allowed for ref in refs):
        raise MonitorError("UNTRUSTED_GIT_REFERENCE")
    with tempfile.TemporaryDirectory(prefix="vf-askpass-") as temp:
        askpass = Path(temp) / "git-askpass"
        # Credential value is injected through the runner environment only,
        # never embedded in the script, command line, URL, logs, or artifact.
        askpass.write_text(
            '#!/bin/sh\ncase "$1" in\n'
            '*Username*) printf "%s\\n" "x-access-token";;\n'
            '*Password*) printf "%s\\n" "$VF_PRIVATE_READ_TOKEN";;\n'
            '*) exit 1;;\nesac\n', encoding="utf-8")
        askpass.chmod(0o700)
        env = os.environ.copy()
        env["VF_PRIVATE_READ_TOKEN"] = token
        env["GIT_ASKPASS"] = str(askpass)
        env["GIT_TERMINAL_PROMPT"] = "0"
        try:
            run = subprocess.run(
                ["git", "-c", "credential.helper=", "ls-remote", "--exit-code",
                 f"https://github.com/{repo}.git", *refs],
                env=env, capture_output=True, text=True, timeout=25, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise MonitorError("READ_ONLY_GIT_REF_UNAVAILABLE:" + type(exc).__name__) from None
    if run.returncode != 0:
        raise MonitorError("READ_ONLY_GIT_REF_DENIED_OR_MISSING")
    output = {}
    for line in run.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        if ref not in refs or ref in output:
            raise MonitorError("UNEXPECTED_GIT_REF_OUTPUT")
        output[ref] = valid_sha(sha, "GIT_REF")
    if set(output) != set(refs):
        raise MonitorError("GIT_REF_INCOMPLETE")
    return output


def valid_sha(value: object, where: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise MonitorError("INVALID_EXACT_SHA:" + where)
    return value


def branch_sha(repo: str, get) -> str:
    ref = "refs/heads/main"
    return valid_sha(get(repo, (ref,))[ref], repo + ":main")


def target_head(t: Target, get) -> tuple[str, str]:
    pull_ref = f"refs/pull/{t.pr}/head"
    branch_ref = "refs/heads/" + BRANCH
    refs = get(t.repo, (pull_ref, branch_ref))
    head = valid_sha(refs[pull_ref], t.id + ":PR_HEAD")
    branch = valid_sha(refs[branch_ref], t.id + ":OWNER_BRANCH")
    if head != branch:
        raise MonitorError("PR_BRANCH_SOURCE_MISMATCH:" + t.id)
    return head, "pr"


def discover(get) -> dict:
    gov_sha = branch_sha(GOV_REPO, get)
    include = []
    for target in TARGETS:
        sha, mode = target_head(target, get)
        include.append({**asdict(target), "sha": sha, "mode": mode})
    if len(include) != 8:
        raise MonitorError("TARGET_COUNT_DRIFT")
    return {"matrix": {"include": include}, "gov_sha": gov_sha, "count": str(len(include))}


def verify_current(t: Target, sha: str, gov_sha: str, mode: str, get) -> None:
    valid_sha(sha, "EXPECTED_PRODUCT")
    valid_sha(gov_sha, "EXPECTED_GOV")
    current, actual_mode = target_head(t, get)
    now_gov = branch_sha(GOV_REPO, get)
    if (current, actual_mode, now_gov) != (sha, mode, gov_sha):
        raise MonitorError("SOURCE_ADVANCED_SINCE_DISCOVERY:" + t.id)


def marker_signature(t: Target, sha: str, gov_sha: str, mode: str) -> str:
    valid_sha(sha, "MARKER_PRODUCT")
    valid_sha(gov_sha, "MARKER_GOV")
    if mode not in ("pr", "main"):
        raise MonitorError("MARKER_MODE_INVALID")
    return hashlib.sha256(f"vf-gov-ci-v1\n{t.id}\n{t.repo}\n{t.pr}\n{t.profile}\n{t.workflow}\n{mode}\n{sha}\n{gov_sha}\n".encode()).hexdigest()


def write_marker(path: Path, sig: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sig + "\n", encoding="ascii")


def verify_marker(path: Path, sig: str) -> None:
    if not path.is_file() or path.is_symlink() or path.read_text(encoding="ascii") != sig + "\n":
        raise MonitorError("EXACT_SUCCESS_CACHE_INVALID")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("discover", "recheck", "write-marker", "verify-marker"))
    ap.add_argument("--id", choices=tuple(INDEX))
    ap.add_argument("--sha")
    ap.add_argument("--gov-sha")
    ap.add_argument("--mode", choices=("pr", "main"))
    ap.add_argument("--file", type=Path, default=Path(".vf-ci-marker/pass"))
    args = ap.parse_args()
    try:
        token = os.environ.get("VF_PRIVATE_READ_TOKEN", "")
        if args.command in ("discover", "recheck") and not token:
            raise MonitorError("PRIVATE_READ_CAPABILITY_NOT_INJECTED")
        get = lambda repo, refs: git_refs(repo, refs, token)
        if args.command == "discover":
            result = discover(get)
            output = os.environ.get("GITHUB_OUTPUT")
            if not output:
                raise MonitorError("GITHUB_OUTPUT_MISSING")
            with open(output, "a", encoding="utf-8") as dest:
                dest.write("matrix=" + json.dumps(result["matrix"], separators=(",", ":")) + "\n")
                dest.write("gov_sha=" + result["gov_sha"] + "\n")
                dest.write("count=" + result["count"] + "\n")
            print("GOV_MONITOR_DISCOVERED=8")
            print("GOV_MONITOR_SOURCE_SHA=" + result["gov_sha"])
        else:
            if not args.id or not args.sha or not args.gov_sha or not args.mode:
                raise MonitorError("MONITOR_EXACT_INPUT_REQUIRED")
            t = INDEX[args.id]
            if args.command == "recheck":
                verify_current(t, args.sha, args.gov_sha, args.mode, get)
                print("GOV_MONITOR_STILL_CURRENT=YES;ID=" + t.id)
            else:
                sig = marker_signature(t, args.sha, args.gov_sha, args.mode)
                if args.command == "write-marker":
                    write_marker(args.file, sig)
                    print("GOV_MONITOR_PASS_MARKER=WRITTEN;ID=" + t.id)
                else:
                    verify_marker(args.file, sig)
                    print("GOV_MONITOR_PASS_MARKER=EXACT_MATCH;ID=" + t.id)
        return 0
    except (MonitorError, ValueError, KeyError, json.JSONDecodeError) as e:
        print("GOV_MONITOR=BLOCKED:" + str(e))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
