"""Private, in-memory, no-SQL migration reconciliation rehearsal.

This is the isolated transformation kernel for verified and restored snapshots,
NOT a MySQL reader, restore engine, migration gate, executor, or production tool.
Inputs stay local to the caller. Neither raw PKs nor business values are output.

An exact typed-byte match is NOT proof of cross-engine semantic equality. Any
mismatch requires an explicit per-PK decision. All source-only and target-only
rows are preserved in the rehearsal; originals of conflicting rows are held
in a private in-memory journal and rollback to target is checked by value.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Mapping

_SCHEMA = "P07_PRIVATE_RECOVERY_REHEARSAL_V1"
_MAX_ROWS = 50_000
_MAX_FIELDS = 256
_MAX_CELL_CHARS = 1_000_000
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_INT = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
_HEX = re.compile(r"^(?:[0-9a-fA-F]{2})*$")
_TYPE_NAMES = frozenset((
    "INT", "DECIMAL", "TEXT", "BINARY", "DATE", "DATETIME", "TIMESTAMP", "NULL"
))
_ALLOWED_DECISIONS = frozenset(("USE_SOURCE", "USE_TARGET", "MERGE_REVIEWED"))
_EXPECTED_KEYS = frozenset(("identical", "source_only", "target_only", "different"))

class RehearsalBlocked(ValueError):
    """Never expose raw input, SQL, primary keys or hostnames in errors."""


def _cell(value: Any) -> tuple[str, str | None]:
    if type(value) is not dict or set(value) != {"type", "value"}:
        raise RehearsalBlocked("CELL_TYPE_UNPROVEN")
    kind, raw = value["type"], value["value"]
    if type(kind) is not str or kind not in _TYPE_NAMES:
        raise RehearsalBlocked("CELL_TYPE_UNPROVEN")
    if kind == "NULL":
        if raw is not None:
            raise RehearsalBlocked("NULL_SEMANTICS_UNPROVEN")
        return ("NULL", None)
    if type(raw) is not str or len(raw) > _MAX_CELL_CHARS:
        raise RehearsalBlocked("CELL_VALUE_UNPROVEN")
    if kind == "INT" and not _INT.fullmatch(raw):
        raise RehearsalBlocked("INTEGER_FORMAT_UNPROVEN")
    if kind == "DECIMAL" and not _DECIMAL.fullmatch(raw):
        raise RehearsalBlocked("DECIMAL_FORMAT_UNPROVEN")
    if kind == "BINARY" and not _HEX.fullmatch(raw):
        raise RehearsalBlocked("BINARY_FORMAT_UNPROVEN")
    # Date/time, collation, number-string and precision semantics are NEVER
    # normalized across engines here: differences stay explicit conflicts.
    return (kind, raw)


def _identity(row: Any) -> tuple[tuple[str, str | None], ...]:
    if type(row) is not dict or set(row) != {"pk", "cells"}:
        raise RehearsalBlocked("ROW_STRUCTURE_UNPROVEN")
    parts = row["pk"]
    if type(parts) is not list or not 1 <= len(parts) <= 8:
        raise RehearsalBlocked("PK_SHAPE_UNPROVEN")
    key = tuple(_cell(v) for v in parts)
    if any(kind == "NULL" for kind, _ in key):
        raise RehearsalBlocked("NULL_PRIMARY_KEY_UNPROVEN")
    return key


def _row(row: Any) -> tuple[tuple[tuple[str, str | None], ...], dict[str, tuple[str, str | None]]]:
    pk = _identity(row)
    cells = row["cells"]
    if type(cells) is not dict or not 1 <= len(cells) <= _MAX_FIELDS:
        raise RehearsalBlocked("ROW_COLUMNS_UNPROVEN")
    values = {}
    for name, cell in cells.items():
        if type(name) is not str or not _IDENTIFIER.fullmatch(name):
            raise RehearsalBlocked("COLUMN_IDENTITY_UNPROVEN")
        values[name] = _cell(cell)
    return pk, values


def _snapshot(rows: Any, pk_columns: tuple[str, ...]) -> dict[tuple[tuple[str, str | None], ...], dict[str, tuple[str, str | None]]]:
    if type(rows) is not list or len(rows) > _MAX_ROWS:
        raise RehearsalBlocked("SNAPSHOT_SCOPE_UNPROVEN")
    data = {}
    columns = None
    for row in rows:
        key, values = _row(row)
        if (len(key) != len(pk_columns) or any(name not in values for name in pk_columns)
                or tuple(values[name] for name in pk_columns) != key):
            raise RehearsalBlocked("PK_NOT_BOUND_TO_ROW")
        if key in data:
            raise RehearsalBlocked("DUPLICATE_PRIMARY_KEY")
        if columns is None:
            columns = {field: kind for field, (kind, _) in values.items()}
        if {field: kind for field, (kind, _) in values.items()} != columns:
            raise RehearsalBlocked("COLUMN_TYPES_CHANGED")
        data[key] = values
    return data


def _count_expectation(expected: Any) -> dict[str, int]:
    if type(expected) is not dict or set(expected) != _EXPECTED_KEYS:
        raise RehearsalBlocked("ADVISORY_COUNTS_UNPROVEN")
    for n in expected.values():
        if type(n) is not int or not 0 <= n <= _MAX_ROWS:
            raise RehearsalBlocked("ADVISORY_COUNTS_UNPROVEN")
    return expected


def _result(status: str, reason: str, *, counts: Mapping[str, int] | None = None,
            decisions: int = 0, rolled_back: bool = False) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": status, "reason": reason,
        "counts": dict(counts or {}),
        "recorded_conflict_decisions": decisions,
        "target_rollback_rehearsed_in_memory": rolled_back,
        "actual_source_restore_verified": False,
        "actual_target_restore_verified": False,
        "cross_engine_semantics_verified": False,
        "dynamic_sql_guards_verified": False,
        "snapshot_consistency_verified": False,
        "foreign_key_and_trigger_effects_verified": False,
        "data_writes_allowed": False,
        "migration_resume_allowed": False,
        "cutover_allowed": False,
        "verification": "NOT_A_PASS_GATE",
    }


def rehearse(source_rows: Any, target_rows: Any, expected: Any,
             decisions: Any, pk_columns: Any) -> dict[str, Any]:
    """Try a local target candidate and rollback, never persist any data.

    `decisions` contains exact *private* typed PK objects and a decision for
    every changed same-PK row. MERGE_REVIEWED requires a reviewed merged
    `cells` object of unchanged schema; it never authorizes production writes.
    Missing/inconsistent rows, changed counts or decisions fail closed.
    """
    try:
        expected = _count_expectation(expected)
        if (type(pk_columns) is not list or not 1 <= len(pk_columns) <= 8
                or any(type(name) is not str or not _IDENTIFIER.fullmatch(name)
                       for name in pk_columns) or len(set(pk_columns)) != len(pk_columns)):
            raise RehearsalBlocked("PK_SCHEMA_UNPROVEN")
        bound_columns = tuple(pk_columns)
        source = _snapshot(source_rows, bound_columns)
        target = _snapshot(target_rows, bound_columns)
        if not source or not target:
            raise RehearsalBlocked("EMPTY_SNAPSHOT_UNPROVEN")
        source_cols = {field: kind for field, (kind, _) in next(iter(source.values())).items()}
        target_cols = {field: kind for field, (kind, _) in next(iter(target.values())).items()}
        if source_cols != target_cols:
            raise RehearsalBlocked("CROSS_ENGINE_SCHEMA_UNPROVEN")
        source_keys, target_keys = set(source), set(target)
        shared = source_keys & target_keys
        changed = {k for k in shared if source[k] != target[k]}
        counts = {
            "identical": len(shared) - len(changed),
            "source_only": len(source_keys - target_keys),
            "target_only": len(target_keys - source_keys),
            "different": len(changed),
        }
        if counts != expected:
            return _result("BLOCKED", "OBSERVED_COUNTS_DRIFT", counts=counts)
        if type(decisions) is not list or len(decisions) != len(changed):
            return _result("BLOCKED", "MISSING_OR_EXTRA_CONFLICT_DECISIONS", counts=counts)
        selected = {}
        for entry in decisions:
            if type(entry) is not dict or set(entry) not in (
                {"pk", "decision"}, {"pk", "decision", "merged_cells"}
            ):
                raise RehearsalBlocked("DECISION_FORMAT_UNPROVEN")
            key = tuple(_cell(v) for v in entry["pk"]) if type(entry["pk"]) is list else ()
            mode = entry["decision"]
            if (key not in changed or key in selected or type(mode) is not str
                    or mode not in _ALLOWED_DECISIONS):
                raise RehearsalBlocked("DECISION_IDENTITY_UNPROVEN")
            if mode == "MERGE_REVIEWED":
                if "merged_cells" not in entry:
                    raise RehearsalBlocked("REVIEWED_MERGE_MISSING")
                _, merged = _row({"pk": entry["pk"], "cells": entry["merged_cells"]})
                if {field: kind for field, (kind, _) in merged.items()} != source_cols:
                    raise RehearsalBlocked("REVIEWED_MERGE_SCHEMA_DRIFT")
                if tuple(merged[name] for name in bound_columns) != key:
                    raise RehearsalBlocked("REVIEWED_MERGE_PK_CHANGED")
            else:
                if "merged_cells" in entry:
                    raise RehearsalBlocked("UNEXPECTED_MERGED_DATA")
                merged = None
            selected[key] = (mode, merged)
        if set(selected) != changed:
            raise RehearsalBlocked("CONFLICT_COVERAGE_UNPROVEN")

        # Rehearsal always works on independent copies. Keep both originals in
        # the local journal until verification; neither is returned or logged.
        target_before = deepcopy(target)
        source_before = deepcopy(source)
        candidate = deepcopy(target)
        inserted = source_keys - target_keys
        # Includes the retained alternate version for each true conflict.
        private_journal = {key: (deepcopy(source[key]), deepcopy(target[key]))
                           for key in changed}
        for key in source_keys - target_keys:
            candidate[key] = deepcopy(source[key])
        for key in changed:
            mode, merged = selected[key]
            if mode == "USE_SOURCE":
                candidate[key] = deepcopy(source[key])
            elif mode == "MERGE_REVIEWED":
                candidate[key] = deepcopy(merged)
        if (not target_keys <= set(candidate)
                or not source_keys <= set(candidate)
                or len(private_journal) != len(changed)
                or source != source_before or target != target_before):
            raise RehearsalBlocked("COPY_PRESERVATION_UNPROVEN")
        # Explicit reverse of this rehearsal: remove only candidate insertions
        # and reinstate the exact original target side of every changed row.
        restored = deepcopy(candidate)
        for key in inserted:
            restored.pop(key)
        for key, (_old_source, old_target) in private_journal.items():
            restored[key] = deepcopy(old_target)
        if restored != target_before:
            raise RehearsalBlocked("IN_MEMORY_ROLLBACK_UNPROVEN")
        if set(candidate) != source_keys | target_keys:
            raise RehearsalBlocked("RECONCILIATION_SET_UNPROVEN")
        return _result(
            "REHEARSAL_ONLY_BLOCKED_FOR_PRODUCTION",
            "INDEPENDENT_REAL_RESTORE_AND_SQL_PROOFS_REQUIRED",
            counts=counts, decisions=len(selected), rolled_back=True,
        )
    except (RehearsalBlocked, KeyError, TypeError, ValueError):
        return _result("BLOCKED", "INVALID_OR_UNVERIFIED_PRIVATE_EVIDENCE")
