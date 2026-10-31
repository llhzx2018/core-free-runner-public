"""P07 R4 private, ephemeral Docker database restore proof (NOT cutover).

Requires an already installed daemon and an already available MariaDB 11.8
image. Docker is deliberately never installed or pulled by this module.
Each backup is streamed to a new networkless, read-only-root container with
only temporary memory-backed datadir/socket mounts. No host directory,
Docker socket, port, credential or production database is mounted.
All private bytes stay on the operator-controlled machine.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import secrets
import select
import shutil
import subprocess
import time
from typing import Any

import private_recovery_gate
import sql_diff_evidence
import restore_sql_preflight
import scratch_sql_host_policy

SCHEMA = "P07_ISOLATED_SQL_RESTORE_PROOF_V1"
IMAGE = "mariadb:11.8"
SQL_LIMIT = 512 * 1024 * 1024
_TIMEOUT = 240
_DATABASE = "vfops_isolated_restore"
_QUERY = (
    "SELECT COUNT(*) FROM information_schema.tables "
    "WHERE TABLE_TYPE='BASE TABLE' "
    "AND TABLE_SCHEMA NOT IN ('mysql','information_schema','performance_schema','sys')"
)


class Blocked(RuntimeError):
    pass


def _report(reason: str, *, source_tables: int = 0, target_tables: int = 0,
            verified_source: bool = False, verified_target: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": (
            "ISOLATED_RESTORE_IMPORT_VERIFIED_NOT_MIGRATION_READY"
            if verified_source and verified_target else "BLOCKED"
        ),
        "reason": reason,
        "backend": "DOCKER_MEMORY_ONLY_MARIADB_11_8",
        "source_tables_restored": source_tables,
        "target_tables_restored": target_tables,
        "actual_source_restore_verified": verified_source,
        "actual_target_restore_verified": verified_target,
        "independent_datadirs": verified_source and verified_target,
        "production_database_writes_performed": False,
        "host_site_or_mysql_metadata_modified": False,
        "source_runtime_frozen": False,
        "migration_state_modified": False,
        "dns_modified": False,
        "cross_engine_business_semantics_verified": False,
        "conflict_decisions_verified": False,
        "dynamic_sql_guards_approved": False,
        "migration_resume_allowed": False,
        "cutover_allowed": False,
        "verification": "ISOLATED_RESTORE_ONLY_NOT_A_MIGRATION_GATE",
    }


def _docker_ready() -> None:
    if not shutil.which("docker"):
        raise Blocked("ISOLATED_CONTAINER_RUNTIME_NOT_INSTALLED")
    for args, error in (
        (["docker", "info", "--format", "{{.ServerVersion}}"], "ISOLATED_DOCKER_DAEMON_UNAVAILABLE"),
        (["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"], "ISOLATED_IMAGE_NOT_PRESENT"),
    ):
        try:
            p = subprocess.run(args, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise Blocked(error) from None
        if p.returncode:
            raise Blocked(error)


def _docker(*args: str, timeout: int = 30, input: bytes | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["docker", *args], input=input, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("ISOLATED_CONTAINER_EXECUTION_FAILED") from None


def _credentials_and_name() -> tuple[str, str]:
    return "vfops-r4-" + secrets.token_hex(10), secrets.token_urlsafe(32)


def _query_count(name: str, password: str, sql: str) -> int:
    out = _docker("exec", "-e", "MYSQL_PWD=" + password, name,
                  "mariadb", "--no-defaults", "--protocol=socket",
                  "--user=root", "--batch", "--skip-column-names",
                  "--execute", sql, timeout=30)
    if out.returncode != 0:
        raise Blocked("ISOLATED_TABLE_COUNT_QUERY_FAILED")
    raw = out.stdout.strip()
    if not raw.isdigit() or len(raw) > 10:
        raise Blocked("ISOLATED_TABLE_COUNT_UNPROVEN")
    return int(raw)


def _wait_ready(name: str, password: str) -> None:
    deadline = time.monotonic() + 95
    while time.monotonic() < deadline:
        p = _docker("exec", "-e", "MYSQL_PWD=" + password, name,
                    "mariadb", "--no-defaults", "--protocol=socket",
                    "--user=root", "--execute", "SELECT 1", timeout=8)
        if p.returncode == 0:
            return
        time.sleep(2)
    raise Blocked("ISOLATED_DATABASE_NOT_READY")


def _stream_sql(name: str, password: str, sql_path: Path) -> None:
    # The untrusted SQL is executed ONLY by the non-root client inside a
    # sealed container; its client-side escape commands cannot run on host.
    args = ["docker", "exec", "-i", "-e", "MYSQL_PWD=" + password,
            name, "mariadb", "--no-defaults", "--protocol=socket",
            "--user=root", "--binary-mode", "--database", _DATABASE]
    try:
        proc = subprocess.Popen(args, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert proc.stdin is not None
        deadline = time.monotonic() + _TIMEOUT
        total = 0
        with sql_path.open("rb") as src:
            while True:
                data = src.read(1024 * 1024)
                if not data:
                    break
                total += len(data)
                if total > SQL_LIMIT:
                    raise Blocked("ISOLATED_SQL_SIZE_OR_DURATION_LIMIT")
                position = 0
                os.set_blocking(proc.stdin.fileno(), False)
                while position < len(data):
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise Blocked("ISOLATED_SQL_IMPORT_TIMEOUT")
                    _, writable, _ = select.select([], [proc.stdin.fileno()], [], left)
                    if not writable:
                        raise Blocked("ISOLATED_SQL_IMPORT_TIMEOUT")
                    position += os.write(proc.stdin.fileno(), data[position:])
        proc.stdin.close()
        remaining = max(1, deadline - time.monotonic())
        if proc.wait(timeout=remaining) != 0:
            raise Blocked("ISOLATED_SQL_IMPORT_FAILED")
    except (OSError, EOFError, BrokenPipeError, subprocess.TimeoutExpired):
        raise Blocked("ISOLATED_SQL_IMPORT_FAILED") from None
    finally:
        if "proc" in locals() and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)


def _restore_one(sql_path: Path, expected_tables: int) -> int:
    # No container or SQL client can start until the exact input is sealed.
    with scratch_sql_host_policy.sealed_sql_stream(sql_path) as approved_path:
        return _restore_one_sealed(approved_path, expected_tables)


def _restore_one_sealed(sql_path: Path, expected_tables: int) -> int:
    # Never re-open the mutable original gzip after passing the host gate.
    name, password = _credentials_and_name()
    # no volume mounts, host paths, published ports, or Docker socket.
    args = (
        "run", "--detach", "--name", name, "--network", "none",
        "--pull", "never", "--read-only", "--user", "999:999",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "128", "--memory", "1536m", "--cpus", "1",
        "--log-driver", "none",
        "--tmpfs", "/var/lib/mysql:rw,nosuid,nodev,size=1024m,uid=999,gid=999,mode=0700",
        "--tmpfs", "/run/mysqld:rw,nosuid,nodev,size=32m,uid=999,gid=999,mode=0700",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m",
        "-e", "MARIADB_ROOT_PASSWORD=" + password,
        IMAGE, "--skip-networking", "--local-infile=0",
    )
    try:
        p = _docker(*args, timeout=45)
        if p.returncode:
            raise Blocked("ISOLATED_DATABASE_START_REFUSED")
        _wait_ready(name, password)
        if _query_count(name, password,
                        "CREATE DATABASE IF NOT EXISTS " + _DATABASE + "; SELECT 1") != 1:
            raise Blocked("ISOLATED_DATABASE_CREATE_FAILED")
        _stream_sql(name, password, sql_path)
        observed = _query_count(name, password, _QUERY)
        if observed != expected_tables:
            raise Blocked("ISOLATED_RESTORED_TABLE_COUNT_DIFFER")
        return observed
    finally:
        # Remove only the uniquely generated disposable container, never
        # host files, a named volume, any production DB, or prior sessions.
        _docker("rm", "--force", "--volumes", name, timeout=45)


def rehearse(source_package: Path, target_package: Path, site: str,
             confirm: str) -> dict[str, Any]:
    if confirm != "ISOLATED_RESTORE_ONLY":
        return _report("EXPLICIT_ISOLATED_RESTORE_CONFIRMATION_REQUIRED")
    base = private_recovery_gate.evaluate(source_package, target_package, site)
    if (base.get("source_backup_integrity") != "PASS"
            or base.get("target_backup_integrity") != "PASS"
            or base.get("status") != "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY"):
        return _report("BOTH_PRIVATE_BACKUPS_MUST_VERIFY_FIRST")
    if type(base.get("dynamic_unsafe")) is not int or base["dynamic_unsafe"] < 0:
        return _report("DYNAMIC_SQL_GUARD_EVIDENCE_UNPROVEN")
    if base["dynamic_unsafe"] != 0:
        return _report("DYNAMIC_SQL_GUARD_BLOCKED_BEFORE_IMPORT")
    try:
        _docker_ready()
        _, a = private_recovery_gate._input_package(source_package, site)
        _, b = private_recovery_gate._input_package(target_package, site)
        try:
            restore_sql_preflight.require_no_unsafe_dynamic_guard(a, b)
        except restore_sql_preflight.GuardBlocked:
            raise Blocked("RESTORE_UNSAFE_OR_UNPROVEN_DYNAMIC_SQL_GUARD") from None
        expected_a = sql_diff_evidence.require_nonempty_source_schema(a)
        expected_b = sql_diff_evidence.require_nonempty_source_schema(b)
        if (type(expected_a) is not int or type(expected_b) is not int
                or expected_a < 1 or expected_b < 1):
            raise Blocked("ISOLATED_EXPECTED_TABLES_UNPROVEN")
        source_count = _restore_one(a, expected_a)
        target_count = _restore_one(b, expected_b)
        return _report("BOTH_INDEPENDENT_RESTORE_IMPORTS_COMPLETED",
                       source_tables=source_count, target_tables=target_count,
                       verified_source=True, verified_target=True)
    except (Blocked, scratch_sql_host_policy.HostPolicyBlocked) as exc:
        return _report(str(exc))
    except Exception:
        # No private stack trace or exception content (possibly SQL) to stdout.
        return _report("ISOLATED_RESTORE_UNAVAILABLE")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="P07 isolated SQL restores; no migration")
    p.add_argument("--source-package", type=Path, required=True)
    p.add_argument("--target-package", type=Path, required=True)
    p.add_argument("--site", required=True)
    p.add_argument("--confirm", required=True)
    a = p.parse_args(argv)
    data = rehearse(a.source_package, a.target_package, a.site, a.confirm)
    print(json.dumps(data, sort_keys=True, ensure_ascii=False))
    return 0 if data["actual_source_restore_verified"] and data["actual_target_restore_verified"] else 13


if __name__ == "__main__":
    raise SystemExit(main())
