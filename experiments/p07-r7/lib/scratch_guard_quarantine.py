"""R7 scratch-only exact-line quarantine of unsafe versioned SET @ commands.

NOT a production SQL repair, NOT a clean restore, NOT authorization to migrate.
The original bytes remain unchanged; only a private, transient client stdin
stream may omit exactly classified guarded SET comment lines. No SQL is logged.
"""
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
import re
from typing import Iterator
import verify
import sql_diff_evidence as evidence

MAX_BYTES = 512 * 1024 * 1024
MAX_GUARD_LINE = 64 * 1024
_SET = re.compile(r"^SET\s+@[A-Za-z_][A-Za-z_0-9$]*\b", re.I)


class QuarantineBlocked(RuntimeError):
    pass


def _classify(line: bytes) -> bool:
    """Return true ONLY for a single standalone unsafe guarded SET @ line."""
    if b"SET" not in line.upper() or b"@" not in line or b"/*!" not in line:
        return False
    if len(line) > MAX_GUARD_LINE:
        raise QuarantineBlocked("QUARANTINE_GUARD_LINE_TOO_LARGE")
    try:
        raw = line.strip().decode("utf-8", errors="strict")
    except UnicodeError:
        raise QuarantineBlocked("QUARANTINE_GUARD_ENCODING_UNPROVEN") from None
    match = evidence._GUARD_RE.fullmatch(raw)
    if not match or not 40000 <= int(match.group(1)) <= 89999:
        raise QuarantineBlocked("QUARANTINE_GUARD_BOUNDARY_UNPROVEN")
    body = re.sub(r"\s+", " ", match.group(2).strip())
    if not _SET.match(body):
        raise QuarantineBlocked("QUARANTINE_GUARD_NOT_SET")
    known = verify._CROSS_ENGINE_DYNAMIC_IF_RE.fullmatch(body)
    if known:
        unsafe = any(
            not verify._cross_engine_safe_dynamic_branch(known.group(name))
            for name in ("yes", "no")
        )
        return unsafe
    if verify._cross_engine_known_session(raw):
        return False
    return True


def _scan(sql_path: Path) -> tuple[str, int, int]:
    sha = hashlib.sha256()
    removed = 0
    size = 0
    try:
        with gzip.open(sql_path, "rb") as stream:
            for line in stream:
                size += len(line)
                if size > MAX_BYTES:
                    raise QuarantineBlocked("QUARANTINE_UNCOMPRESSED_SIZE_LIMIT")
                sha.update(line)
                if _classify(line):
                    removed += 1
        return sha.hexdigest(), removed, size
    except QuarantineBlocked:
        raise
    except (OSError, EOFError, UnicodeError, ValueError):
        raise QuarantineBlocked("QUARANTINE_SQL_UNREADABLE") from None


def plan(sql_path: Path) -> dict:
    """Build bounded, source-local private plan; no SQL fragments/PKs emitted."""
    digest, removed, size = _scan(sql_path)
    try:
        ev = evidence.dynamic_guard_syntax_counts(sql_path)
    except Exception:
        raise QuarantineBlocked("QUARANTINE_CLASSIFIER_UNAVAILABLE") from None
    keys = ("recognized_unsafe", "double_quoted_if", "other_unknown_set")
    if any(type(ev.get(k)) is not int or not 0 <= ev[k] <= 10000 for k in keys):
        raise QuarantineBlocked("QUARANTINE_GUARD_COUNTS_UNPROVEN")
    expected = sum(ev[k] for k in keys)
    if expected != removed:
        raise QuarantineBlocked("QUARANTINE_CLASSIFIER_DRIFT")
    return {"_digest": digest, "removed": removed, "size": size}


def filtered_bytes(sql_path: Path, private_plan: dict) -> Iterator[bytes]:
    """Yield original lines except exact standalone guarded SET directives.

    Consume the iterator completely: digest and omitted count are verified
    at EOF. Any mismatch is a hard failed scratch import even if SQL ran.
    """
    if not isinstance(private_plan, dict):
        raise QuarantineBlocked("QUARANTINE_PLAN_MISSING")
    old_digest = private_plan.get("_digest")
    old_count = private_plan.get("removed")
    old_size = private_plan.get("size")
    if (not isinstance(old_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", old_digest)
            or type(old_count) is not int or old_count < 0
            or type(old_size) is not int or not 0 <= old_size <= MAX_BYTES):
        raise QuarantineBlocked("QUARANTINE_PLAN_INVALID")
    sha = hashlib.sha256()
    count = 0
    total = 0
    try:
        with gzip.open(sql_path, "rb") as stream:
            for line in stream:
                total += len(line)
                if total > MAX_BYTES:
                    raise QuarantineBlocked("QUARANTINE_UNCOMPRESSED_SIZE_LIMIT")
                sha.update(line)
                if _classify(line):
                    count += 1
                    continue
                yield line
    except QuarantineBlocked:
        raise
    except (OSError, EOFError, UnicodeError, ValueError):
        raise QuarantineBlocked("QUARANTINE_SQL_UNREADABLE") from None
    if sha.hexdigest() != old_digest or count != old_count or total != old_size:
        raise QuarantineBlocked("QUARANTINE_SOURCE_CHANGED")
