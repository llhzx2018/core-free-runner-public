"""Pre-import host boundary for P07's untrusted SQL scratch streams.

This is a conservative fail-closed tripwire, NOT an SQL parser or sandbox.
Only private counts and fixed reason codes can leave the VPS process.
No database, CloudPanel, remote SSH, file or state is modified.
"""
from __future__ import annotations

import gzip
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
import re
from typing import BinaryIO, Iterable, Iterator

MAX_UNCOMPRESSED = 512 * 1024 * 1024

# MariaDB client meta commands are dangerous on the host even with socket-only
# and a nonroot UID. Reject ALL line-start backslash commands, not only \!.
_META = re.compile(rb"^[ \t]*\\")
_CLIENT = re.compile(rb"^[ \t]*(?:DELIMITER|SOURCE|SYSTEM|TEE|NOTEE|PAGER|NOPAGER|CONNECT|RESETCONNECTION)\b", re.I)
# Host-accessing and dynamic SQL must be recognized across newline/comment
# boundaries, not by the first physical line of a statement. Quoted strings
# and ordinary comments are masked by _SafeStatementScanner before matching.
# This is deliberately stricter than SQL's full grammar; unknown executable
# versioned-comment contexts fail closed instead of being guessed safe.
_HOST_SQL = re.compile(
    rb"(?:\bLOAD\s+DATA\b|"
    rb"\bINTO\s+(?:OUTFILE|DUMPFILE)\b|"
    rb"\bLOAD_FILE\s*\(|"
    rb"\bINSTALL\s+(?:PLUGIN|SONAME)\b|"
    rb"\bUNINSTALL\s+PLUGIN\b|"
    rb"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|AGGREGATE)\b"
       rb"[\s\S]*?\bSONAME\b|"
    rb"\bSET\s+(?:GLOBAL|PERSIST|PERSIST_ONLY)\b|"
    rb"\bGRANT\b|\bREVOKE\b|"
    rb"\b(?:CREATE|ALTER|DROP)\s+USER\b|"
    rb"\bSHUTDOWN\b|"
    rb"\bRESET\s+MASTER\b|\bCHANGE\s+MASTER\b|"
    rb"\bPREPARE\b|\bEXECUTE\b|\bDEALLOCATE\s+PREPARE\b)",
    re.I,
)
MAX_STATEMENT_BYTES = 64 * 1024 * 1024

_VERSIONED = re.compile(rb"^/\*(?:!|M!)\s*[0-9]{5,6}\s*(.*?)\s*\*/\s*;\s*$", re.I | re.S)


class HostPolicyBlocked(RuntimeError):
    """Deliberately never embed a database name, SQL text or private path."""


class _SafeStatementScanner:
    """Bounded lexical screen for the SQL bytes sent to the scratch client.

    It is not an SQL parser and never approves a production import. It masks
    literal/comment contents, holds code across physical lines and checks
    every completed statement. Unsupported executable guard layouts block.
    """

    def __init__(self) -> None:
        self.state = "code"
        self.code = bytearray()

    def _check(self) -> None:
        if _HOST_SQL.search(self.code):
            raise HostPolicyBlocked("SCRATCH_SQL_HOST_ACCESS_REFUSED")
        self.code.clear()

    def feed(self, raw: bytes) -> None:
        # MariaDB executes /*!xxxxx ... */ and /*M!xxxxx ... */ comments.
        # Their standalone forms are screened as executable statements. Other
        # placements can hide SQL grammar and must NOT be treated as comments.
        stripped = raw.strip()
        if self.state == "code" and (
            guard := _VERSIONED.fullmatch(stripped)
        ) is not None:
            if self.code.strip():
                raise HostPolicyBlocked("SCRATCH_SQL_GUARD_CONTEXT_UNPROVEN")
            raw = guard.group(1) + b";"
        position = 0
        while position < len(raw):
            c = raw[position]
            following = raw[position + 1] if position + 1 < len(raw) else None
            if self.state == "line_comment":
                if c == 10:
                    self.state = "code"
                    self.code.append(32)
                position += 1
                continue
            if self.state == "block_comment":
                if c == 42 and following == 47:
                    self.state = "code"
                    self.code.append(32)
                    position += 2
                else:
                    position += 1
                continue
            if self.state in {"single", "double", "backtick"}:
                quote = {"single": 39, "double": 34, "backtick": 96}[self.state]
                if c == 92 and self.state != "backtick":
                    # Backslash-escaped SQL string byte. Missing byte fails
                    # with unterminated quote at end-of-stream.
                    position += 2
                    continue
                if c == quote:
                    if following == quote:
                        position += 2  # SQL-doubled quote
                        continue
                    self.state = "code"
                    self.code.append(32)
                position += 1
                continue
            if c == 45 and following == 45 and (
                position + 2 == len(raw) or raw[position + 2] <= 32
            ):
                self.state = "line_comment"
                self.code.append(32)
                position += 2
                continue
            if c == 35:
                self.state = "line_comment"
                self.code.append(32)
                position += 1
                continue
            if c == 47 and following == 42:
                if (position + 2 < len(raw) and raw[position + 2] == 33) or (
                    position + 3 < len(raw) and raw[position + 2:position + 4] == b"M!"
                ):
                    raise HostPolicyBlocked("SCRATCH_SQL_GUARD_CONTEXT_UNPROVEN")
                self.state = "block_comment"
                self.code.append(32)
                position += 2
                continue
            if c in (39, 34, 96):
                self.state = {39: "single", 34: "double", 96: "backtick"}[c]
                self.code.append(32)
            elif c == 59:
                self._check()
            else:
                self.code.append(c)
                if len(self.code) > MAX_STATEMENT_BYTES:
                    raise HostPolicyBlocked("SCRATCH_SQL_STATEMENT_TOO_LARGE")
            position += 1

    def finish(self) -> None:
        if self.state not in {"code", "line_comment"}:
            raise HostPolicyBlocked("SCRATCH_SQL_LEXICAL_BOUNDARY_UNPROVEN")
        self._check()


def inspect_lines(lines: Iterable[bytes], *, sink: BinaryIO | None = None) -> int:
    """Screen COMPLETE SQL stdin before any engine is started.

    No parser or schema rewrite. Approved bytes, including blank and multiline
    SQL string lines, go unchanged into the private sealed file. A failed
    screen discards that file before the scratch engine sees any bytes.
    """
    total = 0
    scan = _SafeStatementScanner()
    try:
        for line in lines:
            if type(line) is not bytes:
                raise HostPolicyBlocked("SCRATCH_SQL_STREAM_TYPE_UNPROVEN")
            total += len(line)
            if total > MAX_UNCOMPRESSED:
                raise HostPolicyBlocked("SCRATCH_SQL_UNCOMPRESSED_LIMIT")
            if _META.match(line) or _CLIENT.match(line):
                raise HostPolicyBlocked("SCRATCH_SQL_CLIENT_CONTROL_REFUSED")
            scan.feed(line)
            if sink is not None:
                sink.write(line)
        scan.finish()
        return total
    except HostPolicyBlocked:
        raise
    except (OSError, EOFError, ValueError, TypeError):
        raise HostPolicyBlocked("SCRATCH_SQL_STREAM_UNREADABLE") from None


def preflight_sql(sql_path: Path, *, quarantine_plan: dict | None = None) -> int:
    """Read the private gz export completely; never log its bytes or identifiers."""
    if quarantine_plan is not None:
        import scratch_guard_quarantine
        try:
            return inspect_lines(
                scratch_guard_quarantine.filtered_bytes(sql_path, quarantine_plan)
            )
        except scratch_guard_quarantine.QuarantineBlocked:
            raise HostPolicyBlocked("SCRATCH_QUARANTINE_STREAM_UNPROVEN") from None

    try:
        with gzip.open(sql_path, "rb") as stream:
            return inspect_lines(stream)
    except HostPolicyBlocked:
        raise
    except (OSError, EOFError, ValueError, TypeError):
        raise HostPolicyBlocked("SCRATCH_SQL_STREAM_UNREADABLE") from None


@contextmanager
def sealed_sql_stream(sql_path: Path, *, quarantine_plan: dict | None = None) -> Iterator[Path]:
    """Seal precisely the inspected bytes before starting ANY scratch engine.

    The original gzip is read exactly once, completely, into a private 0700
    temporary directory. Engines receive ONLY the resulting 0600 plain SQL
    file. Quarantine's digest/count validation must complete before yield.
    Never retain or print this sensitive file; cleanup also covers failures.
    This is host-policy screening, not arbitrary SQL safety or restore proof.
    """
    import scratch_guard_quarantine
    try:
        with tempfile.TemporaryDirectory(prefix="vfops-sql-seal-") as temp:
            root = Path(temp)
            os.chmod(root, 0o700)
            sealed = root / "approved.sql"
            with sealed.open("xb") as output:
                os.chmod(sealed, 0o600)
                if quarantine_plan is not None:
                    inspect_lines(
                        scratch_guard_quarantine.filtered_bytes(sql_path, quarantine_plan),
                        sink=output,
                    )
                else:
                    with gzip.open(sql_path, "rb") as stream:
                        inspect_lines(stream, sink=output)
                output.flush()
                os.fsync(output.fileno())
            yield sealed
    except HostPolicyBlocked:
        raise
    except scratch_guard_quarantine.QuarantineBlocked:
        raise HostPolicyBlocked("SCRATCH_QUARANTINE_STREAM_UNPROVEN") from None
    except (OSError, EOFError, ValueError, TypeError):
        raise HostPolicyBlocked("SCRATCH_SQL_SEAL_UNAVAILABLE") from None
