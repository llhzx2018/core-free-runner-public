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
        seen_ordinals = set()
        pks = {"source_only_keys": 0, "target_only_keys": 0,
               "same_key_changed_literals": 0, "identical_key_identical_literals": 0}
        for entry in differences:
            row = _object(entry)
            ordinal = _number(row.get("table_ordinal"))
            if not 1 <= ordinal <= total or ordinal not in tuple_by_ord or ordinal in seen_ordinals:
                raise InvalidAdvisoryEvidence("CONFLICT_TABLE_IDENTITY_UNPROVEN")
            seen_ordinals.add(ordinal)
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


# These are review-slot selections, not database primary keys. Ordinals have
# no stable identity across dumps; never generate SQL or claim live-row proof.
_POLICY_SCHEMA = "P07_CONFLICT_POLICY_REVIEW_V1"
_MAX_REVIEW_SLOTS = 500
_ALLOWED_CHOICES = {
    "SOURCE_ONLY": frozenset(("RETAIN_SOURCE_COPY", "DEFER_REVIEW")),
    "TARGET_ONLY": frozenset(("RETAIN_TARGET_COPY", "DEFER_REVIEW")),
    "SAME_KEY_LITERAL_DIFFER": frozenset((
        "PREFER_SOURCE_AFTER_SEMANTIC_PROOF",
        "PREFER_TARGET_AFTER_SEMANTIC_PROOF",
        "MANUAL_MERGE_REVIEW",
        "FORMAT_EQUIVALENCE_REVIEW",
        "DEFER_REVIEW",
    )),
}
_UNRESOLVED_CHOICES = frozenset((
    "DEFER_REVIEW", "MANUAL_MERGE_REVIEW", "FORMAT_EQUIVALENCE_REVIEW",
))


def _policy_response(status: str, *, expected: int = 0,
                     selected: int = 0, unresolved: int = 0) -> dict[str, Any]:
    """Never reflect caller text, values, keys, SQL, hosts or approval claims."""
    return {
        "schema": _POLICY_SCHEMA,
        "status": status,
        "expected_review_slots": expected,
        "selected_review_slots": selected,
        "unresolved_review_slots": unresolved,
        "primary_keys_bound_to_review_slots": False,
        "source_recovery_verified": False,
        "target_recovery_verified": False,
        "live_row_semantics_verified": False,
        "operator_approval_verified": False,
        "dynamic_sql_verified": False,
        "data_writes_allowed": False,
        "migration_resume_allowed": False,
        "cutover_allowed": False,
        "verification": "NOT_A_PASS_GATE",
    }


def review_policy(advisory: Mapping[str, Any], selections: Any) -> dict[str, Any]:
    """Validate privacy-safe, non-executable choices for *each* advisory slot.

    A review slot is only (table ordinal, category, position in that category).
    It is NOT a primary key, row fingerprint or deterministic row mapping.
    The output cannot approve a data change even with complete selections or
    caller-supplied proof/approval flags. Real policies must be bound to actual
    private row identities, semantic evidence and restored recovery points.
    """
    work_order = draft(advisory)
    if work_order["status"] != "BLOCKED_RECOVERY_AND_OPERATOR_DECISIONS":
        return _policy_response("BLOCKED_ADVISORY_UNPROVEN")
    expected: dict[tuple[int, str, int], None] = {}
    for table in work_order["conflicts"]:
        table_ordinal = table["table_ordinal"]
        for kind, count_field in (
            ("SOURCE_ONLY", "source_only_keys"),
            ("TARGET_ONLY", "target_only_keys"),
            ("SAME_KEY_LITERAL_DIFFER", "same_key_changed_literals"),
        ):
            count = table[count_field]
            if len(expected) + count > _MAX_REVIEW_SLOTS:
                return _policy_response("BLOCKED_REVIEW_SCOPE_LIMIT")
            for position in range(1, count + 1):
                expected[(table_ordinal, kind, position)] = None
    total = len(expected)
    if type(selections) is not list or len(selections) > total:
        return _policy_response("BLOCKED_INVALID_SELECTION", expected=total)
    recorded: dict[tuple[int, str, int], str] = {}
    for item in selections:
        if type(item) is not dict or set(item) != {
            "table_ordinal", "kind", "item_ordinal", "decision"
        }:
            return _policy_response("BLOCKED_INVALID_SELECTION", expected=total)
        ordinal, kind, position, decision = (
            item["table_ordinal"], item["kind"],
            item["item_ordinal"], item["decision"],
        )
        if (type(ordinal) is not int or type(position) is not int
                or type(kind) is not str or type(decision) is not str):
            return _policy_response("BLOCKED_INVALID_SELECTION", expected=total)
        slot = (ordinal, kind, position)
        if (slot not in expected or slot in recorded
                or decision not in _ALLOWED_CHOICES.get(kind, ())):
            return _policy_response("BLOCKED_INVALID_SELECTION", expected=total)
        recorded[slot] = decision
    unresolved = total - len(recorded) + sum(
        choice in _UNRESOLVED_CHOICES for choice in recorded.values()
    )
    status = (
        "BLOCKED_EXTERNAL_RECOVERY_AND_ROW_PROOF"
        if unresolved == 0
        else "BLOCKED_OPERATOR_REVIEW_INCOMPLETE"
    )
    return _policy_response(
        status, expected=total, selected=len(recorded), unresolved=unresolved,
    )
