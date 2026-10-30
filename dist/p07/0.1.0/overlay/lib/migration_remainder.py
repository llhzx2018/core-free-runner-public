"""Fail-closed selector for staging untouched sites after a SQL-guard stop.

This helper NEVER authorizes retry of the blocked site, SQL recovery, cutover,
or edits to the parent migration. Its candidate set is only the untouched
PENDING suffix of a single verified PREPARE_FAILED migration.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "vf-server-ops.server-migration.target-pull.v1"


class RemainderBlocked(ValueError):
    """The parent state is not a safe source for remainder staging."""


def select(parent: Mapping[str, Any]) -> dict[str, Any]:
    """Return a bounded, non-executable staging scope, without editing state."""
    if not isinstance(parent, dict) or parent.get("schema") != SCHEMA:
        raise RemainderBlocked("REMAINDER_PARENT_SCHEMA_UNPROVEN")
    if (parent.get("status") != "PREPARE_FAILED"
            or not isinstance(parent.get("last_sql_guard_failure"), dict)
            or parent["last_sql_guard_failure"].get("reason") != "CONDITIONAL_DDL"):
        raise RemainderBlocked("REMAINDER_SQL_GUARD_PARENT_REQUIRED")
    if (parent.get("source_runtime_frozen") is not False
            or parent.get("target_runtime_activated") is not False
            or parent.get("dns_changed_by_p07") is not False
            or parent.get("source_delete_allowed") is not False
            or parent.get("existing_target_overwrite_allowed") is not False
            or parent.get("partial_parent_migration_id")):
        raise RemainderBlocked("REMAINDER_PARENT_RUNTIME_UNPROVEN")
    source = parent.get("source")
    if (not isinstance(source, dict) or not source.get("host")
            or not source.get("ip") or not source.get("ssh_user")
            or not parent.get("source_server_identity")):
        raise RemainderBlocked("REMAINDER_SOURCE_IDENTITY_UNPROVEN")
    if not isinstance(parent.get("migration_id"), str) or not parent["migration_id"]:
        raise RemainderBlocked("REMAINDER_PARENT_ID_UNPROVEN")
    sites = parent.get("sites")
    if not isinstance(sites, list) or not 3 <= len(sites) <= 250:
        raise RemainderBlocked("REMAINDER_SITE_INVENTORY_UNPROVEN")
    seen_domains: set[str] = set()
    seen_users: set[str] = set()
    statuses: list[str] = []
    names: list[str] = []
    for row in sites:
        if not isinstance(row, dict):
            raise RemainderBlocked("REMAINDER_SITE_INVENTORY_UNPROVEN")
        name, user, stage = row.get("domain"), row.get("site_user"), row.get("stage_status")
        if (not isinstance(name, str) or not name
                or not isinstance(user, str) or not user
                or stage not in {"PULLED_STAGED", "PENDING"}
                or name.lower() in seen_domains or user in seen_users):
            raise RemainderBlocked("REMAINDER_SITE_IDENTITY_OR_STAGE_UNPROVEN")
        seen_domains.add(name.lower())
        seen_users.add(user)
        names.append(name)
        statuses.append(stage)
    # Must be a contiguous, already-staged prefix, then exactly one blocked
    # PENDING site, then an untouched PENDING suffix. The parent can never
    # declare its blocked site staged or silently skip a noncontiguous site.
    try:
        index = statuses.index("PENDING")
    except ValueError as exc:
        raise RemainderBlocked("REMAINDER_NO_BLOCKED_SITE") from exc
    if index < 1 or index >= len(statuses) - 1 or any(
        item != "PENDING" for item in statuses[index:]
    ):
        raise RemainderBlocked("REMAINDER_NONCONTIGUOUS_OR_EMPTY")
    return {
        "schema": "P07_REMAINDER_STAGING_SCOPE_V1",
        "status": "STAGING_SCOPE_ONLY",
        "parent_migration_id": parent["migration_id"],
        "blocked_site": names[index],
        "already_staged_sites": index,
        "remaining_sites": len(names) - index - 1,
        "candidate_domains": names[index + 1:],
        "cutover_allowed": False,
        "existing_target_overwrite_allowed": False,
        "blocked_site_retry_allowed": False,
        "parent_state_modified": False,
        "verification": "NOT_A_MIGRATION_PASS",
    }
