"""P07 original-3-owner Shadow app mapping transaction; NEVER a cutover.

Uses the *existing* per-owner verified CloudPanel shadow and rollback
primitives. Does not manufacture CUTOVER_RUNNING, fake a source freeze,
import SQL, delete databases, activate target services or change DNS.

The historical three tasks remain PREPARE_FAILED/PREPARED today: they will
FAIL these real migration preconditions. Isolated tests create explicit
synthetic per-owner CUTOVER_RUNNING fixtures only in temporary directories.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any, Mapping

import app_config
import migration_chain_consolidation as consolidate
import migration_chain_final_saga as saga
import migration_final_db_shadow as shadow
import migration_three_site_window as window
import server_migration as legacy
import server_migration_pull as pull

SCHEMA = "P07_ORIGINAL_THREE_OWNER_SHADOW_MAPPING_TRANSACTION_V1"
NAME = "original-three-owner-shadow-transaction-v1.json"
LOCK = "original-three-owner-shadow-transaction-v1.lock"
SWITCH_CONFIRM = "SWITCH_VERIFIED_THREE_ORIGINAL_SHADOW_CONFIGS_PRE_DNS"
RESTORE_CONFIRM = "RESTORE_THREE_ORIGINAL_DB_CONFIGS_PRE_DNS"


class ThreeOwnerShadowBlocked(RuntimeError):
    pass


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise ThreeOwnerShadowBlocked(code)


def _scope(plan: Mapping[str, Any],
           originals: tuple[Mapping[str, Any], ...],
           target_identity: str
           ) -> tuple[list[tuple[dict, dict, dict]], str]:
    """Bind all 17 site contracts, exactly three original DB owners."""
    try:
        saga.validate_locked_plan(plan)
    except saga.SagaBlocked:
        raise ThreeOwnerShadowBlocked("THREE_SHADOW_LOCKED_PLAN_INVALID") from None
    _need(type(originals) is tuple and len(originals) == 3
          and all(type(x) is dict for x in originals),
          "THREE_SHADOW_ORIGINAL_THREE_TASKS_REQUIRED")
    tasks = {s.get("migration_id"): s for s in originals}
    _need(len(tasks) == 3 and
          set(tasks) == {s["owner"] for s in plan["steps"][:17]},
          "THREE_SHADOW_ORIGINAL_OWNER_SET_CHANGED")
    _need(type(target_identity) is str and target_identity
          and hashlib.sha256(target_identity.encode()).hexdigest()
          == plan["target_identity_sha256"],
          "THREE_SHADOW_CP2_IDENTITY_CHANGED")
    first_source = originals[0].get("source")
    _need(isinstance(first_source, dict),
          "THREE_SHADOW_SOURCE_IDENTITY_MISSING")
    for state in originals:
        try:
            source = consolidate._original_source_identity(state)
        except consolidate.ConsolidationBlocked:
            raise ThreeOwnerShadowBlocked(
                "THREE_SHADOW_SOURCE_PROVENANCE_INVALID") from None
        _need(hashlib.sha256(saga._encoded(source)).hexdigest()
              == plan["source_identity_sha256"]
              and state.get("source") == first_source
              and state.get("target_server_identity") == target_identity,
              "THREE_SHADOW_SERVER_PROVENANCE_CHANGED")
        # The original single-owner Shadow primitive requires all of these.
        # Never promote historic PREPARE_FAILED, PREPARED or partial-parent
        # states into CUTOVER_RUNNING by changing flags in this module.
        _need(state.get("status") == "CUTOVER_RUNNING"
              and state.get("source_runtime_frozen") is True
              and state.get("target_runtime_activated") is False
              and state.get("dns_changed_by_p07") is False
              and state.get("source_delete_allowed") is False
              and state.get("existing_target_overwrite_allowed") is False
              and state.get("cutover_prohibited") is not True
              and not state.get("partial_parent_migration_id"),
              "THREE_SHADOW_ORIGINAL_CUTOVER_GATE_NOT_MET")
    expected = set(window.OWNER_SITES)
    selected: list[tuple[dict, dict, dict]] = []
    names, databases, owners = set(), set(), set()
    observed = []
    for step in plan["steps"][:17]:
        state = tasks[step["owner"]]
        index = step["index"]
        sites = state.get("sites")
        _need(type(sites) is list and index < len(sites)
              and type(sites[index]) is dict,
              "THREE_SHADOW_ORIGINAL_SITE_MISSING")
        site = sites[index]
        contract = hashlib.sha256(
            saga._encoded(consolidate._site_contract(site))).hexdigest()
        domain = site.get("domain")
        dbs = site.get("mysql_databases")
        _need(domain == step["domain"]
              and contract == step["site_contract_sha256"]
              and domain not in names
              and site.get("stage_status") == "PULLED_STAGED"
              and type(dbs) is list and len(dbs) <= 1,
              "THREE_SHADOW_SITE_CONTRACT_OR_STAGE_DRIFT")
        names.add(domain)
        observed.append((
            domain, step["owner"], index,
            site["stage_status"], contract,
        ))
        if dbs:
            _need(domain in expected
                  and step["owner"] not in owners
                  and type(dbs[0]) is str and dbs[0]
                  and dbs[0] not in databases,
                  "THREE_SHADOW_DATABASE_OUTSIDE_THREE_ORIGINAL")
            owners.add(step["owner"])
            databases.add(dbs[0])
            selected.append((state, site, step))
    _need(len(names) == 17 and
          {site["domain"] for _state, site, _step in selected} == expected
          and len(owners) == 3 and len(databases) == 3
          and plan["pending_domains"] == [],
          "THREE_SHADOW_DATABASE_COVERAGE_OR_STAGING_CHANGED")
    observed_scope = hashlib.sha256(saga._encoded({
        "sites": observed,
        "source": plan["source_identity_sha256"],
        "target": plan["target_identity_sha256"],
    })).hexdigest()
    _need(observed_scope == plan["scope_sha256"],
          "THREE_SHADOW_ORIGINAL_SITE_SCOPE_DIGEST_CHANGED")
    return selected, plan["plan_sha256"]


def _directory(parent_mid: str) -> Path:
    _need(isinstance(parent_mid, str)
          and legacy.SAFE_ID_RE.fullmatch(parent_mid) is not None,
          "THREE_SHADOW_PARENT_MIGRATION_ID_INVALID")
    root = legacy.STATE_ROOT / parent_mid
    try:
        info = root.lstat()
        _need(stat.S_ISDIR(info.st_mode)
              and info.st_uid == os.geteuid()
              and not stat.S_IMODE(info.st_mode) & 0o077,
              "THREE_SHADOW_PARENT_DIRECTORY_UNSAFE")
    except OSError:
        raise ThreeOwnerShadowBlocked(
            "THREE_SHADOW_PARENT_DIRECTORY_UNAVAILABLE") from None
    return root


def _locked(root: Path) -> int:
    p = root / LOCK
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(p, flags, 0o600)
        info = os.fstat(fd)
        _need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
              and info.st_uid == os.geteuid(),
              "THREE_SHADOW_RECOVERY_LOCK_UNSAFE")
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd
    except OSError:
        raise ThreeOwnerShadowBlocked(
            "THREE_SHADOW_RECOVERY_LOCK_UNAVAILABLE") from None


def _fingerprint(plan_sha: str,
                 selected: list[tuple[dict, dict, dict]],
                 target_identity: str) -> str:
    rows = [
        [site["domain"], state["migration_id"],
         site["mysql_databases"][0], step["site_contract_sha256"]]
        for state, site, step in selected
    ]
    return hashlib.sha256(saga._encoded({
        "plan": plan_sha, "target": target_identity, "rows": rows,
    })).hexdigest()


def _receipt(root: Path, expected_sha: str, target_identity: str,
             domains: list[str]) -> dict[str, Any] | None:
    p = root / NAME
    if not os.path.lexists(p):
        return None
    try:
        data = saga._read_receipt(p, expected_schema=SCHEMA)
    except saga.SagaBlocked:
        raise ThreeOwnerShadowBlocked(
            "THREE_SHADOW_PRIVATE_RECEIPT_UNSAFE") from None
    _need(data.get("inventory_sha256") == expected_sha
          and data.get("target_identity_sha256")
          == hashlib.sha256(target_identity.encode()).hexdigest()
          and data.get("domains") == domains
          and data.get("old_databases_retained") is True
          and data.get("shadow_databases_retained") is True
          and data.get("target_runtime_activated") is False
          and data.get("dns_changed") is False
          and data.get("cutover_allowed") is False
          and data.get("schema") == SCHEMA,
          "THREE_SHADOW_PRIVATE_RECEIPT_SCOPE_DRIFT")
    return data


def _require_pre_dns_source_route(originals: tuple[dict, dict, dict]) -> None:
    """Read-only guard against OWNER manual DNS moves not recorded by P07.

    Reuse the conservative public-route validator for every original owner
    before ANY cross-owner application mapping write. The P07-managed DNS
    flag alone is not actual public-route evidence.
    """
    try:
        for original in originals:
            pull.require_old_source_route_before_manual_rollback(original)
    except pull.PullMigrationError:
        raise ThreeOwnerShadowBlocked(
            "THREE_SHADOW_MANUAL_DNS_ROUTE_UNVERIFIED") from None


def _preflight(selected: list[tuple[dict, dict, dict]], target_identity: str,
               *, fresh: bool) -> None:
    shadows, originals = set(), set()
    for state, site, _step in selected:
        try:
            proof, _marker, owner = shadow._read_verified_shadow(
                state, site, target_identity)
            if fresh and proof.get("status") != "STAGED_VERIFIED_NOT_ACTIVATED":
                raise shadow.ShadowBlocked("SHADOW_STAGING_NOT_READY")
            if proof.get("status") not in {
                "STAGED_VERIFIED_NOT_ACTIVATED",
                "APP_SWITCH_PENDING",
                "APP_SWITCH_VERIFIED_NOT_ACTIVATED",
                "APP_SWITCH_ROLLED_BACK",
            }:
                raise shadow.ShadowBlocked("SHADOW_STAGING_STATUS_UNKNOWN")
            if not isinstance(proof.get("verification_mode"), str):
                raise shadow.ShadowBlocked("SHADOW_SOURCE_SQL_PROOF_INVALID")
            old, new = proof["original_database"], proof["shadow_database"]
            if old in originals or new in shadows or old in shadows or new in originals:
                raise shadow.ShadowBlocked("SHADOW_DATABASE_COLLISION")
            originals.add(old)
            shadows.add(new)
            root = Path(site["site_root"])
            shadow._exclusive_application_config(root)
            if fresh and not app_config.verify_rewritten_application_database_config(
                root, old, owner["username"], owner["password"]
            ):
                raise shadow.ShadowBlocked("SHADOW_ORIGINAL_CONFIG_DRIFT")
            if fresh:
                shadow.verify_staged_shadow_fresh(
                    state, site, actual_target_identity=target_identity)
        except (shadow.ShadowBlocked, ValueError, KeyError, OSError):
            raise ThreeOwnerShadowBlocked(
                "THREE_SHADOW_ORIGINAL_PRIVATE_OR_LIVE_PROOF_INVALID"
            ) from None


def _reverse(selected: list[tuple[dict, dict, dict]], identity: str) -> int:
    errors = 0
    # Read *every* owner-specific marker, not a mutable counter in the
    # cross-owner journal. Handles a crash between config write and journal.
    for state, site, _step in reversed(selected):
        try:
            marker, _private, old = shadow._read_verified_shadow(
                state, site, identity)
            status = marker["status"]
            if status in {
                "APP_SWITCH_PENDING",
                "APP_SWITCH_VERIFIED_NOT_ACTIVATED",
                "APP_SWITCH_ROLLED_BACK",
            }:
                shadow.rollback_shadow_application(
                    state, site, actual_target_identity=identity)
            elif status != "STAGED_VERIFIED_NOT_ACTIVATED":
                raise shadow.ShadowBlocked("SHADOW_UNKNOWN_RECOVERY_MARKER")
            if not app_config.verify_rewritten_application_database_config(
                Path(site["site_root"]),
                marker["original_database"], old["username"], old["password"]
            ):
                raise shadow.ShadowBlocked("SHADOW_ORIGINAL_MAPPING_UNVERIFIED")
        except Exception:
            errors += 1
    return errors


def switch_three_owner_shadows(
    plan: dict[str, Any],
    originals: tuple[dict, dict, dict], *,
    actual_target_identity: str,
    confirmation: str = "",
) -> dict[str, Any]:
    """One cross-owner config switch with automatic full reverse on failure.

    No shadow CREATE/IMPORT occurs here. They must have been staged under
    their *original* owner state and independently verified. A failure always
    leaves a durable recoverable journal and never promotes the target.
    """
    _need(confirmation == SWITCH_CONFIRM,
          "THREE_SHADOW_EXPLICIT_SWITCH_CONFIRMATION_REQUIRED")
    selected, plan_sha = _scope(plan, originals, actual_target_identity)
    _require_pre_dns_source_route(originals)
    root = _directory(originals[0]["migration_id"])
    fd = _locked(root)
    try:
        domains = [site["domain"] for _state, site, _step in selected]
        digest = _fingerprint(plan_sha, selected, actual_target_identity)
        _need(_receipt(root, digest, actual_target_identity, domains) is None,
              "THREE_SHADOW_PREVIOUS_ATTEMPT_RECONCILIATION_REQUIRED")
        _preflight(selected, actual_target_identity, fresh=True)
        record: dict[str, Any] = {
            "schema": SCHEMA,
            "status": "SWITCHING",
            "plan_sha256": plan_sha,
            "inventory_sha256": digest,
            "target_identity_sha256":
                hashlib.sha256(actual_target_identity.encode()).hexdigest(),
            "domains": domains,
            "original_owners": [state["migration_id"] for state, _site, _s in selected],
            "last_committed_count": 0,
            "old_databases_retained": True,
            "shadow_databases_retained": True,
            "target_runtime_activated": False,
            "dns_changed": False,
            "cutover_allowed": False,
        }
        legacy.atomic_private_json(root / NAME, record)
        try:
            for state, site, _step in selected:
                shadow.activate_verified_shadow(
                    state, site, actual_target_identity=actual_target_identity)
                record["last_committed_count"] += 1
                legacy.atomic_private_json(root / NAME, record)
            for state, site, _step in selected:
                marker, _p, _owned = shadow._read_verified_shadow(
                    state, site, actual_target_identity)
                if marker["status"] != "APP_SWITCH_VERIFIED_NOT_ACTIVATED":
                    raise shadow.ShadowBlocked("SHADOW_SWITCH_RECEIPT_DRIFT")
                if not app_config.verify_rewritten_application_database_config(
                    Path(site["site_root"]), marker["shadow_database"],
                    marker["shadow_username"], marker["shadow_password"]
                ):
                    raise shadow.ShadowBlocked("SHADOW_SWITCH_APP_CONFIG_DRIFT")
            record["status"] = "THREE_SHADOW_CONFIGS_SWITCHED_PRE_DNS"
            legacy.atomic_private_json(root / NAME, record)
            return {
                "status": record["status"], "original_database_count": 3,
                "original_owners_retained": True,
                "old_databases_retained": True, "shadow_databases_retained": True,
                "target_runtime_activated": False, "cutover_allowed": False,
            }
        except Exception:
            failures = _reverse(selected, actual_target_identity)
            record["status"] = (
                "ROLLBACK_PARTIAL_RECOVERY_REQUIRED" if failures
                else "THREE_SHADOW_CONFIGS_RESTORED"
            )
            record["rollback_failed_count"] = failures
            legacy.atomic_private_json(root / NAME, record)
            raise ThreeOwnerShadowBlocked(
                "THREE_SHADOW_PARTIAL_RECOVERY_REQUIRED" if failures
                else "THREE_SHADOW_SWITCH_FAILED_ALL_RESTORED"
            ) from None
    finally:
        os.close(fd)


def rollback_three_owner_shadows(
    plan: dict[str, Any],
    originals: tuple[dict, dict, dict], *,
    actual_target_identity: str,
    confirmation: str = "",
) -> dict[str, Any]:
    """Explicit resumed reversal, including SWITCHING crash-gap recovery."""
    _need(confirmation == RESTORE_CONFIRM,
          "THREE_SHADOW_EXPLICIT_ROLLBACK_CONFIRMATION_REQUIRED")
    selected, sha = _scope(plan, originals, actual_target_identity)
    _require_pre_dns_source_route(originals)
    root = _directory(originals[0]["migration_id"])
    fd = _locked(root)
    try:
        domains = [site["domain"] for _s, site, _step in selected]
        digest = _fingerprint(sha, selected, actual_target_identity)
        receipt = _receipt(root, digest, actual_target_identity, domains)
        _need(receipt is not None, "THREE_SHADOW_RECOVERY_RECEIPT_MISSING")
        _need(receipt["status"] in {
            "SWITCHING", "THREE_SHADOW_CONFIGS_SWITCHED_PRE_DNS",
            "ROLLBACK_PARTIAL_RECOVERY_REQUIRED",
            "THREE_SHADOW_CONFIGS_RESTORED",
        }, "THREE_SHADOW_RECOVERY_RECEIPT_STATUS_INVALID")
        failures = _reverse(selected, actual_target_identity)
        receipt["status"] = (
            "ROLLBACK_PARTIAL_RECOVERY_REQUIRED" if failures
            else "THREE_SHADOW_CONFIGS_RESTORED"
        )
        receipt["rollback_failed_count"] = failures
        legacy.atomic_private_json(root / NAME, receipt)
        _need(failures == 0, "THREE_SHADOW_PARTIAL_RECOVERY_REQUIRED")
        return {
            "status": receipt["status"], "original_database_count": 3,
            "old_databases_retained": True, "shadow_databases_retained": True,
            "original_application_mappings_restored": True,
            "target_runtime_activated": False,
            "cutover_allowed": False,
        }
    finally:
        os.close(fd)


def inspect_three_owner_shadows(
    plan: dict[str, Any],
    originals: tuple[dict, dict, dict], *,
    actual_target_identity: str,
) -> dict[str, Any]:
    """Read-only identity and private journal inspection; never touches DB."""
    selected, sha = _scope(plan, originals, actual_target_identity)
    root = _directory(originals[0]["migration_id"])
    domains = [site["domain"] for _s, site, _step in selected]
    digest = _fingerprint(sha, selected, actual_target_identity)
    record = _receipt(root, digest, actual_target_identity, domains)
    return {
        "status": record["status"] if record else "NO_ATTEMPT",
        "original_database_count": 3,
        "original_owner_count": 3,
        "verified_original_mappings": False,
        "cutover_allowed": False, "writes_performed": False,
    }
