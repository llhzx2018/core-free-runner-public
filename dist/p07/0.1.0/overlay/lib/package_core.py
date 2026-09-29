#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
from typing import Any

import inventory

PACKAGE_SCHEMA = "vf-server-ops.backup-package.v1"
VERIFY_SCHEMA = "vf-server-ops.backup-verification.v1"
PRIVATE_METADATA_SCHEMA = "vf-server-ops.cloudpanel-private-metadata.v1"
DB_RECOVERY_INPUT_SCHEMA = "vf-server-ops.database-recovery-input.v1"
DB_USER_KEYS = ("user_name", "username", "database_user_name", "databaseUserName", "user")
DB_PASSWORD_KEYS = ("password", "user_password", "database_user_password", "databaseUserPassword")
UNKNOWN = inventory.UNKNOWN
SQLITE_SUFFIXES = (".sqlite", ".sqlite3", ".db", ".sq3")
SQLITE_HEADER = b"SQLite format 3\x00"
PRUNE_DIRS = {".git", "node_modules", "vendor", "cache", "caches", "tmp", "logs", "backups"}
BACKUP_KINDS = {"manual", "automatic", "pre_migration", "pre_upgrade"}


def safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in (".", "-", "_") else "_" for ch in value)
    return cleaned[:120] or "item"


def rooted(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


def relative_display(root: Path, path: Path) -> str:
    return "/" + str(path.relative_to(root)) if root != Path("/") else str(path)


def ensure_within(root: Path, path: Path) -> None:
    root_resolved = root.resolve()
    path_resolved = path.resolve(strict=False)
    if path_resolved != root_resolved and root_resolved not in path_resolved.parents:
        raise RuntimeError(f"path escapes root: {path}")


def chmod_private(path: Path, directory: bool = False) -> None:
    os.chmod(path, 0o700 if directory else 0o600)


def write_json_private(path: Path, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def find_site(manifest: dict[str, Any], domain: str) -> dict[str, Any]:
    for site in manifest.get("sites", []):
        if site.get("domain") == domain or domain in site.get("domains", []):
            return site
    raise RuntimeError(f"site not found in inventory: {domain}")


def derive_site_root(root: Path, site: dict[str, Any]) -> str:
    user = str(site.get("site_user", UNKNOWN))
    domain = str(site.get("domain", UNKNOWN))
    if user != UNKNOWN and domain != UNKNOWN:
        candidate = f"/home/{user}/htdocs/{domain}"
        if rooted(root, candidate).is_dir():
            return candidate

    docroot = str(site.get("document_root", UNKNOWN))
    if docroot != UNKNOWN:
        parts = Path(docroot).parts
        if len(parts) >= 5 and parts[1] == "home" and parts[3] == "htdocs":
            candidate = "/" + "/".join(parts[1:5])
            if rooted(root, candidate).is_dir():
                return candidate
        if rooted(root, docroot).is_dir():
            return docroot
    raise RuntimeError("site root cannot be determined safely")


def discover_sqlite_paths(root: Path, site_root: str) -> list[str]:
    base = rooted(root, site_root)
    ensure_within(root, base)
    if not base.is_dir():
        raise RuntimeError(f"site root missing: {site_root}")
    found: list[str] = []
    base_depth = len(base.parts)
    for current, dirs, files in os.walk(base):
        current_path = Path(current)
        depth = len(current_path.parts) - base_depth
        dirs[:] = [d for d in dirs if d not in PRUNE_DIRS and depth < 7]
        for name in files:
            if not name.lower().endswith(SQLITE_SUFFIXES):
                continue
            candidate = current_path / name
            try:
                with candidate.open("rb") as handle:
                    header = handle.read(len(SQLITE_HEADER))
            except OSError:
                continue
            if header == SQLITE_HEADER:
                found.append(relative_display(root, candidate))
                if len(found) >= 100:
                    return sorted(found)
    return sorted(found)


def copy_private(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    chmod_private(dst.parent, directory=True)
    shutil.copy2(src, dst, follow_symlinks=False)
    if dst.is_file():
        chmod_private(dst)


def copy_private_follow(root: Path, src: Path, dst: Path) -> None:
    resolved = src.resolve(strict=True)
    ensure_within(root, resolved)
    dst.parent.mkdir(parents=True, exist_ok=True)
    chmod_private(dst.parent, directory=True)
    shutil.copy2(resolved, dst)
    chmod_private(dst)


def add_site_archive(root: Path, site_root: str, output: Path) -> None:
    source = rooted(root, site_root)
    ensure_within(root, source)
    if not source.is_dir():
        raise RuntimeError(f"site root missing: {site_root}")
    output.parent.mkdir(parents=True, exist_ok=True)
    chmod_private(output.parent, directory=True)
    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        archive.add(source, arcname="site", recursive=True)
    chmod_private(output)


def backup_sqlite(root: Path, sqlite_paths: list[str], out_dir: Path) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    chmod_private(out_dir, directory=True)
    results: list[dict[str, Any]] = []
    for index, absolute in enumerate(sqlite_paths, start=1):
        source = rooted(root, absolute)
        ensure_within(root, source)
        if not source.is_file():
            raise RuntimeError(f"SQLite source missing: {absolute}")
        target = out_dir / f"{index:02d}_{safe_name(source.name)}"
        src_conn = None
        dst_conn = None
        try:
            src_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=5)
            dst_conn = sqlite3.connect(target)
            src_conn.backup(dst_conn)
            row = dst_conn.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                raise RuntimeError(f"SQLite integrity check failed: {absolute}")
        except sqlite3.Error as exc:
            raise RuntimeError(f"SQLite backup failed for {absolute}: {exc.__class__.__name__}") from exc
        finally:
            if dst_conn is not None:
                dst_conn.close()
            if src_conn is not None:
                src_conn.close()
        chmod_private(target)
        results.append({"source": absolute, "file": f"sqlite/{target.name}", "method": "sqlite_backup_api"})
    return results


def export_mysql(databases: list[str], out_dir: Path, clpctl: str) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    chmod_private(out_dir, directory=True)
    results: list[dict[str, Any]] = []
    for database in databases:
        filename = f"{safe_name(database)}.sql.gz"
        target = out_dir / filename
        proc = subprocess.run(
            [clpctl, "db:export", f"--databaseName={database}", f"--file={target}"],
            text=True,
            capture_output=True,
            check=False,
            timeout=1800,
        )
        if proc.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError(f"CloudPanel database export failed: {database} (exit {proc.returncode})")
        chmod_private(target)
        try:
            with gzip.open(target, "rb") as handle:
                handle.read(64)
        except OSError as exc:
            raise RuntimeError(f"MySQL gzip validation failed: {database}") from exc
        results.append({"database": database, "file": f"mysql/{filename}", "method": "clpctl_db_export"})
    return results


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    try:
        return [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
    except sqlite3.Error:
        return []


def rows_as_dicts(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    cursor = conn.execute(sql, params)
    columns = [item[0] for item in cursor.description or []]
    return [{columns[i]: row[i] for i in range(len(columns))} for row in cursor.fetchall()]


def first_nonempty(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, (str, int)) and str(value):
            return str(value)
    return None


def load_database_recovery_input(path: Path | None, domain: str) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("database recovery input must be a regular non-symlink file")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise RuntimeError("database recovery input permissions must not allow group/world access")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("database recovery input is invalid") from exc
    if not isinstance(payload, dict) or payload.get("schema") != DB_RECOVERY_INPUT_SCHEMA:
        raise RuntimeError("database recovery input schema is invalid")
    if payload.get("domain") != domain:
        raise RuntimeError("database recovery input domain does not match backup site")
    rows = payload.get("databases")
    if not isinstance(rows, list):
        raise RuntimeError("database recovery input databases must be a list")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("database recovery input contains an invalid row")
        name = row.get("name")
        username = row.get("user_name")
        password = row.get("password")
        if not all(isinstance(value, str) and value for value in (name, username, password)):
            raise RuntimeError("database recovery input requires non-empty name/user_name/password")
        if name in result:
            raise RuntimeError(f"database recovery input contains duplicate database: {name}")
        result[name] = {"user_name": username, "password": password}
    return result


def merge_database_recovery(
    captured: dict[str, list[dict[str, Any]]],
    databases: list[str],
    recovery: dict[str, dict[str, str]],
) -> int:
    unexpected = sorted(set(recovery) - set(databases))
    if unexpected:
        raise RuntimeError(f"database recovery input contains database outside this site: {unexpected[0]}")
    rows = captured.get("database", [])
    by_name = {
        str(row.get("name")): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("name"), (str, int))
    }
    merged = 0
    for database in databases:
        row = by_name.get(database)
        if row is None:
            raise RuntimeError(f"CloudPanel database recovery row not found: {database}")
        supplied = recovery.get(database)
        if supplied is not None:
            row["user_name"] = supplied["user_name"]
            row["password"] = supplied["password"]
            merged += 1
        if not first_nonempty(row, DB_USER_KEYS) or not first_nonempty(row, DB_PASSWORD_KEYS):
            raise RuntimeError(
                f"portable database recovery credentials unavailable: {database}; provide --db-recovery-file"
            )
    return merged


def copy_cloudpanel_private_metadata(
    root: Path,
    site: dict[str, Any],
    out_dir: Path,
    databases: list[str] | None = None,
    database_recovery: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    databases = databases or []
    database_recovery = database_recovery or {}
    db_path = rooted(root, "/home/clp/htdocs/app/data/db.sq3")
    if not db_path.is_file():
        if databases:
            raise RuntimeError("CloudPanel private metadata is required for portable MySQL recovery")
        return {"included": False, "status": "PANEL_DB_NOT_FOUND", "file": None, "tables": {}}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        if databases:
            raise RuntimeError("CloudPanel private metadata cannot be read for portable MySQL recovery") from exc
        return {"included": False, "status": "PANEL_DB_READ_FAILED", "file": None, "tables": {}}

    domain = str(site.get("domain", ""))
    try:
        site_cols = table_columns(conn, "site")
        if not {"id", "domain_name"}.issubset(site_cols):
            if databases:
                raise RuntimeError("CloudPanel site schema is unsupported for portable MySQL recovery")
            return {"included": False, "status": "SITE_SCHEMA_UNSUPPORTED", "file": None, "tables": {}}
        site_rows = rows_as_dicts(conn, 'SELECT * FROM "site" WHERE domain_name=? LIMIT 1', (domain,))
        if not site_rows:
            if databases:
                raise RuntimeError("CloudPanel site row is required for portable MySQL recovery")
            return {"included": False, "status": "SITE_ROW_NOT_FOUND", "file": None, "tables": {}}
        site_id = site_rows[0]["id"]
        captured: dict[str, list[dict[str, Any]]] = {"site": site_rows}
        for table in ("php_settings", "database"):
            cols = table_columns(conn, table)
            if "site_id" in cols:
                captured[table] = rows_as_dicts(conn, f'SELECT * FROM "{table}" WHERE site_id=?', (site_id,))
            else:
                captured[table] = []
    except sqlite3.Error as exc:
        if databases:
            raise RuntimeError("CloudPanel private metadata query failed for portable MySQL recovery") from exc
        return {"included": False, "status": "PANEL_METADATA_QUERY_FAILED", "file": None, "tables": {}}
    finally:
        conn.close()

    merged_recovery = merge_database_recovery(captured, databases, database_recovery) if databases else 0
    target = out_dir / "cloudpanel-private.json"
    payload = {
        "schema": PRIVATE_METADATA_SCHEMA,
        "classification": "PRIVATE_SECRET_RECOVERY_METADATA",
        "domain": domain,
        "warning": "May contain credentials/secrets. Never log, publish, or commit this file.",
        "tables": captured,
    }
    write_json_private(target, payload)
    return {
        "included": True,
        "status": "CAPTURED_READ_ONLY_WITH_PRIVATE_RECOVERY_INPUT" if merged_recovery else "CAPTURED_READ_ONLY",
        "file": "metadata/cloudpanel-private.json",
        "tables": {name: len(rows) for name, rows in captured.items()},
        "database_recovery_input_count": merged_recovery,
        "may_contain_secrets": True,
    }


def nginx_directive_path(text: str, directive: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(directive)}\s+([^;]+);", text)
    if not match:
        return None
    value = match.group(1).strip().strip('"\'')
    return value if value.startswith("/") and "$" not in value else None


def copy_runtime_metadata(
    root: Path,
    site: dict[str, Any],
    out_dir: Path,
    databases: list[str] | None = None,
    database_recovery: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    chmod_private(out_dir, directory=True)
    copied: list[str] = []
    ssl_material: list[dict[str, str]] = []
    seen_ssl_sources: set[str] = set()

    site_json = out_dir / "inventory-site.json"
    write_json_private(site_json, site)
    copied.append("metadata/inventory-site.json")

    domain = str(site.get("domain", ""))
    nginx_dir = rooted(root, "/etc/nginx/sites-enabled")
    if nginx_dir.is_dir() and domain:
        vhost_out = out_dir / "vhost"
        ssl_out = out_dir / "ssl"
        for source in sorted(nginx_dir.glob("*.conf")):
            try:
                text = source.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if domain not in text:
                continue
            target = vhost_out / source.name
            copy_private(source, target)
            copied.append(f"metadata/vhost/{source.name}")

            for kind, directive in (("certificate", "ssl_certificate"), ("private_key", "ssl_certificate_key")):
                absolute = nginx_directive_path(text, directive)
                if not absolute or absolute in seen_ssl_sources:
                    continue
                ssl_source = rooted(root, absolute)
                if not ssl_source.exists():
                    continue
                try:
                    ssl_target = ssl_out / f"{safe_name(source.stem)}__{kind}__{safe_name(ssl_source.name)}"
                    copy_private_follow(root, ssl_source, ssl_target)
                except (OSError, RuntimeError):
                    continue
                seen_ssl_sources.add(absolute)
                package_file = f"metadata/ssl/{ssl_target.name}"
                copied.append(package_file)
                ssl_material.append({"kind": kind, "source": absolute, "file": package_file})

    cron_out = out_dir / "cron"
    for source_path in site.get("cron", {}).get("source_paths", []):
        if not isinstance(source_path, str):
            continue
        source = rooted(root, source_path)
        ensure_within(root, source)
        if source.is_file():
            target = cron_out / safe_name(source_path.strip("/").replace("/", "__"))
            copy_private(source, target)
            copied.append(f"metadata/cron/{target.name}")

    user = str(site.get("site_user", UNKNOWN))
    if user != UNKNOWN and site.get("pm2", {}).get("present") is True:
        source = rooted(root, f"/home/{user}/.pm2/dump.pm2")
        if source.is_file():
            target = out_dir / "pm2" / "dump.pm2"
            copy_private(source, target)
            copied.append("metadata/pm2/dump.pm2")

    private_panel = copy_cloudpanel_private_metadata(
        root,
        site,
        out_dir,
        databases=databases,
        database_recovery=database_recovery,
    )
    if private_panel.get("included"):
        copied.append("metadata/cloudpanel-private.json")

    return {
        "copied": sorted(copied),
        "ssl_material": ssl_material,
        "ssl_private_key_included": any(item["kind"] == "private_key" for item in ssl_material),
        "cloudpanel_private_metadata": private_panel,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(package_dir: Path) -> None:
    entries: list[str] = []
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file() or path.name in {"checksums.sha256", "verification.json"}:
            continue
        rel = path.relative_to(package_dir)
        entries.append(f"{sha256_file(path)}  {rel.as_posix()}")
    target = package_dir / "checksums.sha256"
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(entries) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def verify_package(package_dir: Path) -> dict[str, Any]:
    checksums = package_dir / "checksums.sha256"
    failures: list[str] = []
    checked = 0
    try:
        checksum_lines = checksums.read_text(encoding="utf-8").splitlines()
    except OSError:
        checksum_lines = []
        failures.append("checksums:missing")
    for line in checksum_lines:
        if not line.strip():
            continue
        try:
            digest, rel = line.split("  ", 1)
        except ValueError:
            failures.append("checksums:invalid-line")
            continue
        target = package_dir / rel
        checked += 1
        if not target.is_file() or sha256_file(target) != digest:
            failures.append(f"checksum:{rel}")

    archive = package_dir / "files" / "site.tar.gz"
    try:
        with tarfile.open(archive, "r:gz") as handle:
            if not handle.getmembers():
                failures.append("archive:empty")
    except (tarfile.TarError, OSError):
        failures.append("archive:invalid")

    for path in sorted((package_dir / "sqlite").glob("*")) if (package_dir / "sqlite").exists() else []:
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            row = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            if not row or row[0] != "ok":
                failures.append(f"sqlite:{path.name}")
        except sqlite3.Error:
            failures.append(f"sqlite:{path.name}")

    for path in sorted((package_dir / "mysql").glob("*.sql.gz")) if (package_dir / "mysql").exists() else []:
        try:
            with gzip.open(path, "rb") as handle:
                handle.read(64)
        except OSError:
            failures.append(f"mysql:{path.name}")

    return {
        "schema": VERIFY_SCHEMA,
        "status": "PASS" if not failures else "FAIL",
        "checksum_files_checked": checked,
        "failures": failures,
    }


def build_backup(
    root: Path,
    domain: str,
    output_dir: Path,
    clpctl: str,
    backup_kind: str = "manual",
    database_recovery_file: Path | None = None,
) -> Path:
    if backup_kind not in BACKUP_KINDS:
        raise RuntimeError(f"unsupported backup kind: {backup_kind}")
    root = root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    chmod_private(output_dir, directory=True)

    inventory_manifest = inventory.build_manifest(root)
    site = find_site(inventory_manifest, domain)
    mysql = site.get("mysql_databases")
    if not isinstance(mysql, list):
        raise RuntimeError("MySQL association is UNKNOWN; refusing incomplete backup")
    recovery = load_database_recovery_input(database_recovery_file, str(site.get("domain", domain)))

    site_root = derive_site_root(root, site)
    sqlite_paths = discover_sqlite_paths(root, site_root)
    now = os.environ.get("VFOPS_NOW") or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    stamp = now.replace("-", "").replace(":", "").replace("+00:00", "Z").replace("+0000", "Z")
    backup_id = f"{safe_name(site.get('domain', domain))}_{stamp}"
    final_dir = output_dir / backup_id
    if final_dir.exists():
        raise RuntimeError(f"backup already exists: {final_dir}")

    staging = Path(tempfile.mkdtemp(prefix=f".{backup_id}.tmp-", dir=output_dir))
    chmod_private(staging, directory=True)
    try:
        files_archive = staging / "files" / "site.tar.gz"
        add_site_archive(root, site_root, files_archive)
        mysql_results = export_mysql(mysql, staging / "mysql", clpctl) if mysql else []
        sqlite_results = backup_sqlite(root, sqlite_paths, staging / "sqlite") if sqlite_paths else []
        metadata = copy_runtime_metadata(
            root,
            site,
            staging / "metadata",
            databases=mysql,
            database_recovery=recovery,
        )

        manifest = {
            "schema": PACKAGE_SCHEMA,
            "backup_id": backup_id,
            "backup_kind": backup_kind,
            "created_at": now,
            "status": "CREATED",
            "source": {
                "server": inventory_manifest.get("source_server", {}),
                "cloudpanel_version": inventory_manifest.get("system", {}).get("cloudpanel_version", UNKNOWN),
            },
            "site": {
                "domain": site.get("domain", domain),
                "domains": site.get("domains", [domain]),
                "site_user": site.get("site_user", UNKNOWN),
                "site_root": site_root,
                "document_root": site.get("document_root", UNKNOWN),
                "runtime": site.get("runtime", {}),
            },
            "contents": {
                "files_archive": "files/site.tar.gz",
                "mysql": mysql_results,
                "sqlite": sqlite_results,
                "sqlite_discovery": "SITE_ROOT_SQLITE_HEADER_SCAN",
                "metadata": metadata,
            },
            "security": {
                "classification": "PRIVATE_SENSITIVE_BACKUP",
                "contains_sensitive_data": True,
                "contains_recovery_secrets": bool(metadata.get("ssl_private_key_included") or metadata.get("cloudpanel_private_metadata", {}).get("included")),
                "remote_storage_requires_encryption": True,
                "ssl_private_key_included": metadata.get("ssl_private_key_included", False),
                "cloudpanel_private_metadata_included": metadata.get("cloudpanel_private_metadata", {}).get("included", False),
            },
        }
        write_json_private(staging / "manifest.json", manifest)
        write_checksums(staging)
        verification = verify_package(staging)
        write_json_private(staging / "verification.json", verification)
        if verification["status"] != "PASS":
            raise RuntimeError("backup verification failed")
        os.replace(staging, final_dir)
        chmod_private(final_dir, directory=True)
        return final_dir
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops local portable site backup")
    parser.add_argument("--site", required=True, help="site domain from inventory")
    parser.add_argument("--root", default="/", help="root filesystem to inspect")
    parser.add_argument("--output-dir", default="/var/backups/vf-server-ops", help="local backup directory")
    parser.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"), help="CloudPanel clpctl executable")
    parser.add_argument("--kind", choices=sorted(BACKUP_KINDS), default="manual", help="backup lifecycle kind; manual is protected from automatic retention")
    parser.add_argument(
        "--db-recovery-file",
        help="PRIVATE 0600 JSON database recovery input; values are merged only into private backup metadata",
    )
    args = parser.parse_args()

    try:
        result = build_backup(
            Path(args.root),
            args.site,
            Path(args.output_dir),
            args.clpctl,
            args.kind,
            Path(args.db_recovery_file) if args.db_recovery_file else None,
        )
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 4
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
