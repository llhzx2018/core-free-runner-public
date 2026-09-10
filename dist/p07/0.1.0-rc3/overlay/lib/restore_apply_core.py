#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from typing import Any

import package as package_engine
import restore as restore_plan

RESULT_SCHEMA = "vf-server-ops.restore-sandbox-result.v1"
SANDBOX_MARKER = ".vfops-sandbox-root"
SANDBOX_MARKER_VALUE = "VF_SERVER_OPS_SANDBOX_V1"
DB_USER_KEYS = ("user_name", "username", "database_user_name", "databaseUserName", "user")
DB_PASSWORD_KEYS = ("password", "user_password", "database_user_password", "databaseUserPassword")


class SandboxRestoreError(RuntimeError):
    pass


def require_sandbox_root(target_root: Path) -> Path:
    target_root = target_root.resolve()
    if str(target_root) == "/" or not target_root.is_dir():
        raise SandboxRestoreError("sandbox target root must be an existing non-root directory")
    marker = target_root / SANDBOX_MARKER
    try:
        value = marker.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SandboxRestoreError("sandbox marker is missing") from exc
    if value != SANDBOX_MARKER_VALUE:
        raise SandboxRestoreError("sandbox marker is invalid")
    return target_root


def safe_target(target_root: Path, absolute: str) -> Path:
    candidate = (target_root / absolute.lstrip("/")).resolve(strict=False)
    if candidate != target_root and target_root not in candidate.parents:
        raise SandboxRestoreError(f"target path escapes sandbox: {absolute}")
    return candidate


def load_manifest(package_dir: Path) -> dict[str, Any]:
    try:
        payload = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SandboxRestoreError("backup manifest is invalid") from exc
    if payload.get("schema") != package_engine.PACKAGE_SCHEMA:
        raise SandboxRestoreError("unsupported backup package schema")
    return payload


def private_database_row(package_dir: Path, manifest: dict[str, Any], database: str) -> dict[str, Any]:
    info = manifest.get("contents", {}).get("metadata", {}).get("cloudpanel_private_metadata", {})
    relative = info.get("file") if isinstance(info, dict) else None
    if not isinstance(relative, str):
        raise SandboxRestoreError(f"database recovery metadata is missing: {database}")
    path = restore_plan.safe_package_path(package_dir, relative)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SandboxRestoreError("database recovery metadata is invalid") from exc
    rows = payload.get("tables", {}).get("database", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        raise SandboxRestoreError("database recovery metadata has invalid rows")
    for row in rows:
        if isinstance(row, dict) and str(row.get("name", "")) == database:
            return row
    raise SandboxRestoreError(f"database recovery row not found: {database}")


def first_nonempty(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, (str, int)) and str(value):
            return str(value)
    return None


def database_credentials(row: dict[str, Any], database: str) -> tuple[str, str]:
    username = first_nonempty(row, DB_USER_KEYS)
    password = first_nonempty(row, DB_PASSWORD_KEYS)
    if not username or not password:
        raise SandboxRestoreError(f"database credential mapping is not portable yet: {database}")
    return username, password


def run_clpctl(clpctl: str, args: list[str], timeout: int = 1800) -> None:
    try:
        proc = subprocess.run(
            [clpctl, *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxRestoreError(f"CloudPanel CLI execution failed: {args[0]}") from exc
    if proc.returncode != 0:
        raise SandboxRestoreError(f"CloudPanel CLI command failed: {args[0]} (exit {proc.returncode})")


def site_add_args(site: dict[str, Any]) -> list[str]:
    domain = str(site.get("domain", ""))
    user = str(site.get("site_user", ""))
    runtime = site.get("runtime", {}) if isinstance(site.get("runtime"), dict) else {}
    runtime_type = str(runtime.get("type", "")).lower().replace("-", "_")
    version = str(runtime.get("version", ""))
    app_port = runtime.get("app_port")
    if not domain or not user:
        raise SandboxRestoreError("site identity is incomplete")
    common = [f"--domainName={domain}", f"--siteUser={user}", f"--siteUserPassword={secrets.token_urlsafe(24)}"]

    if runtime_type == "php":
        if not version or version == "UNKNOWN":
            raise SandboxRestoreError("PHP version is unknown")
        return ["site:add:php", f"--phpVersion={version}", "--vhostTemplate=Generic", *common]
    if runtime_type in {"static", "static_html"}:
        return ["site:add:static", *common]
    if runtime_type in {"nodejs", "node_js"}:
        if not version or version == "UNKNOWN" or app_port in (None, "UNKNOWN"):
            raise SandboxRestoreError("Node.js runtime metadata is incomplete")
        return ["site:add:nodejs", f"--nodejsVersion={version}", f"--appPort={app_port}", *common]
    if runtime_type in {"reverse_proxy", "reverseproxy"}:
        if app_port in (None, "UNKNOWN"):
            raise SandboxRestoreError("reverse proxy port is unknown")
        return ["site:add:reverse-proxy", f"--reverseProxyUrl=http://127.0.0.1:{app_port}", *common]
    if runtime_type == "python":
        if not version or version == "UNKNOWN" or app_port in (None, "UNKNOWN"):
            raise SandboxRestoreError("Python runtime metadata is incomplete")
        return ["site:add:python", f"--pythonVersion={version}", f"--appPort={app_port}", *common]
    raise SandboxRestoreError(f"unsupported site runtime for sandbox restore: {runtime_type or 'UNKNOWN'}")


def safe_member_relative(member: tarfile.TarInfo) -> Path:
    pure = PurePosixPath(member.name)
    if not pure.parts or pure.parts[0] != "site":
        raise SandboxRestoreError(f"archive member has unexpected root: {member.name}")
    rel = PurePosixPath(*pure.parts[1:])
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise SandboxRestoreError(f"archive member is unsafe: {member.name}")
    return Path(*rel.parts)


def ensure_parent_not_symlink(root: Path, target: Path) -> None:
    current = root
    rel = target.relative_to(root)
    for part in rel.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise SandboxRestoreError(f"archive extraction crosses symlink: {target}")


def extract_site_archive(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    root_resolved = destination.resolve()
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                if member.name == "site":
                    continue
                rel = safe_member_relative(member)
                target = destination / rel
                resolved = target.resolve(strict=False)
                if resolved != root_resolved and root_resolved not in resolved.parents:
                    raise SandboxRestoreError(f"archive extraction escapes sandbox: {member.name}")
                ensure_parent_not_symlink(destination, target)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    os.chmod(target, member.mode & 0o777)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    ensure_parent_not_symlink(destination, target)
                    source = archive.extractfile(member)
                    if source is None:
                        raise SandboxRestoreError(f"archive file cannot be read: {member.name}")
                    with source, target.open("xb") as handle:
                        shutil.copyfileobj(source, handle)
                    os.chmod(target, member.mode & 0o777)
            for member in members:
                if not (member.issym() or member.islnk()):
                    continue
                rel = safe_member_relative(member)
                target = destination / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                ensure_parent_not_symlink(destination, target)
                if member.issym():
                    link = member.linkname
                    if not link or link.startswith("/"):
                        raise SandboxRestoreError(f"archive symlink escapes site: {member.name}")
                    normalized = os.path.normpath(str(PurePosixPath(rel.as_posix()).parent / link))
                    link_target = PurePosixPath(normalized)
                    if link_target.is_absolute() or any(part == ".." for part in link_target.parts):
                        raise SandboxRestoreError(f"archive symlink escapes site: {member.name}")
                    os.symlink(link, target)
                else:
                    link_pure = PurePosixPath(member.linkname)
                    if not link_pure.parts or link_pure.parts[0] != "site":
                        raise SandboxRestoreError(f"archive hardlink escapes site: {member.name}")
                    link_rel = Path(*link_pure.parts[1:])
                    source_target = destination / link_rel
                    if not source_target.is_file() or source_target.is_symlink():
                        raise SandboxRestoreError(f"archive hardlink target is invalid: {member.name}")
                    os.link(source_target, target)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def restore_sqlite(package_dir: Path, manifest: dict[str, Any], staged_site: Path, site_root: str) -> int:
    count = 0
    entries = manifest.get("contents", {}).get("sqlite", [])
    if not isinstance(entries, list):
        raise SandboxRestoreError("SQLite manifest is invalid")
    for item in entries:
        if not isinstance(item, dict):
            raise SandboxRestoreError("SQLite manifest entry is invalid")
        source_abs = restore_plan.safe_absolute_site_path(str(item.get("source", "")))
        if source_abs != site_root and not source_abs.startswith(site_root.rstrip("/") + "/"):
            raise SandboxRestoreError(f"SQLite target is outside site root: {source_abs}")
        package_file = restore_plan.safe_package_path(package_dir, str(item.get("file", "")))
        rel = PurePosixPath(source_abs).relative_to(PurePosixPath(site_root))
        target = staged_site / Path(*rel.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(package_file, target)
        os.chmod(target, 0o600)
        try:
            conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
            row = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
        except sqlite3.Error as exc:
            raise SandboxRestoreError(f"restored SQLite validation failed: {source_abs}") from exc
        if not row or row[0] != "ok":
            raise SandboxRestoreError(f"restored SQLite validation failed: {source_abs}")
        count += 1
    return count


def copy_pending_metadata(package_dir: Path, manifest: dict[str, Any], pending_dir: Path) -> list[str]:
    metadata = manifest.get("contents", {}).get("metadata", {})
    copied = metadata.get("copied", []) if isinstance(metadata, dict) else []
    selected: list[str] = []
    if not isinstance(copied, list):
        return selected
    for relative in copied:
        if not isinstance(relative, str):
            continue
        if not relative.startswith(("metadata/cron/", "metadata/pm2/", "metadata/vhost/")):
            continue
        source = restore_plan.safe_package_path(package_dir, relative)
        if not source.is_file():
            continue
        target = pending_dir / Path(*PurePosixPath(relative).parts[1:])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        os.chmod(target, 0o600)
        selected.append(relative)
    return sorted(selected)


def install_certificate(package_dir: Path, manifest: dict[str, Any], domain: str, clpctl: str) -> bool:
    metadata = manifest.get("contents", {}).get("metadata", {})
    ssl = metadata.get("ssl_material", []) if isinstance(metadata, dict) else []
    if not isinstance(ssl, list):
        return False
    cert = next((item for item in ssl if isinstance(item, dict) and item.get("kind") == "certificate"), None)
    key = next((item for item in ssl if isinstance(item, dict) and item.get("kind") == "private_key"), None)
    if not cert or not key:
        return False
    cert_path = restore_plan.safe_package_path(package_dir, str(cert.get("file", "")))
    key_path = restore_plan.safe_package_path(package_dir, str(key.get("file", "")))
    run_clpctl(clpctl, [
        "site:install:certificate",
        f"--domainName={domain}",
        f"--privateKey={key_path}",
        f"--certificate={cert_path}",
    ])
    return True


def apply_sandbox(package_dir: Path, target_root: Path, clpctl: str) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    target_root = require_sandbox_root(target_root)
    plan = restore_plan.build_plan(package_dir, target_root)
    if plan.get("status") == "BLOCKED":
        raise SandboxRestoreError("restore plan is blocked")
    if plan.get("owner_overwrite_gate_required"):
        raise SandboxRestoreError("sandbox restore refuses an existing target site")

    manifest = load_manifest(package_dir)
    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    domain = str(site.get("domain", ""))
    site_root = restore_plan.safe_absolute_site_path(str(site.get("site_root", "")))
    final_site = safe_target(target_root, site_root)
    final_site.parent.mkdir(parents=True, exist_ok=True)
    if final_site.exists():
        raise SandboxRestoreError("sandbox target site already exists")

    work_parent = target_root / ".vfops-restore"
    work_parent.mkdir(mode=0o700, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{manifest.get('backup_id', 'backup')}-", dir=work_parent))
    os.chmod(staging, 0o700)
    staged_site = staging / "site"
    pending_meta = staging / "pending-metadata"
    steps: list[str] = []
    site_created = False
    committed = False

    try:
        fresh = package_engine.verify_package(package_dir)
        if fresh.get("status") != "PASS":
            raise SandboxRestoreError("backup package failed fresh verification")
        archive_rel = str(manifest.get("contents", {}).get("files_archive", ""))
        archive = restore_plan.safe_package_path(package_dir, archive_rel)
        archive_check = restore_plan.inspect_archive(archive)
        if archive_check.get("blockers"):
            raise SandboxRestoreError("site archive failed safe extraction precheck")

        run_clpctl(clpctl, site_add_args(site))
        site_created = True
        steps.append("cloudpanel_site_created")

        extract_site_archive(archive, staged_site)
        steps.append("files_staged")

        sqlite_count = restore_sqlite(package_dir, manifest, staged_site, site_root)
        steps.append("sqlite_restored")

        mysql_entries = manifest.get("contents", {}).get("mysql", [])
        if not isinstance(mysql_entries, list):
            raise SandboxRestoreError("MySQL manifest is invalid")
        mysql_count = 0
        for item in mysql_entries:
            if not isinstance(item, dict):
                raise SandboxRestoreError("MySQL entry is invalid")
            database = str(item.get("database", ""))
            dump = restore_plan.safe_package_path(package_dir, str(item.get("file", "")))
            row = private_database_row(package_dir, manifest, database)
            username, password = database_credentials(row, database)
            run_clpctl(clpctl, [
                "db:add",
                f"--domainName={domain}",
                f"--databaseName={database}",
                f"--databaseUserName={username}",
                f"--databaseUserPassword={password}",
            ])
            run_clpctl(clpctl, ["db:import", f"--databaseName={database}", f"--file={dump}"])
            mysql_count += 1
        steps.append("mysql_restored")

        pending = copy_pending_metadata(package_dir, manifest, pending_meta)
        steps.append("runtime_metadata_staged")

        ssl_installed = install_certificate(package_dir, manifest, domain, clpctl)
        steps.append("ssl_reconciled" if ssl_installed else "ssl_deferred")

        if final_site.exists():
            raise SandboxRestoreError("sandbox target appeared during restore")
        os.replace(staged_site, final_site)
        committed = True
        steps.append("site_atomically_committed")

        evidence_root = target_root / "var/lib/vf-server-ops/restored-metadata" / str(manifest.get("backup_id", "backup"))
        if pending_meta.exists():
            evidence_root.parent.mkdir(parents=True, exist_ok=True)
            if evidence_root.exists():
                raise SandboxRestoreError("sandbox restore metadata evidence already exists")
            os.replace(pending_meta, evidence_root)
            os.chmod(evidence_root, 0o700)
        steps.append("metadata_evidence_committed")

        if not final_site.is_dir():
            raise SandboxRestoreError("restored site directory is missing after commit")

        return {
            "schema": RESULT_SCHEMA,
            "mode": "SANDBOX_APPLY",
            "status": "PASS",
            "backup_id": manifest.get("backup_id"),
            "domain": domain,
            "writes_performed": True,
            "production_write_allowed": False,
            "sandbox_marker_verified": True,
            "target_site_root": site_root,
            "mysql_database_count": mysql_count,
            "sqlite_database_count": sqlite_count,
            "ssl_installed": ssl_installed,
            "runtime_metadata_files_staged": len(pending),
            "cron_enabled": False,
            "pm2_started": False,
            "dns_changed": False,
            "steps": steps,
            "secrets_emitted": False,
        }
    except Exception as exc:
        if committed and final_site.exists():
            shutil.rmtree(final_site, ignore_errors=True)
        if site_created:
            try:
                run_clpctl(clpctl, ["site:delete", f"--domainName={domain}", "--force"], timeout=300)
            except SandboxRestoreError:
                pass
        if isinstance(exc, SandboxRestoreError):
            raise
        if isinstance(exc, restore_plan.RestorePlanError):
            raise SandboxRestoreError(str(exc)) from exc
        raise SandboxRestoreError("sandbox restore failed") from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops isolated sandbox restore")
    parser.add_argument("--package", required=True, help="verified local backup package")
    parser.add_argument("--target-root", required=True, help="isolated root containing .vfops-sandbox-root")
    parser.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"), help="CloudPanel clpctl executable")
    args = parser.parse_args()
    try:
        result = apply_sandbox(Path(args.package), Path(args.target_root), args.clpctl)
    except SandboxRestoreError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 7
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
