#!/usr/bin/env python3
"""P07: verify exact candidate SQL schema-presence parser against live www3 export.

Owner-run CP2 diagnostic for the EXISTING partly staged 2026-11-02 tail.
Read-only business SQL; one temporary old-VPS export and private CP2 copy.
Never creates or imports target DBs, changes existing site, state, source business
data, freeze, activation or DNS. A parser PASS is NOT import/cutover approval.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile

PARENT="pull-20261101T045943Z-923729a1"
CHILD="pull-20261101T052411Z-35663c25"
TAIL="pull-20261102T005644Z-7178c7d5"
DOMAIN="www3.m3u8.one"
BASE=Path("/var/lib/vf-server-ops/server-migrations")
RUNTIME=Path("/opt/vf-server-ops")
ENGINE_BLOB="71fb59ad7d005b88e39cbeed4b3302c7f313bd06"
CANDIDATE_HEAD="06038930003114ad4223f1d03784c5338e371af3"
CANDIDATE_BLOB="29062b76d6b1fba65014e2a89b9566c3f93cdede"
# Private PR source cannot be fetched anonymously by CP2. This independent
# preflight adapter reuses the pinned PUBLIC release113 schema parser and only
# extends its READ-ONLY source line decoding; it does not claim exact candidate
# binary identity or grant permission to import/cut over.
RELEASE113_SQL_ADVISORY_BLOB="02a377c90279b924b9d589525c5edcb098bed263"
SCHEMA_LINE_LIMIT=128*1024*1024
_DML_LINE=re.compile(r"^(?:INSERT|REPLACE)\s+INTO\b",re.I)
SCHEMA="vf-server-ops.server-migration.target-pull.v1"
REMOTE=r'''
import inventory,cloudpanel,os,sys
from pathlib import Path
domain,db,out,mid=sys.argv[1:]
root=Path("/var/lib/vf-server-ops/pull-source")/mid/"data"
if not root.is_dir() or root.is_symlink():
    raise SystemExit(21)
p=Path(out)
if p.parent!=root or not p.name.startswith("www3-schema-") or p.suffix!=".gz":
    raise SystemExit(22)
rows=[x for x in inventory.build_manifest(Path("/")).get("sites",[])
      if isinstance(x,dict) and x.get("domain")==domain]
if len(rows)!=1 or rows[0].get("mysql_databases")!=[db]:
    raise SystemExit(23)
if os.path.lexists(p):
    raise SystemExit(24)
try:
    cloudpanel.export_database(db,p,clpctl="clpctl")
except (cloudpanel.CloudPanelError,ValueError):
    raise SystemExit(25)
if p.is_symlink() or not p.is_file() or p.stat().st_size<1024:
    raise SystemExit(26)
p.chmod(0o600)
print("SOURCE_EXPORT_CREATED=YES",flush=True)
'''

class Block(ValueError):
    pass

def need(ok,code):
    if not ok:
        raise Block(code)

def blob(data):
    return hashlib.sha1(
        b"blob "+str(len(data)).encode()+b"\0"+data
    ).hexdigest()

def private_state(mid):
    folder=BASE/mid
    path=folder/"state.json"
    need(not BASE.is_symlink() and not folder.is_symlink()
         and not path.is_symlink(),"MIGRATION_STATE_PATH_UNSAFE")
    try:
        meta=path.lstat()
        need(stat.S_ISREG(meta.st_mode) and meta.st_uid==0
             and not meta.st_mode&0o077 and 0<meta.st_size<8*1024*1024,
             "MIGRATION_STATE_PERMISSIONS_UNSAFE")
        row=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,ValueError):
        raise Block("MIGRATION_STATE_UNAVAILABLE") from None
    need(isinstance(row,dict) and row.get("migration_id")==mid
         and row.get("schema")==SCHEMA,"MIGRATION_STATE_IDENTITY_UNPROVEN")
    return row

def verify_state():
    parent,child,tail=(private_state(x) for x in (PARENT,CHILD,TAIL))
    need(parent.get("status")==child.get("status")==tail.get("status")
         =="PREPARE_FAILED","MIGRATION_STATUS_CHANGED")
    need(child.get("partial_parent_migration_id")==PARENT
         and tail.get("partial_parent_migration_id")==PARENT,
         "MIGRATION_LINEAGE_CHANGED")
    need(all(
        isinstance(row.get("last_sql_guard_failure"),dict)
        and row["last_sql_guard_failure"].get("reason")=="CONDITIONAL_DDL"
        for row in (parent,child)
    ),"UPSTREAM_SQL_GUARD_CHANGED")
    ps=parent.get("sites")
    cs=child.get("sites")
    need(isinstance(ps,list) and len(ps)==17
         and isinstance(cs,list) and len(cs)==9
         and all(isinstance(x,dict) for x in ps+cs)
         and all(x.get("stage_status")=="PULLED_STAGED" for x in ps[:7])
         and all(x.get("stage_status")=="PENDING" for x in ps[7:])
         and all(x.get("stage_status")=="PULLED_STAGED" for x in cs[:6])
         and all(x.get("stage_status")=="PENDING" for x in cs[6:]),
         "UPSTREAM_STAGED_BOUNDARY_CHANGED")
    need(tail.get("cutover_prohibited") is True
         and child.get("cutover_prohibited") is True,
         "CHILD_CUTOVER_BOUNDARY_CHANGED")
    for row in (parent,child,tail):
        need(all(row.get(k) is False for k in (
            "source_runtime_frozen","target_runtime_activated",
            "dns_changed_by_p07","source_delete_allowed",
            "existing_target_overwrite_allowed",
        )), "MIGRATION_SAFETY_CHANGED")
        need(row.get("source_server_identity")==parent.get("source_server_identity")
             and row.get("target_server_identity")==parent.get("target_server_identity")
             and row.get("source")==parent.get("source"),"MIGRATION_SERVER_DRIFT")
    sites=tail.get("sites")
    need(isinstance(sites,list) and len(sites)==2
         and all(isinstance(x,dict) for x in sites)
         and [x.get("domain") for x in sites]==
         ["updates.kewaro.com",DOMAIN]
         and [x.get("stage_status") for x in sites]==
         ["PULLED_STAGED","PENDING"],
         "TAIL_SITE_STAGE_CHANGED")
    dbs=sites[1].get("mysql_databases")
    need(isinstance(dbs,list) and len(dbs)==1
         and isinstance(dbs[0],str)
         and re.fullmatch(r"[A-Za-z0-9_-]{1,64}",dbs[0]),
         "WWW3_DATABASE_SCOPE_CHANGED")
    need(sites[1].get("mysql_prepare_count") in (None,0),
         "WWW3_DATABASE_ALREADY_PREPARED")
    runtime=f"/var/lib/vf-server-ops/pull-source/{TAIL}/runtime"
    need(tail.get("source_runtime_path")==runtime,
         "SOURCE_HELPER_PATH_DRIFT")
    transactions=BASE/TAIL/"target-transactions"
    need(not transactions.is_symlink(),"TRANSACTION_DIRECTORY_UNSAFE")
    site_hash=hashlib.sha256(DOMAIN.encode("ascii")).hexdigest()[:16]
    site_marker=transactions/f"site-{site_hash}.json"
    need(not site_marker.is_symlink() and site_marker.is_file(),
         "WWW3_SITE_MARKER_MISSING")
    m=site_marker.lstat()
    need(m.st_uid==0 and not m.st_mode&0o077 and
         stat.S_ISREG(m.st_mode) and m.st_size<65536,
         "WWW3_SITE_MARKER_UNSAFE")
    receipt=json.loads(site_marker.read_text(encoding="utf-8"))
    need(isinstance(receipt,dict)
         and receipt.get("domain")==DOMAIN
         and receipt.get("created_by_migration")==TAIL,
         "WWW3_SITE_NOT_OWNED_BY_TAIL")
    db_token=hashlib.sha256(f"{DOMAIN}:{dbs[0]}:1".encode()).hexdigest()[:16]
    need(not os.path.lexists(transactions/f"db-{db_token}.json"),
         "WWW3_DATABASE_MARKER_EXISTS_RECOVERY_REQUIRED")
    return tail,dbs[0]

def verify_current_runtime():
    build=subprocess.run(
        ["vfops","--build-id"],stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,
        timeout=15,check=False,
    )
    need(build.returncode==0 and build.stdout.strip()=="0.1.0-release113",
         "RELEASE113_REQUIRED")
    path=RUNTIME/"lib/server_migration_pull.py"
    need(path.is_file() and not path.is_symlink()
         and blob(path.read_bytes())==ENGINE_BLOB,"RELEASE113_ENGINE_DRIFT")

def load_release113_schema_adapter():
    """Load the installed public, SHA-pinned parser into a fresh module only."""
    path=RUNTIME/"lib/sql_diff_evidence.py"
    need(path.is_file() and not path.is_symlink()
         and blob(path.read_bytes())==RELEASE113_SQL_ADVISORY_BLOB,
         "RELEASE113_SQL_ADVISORY_DRIFT")
    spec=importlib.util.spec_from_file_location("p07_released_sql_schema_parser",path)
    need(spec is not None and spec.loader is not None,
         "RELEASE113_SQL_ADVISORY_IMPORT_FAILED")
    module=importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (ImportError,OSError,ValueError):
        raise Block("RELEASE113_SQL_ADVISORY_IMPORT_FAILED") from None
    need(callable(getattr(module,"_schema_statements",None))
         and callable(getattr(module,"_read_lines",None))
         and hasattr(module,"_SCHEMA_START")
         and hasattr(module,"AdvisoryDiagnosticUnavailable"),
         "RELEASE113_SQL_ADVISORY_CONTRACT_CHANGED")
    return module


def compatible_schema_lines(path, parser):
    """Whole-stream validation: invalid UTF-8 only in unambiguous DML lines.

    Original source is not modified, transcoded, repaired or imported. This is
    *one way* schema-presence evidence only; DDL continuation with invalid
    bytes fails rather than being silently skipped.
    """
    pending_ddl=False
    try:
        with gzip.open(path,"rt",encoding="utf-8",errors="surrogateescape") as h:
            for raw in h:
                if len(raw)>SCHEMA_LINE_LIMIT:
                    raise parser.AdvisoryDiagnosticUnavailable(
                        "SQL_SOURCE_LINE_TOO_LARGE")
                line=raw.strip()
                if any(0xDC80<=ord(char)<=0xDCFF for char in raw):
                    if pending_ddl:
                        raise parser.AdvisoryDiagnosticUnavailable(
                            "SQL_SOURCE_NONUTF8_SCHEMA_CONTINUATION")
                    if not _DML_LINE.match(raw.lstrip()):
                        raise parser.AdvisoryDiagnosticUnavailable(
                            "SQL_SOURCE_NONUTF8_OUTSIDE_KNOWN_DML")
                if pending_ddl:
                    if line.endswith(";"):
                        pending_ddl=False
                elif parser._SCHEMA_START.match(line):
                    pending_ddl=not line.endswith(";")
                yield raw
    except (OSError,EOFError,UnicodeError) as exc:
        raise parser.AdvisoryDiagnosticUnavailable(
            "SQL_DIAGNOSTIC_INPUT_UNAVAILABLE") from exc


def inspect_existing_site(domain,db):
    import inventory
    manifest=inventory.build_manifest(Path("/"))
    need(manifest.get("discovery_source")=="cloudpanel_db+vhost",
         "CP2_INVENTORY_UNPROVEN")
    rows=[x for x in manifest.get("sites",[])
          if isinstance(x,dict) and x.get("domain")==domain]
    need(len(rows)==1 and db not in (rows[0].get("mysql_databases") or []),
         "CP2_TARGET_DATABASE_ALREADY_BOUND_OR_SITE_MISSING")

def scan_schema_adapter(parser,archive):
    # This is a one-way schema presence probe, NOT candidate-byte parity,
    # cross-engine compatibility, data parity, or import/cutover authorization.
    old=parser._read_lines
    try:
        parser._read_lines=lambda path:compatible_schema_lines(path,parser)
        tables,_other=parser._schema_statements(archive)
        if not tables:
            raise parser.AdvisoryDiagnosticUnavailable(
                "SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA")
    except parser.AdvisoryDiagnosticUnavailable as exc:
        reason=str(exc)
        allowed={
            "SQL_DIAGNOSTIC_INPUT_UNAVAILABLE",
            "SQL_SOURCE_EXPORT_NO_TABLE_SCHEMA",
            "SQL_SOURCE_NONUTF8_OUTSIDE_KNOWN_DML",
            "SQL_SOURCE_NONUTF8_SCHEMA_CONTINUATION",
            "SQL_SOURCE_LINE_TOO_LARGE",
            "SQL_SCHEMA_STATEMENT_INCOMPLETE",
            "SQL_SCHEMA_STATEMENT_TOO_LARGE",
            "SQL_DUPLICATE_CREATE_TABLE",
        }
        print("SCHEMA_PRESENCE_RESULT=BLOCKED",flush=True)
        print("SCHEMA_PRESENCE_REASON="+(
            reason if reason in allowed else "OTHER_UNPROVEN"
        ),flush=True)
        return False
    finally:
        parser._read_lines=old
    print("SCHEMA_PRESENCE_RESULT=PASS_ADVISORY_ONLY",flush=True)
    print("SCHEMA_PRESENCE_TABLE_COUNT="+str(len(tables)),flush=True)
    return True


def main():
    need(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    need(sys.argv[1:]==["--probe-existing-www3-only"],
         "EXPLICIT_READONLY_WWW3_PROBE_REQUIRED")
    os.umask(0o077)
    tail,db=verify_state()
    verify_current_runtime()
    sys.path.insert(0,str(RUNTIME/"lib"))
    import server_migration_pull as engine
    inspect_existing_site(DOMAIN,db)
    adapter=load_release113_schema_adapter()
    remote_file=(
        f"/var/lib/vf-server-ops/pull-source/{TAIL}/data/"
        f"www3-schema-{os.urandom(16).hex()}.sql.gz"
    )
    cmd=shlex.join([
        "env",f"PYTHONPATH={tail['source_runtime_path']}/lib",
        "PYTHONDONTWRITEBYTECODE=1","python3","-B","-c",REMOTE,
        DOMAIN,db,remote_file,TAIL,
    ])
    print("MODE=EXISTING_TAIL_BYTE_PRESERVING_SCHEMA_ADVISORY",flush=True)
    print("PRIVATE_PR_CANDIDATE_DOWNLOAD=NO",flush=True)
    print("PRIVATE_PR_EXACT_BINARY_VERIFICATION=NOT_PERFORMED",flush=True)
    print("DATABASE_IMPORT=NO",flush=True)
    print("SOURCE_BUSINESS_WRITES=NO",flush=True)
    print("CP2_SITE_OR_DB_WRITES=NO",flush=True)
    print("SOURCE_TEMP_EXPORT=YES",flush=True)
    created=False
    failed=False
    cleanup=True
    try:
        # Even a nonzero SSH exit may have created the temporary file.
        # The random path is scoped to the existing migration helper's data.
        created=True
        outcome=engine.source_remote(
            tail["source"],cmd,timeout=1800,check=False
        )
        need(outcome.returncode==0
             and outcome.stdout.strip()=="SOURCE_EXPORT_CREATED=YES",
             "SOURCE_EXPORT_OR_BINDING_UNPROVEN")
        with tempfile.TemporaryDirectory(
            prefix="p07-www3-source-check-",dir="/root"
        ) as directory:
            archive=Path(directory)/"source.sql.gz"
            engine.pull_path(tail["source"],remote_file,archive)
            need(archive.is_file() and not archive.is_symlink()
                 and archive.stat().st_size>1024,"SOURCE_GZIP_COPY_UNVERIFIED")
            failed=not scan_schema_adapter(adapter,archive)
    finally:
        if created:
            try:
                gone=engine.source_remote(
                    tail["source"],
                    "rm -f -- "+shlex.quote(remote_file),
                    timeout=40,check=False,
                )
                cleanup=gone.returncode==0
            except Exception:
                cleanup=False
        print("SOURCE_TEMP_CLEANUP="+(
            "PASS" if cleanup else "UNPROVEN"
        ),flush=True)
    need(cleanup,"SOURCE_TEMP_CLEANUP_UNPROVEN")
    print("MIGRATION_STATE_MUTATED=NO",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    print("MIGRATION_RESUME=NO",flush=True)
    return 13 if failed else 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (Block, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("BLOCKED="+(
            str(exc) if type(exc) is Block else type(exc).__name__
        ),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
