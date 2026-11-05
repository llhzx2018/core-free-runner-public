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
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
FILES=(
    ("p07-www3-restored-readback.py","a1ac6e2c6771ca8f2e8a55bcd7064ccc1f9cf47f"),
    ("p07-www3-content-worker.py","d42c99637679a123672f2b37d62fa2af327875e1"),
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
    if type(raw) is not str or len(raw)>900000:
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
        if (type(row) is not list or len(row)!=4
                or type(row[0]) is not int or not 0<=row[0]<=1000000
                or any(not isinstance(x,str) or not re.fullmatch("[0-9a-f]{64}",x)
                       for x in row[1:3])
                or type(row[3]) is not dict or not 0<len(row[3])<=200
                or any(not isinstance(col,str) or not re.fullmatch("[0-9a-f]{64}",col)
                       or not isinstance(sig,str) or not re.fullmatch("[0-9a-f]{64}",sig)
                       for col,sig in row[3].items())):
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
    cell_diff=0
    changed_columns=0
    combinations_only=0
    details=[]
    # Keep identities private; only deterministic ordinal and count are shown.
    for ordinal,k in enumerate(sorted(set(old_map)|set(local_map)),1):
        if k not in old_map or k not in local_map:continue
        if old_map[k][1]==local_map[k][1]:continue
        s_cols=old_map[k][3]
        t_cols=local_map[k][3]
        if set(s_cols)!=set(t_cols):
            stop("COLUMN_IDENTITY_CHANGED_DURING_CONTENT_COMPARE")
        n=sum(s_cols[col]!=t_cols[col] for col in s_cols)
        if n:
            cell_diff+=1
            changed_columns+=n
        else:
            combinations_only+=1
        details.append(str(ordinal)+":"+str(n))
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
    print("COLUMN_VALUE_DISTRIBUTION_DIFFERING_TABLES="+str(cell_diff))
    print("COLUMN_VALUE_DISTRIBUTION_DIFFERING_COLUMNS="+str(changed_columns))
    print("ROW_COMBINATION_ONLY_DIFFERING_TABLES="+str(combinations_only))
    print("DIFFERING_TABLE_ORDINAL_COLUMN_COUNTS="+(",".join(details) if details else "NONE"))
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


def current_candidate_context():
    path,_=get_file(
        "p07-pending-three-runtime-readonly.py",
        "1d64c229c8886e34ae1fde15d24025680777d458")
    spec=importlib.util.spec_from_file_location(
        "p07_verified_current_candidate_context",path)
    scope=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scope)
    return scope


def compare_current_candidate():
    """Compare OLD VPS source to CURRENT connected CP2 www3, never scratch.

    Both SQL transactions are read-only and independently consistent, NOT
    simultaneous or frozen. MATCH is advisory; no source/target DB writes.
    """
    if sys.argv[1:]!=["--compare-current-candidate-source-rows-read-only"]:
        stop("EXPLICIT_CURRENT_CANDIDATE_READONLY_ARG_REQUIRED")
    scope=current_candidate_context()
    source,panel,transactions,config,identity=scope.www3_context()
    relation=scope.candidate_relation(
        source,panel,transactions,config,identity,0)
    if not (relation["JOURNAL_STATUS"]=="CONNECTED_NOT_CUTOVER_READY"
            and relation["CURRENT_CONFIG_READBACK"]=="CANDIDATE_MATCH"
            and relation["CANDIDATE_DB_IN_CP2_SITE_PANEL"]=="YES"
            and relation["SOURCE_DB_IN_CP2_PANEL"]=="NO"
            and relation["UNCLASSIFIED_CP2_SITE_DB_COUNT"]==0):
        stop("CURRENT_CANDIDATE_NOT_JOURNAL_BOUND")
    target_db,target_user,private_pw=scope.www3_candidate_credentials(
        source,transactions,identity)
    if (target_db not in panel["mysql_databases"]
            or target_db in source["mysql_databases"]):
        stop("CURRENT_CANDIDATE_DB_IDENTITY_CHANGED")
    registry=scope.pinned(scope.BASE,scope.BASE_BLOB,"BASE")
    state=registry.secure_state(
        scope.ROOT/source["migration_id"]/"state.json")
    remote_runtime=state.get("source_runtime_path")
    if (state.get("migration_id")!=source["migration_id"]
            or state.get("target_server_identity")!=identity
            or state.get("source_runtime_frozen") is not False
            or state.get("dns_changed_by_p07") is not False
            or state.get("cutover_prohibited") is not True
            or remote_runtime!=(
                "/var/lib/vf-server-ops/pull-source/"
                +source["migration_id"]+"/runtime")):
        stop("CURRENT_CANDIDATE_SOURCE_RUNTIME_CHANGED")
    original_db=source.get("mysql_databases")
    if (type(original_db) is not list or len(original_db)!=1
            or not re.fullmatch("[A-Za-z0-9._-]{1,64}",original_db[0])):
        stop("CURRENT_CANDIDATE_ORIGINAL_DB_CHANGED")
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import server_migration_pull as migration
    if migration.target_identity()!=identity:
        stop("CURRENT_CANDIDATE_CP2_TARGET_IDENTITY_CHANGED")
    env={**os.environ,
         "PYTHONDONTWRITEBYTECODE":"1",
         "P07_CURRENT_CANDIDATE_READ_ONLY":"YES",
         "P07_CURRENT_CANDIDATE_DB":target_db,
         "P07_CURRENT_CANDIDATE_USER":target_user,
         "P07_CURRENT_CANDIDATE_PASSWORD":private_pw}
    try:
        local=subprocess.run(
            ["python3","-B",str(WORKER),"target-current",
             "www3.m3u8.one",target_db],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,timeout=1900,check=False,text=True,
            env=env)
    except (OSError,subprocess.SubprocessError,UnicodeError):
        stop("CURRENT_CANDIDATE_READONLY_WORKER_UNAVAILABLE")
    if local.returncode:
        stop("CURRENT_CANDIDATE_READONLY_WORKER_FAILED")
    current,cmap=parsed(local.stdout,"TARGET")
    if current["SCANNED_TABLES"]!=157:
        stop("CURRENT_CANDIDATE_157_TABLE_SCOPE_CHANGED")
    try: source_code=WORKER_CODE.decode("utf-8","strict")
    except UnicodeError:stop("CURRENT_WORKER_CODE_ENCODING_INVALID")
    remote=shlex.join([
        "env","PYTHONDONTWRITEBYTECODE=1",
        "PYTHONPATH="+remote_runtime+"/lib",
        "python3","-B","-c",source_code,
        "source","www3.m3u8.one",original_db[0]])
    try:
        response=migration.source_remote(state["source"],remote,
            timeout=1900,check=False)
    except Exception:
        stop("CURRENT_CANDIDATE_OLD_VPS_READONLY_UNAVAILABLE")
    if response.returncode:
        stop("CURRENT_CANDIDATE_OLD_VPS_READONLY_FAILED")
    old,omap=parsed(response.stdout,"SOURCE")
    if old["SCANNED_TABLES"]!=157:
        stop("CURRENT_CANDIDATE_OLD_VPS_157_TABLE_SCOPE_CHANGED")
    common=set(omap)&set(cmap)
    only_source=len(set(omap)-set(cmap))
    only_target=len(set(cmap)-set(omap))
    changed_count=sum(omap[k][0]!=cmap[k][0] for k in common)
    changed_columns=sum(omap[k][2]!=cmap[k][2] for k in common)
    changed_values=sum(omap[k][1]!=cmap[k][1] for k in common)
    column_value_deltas=sum(omap[k][3]!=cmap[k][3] for k in common)
    same=(not any((only_source,only_target,changed_count,
                   changed_columns,changed_values,column_value_deltas))
          and old==current)
    print("PROBE=P07_WWW3_CURRENT_CONNECTED_CANDIDATE_SOURCE_CONTENT")
    print("SITE=www3.m3u8.one")
    print("TARGET_DATABASE=JOURNAL_BOUND_CONNECTED_CANDIDATE_NOT_SCRATCH")
    for name,value in (
        ("SOURCE_TABLES",old["SCANNED_TABLES"]),
        ("CANDIDATE_TABLES",current["SCANNED_TABLES"]),
        ("SOURCE_ROWS",old["SCANNED_ROWS"]),
        ("CANDIDATE_ROWS",current["SCANNED_ROWS"]),
        ("SOURCE_ONLY_TABLES",only_source),
        ("CANDIDATE_ONLY_TABLES",only_target),
        ("ROW_COUNT_DIFF_TABLES",changed_count),
        ("COLUMN_IDENTITY_DIFF_TABLES",changed_columns),
        ("ROW_VALUE_DIFF_TABLES",changed_values),
        ("COLUMN_VALUE_DISTRIBUTION_DIFF_TABLES",column_value_deltas)):
        print(name+"="+str(value))
    print("LIVE_CONTENT_FINGERPRINT="+(
        "MATCH_ADVISORY_ONLY" if same else "DIFFER_ADVISORY"))
    print("BOTH_HOSTS_READ_ONLY_TRANSACTIONS=YES")
    print("SNAPSHOTS_SIMULTANEOUS=NO")
    print("SOURCE_WRITES_MAY_CONTINUE=YES")
    print("SOURCE_EXPORT_SNAPSHOT_PARITY=NOT_VERIFIED")
    print("DYNAMIC_SQL_EFFECTS_FULLY_VERIFIED=NO")
    print("DB_OR_SITE_CONFIG_WRITES=NONE")
    print("DNS_OR_RUNTIME_WRITES=NONE")
    print("CUTOVER_ALLOWED=NO")
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(
            compare_current_candidate()
            if sys.argv[1:]==["--compare-current-candidate-source-rows-read-only"]
            else compare())
    except (Blocked,readback.Blocked,base.Stop) as exc:
        print("BLOCKED="+str(exc))
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=UNVERIFIED_CONTENT_COMPARISON")
        raise SystemExit(13) from None
