#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
from typing import Sequence

import cloudpanel

DEFAULT_TIMEOUT = 300


class CloudPanelSiteUserError(RuntimeError):
    def __init__(self, operation: str, returncode: int | None = None):
        self.operation = operation
        self.returncode = returncode
        suffix = "" if returncode is None else f" (exit {returncode})"
        super().__init__(f"CloudPanel site-user operation failed: {operation}{suffix}")


@dataclass(frozen=True)
class SiteUserResult:
    operation: str
    returncode: int
    stdout: str


def run(
    site_user: str,
    args: Sequence[str],
    *,
    runuser: str = "runuser",
    clpctl: str = "clpctl",
    timeout: int = DEFAULT_TIMEOUT,
    operation: str | None = None,
) -> SiteUserResult:
    user = cloudpanel.validate_user(site_user)
    if not args:
        raise ValueError("CloudPanel site-user command is required")
    safe_args = [cloudpanel._scalar(item, "argument") for item in args]
    command = [cloudpanel._scalar(runuser, "runuser"), "-u", user, "--", cloudpanel._scalar(clpctl, "clpctl"), *safe_args]
    op = operation or safe_args[0]
    try:
        proc = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CloudPanelSiteUserError(op) from exc
    if proc.returncode != 0:
        # Never include command output in exceptions: site commands may expose app data.
        raise CloudPanelSiteUserError(op, proc.returncode)
    return SiteUserResult(op, proc.returncode, proc.stdout)


def reset_permissions(
    site_user: str,
    path: str | Path,
    *,
    directories: str = "770",
    files: str = "660",
    runuser: str = "runuser",
    clpctl: str = "clpctl",
) -> None:
    if not re.fullmatch(r"[0-7]{3,4}", directories) or not re.fullmatch(r"[0-7]{3,4}", files):
        raise ValueError("invalid permission mode")
    run(
        site_user,
        [
            "system:permissions:reset",
            f"--directories={directories}",
            f"--files={files}",
            f"--path={cloudpanel.validate_file(path, 'permissions path')}",
        ],
        runuser=runuser,
        clpctl=clpctl,
        operation="permissions_reset",
    )


def purge_varnish(
    site_user: str,
    target: str = "all",
    *,
    runuser: str = "runuser",
    clpctl: str = "clpctl",
) -> None:
    value = cloudpanel._scalar(target.strip(), "varnish purge target")
    run(
        site_user,
        ["varnish-cache:purge", f"--purge={value}"],
        runuser=runuser,
        clpctl=clpctl,
        operation="varnish_purge",
    )


def export_database(
    site_user: str,
    database: str,
    output: str | Path,
    *,
    runuser: str = "runuser",
    clpctl: str = "clpctl",
) -> Path:
    target = Path(cloudpanel.validate_file(output, "database export file"))
    run(
        site_user,
        ["db:export", f"--databaseName={cloudpanel.validate_name(database, 'database')}", f"--file={target}"],
        runuser=runuser,
        clpctl=clpctl,
        timeout=1800,
        operation="db_export",
    )
    if not target.is_file() or target.stat().st_size == 0:
        raise CloudPanelSiteUserError("db_export_output")
    return target


def import_database(
    site_user: str,
    database: str,
    source: str | Path,
    *,
    runuser: str = "runuser",
    clpctl: str = "clpctl",
) -> None:
    dump = Path(cloudpanel.validate_file(source, "database import file"))
    if not dump.is_file():
        raise ValueError("database import file does not exist")
    run(
        site_user,
        ["db:import", f"--databaseName={cloudpanel.validate_name(database, 'database')}", f"--file={dump}"],
        runuser=runuser,
        clpctl=clpctl,
        timeout=1800,
        operation="db_import",
    )
