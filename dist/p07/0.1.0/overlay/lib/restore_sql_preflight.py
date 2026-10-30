"""Fail-closed pre-import check for unsafe guarded SET statements on BOTH exports.

Only guards accepted by the existing cross-engine parser are counted here.
This is not a complete SQL sandbox or evidence of safe arbitrary SQL; native
scratch imports still require independent host/runtime safety review.
"""
from __future__ import annotations
from pathlib import Path
import sql_diff_evidence

class GuardBlocked(RuntimeError):
    pass

def require_no_unsafe_dynamic_guard(source_sql: Path, target_sql: Path) -> None:
    for path in (source_sql, target_sql):
        try:
            counts = sql_diff_evidence.dynamic_guard_syntax_counts(path)
        except Exception:
            raise GuardBlocked("RESTORE_DYNAMIC_SQL_GUARD_UNAVAILABLE") from None
        for key in ("recognized_unsafe", "double_quoted_if", "other_unknown_set"):
            value = counts.get(key)
            if type(value) is not int or value < 0:
                raise GuardBlocked("RESTORE_DYNAMIC_SQL_GUARD_UNPROVEN")
            if value:
                raise GuardBlocked("RESTORE_UNSAFE_DYNAMIC_SQL_GUARD_BLOCKED")
