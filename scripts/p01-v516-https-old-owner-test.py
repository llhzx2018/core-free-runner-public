#!/usr/bin/env python3
"""Synthetic TLS reverse proxy for a genuine issued P01 PHP Owner API recovery test.

Uses one disposable official v516 clean FULL, certificate-pinned HTTPS client,
actual old PHP server/auth/CSRF and final ZIP one-file recovery. No Production,
real Owner data, GitHub Release or external endpoint is touched.
"""
from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import urllib.request


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-test-root", type=Path, required=True)
    ap.add_argument("--official-full", type=Path, required=True)
    args = ap.parse_args()
    script_dir = (args.old_test_root / "tests/compatibility/laravel/http").resolve(strict=True)
    sys.path.insert(0, str(script_dir))
    import test_p01_issued_v516_major_owner_api as real  # type: ignore

    original_start = real.server.start
    proxies: list[ThreadingHTTPServer] = []
    with tempfile.TemporaryDirectory(prefix="p01-official-v516-https-") as temporary:
        home = Path(temporary)
        cert, key = home / "tls-cert.pem", home / "tls-key.pem"
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-days", "1", "-keyout", str(key), "-out", str(cert),
             "-subj", "/CN=127.0.0.1",
             "-addext", "subjectAltName=IP:127.0.0.1"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=True, timeout=15,
        )
        client_context = ssl.create_default_context(cafile=str(cert))
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.minimum_version = ssl.TLSVersion.TLSv1_2
        server_context.load_cert_chain(str(cert), str(key))
        old_https_context = ssl._create_default_https_context
        ssl._create_default_https_context = lambda: ssl.create_default_context(
            cafile=str(cert))

        def start_https(site: Path):
            process, upstream = original_start(site)
            u = urllib.request.urlparse(upstream)
            upstream_port = u.port
            assert upstream_port is not None

            class Proxy(BaseHTTPRequestHandler):
                def log_message(self, fmt: str, *params: object) -> None:
                    pass  # Never log private paths, Cookie, auth or request body.

                def send_proxy(self):
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 160000:
                        self.send_error(413)
                        return
                    body = self.rfile.read(length) if length else None
                    headers = {
                        k: v for k, v in self.headers.items()
                        if k.lower() not in ("host", "connection", "content-length",
                                             "transfer-encoding", "accept-encoding")
                    }
                    con = http.client.HTTPConnection("127.0.0.1", upstream_port, timeout=9)
                    try:
                        con.request(self.command, self.path, body=body, headers=headers)
                        response = con.getresponse()
                        raw = response.read(1500000)
                        self.send_response(response.status)
                        for k, v in response.getheaders():
                            if k.lower() not in ("connection", "content-length",
                                                 "transfer-encoding", "content-encoding"):
                                self.send_header(k, v)
                        self.send_header("Content-Length", str(len(raw)))
                        self.send_header("Connection", "close")
                        self.end_headers()
                        self.wfile.write(raw)
                    finally:
                        con.close()

                do_GET = send_proxy
                do_POST = send_proxy

            httpd = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
            httpd.socket = server_context.wrap_socket(httpd.socket, server_side=True)
            proxies.append(httpd)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            port = httpd.server_address[1]
            tls_url = f"https://127.0.0.1:{port}"
            with socket.create_connection(("127.0.0.1", port), timeout=4) as raw:
                with client_context.wrap_socket(raw, server_hostname="127.0.0.1") as secure:
                    if secure.version() not in ("TLSv1.2", "TLSv1.3"):
                        raise RuntimeError("TLS_PROTOCOL_TOO_OLD")
                    if not secure.getpeercert():
                        raise RuntimeError("TLS_CERTIFICATE_NOT_VALIDATED")
            return process, tls_url

        real.server.start = start_https
        try:
            real.run(args.official_full, args.old_test_root)
            print("P01_ISSUED_V516_HTTPS_VERIFIED_TLS_OWNER_GUEST_CSRF_AND_SIGKILL=PASS",
                  flush=True)
        finally:
            real.server.start = original_start
            ssl._create_default_https_context = old_https_context
            for proxy in proxies:
                proxy.shutdown()
                proxy.server_close()


if __name__ == "__main__":
    main()
