#!/usr/bin/env python3
"""P07-M05 新服务器初始化 — real first admin from actual module UI on FREE GH host.

Run only after a fresh official CloudPanel installation on a registered ephemeral
GitHub-hosted runner. Pulls the real installed UI function, sends a random
throwaway credential via a private pseudo-terminal, and verifies the backend's
READY status. Never prints or persists username, email, password, terminal
transcript, CLI command args or any admin/DB private data.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import pty
import secrets
import select
import signal
import subprocess
import sys
import tempfile
import termios
import time

ROOT = Path("/opt/vfops-modules/m05/current")
CORE = ROOT / "bin/vfops-init-core"
UI = ROOT / "bin/vfops-init-ui"
ALLOWED_REF = "refs/heads/feat/p07-unified-independent-module-router-20261112"


def fail(message: str) -> None:
    raise SystemExit("P07_M05_FIRST_ADMIN=" + message)


def status() -> str:
    p = subprocess.run(
        ["bash", str(CORE), "server-migrate", "target-status"],
        text=True, capture_output=True, timeout=45,
    )
    if p.returncode:
        fail("TARGET_STATUS_COMMAND_FAILED")
    try:
        value = json.loads(p.stdout)
    except (ValueError, TypeError):
        fail("TARGET_STATUS_INVALID_JSON")
    if value.get("writes_performed") is not False:
        fail("TARGET_STATUS_NOT_READ_ONLY")
    return str(value.get("status", ""))


def real_function_harness() -> str:
    source = UI.read_text(encoding="utf-8")
    start = "\ncloudpanel_status() {\n"
    finish = "\nsystem_update_new_server() {\n"
    if source.count(start) != 1 or source.count(finish) != 1:
        fail("CANONICAL_UI_FUNCTION_BOUNDARY_CHANGED")
    selected = source.split(start, 1)[1].split(finish, 1)[0]
    if not (
        "run_clpctl_root() {" in selected
        and "cloudpanel_create_first_admin() {" in selected
        and "run_clpctl_root user:add" in selected
    ):
        fail("CANONICAL_UI_FIRST_ADMIN_FUNCTION_MISSING")
    return (
        "#!/usr/bin/env bash\nset -Eeuo pipefail\n"
        "CORE='/opt/vfops-modules/m05/current/bin/vfops-init-core'\n"
        "ui_attention(){ :; }\nui_note(){ :; }\n"
        "ui_bad(){ :; }\nui_good(){ :; }\n"
        + "cloudpanel_status() {\n" + selected
        + "\ncloudpanel_create_first_admin\n"
    )


def invoke(harness: Path, *, interactive: bool) -> int:
    if not interactive:
        with open(os.devnull, "rb") as devnull:
            p = subprocess.run(
                ["bash", str(harness)], stdin=devnull,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15, check=False,
            )
            return p.returncode

    # The random test password is passed only over a disabled-echo PTY.
    # No CLI transcript, password, or raw data is ever printed or uploaded.
    name = "p07trial" + secrets.token_hex(3)
    email = "p07-trial-admin@example.invalid"
    password = secrets.token_urlsafe(30)
    master, slave = pty.openpty()
    settings = termios.tcgetattr(slave)
    settings[3] &= ~(termios.ECHO | termios.ECHONL)
    termios.tcsetattr(slave, termios.TCSANOW, settings)

    process = subprocess.Popen(
        ["bash", str(harness)], stdin=slave, stdout=slave, stderr=slave,
        close_fds=True, start_new_session=True,
    )
    os.close(slave)
    try:
        # CLI asks username, email, password, confirmation in this order.
        inputs = "\n".join((name, email, password, password)) + "\n"
        os.write(master, inputs.encode("utf-8"))
        inputs = ""
        password = ""
        name = ""
        email = ""
        limit = time.monotonic() + 180
        while process.poll() is None and time.monotonic() < limit:
            readable, _, _ = select.select([master], [], [], 0.6)
            if readable:
                try:
                    os.read(master, 8192)  # discard secret-bearing output
                except OSError:
                    pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=4)
            fail("CANONICAL_ADMIN_UI_TIMEOUT")
        return int(process.returncode)
    finally:
        os.close(master)


def main() -> None:
    if not (
        os.geteuid() == 0
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY") == "llhzx2018/core-free-runner-public"
        and os.environ.get("GITHUB_REF") == ALLOWED_REF
        and bool(os.environ.get("GITHUB_RUN_ID"))
        and os.environ.get("P07_M05_THROWAWAY_GITHUB_VM") == "YES_I_ACKNOWLEDGE_EPHEMERAL_GH_VM"
        and os.environ.get("P07_M05_TEST_REAL_FIRST_ADMIN") == "YES"
    ):
        fail("DENIED_NON_EPHEMERAL_RUNNER")
    if not (CORE.is_file() and UI.is_file()):
        fail("NOT_INSTALLED_EXACT_M05")
    if status() != "CLOUDPANEL_ADMIN_REQUIRED":
        fail("EXPECTED_FIRST_ADMIN_PENDING")
    harness = real_function_harness()
    with tempfile.TemporaryDirectory(prefix="p07-m05-ui-", dir=os.environ["RUNNER_TEMP"]) as tmp:
        script = Path(tmp) / "actual-m05-first-admin.sh"
        script.write_text(harness, encoding="utf-8")
        script.chmod(0o700)
        # A non-interactive invocation MUST fail before user:add.
        if invoke(script, interactive=False) == 0:
            fail("NONINTERACTIVE_ADMIN_CREATION_ACCEPTED")
        if status() != "CLOUDPANEL_ADMIN_REQUIRED":
            fail("NONINTERACTIVE_ATTEMPT_MUTATED_CLOUDPANEL")
        print("P07_M05_FIRST_ADMIN_NONINTERACTIVE_DENIAL=PASS")
        if invoke(script, interactive=True) != 0:
            fail("REAL_FIRST_ADMIN_UI_RETURNED_FAILURE")

    if status() != "CLOUDPANEL_READY":
        fail("REAL_FIRST_ADMIN_DID_NOT_MAKE_CLOUDPANEL_READY")
    print("P07_M05_FIRST_ADMIN_REAL_PRODUCT_UI=PASS")
    print("P07_M05_FIRST_ADMIN_CLOUDPANEL_READY_READBACK=PASS")
    print("P07_M05_FIRST_ADMIN_CREDENTIALS_PUBLISHED=NO")
    print("P07_M05_FIRST_ADMIN_OWNER_PRODUCTION=UNTOUCHED")


if __name__ == "__main__":
    main()
