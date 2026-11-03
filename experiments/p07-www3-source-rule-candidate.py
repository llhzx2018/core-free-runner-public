#!/usr/bin/env python3
"""One new www3 copy, unused by the app; preserve existing DBs and receipts.

Explicit source collation is applied to CREATE TABLE in a private SQL copy.
No ALTER of an existing database, source export/freeze, website mapping or DNS.
Failure retains the candidate and its separate intent; no retry or cleanup.
"""
from __future__ import annotations
import gzip,hashlib,importlib.util,json,os,re,sys,tempfile
from pathlib import Path

READONLY_NAME="p07-www3-existing-scratch-parity-readonly.py"
READONLY_BLOB="a6285fd4fb44865849d31fd00d368b7af1f00bac"
# These engines remain unchanged in the new copy. MEMORY is volatile on both
# sides; its rows are verified now, never treated as durable activation proof.
COPY_ENGINES=frozenset({"INNODB","MYISAM","MEMORY"})

class Block(Exception):pass
def need(ok,why):
    if not ok:raise Block(why)

def load_readonly():
    path=Path(__file__).with_name(READONLY_NAME)
    need(path.is_file() and not path.is_symlink(),"READONLY_COMPANION_MISSING")
    data=path.read_bytes()
    need(hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()==READONLY_BLOB,"READONLY_COMPANION_DRIFT")
    spec=importlib.util.spec_from_file_location("p07_source_rule_readonly",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def options(suffix,ro):
    """Parse only ordinary dump table options, outside quoted comments."""
    tokens=ro._ATTR_TOKENS.findall(suffix);out={};i=0
    while i<len(tokens):
        key=tokens[i].upper();i+=1
        if key==";" and i==len(tokens):break
        if key=="DEFAULT":
            need(i<len(tokens) and tokens[i].upper()=="CHARSET","TABLE_OPTION_UNPROVEN")
            key="CHARSET";i+=1
        need(key in {"ENGINE","CHARSET","COLLATE","AUTO_INCREMENT","ROW_FORMAT","COMMENT"} and key not in out,"TABLE_OPTION_UNPROVEN")
        need(i+1<len(tokens) and tokens[i]=="=","TABLE_OPTION_UNPROVEN")
        value=tokens[i+1];i+=2
        if key=="COMMENT":need(ro._decode_sql_literal(value) is not None,"TABLE_COMMENT_UNPROVEN")
        else:need(re.fullmatch(r"[A-Za-z0-9_]+",value),"TABLE_OPTION_UNPROVEN")
        out[key]=value
    need("ENGINE" in out and "CHARSET" in out,"TABLE_DEFAULTS_UNPROVEN")
    return out

def columns(parts):
    import sql_pk_conflict_evidence as pk
    result={}
    for item,count in parts[0].items():
        match=pk._DEF.match(item)
        need(count==1 and match,"COLUMN_PARSE_UNPROVEN")
        key=match.group("field")
        if key.startswith("`") and key.endswith("`"):key=key[1:-1].replace("``","`")
        need(key not in result,"COLUMN_PARSE_UNPROVEN")
        result[key]=item[match.end():]
    return result

def source_engine_evidence(source,catalog,ro,expected_tables=157):
    """Report public engine pairs; never reveal table names or SQL literals."""
    from collections import Counter
    import sql_diff_evidence as schema
    tables,_,_=ro._catalog_maps(catalog)
    definitions,_=schema._schema_statements(source)
    need(len(definitions)==expected_tables and set(definitions)==set(tables),"SOURCE_ENGINE_TABLE_SCOPE")
    live={row["name"]:row["engine"] for row in catalog["tables"]}
    public={"INNODB","MYISAM","ARIA","MEMORY","HEAP","ROCKSDB","MYROCKS","TOKUDB",
            "MRG_MYISAM","MERGE","FEDERATED","FEDERATEDX","CONNECT","SPIDER","CSV",
            "ARCHIVE","BLACKHOLE","COLUMNSTORE","MROONGA","S3","SEQUENCE","PERFORMANCE_SCHEMA"}
    pairs=Counter();differing=unsupported=0
    for name,definition in definitions.items():
        parts=schema._split_create_table(definition)
        need(parts is not None,"SOURCE_ENGINE_SCHEMA_PARSE")
        snapshot=options(parts[2],ro)["ENGINE"].upper()
        current=live[name].upper() if isinstance(live[name],str) else "UNAVAILABLE"
        pairs[(snapshot if snapshot in public else "OTHER_UNPROVEN",
               current if current in public else "OTHER_UNPROVEN")]+=1
        differing+=snapshot!=current
        unsupported+=snapshot not in COPY_ENGINES
    for ordinal,((snapshot,current),count) in enumerate(sorted(pairs.items()),1):
        print("SOURCE_ENGINE_PAIR_"+str(ordinal)+"="+snapshot+":"+current+":"+str(count),flush=True)
    print("SOURCE_ENGINE_SNAPSHOT_LIVE_DIFFERING="+str(differing),flush=True)
    print("SOURCE_ENGINE_OUTSIDE_CURRENT_COPY_POLICY="+str(unsupported),flush=True)
    print("SOURCE_ENGINE_EVIDENCE_IS_MIGRATION_APPROVAL=NO",flush=True)
    return differing,unsupported

def source_rule_plan(source,catalog,ro,expected_tables=157):
    import sql_diff_evidence as schema
    tables,charcols,known=ro._catalog_maps(catalog)
    definitions,other=schema._schema_statements(source)
    need(len(definitions)==expected_tables and set(definitions)==set(tables),"SOURCE_RULE_TABLE_SCOPE")
    engines={row["name"]:row["engine"] for row in catalog["tables"]}
    plan={};seen=set();column_count=0
    for name,definition in definitions.items():
        parts=schema._split_create_table(definition)
        need(parts is not None,"SOURCE_RULE_SCHEMA_PARSE")
        opts=options(parts[2],ro)
        need(opts["ENGINE"].lower()==str(engines[name]).lower(),"SOURCE_SNAPSHOT_LIVE_ENGINE_DIFFER")
        need(opts["ENGINE"].upper() in COPY_ENGINES,"SOURCE_ENGINE_OUTSIDE_CURRENT_COPY_POLICY")
        charset=opts["CHARSET"];rule=tables[name]
        need(known[rule]==charset,"SOURCE_RULE_CHARSET_MISMATCH")
        if "COLLATE" in opts:need(opts["COLLATE"]==rule,"SOURCE_RULE_EXPLICIT_DRIFT")
        else:
            need(charset=="utf8mb3" and rule=="utf8mb3_general_ci","IMPLICIT_SOURCE_RULE_UNSUPPORTED")
            plan[name]=rule
        for column,definition in columns(parts).items():
            column_count+=1
            parsed=ro._attribute_scan(definition)
            need(parsed is not None,"SOURCE_COLUMN_PARSE_UNPROVEN")
            key=(name,column)
            if key not in charcols:continue
            seen.add(key)
            attrs=parsed[1]
            need(len(attrs["COLLATION"])<=1 and len(attrs["CHARSET"])<=1,"SOURCE_COLUMN_RULE_UNPROVEN")
            explicit=attrs["COLLATION"][0][-1] if attrs["COLLATION"] else rule
            column_charset=attrs["CHARSET"][0][-1] if attrs["CHARSET"] else charset
            need(explicit==charcols[key] and known[explicit]==column_charset,"SOURCE_COLUMN_RULE_DRIFT")
    need(seen==set(charcols),"SOURCE_CHARACTER_COLUMN_SCOPE")
    return plan,column_count

def prove_rocksdb_only(source,ro):
    """Accept just the observed public MyRocks probe/enable/restore shapes.

    This establishes omission scope only. Nothing from a dynamic branch runs.
    Engine checks and an independent guard on the retained SQL are required.
    """
    import sql_diff_evidence as schema,verify
    variable=r"@[A-Za-z_][A-Za-z0-9_$]*"
    number=r"[+-]?[0-9]{1,20}(?:\.[0-9]{1,20})?"
    patterns=[
        r"SELECT\s+COUNT\s*\(\s*\*\s*\)\s+INTO\s+"+variable+r"\s+FROM\s+performance_schema\.session_variables\s+WHERE\s+VARIABLE_NAME\s*=\s*'rocksdb_bulk_load'",
        r"SET\s+SESSION\s+rocksdb_bulk_load\s*=\s*[01]",
        r"SET\s+SESSION\s+rocksdb_bulk_load\s*=\s*"+variable,
    ]
    groups=[]
    for raw in schema._read_lines(source):
        guard=schema._GUARD_RE.fullmatch(raw.strip())
        if not guard or not 40000<=int(guard.group(1))<80000:continue
        assignment=verify._CROSS_ENGINE_DYNAMIC_IF_RE.fullmatch(guard.group(2).strip())
        if assignment:groups.append(assignment)
    need(len(groups)==3,"ROCKSDB_GROUP_COUNT")
    for i,(group,pattern) in enumerate(zip(groups,patterns)):
        yes=ro._decode_sql_literal(group.group("yes"));no=ro._decode_sql_literal(group.group("no"))
        need(yes is not None and no is not None,"ROCKSDB_LITERAL_UNPROVEN")
        # Permit backticks only around these public catalog identifiers.
        for public in ("performance_schema","session_variables","VARIABLE_NAME","rocksdb_bulk_load"):
            yes=re.sub("`"+public+"`",public,yes,flags=re.I)
        need(re.fullmatch(pattern,yes.strip(),re.I),"ROCKSDB_BRANCH_UNPROVEN")
        # Dumps may use either SELECT 0 or SELECT 1 for the probe fallback.
        # A dummy user-variable assignment may use another numeric constant;
        # its value is not used because all three dynamic groups are omitted.
        # Keep the pinned guard as well as this narrower constant-only grammar:
        # no functions, expressions, queries, session/global SET or comments.
        otherwise=r"SELECT\s+[01]" if i==0 else r"SET\s+"+variable+r"\s*=\s*"+number
        need(verify._cross_engine_safe_dynamic_branch(group.group("no"))
             and re.fullmatch(otherwise,no.strip(),re.I),"ROCKSDB_ELSE_UNPROVEN")

def inject_source_rules(source,destination,plan,ro):
    """Modify only missing table-default COLLATE; keep every other byte."""
    import sql_diff_evidence as schema
    need(not os.path.lexists(destination) and source!=destination,"REPAIR_OUTPUT_EXISTS")
    seen=set();pending=[];name=None;modified=0
    with gzip.open(source,"rb") as inp,gzip.open(destination,"xb") as out:
        for raw in inp:
            if not pending:
                match=re.match(rb"CREATE TABLE `([A-Za-z0-9_$.-]+)`\s*\(",raw)
                if not match:out.write(raw);continue
                name=match.group(1).decode("ascii");pending=[]
            pending.append(raw)
            need(sum(map(len,pending))<=2*1024*1024,"REPAIR_DDL_LIMIT")
            if not raw.rstrip().endswith(b";"):continue
            data=b"".join(pending);pending=[]
            need(name not in seen,"REPAIR_DUPLICATE_TABLE");seen.add(name)
            if name in plan:
                parsed=schema._split_create_table(data.decode("utf-8"))
                need(parsed is not None and "COLLATE" not in options(parsed[2],ro),"REPAIR_EXISTING_COLLATION")
                need(plan[name]=="utf8mb3_general_ci","REPAIR_RULE_UNPROVEN")
                pos=data.rfind(b";")
                data=data[:pos]+b" COLLATE=utf8mb3_general_ci"+data[pos:];modified+=1
            out.write(data)
    need(not pending and set(plan)<=seen and modified==len(plan),"REPAIR_TABLE_SCOPE")
    return modified

def compatible_schema(source,target,ro,expected_tables=157):
    """Exact schema except four independently bounded display differences."""
    import sql_diff_evidence as schema
    a,ao=schema._schema_statements(source);b,bo=schema._schema_statements(target)
    need(len(a)==expected_tables and set(a)==set(b) and ao==bo,"CANDIDATE_SCHEMA_SCOPE")
    allowed={"DEFAULT_TIMESTAMP_SYNTAX_ONLY","ON_UPDATE_TIMESTAMP_SYNTAX_ONLY","DEFAULT_NULLABLE_LOB_NULL_PRESENTATION"}
    hex_defaults=0
    for name in a:
        x,y=schema._split_create_table(a[name]),schema._split_create_table(b[name])
        need(x is not None and y is not None and x[1]==y[1] and options(x[2],ro)==options(y[2],ro),"CANDIDATE_INDEX_OR_OPTIONS_DIFFER")
        ca,cb=columns(x),columns(y)
        need(list(ca)==list(cb),"CANDIDATE_COLUMNS_DIFFER")
        for key in ca:
            if ca[key]==cb[key]:continue
            delta=ro._attribute_detail_categories(ca[key],cb[key])
            if "DEFAULT_EXPRESSION_OR_LITERAL_CHANGED" in delta and ro._default_resolution(ca[key],cb[key]).get("relation")=="EQUAL_ASCII_HEX_BYTES":
                delta=delta-{"DEFAULT_EXPRESSION_OR_LITERAL_CHANGED"};hex_defaults+=1
            need(delta<=allowed,"CANDIDATE_COLUMN_SEMANTICS_DIFFER")
    return hex_defaults

def candidate_collations(source_catalog,target_catalog,ro):
    a,ac,_=ro._catalog_maps(source_catalog);b,bc,_=ro._catalog_maps(target_catalog)
    need(a==b and ac==bc,"CANDIDATE_LIVE_COLLATION_DIFFER")

def prepare_copy(original,quarantined,repaired,source_catalog,ro,stage,expected_tables=157,expected_repairs=25):
    source_engine_evidence(original,source_catalog,ro,expected_tables)
    plan,column_count=source_rule_plan(original,source_catalog,ro,expected_tables)
    need(len(plan)==expected_repairs,"SOURCE_COLLATION_REPAIR_SCOPE_CHANGED")
    prove_rocksdb_only(original,ro)
    stage.make_quarantined_sql(original,quarantined)
    inject_source_rules(quarantined,repaired,plan,ro)
    stage.strict_scope(repaired,quarantined=True)
    return plan,column_count

def verify_copy(repaired,readback,source_catalog,target_catalog,ro,expected_tables=157):
    hex_defaults=compatible_schema(repaired,readback,ro,expected_tables)
    candidate_collations(source_catalog,target_catalog,ro)
    report=ro._pk_literal_identity_report(repaired,readback)
    need(report.get("STATUS")=="LITERAL_EQUAL_NOT_VERIFIED"
         and report.get("TABLES_EVALUABLE")==expected_tables
         and report.get("TABLES_UNAVAILABLE")==0
         and report.get("DIFFERING_TABLES")==0,"CANDIDATE_ROWS_UNPROVEN")
    return hex_defaults,report["IDENTICAL_ROWS"]

def run():
    need(os.geteuid()==0 and sys.argv[1:] in (["--create-new-www3-source-rule-candidate"],["--read-only-source-engine-evidence"]),"EXPLICIT_NEW_CANDIDATE_OR_READONLY_REQUIRED")
    engine_only=sys.argv[1]=="--read-only-source-engine-evidence"
    os.umask(0o077)
    ro=load_readonly();base=ro.load(ro.HELPER_NAME,ro.HELPER_BLOB);stage=ro.load(ro.STAGE_NAME,ro.STAGE_BLOB)
    tail,source_db=base.verify_state();base.verify_current_runtime()
    sys.path.insert(0,str(base.RUNTIME/"lib"))
    import server_migration_pull as engine,site_lifecycle,inventory,cloudpanel
    need(engine.target_identity()==tail["target_server_identity"],"TARGET_IDENTITY_CHANGED")
    base.inspect_existing_site(base.DOMAIN,source_db)
    old=ro.load_receipt(base,stage,tail["target_server_identity"],source_db)
    if engine_only:
        print("MODE=WWW3_SOURCE_ENGINE_READ_ONLY",flush=True)
        print("DATABASE_CREATE_IMPORT_ALTER_DELETE=NONE",flush=True)
        print("RECEIPT_AND_MIGRATION_STATE_WRITES=NONE",flush=True)
        print("SOURCE_NEW_EXPORT_OR_FREEZE=NONE",flush=True)
        print("WEBSITE_MAPPING_AND_DNS_WRITES=NONE",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        with tempfile.TemporaryDirectory(prefix="p07-www3-engine-readonly-",dir="/root") as td:
            original=Path(td)/"source.sql.gz"
            digest=stage.import_existing_verified_source(engine,tail,source_db,base,original)
            need(digest==old["source_snapshot_sha256"],"SOURCE_ARCHIVE_RECEIPT_MISMATCH")
            catalog=ro.live_source_catalog(engine,tail,source_db,base,stage)
            source_engine_evidence(original,catalog,ro)
        print("ENGINE_EVIDENCE_READBACK=COMPLETE",flush=True)
        return 0
    name,user,password=site_lifecycle.derive_database_identity(base.DOMAIN,base.TAIL+":source-rule-copy-v1",1)
    need(name not in {source_db,old["scratch_database"]},"CANDIDATE_NAME_COLLISION")
    sites=inventory.build_manifest(Path("/")).get("sites",[])
    need(isinstance(sites,list) and not any(name in (s.get("mysql_databases") or []) for s in sites if isinstance(s,dict)),"CANDIDATE_ALREADY_BOUND")
    marker=stage.receipt_path(base,name);client=stage.absent_sql(name)
    print("MODE=NEW_WWW3_SOURCE_RULE_CANDIDATE",flush=True)
    print("EXISTING_DATABASES_AND_RECEIPTS=RETAIN_UNCHANGED",flush=True)
    print("SOURCE_NEW_EXPORT_OR_FREEZE=NONE",flush=True)
    print("WEBSITE_MAPPING_AND_DNS_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    with tempfile.TemporaryDirectory(prefix="p07-www3-rule-copy-",dir="/root") as td:
        root=Path(td);original=root/"source.sql.gz";quarantined=root/"quarantine.sql.gz";repaired=root/"source-rules.sql.gz"
        digest=stage.import_existing_verified_source(engine,tail,source_db,base,original)
        need(digest==old["source_snapshot_sha256"],"SOURCE_ARCHIVE_RECEIPT_MISMATCH")
        source_catalog=ro.live_source_catalog(engine,tail,source_db,base,stage)
        plan,column_count=prepare_copy(original,quarantined,repaired,source_catalog,ro,stage)
        need(column_count==1848,"SOURCE_COLUMN_COUNT_CHANGED")
        memory_tables=sum(str(row["engine"]).upper()=="MEMORY" for row in source_catalog["tables"])
        # All preparation and source-rule checks precede the first DB write.
        fresh=ro.live_source_catalog(engine,tail,source_db,base,stage)
        candidate_collations(source_catalog,fresh,ro)
        need(source_catalog["tables"]==fresh["tables"],"SOURCE_ENGINE_METADATA_CHANGED")
        stage.absent_sql(name)
        record={"schema":"p07.www3.source-rule-candidate.v1","migration_id":base.TAIL,"domain":base.DOMAIN,
            "source_database":source_db,"source_snapshot_sha256":digest,"scratch_database":name,"username":user,"password":password,
            "target_server_identity":tail["target_server_identity"],"previous_scratch_retained":True,"source_runtime_frozen":False,
            "website_activated":False,"original_database_modified":False,"status":"INTENT_RESERVED",
            "table_collations_explicit":len(plan),"dynamic_groups_omitted":3,"cutover_allowed":False,
            "memory_table_count":memory_tables,"source_engines_preserved":True,
            "fresh_readback_required_before_activation":True,
            "candidate_sql_sha256":hashlib.sha256(repaired.read_bytes()).hexdigest()}
        stage.save(marker,record,first=True)
        try:
            cloudpanel.add_database(base.DOMAIN,name,user,password)
            record["status"]="CREATED_NOT_IMPORTED";stage.save(marker,record)
            args,env=stage.restricted_user(client,name,user,password)
            stage.import_only_scratch(args,env,name,repaired)
            record["status"]="IMPORTED_NOT_VERIFIED";stage.save(marker,record)
            readback=root/"scratch-native-readonly.sql"
            need(ro.native_readonly_scratch_dump(record,stage,readback)=="COMPLETE","CANDIDATE_EXPORT_FAILED")
            target_catalog=ro.live_target_catalog(record,stage)
            hex_defaults,rows=verify_copy(repaired,readback,source_catalog,target_catalog,ro)
            record.update(status="VERIFIED_STATIC_COPY_NOT_ACTIVATED",verified_rows=rows,ascii_hex_defaults_equal=hex_defaults)
            stage.save(marker,record)
        except Exception:
            record["status"]="CANDIDATE_UNPROVEN_RETAIN_NO_RETRY";stage.save(marker,record)
            raise
    print("CANDIDATE_STATIC_COPY=VERIFIED",flush=True)
    print("CANDIDATE_EXPLICIT_SOURCE_COLLATIONS="+str(len(plan)),flush=True)
    print("CANDIDATE_ASCII_HEX_DEFAULTS_EQUAL="+str(hex_defaults),flush=True)
    print("CANDIDATE_VERIFIED_ROWS="+str(rows),flush=True)
    print("CANDIDATE_DYNAMIC_SQL_EXECUTED=NONE",flush=True)
    print("CANDIDATE_MEMORY_TABLES="+str(memory_tables),flush=True)
    print("CANDIDATE_ENGINE_CONVERSION=NONE",flush=True)
    print("FRESH_READBACK_REQUIRED_BEFORE_ACTIVATION=YES",flush=True)
    print("SOURCE_COLLATION_BASIS=LIVE_METADATA_NOT_FROZEN_SNAPSHOT",flush=True)
    print("CANDIDATE_NEW_RECEIPT="+str(marker),flush=True)
    print("LIVE_SOURCE_FINAL_CONSISTENCY=NOT_PROVEN",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0

if __name__=="__main__":
    try:raise SystemExit(run())
    except Exception as exc:
        print("BLOCKED="+(str(exc) if isinstance(exc,Block) else "CANDIDATE_OPERATION_UNPROVEN"),flush=True)
        print("AUTOMATIC_RETRY=NO",flush=True)
        print("EXISTING_DATABASES_AND_RECEIPTS=RETAIN_UNCHANGED",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
