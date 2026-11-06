"""P07 owner-scoped final-window authority.

The OWNER approved a brief outage of all 17 sites, while the three
previously pending sites remain the exact data-reconciliation scope.
Approval of an outage is not authorization to execute a source freeze.
This module never contacts a server, modifies data or changes DNS.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json

OWNER_SITES = (
    "ilovem3u8.kewaro.com",
    "unzip.kewaro.com",
    "www3.m3u8.one",
)
PLAN_SCHEMA = "P07_CHAIN_FINAL_SAGA_PLAN_V1"
SCHEMA = "P07_THREE_SITE_WINDOW_AUTHORITY_V1"


class WindowBlocked(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise WindowBlocked(reason)


def owner_window_scope(
    plan: Mapping, selected_sites: tuple[str, ...], *,
    whole_server_outage_approved: bool = False,
) -> dict:
    """Bind independent outage and three-database scopes; never execute."""
    require(type(whole_server_outage_approved) is bool,
            "P07_WINDOW_OUTAGE_APPROVAL_TYPE_INVALID")
    # Bind to the existing 21-step 17-site planner, not a caller-crafted list.
    from migration_chain_final_saga import validate_locked_plan

    validate_locked_plan(plan)
    require(type(selected_sites) is tuple and selected_sites == OWNER_SITES,
            "P07_WINDOW_NOT_OWNER_APPROVED_THREE")
    pending = plan.get("pending_domains")
    # Pending is a staging status, not the owner's scope: after the final
    # three sites are staged, consent must still cover exactly these three.
    # Any newly pending 14-site domain remains a hard failure.
    require(type(pending) is list
            and len(pending) == len(set(pending))
            and set(pending).issubset(set(OWNER_SITES)),
            "P07_WINDOW_PENDING_SCOPE_CHANGED")
    sites = plan["steps"][:17]
    owners = {s["domain"]: s["owner"] for s in sites}
    require(len(owners) == 17
            and len({owners[s] for s in OWNER_SITES}) == 3,
            "P07_WINDOW_THREE_ORIGINAL_OWNERS_UNVERIFIED")
    # Only downtime expands to 17 sites. Database/asset ownership never
    # expands implicitly, nor does it acquire write/rollback authority.
    all_domains = tuple(s["domain"] for s in sites)
    require(len(all_domains) == 17 and len(set(all_domains)) == 17
            and set(OWNER_SITES).issubset(all_domains),
            "P07_WINDOW_ALL_SITE_OUTAGE_SCOPE_INVALID")
    outage_domains = all_domains if whole_server_outage_approved else OWNER_SITES
    outage_identity = sha256(json.dumps(
        {"plan": plan["plan_sha256"], "domains": list(outage_domains),
         "approved": whole_server_outage_approved},
        sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    identity = {
        "plan_sha256": plan["plan_sha256"],
        "scope_sha256": plan["scope_sha256"],
        "source_identity_sha256": plan["source_identity_sha256"],
        "target_identity_sha256": plan["target_identity_sha256"],
        "sites": list(OWNER_SITES),
        "owners": [owners[s] for s in OWNER_SITES],
        "whole_server_outage_approved": whole_server_outage_approved,
        "outage_identity_sha256": outage_identity,
    }
    digest = sha256(json.dumps(identity, sort_keys=True,
                               separators=(",", ":")).encode("ascii")).hexdigest()
    return {
        "schema": SCHEMA,
        "status": "OWNER_APPROVAL_BOUND_EXECUTION_BLOCKED",
        "approved_sites": list(OWNER_SITES),
        "pending_site_count": len(pending),
        "other_sites_unaffected_count": (
            0 if whole_server_outage_approved else 14
        ),
        "other_sites_outside_database_reconciliation_count": 14,
        "identity_sha256": digest,
        "approved_outage_scope": (
            "ALL_17_SITE_BRIEF_MAINTENANCE" if whole_server_outage_approved
            else "THREE_SITE_MAINTENANCE_ONLY"
        ),
        "outage_site_count": len(outage_domains),
        "outage_identity_sha256": outage_identity,
        "whole_server_outage_owner_approved": whole_server_outage_approved,
        # This flag remains FALSE until final snapshots, shadow DBs, and
        # rollback are actually proven. Never reinterpret approval as a gate.
        "global_nginx_stop_allowed": False,
        "legacy_global_source_freeze_allowed": False,
        "source_pause_performed": False,
        "source_pause_now_allowed": False,
        "requires_independent_site_scoped_pause_resume": (
            not whole_server_outage_approved
        ),
        "requires_global_pause_and_verified_restore": (
            whole_server_outage_approved
        ),
        "requires_final_source_snapshot_and_no_overwrite_shadow": True,
        "requires_cross_task_rollback_and_app_http_proof": True,
        "old_server_shutdown_allowed": False,
        "source_data_delete_allowed": False,
        "target_existing_db_overwrite_allowed": False,
        "automatic_dns_change_allowed": False,
        "cutover_allowed": False,
        "writes_performed": False,
    }



def assemble_seventeen_site_source_maintenance(
    plan: Mapping, original_tasks: tuple[Mapping, Mapping, Mapping],
) -> dict:
    """Build a *non-executable* all-site source pause control.

    A failed parent/child/tail chain must not freeze source once per task.
    Reconcile 17 original site owners and deduplicate Cron/PM2 resources first.
    The returned private control is data, not approval or a runnable journal;
    the real final executor still needs new frozen SQL/file proof and recovery.
    """
    from pathlib import PurePosixPath
    from migration_chain_consolidation import _site_contract

    consent = owner_window_scope(
        plan, OWNER_SITES, whole_server_outage_approved=True,
    )
    require(consent["outage_site_count"] == 17
            and not consent["source_pause_now_allowed"],
            "P07_SOURCE_MAINTENANCE_CONSENT_DRIFT")
    require(type(original_tasks) is tuple and len(original_tasks) == 3
            and all(isinstance(x, dict) for x in original_tasks),
            "P07_SOURCE_MAINTENANCE_TASKS_INVALID")
    tasks = {x.get("migration_id"): x for x in original_tasks}
    require(len(tasks) == 3
            and set(tasks) == {s["owner"] for s in plan["steps"][:17]},
            "P07_SOURCE_MAINTENANCE_OWNERS_CHANGED")
    require(len({str(t.get("target_server_identity")) for t in original_tasks}) == 1,
            "P07_SOURCE_MAINTENANCE_TARGET_DRIFT")
    source = original_tasks[0].get("source")
    source_identity = original_tasks[0].get("source_server_identity")
    require(isinstance(source, dict) and source_identity
            and all(t.get("source") == source
                    and t.get("source_server_identity") == source_identity
                    and t.get("source_runtime_frozen") is False
                    and t.get("target_runtime_activated") is False
                    and t.get("dns_changed_by_p07") is False
                    for t in original_tasks),
            "P07_SOURCE_MAINTENANCE_RUNTIME_OR_SOURCE_DRIFT")

    sites = []
    for step in plan["steps"][:17]:
        record = tasks[step["owner"]]
        index = step["index"]
        rows = record.get("sites")
        require(isinstance(rows, list) and 0 <= index < len(rows),
                "P07_SOURCE_MAINTENANCE_SITE_INDEX_DRIFT")
        site = rows[index]
        require(site.get("domain") == step["domain"]
                and sha256(json.dumps(
                    _site_contract(site), sort_keys=True,
                    separators=(",", ":"), ensure_ascii=True,
                ).encode("ascii")).hexdigest()
                == step["site_contract_sha256"],
                "P07_SOURCE_MAINTENANCE_SITE_CONTRACT_CHANGED")
        sites.append(site)
    require(len(sites) == 17 and
            len({x["domain"] for x in sites}) == 17,
            "P07_SOURCE_MAINTENANCE_SITE_DUPLICATED")

    # PREPARE_FAILED can occur before stage_runtime_assets() is reached.
    # The original source inventory is available earlier and is the only
    # safe source for a single 17-site stop plan. Pending target staging is
    # optional, but if present must describe the same source resources.
    site_users = {str(site["site_user"]) for site in sites}
    resource_controls = {}
    for name, source_kind in (
        ("pending_system_cron", "system_cron"),
        ("pending_user_cron", "user_cron"),
        ("pending_pm2", "pm2"),
    ):
        unique = {}
        original_details = {}
        for task in original_tasks:
            runtime = task.get("runtime_assets")
            require(type(runtime) is dict
                    and all(type(runtime.get(k)) is list
                            for k in ("system_cron", "user_cron", "pm2")),
                    "P07_SOURCE_MAINTENANCE_INVENTORY_UNVERIFIED")
            discovered = []
            for source_entry in runtime[source_kind]:
                require(type(source_entry) is dict,
                        "P07_SOURCE_MAINTENANCE_RESOURCE_UNVERIFIED")
                if source_kind == "system_cron":
                    path = source_entry.get("path")
                    require(type(path) is str and path.startswith("/etc/cron.d/"),
                            "P07_SOURCE_MAINTENANCE_SYSTEM_CRON_SCOPE_INVALID")
                    row = {"source_path": path, "activated": False}
                    identity = path
                else:
                    user = source_entry.get("user")
                    require(type(user) is str and user in site_users,
                            "P07_SOURCE_MAINTENANCE_USER_SCOPE_INVALID")
                    if source_kind == "user_cron":
                        path = source_entry.get("path")
                        require(path in (f"/var/spool/cron/crontabs/{user}",
                                         f"/var/spool/cron/{user}"),
                                "P07_SOURCE_MAINTENANCE_USER_CRON_SCOPE_INVALID")
                    else:
                        path = source_entry.get("dump")
                        require(path == f"/home/{user}/.pm2/dump.pm2"
                                and type(source_entry.get("node_runtime")) is str
                                and bool(source_entry["node_runtime"]),
                                "P07_SOURCE_MAINTENANCE_PM2_SCOPE_INVALID")
                    row = {"user": user, "source_path": path, "activated": False}
                    identity = user

                require(type(path) is str
                        and PurePosixPath(path).is_absolute()
                        and ".." not in PurePosixPath(path).parts
                        and "\x00" not in path
                        and str(PurePosixPath(path)) == path,
                        "P07_SOURCE_MAINTENANCE_RESOURCE_PATH_UNSAFE")
                discovered.append(row)
                details = (path, source_entry.get("node_runtime")
                           if source_kind == "pm2" else None)
                if identity in unique:
                    require(unique[identity] == row
                            and original_details[identity] == details,
                            "P07_SOURCE_MAINTENANCE_OVERLAP_CONFLICT")
                else:
                    unique[identity] = row
                    original_details[identity] = details
            # A partial task may not have reached target staging. But a
            # previously staged list must never contradict its source list.
            pending = task.get(name)
            if pending is not None:
                require(type(pending) is list
                        and len(pending) == len(discovered),
                        "P07_SOURCE_MAINTENANCE_TARGET_STAGE_DRIFT")
                normalized = []
                for item in pending:
                    require(type(item) is dict
                            and item.get("activated") is False,
                            "P07_SOURCE_MAINTENANCE_TARGET_STAGE_DRIFT")
                    normalized.append({
                        k: item.get(k) for k in discovered[0]
                    } if discovered else {})
                # Order is not a source authority; compare stable identities.
                def canonical(rows):
                    return sorted(json.dumps(x, sort_keys=True)
                                  for x in rows)
                require(canonical(normalized) == canonical(discovered),
                        "P07_SOURCE_MAINTENANCE_TARGET_STAGE_DRIFT")
        resource_controls[name] = [unique[k] for k in sorted(unique)]

    control = {
        "migration_id": "p07-17-site-source-freeze-control",
        "sites": sites,
        **resource_controls,
    }
    # No production caller may interpret this as permission to freeze.
    digest = sha256(json.dumps(control, sort_keys=True,
                               ensure_ascii=True,
                               separators=(",", ":")).encode("ascii")).hexdigest()
    return {
        "schema": "P07_17_SITE_SOURCE_MAINTENANCE_PLAN_V1",
        "status": "CONTROL_ASSEMBLED_EXECUTION_BLOCKED",
        "control_sha256": digest,
        "site_count": 17,
        "original_task_count": 3,
        "system_cron_count": len(resource_controls["pending_system_cron"]),
        "user_cron_count": len(resource_controls["pending_user_cron"]),
        "pm2_count": len(resource_controls["pending_pm2"]),
        "control": control,
        "source_pause_performed": False,
        "source_pause_allowed": False,
        "source_final_snapshot_verified": False,
        "target_database_writes_performed": False,
        "cutover_allowed": False,
    }
