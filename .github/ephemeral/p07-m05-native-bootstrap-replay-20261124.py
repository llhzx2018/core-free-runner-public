#!/usr/bin/env python3
"""P07-M05 disposable read-only diagnostic of the exact native bootstrap sequence.

In transient Public GitHub Hosted only, never Production/CP2/CloudPanel.
Process stdout/stderr never leaves this runtime, including on failure.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import yaml

ROOT = Path(sys.argv[1]).resolve()
WORKFLOW = ROOT / ".github/workflows/ci.yml"
assert WORKFLOW.is_file() and ROOT.name == ".p07-private"
assert (ROOT / "VERSION").read_text().strip() == "0.1.0"
assert (ROOT / "BUILD_ID").read_text().strip() != "0.1.0-release114"
steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["bootstrap"]["steps"]
assert len(steps) >= 40, "UNEXPECTED_NATIVE_BOOTSTRAP_STEP_SET"
secret = os.environ.get("TEST_GOV_TOKEN", "")
assert len(secret) >= 12, "REGISTERED_RUNTIME_READ_TOKEN_UNAVAILABLE"
test_whitelist = frozenset((
    "AssertionError", "ImportError", "ModuleNotFoundError", "KeyError",
    "FileNotFoundError", "PermissionError", "SyntaxError", "TypeError",
    "ValueError", "OSError", "RuntimeError", "TimeoutExpired",
))
total = 0
with tempfile.TemporaryDirectory(prefix="p07-native-bootstrap-") as out:
    temp = Path(out)
    for index, step in enumerate(steps, 1):
        name = str(step.get("name") or "Checkout exact product")
        identity = hashlib.sha256(name.encode()).hexdigest()[:12]
        if step.get("uses"):
            assert index == 1, "UNEXPECTED_THIRD_PARTY_NATIVE_ACTION"
            print("P07_M05_NATIVE_BOOTSTRAP_CHECKOUT_REUSED=PASS")
            continue
        condition = str(step.get("if") or "")
        if condition:
            if "steps.source_build.outputs.id" in condition:
                print("P07_M05_NATIVE_BOOTSTRAP_RELEASE114_IRRELEVANT=SKIPPED")
                continue
            if "head.repo.full_name != github.repository" in condition:
                print("P07_M05_NATIVE_BOOTSTRAP_UNTRUSTED_FORK_BRANCH=SKIPPED")
                continue
            if "head.repo.full_name == github.repository" not in condition:
                print("P07_M05_NATIVE_BOOTSTRAP_UNKNOWN_CONDITION_INDEX=" + str(index))
                raise SystemExit(42)
        code = step.get("run")
        assert isinstance(code, str) and code.strip(), "UNSUPPORTED_NATIVE_STEP"
        env = dict(os.environ)
        env.pop("TEST_GOV_TOKEN", None)
        env.pop("GOV_DOC_READ_TOKEN", None)
        env.pop("GITHUB_BASE_REF", None)
        env["ARCH_EVENT_NAME"] = "pull_request"
        env["ARCH_PR_BASE_REF"] = "main"
        env["GITHUB_EVENT_NAME"] = "pull_request"
        env["GITHUB_OUTPUT"] = str(temp / "github-output")
        env["RUNNER_TEMP"] = str(temp)
        env["GITHUB_WORKSPACE"] = str(ROOT)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if "GOV_DOC_READ_TOKEN" in step.get("env", {}):
            env["GOV_DOC_READ_TOKEN"] = secret
        print(f"P07_M05_NATIVE_BOOTSTRAP_STEP_BEGIN={index}:{identity}",flush=True)
        try:
            result = subprocess.run(
                ["bash", "-Ee", "-o", "pipefail", "-c", code],
                cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=155, check=False,
            )
        except subprocess.TimeoutExpired:
            print("P07_M05_NATIVE_BOOTSTRAP_FIRST_FAILURE_INDEX=" + str(index))
            print("P07_M05_NATIVE_BOOTSTRAP_FAILURE_CLASS=STEP_TIMEOUT")
            raise SystemExit(43)
        if result.returncode:
            output = (result.stdout + b"\n" + result.stderr).decode("utf-8", "replace")
            types = sorted(set(re.findall(r"\b[A-Za-z]+Error\b", output)) & test_whitelist)
            print("P07_M05_NATIVE_BOOTSTRAP_FIRST_FAILURE_INDEX=" + str(index))
            print("P07_M05_NATIVE_BOOTSTRAP_FAILURE_STEP_HASH=" + identity)
            print("P07_M05_NATIVE_BOOTSTRAP_FAILURE_EXIT=" + str(result.returncode))
            print("P07_M05_NATIVE_BOOTSTRAP_FAILURE_CLASSES=" + ",".join(types[:4]))
            print("P07_M05_NATIVE_BOOTSTRAP_REPLAY=FAIL_ISOLATED")
            raise SystemExit(44)
        total += 1
        print(f"P07_M05_NATIVE_BOOTSTRAP_STEP_PASS={index}",flush=True)
print("P07_M05_NATIVE_BOOTSTRAP_STEPS_EXECUTED=" + str(total))
print("P07_M05_NATIVE_BOOTSTRAP_REPLAY=PASS_ISOLATED")
print("P07_M05_NATIVE_BUILDKITE_REQUIRED_CHECK=NOT_SUBSTITUTED")
