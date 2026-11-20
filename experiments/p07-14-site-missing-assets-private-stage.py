#!/usr/bin/env python3
"""P07 CP2: one-shot private-only asset recovery for the 14 already staged sites.

- Reads the three protected PREPARE_FAILED states, never alters them.
- Pulls missing external files/dirs to a new root-only evidence directory;
  collects consistent SQLite snapshots via the existing source helper;
  stages only system Cron text, never activates any service.
- No target site path is written. No old-server business data is changed.
- Existing destination files, databases and protected 3 pending sites untouched.
- No automatic retry, no cutover. Resume requires separate source/target proof.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import uuid

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
BASE=HERE/"p07-17-site-staged-local-evidence.py"
BASE_SHA="01b02934109458942e575d4e5a45d2d7f7ea37cf"

class Block(Exception):pass
def need(ok,why):
    if not ok:raise Block(why)
def gitblob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def verify_base():
    need(BASE.is_file() and not BASE.is_symlink(),"STAGED_BASELINE_MISSING")
    need(gitblob(BASE.read_bytes())==BASE_SHA,"STAGED_BASELINE_DRIFT")
    spec=importlib.util.spec_from_file_location("p07_batch_baseline",BASE)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

base=verify_base()
SAFE_USER=re.compile(r"[a-z_][a-z0-9_-]{0,64}")
SAFE_JOB=re.compile(r"pull-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}")
SAFE_BLOB=re.compile(r"[a-f0-9]{64}")
SCOPE=Path("/var/lib/vf-server-ops/operator-recovery")
MODES={"FILE","DIRECTORY"}
EXPECTED={"external":17,"sqlite":13,"cron":5}
RUNTIME_SHA="71fb59ad7d005b88e39cbeed4b3302c7f313bd06"

def stage_rows():
    states=[]
    by_domain={}
    for label,mid,count in base.JOBS:
        state=base.secure_state(base.ROOT/mid/"state.json")
        need(state.get("schema")==base.SCHEMA and state.get("migration_id")==mid
             and len(state.get("sites",[]))==count and
             state.get("status")=="PREPARE_FAILED","MIGRATION_STATE_CHANGED")
        for key in ("source_runtime_frozen","target_runtime_activated",
                    "dns_changed_by_p07","source_delete_allowed",
                    "existing_target_overwrite_allowed"):
            need(state.get(key) is False,"MIGRATION_PROTECTION_CHANGED")
        need(type(state.get("source")) is dict and
             type(state.get("source_runtime_path")) is str and
             SAFE_JOB.fullmatch(mid),"SOURCE_MIGRATION_BINDING_UNVERIFIED")
        states.append((label,state))
        for site in state["sites"]:
            need(type(site) is dict and type(site.get("domain")) is str,"SITE_INVALID")
            by_domain[site["domain"]]=(label,site)
    need(states[1][1].get("partial_parent_migration_id")==base.JOBS[0][1]
         and states[2][1].get("partial_parent_migration_id")==base.JOBS[0][1],
         "MIGRATION_PARENT_CHAIN_CHANGED")
    need({d for d,(_,s) in by_domain.items() if s.get("stage_status")=="PULLED_STAGED"}
          ==base.EXPECTED_STAGED and
         {d for d,(_,s) in by_domain.items() if s.get("stage_status")=="PENDING"}
          ==base.EXPECTED_PENDING,"STAGED_SCOPE_DRIFT")
    need(len({s.get("target_server_identity") for _,s in states})==1,
         "TARGET_IDENTITY_CHANGED")
    need(len({s.get("source_server_identity") for _,s in states})==1,
         "SOURCE_IDENTITY_CHANGED")
    rows=[]
    for label,state in states:
        user_to_domain={s["site_user"]:s["domain"] for s in state["sites"]
                        if s["stage_status"]=="PULLED_STAGED"}
        need(all(SAFE_USER.fullmatch(u) for u in user_to_domain),"STAGED_USER_UNSAFE")
        for entry in state.get("external_assets",[]):
            need(type(entry) is dict,"EXTERNAL_RECORD_INVALID")
            user=entry.get("user")
            if user not in user_to_domain:continue
            path=validate_asset_path(entry,user)
            if os.path.lexists(path):
                continue
            rows.append(("external",label,state,path,user,entry))
        for entry in state.get("sqlite_assets",[]):
            need(type(entry) is dict,"SQLITE_RECORD_INVALID")
            user=entry.get("user")
            if user not in user_to_domain:continue
            path=validate_asset_path(entry,user)
            if os.path.lexists(path):continue
            rows.append(("sqlite",label,state,path,user,entry))
        runtime=state.get("runtime_assets") or {}
        need(type(runtime) is dict,"RUNTIME_ASSETS_INVALID")
        for entry in runtime.get("system_cron",[]):
            need(type(entry) is dict,"CRON_RECORD_INVALID")
            path=entry.get("path")
            need(type(path) is str and path.startswith("/etc/cron.d/")
                 and len(path)<256 and re.fullmatch(r"/etc/cron\.d/[A-Za-z0-9_.-]+",path),
                 "CRON_SOURCE_OUT_OF_BOUNDARY")
            rows.append(("cron",label,state,Path(path),"root",entry))
    counts={k:sum(row[0]==k for row in rows) for k in EXPECTED}
    need(counts==EXPECTED,"ACTUAL_MISSING_ASSET_SCOPE_CHANGED")
    # Never use automatic or incremental resume to reinterpret a failed state.
    # Cron paths can legitimately recur in several migration child snapshots.
    # Each reference is staged privately per job; only site-file collisions block.
    keys=[(typ,str(path)) for typ,_,_,path,_,_ in rows if typ!="cron"]
    need(len(keys)==len(set(keys)),"DUPLICATE_ASSET_DESTINATION")
    exts=[path for typ,_,_,path,_,_ in rows if typ=="external"]
    for i,path in enumerate(exts):
        need(not any(path in x.parents or x in path.parents for x in exts[i+1:]),
             "NESTED_EXTERNAL_ASSET_ROOTS")
    return states,rows

def validate_asset_path(entry,user):
    raw=entry.get("path")
    need(type(raw) is str and type(user) is str and SAFE_USER.fullmatch(user),
         "ASSET_PATH_OR_USER_INVALID")
    root=Path("/home")/user
    path=Path(raw)
    need(path.is_absolute() and len(raw)<1024
         and root in path.parents and ".." not in path.parts,
         "ASSET_OUTSIDE_SITE_USER_ROOT")
    return path

def safe_read(root, path):
    need(path.exists() and not path.is_symlink(),"STAGED_ASSET_UNREADABLE")
    need(root in path.parents or root==path,"STAGED_ASSET_ESCAPE")
    return path

def hashfile(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        while True:
            chunk=f.read(1024*1024)
            if not chunk:break
            h.update(chunk)
    return h.hexdigest()

def local_sqlite_ok(p):
    # Private snapshots have no live WAL/SHM; read only with immutable URI.
    c=sqlite3.connect(p.as_uri()+"?mode=ro&immutable=1",uri=True,timeout=5)
    try:
        result=c.execute("PRAGMA quick_check").fetchone()
        return result==("ok",)
    finally:c.close()

def prepare_engine():
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import server_migration_pull as migrate
    need(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    need(Path("/opt/vf-server-ops/BUILD_ID").read_text().strip()=="0.1.0-release113",
         "RELEASE113_REQUIRED")
    actual=gitblob(Path("/opt/vf-server-ops/lib/server_migration_pull.py").read_bytes())
    need(actual==RUNTIME_SHA,"RELEASE113_ENGINE_DRIFT")
    return migrate

def validated_remote_kind(migrate,state,src,kind):
    source=state["source"]
    if kind=="cron":
        result=migrate.source_remote(source,
            "test -f "+sh_quote(str(src))+" && test ! -L "+sh_quote(str(src)),
            timeout=40,check=False)
        need(result.returncode==0,"SOURCE_CRON_MISSING_OR_SYMLINK")
        return "FILE"
    observed=migrate.source_path_kind(source,str(src))
    return observed

def sh_quote(value):
    import shlex
    return shlex.quote(value)

def source_space_preflight(migrate,records):
    # Old VPS: read-only du; do not transfer until disk capacity is known.
    total_kib=0
    for category,label,state,src,user,entry in records:
        proc=migrate.source_remote(state["source"],
            "du -sk -- "+sh_quote(str(src)),timeout=120,check=False)
        if proc.returncode!=0:
            raise Block("SOURCE_ASSET_SIZE_UNAVAILABLE")
        match=re.fullmatch(r"([0-9]{1,15})\t.+\n?",proc.stdout)
        if not match:
            raise Block("SOURCE_ASSET_SIZE_FORMAT_UNVERIFIED")
        total_kib+=int(match.group(1))
    free=shutil.disk_usage(SCOPE).free
    # Raw DB/WAL copy plus CP2 backup and site assets: 4x reserve +1GiB.
    need(free>total_kib*4096+1024**3,"INSUFFICIENT_CP2_PRIVATE_STAGE_SPACE")
    print("CP2_PRIVATE_STAGE_CAPACITY=PASS",flush=True)
    print("SOURCE_ASSET_ESTIMATED_MIB="+str((total_kib+1023)//1024),flush=True)


def create_evidence_folder():
    need(SCOPE.is_dir() and not SCOPE.is_symlink(),"RECOVERY_ROOT_MISSING_OR_UNSAFE")
    check=SCOPE.stat()
    need(check.st_uid==0 and not check.st_mode & 0o022,
         "RECOVERY_ROOT_PERMISSIONS_UNSAFE")
    name="p07-missing-assets-"+uuid.uuid4().hex
    dest=SCOPE/name
    dest.mkdir(mode=0o700)
    return dest

def copy_to_private(migrate,category,state,source_path,outpath,kind,user):
    outpath.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    source=state["source"]
    if kind=="DIRECTORY":
        need(not outpath.exists(),"PRIVATE_DESTINATION_EXISTS")
        outpath.mkdir(mode=0o700)
        migrate.pull_path(source,str(source_path).rstrip("/")+"/",outpath,
                          user=None,delete=False)
        # No symlink entries are ever promoted (this pass is strictly
        # private staging, so record their existence as a follow-up risk).
        return "DIRECTORY_TRANSFERRED_NO_BYTE_PARITY"
    need(not outpath.exists(),"PRIVATE_DESTINATION_EXISTS")
    migrate.pull_path(source,str(source_path),outpath,user=None,delete=False)
    need(outpath.is_file() and not outpath.is_symlink(),
         "PRIVATE_FILE_TRANSFER_UNVERIFIED")
    return "FILE_TRANSFERRED_HASHED"


def read_only_source_sqlite_hashes(migrate,state,src):
    """Read authoritative DB and optional WAL fingerprints without source writes."""
    db=sh_quote(str(src))
    wal=sh_quote(str(src)+"-wal")
    journal=sh_quote(str(src)+"-journal")
    command=(
        "set -eu; "
        f"test -f {db} && test ! -L {db}; "
        f"test ! -e {journal} && test ! -L {journal}; "
        f"test ! -L {wal}; "
        f"dbsum=$(sha256sum -- {db} | cut -d ' ' -f 1); "
        "printf 'DB=%s\n' \"$dbsum\"; "
        f"if [ -e {wal} ]; then "
        f"test -f {wal}; "
        f"walsum=$(sha256sum -- {wal} | cut -d ' ' -f 1); "
        "printf 'WAL=%s\n' \"$walsum\"; "
        "else printf 'WAL=ABSENT\n'; fi"
    )
    result=migrate.source_remote(state["source"],command,timeout=600,check=False)
    need(result.returncode==0,"SOURCE_SQLITE_READONLY_HASH_FAILED")
    rows=result.stdout.strip().splitlines()
    need(len(rows)==2 and rows[0].startswith("DB=") and
         rows[1].startswith("WAL="),"SOURCE_SQLITE_FINGERPRINT_FORMAT")
    dbhash=rows[0][3:]
    walhash=rows[1][4:]
    need(SAFE_BLOB.fullmatch(dbhash) and
         (walhash=="ABSENT" or SAFE_BLOB.fullmatch(walhash)),
         "SOURCE_SQLITE_FINGERPRINT_INVALID")
    return dbhash,walhash

def copy_sqlite_source_readonly(migrate,state,src,out):
    """Pull raw DB/WAL read-only; create consistent SQLite backup on CP2 only.

    Source DB/WAL hashes before and after the copy must match the locally
    copied bytes. This is a private staging snapshot, NOT a frozen final source.
    """
    need(not os.path.lexists(out),"PRIVATE_SQLITE_TARGET_EXISTS")
    before=read_only_source_sqlite_hashes(migrate,state,src)
    out.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".p07-sqlite-readonly-",dir=str(SCOPE)) as work:
        remote_copy=Path(work)/"source.sqlite"
        migrate.pull_path(state["source"],str(src),remote_copy,user=None,delete=False)
        need(remote_copy.is_file() and not remote_copy.is_symlink() and
             hashfile(remote_copy)==before[0],"SQLITE_SOURCE_DB_COPY_HASH_MISMATCH")
        if before[1]!="ABSENT":
            local_wal=Path(str(remote_copy)+"-wal")
            migrate.pull_path(state["source"],str(src)+"-wal",
                              local_wal,user=None,delete=False)
            need(local_wal.is_file() and not local_wal.is_symlink() and
                 hashfile(local_wal)==before[1],"SQLITE_SOURCE_WAL_COPY_HASH_MISMATCH")
        after=read_only_source_sqlite_hashes(migrate,state,src)
        need(before==after,"SQLITE_SOURCE_CHANGED_DURING_READONLY_COPY")
        try:
            source=sqlite3.connect(remote_copy.as_uri()+"?mode=ro",uri=True,timeout=10)
            try:
                target=sqlite3.connect(out,timeout=10)
                try:
                    source.backup(target,pages=256,sleep=0.05)
                finally:
                    target.close()
            finally:
                source.close()
        except sqlite3.Error:
            raise Block("CP2_PRIVATE_SQLITE_BACKUP_FAILED") from None
        need(local_sqlite_ok(out),"COPIED_SQLITE_QUICK_CHECK_FAILED")
    return "SQLITE_SNAPSHOT_PRIVATE_VERIFIED"

def stage():
    need(sys.argv[1:]==["--stage-exact-missing-assets-private-only"],
         "EXPLICIT_PRIVATE_STAGE_ARGUMENT_REQUIRED")
    states,records=stage_rows()
    migrate=prepare_engine()
    # Check source existence and path kind BEFORE creating recovery evidence.
    observed=[]
    for category,label,state,src,user,entry in records:
        kind=validated_remote_kind(migrate,state,src,category)
        if category=="sqlite":
            need(kind=="FILE","SQLITE_SOURCE_NOT_FILE")
        if category=="external" and entry.get("kind") in MODES:
            need(kind==entry["kind"],"EXTERNAL_SOURCE_TYPE_CHANGED")
        if category=="cron":need(kind=="FILE","CRON_SOURCE_TYPE_CHANGED")
        observed.append(kind)
    source_space_preflight(migrate,records)
    original_state_hashes={mid:hashfile(base.ROOT/mid/"state.json") for _,mid,_ in base.JOBS}
    evidence=create_evidence_folder()
    entries=[]
    counts={"external":0,"sqlite":0,"cron":0}
    for num,((category,label,state,src,user,entry),kind) in enumerate(zip(records,observed),1):
        out=evidence/category/f"{num:03d}-{hashlib.sha256(str(src).encode()).hexdigest()[:20]}"
        if category=="sqlite":
            result=copy_sqlite_source_readonly(migrate,state,src,out)
        elif category=="cron":
            result=copy_to_private(migrate,category,state,src,out,"FILE",user)
            need(out.stat().st_size<1024*1024,"CRON_STAGING_SIZE_LIMIT")
            result="CRON_PRIVATE_NOT_ACTIVATED"
        else:
            result=copy_to_private(migrate,category,state,src,out,kind,user)
        need(safe_read(evidence,out) is not None,"PRIVATE_ASSET_ESCAPE")
        counts[category]+=1
        item={"category":category,"job":label,"source_path":str(src),
              "private_path":str(out),"scope":"STAGED_SITE_ONLY" if category!="cron" else "SYSTEM_CRON_NOT_ACTIVATED",
              "result":result,"sha256":hashfile(out) if out.is_file() else None}
        entries.append(item)
        print("STAGED_ITEM="+str(num)+" CATEGORY="+category.upper()+
              " RESULT="+result,flush=True)
    need(counts==EXPECTED,"RECOVERY_ASSET_COUNT_INCOMPLETE")
    need(all(hashfile(base.ROOT/mid/"state.json")==original_state_hashes[mid]
             for _,mid,_ in base.JOBS),"ORIGINAL_MIGRATION_STATE_MUTATED_OR_RACED")
    # Before claiming a completed private batch, verify states remain byte-identical
    # to their original snapshots? Source/target cannot have been touched by us.
    manifest=evidence/"private-manifest.json"
    with manifest.open("x",encoding="utf-8") as file:
        json.dump({"status":"PRIVATE_STAGING_ONLY","counts":counts,
                   "cutover_allowed":False,"site_files_materialized":False,
                   "records":entries},file,ensure_ascii=False,sort_keys=True,indent=2)
    os.chmod(manifest,0o600)
    print("STAGED_ASSET_COUNTS="+json.dumps(counts,sort_keys=True))
    print("PRIVATE_EVIDENCE_DIR="+str(evidence))
    print("SITE_PATHS_MODIFIED=NO")
    print("CRON_ACTIVATED=NO")
    print("SOURCE_BUSINESS_DATA_WRITES=NONE")
    print("SOURCE_TEMP_SQLITE_SNAPSHOTS_CREATED=NO")
    print("SOURCE_FILE_WRITES=NONE")
    print("CP2_PRIVATE_SQLITE_SNAPSHOTS=13")
    print("ORIGINAL_MIGRATION_STATES_MODIFIED=NO")
    print("SITE_CONTENT_PARITY=NOT_VERIFIED")
    print("DATABASE_WRITES=NONE")
    print("DNS_WRITES=NONE")
    print("CUTOVER_ALLOWED=NO")
    return 0

if __name__=="__main__":
    try:raise SystemExit(stage())
    except Block as e:
        print("BLOCKED="+str(e),flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=PRIVATE_ASSET_RECOVERY_UNVERIFIED",flush=True)
        raise SystemExit(13) from None
