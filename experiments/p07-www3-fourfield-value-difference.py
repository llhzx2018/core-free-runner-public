#!/usr/bin/env python3
"""P07 www3 three-table field-type advisory, read-only on old VPS and CP2.

Both hosts are scanned using the SAME pinned worker, under independent
REPEATABLE READ consistent-snapshot, READ ONLY transactions. The snapshots are
NOT simultaneous and old VPS is live; MATCH is not original export/cutover PASS.
Only count labels reach operator output. No secret, raw row or SQL is printed.
"""
from __future__ import annotations
import base64
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
    ("p07-www3-three-table-type-worker.py","4cb12c1fcd7c7d03c6b5fe6c95ffc72e946671ac"),
    ("p07-www3-fourfield-values-worker.py","3be0d443561a90b6e66de1470224c72c5552bab5"),
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
    VALUE_WORKER,VALUE_WORKER_CODE=get_file(*FILES[2])
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
            or lines["TARGETED_ORDINALS"]!="39,60,69"
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
    if (type(ordinal_ids) is not dict or set(ordinal_ids)!={"39","60","69"}
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


def parse_value_output(raw,mode,selection,expected_rows):
    if type(raw) is not str or not 0<len(raw)<=900000:
        stop("FOURFIELD_VALUE_OUTPUT_SIZE_UNVERIFIED")
    lines={}
    fields={"MODE","TARGETED_TABLES","TARGETED_COLUMNS","TARGETED_ROWS",
            "VALUES","READ_ONLY_TRANSACTION","CONTENT_COMPARISON_ADVISORY_ONLY"}
    for line in raw.splitlines():
        if "=" not in line:stop("FOURFIELD_VALUE_OUTPUT_INVALID")
        k,v=line.split("=",1)
        if k not in fields or k in lines:stop("FOURFIELD_VALUE_OUTPUT_INVALID")
        lines[k]=v
    if (set(lines)!=fields or lines["MODE"]!=mode or lines["TARGETED_TABLES"]!="3"
            or lines["TARGETED_COLUMNS"]!="4" or
            lines["READ_ONLY_TRANSACTION"]!="YES" or
            lines["CONTENT_COMPARISON_ADVISORY_ONLY"]!="YES"):
        stop("FOURFIELD_VALUE_WORKER_SCOPE_INVALID")
    if not re.fullmatch("[0-9]{1,7}",lines["TARGETED_ROWS"]) or int(lines["TARGETED_ROWS"])!=expected_rows:
        stop("FOURFIELD_VALUE_ROW_COUNT_CHANGED")
    try:data=json.loads(lines["VALUES"])
    except (ValueError,TypeError):stop("FOURFIELD_VALUE_JSON_UNPROVEN")
    if type(data) is not dict or set(data)!=set(selection):
        stop("FOURFIELD_VALUE_TABLE_IDS_CHANGED")
    for tid,cols in data.items():
        if type(cols) is not dict or set(cols)!=set(selection[tid]):
            stop("FOURFIELD_VALUE_COLUMN_IDS_CHANGED")
        for cid,metrics in cols.items():
            if type(metrics) is not dict or set(metrics)!={"rows","nonnull","bytes","counts"}:
                stop("FOURFIELD_VALUE_METRICS_INVALID")
            rows,non_null,byte_sum,counts=(metrics[k] for k in ("rows","nonnull","bytes","counts"))
            if (any(type(x) is not int or not 0<=x<=1000000000 for x in
                    (rows,non_null,byte_sum)) or non_null>rows or
                    type(counts) is not dict or not 1<=len(counts)<=100000 or
                    any(type(k) is not str or not re.fullmatch("[a-f0-9]{64}",k)
                        or type(v) is not int or not 0<v<=rows
                        for k,v in counts.items()) or sum(counts.values())!=rows):
                stop("FOURFIELD_VALUE_COUNTS_INVALID")
    return data

def compare():
    if sys.argv[1:]!=["--compare-four-differing-field-values-read-only"]:
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
        target=subprocess.run(["python3","-B",str(WORKER),"target",base.DOMAIN,db,"--only-three-known-difference-tables"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,timeout=1900,check=False,text=True)
    except (OSError,subprocess.SubprocessError,UnicodeError):
        stop("CP2_READ_ONLY_CONTENT_WORKER_UNAVAILABLE")
    if target.returncode:
        stop("CP2_READ_ONLY_CONTENT_WORKER_FAILED")
    local,local_map,local_meta,local_ord=parsed(target.stdout,"TARGET")
    if expected_ddl!=157 or local["SCANNED_TABLES"]!=3:
        stop("TARGET_TABLE_SCOPE_CHANGED")
    try:
        source_code=WORKER_CODE.decode("utf-8","strict")
    except UnicodeError:stop("BUNDLE_WORKER_INVALID_UTF8")
    remote_cmd=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
        "PYTHONPATH="+base.SOURCE_RUNTIME+"/lib","python3","-B","-c",source_code,
        "source",base.DOMAIN,origin[0],"--only-three-known-difference-tables"])
    try:
        response=migration.source_remote(state["source"],remote_cmd,
            timeout=1900,check=False)
    except Exception:
        stop("OLD_VPS_READ_ONLY_CONTENT_WORKER_UNAVAILABLE")
    if response.returncode:
        stop("OLD_VPS_READ_ONLY_CONTENT_WORKER_FAILED")
    old,old_map,old_meta,old_ord=parsed(response.stdout,"SOURCE")
    if old_ord!=local_ord:stop("THREE_TABLE_IDENTITIES_DIFFER")
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
    if count_diff!=0 or value_diff!=3 or metadata_diff or missing_old or missing_target:
        stop("THREE_TABLE_DIFFERENCE_SCOPE_CHANGED")
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
    if differences!=4:
        stop("FOUR_FIELD_DIFFERENCE_SCOPE_CHANGED")
    # Second pass only: compare distinct value multiset hashes for the same
    # four fields, on precisely the three hashed-ordinal-identified tables.
    selection={}
    for tid in sorted(ids):
        if old_map[tid][1]==local_map[tid][1]:continue
        selection[tid]=sorted([cid for cid in old_map[tid][3]
            if old_map[tid][3][cid]!=local_map[tid][3][cid]])
    if sorted(len(cols) for cols in selection.values())!=[1,1,2]:
        stop("FOUR_FIELD_SELECTION_CHANGED")
    selector=base64.b64encode(json.dumps(selection,sort_keys=True,
        separators=(",",":")).encode("ascii")).decode("ascii")
    try:
        tgt=subprocess.run(["python3","-B",str(VALUE_WORKER),"target",base.DOMAIN,db,
            "--four-field-values-only",selector],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=1400,check=False,text=True)
    except (OSError,subprocess.SubprocessError,UnicodeError):
        stop("TARGET_FOURFIELD_READ_ONLY_WORKER_UNAVAILABLE")
    if tgt.returncode!=0:stop("TARGET_FOURFIELD_READ_ONLY_WORKER_FAILED")
    expected_tgt_rows=sum(local_map[t][0] for t in selection)
    target_values=parse_value_output(tgt.stdout,"TARGET",selection,expected_tgt_rows)
    try:
        source_code=VALUE_WORKER_CODE.decode("utf-8","strict")
    except UnicodeError:stop("FOURFIELD_VALUE_WORKER_CODE_UNVERIFIED")
    cmd=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
        "PYTHONPATH="+base.SOURCE_RUNTIME+"/lib",
        "python3","-B","-c",source_code,"source",base.DOMAIN,origin[0],
        "--four-field-values-only",selector])
    try:
        remote=migration.source_remote(state["source"],cmd,timeout=1400,check=False)
    except Exception:
        stop("SOURCE_FOURFIELD_READ_ONLY_WORKER_UNAVAILABLE")
    if remote.returncode!=0:stop("SOURCE_FOURFIELD_READ_ONLY_WORKER_FAILED")
    expected_src_rows=sum(old_map[t][0] for t in selection)
    source_values=parse_value_output(remote.stdout,"SOURCE",selection,expected_src_rows)
    field_deltas=[]
    from collections import Counter
    for tid in sorted(selection):
        for cid in sorted(selection[tid]):
            l=source_values[tid][cid]
            r=target_values[tid][cid]
            ls=Counter(l["counts"]);rs=Counter(r["counts"])
            source_only=sum((ls-rs).values())
            target_only=sum((rs-ls).values())
            # Only aggregate counts/lengths leave the process.
            field_deltas.append({
                "ordinal":reverse_ord[tid],
                "source_only":source_only,
                "target_only":target_only,
                "source_nonnull":l["nonnull"],
                "target_nonnull":r["nonnull"],
                "source_bytes":l["bytes"],
                "target_bytes":r["bytes"],
                "value_multiset_equal":source_only==target_only==0,
            })
    if len(field_deltas)!=4:
        stop("FOUR_FIELD_DELTA_CARDINALITY_UNVERIFIED")

    print("DIFFERING_FIELD_VALUE_OCCURRENCE_COUNTS=READY")
    print("FOUR_FIELD_VALUE_MULTISET_DIFFERING_FIELDS="+
          str(sum(not x["value_multiset_equal"] for x in field_deltas)))
    for j,item in enumerate(field_deltas,1):
        prefix="VALUE_DELTA_"+str(j)+"_"
        print(prefix+"TABLE_ORDINAL="+item["ordinal"])
        for key in ("source_only","target_only","source_nonnull","target_nonnull",
                    "source_bytes","target_bytes"):
            print(prefix+key.upper()+"="+str(item[key]))
    print("NO_RAW_COLUMN_VALUES_OR_DIGESTS_OUTPUT=YES")
    print("VALUE_DELTA_IS_ORIGINAL_SNAPSHOT_PARITY=NO")
    print("DIFFERING_FIELD_COUNT="+str(differences))
    print("DATA_TYPE_CHANGED_FIELD_COUNT="+str(type_mismatch))
    print("CHARSET_CHANGED_FIELD_COUNT="+str(charset_mismatch))
    print("COLLATION_CHANGED_FIELD_COUNT="+str(collation_mismatch))
    for i,item in enumerate(profiles,1):
        print("DIFFERING_FIELD_"+str(i)+"_TABLE_ORDINAL="+item["table_ordinal"])
        print("DIFFERING_FIELD_"+str(i)+"_TYPE="+
              item["type_source"]+"/"+item["type_target"])
        print("DIFFERING_FIELD_"+str(i)+"_CHARSET="+
              item["charset_source"]+"/"+item["charset_target"])
        print("DIFFERING_FIELD_"+str(i)+"_COLLATION="+
              item["collation_source"]+"/"+item["collation_target"])
        print("DIFFERING_FIELD_"+str(i)+"_NULLABLE="+
              item["nullability_source"]+"/"+item["nullability_target"])
        print("DIFFERING_FIELD_"+str(i)+"_PRECISION="+
              ",".join(item["precision_source"])+"/"+
              ",".join(item["precision_target"]))
    print("CURRENT_SOURCE_TARGETED_TABLES="+str(old["SCANNED_TABLES"]))
    print("RESTORED_TARGETED_TABLES="+str(local["SCANNED_TABLES"]))
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
    print("THREE_TABLE_ROW_VALUE_FINGERPRINT="+
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
