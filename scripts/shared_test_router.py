#!/usr/bin/env python3
"""V1 public-safe admission policy. No GitHub dispatch or shell execution."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SCHEMA = "vf-shared-test-job/v1"
PROJECTS = {"P01", "P02", "P07", "P08", "S01"}
KINDS = {"lint", "unit", "build", "integration", "install_restore"}
PRIVACY = {"PUBLIC_SAFE", "PRIVATE_SOURCE", "PRIVATE_EVIDENCE"}
PROFILES = {"light", "normal", "heavy"}
FIELDS = {"schema", "task_id", "project", "source", "test_id", "kind", "privacy", "profile", "timeout_seconds", "submitted_at", "allow_public_ephemeral"}
SOURCE_FIELDS = {"repo", "sha", "tree_sha"}
REPO = re.compile(r"llhzx2018/[a-z0-9][a-z0-9._-]{1,70}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
TASK = re.compile(r"[a-z0-9][a-z0-9_-]{7,63}\Z")
TEST = re.compile(r"[a-z][a-z0-9_-]{1,40}\Z")


class InvalidTask(ValueError):
    pass


def validate(job: object) -> dict:
    if not isinstance(job, dict) or set(job) != FIELDS:
        raise InvalidTask("INVALID_FIELDS")
    if job["schema"] != SCHEMA or job["project"] not in PROJECTS:
        raise InvalidTask("INVALID_IDENTITY")
    if not isinstance(job["source"], dict) or set(job["source"]) != SOURCE_FIELDS:
        raise InvalidTask("INVALID_SOURCE_FIELDS")
    source = job["source"]
    if not isinstance(source["repo"], str) or not REPO.fullmatch(source["repo"]):
        raise InvalidTask("INVALID_REPOSITORY")
    if not isinstance(source["sha"], str) or not SHA.fullmatch(source["sha"]):
        raise InvalidTask("INVALID_SHA")
    if source["tree_sha"] is not None and (not isinstance(source["tree_sha"], str) or not SHA.fullmatch(source["tree_sha"])):
        raise InvalidTask("INVALID_TREE")
    if not isinstance(job["task_id"], str) or not TASK.fullmatch(job["task_id"]):
        raise InvalidTask("INVALID_TASK_ID")
    if not isinstance(job["test_id"], str) or not TEST.fullmatch(job["test_id"]):
        raise InvalidTask("INVALID_TEST_ID")
    if job["kind"] not in KINDS or job["privacy"] not in PRIVACY or job["profile"] not in PROFILES:
        raise InvalidTask("INVALID_CLASSIFICATION")
    if type(job["timeout_seconds"]) is not int or not 10 <= job["timeout_seconds"] <= 7200:
        raise InvalidTask("INVALID_TIMEOUT")
    if type(job["submitted_at"]) is not int or job["submitted_at"] < 0:
        raise InvalidTask("INVALID_SUBMISSION")
    if type(job["allow_public_ephemeral"]) is not bool:
        raise InvalidTask("INVALID_EPHEMERAL_FLAG")
    if job["privacy"] != "PRIVATE_SOURCE" and job["allow_public_ephemeral"]:
        raise InvalidTask("EPHEMERAL_PRIVACY_MISMATCH")
    if job["kind"] == "install_restore" and job["profile"] != "heavy":
        raise InvalidTask("HEAVY_PROFILE_REQUIRED")
    return job


def route(job: dict, *, approved_ephemeral_source: bool = False) -> str:
    validate(job)
    if job["profile"] == "heavy":
        return "HYPERV_PRIVATE"
    if job["privacy"] == "PRIVATE_EVIDENCE":
        return "PRIVATE"
    if job["privacy"] == "PRIVATE_SOURCE":
        return "PUBLIC_HOSTED" if job["allow_public_ephemeral"] and approved_ephemeral_source else "PRIVATE"
    return "PUBLIC_HOSTED"


def identity(job: dict) -> str:
    validate(job)
    stable = {key: value for key, value in job.items() if key not in ("task_id", "submitted_at")}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def plan(jobs: list[dict], capacity: dict[str, int]) -> dict:
    if set(capacity) != {"PUBLIC_HOSTED", "PRIVATE", "HYPERV_PRIVATE"} or any(type(v) is not int or v < 0 or v > 32 for v in capacity.values()):
        raise InvalidTask("INVALID_CAPACITY")
    if not isinstance(jobs, list) or len(jobs) > 1000:
        raise InvalidTask("INVALID_BATCH")
    seen_ids, seen_fingerprints = set(), set()
    normalized = []
    for j in jobs:
        validate(j)
        fingerprint = identity(j)
        if j["task_id"] in seen_ids or fingerprint in seen_fingerprints:
            raise InvalidTask("DUPLICATE_OR_REPLAY")
        seen_ids.add(j["task_id"])
        seen_fingerprints.add(fingerprint)
        normalized.append((j, fingerprint, route(j)))
    normalized.sort(key=lambda item: (item[0]["submitted_at"], item[0]["task_id"]))
    used = defaultdict(int)
    result = []
    for job, fingerprint, lane in normalized:
        admitted = used[lane] < capacity[lane]
        if admitted:
            used[lane] += 1
        result.append({"task_id": job["task_id"], "project": job["project"], "source_sha": job["source"]["sha"], "fingerprint": fingerprint, "lane": lane, "decision": "ADMIT" if admitted else "DEFER_CAPACITY", "reason": "CAPACITY_DECLARED_NOT_MEASURED"})
    return {"schema": "vf-shared-test-plan/v1", "entries": result, "counts": dict(used), "note": "Planning only; not GitHub job dispatch or machine proof"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--capacity", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = plan(json.loads(args.jobs.read_text()), json.loads(args.capacity.read_text()))
    except (InvalidTask, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED_VALIDATION", "reason": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
