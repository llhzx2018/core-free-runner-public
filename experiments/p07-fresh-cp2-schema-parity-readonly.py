#!/usr/bin/env python3
"""Read-only 11-category MySQL/CloudPanel incident SQL-schema comparison.

Existing source/target SQL data equality is advisory; this supplies separate
portable INFORMATION_SCHEMA metadata evidence, not permission to resume or
cross-engine DDL semantic equivalence.
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
HERE=Path(__file__).resolve().parent
PINNED={
  "p07-fresh-cp2-ilovem3u8-parity-readonly.py":"0afa49dc5c48b8be356166ea1a9fc99d8601f76b",
  "p07-two-pending-live-db-parity.py":"0b6ee5061909115de6f57b5d933244de3a7a79fa",
  "p07-two-pending-live-db-worker.py":"c63cd3513c773678a6162b50f8a93d35fe9160b6",
  "p07-fresh-cp2-schema-readonly-worker.py":"fe096172d1414749bd084f4cb7572c815db4db6b",
}
MID="pull-20261101T045943Z-923729a1"
DOMAIN="ilovem3u8.kewaro.com"
CATEGORIES=("TABLES","COLUMNS","INDEXES","CONSTRAINTS","KEY_USAGE",
           "FOREIGN_KEYS","TRIGGERS","VIEWS","ROUTINES","EVENTS","CHECKS")
class Block(Exception):pass
def need(x,label):
    if not x:raise Block(label)
def gitblob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def pinned(name):
    path=HERE/name
    try:
        need(path.is_file() and not path.is_symlink() and
             gitblob(path.read_bytes())==PINNED[name],
             "READONLY_COMPANION_BLOB_CHANGED")
    except OSError:raise Block("READONLY_COMPANION_UNAVAILABLE") from None
    return path
def load_incident():
    pinned("p07-two-pending-live-db-parity.py")
    pinned("p07-two-pending-live-db-worker.py")
    src=pinned("p07-fresh-cp2-ilovem3u8-parity-readonly.py")
    spec=importlib.util.spec_from_file_location("p07_clean_cp2_schema_incident",src)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pair=mod.load_pair()
    mod.check_incident(pair)
    return pair
def unpack(raw,mode):
    need(type(raw) is str and 0<len(raw)<=4*1024*1024 and raw.count("\n")<=2,
         "SCHEMA_METADATA_WORKER_OUTPUT_INVALID")
    try:obj=json.loads(raw)
    except ValueError:raise Block("SCHEMA_METADATA_WORKER_JSON_INVALID") from None
    need(type(obj) is dict and set(obj)=={"mode","categories"} and
         obj["mode"]==mode and type(obj["categories"]) is dict
         and set(obj["categories"])==set(CATEGORIES),
         "SCHEMA_METADATA_WORKER_SCOPE_INVALID")
    for category,row in obj["categories"].items():
        expected_keys={"count","objects","column_attributes"} if category=="COLUMNS" else {"count","objects"}
        need(type(row) is dict and set(row)==expected_keys and
             type(row["count"]) is int and 0<=row["count"]<=100000
             and type(row["objects"]) is dict and len(row["objects"])<=100000,
             "SCHEMA_METADATA_CATEGORY_INVALID")
        n=0
        for name,data in row["objects"].items():
            need(type(name) is str and re.fullmatch("[a-f0-9]{64}",name)
                 and type(data) is list and len(data)==2
                 and type(data[0]) is int and 0<data[0]<=100000
                 and type(data[1]) is str and re.fullmatch("[a-f0-9]{64}",data[1]),
                 "SCHEMA_METADATA_OBJECT_INVALID")
            n+=data[0]
        need(n==row["count"],"SCHEMA_METADATA_CATEGORY_ROW_MISMATCH")
        if category=="COLUMNS":
            cols=row["column_attributes"]
            properties={"ORDINAL_POSITION","DATA_TYPE","COLUMN_TYPE","IS_NULLABLE",
                "COLUMN_DEFAULT","EXTRA","CHARACTER_SET_NAME","COLLATION_NAME",
                "GENERATION_EXPRESSION"}
            need(type(cols) is dict and len(cols)==row["count"]==761,
                 "METADATA_COLUMN_PROFILE_COUNT_CHANGED")
            for cid,attrs in cols.items():
                need(type(cid) is str and re.fullmatch("[a-f0-9]{64}",cid)
                     and type(attrs) is dict and set(attrs)==properties,
                     "METADATA_COLUMN_PROFILE_ID_INVALID")
                for digests in attrs.values():
                    need(type(digests) is list and len(digests)==2
                         and all(type(v) is str and re.fullmatch("[a-f0-9]{64}",v)
                                 for v in digests),
                         "METADATA_COLUMN_PROFILE_DIGEST_INVALID")
    need(obj["categories"]["TABLES"]["count"]>=42 and
         obj["categories"]["COLUMNS"]["count"]>=42,
         "SCHEMA_METADATA_EXPECTED_TABLE_SCOPE_CHANGED")
    return obj["categories"]
def diff(src,dst):
    result={}
    for name in CATEGORIES:
        a,b=src[name]["objects"],dst[name]["objects"]
        common=a.keys()&b.keys()
        result[name]=(
            src[name]["count"],dst[name]["count"],
            len(a.keys()-b.keys()),len(b.keys()-a.keys()),
            sum(a[k]!=b[k] for k in common),
        )
    return result
def column_attribute_differences(source,target):
    left=source["COLUMNS"]["column_attributes"]
    right=target["COLUMNS"]["column_attributes"]
    common=left.keys() & right.keys()
    properties=("ORDINAL_POSITION","DATA_TYPE","COLUMN_TYPE","IS_NULLABLE",
        "COLUMN_DEFAULT","EXTRA","CHARACTER_SET_NAME","COLLATION_NAME",
        "GENERATION_EXPRESSION")
    output={}
    changed_columns=set()
    for attr in properties:
        raw=0
        normalized=0
        for cid in common:
            if left[cid][attr][0]!=right[cid][attr][0]:
                raw+=1
                changed_columns.add(cid)
            if left[cid][attr][1]!=right[cid][attr][1]:
                normalized+=1
        output[attr]=(raw,normalized)
    return len(left.keys()-right.keys()),len(right.keys()-left.keys()),len(changed_columns),output


def check(pair,engine,inventory):
    state,src_db,dst_db,runtime=pair.preflight(
        engine,inventory,DOMAIN,MID,17,7,42)
    need(dst_db is not None and type(src_db) is str and type(runtime) is str,
         "CLOUDPANEL_DB_MAPPING_UNPROVEN")
    worker=pinned("p07-fresh-cp2-schema-readonly-worker.py")
    base=pinned("p07-two-pending-live-db-worker.py")
    env={**os.environ,"PYTHONPATH":"/opt/vf-server-ops/lib",
         "PYTHONDONTWRITEBYTECODE":"1"}
    try:
        tgt=subprocess.run(["python3","-B",str(worker),"target",DOMAIN,dst_db],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            text=True,timeout=1200,stdin=subprocess.DEVNULL,env=env,check=False)
    except (OSError,subprocess.SubprocessError,UnicodeError):
        raise Block("CP2_SCHEMA_READONLY_WORKER_FAILED") from None
    need(tgt.returncode==0,"CP2_SCHEMA_READONLY_WORKER_FAILED")
    prefix=("import sys,types\n"
        "b=types.ModuleType('p07_injected_readonly_base')\n"
        "exec("+repr(base.read_text(encoding="utf-8"))+",b.__dict__)\n"
        "sys.modules['p07_injected_readonly_base']=b\n"
        "ns={'__name__':'__main__','__file__':'p07-fresh-cp2-schema-readonly-worker.py'}\n"
        "exec("+repr(worker.read_text(encoding="utf-8"))+",ns)\n")
    cmd=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
        "PYTHONPATH="+runtime+"/lib","python3","-B","-c",
        prefix,"source",DOMAIN,src_db])
    try:
        old=engine.source_remote(state["source"],cmd,timeout=1200,check=False)
    except Exception:raise Block("OLD_VPS_SCHEMA_READONLY_WORKER_FAILED") from None
    need(old.returncode==0,"OLD_VPS_SCHEMA_READONLY_WORKER_FAILED")
    left=unpack(old.stdout,"source")
    right=unpack(tgt.stdout,"target")
    return diff(left,right),column_attribute_differences(left,right)
def main():
    need(os.geteuid()==0 and sys.argv[1:]==[
         "--classify-new-cp2-dynamic-ddl-schema-read-only"],
         "EXPLICIT_STRUCTURAL_READ_ONLY_GATE_REQUIRED")
    pair=load_incident()
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import inventory
    import server_migration_pull as engine
    installed=Path("/opt/vf-server-ops/lib/server_migration_pull.py")
    need(installed.is_file() and gitblob(installed.read_bytes())==pair.ENGINE_BLOB,
         "RELEASE113_ENGINE_CHANGED")
    categories,column_detail=check(pair,engine,inventory)
    print("PROBE=NEW_CP2_CONDITIONAL_DDL_LIVE_METADATA",flush=True)
    print("SITE="+DOMAIN,flush=True)
    print("TARGET_DB_ALREADY_IMPORTED=YES",flush=True)
    print("METADATA_CATEGORIES="+str(len(CATEGORIES)),flush=True)
    issues=0
    for name,(s,t,missing_target,missing_source,changed) in categories.items():
        print("CATEGORY="+name+" SOURCE_RECORDS="+str(s)+" TARGET_RECORDS="+str(t)
           +" SOURCE_ONLY_OBJECTS="+str(missing_target)
           +" TARGET_ONLY_OBJECTS="+str(missing_source)
           +" CHANGED_OBJECTS="+str(changed),flush=True)
        issues+=int(s!=t or missing_target or missing_source or changed)
    print("DIFFERING_METADATA_CATEGORIES="+str(issues),flush=True)
    print("KNOWN_INFORMATION_SCHEMA_FIELDS="+
          ("MATCH_ADVISORY" if not issues else "DIFFER_ADVISORY"),flush=True)
    missing_target,missing_source,changed_cols,details=column_detail
    print("SOURCE_ONLY_COLUMN_IDENTITIES="+str(missing_target),flush=True)
    print("TARGET_ONLY_COLUMN_IDENTITIES="+str(missing_source),flush=True)
    print("COLUMNS_WITH_RAW_PROPERTY_DIFFERENCES="+str(changed_cols),flush=True)
    unresolved=0
    for attribute,(raw,normalized) in details.items():
        print("PROPERTY="+attribute+" RAW_CHANGED="+str(raw)
              +" NORMALIZED_CHANGED="+str(normalized)
              +" PRESENTATION_CANDIDATES="+str(raw-normalized),flush=True)
        unresolved+=normalized
    print("UNRESOLVED_COLUMN_PROPERTY_DIFFERENCES="+str(unresolved),flush=True)
    print("PRESENTATION_NORMALIZATION_GRANTS_SCHEMA_PASS=NO",flush=True)
    print("DYNAMIC_DDL_EXECUTION_SEMANTICS=NOT_VERIFIED",flush=True)
    print("CROSS_ENGINE_FULL_SCHEMA_PARITY=NOT_VERIFIED",flush=True)
    print("SOURCE_SNAPSHOT_AND_TARGET_READ_SIMULTANEOUS=NO",flush=True)
    print("BUSINESS_DATABASE_WRITES=NONE",flush=True)
    print("MIGRATION_STATUS_WRITES=NONE",flush=True)
    print("DNS_AND_CUTOVER_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0
if __name__=="__main__":
    try:raise SystemExit(main())
    except (Block,Exception) as error:
        print("BLOCKED="+(str(error) if type(error) is Block
                          else "SCHEMA_READONLY_EVIDENCE_UNVERIFIED"),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
