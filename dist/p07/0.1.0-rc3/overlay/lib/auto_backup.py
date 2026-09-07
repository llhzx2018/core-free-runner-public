#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
from typing import Any, Iterable

import package as package_engine
import storage as storage_engine

CONFIG_SCHEMA = "vf-server-ops.auto-backup.v1"
RESULT_SCHEMA = "vf-server-ops.auto-backup-run.v1"
STATUS_SCHEMA = "vf-server-ops.auto-backup-status.v1"
SCHEDULE_SCHEMA = "vf-server-ops.auto-backup-schedule-check.v1"
STATE_SCHEMA = "vf-server-ops.auto-backup-state.v1"
DOMAIN_RE = re.compile(r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+$")
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
SECRET_KEY_RE = re.compile(r"(?:password|passwd|token|client_secret|access_key|secret_key|private_key|oauth)", re.I)
BACKUP_JOB_RE = re.compile(r"(?:backup|snapshot|mysqldump|mariadb-dump|pg_dump|restic|borg|duplicity|rclone|cloudpanel|clpctl)", re.I)
BUSY_PROCESS_RE = re.compile(
    r"(?:vfops(?:-user)?\s+(?:backup|restore|migrate|storage)|vf-server-ops.*(?:backup|restore|migrate|storage)|"
    r"restore_new\.py|migrate\.py|transport\.py|storage\.py|auto_backup\.py\s+run|"
    r"cloudpanel.*backup|clpctl.*backup|mysqldump|mariadb-dump|pg_dump|restic|borg|duplicity)",
    re.I,
)
REMOTE_TARGETS = ["google", "b2"]
DEFAULT_CONFIG = Path("/etc/vf-server-ops/auto-backup.json")
DEFAULT_CRON = Path("/etc/cron.d/vf-server-ops-auto-backup")
DEFAULT_LOCK = Path("/run/lock/vf-server-ops-auto-backup.lock")
DEFAULT_STATE = Path("/var/lib/vf-server-ops/auto-backup-state.json")
DEFAULT_LOG = Path("/var/log/vf-server-ops/auto-backup.log")
CRON_MARKER = "# P07 VF Server Ops automatic dual-remote backup"
CONFIRM_ENABLE = "ENABLE_DUAL_REMOTE_AUTOBACKUP"
CONFIRM_DISABLE = "DISABLE_DUAL_REMOTE_AUTOBACKUP"
COLLISION_WINDOW_MINUTES = 30


class AutoBackupError(RuntimeError):
    pass


def _absolute(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise AutoBackupError(f"{name} must be an absolute path")
    path = Path(value)
    if ".." in path.parts:
        raise AutoBackupError(f"{name} contains unsafe path segments")
    return str(path)


def _secret_paths(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if SECRET_KEY_RE.search(str(key)):
                found.append(path)
            found.extend(_secret_paths(child, path))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            found.extend(_secret_paths(child, f"{prefix}[{i}]"))
    return found


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutoBackupError(f"invalid automatic-backup config: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != CONFIG_SCHEMA:
        raise AutoBackupError("unsupported automatic-backup config schema")
    return payload


def validate_config(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if _secret_paths(payload):
        raise AutoBackupError("automatic-backup config contains forbidden secret-like fields")
    sites = payload.get("sites")
    if not isinstance(sites, list) or not sites:
        raise AutoBackupError("sites must be a non-empty list")
    normalized = []
    for site in sites:
        if not isinstance(site, str) or not DOMAIN_RE.fullmatch(site) or site.startswith("*."):
            raise AutoBackupError(f"invalid site domain: {site!r}")
        normalized.append(site.lower())
    if len(normalized) != len(set(normalized)):
        raise AutoBackupError("sites contains duplicates")
    daily_at = payload.get("daily_at")
    if not isinstance(daily_at, str) or not TIME_RE.fullmatch(daily_at):
        raise AutoBackupError("daily_at must be HH:MM")
    if payload.get("remote_targets") != REMOTE_TARGETS:
        raise AutoBackupError("remote_targets must be exactly ['google', 'b2'] for RC3 dual-copy mode")
    keep_last = payload.get("local_keep_last", 7)
    if not isinstance(keep_last, int) or isinstance(keep_last, bool) or not 1 <= keep_last <= 100:
        raise AutoBackupError("local_keep_last must be an integer in 1..100")
    enabled = payload.get("enabled", True)
    if not isinstance(enabled, bool):
        raise AutoBackupError("enabled must be boolean")
    return {
        "schema": CONFIG_SCHEMA,
        "enabled": enabled,
        "sites": normalized,
        "daily_at": daily_at,
        "source_root": _absolute(str(payload.get("source_root", "/")), "source_root"),
        "local_backup_dir": _absolute(str(payload.get("local_backup_dir", "")), "local_backup_dir"),
        "storage_config": _absolute(str(payload.get("storage_config", "")), "storage_config"),
        "remote_targets": list(REMOTE_TARGETS),
        "local_keep_last": keep_last,
        "manual_backups_protected": True,
        "dns_changed": False,
    }


def _atomic_json(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    os.chmod(path, mode)


def configure(config_path: Path, sites: list[str], daily_at: str, storage_config: str, backup_dir: str, keep_last: int) -> dict[str, Any]:
    _atomic_json(config_path, {
        "schema": CONFIG_SCHEMA,
        "enabled": True,
        "sites": sites,
        "daily_at": daily_at,
        "source_root": "/",
        "local_backup_dir": backup_dir,
        "storage_config": storage_config,
        "remote_targets": list(REMOTE_TARGETS),
        "local_keep_last": keep_last,
        "manual_backups_protected": True,
    })
    return validate_config(config_path)


def storage_structure(config: dict[str, Any]) -> dict[str, Any]:
    path = Path(config["storage_config"])
    if not path.is_file():
        raise AutoBackupError(f"storage config not found: {path}")
    accounts = storage_engine.accounts_from_config(storage_engine.load_json(path))
    google = [a for a in accounts if a["enabled"] and a["provider"] == "google"]
    b2 = [a for a in accounts if a["enabled"] and a["provider"] == "b2"]
    if not google:
        raise AutoBackupError("no enabled Google encrypted backup target configured")
    if not b2:
        raise AutoBackupError("no enabled Backblaze B2 encrypted disaster-recovery target configured")
    return {"google_accounts": [a["id"] for a in google], "b2_accounts": [a["id"] for a in b2], "dual_remote_configured": True}


def _time_minutes(value: str) -> int:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def _minute_distance(a: int, b: int) -> int:
    raw = abs(a - b)
    return min(raw, 1440 - raw)


def _iter_cron_files(extra_roots: Iterable[Path] | None = None) -> list[Path]:
    files: list[Path] = []
    candidates = [Path("/etc/crontab")]
    dirs = [Path("/etc/cron.d"), Path("/var/spool/cron/crontabs")]
    if extra_roots:
        for root in extra_roots:
            (dirs if root.is_dir() else candidates).append(root)
    files.extend(path for path in candidates if path.is_file())
    for directory in dirs:
        if not directory.is_dir():
            continue
        try:
            files.extend(path for path in directory.iterdir() if path.is_file())
        except OSError:
            pass
    return list({str(path.resolve()): path for path in files}.values())


def _parse_exact_cron(line: str) -> tuple[int, int, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "@")) or "=" in stripped.split()[0]:
        return None
    parts = stripped.split()
    if len(parts) < 6 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    m, h = int(parts[0]), int(parts[1])
    if not 0 <= m <= 59 or not 0 <= h <= 23:
        return None
    return h, m, " ".join(parts[5:])


def schedule_collisions(daily_at: str, cron_files: list[Path] | None = None, window: int = COLLISION_WINDOW_MINUTES) -> dict[str, Any]:
    if not TIME_RE.fullmatch(daily_at):
        raise AutoBackupError("daily_at must be HH:MM")
    requested = _time_minutes(daily_at)
    jobs: list[dict[str, Any]] = []
    for path in (cron_files if cron_files is not None else _iter_cron_files()):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        if lines and lines[0].strip() == CRON_MARKER:
            continue
        for line_no, line in enumerate(lines, 1):
            parsed = _parse_exact_cron(line)
            if not parsed:
                continue
            hour, minute, command = parsed
            if BACKUP_JOB_RE.search(command):
                jobs.append({"path": str(path), "line": line_no, "scheduled_at": f"{hour:02d}:{minute:02d}", "minutes": hour * 60 + minute, "command_class": "BACKUP_LIKE"})
    collisions = []
    for job in jobs:
        distance = _minute_distance(requested, job["minutes"])
        if distance <= window:
            item = {k: v for k, v in job.items() if k != "minutes"}
            item["distance_minutes"] = distance
            collisions.append(item)
    recommended = requested
    if collisions:
        occupied = [job["minutes"] for job in jobs]
        for offset in range(45, 361, 15):
            candidate = (requested + offset) % 1440
            if all(_minute_distance(candidate, item) > window for item in occupied):
                recommended = candidate
                break
    return {
        "schema": SCHEDULE_SCHEMA,
        "status": "COLLISION" if collisions else "CLEAR",
        "requested_at": daily_at,
        "recommended_at": f"{recommended // 60:02d}:{recommended % 60:02d}",
        "collision_window_minutes": window,
        "collisions": collisions,
        "collision_count": len(collisions),
        "writes_performed": False,
    }


def _busy_processes(proc_root: Path = Path("/proc")) -> list[dict[str, Any]]:
    busy = []
    if not proc_root.is_dir():
        return busy
    current = os.getpid()
    for item in proc_root.iterdir():
        if not item.name.isdigit() or int(item.name) == current:
            continue
        try:
            cmd = (item / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
        except OSError:
            continue
        if cmd and BUSY_PROCESS_RE.search(cmd):
            busy.append({"pid": int(item.name), "class": "BACKUP_RESTORE_MIGRATION_OR_STORAGE"})
    return busy


def _write_state(path: Path, status: str, **extra: Any) -> None:
    payload = {"schema": STATE_SCHEMA, "status": status, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    payload.update(extra)
    _atomic_json(path, payload)


def _read_state(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and payload.get("schema") == STATE_SCHEMA else None


def _created_at(path: Path) -> dt.datetime:
    try:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        parsed = dt.datetime.fromisoformat(str(manifest.get("created_at")).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or dt.timezone.utc).astimezone(dt.timezone.utc)
    except Exception:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def _verified_automatic_for_domain(path: Path, domain: str) -> bool:
    try:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        verification = json.loads((path / "verification.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    return manifest.get("backup_kind") == "automatic" and site.get("domain") == domain and verification.get("status") == "PASS"


def prune_local(root: Path, domain: str, keep_last: int) -> list[str]:
    if not root.is_dir():
        return []
    items = [p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and _verified_automatic_for_domain(p, domain)]
    items.sort(key=_created_at, reverse=True)
    deleted = []
    resolved_root = root.resolve()
    for path in items[keep_last:]:
        target = path.resolve()
        if target.parent != resolved_root:
            continue
        shutil.rmtree(target)
        deleted.append(path.name)
    return deleted


def _push_one(config: dict[str, Any], package: Path, target: str, rclone: str) -> tuple[str, str | None, str | None]:
    try:
        result = storage_engine.push(Path(config["storage_config"]), package, target, rclone)
    except (RuntimeError, OSError, storage_engine.StorageError) as exc:
        return "FAIL", None, exc.__class__.__name__
    status = result.get("status", "FAIL")
    return status, result.get("account_id"), None if status == "PASS" else "REMOTE_STATUS_NOT_PASS"


def _execute_run(config: dict[str, Any], clpctl: str, rclone: str) -> dict[str, Any]:
    storage = storage_structure(config)
    root = Path(config["local_backup_dir"])
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    results = []
    overall = True
    for domain in config["sites"]:
        record: dict[str, Any] = {"domain": domain, "local_backup": "NOT_RUN", "google": "NOT_RUN", "b2": "NOT_RUN", "dual_remote": "NOT_RUN", "local_prune": "NOT_RUN"}
        try:
            package = package_engine.build_backup(Path(config["source_root"]), domain, root, clpctl, "automatic")
            record.update(local_backup="PASS", backup_id=package.name)
        except (RuntimeError, OSError) as exc:
            record.update(status="FAIL", error_class=exc.__class__.__name__, local_prune="SKIPPED_ON_FAILURE")
            overall = False
            results.append(record)
            continue
        g_status, g_id, g_err = _push_one(config, package, "google", rclone)
        b_status, b_id, b_err = _push_one(config, package, "b2", rclone)
        record.update(google=g_status, google_account_id=g_id, b2=b_status, b2_account_id=b_id)
        if g_err: record["google_error_class"] = g_err
        if b_err: record["b2_error_class"] = b_err
        if g_status == "PASS" and b_status == "PASS":
            record.update(dual_remote="PASS", local_prune="PASS", status="PASS", deleted_old_local_automatic=prune_local(root, domain, config["local_keep_last"]))
        else:
            record.update(dual_remote="FAIL", local_prune="SKIPPED_ON_FAILURE", status="FAIL")
            overall = False
        results.append(record)
    return {"schema": RESULT_SCHEMA, "status": "PASS" if overall else "FAIL", "sites": results, "remote_redundancy": "GOOGLE_PLUS_B2", "storage": storage, "local_keep_last": config["local_keep_last"], "dns_changed": False, "source_deleted": False, "production_restore_performed": False, "secrets_emitted": False}


def run_once(config_path: Path, clpctl: str, rclone: str, lock_file: Path = DEFAULT_LOCK, state_file: Path = DEFAULT_STATE, proc_root: Path = Path("/proc")) -> dict[str, Any]:
    config = validate_config(config_path)
    if not config["enabled"]:
        _write_state(state_file, "DISABLED")
        return {"schema": RESULT_SCHEMA, "status": "DISABLED", "sites": [], "dns_changed": False, "source_deleted": False}
    try:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_file.open("a+")
    except OSError as exc:
        raise AutoBackupError("cannot open automatic-backup lock") from exc
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _write_state(state_file, "SKIPPED_BUSY", reason="P07_AUTO_BACKUP_ALREADY_RUNNING")
            return {"schema": RESULT_SCHEMA, "status": "SKIPPED_BUSY", "reason": "P07_AUTO_BACKUP_ALREADY_RUNNING", "sites": [], "dns_changed": False, "source_deleted": False}
        busy = _busy_processes(proc_root)
        if busy:
            _write_state(state_file, "SKIPPED_BUSY", reason="BACKUP_RESTORE_MIGRATION_OR_STORAGE_ACTIVE", busy=busy)
            return {"schema": RESULT_SCHEMA, "status": "SKIPPED_BUSY", "reason": "BACKUP_RESTORE_MIGRATION_OR_STORAGE_ACTIVE", "busy": busy, "sites": [], "dns_changed": False, "source_deleted": False}
        _write_state(state_file, "RUNNING", sites=config["sites"])
        try:
            result = _execute_run(config, clpctl, rclone)
        except (RuntimeError, OSError, storage_engine.StorageError, AutoBackupError) as exc:
            _write_state(state_file, "FAIL", error_class=exc.__class__.__name__)
            return {"schema": RESULT_SCHEMA, "status": "FAIL", "error_class": exc.__class__.__name__, "sites": [], "dns_changed": False, "source_deleted": False}
        _write_state(state_file, result["status"], sites=result.get("sites", []))
        return result
    finally:
        try: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally: handle.close()


def _cron_line(config: dict[str, Any], script: Path, python: str, log_file: Path) -> str:
    h, m = config["daily_at"].split(":")
    command = " ".join([shlex.quote(python), shlex.quote(str(script.resolve())), "run", "--config", shlex.quote(str(DEFAULT_CONFIG.resolve())), ">>", shlex.quote(str(log_file)), "2>&1"])
    return f"{int(m)} {int(h)} * * * root {command}"


def install_cron(config_path: Path, cron_file: Path, script: Path, python: str, log_file: Path, confirm: str) -> dict[str, Any]:
    if confirm != CONFIRM_ENABLE: raise AutoBackupError(f"install-cron requires --confirm {CONFIRM_ENABLE}")
    if os.geteuid() != 0: raise AutoBackupError("install-cron requires root")
    config = validate_config(config_path); storage_structure(config)
    if config_path.resolve() != DEFAULT_CONFIG.resolve(): raise AutoBackupError(f"automatic user flow installs only the canonical config path: {DEFAULT_CONFIG}")
    if cron_file.exists():
        try: first = cron_file.read_text(encoding="utf-8").splitlines()[0]
        except OSError as exc: raise AutoBackupError("cannot read existing cron file") from exc
        if first != CRON_MARKER: raise AutoBackupError("refusing to overwrite a cron file not owned by P07")
    log_file.parent.mkdir(parents=True, exist_ok=True); os.chmod(log_file.parent, 0o700); cron_file.parent.mkdir(parents=True, exist_ok=True)
    body = CRON_MARKER + "\nSHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n" + _cron_line(config, script, python, log_file) + "\n"
    tmp = cron_file.with_name(cron_file.name + ".tmp"); tmp.write_text(body, encoding="utf-8"); os.chmod(tmp, 0o644); os.replace(tmp, cron_file); os.chmod(cron_file, 0o644)
    return {"schema": STATUS_SCHEMA, "status": "ENABLED", "cron_file": str(cron_file), "daily_at": config["daily_at"], "sites": config["sites"], "remote_targets": list(REMOTE_TARGETS), "writes_scope": "P07_OWNED_CRON_ONLY"}


def disable(config_path: Path, cron_file: Path, confirm: str) -> dict[str, Any]:
    if confirm != CONFIRM_DISABLE: raise AutoBackupError(f"disable requires --confirm {CONFIRM_DISABLE}")
    if os.geteuid() != 0: raise AutoBackupError("disable requires root")
    validate_config(config_path)
    if cron_file.exists():
        try: first = cron_file.read_text(encoding="utf-8").splitlines()[0]
        except OSError as exc: raise AutoBackupError("cannot read existing cron file") from exc
        if first != CRON_MARKER: raise AutoBackupError("refusing to remove a cron file not owned by P07")
        cron_file.unlink()
    raw = _read_json(config_path); raw["enabled"] = False; _atomic_json(config_path, raw)
    return {"schema": STATUS_SCHEMA, "status": "DISABLED", "cron_file": str(cron_file), "backups_deleted": False, "remote_copies_deleted": False}


def status(config_path: Path, cron_file: Path, state_file: Path = DEFAULT_STATE) -> dict[str, Any]:
    if not config_path.is_file(): return {"schema": STATUS_SCHEMA, "status": "NOT_CONFIGURED", "config": str(config_path), "cron_installed": False, "last_run": _read_state(state_file)}
    config = validate_config(config_path); storage = None; storage_state = "NOT_READY"
    try: storage = storage_structure(config); storage_state = "CONFIGURED"
    except AutoBackupError: pass
    cron_owned = False
    if cron_file.is_file():
        try: cron_owned = cron_file.read_text(encoding="utf-8").splitlines()[0] == CRON_MARKER
        except OSError: pass
    overall = "DISABLED" if not config["enabled"] else ("ENABLED" if cron_owned and storage_state == "CONFIGURED" else "ATTENTION")
    return {"schema": STATUS_SCHEMA, "status": overall, "config": str(config_path), "cron_file": str(cron_file), "cron_installed": cron_owned, "enabled": config["enabled"], "daily_at": config["daily_at"], "sites": config["sites"], "remote_targets": list(REMOTE_TARGETS), "storage_state": storage_state, "storage": storage, "local_keep_last": config["local_keep_last"], "last_run": _read_state(state_file)}


def main() -> int:
    parser = argparse.ArgumentParser(description="P07 guarded automatic Google + B2 backup"); sub = parser.add_subparsers(dest="command", required=True)
    cfg = sub.add_parser("configure"); cfg.add_argument("--config", default=str(DEFAULT_CONFIG)); cfg.add_argument("--site", action="append", required=True); cfg.add_argument("--daily-at", default="03:30"); cfg.add_argument("--storage-config", default="/etc/vf-server-ops/storage.json"); cfg.add_argument("--backup-dir", default="/var/backups/vf-server-ops"); cfg.add_argument("--keep-last", type=int, default=7)
    run = sub.add_parser("run"); run.add_argument("--config", default=str(DEFAULT_CONFIG)); run.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl")); run.add_argument("--rclone", default=os.environ.get("VFOPS_RCLONE", "rclone")); run.add_argument("--lock-file", default=str(DEFAULT_LOCK)); run.add_argument("--state-file", default=str(DEFAULT_STATE))
    stat = sub.add_parser("status"); stat.add_argument("--config", default=str(DEFAULT_CONFIG)); stat.add_argument("--cron-file", default=str(DEFAULT_CRON)); stat.add_argument("--state-file", default=str(DEFAULT_STATE))
    sched = sub.add_parser("schedule-check"); sched.add_argument("--daily-at", required=True); sched.add_argument("--cron-file", action="append")
    install = sub.add_parser("install-cron"); install.add_argument("--config", default=str(DEFAULT_CONFIG)); install.add_argument("--cron-file", default=str(DEFAULT_CRON)); install.add_argument("--script", required=True); install.add_argument("--python", default="/usr/bin/python3"); install.add_argument("--log-file", default=str(DEFAULT_LOG)); install.add_argument("--confirm", required=True)
    off = sub.add_parser("disable"); off.add_argument("--config", default=str(DEFAULT_CONFIG)); off.add_argument("--cron-file", default=str(DEFAULT_CRON)); off.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        if args.command == "configure": result = configure(Path(args.config), args.site, args.daily_at, args.storage_config, args.backup_dir, args.keep_last)
        elif args.command == "run": result = run_once(Path(args.config), args.clpctl, args.rclone, Path(args.lock_file), Path(args.state_file))
        elif args.command == "status": result = status(Path(args.config), Path(args.cron_file), Path(args.state_file))
        elif args.command == "schedule-check": result = schedule_collisions(args.daily_at, [Path(p) for p in args.cron_file] if args.cron_file else None)
        elif args.command == "install-cron": result = install_cron(Path(args.config), Path(args.cron_file), Path(args.script), args.python, Path(args.log_file), args.confirm)
        else: result = disable(Path(args.config), Path(args.cron_file), args.confirm)
    except AutoBackupError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr); return 12
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 12 if result.get("status") in {"FAIL", "ATTENTION"} else 0


if __name__ == "__main__": raise SystemExit(main())
