#!/usr/bin/env python3
"""Owner-run CP2 WordPress DB mapping transaction; no DB import or cutover.

Reuse the already verified source-rule candidate. Recheck its current SQL,
preserve the original config privately, connect using four literal constants,
and support crash recovery / exact rollback without rerunning source access.
WordPress, HTTP, Cron and application code are never executed by this tool.
"""
from __future__ import annotations
import contextlib,errno,fcntl,grp,hashlib,importlib.util,json,os,pwd,re,shlex,shutil,stat,subprocess,sys,tempfile
from pathlib import Path

CANDIDATE_NAME="p07-www3-source-rule-candidate.py"
CANDIDATE_BLOB="b5ce19b8a802fb0c3dcf152f896f8d812a88eb99"
CONNECT="--connect-verified-www3-candidate"
ROLLBACK="--rollback-www3-candidate-config"
JOURNAL_NAME="www3-source-rule-connection-v1"
SCHEMA="p07.www3.config-connection.v1"
KEYS=("DB_NAME","DB_USER","DB_PASSWORD","DB_HOST")

class Block(Exception):pass
def need(ok,code):
    if not ok:raise Block(code)
def digest(data):return hashlib.sha256(data).hexdigest()
def gitblob(data):return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def load_candidate():
    path=Path(__file__).with_name(CANDIDATE_NAME)
    need(path.is_file() and not path.is_symlink(),"CANDIDATE_SCRIPT_MISSING")
    need(gitblob(path.read_bytes())==CANDIDATE_BLOB,"CANDIDATE_SCRIPT_DRIFT")
    spec=importlib.util.spec_from_file_location("p07_connect_candidate",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def isolated_site_group(gid,owner):
    """A writable site's primary group must contain only that user or root.

    Include supplementary and primary memberships; never trust the group name
    alone. Private recovery paths do not use this exception.
    """
    try:
        account=pwd.getpwuid(owner);group=grp.getgrgid(gid)
        if account.pw_gid!=gid:return False
        members=[pwd.getpwnam(name) for name in group.gr_mem]
        members.extend(user for user in pwd.getpwall() if user.pw_gid==gid)
        return all(user.pw_uid in {0,owner} for user in members)
    except KeyError:return False

def no_acl(path,name):
    try:os.getxattr(path,"system.posix_acl_"+name,follow_symlinks=False)
    except OSError as exc:
        if exc.errno in {errno.ENODATA,errno.ENOTSUP}:return True
        raise Block("ACL_READBACK_UNPROVEN") from None
    return False

def trusted_mode(info,path,owner):
    if info.st_uid not in {0,owner} or info.st_mode&0o002:return False
    if info.st_mode&0o020:
        return owner is not None and isolated_site_group(info.st_gid,owner) and no_acl(path,"access")
    return True

def secure_dir(path,*,private=False,owner=None,role="DIRECTORY"):
    need(path.is_absolute() and path==path.resolve(),"DIRECTORY_PATH_UNSAFE")
    for part in (path,*path.parents):
        info=part.lstat()
        need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),"DIRECTORY_KIND_UNSAFE")
    info=path.stat()
    if owner is None or private:valid=not info.st_mode&0o022
    else:valid=trusted_mode(info,path,owner)
    if not valid:
        print("PERMISSION_BLOCK_ROLE="+role,flush=True)
        print("PERMISSION_BLOCK_METADATA="+f"{stat.S_IMODE(info.st_mode):04o}:{info.st_uid}:{info.st_gid}",flush=True)
    need(valid,"DIRECTORY_WRITABLE_BY_OTHERS")
    if private:need(info.st_uid==0 and not info.st_mode&0o077,"PRIVATE_DIRECTORY_UNSAFE")
    if owner is not None:need(no_acl(path,"default"),"SITE_DIRECTORY_DEFAULT_ACL_UNPROVEN")

def read_file(path,*,private=False,owner=None):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and 0<info.st_size<=2*1024*1024,"FILE_KIND_OR_SIZE_UNSAFE")
        need((not info.st_mode&0o022 and info.st_uid==0) if private else trusted_mode(info,path,owner),"FILE_OWNER_OR_MODE_UNSAFE")
        if private:need(not info.st_mode&0o077,"PRIVATE_FILE_MODE_UNSAFE")
        with os.fdopen(os.dup(fd),"rb") as file:data=file.read(2*1024*1024+1)
        need(len(data)==info.st_size,"FILE_CHANGED_DURING_READ")
        return data,{"uid":info.st_uid,"gid":info.st_gid,"mode":stat.S_IMODE(info.st_mode)}
    finally:os.close(fd)

def write_private(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as f:f.write(data);f.flush();os.fsync(f.fileno())

def save_journal(folder,record):
    fd,name=tempfile.mkstemp(prefix=".journal-",dir=folder)
    try:
        with os.fdopen(fd,"wb") as f:f.write((json.dumps(record,sort_keys=True)+"\n").encode());f.flush();os.fsync(f.fileno())
        os.replace(name,folder/"journal.json")
        sync_dir(folder)
    finally:
        if os.path.lexists(name):os.unlink(name)

def sync_dir(folder):
    fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

@contextlib.contextmanager
def lock_dir(folder):
    secure_dir(folder,private=True)
    fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Block("CONFIG_TRANSACTION_BUSY") from None
        yield
    finally:os.close(fd)

# Parse PHP tokens without loading wp-config or running application code.
# Comments/string lookalikes cannot become edit locations. Byte offsets match
# Python's byte slicing, including UTF-8 comments and CRLF files.
PHP_SPANS=r'''
$in=json_decode(stream_get_contents(STDIN),true);
$code=base64_decode($in['config'],true);
if($code===false || !function_exists('token_get_all')) exit(21);
try {$all=token_get_all($code,TOKEN_PARSE);} catch(Throwable $e) {exit(22);}
$tokens=[]; $pos=0;
foreach($all as $t) {
 $id=is_array($t)?$t[0]:0; $s=is_array($t)?$t[1]:$t;
 if(!in_array($id,[T_WHITESPACE,T_COMMENT,T_DOC_COMMENT],true))
   $tokens[]=[$id,$s,$pos,$pos+strlen($s)];
 $pos+=strlen($s);
}
$wanted=['DB_NAME','DB_USER','DB_PASSWORD','DB_HOST']; $found=[];
$depth=0; $alternate=0; $condition=null; $waiting=null; $namespace=false;
for($i=0;$i<count($tokens);$i++) {
 $t=$tokens[$i];
 if($t[0]===T_NAMESPACE) $namespace=true;
 if($waiting!==null) {
   if($t[1]===':' && $waiting!==T_ELSEIF) $alternate++;
   $waiting=null;
 }
 if(in_array($t[0],[T_ENDIF,T_ENDFOR,T_ENDFOREACH,T_ENDWHILE,T_ENDSWITCH,T_ENDDECLARE],true)) $alternate--;
 if(in_array($t[0],[T_IF,T_ELSEIF,T_FOR,T_FOREACH,T_WHILE,T_SWITCH,T_DECLARE],true)) $condition=[$t[0],$depth];
 if(in_array($t[0],[T_CURLY_OPEN,T_DOLLAR_OPEN_CURLY_BRACES],true)) $depth++;
 if($t[0]===0 && ($t[1]==='{' || $t[1]==='(' || $t[1]==='[')) $depth++;
 if($t[0]===0 && ($t[1]==='}' || $t[1]===')' || $t[1]===']')) $depth--;
 if($condition!==null && $t[1]===')' && $depth===$condition[1]) {$waiting=$condition[0]; $condition=null;}
 if($t[0]!==T_STRING || strtolower($t[1])!=='define') continue;
 $v=array_slice($tokens,$i,7);
 if(count($v)<4 || $v[1][1]!=='(' || $v[2][0]!==T_CONSTANT_ENCAPSED_STRING) continue;
 $key=substr($v[2][1],1,-1);
 if(!in_array($key,$wanted,true)) continue;
 if(isset($found[$key]) || $namespace || $alternate!==0 || $depth!==0 || count($v)!==7 || $v[3][1]!==',' || $v[4][0]!==T_CONSTANT_ENCAPSED_STRING || $v[5][1]!==')' || $v[6][1]!==';') exit(23);
 $prev=$i>0?$tokens[$i-1]:null;
 if($prev!==null && $prev[0]!==T_OPEN_TAG && !in_array($prev[1],[';','}'],true)) exit(24);
 $found[$key]=['start'=>$v[4][2],'end'=>$v[4][3]];
}
if(count($found)!==4) exit(25);
echo json_encode($found,JSON_THROW_ON_ERROR);
'''

def spans(data,php):
    import base64
    response=subprocess.run([php,"-r",PHP_SPANS],input=json.dumps({"config":base64.b64encode(data).decode()}).encode(),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=20,check=False)
    need(response.returncode==0 and 0<len(response.stdout)<2048,"WP_STATIC_CONFIG_UNPROVEN")
    value=json.loads(response.stdout)
    need(isinstance(value,dict) and set(value)==set(KEYS),"WP_CONSTANT_SCOPE_UNPROVEN")
    ranges=[]
    for key,row in value.items():
        need(isinstance(row,dict) and type(row.get("start")) is int and type(row.get("end")) is int,"WP_CONSTANT_OFFSET_UNPROVEN")
        a,b=row["start"],row["end"]
        need(0<=a<b<=len(data) and data[a:a+1] in (b"'",b'"') and data[b-1:b]==data[a:a+1],"WP_CONSTANT_OFFSET_UNPROVEN")
        ranges.append((a,b))
    ranges.sort();need(all(a[1]<=b[0] for a,b in zip(ranges,ranges[1:])),"WP_CONSTANT_OVERLAP")
    return value

def render(data,record,source_db,php):
    positions=spans(data,php)
    pos=positions["DB_NAME"];old=data[pos["start"]+1:pos["end"]-1]
    need(old==source_db.encode("ascii"),"WP_ORIGINAL_DATABASE_IDENTITY_CHANGED")
    values={"DB_NAME":record["scratch_database"],"DB_USER":record["username"],"DB_PASSWORD":record["password"],"DB_HOST":"127.0.0.1"}
    result=data
    for key,pos in sorted(positions.items(),key=lambda pair:pair[1]["start"],reverse=True):
        value=values[key]
        need(isinstance(value,str) and value and not any(c in value for c in "\0\r\n"),"CANDIDATE_CREDENTIAL_UNSAFE")
        literal=("'"+value.replace("\\","\\\\").replace("'","\\'")+"'").encode()
        result=result[:pos["start"]]+literal+result[pos["end"]:]
    check=subprocess.run([php,"-l"],input=result,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=False)
    need(check.returncode==0,"WP_PREPARED_CONFIG_SYNTAX_FAILED")
    return result

def replace_config(path,before,after,meta,*,owner=None):
    if owner is None:owner=meta["uid"]
    secure_dir(path.parent,owner=owner,role="CONFIG_PARENT")
    current,actual=read_file(path,owner=owner)
    need(current==before and actual==meta,"WP_CONFIG_CHANGED_RETAIN_ALL")
    # Never leave a plain-text config temporary file readable in a Web root.
    # This fresh root-only directory keeps the same filesystem for rename.
    staging=Path(tempfile.mkdtemp(prefix=".p07-db-write-",dir=path.parent))
    name=staging/"config.php"
    try:
        secure_dir(staging,private=True)
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(after);f.flush();os.fchown(f.fileno(),meta["uid"],meta["gid"]);os.fchmod(f.fileno(),meta["mode"]);os.fsync(f.fileno())
        current,actual=read_file(path,owner=owner)
        need(current==before and actual==meta,"WP_CONFIG_CHANGED_RETAIN_ALL")
        os.replace(name,path);sync_dir(path.parent)
        current,actual=read_file(path,owner=owner)
        need(current==after and actual==meta,"WP_CONFIG_READBACK_FAILED")
    finally:
        if os.path.lexists(name):os.unlink(name)
        os.rmdir(staging)

def rollback(folder,identity,expected_path,*,owner=None):
    """Works after interruption/DB loss; never needs SQL or source access."""
    raw,_=read_file(folder/"journal.json",private=True);record=json.loads(raw)
    need(isinstance(record,dict) and record.get("schema")==SCHEMA and record.get("target_identity")==identity
         and record.get("config_path")==str(expected_path) and record.get("status") in {"INTENT_RESERVED","CONNECTED_NOT_CUTOVER_READY","ROLLBACK_REQUIRED","ROLLED_BACK"},"ROLLBACK_JOURNAL_IDENTITY_UNPROVEN")
    before,_=read_file(folder/"original.php",private=True);after,_=read_file(folder/"candidate.php",private=True)
    need(digest(before)==record.get("original_sha256") and digest(after)==record.get("candidate_sha256"),"ROLLBACK_BACKUP_CHANGED")
    meta=record.get("metadata");need(isinstance(meta,dict) and set(meta)=={"uid","gid","mode"} and all(type(x) is int and x>=0 for x in meta.values()),"ROLLBACK_METADATA_UNPROVEN")
    need(meta["mode"]<=0o777 and not meta["mode"]&0o002,"ROLLBACK_METADATA_UNPROVEN")
    if owner is None:owner=meta["uid"]
    need(record.get("site_owner_uid",owner)==owner,"ROLLBACK_SITE_OWNER_CHANGED")
    current,actual=read_file(expected_path,owner=owner)
    need(actual==meta,"ROLLBACK_CONFIG_METADATA_CHANGED")
    if current==after:replace_config(expected_path,after,before,meta,owner=owner)
    else:need(current==before,"ROLLBACK_CONFIG_CHANGED_RETAIN_ALL")
    record["status"]="ROLLED_BACK";save_journal(folder,record)

def preserve_recovery_bundle(folder,bundle):
    hashes={}
    for name,data in bundle.items():
        need(re.fullmatch(r"[A-Za-z0-9_-]+\.py",name) and isinstance(data,bytes),"RECOVERY_BUNDLE_INVALID")
        write_private(folder/name,data);hashes[name]=gitblob(data)
    command="""#!/bin/bash
set -Eeuo pipefail
D=DIR_VALUE
python3 - "$D" <<'PY'
from pathlib import Path
import hashlib,sys
expected=HASH_VALUES
for name,expected_hash in expected.items():
    path=Path(sys.argv[1])/name
    if path.is_symlink():raise SystemExit('ROLLBACK_BUNDLE_UNSAFE')
    data=path.read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\\0'+data).hexdigest()
    if actual!=expected_hash:raise SystemExit('ROLLBACK_BUNDLE_CHANGED')
print('ROLLBACK_BUNDLE_INTEGRITY=PASS',flush=True)
PY
exec env PYTHONDONTWRITEBYTECODE=1 python3 -B "$D/p07-www3-candidate-connect.py" --rollback-www3-candidate-config
"""
    command=command.replace("DIR_VALUE",shlex.quote(str(folder))).replace("HASH_VALUES",repr(hashes))
    write_private(folder/"rollback.sh",command.encode())
    for name,data in bundle.items():need(read_file(folder/name,private=True)[0]==data,"RECOVERY_BUNDLE_READBACK_FAILED")
    return hashes

def recovery_bundle(candidate,ro):
    root=Path(__file__).parent;secure_dir(root,private=True)
    expected={CANDIDATE_NAME:CANDIDATE_BLOB,candidate.READONLY_NAME:candidate.READONLY_BLOB,
              ro.HELPER_NAME:ro.HELPER_BLOB,ro.STAGE_NAME:ro.STAGE_BLOB}
    bundle={Path(__file__).name:read_file(Path(__file__),private=True)[0]}
    for name,sha in expected.items():
        data=read_file(root/name,private=True)[0];need(gitblob(data)==sha,"RECOVERY_COMPANION_DRIFT");bundle[name]=data
    return bundle

def connect_transaction(folder,path,before,after,meta,identity,postcheck,*,bundle=None,owner=None):
    if owner is None:owner=meta["uid"]
    need(not os.path.lexists(folder),"PRIOR_CONNECTION_ATTEMPT_RETAINED")
    os.mkdir(folder,0o700);sync_dir(folder.parent)
    with lock_dir(folder):
        write_private(folder/"original.php",before);write_private(folder/"candidate.php",after)
        record={"schema":SCHEMA,"target_identity":identity,"config_path":str(path),"metadata":meta,"site_owner_uid":owner,
                "original_sha256":digest(before),"candidate_sha256":digest(after),"status":"INTENT_RESERVED",
                "cutover_allowed":False,"database_writes":False,"migration_state_promoted":False}
        if bundle is not None:record["recovery_bundle_gitblobs"]=preserve_recovery_bundle(folder,bundle)
        save_journal(folder,record)
        # Read the durable recovery files back before the first config write.
        need(read_file(folder/"original.php",private=True)[0]==before and read_file(folder/"candidate.php",private=True)[0]==after,"RECOVERY_COPY_READBACK_FAILED")
        try:
            replace_config(path,before,after,meta,owner=owner)
            postcheck()
            current,actual=read_file(path,owner=owner)
            need(current==after and actual==meta,"WP_CONFIG_CHANGED_AFTER_CONNECT")
            record["status"]="CONNECTED_NOT_CUTOVER_READY";save_journal(folder,record)
        except Exception:
            record["status"]="ROLLBACK_REQUIRED";save_journal(folder,record)
            try:rollback(folder,identity,path,owner=owner)
            except Exception:raise Block("CONFIG_ROLLBACK_UNPROVEN_RETAIN_ALL") from None
            raise Block("CONNECTION_FAILED_ORIGINAL_CONFIG_RESTORED") from None

def candidate_receipt(base,identity,source_db):
    import site_lifecycle
    db,user,_=site_lifecycle.derive_database_identity(base.DOMAIN,base.TAIL+":source-rule-copy-v1",1)
    folder=base.BASE/base.TAIL/"target-transactions";secure_dir(folder,private=True,role="TRANSACTION_DIRECTORY")
    token=hashlib.sha256((base.TAIL+":"+base.DOMAIN+":"+db).encode()).hexdigest()[:20]
    raw,_=read_file(folder/("www3-hex-scratch-"+token+".json"),private=True);r=json.loads(raw)
    need(isinstance(r,dict),"CANDIDATE_RECEIPT_INVALID")
    expected={"schema":"p07.www3.source-rule-candidate.v1","migration_id":base.TAIL,"domain":base.DOMAIN,
        "source_database":source_db,"scratch_database":db,"username":user,"target_server_identity":identity,
        "status":"VERIFIED_STATIC_COPY_NOT_ACTIVATED","table_collations_explicit":25,"ascii_hex_defaults_equal":10,
        "verified_rows":198750,"dynamic_groups_omitted":3,"memory_table_count":1}
    need(all(type(r.get(k)) is type(v) and r[k]==v for k,v in expected.items()),"CANDIDATE_RECEIPT_IDENTITY_OR_PROOF_CHANGED")
    for key in ("source_runtime_frozen","website_activated","original_database_modified","cutover_allowed"):
        need(r.get(key) is False,"CANDIDATE_RECEIPT_BOUNDARY_CHANGED")
    for key in ("previous_scratch_retained","source_engines_preserved","fresh_readback_required_before_activation"):
        need(r.get(key) is True,"CANDIDATE_RECEIPT_BOUNDARY_CHANGED")
    need(isinstance(r.get("password"),str) and 16<=len(r["password"])<=1024 and re.fullmatch(r"[0-9a-f]{64}",r.get("source_snapshot_sha256","")),"CANDIDATE_RECEIPT_CREDENTIAL_OR_HASH_UNPROVEN")
    return r

def site_config(base,tail,*,require_php=True):
    import inventory
    source=[s for s in tail["sites"] if s.get("domain")==base.DOMAIN]
    target=[s for s in inventory.build_manifest(Path("/")).get("sites",[]) if s.get("domain")==base.DOMAIN]
    need(len(source)==len(target)==1,"SITE_IDENTITY_UNPROVEN")
    for key in (("site_user","site_root","document_root","runtime") if require_php else ("site_user","site_root","document_root")):
        need(source[0].get(key)==target[0].get(key),"SITE_CONTRACT_CHANGED")
    site=target[0];user=site["site_user"];root=Path(site["site_root"])
    need(re.fullmatch(r"[a-z_][a-z0-9_-]{0,63}",user) and root==Path("/home")/user/"htdocs"/base.DOMAIN,"SITE_ROOT_UNPROVEN")
    owner=pwd.getpwnam(user).pw_uid
    secure_dir(root,owner=owner,role="SITE_ROOT")
    paths=[p for p in (root/"wp-config.php",root/"public/wp-config.php") if os.path.lexists(p)]
    need(len(paths)==1,"WP_CONFIG_MISSING_OR_AMBIGUOUS")
    secure_dir(paths[0].parent,owner=owner,role="CONFIG_PARENT")
    php=None
    if require_php:
        runtime=site.get("runtime",{});version=str(runtime.get("version",""))
        need(str(runtime.get("type","")).lower()=="php" and re.fullmatch(r"[578]\.[0-9]+",version),"PHP_RUNTIME_UNPROVEN")
        php=shutil.which("php"+version);need(php is not None,"SITE_PHP_BINARY_MISSING")
    return paths[0],owner,php

def connection_check(record,stage):
    binary=shutil.which("mariadb") or shutil.which("mysql");need(binary is not None,"SQL_CLIENT_MISSING")
    args,env=stage.restricted_user(binary,record["scratch_database"],record["username"],record["password"])
    r=subprocess.run(args+["--batch","--skip-column-names","--database="+record["scratch_database"],"--execute=SELECT DATABASE(), 1"],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=30,check=False)
    need(r.returncode==0 and r.stdout.strip()==(record["scratch_database"]+"\t1").encode(),"CANDIDATE_DB_CONNECTION_FAILED")

@contextlib.contextmanager
def preconnect_step(name):
    print("CANDIDATE_PRECONNECT_PHASE="+name,flush=True)
    try:yield
    except Block:raise
    except Exception as exc:
        # Companion modules have distinct exception classes. Only these fixed
        # public codes may cross that boundary; SQL/credentials never do.
        allowed={"NATIVE_OUTPUT_PATH_UNSAFE","NATIVE_DUMP_IDENTITY_UNPROVEN",
                 "CANDIDATE_SCHEMA_SCOPE","CANDIDATE_INDEX_OR_OPTIONS_DIFFER",
                 "CANDIDATE_COLUMNS_DIFFER","CANDIDATE_COLUMN_SEMANTICS_DIFFER",
                 "CANDIDATE_LIVE_COLLATION_DIFFER","CANDIDATE_ROWS_UNPROVEN"}
        code=str(exc)
        raise Block(code if code in allowed else "CANDIDATE_PRECONNECT_"+name+"_UNPROVEN") from None

def fresh_proof(candidate,ro,base,stage,engine,tail,source_db,record):
    with tempfile.TemporaryDirectory(prefix="p07-www3-before-connect-",dir="/root") as td:
        root=Path(td);original=root/"source.sql.gz";q=root/"q.sql.gz";fixed=root/"fixed.sql.gz";dump=root/"scratch-native-readonly.sql"
        with preconnect_step("SOURCE_ARCHIVE"):
            actual=stage.import_existing_verified_source(engine,tail,source_db,base,original)
            need(actual==record["source_snapshot_sha256"],"CANDIDATE_SOURCE_ARCHIVE_CHANGED")
        with preconnect_step("SOURCE_CATALOG"):
            catalog=ro.live_source_catalog(engine,tail,source_db,base,stage)
        with preconnect_step("SOURCE_RULES"):
            plan,columns=candidate.prepare_copy(original,q,fixed,catalog,ro,stage)
            need(len(plan)==25 and columns==1848,"CANDIDATE_PRECONNECT_SCOPE_CHANGED")
        with preconnect_step("TARGET_EXPORT"):
            need(ro.native_readonly_scratch_dump(record,stage,dump)=="COMPLETE","CANDIDATE_READBACK_FAILED")
        with preconnect_step("TARGET_CATALOG"):
            target_catalog=ro.live_target_catalog(record,stage)
        with preconnect_step("COPY_COMPARE"):
            defaults,rows=candidate.verify_copy(fixed,dump,catalog,target_catalog,ro)
            need((defaults,rows)==(10,198750),"CANDIDATE_PRECONNECT_CONTENT_CHANGED")
    print("CANDIDATE_PRECONNECT_FRESH_READBACK=PASS",flush=True)

def run():
    need(os.geteuid()==0 and sys.argv[1:] in ([CONNECT],[ROLLBACK]),"EXPLICIT_CONNECT_OR_ROLLBACK_REQUIRED")
    print("MODE="+("WWW3_CONNECT_EXISTING_CANDIDATE" if sys.argv[1]==CONNECT else "WWW3_CONFIG_ROLLBACK"),flush=True)
    os.umask(0o077);candidate=load_candidate();ro=candidate.load_readonly()
    base=ro.load(ro.HELPER_NAME,ro.HELPER_BLOB);stage=ro.load(ro.STAGE_NAME,ro.STAGE_BLOB)
    sys.path.insert(0,str(base.RUNTIME/"lib"))
    import server_migration_pull as engine
    # Rollback must not depend on source access, DB availability or a still
    # PENDING migration; it uses the same local target/site/config identity.
    tail=base.private_state(base.TAIL);identity=engine.target_identity()
    need(identity==tail.get("target_server_identity"),"TARGET_IDENTITY_CHANGED")
    path,owner,php=site_config(base,tail,require_php=sys.argv[1]!=ROLLBACK)
    parent=base.BASE/base.TAIL/"target-transactions";secure_dir(parent,private=True,role="TRANSACTION_DIRECTORY")
    folder=parent/JOURNAL_NAME
    if sys.argv[1]==ROLLBACK:
        with lock_dir(folder):rollback(folder,identity,path,owner=owner)
        print("WWW3_ORIGINAL_CONFIG_RESTORED=VERIFIED",flush=True)
    else:
        need(not os.path.lexists(folder),"PRIOR_CONNECTION_ATTEMPT_RETAINED")
        tail,source_db=base.verify_state();base.verify_current_runtime()
        record=candidate_receipt(base,identity,source_db)
        before,meta=read_file(path,owner=owner);after=render(before,record,source_db,php)
        connection_check(record,stage)
        fresh_proof(candidate,ro,base,stage,engine,tail,source_db,record)
        # Recheck target ownership after slow readback and immediately before
        # reserving the recovery transaction. No migration status promotion.
        need(engine.target_identity()==identity,"TARGET_IDENTITY_CHANGED")
        base.verify_state();again,again_owner,_=site_config(base,tail);need(again==path and again_owner==owner,"SITE_CONFIG_PATH_CHANGED")
        connect_transaction(folder,path,before,after,meta,identity,lambda:connection_check(record,stage),bundle=recovery_bundle(candidate,ro),owner=owner)
        print("WWW3_CANDIDATE_DB_CONFIG_CONNECTED=VERIFIED",flush=True)
        print("WWW3_CONFIG_ROLLBACK_READY=YES",flush=True)
        print("WWW3_CONNECTION_RECOVERY_PATH="+str(folder),flush=True)
        print("WWW3_OFFLINE_CONFIG_ROLLBACK=bash "+str(folder/"rollback.sh"),flush=True)
    print("DATABASE_CREATE_IMPORT_ALTER_DELETE=NONE",flush=True)
    print("EXISTING_DATABASES_AND_CANDIDATE_RECEIPT=RETAIN_UNCHANGED",flush=True)
    print("MIGRATION_STATE_PROMOTED=NO",flush=True)
    print("WEBSITE_HTTP_PHP_APPLICATION_EXECUTION=NONE",flush=True)
    print("LIVE_SOURCE_FINAL_CONSISTENCY=NOT_PROVEN",flush=True)
    print("CRON_AND_RUNTIME_ACTIVATION=NONE",flush=True)
    print("DNS_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0

if __name__=="__main__":
    try:raise SystemExit(run())
    except Exception as exc:
        print("BLOCKED="+(str(exc) if isinstance(exc,Block) else "CONNECTION_OPERATION_UNPROVEN"),flush=True)
        print("AUTOMATIC_RETRY=NO",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
