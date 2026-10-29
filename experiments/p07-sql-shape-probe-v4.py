#!/usr/bin/env python3
"""P07 private in-place schema forensics. Prints counts/kinds only, never SQL.

Read-only database exports. Temporary gz files are removed after reporting.
No import, schema changes, DNS actions, service restarts, or website writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
import gzip
from pathlib import Path
import re
import shlex
import sys
import tempfile
import uuid

sys.path.insert(0, "/opt/vf-server-ops/lib")
import cloudpanel
import server_migration_pull as migration
import verify

NAME = re.compile(r"^(?:CREATE|DROP) TABLE (?:IF (?:NOT )?EXISTS )?\x60([^\x60]+)\x60", re.I)
TOKEN = re.compile(
    r"\x60(?:[^\x60]|\x60\x60)*\x60|'(?:\\.|''|[^'])*'|"
    r"[A-Za-z_][A-Za-z_0-9$]*|[0-9]+|[^\s]"
)
SAFE_WORDS = set(
    "CREATE TABLE DROP DEFAULT NULL NOT UNSIGNED SIGNED ZEROFILL INT INTEGER "
    "TINYINT SMALLINT MEDIUMINT BIGINT VARCHAR CHAR TEXT LONGTEXT MEDIUMTEXT "
    "TINYTEXT DATETIME TIMESTAMP DECIMAL FLOAT DOUBLE AUTO_INCREMENT "
    "CHARACTER SET CHARSET COLLATE KEY INDEX UNIQUE PRIMARY FOREIGN REFERENCES "
    "CONSTRAINT CHECK ENGINE COMMENT ROW_FORMAT BTREE USING FULLTEXT SPATIAL "
    "GENERATED STORED VIRTUAL ON UPDATE DELETE CURRENT_TIMESTAMP INVISIBLE "
    "VISIBLE IF EXISTS".split()
)
SAFE_GUARD_VERBS = {"SET", "CREATE", "ALTER", "DROP", "TRIGGER", "VIEW", "USE", "LOCK", "UNLOCK"}


def category(token: str) -> str:
    if token.startswith("\x60"):
        return "IDENT"
    if token.startswith("'"):
        return "LITERAL"
    if token.isdecimal():
        return "NUMBER"
    if token.upper() in SAFE_WORDS:
        return token.upper()
    if token and (token[0].isalpha() or token[0] == "_"):
        return "WORD"
    return token if token in {"(", ")", ",", "=", ";"} else "PUNCT"


def parse_dump(path: Path) -> tuple[dict[str, str], dict[str, str], Counter]:
    tables: dict[str, str] = {}
    drops: dict[str, str] = {}
    guards: Counter = Counter()
    pending: list[str] = []
    with gzip.open(path, "rt", encoding="utf-8", errors="strict") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith(("--", "#")):
                continue
            if not pending and line.startswith(("/*!", "/*M!")):
                matched = re.match(r"/\*(?:!|M!)([0-9]{5,6})\s+([A-Za-z]+)", line, re.I)
                version = int(matched.group(1)) if matched else 0
                verb = matched.group(2).upper() if matched else "OTHER"
                verb = verb if verb in SAFE_GUARD_VERBS else "OTHER"
                family = "MYSQL8" if 80000 <= version <= 89999 else (
                    "MARIADB" if version >= 100000 else "LEGACY"
                )
                guards[family + "_" + verb] += 1
                continue
            if not pending and line.upper().startswith("DROP TABLE "):
                item = NAME.match(line)
                if item:
                    drops[item.group(1)] = verify._cross_engine_space(line)
                continue
            if not pending and not line.upper().startswith("CREATE TABLE "):
                continue
            pending.append(line)
            if not line.endswith(";"):
                continue
            sql = " ".join(pending)
            pending.clear()
            match = NAME.match(sql)
            if match:
                tables[match.group(1)] = verify._cross_engine_space(
                    verify._cross_engine_schema(sql)
                )
    if pending:
        raise ValueError("unclosed CREATE TABLE")
    return tables, drops, guards



# This second-stage forensic report only adds fixed-vocabulary shape counters.
# It does not print database identifiers, charset names, literals or SQL.
SAFE_TYPES = {"CHAR", "VARCHAR", "TINYTEXT", "TEXT", "MEDIUMTEXT", "LONGTEXT", "ENUM", "SET", "DECIMAL", "FLOAT", "DOUBLE", "TINYINT", "SMALLINT", "MEDIUMINT", "INT", "INTEGER", "BIGINT"}
STRING_TYPES = {"CHAR", "VARCHAR", "TINYTEXT", "TEXT", "MEDIUMTEXT", "LONGTEXT", "ENUM", "SET"}
NUMERIC_TYPES = {"DECIMAL", "FLOAT", "DOUBLE", "TINYINT", "SMALLINT", "MEDIUMINT", "INT", "INTEGER", "BIGINT"}
GUARD_VARIABLES = (
    "CHARACTER_SET_CLIENT", "CHARACTER_SET_RESULTS", "COLLATION_CONNECTION",
    "TIME_ZONE", "SQL_NOTES", "NOTE_VERBOSITY", "UNIQUE_CHECKS",
    "FOREIGN_KEY_CHECKS", "SQL_MODE", "AUTOCOMMIT", "NAMES",
)


def table_default_charset(create: str) -> str | None:
    # Match only table options after the *last* table-level closing bracket.
    # Ambiguity yields UNKNOWN rather than a guessed equivalence.
    pos = re.search(r"\)\s*ENGINE\s*=", create, re.I)
    if not pos:
        return None
    options = create[pos.start():]
    match = re.search(
        r"\b(?:DEFAULT\s+)?(?:CHARSET|CHARACTER\s+SET)\s*=?\s*([A-Za-z0-9_]+)\b",
        options, re.I,
    )
    return match.group(1).lower() if match else None


def table_default_collation(create: str) -> str | None:
    pos = re.search(r"\)\s*ENGINE\s*=", create, re.I)
    if not pos:
        return None
    match = re.search(
        r"\bCOLLATE\s*=?\s*([A-Za-z0-9_]+)\b",
        create[pos.start():], re.I,
    )
    return match.group(1).lower() if match else None


def nearest_column_type(tokens: list[str], index: int) -> str:
    # Never expose the actual column identifier.
    for item in range(index - 1, max(-1, index - 100), -1):
        if tokens[item].startswith("\x60"):
            next_index = item + 1
            if next_index < index:
                kind = tokens[next_index].upper()
                return kind if kind in SAFE_TYPES else "OTHER"
            return "OTHER"
    return "OTHER"


# Redacted, bounded SQL grammar tokens for source-only vendor-guard analysis.
# All user-defined identifiers, numeric values and string literals are hidden.
FIXED_GRAMMAR = {
    "SET", "USE", "CREATE", "ALTER", "DROP", "TRIGGER", "VIEW",
    "PROCEDURE", "FUNCTION", "EVENT", "INVISIBLE", "VISIBLE",
    "DEFINER", "SQL", "MODE", "SQL_MODE", "SQL_NOTES", "TIME_ZONE",
    "SQL_LOG_BIN", "SQL_SECURITY", "CHARACTER_SET_CLIENT",
    "CHARACTER_SET_RESULTS", "COLLATION_CONNECTION",
    "NAMES", "LOCK", "UNLOCK", "TABLES", "KEY", "KEYS", "ENABLE",
    "DISABLE", "CHECK", "CONSTRAINT", "INDEX", "ALGORITHM",
    "UNIQUE_CHECKS", "FOREIGN_KEY_CHECKS", "AUTOCOMMIT", "SESSION",
    "GLOBAL", "LOCAL", "DEFAULT", "CHARSET", "COLLATE",
    "SQL_NO_CACHE", "SQL_SAFE_UPDATES", "GTID_NEXT", "GTID_PURGED",
}


def guarded_grammar(path: Path) -> tuple[Counter, Counter]:
    unknown_set = Counter()
    other = Counter()
    with gzip.open(path, "rt", encoding="utf-8", errors="strict") as handle:
        for raw in handle:
            line = raw.strip()
            if not line.startswith(("/*!", "/*M!")):
                continue
            match = re.fullmatch(r"/\*(?:!|M!)[0-9]{5,6}\s+(.+?)\s*\*/;?", line, re.I)
            if not match:
                continue
            body = match.group(1).strip()
            tokens = TOKEN.findall(body)
            first = tokens[0].upper() if tokens else ""
            if first in {"ALTER", "CREATE", "DROP", "RENAME", "TRUNCATE"}:
                continue
            if first == "SET" and verify._cross_engine_known_session(line):
                continue
            classified: list[str] = []
            for token in tokens[:20]:
                if token.startswith("\x60"):
                    item = "IDENT"
                elif token.startswith(("'", '"')):
                    item = "LITERAL"
                elif token.isdecimal():
                    item = "NUMBER"
                elif token.upper() in FIXED_GRAMMAR:
                    item = token.upper()
                elif token in {"@", "=", ",", ".", "(", ")"}:
                    item = token
                else:
                    item = "WORD" if token[:1].isalpha() or token[:1] == "_" else "PUNCT"
                classified.append(item)
            profile = "+".join(classified)[:160] if classified else "EMPTY"
            profile += "+MORE" if len(tokens) > 20 else ""
            (unknown_set if first == "SET" else other)[profile] += 1
    return unknown_set, other


def print_grammars(prefix: str, data: Counter) -> None:
    for number, (shape, count) in enumerate(data.most_common(12), 1):
        # Only ASCII fixed grammar categories ever reach this output.
        assert re.fullmatch(r"[A-Z0-9_@=,.()+-]{1,170}", shape)
        print(f"{prefix}_{number}={count}:{shape}")



# Redacted control-flow evidence for version-gated SQL. MySQL dump sources
# sometimes embed dynamically PREPAREd statements. Unlike harmless SET
# formatting, the source-only PREPARE/EXECUTE pair may execute schema DDL.
# These counts are forensic signals, never an approval to bypass validation.
_DYNAMIC_SET_IF_RE = re.compile(
    r"^SET\s+@([A-Za-z_][A-Za-z_0-9$]*)\s*=\s*([A-Za-z_][A-Za-z_0-9$]*)"
    r"\s*\(\s*@([A-Za-z_][A-Za-z_0-9$]*)\s*,\s*"
    r"('(?:\\.|''|[^'])*')\s*,\s*('(?:\\.|''|[^'])*')\s*\)$",
    re.I,
)
_PREPARE_FROM_VAR_RE = re.compile(
    r"^PREPARE\s+([A-Za-z_][A-Za-z_0-9$]*)\s+FROM\s+@([A-Za-z_][A-Za-z_0-9$]*)$",
    re.I,
)
_EXECUTE_STMT_RE = re.compile(r"^EXECUTE\s+([A-Za-z_][A-Za-z_0-9$]*)$", re.I)
_DEALLOCATE_STMT_RE = re.compile(
    r"^DEALLOCATE\s+PREPARE\s+([A-Za-z_][A-Za-z_0-9$]*)$", re.I,
)
_BRANCH_VERBS = frozenset(
    "ALTER CREATE DROP SELECT SET UPDATE DELETE INSERT REPLACE "
    "LOCK UNLOCK DO CALL BEGIN COMMIT ROLLBACK TRUNCATE RENAME".split()
)


def _branch_verb(sql_literal: str) -> str:
    # Do not print SQL, raw literal tokens, or identifiers.
    content = sql_literal[1:-1].replace("''", "'")
    head = re.match(r"\s*([A-Za-z_]+)", content)
    keyword = head.group(1).upper() if head else ""
    return keyword if keyword in _BRANCH_VERBS else "OTHER"




def _cross_engine_decimal_default_column(segment: str) -> str:
    """Normalize only a numeric literal DEFAULT on an actual DECIMAL column.

    Other quoted text (including COMMENT content) remains byte-significant.
    """
    head = re.match(r"\s*\x60(?:[^\x60]|\x60\x60)+\x60\s+DECIMAL(?=\s|\()", segment, re.I)
    if not head:
        return segment
    value_re = re.compile(
        r"'(?P<value>-?(?:0|[1-9][0-9]*)\.[0-9]+)'(?=\s|[,)]|$)"
    )
    index = head.end()
    quote = ""
    while index < len(segment):
        char = segment[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                if index + 1 < len(segment) and segment[index + 1] == quote:
                    index += 2
                    continue
                quote = ""
            index += 1
            continue
        if segment.startswith("/*", index):
            end = segment.find("*/", index + 2)
            if end < 0:
                return segment
            index = end + 2
            continue
        if char in "'\"\x60":
            quote = char
            index += 1
            continue
        if (segment[index:index + 7].upper() == "DEFAULT"
                and (index == 0 or not (segment[index - 1].isalnum() or segment[index - 1] == "_"))
                and (index + 7 == len(segment) or not (
                    segment[index + 7].isalnum() or segment[index + 7] == "_"
                ))):
            at = index + 7
            while at < len(segment) and segment[at].isspace():
                at += 1
            literal = value_re.match(segment, at)
            if literal:
                return segment[:at] + literal.group("value") + segment[literal.end():]
        index += 1
    return segment


def _cross_engine_decimal_defaults(sql: str) -> str:
    """Parse CREATE TABLE top-level column clauses; leave unsafe SQL intact."""
    opening = re.match(
        r"^CREATE TABLE\s+(?:IF NOT EXISTS\s+)?"
        r"\x60(?:[^\x60]|\x60\x60)+\x60\s*\(", sql, re.I,
    )
    if not opening:
        return sql
    ranges = []
    column_start = opening.end()
    depth = 1
    quote = ""
    index = column_start
    while index < len(sql):
        char = sql[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    index += 2
                    continue
                quote = ""
            index += 1
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            if end < 0:
                return sql
            index = end + 2
            continue
        if char in "'\"\x60":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                ranges.append((column_start, index))
                break
            if depth < 0:
                return sql
        elif char == "," and depth == 1:
            ranges.append((column_start, index))
            column_start = index + 1
        index += 1
    if depth != 0 or quote:
        return sql
    for start, end in reversed(ranges):
        segment = sql[start:end]
        changed = _cross_engine_decimal_default_column(segment)
        if changed != segment:
            sql = sql[:start] + changed + sql[end:]
    return sql


def proven_create_table_shape(sql: str) -> str:
    """Private-only preflight against the exact *candidate* safe normalizations.

    Unlike probe printouts, this never discards indexes, defaults, constraints,
    actual column charset changes or differing SQL literals.
    """
    table_charset = table_default_charset(sql)
    table_collation = table_default_collation(sql)
    if table_charset and table_collation:
        explicit = re.compile(
            r"(?P<column>\x60[A-Za-z0-9_]+\x60\s+(?:"
            r"TINYTEXT|TEXT|MEDIUMTEXT|LONGTEXT|"
            r"CHAR\([1-9][0-9]{0,4}\)|VARCHAR\([1-9][0-9]{0,4}\)))"
            r"\s*CHARACTER SET (?P<charset>[A-Za-z0-9_]+)"
            r"\s+COLLATE (?P<collation>[A-Za-z0-9_]+)(?=\s|,|\))",
            re.I,
        )
        def inherited(match: re.Match[str]) -> str:
            if (match.group("charset").lower() == table_charset and
                    match.group("collation").lower() == table_collation):
                return match.group("column")
            return match.group(0)
        sql = explicit.sub(inherited, sql)
    numeric = re.compile(
        r"(?P<prefix>\x60[A-Za-z0-9_]+\x60\s+"
        r"(?:TINYINT|SMALLINT|MEDIUMINT|INT|INTEGER|BIGINT|"
        r"DECIMAL|NUMERIC|FLOAT|DOUBLE(?:\s+PRECISION)?)"
        r"(?:\(\s*[0-9]{1,3}(?:\s*,\s*[0-9]{1,3})?\s*\))?"
        r"(?:\s+(?:UNSIGNED|SIGNED|ZEROFILL|NOT NULL|NULL))*"
        r"\s+DEFAULT\s+)"
        r"'(?P<literal>-?(?:0|[1-9][0-9]*)\.[0-9]+)'(?=\s|[,)]|$)",
        re.I,
    )
    sql = numeric.sub(lambda m: m.group("prefix") + m.group("literal"), sql)
    return _cross_engine_decimal_defaults(verify._cross_engine_space(sql))


def dynamic_guard_activity(path: Path) -> tuple[Counter, Counter]:
    activity, branches = Counter(), Counter()
    assigned: set[str] = set()
    prepared: set[str] = set()
    executed: set[str] = set()
    deallocated: set[str] = set()
    prepared_variables: list[str] = []
    with gzip.open(path, "rt", encoding="utf-8", errors="strict") as handle:
        for raw in handle:
            line = raw.strip()
            match = re.fullmatch(r"/\*(?:!|M!)[0-9]{5,6}\s+(.+?)\s*\*/;?", line, re.I)
            if not match:
                continue
            body = match.group(1).strip()
            if _cross_engine_safe_set(line):
                continue
            setting = _DYNAMIC_SET_IF_RE.fullmatch(body)
            if setting:
                activity["SET_IF" if setting.group(2).upper() == "IF" else "SET_OTHER_FUNC"] += 1
                assigned.add(setting.group(1).upper())
                branches[_branch_verb(setting.group(4))] += 1
                branches[_branch_verb(setting.group(5))] += 1
                continue
            prepare = _PREPARE_FROM_VAR_RE.fullmatch(body)
            if prepare:
                activity["PREPARE"] += 1
                prepared.add(prepare.group(1).upper())
                prepared_variables.append(prepare.group(2).upper())
                continue
            execute = _EXECUTE_STMT_RE.fullmatch(body)
            if execute:
                activity["EXECUTE"] += 1
                executed.add(execute.group(1).upper())
                continue
            dealloc = _DEALLOCATE_STMT_RE.fullmatch(body)
            if dealloc:
                activity["DEALLOCATE"] += 1
                deallocated.add(dealloc.group(1).upper())
                continue
            if re.search(r"\bSELECT\b.*\bINFORMATION_SCHEMA\s*\.\s*TABLES\b", body, re.I):
                activity["SELECT_INFO_TABLES"] += 1
    for variable in prepared_variables:
        activity["PREPARE_USES_SET_VAR" if variable in assigned else "PREPARE_OTHER_VAR"] += 1
    if prepared:
        activity["EXECUTE_PAIR_MATCH" if prepared == executed else "EXECUTE_PAIR_DIFF"] += 1
        activity["DEALLOCATE_PAIR_MATCH" if prepared == deallocated else "DEALLOCATE_PAIR_DIFF"] += 1
    return activity, branches


def _cross_engine_safe_set(line: str) -> bool:
    return verify._cross_engine_known_session(line)

def guard_shapes(path: Path) -> tuple[Counter, Counter]:
    unknown_sets, others = Counter(), Counter()
    with gzip.open(path, "rt", encoding="utf-8", errors="strict") as handle:
        for raw in handle:
            line = raw.strip()
            if not line.startswith(("/*!", "/*M!")):
                continue
            matched = re.fullmatch(
                r"/\*(?:!|M!)[0-9]{5,6}\s+(.+?)\s*\*/;?", line, re.I
            )
            if not matched:
                others["UNPARSED"] += 1
                continue
            body = matched.group(1).strip()
            verb = re.match(r"([A-Za-z]+)", body)
            verb = verb.group(1).upper() if verb else "OTHER"
            if verb == "SET":
                if verify._cross_engine_known_session(line):
                    continue
                family = "OTHER"
                for key in GUARD_VARIABLES:
                    if re.search(r"(?<![A-Za-z0-9_])" + key + r"(?![A-Za-z0-9_])", body, re.I):
                        family = key
                        break
                unknown_sets[family] += 1
            elif verb not in {"ALTER", "CREATE", "DROP", "RENAME", "TRUNCATE"}:
                others[verb if verb in SAFE_GUARD_VERBS else "OTHER"] += 1
    return unknown_sets, others


def print_bounded(name: str, values: Counter) -> None:
    print(name + "=" + (" ".join(
        f"{key}:{values[key]}" for key in sorted(values)
        if re.fullmatch(r"[A-Z_]{1,40}", key)
    ) or "NONE"))


def _residual_numeric_location(left: str, right: str) -> tuple[str, str]:
    """Classify an exact isolated numeric change without exposing private SQL."""
    lhs, rhs = TOKEN.findall(left), TOKEN.findall(right)
    if len(lhs) > 20000 or len(rhs) > 20000:
        return "UNPROVEN", "UNKNOWN"
    differences = [
        (op, i0, i1, j0, j1)
        for op, i0, i1, j0, j1 in SequenceMatcher(
            a=lhs, b=rhs, autojunk=False
        ).get_opcodes() if op != "equal"
    ]
    if len(differences) != 1:
        return "MULTIPLE_OR_UNPROVEN", "UNKNOWN"
    op, i0, i1, j0, j1 = differences[0]
    if op != "replace" or i1 - i0 != 1 or j1 - j0 != 1:
        return "NON_NUMERIC_OR_UNPROVEN", "UNKNOWN"
    a, b = lhs[i0], rhs[j0]
    if not (a.isdecimal() and b.isdecimal()):
        return "NON_NUMERIC_OR_UNPROVEN", "UNKNOWN"
    relation = "SOURCE_GREATER" if int(a) > int(b) else (
        "SOURCE_LOWER" if int(a) < int(b) else "EQUAL"
    )

    def footer_start(tokens: list[str]) -> int | None:
        for index in range(len(tokens) - 2):
            if (tokens[index] == ")" and tokens[index + 1].upper() == "ENGINE"
                    and tokens[index + 2] == "="):
                return index + 1
        return None

    src_footer, dst_footer = footer_start(lhs), footer_start(rhs)
    if (src_footer is None or dst_footer is None
            or i0 < src_footer or j0 < dst_footer):
        return "COLUMN_OR_UNPROVEN", relation
    if (i0 < 2 or j0 < 2 or lhs[i0 - 1] != "="
            or rhs[j0 - 1] != "="
            or lhs[i0 - 2].upper() != rhs[j0 - 2].upper()):
        return "TABLE_OPTION_UNPROVEN", relation
    key = lhs[i0 - 2].upper()
    if key == "AUTO_INCREMENT":
        return "TABLE_AUTO_INCREMENT", relation
    if key in {"AVG_ROW_LENGTH", "CHECKSUM", "KEY_BLOCK_SIZE",
               "STATS_SAMPLE_PAGES", "AUTOEXTEND_SIZE", "DELAY_KEY_WRITE"}:
        return "TABLE_OTHER_NUMERIC_OPTION", relation
    return "TABLE_OPTION_UNKNOWN", relation


def summary(a: Path, b: Path) -> None:
    src, sd, sg = parse_dump(a)
    dst, td, tg = parse_dump(b)
    common = sorted(src.keys() & dst.keys())
    print("P07_PRIVATE_SQL_PROBE_V4")
    print(f"CREATE_TABLE_COUNTS={len(src)}:{len(dst)}")
    print(f"CREATE_TABLE_MISSING={len(src.keys() - dst.keys())}:{len(dst.keys() - src.keys())}")
    print(f"DROP_TABLE_COUNTS={len(sd)}:{len(td)}")
    print(f"DROP_TABLE_MISMATCHES={sum(sd.get(k) != td.get(k) for k in sd.keys() | td.keys())}")
    print("GUARD_COUNTS_SOURCE=" + " ".join(f"{k}:{v}" for k, v in sorted(sg.items())))
    print("GUARD_COUNTS_TARGET=" + " ".join(f"{k}:{v}" for k, v in sorted(tg.items())))
    patterns: Counter = Counter()
    charset_status: Counter = Counter()
    charset_types: Counter = Counter()
    default_status: Counter = Counter()
    footer_status: Counter = Counter()
    mismatched = 0
    for name in common:
        src_charset = table_default_charset(src[name])
        dst_charset = table_default_charset(dst[name])
        src_collation = table_default_collation(src[name])
        dst_collation = table_default_collation(dst[name])
        if src_charset and dst_charset:
            footer_status["EQUAL" if src_charset == dst_charset else "DIFFER"] += 1
        else:
            footer_status["UNPROVEN"] += 1
        if src[name] == dst[name]:
            continue
        mismatched += 1
        left = TOKEN.findall(src[name])
        right = TOKEN.findall(dst[name])
        if len(left) > 20000 or len(right) > 20000:
            patterns[("TOO_MANY_TOKENS",)] += 1
            continue
        for op, i0, i1, j0, j1 in SequenceMatcher(
            a=left, b=right, autojunk=False
        ).get_opcodes():
            if op == "equal":
                continue
            lhs_tokens = left[i0:i1]
            rhs_tokens = right[j0:j1]
            if (op == "delete" and len(lhs_tokens) >= 3
                    and lhs_tokens[0].upper() == "CHARACTER"
                    and lhs_tokens[1].upper() == "SET"
                    and re.fullmatch(r"[A-Za-z0-9_]+", lhs_tokens[2])):
                kind = nearest_column_type(left, i0)
                charset_types[kind] += 1
                explicit_collation = (
                    lhs_tokens[4].lower()
                    if len(lhs_tokens) == 5 and lhs_tokens[3].upper() == "COLLATE"
                    and re.fullmatch(r"[A-Za-z0-9_]+", lhs_tokens[4])
                    else None
                )
                if len(lhs_tokens) not in (3, 5) or (len(lhs_tokens) == 5 and not explicit_collation):
                    charset_status["COMPLEX_UNPROVEN"] += 1
                elif kind not in STRING_TYPES or not src_charset or not dst_charset:
                    charset_status["UNPROVEN"] += 1
                elif src_charset != dst_charset or lhs_tokens[2].lower() != src_charset:
                    charset_status["TABLE_OR_EXPLICIT_DIFFER"] += 1
                elif not explicit_collation:
                    # Source collation may be charset default rather than table default.
                    charset_status["COLLATION_UNPROVEN"] += 1
                elif (src_collation and dst_collation and
                        src_collation == dst_collation == explicit_collation):
                    charset_status["EFFECTIVE_CHARSET_COLLATION_EQUAL"] += 1
                else:
                    charset_status["COLLATION_DIFFER_OR_UNPROVEN"] += 1
            if op == "replace" and len(lhs_tokens) == 1 and lhs_tokens[0].startswith("'"):
                literal = lhs_tokens[0][1:-1]
                rhs = "".join(rhs_tokens)
                kind = nearest_column_type(left, i0)
                if (kind in NUMERIC_TYPES and literal == rhs
                        and re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", literal)):
                    default_status["NUMERIC_EXACT"] += 1
                else:
                    default_status["UNPROVEN"] += 1
            context = category(left[i0 - 1]) if i0 else "START"
            lhs = "+".join(category(v) for v in left[i0:min(i1, i0 + 3)]) or "EMPTY"
            rhs = "+".join(category(v) for v in right[j0:min(j1, j0 + 3)]) or "EMPTY"
            patterns[(op.upper(), context, lhs, rhs)] += 1
    proven_equal = 0
    proven_patterns = Counter()
    proven_types = Counter()
    for name in common:
        left = proven_create_table_shape(src[name])
        right = proven_create_table_shape(dst[name])
        if left == right:
            proven_equal += 1
            continue
        lt, rt = TOKEN.findall(left), TOKEN.findall(right)
        if len(lt) > 20000 or len(rt) > 20000:
            proven_patterns["TOO_MANY_TOKENS"] += 1
            continue
        for op, i0, i1, j0, j1 in SequenceMatcher(
            a=lt, b=rt, autojunk=False
        ).get_opcodes():
            if op != "equal":
                proven_types[nearest_column_type(lt, i0)] += 1
                left_type = "+".join(category(v) for v in lt[i0:min(i1, i0 + 3)]) or "EMPTY"
                right_type = "+".join(category(v) for v in rt[j0:min(j1, j0 + 3)]) or "EMPTY"
                proven_patterns[op.upper() + ":" + left_type + ":" + right_type] += 1
    residual_types, residual_orders = Counter(), Counter()
    for name in common:
        left, right = proven_create_table_shape(src[name]), proven_create_table_shape(dst[name])
        if left != right:
            family, order = _residual_numeric_location(left, right)
            residual_types[family] += 1
            residual_orders[order] += 1
    print_bounded("PROVEN_RESIDUAL_LOCATIONS", residual_types)
    print_bounded("PROVEN_RESIDUAL_DIRECTIONS", residual_orders)
    try:
        diagnostic = verify.sql_cross_engine_known_format_diagnostic(a, b)
        data = re.search(r"\bdata=(EQUAL|DIFFER)\(([0-9]+):([0-9]+)\)", diagnostic)
        print("SNAPSHOT_DATA_PARITY=" + (
            f"{data.group(1)}:{data.group(2)}:{data.group(3)}" if data
            else "UNPROVEN"
        ))
    except Exception:
        print("SNAPSHOT_DATA_PARITY=UNAVAILABLE")
    print("PROBE_CANDIDATE_SHA=5468109f24cb44320b2033d0bbc40b5b7e0282f1")
    print(f"PROVEN_CREATE_TABLES_EQUAL={proven_equal}:{len(common)}")
    for number, (pattern, count) in enumerate(proven_patterns.most_common(8), 1):
        print(f"PROVEN_DIFF_{number}={pattern}:{count}")
    print_bounded("PROVEN_REMAINING_COLUMN_TYPES", proven_types)
    print(f"CREATE_TABLE_MISMATCHES={mismatched}:{len(common)}")
    for i, (pattern, count) in enumerate(patterns.most_common(16), 1):
        print(f"DIFF_{i}=" + ":".join(pattern) + f":{count}")
    print_bounded("TABLE_DEFAULT_CHARSET", footer_status)
    print_bounded("EXPLICIT_CHARSET_STATUS", charset_status)
    print_bounded("EXPLICIT_CHARSET_TYPES", charset_types)
    print_bounded("NUMERIC_DEFAULT_STATUS", default_status)
    source_unknown, source_other = guard_shapes(a)
    target_unknown, target_other = guard_shapes(b)
    print_bounded("GUARD_UNKNOWN_SET_SOURCE", source_unknown)
    print_bounded("GUARD_UNKNOWN_SET_TARGET", target_unknown)
    print_bounded("GUARD_OTHER_SOURCE", source_other)
    print_bounded("GUARD_OTHER_TARGET", target_other)
    source_unknown_g, source_other_g = guarded_grammar(a)
    target_unknown_g, target_other_g = guarded_grammar(b)
    print_grammars("UNKNOWN_SET_GRAMMAR_SOURCE", source_unknown_g)
    print_grammars("UNKNOWN_SET_GRAMMAR_TARGET", target_unknown_g)
    print_grammars("OTHER_GUARD_GRAMMAR_SOURCE", source_other_g)
    print_grammars("OTHER_GUARD_GRAMMAR_TARGET", target_other_g)
    for side, dump in (("SOURCE", a), ("TARGET", b)):
        activity, branches = dynamic_guard_activity(dump)
        print_bounded("DYNAMIC_GUARD_ACTIVITY_" + side, activity)
        print_bounded("DYNAMIC_BRANCH_VERBS_" + side, branches)
    print("PROBE_REDACTED=YES")
    print("PROBE_IS_VERIFICATION_PASS=NO")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migration-id", required=True)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    if Path("/opt/vf-server-ops/BUILD_ID").read_text().strip() != "0.1.0-release97":
        print("P07_PROBE_REQUIRES_RELEASE97")
        return 2
    state = migration.load_state(args.migration_id)
    remote = (
        migration.remote_staging_root(state).rstrip("/")
        + "/vfprobe-" + uuid.uuid4().hex + ".sql.gz"
    )
    cleanup_ok = False
    try:
        with tempfile.TemporaryDirectory(prefix="p07-sql-probe-") as path:
            source = Path(path) / "source.sql.gz"
            target = Path(path) / "target.sql.gz"
            migration.source_export_database(state, args.database, remote)
            migration.pull_path(state["source"], remote, source)
            cloudpanel.export_database(args.database, target, clpctl="clpctl")
            summary(source, target)
        return 0
    except Exception:
        print("PROBE_FAILED_NO_SQL_OUTPUT")
        return 3
    finally:
        try:
            cleanup = migration.source_remote(
                state["source"], "rm -f -- " + shlex.quote(remote),
                timeout=60, check=False,
            )
            cleanup_ok = cleanup.returncode == 0
        except Exception:
            pass
        print("SOURCE_TEMP_CLEANUP=" + ("PASS" if cleanup_ok else "CHECK_REQUIRED"))


if __name__ == "__main__":
    raise SystemExit(main())
