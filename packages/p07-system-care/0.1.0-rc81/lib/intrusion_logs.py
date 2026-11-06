from __future__ import annotations

import datetime as dt
import gzip
import os
import re
import stat
from pathlib import Path
from typing import BinaryIO, Optional

from intrusion_state import iso

LOG_RE = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+"(?P<method>[A-Z]+)\s+(?P<target>\S+)(?:\s+HTTP/[^\"]+)?"\s+(?P<status>\d{3})\b'
)
DEFAULT_MAX_LOG_FILES = 12
DEFAULT_MAX_LOG_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_LINE_BYTES = 16 * 1024


def log_dir(root: Path) -> Optional[Path]:
    """Find a CloudPanel site-user log directory without following a symlink escape."""
    root = root.resolve(strict=True)
    for parent in [root] + list(root.parents):
        if parent.name != "htdocs":
            continue
        user_home = parent.parent.resolve(strict=True)
        candidate = user_home / "logs"
        try:
            st = candidate.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            return None
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(user_home)
        except (FileNotFoundError, ValueError):
            return None
        return resolved
    return None


def log_paths(base: Path, max_files: int = DEFAULT_MAX_LOG_FILES) -> tuple[list[Path], bool]:
    """Enumerate recent access logs without descending through symlink directories."""
    candidates: list[tuple[float, Path]] = []
    seen: set[str] = set()
    for current, dirs, files in os.walk(base, followlinks=False):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if not (current_path / name).is_symlink()]
        for name in files:
            lower = name.lower()
            if "access" not in lower or not (lower.endswith(".log") or ".log." in lower or lower.endswith(".gz")):
                continue
            path = current_path / name
            try:
                st = path.lstat()
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                continue
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            candidates.append((st.st_mtime, path))
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = [path for _, path in candidates[:max_files]]
    return selected, len(candidates) > len(selected)


def parse_time(value: str) -> Optional[dt.datetime]:
    try:
        return dt.datetime.strptime(value, "%d/%b/%Y:%H:%M:%S %z").astimezone(dt.timezone.utc)
    except ValueError:
        return None


def open_log(path: Path) -> BinaryIO:
    """Open one regular log through O_NOFOLLOW when available."""
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise OSError(f"log path is not regular: {path}")
        raw = os.fdopen(fd, "rb")
        fd = -1
        if path.suffix == ".gz":
            return gzip.GzipFile(fileobj=raw, mode="rb")
        return raw
    finally:
        if fd >= 0:
            os.close(fd)


def correlate(
    root: Path,
    center_epoch: int,
    limit: int = 20,
    *,
    max_files: int = DEFAULT_MAX_LOG_FILES,
    max_bytes: int = DEFAULT_MAX_LOG_BYTES,
    max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
) -> tuple[list[dict], dict]:
    """Return query-redacted clues with an explicit bounded-read result."""
    base = log_dir(root)
    meta = {
        "status": "COMPLETE",
        "files_scanned": 0,
        "bytes_read": 0,
        "max_files": max_files,
        "max_bytes": max_bytes,
    }
    if base is None:
        meta["status"] = "NOT_AVAILABLE"
        return [], meta
    if max_files < 1 or max_bytes < 1 or max_line_bytes < 1:
        raise ValueError("invalid log correlation budget")

    center = dt.datetime.fromtimestamp(center_epoch, tz=dt.timezone.utc)
    low, high = center - dt.timedelta(minutes=15), center + dt.timedelta(minutes=15)
    rows = []
    paths, file_limit_hit = log_paths(base, max_files=max_files)
    if file_limit_hit:
        meta["status"] = "PARTIAL_BUDGET"

    for path in paths:
        if meta["bytes_read"] >= max_bytes:
            meta["status"] = "PARTIAL_BUDGET"
            break
        try:
            st = path.lstat()
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                continue
            if dt.datetime.fromtimestamp(st.st_mtime, tz=dt.timezone.utc) < low - dt.timedelta(days=1):
                continue
            handle = open_log(path)
        except (OSError, EOFError, gzip.BadGzipFile):
            continue
        meta["files_scanned"] += 1
        try:
            with handle:
                while meta["bytes_read"] < max_bytes:
                    remaining = max_bytes - meta["bytes_read"]
                    read_size = min(max_line_bytes + 1, remaining)
                    try:
                        raw = handle.readline(read_size)
                    except (OSError, EOFError, gzip.BadGzipFile):
                        break
                    if not raw:
                        break
                    meta["bytes_read"] += len(raw)
                    if len(raw) > max_line_bytes:
                        while raw and not raw.endswith(b"\n") and meta["bytes_read"] < max_bytes:
                            remaining = max_bytes - meta["bytes_read"]
                            try:
                                raw = handle.readline(min(max_line_bytes + 1, remaining))
                            except (OSError, EOFError, gzip.BadGzipFile):
                                raw = b""
                                break
                            meta["bytes_read"] += len(raw)
                        if meta["bytes_read"] >= max_bytes and raw and not raw.endswith(b"\n"):
                            meta["status"] = "PARTIAL_BUDGET"
                        continue
                    if meta["bytes_read"] >= max_bytes and raw and not raw.endswith(b"\n"):
                        meta["status"] = "PARTIAL_BUDGET"
                        break
                    line = raw.decode("utf-8", errors="replace")
                    match = LOG_RE.match(line)
                    if not match:
                        continue
                    stamp = parse_time(match.group("ts"))
                    if stamp is None or not (low <= stamp <= high):
                        continue
                    target = match.group("target").split("?", 1)[0].split("#", 1)[0]
                    if not target.startswith("/"):
                        target = "/"
                    rows.append({
                        "timestamp": iso(stamp), "source_ip": match.group("ip")[:128],
                        "method": match.group("method")[:16], "path_without_query": target[:2048],
                        "status": int(match.group("status")),
                        "classification": "CORRELATED_REQUEST / POSSIBLE_ENTRY_CLUE",
                        "correlation_basis": "FILE_MTIME_PLUS_MINUS_15M_UNTRUSTED_HINT",
                    })
                    if len(rows) >= limit:
                        return rows, meta
        except (OSError, EOFError, gzip.BadGzipFile):
            continue
        if meta["bytes_read"] >= max_bytes:
            meta["status"] = "PARTIAL_BUDGET"
            break
    return rows, meta
