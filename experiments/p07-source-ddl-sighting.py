"""P07 source schema sighting without decoding unrelated DML bytes.

ADVISORY ONLY. Operates on a completed private gzip export in an isolated
workspace. This is not a SQL parser, a restore or an import gate. Even exact
CREATE TABLE candidates do not prove source DB contents or target recovery.
"""
from __future__ import annotations
import gzip
from pathlib import Path
import re
import stat

MAX_UNCOMPRESSED = 1024 * 1024 * 1024
MAX_DDL = 16 * 1024 * 1024
SCHEMA_LINE = re.compile(
    rb"^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    rb"(?:\x60(?:[^\x60]|\x60\x60)+\x60|[A-Za-z_][A-Za-z0-9_$.-]*)\s*\(",
    re.I,
)
CREATE_LINE = re.compile(rb"^CREATE\s+TABLE\b", re.I)


class UnsafeOrUnverifiedExport(ValueError):
    """A fixed label; never expose paths, SQL, literals or hashes."""


def inspect_source_schema_candidates(path: Path, *, max_bytes: int = MAX_UNCOMPRESSED) -> dict:
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_UNCOMPRESSED:
        raise UnsafeOrUnverifiedExport("INVALID_BYTE_CAP")
    try:
        info = path.lstat()
    except OSError:
        raise UnsafeOrUnverifiedExport("DUMP_MISSING") from None
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
        raise UnsafeOrUnverifiedExport("DUMP_TYPE_OR_PERMISSIONS_UNSAFE")
    if path.suffix != ".gz":
        raise UnsafeOrUnverifiedExport("GZIP_REQUIRED")
    seen = set()
    counted_bytes = 0
    schema_lines = 0
    invalid_ddl = 0
    ddl_buffer: bytearray | None = None
    try:
        with gzip.open(path, "rb") as handle:
            while True:
                line = handle.readline(min(1024 * 1024, max_bytes - counted_bytes + 1))
                if not line:
                    break
                counted_bytes += len(line)
                if counted_bytes > max_bytes:
                    raise UnsafeOrUnverifiedExport("DECOMPRESSED_LIMIT_EXCEEDED")
                stripped = line.lstrip()
                if ddl_buffer is None:
                    if not CREATE_LINE.match(stripped):
                        continue
                    schema_lines += 1
                    ddl_buffer = bytearray(stripped)
                else:
                    ddl_buffer.extend(line)
                if len(ddl_buffer) > MAX_DDL:
                    raise UnsafeOrUnverifiedExport("DDL_STATEMENT_TOO_LARGE")
                # It is a conservative *sighting*, not a semantic SQL parse.
                # Never interpret DML contents or allow an import from it.
                if ddl_buffer.rstrip().endswith(b";"):
                    try:
                        decoded = bytes(ddl_buffer).decode("utf-8", "strict")
                    except UnicodeDecodeError:
                        invalid_ddl += 1
                    else:
                        m = SCHEMA_LINE.match(decoded.encode("utf-8"))
                        if m:
                            header = decoded[:min(len(decoded), 256)]
                            name = re.match(
                                r"^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
                                r"(\x60(?:[^\x60]|\x60\x60)+\x60|[A-Za-z_][A-Za-z0-9_$.-]*)\s*\(",
                                header, re.I
                            )
                            if name:
                                # Local identity used only for duplicate detection.
                                # Never output SQL or a schema/table name.
                                normalized = name.group(1)
                                if normalized in seen:
                                    raise UnsafeOrUnverifiedExport("DUPLICATE_TABLE_CANDIDATE")
                                seen.add(normalized)
                    ddl_buffer = None
    except (OSError, EOFError, UnicodeError):
        raise UnsafeOrUnverifiedExport("GZIP_STREAM_UNAVAILABLE") from None
    if ddl_buffer is not None:
        raise UnsafeOrUnverifiedExport("DDL_STATEMENT_INCOMPLETE")
    return {
        "schema": "P07_SOURCE_DDL_SIGHTING_V1",
        "verification": "NOT_A_PASS_GATE",
        "status": "ADVISORY_ONLY",
        "schema_candidates": schema_lines,
        "recognized_schema_candidates": len(seen),
        "invalid_utf8_ddl_candidates": invalid_ddl,
        "decompressed_bytes": counted_bytes,
        "schema_semantics_verified": False,
        "source_database_provenance_verified": False,
        "dml_content_verified": False,
        "target_restore_verified": False,
        "migration_resume_allowed": False,
        "cutover_allowed": False,
        "database_writes_performed": False,
    }
