"""P07 three-task asset inventory conflict audit (read-only and redacted).

Parent, child and tail source inventories may each include the same external
paths, SQLite files, cron/PM2 jobs and HTTP baselines. An executable 17-site
state MUST NOT concatenate those arrays or select an arbitrary owner.

This module detects duplicate-compatible vs conflicting resources and missing
per-site HTTP baselines, without reading customer files, connecting to source
SSH, changing task state, or deciding to cut over. A structural PASS never
proves the frozen-source snapshot, file parity, or rollback readiness.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


SCHEMA = "P07_CHAIN_ASSET_STRUCTURAL_AUDIT_V1"


def _digest(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def audit(
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
    tail: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    tasks = (parent, child, tail)
    errors: set[str] = set()
    seen_external: dict[str, str] = {}
    seen_sqlite: dict[str, str] = {}
    seen_jobs: dict[tuple[str, ...], str] = {}
    job_owner_count: dict[tuple[str, ...], int] = {}
    resource_counts = {
        "external_paths": 0, "sqlite_paths": 0, "runtime_jobs": 0,
        "duplicate_compatible_external": 0, "duplicate_compatible_sqlite": 0,
        "duplicate_compatible_runtime": 0, "unproven_baselines": 0,
        "staged_runtime_records": 0,
    }
    def assets(task: Mapping[str, Any], key: str, kind: str, seen: dict[str, str]) -> None:
        rows = task.get(key)
        if not isinstance(rows, list):
            errors.add("ASSET_INVENTORY_UNAVAILABLE")
            return
        for row in rows:
            if not isinstance(row, dict):
                errors.add("ASSET_RECORD_INVALID")
                continue
            path = row.get("path")
            if not isinstance(path, str) or not path.startswith("/") or "//" in path:
                errors.add("ASSET_PATH_INVALID")
                continue
            value = _digest(row)
            if path in seen:
                if seen[path] != value:
                    errors.add("ASSET_PATH_METADATA_CONFLICT")
                else:
                    resource_counts["duplicate_compatible_" + kind] += 1
            else:
                seen[path] = value

    for task in tasks:
        if not isinstance(task, dict):
            errors.add("MIGRATION_TASK_INVALID")
            continue
        assets(task, "external_assets", "external", seen_external)
        assets(task, "sqlite_assets", "sqlite", seen_sqlite)
        runtime = task.get("runtime_assets")
        if not isinstance(runtime, dict):
            errors.add("RUNTIME_INVENTORY_UNAVAILABLE")
            continue
        for category, required_fields in (
            ("system_cron", ("path",)),
            ("user_cron", ("path", "user")),
            ("pm2", ("user", "dump", "node_runtime")),
        ):
            entries = runtime.get(category)
            if not isinstance(entries, list):
                errors.add("RUNTIME_INVENTORY_UNAVAILABLE")
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    errors.add("RUNTIME_RECORD_INVALID")
                    continue
                parts = tuple(entry.get(key) for key in required_fields)
                if any(not isinstance(v, str) or not v for v in parts):
                    errors.add("RUNTIME_RECORD_INVALID")
                    continue
                for field, value in zip(required_fields, parts):
                    if field != "user" and not value.startswith("/"):
                        errors.add("RUNTIME_PATH_INVALID")
                identity = (category,) + parts[:2] if category == "pm2" else (category,) + parts
                signature = _digest(entry)
                if identity in seen_jobs:
                    if seen_jobs[identity] != signature:
                        errors.add("RUNTIME_JOB_METADATA_CONFLICT")
                    else:
                        resource_counts["duplicate_compatible_runtime"] += 1
                else:
                    seen_jobs[identity] = signature
                job_owner_count[identity] = job_owner_count.get(identity, 0) + 1
            pending_name = {
                "system_cron": "pending_system_cron",
                "user_cron": "pending_user_cron",
                "pm2": "pending_pm2",
            }[category]
            pending = task.get(pending_name)
            if not isinstance(pending, list) or len(pending) != len(entries):
                errors.add("RUNTIME_STAGING_COUNT_MISMATCH")
                continue
            for staged in pending:
                if (
                    not isinstance(staged, dict)
                    or staged.get("activated") is not False
                    or not isinstance(staged.get("staged_target"), str)
                    or not staged["staged_target"].startswith("/")
                ):
                    errors.add("RUNTIME_STAGING_UNVERIFIED")
                else:
                    resource_counts["staged_runtime_records"] += 1
        listeners = task.get("source_external_listeners")
        if not isinstance(listeners, list):
            errors.add("SOURCE_LISTENER_INVENTORY_UNAVAILABLE")

    # The same source runtime resource may have been prepared in multiple
    # private jobs. That is NOT proof its staged_target or rollback owner can
    # be reused in a new consolidated job. Re-stage under a new private scope.
    if any(count > 1 for count in job_owner_count.values()):
        errors.add("RUNTIME_RESTAGING_REQUIRED")

    domain_sources = {
        record["domain"]: record["origin_migration_id"]
        for record in provenance.get("sites", [])
        if isinstance(record, dict)
        and isinstance(record.get("domain"), str)
        and isinstance(record.get("origin_migration_id"), str)
    }
    owners = {str(task.get("migration_id")): task for task in tasks if isinstance(task, dict)}
    if len(domain_sources) != 17 or not set(domain_sources.values()).issubset(owners):
        errors.add("SITE_PROVENANCE_UNVERIFIED")
    for domain, mid in domain_sources.items():
        baseline = owners[mid].get("source_http_baseline")
        required = owners[mid].get("source_http_baseline_required")
        row = baseline.get(domain) if isinstance(baseline, dict) else None
        if (
            required is not True or not isinstance(row, dict)
            or row.get("status") != "PASS"
        ):
            errors.add("SOURCE_HTTP_BASELINE_UNVERIFIED")
            resource_counts["unproven_baselines"] += 1

    resource_counts["external_paths"] = len(seen_external)
    resource_counts["sqlite_paths"] = len(seen_sqlite)
    resource_counts["runtime_jobs"] = len(seen_jobs)
    return {
        "schema": SCHEMA,
        "status": (
            "STRUCTURAL_CONSISTENT_NOT_FINAL_VERIFIED"
            if not errors else "REQUIRES_ASSET_RECONCILIATION"
        ),
        "site_count": len(domain_sources),
        "source_task_count": len(owners),
        "counts": resource_counts,
        "blockers": sorted(errors),
        "original_tasks_unchanged": True,
        "source_live_snapshot_proved": False,
        "file_hashes_proved": False,
        "sqlite_final_snapshot_proved": False,
        "runtime_stage_reusable": False,
        "source_freeze_allowed": False,
        "cutover_allowed": False,
        "writes_performed": False,
    }


class ResourceOwnerBlocked(ValueError):
    """A resource does not have exactly one verified original migration owner."""


def bind_original_resources(plan, parent, child, tail):
    """Bind original external/SQLite records without combining their task state.

    This only produces an immutable, path-redacted execution inventory.
    A shared path (even identical metadata) is NOT an authorization to use
    another task's snapshot. No SQL, remote access or filesystem operations.
    """
    import os
    from pathlib import PurePosixPath
    import migration_chain_consolidation as consolidated
    import migration_chain_final_saga as saga

    try:
        saga.validate_locked_plan(plan)
    except saga.SagaBlocked as exc:
        raise ResourceOwnerBlocked("RESOURCE_LOCKED_PLAN_UNVERIFIED") from exc
    tasks = (parent, child, tail)
    by_mid = {}
    for task in tasks:
        if not isinstance(task, dict):
            raise ResourceOwnerBlocked("RESOURCE_TASK_INVALID")
        mid = task.get("migration_id")
        if not isinstance(mid, str) or mid in by_mid:
            raise ResourceOwnerBlocked("RESOURCE_TASK_ID_DUPLICATE")
        by_mid[mid] = task
        try:
            source = consolidated._original_source_identity(task)
        except consolidated.ConsolidationBlocked:
            raise ResourceOwnerBlocked("RESOURCE_SOURCE_IDENTITY_UNVERIFIED") from None
        source_digest = hashlib.sha256(json.dumps(
            source, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")).hexdigest()
        target_digest = hashlib.sha256(str(
            task.get("target_server_identity", "")).encode("utf-8")
        ).hexdigest()
        if source_digest != plan["source_identity_sha256"] or (
            target_digest != plan["target_identity_sha256"]
        ):
            raise ResourceOwnerBlocked("RESOURCE_SERVER_IDENTITY_DRIFT")

    if len(by_mid) != 3 or set(by_mid) != {
        x["owner"] for x in plan["steps"][:17]
    }:
        raise ResourceOwnerBlocked("RESOURCE_ORIGINAL_TASK_SET_UNVERIFIED")
    users = {}
    for site in plan["steps"][:17]:
        task = by_mid[site["owner"]]
        rows = task.get("sites")
        index = site["index"]
        if not isinstance(rows, list) or index >= len(rows) or (
            not isinstance(rows[index], dict)
        ):
            raise ResourceOwnerBlocked("RESOURCE_SITE_INDEX_DRIFT")
        row = rows[index]
        contract = hashlib.sha256(json.dumps(
            consolidated._site_contract(row), sort_keys=True,
            separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")).hexdigest()
        user = row.get("site_user")
        if (
            contract != site["site_contract_sha256"]
            or row.get("domain") != site["domain"]
            or not isinstance(user, str) or not user
            or user in users
        ):
            raise ResourceOwnerBlocked("RESOURCE_SITE_OWNER_CONTRACT_DRIFT")
        users[user] = site

    resources = []
    claimed = []
    for task in tasks:
        for collection, kind in (
            ("external_assets", "EXTERNAL_ASSET"),
            ("sqlite_assets", "SQLITE"),
        ):
            raw = task.get(collection)
            if not isinstance(raw, list) or len(raw) > 4096:
                raise ResourceOwnerBlocked("RESOURCE_INVENTORY_MISSING_OR_UNBOUNDED")
            for index, record in enumerate(raw):
                if not isinstance(record, dict):
                    raise ResourceOwnerBlocked("RESOURCE_METADATA_INVALID")
                path = record.get("path")
                user = record.get("user")
                if not isinstance(path, str) or not isinstance(user, str):
                    raise ResourceOwnerBlocked("RESOURCE_PATH_OR_USER_UNVERIFIED")
                if (
                    not path.startswith("/") or
                    path in ("/", "/home") or
                    "\0" in path or "\\" in path or
                    len(path) > 2048 or
                    os.path.normpath(path) != path or
                    "//" in path or
                    ".." in PurePosixPath(path).parts or
                    not path.startswith("/home/" + user + "/")
                ):
                    raise ResourceOwnerBlocked("RESOURCE_PATH_OUTSIDE_OWNER_HOME")
                site = users.get(user)
                if site is None or site["owner"] != task["migration_id"]:
                    raise ResourceOwnerBlocked("RESOURCE_CROSS_TASK_OWNER_CONFLICT")
                if kind == "EXTERNAL_ASSET":
                    # Historical real target-pull migration inventories store
                    # {path,user,reason}, NOT "kind". Absence is an unresolved
                    # live-source-type proof, never license to assume a dir.
                    # An explicitly forged or unknown kind is still denied.
                    source_kind = record.get("kind")
                    if source_kind is not None and source_kind not in {"DIRECTORY", "FILE"}:
                        raise ResourceOwnerBlocked("RESOURCE_EXTERNAL_KIND_UNVERIFIED")
                else:
                    source_kind = "FILE"
                    mode = record.get("mode", 0o600)
                    if (
                        type(mode) is not int or mode < 0 or mode > 0o777
                        or mode & 0o002
                    ):
                        raise ResourceOwnerBlocked("RESOURCE_SQLITE_MODE_UNSAFE")
                # Nested externals and SQLite-under-external collide just as
                # exactly duplicated file paths do. Never silently dedupe.
                for other in claimed:
                    if (path == other or path.startswith(other + "/")
                            or other.startswith(path + "/")):
                        raise ResourceOwnerBlocked("RESOURCE_PATH_OVERLAP_UNPROVEN")
                claimed.append(path)
                digest = _digest(record)
                item = {
                    "kind": kind,
                    "owner": task["migration_id"],
                    "domain": site["domain"],
                    "site_contract_sha256": site["site_contract_sha256"],
                    "owner_index": site["index"],
                    "resource_index": index,
                    "source_kind_declared": source_kind if kind == "EXTERNAL_ASSET" else "FILE",
                    "live_source_kind_verified": False,
                    "metadata_sha256": digest,
                    "source_path_sha256": hashlib.sha256(
                        path.encode("utf-8")).hexdigest(),
                }
                resources.append(item)
    resources.sort(key=lambda r: (
        r["domain"], r["kind"], r["source_path_sha256"]
    ))
    inventory_sha256 = hashlib.sha256(json.dumps({
        "plan_sha256": plan["plan_sha256"], "resources": resources,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")).hexdigest()
    return {
        "schema": "P07_CHAIN_ORIGINAL_RESOURCE_BINDINGS_V1",
        "status": "LOCKED_ORIGINAL_RESOURCES_NOT_CUTOVER_READY",
        "plan_sha256": plan["plan_sha256"],
        "source_identity_sha256": plan["source_identity_sha256"],
        "target_identity_sha256": plan["target_identity_sha256"],
        "inventory_sha256": inventory_sha256,
        "resources": resources,
        "resource_count": len(resources),
        "external_count": sum(
            x["kind"] == "EXTERNAL_ASSET" for x in resources),
        "sqlite_count": sum(x["kind"] == "SQLITE" for x in resources),
        "historical_external_kind_missing_count": sum(
            x["kind"] == "EXTERNAL_ASSET" and
            x["source_kind_declared"] is None for x in resources),
        "live_source_types_verified": False,
        "recovery_points_verified": False,
        "source_frozen": False,
        "cutover_allowed": False,
        "writes_performed": False,
    }



def verify_original_resource_source_types(
    plan, parent, child, tail, *, source_path_probe=None,
):
    """Fresh read-only old-VPS type proof for original-owned external/SQLite.

    Existing real migration records did not record external kind. A remote
    symlink/special/missing resource or inconsistent explicit type is a hard
    stop. Even passing this check does NOT prove final snapshot equality;
    the source is still live, and a final frozen readback is required.
    """
    import server_migration_pull as pull

    bindings = bind_original_resources(plan, parent, child, tail)
    probe = source_path_probe if source_path_probe is not None else pull.source_path_kind
    tasks = {s["migration_id"]: s for s in (parent, child, tail)}
    verified = []
    for item in bindings["resources"]:
        task = tasks[item["owner"]]
        collection = (
            "external_assets" if item["kind"] == "EXTERNAL_ASSET"
            else "sqlite_assets"
        )
        origin = task[collection][item["resource_index"]]
        if (_digest(origin) != item["metadata_sha256"] or
                hashlib.sha256(origin["path"].encode("utf-8")).hexdigest()
                != item["source_path_sha256"]):
            raise ResourceOwnerBlocked("RESOURCE_ORIGINAL_RECORD_CHANGED")
        try:
            actual = probe(task["source"], origin["path"])
        except Exception:
            raise ResourceOwnerBlocked(
                "RESOURCE_LIVE_SOURCE_TYPE_READBACK_UNAVAILABLE"
            ) from None
        if actual not in {"DIRECTORY", "FILE"}:
            raise ResourceOwnerBlocked("RESOURCE_LIVE_SOURCE_TYPE_UNSAFE")
        if (item["kind"] == "SQLITE" and actual != "FILE") or (
            item["source_kind_declared"] is not None
            and item["source_kind_declared"] != actual
        ):
            raise ResourceOwnerBlocked("RESOURCE_LIVE_SOURCE_KIND_CHANGED")
        verified.append({
            "owner": item["owner"], "domain": item["domain"],
            "kind": item["kind"], "source_path_sha256":
            item["source_path_sha256"], "source_kind": actual,
        })
    digest = hashlib.sha256(json.dumps({
        "plan_sha256": plan["plan_sha256"],
        "inventory_sha256": bindings["inventory_sha256"],
        "records": verified,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")).hexdigest()
    return {
        "schema": "P07_CHAIN_ORIGINAL_RESOURCE_SOURCE_TYPE_READBACK_V1",
        "status": "LIVE_SOURCE_TYPES_VERIFIED_NOT_FINAL_SNAPSHOT",
        "plan_sha256": plan["plan_sha256"],
        "inventory_sha256": bindings["inventory_sha256"],
        "source_type_readback_sha256": digest,
        "resource_count": len(verified),
        "external_count": bindings["external_count"],
        "sqlite_count": bindings["sqlite_count"],
        "historical_external_kind_missing_count":
            bindings["historical_external_kind_missing_count"],
        "live_source_types_verified": True,
        "source_frozen": False,
        "source_file_parity_verified": False,
        "cutover_allowed": False,
        "source_writes_performed": False,
        "target_writes_performed": False,
    }
