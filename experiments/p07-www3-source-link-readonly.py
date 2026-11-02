#!/usr/bin/env python3
"""P07 www3: CP2 source SSH and old-VPS temporary export READ-ONLY audit.

No SQL export, transfer, DB query/import/create, migration resume or deletion.
Only reports bounded, fixed-status evidence; remote paths/host and secret
connection diagnostics are never printed. A failed SSH leaves cleanup UNPROVEN.
"""
from __future__ import annotations
import hashlib,importlib.util,os,re,shlex,stat,subprocess,sys
from pathlib import Path

HELPER=Path(__file__).with_name("p07-www3-candidate-schema-probe.py")
PIN="8f640e7505c5b49ad5a7574d82c0030eb6e7b884"
REMOTE=r'''
import os,re,stat,sys
from pathlib import Path
mid=sys.argv[1]
if not re.fullmatch(r"pull-[0-9]{8}T[0-9]{6}Z-[a-z0-9]{8}",mid):
    raise SystemExit(21)
root=Path("/var/lib/vf-server-ops/pull-source")/mid/"data"
if not root.is_dir() or root.is_symlink():
    raise SystemExit(22)
mode=root.lstat()
if not stat.S_ISDIR(mode.st_mode) or mode.st_uid!=0 or mode.st_mode & 0o077:
    raise SystemExit(23)
count=0
unsafe=0
for entry in root.glob("www3-hex-*.sql.gz"):
    if not re.fullmatch(r"www3-hex-[a-f0-9]{32}\.sql\.gz",entry.name):
        unsafe+=1
        continue
    try: info=entry.lstat()
    except OSError:
        unsafe+=1
        continue
    if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0
        or info.st_mode & 0o077 or info.st_nlink!=1):
        unsafe+=1
    else:
        count+=1
if count+unsafe>500:
    raise SystemExit(24)
print("SOURCE_HEX_TEMP_AUDIT=PASS")
print("SOURCE_HEX_TEMP_FILES="+str(count))
print("SOURCE_HEX_TEMP_UNSAFE="+str(unsafe))
'''

class Block(Exception):pass
def guard(ok,why):
    if not ok:raise Block(why)
def load_helper():
    guard(HELPER.is_file() and not HELPER.is_symlink(),"PINNED_HELPER_MISSING")
    raw=HELPER.read_bytes()
    sha=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()
    guard(sha==PIN,"PINNED_HELPER_DRIFT")
    spec=importlib.util.spec_from_file_location("p07_www3_probe_ref",HELPER)
    guard(spec and spec.loader,"PINNED_HELPER_IMPORT_UNAVAILABLE")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
def classify(stderr,rc):
    # Never report raw stderr; it may contain hostnames, usernames, paths.
    try:message=stderr[:4096].lower()
    except (TypeError,AttributeError):message=""
    if any(w in message for w in ("permission denied","publickey","too many authentication failures")):
        return "SSH_AUTH_DENIED"
    if any(w in message for w in ("host key verification failed","remote host identification has changed")):
        return "SSH_HOST_KEY_UNVERIFIED"
    if any(w in message for w in ("connection timed out","operation timed out","connection timeout")):
        return "SSH_CONNECTION_TIMEOUT"
    if any(w in message for w in ("connection refused","no route to host","network is unreachable")):
        return "SSH_NETWORK_UNREACHABLE"
    if any(w in message for w in ("could not resolve hostname","name or service not known")):
        return "SSH_HOST_RESOLUTION_FAILED"
    if "connection reset" in message or "connection closed" in message:
        return "SSH_CONNECTION_INTERRUPTED"
    if "sudo:" in message:
        return "SSH_REMOTE_PRIVILEGE_UNPROVEN"
    return "SSH_REMOTE_EXIT_UNCLASSIFIED" if rc else "NONE"

def run():
    guard(os.geteuid()==0 and sys.argv[1:]==["--read-only-source-ssh-and-temp-audit"],
          "EXPLICIT_READONLY_AUDIT_REQUIRED")
    base=load_helper()
    tail,db=base.verify_state()
    base.verify_current_runtime()
    sys.path.insert(0,str(base.RUNTIME/"lib"))
    import server_migration_pull as engine
    guard(engine.target_identity()==tail["target_server_identity"],
          "TARGET_IDENTITY_CHANGED")
    base.inspect_existing_site(base.DOMAIN,db)
    source=tail["source"]
    key=source.get("identity_file")
    if key:
        f=Path(key)
        guard(f.is_file() and not f.is_symlink(),"SOURCE_SSH_IDENTITY_FILE_UNAVAILABLE")
        m=f.lstat()
        guard(stat.S_ISREG(m.st_mode) and not(m.st_mode&0o077),
              "SOURCE_SSH_IDENTITY_FILE_UNSAFE")
    print("MODE=P07_WWW3_SSH_AND_TEMP_READ_ONLY",flush=True)
    print("SOURCE_BUSINESS_WRITES=NO",flush=True)
    print("SOURCE_TEMP_CLEANUP=NOT_ATTEMPTED",flush=True)
    print("CP2_DATABASE_WRITES=NO",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    try:
        result=engine.source_remote(source,"printf 'P07_SSH_READONLY_OK'",
                                    timeout=45,check=False)
    except engine.PullMigrationError:
        print("SOURCE_SSH_HEALTH=TRANSPORT_EXCEPTION",flush=True)
        print("SOURCE_HEX_TEMP_AUDIT=UNPROVEN",flush=True)
        return 13
    if result.returncode or (result.stdout or "").strip()!="P07_SSH_READONLY_OK":
        print("SOURCE_SSH_HEALTH=BLOCKED",flush=True)
        print("SOURCE_SSH_REASON="+classify(result.stderr,result.returncode),flush=True)
        print("SOURCE_HEX_TEMP_AUDIT=UNPROVEN",flush=True)
        return 13
    print("SOURCE_SSH_HEALTH=PASS",flush=True)
    command=shlex.join(["python3","-B","-c",REMOTE,base.TAIL])
    try:
        remote=engine.source_remote(source,command,timeout=60,check=False)
    except engine.PullMigrationError:
        print("SOURCE_HEX_TEMP_AUDIT=TRANSPORT_EXCEPTION",flush=True)
        return 13
    if remote.returncode:
        print("SOURCE_HEX_TEMP_AUDIT=BLOCKED",flush=True)
        print("SOURCE_AUDIT_REASON="+classify(remote.stderr,remote.returncode),flush=True)
        return 13
    lines=(remote.stdout or "").splitlines()
    if len(lines)!=3 or lines[0]!="SOURCE_HEX_TEMP_AUDIT=PASS":
        print("SOURCE_HEX_TEMP_AUDIT=UNPROVEN",flush=True)
        return 13
    numbers=[]
    for prefix,item in zip(("SOURCE_HEX_TEMP_FILES=","SOURCE_HEX_TEMP_UNSAFE="),lines[1:]):
        if not item.startswith(prefix) or not re.fullmatch(r"[0-9]{1,3}",item[len(prefix):]):
            print("SOURCE_HEX_TEMP_AUDIT=UNPROVEN",flush=True)
            return 13
        numbers.append(int(item[len(prefix):]))
    if sum(numbers)>500:
        print("SOURCE_HEX_TEMP_AUDIT=UNPROVEN",flush=True)
        return 13
    print("SOURCE_HEX_TEMP_AUDIT=PASS",flush=True)
    print("SOURCE_HEX_TEMP_FILES="+str(numbers[0]),flush=True)
    print("SOURCE_HEX_TEMP_UNSAFE="+str(numbers[1]),flush=True)
    print("SOURCE_TEMP_CLEANUP=NOT_ATTEMPTED",flush=True)
    print("MIGRATION_STATE_MUTATED=NO",flush=True)
    return 0

if __name__=="__main__":
    try:raise SystemExit(run())
    except (Block,OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        print("BLOCKED="+(str(error) if type(error) is Block else type(error).__name__),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
