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
    def test_nested_sqlite_overlay_composed_before_atomic_parent_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,private,states,records,manifest=self.build_private_fixture(tmp)
            _,approved,_=self.check(root,private,states)
            parent=next(x for x in approved if x[0]["category"]=="external"
                        and x[1].is_dir())
            child=next(x for x in approved if x[0]["category"]=="sqlite"
                       and x[3]==parent[3])
            parent_target=parent[2]
            nested_target=parent_target/"nested"/"state.sqlite"
            nested_rec=dict(child[0],source_path=str(nested_target))
            changed=[(nested_rec,child[1],nested_target,child[3]) if x is child else x
                     for x in approved]
            # The fixture's state row is amended only for mode lookup.
            state=next(s for s in states.values() if any(
                row.get("path")==child[0]["source_path"] for row in s.get("sqlite_assets",[])))
            entry=next(row for row in state["sqlite_assets"]
                       if row.get("path")==child[0]["source_path"])
            entry["path"]=str(nested_target)
            roots,overlays=m.plan_nested_assets(changed)
            self.assertEqual(len(roots),29)
            self.assertEqual(len(overlays[parent_target]),1)
            self.assertEqual(len([item for value in overlays.values() for item in value]),1)
            temp=root/"uninstalled-external"
            temp.mkdir()
            (temp/"demo.txt").write_text("source private tree")
            (temp/"nested").mkdir()
            (temp/"nested"/"state.sqlite").write_bytes(b"old live untrusted DB")
            (temp/"nested"/"state.sqlite-wal").write_bytes(b"stale wal")
            before=m.hashfile(child[1])
            with mock.patch.object(m.os,"chown",return_value=None):
                m.overlay_sqlite_snapshots(temp,parent_target,overlays[parent_target],
                                           [(lab,mid,s,"irrelevant") for lab,mid,s
                                            in [(label,jmid,states[jmid])
                                                for label,jmid,_ in m.base.JOBS]],
                                           os.getuid(),os.getgid())
            self.assertEqual(m.hashfile(temp/"nested"/"state.sqlite"),before)
            self.assertTrue(m.snapshot_ok(temp/"nested"/"state.sqlite"))
            self.assertFalse((temp/"nested"/"state.sqlite-wal").exists())
            self.assertEqual(m.hashfile(child[1]),before)
            self.assertEqual((temp/"demo.txt").read_text(),"source private tree")
            self.assertEqual((parent[1]/"demo.txt").read_text(),"safe fixture")
            self.assertFalse(parent_target.exists())

    def test_nested_external_or_file_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root,private,states,_,_=self.build_private_fixture(temp)
            _,approved,_=self.check(root,private,states)
            parent=next(x for x in approved if x[0]["category"]=="external" and x[1].is_dir())
            child=next(x for x in approved if x[0]["category"]=="sqlite")
            illegal_rec=dict(child[0],category="external")
            illegal=(illegal_rec,child[1],parent[2]/"nested"/"file",parent[3])
            changed=[illegal if x is child else x for x in approved]
            roots,nested=m.plan_nested_assets(changed)
            self.assertIn(parent[2],nested)
            self.assertEqual(len(nested[parent[2]]),1)
            # The synthetic external child may only be installed if its
            # staged bytes are absent or identical within the temp root.
            work=root/"external-temp"
            work.mkdir()
            with mock.patch.object(m,"ownership",return_value=None):
                m.compose_nested_externals(work,parent[2],nested[parent[2]],
                                           os.getuid(),os.getgid())
            self.assertEqual(m.hashfile(work/"nested"/"file"),m.hashfile(child[1]))
            bad_parent_rec=dict(parent[0],category="sqlite")
            changed=[(bad_parent_rec,parent[1],parent[2],parent[3]) if x is parent
                     else x for x in approved]
            changed=[(x[0],x[1],parent[2]/"child.sqlite",parent[3])
                     if x is child else x for x in changed]
            with self.assertRaisesRegex(m.Stop,"TARGET_NESTED_PATH_CONFLICT"):
                m.plan_nested_assets(changed)

    def test_nested_sqlite_overlay_rejects_symlink_in_temp_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,private,states,_,_=self.build_private_fixture(tmp)
            _,approved,_=self.check(root,private,states)
            parent=next(x for x in approved if x[0]["category"]=="external" and x[1].is_dir())
            child=next(x for x in approved if x[0]["category"]=="sqlite" and x[3]==parent[3])
            tar=parent[2]/"nested"/"data.sqlite"
            item=(dict(child[0],source_path=str(tar)),child[1],tar,child[3])
            temp=root/"temp-tree"
            temp.mkdir()
            (temp/"nested").symlink_to(root)
            with self.assertRaisesRegex(m.Stop,"OVERLAY_PARENT_SYMLINK_OR_FILE"):
                m.overlay_sqlite_snapshots(temp,parent[2],[item],[],os.getuid(),os.getgid())

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
            with self.assertRaisesRegex(m.Stop,"EXPLICIT_SITE_ASSET_INSTALL_OR_RESUME_ARGUMENT_REQUIRED"):
                m.do_install()
            preflight.assert_not_called()

    def test_job_scoped_sqlite_mode_allows_parent_child_duplicate(self):
        source="/home/example/data.sqlite"
        states=[
            ("ORIGINAL17","a",{"sqlite_assets":[{"path":source,"user":"example","mode":0o600}]},"sha"),
            ("LEGACY9","b",{"sqlite_assets":[{"path":source,"user":"example","mode":0o640}]},"sha"),
        ]
        self.assertEqual(m.snapshot_mode(states,source,"ORIGINAL17","example"),0o600)
        self.assertEqual(m.snapshot_mode(states,source,"LEGACY9","example"),0o640)
        with self.assertRaisesRegex(m.Stop,"SQLITE_SOURCE_IDENTITY_AMBIGUOUS"):
            m.snapshot_mode(states,source,"LAST2","example")
        states[0][2]["sqlite_assets"].append({"path":source,"user":"example","mode":0o600})
        with self.assertRaisesRegex(m.Stop,"SQLITE_SOURCE_IDENTITY_AMBIGUOUS"):
            m.snapshot_mode(states,source,"ORIGINAL17","example")

    def test_manifest_identity_survives_partial_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root,private,states,records,manifest=self.build_private_fixture(temp)
            with mock.patch.object(m.os.path,"lexists",return_value=True):
                got=m.expected_manifest_records(
                    [(label,mid,states[mid],"sha") for label,mid,_ in m.base.JOBS],
                    {(row["job"],row["category"],row["source_path"]) for row in records})
            self.assertEqual(len(got),35)

    def test_resume_from_five_verified_roots_to_thirty_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)
            private=home/"private"
            private.mkdir()
            (private/"external").mkdir()
            targets=home/"targets"
            targets.mkdir()
            approved=[]
            for i in range(30):
                source=private/"external"/("sample-"+str(i))
                source.write_bytes(("content-%02d" % i).encode())
                target=targets/("site-%02d" % i)
                rec={"category":"external","job":"ORIGINAL17",
                     "source_path":"/home/example/file-"+str(i),
                     "sha256":m.hashfile(source)}
                approved.append((rec,source,target,"example"))
                if i<5:target.write_bytes(source.read_bytes())
            initial={"status":"STARTED","installed":[
                {"category":"external","target":str(x[2]),"nested_sqlite":0}
                for x in approved[:5]],
                "pending_temp":None,"cron_activated":False,"cutover_allowed":False}
            progress=private/"cp2-install-progress.json"
            progress.write_text(json.dumps(initial))
            progress.chmod(0o600)
            acct=types.SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())
            original_security=m.security
            def relaxed_security(p,k,root_only=True):
                return original_security(p,k,root_only=False)
            def execute():
                with mock.patch.object(m,"PRIVATE",private), \
                     mock.patch.object(m,"check_manifest",return_value=([],approved,300)), \
                     mock.patch.object(m,"security",side_effect=relaxed_security), \
                     mock.patch.object(m.pwd,"getpwnam",return_value=acct), \
                     mock.patch.object(m,"ensure_parents",return_value=[]), \
                     mock.patch.object(m,"check_parents",return_value=None), \
                     mock.patch.object(m,"ownership",return_value=None), \
                     mock.patch.object(m.os,"geteuid",return_value=0), \
                     mock.patch.object(m.shutil,"disk_usage",
                         return_value=types.SimpleNamespace(free=10*1024**3)), \
                     mock.patch.object(sys,"argv",["tool","--resume-verified-partial-asset-install"]), \
                     contextlib.redirect_stdout(io.StringIO()):
                    return m.do_install()
            self.assertEqual(execute(),0)
            self.assertEqual(json.loads(progress.read_text())["status"],
                             "COPIED_TO_MISSING_PATHS_NOT_CUTOVER_VERIFIED")
            self.assertEqual(len(json.loads(progress.read_text())["installed"]),30)
            self.assertTrue(all(a[2].read_bytes()==a[1].read_bytes() for a in approved))

    def test_progress_rejects_unknown_existing_and_orphan_temp(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            private=root/"private"
            private.mkdir()
            good=private/"sample"
            good.write_bytes(b"good")
            targets=[({"category":"external","sha256":m.hashfile(good)},good,
                      root/("target"+str(i)),"example") for i in range(30)]
            targets[0][2].write_bytes(b"good")
            progress=private/"cp2-install-progress.json"
            payload={"status":"STARTED","installed":[
                {"category":"external","target":str(targets[0][2]),"nested_sqlite":0}],
                "pending_temp":str(root/(".p07-uninstalled-"+"f"*32)),"cron_activated":False,
                "cutover_allowed":False}
            progress.write_text(json.dumps(payload))
            progress.chmod(0o600)
            acct=types.SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())
            original_security=m.security
            with mock.patch.object(m,"security",
                  side_effect=lambda p,k,root_only=True:original_security(p,k,root_only=False)), \
                 mock.patch.object(m.pwd,"getpwnam",return_value=acct):
                loaded,index=m.load_verified_progress(progress,targets,{},[])
                self.assertEqual(index,1)
                self.assertEqual(loaded["pending_temp"],payload["pending_temp"])
                # An exact completed temp may be atomically adopted without
                # clobbering the target or touching private staged data.
                Path(payload["pending_temp"]).write_bytes(b"good")
                with mock.patch.object(m,"check_parents",return_value=None), \
                     mock.patch.object(m,"ownership",return_value=None), \
                     mock.patch.object(m,"PRIVATE",private):
                    self.assertEqual(m.finish_verified_pending(
                        loaded,targets,{},[],index),2)
                self.assertFalse(Path(payload["pending_temp"]).exists())
                self.assertEqual(targets[1][2].read_bytes(),b"good")
                self.assertEqual(good.read_bytes(),b"good")
                # Recreate the original 1-item progress. An unrelated
                # pre-existing target remains a hard fail, with no overwrite.
                payload["pending_temp"]=None
                progress.write_text(json.dumps(payload))
                targets[2][2].write_bytes(b"unrelated")
                with self.assertRaisesRegex(m.Stop,"UNRECORDED_EXISTING_TARGET_REVIEW_REQUIRED"):
                    m.load_verified_progress(progress,targets,{},[])


    def test_sixth_directory_incomplete_is_preserved_then_all_30_resume(self):
        """Realistic interruption: 5 published directories, 6th stale SQLite tree."""
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            private=root/"private"
            external=private/"external"
            sqlite_store=private/"sqlite"
            external.mkdir(parents=True)
            sqlite_store.mkdir()
            home=root/"sites"
            home.mkdir()
            approved=[]
            account=types.SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())
            for i in range(17):
                source=external/("external-%02d" % i)
                source.mkdir()
                (source/"file.txt").write_text("verified-"+str(i))
                if i==5:
                    (source/"db").mkdir()
                    (source/"db"/"data00.sqlite").write_bytes(b"unsafe old live SQLite")
                    (source/"db"/"data00.sqlite-wal").write_bytes(b"stale WAL")
                rec={"category":"external","job":"ORIGINAL17",
                     "source_path":"/home/example/external"+str(i)}
                target=home/("site%02d" % i)
                approved.append((rec,source,target,"example"))
                if i<5: m.shutil.copytree(source,target)
            states=[("ORIGINAL17","a",{"sqlite_assets":[]},""),
                    ("LEGACY9","b",{"sqlite_assets":[]},""),
                    ("LAST2","c",{"sqlite_assets":[]},"")]
            for i in range(13):
                source=sqlite_store/("db%02d.sqlite" % i)
                conn=sqlite3.connect(source)
                conn.execute("CREATE TABLE verified(id INTEGER PRIMARY KEY, payload TEXT)")
                conn.execute("INSERT INTO verified(payload) VALUES (?)",("snapshot-"+str(i),))
                conn.commit()
                conn.close()
                target=home/"site05"/"db"/("data%02d.sqlite" % i)
                source_path="/home/example/db/data%02d.sqlite" % i
                rec={"category":"sqlite","job":"ORIGINAL17",
                     "source_path":source_path,"sha256":m.hashfile(source)}
                # Only the source metadata path identifies the SQLite inventory,
                # while the mapped target is nested inside atomic external root.
                states[0][2]["sqlite_assets"].append(
                    {"path":source_path,"user":"example","mode":0o600})
                approved.append((rec,source,target,"example"))
            original=home/(".p07-uninstalled-"+"a"*32)
            m.shutil.copytree(approved[5][1],original)
            original_view=m.safe_tree_entries(original)
            roots,overlays=m.plan_nested_assets(approved)
            self.assertEqual((len(roots),m.nested_sqlite_count(overlays)),(17,13))
            initial={"status":"STARTED","installed":[
                {"category":"external","target":str(approved[i][2]),"nested_sqlite":0}
                for i in range(5)],
                "pending_temp":str(original),
                "cron_activated":False,"cutover_allowed":False}
            progress=private/"cp2-install-progress.json"
            progress.write_text(json.dumps(initial))
            progress.chmod(0o600)
            for i,(label,mid,state,digest) in enumerate(states):
                job=root/mid
                job.mkdir()
                fn=job/"state.json"
                fn.write_text(json.dumps(state))
                states[i]=(label,mid,state,m.hashfile(fn))
            private_bytes={
                str(p):m.hashfile(p) for p in external.rglob("*") if p.is_file()}
            private_bytes.update({
                str(p):m.hashfile(p) for p in sqlite_store.iterdir()})
            initial_sites={
                str(row[2]):m.safe_tree_entries(row[2]) for row in approved[:5]}
            original_security=m.security
            def guarded_security(p,kind,root_only=True):
                return original_security(p,kind,root_only=False)
            with mock.patch.object(m,"PRIVATE",private), \
                 mock.patch.object(m.base,"ROOT",root), \
                 mock.patch.object(m,"check_manifest",
                                   return_value=(states,approved,512*1024)), \
                 mock.patch.object(m,"security",side_effect=guarded_security), \
                 mock.patch.object(m.pwd,"getpwnam",return_value=account), \
                 mock.patch.object(m,"check_parents",return_value=None), \
                 mock.patch.object(m,"ensure_parents",return_value=[]), \
                 mock.patch.object(m,"ownership",return_value=None), \
                 mock.patch.object(m.os,"chown",return_value=None), \
                 mock.patch.object(m.os,"geteuid",return_value=0), \
                 mock.patch.object(m.shutil,"disk_usage",
                     return_value=types.SimpleNamespace(free=10*1024**3)), \
                 mock.patch.object(sys,"argv",[
                     "tool","--resume-verified-partial-asset-install"]), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(m.do_install(),0)
            self.assertTrue(original.is_dir())
            self.assertEqual(m.safe_tree_entries(original),original_view)
            self.assertTrue(all(m.safe_tree_entries(Path(p))==v
                                for p,v in initial_sites.items()))
            self.assertTrue(all(m.hashfile(Path(p))==v
                                for p,v in private_bytes.items()))
            final=json.loads(progress.read_text())
            self.assertEqual(len(final["installed"]),17)
            self.assertEqual(final["status"],
                             "COPIED_TO_MISSING_PATHS_NOT_CUTOVER_VERIFIED")
            self.assertIsNone(final["pending_temp"])
            self.assertFalse(final["cron_activated"])
            self.assertFalse(final["cutover_allowed"])
            self.assertEqual(len(final["preserved_partial_temps"]),1)
            self.assertEqual(final["preserved_partial_temps"][0]["path"],
                             str(original))
            backups=list(private.glob("cp2-progress-before-resume-*.json"))
            self.assertEqual(len(backups),1)
            self.assertEqual(json.loads(backups[0].read_text()),initial)
            self.assertEqual(sum(row[0]["category"]=="sqlite" for row in approved),13)
            for rec,source,target,user in approved:
                if rec["category"]=="sqlite":
                    self.assertEqual(m.hashfile(target),rec["sha256"])
                    self.assertTrue(m.snapshot_ok(target))
                    self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)
            self.assertFalse((home/"site05"/"db"/"data00.sqlite-wal").exists())
            self.assertIn("ALL_30_LOGICAL_SITE_ASSETS_READBACK=PASS",
                          output.getvalue())
            self.assertIn("INCOMPLETE_PENDING_TEMP=RETAINED_UNMODIFIED",
                          output.getvalue())

    def test_invalid_pending_symlink_blocks_without_progress_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            private=root/"private"
            private.mkdir()
            staged=private/"root"
            staged.mkdir()
            (staged/"good").write_bytes(b"good")
            target=root/"target"
            pending=root/(".p07-uninstalled-"+"b"*32)
            pending.mkdir()
            (pending/"unsafe").symlink_to(private)
            progress={"status":"STARTED","installed":[],"pending_temp":str(pending),
                      "cron_activated":False,"cutover_allowed":False}
            before=json.dumps(progress,sort_keys=True).encode()
            (private/"cp2-install-progress.json").write_bytes(before)
            root_entry=({"category":"external"},staged,target,"example")
            with self.assertRaisesRegex(m.Stop,"ASSET_TREE_SPECIAL_FILE"):
                m.pending_temp_matches(root_entry,[],pending)
            self.assertEqual((private/"cp2-install-progress.json").read_bytes(),before)
            self.assertTrue((pending/"unsafe").is_symlink())
            self.assertFalse(target.exists())

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
