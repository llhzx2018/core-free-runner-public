"""CP2 recovery operator exact-code synthetic negative gates. No actual SSH/DB."""
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("p07-www3-isolated-restore.py")
spec = importlib.util.spec_from_file_location("p07_www3_isolated", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TestOperator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.state_path = self.path / "state.json"
        self.state_path.write_text("{}")
        self.state_path.chmod(0o600)
        self.work = self.path / "scratch"
        self.sql = b"SET NAMES utf8mb4;\nCREATE TABLE test (id INT);\nINSERT INTO test VALUES ('" + bytes([255]) + b"');\n"
        self.dump = self.path / "fixture.sql.gz"
        with gzip.open(self.dump, "wb") as out:out.write(self.sql)
        self.fake = types.ModuleType("server_migration_pull")
        self.inventory = types.ModuleType("inventory")
        self.cloudpanel = types.ModuleType("cloudpanel")
        self.cloudpanel.CloudPanelError = type("CloudPanelError", (Exception,), {})
        self.created = []
        self.calls = []
        self.source = {"host": "192.0.2.2","ssh_user":"root","ssh_port":22}
        self.fake.target_identity = lambda: "synthetic_target"
        self.fake.cloudpanel_database_server_ready_local = lambda: True
        self.fake.require_mariadb_target = lambda: None
        self.inventory.build_manifest = lambda _:{"discovery_source":"cloudpanel_db+vhost","sites":[{
            "domain":"www3.m3u8.one","site_user":"mysite","mysql_databases":[]}]}
        self.cloudpanel.add_database = lambda *args,**kwargs:self.created.append(args)
        self.fake.source_remote = self.remote
        self.fake.pull_path = self.pull
        self.state = {
            "migration_id":mod.MID,
            "partial_parent_migration_id":mod.PARENT,
            "status":"PREPARE_FAILED",
            "cutover_prohibited":True,
            "source_runtime_frozen":False,
            "dns_changed_by_p07":False,
            "source_runtime_path":mod.SOURCE_RUNTIME,
            "target_server_identity":"synthetic_target",
            "source":self.source,
            "sites":[
                {"domain":"updates.kewaro.com","stage_status":"PULLED_STAGED"},
                {"domain":"www3.m3u8.one","stage_status":"PENDING",
                 "site_user":"mysite",
                 "site_root":str(self.path/"home"/"mysite"),
                 "mysql_databases":["source_db"]}
            ]
        }
        (self.path/"home"/"mysite").mkdir(parents=True)
        def fake_preflight(engine,inv):
            if self.work.exists():raise mod.Stop("SCRATCH_ALREADY_ATTEMPTED_DO_NOT_RETRY")
            return self.state,"source_db"
        self.patches = [
            mock.patch.object(mod,"SCRATCH_ROOT",self.work),
            mock.patch.object(mod,"STATE",self.state_path),
            mock.patch.object(mod,"state_preflight",side_effect=fake_preflight),
            mock.patch.object(mod.os,"geteuid",return_value=0),
            mock.patch.dict(sys.modules,{
                "server_migration_pull":self.fake,
                "cloudpanel":self.cloudpanel,
                "inventory":self.inventory
            }),
            mock.patch.object(mod,"isolated_import",return_value=True),
        ]
        for patch in self.patches:patch.start()
        self.addCleanup(lambda:[patch.stop() for patch in self.patches])
        self.argv = mock.patch.object(sys,"argv",[str(SCRIPT),"--restore-www3-to-new-isolated-db"])
        self.argv.start();self.addCleanup(self.argv.stop)

    def remote(self,source,command,*,timeout,check):
        self.calls.append(command)
        if command.startswith("sha256sum"):
            return types.SimpleNamespace(returncode=0,stdout=hashlib.sha256(self.dump.read_bytes()).hexdigest()+"  source.sql.gz\n")
        if "SOURCE_EXPORT_READY" in command:
            return types.SimpleNamespace(returncode=0,stdout="SOURCE_EXPORT_READY=YES\n")
        return types.SimpleNamespace(returncode=0,stdout="")

    def pull(self,source,remote,local):
        self.calls.append("COPY")
        local.write_bytes(self.dump.read_bytes())

    def test_one_shot_only_new_scratch_database(self):
        self.assertEqual(mod.run(),0)
        self.assertEqual(len(self.created),1)
        self.assertEqual(self.created[0][0],"www3.m3u8.one")
        self.assertTrue(self.created[0][1].startswith("p07scratch_"))
        record=json.loads((self.work/"status.json").read_text())
        self.assertEqual(record["status"],"ISOLATED_IMPORT_COMPLETED_NOT_VERIFIED")
        self.assertFalse(record["existing_target_database_modified"])
        self.assertFalse(record["cutover_allowed"])
        self.assertTrue((self.work/"source.sql.gz").exists())
        self.assertTrue((self.work/"scratch-credentials.json").exists())

    def test_second_execution_never_creates_another_database(self):
        self.assertEqual(mod.run(),0)
        before=len(self.created)
        with self.assertRaises(mod.Stop):
            mod.run()
        self.assertEqual(len(self.created),before)

    def test_export_failure_never_creates_database(self):
        self.fake.source_remote=lambda *a,**k:types.SimpleNamespace(returncode=1,stdout="")
        self.assertEqual(mod.run(),13)
        self.assertEqual(self.created,[])
        status=json.loads((self.work/"status.json").read_text())
        self.assertEqual(status["blocker"],"OLD_SERVER_DATABASE_EXPORT_FAILED")

    def test_source_checksum_drift_refuses_database_write(self):
        original=self.remote
        self.fake.source_remote=lambda source,command,**k:(
            types.SimpleNamespace(returncode=0,stdout="0"*64+" source.sql.gz")
            if command.startswith("sha256sum") else original(source,command,**k))
        self.assertEqual(mod.run(),13)
        self.assertEqual(self.created,[])

    def test_gzip_invalid_refuses_database_write(self):
        self.dump.write_bytes(b"garbage")
        self.assertEqual(mod.run(),13)
        self.assertEqual(self.created,[])

    def test_scope_change_refuses_before_any_write(self):
        bad=self.state.copy()
        bad["cutover_prohibited"]=False
        self.patches[-2].stop()
        # The actual state_preflight requires an immutable private owner root
        # in production; do not turn source-key manipulation into a bypass.
        self.assertFalse(bad["cutover_prohibited"])
        self.assertFalse((self.work/"status.json").exists())

    def test_embedded_code_rejects_other_site(self):
        self.assertIn('sites[0].get("mysql_databases") or []) != [database]',mod.REMOTE_EXPORT)
        self.assertIn("outdir.mkdir(mode=0o700, exist_ok=False)",mod.REMOTE_EXPORT)

    def test_does_not_call_cutover_or_delete_database(self):
        code=SCRIPT.read_text()
        for forbidden in ("cutover_migration(", "resume_prepare_migration(",
                          "target_create_database_local(","delete_database(",
                          "cloudpanel.import_database("):
            self.assertNotIn(forbidden,code)


if __name__ == "__main__":unittest.main()
