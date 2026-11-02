#!/usr/bin/env python3
"""P07 www3: inspect a CREATED, existing quarantine scratch; NO DB writes.

Only create private temporary CP2 copies of source SQL and an export of the
already-existing scratch. Never create/import/overwrite/alter/delete any DB,
site, migration state, receipt, old-VPS source artifact, or DNS.
"""
from __future__ import annotations

import gzip,hashlib,importlib.util,json,os,re,stat,subprocess,sys,tempfile
from pathlib import Path

HELPER_NAME="p07-www3-candidate-schema-probe.py"
STAGE_NAME="p07-www3-isolated-stage.py"
HELPER_BLOB="8f640e7505c5b49ad5a7574d82c0030eb6e7b884"
STAGE_BLOB="8939ff6bd08442a26459a6878d1f94a5c34d000b"

class Block(Exception):pass

def need(ok,why):
    if not ok:raise Block(why)

def load(name,pinned):
    path=Path(__file__).with_name(name)
    need(path.is_file() and not path.is_symlink(),"PINNED_CODE_MISSING")
    data=path.read_bytes()
    digest=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
    need(digest==pinned,"PINNED_CODE_DRIFT")
    spec=importlib.util.spec_from_file_location(
        "p07_existing_scratch_"+name.replace("-","_").replace(".","_"),path
    )
    need(spec is not None and spec.loader is not None,"PINNED_CODE_UNLOADABLE")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_receipt(base,stage,target_server_identity,source_db):
    db,user,_UNUSED_RANDOM_PASSWORD=stage.scratch_name(base,quarantined=True)
    need(db!=source_db,"SCRATCH_COLLIDES_WITH_SOURCE_DB")
    folder=base.BASE/base.TAIL/"target-transactions"
    need(folder.is_dir() and not folder.is_symlink(),
         "SCRATCH_RECEIPT_PARENT_UNPROVEN")
    info=folder.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid()
         and not(info.st_mode&0o077),
         "SCRATCH_RECEIPT_PARENT_UNSAFE")
    identifier=hashlib.sha256(
        (base.TAIL+":"+base.DOMAIN+":"+db).encode()
    ).hexdigest()[:20]
    marker=folder/("www3-hex-scratch-"+identifier+".json")
    need(not marker.is_symlink(),"SCRATCH_RECEIPT_SYMLINK")
    try:
        record_stat=marker.lstat()
        need(stat.S_ISREG(record_stat.st_mode) and record_stat.st_uid==os.getuid()
             and not(record_stat.st_mode&0o077)
             and record_stat.st_nlink==1 and 0<record_stat.st_size<65536,
             "SCRATCH_RECEIPT_UNSAFE")
        record=json.loads(marker.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError):
        raise Block("SCRATCH_RECEIPT_UNAVAILABLE") from None
    need(isinstance(record,dict)
         and record.get("schema")=="p07.www3.quarantined-static-copy.v1"
         and record.get("migration_id")==base.TAIL
         and record.get("domain")==base.DOMAIN
         and record.get("source_database")==source_db
         and record.get("scratch_database")==db
         and record.get("username")==user
         and record.get("target_server_identity")==target_server_identity
         and record.get("status")=="PARITY_UNPROVEN_RETAIN_SCRATCH"
         and record.get("website_activated") is False
         and record.get("original_database_modified") is False
         and record.get("source_runtime_frozen") is False
         and record.get("quarantined_dynamic_groups")==3
         and record.get("quarantined_dynamic_statement_effects")=="UNVERIFIED"
         and isinstance(record.get("password"),str)
         and 16<=len(record["password"])<=1024
         and all(re.fullmatch(r"[a-f0-9]{64}",record.get(k,""))
                 for k in ("source_snapshot_sha256","input_transform_sha256")),
         "SCRATCH_RECEIPT_IDENTITY_OR_STATUS_CHANGED")
    return record

def count_scratch_metadata(stage,record):
    import shutil
    binary=shutil.which("mysql") or shutil.which("mariadb")
    need(binary is not None,"SCRATCH_READONLY_SQL_CLIENT_MISSING")
    db=record["scratch_database"]
    args,env=stage.restricted_user(binary,db,record["username"],record["password"])
    sql=(
        "SELECT "
        "(SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA='"+db+"' AND TABLE_TYPE='BASE TABLE'),"
        "(SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA='"+db+"')"
    )
    try:
        result=subprocess.run(args+[
             "--batch","--skip-column-names","--execute="+sql
        ],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
           stderr=subprocess.DEVNULL,timeout=60,check=False)
    except (OSError,subprocess.SubprocessError):
        raise Block("SCRATCH_METADATA_READ_UNAVAILABLE") from None
    need(result.returncode==0 and len(result.stdout)<128,
         "SCRATCH_METADATA_READ_UNAVAILABLE")
    match=re.fullmatch(rb"([0-9]{1,7})\t([0-9]{1,8})\r?\n?",
                       result.stdout.strip()+b"\n")
    need(match is not None,"SCRATCH_METADATA_FORMAT_UNPROVEN")
    return int(match.group(1)),int(match.group(2))

def inflated_sql_digest(path):
    """SHA256 of actual SQL bytes, not gzip filename / mtime metadata."""
    digest=hashlib.sha256()
    total=0
    try:
        with gzip.open(path,"rb") as source:
            for block in iter(lambda:source.read(1024*1024),b""):
                total+=len(block)
                need(total<1024*1024*1024,
                     "QUARANTINE_SQL_COPY_TOO_LARGE")
                digest.update(block)
    except (OSError,EOFError,gzip.BadGzipFile):
        raise Block("QUARANTINE_SQL_BYTES_UNREADABLE") from None
    need(total>1024,"QUARANTINE_SQL_BYTES_UNVERIFIED")
    return digest.hexdigest(),total


def prove_transformed_copy_without_compressed_header(stage,original,imported,root):
    """Prove two immutable-source transformations yield the same SQL bytes.

    gzip.open(...,"xb") writes variable timestamp/name metadata into the gzip
    header, so its SHA256 isn't reproducible across runs. The historical
    compressed input hash remains recorded but cannot alone prove equality.
    Compare byte-for-byte *decompressed* SQL from two independently generated
    copies, each subject to stage's exact source-line preservation proof.
    """
    first=inflated_sql_digest(imported)
    second=root/"quarantined-independent-rebuild.sql.gz"
    stage.make_quarantined_sql(original,second)
    other=inflated_sql_digest(second)
    need(first==other,"QUARANTINE_REGENERATED_SQL_CONTENT_DRIFT")
    print("QUARANTINE_INFLATED_CONTENT_RECHECK=PASS",flush=True)
    return first


def read_copy_format(path):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size>0,
         "TARGET_SCRATCH_EXPORT_EMPTY")
    with path.open("rb") as file:
        first=file.read(64)
    if first.startswith(b"\x1f\x8b"):
        return "GZIP",path
    # The CloudPanel CLI may export plain SQL even if the requested filename
    # ends with .gz. Point the read-only verifier at an actual .sql copy.
    if first.lstrip().startswith((b"--",b"/*",b"CREATE ",b"SET ")):
        plain=path.with_suffix(".sql")
        need(not os.path.lexists(plain),"EXPORT_FORMAT_COPY_COLLISION")
        import shutil
        shutil.copyfile(path,plain)
        return "PLAIN_SQL",plain
    raise Block("TARGET_SCRATCH_EXPORT_FORMAT_UNPROVEN")

def inspect_target_export_bytes(path,format_name):
    """Validate the WHOLE exported stream; GZIP magic alone is not proof.

    Distinguish gzip trailer/decompression errors from SQL-text UTF-8 errors.
    Only sanitized fixed categories and whole-stream byte count leave CP2.
    This never reads or prints row values, filenames, secrets or SQL fragments.
    """
    import codecs,zlib
    need(format_name in ("GZIP","PLAIN_SQL"),"TARGET_EXPORT_FORMAT_UNKNOWN")
    utf8=codecs.getincrementaldecoder("utf-8")("strict")
    invalid=False
    bytes_seen=0
    reader=gzip.open if format_name=="GZIP" else open
    try:
        with reader(path,"rb") as stream:
            while True:
                block=stream.read(1024*1024)
                if not block:break
                bytes_seen+=len(block)
                need(bytes_seen<=4*1024*1024*1024,
                     "TARGET_DUMP_DECOMPRESSED_SIZE_LIMIT")
                if not invalid:
                    try:utf8.decode(block,final=False)
                    except UnicodeDecodeError:invalid=True
        if not invalid:
            try:utf8.decode(b"",final=True)
            except UnicodeDecodeError:invalid=True
    except EOFError:
        return ("TRUNCATED","UNPROVEN",bytes_seen)
    except gzip.BadGzipFile as error:
        # Never return the exception itself; it can contain bytes of SQL.
        msg=str(error)
        kind=("CRC_FAILED" if "CRC check failed" in msg
              else "SIZE_TRAILER_FAILED" if "Incorrect length" in msg
              else "BAD_GZIP_STREAM")
        return (kind,"UNPROVEN",bytes_seen)
    except zlib.error:
        return ("DEFLATE_INVALID","UNPROVEN",bytes_seen)
    except OSError:
        return ("READ_ERROR","UNPROVEN",bytes_seen)
    need(bytes_seen>0,"TARGET_DUMP_EMPTY_AFTER_DECOMPRESSION")
    return ("PASS","INVALID" if invalid else "VALID",bytes_seen)


def native_readonly_scratch_dump(record,stage,destination):
    """Single read-only MariaDB dump of the existing scratch, with HEX blobs.

    The existing CloudPanel gzip may contain raw non-UTF8 binary data. Never
    change/export from old VPS, never invoke an import, or write into the DB.
    SELECT/transaction only with the root-private receipt's scoped user.
    """
    import shutil
    from pathlib import Path
    db=record["scratch_database"]
    need(re.fullmatch(r"p07[A-Za-z0-9]{11}",db) is not None,
         "NATIVE_DUMP_IDENTITY_UNPROVEN")
    client=shutil.which("mysql") or shutil.which("mariadb")
    dumper=shutil.which("mariadb-dump") or shutil.which("mysqldump")
    if client is None or dumper is None:
        return "CLIENT_UNAVAILABLE"
    # Reuse pre-existing restricted SQL user and its verified database-only
    # SHOW GRANTS; no root SQL account, server admin, or cross-DB privilege.
    try:
        _args,env=stage.restricted_user(
            client,db,record["username"],record["password"]
        )
    except Exception:
        return "RESTRICTED_USER_UNPROVEN"
    need(not os.path.lexists(destination)
         and destination.parent.is_dir()
         and destination.name=="scratch-native-readonly.sql",
         "NATIVE_OUTPUT_PATH_UNSAFE")
    args=[
        dumper,"--no-defaults","--protocol=tcp","--host=127.0.0.1",
        "--user="+record["username"],"--default-character-set=utf8mb4",
        "--single-transaction","--skip-lock-tables","--quick",
        "--hex-blob","--no-tablespaces","--skip-extended-insert",
        "--skip-comments","--skip-dump-date",
        db,
    ]
    # Private plain SQL is ephemeral; only fixed status codes are printed.
    try:
        fd=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"wb") as stream:
            result=subprocess.run(
                args,env=env,stdin=subprocess.DEVNULL,stdout=stream,
                stderr=subprocess.DEVNULL,timeout=1800,check=False
            )
        if result.returncode!=0:return "EXPORT_REJECTED"
        if destination.stat().st_size==0:return "EMPTY_EXPORT"
    except subprocess.TimeoutExpired:
        return "EXPORT_TIMEOUT"
    except (OSError,subprocess.SubprocessError):
        return "EXPORT_UNAVAILABLE"
    return "COMPLETE"


def try_fingerprint(module,name,a,b):
    fun=getattr(module,name,None)
    if not callable(fun):return "UNAVAILABLE"
    try:
        before=fun(a)
        after=fun(b)
    except Exception:
        return "UNPROVEN"
    return "MATCH" if before==after else "DIFFER"

def diagnostic_reason(exc):
    # Never print exception str: it may carry file, DB or private SQL content.
    text=str(exc)
    allowed=(
        "SQL_DUMP_UNREADABLE","NO_COMPARABLE_STATEMENTS",
        "SQL_SCHEMA_UNREADABLE","NO_COMPARABLE_SCHEMA",
        "UNTERMINATED_SCHEMA","CUSTOM_DELIMITER","CONDITIONAL_DDL",
        "MULTILINE_DATA","UNRECOGNIZED_DATA_COMMAND",
        "SQL_CONTENT_UNREADABLE","NO_COMPARABLE_LOGICAL_CONTENT",
        "UNCLASSIFIED_SQL_VERIFICATION","SCHEMA_OR_DATA_MISMATCH",
    )
    for reason in allowed:
        if ("["+reason+"]") in text:return reason
    return "COMPARISON_UNCLASSIFIED"

def bounded_schema_error(error,schema):
    # Only fixed release113 reason codes can leave the private parser.
    if type(error) is schema.AdvisoryDiagnosticUnavailable:
        known={
            "SQL_SCHEMA_STATEMENT_TOO_LARGE",
            "SQL_SCHEMA_STATEMENT_INCOMPLETE",
            "SQL_DUPLICATE_CREATE_TABLE",
            "SQL_DIAGNOSTIC_INPUT_UNAVAILABLE",
        }
        if str(error) in known:return str(error)
    return "OTHER_UNPROVEN"


def conservative_create_heads(path,schema):
    # Identity-only fallback for advisory row diagnostics. Never grants
    # schema or migration equivalence, and never tolerates duplicates.
    names=set()
    for raw in schema._read_lines(path):
        line=raw.strip()
        if not line.upper().startswith("CREATE TABLE "):
            continue
        if len(line)>4096:raise ValueError("CREATE_HEADER_UNPROVEN")
        match=schema._TABLE_NAME.match(line)
        if not match:raise ValueError("CREATE_HEADER_UNPROVEN")
        identity=match.group(1) or match.group(2)
        if identity in names:raise ValueError("DUPLICATE_CREATE_HEADER")
        names.add(identity)
        if len(names)>157:raise ValueError("TOO_MANY_CREATE_HEADERS")
    if len(names)!=157:raise ValueError("CREATE_HEADER_COUNT_UNPROVEN")
    return names


def explain_row_multisets(source,target,schema):
    import sql_row_evidence as tuples
    import sql_multiset_evidence as multiset
    scope="157_FULL_SCHEMA_IDENTITIES"
    try:
        source_tables=set(schema._schema_statements(source)[0])
        target_tables=set(schema._schema_statements(target)[0])
    except Exception:
        try:
            source_tables=conservative_create_heads(source,schema)
            target_tables=conservative_create_heads(target,schema)
            scope="157_CREATE_HEAD_IDENTITIES_ONLY"
        except Exception:
            print("ADVISORY_ROW_SCOPE=UNPROVEN",flush=True)
            return
    if len(source_tables)!=157 or source_tables!=target_tables:
        print("ADVISORY_ROW_SCOPE=UNPROVEN",flush=True)
        return
    print("ADVISORY_ROW_SCOPE="+scope,flush=True)
    for name,func,allowed,fields in (
        ("TUPLES",tuples.diagnostic,
         ("ROW_TUPLES_DIFFER","ROW_TUPLES_EQUAL_NOT_VERIFIED",
          "NO_INSERT_ROWS","UNAVAILABLE"),
         ("source_row_tuples","target_row_tuples",
          "row_count_drift_tables","same_count_content_drift_tables")),
        ("MULTISET",multiset.diagnostic,
         ("ROW_MULTISET_DIFFER","ROW_MULTISET_EQUAL_NOT_VERIFIED",
          "NO_INSERT_ROWS","UNAVAILABLE"),
         ("shared_tuple_instances","source_only_tuple_instances",
          "target_only_tuple_instances","differing_tables")),
    ):
        try:
            result=func(source,target,source_tables,target_tables)
            status=result.get("comparison")
            if status not in allowed: status="UNPROVEN"
            print("ADVISORY_"+name+"_STATUS="+status,flush=True)
            for key in fields:
                n=result.get(key)
                if type(n) is int and 0<=n<=5000000:
                    print("ADVISORY_"+name+"_"+key.upper()+"="+str(n),flush=True)
            changed=result.get("differing_table_ordinals",[])
            if isinstance(changed,list):
                ordinals=[str(item["table_ordinal"]) for item in changed[:20]
                          if isinstance(item,dict)
                          and type(item.get("table_ordinal")) is int
                          and 1<=item["table_ordinal"]<=157]
                print("ADVISORY_"+name+"_DIFFERING_ORDINALS="+
                      (",".join(ordinals) if ordinals else "NONE"),flush=True)
        except Exception:
            print("ADVISORY_"+name+"_STATUS=UNPROVEN",flush=True)



_ATTR_TOKENS = re.compile(
    r"'(?:\\.|''|[^'\\])*'|\"(?:\\.|\"\"|[^\"\\])*\"|"
    r"\`(?:\`\`|[^\`])*\`|[A-Za-z_][A-Za-z_0-9$]*|"
    r"[-+]?[0-9]+(?:\.[0-9]+)?|[^\s]", re.S,
)
_ATTR_TYPE = re.compile(r"^[A-Za-z]+\s*(?:\([^)]*\))?", re.I | re.S)
_ATTR_GROUPS = (
    "NULLABILITY", "DEFAULT", "COLLATION", "CHARSET",
    "COMMENT", "ON_UPDATE", "AUTO_INCREMENT", "UNSIGNED_ZEROFILL",
    "OTHER_OR_UNPARSED",
)


def _column_attribute_delta_groups(source: str, target: str) -> set[str]:
    """Conservative quote-aware attribute categories; not a compatibility gate."""
    def parse(definition: str):
        typ = _ATTR_TYPE.match(definition)
        if typ is None:
            return None
        tokens = _ATTR_TOKENS.findall(definition[typ.end():])
        groups = {name: [] for name in _ATTR_GROUPS if name != "OTHER_OR_UNPARSED"}
        unknown = []

        def consume_value(pos):
            if pos >= len(tokens):
                return pos
            if tokens[pos] == "(":
                depth = 0
                while pos < len(tokens):
                    if tokens[pos] == "(":
                        depth += 1
                    if tokens[pos] == ")":
                        depth -= 1
                    pos += 1
                    if depth == 0:
                        break
                return pos
            pos += 1
            if pos < len(tokens) and tokens[pos] == "(":
                return consume_value(pos)
            return pos

        i = 0
        while i < len(tokens):
            word = tokens[i].upper()
            next_word = tokens[i + 1].upper() if i + 1 < len(tokens) else ""
            category = None
            end = i + 1
            if word == "NOT" and next_word == "NULL":
                category, end = "NULLABILITY", i + 2
            elif word == "NULL":
                category = "NULLABILITY"
            elif word in ("DEFAULT", "COLLATE", "COMMENT", "CHARSET"):
                category = {"COLLATE": "COLLATION", "CHARSET": "CHARSET"}.get(word, word)
                end = consume_value(i + 1) if word == "DEFAULT" else min(i + 2, len(tokens))
            elif word == "CHARACTER" and next_word == "SET":
                category, end = "CHARSET", min(i + 3, len(tokens))
            elif word == "ON" and next_word == "UPDATE":
                category, end = "ON_UPDATE", consume_value(i + 2)
            elif word == "AUTO_INCREMENT":
                category = "AUTO_INCREMENT"
            elif word in ("UNSIGNED", "ZEROFILL"):
                category = "UNSIGNED_ZEROFILL"
            if category is None:
                unknown.append(tokens[i])
            else:
                groups[category].append(tuple(tokens[i:end]))
            i = max(end, i + 1)
        return groups, tuple(unknown)

    a, b = parse(source), parse(target)
    if a is None or b is None:
        return {"OTHER_OR_UNPARSED"}
    changed = {name for name in a[0] if a[0][name] != b[0][name]}
    if a[1] != b[1] or not changed:
        changed.add("OTHER_OR_UNPARSED")
    return changed



def _attribute_detail_categories(source: str, target: str) -> set[str]:
    """More granular risk classification. Never proves SQL compatibility.

    Parsing is deliberately conservative. Unknown SQL, syntactic ambiguity,
    and different evaluated expressions remain unapproved; no values leak.
    """
    def scan(value):
        typ = _ATTR_TYPE.match(value)
        if not typ:
            return None
        tokens = _ATTR_TOKENS.findall(value[typ.end():])
        known = {key: [] for key in _ATTR_GROUPS if key != "OTHER_OR_UNPARSED"}
        unknown = []
        i = 0
        while i < len(tokens):
            head = tokens[i].upper()
            following = tokens[i + 1].upper() if i + 1 < len(tokens) else ""
            category = None
            end = i + 1
            if head == "NOT" and following == "NULL":
                category, end = "NULLABILITY", i + 2
            elif head == "NULL":
                category = "NULLABILITY"
            elif head == "DEFAULT" or head == "ON" and following == "UPDATE":
                category = "DEFAULT" if head == "DEFAULT" else "ON_UPDATE"
                j = i + (1 if head == "DEFAULT" else 2)
                if j < len(tokens):
                    if tokens[j] == "(":
                        depth = 0
                        while j < len(tokens):
                            if tokens[j] == "(":
                                depth += 1
                            elif tokens[j] == ")":
                                depth -= 1
                            j += 1
                            if depth == 0:
                                break
                    else:
                        j += 1
                        if j < len(tokens) and tokens[j] == "(":
                            depth = 0
                            while j < len(tokens):
                                if tokens[j] == "(":
                                    depth += 1
                                elif tokens[j] == ")":
                                    depth -= 1
                                j += 1
                                if depth == 0:
                                    break
                end = j
            elif head in ("COLLATE", "CHARSET", "COMMENT"):
                category = {"COLLATE": "COLLATION"}.get(head, head)
                end = min(i + 2, len(tokens))
            elif head == "CHARACTER" and following == "SET":
                category, end = "CHARSET", min(i + 3, len(tokens))
            elif head == "AUTO_INCREMENT":
                category = "AUTO_INCREMENT"
            elif head in ("UNSIGNED", "ZEROFILL"):
                category = "UNSIGNED_ZEROFILL"
            if category:
                known[category].append(tuple(tokens[i:end]))
            else:
                unknown.append(tokens[i])
            i = max(i + 1, end)
        return known, tuple(unknown)

    left = scan(source)
    right = scan(target)
    if left is None or right is None:
        return {"PARSER_UNPROVEN"}
    l_groups, l_other = left
    r_groups, r_other = right
    result = set()
    if l_other != r_other:
        result.add("UNRECOGNIZED_TOKENS_CHANGED")
    for key in l_groups:
        before = l_groups[key]
        after = r_groups[key]
        if before == after:
            continue
        if len(before) != 1 or len(after) != 1:
            result.add(key + "_PRESENCE_OR_MULTIPLE")
            continue
        a = before[0]
        b = after[0]
        if key in ("DEFAULT", "ON_UPDATE"):
            expr_a, expr_b = a[1 if key == "DEFAULT" else 2:], b[1 if key == "DEFAULT" else 2:]
            if len(expr_a) == len(expr_b) == 1:
                xa, xb = expr_a[0], expr_b[0]
                # Same digits, different quote syntax: not automatically safe.
                numeric = re.compile(r"[-+]?(?:[0-9]+|[0-9]*\.[0-9]+)")
                qa = xa[1:-1] if len(xa) > 1 and xa[0] == xa[-1] == "'" else xa
                qb = xb[1:-1] if len(xb) > 1 and xb[0] == xb[-1] == "'" else xb
                if qa == qb and numeric.fullmatch(qa) and xa != xb:
                    result.add(key + "_NUMERIC_QUOTING_UNPROVEN")
                    continue
            result.add(key + "_EXPRESSION_OR_LITERAL_CHANGED")
        else:
            result.add(key + "_CHANGED")
    if not result and source != target:
        result.add("PRESENTATION_OR_CASE_UNPROVEN")
    return result


_COLLATION_TOKEN = re.compile(
    r"(?:^|\s)(?:COLLATE)\s*=\s*(?P<value>[A-Za-z0-9_]+)(?=\s|;|$)",
    re.I,
)
_COLLATION_RISK_GROUPS = (
    "SOURCE_ONLY", "TARGET_ONLY", "CASE_ONLY",
    "MYSQL0900_TO_UCA1400", "UCA1400_TO_MYSQL0900",
    "SAME_CHARSET_DIFFERENT_RULE", "DIFFERENT_CHARSET",
    "OTHER_OR_UNPROVEN",
)


def _collation_risk_class(source: str, target: str) -> str:
    """Table-suffix risk summary only; no migration approval or SQL output."""
    a = _COLLATION_TOKEN.findall(source)
    b = _COLLATION_TOKEN.findall(target)
    if len(a) > 1 or len(b) > 1:
        return "OTHER_OR_UNPROVEN"
    if not a and b:
        return "TARGET_ONLY"
    if a and not b:
        return "SOURCE_ONLY"
    if not a and not b:
        return "OTHER_OR_UNPROVEN"
    x, y = a[0], b[0]
    if x.lower() == y.lower():
        return "CASE_ONLY" if x != y else "OTHER_OR_UNPROVEN"
    if "0900" in x.lower() and "uca1400" in y.lower():
        return "MYSQL0900_TO_UCA1400"
    if "uca1400" in x.lower() and "0900" in y.lower():
        return "UCA1400_TO_MYSQL0900"
    def charset(value):
        if value.lower().startswith("utf8mb4_"):
            return "utf8mb4"
        if value.lower().startswith("utf8_"):
            return "utf8"
        if value.lower().startswith("latin1_"):
            return "latin1"
        return None
    cx, cy = charset(x), charset(y)
    if cx is None or cy is None:
        return "OTHER_OR_UNPROVEN"
    return "SAME_CHARSET_DIFFERENT_RULE" if cx == cy else "DIFFERENT_CHARSET"


def explain_collation_risk(source, target, evidence):
    """Classify all parsed table option differences, no SQL/table names."""
    from collections import Counter
    try:
        l = evidence._schema_statements(source)[0]
        r = evidence._schema_statements(target)[0]
        if len(l) != 157 or set(l) != set(r):
            raise ValueError("TABLE_SCOPE_UNPROVEN")
        count = Counter()
        ordinals = []
        for index, name in enumerate(sorted(l), 1):
            aa = evidence._split_create_table(l[name])
            bb = evidence._split_create_table(r[name])
            if aa is None or bb is None:
                raise ValueError("SUFFIX_UNPROVEN")
            if aa[2] == bb[2]:
                continue
            option_classes = evidence._table_option_change_classes(aa[2], bb[2])
            if "COLLATION" not in option_classes:
                continue
            count[_collation_risk_class(aa[2], bb[2])] += 1
            ordinals.append(index)
        print("ADVISORY_COLLATION_RISK=CLASSIFIED_NOT_APPROVED", flush=True)
        for label in _COLLATION_RISK_GROUPS:
            print("ADVISORY_COLLATION_" + label + "_TABLES=" + str(count[label]), flush=True)
        print("ADVISORY_COLLATION_CHANGED_TABLE_ORDINALS=" +
              (",".join(map(str, ordinals[:40])) if ordinals else "NONE"), flush=True)
    except Exception:
        print("ADVISORY_COLLATION_RISK=UNPROVEN", flush=True)



def explain_column_change_classes(source,target,evidence):
    """Classify parsed column changes; never approve type/attribute deltas."""
    from collections import Counter
    classes=Counter()
    attribute_classes=Counter()
    detail_classes=Counter()
    ordinals=[]
    try:
        left=evidence._schema_statements(source)[0]
        right=evidence._schema_statements(target)[0]
        if len(left)!=157 or set(left)!=set(right):
            raise ValueError("COLUMN_SCHEMA_IDENTITY_UNPROVEN")
        name_rx=re.compile(
            r"^(?:\x60(?P<q>(?:\x60\x60|[^\x60])+)\x60|(?P<n>[A-Za-z_][A-Za-z0-9_$]*))\s+(?P<rest>.+)$",
            re.I|re.S
        )
        type_rx=re.compile(
            r"^(?P<base>[A-Za-z]+)\s*(?:\((?P<args>[^)]*)\))?",
            re.I|re.S
        )
        def index(statement):
            parts=evidence._split_create_table(statement)
            if parts is None:raise ValueError("COLUMN_SPLIT_UNPROVEN")
            columns={}
            for definition,multiplicity in parts[0].items():
                if multiplicity!=1:raise ValueError("COLUMN_DUPLICATE")
                match=name_rx.match(definition)
                if not match:raise ValueError("COLUMN_NAME_UNPROVEN")
                name=(match.group("q") or match.group("n")).replace("\x60\x60","\x60")
                if name in columns:raise ValueError("COLUMN_DUPLICATE_NAME")
                columns[name]=match.group("rest")
            return columns
        for ordinal,table in enumerate(sorted(left),1):
            if left[table]==right[table]:continue
            a=index(left[table]);b=index(right[table])
            categories=set()
            attribute_categories=set()
            detail_categories=set()
            if set(a)!=set(b):
                categories.add("NAME_SET_CHANGED")
            for col in a.keys() & b.keys():
                if a[col]==b[col]:continue
                x=type_rx.match(a[col]);y=type_rx.match(b[col])
                if not x or not y:
                    categories.add("UNPARSED_COLUMN")
                elif x.group("base").upper()!=y.group("base").upper():
                    categories.add("TYPE_FAMILY_CHANGED")
                elif (x.group("args") or "")!=(y.group("args") or ""):
                    categories.add("TYPE_PARAMETER_CHANGED")
                else:
                    categories.add("ATTRIBUTES_CHANGED")
                    attribute_categories.update(_column_attribute_delta_groups(a[col],b[col]))
                    detail_categories.update(_attribute_detail_categories(a[col],b[col]))
            if categories:
                ordinals.append(ordinal)
                for kind in categories:classes[kind]+=1
                for kind in attribute_categories:attribute_classes[kind]+=1
                for kind in detail_categories:detail_classes[kind]+=1
        print("ADVISORY_COLUMN_CLASSES=CLASSIFIED_NOT_APPROVED",flush=True)
        for name in ("NAME_SET_CHANGED","TYPE_FAMILY_CHANGED",
                     "TYPE_PARAMETER_CHANGED","ATTRIBUTES_CHANGED",
                     "UNPARSED_COLUMN"):
            print("ADVISORY_COLUMN_"+name+"="+str(classes[name]),flush=True)
        for name in _ATTR_GROUPS:
            print("ADVISORY_ATTRIBUTE_"+name+"_TABLES="+str(attribute_classes[name]),flush=True)
        for key in (
            "DEFAULT_NUMERIC_QUOTING_UNPROVEN",
            "DEFAULT_EXPRESSION_OR_LITERAL_CHANGED",
            "DEFAULT_PRESENCE_OR_MULTIPLE",
            "ON_UPDATE_EXPRESSION_OR_LITERAL_CHANGED",
            "ON_UPDATE_PRESENCE_OR_MULTIPLE",
            "UNRECOGNIZED_TOKENS_CHANGED",
            "PRESENTATION_OR_CASE_UNPROVEN",
            "PARSER_UNPROVEN",
        ):
            print("ADVISORY_DETAIL_" + key + "_TABLES=" + str(detail_classes[key]), flush=True)
        print("ADVISORY_COLUMN_CHANGED_TABLE_ORDINALS="+
              (",".join(str(i) for i in ordinals[:40]) if ordinals else "NONE"),
              flush=True)
    except Exception:
        print("ADVISORY_COLUMN_CLASSES=UNPROVEN",flush=True)


def explain_advisory(source,target):
    """Read-only release113 diagnostics; counts are never acceptance proof."""
    import sql_diff_evidence as evidence
    values=None
    try:
        values=evidence.schema_difference_counts(source,target)
    except Exception:
        print("ADVISORY_SCHEMA=UNPROVEN",flush=True)
        for label,path in (("SOURCE",source),("TARGET",target)):
            try:
                table_map,_=evidence._schema_statements(path)
                print("ADVISORY_"+label+"_SCHEMA_PARSER=PARSED",flush=True)
                print("ADVISORY_"+label+"_SCHEMA_TABLES="+
                      str(len(table_map)),flush=True)
            except Exception as error:
                print("ADVISORY_"+label+"_SCHEMA_PARSER="+
                      bounded_schema_error(error,evidence),flush=True)
    else:
        print("ADVISORY_SCHEMA=CLASSIFIED",flush=True)
    import verify
    for label,path in (("SOURCE",source),("TARGET",target)):
        try:
            verify.sql_structure_fingerprint(path)
            state="PARSED"
        except verify.RestoreVerifyError as error:
            reason=str(error)
            state=(
                "CONDITIONAL_DDL" if reason.startswith("conditional SQL DDL")
                else "CUSTOM_DELIMITER" if reason.startswith("custom SQL delimiters")
                else "UNTERMINATED_SCHEMA" if reason.startswith("unterminated SQL schema")
                else "NO_COMPARABLE_SCHEMA" if reason.startswith("no comparable SQL schema")
                else "SCHEMA_PARSE_UNPROVEN"
            )
        except Exception:
            state="SCHEMA_PARSE_UNPROVEN"
        print("ADVISORY_"+label+"_STRUCTURE_PARSER="+state,flush=True)

    if values is not None:
        for name in ("source_tables","target_tables","common_tables",
                     "mismatched_tables","changed_columns","changed_indexes",
                     "changed_options","source_only_tables","target_only_tables",
                     "unclassified_tables",
                     "other_schema_source_only","other_schema_target_only"):
            n=values.get(name)
            if type(n) is int and 0<=n<=5000000:
                print("ADVISORY_"+name.upper()+"="+str(n),flush=True)
        # Existing release113 classifier already distinguishes engine /
        # charset / collation / AUTO_INCREMENT and unparsed suffix changes.
        # Report counters only; these are NEVER compatibility approvals.
        option_classes=values.get("changed_option_classes",{})
        for name in ("ENGINE","CHARSET","COLLATION","AUTO_INCREMENT",
                     "ROW_FORMAT","OTHER_OR_UNPARSED"):
            n=option_classes.get(name)
            if type(n) is int and 0<=n<=157:
                print("ADVISORY_OPTION_"+name+"="+str(n),flush=True)
        auto=values.get("auto_increment_counter_relation",{})
        for name in ("SOURCE_GREATER","TARGET_GREATER","SOURCE_ONLY",
                     "TARGET_ONLY","EQUAL","UNKNOWN_OR_UNPARSED"):
            n=auto.get(name)
            if type(n) is int and 0<=n<=157:
                print("ADVISORY_AUTO_INCREMENT_"+name+"="+str(n),flush=True)
        print("ADVISORY_SCHEMA_DIFF_IS_NOT_COMPATIBILITY_APPROVAL=YES",flush=True)
        explain_column_change_classes(source,target,evidence)
        explain_collation_risk(source,target,evidence)
    try:
        results=evidence.data_content_evidence(source,target)
        value=results.get("comparison")
        allowed=("UNAVAILABLE","NO_DML_STATEMENTS",
                 "FINGERPRINT_EQUAL_NOT_VERIFIED","FINGERPRINT_DIFFER")
        print("ADVISORY_DATA_STATUS="+
              (value if value in allowed else "UNPROVEN"),flush=True)
        if value=="UNAVAILABLE":
            reasons=("MULTILINE_DML_UNPROVEN","DML_COMMAND_UNRECOGNIZED",
                     "NO_COMPARABLE_LOGICAL_CONTENT","DUMP_UNREADABLE",
                     "OTHER_VERIFIER_FAILURE","NONE")
            for part in ("source","target"):
                reason=results.get(part+"_reason")
                if reason not in reasons:reason="UNPROVEN"
                print("ADVISORY_DATA_"+part.upper()+"_REASON="+
                      reason,flush=True)
        for name in ("source_objects","target_objects",
                     "source_dml_statements","target_dml_statements"):
            n=results.get(name)
            if type(n) is int and 0<=n<=5000000:
                print("ADVISORY_DATA_"+name.upper()+"="+str(n),flush=True)
    except Exception:
        print("ADVISORY_DATA_STATUS=UNPROVEN",flush=True)
    explain_row_multisets(source,target,evidence)
    try:
        import sql_pk_conflict_evidence as pk
        report=pk.diagnostic(source,target)
        result=report.get("comparison")
        if result not in ("PK_LITERAL_DIFFER","PK_LITERAL_EQUAL_NOT_VERIFIED",
                          "UNAVAILABLE"):
            result="UNPROVEN"
        print("ADVISORY_PK_STATUS="+result,flush=True)
        for name in ("pk_tables_evaluable","pk_tables_unavailable",
                     "differing_pk_tables","source_only_keys",
                     "target_only_keys","same_key_changed_literals"):
            n=report.get(name)
            if type(n) is int and 0<=n<=5000000:
                print("ADVISORY_PK_"+name.upper()+"="+str(n),flush=True)
    except Exception:
        print("ADVISORY_PK_STATUS=UNPROVEN",flush=True)
    print("ADVISORY_NOT_A_MIGRATION_PASS_GATE=YES",flush=True)


def run():
    need(os.geteuid()==0 and sys.argv[1:]==[
        "--read-only-existing-www3-scratch-parity"
    ],"EXPLICIT_EXISTING_SCRATCH_READONLY_REQUIRED")
    os.umask(0o077)
    base=load(HELPER_NAME,HELPER_BLOB)
    stage=load(STAGE_NAME,STAGE_BLOB)
    tail,source_db=base.verify_state()
    base.verify_current_runtime()
    sys.path.insert(0,str(base.RUNTIME/"lib"))
    import server_migration_pull as engine
    import cloudpanel,verify
    need(engine.target_identity()==tail["target_server_identity"],
         "TARGET_IDENTITY_CHANGED")
    base.inspect_existing_site(base.DOMAIN,source_db)
    record=load_receipt(base,stage,tail["target_server_identity"],source_db)
    print("MODE=WWW3_EXISTING_QUARANTINE_READ_ONLY_PARITY",flush=True)
    print("SCRATCH_RECEIPT=PARITY_UNPROVEN_RETAIN_SCRATCH",flush=True)
    print("DATABASE_CREATE_IMPORT_ALTER_DELETE=NONE",flush=True)
    print("RECEIPT_AND_MIGRATION_STATE_WRITES=NONE",flush=True)
    print("SOURCE_NEW_EXPORT_OR_CLEANUP=NONE",flush=True)
    print("QUARANTINED_DYNAMIC_EFFECTS=NOT_PROVEN",flush=True)
    print("WEBSITE_ACTIVATION=PROHIBITED",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    db=record["scratch_database"]
    tables,columns=count_scratch_metadata(stage,record)
    print("SCRATCH_READONLY_TABLES="+str(tables),flush=True)
    print("SCRATCH_READONLY_COLUMNS="+str(columns),flush=True)
    with tempfile.TemporaryDirectory(prefix="p07-www3-existing-parity-",dir="/root") as td:
        root=Path(td)
        original=root/"old.sql.gz"
        sha=stage.import_existing_verified_source(engine,tail,source_db,base,original)
        need(sha==record["source_snapshot_sha256"],
             "SOURCE_ARCHIVE_RECEIPT_MISMATCH")
        imported=root/"quarantined.sql.gz"
        transformed_sha=stage.make_quarantined_sql(original,imported)
        print("QUARANTINE_COMPRESSED_RECEIPT_HASH="+(
              "MATCH" if transformed_sha==record["input_transform_sha256"]
              else "NOT_REPRODUCIBLE"),flush=True)
        # The historical receipt pinned the compressed bytes, but the
        # original gzip writer included a nonconstant header timestamp.
        # Preserve that observation without claiming the original snapshot
        # equals this reconstruction; independently prove regenerated SQL
        # bytes and compare them to the existing DB below.
        prove_transformed_copy_without_compressed_header(
            stage,original,imported,root
        )
        stage.strict_scope(imported,quarantined=True)
        target=root/"target-export.sql.gz"
        try:
            cloudpanel.export_database(db,target)
        except Exception:
            print("SCRATCH_EXPORT_READONLY=FAILED",flush=True)
            print("SCRATCH_PARITY_CLASS=EXPORT_UNAVAILABLE",flush=True)
            return 13
        print("SCRATCH_EXPORT_READONLY=COMPLETE",flush=True)
        format_name,compare_path=read_copy_format(target)
        print("SCRATCH_EXPORT_FORMAT="+format_name,flush=True)
        stream_status,utf8_status,uncompressed_bytes=inspect_target_export_bytes(
            compare_path,format_name
        )
        print("TARGET_EXPORT_STREAM_INTEGRITY="+stream_status,flush=True)
        print("TARGET_EXPORT_UTF8="+utf8_status,flush=True)
        print("TARGET_EXPORT_SQL_BYTES="+str(uncompressed_bytes),flush=True)
        if stream_status!="PASS" or utf8_status!="VALID":
            print("NATIVE_SCRATCH_FALLBACK=READONLY_HEX_BLOB",flush=True)
            alternative=root/"scratch-native-readonly.sql"
            native_status=native_readonly_scratch_dump(record,stage,alternative)
            print("NATIVE_SCRATCH_EXPORT="+native_status,flush=True)
            if native_status=="COMPLETE":
                normalized_status,native_utf8,native_bytes=inspect_target_export_bytes(
                    alternative,"PLAIN_SQL"
                )
                print("NATIVE_SCRATCH_UTF8="+native_utf8,flush=True)
                print("NATIVE_SCRATCH_SQL_BYTES="+str(native_bytes),flush=True)
                if normalized_status=="PASS" and native_utf8=="VALID":
                    compare_path=alternative
                    print("TARGET_COMPARE_INPUT=NATIVE_SCRATCH_READONLY_DUMP",flush=True)
                else:
                    print("SCRATCH_PARITY_CLASS=NATIVE_EXPORT_ENCODING_UNPROVEN",flush=True)
                    print("SCRATCH_STATIC_COPY_PARITY=NOT_PROVEN",flush=True)
                    return 13
            else:
                print("SCRATCH_PARITY_CLASS="+(
                    "TARGET_EXPORT_BINARY_UNPROVEN" if stream_status!="PASS"
                    else "TARGET_EXPORT_UTF8_UNPROVEN"),flush=True)
                print("SCRATCH_STATIC_COPY_PARITY=NOT_PROVEN",flush=True)
                return 13
        else:
            print("TARGET_COMPARE_INPUT=CLOUDPANEL_GZIP",flush=True)
        explain_advisory(imported,compare_path)
        for label,fun in (
            ("STRUCTURE","sql_structure_fingerprint"),
            ("DATA","sql_data_fingerprint"),
            ("EXACT_SQL","sql_fingerprint"),
        ):
            print("SCRATCH_"+label+"_FINGERPRINT="+
                  try_fingerprint(verify,fun,imported,compare_path),flush=True)
        try:
            mode=engine.compare_database_dumps(imported,compare_path)
        except Exception as error:
            print("SCRATCH_PARITY_CLASS="+diagnostic_reason(error),flush=True)
            print("SCRATCH_STATIC_COPY_PARITY=NOT_PROVEN",flush=True)
            return 13
        allowed={
            "CANONICAL_SQL_EXACT","CROSS_ENGINE_GUARDED_SESSION_SQL_EXACT",
            "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT","CROSS_ENGINE_LOGICAL_CONTENT"
        }
        need(mode in allowed,"SCRATCH_PARITY_MODE_UNRECOGNIZED")
        print("SCRATCH_STATIC_COPY_PARITY=READONLY_MATCH",flush=True)
        print("SCRATCH_ORIGINAL_COMPRESSED_INPUT_EQUALITY="+(
             "NOT_PROVEN" if transformed_sha!=record["input_transform_sha256"]
             else "MATCH"),flush=True)
        print("SCRATCH_FULL_SOURCE_EQUIVALENCE=NOT_PROVEN",flush=True)
        return 0

if __name__=="__main__":
    try:raise SystemExit(run())
    except Exception as exc:
        value=str(exc) if type(exc) is Block else "READONLY_PARITY_DIAGNOSTIC_UNPROVEN"
        print("BLOCKED="+value,flush=True)
        print("DATABASE_CREATE_IMPORT_ALTER_DELETE=NONE",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
