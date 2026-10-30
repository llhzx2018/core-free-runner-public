"""Read-only, redacted multiset deltas from two private SQL exports.

Not a live database query, consistent snapshot, SQL semantic comparator, or
migration PASS gate. Distinct row hashes are only local/transient. Fail closed
on unsupported SQL or size and never report a row, table name or digest.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

import sql_row_evidence as sql_rows

MAX_DISTINCT_ROWS = 250_000
MAX_TOTAL_ROWS = 5_000_000


def _collect(path: Path, tables: set[str]) -> dict[str, Counter[bytes]]:
    seen: dict[str, Counter[bytes]] = {name: Counter() for name in tables}
    distinct = 0
    total = 0
    for statement in sql_rows._statements(path):
        for table, verb, columns, fields in sql_rows._rows(statement):
            if table not in seen:
                raise sql_rows.SQLRowUnproven("ROW_REFERENCES_UNKNOWN_TABLE")
            representation = json.dumps(
                [verb, list(columns), list(fields)],
                ensure_ascii=False, separators=(",", ":"),
            ).encode("utf-8")
            hashed = hashlib.sha256(representation).digest()
            counts = seen[table]
            if hashed not in counts:
                distinct += 1
                if distinct > MAX_DISTINCT_ROWS:
                    raise sql_rows.SQLRowUnproven("DISTINCT_ROW_LIMIT")
            total += 1
            if total > MAX_TOTAL_ROWS:
                raise sql_rows.SQLRowUnproven("TOTAL_ROW_LIMIT")
            counts[hashed] += 1
    return seen


def diagnostic(
    source: Path, target: Path, source_tables: set[str], target_tables: set[str],
) -> dict[str, Any]:
    """Find how many tuple instances are unmatched in *either* direction.

    Count differences alone cannot establish which particular tuples differ:
    a target net +2 can mean +2 only, or e.g. +7 with -5.
    """
    if not source_tables or source_tables != target_tables:
        return {"comparison": "UNAVAILABLE", "reason": "TABLE_IDENTITY_UNPROVEN"}
    try:
        before = _collect(source, source_tables)
        after = _collect(target, target_tables)
    except sql_rows.SQLRowUnproven as exc:
        return {"comparison": "UNAVAILABLE", "reason": str(exc)}
    source_only_total = 0
    target_only_total = 0
    matching_total = 0
    changed = []
    for i, name in enumerate(sorted(source_tables), 1):
        left = before[name]
        right = after[name]
        shared = sum((left & right).values())
        source_only = sum((left - right).values())
        target_only = sum((right - left).values())
        source_only_total += source_only
        target_only_total += target_only
        matching_total += shared
        if source_only or target_only:
            changed.append({
                "table_ordinal": i,
                "source_only_tuple_instances": source_only,
                "target_only_tuple_instances": target_only,
                "shared_tuple_instances": shared,
                "difference_class": (
                    "TARGET_EXTRA_ONLY" if target_only and not source_only
                    else "SOURCE_EXTRA_ONLY" if source_only and not target_only
                    else "BIDIRECTIONAL_DIFFERENCE"
                ),
            })
    return {
        "comparison": (
            "ROW_MULTISET_DIFFER" if changed
            else "NO_INSERT_ROWS" if matching_total == 0
            else "ROW_MULTISET_EQUAL_NOT_VERIFIED"
        ),
        "tables_examined": len(source_tables),
        "differing_tables": len(changed),
        "shared_tuple_instances": matching_total,
        "source_only_tuple_instances": source_only_total,
        "target_only_tuple_instances": target_only_total,
        "differing_table_ordinals": changed[:42],
        "semantics": "DUMP_SQL_LITERAL_MULTISET_ONLY",
        "verification": "NOT_A_PASS_GATE",
    }
