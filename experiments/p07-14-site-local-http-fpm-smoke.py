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
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def baseline():
    must(BASE.is_file() and not BASE.is_symlink() and
         git_blob(BASE)==EXPECTED_BASE,"BASELINE_BUNDLE_IDENTITY_CHANGED")
    spec=importlib.util.spec_from_file_location("p07_http_baseline",BASE)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
base=baseline()
DOMAIN=re.compile(r"[a-z0-9][a-z0-9.-]{1,150}[a-z0-9]$")
PHP=re.compile(r"[0-9]+\.[0-9]+$")
SOCKET=re.compile(r"unix:(/run/(?:php|php-fpm)/[a-zA-Z0-9_.-]+\.sock)")
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
    """Classify explicit FastCGI backends for a site's enabled Nginx files."""
    must(DOMAIN.fullmatch(domain) is not None,"VHOST_DOMAIN_UNSAFE")
    if not root.is_dir():return "MISSING",[]
    matches=[]
    for entry in sorted(root.iterdir()):
        if not entry.is_file():continue
        if entry.stat().st_size>1024*1024:continue
        try:raw=entry.read_text(encoding="utf8",errors="replace")
        except OSError:continue
        conf=re.sub(r"(?m)#.*$","",raw)
        names=re.findall(r"\bserver_name\s+([^;]+);",conf)
        if any(domain in ns.split() for ns in names):
            matches.append(conf)
    if not matches:return "NOT_FOUND",[]
    if len(matches)>3:return "AMBIGUOUS",[]
    endpoints=set()
    for conf in matches:
        for raw in re.findall(r"\bfastcgi_pass\s+([^;\s]+)\s*;",conf):
            if re.fullmatch(r"unix:/run/(?:php|php-fpm)/[A-Za-z0-9_.-]+\.sock",raw):
                endpoints.add(raw[5:])
            elif re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}",raw):
                port=int(raw.rsplit(":",1)[1])
                endpoints.add("tcp:"+raw if 1<=port<=65535 else "UNSUPPORTED")
            else:
                endpoints.add("UNSUPPORTED")
    return "FOUND",sorted(endpoints)

def fpm_pool_matches(version,user,endpoint,root=Path("/etc/php")):
    """Match the configured site-user pool to the exact Nginx listener."""
    must(PHP.fullmatch(version) and
         re.fullmatch(r"[a-z_][a-z0-9_-]{0,64}",user),
         "FPM_POOL_IDENTITY_INVALID")
    root=root/version/"fpm/pool.d"
    if not root.is_dir() or root.is_symlink():return False
    matches=0
    for conf in sorted(root.glob("*.conf")):
        if conf.is_symlink() or not conf.is_file() or conf.stat().st_size>262144:
            continue
        try:raw=conf.read_text(encoding="utf8",errors="replace")
        except OSError:continue
        raw=re.sub(r"(?m)^\s*[;#].*$","",raw)
        listens=re.findall(r"(?m)^\s*listen\s*=\s*([^\s;#]+)",raw)
        users=re.findall(r"(?m)^\s*user\s*=\s*([^\s;#]+)",raw)
        expected=endpoint[4:] if endpoint.startswith("tcp:") else endpoint
        if len(listens)==1 and len(users)==1 and listens[0]==expected and users[0]==user:
            matches+=1
    return matches==1

def tcp_listener_present(port,proc=Path("/proc/net/tcp")):
    """Kernel LISTEN socket observation; no connection or FPM invocation."""
    try:
        for row in proc.read_text(encoding="ascii").splitlines()[1:]:
            cols=row.split()
            if len(cols)<4:continue
            address,hexport=cols[1].split(":",1)
            if (address in ("0100007F","00000000")
                    and int(hexport,16)==port and cols[3]=="0A"):
                return True
    except (ValueError,OSError,IndexError):
        return False
    return False

def backend_status(endpoints,version,user):
    if not endpoints:return "NO_FASTCGI_DECLARED"
    if len(endpoints)!=1:return "AMBIGUOUS_FASTCGI_BACKENDS"
    endpoint=endpoints[0]
    if endpoint=="UNSUPPORTED":return "UNSUPPORTED_FASTCGI_BACKEND"
    if not fpm_pool_matches(version,user,endpoint):
        return "FPM_POOL_OR_SITE_USER_NOT_MATCHED"
    if endpoint.startswith("tcp:"):
        port=int(endpoint.rsplit(":",1)[1])
        return ("TCP_POOL_AND_LISTENER_CONFIRMED" if tcp_listener_present(port)
                else "TCP_FPM_LISTENER_NOT_FOUND")
    path=Path(endpoint)
    try:st=path.stat()
    except OSError:return "UNIX_FPM_SOCKET_NOT_FOUND"
    return ("UNIX_POOL_AND_SOCKET_CONFIRMED" if stat.S_ISSOCK(st.st_mode)
            else "UNIX_FPM_SOCKET_KIND_DIFFER")

def https_route(https):
    if re.fullmatch(r"HTTP_2[0-9]{2}",https):
        return "HTTPS_2XX"
    if re.fullmatch(r"HTTP_3[0-9]{2}",https):
        return "HTTPS_REDIRECT_UNVERIFIED"
    if https=="HTTP_ERROR_404":return "HTTPS_404"
    return "HTTPS_NOT_READY"
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
        msg=("HEAD / HTTP/1.1\r\nHost: "+domain+
             "\r\nUser-Agent: P07-CP2-Local-HEAD/1.0\r\n"
             "Accept: */*\r\nConnection: close\r\n\r\n")
        sock.sendall(msg.encode("ascii"))
        buf=b""
        while b"\r\n" not in buf and len(buf)<4096:
            part=sock.recv(1024)
            if not part:break
            buf+=part
        line=buf.split(b"\r\n",1)[0]
        match=re.fullmatch(rb"HTTP/1\.[01] ([0-9]{3})(?: [^\r\n]*)?",line)
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
        conf,endpoints=vhost(domain)
        backend=(backend_status(endpoints,version,src["site_user"])
                 if php and phpversion else
                 "NOT_APPLICABLE" if not php else "UNKNOWN")
        http=head_local(domain,80)
        https=head_local(domain,443,tls=True)
        route=https_route(https)
        ready=(match and conf=="FOUND" and
               ((php and phpversion and fpm=="ACTIVE" and
                 backend in ("TCP_POOL_AND_LISTENER_CONFIRMED",
                             "UNIX_POOL_AND_SOCKET_CONFIRMED")) or not php) and
               route=="HTTPS_2XX")
        full+=int(bool(ready))
        gaps+=int(not ready)
        print("SITE="+domain+" RUNTIME_MATCH="+("YES" if match else "NO")+
              " VHOST="+conf+" FPM="+fpm+" PHP_BACKEND="+backend+
              " HTTP80="+http+" HTTPS443="+https+" ROUTE="+route+
              " LOCAL_SMOKE="+("PASS_HTTP_HEAD_ONLY" if ready else "REVIEW"),flush=True)
    print("LOCAL_14_SITE_SMOKE_PASS="+str(full),flush=True)
    print("LOCAL_14_SITE_SMOKE_REVIEW="+str(gaps),flush=True)
    print("SOURCE_TARGET_APPLICATION_PARITY=NOT_VERIFIED",flush=True)
    print("PHP_DYNAMIC_EXECUTION=NOT_DIRECTLY_PROVEN",flush=True)
    print("FPM_POOL_AND_LISTENER=CONFIG_AND_KERNEL_OBSERVATION_ONLY",flush=True)
    print("HTTP_REDIRECTS_AND_404=REVIEW_NOT_PASS",flush=True)
    print("TLS_CERTIFICATE_VALIDITY=NOT_VERIFIED",flush=True)
    print("CRON_OR_PM2_ACTIVATED=NO",flush=True)
    print("SOURCE_SERVER_CONTACTED=NO",flush=True)
    print("DATABASE_SQL_WRITES_BY_PROBE=NONE",flush=True)
    print("DNS_WRITE=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0

# Three-site follow-up: inspect response headers, vhost directives, and root
# existence without printing private paths, query strings, cookies or secrets.
ROUTE_REVIEW=("domain.kewaro.com","infra.kewaro.com","press.kewaro.com")
def response_headers_local(domain,timeout=4):
    """Bounded CP2 loopback TLS HEAD. No redirect following or DNS resolution."""
    must(domain in ROUTE_REVIEW,"OUT_OF_SCOPE_ROUTE_HOST")
    sock=None
    try:
        sock=socket.create_connection(("127.0.0.1",443),timeout=timeout)
        sock.settimeout(timeout)
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname=False
        ctx.verify_mode=ssl.CERT_NONE
        sock=ctx.wrap_socket(sock,server_hostname=domain)
        sock.settimeout(timeout)
        req=("HEAD / HTTP/1.1\r\nHost: "+domain+
             "\r\nUser-Agent: P07-CP2-Route-Review/1.0\r\n"
             "Connection: close\r\n\r\n")
        sock.sendall(req.encode("ascii"))
        data=b""
        while b"\r\n\r\n" not in data and len(data)<16384:
            part=sock.recv(min(2048,16384-len(data)))
            if not part:break
            data+=part
        must(b"\r\n\r\n" in data and len(data)<16384,
             "ROUTE_HTTP_HEADERS_INCOMPLETE")
        headers=data.split(b"\r\n\r\n",1)[0].split(b"\r\n")
        code=re.match(rb"HTTP/1\.[01] ([0-9]{3})(?:\s|$)",headers[0])
        must(code is not None,"ROUTE_HTTP_STATUS_INVALID")
        selected={}
        for line in headers[1:]:
            if b":" not in line:continue
            key,value=line.split(b":",1)
            key=key.strip().lower()
            if key in (b"location",b"x-redirect-by") and key not in selected:
                selected[key.decode("ascii")]=value.strip().decode(
                    "utf8",errors="replace")[:2048]
        return int(code.group(1)),selected
    except (OSError,ssl.SSLError,TimeoutError):
        return 0,{}
    finally:
        if sock is not None:
            try:sock.close()
            except OSError:pass

def redirection_class(raw,domain):
    """Never output redirect query, credentials or arbitrary URL/path strings."""
    if not raw:return "NONE"
    from urllib.parse import urlsplit
    try:
        u=urlsplit(raw)
        host=(u.hostname or "").lower()
        if u.scheme and u.scheme.lower() not in ("http","https"):
            return "UNSAFE_SCHEME"
        if u.netloc and not u.scheme:return "NETWORK_PATH_REDIRECT"
        if u.username or u.password:return "CREDENTIAL_URL_REVIEW"
        if not host:host=domain
        if host==domain:scope="SAME_HOST"
        elif host.endswith(".kewaro.com") or host.endswith(".m3u8.one"):
            scope="RELATED_PUBLIC_DOMAIN"
        else:scope="OTHER_HOST"
        path=u.path.lower().strip("/")
        if not path:purpose="ROOT"
        elif any(part in ("login","signin","sign-in","auth","wp-login.php",
                            "admin","wp-admin","user","account")
                 for part in path.split("/")):purpose="AUTH_OR_ADMIN"
        else:purpose="OTHER_PATH"
        scheme=u.scheme.lower() if u.scheme else "RELATIVE"
        return scope+"_"+purpose+"_"+scheme.upper()
    except ValueError:
        return "INVALID_LOCATION"

def site_docroot_evidence(site):
    """Only read metadata under the target site user's /home; no file content."""
    user=site.get("site_user")
    path=site.get("document_root") or site.get("site_root")
    if not (isinstance(user,str) and re.fullmatch(r"[a-z_][a-z0-9_-]{0,64}",user)
            and isinstance(path,str)
            and path.startswith("/home/"+user+"/")
            and ".." not in Path(path).parts):
        return "UNVERIFIED","UNKNOWN","UNKNOWN"
    doc=Path(path)
    try:
        resolved=doc.resolve(strict=True)
        if not doc.is_dir() or not (resolved==Path("/home")/user
             or Path("/home")/user in resolved.parents):
            return "UNSAFE_OR_MISSING","UNKNOWN","UNKNOWN"
        names=("index.php","index.html","index.htm")
        found=[]
        for name in names:
            child=doc/name
            if child.is_file() and not child.is_symlink():
                found.append(name)
        wordpress="YES" if (doc/"wp-config.php").is_file() and not (
            doc/"wp-config.php").is_symlink() else "NO"
        return "DIRECTORY_PRESENT",("PRESENT" if found else "NONE"),wordpress
    except (OSError,RuntimeError,ValueError):
        return "UNVERIFIED","UNKNOWN","UNKNOWN"

def nginx_route_evidence(domain,root=VHOST_DIR):
    """Read only bounded nginx files; never dump their content or host paths."""
    must(domain in ROUTE_REVIEW,"OUT_OF_SCOPE_NGINX_DOMAIN")
    if not root.is_dir():return "VHOST_CONFIG_MISSING","UNKNOWN","UNKNOWN"
    matches=[]
    for f in sorted(root.iterdir()):
        try:
            if not f.is_file() or f.stat().st_size>1048576:continue
            raw=f.read_text(encoding="utf8",errors="replace")
        except OSError:continue
        text=re.sub(r"(?m)#.*$","",raw)
        names=re.findall(r"\bserver_name\s+([^;]+);",text)
        if any(domain in record.split() for record in names):
            matches.append(text)
    if not matches:return "VHOST_NOT_FOUND","UNKNOWN","UNKNOWN"
    config="\n".join(matches)
    has_root=bool(re.search(r"\broot\s+[^;]+;",config))
    has_try=bool(re.search(r"\btry_files\s+[^;]+;",config))
    has_rewrite=bool(re.search(r"\brewrite\s+[^;]+;",config))
    has_proxy=bool(re.search(r"\bproxy_pass\s+[^;]+;",config))
    return ("VHOST_FILES_"+str(len(matches)),
            "YES" if has_root else "NO",
            "TRY_FILES_"+("YES" if has_try else "NO")+
            "_REWRITE_"+("YES" if has_rewrite else "NO")+
            "_PROXY_"+("YES" if has_proxy else "NO"))

def diagnose_three_routes():
    must(os.geteuid()==0,"CP2_ROOT_REQUIRED")
    must(sys.argv[1:]==["--diagnose-only-three-review-routes"],
         "EXPLICIT_THREE_ROUTE_DIAG_ARGUMENT_REQUIRED")
    sites=staged_sites()
    must(set(ROUTE_REVIEW)<=set(sites),"THREE_ROUTE_STAGE_SCOPE_CHANGED")
    bydomain=inventory()
    print("PROBE=CP2_THREE_SITE_ROUTE_DIAGNOSIS",flush=True)
    print("SCOPE=domain.kewaro.com,infra.kewaro.com,press.kewaro.com",flush=True)
    print("HTTPS_TARGET=127.0.0.1:443_ONLY",flush=True)
    print("HTTP_METHOD=HEAD_NO_REDIRECT_FOLLOW",flush=True)
    print("RESPONSE_COOKIES_QUERIES_AND_PRIVATE_PATHS=NOT_DISPLAYED",flush=True)
    for domain in ROUTE_REVIEW:
        site=sites[domain]
        panel=bydomain.get(domain,[])
        must(len(panel)==1 and panel[0].get("site_user")==site.get("site_user"),
             "THREE_SITE_PANEL_USER_OR_INVENTORY_CHANGED")
        source_doc=site_docroot_evidence(site)
        panel_doc=site_docroot_evidence(panel[0])
        code,headers=response_headers_local(domain)
        destination=redirection_class(headers.get("location"),domain)
        redirect_by="YES" if "x-redirect-by" in headers else "NO"
        vhost,ng_root,route=nginx_route_evidence(domain)
        print("SITE="+domain+" HTTPS_STATUS="+str(code)+
              " REDIRECT_CLASS="+destination+
              " APP_REDIRECT_HEADER="+redirect_by+
              " NGINX_CONFIG="+vhost+" NGINX_ROOT="+ng_root+
              " NGINX_RULES="+route+
              " STAGED_DOCROOT="+source_doc[0]+
              " STAGED_INDEX="+source_doc[1]+
              " CP2_DOCROOT="+panel_doc[0]+
              " CP2_INDEX="+panel_doc[1]+
              " CP2_WP_CONFIG="+panel_doc[2],flush=True)
    print("DIAGNOSTIC_ONLY=NO_SITE_CONFIG_OR_DATABASE_WRITES",flush=True)
    print("APPLICATION_CAUSE=REQUIRES_TARGETED_REVIEW",flush=True)
    print("OLD_SERVER_CONTACTED=NO",flush=True)
    print("CRON_OR_PM2_ACTIVATED=NO",flush=True)
    print("DNS_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(
            diagnose_three_routes() if sys.argv[1:]==[
                "--diagnose-only-three-review-routes"] else probe())
    except Block as e:
        print("BLOCKED="+str(e),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
    except Exception:
        print("BLOCKED=CP2_HTTP_FPM_SMOKE_UNVERIFIED",flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
