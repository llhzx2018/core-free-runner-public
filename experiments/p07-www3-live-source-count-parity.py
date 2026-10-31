#!/usr/bin/env python3
"""P07 www3: old live-source vs restored CP2 read-only per-table COUNT advisory.

The old website is not frozen. Matching counts are not snapshot/content parity,
and differing counts may reflect legitimate live writes after source export.
No SQL/table names, credentials, row contents, or business data are printed.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import re
import shlex
import sys

sys.dont_write_bytecode = True
READBACK = Path(__file__).with_name("p07-www3-restored-readback.py")
try:
    data = READBACK.read_bytes()
except OSError:
    print("BLOCKED=VERIFIED_READBACK_BUNDLE_MISSING")
    raise SystemExit(13)
blob = hashlib.sha1(b"blob " + str(len(data)).encode() + bytes([0]) + data).hexdigest()
if blob != "2f0630b76b16d0e6dec64cbcb32f4cbaeabb7de3":
    print("BLOCKED=READBACK_BUNDLE_VERSION_CHANGED")
    raise SystemExit(13)
spec = importlib.util.spec_from_file_location("p07_www3_readback", READBACK)
readback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readback)
base = readback.base

REMOTE = r'''
import hashlib,os,re,shlex,shutil,subprocess,sys
from pathlib import Path
import inventory
domain,db=sys.argv[1:]
if domain!="www3.m3u8.one" or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}",db):
    sys.exit(11)
manifest=inventory.build_manifest(Path("/"))
sites=[s for s in manifest.get("sites",[]) if isinstance(s,dict) and s.get("domain")==domain]
if len(sites)!=1 or sites[0].get("mysql_databases")!=[db]:
    sys.exit(12)
env=os.environ.copy()
env["SUDO_USER"]="root"
try:
    p=subprocess.run(["clpctl","db:show:master-credentials"],stdin=subprocess.DEVNULL,
                     stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=20,
                     env=env,check=False)
except Exception:
    sys.exit(13)
if p.returncode!=0: sys.exit(13)
parsed=None
for line in p.stdout.splitlines():
    m=re.search(r"(?:^|\s)(?:/usr/bin/)?(?:mysql|mariadb)\s+",line)
    if not m: continue
    try: parts=shlex.split(line[m.start():].strip().rstrip("|").strip())
    except ValueError: continue
    opts={}
    for arg in parts[1:]:
        for key,name in (("-h","host"),("-P","port"),("-u","user"),("-p","password")):
            if arg.startswith(key) and len(arg)>2: opts[name]=arg[2:]
    if opts.get("host") not in ("127.0.0.1","localhost"): continue
    if not opts.get("port","").isdigit() or not 1<=int(opts["port"])<=65535: continue
    if not re.fullmatch("[A-Za-z0-9._-]{1,64}",opts.get("user","")): continue
    if not opts.get("password") or len(opts["password"])>256: continue
    if any(c in opts["password"] for c in ("\r","\n","\0")): continue
    parsed=opts;break
if parsed is None: sys.exit(14)
client=shutil.which("mariadb") or shutil.which("mysql")
if not client:sys.exit(15)
env["MYSQL_PWD"]=parsed["password"]
args=[client,"--no-defaults","--protocol=tcp","--host="+parsed["host"],
      "--port="+parsed["port"],"--user="+parsed["user"],
      "--batch","--skip-column-names","--default-character-set=utf8mb4"]
def query(sql,timeout=80):
    try:
        result=subprocess.run(args+["--execute",sql],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,timeout=timeout,check=False)
    except Exception: sys.exit(16)
    if result.returncode or len(result.stdout)>1048576:sys.exit(17)
    try:return result.stdout.decode("utf-8","strict").strip()
    except UnicodeError:sys.exit(18)
def number(s):
    if not re.fullmatch(r"[0-9]{1,16}",s):sys.exit(19)
    v=int(s)
    if v>10**15:sys.exit(20)
    return v
qdb="'"+db+"'"
names=query("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA="+qdb+
            " AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",90)
tables=names.splitlines() if names else []
if not 0<len(tables)<=1000 or len(set(tables))!=len(tables):sys.exit(21)
if not all(re.fullmatch(r"[A-Za-z0-9_]{1,64}",x) for x in tables):sys.exit(22)
cols=number(query("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA="+qdb,90))
if cols<len(tables):sys.exit(23)
count=0;nonempty=0
finger=hashlib.sha256()
for table in tables:
    quoted=chr(96)+db+chr(96)+"."+chr(96)+table+chr(96)
    n=number(query("SELECT COUNT(*) FROM "+quoted,120))
    count+=n;nonempty+=int(n>0)
    finger.update(table.encode("ascii")+bytes([0])+str(n).encode()+bytes([10]))
print("LIVE_SOURCE_SITE_BINDING=PASS")
print("LIVE_SOURCE_TABLES="+str(len(tables)))
print("LIVE_SOURCE_COLUMNS="+str(cols))
print("LIVE_SOURCE_TOTAL_ROWS="+str(count))
print("LIVE_SOURCE_NONEMPTY_TABLES="+str(nonempty))
print("LIVE_SOURCE_ROWCOUNT_FINGERPRINT="+finger.hexdigest())
'''

class Blocked(Exception):
    pass

def parse_remote(output):
    allowed={
        "LIVE_SOURCE_SITE_BINDING":r"PASS",
        "LIVE_SOURCE_TABLES":r"[0-9]{1,4}",
        "LIVE_SOURCE_COLUMNS":r"[0-9]{1,6}",
        "LIVE_SOURCE_TOTAL_ROWS":r"[0-9]{1,16}",
        "LIVE_SOURCE_NONEMPTY_TABLES":r"[0-9]{1,4}",
        "LIVE_SOURCE_ROWCOUNT_FINGERPRINT":r"[0-9a-f]{64}",
    }
    found={}
    for line in output.splitlines():
        if "=" not in line:
            raise Blocked("SOURCE_DIAGNOSTIC_OUTPUT_UNEXPECTED")
        key,value=line.split("=",1)
        if key in found or key not in allowed or not re.fullmatch(allowed[key],value):
            raise Blocked("SOURCE_DIAGNOSTIC_OUTPUT_UNEXPECTED")
        found[key]=value
    if set(found)!=set(allowed):
        raise Blocked("SOURCE_DIAGNOSTIC_OUTPUT_INCOMPLETE")
    return found

def compare():
    if sys.argv[1:]!=["--compare-current-source-counts-read-only"]:
        raise Blocked("EXPLICIT_COMPARISON_ARG_REQUIRED")
    db,user,password,source_ddl=readback.preflight()
    t_tables,t_cols,t_rows,t_nonempty,t_finger=readback.database_readback(db,user,password)
    if t_tables!=source_ddl:
        raise Blocked("TARGET_SOURCE_DDL_COUNT_CHANGED")
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import server_migration_pull as migration
    state=readback.read_private(base.STATE)
    site=state["sites"][1]
    dbs=site.get("mysql_databases")
    if type(dbs) is not list or len(dbs)!=1 or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}",dbs[0]):
        raise Blocked("SOURCE_DATABASE_BINDING_UNVERIFIED")
    if migration.target_identity()!=state.get("target_server_identity"):
        raise Blocked("TARGET_IDENTITY_CHANGED")
    cmd=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
                    "PYTHONPATH="+base.SOURCE_RUNTIME+"/lib",
                    "python3","-B","-c",REMOTE,base.DOMAIN,dbs[0]])
    try:
        proc=migration.source_remote(state["source"],cmd,timeout=1200,check=False)
    except Exception:
        raise Blocked("OLD_SERVER_READ_ONLY_CONNECTION_FAILED") from None
    if proc.returncode!=0:
        raise Blocked("OLD_SERVER_READ_ONLY_QUERY_FAILED")
    source=parse_remote(proc.stdout)
    matched=(int(source["LIVE_SOURCE_TABLES"])==t_tables
             and int(source["LIVE_SOURCE_COLUMNS"])==t_cols
             and int(source["LIVE_SOURCE_TOTAL_ROWS"])==t_rows
             and int(source["LIVE_SOURCE_NONEMPTY_TABLES"])==t_nonempty
             and source["LIVE_SOURCE_ROWCOUNT_FINGERPRINT"]==t_finger)
    print("CURRENT_SOURCE_SITE_BINDING=PASS")
    print("CURRENT_SOURCE_TABLES="+source["LIVE_SOURCE_TABLES"])
    print("CURRENT_SOURCE_COLUMNS="+source["LIVE_SOURCE_COLUMNS"])
    print("CURRENT_SOURCE_ROWS="+source["LIVE_SOURCE_TOTAL_ROWS"])
    print("RESTORED_TARGET_TABLES="+str(t_tables))
    print("RESTORED_TARGET_COLUMNS="+str(t_cols))
    print("RESTORED_TARGET_ROWS="+str(t_rows))
    print("LIVE_SOURCE_VS_RESTORED_COUNT_PARITY="+("MATCH" if matched else "DIFFER"))
    print("LIVE_SOURCE_EQUALS_ORIGINAL_EXPORT_SNAPSHOT=NOT_VERIFIED")
    print("SOURCE_TARGET_ROW_CONTENT_PARITY=NOT_VERIFIED")
    print("OLD_SERVER_DATABASE_WRITES=NONE")
    print("CP2_DATABASE_WRITES=NONE")
    print("CUTOVER_ALLOWED=NO")
    return 0

if __name__=="__main__":
    try:raise SystemExit(compare())
    except (Blocked,readback.Blocked,base.Stop) as exc:
        print("BLOCKED="+str(exc))
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=UNVERIFIED_READ_ONLY_COMPARISON")
        raise SystemExit(13) from None
