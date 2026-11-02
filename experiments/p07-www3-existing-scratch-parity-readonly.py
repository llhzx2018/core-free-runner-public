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
                     "changed_options","source_only_tables","target_only_tables"):
            n=values.get(name)
            if type(n) is int and 0<=n<=5000000:
                print("ADVISORY_"+name.upper()+"="+str(n),flush=True)
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
