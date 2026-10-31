#!/usr/bin/env python3
"""P07 www3 full-row value multiset advisory, read-only on old VPS and CP2.

Both hosts are scanned using the SAME pinned worker, under independent
REPEATABLE READ consistent-snapshot, READ ONLY transactions. The snapshots are
NOT simultaneous and old VPS is live; MATCH is not original export/cutover PASS.
Only count labels reach operator output. No secret, raw row or SQL is printed.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
FILES=(
    ("p07-www3-restored-readback.py","a1ac6e2c6771ca8f2e8a55bcd7064ccc1f9cf47f"),
    ("p07-www3-content-worker.py","85d52f93fddd6be1867752b251534f17a6036752"),
)
def stop(code):
    raise Blocked(code)

class Blocked(Exception):
    pass

def get_file(filename,expected_sha):
    path=ROOT/filename
    try:
        if path.is_symlink() or not path.is_file():
            stop("BUNDLE_FILE_MISSING_OR_SYMLINK")
        content=path.read_bytes()
    except OSError:
        stop("BUNDLE_FILE_UNAVAILABLE")
    blob=hashlib.sha1(b"blob "+str(len(content)).encode()+bytes([0])+content).hexdigest()
    if blob!=expected_sha:stop("BUNDLE_FILE_BLOB_CHANGED")
    return path,content

# Load only version-pinned companion; never an installed or unrelated module.
try:
    READBACK,_=get_file(*FILES[0])
    WORKER,WORKER_CODE=get_file(*FILES[1])
except Blocked as exc:
    print("BLOCKED="+str(exc))
    raise SystemExit(13)
mod=importlib.util.spec_from_file_location("p07_readback_verified",READBACK)
readback=importlib.util.module_from_spec(mod)
mod.loader.exec_module(readback)
base=readback.base

def parsed(raw,mode):
    if type(raw) is not str or len(raw)>131072:
        stop("CONTENT_WORKER_OUTPUT_UNVERIFIED")
    lines={}
    allowed={"MODE","SCANNED_TABLES","SCANNED_COLUMNS","SCANNED_ROWS",
             "ROW_FINGERPRINTS","READ_ONLY_TRANSACTION",
             "CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY"}
    for line in raw.splitlines():
        if "=" not in line:stop("CONTENT_WORKER_OUTPUT_UNVERIFIED")
        key,value=line.split("=",1)
        if key not in allowed or key in lines:stop("CONTENT_WORKER_OUTPUT_UNVERIFIED")
        lines[key]=value
    if set(lines)!=allowed:stop("CONTENT_WORKER_INCOMPLETE")
    if (lines["MODE"]!=mode or lines["READ_ONLY_TRANSACTION"]!="YES"
            or lines["CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY"]!="YES"):
        stop("CONTENT_WORKER_BOUNDARY_CHANGED")
    values={}
    for key in ("SCANNED_TABLES","SCANNED_COLUMNS","SCANNED_ROWS"):
        v=lines[key]
        if not re.fullmatch(r"[0-9]{1,10}",v):
            stop("CONTENT_WORKER_COUNT_UNVERIFIED")
        values[key]=int(v)
    try: m=json.loads(lines["ROW_FINGERPRINTS"])
    except (ValueError,TypeError):
        stop("CONTENT_WORKER_MAP_INVALID")
    if type(m) is not dict or len(m)!=values["SCANNED_TABLES"]:
        stop("CONTENT_WORKER_MAP_SIZE_INVALID")
    if not 0<len(m)<=1000 or not values["SCANNED_COLUMNS"]>=len(m):
        stop("CONTENT_WORKER_EMPTY_OR_INVALID_SCHEMA")
    for name,row in m.items():
        if not isinstance(name,str) or not re.fullmatch("[0-9a-f]{64}",name):
            stop("CONTENT_WORKER_TABLE_ID_INVALID")
        if (type(row) is not list or len(row)!=3
                or type(row[0]) is not int or not 0<=row[0]<=1000000
                or any(not isinstance(x,str) or not re.fullmatch("[0-9a-f]{64}",x)
                       for x in row[1:])):
            stop("CONTENT_WORKER_ROW_HASH_INVALID")
    if sum(row[0] for row in m.values())!=values["SCANNED_ROWS"]:
        stop("CONTENT_WORKER_ROW_TOTAL_INVALID")
    return values,m

def compare():
    if sys.argv[1:]!=["--compare-live-source-rows-read-only"]:
        stop("EXPLICIT_READ_ONLY_CONTENT_ARG_REQUIRED")
    db,user,password,expected_ddl=readback.preflight()
    if (base._cloudpanel_metadata_counts(db)!=("1","1")
            or base._master_sql_presence(db,user)!=("1","1")):
        stop("SCRATCH_DATABASE_BINDING_UNPROVEN")
    state=readback.read_private(base.STATE)
    if state.get("migration_id")!=base.MID:
        stop("MIGRATION_ID_CHANGED")
    sites=state.get("sites")
    if type(sites) is not list or len(sites)!=2 or sites[1].get("domain")!=base.DOMAIN:
        stop("MIGRATION_SITE_SCOPE_CHANGED")
    origin=sites[1].get("mysql_databases")
    if (type(origin) is not list or len(origin)!=1
            or type(origin[0]) is not str
            or not re.fullmatch("[A-Za-z0-9._-]{1,64}",origin[0])):
        stop("SOURCE_DATABASE_ID_UNVERIFIED")
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import server_migration_pull as migration
    if migration.target_identity()!=state.get("target_server_identity"):
        stop("MIGRATION_TARGET_IDENTITY_CHANGED")
    try:
        target=subprocess.run(["python3","-B",str(WORKER),"target",base.DOMAIN,db],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,timeout=1900,check=False,text=True)
    except (OSError,subprocess.SubprocessError,UnicodeError):
        stop("CP2_READ_ONLY_CONTENT_WORKER_UNAVAILABLE")
    if target.returncode:
        stop("CP2_READ_ONLY_CONTENT_WORKER_FAILED")
    local,local_map=parsed(target.stdout,"TARGET")
    if local["SCANNED_TABLES"]!=expected_ddl:
        stop("TARGET_TABLE_SCOPE_CHANGED")
    try:
        source_code=WORKER_CODE.decode("utf-8","strict")
    except UnicodeError:stop("BUNDLE_WORKER_INVALID_UTF8")
    remote_cmd=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
        "PYTHONPATH="+base.SOURCE_RUNTIME+"/lib","python3","-B","-c",source_code,
        "source",base.DOMAIN,origin[0]])
    try:
        response=migration.source_remote(state["source"],remote_cmd,
            timeout=1900,check=False)
    except Exception:
        stop("OLD_VPS_READ_ONLY_CONTENT_WORKER_UNAVAILABLE")
    if response.returncode:
        stop("OLD_VPS_READ_ONLY_CONTENT_WORKER_FAILED")
    old,old_map=parsed(response.stdout,"SOURCE")
    ids=set(old_map)&set(local_map)
    missing_old=len(set(local_map)-set(old_map))
    missing_target=len(set(old_map)-set(local_map))
    metadata_diff=sum(old_map[k][2]!=local_map[k][2] for k in ids)
    count_diff=sum(old_map[k][0]!=local_map[k][0] for k in ids)
    value_diff=sum(old_map[k][1]!=local_map[k][1] for k in ids)
    same=(not missing_old and not missing_target and not metadata_diff
        and not count_diff and not value_diff
        and old["SCANNED_TABLES"]==local["SCANNED_TABLES"]
        and old["SCANNED_COLUMNS"]==local["SCANNED_COLUMNS"]
        and old["SCANNED_ROWS"]==local["SCANNED_ROWS"])
    print("CURRENT_SOURCE_TABLES="+str(old["SCANNED_TABLES"]))
    print("RESTORED_TARGET_TABLES="+str(local["SCANNED_TABLES"]))
    print("CURRENT_SOURCE_ROWS="+str(old["SCANNED_ROWS"]))
    print("RESTORED_TARGET_ROWS="+str(local["SCANNED_ROWS"]))
    print("SOURCE_ONLY_TABLES="+str(missing_target))
    print("TARGET_ONLY_TABLES="+str(missing_old))
    print("COLUMN_NAME_IDENTITY_DIFFERING_TABLES="+str(metadata_diff))
    print("ROW_COUNT_DIFFERING_TABLES="+str(count_diff))
    print("ROW_VALUE_MULTISETS_DIFFERING_TABLES="+str(value_diff))
    print("LIVE_SOURCE_TARGET_ROW_VALUE_FINGERPRINT="+
          ("MATCH_ADVISORY_ONLY" if same else "DIFFER_ADVISORY"))
    print("BOTH_SIDES_CONSISTENT_READ_ONLY_TRANSACTIONS=YES")
    print("SNAPSHOTS_SIMULTANEOUS=NO")
    print("ORIGINAL_SQL_EXPORT_ROW_CONTENT_PARITY=NOT_VERIFIED")
    print("SOURCE_MAY_CHANGE_AFTER_READ=YES")
    print("OLD_SERVER_DATABASE_WRITES=NONE")
    print("CP2_DATABASE_WRITES=NONE")
    print("CUTOVER_ALLOWED=NO")
    return 0

if __name__=="__main__":
    try:raise SystemExit(compare())
    except (Blocked,readback.Blocked,base.Stop) as exc:
        print("BLOCKED="+str(exc))
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=UNVERIFIED_CONTENT_COMPARISON")
        raise SystemExit(13) from None
