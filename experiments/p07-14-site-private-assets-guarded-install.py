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
BASE_BLOB="01b02934109458942e575d4e5a45d2d7f7ea37cf"
PRIVATE=Path("/var/lib/vf-server-ops/operator-recovery/p07-missing-assets-cb93c6b490a04068a5533f9cde0fcec7")
PRIVATE_ROOT=Path("/var/lib/vf-server-ops/operator-recovery")
PRIVATE_DIR_RE=re.compile(r"p07-missing-assets-[a-f0-9]{32}\Z")

def validated_private_directory(path_value):
    """Bind the operator to the *actual* newly staged 35-item package.

    The private stage generator uses a fresh UUID; the historical hardcoded
    receipt name must never silently substitute for an owner-selected one.
    """
    must(type(path_value) is str and len(path_value)<256,
         "PRIVATE_EVIDENCE_DIRECTORY_INVALID")
    path=Path(path_value)
    must(path.is_absolute() and path.parent==PRIVATE_ROOT
         and PRIVATE_DIR_RE.fullmatch(path.name) is not None
         and not path.is_symlink() and not PRIVATE_ROOT.is_symlink(),
         "PRIVATE_EVIDENCE_DIRECTORY_UNSAFE")
    return path
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
         and states[2][2].get("partial_parent_migration_id")==base.JOBS[0][1],
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
def expected_manifest_records(states, manifest_keys):
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
                # Immutable private manifest is the stage-time absence ledger.
                # Do not re-evaluate absence during a partial-install resume.
                if (label,category,str(source)) in manifest_keys:
                    rows.append((label,category,str(source),user,row))
        runtime=state.get("runtime_assets") or {}
        must(type(runtime) is dict and type(runtime.get("system_cron",[])) is list,
             "CRON_INVENTORY_CHANGED")
        for row in runtime.get("system_cron",[]):
            must(type(row) is dict and type(row.get("path")) is str and
                 re.fullmatch(r"/etc/cron\.d/[A-Za-z0-9_.-]+",row["path"]),
                 "CRON_INVENTORY_SCOPE_CHANGED")
            if (label,"cron",row["path"]) in manifest_keys:
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
    manifest_keys=set()
    for rec in manifest["records"]:
        must(type(rec) is dict,"PRIVATE_RECORD_INVALID")
        manifest_keys.add((rec.get("job"),rec.get("category"),rec.get("source_path")))
    must(len(manifest_keys)==MAX_ITEMS,"PRIVATE_MANIFEST_DUPLICATE_KEYS")
    inventory=expected_manifest_records(states,manifest_keys)
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
            approved.append((rec,path,target,site_user))
    must(seen==set(expected),"PRIVATE_RECORDS_NOT_COMPLETE")
    must(len(approved)==30,"SITE_INSTALL_COUNT_CHANGED")
    targets=[str(t) for _,_,t,_ in approved]
    must(len(set(targets))==len(targets),"MULTIPLE_RECORDS_SHARE_TARGET")
    roots,overlays=plan_nested_assets(approved)
    # A child SQLite asset may be inside a missing external directory.
    # It is composed in a private temporary tree before any atomic target write.
    # Other nesting remains a hard safety failure.
    return states,approved,total_size

def plan_nested_assets(approved):
    """Return non-overlapping atomic roots + SQLite children to overlay.

    A nested child is legal ONLY when a missing external DIRECTORY contains
    the separately snapshotted SQLite file. All site targets are initially
    absent, original private sources remain unchanged, and other overlaps
    still fail closed. No I/O or target writes here.
    """
    must(len(approved)==30,"EXPECTED_30_ASSET_RECORDS_CHANGED")
    targets=[row[2] for row in approved]
    must(len(set(targets))==len(targets),"DUPLICATE_ASSET_TARGET")
    roots=[]
    overlays={}
    for record in approved:
        rec,private,target,user=record
        parents=[x for x in approved if x[2]!=target and x[2] in target.parents]
        if not parents:
            roots.append(record)
            continue
        # Flatten nested external directories and SQLite files to the outermost
        # atomic root. Multiple ancestors are legal only under that root.
        p=min(parents,key=lambda x:len(x[2].parts))
        parent_rec,parent_private,parent_target,parent_user=p
        must(parent_rec.get("category")=="external" and parent_private.is_dir()
             and rec.get("category") in ("sqlite","external")
             and (private.is_file() or private.is_dir())
             and (rec.get("category")!="sqlite" or private.is_file())
             and user==parent_user,"TARGET_NESTED_PATH_CONFLICT")
        # Scope remains limited to a file inside an absent external directory.
        rel=target.relative_to(parent_target)
        must(rel.parts and all(part not in ("..","") for part in rel.parts),
             "NESTED_SQLITE_PATH_UNSAFE")
        overlays.setdefault(parent_target,[]).append(record)
    root_targets={row[2] for row in roots}
    must(len(roots)+sum(len(v) for v in overlays.values())==30
         and all(k in root_targets for k in overlays),
         "NESTED_ASSET_GRAPH_UNVERIFIED")
    for i,first in enumerate(roots):
        must(not any(first[2] in x[2].parents or x[2] in first[2].parents
                     for x in roots[i+1:]),"ATOMIC_ROOTS_OVERLAP")
    return roots,overlays

def nested_sqlite_count(overlays):
    return sum(sum(rec["category"]=="sqlite" for rec,private,target,user in children)
               for children in overlays.values())

def safe_tree_entries(path):
    """Exact file/directory hash view, including empty directories, no links."""
    must(path.is_dir() and not path.is_symlink(),"EXPECTED_TREE_ROOT_INVALID")
    items={"":"D"}
    for parent,dirs,files in os.walk(path,topdown=True,followlinks=False):
        for name in sorted(dirs+files):
            p=Path(parent)/name
            st=p.lstat()
            must(not stat.S_ISLNK(st.st_mode) and not st.st_mode&(stat.S_ISUID|stat.S_ISGID)
                 and (stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)),
                 "ASSET_TREE_SPECIAL_FILE")
            key=p.relative_to(path).as_posix()
            items[key]="D" if stat.S_ISDIR(st.st_mode) else "F"+hashfile(p)
            must(len(items)<=MAX_FILES,"TREE_FILE_LIMIT")
    return items

def expected_root_entries(root,children):
    rec,private,target,user=root
    must(private.is_dir(),"EXPECTED_ROOT_NOT_DIRECTORY")
    wanted=safe_tree_entries(private)
    for child_rec,child_private,child_target,child_user in sorted(
            children,key=lambda x:len(x[2].parts)):
        rel=child_target.relative_to(target).as_posix()
        parts=Path(rel).parts
        for i in range(1,len(parts)):
            ancestor="/".join(parts[:i])
            must(wanted.get(ancestor,"D")=="D","NESTED_PARENT_FILE_CONFLICT")
            wanted[ancestor]="D"
        if child_rec["category"]=="external":
            child_items=(safe_tree_entries(child_private) if child_private.is_dir()
                         else {"":"F"+hashfile(child_private)})
            for sub,kind in child_items.items():
                key=rel+("/"+sub if sub else "")
                must(key not in wanted or wanted[key]==kind,
                     "NESTED_EXTERNAL_BYTES_CONFLICT")
                wanted[key]=kind
        elif child_rec["category"]=="sqlite":
            for suffix in ("-wal","-shm","-journal"):
                wanted.pop(rel+suffix,None)
            must(wanted.get(rel,"F").startswith("F"),"NESTED_SQLITE_KIND_CONFLICT")
            wanted[rel]="F"+child_rec["sha256"]
        else:raise Stop("NESTED_ASSET_CATEGORY_UNEXPECTED")
    return wanted

def verify_atomic_root(root,children,states):
    rec,private,target,user=root
    account=pwd.getpwnam(user)
    if private.is_dir():
        must(target.is_dir() and not target.is_symlink()
             and safe_tree_entries(target)==expected_root_entries(root,children),
             "INSTALLED_DIRECTORY_BYTES_OR_LAYOUT_CHANGED")
    else:
        must(target.is_file() and not target.is_symlink()
             and hashfile(target)==rec["sha256"],"INSTALLED_FILE_BYTES_CHANGED")
    for child_rec,child_private,child_target,child_user in children:
        if child_rec["category"]=="sqlite":
            must(child_target.is_file() and not child_target.is_symlink()
                 and hashfile(child_target)==child_rec["sha256"]
                 and snapshot_ok(child_target),"INSTALLED_SQLITE_BYTES_CHANGED")
    for each in [root]+children:
        r,source,actual,owner=each
        if r["category"]=="sqlite":
            st=actual.lstat()
            mode=snapshot_mode(states,r["source_path"],r["job"],owner)
            must(st.st_uid==account.pw_uid and st.st_gid==account.pw_gid
                 and stat.S_IMODE(st.st_mode)==mode,"INSTALLED_SQLITE_MODE_OR_OWNER_CHANGED")
    return True

def compose_nested_externals(temp,parent_target,children,uid,gid):
    """Only copy an absent child or accept byte-identical already staged bytes."""
    for rec,private,target,user in sorted(children,key=lambda x:len(x[2].parts)):
        if rec["category"]!="external":continue
        rel=target.relative_to(parent_target)
        dest=temp/rel
        cur=temp
        for name in rel.parts[:-1]:
            cur=cur/name
            if os.path.lexists(cur):
                must(cur.is_dir() and not cur.is_symlink(),
                     "NESTED_EXTERNAL_PARENT_UNSAFE")
            else:cur.mkdir(mode=0o750)
        if os.path.lexists(dest):
            must((dest.is_dir() and not dest.is_symlink()
                  and safe_tree_entries(dest)==safe_tree_entries(private))
                 if private.is_dir() else
                 (dest.is_file() and not dest.is_symlink()
                  and hashfile(dest)==hashfile(private)),
                 "NESTED_EXTERNAL_BYTES_CONFLICT")
        elif private.is_dir():
            shutil.copytree(private,dest,symlinks=False)
        else:shutil.copy2(private,dest,follow_symlinks=False)
    ownership(temp,uid,gid)

def snapshot_mode(states,source,job,user):
    # Parent and child migration jobs can inventory one absolute path.
    # Bind permission metadata to the manifest's exact job and site user.
    matches=[row for label,mid,state,h in states if label==job
             for row in state.get("sqlite_assets",[])
             if row.get("path")==source and row.get("user")==user]
    must(len(matches)==1,"SQLITE_SOURCE_IDENTITY_AMBIGUOUS")
    raw=matches[0].get("mode",0o600)
    must(type(raw) is int,"SQLITE_MODE_UNSAFE")
    mode=raw
    must(0<=mode<=0o777 and not mode&0o111,"SQLITE_MODE_UNSAFE")
    return mode

def overlay_sqlite_snapshots(temp,parent_target,children,states,uid,gid):
    """Compose independently verified SQLite snapshots in a non-site temp tree.

    Old content in the external tree is never modified in private evidence.
    Any apparent replacement occurs only inside the new unpublished
    temporary tree. Existing CP2 site paths are never overwritten.
    """
    must(temp.is_dir() and not temp.is_symlink(),"OVERLAY_TEMP_DIR_UNSAFE")
    for rec,private,target,user in children:
        if rec.get("category")!="sqlite":continue
        must(target!=parent_target
             and parent_target in target.parents,"OVERLAY_SCOPE_UNVERIFIED")
        rel=target.relative_to(parent_target)
        dest=temp/rel
        must(temp in dest.parents,"OVERLAY_PATH_ESCAPED_TEMP")
        current=temp
        for name in rel.parts[:-1]:
            current=current/name
            if os.path.lexists(current):
                st=current.lstat()
                must(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode),
                     "OVERLAY_PARENT_SYMLINK_OR_FILE")
            else:
                current.mkdir(mode=0o750)
                os.chown(current,uid,gid)
        if os.path.lexists(dest):
            st=dest.lstat()
            must(stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode),
                 "OVERLAY_EXISTING_CHILD_NOT_REGULAR")
        # Snapshot excludes the source live WAL and contains a consistent image.
        # Sidecars from the external dir's unsynchronized copy must not be
        # reused against that snapshot. They remain in original private staging.
        for suffix in ("-wal","-shm","-journal"):
            side=Path(str(dest)+suffix)
            if os.path.lexists(side):
                st=side.lstat()
                must(stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode),
                     "OVERLAY_SQLITE_SIDECAR_UNSAFE")
                side.unlink()
        pending=dest.parent/(".p07-snapshot-"+uuid.uuid4().hex)
        must(not os.path.lexists(pending),"OVERLAY_TEMP_COLLISION")
        shutil.copy2(private,pending,follow_symlinks=False)
        mode=snapshot_mode(states,rec["source_path"],rec["job"],user)
        os.chown(pending,uid,gid,follow_symlinks=False)
        os.chmod(pending,mode)
        must(hashfile(pending)==rec["sha256"]
             and snapshot_ok(pending),"OVERLAY_SNAPSHOT_VERIFICATION_FAILED")
        # Overwrite only the non-live, uninstalled temp copy. Original private
        # external directory and any CP2 existing site file are untouched.
        os.replace(pending,dest)
        must(hashfile(dest)==rec["sha256"]
             and snapshot_ok(dest),"OVERLAY_SQLITE_READBACK_FAILED")
    # All nested snapshots are present before the parent directory is
    # atomically installed at its absent CP2 site path.

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
def write_progress(payload):
    """Write only private staging progress, never touch original manifest/state."""
    path=PRIVATE/"cp2-install-progress.json"
    tmp=PRIVATE/(".cp2-progress-"+uuid.uuid4().hex)
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf8") as writer:
            json.dump(payload,writer,sort_keys=True,separators=(",",":"))
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):
            tmp.unlink()
    return path

def load_verified_progress(path,roots,overlays,states):
    security(path,"file")
    st=path.lstat()
    must(st.st_mode&0o077==0 and st.st_size<1024*1024,
         "PROGRESS_PERMISSIONS_OR_SIZE_CHANGED")
    try:progress=json.loads(path.read_text(encoding="utf8"))
    except (ValueError,OSError,UnicodeError):raise Stop("PROGRESS_INVALID") from None
    must(type(progress) is dict and progress.get("status") in (
         "STARTED","COPIED_TO_MISSING_PATHS_NOT_CUTOVER_VERIFIED")
         and progress.get("cron_activated") is False
         and progress.get("cutover_allowed") is False
         and type(progress.get("installed")) is list,"PROGRESS_SCOPE_CHANGED")
    records=progress["installed"]
    must(len(records)<=len(roots),"PROGRESS_INSTALL_COUNT_UNSAFE")
    # The original installer records each atomic root immediately after
    # no-replace rename. Only an exact ordered prefix may be adopted.
    for idx,old in enumerate(records):
        rec,private,target,user=roots[idx]
        must(type(old) is dict and old=={
            "category":rec["category"],"target":str(target),
            "nested_sqlite":sum(c[0]["category"]=="sqlite"
                                for c in overlays.get(target,[]))},
            "PROGRESS_INSTALLED_PREFIX_CHANGED")
        verify_atomic_root(roots[idx],overlays.get(target,[]),states)
    pending=progress.get("pending_temp")
    if pending is not None:
        must(type(pending) is str and len(records)<len(roots),
             "PROGRESS_PENDING_TEMP_INVALID")
        candidate=Path(pending)
        next_target=roots[len(records)][2]
        must(candidate.parent==next_target.parent and
             re.fullmatch(r"\.p07-uninstalled-[0-9a-f]{32}",candidate.name),
             "PROGRESS_PENDING_TEMP_OUTSIDE_NEXT_ROOT")
        must(not candidate.is_symlink(),"PROGRESS_PENDING_TEMP_SYMLINK")
    for rec,private,target,user in roots[len(records):]:
        must(not os.path.lexists(target),"UNRECORDED_EXISTING_TARGET_REVIEW_REQUIRED")
    return progress,len(records)

def snapshot_progress_before_resuming(path):
    """Keep immutable private before-image before any legitimate progress update."""
    security(path,"file")
    data=path.read_bytes()
    must(len(data)<1024*1024,"ORIGINAL_PROGRESS_TOO_LARGE")
    dest=PRIVATE/("cp2-progress-before-resume-"+uuid.uuid4().hex+".json")
    fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as fp:
        fp.write(data)
        fp.flush()
        os.fsync(fp.fileno())
    must(hashfile(dest)==hashlib.sha256(data).hexdigest(),
         "PROGRESS_RECOVERY_COPY_HASH_FAILED")
    return str(dest)

def pending_temp_matches(root,children,pending):
    """Read-only complete proof; incomplete directory is preserved, never edited."""
    rec,private,target,user=root
    if private.is_dir():
        must(pending.is_dir() and not pending.is_symlink(),
             "PENDING_TEMP_TYPE_CHANGED")
        # Read all existing bytes first; unsafe symlinks/special files fail closed.
        actual=safe_tree_entries(pending)
        return actual==expected_root_entries(root,children)
    must(pending.is_file() and not pending.is_symlink(),
         "PENDING_TEMP_TYPE_CHANGED")
    actual=hashfile(pending)
    return (actual==rec["sha256"] and
            (rec["category"]!="sqlite" or snapshot_ok(pending)))

def preserve_incomplete_temp(progress,pending,root):
    """Retain original partial temp byte-for-byte as local recovery evidence."""
    rec,private,target,user=root
    must(pending.exists() and not pending.is_symlink(),
         "PENDING_TEMP_MISSING_OR_UNSAFE_REVIEW_REQUIRED")
    if pending.is_dir():
        count,size,digest=file_tree_integrity(pending)
    else:
        must(pending.is_file(),"PENDING_TEMP_UNSAFE_KIND")
        count,size,digest=1,pending.stat().st_size,hashfile(pending)
    evidence=progress.get("preserved_partial_temps",[])
    must(type(evidence) is list and len(evidence)<len(root[2].parts)+32,
         "PRESERVED_TEMP_LEDGER_INVALID")
    must(all(type(row) is dict and row.get("path")!=str(pending)
             for row in evidence),"PRESERVED_TEMP_ALREADY_REGISTERED")
    evidence.append({"path":str(pending),"for_target":str(target),
                     "content_sha256":digest,"size_bytes":size,
                     "entry_count":count,"status":"PRESERVED_UNMODIFIED"})
    progress["preserved_partial_temps"]=evidence
    progress["pending_temp"]=None
    write_progress(progress)
    print("INCOMPLETE_PENDING_TEMP=RETAINED_UNMODIFIED",flush=True)
    print("PRESERVED_TEMP_EVIDENCE=RECORDED_PRIVATELY",flush=True)
    return False

def finish_verified_pending(progress,roots,overlays,states,index):
    """Explicit resume: adopt complete temp; otherwise preserve and rebuild."""
    raw=progress.get("pending_temp")
    if raw is None:return index
    root=roots[index]
    rec,private,target,user=root
    pending=Path(raw)
    must(pending.exists() and not pending.is_symlink(),
         "PENDING_TEMP_MISSING_OR_UNSAFE_REVIEW_REQUIRED")
    account=pwd.getpwnam(user)
    uid,gid=account.pw_uid,account.pw_gid
    check_parents(target,user)
    must(not os.path.lexists(target),"PENDING_TARGET_ALREADY_EXISTS")
    children=overlays.get(target,[])
    if not pending_temp_matches(root,children,pending):
        preserve_incomplete_temp(progress,pending,root)
        return index
    # Exact complete image: verify before atomically publishing anything.
    mode=(snapshot_mode(states,rec["source_path"],rec["job"],user)
          if rec["category"]=="sqlite" else None)
    ownership(pending,uid,gid,mode)
    for child_rec,child_private,child_target,child_user in children:
        if child_rec["category"]=="sqlite":
            dest=pending/child_target.relative_to(target)
            child_mode=snapshot_mode(states,child_rec["source_path"],
                                     child_rec["job"],child_user)
            must(dest.is_file() and not dest.is_symlink(),
                 "PENDING_NESTED_SQLITE_CHANGED")
            os.chown(dest,uid,gid,follow_symlinks=False)
            os.chmod(dest,child_mode)
            must(hashfile(dest)==child_rec["sha256"] and snapshot_ok(dest),
                 "PENDING_NESTED_SQLITE_CHANGED")
    rename_noreplace(pending,target)
    progress["installed"].append({
        "category":rec["category"],"target":str(target),
        "nested_sqlite":sum(c[0]["category"]=="sqlite" for c in children)})
    progress["pending_temp"]=None
    write_progress(progress)
    verify_atomic_root(root,children,states)
    print("RECORDED_PENDING_TEMP_RECOVERED=EXACT_BYTES_ONLY",flush=True)
    return index+1

def do_audit_partial(states,approved,roots,overlays):
    """CP2 read-only audit; no file copy, permissions change or state writes."""
    path=PRIVATE/"cp2-install-progress.json"
    must(path.is_file() and not path.is_symlink(),"PROGRESS_NOT_FOUND")
    progress,index=load_verified_progress(path,roots,overlays,states)
    pending=progress.get("pending_temp")
    print("AUDIT=READ_ONLY_CP2_PARTIAL_ASSETS",flush=True)
    print("MANIFEST_SCOPE=35",flush=True)
    print("EXPECTED_LOGICAL_ASSETS=30",flush=True)
    print("EXPECTED_ATOMIC_ROOTS="+str(len(roots)),flush=True)
    print("VERIFIED_ALREADY_INSTALLED_ROOTS="+str(index),flush=True)
    print("PENDING_TEMP_RECORDED="+("YES" if pending else "NO"),flush=True)
    if pending:
        candidate=Path(pending)
        print("PENDING_TEMP_EXISTS="+("YES" if os.path.lexists(candidate) else "NO"),flush=True)
        print("PENDING_TEMP_KIND="+("DIRECTORY" if candidate.is_dir() else
              "FILE" if candidate.is_file() else "OTHER_OR_MISSING"),flush=True)
    # Count duplicate SQLite path across jobs without disclosing private paths.
    by_path={}
    for label,mid,state,digest in states:
        for row in state.get("sqlite_assets",[]):
            if type(row) is dict and type(row.get("path")) is str:
                by_path.setdefault(row["path"],set()).add(label)
    print("SQLITE_PATHS_RECORDED_IN_MULTIPLE_JOBS="+str(
        sum(len(labels)>1 for labels in by_path.values())),flush=True)
    print("CRON_ACTIVATED=NO",flush=True)
    print("RESUME_READY="+("REQUIRES_EXPLICIT_VERIFIED_PENDING_RECOVERY"
                           if pending else "ELIGIBLE_FOR_OWNER_CONTROLLED_RESUME"),flush=True)
    print("SITE_RUNTIME_HTTP_PHP_PARITY=NOT_VERIFIED",flush=True)
    print("DNS_WRITE=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0

def do_install():
    must(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    global PRIVATE
    requested=sys.argv[1:]
    if len(requested)==3 and requested[1]=="--private-evidence-dir":
        PRIVATE=validated_private_directory(requested[2])
        requested=requested[:1]
    must(requested in (["--install-only-30-absent-site-assets"],
                       ["--resume-verified-partial-asset-install"],
                       ["--audit-existing-partial-assets-readonly"]),
         "EXPLICIT_SITE_ASSET_INSTALL_OR_RESUME_ARGUMENT_REQUIRED")
    states,approved,total_size=check_manifest()
    roots,overlays=plan_nested_assets(approved)
    if requested==["--audit-existing-partial-assets-readonly"]:
        return do_audit_partial(states,approved,roots,overlays)
    progress_path=PRIVATE/"cp2-install-progress.json"
    if requested==["--resume-verified-partial-asset-install"]:
        must(os.path.lexists(progress_path),"NO_PARTIAL_PROGRESS_TO_RESUME")
        progress,resume_index=load_verified_progress(progress_path,roots,overlays,states)
        must(resume_index>0,"NO_VERIFIED_INSTALLED_PREFIX_TO_RESUME")
    else:
        must(not os.path.lexists(progress_path),"PREVIOUS_INSTALL_PROGRESS_EXISTS_REVIEW_REQUIRED")
        must(all(not os.path.lexists(r[2]) for r in roots),
             "TARGET_ALREADY_EXISTS_NO_OVERWRITE")
        progress={"status":"STARTED","installed":[],"pending_temp":None,
                  "cron_activated":False,"cutover_allowed":False}
        resume_index=0
    # Verify complete staged scope and SQLite modes before first site write.
    for rec,private,target,user in approved:
        if rec["category"]=="sqlite":
            snapshot_mode(states,rec["source_path"],rec["job"],user)
    for root in roots:
        if root[1].is_dir():
            expected_root_entries(root,overlays.get(root[2],[]))
    # Count the staged roots plus separate nested snapshots (conservative).
    remaining=sum((p.stat().st_size if p.is_file() else file_tree_integrity(p)[1])
                  for rec,p,target,user in roots[resume_index:])
    remaining+=sum((p.stat().st_size if p.is_file() else file_tree_integrity(p)[1])
                  for root in roots[resume_index:]
                  for rec,p,target,user in overlays.get(root[2],[]))
    must(shutil.disk_usage("/home").free>remaining+1024**3,
         "INSUFFICIENT_CP2_INSTALL_SPACE")
    print("PRIVATE_MANIFEST_35_35=PASS",flush=True)
    print("SITE_INSTALL_LOGICAL_TARGETS=30",flush=True)
    print("ATOMIC_INSTALL_ROOTS="+str(len(roots)),flush=True)
    print("NESTED_SQLITE_SNAPSHOTS="+str(nested_sqlite_count(overlays)),flush=True)
    print("VERIFIED_ALREADY_INSTALLED_ROOTS="+str(resume_index),flush=True)
    print("CRON_KEPT_PRIVATE=5",flush=True)
    print("REMAINING_ROOT_COPY_MIB="+str((remaining+1024**2-1)//1024**2),flush=True)
    print("INSTALL_BOUNDARY=CP2_NEW_EMPTY_SITE_PATHS_ONLY",flush=True)
    if resume_index==0:write_progress(progress)
    print("INSTALL_PROGRESS_PATH="+str(progress_path),flush=True)
    if requested==["--resume-verified-partial-asset-install"]:
        saved=snapshot_progress_before_resuming(progress_path)
        print("ORIGINAL_PROGRESS_RECOVERY_COPY="+saved,flush=True)
        resume_index=finish_verified_pending(progress,roots,overlays,states,resume_index)
    for idx,(rec,private,target,user) in enumerate(roots[resume_index:],resume_index+1):
        account=pwd.getpwnam(user)
        uid,gid=account.pw_uid,account.pw_gid
        ensure_parents(target,user,uid,gid)
        check_parents(target,user)
        must(not os.path.lexists(target),"TARGET_CHANGED_DURING_INSTALL")
        temp=target.parent/(".p07-uninstalled-"+uuid.uuid4().hex)
        must(not os.path.lexists(temp),"TEMP_INSTALL_COLLISION")
        progress["pending_temp"]=str(temp)
        write_progress(progress)
        # Do not remove this temp on failure. The operator must inspect it.
        if private.is_dir():
            shutil.copytree(private,temp,symlinks=False)
            ownership(temp,uid,gid)
            must(file_tree_integrity(temp)[2]==file_tree_integrity(private)[2],
                 "DIRECTORY_STAGED_COPY_CHANGED")
            if target in overlays:
                compose_nested_externals(temp,target,overlays[target],uid,gid)
                overlay_sqlite_snapshots(temp,target,overlays[target],
                                         states,uid,gid)
        else:
            shutil.copy2(private,temp,follow_symlinks=False)
            mode=(snapshot_mode(states,rec["source_path"],rec["job"],user)
                  if rec["category"]=="sqlite" else None)
            ownership(temp,uid,gid,mode)
            must(hashfile(temp)==rec["sha256"],"FILE_COPY_SHA256_MISMATCH")
        # Linux no-replace rename, so concurrent creation cannot be overwritten.
        # Pre-publication full logical view check, then final atomic install.
        if private.is_dir():
            must(safe_tree_entries(temp)==expected_root_entries(
                (rec,private,target,user),overlays.get(target,[])),
                "UNPUBLISHED_ROOT_BYTES_MISMATCH")
        rename_noreplace(temp,target)
        progress["installed"].append({"category":rec["category"],"target":str(target),
                                      "nested_sqlite":sum(x[0]["category"]=="sqlite"
                                          for x in overlays.get(target,[]))})
        progress["pending_temp"]=None
        write_progress(progress)
        print("INSTALLED_ASSET="+str(idx)+" CATEGORY="+rec["category"].upper()+
              " STATUS=NEW_ONLY_SHA_VERIFIED",flush=True)
    # Verify complete logical content of every root including nested records.
    for root in roots:
        verify_atomic_root(root,overlays.get(root[2],[]),states)
    print("ALL_30_LOGICAL_SITE_ASSETS_READBACK=PASS",flush=True)
    for label,mid,state,digest in states:
        must(hashfile(base.ROOT/mid/"state.json")==digest,
             "ORIGINAL_MIGRATION_STATE_CHANGED_DURING_COPY")
    progress["status"]="COPIED_TO_MISSING_PATHS_NOT_CUTOVER_VERIFIED"
    write_progress(progress)
    print("INSTALLED_SITE_ASSETS=30",flush=True)
    print("ATOMIC_SITE_ROOTS_INSTALLED="+str(len(roots)),flush=True)
    print("NESTED_SQLITE_COMPOSED="+str(nested_sqlite_count(overlays)),flush=True)
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
