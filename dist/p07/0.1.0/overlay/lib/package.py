#!/usr/bin/env python3
from __future__ import annotations

# RC3 compatibility facade. The mature backup engine remains byte-for-byte in
# package_core.py. CloudPanel database export is routed through the shared
# CloudPanel foundation adapter, while build_backup keeps the safe application-
# config credential discovery used by current CloudPanel schemas.
import gzip
import os
from pathlib import Path
import time

import cloudpanel as _cloudpanel
import package_core as _core


def _file_open_elsewhere(path: Path) -> bool:
    try:
        target = path.stat()
    except OSError:
        return False
    proc = Path("/proc")
    if not proc.is_dir():
        return False
    current_pid = str(os.getpid())
    try:
        pids = list(proc.iterdir())
    except OSError:
        return False
    for pid in pids:
        if not pid.name.isdigit() or pid.name == current_pid:
            continue
        fd_dir = pid / "fd"
        try:
            for fd in fd_dir.iterdir():
                try:
                    opened = fd.stat()
                except OSError:
                    continue
                if opened.st_dev == target.st_dev and opened.st_ino == target.st_ino:
                    return True
        except OSError:
            continue
    return False


def _wait_for_quiescent_gzip(path: Path, database: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last: tuple[int, int] | None = None
    quiet_since: float | None = None
    while True:
        now = time.monotonic()
        try:
            stat_now = path.stat()
            current = (stat_now.st_size, stat_now.st_mtime_ns)
        except OSError:
            current = (0, 0)
        busy = current[0] > 0 and _file_open_elsewhere(path)
        if current[0] > 0 and not busy and current == last:
            if quiet_since is None:
                quiet_since = now
            if now - quiet_since >= 0.5:
                try:
                    total = 0
                    with gzip.open(path, "rb") as handle:
                        while True:
                            chunk = handle.read(1024 * 1024)
                            if not chunk:
                                break
                            total += len(chunk)
                    after = path.stat()
                except (OSError, EOFError) as exc:
                    raise RuntimeError(f"MySQL gzip validation failed: {database}") from exc
                if total > 0 and (after.st_size, after.st_mtime_ns) == current and not _file_open_elsewhere(path):
                    return
        else:
            quiet_since = None
        last = current
        if now >= deadline:
            raise RuntimeError(f"MySQL export did not become stable: {database}")
        time.sleep(0.1)


def _export_mysql_via_cloudpanel(databases: list[str], out_dir: Path, clpctl: str) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    _core.chmod_private(out_dir, directory=True)
    results: list[dict] = []
    for database in databases:
        filename = f"{_core.safe_name(database)}.sql.gz"
        target = out_dir / filename
        try:
            _cloudpanel.export_database(database, target, clpctl=clpctl)
        except _cloudpanel.CloudPanelError as exc:
            exit_code = "UNKNOWN" if exc.returncode is None else str(exc.returncode)
            raise RuntimeError(
                f"CloudPanel database export failed: {database} (exit {exit_code})"
            ) from exc
        _core.chmod_private(target)
        _wait_for_quiescent_gzip(target, database)
        results.append({
            "database": database,
            "file": f"mysql/{filename}",
            "method": "clpctl_db_export",
        })
    return results


# package_core.build_backup resolves export_mysql from its module globals at
# runtime. Patch only that primitive; the mature packaging engine stays intact.
_core.export_mysql = _export_mysql_via_cloudpanel

from package_core import *  # noqa: F401,F403,E402
import backup_frontend as _frontend  # noqa: E402

build_backup = _frontend.build_backup_with_discovery
export_mysql = _export_mysql_via_cloudpanel


def main() -> int:
    return _frontend.main()


if __name__ == "__main__":
    raise SystemExit(main())
