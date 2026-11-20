#!/usr/bin/env python3
"""ONE-OFF synthetic localhost metadata: authentic 607b-origin v013 candidate.
Never forwards to GitHub, never includes a real PAT or private product code.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import ssl
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import zipfile

if (len(sys.argv) != 3 or sys.argv[1] not in ("prepare", "serve")
    or os.getenv("GITHUB_ACTIONS") != "true"
    or os.getenv("P08_ISOLATED_INSTALL_TEST") != "YES"):
    raise SystemExit("P08_607B_PROXY_ISOLATED_ONLY")
mode, name = sys.argv[1:]
temp = Path(os.environ["RUNNER_TEMP"]).resolve()
root = temp / "p08-v013-official-chain-sqlite"
if Path(name) != root or root.is_symlink() or not root.is_dir():
    raise SystemExit("P08_607B_PROXY_PATH_NOT_ALLOWED")
update = root / "v013-update.zip"
full = root / "v013-full.zip"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
source = "dac7bc1d5410c077f32e522eb5740537f618ef9d"
target = "11f1ca58849e4baf8283c33659863416e48b9c5d"
source_manifest = "607b3a02a20021c0747d42440497b7e9e3e0fe39040869f475ba22f9f19437e9"
if (not update.is_file() or update.is_symlink()
    or not full.is_file() or full.is_symlink()
    or sha(update) != "5848cf2c871c61052040a600049745d0e069da336967b6344e83ab7f2ae851be"
    or sha(full) != "66ce5a6b081d218ed54a8ec9903f0544dba577525398f23f3f630ad855367d25"):
    raise SystemExit("P08_607B_PACKAGES_UNTRUSTED")
m = json.loads(zipfile.ZipFile(update).read("ATOMIC_MANIFEST.json"))
if (m.get("source_sha"), m.get("source_full_manifest_sha256"), m.get("target_sha"),
    m.get("schema_changes")) != (source, source_manifest, target, False):
    raise SystemExit("P08_607B_ATOMIC_MANIFEST_UNTRUSTED")
tag = "v0.1.13"
rid, uid, fid = 95113013, 95113014, 95113015
uname, fname = "VF_AdOps_V0.1.13_UPDATE.zip", "VF_AdOps_V0.1.13_FULL.zip"
channel = dict(schema_version="1.0", project_id="P08", component_id="APP",
    repository="llhzx2018/vf-adops", project_slug="vf-adops", enabled=True,
    update_type="ATOMIC", channel="stable", backup_required=True,
    rollback_supported=True, signature_required=False, signature_algorithm=None,
    production_auto_apply=False, from_versions=["0.1.12"], target_version="0.1.13",
    source_sha=source, source_full_manifest_sha256=source_manifest, target_sha=target,
    schema_from="1.1", schema_to="1.1", minimum_php="8.4.1", release_tag=tag,
    release_id=rid, asset_id=uid, asset_name=uname, asset_bytes=update.stat().st_size,
    asset_sha256=sha(update), full_asset_id=fid, full_asset_name=fname,
    full_asset_bytes=full.stat().st_size, full_asset_sha256=sha(full))
assets = [dict(id=i, name=n, size=p.stat().st_size, digest="sha256:"+sha(p),
               url="https://api.github.com/repos/llhzx2018/vf-adops/releases/assets/"+str(i))
          for i,n,p in ((uid,uname,update),(fid,fname,full))]
release = dict(id=rid, tag_name=tag, draft=False, prerelease=False, assets=assets)
tagref = dict(ref="refs/tags/"+tag, object=dict(type="commit", sha=target))
files = (("local-channel.json",channel),("local-release.json",release),("local-tag.json",tagref))
if mode == "prepare":
    for name, data in files:
        path = root / name
        if path.exists() or path.is_symlink():
            raise SystemExit("P08_607B_FIXTURE_EXISTS")
        fd = os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
        with os.fdopen(fd,"w") as f:
            json.dump(data,f,separators=(",",":"),sort_keys=True)
    print("P08_607B_REAL_ARCHIVE_SYNTHETIC_METADATA_NOT_PUBLISHED=PASS")
    sys.exit(0)
paths = {
    ("/repos/llhzx2018/core-updates/contents/projects/P08-ADOPS.json","ref=main"):
        ("channel",root/"local-channel.json","application/vnd.github.raw+json"),
    ("/repos/llhzx2018/vf-adops/releases/tags/v0.1.13",""):
        ("release",root/"local-release.json","application/vnd.github+json"),
    ("/repos/llhzx2018/vf-adops/git/ref/tags/v0.1.13",""):
        ("tag",root/"local-tag.json","application/vnd.github+json"),
    ("/repos/llhzx2018/vf-adops/releases/assets/95113014",""):
        ("atomic",update,"application/octet-stream"),
}
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(str(root/"api.crt"),str(root/"api.key"))
events = root / "local-api-events.txt"
if events.exists() or events.is_symlink():
    raise SystemExit("P08_607B_EVENTS_ALREADY_PRESENT")
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self,*args): pass
    def do_CONNECT(self):
        if self.path != "api.github.com:443":
            return self.send_error(403)
        self.send_response(200,"Connection Established")
        self.end_headers()
        self.wfile.flush()
        self.connection = ctx.wrap_socket(self.connection,server_side=True)
        self.rfile = self.connection.makefile("rb",self.rbufsize)
        self.wfile = self.connection.makefile("wb",self.wbufsize)
        self.close_connection = False
        self.handle_one_request()
        self.close_connection = True
    def do_GET(self):
        if self.headers.get("Host","").lower() not in ("api.github.com","api.github.com:443"):
            return self.send_error(403)
        if not hmac.compare_digest(self.headers.get("Authorization",""),
                                   "Bearer github_pat_"+"Q"*40):
            return self.send_error(403)
        url = urlsplit(self.path)
        match = paths.get((url.path,url.query))
        if match is None:
            return self.send_error(404)
        role, file, accept = match
        if self.headers.get("Accept") != accept:
            return self.send_error(406)
        raw = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Content-Type","application/zip" if role=="atomic" else "application/json")
        self.send_header("Connection","close")
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()
        with events.open("a",encoding="ascii") as f:
            f.write(role+"\n")
        self.close_connection = True
print("P08_607B_NO_UPSTREAM_API_READY=PASS",flush=True)
ThreadingHTTPServer(("127.0.0.1",19097),H).serve_forever()
