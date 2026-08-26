#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path, PurePosixPath


ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
SHA_RE = re.compile(r"^[a-fA-F0-9]{40}$")


def fail(message: str) -> None:
    print(f"JOB_VALIDATION_FAIL: {message}", file=sys.stderr)
    raise SystemExit(2)


def safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or len(value) > 240 or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def validate(data: object) -> None:
    if not isinstance(data, dict):
        fail("manifest must be an object")
    required = {"schema_version", "project_id", "component_id", "run_id", "phase", "source", "environment", "tests"}
    if set(data) != required:
        fail(f"top-level keys must equal {sorted(required)}")
    if data["schema_version"] != "2.0" or data["phase"] != "PHASE3":
        fail("schema_version/phase mismatch")
    for key in ("project_id", "run_id"):
        value = data[key]
        if not isinstance(value, str) or not value or len(value) > 120 or not ID_RE.fullmatch(value):
            fail(f"invalid {key}")
    component = data["component_id"]
    if not isinstance(component, str) or len(component) > 80 or (component and not ID_RE.fullmatch(component)):
        fail("invalid component_id")

    source = data["source"]
    if not isinstance(source, dict) or source.get("mode") not in {"none", "local_directory"}:
        fail("source.mode invalid")
    if source["mode"] == "none" and set(source) != {"mode"}:
        fail("none source accepts only mode")
    if source["mode"] == "local_directory":
        if set(source) != {"mode", "path", "exact_sha"}:
            fail("local_directory source keys invalid")
        if not safe_relative_path(source.get("path")):
            fail("source.path must be a safe relative path")
        if not SHA_RE.fullmatch(str(source.get("exact_sha", ""))):
            fail("source.exact_sha invalid")

    expected_environment = {"wordpress": "7.0.2", "php": "8.4", "mariadb": "11.8.8"}
    if data["environment"] != expected_environment:
        fail("environment must match the pinned V2 baseline")
    if data["tests"] != ["environment"]:
        fail("V2 generic harness only proves the environment baseline")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: validate_job.py <manifest.json>")
    validate(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    print("JOB_VALIDATION_PASS")


if __name__ == "__main__":
    main()

