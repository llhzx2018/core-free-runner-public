"""Synthetic-only P07 unzip WordPress option_name-keyed conflict tests."""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "p07_unzip_keyed", HERE / "p07-unzip-options-keyed-readonly.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def item(option_name, option_id, value, autoload="yes"):
    def encoded(s):
        return s.encode().hex().upper().encode()
    return (
        encoded(option_name) + b"\t" + str(option_id).encode() + b"\tV" +
        encoded(value) + b"\tV" + encoded(autoload) + b"\n"
    )

def sample(mode="SOURCE"):
    rows=m.option_map(
        item("siteurl",1,"https://example.test")+
        item("_transient_update",2,"cached")+
        item("some_option",3,"abc")
    )
    return json.dumps({
        "mode":mode,"domain":m.DOMAIN,"table":"wp_options",
        "transaction":"READ_ONLY","rows":len(rows),"options":rows,
        "final_snapshot_proof":False
    },sort_keys=True,separators=(",",":"))

class Tests(unittest.TestCase):
    def test_wp_option_name_keyed_structural_differences(self):
        source=m.option_map(item("siteurl",1,"A")+
                            item("foo",2,"same")+
                            item("_transient_alive",3,"first"))
        target=m.option_map(item("siteurl",10,"B")+
                            item("foo",2,"same")+
                            item("_transient_alive",3,"second"))
        r=m.compare(source,target)
        self.assertEqual(r["SOURCE_OPTION_ROWS"],3)
        self.assertEqual(r["TARGET_OPTION_ROWS"],3)
        self.assertEqual(r["ONLY_SOURCE_OPTION_NAMES"],0)
        self.assertEqual(r["ONLY_TARGET_OPTION_NAMES"],0)
        self.assertEqual(r["SAME_NAME_ID_DIFFERENCES"],1)
        self.assertEqual(r["SAME_NAME_VALUE_DIFFERENCES"],2)
        self.assertEqual(r["SAME_NAME_AUTOLOAD_DIFFERENCES"],0)
        self.assertEqual(r["TOTAL_CHANGED_OPTION_NAMES"],2)
        self.assertEqual(r["OPTION_NAME_KEYED_PARITY"],"NON_TRANSIENT_DIFFER_ADVISORY")
        self.assertEqual(json.loads(r["CHANGED_NAMES_BY_CLASS"])["CORE_CONFIG"],1)
        self.assertNotIn("https://example.test",str(r))
        self.assertNotIn("siteurl",str(r))
    def test_volatile_alone_never_approves_migration(self):
        source=m.option_map(item("_transient_thing",3,"aaa"))
        target=m.option_map(item("_transient_thing",3,"bbb"))
        r=m.compare(source,target)
        self.assertEqual(r["OPTION_NAME_KEYED_PARITY"],
                         "TRANSIENT_ONLY_DIFFER_ADVISORY")
        self.assertEqual(r["TOTAL_CHANGED_OPTION_NAMES"],1)
    def test_same_totals_but_option_names_changed(self):
        source=m.option_map(item("key_a",1,"val"))
        target=m.option_map(item("key_b",1,"val"))
        r=m.compare(source,target)
        self.assertEqual(r["ONLY_SOURCE_OPTION_NAMES"],1)
        self.assertEqual(r["ONLY_TARGET_OPTION_NAMES"],1)
        self.assertEqual(r["TOTAL_CHANGED_OPTION_NAMES"],2)
    def test_autoload_only_remains_unresolved(self):
        source=m.option_map(item("foo",1,"same","yes"))
        target=m.option_map(item("foo",1,"same","no"))
        r=m.compare(source,target)
        self.assertEqual(r["SAME_NAME_AUTOLOAD_DIFFERENCES"],1)
        self.assertEqual(r["SAME_NAME_VALUE_DIFFERENCES"],0)
        self.assertEqual(r["OPTION_NAME_KEYED_PARITY"],"NON_TRANSIENT_DIFFER_ADVISORY")
    def test_parser_rejects_row_leak_and_invalid_snapshot_claim(self):
        good=sample()
        parsed=m.parse(good,"SOURCE")
        self.assertEqual(len(parsed),3)
        for broken in (
            good+"password=not-allowed",
            good.replace('"READ_ONLY"','"WRITE_ALLOWED"'),
            good.replace('"final_snapshot_proof":false',
                         '"final_snapshot_proof":true'),
            good.replace('"SOURCE"','"TARGET"'),
            good.replace('"siteurl"', '"private-row"'),
        ):
            if broken==good:
                continue
            with self.assertRaises(m.Block):
                m.parse(broken,"SOURCE")
    def test_duplicate_and_malformed_options_rejected(self):
        for broken in (
            item("duplicate",1,"same")+item("duplicate",2,"same"),
            b"AB\t1\tVQQ\tVN\n",
            b"00\t1\tV00\tV0\n",
            b"6869\t0x2\tV00\tV00\n"
        ):
            with self.assertRaises(m.Block):
                m.option_map(broken)
    def test_mock_client_real_fd_and_only_read_sql(self):
        calls=[]
        def memfd(label):
            fd=os.memfd_create(label,flags=os.MFD_CLOEXEC)
            os.fchmod(fd,0o600)
            return os.fdopen(fd,"w+b")
        class Base:
            @staticmethod
            def source_auth(domain, db):
                self.assertEqual(domain,m.DOMAIN)
                self.assertEqual(db,"site_db")
                return "127.0.0.1",3306,"synthetic_user","synthetic-secret"
            target_auth=source_auth
            memory_file=staticmethod(memfd)
        def runner(cmd,**kwargs):
            sql_fd=kwargs["stdin"]
            sql_fd.seek(0)
            sql=sql_fd.read().decode()
            calls.append((cmd,sql,kwargs))
            self.assertIn("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;",sql)
            self.assertIn("FROM " + chr(96) + "site_db" + chr(96) + "." +
                          chr(96) + "wp_options" + chr(96),sql)
            self.assertIn("ROLLBACK;",sql)
            for statement in ("DELETE FROM", "INSERT INTO", "UPDATE wp_options",
                              "DROP DATABASE","CREATE DATABASE"):
                self.assertNotIn(statement,sql)
            self.assertNotIn("synthetic-secret",str(cmd))
            return subprocess.CompletedProcess(cmd,0,item("siteurl",1,"synthetic-value"),b"")
        out=io.StringIO()
        with mock.patch.object(m,"load_base",return_value=Base), \
             mock.patch.object(m.shutil,"which",side_effect=lambda x:"/usr/bin/"+x), \
             mock.patch.object(m.subprocess,"run",side_effect=runner), \
             contextlib.redirect_stdout(out):
            m.worker("TARGET","site_db")
        data=json.loads(out.getvalue())
        self.assertEqual(data["rows"],1)
        self.assertNotIn("synthetic-value",out.getvalue())
        self.assertNotIn("synthetic-secret",out.getvalue())
        self.assertNotIn("site_db",out.getvalue())
        self.assertEqual(len(calls),1)
    def test_unsafe_main_flag_does_not_touch_live_servers(self):
        with mock.patch.object(sys,"argv",["tool","--cutover"]), \
             mock.patch.object(m,"checked_file") as read:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_SINGLE_SITE_READONLY_FLAG_REQUIRED"):
                m.main()
            read.assert_not_called()
    def test_old_server_and_target_write_operations_absent(self):
        source=(HERE/"p07-unzip-options-keyed-readonly.py").read_text()
        self.assertIn("SOURCE_OPTIONS_READONLY_WORKER_FAILED",source)
        self.assertIn("CUTOVER_ALLOWED=NO",source)
        self.assertIn("MIGRATION_STATE_WRITES=NONE",source)
        self.assertIn("READ_ONLY",source)
        for unsafe in ("cloudpanel.import_database(","adopt_existing_guarded_site(",
                       "cutover_migration(","freeze_old_server(","DELETE FROM wp_options"):
            self.assertNotIn(unsafe,source)

if __name__=="__main__":
    unittest.main()
