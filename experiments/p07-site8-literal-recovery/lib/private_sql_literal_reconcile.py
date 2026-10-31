"""Private, read-only SQL literal extraction for a single conflicting PK table.

This tool DOES NOT restore original SQL, execute its dynamic commands, prove
cross-engine row semantics, reconcile live writes or allow migration. Literal
spellings (including SQL quoting/escaping) are kept, not decoded to DB values.
Never send resulting private artifacts, backup paths or SQL to public CI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import private_recovery_gate as gate
import private_conflict_preservation as preserve
import sql_pk_conflict_evidence as pk
import sql_row_evidence as rows
import sql_diff_evidence as schema

SCHEMA = "P07_PRIVATE_SQL_LITERAL_SNAPSHOT_V1"
MAX_ROWS = 300_000


class LiteralBlocked(ValueError):
    """Only constant error codes may cross the command boundary."""


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while part := stream.read(1024 * 1024):
                h.update(part)
    except OSError:
        raise LiteralBlocked("PRIVATE_SQL_READ_UNAVAILABLE") from None
    return h.hexdigest()


def _read_table(sql_path: Path, table: str, names: tuple[str, ...],
                keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Strict SQL scalar spellings, no interpolation, execution or normalization."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for statement in rows._statements(sql_path):
        for name, verb, columns, fields in rows._rows(statement):
            if name != table:
                continue
            if verb != "INSERT":
                raise LiteralBlocked("LITERAL_NONINSERT_DML_REFUSED")
            ordered = tuple(columns or names)
            if (len(ordered) != len(names) or set(ordered) != set(names)
                    or len(fields) != len(names)
                    or any(not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,127}", n)
                           for n in names)):
                raise LiteralBlocked("LITERAL_COLUMN_SCHEMA_UNPROVEN")
            mapping = dict(zip(ordered, fields))
            raw_pk = tuple(mapping[key] for key in keys)
            if (any(not pk._SIMPLE_PK_VALUE.fullmatch(x) or x.upper() == "NULL"
                    for x in raw_pk)
                    or raw_pk in seen):
                raise LiteralBlocked("LITERAL_PRIMARY_KEY_UNPROVEN")
            seen.add(raw_pk)
            if len(out) >= MAX_ROWS:
                raise LiteralBlocked("LITERAL_ROW_LIMIT")
            # Every raw SQL scalar (including NULL/hex/numeric) is treated as
            # opaque SQL text. No claim of SQL-typed or actual DB equality.
            out.append({
                "pk": [{"type": "TEXT", "value": x} for x in raw_pk],
                "cells": {k: {"type": "TEXT", "value": mapping[k]} for k in names},
            })
    return out


def extract_verified(source_package: Path, target_package: Path,
                     site: str, table_ordinal: int) -> tuple[dict, list, list, dict, list, dict]:
    """Read-only: validate both backups and full PK evidence before parsing."""
    if (type(site) is not str or not site or "/" in site or "\\" in site
            or type(table_ordinal) is not int or not 1 <= table_ordinal <= 200):
        raise LiteralBlocked("LITERAL_INPUT_INVALID")
    try:
        if source_package.resolve(strict=True) == target_package.resolve(strict=True):
            raise LiteralBlocked("LITERAL_DISTINCT_PACKAGES_REQUIRED")
        src, a = gate._input_package(source_package, site)
        tgt, b = gate._input_package(target_package, site)
        if src["backup_id"] == tgt["backup_id"]:
            raise LiteralBlocked("LITERAL_DISTINCT_BACKUP_IDENTITIES_REQUIRED")
        before = (_digest(a), _digest(b))
        left, _ = schema._schema_statements(a)
        right, _ = schema._schema_statements(b)
        if not left or set(left) != set(right):
            raise LiteralBlocked("LITERAL_TABLE_IDENTITY_UNPROVEN")
        names = sorted(left)
        if table_ordinal > len(names):
            raise LiteralBlocked("LITERAL_TABLE_ORDINAL_UNPROVEN")
        table = names[table_ordinal - 1]
        eligible, denied = pk._setup(left, right)
        if table in denied or table not in eligible:
            raise LiteralBlocked("LITERAL_PK_SCHEMA_UNPROVEN")
        colnames, keynames = eligible[table]
        diagnostic = pk.diagnostic(a, b)
        entries = diagnostic.get("differing_table_ordinals")
        if (diagnostic.get("comparison") != "PK_LITERAL_DIFFER"
                or diagnostic.get("tables_examined") != len(names)
                or diagnostic.get("pk_tables_evaluable") != len(names)
                or not isinstance(entries, list)):
            raise LiteralBlocked("LITERAL_GLOBAL_PK_EVIDENCE_UNPROVEN")
        match = [item for item in entries if item.get("table_ordinal") == table_ordinal]
        if len(match) != 1:
            raise LiteralBlocked("LITERAL_CONFLICT_TABLE_UNPROVEN")
        item = match[0]
        expected = {
            "identical": item["identical_key_identical_literals"],
            "source_only": item["source_only_keys"],
            "target_only": item["target_only_keys"],
            "different": item["same_key_changed_literals"],
        }
        if any(type(v) is not int or v < 0 for v in expected.values()):
            raise LiteralBlocked("LITERAL_COUNTS_UNPROVEN")
        source_rows = _read_table(a, table, colnames, keynames)
        target_rows = _read_table(b, table, colnames, keynames)
        if (_digest(a), _digest(b)) != before:
            raise LiteralBlocked("LITERAL_BACKUP_SQL_CHANGED_DURING_READ")
        # PK diagnostic also includes INSERT/REPLACE verbs and literal equality.
        # The opaque row representation refuses REPLACE and may differ from
        # SQL-evaluated equality; any count drift blocks rather than rewrites.
        provenance = {
            "source_sql_sha256": before[0],
            "target_sql_sha256": before[1],
            "source_backup_id_sha256": hashlib.sha256(src["backup_id"].encode()).hexdigest(),
            "target_backup_id_sha256": hashlib.sha256(tgt["backup_id"].encode()).hexdigest(),
        }
        bundle = preserve.compile_bundle(source_rows, target_rows, expected,
                                          list(keynames), provenance)
        return bundle, source_rows, target_rows, expected, list(keynames), provenance
    except LiteralBlocked:
        raise
    except (gate.RecoveryBlocked, pk.PKUnproven, rows.SQLRowUnproven,
            schema.AdvisoryDiagnosticUnavailable, preserve.PreservationBlocked,
            OSError, UnicodeError, TypeError, KeyError, ValueError, AttributeError):
        raise LiteralBlocked("LITERAL_PRIVATE_EVIDENCE_NOT_PROVEN") from None


def evaluate(source_package: Path, target_package: Path, site: str,
             table_ordinal: int, *, private_output: Path | None = None,
             confirm: str | None = None) -> dict[str, Any]:
    """Only opt-in writes a new local private artifact; no live DB/SSH calls."""
    report = {
        "schema": SCHEMA, "status": "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE",
        "reason": "LITERAL_EVIDENCE_NOT_VERIFIED",
        "original_sql_restored": False,
        "snapshot_point_in_time_verified": False,
        "live_row_semantics_verified": False,
        "original_dynamic_sql_verified": False,
        "data_writes_allowed": False,
        "migration_resume_allowed": False,
        "cutover_allowed": False,
        "verification": "NOT_A_PASS_GATE",
    }
    if private_output is not None and confirm != "PRESERVE_PRIVATE_SQL_LITERALS_ONLY":
        return {**report, "reason": "EXPLICIT_PRIVATE_ARTIFACT_CONFIRMATION_REQUIRED"}
    try:
        bundle, source_rows, target_rows, expected, keys, origin = extract_verified(
            source_package, target_package, site, table_ordinal)
        if private_output is not None:
            written = preserve.save_private(
                bundle, private_output, source_rows=source_rows,
                target_rows=target_rows, expected=expected, pk_columns=keys,
                provenance=origin)
            verified = preserve.verify_private(private_output)
            if not verified["artifact_bytes_verified"]:
                raise LiteralBlocked("PRIVATE_ARTIFACT_READBACK_UNPROVEN")
        else:
            written = None
        return {
            **report,
            "status": "PRIVATE_SQL_LITERALS_CAPTURED_NOT_RESTORED",
            "reason": "PRIVATE_BACKUP_SCALAR_LITERALS_ONLY",
            "counts": dict(expected),
            "unresolved_conflicts": bundle["unresolved_conflict_count"],
            "private_artifact": ("LOCAL_BYTES_VERIFIED_NOT_ENCRYPTED"
                                 if written else "NOT_WRITTEN"),
            "original_sql_restored": False,
        }
    except (LiteralBlocked, preserve.PreservationBlocked) as exc:
        # Never leak SQL, host paths, PK contents, website, backup IDs or hashes.
        return {**report, "reason": str(exc) if str(exc).startswith(("LITERAL_", "PRESERVATION_",
                                                                     "PRIVATE_ARTIFACT_")) else
                "LITERAL_CAPTURE_FAILED"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Private read-only SQL literal evidence; NOT a restore")
    p.add_argument("--source-package", required=True, type=Path)
    p.add_argument("--target-package", required=True, type=Path)
    p.add_argument("--site", required=True)
    p.add_argument("--table-ordinal", type=int, required=True)
    p.add_argument("--private-output", type=Path)
    p.add_argument("--confirm")
    args = p.parse_args(argv)
    value = evaluate(args.source_package, args.target_package, args.site,
                     args.table_ordinal, private_output=args.private_output,
                     confirm=args.confirm)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0 if value["status"] == "PRIVATE_SQL_LITERALS_CAPTURED_NOT_RESTORED" else 13


if __name__ == "__main__":
    raise SystemExit(main())
