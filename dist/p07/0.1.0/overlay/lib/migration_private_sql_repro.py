"""Issue #287: one-shot private reproduction of rejected version-guarded SQL.

The private excerpt is NOT an approved statement and must NEVER be executed.
Only source versioned control lines are retained: no table data or full dump.
The public return contains fixed tokens/counts, never SQL or identifiers.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

import verify


class PrivateSqlReproBlocked(RuntimeError):
    """Only fixed non-private error codes may be raised."""


REPRO_SCHEMA = "p07.issue287.private-guard-repro.v1"
_GUARD = re.compile(r"^/\*!([0-9]{5,6})\s+(.+?)\s*\*/;?$", re.I)
_STAGE = re.compile(
    r"^(?:SELECT\s+COUNT\s*\(|SET\s+@|PREPARE\s+|EXECUTE\s+|DEALLOCATE\s+PREPARE\s+)",
    re.I,
)
_SERVER_VERSION = re.compile(
    r"^--\s+Server version\s+([0-9]{1,3}\.[0-9]{1,3}(?:\.[0-9]{1,4})?)"
    r"(?=$|[-\s])", re.I,
)
_EXPORT_TOOL = re.compile(r"^--\s+(MySQL|MariaDB)\s+dump\b", re.I)
_LEXER = re.compile(
    r"(?P<ws>\s+)|"
    r"(?P<quoted>'(?:\\.|''|[^'])*'|\"(?:\\.|\"\"|[^\"])*\")|"
    r"(?P<backtick>\x60(?:\x60\x60|[^\x60])*\x60)|"
    r"(?P<variable>@@?[A-Za-z_][A-Za-z_0-9$]*)|"
    r"(?P<number>(?:0|[1-9][0-9]*)(?:\.[0-9]+)?)|"
    r"(?P<word>[A-Za-z_][A-Za-z_0-9$]*)|"
    r"(?P<symbol>[(),.=;*/+<>!?-])|"
    r"(?P<other>.)",
    re.I | re.S,
)
# Reveal only grammar-relevant SQL keywords, not identifiers or literal values.
_WORDS = frozenset({
    "SET", "SESSION", "LOCAL", "GLOBAL", "PERSIST", "PERSIST_ONLY",
    "SQL_MODE", "SQL_NOTES", "AUTOCOMMIT", "NAMES", "TIME_ZONE",
    "CHARACTER_SET_CLIENT", "CHARACTER_SET_RESULTS", "COLLATION_CONNECTION",
    "FOREIGN_KEY_CHECKS", "UNIQUE_CHECKS", "SELECT", "FROM", "WHERE",
    "INTO", "TABLE", "TABLES", "COUNT", "IF", "THEN", "ELSE",
    "NULL", "TRUE", "FALSE", "AND", "OR", "NOT", "AS", "IS",
    "CONCAT", "REPLACE", "COALESCE", "IFNULL", "CAST", "CONVERT",
    "VERSION", "DATABASE", "CURRENT_USER", "PREPARE", "EXECUTE",
    "DEALLOCATE", "CREATE", "ALTER", "DROP", "DELETE", "UPDATE",
    "INSERT", "GRANT", "REVOKE", "CALL", "DO", "TRUNCATE",
})


def _masked_branch(literal: str) -> dict[str, Any]:
    """Preserve control grammar without ever returning private SQL bytes."""
    if len(literal) > 4096 or len(literal) < 2:
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_BRANCH_UNBOUNDED")
    body = literal[1:-1].replace("''", "'")
    tokens: list[str] = []
    for token in _LEXER.finditer(body):
        kind = token.lastgroup
        if kind == "ws":
            continue
        if len(tokens) >= 100:
            raise PrivateSqlReproBlocked("PRIVATE_REPRO_LEXICAL_COMPLEXITY")
        if kind == "word":
            val = token.group().upper()
            tokens.append(val if val in _WORDS else "IDENTIFIER")
        elif kind == "variable":
            tokens.append("SYSTEM_VARIABLE" if token.group().startswith("@@")
                          else "USER_VARIABLE")
        elif kind == "quoted":
            tokens.append("STRING_LITERAL")
        elif kind == "backtick":
            tokens.append("QUOTED_IDENTIFIER")
        elif kind == "number":
            tokens.append("NUMBER_LITERAL")
        elif kind == "symbol":
            tokens.append(token.group())
        else:
            tokens.append("UNRECOGNIZED_CHARACTER")
    if not tokens:
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_EMPTY_BRANCH")
    return {
        "tokens": tokens,
        "guard_verdict": "SAFE_SYNTAX_ONLY" if verify._cross_engine_safe_dynamic_branch(
            literal
        ) else "UNPROVEN",
    }


def _private_dir(root: Path) -> Path:
    """Reject symlink/permission confusion before storing any SQL."""
    try:
        stat_root = root.lstat()
    except OSError:
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_MIGRATION_ROOT_MISSING") from None
    if (not stat.S_ISDIR(stat_root.st_mode)
            or stat_root.st_uid != os.geteuid()
            or stat_root.st_mode & 0o077):
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_MIGRATION_ROOT_UNSAFE")
    folder = root / "private-sql-repro"
    if folder.exists() or folder.is_symlink():
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_ALREADY_PRESENT_NO_OVERWRITE")
    try:
        folder.mkdir(mode=0o700)
    except OSError:
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_DIRECTORY_CREATE_FAILED") from None
    return folder


def _exclusive_private_write(path: Path, data: bytes) -> None:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except OSError:
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_EXCLUSIVE_WRITE_REFUSED") from None
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except OSError:
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_PRIVATE_WRITE_FAILED") from None


def _read_guard_fragments(source: Path) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    """Extract exact five-stage guard commands; never retain row data."""
    opener = gzip.open if source.suffix == ".gz" else open
    captures: list[str] = []
    branches: list[dict[str, Any]] = []
    environment: dict[str, Any] = {
        "source_server_version": "UNAVAILABLE",
        "source_export_tool": "UNAVAILABLE",
    }
    try:
        with opener(source, "rt", encoding="utf-8", errors="strict") as handle:
            for lineno, raw in enumerate(handle, 1):
                if lineno <= 120:
                    header = raw.strip()
                    version = _SERVER_VERSION.match(header)
                    tool = _EXPORT_TOOL.match(header)
                    if version:
                        environment["source_server_version"] = version.group(1)
                    if tool:
                        environment["source_export_tool"] = tool.group(1).upper()
                # Large DML rows do not belong in the private reproduction.
                if len(raw) > 16384:
                    continue
                line = raw.strip()
                match = _GUARD.fullmatch(line)
                if not match or not 40000 <= int(match.group(1)) < 80000:
                    continue
                body = re.sub(r"\s+", " ", match.group(2).strip())
                if not _STAGE.match(body):
                    continue
                if len(captures) >= 64 or len(line) > 8192:
                    raise PrivateSqlReproBlocked("PRIVATE_REPRO_GUARD_BOUND_EXCEEDED")
                captures.append(line)
                setting = verify._CROSS_ENGINE_DYNAMIC_IF_RE.fullmatch(body)
                if setting:
                    if len(branches) >= 3:
                        raise PrivateSqlReproBlocked("PRIVATE_REPRO_MORE_THAN_THREE_GUARDS")
                    branches.append({
                        "ordinal": len(branches) + 1,
                        "version_guard": "SQL_EXECUTABLE_COMMENT",
                        "yes": _masked_branch(setting.group("yes")),
                        "no": _masked_branch(setting.group("no")),
                    })
    except (OSError, EOFError, UnicodeError):
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_SOURCE_UNREADABLE") from None
    if len(branches) != 3 or len(captures) < 13:
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_THREE_COMPLETE_GROUPS_NOT_OBSERVED")
    excerpt = ("\n".join(captures) + "\n").encode("utf-8")
    if len(excerpt) > 100000:
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_EXCERPT_TOO_LARGE")
    return excerpt, branches, environment


def _read_target_header(target: Path) -> dict[str, str]:
    opener = gzip.open if target.suffix == ".gz" else open
    found = {"target_server_version": "UNAVAILABLE", "target_export_tool": "UNAVAILABLE"}
    try:
        with opener(target, "rt", encoding="utf-8", errors="strict") as handle:
            for i, raw in enumerate(handle):
                if i >= 120:
                    break
                line = raw.strip()
                if match := _SERVER_VERSION.match(line):
                    found["target_server_version"] = match.group(1)
                if match := _EXPORT_TOOL.match(line):
                    found["target_export_tool"] = match.group(1).upper()
    except (OSError, EOFError, UnicodeError):
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_TARGET_HEADER_UNREADABLE") from None
    return found


def capture_private_repro(
    migration_root: Path, source_dump: Path, target_dump: Path,
) -> dict[str, Any]:
    """One diagnostic pass, two private files, no DB or state modifications."""
    excerpt, branches, source_env = _read_guard_fragments(source_dump)
    target_env = _read_target_header(target_dump)
    sha256 = hashlib.sha256(excerpt).hexdigest()
    folder = _private_dir(migration_root)
    # This is deliberately a .txt file: do NOT execute these SQL fragments.
    private_fragment = folder / "guarded_fragments.NEVER_EXECUTE.txt"
    _exclusive_private_write(private_fragment, excerpt)
    # Check that these exact retained bytes reproduce the diagnostic flow,
    # not just a count of strings extracted from the original full export.
    try:
        flow = verify.sql_dynamic_guard_flow_diagnostic(private_fragment)
    except verify.RestoreVerifyError:
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_VERIFIER_REPLAY_UNAVAILABLE") from None
    if not (
        flow.startswith("SQL_GUARD_FLOW_V1 probe=1 assignment=3 safe_assignment=0 ")
        and " prepare=3 execute=3 deallocate=3 " in flow
        and flow.endswith("outcome=UNSAFE_BRANCH")
    ):
        raise PrivateSqlReproBlocked("PRIVATE_REPRO_OBSERVED_FLOW_NOT_REPRODUCIBLE")
    receipt = {
        "schema": REPRO_SCHEMA,
        "scope": "PRIVATE_SQL_REPRO_NOT_AN_EXECUTION_OR_MIGRATION_GATE",
        "source_sha256": sha256,
        "excerpt_lines": excerpt.count(b"\n"),
        "observed_if_groups": len(branches),
        "reproduced_guard_flow": flow,
        "environment": {**source_env, **target_env},
        "branches": branches,
        "database_writes_performed": False,
        "migration_state_modified": False,
        "reimport_allowed": False,
        "cutover_allowed": False,
    }
    _exclusive_private_write(
        folder / "private_receipt.json",
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
    )
    # No filesystem path or hash is returned: PRIVATE_DATA stays inside CP2.
    return {
        "status": "PRIVATE_MINIMAL_REPRO_CAPTURED_NOT_VERIFIED",
        "observed_if_groups": len(branches),
        "guard_lines": receipt["excerpt_lines"],
        "reproduced_guard_flow": flow,
        "environment": receipt["environment"],
        "branches": branches,
        "private_bytes_exported_to_chat_or_runner": False,
        "db_reimport_allowed": False,
        "migration_resume_allowed": False,
        "cutover_allowed": False,
    }
