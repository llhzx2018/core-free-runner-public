#!/usr/bin/env python3
"""P07 isolated staged-asset installer, guarded and reversible by private copies.

Owner invokes on CP2. Validates 35-item private evidence and exact three
PREPARE_FAILED task states. Copies only 30 *currently absent* site assets
(17 external files/dirs + 13 verified SQLite snapshots) into CP2 site paths.
Five system Cron files remain private and inactive. No SSH, DB, DNS or live
source operations. Every installed path must be absent and is no-replace
renamed. Partial progress is retained for forensic recovery; never auto retry.
"""
from __future__ import annotations
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import sqlite3
import stat
import sys
import uuid

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
BASE=HERE/"p07-17-site-staged-local-evidence.py"
BASE_BLOB="fe9387cadaa987faf11863ee1524b30e0a6aadbc"
PRIVATE=Path("/var/lib/vf-server-ops/operator-recovery/p07-missing-assets-cb93c6b490a04068a5533f9cde0fcec7")
EXPECTED={"external":17,"sqlite":13,"cron":5}
TYPES={"external","sqlite","cron"}
HEX=re.compile(r"[0-9a-f]{64}$")
DOMAIN=re.compile(r"[a-z0-9][a-z0-9.-]{1,150}[a-z0-9]$")
USER=re.compile(r"[a-z_][a-z0-9_-]{0,64}$")
INVALID_NAME=re.compile(r"(?:^|/)\.\.(?:/|$)")
MAX_ITEMS=35
MAX_TOTAL_BYTES=40*1024**3
MAX_FILES=1000000
class Stop(Exception):pass
def must(ok,reason):
    if not ok:raise Stop(reason)
def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def baseline_module():
    must(BASE.is_file() and not BASE.is_symlink(),"BASELINE_BUNDLE_UNAVAILABLE")
    must(blob(BASE.read_bytes())==BASE_BLOB,"BASELINE_BUNDLE_CHANGED")
    s=importlib.util.spec_from_file_location("p07_fixed_baseline",BASE)
    m=importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
base=baseline_module()
def security(path,kind,root_only=True):
    try: st=path.lstat()
    except OSError:raise Stop("PRIVATE_EVIDENCE_NOT_FOUND") from None
    must(not stat.S_ISLNK(st.st_mode),"PRIVATE_EVIDENCE_SYMLINK")
    must(stat.S_ISDIR(st.st_mode) if kind=="dir" else stat.S_ISREG(st.st_mode),
         "PRIVATE_EVIDENCE_KIND_CHANGED")
    if root_only:
        must(st.st_uid==0 and not st.st_mode&0o022,
             "PRIVATE_EVIDENCE_OWNER_OR_PERMISSIONS_UNSAFE")
    return st
def hashfile(path):
    result=hashlib.sha256()
    with path.open("rb") as file:
        while True:
            chunk=file.read(1024*1024)
            if not chunk:break
            result.update(chunk)
    return result.hexdigest()
def snapshot_ok(path):
    try:
        con=sqlite3.connect(path.as_uri()+"?mode=ro&immutable=1",uri=True,timeout=5)
        try:
            return con.execute("PRAGMA quick_check").fetchone()==("ok",)
        finally:con.close()
    except sqlite3.Error:return False
def file_tree_integrity(path):
    """No symlinks or special files; bounded, hashes for unexpected local change."""
    st=path.lstat()
    must(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode),
         "PRIVATE_TREE_ROOT_UNSAFE")
    count=0
    size=0
    digest=hashlib.sha256()
    for parent,dirnames,filenames in os.walk(path,topdown=True,followlinks=False):
        dirnames.sort()
        filenames.sort()
        for name in dirnames+filenames:
            p=Path(parent)/name
            info=p.lstat()
            must(not stat.S_ISLNK(info.st_mode),"PRIVATE_TREE_SYMLINK_UNSUPPORTED")
            must(not info.st_mode&(stat.S_ISUID|stat.S_ISGID),
                 "PRIVATE_TREE_PRIVILEGED_BITS_UNSUPPORTED")
            isdir=stat.S_ISDIR(info.st_mode)
            must(isdir or stat.S_ISREG(info.st_mode),"PRIVATE_TREE_SPECIAL_FILE_UNSUPPORTED")
            count+=1
            size+=info.st_size if not isdir else 0
            must(count<=MAX_FILES and size<=MAX_TOTAL_BYTES,
                 "PRIVATE_TREE_SIZE_LIMIT")
            rel=p.relative_to(path).as_posix()
            digest.update(rel.encode("utf8")+b"\0"+(b"D" if isdir else b"F"))
            if not isdir:digest.update(bytes.fromhex(hashfile(p)))
    return count,size,digest.hexdigest()
def site_states():
    states=[]
    active={}
    for label,mid,expect in base.JOBS:
        path=base.ROOT/mid/"state.json"
        state=base.secure_state(path)
        must(state.get("schema")==base.SCHEMA and state.get("migration_id")==mid
             and state.get("status")=="PREPARE_FAILED"
             and type(state.get("sites")) is list and len(state["sites"])==expect,
             "MIGRATION_STATE_CHANGED")
        for flag in ("source_runtime_frozen","target_runtime_activated",
                     "dns_changed_by_p07","source_delete_allowed",
                     "existing_target_overwrite_allowed"):
            must(state.get(flag) is False,"MIGRATION_PROTECTION_CHANGED")
        states.append((label,mid,state,hashfile(path)))
        for site in state["sites"]:
            must(type(site) is dict and type(site.get("domain")) is str,
                 "SITE_ENTRY_INVALID")
            active[site["domain"]]=(label,site)
    must(states[1][2].get("partial_parent_migration_id")==base.JOBS[0][1]
         and states[2][2].get("partial_parent_migration_id")==base.JOBS[1][1],
         "PARENT_CHAIN_CHANGED")
    must({d for d,(_,s) in active.items() if s.get("stage_status")=="PULLED_STAGED"}
         ==base.EXPECTED_STAGED and
         {d for d,(_,s) in active.items() if s.get("stage_status")=="PENDING"}
         ==base.EXPECTED_PENDING,"STAGE_SCOPE_CHANGED")
    return states
def under_site(site,source):
    user=site.get("site_user")
    must(type(user) is str and USER.fullmatch(user),"SITE_USER_CHANGED")
    must(type(source) is str and len(source)<1024 and
         source.startswith("/home/"+user+"/") and
         not INVALID_NAME.search(source),
         "SITE_ASSET_PATH_UNSAFE")
    return Path(source),user
def expected_manifest_records(states):
    rows=[]
    for label,mid,state,_ in states:
        staged_users={s["site_user"] for s in state["sites"]
                      if s["stage_status"]=="PULLED_STAGED"}
        for category,key in (("external","external_assets"),("sqlite","sqlite_assets")):
            entries=state.get(key,[])
            must(type(entries) is list,"ASSET_INVENTORY_FORMAT_CHANGED")
            for row in entries:
                must(type(row) is dict,"ASSET_RECORD_INVALID")
                if row.get("user") not in staged_users:continue
                user=row["user"]
                source,_=under_site({"site_user":user},row.get("path"))
                rows.append((label,category,str(source),user,row))
        runtime=state.get("runtime_assets") or {}
        must(type(runtime) is dict and type(runtime.get("system_cron",[])) is list,
             "CRON_INVENTORY_CHANGED")
        for row in runtime.get("system_cron",[]):
            must(type(row) is dict and type(row.get("path")) is str and
                 re.fullmatch(r"/etc/cron\.d/[A-Za-z0-9_.-]+",row["path"]),
                 "CRON_INVENTORY_SCOPE_CHANGED")
            rows.append((label,"cron",row["path"],"root",row))
    totals={key:sum(r[1]==key for r in rows) for key in EXPECTED}
    must(totals==EXPECTED and len(rows)==MAX_ITEMS,
         "EXPECTED_35_ITEM_SCOPE_CHANGED")
    keys=[(a,b,c) for a,b,c,_,_ in rows]
    must(len(keys)==len(set(keys)),"ASSET_SOURCE_INVENTORY_DUPLICATE")
    return rows
def check_parents(path,user,allow_missing=False):
    parts=path.parts
    must(path.is_absolute() and parts[1]=="home"
         and len(parts)>=4 and parts[2]==user,"DESTINATION_OUT_OF_USER_HOME")
    for parent in reversed(list(path.parents)):
        if parent==Path("/"):continue
        try:st=parent.lstat()
        except FileNotFoundError:
            if allow_missing:continue
            raise Stop("TARGET_PARENT_MISSING") from None
        must(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode),
             "TARGET_PARENT_SYMLINK_OR_NONDIR")
def check_manifest():
    security(PRIVATE,"dir")
    manifest_path=PRIVATE/"private-manifest.json"
    st=security(manifest_path,"file")
    must(st.st_size<1024*1024 and not st.st_mode&0o077,
         "PRIVATE_MANIFEST_NOT_PRIVATE")
    try:manifest=json.loads(manifest_path.read_text(encoding="utf8"))
    except (ValueError,OSError,UnicodeError):raise Stop("PRIVATE_MANIFEST_INVALID") from None
    must(type(manifest) is dict and
         manifest.get("status")=="PRIVATE_STAGING_ONLY" and
         manifest.get("cutover_allowed") is False and
         manifest.get("site_files_materialized") is False and
         manifest.get("counts")==EXPECTED and
         type(manifest.get("records")) is list and
         len(manifest["records"])==MAX_ITEMS,
         "PRIVATE_MANIFEST_SCOPE_CHANGED")
    states=site_states()
    inventory=expected_manifest_records(states)
    expected={(a,b,c):(user,row) for a,b,c,user,row in inventory}
    seen=set()
    approved=[]
    total_size=0
    for rec in manifest["records"]:
        must(type(rec) is dict and
             type(rec.get("category")) is str and rec["category"] in TYPES and
             type(rec.get("job")) is str and
             type(rec.get("source_path")) is str,
             "PRIVATE_RECORD_INVALID")
        key=(rec["job"],rec["category"],rec["source_path"])
        must(key in expected and key not in seen,
             "PRIVATE_RECORD_UNEXPECTED_OR_DUPLICATE")
        seen.add(key)
        user,record=expected[key]
        raw=rec.get("private_path")
        must(type(raw) is str and len(raw)<1024 and
             raw.startswith(str(PRIVATE)+"/"),"PRIVATE_RECORD_PATH_ESCAPE")
        path=Path(raw)
        must(PRIVATE in path.parents and len(path.relative_to(PRIVATE).parts)==2
             and path.parts[-2]==rec["category"],"PRIVATE_RECORD_PATH_LAYOUT_CHANGED")
        stored_hash=rec.get("sha256")
        if rec["category"]=="external":
            result=rec.get("result")
            must(result in ("DIRECTORY_TRANSFERRED_NO_BYTE_PARITY","FILE_TRANSFERRED_HASHED"),
                 "EXTERNAL_COPY_EVIDENCE_CHANGED")
            if result=="DIRECTORY_TRANSFERRED_NO_BYTE_PARITY":
                security(path,"dir",root_only=False)
                count,size,content_hash=file_tree_integrity(path)
                must(stored_hash is None,"DIRECTORY_HASH_UNEXPECTED")
            else:
                security(path,"file",root_only=False)
                must(type(stored_hash) is str and HEX.fullmatch(stored_hash) and
                     hashfile(path)==stored_hash,"PRIVATE_FILE_SHA256_CHANGED")
                size=path.stat().st_size
            must(record.get("kind") in (None,"FILE","DIRECTORY",
                                       "file","directory"),
                 "SOURCE_ASSET_KIND_UNEXPECTED")
            if record.get("kind") in ("FILE","DIRECTORY"):
                must((result=="FILE_TRANSFERRED_HASHED" if record["kind"]=="FILE"
                      else result=="DIRECTORY_TRANSFERRED_NO_BYTE_PARITY"),
                     "EXTERNAL_KIND_CHANGED")
        else:
            security(path,"file",root_only=False)
            must(type(stored_hash) is str and HEX.fullmatch(stored_hash) and
                 hashfile(path)==stored_hash,"PRIVATE_FILE_SHA256_CHANGED")
            size=path.stat().st_size
            if rec["category"]=="sqlite":
                must(rec.get("result")=="SQLITE_SNAPSHOT_PRIVATE_VERIFIED"
                     and snapshot_ok(path),"SQLITE_SNAPSHOT_INTEGRITY_FAILED")
            else:
                must(rec.get("result")=="CRON_PRIVATE_NOT_ACTIVATED"
                     and rec.get("scope")=="SYSTEM_CRON_NOT_ACTIVATED",
                     "SYSTEM_CRON_STAGE_BOUNDARY_CHANGED")
        total_size+=size
        must(total_size<=MAX_TOTAL_BYTES,"TOTAL_PRIVATE_ASSET_SIZE_LIMIT")
        if rec["category"]!="cron":
            target,site_user=under_site({"site_user":user},rec["source_path"])
            check_parents(target,site_user,allow_missing=True)
            must(not os.path.lexists(target),"TARGET_ALREADY_EXISTS_NO_OVERWRITE")
            approved.append((rec,path,target,site_user))
    must(seen==set(expected),"PRIVATE_RECORDS_NOT_COMPLETE")
    must(len(approved)==30,"SITE_INSTALL_COUNT_CHANGED")
    targets=[str(t) for _,_,t,_ in approved]
    must(len(set(targets))==len(targets),"MULTIPLE_RECORDS_SHARE_TARGET")
    for i,t in enumerate(targets):
        must(not any(t.startswith(q+"/") or q.startswith(t+"/") for q in targets[i+1:]),
             "TARGET_NESTED_PATH_CONFLICT")
    return states,approved,total_size

def rename_noreplace(source,target):
    libc=ctypes.CDLL(None,use_errno=True)
    func=getattr(libc,"renameat2",None)
    must(func is not None,"ATOMIC_NOREPLACE_UNAVAILABLE")
    func.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    func.restype=ctypes.c_int
    src=os.fsencode(str(source))
    dst=os.fsencode(str(target))
    rc=func(-100,src,-100,dst,1)
    if rc!=0:
        errno=ctypes.get_errno()
        raise Stop("ATOMIC_INSTALL_REFUSED_ERRNO_"+str(errno))
def ensure_parents(target,user,uid,gid):
    # Only absent child directories under the original CloudPanel user home.
    home=Path("/home")/user
    must(home.is_dir() and not home.is_symlink(),"SITE_HOME_INVALID")
    missing=[]
    for p in reversed(list(target.parent.parents)):
        if p==home:break
    ptr=home
    rel=target.parent.relative_to(home)
    for part in rel.parts:
        ptr=ptr/part
        if os.path.lexists(ptr):
            st=ptr.lstat()
            must(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode),
                 "TARGET_PARENT_NOT_SAFE")
        else:
            ptr.mkdir(mode=0o750)
            os.chown(ptr,uid,gid)
            missing.append(str(ptr))
    return missing
def ownership(tree,uid,gid,sqlite_mode=None):
    if tree.is_dir():
        for parent,dirs,files in os.walk(tree,topdown=True,followlinks=False):
            for item in dirs+files:
                p=Path(parent)/item
                st=p.lstat()
                must(not stat.S_ISLNK(st.st_mode) and
                     (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)),
                     "TEMP_COPY_SPECIAL_FILE_CHANGED")
                os.chown(p,uid,gid,follow_symlinks=False)
        os.chown(tree,uid,gid,follow_symlinks=False)
    else:
        os.chown(tree,uid,gid,follow_symlinks=False)
        if sqlite_mode is not None:os.chmod(tree,sqlite_mode)
def do_install():
    must(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    must(sys.argv[1:]==["--install-only-30-absent-site-assets"],
         "EXPLICIT_30_SITE_ASSETS_INSTALL_ARGUMENT_REQUIRED")
    states,approved,total_size=check_manifest()
    must(shutil.disk_usage("/home").free>2*total_size+1024**3,
         "INSUFFICIENT_CP2_INSTALL_SPACE")
    print("PRIVATE_MANIFEST_35_35=PASS",flush=True)
    print("SITE_INSTALL_TARGETS_MISSING=30",flush=True)
    print("CRON_KEPT_PRIVATE=5",flush=True)
    print("APPROVED_COPY_SIZE_MIB="+str((total_size+1024**2-1)//1024**2),flush=True)
    print("INSTALL_BOUNDARY=CP2_NEW_EMPTY_SITE_PATHS_ONLY",flush=True)
    progress=[]
    for idx,(rec,private,target,user) in enumerate(approved,1):
        account=pwd.getpwnam(user)
        uid,gid=account.pw_uid,account.pw_gid
        ensure_parents(target,user,uid,gid)
        check_parents(target,user)
        must(not os.path.lexists(target),"TARGET_CHANGED_DURING_INSTALL")
        temp=target.parent/(".p07-uninstalled-"+uuid.uuid4().hex)
        must(not os.path.lexists(temp),"TEMP_INSTALL_COLLISION")
        # Do not remove this temp on failure. The operator must inspect it.
        if private.is_dir():
            shutil.copytree(private,temp,symlinks=False)
            ownership(temp,uid,gid)
            must(file_tree_integrity(temp)[2]==file_tree_integrity(private)[2],
                 "DIRECTORY_STAGED_COPY_CHANGED")
        else:
            shutil.copy2(private,temp,follow_symlinks=False)
            mode=int(next((row.get("mode",0o600) for label,mid,state,h in states
                for row in state.get("sqlite_assets",[])
                if rec["category"]=="sqlite" and row.get("path")==rec["source_path"]),
                0o600))
            must(0<=mode<=0o777,"SQLITE_MODE_UNSAFE")
            ownership(temp,uid,gid,mode if rec["category"]=="sqlite" else None)
            must(hashfile(temp)==rec["sha256"],"FILE_COPY_SHA256_MISMATCH")
        # Linux no-replace rename, so concurrent creation cannot be overwritten.
        rename_noreplace(temp,target)
        progress.append(str(target))
        print("INSTALLED_ASSET="+str(idx)+" CATEGORY="+rec["category"].upper()+
              " STATUS=NEW_ONLY_SHA_VERIFIED",flush=True)
    for label,mid,state,digest in states:
        must(hashfile(base.ROOT/mid/"state.json")==digest,
             "ORIGINAL_MIGRATION_STATE_CHANGED_DURING_COPY")
    print("INSTALLED_SITE_ASSETS=30",flush=True)
    print("CRON_STILL_PRIVATE_NOT_ACTIVATED=5",flush=True)
    print("ORIGINAL_PRIVATE_EVIDENCE_RETAINED=YES",flush=True)
    print("OLD_SERVER_CONTACTED=NO",flush=True)
    print("SOURCE_DATABASE_WRITES=NONE",flush=True)
    print("CP2_DATABASE_SQL_WRITES=NONE",flush=True)
    print("SITE_SOURCE_TARGET_PARITY=NOT_VERIFIED",flush=True)
    print("DNS_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0

if __name__=="__main__":
    try:raise SystemExit(do_install())
    except Stop as e:
        print("BLOCKED="+str(e),flush=True)
        print("AUTOMATIC_RETRY=NO",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=SITE_ASSET_INSTALL_UNVERIFIED",flush=True)
        print("AUTOMATIC_RETRY=NO",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
