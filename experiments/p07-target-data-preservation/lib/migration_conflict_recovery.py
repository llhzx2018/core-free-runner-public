"""Fail-closed read-only conflict recovery work order.

Pure conversion of sanitized, advisory-only database export evidence into a
non-executable operator review checklist. This is NOT a database backup,
restoration proof, merge plan executable, migration admission, or SQL generator.
There is intentionally no "ready", "approved", or "apply" path. Raw evidence
is never copied to output: fixed reason codes, non-sensitive ordinals/counts.
"""
from __future__ import annotations

from typing import Any, Mapping

_SCHEMA = "P07_CONFLICT_RECOVERY_DRAFT_V1"
_REQUIRED_PROOFS = (
    "SOURCE_INDEPENDENT_RECOVERY_POINT_RESTORE_TEST",
    "TARGET_INDEPENDENT_RECOVERY_POINT_RESTORE_TEST",
    "BOTH_SIDES_CONSISTENT_POINT_IN_TIME",
    "TARGET_WRITE_QUIESCENCE_VERIFIED",
    "LIVE_ROW_VALUE_SEMANTICS_VERIFIED",
    "DYNAMIC_GUARDED_SQL_REVIEWED",
    "EXPLICIT_OPERATOR_CONFLICT_POLICY",
    "ROLLBACK_PATH_VALIDATED",
)


class InvalidAdvisoryEvidence(ValueError):
    pass


def _object(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise InvalidAdvisoryEvidence("EVIDENCE_FORMAT_UNPROVEN")
    return value


def _number(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 10_000_000:
        raise InvalidAdvisoryEvidence("COUNT_UNPROVEN")
    return value


def _fail(code: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "status": "BLOCKED_UNPROVEN_EVIDENCE",
        "reason": code,
        "requires": list(_REQUIRED_PROOFS),
        "data_writes_allowed": False,
        "migration_resume_allowed": False,
        "cutover_allowed": False,
        "verification": "NOT_A_PASS_GATE",
    }


def draft(result: Mapping[str, Any]) -> dict[str, Any]:
    """No code path authorizes business-data writes, regardless of input.

    Evidence is an ephemeral read-only dump comparison, not a recovery proof.
    This output never contains keys, rows, domains, SQL or full dump hashes.
    """
    try:
        item = _object(result)
        ev = _object(item.get("evidence"))
        pk = _object(ev.get("pk_conflicts"))
        tuples = _object(ev.get("row_tuples"))
        multiset = _object(ev.get("row_multiset"))
        guards = _object(ev.get("dynamic_guard"))
        differences = pk.get("differing_table_ordinals")
        counts = tuples.get("differing_table_ordinals")
        if (
            item.get("status") != "ADVISORY_DIAGNOSTIC_ONLY"
            or item.get("database_writes_performed") is not False
            or item.get("migration_state_modified") is not False
            or ev.get("verification") != "NOT_A_PASS_GATE"
            or pk.get("verification") != "NOT_A_PASS_GATE"
            or pk.get("comparison") != "PK_LITERAL_DIFFER"
            or not isinstance(differences, list)
            or not isinstance(counts, list)
        ):
            raise InvalidAdvisoryEvidence("EVIDENCE_PROVENANCE_UNPROVEN")
        total = _number(pk.get("tables_examined"))
        evaluable = _number(pk.get("pk_tables_evaluable"))
        unavailable = _number(pk.get("pk_tables_unavailable"))
        if total < 1 or evaluable + unavailable != total or unavailable:
            raise InvalidAdvisoryEvidence("PRIMARY_KEY_TABLE_COVERAGE_UNPROVEN")
        if _number(tuples.get("tables_examined")) != total:
            raise InvalidAdvisoryEvidence("TABLE_SCOPE_UNPROVEN")
        if _number(pk.get("differing_pk_tables")) != len(differences):
            raise InvalidAdvisoryEvidence("PRIMARY_KEY_DIFFERENCES_UNPROVEN")
        if _number(tuples.get("differing_tables")) != len(counts):
            raise InvalidAdvisoryEvidence("TUPLE_DIFFERENCES_UNPROVEN")
        if not differences or len(differences) != len(counts):
            raise InvalidAdvisoryEvidence("CONFLICT_TABLE_IDENTITY_UNPROVEN")
        tuple_by_ord = {
            _number(row["table_ordinal"]): _object(row)
            for row in counts if isinstance(row, dict)
        }
        if len(tuple_by_ord) != len(counts):
            raise InvalidAdvisoryEvidence("CONFLICT_TABLE_IDENTITY_UNPROVEN")
        work = []
        pks = {"source_only_keys": 0, "target_only_keys": 0,
               "same_key_changed_literals": 0, "identical_key_identical_literals": 0}
        for entry in differences:
            row = _object(entry)
            ordinal = _number(row.get("table_ordinal"))
            if not 1 <= ordinal <= total or ordinal not in tuple_by_ord:
                raise InvalidAdvisoryEvidence("CONFLICT_TABLE_IDENTITY_UNPROVEN")
            counts_row = tuple_by_ord[ordinal]
            source_only = _number(row.get("source_only_keys"))
            target_only = _number(row.get("target_only_keys"))
            changed = _number(row.get("same_key_changed_literals"))
            equal = _number(row.get("identical_key_identical_literals"))
            if (
                source_only == target_only == changed == 0
                or equal + source_only + changed != _number(counts_row.get("source_rows"))
                or equal + target_only + changed != _number(counts_row.get("target_rows"))
            ):
                raise InvalidAdvisoryEvidence("CONFLICT_COUNTS_UNPROVEN")
            for key, value in (
                ("source_only_keys", source_only),
                ("target_only_keys", target_only),
                ("same_key_changed_literals", changed),
                ("identical_key_identical_literals", equal),
            ):
                pks[key] += value
            work.append({
                "table_ordinal": ordinal,
                "source_only_keys": source_only,
                "target_only_keys": target_only,
                "same_key_changed_literals": changed,
                "default_handling": "RETAIN_BOTH_COPIES_REVIEW_REQUIRED",
                "delete_or_replace_allowed": False,
            })
        for key in ("source_only_keys", "target_only_keys", "same_key_changed_literals"):
            if pks[key] != _number(pk.get(key)):
                raise InvalidAdvisoryEvidence("CONFLICT_TOTALS_UNPROVEN")
        # Different statement column orders can cause a conservative mismatch,
        # so the multiset is supporting evidence but never migration proof.
        if _number(multiset.get("tables_examined")) != total:
            raise InvalidAdvisoryEvidence("MULTISET_SCOPE_UNPROVEN")
        if _number(guards.get("recognized_unsafe")):
            guard_status = "UNPROVEN_GUARDED_SQL_REMAINS"
        else:
            guard_status = "DYNAMIC_SQL_INDEPENDENT_GATE_REQUIRED"
        return {
            "schema": _SCHEMA,
            "status": "BLOCKED_RECOVERY_AND_OPERATOR_DECISIONS",
            "data_writes_allowed": False,
            "migration_resume_allowed": False,
            "cutover_allowed": False,
            "tables_examined": total,
            "conflict_tables": len(work),
            "conflicts": work,
            "dynamic_sql": guard_status,
            "requires": list(_REQUIRED_PROOFS),
            "conflict_policy": "UNSELECTED",
            "recovery_proof": "NOT_ESTABLISHED",
            "consistent_snapshot": "NOT_ESTABLISHED",
            "verification": "NOT_A_PASS_GATE",
        }
    except (InvalidAdvisoryEvidence, KeyError, TypeError):
        return _fail("CROSS_EVIDENCE_INCOMPLETE_OR_INCONSISTENT")
