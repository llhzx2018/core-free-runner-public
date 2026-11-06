"""P07 original three DB twice-read private SQL copy after proven old-source runtime pause.

Neither the source runtime freeze nor two stable SQL exports proves that every
independent database writer is fenced. No old or target business database is
changed; no app config, live site path, Cron, PM2 or DNS is changed. Records
remain for recovery and cannot be blindly replayed after an SSH timeout.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping

import migration_chain_final_saga as saga
import migration_chain_private_file_stage as files
import migration_chain_source_pause as pause
import migration_three_site_window as window
import server_migration as legacy

SCHEMA="P07_EXISTING_3_DB_PAUSED_TWO_PASS_PRIVATE_COPY_V1"
ROOT_NAME="p07-three-paused-source-db-private-v1"
CONFIRM="COPY_PAUSED_THREE_SOURCE_DATABASES_PRIVATE_ONLY"


class PausedDatabaseBlocked(RuntimeError):
    pass


def require(ok:bool,reason:str)->None:
    if not ok:
        raise PausedDatabaseBlocked(reason)


def _private(plan:Mapping[str,Any],parent:Path)->Path:
    try:
        root=files._private_parent(plan,parent)
    except files.WarmStageBlocked:
        raise PausedDatabaseBlocked("PAUSED_SQL_PRIVATE_PARENT_UNSAFE") from None
    return root.parent/ROOT_NAME


def _owners(plan,originals,target_identity):
    try:
        files._identity(plan,originals,target_identity)
    except files.WarmStageBlocked:
        raise PausedDatabaseBlocked("PAUSED_SQL_THREE_OWNER_SCOPE_DRIFT") from None
    ids={s.get("migration_id"):s for s in originals}
    rows=[]
    for domain in window.OWNER_SITES:
        steps=[s for s in plan["steps"][:17] if s["domain"]==domain]
        require(len(steps)==1,"PAUSED_SQL_OWNER_SITE_UNBOUND")
        step=steps[0]
        state=ids[step["owner"]]
        site=state["sites"][step["index"]]
        dbs=site.get("mysql_databases")
        require(type(dbs) is list and len(dbs)==1
                and type(dbs[0]) is str
                and re.fullmatch(r"[A-Za-z0-9_]+",dbs[0]) is not None,
                "PAUSED_SQL_OWNER_DB_INVALID")
        rows.append((domain,step["owner"],dbs[0]))
    require(len({d for d,_o,_db in rows})==3
            and len({o for _d,o,_db in rows})==3
            and len({db for _d,_o,db in rows})==3,
            "PAUSED_SQL_THREE_DB_IDENTITY_COLLISION")
    return rows


def _paused_source_proof(plan,originals,root,target_identity):
    import server_migration_pull as pull
    mid,ctl,digest=pause._control(plan,originals,target_identity)
    private=pause._private(plan,root)
    try:
        receipt=pause._read_journal(
            private/"journal.json",plan_sha=plan["plan_sha256"],
            target_sha=plan["target_identity_sha256"])
    except pause.SourcePauseBlocked:
        raise PausedDatabaseBlocked(
            "PAUSED_SQL_CP2_PAUSE_RECEIPT_UNAVAILABLE") from None
    require(receipt.get("status")
            =="SOURCE_RUNTIME_PAUSED_DB_WRITE_FENCE_NOT_PROVEN"
            and receipt.get("source_recovery_id")==mid
            and receipt.get("control_sha256")==digest
            and receipt.get("source_runtime_paused") is True
            and receipt.get("source_business_writes_paused") is False
            and receipt.get("source_final_database_parity") is False
            and receipt.get("cutover_allowed") is False,
            "PAUSED_SQL_CP2_PAUSE_RECEIPT_NOT_PROVEN")
    runtime=f"/var/lib/vf-server-ops/pull-source/{mid}/runtime"
    source=originals[0]["source"]
    try:
        response=pull.source_python(
            source,runtime,"_source-frozen-readback",
            "--migration-id",mid,timeout=60,check=False)
        require(response.returncode==0,
                "PAUSED_SQL_OLD_SOURCE_READBACK_FAILED")
        output=json.loads(response.stdout)
    except Exception:
        raise PausedDatabaseBlocked(
            "PAUSED_SQL_OLD_SOURCE_READBACK_UNAVAILABLE") from None
    require(output.get("status")
            =="SOURCE_17_RUNTIME_STOP_READBACK_PASS_NOT_DATABASE_FENCE"
            and output.get("migration_id")==mid
            and output.get("site_count")==17
            and output.get("source_nginx_inactive_verified") is True
            and output.get("cron_pm2_journal_verified") is True
            and output.get("source_business_writers_all_fenced") is False
            and output.get("cutover_allowed") is False,
            "PAUSED_SQL_OLD_SOURCE_PAUSE_CHANGED")
    return mid,runtime,source


def _digest_file(path:Path)->tuple[str,int]:
    try:
        info=path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink==1
                and info.st_uid==os.geteuid()
                and not stat.S_IMODE(info.st_mode)&0o077
                and info.st_size>0,
                "PAUSED_SQL_PRIVATE_DUMP_UNSAFE")
        digest=hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(1048576),b""):
                digest.update(chunk)
        return digest.hexdigest(),info.st_size
    except OSError:
        raise PausedDatabaseBlocked("PAUSED_SQL_PRIVATE_DUMP_UNREADABLE") from None


def copy_paused_three_source_dbs(
    plan:Mapping[str,Any],
    originals:tuple[Mapping[str,Any],...],*,
    root:Path,target_identity:str,confirmation:str="",
)->dict[str,Any]:
    require(confirmation==CONFIRM,
            "PAUSED_SQL_SEPARATE_PRIVATE_SOURCE_COPY_CONFIRM_REQUIRED")
    rows=_owners(plan,originals,target_identity)
    destination=_private(plan,root)
    require(not os.path.lexists(destination),
            "PAUSED_SQL_PREVIOUS_ATTEMPT_RETAINED")
    import server_migration_pull as pull
    require(pull.target_identity()==target_identity,
            "PAUSED_SQL_LOCAL_TARGET_CHANGED")
    mid,runtime,source=_paused_source_proof(
        plan,originals,root,target_identity)
    # Store private intent BEFORE the first source file transfer/export.
    destination.mkdir(mode=0o700)
    journal=destination/"journal.json"
    record={
        "schema":SCHEMA,"status":"PRIVATE_INTENT_RECORDED",
        "plan_sha256":plan["plan_sha256"],
        "target_identity_sha256":plan["target_identity_sha256"],
        "source_recovery_id":mid,
        "original_database_count":3,
        "completed":[],
        "active_domain":None,
        "source_runtime_paused":True,
        "source_business_writers_all_fenced":False,
        "source_target_database_parity":False,
        "existing_target_databases_modified":False,
        "source_business_databases_modified":False,
        "cutover_allowed":False,
    }
    legacy.atomic_private_json(journal,record)
    # Two separated sweeps A/B/C then A/B/C. Never conclude frozen writer
    # proof from matching exports; they are evidence for data stability only.
    passes=[{},{}]
    try:
        for index in range(2):
            for domain,owner,db in rows:
                token=hashlib.sha256(
                    f"{mid}:{owner}:{domain}:{db}".encode()).hexdigest()[:20]
                local=destination/f"{token}-pass{index+1}.sql.gz"
                remote=f"/var/lib/vf-server-ops/pull-source/{mid}/sql-{token}-p{index+1}.sql.gz"
                require(not os.path.lexists(local),
                        "PAUSED_SQL_PRIVATE_COPY_EXISTS")
                record["status"]="SOURCE_EXPORT_TRANSFER_INTENT"
                record["active_domain"]=domain
                record["active_pass"]=index+1
                legacy.atomic_private_json(journal,record)
                # An old-server export failure can leave a partial dump.
                # Do NOT remove it until the entire newly created source
                # export has been transferred and validated on CP2. In
                # particular, a timeout cannot prove which remote file
                # belongs to this invocation rather than a prior failure.
                copy_verified=False
                cleanup_ok=False
                try:
                    proc=pull.source_python(
                        source,runtime,"_source-export-db",
                        "--database",db,"--output",remote,
                        timeout=1200,check=False)
                    require(proc.returncode==0,
                            "PAUSED_SQL_SOURCE_EXPORT_FAILED")
                    pull.pull_path(source,remote,local,delete=False)
                    # The protected SQL parser may reject conditional or
                    # dynamic side effects; do not weaken it for www3.
                    os.chmod(local,0o600)
                    digest,size=_digest_file(local)
                    pull.sql_diff_probe.require_nonempty_source_schema(local)
                    passes[index][domain]=(local,digest,size,owner)
                    copy_verified=True
                finally:
                    if copy_verified:
                        # Only the successful, already read-back temporary
                        # source export may be cleaned. Failed exports or
                        # partial transfers retain their original evidence.
                        try:
                            proc=pull.source_remote(
                                source,"rm -f -- "+pull.shlex.quote(remote),
                                timeout=60,check=False)
                            cleanup_ok=proc.returncode==0
                        except Exception:
                            cleanup_ok=False
                        if not cleanup_ok:
                            record["status"]="SOURCE_PRIVATE_SQL_CLEANUP_UNVERIFIED"
                            legacy.atomic_private_json(journal,record)
                require(cleanup_ok,"PAUSED_SQL_SOURCE_TEMP_CLEANUP_UNVERIFIED")
                record["status"]="SOURCE_PRIVATE_DUMP_READBACK_NOT_FINAL"
                record.pop("active_domain",None)
                record.pop("active_pass",None)
                legacy.atomic_private_json(journal,record)
        for domain,owner,db in rows:
            a,sha1,size1,_=passes[0][domain]
            b,sha2,size2,_=passes[1][domain]
            mode=pull.compare_database_dumps(a,b)
            require(bool(mode),"PAUSED_SQL_SOURCE_PASSES_DIFFER")
            record["completed"].append({
                "domain":domain,"original_owner":owner,
                "pass_1_sha256":sha1,"pass_2_sha256":sha2,
                "pass_1_bytes":size1,"pass_2_bytes":size2,
                "pass_1_name":a.name,"pass_2_name":b.name,
                "source_two_pass_verification_mode":mode,
                "final_target_parity":False,
            })
            legacy.atomic_private_json(journal,record)
    except Exception:
        if record["status"]!="SOURCE_PRIVATE_SQL_CLEANUP_UNVERIFIED":
            record["status"]="PRIVATE_OR_SOURCE_RECOVERY_REQUIRED_RETAIN"
        legacy.atomic_private_json(journal,record)
        raise PausedDatabaseBlocked(
            "PAUSED_SQL_TRANSFER_OR_TWO_PASS_RECOVERY_REQUIRED") from None
    record["status"]="THREE_ORIGINAL_DB_TWO_PASS_PRIVATE_STABLE_NOT_CUTOVER"
    legacy.atomic_private_json(journal,record)
    return {
        "status":record["status"],
        "site_count":17,"original_database_count":3,
        "private_source_dumps_verified":6,
        "source_runtime_paused":True,
        "source_business_writers_all_fenced":False,
        "source_target_database_parity":False,
        "existing_target_databases_modified":False,
        "cutover_allowed":False,
    }


def verify_paused_three_source_dbs(
    plan:Mapping[str,Any],
    originals:tuple[Mapping[str,Any],...],*,
    root:Path,target_identity:str,
)->dict[str,Any]:
    rows=_owners(plan,originals,target_identity)
    destination=_private(plan,root)
    try:
        record=saga._read_receipt(destination/"journal.json",
                                  expected_schema=SCHEMA)
    except saga.SagaBlocked:
        raise PausedDatabaseBlocked(
            "PAUSED_SQL_JOURNAL_UNAVAILABLE") from None
    require(record.get("status")
            =="THREE_ORIGINAL_DB_TWO_PASS_PRIVATE_STABLE_NOT_CUTOVER"
            and record.get("plan_sha256")==plan["plan_sha256"]
            and record.get("target_identity_sha256")
            ==plan["target_identity_sha256"]
            and record.get("original_database_count")==3
            and record.get("source_runtime_paused") is True
            and record.get("source_business_writers_all_fenced") is False
            and record.get("source_target_database_parity") is False
            and record.get("cutover_allowed") is False,
            "PAUSED_SQL_FINAL_RECEIPT_DRIFT")
    require(type(record.get("source_recovery_id")) is str
            and record["source_recovery_id"].startswith(
                "pull-p07-17sites-"),
            "PAUSED_SQL_SOURCE_RECOVERY_ID_CHANGED")
    completed=record.get("completed")
    require(type(completed) is list and len(completed)==3,
            "PAUSED_SQL_COVERAGE_CHANGED")
    by_domain={r.get("domain"):r for r in completed if isinstance(r,dict)}
    require(len(by_domain)==3 and set(by_domain)=={r[0] for r in rows},
            "PAUSED_SQL_OWNERS_CHANGED")
    # The journal records checksums for each pass, but two independently
    # exported dumps may contain different row data while each hash is
    # individually correct. Always redo the guarded full SQL comparator.
    import server_migration_pull as pull
    accepted_modes={
        "CANONICAL_SQL_EXACT",
        "CROSS_ENGINE_GUARDED_SESSION_SQL_EXACT",
        "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
        "CROSS_ENGINE_LOGICAL_CONTENT",
    }
    for domain,owner,db in rows:
        item=by_domain[domain]
        expected_token=hashlib.sha256(
            f"{record['source_recovery_id']}:{owner}:{domain}:{db}".encode()
        ).hexdigest()[:20]
        expected_mode=item.get("source_two_pass_verification_mode")
        require(item.get("original_owner")==owner
                and item.get("final_target_parity") is False
                and type(expected_mode) is str
                and expected_mode in accepted_modes,
                "PAUSED_SQL_ORIGINAL_OWNER_OR_MODE_DRIFT")
        paths=[]
        for n in (1,2):
            name=item.get(f"pass_{n}_name")
            require(type(name) is str
                    and name==f"{expected_token}-pass{n}.sql.gz",
                    "PAUSED_SQL_PRIVATE_OWNER_FILENAME_CHANGED")
            local=destination/name
            sha,size=_digest_file(local)
            require(sha==item.get(f"pass_{n}_sha256")
                    and size==item.get(f"pass_{n}_bytes"),
                    "PAUSED_SQL_PRIVATE_SQL_CONTENT_CHANGED")
            paths.append(local)
        require(paths[0]!=paths[1],
                "PAUSED_SQL_PRIVATE_PASSES_COLLIDE")
        try:
            observed_mode=pull.compare_database_dumps(paths[0],paths[1])
        except Exception:
            raise PausedDatabaseBlocked(
                "PAUSED_SQL_SECONDARY_SQL_CONTENT_COMPARE_FAILED"
            ) from None
        require(observed_mode==expected_mode,
                "PAUSED_SQL_SECONDARY_SQL_MODE_CHANGED")
    return {
        "status":"THREE_ORIGINAL_PRIVATE_DB_TWO_PASS_READBACK_PASS_NOT_CUTOVER",
        "site_count":17,"database_count":3,
        "source_business_writers_all_fenced":False,
        "target_import_performed":False,
        "cutover_allowed":False,"writes_performed":False,
    }
