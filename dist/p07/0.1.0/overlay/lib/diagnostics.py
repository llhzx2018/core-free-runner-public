#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys

SCHEMA = "VFOPS_DIAGNOSTIC_V1"
SAFE_TOKEN_RE = re.compile(r"^[A-Z][A-Z0-9_+-]*$")
STAGE_RE = re.compile(r"\bstage=([A-Z][A-Z0-9_]*)\b")
CLEANUP_RE = re.compile(r"\bcleanup=([A-Z][A-Z0-9_;+_-]*)\b")

OPERATION_CLASS = {
    "inventory": "INVENTORY_ERROR",
    "backup": "BACKUP_ERROR",
    "storage": "STORAGE_ERROR",
    "restore": "RESTORE_ERROR",
    "runtime": "RUNTIME_ERROR",
    "verify": "VERIFY_ERROR",
    "migrate.transfer-new-site": "TRANSPORT_ERROR",
    "migrate": "MIGRATION_ERROR",
    "policy": "POLICY_ERROR",
}

OPERATION_STAGE = {
    "inventory": "INVENTORY",
    "backup": "BACKUP",
    "storage": "STORAGE",
    "restore.plan": "RESTORE_PLAN",
    "restore": "RESTORE",
    "runtime.plan": "RUNTIME_PLAN",
    "runtime": "RUNTIME_ACTIVATION",
    "verify.cross": "CROSS_SERVER_VERIFY",
    "verify.cutover": "CUTOVER_VERIFY",
    "verify": "VERIFY",
    "migrate.transfer-new-site": "TRANSPORT",
    "migrate": "MIGRATION",
    "policy": "POLICY",
}

BLOCKER_RULES = (
    ("application database recovery credentials could not be discovered safely", "DB_RECOVERY_DISCOVERY_FAILED"),
    ("portable database recovery credentials unavailable", "DB_RECOVERY_INPUT_REQUIRED"),
    ("cloudpanel private metadata is required for portable mysql recovery", "DB_RECOVERY_INPUT_REQUIRED"),
    ("cloudpanel private metadata cannot be read for portable mysql recovery", "DB_RECOVERY_METADATA_UNAVAILABLE"),
    ("cloudpanel site schema is unsupported for portable mysql recovery", "DB_RECOVERY_METADATA_UNAVAILABLE"),
    ("cloudpanel site row is required for portable mysql recovery", "DB_RECOVERY_METADATA_UNAVAILABLE"),
    ("cloudpanel private metadata query failed for portable mysql recovery", "DB_RECOVERY_METADATA_UNAVAILABLE"),
    ("cloudpanel database export failed", "DB_EXPORT_FAILED"),
    ("mysql gzip validation failed", "DB_EXPORT_INVALID"),
    ("mysql association is unknown", "DB_ASSOCIATION_UNKNOWN"),
    ("explicit confirmation required", "CONFIRMATION_REQUIRED"),
    ("confirmation", "CONFIRMATION_MISMATCH"),
    ("fresh verification", "FRESH_VERIFY_NOT_PASS"),
    ("failed fresh verification", "FRESH_VERIFY_NOT_PASS"),
    ("already exists", "TARGET_STATE_CONFLICT"),
    ("preflight failed", "TARGET_PREFLIGHT_FAILED"),
    ("unresolved system/unsupported cron", "RUNTIME_MANUAL_GATE_REQUIRED"),
    ("non-empty crontab", "TARGET_CRONTAB_CONFLICT"),
    ("pm2", "PM2_RUNTIME_FAILED"),
    ("no google drive pool account has enough verified free space", "GOOGLE_POOL_CAPACITY_NOT_READY"),
    ("not a verified rclone crypt remote", "ENCRYPTED_REMOTE_NOT_VERIFIED"),
    ("remote backup fetch failed", "REMOTE_FETCH_FAILED"),
    ("remote package transfer failed", "REMOTE_TRANSFER_FAILED"),
    ("encrypted integrity check failed", "REMOTE_INTEGRITY_NOT_PASS"),
    ("site not found", "SITE_NOT_FOUND"),
)


def _prefix_match(mapping: dict[str, str], operation: str, default: str) -> str:
    if operation in mapping:
        return mapping[operation]
    matches = [(key, value) for key, value in mapping.items() if operation.startswith(key + ".")]
    if matches:
        matches.sort(key=lambda item: len(item[0]), reverse=True)
        return matches[0][1]
    return default


def infer_stage(operation: str, stderr: str) -> str:
    match = STAGE_RE.search(stderr or "")
    if match:
        return match.group(1)
    lower = (stderr or "").lower()
    if "pm2" in lower or "crontab" in lower or "runtime activation" in lower:
        return "RUNTIME_ACTIVATION"
    if "mysql" in lower or "database" in lower:
        return "DATABASE"
    if "ssl" in lower or "certificate" in lower:
        return "SSL"
    if "http" in lower or "https" in lower:
        return "HTTP_HTTPS"
    if "cross-server" in lower or "cross server" in lower:
        return "CROSS_SERVER_VERIFY"
    return _prefix_match(OPERATION_STAGE, operation, "OPERATION")


def infer_error_class(operation: str) -> str:
    return _prefix_match(OPERATION_CLASS, operation, "OPERATION_ERROR")


def infer_blocker(stderr: str) -> str:
    lower = (stderr or "").lower()
    for needle, code in BLOCKER_RULES:
        if needle in lower:
            return code
    return "UNCLASSIFIED_FAILURE"


def infer_cleanup(stderr: str) -> str:
    match = CLEANUP_RE.search(stderr or "")
    if not match:
        return "NOT_REPORTED"
    value = match.group(1).replace(";", "+")
    return value if SAFE_TOKEN_RE.fullmatch(value) else "NOT_REPORTED"


def render(operation: str, exit_code: int, stderr: str) -> str:
    stage = infer_stage(operation, stderr)
    error_class = infer_error_class(operation)
    blocker = infer_blocker(stderr)
    cleanup = infer_cleanup(stderr)
    return (
        f"{SCHEMA} stage={stage} error_class={error_class} "
        f"blocker={blocker} cleanup={cleanup} exit_code={exit_code}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops safe failure diagnostics")
    parser.add_argument("--operation", required=True)
    parser.add_argument("--exit-code", required=True, type=int)
    args = parser.parse_args()
    if args.exit_code == 0:
        print("ERROR: diagnostics requires a non-zero exit code", file=sys.stderr)
        return 2
    stderr = sys.stdin.read()
    print(render(args.operation, args.exit_code, stderr))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
