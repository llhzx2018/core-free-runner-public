#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

import inventory
import package as package_engine
import restore as restore_plan
import restore_apply
import verify as verify_engine

RESULT_SCHEMA = "vf-server-ops.new-site-restore-result.v1"
CONTROLLED_MARKER = ".vfops-controlled-cloudpanel-target"
CONTROLLED_MARKER_VALUE = "VF_SERVER_OPS_CONTROLLED_CLOUDPANEL_TARGET_V1"


class NewSiteRestoreError(RuntimeError):
    pass


def load_manifest(package_dir: Path) -> dict:
    try:
        payload = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NewSiteRestoreError("backup manifest is invalid") from exc
    if payload.get("schema") != package_engine.PACKAGE_SCHEMA:
        raise NewSiteRestoreError("unsupported backup package schema")
    return payload


def expected_confirm(manifest: dict) -> str:
    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    domain = str(site.get("domain", ""))
    backup_id = str(manifest.get("backup_id", ""))
    if not domain or not backup_id:
        raise NewSiteRestoreError("backup identity is incomplete")
    return f"RESTORE_NEW_SITE:{domain}:{backup_id}"


def require_target(target_root: Path, manifest: dict, confirm: str) -> Path:
    root = target_root.resolve()
    if not root.is_dir():
        raise NewSiteRestoreError("target root must already exist")
    required = expected_confirm(manifest)
    if confirm != required:
        raise NewSiteRestoreError(f"explicit confirmation required: {required}")

    if root == Path("/"):
        panel_db = Path("/home/clp/htdocs/app/data/db.sq3")
        if not panel_db.is_file():
            raise NewSiteRestoreError("/ is not a detected CloudPanel target")
    else:
        marker = root / CONTROLLED_MARKER
        try:
            value = marker.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise NewSiteRestoreError("controlled CloudPanel target marker is missing") from exc
        if value != CONTROLLED_MARKER_VALUE:
            raise NewSiteRestoreError("controlled CloudPanel target marker is invalid")
    return root


def target_has_site(target_root: Path, domain: str, site_root: str) -> bool:
    final_site = restore_plan.target_path(target_root, site_root)
    if final_site.exists():
        return True
    try:
        manifest = inventory.build_manifest(target_root)
    except Exception:
        return False
    for site in manifest.get("sites", []):
        if isinstance(site, dict) and (site.get("domain") == domain or domain in site.get("domains", [])):
            return True
    return False


def safe_cleanup_site(clpctl: str, domain: str) -> str:
    try:
        restore_apply.run_clpctl(clpctl, ["site:delete", f"--domainName={domain}", "--force"], timeout=300)
    except restore_apply.SandboxRestoreError:
        return "SITE_DELETE_FAILED_OR_UNVERIFIED"
    return "SITE_DELETE_REQUESTED"


def safe_cleanup_database(clpctl: str, database: str) -> str:
    for args in (
        ["db:delete", f"--databaseName={database}", "--force"],
        ["db:delete", f"--databaseName={database}"],
    ):
        try:
            restore_apply.run_clpctl(clpctl, args, timeout=300)
            return "DATABASE_DELETE_REQUESTED"
        except restore_apply.SandboxRestoreError:
            continue
    return "DATABASE_DELETE_FAILED_OR_UNVERIFIED"


def reconcile_site_ownership(staged_site: Path, cloudpanel_site: Path) -> tuple[int, int]:
    """Apply the ownership chosen by CloudPanel for its bootstrap site to the restored tree.

    The archive is deliberately extracted by the privileged restore process without trusting
    source numeric ownership. The freshly-created CloudPanel site is therefore the target-side
    ownership authority. Symlinks are never followed while ownership is reconciled.
    """
    try:
        reference = cloudpanel_site.stat()
    except OSError as exc:
        raise NewSiteRestoreError("CloudPanel bootstrap ownership cannot be inspected") from exc

    uid, gid = reference.st_uid, reference.st_gid
    try:
        for current, dirs, files in os.walk(staged_site, topdown=False, followlinks=False):
            current_path = Path(current)
            for name in files:
                os.chown(current_path / name, uid, gid, follow_symlinks=False)
            for name in dirs:
                os.chown(current_path / name, uid, gid, follow_symlinks=False)
            os.chown(current_path, uid, gid, follow_symlinks=False)
    except OSError as exc:
        raise NewSiteRestoreError("restored site ownership reconciliation failed") from exc
    return uid, gid


def restore_new_site(package_dir: Path, target_root: Path, clpctl: str, confirm: str) -> dict:
    package_dir = package_dir.resolve()
    fresh = package_engine.verify_package(package_dir)
    if fresh.get("status") != "PASS":
        raise NewSiteRestoreError("backup package failed fresh verification")
    manifest = load_manifest(package_dir)
    target_root = require_target(target_root, manifest, confirm)
    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    domain = str(site.get("domain", ""))
    site_root = restore_plan.safe_absolute_site_path(str(site.get("site_root", "")))
    final_site = restore_plan.target_path(target_root, site_root)

    if target_has_site(target_root, domain, site_root):
        raise NewSiteRestoreError("target site already exists; new-site restore refuses overwrite")

    plan = restore_plan.build_plan(package_dir, target_root)
    if plan.get("status") == "BLOCKED":
        raise NewSiteRestoreError("restore plan is blocked")

    archive_rel = str(manifest.get("contents", {}).get("files_archive", ""))
    archive = restore_plan.safe_package_path(package_dir, archive_rel)
    archive_check = restore_plan.inspect_archive(archive)
    if archive_check.get("blockers"):
        raise NewSiteRestoreError("site archive failed extraction safety checks")

    created = False
    swap_committed = False
    ownership_reconciled = False
    created_databases: list[str] = []
    bootstrap_dir: Path | None = None
    staging: Path | None = None
    evidence_root = target_root / "var/lib/vf-server-ops/restored-metadata" / str(manifest.get("backup_id"))
    cleanup_status = "NOT_REQUIRED"
    failure_stage = "CLOUDPANEL_SITE_CREATE"
    steps: list[str] = []

    try:
        failure_stage = "CLOUDPANEL_SITE_CREATE"
        restore_apply.run_clpctl(clpctl, restore_apply.site_add_args(site))
        created = True
        steps.append("cloudpanel_site_created")

        failure_stage = "CLOUDPANEL_SITE_ROOT_CHECK"
        if not final_site.is_dir():
            raise NewSiteRestoreError("CloudPanel site:add did not create the expected site directory")
        parent = final_site.parent
        staging = Path(tempfile.mkdtemp(prefix=f".vfops-restore-{manifest.get('backup_id')}-", dir=parent))
        os.chmod(staging, 0o700)
        staged_site = staging / "site"

        failure_stage = "SITE_FILES_STAGE"
        restore_apply.extract_site_archive(archive, staged_site)
        failure_stage = "SQLITE_RESTORE"
        restore_apply.restore_sqlite(package_dir, manifest, staged_site, site_root)
        steps.append("site_files_and_sqlite_staged")

        mysql_entries = manifest.get("contents", {}).get("mysql", [])
        if not isinstance(mysql_entries, list):
            raise NewSiteRestoreError("MySQL manifest is invalid")
        for item in mysql_entries:
            if not isinstance(item, dict):
                raise NewSiteRestoreError("MySQL entry is invalid")
            database = str(item.get("database", ""))
            dump = restore_plan.safe_package_path(package_dir, str(item.get("file", "")))
            failure_stage = "MYSQL_RECOVERY_METADATA"
            row = restore_apply.private_database_row(package_dir, manifest, database)
            username, password = restore_apply.database_credentials(row, database)
            failure_stage = "MYSQL_DB_ADD"
            restore_apply.run_clpctl(clpctl, [
                "db:add",
                f"--domainName={domain}",
                f"--databaseName={database}",
                f"--databaseUserName={username}",
                f"--databaseUserPassword={password}",
            ])
            created_databases.append(database)
            failure_stage = "MYSQL_DB_IMPORT"
            restore_apply.run_clpctl(clpctl, ["db:import", f"--databaseName={database}", f"--file={dump}"])
        steps.append("mysql_restored")

        failure_stage = "RUNTIME_METADATA_STAGE"
        pending_meta = staging / "pending-metadata"
        pending = restore_apply.copy_pending_metadata(package_dir, manifest, pending_meta)
        steps.append("runtime_metadata_staged_not_enabled")

        failure_stage = "SSL_INSTALL"
        ssl_installed = restore_apply.install_certificate(package_dir, manifest, domain, clpctl)
        steps.append("ssl_installed" if ssl_installed else "ssl_deferred")

        failure_stage = "SITE_OWNERSHIP_RECONCILIATION"
        reconcile_site_ownership(staged_site, final_site)
        ownership_reconciled = True
        steps.append("site_ownership_reconciled_from_cloudpanel_bootstrap")

        failure_stage = "SITE_ATOMIC_COMMIT"
        bootstrap_dir = parent / f".vfops-bootstrap-{manifest.get('backup_id')}"
        if bootstrap_dir.exists():
            raise NewSiteRestoreError("bootstrap recovery point already exists")
        os.replace(final_site, bootstrap_dir)
        try:
            os.replace(staged_site, final_site)
        except Exception:
            os.replace(bootstrap_dir, final_site)
            bootstrap_dir = None
            raise
        swap_committed = True
        steps.append("site_files_atomically_committed")

        failure_stage = "RUNTIME_METADATA_EVIDENCE"
        if pending_meta.exists():
            evidence_root.parent.mkdir(parents=True, exist_ok=True)
            if evidence_root.exists():
                raise NewSiteRestoreError("runtime metadata evidence already exists")
            os.replace(pending_meta, evidence_root)
            os.chmod(evidence_root, 0o700)
        steps.append("runtime_metadata_evidence_committed")

        failure_stage = "RESTORE_VERIFY"
        verified = verify_engine.verify_restore(package_dir, target_root, clpctl)
        if verified.get("status") != "RESTORE_VERIFIED":
            failed_components = verified.get("failed_components", [])
            if isinstance(failed_components, list):
                for component in ("files", "sqlite", "mysql", "runtime_metadata"):
                    if component in failed_components:
                        failure_stage = f"RESTORE_VERIFY_{component.upper()}"
                        break
            raise NewSiteRestoreError("post-restore verification failed")
        steps.append("restore_verified")

        failure_stage = "BOOTSTRAP_CLEANUP"
        if bootstrap_dir and bootstrap_dir.exists():
            shutil.rmtree(bootstrap_dir)
            bootstrap_dir = None
        steps.append("cloudpanel_empty_bootstrap_removed")

        return {
            "schema": RESULT_SCHEMA,
            "status": "NEW_SITE_RESTORE_VERIFIED",
            "backup_id": manifest.get("backup_id"),
            "domain": domain,
            "target_root": str(target_root),
            "target_site_root": site_root,
            "restore_verify_status": verified.get("status"),
            "runtime_metadata_files_staged": len(pending),
            "runtime_activation_required": len(pending) > 0,
            "site_ownership_reconciled": ownership_reconciled,
            "site_ownership_source": "CLOUDPANEL_BOOTSTRAP_UID_GID",
            "cron_enabled": False,
            "pm2_started": False,
            "dns_changed": False,
            "cutover_ready": False,
            "owner_confirmation_verified": True,
            "existing_site_overwrite_allowed": False,
            "failure_cleanup_contract": "CREATED_DATABASE_DELETE_ATTEMPT; SITE_DELETE_REQUESTED",
            "steps": steps,
            "secrets_emitted": False,
        }
    except Exception as exc:
        if swap_committed and final_site.exists() and bootstrap_dir and bootstrap_dir.exists():
            failed_dir = final_site.parent / f".vfops-failed-{manifest.get('backup_id')}"
            try:
                if failed_dir.exists():
                    shutil.rmtree(failed_dir, ignore_errors=True)
                os.replace(final_site, failed_dir)
                os.replace(bootstrap_dir, final_site)
                bootstrap_dir = None
                shutil.rmtree(failed_dir, ignore_errors=True)
            except OSError:
                pass
        if evidence_root.exists():
            shutil.rmtree(evidence_root, ignore_errors=True)

        database_cleanup = "DATABASE_DELETE_NOT_REQUIRED"
        if created_databases:
            outcomes = [safe_cleanup_database(clpctl, database) for database in reversed(created_databases)]
            database_cleanup = (
                "DATABASE_DELETE_REQUESTED"
                if all(item == "DATABASE_DELETE_REQUESTED" for item in outcomes)
                else "DATABASE_DELETE_PARTIAL_OR_UNVERIFIED"
            )
        site_cleanup = safe_cleanup_site(clpctl, domain) if created else "SITE_DELETE_NOT_REQUIRED"
        cleanup_status = f"{database_cleanup};{site_cleanup}"

        reason = exc.__class__.__name__
        raise NewSiteRestoreError(
            f"new-site restore failed; stage={failure_stage}; cleanup={cleanup_status}; reason={reason}"
        ) from exc
    finally:
        if staging and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops guarded restore to a new CloudPanel site")
    parser.add_argument("--package", required=True)
    parser.add_argument("--target-root", default="/")
    parser.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"))
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        result = restore_new_site(Path(args.package), Path(args.target_root), args.clpctl, args.confirm)
    except NewSiteRestoreError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 12
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())