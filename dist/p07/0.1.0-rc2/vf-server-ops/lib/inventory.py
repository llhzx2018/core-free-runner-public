#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from shutil import which
from typing import Any

UNKNOWN = "UNKNOWN"
SCHEMA = "vf-server-ops.inventory.v1"
PRUNE_DIRS = {"node_modules", "vendor", ".git", "cache", "caches", "tmp", "logs", "backups"}
SQLITE_SUFFIXES = (".sqlite", ".sqlite3", ".db", ".sq3")
SQLITE_HEADER = b"SQLite format 3\x00"


def rooted(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None


def relative_display(root: Path, path: Path) -> str:
    return "/" + str(path.relative_to(root)) if root != Path("/") else str(path)


def parse_os_release(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    text = read_text(rooted(root, "/etc/os-release"))
    if text:
        for line in text.splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    return {
        "id": values.get("ID", UNKNOWN),
        "version_id": values.get("VERSION_ID", UNKNOWN),
        "pretty_name": values.get("PRETTY_NAME", UNKNOWN),
    }


def hostname_identity(root: Path) -> dict[str, str]:
    raw = (read_text(rooted(root, "/etc/hostname")) or "").strip()
    if not raw:
        return {"hostname_hash": UNKNOWN}
    return {"hostname_hash": "sha256:" + hashlib.sha256(raw.encode()).hexdigest()[:16]}


def disk_info(root: Path) -> dict[str, Any]:
    try:
        st = os.statvfs(root)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        return {"total_bytes": total, "used_bytes": total - free, "free_bytes": free}
    except OSError:
        return {"total_bytes": UNKNOWN, "used_bytes": UNKNOWN, "free_bytes": UNKNOWN}


def cloudpanel_version(root: Path) -> str:
    override = os.environ.get("VFOPS_CLOUDPANEL_VERSION")
    if override:
        return override.strip() or UNKNOWN
    for name in ("/home/clp/htdocs/app/VERSION", "/home/clp/htdocs/app/version"):
        text = read_text(rooted(root, name))
        if text and text.strip():
            return text.strip().splitlines()[0][:80]
    if root == Path("/") and which("clpctl"):
        for command in (["clpctl", "--version"], ["clpctl", "-V"]):
            try:
                proc = subprocess.run(command, text=True, capture_output=True, timeout=3, check=False)
            except (OSError, subprocess.TimeoutExpired):
                continue
            text = (proc.stdout or proc.stderr).strip()
            if proc.returncode == 0 and text:
                return text.splitlines()[0][:80]
    return UNKNOWN


def db_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
    except sqlite3.Error:
        return set()


def query_one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> Any:
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row and row[0] not in (None, "") else UNKNOWN
    except sqlite3.Error:
        return UNKNOWN


def query_many(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[str] | str:
    try:
        return [str(row[0]) for row in conn.execute(sql, params).fetchall() if row and row[0] not in (None, "")]
    except sqlite3.Error:
        return UNKNOWN


def parse_vhosts(root: Path) -> dict[str, dict[str, Any]]:
    by_domain: dict[str, dict[str, Any]] = {}
    directory = rooted(root, "/etc/nginx/sites-enabled")
    if not directory.is_dir():
        return by_domain

    for path in sorted(directory.glob("*.conf")):
        text = read_text(path)
        if not text:
            continue
        names: list[str] = []
        for match in re.finditer(r"(?m)^\s*server_name\s+([^;]+);", text):
            names.extend(n for n in re.split(r"\s+", match.group(1).strip()) if n and n != "_")
        primary = next((n for n in names if not n.startswith("*.")), path.stem)
        root_match = re.search(r"(?m)^\s*root\s+([^;]+);", text)
        proxy = re.search(r"proxy_pass\s+https?://(?:127\.0\.0\.1|localhost):([0-9]+)", text)
        php = re.search(r"php(?:[-/]?)([0-9]+\.[0-9]+)", text, re.I)
        cert = re.search(r"(?m)^\s*ssl_certificate\s+([^;]+);", text)
        record = {
            "primary_domain": primary,
            "domains": sorted(set(names)) if names else [primary],
            "document_root": root_match.group(1).strip().strip('"\'') if root_match else UNKNOWN,
            "proxy_port": int(proxy.group(1)) if proxy else UNKNOWN,
            "php_version_hint": php.group(1) if php else UNKNOWN,
            "ssl": {
                "configured": bool(cert),
                "certificate_path": cert.group(1).strip().strip('"\'') if cert else UNKNOWN,
                "days_remaining": UNKNOWN,
            },
            "vhost_source": relative_display(root, path),
        }
        for name in record["domains"]:
            by_domain.setdefault(name, record)
        by_domain.setdefault(primary, record)
    return by_domain


def infer_document_root(root: Path, user: str, domain: str, vhost: dict[str, Any] | None) -> str:
    if vhost and vhost.get("document_root") not in (None, UNKNOWN):
        return str(vhost["document_root"])
    candidate = f"/home/{user}/htdocs/{domain}"
    return candidate if rooted(root, candidate).exists() else UNKNOWN


def infer_site_root(document_root: str, user: str, domain: str) -> str:
    if document_root != UNKNOWN:
        parts = Path(document_root).parts
        if len(parts) >= 5 and parts[1] == "home" and parts[3] == "htdocs":
            return "/" + "/".join(parts[1:5])
        return document_root
    if user != UNKNOWN and domain != UNKNOWN:
        return f"/home/{user}/htdocs/{domain}"
    return UNKNOWN


def scan_sqlite_paths(root: Path, site_root: str) -> list[str] | str:
    if site_root == UNKNOWN:
        return UNKNOWN
    base = rooted(root, site_root)
    if not base.is_dir():
        return []
    found: list[str] = []
    base_depth = len(base.parts)
    try:
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
                        if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                            continue
                except OSError:
                    continue
                found.append(relative_display(root, candidate))
                if len(found) >= 100:
                    return sorted(found)
    except OSError:
        return UNKNOWN
    return sorted(found)


def cron_summary(root: Path, user: str) -> dict[str, Any]:
    sources: list[str] = []
    count = 0
    for path in (rooted(root, f"/var/spool/cron/crontabs/{user}"), rooted(root, f"/var/spool/cron/{user}")):
        text = read_text(path)
        if text is None:
            continue
        sources.append(relative_display(root, path))
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", stripped):
                count += 1
    cron_d = rooted(root, "/etc/cron.d")
    if cron_d.is_dir():
        for path in sorted(cron_d.iterdir()):
            if not path.is_file():
                continue
            text = read_text(path)
            if not text:
                continue
            matched = sum(1 for line in text.splitlines() if re.search(rf"\b{re.escape(user)}\b", line) and not line.lstrip().startswith("#"))
            if matched:
                sources.append(relative_display(root, path))
                count += matched
    return {"entry_count": count, "source_paths": sorted(set(sources)), "command_body_emitted": False}


def pm2_summary(root: Path, user: str) -> dict[str, Any]:
    path = rooted(root, f"/home/{user}/.pm2/dump.pm2")
    if not path.is_file():
        return {"present": False, "processes": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"present": True, "processes": UNKNOWN}
    if not isinstance(data, list):
        return {"present": True, "processes": UNKNOWN}
    processes = []
    for item in data[:100]:
        if isinstance(item, dict):
            processes.append({
                "name": item.get("name", UNKNOWN),
                "script": item.get("pm_exec_path", item.get("script", UNKNOWN)),
                "cwd": item.get("pm_cwd", UNKNOWN),
            })
    return {"present": True, "processes": processes, "environment_emitted": False}


def empty_ssl() -> dict[str, Any]:
    return {"configured": UNKNOWN, "certificate_path": UNKNOWN, "days_remaining": UNKNOWN}


def site_record(root: Path, domain: str, user: str, site_type: str, vhost: dict[str, Any] | None,
                runtime_version: Any, databases: list[str] | str) -> dict[str, Any]:
    docroot = infer_document_root(root, user, domain, vhost)
    site_root = infer_site_root(docroot, user, domain)
    if runtime_version == UNKNOWN and vhost:
        runtime_version = vhost.get("php_version_hint", UNKNOWN)
    return {
        "domain": domain,
        "domains": vhost.get("domains", [domain]) if vhost else [domain],
        "site_user": user,
        "site_root": site_root,
        "document_root": docroot,
        "runtime": {
            "type": site_type or UNKNOWN,
            "version": runtime_version,
            "app_port": vhost.get("proxy_port", UNKNOWN) if vhost else UNKNOWN,
        },
        "mysql_databases": databases,
        "sqlite_paths": scan_sqlite_paths(root, site_root),
        "cron": cron_summary(root, user),
        "pm2": pm2_summary(root, user),
        "ssl": vhost.get("ssl", empty_ssl()) if vhost else empty_ssl(),
        "backup_decision": {"include": True, "reason": "DEFAULT_INCLUDE_UNTIL_POLICY_EXCLUDES"},
    }


def discover_sites_from_db(root: Path, vhosts: dict[str, dict[str, Any]], warnings: list[str]) -> list[dict[str, Any]]:
    path = rooted(root, "/home/clp/htdocs/app/data/db.sq3")
    if not path.is_file():
        warnings.append("CloudPanel database not found; using vhost fallback where possible")
        return []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        warnings.append("CloudPanel database could not be opened read-only")
        return []
    try:
        if not {"id", "domain_name", "user", "type"}.issubset(db_columns(conn, "site")):
            warnings.append("CloudPanel site schema is unsupported; using vhost fallback")
            return []
        php_cols = db_columns(conn, "php_settings")
        database_cols = db_columns(conn, "database")
        sites = []
        for site_id, domain, user, site_type in conn.execute('SELECT id, domain_name, user, type FROM "site" ORDER BY domain_name'):
            domain, user, site_type = str(domain), str(user), str(site_type or UNKNOWN)
            php_version: Any = UNKNOWN
            if {"site_id", "php_version"}.issubset(php_cols):
                php_version = query_one(conn, 'SELECT php_version FROM "php_settings" WHERE site_id=? LIMIT 1', (site_id,))
            databases: list[str] | str = UNKNOWN
            if {"site_id", "name"}.issubset(database_cols):
                databases = query_many(conn, 'SELECT name FROM "database" WHERE site_id=? ORDER BY name', (site_id,))
            runtime_version = php_version if site_type.lower() == "php" else UNKNOWN
            sites.append(site_record(root, domain, user, site_type, vhosts.get(domain), runtime_version, databases))
        return sites
    except sqlite3.Error:
        warnings.append("CloudPanel database query failed; using vhost fallback")
        return []
    finally:
        conn.close()


def fallback_sites(root: Path, vhosts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    sites: list[dict[str, Any]] = []
    seen: set[str] = set()
    for vhost in vhosts.values():
        domain = str(vhost["primary_domain"])
        if domain in seen:
            continue
        seen.add(domain)
        docroot = str(vhost.get("document_root", UNKNOWN))
        user_match = re.match(r"^/home/([^/]+)/", docroot)
        user = user_match.group(1) if user_match else UNKNOWN
        site_type = "node_or_reverse_proxy" if vhost.get("proxy_port") != UNKNOWN else ("php" if vhost.get("php_version_hint") != UNKNOWN else "static_or_unknown")
        sites.append(site_record(root, domain, user, site_type, vhost, vhost.get("php_version_hint", UNKNOWN), UNKNOWN))
    return sorted(sites, key=lambda item: item["domain"])


def build_summary(sites: list[dict[str, Any]]) -> dict[str, int]:
    mysql_known = [s["mysql_databases"] for s in sites if isinstance(s.get("mysql_databases"), list)]
    sqlite_known = [s["sqlite_paths"] for s in sites if isinstance(s.get("sqlite_paths"), list)]
    pm2_known = [s.get("pm2", {}).get("processes") for s in sites if isinstance(s.get("pm2", {}).get("processes"), list)]
    return {
        "site_count": len(sites),
        "mysql_database_count_known": sum(len(v) for v in mysql_known),
        "sites_with_mysql_unknown": sum(1 for s in sites if s.get("mysql_databases") == UNKNOWN),
        "sqlite_file_count_known": sum(len(v) for v in sqlite_known),
        "sites_with_sqlite_unknown": sum(1 for s in sites if s.get("sqlite_paths") == UNKNOWN),
        "pm2_process_count_known": sum(len(v) for v in pm2_known),
        "sites_with_pm2_unknown": sum(1 for s in sites if s.get("pm2", {}).get("processes") == UNKNOWN),
    }


def build_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    warnings: list[str] = []
    vhosts = parse_vhosts(root)
    sites = discover_sites_from_db(root, vhosts, warnings)
    source = "cloudpanel_db+vhost" if sites else "vhost_fallback"
    if not sites:
        sites = fallback_sites(root, vhosts)
    now = os.environ.get("VFOPS_NOW") or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema": SCHEMA,
        "generated_at": now,
        "mode": "READ_ONLY_DISCOVERY",
        "source_server": hostname_identity(root),
        "system": {
            "os": parse_os_release(root),
            "disk": disk_info(root),
            "cloudpanel_version": cloudpanel_version(root),
        },
        "discovery_source": source,
        "sites": sites,
        "summary": build_summary(sites),
        "warnings": warnings,
        "security": {
            "credential_fields_queried": False,
            "secret_values_emitted": False,
            "raw_hostname_emitted": False,
            "local_sensitive_sources_may_be_parsed": ["cron", "pm2_dump"],
            "output_policy": "WHITELIST_ONLY",
        },
    }


def write_private_output(path: Path, encoded: str) -> None:
    parent = path.parent if str(path.parent) else Path(".")
    if not parent.exists() or not parent.is_dir():
        raise RuntimeError(f"output directory does not exist: {parent}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(f"refusing to overwrite existing inventory manifest: {path}") from exc
    except OSError as exc:
        raise RuntimeError(f"cannot create inventory manifest: {path}: {exc}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops read-only inventory")
    parser.add_argument("--root", default="/", help="root filesystem to inspect; defaults to /")
    parser.add_argument("--output", help="write PRIVATE JSON manifest to a new file (0600; refuses overwrite)")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    args = parser.parse_args()
    manifest = build_manifest(Path(args.root))
    encoded = json.dumps(manifest, ensure_ascii=False, indent=None if args.compact else 2, sort_keys=True) + "\n"
    if args.output:
        try:
            output = Path(args.output)
            write_private_output(output, encoded)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=os.sys.stderr)
            return 4
        print(f"Inventory manifest written: {output}")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
