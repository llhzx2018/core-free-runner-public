#!/usr/bin/env python3
"""P07 clean CP2 2026-11-01 incident: exact-site read-only DB value parity.

The current PREPARE_FAILED migration has conditional DDL. This is ONLY
non-mutating evidence about live source/target rows and column identity, not
permission to skip verification, retry import, resume, cutover or modify DNS.
"""
from __future__ import annotations
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
PINNED={
    "p07-two-pending-live-db-parity.py":"0b6ee5061909115de6f57b5d933244de3a7a79fa",
    "p07-two-pending-live-db-worker.py":"c63cd3513c773678a6162b50f8a93d35fe9160b6",
}
INCIDENT_MID="pull-20261101T045943Z-923729a1"
DOMAIN="ilovem3u8.kewaro.com"
EXPECTED_TABLES=42

class Block(Exception):pass
def need(ok,label):
    if not ok:raise Block(label)
def gitblob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def load_pair():
    for filename,expected in PINNED.items():
        file=HERE/filename
        try:
            need(file.is_file() and not file.is_symlink() and
                 gitblob(file.read_bytes())==expected,
                 "EXACT_READONLY_WORKER_BUNDLE_CHANGED")
        except OSError:raise Block("EXACT_READONLY_WORKER_UNAVAILABLE") from None
    spec=importlib.util.spec_from_file_location("p07_new_cp2_parity",
        HERE/"p07-two-pending-live-db-parity.py")
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    obj.ORIGINAL17=INCIDENT_MID
    obj.SITES=((DOMAIN,INCIDENT_MID,17,7,EXPECTED_TABLES),)
    return obj
def check_incident(pair):
    state=pair.private_state(pair.STATE_ROOT/INCIDENT_MID/"state.json")
    need(state.get("status")=="PREPARE_FAILED" and
         state.get("schema")=="vf-server-ops.server-migration.target-pull.v1" and
         state.get("migration_id")==INCIDENT_MID and
         state.get("last_sql_guard_failure",{}).get("reason")=="CONDITIONAL_DDL",
         "EXPECTED_CLEAN_CP2_GUARD_INCIDENT_MISSING")
    need(all(state.get(flag) is False for flag in (
         "source_runtime_frozen","target_runtime_activated",
         "dns_changed_by_p07","source_delete_allowed",
         "existing_target_overwrite_allowed")),
         "MIGRATION_SAFETY_BOUNDARY_CHANGED")
    need(state.get("cutover_prohibited",False) is False,
         "CUTOVER_BOUNDARY_CHANGED")
    sites=state.get("sites")
    need(type(sites) is list and len(sites)==17
         and sum(x.get("stage_status")=="PULLED_STAGED" for x in sites
                 if type(x) is dict)==7
         and sum(x.get("stage_status")=="PENDING" for x in sites
                 if type(x) is dict)==10
         and type(sites[7]) is dict
         and sites[7].get("domain")==DOMAIN
         and sites[7].get("stage_status")=="PENDING",
         "CLEAN_CP2_7_STAGED_10_PENDING_CHANGED")
    need(state.get("source_runtime_path")==
         "/var/lib/vf-server-ops/pull-source/"+INCIDENT_MID+"/runtime",
         "SOURCE_TEMPORARY_RUNTIME_IDENTITY_CHANGED")
def main():
    need(os.geteuid()==0 and
         sys.argv[1:]==["--classify-new-cp2-conditional-ddl-db-read-only"],
         "EXPLICIT_CLEAN_CP2_READONLY_ONLY")
    pair=load_pair()
    check_incident(pair)
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import inventory
    import server_migration_pull as engine
    local=Path("/opt/vf-server-ops/lib/server_migration_pull.py")
    need(local.is_file() and gitblob(local.read_bytes())==pair.ENGINE_BLOB,
         "RELEASE113_ENGINE_CHANGED")
    print("PROBE=CLEAN_CP2_SQL_CONDITIONAL_DDL_READONLY_INCIDENT",flush=True)
    print("NEW_CP2_SITES_STAGED=7",flush=True)
    print("INCIDENT_SITE_ORDINAL=8_OF_17",flush=True)
    print("SOURCE_AND_TARGET_TRANSACTIONS_SIMULTANEOUS=NO",flush=True)
    state=pair.compare_one(
        engine,inventory,DOMAIN,INCIDENT_MID,17,7,EXPECTED_TABLES)
    print("DATABASE_CONTENT_COMPARISON="+
          ("MATCH_ADVISORY_NOT_SCHEMA_VERIFICATION" if state=="MATCH"
           else "DIFFER_ADVISORY_DO_NOT_MUTATE" if state=="DIFFER"
           else "NOT_READY"),flush=True)
    print("SQL_CONDITIONAL_DDL_SEMANTICS_VERIFIED=NO",flush=True)
    print("ORIGINAL_FAILED_STATE_UNCHANGED=YES",flush=True)
    print("SOURCE_BUSINESS_DB_WRITES=NONE",flush=True)
    print("TARGET_DB_WRITES=NONE",flush=True)
    print("SITE_CONFIG_AND_DNS_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0
if __name__=="__main__":
    try:raise SystemExit(main())
    except (Block,Exception) as exc:
        # Never relay raw DB / SSH or SQL exceptions into operator output.
        error=str(exc) if type(exc) is Block else "UNVERIFIED_READONLY_INCIDENT"
        print("BLOCKED="+error,flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
