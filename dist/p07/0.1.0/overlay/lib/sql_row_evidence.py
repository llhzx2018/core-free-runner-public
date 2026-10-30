"""Bounded dump row-tuple localization. Advisory only; never a parity gate.

This scanner does not query database rows or verify transactional snapshots.
It compares exact scalar literals after *presentation-only* whitespace removal
and is intentionally more restrictive than the database dialects themselves.
Unknown syntax fails closed; no SQL/table names, hashes, row values or paths
are returned to the operator.
"""
from __future__ import annotations

from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import verify

_LIMIT = 128 * 1024 * 1024
_MASK = (1 << 256) - 1
_NAME = r"(?:\x60(?:\x60\x60|[^\x60])+\x60|[A-Za-z_][A-Za-z_0-9$.-]*)"
_HEAD = re.compile(
    rf"^(?P<verb>INSERT|REPLACE)\s+INTO\s+(?P<table>{_NAME})"
    rf"\s*(?P<cols>\(\s*{_NAME}(?:\s*,\s*{_NAME})*\s*\))?"
    r"(?(cols)\s*|\s+)VALUES\s*", re.I | re.S,
)
_COLUMN = re.compile(_NAME)
_SCALAR = re.compile(
    r"(?:NULL|TRUE|FALSE|"
    r"[-+]?(?:(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?)|"
    r"0[xX][0-9a-fA-F]+|"
    r"[xX]'[0-9a-fA-F]+'|[bB]'[01]+'|"
    r"(?:_[A-Za-z0-9]+|[nN])?'(?:\\.|''|[^'\\])*')", re.S | re.I,
)
_DML_HEAD = re.compile(r"^(?:INSERT|REPLACE|UPDATE|DELETE|LOAD|COPY|TRUNCATE|CALL)\b", re.I)


class SQLRowUnproven(RuntimeError):
    """The entire exception is a whitelisted, non-sensitive reason code."""


def _name(raw: str) -> str:
    if raw.startswith("\x60"):
        return raw[1:-1].replace("\x60\x60", "\x60")
    return raw


def _statements(path: Path):
    opener = gzip.open if path.name.endswith(".gz") else open
    pending: list[str] = []
    size = 0
    quote = ""
    escaped = False
    try:
        with opener(path, "rt", encoding="utf-8", errors="strict") as handle:
            for raw in handle:
                line = raw.strip()
                if not pending:
                    if not line or line.startswith(("--", "#", "/*!", "/*M!")):
                        continue
                    if not _DML_HEAD.match(line):
                        continue
                    if not re.match(r"^(?:INSERT|REPLACE)\s+INTO\b", line, re.I):
                        raise SQLRowUnproven("UNKNOWN_DML_COMMAND")
                pending.append(line)
                size += len(line) + 1
                if size > _LIMIT:
                    raise SQLRowUnproven("STATEMENT_TOO_LARGE")
                try:
                    complete, quote, escaped = verify._sql_data_statement_terminator(
                        line, quote, escaped
                    )
                except verify.RestoreVerifyError as exc:
                    message = str(exc)
                    reason = ("MULTI_OR_TRAILING_SQL" if message.startswith("SQL data contains multiple")
                              else "INLINE_COMMENT_UNPROVEN")
                    raise SQLRowUnproven(reason) from exc
                if quote or escaped:
                    # Physical newline within quoted data can be meaningful.
                    if not complete:
                        raise SQLRowUnproven("MULTILINE_LITERAL_UNPROVEN")
                if complete:
                    yield "\n".join(pending)
                    pending.clear()
                    size = 0
                    quote = ""
                    escaped = False
    except (OSError, EOFError, UnicodeError) as exc:
        raise SQLRowUnproven("DUMP_UNREADABLE") from exc
    if pending:
        raise SQLRowUnproven("UNTERMINATED_DML")


def _columns(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    inside = raw[1:-1].strip()
    names = []
    for item in inside.split(","):
        match = _COLUMN.fullmatch(item.strip())
        if not match:
            raise SQLRowUnproven("COLUMN_GRAMMAR_UNPROVEN")
        names.append(_name(match.group(0)))
    if len(names) != len(set(names)):
        raise SQLRowUnproven("DUPLICATE_COLUMNS_UNPROVEN")
    return tuple(names)


def _rows(statement: str):
    try:
        value = verify._cross_engine_space(statement)
    except verify.RestoreVerifyError as exc:
        raise SQLRowUnproven("SQL_LITERAL_UNPROVEN") from exc
    match = _HEAD.match(value)
    if not match:
        raise SQLRowUnproven("INSERT_GRAMMAR_UNPROVEN")
    table = _name(match.group("table"))
    columns = _columns(match.group("cols"))
    verb = match.group("verb").upper()
    pos = match.end()
    rows = 0
    while pos < len(value):
        if value[pos] != "(":
            raise SQLRowUnproven("ROW_GRAMMAR_UNPROVEN")
        pos += 1
        fields = []
        token = []
        quote = ""
        escaped = False
        while pos < len(value):
            c = value[pos]
            if quote:
                token.append(c)
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == quote:
                    if pos + 1 < len(value) and value[pos + 1] == quote:
                        pos += 1
                        token.append(value[pos])
                    else:
                        quote = ""
            elif c == "'":
                quote = c
                token.append(c)
            elif c == "," or c == ")":
                literal = "".join(token).strip()
                if not _SCALAR.fullmatch(literal):
                    raise SQLRowUnproven("SCALAR_GRAMMAR_UNPROVEN")
                fields.append(literal)
                token = []
                if c == ")":
                    pos += 1
                    break
            else:
                if c in ('"', "\x60", "(", ";", "#") or value.startswith(("/*", "--"), pos):
                    raise SQLRowUnproven("EXPRESSION_OR_COMMENT_UNPROVEN")
                token.append(c)
            pos += 1
        else:
            raise SQLRowUnproven("UNTERMINATED_ROW")
        if quote or escaped:
            raise SQLRowUnproven("SQL_LITERAL_UNPROVEN")
        if columns and len(fields) != len(columns):
            raise SQLRowUnproven("COLUMN_VALUE_COUNT_UNPROVEN")
        if not fields:
            raise SQLRowUnproven("EMPTY_ROW_UNPROVEN")
        rows += 1
        yield table, verb, columns, tuple(fields)
        if pos == len(value) - 1 and value[pos] == ";":
            break
        if pos >= len(value) or value[pos] != ",":
            raise SQLRowUnproven("TRAILING_SQL_UNPROVEN")
        pos += 1
    if not rows or pos != len(value) - 1 or value[pos] != ";":
        raise SQLRowUnproven("INSERT_TERMINATOR_UNPROVEN")


def _profile(path: Path, schema_tables: set[str]) -> dict[str, tuple[int, int, int]]:
    result = {table: [0, 0, 0] for table in schema_tables}
    for statement in _statements(path):
        for table, verb, columns, fields in _rows(statement):
            if table not in result:
                raise SQLRowUnproven("ROW_REFERENCES_UNKNOWN_TABLE")
            # Each scalar is syntax checked, and every literal byte remains
            # covered. A row's original INSERT grouping and position do not.
            literal = json.dumps(
                [verb, list(columns), list(fields)],
                ensure_ascii=False, separators=(",", ":"),
            )
            n = int.from_bytes(hashlib.sha256(literal.encode("utf-8")).digest(), "big")
            agg = result[table]
            agg[0] += 1
            agg[1] = (agg[1] + n) & _MASK
            agg[2] ^= n
    return {key: tuple(value) for key, value in result.items()}


def diagnostic(source: Path, target: Path, source_tables: set[str],
               target_tables: set[str]) -> dict[str, Any]:
    """Advisory mismatch localization, bounded output with no identifiers."""
    if not source_tables or source_tables != target_tables:
        return {"comparison": "UNAVAILABLE", "reason": "TABLE_IDENTITY_UNPROVEN"}
    try:
        left = _profile(source, source_tables)
        right = _profile(target, target_tables)
    except SQLRowUnproven as exc:
        return {"comparison": "UNAVAILABLE", "reason": str(exc)}
    changed = []
    row_count_drift = 0
    same_count_content_drift = 0
    for i, table in enumerate(sorted(source_tables), 1):
        before, after = left[table], right[table]
        if before == after:
            continue
        if before[0] != after[0]:
            row_count_drift += 1
        else:
            same_count_content_drift += 1
        changed.append({
            "table_ordinal": i,
            "source_rows": before[0],
            "target_rows": after[0],
            "difference_class": ("ROW_COUNT_DIFFER" if before[0] != after[0]
                                 else "ROW_CONTENT_DIFFER"),
        })
    source_rows = sum(stat[0] for stat in left.values())
    target_rows = sum(stat[0] for stat in right.values())
    status = ("ROW_TUPLES_DIFFER" if changed
              else "NO_INSERT_ROWS" if source_rows == 0
              else "ROW_TUPLES_EQUAL_NOT_VERIFIED")
    return {
        "comparison": status,
        "tables_examined": len(source_tables),
        "tables_with_rows": sum(1 for x in left.values() if x[0]),
        "source_row_tuples": source_rows,
        "target_row_tuples": target_rows,
        "row_count_drift_tables": row_count_drift,
        "same_count_content_drift_tables": same_count_content_drift,
        "differing_tables": len(changed),
        "differing_table_ordinals": changed[:42],
        "verification": "NOT_A_PASS_GATE",
    }
