#!/usr/bin/env python3
from __future__ import annotations

# CloudPanel compatibility facade for the mature sandbox restore engine.
# The large, already-tested implementation remains byte-for-byte in
# restore_apply_core.py. All CloudPanel command execution is routed through
# lib/cloudpanel.py so backup/restore/migration share one platform adapter.
import cloudpanel as _cloudpanel
import restore_apply_core as _core


def _adapter_run_clpctl(clpctl: str, args: list[str], timeout: int = 1800) -> None:
    operation = args[0] if args else "unknown"
    try:
        _cloudpanel.run(args, clpctl=clpctl, timeout=timeout, operation=operation)
    except _cloudpanel.CloudPanelError as exc:
        suffix = "" if exc.returncode is None else f" (exit {exc.returncode})"
        raise _core.SandboxRestoreError(
            f"CloudPanel CLI command failed: {operation}{suffix}"
        ) from exc


# Functions defined in restore_apply_core resolve this global at runtime.
_core.run_clpctl = _adapter_run_clpctl

from restore_apply_core import *  # noqa: F401,F403,E402

# Make the compatibility name explicit for callers/tests.
run_clpctl = _adapter_run_clpctl


def main() -> int:
    return _core.main()


if __name__ == "__main__":
    raise SystemExit(main())
