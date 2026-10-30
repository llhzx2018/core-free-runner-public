"""R7 scratch-only exact-line quarantine of unsafe versioned SET @ commands.

NOT a production SQL repair, NOT a clean restore, NOT authorization to migrate.
The original bytes remain unchanged; only a private, transient client stdin
stream may omit exactly classified guarded SET comment lines. No SQL is logged.
"""
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
import re
from typing import Iterator
import verify
import sql_diff_evidence as evidence

MAX_BYTES = 512 * 1024 * 1024
MAX_GUARD_LINE = 64 * 1024
_SET = re.compile(r"^SET\s+@[A-Za-z_][A-Za-z_0-9$]*\b", re.I)


class QuarantineBlocked(RuntimeError):
    pass


def _classify(line: bytes) -> bool:
    """Return true ONLY for a single standalone unsafe guarded SET @ line."""
    if b"SET" not in line.upper() or b"@" not in line or b"/*!" not in line:
        return False
    if len(line) > MAX_GUARD_LINE:
        raise QuarantineBlocked("QUARANTINE_GUARD_LINE_TOO_LARGE")
    try:
        raw = line.strip().decode("utf-8", errors="strict")
    except UnicodeError:
        raise QuarantineBlocked("QUARANTINE_GUARD_ENCODING_UNPROVEN") from None
    match = evidence._GUARD_RE.fullmatch(raw)
    if not match or not 40000 <= int(match.group(1)) <= 89999:
        raise QuarantineBlocked("QUARANTINE_GUARD_BOUNDARY_UNPROVEN")
    body = re.sub(r"\s+", " ", match.group(2).strip())
    if not _SET.match(body):
        raise QuarantineBlocked("QUARANTINE_GUARD_NOT_SET")
    known = verify._CROSS_ENGINE_DYNAMIC_IF_RE.fullmatch(body)
    if known:
        unsafe = any(
            not verify._cross_engine_safe_dynamic_branch(known.group(name))
            for name in ("yes", "no")
        )
        return unsafe
    if verify._cross_engine_known_session(raw):
        return False
    return True


def _scan(sql_path: Path) -> tuple[str, int, int]:
    sha = hashlib.sha256()
    removed = 0
    size = 0
    try:
        with gzip.open(sql_path, "rb") as stream:
            for line in stream:
                size += len(line)
                if size > MAX_BYTES:
                    raise QuarantineBlocked("QUARANTINE_UNCOMPRESSED_SIZE_LIMIT")
                sha.update(line)
                if _classify(line):
                    removed += 1
        return sha.hexdigest(), removed, size
    except QuarantineBlocked:
        raise
    except (OSError, EOFError, UnicodeError, ValueError):
        raise QuarantineBlocked("QUARANTINE_SQL_UNREADABLE") from None



# A scratch-only omission MUST cover the entire guarded dynamic statement flow:
# probe -> unsafe SET assignment -> PREPARE -> EXECUTE -> DEALLOCATE.
# Isolating only SET is unsafe: the remaining PREPARE/EXECUTE may run anyway.
_STAGES = ("probe", "assign", "prepare", "execute", "deallocate")
_COMMENT = re.compile(rb"^(?:--[ \t]|#|/\*(?!\!)(?!M\!)[^\r\n]*\*/)[^\r\n]*$")


def _complete_dynamic_groups(sql_path: Path) -> tuple[set[int], int]:
    """Strict whole-group grammar; all five control lines are omitted in scratch.

    Groups must be contiguous except blank/non-executable comment lines.
    Unknown version guards, malformed syntax, interleaving SQL, or unmatched
    controls hard-block the scratch import. Returned line indices are PRIVATE.
    """
    omit: set[int] = set()
    unsafe_assignments = 0
    stage = 0
    flag = stmt_variable = prepared_name = ""
    try:
        with gzip.open(sql_path, "rb") as stream:
            for number, line in enumerate(stream, 1):
                stripped = line.strip()
                if not stripped:
                    continue
                if re.match(rb"^(?:PREPARE|EXECUTE|DEALLOCATE)\b", stripped, re.I):
                    raise QuarantineBlocked("QUARANTINE_UNGUARDED_CONTROL_REFUSED")
                kind = ""
                variables: tuple[str, ...] = ()
                if stripped.startswith((b"/*!", b"/*M!")):
                    if len(stripped) > MAX_GUARD_LINE:
                        raise QuarantineBlocked("QUARANTINE_GUARD_LINE_TOO_LARGE")
                    try:
                        raw = stripped.decode("utf-8", errors="strict")
                    except UnicodeError:
                        raise QuarantineBlocked("QUARANTINE_GUARD_ENCODING_UNPROVEN") from None
                    m = evidence._GUARD_RE.fullmatch(raw)
                    if m and 40000 <= int(m.group(1)) <= 89999:
                        body = re.sub(r"\s+", " ", m.group(2).strip())
                        if v := verify._CROSS_ENGINE_TABLE_COUNT_RE.fullmatch(body):
                            kind, variables = "probe", (v.group("flag").upper(),)
                        elif v := verify._CROSS_ENGINE_DYNAMIC_IF_RE.fullmatch(body):
                            # Only genuinely rejected dynamic branches qualify.
                            if not _classify(line):
                                raise QuarantineBlocked("QUARANTINE_SAFE_GROUP_NOT_SUPPORTED")
                            kind, variables = "assign", (
                                v.group("stmt").upper(), v.group("flag").upper())
                        elif v := verify._CROSS_ENGINE_PREPARE_RE.fullmatch(body):
                            kind, variables = "prepare", (
                                v.group(1).upper(), v.group(2).upper())
                        elif v := verify._CROSS_ENGINE_EXECUTE_RE.fullmatch(body):
                            kind, variables = "execute", (v.group(1).upper(),)
                        elif v := verify._CROSS_ENGINE_DEALLOCATE_RE.fullmatch(body):
                            kind, variables = "deallocate", (v.group(1).upper(),)
                        elif _SET.match(body) and not verify._cross_engine_known_session(raw):
                            raise QuarantineBlocked("QUARANTINE_UNSUPPORTED_ASSIGNMENT")
                        elif re.match(r"^(?:PREPARE|EXECUTE|DEALLOCATE)\b", body, re.I):
                            raise QuarantineBlocked("QUARANTINE_UNKNOWN_CONTROL")
                        elif stage and not verify._cross_engine_known_session(raw):
                            raise QuarantineBlocked("QUARANTINE_INTERLEAVED_GUARDED_SQL")
                    elif stage or b"PREPARE" in stripped.upper() or b"EXECUTE" in stripped.upper():
                        raise QuarantineBlocked("QUARANTINE_GUARDED_BOUNDARY_UNPROVEN")
                if kind:
                    if kind != _STAGES[stage]:
                        raise QuarantineBlocked("QUARANTINE_DYNAMIC_STAGE_ORDER_UNPROVEN")
                    if stage == 0:
                        flag = variables[0]
                    elif stage == 1:
                        stmt_variable, linked_flag = variables
                        if linked_flag != flag:
                            raise QuarantineBlocked("QUARANTINE_PROBE_FLAG_MISMATCH")
                        unsafe_assignments += 1
                    elif stage == 2:
                        prepared_name, linked_variable = variables
                        if linked_variable != stmt_variable:
                            raise QuarantineBlocked("QUARANTINE_PREPARE_VARIABLE_MISMATCH")
                    elif stage in (3, 4) and variables[0] != prepared_name:
                        raise QuarantineBlocked("QUARANTINE_EXECUTE_NAME_MISMATCH")
                    omit.add(number)
                    stage = (stage + 1) % len(_STAGES)
                elif stage and not _COMMENT.fullmatch(stripped):
                    raise QuarantineBlocked("QUARANTINE_INTERLEAVED_SQL_UNPROVEN")
    except QuarantineBlocked:
        raise
    except (OSError, EOFError, UnicodeError, ValueError):
        raise QuarantineBlocked("QUARANTINE_SQL_UNREADABLE") from None
    if stage:
        raise QuarantineBlocked("QUARANTINE_DYNAMIC_GROUP_INCOMPLETE")
    if len(omit) != unsafe_assignments * len(_STAGES):
        raise QuarantineBlocked("QUARANTINE_DYNAMIC_GROUP_CARDINALITY_UNPROVEN")
    return omit, unsafe_assignments

def plan(sql_path: Path) -> dict:
    """Build bounded, source-local private plan; no SQL fragments/PKs emitted."""
    digest, removed, size = _scan(sql_path)
    try:
        ev = evidence.dynamic_guard_syntax_counts(sql_path)
    except Exception:
        raise QuarantineBlocked("QUARANTINE_CLASSIFIER_UNAVAILABLE") from None
    keys = ("recognized_unsafe", "double_quoted_if", "other_unknown_set")
    if any(type(ev.get(k)) is not int or not 0 <= ev[k] <= 10000 for k in keys):
        raise QuarantineBlocked("QUARANTINE_GUARD_COUNTS_UNPROVEN")
    expected = sum(ev[k] for k in keys)
    omit, whole_groups = _complete_dynamic_groups(sql_path)
    if expected != removed or whole_groups != removed:
        raise QuarantineBlocked("QUARANTINE_CLASSIFIER_DRIFT")
    return {"_digest": digest, "removed": removed, "size": size,
            "_omit_lines": tuple(sorted(omit))}


def filtered_bytes(sql_path: Path, private_plan: dict) -> Iterator[bytes]:
    """Yield original lines except exact standalone guarded SET directives.

    Consume the iterator completely: digest and omitted count are verified
    at EOF. Any mismatch is a hard failed scratch import even if SQL ran.
    """
    if not isinstance(private_plan, dict):
        raise QuarantineBlocked("QUARANTINE_PLAN_MISSING")
    old_digest = private_plan.get("_digest")
    old_count = private_plan.get("removed")
    old_size = private_plan.get("size")
    if (not isinstance(old_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", old_digest)
            or type(old_count) is not int or old_count < 0
            or type(old_size) is not int or not 0 <= old_size <= MAX_BYTES):
        raise QuarantineBlocked("QUARANTINE_PLAN_INVALID")
    omit_lines = private_plan.get("_omit_lines")
    if (not isinstance(omit_lines, tuple)
            or len(omit_lines) != old_count * len(_STAGES)
            or any(type(x) is not int or x < 1 for x in omit_lines)
            or tuple(sorted(set(omit_lines))) != omit_lines):
        raise QuarantineBlocked("QUARANTINE_PLAN_INVALID")
    omit_set = set(omit_lines)
    sha = hashlib.sha256()
    count = 0
    total = 0
    try:
        with gzip.open(sql_path, "rb") as stream:
            for lineno, line in enumerate(stream, 1):
                total += len(line)
                if total > MAX_BYTES:
                    raise QuarantineBlocked("QUARANTINE_UNCOMPRESSED_SIZE_LIMIT")
                sha.update(line)
                if lineno in omit_set:
                    if _classify(line):
                        count += 1
                    yield b""  # explicit no-op, never send the omitted directive
                    continue
                if _classify(line):
                    raise QuarantineBlocked("QUARANTINE_UNEXPECTED_UNSAFE_SET")
                yield line
    except QuarantineBlocked:
        raise
    except (OSError, EOFError, UnicodeError, ValueError):
        raise QuarantineBlocked("QUARANTINE_SQL_UNREADABLE") from None
    if sha.hexdigest() != old_digest or count != old_count or total != old_size:
        raise QuarantineBlocked("QUARANTINE_SOURCE_CHANGED")
