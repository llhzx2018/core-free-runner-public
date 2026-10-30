"""Strict read-only PRIMARY KEY identity comparison from private SQL exports.

This is a privacy-redacted *SQL literal* comparison. It never queries a live
database, never asserts a transactionally consistent snapshot or semantic
cross-engine equality, never produces repair SQL, and is NOT a migration gate.

Only a simple explicit PRIMARY KEY made of named full columns is accepted.
Unsupported tables stay UNAVAILABLE independently; not even a perfect match
here can relax guarded SQL, schema or restoration verification.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

import sql_diff_evidence as schema
import sql_row_evidence as sql_rows

MAX_ROWS = 3_000_000
MAX_PK_TABLE_ROWS = 300_000
MAX_REPORT_TABLES = 42

_PK = re.compile(r"^PRIMARY\s+KEY\s*\((?P<fields>[^()]*)\)$", re.I | re.S)
_ID = re.compile(sql_rows._NAME, re.I)
_DEF = re.compile(rf"^\s*(?P<field>{sql_rows._NAME})\s+", re.I | re.S)
_SIMPLE_PK_VALUE = re.compile(
    r"(?:[-+]?[0-9]+|0[xX][0-9a-fA-F]+|"
    r"[xX]'[0-9a-fA-F]+'|[bB]'[01]+'|"
    r"(?:_[A-Za-z0-9]+|[nN])?'(?:\\.|''|[^'\\])*')",
    re.I | re.S,
)


class PKUnproven(RuntimeError):
    """Fixed, public-safe code only; do not attach SQL fragments."""


def _pk_schema(statement: str) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    parsed = schema._split_create_table(statement)
    if not parsed:
        return None
    columns, indexes, _options = parsed
    names = []
    for item, count in columns.items():
        if count != 1:
            return None
        match = _DEF.match(item)
        if not match:
            return None
        # Inline PRIMARY KEY is not covered by the explicit PK grammar.
        if re.search(r"\bPRIMARY\s+KEY\b", item, re.I):
            return None
        names.append(sql_rows._name(match.group("field")))
    if not names or len(names) != len(set(names)):
        return None
    keys = [item for item, count in indexes.items()
            if re.match(r"^PRIMARY\s+KEY\b", item, re.I) for _ in range(count)]
    if len(keys) != 1:
        return None
    match = _PK.fullmatch(keys[0])
    if not match:
        return None
    key_names = []
    for item in match.group("fields").split(","):
        field = item.strip()
        if not _ID.fullmatch(field):
            return None
        key_names.append(sql_rows._name(field))
    if not key_names or len(key_names) != len(set(key_names)):
        return None
    if not set(key_names) <= set(names):
        return None
    return tuple(names), tuple(key_names)


def _setup(source_tables: dict[str, str], target_tables: dict[str, str]):
    if not source_tables or set(source_tables) != set(target_tables):
        raise PKUnproven("TABLE_IDENTITY_UNPROVEN")
    eligible = {}
    denied = {}
    for table in sorted(source_tables):
        source = schema._split_create_table(source_tables[table])
        target = schema._split_create_table(target_tables[table])
        if not source or not target or source[0] != target[0] or source[1] != target[1]:
            denied[table] = "SCHEMA_COLUMNS_OR_INDEXES_UNPROVEN"
            continue
        left, right = _pk_schema(source_tables[table]), _pk_schema(target_tables[table])
        if left is None or right is None or left != right:
            denied[table] = "SIMPLE_PRIMARY_KEY_UNPROVEN"
            continue
        eligible[table] = left
    return eligible, denied


def _rows(path: Path, tables: dict[str, tuple[tuple[str, ...], tuple[str, ...]]]):
    result: dict[str, dict[bytes, bytes]] = {name: {} for name in tables}
    total = 0
    for statement in sql_rows._statements(path):
        for name, verb, columns, fields in sql_rows._rows(statement):
            total += 1
            if total > MAX_ROWS:
                raise PKUnproven("TOTAL_ROW_LIMIT")
            if name not in tables:
                # The row grammar was still validated, but this schema was
                # excluded before we could establish primary-key identity.
                continue
            names, key_names = tables[name]
            if not columns:
                ordered = names
            else:
                ordered = columns
            if len(fields) != len(names) or len(ordered) != len(names) or set(ordered) != set(names):
                raise PKUnproven("INCOMPLETE_ROW_COLUMNS_UNPROVEN")
            values = dict(zip(ordered, fields, strict=True))
            pk = tuple(values[key] for key in key_names)
            if any(not _SIMPLE_PK_VALUE.fullmatch(item) for item in pk):
                raise PKUnproven("PRIMARY_KEY_LITERAL_UNPROVEN")
            if any(item.upper() == "NULL" for item in pk):
                raise PKUnproven("NULL_PRIMARY_KEY_UNPROVEN")
            # A normalized column order eliminates innocent INSERT column
            # permutations. Actual SQL literal bytes stay significant.
            payload = json.dumps(
                [verb, [values[c] for c in names]],
                ensure_ascii=False, separators=(",", ":"),
            ).encode("utf-8")
            key_digest = hashlib.sha256(
                json.dumps(pk, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).digest()
            content_digest = hashlib.sha256(payload).digest()
            if key_digest in result[name]:
                raise PKUnproven("DUPLICATE_PRIMARY_KEY_IN_EXPORT")
            if len(result[name]) >= MAX_PK_TABLE_ROWS:
                raise PKUnproven("TABLE_ROW_LIMIT")
            result[name][key_digest] = content_digest
    return result


def diagnostic(source: Path, target: Path) -> dict[str, Any]:
    """Primary-key classification only; safe output has counts and ordinals."""
    try:
        left_schema, _ = schema._schema_statements(source)
        right_schema, _ = schema._schema_statements(target)
        eligible, denied = _setup(left_schema, right_schema)
        left, right = _rows(source, eligible), _rows(target, eligible)
    except (PKUnproven, sql_rows.SQLRowUnproven, schema.AdvisoryDiagnosticUnavailable) as exc:
        return {"comparison": "UNAVAILABLE", "reason": str(exc),
                "verification": "NOT_A_PASS_GATE"}
    except (OSError, UnicodeError, ValueError):
        return {"comparison": "UNAVAILABLE", "reason": "EXPORT_UNREADABLE",
                "verification": "NOT_A_PASS_GATE"}
    changes = []
    totals = {"source_only_keys": 0, "target_only_keys": 0,
              "same_key_changed_literals": 0, "identical_key_identical_literals": 0}
    for ordinal, table in enumerate(sorted(left_schema), 1):
        if table not in eligible:
            continue
        a, b = left[table], right[table]
        common = a.keys() & b.keys()
        source_only = len(a.keys() - b.keys())
        target_only = len(b.keys() - a.keys())
        changed = sum(a[key] != b[key] for key in common)
        equal = len(common) - changed
        totals["source_only_keys"] += source_only
        totals["target_only_keys"] += target_only
        totals["same_key_changed_literals"] += changed
        totals["identical_key_identical_literals"] += equal
        if source_only or target_only or changed:
            changes.append({
                "table_ordinal": ordinal,
                "source_only_keys": source_only,
                "target_only_keys": target_only,
                "same_key_changed_literals": changed,
                "identical_key_identical_literals": equal,
            })
    denied_counts = {
        reason: sum(r == reason for r in denied.values())
        for reason in ("SCHEMA_COLUMNS_OR_INDEXES_UNPROVEN", "SIMPLE_PRIMARY_KEY_UNPROVEN")
    }
    denied_ordinals = [
        {"table_ordinal": i, "reason": denied[table]}
        for i, table in enumerate(sorted(left_schema), 1) if table in denied
    ]
    return {
        "comparison": (
            "PK_LITERAL_DIFFER" if changes
            else "PK_LITERAL_EQUAL_NOT_VERIFIED" if eligible
            else "UNAVAILABLE"
        ),
        "tables_examined": len(left_schema),
        "pk_tables_evaluable": len(eligible),
        "pk_tables_unavailable": len(denied),
        "pk_unavailable_reasons": denied_counts,
        "pk_unavailable_table_ordinals": denied_ordinals[:MAX_REPORT_TABLES],
        "differing_pk_tables": len(changes),
        "differing_table_ordinals": changes[:MAX_REPORT_TABLES],
        **totals,
        "semantics": "DUMP_SQL_LITERAL_PK_ONLY",
        "verification": "NOT_A_PASS_GATE",
    }
