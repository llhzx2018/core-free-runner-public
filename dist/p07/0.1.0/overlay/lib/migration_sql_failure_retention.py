"""P07 private forensic retention for a failed already-started SQL import.

Writes ONLY owner-private migration evidence on TARGET. Never accepts a SQL
verifier failure as PASS, retries import, changes business data or creates a
new migration. The original source may still be live (no final parity claim).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


class SqlFailureEvidenceBlocked(RuntimeError):
    pass


def _secure_work(work: Path) -> None:
    try:
        metadata = work.lstat()
    except OSError:
        raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_DIRECTORY_UNAVAILABLE") from None
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o077):
        raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_DIRECTORY_UNSAFE")


def _owned_digest(path: Path) -> dict[str, Any]:
    """Digest only a private regular file, without following links."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {"status": "MISSING"}
    except OSError:
        raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_FILE_UNAVAILABLE") from None
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1):
            raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_FILE_UNSAFE")
        # A SQL export should never be world readable, even if rsync copied a
        # source permission that was unexpectedly permissive.
        if meta.st_mode & 0o077:
            os.fchmod(fd, 0o600)
            meta = os.fstat(fd)
        if meta.st_size <= 0:
            raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_FILE_EMPTY")
        hasher = hashlib.sha256()
        with os.fdopen(os.dup(fd), "rb", closefd=True) as stream:
            while data := stream.read(1024 * 1024):
                hasher.update(data)
        end = os.fstat(fd)
        if (meta.st_dev, meta.st_ino, meta.st_size, meta.st_mtime_ns) != (
                end.st_dev, end.st_ino, end.st_size, end.st_mtime_ns):
            raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_FILE_CHANGED")
        return {"status": "RETAINED", "sha256": hasher.hexdigest(),
                "bytes": meta.st_size, "filename": path.name}
    finally:
        os.close(fd)


def retain_failed_import(
    *,
    migration_id: str, domain: str, database: str, phase: str,
    source_dump: Path, import_dump: Path, target_dump: Path,
    reason: str
) -> dict[str, Any]:
    """Create a no-overwrite 0600 receipt under the existing private work dir.

    Database mutations may already have happened BEFORE this call.
    This evidence is not an endorsement of the SQL, a restore point, or
    permission to resume, activate, cut over or delete any site.
    """
    if (phase not in ("prepare", "final") or not migration_id.startswith("pull-")
            or not domain or not database
            or reason not in ("CONDITIONAL_DDL", "IMPORT_OR_VERIFICATION_FAILURE")):
        raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_SCOPE_INVALID")
    work = source_dump.parent
    if (import_dump.parent != work or target_dump.parent != work
            or any("/" in p.name for p in (source_dump, import_dump, target_dump))
            or len({p.name for p in (source_dump, import_dump, target_dump)}) != 3):
        raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_PATH_SCOPE_INVALID")
    _secure_work(work)
    evidence = {
        "schema": "P07_PRIVATE_SQL_FAILURE_EVIDENCE_V1",
        "status": "RETAINED_NOT_RECOVERED",
        "migration_id": migration_id,
        "domain": domain,
        "database": database,
        "phase": phase,
        "reason": reason,
        "source_frozen": False,
        "source_target_final_parity": False,
        "target_import_may_have_started": True,
        "database_reimport_authorized": False,
        "source_deletion_authorized": False,
        "cutover_allowed": False,
        "files": {
            "source": _owned_digest(source_dump),
            "import": _owned_digest(import_dump),
            "target": _owned_digest(target_dump),
        },
    }
    if evidence["files"]["source"]["status"] != "RETAINED":
        raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_SOURCE_NOT_RETAINED")
    receipt_name = hashlib.sha256(
        (migration_id + ":" + domain + ":" + database + ":" + phase).encode()
    ).hexdigest()[:20] + "-sql-failure.json"
    receipt = work / receipt_name
    try:
        fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_RECEIPT_ALREADY_EXISTS") from None
    except OSError:
        raise SqlFailureEvidenceBlocked("SQL_EVIDENCE_RECEIPT_CREATE_FAILED") from None
    try:
        payload = (json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # A partially written receipt must never masquerade as valid proof;
        # keep original SQL snapshots for manual recovery.
        try:
            receipt.unlink()
        except OSError:
            pass
        raise
    # Only the fixed safe status is placed in migration state; hashes are
    # exclusively in the protected on-target receipt.
    return {
        "schema": "P07_PRIVATE_SQL_FAILURE_EVIDENCE_V1",
        "status": "RETAINED_NOT_RECOVERED",
        "reason": reason,
        "phase": phase,
        "receipt": receipt_name,
        "source_dump_retained": True,
        "target_dump_retained": evidence["files"]["target"]["status"] == "RETAINED",
        "cutover_allowed": False,
        "db_reimport_allowed": False,
    }
