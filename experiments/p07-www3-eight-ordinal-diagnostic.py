#!/usr/bin/env python3
"""P07 www3 scoped eight-table live difference and column-type advisory, read-only on old VPS and CP2.

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
    ("p07-www3-eight-ordinal-type-worker.py","95973afd4efba1122156a53cc98f2efd59f35ac0"),
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
             "FULL_BASE_TABLES","TARGETED_ORDINALS","ORDINAL_TABLE_IDS","COLUMN_TYPES",
             "ROW_FINGERPRINTS","READ_ONLY_TRANSACTION",
             "CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY"}
    for line in raw.splitlines():
        if "=" not in line:stop("CONTENT_WORKER_OUTPUT_UNVERIFIED")
        key,value=line.split("=",1)
        if key not in allowed or key in lines:stop("CONTENT_WORKER_OUTPUT_UNVERIFIED")
        lines[key]=value
    if set(lines)!=allowed:stop("CONTENT_WORKER_INCOMPLETE")
    if (lines["MODE"]!=mode or lines["FULL_BASE_TABLES"]!="157"
            or lines["TARGETED_ORDINALS"]!="17,39,60,69,70,71,78,139"
            or lines["READ_ONLY_TRANSACTION"]!="YES"
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
    try: metadata=json.loads(lines["COLUMN_TYPES"])
    except (ValueError,TypeError):stop("COLUMN_TYPES_MAP_INVALID")
    try: ordinal_ids=json.loads(lines["ORDINAL_TABLE_IDS"])
    except (ValueError,TypeError):stop("TARGETED_ORDINAL_MAP_INVALID")
    if (type(ordinal_ids) is not dict or set(ordinal_ids)!={"17","39","60","69","70","71","78","139"}
            or set(ordinal_ids.values())!=set(m)):
        stop("TARGETED_ORDINAL_MAP_UNVERIFIED")
    if type(metadata) is not dict or set(metadata)!=set(m):
        stop("COLUMN_TYPES_IDENTITY_INVALID")
    for tid,columns in metadata.items():
        if type(columns) is not dict or set(columns)!=set(m[tid][3]):
            stop("COLUMN_TYPES_COL_IDENTITY_INVALID")
        for cid,profile in columns.items():
            if type(profile) is not list or len(profile)!=8:
                stop("COLUMN_TYPES_PROFILE_INVALID")
            for i,v in enumerate(profile):
                if (type(v) is not str or
                    not re.fullmatch("[A-Za-z0-9_]{1,50}|-|YES|NO",v)):
                    stop("COLUMN_TYPES_PROFILE_UNSAFE")
    return values,m,metadata,ordinal_ids

def compare():
    if sys.argv[1:]!=["--diagnose-eight-current-difference-tables-read-only"]:
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
        target=subprocess.run(["python3","-B",str(WORKER),"target",base.DOMAIN,db,"--only-eight-current-difference-tables"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,timeout=1900,check=False,text=True)
    except (OSError,subprocess.SubprocessError,UnicodeError):
        stop("CP2_READ_ONLY_CONTENT_WORKER_UNAVAILABLE")
    if target.returncode:
        stop("CP2_READ_ONLY_CONTENT_WORKER_FAILED")
    local,local_map,local_meta,local_ord=parsed(target.stdout,"TARGET")
    if expected_ddl!=157 or local["SCANNED_TABLES"]!=8:
        stop("TARGET_TABLE_SCOPE_CHANGED")
    try:
        source_code=WORKER_CODE.decode("utf-8","strict")
    except UnicodeError:stop("BUNDLE_WORKER_INVALID_UTF8")
    remote_cmd=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
        "PYTHONPATH="+base.SOURCE_RUNTIME+"/lib","python3","-B","-c",source_code,
        "source",base.DOMAIN,origin[0],"--only-eight-current-difference-tables"])
    try:
        response=migration.source_remote(state["source"],remote_cmd,
            timeout=1900,check=False)
    except Exception:
        stop("OLD_VPS_READ_ONLY_CONTENT_WORKER_UNAVAILABLE")
    if response.returncode:
        stop("OLD_VPS_READ_ONLY_CONTENT_WORKER_FAILED")
    old,old_map,old_meta,old_ord=parsed(response.stdout,"SOURCE")
    if old_ord!=local_ord:stop("EIGHT_TABLE_IDENTITIES_DIFFER")
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
    if (missing_old or missing_target or metadata_diff or
            old["SCANNED_TABLES"]!=8 or len(ids)!=8):
        stop("EIGHT_TABLE_IDENTITIES_OR_COLUMNS_CHANGED")
    # Identifiers are hashed in the workers and never printed.
    profiles=[]
    reverse_ord={v:k for k,v in old_ord.items()}
    differences=0
    type_mismatch=charset_mismatch=collation_mismatch=0
    for tid in sorted(ids):
        s=old_map[tid]
        t=local_map[tid]
        if s[1]==t[1]:continue
        source_cols=old_meta[tid]
        target_cols=local_meta[tid]
        for cid in sorted(s[3]):
            if s[3][cid]==t[3][cid]:continue
            differences+=1
            sp,tp=source_cols[cid],target_cols[cid]
            type_mismatch+=int(sp[0]!=tp[0])
            charset_mismatch+=int(sp[1]!=tp[1])
            collation_mismatch+=int(sp[2]!=tp[2])
            profiles.append({"table_ordinal":reverse_ord[tid],"type_source":sp[0],"type_target":tp[0],
                             "charset_source":sp[1],"charset_target":tp[1],
                             "collation_source":sp[2],"collation_target":tp[2],
                             "nullability_source":sp[3],"nullability_target":tp[3],
                             "precision_source":sp[4:],"precision_target":tp[4:]})
    if differences>1600:
        stop("EIGHT_TABLE_CHANGED_FIELD_CAP_EXCEEDED")
    print("DIFFERING_FIELD_COUNT="+str(differences))
    print("DATA_TYPE_CHANGED_FIELD_COUNT="+str(type_mismatch))
    print("CHARSET_CHANGED_FIELD_COUNT="+str(charset_mismatch))
    print("COLLATION_CHANGED_FIELD_COUNT="+str(collation_mismatch))
    for ordinal in sorted(old_ord,key=lambda k:int(k)):
        tid=old_ord[ordinal]
        source_row=old_map[tid]
        target_row=local_map[tid]
        source_cols=old_meta[tid]
        target_cols=local_meta[tid]
        if set(source_cols)!=set(target_cols) or set(source_cols)!=set(source_row[3]):
            stop("COLUMN_PROFILE_IDENTITY_CHANGED")
        n=sum(source_row[3][cid]!=target_row[3][cid] for cid in source_row[3])
        mismatch=sum(source_cols[cid]!=target_cols[cid] for cid in source_cols)
        print("ORDINAL_"+ordinal+"_SOURCE_ROWS="+str(source_row[0]))
        print("ORDINAL_"+ordinal+"_RESTORED_ROWS="+str(target_row[0]))
        print("ORDINAL_"+ordinal+"_ROW_VALUES="+("DIFFER" if source_row[1]!=target_row[1] else "MATCH"))
        print("ORDINAL_"+ordinal+"_DIFFERING_COLUMNS="+str(n))
        print("ORDINAL_"+ordinal+"_SCHEMA_PROFILES_DIFFERING="+str(mismatch))
    print("CURRENT_SOURCE_TARGETED_TABLES="+str(old["SCANNED_TABLES"]))
    print("RESTORED_TARGETED_TABLES="+str(local["SCANNED_TABLES"]))
    print("CURRENT_SOURCE_ROWS="+str(old["SCANNED_ROWS"]))
    print("RESTORED_TARGET_ROWS="+str(local["SCANNED_ROWS"]))
    print("SOURCE_ONLY_TABLES="+str(missing_target))
    print("TARGET_ONLY_TABLES="+str(missing_old))
    print("COLUMN_NAME_IDENTITY_DIFFERING_TABLES="+str(metadata_diff))
    print("SOURCE_EXCESS_ROWS_IN_SHARED_TABLES="+str(
        sum(max(0,old_map[k][0]-local_map[k][0]) for k in ids)))
    print("TARGET_EXCESS_ROWS_IN_SHARED_TABLES="+str(
        sum(max(0,local_map[k][0]-old_map[k][0]) for k in ids)))
    print("EIGHT_ORDINAL_SCOPE=17,39,60,69,70,71,78,139")
    print("ROW_COUNT_DIFFERING_TABLES="+str(count_diff))
    print("ROW_VALUE_MULTISETS_DIFFERING_TABLES="+str(value_diff))
    print("COLUMN_VALUE_DISTRIBUTION_DIFFERING_TABLES="+str(cell_diff))
    print("COLUMN_VALUE_DISTRIBUTION_DIFFERING_COLUMNS="+str(changed_columns))
    print("ROW_COMBINATION_ONLY_DIFFERING_TABLES="+str(combinations_only))
    print("DIFFERING_TABLE_ORDINAL_COLUMN_COUNTS="+(",".join(details) if details else "NONE"))
    print("EIGHT_TABLE_ROW_VALUE_FINGERPRINT="+
          ("MATCH_ADVISORY_ONLY" if same else "DIFFER_ADVISORY"))
    print("BOTH_SIDES_CONSISTENT_READ_ONLY_TRANSACTIONS=YES")
    print("SNAPSHOTS_SIMULTANEOUS=NO")
    print("OLD_SOURCE_MAY_HAVE_LIVE_CHANGES=YES")
    print("VALUE_DIFFERENCE_CAUSE=NOT_PROVEN")
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
