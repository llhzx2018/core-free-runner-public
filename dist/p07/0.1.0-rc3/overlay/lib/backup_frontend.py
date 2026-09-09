#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Callable
from urllib.parse import unquote, urlparse

import inventory
import package_core as package_engine

RECOVERY_SCHEMA = "vf-server-ops.database-recovery-input.v1"
MAX_CONFIG_FILES = 120
MAX_CONFIG_BYTES = 256 * 1024
MAX_SCAN_DEPTH = 4
PRUNE_DIRS = {".git", "node_modules", "vendor", "cache", "caches", "logs", "backups", "tmp"}
KNOWN_NAMES = {
    "wp-config.php", ".env", ".env.local", ".env.production", ".env.prod",
    "config.production.json", "config.development.json", "config.json",
}
DB_NAME_KEYS = ("DB_DATABASE", "DB_NAME", "MYSQL_DATABASE", "DATABASE_NAME")
DB_USER_KEYS = ("DB_USERNAME", "DB_USER", "MYSQL_USER", "DATABASE_USER")
DB_PASS_KEYS = ("DB_PASSWORD", "DB_PASS", "MYSQL_PASSWORD", "DATABASE_PASSWORD")
URL_KEYS = ("DATABASE_URL", "MYSQL_URL", "MARIADB_URL")


class DiscoveryError(RuntimeError):
    pass


def _site_from_inventory(root: Path, domain: str) -> tuple[Path, list[str]]:
    payload = inventory.build_manifest(root)
    site = None
    for row in payload.get("sites", []):
        if isinstance(row, dict) and (row.get("domain") == domain or domain in row.get("domains", [])):
            site = row
            break
    if site is None:
        raise DiscoveryError("site inventory unavailable")
    databases = site.get("mysql_databases")
    if not isinstance(databases, list) or not all(isinstance(x, str) and x for x in databases):
        raise DiscoveryError("database association unavailable")
    user = str(site.get("site_user", "UNKNOWN"))
    site_domain = str(site.get("domain", domain))
    candidate = root / f"home/{user}/htdocs/{site_domain}"
    if user != "UNKNOWN" and candidate.is_dir():
        return candidate, sorted(set(databases))
    docroot = site.get("document_root")
    if isinstance(docroot, str) and docroot.startswith("/"):
        doc = root / docroot.lstrip("/")
        if doc.is_dir():
            return doc, sorted(set(databases))
    raise DiscoveryError("site root unavailable")


def _iter_known_files(site_root: Path):
    base_depth = len(site_root.parts)
    seen = 0
    for current, dirs, files in os.walk(site_root):
        current_path = Path(current)
        depth = len(current_path.parts) - base_depth
        dirs[:] = [d for d in dirs if d not in PRUNE_DIRS and depth < MAX_SCAN_DEPTH]
        for name in sorted(files):
            if name not in KNOWN_NAMES:
                continue
            path = current_path / name
            try:
                st = path.stat()
            except OSError:
                continue
            if not path.is_file() or path.is_symlink() or st.st_size > MAX_CONFIG_BYTES:
                continue
            seen += 1
            if seen > MAX_CONFIG_FILES:
                raise DiscoveryError("too many candidate configuration files")
            yield path


def _unquote_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _env_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = value.strip()
        if "$(" in value or "`" in value:
            continue
        values[key] = _unquote_scalar(value)
    return values


def _first(values: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = values.get(key)
        if value:
            return value
    return None


def _url_candidate(raw: str) -> tuple[str, str, str] | None:
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"mysql", "mariadb", "mysql2"}:
        return None
    database = parsed.path.lstrip("/").split("/", 1)[0]
    if not database or parsed.username is None or parsed.password is None:
        return None
    return unquote(database), unquote(parsed.username), unquote(parsed.password)


def _wordpress_candidate(text: str) -> tuple[str, str, str] | None:
    def get(name: str) -> str | None:
        pattern = re.compile(
            r"define\s*\(\s*(['\"])" + re.escape(name) + r"\1\s*,\s*(['\"])(.*?)\2\s*\)",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text)
        return match.group(3) if match else None
    values = (get("DB_NAME"), get("DB_USER"), get("DB_PASSWORD"))
    return values if all(values) else None


def _env_candidates(text: str) -> list[tuple[str, str, str]]:
    values = _env_values(text)
    result: list[tuple[str, str, str]] = []
    direct = (_first(values, DB_NAME_KEYS), _first(values, DB_USER_KEYS), _first(values, DB_PASS_KEYS))
    if all(direct):
        result.append((str(direct[0]), str(direct[1]), str(direct[2])))
    for key in URL_KEYS:
        raw = values.get(key)
        if raw:
            candidate = _url_candidate(raw)
            if candidate:
                result.append(candidate)
    return result


def _ghost_candidates(text: str) -> list[tuple[str, str, str]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    db = payload.get("database")
    connection = db.get("connection") if isinstance(db, dict) else None
    if not isinstance(connection, dict):
        return []
    database = connection.get("database")
    user = connection.get("user") or connection.get("username")
    password = connection.get("password")
    if all(isinstance(x, str) and x for x in (database, user, password)):
        return [(database, user, password)]
    return []


def _panel_schema_needs_recovery(root: Path, databases: list[str]) -> bool:
    if not databases:
        return False
    db_path = root / "home/clp/htdocs/app/data/db.sq3"
    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        columns = {str(row[1]) for row in conn.execute('PRAGMA table_info("database")')}
        conn.close()
    except Exception:
        return False
    user_keys = set(getattr(package_engine, "DB_USER_KEYS", ()))
    password_keys = set(getattr(package_engine, "DB_PASSWORD_KEYS", ()))
    return not (columns & user_keys and columns & password_keys)


def discover_credentials(site_root: Path, databases: list[str]) -> dict[str, dict[str, str]]:
    expected = set(databases)
    if not expected:
        return {}
    found: dict[str, set[tuple[str, str]]] = {db: set() for db in databases}
    for path in _iter_known_files(site_root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidates: list[tuple[str, str, str]] = []
        if path.name == "wp-config.php":
            candidate = _wordpress_candidate(text)
            if candidate:
                candidates.append(candidate)
        if path.name.startswith(".env"):
            candidates.extend(_env_candidates(text))
        if path.name.endswith(".json"):
            candidates.extend(_ghost_candidates(text))
        for database, user, password in candidates:
            if database in expected and user and password:
                found[database].add((user, password))
    result: dict[str, dict[str, str]] = {}
    for database in databases:
        candidates = found.get(database, set())
        if len(candidates) != 1:
            raise DiscoveryError("database credential discovery incomplete or ambiguous")
        user, password = next(iter(candidates))
        result[database] = {"user_name": user, "password": password}
    return result


def _write_recovery(domain: str, credentials: dict[str, dict[str, str]]) -> Path:
    tmpdir = Path(os.environ.get("VFOPS_RECOVERY_TMPDIR", "/run"))
    if not tmpdir.is_dir() or not os.access(tmpdir, os.W_OK):
        tmpdir = Path(tempfile.gettempdir())
    fd, name = tempfile.mkstemp(prefix=".vfops-db-recovery-", dir=tmpdir)
    path = Path(name)
    try:
        os.fchmod(fd, 0o600)
        payload = {
            "schema": RECOVERY_SCHEMA,
            "domain": domain,
            "databases": [
                {"name": db, "user_name": row["user_name"], "password": row["password"]}
                for db, row in sorted(credentials.items())
            ],
        }
        data = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    return path


def build_backup_with_discovery(
    root: Path,
    domain: str,
    output_dir: Path,
    clpctl: str,
    backup_kind: str = "manual",
    database_recovery_file: Path | None = None,
) -> Path:
    root = root.resolve()
    if database_recovery_file is not None:
        return package_engine.build_backup(root, domain, output_dir, clpctl, backup_kind, database_recovery_file)

    recovery_path: Path | None = None
    try:
        site_root, databases = _site_from_inventory(root, domain)
        if _panel_schema_needs_recovery(root, databases):
            credentials = discover_credentials(site_root, databases)
            recovery_path = _write_recovery(domain, credentials)
            return package_engine.build_backup(root, domain, output_dir, clpctl, backup_kind, recovery_path)
    except DiscoveryError:
        if recovery_path is not None:
            recovery_path.unlink(missing_ok=True)
            recovery_path = None
        pass
    finally:
        if recovery_path is not None:
            try:
                recovery_path.unlink(missing_ok=True)
            except OSError:
                pass

    try:
        return package_engine.build_backup(root, domain, output_dir, clpctl, backup_kind)
    except RuntimeError as exc:
        if "portable database recovery credentials unavailable" not in str(exc).lower():
            raise
        try:
            site_root, databases = _site_from_inventory(root, domain)
            credentials = discover_credentials(site_root, databases)
        except DiscoveryError as discovery_exc:
            raise RuntimeError("application database recovery credentials could not be discovered safely") from discovery_exc
        recovery_path = _write_recovery(domain, credentials)
        try:
            return package_engine.build_backup(root, domain, output_dir, clpctl, backup_kind, recovery_path)
        finally:
            try:
                recovery_path.unlink(missing_ok=True)
            except OSError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops local portable site backup frontend")
    parser.add_argument("--site", required=True)
    parser.add_argument("--root", default="/")
    parser.add_argument("--output-dir", default="/var/backups/vf-server-ops")
    parser.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"))
    parser.add_argument("--kind", choices=sorted(package_engine.BACKUP_KINDS), default="manual")
    parser.add_argument("--db-recovery-file")
    args = parser.parse_args()
    try:
        result = build_backup_with_discovery(
            Path(args.root), args.site, Path(args.output_dir), args.clpctl, args.kind,
            Path(args.db_recovery_file) if args.db_recovery_file else None,
        )
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
