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


def native_readonly_scratch_dump(record,stage,destination, *, schema_only=False):
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
    if schema_only:
        args.insert(-1,"--no-data")
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
    r"0[xX][0-9a-fA-F]+|[-+]?[0-9]+(?:\.[0-9]+)?|[^\s]", re.S,
)
_ATTR_GROUPS = (
    "NULLABILITY", "DEFAULT", "COLLATION", "CHARSET",
    "COMMENT", "ON_UPDATE", "AUTO_INCREMENT", "UNSIGNED_ZEROFILL",
    "OTHER_OR_UNPARSED",
)


def _attribute_scan(definition):
    """Lossless token grouping for evidence; never execute or rewrite SQL."""
    tokens = _ATTR_TOKENS.findall(definition)
    if not tokens or not re.fullmatch(r"[A-Za-z]+", tokens[0]):
        return None
    if any(t in ("'", '"', "`") for t in tokens):
        return None

    def parens(pos):
        depth = 0
        for end in range(pos, len(tokens)):
            if tokens[end] == "(": depth += 1
            elif tokens[end] == ")": depth -= 1
            if depth == 0: return end + 1
        raise ValueError("UNBALANCED_ATTRIBUTE")

    try:
        start = 1
        if tokens[0].upper() == "DOUBLE" and len(tokens) > 1 and tokens[1].upper() == "PRECISION":
            start = 2
        if start < len(tokens) and tokens[start] == "(": start = parens(start)
        typ = tuple(t.upper() if re.fullmatch(r"[A-Za-z]+", t) else t
                    for t in tokens[:start])
        groups = {k: [] for k in _ATTR_GROUPS if k != "OTHER_OR_UNPARSED"}
        unknown = []

        def value(pos):
            if pos >= len(tokens): raise ValueError("MISSING_ATTRIBUTE_VALUE")
            if tokens[pos] == "(": return parens(pos)
            end = pos + 1
            # Charset, national, hex and bit introducers belong to the literal.
            if (re.fullmatch(r"_[A-Za-z][A-Za-z0-9_]*|[nNbBxX]", tokens[pos])
                    and end < len(tokens) and tokens[end].startswith("'")):
                return end + 1
            if end < len(tokens) and tokens[end] == "(": return parens(end)
            return end

        i = start
        while i < len(tokens):
            word = tokens[i].upper()
            nxt = tokens[i+1].upper() if i+1 < len(tokens) else ""
            category, end = None, i+1
            if word == "NOT" and nxt == "NULL": category, end = "NULLABILITY", i+2
            elif word == "NULL": category = "NULLABILITY"
            elif word in ("DEFAULT", "COLLATE", "COMMENT", "CHARSET"):
                category = {"COLLATE": "COLLATION"}.get(word, word)
                end = value(i+1)
            elif word == "CHARACTER" and nxt == "SET":
                category, end = "CHARSET", value(i+2)
            elif word == "ON" and nxt == "UPDATE":
                category, end = "ON_UPDATE", value(i+2)
            elif word == "AUTO_INCREMENT": category = "AUTO_INCREMENT"
            elif word in ("SIGNED", "UNSIGNED", "ZEROFILL"): category = "UNSIGNED_ZEROFILL"
            if category: groups[category].append(tuple(tokens[i:end]))
            else: unknown.append(tokens[i])
            i = end
        return typ, groups, tuple(unknown)
    except ValueError:
        return None


def _column_attribute_delta_groups(source, target):
    a, b = _attribute_scan(source), _attribute_scan(target)
    if a is None or b is None or a[0] != b[0]: return {"OTHER_OR_UNPARSED"}
    changed = {k for k in a[1] if a[1][k] != b[1][k]}
    if a[2] != b[2] or not changed: changed.add("OTHER_OR_UNPARSED")
    return changed


def _time_default_key(expr):
    text = "".join(expr).upper()
    match = re.fullmatch(r"(CURRENT_TIMESTAMP|LOCALTIME|LOCALTIMESTAMP)(?:\(([0-6]?)\))?", text)
    if match: return int(match.group(2) or 0)
    match = re.fullmatch(r"NOW\(([0-6]?)\)", text)
    return int(match.group(1) or 0) if match else None


def _decode_sql_literal(text):
    """Decode one bounded single-quoted literal in memory, never evaluate SQL.

    Return unknown on nonstandard escapes. The decoder establishes lexical
    bytes only; connection charset, SQL mode and default behavior stay gated.
    """
    if not isinstance(text,str) or len(text)>65536 or not re.fullmatch(r"'(?:\\.|''|[^'\\])*'",text,re.S):
        return None
    out=[]; i=1
    escapes={"0":"\x00","b":"\b","n":"\n","r":"\r","t":"\t","Z":"\x1a","'":"'",'"':'"',"\\":"\\"}
    while i<len(text)-1:
        c=text[i]
        if c=="'" and text[i+1:i+2]=="'":out.append("'");i+=2
        elif c=="\\":
            if text[i+1] not in escapes:return None
            out.append(escapes[text[i+1]]);i+=2
        else:out.append(c);i+=1
    return "".join(out)


def _scalar_default(expr):
    """Recognize only wrapped literals; no functions/casts/operators execute."""
    tokens=tuple(expr);wrappers=0
    while len(tokens)>2 and tokens[0]=="(" and tokens[-1]==")":
        depth=0;end=None
        for i,t in enumerate(tokens):
            if t=="(":depth+=1
            elif t==")":depth-=1
            if depth==0:end=i;break
        if end!=len(tokens)-1 or wrappers>=8:break
        tokens=tokens[1:-1];wrappers+=1
    prefix=""
    if len(tokens)==2 and re.fullmatch(r"_[A-Za-z][A-Za-z0-9_]*|[nNbBxX]",tokens[0]):
        prefix=tokens[0].lower();tokens=tokens[1:]
    if len(tokens)!=1:return {"kind":"EXPRESSION","wrappers":wrappers,"prefix":prefix,"value":None}
    token=tokens[0];kind="UNKNOWN";value=None
    if prefix=="x":
        if re.fullmatch(r"'(?:[0-9A-Fa-f]{2})*'",token):
            kind="HEX_STRING";value=bytes.fromhex(token[1:-1])
        return {"kind":kind,"wrappers":wrappers,"prefix":prefix,"value":value}
    if prefix=="b":
        return {"kind":"BIT_LITERAL","wrappers":wrappers,"prefix":prefix,"value":None}
    if token.upper()=="NULL" and not prefix:kind="NULL";value="NULL"
    elif re.fullmatch(r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?",token) and not prefix:
        from decimal import Decimal
        kind="NUMBER";value=Decimal(token)
    elif re.fullmatch(r"0[xX][0-9a-fA-F]+",token) and not prefix:
        kind="HEX";value=token[2:].lower()
    else:
        decoded=_decode_sql_literal(token)
        if decoded is not None:kind="STRING";value=decoded
    return {"kind":kind,"wrappers":wrappers,"prefix":prefix,"value":value}


def _default_resolution(source,target):
    """Safe structured detail; never return default literals or identifiers."""
    a,b=_attribute_scan(source),_attribute_scan(target)
    if a is None or b is None or a[0]!=b[0]:return {"relation":"PARSER_UNPROVEN"}
    x,y=a[1]["DEFAULT"],b[1]["DEFAULT"]
    if len(x)!=1 or len(y)!=1:return {"relation":"PRESENCE_UNPROVEN"}
    x,y=_scalar_default(x[0][1:]),_scalar_default(y[0][1:])
    prefixes={"","_utf8","_utf8mb3","_utf8mb4","_ascii","_latin1","_binary","n","b","x"}
    result={"source_kind":x["kind"],"target_kind":y["kind"],
            "source_wrappers":x["wrappers"],"target_wrappers":y["wrappers"],
            "source_prefix":x["prefix"] if x["prefix"] in prefixes else "OTHER_UNPROVEN",
            "target_prefix":y["prefix"] if y["prefix"] in prefixes else "OTHER_UNPROVEN"}
    string_types={"CHAR","VARCHAR","BINARY","VARBINARY","TINYTEXT","TEXT","MEDIUMTEXT","LONGTEXT","TINYBLOB","BLOB","MEDIUMBLOB","LONGBLOB"}
    if {x["kind"],y["kind"]}=={"STRING","HEX_STRING"}:
        plain=x if x["kind"]=="STRING" else y
        binary=y if y["kind"]=="HEX_STRING" else x
        if a[0][0] not in string_types or plain["prefix"] not in ("","_ascii","_binary","_utf8","_utf8mb3","_utf8mb4") or not plain["value"].isascii():
            relation="HEX_STRING_CHARSET_OR_TYPE_UNPROVEN"
        else:
            relation="EQUAL_ASCII_HEX_BYTES" if plain["value"].encode("ascii")==binary["value"] else "HEX_STRING_BYTES_DIFFER"
    elif x["value"] is None or y["value"] is None:relation="EXPRESSION_UNPROVEN"
    elif x["kind"]!=y["kind"]:relation="KIND_CHANGED_UNPROVEN"
    elif x["value"]!=y["value"]:relation="LITERAL_VALUE_DIFFER"
    elif x["prefix"]!=y["prefix"]:relation="EQUAL_LITERAL_CHARSET_CONTEXT_REQUIRED"
    elif x["wrappers"]!=y["wrappers"]:relation="EQUAL_LITERAL_PARENTHESES_ONLY"
    else:relation="EQUAL_LITERAL_SPELLING_ONLY"
    result["relation"]=relation
    if x["kind"]==y["kind"]=="STRING" and x["value"] is not None and y["value"] is not None:
        result["both_empty"]=x["value"]==y["value"]==""
        result["both_ascii"]=x["value"].isascii() and y["value"].isascii()
    return result


def _literal_parts(expr):
    if len(expr) == 1 and re.fullmatch(r"'(?:\\.|''|[^'\\])*'", expr[0], re.S):
        return "", expr[0]
    if (len(expr) == 2 and re.fullmatch(r"_[A-Za-z][A-Za-z0-9_]*|[nNbBxX]", expr[0])
            and re.fullmatch(r"'(?:\\.|''|[^'\\])*'", expr[1], re.S)):
        return expr[0].lower(), expr[1]
    return None


def _attribute_detail_categories(source, target):
    left, right = _attribute_scan(source), _attribute_scan(target)
    if left is None or right is None or left[0] != right[0]: return {"PARSER_UNPROVEN"}
    result = set()
    if left[2] != right[2]: result.add("UNRECOGNIZED_TOKENS_CHANGED")
    for key in left[1]:
        before, after = left[1][key], right[1][key]
        if before == after: continue
        if len(before) != 1 or len(after) != 1:
            nullable_lob = (left[0][0] in ("TINYTEXT", "TEXT", "MEDIUMTEXT", "LONGTEXT",
                            "TINYBLOB", "BLOB", "MEDIUMBLOB", "LONGBLOB")
                and not left[2] and not right[2]
                and all(not any("NOT" in (t.upper() for t in item) for item in side[1]["NULLABILITY"])
                        and not side[1]["AUTO_INCREMENT"] for side in (left, right)))
            normalized = [tuple(t.upper() for t in entry) for entry in (before or after)]
            if key == "DEFAULT" and nullable_lob and (not before or not after) and normalized == [("DEFAULT", "NULL")]:
                result.add("DEFAULT_NULLABLE_LOB_NULL_PRESENTATION")
            else: result.add(key + "_PRESENCE_OR_MULTIPLE")
            continue
        if key not in ("DEFAULT", "ON_UPDATE"):
            result.add(key + "_CHANGED")
            continue
        offset = 1 if key == "DEFAULT" else 2
        a, b = before[0][offset:], after[0][offset:]
        if left[0][0] in ("TIMESTAMP", "DATETIME"):
            ta, tb = _time_default_key(a), _time_default_key(b)
            if ta is not None and tb is not None and ta == tb:
                result.add(key + "_TIMESTAMP_SYNTAX_ONLY")
                continue
        la, lb = _literal_parts(a), _literal_parts(b)
        if la and lb and la[1] == lb[1] and la[0] != lb[0]:
            result.add(key + "_LITERAL_INTRODUCER_REQUIRES_CHARSET_PROOF")
            continue
        if len(a) == len(b) == 1:
            xa, xb = a[0], b[0]
            qa = xa[1:-1] if len(xa)>1 and xa[0]==xa[-1]=="'" else xa
            qb = xb[1:-1] if len(xb)>1 and xb[0]==xb[-1]=="'" else xb
            if qa == qb and re.fullmatch(r"[-+]?(?:[0-9]+|[0-9]*\.[0-9]+)", qa) and xa != xb:
                result.add(key + "_NUMERIC_QUOTING_UNPROVEN")
                continue
        result.add(key + "_EXPRESSION_OR_LITERAL_CHANGED")
    if not result and source != target: result.add("PRESENTATION_OR_CASE_UNPROVEN")
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
        target_defaults = Counter()
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
            # Only known public collation names may leave this process.
            known = {"utf8mb4_general_ci", "utf8mb4_unicode_ci", "utf8mb4_bin",
                     "utf8mb4_0900_ai_ci", "utf8mb4_0900_as_cs", "utf8mb4_0900_bin",
                     "utf8mb4_uca1400_ai_ci", "utf8mb4_uca1400_nopad_ai_ci",
                     "utf8mb3_general_ci", "utf8_general_ci", "latin1_swedish_ci"}
            target_value = _COLLATION_TOKEN.findall(bb[2])
            label = target_value[0].lower() if len(target_value) == 1 else ""
            target_defaults[label if label in known else "OTHER_UNPROVEN"] += 1
            ordinals.append(index)
        print("ADVISORY_COLLATION_RISK=CLASSIFIED_NOT_APPROVED", flush=True)
        for label in _COLLATION_RISK_GROUPS:
            print("ADVISORY_COLLATION_" + label + "_TABLES=" + str(count[label]), flush=True)
        for label in sorted(target_defaults):
            print("ADVISORY_COLLATION_TARGET_NAME_" + label.upper() + "_TABLES=" +
                  str(target_defaults[label]), flush=True)
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
    detail_records=[]
    try:
        left=evidence._schema_statements(source)[0]
        right=evidence._schema_statements(target)[0]
        if len(left)!=157 or set(left)!=set(right):
            raise ValueError("COLUMN_SCHEMA_IDENTITY_UNPROVEN")
        name_rx=re.compile(
            r"^(?:\x60(?P<q>(?:\x60\x60|[^\x60])+)\x60|(?P<n>[A-Za-z_][A-Za-z0-9_$]*))\s+(?P<rest>.+)$",
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
            for column_ordinal,col in enumerate(a,1):
                if col not in b:continue
                if a[col]==b[col]:continue
                x=_attribute_scan(a[col]);y=_attribute_scan(b[col])
                if not x or not y:
                    categories.add("UNPARSED_COLUMN")
                elif x[0][0]!=y[0][0]:
                    categories.add("TYPE_FAMILY_CHANGED")
                elif x[0]!=y[0]:
                    categories.add("TYPE_PARAMETER_CHANGED")
                else:
                    categories.add("ATTRIBUTES_CHANGED")
                    attribute_categories.update(_column_attribute_delta_groups(a[col],b[col]))
                    delta=_attribute_detail_categories(a[col],b[col])
                    detail_categories.update(delta)
                    detail_records.append((ordinal,column_ordinal,sorted(delta)))
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
            "DEFAULT_TIMESTAMP_SYNTAX_ONLY",
            "ON_UPDATE_TIMESTAMP_SYNTAX_ONLY",
            "DEFAULT_NULLABLE_LOB_NULL_PRESENTATION",
            "DEFAULT_LITERAL_INTRODUCER_REQUIRES_CHARSET_PROOF",
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
        for i,(table,column,details) in enumerate(detail_records[:100],1):
            print("ADVISORY_COLUMN_DETAIL_"+str(i)+"="+str(table)+":"+str(column)+":"+
                  ",".join(details),flush=True)
        print("ADVISORY_COLUMN_DETAIL_TRUNCATED="+
              ("YES" if len(detail_records)>100 else "NO"),flush=True)
    except Exception:
        print("ADVISORY_COLUMN_CLASSES=UNPROVEN",flush=True)


def _pk_literal_identity_report(source, target):
    """Separate SQL-literal evidence across attribute drift; never a gate.

    Keep the installed strict PK diagnostic unchanged. Require identical
    ordered columns, explicit full PK, types, signedness and index definitions.
    DEFAULT/ON UPDATE differences remain independent schema blockers.
    """
    from collections import Counter
    import sql_diff_evidence as schema
    import sql_pk_conflict_evidence as pk
    try:
        ls, _ = schema._schema_statements(source)
        rs, _ = schema._schema_statements(target)
        if not ls or set(ls) != set(rs): raise ValueError("SCOPE")
        eligible, denied = {}, Counter()
        drift = 0
        for name in sorted(ls):
            a, b = schema._split_create_table(ls[name]), schema._split_create_table(rs[name])
            if not a or not b or a[1] != b[1]:
                denied["INDEX_OR_PARSE"] += 1
                continue
            ka, kb = pk._pk_schema(ls[name]), pk._pk_schema(rs[name])
            if ka is None or kb is None or ka != kb:
                denied["PK_OR_COLUMN_IDENTITY"] += 1
                continue
            def signatures(columns):
                out = []
                for column, count in columns.items():
                    head = pk._DEF.match(column)
                    if count != 1 or head is None: raise ValueError("COLUMN")
                    parsed = _attribute_scan(column[head.end():])
                    if parsed is None: raise ValueError("TYPE")
                    out.append((parsed[0], parsed[1]["UNSIGNED_ZEROFILL"]))
                return out
            if signatures(a[0]) != signatures(b[0]):
                denied["TYPE_OR_SIGNEDNESS"] += 1
                continue
            eligible[name] = ka
            drift += a[0] != b[0] or a[2] != b[2]
        left, right = pk._rows(source, eligible), pk._rows(target, eligible)
        totals = Counter()
        for name in eligible:
            a, b = left[name], right[name]
            shared = a.keys() & b.keys()
            changed = sum(a[k] != b[k] for k in shared)
            only_a, only_b = len(a.keys()-b.keys()), len(b.keys()-a.keys())
            totals["SOURCE_ONLY_KEYS"] += only_a
            totals["TARGET_ONLY_KEYS"] += only_b
            totals["SAME_KEY_CHANGED_LITERALS"] += changed
            totals["IDENTICAL_ROWS"] += len(shared)-changed
            totals["DIFFERING_TABLES"] += bool(changed or only_a or only_b)
        return {"STATUS": "LITERAL_DIFFER" if totals["DIFFERING_TABLES"] else
                "LITERAL_EQUAL_NOT_VERIFIED" if eligible else "UNPROVEN",
                "TABLES_EXAMINED": len(ls), "TABLES_EVALUABLE": len(eligible),
                "TABLES_UNAVAILABLE": sum(denied.values()),
                "SCHEMA_DRIFT_TABLES_STILL_BLOCKED": drift,
                **{k: totals[k] for k in ("SOURCE_ONLY_KEYS", "TARGET_ONLY_KEYS",
                   "SAME_KEY_CHANGED_LITERALS", "IDENTICAL_ROWS", "DIFFERING_TABLES")},
                **{"DENIED_"+k: denied[k] for k in
                   ("INDEX_OR_PARSE", "PK_OR_COLUMN_IDENTITY", "TYPE_OR_SIGNEDNESS")}}
    except Exception:
        return {"STATUS": "UNPROVEN"}


def explain_pk_literal_identity(source, target):
    for key, value in _pk_literal_identity_report(source, target).items():
        print("ADVISORY_PK_IDENTITY_"+key+"="+str(value), flush=True)
    print("ADVISORY_PK_IDENTITY_SEMANTICS=DUMP_LITERALS_ONLY_NO_SCHEMA_APPROVAL", flush=True)


def explain_conditional_ddl(source, target):
    """Expose the exact known key-toggle shape, never waive conditional DDL."""
    from collections import Counter
    import sql_diff_evidence as evidence
    rx = re.compile(r"/\*!40000\s+ALTER\s+TABLE\s+`(?P<table>[A-Za-z0-9_$.-]+)`\s+"
                    r"(?P<action>DISABLE|ENABLE)\s+KEYS\s*\*/;", re.I)
    summaries = []
    try:
        for label, path in (("SOURCE", source), ("TARGET", target)):
            toggles, unknown = Counter(), 0
            tables = set(evidence._schema_statements(path)[0])
            for raw in evidence._read_lines(path):
                line = raw.strip()
                if not line.startswith(("/*!", "/*M!")): continue
                match = rx.fullmatch(line)
                if match and match.group("table") in tables:
                    toggles[(match.group("table"), match.group("action").upper())] += 1
                elif re.search(r"\b(?:CREATE|ALTER|DROP|RENAME|TRUNCATE|TRIGGER|INDEX|EVENT|PROCEDURE|FUNCTION|VIEW)\b", line, re.I):
                    unknown += 1
            paired = sum(toggles[(t,"DISABLE")] == toggles[(t,"ENABLE")] == 1 for t in tables)
            unmatched = sum(toggles.values()) - paired*2
            summaries.append((toggles, unknown))
            for key, value in (("KEY_TOGGLE_PAIRS", paired), ("UNPAIRED_TOGGLES", unmatched),
                               ("OTHER_DDL_LINES", unknown)):
                print("ADVISORY_CONDITIONAL_"+label+"_"+key+"="+str(value), flush=True)
        print("ADVISORY_CONDITIONAL_TOGGLE_IDENTITY="+
              ("UNKNOWN_DDL_PRESENT" if any(item[1] for item in summaries) else
               "MATCH_NOT_APPROVED" if summaries[0][0] == summaries[1][0] else "DIFFER"), flush=True)
    except Exception:
        print("ADVISORY_CONDITIONAL_CLASS=UNPROVEN", flush=True)


def _redacted_branch_shape(literal):
    """Fixed public vocabulary only; private literals/names stay redacted."""
    if not isinstance(literal,str) or len(literal)>4096: return "UNPROVEN"
    body = _decode_sql_literal(literal)
    if body is None:return "LITERAL_ESCAPE_UNPROVEN"
    tokens = _ATTR_TOKENS.findall(body)
    words = set("SET SELECT SESSION GLOBAL PERSIST PERSIST_ONLY NAMES COLLATE FROM DUAL COUNT INTO WHERE AND OR IF NULL TRUE FALSE ON OFF SQL_MODE SQL_NOTES TIME_ZONE CHARACTER_SET_CLIENT CHARACTER_SET_RESULTS COLLATION_CONNECTION FOREIGN_KEY_CHECKS UNIQUE_CHECKS AUTOCOMMIT SQL_SAFE_UPDATES MAX_EXECUTION_TIME SQL_LOG_BIN GTID_PURGED INFORMATION_SCHEMA PERFORMANCE_SCHEMA TABLES TABLE_SCHEMA TABLE_NAME INNODB_TABLES INNODB_TABLESPACES SESSION_VARIABLES VARIABLE_NAME ROCKSDB_BULK_LOAD SQL_REQUIRE_PRIMARY_KEY SQL_GENERATE_INVISIBLE_PRIMARY_KEY SQL_AUTO_IS_NULL UNIQUE_CHECKS CHECK_CONSTRAINT_CHECKS MAX_STATEMENT_TIME OPTIMIZER_SWITCH".split())
    parts = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.startswith("`") and t.endswith("`"):t=t[1:-1].replace("``","`")
        if t == "@":
            is_system = i+1 < len(tokens) and tokens[i+1] == "@"
            i += 2 if is_system else 1
            label = "SYSTEM_VAR" if is_system else "USER_VAR"
            if i < len(tokens):
                word = tokens[i].upper()
                if is_system and word in words: label += "_"+word
                i += 1
            parts.append(label)
            continue
        if t.upper() in words: parts.append(t.upper())
        elif t[:1] in ("'", '"'):
            decoded=_decode_sql_literal(t)
            public={"rocksdb_bulk_load","performance_schema","information_schema","session_variables"}
            parts.append("SYSTEM_LITERAL_"+decoded.upper() if decoded in public else "LITERAL")
        elif re.fullmatch(r"[-+]?[0-9]+(?:\.[0-9]+)?",t): parts.append("NUMBER")
        elif t in ("=", ";", ",", "(", ")", ".", "*", "+", "-"): parts.append(t)
        else: parts.append("IDENTIFIER")
        i += 1
    if len(parts)>64: return "SHAPE_LIMIT_UNPROVEN"
    return "+".join(parts) or "UNPROVEN"


def explain_quarantined_dynamic(original):
    import sql_diff_evidence as evidence
    import verify
    try:
        groups = []
        for raw in evidence._read_lines(original):
            guard = evidence._GUARD_RE.fullmatch(raw.strip())
            if not guard or not 40000 <= int(guard.group(1)) < 80000: continue
            assignment = verify._CROSS_ENGINE_DYNAMIC_IF_RE.fullmatch(guard.group(2).strip())
            if assignment:
                if len(groups) >= 3: raise ValueError("GROUP_COUNT")
                groups.append(assignment)
        if len(groups) != 3: raise ValueError("GROUP_COUNT")
        for ordinal, group in enumerate(groups, 1):
            for side in ("yes", "no"):
                print("ADVISORY_DYNAMIC_"+str(ordinal)+"_"+side.upper()+"_SHAPE="+
                      _redacted_branch_shape(group.group(side)), flush=True)
        print("ADVISORY_DYNAMIC_EFFECTS=NOT_PROVEN_NO_EXECUTION", flush=True)
    except Exception:
        print("ADVISORY_DYNAMIC_CLASS=UNPROVEN", flush=True)



def explain_advisory(source,target, *, compatibility_only=False):
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
    if compatibility_only:
        explain_conditional_ddl(source,target)
        explain_pk_literal_identity(source,target)
        print("ADVISORY_PREVIOUS_ROW_MULTISET_RESULT=NOT_RERUN",flush=True)
        print("ADVISORY_NOT_A_MIGRATION_PASS_GATE=YES",flush=True)
        return
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


def _metadata_queries(db):
    """Four fixed catalog-only queries; no caller-provided SQL fragments."""
    need(isinstance(db,str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}",db),"METADATA_DB_SCOPE_UNPROVEN")
    where=" WHERE TABLE_SCHEMA='"+db+"'"
    return {
        "server":"SELECT JSON_OBJECT('version',VERSION())",
        "tables":"SELECT JSON_OBJECT('name',TABLE_NAME,'collation',TABLE_COLLATION,'engine',ENGINE) FROM information_schema.TABLES"+where+" AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
        "columns":"SELECT JSON_OBJECT('table',TABLE_NAME,'column',COLUMN_NAME,'charset',CHARACTER_SET_NAME,'collation',COLLATION_NAME) FROM information_schema.COLUMNS"+where+" AND COLLATION_NAME IS NOT NULL ORDER BY TABLE_NAME,ORDINAL_POSITION",
        "collations":"SELECT JSON_OBJECT('name',COLLATION_NAME,'charset',CHARACTER_SET_NAME) FROM information_schema.COLLATION_CHARACTER_SET_APPLICABILITY",
    }


def _read_catalog(args,env,db):
    result={}
    for key,sql in _metadata_queries(db).items():
        response=subprocess.run(args+["--batch","--raw","--skip-column-names","--execute="+sql],
            env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=60,check=False)
        need(response.returncode==0 and 0<len(response.stdout)<=2*1024*1024,"METADATA_QUERY_UNAVAILABLE")
        result[key]=[json.loads(row) for row in response.stdout.decode("utf-8","strict").splitlines()]
        need(len(result[key])<=10000 and all(isinstance(row,dict) for row in result[key]),"METADATA_QUERY_FORMAT_UNPROVEN")
    return result


def live_source_catalog(engine,tail,source_db,base,stage):
    """Read catalog in source memory over the already-bound SSH connection.

    Only pinned credential-parser code and fixed catalog SELECTs are sent.
    No new source dump, script file, SQL command from the export, or cleanup.
    Private table/column identities stay in the CP2 process, never printed.
    """
    import inspect,shlex
    code="import os,re,shlex,subprocess,json,sys,shutil\nfrom pathlib import Path\n"
    code+="class Block(Exception): pass\nclass Stop(Exception): pass\n"
    code+=inspect.getsource(need)+"\n"
    code+=inspect.getsource(stage._target_master_credentials)+"\n"
    code+=inspect.getsource(_metadata_queries)+"\n"+inspect.getsource(_read_catalog)+"\n"
    code+='''
try:
    import inventory
    domain,db=sys.argv[1:]
    sites=[x for x in inventory.build_manifest(Path('/')).get('sites',[]) if isinstance(x,dict) and x.get('domain')==domain]
    need(len(sites)==1 and sites[0].get('mysql_databases')==[db],'SOURCE_BINDING')
    identity=_target_master_credentials()
    binary=shutil.which('mysql') or shutil.which('mariadb')
    need(binary is not None,'SOURCE_CLIENT')
    env=os.environ.copy();env['MYSQL_PWD']=identity['password']
    args=[binary,'--no-defaults','--protocol=tcp','--host='+identity['host'],'--port='+identity['port'],'--user='+identity['user']]
    print(json.dumps(_read_catalog(args,env,db),separators=(',',':')))
except Exception:
    print('SOURCE_METADATA_UNAVAILABLE')
    raise SystemExit(13) from None
'''
    args=["env","PYTHONPATH="+tail["source_runtime_path"]+"/lib","PYTHONDONTWRITEBYTECODE=1",
          "python3","-B","-c",code,base.DOMAIN,source_db]
    response=engine.source_remote(tail["source"],shlex.join(args),timeout=300,check=False)
    need(response.returncode==0 and isinstance(response.stdout,str) and len(response.stdout)<=3*1024*1024,"SOURCE_METADATA_UNAVAILABLE")
    return json.loads(response.stdout)


def live_target_catalog(record,stage):
    import shutil
    binary=shutil.which("mysql") or shutil.which("mariadb")
    need(binary is not None,"TARGET_METADATA_CLIENT_UNAVAILABLE")
    args,env=stage.restricted_user(binary,record["scratch_database"],record["username"],record["password"])
    return _read_catalog([args[0],"--no-defaults",*args[1:]],env,record["scratch_database"])


def _catalog_maps(catalog):
    need(isinstance(catalog,dict) and set(catalog)=={"server","tables","columns","collations"},"CATALOG_SHAPE")
    need(all(isinstance(v,list) and len(v)<=10000 for v in catalog.values()),"CATALOG_SIZE")
    known={}
    for row in catalog["collations"]:
        need(isinstance(row,dict) and set(row)=={"name","charset"},"CATALOG_COLLATION_SHAPE")
        name,charset=row["name"],row["charset"]
        need(isinstance(name,str) and re.fullmatch(r"[A-Za-z0-9_]{1,64}",name),"CATALOG_NAME")
        # MariaDB's UCA family includes generic rows with no charset binding.
        if charset is None:continue
        need(isinstance(charset,str) and re.fullmatch(r"[A-Za-z0-9_]{1,64}",charset),"CATALOG_CHARSET")
        if name.startswith("uca1400_"):
            # CCSA lists one UCA row per charset; compose its documented full
            # name from that actual binding, rather than guessing a charset.
            name=charset+"_"+name
        need(name not in known,"CATALOG_DUPLICATE_COLLATION")
        known[name]=charset
    tables={};columns={}
    for row in catalog["tables"]:
        need(isinstance(row,dict) and set(row)=={"name","collation","engine"},"CATALOG_TABLE_SHAPE")
        name=row["name"]
        need(isinstance(name,str) and name not in tables and row["collation"] in known,"CATALOG_TABLE_IDENTITY")
        tables[name]=row["collation"]
    for row in catalog["columns"]:
        need(isinstance(row,dict) and set(row)=={"table","column","charset","collation"},"CATALOG_COLUMN_SHAPE")
        key=(row["table"],row["column"])
        need(all(isinstance(v,str) for v in key) and key not in columns and key[0] in tables
             and known.get(row["collation"])==row["charset"],"CATALOG_COLUMN_IDENTITY")
        columns[key]=row["collation"]
    return tables,columns,known


def explain_live_collations(source,target,source_sql,target_sql):
    from collections import Counter
    import sql_diff_evidence as schema
    a,ac,ak=_catalog_maps(source);b,bc,bk=_catalog_maps(target)
    sa=schema._schema_statements(source_sql)[0];sb=schema._schema_statements(target_sql)[0]
    need(len(sa)==157 and set(sa)==set(sb)==set(a)==set(b),"LIVE_COLLATION_TABLE_SCOPE")
    need(set(ac)==set(bc),"LIVE_COLLATION_COLUMN_SCOPE")
    pairs=Counter((a[k],b[k]) for k in a if a[k]!=b[k])
    cpairs=Counter((ac[k],bc[k]) for k in ac if ac[k]!=bc[k])
    print("SEMANTIC_LIVE_TABLE_COLLATION_DIFFERING="+str(sum(pairs.values())),flush=True)
    print("SEMANTIC_LIVE_COLUMN_COLLATION_DIFFERING="+str(sum(cpairs.values())),flush=True)
    for label,items in (("TABLE",pairs),("COLUMN",cpairs)):
        for i,((old,new),count) in enumerate(sorted(items.items()),1):
            # Both names were validated against actual public server catalogs.
            print("SEMANTIC_LIVE_"+label+"_COLLATION_"+str(i)+"="+old+":"+new+":"+str(count),flush=True)
    print("SEMANTIC_LIVE_METADATA_IS_FROZEN_SNAPSHOT_PROOF=NO",flush=True)
    print("SEMANTIC_LIVE_COLLATION_ACTION="+("PRESERVE_SOURCE_RULE_IN_REVIEWED_REPAIR" if pairs or cpairs else "NO_LIVE_COLLATION_CHANGE_OBSERVED"),flush=True)


def explain_remaining_defaults(source,target):
    import sql_diff_evidence as schema
    import sql_pk_conflict_evidence as pk
    a=schema._schema_statements(source)[0];b=schema._schema_statements(target)[0]
    need(len(a)==157 and set(a)==set(b),"DEFAULT_TABLE_SCOPE")
    count=0
    for ordinal,name in enumerate(sorted(a),1):
        sa,sb=schema._split_create_table(a[name]),schema._split_create_table(b[name])
        need(sa is not None and sb is not None,"DEFAULT_SCHEMA_PARSE")
        def columns(parts):
            rows={}
            for item,multiplicity in parts[0].items():
                match=pk._DEF.match(item)
                need(multiplicity==1 and match is not None,"DEFAULT_COLUMN_PARSE")
                key=match.group("field")
                need(key not in rows,"DEFAULT_COLUMN_DUPLICATE")
                rows[key]=item[match.end():]
            return rows
        ca,cb=columns(sa),columns(sb)
        need(list(ca)==list(cb),"DEFAULT_COLUMN_SCOPE")
        for colord,key in enumerate(ca,1):
            if ca[key]==cb[key]:continue
            detail=_attribute_detail_categories(ca[key],cb[key])
            if "DEFAULT_EXPRESSION_OR_LITERAL_CHANGED" not in detail:continue
            count+=1;need(count<=100,"DEFAULT_DETAIL_LIMIT")
            result=_default_resolution(ca[key],cb[key])
            print("SEMANTIC_DEFAULT_"+str(count)+"="+str(ordinal)+":"+str(colord)+":"+
                  json.dumps(result,sort_keys=True,separators=(",",":")),flush=True)
    print("SEMANTIC_DEFAULT_UNRESOLVED_COLUMNS_EXAMINED="+str(count),flush=True)
    print("SEMANTIC_DEFAULT_RESULT_IS_SCHEMA_APPROVAL=NO",flush=True)


def semantic_resolution(original,root,record,stage,base,engine,tail,source_db):
    target=root/"scratch-native-readonly.sql"
    status=native_readonly_scratch_dump(record,stage,target,schema_only=True)
    need(status=="COMPLETE","TARGET_SCHEMA_EXPORT_UNAVAILABLE")
    stream,encoding,size=inspect_target_export_bytes(target,"PLAIN_SQL")
    need(stream=="PASS" and encoding=="VALID","TARGET_SCHEMA_ENCODING_UNPROVEN")
    print("TARGET_EXPORT_SCOPE=SCHEMA_ONLY_NO_ROWS",flush=True)
    print("TARGET_SCHEMA_SQL_BYTES="+str(size),flush=True)
    explain_remaining_defaults(original,target)
    explain_quarantined_dynamic(original)
    phase="TARGET_QUERY"
    try:
        target_catalog=live_target_catalog(record,stage)
        phase="SOURCE_QUERY"
        source_catalog=live_source_catalog(engine,tail,source_db,base,stage)
        phase="COLLATION_SCOPE_AND_NAMES"
        explain_live_collations(source_catalog,target_catalog,original,target)
        print("SEMANTIC_LIVE_METADATA=READ_ONLY_COMPLETE",flush=True)
    except Exception as exc:
        print("SEMANTIC_LIVE_METADATA=UNAVAILABLE_NO_INFERENCE",flush=True)
        print("SEMANTIC_LIVE_METADATA_FAILURE_PHASE="+phase,flush=True)
        if isinstance(exc,Block) and re.fullmatch(r"[A-Z0-9_]{1,96}",str(exc)):
            print("SEMANTIC_LIVE_METADATA_FAILURE_CODE="+str(exc),flush=True)
    print("PREVIOUS_157_TABLE_PK_AND_MULTISET_EVIDENCE=NOT_RERUN",flush=True)
    print("SCRATCH_STATIC_COPY_PARITY=NOT_PROVEN",flush=True)
    print("SCRATCH_FULL_SOURCE_EQUIVALENCE=NOT_PROVEN",flush=True)
    print("SCRATCH_PARITY_CLASS=SEMANTIC_RESOLUTION_ONLY",flush=True)
    return 13


def run():
    allowed = ("--read-only-existing-www3-scratch-parity",
               "--read-only-existing-www3-compatibility-closure",
               "--read-only-existing-www3-semantic-resolution")
    need(os.geteuid()==0 and len(sys.argv)==2 and sys.argv[1] in allowed,
         "EXPLICIT_EXISTING_SCRATCH_READONLY_REQUIRED")
    compatibility_only = sys.argv[1] == allowed[1]
    semantic_only = sys.argv[1] == allowed[2]
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
    print("MODE="+("WWW3_EXISTING_SEMANTIC_READ_ONLY" if semantic_only else
                   "WWW3_EXISTING_COMPATIBILITY_READ_ONLY" if compatibility_only else
                   "WWW3_EXISTING_QUARANTINE_READ_ONLY_PARITY"),flush=True)
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
        if semantic_only:
            return semantic_resolution(original,root,record,stage,base,engine,tail,source_db)
        if compatibility_only:
            explain_quarantined_dynamic(original)
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
        if compatibility_only:
            # Prior CP2 readback proved the CloudPanel dump contains raw binary.
            # Use the existing restricted HEX dumper once; do not repeat that
            # known-invalid export before collecting the missing PK evidence.
            compare_path=root/"scratch-native-readonly.sql"
            native_status=native_readonly_scratch_dump(record,stage,compare_path)
            print("NATIVE_SCRATCH_EXPORT="+native_status,flush=True)
            need(native_status=="COMPLETE","NATIVE_READONLY_EXPORT_UNAVAILABLE")
            stream_status,native_utf8,native_bytes=inspect_target_export_bytes(compare_path,"PLAIN_SQL")
            print("NATIVE_SCRATCH_UTF8="+native_utf8,flush=True)
            print("NATIVE_SCRATCH_SQL_BYTES="+str(native_bytes),flush=True)
            need(stream_status=="PASS" and native_utf8=="VALID","NATIVE_EXPORT_ENCODING_UNPROVEN")
            print("TARGET_COMPARE_INPUT=NATIVE_SCRATCH_READONLY_DUMP",flush=True)
        else:
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
        explain_advisory(imported,compare_path,compatibility_only=compatibility_only)
        if compatibility_only:
            print("SCRATCH_STATIC_COPY_PARITY=NOT_PROVEN",flush=True)
            print("SCRATCH_PARITY_CLASS=COMPATIBILITY_EVIDENCE_ONLY",flush=True)
            print("SCRATCH_FULL_SOURCE_EQUIVALENCE=NOT_PROVEN",flush=True)
            return 13
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
