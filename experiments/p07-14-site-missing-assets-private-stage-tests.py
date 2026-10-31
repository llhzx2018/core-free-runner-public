"""P07 private asset batch: safety and exact-scope synthetic tests only."""
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

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("p07_assetstage",HERE/"p07-14-site-missing-assets-private-stage.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
fspec=importlib.util.spec_from_file_location("p07_assetfixture",HERE/"p07-17-site-staged-local-evidence-tests.py")
f=importlib.util.module_from_spec(fspec)
fspec.loader.exec_module(f)

def seed_states():
    states=f.make_states()
    distribution=[
        (0,4,5,2),(1,13,8,2),(2,0,0,1),
    ]
    for idx,ext_count,sql_count,cron_count in distribution:
        mid=m.base.JOBS[idx][1]
        state=states[mid]
        users=[s["site_user"] for s in state["sites"] if s["stage_status"]=="PULLED_STAGED"]
        state["source"]={"ssh_user":"root","host":"old.example.test","ssh_port":22}
        state["source_runtime_path"]=f"/var/lib/vf-server-ops/pull-source/{mid}/runtime"
        state["source_server_identity"]="old-stable"
        state["external_assets"]=[
            {"path":f"/home/{users[j%len(users)]}/external-{j}","user":users[j%len(users)],
             "kind":"DIRECTORY"} for j in range(ext_count)
        ]
        state["sqlite_assets"]=[
            {"path":f"/home/{users[j%len(users)]}/database-{j}.sqlite",
             "user":users[j%len(users)],"mode":0o600} for j in range(sql_count)
        ]
        state["runtime_assets"]={
            "system_cron":[{"path":f"/etc/cron.d/job{idx}-{j}"} for j in range(cron_count)],
            "user_cron":[],"pm2":[]
        }
    return states

class Tests(unittest.TestCase):
    def get_rows(self,states):
        with mock.patch.object(m.base,"secure_state",side_effect=lambda p:states[p.parent.name]), \
             mock.patch.object(m.os.path,"lexists",return_value=False):
            return m.stage_rows()

    def test_exact_17_13_5_scope_and_old_protected(self):
        states=seed_states()
        _, rows=self.get_rows(states)
        count={category:sum(item[0]==category for item in rows) for category in m.EXPECTED}
        self.assertEqual(count,{"external":17,"sqlite":13,"cron":5})
        self.assertTrue(all(item[4]!="root" for item in rows if item[0]!="cron"))
        self.assertEqual(sum(item[0]=="cron" for item in rows),5)
        self.assertEqual(set(state["status"] for state in states.values()),{"PREPARE_FAILED"})

    def test_duplicate_or_changed_scope_denied_before_copy(self):
        states=seed_states()
        states[m.base.JOBS[0][1]]["external_assets"].pop()
        with self.assertRaisesRegex(m.Block,"ACTUAL_MISSING_ASSET_SCOPE_CHANGED"):
            self.get_rows(states)
        states=seed_states()
        states[m.base.JOBS[1][1]]["sites"][6]["stage_status"]="PULLED_STAGED"
        with self.assertRaisesRegex(m.Block,"STAGED_SCOPE_DRIFT"):
            self.get_rows(states)

    def test_identical_cron_path_across_jobs_is_safe_private_duplicate(self):
        states=seed_states()
        first=states[m.base.JOBS[0][1]]["runtime_assets"]["system_cron"][0]["path"]
        states[m.base.JOBS[1][1]]["runtime_assets"]["system_cron"][0]["path"]=first
        _,rows=self.get_rows(states)
        self.assertEqual(sum(r[0]=="cron" for r in rows),5)
        self.assertEqual(sum(str(r[3])==first for r in rows),2)

    def test_unsafe_path_and_protected_existing_file(self):
        with self.assertRaisesRegex(m.Block,"ASSET_OUTSIDE_SITE_USER_ROOT"):
            m.validate_asset_path({"path":"/etc/shadow"},"site")
        with self.assertRaisesRegex(m.Block,"ASSET_OUTSIDE_SITE_USER_ROOT"):
            m.validate_asset_path({"path":"/home/site/../other/db"},"site")
        states=seed_states()
        with mock.patch.object(m.base,"secure_state",side_effect=lambda p:states[p.parent.name]), \
             mock.patch.object(m.os.path,"lexists",side_effect=lambda path: "external-0" in str(path)):
            with self.assertRaisesRegex(m.Block,"ACTUAL_MISSING_ASSET_SCOPE_CHANGED"):
                m.stage_rows()

    def test_preflight_capacity_checks_no_transfer(self):
        rows=[("external","ORIGINAL17",{"source":{"ssh_user":"root"}},
               Path("/home/example/data"),"example",{})]
        server=types.SimpleNamespace(source_remote=lambda *a,**kw:
            subprocess.CompletedProcess([],0,"500\t/home/example/data\n",""))
        with mock.patch.object(m.shutil,"disk_usage",return_value=types.SimpleNamespace(free=2*1024**3)), \
             contextlib.redirect_stdout(io.StringIO()):
            m.source_space_preflight(server,rows)
        with mock.patch.object(m.shutil,"disk_usage",return_value=types.SimpleNamespace(free=1024**3)):
            with self.assertRaisesRegex(m.Block,"INSUFFICIENT_CP2_PRIVATE_STAGE_SPACE"):
                m.source_space_preflight(server,rows)

    def test_private_copy_operator_never_writes_site_paths(self):
        code=(HERE/"p07-14-site-missing-assets-private-stage.py").read_text()
        for prohibited in (
            "create_target_site(", "sync_sqlite_assets(", "sync_external_assets(",
            "resume_prepare_migration(", "os.replace(", "shutil.copy2(",
            "source_nginx_stop(", "CUTOVER_PULL:", "DROP DATABASE",
            "activate_target_runtime(", "DNS_CHANGED=YES",
        ):
            self.assertNotIn(prohibited,code)
        self.assertIn("site_files_materialized",code)
        self.assertIn("SITE_PATHS_MODIFIED=NO",code)
        self.assertIn("CRON_ACTIVATED=NO",code)
        self.assertIn("SOURCE_TEMP_SQLITE_SNAPSHOTS_CLEANED=REQUESTED",code)
        self.assertIn("STAGED_ASSET_COUNTS=",code)

    def test_synthetic_full_35_item_private_recovery_without_site_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            records=[]
            state={"migration_id":m.base.JOBS[0][1],"source":{"ssh_user":"root"},
                   "source_runtime_path":"/var/lib/vf-server-ops/pull-source/fixture/runtime"}
            for i in range(17):
                records.append(("external","ORIGINAL17",state,
                    Path("/home/site/external"+str(i)),"site",
                    {"kind":"FILE"}))
            for i in range(13):
                records.append(("sqlite","ORIGINAL17",state,
                    Path("/home/site/data"+str(i)+".sqlite"),"site",{}))
            for i in range(5):
                records.append(("cron","ORIGINAL17",state,
                    Path("/etc/cron.d/job"+str(i)),"root",{}))
            for _,mid,_ in m.base.JOBS:
                s=root/mid
                s.mkdir()
                (s/"state.json").write_text('{"synthetic":true}')
            evidence=root/"recovery"
            evidence.mkdir()
            remote_calls=[]
            fake=types.SimpleNamespace(
                source_path_kind=lambda *a,**k:"FILE",
                source_python=lambda *a,**k:subprocess.CompletedProcess([],0,"",""),
                source_remote=lambda *a,**k:(remote_calls.append((a,k)) or
                    subprocess.CompletedProcess([],0,"","")),
            )
            copied=[]
            def copier(migration,cat,from_state,source,out,kind,user):
                out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(b"synthetic private sample")
                copied.append((cat,str(out)))
                return "FILE_TRANSFERRED_HASHED"
            result=io.StringIO()
            with mock.patch.object(sys,"argv",["p07-asset","--stage-exact-missing-assets-private-only"]), \
                 mock.patch.object(m,"stage_rows",return_value=([],records)), \
                 mock.patch.object(m,"prepare_engine",return_value=fake), \
                 mock.patch.object(m,"source_space_preflight"), \
                 mock.patch.object(m,"create_evidence_folder",return_value=evidence), \
                 mock.patch.object(m,"copy_to_private",side_effect=copier), \
                 mock.patch.object(m,"local_sqlite_ok",return_value=True), \
                 mock.patch.object(m.base,"ROOT",root), \
                 contextlib.redirect_stdout(result):
                self.assertEqual(m.stage(),0)
            manifest=json.loads((evidence/"private-manifest.json").read_text())
            self.assertEqual(manifest["counts"],{"external":17,"sqlite":13,"cron":5})
            self.assertFalse(manifest["site_files_materialized"])
            self.assertFalse(manifest["cutover_allowed"])
            self.assertEqual(len(manifest["records"]),35)
            self.assertEqual(len(copied),35)
            self.assertEqual(len(remote_calls),18)
            self.assertIn("SITE_PATHS_MODIFIED=NO",result.getvalue())
            self.assertIn("CUTOVER_ALLOWED=NO",result.getvalue())
            self.assertNotIn("password",result.getvalue().lower())

    def test_exact_argument_required_before_preflight(self):
        with mock.patch.object(sys,"argv",["asset-stage","--unsafe"]), \
             mock.patch.object(m,"stage_rows") as check:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_PRIVATE_STAGE_ARGUMENT_REQUIRED"):
                m.stage()
            check.assert_not_called()

if __name__=="__main__":
    unittest.main()
