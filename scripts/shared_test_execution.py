"""Shared command execution for already-admitted VF test lanes.

The existing workflow owns exact Git admission, test ID, resource lock, fixed
argv, explicit synthetic environment, and workspace cleanup. This module does
not dispatch jobs, choose authorization, run shell text, or change the host.
"""
from __future__ import annotations

import json
import os
import re
import selectors
import signal
import stat
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from shared_test_result import MAX_REPORT, summarize_junit

MAX_OUTPUT = 4 * 1024 * 1024
MAX_MANIFEST = 256 * 1024
PHASE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}\Z")
FAILURE_HINTS = (
    ("NETWORK_DNS", ("could not resolve", "temporary failure in name resolution", "curl error 6")),
    ("NETWORK_TIMEOUT", ("curl error 28", "operation timed out")),
    ("LOCKFILE_MISMATCH", ("lock file is not up to date", "lockfile is not up to date", "frozen-lockfile")),
    ("RUNTIME_PLATFORM", ("requires php", "platform requirements")),
    ("INVALID_TOOL_OPTION", ("option does not exist", "unknown option", "option is not defined")),
    ("PERMISSION_DENIED", ("permission denied", "eacces")),
    ("MISSING_DEPENDENCY", ("module not found", "cannot find module", "class not found", "command not found")),
    ("DB_CONNECTION", ("sqlstate[hy000] [2002]", "connection refused")),
)

@dataclass(frozen=True)
class PhaseResult:
    phase: str
    exit_code: int | None
    reason: str
    private_output: bytes = field(repr=False)
    report: dict | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and self.reason == "EXIT_ZERO"

    def receipt(self) -> dict:
        # No command, env, absolute path or raw subprocess output.
        return {"phase": self.phase, "exit_code": self.exit_code,
                "reason": self.reason, "junit": self.report}


def _regular_bytes(path: Path, limit: int) -> bytes:
    # Never follow a report symlink, device, FIFO or hardlink. The caller
    # owns the parent directory within the admitted isolated workspace.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                or st.st_uid != os.geteuid() or st.st_size > limit):
            raise ValueError("UNSAFE_INPUT")
        data = f.read(limit + 1)
        if len(data) > limit:
            raise ValueError("INPUT_LIMIT")
        return data


def _report(path: Path | None, names: frozenset[str]) -> dict | None:
    if path is None:
        return None
    try:
        return summarize_junit(_regular_bytes(path, MAX_REPORT), known_names=names)
    except FileNotFoundError:
        return {"status": "REPORT_NOT_CREATED"}
    except (OSError, ValueError):
        return {"status": "REPORT_UNSAFE_OR_UNREADABLE"}


def _failure(output: bytes) -> str:
    low = output.decode("utf-8", errors="replace").lower()
    for reason, terms in FAILURE_HINTS:
        if any(term in low for term in terms):
            return reason
    return "NONZERO_WITHOUT_STRUCTURED_CAUSE"


def _group_exists(pid: int) -> bool:
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _stop_group(proc: subprocess.Popen) -> None:
    # Only the process group created by our own start_new_session=True.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    if _group_exists(proc.pid):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait(timeout=5)


def run_trusted_phase(argv: list[str], *, cwd: Path, env: dict[str, str],
                      phase: str, timeout: int, junit: Path | None = None,
                      known_names: frozenset[str] = frozenset()) -> PhaseResult:
    """Call a fixed, reviewed argv from an already-admitted workflow.

    The API is intentionally not a CLI or request parser. The caller retains
    its assertion/lockfile/source checks, and a zero exit is not a machine PASS.
    """
    if (not isinstance(argv, list) or not argv
            or not argv[0] or any(not isinstance(x, str) or "\0" in x for x in argv)
            or not PHASE.fullmatch(phase)
            or type(timeout) is not int or not 1 <= timeout <= 7200
            or not isinstance(env, dict) or not env.get("PATH")
            or any(not isinstance(k, str) or not isinstance(v, str)
                   or "\0" in k or "\0" in v or "=" in k for k, v in env.items())):
        raise ValueError("INVALID_TRUSTED_PHASE")
    if junit is not None and os.path.lexists(junit):
        raise ValueError("REPORT_ALREADY_EXISTS")
    try:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                start_new_session=True, shell=False)
    except FileNotFoundError:
        return PhaseResult(phase, None, "EXECUTABLE_MISSING", b"")
    except OSError:
        return PhaseResult(phase, None, "PROCESS_START_FAILED", b"")
    output = bytearray()
    reason = None
    deadline = time.monotonic() + timeout
    try:
        assert proc.stdout is not None
        with selectors.DefaultSelector() as sel:
            sel.register(proc.stdout, selectors.EVENT_READ)
            while sel.get_map():
                left = deadline - time.monotonic()
                if left <= 0:
                    reason = "PROCESS_TIMEOUT"
                    break
                for key, _ in sel.select(left):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        sel.unregister(key.fileobj)
                    elif len(output) + len(chunk) > MAX_OUTPUT:
                        reason = "OUTPUT_LIMIT"
                        break
                    else:
                        output.extend(chunk)
                if reason:
                    break
        if not reason:
            try:
                proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                reason = "PROCESS_TIMEOUT"
        if not reason and _group_exists(proc.pid):
            reason = "PROCESS_GROUP_REMAINS"
        if reason:
            _stop_group(proc)
    except BaseException:
        _stop_group(proc)
        raise
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
    report = _report(junit, known_names)
    if reason is None:
        if proc.returncode == 0:
            if junit is not None and (not report or report.get("status") != "REPORT_OBSERVED" or report.get("failed", 0)):
                reason = "REPORT_INCONSISTENT_OR_MISSING"
            else:
                reason = "EXIT_ZERO"
        elif report and report.get("failed", 0):
            reason = "REPORTED_TEST_FAILURE"
        else:
            reason = _failure(bytes(output))
    return PhaseResult(phase, proc.returncode, reason, bytes(output), report)


def _manifest(root: Path, name: str) -> dict:
    try:
        data = json.loads(_regular_bytes(root / name, MAX_MANIFEST))
    except (OSError, ValueError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def discover_stack(root: Path) -> tuple[str, ...]:
    """Advisory capabilities only: never infer authorization or coverage."""
    hints = set()
    php = _manifest(root, "composer.json")
    node = _manifest(root, "package.json")
    php_deps = set()
    node_deps = set()
    for key in ("require", "require-dev"):
        if isinstance(php.get(key), dict):
            php_deps.update(php[key])
    for key in ("dependencies", "devDependencies"):
        if isinstance(node.get(key), dict):
            node_deps.update(node[key])
    if php:
        hints.update(("php", "composer"))
    if "laravel/framework" in php_deps:
        hints.add("laravel")
    if "phpunit/phpunit" in php_deps:
        hints.add("phpunit")
    for capability, dependencies in (
        ("vue", {"vue"}), ("vitest", {"vitest"}), ("vite", {"vite"}),
        ("playwright", {"playwright", "@playwright/test", "playwright-core"}),
    ):
        if dependencies & node_deps:
            hints.add(capability)
    if node:
        hints.add("node")
    for name, capability in (("pyproject.toml", "python"), ("requirements.txt", "python"),
                             ("Dockerfile", "docker"), ("compose.yml", "docker"),
                             ("docker-compose.yml", "docker")):
        path = root / name
        if path.is_file() and not path.is_symlink():
            hints.add(capability)
    for rel, capability in (("tests", "python"), ("bin", "shell")):
        folder = root / rel
        if folder.is_dir() and not folder.is_symlink():
            # Only bounded, direct source-shape hints; no script execution.
            for n, item in enumerate(folder.iterdir()):
                if n >= 256:
                    break
                if item.is_file() and not item.is_symlink() and (
                    (capability == "python" and item.suffix == ".py")
                    or (capability == "shell" and item.suffix == ".sh")):
                    hints.add(capability)
                    break
    return tuple(sorted(hints))
