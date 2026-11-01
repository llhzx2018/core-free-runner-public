#!/usr/bin/env python3
"""P07 two pending migration sites: bounded read-only SQL value multiset worker.

Local execution on old VPS or CP2. No database writes and no raw data in output.
The two independent read-only transactions occur at different times: MATCH is
not proof that source-export snapshot and current source are identical.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile

TABLE_CAP=1000
COLUMN_CAP=200
ROW_CAP=1000000
ROW_BYTES_CAP=16*1024*1024
OUTPUT_BYTES_CAP=1024*1024*1024

def block(code):
    print("BLOCKED="+code,flush=True)
    raise SystemExit(13)

def private(path):
    try: info=path.lstat()
    except OSError: block("PRIVATE_FILE_MISSING")
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o077:
        block("PRIVATE_FILE_UNSAFE")
    return path

def source_auth(domain,db):
    if domain not in ("unzip.kewaro.com","ilovem3u8.kewaro.com") or not re.fullmatch("[A-Za-z0-9._-]{1,64}",db):
        block("SOURCE_IDENTITY_INVALID")
    import inventory
    m=inventory.build_manifest(Path("/"))
    sites=[x for x in m.get("sites",[]) if isinstance(x,dict) and x.get("domain")==domain]
    if len(sites)!=1 or sites[0].get("mysql_databases")!=[db]:
        block("SOURCE_SITE_DATABASE_BINDING_INVALID")
    env=os.environ.copy()
    env["SUDO_USER"]="root"
    try:
        cp=subprocess.run(["clpctl","db:show:master-credentials"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            text=True,timeout=20,env=env,check=False)
    except (OSError,subprocess.SubprocessError,UnicodeError):
        block("SOURCE_CLOUDPANEL_MASTER_UNAVAILABLE")
    if cp.returncode!=0: block("SOURCE_CLOUDPANEL_MASTER_UNAVAILABLE")
    for line in cp.stdout.splitlines():
        m=re.search(r"(?:^|\s)(?:/usr/bin/)?(?:mysql|mariadb)\s+",line)
        if not m:continue
        try: args=shlex.split(line[m.start():].strip().rstrip("|").strip())
        except ValueError:continue
        values={}
        for a in args[1:]:
            for flag,key in (("-h","host"),("-P","port"),("-u","user"),("-p","password")):
                if a.startswith(flag) and len(a)>2:values[key]=a[2:]
        if (values.get("host") in ("127.0.0.1","localhost")
                and values.get("port","").isdigit()
                and 1<=int(values["port"])<=65535
                and re.fullmatch("[A-Za-z0-9._-]{1,64}",values.get("user",""))
                and 1<=len(values.get("password",""))<=256
                and not any(c in values["password"] for c in ("\r","\n","\0"))):
            return values["host"],int(values["port"]),values["user"],values["password"]
    block("SOURCE_MASTER_CONNECT_FORMAT_UNVERIFIED")

def target_auth(domain,db):
    # Both pending targets are registered CloudPanel databases, unlike the
    # separately restored www3 scratch. Never fall back to raw root socket.
    return source_auth(domain,db)

def sql_read(args,query,timeout=60):
    try:
        p=subprocess.run(args+["--execute",query],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=timeout,check=False)
    except (OSError,subprocess.SubprocessError):
        block("SQL_METADATA_QUERY_UNAVAILABLE")
    if p.returncode!=0 or len(p.stdout)>1048576:
        block("SQL_METADATA_QUERY_FAILED")
    try:return p.stdout.decode("ascii","strict").strip()
    except UnicodeError:block("SQL_METADATA_NONASCII")

def schema(args,db):
    lit="'"+db+"'"
    names=sql_read(args,"SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA="
                   +lit+" AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",90)
    tables=sorted(names.splitlines()) if names else []
    if not 0<len(tables)<=TABLE_CAP or len(set(tables))!=len(tables):
        block("TABLE_LIST_UNVERIFIED")
    if not all(re.fullmatch("[A-Za-z0-9_]{1,64}",v) for v in tables):
        block("TABLE_IDENTIFIER_UNSUPPORTED")
    values=sql_read(args,"SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA="
            +lit+" ORDER BY TABLE_NAME,ORDINAL_POSITION",90)
    cols={x:[] for x in tables}
    for line in values.splitlines():
        pair=line.split("\t")
        if len(pair)!=2 or pair[0] not in cols:
            block("COLUMN_METADATA_UNPROVEN")
        if not re.fullmatch("[A-Za-z0-9_]{1,64}",pair[1]):
            block("COLUMN_IDENTIFIER_UNSUPPORTED")
        cols[pair[0]].append(pair[1])
    if any(not 0<len(v)<=COLUMN_CAP or len(v)!=len(set(v)) for v in cols.values()):
        block("COLUMN_COUNT_UNVERIFIED")
    # Stable cross-engine collation-independent field order.
    return tables,{t:sorted(cols[t]) for t in tables}

def fingerprint(args,db,tables,cols):
    with tempfile.TemporaryFile(mode="w+b") as script:
        script.write(b"SET SESSION time_zone='+00:00';\n")
        script.write(b"SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;\n")
        script.write(b"START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;\n")
        for i,table in enumerate(tables):
            expressions=[]
            for col in cols[table]:
                ident=chr(96)+col+chr(96)
                expressions.append("IF("+ident+" IS NULL,'N',CONCAT('V',HEX(CAST("+
                                   ident+" AS BINARY))))")
            ref=chr(96)+db+chr(96)+"."+chr(96)+table+chr(96)
            query="SELECT "+str(i)+","+(",".join(expressions))+" FROM "+ref+";\n"
            script.write(query.encode("ascii"))
        script.write(b"ROLLBACK;\n")
        script.flush()
        script.seek(0)
        cli=shutil.which("mariadb") or shutil.which("mysql")
        if not cli:block("SQL_CLIENT_UNAVAILABLE")
        # timeout caps the whole reader even if the server hangs before stdout.
        tool=shutil.which("timeout")
        if not tool:block("PROCESS_TIMEOUT_UNAVAILABLE")
        command=[tool,"1800",cli,*args,"--raw","--binary-mode",
                 "--default-character-set=utf8mb4"]
        try:
            process=subprocess.Popen(command,stdin=script,stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL)
        except OSError:
            block("TRANSACTION_QUERY_UNAVAILABLE")
        rows=[[] for _ in tables]
        # Add bounded, order-independent per-column value distribution checks.
        # This local diagnostic hashes cells and never emits their raw values.
        cell_sums=[[[0,0] for _ in cols[t]] for t in tables]
        modulus=(1<<256)-1
        total=0
        scanned=0
        try:
            assert process.stdout is not None
            while True:
                line=process.stdout.readline(ROW_BYTES_CAP+1)
                if not line:break
                scanned+=len(line)
                if scanned>OUTPUT_BYTES_CAP or len(line)>ROW_BYTES_CAP or not line.endswith(b"\n"):
                    block("ROW_STREAM_SIZE_LIMIT")
                bits=line[:-1].split(b"\t")
                if len(bits)<2 or not re.fullmatch(rb"[0-9]{1,4}",bits[0]):
                    block("ROW_STREAM_FORMAT_INVALID")
                ordinal=int(bits[0])
                if ordinal>=len(tables) or len(bits)!=len(cols[tables[ordinal]])+1:
                    block("ROW_COLUMNS_MISMATCH")
                if not all(bit==b"N" or (bit.startswith(b"V") and
                    len(bit[1:])%2==0 and re.fullmatch(rb"[A-Fa-f0-9]*",bit[1:]))
                    for bit in bits[1:]):
                    block("ROW_VALUE_ENCODING_UNVERIFIED")
                total+=1
                if total>ROW_CAP:block("ROW_COUNT_CAP")
                rows[ordinal].append(hashlib.sha256(b"\t".join(bits[1:])).digest())
                for j,value in enumerate(bits[1:]):
                    digest=int.from_bytes(hashlib.sha256(value).digest(),"big")
                    aggregate=cell_sums[ordinal][j]
                    aggregate[0]=(aggregate[0]+digest)&modulus
                    aggregate[1]^=digest
            code=process.wait(timeout=20)
            if code!=0:block("READ_ONLY_TRANSACTION_FAILED")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=20)
            if process.stdout:
                process.stdout.close()
    answers={}
    for table,columns,row_hashes,aggregates in zip(
            tables,(cols[t] for t in tables),rows,cell_sums):
        identity=hashlib.sha256(table.encode("ascii")).hexdigest()
        head=hashlib.sha256(b"\x00".join(v.encode("ascii") for v in columns)).digest()
        digest=hashlib.sha256(head+b"".join(sorted(row_hashes))).hexdigest()
        cell_signatures={}
        for name,(total_hash,xor_hash) in zip(columns,aggregates):
            col_id=hashlib.sha256(name.encode("ascii")).hexdigest()
            if col_id in cell_signatures:block("COLUMN_HASH_COLLISION")
            sig=hashlib.sha256(total_hash.to_bytes(32,"big")+
                               xor_hash.to_bytes(32,"big")+
                               len(row_hashes).to_bytes(8,"big")).hexdigest()
            cell_signatures[col_id]=sig
        answers[identity]=[len(row_hashes),digest,
                           hashlib.sha256(head).hexdigest(),cell_signatures]
    return answers,total

def main():
    if os.geteuid()!=0 or len(sys.argv)!=4 or sys.argv[1] not in ("source","target"):
        block("EXPLICIT_ROOT_MODE_DOMAIN_DATABASE_REQUIRED")
    mode,domain,db=sys.argv[1:]
    if mode=="source":host,port,user,pw=source_auth(domain,db)
    else:host,port,user,pw=target_auth(domain,db)
    cli=shutil.which("mariadb") or shutil.which("mysql")
    if not cli:block("SQL_CLIENT_UNAVAILABLE")
    with tempfile.TemporaryDirectory(prefix="p07-content-",dir="/root") as directory:
        cfg=Path(directory)/"client.cnf"
        fd=os.open(cfg,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        escaped=lambda v:v.replace(chr(92),chr(92)+chr(92)).replace('"',chr(92)+'"')
        with os.fdopen(fd,"w") as handle:
            handle.write('[client]'+chr(10)+'user="'+escaped(user)+'"'+chr(10)+
                         'password="'+escaped(pw)+'"'+chr(10))
        # Scoped local secret file never leaves this host and is unlinked on exit.
        args=[cli,"--defaults-extra-file="+str(cfg),"--protocol=tcp",
              "--host="+host,"--port="+str(port),
              "--batch","--skip-column-names"]
        tables,cols=schema(args,db)
        rows,total=fingerprint(args[1:],db,tables,cols)
    print("MODE="+mode.upper(),flush=True)
    print("SCANNED_TABLES="+str(len(tables)),flush=True)
    print("SCANNED_COLUMNS="+str(sum(len(v) for v in cols.values())),flush=True)
    print("SCANNED_ROWS="+str(total),flush=True)
    print("ROW_FINGERPRINTS="+json.dumps(rows,sort_keys=True,separators=(",",":")),flush=True)
    print("READ_ONLY_TRANSACTION=YES",flush=True)
    print("CONTENT_FINGERPRINT_NOT_SNAPSHOT_PARITY=YES",flush=True)

if __name__=="__main__":
    try:main()
    except SystemExit:raise
    except Exception:block("UNVERIFIED_CONTENT_WORKER_STATE")
