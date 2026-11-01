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
    def execute(self,changed=None,heads=None):
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
                 side_effect=(heads or
                     (lambda d,p,tls=False: "HTTP_200" if tls else "HTTP_301"))), \
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
        def new_head(domain,port,tls=False):
            if tls and domain=="press.kewaro.com":return "HTTP_ERROR_404"
            if tls and domain=="infra.kewaro.com":return "HTTP_302"
            return "HTTP_200" if tls else "HTTP_301"
        output=self.execute(heads=new_head)
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
    def test_three_route_details_record_only_review_and_redact_redirect(self):
        states,cp=self.fixture()
        records={
            "domain.kewaro.com":(302,{"location":"https://domain.kewaro.com/login?token=secret"}),
            "infra.kewaro.com":(302,{"location":"https://accounts.kewaro.com/auth?jwt=secret",
                                      "x-redirect-by":"Application"}),
            "press.kewaro.com":(404,{})
        }
        out=io.StringIO()
        with mock.patch.object(m.base,"secure_state",
                 side_effect=lambda p:states[p.parent.name]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"inventory",return_value=cp), \
             mock.patch.object(m,"response_headers_local",side_effect=lambda d:records[d]), \
             mock.patch.object(m,"site_docroot_evidence",
                               return_value=("DIRECTORY_PRESENT","PRESENT","NO")), \
             mock.patch.object(m,"nginx_route_evidence",
                               return_value=("VHOST_FILES_2","YES",
                                             "TRY_FILES_YES_REWRITE_NO_PROXY_NO")), \
             mock.patch.object(sys,"argv",["tool","--diagnose-only-three-review-routes"]), \
             contextlib.redirect_stdout(out):
            self.assertEqual(m.diagnose_three_routes(),0)
        log=out.getvalue()
        self.assertEqual(sum(x.startswith("SITE=") for x in log.splitlines()),3)
        self.assertIn("HTTPS_STATUS=404",log)
        self.assertIn("REDIRECT_CLASS=SAME_HOST_AUTH_OR_ADMIN_HTTPS",log)
        self.assertIn("REDIRECT_CLASS=RELATED_PUBLIC_DOMAIN_AUTH_OR_ADMIN_HTTPS",log)
        self.assertNotIn("token",log)
        self.assertNotIn("secret",log)
        self.assertNotIn("jwt",log)
        self.assertIn("CUTOVER_ALLOWED=NO",log)
    def test_three_route_http_header_parser_never_follows_redirect(self):
        fake=FakeSocket(
            b"HTTP/1.1 302 Found\r\n"
            b"Location: https://domain.kewaro.com/login?session=SECRET\r\n"
            b"Set-Cookie: private=SECRET\r\n\r\n")
        class FakeTLS:
            def __init__(self):self.check_hostname=None;self.verify_mode=None
            def wrap_socket(self,s,server_hostname):
                self.name=server_hostname
                return s
        ctx=FakeTLS()
        with mock.patch.object(m.socket,"create_connection",return_value=fake) as conn, \
             mock.patch.object(m.ssl,"SSLContext",return_value=ctx):
            code,headers=m.response_headers_local("domain.kewaro.com")
        self.assertEqual(code,302)
        self.assertEqual(ctx.name,"domain.kewaro.com")
        self.assertIn("location",headers)
        self.assertNotIn("set-cookie",headers)
        self.assertIn(b"HEAD / HTTP/1.1",fake.sent)
        self.assertEqual(conn.call_args.args[0],("127.0.0.1",443))
        self.assertTrue(fake.closed)
    def test_three_route_out_of_scope_and_unsafe_paths_fail_closed(self):
        with self.assertRaisesRegex(m.Block,"OUT_OF_SCOPE_ROUTE_HOST"):
            m.response_headers_local("www3.m3u8.one")
        with self.assertRaisesRegex(m.Block,"OUT_OF_SCOPE_NGINX_DOMAIN"):
            m.nginx_route_evidence("www3.m3u8.one")
        self.assertEqual(m.site_docroot_evidence({
            "site_user":"example","document_root":"/etc/passwd"}),
            ("UNVERIFIED","UNKNOWN","UNKNOWN"))
        self.assertEqual(m.site_docroot_evidence({
            "site_user":"example","document_root":"/home/example/../other"}),
            ("UNVERIFIED","UNKNOWN","UNKNOWN"))
        self.assertEqual(m.redirection_class("javascript:alert(1)",
                                              "domain.kewaro.com"),"UNSAFE_SCHEME")
        self.assertEqual(m.redirection_class(
            "https://x:passwd@domain.kewaro.com/login?secret",
            "domain.kewaro.com"),"CREDENTIAL_URL_REVIEW")
        self.assertEqual(m.redirection_class("https://unrelated.example/test?secret",
            "domain.kewaro.com"),"OTHER_HOST_OTHER_PATH_HTTPS")
    def test_nginx_routing_config_only_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"site.conf").write_text(
                "server { server_name press.kewaro.com; "
                "root /home/hidden/wp; index index.php; "
                "location / { try_files $uri $uri/ /index.php?$args; } }")
            self.assertEqual(m.nginx_route_evidence("press.kewaro.com",root),
                ("VHOST_FILES_1","YES","TRY_FILES_YES_REWRITE_NO_PROXY_NO"))
            self.assertEqual(m.nginx_route_evidence("domain.kewaro.com",root),
                ("VHOST_NOT_FOUND","UNKNOWN","UNKNOWN"))
    def test_three_route_no_config_changes(self):
        source=(HERE/"p07-14-site-local-http-fpm-smoke.py").read_text()
        for prohibited in ("nginx -s reload","systemctl restart",
                           "crontab -","os.replace(","shutil.copytree(",
                           "DROP DATABASE","DNS_UPDATE","subprocess.Popen"):
            self.assertNotIn(prohibited,source)
        self.assertIn("CUTOVER_ALLOWED=NO",source)
        self.assertIn("HTTP_METHOD=HEAD_NO_REDIRECT_FOLLOW",source)

    def test_three_site_deeper_route_classification_never_acts_or_reveals_paths(self):
        states,cp=self.fixture()
        detail={
            "domain.kewaro.com":(302,{"location":"/dashboard?token=DO_NOT_OUTPUT"}),
            "infra.kewaro.com":(302,{"location":"/home?secret=DO_NOT_OUTPUT"}),
            "press.kewaro.com":(404,{})
        }
        calls=[]
        def fake_response(domain,timeout=4,path="/"):
            calls.append((domain,path))
            if path=="/":return detail[domain]
            if path=="/index.php":
                return (404 if domain=="press.kewaro.com" else 302),{}
            if path=="/robots.txt":return 200,{}
            raise AssertionError("Unexpected side-effecting path")
        def safe_entries(panel):
            return {"index.php":True,"index.html":False,"robots.txt":True}
        out=io.StringIO()
        with mock.patch.object(m.base,"secure_state",
                 side_effect=lambda p:states[p.parent.name]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"inventory",return_value=cp), \
             mock.patch.object(m,"safe_entry_metadata",side_effect=safe_entries), \
             mock.patch.object(m,"nginx_document_root_match",
                               return_value="EXACT_MATCH"), \
             mock.patch.object(m,"response_headers_local",
                               side_effect=fake_response), \
             mock.patch.object(sys,"argv",["tool","--review-three-site-root-and-entry"]), \
             contextlib.redirect_stdout(out):
            self.assertEqual(m.diagnose_three_routes_depth(),0)
        log=out.getvalue()
        self.assertIn("REVIEWED_SITE_COUNT=3",log)
        self.assertIn("NGINX_TO_PANEL_ROOT=EXACT_MATCH",log)
        self.assertIn("SITE=press.kewaro.com HTTPS_ROOT=404",log)
        self.assertIn("INDEX_PHP_HEAD=404",log)
        self.assertIn("INDEX_HTML_HEAD=SKIP_NO_SAFE_FILE",log)
        self.assertIn("ROBOTS_HEAD=200",log)
        self.assertIn("CAUSE=NOT_YET_PROVEN",log)
        self.assertIn("CUTOVER_ALLOWED=NO",log)
        self.assertNotIn("DO_NOT_OUTPUT",log)
        self.assertNotIn("/dashboard",log)
        self.assertEqual(len(calls),9)
        self.assertEqual(set(path for _,path in calls),
                         {"/","/index.php","/robots.txt"})
    def test_bounded_routes_and_root_paths_fail_closed(self):
        with self.assertRaisesRegex(m.Block,"HTTP_ROUTE_PATH_SCOPE_UNSAFE"):
            m.response_headers_local("press.kewaro.com",path="/admin/reset")
        with self.assertRaisesRegex(m.Block,"OUT_OF_SCOPE_NGINX_ROOT"):
            m.nginx_document_root_match("www3.m3u8.one",{})
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"vhost").write_text(
                "server_name press.kewaro.com;\n"
                "root /home/example/htdocs/press.kewaro.com;\n")
            self.assertEqual(m.nginx_document_root_match(
                "press.kewaro.com",
                {"site_user":"example",
                 "document_root":"/home/example/htdocs/press.kewaro.com"},
                root),"NGINX_OR_PANEL_ROOT_MISSING_OR_SYMLINK")
            self.assertEqual(m.nginx_document_root_match(
                "press.kewaro.com",
                {"site_user":"example",
                 "document_root":"/etc/passwd"},root),
                "PANEL_DOCROOT_UNVERIFIED")
    def test_three_site_depth_cli_explicit_scope(self):
        with mock.patch.object(sys,"argv",["tool","--write"]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m,"staged_sites") as states:
            with self.assertRaisesRegex(
                m.Block,"EXPLICIT_THREE_ROUTE_DEPTH_ARGUMENT_REQUIRED"):
                m.diagnose_three_routes_depth()
            states.assert_not_called()

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
