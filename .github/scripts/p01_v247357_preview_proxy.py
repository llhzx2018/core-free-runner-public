#!/usr/bin/env python3
"""V2.47.357 single-use gated proxy. It serves ONLY a disposable local app.

The externally supplied password is never present in this public file or Actions logs.
An authenticated reviewer sees a local synthetic admin session (no app password exposed).
"""
import base64
import hashlib
import hmac
import http.client
import pathlib
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

EXPECTED_SHA256 = "6a58716461e99b6324af683d5b25e6f147a7e08acca95bd0717ed1f957d90d7d"
COOKIE_JAR = pathlib.Path("/tmp/p01-v247357-preview/admin-cookies.txt")
APP_HOST, APP_PORT = "127.0.0.1", 18541
MAX_BODY = 65536

def local_session_cookie():
    cookies = {}
    for row in COOKIE_JAR.read_text(encoding="utf-8").splitlines():
        if not row or (row.startswith("#") and not row.startswith("#HttpOnly_")):
            continue
        columns = row.replace("#HttpOnly_", "", 1).split("\t")
        if len(columns) >= 7:
            cookies[columns[5]] = columns[6]
    value = cookies.get("vfnav_session")
    if not value or not re.fullmatch(r"[A-Za-z0-9,-]{12,128}", value):
        raise RuntimeError("Disposable authenticated PHP session absent")
    return "vfnav_session=" + value

SESSION = local_session_cookie()

class PreviewProxy(BaseHTTPRequestHandler):
    server_version = "IsolatedPreview"
    def log_message(self, *_):  # No request paths, credentials or token values in runner logs.
        pass

    def respond(self, status, data=b"", content_type="text/plain; charset=utf-8", auth=False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if auth:
            self.send_header("WWW-Authenticate", 'Basic realm="P01 V2.47.357 simulated preview"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def authorized(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic ") or len(header) > 250:
            return False
        try:
            creds = base64.b64decode(header[6:], validate=True).decode("utf-8")
            user, password = creds.split(":", 1)
        except (ValueError, UnicodeError):
            return False
        return user == "preview" and hmac.compare_digest(
            hashlib.sha256(password.encode("utf-8")).hexdigest(), EXPECTED_SHA256
        )

    def safe_target(self):
        raw = urlsplit(self.path)
        path = unquote(unquote(raw.path)).replace("\\", "/")
        parts = path.split("/")
        if any(p.startswith(".") or p in ("..", "") for p in parts[1:] if p):
            return None
        if path == "/browser-helper.php" and self.command in ("GET", "HEAD") and not raw.query:
            return self.path
        # VF Start does NOT reference /assets/*.css directly. Its canonical
        # vf_asset_url() routes all static files through asset.php?file=...&v=VERSION.
        # The former proxy blocked this and displayed giant unstyled SVG icons.
        if path == "/asset.php" and self.command in ("GET", "HEAD"):
            try:
                params = parse_qs(raw.query, keep_blank_values=True, strict_parsing=True)
            except ValueError:
                return None
            if (set(params) == {"file", "v"}
                and len(params["file"]) == 1 and len(params["v"]) == 1
                and params["v"][0] == "2.47.357"
                and re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:css|js|png|jpe?g|webp|gif|svg|ico)", params["file"][0], re.IGNORECASE)):
                return self.path
            return None
        if path == "/api.php" and self.command == "POST":
            try:
                params = parse_qs(raw.query, strict_parsing=True)
            except ValueError:
                return None
            if params.get("action") in (["plugin_token_regenerate"], ["plugin_token_revoke"]) and len(params) == 1:
                return self.path
        if (self.command in ("GET", "HEAD") and path.startswith("/assets/")
            and re.fullmatch(r"/assets/[A-Za-z0-9_./-]+", path)
            and path.lower().endswith((".js", ".css", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico"))):
            return self.path
        return None

    def do_GET(self):
        self.forward()
    def do_HEAD(self):
        self.forward()
    def do_POST(self):
        self.forward()
    def forward(self):
        if not self.authorized():
            return self.respond(401, b"Authentication required", auth=True)
        target = self.safe_target()
        if target is None:
            return self.respond(404, b"Not part of isolated preview")
        raw_size = self.headers.get("Content-Length", "0")
        if not raw_size.isdecimal() or int(raw_size) > MAX_BODY:
            return self.respond(413, b"Request too large")
        size = int(raw_size)
        data = self.rfile.read(size) if size else None
        # Never allow browser-supplied cookies, auth or forwarding headers to reach the mock app.
        headers = {
            "Host": f"{APP_HOST}:{APP_PORT}",
            "Cookie": SESSION,
            "Accept": self.headers.get("Accept", "text/html,application/json")[:300],
            "Content-Type": self.headers.get("Content-Type", "application/json")[:100],
            "X-CSRF-Token": self.headers.get("X-CSRF-Token", "")[:256],
        }
        try:
            conn = http.client.HTTPConnection(APP_HOST, APP_PORT, timeout=20)
            conn.request(self.command, target, body=data, headers=headers)
            response = conn.getresponse()
            result = response.read()
            self.send_response(response.status)
            for name, value in response.getheaders():
                if name.lower() in (
                    "connection", "transfer-encoding", "content-length",
                    "set-cookie", "cache-control", "server", "date", "location",
                    "access-control-allow-origin", "access-control-allow-credentials",
                    "x-powered-by"
                ):
                    continue
                self.send_header(name, value)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(result)
            conn.close()
        except (TimeoutError, OSError, http.client.HTTPException):
            self.respond(502, b"Disposable preview unavailable")

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18542), PreviewProxy).serve_forever()
