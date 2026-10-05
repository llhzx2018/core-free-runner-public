#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any

import cloudpanel
import cutover
import inventory
import package as package_engine
import server_migration as legacy
import transport
import verify as verify_engine

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


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def progress_note(message: str) -> None:
    if os.environ.get("VFOPS_MIGRATION_PROGRESS") == "1":
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
        f"rm -rf -- {shlex.quote(runtime)}; "
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
) -> subprocess.CompletedProcess[str]:
    command = [
        "env",
        f"PYTHONPATH={runtime}/lib",
        "python3",
        f"{runtime}/lib/server_migration_pull.py",
        *args,
    ]
    rendered = " ".join(shlex.quote(item) for item in command)
    return source_remote(source, rendered, timeout=timeout)


def cleanup_probe_runtime(source: dict[str, Any], runtime: str) -> None:
    root = str(Path(runtime).parent)
    if root.startswith("/var/lib/vf-server-ops/pull-source/probe-"):
        source_remote(source, f"rm -rf -- {shlex.quote(root)}", timeout=120, check=False)


def source_probe(source: dict[str, Any], domains: list[str]) -> dict[str, Any]:
    token = "probe-" + hashlib.sha256(
        f"{source['host']}:{source['ssh_port']}".encode()
    ).hexdigest()[:16]
    runtime = stage_source_runtime(source, token)
    try:
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
    if (os_id, version_id) not in legacy.SUPPORTED_BOOTSTRAP_OS:
        raise PullMigrationError(f"unsupported OS for CloudPanel: {os_id} {version_id}")
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
        "writes_performed": False,
    }


def bootstrap_local_cloudpanel(confirm: str) -> dict[str, Any]:
    if confirm != "BOOTSTRAP_LOCAL_CLOUDPANEL":
        raise PullMigrationError("explicit confirmation required: BOOTSTRAP_LOCAL_CLOUDPANEL")
    preflight = local_bootstrap_preflight()
    cloud_hint = "" if preflight["cloud_hint"] == "generic" else str(preflight["cloud_hint"])
    script = legacy.cloudpanel_bootstrap_script(cloud_hint)
    proc = subprocess.run(
        ["bash", "-lc", script],
        text=True,
        capture_output=True,
        check=False,
        timeout=5400,
    )
    if proc.returncode != 0 or not cloudpanel_ready_local():
        raise PullMigrationError("CloudPanel installation on current server failed")
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
    )
    if proc.returncode != 0:
        raise PullMigrationError(f"old-server MySQL export failed: {database}")


def compare_database_dumps(source_dump: Path, target_dump: Path) -> str:
    try:
        before, before_count = verify_engine.sql_fingerprint(source_dump)
        after, after_count = verify_engine.sql_fingerprint(target_dump)
        if before == after and before_count == after_count:
            return "CANONICAL_SQL_EXACT"
        if (
            verify_engine.sql_data_fingerprint(source_dump)
            == verify_engine.sql_data_fingerprint(target_dump)
        ):
            return "CROSS_ENGINE_LOGICAL_CONTENT"
    except verify_engine.RestoreVerifyError as exc:
        raise PullMigrationError("MySQL verification failed") from exc
    raise PullMigrationError("MySQL logical-content verification failed")


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
        try:
            phase_cn = "最终同步" if phase == "final" else "首轮迁入"
            progress_note(f"{phase_cn} MySQL · 正在导出 {database}")
            source_export_database(state, database, remote_dump)
            progress_note(f"{phase_cn} MySQL · 正在传输 {database}")
            pull_path(state["source"], remote_dump, source_dump)
            shutil.copy2(source_dump, import_dump)
            progress_note(f"{phase_cn} MySQL · 正在导入 {database}")
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
        finally:
            source_remote(
                state["source"],
                f"rm -f -- {shlex.quote(remote_dump)}",
                timeout=60,
                check=False,
            )
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


def sync_external_assets(state: dict[str, Any], *, final: bool) -> list[str]:
    synced: list[str] = []
    for row in state.get("external_assets", []):
        if not isinstance(row, dict):
            continue
        source_path = str(row["path"])
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


def sync_sqlite_assets(state: dict[str, Any], *, phase: str) -> int:
    count = 0
    work = state_dir(state["migration_id"]) / "sqlite" / phase
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    for row in state.get("sqlite_assets", []):
        if not isinstance(row, dict):
            continue
        source_path = str(row["path"])
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


def target_smoke(state: dict[str, Any]) -> dict[str, Any]:
    manifest = inventory.build_manifest(Path("/"))
    site_map = {
        str(row.get("domain")): row
        for row in manifest.get("sites", [])
        if isinstance(row, dict)
    }
    passed = failed = 0
    failures: list[dict[str, Any]] = []
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
        proc = run_local([
            "curl", "-kLsS", "--connect-timeout", "10", "--max-time", "30",
            "--resolve", f"{domain}:443:127.0.0.1",
            "-o", "/dev/null", "-w", "%{http_code}",
            f"https://{domain}/",
        ], timeout=45, check=False)
        code = proc.stdout.strip()[-3:]
        # Pre-DNS local smoke proves vhost/runtime reachability, not application
        # business semantics. A deliberate 401/403/404 still proves that Nginx
        # routed the request to the migrated site. 5xx/000 remain hard failures.
        if proc.returncode == 0 and code.isdigit() and 200 <= int(code) < 500:
            passed += 1
        else:
            failed += 1
            failures.append({
                "domain": domain,
                "reason": "LOCAL_HTTP_PROBE",
                "http_code": code if code.isdigit() else "000",
                "curl_exit": int(proc.returncode),
            })
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
    for site in state["sites"]:
        domain = str(site["domain"])
        proc = run_local([
            "curl", "-LsS", "--connect-timeout", "10", "--max-time", "30",
            "-o", "/dev/null", "-w", "%{http_code}|%{ssl_verify_result}|%{remote_ip}",
            f"https://{domain}/",
        ], timeout=45, check=False)
        parts = proc.stdout.strip().split("|", 2)
        code = parts[0] if parts else "000"
        tls = parts[1] if len(parts) > 1 else "999"
        remote_ip = parts[2] if len(parts) > 2 else ""
        ok = (
            proc.returncode == 0
            and code.isdigit()
            and 200 <= int(code) < 400
            and tls == "0"
        )
        sites.append({
            "domain": domain,
            "http_code": code,
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


def plan_payload(source: dict[str, Any], domains: list[str]) -> dict[str, Any]:
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
        "writes_performed": False,
        "secrets_emitted": False,
    }


def prepare_migration(
    source: dict[str, Any],
    domains: list[str],
    confirm: str,
) -> dict[str, Any]:
    if confirm != "PREPARE_PULL_MIGRATION":
        raise PullMigrationError("explicit confirmation required: PREPARE_PULL_MIGRATION")
    source_plan = source_probe(source, domains)
    target = target_preflight_local(source_plan)
    source_identity = str(source_plan.get("source_server_identity", "UNKNOWN"))
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
        "secrets_emitted": False,
    }
    for site in state["sites"]:
        site["stage_status"] = "PENDING"
    save_state(state)
    return resume_prepare_migration(mid)


def resume_prepare_migration(mid: str) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("status") not in {"PREPARING", "PREPARE_FAILED"}:
        raise PullMigrationError("migration is not resumable from prepare stage")
    if not cloudpanel_database_server_ready_local():
        raise PullMigrationError(
            "new-server CloudPanel database server metadata is missing; migration cannot resume safely"
        )
    state["status"] = "PREPARING"
    state.pop("last_error_class", None)
    save_state(state)
    try:
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
        state["status"] = "PREPARED"
        state["source_still_live"] = True
        state["dns_manual_gate_required"] = True
        save_state(state)
        return state
    except Exception as exc:
        state["status"] = "PREPARE_FAILED"
        state["last_error_class"] = exc.__class__.__name__
        save_state(state)
        if isinstance(exc, PullMigrationError):
            raise
        raise PullMigrationError("target-pull prepare failed") from exc


def cutover_migration(mid: str, confirm: str) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("status") not in {
        "PREPARED", "CUTOVER_RUNNING", "CUTOVER_FAILED_ROLLED_BACK"
    }:
        raise PullMigrationError("migration is not ready for final synchronization")
    if confirm != f"CUTOVER_PULL:{mid}":
        raise PullMigrationError(f"explicit confirmation required: CUTOVER_PULL:{mid}")
    state["status"] = "CUTOVER_RUNNING"
    state["cutover_started_at"] = now_utc()
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
                    if row.get("reason") == "LOCAL_HTTP_PROBE"
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
        state["status"] = "CUTOVER_PREP_READY"
        state["dns_manual_gate_required"] = True
        state["source_still_live"] = False
        save_state(state)
        return state
    except Exception as exc:
        progress_note("安全恢复 · 正在撤销新服务器临时运行任务")
        target_ok = deactivate_target_runtime(state)
        progress_note("安全恢复 · 正在恢复旧服务器运行状态")
        source_ok = restore_old_server(state)
        state["status"] = (
            "CUTOVER_FAILED_ROLLED_BACK"
            if target_ok and source_ok
            else "CUTOVER_FAILED_ROLLBACK_PARTIAL"
        )
        state["last_error_class"] = exc.__class__.__name__
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
        state["status"] = "WAITING_DNS"
        save_state(state)
        return state
    progress_note("公网验证 2/2 · 正在逐站检查 HTTPS 与正式访问状态")
    production = production_verify(state)
    state["production_verification"] = production
    if production["status"] != "PASS":
        state["status"] = "PRODUCTION_VERIFY_FAILED"
        save_state(state)
        raise PullMigrationError("public production verification failed")
    state["status"] = "PRODUCTION_PASS"
    state["production_passed_at"] = now_utc()
    state["source_retained_for_recovery"] = True
    state["source_delete_allowed"] = False
    state["dns_changed_by_p07"] = False
    state["source_helper_retained_for_recovery"] = True
    save_state(state)
    return state


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
    target_ok = deactivate_target_runtime(state)
    source_ok = restore_old_server(state)
    state["status"] = "ROLLED_BACK" if target_ok and source_ok else "ROLLBACK_PARTIAL"
    state["source_delete_allowed"] = False
    state["dns_changed_by_p07"] = False
    save_state(state)
    if not (target_ok and source_ok):
        raise PullMigrationError("rollback is partial and needs operator attention")
    return state


def summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": state.get("schema"),
        "migration_id": state.get("migration_id"),
        "status": state.get("status"),
        "direction": state.get("direction"),
        "current_server_role": state.get("current_server_role"),
        "old_server_ip": (state.get("source") or {}).get("ip"),
        "site_count": len(state.get("sites", [])),
        "mysql_final_count": state.get("mysql_final_count"),
        "sqlite_snapshot_count_prepare": state.get("sqlite_snapshot_count_prepare"),
        "sqlite_snapshot_count_final": state.get("sqlite_snapshot_count_final"),
        "target_smoke": state.get("target_smoke"),
        "public_route_proof": state.get("public_route_proof"),
        "production_verification": state.get("production_verification"),
        "dns_manual_gate_required": state.get("dns_manual_gate_required", False),
        "source_retained_for_recovery": state.get(
            "source_retained_for_recovery", False
        ),
        "old_server_external_listeners": state.get(
            "source_external_listeners", []
        ),
        "source_delete_allowed": False,
        "dns_changed_by_p07": False,
        "existing_target_overwrite_allowed": False,
        "secrets_emitted": False,
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
        paths = legacy.external_paths_for_site(site)
        site["external_paths"] = paths
        for path in paths:
            row = {"path": path, "user": user}
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
    if not str(output).startswith("/var/lib/vf-server-ops/pull-source/"):
        raise PullMigrationError("unsafe MySQL staging output")
    output.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(output.parent, 0o700)
    try:
        cloudpanel.export_database(database, output, clpctl="clpctl")
    except (cloudpanel.CloudPanelError, ValueError) as exc:
        raise PullMigrationError("MySQL export failed") from exc
    os.chmod(output, 0o600)
    return {"status": "PASS", "secrets_emitted": False}


def source_freeze(mid: str, control_path: Path) -> dict[str, Any]:
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
    try:
        recovery = legacy.state_path(mid)
        if recovery.is_file():
            try:
                state = legacy.load_state(mid)
            except legacy.ServerMigrationError as exc:
                raise PullMigrationError("old-server recovery state is invalid") from exc
        else:
            legacy.save_state(state)
        legacy.freeze_source_runtime(state)
        state["status"] = "SOURCE_FROZEN"
        legacy.save_state(state)
    except legacy.ServerMigrationError as exc:
        raise PullMigrationError("old-server freeze failed") from exc
    finally:
        legacy.STATE_ROOT = previous
    return {
        "status": "SOURCE_FROZEN",
        "migration_id": mid,
        "dns_changed": False,
        "source_deleted": False,
        "secrets_emitted": False,
    }


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

    prepare = sub.add_parser("prepare")
    add_source_args(prepare)
    prepare.add_argument("--confirm", required=True)

    resume = sub.add_parser("resume")
    resume.add_argument("--migration-id", required=True)

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

    restore = sub.add_parser("_source-restore")
    restore.add_argument("--migration-id", required=True)

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
            result = plan_payload(source_from_args(args), args.site)
        elif args.command == "prepare":
            result = summary(prepare_migration(
                source_from_args(args), args.site, args.confirm
            ))
        elif args.command == "resume":
            result = summary(resume_prepare_migration(args.migration_id))
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
            result = source_freeze(args.migration_id, Path(args.control))
        elif args.command == "_source-restore":
            result = source_restore(args.migration_id)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
