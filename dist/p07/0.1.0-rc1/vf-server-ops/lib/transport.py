#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any

import package as package_engine

SCHEMA = "vf-server-ops.migration-transport.v1"
ROOT = Path(__file__).resolve().parents[1]
REMOTE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
REMOTE_USER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$" )
TARGET_FAILURE_STAGE_RE = re.compile(r"\bstage=([A-Z0-9_]+)\b")
SAFE_DIAGNOSTIC_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,95}$")


class TransportError(RuntimeError):
    pass


def validate_host(value: str) -> str:
    value = value.strip()
    if not value or any(ch.isspace() for ch in value) or value.startswith("-"):
        raise TransportError("invalid target host")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        if not HOST_RE.fullmatch(value):
            raise TransportError("invalid target host")
    return value


def validate_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError as exc:
        raise TransportError("invalid target IP") from exc


def validate_user(value: str) -> str:
    if not REMOTE_USER_RE.fullmatch(value or ""):
        raise TransportError("invalid SSH user")
    return value


def validate_port(value: int) -> int:
    if value < 1 or value > 65535:
        raise TransportError("invalid SSH port")
    return value


def load_verified_identity(package_dir: Path) -> tuple[dict[str, Any], str, str]:
    package_dir = package_dir.expanduser().resolve()
    fresh = package_engine.verify_package(package_dir)
    if fresh.get("status") != "PASS":
        raise TransportError("source backup package failed fresh verification")
    try:
        manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TransportError("backup manifest is missing or invalid") from exc
    site = manifest.get("site") if isinstance(manifest.get("site"), dict) else {}
    domain = site.get("domain")
    backup_id = manifest.get("backup_id")
    if not isinstance(domain, str) or not domain:
        raise TransportError("backup domain is missing")
    if not isinstance(backup_id, str) or not REMOTE_NAME_RE.fullmatch(backup_id):
        raise TransportError("backup id is unsafe for transport")
    if package_dir.name != backup_id:
        raise TransportError("backup directory name does not match backup id")
    return manifest, domain, backup_id


def expected_confirmation(domain: str, backup_id: str) -> str:
    return f"MIGRATE_NEW_SITE:{domain}:{backup_id}"


def endpoint_hash(user: str, host: str, port: int) -> str:
    raw = f"{user}@{host}:{port}".encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:16]


def ssh_base(ssh: str, host: str, user: str, port: int, identity_file: Path | None) -> list[str]:
    args = [
        ssh,
        "-p", str(port),
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=2",
    ]
    if identity_file is not None:
        identity = identity_file.expanduser().resolve()
        if not identity.is_file():
            raise TransportError("SSH identity file does not exist")
        args.extend(["-i", str(identity)])
    args.append(f"{user}@{host}")
    return args


def remote_priv(user: str, command: str) -> str:
    if user == "root":
        return command
    return f"sudo -n sh -c {shlex.quote(command)}"


def run_ssh(base: list[str], command: str, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [*base, command],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise TransportError("SSH operation timed out") from exc
    except OSError as exc:
        raise TransportError("SSH executable is unavailable") from exc


def require_target_preflight(base: list[str], user: str, runtime_path: str, package_path: str) -> None:
    checks = (
        "set -eu; "
        "command -v clpctl >/dev/null 2>&1; "
        "test -f /home/clp/htdocs/app/data/db.sq3; "
        f"test ! -e {shlex.quote(runtime_path)}; "
        f"test ! -e {shlex.quote(package_path)}"
    )
    proc = run_ssh(base, remote_priv(user, checks), timeout=30)
    if proc.returncode != 0:
        raise TransportError("target CloudPanel/privilege/staging preflight failed")


def cleanup_remote_staging(base: list[str], user: str, runtime_path: str, package_path: str) -> bool:
    command = (
        "set -eu; "
        f"rm -rf -- {shlex.quote(runtime_path)} {shlex.quote(package_path)}; "
        f"test ! -e {shlex.quote(runtime_path)}; "
        f"test ! -e {shlex.quote(package_path)}"
    )
    try:
        proc = run_ssh(base, remote_priv(user, command), timeout=120)
    except TransportError:
        return False
    return proc.returncode == 0


def stream_tar_to_remote(
    tar: str,
    source_cwd: Path,
    members: list[str],
    base: list[str],
    remote_command: str,
    stage: str,
) -> None:
    try:
        producer = subprocess.Popen(
            [tar, "-C", str(source_cwd), "-czf", "-", *members],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise TransportError("tar executable is unavailable") from exc
    assert producer.stdout is not None
    try:
        consumer = subprocess.run(
            [*base, remote_command],
            stdin=producer.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=3600,
        )
    except subprocess.TimeoutExpired as exc:
        producer.kill()
        producer.wait()
        raise TransportError(f"{stage} timed out") from exc
    except OSError as exc:
        producer.kill()
        producer.wait()
        raise TransportError("SSH executable is unavailable") from exc
    finally:
        producer.stdout.close()
    producer_stderr = producer.stderr.read() if producer.stderr is not None else b""
    producer_rc = producer.wait()
    if producer_rc != 0:
        raise TransportError(f"{stage} local archive failed")
    if consumer.returncode != 0:
        raise TransportError(f"{stage} remote transfer failed")
    if not members or consumer.stdout is None:
        raise TransportError(f"{stage} internal transport state invalid")
    _ = producer_stderr  # deliberately not emitted; archive stderr may contain private paths


def parse_remote_result(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise TransportError("target migration returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise TransportError("target migration returned invalid result")
    if payload.get("status") != "TECHNICAL_CUTOVER_READY":
        raise TransportError("target migration did not reach TECHNICAL_CUTOVER_READY")
    if payload.get("dns_changed") is not False:
        raise TransportError("target migration violated DNS safety invariant")
    if payload.get("old_server_delete_requested") is not False:
        raise TransportError("target migration violated old-server safety invariant")
    if payload.get("technical_cutover_ready") is not True:
        raise TransportError("target migration readiness result is inconsistent")
    return payload


def safe_target_failure_stage(stderr: str) -> str | None:
    match = TARGET_FAILURE_STAGE_RE.search(stderr or "")
    return match.group(1) if match else None


def safe_diagnostic_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if SAFE_DIAGNOSTIC_SYMBOL_RE.fullmatch(value) else None


def safe_target_failure_diagnostics(stdout: str, stderr: str) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    explicit_stage = safe_target_failure_stage(stderr)
    if explicit_stage:
        diagnostics["stage"] = explicit_stage

    try:
        payload = json.loads(stdout or "")
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict):
        if "stage" not in diagnostics:
            diagnostics["stage"] = "TARGET_MIGRATION"
        return diagnostics

    key_map = {
        "status": "target_status",
        "restore_status": "restore_status",
        "runtime_status": "runtime_status",
        "cross_server_status": "cross_server_status",
        "http_https_status": "http_https_status",
    }
    for source_key, output_key in key_map.items():
        safe = safe_diagnostic_symbol(payload.get(source_key))
        if safe:
            diagnostics[output_key] = safe

    blockers: list[str] = []
    raw_blockers = payload.get("blockers")
    if isinstance(raw_blockers, list):
        for item in raw_blockers[:16]:
            safe = safe_diagnostic_symbol(item)
            if safe and safe not in blockers:
                blockers.append(safe)
    if blockers:
        diagnostics["blockers"] = blockers

    if "stage" not in diagnostics:
        restore_status = diagnostics.get("restore_status")
        runtime_status = diagnostics.get("runtime_status")
        cross_status = diagnostics.get("cross_server_status")
        http_status = diagnostics.get("http_https_status")
        target_status = diagnostics.get("target_status")
        if restore_status and restore_status != "RESTORE_VERIFIED":
            diagnostics["stage"] = "RESTORE_VERIFY"
        elif runtime_status and runtime_status != "RUNTIME_ACTIVATED":
            diagnostics["stage"] = "RUNTIME_ACTIVATION"
        elif cross_status and cross_status != "PASS":
            diagnostics["stage"] = "CROSS_SERVER_VERIFY"
        elif http_status and http_status != "PASS":
            diagnostics["stage"] = "HTTP_HTTPS_TARGET_PROBE"
        elif target_status:
            diagnostics["stage"] = "TARGET_MIGRATION_NOT_READY"
        else:
            diagnostics["stage"] = "TARGET_MIGRATION"
    return diagnostics


def format_target_failure_diagnostics(diagnostics: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "stage",
        "target_status",
        "restore_status",
        "runtime_status",
        "cross_server_status",
        "http_https_status",
    ):
        value = diagnostics.get(key)
        if isinstance(value, str):
            parts.append(f"{key}={value}")
    blockers = diagnostics.get("blockers")
    if isinstance(blockers, list) and blockers:
        parts.append("blockers=" + ",".join(str(item) for item in blockers))
    return "; ".join(parts)


def transfer_new_site(
    package_dir: Path,
    target_host: str,
    target_ip: str,
    ssh_user: str,
    ssh_port: int,
    identity_file: Path | None,
    confirm: str,
    ssh: str,
    tar: str,
) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    _, domain, backup_id = load_verified_identity(package_dir)
    required = expected_confirmation(domain, backup_id)
    if confirm != required:
        raise TransportError(f"explicit confirmation required: {required}")

    host = validate_host(target_host)
    ip = validate_ip(target_ip)
    user = validate_user(ssh_user)
    port = validate_port(ssh_port)
    base = ssh_base(ssh, host, user, port, identity_file)

    runtime_path = f"/var/lib/vf-server-ops/transport-runtime/{backup_id}"
    incoming_root = "/var/lib/vf-server-ops/incoming"
    package_path = f"{incoming_root}/{backup_id}"
    require_target_preflight(base, user, runtime_path, package_path)

    runtime_parent = str(Path(runtime_path).parent)
    runtime_prepare = (
        "set -eu; "
        f"install -d -m 700 {shlex.quote(runtime_parent)}; "
        f"install -d -m 700 {shlex.quote(runtime_path)}; "
        f"tar -xzf - -C {shlex.quote(runtime_path)}; "
        f"chmod -R go-rwx {shlex.quote(runtime_path)}; "
        f"chmod 700 {shlex.quote(runtime_path + '/bin/vfops')}"
    )
    package_prepare = (
        "set -eu; "
        f"install -d -m 700 {shlex.quote(incoming_root)}; "
        f"tar -xzf - -C {shlex.quote(incoming_root)}; "
        f"chmod -R go-rwx {shlex.quote(package_path)}; "
        f"test -f {shlex.quote(package_path + '/manifest.json')}; "
        f"test -f {shlex.quote(package_path + '/verification.json')}"
    )

    staging_started = False
    cleanup_verified = False
    remote_result: dict[str, Any]
    try:
        staging_started = True
        stream_tar_to_remote(
            tar,
            ROOT,
            ["bin", "lib", "VERSION", "VF_PROJECT.json"],
            base,
            remote_priv(user, runtime_prepare),
            "runtime transfer",
        )
        stream_tar_to_remote(
            tar,
            package_dir.parent,
            [backup_id],
            base,
            remote_priv(user, package_prepare),
            "backup package transfer",
        )

        remote_vfops = f"{runtime_path}/bin/vfops"
        migrate_args = [
            remote_vfops,
            "migrate", "apply-new-site",
            "--package", package_path,
            "--target-ip", ip,
            "--confirm", required,
        ]
        remote_exec = " ".join(shlex.quote(value) for value in migrate_args)
        proc = run_ssh(base, remote_priv(user, remote_exec), timeout=3600)
        if proc.returncode != 0:
            diagnostics = safe_target_failure_diagnostics(proc.stdout, proc.stderr)
            rendered = format_target_failure_diagnostics(diagnostics)
            raise TransportError(
                "target migration execution failed" + (f"; {rendered}" if rendered else "")
            )
        remote_result = parse_remote_result(proc.stdout)

        if not cleanup_remote_staging(base, user, runtime_path, package_path):
            raise TransportError("target private staging cleanup failed")
        cleanup_verified = True
    except Exception:
        if staging_started and not cleanup_verified:
            cleanup_remote_staging(base, user, runtime_path, package_path)
        raise

    return {
        "schema": SCHEMA,
        "status": "TECHNICAL_CUTOVER_READY",
        "backup_id": backup_id,
        "domain": domain,
        "transport": "SSH_TAR_PRIVATE_STREAM",
        "target_endpoint": endpoint_hash(user, host, port),
        "target_ip": ip,
        "runtime_staged": True,
        "package_staged": True,
        "remote_private_staging_cleanup": "PASS",
        "runtime_staging_retained": False,
        "package_staging_retained": False,
        "target_migration_status": remote_result.get("status"),
        "restore_status": remote_result.get("restore_status"),
        "runtime_status": remote_result.get("runtime_status"),
        "cross_server_status": remote_result.get("cross_server_status"),
        "http_https_status": remote_result.get("http_https_status"),
        "technical_cutover_ready": True,
        "owner_cutover_gate_required": True,
        "dns_changed": False,
        "old_server_delete_requested": False,
        "existing_site_overwrite": False,
        "source_backup_deleted": False,
        "ssh_password_accepted": False,
        "host_key_policy": "STRICT_ACCEPT_NEW_REFUSE_CHANGED",
        "secrets_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops guarded source-to-target SSH transport")
    parser.add_argument("--package", required=True)
    parser.add_argument("--target-host", required=True)
    parser.add_argument("--target-ip", required=True)
    parser.add_argument("--ssh-user", default="root")
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument("--identity-file")
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--ssh", default=os.environ.get("VFOPS_SSH", "ssh"))
    parser.add_argument("--tar", default=os.environ.get("VFOPS_TAR", "tar"))
    args = parser.parse_args()
    try:
        result = transfer_new_site(
            Path(args.package),
            args.target_host,
            args.target_ip,
            args.ssh_user,
            args.ssh_port,
            Path(args.identity_file) if args.identity_file else None,
            args.confirm,
            args.ssh,
            args.tar,
        )
    except (TransportError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 13
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())