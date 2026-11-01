"""Synthetic-only CP2 14-site loopback HEAD/PHP-FPM probe gates."""
import contextlib
import importlib.util
import io
from pathlib import Path
import os
import socket
import stat
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE=Path(__file__).parent
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,HERE/path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
m=load("p07-14-site-local-http-fpm-smoke.py","p07_site_http")
fx=load("p07-17-site-staged-local-evidence-tests.py","p07_stage_http_fixture")

class FakeSocket:
    def __init__(self,response=b"HTTP/1.1 302 Found\r\nLocation: https://example.invalid\r\n\r\n"):
        self.response=response
        self.sent=None
        self.closed=False
    def settimeout(self,n):pass
    def sendall(self,data):self.sent=data
    def recv(self,n):
        a=self.response
        self.response=b""
        return a
    def close(self):self.closed=True

class Tests(unittest.TestCase):
    def fixture(self):
        states=fx.make_states()
        final={}
        cp={}
        for label,mid,n in m.base.JOBS:
            for site in states[mid]["sites"]:
                if site["stage_status"]=="PULLED_STAGED":
                    site["runtime"]={"type":"php","version":"8.3"}
                    cp[site["domain"]]=[{"domain":site["domain"],
                         "site_user":site["site_user"],
                         "runtime":{"type":"php","version":"8.3"}}]
            final[mid]=states[mid]
        return states,cp
    def execute(self,changed=None):
        states,cp=self.fixture()
        if changed:changed(states,cp)
        out=io.StringIO()
        with mock.patch.object(m.base,"secure_state",
                 side_effect=lambda p:states[p.parent.name]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"inventory",return_value=cp), \
             mock.patch.object(m,"vhost",return_value=("FOUND",["/run/php/test.sock"])), \
             mock.patch.object(m,"backend_status",
                               return_value="TCP_POOL_AND_LISTENER_CONFIRMED"), \
             mock.patch.object(m,"service",return_value="ACTIVE"), \
             mock.patch.object(m,"head_local",
                 side_effect=lambda d,p,tls=False: "HTTP_200" if tls else "HTTP_301"), \
             mock.patch.object(sys,"argv",["tool","--probe-only-14-staged-sites"]), \
             contextlib.redirect_stdout(out):
            m.probe()
        return out.getvalue()
    def test_14_site_scoped_functional_pass_not_data_parity(self):
        output=self.execute()
        self.assertEqual(sum(line.startswith("SITE=") for line in output.splitlines()),14)
        self.assertIn("LOCAL_14_SITE_SMOKE_PASS=14",output)
        self.assertIn("LOCAL_14_SITE_SMOKE_REVIEW=0",output)
        self.assertIn("SOURCE_TARGET_APPLICATION_PARITY=NOT_VERIFIED",output)
        self.assertIn("PHP_DYNAMIC_EXECUTION=NOT_DIRECTLY_PROVEN",output)
        self.assertIn("CUTOVER_ALLOWED=NO",output)
    def test_mismatch_does_not_count_as_pass(self):
        def changed(s,cp):
            cp["123.kewaro.com"][0]["runtime"]["version"]="8.4"
        output=self.execute(changed)
        self.assertIn("LOCAL_14_SITE_SMOKE_PASS=13",output)
        self.assertIn("LOCAL_14_SITE_SMOKE_REVIEW=1",output)
    def test_local_head_literal_loopback_no_follow(self):
        fake=FakeSocket()
        got=[]
        def conn(addr,timeout):
            got.append((addr,timeout))
            return fake
        with mock.patch.object(m.socket,"create_connection",side_effect=conn):
            status=m.head_local("start.kewaro.com",80)
        self.assertEqual(status,"HTTP_302")
        self.assertEqual(got[0][0],("127.0.0.1",80))
        self.assertEqual(fake.sent.count(b"HEAD / HTTP/1.1"),1)
        self.assertIn(b"Host: start.kewaro.com",fake.sent)
        self.assertNotIn(b"GET ",fake.sent)
        self.assertTrue(fake.closed)
    def test_http_500_and_socket_failure_not_success(self):
        for raw,expect in (
            (b"HTTP/1.1 500 Server Error\r\n\r\n","HTTP_ERROR_500"),
            (b"HTTP/1.1 405 Method Not Allowed\r\n\r\n","HEAD_NOT_ALLOWED_405"),
            (b"HTTP/1.1 401 Unauthorized\r\n\r\n","ACCESS_PROTECTED_401"),
            (b"BAD RESPONSE\r\n","INVALID_HTTP_RESPONSE"),
        ):
            with self.subTest(expect=expect),mock.patch.object(
                m.socket,"create_connection",return_value=FakeSocket(raw)):
                self.assertEqual(m.head_local("start.kewaro.com",80),expect)
        with mock.patch.object(m.socket,"create_connection",
                               side_effect=OSError("no local listener")):
            self.assertEqual(m.head_local("start.kewaro.com",443,True),
                             "LOCAL_CONNECT_OR_TLS_FAILED")
    def test_vhost_exact_domain_match_and_no_wildcard_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"site.conf").write_text(
                "server { server_name start.kewaro.com; "
                "fastcgi_pass unix:/run/php/php8.3-fpm-site.sock; }")
            self.assertEqual(m.vhost("start.kewaro.com",root),
                             ("FOUND",["/run/php/php8.3-fpm-site.sock"]))
            self.assertEqual(m.vhost("unzip.kewaro.com",root),("NOT_FOUND",[]))
            self.assertEqual(m.vhost("start.kewaro.com.evil",root),("NOT_FOUND",[]))
    def test_cloudpanel_tcp_pool_listener_matching(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            nginx=root/"nginx"
            nginx.mkdir()
            (nginx/"site.conf").write_text(
                "server { server_name start.kewaro.com; "
                "location ~ \\.php$ { fastcgi_pass 127.0.0.1:9777; } }")
            self.assertEqual(m.vhost("start.kewaro.com",nginx),
                             ("FOUND",["tcp:127.0.0.1:9777"]))
            pools=root/"php"/"8.3"/"fpm"/"pool.d"
            pools.mkdir(parents=True)
            (pools/"start.conf").write_text(
                "[start]\nlisten = 127.0.0.1:9777\nuser = site_start\n"
                "group = site_start\n")
            self.assertTrue(m.fpm_pool_matches(
                "8.3","site_start","tcp:127.0.0.1:9777",root/"php"))
            self.assertFalse(m.fpm_pool_matches(
                "8.3","other_user","tcp:127.0.0.1:9777",root/"php"))
            proc=root/"tcp"
            proc.write_text(
                "sl  local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"
                "0: 0100007F:2631 00000000:0000 0A 00000000:00000000 00:00000000 00000000 33 0 11\n")
            self.assertTrue(m.tcp_listener_present(9777,proc))
            self.assertFalse(m.tcp_listener_present(9778,proc))
            with mock.patch.object(m,"fpm_pool_matches",return_value=True), \
                 mock.patch.object(m,"tcp_listener_present",return_value=True):
                self.assertEqual(
                    m.backend_status(["tcp:127.0.0.1:9777"],"8.3","site_start"),
                    "TCP_POOL_AND_LISTENER_CONFIRMED")
            with mock.patch.object(m,"fpm_pool_matches",return_value=False):
                self.assertEqual(
                    m.backend_status(["tcp:127.0.0.1:9777"],"8.3","site_start"),
                    "FPM_POOL_OR_SITE_USER_NOT_MATCHED")
            with mock.patch.object(m,"fpm_pool_matches",return_value=True), \
                 mock.patch.object(m,"tcp_listener_present",return_value=False):
                self.assertEqual(
                    m.backend_status(["tcp:127.0.0.1:9777"],"8.3","site_start"),
                    "TCP_FPM_LISTENER_NOT_FOUND")
    def test_unsafe_ambiguous_unknown_backends_block(self):
        self.assertEqual(m.backend_status([],"8.3","example"),
                         "NO_FASTCGI_DECLARED")
        self.assertEqual(m.backend_status(["UNSUPPORTED"],"8.3","example"),
                         "UNSUPPORTED_FASTCGI_BACKEND")
        self.assertEqual(m.backend_status(["tcp:127.0.0.1:9000",
                                             "tcp:127.0.0.1:9001"],
                                            "8.3","example"),
                         "AMBIGUOUS_FASTCGI_BACKENDS")
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            (p/"x.conf").write_text(
                "server { server_name start.kewaro.com; "
                "fastcgi_pass 192.0.2.1:9000; }")
            self.assertEqual(m.vhost("start.kewaro.com",p),
                             ("FOUND",["UNSUPPORTED"]))
    def test_https_404_and_redirect_are_review_even_with_tcp_backend(self):
        self.assertEqual(m.https_route("HTTP_200"),"HTTPS_2XX")
        self.assertEqual(m.https_route("HTTP_302"),
                         "HTTPS_REDIRECT_UNVERIFIED")
        self.assertEqual(m.https_route("HTTP_ERROR_404"),"HTTPS_404")
        self.assertEqual(m.https_route("LOCAL_CONNECT_OR_TLS_FAILED"),
                         "HTTPS_NOT_READY")
        original=m.head_local
        def new_head(domain,port,tls=False):
            if tls and domain=="press.kewaro.com":return "HTTP_ERROR_404"
            if tls and domain=="infra.kewaro.com":return "HTTP_302"
            return "HTTP_200" if tls else "HTTP_301"
        with mock.patch.object(m,"head_local",side_effect=new_head):
            output=self.execute()
        self.assertIn("LOCAL_14_SITE_SMOKE_PASS=12",output)
        self.assertIn("LOCAL_14_SITE_SMOKE_REVIEW=2",output)
        self.assertIn("SITE=press.kewaro.com ",output)
        self.assertIn("HTTPS443=HTTP_ERROR_404 ROUTE=HTTPS_404 LOCAL_SMOKE=REVIEW",
                      output)
        self.assertIn("HTTPS443=HTTP_302 ROUTE=HTTPS_REDIRECT_UNVERIFIED LOCAL_SMOKE=REVIEW",
                      output)

    def test_migration_state_safety_guards(self):
        def bad(states,cp):
            states[m.base.JOBS[1][1]]["source_runtime_frozen"]=True
        with self.assertRaisesRegex(m.Block,"MIGRATION_PROTECTION_CHANGED"):
            self.execute(bad)
        def pending(states,cp):
            states[m.base.JOBS[2][1]]["sites"][-1]["stage_status"]="PULLED_STAGED"
        with self.assertRaisesRegex(m.Block,"14_SITE_SCOPE_CHANGED"):
            self.execute(pending)
    def test_explicit_argument_required(self):
        with mock.patch.object(sys,"argv",["tool","--apply"]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"staged_sites") as s:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_LOCAL_HTTP_PROBE_ARGUMENT_REQUIRED"):
                m.probe()
            s.assert_not_called()
    def test_no_remote_or_mutating_commands(self):
        source=(HERE/"p07-14-site-local-http-fpm-smoke.py").read_text()
        for banned in ("ssh ","rsync ","curl ","DROP DATABASE","INSERT INTO",
                       "UPDATE ","DELETE ","subprocess.Popen","nginx -s",
                       "systemctl restart","systemctl start","getaddrinfo(",
                       "urlopen(","follow_redirects"):
            self.assertNotIn(banned,source)
        self.assertIn('("127.0.0.1",port)',source)
        self.assertIn("HEAD / HTTP/1.1",source)
        self.assertIn("CUTOVER_ALLOWED=NO",source)

if __name__=="__main__":
    unittest.main()
