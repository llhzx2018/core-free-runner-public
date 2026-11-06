#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import grp
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import sqlite3
import socket
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

import app_config
import cloudpanel
import cutover
import inventory
import native_scratch_restore
import isolated_db_restore
import private_recovery_gate
import private_sql_literal_reconcile
import migration_remainder
import migration_chain_recovery
import migration_chain_consolidation
import migration_chain_execution_scope
import migration_three_site_window
import migration_db_adoption
import package as package_engine
import server_migration as legacy
import transport
import verify as verify_engine
import sql_diff_evidence as sql_diff_probe

SCHEMA = "vf-server-ops.server-migration.target-pull.v1"
ROOT = Path(__file__).resolve().parents[1]
STATE_ROOT = Path(os.environ.get(
    "VFOPS_SERVER_MIGRATION_STATE_ROOT",
    "/var/lib/vf-server-ops/server-migrations",
))
SOURCE_RECOVERY_ROOT = Path(os.environ.get(
    "VFOPS_SOURCE_RECOVERY_ROOT",
    "/var/lib/vf-server-ops/source-recovery",
))
SAFE_ID_RE = legacy.SAFE_ID_RE
PROTECTED_DB_CONFIGS = legacy.PROTECTED_DB_CONFIGS

# Target transaction markers are intentionally co-located with the target-owned
# migration state. The legacy module is retained only as a library of audited
# local CloudPanel/DB transaction primitives.
legacy.STATE_ROOT = STATE_ROOT


class PullMigrationError(RuntimeError):
    pass


# Extract only verifier-owned fixed labels and decimal counts. Even if an
# upstream exception contains SQL text or a database name, never persist it.
_SQL_GUARD_FLOW_EVIDENCE_RE = re.compile(
    r"\[(SQL_GUARD_FLOW_V1 "
    r"probe=[0-9]{1,10} assignment=[0-9]{1,10} "
    r"safe_assignment=[0-9]{1,10} prepare=[0-9]{1,10} "
    r"execute=[0-9]{1,10} deallocate=[0-9]{1,10} "
    r"unknown_set=[0-9]{1,10} unknown_control=[0-9]{1,10} "
    r"recognized=[0-9]{1,10} outcome=(?:RECOGNIZED|UNSAFE_BRANCH|"
    r"UNKNOWN_CONTROL_GRAMMAR|NO_COMPLETE_DYNAMIC_GROUP|"
    r"UNBALANCED_STAGES|SEQUENCE_REJECTED))\]"
)


def retain_safe_sql_guard_failure(state: dict[str, Any], error: Exception) -> None:
    """Persist only fixed MySQL guard counts before transient SQL is cleaned."""
    if not isinstance(error, PullMigrationError):
        return
    detail = str(error)
    if not detail.startswith("MySQL verification failed [CONDITIONAL_DDL]"):
        return
    match = _SQL_GUARD_FLOW_EVIDENCE_RE.search(detail)
    state["last_sql_guard_failure"] = {
        "reason": "CONDITIONAL_DDL",
        "flow": match.group(1) if match else "SQL_GUARD_FLOW_V1_UNAVAILABLE",
    }


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


PROGRESS_EVENT_SCHEMA = "vf-server-ops.migration-progress.v1"

MIGRATION_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "PREPARING": frozenset({"PREPARING", "PREPARED", "PREPARE_FAILED"}),
    "PREPARE_FAILED": frozenset({"PREPARING"}),
    "PREPARED": frozenset({
        "PREPARE_FAILED",
        "CUTOVER_RUNNING",
        "ROLLED_BACK",
        "ROLLBACK_PARTIAL",
    }),
    "CUTOVER_RUNNING": frozenset({
        "CUTOVER_RUNNING",
        "CUTOVER_PREP_READY",
        "CUTOVER_FAILED_ROLLED_BACK",
        "CUTOVER_FAILED_ROLLBACK_PARTIAL",
        "ROLLED_BACK",
        "ROLLBACK_PARTIAL",
    }),
    "CUTOVER_FAILED_ROLLED_BACK": frozenset({"CUTOVER_RUNNING"}),
    "CUTOVER_FAILED_ROLLBACK_PARTIAL": frozenset({
        "ROLLED_BACK",
        "ROLLBACK_PARTIAL",
    }),
    "CUTOVER_PREP_READY": frozenset({
        "WAITING_DNS",
        "PRODUCTION_VERIFY_FAILED",
        "PRODUCTION_PASS",
        "CUTOVER_FAILED_ROLLED_BACK",
        "CUTOVER_FAILED_ROLLBACK_PARTIAL",
        "ROLLED_BACK",
        "ROLLBACK_PARTIAL",
    }),
    "WAITING_DNS": frozenset({
        "WAITING_DNS",
        "PRODUCTION_VERIFY_FAILED",
        "PRODUCTION_PASS",
    }),
    "PRODUCTION_VERIFY_FAILED": frozenset({
        "WAITING_DNS",
        "PRODUCTION_VERIFY_FAILED",
        "PRODUCTION_PASS",
    }),
    "PRODUCTION_PASS": frozenset(),
    "ROLLED_BACK": frozenset(),
    "ROLLBACK_PARTIAL": frozenset(),
}


def transition_migration_status(state: dict[str, Any], new_status: str) -> None:
    current = str(state.get("status", ""))
    allowed = MIGRATION_STATUS_TRANSITIONS.get(current)
    if allowed is None or new_status not in allowed:
        raise PullMigrationError(
            "invalid migration status transition: "
            f"{current or 'UNKNOWN'} -> {new_status}"
        )
    state["status"] = new_status


def migration_progress_event(message: str) -> dict[str, Any]:
    event: dict[str, Any] = {
        "schema": PROGRESS_EVENT_SCHEMA,
        "kind": "MIGRATION_PROGRESS",
        "message": str(message),
    }

    phase_match = re.match(
        r"^(?P<step>\d+)/(?P<total>\d+)\s*·\s*(?P<detail>.*)$",
        str(message),
    )
    detail = str(message)
    if phase_match:
        event["phase_step"] = int(phase_match.group("step"))
        event["phase_total"] = int(phase_match.group("total"))
        detail = phase_match.group("detail")

    item_match = re.search(
        r"(?:网站\s+)?(?P<current>\d+)/(?P<total>\d+)",
        detail,
    )
    if item_match:
        event["item_current"] = int(item_match.group("current"))
        event["item_total"] = int(item_match.group("total"))

    if "MySQL" in detail:
        event["scope"] = "MYSQL"
    elif "SQLite" in detail:
        event["scope"] = "SQLITE"
    elif "HTTP" in detail or "本地验证" in detail or "公网验证" in detail:
        event["scope"] = "HTTP_VERIFY"
    elif "Runtime" in detail or "Storage" in detail or "外部业务文件" in detail:
        event["scope"] = "EXTERNAL_ASSET"
    elif "Cron" in detail or "PM2" in detail or "Node.js" in detail:
        event["scope"] = "RUNTIME"
    elif "网站" in detail:
        event["scope"] = "SITE_FILES"
    else:
        event["scope"] = "MIGRATION"

    return event


def progress_note(message: str) -> None:
    if os.environ.get("VFOPS_MIGRATION_PROGRESS") != "1":
        return
    event = migration_progress_event(message)
    if os.environ.get("VFOPS_MIGRATION_PROGRESS_FORMAT") == "jsonl":
        print(
            json.dumps(event, ensure_ascii=False, separators=(",", ":")),
            file=sys.stderr,
            flush=True,
        )
        return
    print(f"迁移阶段：{message}", file=sys.stderr, flush=True)


def run_local(
    args: list[str],
    *,
    timeout: int = 3600,
    check: bool = True,
    stream_to_stderr: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        kwargs: dict[str, Any] = {
            "text": True,
            "check": False,
            "timeout": timeout,
        }
        if stream_to_stderr:
            kwargs["stdout"] = sys.stderr
            kwargs["stderr"] = sys.stderr
        else:
            kwargs["capture_output"] = True
        proc = subprocess.run(args, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PullMigrationError(f"local command unavailable: {args[0]}") from exc
    if check and proc.returncode != 0:
        raise PullMigrationError(f"local command failed: {args[0]}")
    return proc


def state_dir(mid: str) -> Path:
    if not SAFE_ID_RE.fullmatch(mid):
        raise PullMigrationError("invalid migration id")
    return STATE_ROOT / mid


def state_path(mid: str) -> Path:
    return state_dir(mid) / "state.json"


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = now_utc()
    legacy.atomic_private_json(state_path(str(state["migration_id"])), state)


def load_state(mid: str) -> dict[str, Any]:
    try:
        data = json.loads(state_path(mid).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PullMigrationError("migration state is unavailable or invalid") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise PullMigrationError("unsupported migration state")
    return data


def source_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.ssh_user != "root":
        raise PullMigrationError("server migration currently requires root SSH on old server")
    try:
        host = transport.validate_host(args.source_host or args.source_ip)
        ip = transport.validate_ip(args.source_ip)
        port = transport.validate_port(args.ssh_port)
    except transport.TransportError as exc:
        raise PullMigrationError("old-server SSH endpoint is invalid") from exc
    identity: str | None = None
    if args.identity_file:
        path = Path(args.identity_file).expanduser().resolve()
        if not path.is_file():
            raise PullMigrationError("SSH identity file does not exist")
        identity = str(path)
    return {
        "host": host,
        "ip": ip,
        "ssh_user": args.ssh_user,
        "ssh_port": port,
        "identity_file": identity,
        "managed_identity_file": bool(getattr(args, "managed_identity_file", False)),
        "ssh": args.ssh,
    }


def source_base(source: dict[str, Any]) -> list[str]:
    identity = Path(source["identity_file"]) if source.get("identity_file") else None
    return transport.ssh_base(
        source.get("ssh", "ssh"),
        source["host"],
        source["ssh_user"],
        int(source["ssh_port"]),
        identity,
    )


def source_remote(
    source: dict[str, Any],
    command: str,
    *,
    timeout: int = 300,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        proc = transport.run_ssh(
            source_base(source),
            transport.remote_priv(source["ssh_user"], command),
            timeout=timeout,
        )
    except transport.TransportError as exc:
        raise PullMigrationError("old-server SSH operation failed") from exc
    if check and proc.returncode != 0:
        raise PullMigrationError("old-server command failed")
    return proc


def ssh_rsync_command(source: dict[str, Any]) -> str:
    parts = [
        source.get("ssh", "ssh"),
        "-p", str(source["ssh_port"]),
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=2",
    ]
    if source.get("identity_file"):
        parts.extend(["-i", str(Path(source["identity_file"]).expanduser().resolve())])
    return shlex.join(parts)


def local_user_group(user: str) -> tuple[str, int, int]:
    try:
        row = pwd.getpwnam(user)
        group = grp.getgrgid(row.pw_gid).gr_name
    except KeyError as exc:
        raise PullMigrationError(f"new-server website user is unavailable: {user}") from exc
    return group, row.pw_uid, row.pw_gid


def pull_path(
    source: dict[str, Any],
    remote_path: str,
    local_path: Path,
    *,
    user: str | None = None,
    delete: bool = False,
    excludes: tuple[str, ...] = (),
) -> None:
    if not remote_path.startswith("/"):
        raise PullMigrationError("old-server path is not absolute")
    show_progress = os.environ.get("VFOPS_MIGRATION_PROGRESS") == "1"
    info = "--info=progress2,stats2" if show_progress else "--info=stats2"
    args = ["rsync", "-aH", "--partial", "--protect-args", info]
    if show_progress:
        args.append("--human-readable")
    if delete:
        args.append("--delete-delay")
    if user:
        group, _, _ = local_user_group(user)
        args.append(f"--chown={user}:{group}")
    for item in excludes:
        args.extend(["--exclude", item])
    remote = f"{source['ssh_user']}@{source['host']}:{remote_path}"
    # Caller owns the source-path semantics: a trailing slash means directory
    # contents, while a path without one means the exact remote object. Never
    # infer remote type from the current local target; a previous failed run may
    # have left an empty directory where the source is actually a file.
    remote_spec = remote
    args.extend(["-e", ssh_rsync_command(source), remote_spec, str(local_path)])
    if show_progress:
        print(f"迁移进度：{remote_path} → {local_path}", file=sys.stderr, flush=True)
    run_local(args, timeout=3600, stream_to_stderr=show_progress)


def source_path_kind(source: dict[str, Any], remote_path: str) -> str:
    if not remote_path.startswith("/"):
        raise PullMigrationError("old-server path is not absolute")
    quoted = shlex.quote(remote_path)
    command = (
        f"if [ -L {quoted} ]; then printf 'SYMLINK'; "
        f"elif [ -d {quoted} ]; then printf 'DIRECTORY'; "
        f"elif [ -f {quoted} ]; then printf 'FILE'; "
        f"elif [ -e {quoted} ]; then printf 'OTHER'; "
        "else printf 'MISSING'; fi"
    )
    proc = source_remote(source, command, timeout=30, check=False)
    if proc.returncode != 0:
        raise PullMigrationError("old-server external path type check failed")
    kind = proc.stdout.strip()
    if kind not in {"DIRECTORY", "FILE"}:
        raise PullMigrationError(
            f"old-server external path is not a regular file/directory: {remote_path}"
        )
    return kind


def push_control_file(
    source: dict[str, Any],
    local_path: Path,
    remote_path: str,
) -> None:
    if not remote_path.startswith("/var/lib/vf-server-ops/"):
        raise PullMigrationError("unsafe old-server control path")
    parent = str(Path(remote_path).parent)
    source_remote(source, f"install -d -m 700 {shlex.quote(parent)}")
    args = [
        "rsync", "-a", "--protect-args",
        "-e", ssh_rsync_command(source),
        str(local_path),
        f"{source['ssh_user']}@{source['host']}:{remote_path}",
    ]
    run_local(args, timeout=300)
    source_remote(source, f"chmod 600 {shlex.quote(remote_path)}")


def stage_source_runtime(source: dict[str, Any], token: str) -> str:
    if not SAFE_ID_RE.fullmatch(token):
        raise PullMigrationError("invalid source runtime token")
    runtime = f"/var/lib/vf-server-ops/pull-source/{token}/runtime"
    command = (
        "set -eu; "
        # Never reuse, overwrite or delete a pre-existing helper directory.
        f"test ! -e {shlex.quote(runtime)}; "
        f"test ! -L {shlex.quote(runtime)}; "
        f"install -d -m 700 {shlex.quote(runtime)}; "
        f"tar -xzf - -C {shlex.quote(runtime)}; "
        f"chmod -R go-rwx {shlex.quote(runtime)}"
    )
    try:
        transport.stream_tar_to_remote(
            "tar",
            ROOT,
            ["bin", "lib", "VERSION", "BUILD_ID"],
            source_base(source),
            transport.remote_priv(source["ssh_user"], command),
            "old-server helper staging",
        )
    except transport.TransportError as exc:
        if "local archive failed" in str(exc):
            raise PullMigrationError("current-server migration runtime is incomplete") from exc
        raise PullMigrationError("cannot stage migration helper on old server") from exc
    return runtime


def source_python(
    source: dict[str, Any],
    runtime: str,
    *args: str,
    timeout: int = 1800,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [
        "env",
        f"PYTHONPATH={runtime}/lib",
        "python3",
        f"{runtime}/lib/server_migration_pull.py",
        *args,
    ]
    rendered = " ".join(shlex.quote(item) for item in command)
    return source_remote(source, rendered, timeout=timeout, check=check)


# A migration is resumable across releases. The source-side helper staged at
# original prepare time can therefore be older than this receiver's verifier.
# Confirm exact bytes of the bounded export/verification dependency set before
# any resumed SQL export, and stage a fresh migration-owned helper if needed.
_SOURCE_EXPORT_HELPER_FILES = (
    "BUILD_ID", "lib/server_migration_pull.py", "lib/sql_diff_evidence.py",
    "lib/verify.py", "lib/cloudpanel.py",
)
_SOURCE_RUNTIME_PATH_RE = re.compile(
    r"^/var/lib/vf-server-ops/pull-source/(?:pull-[A-Za-z0-9-]+|probe-[0-9a-f]{32})/runtime$"
)


def source_export_helper_matches_current(source: dict[str, Any], runtime: str) -> bool:
    """Read-only exact source/receiver helper integrity, never SQL or credentials."""
    if not _SOURCE_RUNTIME_PATH_RE.fullmatch(runtime):
        raise PullMigrationError("SOURCE_EXPORT_HELPER_PATH_UNVERIFIED")
    expected = []
    for relative in _SOURCE_EXPORT_HELPER_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise PullMigrationError("CURRENT_SOURCE_EXPORT_HELPER_INCOMPLETE")
        expected.append(hashlib.sha256(path.read_bytes()).hexdigest())
    files = [f"{runtime}/{name}" for name in _SOURCE_EXPORT_HELPER_FILES]
    command = "sha256sum -- " + " ".join(shlex.quote(item) for item in files)
    response = source_remote(source, command, timeout=60, check=False)
    if response.returncode != 0:
        return False
    actual = response.stdout.splitlines()
    if len(actual) != len(expected):
        return False
    for line, hash_value, filename in zip(actual, expected, files):
        if not re.fullmatch(r"[0-9a-f]{64}  .+", line):
            return False
        got_hash, got_file = line.split("  ", 1)
        if got_hash != hash_value or got_file != filename:
            return False
    return True


def cleanup_probe_runtime(source: dict[str, Any], runtime: str) -> None:
    root = str(Path(runtime).parent)
    # Cleanup is restricted to unpredictable, transaction-owned probe IDs.
    if re.fullmatch(r"/var/lib/vf-server-ops/pull-source/probe-[0-9a-f]{32}", root):
        source_remote(source, f"rm -rf -- {shlex.quote(root)}", timeout=120, check=False)


def source_probe(source: dict[str, Any], domains: list[str]) -> dict[str, Any]:
    token = "probe-" + os.urandom(16).hex()
    runtime = f"/var/lib/vf-server-ops/pull-source/{token}/runtime"
    try:
        stage_source_runtime(source, token)
        args: list[str] = ["_source-plan"]
        for domain in domains:
            args.extend(["--site", domain])
        proc = source_python(source, runtime, *args, timeout=600)
        if proc.returncode != 0:
            raise PullMigrationError("old-server inventory/preflight failed")
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise PullMigrationError("old-server inventory result is invalid") from exc
        if payload.get("status") != "READY":
            raise PullMigrationError("old-server inventory is not migration-ready")
        return payload
    finally:
        cleanup_probe_runtime(source, runtime)


def _selected_domains(state: dict[str, Any]) -> list[str]:
    return [
        str(site.get("domain"))
        for site in state.get("sites", [])
        if isinstance(site, dict) and site.get("domain")
    ]


def _allowed_site_users(state: dict[str, Any]) -> set[str]:
    return {
        str(site.get("site_user"))
        for site in state.get("sites", [])
        if isinstance(site, dict) and site.get("site_user")
    }


def _site_structure_fingerprint(site: dict[str, Any]) -> dict[str, Any]:
    runtime = site.get("runtime") if isinstance(site.get("runtime"), dict) else {}
    raw_dbs = site.get("mysql_databases")
    databases = sorted(str(item) for item in raw_dbs) if isinstance(raw_dbs, list) else raw_dbs
    return {
        "domain": str(site.get("domain") or ""),
        "site_user": str(site.get("site_user") or ""),
        "site_root": str(site.get("site_root") or ""),
        "document_root": str(site.get("document_root") or ""),
        "runtime": {
            "type": runtime.get("type"),
            "version": runtime.get("version"),
            "app_port": runtime.get("app_port"),
        },
        "mysql_databases": databases,
    }


def refresh_migration_assets_from_source(state: dict[str, Any]) -> dict[str, Any]:
    domains = _selected_domains(state)
    if not domains:
        return {
            "external_added": 0,
            "external_added_paths": [],
            "sqlite_added": 0,
            "sqlite_added_paths": [],
            "runtime_assets_changed": False,
        }

    plan = source_probe(state["source"], domains)
    expected_identity = str(state.get("source_server_identity") or "")
    actual_identity = str(plan.get("source_server_identity") or "")
    if expected_identity and actual_identity and actual_identity != expected_identity:
        raise PullMigrationError("old-server identity changed during migration")

    fresh_sites = {
        str(row.get("domain")): row
        for row in plan.get("sites", [])
        if isinstance(row, dict) and row.get("domain")
    }
    drifted: list[str] = []
    for site in state.get("sites", []):
        if not isinstance(site, dict):
            continue
        domain = str(site.get("domain") or "")
        fresh = fresh_sites.get(domain)
        if not fresh or _site_structure_fingerprint(site) != _site_structure_fingerprint(fresh):
            drifted.append(domain or "UNKNOWN")
    if drifted:
        raise PullMigrationError(
            "old-server selected site structure changed during migration: "
            + ",".join(sorted(set(drifted)))
        )

    allowed_users = _allowed_site_users(state)

    current_external = [
        row for row in state.get("external_assets", [])
        if isinstance(row, dict)
    ]
    external_seen = {
        (str(row.get("path")), str(row.get("user"))): row
        for row in current_external
        if row.get("path") and row.get("user")
    }
    external_added_paths: list[str] = []
    metadata_changed = False
    for row in plan.get("external_assets", []):
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        user = str(row.get("user") or "")
        reason = str(row.get("reason") or "DISCOVERED_EXTERNAL")
        if user not in allowed_users or not path.startswith(f"/home/{user}/"):
            raise PullMigrationError("old-server external asset escaped selected site home")
        key = (path, user)
        existing = external_seen.get(key)
        if existing is not None:
            if not existing.get("reason"):
                existing["reason"] = reason
                metadata_changed = True
            continue
        item = {"path": path, "user": user, "reason": reason}
        current_external.append(item)
        external_seen[key] = item
        external_added_paths.append(path)
    state["external_assets"] = current_external

    current_sqlite = [
        row for row in state.get("sqlite_assets", [])
        if isinstance(row, dict)
    ]
    sqlite_seen = {
        (str(row.get("path")), str(row.get("user"))): row
        for row in current_sqlite
        if row.get("path") and row.get("user")
    }
    sqlite_added_paths: list[str] = []
    for row in plan.get("sqlite_assets", []):
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        user = str(row.get("user") or "")
        if user not in allowed_users or not path.startswith(f"/home/{user}/"):
            raise PullMigrationError("old-server SQLite asset escaped selected site home")
        key = (path, user)
        if key in sqlite_seen:
            continue
        item = {
            "path": path,
            "user": user,
            "mode": int(row.get("mode") or 0o600),
        }
        current_sqlite.append(item)
        sqlite_seen[key] = item
        sqlite_added_paths.append(path)
    state["sqlite_assets"] = current_sqlite

    fresh_runtime = (
        plan.get("runtime_assets")
        if isinstance(plan.get("runtime_assets"), dict)
        else {}
    )
    runtime_assets_changed = (
        json.dumps(fresh_runtime, ensure_ascii=False, sort_keys=True)
        != json.dumps(state.get("runtime_assets") or {}, ensure_ascii=False, sort_keys=True)
    )
    if runtime_assets_changed:
        state["runtime_assets"] = fresh_runtime

    listeners = plan.get("source_external_listeners", [])
    if listeners != state.get("source_external_listeners", []):
        state["source_external_listeners"] = listeners
        metadata_changed = True

    result = {
        "external_added": len(external_added_paths),
        "external_added_paths": external_added_paths,
        "sqlite_added": len(sqlite_added_paths),
        "sqlite_added_paths": sqlite_added_paths,
        "runtime_assets_changed": runtime_assets_changed,
    }
    if external_added_paths:
        progress_note(
            f"发现 {len(external_added_paths)} 个此前漏记的站点外部 Runtime / Storage，已加入原迁移任务"
        )
    if sqlite_added_paths:
        progress_note(
            f"发现 {len(sqlite_added_paths)} 个此前漏记的 SQLite 数据文件，已加入原迁移任务"
        )
    if runtime_assets_changed:
        progress_note("检测到 Cron / PM2 运行资料变化，已刷新待迁移运行资料")

    if (
        external_added_paths
        or sqlite_added_paths
        or runtime_assets_changed
        or metadata_changed
    ):
        save_state(state)
    return result


def refresh_external_assets_from_source(state: dict[str, Any]) -> int:
    """Compatibility wrapper for older callers/tests."""
    return int(refresh_migration_assets_from_source(state)["external_added"])


def _http_status_family(code: str) -> str:
    if not code.isdigit():
        return "UNAVAILABLE"
    value = int(code)
    if 200 <= value < 400:
        return "SUCCESS_OR_REDIRECT"
    if 400 <= value < 500:
        return "CLIENT_ERROR"
    return "UNAVAILABLE"


def capture_source_http_baseline(
    source: dict[str, Any],
    sites: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    address = ipaddress.ip_address(str(source["ip"]))
    resolve_ip = f"[{address}]" if address.version == 6 else str(address)
    rows: dict[str, dict[str, Any]] = {}
    for site in sites:
        domain = str(site.get("domain") or "")
        if not domain:
            continue
        proc = run_local([
            "curl", "-kSs", "--connect-timeout", "10", "--max-time", "30",
            "--resolve", f"{domain}:443:{resolve_ip}",
            "-o", "/dev/null", "-w", "%{http_code}",
            f"https://{domain}/",
        ], timeout=45, check=False)
        code = proc.stdout.strip()[-3:]
        code = code if code.isdigit() else "000"
        family = _http_status_family(code)
        rows[domain] = {
            "status": "PASS" if proc.returncode == 0 and family != "UNAVAILABLE" else "FAIL",
            "http_code": code,
            "family": family,
            "curl_exit": int(proc.returncode),
        }
    return rows


def ensure_source_http_baseline(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    current = state.get("source_http_baseline")
    if isinstance(current, dict) and current:
        return current
    if state.get("source_runtime_frozen"):
        return current if isinstance(current, dict) else {}
    baseline = capture_source_http_baseline(state["source"], state["sites"])
    state["source_http_baseline"] = baseline
    state["source_http_baseline_required"] = True
    save_state(state)
    return baseline

def ensure_old_server_rsync(source: dict[str, Any]) -> dict[str, Any]:
    check = source_remote(source, "command -v rsync >/dev/null 2>&1", timeout=30, check=False)
    if check.returncode == 0:
        return {"status": "READY", "installed": False}
    install = source_remote(
        source,
        "set -eu; command -v apt-get >/dev/null 2>&1; "
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -y >/dev/null; apt-get install -y rsync >/dev/null; "
        "command -v rsync >/dev/null 2>&1",
        timeout=1200,
        check=False,
    )
    if install.returncode != 0:
        raise PullMigrationError("old-server rsync is missing and automatic install failed")
    return {"status": "READY", "installed": True}


def migration_id(source_identity: str, target_identity: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    token = hashlib.sha256(
        f"{source_identity}:{target_identity}:{stamp}".encode()
    ).hexdigest()[:8]
    return f"pull-{stamp}-{token}"


def cloudpanel_ready_local() -> bool:
    return (
        shutil.which("clpctl") is not None
        and Path("/home/clp/htdocs/app/data/db.sq3").is_file()
    )


def local_target_db_engine_version() -> str:
    """Check only daemon binary version, never read credentials or alter state."""
    for executable_name in ("mariadbd", "mysqld"):
        executable = shutil.which(executable_name)
        if executable is None:
            continue
        try:
            p = subprocess.run(
                [executable, "--version"],
                capture_output=True, text=True, timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        output = (p.stdout + " " + p.stderr).lower()
        if p.returncode == 0 and "mariadb" in output:
            for version in ("10.11", "11.8"):
                if re.search(rf"(?<![0-9]){re.escape(version)}(?:\.[0-9]+)?(?![0-9])", output):
                    return f"MARIADB_{version}"
            return "MARIADB_OTHER"
        if p.returncode == 0 and ("mysql" in output or "percona" in output):
            return "MYSQL_OR_PERCONA"
    return "UNKNOWN"


def local_target_live_mariadb_process_version(
    *,
    proc_root: Path = Path("/proc"),
    socket_path: Path = Path("/run/mysqld/mysqld.sock"),
) -> str:
    """Credential-free proof that the active MariaDB service owns the SQL socket.

    CloudPanel creates a password-protected master account. A root socket
    ERROR 1045 is expected there; it is not permission to skip engine checks.
    Accept only the *running* systemd MainPID's executable version, and only
    when that exact PID owns the responding local Unix socket inode.
    """
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return "UNKNOWN"
    try:
        state = subprocess.run(
            [systemctl, "show", "mariadb.service",
             "--property=ActiveState,MainPID", "--no-pager"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if state.returncode != 0:
            return "UNKNOWN"
        values = dict(
            line.split("=", 1) for line in state.stdout.splitlines()
            if "=" in line
        )
        if values.get("ActiveState") != "active":
            return "UNKNOWN"
        pid = int(values.get("MainPID", "0"))
        if pid <= 1:
            return "UNKNOWN"
        proc_exe = proc_root / str(pid) / "exe"
        target = os.readlink(proc_exe)
        if target.endswith(" (deleted)") or Path(target).name not in ("mariadbd", "mysqld"):
            return "UNKNOWN"
        running = subprocess.run(
            [str(proc_exe), "--version"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        output = (running.stdout + " " + running.stderr).lower()
        if running.returncode != 0 or "mariadb" not in output:
            return "UNKNOWN"
        version = "MARIADB_OTHER"
        for supported in ("10.11", "11.8"):
            if re.search(rf"(?<![0-9]){re.escape(supported)}(?:[.][0-9]+)?(?![0-9])", output):
                version = f"MARIADB_{supported}"
                break
        socket_real = socket_path.resolve(strict=True)
        if not stat.S_ISSOCK(socket_real.stat().st_mode):
            return "UNKNOWN"
        inode = ""
        for line in (proc_root / "net" / "unix").read_text(encoding="utf-8").splitlines()[1:]:
            fields = line.split(None, 7)
            if len(fields) == 8 and Path(fields[7]).resolve() == socket_real:
                inode = fields[6]
                break
        if not inode:
            return "UNKNOWN"
        for fd in (proc_root / str(pid) / "fd").iterdir():
            try:
                if os.readlink(fd) == f"socket:[{inode}]":
                    return version
            except OSError:
                continue
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return "UNKNOWN"
    return "UNKNOWN"


def local_target_active_db_engine_version() -> str:
    """Verify the *running* local SQL server through a credential-free root socket.

    A MariaDB binary on PATH alone is not evidence that CloudPanel's target
    SQL endpoint is running MariaDB. Authentication failure is UNKNOWN.
    """
    client = shutil.which("mariadb") or shutil.which("mysql")
    if not client:
        return "UNKNOWN"
    try:
        p = subprocess.run(
            [
                client, "--no-defaults", "--protocol=socket", "--user=root",
                "--batch", "--skip-column-names", "--connect-timeout=5",
                "--execute=SELECT @@version, @@version_comment",
            ],
            capture_output=True, text=True, timeout=9, check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "UNKNOWN"
    if p.returncode != 0:
        # CloudPanel's master root is intentionally password-protected.
        # Accept only the exact access-denied class plus an independently
        # proven active MariaDB process owning this Unix socket.
        if (
            p.returncode == 1
            and "ERROR 1045 (28000)" in p.stderr
            and "Access denied for user 'root'@'localhost'" in p.stderr
            and "(using password: NO)" in p.stderr
        ):
            return local_target_live_mariadb_process_version()
        return "UNKNOWN"
    fields = p.stdout.strip().split("\t")
    if len(fields) != 2:
        return "UNKNOWN"
    version, comment = fields
    if "percona" not in comment.lower() and "mysql community" not in comment.lower():
        for supported in ("10.11", "11.8"):
            if re.match(
                rf"^(?:5[.]5[.]5-)?{re.escape(supported)}[.][0-9]+[-+]MariaDB(?:$|[-+])",
                version, re.I,
            ):
                return f"MARIADB_{supported}"
    if "mariadb" in version.lower():
        return "MARIADB_OTHER"
    if "mysql" in comment.lower() or "percona" in comment.lower():
        return "MYSQL_OR_PERCONA"
    return "UNKNOWN"


def required_mariadb_engine_local() -> str:
    """Read-only OS/CloudPanel compatibility check for the receiving VPS."""
    try:
        os_release = Path("/etc/os-release").read_text(encoding="utf-8")
        os_id, version_id = legacy.parse_os_release(os_release)
        return legacy.cloudpanel_db_engine_for_os(os_id, version_id)
    except (OSError, legacy.ServerMigrationError) as exc:
        raise PullMigrationError(
            "NEW_SERVER_MARIADB_OS_UNSUPPORTED: 不能确认当前系统支持的 MariaDB 版本；"
            "已停止迁移，不会修改数据库"
        ) from exc


def require_mariadb_target() -> None:
    # Both daemon binary and the live root socket must match the OS-specific
    # CloudPanel MariaDB engine. Fail closed before any import or SOURCE freeze.
    expected = required_mariadb_engine_local()
    if (
        local_target_db_engine_version() != expected
        or local_target_active_db_engine_version() != expected
    ):
        display_version = expected.removeprefix("MARIADB_")
        raise PullMigrationError(
            f"NEW_SERVER_REQUIRES_{expected.replace('.', '_')}: "
            f"新服务器必须实际运行 MariaDB {display_version}（含本机数据库连接验证）；"
            "如本机 root socket 无法只读验证，请先检查 CloudPanel/数据库服务。"
            "已停止迁移，不会自动卸载或替换任何已有数据库"
        )


def cloudpanel_user_count_local(
    db: Path = Path("/home/clp/htdocs/app/data/db.sq3"),
) -> int | None:
    if not db.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = conn.execute('SELECT COUNT(*) FROM "user"').fetchone()
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        return None
    if not row:
        return None
    return int(row[0] or 0)


def cloudpanel_database_server_ready_local(
    db: Path = Path("/home/clp/htdocs/app/data/db.sq3"),
) -> bool:
    if not db.is_file():
        return False
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT COUNT(*), "
                "SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END), "
                "MIN(length(trim(host))), MIN(length(trim(user_name))), "
                "MIN(length(password)) FROM database_server"
            ).fetchone()
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        return False
    if not row:
        return False
    count, active, host_len, user_len, password_len = row
    return bool(
        int(count or 0) > 0
        and int(active or 0) > 0
        and int(host_len or 0) > 0
        and int(user_len or 0) > 0
        and int(password_len or 0) > 0
    )


def target_identity() -> str:
    try:
        manifest = inventory.build_manifest(Path("/"))
        value = str((manifest.get("source_server") or {}).get("hostname_hash", ""))
        if value:
            return value
    except Exception:
        pass
    host = os.uname().nodename
    return "sha256:" + hashlib.sha256(host.encode()).hexdigest()[:16]


def target_preflight_local(source_plan: dict[str, Any]) -> dict[str, Any]:
    if not cloudpanel_ready_local():
        raise PullMigrationError("CURRENT_SERVER_CLOUDPANEL_MISSING")
    if not cloudpanel_database_server_ready_local():
        raise PullMigrationError("CURRENT_SERVER_CLOUDPANEL_DATABASE_SERVER_INCOMPLETE")
    require_mariadb_target()
    required = ("clpctl", "rsync", "python3", "curl", "systemctl", "crontab", "runuser")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        raise PullMigrationError("new-server required commands are missing: " + ",".join(missing))

    try:
        current = inventory.build_manifest(Path("/"))
    except Exception as exc:
        raise PullMigrationError("new-server CloudPanel inventory failed") from exc

    current_sites = [
        row for row in current.get("sites", [])
        if isinstance(row, dict)
    ]
    domains = {str(row.get("domain", "")).lower() for row in current_sites}
    users = {str(row.get("site_user", "")) for row in current_sites}
    databases: set[str] = set()
    for row in current_sites:
        raw = row.get("mysql_databases")
        if isinstance(raw, list):
            databases.update(str(item) for item in raw if item)

    conflicts: list[str] = []
    for site in source_plan.get("sites", []):
        if not isinstance(site, dict):
            continue
        domain = str(site.get("domain", ""))
        user = str(site.get("site_user", ""))
        source_dbs = site.get("mysql_databases")
        if domain.lower() in domains or user in users or (Path("/home") / user).exists():
            conflicts.append(domain)
            continue
        if isinstance(source_dbs, list) and any(str(db) in databases for db in source_dbs):
            conflicts.append(domain)
    if conflicts:
        raise PullMigrationError(
            "new server already has conflicting website/user/database: "
            + ",".join(sorted(set(conflicts)))
        )

    capacity = source_plan.get("capacity_estimate") or {}
    required_bytes = int(capacity.get("target_required_bytes") or 0)
    free = shutil.disk_usage("/").free
    if required_bytes and free < required_bytes:
        raise PullMigrationError("new-server free disk is below migration requirement")
    return {
        "status": "READY",
        "target_identity": target_identity(),
        "free_bytes": free,
        "required_bytes": required_bytes,
        "writes_performed": False,
    }


def local_cloud_hint() -> str:
    text = ""
    for path in (
        Path("/sys/class/dmi/id/sys_vendor"),
        Path("/sys/class/dmi/id/product_name"),
    ):
        try:
            text += "\n" + path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pass
    return legacy.detect_cloud_hint(text)


def local_bootstrap_preflight() -> dict[str, Any]:
    if os.geteuid() != 0:
        raise PullMigrationError("CloudPanel bootstrap requires root")
    try:
        text = Path("/etc/os-release").read_text(encoding="utf-8")
        os_id, version_id = legacy.parse_os_release(text)
    except OSError as exc:
        raise PullMigrationError("current server OS cannot be identified") from exc
    try:
        db_engine = legacy.cloudpanel_db_engine_for_os(os_id, version_id)
    except legacy.ServerMigrationError as exc:
        raise PullMigrationError(f"unsupported OS/MariaDB pair for CloudPanel: {os_id} {version_id}") from exc
    arch = os.uname().machine
    cores = os.cpu_count() or 0
    mem_kb = 0
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            mem_kb = int(line.split()[1])
            break
    disk = shutil.disk_usage("/").total
    if arch not in legacy.SUPPORTED_BOOTSTRAP_ARCH:
        raise PullMigrationError("unsupported architecture for CloudPanel")

    # Hardware sizing is advisory only. CloudPanel publishes a 1-core / 2-GB /
    # 10-GB baseline, but P07 must not turn that recommendation into an owner
    # policy gate. Real smaller servers may still be intentionally used for
    # testing or light workloads. Compatibility and empty-server safety checks
    # below remain fail-closed.
    hardware_advisories: list[str] = []
    if cores < legacy.CLOUDPANEL_MIN_CORES:
        hardware_advisories.append("CPU_BELOW_CLOUDPANEL_PUBLISHED_BASELINE")
    if mem_kb * 1024 < legacy.CLOUDPANEL_MIN_MEMORY_BYTES:
        hardware_advisories.append("MEMORY_BELOW_CLOUDPANEL_PUBLISHED_BASELINE")
    if disk < legacy.CLOUDPANEL_MIN_DISK_BYTES:
        hardware_advisories.append("DISK_BELOW_CLOUDPANEL_PUBLISHED_BASELINE")

    existing_environment: list[str] = []
    for command in ("nginx", "apache2", "mysql", "mariadb"):
        if shutil.which(command):
            existing_environment.append(command)

    # A leftover web-server config directory alone is not proof that a
    # conflicting service is installed or running. Images and removed packages
    # can leave /etc/nginx or /etc/apache2 behind. Report those as advisories,
    # while real binaries, CloudPanel state, and database data roots remain
    # fail-closed.
    environment_advisories: list[str] = []
    for path in (Path("/etc/nginx"), Path("/etc/apache2")):
        if path.exists():
            environment_advisories.append(f"STALE_CONFIG_DIR:{path}")

    for path in (
        Path("/home/clp"), Path("/home/mysql"),
        Path("/var/lib/mysql"), Path("/var/lib/mariadb"),
    ):
        if path.exists():
            existing_environment.append(str(path))
    if existing_environment:
        raise PullMigrationError(
            "current server is not empty enough for automatic CloudPanel install: "
            + ",".join(existing_environment)
        )
    if shutil.which("ss"):
        proc = run_local(["ss", "-ltnH"], timeout=30, check=False)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                local = line.split()[3] if len(line.split()) > 3 else ""
                if local.endswith(":80") or local.endswith(":443"):
                    raise PullMigrationError("current server already has Web listeners")
    cloud_hint = local_cloud_hint()

    return {
        "status": "READY",
        "os_id": os_id,
        "version_id": version_id,
        "cloud_hint": cloud_hint or "generic",
        "architecture": arch,
        "cores": cores,
        "memory_bytes": mem_kb * 1024,
        "disk_bytes": disk,
        "hardware_advisories": hardware_advisories,
        "hardware_baseline_is_advisory": True,
        "environment_advisories": environment_advisories,
        "installer_sha256": legacy.CLOUDPANEL_INSTALLER_SHA256,
        "db_engine": db_engine,
        "writes_performed": False,
    }


def bootstrap_local_cloudpanel(confirm: str) -> dict[str, Any]:
    if confirm != "BOOTSTRAP_LOCAL_CLOUDPANEL":
        raise PullMigrationError("explicit confirmation required: BOOTSTRAP_LOCAL_CLOUDPANEL")
    preflight = local_bootstrap_preflight()
    cloud_hint = "" if preflight["cloud_hint"] == "generic" else str(preflight["cloud_hint"])
    script = legacy.cloudpanel_bootstrap_script(cloud_hint, preflight["db_engine"])
    proc = subprocess.run(
        ["bash", "-lc", script],
        text=True,
        capture_output=True,
        check=False,
        timeout=5400,
    )
    if proc.returncode != 0 or not cloudpanel_ready_local():
        raise PullMigrationError(
            f"CLOUDPANEL_INSTALL_FAILED_{preflight['db_engine']}: "
            f"CloudPanel 安装未完成（安装进程退出码 {proc.returncode}）；"
            "不自动重试或覆盖现有组件，请先检查目标机安装状态"
        )
    if not cloudpanel_database_server_ready_local():
        user_count = cloudpanel_user_count_local()
        if user_count == 0:
            return {
                "schema": SCHEMA,
                "status": "CLOUDPANEL_ADMIN_REQUIRED",
                "target_role": "CURRENT_SERVER_RECEIVER",
                "installer_checksum_verified": True,
                "os_id": preflight["os_id"],
                "version_id": preflight["version_id"],
                "cloud_hint": preflight["cloud_hint"],
                "db_engine": preflight["db_engine"],
                "first_admin_required": True,
                "dns_changed": False,
                "source_changed": False,
                "secrets_emitted": False,
            }
        raise PullMigrationError(
            "CloudPanel installation incomplete: local database server metadata is missing"
        )
    return {
        "schema": SCHEMA,
        "status": "CLOUDPANEL_READY",
        "target_role": "CURRENT_SERVER_RECEIVER",
        "installer_checksum_verified": True,
        "os_id": preflight["os_id"],
        "version_id": preflight["version_id"],
        "db_engine": preflight["db_engine"],
        "dns_changed": False,
        "source_changed": False,
        "secrets_emitted": False,
    }


def create_target_site(mid: str, site: dict[str, Any]) -> None:
    token = hashlib.sha256(str(site["domain"]).encode()).hexdigest()[:16]
    path = state_dir(mid) / "site-metadata" / f"{token}.json"
    legacy.atomic_private_json(path, site)
    try:
        result = legacy.target_create_site_local(mid, path)
    except legacy.ServerMigrationError as exc:
        raise PullMigrationError("new-server CloudPanel site creation failed") from exc
    if result.get("status") != "CREATED":
        raise PullMigrationError("new-server site creation did not complete")


def pull_site_files(
    state: dict[str, Any],
    site: dict[str, Any],
    *,
    final: bool,
) -> None:
    path = str(site["site_root"])
    target = Path(path)
    if not target.is_dir():
        raise PullMigrationError(f"new-server website directory is missing: {site['domain']}")
    excludes: tuple[str, ...] = ()
    mysql = site.get("mysql_databases")
    if final and isinstance(mysql, list) and mysql:
        excludes = PROTECTED_DB_CONFIGS
    pull_path(
        state["source"],
        path.rstrip("/") + "/",
        target,
        user=str(site["site_user"]),
        delete=final,
        excludes=excludes,
    )


def remote_staging_root(state: dict[str, Any]) -> str:
    return f"/var/lib/vf-server-ops/pull-source/{state['migration_id']}/data"


def source_export_database(
    state: dict[str, Any],
    database: str,
    remote_file: str,
) -> None:
    proc = source_python(
        state["source"],
        state["source_runtime_path"],
        "_source-export-db",
        "--database", database,
        "--output", remote_file,
        timeout=3600,
        check=False,  # Caller must classify the pinned SQL-helper exit marker.
    )
    if proc.returncode != 0:
        # Only this complete fixed marker can be attributed to the pinned
        # source helper's no-schema sanity check. Never parse or echo raw
        # remote SQL/CLI stderr or misclassify authentication/SSH failures.
        if (proc.returncode == 13
                and (proc.stderr or "").strip() == "ERROR: SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA"):
            raise PullMigrationError("SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA")
        raise PullMigrationError(f"old-server MySQL export failed: {database}")


def guarded_export_comparison_advisory(
    source_dump: Path, target_dump: Path
) -> dict[str, Any]:
    """Probe exact conservative SQL comparator with NO migration state write.

    A live old-VPS source dump is not simultaneous with the stored target;
    even identical content here is advisory, not approval for a database
    re-import, migration resume, source freeze or DNS cutover.
    """
    try:
        mode = compare_database_dumps(source_dump, target_dump)
    except PullMigrationError as exc:
        detail = str(exc)
        reason = (
            "CONDITIONAL_DDL"
            if detail.startswith("MySQL verification failed [CONDITIONAL_DDL]")
            else "SCHEMA_OR_DATA_UNPROVEN"
        )
        return {"status": "BLOCKED", "reason": reason,
                "cutover_allowed": False}
    if mode not in {
        "CANONICAL_SQL_EXACT", "CROSS_ENGINE_GUARDED_SESSION_SQL_EXACT",
        "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
        "CROSS_ENGINE_LOGICAL_CONTENT",
    }:
        return {"status": "BLOCKED", "reason": "UNKNOWN_COMPARISON_MODE",
                "cutover_allowed": False}
    return {
        "status": "MATCH_ADVISORY_NOT_MIGRATION_PASS",
        "comparison_mode": mode,
        "cutover_allowed": False,
    }


def diagnose_sql_difference(
    mid: str, domain: str, *, expected_source_tables: int | None = None
) -> dict[str, Any]:
    """One selected DB, advisory read/export only; never resumes migration.

    SQL is kept in private temporary files and removed even on failure.
    No database import, target-site creation, state mutation, or cutover occurs.
    """
    # A caller-supplied observed inventory count (for example from the
    # existing source-panel read-only query) is a diagnostic assertion,
    # not independently established database truth or a migration PASS.
    if expected_source_tables is not None and (
        type(expected_source_tables) is not int
        or not 1 <= expected_source_tables <= 100000
    ):
        raise PullMigrationError("SQL_DIAGNOSTIC_EXPECTED_TABLES_INVALID")
    state = load_state(mid)
    if state.get("status") != "PREPARE_FAILED":
        raise PullMigrationError("SQL_DIAGNOSTIC_REQUIRES_PREPARE_FAILED")
    selected = [
        site for site in state.get("sites", [])
        if isinstance(site, dict) and site.get("domain") == domain
    ]
    if len(selected) != 1:
        raise PullMigrationError("SQL_DIAGNOSTIC_SITE_NOT_IN_MIGRATION")
    databases = selected[0].get("mysql_databases")
    if not isinstance(databases, list) or len(databases) != 1:
        raise PullMigrationError("SQL_DIAGNOSTIC_SINGLE_DATABASE_REQUIRED")
    database = databases[0]
    if not isinstance(database, str) or not database:
        raise PullMigrationError("SQL_DIAGNOSTIC_DATABASE_INVALID")
    if not state.get("source_runtime_path") or not state.get("source"):
        raise PullMigrationError("SQL_DIAGNOSTIC_SOURCE_RUNTIME_UNAVAILABLE")

    # The helper on the source VPS may be an older, already-staged runtime.
    # Validate the received SQL locally before trusting its schema counters.
    # A second independent export is allowed only when the first completed
    # transfer has no verifiable CREATE TABLE; never retry authentication or
    # transport failures. Both exports are read-only at the database layer.
    remote_files: list[str] = []
    diagnostic_state = state
    temporary_helper = ""
    try:
        # The stored helper can predate the receiver's SQL export sanity
        # protection. Diagnose with verified current source bytes, but never
        # change the migration's pinned runtime path or state on this command.
        if not source_export_helper_matches_current(
            state["source"], str(state["source_runtime_path"])
        ):
            temporary_helper = stage_source_runtime(
                state["source"], "probe-" + os.urandom(16).hex()
            )
            if not source_export_helper_matches_current(
                state["source"], temporary_helper
            ):
                raise PullMigrationError("SQL_DIAGNOSTIC_HELPER_UNVERIFIED")
            diagnostic_state = dict(state)
            diagnostic_state["source_runtime_path"] = temporary_helper
        with tempfile.TemporaryDirectory(prefix="vfops-sql-evidence-") as directory:
            root = Path(directory)
            os.chmod(root, 0o700)
            target_dump = root / "target.sql.gz"
            try:
                evidence = {
                    "schema": "SQL_DIFF_EVIDENCE_V2",
                    "verification": "SOURCE_EXPORT_UNUSABLE",
                    "data_content": {"comparison": "UNAVAILABLE"},
                    # A failed export is UNKNOWN, never evidence of an empty source DB.
                    "source_export_readback": {"attempts": 2, "source_tables": None},
                }
                for attempt in range(2):
                    evidence["source_export_readback"]["attempts"] = attempt + 1
                    token = os.urandom(16).hex()
                    remote_file = f"{remote_staging_root(state)}/advisory-{token}.sql.gz"
                    remote_files.append(remote_file)
                    source_dump = root / f"source-{attempt + 1}.sql.gz"
                    try:
                        source_export_database(diagnostic_state, database, remote_file)
                    except PullMigrationError as exc:
                        if str(exc) != "SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA":
                            raise
                        # The verified source helper rejected a completed
                        # export without table DDL. Retry only once, never on
                        # permission/transport/unknown failures.
                        continue
                    pull_path(state["source"], remote_file, source_dump)
                    try:
                        count = sql_diff_probe.require_nonempty_source_schema(source_dump)
                    except sql_diff_probe.AdvisoryDiagnosticUnavailable:
                        # Retry once; never interpret absent schema as zero
                        # source tables or successful cross-engine parity.
                        continue
                    if expected_source_tables is not None and count != expected_source_tables:
                        # An apparently valid but incomplete dump is not a
                        # usable comparison. Retry the source read once and
                        # never export/import/touch the target on mismatch.
                        evidence = {
                            "schema": "SQL_DIFF_EVIDENCE_V2",
                            "verification": "SOURCE_TABLE_COUNT_MISMATCH",
                            "data_content": {"comparison": "UNAVAILABLE"},
                            "source_export_readback": {
                                "attempts": attempt + 1,
                                "source_tables": count,
                                "expected_source_tables": expected_source_tables,
                                "source_table_count_matches_expectation": False,
                            },
                        }
                        continue
                    cloudpanel.export_database(database, target_dump, clpctl="clpctl")
                    evidence = sql_diff_probe.diagnostic(source_dump, target_dump)
                    evidence["guarded_export_comparison"] = (
                        guarded_export_comparison_advisory(source_dump, target_dump)
                    )
                    evidence["source_export_readback"] = {
                        "attempts": attempt + 1, "source_tables": count,
                    }
                    if expected_source_tables is not None:
                        evidence["source_export_readback"].update({
                            "expected_source_tables": expected_source_tables,
                            "source_table_count_matches_expectation": True,
                        })
                    # Only when the first read-only comparison *already*
                    # detected a row discrepancy, take one independent source
                    # readback. It can detect temporal drift, never prove an
                    # atomic snapshot or authorize migration continuation.
                    if evidence.get("row_tuples", {}).get("comparison") == "ROW_TUPLES_DIFFER":
                        evidence["source_readback_stability"] = {
                            "comparison": "UNAVAILABLE",
                            "verification": "NOT_A_PASS_GATE",
                        }
                        repeat_token = os.urandom(16).hex()
                        repeat_remote = (
                            f"{remote_staging_root(state)}/advisory-{repeat_token}.sql.gz"
                        )
                        remote_files.append(repeat_remote)
                        repeat_local = root / "source-readback.sql.gz"
                        try:
                            source_export_database(diagnostic_state, database, repeat_remote)
                            pull_path(state["source"], repeat_remote, repeat_local)
                            repeat_count = sql_diff_probe.require_nonempty_source_schema(
                                repeat_local
                            )
                            if repeat_count != count:
                                evidence["source_readback_stability"] = {
                                    "comparison": "TABLE_COUNT_CHANGED",
                                    "verification": "NOT_A_PASS_GATE",
                                }
                            else:
                                # Table identity, not only table count, is
                                # checked by the independent multiset parser.
                                names_first = set(sql_diff_probe._schema_statements(source_dump)[0])
                                names_second = set(sql_diff_probe._schema_statements(repeat_local)[0])
                                stable = sql_diff_probe.sql_multiset_evidence.diagnostic(
                                    source_dump, repeat_local,
                                    names_first, names_second,
                                )
                                if stable.get("comparison") == "ROW_MULTISET_EQUAL_NOT_VERIFIED":
                                    state_label = "SAME_DUMP_TUPLES_IN_READBACK_WINDOW"
                                elif stable.get("comparison") == "ROW_MULTISET_DIFFER":
                                    state_label = "SOURCE_TUPLES_CHANGED_BETWEEN_EXPORTS"
                                else:
                                    state_label = "UNAVAILABLE"
                                evidence["source_readback_stability"] = {
                                    "comparison": state_label,
                                    "verification": "NOT_A_PASS_GATE",
                                }
                        except (
                            PullMigrationError, cloudpanel.CloudPanelError,
                            transport.TransportError, OSError, ValueError,
                            sql_diff_probe.AdvisoryDiagnosticUnavailable,
                        ):
                            # A failed second read never masks the original
                            # evidence or produces a migration acceptance.
                            pass
                    break
            except (
                PullMigrationError, cloudpanel.CloudPanelError,
                transport.TransportError, OSError, ValueError,
            ) as exc:
                raise PullMigrationError("SQL_DIAGNOSTIC_EXPORT_UNAVAILABLE") from exc
    finally:
        try:
            # Remove only the unpredictable export files created by this call.
            for remote_file in remote_files:
                source_remote(
                    state["source"],
                    f"rm -f -- {shlex.quote(remote_file)}",
                    timeout=60,
                    check=False,
                )
        finally:
            if temporary_helper:
                cleanup_probe_runtime(state["source"], temporary_helper)
    return {
        "status": "ADVISORY_DIAGNOSTIC_ONLY",
        "source_temporary_helper_written": bool(temporary_helper),
        "source_helper_cleanup_attempted": bool(temporary_helper),
        "database_writes_performed": False,
        "migration_state_modified": False,
        "dns_changed": False,
        "source_deleted": False,
        "evidence": evidence,
    }


def compare_database_dumps(source_dump: Path, target_dump: Path) -> str:
    try:
        # A full SQL digest equality or a cross-engine normalized match never
        # proves that version-guarded dynamic SQL is harmless. The source and
        # the target may run branches under different server versions. Check
        # each dump *before* allowing any fingerprint shortcut.
        for candidate in (source_dump, target_dump):
            try:
                if verify_engine.sql_unproven_side_effects(candidate):
                    raise verify_engine.RestoreVerifyError(
                        "SQL unproven side effect or privilege statement"
                    )
                branch_counts = sql_diff_probe.dynamic_guard_syntax_counts(candidate)
            except sql_diff_probe.AdvisoryDiagnosticUnavailable as exc:
                raise verify_engine.RestoreVerifyError(
                    "SQL dump cannot be fingerprinted"
                ) from exc
            if any(branch_counts.get(key, 0) for key in (
                "recognized_unsafe", "other_unknown_set", "double_quoted_if"
            )):
                raise verify_engine.RestoreVerifyError(
                    "conditional SQL DDL is not independently verified"
                )
        before, before_count = verify_engine.sql_fingerprint(source_dump)
        after, after_count = verify_engine.sql_fingerprint(target_dump)
        if before == after and before_count == after_count:
            return "CANONICAL_SQL_EXACT"
        # MariaDB/MySQL may emit the same executed SET directive behind
        # different old-version guards. Before invoking conservative schema
        # parsing, accept only a strict complete-SQL digest where every
        # conditional DDL byte, row literal, and delimiter remains covered.
        guarded_before, guarded_before_count = verify_engine.sql_guarded_session_fingerprint(source_dump)
        guarded_after, guarded_after_count = verify_engine.sql_guarded_session_fingerprint(target_dump)
        if guarded_before == guarded_after and guarded_before_count == guarded_after_count:
            return "CROSS_ENGINE_GUARDED_SESSION_SQL_EXACT"
        # The exact full-SQL cross-engine gate accepts only enumerated, proven
        # dump presentation differences; every data literal and DDL is hashed.
        try:
            cross_before = verify_engine.sql_cross_engine_known_format_fingerprint(source_dump)
            cross_after = verify_engine.sql_cross_engine_known_format_fingerprint(target_dump)
            if cross_before == cross_after:
                return "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT"
        except verify_engine.RestoreVerifyError:
            # Unknown syntax never gains equivalence from this new gate.
            pass
        if (
            verify_engine.sql_structure_fingerprint(source_dump)
            == verify_engine.sql_structure_fingerprint(target_dump)
            and verify_engine.sql_data_fingerprint(source_dump)
            == verify_engine.sql_data_fingerprint(target_dump)
        ):
            return "CROSS_ENGINE_LOGICAL_CONTENT"
    except verify_engine.RestoreVerifyError as exc:
        # Expose only a fixed, non-sensitive verifier reason code. SQL dumps can
        # contain production data and must never be printed in operator output.
        detail = str(exc)
        reason = "UNCLASSIFIED_SQL_VERIFICATION"
        if detail.startswith(("SQL dump cannot be fingerprinted",
                               "SQL side-effect scan cannot be read",
                               "cross-engine dynamic guard scan cannot be read")):
            reason = "SQL_DUMP_UNREADABLE"
        elif detail.startswith("SQL dump has no comparable statements"):
            reason = "NO_COMPARABLE_STATEMENTS"
        elif detail.startswith("SQL schema cannot be fingerprinted"):
            reason = "SQL_SCHEMA_UNREADABLE"
        elif detail.startswith("no comparable SQL schema statements"):
            reason = "NO_COMPARABLE_SCHEMA"
        elif detail.startswith("unterminated SQL schema statement"):
            reason = "UNTERMINATED_SCHEMA"
        elif detail.startswith("custom SQL delimiters"):
            reason = "CUSTOM_DELIMITER"
        elif detail.startswith("conditional SQL DDL"):
            reason = "CONDITIONAL_DDL"
        elif detail.startswith("SQL unproven side effect or privilege statement"):
            reason = "UNPROVEN_PRIVILEGED_SQL"
        elif detail.startswith("multiline SQL data"):
            reason = "MULTILINE_DATA"
        elif detail.startswith("unrecognized SQL data command"):
            reason = "UNRECOGNIZED_DATA_COMMAND"
        elif detail.startswith("SQL dump cannot be content-fingerprinted"):
            reason = "SQL_CONTENT_UNREADABLE"
        elif detail.startswith("SQL dump has no comparable logical content"):
            reason = "NO_COMPARABLE_LOGICAL_CONTENT"
        diagnostic = ""
        if reason == "CONDITIONAL_DDL":
            # Diagnostics must not change the fail-closed decision or echo SQL.
            try:
                diagnostic = " [" + verify_engine.sql_comparison_diagnostic(source_dump, target_dump) + "]"
            except verify_engine.RestoreVerifyError:
                diagnostic = " [SQL_DIFF_V1_UNAVAILABLE]"
            # Treat normalized statement mismatch as an observable failure,
            # not as proof of an equivalent cross-engine database.
            try:
                diagnostic += " [" + verify_engine.sql_cross_engine_known_format_diagnostic(
                    source_dump, target_dump
                ) + "]"
            except verify_engine.RestoreVerifyError:
                diagnostic += " [SQL_CANON_V2_UNAVAILABLE]"
            try:
                diagnostic += " [" + verify_engine.sql_cross_engine_shape_diagnostic(
                    source_dump, target_dump
                ) + "]"
            except verify_engine.RestoreVerifyError:
                diagnostic += " [SQL_SHAPE_V1_UNAVAILABLE]"
            try:
                diagnostic += " [" + verify_engine.sql_dynamic_guard_flow_diagnostic(source_dump) + "]"
            except verify_engine.RestoreVerifyError:
                diagnostic += " [SQL_GUARD_FLOW_V1_UNAVAILABLE]"
        raise PullMigrationError(f"MySQL verification failed [{reason}]{diagnostic}") from exc
    raise PullMigrationError("MySQL logical-content verification failed [SCHEMA_OR_DATA_MISMATCH]")


def sync_site_databases(state: dict[str, Any], site: dict[str, Any], *, phase: str) -> int:
    raw = site.get("mysql_databases")
    if not isinstance(raw, list):
        raise PullMigrationError(f"MySQL inventory is invalid: {site['domain']}")
    if len(raw) > 1:
        raise PullMigrationError(
            f"automatic app-config remap is ambiguous for multi-database site: {site['domain']}"
        )
    if not raw:
        return 0
    work = state_dir(state["migration_id"]) / "mysql" / phase
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    count = 0
    for index, value in enumerate(raw, 1):
        database = str(value)
        token = hashlib.sha256(
            f"{site['domain']}:{database}:{phase}".encode()
        ).hexdigest()[:16]
        remote_dump = f"{remote_staging_root(state)}/{token}.sql.gz"
        source_dump = work / f"{token}-source.sql.gz"
        import_dump = work / f"{token}-import.sql.gz"
        target_dump = work / f"{token}-target.sql.gz"
        import_started = False
        verification_completed = False
        try:
            phase_cn = "最终同步" if phase == "final" else "首轮迁入"
            progress_note(f"{phase_cn} MySQL · 正在导出 {database}")
            source_export_database(state, database, remote_dump)
            progress_note(f"{phase_cn} MySQL · 正在传输 {database}")
            pull_path(state["source"], remote_dump, source_dump)
            # Never send an empty/header-only or unparseable source SQL export
            # into target_create_database_local, which can mutate the receiver.
            # This check proves only a usable source schema; row parity and
            # guarded DDL verification still run after import.
            try:
                sql_diff_probe.require_nonempty_source_schema(source_dump)
            except sql_diff_probe.AdvisoryDiagnosticUnavailable as exc:
                raise PullMigrationError(
                    "old-server MySQL export has no verifiable table schema"
                ) from exc
            # Schema presence is only a one-way advisory. If non-UTF-8 data
            # bytes were present, the strict verification pipeline cannot
            # establish source/target row identity. Stop BEFORE CloudPanel
            # creates a database or rewrites application configuration.
            try:
                sql_diff_probe.require_source_import_utf8_integrity(source_dump)
            except sql_diff_probe.AdvisoryDiagnosticUnavailable as exc:
                label = str(exc)
                if label == "SQL_SOURCE_IMPORT_ENCODING_UNPROVEN":
                    raise PullMigrationError(
                        "SQL_SOURCE_IMPORT_ENCODING_UNPROVEN"
                    ) from None
                raise PullMigrationError(
                    "SQL_SOURCE_IMPORT_STREAM_UNVERIFIED"
                ) from None
            shutil.copy2(source_dump, import_dump)
            progress_note(f"{phase_cn} MySQL · 正在导入 {database}")
            # From here onward, target DB and application config MAY have
            # changed even when the command eventually raises. Preserve
            # private SQL bytes for a safe, read-only recovery assessment.
            import_started = True
            try:
                result = legacy.target_create_database_local(
                    state["migration_id"],
                    str(site["domain"]),
                    Path(str(site["site_root"])),
                    database,
                    index,
                    import_dump,
                )
            except legacy.ServerMigrationError as exc:
                detail = str(exc)
                if "target database import failed" in detail:
                    raise PullMigrationError(
                        f"new-server MySQL import failed: {database}"
                    ) from exc
                if "target application database config remap failed" in detail:
                    raise PullMigrationError(
                        f"new-server application DB config remap failed: {database}"
                    ) from exc
                raise PullMigrationError(
                    f"new-server MySQL transaction failed: {database}"
                ) from exc
            progress_note(f"{phase_cn} MySQL · 正在校验 {database}")
            try:
                cloudpanel.export_database(database, target_dump, clpctl="clpctl")
            except (cloudpanel.CloudPanelError, ValueError) as exc:
                raise PullMigrationError(
                    f"new-server MySQL verification export failed: {database}"
                ) from exc
            mode = compare_database_dumps(source_dump, target_dump)
            rows = site.setdefault("mysql_verification", [])
            rows[:] = [
                row for row in rows
                if not (
                    isinstance(row, dict)
                    and row.get("database") == database
                    and row.get("phase") == phase
                )
            ]
            rows.append({
                "database": database,
                "phase": phase,
                "status": "PASS",
                "mode": mode,
                "config_mode": result.get("application_config_mode"),
                "config_file": result.get("application_config_file"),
            })
            count += 1
            verification_completed = True
        except Exception as exc:
            if import_started and not verification_completed:
                # This is forensic retention, NOT import rollback or a
                # relaxation of any SQL verifier / resume gate.
                from migration_sql_failure_retention import retain_failed_import
                reason = (
                    "CONDITIONAL_DDL"
                    if isinstance(exc, PullMigrationError) and
                    str(exc).startswith("MySQL verification failed [CONDITIONAL_DDL]")
                    else "IMPORT_OR_VERIFICATION_FAILURE"
                )
                try:
                    site["failed_prepare_sql_evidence"] = retain_failed_import(
                        migration_id=str(state["migration_id"]),
                        domain=str(site["domain"]),
                        database=database,
                        phase=phase,
                        source_dump=source_dump,
                        import_dump=import_dump,
                        target_dump=target_dump,
                        reason=reason,
                    )
                except Exception:
                    # Never replace the original DB error with an evidence
                    # logger error; keep all private exports for inspection.
                    site["failed_prepare_sql_evidence"] = {
                        "status": "EVIDENCE_RETENTION_UNVERIFIED",
                        "reason": reason,
                        "cutover_allowed": False,
                        "db_reimport_allowed": False,
                    }
            raise
        finally:
            source_remote(
                state["source"],
                f"rm -f -- {shlex.quote(remote_dump)}",
                timeout=60,
                check=False,
            )
            # Source/temp SQL from a potentially changed target DB must
            # survive a verifier failure. The existing 0700 migration
            # directory is owner-private; no business data is deleted here.
            if not import_started or verification_completed:
                for path in (source_dump, import_dump, target_dump):
                    path.unlink(missing_ok=True)
    return count


def ensure_local_parent(path: Path, user: str) -> None:
    group, uid, gid = local_user_group(user)
    _ = group
    if path.exists():
        return
    path.mkdir(parents=True, exist_ok=True)
    os.chown(path, uid, gid)
    os.chmod(path, 0o750)


def sync_external_assets(
    state: dict[str, Any],
    *,
    final: bool,
    only_paths: set[str] | None = None,
) -> list[str]:
    synced: list[str] = []
    for row in state.get("external_assets", []):
        if not isinstance(row, dict):
            continue
        source_path = str(row["path"])
        if only_paths is not None and source_path not in only_paths:
            continue
        user = str(row["user"])
        target = Path(source_path)
        ensure_local_parent(target.parent, user)

        kind = str(row.get("kind") or "")
        if kind not in {"DIRECTORY", "FILE"}:
            kind = source_path_kind(state["source"], source_path)
            row["kind"] = kind

        if target.is_symlink():
            raise PullMigrationError(
                f"new-server external target is a symlink: {source_path}"
            )

        if kind == "DIRECTORY":
            if target.exists() and not target.is_dir():
                raise PullMigrationError(
                    f"new-server external target type conflict: {source_path}"
                )
            if not target.exists():
                target.mkdir(parents=True, exist_ok=True)
                _, uid, gid = local_user_group(user)
                os.chown(target, uid, gid)
            pull_path(
                state["source"],
                source_path.rstrip("/") + "/",
                target,
                user=user,
                delete=final,
            )
        else:
            # release62 could create an empty directory before discovering that
            # the source external asset was actually a file. Remove only that
            # empty placeholder; any non-empty directory fails closed.
            if target.is_dir():
                try:
                    target.rmdir()
                except OSError as exc:
                    raise PullMigrationError(
                        f"new-server external target type conflict: {source_path}"
                    ) from exc
            elif target.exists() and not target.is_file():
                raise PullMigrationError(
                    f"new-server external target type conflict: {source_path}"
                )
            pull_path(
                state["source"],
                source_path,
                target,
                user=user,
                delete=False,
            )

        synced.append(source_path)
    return sorted(set(synced))


def sync_sqlite_assets(
    state: dict[str, Any],
    *,
    phase: str,
    only_paths: set[str] | None = None,
) -> int:
    count = 0
    work = state_dir(state["migration_id"]) / "sqlite" / phase
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    for row in state.get("sqlite_assets", []):
        if not isinstance(row, dict):
            continue
        source_path = str(row["path"])
        if only_paths is not None and source_path not in only_paths:
            continue
        user = str(row["user"])
        mode = int(row.get("mode") or 0o600)
        token = hashlib.sha256(source_path.encode()).hexdigest()[:16]
        remote_snap = f"{remote_staging_root(state)}/sqlite-{token}.sqlite"
        local_snap = work / f"{token}.sqlite"
        phase_cn = "最终同步" if phase == "final" else "首轮迁入"
        progress_note(f"{phase_cn} SQLite · 正在生成一致性快照 {source_path}")
        proc = source_python(
            state["source"],
            state["source_runtime_path"],
            "_source-snapshot-sqlite",
            "--source", source_path,
            "--output", remote_snap,
            timeout=600,
        )
        if proc.returncode != 0:
            raise PullMigrationError(f"old-server SQLite snapshot failed: {source_path}")
        try:
            pull_path(state["source"], remote_snap, local_snap)
            conn = sqlite3.connect(f"file:{local_snap}?mode=ro", uri=True)
            try:
                check = conn.execute("PRAGMA quick_check").fetchone()
            finally:
                conn.close()
            if not check or check[0] != "ok":
                raise PullMigrationError(f"SQLite snapshot verification failed: {source_path}")
            target = Path(source_path)
            ensure_local_parent(target.parent, user)
            for suffix in ("-wal", "-shm", "-journal"):
                Path(str(target) + suffix).unlink(missing_ok=True)
            temp = target.parent / f".vfops-{token}.sqlite"
            shutil.copy2(local_snap, temp)
            _, uid, gid = local_user_group(user)
            os.chown(temp, uid, gid)
            os.chmod(temp, mode)
            os.replace(temp, target)
            for suffix in ("-wal", "-shm", "-journal"):
                Path(str(target) + suffix).unlink(missing_ok=True)
            conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
            try:
                check = conn.execute("PRAGMA quick_check").fetchone()
            finally:
                conn.close()
            if not check or check[0] != "ok":
                raise PullMigrationError(f"new-server SQLite verification failed: {source_path}")
            count += 1
        finally:
            source_remote(
                state["source"],
                f"rm -f -- {shlex.quote(remote_snap)}",
                timeout=60,
                check=False,
            )
            local_snap.unlink(missing_ok=True)
    return count



def _sqlite_quick_check_local(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute("PRAGMA quick_check").fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    return bool(row and row[0] == "ok")


def pre_cutover_reconcile(
    state: dict[str, Any],
    *,
    home_root: Path = Path("/home"),
) -> dict[str, Any]:
    failures: list[str] = []
    home_prefix = str(home_root.resolve()) + os.sep
    checked = {
        "sites": 0,
        "external_assets": 0,
        "sqlite_assets": 0,
        "mysql_databases": 0,
        "runtime_assets": 0,
        "source_http_baselines": 0,
    }

    for site in state.get("sites", []):
        if not isinstance(site, dict):
            continue
        domain = str(site.get("domain") or "UNKNOWN")
        checked["sites"] += 1
        if site.get("stage_status") != "PULLED_STAGED":
            failures.append(f"SITE_NOT_STAGED:{domain}")
        document_root = str(site.get("document_root") or site.get("site_root") or "")
        document_path = Path(document_root)
        try:
            document_real = str(document_path.resolve(strict=False))
        except OSError:
            document_real = ""
        if (
            not document_real.startswith(home_prefix)
            or not document_path.is_dir()
        ):
            failures.append(f"SITE_DOCUMENT_ROOT_MISSING:{domain}")

        raw_dbs = site.get("mysql_databases")
        if isinstance(raw_dbs, list):
            verification = [
                row for row in site.get("mysql_verification", [])
                if isinstance(row, dict)
            ]
            for database in raw_dbs:
                checked["mysql_databases"] += 1
                db = str(database)
                if not any(
                    row.get("database") == db
                    and row.get("phase") == "prepare"
                    and row.get("status") == "PASS"
                    for row in verification
                ):
                    failures.append(f"MYSQL_PREPARE_NOT_VERIFIED:{domain}:{db}")
        else:
            failures.append(f"MYSQL_INVENTORY_INVALID:{domain}")

    for row in state.get("external_assets", []):
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path:
            continue
        checked["external_assets"] += 1
        kind = str(row.get("kind") or "")
        if kind not in {"DIRECTORY", "FILE"}:
            kind = source_path_kind(state["source"], path)
            row["kind"] = kind
        target = Path(path)
        if kind == "DIRECTORY" and not target.is_dir():
            failures.append(f"EXTERNAL_DIRECTORY_MISSING:{path}")
        elif kind == "FILE" and not target.is_file():
            failures.append(f"EXTERNAL_FILE_MISSING:{path}")

    for row in state.get("sqlite_assets", []):
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path:
            continue
        checked["sqlite_assets"] += 1
        if not _sqlite_quick_check_local(Path(path)):
            failures.append(f"SQLITE_NOT_VERIFIED:{path}")

    runtime_assets = state.get("runtime_assets")
    if not isinstance(runtime_assets, dict):
        runtime_assets = {}
    runtime_pairs = (
        ("system_cron", "pending_system_cron"),
        ("user_cron", "pending_user_cron"),
        ("pm2", "pending_pm2"),
    )
    for source_key, pending_key in runtime_pairs:
        expected = runtime_assets.get(source_key, [])
        pending = state.get(pending_key, [])
        expected_count = len(expected) if isinstance(expected, list) else 0
        pending_count = len(pending) if isinstance(pending, list) else 0
        checked["runtime_assets"] += expected_count
        if expected_count != pending_count:
            failures.append(
                f"RUNTIME_STAGE_COUNT_MISMATCH:{source_key}:{expected_count}:{pending_count}"
            )

    baseline = state.get("source_http_baseline")
    baseline_required = bool(state.get("source_http_baseline_required"))
    if isinstance(baseline, dict):
        for site in state.get("sites", []):
            if not isinstance(site, dict):
                continue
            domain = str(site.get("domain") or "")
            if not domain:
                continue
            checked["source_http_baselines"] += 1
            row = baseline.get(domain)
            if baseline_required and (
                not isinstance(row, dict) or row.get("status") != "PASS"
            ):
                failures.append(f"SOURCE_HTTP_BASELINE_UNAVAILABLE:{domain}")
    elif baseline_required:
        failures.append("SOURCE_HTTP_BASELINE_MISSING")

    return {
        "status": "PASS" if not failures else "FAIL",
        "checked": checked,
        "failures": failures,
    }


def stage_runtime_assets(state: dict[str, Any]) -> None:
    runtime_root = state_dir(state["migration_id"]) / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    pending_system: list[dict[str, Any]] = []
    pending_user: list[dict[str, Any]] = []
    pending_pm2: list[dict[str, Any]] = []

    for row in state.get("runtime_assets", {}).get("system_cron", []):
        source_path = str(row["path"])
        token = hashlib.sha256(source_path.encode()).hexdigest()[:12]
        staged = runtime_root / "system-cron" / f"{token}.cron"
        staged.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        pull_path(state["source"], source_path, staged)
        os.chmod(staged, 0o600)
        pending_system.append({
            "source_path": source_path,
            "staged_target": str(staged),
            "activated": False,
        })

    for row in state.get("runtime_assets", {}).get("user_cron", []):
        source_path = str(row["path"])
        user = str(row["user"])
        staged = runtime_root / "user-cron" / f"{package_engine.safe_name(user)}.cron"
        staged.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        pull_path(state["source"], source_path, staged)
        os.chmod(staged, 0o600)
        pending_user.append({
            "user": user,
            "source_path": source_path,
            "staged_target": str(staged),
            "activated": False,
        })

    for row in state.get("runtime_assets", {}).get("pm2", []):
        user = str(row["user"])
        dump_source = str(row["dump"])
        node_source = str(row["node_runtime"])
        staged = runtime_root / "pm2" / f"{package_engine.safe_name(user)}.json"
        staged.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        pull_path(state["source"], dump_source, staged)
        os.chmod(staged, 0o600)
        node_target = Path("/home") / user / ".nvm/versions/node" / Path(node_source).name
        ensure_local_parent(node_target.parent, user)
        if not node_target.exists():
            node_target.mkdir(parents=True, exist_ok=True)
        pull_path(
            state["source"],
            node_source.rstrip("/") + "/",
            node_target,
            user=user,
        )
        pending_pm2.append({
            "user": user,
            "source_path": dump_source,
            "staged_target": str(staged),
            "source_node_runtime": node_source,
            "target_node_runtime": str(node_target),
            "activated": False,
        })

    state["pending_system_cron"] = pending_system
    state["pending_user_cron"] = pending_user
    state["pending_pm2"] = pending_pm2


def create_source_freeze_control(state: dict[str, Any]) -> str:
    control = {
        "migration_id": state["migration_id"],
        "sites": state["sites"],
        "pending_system_cron": [
            {"source_path": row["source_path"], "activated": False}
            for row in state.get("pending_system_cron", [])
        ],
        "pending_user_cron": [
            {
                "user": row["user"],
                "source_path": row["source_path"],
                "activated": False,
            }
            for row in state.get("pending_user_cron", [])
        ],
        "pending_pm2": [
            {
                "user": row["user"],
                "source_path": row["source_path"],
                "activated": False,
            }
            for row in state.get("pending_pm2", [])
        ],
    }
    local = state_dir(state["migration_id"]) / "source-freeze-control.json"
    legacy.atomic_private_json(local, control)
    remote = f"{remote_staging_root(state)}/freeze-control.json"
    push_control_file(state["source"], local, remote)
    return remote


def freeze_old_server(state: dict[str, Any]) -> None:
    control = create_source_freeze_control(state)
    proc = source_python(
        state["source"],
        state["source_runtime_path"],
        "_source-freeze",
        "--migration-id", state["migration_id"],
        "--control", control,
        timeout=600,
    )
    if proc.returncode != 0:
        raise PullMigrationError("old-server runtime freeze failed")
    state["source_runtime_frozen"] = True
    save_state(state)


def restore_old_server(state: dict[str, Any]) -> bool:
    proc = source_python(
        state["source"],
        state["source_runtime_path"],
        "_source-restore",
        "--migration-id", state["migration_id"],
        timeout=600,
    )
    if proc.returncode != 0:
        return False
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False
    ok = payload.get("status") == "SOURCE_RESTORED"
    if ok:
        state["source_runtime_frozen"] = False
        save_state(state)
    return ok


def activate_target_runtime(state: dict[str, Any]) -> None:
    for row in state.get("pending_user_cron", []):
        if row.get("activated"):
            continue
        user = str(row["user"])
        existing = run_local(["crontab", "-u", user, "-l"], timeout=30, check=False)
        if existing.returncode == 0:
            meaningful = [
                line for line in existing.stdout.splitlines()
                if line.strip()
                and not line.lstrip().startswith("#")
                and not (
                    "=" in line
                    and line.split("=", 1)[0].strip().replace("_", "").isalnum()
                    and " " not in line.split("=", 1)[0].strip()
                )
            ]
            if meaningful:
                raise PullMigrationError(f"new-server user Cron already contains jobs: {user}")
        proc = run_local(
            ["crontab", "-u", user, str(row["staged_target"])],
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            raise PullMigrationError(f"new-server user Cron activation failed: {user}")
        row["activated"] = True
        save_state(state)

    for row in state.get("pending_pm2", []):
        if row.get("activated"):
            continue
        try:
            result = legacy.target_activate_pm2_local(
                str(row["user"]),
                Path(str(row["staged_target"])),
            )
        except legacy.ServerMigrationError as exc:
            raise PullMigrationError(
                f"new-server PM2 activation failed: {row['user']}"
            ) from exc
        if result.get("status") != "PM2_ACTIVATED":
            raise PullMigrationError(f"new-server PM2 activation failed: {row['user']}")
        row["activated"] = True
        save_state(state)

    for row in state.get("pending_system_cron", []):
        if row.get("activated"):
            continue
        target = Path(str(row["source_path"]))
        if not str(target).startswith("/etc/cron.d/"):
            raise PullMigrationError("unsafe new-server system Cron path")
        if target.exists():
            raise PullMigrationError(f"new-server system Cron already exists: {target}")
        shutil.copy2(str(row["staged_target"]), target)
        os.chown(target, 0, 0)
        os.chmod(target, 0o644)
        row["activated"] = True
        save_state(state)
    state["target_runtime_activated"] = True
    save_state(state)


def deactivate_target_runtime(state: dict[str, Any]) -> bool:
    ok = True
    for row in state.get("pending_system_cron", []):
        if row.get("activated"):
            try:
                Path(str(row["source_path"])).unlink(missing_ok=True)
                row["activated"] = False
                save_state(state)
            except OSError:
                ok = False
    for row in state.get("pending_user_cron", []):
        if row.get("activated"):
            proc = run_local(
                ["crontab", "-u", str(row["user"]), "-r"],
                timeout=30,
                check=False,
            )
            if proc.returncode in (0, 1):
                row["activated"] = False
                save_state(state)
            else:
                ok = False
    for row in state.get("pending_pm2", []):
        if not row.get("activated"):
            continue
        try:
            result = legacy.target_stop_pm2_local(
                str(row["user"]),
                Path(str(row["staged_target"])),
            )
        except legacy.ServerMigrationError:
            ok = False
        else:
            if result.get("status") == "PM2_STOPPED":
                row["activated"] = False
                save_state(state)
            else:
                ok = False
    state["target_runtime_activated"] = any(
        row.get("activated")
        for key in ("pending_system_cron", "pending_user_cron", "pending_pm2")
        for row in state.get(key, [])
        if isinstance(row, dict)
    )
    save_state(state)
    return ok


def php_fpm_listener_for_domain(domain: str) -> int | None:
    if not domain or "/" in domain:
        return None
    directory = Path("/etc/nginx/sites-enabled")
    if not directory.is_dir():
        return None
    for path in sorted(directory.glob("*.conf")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        names: list[str] = []
        for match in re.finditer(r"(?m)^\s*server_name\s+([^;]+);", text):
            names.extend(
                item
                for item in re.split(r"\s+", match.group(1).strip())
                if item and item != "_"
            )
        if domain not in names:
            continue
        match = re.search(
            r"fastcgi_pass\s+(?:127\.0\.0\.1|localhost):([0-9]+)",
            text,
            re.I,
        )
        if not match:
            return None
        port = int(match.group(1))
        return port if 1 <= port <= 65535 else None
    return None


def tcp_listener_ready(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=1.0):
            return True
    except (OSError, ValueError):
        return False


def reconcile_php_fpm_backend(site: dict[str, Any]) -> dict[str, Any]:
    runtime = site.get("runtime") if isinstance(site.get("runtime"), dict) else {}
    runtime_type = str(runtime.get("type", "")).lower().replace("-", "_")
    if runtime_type != "php":
        return {"status": "NOT_APPLICABLE"}

    version = str(runtime.get("version", "")).strip()
    parts = version.split(".")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return {"status": "FAIL", "reason": "PHP_VERSION_INVALID"}

    domain = str(site.get("domain", ""))
    service = f"php{version}-fpm"
    active = run_local(
        ["systemctl", "is-active", service],
        timeout=20,
        check=False,
    )
    if active.returncode != 0:
        progress_note(
            f"7/7 · {domain} PHP-FPM 未运行，正在启动 {service}"
        )
        started = run_local(
            ["systemctl", "start", service],
            timeout=60,
            check=False,
        )
        if started.returncode != 0:
            return {
                "status": "FAIL",
                "reason": "PHP_FPM_SERVICE_START_FAILED",
                "service": service,
            }

    port = php_fpm_listener_for_domain(domain)
    if port is None:
        return {
            "status": "FAIL",
            "reason": "PHP_FPM_LISTENER_UNKNOWN",
            "service": service,
        }

    if tcp_listener_ready(port):
        return {
            "status": "READY",
            "service": service,
            "listener_port": port,
            "action": "STARTED" if active.returncode != 0 else "NONE",
        }

    progress_note(
        f"7/7 · {domain} PHP-FPM 监听未就绪，正在安全 reload {service}"
    )
    reloaded = run_local(
        ["systemctl", "reload", service],
        timeout=60,
        check=False,
    )
    if reloaded.returncode != 0:
        return {
            "status": "FAIL",
            "reason": "PHP_FPM_RELOAD_FAILED",
            "service": service,
            "listener_port": port,
        }

    time.sleep(1.0)
    if not tcp_listener_ready(port):
        return {
            "status": "FAIL",
            "reason": "PHP_FPM_LISTENER_MISSING",
            "service": service,
            "listener_port": port,
        }
    return {
        "status": "READY",
        "service": service,
        "listener_port": port,
        "action": "RELOADED",
    }



def http_baseline_compatible(source_code: str, target_code: str) -> bool:
    source_family = _http_status_family(source_code)
    target_family = _http_status_family(target_code)
    if source_family == "SUCCESS_OR_REDIRECT":
        return target_family == "SUCCESS_OR_REDIRECT"
    if source_family == "CLIENT_ERROR":
        return target_family == "CLIENT_ERROR" and source_code == target_code
    return False


def target_smoke(
    state: dict[str, Any],
    *,
    attempts: int = 10,
    delay: float = 3.0,
) -> dict[str, Any]:
    manifest = inventory.build_manifest(Path("/"))
    site_map = {
        str(row.get("domain")): row
        for row in manifest.get("sites", [])
        if isinstance(row, dict)
    }
    passed = failed = 0
    failures: list[dict[str, Any]] = []
    max_attempts = max(1, int(attempts))
    retry_delay = max(0.0, float(delay))
    for source_site in state["sites"]:
        domain = str(source_site["domain"])
        target_site = site_map.get(domain)
        if not target_site:
            failed += 1
            failures.append({"domain": domain, "reason": "SITE_MISSING"})
            continue
        compare = cutover.compare_site(source_site, target_site, domain)
        compare["failures"] = [
            item for item in compare.get("failures", [])
            if item != "ssl.configured"
        ]
        compare["unknowns"] = [
            item for item in compare.get("unknowns", [])
            if item != "ssl.configured"
        ]
        if compare["failures"] or compare["unknowns"]:
            failed += 1
            failures.append({
                "domain": domain,
                "reason": "INVENTORY_MISMATCH",
                "fields": sorted(set(compare["failures"] + compare["unknowns"])),
            })
            continue

        last_code = "000"
        last_exit = 0
        ready = False
        used_attempts = 0
        backend: dict[str, Any] = {"status": "NOT_CHECKED"}
        backend_checked = False
        baseline_failure: dict[str, Any] | None = None
        for probe_attempt in range(1, max_attempts + 1):
            used_attempts = probe_attempt
            progress_note(
                f"7/7 · 本地验证 {domain} · 第 {probe_attempt}/{max_attempts} 次"
            )
            proc = run_local([
                "curl", "-kSs", "--connect-timeout", "10", "--max-time", "30",
                "--resolve", f"{domain}:443:127.0.0.1",
                "-o", "/dev/null", "-w", "%{http_code}",
                f"https://{domain}/",
            ], timeout=45, check=False)
            code = proc.stdout.strip()[-3:]
            last_code = code if code.isdigit() else "000"
            last_exit = int(proc.returncode)
            if (
                proc.returncode == 0
                and last_code.isdigit()
                and 200 <= int(last_code) < 500
            ):
                baseline_map = (
                    state.get("source_http_baseline")
                    if isinstance(state.get("source_http_baseline"), dict)
                    else {}
                )
                baseline_row = baseline_map.get(domain)
                if (
                    isinstance(baseline_row, dict)
                    and baseline_row.get("status") == "PASS"
                    and not http_baseline_compatible(
                        str(baseline_row.get("http_code") or "000"),
                        last_code,
                    )
                ):
                    baseline_failure = {
                        "source_http_code": str(
                            baseline_row.get("http_code") or "000"
                        ),
                        "source_http_family": str(
                            baseline_row.get("family") or "UNKNOWN"
                        ),
                    }
                    break
                ready = True
                break

            runtime = (
                source_site.get("runtime")
                if isinstance(source_site.get("runtime"), dict)
                else {}
            )
            runtime_type = str(runtime.get("type", "")).lower().replace("-", "_")
            if not backend_checked and runtime_type == "php":
                backend_checked = True
                backend = reconcile_php_fpm_backend(source_site)
                if backend.get("status") == "FAIL":
                    break

            if probe_attempt < max_attempts:
                progress_note(
                    f"7/7 · {domain} 暂未就绪（HTTP {last_code}），"
                    f"{retry_delay:g} 秒后重试"
                )
                time.sleep(retry_delay)

        if ready:
            passed += 1
        else:
            failed += 1
            reason = (
                "HTTP_BASELINE_REGRESSION"
                if baseline_failure is not None
                else (
                    str(backend.get("reason"))
                    if backend.get("status") == "FAIL"
                    else "LOCAL_HTTP_PROBE"
                )
            )
            row: dict[str, Any] = {
                "domain": domain,
                "reason": reason,
                "http_code": last_code,
                "curl_exit": last_exit,
                "attempts": used_attempts,
            }
            if baseline_failure is not None:
                row["source_http_baseline"] = baseline_failure
            if backend.get("status") != "NOT_CHECKED":
                row["backend"] = {
                    key: value
                    for key, value in backend.items()
                    if key in {
                        "status", "reason", "service",
                        "listener_port", "action",
                    }
                }
            failures.append(row)
    return {"pass": passed, "fail": failed, "failures": failures}


def create_public_markers(state: dict[str, Any], token: str) -> list[tuple[str, Path]]:
    manifest = inventory.build_manifest(Path("/"))
    rows: list[tuple[str, Path]] = []
    for site in state["sites"]:
        domain = str(site["domain"])
        target = cutover.find_site(manifest, domain)
        docroot = str(target.get("document_root", ""))
        if not docroot.startswith("/home/"):
            docroot = str(target.get("site_root", ""))
        if not docroot.startswith("/home/"):
            raise PullMigrationError(f"unsafe new-server document root: {domain}")
        marker = Path(docroot) / f".vfops-cutover-proof-{token}.txt"
        marker.write_text(token + "\n", encoding="utf-8")
        os.chmod(marker, 0o644)
        rows.append((domain, marker))
    return rows


def public_route_proof(
    state: dict[str, Any],
    *,
    attempts: int,
    delay: float,
) -> dict[str, Any]:
    token = hashlib.sha256(
        f"{state['migration_id']}:{time.time_ns()}".encode()
    ).hexdigest()[:24]
    mapping = create_public_markers(state, token)
    pending = {domain for domain, _ in mapping}
    try:
        for _ in range(max(1, attempts)):
            for domain in list(pending):
                proc = run_local([
                    "curl", "-kLsS", "--connect-timeout", "10", "--max-time", "30",
                    "-H", "Cache-Control: no-cache, no-store",
                    f"https://{domain}/.vfops-cutover-proof-{token}.txt?t={token}",
                ], timeout=45, check=False)
                if proc.returncode == 0 and proc.stdout.strip() == token:
                    pending.remove(domain)
            if not pending:
                break
            time.sleep(max(0.0, delay))
        return {
            "status": "PASS" if not pending else "WAITING_DNS",
            "pass": len(mapping) - len(pending),
            "fail": len(pending),
            "pending": sorted(pending),
        }
    finally:
        for _, path in mapping:
            path.unlink(missing_ok=True)


def production_verify(state: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    sites: list[dict[str, Any]] = []
    baseline_map = (
        state.get("source_http_baseline")
        if isinstance(state.get("source_http_baseline"), dict)
        else {}
    )
    for site in state["sites"]:
        domain = str(site["domain"])
        proc = run_local([
            "curl", "-sS", "--connect-timeout", "10", "--max-time", "30",
            "-o", "/dev/null", "-w", "%{http_code}|%{ssl_verify_result}|%{remote_ip}",
            f"https://{domain}/",
        ], timeout=45, check=False)
        parts = proc.stdout.strip().split("|", 2)
        code = parts[0] if parts else "000"
        tls = parts[1] if len(parts) > 1 else "999"
        remote_ip = parts[2] if len(parts) > 2 else ""
        baseline_row = baseline_map.get(domain)
        if isinstance(baseline_row, dict) and baseline_row.get("status") == "PASS":
            behavior_ok = http_baseline_compatible(
                str(baseline_row.get("http_code") or "000"),
                code,
            )
            source_code = str(baseline_row.get("http_code") or "000")
        else:
            behavior_ok = code.isdigit() and 200 <= int(code) < 400
            source_code = None
        ok = (
            proc.returncode == 0
            and behavior_ok
            and tls == "0"
        )
        sites.append({
            "domain": domain,
            "http_code": code,
            "source_http_code": source_code,
            "baseline_compatible": behavior_ok,
            "tls_verify": tls,
            "remote_ip": remote_ip,
            "status": "PASS" if ok else "FAIL",
        })
        if not ok:
            failed.append(domain)
    source_nginx = source_remote(
        state["source"],
        "systemctl is-active nginx >/dev/null 2>&1",
        timeout=30,
        check=False,
    )
    if source_nginx.returncode == 0:
        failed.append("OLD_SERVER_NGINX_STILL_ACTIVE")
    return {
        "status": "PASS" if not failed else "FAIL",
        "sites": sites,
        "old_server_runtime_frozen": source_nginx.returncode != 0,
        "failures": failed,
    }


def plan_payload(
    source: dict[str, Any], domains: list[str], confirm_source_staging: str = ""
) -> dict[str, Any]:
    # A complete source inventory currently requires a short-lived helper on
    # the old server. Do not disguise that filesystem write as a dry run.
    if confirm_source_staging != "ALLOW_SOURCE_HELPER_STAGING":
        raise PullMigrationError(
            "source helper staging requires --confirm-source-helper-staging "
            "ALLOW_SOURCE_HELPER_STAGING before migration plan"
        )
    source_plan = source_probe(source, domains)
    target = target_preflight_local(source_plan)
    return {
        "schema": SCHEMA,
        "operation": "PLAN",
        "status": "READY",
        "migration_direction": "CURRENT_SERVER_PULLS_OLD_SERVER",
        "current_server_role": "RECEIVER",
        "old_server_ip": source["ip"],
        "source_server_identity": source_plan.get("source_server_identity"),
        "target_server_identity": target.get("target_identity"),
        "site_count": len(source_plan.get("sites", [])),
        "sites": source_plan.get("sites", []),
        "capacity_estimate": source_plan.get("capacity_estimate"),
        "old_server_external_listeners": source_plan.get("source_external_listeners", []),
        "dns_manual_gate_required": True,
        "automatic_dns_change": False,
        "old_server_delete_allowed": False,
        "existing_target_overwrite_allowed": False,
        # PLAN stages and removes a temporary helper on the old host.
        # This is not a purely read-only operation, even if cleanup succeeds.
        "writes_performed": True,
        "source_temporary_helper_written": True,
        "source_helper_cleanup_attempted": True,
        "source_business_data_written": False,
        "secrets_emitted": False,
    }


def require_remainder_exact_source_scope(
    expected: list[dict[str, Any]] | None,
    fresh: Any,
    domains: list[str],
) -> None:
    """Refuse a fresh source inventory drift before target preflight or writes.

    A failed parent may have already populated target DBs. A new sibling staging
    job must not silently change site user, database ownership, document root,
    runtime or the candidate list while claiming to stage untouched suffix.
    Never echo any private source values in error messages.
    """
    if (not isinstance(expected, list) or not expected
            or not isinstance(fresh, list)
            or len(expected) != len(domains) or len(fresh) != len(domains)
            or not isinstance(domains, list) or not domains):
        raise PullMigrationError("REMAINDER_SOURCE_SCOPE_UNPROVEN")
    unique: set[str] = set()
    for prior, current, name in zip(expected, fresh, domains):
        if not isinstance(prior, dict) or not isinstance(current, dict):
            raise PullMigrationError("REMAINDER_SOURCE_SCOPE_UNPROVEN")
        if (type(name) is not str or not name or name.lower() in unique
                or prior.get("domain") != name or current.get("domain") != name):
            raise PullMigrationError("REMAINDER_SOURCE_SCOPE_CHANGED")
        unique.add(name.lower())
        if (_site_structure_fingerprint(prior)
                != _site_structure_fingerprint(current)):
            raise PullMigrationError("REMAINDER_SOURCE_SITE_STRUCTURE_CHANGED")


def prepare_migration(
    source: dict[str, Any],
    domains: list[str],
    confirm: str,
    *,
    remainder_parent: str | None = None,
    expected_source_identity: str | None = None,
    expected_remainder_sites: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if confirm != "PREPARE_PULL_MIGRATION":
        raise PullMigrationError("explicit confirmation required: PREPARE_PULL_MIGRATION")
    source_plan = source_probe(source, domains)
    source_identity = str(source_plan.get("source_server_identity", "UNKNOWN"))
    if expected_source_identity is not None and source_identity != expected_source_identity:
        raise PullMigrationError("REMAINDER_SOURCE_SERVER_CHANGED")
    if remainder_parent is not None:
        require_remainder_exact_source_scope(
            expected_remainder_sites, source_plan.get("sites"), domains
        )
    elif expected_remainder_sites is not None:
        raise PullMigrationError("REMAINDER_SCOPE_WITHOUT_PARENT_REFUSED")
    target = target_preflight_local(source_plan)
    mid = migration_id(source_identity, str(target["target_identity"]))
    root = state_dir(mid)
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    runtime = stage_source_runtime(source, mid)
    source_rsync = ensure_old_server_rsync(source)
    state: dict[str, Any] = {
        "schema": SCHEMA,
        "migration_id": mid,
        "status": "PREPARING",
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "direction": "TARGET_PULL",
        "current_server_role": "RECEIVER",
        "source": source,
        "source_server_identity": source_identity,
        "target_server_identity": target["target_identity"],
        "source_runtime_path": runtime,
        "source_rsync": source_rsync,
        "sites": source_plan.get("sites", []),
        "external_assets": source_plan.get("external_assets", []),
        "sqlite_assets": source_plan.get("sqlite_assets", []),
        "runtime_assets": source_plan.get("runtime_assets", {}),
        "source_external_listeners": source_plan.get("source_external_listeners", []),
        "source_runtime_frozen": False,
        "target_runtime_activated": False,
        "dns_changed_by_p07": False,
        "source_delete_allowed": False,
        "existing_target_overwrite_allowed": False,
        "partial_parent_migration_id": remainder_parent,
        "cutover_prohibited": bool(remainder_parent),
        "secrets_emitted": False,
    }
    for site in state["sites"]:
        site["stage_status"] = "PENDING"
    save_state(state)
    return resume_prepare_migration(mid)


def prepare_chain_tail(parent_mid: str, child_mid: str, confirm: str) -> dict[str, Any]:
    """Stage only never-created suffix sites under a separate blocked-cutover job.

    Strict provenance and target identity checks run before any source probing.
    No parent/child SQL guard or stage_status is altered. Existing sites/DBs
    continue to be rejected by the normal target preflight. Any new tail job
    remains independently cutover-prohibited; no 17-site promotion is implied.
    """
    if confirm != f"STAGE_CHAIN_TAIL:{parent_mid}:{child_mid}":
        raise PullMigrationError("CHAIN_TAIL_EXPLICIT_CONFIRMATION_REQUIRED")
    parent = load_state(parent_mid)
    child = load_state(child_mid)
    try:
        plan = migration_chain_recovery.select(parent, child)
    except migration_chain_recovery.ChainRecoveryBlocked as exc:
        raise PullMigrationError(str(exc)) from None
    if target_identity() != parent["target_server_identity"]:
        raise PullMigrationError("CHAIN_TAIL_LOCAL_TARGET_IDENTITY_CHANGED")
    domains = plan["uncreated_candidate_domains"]
    if not domains or any(
        item.get("stage_status") != "PENDING"
        for item in parent["sites"][-len(domains):]
    ):
        raise PullMigrationError("CHAIN_TAIL_NOT_UNTOUCHED")
    return prepare_migration(
        parent["source"], domains, "PREPARE_PULL_MIGRATION",
        remainder_parent=parent_mid,
        expected_source_identity=str(parent["source_server_identity"]),
        expected_remainder_sites=[
            dict(row) for row in parent["sites"][-len(domains):]
        ],
    )


def _private_marker_readback(path: Path, fields: dict[str, str]) -> dict[str, Any]:
    """Verify exact already-owned private marker without creating a new one."""
    try:
        metadata = path.lstat()
    except OSError:
        raise PullMigrationError("ADOPT_TARGET_OWNERSHIP_MARKER_MISSING") from None
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0
            or metadata.st_mode & 0o077):
        raise PullMigrationError("ADOPT_TARGET_OWNERSHIP_MARKER_UNSAFE")
    try:
        payload = legacy.read_target_ownership_marker(path, fields)
    except legacy.ServerMigrationError:
        raise PullMigrationError("ADOPT_TARGET_OWNERSHIP_UNVERIFIED") from None
    if not isinstance(payload, dict):
        raise PullMigrationError("ADOPT_TARGET_OWNERSHIP_UNVERIFIED")
    return payload


def _owned_pending_database_readback(state: dict[str, Any], domain: str) -> dict[str, Any]:
    """Read three SQL exports, never open an import or modify existing DB."""
    try:
        database = migration_db_adoption.selected_db(state, domain)
    except migration_db_adoption.AdoptBlocked as exc:
        raise PullMigrationError(str(exc)) from None
    mid = str(state["migration_id"])
    row = next(x for x in state["sites"] if x.get("domain") == domain)
    target_root = state_dir(mid) / "target-transactions"
    site_token = hashlib.sha256(domain.encode("ascii")).hexdigest()[:16]
    db_token = hashlib.sha256(f"{domain}:{database}:1".encode()).hexdigest()[:16]
    _private_marker_readback(target_root / f"site-{site_token}.json", {
        "domain": domain, "created_by_migration": mid,
    })
    ownership = _private_marker_readback(target_root / f"db-{db_token}.json", {
        "domain": domain, "database": database, "created_by_migration": mid,
    })
    if (not isinstance(ownership.get("username"), str)
            or not ownership.get("username")
            or not isinstance(ownership.get("password"), str)
            or not ownership.get("password")):
        raise PullMigrationError("ADOPT_DB_OWNERSHIP_CREDENTIALS_UNVERIFIED")
    site_root = Path(str(row.get("site_root") or ""))
    if not site_root.is_dir() or site_root.is_symlink():
        raise PullMigrationError("ADOPT_TARGET_SITE_ROOT_MISSING")
    if not app_config.verify_rewritten_application_database_config(
        site_root, database, ownership["username"], ownership["password"]
    ):
        raise PullMigrationError("ADOPT_TARGET_APPLICATION_DB_CONFIG_UNVERIFIED")
    try:
        mismatches = legacy.verify_target_site_creation(row)
    except legacy.ServerMigrationError:
        raise PullMigrationError("ADOPT_TARGET_SITE_CONFIG_UNVERIFIED") from None
    if mismatches:
        raise PullMigrationError("ADOPT_TARGET_SITE_CONFIG_DRIFT")
    if not state.get("source_runtime_path") or not state.get("source"):
        raise PullMigrationError("ADOPT_SOURCE_HELPER_UNAVAILABLE")

    with tempfile.TemporaryDirectory(prefix="vfops-adopt-readback-") as location:
        directory = Path(location)
        os.chmod(directory, 0o700)
        first = directory / "first.sql.gz"
        reread = directory / "reread.sql.gz"
        target = directory / "target.sql.gz"
        remote_paths: list[str] = []
        try:
            for local in (first,):
                name = f"{remote_staging_root(state)}/adopt-{os.urandom(16).hex()}.sql.gz"
                remote_paths.append(name)
                source_export_database(state, database, name)
                pull_path(state["source"], name, local)
                try:
                    sql_diff_probe.require_nonempty_source_schema(local)
                except sql_diff_probe.AdvisoryDiagnosticUnavailable:
                    raise PullMigrationError("ADOPT_SOURCE_SQL_SCHEMA_UNVERIFIED") from None
            try:
                cloudpanel.export_database(database, target, clpctl="clpctl")
            except (cloudpanel.CloudPanelError, ValueError):
                raise PullMigrationError("ADOPT_TARGET_SQL_EXPORT_FAILED") from None
            name = f"{remote_staging_root(state)}/adopt-{os.urandom(16).hex()}.sql.gz"
            remote_paths.append(name)
            source_export_database(state, database, name)
            pull_path(state["source"], name, reread)
            try:
                sql_diff_probe.require_nonempty_source_schema(reread)
            except sql_diff_probe.AdvisoryDiagnosticUnavailable:
                raise PullMigrationError("ADOPT_SOURCE_SQL_SCHEMA_UNVERIFIED") from None
            try:
                mode = compare_database_dumps(first, target)
                readback_mode = compare_database_dumps(first, reread)
                first_fingerprint, first_statements = verify_engine.sql_fingerprint(first)
                reread_fingerprint, reread_statements = verify_engine.sql_fingerprint(reread)
            except verify_engine.RestoreVerifyError:
                raise PullMigrationError("ADOPT_SOURCE_SQL_FINGERPRINT_UNAVAILABLE") from None
            if (first_fingerprint != reread_fingerprint
                    or first_statements != reread_statements):
                raise PullMigrationError("ADOPT_SOURCE_CHANGED_BETWEEN_READS")
            def digest(p: Path) -> str:
                value = hashlib.sha256()
                with p.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        value.update(block)
                return value.hexdigest()
            return {
                "domain": domain, "migration_id": mid, "database": database,
                "comparison_mode": mode, "source_readback_mode": readback_mode,
                "source_dump_sha256": digest(first),
                "source_readback_sha256": digest(reread),
                "target_dump_sha256": digest(target),
                "source_snapshot_fingerprint": first_fingerprint,
                "readback_snapshot_fingerprint": reread_fingerprint,
            }
        finally:
            for path in remote_paths:
                source_remote(
                    state["source"],
                    f"rm -f -- {shlex.quote(path)}",
                    timeout=60, check=False,
                )


def adopt_existing_guarded_site(mid: str, domain: str, confirm: str) -> dict[str, Any]:
    """Recover exactly ONE imported, marked, failed site without re-importing.

    A failed first-site checkpoint cannot prevent recovering the second site:
    each existing migration state updates atomically and independently. The
    parent/child stay PREPARE_FAILED, and the old SQL guard is retained. Never
    changes runtime activation, source freeze or DNS.
    """
    if confirm != f"ADOPT_EXISTING_DB:{mid}:{domain}":
        raise PullMigrationError("ADOPT_EXPLICIT_OWNER_CONFIRMATION_REQUIRED")
    if not SAFE_ID_RE.fullmatch(mid):
        raise PullMigrationError("ADOPT_MIGRATION_ID_INVALID")
    # Record lock prevents two owner recovery commands racing on this state.
    # This also closes TOCTOU between readback and the atomic state write.
    lock_path = state_dir(mid) / ".database-adoption.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError:
        raise PullMigrationError("ADOPT_PRIVATE_LOCK_UNAVAILABLE") from None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = load_state(mid)
        if (state.get("status") != "PREPARE_FAILED"
                or not isinstance(state.get("last_sql_guard_failure"), dict)
                or state["last_sql_guard_failure"].get("reason") != "CONDITIONAL_DDL"):
            raise PullMigrationError("ADOPT_ORIGINAL_FAILED_GUARD_REQUIRED")
        selected = [x for x in state.get("sites", [])
                    if isinstance(x, dict) and x.get("domain") == domain]
        if len(selected) != 1:
            raise PullMigrationError("ADOPT_SITE_NOT_IN_MIGRATION")
        if selected[0].get("stage_status") == "PULLED_STAGED":
            # Idempotent checkpoint: do not repeat source exports, imports
            # or state writes. Original guard remains recorded.
            checkpoint = selected[0].get("database_adoption")
            if isinstance(checkpoint, dict) and (
                checkpoint.get("schema") == "P07_EXISTING_DB_ADOPTION_CHECKPOINT_V1"
                and checkpoint.get("status") == "SOURCE_TARGET_PREPARE_READBACK_PASS"
                and checkpoint.get("db_reimported") is False
                and checkpoint.get("cutover_allowed") is False
            ):
                return {
                    "status": "ALREADY_ADOPTED_FIRST_STAGE",
                    "migration_id": mid, "domain": domain,
                    "cutover_allowed": False, "database_writes_performed": False,
                }
            raise PullMigrationError("ADOPT_SITE_ALREADY_STAGED_WITHOUT_PROOF")
        try:
            migration_db_adoption.selected_db(state, domain)
        except migration_db_adoption.AdoptBlocked as exc:
            raise PullMigrationError(str(exc)) from None
        if target_identity() != state.get("target_server_identity"):
            raise PullMigrationError("ADOPT_LOCAL_TARGET_IDENTITY_CHANGED")
        # Check the same source identity and exact site configuration, not
        # merely an address or an old transcript's source IP.
        plan = source_probe(state["source"], [domain])
        fresh = [row for row in plan.get("sites", [])
                 if isinstance(row, dict) and row.get("domain") == domain]
        if (plan.get("source_server_identity") != state.get("source_server_identity")
                or len(fresh) != 1
                or _site_structure_fingerprint(fresh[0])
                   != _site_structure_fingerprint(selected[0])):
            raise PullMigrationError("ADOPT_OLD_SERVER_IDENTITY_OR_SITE_DRIFT")
        before_state_hash = hashlib.sha256(state_path(mid).read_bytes()).hexdigest()
        proof = _owned_pending_database_readback(state, domain)
        # Detect a non-cooperating migration process or admin editing state
        # while source/target SQL exports were being compared.
        if hashlib.sha256(state_path(mid).read_bytes()).hexdigest() != before_state_hash:
            raise PullMigrationError("ADOPT_MIGRATION_STATE_CHANGED_DURING_EXPORT")
        try:
            updated = migration_db_adoption.stage_existing_verified_site(state, domain, proof)
        except migration_db_adoption.AdoptBlocked as exc:
            raise PullMigrationError(str(exc)) from None
        # Never erase SQL failure history; a first-stage readback does not
        # release either a parent or a partial child for cutover.
        if (updated.get("status") != "PREPARE_FAILED"
                or updated.get("last_sql_guard_failure") != state.get("last_sql_guard_failure")):
            raise PullMigrationError("ADOPT_ORIGINAL_GUARD_LOST")
        save_state(updated)
        return {
            "status": "FIRST_STAGE_ADOPTED_REQUIRES_CHAIN_RECOVERY",
            "migration_id": mid, "domain": domain,
            "cutover_allowed": False, "database_writes_performed": False,
            "source_frozen": False, "site_stage_status": "PULLED_STAGED",
        }
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def chain_adopt_database_proof(parent_mid: str, child_mid: str) -> dict[str, Any]:
    """Two prior imports, both checked; NO state change, DB import or cutover."""
    parent, child = load_state(parent_mid), load_state(child_mid)
    try:
        scope = migration_chain_recovery.select(parent, child)
    except migration_chain_recovery.ChainRecoveryBlocked as exc:
        raise PullMigrationError(str(exc)) from None
    if target_identity() != parent.get("target_server_identity"):
        raise PullMigrationError("ADOPT_LOCAL_TARGET_IDENTITY_CHANGED")
    # Refuse to probe either DB unless BOTH states match the exact unsafe
    # parent-child chain and both pending sites are single-DB bindings.
    for state, domain in zip((parent, child), scope["blocked_sites"]):
        try:
            migration_db_adoption.selected_db(state, domain)
        except migration_db_adoption.AdoptBlocked as exc:
            raise PullMigrationError(str(exc)) from None
    proof = [
        _owned_pending_database_readback(parent, scope["blocked_sites"][0]),
        _owned_pending_database_readback(child, scope["blocked_sites"][1]),
    ]
    try:
        receipt = migration_db_adoption.sealed_receipt(proof)
    except migration_db_adoption.AdoptBlocked as exc:
        raise PullMigrationError(str(exc)) from None
    receipt["parent_migration_id"] = parent_mid
    receipt["child_migration_id"] = child_mid
    return receipt


def diagnose_chain_sql(parent_mid: str, child_mid: str) -> dict[str, Any]:
    """One opt-in advisory read/export of the two already-failed DBs.

    Enforce both states and host identity before any network call. Never infer
    that a matching row fingerprint proves conditional DDL equivalence.
    There is no migration state write, data import, cleanup of an existing
    target, or permission to resume or cut over.
    """
    parent = load_state(parent_mid)
    child = load_state(child_mid)
    try:
        scope = migration_chain_recovery.select(parent, child)
    except migration_chain_recovery.ChainRecoveryBlocked as exc:
        raise PullMigrationError(str(exc)) from None
    if target_identity() != parent.get("target_server_identity"):
        raise PullMigrationError("CHAIN_SQL_LOCAL_TARGET_IDENTITY_CHANGED")
    exact = (
        (parent, parent_mid, scope["blocked_sites"][0]),
        (child, child_mid, scope["blocked_sites"][1]),
    )
    for state, _, domain in exact:
        rows = [
            entry for entry in state["sites"]
            if entry.get("domain") == domain
        ]
        if (len(rows) != 1 or rows[0].get("stage_status") != "PENDING"
                or not isinstance(rows[0].get("mysql_databases"), list)
                or len(rows[0]["mysql_databases"]) != 1):
            raise PullMigrationError("CHAIN_SQL_GUARDED_DB_BINDING_UNVERIFIED")
    results = []
    for _, mid, domain in exact:
        evidence = diagnose_sql_difference(mid, domain)
        # Returned diagnostics are advisory-only; limit output to fixed,
        # code-owned aggregate categories rather than SQL or raw values.
        info = evidence.get("evidence")
        if (evidence.get("status") != "ADVISORY_DIAGNOSTIC_ONLY"
                or not isinstance(info, dict)):
            raise PullMigrationError("CHAIN_SQL_ADVISORY_EVIDENCE_INVALID")
        # Only fixed key names with bounded aggregate counts may leave
        # this command. Raw SQL/literals/identifiers never enter stdout.
        def picked_counts(blob: Any, keys: tuple[str, ...]) -> dict[str, int]:
            if blob is None:
                return {}
            if not isinstance(blob, dict):
                raise PullMigrationError("CHAIN_SQL_COUNTERS_UNVERIFIED")
            output = {}
            for key in keys:
                value = blob.get(key)
                if value is not None:
                    if type(value) is not int or not 0 <= value <= 100000000:
                        raise PullMigrationError("CHAIN_SQL_COUNTERS_UNVERIFIED")
                    output[key] = value
            return output

        guard = picked_counts(info.get("dynamic_guard"), (
            "recognized_safe", "recognized_unsafe", "double_quoted_if",
            "other_unknown_set", "unsafe_yes_branches", "unsafe_no_branches",
            "unsafe_control_or_multi",
        ))
        schema = picked_counts(info.get("schema_difference"), (
            "source_tables", "target_tables", "common_tables",
            "source_only_tables", "target_only_tables", "mismatched_tables",
            "changed_columns", "changed_indexes", "changed_options",
            "unclassified_tables", "other_schema_source_only",
            "other_schema_target_only",
        ))
        readback = info.get("source_export_readback", {})
        if not isinstance(readback, dict):
            raise PullMigrationError("CHAIN_SQL_READBACK_UNVERIFIED")
        verification = info.get("verification", "UNAVAILABLE")
        if verification not in {
            "NOT_A_PASS_GATE", "UNAVAILABLE", "SOURCE_EXPORT_UNUSABLE",
            "SOURCE_TABLE_COUNT_MISMATCH",
        }:
            verification = "UNAVAILABLE"
        guarded = info.get("guarded_export_comparison", {})
        if not isinstance(guarded, dict):
            raise PullMigrationError("CHAIN_SQL_GUARDED_EXPORT_VERDICT_INVALID")
        safe_status = guarded.get("status", "UNAVAILABLE")
        if safe_status not in {
            "BLOCKED", "MATCH_ADVISORY_NOT_MIGRATION_PASS", "UNAVAILABLE",
        }:
            safe_status = "UNAVAILABLE"
        guarded_reason = guarded.get("reason")
        if guarded_reason not in {
            "CONDITIONAL_DDL", "SCHEMA_OR_DATA_UNPROVEN",
            "UNKNOWN_COMPARISON_MODE", None,
        }:
            guarded_reason = "UNAVAILABLE"
        results.append({
            "domain": domain,
            "migration_id": mid,
            "guarded_export_comparison": {
                "status": safe_status,
                "reason": guarded_reason,
                "cutover_allowed": False,
            },
            "verification": verification,
            "source_export_readback": picked_counts(
                readback, ("attempts", "source_tables", "expected_source_tables")
            ),
            "dynamic_guard_counts": guard,
            "schema_difference_counts": schema,
            "database_writes_performed": False,
            "migration_state_writes_performed": False,
        })
    return {
        "schema": "P07_CHAIN_SQL_ADVISORY_V1",
        "status": "ADVISORY_ONLY",
        "source_target_snapshot_atomic": False,
        "conditional_ddl_semantics_verified": False,
        "database_writes_performed": False,
        "migration_state_writes_performed": False,
        "cutover_allowed": False,
        "sites": results,
    }


def chain_recovery_scope(parent_mid: str, child_mid: str) -> dict[str, Any]:
    """Only return cross-task evidence; keep all live assets and state intact."""
    try:
        return migration_chain_recovery.select(
            load_state(parent_mid), load_state(child_mid)
        )
    except migration_chain_recovery.ChainRecoveryBlocked as exc:
        raise PullMigrationError(str(exc)) from None


def consolidated_chain_scope(
    parent_mid: str, child_mid: str, tail_mid: str, *,
    verify_target_markers: bool = False,
    locked_candidate_id: str | None = None,
) -> dict[str, Any]:
    """Read-only three-task reconciliation or sealed, nonexecutable candidate."""
    try:
        parent, child, tail = (
            load_state(parent_mid), load_state(child_mid), load_state(tail_mid)
        )
        if locked_candidate_id is not None:
            if not verify_target_markers:
                raise PullMigrationError("CONSOLIDATED_EXECUTION_LOCAL_PROOF_REQUIRED")
            return migration_chain_consolidation.build_locked_execution_candidate(
                parent, child, tail,
                proposed_migration_id=locked_candidate_id,
                local_target_identity=target_identity(),
            )
        if verify_target_markers:
            return migration_chain_consolidation.local_target_marker_proof(
                parent, child, tail, local_target_identity=target_identity()
            )
        return migration_chain_consolidation.consolidate(parent, child, tail)
    except migration_chain_consolidation.ConsolidationBlocked as exc:
        raise PullMigrationError(str(exc)) from None


def chain_execution_scope(parent_mid: str, child_mid: str,
                          tail_mid: str) -> dict[str, Any]:
    """No-write 17-site owner and connected-www3 recovery view.

    This is deliberately separate from cutover_migration: an existing
    three-task incident cannot impersonate a single PREPARED target-pull.
    """
    try:
        parent, child, tail = (
            load_state(parent_mid), load_state(child_mid), load_state(tail_mid)
        )
        if target_identity() != parent.get("target_server_identity"):
            raise PullMigrationError("CHAIN_EXECUTION_LOCAL_TARGET_IDENTITY_CHANGED")
        result = migration_chain_execution_scope.scope(parent, child, tail)
        # Attach the exact OWNER-approved final window to the existing
        # original-owner CLI output. This is a locked scope only, never a
        # source-side pause or a permission to run legacy all-sites freeze.
        result["owner_final_window"] = (
            migration_three_site_window.owner_window_scope(
                result["final_sync_plan"],
                migration_three_site_window.OWNER_SITES,
                # OWNER explicitly approved a brief outage for all 17 sites.
                # Approval does NOT satisfy source freeze, shadow or rollback.
                whole_server_outage_approved=True,
            )
        )
        # Reconcile the three original owners' Cron/PM2 source controls once,
        # not once per partial migration. The full private control is never
        # printed by this read-only CLI and cannot activate any source stop.
        try:
            control = migration_three_site_window.assemble_seventeen_site_source_maintenance(
                result["final_sync_plan"], (parent, child, tail),
            )
            result["source_maintenance"] = {
                key: value for key, value in control.items()
                if key != "control"
            }
        except migration_three_site_window.WindowBlocked as exc:
            result["source_maintenance"] = {
                "status": "CONTROL_INVENTORY_OR_OWNER_BLOCKED",
                "reason": str(exc),
                "source_pause_performed": False,
                "source_pause_allowed": False,
                "cutover_allowed": False,
            }
        return result
    except migration_three_site_window.WindowBlocked as exc:
        raise PullMigrationError(str(exc)) from None
    except migration_chain_execution_scope.RecoveryScopeBlocked as exc:
        raise PullMigrationError(str(exc)) from None





def _verify_three_owner_private_sql_dumps(plan: dict[str, Any],
                                          parent_mid: str) -> dict[str, Any]:
    """Read only the 3 original-owner private dumps; never infer final parity."""
    import migration_chain_final_saga as saga
    path = state_dir(parent_mid) / "three-source-dumps-prestage-v1" / "journal.json"
    try:
        record = saga._read_receipt(
            path, expected_schema="p07.chain-three-source-dumps-prestage.v1")
    except (saga.SagaBlocked, OSError):
        raise PullMigrationError("17_SITE_PRIVATE_SOURCE_DUMPS_UNVERIFIED") from None
    expected = set(migration_three_site_window.OWNER_SITES)
    done = record.get("completed")
    if (record.get("status") != "THREE_SOURCE_DUMPS_PRESTAGED_NOT_FINAL"
            or record.get("plan_sha256") != plan["plan_sha256"]
            or record.get("target_identity_sha256")
            != plan["target_identity_sha256"]
            or record.get("source_runtime_frozen") is not False
            or record.get("cutover_allowed") is not False
            or type(done) is not list or len(done) != 3
            or {row.get("domain") for row in done
                if isinstance(row, dict)} != expected):
        raise PullMigrationError("17_SITE_PRIVATE_SQL_RECEIPT_DRIFT")
    verified = []
    for item in done:
        name = item.get("dump_basename")
        if (type(name) is not str
                or re.fullmatch(r"[0-9a-f]{20}\.sql\.gz", name) is None
                or item.get("final_snapshot") is not False
                or item.get("source_target_parity_verified") is not False):
            raise PullMigrationError("17_SITE_PRIVATE_SQL_PATH_UNSAFE")
        local = path.parent / name
        try:
            stat_info = local.lstat()
            if (not stat.S_ISREG(stat_info.st_mode)
                    or stat_info.st_nlink != 1
                    or stat_info.st_uid != os.geteuid()
                    or stat.S_IMODE(stat_info.st_mode) & 0o077
                    or stat_info.st_size != item.get("dump_bytes")
                    or stat_info.st_size <= 0):
                raise PullMigrationError("17_SITE_PRIVATE_SQL_FILE_UNSAFE")
            digest = hashlib.sha256()
            with local.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1048576), b""):
                    digest.update(chunk)
            if digest.hexdigest() != item.get("dump_sha256"):
                raise PullMigrationError("17_SITE_PRIVATE_SQL_CONTENT_CHANGED")
            sql_diff_probe.require_nonempty_source_schema(local)
        except (OSError, sql_diff_probe.AdvisoryDiagnosticUnavailable):
            raise PullMigrationError("17_SITE_PRIVATE_SQL_READBACK_UNAVAILABLE") from None
        verified.append(item["domain"])
    return {
        "status": "THREE_ORIGINAL_PRIVATE_SQL_DUMPS_VERIFIED_NOT_FINAL",
        "site_count": 17, "database_count": 3,
        "source_frozen": False, "final_source_parity": False,
        "existing_target_database_writes": False, "cutover_allowed": False,
    }


def chain_seventeen_site_delivery(
    parent_mid: str, child_mid: str, tail_mid: str, *,
    action: str = "status", confirm: str | None = None,
) -> dict[str, Any]:
    """ONE incident-specific operator interface, not three independent cutovers.

    This command manages strictly PRIVATE preparation. Source write-freeze,
    database promotion, active target overwrite and cutover are deliberately
    outside this command until the full original-owner transaction is proven.
    """
    if action not in {
        "status", "private-prestage", "verify-private", "pause-preview",
        "paused-db-copy", "verify-paused-dbs",
    }:
        raise PullMigrationError("17_SITE_DELIVERY_ACTION_UNSUPPORTED")
    if action == "private-prestage":
        if confirm != "PRESTAGE_EXISTING_17_SITES_PRIVATE_ONLY":
            raise PullMigrationError("17_SITE_PRIVATE_PRESTAGE_CONFIRMATION_REQUIRED")
    elif action == "paused-db-copy":
        if confirm != "COPY_PAUSED_THREE_SOURCE_DATABASES_PRIVATE_ONLY":
            raise PullMigrationError("17_SITE_PAUSED_SQL_COPY_CONFIRMATION_REQUIRED")
    elif confirm is not None:
        raise PullMigrationError("17_SITE_READ_ONLY_CONFIRMATION_UNEXPECTED")
    tasks = (
        load_state(parent_mid), load_state(child_mid), load_state(tail_mid),
    )
    current_target = target_identity()
    if current_target != tasks[0].get("target_server_identity"):
        raise PullMigrationError("17_SITE_DELIVERY_TARGET_IDENTITY_CHANGED")
    try:
        scope = migration_chain_execution_scope.scope(*tasks)
        plan = scope["final_sync_plan"]
        migration_three_site_window.owner_window_scope(
            plan, migration_three_site_window.OWNER_SITES,
            whole_server_outage_approved=True,
        )
    except (migration_chain_execution_scope.RecoveryScopeBlocked,
            migration_three_site_window.WindowBlocked) as exc:
        raise PullMigrationError("17_SITE_DELIVERY_ORIGINAL_OWNERS_UNVERIFIED") from None
    if (scope["site_count"] != 17 or scope["source_task_count"] != 3
            or plan["cutover_allowed"] is not False
            or plan["source_freeze_allowed"] is not False):
        raise PullMigrationError("17_SITE_DELIVERY_CUTOVER_BOUNDARY_CHANGED")

    root = state_dir(parent_mid)
    if action in {"paused-db-copy", "verify-paused-dbs"}:
        import migration_chain_paused_sql as frozen_sql
        try:
            if action == "paused-db-copy":
                return frozen_sql.copy_paused_three_source_dbs(
                    plan, tasks, root=root, target_identity=current_target,
                    confirmation=confirm)
            return frozen_sql.verify_paused_three_source_dbs(
                plan, tasks, root=root, target_identity=current_target)
        except frozen_sql.PausedDatabaseBlocked as exc:
            raise PullMigrationError(str(exc)) from None
    if action == "status":
        # Even all three private receipts do not prove a frozen source,
        # a safe original-owner DB switch or a reversible final migration.
        return {
            "status": "17_SITE_DELIVERY_NOT_CUTOVER_READY",
            "site_count": 17, "original_task_count": 3,
            "staged_site_count": scope["staged_count"],
            "pending_site_count": scope["pending_count"],
            "plan_sha256": plan["plan_sha256"],
            "private_site_warm_attempt_exists": os.path.lexists(
                root / "p07-17-site-private-warm-stage-v1"),
            "private_resource_warm_attempt_exists": os.path.lexists(
                root / "p07-17-site-private-resource-stage-v1"),
            "private_sql_dump_attempt_exists": os.path.lexists(
                root / "three-source-dumps-prestage-v1"),
            "paused_source_sql_copy_attempt_exists": os.path.lexists(
                root / "p07-three-paused-source-db-private-v1"),
            "source_maintenance_control": "NOT_EXECUTED",
            "remaining_final_gates": [
                "FROZEN_SOURCE_WRITERS_AND_DATABASE_PARITY",
                "THREE_ORIGINAL_DB_SHADOW_ROLLBACK",
                "FROZEN_FILES_EXTERNAL_SQLITE_PARITY",
                "REAL_CP2_HTTP_AND_FULL_RECOVERY",
            ],
            "source_runtime_paused": False,
            "database_writes_performed": False,
            "cutover_allowed": False, "writes_performed": False,
        }

    if action == "pause-preview":
        import migration_chain_source_pause as pausing
        try:
            return pausing.source_pause_preview(
                plan, tasks, root=root, target_identity=current_target)
        except pausing.SourcePauseBlocked:
            raise PullMigrationError(
                "17_SITE_SOURCE_PAUSE_CONTROL_NOT_READY"
            ) from None

    if action == "verify-private":
        import migration_chain_private_file_stage as files
        import migration_chain_private_resource_stage as resources
        try:
            a = files.verify_private_seventeen_site_warm_copy(plan, root=root)
            b = resources.verify_original_private_resources(
                plan, tasks, root=root)
        except (files.WarmStageBlocked,
                resources.ResourceStageBlocked) as exc:
            raise PullMigrationError("17_SITE_PRIVATE_STAGE_READBACK_FAILED") from None
        c = _verify_three_owner_private_sql_dumps(plan, parent_mid)
        return {
            "status": "17_SITE_PRIVATE_PRESTAGE_VERIFIED_NOT_CUTOVER",
            "site_file_count": a["site_count"],
            "private_resource_count": b["resource_count"],
            "original_database_count": c["database_count"],
            "source_snapshot_frozen": False,
            "source_target_final_parity": False,
            "cutover_allowed": False, "writes_performed": False,
        }

    # Verify all destination namespaces are fresh BEFORE the first transfer.
    # A partial prior operation must be independently reconciled; never
    # auto-repeat a previous file, SQLite or SQL export.
    for dirname in (
        "p07-17-site-private-warm-stage-v1",
        "p07-17-site-private-resource-stage-v1",
        "three-source-dumps-prestage-v1",
    ):
        if os.path.lexists(root / dirname):
            raise PullMigrationError(
                "17_SITE_PRESTAGE_PRIOR_ATTEMPT_RETAIN_FOR_RECOVERY")
    import migration_chain_private_file_stage as files
    import migration_chain_private_resource_stage as resources
    try:
        a = files.stage_private_seventeen_site_warm_copy(
            plan, tasks, root=root, actual_target_identity=current_target,
            authorize_private_copy=True)
        b = resources.stage_original_private_resources(
            plan, tasks, root=root, actual_target_identity=current_target,
            authorize_private_copy=True)
    except (files.WarmStageBlocked, resources.ResourceStageBlocked):
        raise PullMigrationError(
            "17_SITE_PRIVATE_PRESTAGE_PARTIAL_RECONCILIATION_REQUIRED"
        ) from None
    c = chain_prestage_three_source_dumps(
        parent_mid, child_mid, tail_mid,
        confirm="PRESTAGE_THREE_SOURCE_DUMPS_ONLY")
    if (a.get("site_count") != 17
            or a.get("cutover_allowed") is not False
            or b.get("cutover_allowed") is not False
            or c.get("domain_count") != 3
            or c.get("cutover_allowed") is not False):
        raise PullMigrationError("17_SITE_PRESTAGE_UNEXPECTED_RESULT_RETAIN")
    return chain_seventeen_site_delivery(
        parent_mid, child_mid, tail_mid, action="verify-private")

def chain_original_resource_type_readiness(
    parent_mid: str, child_mid: str, tail_mid: str, *,
    verify_live_source: bool = False,
) -> dict[str, Any]:
    """Never silently SSH or mutate three original migration states."""
    import migration_chain_asset_audit as resources

    originals = (
        load_state(parent_mid), load_state(child_mid), load_state(tail_mid),
    )
    if target_identity() != originals[0].get("target_server_identity"):
        raise PullMigrationError("CHAIN_RESOURCES_TARGET_IDENTITY_CHANGED")
    try:
        plan = migration_chain_execution_scope.scope(*originals)["final_sync_plan"]
        if verify_live_source:
            return resources.verify_original_resource_source_types(
                plan, *originals,
            )
        result = resources.bind_original_resources(plan, *originals)
        return {key: value for key, value in result.items()
                if key != "resources"}
    except (resources.ResourceOwnerBlocked,
            migration_chain_execution_scope.RecoveryScopeBlocked) as exc:
        raise PullMigrationError(str(exc)) from None



def chain_private_resource_warm_stage(
    parent_mid: str, child_mid: str, tail_mid: str, *,
    confirm: str | None = None, verify_only: bool = False,
) -> dict[str, Any]:
    """Private external and SQLite source-origin pre-copy, never cutover.

    SQLite warm snapshots create temporary files ONLY under the original
    old-server PRIVATE source staging root. No live website/database path,
    existing CP2 path, DNS, Cron or PM2 state may be changed by this flow.
    """
    import migration_chain_private_resource_stage as resources
    if verify_only:
        if confirm is not None:
            raise PullMigrationError("CHAIN_RESOURCE_VERIFY_CONFIRM_UNEXPECTED")
    elif confirm != "PRESTAGE_17_RESOURCES_PRIVATE_ONLY":
        raise PullMigrationError("CHAIN_RESOURCE_EXPLICIT_PRIVATE_SCOPE_REQUIRED")
    original = (
        load_state(parent_mid), load_state(child_mid), load_state(tail_mid),
    )
    real_target = target_identity()
    if original[0].get("target_server_identity") != real_target:
        raise PullMigrationError("CHAIN_RESOURCE_LOCAL_TARGET_IDENTITY_CHANGED")
    try:
        plan = migration_chain_execution_scope.scope(*original)["final_sync_plan"]
        if verify_only:
            return resources.verify_original_private_resources(
                plan, original, root=state_dir(parent_mid),
            )
        return resources.stage_original_private_resources(
            plan, original, root=state_dir(parent_mid),
            actual_target_identity=real_target,
            authorize_private_copy=True,
        )
    except (resources.ResourceStageBlocked,
            migration_chain_execution_scope.RecoveryScopeBlocked) as exc:
        raise PullMigrationError(str(exc)) from None


def chain_private_file_warm_stage(
    parent_mid: str, child_mid: str, tail_mid: str, *,
    confirm: str | None = None, verify_only: bool = False,
) -> dict[str, Any]:
    """Bounded cross-owner CP2 private warm files; NOT a final migration.

    Uses the same original-three-task scope. Real file transfer is allowed
    only behind the explicit private-only confirmation; none of the active
    website roots, credentials, databases, services, DNS or state.json change.
    A prior interrupted intent is retained and cannot be automatically rerun.
    """
    import migration_chain_private_file_stage as warm

    if verify_only:
        if confirm is not None:
            raise PullMigrationError("CHAIN_WARM_VERIFY_CONFIRMATION_UNEXPECTED")
    elif confirm != "PRESTAGE_17_FILES_PRIVATE_ONLY":
        raise PullMigrationError("CHAIN_WARM_EXPLICIT_PRIVATE_SCOPE_REQUIRED")
    originals = (
        load_state(parent_mid), load_state(child_mid), load_state(tail_mid),
    )
    target = target_identity()
    if originals[0].get("target_server_identity") != target:
        raise PullMigrationError("CHAIN_WARM_TARGET_IDENTITY_CHANGED")
    try:
        plan = migration_chain_execution_scope.scope(*originals)["final_sync_plan"]
        if verify_only:
            return warm.verify_private_seventeen_site_warm_copy(
                plan, root=state_dir(parent_mid),
            )
        return warm.stage_private_seventeen_site_warm_copy(
            plan, originals, root=state_dir(parent_mid),
            actual_target_identity=target,
            authorize_private_copy=True,
        )
    except (warm.WarmStageBlocked,
            migration_chain_execution_scope.RecoveryScopeBlocked) as exc:
        raise PullMigrationError(str(exc)) from None


def chain_prestage_three_source_dumps(
    parent_mid: str, child_mid: str, tail_mid: str, *, confirm: str,
) -> dict[str, Any]:
    """Transfer fresh, source-only SQL copies for the three original owners.

    This is NOT the final consistency snapshot: the old sites keep serving
    traffic. No existing CP2 DB, application mapping or migration state.json
    is touched. Failures retain a private intent record and do not retry.
    """
    if confirm != "PRESTAGE_THREE_SOURCE_DUMPS_ONLY":
        raise PullMigrationError("CHAIN_PRESTAGE_EXPLICIT_SCOPE_REQUIRED")
    originals = [load_state(mid) for mid in (parent_mid, child_mid, tail_mid)]
    parent, child, tail = originals
    if target_identity() != parent.get("target_server_identity"):
        raise PullMigrationError("CHAIN_PRESTAGE_TARGET_IDENTITY_CHANGED")
    try:
        report = migration_chain_execution_scope.scope(parent, child, tail)
        consent = migration_three_site_window.owner_window_scope(
            report["final_sync_plan"], migration_three_site_window.OWNER_SITES)
    except (migration_chain_execution_scope.RecoveryScopeBlocked,
            migration_three_site_window.WindowBlocked) as exc:
        raise PullMigrationError("CHAIN_PRESTAGE_SCOPE_NOT_VERIFIED") from exc
    if (report["site_count"] != 17 or report["source_task_count"] != 3
            or consent["cutover_allowed"] is not False
            or report["source_freeze_allowed"] is not False):
        raise PullMigrationError("CHAIN_PRESTAGE_BOUNDARY_CHANGED")

    tasks = {state["migration_id"]: state for state in originals}
    sites = {row["domain"]: row for row in report["sites"]}
    eligible = []
    for domain in migration_three_site_window.OWNER_SITES:
        owned = sites[domain]
        source_task = tasks[owned["owner_migration_id"]]
        original_site = source_task["sites"][owned["owner_index"]]
        dbs = original_site.get("mysql_databases")
        if (original_site.get("domain") != domain
                or not isinstance(dbs, list) or len(dbs) != 1
                or not isinstance(dbs[0], str) or not dbs[0]
                or source_task.get("status") not in {"PREPARE_FAILED", "PREPARED"}
                or source_task.get("source_runtime_frozen") is not False
                or source_task.get("target_runtime_activated") is not False
                or source_task.get("dns_changed_by_p07") is not False
                or source_task.get("source_delete_allowed") is not False
                or source_task.get("existing_target_overwrite_allowed") is not False
                or not isinstance(source_task.get("source"), dict)):
            raise PullMigrationError("CHAIN_PRESTAGE_SOURCE_SITE_UNSAFE")
        eligible.append((domain, dbs[0], source_task))

    root = state_dir(parent_mid) / "three-source-dumps-prestage-v1"
    if os.path.lexists(root):
        raise PullMigrationError("CHAIN_PRESTAGE_PRIOR_ATTEMPT_RETAINED")
    if state_dir(parent_mid).is_symlink() or not state_dir(parent_mid).is_dir():
        raise PullMigrationError("CHAIN_PRESTAGE_PRIVATE_STATE_ROOT_UNSAFE")
    root.mkdir(mode=0o700, exist_ok=False)
    record: dict[str, Any] = {
        "schema": "p07.chain-three-source-dumps-prestage.v1",
        "status": "INTENT_RECORDED_UNVERIFIED",
        "original_owner_ids": [parent_mid, child_mid, tail_mid],
        "plan_sha256": report["final_sync_plan"]["plan_sha256"],
        "source_identity_sha256": report["source_identity_sha256"],
        "target_identity_sha256": report["target_identity_sha256"],
        "domains": list(migration_three_site_window.OWNER_SITES),
        "completed": [],
        "source_runtime_frozen": False,
        "source_business_writes_performed": False,
        "target_database_writes_performed": False,
        "target_config_writes_performed": False,
        "migration_state_writes_performed": False,
        "automatic_dns_change_allowed": False,
        "cutover_allowed": False,
    }
    journal = root / "journal.json"
    legacy.atomic_private_json(journal, record)
    # The helper runs only in a distinct migration-owned temporary source
    # directory; it never touches the old site's files, DB or service config.
    token = "p07-three-source-dumps-" + hashlib.sha256(
        report["final_sync_plan"]["plan_sha256"].encode("ascii")
    ).hexdigest()[:20]
    record["status"] = "SOURCE_HELPER_STAGING_INTENT"
    legacy.atomic_private_json(journal, record)
    runtime = stage_source_runtime(parent["source"], token)
    for domain, db, task in eligible:
        digest = hashlib.sha256(
            f"{task['migration_id']}:{domain}:{db}".encode("utf-8")
        ).hexdigest()[:20]
        remote_file = f"{remote_staging_root(task)}/prestage-{digest}.sql.gz"
        local_file = root / f"{digest}.sql.gz"
        if os.path.lexists(local_file):
            raise PullMigrationError("CHAIN_PRESTAGE_PRIVATE_DUMP_ALREADY_EXISTS")
        record["status"] = "SOURCE_EXPORT_AND_TRANSFER_INTENT"
        record["active_domain"] = domain
        legacy.atomic_private_json(journal, record)
        bound = dict(task, source_runtime_path=runtime)
        source_export_database(bound, db, remote_file)
        pull_path(task["source"], remote_file, local_file)
        if local_file.is_symlink() or not local_file.is_file() or local_file.stat().st_size == 0:
            raise PullMigrationError("CHAIN_PRESTAGE_SOURCE_DUMP_UNVERIFIED")
        try:
            sql_diff_probe.require_nonempty_source_schema(local_file)
        except sql_diff_probe.AdvisoryDiagnosticUnavailable as exc:
            raise PullMigrationError("CHAIN_PRESTAGE_SOURCE_SCHEMA_UNVERIFIED") from exc
        checksum = hashlib.sha256()
        with local_file.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                checksum.update(block)
        record["completed"].append({
            "domain": domain,
            "original_owner": task["migration_id"],
            "dump_basename": local_file.name,
            "dump_sha256": checksum.hexdigest(),
            "dump_bytes": local_file.stat().st_size,
            "final_snapshot": False,
            "source_target_parity_verified": False,
        })
        record.pop("active_domain", None)
        legacy.atomic_private_json(journal, record)
    record["status"] = "THREE_SOURCE_DUMPS_PRESTAGED_NOT_FINAL"
    legacy.atomic_private_json(journal, record)
    return {
        "status": record["status"],
        "domain_count": 3,
        "original_task_count": 3,
        "plan_sha256": record["plan_sha256"],
        "source_writes_frozen": False,
        "source_business_writes_performed": False,
        "source_private_export_files_created": True,
        "target_private_export_files_created": True,
        "existing_target_databases_modified": False,
        "target_config_modified": False,
        "migration_state_modified": False,
        "source_target_final_parity_verified": False,
        "automatic_dns_changed": False,
        "cutover_allowed": False,
    }


def chain_original_database_readiness(
    parent_mid: str, child_mid: str, tail_mid: str, *,
    verify_original_markers: bool = False,
) -> dict[str, Any]:
    """Local CP2-only, read-only three-owner DB blocker triage.

    It reuses existing www3 candidate-connection journal without
    reconnecting, importing or altering the previously staged database.
    """
    parent, child, tail = (
        load_state(parent_mid), load_state(child_mid), load_state(tail_mid)
    )
    if target_identity() != parent.get("target_server_identity"):
        raise PullMigrationError("CHAIN_DB_LOCAL_TARGET_IDENTITY_CHANGED")
    try:
        return migration_chain_execution_scope.original_database_readiness(
            parent, child, tail,
            verify_original_markers=verify_original_markers,
        )
    except migration_chain_execution_scope.RecoveryScopeBlocked as exc:
        raise PullMigrationError(str(exc)) from None


def remainder_scope(mid: str) -> dict[str, Any]:
    """Read-only parent-state selector; no remote call or state update."""
    try:
        return migration_remainder.select(load_state(mid))
    except migration_remainder.RemainderBlocked as exc:
        raise PullMigrationError(str(exc)) from None


def prepare_remainder(mid: str, confirm: str) -> dict[str, Any]:
    """Stage only the untouched suffix in a new state, not the blocked site.

    Normal target inventory preflight rejects already-existing destinations.
    This never clears the parent SQL guard or authorizes a partial cutover.
    """
    if confirm != f"STAGE_REMAINDER:{mid}":
        raise PullMigrationError("STAGE_REMAINDER_CONFIRMATION_REQUIRED")
    parent = load_state(mid)
    try:
        scope = migration_remainder.select(parent)
    except migration_remainder.RemainderBlocked as exc:
        raise PullMigrationError(str(exc)) from None
    state = prepare_migration(
        parent["source"], scope["candidate_domains"], "PREPARE_PULL_MIGRATION",
        remainder_parent=mid,
        expected_source_identity=str(parent["source_server_identity"]),
        expected_remainder_sites=[
            dict(row) for row in parent["sites"][scope["already_staged_sites"] + 1:]
        ],
    )
    return state


def _verify_adopted_failed_sql_resume_scope(
    state: dict[str, Any], site_domain: str
) -> None:
    """Read-only proof for exactly one verified first-stage SQL re-adoption.

    Old target DB is NEVER imported, renamed, dropped, or overwritten. The
    old SQL guard stays in history. Any uncertain ownership, site layout,
    second failed DB, source drift or existing suffix is a hard stop.
    """
    if (state.get("status") != "PREPARE_FAILED"
            or not isinstance(state.get("last_sql_guard_failure"), dict)
            or state["last_sql_guard_failure"].get("reason") != "CONDITIONAL_DDL"
            or not isinstance(state.get("sites"), list)
            or len(state["sites"]) != 18
            or not all(state.get(key) is False for key in (
                "source_runtime_frozen", "target_runtime_activated",
                "dns_changed_by_p07", "source_delete_allowed",
                "existing_target_overwrite_allowed",
            ))
            or target_identity() != state.get("target_server_identity")):
        raise PullMigrationError("ADOPTED_RESUME_ORIGINAL_18_SITE_SCOPE_UNPROVEN")
    rows = state["sites"]
    marked = [
        (i, item) for i, item in enumerate(rows)
        if isinstance(item, dict) and isinstance(item.get("database_adoption"), dict)
    ]
    if (len(marked) != 1 or marked[0][0] < 1
            or marked[0][0] >= len(rows) - 1
            or marked[0][1].get("domain") != site_domain):
        raise PullMigrationError("ADOPTED_RESUME_EXACT_ONE_RECOVERED_DB_REQUIRED")
    n, selected = marked[0]
    if (any(not isinstance(x, dict) or x.get("stage_status") != "PULLED_STAGED"
            for x in rows[:n + 1])
            or any(not isinstance(x, dict) or x.get("stage_status") != "PENDING"
                   for x in rows[n + 1:])):
        raise PullMigrationError("ADOPTED_RESUME_SUFFIX_NOT_UNTOUCHED")
    checkpoint = selected["database_adoption"]
    if (checkpoint.get("schema") != "P07_EXISTING_DB_ADOPTION_CHECKPOINT_V1"
            or checkpoint.get("status") != "SOURCE_TARGET_PREPARE_READBACK_PASS"
            or checkpoint.get("db_reimported") is not False
            or checkpoint.get("cutover_allowed") is not False
            or checkpoint.get("snapshot_is_atomic_across_servers") is not False
            or not re.fullmatch(r"[a-f0-9]{64}", str(checkpoint.get("target_dump_sha256", "")))):
        raise PullMigrationError("ADOPTED_RESUME_SQL_CHECKPOINT_UNPROVEN")
    database = selected.get("mysql_databases")
    if not isinstance(database, list) or len(database) != 1:
        raise PullMigrationError("ADOPTED_RESUME_SINGLE_DATABASE_REQUIRED")
    verifications = selected.get("mysql_verification")
    if (not isinstance(verifications, list) or
            not any(isinstance(v, dict) and
                    v.get("database") == database[0] and
                    v.get("phase") == "prepare" and
                    v.get("status") == "PASS" and
                    v.get("recovered_from_failed_guard") is True and
                    v.get("config_mode") == "PREEXISTING_OWNED_DB_NO_REIMPORT" and
                    v.get("mode") in migration_db_adoption.VALID_MODES
                    for v in verifications)):
        raise PullMigrationError("ADOPTED_RESUME_SQL_VERIFICATION_UNPROVEN")
    mid = str(state["migration_id"])
    if not SAFE_ID_RE.fullmatch(mid):
        raise PullMigrationError("ADOPTED_RESUME_MIGRATION_ID_UNVERIFIED")
    root = state_dir(mid) / "target-transactions"
    domain = str(selected["domain"])
    db = str(database[0])
    site_token = hashlib.sha256(domain.encode()).hexdigest()[:16]
    db_token = hashlib.sha256(f"{domain}:{db}:1".encode()).hexdigest()[:16]
    _private_marker_readback(root / f"site-{site_token}.json", {
        "domain": domain, "created_by_migration": mid,
    })
    ownership = _private_marker_readback(root / f"db-{db_token}.json", {
        "domain": domain, "database": db, "created_by_migration": mid,
    })
    try:
        site_mismatch = legacy.verify_target_site_creation(selected)
    except legacy.ServerMigrationError:
        raise PullMigrationError("ADOPTED_RESUME_TARGET_SITE_UNVERIFIED") from None
    if site_mismatch:
        raise PullMigrationError("ADOPTED_RESUME_TARGET_SITE_CHANGED")
    if (not isinstance(ownership.get("username"), str)
            or not isinstance(ownership.get("password"), str)
            or not app_config.verify_rewritten_application_database_config(
                Path(str(selected["site_root"])), db,
                ownership["username"], ownership["password"]
            )):
        raise PullMigrationError("ADOPTED_RESUME_APP_CONFIG_DRIFT")
    selected_plan = source_probe(state["source"], [domain])
    if (selected_plan.get("source_server_identity")
            != state.get("source_server_identity")
            or not isinstance(selected_plan.get("sites"), list)
            or len(selected_plan["sites"]) != 1
            or _site_structure_fingerprint(selected_plan["sites"][0])
               != _site_structure_fingerprint(selected)):
        raise PullMigrationError("ADOPTED_RESUME_SOURCE_IDENTITY_CHANGED")
    # Before any target write, independently assert that all suffix site
    # identities are still bound to the same source and ABSENT on CP2.
    remaining = rows[n + 1:]
    remaining_names = [str(x["domain"]) for x in remaining]
    fresh = source_probe(state["source"], remaining_names)
    if fresh.get("source_server_identity") != state.get("source_server_identity"):
        raise PullMigrationError("ADOPTED_RESUME_SOURCE_IDENTITY_CHANGED")
    require_remainder_exact_source_scope(
        remaining, fresh.get("sites"), remaining_names
    )
    target_preflight_local(fresh)


def resume_after_verified_adoption(
    mid: str, site_domain: str, confirm: str
) -> dict[str, Any]:
    """Explicit protected first-copy continuation only; NOT a final cutover."""
    if confirm != f"RESUME_VERIFIED_ADOPTION:{mid}:{site_domain}":
        raise PullMigrationError("ADOPTED_RESUME_EXPLICIT_CONFIRMATION_REQUIRED")
    if not SAFE_ID_RE.fullmatch(mid):
        raise PullMigrationError("ADOPTED_RESUME_MIGRATION_ID_INVALID")
    lock_path = state_dir(mid) / ".database-adoption.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError:
        raise PullMigrationError("ADOPTED_RESUME_PRIVATE_LOCK_UNAVAILABLE") from None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return resume_prepare_migration(mid, verified_adoption=site_domain)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def resume_prepare_migration(
    mid: str, *, verified_adoption: str | None = None
) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("status") not in {"PREPARING", "PREPARE_FAILED"}:
        raise PullMigrationError("migration is not resumable from prepare stage")
    # Prior conditional DDL verification failure is an independent hard
    # block: resume must not clear this evidence or re-import an already
    # populated target merely because a retry was requested. This check
    # intentionally runs before any status transition, save or remote call.
    previous_guard = state.get("last_sql_guard_failure")
    guarded_failure = (
        state.get("status") == "PREPARE_FAILED"
        and isinstance(previous_guard, dict)
        and previous_guard.get("reason") == "CONDITIONAL_DDL"
    )
    if guarded_failure:
        if verified_adoption is None:
            raise PullMigrationError(
                "PREPARE_RESUME_SQL_GUARD_AND_RECOVERY_PROOF_REQUIRED"
            )
        _verify_adopted_failed_sql_resume_scope(state, verified_adoption)
    elif verified_adoption is not None:
        raise PullMigrationError("ADOPTED_RESUME_NOT_A_GUARDED_SQL_FAILURE")
    # Older migrations can have no persisted SQL-guard evidence although
    # some sites were already staged. Never infer a safe retry merely from
    # a missing field: target DBs may already hold source/target mixed data.
    # This must execute before a status change, network call or DB write.
    if state.get("status") == "PREPARE_FAILED" and not guarded_failure:
        sites = state.get("sites")
        if (not isinstance(sites, list) or not sites
                or any(not isinstance(site, dict) for site in sites)
                or any(site.get("stage_status") == "PULLED_STAGED"
                       for site in sites)):
            raise PullMigrationError(
                "PREPARE_RESUME_PARTIAL_STATE_RECOVERY_PROOF_REQUIRED"
            )
    if not cloudpanel_database_server_ready_local():
        raise PullMigrationError(
            "new-server CloudPanel database server metadata is missing; migration cannot resume safely"
        )
    require_mariadb_target()
    transition_migration_status(state, "PREPARING")
    state.pop("last_error_class", None)
    if guarded_failure:
        # Keep previous failure and its fixed-count evidence in private task
        # history, never silently claim it did not happen.
        prior = state.get("sql_guard_recovery_history")
        if prior is not None:
            raise PullMigrationError("ADOPTED_RESUME_RECOVERY_ALREADY_ATTEMPTED")
        state["sql_guard_recovery_history"] = {
            "schema": "P07_ADOPTED_GUARD_FIRST_STAGE_RESUME_V1",
            "site": verified_adoption,
            "reason": "CONDITIONAL_DDL",
            "flow": previous_guard.get("flow", "SQL_GUARD_FLOW_V1_UNAVAILABLE"),
            "state": "FIRST_STAGE_ONLY_NOT_FINAL_PARITY",
            "cutover_allowed": False,
        }
    state.pop("last_sql_guard_failure", None)
    save_state(state)
    try:
        progress_note("首轮迁入 · 正在刷新旧服务器完整资产清单")
        state["asset_refresh_prepare"] = refresh_migration_assets_from_source(state)
        progress_note("首轮迁入 · 正在记录旧服务器 HTTP 基线")
        ensure_source_http_baseline(state)
        total_sites = len(state["sites"])
        for index, site in enumerate(state["sites"], 1):
            if site.get("stage_status") == "PULLED_STAGED":
                progress_note(f"首轮迁入 {index}/{total_sites} · {site['domain']} 已完成，断点跳过")
                continue
            progress_note(f"首轮迁入 {index}/{total_sites} · 正在处理 {site['domain']}")
            create_target_site(mid, site)
            pull_site_files(state, site, final=False)
            site["mysql_prepare_count"] = sync_site_databases(
                state, site, phase="prepare"
            )
            site["stage_status"] = "PULLED_STAGED"
            save_state(state)
        progress_note("首轮迁入 · 正在同步站点外部业务文件")
        state["external_paths_synced"] = sync_external_assets(state, final=False)
        progress_note("首轮迁入 · 正在同步 SQLite 数据")
        state["sqlite_snapshot_count_prepare"] = sync_sqlite_assets(
            state, phase="prepare"
        )
        progress_note("首轮迁入 · 正在准备 Cron / Node.js 运行资料")
        stage_runtime_assets(state)
        progress_note("首轮迁入 · 正在执行切换前完整性对账")
        state["pre_cutover_reconciliation"] = pre_cutover_reconcile(state)
        if state["pre_cutover_reconciliation"]["status"] != "PASS":
            details = ",".join(state["pre_cutover_reconciliation"]["failures"][:12])
            raise PullMigrationError(
                "pre-cutover completeness reconciliation failed"
                + (f": {details}" if details else "")
            )
        transition_migration_status(state, "PREPARED")
        state["source_still_live"] = True
        state["dns_manual_gate_required"] = True
        save_state(state)
        return state
    except Exception as exc:
        transition_migration_status(state, "PREPARE_FAILED")
        state["last_error_class"] = exc.__class__.__name__
        retain_safe_sql_guard_failure(state, exc)
        save_state(state)
        if isinstance(exc, PullMigrationError):
            raise
        raise PullMigrationError("target-pull prepare failed") from exc


def stage_frozen_final_mysql_shadows(
    state: dict[str, Any], *, expected_site_count: int,
) -> dict[str, Any]:
    """Stage all frozen-source final SQL dumps into NEW target shadow DBs.

    This function is intentionally NOT called by cutover_migration or CLI:
    the current full-server gate remains a hard stop. It is an independently
    testable transaction primitive, not permission to freeze a live server.

    A failed later site leaves previously verified SHADOW databases intact,
    never retries or changes original database credentials, and does not
    switch any application configuration. Exactly one snapshot per DB is
    imported only when a new empty shadow identity was first proven absent.
    """
    import migration_final_db_batch as batch
    import migration_final_db_shadow as shadow

    identity = target_identity()
    _all_sites, selected, _fingerprint = batch._safe_scope(
        state, identity, expected_site_count
    )
    if not selected:
        return {
            "status": "NO_DATABASES", "database_count": 0,
            "cutover_allowed": False, "app_config_modified": False,
        }
    # Preflight ALL original target ownership receipts and app credentials
    # before exporting or creating the first shadow. A later site without a
    # proven original DB must not cause a partial new-DB staging pass.
    for site in selected:
        domain, database = str(site["domain"]), str(site["mysql_databases"][0])
        owner_mid = shadow.original_database_owner(state, site)
        marker = legacy.target_db_marker(
            owner_mid, domain, database, 1
        )
        try:
            owned = legacy.read_target_ownership_marker(
                marker,
                {"domain": domain, "database": database,
                 "created_by_migration": owner_mid},
            )
        except legacy.ServerMigrationError as exc:
            raise PullMigrationError(
                "FINAL_SHADOW_ORIGINAL_MARKER_UNVERIFIED"
            ) from exc
        if (
            not isinstance(owned, dict)
            or not isinstance(owned.get("username"), str)
            or not isinstance(owned.get("password"), str)
            or not owned["username"] or not owned["password"]
            or not app_config.verify_rewritten_application_database_config(
                Path(str(site["site_root"])), database,
                owned["username"], owned["password"],
            )
        ):
            raise PullMigrationError(
                "FINAL_SHADOW_ORIGINAL_APP_OR_DB_UNVERIFIED"
            )
        shadow_name = shadow.shadow_identity(state, site)[1]
        if os.path.lexists(shadow._marker(state, site, shadow_name)):
            raise PullMigrationError(
                "FINAL_SHADOW_ALREADY_STAGED_RECOVERY_REQUIRED"
            )
    work = state_dir(str(state["migration_id"])) / "mysql" / "final-shadow"
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(work, 0o700)
    staged = 0
    for site in selected:
        domain = str(site["domain"])
        database = str(site["mysql_databases"][0])
        token = hashlib.sha256(
            f"{state['migration_id']}:{domain}:{database}:final-shadow".encode()
        ).hexdigest()[:24]
        remote_dump = f"{remote_staging_root(state)}/shadow-{token}.sql.gz"
        source_dump = work / f"{token}-source.sql.gz"
        try:
            # Source must already be frozen by a distinct guarded transaction.
            source_export_database(state, database, remote_dump)
            pull_path(state["source"], remote_dump, source_dump)
            if source_dump.is_symlink() or not source_dump.is_file():
                raise PullMigrationError("FINAL_SHADOW_SOURCE_EXPORT_UNVERIFIED")
            os.chmod(source_dump, 0o600)
            result = shadow.stage_frozen_source_shadow(
                state, site, source_dump, actual_target_identity=identity
            )
            if result.get("status") != "STAGED_VERIFIED_NOT_ACTIVATED":
                raise PullMigrationError("FINAL_SHADOW_STAGE_NOT_VERIFIED")
            staged += 1
        except (shadow.ShadowBlocked, OSError, ValueError) as exc:
            # No SQL, passwords or source data in the public error.
            raise PullMigrationError(
                "FINAL_SHADOW_STAGING_RECOVERY_REQUIRED"
            ) from exc
        finally:
            source_remote(
                state["source"],
                f"rm -f -- {shlex.quote(remote_dump)}",
                timeout=60, check=False,
            )
            source_dump.unlink(missing_ok=True)
    return {
        "status": "ALL_SHADOW_DATABASES_STAGED_NOT_ACTIVATED",
        "database_count": staged, "site_count": expected_site_count,
        "app_config_modified": False, "original_databases_retained": True,
        "cutover_allowed": False, "source_runtime_frozen": True,
    }


def run_frozen_final_mysql_shadow_transaction(
    state: dict[str, Any], *, expected_site_count: int,
) -> dict[str, Any]:
    """One frozen-source final-DB transaction; NOT bound to normal cutover.

    Stages all final source DBs into new isolated target databases, requires
    fresh live SQL readbacks on each, atomically journals every app mapping,
    and rolls all mappings back if any switch fails. The source was already
    frozen by a distinct guarded phase. This does NOT turn on target runtime,
    edit DNS, or set the migration to CUTOVER_PREP_READY.

    For actual site migration, caller still must validate frozen-source
    assets, Nginx/PHP/SQLite/Cron/PM2 and staged file parity, then integrate
    explicit rollback of this phase into the complete cutover exception path.
    The existing user-facing cutover is deliberately unchanged.
    """
    import migration_final_db_batch as shadow_batch

    identity = target_identity()
    try:
        all_sites, selected, _fingerprint = shadow_batch._safe_scope(
            state, identity, expected_site_count
        )
        if len(all_sites) != expected_site_count:
            raise shadow_batch.BatchBlocked("FINAL_SHADOW_SITE_COUNT_UNVERIFIED")
    except shadow_batch.BatchBlocked as exc:
        raise PullMigrationError(str(exc)) from None
    if not selected:
        return {
            "status": "NO_MYSQL_DATABASES",
            "site_count": expected_site_count, "database_count": 0,
            "cutover_allowed": False, "runtime_activated": False,
        }
    # This does not switch any site's credentials while the final SQL copy
    # is incomplete or any site still lacks the verified SQL snapshot.
    staged = stage_frozen_final_mysql_shadows(
        state, expected_site_count=expected_site_count
    )
    if (
        staged.get("status") != "ALL_SHADOW_DATABASES_STAGED_NOT_ACTIVATED"
        or staged.get("database_count") != len(selected)
        or staged.get("app_config_modified") is not False
        or staged.get("cutover_allowed") is not False
    ):
        raise PullMigrationError("FINAL_SHADOW_STAGE_PHASE_INCOMPLETE")
    try:
        switched = shadow_batch.switch_verified_shadow_batch(
            state, actual_target_identity=identity,
            expected_site_count=expected_site_count,
        )
    except shadow_batch.BatchBlocked as exc:
        # switch_verified_shadow_batch has already attempted a reverse
        # rollback and journaled its true status. Never retry a failed batch.
        raise PullMigrationError(str(exc)) from None
    if (
        switched.get("status") != "SWITCHED_VERIFIED_NOT_ACTIVATED"
        or switched.get("database_count") != len(selected)
        or switched.get("cutover_allowed") is not False
    ):
        raise PullMigrationError("FINAL_SHADOW_SWITCH_PHASE_INCOMPLETE")
    return {
        "status": "FINAL_MYSQL_SHADOW_TRANSACTION_VERIFIED_NOT_CUTOVER",
        "site_count": expected_site_count,
        "database_count": len(selected),
        "source_runtime_frozen": True,
        "original_databases_retained": True,
        "rollback_required_if_later_phase_fails": True,
        "cutover_allowed": False,
        "runtime_activated": False,
    }


def rollback_frozen_final_mysql_shadow_transaction(
    state: dict[str, Any], *, expected_site_count: int,
) -> dict[str, Any]:
    """Recovery after a later failure while the old server remains frozen.

    Only the DB app mappings are restored. This intentionally does NOT
    claim the old server was unfrozen, site files restored, or DNS changed.
    """
    import migration_final_db_batch as shadow_batch
    # The original journal was sealed in CUTOVER_RUNNING. After target
    # smoke passes the owning state becomes CUTOVER_PREP_READY, whereas
    # explicit rollback is still permitted before DNS. Reuse the immutable
    # frozen-snapshot boundary for verification without changing the actual
    # state/status or admitting any post-DNS production operation.
    status = state.get("status")
    if status not in {
        "CUTOVER_RUNNING", "CUTOVER_PREP_READY", "CUTOVER_FAILED_ROLLBACK_PARTIAL",
    } or state.get("source_runtime_frozen") is not True:
        raise PullMigrationError("FINAL_SHADOW_ROLLBACK_SOURCE_OR_STATUS_UNVERIFIED")
    if (
        state.get("dns_changed_by_p07") is True
        or state.get("source_delete_allowed") is True
        or state.get("target_runtime_activated") is True
    ):
        raise PullMigrationError("FINAL_SHADOW_ROLLBACK_RUNTIME_BOUNDARY_UNSAFE")
    scoped = dict(state)
    scoped["status"] = "CUTOVER_RUNNING"
    try:
        result = shadow_batch.rollback_verified_shadow_batch(
            scoped, actual_target_identity=target_identity(),
            expected_site_count=expected_site_count,
        )
    except shadow_batch.BatchBlocked as exc:
        raise PullMigrationError(str(exc)) from None
    if result.get("status") != "ROLLED_BACK":
        raise PullMigrationError("FINAL_SHADOW_BATCH_ROLLBACK_UNVERIFIED")
    return {
        "status": "FINAL_MYSQL_APP_MAPPING_ROLLED_BACK",
        "site_count": result["site_count"],
        "database_count": result["database_count"],
        "source_runtime_restored": False,
        "original_databases_retained": True,
        "shadow_databases_retained": True,
        "cutover_allowed": False,
    }


def recover_shadow_application_mappings_if_present(state: dict[str, Any]) -> bool:
    """Fail closed on a pending 17-site DB switch before source unfreeze.

    The journal is created before the first app-config change. No journal
    means legacy no-DB cutover has nothing to unwind; a malformed or
    mismatched journal must NOT be treated as absence of a transaction.
    This function does not remove databases, touch DNS or alter site data.
    """
    import migration_final_db_batch as shadow_batch

    mid = str(state.get("migration_id") or "")
    if not legacy.SAFE_ID_RE.fullmatch(mid):
        return False
    receipt_path = state_dir(mid) / "final-shadow-batch.json"
    try:
        receipt = shadow_batch._read_receipt(receipt_path)
        if receipt is None:
            return True
        if not isinstance(receipt, dict):
            return False
        recovered = rollback_frozen_final_mysql_shadow_transaction(
            state, expected_site_count=len(state.get("sites") or [])
        )
        return recovered.get("status") == "FINAL_MYSQL_APP_MAPPING_ROLLED_BACK"
    except (PullMigrationError, shadow_batch.BatchBlocked, OSError, ValueError):
        return False


def require_non_destructive_final_db_plan(state: dict[str, Any]) -> None:
    """Read-only early proof before source freeze for an ordinary single task.

    DB-free migrations retain their old cutover path. A DB-bearing migration
    may use an independent verified *new shadow* only if every original DB
    belongs to this exact already PREPARED task, app credentials still match,
    and there is no prior shadow attempt. Three-task parent/child/tail recovery
    is explicitly NOT admitted by this single-task route; it requires a
    separately proven whole-asset execution plan.
    """
    import migration_final_db_shadow as shadow

    sites = state.get("sites")
    if not isinstance(sites, list):
        raise PullMigrationError("FINAL_MYSQL_SITE_SCOPE_UNVERIFIED")
    if any(not isinstance(site, dict) for site in sites):
        raise PullMigrationError("FINAL_MYSQL_SITE_SCOPE_UNVERIFIED")
    if any(not isinstance(site.get("mysql_databases"), list) for site in sites):
        raise PullMigrationError("FINAL_MYSQL_DATABASE_SCOPE_UNVERIFIED")
    db_sites = [site for site in sites if site["mysql_databases"]]
    if not db_sites:
        return
    # A failed or partial job might retain newly created databases, journal
    # markers and original source-freeze assets. Never transparently retry it.
    if (
        state.get("status") != "PREPARED"
        or state.get("source_runtime_frozen") is not False
        or state.get("target_runtime_activated") is not False
        or state.get("cutover_prohibited") is True
        or state.get("partial_parent_migration_id")
        or state.get("original_db_migration_owners") is not None
        or state.get("dns_changed_by_p07") is not False
        or state.get("source_delete_allowed") is not False
        or state.get("existing_target_overwrite_allowed") is not False
        or not state.get("source_runtime_path")
        or not isinstance(state.get("source"), dict)
        or not state.get("source_server_identity")
        or not state.get("target_server_identity")
    ):
        raise PullMigrationError("FINAL_MYSQL_SAFE_REPLACEMENT_NOT_IMPLEMENTED")
    if target_identity() != state["target_server_identity"]:
        raise PullMigrationError("FINAL_MYSQL_TARGET_IDENTITY_CHANGED")
    mid = str(state.get("migration_id") or "")
    if not SAFE_ID_RE.fullmatch(mid):
        raise PullMigrationError("FINAL_MYSQL_MIGRATION_ID_UNVERIFIED")
    root = state_dir(mid)
    tx_root = root / "target-transactions"
    if root.is_symlink() or tx_root.is_symlink() or not tx_root.is_dir():
        raise PullMigrationError("FINAL_MYSQL_ORIGINAL_TRANSACTION_ROOT_UNVERIFIED")
    if os.path.lexists(root / "final-shadow-batch.json"):
        raise PullMigrationError("FINAL_MYSQL_PRIOR_SHADOW_TRANSACTION_EXISTS")
    seen_databases: set[str] = set()
    for site in sites:
        if site.get("stage_status") != "PULLED_STAGED":
            raise PullMigrationError("FINAL_MYSQL_SITE_NOT_STAGED")
        raw = site["mysql_databases"]
        if len(raw) > 1:
            raise PullMigrationError("FINAL_MYSQL_MULTI_DB_UNSUPPORTED")
        if not raw:
            continue
        domain, db = site.get("domain"), raw[0]
        try:
            domain = cloudpanel.validate_domain(str(domain))
            db = cloudpanel.validate_name(str(db), "database")
            original, shadow_name = shadow.shadow_identity(state, site)
        except (ValueError, shadow.ShadowBlocked):
            raise PullMigrationError("FINAL_MYSQL_SITE_IDENTITY_UNVERIFIED") from None
        if original != db or db in seen_databases:
            raise PullMigrationError("FINAL_MYSQL_DATABASE_SCOPE_AMBIGUOUS")
        seen_databases.add(db)
        token = hashlib.sha256(f"{domain}:{db}:1".encode()).hexdigest()[:16]
        marker = tx_root / f"db-{token}.json"
        if marker.is_symlink() or not marker.is_file():
            raise PullMigrationError("FINAL_MYSQL_ORIGINAL_MARKER_MISSING")
        try:
            owned = legacy.read_target_ownership_marker(
                marker, {"domain": domain, "database": db,
                         "created_by_migration": mid},
            )
        except legacy.ServerMigrationError:
            raise PullMigrationError("FINAL_MYSQL_ORIGINAL_MARKER_UNSAFE") from None
        if (
            not isinstance(owned, dict)
            or not isinstance(owned.get("username"), str)
            or not isinstance(owned.get("password"), str)
            or not owned["username"] or not owned["password"]
            or not app_config.verify_rewritten_application_database_config(
                Path(str(site.get("site_root") or "")), db,
                owned["username"], owned["password"],
            )
        ):
            raise PullMigrationError("FINAL_MYSQL_ORIGINAL_APP_CONFIG_UNVERIFIED")
        token2 = hashlib.sha256(
            f"{mid}:{domain}:{shadow_name}:final".encode()
        ).hexdigest()[:20]
        if os.path.lexists(tx_root / f"final-shadow-{token2}.json"):
            raise PullMigrationError("FINAL_MYSQL_PRIOR_SHADOW_EXISTS")



def cutover_migration(mid: str, confirm: str) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("cutover_prohibited") or state.get("partial_parent_migration_id"):
        raise PullMigrationError("PARTIAL_REMAINDER_CUTOVER_REQUIRES_CONSOLIDATED_RECOVERY")
    if state.get("status") not in {
        "PREPARED", "CUTOVER_RUNNING", "CUTOVER_FAILED_ROLLED_BACK"
    }:
        raise PullMigrationError("migration is not ready for final synchronization")
    if confirm != f"CUTOVER_PULL:{mid}":
        raise PullMigrationError(f"explicit confirmation required: CUTOVER_PULL:{mid}")

    # A marked initial-import target is not disposable. Do not freeze the old
    # server before a non-destructive final database replacement has been
    # independently implemented and verified.
    require_non_destructive_final_db_plan(state)
    require_mariadb_target()

    # Run all completeness work while the old server is still serving traffic.
    # This keeps missing assets out of the maintenance window and ensures we do
    # not freeze SOURCE until TARGET has a complete prepared copy.
    if not state.get("source_runtime_frozen"):
        try:
            progress_note("0/7 · 正在刷新旧服务器完整资产清单")
            refresh = refresh_migration_assets_from_source(state)
            state["asset_refresh_cutover"] = refresh
            progress_note("0/7 · 正在确认旧服务器 HTTP 基线")
            ensure_source_http_baseline(state)

            external_added = set(refresh.get("external_added_paths") or [])
            if external_added:
                progress_note(
                    f"0/7 · 正在补拉 {len(external_added)} 个新增外部 Runtime / Storage"
                )
                sync_external_assets(
                    state,
                    final=False,
                    only_paths=external_added,
                )

            sqlite_added = set(refresh.get("sqlite_added_paths") or [])
            if sqlite_added:
                progress_note(
                    f"0/7 · 正在补拉 {len(sqlite_added)} 个新增 SQLite 数据文件"
                )
                sync_sqlite_assets(
                    state,
                    phase="prepare-refresh",
                    only_paths=sqlite_added,
                )

            if refresh.get("runtime_assets_changed"):
                progress_note("0/7 · 正在重新准备变化后的 Cron / PM2 运行资料")
                stage_runtime_assets(state)

            progress_note("0/7 · 正在执行切换前完整性对账")
            state["pre_cutover_reconciliation"] = pre_cutover_reconcile(state)
            save_state(state)
            if state["pre_cutover_reconciliation"]["status"] != "PASS":
                details = ",".join(
                    state["pre_cutover_reconciliation"]["failures"][:12]
                )
                raise PullMigrationError(
                    "pre-cutover completeness reconciliation failed"
                    + (f": {details}" if details else "")
                )
        except Exception as exc:
            state["last_error_class"] = exc.__class__.__name__
            save_state(state)
            if isinstance(exc, PullMigrationError):
                raise
            raise PullMigrationError("pre-cutover reconciliation failed") from exc
    elif (
        state.get("pre_cutover_reconciliation", {}).get("status")
        != "PASS"
    ):
        state["pre_cutover_reconciliation"] = pre_cutover_reconcile(state)
        save_state(state)
        if state["pre_cutover_reconciliation"]["status"] != "PASS":
            # An interrupted CUTOVER_RUNNING task already has SOURCE frozen.
            # Restore it before returning a reconciliation failure.
            recovery = guarded_restore_cutover_boundary(state)
            complete = all(recovery.values())
            transition_migration_status(
                state,
                "CUTOVER_FAILED_ROLLED_BACK"
                if complete else "CUTOVER_FAILED_ROLLBACK_PARTIAL",
            )
            state["last_reconciliation_recovery"] = recovery
            save_state(state)
            details = ",".join(
                state["pre_cutover_reconciliation"]["failures"][:12]
            )
            raise PullMigrationError(
                "pre-cutover completeness reconciliation failed"
                + (f": {details}" if details else "")
            )

    transition_migration_status(state, "CUTOVER_RUNNING")
    state["cutover_started_at"] = now_utc()
    state.pop("last_error_class", None)
    state.pop("last_sql_guard_failure", None)
    save_state(state)
    try:
        progress_note("1/7 · 正在进入短维护窗口并保护旧服务器运行状态")
        if not state.get("source_runtime_frozen"):
            freeze_old_server(state)
        else:
            progress_note("1/7 · 旧服务器运行状态已保护，直接继续")
        progress_note("2/7 · 正在最终增量同步网站文件")
        total_sites = len(state["sites"])
        for index, site in enumerate(state["sites"], 1):
            progress_note(f"2/7 · 网站 {index}/{total_sites} · {site['domain']}")
            pull_site_files(state, site, final=True)
        progress_note("3/7 · 正在同步站点外部业务文件")
        state["external_paths_synced_final"] = sync_external_assets(state, final=True)
        progress_note("4/7 · 正在最终同步 MySQL 数据库")
        if any(site.get("mysql_databases") for site in state["sites"]):
            # Existing target DBs are NEVER dropped or reimported. Only
            # isolated new shadow DBs receive the frozen source snapshot.
            mysql_result = run_frozen_final_mysql_shadow_transaction(
                state, expected_site_count=len(state["sites"]),
            )
            if (
                mysql_result.get("status")
                != "FINAL_MYSQL_SHADOW_TRANSACTION_VERIFIED_NOT_CUTOVER"
                or mysql_result.get("source_runtime_frozen") is not True
                or mysql_result.get("original_databases_retained") is not True
                or mysql_result.get("cutover_allowed") is not False
            ):
                raise PullMigrationError("FINAL_MYSQL_SHADOW_PROOF_INCOMPLETE")
            mysql_count = mysql_result["database_count"]
            state["mysql_shadow_transaction"] = mysql_result
            save_state(state)
        else:
            mysql_count = 0
            for site in state["sites"]:
                mysql_count += sync_site_databases(state, site, phase="final")
        state["mysql_final_count"] = mysql_count
        progress_note("5/7 · 正在生成并同步 SQLite 一致性快照")
        state["sqlite_snapshot_count_final"] = sync_sqlite_assets(
            state, phase="final"
        )
        progress_note("6/7 · 正在激活新服务器 Cron / Node.js 运行任务")
        activate_target_runtime(state)
        progress_note("7/7 · 正在逐站执行新服务器本地验证")
        state["target_smoke"] = target_smoke(state)
        save_state(state)
        if state["target_smoke"]["fail"]:
            details = ", ".join(
                f"{row.get('domain')}:{row.get('reason')}"
                + (
                    f":{row.get('http_code')}"
                    + (
                        f":attempts={row.get('attempts')}"
                        if row.get("attempts")
                        else ""
                    )
                    if row.get("reason") in {
                        "LOCAL_HTTP_PROBE",
                        "HTTP_BASELINE_REGRESSION",
                    }
                    else (
                        ":" + "/".join(row.get("fields", []))
                        if row.get("fields")
                        else ""
                    )
                )
                for row in state["target_smoke"].get("failures", [])
            )
            raise PullMigrationError(
                "new-server local verification failed: "
                f"pass={state['target_smoke']['pass']} "
                f"fail={state['target_smoke']['fail']}"
                + (f"; {details}" if details else "")
            )
        transition_migration_status(state, "CUTOVER_PREP_READY")
        state["dns_manual_gate_required"] = True
        state["source_still_live"] = False
        save_state(state)
        return state
    except Exception as exc:
        progress_note("安全恢复 · 正在验证目标运行任务停止并恢复旧服务器")
        recovery = guarded_restore_cutover_boundary(state)
        target_ok = recovery["target_stopped"]
        db_ok = recovery["database_mapping_restored"]
        source_ok = recovery["source_restored"]
        transition_migration_status(
            state,
            (
                "CUTOVER_FAILED_ROLLED_BACK"
                if target_ok and db_ok and source_ok
                else "CUTOVER_FAILED_ROLLBACK_PARTIAL"
            ),
        )
        state["last_error_class"] = exc.__class__.__name__
        retain_safe_sql_guard_failure(state, exc)
        save_state(state)
        if isinstance(exc, PullMigrationError):
            raise
        raise PullMigrationError("target-pull final synchronization failed") from exc

def finalize_migration(
    mid: str,
    confirm: str,
    *,
    attempts: int,
    delay: float,
) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("status") not in {
        "CUTOVER_PREP_READY", "WAITING_DNS", "PRODUCTION_VERIFY_FAILED"
    }:
        raise PullMigrationError("migration is not waiting for DNS/final verification")
    if confirm != f"DNS_UPDATED:{mid}":
        raise PullMigrationError(f"explicit confirmation required: DNS_UPDATED:{mid}")
    progress_note("公网验证 1/2 · 正在确认 DNS 路由是否已到达新服务器")
    route = public_route_proof(state, attempts=attempts, delay=delay)
    state["public_route_proof"] = route
    if route["status"] != "PASS":
        transition_migration_status(state, "WAITING_DNS")
        save_state(state)
        return state
    progress_note("公网验证 2/2 · 正在逐站检查 HTTPS 与正式访问状态")
    production = production_verify(state)
    state["production_verification"] = production
    if production["status"] != "PASS":
        transition_migration_status(state, "PRODUCTION_VERIFY_FAILED")
        save_state(state)
        raise PullMigrationError("public production verification failed")
    transition_migration_status(state, "PRODUCTION_PASS")
    state["production_passed_at"] = now_utc()
    state["source_retained_for_recovery"] = True
    state["source_delete_allowed"] = False
    state["dns_changed_by_p07"] = False
    state["source_helper_retained_for_recovery"] = True
    save_state(state)
    return state


def guarded_restore_cutover_boundary(state: dict[str, Any]) -> dict[str, bool]:
    """Prevent split-brain: never restart SOURCE while target may be active.

    Deactivation, DB app-config restoration and SOURCE unfreeze are separate,
    evidence-bearing operations. A failed target deactivation is a hard stop
    for SOURCE unfreeze, even if an exception occurs in cleanup itself.
    On DB rollback failure with target *verified stopped*, restoring SOURCE
    is allowed for service recovery, but the overall status remains PARTIAL.
    """
    try:
        stopped = deactivate_target_runtime(state) is True
    except Exception:
        stopped = False
    # A successful return is not enough if the runtime state still claims
    # an active job. Avoid silently reopening the old source alongside it.
    target_ok = stopped and state.get("target_runtime_activated") is not True
    db_ok = False
    source_ok = False
    if target_ok:
        try:
            db_ok = recover_shadow_application_mappings_if_present(state) is True
        except Exception:
            db_ok = False
        try:
            source_ok = restore_old_server(state) is True
        except Exception:
            source_ok = False
    return {
        "target_stopped": target_ok,
        "database_mapping_restored": db_ok,
        "source_restored": source_ok,
    }


def require_old_source_route_before_manual_rollback(state: dict[str, Any]) -> None:
    """Fail closed before any pre-DNS rollback that could strand live clients.

    The owner switches DNS manually, independent of P07. Therefore the field
    dns_changed_by_p07=False is NOT evidence DNS remains on the source VPS.
    Only direct, non-proxied DNS that still resolves every selected domain
    exclusively to the pinned old source IP is safe for automatic rollback.
    CDN/dual-stack/ambiguous records require supervised reconciliation.
    This performs DNS reads only; it does not touch source or target files.
    """
    source = state.get("source")
    sites = state.get("sites")
    if not isinstance(source, dict) or not isinstance(sites, list) or not sites:
        raise PullMigrationError("MANUAL_ROLLBACK_PRE_DNS_SOURCE_ROUTE_UNPROVEN")
    try:
        old_address = ipaddress.ip_address(str(source.get("ip") or ""))
    except ValueError:
        raise PullMigrationError("MANUAL_ROLLBACK_PRE_DNS_SOURCE_ROUTE_UNPROVEN") from None
    seen: set[str] = set()
    for site in sites:
        if not isinstance(site, dict):
            raise PullMigrationError("MANUAL_ROLLBACK_PRE_DNS_SOURCE_ROUTE_UNPROVEN")
        domain = str(site.get("domain") or "")
        if not domain or domain.lower() in seen:
            raise PullMigrationError("MANUAL_ROLLBACK_PRE_DNS_SOURCE_ROUTE_UNPROVEN")
        seen.add(domain.lower())
        try:
            addresses = {
                ipaddress.ip_address(record[4][0])
                for record in socket.getaddrinfo(
                    domain, 443, type=socket.SOCK_STREAM
                )
            }
        except (OSError, ValueError, IndexError):
            raise PullMigrationError("MANUAL_ROLLBACK_PRE_DNS_SOURCE_ROUTE_UNPROVEN") from None
        if addresses != {old_address}:
            raise PullMigrationError("MANUAL_ROLLBACK_PRE_DNS_SOURCE_ROUTE_UNPROVEN")


def rollback_migration(mid: str, confirm: str) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("status") in {"PRODUCTION_PASS", "PRODUCTION_VERIFY_FAILED"}:
        raise PullMigrationError(
            "post-DNS rollback requires data reconciliation; runtime-only rollback is denied"
        )
    if state.get("status") not in {
        "PREPARED", "CUTOVER_RUNNING", "CUTOVER_PREP_READY",
        "CUTOVER_FAILED_ROLLBACK_PARTIAL",
    }:
        raise PullMigrationError("migration is not in a rollback-eligible state")
    if confirm != f"ROLLBACK_PULL:{mid}":
        raise PullMigrationError(f"explicit confirmation required: ROLLBACK_PULL:{mid}")
    if state.get("status") == "CUTOVER_PREP_READY":
        # A manual DNS switch can precede finalization without updating P07
        # state. Require fresh proof of the old route before ANY rollback.
        require_old_source_route_before_manual_rollback(state)
    recovery = guarded_restore_cutover_boundary(state)
    target_ok = recovery["target_stopped"]
    db_ok = recovery["database_mapping_restored"]
    source_ok = recovery["source_restored"]
    transition_migration_status(
        state,
        "ROLLED_BACK" if target_ok and db_ok and source_ok else "ROLLBACK_PARTIAL",
    )
    state["source_delete_allowed"] = False
    state["dns_changed_by_p07"] = False
    save_state(state)
    if not (target_ok and db_ok and source_ok):
        raise PullMigrationError("rollback is partial and needs operator attention")
    return state


def post_migration_audit(state: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "production_pass": state.get("status") == "PRODUCTION_PASS",
        "public_route_proof_pass": (
            isinstance(state.get("public_route_proof"), dict)
            and state["public_route_proof"].get("status") == "PASS"
        ),
        "production_verification_pass": (
            isinstance(state.get("production_verification"), dict)
            and state["production_verification"].get("status") == "PASS"
        ),
        "source_recovery_copy_retained": bool(
            state.get("source_retained_for_recovery")
        ),
        "source_delete_denied": not bool(
            state.get("source_delete_allowed", False)
        ),
        "dns_not_changed_by_p07": not bool(
            state.get("dns_changed_by_p07", False)
        ),
        "existing_target_overwrite_denied": not bool(
            state.get("existing_target_overwrite_allowed", False)
        ),
        "secrets_not_emitted": not bool(
            state.get("secrets_emitted", False)
        ),
        "source_runtime_frozen_for_recovery": (
            state.get("source_runtime_frozen") is True
        ),
    }
    blocker_tokens = {
        "production_pass": "MIGRATION_NOT_PRODUCTION_PASS",
        "public_route_proof_pass": "PUBLIC_ROUTE_NOT_VERIFIED",
        "production_verification_pass": "PRODUCTION_VERIFY_NOT_PASS",
        "source_recovery_copy_retained": "SOURCE_RECOVERY_COPY_NOT_RETAINED",
        "source_delete_denied": "SOURCE_DELETE_POLICY_VIOLATION",
        "dns_not_changed_by_p07": "DNS_MUTATION_POLICY_VIOLATION",
        "existing_target_overwrite_denied": "TARGET_OVERWRITE_POLICY_VIOLATION",
        "secrets_not_emitted": "SECRET_OUTPUT_POLICY_VIOLATION",
        "source_runtime_frozen_for_recovery": "SOURCE_RUNTIME_NOT_FROZEN",
    }
    closure_blockers = [
        blocker_tokens[key]
        for key, passed in checks.items()
        if not passed
    ]
    retirement_blockers = ["OWNER_RETIREMENT_GATE_REQUIRED"]
    if state.get("source_helper_retained_for_recovery"):
        retirement_blockers.append("SOURCE_HELPER_RETAINED_FOR_RECOVERY")

    return {
        "status": (
            "PRODUCTION_CLOSURE_VERIFIED"
            if not closure_blockers
            else "INCOMPLETE"
        ),
        "old_server_disposition": "RETAIN_RECOVERY_COPY",
        "retirement_readiness": "NOT_AUTHORIZED",
        "owner_retirement_gate_required": True,
        "old_server_delete_allowed": False,
        "source_runtime_state": (
            "FROZEN"
            if state.get("source_runtime_frozen") is True
            else (
                "LIVE"
                if state.get("source_runtime_frozen") is False
                else "UNKNOWN"
            )
        ),
        "source_helper_retained_for_recovery": bool(
            state.get("source_helper_retained_for_recovery")
        ),
        "production_passed_at": state.get("production_passed_at"),
        "checks": checks,
        "closure_blockers": closure_blockers,
        "retirement_blockers": retirement_blockers,
        "writes_performed": False,
    }


def _blocked_first_pending_database(state: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    """Return ONLY the first failed DB's public domain and redacted receipt.

    Do not select a later database if the earliest unfinished site is not
    an owned PENDING single-DB site. A menu diagnostic is not a resume gate.
    """
    if (state.get("status") != "PREPARE_FAILED"
            or not isinstance(state.get("last_sql_guard_failure"), dict)
            or state["last_sql_guard_failure"].get("reason") != "CONDITIONAL_DDL"):
        return None, None
    sites = state.get("sites")
    if not isinstance(sites, list):
        return None, None
    first = next((row for row in sites
                  if isinstance(row, dict)
                  and row.get("stage_status") != "PULLED_STAGED"), None)
    if (not isinstance(first, dict)
            or first.get("stage_status") != "PENDING"
            or not isinstance(first.get("domain"), str)
            or not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", first["domain"])
            or not isinstance(first.get("mysql_databases"), list)
            or len(first["mysql_databases"]) != 1):
        return None, None
    raw = first.get("failed_prepare_sql_evidence")
    sanitized = None
    if isinstance(raw, dict) and raw.get("status") in {
        "RETAINED_NOT_RECOVERED", "EVIDENCE_RETENTION_UNVERIFIED",
    }:
        sanitized = {
            "status": raw["status"],
            "source_dump_retained": raw.get("source_dump_retained") is True,
            "target_dump_retained": raw.get("target_dump_retained") is True,
            "cutover_allowed": False,
            "db_reimport_allowed": False,
        }
    return first["domain"], sanitized


def summary(state: dict[str, Any]) -> dict[str, Any]:
    blocked_site, blocked_evidence = _blocked_first_pending_database(state)
    adopted = [
        row.get("domain") for row in state.get("sites", [])
        if isinstance(row, dict) and isinstance(row.get("database_adoption"), dict)
        and row["database_adoption"].get("status") == "SOURCE_TARGET_PREPARE_READBACK_PASS"
    ] if isinstance(state.get("sites"), list) else []
    adopted_site = (
        adopted[0] if len(adopted) == 1 and isinstance(adopted[0], str)
        and re.fullmatch(r"[A-Za-z0-9.-]{1,253}", adopted[0])
        and state.get("status") == "PREPARE_FAILED"
        and isinstance(state.get("last_sql_guard_failure"), dict)
        and state["last_sql_guard_failure"].get("reason") == "CONDITIONAL_DDL"
        else None
    )
    return {
        "first_failed_sql_site": blocked_site,
        "first_failed_sql_evidence": blocked_evidence,
        "first_stage_adopted_sql_site": adopted_site,
        "schema": state.get("schema"),
        "migration_id": state.get("migration_id"),
        "status": state.get("status"),
        "last_sql_guard_failure": state.get("last_sql_guard_failure"),
        "direction": state.get("direction"),
        "current_server_role": state.get("current_server_role"),
        "old_server_ip": (state.get("source") or {}).get("ip"),
        "site_count": len(state.get("sites", [])),
        "mysql_final_count": state.get("mysql_final_count"),
        "sqlite_snapshot_count_prepare": state.get("sqlite_snapshot_count_prepare"),
        "sqlite_snapshot_count_final": state.get("sqlite_snapshot_count_final"),
        "pre_cutover_reconciliation": state.get(
            "pre_cutover_reconciliation"
        ),
        "source_http_baseline": state.get("source_http_baseline"),
        "target_smoke": state.get("target_smoke"),
        "public_route_proof": state.get("public_route_proof"),
        "production_verification": state.get("production_verification"),
        "post_audit": post_migration_audit(state),
        "dns_manual_gate_required": state.get("dns_manual_gate_required", False),
        "source_retained_for_recovery": state.get(
            "source_retained_for_recovery", False
        ),
        "old_server_external_listeners": state.get(
            "source_external_listeners", []
        ),
        "source_delete_allowed": bool(state.get("source_delete_allowed", False)),
        "dns_changed_by_p07": bool(state.get("dns_changed_by_p07", False)),
        "existing_target_overwrite_allowed": bool(
            state.get("existing_target_overwrite_allowed", False)
        ),
        "partial_parent_migration_id": state.get("partial_parent_migration_id"),
        # Report runtime readiness rather than simply echoing the
        # partial-child flag. A PREPARE_FAILED parent can otherwise print
        # cutover_prohibited=false even though cutover_migration rejects it.
        "cutover_prohibited": bool(
            state.get("cutover_prohibited", False)
            or state.get("partial_parent_migration_id")
            or state.get("status") not in {
                "PREPARED", "CUTOVER_RUNNING", "CUTOVER_FAILED_ROLLED_BACK"
            }
        ),
        "prepare_failure_provenance": (
            "MISSING_PARTIAL_STATE_RECOVERY_REQUIRED"
            if state.get("status") == "PREPARE_FAILED"
            and not isinstance(state.get("last_sql_guard_failure"), dict)
            else "RECORDED" if isinstance(
                state.get("last_sql_guard_failure"), dict
            ) else "NOT_APPLICABLE"
        ),
        "secrets_emitted": bool(state.get("secrets_emitted", False)),
    }



def _source_service_state(
    source: dict[str, Any],
    service: str,
) -> str:
    proc = source_remote(
        source,
        f"systemctl is-active {shlex.quote(service)}",
        timeout=30,
        check=False,
    )
    value = proc.stdout.strip().splitlines()
    return value[-1].strip() if value else "unknown"


def _source_listener_ports(source: dict[str, Any]) -> set[int] | None:
    proc = source_remote(source, "ss -ltnH", timeout=30, check=False)
    if proc.returncode != 0:
        return None
    ports: set[int] = set()
    for raw in proc.stdout.splitlines():
        parts = raw.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        if ":" not in local:
            continue
        value = local.rsplit(":", 1)[-1]
        if value.isdigit():
            ports.add(int(value))
    return ports


def source_nginx_status(source: dict[str, Any]) -> dict[str, Any]:
    site_state = _source_service_state(source, "nginx")
    panel_state = _source_service_state(source, "clp-nginx")
    ports = _source_listener_ports(source)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "old_server_ip": source["ip"],
        "site_nginx_service": "nginx.service",
        "site_nginx_state": site_state,
        "site_nginx_running": site_state == "active",
        "cloudpanel_nginx_service": "clp-nginx.service",
        "cloudpanel_nginx_state": panel_state,
        "web_listener_80_443": (
            "UNKNOWN"
            if ports is None
            else ("YES" if ports & {80, 443} else "NO")
        ),
        "cloudpanel_listener_8443": (
            "UNKNOWN"
            if ports is None
            else ("YES" if 8443 in ports else "NO")
        ),
        "writes_performed": False,
        "dns_changed": False,
        "source_deleted": False,
        "secrets_emitted": False,
    }


def source_nginx_start(
    source: dict[str, Any],
    confirm: str,
) -> dict[str, Any]:
    before = source_nginx_status(source)
    if before["site_nginx_running"]:
        result = dict(before)
        result["status"] = "ALREADY_RUNNING"
        return result

    expected = f"START_SOURCE_NGINX:{source['ip']}"
    if confirm != expected:
        raise PullMigrationError(f"explicit confirmation required: {expected}")

    config = source_remote(source, "nginx -t", timeout=60, check=False)
    if config.returncode != 0:
        raise PullMigrationError(
            "old-server website Nginx config test failed; start denied"
        )

    started = source_remote(
        source,
        "systemctl start nginx",
        timeout=120,
        check=False,
    )
    if started.returncode != 0:
        raise PullMigrationError("old-server website Nginx start failed")

    after = source_nginx_status(source)
    if not after["site_nginx_running"]:
        raise PullMigrationError("old-server website Nginx did not become active")
    result = dict(after)
    result["status"] = "STARTED"
    result["writes_performed"] = True
    result["config_test"] = "PASS"
    return result


def source_nginx_stop(
    source: dict[str, Any],
    confirm: str,
) -> dict[str, Any]:
    before = source_nginx_status(source)
    if not before["site_nginx_running"]:
        result = dict(before)
        result["status"] = "ALREADY_STOPPED"
        return result

    expected = f"STOP_SOURCE_NGINX:{source['ip']}"
    if confirm != expected:
        raise PullMigrationError(f"explicit confirmation required: {expected}")

    stopped = source_remote(
        source,
        "systemctl stop nginx",
        timeout=120,
        check=False,
    )
    if stopped.returncode != 0:
        raise PullMigrationError("old-server website Nginx stop failed")

    after = source_nginx_status(source)
    if after["site_nginx_running"]:
        raise PullMigrationError("old-server website Nginx is still active")
    result = dict(after)
    result["status"] = "STOPPED"
    result["writes_performed"] = True
    return result


def _local_service_state(service: str) -> str:
    proc = run_local(
        ["systemctl", "is-active", service],
        timeout=30,
        check=False,
    )
    value = proc.stdout.strip().splitlines()
    return value[-1].strip() if value else "unknown"


def _local_listener_ports() -> set[int] | None:
    proc = run_local(["ss", "-ltnH"], timeout=30, check=False)
    if proc.returncode != 0:
        return None
    ports: set[int] = set()
    for raw in proc.stdout.splitlines():
        parts = raw.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        if ":" not in local:
            continue
        value = local.rsplit(":", 1)[-1]
        if value.isdigit():
            ports.add(int(value))
    return ports


def local_nginx_status() -> dict[str, Any]:
    site_state = _local_service_state("nginx")
    panel_state = _local_service_state("clp-nginx")
    ports = _local_listener_ports()
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "site_nginx_state": site_state,
        "site_nginx_running": site_state == "active",
        "cloudpanel_nginx_state": panel_state,
        "web_listener_80_443": (
            "UNKNOWN"
            if ports is None
            else ("YES" if ports & {80, 443} else "NO")
        ),
        "cloudpanel_listener_8443": (
            "UNKNOWN"
            if ports is None
            else ("YES" if 8443 in ports else "NO")
        ),
        "writes_performed": False,
        "dns_changed": False,
        "source_deleted": False,
        "secrets_emitted": False,
    }


def local_nginx_start(confirm: str) -> dict[str, Any]:
    before = local_nginx_status()
    if before["site_nginx_running"]:
        result = dict(before)
        result["status"] = "ALREADY_RUNNING"
        return result
    if confirm != "START_LOCAL_NGINX":
        raise PullMigrationError(
            "explicit confirmation required: START_LOCAL_NGINX"
        )

    config = run_local(["nginx", "-t"], timeout=60, check=False)
    if config.returncode != 0:
        raise PullMigrationError(
            "local website Nginx config test failed; start denied"
        )

    started = run_local(
        ["systemctl", "start", "nginx"],
        timeout=120,
        check=False,
    )
    if started.returncode != 0:
        raise PullMigrationError("local website Nginx start failed")

    after = local_nginx_status()
    if not after["site_nginx_running"]:
        raise PullMigrationError("local website Nginx did not become active")
    result = dict(after)
    result["status"] = "STARTED"
    result["writes_performed"] = True
    result["config_test"] = "PASS"
    return result


def local_nginx_stop(confirm: str) -> dict[str, Any]:
    before = local_nginx_status()
    if not before["site_nginx_running"]:
        result = dict(before)
        result["status"] = "ALREADY_STOPPED"
        return result
    if confirm != "STOP_LOCAL_NGINX":
        raise PullMigrationError(
            "explicit confirmation required: STOP_LOCAL_NGINX"
        )

    stopped = run_local(
        ["systemctl", "stop", "nginx"],
        timeout=120,
        check=False,
    )
    if stopped.returncode != 0:
        raise PullMigrationError("local website Nginx stop failed")

    after = local_nginx_status()
    if after["site_nginx_running"]:
        raise PullMigrationError("local website Nginx is still active")
    result = dict(after)
    result["status"] = "STOPPED"
    result["writes_performed"] = True
    return result

def source_plan_local(domains: list[str]) -> dict[str, Any]:
    try:
        manifest = legacy.current_inventory()
        sites = legacy.select_sites(manifest, domains)
        legacy.validate_full_server_site_set(sites)
        capacity = legacy.migration_capacity_estimate(sites)
        dependency = legacy.source_dependency_preflight(
            sites,
            capacity,
            allow_missing_rsync_autofix=True,
        )
    except legacy.ServerMigrationError as exc:
        raise PullMigrationError(str(exc)) from exc

    external_assets: list[dict[str, str]] = []
    for site in sites:
        user = str(site["site_user"])
        assets = legacy.external_assets_for_site(site)
        site["external_paths"] = [row["path"] for row in assets]
        for asset in assets:
            row = {
                "path": str(asset["path"]),
                "user": user,
                "reason": str(asset.get("reason") or "DISCOVERED_EXTERNAL"),
            }
            if row not in external_assets:
                external_assets.append(row)

    sqlite_assets = []
    for path, user in legacy.sqlite_paths_for_sites(sites):
        try:
            mode = path.stat().st_mode & 0o777
        except OSError:
            continue
        sqlite_assets.append({
            "path": str(path),
            "user": user,
            "mode": mode,
        })

    selected_users = {str(site["site_user"]) for site in sites}
    system_cron: list[dict[str, str]] = []
    user_cron: list[dict[str, str]] = []
    pm2_rows: list[dict[str, str]] = []
    seen_system: set[str] = set()
    seen_user: set[str] = set()
    seen_pm2: set[str] = set()

    for site in sites:
        user = str(site["site_user"])
        cron = site.get("cron") if isinstance(site.get("cron"), dict) else {}
        for value in cron.get("source_paths", []) if isinstance(cron.get("source_paths"), list) else []:
            path = Path(str(value))
            if not path.is_file() or path.is_symlink():
                continue
            text = str(path)
            if text.startswith("/etc/cron.d/"):
                if text in seen_system:
                    continue
                try:
                    users = legacy.system_cron_job_users(path)
                except legacy.ServerMigrationError as exc:
                    raise PullMigrationError(str(exc)) from exc
                if not users or not users.issubset(selected_users):
                    raise PullMigrationError(
                        f"shared/ambiguous system Cron requires manual separation: {text}"
                    )
                system_cron.append({"path": text})
                seen_system.add(text)
            elif text in {
                f"/var/spool/cron/crontabs/{user}",
                f"/var/spool/cron/{user}",
            } and user not in seen_user:
                user_cron.append({"path": text, "user": user})
                seen_user.add(user)

        pm2 = site.get("pm2") if isinstance(site.get("pm2"), dict) else {}
        dump = Path("/home") / user / ".pm2/dump.pm2"
        if pm2.get("present") and dump.is_file() and user not in seen_pm2:
            try:
                node = legacy.resolve_source_pm2_node_runtime(user, dump)
            except legacy.ServerMigrationError as exc:
                raise PullMigrationError(str(exc)) from exc
            pm2_rows.append({
                "user": user,
                "dump": str(dump),
                "node_runtime": str(node),
            })
            seen_pm2.add(user)

    return {
        "schema": SCHEMA,
        "status": "READY",
        "source_server_identity": (
            manifest.get("source_server") or {}
        ).get("hostname_hash", "UNKNOWN"),
        "sites": sites,
        "capacity_estimate": capacity,
        "source_dependency_preflight": dependency,
        "external_assets": external_assets,
        "sqlite_assets": sqlite_assets,
        "runtime_assets": {
            "system_cron": system_cron,
            "user_cron": user_cron,
            "pm2": pm2_rows,
        },
        "source_external_listeners": legacy.discover_source_external_listeners(),
        "writes_performed": False,
        "secrets_emitted": False,
    }


def source_snapshot_sqlite(source: Path, output: Path) -> dict[str, Any]:
    if not str(source).startswith("/home/"):
        raise PullMigrationError("SQLite source is outside /home")
    if not str(output).startswith("/var/lib/vf-server-ops/pull-source/"):
        raise PullMigrationError("unsafe SQLite staging output")
    try:
        legacy.sqlite_snapshot(source, output)
    except legacy.ServerMigrationError as exc:
        raise PullMigrationError("SQLite snapshot failed") from exc
    return {"status": "PASS", "secrets_emitted": False}


def source_export_db(database: str, output: Path) -> dict[str, Any]:
    allowed = Path("/var/lib/vf-server-ops/pull-source")
    try:
        output.relative_to(allowed)
    except ValueError:
        raise PullMigrationError("unsafe MySQL staging output") from None
    if (output == allowed or output.suffix != ".gz"
            or ".." in output.parts
            or allowed.is_symlink()
            or not output.parent.resolve().is_relative_to(allowed)):
        raise PullMigrationError("unsafe MySQL staging output")
    if os.path.lexists(output) or output.parent.is_symlink():
        raise PullMigrationError("source SQL export already exists or path unsafe")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.parent.resolve().is_relative_to(allowed):
        raise PullMigrationError("unsafe MySQL staging output")
    os.chmod(output.parent, 0o700)
    try:
        cloudpanel.export_database(database, output, clpctl="clpctl")
    except (cloudpanel.CloudPanelError, ValueError) as exc:
        raise PullMigrationError("MySQL export failed") from exc
    os.chmod(output, 0o600)
    try:
        sql_diff_probe.require_nonempty_source_schema(output)
    except sql_diff_probe.AdvisoryDiagnosticUnavailable:
        # This helper may be staged on a remote VPS for later migrations.
        # Never declare PASS for a nonempty gzip with no usable table DDL.
        raise PullMigrationError("SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA") from None
    return {"status": "PASS", "secrets_emitted": False}



def validate_seventeen_site_source_freeze_control(
    control: dict[str, Any], *, check_live_source_files: bool = True,
) -> dict[str, Any]:
    """Source-side *second* authority check before global Cron/PM2/Nginx stop.

    The CP2 planner already checks original owner provenance. The old VPS
    independently denies arbitrary file deletion or user shutdown even if a
    transferred freeze-control.json was malformed or raced between checks.
    Missing/symlinked/renamed Cron or PM2 inventory is stale and fails closed.
    Pure-data validation may be run without touching the old VPS in tests.
    """
    if not isinstance(control, dict):
        raise PullMigrationError("17_SITE_SOURCE_CONTROL_INVALID")
    sites = control.get("sites")
    if type(sites) is not list or len(sites) != 17:
        raise PullMigrationError("17_SITE_SOURCE_SCOPE_CHANGED")
    users: set[str] = set()
    domains: set[str] = set()
    for site in sites:
        if not isinstance(site, dict):
            raise PullMigrationError("17_SITE_SOURCE_SITE_INVALID")
        domain, user = site.get("domain"), site.get("site_user")
        root = site.get("site_root")
        if (type(domain) is not str or not domain
                or type(user) is not str
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", user)
                or type(root) is not str
                or not root.startswith(f"/home/{user}/")
                or ".." in Path(root).parts
                or "//" in root or "\x00" in root
                or domain in domains or user in users):
            raise PullMigrationError("17_SITE_SOURCE_SITE_IDENTITY_INVALID")
        domains.add(domain)
        users.add(user)

    rows = []
    for kind in ("pending_system_cron", "pending_user_cron", "pending_pm2"):
        items = control.get(kind)
        if type(items) is not list:
            raise PullMigrationError("17_SITE_SOURCE_RUNTIME_CONTROL_MISSING")
        seen = set()
        for item in items:
            if not isinstance(item, dict) or item.get("activated") is not False:
                raise PullMigrationError("17_SITE_SOURCE_RUNTIME_CONTROL_INVALID")
            path, user = item.get("source_path"), item.get("user")
            if (type(path) is not str or not path.startswith("/")
                    or "//" in path or "\x00" in path
                    or ".." in Path(path).parts
                    or str(Path(path)) != path):
                raise PullMigrationError("17_SITE_SOURCE_RUNTIME_PATH_UNSAFE")
            if kind == "pending_system_cron":
                if (user is not None or not path.startswith("/etc/cron.d/")
                        or not re.fullmatch(r"[A-Za-z0-9_.-]+",
                                            path[len("/etc/cron.d/"):])):
                    raise PullMigrationError("17_SITE_SOURCE_SYSTEM_CRON_SCOPE_UNSAFE")
                key = path
            else:
                if type(user) is not str or user not in users:
                    raise PullMigrationError("17_SITE_SOURCE_RUNTIME_USER_UNOWNED")
                if kind == "pending_user_cron":
                    if path not in (
                        f"/var/spool/cron/crontabs/{user}",
                        f"/var/spool/cron/{user}",
                    ):
                        raise PullMigrationError("17_SITE_SOURCE_USER_CRON_UNSAFE")
                elif path != f"/home/{user}/.pm2/dump.pm2":
                    raise PullMigrationError("17_SITE_SOURCE_PM2_PATH_UNSAFE")
                key = user
            if key in seen:
                raise PullMigrationError("17_SITE_SOURCE_RUNTIME_DUPLICATED")
            seen.add(key)
            rows.append((kind, path))
    if check_live_source_files:
        for kind, path in rows:
            try:
                info = Path(path).lstat()
            except OSError:
                raise PullMigrationError(
                    "17_SITE_SOURCE_RUNTIME_PATH_CHANGED"
                ) from None
            if (not stat.S_ISREG(info.st_mode)
                    or stat.S_ISLNK(info.st_mode)
                    or stat.S_IMODE(info.st_mode) & 0o002):
                raise PullMigrationError("17_SITE_SOURCE_RUNTIME_FILE_UNSAFE")
    return {
        "status": "SOURCE_FREEZE_CONTROL_17_VERIFIED_NOT_EXECUTED",
        "site_count": 17,
        "system_cron_count": len(control["pending_system_cron"]),
        "user_cron_count": len(control["pending_user_cron"]),
        "pm2_count": len(control["pending_pm2"]),
        "writers_stopped": False, "cutover_allowed": False,
    }


def source_freeze(
    mid: str, control_path: Path, *, require_fresh: bool = False,
    expected_site_count: int | None = None,
    expected_control_sha256: str | None = None,
) -> dict[str, Any]:
    if not SAFE_ID_RE.fullmatch(mid):
        raise PullMigrationError("invalid migration id")
    if not str(control_path).startswith("/var/lib/vf-server-ops/pull-source/"):
        raise PullMigrationError("unsafe freeze control path")
    try:
        control = json.loads(control_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PullMigrationError("freeze control is invalid") from exc
    if control.get("migration_id") != mid:
        raise PullMigrationError("freeze control migration id mismatch")
    if require_fresh:
        # Three historical owners MUST be paused in one fresh recovery
        # transaction. Never reuse an old or interrupted source journal.
        if expected_site_count != 17:
            raise PullMigrationError("17-site source freeze count required")
        if not isinstance(expected_control_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_control_sha256
        ):
            raise PullMigrationError("17-site freeze control digest required")
        try:
            raw = control_path.read_bytes()
            info = control_path.lstat()
        except OSError:
            raise PullMigrationError("17-site source control unavailable") from None
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077
                or hashlib.sha256(raw).hexdigest()
                != expected_control_sha256):
            raise PullMigrationError("17-site source control identity unsafe")
        sites = control.get("sites")
        if (not isinstance(sites, list)
                or len(sites) != expected_site_count
                or any(not isinstance(site, dict)
                       or not isinstance(site.get("domain"), str)
                       or not isinstance(site.get("site_user"), str)
                       for site in sites)
                or len({site["domain"] for site in sites}) != 17
                or len({site["site_user"] for site in sites}) != 17
                or any(not isinstance(control.get(key), list)
                       for key in ("pending_system_cron",
                                   "pending_user_cron", "pending_pm2"))):
            raise PullMigrationError("17-site source control incomplete")
        validate_seventeen_site_source_freeze_control(
            control, check_live_source_files=True)
        # A prior source-side attempt may have stopped services before a
        # network outage. Its record must remain for explicit recovery.
        previous_root = legacy.STATE_ROOT
        try:
            legacy.STATE_ROOT = SOURCE_RECOVERY_ROOT
            if os.path.lexists(legacy.state_path(mid)):
                raise PullMigrationError(
                    "17-site source freeze prior attempt retained"
                )
        finally:
            legacy.STATE_ROOT = previous_root
    previous = legacy.STATE_ROOT
    legacy.STATE_ROOT = SOURCE_RECOVERY_ROOT
    state = {
        "schema": legacy.SCHEMA,
        "migration_id": mid,
        "status": "SOURCE_FREEZE_RUNNING",
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "sites": control.get("sites", []),
        "pending_system_cron": control.get("pending_system_cron", []),
        "pending_user_cron": control.get("pending_user_cron", []),
        "pending_pm2": control.get("pending_pm2", []),
        "source_nginx_frozen": False,
        "source_still_live": True,
        "source_delete_allowed": False,
        "dns_changed_by_p07": False,
        "secrets_emitted": False,
    }
    # Once an owned source recovery record exists, a partial stop of Cron,
    # PM2, or Nginx must trigger the recorded inverse operations. The caller
    # only receives a generic result, never a raw command/secret exception.
    recovery_initialized = False
    try:
        recovery = legacy.state_path(mid)
        if recovery.is_file():
            try:
                state = legacy.load_state(mid)
            except legacy.ServerMigrationError as exc:
                raise PullMigrationError("old-server recovery state is invalid") from exc
        else:
            legacy.save_state(state)
        recovery_initialized = True
        legacy.freeze_source_runtime(state)
        state["status"] = "SOURCE_FROZEN"
        legacy.save_state(state)
    except Exception:
        if not recovery_initialized:
            raise PullMigrationError("old-server freeze preflight failed") from None
        restored = False
        try:
            restored = legacy.restore_source_runtime(state) is True
        except Exception:
            pass
        state["status"] = (
            "SOURCE_FREEZE_FAILED_RESTORED" if restored
            else "SOURCE_FREEZE_FAILED_RECOVERY_REQUIRED"
        )
        try:
            legacy.save_state(state)
        except Exception:
            restored = False
        if restored:
            raise PullMigrationError("old-server freeze failed; source restored") from None
        raise PullMigrationError(
            "old-server freeze failed; source recovery required"
        ) from None
    finally:
        legacy.STATE_ROOT = previous
    return {
        "status": "SOURCE_FROZEN",
        "migration_id": mid,
        "dns_changed": False,
        "source_deleted": False,
        "secrets_emitted": False,
    }



def source_frozen_readback(mid: str) -> dict[str, Any]:
    """Read-only original old-server 17-site stop evidence; NOT a DB fence.

    Never infer status from CP2 journal alone after an SSH timeout. The
    original source retains its own durable recovery record and must still
    have inactive Nginx before allowing a private frozen SQL copy.
    """
    if (not SAFE_ID_RE.fullmatch(mid)
            or not mid.startswith("pull-p07-17sites-")):
        raise PullMigrationError("17_SITE_SOURCE_RECOVERY_ID_UNVERIFIED")
    previous = legacy.STATE_ROOT
    try:
        legacy.STATE_ROOT = SOURCE_RECOVERY_ROOT
        try:
            state = legacy.load_state(mid)
        except legacy.ServerMigrationError:
            raise PullMigrationError(
                "17_SITE_SOURCE_FREEZE_RECEIPT_UNAVAILABLE") from None
        sites = state.get("sites")
        pending_sys = state.get("pending_system_cron")
        pending_user = state.get("pending_user_cron")
        pending_pm2 = state.get("pending_pm2")
        if (state.get("status") != "SOURCE_FROZEN"
                or state.get("migration_id") != mid
                or state.get("source_nginx_frozen") is not True
                or state.get("source_still_live") is not False
                or state.get("source_delete_allowed") is not False
                or state.get("dns_changed_by_p07") is not False
                or not isinstance(sites, list) or len(sites) != 17
                or not isinstance(pending_sys, list)
                or not isinstance(pending_user, list)
                or not isinstance(pending_pm2, list)):
            raise PullMigrationError(
                "17_SITE_SOURCE_FREEZE_STATE_NOT_PROVEN")
        validate_seventeen_site_source_freeze_control(
            {
                "sites": sites,
                "pending_system_cron": pending_sys,
                "pending_user_cron": pending_user,
                "pending_pm2": pending_pm2,
            }, check_live_source_files=False,
        )
        saved_sys = state.get("source_system_cron_saved")
        saved_users = state.get("source_user_cron_saved")
        saved_pm2 = state.get("source_pm2_stopped")
        if (not isinstance(saved_sys, list)
                or not isinstance(saved_users, list)
                or not isinstance(saved_pm2, list)
                or len(saved_sys) != len(pending_sys)
                or len(saved_users) != len(pending_user)
                or len(saved_pm2) != len(pending_pm2)
                or any(not isinstance(r, dict) for r in
                       (*saved_sys, *saved_users, *saved_pm2))
                or {r.get("source_path") for r in saved_sys} !=
                   {r.get("source_path") for r in pending_sys}
                or {r.get("user") for r in saved_users} !=
                   {r.get("user") for r in pending_user}
                or {r.get("user") for r in saved_pm2} !=
                   {r.get("user") for r in pending_pm2}
                or not all(r.get("disabled") is True for r in saved_sys)
                or not all(
                    r.get("disabled") is True or r.get("existed") is False
                    for r in saved_users)
                or not all(r.get("stopped") is True for r in saved_pm2)):
            raise PullMigrationError(
                "17_SITE_SOURCE_CRON_PM2_RECOVERY_NOT_PROVEN")
        try:
            proc = legacy.run_local(
                ["systemctl", "is-active", "nginx"],
                timeout=30, check=False,
            )
        except legacy.ServerMigrationError:
            raise PullMigrationError(
                "17_SITE_SOURCE_NGINX_LIVE_CHECK_UNAVAILABLE") from None
        if proc.returncode == 0 or proc.stdout.strip() != "inactive":
            raise PullMigrationError(
                "17_SITE_SOURCE_NGINX_NOT_INACTIVE")
        return {
            "status": "SOURCE_17_RUNTIME_STOP_READBACK_PASS_NOT_DATABASE_FENCE",
            "migration_id": mid,
            "site_count": 17,
            "cron_pm2_journal_verified": True,
            "source_nginx_inactive_verified": True,
            "source_business_writers_all_fenced": False,
            "source_final_sql_data_parity": False,
            "cutover_allowed": False,
            "writes_performed": False,
        }
    finally:
        legacy.STATE_ROOT = previous

def source_restore(mid: str) -> dict[str, Any]:
    previous = legacy.STATE_ROOT
    legacy.STATE_ROOT = SOURCE_RECOVERY_ROOT
    try:
        try:
            state = legacy.load_state(mid)
        except legacy.ServerMigrationError as exc:
            raise PullMigrationError("old-server recovery state is unavailable") from exc
        if not legacy.restore_source_runtime(state):
            raise PullMigrationError("old-server runtime recovery is partial")
        state["status"] = "SOURCE_RESTORED"
        legacy.save_state(state)
    finally:
        legacy.STATE_ROOT = previous
    return {
        "status": "SOURCE_RESTORED",
        "migration_id": mid,
        "dns_changed": False,
        "source_deleted": False,
        "secrets_emitted": False,
    }


def add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-ip", required=True)
    parser.add_argument("--source-host")
    parser.add_argument("--ssh-user", default="root")
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument("--identity-file")
    parser.add_argument("--managed-identity-file", action="store_true")
    parser.add_argument("--ssh", default=os.environ.get("VFOPS_SSH", "ssh"))
    parser.add_argument("--site", action="append", default=[])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P07 target-owned server migration: current server pulls old server"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    target_status = sub.add_parser("target-status")
    target_status.add_argument("--bootstrap-preflight", action="store_true")

    bootstrap = sub.add_parser("bootstrap-local")
    bootstrap.add_argument("--confirm", required=True)

    plan = sub.add_parser("plan")
    add_source_args(plan)
    plan.add_argument("--confirm-source-helper-staging", default="")

    prepare = sub.add_parser("prepare")
    add_source_args(prepare)
    prepare.add_argument("--confirm", required=True)

    resume = sub.add_parser("resume")
    resume.add_argument("--migration-id", required=True)

    resume_adopted = sub.add_parser("resume-verified-adoption")
    resume_adopted.add_argument("--migration-id", required=True)
    resume_adopted.add_argument("--domain", required=True)
    resume_adopted.add_argument("--confirm", required=True)

    chain_tail = sub.add_parser("chain-tail-prepare")
    chain_tail.add_argument("--parent-migration-id", required=True)
    chain_tail.add_argument("--child-migration-id", required=True)
    chain_tail.add_argument("--confirm", required=True)

    adopt = sub.add_parser("adopt-existing-guarded-db")
    adopt.add_argument("--migration-id", required=True)
    adopt.add_argument("--domain", required=True)
    adopt.add_argument("--confirm", required=True)

    chain_adopt = sub.add_parser("chain-adopt-db-proof")
    chain_adopt.add_argument("--parent-migration-id", required=True)
    chain_adopt.add_argument("--child-migration-id", required=True)

    chain_sql = sub.add_parser("chain-sql-diagnose")
    chain_sql.add_argument("--parent-migration-id", required=True)
    chain_sql.add_argument("--child-migration-id", required=True)

    chain_plan = sub.add_parser("chain-recovery-plan")
    chain_plan.add_argument("--parent-migration-id", required=True)
    chain_plan.add_argument("--child-migration-id", required=True)

    consolidation = sub.add_parser("chain-consolidation-proof")
    consolidation.add_argument("--parent-migration-id", required=True)
    consolidation.add_argument("--child-migration-id", required=True)
    consolidation.add_argument("--tail-migration-id", required=True)
    consolidation.add_argument("--verify-target-markers", action="store_true")
    consolidation.add_argument("--locked-candidate-id", default=None)


    execution_scope = sub.add_parser("chain-execution-scope")
    execution_scope.add_argument("--parent-migration-id", required=True)
    execution_scope.add_argument("--child-migration-id", required=True)
    execution_scope.add_argument("--tail-migration-id", required=True)

    delivered = sub.add_parser("chain-17site-delivery")
    delivered.add_argument("--parent-migration-id", required=True)
    delivered.add_argument("--child-migration-id", required=True)
    delivered.add_argument("--tail-migration-id", required=True)
    delivered.add_argument("--action", choices=(
        "status", "private-prestage", "verify-private", "pause-preview",
        "paused-db-copy", "verify-paused-dbs"), default="status")
    delivered.add_argument("--confirm")

    resource_stage = sub.add_parser("chain-private-resource-warm-stage")
    resource_stage.add_argument("--parent-migration-id", required=True)
    resource_stage.add_argument("--child-migration-id", required=True)
    resource_stage.add_argument("--tail-migration-id", required=True)
    resource_stage.add_argument("--confirm", required=True)

    resource_verify = sub.add_parser("chain-private-resource-warm-verify")
    resource_verify.add_argument("--parent-migration-id", required=True)
    resource_verify.add_argument("--child-migration-id", required=True)
    resource_verify.add_argument("--tail-migration-id", required=True)

    resource_types = sub.add_parser("chain-source-resource-types")
    resource_types.add_argument("--parent-migration-id", required=True)
    resource_types.add_argument("--child-migration-id", required=True)
    resource_types.add_argument("--tail-migration-id", required=True)
    resource_types.add_argument("--verify-live-source", action="store_true")

    warm_stage = sub.add_parser("chain-private-file-warm-stage")
    warm_stage.add_argument("--parent-migration-id", required=True)
    warm_stage.add_argument("--child-migration-id", required=True)
    warm_stage.add_argument("--tail-migration-id", required=True)
    warm_stage.add_argument("--confirm", required=True)

    warm_verify = sub.add_parser("chain-private-file-warm-verify")
    warm_verify.add_argument("--parent-migration-id", required=True)
    warm_verify.add_argument("--child-migration-id", required=True)
    warm_verify.add_argument("--tail-migration-id", required=True)

    prestage = sub.add_parser("chain-prestage-three-source-dumps")
    prestage.add_argument("--parent-migration-id", required=True)
    prestage.add_argument("--child-migration-id", required=True)
    prestage.add_argument("--tail-migration-id", required=True)
    prestage.add_argument("--confirm", required=True)

    original_db = sub.add_parser("chain-db-readiness")
    original_db.add_argument("--parent-migration-id", required=True)
    original_db.add_argument("--child-migration-id", required=True)
    original_db.add_argument("--tail-migration-id", required=True)
    original_db.add_argument("--verify-original-markers",
                             action="store_true")

    remainder_plan = sub.add_parser("remainder-plan")
    remainder_plan.add_argument("--migration-id", required=True)

    remainder_prepare = sub.add_parser("remainder-prepare")
    remainder_prepare.add_argument("--migration-id", required=True)
    remainder_prepare.add_argument("--confirm", required=True)

    cut = sub.add_parser("cutover")
    cut.add_argument("--migration-id", required=True)
    cut.add_argument("--confirm", required=True)

    final = sub.add_parser("finalize")
    final.add_argument("--migration-id", required=True)
    final.add_argument("--confirm", required=True)
    final.add_argument("--attempts", type=int, default=12)
    final.add_argument("--delay", type=float, default=5.0)

    rollback = sub.add_parser("rollback")
    rollback.add_argument("--migration-id", required=True)
    rollback.add_argument("--confirm", required=True)

    recover = sub.add_parser("recovery-evidence")
    recover.add_argument("--source-package", type=Path, required=True)
    recover.add_argument("--target-package", type=Path, required=True)
    recover.add_argument("--site", required=True)

    offline = sub.add_parser("recovery-literal-review")
    offline.add_argument("--source-package", type=Path, required=True)
    offline.add_argument("--target-package", type=Path, required=True)
    offline.add_argument("--site", required=True)
    offline.add_argument("--table-ordinal", required=True, type=int)
    offline.add_argument("--private-output", type=Path)
    offline.add_argument("--confirm")

    isolated = sub.add_parser("isolated-restore")
    isolated.add_argument("--source-package", type=Path, required=True)
    isolated.add_argument("--target-package", type=Path, required=True)
    isolated.add_argument("--site", required=True)
    isolated.add_argument("--confirm", required=True)

    native = sub.add_parser("native-restore")
    native.add_argument("--source-package", type=Path, required=True)
    native.add_argument("--target-package", type=Path, required=True)
    native.add_argument("--site", required=True)
    native.add_argument("--confirm", required=True)

    quarantined = sub.add_parser("scratch-restore-quarantined")
    quarantined.add_argument("--source-package", type=Path, required=True)
    quarantined.add_argument("--target-package", type=Path, required=True)
    quarantined.add_argument("--site", required=True)
    quarantined.add_argument("--confirm", required=True)

    diagnose = sub.add_parser("diagnose-sql")
    diagnose.add_argument("--migration-id", required=True)
    diagnose.add_argument("--domain", required=True)
    diagnose.add_argument("--expected-source-tables", type=int, default=None)

    status = sub.add_parser("status")
    status.add_argument("--migration-id", required=True)

    nginx_status = sub.add_parser("source-nginx-status")
    add_source_args(nginx_status)

    nginx_start = sub.add_parser("source-nginx-start")
    add_source_args(nginx_start)
    nginx_start.add_argument("--confirm", required=True)

    nginx_stop = sub.add_parser("source-nginx-stop")
    add_source_args(nginx_stop)
    nginx_stop.add_argument("--confirm", required=True)

    local_status = sub.add_parser("local-nginx-status")

    local_start = sub.add_parser("local-nginx-start")
    local_start.add_argument("--confirm", required=True)

    local_stop = sub.add_parser("local-nginx-stop")
    local_stop.add_argument("--confirm", required=True)

    source_plan = sub.add_parser("_source-plan")
    source_plan.add_argument("--site", action="append", default=[])

    snap = sub.add_parser("_source-snapshot-sqlite")
    snap.add_argument("--source", required=True)
    snap.add_argument("--output", required=True)

    export_db = sub.add_parser("_source-export-db")
    export_db.add_argument("--database", required=True)
    export_db.add_argument("--output", required=True)

    freeze = sub.add_parser("_source-freeze")
    freeze.add_argument("--migration-id", required=True)
    freeze.add_argument("--control", required=True)
    freeze.add_argument("--require-fresh", action="store_true")
    freeze.add_argument("--expected-site-count", type=int)
    freeze.add_argument("--expected-control-sha256")

    restore = sub.add_parser("_source-restore")
    restore.add_argument("--migration-id", required=True)
    readback = sub.add_parser("_source-frozen-readback")
    readback.add_argument("--migration-id", required=True)

    args = parser.parse_args()
    try:
        if args.command == "target-status":
            if cloudpanel_ready_local() and cloudpanel_database_server_ready_local():
                result = {
                    "schema": SCHEMA,
                    "status": "CLOUDPANEL_READY",
                    "current_server_role": "RECEIVER",
                    "writes_performed": False,
                }
            elif cloudpanel_ready_local() and cloudpanel_user_count_local() == 0:
                result = {
                    "schema": SCHEMA,
                    "status": "CLOUDPANEL_ADMIN_REQUIRED",
                    "current_server_role": "RECEIVER",
                    "first_admin_required": True,
                    "writes_performed": False,
                }
            elif cloudpanel_ready_local():
                result = {
                    "schema": SCHEMA,
                    "status": "CLOUDPANEL_INCOMPLETE_DATABASE_SERVER",
                    "current_server_role": "RECEIVER",
                    "writes_performed": False,
                }
            elif args.bootstrap_preflight:
                result = local_bootstrap_preflight()
            else:
                result = {
                    "schema": SCHEMA,
                    "status": "CLOUDPANEL_MISSING",
                    "current_server_role": "RECEIVER",
                    "writes_performed": False,
                }
        elif args.command == "bootstrap-local":
            result = bootstrap_local_cloudpanel(args.confirm)
        elif args.command == "plan":
            result = plan_payload(
                source_from_args(args), args.site, args.confirm_source_helper_staging
            )
        elif args.command == "prepare":
            result = summary(prepare_migration(
                source_from_args(args), args.site, args.confirm
            ))
        elif args.command == "resume":
            result = summary(resume_prepare_migration(args.migration_id))
        elif args.command == "resume-verified-adoption":
            result = summary(resume_after_verified_adoption(
                args.migration_id, args.domain, args.confirm,
            ))
        elif args.command == "chain-tail-prepare":
            result = summary(prepare_chain_tail(
                args.parent_migration_id, args.child_migration_id,
                args.confirm,
            ))
        elif args.command == "adopt-existing-guarded-db":
            result = adopt_existing_guarded_site(
                args.migration_id, args.domain, args.confirm
            )
        elif args.command == "chain-adopt-db-proof":
            result = chain_adopt_database_proof(
                args.parent_migration_id, args.child_migration_id
            )
        elif args.command == "chain-sql-diagnose":
            result = diagnose_chain_sql(
                args.parent_migration_id, args.child_migration_id
            )
        elif args.command == "chain-recovery-plan":
            result = chain_recovery_scope(
                args.parent_migration_id, args.child_migration_id
            )
        elif args.command == "chain-consolidation-proof":
            result = consolidated_chain_scope(
                args.parent_migration_id, args.child_migration_id,
                args.tail_migration_id,
                verify_target_markers=args.verify_target_markers,
                locked_candidate_id=args.locked_candidate_id,
            )

        elif args.command == "chain-execution-scope":
            result = chain_execution_scope(
                args.parent_migration_id, args.child_migration_id,
                args.tail_migration_id,
            )
        elif args.command == "chain-17site-delivery":
            result = chain_seventeen_site_delivery(
                args.parent_migration_id, args.child_migration_id,
                args.tail_migration_id, action=args.action,
                confirm=args.confirm,
            )
        elif args.command == "chain-private-resource-warm-stage":
            result = chain_private_resource_warm_stage(
                args.parent_migration_id, args.child_migration_id,
                args.tail_migration_id, confirm=args.confirm,
            )
        elif args.command == "chain-private-resource-warm-verify":
            result = chain_private_resource_warm_stage(
                args.parent_migration_id, args.child_migration_id,
                args.tail_migration_id, verify_only=True,
            )
        elif args.command == "chain-source-resource-types":
            result = chain_original_resource_type_readiness(
                args.parent_migration_id, args.child_migration_id,
                args.tail_migration_id,
                verify_live_source=args.verify_live_source,
            )
        elif args.command == "chain-private-file-warm-stage":
            result = chain_private_file_warm_stage(
                args.parent_migration_id, args.child_migration_id,
                args.tail_migration_id, confirm=args.confirm,
            )
        elif args.command == "chain-private-file-warm-verify":
            result = chain_private_file_warm_stage(
                args.parent_migration_id, args.child_migration_id,
                args.tail_migration_id, verify_only=True,
            )
        elif args.command == "chain-prestage-three-source-dumps":
            result = chain_prestage_three_source_dumps(
                args.parent_migration_id,
                args.child_migration_id,
                args.tail_migration_id,
                confirm=args.confirm,
            )
        elif args.command == "chain-db-readiness":
            result = chain_original_database_readiness(
                args.parent_migration_id, args.child_migration_id,
                args.tail_migration_id,
                verify_original_markers=args.verify_original_markers,
            )
        elif args.command == "remainder-plan":
            result = remainder_scope(args.migration_id)
        elif args.command == "remainder-prepare":
            result = summary(prepare_remainder(args.migration_id, args.confirm))
        elif args.command == "cutover":
            result = summary(cutover_migration(args.migration_id, args.confirm))
        elif args.command == "finalize":
            result = summary(finalize_migration(
                args.migration_id,
                args.confirm,
                attempts=args.attempts,
                delay=args.delay,
            ))
        elif args.command == "rollback":
            result = summary(rollback_migration(args.migration_id, args.confirm))
        elif args.command == "recovery-evidence":
            result = private_recovery_gate.evaluate(
                args.source_package, args.target_package, args.site
            )
        elif args.command == "recovery-literal-review":
            # No SSH, database connections, SQL execution or migration state.
            # Private artifact output must be explicitly opted into and is
            # exclusive local plaintext only. stdout is always redacted.
            result = private_sql_literal_reconcile.evaluate(
                args.source_package, args.target_package, args.site,
                args.table_ordinal, private_output=args.private_output,
                confirm=args.confirm,
            )
        elif args.command == "isolated-restore":
            result = isolated_db_restore.rehearse(
                args.source_package, args.target_package, args.site, args.confirm
            )
        elif args.command == "native-restore":
            result = native_scratch_restore.rehearse(
                args.source_package, args.target_package, args.site, args.confirm
            )
        elif args.command == "scratch-restore-quarantined":
            result = native_scratch_restore.rehearse_quarantined(
                args.source_package, args.target_package, args.site, args.confirm
            )
        elif args.command == "diagnose-sql":
            result = diagnose_sql_difference(
                args.migration_id, args.domain,
                expected_source_tables=args.expected_source_tables,
            )
        elif args.command == "status":
            result = summary(load_state(args.migration_id))
        elif args.command == "source-nginx-status":
            result = source_nginx_status(source_from_args(args))
        elif args.command == "source-nginx-start":
            result = source_nginx_start(source_from_args(args), args.confirm)
        elif args.command == "source-nginx-stop":
            result = source_nginx_stop(source_from_args(args), args.confirm)
        elif args.command == "local-nginx-status":
            result = local_nginx_status()
        elif args.command == "local-nginx-start":
            result = local_nginx_start(args.confirm)
        elif args.command == "local-nginx-stop":
            result = local_nginx_stop(args.confirm)
        elif args.command == "_source-plan":
            result = source_plan_local(args.site)
        elif args.command == "_source-snapshot-sqlite":
            result = source_snapshot_sqlite(Path(args.source), Path(args.output))
        elif args.command == "_source-export-db":
            result = source_export_db(args.database, Path(args.output))
        elif args.command == "_source-freeze":
            result = source_freeze(
                args.migration_id, Path(args.control),
                require_fresh=args.require_fresh,
                expected_site_count=args.expected_site_count,
                expected_control_sha256=args.expected_control_sha256,
            )
        elif args.command == "_source-restore":
            result = source_restore(args.migration_id)
        elif args.command == "_source-frozen-readback":
            result = source_frozen_readback(args.migration_id)
        else:
            raise PullMigrationError("unsupported command")
    except (
        PullMigrationError,
        legacy.ServerMigrationError,
        cloudpanel.CloudPanelError,
        transport.TransportError,
        OSError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 13
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.command == "recovery-literal-review" and (
        result.get("status") != "PRIVATE_SQL_LITERALS_CAPTURED_NOT_RESTORED"
        or result.get("data_writes_allowed") is not False
        or result.get("migration_resume_allowed") is not False
        or result.get("cutover_allowed") is not False
    ):
        return 13
    if args.command == "scratch-restore-quarantined" and not (
        result.get("scratch_imports_completed") is True
        and result.get("cutover_allowed") is False
        and result.get("actual_source_restore_verified") is False
        and result.get("actual_target_restore_verified") is False
    ):
        return 13
    if args.command == "native-restore" and not (
        result.get("actual_source_restore_verified") is True
        and result.get("actual_target_restore_verified") is True
    ):
        return 13
    if args.command == "isolated-restore" and not (
        result.get("actual_source_restore_verified") is True
        and result.get("actual_target_restore_verified") is True
    ):
        return 13
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
