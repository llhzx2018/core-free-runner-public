#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import ephemeral_lane_spec


class WorktreeError(RuntimeError):
    pass


def _run(args: list[str], *, cwd: Path | None = None, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=capture,
        check=False,
    )


def _git(repo: Path, *args: str) -> str:
    result = _run(["git", "-C", str(repo), *args])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise WorktreeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _read_version(repo: Path, rel: str) -> str:
    path = repo / rel
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise WorktreeError(f"version file {rel}: {exc}") from exc


def verify_worktree(
    repo: Path,
    spec: dict,
    *,
    version_files: list[str],
    allow_dirty: bool,
) -> dict:
    repo = repo.resolve()
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        raise WorktreeError(f"repo is not a git worktree: {repo}")

    actual_sha = _git(repo, "rev-parse", "HEAD")
    actual_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    status = _git(repo, "status", "--porcelain")

    failures: list[str] = []
    if actual_sha != spec["target_sha"]:
        failures.append(f"HEAD_MISMATCH expected={spec['target_sha']} actual={actual_sha}")
    if spec["target_tree"] and actual_tree != spec["target_tree"]:
        failures.append(f"TREE_MISMATCH expected={spec['target_tree']} actual={actual_tree}")
    if status and not allow_dirty:
        failures.append("WORKTREE_DIRTY")

    versions: dict[str, str] = {}
    for rel in version_files:
        value = _read_version(repo, rel)
        versions[rel] = value
        if value != spec["target_version"]:
            failures.append(
                f"VERSION_MISMATCH file={rel} expected={spec['target_version']} actual={value}"
            )

    payload = {
        "schema": "vf-ephemeral-lane-worktree-check/v1",
        "status": "PASS" if not failures else "FAIL",
        "failure_class": None if not failures else "HARNESS_IDENTITY_OR_BINDING",
        "repository": spec["repository"],
        "target_version": spec["target_version"],
        "expected_sha": spec["target_sha"],
        "actual_sha": actual_sha,
        "expected_tree": spec["target_tree"],
        "actual_tree": actual_tree,
        "clean": not bool(status),
        "version_files": versions,
        "failures": failures,
    }
    if failures:
        raise WorktreeError(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


def run_isolated(
    repo: Path,
    spec: dict,
    *,
    command: list[str],
    label: str,
) -> int:
    repo = repo.resolve()
    if not command:
        raise WorktreeError("run-isolated: command is required after --")

    # Fail closed before creating a second worktree: the source binding itself
    # must already be exact. Dirty state is allowed here because the isolated
    # worktree is specifically intended to protect the source checkout from
    # mutating tests.
    verify_worktree(repo, spec, version_files=[], allow_dirty=True)

    original_status = _git(repo, "status", "--porcelain")
    temp_root = Path(tempfile.mkdtemp(prefix="vf-isolated-worktree-"))
    isolated = temp_root / "worktree"
    added = False
    command_rc: int | None = None
    isolated_status = ""
    cleanup_error = ""

    try:
        add = _run(
            ["git", "-C", str(repo), "worktree", "add", "--detach", str(isolated), spec["target_sha"]]
        )
        if add.returncode != 0:
            detail = (add.stderr or add.stdout).strip()
            raise WorktreeError(f"worktree add failed: {detail}")
        added = True

        env = os.environ.copy()
        env["VF_ISOLATED_WORKTREE"] = "1"
        env["VF_ISOLATED_WORKTREE_PATH"] = str(isolated)
        result = subprocess.run(command, cwd=isolated, env=env, check=False)
        command_rc = result.returncode
        isolated_status = _git(isolated, "status", "--porcelain")
    finally:
        if added:
            remove = _run(["git", "-C", str(repo), "worktree", "remove", "--force", str(isolated)])
            if remove.returncode != 0:
                cleanup_error = (remove.stderr or remove.stdout).strip()
            _run(["git", "-C", str(repo), "worktree", "prune"])
        try:
            temp_root.rmdir()
        except OSError:
            pass

    current_status = _git(repo, "status", "--porcelain")
    source_unchanged = current_status == original_status

    if cleanup_error or not source_unchanged:
        payload = {
            "schema": "vf-isolated-worktree-run/v1",
            "status": "FAIL",
            "failure_class": "HARNESS_ISOLATION_FAILURE",
            "label": label,
            "command_exit_code": command_rc,
            "isolated_dirty": bool(isolated_status),
            "source_unchanged": source_unchanged,
            "cleanup_error": cleanup_error,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    if command_rc != 0:
        payload = {
            "schema": "vf-isolated-worktree-run/v1",
            "status": "FAIL",
            "failure_class": "UNRESOLVED_TEST_FAILURE",
            "label": label,
            "command_exit_code": command_rc,
            "isolated_dirty": bool(isolated_status),
            "source_unchanged": True,
            "next_classification": ["PRODUCT", "CONTRACT", "HARNESS", "ENVIRONMENT"],
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return int(command_rc or 1)

    payload = {
        "schema": "vf-isolated-worktree-run/v1",
        "status": "PASS",
        "failure_class": None,
        "label": label,
        "command_exit_code": 0,
        "isolated_dirty": bool(isolated_status),
        "source_unchanged": True,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exact-source and isolated-worktree helper for VF ephemeral Runner lanes"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--spec", type=Path, required=True)
    verify.add_argument("--repo", type=Path, required=True)
    verify.add_argument("--version-file", action="append", default=[])
    verify.add_argument("--allow-dirty", action="store_true")

    isolated = sub.add_parser("run-isolated")
    isolated.add_argument("--spec", type=Path, required=True)
    isolated.add_argument("--repo", type=Path, required=True)
    isolated.add_argument("--label", default="isolated-test")
    isolated.add_argument("command_args", nargs=argparse.REMAINDER)

    args = parser.parse_args()
    try:
        spec = ephemeral_lane_spec.load_spec(args.spec)
        if args.command == "verify":
            result = verify_worktree(
                args.repo,
                spec,
                version_files=args.version_file,
                allow_dirty=args.allow_dirty,
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0

        command = list(args.command_args)
        if command and command[0] == "--":
            command = command[1:]
        return run_isolated(args.repo, spec, command=command, label=args.label)
    except (OSError, WorktreeError, ephemeral_lane_spec.ContractError) as exc:
        detail = str(exc)
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                print(json.dumps(parsed, ensure_ascii=False, sort_keys=True))
                return 2
        except json.JSONDecodeError:
            pass
        print(json.dumps({
            "schema": "vf-ephemeral-lane-worktree-check/v1",
            "status": "FAIL",
            "failure_class": "HARNESS_IDENTITY_OR_BINDING",
            "error": detail,
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
