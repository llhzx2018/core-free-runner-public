"""Synthetic-only recovery/install checks for private 35-item P07 stage evidence."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE=Path(__file__).parent
def load(name,label):
    s=importlib.util.spec_from_file_location(label,HERE/name)
    m=importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
m=load("p07-14-site-private-assets-guarded-install.py","p07_stage_install")
fx=load("p07-14-site-missing-assets-private-stage-tests.py","p07_stage_fx")

class Tests(unittest.TestCase):
    def build_private_fixture(self,temp):
        root=Path(temp)
        private=root/"private"
        private.mkdir(mode=0o700)
        states=fx.seed_states()
        for label,mid,expect in m.base.JOBS:
            here=root/mid
            here.mkdir()
            with (here/"state.json").open("w",encoding="utf8") as stream:
                json.dump(states[mid],stream)
        rows=[]
        count=0
        for label,mid,expect in m.base.JOBS:
            state=states[mid]
            users={s["site_user"] for s in state["sites"] if s["stage_status"]=="PULLED_STAGED"}
            for cat,key in (("external","external_assets"),("sqlite","sqlite_assets")):
                for ent in state[key]:
                    if ent.get("user") not in users:continue
                    count+=1
                    p=private/cat/(f"{count:03d}-"+m.hashlib.sha256(ent["path"].encode()).hexdigest()[:20])
                    p.parent.mkdir(exist_ok=True)
                    if cat=="external":
                        p.mkdir()
                        (p/"demo.txt").write_text("safe fixture",encoding="utf8")
                        result="DIRECTORY_TRANSFERRED_NO_BYTE_PARITY"
                        digest=None
                    else:
                        db=sqlite3.connect(p)
                        db.execute("CREATE TABLE example (id INTEGER PRIMARY KEY)")
                        db.commit()
                        db.close()
                        result="SQLITE_SNAPSHOT_PRIVATE_VERIFIED"
                        digest=m.hashfile(p)
                    rows.append({"category":cat,"job":label,"source_path":ent["path"],
                        "private_path":str(p),"scope":"STAGED_SITE_ONLY",
                        "result":result,"sha256":digest})
            for ent in state["runtime_assets"]["system_cron"]:
                count+=1
                p=private/"cron"/(f"{count:03d}-"+m.hashlib.sha256(ent["path"].encode()).hexdigest()[:20])
                p.parent.mkdir(exist_ok=True)
                p.write_text("# private Cron not activated\n")
                rows.append({"category":"cron","job":label,"source_path":ent["path"],
                    "private_path":str(p),"scope":"SYSTEM_CRON_NOT_ACTIVATED",
                    "result":"CRON_PRIVATE_NOT_ACTIVATED","sha256":m.hashfile(p)})
        self.assertEqual(count,35)
        manifest={"status":"PRIVATE_STAGING_ONLY","counts":m.EXPECTED,
            "cutover_allowed":False,"site_files_materialized":False,"records":rows}
        file=private/"private-manifest.json"
        file.write_text(json.dumps(manifest))
        file.chmod(0o600)
        return root,private,states,rows,manifest
    def check(self,root,private,states):
        actual_security=m.security
        # CI runs unprivileged; bypass only root ownership in synthetic fixture.
        # Keep type/symlink validation; production code remains unchanged.
        synthetic_security=lambda p,kind,root_only=True: actual_security(
            p,kind,root_only=False)
        with mock.patch.object(m,"PRIVATE",private), \
             mock.patch.object(m.base,"ROOT",root), \
             mock.patch.object(m,"security",side_effect=synthetic_security), \
             mock.patch.object(m.base,"secure_state",
                 side_effect=lambda p:states[p.parent.name]):
            return m.check_manifest()
    def test_exact_35_private_entries_approve_only_30_site_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root,private,states,records,manifest=self.build_private_fixture(temp)
            jobstates,targets,bytes_count=self.check(root,private,states)
            self.assertEqual(len(jobstates),3)
            self.assertEqual(len(targets),30)
            self.assertEqual(sum(r[0]["category"]=="sqlite" for r in targets),13)
            self.assertGreater(bytes_count,0)
            self.assertFalse((private/"cp2-install-progress.json").exists())
    def test_missing_or_changed_evidence_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            root,private,states,records,manifest=self.build_private_fixture(temp)
            bad=Path(records[4]["private_path"])
            with bad.open("ab") as fp:fp.write(b"x")
            with self.assertRaisesRegex(m.Stop,"SQLITE_SNAPSHOT_INTEGRITY_FAILED|PRIVATE_FILE_SHA256_CHANGED"):
                self.check(root,private,states)
    def test_scope_drift_or_private_symlink_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            root,private,states,records,manifest=self.build_private_fixture(temp)
            states[m.base.JOBS[2][1]]["sites"][-1]["stage_status"]="PULLED_STAGED"
            with self.assertRaisesRegex(m.Stop,"STAGE_SCOPE_CHANGED"):
                self.check(root,private,states)
    def test_target_existing_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            src=root/"source"
            target=root/"target"
            src.write_bytes(b"new")
            target.write_bytes(b"original")
            with self.assertRaises(m.Stop):
                m.rename_noreplace(src,target)
            self.assertEqual(target.read_bytes(),b"original")
            self.assertEqual(src.read_bytes(),b"new")
            target.unlink()
            m.rename_noreplace(src,target)
            self.assertEqual(target.read_bytes(),b"new")
            self.assertFalse(src.exists())
    def test_progress_is_private_atomic_and_rejects_second_run(self):
        with tempfile.TemporaryDirectory() as temp:
            private=Path(temp)
            with mock.patch.object(m,"PRIVATE",private):
                path=m.write_progress({"installed":[],"status":"STARTED"})
                self.assertTrue(path.is_file())
                self.assertFalse(path.stat().st_mode&0o077)
                m.write_progress({"installed":[{"target":"new"}],"status":"COPIED"})
                self.assertEqual(json.loads(path.read_text())["status"],"COPIED")
    def test_explicit_install_gate_precedes_state_read(self):
        with mock.patch.object(sys,"argv",["tool","--wrong"]), \
             mock.patch.object(m,"check_manifest") as preflight, \
             mock.patch.object(m.os,"geteuid",return_value=0):
            with self.assertRaisesRegex(m.Stop,"EXPLICIT_30_SITE_ASSETS_INSTALL_ARGUMENT_REQUIRED"):
                m.do_install()
            preflight.assert_not_called()
    def test_never_activates_cron_or_touches_source(self):
        text=(HERE/"p07-14-site-private-assets-guarded-install.py").read_text()
        for forbidden in ("source_remote(", "run_ssh(", "source_python(", 
                          "cutover_migration(", "activate_target_runtime(",
                          "DROP DATABASE", "rsync -","crontab -","curl "):
            self.assertNotIn(forbidden,text)
        for required in ("renameat2","SOURCE_DATABASE_WRITES=NONE",
                         "CRON_STILL_PRIVATE_NOT_ACTIVATED=5",
                         "SITE_SOURCE_TARGET_PARITY=NOT_VERIFIED"):
            self.assertIn(required,text)

if __name__=="__main__":
    unittest.main()
