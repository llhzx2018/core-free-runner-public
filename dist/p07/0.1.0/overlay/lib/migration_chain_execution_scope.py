"""Fail-closed 17-site recovery execution scope for the existing three owners.

This is the owner-bound precursor to a future transactional executor, NOT
an executable migration state. It maps each original site to its one actual
import task, recognizes a separately connected www3 configuration without
calling it staged, and never imports, freezes or changes a migration receipt.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any, Mapping

import migration_chain_consolidation as consolidated
import migration_chain_recovery as chain
import migration_chain_final_saga as final_saga
import server_migration as legacy

SCHEMA = "P07_17_SITE_RECOVERY_EXECUTION_SCOPE_V1"
CONNECTION_SCHEMA = "p07.www3.config-connection.v1"
CONNECTION_DIR = "www3-source-rule-connection-v1"


class RecoveryScopeBlocked(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RecoveryScopeBlocked(reason)


def _read_private(path: Path, *, owner: int = 0) -> bytes:
    """Race-resistant private read; never follow a swapped link.

    lstat() followed by Path.open() could follow a newly replaced symlink.
    An O_NOFOLLOW fd and two fstat checks bind the returned bytes to one
    regular, privately owned and unchanged inode.
    """
    fd = -1
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_uid == owner
                and not stat.S_IMODE(before.st_mode) & 0o077
                and 0 < before.st_size <= 2 * 1024 * 1024,
                "CHAIN_PRIVATE_RECEIPT_UNSAFE")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            data = handle.read(2 * 1024 * 1024 + 1)
        after = os.fstat(fd)
        require(len(data) == before.st_size
                and (before.st_dev, before.st_ino, before.st_size,
                     before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns),
                "CHAIN_PRIVATE_RECEIPT_DRIFT")
        return data
    except OSError:
        raise RecoveryScopeBlocked("CHAIN_PRIVATE_RECEIPT_UNAVAILABLE") from None
    finally:
        if fd >= 0:
            os.close(fd)


def connected_www3_proof(tail: Mapping[str, Any], *, root: Path | None = None,
                         private_owner: int = 0) -> dict[str, Any]:
    """Read the existing config connection only, not DB rows or SQL.

    A connected wp-config proves neither source snapshot parity nor staging.
    No write or migration-state promotion occurs, including on error.
    """
    mid = tail.get("migration_id")
    require(isinstance(mid, str) and legacy.SAFE_ID_RE.fullmatch(mid),
            "CHAIN_TAIL_ID_INVALID")
    root = legacy.STATE_ROOT if root is None else root
    folder = root / mid / "target-transactions" / CONNECTION_DIR
    try:
        info = folder.lstat()
    except FileNotFoundError:
        return {"status": "ABSENT_NOT_PROVEN", "cutover_allowed": False}
    except OSError:
        raise RecoveryScopeBlocked("CHAIN_WWW3_CONNECTION_DIRECTORY_UNREADABLE") from None
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == private_owner
            and not info.st_mode & 0o077,
            "CHAIN_WWW3_CONNECTION_DIRECTORY_UNSAFE")
    try:
        receipt = json.loads(_read_private(folder / "journal.json",
                                           owner=private_owner))
    except (ValueError, UnicodeDecodeError):
        raise RecoveryScopeBlocked("CHAIN_WWW3_CONNECTION_JOURNAL_INVALID") from None
    require(isinstance(receipt, dict) and receipt.get("schema") == CONNECTION_SCHEMA,
            "CHAIN_WWW3_CONNECTION_JOURNAL_INVALID")
    require(receipt.get("target_identity") == tail.get("target_server_identity"),
            "CHAIN_WWW3_CONNECTION_TARGET_DRIFT")
    require(receipt.get("cutover_allowed") is False
            and receipt.get("database_writes") is False
            and receipt.get("migration_state_promoted") is False,
            "CHAIN_WWW3_CONNECTION_BOUNDARY_INVALID")
    state = receipt.get("status")
    require(state in {"INTENT_RESERVED", "CONNECTED_NOT_CUTOVER_READY",
                      "ROLLBACK_REQUIRED", "ROLLED_BACK"},
            "CHAIN_WWW3_CONNECTION_STATUS_UNKNOWN")
    rows = [s for s in tail.get("sites", [])
            if isinstance(s, dict) and s.get("domain") == "www3.m3u8.one"]
    require(len(rows) == 1, "CHAIN_WWW3_SITE_IDENTITY_UNPROVEN")
    site_root = rows[0].get("site_root")
    expected_path = receipt.get("config_path")
    require(isinstance(site_root, str) and Path(site_root).is_absolute()
            and ".." not in Path(site_root).parts
            and isinstance(expected_path, str)
            and expected_path in {
                str(Path(site_root) / "wp-config.php"),
                str(Path(site_root) / "public" / "wp-config.php"),
            },
            "CHAIN_WWW3_CONFIG_PATH_CHANGED")
    metadata = receipt.get("metadata")
    require(isinstance(metadata, dict)
            and all(type(metadata.get(k)) is int for k in ("uid", "gid", "mode"))
            and 0 <= metadata["mode"] <= 0o777
            and not metadata["mode"] & 0o002
            and receipt.get("site_owner_uid") == metadata["uid"],
            "CHAIN_WWW3_CONFIG_METADATA_UNVERIFIED")
    original = _read_private(folder / "original.php", owner=private_owner)
    candidate = _read_private(folder / "candidate.php", owner=private_owner)
    rollback = _read_private(folder / "rollback.sh", owner=private_owner)
    require(bool(rollback) and
            hashlib.sha256(original).hexdigest() == receipt.get("original_sha256")
            and hashlib.sha256(candidate).hexdigest() == receipt.get("candidate_sha256")
            and original != candidate,
            "CHAIN_WWW3_CONFIG_BACKUPS_UNVERIFIED")
    path = Path(expected_path)
    fd = -1
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
                == (metadata["uid"], metadata["gid"], metadata["mode"])
                and 0 < info.st_size <= 2 * 1024 * 1024,
                "CHAIN_WWW3_LIVE_CONFIG_UNSAFE")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            config = handle.read(2 * 1024 * 1024 + 1)
        after = os.fstat(fd)
        require(len(config) == info.st_size
                and (info.st_dev, info.st_ino, info.st_size,
                     info.st_mtime_ns, info.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns),
                "CHAIN_WWW3_LIVE_CONFIG_DRIFT")
    except OSError:
        raise RecoveryScopeBlocked("CHAIN_WWW3_LIVE_CONFIG_UNAVAILABLE") from None
    finally:
        if fd >= 0:
            os.close(fd)
    observed = hashlib.sha256(config).hexdigest()
    matched = (
        "CANDIDATE_MATCH" if observed == receipt["candidate_sha256"]
        else "ORIGINAL_MATCH" if observed == receipt["original_sha256"]
        else "CHANGED_UNKNOWN"
    )
    require(matched != "CHANGED_UNKNOWN",
            "CHAIN_WWW3_CONCURRENT_CONFIG_EDIT")
    require(
        (state == "CONNECTED_NOT_CUTOVER_READY" and matched == "CANDIDATE_MATCH")
        or (state == "ROLLED_BACK" and matched == "ORIGINAL_MATCH")
        or state in {"INTENT_RESERVED", "ROLLBACK_REQUIRED"},
        "CHAIN_WWW3_CONNECTION_STATUS_CONFIG_CONFLICT",
    )
    return {
        "status": state,
        "config": matched,
        "rollback_bundle_present": True,
        "final_source_equality_proven": False,
        "site_stage_promoted": False,
        "cutover_allowed": False,
    }


def scope(parent: Mapping[str, Any], child: Mapping[str, Any],
          tail: Mapping[str, Any], *, root: Path | None = None,
          private_owner: int = 0) -> dict[str, Any]:
    """Establish 17 single owners and staged/pending counts before any write."""
    try:
        chain_plan = chain.select(parent, child)
    except chain.ChainRecoveryBlocked:
        raise RecoveryScopeBlocked("CHAIN_ORIGINAL_LINEAGE_UNVERIFIED") from None
    require(chain_plan.get("site_count") == 17
            and tuple(chain_plan.get("uncreated_candidate_domains") or ())
            == consolidated.EXPECTED_DOMAINS_LAST,
            "CHAIN_17_SITE_SCOPE_CHANGED")
    require(isinstance(tail, dict) and tail.get("schema") == chain.SCHEMA
            and tail.get("status") in {"PREPARE_FAILED", "PREPARED"}
            and tail.get("cutover_prohibited") is True
            and tail.get("partial_parent_migration_id") == parent.get("migration_id")
            and tail.get("migration_id") not in {
                parent.get("migration_id"), child.get("migration_id")},
            "CHAIN_TAIL_LINEAGE_UNVERIFIED")
    try:
        require(consolidated._original_source_identity(tail) ==
                consolidated._original_source_identity(parent)
                and tail.get("target_server_identity") ==
                parent.get("target_server_identity"),
                "CHAIN_TAIL_SERVER_IDENTITY_CHANGED")
    except consolidated.ConsolidationBlocked:
        raise RecoveryScopeBlocked("CHAIN_TAIL_SERVER_IDENTITY_CHANGED") from None
    for name in ("source_runtime_frozen", "target_runtime_activated",
                 "dns_changed_by_p07", "source_delete_allowed",
                 "existing_target_overwrite_allowed"):
        require(tail.get(name) is False, "CHAIN_TAIL_RUNTIME_UNSAFE")
    tail_rows = tail.get("sites")
    require(isinstance(tail_rows, list) and len(tail_rows) == 2
            and all(isinstance(s, dict) for s in tail_rows)
            and [s.get("domain") for s in tail_rows]
            == list(consolidated.EXPECTED_DOMAINS_LAST),
            "CHAIN_TAIL_SITE_SCOPE_CHANGED")
    tail_stages = [s.get("stage_status") for s in tail_rows]
    require(tail_stages in (["PULLED_STAGED", "PENDING"],
                            ["PULLED_STAGED", "PULLED_STAGED"]),
            "CHAIN_TAIL_STAGE_SEQUENCE_UNVERIFIED")
    require(tail.get("status") != "PREPARED" or
            tail_stages == ["PULLED_STAGED", "PULLED_STAGED"],
            "CHAIN_TAIL_FALSE_PREPARED")
    original = parent["sites"]
    child_rows = child["sites"]
    first = len(original) - len(child_rows) - 1
    second = len(child_rows) - 3
    require((first, second) == (7, 6),
            "CHAIN_ORIGINAL_SITE_PARTITION_CHANGED")
    owned = ([(parent, i) for i in range(first + 1)]
             + [(child, i) for i in range(second + 1)]
             + [(tail, i) for i in range(2)])
    require(len(owned) == 17, "CHAIN_17_SITE_OWNER_COVERAGE_INVALID")
    checked = []
    domains = set()
    users = set()
    staged = 0
    for index, (task, pos) in enumerate(owned):
        row = task["sites"][pos]
        expected = original[index]
        require(consolidated._site_contract(row) ==
                consolidated._site_contract(expected),
                "CHAIN_SOURCE_SITE_CONTRACT_DRIFT")
        domain, user = row.get("domain"), row.get("site_user")
        databases = row.get("mysql_databases")
        require(isinstance(domain, str) and domain not in domains
                and isinstance(user, str) and user not in users
                and isinstance(databases, list) and len(databases) <= 1,
                "CHAIN_DUPLICATE_SITE_OWNER")
        domains.add(domain)
        users.add(user)
        is_staged = row.get("stage_status") == "PULLED_STAGED"
        require(is_staged or row.get("stage_status") == "PENDING",
                "CHAIN_SITE_STAGE_INVALID")
        staged += int(is_staged)
        contract_sha256 = hashlib.sha256(json.dumps(
            consolidated._site_contract(row), sort_keys=True,
            separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")).hexdigest()
        checked.append({
            "site_contract_sha256": contract_sha256,
            "domain": domain,
            "owner_migration_id": task["migration_id"],
            "owner_index": pos,
            "stage_status": row["stage_status"],
            "database_count": len(databases),
        })
    connection = connected_www3_proof(tail, root=root,
                                       private_owner=private_owner)
    blockers = []
    if not chain_plan["blocker_stage_adopted"][0]:
        blockers.append("ILOVE_EXISTING_DB_ADOPTION_REQUIRED")
    if not chain_plan["blocker_stage_adopted"][1]:
        blockers.append("UNZIP_EXISTING_DB_ADOPTION_REQUIRED")
    if tail_stages[1] == "PENDING":
        blockers.append("WWW3_STAGE_NOT_VERIFIED")
    if connection.get("status") != "CONNECTED_NOT_CUTOVER_READY":
        blockers.append("WWW3_CANDIDATE_CONNECTION_UNVERIFIED")
    # Even a fully staged set is not an executable transaction. The final
    # source snapshot, excluded dynamic SQL, multi-owner rollback and live
    # HTTP acceptance remain independent mandatory gates.
    blockers.append("FINAL_17_SITE_SYNC_AND_ROLLBACK_NOT_PROVEN")
    source_sha256 = hashlib.sha256(json.dumps(
        consolidated._original_source_identity(parent), sort_keys=True,
        separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")).hexdigest()
    target_sha256 = hashlib.sha256(
        str(parent["target_server_identity"]).encode("utf-8")
    ).hexdigest()
    identity = hashlib.sha256(json.dumps({
        "sites": [(x["domain"], x["owner_migration_id"], x["owner_index"],
                   x["stage_status"], x["site_contract_sha256"])
                  for x in checked],
        "source": source_sha256, "target": target_sha256,
    }, sort_keys=True, ensure_ascii=True,
       separators=(",", ":")).encode("ascii")).hexdigest()
    result = {
        "schema": SCHEMA,
        "status": "OWNERSHIP_RESOLVED_EXECUTION_BLOCKED",
        "site_count": len(checked),
        "staged_count": staged,
        "pending_count": len(checked) - staged,
        "source_task_count": 3,
        "site_owner_scope_sha256": identity,
        "source_identity_sha256": source_sha256,
        "target_identity_sha256": target_sha256,
        "sites": checked,
        "www3_connection": connection,
        "blockers": blockers,
        "source_final_snapshot": "NOT_PROVEN",
        "cross_task_rollback": "NOT_PROVEN",
        "source_freeze_allowed": False,
        "target_runtime_activation_allowed": False,
        "cutover_allowed": False,
        "database_writes_performed": False,
        "migration_state_writes_performed": False,
    }
    # Make the new recovery sequence discoverable from the *same* owner
    # reconciliation entry. It is immutable/read-only, and remains LOCKED
    # while even one of the three pending sites or final proofs is missing.
    result["final_sync_plan"] = final_saga.operation_plan(result)
    return result



def original_db_local_marker_evidence(
    plan: Mapping[str, Any],
    parent: Mapping[str, Any], child: Mapping[str, Any],
    tail: Mapping[str, Any], *, root: Path | None = None,
    private_owner: int = 0,
) -> dict[str, Any]:
    """Read real CP2 original-owner transaction markers, not database rows.

    The marker root and both exact marker filenames must already exist.
    This function must never call legacy.target_db_marker/target_tx_root:
    both helpers create/chmod folders, even when intended only for reading.
    Missing markers are evidence gaps, not a statement that DBs are absent.
    A malformed/forged marker is a hard stop. Credentials are never returned.
    """
    import app_config
    try:
        db_scope = consolidated.bind_locked_original_database_scope(
            plan, parent, child, tail)
    except consolidated.ConsolidationBlocked:
        raise RecoveryScopeBlocked("CHAIN_DB_MARKER_PROVENANCE_INVALID") from None
    base = legacy.STATE_ROOT if root is None else root
    require(isinstance(base, Path) and base.is_absolute()
            and not base.is_symlink(),
            "CHAIN_DB_MARKER_ROOT_UNVERIFIED")
    owners = {task["migration_id"]: task for task in (parent, child, tail)}
    records = []
    for expected in db_scope["databases"]:
        mid = expected["original_owner"]
        domain = expected["domain"]
        task = owners[mid]
        site = task["sites"][expected["original_index"]]
        database = site["mysql_databases"][0]
        tx = base / mid / "target-transactions"
        try:
            info = tx.lstat()
        except FileNotFoundError:
            records.append({
                "domain": domain,
                "original_owner": mid,
                "original_site_marker": "ABSENT_UNVERIFIED",
                "original_database_marker": "ABSENT_UNVERIFIED",
                "application_binding": "NOT_CHECKED_MISSING_OWNER_MARKER",
            })
            continue
        except OSError:
            raise RecoveryScopeBlocked(
                "CHAIN_DB_TRANSACTION_DIRECTORY_UNAVAILABLE") from None
        try:
            owner_info = tx.parent.lstat()
        except OSError:
            raise RecoveryScopeBlocked(
                "CHAIN_DB_ORIGINAL_OWNER_DIRECTORY_UNAVAILABLE") from None
        require(stat.S_ISDIR(owner_info.st_mode)
                and owner_info.st_uid == private_owner
                and not stat.S_IMODE(owner_info.st_mode) & 0o077,
                "CHAIN_DB_ORIGINAL_OWNER_DIRECTORY_UNSAFE")
        require(stat.S_ISDIR(info.st_mode)
                and info.st_uid == private_owner
                and not stat.S_IMODE(info.st_mode) & 0o077,
                "CHAIN_DB_TRANSACTION_DIRECTORY_UNSAFE")
        site_token = hashlib.sha256(domain.encode()).hexdigest()[:16]
        db_token = hashlib.sha256(
            f"{domain}:{database}:1".encode()).hexdigest()[:16]
        site_path = tx / f"site-{site_token}.json"
        db_path = tx / f"db-{db_token}.json"
        states = {}
        marker = None
        for label, path, required in (
            ("original_site_marker", site_path, {
                "domain": domain, "created_by_migration": mid,
            }),
            ("original_database_marker", db_path, {
                "domain": domain, "database": database,
                "created_by_migration": mid,
            }),
        ):
            if not os.path.lexists(path):
                states[label] = "ABSENT_UNVERIFIED"
                continue
            try:
                payload = json.loads(_read_private(path, owner=private_owner))
            except (ValueError, UnicodeError):
                raise RecoveryScopeBlocked(
                    "CHAIN_DB_ORIGINAL_MARKER_INVALID") from None
            require(isinstance(payload, dict) and
                    all(payload.get(k) == v for k, v in required.items()),
                    "CHAIN_DB_ORIGINAL_MARKER_OWNER_CHANGED")
            states[label] = "ORIGINAL_OWNER_VERIFIED"
            if label == "original_database_marker":
                marker = payload
        if marker is None:
            binding = "NOT_CHECKED_MISSING_OWNER_MARKER"
        else:
            username, password = marker.get("username"), marker.get("password")
            require(isinstance(username, str) and bool(username)
                    and isinstance(password, str) and bool(password),
                    "CHAIN_DB_ORIGINAL_MARKER_CREDENTIALS_INVALID")
            root_path = Path(str(site["site_root"]))
            require(root_path.is_absolute() and
                    ".." not in root_path.parts and
                    root_path.is_dir() and not root_path.is_symlink(),
                    "CHAIN_DB_APPLICATION_ROOT_UNVERIFIED")
            # The existing verifier detects ambiguous Wordpress/Dotenv
            # configuration; "MATCH" does not prove SQL row parity or site
            # functionality, only the current exact app credential binding.
            try:
                verified = app_config.verify_rewritten_application_database_config(
                    root_path, database, username, password)
            except (OSError, ValueError):
                verified = False
            binding = ("EXACT_ORIGINAL_MARKER_MATCH"
                       if verified else "UNVERIFIED_OR_CHANGED")
        records.append({
            "domain": domain, "original_owner": mid,
            **states, "application_binding": binding,
        })
    return {
        "schema": "P07_CHAIN_ORIGINAL_DB_LOCAL_MARKER_READBACK_V1",
        "status": "LOCAL_ORIGINAL_OWNER_MARKERS_ONLY_NOT_DATA_PARITY",
        "original_task_count": 3,
        "database_count": len(records),
        "databases": records,
        "original_owner_site_markers_verified": sum(
            r["original_site_marker"] == "ORIGINAL_OWNER_VERIFIED"
            for r in records),
        "original_owner_db_markers_verified": sum(
            r["original_database_marker"] == "ORIGINAL_OWNER_VERIFIED"
            for r in records),
        "application_original_binding_verified": sum(
            r["application_binding"] == "EXACT_ORIGINAL_MARKER_MATCH"
            for r in records),
        "source_target_row_parity_verified": False,
        "database_writes_performed": False,
        "site_config_writes_performed": False,
        "migration_state_writes_performed": False,
        "cutover_allowed": False,
    }

def original_database_readiness(
    parent: Mapping[str, Any], child: Mapping[str, Any],
    tail: Mapping[str, Any], *, root: Path | None = None,
    private_owner: int = 0, verify_original_markers: bool = False,
) -> dict[str, Any]:
    """One existing-evidence CP2 read, three original owners, no network.

    This endpoint deliberately does not call source_probe, import, mysql,
    export, sqlite, app reconfiguration, or the existing shadow switcher.
    Any initial first-stage adoption is explicitly NOT a final snapshot.
    """
    report = scope(parent, child, tail, root=root, private_owner=private_owner)
    try:
        database_scope = consolidated.bind_locked_original_database_scope(
            report["final_sync_plan"], parent, child, tail)
    except consolidated.ConsolidationBlocked:
        raise RecoveryScopeBlocked(
            "CHAIN_DATABASE_ORIGINAL_PROVENANCE_UNVERIFIED") from None
    require(database_scope.get("database_count") == 3
            and database_scope.get("cross_task_batch_execution_allowed") is False
            and database_scope.get("cutover_allowed") is False,
            "CHAIN_DATABASE_UNSAFE_SCOPE")
    expected = {
        "ilovem3u8.kewaro.com": "EXISTING_DB_ROW_CONFLICT_RECONCILIATION",
        "unzip.kewaro.com": "ORIGINAL_OWNER_ADOPTION_AND_SQL_READBACK",
        "www3.m3u8.one": "DYNAMIC_SQL_EFFECT_AND_SITE_STAGE_PROOF",
    }
    domains = {row["domain"]: row for row in database_scope["databases"]}
    require(set(domains) == set(expected),
            "CHAIN_DATABASE_THREE_SITES_CHANGED")
    www3 = report.get("www3_connection")
    require(isinstance(www3, dict)
            and www3.get("cutover_allowed") is False,
            "CHAIN_DATABASE_WWW3_CONNECTION_UNVERIFIED")
    statuses = []
    for domain, gate in expected.items():
        row = domains[domain]
        stage = row["stage_status"]
        require(stage in {"PENDING", "PULLED_STAGED"}
                and row.get("final_shadow_receipt") == "NOT_VERIFIED"
                and row.get("source_sql_effects") == "NOT_PROVEN"
                and row.get("app_mapping_recovery") == "NOT_VERIFIED",
                "CHAIN_DATABASE_FALSE_FINAL_PASS")
        # Parent/child adoption carries an original-owner checkpoint.
        # A manually changed tail stage flag alone does NOT independently
        # prove www3 SQL dynamic effects, DB adoption or final row parity.
        if stage == "PENDING":
            first_stage = "PENDING_ORIGINAL_RECOVERY_PROOF"
        elif domain == "www3.m3u8.one":
            first_stage = "STAGED_FLAG_ONLY_FINAL_DB_PROOF_UNVERIFIED"
        else:
            first_stage = "ADOPTION_CHECKPOINT_RECORDED_FINAL_PROOF_MISSING"
        statuses.append({
            "domain": domain,
            "original_owner": row["original_owner"],
            "original_index": row["original_index"],
            "site_contract_sha256": row["site_contract_sha256"],
            "database_sha256": row["database_sha256"],
            "initial_stage": first_stage,
            "next_unresolved_gate": (
                gate if stage == "PENDING"
                else "FINAL_SOURCE_TARGET_PARITY_AND_RECOVERY_POINT"),
            "source_target_row_parity": "NOT_PROVEN",
            "final_sql_effects": "NOT_PROVEN",
            "original_db_data_preserved": "NOT_RECHECKED_BY_THIS_REPORT",
            "final_recovery_point": "NOT_VERIFIED",
        })
    connection_status = www3.get("status", "ABSENT_NOT_PROVEN")
    require(type(verify_original_markers) is bool,
            "CHAIN_DB_MARKER_PROBE_MODE_INVALID")
    local_markers = (
        original_db_local_marker_evidence(
            report["final_sync_plan"], parent, child, tail,
            root=root, private_owner=private_owner)
        if verify_original_markers else None
    )
    return {
        "schema": "P07_CHAIN_ORIGINAL_DATABASE_READINESS_V1",
        "status": "THREE_DATABASES_BLOCKED_FINAL_MIGRATION",
        "site_count": 17,
        "original_task_count": 3,
        "staged_site_count": report["staged_count"],
        "pending_site_count": report["pending_count"],
        "database_count": 3,
        "plan_sha256": report["final_sync_plan"]["plan_sha256"],
        "database_scope_sha256": database_scope["scope_sha256"],
        "databases": statuses,
        "local_original_marker_readback": local_markers,
        "www3_connection_status": connection_status,
        "www3_connection_reused_only": True,
        "www3_connection_or_import_retried": False,
        "source_target_final_parity_verified": False,
        "database_shadow_batch_execution_allowed": False,
        "source_freeze_allowed": False,
        "target_runtime_activation_allowed": False,
        "cutover_allowed": False,
        "database_writes_performed": False,
        "site_config_writes_performed": False,
        "migration_state_writes_performed": False,
        "source_server_contacted": False,
    }
