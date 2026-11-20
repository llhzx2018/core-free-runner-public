#!/usr/bin/env python3
"""P08 #85 CI-ONLY GitHub API emulation over pinned localhost TLS proxy.

The targets, tag and asset bytes are synthetic and NEVER published.
No upstream; no fallback, no actual GitHub credentials.
"""
import hmac
import json
import os
import ssl
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

if (os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("P08_ISOLATED_INSTALL_TEST") != "YES"
        or os.environ.get("P08_85_UNISSUED_POSITIVE") != "YES"
        or len(sys.argv) != 5):
    raise SystemExit("P08_85_PROXY_DISPOSABLE_ONLY")
fixture, certificate, key, events = map(Path, sys.argv[1:])
tmp = Path(os.environ["RUNNER_TEMP"]).resolve()
if (fixture != tmp / "p08-85-native-fixture"
        or events != tmp / "p08-85-native-events.log"
        or events.exists() or events.is_symlink()
        or not fixture.is_dir() or fixture.is_symlink()
        or any(not x.is_file() or not str(x.resolve()).startswith(str(tmp)+"/")
               for x in (certificate, key))):
    raise SystemExit("P08_85_PROXY_SCOPE_INVALID")
version = "0.1.14"
asset_id = 84552114
tag = "v" + version
channel = fixture / "channel.json"
release = fixture / "release.json"
git_ref = fixture / "tag.json"
update = fixture / ("VF_AdOps_V" + version + "_UPDATE.zip")
for f in (channel, release, git_ref, update):
    if not f.is_file() or f.is_symlink() or f.stat().st_size < 2:
        raise SystemExit("P08_85_PROXY_FIXTURE_MISSING")
routes = {
    ("/repos/llhzx2018/core-updates/contents/projects/P08-ADOPS.json", "ref=main"):
        (channel, "application/vnd.github.raw+json", "channel"),
    ("/repos/llhzx2018/vf-adops/releases/tags/" + tag, ""):
        (release, "application/vnd.github+json", "release"),
    ("/repos/llhzx2018/vf-adops/git/ref/tags/" + tag, ""):
        (git_ref, "application/vnd.github+json", "tag"),
    ("/repos/llhzx2018/vf-adops/releases/assets/" + str(asset_id), ""):
        (update, "application/octet-stream", "atomic"),
}
test_token = "github_pat_" + "r" * 45
tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
tls.load_cert_chain(str(certificate), str(key))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "P08IsolatedNoUpstream"
    sys_version = ""

    def log_message(self, *args):
        return

    def do_CONNECT(self):
        if self.path != "api.github.com:443":
            self.send_error(403)
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        self.wfile.flush()
        self.connection = tls.wrap_socket(self.connection, server_side=True)
        self.rfile = self.connection.makefile("rb", self.rbufsize)
        self.wfile = self.connection.makefile("wb", self.wbufsize)
        self.close_connection = False
        self.handle_one_request()
        self.close_connection = True

    def do_GET(self):
        host = self.headers.get("Host", "").lower()
        if host not in ("api.github.com", "api.github.com:443"):
            self.send_error(403)
            return
        if not hmac.compare_digest(self.headers.get("Authorization", ""),
                                   "Bearer " + test_token):
            self.send_error(403)
            return
        parsed = urlsplit(self.path)
        route = routes.get((parsed.path, parsed.query))
        if route is None:
            self.send_error(404)
            return
        file, accept, role = route
        if self.headers.get("Accept", "") != accept:
            self.send_error(406)
            return
        size = file.stat().st_size
        self.send_response(200)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Type",
                         "application/zip" if role == "atomic" else "application/json")
        self.send_header("Connection", "close")
        self.end_headers()
        with file.open("rb") as reader:
            while chunk := reader.read(65536):
                self.wfile.write(chunk)
        self.wfile.flush()
        with events.open("a", encoding="ascii") as writer:
            writer.write(role + "\n")
        self.close_connection = True


server = ThreadingHTTPServer(("127.0.0.1", 19184), Handler)
print("P08_85_ISOLATED_POSITIVE_TLS_PROXY=READY", flush=True)
try:
    server.serve_forever(poll_interval=0.2)
finally:
    server.server_close()
