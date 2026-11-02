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

def _target_master_credentials():
    """Read CP2's existing CloudPanel master connection, never print secrets.

    CloudPanel source-side export already proves that a direct root/socket
    assumption is not portable. Require a documented, local-only connection;
    authentication failure can NEVER be interpreted as database absence.
    """
    env=os.environ.copy()
    env.setdefault("SUDO_USER","root")
    try:
        result=subprocess.run(
            ["clpctl","db:show:master-credentials"],
            stdin=subprocess.DEVNULL,capture_output=True,
            timeout=30,check=False,env=env,
        )
    except (OSError,subprocess.SubprocessError):
        raise Stop("TARGET_CATALOG_MASTER_CREDENTIALS_UNAVAILABLE") from None
    need(result.returncode==0 and 0<len(result.stdout)<=32768,
         "TARGET_CATALOG_MASTER_CREDENTIALS_UNAVAILABLE")
    raw=result.stdout.decode("utf-8","replace")
    # Reuse the same conservative CloudPanel formats already verified on
    # the source VPS: a single local mysql Connect Command OR four fields.
    lines=[line for line in raw.splitlines()
           if re.search(r"Connect\s+Command",line,re.I)]
    values={}
    if len(lines)==1:
        tail=re.split(r"Connect\s+Command",lines[0],
                      maxsplit=1,flags=re.I)[1].strip(" \t:|")
        try: parts=shlex.split(tail)
        except ValueError:
            raise Stop("TARGET_CATALOG_MASTER_FORMAT_UNPROVEN") from None
        need(parts and Path(parts[0]).name in ("mysql","mariadb"),
             "TARGET_CATALOG_MASTER_FORMAT_UNPROVEN")
        prefix={"-h":"host","-P":"port","-u":"user","-p":"password"}
        long={"--host":"host","--port":"port",
              "--user":"user","--password":"password"}
        index=1
        while index<len(parts):
            item=parts[index]
            # CloudPanel v2's documented Connect Command ends in -A
            # (skip mysql auto-rehash). It has no write or query effect.
            # Permit only that exact final token; all other extra argv
            # are still rejected before any SQL connection is attempted.
            if item=="-A" and index==len(parts)-1:
                index+=1
                continue
            found=None
            value=None
            for opt,key in long.items():
                if item.startswith(opt+"="):
                    found=key
                    value=item[len(opt)+1:]
                    break
            if found is None:
                for opt,key in prefix.items():
                    if item.startswith(opt):
                        found=key
                        value=item[len(opt):]
                        if not value:
                            index+=1
                            if index>=len(parts):
                                raise Stop("TARGET_CATALOG_MASTER_FORMAT_UNPROVEN")
                            value=parts[index]
                        break
            need(found is not None and found not in values and value,
                 "TARGET_CATALOG_MASTER_FORMAT_UNPROVEN")
            values[found]=value
            index+=1
    elif not lines:
        names={"host":"host","port":"port","username":"user",
               "user":"user","password":"password"}
        for line in raw.splitlines():
            body=line.strip()
            if body.startswith("|"):
                cells=[v.strip() for v in body.strip("|").split("|")]
                if len(cells)!=2:
                    continue
                label,value=cells
            elif ":" in body:
                label,value=body.split(":",1)
                value=value.strip()
            else:
                continue
            label=names.get(re.sub(r"[\s_-]+","",label).lower())
            if label is None:
                continue
            need(label not in values and value,
                 "TARGET_CATALOG_MASTER_FORMAT_UNPROVEN")
            values[label]=value
    need(set(values)=={"host","port","user","password"},
         "TARGET_CATALOG_MASTER_FORMAT_UNPROVEN")
    need(values["host"] in ("127.0.0.1","localhost","::1")
         and re.fullmatch(r"[0-9]{1,5}",values["port"])
         and 1<=int(values["port"])<=65535
         and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}",values["user"])
         and 0<len(values["password"])<=1024
         and not any(c in values["password"] for c in ("\x00","\n","\r")),
         "TARGET_CATALOG_MASTER_SCOPE_UNPROVEN")
    return values


def absent_sql(name):
    """Independently prove absence in the *real* CP2 SQL catalog.

    A master-authenticated SQL catalog query must return exactly 0; 1+ means
    the database already exists and must be retained. Connection failure or
    insufficient global privileges is never permission to create anything.
    The caller still separately verifies CloudPanel binding and owner markers.
    """
    binary=shutil.which("mariadb") or shutil.which("mysql")
    need(binary is not None and re.fullmatch(r"[A-Za-z0-9]{1,60}",name),
         "TARGET_CATALOG_CLIENT_UNPROVEN")
    identity=_target_master_credentials()
    environment=os.environ.copy()
    environment["MYSQL_PWD"]=identity["password"]
    arguments=[
        binary,"--protocol=tcp","--host="+identity["host"],
        "--port="+identity["port"],"--user="+identity["user"],
        "--batch","--skip-column-names",
    ]
    try:
        # A low-privilege SQL account can falsely report zero schemas because
        # information_schema hides schemas it cannot see. Verify the master
        # account has global ALL PRIVILEGES before trusting a zero result.
        grants=subprocess.run(
            arguments+["--execute=SHOW GRANTS"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,env=environment,check=False,timeout=30,
        )
    except (OSError,subprocess.SubprocessError):
        raise Stop("TARGET_CATALOG_AUTH_UNAVAILABLE") from None
    need(grants.returncode==0 and 0<len(grants.stdout)<=65536,
         "TARGET_CATALOG_AUTH_UNAVAILABLE")
    try:lines=grants.stdout.decode("utf-8","strict").splitlines()
    except UnicodeError:
        raise Stop("TARGET_CATALOG_PRIVILEGES_UNPROVEN") from None
    need(any(re.match(
        r"^GRANT\s+ALL(?:\s+PRIVILEGES)?\s+ON\s+\*\.\*\s+TO\b",
        line,re.I,
    ) for line in lines),"TARGET_CATALOG_PRIVILEGES_UNPROVEN")
    sql=("SELECT COUNT(*) FROM information_schema.SCHEMATA "
         "WHERE SCHEMA_NAME='"+name+"'")
    try:
        result=subprocess.run(
            arguments+["--execute="+sql],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,env=environment,check=False,timeout=30,
        )
    except (OSError,subprocess.SubprocessError):
        raise Stop("TARGET_CATALOG_QUERY_FAILED") from None
    need(result.returncode==0,"TARGET_CATALOG_QUERY_FAILED")
    raw=result.stdout.strip()
    if raw==b"0":
        print("SCRATCH_SQL_CATALOG=ABSENT_VERIFIED",flush=True)
        return binary
    if re.fullmatch(rb"[1-9][0-9]{0,6}",raw):
        raise Stop("TARGET_SCRATCH_DATABASE_ALREADY_EXISTS_RETAIN")
    raise Stop("TARGET_CATALOG_QUERY_AMBIGUOUS")


# Local fail-closed side-effect scan backported from the product PR #282.
# Public release113 `verify` has the dynamic guards but NOT this function.
# Keep this independent until the fully-tested candidate is released.
_SQL_SIDE_EFFECT_HEAD_RE = re.compile(
    r"^(?:GRANT|REVOKE|FLUSH|RESET|SHUTDOWN|CALL|DO|"
    r"PREPARE|EXECUTE|DEALLOCATE|UPDATE|DELETE|TRUNCATE|"
    r"LOAD\s+(?:DATA|XML)|"
    r"(?:CREATE|ALTER|DROP|RENAME)\s+(?:USER|ROLE)\b|"
    r"SET\s+(?:GLOBAL\b|PERSIST(?:_ONLY)?\b|"
    r"@@\s*(?:GLOBAL|PERSIST(?:_ONLY)?)\s*\.)|"
    r"SELECT\b[^\r\n]*\bINTO\s+(?:OUTFILE|DUMPFILE)\b)",
    re.I,
)
_SQL_VERSIONED_HEAD_RE = re.compile(r"^/\*(?:!|M!)[0-9]{5,6}\s+(.+?)\s*\*/;?$", re.I)


def _sql_line_stacks_commands(line: str) -> bool:
    """Detect an unquoted terminal semicolon followed by more SQL tokens."""
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                if index + 1 < len(line) and line[index + 1] == quote:
                    index += 2
                    continue
                quote = ""
        elif char in ("'", '"', chr(96)):
            quote = char
        elif char == ";" and line[index + 1:].strip():
            return True
        index += 1
    return False


def standalone_sql_unproven_side_effects(path: Path, verifier) -> bool:
    """Reject privileged and stacked SQL before exact or logical parity.

    Known session-only dynamic guard flows are exempt. Normal comments,
    literals and the exact MariaDB sandbox banner are not SQL commands.
    """
    known_dynamic = verifier._cross_engine_known_dynamic_guard_lines(path)
    opener = gzip.open if path.name.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="strict") as handle:
            in_comment = False
            for number, raw in enumerate(handle, 1):
                if number in known_dynamic:
                    continue
                line = raw.strip()
                if not line:
                    continue
                if in_comment:
                    if "*/" not in line:
                        continue
                    line = line.split("*/", 1)[1].strip()
                    in_comment = False
                if not line or line.startswith(("--", "#")):
                    continue
                if line == r"/*M!999999\- enable the sandbox mode */":
                    continue
                while line.startswith("/*") and not re.match(r"^/\*(?:!|M!)", line, re.I):
                    if "*/" not in line:
                        in_comment = True
                        line = ""
                        break
                    line = line.split("*/", 1)[1].strip()
                if not line:
                    continue
                match = _SQL_VERSIONED_HEAD_RE.fullmatch(line)
                if match:
                    line = match.group(1).strip()
                elif re.match(r"^/\*(?:!|M!)[0-9]{5,6}\s+CREATE\s+TRIGGER\b", line, re.I):
                    # A mysqldump multiline CREATE TRIGGER is verified by the
                    # existing exact guarded DDL fingerprint, including its
                    # body. Reject privileged lines inside it independently.
                    continue
                elif re.match(r"^/\*(?:!|M!)", line, re.I):
                    return True
                if _SQL_SIDE_EFFECT_HEAD_RE.match(line):
                    return True
                if re.match(
                    r"^(?:SET|SELECT|INSERT|REPLACE|UPDATE|DELETE|"
                    r"CREATE|ALTER|DROP|GRANT|REVOKE)\b",
                    line, re.I,
                ) and _sql_line_stacks_commands(line):
                    return True
        return in_comment
    except (OSError, EOFError, UnicodeError) as exc:
        raise verifier.RestoreVerifyError("SQL side-effect scan cannot be read") from exc



def strict_scope(sql):
    """No target DB exists before the whole source SQL passes these gates."""
    import sql_diff_evidence,verify
    try:
        need(sql_diff_evidence.require_nonempty_source_schema(sql)==157,
             "SOURCE_TABLE_COUNT_DRIFT")
        need(not standalone_sql_unproven_side_effects(sql,verify),
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

# Only consider an earlier exact-scope, root-private hex export.  The
# previous operator's remote transport failed after export; never create a
# second source snapshot or delete a first-party forensic artifact as a retry.
# This does not establish a live-source freeze or permission to cut over.
REMOTE_REUSE_HEX=r'''
import hashlib,inventory,os,re,stat,sys,time
from pathlib import Path
domain,db,mid=sys.argv[1:]
if not re.fullmatch(r"pull-[0-9]{8}T[0-9]{6}Z-[a-z0-9]{8}",mid):
    raise SystemExit(21)
root=Path("/var/lib/vf-server-ops/pull-source")/mid/"data"
if root.is_symlink() or not root.is_dir():
    raise SystemExit(22)
st=root.lstat()
if not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or st.st_mode & 0o077:
    raise SystemExit(23)
sites=[x for x in inventory.build_manifest(Path("/")).get("sites",[])
       if isinstance(x,dict) and x.get("domain")==domain]
if len(sites)!=1 or sites[0].get("mysql_databases")!=[db]:
    raise SystemExit(24)
paths=list(root.glob("www3-hex-*.sql.gz"))
if len(paths)!=1:
    raise SystemExit(25)
entry=paths[0]
if not re.fullmatch(r"www3-hex-[a-f0-9]{32}\.sql\.gz",entry.name):
    raise SystemExit(26)
info=entry.lstat()
if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or \
   info.st_mode & 0o077 or info.st_nlink!=1 or not \
   1024<info.st_size<350*1024*1024 or not \
   0<=time.time()-info.st_mtime<72*3600:
    raise SystemExit(27)
digest=hashlib.sha256()
with entry.open("rb") as source:
    if source.read(2)!=b"\x1f\x8b":
        raise SystemExit(28)
    source.seek(0)
    while True:
        data=source.read(1024*1024)
        if not data:
            break
        digest.update(data)
after=entry.lstat()
if (not stat.S_ISREG(after.st_mode) or after.st_ino!=info.st_ino
    or after.st_size!=info.st_size or after.st_mtime_ns!=info.st_mtime_ns):
    raise SystemExit(29)
print("EXISTING_HEX=OWNER_SCOPED")
print("HEX_NAME="+entry.name)
print("HEX_BYTES="+str(info.st_size))
print("HEX_SHA256="+digest.hexdigest())
'''


def source_hex_identity(engine,tail,source_db,base):
    """Read-only source record; no raw database data or path in stdout."""
    command=shlex.join([
        "env","PYTHONPATH="+tail["source_runtime_path"]+"/lib",
        "PYTHONDONTWRITEBYTECODE=1","python3","-B","-c",
        REMOTE_REUSE_HEX,base.DOMAIN,source_db,base.TAIL
    ])
    try:
        result=engine.source_remote(tail["source"],command,
                                    timeout=180,check=False)
    except engine.PullMigrationError:
        raise Stop("SOURCE_HEX_READONLY_SSH_UNAVAILABLE") from None
    need(result.returncode==0,"SOURCE_HEX_SCOPE_OR_FILE_UNVERIFIED")
    lines=(result.stdout or "").splitlines()
    need(len(lines)==4 and lines[0]=="EXISTING_HEX=OWNER_SCOPED",
         "SOURCE_HEX_IDENTITY_REPLY_UNVERIFIED")
    need(lines[1].startswith("HEX_NAME=")
         and lines[2].startswith("HEX_BYTES=")
         and lines[3].startswith("HEX_SHA256="),
         "SOURCE_HEX_IDENTITY_REPLY_UNVERIFIED")
    name=lines[1][len("HEX_NAME="):]
    size=lines[2][len("HEX_BYTES="):]
    sha=lines[3][len("HEX_SHA256="):]
    need(re.fullmatch(r"www3-hex-[a-f0-9]{32}\.sql\.gz",name)
         and re.fullmatch(r"[0-9]{4,9}",size)
         and 1024<int(size)<350*1024*1024
         and re.fullmatch(r"[a-f0-9]{64}",sha),
         "SOURCE_HEX_IDENTITY_REPLY_UNVERIFIED")
    return name,int(size),sha


def import_existing_verified_source(engine,tail,source_db,base,local):
    """Retrieve one already-owned file; verify same source bytes before+after.

    This file remains on old VPS. A new source snapshot is neither created
    nor deleted and this stage does not assert that the live DB is frozen.
    """
    first=source_hex_identity(engine,tail,source_db,base)
    name,size,digest=first
    remote=(f"/var/lib/vf-server-ops/pull-source/{base.TAIL}/data/"+name)
    try:
        engine.pull_path(tail["source"],remote,local)
    except engine.PullMigrationError:
        raise Stop("SOURCE_HEX_RSYNC_UNAVAILABLE") from None
    need(local.is_file() and not local.is_symlink()
         and local.stat().st_size==size,
         "SOURCE_HEX_TRANSFER_SIZE_UNVERIFIED")
    actual=hashlib.sha256()
    with local.open("rb") as source:
        for data in iter(lambda:source.read(1024*1024),b""):
            actual.update(data)
    need(actual.hexdigest()==digest,
         "SOURCE_HEX_TRANSFER_DIGEST_MISMATCH")
    second=source_hex_identity(engine,tail,source_db,base)
    need(first==second,"SOURCE_HEX_CHANGED_DURING_TRANSFER")
    print("SOURCE_HEX_EXISTING_REUSE=PASS",flush=True)
    print("SOURCE_HEX_TRANSFER_SHA256=PASS",flush=True)
    print("SOURCE_TEMP_CLEANUP=NOT_ATTEMPTED_RETAINED",flush=True)
    return digest


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
    print("MODE=WWW3_EXISTING_SOURCE_HEX_TO_NEW_SCRATCH_ONLY",flush=True)
    print("SOURCE_NEW_EXPORT=NO",flush=True)
    print("SOURCE_TEMP_CLEANUP=NOT_ATTEMPTED_RETAINED",flush=True)
    print("EXISTING_WEBSITE_CONFIG_MODIFIED=NO",flush=True)
    print("EXISTING_DATABASE_OVERWRITE=NO",flush=True)
    print("MIGRATION_RETRY=NO",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix="p07-www3-scratch-",dir="/root") as folder:
            before=Path(folder)/"original.sql.gz"
            source_digest=import_existing_verified_source(
                engine,tail,source_db,base,before
            )
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
                    "source_snapshot_sha256":source_digest,
                    "source_snapshot_kind":"EXISTING_PRIVATE_HEX_ADVISORY",
                    "source_runtime_frozen":False,
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
                need(mode in {
                    "CANONICAL_SQL_EXACT",
                    "CROSS_ENGINE_GUARDED_SESSION_SQL_EXACT",
                    "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
                    "CROSS_ENGINE_LOGICAL_CONTENT",
                },"SCRATCH_PARITY_MODE_UNRECOGNIZED")
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
        # Preserve the previous source snapshot after any result, even a
        # verified scratch. A separate owner-scoped retention/cleanup step
        # must independently confirm identity and permission before deletion.
        print("SOURCE_TEMP_CLEANUP=NOT_ATTEMPTED_RETAINED",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
    return 0

if __name__=="__main__":
    try:raise SystemExit(run())
    except (Stop,OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        print("BLOCKED="+(str(exc) if type(exc) is Stop else type(exc).__name__),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
