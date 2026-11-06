"""All-site final database config-switch transaction, isolated from cutover CLI.

No existing database is modified or deleted. Every selected site must be
prepared and every DB-bearing site must have a separately verified shadow.
One failed app mapping forces a reverse-order rollback across all sites.
A durable private receipt permits explicit recovery after a process crash.

NO public CLI, DNS operation, source freeze, runtime activation, finalization
or cutover permission is exposed by this module. The source migration's
FINAL_MYSQL_SAFE_REPLACEMENT_NOT_IMPLEMENTED gate stays in effect.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any

import app_config
import migration_final_db_shadow as shadow
import server_migration as legacy


class BatchBlocked(RuntimeError):
    pass


def _deny(reason: str) -> None:
    raise BatchBlocked(reason)


def _safe_scope(
    state: dict[str, Any], target_identity: str, expected_site_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    if (
        type(expected_site_count) is not int or expected_site_count < 1
        or expected_site_count > 100
    ):
        _deny("FINAL_SHADOW_BATCH_SITE_COUNT_INVALID")
    if (
        state.get("status") != "CUTOVER_RUNNING"
        or state.get("source_runtime_frozen") is not True
        or state.get("target_runtime_activated") is True
        or state.get("cutover_prohibited") is True
        or state.get("partial_parent_migration_id")
        or state.get("dns_changed_by_p07") is True
        or state.get("source_delete_allowed") is True
        or state.get("existing_target_overwrite_allowed") is True
        or not target_identity
        or target_identity != state.get("target_server_identity")
    ):
        _deny("FINAL_SHADOW_BATCH_BOUNDARY_UNVERIFIED")
    mid = str(state.get("migration_id", ""))
    if not legacy.SAFE_ID_RE.fullmatch(mid):
        _deny("FINAL_SHADOW_BATCH_MIGRATION_ID_INVALID")
    rows = state.get("sites")
    if not isinstance(rows, list) or len(rows) != expected_site_count:
        _deny("FINAL_SHADOW_BATCH_SITE_SCOPE_CHANGED")
    domains: set[str] = set()
    databases: set[str] = set()
    selected: list[dict[str, Any]] = []
    fingerprint_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            _deny("FINAL_SHADOW_BATCH_SITE_SCOPE_INVALID")
        domain = row.get("domain")
        raw = row.get("mysql_databases")
        if (
            not isinstance(domain, str) or not domain
            or domain in domains
            or row.get("stage_status") != "PULLED_STAGED"
            or not isinstance(raw, list) or len(raw) > 1
        ):
            _deny("FINAL_SHADOW_BATCH_SITE_UNPREPARED")
        domains.add(domain)
        if raw:
            if not isinstance(raw[0], str) or not raw[0] or raw[0] in databases:
                _deny("FINAL_SHADOW_BATCH_DATABASE_SCOPE_AMBIGUOUS")
            databases.add(raw[0])
            selected.append(row)
        if raw:
            try:
                original_owner = shadow.original_database_owner(state, row)
            except shadow.ShadowBlocked:
                _deny("FINAL_SHADOW_BATCH_ORIGINAL_OWNER_UNVERIFIED")
        else:
            original_owner = None
        fingerprint_rows.append({
            "domain": domain,
            "database": raw,
            "original_db_migration_owner": original_owner,
            "site_root": row.get("site_root"),
            "stage_status": row.get("stage_status"),
        })
    fingerprint = hashlib.sha256(json.dumps(
        fingerprint_rows, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")).hexdigest()
    return rows, selected, fingerprint


def _receipt_path(mid: str) -> Path:
    return legacy.state_dir(mid) / "final-shadow-batch.json"


def _read_receipt(path: Path) -> dict[str, Any] | None:
    if os.path.lexists(path) and (path.is_symlink() or not path.is_file()):
        _deny("FINAL_SHADOW_BATCH_RECEIPT_UNSAFE")
    if not path.exists():
        return None
    try:
        if path.stat().st_size > 1024 * 1024:
            _deny("FINAL_SHADOW_BATCH_RECEIPT_UNBOUNDED")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        _deny("FINAL_SHADOW_BATCH_RECEIPT_UNREADABLE")
    if not isinstance(payload, dict):
        _deny("FINAL_SHADOW_BATCH_RECEIPT_INVALID")
    return payload


def _locked_receipt(mid: str):
    """Take an exclusive process lock before inspecting or modifying a batch."""
    root = legacy.state_dir(mid)
    if root.is_symlink() or not root.is_dir():
        _deny("FINAL_SHADOW_BATCH_STATE_ROOT_UNSAFE")
    path = root / "final-shadow-batch.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            _deny("FINAL_SHADOW_BATCH_LOCK_UNSAFE")
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError:
        _deny("FINAL_SHADOW_BATCH_LOCK_UNAVAILABLE")
    return fd


def _read_shadow_row(
    state: dict[str, Any], site: dict[str, Any], target_identity: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        receipt, _marker, owned = shadow._read_verified_shadow(
            state, site, target_identity
        )
        return receipt, owned
    except (shadow.ShadowBlocked, ValueError, OSError):
        _deny("FINAL_SHADOW_BATCH_SITE_PROOF_INVALID")


def _original_mapping_verified(
    site: dict[str, Any], receipt: dict[str, Any], owned: dict[str, Any],
) -> bool:
    return app_config.verify_rewritten_application_database_config(
        Path(str(site["site_root"])),
        str(receipt["original_database"]),
        str(owned["username"]), str(owned["password"]),
    )


def _shadow_mapping_verified(
    site: dict[str, Any], receipt: dict[str, Any],
) -> bool:
    return app_config.verify_rewritten_application_database_config(
        Path(str(site["site_root"])),
        str(receipt["shadow_database"]),
        str(receipt["shadow_username"]), str(receipt["shadow_password"]),
    )


def _rollback_rows(
    state: dict[str, Any], selected: list[dict[str, Any]], identity: str,
) -> int:
    failures = 0
    # A process may crash after a config switch and before the batch receipt
    # records the row. Re-read every individual private marker, not the count.
    for site in reversed(selected):
        try:
            receipt, owned = _read_shadow_row(state, site, identity)
            status = receipt.get("status")
            if status in (
                "APP_SWITCH_PENDING",
                "APP_SWITCH_VERIFIED_NOT_ACTIVATED",
                "APP_SWITCH_ROLLED_BACK",
            ):
                shadow.rollback_shadow_application(
                    state, site, actual_target_identity=identity
                )
                receipt, owned = _read_shadow_row(state, site, identity)
            elif status != "STAGED_VERIFIED_NOT_ACTIVATED":
                raise shadow.ShadowBlocked("UNKNOWN_ROW_STATUS")
            if not _original_mapping_verified(site, receipt, owned):
                raise shadow.ShadowBlocked("ORIGINAL_MAPPING_UNVERIFIED")
        except (BatchBlocked, shadow.ShadowBlocked, OSError, ValueError, KeyError):
            failures += 1
    return failures


def _validate_batch_receipt(
    receipt: dict[str, Any], state: dict[str, Any],
    selected: list[dict[str, Any]], identity: str, fingerprint: str,
) -> None:
    if any((
        receipt.get("schema") != "vf-server-ops.final-shadow-batch.v1",
        receipt.get("migration_id") != state.get("migration_id"),
        receipt.get("target_server_identity") != identity,
        receipt.get("inventory_sha256") != fingerprint,
        receipt.get("db_domains") != [str(x["domain"]) for x in selected],
    )):
        _deny("FINAL_SHADOW_BATCH_RECEIPT_SCOPE_CHANGED")


def switch_verified_shadow_batch(
    state: dict[str, Any],
    *, actual_target_identity: str, expected_site_count: int,
) -> dict[str, Any]:
    """Fail-closed all-site switch; never authorizes target runtime or DNS."""
    rows, selected, fingerprint = _safe_scope(
        state, actual_target_identity, expected_site_count
    )
    if not selected:
        _deny("FINAL_SHADOW_BATCH_HAS_NO_DATABASES")
    mid = str(state["migration_id"])
    fd = _locked_receipt(mid)
    try:
        path = _receipt_path(mid)
        if _read_receipt(path) is not None:
            _deny("FINAL_SHADOW_BATCH_PREVIOUS_ATTEMPT_RECOVERY_REQUIRED")
        # Preflight all sites before switching even the first one.
        shadow_names: set[str] = set()
        for site in selected:
            receipt, owned = _read_shadow_row(state, site, actual_target_identity)
            if receipt.get("status") != "STAGED_VERIFIED_NOT_ACTIVATED":
                _deny("FINAL_SHADOW_BATCH_UNVERIFIED_SHADOW")
            if receipt["shadow_database"] in shadow_names:
                _deny("FINAL_SHADOW_BATCH_SHADOW_COLLISION")
            shadow_names.add(receipt["shadow_database"])
            root = Path(str(site["site_root"]))
            shadow._exclusive_application_config(root)
            if not _original_mapping_verified(site, receipt, owned):
                _deny("FINAL_SHADOW_BATCH_ORIGINAL_MAPPING_DRIFT")
        record: dict[str, Any] = {
            "schema": "vf-server-ops.final-shadow-batch.v1",
            "migration_id": mid, "target_server_identity": actual_target_identity,
            "inventory_sha256": fingerprint,
            "site_count": len(rows),
            "db_domains": [str(x["domain"]) for x in selected],
            "status": "SWITCHING",
            "last_committed_domain_count": 0,
            "cutover_allowed": False,
        }
        legacy.atomic_private_json(path, record)
        try:
            for site in selected:
                shadow.activate_verified_shadow(
                    state, site, actual_target_identity=actual_target_identity
                )
                record["last_committed_domain_count"] += 1
                legacy.atomic_private_json(path, record)
            # Even a successful per-site method is not proof of all-site
            # consistency until every receipt and app mapping is re-read.
            for site in selected:
                receipt, _owned = _read_shadow_row(
                    state, site, actual_target_identity
                )
                if (
                    receipt.get("status") != "APP_SWITCH_VERIFIED_NOT_ACTIVATED"
                    or not _shadow_mapping_verified(site, receipt)
                ):
                    _deny("FINAL_SHADOW_BATCH_POST_SWITCH_DRIFT")
            record["status"] = "SWITCHED_VERIFIED_NOT_ACTIVATED"
            legacy.atomic_private_json(path, record)
            return {
                "status": "SWITCHED_VERIFIED_NOT_ACTIVATED",
                "site_count": len(rows), "database_count": len(selected),
                "cutover_allowed": False, "runtime_activated": False,
                "original_databases_retained": True,
            }
        except Exception:
            failed = _rollback_rows(state, selected, actual_target_identity)
            record["status"] = "ROLLBACK_PARTIAL" if failed else "ROLLED_BACK"
            record["rollback_failed_site_count"] = failed
            legacy.atomic_private_json(path, record)
            _deny(
                "FINAL_SHADOW_BATCH_ROLLBACK_PARTIAL"
                if failed else "FINAL_SHADOW_BATCH_FAILED_ROLLED_BACK"
            )
    finally:
        os.close(fd)


def rollback_verified_shadow_batch(
    state: dict[str, Any],
    *, actual_target_identity: str, expected_site_count: int,
) -> dict[str, Any]:
    """Explicitly resume rollback using row receipts, including crash gaps."""
    rows, selected, fingerprint = _safe_scope(
        state, actual_target_identity, expected_site_count
    )
    if not selected:
        _deny("FINAL_SHADOW_BATCH_HAS_NO_DATABASES")
    mid = str(state["migration_id"])
    fd = _locked_receipt(mid)
    try:
        path = _receipt_path(mid)
        receipt = _read_receipt(path)
        if receipt is None:
            _deny("FINAL_SHADOW_BATCH_NO_RECOVERY_RECEIPT")
        _validate_batch_receipt(
            receipt, state, selected, actual_target_identity, fingerprint
        )
        if receipt.get("status") not in (
            "SWITCHING", "SWITCHED_VERIFIED_NOT_ACTIVATED",
            "ROLLED_BACK", "ROLLBACK_PARTIAL",
        ):
            _deny("FINAL_SHADOW_BATCH_RECEIPT_STATUS_UNPROVEN")
        failed = _rollback_rows(state, selected, actual_target_identity)
        receipt["status"] = "ROLLBACK_PARTIAL" if failed else "ROLLED_BACK"
        receipt["rollback_failed_site_count"] = failed
        legacy.atomic_private_json(path, receipt)
        if failed:
            _deny("FINAL_SHADOW_BATCH_ROLLBACK_PARTIAL")
        return {
            "status": "ROLLED_BACK", "site_count": len(rows),
            "database_count": len(selected), "cutover_allowed": False,
            "original_databases_retained": True,
            "shadow_databases_retained": True,
        }
    finally:
        os.close(fd)
