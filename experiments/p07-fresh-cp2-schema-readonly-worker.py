#!/usr/bin/env python3
"""Bounded cross-engine metadata fingerprint for exactly the P07 ilovem3u8 DB.

Metadata is read via SELECT only; object names/definitions/defaults and
credentials are never displayed. This is advisory and not complete DDL proof.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
BASE=HERE/"p07-two-pending-live-db-worker.py"
BASE_BLOB="c63cd3513c773678a6162b50f8a93d35fe9160b6"
DOMAIN="ilovem3u8.kewaro.com"
CATEGORIES=(
 ("TABLES","TABLES","TABLE_SCHEMA",("TABLE_NAME","TABLE_TYPE","ENGINE","TABLE_COLLATION")),
 ("COLUMNS","COLUMNS","TABLE_SCHEMA",("TABLE_NAME","COLUMN_NAME","ORDINAL_POSITION",
          "DATA_TYPE","COLUMN_TYPE","IS_NULLABLE","COLUMN_DEFAULT","EXTRA",
          "CHARACTER_SET_NAME","COLLATION_NAME","GENERATION_EXPRESSION")),
 ("INDEXES","STATISTICS","TABLE_SCHEMA",("TABLE_NAME","INDEX_NAME","NON_UNIQUE",
          "SEQ_IN_INDEX","COLUMN_NAME","SUB_PART","INDEX_TYPE","COLLATION")),
 ("CONSTRAINTS","TABLE_CONSTRAINTS","TABLE_SCHEMA",("TABLE_NAME","CONSTRAINT_NAME","CONSTRAINT_TYPE")),
 ("KEY_USAGE","KEY_COLUMN_USAGE","TABLE_SCHEMA",("TABLE_NAME","CONSTRAINT_NAME",
          "COLUMN_NAME","ORDINAL_POSITION","REFERENCED_TABLE_NAME","REFERENCED_COLUMN_NAME")),
 ("FOREIGN_KEYS","REFERENTIAL_CONSTRAINTS","CONSTRAINT_SCHEMA",
          ("TABLE_NAME","CONSTRAINT_NAME","REFERENCED_TABLE_NAME","UPDATE_RULE","DELETE_RULE")),
 ("TRIGGERS","TRIGGERS","TRIGGER_SCHEMA",("EVENT_OBJECT_TABLE","TRIGGER_NAME",
          "EVENT_MANIPULATION","ACTION_TIMING","ACTION_STATEMENT")),
 ("VIEWS","VIEWS","TABLE_SCHEMA",("TABLE_NAME","VIEW_DEFINITION",
          "CHECK_OPTION","IS_UPDATABLE","SECURITY_TYPE")),
 ("ROUTINES","ROUTINES","ROUTINE_SCHEMA",("ROUTINE_NAME","ROUTINE_TYPE",
          "ROUTINE_DEFINITION","IS_DETERMINISTIC","SECURITY_TYPE")),
 ("EVENTS","EVENTS","EVENT_SCHEMA",("EVENT_NAME","EVENT_DEFINITION","STATUS")),
 ("CHECKS","CHECK_CONSTRAINTS","CONSTRAINT_SCHEMA",
          ("CONSTRAINT_NAME","CHECK_CLAUSE")),
)
class Block(Exception):pass
def need(ok,code):
    if not ok:raise Block(code)
def blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def base_module():
    injected=sys.modules.get("p07_injected_readonly_base")
    if injected is not None:
        need(callable(getattr(injected,"source_auth",None)),"INJECTED_AUTH_UNVERIFIED")
        return injected
    need(BASE.is_file() and not BASE.is_symlink() and
         blob(BASE.read_bytes())==BASE_BLOB,"READONLY_BASE_BLOB_CHANGED")
    spec=importlib.util.spec_from_file_location("p07_schema_base",BASE)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def query_statement(table,schema_field,cols,db):
    # Every identifier originates in the fixed CATEGORIES constant; the
    # database identifier was verified by the CloudPanel inventory resolver.
    need(re.fullmatch("[A-Za-z_]+",table) is not None and
         re.fullmatch("[A-Za-z_]+",schema_field) is not None and
         all(re.fullmatch("[A-Za-z_]+",x) is not None for x in cols) and
         re.fullmatch("[A-Za-z0-9._-]{1,64}",db) is not None,
         "STATIC_METADATA_SQL_IDENTIFIER_UNVERIFIED")
    cells=["IF("+col+" IS NULL,'N',CONCAT('V',HEX(CAST("+
           col+" AS CHAR CHARACTER SET utf8mb4))))" for col in cols]
    return ("SELECT "+",".join(cells)+" FROM information_schema."+
            table+" WHERE "+schema_field+"='"+db+"' ORDER BY "+
            ",".join("("+col+" IS NULL),"+col for col in cols[:2])+";")
def decode_line(line,width):
    cells=line.split(b"\t")
    need(len(cells)==width,"METADATA_FIELD_COUNT_UNVERIFIED")
    result=[]
    for v in cells:
        need(len(v)<=2*1024*1024 and (v==b"N" or
             v.startswith(b"V") and len(v[1:])%2==0 and
             re.fullmatch(rb"[A-Fa-f0-9]*",v[1:])),
             "METADATA_HEX_ENCODING_UNVERIFIED")
        result.append(None if v==b"N" else bytes.fromhex(v[1:].decode("ascii")).decode("utf-8"))
    return result
def category_fingerprint(lines,cols):
    # SQL statement output is intentionally not returned to the caller. Key
    # each object by its first field, hash the full field-value tuples, and
    # report only aggregate evidence of object-level differences.
    groups={}
    count=0
    for raw in lines:
        need(len(raw)<=16*1024*1024,"SCHEMA_METADATA_ROW_TOO_LARGE")
        fields=decode_line(raw.rstrip(b"\r\n"),len(cols))
        need(fields[0] is not None and 0<len(fields[0])<=256,
             "METADATA_OBJECT_ID_UNVERIFIED")
        identity=hashlib.sha256(fields[0].encode("utf-8")).hexdigest()
        digest=hashlib.sha256(json.dumps(fields,ensure_ascii=False,separators=(",",":")).encode("utf-8")).digest()
        groups.setdefault(identity,[]).append(digest)
        count+=1
        need(count<=100000,"SCHEMA_METADATA_ROW_COUNT_EXCEEDED")
    objects={name:[len(values),hashlib.sha256(b"".join(sorted(values))).hexdigest()]
             for name,values in groups.items()}
    return {"count":count,"objects":objects}
def scan(base,domain,db):
    need(domain==DOMAIN and re.fullmatch("[A-Za-z0-9._-]{1,64}",db) is not None,
         "FIXED_INCIDENT_DOMAIN_AND_DB_REQUIRED")
    host,port,user,password=base.source_auth(domain,db)
    cli=shutil.which("mariadb") or shutil.which("mysql")
    need(cli is not None and shutil.which("timeout") is not None,
         "READONLY_METADATA_CLIENT_UNAVAILABLE")
    with tempfile.TemporaryDirectory(prefix="p07-meta-",dir="/root") as tmp:
        conf=Path(tmp)/"client.cnf"
        fd=os.open(conf,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        escape=lambda x:x.replace("\\","\\\\").replace('"','\\"')
        with os.fdopen(fd,"w") as f:
            f.write('[client]\nuser="'+escape(user)+'"\npassword="'+escape(password)+'"\n')
        args=[shutil.which("timeout"),"120",cli,
              "--defaults-extra-file="+str(conf),"--protocol=tcp",
              "--host="+host,"--port="+str(port),
              "--batch","--skip-column-names","--raw","--binary-mode",
              "--default-character-set=utf8mb4"]
        result={}
        for name,table,field,cols in CATEGORIES:
            sql=query_statement(table,field,cols,db)
            try:
                proc=subprocess.run(args+["--execute",sql],stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,check=False,timeout=140)
            except (OSError,subprocess.SubprocessError):
                raise Block("METADATA_SQL_READ_UNAVAILABLE") from None
            need(proc.returncode==0 and len(proc.stdout)<=32*1024*1024,
                 "METADATA_SQL_READ_FAILED_"+name)
            try:
                result[name]=category_fingerprint(proc.stdout.splitlines(),cols)
            except UnicodeError:raise Block("METADATA_UTF8_UNVERIFIED") from None
    return result
def main():
    need(os.geteuid()==0 and len(sys.argv)==4 and
         sys.argv[1] in ("source","target") and sys.argv[2]==DOMAIN,
         "EXPLICIT_SOURCE_OR_TARGET_SCHEMA_READ_ONLY_REQUIRED")
    output=scan(base_module(),sys.argv[2],sys.argv[3])
    print(json.dumps({"mode":sys.argv[1],"categories":output},
         separators=(",",":"),sort_keys=True),flush=True)
if __name__=="__main__":
    try:main()
    except SystemExit:raise
    except Exception:
        print("BLOCKED=SCHEMA_METADATA_READ_FAILED",flush=True)
        raise SystemExit(13) from None
