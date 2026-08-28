from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote


GOVERNANCE_REPOSITORY = "llhzx2018/gov-doc"
REGISTRY_PATH = "governance/authority/VF_GIT_REPOSITORY_REGISTRY_V1.0.json"
INFRA_AUTHORITY_PATH = "governance/agent/VF_AGENT_INFRA_AUTHORITY.json"

DYNAMIC_REPOSITORY_KEYS = {
    "main_sha",
    "head_sha",
    "open_pr_count",
    "branch_count",
    "latest_workflow",
    "latest_workflow_run",
    "release_version",
    "production_version",
    "production_installed",
}

REQUIRED_CURRENT_INFRASTRUCTURE = {
    "llhzx2018/core-agent",
    "llhzx2018/core-updates",
    "llhzx2018/core-free-runner-public",
    "llhzx2018/core-free-runner-private",
    "llhzx2018/gov-doc",
}


def _failure(code: str, detail: str = "") -> str:
    return code if not detail else f"{code}:{detail}"


def verify_registry(registry: dict) -> list[str]:
    failures: list[str] = []
    if registry.get("schema") != "vf.git-repository-registry.v1":
        failures.append(_failure("REGISTRY_SCHEMA", str(registry.get("schema"))))

    repositories = registry.get("repositories")
    if not isinstance(repositories, list):
        return failures + ["REGISTRY_REPOSITORIES_NOT_LIST"]

    by_repo: dict[str, dict] = {}
    for index, item in enumerate(repositories):
        if not isinstance(item, dict):
            failures.append(_failure("REGISTRY_ENTRY_NOT_OBJECT", str(index)))
            continue
        repository = item.get("repository")
        if not isinstance(repository, str) or not repository:
            failures.append(_failure("REGISTRY_REPOSITORY_MISSING", str(index)))
            continue
        if repository in by_repo:
            failures.append(_failure("REGISTRY_DUPLICATE_REPOSITORY", repository))
            continue
        by_repo[repository] = item

        dynamic = sorted(DYNAMIC_REPOSITORY_KEYS.intersection(item))
        if dynamic:
            failures.append(_failure("REGISTRY_DYNAMIC_FIELD", f"{repository}:{','.join(dynamic)}"))

        lifecycle = item.get("lifecycle")
        route_status = item.get("route_status")
        source_class = item.get("source_class")

        if lifecycle == "DELETED" and route_status != "TOMBSTONE":
            failures.append(_failure("DELETED_NOT_TOMBSTONE", repository))
        if route_status == "TOMBSTONE" and lifecycle != "DELETED":
            failures.append(_failure("TOMBSTONE_NOT_DELETED", repository))
        if source_class == "VF_OWNED" and lifecycle == "ACTIVE" and route_status != "CURRENT_ROUTE":
            failures.append(_failure("ACTIVE_VF_NOT_CURRENT_ROUTE", repository))
        if source_class == "EXTERNAL_FORK":
            if lifecycle != "REFERENCE" or route_status != "NON_AUTHORITY":
                failures.append(_failure("EXTERNAL_FORK_ROUTE", repository))
            if not item.get("upstream"):
                failures.append(_failure("EXTERNAL_FORK_UPSTREAM_MISSING", repository))

    for repository in sorted(REQUIRED_CURRENT_INFRASTRUCTURE):
        item = by_repo.get(repository)
        if item is None:
            failures.append(_failure("REQUIRED_INFRA_MISSING", repository))
            continue
        if item.get("lifecycle") != "ACTIVE" or item.get("route_status") != "CURRENT_ROUTE":
            failures.append(_failure("REQUIRED_INFRA_NOT_CURRENT", repository))

    p03 = by_repo.get("llhzx2018/vf-forge")
    if p03 is None:
        failures.append("P03_RECORD_MISSING")
    elif p03.get("lifecycle") != "HISTORICAL" or p03.get("route_status") != "NON_AUTHORITY":
        failures.append("P03_ROUTE_NOT_RETIRED")

    legacy = by_repo.get("llhzx2018/core-test-runner")
    if legacy is None:
        failures.append("LEGACY_RUNNER_TOMBSTONE_MISSING")
    elif legacy.get("lifecycle") != "DELETED" or legacy.get("route_status") != "TOMBSTONE":
        failures.append("LEGACY_RUNNER_REACTIVATED")

    return failures


def verify_infra_authority(authority: dict) -> list[str]:
    failures: list[str] = []
    if authority.get("schema") != "vf-agent-infra-authority/2":
        failures.append(_failure("INFRA_AUTHORITY_SCHEMA", str(authority.get("schema"))))
    if authority.get("status") != "CURRENT":
        failures.append(_failure("INFRA_AUTHORITY_STATUS", str(authority.get("status"))))
    if authority.get("public_runner") != "llhzx2018/core-free-runner-public":
        failures.append("PUBLIC_RUNNER_ROUTE_DRIFT")
    if authority.get("private_runner") != "llhzx2018/core-free-runner-private":
        failures.append("PRIVATE_RUNNER_ROUTE_DRIFT")
    if "legacy_runner" in authority:
        failures.append("LEGACY_RUNNER_ACTIVE_KEY_PRESENT")

    hard_rules = authority.get("hard_rules") or {}
    if hard_rules.get("allow_third_runner") is not False:
        failures.append("THIRD_RUNNER_RULE_NOT_FALSE")
    if hard_rules.get("allow_third_credential") is not False:
        failures.append("THIRD_CREDENTIAL_RULE_NOT_FALSE")

    tombstone = authority.get("legacy_runner_tombstone")
    if not isinstance(tombstone, dict):
        failures.append("LEGACY_RUNNER_TOMBSTONE_AUTHORITY_MISSING")
    else:
        if tombstone.get("canonical_id") != "llhzx2018/core-test-runner":
            failures.append("LEGACY_RUNNER_TOMBSTONE_ID_DRIFT")
        if tombstone.get("state") != "DELETED":
            failures.append("LEGACY_RUNNER_TOMBSTONE_STATE_DRIFT")
        if tombstone.get("current_route") is not False:
            failures.append("LEGACY_RUNNER_TOMBSTONE_ROUTE_DRIFT")
        if tombstone.get("compatibility_policy") != "TOMBSTONE_AND_MIGRATION_EVIDENCE_ONLY":
            failures.append("LEGACY_RUNNER_TOMBSTONE_POLICY_DRIFT")

    return failures


def verify_local_workflows(root: Path) -> list[str]:
    failures: list[str] = []
    workflow_root = root / ".github" / "workflows"
    workflows = sorted(workflow_root.glob("*.yml"))
    if not workflows:
        return ["CURRENT_WORKFLOWS_MISSING"]

    for path in workflows:
        text = path.read_text(encoding="utf-8")
        if re.search(r"(?mi)^\s*contents:\s*write\s*$", text):
            failures.append(_failure("CURRENT_WORKFLOW_CONTENTS_WRITE", path.name))
        if re.search(r"(?mi)\bgit\s+push\b", text):
            failures.append(_failure("CURRENT_WORKFLOW_DIRECT_GIT_PUSH", path.name))

    core_agent = workflow_root / "core-agent-current-verify.yml"
    if not core_agent.is_file():
        failures.append("CORE_AGENT_CURRENT_WORKFLOW_MISSING")
    else:
        text = core_agent.read_text(encoding="utf-8")
        if re.search(r"CORE_AGENT_SOURCE_SHA:\s*[0-9a-f]{40}\b", text):
            failures.append("CORE_AGENT_CURRENT_HARDCODED_SHA")
        if "ref: main" not in text:
            failures.append("CORE_AGENT_CURRENT_NOT_TRACKING_MAIN")
        if "git -C source rev-parse HEAD" not in text:
            failures.append("CORE_AGENT_CURRENT_IDENTITY_READBACK_MISSING")

    return failures


def _fetch_private_json(repository: str, path: str, token: str, ref: str = "main") -> dict:
    encoded_path = quote(path, safe="/")
    url = f"https://api.github.com/repos/{repository}/contents/{encoded_path}?ref={quote(ref, safe='')}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "vf-estate-anti-drift-v1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raw = base64.b64decode(payload["content"])
    return json.loads(raw.decode("utf-8"))


def verify_live(token: str) -> list[str]:
    try:
        registry = _fetch_private_json(GOVERNANCE_REPOSITORY, REGISTRY_PATH, token)
        authority = _fetch_private_json(GOVERNANCE_REPOSITORY, INFRA_AUTHORITY_PATH, token)
    except urllib.error.HTTPError as exc:
        return [_failure("LIVE_AUTHORITY_HTTP", str(exc.code))]
    except Exception as exc:  # public-safe class only; never print token or source bodies
        return [_failure("LIVE_AUTHORITY_READ", type(exc).__name__)]
    return verify_registry(registry) + verify_infra_authority(authority)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify current VF Git Estate governance invariants.")
    parser.add_argument("--live", action="store_true", help="Read CURRENT gov-doc authority through registered private-read capability.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)

    failures = verify_local_workflows(Path(args.root))
    if args.live:
        token = os.environ.get("VF_PRIVATE_READ_TOKEN", "")
        if not token:
            print("ESTATE_ANTI_DRIFT=BLOCKED_INFRA")
            print("BLOCK=VF_PRIVATE_READ_TOKEN_MISSING")
            return 78
        failures.extend(verify_live(token))

    if failures:
        print("ESTATE_ANTI_DRIFT=FAIL")
        for failure in failures:
            print(f"FAIL={failure}")
        return 1

    print("ESTATE_ANTI_DRIFT=PASS")
    print(f"LIVE_AUTHORITY={'YES' if args.live else 'NO'}")
    print("PRIVATE_SOURCE_PERSISTED=NO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
