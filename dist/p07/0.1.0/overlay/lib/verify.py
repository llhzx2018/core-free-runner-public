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

_GUARDED_SESSION_SET_RE = re.compile(
    r"^/\*(?P<flavor>!|M!)(?P<version>[0-9]{5,6})[ \t]+"
    r"(?P<statement>SET[ \t]+.+?)[ \t]*\*/;?$",
    re.IGNORECASE,
)


def sql_guarded_session_fingerprint(path: Path) -> tuple[str, int]:
    """Strict raw SQL parity except equivalent, *known* session guard versions.

    SQL DDL (including conditional triggers, views, routines, and custom
    delimiters) and all row literals remain byte-for-byte represented.
    Unrecognized guards, high-version guards, and differing SET values keep
    their literal representation and therefore cannot falsely pass.
    """
    digest = hashlib.sha256()
    statements = 0
    opener = gzip.open if path.name.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="strict") as handle:
            for raw in handle:
                line = raw.rstrip("\r\n")
                if not line.strip() or line.lstrip().startswith(("--", "#")):
                    continue
                match = _GUARDED_SESSION_SET_RE.fullmatch(line.strip())
                if match:
                    version = int(match.group("version"))
                    flavor = match.group("flavor").upper()
                    known_mysql = flavor == "!" and 40000 <= version <= 50699
                    known_maria = flavor == "M!" and 100000 <= version <= 110899
                    if known_mysql or known_maria:
                        # Only the execution-version wrapper is canonicalized.
                        # The entire SET statement, including quoted values,
                        # remains unchanged and participates in the hash.
                        line = "GUARDED_SESSION_SET " + match.group("statement")
                digest.update(line.encode("utf-8"))
                digest.update(b"\n")
                statements += 1
    except (OSError, EOFError, UnicodeError) as exc:
        raise RestoreVerifyError("SQL guarded-session dump cannot be fingerprinted") from exc
    if statements == 0:
        raise RestoreVerifyError("SQL guarded-session dump has no statements")
    return digest.hexdigest(), statements



# The diagnostic below is only a reason-code aid. It never grants a SQL parity
# PASS: its bounded-memory per-line categories are not a SQL semantic parser.
_SQL_DIFF_CLASSES = (
    "conditional_ddl", "guarded_set", "guarded_other",
    "ddl_head", "row_head", "delimiter", "continuation",
)
_SQL_DIFF_DDL_RE = re.compile(
    r"\b(?:CREATE|ALTER|DROP|RENAME|TRUNCATE|TRIGGER|INDEX|EVENT|PROCEDURE|FUNCTION|VIEW)\b",
    re.IGNORECASE,
)
_SQL_DIFF_HEAD_DDL_RE = re.compile(
    r"^(?:CREATE|ALTER|DROP|RENAME|TRUNCATE)\s+", re.IGNORECASE,
)
_SQL_DIFF_HEAD_ROW_RE = re.compile(
    r"^(?:INSERT|REPLACE|UPDATE|DELETE|LOAD|COPY)\s+", re.IGNORECASE,
)


def _sql_line_diff_profile(path: Path) -> dict[str, tuple[int, int, int]]:
    """Aggregate line hashes without retaining SQL or large row-value buffers."""
    mask = (1 << 128) - 1
    counters = {key: [0, 0, 0] for key in _SQL_DIFF_CLASSES}
    opener = gzip.open if path.name.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="strict") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith(("--", "#")):
                    continue
                guarded_set = _GUARDED_SESSION_SET_RE.fullmatch(line)
                if guarded_set:
                    cls = "guarded_set"
                    version = int(guarded_set.group("version"))
                    flavor = guarded_set.group("flavor").upper()
                    if ((flavor == "!" and 40000 <= version <= 50699)
                            or (flavor == "M!" and 100000 <= version <= 110899)):
                        line = "GUARDED_SESSION_SET " + guarded_set.group("statement")
                elif line.startswith(("/*!", "/*M!")):
                    cls = ("conditional_ddl" if _SQL_DIFF_DDL_RE.search(line)
                           else "guarded_other")
                elif line.upper().startswith("DELIMITER "):
                    cls = "delimiter"
                elif _SQL_DIFF_HEAD_DDL_RE.match(line):
                    cls = "ddl_head"
                elif _SQL_DIFF_HEAD_ROW_RE.match(line):
                    cls = "row_head"
                else:
                    cls = "continuation"
                # The digest never leaves this process. The diagnostic emits
                # only equality flags and bounded integer counts, no SQL,
                # table names, literal values, or paths.
                value = int.from_bytes(
                    hashlib.blake2b(line.encode("utf-8"), digest_size=16).digest(), "big"
                )
                counters[cls][0] += 1
                counters[cls][1] = (counters[cls][1] + value) & mask
                counters[cls][2] ^= value
    except (OSError, EOFError, UnicodeError) as exc:
        raise RestoreVerifyError("SQL comparison diagnostic is unavailable") from exc
    return {key: tuple(values) for key, values in counters.items()}


def sql_comparison_diagnostic(source: Path, target: Path) -> str:
    """Private-dump comparison summary; informative only, never a success gate."""
    before = _sql_line_diff_profile(source)
    after = _sql_line_diff_profile(target)
    parts = []
    for key in _SQL_DIFF_CLASSES:
        lhs, rhs = before[key], after[key]
        result = "EQUAL" if lhs == rhs else "DIFFER"
        parts.append(f"{key}={result}({lhs[0]}:{rhs[0]})")
    return "SQL_DIFF_V1 " + " ".join(parts)




# The narrow export-format equivalence checker below is a second, independent
# strict gate. It never uses row counts or object names in place of full SQL.
# Only documented, harmless MySQL 8.4 / MariaDB 11.8 dump presentation
# differences are canonicalized; every retained DDL, index and literal is hashed.
_CROSS_ENGINE_SESSION_RE = (
    re.compile(r"^SET @OLD_(?:CHARACTER_SET_CLIENT|CHARACTER_SET_RESULTS|COLLATION_CONNECTION|TIME_ZONE|SQL_NOTES)=@@(?:CHARACTER_SET_CLIENT|CHARACTER_SET_RESULTS|COLLATION_CONNECTION|TIME_ZONE|SQL_NOTES)$", re.I),
    re.compile(r"^SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0$", re.I),
    re.compile(r"^SET NAMES utf8mb4$", re.I),
    re.compile(r"^SET TIME_ZONE='\+00:00'$", re.I),
    re.compile(r"^SET @OLD_(?:UNIQUE_CHECKS|FOREIGN_KEY_CHECKS)=@@(?:UNIQUE_CHECKS|FOREIGN_KEY_CHECKS), (?:UNIQUE_CHECKS|FOREIGN_KEY_CHECKS)=0$", re.I),
    re.compile(r"^SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO'$", re.I),
    re.compile(r"^SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0$", re.I),
    re.compile(r"^SET (?:CHARACTER_SET_CLIENT|CHARACTER_SET_RESULTS|COLLATION_CONNECTION|TIME_ZONE|SQL_NOTES|NOTE_VERBOSITY)=@OLD_(?:CHARACTER_SET_CLIENT|CHARACTER_SET_RESULTS|COLLATION_CONNECTION|TIME_ZONE|SQL_NOTES|NOTE_VERBOSITY)$", re.I),
    re.compile(r"^SET (?:UNIQUE_CHECKS|FOREIGN_KEY_CHECKS)=@OLD_(?:UNIQUE_CHECKS|FOREIGN_KEY_CHECKS)$", re.I),
    re.compile(r"^SET SQL_MODE=@OLD_SQL_MODE$", re.I),
    re.compile(r"^SET @saved_cs_client = @@character_set_client$", re.I),
    re.compile(r"^SET character_set_client = (?:@saved_cs_client|utf8mb4)$", re.I),
)


def _cross_engine_space(sql: str) -> str:
    """Collapse only whitespace outside quoted SQL literals or identifiers."""
    out: list[str] = []
    quote = ""
    space = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            out.append(char)
            if char == "\\" and index + 1 < len(sql):
                index += 1
                out.append(sql[index])
            elif char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    index += 1
                    out.append(sql[index])
                else:
                    quote = ""
        elif char in ("'", '"', "\x60"):
            if space and out:
                out.append(" ")
            space = False
            quote = char
            out.append(char)
        elif char.isspace():
            space = True
        else:
            if space and out:
                out.append(" ")
            space = False
            out.append(char)
        index += 1
    if quote:
        raise RestoreVerifyError("cross-engine SQL literal is unterminated")
    return "".join(out).strip()


def _cross_engine_known_session(sql: str) -> bool:
    guard = _GUARDED_SESSION_SET_RE.fullmatch(sql)
    if not guard:
        return False
    version = int(guard.group("version"))
    flavor = guard.group("flavor").upper()
    if not ((flavor == "!" and 40000 <= version <= 50699)
            or (flavor == "M!" and 100000 <= version <= 110899)):
        return False
    statement = _cross_engine_space(guard.group("statement"))
    return any(pattern.fullmatch(statement) for pattern in _CROSS_ENGINE_SESSION_RE)


def _cross_engine_schema(sql: str) -> str:
    if sql.upper().startswith("CREATE DATABASE "):
        # Only the MySQL default *off* encryption option is export metadata.
        sql = sql.replace(" /*!80016 DEFAULT ENCRYPTION='N' */", "")
    if not sql.upper().startswith("CREATE TABLE "):
        return sql
    charset = re.search(r"\bDEFAULT CHARSET=([A-Za-z0-9_]+)\b", sql, re.I)
    collation = re.search(r"\bCOLLATE=([A-Za-z0-9_]+)\b", sql, re.I)
    if charset and collation:
        actual_charset = charset.group(1).lower()
        actual_collation = collation.group(1).lower()
        text_column = re.compile(
            r"(?P<column>\x60[A-Za-z0-9_]+\x60\s+(?:TINYTEXT|TEXT|MEDIUMTEXT|LONGTEXT))"
            r"\s+CHARACTER SET (?P<charset>[A-Za-z0-9_]+)"
            r"\s+COLLATE (?P<collation>[A-Za-z0-9_]+)(?=\s*,|\s+DEFAULT NULL\s*[,)])",
            re.I,
        )

        def inherited(match: re.Match[str]) -> str:
            if (match.group("charset").lower() == actual_charset
                    and match.group("collation").lower() == actual_collation):
                return match.group("column")
            return match.group(0)

        sql = text_column.sub(inherited, sql)
    # Nullable TEXT DEFAULT NULL and no DEFAULT have identical stored defaults.
    sql = re.sub(
        r"(\x60[A-Za-z0-9_]+\x60\s+(?:TINYTEXT|TEXT|MEDIUMTEXT|LONGTEXT))"
        r"\s+DEFAULT NULL(?=\s*[,)])", r"\1", sql, flags=re.I,
    )
    # MariaDB reports this legacy display width; neither side uses ZEROFILL.
    def strip_display_width(match: re.Match[str]) -> str:
        column = match.group(0)
        if re.search(r"\bZEROFILL\b", column, re.I):
            return column
        return re.sub(r"\bBIGINT\(20\)(?=\s|[,)]|$)", "bigint", column, flags=re.I)

    sql = re.sub(
        r"\x60[A-Za-z0-9_]+\x60\s+BIGINT\(20\)[^,)]*(?=,|\))",
        strip_display_width, sql, flags=re.I,
    )
    return sql


def sql_cross_engine_known_format_fingerprint(path: Path) -> tuple[str, int]:
    """Hash whole SQL statements; refuse unknown syntax, data or DDL changes.

    This check is intentionally narrower than a semantic SQL comparison.
    Each statement remains represented, including versioned ALTER TABLE
    directives, constraints, triggers and all literal content.
    """
    digest = hashlib.sha256()
    statements = 0
    create_count = 0
    pending: list[str] = []
    pending_size = 0
    opener = gzip.open if path.name.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="strict") as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                if line.upper().startswith("DELIMITER "):
                    raise RestoreVerifyError("custom SQL delimiters require manual schema verification")
                if not pending and line.startswith(("--", "#")):
                    continue
                if not pending and line == r"/*M!999999\- enable the sandbox mode */":
                    continue
                if not pending and _cross_engine_known_session(line):
                    continue
                if not pending and (
                    re.fullmatch(r"LOCK TABLES \x60[A-Za-z0-9_$.-]+\x60 WRITE;", line, re.I)
                    or re.fullmatch(r"UNLOCK TABLES;", line, re.I)
                    or re.fullmatch(r"SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;", line, re.I)
                    or re.fullmatch(r"SET AUTOCOMMIT=@OLD_AUTOCOMMIT;", line, re.I)
                    or re.fullmatch(r"COMMIT;", line, re.I)
                ):
                    continue
                pending.append(line)
                pending_size += len(line)
                if pending_size > 128 * 1024 * 1024:
                    raise RestoreVerifyError("cross-engine SQL statement exceeds safe limit")
                if not line.endswith(";"):
                    continue
                statement = _cross_engine_space(" ".join(pending))
                pending.clear()
                pending_size = 0
                statement = _cross_engine_schema(statement)
                if statement.upper().startswith("CREATE TABLE "):
                    create_count += 1
                digest.update(statement.encode("utf-8"))
                digest.update(b"\n")
                statements += 1
    except (OSError, EOFError, UnicodeError) as exc:
        raise RestoreVerifyError("cross-engine SQL dump cannot be read") from exc
    if pending:
        raise RestoreVerifyError("cross-engine SQL statement is unterminated")
    if not statements or not create_count:
        raise RestoreVerifyError("cross-engine SQL dump has no comparable tables")
    return digest.hexdigest(), statements


_CREATE_OBJECT_RE = re.compile(
    r"^CREATE\s+(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([A-Za-z0-9_.$-]+)`?",
    re.IGNORECASE,
)
_DATA_STATEMENT_RE = re.compile(r"^(?:INSERT|REPLACE)\s+INTO\s+", re.IGNORECASE)


def sql_data_fingerprint(path: Path) -> dict[str, Any]:
    """Cross-engine content fingerprint for logical MariaDB/MySQL migrations.

    DDL emitted by MariaDB and MySQL can differ while representing the same
    imported data. This fingerprint deliberately compares logical object names
    plus DML content and ignores engine-specific dump/session metadata.
    """
    opener = gzip.open if path.name.endswith(".gz") else open
    objects: set[str] = set()
    data_line_hashes: list[str] = []
    try:
        with opener(path, "rt", encoding="utf-8", errors="strict") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("--") or line.startswith("#"):
                    continue
                # Version-gated/session directives differ legitimately across
                # MariaDB/MySQL exports and are not row-content evidence.
                if line.startswith("/*!") or line.startswith("/*M!"):
                    continue
                normalized = canonical_sql_line(line)
                object_match = _CREATE_OBJECT_RE.match(normalized)
                if object_match:
                    objects.add(object_match.group(1))
                if re.match(r"^(?:INSERT|REPLACE|UPDATE|DELETE|LOAD|COPY)[ ]+", normalized, re.I) and not _DATA_STATEMENT_RE.match(normalized):
                    raise RestoreVerifyError("unrecognized SQL data command in cross-engine verification")
                if _DATA_STATEMENT_RE.match(normalized):
                    if not normalized.endswith(";"):
                        raise RestoreVerifyError(
                            "multiline SQL data requires manual cross-engine verification"
                        )
                    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                    data_line_hashes.append(digest)
    except (OSError, EOFError, UnicodeError) as exc:
        raise RestoreVerifyError(
            f"SQL dump cannot be content-fingerprinted: {path.name}"
        ) from exc

    if not objects and not data_line_hashes:
        raise RestoreVerifyError(
            f"SQL dump has no comparable logical content: {path.name}"
        )
    # Sorting makes table/export ordering differences non-semantic while every
    # DML statement remains represented.
    digest = hashlib.sha256()
    for item in sorted(data_line_hashes):
        digest.update(item.encode("ascii"))
        digest.update(b"\n")
    return {
        "objects": sorted(objects),
        "data_hash": digest.hexdigest(),
        "data_statements": len(data_line_hashes),
    }


def sql_structure_fingerprint(path: Path) -> tuple[str, int]:
    """Conservative DDL parity gate for cross-engine SQL restore.

    Unlike a row-only fingerprint, this catches lost indexes, constraints,
    triggers, defaults and changed collations. Unknown vendor-guarded DDL and
    custom delimiters remain unproven rather than silently accepted.
    """
    opener = gzip.open if path.name.endswith(".gz") else open
    digest = hashlib.sha256()
    ddl_count = 0
    collecting: list[str] = []
    ddl_start = re.compile(
        r"^(?:CREATE|ALTER|DROP|RENAME|TRUNCATE)[ ]+",
        re.IGNORECASE,
    )
    try:
        with opener(path, "rt", encoding="utf-8", errors="strict") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("--") or line.startswith("#"):
                    continue
                if line.upper().startswith("DELIMITER "):
                    raise RestoreVerifyError("custom SQL delimiters require manual schema verification")
                if line.startswith("/*!") or line.startswith("/*M!"):
                    if re.search(
                        r"(?:CREATE|ALTER|DROP|RENAME|TRUNCATE|TRIGGER|INDEX|EVENT|PROCEDURE|FUNCTION|VIEW)",
                        line, re.I,
                    ):
                        raise RestoreVerifyError("conditional SQL DDL is not independently verified")
                    continue
                if not collecting and not ddl_start.match(line):
                    continue
                collecting.append(canonical_sql_line(line))
                if line.endswith(";"):
                    statement = " ".join(" ".join(collecting).split())
                    digest.update(statement.encode("utf-8"))
                    digest.update(bytes((10,)))
                    ddl_count += 1
                    collecting.clear()
    except (OSError, UnicodeError, EOFError) as exc:
        raise RestoreVerifyError("SQL schema cannot be fingerprinted") from exc
    if collecting:
        raise RestoreVerifyError("unterminated SQL schema statement")
    if ddl_count == 0:
        raise RestoreVerifyError("no comparable SQL schema statements")
    return digest.hexdigest(), ddl_count


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


def sqlite_archive_excluded_paths(manifest: dict[str, Any], site_root: str) -> set[str]:
    primary = sqlite_relative_paths(manifest, site_root)
    excluded = set(primary)
    for rel in primary:
        for suffix in ("-wal", "-shm", "-journal"):
            excluded.add(rel + suffix)
    return excluded


def verify_files(package_dir: Path, manifest: dict[str, Any], target_site: Path, site_root: str) -> dict[str, Any]:
    archive_ref = manifest.get("contents", {}).get("files_archive")
    if not isinstance(archive_ref, str):
        raise RestoreVerifyError("files archive reference is missing")
    archive = restore_plan.safe_package_path(package_dir, archive_ref)
    skip = sqlite_archive_excluded_paths(manifest, site_root)
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
        conn = None
        try:
            uri = target.resolve().as_uri() + "?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True, timeout=5)
            row = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.Error:
            failures.append(f"SQLITE_INTEGRITY_FAIL:{source}")
            continue
        finally:
            if conn is not None:
                conn.close()
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
