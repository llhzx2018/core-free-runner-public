#!/usr/bin/env python3
"""Public-safe multi-project request admission and bounded parallel execution.

No GitHub credentials, no runner activation and no arbitrary command strings in
requests. Command catalog is trusted *local* infrastructure configuration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROTOCOL = "vf.shared-test/v1"
REQUIRED = frozenset({"task_id", "repository", "commit_sha", "tree_sha", "test_id", "tier", "privacy", "resource_key", "timeout_seconds"})
REPO = re.compile(r"^llhzx2018/[a-z0-9][a-z0-9-]{1,80}$")
IDENT = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
RESOURCE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


class InvalidRequest(ValueError):
    pass


def fail(code):
    raise InvalidRequest(code)


def validate(item):
    if not isinstance(item, dict) or set(item) != REQUIRED:
        fail("REQUEST_FIELDS_INVALID")
    for name in ("task_id", "test_id"):
        if not isinstance(item[name], str) or not IDENT.fullmatch(item[name]):
            fail("REQUEST_ID_INVALID")
    if not isinstance(item["repository"], str) or not REPO.fullmatch(item["repository"]):
        fail("REPOSITORY_INVALID")
    if any(not isinstance(item[k], str) or not SHA.fullmatch(item[k]) for k in ("commit_sha", "tree_sha")):
        fail("SOURCE_SHA_INVALID")
    if item["tier"] not in ("light", "integration", "heavy") or item["privacy"] not in ("public_safe", "private_source", "private_evidence"):
        fail("CLASSIFICATION_INVALID")
    if not isinstance(item["resource_key"], str) or not RESOURCE.fullmatch(item["resource_key"]):
        fail("RESOURCE_KEY_INVALID")
    if type(item["timeout_seconds"]) is not int or not 1 <= item["timeout_seconds"] <= 3600:
        fail("TIMEOUT_INVALID")
    return item


def route(item):
    validate(item)
    if item["tier"] == "heavy":
        return "EXISTING_HYPERV"
    if item["privacy"] == "private_evidence":
        return "PRIVATE_SANDBOX"
    if item["privacy"] == "private_source":
        return "PUBLIC_TRANSIENT_PRIVATE_SOURCE"
    return "PUBLIC_HOSTED"


def plan(requests):
    if not isinstance(requests, list) or not 1 <= len(requests) <= 128:
        fail("BATCH_SIZE_INVALID")
    seen = set()
    tasks = []
    for raw in requests:
        item = validate(raw)
        if item["task_id"] in seen:
            fail("TASK_ID_REPLAY")
        seen.add(item["task_id"])
        tasks.append({"request": item, "lane": route(item), "resource_class": "exclusive_heavy" if item["tier"] == "heavy" else ("isolated" if item["tier"] == "integration" else "independent")})
    return {"protocol": PROTOCOL, "tasks": tasks}


def _safe_run(command, timeout_seconds):
    if not isinstance(command, list) or not command or any(not isinstance(a, str) or not a or "\x00" in a for a in command):
        fail("CATALOG_COMMAND_INVALID")
    if not Path(command[0]).is_absolute():
        fail("CATALOG_EXECUTABLE_NOT_ABSOLUTE")
    with tempfile.TemporaryDirectory(prefix="vf-public-test-") as directory:
        safe_env = {k: os.environ[k] for k in ("PATH", "LANG") if k in os.environ}
        process = subprocess.Popen(command, cwd=directory, env=safe_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            process.communicate(timeout=timeout_seconds)
            return "PASS" if process.returncode == 0 else "TEST_FAILURE", process.returncode
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            return "TIMEOUT", -9


def execute_public(planned, catalog, workers=2):
    if planned.get("protocol") != PROTOCOL or type(workers) is not int or not 1 <= workers <= 8:
        fail("PLAN_OR_CAPACITY_INVALID")
    if not isinstance(catalog, dict):
        fail("CATALOG_INVALID")
    results = [None] * len(planned["tasks"])

    def work(index, task):
        item = validate(task["request"])
        expected = route(item)
        if task["lane"] != expected:
            fail("LANE_TAMPERED")
        if expected not in ("PUBLIC_HOSTED", "PUBLIC_TRANSIENT_PRIVATE_SOURCE"):
            return {"task_id": item["task_id"], "lane": expected, "result": "DEFERRED_ROUTE"}
        # Private-source checkout is NOT performed here. Never pretend a secret
        # or exact source was fetched: the existing Hosted Lane must do that.
        if expected == "PUBLIC_TRANSIENT_PRIVATE_SOURCE":
            return {"task_id": item["task_id"], "lane": expected, "result": "BLOCKED_PRIVATE_CHECKOUT_NOT_ATTESTED"}
        command = catalog.get(item["test_id"])
        if command is None:
            return {"task_id": item["task_id"], "lane": expected, "result": "BLOCKED_TEST_CATALOG_MISSING"}
        started = time.monotonic()
        status, exit_code = _safe_run(command, item["timeout_seconds"])
        return {"task_id": item["task_id"], "lane": expected, "result": status,
                "exit_code": exit_code, "elapsed_ms": round((time.monotonic() - started) * 1000),
                "command_sha256": hashlib.sha256(json.dumps(command, separators=(",", ":")).encode()).hexdigest(),
                "sandbox_cleaned": True}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(work, i, task) for i, task in enumerate(planned["tasks"])]
        for i, future in enumerate(futures):
            results[i] = future.result()
    return {"protocol": PROTOCOL, "receipts": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "run-public"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text())
        if args.action == "plan":
            output = plan(payload)
        else:
            if args.catalog is None:
                fail("CATALOG_REQUIRED")
            output = execute_public(payload, json.loads(args.catalog.read_text()), args.workers)
        print(json.dumps(output, sort_keys=True))
        return 0
    except (InvalidRequest, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"protocol": PROTOCOL, "result": "BLOCKED_REQUEST", "reason": str(exc)[:120]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
