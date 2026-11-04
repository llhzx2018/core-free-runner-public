#!/usr/bin/env python3
"""P07: all three PENDING CloudPanel site roots, runtime and candidate DB links.

Read-only CP2 metadata, no HTTP handlers, source SSH, SQL queries or writes.
This is not file-content parity or Production/Cutover acceptance. The existing
14 staged site evidence and DB recovery archives are not rechecked here.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
SMOKE=HERE/"p07-14-site-local-http-fpm-smoke.py"
SMOKE_BLOB="c4d390396819313ce28e923d8740f33291d194e4"
BASE=HERE/"p07-17-site-staged-local-evidence.py"
BASE_BLOB="01b02934109458942e575d4e5a45d2d7f7ea37cf"
ROOT=Path("/var/lib/vf-server-ops/server-migrations")
# Structural CloudPanel database counts, never app-config or SQL parity.
THREE=(
 ("ilovem3u8.kewaro.com","ORIGINAL17"),
 ("unzip.kewaro.com","LEGACY9"),
 ("www3.m3u8.one","LAST2"),
)
class Block(Exception):pass
def need(ok,code):
    if not ok:raise Block(code)
def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def pinned(path,sha,name):
    need(path.is_file() and not path.is_symlink() and blob(path.read_bytes())==sha,
         "PINNED_"+name+"_BUNDLE_CHANGED")
    spec=importlib.util.spec_from_file_location("p07_pending_"+name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def status_scope(base):
    states=[]
    seen={}
    for name,mid,count in base.JOBS:
        s=base.secure_state(ROOT/mid/"state.json")
        need(s.get("migration_id")==mid and s.get("schema")==base.SCHEMA
             and s.get("status")=="PREPARE_FAILED"
             and type(s.get("sites")) is list and len(s["sites"])==count
             and all(s.get(k) is False for k in (
                 "source_runtime_frozen","target_runtime_activated",
                 "dns_changed_by_p07","source_delete_allowed",
                 "existing_target_overwrite_allowed")),
             "MIGRATION_ID_OR_SAFETY_BOUNDARY_CHANGED")
        if name!="ORIGINAL17":
            need(s.get("cutover_prohibited") is True,
                 "CHILD_CUTOVER_PROTECTION_CHANGED")
        else:
            need(s.get("cutover_prohibited",False) is False,
                 "ORIGINAL_CUTOVER_GUARD_CHANGED")
        for site in s["sites"]:
            need(type(site) is dict and type(site.get("domain")) is str,
                 "MIGRATION_SITE_INVALID")
            seen[site["domain"]]=(name,site)
        states.append(s)
    need(states[1].get("partial_parent_migration_id")==base.JOBS[0][1]
         and states[2].get("partial_parent_migration_id")==base.JOBS[0][1],
         "PARENT_MIGRATION_CHAIN_CHANGED")
    need(all(s.get("target_server_identity")==states[0].get("target_server_identity")
             for s in states[1:]),"CP2_MIGRATION_TARGET_IDENTITY_CHANGED")
    need(set(seen)==base.EXPECTED_STAGED|base.EXPECTED_PENDING
         and {n for n,(label,s) in seen.items() if s.get("stage_status")=="PENDING"}
              ==base.EXPECTED_PENDING
         and {n for n,(label,s) in seen.items() if s.get("stage_status")=="PULLED_STAGED"}
              ==base.EXPECTED_STAGED,
         "17_SITE_FINAL_SCOPE_CHANGED")
    return seen
def panel_db_candidate(site, cp_dbs):
    """CloudPanel site DB inventory, independent of isolated recovery scratch.

    Name equality does NOT prove application config, credentials, data,
    cross-engine schema parity or cutover readiness.
    """
    if type(cp_dbs) is not list or any(type(x) is not str or not x
                                       or len(x)>128 for x in cp_dbs):
        return "CP2_SITE_DB_INVENTORY_INVALID"
    if len(set(cp_dbs))!=len(cp_dbs):
        return "CP2_SITE_DB_DUPLICATE"
    declared=site.get("mysql_databases")
    if type(declared) is not list or any(type(x) is not str or not x
                                         or len(x)>128 for x in declared):
        return "SOURCE_SITE_DB_DECLARATION_INVALID"
    if not declared:
        return "SOURCE_SITE_DB_DECLARATION_EMPTY"
    if len(set(declared))!=len(declared):
        return "SOURCE_SITE_DB_DECLARATION_DUPLICATE"
    if set(declared)==set(cp_dbs):
        return "SOURCE_DECLARED_DB_REGISTERED_IN_CP2"
    if not cp_dbs:
        return "SOURCE_DECLARED_DB_NOT_REGISTERED_IN_CP2"
    if set(declared).issubset(set(cp_dbs)):
        return "ADDITIONAL_CP2_REGISTERED_DB_REVIEW_REQUIRED"
    return "SOURCE_CP2_SITE_DB_IDENTITY_DIFFERENCE"


def assess(smoke,site,target):
    src=site.get("runtime")
    runtime=target.get("runtime")
    match=(type(src) is dict and type(runtime) is dict
           and src.get("type")==runtime.get("type")
           and src.get("version")==runtime.get("version"))
    entry=smoke.safe_entry_metadata(target)
    present=bool(entry.get("index.php") or entry.get("index.html"))
    vhost,endpoints=smoke.vhost(site["domain"])
    kind=runtime.get("type") if type(runtime) is dict else None
    version=runtime.get("version") if type(runtime) is dict else None
    if kind=="php" and type(version) is str and smoke.PHP.fullmatch(version):
        fpm=smoke.service("php"+version+"-fpm")
        backend=smoke.backend_status(endpoints,version,target["site_user"])
    else:
        fpm="NOT_APPLICABLE" if kind!="php" else "UNKNOWN"
        backend="NOT_APPLICABLE" if kind!="php" else "UNKNOWN"
    php_ok=(fpm=="ACTIVE" and backend in (
        "TCP_POOL_AND_LISTENER_CONFIRMED","UNIX_POOL_AND_SOCKET_CONFIRMED"))
    evidence_ok=bool(match and present and vhost=="FOUND" and
                     (php_ok if kind=="php" else True))
    return {"SITE_FILES_ENTRY_PRESENT":"YES" if present else "NO",
            "PHP_OR_OTHER_RUNTIME_MATCH":"YES" if match else "NO",
            "NGINX_VHOST":vhost,
            "FPM_SERVICE":fpm,
            "FPM_BACKEND":backend,
            "SITE_FILES_FULL_PARITY":"NOT_VERIFIED",
            "APPLICATION_DB_CONFIG_MAPPING":"NOT_VERIFIED",
            "HTTP_APP_FUNCTIONALITY":"NOT_TESTED",
            "LOCAL_FILES_VHOST_FPM_EVIDENCE":("MATCH" if evidence_ok else "GAP")}
def scan(base,smoke):
    items=status_scope(base)
    inventory=smoke.inventory()
    entries=[]
    for domain,label in THREE:
        found=items.get(domain)
        need(found is not None and found[0]==label and
             found[1].get("stage_status")=="PENDING",
             "PENDING_SITE_IDENTITY_CHANGED")
        site=found[1]
        rows=inventory.get(domain,[])
        need(len(rows)==1 and rows[0].get("site_user")==site.get("site_user"),
             "CP2_SITE_USER_OR_INVENTORY_CHANGED")
        target=rows[0]
        panel_dbs=target.get("mysql_databases")
        bound=panel_db_candidate(site,panel_dbs)
        result=assess(smoke,site,target)
        source_dbs=site.get("mysql_databases")
        result["SOURCE_DB_DECLARED_COUNT"]=(len(source_dbs)
            if type(source_dbs) is list else "UNKNOWN")
        result["CP2_SITE_DB_REGISTERED_COUNT"]=(len(panel_dbs)
            if type(panel_dbs) is list else "UNKNOWN")
        entries.append((domain,bound,result))
    return entries

def private_bytes(path,owner,max_size=2*1024*1024):
    """Read only root-owned local recovery evidence, never log its raw bytes."""
    try:
        info=path.lstat()
        need(stat.S_ISREG(info.st_mode) and not path.is_symlink()
             and info.st_uid==owner and info.st_nlink==1
             and not info.st_mode&0o077 and 0<info.st_size<=max_size,
             "WWW3_PRIVATE_FILE_UNSAFE")
        data=path.read_bytes()
    except OSError:
        raise Block("WWW3_PRIVATE_FILE_UNAVAILABLE") from None
    need(len(data)==info.st_size,"WWW3_PRIVATE_FILE_READ_CHANGED")
    return data

def private_json(path,owner):
    try:
        raw=private_bytes(path,owner,65536)
        value=json.loads(raw)
    except (ValueError,UnicodeError):
        raise Block("WWW3_PRIVATE_JSON_UNVERIFIED") from None
    need(type(value) is dict,"WWW3_PRIVATE_JSON_INVALID")
    return value

def candidate_relation(source,panel,transactions,site_config,identity,owner):
    """Read-only link between real source DB, existing scratch receipts & config.

    The recovery scratch is not automatically a CloudPanel *site* database.
    Never expose DB names, passwords, config content or raw journal.
    """
    need(type(source) is dict and type(panel) is dict
         and type(identity) is str and bool(identity),"WWW3_SITE_CONTEXT_UNVERIFIED")
    dbs=source.get("mysql_databases")
    registered=panel.get("mysql_databases")
    need(type(dbs) is list and len(dbs)==1 and type(dbs[0]) is str
         and bool(dbs[0]) and type(registered) is list
         and len(registered)==len(set(registered))
         and all(type(x) is str and bool(x) for x in registered),
         "WWW3_SITE_DATABASE_INVENTORY_UNVERIFIED")
    name=dbs[0]
    need(transactions.is_dir() and not transactions.is_symlink(),
         "WWW3_TRANSACTIONS_NOT_FOUND")
    info=transactions.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid==owner
         and not info.st_mode&0o077,"WWW3_TRANSACTIONS_NOT_PRIVATE")
    folder=transactions/"www3-source-rule-connection-v1"
    need(folder.is_dir() and not folder.is_symlink(),
         "WWW3_CONNECTION_JOURNAL_NOT_FOUND")
    info=folder.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid==owner
         and not info.st_mode&0o077,"WWW3_JOURNAL_FOLDER_UNSAFE")
    journal=private_json(folder/"journal.json",owner)
    need(journal.get("schema")=="p07.www3.config-connection.v1"
         and journal.get("target_identity")==identity
         and journal.get("config_path")==str(site_config)
         and journal.get("status") in {
            "CONNECTED_NOT_CUTOVER_READY","ROLLED_BACK","ROLLBACK_REQUIRED",
            "INTENT_RESERVED"}
         and journal.get("cutover_allowed") is False
         and journal.get("database_writes") is False
         and journal.get("migration_state_promoted") is False,
         "WWW3_CONNECTION_JOURNAL_IDENTITY_OR_GUARD")
    original=private_bytes(folder/"original.php",owner)
    candidate=private_bytes(folder/"candidate.php",owner)
    need(hashlib.sha256(original).hexdigest()==journal.get("original_sha256")
         and hashlib.sha256(candidate).hexdigest()==journal.get("candidate_sha256"),
         "WWW3_CONNECTION_BACKUP_HASH_CHANGED")
    try:
        local=site_config.lstat()
        need(stat.S_ISREG(local.st_mode) and not site_config.is_symlink()
             and local.st_size<=2*1024*1024 and not local.st_mode&0o002,
             "WWW3_CURRENT_CONFIG_UNSAFE")
        present=site_config.read_bytes()
    except OSError:
        raise Block("WWW3_CURRENT_CONFIG_UNAVAILABLE") from None
    if present==candidate:cfg="CANDIDATE_MATCH"
    elif present==original:cfg="ORIGINAL_MATCH"
    else:cfg="DIFFERENT_REVIEW_REQUIRED"
    need(cfg!="DIFFERENT_REVIEW_REQUIRED",
         "WWW3_CONFIG_BYTES_OUTSIDE_RECOVERY_JOURNAL")
    receipts=sorted(transactions.glob("www3-hex-scratch-*.json"))
    need(len(receipts)<=32,"WWW3_RECEIPT_SCOPE_UNSAFE")
    candidate_rows=[]
    quarantine_rows=[]
    for path in receipts:
        row=private_json(path,owner)
        if (row.get("migration_id")!=source["migration_id"]
            or row.get("domain")!="www3.m3u8.one"
            or row.get("source_database")!=name
            or row.get("target_server_identity")!=identity):
            continue
        if row.get("schema")=="p07.www3.source-rule-candidate.v1":
            need(row.get("status")=="VERIFIED_STATIC_COPY_NOT_ACTIVATED"
                 and row.get("cutover_allowed") is False
                 and row.get("website_activated") is False
                 and row.get("original_database_modified") is False,
                 "WWW3_CANDIDATE_RECEIPT_GUARD_CHANGED")
            candidate_rows.append(row)
        elif row.get("schema")=="p07.www3.quarantined-static-copy.v1":
            quarantine_rows.append(row)
    need(len(candidate_rows)==1,"WWW3_UNIQUE_CANDIDATE_RECEIPT_UNPROVEN")
    fresh=candidate_rows[0].get("scratch_database")
    need(type(fresh) is str and bool(fresh) and fresh!=name,
         "WWW3_CANDIDATE_DATABASE_IDENTITY_INVALID")
    old_scratch={
        x.get("scratch_database") for x in quarantine_rows
        if type(x.get("scratch_database")) is str
    }
    covered={name,fresh}|old_scratch
    return {
       "SOURCE_DB_IN_CP2_PANEL":"YES" if name in registered else "NO",
       "CP2_SITE_DB_REGISTERED_COUNT":len(registered),
       "SOURCE_DECLARED_DB_COUNT":len(dbs),
       "VERIFIED_CANDIDATE_RECEIPTS":len(candidate_rows),
       "CANDIDATE_DB_IN_CP2_SITE_PANEL":"YES" if fresh in registered else "NO",
       "OLD_SCRATCH_IN_CP2_SITE_PANEL":(
           "YES" if old_scratch & set(registered) else
           "NO" if old_scratch else "NO_RECEIPT"),
       "UNCLASSIFIED_CP2_SITE_DB_COUNT":len(set(registered)-covered),
       "JOURNAL_STATUS":journal["status"],
       "ORIGINAL_CANDIDATE_BACKUP_HASH":"PASS",
       "CURRENT_CONFIG_READBACK":cfg,
       "APPLICATION_DB_LIVE_CONNECTION":"NOT_TESTED",
       "SOURCE_TARGET_DB_PARITY":"NOT_VERIFIED",
       "CUTOVER_ALLOWED":"NO",
    }

def www3_context():
    """One safe, current CP2-only inventory scope for all www3 subcommands."""
    need(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    base=pinned(BASE,BASE_BLOB,"BASE")
    sites=status_scope(base)
    label,site=sites["www3.m3u8.one"]
    need(label=="LAST2" and site.get("stage_status")=="PENDING",
         "WWW3_SITE_OWNER_CHANGED")
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import inventory
    matches=[x for x in inventory.build_manifest(Path("/")).get("sites",[])
             if type(x) is dict and x.get("domain")=="www3.m3u8.one"]
    need(len(matches)==1 and site.get("site_user")==matches[0].get("site_user"),
         "WWW3_CP2_SITE_INVENTORY_UNVERIFIED")
    user=site.get("site_user")
    need(type(user) is str and re.fullmatch(r"[a-z_][a-z0-9_-]{0,64}",user),
         "WWW3_SITE_USER_UNSAFE")
    root=Path("/home")/user/"htdocs"/"www3.m3u8.one"
    need(site.get("site_root")==str(root)
         and matches[0].get("site_root")==str(root),
         "WWW3_SITE_ROOT_CHANGED")
    tail=ROOT/base.JOBS[2][1]
    state=base.secure_state(tail/"state.json")
    identity=state.get("target_server_identity")
    choices=[p for p in (root/"wp-config.php",root/"public/wp-config.php")
             if os.path.lexists(p)]
    need(len(choices)==1,"WWW3_CONFIG_LOCATION_UNVERIFIED")
    row=dict(site,migration_id=base.JOBS[2][1])
    return row,matches[0],tail/"target-transactions",choices[0],identity

def classify_www3():
    row,panel,transactions,config,identity=www3_context()
    result=candidate_relation(row,panel,transactions,config,identity,0)
    print("PROBE=P07_WWW3_SITE_DB_AND_RECOVERY_RELATION_READ_ONLY",flush=True)
    print("SITE=www3.m3u8.one",flush=True)
    for key,value in result.items():
        print(key+"="+str(value),flush=True)
    print("SITE_FILES_DB_CRON_DNS_WRITES=NONE",flush=True)
    print("SOURCE_SERVER_CONTACTED=NO",flush=True)
    print("DB_SQL_REQUESTS=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0

def www3_candidate_credentials(source,transactions,identity):
    """Return credentials in memory only; never print or persist values."""
    need(type(source.get("mysql_databases")) is list
         and len(source["mysql_databases"])==1,"WWW3_ORIGINAL_DB_SCOPE_CHANGED")
    source_db=source["mysql_databases"][0]
    records=[]
    for path in sorted(transactions.glob("www3-hex-scratch-*.json")):
        row=private_json(path,0)
        if row.get("schema")!="p07.www3.source-rule-candidate.v1":
            continue
        if (row.get("migration_id")!=source["migration_id"]
            or row.get("domain")!="www3.m3u8.one"
            or row.get("target_server_identity")!=identity
            or row.get("source_database")!=source_db):
            continue
        records.append(row)
    need(len(records)==1,"WWW3_CANDIDATE_CREDENTIAL_RECEIPT_NOT_UNIQUE")
    rec=records[0]
    need(rec.get("status")=="VERIFIED_STATIC_COPY_NOT_ACTIVATED"
         and rec.get("cutover_allowed") is False
         and rec.get("website_activated") is False
         and rec.get("original_database_modified") is False
         and rec.get("source_runtime_frozen") is False
         and rec.get("verified_rows")==198750
         and rec.get("dynamic_groups_omitted")==3
         and rec.get("table_collations_explicit")==25
         and rec.get("ascii_hex_defaults_equal")==10
         and rec.get("memory_table_count")==1,
         "WWW3_CANDIDATE_EVIDENCE_OR_GUARD_CHANGED")
    db,user,password=(rec.get("scratch_database"),
                      rec.get("username"),rec.get("password"))
    need(type(db) is str and re.fullmatch(r"[a-zA-Z0-9_-]{1,64}",db)
         and type(user) is str and re.fullmatch(r"[a-zA-Z0-9_]{1,64}",user)
         and type(password) is str and 16<=len(password)<=1024
         and "\x00" not in password,"WWW3_CANDIDATE_CREDENTIAL_IDENTITY_UNSAFE")
    return db,user,password

def readonly_candidate_probe(client,db,user,password):
    """Fixed SELECT only, with password in child environment and no app/HTTP."""
    need(type(client) is str and Path(client).is_absolute()
         and Path(client).name in ("mariadb","mysql")
         and type(db) is str and re.fullmatch(r"[a-zA-Z0-9_-]{1,64}",db)
         and type(user) is str and re.fullmatch(r"[a-zA-Z0-9_]{1,64}",user)
         and type(password) is str and len(password)>=16,
         "WWW3_READONLY_CLIENT_ARGUMENT_UNSAFE")
    sql=("SELECT DATABASE(), (SELECT COUNT(*) FROM information_schema.TABLES "
         "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE')")
    argv=[client,"--no-defaults","--protocol=TCP","--host=127.0.0.1",
          "--port=3306","--connect-timeout=5","--default-character-set=utf8mb4",
          "--user="+user,"--database="+db,"--batch","--skip-column-names",
          "--execute="+sql]
    env={"PATH":"/usr/bin:/bin","HOME":"/nonexistent","LC_ALL":"C",
         "MYSQL_PWD":password}
    try:
        proc=subprocess.run(argv,env=env,stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                            timeout=30,check=False)
    except (OSError,subprocess.SubprocessError):
        raise Block("WWW3_READONLY_SQL_CLIENT_FAILED") from None
    need(proc.returncode==0 and 0<len(proc.stdout)<=128
         and proc.stdout.count(b"\n")==1,"WWW3_READONLY_SQL_CONNECTION_FAILED")
    expected=(db+"\t157\n").encode("ascii")
    need(proc.stdout==expected,"WWW3_CANDIDATE_DATABASE_OR_TABLE_SCOPE_CHANGED")
    return "PASS"

def verify_www3_candidate_live_readonly():
    source,panel,transactions,config,identity=www3_context()
    relation=candidate_relation(source,panel,transactions,config,identity,0)
    need(relation["JOURNAL_STATUS"]=="CONNECTED_NOT_CUTOVER_READY"
         and relation["CURRENT_CONFIG_READBACK"]=="CANDIDATE_MATCH"
         and relation["CANDIDATE_DB_IN_CP2_SITE_PANEL"]=="YES"
         and relation["SOURCE_DB_IN_CP2_PANEL"]=="NO"
         and relation["UNCLASSIFIED_CP2_SITE_DB_COUNT"]==0,
         "WWW3_CANDIDATE_JOURNAL_AND_PANEL_NOT_READY")
    db,user,password=www3_candidate_credentials(source,transactions,identity)
    need(db in panel["mysql_databases"] and
         db not in source["mysql_databases"],"WWW3_CANDIDATE_IDENTITY_CHANGED")
    client=shutil.which("mariadb") or shutil.which("mysql")
    need(client is not None,"WWW3_SQL_CLIENT_NOT_FOUND")
    outcome=readonly_candidate_probe(client,db,user,password)
    print("PROBE=P07_WWW3_CANDIDATE_DB_CURRENT_LIVE_READONLY",flush=True)
    print("SITE=www3.m3u8.one",flush=True)
    print("CURRENT_CONFIG_READBACK=CANDIDATE_MATCH",flush=True)
    print("JOURNAL_STATUS=CONNECTED_NOT_CUTOVER_READY",flush=True)
    print("CANDIDATE_DB_IN_CP2_SITE_PANEL=YES",flush=True)
    print("CANDIDATE_DB_USER_CONNECTION="+outcome,flush=True)
    print("CANDIDATE_DB_BASE_TABLE_COUNT=157",flush=True)
    print("SOURCE_TARGET_DB_PARITY=NOT_VERIFIED",flush=True)
    print("APPLICATION_HTTP_FUNCTIONALITY=NOT_TESTED",flush=True)
    print("SOURCE_SERVER_CONTACTED=NO",flush=True)
    print("SITE_FILES_OR_MIGRATION_STATE_WRITES=NONE",flush=True)
    print("DB_SQL_WRITE_REQUESTS=NONE",flush=True)
    print("CRON_AND_DNS_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0

def main():
    if sys.argv[1:]==["--verify-www3-candidate-live-read-only"]:
        return verify_www3_candidate_live_readonly()
    if sys.argv[1:]==["--classify-www3-site-db-and-recovery-read-only"]:
        return classify_www3()
    need(os.geteuid()==0 and sys.argv[1:]==["--check-pending-three-runtime-bindings-read-only"],
         "EXPLICIT_PENDING_THREE_READONLY_ARG_REQUIRED")
    base=pinned(BASE,BASE_BLOB,"BASE")
    smoke=pinned(SMOKE,SMOKE_BLOB,"SMOKE")
    rows=scan(base,smoke)
    print("PROBE=P07_PENDING_THREE_WEB_RUNTIME_AND_DB_CANDIDATE",flush=True)
    print("STAGED_OTHER_SITES=14_PREVIOUS_EVIDENCE_NOT_RESCANNED",flush=True)
    print("PENDING_SITE_COUNT="+str(len(rows)),flush=True)
    gaps=0
    db_gaps=0
    for domain,db,result in rows:
        print("SITE="+domain+" DATABASE_CANDIDATE="+db+" "+
              " ".join(k+"="+str(v) for k,v in result.items()),flush=True)
        gaps+=int(result["LOCAL_FILES_VHOST_FPM_EVIDENCE"]!="MATCH")
        db_gaps+=int(db!="SOURCE_DECLARED_DB_REGISTERED_IN_CP2")
    print("WEB_RUNTIME_GAP_COUNT="+str(gaps),flush=True)
    print("PANEL_DATABASE_REGISTRATION_GAP_COUNT="+str(db_gaps),flush=True)
    print("ISOLATED_SCRATCH_DB_CLOUDPANEL_SITE_REGISTRATION=NOT_REQUIRED",flush=True)
    print("ISOLATED_SCRATCH_RECOVERY_PROOF=NOT_REEVALUATED",flush=True)
    print("APPLICATION_DB_BINDING_PROOF=NOT_VERIFIED",flush=True)
    print("CLOUDPANEL_SITE_DB_CONFIGURATION=NOT_MODIFIED",flush=True)
    print("SOURCE_VPS_CONTACTED=NO",flush=True)
    print("HTTP_REQUESTS=NONE",flush=True)
    print("DATABASE_SQL_QUERIES_AND_WRITES=NONE",flush=True)
    print("DNS_OR_CRON_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0 if gaps==0 and db_gaps==0 else 13
if __name__=="__main__":
    try:raise SystemExit(main())
    except Block as e:
        print("BLOCKED="+str(e),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=UNVERIFIED_PENDING_THREE_RUNTIME",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
