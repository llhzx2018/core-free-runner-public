"""No real VPS, SSH, or database; negative bounds for last-two staging."""
import copy, importlib.util, json, os, stat, tempfile
from pathlib import Path
from unittest import mock
import unittest

p = Path(__file__).with_name("p07-release113-last-two-stage.py")
spec = importlib.util.spec_from_file_location("p07_last_two", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def state_pair():
    sites=[]
    for i in range(17):
        domain=m.PARENT_DOMAINS[i]
        sites.append(dict(domain=domain,site_user=f"user{i}",
                          site_root=f"/home/user{i}",document_root=f"/home/user{i}/htdocs",
                          runtime={"type":"php","version":"8.3"},
                          mysql_databases=[f"db{i}"] if i in (14,16) else [],
                          stage_status="PENDING"))
    a=dict(schema=m.SCHEMA,migration_id=m.ORIGINAL,status="PREPARE_FAILED",
           last_sql_guard_failure={"reason":"CONDITIONAL_DDL"},
           source=dict(host="192.0.2.1",ip="192.0.2.1",ssh_user="root",ssh_port=22),
           source_server_identity="sha256:synthetic-source",
           target_server_identity="sha256:synthetic-target",
           source_runtime_frozen=False,target_runtime_activated=False,
           dns_changed_by_p07=False,source_delete_allowed=False,
           existing_target_overwrite_allowed=False,sites=sites)
    for row in a["sites"][:7]: row["stage_status"]="PULLED_STAGED"
    b=copy.deepcopy(a)
    b.update(migration_id=m.NINE_CHILD,partial_parent_migration_id=m.ORIGINAL,
             cutover_prohibited=True,last_sql_guard_failure={"reason":"CONDITIONAL_DDL"},
             sites=copy.deepcopy(sites[8:]))
    for row in b["sites"][:6]: row["stage_status"]="PULLED_STAGED"
    return a,b

class Tests(unittest.TestCase):
    def test_exact_scope(self):
        a,b=state_pair()
        baseline=json.dumps([a,b],sort_keys=True)
        self.assertEqual([r["domain"] for r in m.prove_original_and_child(a,b)],list(m.DOMAINS))
        self.assertEqual(baseline,json.dumps([a,b],sort_keys=True))

    def test_status_and_cutover_fail_closed(self):
        for which,key,value in [
            ("a","status","PREPARED"),("b","status","PREPARED"),
            ("b","cutover_prohibited",False),
            ("a","last_sql_guard_failure",None),
            ("a","last_sql_guard_failure",{"reason":"OTHER"}),
            ("b","last_sql_guard_failure",None),
            ("b","source_runtime_frozen",True),
            ("b","dns_changed_by_p07",True),
            ("b","source_server_identity","wrong"),
            ("b","target_server_identity","wrong"),
            ("b","partial_parent_migration_id","wrong")]:
            with self.subTest(which=which,key=key):
                a,b=state_pair()
                (a if which=="a" else b)[key]=value
                with self.assertRaises(m.Stop):m.prove_original_and_child(a,b)

    def test_real_november_1_identity_and_order(self):
        self.assertEqual(m.ORIGINAL, "pull-20261101T045943Z-923729a1")
        self.assertEqual(m.NINE_CHILD, "pull-20261101T052411Z-35663c25")
        self.assertEqual(m.PARENT_DOMAINS[7], "ilovem3u8.kewaro.com")
        self.assertEqual(m.NINE_DOMAINS[6], "unzip.kewaro.com")
        self.assertEqual(list(m.DOMAINS), list(m.PARENT_DOMAINS[-2:]))

    def test_parent_prefix_and_pending_tail_are_immutable(self):
        for index, changed in ((0,"PENDING"),(6,"PENDING"),(7,"PULLED_STAGED"),
                               (14,"PULLED_STAGED"),(15,"PULLED_STAGED"),(16,"PULLED_STAGED")):
            a,b=state_pair()
            a["sites"][index]["stage_status"]=changed
            with self.subTest(index=index), self.assertRaises(m.Stop):
                m.prove_original_and_child(a,b)

    def test_parent_site_order_and_original_guard_are_required(self):
        for index in (0,7,14,16):
            a,b=state_pair()
            a["sites"][index]["domain"]="modified.example.test"
            with self.subTest(index=index), self.assertRaises(m.Stop):
                m.prove_original_and_child(a,b)

    def test_no_restage_unzip_or_six_or_last_two(self):
        for index,stage in [(0,"PENDING"),(6,"PULLED_STAGED"),(7,"PULLED_STAGED"),(8,"PULLED_STAGED")]:
            a,b=state_pair()
            b["sites"][index]["stage_status"]=stage
            with self.subTest(index=index),self.assertRaises(m.Stop):
                m.prove_original_and_child(a,b)

    def test_scope_drift_rejected(self):
        for site_index,field,value in [(7,"site_user","different"),
                         (8,"mysql_databases",[]),(7,"document_root","/wrong"),
                         (6,"domain","different.invalid")]:
            a,b=state_pair()
            b["sites"][site_index][field]=value
            with self.subTest(site=site_index,field=field),self.assertRaises(m.Stop):
                m.prove_original_and_child(a,b)

    def test_existing_child_is_not_resumable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,parent in [("nine",m.ORIGINAL),("two",m.NINE_CHILD),
                                ("sibling",m.ORIGINAL)]:
                x=root/name;x.mkdir()
                (x/"state.json").write_text(json.dumps({
                    "partial_parent_migration_id":parent,
                    "migration_id":m.NINE_CHILD if name=="nine" else "tail2"}))
            with mock.patch.object(m,"STATES",root),self.assertRaises(m.Stop):
                m.ensure_no_duplicate_child()

    def test_sibling_tail_lineage_is_not_child_of_child(self):
        source=p.read_text()
        self.assertIn("remainder_parent=ORIGINAL",source)
        self.assertIn('descendant.get("partial_parent_migration_id") == ORIGINAL',source)
        self.assertIn('entry.get("migration_id")!=NINE_CHILD',source)
        self.assertNotIn("remainder_parent=NINE_CHILD",source)

    def test_default_receipt_path_is_root_private_not_shared_vf_state(self):
        self.assertEqual(m.RECOVERY_DIR, Path("/root/p07-last-two-recovery"))
        self.assertNotIn("/var/lib/vf-server-ops/operator-recovery", p.read_text())
        self.assertNotIn("chmod(", p.read_text())
        self.assertNotIn("chown(", p.read_text())

    def test_missing_recovery_directory_initialized_privately(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory)/"vf-server-ops"
            parent.mkdir(mode=0o700)
            target=parent/"operator-recovery"
            with mock.patch.object(m,"RECOVERY_DIR",target):
                self.assertFalse(target.exists())
                m.ensure_private_recovery_dir()
                metadata=target.lstat()
                self.assertTrue(stat.S_ISDIR(metadata.st_mode))
                self.assertEqual(stat.S_IMODE(metadata.st_mode),0o700)
                self.assertEqual(metadata.st_uid,os.geteuid())
                # Existing private recovery receipts are never removed or replaced.
                receipt=target/"existing-receipt"
                receipt.write_text("preserve this receipt")
                m.ensure_private_recovery_dir()
                self.assertEqual(receipt.read_text(),"preserve this receipt")

    def test_recovery_directory_unsafe_existing_forms_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory)/"vf-server-ops"
            parent.mkdir(mode=0o700)
            target=parent/"operator-recovery"
            outside=Path(directory)/"outside"
            outside.mkdir(mode=0o700)
            target.symlink_to(outside, target_is_directory=True)
            with mock.patch.object(m,"RECOVERY_DIR",target),self.assertRaises(m.Stop):
                m.ensure_private_recovery_dir()
            self.assertTrue(target.is_symlink())
            target.unlink()
            target.mkdir(mode=0o700)
            target.chmod(0o755)
            with mock.patch.object(m,"RECOVERY_DIR",target),self.assertRaises(m.Stop):
                m.ensure_private_recovery_dir()
            self.assertEqual(stat.S_IMODE(target.lstat().st_mode),0o755)
            target.rmdir()
            target.write_text("do not overwrite")
            with mock.patch.object(m,"RECOVERY_DIR",target),self.assertRaises(m.Stop):
                m.ensure_private_recovery_dir()
            self.assertEqual(target.read_text(),"do not overwrite")

    def test_unsafe_recovery_parent_fails_before_directory_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory)/"vf-server-ops"
            parent.mkdir(mode=0o700)
            parent.chmod(0o777)
            target=parent/"operator-recovery"
            with mock.patch.object(m,"RECOVERY_DIR",target),self.assertRaises(m.Stop):
                m.ensure_private_recovery_dir()
            self.assertFalse(target.exists())

    def test_snapshot_has_guarded_private_directory_initialization(self):
        text=p.read_text()
        self.assertIn("    ensure_private_recovery_dir()",text)
        self.assertIn("    p = RECOVERY_DIR /",text)
        self.assertIn("flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY",text)
        self.assertIn("os.fsync(f.fileno())",text)

    def test_existing_website_prevents_write(self):
        import sys
        a,b=state_pair()
        inventory=type("Invent",(),{"build_manifest":staticmethod(lambda root:{
            "discovery_source":"cloudpanel_db+vhost",
            "sites":[{"domain":"updates.kewaro.com","site_user":"any",
                      "mysql_databases":[]}]})})
        with mock.patch.dict(sys.modules,{"inventory":inventory}),self.assertRaises(m.Stop):
            m.ensure_target_unoccupied(b["sites"][7:])

    def test_code_does_not_invoke_cutover_or_retry(self):
        s=p.read_text()
        self.assertIn("remainder_parent=ORIGINAL",s)
        self.assertIn("expected_remainder_sites=[dict(row) for row in last_two]",s)
        self.assertIn('descendant.get("cutover_prohibited") is True',s)
        self.assertNotIn("engine.cutover_migration(",s)
        self.assertNotIn("engine.resume_prepare_migration(",s)
        self.assertNotIn("engine.freeze_old_server(",s)


class CandidateWww3SchemaTests(unittest.TestCase):
    def module(self):
        script=Path(__file__).with_name("p07-www3-candidate-schema-probe.py")
        spec=importlib.util.spec_from_file_location("p07_www3_exact",script)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_actual_tail_and_sql_revision_are_pinned(self):
        n=self.module()
        self.assertEqual(n.PARENT,"pull-20261101T045943Z-923729a1")
        self.assertEqual(n.CHILD,"pull-20261101T052411Z-35663c25")
        self.assertEqual(n.TAIL,"pull-20261102T005644Z-7178c7d5")
        self.assertEqual(n.CANDIDATE_HEAD,"06038930003114ad4223f1d03784c5338e371af3")
        self.assertEqual(n.CANDIDATE_BLOB,"29062b76d6b1fba65014e2a89b9566c3f93cdede")
        self.assertEqual(n.DOMAIN,"www3.m3u8.one")
        self.assertEqual(n.ENGINE_BLOB,m.ENGINE_BLOB)
        self.assertEqual(n.RELEASE113_SQL_ADVISORY_BLOB,
                         "02a377c90279b924b9d589525c5edcb098bed263")
        source=Path(__file__).resolve().parents[1]/"dist/p07/0.1.0/overlay/lib/sql_diff_evidence.py"
        self.assertEqual(n.blob(source.read_bytes()), n.RELEASE113_SQL_ADVISORY_BLOB)

    def test_no_target_database_create_import_or_resume_callsite(self):
        code=Path(__file__).with_name("p07-www3-candidate-schema-probe.py").read_text()
        for forbidden in ("engine.resume_prepare_migration(", "engine.prepare_migration(",
                          "engine.cutover_migration(", "engine.create_target_site(",
                          "engine.sync_site_databases(", "cloudpanel.add_database(",
                          "cloudpanel.import_database(", "mysql:import",
                          "chmod(0o777", "shutil.rmtree("):
            self.assertNotIn(forbidden,code)
        self.assertIn('engine.pull_path(tail["source"],remote_file,archive)',code)
        self.assertIn("adapter=load_release113_schema_adapter()",code)
        self.assertIn("SCHEMA_PRESENCE_RESULT=PASS_ADVISORY_ONLY",code)
        self.assertIn("PRIVATE_PR_EXACT_BINARY_VERIFICATION=NOT_PERFORMED",code)
        self.assertNotIn("urllib.request",code)
        self.assertNotIn("CANDIDATE_URL=",code)
        self.assertNotIn("fetch_pinned_candidate()",code)
        self.assertIn("SOURCE_TEMP_CLEANUP=",code)
        self.assertIn("CUTOVER_ALLOWED=NO",code)

    def test_wrong_tail_stage_or_parent_rejected_before_network(self):
        n=self.module()
        a,b=state_pair()
        a["sites"]=copy.deepcopy(a["sites"])
        t=copy.deepcopy(a)
        t.update(migration_id=n.TAIL,
                 partial_parent_migration_id=n.PARENT,
                 cutover_prohibited=True,
                 sites=[copy.deepcopy(a["sites"][15]),copy.deepcopy(a["sites"][16])])
        t["sites"][0]["stage_status"]="PULLED_STAGED"
        t["sites"][1]["stage_status"]="PENDING"
        t["sites"][1]["mysql_prepare_count"]=None
        t["source_runtime_path"]=f"/var/lib/vf-server-ops/pull-source/{n.TAIL}/runtime"
        mapping={n.PARENT:a,n.CHILD:b,n.TAIL:t}
        with mock.patch.object(n,"private_state",side_effect=lambda mid:mapping[mid]):
            for changed in ("status","parent","stage","db_count","source_frozen"):
                c=copy.deepcopy(t)
                if changed=="status":c["status"]="PREPARED"
                if changed=="parent":c["partial_parent_migration_id"]=n.CHILD
                if changed=="stage":c["sites"][1]["stage_status"]="PULLED_STAGED"
                if changed=="db_count":c["sites"][1]["mysql_databases"]=[]
                if changed=="source_frozen":c["source_runtime_frozen"]=True
                mapping[n.TAIL]=c
                with self.subTest(changed=changed),self.assertRaises(n.Block):
                    n.verify_state()

    def test_remote_source_export_synthetic_only_exact_site_and_no_overwrite(self):
        import contextlib,io,sys,types
        n=self.module()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            mid=n.TAIL
            data=root/mid/"data"
            data.mkdir(parents=True,mode=0o700)
            out=data/"www3-schema-aabbcc.sql.gz"
            inv=types.ModuleType("inventory")
            inv.build_manifest=lambda _root:{"sites":[
                {"domain":n.DOMAIN,"mysql_databases":["fixture_db"]}]}
            clp=types.ModuleType("cloudpanel")
            clp.CloudPanelError=type("CloudPanelError",(Exception,),{})
            calls=[]
            def export(db,path,*,clpctl):
                calls.append((db,clpctl))
                Path(path).write_bytes(b"x"*1100)
            clp.export_database=export
            remote=n.REMOTE.replace(
                'Path("/var/lib/vf-server-ops/pull-source")',
                f"Path({str(root)!r})",
            )
            env={"inventory":inv,"cloudpanel":clp}
            args=["-c",n.DOMAIN,"fixture_db",str(out),mid]
            with mock.patch.dict(sys.modules,env),mock.patch.object(sys,"argv",args):
                buf=io.StringIO()
                with contextlib.redirect_stdout(buf):
                    exec(compile(remote,"<isolated-source>","exec"),
                         {"__name__":"__main__"})
                self.assertEqual(buf.getvalue().strip(),"SOURCE_EXPORT_CREATED=YES")
                self.assertEqual(calls,[("fixture_db","clpctl")])
                self.assertEqual(out.read_bytes(),b"x"*1100)
                # Existing output is retained and never overwritten.
                with self.assertRaises(SystemExit) as caught:
                    exec(compile(remote,"<isolated-source>","exec"),
                         {"__name__":"__main__"})
                self.assertEqual(caught.exception.code,24)
                self.assertEqual(len(calls),1)
            out.unlink()
            inv.build_manifest=lambda _root:{"sites":[
                {"domain":n.DOMAIN,"mysql_databases":["unrelated"]}]}
            with mock.patch.dict(sys.modules,env),mock.patch.object(sys,"argv",args):
                with self.assertRaises(SystemExit) as caught:
                    exec(compile(remote,"<isolated-source>","exec"),
                         {"__name__":"__main__"})
                self.assertEqual(caught.exception.code,23)
                self.assertEqual(len(calls),1)
                self.assertFalse(out.exists())


    def test_actual_public_release_schema_parser_handles_only_safe_invalid_dml(self):
        import gzip,io,contextlib,sys
        n=self.module()
        overlay=Path(__file__).resolve().parents[1]/"dist/p07/0.1.0/overlay"
        sys.path.insert(0,str(overlay/"lib"))
        with mock.patch.object(n,"RUNTIME",overlay):
            parser=n.load_release113_schema_adapter()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"source.sql.gz"
            valid=(
                b"SET NAMES utf8mb4;\nCREATE TABLE \`one\` (\`id\` INT);\n"
                b"INSERT INTO \`one\` VALUES ('"+bytes([255])+b"');\n"
                b"CREATE TABLE \`two\` (\`id\` INT);\n"
                b"REPLACE INTO \`two\` VALUES ('"+bytes([254])+b"');\n"
            )
            with gzip.open(path,"wb") as handle:
                handle.write(valid)
            before=path.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertTrue(n.scan_schema_adapter(parser,path))
            self.assertIn("SCHEMA_PRESENCE_RESULT=PASS_ADVISORY_ONLY",out.getvalue())
            self.assertIn("SCHEMA_PRESENCE_TABLE_COUNT=2",out.getvalue())
            self.assertEqual(path.read_bytes(),before)
            # No in-memory adaptation may leak into the released parser.
            with self.assertRaises(parser.AdvisoryDiagnosticUnavailable):
                parser._schema_statements(path)

    def test_schema_adapter_rejects_invalid_ddl_unknown_dml_continuation_and_gzip(self):
        import gzip,io,contextlib,sys
        n=self.module()
        overlay=Path(__file__).resolve().parents[1]/"dist/p07/0.1.0/overlay"
        sys.path.insert(0,str(overlay/"lib"))
        with mock.patch.object(n,"RUNTIME",overlay):
            parser=n.load_release113_schema_adapter()
        rows=(
            b"CREATE TABLE \`broken\` (\`id\` "+bytes([255])+b" INT);\n",
            b"CREATE TABLE \`a\` (\nINSERT INTO \`bad\` VALUES ('"+
                bytes([255])+b"');\n);\n",
            b"CREATE TABLE \`a\` (\`id\` INT);\nUPDATE \`a\` SET id='"+
                bytes([255])+b"';\n",
            b"INSERT INTO \`a\` VALUES ('"+bytes([255])+b"');\n",
            b"CREATE TABLE \`a\` (\`id\` INT);\n"+bytes([255])+b"INSERT INTO \`a\` VALUES(1);\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            for index,data in enumerate(rows):
                with self.subTest(index=index):
                    path=Path(directory)/f"source-{index}.sql.gz"
                    with gzip.open(path,"wb") as handle:
                        handle.write(data)
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertFalse(n.scan_schema_adapter(parser,path))
            path=Path(directory)/"source-corrupt.sql.gz"
            path.write_bytes(b"\x1f\x8bnot-valid-gzip")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(n.scan_schema_adapter(parser,path))
    
    def test_private_product_cannot_be_downloaded_by_anonymous_operator(self):
        n=self.module()
        code=Path(__file__).with_name("p07-www3-candidate-schema-probe.py").read_text()
        self.assertIn("PRIVATE_PR_CANDIDATE_DOWNLOAD=NO",code)
        self.assertIn("PRIVATE_PR_EXACT_BINARY_VERIFICATION=NOT_PERFORMED",code)
        self.assertNotIn("raw.githubusercontent.com/llhzx2018/vf-server-ops",code)
        self.assertNotIn("urllib.request",code)
        self.assertNotIn("curl ",code)

if __name__=="__main__":unittest.main()
