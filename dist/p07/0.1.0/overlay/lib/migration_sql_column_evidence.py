"""Cross-engine SQL column-metadata evidence classifier.

Consumes previously produced read-only, redacted source/target column-property
fingerprints. It distinguishes narrowly-normalized presentation differences
from remaining metadata differences. This is NOT a SQL dynamic-DDL semantic
proof, a data snapshot, a retry token, or permission to alter migration state.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

FIELDS = (
    "ORDINAL_POSITION", "DATA_TYPE", "COLUMN_TYPE", "IS_NULLABLE",
    "COLUMN_DEFAULT", "EXTRA", "CHARACTER_SET_NAME", "COLLATION_NAME",
    "GENERATION_EXPRESSION",
)
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class ColumnEvidenceBlocked(ValueError):
    pass


def _valid_pair(value: Any) -> bool:
    return (
        isinstance(value, list) and len(value) == 2
        and all(type(x) is str and _HASH.fullmatch(x) for x in value)
    )


def _validated(obj: Any) -> Mapping[str, Mapping[str, list[str]]]:
    if type(obj) is not dict or not 1 <= len(obj) <= 100000:
        raise ColumnEvidenceBlocked("COLUMN_METADATA_SCOPE_INVALID")
    for column_id, fields in obj.items():
        if (type(column_id) is not str or not _HASH.fullmatch(column_id)
                or type(fields) is not dict or set(fields) != set(FIELDS)
                or any(not _valid_pair(value) for value in fields.values())):
            raise ColumnEvidenceBlocked("COLUMN_METADATA_RECORD_INVALID")
    return obj


def compare(
    source: Any,
    target: Any,
    *,
    expected_column_count: int | None = None,
) -> dict[str, Any]:
    """Return aggregate differences only; schema outcome always unverified."""
    a, b = _validated(source), _validated(target)
    if expected_column_count is not None and (
        type(expected_column_count) is not int
        or not 1 <= expected_column_count <= 100000
        or len(a) != expected_column_count
        or len(b) != expected_column_count
    ):
        raise ColumnEvidenceBlocked("COLUMN_METADATA_EXPECTED_COUNT_MISMATCH")
    shared = a.keys() & b.keys()
    raw_changed = set()
    evidence = {}
    outstanding = 0
    for field in FIELDS:
        changed, normalized_changed = 0, 0
        for col in shared:
            if a[col][field][0] != b[col][field][0]:
                changed += 1
                raw_changed.add(col)
            if a[col][field][1] != b[col][field][1]:
                normalized_changed += 1
        # Never classify a mismatch as only a formatting difference solely
        # because normalized digests match: the normalizer is not an audited
        # equivalence relation for arbitrary SQL expressions/defaults.
        outstanding += normalized_changed
        evidence[field] = {
            "raw_changed": changed,
            "after_narrow_presentation_normalization": normalized_changed,
            "presentation_candidates": max(0, changed - normalized_changed),
        }
    return {
        "schema": "P07_CROSS_ENGINE_COLUMN_DIAGNOSTIC_V1",
        "source_columns": len(a),
        "target_columns": len(b),
        "source_only_column_identities": len(a.keys() - b.keys()),
        "target_only_column_identities": len(b.keys() - a.keys()),
        "columns_with_raw_property_differences": len(raw_changed),
        "unresolved_normalized_property_differences": outstanding,
        "properties": evidence,
        "normalization_grants_schema_equivalence": False,
        "dynamic_ddl_semantics_verified": False,
        "original_export_snapshot_matched": False,
        "source_target_data_parity_verified": False,
        "cutover_allowed": False,
        "database_writes_performed": False,
        "state_writes_performed": False,
    }
