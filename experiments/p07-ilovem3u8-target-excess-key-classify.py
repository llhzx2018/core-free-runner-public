#!/usr/bin/env python3
"""P07 ilovem3u8 one-table live PK conflict classifier; advisory, no mutations.

Determines whether the TWO CP2 excess rows are distinct target-only PKs, a
shared-key conflict, or schema/row drift. No raw values, names, hashes, SQL,
passwords or source credentials printed; ALL result data is count-only.
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
FILES={
  "p07-two-pending-live-db-parity.py":"0b6ee5061909115de6f57b5d933244de3a7a79fa",
  "p07-two-pending-live-db-worker.py":"c63cd3513c773678a6162b50f8a93d35fe9160b6",
  "p07-ilovem3u8-single-table-pk-worker.py":"264855bbc9e517ba72b8ad3cf91f409e551bc319",
}
DOMAIN="ilovem3u8.kewaro.com"
class Block(Exception): pass
def need(ok,code):
    if not ok:raise Block(code)
def gitblob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def load():
    for filename,want in FILES.items():
        path=HERE/filename
        need(path.is_file() and not path.is_symlink() and gitblob(path.read_bytes())==want,
             "PINNED_READONLY_SCRIPT_BUNDLE_CHANGED")
    spec=importlib.util.spec_from_file_location("p07_bound_pair",HERE/"p07-two-pending-live-db-parity.py")
    p=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)
    return p
def run(migration,state,worker,domain,src_db,dst_db,*args):
    need(domain==DOMAIN,"DOMAIN_CHANGED")
    need(worker in FILES,"WORKER_NOT_PINNED")
    code=(HERE/worker).read_text(encoding="utf8")
    try:
        if worker=="p07-two-pending-live-db-worker.py":
            local=subprocess.run(["python3","-B",str(HERE/worker),"target",domain,dst_db],
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                text=True,check=False,timeout=1900,
                env={**os.environ,"PYTHONPATH":"/opt/vf-server-ops/lib",
                     "PYTHONDONTWRITEBYTECODE":"1"})
            remote=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
                "PYTHONPATH="+state["source_runtime_path"]+"/lib",
                "python3","-B","-c",code,"source",domain,src_db])
        else:
            table_hash=args[0]
            local=subprocess.run(
                ["python3","-B",str(HERE/worker),"target",domain,dst_db,table_hash],
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                text=True,check=False,timeout=1900,
                env={**os.environ,"PYTHONPATH":"/opt/vf-server-ops/lib",
                     "PYTHONDONTWRITEBYTECODE":"1"})
            base_code=(HERE/"p07-two-pending-live-db-worker.py").read_text(encoding="utf8")
            payload=("import sys,types\n"
                "b=types.ModuleType('p07_injected_readonly_base')\n"
                "exec("+repr(base_code)+",b.__dict__)\n"
                "sys.modules['p07_injected_readonly_base']=b\n"
                "ns={'__name__':'__main__','__file__':'p07-ilovem3u8-single-table-pk-worker.py'}\n"
                "exec("+repr(code)+",ns)\n")
            remote=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
                "PYTHONPATH="+state["source_runtime_path"]+"/lib",
                "python3","-B","-c",payload,"source",domain,src_db,table_hash])
        need(local.returncode==0,"CP2_READONLY_WORKER_FAILED")
        old=migration.source_remote(state["source"],remote,timeout=1900,check=False)
        need(old.returncode==0,"OLD_VPS_READONLY_WORKER_FAILED")
        return old.stdout,local.stdout
    except (OSError,subprocess.SubprocessError,UnicodeError,KeyError):
        raise Block("READONLY_DATABASE_TRANSPORT_FAILED") from None
def parsed_keys(raw,mode,table_id):
    need(type(raw) is str and len(raw)<=1000000,
         "PK_WORKER_OUTPUT_SIZE_CHANGED")
    try:obj=json.loads(raw)
    except (TypeError,ValueError):raise Block("PK_WORKER_JSON_INVALID") from None
    need(type(obj) is dict and set(obj)=={
        "MODE","TABLE_ID","TABLES_SCANNED",
        "PRIMARY_KEY_COLUMN_COUNT","ROW_COUNT","ROWS","READ_ONLY_TRANSACTION"},
        "PK_WORKER_FORMAT_CHANGED")
    need(obj["MODE"]==mode and obj["TABLE_ID"]==table_id
         and obj["TABLES_SCANNED"]==42 and obj["READ_ONLY_TRANSACTION"]=="YES"
         and type(obj["PRIMARY_KEY_COLUMN_COUNT"]) is int
         and 0<obj["PRIMARY_KEY_COLUMN_COUNT"]<=8
         and type(obj["ROW_COUNT"]) is int and 0<=obj["ROW_COUNT"]<=10000,
         "PK_WORKER_IDENTITY_CHANGED")
    rows=obj["ROWS"]
    need(type(rows) is dict and len(rows)==obj["ROW_COUNT"]
         and all(type(k) is str and re.fullmatch("[0-9a-f]{64}",k)
                 and type(v) is str and re.fullmatch("[0-9a-f]{64}",v)
                 for k,v in rows.items()),
         "PK_WORKER_ROW_HASHES_INVALID")
    return obj
def decide(p,source_raw,target_raw,source_pk,target_pk):
    src,smap=p.parsed(source_raw,"SOURCE")
    dst,tmap=p.parsed(target_raw,"TARGET")
    need(src["SCANNED_TABLES"]==dst["SCANNED_TABLES"]==42
         and src["SCANNED_ROWS"]>=1 and dst["SCANNED_ROWS"]>=1
         and set(smap)==set(tmap) and
         all(smap[t][2]==tmap[t][2] and set(smap[t][3])==set(tmap[t][3])
             for t in smap),
         "FULL_SCHEMA_OR_TABLE_IDENTITIES_CHANGED")
    changed=[k for k in smap if smap[k][1]!=tmap[k][1]]
    different_counts=[k for k in smap if smap[k][0]!=tmap[k][0]]
    need(len(changed)==len(different_counts)==1
         and changed[0]==different_counts[0]
         and dst["SCANNED_ROWS"]-src["SCANNED_ROWS"]==2
         and tmap[changed[0]][0]-smap[changed[0]][0]==2,
         "ONE_TABLE_TWO_ROW_DRIFT_SCOPE_CHANGED")
    table_id=changed[0]
    left=parsed_keys(source_pk,"SOURCE",table_id)
    right=parsed_keys(target_pk,"TARGET",table_id)
    need(left["PRIMARY_KEY_COLUMN_COUNT"]==right["PRIMARY_KEY_COLUMN_COUNT"]
         and left["ROW_COUNT"]==smap[table_id][0]
         and right["ROW_COUNT"]==tmap[table_id][0],
         "PK_SNAPSHOT_ROW_COUNT_CHANGED")
    a,b=left["ROWS"],right["ROWS"]
    common=set(a)&set(b)
    only_src=len(set(a)-set(b))
    only_dst=len(set(b)-set(a))
    shared_changed=sum(a[k]!=b[k] for k in common)
    decision=("TARGET_ONLY_TWO_KEYS_WITH_IDENTICAL_SHARED_ROWS_ADVISORY"
              if only_src==0 and only_dst==2 and shared_changed==0
              else "UNRESOLVED_PRIMARY_KEY_OR_SHARED_ROW_DIFFERENCE")
    return {"SOURCE_TOTAL_ROWS":src["SCANNED_ROWS"],
       "TARGET_TOTAL_ROWS":dst["SCANNED_ROWS"],
       "DIFFERING_TABLE_COUNT":len(changed),
       "CONFLICT_TABLE_SOURCE_ROWS":len(a),
       "CONFLICT_TABLE_TARGET_ROWS":len(b),
       "PRIMARY_KEY_COLUMNS":left["PRIMARY_KEY_COLUMN_COUNT"],
       "SOURCE_ONLY_PRIMARY_KEYS":only_src,
       "TARGET_ONLY_PRIMARY_KEYS":only_dst,
       "SHARED_PRIMARY_KEYS":len(common),
       "SHARED_KEY_CHANGED_ROW_CONTENT":shared_changed,
       "CONFLICT_CLASSIFICATION":decision}
def main():
    need(os.geteuid()==0 and sys.argv[1:]==["--classify-ilovem3u8-target-excess-2-read-only"],
         "EXPLICIT_READONLY_CONFLICT_CLASSIFICATION_ARG_REQUIRED")
    p=load()
    p.verify_file()
    engine=Path("/opt/vf-server-ops/lib/server_migration_pull.py")
    need(engine.is_file() and gitblob(engine.read_bytes())==p.ENGINE_BLOB,
         "RELEASE113_ENGINE_CHANGED")
    build=subprocess.run(["vfops","--build-id"],capture_output=True,
        text=True,timeout=20,check=False)
    need(build.returncode==0 and build.stdout.strip()=="0.1.0-release113",
         "RELEASE113_RUNTIME_REQUIRED")
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import server_migration_pull as migration
    import inventory
    item=p.SITES[1]
    state,src_db,dst_db,remote=p.preflight(migration,inventory,*item)
    need(dst_db is not None,"TARGET_DATABASE_NOT_REGISTERED")
    src_raw,dst_raw=run(migration,state,"p07-two-pending-live-db-worker.py",DOMAIN,src_db,dst_db)
    src,smap=p.parsed(src_raw,"SOURCE")
    dst,tmap=p.parsed(dst_raw,"TARGET")
    changes=[tid for tid in smap if tid in tmap and smap[tid][1]!=tmap[tid][1]]
    need(len(changes)==1,"ONE_TABLE_SCOPE_CHANGED")
    selected=changes[0]
    a,b=run(migration,state,"p07-ilovem3u8-single-table-pk-worker.py",
            DOMAIN,src_db,dst_db,selected)
    result=decide(p,src_raw,dst_raw,a,b)
    print("PROBE=ILOVEM3U8_ONE_TABLE_PK_RECONCILIATION_ADVISORY",flush=True)
    for k,v in result.items():print(str(k)+"="+str(v),flush=True)
    print("SOURCE_AND_TARGET_SNAPSHOTS_SIMULTANEOUS=NO",flush=True)
    print("EXPORTED_SQL_SNAPSHOT_PARITY=NOT_VERIFIED",flush=True)
    print("EXCESS_ROWS_PRESERVED=YES",flush=True)
    print("DATA_WRITES=NONE",flush=True)
    print("MIGRATION_STATE_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0
if __name__=="__main__":
    try:raise SystemExit(main())
    except (Block,Exception) as e:
        # Do not echo exception text that might contain SQL or credentials.
        code=str(e) if isinstance(e,Block) else "UNVERIFIED_READONLY_CONFLICT_STATE"
        print("BLOCKED="+code,flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
