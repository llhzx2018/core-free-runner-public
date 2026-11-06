"""P07 three-owner, real CP2 PRIVATE site-file warm copy (never a cutover).

This stage is deliberately no-overwrite and no-delete. It can transfer all
17 source roots only to a new private CP2 recovery namespace. A live source
can change while copying; no file parity, final snapshot, or cutover claim
is implied. It is a component of the future full migration transaction,
not an independently executable final migration.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any, Mapping

import migration_chain_final_saga as saga
import migration_chain_consolidation as consolidated
import server_migration as legacy

SCHEMA = "P07_17_SITE_PRIVATE_WARM_STAGE_V1"
ROOT_NAME = "p07-17-site-private-warm-stage-v1"


class WarmStageBlocked(RuntimeError):
    pass


def _need(ok: bool, reason: str) -> None:
    if not ok:
        raise WarmStageBlocked(reason)


def _identity(plan: Mapping[str, Any], originals: tuple[Mapping[str, Any], ...],
              actual_target_identity: str) -> list[tuple[dict, dict]]:
    try:
        saga.validate_locked_plan(plan)
    except saga.SagaBlocked:
        raise WarmStageBlocked("WARM_STAGE_LOCKED_PLAN_INVALID") from None
    _need(type(originals) is tuple and len(originals) == 3
          and all(isinstance(x, dict) for x in originals),
          "WARM_STAGE_THREE_ORIGINAL_TASKS_REQUIRED")
    tasks = {s.get("migration_id"): s for s in originals}
    _need(len(tasks) == 3
          and set(tasks) == {s["owner"] for s in plan["steps"][:17]},
          "WARM_STAGE_ORIGINAL_TASK_OWNERS_DRIFT")
    source = originals[0].get("source")
    _need(isinstance(source, dict)
          and isinstance(source.get("host"), str) and source["host"]
          and isinstance(source.get("ssh_user"), str) and source["ssh_user"],
          "WARM_STAGE_SOURCE_CONNECTION_UNVERIFIED")
    expected_source = plan["source_identity_sha256"]
    expected_target = plan["target_identity_sha256"]
    _need(isinstance(actual_target_identity, str)
          and hashlib.sha256(actual_target_identity.encode()).hexdigest()
          == expected_target,
          "WARM_STAGE_TARGET_IDENTITY_CHANGED")
    for owner in originals:
        try:
            source_identity = consolidated._original_source_identity(owner)
        except consolidated.ConsolidationBlocked:
            raise WarmStageBlocked("WARM_STAGE_ORIGINAL_SOURCE_CHANGED") from None
        _need(hashlib.sha256(saga._encoded(source_identity)).hexdigest()
              == expected_source
              and owner.get("source") == source
              and owner.get("target_server_identity") == actual_target_identity
              and owner.get("status") in {"PREPARE_FAILED", "PREPARED"}
              and owner.get("source_runtime_frozen") is False
              and owner.get("target_runtime_activated") is False
              and owner.get("dns_changed_by_p07") is False
              and owner.get("source_delete_allowed") is False
              and owner.get("existing_target_overwrite_allowed") is False,
              "WARM_STAGE_ORIGINAL_TASK_RUNTIME_CHANGED")

    bound = []
    users, roots = set(), set()
    for row in plan["steps"][:17]:
        task = tasks[row["owner"]]
        sites = task.get("sites")
        index = row["index"]
        _need(isinstance(sites, list) and index < len(sites)
              and isinstance(sites[index], dict),
              "WARM_STAGE_ORIGINAL_SITE_MISSING")
        site = sites[index]
        contract_sha = hashlib.sha256(
            saga._encoded(consolidated._site_contract(site))
        ).hexdigest()
        site_root = site.get("site_root")
        user = site.get("site_user")
        dbs = site.get("mysql_databases")
        _need(site.get("domain") == row["domain"]
              and contract_sha == row["site_contract_sha256"]
              and isinstance(site_root, str)
              and site_root.startswith("/home/")
              and ".." not in Path(site_root).parts
              and str(Path(site_root)) == site_root
              and isinstance(user, str) and user
              and isinstance(dbs, list) and len(dbs) <= 1
              and site.get("stage_status") in {"PENDING", "PULLED_STAGED"}
              and user not in users and site_root not in roots,
              "WARM_STAGE_SITE_CONTRACT_OR_PATH_CHANGED")
        roots.add(site_root)
        users.add(user)
        bound.append((task, site))
    _need(len(bound) == 17, "WARM_STAGE_SITE_COUNT_CHANGED")
    return bound


def _private_parent(plan: Mapping[str, Any], root: Path) -> Path:
    # The caller must pass the *original parent* migration state directory,
    # not an arbitrary location or an unrelated backup site.
    expected = legacy.state_dir(plan["steps"][0]["owner"])
    _need(root == expected and not root.is_symlink() and root.is_dir(),
          "WARM_STAGE_PARENT_STATE_ROOT_UNVERIFIED")
    info = root.stat()
    _need(info.st_uid == os.geteuid()
          and not stat.S_IMODE(info.st_mode) & 0o077,
          "WARM_STAGE_PARENT_STATE_ROOT_UNSAFE")
    return root / ROOT_NAME


def _tree_digest(root: Path) -> str:
    """Private copied-file readback: reject links and special device files."""
    _need(not root.is_symlink() and root.is_dir(),
          "WARM_STAGE_TREE_ROOT_UNSAFE")
    rows = []
    def visit(path: Path, rel: str) -> None:
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        _need(not stat.S_ISLNK(info.st_mode) and not mode & 0o002
              and info.st_uid >= 0,
              "WARM_STAGE_TREE_SYMLINK_OR_WORLD_WRITABLE")
        if stat.S_ISDIR(info.st_mode):
            rows.append([rel + "/", "dir", mode])
            for child in sorted(path.iterdir(), key=lambda p: p.name):
                visit(child, rel + "/" + child.name if rel else child.name)
        elif stat.S_ISREG(info.st_mode):
            _need(info.st_nlink == 1, "WARM_STAGE_TREE_HARDLINK_UNSAFE")
            sha = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1048576), b""):
                    sha.update(chunk)
            rows.append([rel, "file", mode, info.st_size, sha.hexdigest()])
        else:
            raise WarmStageBlocked("WARM_STAGE_TREE_SPECIAL_FILE")
    visit(root, "")
    _need(len(rows) > 1, "WARM_STAGE_TREE_EMPTY")
    return hashlib.sha256(saga._encoded(rows)).hexdigest()


def stage_private_seventeen_site_warm_copy(
    plan: Mapping[str, Any],
    original_tasks: tuple[Mapping[str, Any], ...],
    *,
    root: Path,
    actual_target_identity: str,
    authorize_private_copy: bool = False,
) -> dict[str, Any]:
    """Reserve before each read transfer; never reattempt a partial stage.

    No source freeze, target document root mutation, database import,
    target runtime activation, state.json update or DNS operation is done.
    """
    _need(authorize_private_copy is True,
          "WARM_STAGE_EXPLICIT_PRIVATE_COPY_REQUIRED")
    bound = _identity(plan, original_tasks, actual_target_identity)
    private = _private_parent(plan, root)
    _need(not os.path.lexists(private),
          "WARM_STAGE_PRIOR_ATTEMPT_RETAINED")
    private.mkdir(mode=0o700)
    journal = private / "journal.json"
    record = {
        "schema": SCHEMA, "status": "INTENT_RECORDED",
        "plan_sha256": plan["plan_sha256"],
        "target_identity_sha256": plan["target_identity_sha256"],
        "original_task_count": 3, "site_count": 17,
        "completed": [],
        "active_domain": None,
        "original_target_untouched": True,
        "source_frozen": False,
        "source_target_parity_verified": False,
        "database_writes_performed": False,
        "cron_pm2_writes_performed": False,
        "cutover_allowed": False,
    }
    legacy.atomic_private_json(journal, record)
    import server_migration_pull as pull

    for task, site in bound:
        domain = site["domain"]
        token = hashlib.sha256(
            (task["migration_id"] + "|" + domain).encode()
        ).hexdigest()[:24]
        folder = private / ("site-" + token)
        _need(not os.path.lexists(folder),
              "WARM_STAGE_PRIVATE_SITE_PATH_CONFLICT")
        record["active_domain"] = domain
        record["status"] = "SOURCE_COPY_INTENT"
        legacy.atomic_private_json(journal, record)
        try:
            folder.mkdir(mode=0o700)
            pull.pull_path(
                task["source"], site["site_root"].rstrip("/") + "/",
                folder, delete=False,
                excludes=(pull.PROTECTED_DB_CONFIGS
                          if site["mysql_databases"] else ()),
            )
            digest = _tree_digest(folder)
            record["completed"].append({
                "domain": domain, "original_owner": task["migration_id"],
                "site_contract_sha256": next(
                    step["site_contract_sha256"]
                    for step in plan["steps"][:17]
                    if step["domain"] == domain
                ),
                "stage_tree_sha256": digest,
                "source_target_final_parity": False,
            })
            record["active_domain"] = None
            record["status"] = "SOURCE_COPY_VERIFIED_NOT_FINAL"
            legacy.atomic_private_json(journal, record)
        except Exception:
            record["status"] = "INTERRUPTED_RETAIN_PRIVATE_STAGE"
            legacy.atomic_private_json(journal, record)
            raise WarmStageBlocked(
                "WARM_STAGE_UNCERTAIN_WRITE_RETAIN_EVIDENCE"
            ) from None
    record["status"] = "ALL_17_PRIVATE_WARM_COPIES_NOT_FINAL"
    legacy.atomic_private_json(journal, record)
    return {
        "status": record["status"], "site_count": 17,
        "original_task_count": 3, "existing_target_modified": False,
        "database_writes_performed": False,
        "source_frozen": False,
        "source_target_final_parity": False, "cutover_allowed": False,
    }


def verify_private_seventeen_site_warm_copy(
    plan: Mapping[str, Any], *,
    root: Path,
) -> dict[str, Any]:
    """Read-only post-copy check. Not a frozen snapshot or cutover gate."""
    try:
        saga.validate_locked_plan(plan)
    except saga.SagaBlocked:
        raise WarmStageBlocked("WARM_STAGE_LOCKED_PLAN_INVALID") from None
    private = _private_parent(plan, root)
    receipt = saga._read_receipt(private / "journal.json",
                                expected_schema=SCHEMA)
    _need(receipt.get("status") == "ALL_17_PRIVATE_WARM_COPIES_NOT_FINAL"
          and receipt.get("plan_sha256") == plan["plan_sha256"]
          and receipt.get("target_identity_sha256")
          == plan["target_identity_sha256"]
          and receipt.get("source_frozen") is False
          and receipt.get("source_target_parity_verified") is False
          and receipt.get("cutover_allowed") is False
          and receipt.get("original_target_untouched") is True
          and receipt.get("database_writes_performed") is False
          and receipt.get("site_count") == 17,
          "WARM_STAGE_RECEIPT_INCOMPLETE_OR_TAMPERED")
    completed = receipt.get("completed")
    expected = {s["domain"]: s for s in plan["steps"][:17]}
    _need(type(completed) is list and len(completed) == 17
          and {x.get("domain") for x in completed
               if isinstance(x, dict)} == set(expected),
          "WARM_STAGE_COMPLETION_SET_CHANGED")
    for row in completed:
        step = expected[row["domain"]]
        _need(row.get("original_owner") == step["owner"]
              and row.get("site_contract_sha256")
              == step["site_contract_sha256"]
              and row.get("source_target_final_parity") is False,
              "WARM_STAGE_ORIGINAL_OWNER_DRIFT")
        token = hashlib.sha256(
            (step["owner"] + "|" + step["domain"]).encode()
        ).hexdigest()[:24]
        folder = private / ("site-" + token)
        _need(_tree_digest(folder) == row.get("stage_tree_sha256"),
              "WARM_STAGE_PRIVATE_COPY_CHANGED")
    return {
        "status": "ALL_17_PRIVATE_WARM_COPIES_VERIFIED_NOT_FINAL",
        "site_count": 17, "source_final_snapshot": "NOT_VERIFIED",
        "existing_target_modified": False, "cutover_allowed": False,
        "writes_performed": False,
    }
