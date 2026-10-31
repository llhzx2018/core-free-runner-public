"""P07 14-site runtime/asset audit: synthetic tests; no host connections."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT=Path(__file__).parent
def load(name,label):
    spec=importlib.util.spec_from_file_location(label,ROOT/name)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
m=load("p07-14-site-runtime-assets-readonly.py","p07_runtime")
fixture=load("p07-17-site-staged-local-evidence-tests.py","p07_stage_fixture")

class Tests(unittest.TestCase):
    def test_php_runtime_match_and_mismatch(self):
        s={"runtime":{"type":"php","version":"8.3"}}
        t={"runtime":{"type":"php","version":"8.4"}}
        self.assertEqual(m.runtime_status(s,t)[0],"PHP_VERSION_DIFFER")
        t["runtime"]["version"]="8.3"
        with mock.patch.object(m.Path,"is_file",return_value=True):
            self.assertEqual(m.runtime_status(s,t)[0],"PHP_VERSION_AND_BINARY_PRESENT")
        with mock.patch.object(m.Path,"is_file",return_value=False):
            self.assertEqual(m.runtime_status(s,t)[0],"PHP_BINARY_MISSING")
        self.assertEqual(m.runtime_status({"runtime":{"type":"static"}},
            {"runtime":{"type":"static"}})[0],"DECLARED_RUNTIME_MATCH_NEEDS_FUNCTIONAL_SMOKE")

    def test_local_asset_paths_prevent_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"test.sqlite"
            file.write_bytes(b"SQLite format 3\x00"+b"\0"*100)
            self.assertEqual(m.local_sqlite_header(file),"HEADER_PASS")
            self.assertEqual(m.stat_asset(file,"FILE"),"PRESENT")
            link=Path(d)/"alias"
            link.symlink_to(file)
            self.assertEqual(m.stat_asset(link,"FILE"),"SYMLINK_REVIEW_REQUIRED")
            self.assertEqual(m.local_sqlite_header(link),"MISSING_OR_UNSAFE")
        for path in ("/home/user/../other/data", "/etc/passwd",
                     "/home/another/data"):
            with self.assertRaises(m.baseline.Block):
                m.safe_asset_path({"path":path,"user":"user"})

    def run_fixture(self,override=None):
        states=fixture.make_states()
        if override:override(states)
        manifest={"sites":[]}
        for s in states.values():
            for site in s["sites"]:
                if site["stage_status"]=="PULLED_STAGED":
                    manifest["sites"].append({
                        "domain":site["domain"],"site_user":site["site_user"],
                        "runtime":{"type":"php","version":"8.3"},
                        "mysql_databases":[]})
                    site["runtime"]={"type":"php","version":"8.3"}
        module=types.ModuleType("inventory")
        module.build_manifest=lambda _:manifest
        output=io.StringIO()
        fake_asset={
            job:({"external_present":0,"external_missing":0,"external_unknown":0,
                   "sqlite_header_pass":0,"sqlite_missing":0,"sqlite_unverified":0},
                  {"system_cron":{"expected":0,"staged_count":0,"local_staged_present":0},
                   "user_cron":{"expected":0,"staged_count":0,"local_staged_present":0},
                   "pm2":{"expected":0,"staged_count":0,"local_staged_present":0}})
            for job in ("ORIGINAL17","LEGACY9","LAST2")
        }
        with mock.patch.object(m.baseline,"secure_state",
                side_effect=lambda p:states[p.parent.name]), \
             mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.dict(sys.modules,{"inventory":module}), \
             mock.patch.object(m,"asset_overview",return_value=fake_asset), \
             mock.patch.object(m,"local_service_status",return_value="ACTIVE"), \
             mock.patch.object(m.Path,"is_file",return_value=True), \
             contextlib.redirect_stdout(output):
            m.diagnose()
        return output.getvalue()

    def test_batch_14_sites_and_cutover_denied(self):
        output=self.run_fixture()
        self.assertIn("BATCH=14_STAGED_RUNTIME_ASSET_READONLY",output)
        self.assertIn("CP2_NGINX_SERVICE=ACTIVE",output)
        self.assertEqual(len([line for line in output.splitlines()
                              if line.startswith("SITE=")]),14)
        self.assertIn("PHP_INVENTORY_GAP_COUNT=0",output)
        self.assertIn("EXTERNAL_ASSET_AND_SQLITE_DATA_PARITY=NOT_VERIFIED",output)
        self.assertIn("PHP_FPM_SOCKET_AND_APP_HTTP_SMOKE=NOT_VERIFIED",output)
        self.assertIn("CUTOVER_ALLOWED=NO",output)
        self.assertIn("OLD_SERVER_CONTACTED=NO",output)

    def test_pending_site_still_pending_failure_blocks(self):
        def alter(states):
            states[m.baseline.JOBS[2][1]]["sites"][-1]["stage_status"]="PULLED_STAGED"
        with self.assertRaisesRegex(m.baseline.Block,"STAGED_PENDING_17_SITE_SCOPE_CHANGED"):
            self.run_fixture(alter)

    def test_runtime_activation_never_performed_and_private_asset_guard(self):
        s=fixture.make_states()[m.baseline.JOBS[0][1]]
        s["runtime_assets"]={"system_cron":[{"path":"/etc/cron.d/x"}]}
        s["pending_system_cron"]=[]
        with mock.patch.object(m.Path,"is_file",return_value=False):
            result=m.asset_overview([s,fixture.make_states()[m.baseline.JOBS[1][1]],
                                       fixture.make_states()[m.baseline.JOBS[2][1]]])
        self.assertEqual(result["ORIGINAL17"][1]["system_cron"]["expected"],1)
        self.assertEqual(result["ORIGINAL17"][1]["system_cron"]["staged_count"],0)

    def test_read_only_static_contract(self):
        source=(ROOT/"p07-14-site-runtime-assets-readonly.py").read_text()
        for banned in ("db:import","db:delete","INSERT INTO", "subprocess.Popen",
                       "rsync -","source_remote(","DROP DATABASE","curl ", "chmod("):
            self.assertNotIn(banned,source)
        self.assertIn("OLD_SERVER_CONTACTED=NO",source)
        self.assertIn("DATABASE_WRITES=NONE",source)

if __name__=="__main__":
    unittest.main()
