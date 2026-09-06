#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import tarfile
import tempfile
from typing import Any, BinaryIO

import package as package_engine
import restore as restore_plan

VERIFY_SCHEMA = "vf-server-ops.restore-verification.v1"
_REDUNDANT_CHARSET_COLLATE_RE = re.compile(
    r"\bCHARACTER\s+SET\s+([A-Za-z0-9_]+)\s+(COLLATE\s+([A-Za-z0-9_]+))\b",
    re.IGNORECASE,
)


class RestoreVerifyError(RuntimeError):
    pass


def stream_sha256(handle: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def archive_expected_files(archive_path: Path, sqlite_rel_paths: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    files: dict[str, str] = {}
    symlinks: dict[str, str] = {}
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                pure = PurePosixPath(member.name)
                if not pure.parts or pure.parts[0] != "site" or member.name == "site":
                    continue
                rel = PurePosixPath(*pure.parts[1:]).as_posix()
                if member.isfile():
                    if rel in sqlite_rel_paths:
                        continue
                    handle = archive.extractfile(member)
                    if handle is None:
                        raise RestoreVerifyError(f"archive member cannot be read: {rel}")
                    with handle:
                        files[rel] = stream_sha256(handle)
                elif member.issym():
                    symlinks[rel] = member.linkname
    except (OSError, tarfile.TarError) as exc:
        raise RestoreVerifyError("site archive cannot be verified") from exc
    return files, symlinks


def canonical_sql_line(line: str) -> str:
    normalized = re.sub(r"\s+", " ", line.strip())

    def strip_redundant_charset(match: re.Match[str]) -> str:
        charset = match.group(1)
        collate_clause = match.group(2)
        collation = match.group(3)
        charset_lower = charset.lower()
        collation_lower = collation.lower()
        if collation_lower == charset_lower or collation_lower.startswith(charset_lower + "_"):
            return collate_clause
        return match.group(0)

    return _REDUNDANT_CHARSET_COLLATE_RE.sub(strip_redundant_charset, normalized)


def sql_fingerprint(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    statements = 0
    opener = gzip.open if path.name.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("--") or line.startswith("#"):
                    continue
                normalized = canonical_sql_line(line)
                digest.update(normalized.encode("utf-8"))
                digest.update(b"\n")
                statements += 1
    except (OSError, EOFError) as exc:
        raise RestoreVerifyError(f"SQL dump cannot be fingerprinted: {path.name}") from exc
    if statements == 0:
        raise RestoreVerifyError(f"SQL dump has no comparable statements: {path.name}")
    return digest.hexdigest(), statements


def run_db_export(clpctl: str, database: str, output: Path) -> None:
    try:
        proc = subprocess.run(
            [clpctl, "db:export", f"--databaseName={database}", f"--file={output}"],
            text=True,
            capture_output=True,
            check=False,
            timeout=1800,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RestoreVerifyError(f"target database export failed: {database}") from exc
    if proc.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        raise RestoreVerifyError(f"target database export failed: {database} (exit {proc.returncode})")


def load_manifest(package_dir: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RestoreVerifyError("backup manifest is invalid") from exc
    if manifest.get("schema") != package_engine.PACKAGE_SCHEMA:
        raise RestoreVerifyError("unsupported backup package schema")
    return manifest


def sqlite_relative_paths(manifest: dict[str, Any], site_root: str) -> set[str]:
    result: set[str] = set()
    entries = manifest.get("contents", {}).get("sqlite", [])
    if not isinstance(entries, list):
        return result
    root = PurePosixPath(site_root)
    for item in entries:
        if not isinstance(item, dict):
            continue
        source = PurePosixPath(str(item.get("source", "")))
        try:
            rel = source.relative_to(root)
        except ValueError:
            continue
        result.add(rel.as_posix())
    return result


def verify_files(package_dir: Path, manifest: dict[str, Any], target_site: Path, site_root: str) -> dict[str, Any]:
    archive_ref = manifest.get("contents", {}).get("files_archive")
    if not isinstance(archive_ref, str):
        raise RestoreVerifyError("files archive reference is missing")
    archive = restore_plan.safe_package_path(package_dir, archive_ref)
    skip = sqlite_relative_paths(manifest, site_root)
    expected, expected_symlinks = archive_expected_files(archive, skip)
    missing: list[str] = []
    mismatched: list[str] = []
    symlink_mismatch: list[str] = []
    for rel, expected_hash in expected.items():
        path = target_site / Path(*PurePosixPath(rel).parts)
        if not path.is_file() or path.is_symlink():
            missing.append(rel)
            continue
        if package_engine.sha256_file(path) != expected_hash:
            mismatched.append(rel)
    for rel, link in expected_symlinks.items():
        path = target_site / Path(*PurePosixPath(rel).parts)
        if not path.is_symlink() or os.readlink(path) != link:
            symlink_mismatch.append(rel)
    failures = len(missing) + len(mismatched) + len(symlink_mismatch)
    return {
        "status": "PASS" if failures == 0 else "FAIL",
        "regular_files_checked": len(expected),
        "symlinks_checked": len(expected_symlinks),
        "missing": missing,
        "content_mismatch": mismatched,
        "symlink_mismatch": symlink_mismatch,
        "sqlite_archive_copies_excluded": len(skip),
    }


def verify_sqlite(package_dir: Path, manifest: dict[str, Any], target_site: Path, site_root: str) -> dict[str, Any]:
    entries = manifest.get("contents", {}).get("sqlite", [])
    if not isinstance(entries, list):
        return {"status": "FAIL", "checked": 0, "failures": ["SQLITE_MANIFEST_INVALID"]}
    failures: list[str] = []
    checked = 0
    root = PurePosixPath(site_root)
    for item in entries:
        if not isinstance(item, dict):
            failures.append("SQLITE_ENTRY_INVALID")
            continue
        source = str(item.get("source", ""))
        file_ref = str(item.get("file", ""))
        try:
            rel = PurePosixPath(source).relative_to(root)
            package_file = restore_plan.safe_package_path(package_dir, file_ref)
        except (ValueError, restore_plan.RestorePlanError):
            failures.append(f"SQLITE_PATH_INVALID:{source}")
            continue
        target = target_site / Path(*rel.parts)
        checked += 1
        if not target.is_file() or package_engine.sha256_file(target) != package_engine.sha256_file(package_file):
            failures.append(f"SQLITE_HASH_MISMATCH:{source}")
            continue
        try:
            conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
            row = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
        except sqlite3.Error:
            failures.append(f"SQLITE_INTEGRITY_FAIL:{source}")
            continue
        if not row or row[0] != "ok":
            failures.append(f"SQLITE_INTEGRITY_FAIL:{source}")
    return {"status": "PASS" if not failures else "FAIL", "checked": checked, "failures": failures}


def verify_mysql(package_dir: Path, manifest: dict[str, Any], clpctl: str) -> dict[str, Any]:
    entries = manifest.get("contents", {}).get("mysql", [])
    if not isinstance(entries, list):
        return {"status": "FAIL", "checked": 0, "failures": ["MYSQL_MANIFEST_INVALID"]}
    failures: list[str] = []
    checked = 0
    with tempfile.TemporaryDirectory(prefix="vfops-db-verify-") as tmp:
        temp = Path(tmp)
        for item in entries:
            if not isinstance(item, dict):
                failures.append("MYSQL_ENTRY_INVALID")
                continue
            database = str(item.get("database", ""))
            file_ref = str(item.get("file", ""))
            try:
                source = restore_plan.safe_package_path(package_dir, file_ref)
            except restore_plan.RestorePlanError:
                failures.append(f"MYSQL_DUMP_INVALID:{database or 'UNKNOWN'}")
                continue
            exported = temp / f"{checked:03d}_{re.sub(r'[^A-Za-z0-9._-]', '_', database)}.sql.gz"
            try:
                run_db_export(clpctl, database, exported)
                before, before_statements = sql_fingerprint(source)
                after, after_statements = sql_fingerprint(exported)
            except RestoreVerifyError:
                failures.append(f"MYSQL_EXPORT_OR_PARSE_FAIL:{database}")
                continue
            checked += 1
            if before != after or before_statements != after_statements:
                failures.append(f"MYSQL_FINGERPRINT_MISMATCH:{database}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "checked": checked,
        "failures": failures,
        "method": "CLPCTL_REEXPORT_CANONICAL_SQL_FINGERPRINT",
        "canonicalization": "REDUNDANT_MATCHING_CHARACTER_SET_BEFORE_COLLATE_ONLY",
    }


def verify_pending_metadata(target_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    backup_id = str(manifest.get("backup_id", ""))
    evidence = target_root / "var/lib/vf-server-ops/restored-metadata" / backup_id
    metadata = manifest.get("contents", {}).get("metadata", {})
    copied = metadata.get("copied", []) if isinstance(metadata, dict) else []
    expected = [item for item in copied if isinstance(item, str) and item.startswith(("metadata/cron/", "metadata/pm2/", "metadata/vhost/"))] if isinstance(copied, list) else []
    missing: list[str] = []
    for relative in expected:
        rel = PurePosixPath(relative)
        target = evidence / Path(*rel.parts[1:])
        if not target.is_file():
            missing.append(relative)
    return {
        "status": "PASS" if not missing else "FAIL",
        "expected": len(expected),
        "checked": len(expected) - len(missing),
        "missing": missing,
        "cron_enabled": False,
        "pm2_started": False,
    }


def verify_restore(package_dir: Path, target_root: Path, clpctl: str) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    target_root = target_root.resolve()
    if not target_root.is_dir():
        raise RestoreVerifyError("target root does not exist")
    fresh = package_engine.verify_package(package_dir)
    if fresh.get("status") != "PASS":
        raise RestoreVerifyError("backup package failed fresh verification")
    manifest = load_manifest(package_dir)
    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    site_root = restore_plan.safe_absolute_site_path(str(site.get("site_root", "")))
    target_site = restore_plan.target_path(target_root, site_root)
    if not target_site.is_dir():
        raise RestoreVerifyError("restored target site does not exist")

    files = verify_files(package_dir, manifest, target_site, site_root)
    sqlite_result = verify_sqlite(package_dir, manifest, target_site, site_root)
    mysql = verify_mysql(package_dir, manifest, clpctl)
    metadata = verify_pending_metadata(target_root, manifest)
    components = {"files": files, "sqlite": sqlite_result, "mysql": mysql, "runtime_metadata": metadata}
    failed = [name for name, value in components.items() if value.get("status") != "PASS"]
    return {
        "schema": VERIFY_SCHEMA,
        "status": "RESTORE_VERIFIED" if not failed else "FAIL",
        "backup_id": manifest.get("backup_id"),
        "domain": site.get("domain"),
        "scope": "FILES_MYSQL_SQLITE_PENDING_RUNTIME_METADATA",
        "package_fresh_verification": fresh.get("status"),
        "components": components,
        "failed_components": failed,
        "ssl_runtime_verification": "NOT_INCLUDED_IN_THIS_GATE",
        "http_https_verification": "NOT_INCLUDED_IN_THIS_GATE",
        "cutover_ready": False,
        "dns_changed": False,
        "secrets_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops verification engine")
    sub = parser.add_subparsers(dest="command", required=True)
    restore = sub.add_parser("restore", help="verify restored files, MySQL, SQLite and staged runtime metadata")
    restore.add_argument("--package", required=True)
    restore.add_argument("--target-root", required=True)
    restore.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"))
    args = parser.parse_args()
    try:
        result = verify_restore(Path(args.package), Path(args.target_root), args.clpctl)
    except (RestoreVerifyError, restore_plan.RestorePlanError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 8
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "RESTORE_VERIFIED" else 8


if __name__ == "__main__":
    raise SystemExit(main())
