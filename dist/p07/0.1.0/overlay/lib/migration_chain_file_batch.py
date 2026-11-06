"""P07 synthetic 17-owner file phase: all recovery points before one promotion.

This is an isolated 0700 fixture executor, not production migration, not a
database switch, and not an authorization to freeze old sites or change DNS.
The real three-owner SQL reconciliation and resource/cron gates remain locked.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import migration_chain_final_saga as saga

SCHEMA = "P07_CHAIN_17_SITE_FILE_BATCH_V1"
STEPS = 17
FILE = "seventeen-site-file-batch.json"


def _fixture(authorized: bool) -> None:
    saga.need(authorized is True and
              os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
              "CHAIN_FILE_BATCH_REAL_EXECUTION_NOT_WIRED")


def _steps(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    saga.validate_locked_plan(plan)
    rows = plan["steps"][:STEPS]
    saga.need(len(rows) == STEPS and all(
        x.get("phase") == "SITE_FILES" for x in rows
    ), "CHAIN_FILE_BATCH_SITE_SCOPE_CHANGED")
    return rows


def _journal(plan: Mapping[str, Any], directory: Path) -> dict[str, Any]:
    current = saga._read_receipt(
        directory / FILE, expected_schema=SCHEMA)
    saga.need(
        current.get("plan_sha256") == plan["plan_sha256"] and
        current.get("scope_sha256") == plan["scope_sha256"] and
        current.get("synthetic_only") is True and
        current.get("cutover_allowed") is False and
        current.get("source_frozen") is False and
        current.get("database_writes_performed") is False,
        "CHAIN_FILE_BATCH_JOURNAL_IDENTITY_CHANGED"
    )
    items = current.get("sites")
    expected = _steps(plan)
    saga.need(isinstance(items, list) and len(items) == STEPS,
              "CHAIN_FILE_BATCH_JOURNAL_COUNT_DRIFT")
    statuses = {"NOT_STARTED", "RECOVERY_INTENT", "RECOVERY_VERIFIED",
                "PROMOTION_INTENT", "PROMOTED_VERIFIED",
                "ROLLBACK_INTENT", "ROLLED_BACK_VERIFIED"}
    for a, b in zip(items, expected):
        saga.need(isinstance(a, dict) and
                  a.get("status") in statuses and
                  a.get("domain") == b["domain"] and
                  a.get("owner") == b["owner"] and
                  a.get("index") == b["index"] and
                  a.get("contract_sha256") == b["site_contract_sha256"] and
                  a.get("stage_sha256") and
                  a.get("target_before_sha256"),
                  "CHAIN_FILE_BATCH_JOURNAL_SITE_DRIFT")
    return current


def _transition(plan: Mapping[str, Any], directory: Path,
                index: int | None, expected: str, next_state: str,
                *, global_field: bool = False) -> None:
    fd = saga._lock(directory)
    try:
        path = directory / FILE
        journal = _journal(plan, directory)
        if global_field:
            saga.need(index is None and journal.get("status") == expected,
                      "CHAIN_FILE_BATCH_GLOBAL_STATE_CHANGED")
            journal["status"] = next_state
        else:
            saga.need(type(index) is int and 0 <= index < STEPS and
                      journal["sites"][index]["status"] == expected,
                      "CHAIN_FILE_BATCH_STEP_STATE_CHANGED")
            journal["sites"][index]["status"] = next_state
        saga._save(path, journal)
    finally:
        os.close(fd)


def _all_recovery_points(
    plan: Mapping[str, Any], directory: Path, *,
    promoted_count: int = 0,
) -> None:
    """All 17 independent snapshots checked before ANY target is rolled back."""
    journal = _journal(plan, directory)
    for index, (step, item) in enumerate(zip(_steps(plan), journal["sites"])):
        paths, _, stage_hash = saga._verify_synthetic_stage(
            plan, step, directory)
        saga.need(stage_hash == item["stage_sha256"],
                  "CHAIN_FILE_BATCH_STAGE_DRIFT")
        receipt = saga._verify_recovery_receipt(
            plan, step, paths, stage_hash)
        saga.need(receipt["target_before_sha256"] ==
                  item["target_before_sha256"],
                  "CHAIN_FILE_BATCH_RECOVERY_POINT_DRIFT")
        if index < promoted_count:
            saga.need(
                item["status"] == "PROMOTED_VERIFIED" and
                receipt.get("status") == "PROMOTED_NOT_CUTOVER" and
                not os.path.lexists(paths["failed"]) and
                not os.path.lexists(paths["next"]) and
                saga._synthetic_tree_hash(paths["held"]) ==
                    item["target_before_sha256"] and
                saga._synthetic_tree_hash(paths["target"]) ==
                    item["stage_sha256"],
                "CHAIN_FILE_BATCH_ROLLBACK_PREFLIGHT_DRIFT")
        else:
            saga.need(
                item["status"] == "RECOVERY_VERIFIED" and
                receipt.get("status") == "RECOVERY_POINT_VERIFIED" and
                saga._synthetic_tree_hash(paths["target"]) ==
                    item["target_before_sha256"],
                "CHAIN_FILE_BATCH_PREFLIGHT_DRIFT")


def _reverse_verified(plan: Mapping[str, Any], directory: Path,
                      *, expected_status: str,
                      promoted_count: int = STEPS) -> dict[str, Any]:
    journal = _journal(plan, directory)
    saga.need(journal.get("status") == expected_status,
              "CHAIN_FILE_BATCH_ROLLBACK_STATE_CHANGED")
    saga.need(type(promoted_count) is int and
              1 <= promoted_count <= STEPS,
              "CHAIN_FILE_BATCH_ROLLBACK_COUNT_INVALID")
    _all_recovery_points(plan, directory, promoted_count=promoted_count)
    _transition(plan, directory, None, expected_status,
                "ROLLBACK_IN_PROGRESS", global_field=True)
    for i in reversed(range(promoted_count)):
        step = plan["steps"][i]
        _transition(plan, directory, i, "PROMOTED_VERIFIED",
                    "ROLLBACK_INTENT")
        # If interrupted after reserving rollback intent, DO NOT retry;
        # preserve every target, original and recovery snapshot.
        try:
            result = saga.rollback_isolated_target_replacement(
                plan, step, directory, synthetic_authority=True)
            saga.need(result["status"] == "ROLLED_BACK_VERIFIED",
                      "CHAIN_FILE_BATCH_ROLLBACK_RESULT_INVALID")
        except Exception:
            _transition(plan, directory, None, "ROLLBACK_IN_PROGRESS",
                        "RECOVERY_REQUIRED", global_field=True)
            raise saga.SagaBlocked(
                "CHAIN_FILE_BATCH_ROLLBACK_UNKNOWN_RETAIN_EVIDENCE") from None
        _transition(plan, directory, i, "ROLLBACK_INTENT",
                    "ROLLED_BACK_VERIFIED")
    complete = ("ALL_17_FILE_TARGETS_RESTORED_NOT_CUTOVER"
                if promoted_count == STEPS else
                "KNOWN_FAILURE_FILE_TARGETS_RESTORED_NOT_CUTOVER")
    _transition(plan, directory, None, "ROLLBACK_IN_PROGRESS",
                complete, global_field=True)
    return {"status": complete,
            "restored_count": promoted_count, "cutover_allowed": False}


def rehearse_seventeen_site_files(
    plan: Mapping[str, Any], directory: Path, *,
    synthetic_authority: bool = False,
    fail_after_promotions: int | None = None,
) -> dict[str, Any]:
    """Preflight 17 original owners, snapshot ALL targets, then promote in order.

    Known *injected* failure after full verified promotion triggers reverse
    rollback; unknown or interrupted writes block without blind replays.
    """
    _fixture(synthetic_authority)
    rows = _steps(plan)
    saga.need(fail_after_promotions is None or (
        type(fail_after_promotions) is int and
        1 <= fail_after_promotions < STEPS),
        "CHAIN_FILE_BATCH_FAILURE_SCOPE_INVALID")
    fd = saga._lock(directory)
    try:
        path = directory / FILE
        saga.need(not os.path.lexists(path),
                  "CHAIN_FILE_BATCH_PREVIOUS_ATTEMPT_RETAINED")
        items = []
        for step in rows:
            paths, _, stage_hash = saga._verify_synthetic_stage(
                plan, step, directory)
            saga.need(
                not os.path.lexists(paths["journal"]) and
                not os.path.lexists(paths["snapshot"]) and
                not os.path.lexists(paths["held"]) and
                not os.path.lexists(paths["next"]) and
                not os.path.lexists(paths["failed"]) and
                paths["target"].is_dir() and
                not paths["target"].is_symlink() and
                paths["target"].stat().st_uid == os.geteuid() and
                not (paths["target"].stat().st_mode & 0o077),
                "CHAIN_FILE_BATCH_EXISTING_TARGET_OR_INTENT_UNSAFE"
            )
            target_before = saga._synthetic_tree_hash(paths["target"])
            items.append({
                "domain": step["domain"], "owner": step["owner"],
                "index": step["index"],
                "contract_sha256": step["site_contract_sha256"],
                "stage_sha256": stage_hash,
                "target_before_sha256": target_before,
                "status": "NOT_STARTED",
            })
        receipt = {
            "schema": SCHEMA, "status": "RECOVERY_PREPARE",
            "plan_sha256": plan["plan_sha256"],
            "scope_sha256": plan["scope_sha256"],
            "synthetic_only": True, "source_frozen": False,
            "cutover_allowed": False, "database_writes_performed": False,
            "sites": items,
        }
        saga._save(path, receipt)
    finally:
        os.close(fd)

    for i, step in enumerate(rows):
        _transition(plan, directory, i, "NOT_STARTED", "RECOVERY_INTENT")
        try:
            r = saga.snapshot_isolated_target(
                plan, step, directory, synthetic_authority=True)
            saga.need(r["status"] == "RECOVERY_POINT_VERIFIED" and
                      r["target_before_sha256"] ==
                      receipt["sites"][i]["target_before_sha256"],
                      "CHAIN_FILE_BATCH_SNAPSHOT_DRIFT")
        except Exception:
            _transition(plan, directory, None, "RECOVERY_PREPARE",
                        "RECOVERY_REQUIRED", global_field=True)
            raise saga.SagaBlocked(
                "CHAIN_FILE_BATCH_SNAPSHOT_UNKNOWN_RETAIN_EVIDENCE") from None
        _transition(plan, directory, i, "RECOVERY_INTENT",
                    "RECOVERY_VERIFIED")

    _all_recovery_points(plan, directory)
    _transition(plan, directory, None, "RECOVERY_PREPARE",
                "ALL_RECOVERY_POINTS_VERIFIED", global_field=True)
    for i, step in enumerate(rows):
        _transition(plan, directory, i, "RECOVERY_VERIFIED",
                    "PROMOTION_INTENT")
        try:
            r = saga.replace_isolated_target_from_stage(
                plan, step, directory, synthetic_authority=True)
            saga.need(r["status"] == "PROMOTED_NOT_CUTOVER",
                      "CHAIN_FILE_BATCH_PROMOTION_RESULT_UNVERIFIED")
        except Exception:
            _transition(plan, directory, None,
                        "ALL_RECOVERY_POINTS_VERIFIED",
                        "RECOVERY_REQUIRED", global_field=True)
            raise saga.SagaBlocked(
                "CHAIN_FILE_BATCH_PROMOTION_UNKNOWN_RETAIN_EVIDENCE") from None
        _transition(plan, directory, i, "PROMOTION_INTENT",
                    "PROMOTED_VERIFIED")

        if fail_after_promotions == i + 1:
            # All completed writes are known and verified. Preflight the
            # full 17-site snapshot set BEFORE reversing any target. Unknown
            # writes take the other branch and are never auto-rolled back.
            _transition(plan, directory, None,
                        "ALL_RECOVERY_POINTS_VERIFIED",
                        "KNOWN_DOWNSTREAM_FAILURE", global_field=True)
            restored = _reverse_verified(
                plan, directory, expected_status="KNOWN_DOWNSTREAM_FAILURE",
                promoted_count=i + 1)
            return {"status": restored["status"],
                    "restored_count": restored["restored_count"],
                    "recovery_points_verified": STEPS,
                    "cutover_allowed": False}

    _transition(plan, directory, None, "ALL_RECOVERY_POINTS_VERIFIED",
                "ALL_17_SITE_FILES_PROMOTED_NOT_CUTOVER", global_field=True)
    return {"status": "ALL_17_SITE_FILES_PROMOTED_NOT_CUTOVER",
            "promoted_count": STEPS,
            "recovery_points_verified": STEPS, "cutover_allowed": False,
            "source_frozen": False, "database_writes_performed": False}


def rollback_seventeen_site_files(
    plan: Mapping[str, Any], directory: Path, *,
    synthetic_authority: bool = False,
) -> dict[str, Any]:
    """Explicit safe reversal: all 17 verified promotions, no partial replay."""
    _fixture(synthetic_authority)
    return _reverse_verified(
        plan, directory,
        expected_status="ALL_17_SITE_FILES_PROMOTED_NOT_CUTOVER")


def inspect_seventeen_site_files(
    plan: Mapping[str, Any], directory: Path,
) -> dict[str, Any]:
    """Read-only; report uncertain intent, no replay or writes."""
    saga._safe_journal_dir(directory)
    receipt = _journal(plan, directory)
    statuses = [x["status"] for x in receipt["sites"]]
    uncertain = sum(x in {"RECOVERY_INTENT", "PROMOTION_INTENT",
                          "ROLLBACK_INTENT"} for x in statuses)
    return {
        "status": "MANUAL_RECOVERY_REQUIRED" if uncertain else receipt["status"],
        "recovery_verified_count":
            sum(x in {"RECOVERY_VERIFIED","PROMOTED_VERIFIED",
                      "ROLLBACK_INTENT","ROLLED_BACK_VERIFIED"}
                for x in statuses),
        "promoted_count": statuses.count("PROMOTED_VERIFIED"),
        "rolled_back_count": statuses.count("ROLLED_BACK_VERIFIED"),
        "uncertain_count": uncertain,
        "synthetic_only": True, "cutover_allowed": False,
    }


def rehearse_locked_database_full_reverse(
    plan: Mapping[str, Any], db_scope: Mapping[str, Any],
    resource_bindings: Mapping[str, Any],
    originals: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    directory: Path, *, synthetic_authority: bool = False,
) -> dict[str, Any]:
    """Reverse all verified assets/SQLite and 17 site files after DB refusal.

    The three original databases are never contacted or written. Unlike the
    existing resource-only reversal, this bridge includes every original site
    file owner. Both recovery sets are preflighted before FIRST rollback write.
    Any unknown/failed reversal retains all receipts and forbids auto-retry.
    """
    _fixture(synthetic_authority)
    import migration_chain_consolidation as consolidated

    _steps(plan)
    current_db = consolidated.bind_locked_original_database_scope(
        plan, *originals)
    saga.need(type(db_scope) is dict and db_scope == current_db and
              current_db.get("status") ==
              "LOCKED_DB_RECOVERY_REQUIRED_NOT_CUTOVER_READY" and
              current_db.get("database_count") == 3 and
              current_db.get("cross_task_batch_execution_allowed") is False and
              current_db.get("database_writes_performed") is False and
              current_db.get("cutover_allowed") is False,
              "CHAIN_FULL_REVERSE_DB_SCOPE_CHANGED")

    # Validate every file recovery snapshot and byte-exact held target first.
    site_journal = _journal(plan, directory)
    saga.need(site_journal.get("status") ==
              "ALL_17_SITE_FILES_PROMOTED_NOT_CUTOVER",
              "CHAIN_FULL_REVERSE_SITE_STAGE_UNVERIFIED")
    _all_recovery_points(plan, directory, promoted_count=STEPS)

    # Validate each owned external/SQLite recovery and target identity before
    # ANY resource or site restoration. Do not trust a status flag alone.
    resources = saga._assert_bound_resources(
        plan, resource_bindings, originals)
    resource_journal = saga._read_receipt(
        directory / "resource-rehearsal.json",
        expected_schema="P07_CHAIN_RESOURCE_REHEARSAL_V1")
    saga.need(
        resource_journal.get("status") ==
            "ALL_RESOURCE_PROMOTIONS_VERIFIED_NOT_CUTOVER" and
        resource_journal.get("plan_sha256") == plan["plan_sha256"] and
        resource_journal.get("inventory_sha256") ==
            resource_bindings["inventory_sha256"] and
        resource_journal.get("synthetic_only") is True and
        resource_journal.get("cutover_allowed") is False and
        isinstance(resource_journal.get("items"), list) and
        len(resource_journal["items"]) == len(resources),
        "CHAIN_FULL_REVERSE_RESOURCE_STAGE_UNVERIFIED"
    )
    for row, original in zip(resource_journal["items"], resources):
        saga.need(
            row.get("status") == "PROMOTED_VERIFIED" and
            {k:v for k,v in row.items() if k in original} == original,
            "CHAIN_FULL_REVERSE_RESOURCE_OWNER_CHANGED")
        paths = saga._resource_sandbox_paths(directory, row)
        kind = row["kind"]
        saga.need(
            saga._resource_fingerprint(kind, paths["target"]) ==
                row.get("promoted_sha256") and
            saga._resource_fingerprint(kind, paths["held"]) ==
                row.get("target_before_sha256") and
            saga._resource_fingerprint(kind, paths["recovery"]) ==
                row.get("recovery_sha256") and
            not os.path.lexists(paths["failed"]),
            "CHAIN_FULL_REVERSE_RESOURCE_RECOVERY_DRIFT"
        )

    # One-use durable boundary journal. Any interruption after this point is
    # explicit manual-recovery, never a blind repeat of a partial compensation.
    filename = "full-cross-owner-rollback.json"
    fd = saga._lock(directory)
    try:
        path = directory / filename
        saga.need(not os.path.lexists(path),
                  "CHAIN_FULL_REVERSE_PRIOR_INTENT_RETAINED")
        saga._save(path, {
            "schema":"P07_CHAIN_17_SITE_FULL_REVERSE_V1",
            "status":"INTENT_RESERVED",
            "plan_sha256":plan["plan_sha256"],
            "db_scope_sha256":current_db["scope_sha256"],
            "inventory_sha256":resource_bindings["inventory_sha256"],
            "synthetic_only":True,
            "cutover_allowed":False,
            "source_frozen":False,
            "database_writes_performed":False,
            "www3_reconnected":False,
            "resource_rollback_verified":False,
            "file_rollback_verified":False,
        })
    finally:
        os.close(fd)

    def save_status(status: str, *, resources_done: bool,
                    files_done: bool) -> None:
        fd = saga._lock(directory)
        try:
            journal = saga._read_receipt(
                directory / filename,
                expected_schema="P07_CHAIN_17_SITE_FULL_REVERSE_V1")
            saga.need(journal.get("plan_sha256") ==
                      plan["plan_sha256"] and
                      journal.get("db_scope_sha256") ==
                      current_db["scope_sha256"] and
                      journal.get("inventory_sha256") ==
                      resource_bindings["inventory_sha256"] and
                      journal.get("synthetic_only") is True and
                      journal.get("database_writes_performed") is False,
                      "CHAIN_FULL_REVERSE_JOURNAL_CHANGED")
            journal["status"] = status
            journal["resource_rollback_verified"] = resources_done
            journal["file_rollback_verified"] = files_done
            saga._save(directory / filename, journal)
        finally:
            os.close(fd)

    resources_done = False
    files_done = False
    try:
        resource_result = saga.reject_unverified_original_db_and_restore_resources(
            plan, db_scope, resource_bindings, originals, directory,
            synthetic_authority=True)
        saga.need(
            resource_result.get("status") ==
            "RESOURCE_ROLLBACK_VERIFIED_DATABASE_UNTOUCHED_NOT_CUTOVER" and
            resource_result.get("database_writes_performed") is False and
            resource_result.get("restored_resource_count") == len(resources),
            "CHAIN_FULL_REVERSE_RESOURCE_ROLLBACK_NOT_PROVEN")
        resources_done = True
        save_status("RESOURCES_RESTORED_FILES_PENDING",
                    resources_done=True, files_done=False)
        site_result = rollback_seventeen_site_files(
            plan, directory, synthetic_authority=True)
        saga.need(
            site_result.get("status") ==
            "ALL_17_FILE_TARGETS_RESTORED_NOT_CUTOVER" and
            site_result.get("restored_count") == STEPS,
            "CHAIN_FULL_REVERSE_SITE_ROLLBACK_NOT_PROVEN")
        files_done = True
    except Exception:
        save_status("RECOVERY_REQUIRED",
                    resources_done=resources_done, files_done=files_done)
        raise saga.SagaBlocked(
            "CHAIN_FULL_REVERSE_UNKNOWN_RETAIN_EVIDENCE") from None
    save_status("ALL_RESOURCES_AND_17_FILES_RESTORED_NOT_CUTOVER",
                resources_done=True, files_done=True)
    return {
        "status":"ALL_RESOURCES_AND_17_FILES_RESTORED_NOT_CUTOVER",
        "restored_file_site_count":STEPS,
        "restored_external_sqlite_count":len(resources),
        "database_writes_performed":False,
        "www3_reconnected":False,
        "cutover_allowed":False,
    }
