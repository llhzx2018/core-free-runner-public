#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import shutil
from typing import Any

import package as package_engine
import storage as storage_engine

CONFIG_SCHEMA = "vf-server-ops.auto-backup.v1"
RESULT_SCHEMA = "vf-server-ops.auto-backup-run.v1"
STATUS_SCHEMA = "vf-server-ops.auto-backup-status.v1"
DOMAIN_RE = re.compile(r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+$")
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
SECRET_KEY_RE = re.compile(r"(?:password|passwd|token|client_secret|access_key|secret_key|private_key|oauth)", re.I)
REMOTE_TARGETS = ["google", "b2"]
DEFAULT_CONFIG = Path("/etc/vf-server-ops/auto-backup.json")
DEFAULT_CRON = Path("/etc/cron.d/vf-server-ops-auto-backup")
CRON_MARKER = "# P07 VF Server Ops automatic dual-remote backup"
CONFIRM_ENABLE = "ENABLE_DUAL_REMOTE_AUTOBACKUP"
CONFIRM_DISABLE = "DISABLE_DUAL_REMOTE_AUTOBACKUP"


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
        for index, child in enumerate(value):
            found.extend(_secret_paths(child, f"{prefix}[{index}]"))
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
    forbidden = _secret_paths(payload)
    if forbidden:
        raise AutoBackupError("automatic-backup config contains forbidden secret-like fields")

    sites = payload.get("sites")
    if not isinstance(sites, list) or not sites:
        raise AutoBackupError("sites must be a non-empty list")
    normalized: list[str] = []
    for site in sites:
        if not isinstance(site, str) or not DOMAIN_RE.fullmatch(site) or site.startswith("*."):
            raise AutoBackupError(f"invalid site domain: {site!r}")
        normalized.append(site.lower())
    if len(normalized) != len(set(normalized)):
        raise AutoBackupError("sites contains duplicates")

    daily_at = payload.get("daily_at")
    if not isinstance(daily_at, str) or not TIME_RE.fullmatch(daily_at):
        raise AutoBackupError("daily_at must be HH:MM")

    storage_config = _absolute(str(payload.get("storage_config", "")), "storage_config")
    local_backup_dir = _absolute(str(payload.get("local_backup_dir", "")), "local_backup_dir")
    source_root = _absolute(str(payload.get("source_root", "/")), "source_root")
    remote_targets = payload.get("remote_targets")
    if remote_targets != REMOTE_TARGETS:
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
        "source_root": source_root,
        "local_backup_dir": local_backup_dir,
        "storage_config": storage_config,
        "remote_targets": list(REMOTE_TARGETS),
        "local_keep_last": keep_last,
        "manual_backups_protected": True,
        "dns_changed": False,
    }


def _atomic_json(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    os.chmod(path, mode)


def configure(config_path: Path, sites: list[str], daily_at: str, storage_config: str, backup_dir: str, keep_last: int) -> dict[str, Any]:
    payload = {
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
    }
    _atomic_json(config_path, payload)
    return validate_config(config_path)


def storage_structure(config: dict[str, Any]) -> dict[str, Any]:
    storage_path = Path(config["storage_config"])
    if not storage_path.is_file():
        raise AutoBackupError(f"storage config not found: {storage_path}")
    raw = storage_engine.load_json(storage_path)
    accounts = storage_engine.accounts_from_config(raw)
    google = [a for a in accounts if a["enabled"] and a["provider"] == "google"]
    b2 = [a for a in accounts if a["enabled"] and a["provider"] == "b2"]
    if not google:
        raise AutoBackupError("no enabled Google encrypted backup target configured")
    if not b2:
        raise AutoBackupError("no enabled Backblaze B2 encrypted disaster-recovery target configured")
    return {
        "google_accounts": [a["id"] for a in google],
        "b2_accounts": [a["id"] for a in b2],
        "dual_remote_configured": True,
    }


def _created_at(package_dir: Path) -> dt.datetime:
    try:
        manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
        raw = manifest.get("created_at")
        parsed = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def _verified_automatic_for_domain(path: Path, domain: str) -> bool:
    try:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        verification = json.loads((path / "verification.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    return (
        manifest.get("backup_kind") == "automatic"
        and site.get("domain") == domain
        and verification.get("status") == "PASS"
    )


def prune_local(backup_root: Path, domain: str, keep_last: int) -> list[str]:
    if not backup_root.is_dir():
        return []
    candidates = [
        p for p in backup_root.iterdir()
        if p.is_dir() and not p.is_symlink() and _verified_automatic_for_domain(p, domain)
    ]
    candidates.sort(key=_created_at, reverse=True)
    deleted: list[str] = []
    root = backup_root.resolve()
    for path in candidates[keep_last:]:
        resolved = path.resolve()
        if resolved.parent != root:
            continue
        shutil.rmtree(resolved)
        deleted.append(path.name)
    return deleted


def _push_one(config: dict[str, Any], package: Path, target: str, rclone: str) -> tuple[str, str | None, str | None]:
    try:
        result = storage_engine.push(Path(config["storage_config"]), package, target, rclone)
    except (RuntimeError, OSError, storage_engine.StorageError) as exc:
        return "FAIL", None, exc.__class__.__name__
    status = result.get("status", "FAIL")
    return status, result.get("account_id"), None if status == "PASS" else "REMOTE_STATUS_NOT_PASS"


def run_once(config_path: Path, clpctl: str, rclone: str) -> dict[str, Any]:
    config = validate_config(config_path)
    if not config["enabled"]:
        return {
            "schema": RESULT_SCHEMA,
            "status": "DISABLED",
            "sites": [],
            "dns_changed": False,
            "source_deleted": False,
        }
    storage = storage_structure(config)
    backup_root = Path(config["local_backup_dir"])
    backup_root.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_root, 0o700)

    results: list[dict[str, Any]] = []
    overall_pass = True
    for domain in config["sites"]:
        record: dict[str, Any] = {
            "domain": domain,
            "local_backup": "NOT_RUN",
            "google": "NOT_RUN",
            "b2": "NOT_RUN",
            "dual_remote": "NOT_RUN",
            "local_prune": "NOT_RUN",
        }
        try:
            package = package_engine.build_backup(Path(config["source_root"]), domain, backup_root, clpctl, "automatic")
            record["local_backup"] = "PASS"
            record["backup_id"] = package.name
        except (RuntimeError, OSError) as exc:
            record["status"] = "FAIL"
            record["error_class"] = exc.__class__.__name__
            record["local_prune"] = "SKIPPED_ON_FAILURE"
            overall_pass = False
            results.append(record)
            continue

        google_status, google_account, google_error = _push_one(config, package, "google", rclone)
        b2_status, b2_account, b2_error = _push_one(config, package, "b2", rclone)
        record["google"] = google_status
        record["google_account_id"] = google_account
        record["b2"] = b2_status
        record["b2_account_id"] = b2_account
        if google_error:
            record["google_error_class"] = google_error
        if b2_error:
            record["b2_error_class"] = b2_error

        if google_status == "PASS" and b2_status == "PASS":
            record["dual_remote"] = "PASS"
            record["deleted_old_local_automatic"] = prune_local(backup_root, domain, config["local_keep_last"])
            record["local_prune"] = "PASS"
            record["status"] = "PASS"
        else:
            record["dual_remote"] = "FAIL"
            record["local_prune"] = "SKIPPED_ON_FAILURE"
            record["status"] = "FAIL"
            overall_pass = False
        results.append(record)

    return {
        "schema": RESULT_SCHEMA,
        "status": "PASS" if overall_pass else "FAIL",
        "sites": results,
        "remote_redundancy": "GOOGLE_PLUS_B2",
        "storage": storage,
        "local_keep_last": config["local_keep_last"],
        "dns_changed": False,
        "source_deleted": False,
        "production_restore_performed": False,
        "secrets_emitted": False,
    }


def _cron_line(config: dict[str, Any], script: Path, python: str, log_file: Path) -> str:
    hour, minute = config["daily_at"].split(":")
    command = " ".join([
        shlex.quote(python),
        shlex.quote(str(script.resolve())),
        "run",
        "--config",
        shlex.quote(str(DEFAULT_CONFIG.resolve())),
        ">>",
        shlex.quote(str(log_file)),
        "2>&1",
    ])
    return f"{int(minute)} {int(hour)} * * * root {command}"


def install_cron(config_path: Path, cron_file: Path, script: Path, python: str, log_file: Path, confirm: str) -> dict[str, Any]:
    if confirm != CONFIRM_ENABLE:
        raise AutoBackupError(f"install-cron requires --confirm {CONFIRM_ENABLE}")
    if os.geteuid() != 0:
        raise AutoBackupError("install-cron requires root")
    config = validate_config(config_path)
    storage_structure(config)
    if config_path.resolve() != DEFAULT_CONFIG.resolve():
        raise AutoBackupError(f"automatic user flow installs only the canonical config path: {DEFAULT_CONFIG}")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(log_file.parent, 0o700)
    cron_file.parent.mkdir(parents=True, exist_ok=True)
    body = CRON_MARKER + "\nSHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n" + _cron_line(config, script, python, log_file) + "\n"
    tmp = cron_file.with_name(cron_file.name + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, cron_file)
    os.chmod(cron_file, 0o644)
    return {
        "schema": STATUS_SCHEMA,
        "status": "ENABLED",
        "cron_file": str(cron_file),
        "daily_at": config["daily_at"],
        "sites": config["sites"],
        "remote_targets": list(REMOTE_TARGETS),
        "writes_scope": "P07_OWNED_CRON_ONLY",
    }


def disable(config_path: Path, cron_file: Path, confirm: str) -> dict[str, Any]:
    if confirm != CONFIRM_DISABLE:
        raise AutoBackupError(f"disable requires --confirm {CONFIRM_DISABLE}")
    if os.geteuid() != 0:
        raise AutoBackupError("disable requires root")
    config = validate_config(config_path)
    if cron_file.exists():
        try:
            first = cron_file.read_text(encoding="utf-8").splitlines()[0]
        except OSError as exc:
            raise AutoBackupError("cannot read existing cron file") from exc
        if first != CRON_MARKER:
            raise AutoBackupError("refusing to remove a cron file not owned by P07")
        cron_file.unlink()
    raw = _read_json(config_path)
    raw["enabled"] = False
    _atomic_json(config_path, raw)
    return {
        "schema": STATUS_SCHEMA,
        "status": "DISABLED",
        "cron_file": str(cron_file),
        "backups_deleted": False,
        "remote_copies_deleted": False,
    }


def status(config_path: Path, cron_file: Path) -> dict[str, Any]:
    if not config_path.is_file():
        return {
            "schema": STATUS_SCHEMA,
            "status": "NOT_CONFIGURED",
            "config": str(config_path),
            "cron_installed": False,
        }
    config = validate_config(config_path)
    try:
        storage = storage_structure(config)
        storage_state = "CONFIGURED"
    except AutoBackupError:
        storage = None
        storage_state = "NOT_READY"
    cron_owned = False
    if cron_file.is_file():
        try:
            cron_owned = cron_file.read_text(encoding="utf-8").splitlines()[0] == CRON_MARKER
        except OSError:
            cron_owned = False
    return {
        "schema": STATUS_SCHEMA,
        "status": "ENABLED" if config["enabled"] and cron_owned and storage_state == "CONFIGURED" else "ATTENTION",
        "config": str(config_path),
        "cron_file": str(cron_file),
        "cron_installed": cron_owned,
        "enabled": config["enabled"],
        "daily_at": config["daily_at"],
        "sites": config["sites"],
        "remote_targets": list(REMOTE_TARGETS),
        "storage_state": storage_state,
        "storage": storage,
        "local_keep_last": config["local_keep_last"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P07 guarded automatic Google + B2 backup")
    sub = parser.add_subparsers(dest="command", required=True)

    cfg = sub.add_parser("configure")
    cfg.add_argument("--config", default=str(DEFAULT_CONFIG))
    cfg.add_argument("--site", action="append", required=True)
    cfg.add_argument("--daily-at", default="03:30")
    cfg.add_argument("--storage-config", default="/etc/vf-server-ops/storage.json")
    cfg.add_argument("--backup-dir", default="/var/backups/vf-server-ops")
    cfg.add_argument("--keep-last", type=int, default=7)

    run = sub.add_parser("run")
    run.add_argument("--config", default=str(DEFAULT_CONFIG))
    run.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"))
    run.add_argument("--rclone", default=os.environ.get("VFOPS_RCLONE", "rclone"))

    stat = sub.add_parser("status")
    stat.add_argument("--config", default=str(DEFAULT_CONFIG))
    stat.add_argument("--cron-file", default=str(DEFAULT_CRON))

    install = sub.add_parser("install-cron")
    install.add_argument("--config", default=str(DEFAULT_CONFIG))
    install.add_argument("--cron-file", default=str(DEFAULT_CRON))
    install.add_argument("--script", required=True)
    install.add_argument("--python", default="/usr/bin/python3")
    install.add_argument("--log-file", default="/var/log/vf-server-ops/auto-backup.log")
    install.add_argument("--confirm", required=True)

    off = sub.add_parser("disable")
    off.add_argument("--config", default=str(DEFAULT_CONFIG))
    off.add_argument("--cron-file", default=str(DEFAULT_CRON))
    off.add_argument("--confirm", required=True)

    args = parser.parse_args()
    try:
        if args.command == "configure":
            result = configure(Path(args.config), args.site, args.daily_at, args.storage_config, args.backup_dir, args.keep_last)
        elif args.command == "run":
            result = run_once(Path(args.config), args.clpctl, args.rclone)
        elif args.command == "status":
            result = status(Path(args.config), Path(args.cron_file))
        elif args.command == "install-cron":
            result = install_cron(Path(args.config), Path(args.cron_file), Path(args.script), args.python, Path(args.log_file), args.confirm)
        else:
            result = disable(Path(args.config), Path(args.cron_file), args.confirm)
    except AutoBackupError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 12
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") not in {"FAIL", "ATTENTION"} else 12


if __name__ == "__main__":
    raise SystemExit(main())
