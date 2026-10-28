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

def summary(a: Path, b: Path) -> None:
    src, sd, sg = parse_dump(a)
    dst, td, tg = parse_dump(b)
    common = sorted(src.keys() & dst.keys())
    print("P07_PRIVATE_SQL_PROBE_V1")
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
            if (op == "delete" and len(lhs_tokens) == 3
                    and lhs_tokens[0].upper() == "CHARACTER"
                    and lhs_tokens[1].upper() == "SET"
                    and re.fullmatch(r"[A-Za-z0-9_]+", lhs_tokens[2])):
                kind = nearest_column_type(left, i0)
                charset_types[kind] += 1
                if (src_charset and dst_charset
                        and src_charset == dst_charset == lhs_tokens[2].lower()
                        and kind in STRING_TYPES):
                    charset_status["EFFECTIVE_DEFAULT_EQUAL"] += 1
                elif src_charset and dst_charset and src_charset != dst_charset:
                    charset_status["TABLE_DEFAULT_DIFFER"] += 1
                elif src_charset and dst_charset and lhs_tokens[2].lower() != src_charset:
                    charset_status["EXPLICIT_NONDEFAULT"] += 1
                else:
                    charset_status["UNPROVEN"] += 1
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
