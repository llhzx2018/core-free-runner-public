"""R5 non-Docker private MariaDB scratch restore; NOT a production migration gate.

Uses the existing native binaries only, strictly separate fresh datadir/socket,
no TCP, no CloudPanel/production database API, no existing daemon controls.
Runs as unprivileged user, even when vfops is invoked by root. All SQL is
streamed privately through stdin; errors/logs/data are never returned.
Native process isolation is NOT a filesystem namespace or VM boundary.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import pwd
import select
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from typing import Any

import private_recovery_gate
import sql_diff_evidence

SCHEMA = "P07_NATIVE_SCRATCH_RESTORE_V1"
DATABASE = "vfops_r5_scratch"
MAX_SQL_BYTES = 512 * 1024 * 1024
IMPORT_TIMEOUT = 240
BINARY_NAMES = ("mariadbd", "mariadb-install-db", "mariadb")


class Blocked(RuntimeError):
    """Fixed diagnostic code; no private source SQL or paths."""


def _report(reason: str, source: int = 0, target: int = 0,
            source_ok: bool = False, target_ok: bool = False) -> dict[str, Any]:
    ok = source_ok and target_ok
    return {
        "schema": SCHEMA,
        "status": "NATIVE_SCRATCH_RESTORE_VERIFIED_NOT_CUTOVER" if ok else "BLOCKED",
        "reason": reason,
        "backend": "NATIVE_MARIADB_UNPRIVILEGED_NO_TCP",
        "source_tables_restored": source,
        "target_tables_restored": target,
        "source_independent_native_import_verified": source_ok,
        "target_independent_native_import_verified": target_ok,
        "actual_source_restore_verified": source_ok,
        "actual_target_restore_verified": target_ok,
        "independent_temporary_datadirs": ok,
        "production_database_writes_performed": False,
        "existing_host_database_configuration_modified": False,
        "migration_state_modified": False,
        "source_runtime_frozen": False,
        "dns_modified": False,
        "cross_engine_business_semantics_verified": False,
        "row_data_and_trigger_semantics_verified": False,
        "unsafe_dynamic_sql_approved": False,
        "conflict_decisions_verified": False,
        "migration_resume_allowed": False,
        "cutover_allowed": False,
        "verification": "NATIVE_RESTORE_ONLY_NOT_MIGRATION_PASS",
    }


def _binaries() -> dict[str, str]:
    found: dict[str, str] = {}
    for program in BINARY_NAMES:
        path = shutil.which(program)
        if not path or not Path(path).is_file():
            raise Blocked("NATIVE_MARIADB_BINARIES_UNAVAILABLE")
        found[program] = path
    try:
        p = subprocess.run([found["mariadbd"], "--no-defaults", "--version"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("NATIVE_MARIADB_ENGINE_VERSION_UNAVAILABLE") from None
    if p.returncode or b"MariaDB" not in p.stdout:
        raise Blocked("NATIVE_MARIADB_ENGINE_UNSUPPORTED")
    return found


def _identity() -> tuple[int, int]:
    """Return a genuine unprivileged service identity, never UID 0."""
    if os.geteuid() == 0:
        try:
            entry = pwd.getpwnam("nobody")
        except KeyError:
            raise Blocked("NATIVE_UNPRIVILEGED_USER_UNAVAILABLE") from None
        uid, gid = entry.pw_uid, entry.pw_gid
    else:
        uid, gid = os.geteuid(), os.getegid()
    if uid == 0 or gid == 0:
        raise Blocked("NATIVE_UNPRIVILEGED_IDENTITY_REQUIRED")
    return uid, gid


def _drop_user(uid: int, gid: int):
    def change() -> None:
        if os.geteuid() == 0:
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
    return change


def _environment(home: Path) -> dict[str, str]:
    # Never inherit database passwords, MYSQL_* environment or client defaults.
    return {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": str(home), "TMPDIR": str(home),
            "LANG": "C", "LC_ALL": "C", "MYSQL_HISTFILE": "/dev/null"}


def _run(args: list[str], *, env: dict[str, str], uid: int, gid: int,
         timeout: int = 40) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, env=env, timeout=timeout,
                              check=False, preexec_fn=_drop_user(uid, gid))
    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        raise Blocked("NATIVE_SCRATCH_EXECUTION_FAILED") from None


def _client(bins: dict[str, str], socket: Path, home: Path, uid: int, gid: int,
            statement: str) -> bytes:
    args = [bins["mariadb"], "--no-defaults", "--protocol=socket",
            "--socket=" + str(socket), "--user=root", "--batch",
            "--skip-column-names", "--binary-mode", "--local-infile=0",
            "--execute=" + statement]
    result = _run(args, env=_environment(home), uid=uid, gid=gid, timeout=20)
    if result.returncode:
        raise Blocked("NATIVE_SCRATCH_CLIENT_COMMAND_FAILED")
    return result.stdout


def _wait_socket(bins: dict[str, str], socket: Path, home: Path,
                 daemon: subprocess.Popen, uid: int, gid: int) -> None:
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        if daemon.poll() is not None:
            raise Blocked("NATIVE_SCRATCH_DAEMON_EXITED")
        try:
            out = _client(bins, socket, home, uid, gid, "SELECT 1")
            if out.strip() == b"1":
                return
        except Blocked:
            pass
        time.sleep(1)
    raise Blocked("NATIVE_SCRATCH_DAEMON_NOT_READY")


def _sql_stream(bins: dict[str, str], socket: Path, home: Path,
                uid: int, gid: int, sql_path: Path) -> None:
    args = [bins["mariadb"], "--no-defaults", "--protocol=socket",
            "--socket=" + str(socket), "--user=root", "--binary-mode",
            "--local-infile=0", "--database=" + DATABASE]
    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(args, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=_environment(home), preexec_fn=_drop_user(uid, gid),
                                start_new_session=True)
        if proc.stdin is None:
            raise Blocked("NATIVE_SCRATCH_CLIENT_STDIN_UNAVAILABLE")
        fd = proc.stdin.fileno()
        os.set_blocking(fd, False)
        size = 0
        deadline = time.monotonic() + IMPORT_TIMEOUT
        with gzip.open(sql_path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_SQL_BYTES:
                    raise Blocked("NATIVE_SQL_UNCOMPRESSED_LIMIT")
                offset = 0
                while offset < len(chunk):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise Blocked("NATIVE_SQL_IMPORT_TIMEOUT")
                    _, writable, _ = select.select([], [fd], [], remaining)
                    if not writable:
                        raise Blocked("NATIVE_SQL_IMPORT_TIMEOUT")
                    offset += os.write(fd, chunk[offset:])
        proc.stdin.close()
        if proc.wait(timeout=max(1, deadline - time.monotonic())):
            raise Blocked("NATIVE_SQL_IMPORT_FAILED")
    except Blocked:
        raise
    except (OSError, EOFError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        raise Blocked("NATIVE_SQL_IMPORT_FAILED") from None
    finally:
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=10)


def _shutdown(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=12)
        except (OSError, subprocess.TimeoutExpired):
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=10)


def restore_one(sql_path: Path, expected_tables: int) -> int:
    """Run one independent MariaDB daemon; remove ONLY this random scratch root."""
    if type(expected_tables) is not int or not 1 <= expected_tables <= 20000:
        raise Blocked("NATIVE_EXPECTED_TABLES_UNPROVEN")
    bins = _binaries()
    uid, gid = _identity()
    daemon: subprocess.Popen | None = None
    # An OS-generated directory is never an existing CloudPanel datadir.
    # Keep path short enough for the maximum Unix socket length.
    with tempfile.TemporaryDirectory(prefix="vfops-r5-", dir="/tmp") as temp:
        base = Path(temp)
        os.chmod(base, 0o700)
        if os.geteuid() == 0:
            os.chown(base, uid, gid)
        datadir = base / "db"
        datadir.mkdir(mode=0o700)
        if os.geteuid() == 0:
            os.chown(datadir, uid, gid)
        sock = base / "sql.sock"
        init = [
            bins["mariadb-install-db"], "--no-defaults",
            "--datadir=" + str(datadir),
            "--auth-root-authentication-method=normal", "--skip-test-db",
        ]
        setup = _run(init, env=_environment(base), uid=uid, gid=gid, timeout=90)
        if setup.returncode:
            raise Blocked("NATIVE_SCRATCH_INITIALIZATION_FAILED")
        daemon_args = [
            bins["mariadbd"], "--no-defaults",
            "--datadir=" + str(datadir),
            "--socket=" + str(sock),
            "--pid-file=" + str(base / "daemon.pid"),
            "--log-error=" + str(base / "daemon.err"),
            "--skip-networking", "--port=0",
            "--local-infile=0", "--skip-log-bin",
            "--max-connections=5",
        ]
        try:
            daemon = subprocess.Popen(daemon_args, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      env=_environment(base),
                                      preexec_fn=_drop_user(uid, gid),
                                      start_new_session=True)
            _wait_socket(bins, sock, base, daemon, uid, gid)
            _client(bins, sock, base, uid, gid, "CREATE DATABASE " + DATABASE)
            _sql_stream(bins, sock, base, uid, gid, sql_path)
            rows = _client(bins, sock, base, uid, gid,
                           "SELECT COUNT(*) FROM information_schema.tables "
                           "WHERE table_schema='" + DATABASE + "' "
                           "AND table_type='BASE TABLE'").strip()
            if not rows.isdigit() or int(rows) != expected_tables:
                raise Blocked("NATIVE_SCRATCH_TABLE_COUNT_DIFFER")
            return int(rows)
        except Blocked:
            raise
        except (OSError, subprocess.SubprocessError):
            raise Blocked("NATIVE_SCRATCH_DAEMON_START_FAILED") from None
        finally:
            _shutdown(daemon)


def rehearse(source_package: Path, target_package: Path,
             site: str, confirm: str) -> dict[str, Any]:
    if confirm != "NATIVE_RESTORE_SCRATCH_ONLY":
        return _report("NATIVE_RESTORE_CONFIRMATION_REQUIRED")
    evidence = private_recovery_gate.evaluate(source_package, target_package, site)
    if (evidence.get("source_backup_integrity") != "PASS"
            or evidence.get("target_backup_integrity") != "PASS"):
        return _report("NATIVE_BOTH_BACKUPS_MUST_VERIFY")
    try:
        # Reject missing engine before changing even our scratch directory.
        _binaries()
        _, a = private_recovery_gate._input_package(source_package, site)
        _, b = private_recovery_gate._input_package(target_package, site)
        one = sql_diff_evidence.require_nonempty_source_schema(a)
        two = sql_diff_evidence.require_nonempty_source_schema(b)
        if type(one) is not int or type(two) is not int or not 0 < one < 20001 or not 0 < two < 20001:
            raise Blocked("NATIVE_SQL_SCHEMA_UNPROVEN")
        count_a = restore_one(a, one)
        count_b = restore_one(b, two)
        return _report("NATIVE_BOTH_SCRATCH_IMPORTS_COMPLETED",
                       source=count_a, target=count_b,
                       source_ok=True, target_ok=True)
    except Blocked as exc:
        return _report(str(exc))
    except Exception:
        return _report("NATIVE_SCRATCH_RESTORE_UNAVAILABLE")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P07 scratch MariaDB restores, never production cutover")
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--target-package", type=Path, required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)
    result = rehearse(args.source_package, args.target_package, args.site, args.confirm)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["actual_source_restore_verified"] and result["actual_target_restore_verified"] else 13


if __name__ == "__main__":
    raise SystemExit(main())
