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
# These SQL forms access the host filesystem, alter privileges or control a
# server. The first SQL keyword may be wrapped in a versioned comment.
_HOST_SQL = re.compile(
    rb"^(?:LOAD\s+DATA\b|"
    rb"SELECT\b[^\r\n]*\bINTO\s+(?:OUTFILE|DUMPFILE)\b|"
    rb"INSERT\b[^\r\n]*\bINTO\s+(?:OUTFILE|DUMPFILE)\b|"
    rb"INSTALL\s+(?:PLUGIN|SONAME)\b|UNINSTALL\s+PLUGIN\b|"
    rb"CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|AGGREGATE)\b[^\r\n]*\bSONAME\b|"
    rb"SET\s+(?:GLOBAL|PERSIST|PERSIST_ONLY)\b|"
    rb"GRANT\b|REVOKE\b|"
    rb"CREATE\s+USER\b|ALTER\s+USER\b|DROP\s+USER\b|"
    rb"SHUTDOWN\b|"
    rb"RESET\s+MASTER\b|CHANGE\s+MASTER\b|"
    rb"LOAD_FILE\s*\()",
    re.I,
)
_VERSIONED = re.compile(rb"^/\*(?:!|M!)\s*[0-9]{5,6}\s*(.*?)\s*\*/\s*;\s*$", re.I | re.S)


class HostPolicyBlocked(RuntimeError):
    """Deliberately never embed a database name, SQL text or private path."""


def inspect_lines(lines: Iterable[bytes], *, sink: BinaryIO | None = None) -> int:
    """Consume complete proposed SQL stdin BEFORE starting a database process.

    The input must be the *post-quarantine* stream when using R7/R8.
    Passing this check alone never authorizes an original restore.
    """
    total = 0
    try:
        for line in lines:
            if type(line) is not bytes:
                raise HostPolicyBlocked("SCRATCH_SQL_STREAM_TYPE_UNPROVEN")
            total += len(line)
            if total > MAX_UNCOMPRESSED:
                raise HostPolicyBlocked("SCRATCH_SQL_UNCOMPRESSED_LIMIT")
            stripped = line.lstrip(b" \t\r\n")
            if not stripped:
                continue
            if _META.match(line) or _CLIENT.match(line):
                raise HostPolicyBlocked("SCRATCH_SQL_CLIENT_CONTROL_REFUSED")
            versioned = _VERSIONED.fullmatch(stripped)
            sql = versioned.group(1).lstrip() if versioned else stripped
            if _HOST_SQL.match(sql):
                raise HostPolicyBlocked("SCRATCH_SQL_HOST_ACCESS_REFUSED")
            if sink is not None:
                sink.write(line)
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
