"""Fail-closed P07 parent/child failed-prepare migration reconciliation.

This module only builds a non-executable read-only evidence plan from two
in-memory state documents. It never promotes staged resources, authorizes SQL
guard bypass, imports data, contacts old VPS or permits cutover.
"""
from __future__ import annotations
from typing import Any, Mapping

SCHEMA = "vf-server-ops.server-migration.target-pull.v1"
PLAN_SCHEMA = "P07_MIGRATION_CHAIN_RECOVERY_PLAN_V1"


class ChainRecoveryBlocked(ValueError):
    """State ownership, security or continuity is not proved."""


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ChainRecoveryBlocked(code)


def _unsafe_state(data: Mapping[str, Any], *, child: bool) -> None:
    need(isinstance(data, dict) and data.get("schema") == SCHEMA,
         "CHAIN_MIGRATION_SCHEMA_INVALID")
    need(data.get("status") == "PREPARE_FAILED",
         "CHAIN_FAILED_PREPARE_REQUIRED")
    guard = data.get("last_sql_guard_failure")
    need(isinstance(guard, dict) and guard.get("reason") == "CONDITIONAL_DDL",
         "CHAIN_CONDITIONAL_DDL_GUARD_REQUIRED")
    for key in ("source_runtime_frozen", "target_runtime_activated",
                "dns_changed_by_p07", "source_delete_allowed",
                "existing_target_overwrite_allowed"):
        need(data.get(key) is False, "CHAIN_UNSAFE_RUNTIME_BOUNDARY")
    need((data.get("cutover_prohibited") is True) if child else
         (data.get("cutover_prohibited") is not True),
         "CHAIN_CUTOVER_BOUNDARY_INVALID")


def _sites(data: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int]:
    raw = data.get("sites")
    need(isinstance(raw, list) and 2 <= len(raw) <= 250,
         "CHAIN_SITE_LIST_INVALID")
    names, users, dbs = set(), set(), set()
    sites = []
    for entry in raw:
        need(isinstance(entry, dict), "CHAIN_SITE_RECORD_INVALID")
        domain, user = entry.get("domain"), entry.get("site_user")
        stage = entry.get("stage_status")
        need(isinstance(domain, str) and 0 < len(domain) <= 253
             and isinstance(user, str) and 0 < len(user) <= 128
             and stage in {"PULLED_STAGED", "PENDING"},
             "CHAIN_SITE_IDENTITY_INVALID")
        db = entry.get("mysql_databases")
        need(isinstance(db, list) and len(db) <= 1 and
             all(isinstance(x, str) and x for x in db),
             "CHAIN_SITE_DATABASE_SCOPE_INVALID")
        need(domain.lower() not in names and user not in users,
             "CHAIN_DUPLICATE_SITE_OR_USER")
        names.add(domain.lower())
        users.add(user)
        if db:
            need(db[0] not in dbs, "CHAIN_DUPLICATE_DATABASE")
            dbs.add(db[0])
        sites.append(entry)
    try:
        first_pending = next(i for i, s in enumerate(sites)
                             if s["stage_status"] == "PENDING")
    except StopIteration as exc:
        raise ChainRecoveryBlocked("CHAIN_HAS_NO_BLOCKED_SITE") from exc
    need(0 < first_pending < len(sites) - 1
         and all(s["stage_status"] == "PULLED_STAGED" for s in sites[:first_pending])
         and all(s["stage_status"] == "PENDING" for s in sites[first_pending:]),
         "CHAIN_NONCONTIGUOUS_STAGE_SEQUENCE")
    return sites, first_pending


def _source_identity(state: Mapping[str, Any]) -> tuple[Any, ...]:
    source = state.get("source")
    need(isinstance(source, dict), "CHAIN_SOURCE_UNAVAILABLE")
    fields = ("host", "ip", "ssh_user", "ssh_port")
    identity = (state.get("source_server_identity"),) + tuple(
        source.get(x) for x in fields
    )
    need(all(v is not None and v != "" for v in identity),
         "CHAIN_SOURCE_IDENTITY_UNVERIFIED")
    return identity


def select(parent: Mapping[str, Any], child: Mapping[str, Any]) -> dict[str, Any]:
    """Return only a safe-to-view consolidated inventory, never a resume token."""
    _unsafe_state(parent, child=False)
    _unsafe_state(child, child=True)
    p_id, c_id = parent.get("migration_id"), child.get("migration_id")
    need(isinstance(p_id, str) and p_id.startswith("pull-")
         and isinstance(c_id, str) and c_id.startswith("pull-")
         and c_id != p_id and child.get("partial_parent_migration_id") == p_id
         and not parent.get("partial_parent_migration_id"),
         "CHAIN_PARENT_CHILD_LINK_UNVERIFIED")
    need(_source_identity(parent) == _source_identity(child),
         "CHAIN_SOURCE_IDENTITY_CHANGED")
    need(parent.get("target_server_identity") and
         parent.get("target_server_identity") == child.get("target_server_identity"),
         "CHAIN_TARGET_IDENTITY_CHANGED")
    original, parent_first_pending = _sites(parent)
    remainder, child_first_pending = _sites(child)
    # The original parent's first blocked site is immediately before the
    # child remainder scope. This is immutable even after a proven database
    # checkpoint promotes that site from PENDING to PULLED_STAGED.
    first_block = len(original) - len(remainder) - 1
    need(0 < first_block < len(original) - 1
         and parent_first_pending in {first_block, first_block + 1},
         "CHAIN_PARENT_STAGE_SCOPE_CHANGED")

    def recovered(row: dict[str, Any]) -> bool:
        checkpoint = row.get("database_adoption")
        sql = row.get("mysql_verification")
        dbs = row.get("mysql_databases")
        return bool(
            row.get("stage_status") == "PULLED_STAGED"
            and isinstance(dbs, list) and len(dbs) == 1
            and isinstance(checkpoint, dict)
            and checkpoint.get("schema") == "P07_EXISTING_DB_ADOPTION_CHECKPOINT_V1"
            and checkpoint.get("status") == "SOURCE_TARGET_PREPARE_READBACK_PASS"
            and checkpoint.get("db_reimported") is False
            and checkpoint.get("cutover_allowed") is False
            and isinstance(sql, list)
            and any(
                isinstance(item, dict)
                and item.get("database") == dbs[0]
                and item.get("phase") == "prepare"
                and item.get("status") == "PASS"
                and item.get("recovered_from_failed_guard") is True
                for item in sql
            )
        )
    parent_adopted = parent_first_pending == first_block + 1
    need(
        recovered(original[first_block]) if parent_adopted
        else original[first_block].get("stage_status") == "PENDING",
        "CHAIN_PARENT_BLOCKER_ADOPTION_UNVERIFIED",
    )
    # An independently confirmed existing DB adoption can advance the child
    # staging prefix one site; all after it must still be untouched.
    child_adopted = (
        child_first_pending > 1 and recovered(remainder[child_first_pending - 1])
    )
    second_block = child_first_pending - (1 if child_adopted else 0)
    need(0 < second_block < len(remainder) - 1,
         "CHAIN_CHILD_BLOCKER_POSITION_INVALID")
    need(
        recovered(remainder[second_block]) if child_adopted
        else remainder[second_block].get("stage_status") == "PENDING",
        "CHAIN_CHILD_BLOCKER_ADOPTION_UNVERIFIED",
    )
    need(len(remainder) == len(original) - first_block - 1,
         "CHAIN_CHILD_SCOPE_LENGTH_CHANGED")
    for index, record in enumerate(remainder):
        expected = original[first_block + index + 1]
        for key in ("domain", "site_user", "site_root",
                    "document_root", "mysql_databases", "runtime"):
            need(record.get(key) == expected.get(key),
                 "CHAIN_CHILD_SOURCE_SITE_CONTRACT_CHANGED")
        need(expected["stage_status"] == "PENDING",
             "CHAIN_PARENT_SUFFIX_NO_LONGER_PENDING")
    total = len(original)
    first_done, second_done = first_block, second_block
    recovered_blocker_count = int(parent_adopted) + int(child_adopted)
    blocked = (original[first_block]["domain"], remainder[second_block]["domain"])
    untouched = [site["domain"] for site in remainder[second_block + 1:]]
    # The original 17-site incident has TWO truly never-created suffix
    # domains. A caller changing unzip from PENDING to PULLED_STAGED without
    # validated adoption proof must not silently move the blocker to updates.
    need(len(untouched) == 2
         and first_done + second_done + len(blocked) + len(untouched) == total,
         "CHAIN_EXPECTED_TWO_BLOCKERS_AND_SUFFIX")
    return {
        "schema": PLAN_SCHEMA,
        "status": "RECOVERY_PROOF_REQUIRED",
        "parent_migration_id": p_id,
        "child_migration_id": c_id,
        "site_count": total,
        "staged_prefix": first_done,
        "staged_child": second_done,
        "staged_count": first_done + second_done + recovered_blocker_count,
        "recovered_blocker_count": recovered_blocker_count,
        "blocker_stage_adopted": [bool(parent_adopted), bool(child_adopted)],
        "blocked_sites": list(blocked),
        "uncreated_candidate_domains": untouched,
        "source_identity_match": True,
        "target_identity_match": True,
        "child_site_scope_match": True,
        "source_runtime_frozen": False,
        "existing_target_overwrite_allowed": False,
        "guarded_database_retry_allowed": False,
        "partial_child_cutover_allowed": False,
        "consolidated_cutover_allowed": False,
        "state_writes_performed": False,
        "database_writes_performed": False,
        "site_writes_performed": False,
        "read_only_evidence_not_migration_pass": True,
    }
