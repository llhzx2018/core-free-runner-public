#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import cutover
import inventory
import package as package_engine
import restore_apply
import restore_new
import runtime as runtime_engine
import verify as verify_engine

MIGRATION_SCHEMA = "vf-server-ops.migration-result.v1"


class MigrationError(RuntimeError):
    pass


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def sandbox_migrate(package_dir: Path, target_root: Path, clpctl: str) -> dict:
    package_dir = package_dir.resolve()
    target_root = target_root.resolve()
    fresh = package_engine.verify_package(package_dir)
    if fresh.get("status") != "PASS":
        raise MigrationError("source backup package failed fresh verification")

    try:
        restored = restore_apply.apply_sandbox(package_dir, target_root, clpctl)
    except restore_apply.SandboxRestoreError as exc:
        raise MigrationError(f"sandbox target restore failed: {exc}") from exc

    try:
        verified = verify_engine.verify_restore(package_dir, target_root, clpctl)
    except verify_engine.RestoreVerifyError as exc:
        return {
            "schema": MIGRATION_SCHEMA,
            "mode": "SANDBOX_MIGRATION",
            "status": "SANDBOX_MIGRATION_VERIFY_FAILED",
            "backup_id": restored.get("backup_id"),
            "domain": restored.get("domain"),
            "restore_status": restored.get("status"),
            "verify_status": "ERROR",
            "verify_error_class": exc.__class__.__name__,
            "restore_engine_reused": True,
            "portable_backup_package_reused": True,
            "target_retained_for_diagnosis": True,
            "cutover_ready": False,
            "dns_changed": False,
            "old_server_delete_requested": False,
            "production_write_allowed": False,
            "secrets_emitted": False,
        }

    success = verified.get("status") == "RESTORE_VERIFIED"
    return {
        "schema": MIGRATION_SCHEMA,
        "mode": "SANDBOX_MIGRATION",
        "status": "SANDBOX_MIGRATION_VERIFIED" if success else "SANDBOX_MIGRATION_VERIFY_FAILED",
        "backup_id": restored.get("backup_id"),
        "domain": restored.get("domain"),
        "restore_status": restored.get("status"),
        "verify_status": verified.get("status"),
        "verified_scope": verified.get("scope"),
        "failed_components": verified.get("failed_components", []),
        "restore_engine_reused": True,
        "verify_engine_reused": True,
        "portable_backup_package_reused": True,
        "target_retained_for_diagnosis": not success,
        "cutover_ready": False,
        "cutover_blockers": [
            "REAL_CLOUDPANEL_TARGET_GATE_NOT_RUN",
            "HTTP_HTTPS_HOSTS_VERIFICATION_NOT_RUN",
            "SOURCE_TARGET_CROSS_SERVER_RECONCILIATION_NOT_RUN",
        ],
        "dns_changed": False,
        "old_server_delete_requested": False,
        "production_write_allowed": False,
        "secrets_emitted": False,
    }


def load_source_site_snapshot(package_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    path = package_dir / "metadata" / "inventory-site.json"
    try:
        site = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationError("source site inventory snapshot is missing or invalid") from exc
    if not isinstance(site, dict):
        raise MigrationError("source site inventory snapshot is invalid")
    domain = str(manifest.get("site", {}).get("domain", ""))
    if site.get("domain") != domain and domain not in site.get("domains", []):
        raise MigrationError("source site inventory snapshot does not match backup domain")
    return site


def expected_new_site_migration_confirm(manifest: dict[str, Any]) -> str:
    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    domain = str(site.get("domain", ""))
    backup_id = str(manifest.get("backup_id", ""))
    if not domain or not backup_id:
        raise MigrationError("backup identity is incomplete")
    return f"MIGRATE_NEW_SITE:{domain}:{backup_id}"


def migration_evidence_path(target_root: Path, backup_id: str) -> Path:
    if backup_id != package_engine.safe_name(backup_id):
        raise MigrationError("backup id is not safe for migration evidence path")
    return target_root / "var/lib/vf-server-ops/migrations" / backup_id


def persist_migration_evidence(target_root: Path, backup_id: str, source_site: dict[str, Any], target_inventory: dict[str, Any], result: dict[str, Any]) -> str:
    evidence = migration_evidence_path(target_root, backup_id)
    if evidence.exists():
        raise MigrationError("migration evidence directory already exists")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(evidence.parent, 0o700)
    evidence.mkdir(mode=0o700)
    try:
        write_private_json(evidence / "source-site.json", source_site)
        write_private_json(evidence / "target-inventory.json", target_inventory)
        write_private_json(evidence / "migration-result.json", result)
    except Exception:
        for item in evidence.glob("*"):
            item.unlink(missing_ok=True)
        evidence.rmdir()
        raise
    return str(evidence)


def new_site_migrate(
    package_dir: Path,
    target_root: Path,
    target_ip: str,
    confirm: str,
    clpctl: str,
    crontab: str,
    runuser: str,
    pm2: str,
    chown: str,
    curl: str,
    path: str,
) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    target_root = target_root.resolve()
    fresh = package_engine.verify_package(package_dir)
    if fresh.get("status") != "PASS":
        raise MigrationError("source backup package failed fresh verification")
    try:
        manifest = restore_new.load_manifest(package_dir)
    except restore_new.NewSiteRestoreError as exc:
        raise MigrationError("backup manifest is invalid for new-site migration") from exc

    required = expected_new_site_migration_confirm(manifest)
    if confirm != required:
        raise MigrationError(f"explicit confirmation required: {required}")

    domain = str(manifest.get("site", {}).get("domain", ""))
    domains = manifest.get("site", {}).get("domains", [domain])
    if not isinstance(domains, list):
        domains = [domain]
    backup_id = str(manifest.get("backup_id", ""))
    evidence = migration_evidence_path(target_root, backup_id)
    if evidence.exists():
        raise MigrationError("migration evidence already exists; refusing ambiguous rerun")
    source_site = load_source_site_snapshot(package_dir, manifest)

    try:
        restored = restore_new.restore_new_site(
            package_dir,
            target_root,
            clpctl,
            restore_new.expected_confirm(manifest),
        )
    except restore_new.NewSiteRestoreError as exc:
        raise MigrationError(f"new-site restore failed: {exc}") from exc

    runtime_status = "NOT_RUN"
    runtime_manual_gates: list[dict[str, str]] = []
    runtime_error_class: str | None = None
    try:
        runtime_plan = runtime_engine.build_plan(package_dir, target_root)
        runtime_manual_gates = runtime_plan.get("manual_cron", []) if isinstance(runtime_plan.get("manual_cron"), list) else []
        if runtime_manual_gates:
            runtime_status = "MANUAL_GATE_REQUIRED"
        else:
            runtime_result = runtime_engine.apply_runtime(
                package_dir,
                target_root,
                f"ACTIVATE_RUNTIME:{domain}:{backup_id}",
                crontab,
                runuser,
                pm2,
                chown,
            )
            runtime_status = str(runtime_result.get("status", "UNKNOWN"))
    except runtime_engine.RuntimeActivationError as exc:
        runtime_status = "FAILED"
        runtime_error_class = exc.__class__.__name__

    try:
        restore_verified = verify_engine.verify_restore(package_dir, target_root, clpctl)
        restore_status = str(restore_verified.get("status", "UNKNOWN"))
    except verify_engine.RestoreVerifyError as exc:
        restore_status = "ERROR"
        restore_error_class = exc.__class__.__name__
    else:
        restore_error_class = None

    target_inventory = inventory.build_manifest(target_root)
    try:
        target_site = cutover.find_site(target_inventory, domain)
        cross_site = cutover.compare_site(source_site, target_site, domain)
    except cutover.CutoverError:
        cross_site = {
            "status": "FAIL",
            "domain": domain,
            "checks": [],
            "failures": ["TARGET_SITE_NOT_FOUND"],
            "unknowns": [],
        }

    try:
        probe = cutover.http_https_probe([str(item) for item in domains if isinstance(item, str) and item], target_ip, curl, path)
    except cutover.CutoverError as exc:
        probe = {
            "status": "FAIL",
            "target_ip": target_ip,
            "path": path,
            "results": [],
            "skipped_wildcards": [],
            "failures": [exc.__class__.__name__],
            "dns_changed": False,
            "method": "CURL_RESOLVE_HOST_AND_SNI",
        }

    blockers: list[str] = []
    if restore_status != "RESTORE_VERIFIED":
        blockers.append("RESTORE_NOT_VERIFIED")
    if runtime_status != "RUNTIME_ACTIVATED":
        blockers.append("RUNTIME_NOT_ACTIVATED")
    if runtime_manual_gates:
        blockers.append("RUNTIME_MANUAL_GATE_REQUIRED")
    if cross_site.get("status") != "PASS":
        blockers.append("CROSS_SERVER_VERIFY_NOT_PASS")
    if probe.get("status") != "PASS":
        blockers.append("HTTP_HTTPS_TARGET_PROBE_NOT_PASS")

    ready = not blockers
    source_server = manifest.get("source", {}).get("server", {}).get("hostname_hash", "UNKNOWN")
    target_server = target_inventory.get("source_server", {}).get("hostname_hash", "UNKNOWN")
    result: dict[str, Any] = {
        "schema": MIGRATION_SCHEMA,
        "mode": "NEW_SITE_MIGRATION",
        "status": "TECHNICAL_CUTOVER_READY" if ready else "NEW_SITE_MIGRATION_NOT_READY",
        "backup_id": backup_id,
        "domain": domain,
        "restore_status": restore_status,
        "restore_error_class": restore_error_class,
        "runtime_status": runtime_status,
        "runtime_error_class": runtime_error_class,
        "runtime_manual_gates": runtime_manual_gates,
        "cross_server_status": cross_site.get("status"),
        "cross_server": {
            "site": cross_site,
            "source_server_identity": source_server,
            "target_server_identity": target_server,
            "server_identity_changed": None if "UNKNOWN" in (source_server, target_server) else source_server != target_server,
            "server_identity_is_not_a_business_asset_match_requirement": True,
        },
        "http_https_status": probe.get("status"),
        "http_https_probe": probe,
        "blockers": blockers,
        "restore_engine_reused": True,
        "runtime_engine_reused": True,
        "verify_engine_reused": True,
        "portable_backup_package_reused": True,
        "owner_migration_confirmation_verified": True,
        "owner_cutover_gate_required": True,
        "technical_cutover_ready": ready,
        "automatic_dns_change": False,
        "dns_changed": False,
        "old_server_delete_requested": False,
        "existing_site_overwrite_allowed": False,
        "target_retained_for_owner_cutover_or_diagnosis": True,
        "secrets_emitted": False,
    }
    evidence_path = persist_migration_evidence(target_root, backup_id, source_site, target_inventory, result)
    result["evidence_path"] = evidence_path
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops migration orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    sandbox = sub.add_parser("apply-sandbox", help="rehearse migration by reusing restore + verify engines")
    sandbox.add_argument("--package", required=True)
    sandbox.add_argument("--target-root", required=True)
    sandbox.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"))

    new_site = sub.add_parser("apply-new-site", help="restore a brand-new CloudPanel site, activate runtime, verify target, and stop before DNS cutover")
    new_site.add_argument("--package", required=True)
    new_site.add_argument("--target-root", default="/")
    new_site.add_argument("--target-ip", required=True)
    new_site.add_argument("--path", default="/")
    new_site.add_argument("--confirm", required=True)
    new_site.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"))
    new_site.add_argument("--crontab", default=os.environ.get("VFOPS_CRONTAB", "crontab"))
    new_site.add_argument("--runuser", default=os.environ.get("VFOPS_RUNUSER", "runuser"))
    new_site.add_argument("--pm2", default=os.environ.get("VFOPS_PM2", "pm2"))
    new_site.add_argument("--chown", default=os.environ.get("VFOPS_CHOWN", "chown"))
    new_site.add_argument("--curl", default=os.environ.get("VFOPS_CURL", "curl"))
    args = parser.parse_args()

    try:
        if args.command == "apply-sandbox":
            result = sandbox_migrate(Path(args.package), Path(args.target_root), args.clpctl)
            success = result["status"] == "SANDBOX_MIGRATION_VERIFIED"
        else:
            result = new_site_migrate(
                Path(args.package), Path(args.target_root), args.target_ip, args.confirm,
                args.clpctl, args.crontab, args.runuser, args.pm2, args.chown, args.curl, args.path,
            )
            success = result["status"] == "TECHNICAL_CUTOVER_READY"
    except MigrationError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 9
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if success else 9


if __name__ == "__main__":
    raise SystemExit(main())
