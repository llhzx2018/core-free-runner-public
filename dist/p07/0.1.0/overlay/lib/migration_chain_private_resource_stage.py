"""Guarded original-owner external/SQLite resource warm copy to private CP2 only.

Real transfers are isolated; no active target asset, SQLite database, DNS,
application config, runtime service or migration state.json is modified.
Source SQLite uses the existing pinned backup helper to create a temporary
snapshot under the original owner's PRIVATE source staging folder. This
writes a temporary private file on SOURCE and must never be run until the
owner explicitly starts the bounded preparation; not a frozen final snapshot.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import sqlite3
from typing import Any, Mapping

import migration_chain_asset_audit as assets
import migration_chain_final_saga as saga
import migration_chain_private_file_stage as file_stage
import server_migration as legacy

SCHEMA = "P07_17_SITE_PRIVATE_RESOURCE_WARM_STAGE_V1"
ROOT_NAME = "p07-17-site-private-resource-stage-v1"


class ResourceStageBlocked(RuntimeError):
    pass


def _need(value: bool, code: str) -> None:
    if not value:
        raise ResourceStageBlocked(code)


def _inventory(plan, originals):
    try:
        return assets.bind_original_resources(plan, *originals)
    except assets.ResourceOwnerBlocked:
        raise ResourceStageBlocked("RESOURCE_STAGE_ORIGINAL_SCOPE_DRIFT") from None


def _root(plan, base: Path) -> Path:
    try:
        parent = file_stage._private_parent(plan, base)
    except file_stage.WarmStageBlocked:
        raise ResourceStageBlocked("RESOURCE_STAGE_PRIVATE_PARENT_INVALID") from None
    # The external/SQLite namespace must be a private sibling of the original
    # site files; never remove or modify the existing site warm-copy evidence.
    return parent.parent / ROOT_NAME


def _token(item: Mapping[str, Any]) -> str:
    return hashlib.sha256(saga._encoded({
        "owner": item["owner"], "kind": item["kind"],
        "path": item["source_path_sha256"],
    })).hexdigest()[:32]


def _sqlite_readback(path: Path) -> None:
    _need(path.is_file() and not path.is_symlink(),
          "RESOURCE_STAGE_SQLITE_FILE_UNSAFE")
    try:
        with sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True) as conn:
            result = conn.execute("PRAGMA quick_check").fetchone()
            _need(result is not None and result[0] == "ok",
                  "RESOURCE_STAGE_SQLITE_CHECK_FAILED")
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        raise ResourceStageBlocked("RESOURCE_STAGE_SQLITE_CHECK_FAILED") from None


def _live_kind(pull, task, source_path: str, declared: str | None,
               resource_kind: str) -> str:
    try:
        kind = pull.source_path_kind(task["source"], source_path)
    except Exception:
        raise ResourceStageBlocked("RESOURCE_STAGE_SOURCE_TYPE_UNAVAILABLE") from None
    _need(kind in ("FILE", "DIRECTORY"),
          "RESOURCE_STAGE_SOURCE_TYPE_UNSAFE")
    if declared is not None:
        _need(kind == declared, "RESOURCE_STAGE_SOURCE_TYPE_DRIFT")
    if resource_kind == "SQLITE":
        _need(kind == "FILE", "RESOURCE_STAGE_SQLITE_SOURCE_NOT_FILE")
    return kind


def stage_original_private_resources(
    plan: Mapping[str, Any],
    originals: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    *, root: Path, actual_target_identity: str,
    authorize_private_copy: bool = False,
) -> dict[str, Any]:
    """One-shot source-origin copy; preserves uncertain partial attempts."""
    _need(authorize_private_copy is True,
          "RESOURCE_STAGE_EXPLICIT_PRIVATE_SCOPE_REQUIRED")
    try:
        file_stage._identity(plan, originals, actual_target_identity)
    except file_stage.WarmStageBlocked:
        raise ResourceStageBlocked("RESOURCE_STAGE_ORIGINAL_SITE_SCOPE_DRIFT") from None
    inventory = _inventory(plan, originals)
    private = _root(plan, root)
    _need(not os.path.lexists(private),
          "RESOURCE_STAGE_PREVIOUS_ATTEMPT_RETAINED")

    tasks = {t["migration_id"]: t for t in originals}
    # All original metadata, owners and source paths are rehashed before any
    # target/source staging operation or source-network read.
    rows: list[tuple[dict, dict, dict]] = []
    for item in inventory["resources"]:
        task = tasks[item["owner"]]
        key = ("external_assets" if item["kind"] == "EXTERNAL_ASSET"
               else "sqlite_assets")
        origin = task[key][item["resource_index"]]
        if item["kind"] == "SQLITE":
            expected_helper = ("/var/lib/vf-server-ops/pull-source/"
                               + task["migration_id"] + "/runtime")
            _need(task.get("source_runtime_path") == expected_helper,
                  "RESOURCE_STAGE_SQLITE_SOURCE_HELPER_UNVERIFIED")
        _need(assets._digest(origin) == item["metadata_sha256"]
              and hashlib.sha256(origin["path"].encode()).hexdigest()
              == item["source_path_sha256"],
              "RESOURCE_STAGE_ORIGINAL_RECORD_CHANGED")
        rows.append((item, task, origin))

    private.mkdir(mode=0o700)
    journal = private / "journal.json"
    receipt: dict[str, Any] = {
        "schema": SCHEMA, "status": "INTENT_RECORDED",
        "plan_sha256": plan["plan_sha256"],
        "inventory_sha256": inventory["inventory_sha256"],
        "target_identity_sha256": plan["target_identity_sha256"],
        "resource_count": len(rows),
        "external_count": inventory["external_count"],
        "sqlite_count": inventory["sqlite_count"],
        "completed": [], "active_token": None,
        "source_frozen": False, "source_final_parity": False,
        "target_active_files_untouched": True,
        "target_active_sqlite_untouched": True,
        "source_business_files_untouched": True,
        "source_private_sqlite_snapshots_attempted": False,
        "cutover_allowed": False,
    }
    legacy.atomic_private_json(journal, receipt)
    import server_migration_pull as pull

    for item, task, origin in rows:
        token = _token(item)
        dest = private / ("resource-" + token)
        _need(not os.path.lexists(dest), "RESOURCE_STAGE_PRIVATE_PATH_CONFLICT")
        receipt["status"] = "RESOURCE_COPY_INTENT"
        receipt["active_token"] = token
        legacy.atomic_private_json(journal, receipt)
        remote_sqlite: str | None = None
        cleanup_verified = True
        private_readback_complete = False
        try:
            kind = _live_kind(pull, task, origin["path"],
                              item["source_kind_declared"], item["kind"])
            dest.mkdir(mode=0o700)
            if item["kind"] == "SQLITE":
                # Existing source helper is a SQLite online backup, NOT raw
                # rsync of a live WAL file. Use an unpredictable private path.
                # The old VPS source helper creates this temp snapshot.
                remote_sqlite = (pull.remote_staging_root(task)
                                 + "/resource-warm-"
                                 + secrets.token_hex(16) + ".sqlite")
                receipt["source_private_sqlite_snapshots_attempted"] = True
                # Keep the exact private remote temp path in the protected
                # journal so an interrupted transfer is recoverable without
                # searching or deleting source business files.
                receipt["active_remote_sqlite_snapshot"] = remote_sqlite
                legacy.atomic_private_json(journal, receipt)
                result = pull.source_python(
                    task["source"], task["source_runtime_path"],
                    "_source-snapshot-sqlite",
                    "--source", origin["path"], "--output", remote_sqlite,
                    timeout=600,
                )
                _need(result.returncode == 0,
                      "RESOURCE_STAGE_SQLITE_SOURCE_SNAPSHOT_FAILED")
                pull.pull_path(
                    task["source"], remote_sqlite,
                    dest / "snapshot.sqlite", delete=False,
                )
                _sqlite_readback(dest / "snapshot.sqlite")
            elif kind == "DIRECTORY":
                pull.pull_path(task["source"], origin["path"].rstrip("/") + "/",
                               dest, delete=False)
            else:
                pull.pull_path(task["source"], origin["path"],
                               dest / "asset", delete=False)
            digest = file_stage._tree_digest(dest)
            private_readback_complete = True
        except Exception:
            receipt["status"] = "INTERRUPTED_KEEP_ALL_PRIVATE_EVIDENCE"
            legacy.atomic_private_json(journal, receipt)
            raise ResourceStageBlocked(
                "RESOURCE_STAGE_COPY_OR_READBACK_RECOVERY_REQUIRED"
            ) from None
        finally:
            if remote_sqlite is not None and private_readback_complete:
                # Never clean a remote SQLite snapshot if the source helper
                # failed, transfer was interrupted or private quick_check
                # failed. In these cases preserve the source-side recovery
                # copy and the exact path in the CP2 private journal.
                try:
                    proc = pull.source_remote(
                        task["source"], "rm -f -- " + shlex.quote(remote_sqlite),
                        timeout=60, check=False,
                    )
                    cleanup_verified = proc.returncode == 0
                except Exception:
                    cleanup_verified = False
                if not cleanup_verified:
                    receipt["status"] = "SOURCE_PRIVATE_SNAPSHOT_CLEANUP_UNVERIFIED"
                    legacy.atomic_private_json(journal, receipt)
        _need(cleanup_verified,
              "RESOURCE_STAGE_SOURCE_TEMP_CLEANUP_RECOVERY_REQUIRED")
        receipt.pop("active_remote_sqlite_snapshot", None)
        receipt["completed"].append({
            "token": token,
            "domain": item["domain"], "kind": item["kind"],
            "original_owner": item["owner"],
            "source_path_sha256": item["source_path_sha256"],
            "metadata_sha256": item["metadata_sha256"],
            "source_kind": kind, "stage_tree_sha256": digest,
            "source_final_parity": False,
        })
        receipt["active_token"] = None
        receipt["status"] = "PRIVATE_COPY_READBACK_NOT_FROZEN"
        legacy.atomic_private_json(journal, receipt)

    receipt["status"] = "ALL_ORIGINAL_PRIVATE_RESOURCES_STAGED_NOT_FINAL"
    legacy.atomic_private_json(journal, receipt)
    return {
        "status": receipt["status"], "resource_count": len(rows),
        "external_count": inventory["external_count"],
        "sqlite_count": inventory["sqlite_count"],
        "source_private_sqlite_snapshots_attempted":
            receipt["source_private_sqlite_snapshots_attempted"],
        "existing_target_modified": False,
        "source_final_parity": False, "cutover_allowed": False,
    }


def verify_original_private_resources(
    plan: Mapping[str, Any],
    originals: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    *, root: Path,
) -> dict[str, Any]:
    """Readback every staged tree and original resource identity, without SSH."""
    try:
        saga.validate_locked_plan(plan)
    except saga.SagaBlocked:
        raise ResourceStageBlocked("RESOURCE_STAGE_LOCKED_PLAN_INVALID") from None
    inventory = _inventory(plan, originals)
    private = _root(plan, root)
    try:
        receipt = saga._read_receipt(private / "journal.json",
                                    expected_schema=SCHEMA)
    except saga.SagaBlocked:
        raise ResourceStageBlocked("RESOURCE_STAGE_RECEIPT_UNAVAILABLE") from None
    _need(receipt.get("status") == "ALL_ORIGINAL_PRIVATE_RESOURCES_STAGED_NOT_FINAL"
          and receipt.get("plan_sha256") == plan["plan_sha256"]
          and receipt.get("inventory_sha256") == inventory["inventory_sha256"]
          and receipt.get("target_identity_sha256")
          == plan["target_identity_sha256"]
          and receipt.get("resource_count") == inventory["resource_count"]
          and receipt.get("source_frozen") is False
          and receipt.get("source_final_parity") is False
          and receipt.get("target_active_files_untouched") is True
          and receipt.get("target_active_sqlite_untouched") is True
          and receipt.get("cutover_allowed") is False,
          "RESOURCE_STAGE_RECEIPT_SCOPE_CHANGED")
    expected = {_token(r): r for r in inventory["resources"]}
    completed = receipt.get("completed")
    _need(type(completed) is list and len(completed) == len(expected)
          and len({r.get("token") for r in completed
                   if isinstance(r, dict)}) == len(expected),
          "RESOURCE_STAGE_COMPLETION_COUNT_CHANGED")
    for row in completed:
        _need(isinstance(row, dict)
              and row.get("token") in expected,
              "RESOURCE_STAGE_COMPLETION_OWNER_CHANGED")
        bound = expected[row["token"]]
        _need(row.get("original_owner") == bound["owner"]
              and row.get("kind") == bound["kind"]
              and row.get("domain") == bound["domain"]
              and row.get("source_path_sha256") == bound["source_path_sha256"]
              and row.get("metadata_sha256") == bound["metadata_sha256"]
              and row.get("source_final_parity") is False,
              "RESOURCE_STAGE_COMPLETION_OWNER_CHANGED")
        folder = private / ("resource-" + row["token"])
        try:
            digest = file_stage._tree_digest(folder)
        except file_stage.WarmStageBlocked:
            raise ResourceStageBlocked("RESOURCE_STAGE_PRIVATE_FILE_UNSAFE") from None
        _need(digest == row.get("stage_tree_sha256"),
              "RESOURCE_STAGE_PRIVATE_COPY_DRIFT")
        if bound["kind"] == "SQLITE":
            _sqlite_readback(folder / "snapshot.sqlite")
    return {
        "status": "ALL_ORIGINAL_PRIVATE_RESOURCES_VERIFIED_NOT_FINAL",
        "resource_count": len(completed),
        "external_count": inventory["external_count"],
        "sqlite_count": inventory["sqlite_count"],
        "source_final_parity": False,
        "existing_target_modified": False,
        "cutover_allowed": False, "writes_performed": False,
    }
