#!/usr/bin/env python3
"""P07 ilovem3u8: one-attempt, fail-closed SOURCE -> NEW ISOLATED CP2 DB.

Keeps original target site database and its 5-only / 6-changed-PK rows untouched.
Only creates one unique scratch DB for an independently protected fresh source
export. No existing DB import, source business writes, DNS, app config or Cutover.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import sqlite3
import stat
import subprocess
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
PINNED={
 "p07-two-pending-live-db-parity.py":"0b6ee5061909115de6f57b5d933244de3a7a79fa",
 "p07-two-pending-live-db-worker.py":"c63cd3513c773678a6162b50f8a93d35fe9160b6",
 "p07-www3-isolated-restore.py":"1b3b9285853cc99e467f70d92c7d2b0222874018",
}
MID="pull-20261028T103425Z-98050c76"
DOMAIN="ilovem3u8.kewaro.com"
ROOT=Path("/var/lib/vf-server-ops/server-migrations")/MID/"recovery-scratch-ilovem3u8"
class Block(Exception):pass
def need(ok,code):
    if not ok: raise Block(code)
def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def load(name,module):
    path=HERE/name
    try:
        need(path.is_file() and not path.is_symlink() and
             blob(path.read_bytes())==PINNED[name],"PINNED_COMPANION_CHANGED")
    except OSError:raise Block("PINNED_COMPANION_UNAVAILABLE") from None
    spec=importlib.util.spec_from_file_location(module,path)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj
def save(record):
    tmp=ROOT/"status.json.tmp"
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as w:
        json.dump(record,w,sort_keys=True,separators=(",",":"))
        w.flush();os.fsync(w.fileno())
    os.replace(tmp,ROOT/"status.json")
def panel_link_count(db):
    path=Path("/home/clp/htdocs/app/data/db.sq3")
    try:
        con=sqlite3.connect(f"file:{path}?mode=ro",uri=True,timeout=3)
        try:
            value=con.execute(
                'SELECT COUNT(*) FROM "database" d JOIN "site" s '
                'ON d.site_id=s.id WHERE d.name=? AND s.domain_name=?',
                (db,DOMAIN)).fetchone()[0]
        finally:con.close()
    except (OSError,sqlite3.Error):
        raise Block("CLOUDPANEL_SCRATCH_REGISTRATION_UNAVAILABLE") from None
    return value
def preflight(pair,base,engine,inventory):
    need(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    installed=Path("/opt/vf-server-ops/lib/server_migration_pull.py")
    need(installed.is_file() and blob(installed.read_bytes())==pair.ENGINE_BLOB,
         "RELEASE113_ENGINE_CHANGED")
    b=subprocess.run(["vfops","--build-id"],stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,timeout=20,text=True,check=False)
    need(b.returncode==0 and b.stdout.strip()=="0.1.0-release113",
         "RELEASE113_RUNTIME_REQUIRED")
    state,origin,target,_=pair.preflight(engine,inventory,*pair.SITES[1])
    need(type(target) is str and re.fullmatch("[A-Za-z0-9._-]{1,64}",target)
         and type(origin) is str and re.fullmatch("[A-Za-z0-9._-]{1,64}",origin),
         "EXISTING_TARGET_DB_NOT_UNIQUELY_BOUND")
    need(state.get("status")=="PREPARE_FAILED" and
         state.get("source_runtime_frozen") is False and
         state.get("dns_changed_by_p07") is False and
         state.get("source_delete_allowed") is False and
         state.get("existing_target_overwrite_allowed") is False,
         "MIGRATION_PROTECTION_CHANGED")
    need(not ROOT.exists() and not ROOT.is_symlink(),
         "ISOLATED_SOURCE_RESTORE_ALREADY_ATTEMPTED")
    need(engine.cloudpanel_database_server_ready_local(),
         "TARGET_DATABASE_SERVICE_UNAVAILABLE")
    engine.require_mariadb_target()
    need(shutil.disk_usage("/").free>=2*1024*1024*1024,
         "SCRATCH_FREE_DISK_BELOW_2GB")
    need(all(shutil.which(x) for x in ("mariadb","gzip","clpctl")),
         "MIGRATION_CLIENT_UNAVAILABLE")
    need(panel_link_count(target)==1,"EXISTING_TARGET_BINDING_CHANGED")
    return state,origin,target
def readback(db,user,password):
    # Query one newly created scratch DB only, with credentials kept off argv.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix="p07-scratch-count-",dir="/root") as d:
        conf=Path(d)/"client.cnf"
        fd=os.open(conf,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        def escape(t):return t.replace("\\","\\\\").replace('"','\\"')
        with os.fdopen(fd,"w") as f:
            f.write('[client]\nuser="'+escape(user)+'"\npassword="'+escape(password)+'"\n')
        args=["mariadb","--defaults-extra-file="+str(conf),"--protocol=tcp",
              "--host=127.0.0.1","--batch","--skip-column-names"]
        q=("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='"
           +db+"' AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
        p=subprocess.run(args+["--execute",q],stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,timeout=40,check=False,text=True)
        need(p.returncode==0,"SCRATCH_TABLE_METADATA_QUERY_FAILED")
        tables=p.stdout.splitlines()
        need(len(tables)==42 and len(set(tables))==42 and
             all(re.fullmatch("[A-Za-z0-9_]{1,64}",x) for x in tables),
             "SCRATCH_42_TABLES_NOT_VERIFIED")
        count=0
        for t in tables:
            p=subprocess.run(args+["--execute","SELECT COUNT(*) FROM "+chr(96)+db+chr(96)
                                   +"."+chr(96)+t+chr(96)],
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                timeout=60,text=True,check=False)
            need(p.returncode==0 and re.fullmatch("[0-9]{1,10}",p.stdout.strip()),
                 "SCRATCH_ROW_COUNT_READBACK_FAILED")
            count+=int(p.stdout.strip())
    return len(tables),count
def run():
    need(sys.argv[1:]==["--restore-fresh-source-to-new-isolated-ilovem3u8-db"],
         "EXPLICIT_ISOLATED_RESTORE_MODE_REQUIRED")
    pair=load("p07-two-pending-live-db-parity.py","p07_pair_recovery")
    load("p07-two-pending-live-db-worker.py","p07_credential_boundary")
    base=load("p07-www3-isolated-restore.py","p07_safe_restore_primitives")
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import server_migration_pull as engine
    import cloudpanel,inventory
    state,source_db,original_target=preflight(pair,base,engine,inventory)
    token=secrets.token_hex(12)
    scratch_db="p07scratch-"+token[:12]
    scratch_user="p07stage-"+token[:12]
    scratch_password=secrets.token_urlsafe(32)
    # Before any write, prove BOTH new DB and user absent. Unknown => hard stop.
    need(base._master_sql_presence(scratch_db,scratch_user)==("0","0"),
         "SCRATCH_NAMES_EXIST_OR_CANNOT_BE_PROVEN_ABSENT")
    ROOT.mkdir(mode=0o700,parents=False,exist_ok=False)
    record={"original_site":DOMAIN,"migration_id":MID,
            "status":"SOURCE_EXPORT_IN_PROGRESS",
            "scratch_database":scratch_db,"scratch_user":scratch_user,
            "source_frozen":False,"dns_changed":False,
            "site_config_modified":False,
            "existing_target_database_modified":False,
            "cutover_allowed":False,
            "original_target_preserved":True}
    save(record)
    dump=ROOT/"source.sql.gz"
    remote_dir=f"/var/lib/vf-server-ops/pull-source/{MID}/data/scratch-{token}"
    remote_dump=remote_dir+"/source.sql.gz"
    print("BOUNDARY=NEW_UNBOUND_ISOLATED_DB_ONLY",flush=True)
    print("ORIGINAL_TARGET_DATABASE_PRESERVED=YES",flush=True)
    print("OLD_SOURCE_BUSINESS_DATABASE_WRITES=NONE",flush=True)
    try:
        # Preserve the complete CURRENT CP2 target before creating a scratch
        # DB. This includes all five target-only and six changed-key rows.
        # CloudPanel export is a READ of the original site DB into this 0700
        # evidence directory; it does not overwrite any database.
        target_dump=ROOT/"protected-original-target.sql.gz"
        try:
            cloudpanel.export_database(original_target,target_dump,clpctl="clpctl")
        except (cloudpanel.CloudPanelError,ValueError):
            raise Block("EXISTING_TARGET_PROTECTED_EXPORT_FAILED") from None
        need(target_dump.is_file() and not target_dump.is_symlink()
             and target_dump.stat().st_size>0,
             "EXISTING_TARGET_PROTECTED_EXPORT_NOT_FOUND")
        target_dump.chmod(0o600)
        _n,target_tables=base.inspect_archive(target_dump)
        need(target_tables==42,"EXISTING_TARGET_42_TABLES_EXPORT_UNVERIFIED")
        record.update({"status":"EXISTING_TARGET_ARCHIVE_PROTECTED",
                       "target_dump_sha256":base.sha256_file(target_dump),
                       "target_ddl_table_count":target_tables})
        save(record)
        print("PROTECTED_EXISTING_TARGET_ARCHIVE=SHA256_RECORDED",flush=True)
        code=base.REMOTE_EXPORT
        cmd=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
            "PYTHONPATH="+state["source_runtime_path"]+"/lib",
            "python3","-B","-c",code,DOMAIN,source_db,MID,token])
        result=engine.source_remote(state["source"],cmd,timeout=1800,check=False)
        need(result.returncode==0 and
             result.stdout.strip()=="SOURCE_EXPORT_READY=YES",
             "OLD_SOURCE_SNAPSHOT_EXPORT_FAILED")
        record["status"]="SOURCE_EXPORTED";save(record)
        engine.pull_path(state["source"],remote_dump,dump)
        dump.chmod(0o600)
        uncompressed,table_count=base.inspect_archive(dump)
        need(table_count==42,"SOURCE_EXPORT_42_CREATE_TABLES_NOT_VERIFIED")
        actual_sha=base.sha256_file(dump)
        result=engine.source_remote(state["source"],
            "sha256sum -- "+shlex.quote(remote_dump),timeout=90,check=False)
        parts=result.stdout.split()
        need(result.returncode==0 and len(parts)>=1 and
             re.fullmatch("[a-f0-9]{64}",parts[0]) is not None and
             parts[0]==actual_sha,"SOURCE_SNAPSHOT_TRANSFER_HASH_MISMATCH")
        record.update({"status":"SOURCE_ARCHIVE_SHA256_PASS",
            "source_dump_sha256":actual_sha,
            "source_ddl_table_count":table_count,
            "source_uncompressed_bytes":uncompressed})
        save(record)
        print("PROTECTED_SOURCE_EXPORT_SHA256=PASS",flush=True)
        print("SOURCE_DDL_TABLES=42",flush=True)
        # CloudPanel registers this as another, UNIQUE DB under the same site,
        # but neither modifies the existing target DB nor rewrites app config.
        creds=ROOT/"scratch-credentials.json"
        fd=os.open(creds,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w") as f:
            json.dump({"database":scratch_db,"user":scratch_user,
                       "password":scratch_password},f)
        record["status"]="SCRATCH_DB_CREATION_STARTED";save(record)
        try:cloudpanel.add_database(DOMAIN,scratch_db,scratch_user,
                                     scratch_password,clpctl="clpctl")
        except (cloudpanel.CloudPanelError,ValueError):
            raise Block("SCRATCH_DATABASE_CREATE_FAILED") from None
        need(panel_link_count(scratch_db)==1 and
             panel_link_count(original_target)==1 and
             base._master_sql_presence(scratch_db,scratch_user)==("1","1"),
             "SCRATCH_OR_ORIGINAL_TARGET_REGISTRATION_CHANGED")
        record["status"]="SCRATCH_DB_CREATED";save(record)
        print("SCRATCH_DATABASE_CREATED=YES",flush=True)
        record["status"]="ISOLATED_IMPORT_STARTED";save(record)
        need(base.isolated_import(scratch_user,scratch_password,scratch_db,dump,ROOT),
             "SCRATCH_IMPORT_FAILED_NO_AUTORETRY")
        record["status"]="ISOLATED_IMPORT_COMPLETED_NOT_VERIFIED";save(record)
        print("ISOLATED_SOURCE_RESTORE=IMPORTED",flush=True)
        tables,rows=readback(scratch_db,scratch_user,scratch_password)
        need(tables==42,"SCRATCH_42_TABLE_READBACK_FAILED")
        record["status"]="ISOLATED_SOURCE_READBACK_PASS"
        record["readback_tables"]=tables
        record["readback_rows"]=rows
        save(record)
        print("SCRATCH_READBACK_TABLES="+str(tables),flush=True)
        print("SCRATCH_READBACK_ROWS="+str(rows),flush=True)
        print("ISOLATED_SOURCE_READBACK=PASS",flush=True)
        print("SOURCE_SNAPSHOT_ROW_VALUE_PARITY=NOT_VERIFIED",flush=True)
        return 0
    except Block as exc:
        record["status"]="BLOCKED"
        record["blocker"]=str(exc)
        save(record)
        print("BLOCKED="+str(exc),flush=True)
        return 13
    except Exception:
        record["status"]="BLOCKED"
        record["blocker"]="UNCLASSIFIED_ISOLATED_RESTORE_FAILURE"
        save(record)
        print("BLOCKED=UNCLASSIFIED_ISOLATED_RESTORE_FAILURE",flush=True)
        return 13
    finally:
        try:
            cleanup="rm -f -- "+shlex.quote(remote_dump)+"; rmdir -- "+shlex.quote(remote_dir)
            result=engine.source_remote(state["source"],cleanup,timeout=120,check=False)
            print("SOURCE_TEMP_CLEANUP="+("PASS" if result.returncode==0 else "NOT_CONFIRMED"),flush=True)
        except Exception:
            print("SOURCE_TEMP_CLEANUP=NOT_CONFIRMED",flush=True)
        print("CP2_ISOLATED_RECOVERY_STATUS="+str(ROOT/"status.json"),flush=True)
        print("ORIGINAL_TARGET_DATABASE_MODIFIED=NO",flush=True)
        print("SOURCE_BUSINESS_DATABASE_WRITES=NONE",flush=True)
        print("WEBSITE_CONFIGURATION_CHANGED=NO",flush=True)
        print("DNS_CHANGED=NO",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        print("AUTOMATIC_RETRY=NO",flush=True)
if __name__=="__main__":
    try:raise SystemExit(run())
    except Block as exc:
        print("BLOCKED="+str(exc),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=UNVERIFIED_ISOLATED_RESTORE_PREFLIGHT",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
