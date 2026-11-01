#!/usr/bin/env python3
"""P07 ilovem3u8 single differing table read-only primary-key/row worker."""
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
class Block(Exception): pass
def need(ok,code):
    if not ok:raise Block(code)
def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def load_base():
    try:
        need(BASE.is_file() and not BASE.is_symlink() and
             blob(BASE.read_bytes())==BASE_BLOB,
             "BASE_READONLY_WORKER_CHANGED")
        spec=importlib.util.spec_from_file_location("p07_safe_base",BASE)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except OSError:raise Block("BASE_READONLY_WORKER_MISSING") from None

def scan_rows(base,mode,domain,db,table_id):
    need(domain=="ilovem3u8.kewaro.com" and
         re.fullmatch("[a-f0-9]{64}",table_id) is not None,
         "SITE_OR_TABLE_SCOPE_INVALID")
    need(mode in ("source","target") and
         re.fullmatch("[A-Za-z0-9._-]{1,64}",db) is not None,
         "DB_SCOPE_INVALID")
    host,port,user,password=base.source_auth(domain,db)
    cli=shutil.which("mariadb") or shutil.which("mysql")
    need(cli is not None,"SQL_CLIENT_UNAVAILABLE")
    with tempfile.TemporaryDirectory(prefix="p07-single-pk-",dir="/root") as folder:
        cfg=Path(folder)/"client.cnf"
        fd=os.open(cfg,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        escaped=lambda v:v.replace("\\","\\\\").replace('"','\\"')
        with os.fdopen(fd,"w") as out:
            out.write('[client]\nuser="'+escaped(user)+'"\npassword="'+escaped(password)+'"\n')
        args=[cli,"--defaults-extra-file="+str(cfg),
              "--protocol=tcp","--host="+host,"--port="+str(port),
              "--batch","--skip-column-names","--raw","--binary-mode",
              "--default-character-set=utf8mb4"]
        tables,allcols=base.schema(args,db)
        need(len(tables)==42,"EXPECTED_42_TABLE_SCOPE_CHANGED")
        matches=[t for t in tables if hashlib.sha256(t.encode("ascii")).hexdigest()==table_id]
        need(len(matches)==1,"DIFFERING_TABLE_ID_NOT_FOUND")
        table=matches[0]
        lit="'"+db+"'"
        primaries=base.sql_read(args,
            "SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE "
            "TABLE_SCHEMA="+lit+" AND TABLE_NAME='"+table+"' AND "
            "CONSTRAINT_NAME='PRIMARY' ORDER BY ORDINAL_POSITION",90).splitlines()
        need(0<len(primaries)<=8 and len(primaries)==len(set(primaries))
             and set(primaries)<=set(allcols[table]),
             "PRIMARY_KEY_ABSENT_OR_UNVERIFIED")
        columns=allcols[table]
        names=primaries+columns
        expr=[]
        for col in names:
            need(re.fullmatch("[A-Za-z0-9_]{1,64}",col) is not None,"COLUMN_ID_INVALID")
            ident=chr(96)+col+chr(96)
            expr.append("IF("+ident+" IS NULL,'N',CONCAT('V',HEX(CAST("+ident+" AS BINARY))))")
        qident=lambda x:chr(96)+x+chr(96)
        query="SELECT "+",".join(expr)+" FROM "+qident(db)+"."+qident(table)+";"
        with tempfile.TemporaryFile(mode="w+b") as source:
            source.write(b"SET SESSION time_zone='+00:00';\n")
            source.write(b"SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;\n")
            source.write(b"START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;\n")
            source.write(query.encode("ascii")+b"\n")
            source.write(b"ROLLBACK;\n")
            source.flush();source.seek(0)
            timeout=shutil.which("timeout")
            need(timeout is not None,"TIMEOUT_UNAVAILABLE")
            try:
                proc=subprocess.Popen([timeout,"1800",*args],stdin=source,
                                       stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            except OSError:raise Block("SQL_TRANSACTION_UNAVAILABLE") from None
            rows={}
            try:
                assert proc.stdout is not None
                for raw in proc.stdout:
                    need(len(raw)<=16*1024*1024,"ROW_SIZE_LIMIT_EXCEEDED")
                    vals=raw.rstrip(b"\r\n").split(b"\t")
                    need(len(vals)==len(names),"ROW_FIELD_COUNT_CHANGED")
                    need(all(re.fullmatch(b"(?:N|V[0-9A-F]*)",x) for x in vals),
                         "ROW_HEX_ENCODING_UNVERIFIED")
                    need(all(x!=b"N" for x in vals[:len(primaries)]),
                         "PRIMARY_KEY_NULL_UNVERIFIED")
                    pk=b"\x00".join(vals[:len(primaries)])
                    body=b"\x00".join(vals[len(primaries):])
                    identity=hashlib.sha256(pk).hexdigest()
                    need(identity not in rows,"PRIMARY_KEY_DUPLICATE_OR_HASH_COLLISION")
                    rows[identity]=hashlib.sha256(body).hexdigest()
                    need(len(rows)<=10000,"ROW_LIMIT_EXCEEDED")
                need(proc.wait(timeout=25)==0,"SQL_READONLY_TRANSACTION_FAILED")
            except (OSError,subprocess.SubprocessError):
                raise Block("SQL_READONLY_TRANSACTION_UNAVAILABLE") from None
            finally:
                if proc.poll() is None:proc.kill();proc.wait(timeout=20)
                if proc.stdout:proc.stdout.close()
    return {
        "MODE":mode.upper(),
        "TABLE_ID":table_id,
        "TABLES_SCANNED":42,
        "PRIMARY_KEY_COLUMN_COUNT":len(primaries),
        "ROW_COUNT":len(rows),
        "ROWS":rows,
        "READ_ONLY_TRANSACTION":"YES",
    }

def main():
    need(os.geteuid()==0 and len(sys.argv)==5 and
         sys.argv[1] in ("source","target"),
         "EXPLICIT_READONLY_SOURCE_TARGET_ARG_REQUIRED")
    out=scan_rows(load_base(),*sys.argv[1:])
    print(json.dumps(out,sort_keys=True,separators=(",",":")),flush=True)
    return 0
if __name__=="__main__":
    try:raise SystemExit(main())
    except Block as e:
        print("BLOCKED="+str(e),flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=UNVERIFIED_PRIMARY_KEY_WORKER",flush=True)
        raise SystemExit(13) from None
