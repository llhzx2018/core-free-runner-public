#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ARCHIVE_BATCH = Path("archive/workflows/2026-08")
MANIFEST_PATH = Path("archive/workflows/归档清单_V7.json")
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
ARCHIVE_SOURCES = (
    ("temporary", ARCHIVE_BATCH / "temporary", "060e65f9adec05e1fe4b3798f86f10513764c97f"),
    ("invalid-yaml", ARCHIVE_BATCH / "invalid-yaml", "060e65f9adec05e1fe4b3798f86f10513764c97f"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "core-agent", "402ff91296b11fe48626ea430bd364125750eb1a"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p02", "43d9770fe09bb0b1c02df6fc1cc9dca99786db03"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p03", "74615999a34563542f800e6810039e9e366f581c"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p04", "4f71ecb5f0bc7a81da32fd614de925cdcdb7923f"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p05", "2f6f56cd8b4631e075f10b0df3b353bc5928eb07"),
    ("historical-version", ARCHIVE_BATCH / "historical-version" / "p06", "e5a65712df80899ada28f43b668f1463d0c0320f"),
)
CATEGORIES = ("temporary", "invalid-yaml", "historical-version")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(root: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for category, source_directory, source_commit in ARCHIVE_SOURCES:
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
        "schema": "core-free-runner-workflow-archive/v7",
        "batch": "2026-08",
        "policy": "MOVE_ONLY_NO_CONTENT_CHANGE",
        "entry_count": len(entries),
        "category_counts": {
            category: sum(item["category"] == category for item in entries)
            for category in CATEGORIES
        },
        "entries": entries,
    }


def verify(root: Path) -> list[str]:
    failures: list[str] = []
    manifest_path = root / MANIFEST_PATH
    if not manifest_path.is_file():
        return ["MANIFEST_MISSING"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["MANIFEST_INVALID_JSON"]
    expected = build_manifest(root)
    if manifest != expected:
        failures.append("MANIFEST_DRIFT")
    if expected["entry_count"] != 355:
        failures.append("ENTRY_COUNT_NOT_355")
    if expected["category_counts"] != {
        "temporary": 37,
        "invalid-yaml": 2,
        "historical-version": 316,
    }:
        failures.append("CATEGORY_COUNT_MISMATCH")
    for entry in expected["entries"]:
        if (root / entry["source_path"]).exists():
            failures.append(f"SOURCE_STILL_ACTIVE:{entry['source_path']}")
    active_temp = sorted((root / ".github/workflows").glob("temp-*.yml"))
    if active_temp:
        failures.append("ACTIVE_TEMP_WORKFLOW_REMAINS")
    for name in INVALID_NAMES:
        if (root / ".github/workflows" / name).exists():
            failures.append(f"INVALID_WORKFLOW_STILL_ACTIVE:{name}")
    for name in HISTORICAL_CORE_AGENT_NAMES:
        if (root / ".github/workflows" / name).exists():
            failures.append(f"HISTORICAL_WORKFLOW_STILL_ACTIVE:{name}")
    if not (root / ".github/workflows/core-agent-current-verify.yml").is_file():
        failures.append("CURRENT_CORE_AGENT_HARNESS_MISSING")
    active_p02 = sorted((root / ".github/workflows").glob("p02*.yml"))
    if active_p02:
        failures.append("ACTIVE_P02_HISTORICAL_WORKFLOW_REMAINS")
    archived_p02 = sorted((root / ARCHIVE_BATCH / "historical-version" / "p02").glob("p02*.yml"))
    if len(archived_p02) != 83:
        failures.append("P02_ARCHIVE_COUNT_NOT_83")
    active_p03 = sorted((root / ".github/workflows").glob("p03*.yml"))
    if active_p03:
        failures.append("ACTIVE_P03_HISTORICAL_WORKFLOW_REMAINS")
    archived_p03 = sorted((root / ARCHIVE_BATCH / "historical-version" / "p03").glob("p03*.yml"))
    if len(archived_p03) != 78:
        failures.append("P03_ARCHIVE_COUNT_NOT_78")
    active_p04 = sorted((root / ".github/workflows").glob("p04*.yml"))
    if active_p04:
        failures.append("ACTIVE_P04_HISTORICAL_WORKFLOW_REMAINS")
    archived_p04 = sorted((root / ARCHIVE_BATCH / "historical-version" / "p04").glob("p04*.yml"))
    if len(archived_p04) != 67:
        failures.append("P04_ARCHIVE_COUNT_NOT_67")
    active_p05 = sorted((root / ".github/workflows").glob("p05*.yml"))
    if active_p05:
        failures.append("ACTIVE_P05_HISTORICAL_WORKFLOW_REMAINS")
    archived_p05 = sorted((root / ARCHIVE_BATCH / "historical-version" / "p05").glob("p05*.yml"))
    if len(archived_p05) != 17:
        failures.append("P05_ARCHIVE_COUNT_NOT_17")
    active_p06 = sorted((root / ".github/workflows").glob("p06*.yml"))
    if active_p06:
        failures.append("ACTIVE_P06_HISTORICAL_WORKFLOW_REMAINS")
    archived_p06 = sorted((root / ARCHIVE_BATCH / "historical-version" / "p06").glob("p06*.yml"))
    if len(archived_p06) != 62:
        failures.append("P06_ARCHIVE_COUNT_NOT_62")
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
        "schema": "core-free-runner-workflow-archive-check/v1",
        "status": "PASS" if not failures else "FAIL",
        "archived": build_manifest(root).get("entry_count"),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
