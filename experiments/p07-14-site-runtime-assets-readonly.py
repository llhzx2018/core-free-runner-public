#!/usr/bin/env python3
"""P07 CP2: 14-site runtime/storage readiness observation, strictly local/readonly.

A PREPARE_FAILED migration cannot be certified PREPARED merely because some
sites report PULLED_STAGED. This probe does not activate PHP, Cron, Node, PM2,
run HTTP requests, open DB sessions, SSH, import or modify any site.
"""
from __future__ import annotations
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
from typing import Any

sys.dont_write_bytecode=True
THIS=Path(__file__).resolve()
COMPANION=THIS.with_name("p07-17-site-staged-local-evidence.py")
EXPECTED_BASELINE_BLOB="01b02934109458942e575d4e5a45d2d7f7ea37cf"
try:
    data=COMPANION.read_bytes()
except OSError:
    print("BLOCKED=STAGED_BASELINE_COMPANION_MISSING")
    raise SystemExit(13)
actual=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
if COMPANION.is_symlink() or actual!=EXPECTED_BASELINE_BLOB:
    print("BLOCKED=STAGED_BASELINE_COMPANION_IDENTITY_CHANGED")
    raise SystemExit(13)
spec=importlib.util.spec_from_file_location("p07_staged_baseline_verified",COMPANION)
baseline=importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

def block(label):
    raise baseline.Block(label)

def require(ok,label):
    if not ok:block(label)

def local_service_status(name):
    # Read-only systemctl; never starts, reloads or restarts the service.
    try:
        p=subprocess.run(["systemctl","is-active",name],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,text=True,timeout=6,check=False)
    except (OSError,subprocess.SubprocessError):
        return "UNKNOWN"
    return "ACTIVE" if p.returncode==0 and p.stdout.strip()=="active" else "INACTIVE_OR_UNKNOWN"

def runtime_status(source,target):
    s=source.get("runtime")
    t=target.get("runtime")
    if type(s) is not dict or type(t) is not dict:
        return "RUNTIME_INVENTORY_UNVERIFIED","UNKNOWN","UNKNOWN"
    kind=s.get("type")
    tk=t.get("type")
    if not isinstance(kind,str) or not isinstance(tk,str) or not kind or not tk:
        return "RUNTIME_INVENTORY_UNVERIFIED","UNKNOWN","UNKNOWN"
    if kind!=tk:
        return "RUNTIME_TYPE_DIFFER","UNKNOWN","UNKNOWN"
    if kind.lower()=="php":
        src=s.get("version")
        dst=t.get("version")
        if not isinstance(src,str) or not re.fullmatch(r"[0-9]+\.[0-9]+",src):
            return "PHP_SOURCE_VERSION_UNVERIFIED",str(src)[:16],"UNKNOWN"
        if src!=dst:
            return "PHP_VERSION_DIFFER",src,str(dst)[:16]
        # This is package evidence only; not a proof PHP-FPM serves requests.
        candidates=[Path("/usr/bin/php"+src),Path("/usr/sbin/php-fpm"+src),
                    Path("/usr/sbin/php"+src+"-fpm")]
        return ("PHP_VERSION_AND_BINARY_PRESENT" if any(p.is_file() for p in candidates)
                else "PHP_BINARY_MISSING"),src,str(dst)
    if kind.lower() in ("static","static_or_unknown"):
        return "STATIC_OR_UNKNOWN_REQUIRES_SMOKE","N/A","N/A"
    return "DECLARED_RUNTIME_MATCH_NEEDS_FUNCTIONAL_SMOKE","N/A","N/A"

def safe_asset_path(record):
    if type(record) is not dict:
        block("ASSET_RECORD_INVALID")
    value=record.get("path")
    user=record.get("user")
    if (not isinstance(value,str) or not isinstance(user,str)
            or not re.fullmatch("[a-z_][a-z0-9_-]{0,64}",user)
            or not value.startswith("/home/"+user+"/")
            or len(value)>1024 or ".." in Path(value).parts):
        block("ASSET_PATH_SCOPE_INVALID")
    return Path(value)

def stat_asset(p,kind):
    try:
        st=p.lstat()
    except OSError:
        return "MISSING"
    if stat.S_ISLNK(st.st_mode):
        return "SYMLINK_REVIEW_REQUIRED"
    if kind=="FILE":
        return "PRESENT" if stat.S_ISREG(st.st_mode) else "TYPE_DIFFER"
    if kind=="DIRECTORY":
        return "PRESENT" if stat.S_ISDIR(st.st_mode) else "TYPE_DIFFER"
    return "UNKNOWN_KIND"

def local_sqlite_header(p):
    try:
        if stat_asset(p,"FILE")!="PRESENT":return "MISSING_OR_UNSAFE"
        with p.open("rb") as handle:
            return "HEADER_PASS" if handle.read(16)==b"SQLite format 3\x00" else "HEADER_INVALID"
    except OSError:
        return "UNREADABLE"
    # Header check intentionally avoids SQLite connections and WAL side effects.

def asset_overview(states):
    out={}
    for state in states:
        label="ORIGINAL17" if len(state["sites"])==17 else ("LEGACY9" if len(state["sites"])==9 else "LAST2")
        staged_users={s.get("site_user") for s in state["sites"] if s.get("stage_status")=="PULLED_STAGED"}
        external=state.get("external_assets",[])
        sqlite=state.get("sqlite_assets",[])
        require(type(external) is list and type(sqlite) is list,"ASSET_LIST_FORMAT_CHANGED")
        counters={"external_present":0,"external_missing":0,"external_unknown":0,
                  "sqlite_header_pass":0,"sqlite_missing":0,"sqlite_unverified":0}
        for item in external:
            p=safe_asset_path(item)
            if item.get("user") not in staged_users:
                continue
            status=stat_asset(p,item.get("kind"))
            if status=="PRESENT":
                counters["external_present"]+=1
            elif status=="MISSING":counters["external_missing"]+=1
            else:counters["external_unknown"]+=1
        for item in sqlite:
            p=safe_asset_path(item)
            if item.get("user") not in staged_users:
                continue
            status=local_sqlite_header(p)
            if status=="HEADER_PASS":counters["sqlite_header_pass"]+=1
            elif status=="MISSING_OR_UNSAFE":counters["sqlite_missing"]+=1
            else:counters["sqlite_unverified"]+=1
        pending={}
        runtime=state.get("runtime_assets") or {}
        require(type(runtime) is dict,"RUNTIME_ASSET_RECORD_INVALID")
        for source_key,pending_key in (("system_cron","pending_system_cron"),
                                       ("user_cron","pending_user_cron"),("pm2","pending_pm2")):
            expected=runtime.get(source_key,[])
            ready=state.get(pending_key,[])
            require(type(expected) is list and type(ready) is list,
                    "RUNTIME_ASSET_LIST_FORMAT_INVALID")
            pending[source_key]={"expected":len(expected),"staged_count":len(ready),
                                  "local_staged_present":0}
            for row in ready:
                require(type(row) is dict,"PENDING_RUNTIME_ROW_INVALID")
                staged=row.get("staged_target")
                if (not isinstance(staged,str) or
                    not staged.startswith(str(baseline.ROOT/state["migration_id"]/"runtime")+"/")):
                    block("RUNTIME_STAGED_PATH_SCOPE_INVALID")
                if stat_asset(Path(staged),"FILE")=="PRESENT":
                    pending[source_key]["local_staged_present"]+=1
                require(row.get("activated") is False,"RUNTIME_ALREADY_ACTIVATED")
        out[label]=(counters,pending)
    return out

def diagnose():
    require(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    root=baseline.ROOT
    states=[]
    seen={}
    for label,mid,expected in baseline.JOBS:
        state=baseline.secure_state(root/mid/"state.json")
        require(state.get("schema")==baseline.SCHEMA and state.get("migration_id")==mid
                and state.get("status")=="PREPARE_FAILED"
                and type(state.get("sites")) is list and len(state["sites"])==expected,
                "MIGRATION_STATE_SCOPE_CHANGED")
        for key in ("source_runtime_frozen","target_runtime_activated",
                    "dns_changed_by_p07","source_delete_allowed",
                    "existing_target_overwrite_allowed"):
            require(state.get(key) is False,"MIGRATION_SAFETY_BOUNDARY_CHANGED")
        for s in state["sites"]:
            require(type(s) is dict and type(s.get("domain")) is str,
                    "SITE_INVENTORY_CHANGED")
            seen[s["domain"]]=(label,s)
        states.append(state)
    require(states[1].get("partial_parent_migration_id")==baseline.JOBS[0][1]
            and states[2].get("partial_parent_migration_id")==baseline.JOBS[1][1],
            "PARTIAL_PARENT_CHAIN_CHANGED")
    staged={domain for domain,(label,s) in seen.items()
            if s.get("stage_status")=="PULLED_STAGED"}
    pending={domain for domain,(label,s) in seen.items()
            if s.get("stage_status")=="PENDING"}
    require(staged==baseline.EXPECTED_STAGED and pending==baseline.EXPECTED_PENDING,
            "STAGED_PENDING_17_SITE_SCOPE_CHANGED")
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import inventory
    manifest=inventory.build_manifest(Path("/"))
    require(type(manifest) is dict and type(manifest.get("sites")) is list,
            "CLOUDPANEL_INVENTORY_INVALID")
    bydomain={}
    for r in manifest["sites"]:
        if type(r) is dict and type(r.get("domain")) is str:
            bydomain.setdefault(r["domain"],[]).append(r)
    print("BATCH=14_STAGED_RUNTIME_ASSET_READONLY")
    print("CP2_NGINX_SERVICE="+local_service_status("nginx"))
    runtime_gaps=0
    for domain in sorted(staged):
        if len(bydomain.get(domain,[]))!=1:
            block("SITE_INVENTORY_AMBIGUOUS")
        label,site=seen[domain]
        status,src,dst=runtime_status(site,bydomain[domain][0])
        if status in ("PHP_VERSION_DIFFER","PHP_BINARY_MISSING","RUNTIME_TYPE_DIFFER",
                      "PHP_SOURCE_VERSION_UNVERIFIED","RUNTIME_INVENTORY_UNVERIFIED"):
            runtime_gaps+=1
        print("SITE="+domain+" JOB="+label+" RUNTIME="+status+
              " PHP_SOURCE="+src+" PHP_TARGET="+dst)
    assets=asset_overview(states)
    for label in ("ORIGINAL17","LEGACY9","LAST2"):
        counts,pending_assets=assets[label]
        print("JOB="+label+" ASSETS="+",".join(k.upper()+":"+str(v) for k,v in sorted(counts.items())))
        for k,rec in pending_assets.items():
            print("JOB="+label+" RUNTIME_ASSET="+k.upper()+
                  " EXPECTED="+str(rec["expected"])+
                  " STAGED="+str(rec["staged_count"])+
                  " FILE_PRESENT="+str(rec["local_staged_present"]))
    print("PHP_INVENTORY_GAP_COUNT="+str(runtime_gaps))
    print("EXTERNAL_ASSET_AND_SQLITE_DATA_PARITY=NOT_VERIFIED")
    print("PHP_FPM_SOCKET_AND_APP_HTTP_SMOKE=NOT_VERIFIED")
    print("PHP_NODE_CRON_PM2_ACTIVATION=NOT_PERFORMED")
    print("OLD_SERVER_CONTACTED=NO")
    print("DATABASE_WRITES=NONE")
    print("DNS_WRITES=NONE")
    print("CUTOVER_ALLOWED=NO")
    return 0

if __name__=="__main__":
    try:raise SystemExit(diagnose())
    except baseline.Block as e:
        print("BLOCKED="+str(e));raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=RUNTIME_ASSET_LOCAL_DIAG_UNVERIFIED");raise SystemExit(13) from None
