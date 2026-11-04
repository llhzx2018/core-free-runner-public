#!/usr/bin/env python3
"""CP2 only: bounded local, secret-free evidence for three PENDING site databases.

Not an import or verification of source/target parity. No service or DB socket
connections. Source VPS stays untouched; DNS/Cron/Cutover remain disabled.
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
BASE=HERE/"p07-17-site-staged-local-evidence.py"
EXPECTED_BASE_BLOB="7296ea88fe0d096bc622671bf20f1b2b7aa18f5c"
EXPECTED_DOMAINS=("ilovem3u8.kewaro.com","unzip.kewaro.com","www3.m3u8.one")
WWW3="pull-20261031T095604Z-edae3c44"
WWW3_RECOVERY=Path("/var/lib/vf-server-ops/server-migrations")/WWW3/"recovery-scratch-www3"
BACKUP_MANIFESTS=(
 Path("/var/backups/vf-server-ops/ilovem3u8.kewaro.com_20261030T095348Z/manifest.json"),
 Path("/var/backups/vf-server-ops/ilovem3u8.kewaro.com_20261030T104255Z/manifest.json"),
 Path("/root/p07-recovery-source-20261030T104255Z/manifest.json"),
)
class Block(Exception):pass
def need(ok,label):
    if not ok:raise Block(label)
def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+bytes([0])+data).hexdigest()
def companion():
    try:
        need(not BASE.is_symlink() and BASE.is_file() and
             blob(BASE.read_bytes())==EXPECTED_BASE_BLOB,
             "BASELINE_IDENTITY_MISMATCH")
        spec=importlib.util.spec_from_file_location("p07_pending_verified",BASE)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except OSError:raise Block("BASELINE_MISSING") from None
base=companion()
def private_file(path,limit=1048576):
    try:meta=path.lstat()
    except FileNotFoundError:return "ABSENT",None
    except OSError:raise Block("PRIVATE_FILE_STAT_UNAVAILABLE") from None
    need(stat.S_ISREG(meta.st_mode) and meta.st_uid==0 and not meta.st_mode&0o077
         and 0<meta.st_size<=limit,"PRIVATE_EVIDENCE_KIND_OWNER_OR_PERMISSIONS_CHANGED")
    return "PRESENT",path
def read_record(path):
    status,p=private_file(path)
    if p is None:return status,None
    try:obj=json.loads(p.read_text(encoding="utf8"))
    except (OSError,ValueError,UnicodeError):
        raise Block("PRIVATE_EVIDENCE_JSON_INVALID") from None
    need(type(obj) is dict,"PRIVATE_RECORD_NOT_OBJECT")
    return "PRESENT",obj
def site_evidence():
    bydomain={}
    states=[]
    for label,mid,count in base.JOBS:
        state=base.secure_state(base.ROOT/mid/"state.json")
        need(state.get("schema")==base.SCHEMA and state.get("migration_id")==mid
             and state.get("status")=="PREPARE_FAILED"
             and type(state.get("sites")) is list and len(state["sites"])==count,
             "MIGRATION_STATE_SCOPE_CHANGED")
        for flag in ("source_runtime_frozen","target_runtime_activated",
                     "dns_changed_by_p07","source_delete_allowed",
                     "existing_target_overwrite_allowed"):
            need(state.get(flag) is False,"MIGRATION_SAFETY_BOUNDARY_CHANGED")
        for row in state["sites"]:
            need(type(row) is dict and type(row.get("domain")) is str,
                 "INVALID_SITE_ROW")
            bydomain[row["domain"]]=(label,row)
        states.append(state)
    need(states[1].get("partial_parent_migration_id")==base.JOBS[0][1]
         and states[2].get("partial_parent_migration_id")==base.JOBS[1][1],
         "MIGRATION_CHAIN_CHANGED")
    need(all(s.get("target_server_identity")==states[0].get("target_server_identity")
             for s in states[1:]),"CP2_TARGET_IDENTITY_CHANGED")
    staged={d for d,(_,row) in bydomain.items()
            if row.get("stage_status")=="PULLED_STAGED"}
    pending={d for d,(_,row) in bydomain.items()
             if row.get("stage_status")=="PENDING"}
    need(staged==base.EXPECTED_STAGED and pending==base.EXPECTED_PENDING,
         "17_SITE_STAGED_PENDING_SCOPE_CHANGED")
    return bydomain
def safe_status(value):
    allowed={"SOURCE_EXPORT_IN_PROGRESS","SOURCE_EXPORTED",
             "SOURCE_COPY_PROTECTED","SAFE_NAME_DATABASE_CREATED",
             "ISOLATED_DATABASE_CREATED","ISOLATED_IMPORT_COMPLETED_NOT_VERIFIED",
             "BLOCKED","ISOLATED_IMPORT_READBACK_PASS"}
    return value if type(value) is str and value in allowed else "OTHER_OR_UNKNOWN"
def archive_proof(rec,path):
    if rec is None:return "RECOVERY_RECORD_MISSING"
    present,p=private_file(path,limit=2*1024*1024*1024)
    if p is None:return "ARCHIVE_ABSENT"
    expected=rec.get("source_dump_sha256")
    if type(expected) is not str or re.fullmatch(r"[a-f0-9]{64}",expected) is None:
        return "NO_PINNED_SHA256"
    sha=hashlib.sha256()
    with p.open("rb") as reader:
        while True:
            part=reader.read(1024*1024)
            if not part:break
            sha.update(part)
    return "SHA256_PASS" if sha.hexdigest()==expected else "SHA256_MISMATCH"
def backup_manifest_presence(path):
    """Metadata existence only; historical backup manifests may be world-readable."""
    try:meta=path.lstat()
    except FileNotFoundError:return "ABSENT"
    except OSError:return "UNREADABLE"
    return ("PRESENT" if stat.S_ISREG(meta.st_mode) and meta.st_uid==0
            and not meta.st_mode&0o022 and meta.st_size<8*1024*1024
            else "UNSAFE_OR_UNVERIFIED")
def run():
    need(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    need(sys.argv[1:]==["--audit-three-pending-site-databases-readonly"],
         "EXPLICIT_THREE_PENDING_DB_AUDIT_REQUIRED")
    sites=site_evidence()
    print("PROBE=CP2_THREE_PENDING_DATABASE_EVIDENCE",flush=True)
    print("PENDING_SITE_COUNT=3",flush=True)
    for name in EXPECTED_DOMAINS:
        label,row=sites[name]
        dbs=row.get("mysql_databases")
        need(type(dbs) is list and all(type(x) is str for x in dbs),
             "PENDING_DATABASE_LIST_FORMAT_CHANGED")
        verify=row.get("mysql_verification",[])
        if type(verify) is not list:verify=[]
        passes=sum(type(x) is dict and x.get("phase")=="prepare"
                   and x.get("status")=="PASS" for x in verify)
        print("SITE="+name+" LAST_JOB="+label+
              " STATUS=PENDING DATABASES_DECLARED="+str(len(dbs))+
              " PREPARE_DB_PASS_RECORDS="+str(passes)+
              " DATA_PARITY=NOT_VERIFIED",flush=True)
    for i,manifest in enumerate(BACKUP_MANIFESTS,1):
        status=backup_manifest_presence(manifest)
        print("ILOVEM3U8_PROTECTED_BACKUP_MANIFEST_"+str(i)+"="+status,
              flush=True)
    record_path=WWW3_RECOVERY/"status.json"
    present,record=read_record(record_path)
    print("WWW3_SCRATCH_STATUS_FILE="+present,flush=True)
    if record is not None:
        need(record.get("original_site")=="www3.m3u8.one"
             and record.get("migration_id")==WWW3
             and record.get("site_config_modified") is False
             and record.get("existing_target_database_modified") is False
             and record.get("dns_changed") is False
             and record.get("source_frozen") is False
             and record.get("cutover_allowed") is False,
             "WWW3_SCRATCH_PROTECTION_CHANGED")
        print("WWW3_SCRATCH_STAGE="+safe_status(record.get("status")),flush=True)
        print("WWW3_SOURCE_PROTECTED_ARCHIVE="+
              archive_proof(record,WWW3_RECOVERY/"source.sql.gz"),flush=True)
        creds,p=private_file(WWW3_RECOVERY/"scratch-credentials.json")
        print("WWW3_PRIVATE_SCRATCH_CREDENTIAL_RECORD="+creds,flush=True)
        print("WWW3_SCRATCH_IMPORT_COMPLETED_RECORDED="+(
            "YES" if record.get("status")=="ISOLATED_IMPORT_COMPLETED_NOT_VERIFIED"
            else "NOT_PROVEN"),flush=True)
    print("ILOVEM3U8_CONFLICT_RESOLUTION=NOT_AUTHORIZED",flush=True)
    print("UNZIP_CONDITIONAL_SQL_RECOVERY=NOT_AUTHORIZED",flush=True)
    print("WWW3_SCRATCH_PROMOTION=NOT_AUTHORIZED",flush=True)
    print("OLD_SERVER_CONTACTED=NO",flush=True)
    print("MYSQL_CONNECTIONS_AND_WRITES=NONE",flush=True)
    print("PRIVATE_EVIDENCE_MODIFIED=NO",flush=True)
    print("CRON_ACTIVATED=NO",flush=True)
    print("DNS_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0
if __name__=="__main__":
    try:raise SystemExit(run())
    except (Block,base.Block) as exc:
        print("BLOCKED="+str(exc),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=PRIVATE_THREE_DB_EVIDENCE_UNVERIFIED",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
