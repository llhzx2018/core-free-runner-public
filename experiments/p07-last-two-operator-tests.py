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
                b"SET NAMES utf8mb4;\nCREATE TABLE `one` (`id` INT);\n"
                b"INSERT INTO `one` VALUES ('"+bytes([255])+b"');\n"
                b"CREATE TABLE `two` (`id` INT);\n"
                b"REPLACE INTO `two` VALUES ('"+bytes([254])+b"');\n"
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
            b"CREATE TABLE `broken` (`id` "+bytes([255])+b" INT);\n",
            b"CREATE TABLE `a` (\nINSERT INTO `bad` VALUES ('"+
                bytes([255])+b"');\n);\n",
            b"CREATE TABLE `a` (`id` INT);\nUPDATE `a` SET id='"+
                bytes([255])+b"';\n",
            b"INSERT INTO `a` VALUES ('"+bytes([255])+b"');\n",
            b"CREATE TABLE `a` (`id` INT);\n"+bytes([255])+b"INSERT INTO `a` VALUES(1);\n",
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


    def test_hex_export_remote_uses_socket_read_only_and_refuses_duplicates(self):
        import contextlib,gzip,io,sys,types
        n=self.module()
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            data=base/n.TAIL/"data"
            data.mkdir(parents=True)
            output=data/"www3-hex-safe.sql.gz"
            raw=(b"CREATE TABLE sample (payload BLOB);\n" +
                 b"".join(b"INSERT INTO sample VALUES (0x" +
                     __import__("hashlib").sha256(str(i).encode()).hexdigest().encode() +
                     b");\n" for i in range(100)))
            inventory=types.ModuleType("inventory")
            inventory.build_manifest=lambda root:{"sites":[{
                "domain":n.DOMAIN,"mysql_databases":["dbfixture"]}]}
            dump=types.ModuleType("subprocess")
            import subprocess as base_subprocess
            for name in ("DEVNULL","PIPE","TimeoutExpired","SubprocessError"):
                setattr(dump,name,getattr(base_subprocess,name))
            class Process:
                def __init__(self):
                    self.stdout=io.BytesIO(raw)
                def wait(self,timeout=None):
                    return 0
                def poll(self):
                    return 0
                def kill(self):
                    raise AssertionError("a complete export must not be killed")
            calls=[]
            master_line = (
                b"Connect Command: mysql -h127.0.0.1 -P3306 -uroot "
                b"-p'fixture-private-password'\n"
            )
            def fake_run(cmd, **kw):
                if cmd[:2]==["clpctl","db:show:master-credentials"]:
                    return base_subprocess.CompletedProcess(cmd,0,master_line,b"")
                if "--execute=SELECT 1" in cmd:
                    self.assertEqual(kw["env"]["MYSQL_PWD"],
                                     "fixture-private-password")
                    return base_subprocess.CompletedProcess(cmd,0,b"1\n",b"")
                return base_subprocess.CompletedProcess(
                    cmd,0,
                    b"--hex-blob --single-transaction --quick --default-character-set "
                    b"--no-tablespaces --set-gtid-purged --set-charset",b"")
            dump.run=fake_run
            def spawned(command,**kwargs):
                self.assertEqual(kwargs["env"]["MYSQL_PWD"],
                                 "fixture-private-password")
                calls.append(command)
                return Process()
            dump.Popen=spawned
            shutil=types.ModuleType("shutil")
            shutil.which=lambda name:(
                "/usr/bin/"+name if name in ("mysqldump","mysql") else None
            )
            remote=n.REMOTE_HEX.replace(
                'Path("/var/lib/vf-server-ops/pull-source")',
                f"Path({str(base)!r})",
            )
            payload={"inventory":inventory,"subprocess":dump,"shutil":shutil}
            args=["-c",n.DOMAIN,"dbfixture",str(output),n.TAIL]
            with mock.patch.dict(sys.modules,payload),mock.patch.object(sys,"argv",args):
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    exec(compile(remote,"<source-dump>","exec"),
                         {"__name__":"__main__"})
                self.assertEqual(out.getvalue().strip(),
                    "HEX_EXPORT_AUTH=READ_ONLY_CONNECTION_PASS\n"
                    "HEX_SOURCE_EXPORT=CREATED_UNVERIFIED")
                self.assertNotIn("fixture-private-password",out.getvalue())
                self.assertEqual(gzip.decompress(output.read_bytes()),raw)
                self.assertEqual(len(calls),1)
                self.assertIn("--hex-blob",calls[0])
                self.assertIn("--single-transaction",calls[0])
                self.assertIn("--skip-lock-tables",calls[0])
                self.assertNotIn("--password", " ".join(calls[0]))
                with self.assertRaises(SystemExit) as refused:
                    exec(compile(remote,"<source-dump>","exec"),
                         {"__name__":"__main__"})
                self.assertEqual(refused.exception.code,23)
            self.assertEqual(len(calls),1)

    def test_hex_cloudpanel_auth_parser_rejects_untrusted_commands(self):
        import contextlib,io,sys,types
        n=self.module()
        # Exercise the exact old-server parser without ever contacting a VPS.
        source=n.REMOTE_HEX
        part=source[source.index("def parse_master_command("):
                    source.index("master=managed_master_credentials()")]
        # Function definitions here are inert; never execute the remote export.
        ns={"__name__":"test_auth_parser"}
        import os,subprocess,shlex,re,shutil
        from pathlib import Path
        ns.update(os=os,subprocess=subprocess,shlex=shlex,re=re,shutil=shutil,
                  Path=Path)
        exec(compile(part,"<auth-test>","exec"),ns)
        parse=ns["parse_master_command"]
        fields=ns["parse_master_fields"]
        fixture=("Host: 127.0.0.1\nUser Name: root\n"
                 "Password: fixture-secret\nPort: 3306\n")
        self.assertEqual(fields(fixture)["password"],"fixture-secret")
        self.assertEqual(fields(
            "| Host | localhost |\n| User Name | root |\n"
            "| Password | fixture-secret |\n| Port | 3306 |\n"
        )["user"],"root")
        for bad in (
            "Host: remote.example\nUser Name: root\n"
            "Password: secret\nPort: 3306\n",
            "Host: localhost\nUser Name: root\n"
            "Password: secret\nPort: 3306\nPassword: other",
        ):
            self.assertIsNone(fields(bad))
        cred=parse("Connect Command: mysql -h127.0.0.1 -P3306 "
                   "-uroot -p'fixture-private-password'")
        self.assertIsNotNone(cred)
        self.assertEqual(cred["host"],"127.0.0.1")
        self.assertEqual(cred["password"],"fixture-private-password")
        for unsafe in (
            "Connect Command: mysql -h192.0.2.18 -P3306 -uroot -psecret",
            "Connect Command: mysql -h127.0.0.1 -P3306 -uroot -psecret; echo LEAK",
            "Connect Command: bash -c 'mysql -h127.0.0.1'",
            "Connect Command: mysql -h127.0.0.1 -P3306 -uroot -psecret --execute=DROP",
            "Connect Command: mysql -h127.0.0.1 -P3306 -uroot",
            "Connect Command: mysql -h127.0.0.1 -P3306 -uroot -psecret\n"
            "Connect Command: mysql -h127.0.0.1 -P3306 -uroot -psecret",
        ):
            with self.subTest(unsafe=unsafe[:40]):
                self.assertIsNone(parse(unsafe))

    def test_hex_path_does_not_expose_cloudpanel_master_credentials(self):
        code=Path(__file__).with_name(
            "p07-www3-candidate-schema-probe.py"
        ).read_text()
        self.assertIn("db:show:master-credentials",code)
        self.assertIn('env["MYSQL_PWD"]=',code)
        self.assertIn('stderr=subprocess.DEVNULL',code)
        self.assertIn("HEX_EXPORT_AUTH=READ_ONLY_CONNECTION_PASS",code)
        self.assertNotIn("print(result.stdout)",code)
        self.assertNotIn("print(master)",code)
        self.assertNotIn('"--password="+',code)
        self.assertNotIn("shell=True",code)

    def test_hex_export_read_only_utf8_and_gzip_gates(self):
        import gzip,io,contextlib
        n=self.module()
        with tempfile.TemporaryDirectory() as directory:
            f=Path(directory)/"file.sql.gz"
            with gzip.open(f,"wb") as stream:
                stream.write(b"CREATE TABLE sample (v BLOB);\n"+
                             b"INSERT INTO sample VALUES (0xFF);\n"*30)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertTrue(n.strict_hex_export_utf8(f))
            self.assertIn("UTF8_STREAM_INTACT",out.getvalue())
            with gzip.open(f,"wb") as stream:
                stream.write(b"CREATE TABLE sample (v TEXT);\n"+
                             b"INSERT INTO sample VALUES ('"+bytes([255])+b"');\n"*30)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertFalse(n.strict_hex_export_utf8(f))
            self.assertIn("NON_UTF8_REMAINS",out.getvalue())
            broken=f.read_bytes()[:-6]
            f.write_bytes(broken)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertFalse(n.strict_hex_export_utf8(f))
            self.assertIn("GZIP_INVALID",out.getvalue())

    def test_hex_option_never_enters_target_import_or_state_update(self):
        n=self.module()
        source=Path(__file__).with_name("p07-www3-candidate-schema-probe.py").read_text()
        self.assertIn("--prove-hex-export-source-only",source)
        self.assertIn("expected_tables=157",source)
        self.assertIn("TARGET_DATABASE_WRITES=NO",source)
        self.assertIn("MIGRATION_RETRY=NO",source)
        self.assertIn("SOURCE_TEMP_CLEANUP=",source)
        for forbidden in ("engine.resume_prepare_migration(", "engine.prepare_migration(",
                          "cloudpanel.import_database(", "cloudpanel.add_database(",
                          "engine.cutover_migration(", "engine.save_state("):
            self.assertNotIn(forbidden,source)


class IsolatedWww3ScratchTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).with_name("p07-www3-isolated-stage.py")
        spec=importlib.util.spec_from_file_location("p07_www3_scratch_test",path)
        m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_helper_is_pinned_and_no_target_destructive_primitives(self):
        m=self.module()
        self.assertEqual(m.load_helper().TAIL,"pull-20261102T005644Z-7178c7d5")
        src=Path(__file__).with_name("p07-www3-isolated-stage.py").read_text()
        self.assertIn('"--stage-new-www3-scratch-only"',src)
        self.assertIn("SCRATCH_DB=CREATED_NOT_ACTIVATED",src)
        self.assertIn("SCRATCH_PARITY=UNPROVEN",src)
        self.assertIn("SOURCE_TEMP_CLEANUP=",src)
        self.assertIn("CUTOVER_ALLOWED=NO",src)
        self.assertIn("os.O_EXCL",src)
        for banned in ("cloudpanel.delete_database(", "cloudpanel.delete_site(",
                       "engine.cutover_migration(", "engine.save_state(",
                       "engine.resume_prepare_migration(", "engine.prepare_migration(",
                       "engine.activate_target_runtime(", "engine.freeze_old_server(",
                       "subprocess.run(shell=True", "shell=True"):
            self.assertNotIn(banned,src)

    def test_scratch_marker_is_private_exclusive_and_never_reused(self):
        import types,sys
        m=self.module()
        with tempfile.TemporaryDirectory() as folder:
            base=types.SimpleNamespace(BASE=Path(folder),TAIL="pull-test",DOMAIN="www3.m3u8.one")
            root=Path(folder)/"pull-test"/"target-transactions"
            root.mkdir(parents=True,mode=0o700)
            root.chmod(0o700)
            # CI runner is unprivileged; simulate only the root-owned
            # PRIVATE receipt directory, never relax the product guard.
            original_lstat=Path.lstat
            def root_owned_lstat(path):
                info=original_lstat(path)
                if path==root:
                    import types
                    return types.SimpleNamespace(
                        st_uid=0,st_mode=info.st_mode)
                return info
            with mock.patch.object(Path,"lstat",root_owned_lstat):
                p=m.receipt_path(base,"p07safescratch1")
                self.assertTrue(str(p).startswith(str(root)))
                with mock.patch.dict(sys.modules,{"server_migration":type("L",(),{
                     "atomic_private_json":staticmethod(lambda path,entry:None)})}):
                    m.save(p,{"status":"INTENT_RESERVED"},first=True)
                    self.assertEqual(p.stat().st_mode&0o777,0o600)
                    self.assertEqual(json.loads(p.read_text())["status"],"INTENT_RESERVED")
                    with self.assertRaises(m.Stop):
                        m.receipt_path(base,"p07safescratch1")
                    with self.assertRaises(FileExistsError):
                        m.save(p,{"status":"OVERWRITE"},first=True)
                    self.assertEqual(json.loads(p.read_text())["status"],"INTENT_RESERVED")

    def test_catalog_absence_requires_master_grants_and_exact_zero(self):
        import subprocess as real_sub
        m=self.module()
        info={"host":"127.0.0.1","port":"3306",
              "user":"root","password":"fixture-hidden-secret"}
        allowed=b"GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost'\n"
        def output(value):
            return real_sub.CompletedProcess([],0,value,b"")
        with mock.patch.object(m.shutil,"which",
               side_effect=lambda name:"/usr/bin/mysql"),\
             mock.patch.object(m,"_target_master_credentials",
               return_value=info),\
             mock.patch.object(m.subprocess,"run",
               side_effect=[output(allowed),output(b"0\n")]) as call:
            self.assertEqual(m.absent_sql("p07safescratch1"),"/usr/bin/mysql")
            self.assertEqual(call.call_count,2)
            self.assertIn("information_schema.SCHEMATA",
                          call.call_args.args[0][-1])
            self.assertIn("SCHEMA_NAME='p07safescratch1'",
                          call.call_args.args[0][-1])
            self.assertNotIn("DROP",call.call_args.args[0][-1])
            for c in call.call_args_list:
                self.assertEqual(c.kwargs["env"]["MYSQL_PWD"],
                                 "fixture-hidden-secret")
                self.assertNotIn("fixture-hidden-secret"," ".join(c.args[0]))
        with mock.patch.object(m.shutil,"which",
               return_value="/usr/bin/mysql"),\
             mock.patch.object(m,"_target_master_credentials",
               return_value=info),\
             mock.patch.object(m.subprocess,"run",
               side_effect=[output(allowed),output(b"1\n")]):
            with self.assertRaisesRegex(
                m.Stop,"TARGET_SCRATCH_DATABASE_ALREADY_EXISTS_RETAIN"
            ):
                m.absent_sql("p07safescratch1")

    def test_catalog_denies_unknown_credentials_permissions_and_ambiguous_read(self):
        import subprocess as real_sub
        m=self.module()
        info={"host":"localhost","port":"3306","user":"root",
              "password":"fixture-not-exposed"}
        ok=b"GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost'\n"
        no=b"GRANT SELECT ON *.* TO 'readonly'@'localhost'\n"
        def output(data,code=0):
            return real_sub.CompletedProcess([],code,data,b"")
        for grants, count,expected in (
            (no,b"0\n","TARGET_CATALOG_PRIVILEGES_UNPROVEN"),
            (ok,b"\n","TARGET_CATALOG_QUERY_AMBIGUOUS"),
            (ok,b"two\n","TARGET_CATALOG_QUERY_AMBIGUOUS"),
            (ok,b"1\n","TARGET_SCRATCH_DATABASE_ALREADY_EXISTS_RETAIN"),
            (ok,b"0\n","NONE"),
        ):
            with self.subTest(expected=expected),\
                 mock.patch.object(m.shutil,"which",return_value="/usr/bin/mysql"),\
                 mock.patch.object(m,"_target_master_credentials",return_value=info),\
                 mock.patch.object(m.subprocess,"run",
                     side_effect=[output(grants),output(count)]) as calls:
                if expected=="NONE":
                    self.assertEqual(m.absent_sql("p07safescratch1"),"/usr/bin/mysql")
                else:
                    with self.assertRaisesRegex(m.Stop,expected):
                        m.absent_sql("p07safescratch1")
                if expected=="TARGET_CATALOG_PRIVILEGES_UNPROVEN":
                    self.assertEqual(calls.call_count,1)
        with mock.patch.object(m.shutil,"which",return_value="/usr/bin/mysql"),\
             mock.patch.object(m,"_target_master_credentials",
                                side_effect=m.Stop("TARGET_CATALOG_MASTER_CREDENTIALS_UNAVAILABLE")):
            with self.assertRaisesRegex(m.Stop,"TARGET_CATALOG_MASTER_CREDENTIALS_UNAVAILABLE"):
                m.absent_sql("p07safescratch1")

    def test_cp2_master_credentials_conservative_parsing_and_no_stdout_leak(self):
        import subprocess as real_sub
        m=self.module()
        samples=(
            # CloudPanel v2 documentation: box table plus Connect Command
            # with quoted values and trailing -A (skip client auto-rehash).
            b"+---------+-------------+\n"
            b"| Name    | Value       |\n"
            b"+---------+-------------+\n"
            b"| Host    | 127.0.0.1   |\n"
            b"| User Name | root      |\n"
            b"| Password | fixture-secret |\n"
            b"| Port    | 3306        |\n"
            b"Connect Command: mysql -h'127.0.0.1' -P'3306' -u'root' "
            b"-p'fixture-secret' -A\n",
            b"Connect Command: mysql -h127.0.0.1 -P3306 -uroot -p'fixture-secret'\n",
            b"Host: localhost\nPort: 3306\nUser Name: root\nPassword: fixture-secret\n",
            b"| Host | localhost |\n| Port | 3306 |\n"
            b"| User Name | root |\n| Password | fixture-secret |\n",
        )
        for sample in samples:
            with self.subTest(sample=sample[:9]),\
                 mock.patch.object(m.subprocess,"run",
                   return_value=real_sub.CompletedProcess([],0,sample,b"")) as call:
                got=m._target_master_credentials()
                self.assertEqual(got["password"],"fixture-secret")
                self.assertIn("db:show:master-credentials",call.call_args.args[0])
        for malformed in (
            b"Connect Command: mysql -h192.0.2.1 -P3306 -uroot -psecret",
            b"Connect Command: mysql -h127.0.0.1 -P3306 -uroot -psecret -A --execute=DROP",
            b"Connect Command: mysql -h127.0.0.1 -P3306 -uroot -psecret -A -A",
            b"Connect Command: mysql -h127.0.0.1 -P3306 -uroot -psecret --execute=DROP",
            b"Host: remote.example\nPort: 3306\nUser Name: root\nPassword: secret\n",
            b"Host: localhost\nPort: 3306\nUser Name: root\nPassword: one\nPassword: two\n",
        ):
            with self.subTest(malformed=malformed[:18]),\
                 mock.patch.object(m.subprocess,"run",
                    return_value=real_sub.CompletedProcess([],0,malformed,b"")):
                with self.assertRaises(m.Stop):
                    m._target_master_credentials()

    def test_only_new_database_scoped_grants_are_accepted(self):
        import subprocess as real_sub
        m=self.module()
        db="p07safescratch1"
        ok=(f"GRANT USAGE ON *.* TO 'u'@'127.0.0.1'\n"
            f"GRANT ALL PRIVILEGES ON {db}.* TO 'u'@'127.0.0.1'\n").encode()
        with mock.patch.object(m.subprocess,"run",
             return_value=real_sub.CompletedProcess([],0,ok,b"")):
            args,env=m.restricted_user("/usr/bin/mysql",db,"u","fixture-secret")
            self.assertIn("--user=u",args)
            self.assertNotIn("fixture-secret"," ".join(args))
            self.assertEqual(env["MYSQL_PWD"],"fixture-secret")
        wrong=b"GRANT ALL PRIVILEGES ON *.* TO 'u'@'127.0.0.1'\n"
        with mock.patch.object(m.subprocess,"run",
             return_value=real_sub.CompletedProcess([],0,wrong,b"")):
            with self.assertRaises(m.Stop):
                m.restricted_user("/usr/bin/mysql",db,"u","fixture-secret")
        elevated=(f"GRANT ALL PRIVILEGES ON {db}.* TO 'u'@'localhost' WITH GRANT OPTION\n").encode()
        with mock.patch.object(m.subprocess,"run",
             return_value=real_sub.CompletedProcess([],0,elevated,b"")):
            with self.assertRaises(m.Stop):
                m.restricted_user("/usr/bin/mysql",db,"u","fixture-secret")

    def test_restricted_import_writes_only_to_selected_new_scratch(self):
        import gzip,io
        m=self.module()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"input.sql.gz"
            original=b"CREATE TABLE checked (v BLOB);\nINSERT INTO checked VALUES (0xFF);\n"
            with gzip.open(path,"wb") as out:out.write(original)
            commands=[]
            class Process:
                def __init__(self):
                    self.stdin=io.BytesIO()
                def poll(self):
                    return 0
                def wait(self,timeout):
                    self.stdin_content=self.stdin.getvalue() if not self.stdin.closed else b""
                    return 0
                def kill(self):
                    raise AssertionError("unexpected kill")
            proc=Process()
            class Sink(io.BytesIO):
                def close(self):
                    self.seen=self.getvalue()
                    super().close()
            proc.stdin=Sink()
            with mock.patch.object(m.subprocess,"Popen",
               side_effect=lambda argv,**kwargs:(commands.append((argv,kwargs)) or proc)):
                m.import_only_scratch(
                    ["/usr/bin/mysql","--user=u"],{"MYSQL_PWD":"secret"},
                    "p07safescratch1",path
                )
            self.assertEqual(proc.stdin.seen,original)
            self.assertIn("--database=p07safescratch1",commands[0][0])
            self.assertNotIn("secret"," ".join(commands[0][0]))

    def test_release113_side_effect_guard_actual_api(self):
        import gzip,sys
        m=self.module()
        overlay=Path(__file__).resolve().parents[1]/"dist/p07/0.1.0/overlay/lib"
        sys.path.insert(0,str(overlay))
        import verify
        self.assertFalse(hasattr(verify,"sql_unproven_side_effects"))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"case.sql.gz"
            with gzip.open(path,"wb") as f:
                f.write(b"CREATE TABLE sample (id INT);\nINSERT INTO sample VALUES(1);\n")
            self.assertFalse(m.standalone_sql_unproven_side_effects(path,verify))
            for payload in (
                b"UPDATE sample SET id=2;\n",
                b"DELETE FROM sample;\n",
                b"SET GLOBAL sql_log_bin=0;\n",
                b"CREATE TABLE a(id INT); DROP TABLE b;\n",
            ):
                with gzip.open(path,"wb") as f:f.write(payload)
                self.assertTrue(m.standalone_sql_unproven_side_effects(path,verify))
            path.write_bytes(b"corrupt-gzip")
            with self.assertRaises(verify.RestoreVerifyError):
                m.standalone_sql_unproven_side_effects(path,verify)

    def test_release113_strict_scope_accepts_safe_and_rejects_unsafe(self):
        import gzip,sys
        m=self.module()
        overlay=Path(__file__).resolve().parents[1]/"dist/p07/0.1.0/overlay/lib"
        sys.path.insert(0,str(overlay))
        import verify,sql_diff_evidence
        self.assertFalse(hasattr(verify,"sql_unproven_side_effects"))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"real.sql.gz"
            with mock.patch.object(sql_diff_evidence,
                   "require_nonempty_source_schema",return_value=157):
                with gzip.open(path,"wb") as f:
                    f.write(b"CREATE TABLE sample (id INT);"+bytes([10])+
                            b"INSERT INTO sample VALUES(1);"+bytes([10]))
                self.assertIsNone(m.strict_scope(path))
                with gzip.open(path,"wb") as f:
                    f.write(b"CREATE TABLE sample (id INT);"+bytes([10])+
                            b"UPDATE sample SET id=2;"+bytes([10]))
                with self.assertRaisesRegex(m.Stop,"SOURCE_UNPROVEN_SIDE_EFFECTS"):
                    m.strict_scope(path)
                with gzip.open(path,"wb") as f:
                    f.write(b"CREATE TABLE sample (id INT);"+bytes([10])+
                            b"INSERT INTO external.sample VALUES(1);"+bytes([10]))
                with self.assertRaisesRegex(m.Stop,"SOURCE_SQL_ESCAPES_SCRATCH_SCOPE"):
                    m.strict_scope(path)

    def test_preflight_sql_denies_database_escape(self):
        import gzip,sys
        m=self.module()
        overlay=Path(__file__).resolve().parents[1]/"dist/p07/0.1.0/overlay/lib"
        sys.path.insert(0,str(overlay))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"source.sql.gz"
            with gzip.open(path,"wb") as out:
                out.write(b"CREATE DATABASE external;\nCREATE TABLE demo (id INT);\n")
            with self.assertRaises(m.Stop):
                m.strict_scope(path)



    def test_isolated_staging_full_synthetic_success_and_failed_import_preservation(self):
        import contextlib,gzip,io,subprocess,sys,types
        m=self.module()
        for fail_import in (False,True):
            with self.subTest(fail_import=fail_import),tempfile.TemporaryDirectory() as td:
                root=Path(td)
                marker=root/"private.json"
                raw=(b"CREATE TABLE demo (v BLOB);\n" + b"".join(
                    b"INSERT INTO demo VALUES (0x" +
                    __import__("hashlib").sha256(str(i).encode()).hexdigest().encode() +
                    b");\n" for i in range(200)))
                state={"source":{"host":"old.example"},
                       "target_server_identity":"target-identity",
                       "source_runtime_path":"/tmp/staged-runtime",
                       "sites":[{"domain":"updates.kewaro.com"},
                                {"domain":"www3.m3u8.one","mysql_databases":["original"]}]}
                helper=types.SimpleNamespace(
                    verify_state=lambda:(state,"original"),
                    verify_current_runtime=lambda:None,
                    RUNTIME=root,
                    DOMAIN="www3.m3u8.one",
                    TAIL="pull-simulated",
                    REMOTE_HEX="source-export-helper",
                    load_release113_schema_adapter=lambda:object(),
                    inspect_existing_site=lambda *args:None,
                    strict_hex_export_utf8=lambda path:True,
                    scan_schema_adapter=lambda *args,**kw:True,
                )
                recorded=[]
                fake_engine=types.ModuleType("server_migration_pull")
                fake_engine.target_identity=lambda:"target-identity"
                def remote_fn(*args,**kwargs):
                    if "rm -f" in args[1]:
                        recorded.append("cleanup")
                        return subprocess.CompletedProcess([],0,"","")
                    recorded.append("source-export")
                    return subprocess.CompletedProcess(
                        [],0,
                        "HEX_EXPORT_AUTH=READ_ONLY_CONNECTION_PASS\n"
                        "HEX_SOURCE_EXPORT=CREATED_UNVERIFIED\n",""
                    )
                fake_engine.source_remote=remote_fn
                def transfer_fn(_source,_remote,local):
                    with gzip.open(local,"wb") as g:
                        g.write(raw)
                fake_engine.pull_path=transfer_fn
                fake_engine.compare_database_dumps=lambda *args:"CANONICAL_SQL_EXACT"
                fake_panel=types.ModuleType("cloudpanel")
                fake_panel.CloudPanelError=type("CloudPanelError",(Exception,),{})
                def add_db(*args):
                    recorded.append("create-db")
                    self.assertEqual(marker.exists(),True)
                    self.assertEqual(json.loads(marker.read_text())["status"],
                                     "INTENT_RESERVED")
                fake_panel.add_database=add_db
                fake_panel.export_database=lambda name,after:Path(after).write_bytes(b"safe")
                fake_inventory=types.ModuleType("inventory")
                fake_inventory.build_manifest=lambda root:{"sites":[{
                    "domain":"www3.m3u8.one","mysql_databases":[]}]}
                def persist(path,entry,first=False):
                    if first:
                        self.assertFalse(marker.exists())
                        with marker.open("x") as out:json.dump(entry,out)
                    else:
                        self.assertTrue(marker.exists())
                        marker.write_text(json.dumps(entry))
                    recorded.append("receipt:"+entry["status"])
                def import_fn(*args):
                    recorded.append("import")
                    if fail_import:raise m.Stop("SCRATCH_IMPORT_FAILED")
                keep_temp=tempfile.TemporaryDirectory
                def sandbox_temp(*args,**kwargs):
                    kwargs["dir"]=root
                    return keep_temp(*args,**kwargs)
                fake_site_lifecycle=types.ModuleType("site_lifecycle")
                with mock.patch.dict(sys.modules,{
                       "server_migration_pull":fake_engine,
                       "cloudpanel":fake_panel,"inventory":fake_inventory,
                       "site_lifecycle":fake_site_lifecycle
                     }),mock.patch.object(m,"load_helper",return_value=helper),\
                     mock.patch.object(m.os,"geteuid",return_value=0),\
                     mock.patch.object(sys,"argv",["script","--stage-new-www3-scratch-only"]),\
                     mock.patch.object(m,"scratch_name",
                          return_value=("p07safescratch","user","password")),\
                     mock.patch.object(m,"absent_sql",return_value="/usr/bin/mysql"),\
                     mock.patch.object(m,"receipt_path",return_value=marker),\
                     mock.patch.object(m,"save",side_effect=persist),\
                     mock.patch.object(m,"strict_scope"),\
                     mock.patch.object(m,"restricted_user",
                          return_value=(["/usr/bin/mysql"],{"MYSQL_PWD":"secret"})),\
                     mock.patch.object(m,"import_only_scratch",side_effect=import_fn),\
                     mock.patch.object(m.tempfile,"TemporaryDirectory",
                          side_effect=sandbox_temp):
                    if fail_import:
                        with contextlib.redirect_stdout(io.StringIO()),\
                             self.assertRaisesRegex(m.Stop,"SCRATCH_IMPORT_FAILED"):
                            m.run()
                    else:
                        with contextlib.redirect_stdout(io.StringIO()):
                            self.assertEqual(m.run(),0)
                self.assertLess(recorded.index("receipt:INTENT_RESERVED"),
                                recorded.index("create-db"))
                self.assertLess(recorded.index("create-db"),
                                recorded.index("import"))
                self.assertEqual(recorded[-1],"cleanup")
                self.assertEqual(json.loads(marker.read_text())["status"],
                                 "IMPORT_UNPROVEN" if fail_import else
                                 "VERIFIED_NOT_ACTIVATED")
                self.assertNotIn("delete",json.dumps(recorded))
                self.assertNotIn("app-config",json.dumps(recorded))



class SourceLinkReadOnlyTests(unittest.TestCase):
    def module(self):
        script=Path(__file__).with_name("p07-www3-source-link-readonly.py")
        spec=importlib.util.spec_from_file_location("p07_www3_source_link_test",script)
        m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_read_only_source_probe_has_no_write_or_cleanup_command(self):
        code=Path(__file__).with_name("p07-www3-source-link-readonly.py").read_text()
        for forbidden in (
            "engine.pull_path(", "cloudpanel.add_database(", "cloudpanel.import_database(",
            "engine.resume_prepare_migration(", "engine.prepare_migration(",
            "engine.save_state(", "engine.freeze", "rm -f", "unlink(",
            "engine.cutover_migration(", "cloudpanel.delete_database(",
        ):
            self.assertNotIn(forbidden,code)
        m=self.module()
        self.assertEqual(m.PIN,"8f640e7505c5b49ad5a7574d82c0030eb6e7b884")
        self.assertIsNotNone(m.load_helper())
        self.assertEqual(m.classify("Permission denied (publickey)",255),
                         "SSH_AUTH_DENIED")
        self.assertEqual(m.classify("Host key verification failed",255),
                         "SSH_HOST_KEY_UNVERIFIED")
        self.assertEqual(m.classify("Connection timed out",255),
                         "SSH_CONNECTION_TIMEOUT")
        self.assertEqual(m.classify("No route to host",255),
                         "SSH_NETWORK_UNREACHABLE")

    def test_ssh_transport_failure_is_read_only_and_never_claims_cleanup(self):
        import contextlib,io,sys,subprocess,types
        m=self.module()
        source={"identity_file":None,"ssh_user":"root"}
        tail={"target_server_identity":"cp2","source":source}
        base=types.SimpleNamespace(
            verify_state=lambda:(tail,"legacy_db"),
            verify_current_runtime=lambda:None,
            RUNTIME=Path("/opt/vf-server-ops"),
            inspect_existing_site=lambda *args:None,
            DOMAIN="www3.m3u8.one",TAIL="pull-synthetic"
        )
        engine=types.ModuleType("server_migration_pull")
        engine.target_identity=lambda:"cp2"
        class PullMigrationError(Exception):pass
        engine.PullMigrationError=PullMigrationError
        calls=[]
        def fail(src,command,**kwargs):
            calls.append(command)
            return subprocess.CompletedProcess([],255,"","Permission denied (publickey)")
        engine.source_remote=fail
        with mock.patch.dict(sys.modules,{"server_migration_pull":engine}),\
             mock.patch.object(m,"load_helper",return_value=base),\
             mock.patch.object(m.os,"geteuid",return_value=0),\
             mock.patch.object(sys,"argv",["script","--read-only-source-ssh-and-temp-audit"]),\
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(m.run(),13)
        printed=output.getvalue()
        self.assertIn("SOURCE_SSH_REASON=SSH_AUTH_DENIED",printed)
        self.assertIn("SOURCE_HEX_TEMP_AUDIT=UNPROVEN",printed)
        self.assertIn("SOURCE_TEMP_CLEANUP=NOT_ATTEMPTED",printed)
        self.assertEqual(len(calls),1)
        self.assertIn("printf",calls[0])

    def test_ssh_success_reports_only_bounded_temp_counts(self):
        import contextlib,io,sys,subprocess,types
        m=self.module()
        source={"identity_file":None,"ssh_user":"root"}
        tail={"target_server_identity":"cp2","source":source}
        base=types.SimpleNamespace(
            verify_state=lambda:(tail,"legacy_db"),
            verify_current_runtime=lambda:None,
            RUNTIME=Path("/opt/vf-server-ops"),
            inspect_existing_site=lambda *args:None,
            DOMAIN="www3.m3u8.one",TAIL="pull-synthetic"
        )
        engine=types.ModuleType("server_migration_pull")
        engine.target_identity=lambda:"cp2"
        class PullMigrationError(Exception):pass
        engine.PullMigrationError=PullMigrationError
        calls=[]
        def ok(src,command,**kwargs):
            calls.append(command)
            result=("P07_SSH_READONLY_OK" if len(calls)==1 else
                    "SOURCE_HEX_TEMP_AUDIT=PASS\n"
                    "SOURCE_HEX_TEMP_FILES=1\nSOURCE_HEX_TEMP_UNSAFE=0\n")
            return subprocess.CompletedProcess([],0,result,"")
        engine.source_remote=ok
        engine.ssh_rsync_command=lambda src:"ssh -p 22 -o BatchMode=yes"
        with mock.patch.object(m.subprocess,"run",
                return_value=subprocess.CompletedProcess([],0,b"VERSION",b"")) as rsync,\
             mock.patch.dict(sys.modules,{"server_migration_pull":engine}),\
             mock.patch.object(m,"load_helper",return_value=base),\
             mock.patch.object(m.os,"geteuid",return_value=0),\
             mock.patch.object(sys,"argv",["script","--read-only-source-ssh-and-temp-audit"]),\
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(m.run(),0)
        self.assertIn("SOURCE_HEX_TEMP_FILES=1",output.getvalue())
        self.assertIn("SOURCE_HEX_TEMP_AUDIT=PASS",output.getvalue())
        self.assertIn("SOURCE_TEMP_CLEANUP=NOT_ATTEMPTED",output.getvalue())
        self.assertIn("SOURCE_RSYNC_READONLY=PASS",output.getvalue())
        self.assertIn("--list-only",rsync.call_args.args[0])
        self.assertNotIn("--delete",rsync.call_args.args[0])
        self.assertEqual(len(calls),2)
        self.assertIn("python3 -B",calls[1])

if __name__=="__main__":unittest.main()
