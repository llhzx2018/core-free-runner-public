#!/usr/bin/env python3
"""P07: independently verify the existing ilovem3u8 isolated recovery, read-only.

No source VPS contact, no new export/import, no DB creation or data modification.
Keep source archive, original CP2 target archive, scratch and migration state
immutable. SQL literal tuple counts are advisory, not semantic parity proofs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
STAGE_FILE=HERE/"p07-ilovem3u8-isolated-source-restore.py"
STAGE_BLOB="f35bc8d04f675c278197f7aef653776363ec9e50"
BASE_FILE=HERE/"p07-www3-isolated-restore.py"
BASE_BLOB="1b3b9285853cc99e467f70d92c7d2b0222874018"
MID="pull-20261028T103425Z-98050c76"
DOMAIN="ilovem3u8.kewaro.com"
ROOT=Path("/var/lib/vf-server-ops/server-migrations")/MID/"recovery-scratch-ilovem3u8"
STATE=ROOT.parent/"state.json"
class Block(Exception):pass
def need(value,code):
    if not value:raise Block(code)
def blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def sha256(path):
    hash=hashlib.sha256()
    with path.open("rb") as stream:
        for item in iter(lambda:stream.read(1024*1024),b""):
            hash.update(item)
    return hash.hexdigest()
def pinned(path,expected,name):
    try:
        need(path.is_file() and not path.is_symlink() and
             blob(path.read_bytes())==expected,"PINNED_HELPER_"+name+"_CHANGED")
        spec=importlib.util.spec_from_file_location("p07_recovery_"+name,path)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except OSError:raise Block("PINNED_HELPER_"+name+"_UNAVAILABLE") from None
def private_dir(path):
    try:x=path.lstat()
    except OSError:raise Block("PRIVATE_RECOVERY_DIRECTORY_MISSING") from None
    need(stat.S_ISDIR(x.st_mode) and x.st_uid==0 and not x.st_mode&0o077
         and not path.is_symlink(),"PRIVATE_RECOVERY_DIRECTORY_UNSAFE")
def private_file(path,maxsize):
    try:x=path.lstat()
    except OSError:raise Block("PRIVATE_RECOVERY_FILE_MISSING") from None
    need(stat.S_ISREG(x.st_mode) and x.st_uid==0 and not x.st_mode&0o077
         and not path.is_symlink() and 0<x.st_size<=maxsize,
         "PRIVATE_RECOVERY_FILE_UNSAFE")
    return path
def record(path):
    private_file(path,1048576)
    try:data=json.loads(path.read_text("utf-8"))
    except (OSError,ValueError,UnicodeError):
        raise Block("PRIVATE_RECOVERY_STATE_INVALID") from None
    need(type(data) is dict,"PRIVATE_RECOVERY_STATE_NOT_OBJECT")
    return data
def safe_names(value,user):
    a=re.fullmatch(r"p07scratch-([0-9a-f]{12})",value or "")
    b=re.fullmatch(r"p07stage-([0-9a-f]{12})",user or "")
    need(a is not None and b is not None and a.group(1)==b.group(1),
         "SCRATCH_DATABASE_USER_IDENTITY_CHANGED")
def protect_archives(stage,base,rec,root):
    outputs={}
    for kind,filename,sha_key,ddl_key in (
        ("SOURCE","source.sql.gz","source_dump_sha256","source_ddl_table_count"),
        ("ORIGINAL_TARGET","protected-original-target.sql.gz","target_dump_sha256","target_ddl_table_count"),
    ):
        path=private_file(root/filename,2*1024*1024*1024)
        want=rec.get(sha_key)
        need(type(want) is str and re.fullmatch("[a-f0-9]{64}",want) and
             sha256(path)==want,"PROTECTED_"+kind+"_ARCHIVE_SHA_CHANGED")
        size,tables=base.inspect_archive(path)
        need(tables==rec.get(ddl_key)==42 and size>0,
             "PROTECTED_"+kind+"_42_TABLE_DDL_CHANGED")
        if kind=="SOURCE":
            need(size==rec.get("source_uncompressed_bytes"),
                 "PROTECTED_SOURCE_UNCOMPRESSED_SIZE_CHANGED")
        outputs[kind+"_ARCHIVE"]="SHA256_PASS"
        outputs[kind+"_DDL_TABLES"]=tables
    return outputs
def cloudpanel_site_db_names(path=Path("/home/clp/htdocs/app/data/db.sq3")):
    try:
        con=sqlite3.connect(f"file:{path}?mode=ro",uri=True,timeout=3)
        try:
            items=con.execute(
                'SELECT d.name FROM "database" d JOIN "site" s '
                'ON d.site_id=s.id WHERE s.domain_name=?',(DOMAIN,)).fetchall()
        finally:con.close()
    except (sqlite3.Error,OSError):
        raise Block("CLOUDPANEL_SITE_DB_INVENTORY_UNAVAILABLE") from None
    need(len(items)==2 and len({x[0] for x in items})==2
         and all(type(x[0]) is str and re.fullmatch("[A-Za-z0-9._-]{1,64}",x[0])
                 for x in items),"SITE_DB_SCOPE_NOT_ORIGINAL_PLUS_ONE_SCRATCH")
    return {x[0] for x in items}
def archive_tuple_count(path):
    # Optional semantic-insufficient but independent SQL INSERT tuple count.
    # The count can be unavailable on unsupported SQL grammar. No raw SQL
    # or table names are ever printed, and it does not waive the main gate.
    try:
        import sql_row_evidence
        count=0
        for statement in sql_row_evidence._statements(path):
            for _ in sql_row_evidence._rows(statement):
                count+=1
                if count>5000000:return "UNAVAILABLE"
        return count if count>0 else "UNAVAILABLE"
    except (Exception,):
        return "UNAVAILABLE"
def verify(stage,base,root=ROOT,state=STATE):
    private_dir(root)
    rec=record(root/"status.json")
    old=record(state)
    need(old.get("schema")=="vf-server-ops.server-migration.target-pull.v1"
         and old.get("migration_id")==MID
         and old.get("status")=="PREPARE_FAILED"
         and old.get("source_runtime_frozen") is False
         and old.get("dns_changed_by_p07") is False
         and old.get("source_delete_allowed") is False
         and old.get("existing_target_overwrite_allowed") is False,
         "ORIGINAL_MIGRATION_PROTECTION_CHANGED")
    sites=old.get("sites")
    need(type(sites) is list and len(sites)==17 and type(sites[7]) is dict
         and sites[7].get("domain")==DOMAIN
         and sites[7].get("stage_status")=="PENDING",
         "ORIGINAL_MIGRATION_SITE_STATE_CHANGED")
    need(rec.get("migration_id")==MID and rec.get("original_site")==DOMAIN
         and rec.get("status")=="ISOLATED_SOURCE_READBACK_PASS"
         and rec.get("cutover_allowed") is False
         and rec.get("source_frozen") is False
         and rec.get("dns_changed") is False
         and rec.get("site_config_modified") is False
         and rec.get("existing_target_database_modified") is False
         and rec.get("original_target_preserved") is True,
         "ISOLATED_RECOVERY_STATE_CHANGED")
    db,user=rec.get("scratch_database"),rec.get("scratch_user")
    safe_names(db,user)
    creds=record(root/"scratch-credentials.json")
    password=creds.get("password")
    need(creds.get("database")==db and creds.get("user")==user
         and type(password) is str and 30<=len(password)<=96
         and not any(x in password for x in ("\r","\n","\0")),
         "SCRATCH_PRIVATE_CREDENTIAL_CHANGED")
    exports=protect_archives(stage,base,rec,root)
    names=cloudpanel_site_db_names()
    need(db in names and len(names-{db})==1,
         "ORIGINAL_CP2_DATABASE_REGISTRATION_CHANGED")
    original=next(iter(names-{db}))
    need(stage.panel_link_count(db)==1 and stage.panel_link_count(original)==1
         and base._master_sql_presence(db,user)==("1","1"),
         "SCRATCH_CP2_ORIGINAL_BINDING_CHANGED")
    tables,rows=stage.readback(db,user,password)
    need(tables==rec.get("readback_tables")==42 and
         rows==rec.get("readback_rows")==1013,
         "ISOLATED_SNAPSHOT_READBACK_CHANGED")
    source_tuples=archive_tuple_count(root/"source.sql.gz")
    target_tuples=archive_tuple_count(root/"protected-original-target.sql.gz")
    if type(source_tuples) is int:
        need(source_tuples==rows,"SOURCE_EXPORT_SQL_ROW_COUNT_DIFFERS_FROM_SCRATCH")
    return {
        **exports,
        "SCRATCH_TABLES":tables,
        "SCRATCH_ROWS":rows,
        "ORIGINAL_CP2_TARGET_ARCHIVE_PRESERVED":"YES",
        "SOURCE_SQL_INSERT_TUPLES_ADVISORY":source_tuples,
        "TARGET_SQL_INSERT_TUPLES_ADVISORY":target_tuples,
        "PROTECTED_ISOLATED_RECOVERY_READBACK":"PASS",
        "RAW_SOURCE_EXPORT_TO_DB_VALUE_PARITY":"NOT_VERIFIED",
        "POST_EXPORT_SOURCE_CHANGES":"NOT_CHECKED",
        "DATABASE_WRITES":"NONE","SOURCE_VPS_CONTACTED":"NO",
        "SITE_CONFIG_WRITES":"NONE","CUTOVER_ALLOWED":"NO",
    }
def main():
    need(os.geteuid()==0 and sys.argv[1:]==["--verify-protected-isolated-ilovem3u8-read-only"],
         "EXPLICIT_ISOLATED_READONLY_GATE_REQUIRED")
    stage=pinned(STAGE_FILE,STAGE_BLOB,"stage")
    base=pinned(BASE_FILE,BASE_BLOB,"base")
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    for key,value in verify(stage,base).items():
        print(str(key)+"="+str(value),flush=True)
    return 0
if __name__=="__main__":
    try:raise SystemExit(main())
    except Block as e:
        print("BLOCKED="+str(e),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=UNVERIFIED_PROTECTED_ISOLATED_READBACK",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
