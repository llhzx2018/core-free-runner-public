#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ARCHIVE_BATCH = Path("archive/workflows/2026-08")
V10_MANIFEST_PATH = Path("archive/workflows/归档清单_V10.json")
MANIFEST_PATH = Path("archive/workflows/归档清单_V11.json")
LATE_BATCH = ARCHIVE_BATCH / "late-active-v11"
LATE_BATCH_SOURCE_COMMIT = "e90d10a76f01f6166ed49516d44a82019205fe84"
LATE_BATCH_TREE_SHA = "fc14bb126badeacedd455f974d60b29105d34883"
LATE_BATCH_ENTRY_COUNT = 86
V10_ENTRY_COUNT = 421
TOTAL_ENTRY_COUNT = V10_ENTRY_COUNT + LATE_BATCH_ENTRY_COUNT

INVALID_NAMES = {
    "p01-22121-browser-reverify.yml",
    "p01-22121-product-final-gate.yml",
}
HISTORICAL_CORE_AGENT_NAMES = {
    "core-agent-v0.4-verify.yml",
    "core-agent-v0.5-verify.yml",
    "core-agent-v0.6-write-verify.yml",
    "core-agent-v0.7-private-write-verify.yml",
    "core-agent-v0.8-p02-autonomous-engineering.yml",
    "core-agent-v0.9-portfolio.yml",
    "core-agent-v0.10-project-plan.yml",
    "core-agent-v0.11-project-run.yml",
    "core-agent-v1.0-final-gate.yml",
}
V10_ARCHIVE_SOURCES = (
    ("temporary", ARCHIVE_BATCH / "temporary", "060e65f9adec05e1fe4b3798f86f10513764c97f"),
    ("invalid-yaml", ARCHIVE_BATCH / "invalid-yaml", "060e65f9adec05e1fe4b3798f86f10513764c97f"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "core-agent", "402ff91296b11fe48626ea430bd364125750eb1a"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p02", "43d9770fe09bb0b1c02df6fc1cc9dca99786db03"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p03", "74615999a34563542f800e6810039e9e366f581c"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p04", "4f71ecb5f0bc7a81da32fd614de925cdcdb7923f"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p05", "2f6f56cd8b4631e075f10b0df3b353bc5928eb07"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p06", "e5a65712df80899ada28f43b668f1463d0c0320f"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p01", "4bf561f5d70d1194995e34ea43480c9a2ea0209c"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "s01", "3cb891c0c0d49526cbd36e85b38da3780575fdc"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "public-infrastructure", "0a109a88a46997ef91145d80a452545d78a77208"),
)
V10_CATEGORIES = ("temporary", "invalid-yaml", "historical-version")
ACTIVE_CURRENT_WORKFLOW_NAMES = {
    "core-agent-current-verify.yml",
    "gov-doc-skill-pack-publish.yml",
    "runner-selftest-current.yml",
    "runner-trigger-scope-gate.yml",
    "runner-workflow-archive-gate.yml",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_v10_manifest(root: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for category, source_directory, source_commit in V10_ARCHIVE_SOURCES:
        directory = root / source_directory
        for path in sorted(directory.glob("*.yml")):
            relative = path.relative_to(root).as_posix()
            entries.append({
                "source_path": f".github/workflows/{path.name}",
                "archive_path": relative,
                "category": category,
                "source_commit": source_commit,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            })
    return {
        "schema": "core-free-runner-workflow-archive/v10",
        "batch": "2026-08",
        "policy": "MOVE_ONLY_NO_CONTENT_CHANGE",
        "entry_count": len(entries),
        "category_counts": {
            category: sum(item["category"] == category for item in entries)
            for category in V10_CATEGORIES
        },
        "entries": entries,
    }


def _late_files(root: Path) -> list[Path]:
    return sorted((root / LATE_BATCH).glob("*.yml"))


def build_manifest(root: Path) -> dict[str, Any]:
    late_count = len(_late_files(root))
    return {
        "schema": "core-free-runner-workflow-archive/v11",
        "batch": "2026-08",
        "policy": "MOVE_ONLY_NO_CONTENT_CHANGE",
        "entry_count": V10_ENTRY_COUNT + late_count,
        "category_counts": {
            "temporary": 37,
            "invalid-yaml": 2,
            "historical-version": 382,
            "late-active": late_count,
        },
        "base_manifest": {
            "path": V10_MANIFEST_PATH.as_posix(),
            "entry_count": V10_ENTRY_COUNT,
        },
        "delta": {
            "archive_path": LATE_BATCH.as_posix(),
            "category": "late-active",
            "source_commit": LATE_BATCH_SOURCE_COMMIT,
            "git_tree_sha": LATE_BATCH_TREE_SHA,
            "entry_count": late_count,
        },
        "active_current_workflows": sorted(ACTIVE_CURRENT_WORKFLOW_NAMES),
    }


def _git_tree_sha(root: Path, relative: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"HEAD:{relative.as_posix()}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def verify(root: Path) -> list[str]:
    failures: list[str] = []

    expected_v10 = build_v10_manifest(root)
    v10_path = root / V10_MANIFEST_PATH
    if not v10_path.is_file():
        failures.append("V10_MANIFEST_MISSING")
    else:
        try:
            actual_v10 = json.loads(v10_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append("V10_MANIFEST_INVALID_JSON")
        else:
            if actual_v10 != expected_v10:
                failures.append("V10_MANIFEST_DRIFT")

    if expected_v10["entry_count"] != V10_ENTRY_COUNT:
        failures.append("V10_ENTRY_COUNT_NOT_421")
    if expected_v10["category_counts"] != {
        "temporary": 37,
        "invalid-yaml": 2,
        "historical-version": 382,
    }:
        failures.append("V10_CATEGORY_COUNT_MISMATCH")

    late_files = _late_files(root)
    if len(late_files) != LATE_BATCH_ENTRY_COUNT:
        failures.append("LATE_BATCH_COUNT_NOT_86")
    late_tree_sha = _git_tree_sha(root, LATE_BATCH)
    if late_tree_sha is not None and late_tree_sha != LATE_BATCH_TREE_SHA:
        failures.append("LATE_BATCH_TREE_DRIFT")

    manifest_path = root / MANIFEST_PATH
    if not manifest_path.is_file():
        failures.append("V11_MANIFEST_MISSING")
    else:
        try:
            actual = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append("V11_MANIFEST_INVALID_JSON")
        else:
            expected = build_manifest(root)
            if actual != expected:
                failures.append("V11_MANIFEST_DRIFT")
            if expected["entry_count"] != TOTAL_ENTRY_COUNT:
                failures.append("TOTAL_ENTRY_COUNT_NOT_507")

    for entry in expected_v10["entries"]:
        if (root / entry["source_path"]).exists():
            failures.append(f"SOURCE_STILL_ACTIVE:{entry['source_path']}")
    for path in late_files:
        source = root / ".github/workflows" / path.name
        if source.exists():
            failures.append(f"LATE_SOURCE_STILL_ACTIVE:.github/workflows/{path.name}")

    active_dir = root / ".github/workflows"
    active_temp = sorted(active_dir.glob("temp-*.yml"))
    if active_temp:
        failures.append("ACTIVE_TEMP_WORKFLOW_REMAINS")
    for name in INVALID_NAMES:
        if (active_dir / name).exists():
            failures.append(f"INVALID_WORKFLOW_STILL_ACTIVE:{name}")
    for name in HISTORICAL_CORE_AGENT_NAMES:
        if (active_dir / name).exists():
            failures.append(f"HISTORICAL_WORKFLOW_STILL_ACTIVE:{name}")
    if not (active_dir / "core-agent-current-verify.yml").is_file():
        failures.append("CURRENT_CORE_AGENT_HARNESS_MISSING")

    for prefix in ("p01", "p02", "p03", "p04", "p05", "p06", "s01"):
        if sorted(active_dir.glob(f"{prefix}*.yml")):
            failures.append(f"ACTIVE_{prefix.upper()}_HISTORICAL_WORKFLOW_REMAINS")

    old_counts = {
        "p02": 83,
        "p03": 78,
        "p04": 67,
        "p05": 17,
        "p06": 62,
        "p01": 58,
        "s01": 6,
    }
    for prefix, count in old_counts.items():
        archived = sorted((root / ARCHIVE_BATCH / "historical-version" / prefix).glob(f"{prefix}*.yml"))
        if len(archived) != count:
            failures.append(f"{prefix.upper()}_V10_ARCHIVE_COUNT_NOT_{count}")

    archived_infrastructure = sorted(
        (root / ARCHIVE_BATCH / "historical-version" / "public-infrastructure").glob("*.yml")
    )
    if len(archived_infrastructure) != 2:
        failures.append("PUBLIC_INFRASTRUCTURE_V10_ARCHIVE_COUNT_NOT_2")

    active_names = {path.name for path in active_dir.glob("*.yml")}
    if active_names != ACTIVE_CURRENT_WORKFLOW_NAMES:
        failures.append("ACTIVE_CURRENT_WORKFLOW_ALLOWLIST_DRIFT")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify the passive Public Runner workflow archive")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.write_manifest:
        payload = build_manifest(root)
        target = root / MANIFEST_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = verify(root)
    result = {
        "schema": "core-free-runner-workflow-archive-check/v2",
        "status": "PASS" if not failures else "FAIL",
        "archived": build_manifest(root).get("entry_count"),
        "v10_archived": build_v10_manifest(root).get("entry_count"),
        "late_active_archived": len(_late_files(root)),
        "late_batch_tree_sha": _git_tree_sha(root, LATE_BATCH),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
