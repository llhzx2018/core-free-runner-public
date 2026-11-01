#!/usr/bin/env python3
"""CP2-only 14-site bounded HTTP HEAD + PHP-FPM live-readiness probe.

Does not connect to old VPS, follow redirects, write databases, activate cron,
restart services or change DNS. HEAD requests may invoke web application
handlers and access logs: this is a local functional probe, NOT a pure filesystem
read-only scan, nor final application or source-target parity acceptance.
"""
from __future__ import annotations
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import subprocess
import sys

sys.dont_write_bytecode=True
BASE=Path(__file__).with_name("p07-17-site-staged-local-evidence.py")
EXPECTED_BASE="fe9387cadaa987faf11863ee1524b30e0a6aadbc"
class Block(Exception):pass
def must(ok,reason):
    if not ok:raise Block(reason)
def git_blob(p):
    b=p.read_bytes()
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\\0"+b).hexdigest()
def baseline():
    must(BASE.is_file() and not BASE.is_symlink() and
         git_blob(BASE)==EXPECTED_BASE,"BASELINE_BUNDLE_IDENTITY_CHANGED")
    spec=importlib.util.spec_from_file_location("p07_http_baseline",BASE)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
base=baseline()
DOMAIN=re.compile(r"[a-z0-9][a-z0-9.-]{1,150}[a-z0-9]$")
PHP=re.compile(r"[0-9]+\\.[0-9]+$")
SOCKET=re.compile(r"unix:(/run/(?:php|php-fpm)/[a-zA-Z0-9_.-]+\\.sock)")
VHOST_DIR=Path("/etc/nginx/sites-enabled")
def service(name):
    try:
        x=subprocess.run(["systemctl","is-active",name],check=False,
            capture_output=True,text=True,timeout=5,stdin=subprocess.DEVNULL)
        return "ACTIVE" if x.returncode==0 and x.stdout.strip()=="active" else "NOT_ACTIVE"
    except (OSError,subprocess.SubprocessError):return "UNKNOWN"
def staged_sites():
    seen={}
    states=[]
    for label,mid,n in base.JOBS:
        state=base.secure_state(base.ROOT/mid/"state.json")
        must(state.get("schema")==base.SCHEMA and
             state.get("migration_id")==mid and state.get("status")=="PREPARE_FAILED"
             and type(state.get("sites")) is list and len(state["sites"])==n,
             "MIGRATION_STATE_CHANGED")
        for flag in ("source_runtime_frozen","target_runtime_activated",
                     "dns_changed_by_p07","source_delete_allowed",
                     "existing_target_overwrite_allowed"):
            must(state.get(flag) is False,"MIGRATION_PROTECTION_CHANGED")
        for row in state["sites"]:
            must(type(row) is dict and type(row.get("domain")) is str
                 and DOMAIN.fullmatch(row["domain"]),"INVALID_SITE_DOMAIN")
            seen[row["domain"]]=(label,row)
        states.append(state)
    must(states[1].get("partial_parent_migration_id")==base.JOBS[0][1]
         and states[2].get("partial_parent_migration_id")==base.JOBS[1][1],
         "MIGRATION_PARENT_CHAIN_CHANGED")
    must(all(s.get("target_server_identity")==states[0].get("target_server_identity")
             for s in states[1:]),"CP2_TARGET_IDENTITY_CHANGED")
    staged={d for d,(label,s) in seen.items() if s.get("stage_status")=="PULLED_STAGED"}
    pending={d for d,(label,s) in seen.items() if s.get("stage_status")=="PENDING"}
    must(staged==base.EXPECTED_STAGED and pending==base.EXPECTED_PENDING,
         "14_SITE_SCOPE_CHANGED")
    return {d:seen[d][1] for d in staged}
def inventory():
    sys.path.insert(0,"/opt/vf-server-ops/lib")
    import inventory as cp
    m=cp.build_manifest(Path("/"))
    must(type(m) is dict and type(m.get("sites")) is list,"CP2_INVENTORY_MISSING")
    out={}
    for s in m["sites"]:
        if type(s) is dict and type(s.get("domain")) is str:
            out.setdefault(s["domain"],[]).append(s)
    return out
def vhost(domain,root=VHOST_DIR):
    """Read enabled Nginx configs only, ignoring comments; no config execution."""
    must(DOMAIN.fullmatch(domain) is not None,"VHOST_DOMAIN_UNSAFE")
    if not root.is_dir():return "MISSING",[]
    matches=[]
    for entry in sorted(root.iterdir()):
        if not entry.is_file():continue
        if entry.stat().st_size>1024*1024:continue
        try:raw=entry.read_text(encoding="utf8",errors="replace")
        except OSError:continue
        conf=re.sub(r"(?m)#.*$","",raw)
        names=re.findall(r"\\bserver_name\\s+([^;]+);",conf)
        if any(domain in ns.split() for ns in names):
            matches.append(conf)
    if not matches:return "NOT_FOUND",[]
    if len(matches)>3:return "AMBIGUOUS",[]
    upstreams=[]
    for conf in matches:
        upstreams.extend(SOCKET.findall(conf))
    return "FOUND",sorted(set(upstreams))
def socket_status(paths):
    if not paths:return "NO_UNIX_SOCKET_DECLARED"
    result=[]
    for path in paths:
        try:st=Path(path).stat()
        except OSError:return "DECLARED_SOCKET_MISSING"
        if not stat.S_ISSOCK(st.st_mode):return "DECLARED_SOCKET_NOT_SOCKET"
        result.append(path)
    return "DECLARED_UNIX_SOCKETS_PRESENT"
def head_local(domain,port,tls=False,timeout=3):
    """Always connect to literal loopback IP; SNI and Host equal fixed scoped domain."""
    must(DOMAIN.fullmatch(domain) is not None and port in (80,443),
         "HTTP_DESTINATION_UNSAFE")
    sock=None
    try:
        sock=socket.create_connection(("127.0.0.1",port),timeout=timeout)
        sock.settimeout(timeout)
        if tls:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname=False
            context.verify_mode=ssl.CERT_NONE
            sock=context.wrap_socket(sock,server_hostname=domain)
            sock.settimeout(timeout)
        msg=("HEAD / HTTP/1.1\\r\\nHost: "+domain+
             "\\r\\nUser-Agent: P07-CP2-Local-HEAD/1.0\\r\\n"
             "Accept: */*\\r\\nConnection: close\\r\\n\\r\\n")
        sock.sendall(msg.encode("ascii"))
        buf=b""
        while b"\\r\\n" not in buf and len(buf)<4096:
            part=sock.recv(1024)
            if not part:break
            buf+=part
        line=buf.split(b"\\r\\n",1)[0]
        match=re.fullmatch(rb"HTTP/1\\.[01] ([0-9]{3})(?: [^\\r\\n]*)?",line)
        if not match:return "INVALID_HTTP_RESPONSE"
        status=int(match.group(1))
        if 200<=status<400:return "HTTP_"+str(status)
        if status in (401,403):return "ACCESS_PROTECTED_"+str(status)
        if status==405:return "HEAD_NOT_ALLOWED_405"
        return "HTTP_ERROR_"+str(status)
    except (OSError,ssl.SSLError,TimeoutError):
        return "LOCAL_CONNECT_OR_TLS_FAILED"
    finally:
        if sock is not None:
            try:sock.close()
            except OSError:pass
def probe():
    must(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    must(sys.argv[1:]==["--probe-only-14-staged-sites"],
         "EXPLICIT_LOCAL_HTTP_PROBE_ARGUMENT_REQUIRED")
    sites=staged_sites()
    bydomain=inventory()
    print("PROBE=CP2_LOCAL_14_SITE_HTTP_HEAD_PHP_FPM",flush=True)
    print("NGINX_SERVICE="+service("nginx"),flush=True)
    print("HTTP_DESTINATION=127.0.0.1_ONLY",flush=True)
    print("HTTP_METHOD=HEAD_ONLY_NO_REDIRECTS",flush=True)
    print("TLS_CERTIFICATE_VALIDATION=NOT_TESTED",flush=True)
    full=0
    gaps=0
    for domain in sorted(sites):
        src=sites[domain]
        cp=bydomain.get(domain,[])
        must(len(cp)==1 and src.get("site_user")==cp[0].get("site_user"),
             "CP2_SITE_USER_OR_INVENTORY_UNVERIFIED")
        sr=src.get("runtime")
        tr=cp[0].get("runtime")
        match=(type(sr) is dict and type(tr) is dict
               and sr.get("type")==tr.get("type") and
               sr.get("version")==tr.get("version"))
        kind=sr.get("type") if type(sr) is dict else None
        version=sr.get("version") if type(sr) is dict else None
        php=(kind=="php")
        phpversion=(type(version) is str and PHP.fullmatch(version) is not None)
        fpm=(service("php"+version+"-fpm") if php and phpversion else
             "NOT_APPLICABLE" if not php else "UNKNOWN")
        conf,socks=vhost(domain)
        unix=socket_status(socks) if php else "NOT_APPLICABLE"
        http=head_local(domain,80)
        https=head_local(domain,443,tls=True)
        http_ok=http.startswith(("HTTP_2","HTTP_3","ACCESS_PROTECTED"))
        https_ok=https.startswith(("HTTP_2","HTTP_3","ACCESS_PROTECTED"))
        ready=(match and conf=="FOUND" and
               ((php and phpversion and fpm=="ACTIVE" and
                 unix=="DECLARED_UNIX_SOCKETS_PRESENT") or not php) and
               (http_ok or https_ok))
        full+=int(bool(ready))
        gaps+=int(not ready)
        print("SITE="+domain+" RUNTIME_MATCH="+("YES" if match else "NO")+
              " VHOST="+conf+" FPM="+fpm+" PHP_BACKEND="+unix+
              " HTTP80="+http+" HTTPS443="+https+
              " LOCAL_SMOKE="+("PASS" if ready else "REVIEW"),flush=True)
    print("LOCAL_14_SITE_SMOKE_PASS="+str(full),flush=True)
    print("LOCAL_14_SITE_SMOKE_REVIEW="+str(gaps),flush=True)
    print("SOURCE_TARGET_APPLICATION_PARITY=NOT_VERIFIED",flush=True)
    print("PHP_DYNAMIC_EXECUTION=NOT_DIRECTLY_PROVEN",flush=True)
    print("TLS_CERTIFICATE_VALIDITY=NOT_VERIFIED",flush=True)
    print("CRON_OR_PM2_ACTIVATED=NO",flush=True)
    print("SOURCE_SERVER_CONTACTED=NO",flush=True)
    print("DATABASE_SQL_WRITES_BY_PROBE=NONE",flush=True)
    print("DNS_WRITE=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0
if __name__=="__main__":
    try:raise SystemExit(probe())
    except Block as e:
        print("BLOCKED="+str(e),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=CP2_HTTP_FPM_SMOKE_UNVERIFIED",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
