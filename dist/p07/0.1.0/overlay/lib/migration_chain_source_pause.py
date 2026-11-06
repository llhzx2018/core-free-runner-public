"""Guarded, single-owner-of-control source pause for three P07 migration tasks.

The old server has exactly ONE web service; parent/child/tail are overlapping
historical states, not independent owners of a freeze. This component uses
their locked 17-site contract and one fresh source recovery ID. It is a
pre-cutover building block, NOT a full migration or DB write-lock proof.

Only call stage_and_pause_source in a separately authorized outage window.
It writes an independent private target journal before ANY source transport,
and old-source helper stages its own durable reverse Cron/PM2/Nginx records.
Neither successful pause nor an old-server SQL export proves quiescence of
unknown external data producers, MariaDB events or third-party services.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

import migration_chain_final_saga as saga
import migration_chain_private_file_stage as files
import migration_three_site_window as window
import server_migration as legacy

SCHEMA = "P07_17_SITE_SINGLE_SOURCE_PAUSE_V1"
ROOT_NAME = "p07-single-17-site-source-pause-v1"
PAUSE_CONFIRM = "PAUSE_ALL_17_SOURCE_SITES_NO_DNS"
RESTORE_CONFIRM = "RESTORE_ALL_17_SOURCE_SITES_PRE_DNS"
_ID_PREFIX = "pull-p07-17sites-"


class SourcePauseBlocked(RuntimeError):
    pass


def need(ok: bool, reason: str) -> None:
    if not ok:
        raise SourcePauseBlocked(reason)


def _control(
    plan: Mapping[str, Any],
    originals: tuple[Mapping[str, Any], ...],
    target_identity: str,
) -> tuple[str, dict, str]:
    try:
        files._identity(plan, originals, target_identity)
        report = window.assemble_seventeen_site_source_maintenance(
            plan, originals)
    except (files.WarmStageBlocked, window.WindowBlocked, saga.SagaBlocked):
        raise SourcePauseBlocked("PAUSE_ORIGINAL_17_SITE_OWNER_SCOPE_INVALID") from None
    need(report.get("status") == "CONTROL_ASSEMBLED_EXECUTION_BLOCKED"
         and report.get("site_count") == 17
         and report.get("original_task_count") == 3
         and report.get("source_pause_allowed") is False
         and report.get("cutover_allowed") is False,
         "PAUSE_ORIGINAL_17_SITE_CONTROL_INVALID")
    mid = _ID_PREFIX + plan["plan_sha256"][:32]
    need(legacy.SAFE_ID_RE.fullmatch(mid) is not None,
         "PAUSE_RECOVERY_ID_UNSAFE")
    control = dict(report["control"])
    control["migration_id"] = mid
    payload = json.dumps(control, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return mid, control, hashlib.sha256(payload).hexdigest()


def _private(plan: Mapping[str, Any], root: Path) -> Path:
    try:
        ancestor = files._private_parent(plan, root)
    except files.WarmStageBlocked:
        raise SourcePauseBlocked("PAUSE_PRIVATE_ORIGINAL_PARENT_UNSAFE") from None
    return ancestor.parent / ROOT_NAME


def _read_journal(path: Path, *, plan_sha: str, target_sha: str) -> dict:
    try:
        data = saga._read_receipt(path, expected_schema=SCHEMA)
    except saga.SagaBlocked:
        raise SourcePauseBlocked("PAUSE_RECOVERY_RECEIPT_UNAVAILABLE") from None
    need(data.get("plan_sha256") == plan_sha
         and data.get("target_identity_sha256") == target_sha
         and data.get("cutover_allowed") is False
         and data.get("site_count") == 17
         and data.get("source_deleted") is False
         and data.get("dns_changed") is False,
         "PAUSE_RECOVERY_RECEIPT_DRIFT")
    return data


def source_pause_preview(
    plan: Mapping[str, Any], originals: tuple[Mapping[str, Any], ...],
    *, root: Path, target_identity: str,
) -> dict[str, Any]:
    """Pure owner-control preflight: no local state write, source SSH or pause."""
    mid, control, digest = _control(plan, originals, target_identity)
    private = _private(plan, root)
    need(not os.path.lexists(private),
         "PAUSE_PREVIOUS_ATTEMPT_REQUIRES_RECONCILIATION")
    return {
        "schema": SCHEMA, "status": "SOURCE_PAUSE_PREVIEW_ONLY",
        "source_recovery_id": mid,
        "site_count": 17, "original_task_count": 3,
        "system_cron_count": len(control["pending_system_cron"]),
        "user_cron_count": len(control["pending_user_cron"]),
        "pm2_count": len(control["pending_pm2"]),
        "control_sha256": digest,
        "source_runtime_paused": False,
        "source_business_writes_paused": False,
        "source_final_database_parity": False,
        "cutover_allowed": False, "writes_performed": False,
    }


def stage_and_pause_source(
    plan: Mapping[str, Any], originals: tuple[Mapping[str, Any], ...],
    *, root: Path, target_identity: str,
    authorize_source_outage: bool = False,
    confirmation: str = "",
) -> dict[str, Any]:
    """ONE fresh remote freeze, never three. Private intent before any SSH write.

    Never automatically replay on failure; the remote helper self-recovers
    Cron/PM2/Nginx on error and retains source recovery evidence for operator.
    """
    need(authorize_source_outage is True and confirmation == PAUSE_CONFIRM,
         "PAUSE_SEPARATE_ALL_17_OUTAGE_AUTHORIZATION_REQUIRED")
    mid, control, control_digest = _control(plan, originals, target_identity)
    private = _private(plan, root)
    need(not os.path.lexists(private), "PAUSE_PREVIOUS_ATTEMPT_RETAINED")
    import server_migration_pull as pull
    need(pull.target_identity() == target_identity,
         "PAUSE_LOCAL_CP2_IDENTITY_CHANGED")
    source = originals[0]["source"]

    private.mkdir(mode=0o700)
    journal = private / "journal.json"
    record = {
        "schema": SCHEMA,
        "status": "INTENT_RECORDED",
        "site_count": 17, "original_task_count": 3,
        "plan_sha256": plan["plan_sha256"],
        "target_identity_sha256": plan["target_identity_sha256"],
        "control_sha256": control_digest,
        "source_recovery_id": mid,
        "source_runtime_paused": False,
        "source_business_writes_paused": False,
        "source_final_database_parity": False,
        "source_deleted": False, "dns_changed": False,
        "cutover_allowed": False,
    }
    legacy.atomic_private_json(journal, record)
    # Persist exact bounded control alongside the intent before stage_source.
    local_control = private / "control.json"
    legacy.atomic_private_json(local_control, control)

    try:
        status = pull.source_nginx_status(source)
        need(status.get("site_nginx_running") is True,
             "PAUSE_SOURCE_NGINX_NOT_VERIFIED_ACTIVE")
        record["status"] = "SOURCE_RUNTIME_STAGING_INTENT"
        legacy.atomic_private_json(journal, record)
        runtime = pull.stage_source_runtime(source, mid)
        need(runtime == f"/var/lib/vf-server-ops/pull-source/{mid}/runtime",
             "PAUSE_SOURCE_RUNTIME_IDENTITY_UNEXPECTED")
        need(pull.source_export_helper_matches_current(source, runtime) is True,
             "PAUSE_SOURCE_RUNTIME_HELPER_INTEGRITY_FAILED")
        remote_control = (
            f"/var/lib/vf-server-ops/pull-source/{mid}/freeze-control.json")
        pull.push_control_file(source, local_control, remote_control)
        record["status"] = "SOURCE_FREEZE_CALL_INTENT"
        legacy.atomic_private_json(journal, record)
        # Source helper independently checks fresh recovery journal and exact
        # transfer bytes. Its built-in failure path attempts source restore.
        response = pull.source_python(
            source, runtime,
            "_source-freeze", "--migration-id", mid,
            "--control", remote_control,
            "--require-fresh", "--expected-site-count", "17",
            "--expected-control-sha256",
            hashlib.sha256(local_control.read_bytes()).hexdigest(),
            timeout=900, check=False,
        )
        need(response.returncode == 0,
             "PAUSE_REMOTE_FREEZE_FAILED_RECOVERY_REQUIRED")
        try:
            receipt = json.loads(response.stdout)
        except (TypeError, ValueError):
            raise SourcePauseBlocked(
                "PAUSE_REMOTE_FREEZE_RECEIPT_UNVERIFIED"
            ) from None
        need(receipt.get("status") == "SOURCE_FROZEN"
             and receipt.get("migration_id") == mid
             and receipt.get("dns_changed") is False
             and receipt.get("source_deleted") is False,
             "PAUSE_REMOTE_FREEZE_RECEIPT_UNVERIFIED")
        record["status"] = "SOURCE_RUNTIME_PAUSED_DB_WRITE_FENCE_NOT_PROVEN"
        record["source_runtime_paused"] = True
        legacy.atomic_private_json(journal, record)
    except Exception:
        if record["status"] != "SOURCE_RUNTIME_PAUSED_DB_WRITE_FENCE_NOT_PROVEN":
            record["status"] = "SOURCE_PAUSE_RESULT_UNCERTAIN_RECOVERY_REQUIRED"
            legacy.atomic_private_json(journal, record)
        # Do not blindly resume after a timeout. The source journal records
        # the exact last safe action; manual route/activation guards apply.
        raise SourcePauseBlocked(
            "PAUSE_ONE_SHOT_SOURCE_RESULT_RECONCILIATION_REQUIRED"
        ) from None

    return {
        "status": record["status"],
        "source_recovery_id": mid, "site_count": 17,
        "source_runtime_paused": True,
        "source_business_writes_paused": False,
        "source_final_database_parity": False,
        "target_runtime_activated": False,
        "cutover_allowed": False,
    }


def restore_paused_source_pre_dns(
    plan: Mapping[str, Any], originals: tuple[Mapping[str, Any], ...],
    *, root: Path, target_identity: str,
    confirmation: str = "",
    verified_old_dns_route: bool = False,
) -> dict[str, Any]:
    """Explicit pre-DNS reversal; fail closed if target could be activated."""
    need(confirmation == RESTORE_CONFIRM,
         "PAUSE_RESTORE_EXPLICIT_AUTHORIZATION_REQUIRED")
    need(verified_old_dns_route is True,
         "PAUSE_RESTORE_OLD_DNS_ROUTE_NOT_VERIFIED")
    mid, _control_data, digest = _control(plan, originals, target_identity)
    private = _private(plan, root)
    receipt = _read_journal(
        private / "journal.json", plan_sha=plan["plan_sha256"],
        target_sha=plan["target_identity_sha256"])
    need(receipt.get("status")
         == "SOURCE_RUNTIME_PAUSED_DB_WRITE_FENCE_NOT_PROVEN"
         and receipt.get("source_recovery_id") == mid
         and receipt.get("control_sha256") == digest
         and receipt.get("source_runtime_paused") is True,
         "PAUSE_RESTORE_RECOVERY_NOT_READY")
    # A separate call into a target-environment activation guard must be made
    # before this primitive. Even known-original "target_runtime_activated"
    # can be stale, so this only supports original-state disqualification.
    need(all(x.get("target_runtime_activated") is False
             and x.get("dns_changed_by_p07") is False
             and x.get("source_runtime_frozen") is False
             for x in originals),
         "PAUSE_RESTORE_ORIGINAL_RUNTIME_DRIFT")
    # No executable restore in a standalone source-pause module: actual
    # target runtime shutdown and fresh public-DNS proof are independent
    # authoritative facts. Returning a request avoids split-brain risk.
    return {
        "status": "RESTORE_REQUEST_PREPARED_EXECUTION_BLOCKED",
        "site_count": 17,
        "source_recovery_id": mid,
        "target_runtime_deactivation_verified": False,
        "dns_manual_route_verified_by_executor": False,
        "source_restore_performed": False,
        "cutover_allowed": False,
    }
