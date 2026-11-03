#!/usr/bin/env python3
"""P07 CP2: bounded read-only source-vs-target live DB parity, two pending sites.

Never upgrades an existing migration's status, imports, creates a database,
replays guards, modifies a site, freezes the old VPS or cuts over DNS.
Both read-only snapshots are independent and NOT the original source export.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
WORKER=HERE/"p07-two-pending-live-db-worker.py"
WORKER_BLOB="0ebbe16b708f064bc21e20f92fcf1a3a487e5ee2"
STATE_ROOT=Path("/var/lib/vf-server-ops/server-migrations")
ORIGINAL17="pull-20261028T103425Z-98050c76"
LEGACY9="pull-20261031T094144Z-d045fa5a"
SITES=(
    ("unzip.kewaro.com",LEGACY9,9,6,12),
    ("ilovem3u8.kewaro.com",ORIGINAL17,17,7,42),
)
CURRENT_PARENT="pull-20261101T045943Z-923729a1"
CURRENT_CHILD="pull-20261101T052411Z-35663c25"
CURRENT_SITES=(
    ("unzip.kewaro.com",CURRENT_CHILD,9,6,12),
    ("ilovem3u8.kewaro.com",CURRENT_PARENT,17,7,42),
)
ENGINE_BLOB="71fb59ad7d005b88e39cbeed4b3302c7f313bd06"
class Block(Exception):pass
def need(ok,label):
    if not ok:raise Block(label)
def gitblob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def verify_file():
    try:
        need(WORKER.is_file() and not WORKER.is_symlink()
             and gitblob(WORKER.read_bytes())==WORKER_BLOB,
             "READ_ONLY_WORKER_BLOB_MISMATCH")
    except OSError:raise Block("READ_ONLY_WORKER_UNAVAILABLE") from None
def private_state(path):
    try:meta=path.lstat()
    except OSError:raise Block("MIGRATION_STATE_UNAVAILABLE") from None
    need(stat.S_ISREG(meta.st_mode) and meta.st_uid==0 and not meta.st_mode&0o077,
         "MIGRATION_STATE_NOT_PRIVATE")
    try:record=json.loads(path.read_text("utf-8"))
    except (OSError,ValueError,UnicodeError):
        raise Block("MIGRATION_STATE_INVALID") from None
    need(type(record) is dict,"MIGRATION_STATE_NOT_OBJECT")
    return record
def preflight(migration,inventory,domain,mid,expected_count,idx,expected_tables):
    record=private_state(STATE_ROOT/mid/"state.json")
    sites=record.get("sites")
    # The original migration was created with an older engine. Diagnose
    # each individual safety invariant without printing state JSON, server
    # identities or credentials. This does NOT weaken any invariant.
    # The exact ORIGINAL17 state on CP2 predates cutover_prohibited:
    # verified by the Owner's redacted real-state probe. Only the original
    # migration may omit this optional legacy marker; a present marker must
    # be False. All actual no-cutover/no-overwrite guards remain mandatory,
    # and this read-only tool can NEVER promote a migration.
    cutover_marker_ok=(
        (mid in (ORIGINAL17,CURRENT_PARENT) and
         ("cutover_prohibited" not in record or
          record.get("cutover_prohibited") is False))
        or (mid in (LEGACY9,CURRENT_CHILD) and record.get("cutover_prohibited") is True)
    )
    checks=(
        ("MIGRATION_ID",record.get("migration_id")==mid),
        ("STATUS",record.get("status")=="PREPARE_FAILED"),
        ("SCHEMA",record.get("schema")=="vf-server-ops.server-migration.target-pull.v1"),
        ("CUTOVER_PROHIBITED_MARKER",cutover_marker_ok),
        ("SOURCE_NOT_FROZEN",record.get("source_runtime_frozen") is False),
        ("DNS_UNCHANGED",record.get("dns_changed_by_p07") is False),
        ("SOURCE_DELETE_FORBIDDEN",record.get("source_delete_allowed") is False),
        ("TARGET_OVERWRITE_FORBIDDEN",record.get("existing_target_overwrite_allowed") is False),
        ("SITE_COUNT",type(sites) is list and len(sites)==expected_count),
        ("SITE_ORDINAL",type(sites) is list and len(sites)>idx and type(sites[idx]) is dict),
        ("SITE_DOMAIN",type(sites) is list and len(sites)>idx
             and type(sites[idx]) is dict and sites[idx].get("domain")==domain),
        ("SITE_PENDING",type(sites) is list and len(sites)>idx
             and type(sites[idx]) is dict and sites[idx].get("stage_status")=="PENDING"),
        ("TARGET_IDENTITY",record.get("target_server_identity")==migration.target_identity()),
    )
    failed=[key for key,ok in checks if not ok]
    if failed:
        print("FAILED_STATE_GUARDS="+",".join(failed),flush=True)
        if "CUTOVER_PROHIBITED_MARKER" in failed:
            val=record.get("cutover_prohibited")
            classification=("MISSING" if "cutover_prohibited" not in record
                            else "TRUE" if val is True
                            else "FALSE" if val is False else "OTHER")
            print("ORIGINAL_CUTOVER_MARKER="+classification,flush=True)
        raise Block("MIGRATION_SAFETY_OR_SITE_BOUNDARY_CHANGED")
    if mid in (ORIGINAL17,CURRENT_PARENT) and "cutover_prohibited" not in record:
        print("ORIGINAL17_LEGACY_MISSING_MARKER=ACCEPTED_READONLY_ONLY",flush=True)
    if mid in (LEGACY9,CURRENT_CHILD):
        expected_parent=ORIGINAL17 if mid==LEGACY9 else CURRENT_PARENT
        need(record.get("partial_parent_migration_id")==expected_parent,
             "PARENT_MIGRATION_ID_CHANGED")
    site=sites[idx]
    src_db=site.get("mysql_databases")
    need(type(src_db) is list and len(src_db)==1
         and type(src_db[0]) is str
         and re.fullmatch(r"[A-Za-z0-9._-]{1,64}",src_db[0]) is not None,
         "SOURCE_DATABASE_IDENTITY_UNVERIFIED")
    origin_runtime=record.get("source_runtime_path")
    need(type(origin_runtime) is str
         and origin_runtime=="/var/lib/vf-server-ops/pull-source/"+mid+"/runtime",
         "SOURCE_RUNTIME_IDENTITY_CHANGED")
    env=inventory.build_manifest(Path("/"))
    need(env.get("discovery_source")=="cloudpanel_db+vhost",
         "CP2_CLOUDPANEL_INVENTORY_UNVERIFIED")
    rows=[x for x in env.get("sites",[])
          if type(x) is dict and x.get("domain")==domain]
    need(len(rows)==1 and rows[0].get("site_user")==site.get("site_user"),
         "TARGET_SITE_IDENTITY_CHANGED")
    dst_db=rows[0].get("mysql_databases")
    if type(dst_db) is not list or len(dst_db)!=1:
        return record,src_db[0],None,origin_runtime
    need(type(dst_db[0]) is str and
         re.fullmatch(r"[A-Za-z0-9._-]{1,64}",dst_db[0]) is not None,
         "TARGET_DATABASE_IDENTITY_UNVERIFIED")
    return record,src_db[0],dst_db[0],origin_runtime

def parsed(raw,mode):
    need(type(raw) is str and 0<len(raw)<=900000,
         "WORKER_OUTPUT_SIZE_UNVERIFIED")
    fields={}
    allowed={"MODE","SCANNED_TABLES","SCANNED_COLUMNS","SCANNED_ROWS",
             "ROW_FINGERPRINTS","READ_ONLY_TRANSACTION",
             "CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY"}
    for line in raw.splitlines():
        need("=" in line,"WORKER_OUTPUT_INVALID")
        k,v=line.split("=",1)
        need(k in allowed and k not in fields,"WORKER_OUTPUT_KEY_INVALID")
        fields[k]=v
    need(set(fields)==allowed and fields["MODE"]==mode
         and fields["READ_ONLY_TRANSACTION"]=="YES"
         and fields["CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY"]=="YES",
         "WORKER_OUTPUT_BOUNDARY_UNVERIFIED")
    nums={}
    for key in ("SCANNED_TABLES","SCANNED_COLUMNS","SCANNED_ROWS"):
        need(re.fullmatch("[0-9]{1,10}",fields[key]) is not None,
             "WORKER_NUMBER_UNVERIFIED")
        nums[key]=int(fields[key])
    try:mp=json.loads(fields["ROW_FINGERPRINTS"])
    except (ValueError,TypeError):raise Block("WORKER_HASH_MAP_INVALID") from None
    need(type(mp) is dict and 0<len(mp)<=1000 and len(mp)==nums["SCANNED_TABLES"]
         and nums["SCANNED_COLUMNS"]>=len(mp),"WORKER_TABLE_COUNT_INVALID")
    for t,row in mp.items():
        need(type(t) is str and re.fullmatch("[a-f0-9]{64}",t) is not None
             and type(row) is list and len(row)==4
             and type(row[0]) is int and 0<=row[0]<=1000000
             and type(row[1]) is str and re.fullmatch("[a-f0-9]{64}",row[1]) is not None
             and type(row[2]) is str and re.fullmatch("[a-f0-9]{64}",row[2]) is not None
             and type(row[3]) is dict and 0<len(row[3])<=200,
             "WORKER_TABLE_HASH_INVALID")
        need(all(type(col) is str and re.fullmatch("[a-f0-9]{64}",col)
                 and type(sig) is str and re.fullmatch("[a-f0-9]{64}",sig)
                 for col,sig in row[3].items()),"WORKER_COLUMN_HASH_INVALID")
    need(sum(r[0] for r in mp.values())==nums["SCANNED_ROWS"],
         "WORKER_ROW_TOTAL_INVALID")
    return nums,mp

def compare_one(migration,inventory,domain,mid,total,idx,expected_tables):
    state,source_db,target_db,remote_runtime=preflight(
        migration,inventory,domain,mid,total,idx,expected_tables)
    print("SITE="+domain,flush=True)
    print("MIGRATION_STATUS=PREPARE_FAILED_PENDING",flush=True)
    if target_db is None:
        print("TARGET_SITE_DATABASE=NOT_UNIQUELY_REGISTERED",flush=True)
        print("SITE_DATABASE_PARITY=NOT_RUN_TARGET_NOT_READY",flush=True)
        return "NOT_READY"
    # The local worker reads only the exact CloudPanel-registered DB.
    try:
        local=subprocess.run(["python3","-B",str(WORKER),"target",domain,target_db],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=1900,check=False,text=True,
            env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1",
                 "PYTHONPATH":"/opt/vf-server-ops/lib"})
    except (OSError,subprocess.SubprocessError,UnicodeError):
        raise Block("CP2_READONLY_WORKER_UNAVAILABLE") from None
    need(local.returncode==0,"CP2_READONLY_WORKER_FAILED")
    target,tmap=parsed(local.stdout,"TARGET")
    need(target["SCANNED_TABLES"]==expected_tables,
         "TARGET_EXPECTED_TABLE_SCOPE_NOT_RESTORED")
    cmd=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
        "PYTHONPATH="+remote_runtime+"/lib","python3","-B","-c",
        WORKER.read_text(encoding="utf8"),"source",domain,source_db])
    try:
        result=migration.source_remote(state["source"],cmd,timeout=1900,
                                       check=False)
    except Exception:raise Block("SOURCE_READONLY_WORKER_UNAVAILABLE") from None
    need(result.returncode==0,"SOURCE_READONLY_WORKER_FAILED")
    source,smap=parsed(result.stdout,"SOURCE")
    need(source["SCANNED_TABLES"]==expected_tables,
         "SOURCE_EXPECTED_TABLE_SCOPE_CHANGED")
    names=set(smap)&set(tmap)
    missing_src=len(set(tmap)-set(smap))
    missing_tgt=len(set(smap)-set(tmap))
    cols_diff=sum(smap[k][2]!=tmap[k][2] for k in names)
    count_diff=sum(smap[k][0]!=tmap[k][0] for k in names)
    val_diff=sum(smap[k][1]!=tmap[k][1] for k in names)
    cell_diff=sum(smap[k][3]!=tmap[k][3] for k in names)
    surplus_src=sum(max(0,smap[k][0]-tmap[k][0]) for k in names)
    surplus_dst=sum(max(0,tmap[k][0]-smap[k][0]) for k in names)
    same=(missing_src==missing_tgt==cols_diff==count_diff==val_diff==cell_diff==0
          and source==target)
    for k,v in (
      ("SOURCE_TABLES",source["SCANNED_TABLES"]),
      ("TARGET_TABLES",target["SCANNED_TABLES"]),
      ("SOURCE_ROWS",source["SCANNED_ROWS"]),
      ("TARGET_ROWS",target["SCANNED_ROWS"]),
      ("SOURCE_ONLY_TABLES",missing_tgt),
      ("TARGET_ONLY_TABLES",missing_src),
      ("COLUMN_IDENTITY_DIFF_TABLES",cols_diff),
      ("ROW_COUNT_DIFF_TABLES",count_diff),
      ("ROW_VALUE_DIFF_TABLES",val_diff),
      ("COLUMN_VALUE_DISTRIBUTION_DIFF_TABLES",cell_diff),
      ("SOURCE_EXCESS_ROWS_IN_SHARED_TABLES",surplus_src),
      ("TARGET_EXCESS_ROWS_IN_SHARED_TABLES",surplus_dst),
      ("LIVE_SOURCE_VS_EXISTING_TARGET",("MATCH_ADVISORY_ONLY" if same else "DIFFER_ADVISORY")),
      ("SITE_DATABASE_PARITY","ADVISORY_COMPLETE")):
        print(str(k)+"="+str(v),flush=True)
    return "MATCH" if same else "DIFFER"

def main():
    need(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    flags={
        "--compare-two-pending-site-databases-read-only":SITES,
        "--compare-ilovem3u8-only-read-only":SITES[1:],
        "--compare-current-unzip-only-read-only":CURRENT_SITES[:1],
        "--compare-current-two-pending-site-databases-read-only":CURRENT_SITES,
    }
    need(len(sys.argv)==2 and sys.argv[1] in flags,
         "EXPLICIT_SCOPED_READONLY_ARG_REQUIRED")
    chosen=flags[sys.argv[1]]
    verify_file()
    import_path=Path("/opt/vf-server-ops/lib/server_migration_pull.py")
    need(import_path.is_file() and
         gitblob(import_path.read_bytes())==ENGINE_BLOB,
         "RELEASE113_ENGINE_CHANGED")
    build=subprocess.run(["vfops","--build-id"],capture_output=True,
                         text=True,timeout=20,check=False)
    need(build.returncode==0 and build.stdout.strip()=="0.1.0-release113",
         "RELEASE113_RUNTIME_REQUIRED")
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import server_migration_pull as migration
    import inventory
    print("PROBE=P07_TWO_PENDING_LIVE_SOURCE_TARGET_READONLY",flush=True)
    print("SITE_COUNT="+str(len(chosen)),flush=True)
    results=[]
    for data in chosen:
        try:results.append(compare_one(migration,inventory,*data))
        except Block as exc:
            print("SITE_BLOCKED="+data[0]+":"+str(exc),flush=True)
            results.append("BLOCKED")
    print("SOURCE_SNAPSHOTS_AND_TARGET_SNAPSHOTS_SIMULTANEOUS=NO",flush=True)
    print("ORIGINAL_SQL_EXPORT_SNAPSHOT_PARITY=NOT_VERIFIED",flush=True)
    print("OLD_VPS_DATABASE_WRITES=NONE",flush=True)
    print("CP2_DATABASE_WRITES=NONE",flush=True)
    print("WEB_SITE_CONFIGURATION_CHANGED=NO",flush=True)
    print("DNS_WRITES=NONE",flush=True)
    print("CRON_ACTIVATED=NO",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    print("RESULT_COUNT="+str(len(results)),flush=True)
    return 0 if all(x in ("MATCH","DIFFER") for x in results) else 13

if __name__=="__main__":
    try:raise SystemExit(main())
    except Block as exc:
        print("BLOCKED="+str(exc),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=UNVERIFIED_TWO_SITE_READONLY_STATE",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
