from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Optional

SCHEMA = "p07.system-care.intrusion-evidence.v1"
DEFAULT_STATE_DIR = "/var/lib/vf-system-care/intrusion-evidence"
RETENTION_DAYS = 90


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: Optional[dt.datetime] = None) -> str:
    value = value or utcnow()
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


@contextmanager
def exclusive_lock(state_dir: Path) -> Iterator[None]:
    """Serialize baseline/scan writes so concurrent timer/manual runs cannot lose evidence."""
    ensure_dir(state_dir)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(state_dir / ".lock", flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def write_json(path: Path, data: object) -> None:
    ensure_dir(path.parent)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(tmp, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"invalid JSON object: {path}")
    return value


def read_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    doc = read_json(path)
    if doc.get("schema") != SCHEMA:
        raise ValueError("invalid events schema")
    rows = doc.get("events")
    if not isinstance(rows, list):
        raise ValueError("invalid events list")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid event row")
    return rows


def write_events(path: Path, rows: list[dict]) -> None:
    write_json(path, {"schema": SCHEMA, "events": rows})


def prune_events(
    rows: list[dict],
    now: dt.datetime,
    *,
    preserve_since: Optional[dt.datetime] = None,
    preserve_ids: Optional[Iterable[str]] = None,
) -> list[dict]:
    """Apply normal retention without deleting evidence that belongs to an open/current incident."""
    cutoff = now - dt.timedelta(days=RETENTION_DAYS)
    protected = {value for value in (preserve_ids or []) if value}
    kept = []
    for row in rows:
        if row.get("event_id") in protected:
            kept.append(row)
            continue
        when = parse_iso(row.get("first_detected_at"))
        if when is None:
            kept.append(row)
            continue
        if preserve_since is not None and when >= preserve_since:
            kept.append(row)
            continue
        if when >= cutoff:
            kept.append(row)
    return kept
