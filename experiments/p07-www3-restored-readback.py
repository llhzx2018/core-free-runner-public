#!/usr/bin/env python3
"""P07 CP2 www3 isolated DB readonly readback. NOT source-content parity."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

# Do not leave __pycache__ in one-time verification bundles.
sys.dont_write_bytecode = True

# Readback is a two-file, version-locked operator bundle. Never import an
# unrelated file or silently fall back to a different installed runtime.
companion = Path(__file__).with_name("p07-www3-isolated-restore.py")
try:
    if companion.is_symlink() or not companion.is_file():
        raise OSError("missing companion")
    raw = companion.read_bytes()
except OSError:
    print("BLOCKED=READBACK_COMPANION_MISSING_OR_UNSAFE")
    raise SystemExit(13) from None
blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + bytes([0]) + raw).hexdigest()
if blob != "1b3b9285853cc99e467f70d92c7d2b0222874018":
    print("BLOCKED=READBACK_COMPANION_IDENTITY_MISMATCH")
    raise SystemExit(13)
spec=importlib.util.spec_from_file_location("p07_existing",companion)
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

class Blocked(Exception):
    pass

def need(ok,code):
    if not ok: raise Blocked(code)

def safe_file(path):
    s=path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_uid==0 and not s.st_mode&0o077,"PRIVATE_RECORD_UNSAFE")
    return path

def read_private(path):
    return json.loads(safe_file(path).read_text(encoding="utf8"))

def preflight():
    need(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    root=base.SCRATCH_ROOT
    s=root.lstat()
    need(stat.S_ISDIR(s.st_mode) and s.st_uid==0 and not s.st_mode&0o077 and not root.is_symlink(),
         "SCRATCH_DIRECTORY_UNSAFE")
    record=read_private(root/"status.json")
    creds=read_private(root/"scratch-credentials.json")
    need(record.get("migration_id")==base.MID and record.get("original_site")==base.DOMAIN
         and record.get("resume_attempted") is True
         and record.get("status")=="ISOLATED_IMPORT_COMPLETED_NOT_VERIFIED"
         and record.get("cutover_allowed") is False
         and record.get("existing_target_database_modified") is False
         and record.get("site_config_modified") is False
         and record.get("source_frozen") is False
         and record.get("dns_changed") is False,"RESTORE_STATE_UNVERIFIED")
    db,user=base._recover_safe_names(record.get("scratch_database"),record.get("scratch_user"))
    need((record.get("resume_scratch_database"),record.get("resume_scratch_user"))==(db,user),
         "SCRATCH_IDENTITY_UNVERIFIED")
    need(creds.get("database")==record.get("scratch_database")
         and creds.get("user")==record.get("scratch_user"),"ORIGINAL_CREDENTIAL_IDENTITY_CHANGED")
    password=creds.get("password")
    need(type(password) is str and 30<=len(password)<=96 and "\n" not in password
         and "\r" not in password,"SCRATCH_PASSWORD_UNVERIFIED")
    archive=root/"source.sql.gz"
    safe_file(archive)
    need(re.fullmatch("[0-9a-f]{64}",str(record.get("source_dump_sha256","")))
         and base.sha256_file(archive)==record["source_dump_sha256"],"SOURCE_SHA256_MISMATCH")
    decompressed,ddl=base.inspect_archive(archive)
    need(decompressed==record.get("source_uncompressed_bytes")
         and ddl==record.get("source_create_table_lines") and ddl>0,"SOURCE_DDL_OR_BYTES_MISMATCH")
    child=read_private(base.STATE)
    sites=child.get("sites")
    need(child.get("migration_id")==base.MID and child.get("status")=="PREPARE_FAILED"
         and child.get("cutover_prohibited") is True
         and child.get("source_runtime_frozen") is False
         and child.get("dns_changed_by_p07") is False
         and type(sites) is list and len(sites)==2
         and sites[1].get("domain")==base.DOMAIN
         and sites[1].get("stage_status")=="PENDING","CHILD_STATE_DRIFT")
    return db,user,password,ddl

def query(argv,sql,timeout=120):
    try:
        p=subprocess.run(argv+["--execute",sql],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=timeout,check=False)
    except (OSError,subprocess.SubprocessError):
        raise Blocked("READ_ONLY_QUERY_UNAVAILABLE") from None
    need(p.returncode==0 and len(p.stdout)<1048576,"READ_ONLY_QUERY_FAILED")
    try: return p.stdout.decode("utf-8","strict").strip()
    except UnicodeError: raise Blocked("METADATA_NOT_UTF8") from None

def number(raw):
    need(bool(re.fullmatch("[0-9]{1,16}",raw)),"SQL_COUNT_UNPROVEN")
    value=int(raw)
    need(value<=10**15,"SQL_COUNT_TOO_LARGE")
    return value

def database_readback(db,user,password,*,include_count_map=False):
    need(base._cloudpanel_metadata_counts(db)==("1","1")
         and base._master_sql_presence(db,user)==("1","1"),
         "CLOUDPANEL_AND_MARIADB_BINDING_UNVERIFIED")
    with tempfile.TemporaryDirectory(prefix="p07-readback-",dir="/root") as t:
        cfg=Path(t)/"client.cnf"
        fd=os.open(cfg,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        escape=password.replace("\\","\\\\").replace('"','\\"')
        with os.fdopen(fd,"w") as f:
            f.write('[client]\nuser="'+user+'"\npassword="'+escape+
                    '"\nhost=127.0.0.1\nprotocol=tcp\n')
        argv=["mariadb","--defaults-extra-file="+str(cfg),"--batch",
              "--skip-column-names","--default-character-set=utf8mb4"]
        qdb="'"+db+"'"
        output=query(argv,"SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA="
              +qdb+" AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",60)
        # MySQL and MariaDB may sort metadata differently under their collations.
        # Python codepoint ordering is stable across both database engines.
        tables=sorted(output.splitlines()) if output else []
        need(0<len(tables)<=1000 and len(tables)==len(set(tables)),"BASE_TABLES_UNPROVEN")
        need(all(re.fullmatch("[A-Za-z0-9_]{1,64}",s) for s in tables),
             "TABLE_NAMES_REQUIRE_EXPLICIT_SAFE_PARSER")
        cols=number(query(argv,"SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA="+qdb,60))
        need(cols>=len(tables),"COLUMN_COUNT_UNPROVEN")
        counts=[]
        table_counts={}
        for table in tables:
            escaped_name=chr(96)+db+chr(96)+"."+chr(96)+table+chr(96)
            n=number(query(argv,"SELECT COUNT(*) FROM "+escaped_name,180))
            counts.append(n)
            # Table identities stay in RAM; never expose actual names in logs.
            ident=hashlib.sha256(table.encode("ascii")).hexdigest()
            need(ident not in table_counts,"DUPLICATE_TABLE_IDENTITY")
            table_counts[ident]=n
        hashed=hashlib.sha256()
        for name,count in zip(tables,counts):
            hashed.update(name.encode("ascii")+bytes([0])+str(count).encode()+bytes([10]))
        result=(len(tables),cols,sum(counts),sum(n>0 for n in counts),hashed.hexdigest())
        return result+(table_counts,) if include_count_map else result

def main():
    need(sys.argv[1:]==["--verify-restored-read-only"],"EXPLICIT_READ_ONLY_ARG_REQUIRED")
    db,user,password,expected=preflight()
    tables,cols,rows,nonempty,fingerprint=database_readback(db,user,password)
    need(tables==expected,"RESTORED_TABLES_DIFFER_FROM_SOURCE_DDL")
    for key,value in (
        ("ORIGINAL_SOURCE_ARCHIVE","SHA256_PASS"),
        ("CLOUDPANEL_DATABASE_BINDING","PASS"),
        ("RESTORED_TABLES",str(tables)),("RESTORED_COLUMNS",str(cols)),
        ("RESTORED_TOTAL_ROWS",str(rows)),("RESTORED_NONEMPTY_TABLES",str(nonempty)),
        ("SOURCE_DDL_TABLE_COUNT","MATCH"),
        ("ROW_COUNT_FINGERPRINT_SHA256",fingerprint),
        ("RESTORED_DATABASE_READBACK","PASS"),
        ("SOURCE_TARGET_ROW_CONTENT_PARITY","NOT_VERIFIED"),
        ("SOURCE_RAW_BYTES_TO_DB_PARITY","NOT_VERIFIED"),
        ("DATABASE_WRITES","NONE"),("CUTOVER_ALLOWED","NO")):
        print(key+"="+value,flush=True)
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except (Blocked,base.Stop) as exc:
        print("BLOCKED="+str(exc))
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=UNVERIFIED_LOCAL_STATE")
        raise SystemExit(13) from None
