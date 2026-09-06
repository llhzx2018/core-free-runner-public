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

POLICY_SCHEMA = "vf-server-ops.policy.v1"
RETENTION_SCHEMA = "vf-server-ops.retention-plan.v1"
RUN_SCHEMA = "vf-server-ops.policy-run.v1"
APPLY_SCHEMA = "vf-server-ops.retention-apply.v1"
SECRET_KEY_RE = re.compile(r"(?:password|passwd|token|client_secret|access_key|secret_key|private_key|oauth)", re.I)
DOMAIN_RE = re.compile(r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+$")
CONFIRM_DELETE = "DELETE_AUTOMATIC_BACKUPS"


class PolicyError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"invalid policy JSON: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != POLICY_SCHEMA:
        raise PolicyError("unsupported policy schema")
    return payload


def secret_key_paths(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if SECRET_KEY_RE.search(str(key)):
                found.append(path)
            found.extend(secret_key_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(secret_key_paths(child, f"{prefix}[{index}]"))
    return found


def positive_int(value: Any, name: str, minimum: int = 1, maximum: int = 100000) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise PolicyError(f"{name} must be an integer in {minimum}..{maximum}")
    return value


def validate_time(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise PolicyError("automation.daily_at must be HH:MM")
    return value


def absolute_path(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise PolicyError(f"{name} must be an absolute path")
    path = Path(value)
    if ".." in path.parts:
        raise PolicyError(f"{name} contains unsafe path segments")
    return str(path)


def validate_policy(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    forbidden = secret_key_paths(payload)
    if forbidden:
        raise PolicyError("policy contains forbidden secret-like fields: " + ", ".join(sorted(forbidden)))

    backup_dir = absolute_path(payload.get("local_backup_dir"), "local_backup_dir")
    root = absolute_path(payload.get("source_root", "/"), "source_root")
    sites = payload.get("sites")
    if not isinstance(sites, list) or not sites:
        raise PolicyError("sites must be a non-empty list")
    normalized_sites: list[str] = []
    for site in sites:
        if not isinstance(site, str) or not DOMAIN_RE.fullmatch(site) or site.startswith("*."):
            raise PolicyError(f"invalid site domain: {site!r}")
        normalized_sites.append(site.lower())
    if len(normalized_sites) != len(set(normalized_sites)):
        raise PolicyError("sites contains duplicates")

    storage_config = payload.get("storage_config")
    if storage_config is not None:
        storage_config = absolute_path(storage_config, "storage_config")

    backup = payload.get("backup", {})
    if not isinstance(backup, dict):
        raise PolicyError("backup must be an object")
    upload_remote = backup.get("upload_remote", False)
    if not isinstance(upload_remote, bool):
        raise PolicyError("backup.upload_remote must be boolean")
    remote_target = backup.get("remote_target", "auto")
    if not isinstance(remote_target, str) or not remote_target:
        raise PolicyError("backup.remote_target must be a string")
    if upload_remote and storage_config is None:
        raise PolicyError("storage_config is required when backup.upload_remote=true")

    retention = payload.get("retention", {})
    if not isinstance(retention, dict):
        raise PolicyError("retention must be an object")
    keep_last = positive_int(retention.get("automatic_keep_last", 7), "retention.automatic_keep_last", 1, 1000)
    max_age = positive_int(retention.get("automatic_max_age_days", 30), "retention.automatic_max_age_days", 1, 36500)
    manual_protected = retention.get("manual_protected", True)
    if manual_protected is not True:
        raise PolicyError("retention.manual_protected is locked to true")
    auto_delete = retention.get("auto_delete_automatic", False)
    if not isinstance(auto_delete, bool):
        raise PolicyError("retention.auto_delete_automatic must be boolean")

    automation = payload.get("automation", {})
    if not isinstance(automation, dict):
        raise PolicyError("automation must be an object")
    enabled = automation.get("enabled", False)
    if not isinstance(enabled, bool):
        raise PolicyError("automation.enabled must be boolean")
    daily_at = validate_time(automation.get("daily_at", "03:30"))

    return {
        "schema": POLICY_SCHEMA,
        "status": "PASS",
        "source_root": root,
        "local_backup_dir": backup_dir,
        "sites": normalized_sites,
        "storage_config": storage_config,
        "backup": {"upload_remote": upload_remote, "remote_target": remote_target},
        "retention": {
            "automatic_keep_last": keep_last,
            "automatic_max_age_days": max_age,
            "manual_protected": True,
            "auto_delete_automatic": auto_delete,
        },
        "automation": {"enabled": enabled, "daily_at": daily_at},
        "secret_values_in_policy_allowed": False,
    }


def parse_created_at(value: Any) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def load_package_record(path: Path) -> dict[str, Any]:
    manifest_path = path / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"path": str(path), "status": "PROTECTED_INVALID_OR_UNKNOWN", "eligible": False}
    if not isinstance(manifest, dict) or manifest.get("schema") != package_engine.PACKAGE_SCHEMA:
        return {"path": str(path), "status": "PROTECTED_INVALID_OR_UNKNOWN", "eligible": False}
    domain = manifest.get("site", {}).get("domain") if isinstance(manifest.get("site"), dict) else None
    kind = manifest.get("backup_kind", "manual")
    created = parse_created_at(manifest.get("created_at"))
    if not isinstance(domain, str) or not domain or kind not in package_engine.BACKUP_KINDS or created is None:
        return {"path": str(path), "status": "PROTECTED_INVALID_OR_UNKNOWN", "eligible": False}
    verification = package_engine.verify_package(path)
    return {
        "path": str(path),
        "backup_id": manifest.get("backup_id", path.name),
        "domain": domain,
        "kind": kind,
        "created_at": created.isoformat(),
        "created_dt": created,
        "fresh_verification": verification.get("status"),
        "eligible": kind == "automatic" and verification.get("status") == "PASS",
        "status": "AUTOMATIC_VALID" if kind == "automatic" and verification.get("status") == "PASS" else ("PROTECTED_NON_AUTOMATIC" if kind != "automatic" else "PROTECTED_INVALID_AUTOMATIC"),
    }


def retention_plan(policy_path: Path, now: dt.datetime | None = None) -> dict[str, Any]:
    policy = validate_policy(policy_path)
    backup_dir = Path(policy["local_backup_dir"])
    if not backup_dir.is_dir():
        raise PolicyError("local_backup_dir does not exist")
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    now = now.astimezone(dt.timezone.utc)

    records = [load_package_record(path) for path in sorted(backup_dir.iterdir()) if path.is_dir() and not path.is_symlink() and not path.name.startswith(".")]
    keep_last = policy["retention"]["automatic_keep_last"]
    max_age = policy["retention"]["automatic_max_age_days"]
    cutoff = now - dt.timedelta(days=max_age)

    candidates: list[dict[str, Any]] = []
    protected: list[dict[str, Any]] = []
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record.get("eligible"):
            by_domain.setdefault(record["domain"], []).append(record)
        else:
            protected.append({k: v for k, v in record.items() if k != "created_dt"})

    for domain, items in by_domain.items():
        items.sort(key=lambda item: item["created_dt"], reverse=True)
        for index, item in enumerate(items):
            age_exceeded = item["created_dt"] < cutoff
            count_exceeded = index >= keep_last
            public = {k: v for k, v in item.items() if k != "created_dt"}
            if index < keep_last:
                public["retention_reason"] = "KEEP_RECENT_MINIMUM"
                protected.append(public)
            elif age_exceeded or count_exceeded:
                public["retention_reason"] = "AGE_OR_COUNT_EXCEEDED"
                candidates.append(public)
            else:
                public["retention_reason"] = "KEEP_WITHIN_POLICY"
                protected.append(public)

    candidates.sort(key=lambda item: (item.get("domain", ""), item.get("created_at", "")))
    return {
        "schema": RETENTION_SCHEMA,
        "status": "PLAN_READY",
        "generated_at": now.isoformat(),
        "local_backup_dir": str(backup_dir),
        "automatic_keep_last": keep_last,
        "automatic_max_age_days": max_age,
        "manual_protected": True,
        "delete_scope": "VALID_AUTOMATIC_ONLY",
        "delete_candidates": candidates,
        "protected": protected,
        "delete_candidate_count": len(candidates),
        "writes_performed": False,
    }


def retention_apply(policy_path: Path, confirm: str) -> dict[str, Any]:
    if confirm != CONFIRM_DELETE:
        raise PolicyError(f"retention apply requires --confirm {CONFIRM_DELETE}")
    policy = validate_policy(policy_path)
    if policy["retention"]["auto_delete_automatic"] is not True:
        raise PolicyError("policy does not authorize automatic-backup deletion")
    plan = retention_plan(policy_path)
    deleted: list[str] = []
    refused: list[dict[str, str]] = []
    backup_root = Path(plan["local_backup_dir"]).resolve()
    for item in plan["delete_candidates"]:
        target = Path(item["path"]).resolve()
        if target.parent != backup_root or target.is_symlink() or not target.is_dir():
            refused.append({"backup_id": str(item.get("backup_id")), "reason": "PATH_BOUNDARY"})
            continue
        fresh = load_package_record(target)
        if fresh.get("kind") != "automatic" or fresh.get("fresh_verification") != "PASS":
            refused.append({"backup_id": str(item.get("backup_id")), "reason": "NO_LONGER_VALID_AUTOMATIC"})
            continue
        shutil.rmtree(target)
        deleted.append(str(item.get("backup_id")))
    return {
        "schema": APPLY_SCHEMA,
        "status": "PASS" if not refused else "PARTIAL",
        "deleted_backup_ids": deleted,
        "refused": refused,
        "manual_delete_performed": False,
        "non_automatic_delete_performed": False,
        "confirmation": CONFIRM_DELETE,
    }


def policy_run(policy_path: Path, clpctl: str, rclone: str) -> dict[str, Any]:
    policy = validate_policy(policy_path)
    backup_dir = Path(policy["local_backup_dir"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    results: list[dict[str, Any]] = []
    failed = False
    for domain in policy["sites"]:
        record: dict[str, Any] = {"domain": domain, "backup": "NOT_RUN", "remote": "NOT_RUN"}
        try:
            package = package_engine.build_backup(Path(policy["source_root"]), domain, backup_dir, clpctl, "automatic")
            record["backup"] = "PASS"
            record["backup_id"] = package.name
            if policy["backup"]["upload_remote"]:
                storage_config = policy["storage_config"]
                if not storage_config:
                    raise PolicyError("storage_config is missing")
                remote = storage_engine.push(Path(storage_config), package, policy["backup"]["remote_target"], rclone)
                record["remote"] = remote.get("status", "FAIL")
                record["remote_provider"] = remote.get("provider")
                record["remote_account_id"] = remote.get("account_id")
                if remote.get("status") != "PASS":
                    failed = True
            else:
                record["remote"] = "DISABLED"
        except (RuntimeError, OSError, storage_engine.StorageError, PolicyError) as exc:
            record["error_class"] = exc.__class__.__name__
            record["status"] = "FAIL"
            failed = True
        else:
            record["status"] = "PASS"
        results.append(record)

    retention = None
    if policy["retention"]["auto_delete_automatic"]:
        try:
            retention = retention_apply(policy_path, CONFIRM_DELETE)
            if retention["status"] not in {"PASS"}:
                failed = True
        except PolicyError as exc:
            retention = {"status": "FAIL", "error_class": exc.__class__.__name__}
            failed = True

    return {
        "schema": RUN_SCHEMA,
        "status": "PASS" if not failed else "FAIL",
        "backup_kind": "automatic",
        "sites": results,
        "retention": retention,
        "dns_changed": False,
        "production_restore_performed": False,
        "secrets_emitted": False,
    }


def cron_line(policy_path: Path, vfops_path: str) -> dict[str, Any]:
    policy = validate_policy(policy_path)
    hour, minute = policy["automation"]["daily_at"].split(":")
    command = f"{shlex.quote(vfops_path)} policy run --policy {shlex.quote(str(policy_path.resolve()))}"
    line = f"{int(minute)} {int(hour)} * * * {command}"
    return {
        "schema": "vf-server-ops.automation-cron.v1",
        "status": "ENABLED_POLICY" if policy["automation"]["enabled"] else "DISABLED_POLICY",
        "cron": line,
        "writes_performed": False,
        "install_performed": False,
        "scope": "VF_SERVER_OPS_POLICY_RUN_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops settings/retention/automation policy")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--policy", required=True)

    run = sub.add_parser("run")
    run.add_argument("--policy", required=True)
    run.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"))
    run.add_argument("--rclone", default=os.environ.get("VFOPS_RCLONE", "rclone"))

    plan = sub.add_parser("retention-plan")
    plan.add_argument("--policy", required=True)

    apply = sub.add_parser("retention-apply")
    apply.add_argument("--policy", required=True)
    apply.add_argument("--confirm", required=True)

    cron = sub.add_parser("render-cron")
    cron.add_argument("--policy", required=True)
    cron.add_argument("--vfops", default="vfops")

    args = parser.parse_args()
    try:
        if args.command == "validate":
            result = validate_policy(Path(args.policy))
        elif args.command == "run":
            result = policy_run(Path(args.policy), args.clpctl, args.rclone)
        elif args.command == "retention-plan":
            result = retention_plan(Path(args.policy))
        elif args.command == "retention-apply":
            result = retention_apply(Path(args.policy), args.confirm)
        else:
            result = cron_line(Path(args.policy), args.vfops)
    except PolicyError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 11
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") not in {"FAIL", "PARTIAL"} else 11


if __name__ == "__main__":
    raise SystemExit(main())
