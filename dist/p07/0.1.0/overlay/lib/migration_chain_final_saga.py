"""Private 17-site cross-owner final-sync saga journal.

The product has three *different* existing migration owners. Repeating a
partially completed sync after a crash can overwrite target business files.
This module therefore records a durable operation intent BEFORE every call,
never automatically replays an uncertain intent and compensates completed
steps in reverse order. The caller supplies byte-verified reversible
operations; this module deliberately has NO CLI, source-freeze, DNS,
production activation, database import or shell implementation.

The final migration remains blocked until a separately reviewed owner-gated
executor wires trusted operations, real recovery points, and original state
rehydration. Synthetic tests exercise the actual journal and callback order.
"""
from __future__ import annotations

import fcntl
import hashlib
import ipaddress
import json
import os
import shutil
import sqlite3
from urllib.parse import quote
from pathlib import Path
import stat
import tempfile
from typing import Any, Callable, Mapping

import server_migration as legacy
import migration_chain_consolidation as consolidated

SCHEMA = "P07_CHAIN_FINAL_SAGA_JOURNAL_V1"
PHASES = ("SITE_FILES", "EXTERNAL_ASSETS", "SQLITE_SNAPSHOTS",
          "DATABASE_SHADOWS", "APPLICATION_MAPPINGS")
MAX_BYTES = 1024 * 1024


class SagaBlocked(RuntimeError):
    pass


def need(value: bool, reason: str) -> None:
    if not value:
        raise SagaBlocked(reason)


def _encoded(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":")).encode("ascii")


def operation_plan(execution_scope: Mapping[str, Any]) -> dict[str, Any]:
    """Inventory each original owner exactly once; do not infer migration PASS.

    An initial 14/17 partial state is accepted as a LOCKED plan only:
    it cannot start a durable transaction or mutate any site.
    """
    need(isinstance(execution_scope, dict)
         and execution_scope.get("schema")
         == "P07_17_SITE_RECOVERY_EXECUTION_SCOPE_V1"
         and execution_scope.get("status")
         == "OWNERSHIP_RESOLVED_EXECUTION_BLOCKED"
         and execution_scope.get("site_count") == 17
         and execution_scope.get("source_task_count") == 3
         and execution_scope.get("cutover_allowed") is False
         and execution_scope.get("source_freeze_allowed") is False,
         "CHAIN_SAGA_SCOPE_UNVERIFIED")
    rows = execution_scope.get("sites")
    need(isinstance(rows, list) and len(rows) == 17,
         "CHAIN_SAGA_SITE_COUNT_DRIFT")
    ids, owners = set(), set()
    for name in ("site_owner_scope_sha256", "source_identity_sha256",
                 "target_identity_sha256"):
        val = execution_scope.get(name)
        need(isinstance(val, str) and len(val) == 64 and
             all(ch in "0123456789abcdef" for ch in val),
             "CHAIN_SAGA_IDENTITY_DIGEST_UNVERIFIED")
    steps: list[dict[str, Any]] = []
    for site in rows:
        need(isinstance(site, dict), "CHAIN_SAGA_SITE_INVALID")
        domain, owner, index = (site.get("domain"),
                                site.get("owner_migration_id"),
                                site.get("owner_index"))
        need(isinstance(domain, str) and domain and domain not in ids
             and isinstance(owner, str)
             and legacy.SAFE_ID_RE.fullmatch(owner) is not None
             and type(index) is int and 0 <= index < 250
             and site.get("stage_status") in {"PULLED_STAGED", "PENDING"},
             "CHAIN_SAGA_SITE_OWNER_AMBIGUOUS")
        contract = site.get("site_contract_sha256")
        need(isinstance(contract, str) and len(contract) == 64 and
             all(ch in "0123456789abcdef" for ch in contract),
             "CHAIN_SAGA_SITE_CONTRACT_UNVERIFIED")
        ids.add(domain)
        owners.add(owner)
        steps.append({"phase": "SITE_FILES", "domain": domain,
                      "owner": owner, "index": index,
                      "site_contract_sha256": contract})
    need(len(ids) == 17 and len(owners) == 3,
         "CHAIN_SAGA_OWNER_COVERAGE_INCOMPLETE")
    actual_scope = hashlib.sha256(_encoded({
        "sites": [(s["domain"], s["owner_migration_id"], s["owner_index"],
                   s["stage_status"], s["site_contract_sha256"]) for s in rows],
        "source": execution_scope["source_identity_sha256"],
        "target": execution_scope["target_identity_sha256"],
    })).hexdigest()
    need(actual_scope == execution_scope["site_owner_scope_sha256"],
         "CHAIN_SAGA_SCOPE_DIGEST_DRIFT")
    for phase in PHASES[1:]:
        steps.append({"phase": phase, "domain": "", "owner": "", "index": -1})
    pending = [site["domain"] for site in rows
               if site["stage_status"] == "PENDING"]
    blockers = execution_scope.get("blockers")
    need(isinstance(blockers, list) and all(
        isinstance(x, str) for x in blockers),
        "CHAIN_SAGA_BLOCKERS_UNVERIFIED")
    plan_hash = hashlib.sha256(_encoded({
        "scope": execution_scope.get("site_owner_scope_sha256"),
        "steps": steps,
        "pending": pending,
        "blockers": sorted(set(blockers)),
    })).hexdigest()
    return {
        "schema": "P07_CHAIN_FINAL_SAGA_PLAN_V1",
        "status": "LOCKED_AWAITING_ORIGINAL_RECOVERY_AND_FINAL_PROOF",
        "site_count": 17,
        "original_task_count": 3,
        "steps": steps,
        "step_count": len(steps),
        "scope_sha256": execution_scope.get("site_owner_scope_sha256"),
        "source_identity_sha256": execution_scope["source_identity_sha256"],
        "target_identity_sha256": execution_scope["target_identity_sha256"],
        "plan_sha256": plan_hash,
        "pending_domains": pending,
        "blockers": sorted(set(blockers)),
        "recovery_snapshots_verified": False,
        "source_snapshot_frozen": False,
        "database_import_allowed": False,
        "source_freeze_allowed": False,
        "cutover_allowed": False,
        "writes_performed": False,
    }


def _safe_journal_dir(directory: Path) -> None:
    need(directory.is_absolute() and not directory.is_symlink()
         and directory.is_dir(), "CHAIN_SAGA_DIRECTORY_UNSAFE")
    # There is intentionally no production-mode API. Even if a caller sets
    # the synthetic fixture variable, refuse a persistent CP2 state root.
    temporary_root = Path(tempfile.gettempdir()).resolve()
    resolved = directory.resolve(strict=True)
    need(resolved != temporary_root and
         resolved.is_relative_to(temporary_root),
         "CHAIN_SAGA_REAL_FILESYSTEM_ROOT_DENIED")
    mode = directory.stat()
    need(mode.st_uid == os.geteuid() and
         not stat.S_IMODE(mode.st_mode) & 0o077,
         "CHAIN_SAGA_DIRECTORY_PERMISSIONS_UNSAFE")


def _read_receipt(path: Path, *, expected_schema: str = SCHEMA) -> dict[str, Any]:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                 and info.st_uid == os.geteuid()
                 and not stat.S_IMODE(info.st_mode) & 0o077
                 and 0 < info.st_size <= MAX_BYTES,
                 "CHAIN_SAGA_RECEIPT_UNSAFE")
            with os.fdopen(os.dup(fd), "rb") as stream:
                data = stream.read(MAX_BYTES + 1)
            need(len(data) == info.st_size,
                 "CHAIN_SAGA_RECEIPT_READ_DRIFT")
            obj = json.loads(data)
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeDecodeError):
        raise SagaBlocked("CHAIN_SAGA_RECEIPT_UNAVAILABLE") from None
    need(isinstance(obj, dict) and obj.get("schema") == expected_schema,
         "CHAIN_SAGA_RECEIPT_SCHEMA_INVALID")
    return obj


def _lock(directory: Path) -> int:
    _safe_journal_dir(directory)
    path = directory / ".saga-lock"
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        s = os.fstat(fd)
        if not (stat.S_ISREG(s.st_mode) and s.st_uid == os.geteuid()
                and not stat.S_IMODE(s.st_mode) & 0o077):
            os.close(fd)
            raise SagaBlocked("CHAIN_SAGA_LOCK_UNSAFE")
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd
    except OSError:
        raise SagaBlocked("CHAIN_SAGA_LOCK_UNAVAILABLE") from None


def _save(path: Path, record: dict[str, Any]) -> None:
    legacy.atomic_private_json(path, record)



def validate_locked_plan(plan: Mapping[str, Any]) -> None:
    """Rehash the entire 21-step locked scope before any synthetic write."""
    need(isinstance(plan, dict) and
         plan.get("schema") == "P07_CHAIN_FINAL_SAGA_PLAN_V1" and
         plan.get("status") == "LOCKED_AWAITING_ORIGINAL_RECOVERY_AND_FINAL_PROOF"
         and plan.get("site_count") == 17 and
         plan.get("original_task_count") == 3 and
         plan.get("step_count") == 21 and
         plan.get("recovery_snapshots_verified") is False and
         plan.get("source_snapshot_frozen") is False and
         plan.get("database_import_allowed") is False and
         plan.get("source_freeze_allowed") is False and
         plan.get("cutover_allowed") is False and
         plan.get("writes_performed") is False,
         "CHAIN_SAGA_LOCKED_PLAN_BOUNDARY_CHANGED")
    for key in ("scope_sha256", "source_identity_sha256",
                "target_identity_sha256", "plan_sha256"):
        value = plan.get(key)
        need(isinstance(value, str) and len(value) == 64 and
             all(ch in "0123456789abcdef" for ch in value),
             "CHAIN_SAGA_LOCKED_PLAN_DIGEST_INVALID")
    steps = plan.get("steps")
    need(isinstance(steps, list) and len(steps) == 21,
         "CHAIN_SAGA_LOCKED_PLAN_STEPS_CHANGED")
    keys, owners = set(), set()
    for s in steps[:17]:
        need(isinstance(s, dict) and s.get("phase") == "SITE_FILES"
             and isinstance(s.get("domain"), str) and s["domain"]
             and isinstance(s.get("owner"), str) and
             legacy.SAFE_ID_RE.fullmatch(s["owner"]) is not None
             and type(s.get("index")) is int and 0 <= s["index"] < 250,
             "CHAIN_SAGA_LOCKED_PLAN_ORIGINAL_OWNER_INVALID")
        contract = s.get("site_contract_sha256")
        need(isinstance(contract, str) and len(contract) == 64 and
             all(ch in "0123456789abcdef" for ch in contract)
             and s["domain"] not in keys,
             "CHAIN_SAGA_LOCKED_PLAN_CONTRACT_INVALID")
        keys.add(s["domain"])
        owners.add(s["owner"])
    need(len(keys) == 17 and len(owners) == 3 and
         steps[17:] == [{"phase": phase, "domain": "",
                         "owner": "", "index": -1}
                        for phase in PHASES[1:]],
         "CHAIN_SAGA_LOCKED_PLAN_PHASE_CHANGED")
    pending, blockers = plan.get("pending_domains"), plan.get("blockers")
    need(isinstance(pending, list) and
         all(isinstance(d, str) and d in keys for d in pending) and
         len(pending) == len(set(pending)) and
         isinstance(blockers, list) and
         all(isinstance(b, str) for b in blockers) and
         blockers == sorted(set(blockers)),
         "CHAIN_SAGA_LOCKED_PLAN_BLOCKERS_CHANGED")
    digest = hashlib.sha256(_encoded({
        "scope": plan["scope_sha256"], "steps": steps,
        "pending": pending, "blockers": blockers,
    })).hexdigest()
    need(digest == plan["plan_sha256"],
         "CHAIN_SAGA_LOCKED_PLAN_DIGEST_DRIFT")


def start_synthetic_rehearsal(plan: Mapping[str, Any], directory: Path,
                              *, synthetic_authority: bool = False) -> dict[str, Any]:
    """Build an isolated test-only receipt, NEVER authorize a CP2 execution.

    A real executor must use separately authorized high-risk preflight and
    recovery points; making a locked plan is not permission to start.
    """
    need(synthetic_authority is True and
         os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
         "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED")
    need(plan.get("schema") == "P07_CHAIN_FINAL_SAGA_PLAN_V1"
         and plan.get("cutover_allowed") is False
         and plan.get("source_freeze_allowed") is False,
         "CHAIN_SAGA_PLAN_UNTRUSTED")
    validate_locked_plan(plan)
    fd = _lock(directory)
    try:
        path = directory / "journal.json"
        need(not os.path.lexists(path), "CHAIN_SAGA_EXISTING_ATTEMPT_RETAINED")
        steps = plan.get("steps")
        need(isinstance(steps, list) and len(steps) == 21
             and len([x for x in steps if x.get("phase") == "SITE_FILES"]) == 17,
             "CHAIN_SAGA_STEP_SCOPE_INVALID")
        record = {
            "schema": SCHEMA, "status": "REHEARSAL_ONLY",
            "scope_sha256": plan.get("scope_sha256"),
            "plan_sha256": plan.get("plan_sha256"),
            "steps": [{
                "phase": x["phase"], "domain": x["domain"],
                "owner": x["owner"], "index": x["index"],
                **({"site_contract_sha256": x["site_contract_sha256"]}
                   if x["phase"] == "SITE_FILES" else {}),
                "status": "NOT_STARTED",
            } for x in steps],
            "cutover_allowed": False, "source_freeze_allowed": False,
            "real_target_writes_allowed": False, "synthetic_only": True,
        }
        _save(path, record)
        return record
    finally:
        os.close(fd)


def _assert_rehearsal(record: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
    validate_locked_plan(plan)
    need(record.get("status") in {"REHEARSAL_ONLY", "REHEARSAL_FAILED",
                                  "REHEARSAL_ROLLED_BACK", "RECOVERY_REQUIRED"}
         and record.get("synthetic_only") is True
         and record.get("cutover_allowed") is False
         and record.get("source_freeze_allowed") is False
         and record.get("real_target_writes_allowed") is False
         and record.get("plan_sha256") == plan.get("plan_sha256")
         and record.get("scope_sha256") == plan.get("scope_sha256"),
         "CHAIN_SAGA_JOURNAL_SCOPE_CHANGED")
    planned = plan.get("steps")
    steps = record.get("steps")
    need(isinstance(planned, list) and isinstance(steps, list)
         and len(planned) == len(steps) == 21,
         "CHAIN_SAGA_JOURNAL_STEPS_CHANGED")
    for ref, step in zip(planned, steps):
        need(isinstance(step, dict)
             and all(step.get(name) == ref.get(name)
                     for name in ("phase", "domain", "owner", "index",
                                  "site_contract_sha256"))
             and step.get("status") in {
                 "NOT_STARTED", "INTENT_RESERVED", "COMPLETED",
                 "ROLLBACK_INTENT", "ROLLED_BACK", "ROLLBACK_FAILED",
             }, "CHAIN_SAGA_JOURNAL_STEP_CHANGED")


def execute_synthetic_rehearsal(
    plan: Mapping[str, Any], directory: Path,
    *,
    apply: Callable[[Mapping[str, Any]], None],
    compensate: Callable[[Mapping[str, Any]], bool],
) -> dict[str, Any]:
    """Exercise durable compensations; never replay a prior unknown attempt.

    NOTE: no Python/CLI code path can enable real server operations. The
    explicit fixture environment and test-only interface are not a real gate.
    """
    need(os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
         "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED")
    fd = _lock(directory)
    try:
        path = directory / "journal.json"
        record = _read_receipt(path)
        _assert_rehearsal(record, plan)
        need(record["status"] == "REHEARSAL_ONLY"
             and all(x["status"] == "NOT_STARTED" for x in record["steps"]),
             "CHAIN_SAGA_PRIOR_INTENT_RECOVERY_REQUIRED")
        try:
            for i, item in enumerate(record["steps"]):
                item["status"] = "INTENT_RESERVED"
                _save(path, record)
                apply(dict(item))
                item["status"] = "COMPLETED"
                _save(path, record)
        except Exception:
            record["status"] = "REHEARSAL_FAILED"
            _save(path, record)
            # The in-flight INTENT may have produced a partial effect; it
            # MUST be compensated too. Nothing is ever automatically replayed.
            failed = 0
            for item in reversed(record["steps"]):
                if item["status"] not in ("COMPLETED", "INTENT_RESERVED"):
                    continue
                item["status"] = "ROLLBACK_INTENT"
                _save(path, record)
                try:
                    safe = compensate(dict(item)) is True
                except Exception:
                    safe = False
                item["status"] = "ROLLED_BACK" if safe else "ROLLBACK_FAILED"
                _save(path, record)
                failed += int(not safe)
            record["status"] = ("RECOVERY_REQUIRED" if failed
                                else "REHEARSAL_ROLLED_BACK")
            _save(path, record)
            raise SagaBlocked(
                "CHAIN_SAGA_REHEARSAL_PARTIAL_RECOVERY_REQUIRED"
                if failed else "CHAIN_SAGA_REHEARSAL_FAILED_ROLLED_BACK"
            ) from None
        record["status"] = "REHEARSAL_ONLY"
        record["completed_count"] = len(record["steps"])
        _save(path, record)
        return {"status": "SYNTHETIC_ALL_STEPS_EXECUTED_NOT_CUTOVER_READY",
                "step_count": len(record["steps"]), "cutover_allowed": False}
    finally:
        os.close(fd)


def inspect_recovery(plan: Mapping[str, Any], directory: Path) -> dict[str, Any]:
    """Read-only crash classification; no replay, rollback or source writes."""
    _safe_journal_dir(directory)
    record = _read_receipt(directory / "journal.json")
    _assert_rehearsal(record, plan)
    states = [x["status"] for x in record["steps"]]
    uncertain = sum(x in {"INTENT_RESERVED", "ROLLBACK_INTENT",
                          "ROLLBACK_FAILED"} for x in states)
    return {
        "status": ("MANUAL_RECOVERY_REQUIRED" if uncertain else record["status"]),
        "completed_count": states.count("COMPLETED"),
        "rolled_back_count": states.count("ROLLED_BACK"),
        "uncertain_count": uncertain,
        "cutover_allowed": False, "writes_performed": False,
    }

def stage_isolated_site_files(
    plan: Mapping[str, Any], step: Mapping[str, Any],
    owner_state: Mapping[str, Any], directory: Path,
    *, synthetic_authority: bool = False,
) -> dict[str, Any]:
    """Real pull_path wiring, but only into an isolated synthetic shadow.

    Not a complete final sync: source was not frozen and the existing CP2
    webroot is intentionally not read or modified. A recorded in-flight
    attempt can never be automatically retried.
    """
    need(synthetic_authority is True and
         os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
         "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED")
    need(plan.get("schema") == "P07_CHAIN_FINAL_SAGA_PLAN_V1"
         and plan.get("cutover_allowed") is False
         and step in plan.get("steps", [])
         and step.get("phase") == "SITE_FILES",
         "CHAIN_SAGA_FILE_SCOPE_UNVERIFIED")
    validate_locked_plan(plan)
    fd = _lock(directory)
    try:
        idx = step.get("index")
        rows = owner_state.get("sites")
        need(owner_state.get("migration_id") == step.get("owner") and
             type(idx) is int and isinstance(rows, list) and
             0 <= idx < len(rows) and isinstance(rows[idx], dict),
             "CHAIN_SAGA_ORIGINAL_OWNER_CHANGED")
        site = rows[idx]
        contract = hashlib.sha256(_encoded(
            consolidated._site_contract(site))).hexdigest()
        need(site.get("domain") == step.get("domain") and
             contract == step.get("site_contract_sha256"),
             "CHAIN_SAGA_SITE_CONTRACT_CHANGED")
        source_connection = owner_state.get("source")
        # A synthetic fixture must never accidentally dial the real old VPS,
        # even if someone sets P07_SYNTHETIC_SAGA_FIXTURE on CP2.
        need(isinstance(source_connection, dict) and
             isinstance(source_connection.get("host"), str) and
             source_connection["host"].endswith(".example.test") and
             isinstance(source_connection.get("ip"), str),
             "CHAIN_SAGA_SYNTHETIC_REMOTE_REQUIRED")
        try:
            ip = ipaddress.ip_address(source_connection["ip"])
            allowed = any(ip in ipaddress.ip_network(subnet) for subnet in (
                "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"))
        except ValueError:
            allowed = False
        need(allowed, "CHAIN_SAGA_SYNTHETIC_REMOTE_REQUIRED")
        try:
            source = consolidated._original_source_identity(owner_state)
        except consolidated.ConsolidationBlocked:
            raise SagaBlocked("CHAIN_SAGA_SOURCE_IDENTITY_UNVERIFIED") from None
        need(hashlib.sha256(_encoded(source)).hexdigest() ==
             plan.get("source_identity_sha256") and
             hashlib.sha256(str(owner_state.get(
                 "target_server_identity", "")).encode()).hexdigest() ==
             plan.get("target_identity_sha256"),
             "CHAIN_SAGA_SERVER_IDENTITY_CHANGED")
        original_path = site.get("site_root")
        databases = site.get("mysql_databases")
        need(isinstance(original_path, str) and
             Path(original_path).is_absolute() and
             ".." not in Path(original_path).parts and
             original_path != "/" and
             isinstance(databases, list) and len(databases) <= 1,
             "CHAIN_SAGA_ORIGINAL_PATH_UNVERIFIED")
        token = hashlib.sha256(
            (str(step["owner"]) + "|" + str(step["domain"])).encode()
        ).hexdigest()[:24]
        receipt_path = directory / ("site-" + token + ".json")
        private_shadow = directory / ("site-" + token + "-shadow")
        need(not os.path.lexists(receipt_path) and
             not os.path.lexists(private_shadow),
             "CHAIN_SAGA_PREVIOUS_FILE_INTENT_RETAINED")
        receipt = {
            "schema": "P07_CHAIN_FILE_SHADOW_V1", "status": "INTENT_RESERVED",
            "plan_sha256": plan["plan_sha256"],
            "site_contract_sha256": contract, "original_owner": step["owner"],
            "domain": step["domain"], "private_shadow_only": True,
            "original_target_untouched": True, "cutover_allowed": False,
        }
        _save(receipt_path, receipt)
        try:
            private_shadow.mkdir(mode=0o700)
            import server_migration_pull as pull  # lazy: avoid import cycle
            pull.pull_path(owner_state["source"],
                           original_path.rstrip("/") + "/",
                           private_shadow, delete=False,
                           excludes=(pull.PROTECTED_DB_CONFIGS
                                     if databases else ()))
            # Shared byte/mode/symlink/hardlink readback authority used again
            # before taking the recovery point, promotion and rollback.
            receipt["stage_readback_sha256"] = _synthetic_tree_hash(
                private_shadow)
            receipt["status"] = "PRIVATE_STAGE_SOURCE_PARITY_NOT_PROVEN"
            _save(receipt_path, receipt)
        except Exception:
            receipt["status"] = "RECOVERY_REQUIRED_RETAIN_SHADOW"
            _save(receipt_path, receipt)
            raise SagaBlocked("CHAIN_SAGA_SHADOW_RECOVERY_REQUIRED") from None
        return dict(receipt)
    finally:
        os.close(fd)



def _site_file_token(step: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        (str(step["owner"]) + "|" + str(step["domain"])).encode()
    ).hexdigest()[:24]


def _synthetic_target_paths(directory: Path, step: Mapping[str, Any]) -> dict[str, Path]:
    token = _site_file_token(step)
    return {
        "shadow": directory / ("site-" + token + "-shadow"),
        "stage": directory / ("site-" + token + ".json"),
        "target": directory / ("site-" + token + "-target"),
        "snapshot": directory / ("site-" + token + "-recovery"),
        "journal": directory / ("site-" + token + "-recovery.json"),
        "next": directory / ("site-" + token + "-next"),
        "held": directory / ("site-" + token + "-held"),
        "failed": directory / ("site-" + token + "-failed"),
    }


def _synthetic_tree_hash(root: Path) -> str:
    """Byte and mode readback. Reject symlinks, special files and hardlinks.

    The existing real sync may legitimately encounter symlinks/hardlinks; this
    conservative isolated executor does NOT claim those are production-ready.
    """
    need(not root.is_symlink() and root.is_dir(),
         "CHAIN_SAGA_TREE_ROOT_UNSAFE")
    rows: list[list[Any]] = []
    def walk(path: Path, rel: str) -> None:
        info = path.lstat()
        need(not stat.S_ISLNK(info.st_mode),
             "CHAIN_SAGA_TREE_SYMLINK_OR_SPECIAL")
        need(info.st_uid == os.geteuid() and
             not stat.S_IMODE(info.st_mode) & 0o002,
             "CHAIN_SAGA_TREE_OWNER_OR_MODE_UNSAFE")
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISDIR(info.st_mode):
            rows.append([rel + "/", "directory", mode])
            for child in sorted(path.iterdir(), key=lambda item: item.name):
                walk(child, rel + "/" + child.name if rel else child.name)
        elif stat.S_ISREG(info.st_mode):
            need(info.st_nlink == 1, "CHAIN_SAGA_TREE_HARDLINK_UNSAFE")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1048576), b""):
                    digest.update(chunk)
            rows.append([rel, "file", mode, info.st_size, digest.hexdigest()])
        else:
            raise SagaBlocked("CHAIN_SAGA_TREE_SYMLINK_OR_SPECIAL")
    walk(root, "")
    need(any(row[1] == "file" for row in rows),
         "CHAIN_SAGA_TREE_HAS_NO_FILES")
    return hashlib.sha256(_encoded(rows)).hexdigest()


def _verify_synthetic_stage(
    plan: Mapping[str, Any], step: Mapping[str, Any], directory: Path
) -> tuple[dict[str, Path], dict[str, Any], str]:
    validate_locked_plan(plan)
    need(isinstance(step, dict) and step in plan["steps"] and
         step.get("phase") == "SITE_FILES",
         "CHAIN_SAGA_RECOVERY_SCOPE_UNVERIFIED")
    paths = _synthetic_target_paths(directory, step)
    record = _read_receipt(
        paths["stage"], expected_schema="P07_CHAIN_FILE_SHADOW_V1")
    need(record.get("status") == "PRIVATE_STAGE_SOURCE_PARITY_NOT_PROVEN" and
         record.get("plan_sha256") == plan["plan_sha256"] and
         record.get("site_contract_sha256") ==
         step["site_contract_sha256"] and
         record.get("original_owner") == step["owner"] and
         record.get("domain") == step["domain"] and
         record.get("original_target_untouched") is True and
         record.get("private_shadow_only") is True and
         record.get("cutover_allowed") is False,
         "CHAIN_SAGA_STAGE_RECEIPT_UNVERIFIED")
    stage_hash = _synthetic_tree_hash(paths["shadow"])
    need(stage_hash == record.get("stage_readback_sha256"),
         "CHAIN_SAGA_STAGE_DRIFT")
    return paths, record, stage_hash


def _verify_recovery_receipt(
    plan: Mapping[str, Any], step: Mapping[str, Any],
    paths: Mapping[str, Path], stage_hash: str,
) -> dict[str, Any]:
    receipt = _read_receipt(
        paths["journal"], expected_schema="P07_CHAIN_TARGET_RECOVERY_V1")
    need(receipt.get("plan_sha256") == plan["plan_sha256"] and
         receipt.get("site_contract_sha256") ==
         step["site_contract_sha256"] and
         receipt.get("original_owner") == step["owner"] and
         receipt.get("domain") == step["domain"] and
         receipt.get("stage_sha256") == stage_hash and
         receipt.get("synthetic_only") is True and
         receipt.get("cutover_allowed") is False and
         receipt.get("target_recovery_verified") is True,
         "CHAIN_SAGA_TARGET_RECOVERY_BINDING_CHANGED")
    original_hash = receipt.get("target_before_sha256")
    need(isinstance(original_hash, str) and len(original_hash) == 64 and
         _synthetic_tree_hash(paths["snapshot"]) == original_hash,
         "CHAIN_SAGA_TARGET_RECOVERY_DRIFT")
    return receipt


def snapshot_isolated_target(
    plan: Mapping[str, Any], step: Mapping[str, Any], directory: Path,
    *, synthetic_authority: bool = False,
) -> dict[str, Any]:
    """Take a private, readback-verified target recovery point BEFORE overwrite.

    The destination is a uniquely derived directory under the test sandbox,
    never an arbitrary filesystem path or the live CP2 webroot.
    """
    need(synthetic_authority is True and
         os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
         "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED")
    fd = _lock(directory)
    try:
        paths, _stage, stage_hash = _verify_synthetic_stage(
            plan, step, directory)
        need(not os.path.lexists(paths["journal"]) and
             not os.path.lexists(paths["snapshot"]),
             "CHAIN_SAGA_RECOVERY_ALREADY_ATTEMPTED")
        need(paths["target"].is_dir() and
             not paths["target"].is_symlink() and
             paths["target"].stat().st_uid == os.geteuid() and
             not stat.S_IMODE(paths["target"].stat().st_mode) & 0o077,
             "CHAIN_SAGA_TARGET_NOT_PRIVATE_FIXTURE")
        before = _synthetic_tree_hash(paths["target"])
        receipt = {
            "schema": "P07_CHAIN_TARGET_RECOVERY_V1",
            "status": "RECOVERY_INTENT_RESERVED",
            "plan_sha256": plan["plan_sha256"],
            "site_contract_sha256": step["site_contract_sha256"],
            "original_owner": step["owner"], "domain": step["domain"],
            "stage_sha256": stage_hash, "target_before_sha256": before,
            "synthetic_only": True, "target_recovery_verified": False,
            "cutover_allowed": False,
        }
        _save(paths["journal"], receipt)
        try:
            shutil.copytree(paths["target"], paths["snapshot"],
                            symlinks=True)
            need(_synthetic_tree_hash(paths["snapshot"]) == before,
                 "CHAIN_SAGA_RECOVERY_COPY_MISMATCH")
            need(_synthetic_tree_hash(paths["target"]) == before,
                 "CHAIN_SAGA_TARGET_CHANGED_DURING_SNAPSHOT")
            receipt["status"] = "RECOVERY_POINT_VERIFIED"
            receipt["target_recovery_verified"] = True
            _save(paths["journal"], receipt)
            return dict(receipt)
        except Exception:
            receipt["status"] = "RECOVERY_UNKNOWN_RETAIN_EVIDENCE"
            _save(paths["journal"], receipt)
            raise SagaBlocked("CHAIN_SAGA_RECOVERY_COPY_UNKNOWN") from None
    finally:
        os.close(fd)


def replace_isolated_target_from_stage(
    plan: Mapping[str, Any], step: Mapping[str, Any], directory: Path,
    *, synthetic_authority: bool = False,
) -> dict[str, Any]:
    """Two-rename synthetic promotion, with retained original + recovery point.

    Crash gaps stay UNKNOWN. No real CP2 path can be passed to this API.
    """
    need(synthetic_authority is True and
         os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
         "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED")
    fd = _lock(directory)
    try:
        paths, _stage, stage_hash = _verify_synthetic_stage(
            plan, step, directory)
        receipt = _verify_recovery_receipt(
            plan, step, paths, stage_hash)
        need(receipt.get("status") == "RECOVERY_POINT_VERIFIED",
             "CHAIN_SAGA_PROMOTION_PREVIOUS_INTENT_BLOCKED")
        need(not os.path.lexists(paths["next"]) and
             not os.path.lexists(paths["held"]) and
             not os.path.lexists(paths["failed"]),
             "CHAIN_SAGA_PROMOTION_EXISTING_DATA_BLOCKED")
        need(_synthetic_tree_hash(paths["target"]) ==
             receipt["target_before_sha256"],
             "CHAIN_SAGA_TARGET_DRIFT_BEFORE_OVERWRITE")
        # Prepare the new tree without touching the existing target.
        try:
            shutil.copytree(paths["shadow"], paths["next"], symlinks=True)
            need(_synthetic_tree_hash(paths["next"]) == stage_hash,
                 "CHAIN_SAGA_PROMOTION_COPY_MISMATCH")
            need(_synthetic_tree_hash(paths["target"]) ==
                 receipt["target_before_sha256"],
                 "CHAIN_SAGA_TARGET_CHANGED_BEFORE_PROMOTION")
        except Exception:
            receipt["status"] = "PROMOTION_COPY_UNKNOWN_RETAIN_EVIDENCE"
            _save(paths["journal"], receipt)
            raise SagaBlocked("CHAIN_SAGA_PROMOTION_PREPARE_UNKNOWN") from None
        receipt["status"] = "PROMOTION_INTENT_RESERVED"
        _save(paths["journal"], receipt)
        try:
            os.rename(paths["target"], paths["held"])
            os.rename(paths["next"], paths["target"])
            need(_synthetic_tree_hash(paths["target"]) == stage_hash and
                 _synthetic_tree_hash(paths["held"]) ==
                 receipt["target_before_sha256"],
                 "CHAIN_SAGA_PROMOTION_POST_READBACK_FAILED")
            receipt["status"] = "PROMOTED_NOT_CUTOVER"
            _save(paths["journal"], receipt)
            return dict(receipt)
        except Exception:
            receipt["status"] = "PROMOTION_UNKNOWN_MANUAL_RECONCILIATION"
            _save(paths["journal"], receipt)
            raise SagaBlocked("CHAIN_SAGA_PROMOTION_STATE_UNKNOWN") from None
    finally:
        os.close(fd)


def rollback_isolated_target_replacement(
    plan: Mapping[str, Any], step: Mapping[str, Any], directory: Path,
    *, synthetic_authority: bool = False,
) -> dict[str, Any]:
    """Explicit reverse restore only from a verified completed promotion.

    If an intent was interrupted, never guess which of the two renames ran.
    A changed target is also retained and the rollback is refused.
    """
    need(synthetic_authority is True and
         os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
         "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED")
    fd = _lock(directory)
    try:
        paths, _stage, stage_hash = _verify_synthetic_stage(
            plan, step, directory)
        receipt = _verify_recovery_receipt(
            plan, step, paths, stage_hash)
        need(receipt.get("status") == "PROMOTED_NOT_CUTOVER",
             "CHAIN_SAGA_ROLLBACK_UNCERTAIN_OR_ALREADY_DONE")
        need(not os.path.lexists(paths["failed"]) and
             not os.path.lexists(paths["next"]) and
             _synthetic_tree_hash(paths["target"]) == stage_hash and
             _synthetic_tree_hash(paths["held"]) ==
             receipt["target_before_sha256"],
             "CHAIN_SAGA_ROLLBACK_POST_WRITE_DRIFT")
        receipt["status"] = "ROLLBACK_INTENT_RESERVED"
        _save(paths["journal"], receipt)
        try:
            os.rename(paths["target"], paths["failed"])
            os.rename(paths["held"], paths["target"])
            need(_synthetic_tree_hash(paths["target"]) ==
                 receipt["target_before_sha256"],
                 "CHAIN_SAGA_ROLLBACK_READBACK_FAILED")
            receipt["status"] = "ROLLED_BACK_VERIFIED"
            _save(paths["journal"], receipt)
            return dict(receipt)
        except Exception:
            receipt["status"] = "ROLLBACK_UNKNOWN_MANUAL_RECONCILIATION"
            _save(paths["journal"], receipt)
            raise SagaBlocked("CHAIN_SAGA_ROLLBACK_STATE_UNKNOWN") from None
    finally:
        os.close(fd)

def abandon_isolated_site_file_shadow(
    plan: Mapping[str, Any], step: Mapping[str, Any], directory: Path,
    *, synthetic_authority: bool = False,
) -> bool:
    """Synthetic reverse compensation: retain the private stage and evidence.

    A completed private copy is reversible because it never modified the
    original target. An INTENT_RESERVED or failed transfer is UNKNOWN and
    must not be marked rolled back; no directory deletion or copy replay.
    """
    need(synthetic_authority is True and
         os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
         "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED")
    validate_locked_plan(plan)
    need(isinstance(step, dict) and step in plan["steps"] and
         step.get("phase") == "SITE_FILES",
         "CHAIN_SAGA_ROLLBACK_STEP_NOT_IN_PLAN")
    fd = _lock(directory)
    try:
        token = hashlib.sha256(
            (str(step["owner"]) + "|" + str(step["domain"])).encode()
        ).hexdigest()[:24]
        path = directory / ("site-" + token + ".json")
        shadow = directory / ("site-" + token + "-shadow")
        record = _read_receipt(
            path, expected_schema="P07_CHAIN_FILE_SHADOW_V1")
        need(record.get("plan_sha256") == plan["plan_sha256"] and
             record.get("site_contract_sha256") ==
             step["site_contract_sha256"] and
             record.get("original_owner") == step["owner"] and
             record.get("domain") == step["domain"] and
             record.get("private_shadow_only") is True and
             record.get("original_target_untouched") is True and
             record.get("cutover_allowed") is False,
             "CHAIN_SAGA_ROLLBACK_BINDING_CHANGED")
        need(shadow.is_dir() and not shadow.is_symlink() and
             shadow.stat().st_uid == os.geteuid() and
             not stat.S_IMODE(shadow.stat().st_mode) & 0o077,
             "CHAIN_SAGA_ROLLBACK_SHADOW_UNSAFE")
        if record.get("status") != "PRIVATE_STAGE_SOURCE_PARITY_NOT_PROVEN":
            return False
        digest = record.get("stage_readback_sha256")
        need(isinstance(digest, str) and len(digest) == 64 and
             all(ch in "0123456789abcdef" for ch in digest),
             "CHAIN_SAGA_ROLLBACK_READBACK_UNVERIFIED")
        record["status"] = "ABANDONED_RETAINED_NOT_PROMOTED"
        _save(path, record)
        return True
    finally:
        os.close(fd)



def _resource_sandbox_paths(directory: Path, item: Mapping[str, Any]) -> dict[str, Path]:
    """Derive all paths solely from a verified, redacted original resource ID."""
    token = hashlib.sha256(_encoded([
        item["owner"], item["kind"], item["source_path_sha256"],
    ])).hexdigest()[:24]
    base = directory / ("asset-" + token)
    return {
        "base": base, "source": base / "source", "target": base / "target",
        "staged": base / "staged", "recovery": base / "recovery",
        "held": base / "held", "failed": base / "failed",
    }


def _sqlite_synthetic_digest(directory: Path) -> str:
    """Fixture-only logical SQL digest; never exports or logs real SQL."""
    entries = list(directory.iterdir())
    need(len(entries) == 1 and entries[0].name == "data.sqlite"
         and not entries[0].is_symlink() and entries[0].is_file(),
         "CHAIN_SAGA_SQLITE_FIXTURE_TYPE_UNSAFE")
    database = entries[0]
    uri = "file:" + quote(str(database)) + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            status = connection.execute("PRAGMA quick_check").fetchone()
            need(status is not None and status[0] == "ok",
                 "CHAIN_SAGA_SQLITE_INTEGRITY_FAILED")
            sha = hashlib.sha256()
            for line in connection.iterdump():
                sha.update(line.encode("utf-8"))
                sha.update(b"\n")
            return sha.hexdigest()
    except sqlite3.DatabaseError:
        raise SagaBlocked("CHAIN_SAGA_SQLITE_INTEGRITY_FAILED") from None


def _resource_fingerprint(kind: str, directory: Path) -> str:
    tree = _synthetic_tree_hash(directory)
    if kind == "SQLITE":
        return hashlib.sha256(_encoded([
            tree, _sqlite_synthetic_digest(directory)
        ])).hexdigest()
    return tree


def _copy_recovery_resource(kind: str, source: Path, target: Path) -> None:
    """Use SQLite's consistent backup API, not unsafe WAL file copying."""
    if kind == "SQLITE":
        _sqlite_synthetic_digest(source)
        target.mkdir(mode=0o700)
        src = "file:" + quote(str(source / "data.sqlite")) + "?mode=ro"
        try:
            with sqlite3.connect(src, uri=True) as incoming:
                with sqlite3.connect(str(target / "data.sqlite")) as outgoing:
                    incoming.backup(outgoing)
        except sqlite3.DatabaseError:
            raise SagaBlocked("CHAIN_SAGA_SQLITE_BACKUP_FAILED") from None
        need(_sqlite_synthetic_digest(target) ==
             _sqlite_synthetic_digest(source),
             "CHAIN_SAGA_SQLITE_BACKUP_PARITY_FAILED")
    else:
        shutil.copytree(source, target, symlinks=True)
        need(_resource_fingerprint(kind, target) ==
             _resource_fingerprint(kind, source),
             "CHAIN_SAGA_ASSET_BACKUP_PARITY_FAILED")


def _assert_bound_resources(
    plan: Mapping[str, Any], bindings: Mapping[str, Any],
    originals: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    import migration_chain_asset_audit as asset_audit
    validate_locked_plan(plan)
    try:
        latest = asset_audit.bind_original_resources(plan, *originals)
    except asset_audit.ResourceOwnerBlocked:
        raise SagaBlocked("CHAIN_SAGA_RESOURCE_ORIGINAL_OWNER_DRIFT") from None
    need(isinstance(bindings, dict) and latest == bindings
         and bindings.get("cutover_allowed") is False
         and bindings.get("recovery_points_verified") is False,
         "CHAIN_SAGA_RESOURCE_BINDINGS_CHANGED")
    return list(latest["resources"])


def _rollback_proven_resource_steps(
    journal: dict[str, Any], path: Path, directory: Path,
) -> None:
    """All-owner recovery preflight first; then reverse only proven writes.

    A corrupt recovery point in *any* resource must stop the entire batch
    before rollback changes even one of the other resources.
    """
    selected = [item for item in reversed(journal["items"])
                if item["status"] == "PROMOTED_VERIFIED"]

    def require_safe(item: Mapping[str, Any]) -> None:
        paths = _resource_sandbox_paths(directory, item)
        kind = item["kind"]
        need(_resource_fingerprint(kind, paths["target"]) ==
             item["promoted_sha256"] and
             _resource_fingerprint(kind, paths["held"]) ==
             item["target_before_sha256"] and
             _resource_fingerprint(kind, paths["recovery"]) ==
             item["recovery_sha256"] and
             not os.path.lexists(paths["failed"]),
             "CHAIN_SAGA_RESOURCE_ROLLBACK_CONCURRENT_DRIFT")

    for item in selected:
        require_safe(item)
    for item in selected:
        require_safe(item)
        paths = _resource_sandbox_paths(directory, item)
        kind = item["kind"]
        item["status"] = "ROLLBACK_INTENT_RESERVED"
        _save(path, journal)
        try:
            os.rename(paths["target"], paths["failed"])
            os.rename(paths["held"], paths["target"])
            need(_resource_fingerprint(kind, paths["target"]) ==
                 item["target_before_sha256"],
                 "CHAIN_SAGA_RESOURCE_RESTORE_READBACK_FAILED")
            item["status"] = "ROLLED_BACK_VERIFIED"
            _save(path, journal)
        except Exception:
            item["status"] = "ROLLBACK_UNKNOWN_RETAIN_EVIDENCE"
            journal["status"] = "RECOVERY_REQUIRED"
            _save(path, journal)
            raise SagaBlocked(
                "CHAIN_SAGA_RESOURCE_ROLLBACK_UNCERTAIN") from None


def rehearse_bound_resources(
    plan: Mapping[str, Any], bindings: Mapping[str, Any],
    originals: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    directory: Path, *, synthetic_authority: bool = False,
    fail_after_promotions: int | None = None,
    interrupt_after_rename: bool = False,
) -> dict[str, Any]:
    """Two-phase recovery rehearsal for the exact externally owned resources.

    Only isolated 0700 fixtures under tempfile; NO SSH, original webroot,
    source freeze, SQL database import, DNS, Cron/PM2 or production writes.
    All recovery points are verified BEFORE the first replacement. Automatic
    reverse compensation is allowed solely after a deterministic test fault
    between two fully verified promotions, never during an unknown write.
    """
    need(synthetic_authority is True and
         os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
         "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED")
    rows = _assert_bound_resources(plan, bindings, originals)
    need(type(fail_after_promotions) in (int, type(None))
         and (fail_after_promotions is None or
              1 <= fail_after_promotions < len(rows)),
         "CHAIN_SAGA_INJECTED_FAILURE_OUT_OF_SCOPE")
    fd = _lock(directory)
    try:
        journal_path = directory / "resource-rehearsal.json"
        need(not os.path.lexists(journal_path),
             "CHAIN_SAGA_RESOURCE_EXISTING_ATTEMPT_RETAINED")
        for item in rows:
            paths = _resource_sandbox_paths(directory, item)
            need(paths["base"].is_dir() and
                 not paths["base"].is_symlink() and
                 paths["base"].stat().st_uid == os.geteuid() and
                 not stat.S_IMODE(paths["base"].stat().st_mode) & 0o077,
                 "CHAIN_SAGA_RESOURCE_FIXTURE_ROOT_UNSAFE")
            for name in ("staged", "recovery", "held", "failed"):
                need(not os.path.lexists(paths[name]),
                     "CHAIN_SAGA_RESOURCE_PREVIOUS_COPY_RETAINED")
            for name in ("source", "target"):
                need(paths[name].is_dir() and
                     not paths[name].is_symlink() and
                     paths[name].stat().st_uid == os.geteuid() and
                     not stat.S_IMODE(paths[name].stat().st_mode) & 0o077,
                     "CHAIN_SAGA_RESOURCE_SOURCE_OR_TARGET_UNSAFE")
                _resource_fingerprint(item["kind"], paths[name])
        journal = {
            "schema": "P07_CHAIN_RESOURCE_REHEARSAL_V1",
            "status": "RECOVERY_PREPARE",
            "plan_sha256": plan["plan_sha256"],
            "inventory_sha256": bindings["inventory_sha256"],
            "synthetic_only": True, "cutover_allowed": False,
            "items": [{**item, "status": "NOT_STARTED"} for item in rows],
        }
        _save(journal_path, journal)
        # First stage + verify the complete source and target recovery set.
        for item in journal["items"]:
            paths = _resource_sandbox_paths(directory, item)
            item["source_sha256"] = _resource_fingerprint(
                item["kind"], paths["source"])
            item["target_before_sha256"] = _resource_fingerprint(
                item["kind"], paths["target"])
            item["status"] = "RECOVERY_INTENT_RESERVED"
            _save(journal_path, journal)
            try:
                _copy_recovery_resource(item["kind"], paths["source"],
                                        paths["staged"])
                _copy_recovery_resource(item["kind"], paths["target"],
                                        paths["recovery"])
                item["promoted_sha256"] = _resource_fingerprint(
                    item["kind"], paths["staged"])
                item["recovery_sha256"] = _resource_fingerprint(
                    item["kind"], paths["recovery"])
                # SQLite backup can be logically identical yet physically
                # different; the original untouched target is ALSO retained
                # by rename at promotion for byte-exact reverse restoration.
                if item["kind"] == "SQLITE":
                    need(_sqlite_synthetic_digest(paths["staged"]) ==
                         _sqlite_synthetic_digest(paths["source"]) and
                         _sqlite_synthetic_digest(paths["recovery"]) ==
                         _sqlite_synthetic_digest(paths["target"]),
                         "CHAIN_SAGA_SQLITE_RECOVERY_PARITY_FAILED")
                else:
                    need(_resource_fingerprint(item["kind"], paths["staged"]) ==
                         item["source_sha256"] and
                         _resource_fingerprint(item["kind"], paths["recovery"]) ==
                         item["target_before_sha256"],
                         "CHAIN_SAGA_RESOURCE_RECOVERY_PARITY_FAILED")
                item["status"] = "RECOVERY_VERIFIED"
                _save(journal_path, journal)
            except Exception:
                item["status"] = "RECOVERY_UNKNOWN_RETAIN_EVIDENCE"
                journal["status"] = "RECOVERY_REQUIRED"
                _save(journal_path, journal)
                raise SagaBlocked(
                    "CHAIN_SAGA_RESOURCE_SNAPSHOT_RECOVERY_REQUIRED") from None
        journal["status"] = "ALL_RECOVERY_POINTS_VERIFIED_NOT_CUTOVER"
        _save(journal_path, journal)
        promoted = 0
        for item in journal["items"]:
            paths = _resource_sandbox_paths(directory, item)
            kind = item["kind"]
            need(item["status"] == "RECOVERY_VERIFIED" and
                 _resource_fingerprint(kind, paths["target"]) ==
                 item["target_before_sha256"] and
                 _resource_fingerprint(kind, paths["staged"]) ==
                 item["promoted_sha256"] and
                 _resource_fingerprint(kind, paths["source"]) ==
                 item["source_sha256"],
                 "CHAIN_SAGA_RESOURCE_PREFLIGHT_DRIFT")
            item["status"] = "PROMOTION_INTENT_RESERVED"
            _save(journal_path, journal)
            try:
                os.rename(paths["target"], paths["held"])
                if interrupt_after_rename and promoted == 0:
                    raise OSError("injected unverified rename gap")
                os.rename(paths["staged"], paths["target"])
                need(_resource_fingerprint(kind, paths["target"]) ==
                     item["promoted_sha256"] and
                     _resource_fingerprint(kind, paths["held"]) ==
                     item["target_before_sha256"],
                     "CHAIN_SAGA_RESOURCE_POST_WRITE_DRIFT")
                item["status"] = "PROMOTED_VERIFIED"
                _save(journal_path, journal)
            except Exception:
                item["status"] = "PROMOTION_UNKNOWN_RETAIN_EVIDENCE"
                journal["status"] = "RECOVERY_REQUIRED"
                _save(journal_path, journal)
                raise SagaBlocked(
                    "CHAIN_SAGA_RESOURCE_PROMOTION_UNCERTAIN") from None
            promoted += 1
            if fail_after_promotions == promoted:
                journal["status"] = "KNOWN_DOWNSTREAM_FAILURE"
                _save(journal_path, journal)
                _rollback_proven_resource_steps(
                    journal, journal_path, directory)
                journal["status"] = "ROLLED_BACK_VERIFIED_NOT_CUTOVER"
                _save(journal_path, journal)
                return {
                    "status": journal["status"], "restored_count": promoted,
                    "cutover_allowed": False,
                }
        journal["status"] = "ALL_RESOURCE_PROMOTIONS_VERIFIED_NOT_CUTOVER"
        _save(journal_path, journal)
        return {
            "status": journal["status"],
            "resource_count": len(rows), "cutover_allowed": False,
            "source_frozen": False,
        }
    finally:
        os.close(fd)


def rollback_rehearsed_resources(
    plan: Mapping[str, Any], bindings: Mapping[str, Any],
    originals: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    directory: Path, *, synthetic_authority: bool = False,
) -> dict[str, Any]:
    """Explicit rollback of a completed private rehearsal, not an unknown gap."""
    need(synthetic_authority is True and
         os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
         "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED")
    rows = _assert_bound_resources(plan, bindings, originals)
    fd = _lock(directory)
    try:
        path = directory / "resource-rehearsal.json"
        journal = _read_receipt(path, expected_schema=
                                "P07_CHAIN_RESOURCE_REHEARSAL_V1")
        need(journal.get("status") ==
             "ALL_RESOURCE_PROMOTIONS_VERIFIED_NOT_CUTOVER"
             and journal.get("plan_sha256") == plan["plan_sha256"]
             and journal.get("inventory_sha256") ==
             bindings["inventory_sha256"] and
             journal.get("synthetic_only") is True and
             journal.get("cutover_allowed") is False and
             len(journal.get("items", [])) == len(rows) and
             all({k: v for k, v in item.items()
                  if k in original} == original and
                 item.get("status") == "PROMOTED_VERIFIED"
                 for item, original in zip(journal["items"], rows)),
             "CHAIN_SAGA_RESOURCE_ROLLBACK_RECEIPT_UNVERIFIED")
        _rollback_proven_resource_steps(journal, path, directory)
        journal["status"] = "ROLLED_BACK_VERIFIED_NOT_CUTOVER"
        _save(path, journal)
        return {
            "status": journal["status"],
            "restored_count": len(rows), "cutover_allowed": False,
        }
    finally:
        os.close(fd)


def reject_unverified_original_db_and_restore_resources(
    plan: Mapping[str, Any],
    db_scope: Mapping[str, Any],
    resource_bindings: Mapping[str, Any],
    originals: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    directory: Path,
    *,
    synthetic_authority: bool = False,
) -> dict[str, Any]:
    """Fail a cross-owner DB switch BEFORE ANY database call, restore resources.

    This is the actual bridge between the existing resource rollback engine
    and the three original DB scopes. The real final shadow batch explicitly
    requires ONE frozen CUTOVER_RUNNING migration owner; we must never invoke
    it with parent/child/tail PREPARE_FAILED states or the locked 21-step plan.

    Synthetic-only: the resource journal is already a verified local rehearsal.
    On the known-zero-DB-write boundary, reverse only those resource changes.
    A prior/unknown transaction or damaged receipt remains manual-recovery,
    never a blind replay or an assertion that DB row parity passed.
    """
    need(synthetic_authority is True and
         os.environ.get("P07_SYNTHETIC_SAGA_FIXTURE") == "1",
         "CHAIN_SAGA_REAL_EXECUTION_NOT_WIRED")
    validate_locked_plan(plan)
    current_db = consolidated.bind_locked_original_database_scope(
        plan, *originals)
    need(isinstance(db_scope, dict) and db_scope == current_db
         and db_scope["status"] ==
         "LOCKED_DB_RECOVERY_REQUIRED_NOT_CUTOVER_READY"
         and db_scope["cross_task_batch_execution_allowed"] is False
         and db_scope["database_writes_performed"] is False,
         "CHAIN_SAGA_DB_ORIGINAL_SCOPE_CHANGED")
    _assert_bound_resources(plan, resource_bindings, originals)

    fd = _lock(directory)
    try:
        path = directory / "locked-db-boundary.json"
        need(not os.path.lexists(path),
             "CHAIN_SAGA_DB_BOUNDARY_PRIOR_ATTEMPT_RETAINED")
        prior = _read_receipt(
            directory / "resource-rehearsal.json",
            expected_schema="P07_CHAIN_RESOURCE_REHEARSAL_V1")
        need(prior.get("status") ==
             "ALL_RESOURCE_PROMOTIONS_VERIFIED_NOT_CUTOVER"
             and prior.get("plan_sha256") == plan["plan_sha256"]
             and prior.get("inventory_sha256") ==
             resource_bindings["inventory_sha256"]
             and prior.get("synthetic_only") is True
             and prior.get("cutover_allowed") is False,
             "CHAIN_SAGA_DB_RESOURCE_STAGE_UNVERIFIED")
        receipt = {
            "schema": "P07_CHAIN_LOCKED_DB_BOUNDARY_V1",
            "status": "DB_SWITCH_REFUSED_BEFORE_FIRST_WRITE",
            "plan_sha256": plan["plan_sha256"],
            "db_scope_sha256": db_scope["scope_sha256"],
            "resource_inventory_sha256":
                resource_bindings["inventory_sha256"],
            "database_count": db_scope["database_count"],
            "database_writes_performed": False,
            "www3_reconnected": False,
            "synthetic_only": True,
            "cutover_allowed": False,
            "resource_rollback_verified": False,
        }
        _save(path, receipt)
    finally:
        os.close(fd)

    # The return is only complete if the existing independent resource
    # rollback verifies EVERY original recovery copy and target readback.
    # No DB switch/stage/import/connection callable exists on this path.
    try:
        restored = rollback_rehearsed_resources(
            plan, resource_bindings, originals, directory,
            synthetic_authority=True)
    except Exception:
        fd = _lock(directory)
        try:
            latest = _read_receipt(
                directory / "locked-db-boundary.json",
                expected_schema="P07_CHAIN_LOCKED_DB_BOUNDARY_V1")
            if (latest.get("plan_sha256") == plan["plan_sha256"] and
                    latest.get("db_scope_sha256") ==
                    db_scope["scope_sha256"] and
                    latest.get("status") ==
                    "DB_SWITCH_REFUSED_BEFORE_FIRST_WRITE"):
                latest["status"] = "RESOURCE_RECOVERY_REQUIRED"
                _save(directory / "locked-db-boundary.json", latest)
        finally:
            os.close(fd)
        raise SagaBlocked(
            "CHAIN_SAGA_DB_RESOURCE_REVERSE_RECOVERY_REQUIRED") from None

    need(restored["status"] == "ROLLED_BACK_VERIFIED_NOT_CUTOVER"
         and restored["restored_count"] ==
         resource_bindings["resource_count"],
         "CHAIN_SAGA_DB_REVERSE_RESTORE_UNVERIFIED")
    fd = _lock(directory)
    try:
        latest = _read_receipt(
            directory / "locked-db-boundary.json",
            expected_schema="P07_CHAIN_LOCKED_DB_BOUNDARY_V1")
        need(latest.get("status") ==
             "DB_SWITCH_REFUSED_BEFORE_FIRST_WRITE"
             and latest.get("plan_sha256") == plan["plan_sha256"]
             and latest.get("db_scope_sha256") ==
             db_scope["scope_sha256"] and
             latest.get("resource_inventory_sha256") ==
             resource_bindings["inventory_sha256"]
             and latest.get("database_writes_performed") is False,
             "CHAIN_SAGA_DB_BOUNDARY_RECEIPT_CHANGED")
        latest["status"] = (
            "RESOURCE_ROLLBACK_VERIFIED_DATABASE_UNTOUCHED_NOT_CUTOVER")
        latest["resource_rollback_verified"] = True
        latest["restored_resource_count"] = restored["restored_count"]
        _save(directory / "locked-db-boundary.json", latest)
        return {
            "status": latest["status"],
            "database_count": db_scope["database_count"],
            "restored_resource_count": restored["restored_count"],
            "database_writes_performed": False,
            "www3_reconnected": False,
            "cutover_allowed": False,
        }
    finally:
        os.close(fd)
