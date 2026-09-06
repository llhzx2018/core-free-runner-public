#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import tarfile
from typing import Any

import package as package_engine

PLAN_SCHEMA = "vf-server-ops.restore-plan.v1"
UNKNOWN = "UNKNOWN"
MAX_ARCHIVE_MEMBERS = 500_000
MAX_UNCOMPRESSED_BYTES = 500 * 1024 ** 3
MAX_EXPANSION_RATIO = 5000


class RestorePlanError(RuntimeError):
    pass


def safe_package_path(package_dir: Path, relative: str) -> Path:
    rel = PurePosixPath(relative)
    if not relative or rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise RestorePlanError(f"unsafe package path: {relative}")
    target = package_dir / Path(*rel.parts)
    root = package_dir.resolve()
    resolved = target.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise RestorePlanError(f"package path escapes package: {relative}")
    return target


def safe_absolute_site_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value.startswith("/") or any(part in ("", ".", "..") for part in path.parts[1:]):
        raise RestorePlanError(f"unsafe target site path: {value}")
    if len(path.parts) < 5 or path.parts[1] != "home" or path.parts[3] != "htdocs":
        raise RestorePlanError(f"site path is outside CloudPanel site boundary: {value}")
    return path.as_posix()


def target_path(target_root: Path, absolute: str) -> Path:
    target_root = target_root.resolve()
    candidate = (target_root / absolute.lstrip("/")).resolve(strict=False)
    if candidate != target_root and target_root not in candidate.parents:
        raise RestorePlanError(f"target path escapes target root: {absolute}")
    return candidate


def inspect_archive(archive_path: Path) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    member_count = 0
    file_count = 0
    uncompressed = 0
    try:
        compressed = archive_path.stat().st_size
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive:
                member_count += 1
                if member_count > MAX_ARCHIVE_MEMBERS:
                    blockers.append("ARCHIVE_MEMBER_LIMIT_EXCEEDED")
                    break
                name = member.name
                pure = PurePosixPath(name)
                if pure.is_absolute() or any(part == ".." for part in pure.parts):
                    blockers.append(f"ARCHIVE_PATH_ESCAPE:{name}")
                    continue
                if not pure.parts or pure.parts[0] != "site":
                    blockers.append(f"ARCHIVE_UNEXPECTED_ROOT:{name}")
                    continue
                if member.ischr() or member.isblk() or member.isfifo():
                    blockers.append(f"ARCHIVE_SPECIAL_FILE:{name}")
                if member.issym() or member.islnk():
                    link = member.linkname
                    if not link or link.startswith("/"):
                        blockers.append(f"ARCHIVE_UNSAFE_LINK:{name}")
                    else:
                        normalized = posixpath.normpath(posixpath.join(posixpath.dirname(name), link))
                        if normalized != "site" and not normalized.startswith("site/"):
                            blockers.append(f"ARCHIVE_LINK_ESCAPE:{name}")
                if member.isfile():
                    file_count += 1
                    uncompressed += max(0, int(member.size))
                    if uncompressed > MAX_UNCOMPRESSED_BYTES:
                        blockers.append("ARCHIVE_UNCOMPRESSED_LIMIT_EXCEEDED")
                        break
    except (OSError, tarfile.TarError) as exc:
        raise RestorePlanError("site archive cannot be inspected safely") from exc

    ratio = (uncompressed / compressed) if compressed > 0 else None
    if ratio is not None and ratio > MAX_EXPANSION_RATIO:
        blockers.append("ARCHIVE_EXPANSION_RATIO_EXCEEDED")
    if file_count == 0:
        blockers.append("ARCHIVE_HAS_NO_FILES")
    return {
        "member_count": member_count,
        "file_count": file_count,
        "compressed_bytes": compressed,
        "uncompressed_bytes": uncompressed,
        "expansion_ratio": ratio,
        "blockers": sorted(set(blockers)),
        "warnings": warnings,
    }


def read_json_private_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False, "schema": None, "tables": {}, "database_fields": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RestorePlanError("CloudPanel private recovery metadata is invalid JSON") from exc
    tables = payload.get("tables", {}) if isinstance(payload, dict) else {}
    db_rows = tables.get("database", []) if isinstance(tables, dict) else []
    fields: set[str] = set()
    if isinstance(db_rows, list):
        for row in db_rows:
            if isinstance(row, dict):
                fields.update(str(key) for key in row.keys())
    return {
        "present": True,
        "schema": payload.get("schema") if isinstance(payload, dict) else None,
        "tables": {name: len(rows) for name, rows in tables.items() if isinstance(rows, list)} if isinstance(tables, dict) else {},
        "database_fields": sorted(fields),
        "values_emitted": False,
    }


def database_private_metadata_matches(package_dir: Path, manifest: dict[str, Any], database: str) -> tuple[bool, str]:
    metadata_info = manifest.get("contents", {}).get("metadata", {}).get("cloudpanel_private_metadata", {})
    relative = metadata_info.get("file") if isinstance(metadata_info, dict) else None
    if not isinstance(relative, str):
        return False, "MISSING"
    path = safe_package_path(package_dir, relative)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "INVALID"
    rows = payload.get("tables", {}).get("database", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return False, "INVALID"
    for row in rows:
        if isinstance(row, dict) and str(row.get("name", "")) == database:
            return True, "CAPTURED_RAW_ROW"
    return False, "NOT_FOUND"


def build_site_create_action(site: dict[str, Any]) -> dict[str, Any]:
    domain = str(site.get("domain", UNKNOWN))
    user = str(site.get("site_user", UNKNOWN))
    runtime = site.get("runtime", {}) if isinstance(site.get("runtime"), dict) else {}
    runtime_type = str(runtime.get("type", UNKNOWN)).lower()
    version = runtime.get("version", UNKNOWN)
    app_port = runtime.get("app_port", UNKNOWN)
    common = {"domain": domain, "site_user": user, "site_user_password": "RUNTIME_GENERATED_SECRET"}

    if runtime_type == "php":
        return {
            "type": "cloudpanel_site_prepare",
            "method": "clpctl site:add:php",
            "parameters": {**common, "php_version": version, "vhost_template": "RECOVER_FROM_PRIVATE_METADATA_OR_REVIEW"},
        }
    if "node" in runtime_type or "reverse_proxy" in runtime_type:
        return {
            "type": "cloudpanel_site_prepare",
            "method": "clpctl site:add:nodejs_or_reverse_proxy",
            "parameters": {**common, "runtime_version": version, "app_port": app_port},
        }
    if "static" in runtime_type:
        return {"type": "cloudpanel_site_prepare", "method": "clpctl site:add:static", "parameters": common}
    return {"type": "cloudpanel_site_prepare", "method": "UNSUPPORTED_OR_REVIEW_REQUIRED", "parameters": common}


def build_plan(package_dir: Path, target_root: Path) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    target_root = target_root.resolve()
    if not target_root.is_dir():
        raise RestorePlanError("target root must already exist for dry-run")

    fresh = package_engine.verify_package(package_dir)
    if fresh.get("status") != "PASS":
        raise RestorePlanError("backup package failed fresh verification")

    try:
        manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RestorePlanError("backup manifest is invalid") from exc
    if manifest.get("schema") != package_engine.PACKAGE_SCHEMA:
        raise RestorePlanError("unsupported backup package schema")

    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    site_root = safe_absolute_site_path(str(site.get("site_root", "")))
    target_site = target_path(target_root, site_root)
    target_exists = target_site.exists()
    blockers: list[str] = []
    warnings: list[str] = []
    gates: list[str] = []

    files_rel = manifest.get("contents", {}).get("files_archive")
    if not isinstance(files_rel, str):
        raise RestorePlanError("package has no files archive reference")
    archive_path = safe_package_path(package_dir, files_rel)
    archive = inspect_archive(archive_path)
    blockers.extend(archive["blockers"])
    warnings.extend(archive["warnings"])

    if target_exists:
        gates.append("OWNER_OVERWRITE_GATE_REQUIRED")

    site_action = build_site_create_action(site)
    if site_action["method"] == "UNSUPPORTED_OR_REVIEW_REQUIRED":
        blockers.append("SITE_RUNTIME_REQUIRES_MANUAL_MAPPING")

    actions: list[dict[str, Any]] = [
        {
            "order": 1,
            "type": "target_precheck",
            "target_site_root": site_root,
            "target_exists": target_exists,
            "writes": False,
        },
        {"order": 2, **site_action, "writes": True},
        {
            "order": 3,
            "type": "restore_site_files",
            "source": files_rel,
            "target": site_root,
            "archive_root": "site/",
            "writes": True,
        },
    ]

    order = 4
    mysql_entries = manifest.get("contents", {}).get("mysql", [])
    if not isinstance(mysql_entries, list):
        blockers.append("MYSQL_MANIFEST_INVALID")
        mysql_entries = []
    for item in mysql_entries:
        if not isinstance(item, dict):
            blockers.append("MYSQL_ENTRY_INVALID")
            continue
        database = str(item.get("database", ""))
        file_ref = str(item.get("file", ""))
        try:
            dump = safe_package_path(package_dir, file_ref)
        except RestorePlanError:
            blockers.append(f"MYSQL_UNSAFE_PACKAGE_PATH:{database}")
            continue
        if not database or not dump.is_file():
            blockers.append(f"MYSQL_DUMP_MISSING:{database or 'UNKNOWN'}")
            continue
        private_match, private_status = database_private_metadata_matches(package_dir, manifest, database)
        if not private_match:
            gates.append(f"DATABASE_CREDENTIAL_RECONCILIATION:{database}")
        actions.append({
            "order": order,
            "type": "mysql_prepare_and_import",
            "database": database,
            "dump": file_ref,
            "prepare_method": "clpctl db:add",
            "import_method": "clpctl db:import",
            "private_recovery_row": private_status,
            "credentials_emitted": False,
            "writes": True,
        })
        order += 1

    sqlite_entries = manifest.get("contents", {}).get("sqlite", [])
    if not isinstance(sqlite_entries, list):
        blockers.append("SQLITE_MANIFEST_INVALID")
        sqlite_entries = []
    for item in sqlite_entries:
        if not isinstance(item, dict):
            blockers.append("SQLITE_ENTRY_INVALID")
            continue
        source_abs = str(item.get("source", ""))
        file_ref = str(item.get("file", ""))
        try:
            package_file = safe_package_path(package_dir, file_ref)
            sqlite_target = safe_absolute_site_path(source_abs)
        except RestorePlanError:
            blockers.append(f"SQLITE_UNSAFE_TARGET:{source_abs or 'UNKNOWN'}")
            continue
        if sqlite_target != site_root and not sqlite_target.startswith(site_root.rstrip("/") + "/"):
            blockers.append(f"SQLITE_TARGET_OUTSIDE_SITE_ROOT:{source_abs}")
            continue
        if not package_file.is_file():
            blockers.append(f"SQLITE_BACKUP_MISSING:{file_ref}")
            continue
        actions.append({
            "order": order,
            "type": "restore_sqlite",
            "source": file_ref,
            "target": sqlite_target,
            "writes": True,
        })
        order += 1

    metadata = manifest.get("contents", {}).get("metadata", {})
    copied = metadata.get("copied", []) if isinstance(metadata, dict) else []
    if isinstance(copied, list):
        if any(str(item).startswith("metadata/cron/") for item in copied):
            actions.append({"order": order, "type": "reconcile_cron", "source": "metadata/cron/", "writes": True, "gate": "REVIEW_BEFORE_ENABLE"})
            order += 1
        if any(str(item).startswith("metadata/pm2/") for item in copied):
            actions.append({"order": order, "type": "restore_pm2_runtime", "source": "metadata/pm2/", "writes": True, "gate": "REVIEW_BEFORE_START"})
            order += 1
        if any(str(item).startswith("metadata/vhost/") for item in copied):
            actions.append({"order": order, "type": "reconcile_vhost", "source": "metadata/vhost/", "writes": True, "gate": "NGINX_TEST_REQUIRED"})
            order += 1

    ssl_material = metadata.get("ssl_material", []) if isinstance(metadata, dict) else []
    if isinstance(ssl_material, list) and ssl_material:
        certs = [item for item in ssl_material if isinstance(item, dict) and item.get("kind") == "certificate"]
        keys = [item for item in ssl_material if isinstance(item, dict) and item.get("kind") == "private_key"]
        if certs and keys:
            actions.append({
                "order": order,
                "type": "install_ssl_certificate",
                "method": "clpctl site:install:certificate",
                "certificate": certs[0].get("file"),
                "private_key": keys[0].get("file"),
                "writes": True,
            })
            order += 1
        else:
            gates.append("SSL_MATERIAL_RECONCILIATION")
    else:
        gates.append("SSL_REISSUE_OR_RECONCILIATION")

    actions.extend([
        {"order": order, "type": "permissions_reconcile", "method": "clpctl system:permissions:reset_or_supported_equivalent", "writes": True},
        {"order": order + 1, "type": "post_restore_verify", "checks": ["files", "mysql", "sqlite", "runtime", "http_https"], "writes": False},
    ])

    private_meta_path = package_dir / "metadata" / "cloudpanel-private.json"
    private_summary = read_json_private_summary(private_meta_path)
    if mysql_entries and not private_summary["present"]:
        gates.append("DATABASE_CREDENTIAL_RECONCILIATION_REQUIRED")

    blockers = sorted(set(blockers))
    gates = sorted(set(gates))
    if blockers:
        status = "BLOCKED"
    elif gates:
        status = "READY_WITH_GATES"
    else:
        status = "READY"

    return {
        "schema": PLAN_SCHEMA,
        "mode": "DRY_RUN",
        "status": status,
        "writes_performed": False,
        "backup_id": manifest.get("backup_id", UNKNOWN),
        "domain": site.get("domain", UNKNOWN),
        "target_root": str(target_root),
        "target_site_root": site_root,
        "target_site_exists": target_exists,
        "owner_overwrite_gate_required": target_exists,
        "package_verification": fresh,
        "archive": archive,
        "private_recovery_metadata": private_summary,
        "blockers": blockers,
        "gates": gates,
        "warnings": sorted(set(warnings)),
        "actions": actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops restore planning")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="build a zero-write restore dry-run plan")
    plan.add_argument("--package", required=True, help="verified local backup package")
    plan.add_argument("--target-root", default="/", help="target filesystem root to inspect without modifying")
    args = parser.parse_args()

    try:
        result = build_plan(Path(args.package), Path(args.target_root))
    except RestorePlanError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 6
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 6 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
