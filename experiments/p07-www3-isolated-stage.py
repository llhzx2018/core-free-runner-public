#!/usr/bin/env python3
"""P07 www3: owner-operated NEW scratch DB only; never app config/cutover."""
import gzip,hashlib,importlib.util,json,os,re,shlex,shutil,stat,subprocess,sys,tempfile
from pathlib import Path

HELPER=Path(__file__).with_name("p07-www3-candidate-schema-probe.py")
HELPER_BLOB="8f640e7505c5b49ad5a7574d82c0030eb6e7b884"

class Stop(Exception):pass
def need(condition,why):
    if not condition:raise Stop(why)

def load_helper():
    need(HELPER.is_file() and not HELPER.is_symlink(),"PINNED_HELPER_MISSING")
    data=HELPER.read_bytes()
    sha=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
    need(sha==HELPER_BLOB,"PINNED_HELPER_CHANGED")
    spec=importlib.util.spec_from_file_location("p07_www3_safe",HELPER)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def scratch_name(base):
    import site_lifecycle
    return site_lifecycle.derive_database_identity(
        base.DOMAIN,base.TAIL+":isolated-hex-first-pass",1)

def absent_sql(name):
    """Read the SQL catalog independently of the CloudPanel site inventory."""
    binary=shutil.which("mariadb") or shutil.which("mysql")
    need(binary is not None and re.fullmatch("[A-Za-z0-9]{1,60}",name),
         "TARGET_CATALOG_CLIENT_UNPROVEN")
    query="SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='"+name+"'"
    try:
        r=subprocess.run([binary,"--protocol=socket","--user=root","-N",
                          "-e",query],stdin=subprocess.DEVNULL,
                         capture_output=True,timeout=30,check=False)
    except (OSError,subprocess.SubprocessError):
        raise Stop("TARGET_CATALOG_UNREACHABLE") from None
    need(r.returncode==0 and r.stdout.strip()==b"0",
         "TARGET_DATABASE_ALREADY_EXISTS_OR_CATALOG_UNKNOWN")
    return binary

def strict_scope(sql):
    """No target DB exists before the whole source SQL passes these gates."""
    import sql_diff_evidence,verify
    try:
        need(sql_diff_evidence.require_nonempty_source_schema(sql)==157,
             "SOURCE_TABLE_COUNT_DRIFT")
        need(not verify.sql_unproven_side_effects(sql),
             "SOURCE_UNPROVEN_SIDE_EFFECTS")
        v=sql_diff_evidence.dynamic_guard_syntax_counts(sql)
        need(not any(v.get(k,0) for k in
            ("recognized_unsafe","other_unknown_set","double_quoted_if")),
             "SOURCE_DYNAMIC_SQL_UNPROVEN")
    except (sql_diff_evidence.AdvisoryDiagnosticUnavailable,
            verify.RestoreVerifyError):
        raise Stop("SOURCE_SQL_UNPROVEN") from None
    deny=re.compile(
        r"^(?:USE\b|SOURCE\b|DELIMITER\b|(?:CREATE|ALTER|DROP)\s+"
        r"(?:DATABASE|SCHEMA|USER|ROLE|SERVER|TRIGGER|EVENT|FUNCTION|PROCEDURE)\b|"
        r"GRANT\b|REVOKE\b|RENAME\b|LOAD\s+DATA\b|"
        r"SET\s+(?:GLOBAL|PERSIST)\b|"
        r"(?:CREATE|ALTER|DROP|TRUNCATE)\s+TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?"
        r"(?:\x60?[A-Za-z_][A-Za-z_0-9-]*\x60?\.)|"
        r"(?:INSERT|REPLACE)\s+INTO\s+"
        r"(?:\x60?[A-Za-z_][A-Za-z_0-9-]*\x60?\.)"
        r")",re.I)
    prefix=re.compile(r"^/\*(?:!|M!)[0-9]{5,6}\s+",re.I)
    try:
        with gzip.open(sql,"rt",encoding="utf-8",errors="strict") as f:
            for line in f:
                part=line.strip()
                if not part or part.startswith(("--","#")):continue
                part=prefix.sub("",part)
                need(not deny.match(part),"SOURCE_SQL_ESCAPES_SCRATCH_SCOPE")
    except (OSError,UnicodeError,EOFError):
        raise Stop("SOURCE_SQL_UNREADABLE") from None

def receipt_path(base,db):
    folder=base.BASE/base.TAIL/"target-transactions"
    need(folder.is_dir() and not folder.is_symlink(),
         "SCRATCH_MARKER_PARENT_UNPROVEN")
    info=folder.lstat()
    need(info.st_uid==0 and stat.S_ISDIR(info.st_mode)
         and not(info.st_mode&0o077),"SCRATCH_MARKER_PARENT_UNSAFE")
    name="www3-hex-scratch-"+hashlib.sha256(
        (base.TAIL+":"+base.DOMAIN+":"+db).encode()).hexdigest()[:20]+".json"
    path=folder/name
    need(not os.path.lexists(path),"SCRATCH_PRIOR_ATTEMPT_RETAINED")
    return path

def save(marker,entry,first=False):
    import server_migration as legacy
    if first:
        with os.fdopen(os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                              os.O_NOFOLLOW,0o600),"w") as f:
            json.dump(entry,f,sort_keys=True);f.write("\n")
            f.flush();os.fsync(f.fileno())
    else:
        need(marker.is_file() and not marker.is_symlink(),
             "SCRATCH_MARKER_LOST")
        legacy.atomic_private_json(marker,entry)

def restricted_user(client,db,user,password):
    env=os.environ.copy()
    env["MYSQL_PWD"]=password
    args=[client,"--protocol=tcp","--host=127.0.0.1",
          "--user="+user,"--default-character-set=utf8mb4"]
    try:
        r=subprocess.run(args+["-N","-e","SHOW GRANTS"],env=env,
             stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
             stderr=subprocess.DEVNULL,timeout=30,check=False)
    except (OSError,subprocess.SubprocessError):
        raise Stop("SCRATCH_USER_UNREACHABLE") from None
    need(r.returncode==0 and 0<len(r.stdout)<65536,
         "SCRATCH_USER_UNREACHABLE")
    try:grants=r.stdout.decode("utf-8").splitlines()
    except UnicodeError:raise Stop("SCRATCH_GRANTS_UNKNOWN") from None
    safe=re.compile(r"^GRANT\s+.+?\s+ON\s+\x60?"+re.escape(db)+
                    r"\x60?\.\*\s+TO\b",re.I)
    usage=re.compile(r"^GRANT\s+USAGE\s+ON\s+\*\.\*\s+TO\b",re.I)
    need(1<=len(grants)<=8
         and any(safe.search(x) for x in grants)
         and all((safe.search(x) or usage.search(x))
                 and "WITH GRANT OPTION" not in x.upper()
                 for x in grants),"SCRATCH_PRIVILEGES_OUT_OF_SCOPE")
    return args,env

def import_only_scratch(args,env,db,source):
    proc=None
    try:
        proc=subprocess.Popen(args+["--binary-mode","--database="+db],
             stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
             stderr=subprocess.DEVNULL,env=env)
        with gzip.open(source,"rb") as f:
            while True:
                block=f.read(1<<20)
                if not block:break
                proc.stdin.write(block)
        proc.stdin.close()
        need(proc.wait(timeout=1800)==0,"SCRATCH_IMPORT_FAILED")
    except (OSError,EOFError,BrokenPipeError,subprocess.SubprocessError):
        raise Stop("SCRATCH_IMPORT_FAILED") from None
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill();proc.wait()

def run():
    need(os.geteuid()==0 and sys.argv[1:]==["--stage-new-www3-scratch-only"],
         "EXPLICIT_CP2_SCRATCH_STAGE_REQUIRED")
    os.umask(0o077)
    base=load_helper()
    tail,source_db=base.verify_state()
    base.verify_current_runtime()
    sys.path.insert(0,str(base.RUNTIME/"lib"))
    import server_migration_pull as engine
    import cloudpanel,inventory
    need(engine.target_identity()==tail["target_server_identity"],
         "TARGET_SERVER_IDENTITY_CHANGED")
    base.inspect_existing_site(base.DOMAIN,source_db)
    name,user,password=scratch_name(base)
    need(name!=source_db,"SCRATCH_DB_NAME_COLLISION")
    inv=inventory.build_manifest(Path("/")).get("sites",[])
    need(isinstance(inv,list) and not any(
        name in (r.get("mysql_databases") or [])
        for r in inv if isinstance(r,dict)),"SCRATCH_DB_ALREADY_BOUND")
    client=absent_sql(name)
    marker=receipt_path(base,name)
    parser=base.load_release113_schema_adapter()
    remote=f"/var/lib/vf-server-ops/pull-source/{base.TAIL}/data/www3-hex-{os.urandom(16).hex()}.sql.gz"
    cmd=shlex.join(["env","PYTHONPATH="+tail["source_runtime_path"]+"/lib",
          "PYTHONDONTWRITEBYTECODE=1","python3","-B","-c",
          base.REMOTE_HEX,base.DOMAIN,source_db,remote,base.TAIL])
    print("MODE=WWW3_NEW_SCRATCH_ONLY",flush=True)
    print("EXISTING_WEBSITE_CONFIG_MODIFIED=NO",flush=True)
    print("EXISTING_DATABASE_OVERWRITE=NO",flush=True)
    print("MIGRATION_RETRY=NO",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    try:
        p=engine.source_remote(tail["source"],cmd,timeout=1800,check=False)
        need(p.returncode==0 and
             (p.stdout or "").strip().endswith("HEX_SOURCE_EXPORT=CREATED_UNVERIFIED") and
             "HEX_EXPORT_AUTH=READ_ONLY_CONNECTION_PASS" in p.stdout,
             "SOURCE_HEX_EXPORT_FAILED")
        with tempfile.TemporaryDirectory(prefix="p07-www3-scratch-",dir="/root") as folder:
            before=Path(folder)/"original.sql.gz"
            engine.pull_path(tail["source"],remote,before)
            need(before.is_file() and before.stat().st_size>1024,
                 "SOURCE_HEX_TRANSFER_UNVERIFIED")
            need(base.strict_hex_export_utf8(before) and
                 base.scan_schema_adapter(parser,before,expected_tables=157),
                 "SOURCE_HEX_PROOF_FAILED")
            strict_scope(before)
            absent_sql(name)
            record={"schema":"p07.www3.isolated-hex-scratch.v1",
                    "migration_id":base.TAIL,"domain":base.DOMAIN,
                    "scratch_database":name,"username":user,"password":password,
                    "source_database":source_db,
                    "target_server_identity":tail["target_server_identity"],
                    "source_snapshot_sha256":hashlib.sha256(before.read_bytes()).hexdigest(),
                    "status":"INTENT_RESERVED",
                    "website_activated":False,"original_database_modified":False}
            save(marker,record,first=True)
            try:cloudpanel.add_database(base.DOMAIN,name,user,password)
            except (cloudpanel.CloudPanelError,ValueError):
                record["status"]="CREATE_UNPROVEN";save(marker,record)
                raise Stop("SCRATCH_CREATE_UNPROVEN_NO_RETRY") from None
            record["status"]="CREATED_NOT_IMPORTED";save(marker,record)
            print("SCRATCH_DB=CREATED_NOT_ACTIVATED",flush=True)
            args,env=restricted_user(client,name,user,password)
            try:import_only_scratch(args,env,name,before)
            except Stop:
                record["status"]="IMPORT_UNPROVEN";save(marker,record)
                raise
            record["status"]="IMPORTED_NOT_VERIFIED";save(marker,record)
            print("SCRATCH_IMPORT=COMPLETE_UNVERIFIED",flush=True)
            try:
                after=Path(folder)/"target.sql.gz"
                cloudpanel.export_database(name,after)
                mode=engine.compare_database_dumps(before,after)
            except Exception:
                record["status"]="PARITY_UNPROVEN_RETAIN_SCRATCH";save(marker,record)
                print("SCRATCH_PARITY=UNPROVEN",flush=True)
                raise Stop("SCRATCH_PARITY_NOT_PROVEN") from None
            record["status"]="VERIFIED_NOT_ACTIVATED"
            record["verification_mode"]=mode
            save(marker,record)
            print("SCRATCH_PARITY=PASS",flush=True)
            print("SCRATCH_STATUS=VERIFIED_NOT_ACTIVATED",flush=True)
    finally:
        try:
            gone=engine.source_remote(tail["source"],
                "rm -f -- "+shlex.quote(remote),timeout=60,check=False)
            clean=gone.returncode==0
        except Exception:clean=False
        print("SOURCE_TEMP_CLEANUP="+("PASS" if clean else "UNPROVEN"),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
    need(clean,"SOURCE_TEMP_CLEANUP_UNPROVEN")
    return 0

if __name__=="__main__":
    try:raise SystemExit(run())
    except (Stop,OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        print("BLOCKED="+(str(exc) if type(exc) is Stop else type(exc).__name__),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
