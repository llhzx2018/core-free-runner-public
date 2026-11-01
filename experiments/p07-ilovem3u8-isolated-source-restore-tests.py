"""Synthetic safeguards for one-time ilovem3u8 SOURCE -> isolated CP2 DB staging.

No real VPS, DB, CloudPanel, SSH or business data. Test does not enter Production.
"""
from __future__ import annotations
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

P=Path(__file__).with_name("p07-ilovem3u8-isolated-source-restore.py")
spec=importlib.util.spec_from_file_location("p07_ilove_isolated",P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Engine:
    def __init__(self,hash_value="a"*64,fail_export=False):
        self.commands=[]
        self.hash=hash_value
        self.fail_export=fail_export
    def source_remote(self,src,cmd,timeout,check):
        self.commands.append((cmd,timeout,check))
        if "SOURCE_EXPORT_READY" in cmd:
            return subprocess.CompletedProcess([],13 if self.fail_export else 0,
                "" if self.fail_export else "SOURCE_EXPORT_READY=YES","")
        if "sha256sum --" in cmd:
            return subprocess.CompletedProcess([],0,self.hash+"  /private/archive\n","")
        return subprocess.CompletedProcess([],0,"","")
    def pull_path(self,source,remote,dest):
        Path(dest).write_bytes(b"synthetic private gzip bytes")
class CloudPanel(types.ModuleType):
    def __init__(self):
        super().__init__("cloudpanel")
        self.calls=[]
        self.CloudPanelError=type("CloudPanelError",(Exception,),{})
    def add_database(self,domain,db,user,pw,clpctl=None):
        self.calls.append((domain,db,user,pw,clpctl))

class TestIsolated(unittest.TestCase):
    def test_output_protection_and_one_attempt(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.object(m,"ROOT",Path(root)/"scratch"):
            src_engine=Engine()
            cp=CloudPanel()
            target_id="original-target"
            state={"source":{"private":"SENSITIVE_DATA"},
                "source_runtime_path":"/var/lib/vf-server-ops/pull-source/"+m.MID+"/runtime",
                "status":"PREPARE_FAILED","source_runtime_frozen":False,
                "dns_changed_by_p07":False,"source_delete_allowed":False,
                "existing_target_overwrite_allowed":False}
            pair=types.ModuleType("p07_pair")
            base=types.ModuleType("p07_www3")
            base.REMOTE_EXPORT="print('SOURCE_EXPORT_READY=YES')"
            base.inspect_archive=lambda _p:(234,42)
            base.sha256_file=lambda _p:"a"*64
            base._master_sql_presence=lambda db,user:(
                ("1","1") if cp.calls else ("0","0"))
            base.isolated_import=lambda *args:True
            fns=[]
            original=m.load
            def load(filename,name):
                if filename=="p07-two-pending-live-db-parity.py":return pair
                if filename=="p07-www3-isolated-restore.py":return base
                return types.ModuleType("p07_base_worker")
            engine_module=types.ModuleType("server_migration_pull")
            inventory=types.ModuleType("inventory")
            for item in ["source_remote","pull_path"]:
                setattr(engine_module,item,getattr(src_engine,item))
            buffer=io.StringIO()
            with mock.patch.object(m,"load",side_effect=load), \
                 mock.patch.object(m,"preflight",
                   return_value=(state,"original-source",target_id)), \
                 mock.patch.object(m,"panel_link_count",return_value=1), \
                 mock.patch.object(m,"readback",return_value=(42,1013)), \
                 mock.patch.object(sys,"argv",["app","--restore-fresh-source-to-new-isolated-ilovem3u8-db"]), \
                 mock.patch.dict(sys.modules,{"server_migration_pull":engine_module,
                        "cloudpanel":cp,"inventory":inventory}), \
                 contextlib.redirect_stdout(buffer):
                result=m.run()
            self.assertEqual(result,0)
            record=json.loads((m.ROOT/"status.json").read_text())
            self.assertEqual(record["status"],"ISOLATED_SOURCE_READBACK_PASS")
            self.assertEqual(record["readback_tables"],42)
            self.assertEqual(record["readback_rows"],1013)
            self.assertFalse(record["cutover_allowed"])
            self.assertTrue(record["original_target_preserved"])
            self.assertEqual(len(cp.calls),1)
            self.assertEqual(cp.calls[0][0],m.DOMAIN)
            self.assertIn(cp.calls[0][1].split("-")[0],"p07scratch")
            self.assertEqual(len(src_engine.commands),3)
            self.assertTrue(all(cmd[2] is False for cmd in src_engine.commands))
            self.assertIn("SOURCE_SNAPSHOT_ROW_VALUE_PARITY=NOT_VERIFIED",
                          buffer.getvalue())
            for secret in ("SENSITIVE_DATA","original-source","original-target",
                           cp.calls[0][3],cp.calls[0][1],cp.calls[0][2]):
                self.assertNotIn(secret,buffer.getvalue())
            self.assertIn("ORIGINAL_TARGET_DATABASE_MODIFIED=NO",buffer.getvalue())
            self.assertIn("CUTOVER_ALLOWED=NO",buffer.getvalue())
            self.assertTrue((m.ROOT/"source.sql.gz").exists())
            self.assertTrue((m.ROOT/"scratch-credentials.json").exists())
            self.assertEqual((m.ROOT/"status.json").stat().st_mode&0o077,0)
            with mock.patch.object(m,"panel_link_count",return_value=1):
                pass
            self.assertTrue(m.ROOT.exists())  # No deletion or automatic retry.
    def test_literal_boundary_and_no_existing_db_dml(self):
        source=P.read_text()
        for forbidden in ("DROP DATABASE","DELETE FROM", "UPDATE ",
                          "REPLACE INTO","cutover_migration(", "source_freeze(",
                          "os.system(","subprocess.run([\"bash\""):
            self.assertNotIn(forbidden,source)
        self.assertIn("SCRATCH_FREE_DISK_BELOW_2GB",source)
        self.assertIn("ISOLATED_SOURCE_READBACK=PASS",source)
        self.assertIn("SOURCE_SNAPSHOT_ROW_VALUE_PARITY=NOT_VERIFIED",source)
        self.assertIn("SCRATCH_DB_CREATION_STARTED",source)
        self.assertIn("SOURCE_SNAPSHOT_TRANSFER_HASH_MISMATCH",source)
        self.assertIn("ISOLATED_SOURCE_RESTORE_ALREADY_ATTEMPTED",source)
        self.assertIn("CUTOVER_ALLOWED=NO",source)
    def test_invalid_arg_fails_before_loading_any_helper(self):
        with mock.patch.object(sys,"argv",["app","--overwrite-db"]), \
             mock.patch.object(m,"load") as fetch:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_ISOLATED_RESTORE_MODE_REQUIRED"):
                m.run()
            fetch.assert_not_called()
    def test_incomplete_manifest_and_unsafe_status_stops(self):
        pair=types.SimpleNamespace(
            SITES=[None,("ilovem3u8.kewaro.com",m.MID,17,7,42)],
            ENGINE_BLOB="a"*40)
        # CP2 real preflight performs strict identity before any writes;
        # isolated class uses it rather than altering legacy migration state.
        content=P.read_text()
        self.assertIn("pair.preflight(engine,inventory,*pair.SITES[1])",content)
        self.assertIn("existing_target_overwrite_allowed",content)
        self.assertIn("source_delete_allowed",content)
        self.assertIn("ORIGINAL_TARGET_DATABASE_PRESERVED=YES",content)
        self.assertIn("SCRATCH_NAMES_EXIST_OR_CANNOT_BE_PROVEN_ABSENT",content)
if __name__=="__main__":
    unittest.main()
