"""P07 advisory-only SQL byte equality for prepared *synthetic/offline* dumps.

Preserves all uncompressed SQL bytes, including invalid UTF-8, DML, DDL,
guards, and comments. Does not parse SQL, repair source encoding, or import
to a database. Equal dump bytes are NOT independent database correctness or
recovery proof. Never call this an acceptance/cutover gate.
"""
from __future__ import annotations

import gzip
import hashlib
import os
from pathlib import Path
import stat
from typing import Any

MAX_BYTES = 1024 * 1024 * 1024
BLOCK_BYTES = 1024 * 1024


class EvidenceUnavailable(ValueError):
    """Non-sensitive fixed reason code (no SQL, names, paths, or digests)."""


def _safe_input(path: Path) -> None:
    try:
        meta = path.lstat()
    except OSError:
        raise EvidenceUnavailable("DUMP_UNAVAILABLE") from None
    if not stat.S_ISREG(meta.st_mode) or (meta.st_mode & 0o022):
        raise EvidenceUnavailable("DUMP_PERMISSIONS_OR_TYPE_UNSAFE")
    if not path.name.endswith(".gz"):
        raise EvidenceUnavailable("GZIP_DUMP_REQUIRED")


def _digest_uncompressed(path: Path, *, max_bytes: int) -> tuple[bytes, int]:
    _safe_input(path)
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise EvidenceUnavailable("INVALID_SCAN_CAP")
    digest = hashlib.sha256()
    count = 0
    try:
        with gzip.open(path, "rb") as fp:
            while True:
                chunk = fp.read(min(BLOCK_BYTES, max_bytes - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                if count > max_bytes:
                    raise EvidenceUnavailable("SCAN_LIMIT_EXCEEDED")
                digest.update(chunk)
    except (OSError, EOFError, UnicodeError):
        raise EvidenceUnavailable("GZIP_STREAM_INVALID") from None
    return digest.digest(), count


def compare_sql_bytes(
    source: Path, target: Path, *, max_bytes: int = MAX_BYTES
) -> dict[str, Any]:
    """Only full uncompressed dump equality; never a migration PASS.

    The checksum is calculated independently for both gzip streams and never
    printed. A source SQL export is not proof of original DB provenance.
    """
    a_hash, a_bytes = _digest_uncompressed(source, max_bytes=max_bytes)
    b_hash, b_bytes = _digest_uncompressed(target, max_bytes=max_bytes)
    equal = a_hash == b_hash and a_bytes == b_bytes
    return {
        "schema": "P07_SQL_RAW_BYTE_ADVISORY_V1",
        "verification": "NOT_A_PASS_GATE",
        "comparison": ("EXACT_UNCOMPRESSED_SQL_BYTES_NOT_VERIFIED"
                       if equal else "UNCOMPRESSED_SQL_BYTES_DIFFER"),
        "source_bytes": a_bytes,
        "target_bytes": b_bytes,
        "source_export_provenance_verified": False,
        "target_restore_verified": False,
        "dynamic_sql_semantics_verified": False,
        "database_writes_performed": False,
        "migration_resume_allowed": False,
        "cutover_allowed": False,
    }
