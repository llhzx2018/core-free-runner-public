#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


QUARANTINED_WORKFLOWS = (
    ".github/workflows/p01-pr-probe.yml",
    ".github/workflows/p01-22121-browser-gate.yml",
    ".github/workflows/p01-22121-final-source-gate.yml",
    ".github/workflows/p02-v2516-final-candidate-verify.yml",
    ".github/workflows/p02-v2517-production-readiness.yml",
    ".github/workflows/p02-v2516-production-readiness.yml",
    ".github/workflows/p02-v2516-manifest-reseal.yml",
    ".github/workflows/p02-v2517-source-manifest-reseal.yml",
)


def event_block(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == "on:" and not line.startswith((" ", "\t")))
    except StopIteration as exc:
        raise ValueError(f"top-level on block missing: {path}") from exc

    selected = [lines[start]]
    for line in lines[start + 1 :]:
        if line and not line.startswith((" ", "\t")):
            break
        selected.append(line)
    return "\n".join(selected)


def classify(path: Path) -> dict[str, bool]:
    block = event_block(path)
    return {
        "pull_request": "pull_request:" in block,
        "workflow_dispatch": "workflow_dispatch:" in block,
        "paths": "paths:" in block,
        "branches": "branches:" in block,
    }


def verify_quarantine(root: Path) -> list[str]:
    failures: list[str] = []
    for relative in QUARANTINED_WORKFLOWS:
        path = root / relative
        if not path.is_file():
            failures.append(f"MISSING:{relative}")
            continue
        state = classify(path)
        if state["pull_request"]:
            failures.append(f"PR_TRIGGER_STILL_ACTIVE:{relative}")
        if not state["workflow_dispatch"]:
            failures.append(f"MANUAL_RECOVERY_MISSING:{relative}")
    return failures


def inventory(root: Path) -> dict[str, object]:
    workflow_root = root / ".github" / "workflows"
    paths = sorted((*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")))
    pull_request_count = 0
    unscoped_pull_request_count = 0
    manual_count = 0
    unscoped_pull_request_paths: list[str] = []
    identities: list[str] = []
    for path in paths:
        state = classify(path)
        if state["pull_request"]:
            pull_request_count += 1
            if not state["paths"]:
                unscoped_pull_request_count += 1
                unscoped_pull_request_paths.append(path.name)
        if state["workflow_dispatch"]:
            manual_count += 1
        identities.append(f"{path.name}:{hashlib.sha256(path.read_bytes()).hexdigest()}")
    return {
        "schema": "core-free-runner-trigger-inventory/v1",
        "workflow_count": len(paths),
        "pull_request_workflow_count": pull_request_count,
        "unscoped_pull_request_workflow_count": unscoped_pull_request_count,
        "unscoped_pull_request_workflows": unscoped_pull_request_paths,
        "workflow_dispatch_count": manual_count,
        "inventory_sha256": hashlib.sha256("\n".join(identities).encode("utf-8")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Public Runner PR trigger containment")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    failures = verify_quarantine(root)
    payload = inventory(root) if args.inventory else {}
    payload.update({
        "quarantined_workflow_count": len(QUARANTINED_WORKFLOWS),
        "quarantine_status": "PASS" if not failures else "FAIL",
        "failures": failures,
    })
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
