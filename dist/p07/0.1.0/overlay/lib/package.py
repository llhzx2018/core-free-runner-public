#!/usr/bin/env python3
from __future__ import annotations

# RC3 compatibility facade. The mature backup engine remains byte-for-byte in
# package_core.py. CloudPanel database export is routed through the shared
# CloudPanel foundation adapter, while build_backup keeps the safe application-
# config credential discovery used by current CloudPanel schemas.
import gzip
import os
from pathlib import Path
import shutil
import tempfile
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


def _export_identity(path: Path) -> tuple[int, int, int, int]:
    stat_now = path.stat()
    return (stat_now.st_dev, stat_now.st_ino, stat_now.st_size, stat_now.st_mtime_ns)


def _read_gzip_fully(path: Path, database: str) -> int:
    total = 0
    try:
        with gzip.open(path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
    except (OSError, EOFError) as exc:
        raise RuntimeError(f"MySQL gzip validation failed: {database}") from exc
    if total <= 0:
        raise RuntimeError(f"MySQL gzip validation failed: {database}")
    return total


def _wait_for_quiescent_gzip(
    path: Path,
    database: str,
    timeout: float = 30.0,
    quiet_seconds: float = 2.0,
) -> tuple[int, int, int, int]:
    deadline = time.monotonic() + timeout
    last: tuple[int, int, int, int] | None = None
    quiet_since: float | None = None
    while True:
        now = time.monotonic()
        try:
            current = _export_identity(path)
        except OSError:
            current = (0, 0, 0, 0)
        busy = current[2] > 0 and _file_open_elsewhere(path)
        if current[2] > 0 and not busy and current == last:
            if quiet_since is None:
                quiet_since = now
            if now - quiet_since >= quiet_seconds:
                _read_gzip_fully(path, database)
                after = _export_identity(path)
                if after == current and not _file_open_elsewhere(path):
                    return after
        else:
            quiet_since = None
        last = current
        if now >= deadline:
            raise RuntimeError(f"MySQL export did not become stable: {database}")
        time.sleep(0.1)


def _snapshot_quiescent_gzip(
    source: Path,
    target: Path,
    database: str,
    timeout: float = 45.0,
) -> None:
    deadline = time.monotonic() + timeout
    target.parent.mkdir(parents=True, exist_ok=True)
    _core.chmod_private(target.parent, directory=True)
    snapshot = target.with_name(f".{target.name}.snapshot-{os.getpid()}")
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"MySQL export did not become immutable: {database}")
            _wait_for_quiescent_gzip(
                source,
                database,
                timeout=min(remaining, 30.0),
                quiet_seconds=2.0,
            )
            before = _export_identity(source)
            shutil.copyfile(source, snapshot)
            _core.chmod_private(snapshot)
            with snapshot.open("rb+") as handle:
                handle.flush()
                os.fsync(handle.fileno())
            _read_gzip_fully(snapshot, database)
            snapshot_digest = _core.sha256_file(snapshot)
            after_copy = _export_identity(source)
            if before != after_copy or _file_open_elsewhere(source):
                snapshot.unlink(missing_ok=True)
                continue

            # CloudPanel may return before a helper atomically replaces the export
            # path. Hold a second observation window after the package-owned copy.
            time.sleep(1.0)
            after_hold = _export_identity(source)
            if after_hold != after_copy or _file_open_elsewhere(source):
                snapshot.unlink(missing_ok=True)
                continue

            source_digest = _core.sha256_file(source)
            after_digest = _export_identity(source)
            if after_digest != after_hold or source_digest != snapshot_digest:
                snapshot.unlink(missing_ok=True)
                continue

            os.replace(snapshot, target)
            _core.chmod_private(target)
            _read_gzip_fully(target, database)
            return
    finally:
        snapshot.unlink(missing_ok=True)


def _export_mysql_via_cloudpanel(databases: list[str], out_dir: Path, clpctl: str) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    _core.chmod_private(out_dir, directory=True)
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix=".vfops-mysql-export-", dir=out_dir.parent) as work:
        work_dir = Path(work)
        _core.chmod_private(work_dir, directory=True)
        for database in databases:
            filename = f"{_core.safe_name(database)}.sql.gz"
            export_source = work_dir / filename
            target = out_dir / filename
            try:
                _cloudpanel.export_database(database, export_source, clpctl=clpctl)
            except _cloudpanel.CloudPanelError as exc:
                exit_code = "UNKNOWN" if exc.returncode is None else str(exc.returncode)
                raise RuntimeError(
                    f"CloudPanel database export failed: {database} (exit {exit_code})"
                ) from exc

            # Never checksum the path CloudPanel writes. First convert it into a
            # package-owned immutable snapshot so a late writer/rename cannot
            # mutate the committed backup after verification.
            _snapshot_quiescent_gzip(export_source, target, database)
            results.append({
                "database": database,
                "file": f"mysql/{filename}",
                "method": "clpctl_db_export_immutable_snapshot",
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
