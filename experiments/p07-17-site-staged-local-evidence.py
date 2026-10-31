#!/usr/bin/env python3
"""P07: one-pass read-only local evidence audit for the 14 PULLED_STAGED sites.

No SSH, SQL, curl, rsync, CloudPanel changes, migrations, DNS, or source access.
PULLED_STAGED only means partial PREPARE progress: never a Cutover PASS.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys

ROOT=Path("/var/lib/vf-server-ops/server-migrations")
JOBS=(
    ("ORIGINAL17","pull-20261028T103425Z-98050c76",17),
    ("LEGACY9","pull-20261031T094144Z-d045fa5a",9),
    ("LAST2","pull-20261031T095604Z-edae3c44",2),
)
EXPECTED_STAGED={
    "123.kewaro.com","123.m3u8.one","assetbox.kewaro.com",
    "doc.kewaro.com","domain.kewaro.com","example.cloudpanel.io",
    "forge.kewaro.com","infra.kewaro.com","lib.kewaro.com",
    "press.kewaro.com","seo.kewaro.com","start.kewaro.com",
    "textbox.kewaro.com","updates.kewaro.com",
}
EXPECTED_PENDING={"ilovem3u8.kewaro.com","unzip.kewaro.com","www3.m3u8.one"}
DOMAIN=re.compile(r"[a-z0-9][a-z0-9.-]{1,150}[a-z0-9]$")
SCHEMA="vf-server-ops.server-migration.target-pull.v1"

class Block(Exception):
    pass

def require(ok, reason):
    if not ok:raise Block(reason)

def secure_state(path):
    require(not path.is_symlink(),"STATE_SYMLINK")
    try:st=path.stat()
    except OSError:raise Block("MIGRATION_STATE_MISSING") from None
    require(stat.S_ISREG(st.st_mode) and st.st_uid==0
            and not st.st_mode & 0o022 and st.st_size<8*1024*1024,
            "MIGRATION_STATE_UNSAFE")
    try:result=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError):
        raise Block("MIGRATION_STATE_UNREADABLE") from None
    require(type(result) is dict,"MIGRATION_STATE_FORMAT_INVALID")
    return result

def safe_site_path(value):
    if type(value) is not str or not value.startswith("/home/") or len(value)>512:
        return False
    path=Path(value)
    try:
        resolved=path.resolve(strict=True)
        return (resolved.is_dir() and
                (resolved==Path("/home") or Path("/home") in resolved.parents))
    except (OSError,RuntimeError):
        return False

def check_site(site, panel_row):
    root=safe_site_path(site.get("site_root"))
    doc=safe_site_path(site.get("document_root") or site.get("site_root"))
    user=site.get("site_user")
    try:
        user_exists=type(user) is str and bool(pwd.getpwnam(user))
    except KeyError:
        user_exists=False
    dbs=site.get("mysql_databases")
    if type(dbs) is not list or any(type(x) is not str or not x for x in dbs):
        return ("INVALID","INVALID","INVALID","INVALID","INVALID")
    verification=site.get("mysql_verification")
    if type(verification) is not list:verification=[]
    valid_dbs=set()
    for row in verification:
        if type(row) is dict and row.get("phase")=="prepare" and row.get("status")=="PASS" and type(row.get("database")) is str:
            valid_dbs.add(row["database"])
    recorded=(len(dbs)==0 or (
        len(dbs)==site.get("mysql_prepare_count")
        and set(dbs)<=valid_dbs))
    # Checking panel metadata is *not* equivalent to opening or verifying DB data.
    panel_ok=(type(panel_row) is dict and
              panel_row.get("domain")==site.get("domain") and
              panel_row.get("site_user")==user and
              type(panel_row.get("mysql_databases")) is list and
              set(dbs)<=set(panel_row["mysql_databases"]))
    return (
        "PASS" if root else "MISSING",
        "PASS" if doc else "MISSING",
        "PASS" if user_exists else "MISSING",
        "PASS" if recorded else "MISSING",
        "PASS" if panel_ok else "MISSING",
    )

def audit(root=ROOT,inventory_fn=None):
    require(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    states=[]
    seen={}
    for label,mid,expected_count in JOBS:
        state=secure_state(root/mid/"state.json")
        require(state.get("schema")==SCHEMA and state.get("migration_id")==mid,
                "MIGRATION_ID_OR_SCHEMA_CHANGED")
        require(state.get("status")=="PREPARE_FAILED","MIGRATION_STATUS_CHANGED")
        require(type(state.get("sites")) is list and len(state["sites"])==expected_count,
                "SITE_COUNT_SCOPE_CHANGED")
        for flag in ("source_runtime_frozen","target_runtime_activated",
                     "dns_changed_by_p07","source_delete_allowed",
                     "existing_target_overwrite_allowed"):
            require(state.get(flag) is False,"MIGRATION_GUARD_CHANGED")
        for site in state["sites"]:
            require(type(site) is dict,"SITE_RECORD_INVALID")
            name=site.get("domain")
            require(type(name) is str and DOMAIN.fullmatch(name),
                    "SITE_DOMAIN_INVALID")
            status=site.get("stage_status")
            require(status in ("PULLED_STAGED","PENDING"),
                    "SITE_STAGE_STATUS_CHANGED")
            # Overlaps must carry the same original site identity and be
            # consistent with the final observed status order.
            seen.setdefault(name,[]).append((label,status,site))
        states.append(state)
    require(states[1].get("partial_parent_migration_id")==JOBS[0][1]
            and states[2].get("partial_parent_migration_id")==JOBS[1][1],
            "MIGRATION_PARENT_CHAIN_CHANGED")
    statuses={k:rows[-1][1] for k,rows in seen.items()}
    require(set(statuses)==EXPECTED_STAGED|EXPECTED_PENDING and
            {k for k,v in statuses.items() if v=="PULLED_STAGED"}==EXPECTED_STAGED and
            {k for k,v in statuses.items() if v=="PENDING"}==EXPECTED_PENDING,
            "STAGED_PENDING_SCOPE_CHANGED")
    require(all(states[i].get("target_server_identity")==states[0].get("target_server_identity")
                for i in (1,2)), "TARGET_IDENTITY_CHANGED")
    # Read-only CloudPanel inventory from installed runtime, not the old VPS.
    if inventory_fn is None:
        sys.path.insert(0,"/opt/vf-server-ops/lib")
        import inventory
        inventory_fn=inventory.build_manifest
    manifest=inventory_fn(Path("/"))
    require(type(manifest) is dict and type(manifest.get("sites")) is list,
            "CLOUDPANEL_INVENTORY_UNAVAILABLE")
    by_domain={}
    for row in manifest["sites"]:
        if type(row) is dict and type(row.get("domain")) is str:
            by_domain.setdefault(row["domain"],[]).append(row)
    print("SCOPE=17_SITES_3_FAILED_MIGRATIONS")
    print("STAGED_SITES=14")
    print("PENDING_SITES=3")
    print("WWW3_ISOLATED_DATABASE=OUTSIDE_THIS_STATE_AUDIT")
    failures=0
    staged_dbs=0
    for name in sorted(EXPECTED_STAGED):
        label,_,site=seen[name][-1]
        panel=by_domain.get(name,[])
        outcome=check_site(site,panel[0] if len(panel)==1 else None)
        staged_dbs+=len(site.get("mysql_databases",[])) if type(site.get("mysql_databases")) is list else 0
        if any(x!="PASS" for x in outcome):failures+=1
        print("SITE="+name+" JOB="+label+
              " ROOT="+outcome[0]+" DOCROOT="+outcome[1]+
              " USER="+outcome[2]+" DB_PREPARE_EVIDENCE="+outcome[3]+
              " PANEL_INVENTORY="+outcome[4])
    for name in sorted(EXPECTED_PENDING):
        print("PENDING_SITE="+name+" STATE=PENDING_NO_AUTOMATIC_RETRY")
    print("STAGED_DATABASE_COUNT_IN_MIGRATION_STATE="+str(staged_dbs))
    print("STAGED_SITE_LOCAL_EVIDENCE="+("PASS" if failures==0 else "GAPS_FOUND"))
    print("STAGED_SITE_GAP_COUNT="+str(failures))
    print("EXTERNAL_ASSETS_SQLITE_CRON_PHP_SMOKE=NOT_YET_VERIFIED")
    print("SOURCE_TARGET_CONTENT_PARITY=NOT_VERIFIED")
    print("OLD_SERVER_CONTACTED=NO")
    print("DNS_WRITES=NONE")
    print("DATABASE_WRITES=NONE")
    print("CUTOVER_ALLOWED=NO")
    return 0

if __name__=="__main__":
    try:raise SystemExit(audit())
    except Block as e:
        print("BLOCKED="+str(e));raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=LOCAL_EVIDENCE_UNVERIFIED");raise SystemExit(13) from None
