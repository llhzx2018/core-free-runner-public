#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
TEST_COUNT_RE = re.compile(r"Ran\s+(\d+)\s+tests?", re.IGNORECASE)
PUBLIC_SCHEMA = "core-agent-runtime-ab-public-evidence/v1"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_version(source: Path) -> str:
    version_file = source / "VERSION"
    if not version_file.is_file():
        raise RuntimeError("VERSION_MISSING")
    return version_file.read_text(encoding="utf-8").strip()


def _test_count(evidence: dict[str, Any]) -> int | None:
    counts: list[int] = []
    for check in evidence.get("checks") or ():
        if not isinstance(check, dict):
            continue
        text = f"{check.get('stdout') or ''}\n{check.get('stderr') or ''}"
        counts.extend(int(item) for item in TEST_COUNT_RE.findall(text))
    return max(counts) if counts else None


def run_verification(source: Path, source_sha: str, *, timeout: int = 300) -> dict[str, Any]:
    verify = source / "scripts" / "verify.py"
    if not verify.is_file():
        return {"status": "HARNESS_BLOCK", "reason": "VERIFY_SCRIPT_MISSING"}

    env = os.environ.copy()
    env["VF_SOURCE_SHA"] = source_sha
    try:
        completed = subprocess.run(
            [sys.executable, str(verify)],
            cwd=source,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "HARNESS_BLOCK", "reason": "VERIFY_TIMEOUT"}

    evidence_path = source / ".evidence" / "verification.json"
    if not evidence_path.is_file():
        return {
            "status": "PRODUCT_FAIL" if completed.returncode else "HARNESS_BLOCK",
            "reason": "VERIFICATION_EVIDENCE_MISSING",
            "exit_code": completed.returncode,
        }

    raw = evidence_path.read_bytes()
    try:
        private_evidence = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "HARNESS_BLOCK", "reason": "VERIFICATION_EVIDENCE_INVALID"}

    machine_status = str(private_evidence.get("status") or "UNKNOWN")
    return {
        "status": "PASS" if completed.returncode == 0 and machine_status == "PASS" else "PRODUCT_FAIL",
        "reason": None if completed.returncode == 0 and machine_status == "PASS" else "MACHINE_VERIFICATION_FAILED",
        "exit_code": completed.returncode,
        "machine_status": machine_status,
        "test_count": _test_count(private_evidence),
        "private_evidence_sha256": _sha256(raw),
    }


def probe_candidate(source: Path, *, timeout: int = 60) -> dict[str, Any]:
    code = r'''
import json
from core_agent.budget import BudgetState, RuntimeBudgetExceeded, RuntimeBudgetTracker, RuntimeStopRule
from core_agent.context_snapshot import ProjectContextSnapshot
from core_agent.profiles.vf.runtime_policy import detect_runtime_level, minimal_skill_routes, runtime_profile

profiles = {}
for name in ("L0", "L1", "L2", "L3"):
    profile = runtime_profile(name)
    profiles[name] = {
        "max_files_read": profile.budget.max_files_read,
        "max_steps": profile.budget.max_steps,
        "max_text_bytes": profile.budget.max_text_bytes,
        "max_references": profile.budget.max_references,
        "max_repositories": profile.budget.max_repositories,
        "max_skills": profile.max_skills,
    }

l1 = runtime_profile("L1")
checkpoint = RuntimeBudgetTracker(l1.budget)
checkpoint.consume_step(12)
checkpoint_required = checkpoint.state() is BudgetState.CHECKPOINT_REQUIRED

limit = RuntimeBudgetTracker(l1.budget)
for index in range(20):
    limit.consume_file(f"file-{index}.txt")
try:
    limit.consume_file("file-20.txt")
    upgrade_dimension = None
except RuntimeBudgetExceeded as exc:
    upgrade_dimension = exc.dimension

stop = RuntimeStopRule()
stop.observe({"_runtime_progress": {"problem_located": True, "modification_complete": True}})
stop_before_tests = stop.satisfied
stop.observe({"_runtime_progress": {"tests_passed": True}})

snapshot = ProjectContextSnapshot(
    project_id="P04",
    repo="owner/repository",
    observed_commit="a" * 40,
    observed_at="2026-08-26T00:00:00Z",
    authority_pointers=("docs/authority/CURRENT.md",),
    hot_files=("src/example.py",),
    test_commands=("python -m unittest",),
    runtime_level="L1",
    scope="修复余额显示 BUG",
)
snapshot_bytes = len(snapshot.serialize().encode("utf-8"))

bug_scope = "修复 P04 域名余额显示 BUG"
analysis_scope = "只读定位这个问题并分析方案"
release_scope = "VF L3：正式发布"
payload = {
    "profiles": profiles,
    "routes": {
        "bugfix": [detect_runtime_level(bug_scope).value, list(minimal_skill_routes(detect_runtime_level(bug_scope), bug_scope))],
        "analysis": [detect_runtime_level(analysis_scope).value, list(minimal_skill_routes(detect_runtime_level(analysis_scope), analysis_scope))],
        "release": [detect_runtime_level(release_scope).value, list(minimal_skill_routes(detect_runtime_level(release_scope), release_scope))],
    },
    "checkpoint_required_at_80_percent": checkpoint_required,
    "upgrade_dimension": upgrade_dimension,
    "stop_before_tests": stop_before_tests,
    "stop_after_tests": stop.satisfied,
    "snapshot_bytes": snapshot_bytes,
    "snapshot_within_4k": snapshot_bytes <= ProjectContextSnapshot.MAX_BYTES,
}
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
'''
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source / "src")
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=source,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "HARNESS_BLOCK", "reason": "RUNTIME_PROBE_TIMEOUT"}
    if completed.returncode != 0:
        return {"status": "PRODUCT_FAIL", "reason": "RUNTIME_PROBE_FAILED"}
    try:
        data = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        return {"status": "HARNESS_BLOCK", "reason": "RUNTIME_PROBE_OUTPUT_INVALID"}

    expected_profiles = {
        "L0": {"max_files_read": 8, "max_steps": 8, "max_text_bytes": 40 * 1024, "max_references": 1, "max_repositories": 1, "max_skills": 0},
        "L1": {"max_files_read": 20, "max_steps": 15, "max_text_bytes": 120 * 1024, "max_references": 1, "max_repositories": 1, "max_skills": 1},
        "L2": {"max_files_read": 100, "max_steps": 50, "max_text_bytes": 400 * 1024, "max_references": 4, "max_repositories": 1, "max_skills": 2},
        "L3": {"max_files_read": 200, "max_steps": 100, "max_text_bytes": 600 * 1024, "max_references": 8, "max_repositories": 2, "max_skills": 5},
    }
    checks = {
        "profiles_exact": data.get("profiles") == expected_profiles,
        "bugfix_lazy_load": data.get("routes", {}).get("bugfix") == ["L1", ["skill-dev"]],
        "analysis_zero_skill": data.get("routes", {}).get("analysis") == ["L0", []],
        "release_isolated_l3": data.get("routes", {}).get("release") == ["L3", ["skill-release"]],
        "checkpoint_80_percent": data.get("checkpoint_required_at_80_percent") is True,
        "upgrade_stop": data.get("upgrade_dimension") == "files_read",
        "stop_rule_waits_for_tests": data.get("stop_before_tests") is False and data.get("stop_after_tests") is True,
        "snapshot_within_4k": data.get("snapshot_within_4k") is True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "PRODUCT_FAIL",
        "reason": None if all(checks.values()) else "RUNTIME_CONTRACT_MISMATCH",
        "checks": checks,
        "profiles": data.get("profiles"),
        "routes": data.get("routes"),
        "snapshot_bytes": data.get("snapshot_bytes"),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    baseline = args.baseline.resolve()
    candidate = args.candidate.resolve()
    for value in (args.baseline_sha, args.candidate_sha):
        if not SHA_RE.fullmatch(value):
            raise RuntimeError("INVALID_SOURCE_SHA")

    baseline_result = run_verification(baseline, args.baseline_sha, timeout=args.timeout)
    candidate_result = run_verification(candidate, args.candidate_sha, timeout=args.timeout)
    runtime_probe = probe_candidate(candidate, timeout=min(args.timeout, 60))
    baseline_version = _read_version(baseline)
    candidate_version = _read_version(candidate)
    versions_match = baseline_version == args.expect_baseline_version and candidate_version == args.expect_candidate_version
    tests_non_decreasing = (
        isinstance(baseline_result.get("test_count"), int)
        and isinstance(candidate_result.get("test_count"), int)
        and candidate_result["test_count"] >= baseline_result["test_count"]
    )

    status = "PASS" if (
        baseline_result.get("status") == "PASS"
        and candidate_result.get("status") == "PASS"
        and runtime_probe.get("status") == "PASS"
        and versions_match
        and tests_non_decreasing
    ) else "FAIL"
    payload: dict[str, Any] = {
        "schema": PUBLIC_SCHEMA,
        "status": status,
        "baseline": {"source_sha": args.baseline_sha, "version": baseline_version, **baseline_result},
        "candidate": {"source_sha": args.candidate_sha, "version": candidate_version, **candidate_result},
        "runtime_probe": runtime_probe,
        "comparison": {
            "versions_match_expected": versions_match,
            "tests_non_decreasing": tests_non_decreasing,
            "l1_step_cap_reduction_vs_legacy_default": "25%",
            "model_tokens_measured": False,
            "token_result": "NOT_MEASURED_DETERMINISTIC_CONTROL_PLANE_ONLY",
        },
        "privacy": {
            "private_source_persisted": False,
            "private_source_uploaded": False,
            "secret_value_persisted": False,
            "raw_test_output_persisted": False,
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["sha256"] = _sha256(canonical)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build public-safe core-agent Runtime V1.1 A/B evidence")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--expect-baseline-version", default="1.0.0")
    parser.add_argument("--expect-candidate-version", default="1.1.0rc1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = build_report(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"RUNNER_HARNESS_BLOCK={type(exc).__name__}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"CORE_AGENT_RUNTIME_AB={payload['status']}")
    print(f"PUBLIC_EVIDENCE_SHA256={payload['sha256']}")
    print(f"MODEL_TOKENS_MEASURED={payload['comparison']['model_tokens_measured']}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
