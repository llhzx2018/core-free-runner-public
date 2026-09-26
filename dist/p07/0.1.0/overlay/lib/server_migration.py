#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import subprocess
import tempfile
import time
from typing import Any

import app_config
import cloudpanel
import cutover
import inventory
import package as package_engine
import restore_apply
import runtime as runtime_engine
import site_lifecycle
import transport
import verify as verify_engine

SCHEMA = "vf-server-ops.server-migration.v1"
ROOT = Path(__file__).resolve().parents[1]
STATE_ROOT = Path(os.environ.get("VFOPS_SERVER_MIGRATION_STATE_ROOT", "/var/lib/vf-server-ops/server-migrations"))
BACKUP_ROOT = Path(os.environ.get("VFOPS_BACKUP_DIR", "/var/backups/vf-server-ops"))
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
PRUNE_DIRS = {
    ".git", "node_modules", "vendor", "cache", "caches", "tmp", "temp",
    "logs", "backups", "backup",
}
SQLITE_SUFFIXES = (".sqlite", ".sqlite3", ".db", ".sq3")
SQLITE_HEADER = b"SQLite format 3\x00"
# Pinned from CloudPanel's official installer documentation on 2026-09-24.
# A future P07 release must deliberately update the checksum; runtime never
# executes an unverified remote installer.
CLOUDPANEL_INSTALLER_URL = "https://installer.cloudpanel.io/ce/v2/install.sh"
CLOUDPANEL_INSTALLER_SHA256 = "8146dbe0a488e7088b04071b0c34d59aa0ab1fe9dcec382d395fd155c9e6c476"
CLOUDPANEL_BOOTSTRAP_DB_ENGINE = "MYSQL_8.4"
CLOUDPANEL_MIN_CORES = 1
# MemTotal is lower than provider-advertised RAM because firmware/kernel reserve
# some memory; accept a genuine 2 GB class VM without weakening the product floor.
CLOUDPANEL_MIN_MEMORY_BYTES = 1_900_000_000
CLOUDPANEL_MIN_DISK_BYTES = 10 * 1024**3
SUPPORTED_BOOTSTRAP_ARCH = {"x86_64", "aarch64", "arm64"}
SUPPORTED_BOOTSTRAP_OS = {
    ("ubuntu", "22.04"),
    ("ubuntu", "24.04"),
    ("ubuntu", "26.04"),
    ("debian", "12"),
    ("debian", "13"),
}

PROTECTED_DB_CONFIGS = (
    "wp-config.php",
    "public/wp-config.php",
    ".env",
    ".env.local",
    ".env.production",
    ".env.prod",
    "public/.env",
    "public/.env.local",
    "public/.env.production",
    "public/.env.prod",
)


class ServerMigrationError(RuntimeError):
    pass


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def migration_id(source_hash: str, target_ip: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    token = hashlib.sha256(f"{source_hash}:{target_ip}:{stamp}".encode()).hexdigest()[:8]
    return f"server-{stamp}-{token}"


def state_dir(mid: str) -> Path:
    if not SAFE_ID_RE.fullmatch(mid):
        raise ServerMigrationError("invalid migration id")
    return STATE_ROOT / mid


def state_path(mid: str) -> Path:
    return state_dir(mid) / "state.json"


def atomic_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temp_name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = now_utc()
    atomic_private_json(state_path(str(state["migration_id"])), state)


def load_state(mid: str) -> dict[str, Any]:
    path = state_path(mid)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ServerMigrationError("migration state is unavailable or invalid") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ServerMigrationError("unsupported migration state")
    return payload


def run_local(args: list[str], *, timeout: int = 3600, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(args, text=True, capture_output=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ServerMigrationError(f"local command unavailable: {args[0]}") from exc
    if check and proc.returncode != 0:
        raise ServerMigrationError(f"local command failed: {args[0]}")
    return proc


def target_base(state: dict[str, Any]) -> list[str]:
    target = state["target"]
    identity = Path(target["identity_file"]) if target.get("identity_file") else None
    return transport.ssh_base(
        target.get("ssh", "ssh"),
        target["host"],
        target["ssh_user"],
        int(target["ssh_port"]),
        identity,
    )


def remote(state: dict[str, Any], command: str, *, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    target = state["target"]
    proc = transport.run_ssh(
        target_base(state),
        transport.remote_priv(target["ssh_user"], command),
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise ServerMigrationError("target command failed")
    return proc


def rsync_ssh_command(state: dict[str, Any]) -> str:
    target = state["target"]
    parts = [
        target.get("ssh", "ssh"),
        "-p", str(target["ssh_port"]),
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=2",
    ]
    if target.get("identity_file"):
        parts.extend(["-i", str(Path(target["identity_file"]).expanduser().resolve())])
    return shlex.join(parts)


def rsync_to_target(
    state: dict[str, Any],
    source: Path,
    destination: str,
    *,
    user: str | None = None,
    delete: bool = False,
    excludes: tuple[str, ...] = (),
) -> None:
    if not source.exists():
        raise ServerMigrationError(f"source path disappeared during migration: {source}")
    args = ["rsync", "-aH", "--partial", "--info=stats2"]
    if delete:
        args.append("--delete-delay")
    if user:
        group = remote(state, f"id -gn {shlex.quote(user)}", timeout=30).stdout.strip()
        if not group or any(ch.isspace() for ch in group):
            raise ServerMigrationError("target site group cannot be resolved")
        args.append(f"--chown={user}:{group}")
    for item in excludes:
        args.append(f"--exclude={item}")
    args.extend([
        "-e", rsync_ssh_command(state),
        str(source) + ("/" if source.is_dir() else ""),
        f"{state['target']['ssh_user']}@{state['target']['host']}:{destination}",
    ])
    run_local(args, timeout=7200)


def parse_os_release(text: str) -> tuple[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values.get("ID", "").lower(), values.get("VERSION_ID", "")


def detect_cloud_hint(text: str) -> str:
    value = text.lower()
    if "digitalocean" in value:
        return "do"
    if "amazon" in value or "ec2" in value:
        return "aws"
    if "google" in value:
        return "gce"
    if "microsoft" in value or "azure" in value:
        return "msa"
    if "hetzner" in value:
        return "hetzner"
    if "oracle" in value:
        return "oci"
    return ""


def cloudpanel_bootstrap_script(cloud_hint: str) -> str:
    cloud_env = f"CLOUD={shlex.quote(cloud_hint)} " if cloud_hint else ""
    return (
        "set -euo pipefail; "
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update; "
        "apt-get -y upgrade; "
        "apt-get -y install curl wget sudo rsync cron; "
        f"curl -fSsS {shlex.quote(CLOUDPANEL_INSTALLER_URL)} -o /root/cloudpanel-install.sh; "
        f"echo {shlex.quote(CLOUDPANEL_INSTALLER_SHA256 + '  /root/cloudpanel-install.sh')} | sha256sum -c -; "
        f"{cloud_env}DB_ENGINE={shlex.quote(CLOUDPANEL_BOOTSTRAP_DB_ENGINE)} "
        "bash /root/cloudpanel-install.sh; "
        "rm -f /root/cloudpanel-install.sh; "
        "command -v clpctl >/dev/null 2>&1; "
        "test -f /home/clp/htdocs/app/data/db.sq3; "
        "clpctl --version >/dev/null 2>&1"
    )


def target_bootstrap_preflight(target: dict[str, Any]) -> dict[str, Any]:
    base = target_base({"target": target})
    os_proc = transport.run_ssh(
        base,
        transport.remote_priv(target["ssh_user"], "cat /etc/os-release"),
        timeout=30,
    )
    if os_proc.returncode != 0:
        raise ServerMigrationError("target OS cannot be identified")

    os_id, version_id = parse_os_release(os_proc.stdout)
    if (os_id, version_id) not in SUPPORTED_BOOTSTRAP_OS:
        raise ServerMigrationError(
            "target OS is not supported for guarded CloudPanel bootstrap: "
            f"{os_id} {version_id}"
        )

    resource_cmd = (
        "set -eu; "
        "arch=$(uname -m); "
        "cores=$(nproc); "
        "mem_kb=$(awk '/MemTotal:/ {print $2}' /proc/meminfo); "
        "disk=$(df -B1 --output=size / | tail -n 1 | tr -d ' '); "
        "printf '%s|%s|%s|%s' \"$arch\" \"$cores\" \"$mem_kb\" \"$disk\""
    )
    resource_proc = transport.run_ssh(
        base,
        transport.remote_priv(target["ssh_user"], resource_cmd),
        timeout=30,
    )
    if resource_proc.returncode != 0:
        raise ServerMigrationError(
            "target CloudPanel resource requirements cannot be determined"
        )

    parts = resource_proc.stdout.strip().split("|", 3)
    if len(parts) != 4:
        raise ServerMigrationError(
            "target CloudPanel resource result is invalid"
        )
    arch = parts[0].strip()
    try:
        cores = int(parts[1])
        memory_bytes = int(parts[2]) * 1024
        disk_bytes = int(parts[3])
    except ValueError as exc:
        raise ServerMigrationError(
            "target CloudPanel resource result is invalid"
        ) from exc

    if arch not in SUPPORTED_BOOTSTRAP_ARCH:
        raise ServerMigrationError(
            f"target architecture is unsupported: {arch}"
        )
    if cores < CLOUDPANEL_MIN_CORES:
        raise ServerMigrationError(
            "target CPU is below CloudPanel minimum requirements"
        )
    if memory_bytes < CLOUDPANEL_MIN_MEMORY_BYTES:
        raise ServerMigrationError(
            "target memory is below CloudPanel minimum requirements"
        )
    if disk_bytes < CLOUDPANEL_MIN_DISK_BYTES:
        raise ServerMigrationError(
            "target disk is below CloudPanel minimum requirements"
        )

    guard = (
        "set -eu; "
        "command -v ss >/dev/null 2>&1; "
        "! command -v nginx >/dev/null 2>&1; "
        "! command -v apache2 >/dev/null 2>&1; "
        "! command -v mysql >/dev/null 2>&1; "
        "! command -v mariadb >/dev/null 2>&1; "
        "test ! -e /etc/nginx; "
        "test ! -e /etc/apache2; "
        "test ! -e /home/clp; "
        "test ! -e /home/mysql; "
        "test ! -e /var/lib/mysql; "
        "test ! -e /var/lib/mariadb; "
        "! ss -ltnH | awk '{print $4}' | grep -Eq '(^|:)(80|443)$'; "
        "found=0; "
        "for p in /home/*/htdocs/*; do [ ! -e \"$p\" ] || found=1; done; "
        "[ \"$found\" -eq 0 ]"
    )
    guard_proc = transport.run_ssh(
        base,
        transport.remote_priv(target["ssh_user"], guard),
        timeout=30,
    )
    if guard_proc.returncode != 0:
        raise ServerMigrationError(
            "target is not empty enough for automatic CloudPanel bootstrap"
        )

    vendor_proc = transport.run_ssh(
        base,
        transport.remote_priv(
            target["ssh_user"],
            "(cat /sys/class/dmi/id/sys_vendor 2>/dev/null || true; "
            "cat /sys/class/dmi/id/product_name 2>/dev/null || true)",
        ),
        timeout=30,
    )
    cloud_hint = detect_cloud_hint(
        vendor_proc.stdout if vendor_proc.returncode == 0 else ""
    )
    return {
        "status": "READY",
        "os_id": os_id,
        "version_id": version_id,
        "cloud_hint": cloud_hint or "generic",
        "architecture": arch,
        "cores": cores,
        "memory_bytes": memory_bytes,
        "disk_bytes": disk_bytes,
        "db_engine": CLOUDPANEL_BOOTSTRAP_DB_ENGINE,
        "installer_sha256": CLOUDPANEL_INSTALLER_SHA256,
        "writes_performed": False,
    }

def bootstrap_target_cloudpanel(
    target: dict[str, Any],
    confirm: str,
) -> dict[str, Any]:
    required = f"BOOTSTRAP_CLOUDPANEL:{target['ip']}"
    if confirm != required:
        raise ServerMigrationError(f"explicit confirmation required: {required}")
    preflight = target_bootstrap_preflight(target)
    cloud_hint = "" if preflight["cloud_hint"] == "generic" else str(preflight["cloud_hint"])
    proc = remote(
        {"target": target},
        cloudpanel_bootstrap_script(cloud_hint),
        timeout=5400,
        check=False,
    )
    if proc.returncode != 0:
        raise ServerMigrationError("target CloudPanel bootstrap failed")
    return {
        "schema": SCHEMA,
        "operation": "BOOTSTRAP_TARGET",
        "status": "CLOUDPANEL_READY",
        "target_ip": target["ip"],
        "os_id": preflight["os_id"],
        "version_id": preflight["version_id"],
        "cloud_hint": preflight["cloud_hint"],
        "architecture": preflight["architecture"],
        "cores": preflight["cores"],
        "memory_bytes": preflight["memory_bytes"],
        "disk_bytes": preflight["disk_bytes"],
        "db_engine": CLOUDPANEL_BOOTSTRAP_DB_ENGINE,
        "installer_checksum_verified": True,
        "dns_changed": False,
        "source_changed": False,
        "secrets_emitted": False,
    }


def ensure_source_rsync_for_prepare() -> dict[str, Any]:
    if shutil.which("rsync"):
        return {"status": "READY", "installed": False}
    if os.geteuid() != 0 or shutil.which("apt-get") is None:
        raise ServerMigrationError("source rsync is missing and cannot be auto-installed")
    proc = run_local(
        ["apt-get", "update"],
        timeout=900,
        check=False,
    )
    if proc.returncode != 0:
        raise ServerMigrationError("source package index update failed while installing rsync")
    proc = run_local(
        ["apt-get", "-y", "install", "rsync"],
        timeout=900,
        check=False,
    )
    if proc.returncode != 0 or shutil.which("rsync") is None:
        raise ServerMigrationError("source rsync automatic installation failed")
    return {"status": "READY", "installed": True}


def parse_public_listener_rows(text: str) -> list[dict[str, Any]]:
    rows: set[tuple[str, int]] = set()
    allowed_web_management = {22, 80, 443, 8443}
    for raw in text.splitlines():
        parts = raw.split()
        if len(parts) < 5:
            continue
        proto = parts[0].lower()
        local = parts[4]
        if proto not in {"tcp", "udp"}:
            continue
        # ss may render *:31535, 0.0.0.0:80, [::]:443 or :::443.
        match = re.search(r"(?P<host>\*|0\.0\.0\.0|\[?::\]?|:::):(?P<port>[0-9]+)$", local)
        if not match:
            if local.startswith("*:"):
                host, _, port_text = local.rpartition(":")
            else:
                continue
        else:
            port_text = match.group("port")
        try:
            port = int(port_text)
        except (ValueError, UnboundLocalError):
            continue
        if not 1 <= port <= 65535 or port in allowed_web_management:
            continue
        rows.add((proto, port))
    return [
        {"protocol": proto, "port": port, "classification": "NON_CLOUDPANEL_PUBLIC_LISTENER"}
        for proto, port in sorted(rows)
    ]


def discover_source_external_listeners() -> list[dict[str, Any]]:
    if shutil.which("ss") is None:
        return []
    proc = run_local(["ss", "-H", "-lntu"], timeout=30, check=False)
    if proc.returncode != 0:
        return []
    return parse_public_listener_rows(proc.stdout)


def current_inventory() -> dict[str, Any]:
    manifest = inventory.build_manifest(Path("/"))
    if not manifest.get("sites"):
        raise ServerMigrationError("source CloudPanel inventory is empty")
    return manifest


def select_sites(manifest: dict[str, Any], domains: list[str]) -> list[dict[str, Any]]:
    sites = [item for item in manifest.get("sites", []) if isinstance(item, dict)]
    if not domains:
        return sites
    wanted = {str(item).lower() for item in domains}
    selected = [item for item in sites if str(item.get("domain", "")).lower() in wanted]
    found = {str(item.get("domain", "")).lower() for item in selected}
    missing = sorted(wanted - found)
    if missing:
        raise ServerMigrationError("source sites not found: " + ",".join(missing))
    return selected


def validate_full_server_site_set(
    sites: list[dict[str, Any]],
    home_root: Path = Path("/home"),
) -> dict[str, Any]:
    if not sites:
        raise ServerMigrationError("no source sites selected")
    users: set[str] = set()
    domains: set[str] = set()
    for site in sites:
        try:
            domain = cloudpanel.validate_domain(str(site.get("domain", "")))
            user = cloudpanel.validate_user(str(site.get("site_user", "")))
        except ValueError as exc:
            raise ServerMigrationError("source site identity is not portable") from exc
        if domain in domains:
            raise ServerMigrationError(f"duplicate source domain is ambiguous: {domain}")
        domains.add(domain)
        if user in users:
            raise ServerMigrationError(
                f"full-server automatic migration requires unique Site Users: {user}"
            )
        users.add(user)

        expected_root = home_root / user / "htdocs" / domain
        root = Path(str(site.get("site_root", "")))
        if root != expected_root or not root.is_dir():
            raise ServerMigrationError(
                f"source site root is not the canonical CloudPanel path: {domain}"
            )

        runtime = site.get("runtime") if isinstance(site.get("runtime"), dict) else {}
        runtime_type = str(runtime.get("type", "")).lower().replace("-", "_")
        version = str(runtime.get("version", ""))
        app_port = runtime.get("app_port")
        if runtime_type == "php":
            if not version or version == "UNKNOWN":
                raise ServerMigrationError(f"source PHP version is unknown: {domain}")
        elif runtime_type in {"nodejs", "node_js", "python"}:
            if not version or version == "UNKNOWN" or app_port in (None, "UNKNOWN"):
                raise ServerMigrationError(
                    f"source application runtime is incomplete: {domain}"
                )
        elif runtime_type in {"reverse_proxy", "reverseproxy"}:
            if app_port in (None, "UNKNOWN"):
                raise ServerMigrationError(
                    f"source reverse-proxy runtime is incomplete: {domain}"
                )
        elif runtime_type not in {"static", "static_html"}:
            raise ServerMigrationError(
                f"source runtime is not safely portable: {domain}"
            )

        mysql = site.get("mysql_databases")
        if not isinstance(mysql, list) or not all(
            isinstance(item, str) and item for item in mysql
        ):
            raise ServerMigrationError(f"source MySQL inventory is unknown: {domain}")

        cron = site.get("cron")
        if not isinstance(cron, dict):
            raise ServerMigrationError(f"source Cron inventory is invalid: {domain}")
        entry_count = cron.get("entry_count")
        source_paths = cron.get("source_paths")
        if not isinstance(entry_count, int) or entry_count < 0:
            raise ServerMigrationError(f"source Cron entry count is invalid: {domain}")
        if not isinstance(source_paths, list) or not all(
            isinstance(item, str) and item.startswith("/") for item in source_paths
        ):
            raise ServerMigrationError(f"source Cron paths are invalid: {domain}")

        pm2 = site.get("pm2")
        if not isinstance(pm2, dict) or not isinstance(pm2.get("present"), bool):
            raise ServerMigrationError(f"source PM2 inventory is invalid: {domain}")
        processes = pm2.get("processes")
        if pm2["present"]:
            if not isinstance(processes, list):
                raise ServerMigrationError(
                    f"source PM2 metadata is not safely portable: {domain}"
                )
        elif processes not in ([], None):
            raise ServerMigrationError(f"source PM2 metadata is inconsistent: {domain}")

    return {
        "status": "READY",
        "site_count": len(sites),
        "unique_site_users": len(users),
        "domains": sorted(domains),
    }


def path_apparent_size(path: Path) -> int:
    """Best-effort apparent byte count for migration capacity planning."""
    if path.is_symlink():
        try:
            return path.lstat().st_size
        except OSError:
            return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    if not path.is_dir():
        return 0
    total = 0
    try:
        for current, dirs, files in os.walk(path):
            current_path = Path(current)
            kept: list[str] = []
            for name in dirs:
                child = current_path / name
                if child.is_symlink():
                    try:
                        total += child.lstat().st_size
                    except OSError:
                        pass
                else:
                    kept.append(name)
            dirs[:] = kept
            for name in files:
                child = current_path / name
                try:
                    total += child.lstat().st_size
                except OSError:
                    pass
    except OSError:
        return total
    return total


def migration_capacity_estimate(sites: list[dict[str, Any]]) -> dict[str, int]:
    paths: set[Path] = set()
    mysql_present = False
    for site in sites:
        site_root = Path(str(site.get("site_root", "")))
        if site_root.is_absolute() and str(site_root).startswith("/home/"):
            paths.add(site_root)
        for external in external_paths_for_site(site):
            candidate = Path(external)
            if candidate.is_absolute() and str(candidate).startswith("/home/"):
                paths.add(candidate)
        mysql = site.get("mysql_databases")
        if isinstance(mysql, list) and mysql:
            mysql_present = True

    file_bytes = sum(path_apparent_size(path) for path in sorted(paths, key=str))
    mysql_raw_bytes = path_apparent_size(Path("/home/mysql")) if mysql_present else 0
    # Target stores site files plus database data and needs working headroom for
    # imports, SQLite replacement and CloudPanel metadata. Use an intentionally
    # conservative 20% + 512 MiB margin.
    payload_bytes = file_bytes + mysql_raw_bytes
    target_required = int(payload_bytes * 1.20) + 512 * 1024 * 1024
    # SOURCE creates only one transient logical dump/snapshot at a time, but
    # an individual logical dump can approach raw database size. Use the current
    # whole /home/mysql footprint as a conservative upper bound instead of an
    # arbitrary cap; low-disk mode may refuse an unusually large SOURCE rather
    # than risk filling Production during export.
    source_transient_required = (
        mysql_raw_bytes + 256 * 1024**2
        if mysql_present else 256 * 1024**2
    )
    return {
        "site_and_external_bytes": file_bytes,
        "mysql_raw_reference_bytes": mysql_raw_bytes,
        "estimated_payload_bytes": payload_bytes,
        "target_required_bytes": target_required,
        "source_transient_required_bytes": source_transient_required,
    }


def source_dependency_preflight(
    sites: list[dict[str, Any]],
    capacity: dict[str, int],
    *,
    allow_missing_rsync_autofix: bool = False,
) -> dict[str, Any]:
    required = ["rsync", "systemctl", "curl"]
    if any(
        isinstance(site.get("cron"), dict)
        and site.get("cron", {}).get("entry_count", 0) > 0
        for site in sites
    ):
        required.append("crontab")
    if any(
        isinstance(site.get("pm2"), dict) and site.get("pm2", {}).get("present")
        for site in sites
    ):
        required.append("runuser")
    missing = [name for name in required if shutil.which(name) is None]
    fixable = ["rsync"] if allow_missing_rsync_autofix and missing == ["rsync"] else []
    if missing and not fixable:
        raise ServerMigrationError(
            "source migration dependencies are missing: " + ",".join(missing)
        )
    source_free = shutil.disk_usage("/").free
    transient = int(capacity["source_transient_required_bytes"])
    if source_free < transient:
        raise ServerMigrationError(
            "source free disk is below the low-disk transient migration reserve"
        )
    return {
        "status": "READY_WITH_AUTO_FIX" if fixable else "READY",
        "required_commands": required,
        "missing_commands": missing,
        "auto_install_on_prepare": fixable,
        "source_free_bytes": source_free,
        "source_transient_required_bytes": transient,
    }


def target_preflight(
    target: dict[str, Any],
    sites: list[dict[str, Any]],
    *,
    target_required_bytes: int = 0,
) -> dict[str, Any]:
    identity = Path(target["identity_file"]) if target.get("identity_file") else None
    base = transport.ssh_base(
        target.get("ssh", "ssh"),
        target["host"],
        target["ssh_user"],
        int(target["ssh_port"]),
        identity,
    )
    check = (
        "set -eu; "
        "command -v clpctl >/dev/null 2>&1; "
        "command -v rsync >/dev/null 2>&1; "
        "command -v python3 >/dev/null 2>&1; "
        "command -v curl >/dev/null 2>&1; "
        "command -v systemctl >/dev/null 2>&1; "
        "command -v crontab >/dev/null 2>&1; "
        "command -v runuser >/dev/null 2>&1; "
        "command -v df >/dev/null 2>&1; "
        "command -v tail >/dev/null 2>&1; "
        "python3 -c 'import sqlite3' >/dev/null 2>&1; "
        "test -f /home/clp/htdocs/app/data/db.sq3; "
        "clpctl --version >/dev/null 2>&1"
    )
    proc = transport.run_ssh(base, transport.remote_priv(target["ssh_user"], check), timeout=30)
    if proc.returncode != 0:
        raise ServerMigrationError("target is not a ready CloudPanel server or SSH key access is unavailable")

    conflicts: list[str] = []
    db_check_code = (
        "import json,sqlite3,sys; "
        "domain,user,dbs=sys.argv[1],sys.argv[2],json.loads(sys.argv[3]); "
        "c=sqlite3.connect('file:/home/clp/htdocs/app/data/db.sq3?mode=ro',uri=True); "
        "site_hit=c.execute('SELECT 1 FROM site WHERE domain_name=? LIMIT 1',(domain,)).fetchone(); "
        "db_hit=None; "
        "\nfor db in dbs:\n"
        "    try:\n"
        "        db_hit=c.execute('SELECT 1 FROM \"database\" WHERE name=? LIMIT 1',(db,)).fetchone()\n"
        "    except sqlite3.Error:\n"
        "        db_hit='SCHEMA_UNKNOWN'\n"
        "    if db_hit: break\n"
        "c.close(); "
        "raise SystemExit(9 if site_hit or db_hit else 0)"
    )
    for site in sites:
        domain = str(site.get("domain", ""))
        user = str(site.get("site_user", ""))
        databases = site.get("mysql_databases")
        db_names = [str(item) for item in databases] if isinstance(databases, list) else []
        command = (
            f"set -eu; "
            f"test ! -e {shlex.quote('/home/' + user)}; "
            f"found=0; "
            f"for p in /home/*/htdocs/{shlex.quote(domain)}; do "
            f"[ ! -e \"$p\" ] || found=1; done; "
            f"[ \"$found\" -eq 0 ]; "
        )
        for database in db_names:
            command += f"test ! -e {shlex.quote('/home/mysql/' + database)}; "
        command += (
            f"python3 -c {shlex.quote(db_check_code)} "
            f"{shlex.quote(domain)} {shlex.quote(user)} "
            f"{shlex.quote(json.dumps(db_names, separators=(',', ':')))}"
        )
        result = transport.run_ssh(
            base,
            transport.remote_priv(target["ssh_user"], command),
            timeout=30,
        )
        if result.returncode != 0:
            conflicts.append(domain)
    if conflicts:
        raise ServerMigrationError(
            "target has domain/site-user/database conflicts for: " + ",".join(conflicts)
        )

    free_proc = transport.run_ssh(
        base,
        transport.remote_priv(
            target["ssh_user"],
            "df -B1 --output=avail /home | tail -n 1",
        ),
        timeout=30,
    )
    if free_proc.returncode != 0:
        raise ServerMigrationError("target free disk cannot be determined")
    try:
        target_free = int(free_proc.stdout.strip())
    except ValueError as exc:
        raise ServerMigrationError("target free disk result is invalid") from exc
    if target_required_bytes and target_free < target_required_bytes:
        raise ServerMigrationError("target free disk is below the migration capacity requirement")
    return {
        "status": "READY",
        "site_count": len(sites),
        "target_site_conflicts": [],
        "dns_changed": False,
        "writes_performed": False,
        "target_free_bytes": target_free,
        "target_required_bytes": target_required_bytes,
    }


def plan_payload(target: dict[str, Any], domains: list[str]) -> dict[str, Any]:
    source = current_inventory()
    sites = select_sites(source, domains)
    site_set = validate_full_server_site_set(sites)
    capacity = migration_capacity_estimate(sites)
    source_preflight = source_dependency_preflight(
        sites,
        capacity,
        allow_missing_rsync_autofix=True,
    )
    preflight = target_preflight(
        target,
        sites,
        target_required_bytes=int(capacity["target_required_bytes"]),
    )
    return {
        "schema": SCHEMA,
        "operation": "PLAN",
        "status": "READY",
        "source_server_identity": source.get("source_server", {}).get("hostname_hash", "UNKNOWN"),
        "target_ip": target["ip"],
        "site_count": len(sites),
        "site_set_preflight": site_set,
        "sites": [
            {
                "domain": item.get("domain"),
                "site_user": item.get("site_user"),
                "runtime": item.get("runtime"),
                "mysql_databases": item.get("mysql_databases"),
                "cron_entry_count": (item.get("cron") or {}).get("entry_count"),
            }
            for item in sites
        ],
        "target_preflight": preflight,
        "source_preflight": source_preflight,
        "capacity_estimate": capacity,
        "source_external_listeners": discover_source_external_listeners(),
        "cutover_requires_separate_confirmation": True,
        "dns_manual_gate_required": True,
        "automatic_dns_change": False,
        "source_delete_allowed": False,
        "writes_performed": False,
        "secrets_emitted": False,
    }


def external_paths_for_site(site: dict[str, Any], home_root: Path = Path("/home")) -> list[str]:
    user = str(site.get("site_user", ""))
    if not user or "/" in user:
        return []
    home = home_root / user
    if not home.is_dir():
        return []
    candidates: list[Path] = []
    candidates.extend(sorted(home.glob(".vf*")))
    candidates.extend(sorted(home.glob(".press*")))
    share = home / ".local/share"
    if share.is_dir():
        candidates.extend(sorted(share.glob("vf-*")))
    site_root = Path(str(site.get("site_root", ""))).resolve(strict=False)
    rows: list[str] = []
    for item in candidates:
        try:
            resolved = item.resolve(strict=False)
        except OSError:
            continue
        if not item.exists() or item.is_symlink():
            continue
        if site_root == resolved or site_root in resolved.parents:
            continue
        try:
            resolved.relative_to(home.resolve())
        except ValueError:
            continue
        value = str(resolved)
        if value not in rows:
            rows.append(value)
    return rows


def sqlite_paths_for_sites(
    sites: list[dict[str, Any]],
    home_root: Path = Path("/home"),
) -> list[tuple[Path, str]]:
    users = {str(item.get("site_user", "")) for item in sites if item.get("site_user")}
    found: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for user in sorted(users):
        if not user or "/" in user:
            continue
        home = home_root / user
        if not home.is_dir():
            continue
        for current, dirs, files in os.walk(home):
            dirs[:] = [d for d in dirs if d not in PRUNE_DIRS]
            current_path = Path(current)
            for name in files:
                if not name.lower().endswith(SQLITE_SUFFIXES):
                    continue
                candidate = current_path / name
                if candidate in seen or candidate.is_symlink():
                    continue
                try:
                    with candidate.open("rb") as handle:
                        if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                            continue
                except OSError:
                    continue
                seen.add(candidate)
                found.append((candidate, user))
    return sorted(found, key=lambda item: str(item[0]))


def sqlite_snapshot(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    try:
        src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30)
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
            row = dst.execute("PRAGMA quick_check").fetchone()
        finally:
            dst.close()
            src.close()
    except sqlite3.Error as exc:
        destination.unlink(missing_ok=True)
        raise ServerMigrationError(f"SQLite snapshot failed: {source}") from exc
    if not row or row[0] != "ok":
        destination.unlink(missing_ok=True)
        raise ServerMigrationError(f"SQLite snapshot verification failed: {source}")
    os.chmod(destination, 0o600)


def verify_remote_sqlite(state: dict[str, Any], path: str) -> None:
    code = (
        "import sqlite3,sys; "
        "c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True); "
        "r=c.execute('PRAGMA quick_check').fetchone(); c.close(); "
        "raise SystemExit(0 if r and r[0]=='ok' else 9)"
    )
    proc = remote(
        state,
        f"python3 -c {shlex.quote(code)} {shlex.quote(path)}",
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        raise ServerMigrationError("target SQLite quick_check failed")


def sync_sqlite_snapshots(state: dict[str, Any]) -> int:
    sites = state["sites"]
    work = state_dir(state["migration_id"]) / "sqlite-tmp"
    work.mkdir(parents=True, exist_ok=True)
    os.chmod(work, 0o700)
    count = 0
    try:
        for source, user in sqlite_paths_for_sites(sites):
            token = hashlib.sha256(str(source).encode()).hexdigest()[:16]
            snap = work / f"{token}.sqlite"
            sqlite_snapshot(source, snap)
            parent = str(source.parent)
            # The normal file/external pass must have created the parent already.
            # Never chmod an existing CloudPanel home/document directory here.
            remote(state, f"test -d {shlex.quote(parent)}")
            target_db = str(source)
            sidecars = [
                target_db + "-wal",
                target_db + "-shm",
                target_db + "-journal",
            ]
            remote(
                state,
                "rm -f -- " + " ".join(shlex.quote(item) for item in sidecars),
                timeout=30,
            )
            rsync_to_target(state, snap, target_db, user=user)
            mode = source.stat().st_mode & 0o777
            group = remote(state, f"id -gn {shlex.quote(user)}", timeout=30).stdout.strip()
            remote(
                state,
                f"chown {shlex.quote(user + ':' + group)} {shlex.quote(target_db)} && "
                f"chmod {mode:o} {shlex.quote(target_db)} && "
                + "rm -f -- " + " ".join(shlex.quote(item) for item in sidecars),
            )
            verify_remote_sqlite(state, str(source))
            count += 1
            snap.unlink(missing_ok=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return count


def sync_external_paths(state: dict[str, Any], *, delete: bool) -> list[str]:
    synced: list[str] = []
    for site in state["sites"]:
        user = str(site["site_user"])
        for source_text in site.get("external_paths", []):
            source = Path(source_text)
            destination = source_text
            parent = str(Path(destination).parent)
            group = remote(state, f"id -gn {shlex.quote(user)}", timeout=30).stdout.strip()
            if not group or any(ch.isspace() for ch in group):
                raise ServerMigrationError("target site group cannot be resolved")
            remote(
                state,
                (
                    f"if [ ! -d {shlex.quote(parent)} ]; then "
                    f"install -d -o {shlex.quote(user)} -g {shlex.quote(group)} "
                    f"-m 750 {shlex.quote(parent)}; fi"
                ),
                timeout=30,
            )
            rsync_to_target(state, source, destination, user=user, delete=delete)
            synced.append(source_text)
    return sorted(set(synced))


def stage_target_runtime(state: dict[str, Any]) -> None:
    mid = state["migration_id"]
    base = target_base(state)
    target_user = state["target"]["ssh_user"]
    runtime_path = f"/var/lib/vf-server-ops/server-migrations/{mid}/runtime"
    data_root = f"/var/lib/vf-server-ops/server-migrations/{mid}/data"
    command = (
        f"set -eu; install -d -m 700 {shlex.quote(runtime_path)} {shlex.quote(data_root)}; "
        f"tar -xzf - -C {shlex.quote(runtime_path)}; chmod -R go-rwx {shlex.quote(runtime_path)}; "
        f"chmod 700 {shlex.quote(runtime_path + '/bin/vfops')}"
    )
    transport.stream_tar_to_remote(
        "tar",
        ROOT,
        ["bin", "lib", "VERSION", "VF_PROJECT.json"],
        base,
        transport.remote_priv(target_user, command),
        "server-migration runtime staging",
    )
    state["target_runtime_path"] = runtime_path
    state["target_data_root"] = data_root


def target_python(state: dict[str, Any], *args: str, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    runtime = str(state["target_runtime_path"])
    command = [
        "env",
        f"PYTHONPATH={runtime}/lib",
        "python3",
        f"{runtime}/lib/server_migration.py",
        *args,
    ]
    rendered = " ".join(shlex.quote(item) for item in command)
    return remote(state, rendered, timeout=timeout)


def stage_site_metadata(state: dict[str, Any], site: dict[str, Any]) -> str:
    token = hashlib.sha256(str(site["domain"]).encode()).hexdigest()[:16]
    local = state_dir(state["migration_id"]) / f"site-{token}.json"
    atomic_private_json(local, site)
    remote_dir = f"{state['target_data_root']}/sites"
    remote_path = f"{remote_dir}/{token}.json"
    remote(state, f"install -d -m 700 {shlex.quote(remote_dir)}")
    rsync_to_target(state, local, remote_path)
    remote(state, f"chmod 600 {shlex.quote(remote_path)}")
    return remote_path


def target_create_site_from_metadata(state: dict[str, Any], remote_site_file: str) -> None:
    proc = target_python(
        state,
        "_target-create-site",
        "--migration-id", str(state["migration_id"]),
        "--site-file", remote_site_file,
        timeout=600,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ServerMigrationError("target site creation returned invalid result") from exc
    if payload.get("status") != "CREATED":
        raise ServerMigrationError("target site creation did not complete")


def target_create_database(
    state: dict[str, Any],
    site: dict[str, Any],
    database: str,
    index: int,
    remote_dump: str,
) -> dict[str, Any]:
    proc = target_python(
        state,
        "_target-create-database",
        "--migration-id", str(state["migration_id"]),
        "--domain", str(site["domain"]),
        "--site-root", str(site["site_root"]),
        "--database", database,
        "--index", str(index),
        "--dump", remote_dump,
        timeout=3600,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ServerMigrationError("target database creation returned invalid result") from exc
    if payload.get("status") != "DATABASE_IMPORTED":
        raise ServerMigrationError(f"target database import did not complete: {database}")
    return payload


def initial_mysql_sync(state: dict[str, Any], site: dict[str, Any]) -> int:
    databases = site.get("mysql_databases")
    if not isinstance(databases, list):
        if databases == "UNKNOWN":
            raise ServerMigrationError(f"MySQL inventory is UNKNOWN: {site['domain']}")
        return 0
    if not databases:
        return 0
    if len(databases) > 1:
        raise ServerMigrationError(
            f"full-server automatic app-config remap is ambiguous for multi-database site: {site['domain']}"
        )
    work = state_dir(state["migration_id"]) / "mysql-prepare"
    work.mkdir(parents=True, exist_ok=True)
    os.chmod(work, 0o700)
    user = str(site["site_user"])
    count = 0
    for index, raw in enumerate(databases, 1):
        database = str(raw)
        token = hashlib.sha256(f"{site['domain']}:{database}".encode()).hexdigest()[:12]
        local = work / f"{token}.sql.gz"
        remote_dump = f"/home/{user}/.vfops-prepare-{state['migration_id']}-{token}.sql.gz"
        try:
            cloudpanel.export_database(database, local)
            rsync_to_target(state, local, remote_dump, user=user)
            result = target_create_database(state, site, database, index, remote_dump)
            site.setdefault("target_databases", []).append({
                "database": database,
                "config_mode": result.get("application_config_mode"),
                "config_file": result.get("application_config_file"),
            })
            count += 1
        finally:
            local.unlink(missing_ok=True)
            remote(state, f"rm -f -- {shlex.quote(remote_dump)}", timeout=30, check=False)
    try:
        work.rmdir()
    except OSError:
        pass
    return count


def resolve_source_pm2_node_runtime(
    user: str,
    source_dump: Path,
    home_root: Path = Path("/home"),
) -> Path:
    try:
        source_pm2, _source_path = runtime_engine.resolve_site_user_nvm_pm2(
            user, source_dump, home_root=home_root
        )
    except runtime_engine.RuntimeActivationError as exc:
        raise ServerMigrationError(
            f"source PM2 runtime cannot be resolved for automated migration: {user}"
        ) from exc
    source_node_root = Path(source_pm2).parent.parent
    expected_parent = home_root / user / ".nvm" / "versions" / "node"
    try:
        relative = source_node_root.relative_to(expected_parent)
    except ValueError as exc:
        raise ServerMigrationError(
            f"source PM2 runtime is outside the expected NVM tree: {user}"
        ) from exc
    if len(relative.parts) != 1:
        raise ServerMigrationError(
            f"source PM2 runtime has an unexpected NVM version path: {user}"
        )
    return source_node_root


def system_cron_job_users(path: Path) -> set[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ServerMigrationError(f"system cron cannot be read safely: {path}") from exc

    users: set[str] = set()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", line):
            continue
        parts = line.split()
        if line.startswith("@"):
            if len(parts) < 3:
                raise ServerMigrationError(f"system cron line is ambiguous: {path}")
            user = parts[1]
        else:
            if len(parts) < 7:
                raise ServerMigrationError(f"system cron line is ambiguous: {path}")
            user = parts[5]
        try:
            users.add(cloudpanel.validate_user(user))
        except ValueError as exc:
            raise ServerMigrationError(f"system cron user is invalid: {path}") from exc
    return users


def stage_runtime_sources(state: dict[str, Any]) -> None:
    root = str(state["target_data_root"])
    system_records: dict[str, dict[str, Any]] = {}
    user_records: dict[str, dict[str, Any]] = {}
    pm2_records: dict[str, dict[str, Any]] = {}
    selected_users = {
        str(site["site_user"])
        for site in state["sites"]
        if isinstance(site, dict) and site.get("site_user")
    }

    for site in state["sites"]:
        user = str(site["site_user"])
        cron = site.get("cron") if isinstance(site.get("cron"), dict) else {}
        for source_text in cron.get("source_paths", []) if isinstance(cron.get("source_paths"), list) else []:
            source = Path(str(source_text))
            if not source.is_file() or source.is_symlink():
                continue
            if str(source).startswith("/etc/cron.d/"):
                if str(source) in system_records:
                    continue
                cron_users = system_cron_job_users(source)
                if not cron_users or not cron_users.issubset(selected_users):
                    raise ServerMigrationError(
                        f"shared/ambiguous system cron requires manual separation before migration: {source}"
                    )
                token = hashlib.sha256(str(source).encode()).hexdigest()[:12]
                target = f"{root}/runtime/system-cron/{token}.cron"
                remote(state, f"install -d -m 700 {shlex.quote(str(Path(target).parent))}")
                rsync_to_target(state, source, target)
                remote(state, f"chmod 600 {shlex.quote(target)}")
                system_records[str(source)] = {
                    "source_path": str(source),
                    "staged_target": target,
                    "domain": str(site["domain"]),
                    "activated": False,
                }
            elif str(source) in {f"/var/spool/cron/crontabs/{user}", f"/var/spool/cron/{user}"}:
                if user in user_records:
                    continue
                target = f"{root}/runtime/user-cron/{package_engine.safe_name(user)}.cron"
                remote(state, f"install -d -m 700 {shlex.quote(str(Path(target).parent))}")
                rsync_to_target(state, source, target)
                remote(state, f"chmod 600 {shlex.quote(target)}")
                user_records[user] = {
                    "user": user,
                    "source_path": str(source),
                    "staged_target": target,
                    "activated": False,
                }

        pm2 = site.get("pm2") if isinstance(site.get("pm2"), dict) else {}
        source_dump = Path("/home") / user / ".pm2" / "dump.pm2"
        if pm2.get("present") and source_dump.is_file() and user not in pm2_records:
            target = f"{root}/runtime/pm2/{package_engine.safe_name(user)}.json"
            remote(state, f"install -d -m 700 {shlex.quote(str(Path(target).parent))}")
            rsync_to_target(state, source_dump, target)
            remote(state, f"chmod 600 {shlex.quote(target)}")

            # Full-server migration must not assume a clean TARGET already has the
            # Site User's NVM/PM2 toolchain. Resolve the exact source runtime from
            # the PM2 dump, then copy only that Node version directory. This keeps
            # the transfer bounded while allowing PM2 activation without a manual
            # Node/NVM installation step.
            source_node_root = resolve_source_pm2_node_runtime(user, source_dump)
            target_node_parent = Path("/home") / user / ".nvm" / "versions" / "node"
            target_node_root = target_node_parent / source_node_root.name
            group = remote(state, f"id -gn {shlex.quote(user)}", timeout=30).stdout.strip()
            if not group or any(ch.isspace() for ch in group):
                raise ServerMigrationError("target site group cannot be resolved for PM2")
            remote(
                state,
                "install -d "
                f"-o {shlex.quote(user)} -g {shlex.quote(group)} -m 755 "
                f"{shlex.quote(str(target_node_parent))}",
                timeout=30,
            )
            rsync_to_target(
                state,
                source_node_root,
                str(target_node_root),
                user=user,
                delete=False,
            )
            pm2_records[user] = {
                "user": user,
                "source_path": str(source_dump),
                "staged_target": target,
                "source_node_runtime": str(source_node_root),
                "target_node_runtime": str(target_node_root),
                "activated": False,
            }

    state["pending_system_cron"] = sorted(system_records.values(), key=lambda item: item["source_path"])
    state["pending_user_cron"] = sorted(user_records.values(), key=lambda item: item["user"])
    state["pending_pm2"] = sorted(pm2_records.values(), key=lambda item: item["user"])


def prepare_one_site_direct(state: dict[str, Any], site: dict[str, Any]) -> None:
    remote_site_file = stage_site_metadata(state, site)
    created = False
    try:
        target_create_site_from_metadata(state, remote_site_file)
        created = True
        source_root = Path(str(site["site_root"]))
        rsync_to_target(
            state,
            source_root,
            str(source_root),
            user=str(site["site_user"]),
            delete=False,
        )
        site["mysql_prepare_count"] = initial_mysql_sync(state, site)
        site["stage_status"] = "DIRECT_STAGED"
    except Exception:
        if created:
            databases = [
                str(item)
                for item in site.get("mysql_databases", [])
                if isinstance(item, str) and item
            ]
            args = [
                "_target-cleanup-site",
                "--migration-id", str(state["migration_id"]),
                "--domain", str(site["domain"]),
            ]
            for database in databases:
                args.extend(["--database", database])
            # target_python is fail-closed; cleanup must be best effort and must not
            # replace the original failure with cleanup noise.
            runtime = str(state["target_runtime_path"])
            command = [
                "env", f"PYTHONPATH={runtime}/lib", "python3",
                f"{runtime}/lib/server_migration.py", *args,
            ]
            remote(
                state,
                " ".join(shlex.quote(item) for item in command),
                timeout=600,
                check=False,
            )
        site["target_databases"] = []
        site["stage_status"] = "PENDING"
        raise


def prepare_migration(
    target: dict[str, Any],
    domains: list[str],
    confirm: str,
) -> dict[str, Any]:
    if confirm != "PREPARE_SERVER_MIGRATION":
        raise ServerMigrationError("explicit confirmation required: PREPARE_SERVER_MIGRATION")
    source = current_inventory()
    selected = select_sites(source, domains)
    site_set = validate_full_server_site_set(selected)
    capacity = migration_capacity_estimate(selected)
    ensure_source_rsync_for_prepare()
    source_dependency_preflight(selected, capacity)
    target_preflight(
        target,
        selected,
        target_required_bytes=int(capacity["target_required_bytes"]),
    )
    source_hash = str(source.get("source_server", {}).get("hostname_hash", "UNKNOWN"))
    mid = migration_id(source_hash, target["ip"])
    directory = state_dir(mid)
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)

    state: dict[str, Any] = {
        "schema": SCHEMA,
        "migration_id": mid,
        "status": "PREPARING",
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "source_server_identity": source_hash,
        "target": target,
        "sites": [],
        "source_nginx_frozen": False,
        "target_runtime_activated": False,
        "dns_changed_by_p07": False,
        "source_delete_allowed": False,
        "secrets_emitted": False,
        "transfer_mode": "LOW_DISK_DIRECT_RSYNC",
        "source_full_backup_packages_created": 0,
        "capacity_estimate": capacity,
        "site_set_preflight": site_set,
        "source_external_listeners": discover_source_external_listeners(),
    }
    for item in selected:
        row = dict(item)
        row["external_paths"] = external_paths_for_site(item)
        row["stage_status"] = "PENDING"
        state["sites"].append(row)
    save_state(state)

    try:
        stage_target_runtime(state)
        save_state(state)
        for site in state["sites"]:
            prepare_one_site_direct(state, site)
            save_state(state)

        state["external_paths_synced"] = sync_external_paths(state, delete=False)
        state["sqlite_snapshot_count_prepare"] = sync_sqlite_snapshots(state)
        stage_runtime_sources(state)
        state["status"] = "PREPARED"
        state["source_still_live"] = True
        state["dns_changed_by_p07"] = False
        save_state(state)
        return state
    except Exception as exc:
        state["status"] = "PREPARE_FAILED"
        state["last_error_class"] = exc.__class__.__name__
        save_state(state)
        if isinstance(exc, ServerMigrationError):
            raise
        raise ServerMigrationError("server migration prepare failed") from exc


def resume_prepare_migration(mid: str) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("status") not in {"PREPARE_FAILED", "PREPARING"}:
        raise ServerMigrationError("migration is not resumable from prepare stage")
    remote(state, "command -v clpctl >/dev/null 2>&1 && test -f /home/clp/htdocs/app/data/db.sq3", timeout=30)
    state["status"] = "PREPARING"
    state.pop("last_error_class", None)
    save_state(state)
    try:
        if not state.get("target_runtime_path"):
            stage_target_runtime(state)
            save_state(state)
        for site in state["sites"]:
            if site.get("stage_status") == "DIRECT_STAGED":
                continue
            prepare_one_site_direct(state, site)
            save_state(state)

        state["external_paths_synced"] = sync_external_paths(state, delete=False)
        state["sqlite_snapshot_count_prepare"] = sync_sqlite_snapshots(state)
        stage_runtime_sources(state)
        state["status"] = "PREPARED"
        state["source_still_live"] = True
        save_state(state)
        return state
    except Exception as exc:
        state["status"] = "PREPARE_FAILED"
        state["last_error_class"] = exc.__class__.__name__
        save_state(state)
        if isinstance(exc, ServerMigrationError):
            raise
        raise ServerMigrationError("server migration prepare resume failed") from exc


def target_tx_root(mid: str) -> Path:
    if not SAFE_ID_RE.fullmatch(mid):
        raise ServerMigrationError("invalid target migration id")
    root = STATE_ROOT / mid / "target-transactions"
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    return root


def target_site_marker(mid: str, domain: str) -> Path:
    token = hashlib.sha256(cloudpanel.validate_domain(domain).encode()).hexdigest()[:16]
    return target_tx_root(mid) / f"site-{token}.json"


def target_db_marker(mid: str, domain: str, database: str, index: int) -> Path:
    token = hashlib.sha256(
        f"{cloudpanel.validate_domain(domain)}:{cloudpanel.validate_name(database, 'database')}:{index}".encode()
    ).hexdigest()[:16]
    return target_tx_root(mid) / f"db-{token}.json"


def target_site_creation_mismatches(
    source_site: dict[str, Any],
    target_site: dict[str, Any],
) -> list[str]:
    mismatches: list[str] = []
    for field in ("domain", "site_user", "site_root"):
        if str(source_site.get(field, "")) != str(target_site.get(field, "")):
            mismatches.append(field)

    source_docroot = str(source_site.get("document_root", "UNKNOWN"))
    if source_docroot not in {"", "UNKNOWN"}:
        if source_docroot != str(target_site.get("document_root", "")):
            mismatches.append("document_root")

    source_runtime = (
        source_site.get("runtime")
        if isinstance(source_site.get("runtime"), dict)
        else {}
    )
    target_runtime = (
        target_site.get("runtime")
        if isinstance(target_site.get("runtime"), dict)
        else {}
    )
    source_type = str(source_runtime.get("type", "")).lower().replace("-", "_")
    target_type = str(target_runtime.get("type", "")).lower().replace("-", "_")
    if source_type != target_type:
        mismatches.append("runtime.type")
    if str(source_runtime.get("version", "")) not in {"", "UNKNOWN"}:
        if str(source_runtime.get("version")) != str(target_runtime.get("version")):
            mismatches.append("runtime.version")
    if source_type in {"nodejs", "node_js", "python", "reverse_proxy", "reverseproxy"}:
        if str(source_runtime.get("app_port")) != str(target_runtime.get("app_port")):
            mismatches.append("runtime.app_port")

    source_domains = {
        str(item)
        for item in source_site.get("domains", [])
        if isinstance(item, str) and item
    }
    target_domains = {
        str(item)
        for item in target_site.get("domains", [])
        if isinstance(item, str) and item
    }
    if source_domains and not source_domains.issubset(target_domains):
        mismatches.append("domains")
    return sorted(set(mismatches))


def verify_target_site_creation(source_site: dict[str, Any]) -> list[str]:
    domain = str(source_site.get("domain", ""))
    try:
        manifest = inventory.build_manifest(Path("/"))
        target_site = cutover.find_site(manifest, domain)
    except Exception as exc:
        raise ServerMigrationError(
            f"target CloudPanel site cannot be read back after creation: {domain}"
        ) from exc
    return target_site_creation_mismatches(source_site, target_site)


def target_create_site_local(mid: str, site_file: Path) -> dict[str, Any]:
    try:
        site = json.loads(site_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ServerMigrationError("target site metadata is invalid") from exc
    if not isinstance(site, dict):
        raise ServerMigrationError("target site metadata is invalid")
    domain = str(site.get("domain", ""))
    site_root = Path(str(site.get("site_root", "")))
    marker = target_site_marker(mid, domain)
    if marker.is_file():
        if not site_root.is_dir():
            raise ServerMigrationError(
                "target site transaction marker exists but site root is missing"
            )
        mismatches = verify_target_site_creation(site)
        if mismatches:
            raise ServerMigrationError(
                "target site readback no longer matches the staged source contract: "
                + ",".join(mismatches)
            )
        return {
            "status": "CREATED",
            "domain": domain,
            "resumed": True,
            "web_contract_mismatches": [],
            "secrets_emitted": False,
        }

    try:
        restore_apply.run_clpctl("clpctl", restore_apply.site_add_args(site))
    except restore_apply.SandboxRestoreError as exc:
        raise ServerMigrationError("target CloudPanel site creation failed") from exc
    if not site_root.is_dir():
        site_lifecycle.cleanup_site(domain, clpctl="clpctl")
        raise ServerMigrationError("target site root was not created")

    try:
        mismatches = verify_target_site_creation(site)
    except ServerMigrationError:
        site_lifecycle.cleanup_site(domain, clpctl="clpctl")
        raise
    if mismatches:
        site_lifecycle.cleanup_site(domain, clpctl="clpctl")
        raise ServerMigrationError(
            "target CloudPanel site is not web-runtime equivalent: "
            + ",".join(mismatches)
        )

    atomic_private_json(marker, {"domain": domain, "created_by_migration": mid})
    return {
        "status": "CREATED",
        "domain": domain,
        "resumed": False,
        "web_contract_mismatches": [],
        "secrets_emitted": False,
    }


def target_create_database_local(
    migration_id_value: str,
    domain: str,
    site_root: Path,
    database: str,
    index: int,
    dump: Path,
) -> dict[str, Any]:
    if not dump.is_file() or not site_root.is_dir():
        raise ServerMigrationError("target database staging input is unavailable")
    marker = target_db_marker(migration_id_value, domain, database, index)
    created_now = False
    if marker.is_file():
        try:
            private = json.loads(marker.read_text(encoding="utf-8"))
            username = str(private["username"])
            password = str(private["password"])
            if (
                str(private.get("domain")) != domain
                or str(private.get("database")) != database
                or str(private.get("created_by_migration")) != migration_id_value
            ):
                raise ServerMigrationError(
                    "target database transaction marker ownership is inconsistent"
                )
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            raise ServerMigrationError("target database transaction marker is invalid") from exc

        # A previous import may have been interrupted after partially writing rows.
        # Because the private marker proves this database is owned by this migration,
        # reset it to a known-empty state before a resumable re-import.
        if not site_lifecycle.cleanup_database(database, clpctl="clpctl"):
            raise ServerMigrationError(
                "target transaction-owned database cannot be reset for resume"
            )
        try:
            cloudpanel.add_database(
                domain, database, username, password, clpctl="clpctl"
            )
        except (cloudpanel.CloudPanelError, ValueError) as exc:
            raise ServerMigrationError(
                "target database recreation failed during resume"
            ) from exc
    else:
        _, username, password = site_lifecycle.derive_database_identity(
            domain, migration_id_value, index
        )
        try:
            cloudpanel.add_database(
                domain, database, username, password, clpctl="clpctl"
            )
        except (cloudpanel.CloudPanelError, ValueError) as exc:
            raise ServerMigrationError("target database creation failed") from exc
        atomic_private_json(marker, {
            "domain": domain,
            "database": database,
            "username": username,
            "password": password,
            "created_by_migration": migration_id_value,
        })
        created_now = True

    try:
        cloudpanel.import_database(database, dump, clpctl="clpctl")
        mode, config_path = app_config.rewrite_application_database_config(
            site_root,
            domain,
            domain,
            database,
            username,
            password,
        )
        owner = site_root.stat()
        if config_path is not None:
            os.chown(config_path, owner.st_uid, owner.st_gid, follow_symlinks=False)
        return {
            "status": "DATABASE_IMPORTED",
            "database": database,
            "application_config_mode": mode,
            "application_config_file": (
                config_path.relative_to(site_root).as_posix() if config_path is not None else None
            ),
            "resumed": not created_now,
            "secrets_emitted": False,
        }
    except (cloudpanel.CloudPanelError, ValueError, app_config.AppConfigError, OSError) as exc:
        # Keep a marked database for safe resume when import/config failed. It is
        # transaction-owned and can be retried without guessing or deleting unrelated data.
        raise ServerMigrationError("target database import/config-remap failed") from exc
    finally:
        dump.unlink(missing_ok=True)


def target_cleanup_site_local(
    mid: str,
    domain: str,
    databases: list[str],
) -> dict[str, Any]:
    db_ok = True
    for index, database in enumerate(databases, 1):
        marker = target_db_marker(mid, domain, database, index)
        if not marker.is_file():
            continue
        cleaned = site_lifecycle.cleanup_database(database, clpctl="clpctl")
        db_ok = cleaned and db_ok
        if cleaned:
            marker.unlink(missing_ok=True)
    site_marker = target_site_marker(mid, domain)
    site_ok = True
    if site_marker.is_file():
        site_ok = site_lifecycle.cleanup_site(domain, clpctl="clpctl")
        if site_ok:
            site_marker.unlink(missing_ok=True)
    return {
        "status": "CLEANED" if db_ok and site_ok else "PARTIAL",
        "database_cleanup": db_ok,
        "site_cleanup": site_ok,
        "secrets_emitted": False,
    }


def freeze_source_runtime(state: dict[str, Any]) -> None:
    recovery = state_dir(state["migration_id"]) / "source-runtime"
    recovery.mkdir(parents=True, exist_ok=True)
    os.chmod(recovery, 0o700)

    state.setdefault("source_system_cron_saved", [])
    state.setdefault("source_user_cron_saved", [])
    state.setdefault("source_pm2_stopped", [])
    save_state(state)

    saved_system = {
        str(row.get("source_path")): row
        for row in state["source_system_cron_saved"]
        if isinstance(row, dict) and row.get("source_path")
    }
    for row in state.get("pending_system_cron", []):
        source = Path(str(row["source_path"]))
        saved_row = saved_system.get(str(source))
        if saved_row and saved_row.get("disabled"):
            continue

        if saved_row is None:
            if not source.exists():
                continue
            target = recovery / (
                "system-"
                + hashlib.sha256(str(source).encode()).hexdigest()[:12]
            )
            shutil.copy2(source, target)
            os.chmod(target, 0o600)
            saved_row = {
                "source_path": str(source),
                "saved_file": str(target),
                "disable_intent": True,
                "disabled": False,
            }
            state["source_system_cron_saved"].append(saved_row)
            saved_system[str(source)] = saved_row
            save_state(state)

        if source.exists():
            source.unlink()
        saved_row["disabled"] = True
        save_state(state)

    saved_users = {
        str(row.get("user")): row
        for row in state["source_user_cron_saved"]
        if isinstance(row, dict) and row.get("user")
    }
    for row in state.get("pending_user_cron", []):
        user = str(row["user"])
        saved_row = saved_users.get(user)
        if saved_row and saved_row.get("disabled"):
            continue
        if saved_row and not saved_row.get("existed"):
            continue

        if saved_row is None:
            proc = run_local(
                ["crontab", "-u", user, "-l"],
                timeout=30,
                check=False,
            )
            if proc.returncode == 0:
                target = recovery / (
                    f"user-cron-{package_engine.safe_name(user)}"
                )
                target.write_text(proc.stdout, encoding="utf-8")
                os.chmod(target, 0o600)
                saved_row = {
                    "user": user,
                    "saved_file": str(target),
                    "existed": True,
                    "disable_intent": True,
                    "disabled": False,
                }
                state["source_user_cron_saved"].append(saved_row)
                saved_users[user] = saved_row
                save_state(state)
            elif proc.returncode == 1:
                saved_row = {
                    "user": user,
                    "saved_file": "",
                    "existed": False,
                    "disable_intent": False,
                    "disabled": False,
                }
                state["source_user_cron_saved"].append(saved_row)
                saved_users[user] = saved_row
                save_state(state)
                continue
            else:
                raise ServerMigrationError(
                    f"cannot inspect source user cron: {user}"
                )

        remove = run_local(
            ["crontab", "-u", user, "-r"],
            timeout=30,
            check=False,
        )
        if remove.returncode not in (0, 1):
            raise ServerMigrationError(
                f"cannot disable source user cron: {user}"
            )
        saved_row["disabled"] = True
        save_state(state)

    stopped_by_user = {
        str(row.get("user")): row
        for row in state["source_pm2_stopped"]
        if isinstance(row, dict) and row.get("user")
    }
    for row in state.get("pending_pm2", []):
        user = str(row["user"])
        stopped_row = stopped_by_user.get(user)
        if stopped_row and stopped_row.get("stopped"):
            continue

        source_dump = Path(str(row["source_path"]))
        try:
            pm2_cmd, path_env = runtime_engine.resolve_site_user_nvm_pm2(
                user,
                source_dump,
            )
        except runtime_engine.RuntimeActivationError as exc:
            raise ServerMigrationError(
                f"cannot resolve source PM2: {user}"
            ) from exc
        env = [
            f"HOME=/home/{user}",
            f"PM2_HOME=/home/{user}/.pm2",
            f"PATH={path_env}",
        ]

        if stopped_row is None:
            stopped_row = {
                "user": user,
                "source_path": str(source_dump),
                "stop_intent": True,
                "stopped": False,
            }
            state["source_pm2_stopped"].append(stopped_row)
            stopped_by_user[user] = stopped_row
            save_state(state)

        if not runtime_engine.best_effort_pm2_shutdown(
            "runuser",
            user,
            env,
            pm2_cmd,
            Path("/home") / user,
        ):
            raise ServerMigrationError(
                f"cannot stop source PM2 safely: {user}"
            )
        stopped_row["stopped"] = True
        save_state(state)

    if not state.get("source_nginx_frozen"):
        run_local(["systemctl", "stop", "nginx"], timeout=120)
        active = run_local(["systemctl", "is-active", "nginx"], timeout=30, check=False)
        if active.returncode == 0:
            raise ServerMigrationError("source nginx is still active")
        state["source_nginx_frozen"] = True
        state["source_still_live"] = False
        save_state(state)


def restore_source_runtime(state: dict[str, Any]) -> bool:
    ok = True

    for row in state.get("source_system_cron_saved", []):
        if row.get("restored"):
            continue
        try:
            shutil.copy2(row["saved_file"], row["source_path"])
            os.chmod(row["source_path"], 0o644)
        except OSError:
            ok = False
        else:
            row["restored"] = True
            save_state(state)

    for row in state.get("source_user_cron_saved", []):
        if row.get("restored"):
            continue
        if not row.get("existed"):
            row["restored"] = True
            save_state(state)
            continue
        try:
            proc = run_local(
                ["crontab", "-u", row["user"], row["saved_file"]],
                timeout=30,
                check=False,
            )
        except ServerMigrationError:
            ok = False
        else:
            if proc.returncode == 0:
                row["restored"] = True
                save_state(state)
            else:
                ok = False

    for row in state.get("source_pm2_stopped", []):
        if row.get("restored"):
            continue
        user = str(row["user"])
        source_dump = Path(str(row["source_path"]))
        try:
            pm2_cmd, path_env = runtime_engine.resolve_site_user_nvm_pm2(
                user, source_dump
            )
            proc = run_local(
                [
                    "runuser", "-u", user, "--", "/usr/bin/env",
                    f"HOME=/home/{user}",
                    f"PM2_HOME=/home/{user}/.pm2",
                    f"PATH={path_env}",
                    pm2_cmd, "resurrect",
                ],
                timeout=120,
                check=False,
            )
            if proc.returncode == 0:
                row["restored"] = True
                save_state(state)
            else:
                ok = False
        except (ServerMigrationError, runtime_engine.RuntimeActivationError):
            ok = False

    try:
        proc = run_local(["systemctl", "start", "nginx"], timeout=120, check=False)
        if proc.returncode == 0:
            state["source_nginx_frozen"] = False
            state["source_still_live"] = True
            save_state(state)
        else:
            ok = False
    except ServerMigrationError:
        ok = False

    if not ok:
        state["source_still_live"] = False if state.get("source_nginx_frozen") else state.get(
            "source_still_live", False
        )
        save_state(state)
    return ok


def sync_site_roots_final(state: dict[str, Any]) -> None:
    for site in state["sites"]:
        source = Path(str(site["site_root"]))
        excludes: tuple[str, ...] = ()
        mysql = site.get("mysql_databases")
        if isinstance(mysql, list) and mysql:
            excludes = PROTECTED_DB_CONFIGS
        rsync_to_target(
            state,
            source,
            str(source),
            user=str(site["site_user"]),
            delete=True,
            excludes=excludes,
        )


def final_mysql_sync(state: dict[str, Any]) -> int:
    work = state_dir(state["migration_id"]) / "mysql-final"
    work.mkdir(parents=True, exist_ok=True)
    os.chmod(work, 0o700)
    count = 0
    try:
        for site in state["sites"]:
            databases = site.get("mysql_databases")
            if not isinstance(databases, list):
                continue
            user = str(site["site_user"])
            for index, raw in enumerate(databases, 1):
                database = str(raw)
                token = hashlib.sha256(
                    f"{site['domain']}:{database}".encode()
                ).hexdigest()[:12]
                source_dump = work / f"{token}-source.sql.gz"
                target_export_local = work / f"{token}-target.sql.gz"
                target_temp = (
                    f"/home/{user}/.vfops-final-"
                    f"{state['migration_id']}-{token}.sql.gz"
                )
                target_export = (
                    f"/home/{user}/.vfops-verify-"
                    f"{state['migration_id']}-{token}.sql.gz"
                )

                try:
                    cloudpanel.export_database(database, source_dump)
                    rsync_to_target(
                        state,
                        source_dump,
                        target_temp,
                        user=user,
                    )
                    remote(
                        state,
                        f"chmod 600 {shlex.quote(target_temp)}",
                        timeout=30,
                    )

                    # Reuse the transaction-owned TARGET database helper. If the
                    # PREPARE import (or a previous final import) was interrupted,
                    # the helper proves marker ownership, drops only that
                    # migration-owned DB, recreates it with the same private
                    # TARGET credentials, imports the frozen SOURCE dump, and
                    # re-applies supported application config atomically.
                    target_create_database(
                        state,
                        site,
                        database,
                        index,
                        target_temp,
                    )

                    remote(
                        state,
                        (
                            "clpctl db:export "
                            f"--databaseName={shlex.quote(database)} "
                            f"--file={shlex.quote(target_export)}"
                        ),
                        timeout=3600,
                    )
                    args = [
                        "rsync",
                        "-a",
                        "-e",
                        rsync_ssh_command(state),
                        (
                            f"{state['target']['ssh_user']}@"
                            f"{state['target']['host']}:{target_export}"
                        ),
                        str(target_export_local),
                    ]
                    run_local(args, timeout=3600)

                    try:
                        before, before_count = verify_engine.sql_fingerprint(
                            source_dump
                        )
                        after, after_count = verify_engine.sql_fingerprint(
                            target_export_local
                        )
                        verification_mode = "CANONICAL_SQL_EXACT"
                        if before != after or before_count != after_count:
                            source_content = verify_engine.sql_data_fingerprint(
                                source_dump
                            )
                            target_content = verify_engine.sql_data_fingerprint(
                                target_export_local
                            )
                            if source_content != target_content:
                                raise ServerMigrationError(
                                    "MySQL target logical-content mismatch: "
                                    f"{database}"
                                )
                            verification_mode = "CROSS_ENGINE_LOGICAL_CONTENT"
                    except verify_engine.RestoreVerifyError as exc:
                        raise ServerMigrationError(
                            f"MySQL verification failed: {database}"
                        ) from exc

                    site.setdefault("mysql_final_verification", []).append({
                        "database": database,
                        "mode": verification_mode,
                        "status": "PASS",
                    })
                    count += 1
                finally:
                    remote(
                        state,
                        (
                            "rm -f -- "
                            f"{shlex.quote(target_temp)} "
                            f"{shlex.quote(target_export)}"
                        ),
                        timeout=30,
                        check=False,
                    )
                    source_dump.unlink(missing_ok=True)
                    target_export_local.unlink(missing_ok=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return count


def remote_activate_runtime(state: dict[str, Any]) -> None:
    for row in state.get("pending_user_cron", []):
        if row.get("activated"):
            continue
        user = str(row["user"])
        staged = str(row["staged_target"])
        check = remote(
            state,
            (
                f"set -eu; tmp=$(mktemp); "
                f"if crontab -u {shlex.quote(user)} -l >\"$tmp\" 2>/dev/null; then "
                f"  if grep -Ev '^[[:space:]]*(#|$)|^[A-Za-z_][A-Za-z0-9_]*=' \"$tmp\" | grep -q .; then "
                f"    rm -f \"$tmp\"; exit 9; "
                f"  fi; "
                f"fi; rm -f \"$tmp\"; "
                f"crontab -u {shlex.quote(user)} {shlex.quote(staged)}"
            ),
            timeout=60,
            check=False,
        )
        if check.returncode != 0:
            raise ServerMigrationError(f"target user cron activation failed: {user}")
        row["activated"] = True
        save_state(state)

    for row in state.get("pending_pm2", []):
        if row.get("activated"):
            continue
        user = str(row["user"])
        staged = str(row["staged_target"])
        proc = target_python(
            state,
            "_target-activate-pm2",
            "--user", user,
            "--dump", staged,
            timeout=300,
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ServerMigrationError("target PM2 activation returned invalid result") from exc
        if payload.get("status") != "PM2_ACTIVATED":
            raise ServerMigrationError(f"target PM2 activation failed: {user}")
        row["activated"] = True
        save_state(state)

    for row in state.get("pending_system_cron", []):
        if row.get("activated"):
            continue
        destination = str(row["source_path"])
        staged = str(row["staged_target"])
        if not destination.startswith("/etc/cron.d/"):
            raise ServerMigrationError("unsafe target system cron path")
        check = remote(state, f"test ! -e {shlex.quote(destination)}", timeout=30, check=False)
        if check.returncode != 0:
            raise ServerMigrationError(f"target system cron already exists: {destination}")
        remote(
            state,
            f"install -o root -g root -m 644 {shlex.quote(staged)} {shlex.quote(destination)}",
            timeout=30,
        )
        row["activated"] = True
        save_state(state)

    state["target_runtime_activated"] = True
    save_state(state)


def deactivate_target_runtime(state: dict[str, Any]) -> bool:
    ok = True

    for row in state.get("pending_system_cron", []):
        if not row.get("activated"):
            continue
        proc = remote(
            state,
            f"rm -f -- {shlex.quote(str(row['source_path']))}",
            timeout=30,
            check=False,
        )
        if proc.returncode == 0:
            row["activated"] = False
            save_state(state)
        else:
            ok = False

    for row in state.get("pending_user_cron", []):
        if not row.get("activated"):
            continue
        user = str(row["user"])
        proc = remote(
            state,
            f"crontab -u {shlex.quote(user)} -r >/dev/null 2>&1 || true",
            timeout=30,
            check=False,
        )
        if proc.returncode == 0:
            row["activated"] = False
            save_state(state)
        else:
            ok = False

    for row in state.get("pending_pm2", []):
        if not row.get("activated"):
            continue
        user = str(row["user"])
        staged = str(row["staged_target"])
        try:
            proc = target_python(
                state,
                "_target-stop-pm2",
                "--user", user,
                "--dump", staged,
                timeout=300,
            )
            payload = json.loads(proc.stdout)
        except (ServerMigrationError, json.JSONDecodeError):
            ok = False
            continue
        if payload.get("status") == "PM2_STOPPED":
            row["activated"] = False
            save_state(state)
        else:
            ok = False

    remaining = any(
        row.get("activated")
        for key in ("pending_system_cron", "pending_user_cron", "pending_pm2")
        for row in state.get(key, [])
        if isinstance(row, dict)
    )
    state["target_runtime_activated"] = remaining
    save_state(state)
    return ok and not remaining


def remote_inventory(state: dict[str, Any]) -> dict[str, Any]:
    command = f"{shlex.quote(state['target_runtime_path'] + '/bin/vfops')} inventory --compact"
    proc = remote(state, command, timeout=300)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ServerMigrationError("target inventory is invalid") from exc
    return payload


def smoke_target(state: dict[str, Any]) -> dict[str, int]:
    target_manifest = remote_inventory(state)
    site_map = {
        str(item.get("domain")): item
        for item in target_manifest.get("sites", [])
        if isinstance(item, dict)
    }
    passed = failed = 0
    for source_site in state["sites"]:
        domain = str(source_site["domain"])
        target_site = site_map.get(domain)
        if not target_site:
            failed += 1
            continue
        compare = cutover.compare_site(source_site, target_site, domain)
        # Full-server TLS is finalized only after the OWNER DNS Gate. A clean
        # TARGET may temporarily use CloudPanel's placeholder/self-signed
        # certificate, so pre-DNS smoke must not turn ssl.configured parity into
        # a false cutover blocker. Public HTTPS/TLS verification in finalize is
        # the certificate authority.
        for check in compare.get("checks", []):
            if isinstance(check, dict) and check.get("field") == "ssl.configured":
                check["status"] = "DEFERRED"
        compare["failures"] = [
            field
            for field in compare.get("failures", [])
            if field != "ssl.configured"
        ]
        compare["unknowns"] = [
            field
            for field in compare.get("unknowns", [])
            if field != "ssl.configured"
        ]
        compare["status"] = (
            "FAIL"
            if compare["failures"]
            else ("UNKNOWN" if compare["unknowns"] else "PASS")
        )
        # Runtime is active now; Cron/PM2 and business assets must match.
        if compare.get("status") != "PASS":
            failed += 1
            continue
        command = (
            "curl -kLsS --connect-timeout 10 --max-time 30 "
            f"--resolve {shlex.quote(domain + ':443:127.0.0.1')} "
            "-o /dev/null -w '%{http_code}' "
            f"{shlex.quote('https://' + domain + '/')}"
        )
        proc = remote(state, command, timeout=45, check=False)
        code = proc.stdout.strip()[-3:]
        if proc.returncode == 0 and code.isdigit() and 200 <= int(code) < 400:
            passed += 1
        else:
            failed += 1
    if failed:
        raise ServerMigrationError(f"target final smoke failed: pass={passed} fail={failed}")
    return {"pass": passed, "fail": failed}


def cutover_migration(mid: str, confirm: str) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("status") not in {"PREPARED", "CUTOVER_RUNNING"}:
        raise ServerMigrationError(
            "migration is not in PREPARED/CUTOVER_RUNNING state"
        )
    if confirm != f"CUTOVER_SERVER:{mid}":
        raise ServerMigrationError(f"explicit confirmation required: CUTOVER_SERVER:{mid}")

    if state.get("status") == "PREPARED":
        state["status"] = "CUTOVER_RUNNING"
        state["cutover_started_at"] = now_utc()
        save_state(state)
    try:
        freeze_source_runtime(state)
        sync_site_roots_final(state)
        state["external_paths_synced_final"] = sync_external_paths(state, delete=True)
        state["mysql_final_count"] = final_mysql_sync(state)
        state["sqlite_snapshot_count_final"] = sync_sqlite_snapshots(state)
        remote_activate_runtime(state)
        state["target_smoke"] = smoke_target(state)
        state["status"] = "CUTOVER_PREP_READY"
        state["dns_manual_gate_required"] = True
        state["target_ip_for_dns"] = state["target"]["ip"]
        state["source_delete_allowed"] = False
        save_state(state)
        return state
    except Exception as exc:
        target_ok = deactivate_target_runtime(state)
        source_ok = restore_source_runtime(state)
        state["status"] = "CUTOVER_FAILED_ROLLED_BACK" if target_ok and source_ok else "CUTOVER_FAILED_ROLLBACK_PARTIAL"
        state["last_error_class"] = exc.__class__.__name__
        save_state(state)
        if isinstance(exc, ServerMigrationError):
            raise
        raise ServerMigrationError("server cutover failed") from exc


def create_target_markers(state: dict[str, Any], token: str) -> list[tuple[str, str]]:
    target_manifest = remote_inventory(state)
    mapping: list[tuple[str, str]] = []
    for site in state["sites"]:
        domain = str(site["domain"])
        target_site = cutover.find_site(target_manifest, domain)
        docroot = str(target_site.get("document_root", ""))
        if not docroot.startswith("/home/"):
            docroot = str(target_site.get("site_root", ""))
        if not docroot.startswith("/home/"):
            raise ServerMigrationError(f"target document root is unsafe: {domain}")
        filename = f".vfops-cutover-proof-{token}.txt"
        path = str(Path(docroot) / filename)
        remote(
            state,
            f"printf '%s\\n' {shlex.quote(token)} > {shlex.quote(path)} && chmod 644 {shlex.quote(path)}",
            timeout=30,
        )
        mapping.append((domain, path))
    return mapping


def remove_target_markers(state: dict[str, Any], mapping: list[tuple[str, str]]) -> None:
    for _, path in mapping:
        remote(state, f"rm -f -- {shlex.quote(path)}", timeout=30, check=False)


def public_route_proof(state: dict[str, Any], *, attempts: int, delay: float) -> dict[str, Any]:
    token = hashlib.sha256(f"{state['migration_id']}:{time.time_ns()}".encode()).hexdigest()[:24]
    mapping = create_target_markers(state, token)
    try:
        pending = {domain for domain, _ in mapping}
        codes: dict[str, str] = {}
        for _ in range(max(1, attempts)):
            for domain in list(pending):
                url = f"https://{domain}/.vfops-cutover-proof-{token}.txt?t={token}"
                proc = run_local(
                    [
                        "curl", "-kLsS", "--connect-timeout", "10", "--max-time", "30",
                        "-H", "Cache-Control: no-cache, no-store", url,
                    ],
                    timeout=45,
                    check=False,
                )
                body = proc.stdout.strip()
                codes[domain] = "PASS" if proc.returncode == 0 and body == token else "WAIT"
                if codes[domain] == "PASS":
                    pending.remove(domain)
            if not pending:
                break
            time.sleep(max(0.0, delay))
        result = {
            "status": "PASS" if not pending else "WAITING_DNS",
            "pass": len(mapping) - len(pending),
            "fail": len(pending),
            "pending": sorted(pending),
        }
        return result
    finally:
        remove_target_markers(state, mapping)


def source_pm2_daemon_present(
    user: str,
    *,
    home_root: Path = Path("/home"),
    proc_root: Path = Path("/proc"),
) -> bool:
    home = home_root / user
    try:
        uid = home.stat().st_uid
    except OSError as exc:
        raise ServerMigrationError(
            f"cannot resolve source PM2 user identity: {user}"
        ) from exc

    try:
        proc_dirs = list(proc_root.iterdir())
    except OSError as exc:
        raise ServerMigrationError("cannot inspect source process table") from exc

    pm2_home = str(home / ".pm2")
    for proc_dir in proc_dirs:
        if not proc_dir.name.isdigit():
            continue
        try:
            if proc_dir.stat().st_uid != uid:
                continue
            raw = (proc_dir / "cmdline").read_bytes()
        except (OSError, PermissionError):
            continue
        command = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")
        if "PM2" in command and (
            "God Daemon" in command or pm2_home in command
        ):
            return True
    return False


def public_production_check(state: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for site in state["sites"]:
        domain = str(site["domain"])
        proc = run_local(
            [
                "curl", "-LsS", "--connect-timeout", "10", "--max-time", "30",
                "-o", "/dev/null", "-w", "%{http_code}|%{ssl_verify_result}|%{remote_ip}",
                f"https://{domain}/",
            ],
            timeout=45,
            check=False,
        )
        parts = proc.stdout.strip().split("|", 2)
        code = parts[0] if parts else "000"
        tls = parts[1] if len(parts) >= 2 else "999"
        remote_ip = parts[2] if len(parts) >= 3 else ""
        passed = proc.returncode == 0 and code.isdigit() and 200 <= int(code) < 400 and tls == "0"
        results.append({
            "domain": domain,
            "http_code": code,
            "tls_verify": tls,
            "remote_ip": remote_ip,
            "curl_exit": proc.returncode,
            "status": "PASS" if passed else "FAIL",
        })
        if not passed:
            failures.append(domain)

    source_nginx = run_local(["systemctl", "is-active", "nginx"], timeout=30, check=False)
    if source_nginx.returncode == 0:
        failures.append("SOURCE_NGINX_ACTIVE")

    for row in state.get("source_system_cron_saved", []):
        if Path(row["source_path"]).exists():
            failures.append("SOURCE_SYSTEM_CRON_ACTIVE")

    for row in state.get("pending_user_cron", []):
        user = str(row.get("user", ""))
        if not user:
            failures.append("SOURCE_USER_CRON_UNKNOWN")
            continue
        try:
            exists, content = runtime_engine.current_crontab("crontab", user)
        except runtime_engine.RuntimeActivationError:
            failures.append(f"SOURCE_USER_CRON_UNKNOWN:{user}")
            continue
        if exists and runtime_engine.meaningful_cron(content):
            failures.append(f"SOURCE_USER_CRON_ACTIVE:{user}")

    for row in state.get("pending_pm2", []):
        user = str(row.get("user", ""))
        if not user:
            failures.append("SOURCE_PM2_UNKNOWN")
            continue
        try:
            active = source_pm2_daemon_present(user)
        except ServerMigrationError:
            failures.append(f"SOURCE_PM2_UNKNOWN:{user}")
            continue
        if active:
            failures.append(f"SOURCE_PM2_ACTIVE:{user}")

    return {
        "status": "PASS" if not failures else "FAIL",
        "site_pass": sum(1 for item in results if item["status"] == "PASS"),
        "site_fail": sum(1 for item in results if item["status"] == "FAIL"),
        "results": results,
        "failures": failures,
    }



def attempt_direct_tls_repair(
    state: dict[str, Any],
    production: dict[str, Any],
) -> dict[str, Any]:
    target_ip = str(state["target"]["ip"])
    attempted: list[str] = []
    repaired: list[str] = []
    skipped: list[str] = []

    for row in production.get("results", []):
        if not isinstance(row, dict) or row.get("status") == "PASS":
            continue
        domain = str(row.get("domain", ""))
        if not domain or str(row.get("tls_verify")) == "0":
            skipped.append(domain)
            continue

        probe = run_local(
            [
                "curl", "-kLsS", "--connect-timeout", "10", "--max-time", "30",
                "-o", "/dev/null", "-w", "%{http_code}|%{remote_ip}",
                f"https://{domain}/",
            ],
            timeout=45,
            check=False,
        )
        parts = probe.stdout.strip().split("|", 1)
        code = parts[0] if parts else "000"
        remote_ip = parts[1] if len(parts) == 2 else ""
        direct_and_alive = (
            probe.returncode == 0
            and code.isdigit()
            and 200 <= int(code) < 400
            and remote_ip == target_ip
        )
        if not direct_and_alive:
            skipped.append(domain)
            continue

        attempted.append(domain)
        proc = remote(
            state,
            "clpctl lets-encrypt:install:certificate "
            f"--domainName={shlex.quote(domain)}",
            timeout=1800,
            check=False,
        )
        if proc.returncode == 0:
            repaired.append(domain)

    return {
        "attempted": attempted,
        "repaired": repaired,
        "skipped": sorted(set(skipped)),
        "status": "REPAIRED" if attempted and len(repaired) == len(attempted) else (
            "PARTIAL" if repaired else "NOT_APPLICABLE"
        ),
    }



def cleanup_managed_ssh_identity(state: dict[str, Any]) -> dict[str, Any]:
    target = state.get("target") if isinstance(state.get("target"), dict) else {}
    identity_text = target.get("identity_file")
    managed = target.get("managed_identity_file") is True
    if not managed or not isinstance(identity_text, str) or not identity_text:
        return {
            "status": "NOT_MANAGED",
            "remote_key_removed": False,
            "local_key_removed": False,
        }

    identity = Path(identity_text).expanduser().resolve()
    public_file = Path(str(identity) + ".pub")
    marker_file = Path(str(identity) + ".vfops-managed")

    # If the TARGET authorization was already removed in a previous attempt,
    # retry only local cleanup. The old key can no longer authenticate remotely,
    # so reconnecting with it would turn a recoverable local-cleanup partial into
    # a false remote failure.
    if state.get("managed_ssh_key_cleanup") in {"REMOTE_REMOVED", "LOCAL_REMOVE_PARTIAL"}:
        local_ok = True
        for path in (public_file, identity, marker_file):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                local_ok = False
        state["managed_ssh_key_cleanup"] = (
            "PASS" if local_ok else "LOCAL_REMOVE_PARTIAL"
        )
        save_state(state)
        return {
            "status": state["managed_ssh_key_cleanup"],
            "remote_key_removed": True,
            "local_key_removed": local_ok,
        }
    try:
        marker_value = marker_file.read_text(encoding="utf-8").strip()
    except OSError:
        return {
            "status": "REFUSED_UNPROVEN_MANAGED_KEY",
            "remote_key_removed": False,
            "local_key_removed": False,
        }
    if marker_value != "VFOPS_MANAGED_MIGRATION_KEY_V1":
        return {
            "status": "REFUSED_UNPROVEN_MANAGED_KEY",
            "remote_key_removed": False,
            "local_key_removed": False,
        }
    if not identity.is_file():
        return {
            "status": "LOCAL_PRIVATE_KEY_MISSING",
            "remote_key_removed": False,
            "local_key_removed": False,
        }

    proc = run_local(
        ["ssh-keygen", "-y", "-f", str(identity)],
        timeout=30,
        check=False,
    )
    public_parts = proc.stdout.strip().split()
    if proc.returncode != 0 or len(public_parts) < 2:
        return {
            "status": "PUBLIC_KEY_DERIVATION_FAILED",
            "remote_key_removed": False,
            "local_key_removed": False,
        }
    key_type, key_blob = public_parts[0], public_parts[1]

    state["managed_ssh_key_cleanup"] = "REMOVAL_INTENT"
    save_state(state)
    code = (
        "from pathlib import Path; import os,sys,tempfile; "
        "p=Path('/root/.ssh/authorized_keys'); "
        "kt,kb=sys.argv[1],sys.argv[2]; "
        "\nif p.exists():\n"
        "    lines=p.read_text(encoding='utf-8',errors='replace').splitlines(True)\n"
        "    kept=[]\n"
        "    for line in lines:\n"
        "        parts=line.strip().split()\n"
        "        if len(parts)>=2 and parts[0]==kt and parts[1]==kb: continue\n"
        "        kept.append(line)\n"
        "    fd,tmp=tempfile.mkstemp(prefix='.authorized_keys.',dir=str(p.parent))\n"
        "    with os.fdopen(fd,'w',encoding='utf-8') as h: h.writelines(kept); h.flush(); os.fsync(h.fileno())\n"
        "    os.chmod(tmp,0o600); os.replace(tmp,p)\n"
    )
    remove_proc = remote(
        state,
        f"python3 -c {shlex.quote(code)} {shlex.quote(key_type)} {shlex.quote(key_blob)}",
        timeout=60,
        check=False,
    )
    if remove_proc.returncode != 0:
        state["managed_ssh_key_cleanup"] = "REMOTE_REMOVE_FAILED"
        save_state(state)
        return {
            "status": "REMOTE_REMOVE_FAILED",
            "remote_key_removed": False,
            "local_key_removed": False,
        }

    state["managed_ssh_key_cleanup"] = "REMOTE_REMOVED"
    save_state(state)
    local_ok = True
    for path in (public_file, identity, marker_file):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            local_ok = False
    state["managed_ssh_key_cleanup"] = (
        "PASS" if local_ok else "LOCAL_REMOVE_PARTIAL"
    )
    save_state(state)
    return {
        "status": state["managed_ssh_key_cleanup"],
        "remote_key_removed": True,
        "local_key_removed": local_ok,
    }


def cleanup_target_staging(state: dict[str, Any]) -> bool:
    root = f"/var/lib/vf-server-ops/server-migrations/{state['migration_id']}"
    try:
        proc = remote(
            state,
            f"rm -rf -- {shlex.quote(root)}",
            timeout=300,
            check=False,
        )
    except (
        ServerMigrationError,
        transport.TransportError,
        OSError,
        subprocess.SubprocessError,
    ):
        return False
    return proc.returncode == 0


def finalize_migration(mid: str, confirm: str, *, attempts: int, delay: float) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("status") not in {"CUTOVER_PREP_READY", "WAITING_DNS", "PRODUCTION_VERIFY_FAILED"}:
        raise ServerMigrationError("migration is not waiting for DNS/final verification")
    if confirm != f"DNS_UPDATED:{mid}":
        raise ServerMigrationError(f"explicit confirmation required: DNS_UPDATED:{mid}")

    route = public_route_proof(state, attempts=attempts, delay=delay)
    state["public_route_proof"] = route
    if route["status"] != "PASS":
        state["status"] = "WAITING_DNS"
        save_state(state)
        return state

    production = public_production_check(state)
    state["production_verification"] = production
    if production["status"] != "PASS":
        repair = attempt_direct_tls_repair(state, production)
        state["tls_repair"] = repair
        if repair.get("repaired"):
            production = public_production_check(state)
            state["production_verification"] = production
    if production["status"] != "PASS":
        state["status"] = "PRODUCTION_VERIFY_FAILED"
        save_state(state)
        raise ServerMigrationError("public production verification failed")

    # Production proof is authoritative. Persist PASS before non-critical
    # housekeeping so a transient SSH failure while deleting private staging
    # cannot erase a completed public/TLS/runtime verification result.
    state["status"] = "PRODUCTION_PASS"
    state["production_passed_at"] = now_utc()
    state["source_retained_for_rollback"] = True
    state["source_delete_allowed"] = False
    state["dns_changed_by_p07"] = False
    target = state.get("target") if isinstance(state.get("target"), dict) else {}
    state["managed_ssh_key_cleanup"] = (
        "RETAINED_FOR_RECOVERY"
        if target.get("managed_identity_file") is True
        else "NOT_MANAGED"
    )
    state["recovery_protection_key_active"] = (
        target.get("managed_identity_file") is True
    )
    state["target_staging_cleanup"] = "PENDING"
    save_state(state)

    cleaned = cleanup_target_staging(state)
    state["target_staging_cleanup"] = "PASS" if cleaned else "RETRY_REQUIRED"
    save_state(state)
    return state


def cleanup_managed_key_after_recovery_window(
    mid: str,
    confirm: str,
) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("status") not in {"PRODUCTION_PASS", "ROLLED_BACK"}:
        raise ServerMigrationError(
            "managed migration key cleanup is allowed only after Production PASS or rollback"
        )
    required = f"CLEANUP_MANAGED_SSH_KEY:{mid}"
    if confirm != required:
        raise ServerMigrationError(f"explicit confirmation required: {required}")
    # Use the still-authorized P07 recovery channel for one last best-effort
    # private staging cleanup before intentionally removing that channel.
    if state.get("target_staging_cleanup") != "PASS":
        cleaned = cleanup_target_staging(state)
        state["target_staging_cleanup"] = (
            "PASS" if cleaned else "RETRY_REQUIRED"
        )
        save_state(state)
        if not cleaned:
            raise ServerMigrationError(
                "target private staging cleanup must pass before removing the P07 recovery SSH key"
            )

    result = cleanup_managed_ssh_identity(state)
    state["managed_ssh_key_cleanup_result"] = result
    if result.get("remote_key_removed") is True:
        state["recovery_protection_key_active"] = False
        state["recovery_protection_key_closed_at"] = now_utc()
    save_state(state)
    return state


def rollback_migration(mid: str, confirm: str) -> dict[str, Any]:
    state = load_state(mid)
    if state.get("status") != "CUTOVER_PREP_READY":
        raise ServerMigrationError(
            "automatic rollback is allowed only before the DNS handoff; "
            "post-DNS rollback requires TARGET-to-SOURCE data reconciliation"
        )
    target = state.get("target") if isinstance(state.get("target"), dict) else {}
    if (
        target.get("managed_identity_file") is True
        and state.get("recovery_protection_key_active") is False
    ):
        raise ServerMigrationError(
            "P07-managed TARGET recovery key is no longer available after the recovery window"
        )
    if confirm != f"ROLLBACK_SERVER:{mid}":
        raise ServerMigrationError(f"explicit confirmation required: ROLLBACK_SERVER:{mid}")
    target_ok = deactivate_target_runtime(state)
    source_ok = restore_source_runtime(state)
    state["status"] = "ROLLED_BACK" if target_ok and source_ok else "ROLLBACK_PARTIAL"
    state["dns_rollback_required_if_already_changed"] = True
    state["target_sites_retained"] = True
    state["source_delete_allowed"] = False
    save_state(state)
    return state


def target_activate_pm2_local(user: str, staged_dump: Path) -> dict[str, Any]:
    if not staged_dump.is_file():
        raise ServerMigrationError("staged PM2 dump is unavailable")
    try:
        pm2_cmd, path_env = runtime_engine.resolve_site_user_nvm_pm2(user, staged_dump)
    except runtime_engine.RuntimeActivationError as exc:
        raise ServerMigrationError("target PM2 prerequisite is unavailable") from exc

    home = Path("/home") / user
    pm2_home = home / ".pm2"
    pm2_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    final_dump = pm2_home / "dump.pm2"
    shutil.copy2(staged_dump, final_dump)
    owner = home.stat()
    os.chown(pm2_home, owner.st_uid, owner.st_gid)
    os.chown(final_dump, owner.st_uid, owner.st_gid)
    os.chmod(final_dump, 0o600)
    proc = subprocess.run(
        [
            "runuser", "-u", user, "--", "/usr/bin/env",
            f"HOME={home}", f"PM2_HOME={pm2_home}", f"PATH={path_env}",
            pm2_cmd, "resurrect",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    if proc.returncode != 0:
        final_dump.unlink(missing_ok=True)
        raise ServerMigrationError("target PM2 resurrect failed")
    return {"status": "PM2_ACTIVATED", "user": user, "secrets_emitted": False}


def target_stop_pm2_local(user: str, staged_dump: Path) -> dict[str, Any]:
    try:
        pm2_cmd, path_env = runtime_engine.resolve_site_user_nvm_pm2(
            user, staged_dump
        )
    except runtime_engine.RuntimeActivationError as exc:
        raise ServerMigrationError(
            f"target PM2 rollback prerequisite is unavailable: {user}"
        ) from exc
    home = Path("/home") / user
    env = [f"HOME={home}", f"PM2_HOME={home / '.pm2'}", f"PATH={path_env}"]
    if not runtime_engine.best_effort_pm2_shutdown(
        "runuser", user, env, pm2_cmd, home
    ):
        raise ServerMigrationError(f"target PM2 rollback failed: {user}")
    return {
        "status": "PM2_STOPPED",
        "user": user,
        "secrets_emitted": False,
    }


def target_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.ssh_user != "root":
        raise ServerMigrationError("full-server migration currently requires root SSH on TARGET")
    host = transport.validate_host(args.target_host or args.target_ip)
    ip = transport.validate_ip(args.target_ip)
    port = transport.validate_port(args.ssh_port)
    identity = None
    if args.identity_file:
        identity = str(Path(args.identity_file).expanduser().resolve())
        if not Path(identity).is_file():
            raise ServerMigrationError("SSH identity file does not exist")
    return {
        "host": host,
        "ip": ip,
        "ssh_user": args.ssh_user,
        "ssh_port": port,
        "identity_file": identity,
        "managed_identity_file": bool(getattr(args, "managed_identity_file", False)),
        "ssh": args.ssh,
    }


def add_target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target-ip", required=True)
    parser.add_argument("--target-host")
    parser.add_argument("--ssh-user", default="root")
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument("--identity-file")
    parser.add_argument("--managed-identity-file", action="store_true")
    parser.add_argument("--ssh", default=os.environ.get("VFOPS_SSH", "ssh"))
    parser.add_argument("--site", action="append", default=[])


def summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": state.get("schema"),
        "migration_id": state.get("migration_id"),
        "status": state.get("status"),
        "site_count": len(state.get("sites", [])),
        "target_ip": (state.get("target") or {}).get("ip"),
        "mysql_final_count": state.get("mysql_final_count"),
        "sqlite_snapshot_count_prepare": state.get("sqlite_snapshot_count_prepare"),
        "sqlite_snapshot_count_final": state.get("sqlite_snapshot_count_final"),
        "target_smoke": state.get("target_smoke"),
        "public_route_proof": state.get("public_route_proof"),
        "production_verification": state.get("production_verification"),
        "dns_manual_gate_required": state.get("dns_manual_gate_required", False),
        "source_retained_for_rollback": state.get("source_retained_for_rollback", False),
        "source_external_listeners": state.get("source_external_listeners", []),
        "source_decommission_safe": not bool(state.get("source_external_listeners", [])),
        "managed_ssh_key_cleanup": state.get("managed_ssh_key_cleanup", "NOT_RUN"),
        "recovery_protection_key_active": state.get("recovery_protection_key_active"),
        "recovery_protection_key_closed_at": state.get("recovery_protection_key_closed_at"),
        "target_staging_cleanup": state.get("target_staging_cleanup", "NOT_RUN"),
        "source_delete_allowed": False,
        "dns_changed_by_p07": False,
        "secrets_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P07 full CloudPanel server migration orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="read-only full-server migration preflight")
    add_target_args(plan)

    bootstrap = sub.add_parser(
        "bootstrap-target",
        help="guarded CloudPanel install on a verified empty target",
    )
    add_target_args(bootstrap)
    bootstrap.add_argument("--confirm", required=True)

    prepare = sub.add_parser("prepare", help="stage selected/all sites on a clean target with runtime deferred")
    add_target_args(prepare)
    prepare.add_argument("--confirm", required=True)

    resume = sub.add_parser("resume", help="resume an interrupted prepare stage")
    resume.add_argument("--migration-id", required=True)

    cut = sub.add_parser("cutover", help="freeze source, final-sync data, activate target runtime, stop before DNS")
    cut.add_argument("--migration-id", required=True)
    cut.add_argument("--confirm", required=True)

    final = sub.add_parser("finalize", help="prove public route after manual DNS and run production verification")
    final.add_argument("--migration-id", required=True)
    final.add_argument("--confirm", required=True)
    final.add_argument("--attempts", type=int, default=12)
    final.add_argument("--delay", type=float, default=5.0)

    rollback = sub.add_parser("rollback", help="restore source runtime without deleting target")
    rollback.add_argument("--migration-id", required=True)
    rollback.add_argument("--confirm", required=True)

    status = sub.add_parser("status", help="show secret-safe migration state summary")
    status.add_argument("--migration-id", required=True)

    cleanup_key = sub.add_parser(
        "cleanup-managed-key",
        help="remove only the P07-managed migration SSH key after rollback protection",
    )
    cleanup_key.add_argument("--migration-id", required=True)
    cleanup_key.add_argument("--confirm", required=True)

    target_site = sub.add_parser("_target-create-site", help=argparse.SUPPRESS)
    target_site.add_argument("--migration-id", required=True)
    target_site.add_argument("--site-file", required=True)

    target_db = sub.add_parser("_target-create-database", help=argparse.SUPPRESS)
    target_db.add_argument("--migration-id", required=True)
    target_db.add_argument("--domain", required=True)
    target_db.add_argument("--site-root", required=True)
    target_db.add_argument("--database", required=True)
    target_db.add_argument("--index", type=int, required=True)
    target_db.add_argument("--dump", required=True)

    target_cleanup = sub.add_parser("_target-cleanup-site", help=argparse.SUPPRESS)
    target_cleanup.add_argument("--migration-id", required=True)
    target_cleanup.add_argument("--domain", required=True)
    target_cleanup.add_argument("--database", action="append", default=[])

    target_pm2 = sub.add_parser("_target-activate-pm2", help=argparse.SUPPRESS)
    target_pm2.add_argument("--user", required=True)
    target_pm2.add_argument("--dump", required=True)

    target_pm2_stop = sub.add_parser("_target-stop-pm2", help=argparse.SUPPRESS)
    target_pm2_stop.add_argument("--user", required=True)
    target_pm2_stop.add_argument("--dump", required=True)

    args = parser.parse_args()
    try:
        if args.command == "plan":
            result = plan_payload(target_from_args(args), args.site)
        elif args.command == "bootstrap-target":
            result = bootstrap_target_cloudpanel(
                target_from_args(args),
                args.confirm,
            )
        elif args.command == "prepare":
            result = summary(prepare_migration(target_from_args(args), args.site, args.confirm))
        elif args.command == "resume":
            result = summary(resume_prepare_migration(args.migration_id))
        elif args.command == "cutover":
            result = summary(cutover_migration(args.migration_id, args.confirm))
        elif args.command == "finalize":
            result = summary(finalize_migration(args.migration_id, args.confirm, attempts=args.attempts, delay=args.delay))
        elif args.command == "rollback":
            result = summary(rollback_migration(args.migration_id, args.confirm))
        elif args.command == "cleanup-managed-key":
            result = summary(
                cleanup_managed_key_after_recovery_window(
                    args.migration_id,
                    args.confirm,
                )
            )
        elif args.command == "_target-create-site":
            result = target_create_site_local(args.migration_id, Path(args.site_file))
        elif args.command == "_target-create-database":
            result = target_create_database_local(
                args.migration_id,
                args.domain,
                Path(args.site_root),
                args.database,
                args.index,
                Path(args.dump),
            )
        elif args.command == "_target-cleanup-site":
            result = target_cleanup_site_local(
                args.migration_id, args.domain, list(args.database)
            )
        elif args.command == "_target-activate-pm2":
            result = target_activate_pm2_local(args.user, Path(args.dump))
        elif args.command == "_target-stop-pm2":
            result = target_stop_pm2_local(args.user, Path(args.dump))
        else:
            result = summary(load_state(args.migration_id))
    except (
        ServerMigrationError,
        transport.TransportError,
        runtime_engine.RuntimeActivationError,
        cloudpanel.CloudPanelError,
        RuntimeError,
        OSError,
        subprocess.SubprocessError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 17

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.command == "finalize" and result.get("status") == "WAITING_DNS":
        return 18
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
