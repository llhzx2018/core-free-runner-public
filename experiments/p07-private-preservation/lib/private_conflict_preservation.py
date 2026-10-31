"""Strict private, non-executable preservation of BOTH copies of divergent PK rows.

Input: typed rows from *separately reviewed* snapshots, not SQL dump parser
output and NOT source/target restore proof. Do not upload artifacts or use as
migration decisions. Original backup packages and databases are never touched.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any

import migration_recovery_rehearsal as typed

SCHEMA = "P07_PRIVATE_DUAL_ORIGINAL_PRESERVATION_V1"
MAX_BYTES = 64 * 1024 * 1024


class PreservationBlocked(ValueError):
    """Fixed reason codes only: never include private rows, PKs, paths or SQL."""


def _encoded(obj: Any) -> bytes:
    try:
        data = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError):
        raise PreservationBlocked("PRESERVATION_SERIALIZATION_REFUSED") from None
    if len(data) > MAX_BYTES:
        raise PreservationBlocked("PRESERVATION_BUNDLE_SIZE_LIMIT")
    return data


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_row(key: tuple, cells: dict) -> dict:
    return {
        "pk": [{"type": kind, "value": value} for kind, value in key],
        "cells": {field: {"type": kind, "value": value}
                  for field, (kind, value) in sorted(cells.items())},
    }


def _ordered_rows(snapshot: dict) -> list[dict]:
    # Sort on complete *typed* PKs, preserving literal differences, not
    # database collation or date/decimal interpretation.
    return [_canonical_row(key, snapshot[key])
            for key in sorted(snapshot, key=lambda k: _encoded(k))]


def compile_bundle(source_rows: Any, target_rows: Any, expected: Any,
                   pk_columns: Any) -> dict:
    """Retain every unique row and BOTH originals of every conflicting PK.

    No auto-winner, no SQL writer, no filesystem modification, no PASS gate.
    The 1,004 or other identical records stay in original full backups;
    private digests bind the supplied complete typed snapshots.
    """
    try:
        counts = typed._count_expectation(expected)
        if (type(pk_columns) is not list or not 1 <= len(pk_columns) <= 8
                or len(set(pk_columns)) != len(pk_columns)
                or any(type(x) is not str or not typed._IDENTIFIER.fullmatch(x)
                       for x in pk_columns)):
            raise PreservationBlocked("PRESERVATION_PK_COLUMNS_UNPROVEN")
        src = typed._snapshot(source_rows, tuple(pk_columns))
        tgt = typed._snapshot(target_rows, tuple(pk_columns))
        if not src or not tgt:
            raise PreservationBlocked("PRESERVATION_EMPTY_SNAPSHOT")
        src_types = {k: v[0] for k, v in next(iter(src.values())).items()}
        tgt_types = {k: v[0] for k, v in next(iter(tgt.values())).items()}
        if src_types != tgt_types:
            raise PreservationBlocked("PRESERVATION_SCHEMA_DRIFT")
        source_keys, target_keys = set(src), set(tgt)
        shared = source_keys & target_keys
        changed = {key for key in shared if src[key] != tgt[key]}
        observed = {
            "identical": len(shared) - len(changed),
            "source_only": len(source_keys - target_keys),
            "target_only": len(target_keys - source_keys),
            "different": len(changed),
        }
        if observed != counts:
            raise PreservationBlocked("PRESERVATION_COUNTS_DRIFT")
        src_only = _ordered_rows({key: src[key] for key in source_keys - target_keys})
        tgt_only = _ordered_rows({key: tgt[key] for key in target_keys - source_keys})
        conflicts = [
            {"pk": _canonical_row(key, src[key])["pk"],
             "source_original": _canonical_row(key, src[key]),
             "target_original": _canonical_row(key, tgt[key]),
             "resolution": "UNRESOLVED_KEEP_BOTH"}
            for key in sorted(changed, key=lambda k: _encoded(k))
        ]
        if (len(src_only) != counts["source_only"]
                or len(tgt_only) != counts["target_only"]
                or len(conflicts) != counts["different"]):
            raise PreservationBlocked("PRESERVATION_SET_COVERAGE_DRIFT")
        return {
            "schema": SCHEMA,
            "status": "PRIVATE_DUAL_ORIGINALS_UNRESOLVED",
            "pk_columns": list(pk_columns),
            "counts": dict(counts),
            "source_complete_typed_snapshot_sha256": _sha(_encoded(_ordered_rows(src))),
            "target_complete_typed_snapshot_sha256": _sha(_encoded(_ordered_rows(tgt))),
            "source_only_originals": src_only,
            "target_only_originals": tgt_only,
            "conflicting_dual_originals": conflicts,
            "unresolved_conflict_count": len(conflicts),
            "storage_format": "PRIVATE_PLAINTEXT_LOCAL_ONLY_NOT_ENCRYPTED",
            "actual_original_sql_restores_verified": False,
            "snapshot_time_consistency_verified": False,
            "operator_conflict_policy_verified": False,
            "data_writes_allowed": False,
            "migration_resume_allowed": False,
            "cutover_allowed": False,
            "verification": "NOT_A_PASS_GATE",
        }
    except PreservationBlocked:
        raise
    except (typed.RehearsalBlocked, TypeError, KeyError, ValueError, OverflowError):
        raise PreservationBlocked("PRESERVATION_TYPED_INPUT_UNPROVEN") from None


def compare_to_inputs(bundle: Any, source_rows: Any, target_rows: Any,
                      expected: Any, pk_columns: Any) -> bool:
    """Recompute every unique/changed original against separate input copies."""
    try:
        return type(bundle) is dict and _encoded(bundle) == _encoded(
            compile_bundle(source_rows, target_rows, expected, pk_columns))
    except PreservationBlocked:
        return False


def _private_parent(path: Path) -> None:
    """Only an existing operator-owned 0700 parent, never symlinks."""
    try:
        parent = path.parent
        value = parent.lstat()
        if (not stat.S_ISDIR(value.st_mode) or value.st_uid != os.geteuid()
                or stat.S_IMODE(value.st_mode) != 0o700
                or parent.resolve(strict=True) != parent.absolute()\n                or path.is_symlink() or path.exists()):
            raise PreservationBlocked("PRESERVATION_PRIVATE_DESTINATION_REQUIRED")
    except PreservationBlocked:
        raise
    except OSError:
        raise PreservationBlocked("PRESERVATION_PRIVATE_DESTINATION_REQUIRED") from None


def _write_exclusive(path: Path, value: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())


def save_private(bundle: dict, directory: Path, *, source_rows: Any,\n                 target_rows: Any, expected: Any, pk_columns: Any) -> dict:
    """Create only one new 0700 directory and private 0600 files, never replace.

    Not encrypted. Callers must use an operator-controlled local filesystem,
    never public CI, shared storage, SSH transport, or a production DB path.
    Any failure rolls back only the newly created files and directory.
    """
    if (type(bundle) is not dict or bundle.get("schema") != SCHEMA
            or bundle.get("status") != "PRIVATE_DUAL_ORIGINALS_UNRESOLVED"
            or bundle.get("verification") != "NOT_A_PASS_GATE"
            or bundle.get("data_writes_allowed") is not False):
        raise PreservationBlocked("PRESERVATION_BUNDLE_UNPROVEN")
    if not compare_to_inputs(bundle, source_rows, target_rows, expected, pk_columns):
        raise PreservationBlocked("PRESERVATION_INPUT_BINDING_UNPROVEN")
    payload = _encoded(bundle)
    _private_parent(directory)
    made = False
    try:
        os.mkdir(directory, 0o700)
        made = True
        if stat.S_IMODE(directory.stat().st_mode) != 0o700:
            raise PreservationBlocked("PRESERVATION_PRIVATE_DIRECTORY_UNPROVEN")
        _write_exclusive(directory / "originals.json", payload)
        _write_exclusive(directory / "integrity.json", _encoded({
            "schema": SCHEMA,
            "file": "originals.json",
            "sha256": _sha(payload),
            "bytes": len(payload),
            "verification": "ARTIFACT_INTEGRITY_ONLY_NOT_SOURCE_RESTORE",
        }))
        return {"status": "PRIVATE_PLAINTEXT_ARTIFACT_WRITTEN",
                "conflict_count": bundle.get("unresolved_conflict_count"),
                "artifact_integrity": "SHA256_WRITTEN_NOT_AUTHENTICATED",
                "at_rest_encryption": False,
                "migration_resume_allowed": False,
                "cutover_allowed": False,
                "verification": "NOT_A_PASS_GATE"}
    except (OSError, PreservationBlocked):
        if made:
            for name in ("originals.json", "integrity.json"):
                try:
                    (directory / name).unlink(missing_ok=True)
                except OSError:
                    pass
            try:
                directory.rmdir()
            except OSError:
                pass
        raise PreservationBlocked("PRESERVATION_LOCAL_WRITE_FAILED") from None


def verify_private(directory: Path) -> dict:
    """Local readback checks bytes, ownership, permissions and digest only.

    A hash alongside its own data is NOT authentication or source provenance.
    Neither result authorizes database import, conflict decisions, or cutover.
    """
    result = {"status": "BLOCKED_PRIVATE_ARTIFACT_UNVERIFIED",
              "artifact_bytes_verified": False,
              "original_sql_restore_verified": False,
              "at_rest_encryption": False,
              "migration_resume_allowed": False,
              "cutover_allowed": False,
              "verification": "NOT_A_PASS_GATE"}
    try:
        root_stat = directory.lstat()
        if (not stat.S_ISDIR(root_stat.st_mode)
                or root_stat.st_uid != os.geteuid()
                or stat.S_IMODE(root_stat.st_mode) != 0o700):
            return result
        values = []
        for file in ("originals.json", "integrity.json"):
            p = directory / file
            st = p.lstat()
            if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                    or st.st_uid != os.geteuid()
                    or stat.S_IMODE(st.st_mode) != 0o600
                    or st.st_size > MAX_BYTES):
                return result
            values.append(p.read_bytes())
        payload, digest_bytes = values
        meta = json.loads(digest_bytes)
        bundle = json.loads(payload)
        if (meta.get("schema") != SCHEMA or meta.get("file") != "originals.json"
                or meta.get("bytes") != len(payload)
                or meta.get("sha256") != _sha(payload)
                or bundle.get("schema") != SCHEMA
                or bundle.get("status") != "PRIVATE_DUAL_ORIGINALS_UNRESOLVED"
                or bundle.get("verification") != "NOT_A_PASS_GATE"
                or bundle.get("data_writes_allowed") is not False
                or bundle.get("migration_resume_allowed") is not False
                or bundle.get("cutover_allowed") is not False):
            return result
        return {**result, "status": "PRIVATE_ARTIFACT_BYTES_VERIFIED_NOT_RESTORE",
                "artifact_bytes_verified": True}
    except (OSError, TypeError, ValueError, AttributeError, UnicodeError):
        return result
