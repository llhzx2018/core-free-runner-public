#!/usr/bin/env python3
"""P07 release113 fixed www3 SQL advisory; no migration/cutover/data changes."""
import json
from pathlib import Path
import re
import shlex
import stat
import sys

MID="pull-20261031T095604Z-edae3c44"
PARENT="pull-20261031T094144Z-d045fa5a"
SOURCE_RUNTIME=f"/var/lib/vf-server-ops/pull-source/{MID}/runtime"
STATE=Path("/var/lib/vf-server-ops/server-migrations")/MID/"state.json"

REMOTE=r'''
import gzip,re,shutil,subprocess,sys,tempfile
from pathlib import Path
import cloudpanel,inventory,sql_diff_evidence
def classify_invalid_utf8_context(path):
    # Byte-preserving, bounded advisory. Statement labels are HINTS ONLY,
    # never used by the actual SQL verification or import.
    import codecs
    decoder=codecs.getincrementaldecoder("utf-8")("surrogateescape")
    bad=re.compile("[\udc80-\udcff]")
    categories={"DML":0,"DDL":0,"SESSION":0,"OTHER":0}
    context="OTHER"
    boundary=True
    charset=set()
    limit=1024*1024*1024
    total=0
    completed=False
    with gzip.open(path,"rb") as handle:
        while total<limit:
            piece=handle.readline(min(1024*1024,limit-total))
            if not piece:
                completed=True
                last=decoder.decode(b"",final=True)
                if bad.search(last):
                    categories[context]+=1
                break
            if boundary:
                prefix=piece.lstrip()[:256]
                if re.match(rb"^(INSERT|REPLACE|UPDATE|DELETE|LOAD)\b",prefix,re.I):
                    context="DML"
                elif re.match(rb"^(CREATE|ALTER|DROP|TRUNCATE|RENAME)\b",prefix,re.I):
                    context="DDL"
                elif re.match(rb"^(SET|LOCK|UNLOCK|USE|DELIMITER|START|COMMIT|/\*!)\b",prefix,re.I):
                    context="SESSION"
                elif not prefix or prefix.startswith((b"--",b"#")):
                    context="OTHER"
                if total<5*1024*1024:
                    match=re.search(rb"\bSET\s+NAMES\s+([A-Za-z0-9_]{1,32})",prefix,re.I)
                    if match:
                        charset.add(match.group(1).lower())
            text=decoder.decode(piece,final=False)
            if bad.search(text):
                categories[context]+=1
            total+=len(piece)
            boundary=piece.endswith(b"\n")
            if boundary and piece.rstrip().endswith(b";"):
                context="OTHER"
    allow={b"utf8mb4",b"utf8",b"latin1",b"gbk",b"gb18030",
           b"binary",b"ascii",b"utf16",b"ucs2",b"sjis"}
    valid=charset & allow
    if len(charset)==1 and len(valid)==1:
        label=next(iter(valid)).decode("ascii").upper()
    elif charset:
        label="UNRECOGNIZED_OR_MIXED"
    else:
        label="NOT_FOUND"
    return categories,completed,label

domain,database,mid=sys.argv[1:]
rows=[s for s in inventory.build_manifest(Path("/")).get("sites",[])
      if isinstance(s,dict) and s.get("domain")==domain]
if len(rows)!=1 or database not in (rows[0].get("mysql_databases") or []):
    print("SOURCE_DB_BINDING=NOT_PROVEN");sys.exit(31)
print("SOURCE_DB_BINDING=PASS",flush=True)
client=shutil.which("mariadb") or shutil.which("mysql")
query=("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='"+
       database+"' AND table_type='BASE TABLE'")
if client:
    try:
        result=subprocess.run(
            [client,"--no-defaults","--protocol=socket","--user=root",
             "--batch","--skip-column-names","--execute",query],
            capture_output=True,text=True,timeout=15,check=False)
        value=result.stdout.strip()
        value=value if result.returncode==0 and re.fullmatch(r"[0-9]{1,9}",value) else "UNAVAILABLE"
    except (OSError,subprocess.SubprocessError,UnicodeError):
        value="UNAVAILABLE"
else:
    value="UNAVAILABLE"
print("INDEPENDENT_BASE_TABLE_COUNT="+value,flush=True)
root=Path("/var/lib/vf-server-ops/pull-source")/mid/"data"
if not root.is_dir() or root.is_symlink():
    print("SOURCE_EXPORT_DIAG=STAGING_UNAVAILABLE");sys.exit(32)
with tempfile.TemporaryDirectory(prefix="schema-only-",dir=root) as tmp:
    dump=Path(tmp)/"sample.sql.gz"
    try:
        cloudpanel.export_database(database,dump,clpctl="clpctl")
    except (cloudpanel.CloudPanelError,ValueError):
        print("SOURCE_EXPORT_DIAG=CLI_FAILED");sys.exit(33)
    with dump.open("rb") as f:
        prefix=f.read(4)
    gz=prefix[:2]==bytes.fromhex("1f8b")
    print("EXPORT_CONTAINER="+("GZIP" if gz else "PLAIN_OR_OTHER"),flush=True)
    try:
        count=sql_diff_evidence.require_nonempty_source_schema(dump)
        print("PARSER_SCHEMA_COUNT="+str(count),flush=True)
    except sql_diff_evidence.AdvisoryDiagnosticUnavailable as exc:
        label=str(exc)
        allowed={"SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA",
                 "SQL_DIAGNOSTIC_INPUT_UNAVAILABLE",
                 "SQL_SCHEMA_STATEMENT_INCOMPLETE",
                 "SQL_SCHEMA_STATEMENT_TOO_LARGE",
                 "SQL_DUPLICATE_CREATE_TABLE"}
        print("PARSER_RESULT="+(label if label in allowed else "OTHER_UNAVAILABLE"),flush=True)
    if gz:
        lines=qualified=scanned=0
        complete=True
        try:
            with gzip.open(dump,"rb") as handle:
                for line in handle:
                    scanned+=len(line)
                    if scanned>32*1024*1024:
                        complete=False;break
                    line=line.lstrip()
                    if re.match(rb"CREATE\s+TABLE\b",line,re.I):
                        lines+=1
                        if re.match(rb"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?\x60[^\x60]+\x60\.",line,re.I):
                            qualified+=1
        except (OSError,EOFError):
            print("EXPORT_STREAM=UNREADABLE",flush=True)
        else:
            print("DDL_LINES_IN_SAMPLE="+str(lines),flush=True)
            print("QUALIFIED_DDL_LINES_IN_SAMPLE="+str(qualified),flush=True)
            print("SAMPLE_COMPLETE="+str(complete).upper(),flush=True)
    if gz:
        # Independent streaming check: verify checksum/end-of-stream and
        # UTF-8 without exposing SQL or needing to store decompressed data.
        import codecs
        limit = 1024 * 1024 * 1024
        total = 0
        utf8_invalid = False
        decoder = codecs.getincrementaldecoder("utf-8")("strict")
        integrity = "UNDETERMINED"
        try:
            with gzip.open(dump,"rb") as stream:
                while True:
                    block = stream.read(1024 * 1024)
                    if not block:
                        if not utf8_invalid:
                            try: decoder.decode(b"",final=True)
                            except UnicodeDecodeError: utf8_invalid=True
                        integrity="PASS"
                        break
                    total += len(block)
                    if not utf8_invalid:
                        try: decoder.decode(block,final=False)
                        except UnicodeDecodeError: utf8_invalid=True
                    if total >= limit:
                        integrity="SIZE_CAP_REACHED"
                        break
        except (OSError,EOFError):
            integrity="GZIP_READ_FAILED"
        print("GZIP_STREAM_INTEGRITY="+integrity,flush=True)
        print("UTF8_VALIDITY="+(
            "INVALID" if utf8_invalid else "VALID" if integrity=="PASS"
            else "UNPROVEN"),flush=True)
        print("STREAM_MIB_SCANNED="+str(total // (1024*1024)),flush=True)
        print("COMPRESSED_MIB="+str(
            (dump.stat().st_size + (1024*1024) - 1) // (1024*1024)
        ),flush=True)

    if gz:
        try:
            categories,complete,charset=classify_invalid_utf8_context(dump)
            print("UTF8_CONTEXT_SCAN_COMPLETE="+str(complete).upper(),flush=True)
            print("SQL_SET_NAMES_HINT="+charset,flush=True)
            for key in ("DML","DDL","SESSION","OTHER"):
                print("INVALID_UTF8_CHUNKS_"+key+"="+str(categories[key]),flush=True)
            print("CONTEXT_CLASSIFICATION=ADVISORY_NOT_A_PASS_GATE",flush=True)
        except (OSError,EOFError):
            print("UTF8_CONTEXT_SCAN_COMPLETE=FALSE",flush=True)
print("SOURCE_BUSINESS_DB_WRITES=NO",flush=True)
'''

ALLOWED=re.compile(
    r"^(?:SOURCE_DB_BINDING=(?:PASS|NOT_PROVEN)|"
    r"INDEPENDENT_BASE_TABLE_COUNT=(?:[0-9]{1,9}|UNAVAILABLE)|"
    r"SOURCE_EXPORT_DIAG=(?:STAGING_UNAVAILABLE|CLI_FAILED)|"
    r"EXPORT_CONTAINER=(?:GZIP|PLAIN_OR_OTHER)|PARSER_SCHEMA_COUNT=[0-9]{1,9}|"
    r"PARSER_RESULT=(?:SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA|SQL_DIAGNOSTIC_INPUT_UNAVAILABLE|"
    r"SQL_SCHEMA_STATEMENT_INCOMPLETE|SQL_SCHEMA_STATEMENT_TOO_LARGE|"
    r"SQL_DUPLICATE_CREATE_TABLE|OTHER_UNAVAILABLE)|"
    r"EXPORT_STREAM=UNREADABLE|DDL_LINES_IN_SAMPLE=[0-9]{1,9}|"
    r"QUALIFIED_DDL_LINES_IN_SAMPLE=[0-9]{1,9}|"
    r"SAMPLE_COMPLETE=(?:TRUE|FALSE)|GZIP_STREAM_INTEGRITY=(?:PASS|SIZE_CAP_REACHED|GZIP_READ_FAILED|UNDETERMINED)|"
    r"UTF8_VALIDITY=(?:VALID|INVALID|UNPROVEN)|STREAM_MIB_SCANNED=[0-9]{1,9}|"
    r"COMPRESSED_MIB=[0-9]{1,9}|UTF8_CONTEXT_SCAN_COMPLETE=(?:TRUE|FALSE)|"
    r"SQL_SET_NAMES_HINT=(?:UTF8MB4|UTF8|LATIN1|GBK|GB18030|BINARY|ASCII|UTF16|UCS2|SJIS|UNRECOGNIZED_OR_MIXED|NOT_FOUND)|"
    r"INVALID_UTF8_CHUNKS_(?:DML|DDL|SESSION|OTHER)=[0-9]{1,9}|"
    r"CONTEXT_CLASSIFICATION=ADVISORY_NOT_A_PASS_GATE|SOURCE_BUSINESS_DB_WRITES=NO)$"
)

def main():
    if sys.argv[1:]!=["--source-schema-advisory"]:
        print("BLOCKED=EXPLICIT_DIAGNOSTIC_ARG_REQUIRED");return 13
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import server_migration_pull as engine
    meta=STATE.lstat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid!=0 or meta.st_mode&0o022:
        print("BLOCKED=CHILD_STATE_UNSAFE");return 13
    s=json.loads(STATE.read_text())
    sites=s.get("sites")
    if not (s.get("migration_id")==MID and s.get("partial_parent_migration_id")==PARENT
            and s.get("status")=="PREPARE_FAILED"
            and s.get("cutover_prohibited") is True
            and s.get("source_runtime_frozen") is False
            and s.get("dns_changed_by_p07") is False
            and s.get("source_runtime_path")==SOURCE_RUNTIME
            and isinstance(sites,list) and len(sites)==2
            and sites[0].get("domain")=="updates.kewaro.com"
            and sites[0].get("stage_status")=="PULLED_STAGED"
            and sites[1].get("domain")=="www3.m3u8.one"
            and sites[1].get("stage_status")=="PENDING"):
        print("BLOCKED=CHILD_SCOPE_DRIFT");return 13
    dbs=sites[1].get("mysql_databases")
    if not (type(dbs) is list and len(dbs)==1 and type(dbs[0]) is str
            and re.fullmatch(r"[A-Za-z0-9._-]{1,128}",dbs[0])):
        print("BLOCKED=SOURCE_DATABASE_SCOPE_DRIFT");return 13
    args=["env",f"PYTHONPATH={SOURCE_RUNTIME}/lib",
          "python3","-c",REMOTE,"www3.m3u8.one",dbs[0],MID]
    print("MIGRATION_RETRY=NO",flush=True)
    try:
        response=engine.source_remote(s["source"],shlex.join(args),timeout=1900,check=False)
    except Exception as exc:
        print("SOURCE_CONNECT_ERROR="+type(exc).__name__);return 13
    for line in response.stdout.splitlines():
        if ALLOWED.fullmatch(line):print(line)
    print("SOURCE_DIAGNOSTIC_RC="+str(response.returncode))
    print("CUTOVER=NO")
    return 0 if response.returncode==0 else 13

if __name__=="__main__":
    try:raise SystemExit(main())
    except (OSError,ValueError,json.JSONDecodeError):
        print("BLOCKED=UNVERIFIED_RUNTIME_STATE")
        raise SystemExit(13) from None
