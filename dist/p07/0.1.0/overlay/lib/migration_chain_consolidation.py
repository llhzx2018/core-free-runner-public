"""Read-only 17-site parent/child/tail reconciliation; NEVER a cutover state.

Three independent target-pull migration states cannot be merged merely by
concatenating site lists. Every site must retain its original ownership, source
contract and stage evidence. Output contains no live migration state schema or
PREPARED status and therefore cannot be passed into cutover_migration().
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
from typing import Any, Mapping

import app_config
import migration_chain_asset_audit
import server_migration as legacy

import migration_chain_recovery as chain

SCHEMA = "P07_17_SITE_CONSOLIDATION_EVIDENCE_V1"
EXPECTED_SITES = 17
EXPECTED_DOMAINS_LAST = ("updates.kewaro.com", "www3.m3u8.one")


class ConsolidationBlocked(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ConsolidationBlocked(code)


def _site_contract(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("domain", "site_user", "site_root", "document_root",
            "mysql_databases", "runtime")
    return {key: row.get(key) for key in keys}


def _original_source_identity(task: Mapping[str, Any]) -> tuple[Any, ...]:
    try:
        return chain._source_identity(task)
    except chain.ChainRecoveryBlocked as exc:
        raise ConsolidationBlocked("CONSOLIDATION_SOURCE_IDENTITY_UNVERIFIED") from exc


def _all_true_safe(task: Mapping[str, Any], *, status: str) -> None:
    require(isinstance(task, dict) and task.get("schema") == chain.SCHEMA,
            "CONSOLIDATION_TASK_SCHEMA_INVALID")
    require(task.get("status") == status, "CONSOLIDATION_TASK_STATUS_INVALID")
    for name in ("source_runtime_frozen", "target_runtime_activated",
                 "dns_changed_by_p07", "source_delete_allowed",
                 "existing_target_overwrite_allowed"):
        require(task.get(name) is False, "CONSOLIDATION_UNSAFE_RUNTIME_STATE")


def _prepare_db_evidence(row: Mapping[str, Any]) -> bool:
    raw = row.get("mysql_databases")
    if not isinstance(raw, list) or len(raw) > 1:
        return False
    if not raw:
        return True
    records = row.get("mysql_verification")
    if not isinstance(records, list):
        return False
    return any(
        isinstance(entry, dict)
        and entry.get("database") == raw[0]
        and entry.get("phase") == "prepare"
        and entry.get("status") == "PASS"
        and isinstance(entry.get("mode"), str)
        and entry.get("mode") in {
            "CANONICAL_SQL_EXACT", "CROSS_ENGINE_GUARDED_SESSION_SQL_EXACT",
            "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
            "CROSS_ENGINE_LOGICAL_CONTENT",
        }
        for entry in records
    )


def consolidate(
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
    tail: Mapping[str, Any],
) -> dict[str, Any]:
    """Return provenance-only 17-site reconciliation, without changing inputs."""
    try:
        chain_plan = chain.select(parent, child)
    except chain.ChainRecoveryBlocked as exc:
        raise ConsolidationBlocked("CONSOLIDATION_PARENT_CHILD_UNVERIFIED") from exc
    require(chain_plan.get("site_count") == EXPECTED_SITES,
            "CONSOLIDATION_SITE_COUNT_CHANGED")
    require(chain_plan.get("blocker_stage_adopted") == [True, True],
            "CONSOLIDATION_TWO_DATABASE_ADOPTIONS_REQUIRED")
    require(tuple(chain_plan.get("uncreated_candidate_domains") or ())
            == EXPECTED_DOMAINS_LAST,
            "CONSOLIDATION_SUFFIX_CHANGED")
    _all_true_safe(tail, status="PREPARED")
    parent_mid = parent.get("migration_id")
    child_mid = child.get("migration_id")
    tail_mid = tail.get("migration_id")
    require(
        isinstance(tail_mid, str) and tail_mid.startswith("pull-")
        and tail_mid not in (parent_mid, child_mid)
        and tail.get("partial_parent_migration_id") == parent_mid
        and tail.get("cutover_prohibited") is True,
        "CONSOLIDATION_TAIL_LINEAGE_UNVERIFIED",
    )
    require(
        _original_source_identity(tail) == _original_source_identity(parent)
        and tail.get("target_server_identity") == parent.get("target_server_identity"),
        "CONSOLIDATION_SERVER_IDENTITY_DRIFT",
    )
    tail_sites = tail.get("sites")
    require(
        isinstance(tail_sites, list) and len(tail_sites) == 2
        and all(isinstance(row, dict) for row in tail_sites),
        "CONSOLIDATION_TAIL_SCOPE_INVALID",
    )
    require(
        [row.get("domain") for row in tail_sites]
        == chain_plan["uncreated_candidate_domains"],
        "CONSOLIDATION_TAIL_DOMAINS_CHANGED",
    )
    original = parent["sites"]
    child_sites = child["sites"]
    parent_prefix_size = chain_plan["staged_prefix"] + 1
    child_prefix_size = chain_plan["staged_child"] + 1
    require(
        parent_prefix_size + child_prefix_size + len(tail_sites) == EXPECTED_SITES,
        "CONSOLIDATION_STAGE_PARTITION_INVALID",
    )
    upstream: list[tuple[Mapping[str, Any], str, int]] = []
    upstream += [
        (row, str(parent_mid), index)
        for index, row in enumerate(original[:parent_prefix_size])
    ]
    upstream += [
        (row, str(child_mid), index)
        for index, row in enumerate(child_sites[:child_prefix_size])
    ]
    upstream += [
        (row, str(tail_mid), index)
        for index, row in enumerate(tail_sites)
    ]
    domains, users, dbs = set(), set(), set()
    proven: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []
    for index, (row, owner, owner_index) in enumerate(upstream):
        expected = original[index]
        require(
            _site_contract(row) == _site_contract(expected)
            and row.get("stage_status") == "PULLED_STAGED",
            "CONSOLIDATION_ORIGINAL_SITE_CONTRACT_DRIFT",
        )
        domain = row["domain"]
        site_user = row["site_user"]
        databases = row["mysql_databases"]
        require(
            isinstance(domain, str) and domain and domain not in domains
            and isinstance(site_user, str) and site_user and site_user not in users
            and isinstance(databases, list) and len(databases) <= 1,
            "CONSOLIDATION_DUPLICATE_OR_BAD_SITE_IDENTITY",
        )
        require(_prepare_db_evidence(row),
                "CONSOLIDATION_PREPARE_DATABASE_PROOF_MISSING")
        domains.add(domain)
        users.add(site_user)
        if databases:
            require(databases[0] not in dbs,
                    "CONSOLIDATION_DUPLICATE_DATABASE")
            dbs.add(databases[0])
        contracts.append(_site_contract(row))
        # Operator-safe output: no DB credentials, original raw SQL, source
        # passwords, user paths or application config contents.
        proven.append({
            "domain": domain,
            "origin_migration_id": owner,
            "origin_site_index": owner_index,
            "database_count": len(databases),
            "prepare_evidence_present": True,
        })
    require(len(proven) == EXPECTED_SITES and
            len(domains) == EXPECTED_SITES,
            "CONSOLIDATION_FINAL_SCOPE_INCOMPLETE")
    contract_sha256 = hashlib.sha256(json.dumps(
        contracts, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")).hexdigest()
    return {
        "schema": SCHEMA,
        "status": "RECONCILED_PROVENANCE_ONLY_NOT_CUTOVER_READY",
        "site_count": EXPECTED_SITES,
        "staged_site_count": EXPECTED_SITES,
        "parent_migration_id": parent_mid,
        "child_migration_id": child_mid,
        "tail_migration_id": tail_mid,
        "source_identity_match": True,
        "target_identity_match": True,
        "three_task_scope_reconciled": True,
        "site_contract_sha256": contract_sha256,
        "sites": proven,
        "source_freeze_allowed": False,
        "target_runtime_activation_allowed": False,
        "db_reimport_allowed": False,
        "existing_db_overwrite_allowed": False,
        "cutover_allowed": False,
        "migration_state_writes_performed": False,
        "database_writes_performed": False,
        "real_server_verification": "NOT_PERFORMED",
        "final_consistency_snapshot": "NOT_VERIFIED",
    }


def original_database_provenance_map(
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
    tail: Mapping[str, Any],
) -> dict[str, str]:
    """Bind DB domains to the real *original import task*, never the new task.

    This is only structural provenance. The shadow workflow must separately
    read each private target database marker, verify the exact CloudPanel
    application mapping and check its actual target-server identity before
    writing anything. No cutover or source-freeze permission is returned.
    """
    report = consolidate(parent, child, tail)
    mapping = {
        item["domain"]: item["origin_migration_id"]
        for item in report["sites"]
        if item["database_count"] == 1
    }
    require(bool(mapping), "CONSOLIDATION_HAS_NO_DATABASES")
    require(
        len(mapping) == sum(item["database_count"] for item in report["sites"]),
        "CONSOLIDATION_ORIGINAL_DB_OWNERS_AMBIGUOUS",
    )
    return mapping


def local_target_marker_proof(
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
    tail: Mapping[str, Any],
    *,
    local_target_identity: str,
) -> dict[str, Any]:
    """Read exact CP2 owner markers and app bindings, never write files or DBs.

    Unlike the structural three-task report, this requires 17 private site
    creation markers, plus the original database receipt and a matching
    application config for every DB-bearing site. No call to
    legacy.target_*_marker: those older path helpers mkdir on read.
    It is still NOT schema/row parity, runtime acceptance, or cutover approval.
    """
    plan = consolidate(parent, child, tail)
    require(
        bool(local_target_identity)
        and local_target_identity == parent.get("target_server_identity"),
        "CONSOLIDATION_LOCAL_SERVER_IDENTITY_CHANGED",
    )
    owned_tasks = {
        str(parent["migration_id"]): parent,
        str(child["migration_id"]): child,
        str(tail["migration_id"]): tail,
    }
    checked = 0
    database_count = 0
    for reference in plan["sites"]:
        owner_id = reference["origin_migration_id"]
        item = owned_tasks[owner_id]["sites"][reference["origin_site_index"]]
        domain = str(item["domain"])
        tx = legacy.state_dir(owner_id) / "target-transactions"
        if tx.is_symlink() or not tx.is_dir():
            raise ConsolidationBlocked("CONSOLIDATION_TARGET_MARKER_ROOT_UNVERIFIED")
        name_token = hashlib.sha256(domain.encode()).hexdigest()[:16]
        marker = tx / f"site-{name_token}.json"
        try:
            if not marker.is_file() or marker.is_symlink() or (
                stat.S_IMODE(marker.stat().st_mode) & 0o077
            ):
                raise ConsolidationBlocked("CONSOLIDATION_SITE_MARKER_UNSAFE")
            site_receipt = legacy.read_target_ownership_marker(
                marker, {"domain": domain, "created_by_migration": owner_id},
            )
        except (OSError, ValueError, legacy.ServerMigrationError):
            raise ConsolidationBlocked("CONSOLIDATION_SITE_MARKER_UNVERIFIED") from None
        require(isinstance(site_receipt, dict),
                "CONSOLIDATION_SITE_MARKER_MISSING")
        root = Path(str(item["site_root"]))
        require(root.is_absolute() and not root.is_symlink() and root.is_dir(),
                "CONSOLIDATION_TARGET_SITE_ROOT_INVALID")
        dbs = item["mysql_databases"]
        if dbs:
            database = dbs[0]
            token = hashlib.sha256(
                f"{domain}:{database}:1".encode()
            ).hexdigest()[:16]
            db_marker = tx / f"db-{token}.json"
            try:
                if not db_marker.is_file() or db_marker.is_symlink() or (
                    stat.S_IMODE(db_marker.stat().st_mode) & 0o077
                ):
                    raise ConsolidationBlocked("CONSOLIDATION_DB_MARKER_UNSAFE")
                receipt = legacy.read_target_ownership_marker(
                    db_marker,
                    {"domain": domain, "database": database,
                     "created_by_migration": owner_id},
                )
            except (OSError, ValueError, legacy.ServerMigrationError):
                raise ConsolidationBlocked("CONSOLIDATION_DB_MARKER_UNVERIFIED") from None
            require(
                isinstance(receipt, dict)
                and isinstance(receipt.get("username"), str)
                and isinstance(receipt.get("password"), str)
                and bool(receipt["username"]) and bool(receipt["password"]),
                "CONSOLIDATION_DB_MARKER_CREDENTIALS_UNVERIFIED",
            )
            require(
                app_config.verify_rewritten_application_database_config(
                    root, database, receipt["username"], receipt["password"],
                ),
                "CONSOLIDATION_APPLICATION_DATABASE_BINDING_DRIFT",
            )
            database_count += 1
        checked += 1
    return {
        "schema": "P07_17_SITE_LOCAL_OWNERSHIP_EVIDENCE_V1",
        "status": "LOCAL_MARKERS_AND_APP_BINDINGS_ONLY_NOT_CUTOVER_READY",
        "site_count": checked,
        "database_count": database_count,
        "contract_sha256": plan["site_contract_sha256"],
        "local_target_identity_match": True,
        "all_migration_markers_owned": True,
        "all_database_app_bindings_checked": True,
        "sql_contents_or_row_parity_verified": False,
        "final_snapshot_verified": False,
        "cutover_allowed": False,
        "state_writes_performed": False,
        "database_writes_performed": False,
        "real_target_verification_performed": True,
    }


EXECUTION_LOCKED_SCHEMA = "P07_17_SITE_EXECUTION_CANDIDATE_LOCKED_V1"


def build_locked_execution_candidate(
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
    tail: Mapping[str, Any],
    *,
    proposed_migration_id: str,
    local_target_identity: str,
) -> dict[str, Any]:
    """Assemble the real 17-site provenance into a non-executable state.

    The original 17 websites were created by three different migration IDs.
    Concatenating their state files and running normal cutover would silently
    assume the consolidated ID owns all databases, source-freeze metadata,
    cron/PM2 jobs and external assets. Only a lock-only, non-target-pull
    candidate is produced here. There are ZERO source, database or state writes.

    No source credentials, SQL dumps or private ownership marker credentials
    are embedded in or printed from this artifact. The three parent tasks
    remain the owning authority for any later supervised execution.
    """
    require(
        isinstance(proposed_migration_id, str)
        and proposed_migration_id.startswith("pull-")
        and bool(legacy.SAFE_ID_RE.fullmatch(proposed_migration_id)),
        "CONSOLIDATED_EXECUTION_ID_INVALID",
    )
    plan = consolidate(parent, child, tail)
    old_ids = (
        str(parent["migration_id"]), str(child["migration_id"]),
        str(tail["migration_id"]),
    )
    require(
        proposed_migration_id not in old_ids and len(set(old_ids)) == 3,
        "CONSOLIDATED_EXECUTION_ID_COLLISION",
    )
    require(
        bool(local_target_identity)
        and local_target_identity == parent.get("target_server_identity"),
        "CONSOLIDATED_EXECUTION_TARGET_IDENTITY_CHANGED",
    )
    # A local real-machine identity, private CloudPanel site receipt and
    # original DB configuration must pass for ALL 17 sites, not only two DBs.
    local = local_target_marker_proof(
        parent, child, tail, local_target_identity=local_target_identity,
    )
    require(
        local.get("schema") == "P07_17_SITE_LOCAL_OWNERSHIP_EVIDENCE_V1"
        and local.get("status") == "LOCAL_MARKERS_AND_APP_BINDINGS_ONLY_NOT_CUTOVER_READY"
        and local.get("site_count") == EXPECTED_SITES
        and local.get("contract_sha256") == plan["site_contract_sha256"]
        and local.get("local_target_identity_match") is True
        and local.get("all_migration_markers_owned") is True
        and local.get("all_database_app_bindings_checked") is True
        and local.get("cutover_allowed") is False,
        "CONSOLIDATED_EXECUTION_LOCAL_PROOF_INCOMPLETE",
    )
    original_map = original_database_provenance_map(parent, child, tail)
    require(
        local.get("database_count") == len(original_map),
        "CONSOLIDATED_EXECUTION_DATABASE_COUNT_DRIFT",
    )
    originals = dict(zip(old_ids, (parent, child, tail)))
    owned_sites: list[dict[str, Any]] = []
    for record in plan["sites"]:
        owner_id = record["origin_migration_id"]
        site_index = record["origin_site_index"]
        source_row = originals[owner_id]["sites"][site_index]
        # Retain only a digest and the immutable original task/index pointer.
        # Later execution must reread the original private source records and
        # reject any mutation before it can stage files or freeze source.
        contract = _site_contract(source_row)
        row_digest = hashlib.sha256(json.dumps(
            contract, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")).hexdigest()
        owned_sites.append({
            "domain": record["domain"],
            "original_migration_id": owner_id,
            "original_site_index": site_index,
            "database_count": record["database_count"],
            "site_contract_sha256": row_digest,
        })
    inventories = {}
    # No automatic union of three independent external paths / cron / PM2 /
    # SQLite / source freeze records. Even apparently equal paths can have
    # different staging roots and ownership. Bind their original snapshots.
    asset_keys = (
        "external_assets", "sqlite_assets", "runtime_assets",
        "pending_system_cron", "pending_user_cron", "pending_pm2",
        "source_http_baseline", "source_external_listeners",
    )
    for mid, task in originals.items():
        metadata = {key: task.get(key) for key in asset_keys}
        inventories[mid] = hashlib.sha256(json.dumps(
            metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")).hexdigest()
    asset_scope = migration_chain_asset_audit.audit(parent, child, tail, plan)
    return {
        "schema": EXECUTION_LOCKED_SCHEMA,
        "status": "LOCKED_AWAITING_FULL_ASSET_AND_FREEZE_RECOVERY_PROOF",
        "migration_id": proposed_migration_id,
        "original_migration_ids": list(old_ids),
        "original_database_migration_owners": original_map,
        "target_server_identity": local_target_identity,
        "site_contract_sha256": plan["site_contract_sha256"],
        "site_count": EXPECTED_SITES,
        "database_count": len(original_map),
        "sites": owned_sites,
        "original_asset_inventory_sha256": inventories,
        "asset_audit": asset_scope,
        "all_original_site_markers_verified": True,
        "all_original_db_app_bindings_verified": True,
        "source_runtime_staged_for_new_migration": False,
        "all_site_files_final_verified": False,
        "all_external_assets_final_verified": False,
        "all_sqlite_snapshots_final_verified": False,
        "all_cron_pm2_jobs_final_verified": False,
        "all_source_http_baselines_fresh": False,
        "source_runtime_frozen": False,
        "target_runtime_activated": False,
        "cutover_prohibited": True,
        "cutover_allowed": False,
        "source_freeze_allowed": False,
        "dns_changed_by_p07": False,
        "source_delete_allowed": False,
        "existing_target_overwrite_allowed": False,
        "database_writes_performed": False,
        "state_writes_performed": False,
        "real_source_consistency_snapshot": "NOT_VERIFIED",
        "production_migration": "NOT_PERFORMED",
    }


# This is deliberately NOT a wrapper around migration_final_db_batch._safe_scope:
# that routine requires a single CUTOVER_RUNNING owner. The three historical
# PREPARE_FAILED owners cannot be promoted to a fake consolidated migration.
P07_BLOCKED_DATABASE_DOMAINS = frozenset({
    "ilovem3u8.kewaro.com", "unzip.kewaro.com", "www3.m3u8.one",
})


def bind_locked_original_database_scope(
    plan: Mapping[str, Any],
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
    tail: Mapping[str, Any],
) -> dict[str, Any]:
    """Read-only DB scope bridge for the existing 21-step final-sync saga.

    Bind exact original task, site contract, DB identity and status without
    reading data, creating a shadow, reconnecting www3 or opening a single
    CloudPanel connection. This is NOT proof of row parity or a recovery point.
    """
    import migration_chain_final_saga as saga
    try:
        saga.validate_locked_plan(plan)
    except saga.SagaBlocked:
        raise ConsolidationBlocked("CHAIN_DB_LOCKED_PLAN_INVALID") from None
    # Keep the parent/child failed-prepare lineage as the authority, and
    # independently confirm tail belongs to that same original migration.
    # A copied site list with a new migration ID must never inherit a
    # database owner's recovery or candidate connection.
    try:
        selected = chain.select(parent, child)
    except chain.ChainRecoveryBlocked:
        raise ConsolidationBlocked(
            "CHAIN_DB_PARENT_CHILD_LINEAGE_UNVERIFIED") from None
    require(selected.get("site_count") == 17 and
            tuple(selected.get("uncreated_candidate_domains") or ())
            == EXPECTED_DOMAINS_LAST,
            "CHAIN_DB_SEVENTEEN_SITE_LINEAGE_CHANGED")
    require(tail.get("partial_parent_migration_id") ==
            parent.get("migration_id") and
            tail.get("cutover_prohibited") is True and
            isinstance(tail.get("sites"), list) and
            len(tail["sites"]) == 2 and
            [row.get("domain") for row in tail["sites"]
             if isinstance(row, dict)] == list(EXPECTED_DOMAINS_LAST),
            "CHAIN_DB_TAIL_LINEAGE_UNVERIFIED")
    require(tail.get("status") != "PREPARED" or
            all(row.get("stage_status") == "PULLED_STAGED"
                for row in tail["sites"]),
            "CHAIN_DB_TAIL_FALSE_PREPARED")
    tasks = (parent, child, tail)
    by_id: dict[str, Mapping[str, Any]] = {}
    source_fingerprint = plan["source_identity_sha256"]
    target_fingerprint = plan["target_identity_sha256"]
    for task in tasks:
        require(isinstance(task, dict), "CHAIN_DB_ORIGINAL_TASK_INVALID")
        mid = task.get("migration_id")
        require(isinstance(mid, str) and
                legacy.SAFE_ID_RE.fullmatch(mid) is not None and
                mid not in by_id, "CHAIN_DB_ORIGINAL_OWNER_DUPLICATE")
        by_id[mid] = task
        try:
            original_source = _original_source_identity(task)
        except ConsolidationBlocked:
            raise ConsolidationBlocked("CHAIN_DB_SOURCE_IDENTITY_UNVERIFIED") from None
        source_hash = hashlib.sha256(json.dumps(
            original_source, ensure_ascii=True, sort_keys=True,
            separators=(",", ":")).encode("ascii")).hexdigest()
        target_hash = hashlib.sha256(
            str(task.get("target_server_identity", "")).encode("utf-8")
        ).hexdigest()
        require(source_hash == source_fingerprint and
                target_hash == target_fingerprint,
                "CHAIN_DB_SERVER_IDENTITY_DRIFT")
        require(task.get("status") in {"PREPARE_FAILED", "PREPARED"}
                and task.get("source_runtime_frozen") is False
                and task.get("target_runtime_activated") is False
                and task.get("dns_changed_by_p07") is False
                and task.get("source_delete_allowed") is False
                and task.get("existing_target_overwrite_allowed") is False,
                "CHAIN_DB_ORIGINAL_RUNTIME_UNSAFE")

    first = plan["steps"][:17]
    require(len(by_id) == 3 and
            set(by_id) == {s["owner"] for s in first},
            "CHAIN_DB_ORIGINAL_OWNER_SET_CHANGED")
    database_names: set[str] = set()
    records: list[dict[str, Any]] = []
    for step in first:
        original = by_id[step["owner"]]
        index = step["index"]
        rows = original.get("sites")
        require(isinstance(rows, list) and 0 <= index < len(rows)
                and isinstance(rows[index], dict),
                "CHAIN_DB_ORIGINAL_SITE_INDEX_CHANGED")
        site = rows[index]
        contract_hash = hashlib.sha256(json.dumps(
            _site_contract(site), ensure_ascii=True, sort_keys=True,
            separators=(",", ":")).encode("ascii")).hexdigest()
        require(site.get("domain") == step["domain"] and
                contract_hash == step["site_contract_sha256"] and
                site.get("stage_status") ==
                ("PENDING" if step["domain"] in plan["pending_domains"]
                 else "PULLED_STAGED"),
                "CHAIN_DB_ORIGINAL_SITE_CONTRACT_CHANGED")
        dbs = site.get("mysql_databases")
        require(isinstance(dbs, list) and len(dbs) <= 1,
                "CHAIN_DB_DATABASE_LIST_INVALID")
        if not dbs:
            continue
        db_name = dbs[0]
        require(isinstance(db_name, str) and db_name and
                db_name.casefold() not in database_names,
                "CHAIN_DB_DATABASE_IDENTITY_COLLISION")
        database_names.add(db_name.casefold())
        records.append({
            "domain": step["domain"],
            "original_owner": step["owner"],
            "original_index": index,
            "site_contract_sha256": contract_hash,
            "database_sha256": hashlib.sha256(
                db_name.encode("utf-8")).hexdigest(),
            "stage_status": site["stage_status"],
            # A standalone connection or a once-staged DB is never
            # equivalent to final source SQL, row-parity or recovery proof.
            "final_shadow_receipt": "NOT_VERIFIED",
            "source_sql_effects": "NOT_PROVEN",
            "app_mapping_recovery": "NOT_VERIFIED",
        })
    domains = {item["domain"] for item in records}
    require(len(records) == 3 and domains == P07_BLOCKED_DATABASE_DOMAINS,
            "CHAIN_DB_THREE_ORIGINAL_DATABASES_CHANGED")
    digest = hashlib.sha256(json.dumps({
        "plan_sha256": plan["plan_sha256"], "records": records,
        "source": source_fingerprint, "target": target_fingerprint,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")).hexdigest()
    return {
        "schema": "P07_CHAIN_ORIGINAL_DB_SHADOW_SCOPE_V1",
        "status": "LOCKED_DB_RECOVERY_REQUIRED_NOT_CUTOVER_READY",
        "plan_sha256": plan["plan_sha256"],
        "scope_sha256": digest,
        "site_count": 17, "original_task_count": 3,
        "database_count": len(records),
        "databases": records,
        "pending_database_domains": sorted(
            item["domain"] for item in records
            if item["stage_status"] == "PENDING"),
        "blockers": [
            "FINAL_SOURCE_SQL_AND_ROW_PARITY_REQUIRED",
            "ORIGINAL_OWNER_DB_SHADOW_RECEIPTS_REQUIRED",
            "CROSS_OWNER_DB_APP_MAPPING_ROLLBACK_REQUIRED",
            "WWW3_CONNECTED_NOT_CUTOVER_READY",
        ],
        "original_states_unchanged": True,
        "cross_task_batch_execution_allowed": False,
        "source_freeze_allowed": False,
        "target_activation_allowed": False,
        "cutover_allowed": False,
        "database_writes_performed": False,
        "migration_state_writes_performed": False,
    }
