#!/usr/bin/env python3
"""P07: all three PENDING CloudPanel site roots, runtime and candidate DB links.

Read-only CP2 metadata, no HTTP handlers, source SSH, SQL queries or writes.
This is not file-content parity or Production/Cutover acceptance. The existing
14 staged site evidence and DB recovery archives are not rechecked here.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
SMOKE=HERE/"p07-14-site-local-http-fpm-smoke.py"
SMOKE_BLOB="af9784b44cdeec326b37dae27100e21225f83152"
BASE=HERE/"p07-17-site-staged-local-evidence.py"
BASE_BLOB="fe9387cadaa987faf11863ee1524b30e0a6aadbc"
ROOT=Path("/var/lib/vf-server-ops/server-migrations")
THREE=(
 ("ilovem3u8.kewaro.com","ORIGINAL17",
  "recovery-scratch-ilovem3u8","ISOLATED_SOURCE_READBACK_PASS",2),
 ("unzip.kewaro.com","LEGACY9",None,None,1),
 ("www3.m3u8.one","LAST2",
  "recovery-scratch-www3","ISOLATED_IMPORT_COMPLETED_NOT_VERIFIED",1),
)
class Block(Exception):pass
def need(ok,code):
    if not ok:raise Block(code)
def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def pinned(path,sha,name):
    need(path.is_file() and not path.is_symlink() and blob(path.read_bytes())==sha,
         "PINNED_"+name+"_BUNDLE_CHANGED")
    spec=importlib.util.spec_from_file_location("p07_pending_"+name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def private_record(path):
    try:st=path.lstat()
    except OSError:raise Block("PRIVATE_RECOVERY_STATE_MISSING") from None
    need(stat.S_ISREG(st.st_mode) and st.st_uid==0 and not st.st_mode&0o077
         and not path.is_symlink() and 0<st.st_size<1048576,
         "PRIVATE_RECOVERY_STATE_UNSAFE")
    try:obj=json.loads(path.read_text("utf-8"))
    except (UnicodeError,OSError,ValueError):
        raise Block("PRIVATE_RECOVERY_STATE_UNREADABLE") from None
    need(type(obj) is dict,"PRIVATE_RECOVERY_STATE_INVALID")
    return obj
def status_scope(base):
    states=[]
    seen={}
    for name,mid,count in base.JOBS:
        s=base.secure_state(ROOT/mid/"state.json")
        need(s.get("migration_id")==mid and s.get("schema")==base.SCHEMA
             and s.get("status")=="PREPARE_FAILED"
             and type(s.get("sites")) is list and len(s["sites"])==count
             and all(s.get(k) is False for k in (
                 "source_runtime_frozen","target_runtime_activated",
                 "dns_changed_by_p07","source_delete_allowed",
                 "existing_target_overwrite_allowed")),
             "MIGRATION_ID_OR_SAFETY_BOUNDARY_CHANGED")
        if name!="ORIGINAL17":
            need(s.get("cutover_prohibited") is True,
                 "CHILD_CUTOVER_PROTECTION_CHANGED")
        else:
            need(s.get("cutover_prohibited",False) is False,
                 "ORIGINAL_CUTOVER_GUARD_CHANGED")
        for site in s["sites"]:
            need(type(site) is dict and type(site.get("domain")) is str,
                 "MIGRATION_SITE_INVALID")
            seen[site["domain"]]=(name,site)
        states.append(s)
    need(states[1].get("partial_parent_migration_id")==base.JOBS[0][1]
         and states[2].get("partial_parent_migration_id")==base.JOBS[1][1],
         "PARENT_MIGRATION_CHAIN_CHANGED")
    need(all(s.get("target_server_identity")==states[0].get("target_server_identity")
             for s in states[1:]),"CP2_MIGRATION_TARGET_IDENTITY_CHANGED")
    need(set(seen)==base.EXPECTED_STAGED|base.EXPECTED_PENDING
         and {n for n,(label,s) in seen.items() if s.get("stage_status")=="PENDING"}
              ==base.EXPECTED_PENDING
         and {n for n,(label,s) in seen.items() if s.get("stage_status")=="PULLED_STAGED"}
              ==base.EXPECTED_STAGED,
         "17_SITE_FINAL_SCOPE_CHANGED")
    return seen
def scratch_link(site,mid,recorddir,expected_status,cp_dbs):
    if recorddir is None:
        need(type(cp_dbs) is list and len(cp_dbs)==1,
             "UNZIP_REGISTERED_DB_SCOPE_CHANGED")
        need((site.get("mysql_databases") or [])==cp_dbs,
             "UNZIP_SOURCE_TARGET_DB_BINDING_CHANGED")
        return "EXISTING_CP2_DB"
    root=ROOT/mid/recorddir
    need(root.is_dir() and not root.is_symlink()
         and root.stat().st_uid==0 and not root.stat().st_mode&0o077,
         "ISOLATED_RECOVERY_DIRECTORY_UNSAFE")
    rec=private_record(root/"status.json")
    need(rec.get("original_site")==site["domain"]
         and rec.get("migration_id")==mid
         and rec.get("status")==expected_status
         and rec.get("cutover_allowed") is False
         and rec.get("site_config_modified") is False
         and rec.get("dns_changed") is False
         and rec.get("source_frozen") is False
         and rec.get("existing_target_database_modified") is False,
         "ISOLATED_RECOVERY_PROTECTION_CHANGED")
    scratch=(rec.get("resume_scratch_database") if site["domain"]=="www3.m3u8.one"
             else rec.get("scratch_database"))
    need(type(scratch) is str and re.fullmatch("p07scratch-[a-f0-9]{12}",scratch)
         and type(cp_dbs) is list and len(cp_dbs)==(
             1 if site["domain"]=="www3.m3u8.one" else 2)
         and scratch in cp_dbs and len(set(cp_dbs))==len(cp_dbs),
         "ISOLATED_DATABASE_NOT_IN_CLOUDPANEL")
    return "ISOLATED_SOURCE_SNAPSHOT"
def assess(smoke,site,target):
    src=site.get("runtime")
    runtime=target.get("runtime")
    match=(type(src) is dict and type(runtime) is dict
           and src.get("type")==runtime.get("type")
           and src.get("version")==runtime.get("version"))
    entry=smoke.safe_entry_metadata(target)
    present=bool(entry.get("index.php") or entry.get("index.html"))
    vhost,endpoints=smoke.vhost(site["domain"])
    kind=runtime.get("type") if type(runtime) is dict else None
    version=runtime.get("version") if type(runtime) is dict else None
    if kind=="php" and type(version) is str and smoke.PHP.fullmatch(version):
        fpm=smoke.service("php"+version+"-fpm")
        backend=smoke.backend_status(endpoints,version,target["site_user"])
    else:
        fpm="NOT_APPLICABLE" if kind!="php" else "UNKNOWN"
        backend="NOT_APPLICABLE" if kind!="php" else "UNKNOWN"
    php_ok=(fpm=="ACTIVE" and backend in (
        "TCP_POOL_AND_LISTENER_CONFIRMED","UNIX_POOL_AND_SOCKET_CONFIRMED"))
    evidence_ok=bool(match and present and vhost=="FOUND" and
                     (php_ok if kind=="php" else True))
    return {"SITE_FILES_ENTRY_PRESENT":"YES" if present else "NO",
            "PHP_OR_OTHER_RUNTIME_MATCH":"YES" if match else "NO",
            "NGINX_VHOST":vhost,
            "FPM_SERVICE":fpm,
            "FPM_BACKEND":backend,
            "SITE_FILES_FULL_PARITY":"NOT_VERIFIED",
            "APPLICATION_DB_CONFIG_MAPPING":"NOT_VERIFIED",
            "HTTP_APP_FUNCTIONALITY":"NOT_TESTED",
            "LOCAL_FILES_VHOST_FPM_EVIDENCE":("MATCH" if evidence_ok else "GAP")}
def scan(base,smoke):
    items=status_scope(base)
    inventory=smoke.inventory()
    entries=[]
    for domain,label,recorddir,status,dbcount in THREE:
        found=items.get(domain)
        need(found is not None and found[0]==label and
             found[1].get("stage_status")=="PENDING",
             "PENDING_SITE_IDENTITY_CHANGED")
        site=found[1]
        rows=inventory.get(domain,[])
        need(len(rows)==1 and rows[0].get("site_user")==site.get("site_user"),
             "CP2_SITE_USER_OR_INVENTORY_CHANGED")
        target=rows[0]
        bound=scratch_link(site,dict((a,b) for a,b,c in base.JOBS)[label],
                           recorddir,status,target.get("mysql_databases"))
        result=assess(smoke,site,target)
        entries.append((domain,bound,result))
    return entries
def main():
    need(os.geteuid()==0 and sys.argv[1:]==["--check-pending-three-runtime-bindings-read-only"],
         "EXPLICIT_PENDING_THREE_READONLY_ARG_REQUIRED")
    base=pinned(BASE,BASE_BLOB,"BASE")
    smoke=pinned(SMOKE,SMOKE_BLOB,"SMOKE")
    rows=scan(base,smoke)
    print("PROBE=P07_PENDING_THREE_WEB_RUNTIME_AND_DB_CANDIDATE",flush=True)
    print("STAGED_OTHER_SITES=14_PREVIOUS_EVIDENCE_NOT_RESCANNED",flush=True)
    print("PENDING_SITE_COUNT="+str(len(rows)),flush=True)
    gaps=0
    for domain,db,result in rows:
        print("SITE="+domain+" DATABASE_CANDIDATE="+db+" "+
              " ".join(k+"="+str(v) for k,v in result.items()),flush=True)
        gaps+=int(result["LOCAL_FILES_VHOST_FPM_EVIDENCE"]!="MATCH")
    print("WEB_RUNTIME_GAP_COUNT="+str(gaps),flush=True)
    print("CLOUDPANEL_SITE_DB_CONFIGURATION=NOT_MODIFIED",flush=True)
    print("SOURCE_VPS_CONTACTED=NO",flush=True)
    print("HTTP_REQUESTS=NONE",flush=True)
    print("DATABASE_SQL_QUERIES_AND_WRITES=NONE",flush=True)
    print("DNS_OR_CRON_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0 if gaps==0 else 13
if __name__=="__main__":
    try:raise SystemExit(main())
    except Block as e:
        print("BLOCKED="+str(e),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=UNVERIFIED_PENDING_THREE_RUNTIME",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
