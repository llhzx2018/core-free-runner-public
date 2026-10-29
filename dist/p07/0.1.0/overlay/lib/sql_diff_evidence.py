"""Privacy-safe, advisory-only cross-engine dump diff diagnostics.

No result from this module is a migration acceptance or SQL equivalence gate.
Only fixed labels and integer counters leave the module; names and SQL remain local.
"""
from __future__ import annotations

from collections import Counter
import gzip
from pathlib import Path
import re
from typing import Any

import verify

_GUARD_RE = re.compile(r"/\*!([0-9]{5,6})\s+(.+?)\s*\*/;?", re.I)
_DOUBLE_IF_RE = re.compile(
    r'^SET\s+@[A-Za-z_][A-Za-z_0-9$]*\s*=\s*IF\s*\(\s*'
    r'@[A-Za-z_][A-Za-z_0-9$]*\s*,\s*'
    r'"(?:\\.|""|[^"])*"\s*,\s*"(?:\\.|""|[^"])*"\s*\)$', re.I,
)
_SCHEMA_START = re.compile(
    r"^(?:CREATE\s+TABLE|DROP\s+TABLE|ALTER\s+TABLE|"
    r"CREATE\s+VIEW|CREATE\s+TRIGGER)\b", re.I,
)
_TABLE_NAME = re.compile(
    r"^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:`((?:[^`]|``)+)`|([A-Za-z0-9_.$-]+))\s*\(", re.I,
)
_INDEX_START = re.compile(
    r"^(?:PRIMARY\s+KEY|UNIQUE\s+(?:KEY|INDEX)|FOREIGN\s+KEY|"
    r"(?:FULLTEXT|SPATIAL)\s+(?:KEY|INDEX)|KEY|INDEX|CONSTRAINT)\b", re.I,
)
_MAX_SCHEMA_STATEMENT = 128 * 1024 * 1024


class AdvisoryDiagnosticUnavailable(RuntimeError):
    """Fixed-reason failure; never incorporates an SQL fragment or a filename."""


def _read_lines(path: Path):
    opener = gzip.open if path.name.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="strict") as handle:
            yield from handle
    except (OSError, EOFError, UnicodeError) as exc:
        raise AdvisoryDiagnosticUnavailable("SQL_DIAGNOSTIC_INPUT_UNAVAILABLE") from exc


_UNSAFE_BRANCH_CLASSES = (
    "DDL_CREATE", "DDL_ALTER", "DDL_DROP", "DDL_OTHER",
    "DATA_MUTATION", "PRIVILEGED_OR_CONTROL",
    "SESSION_UNPROVEN", "READ_UNPROVEN", "UNKNOWN_OR_ESCAPED",
)


def _unsafe_branch_category(literal: str) -> str:
    """Categorize a rejected branch without returning any of its SQL bytes."""
    value = literal[1:-1].replace("''", "'").strip()
    if re.match(r"^CREATE\b", value, re.I):
        return "DDL_CREATE"
    if re.match(r"^ALTER\b", value, re.I):
        return "DDL_ALTER"
    if re.match(r"^DROP\b", value, re.I):
        return "DDL_DROP"
    if re.match(r"^(?:RENAME|TRUNCATE)\b", value, re.I):
        return "DDL_OTHER"
    if re.match(r"^(?:INSERT|UPDATE|DELETE|REPLACE|LOAD|COPY)\b", value, re.I):
        return "DATA_MUTATION"
    if re.match(r"^(?:GRANT|REVOKE|CALL|DO|PREPARE|EXECUTE|SHUTDOWN)\b", value, re.I):
        return "PRIVILEGED_OR_CONTROL"
    if re.match(r"^SET\b", value, re.I):
        return "SESSION_UNPROVEN"
    if re.match(r"^(?:SELECT|SHOW|EXPLAIN)\b", value, re.I):
        return "READ_UNPROVEN"
    return "UNKNOWN_OR_ESCAPED"


def dynamic_guard_syntax_counts(source: Path) -> dict[str, Any]:
    """Classify guarded IF branches; classification never makes them safe."""
    counts: dict[str, Any] = {
        "recognized_safe": 0, "recognized_unsafe": 0,
        "double_quoted_if": 0, "other_unknown_set": 0,
        "unsafe_yes_branches": 0, "unsafe_no_branches": 0,
        "unsafe_control_or_multi": 0,
        "unsafe_branch_classes": {name: 0 for name in _UNSAFE_BRANCH_CLASSES},
    }
    for raw in _read_lines(source):
        match = _GUARD_RE.fullmatch(raw.strip())
        if not match or not 40000 <= int(match.group(1)) <= 89999:
            continue
        body = re.sub(r"\s+", " ", match.group(2).strip())
        known = verify._CROSS_ENGINE_DYNAMIC_IF_RE.fullmatch(body)
        if known:
            rejected = False
            for part in ("yes", "no"):
                literal = known.group(part)
                if verify._cross_engine_safe_dynamic_branch(literal):
                    continue
                rejected = True
                counts[f"unsafe_{part}_branches"] += 1
                counts["unsafe_branch_classes"][_unsafe_branch_category(literal)] += 1
                value = literal[1:-1]
                if len(value) > 4096 or any(
                    char in value for char in ("\\", ";", "/*", "*/", "--", "#", "\r", "\n")
                ):
                    counts["unsafe_control_or_multi"] += 1
            counts["recognized_unsafe" if rejected else "recognized_safe"] += 1
        elif re.match(r"^SET\s+@", body, re.I) and not verify._cross_engine_known_session(raw.strip()):
            category = "double_quoted_if" if _DOUBLE_IF_RE.fullmatch(body) else "other_unknown_set"
            counts[category] += 1
    return counts


def _schema_statements(path: Path) -> tuple[dict[str, str], Counter[str]]:
    tables: dict[str, str] = {}
    other: Counter[str] = Counter()
    pending: list[str] = []
    size = 0
    for raw in _read_lines(path):
        line = raw.strip()
        if not pending:
            if not _SCHEMA_START.match(line):
                continue
        pending.append(line)
        size += len(line)
        if size > _MAX_SCHEMA_STATEMENT:
            raise AdvisoryDiagnosticUnavailable("SQL_SCHEMA_STATEMENT_TOO_LARGE")
        if not line.endswith(";"):
            continue
        statement = verify._cross_engine_space(verify._cross_engine_schema(" ".join(pending)))
        pending.clear()
        size = 0
        table = _TABLE_NAME.match(statement)
        if table:
            name = table.group(1) or table.group(2)
            if name in tables:
                raise AdvisoryDiagnosticUnavailable("SQL_DUPLICATE_CREATE_TABLE")
            tables[name] = statement
        else:
            other[statement] += 1
    if pending:
        raise AdvisoryDiagnosticUnavailable("SQL_SCHEMA_STATEMENT_INCOMPLETE")
    return tables, other


def _split_create_table(statement: str) -> tuple[Counter[str], Counter[str], str] | None:
    head = _TABLE_NAME.match(statement)
    if not head:
        return None
    index = head.end()
    depth = 1
    quote = ""
    start = index
    parts: list[str] = []
    while index < len(statement):
        char = statement[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                if index + 1 < len(statement) and statement[index + 1] == quote:
                    index += 2
                else:
                    quote = ""
        elif char in ("'", '"', "`"):
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                parts.append(statement[start:index].strip())
                suffix = statement[index + 1:].strip()
                columns = Counter(p for p in parts if not _INDEX_START.match(p))
                indexes = Counter(p for p in parts if _INDEX_START.match(p))
                return columns, indexes, suffix
        elif char == "," and depth == 1:
            parts.append(statement[start:index].strip())
            start = index + 1
        index += 1
    return None


def schema_difference_counts(source: Path, target: Path) -> dict[str, int]:
    """Compare normalized CREATE TABLE statements by identity only in memory."""
    left, left_other = _schema_statements(source)
    right, right_other = _schema_statements(target)
    common = left.keys() & right.keys()
    result = {
        "source_tables": len(left), "target_tables": len(right),
        "common_tables": len(common),
        "source_only_tables": len(left.keys() - right.keys()),
        "target_only_tables": len(right.keys() - left.keys()),
        "mismatched_tables": 0, "changed_columns": 0,
        "changed_indexes": 0, "changed_options": 0,
        "unclassified_tables": 0,
        "other_schema_source_only": sum((left_other - right_other).values()),
        "other_schema_target_only": sum((right_other - left_other).values()),
    }
    for name in common:
        if left[name] == right[name]:
            continue
        result["mismatched_tables"] += 1
        a = _split_create_table(left[name])
        b = _split_create_table(right[name])
        if a is None or b is None:
            result["unclassified_tables"] += 1
            continue
        if a[0] != b[0]:
            result["changed_columns"] += 1
        if a[1] != b[1]:
            result["changed_indexes"] += 1
        if a[2] != b[2]:
            result["changed_options"] += 1
        if a == b:
            result["unclassified_tables"] += 1
    return result


def data_content_evidence(source: Path, target: Path) -> dict[str, Any]:
    """Advisory DML/object fingerprint parity; no SQL or digest leaves memory.

    The current verifier ignores guarded SQL and its DML comparison is a
    presentation-sensitive fingerprint. This result is NEVER a migration PASS.
    """
    try:
        left = verify.sql_data_fingerprint(source)
        right = verify.sql_data_fingerprint(target)
    except verify.RestoreVerifyError:
        return {"comparison": "UNAVAILABLE"}
    left_count = left["data_statements"]
    right_count = right["data_statements"]
    if not left_count and not right_count:
        comparison = "NO_DML_STATEMENTS"
    elif (
        left["objects"] == right["objects"]
        and left_count == right_count
        and left["data_hash"] == right["data_hash"]
    ):
        comparison = "FINGERPRINT_EQUAL_NOT_VERIFIED"
    else:
        comparison = "FINGERPRINT_DIFFER"
    return {
        "comparison": comparison,
        "source_objects": len(left["objects"]),
        "target_objects": len(right["objects"]),
        "source_dml_statements": left_count,
        "target_dml_statements": right_count,
    }


def diagnostic(source: Path, target: Path) -> dict[str, Any]:
    """Advisory only. No value ever enables migration or changes a verifier."""
    try:
        return {
            "schema": "SQL_DIFF_EVIDENCE_V2",
            "verification": "NOT_A_PASS_GATE",
            "dynamic_guard": dynamic_guard_syntax_counts(source),
            "schema_difference": schema_difference_counts(source, target),
            "data_content": data_content_evidence(source, target),
        }
    except (AdvisoryDiagnosticUnavailable, verify.RestoreVerifyError):
        return {"schema": "SQL_DIFF_EVIDENCE_V2", "verification": "UNAVAILABLE"}
