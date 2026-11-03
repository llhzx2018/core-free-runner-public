#!/usr/bin/env python3
"""Synthetic config/DB transaction tests; never reads an actual site's config."""
import contextlib,hashlib,importlib.util,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parent/"dist/p07/0.1.0/overlay/lib"))
def load(name,label):
    spec=importlib.util.spec_from_file_location(label,HERE/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
connect=load("p07-www3-candidate-connect.py","connect")
PHP=shutil.which("php")
CONFIG=b'''<?php
// A comment is not code: define('DB_PASSWORD', 'comment');
define( 'DB_NAME', 'original_copy' );
define( "DB_USER", "olduser" );
define( 'DB_PASSWORD', 'oldpassword' );
define( 'DB_HOST', 'localhost' );
$table_prefix = 'fixture_';
define('AUTH_KEY', 'synthetic-salt-unchanged');
'''
RECORD={"scratch_database":"corrected_copy","username":"candidate_user","password":"synthetic_candidate_password"}

class ConnectionTests(unittest.TestCase):
    def files(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
        root=Path(td.name);root.chmod(0o700)
        path=root/"wp-config.php";path.write_bytes(CONFIG);path.chmod(0o640)
        before,meta=connect.read_file(path,owner=os.getuid())
        return root,path,before,meta

    def test_pinned_candidate_bundle(self):
        self.assertEqual(connect.load_candidate().READONLY_BLOB,"a6285fd4fb44865849d31fd00d368b7af1f00bac")

    def test_explicit_cli_required_before_imports_or_mutations(self):
        for args in ([],["--force"],[connect.CONNECT,"--retry"]):
            with patch.object(sys,"argv",["connect"]+args),patch.object(connect,"load_candidate") as fn:
                with self.assertRaisesRegex(connect.Block,"EXPLICIT_CONNECT_OR_ROLLBACK_REQUIRED"):connect.run()
                fn.assert_not_called()

    @unittest.skipUnless(PHP,"PHP is required by the hosted gate")
    def test_php_token_edit_preserves_every_other_byte_and_does_not_execute(self):
        root,path,_,_=self.files()
        sentinel=root/"must-not-be-written"
        source=CONFIG.replace(b"// A comment", "// 中文注释".encode())+f"file_put_contents('{sentinel}', 'executed');\n".encode()
        source=source.replace(b"\n",b"\r\n")
        record=dict(RECORD,password="quote'backslash\\dollar$literal")
        result=connect.render(source,record,"original_copy",PHP)
        oldsp=connect.spans(source,PHP);newsp=connect.spans(result,PHP)
        def blank(data,positions):
            for row in sorted(positions.values(),key=lambda r:r["start"],reverse=True):data=data[:row["start"]]+b"VALUE"+data[row["end"]:]
            return data
        self.assertEqual(blank(source,oldsp),blank(result,newsp))
        self.assertIn(b"quote\\'backslash\\\\dollar$literal",result)
        self.assertFalse(sentinel.exists())
        self.assertEqual(path.read_bytes(),CONFIG)

    @unittest.skipUnless(PHP,"PHP is required by the hosted gate")
    def test_ambiguous_dynamic_conditional_or_wrong_db_configs_are_denied(self):
        cases=[CONFIG+b"define('DB_HOST','other');\n",
            CONFIG.replace(b"'oldpassword'",b"getenv('DB_PASSWORD')"),
            CONFIG.replace(b"define( 'DB_NAME'",b"if (true) define( 'DB_NAME'"),
            CONFIG.replace(b"define( 'DB_NAME', 'original_copy' );",b"if (true): echo ''; define('DB_NAME','original_copy'); endif;"),
            CONFIG.replace(b"define( 'DB_NAME', 'original_copy' );",b"function hidden() { define('DB_NAME','original_copy'); }"),
            CONFIG.replace(b"'original_copy'",b"'different_copy'"),
            CONFIG.replace(b"<?php",b"<?php namespace Other;"),
            CONFIG.replace(b"define( 'DB_HOST', 'localhost' );",b"// define( 'DB_HOST', 'localhost' );"),
            CONFIG+b"this is not valid PHP"]
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(connect.Block):connect.render(source,RECORD,"original_copy",PHP)

    @unittest.skipUnless(PHP,"PHP is required by the hosted gate")
    def test_completed_conditional_before_literal_settings_is_supported(self):
        for prefix in (b"if (false) { echo 'unused'; }\n",b"if (false): echo 'unused'; endif;\n"):
            source=CONFIG.replace(b"<?php\n",b"<?php\n"+prefix)
            result=connect.render(source,RECORD,"original_copy",PHP)
            self.assertIn(prefix,result)

    def test_success_and_exact_idempotent_rollback_preserve_metadata_and_backups(self):
        root,path,before,meta=self.files();folder=root/"recovery";after=before.replace(b"original_copy",b"corrected_copy")
        check=Mock()
        connect.connect_transaction(folder,path,before,after,meta,"target",check)
        check.assert_called_once();self.assertEqual(connect.read_file(path,owner=os.getuid()),(after,meta))
        for filename in ("original.php","candidate.php","journal.json"):self.assertEqual((folder/filename).stat().st_mode&0o777,0o600)
        with self.assertRaisesRegex(connect.Block,"PRIOR_CONNECTION_ATTEMPT_RETAINED"):
            connect.connect_transaction(folder,path,before,after,meta,"target",check)
        with connect.lock_dir(folder):connect.rollback(folder,"target",path)
        with connect.lock_dir(folder):connect.rollback(folder,"target",path)
        self.assertEqual(connect.read_file(path,owner=os.getuid()),(before,meta))
        self.assertEqual((folder/"candidate.php").read_bytes(),after)

    def test_failed_db_connection_restores_original_config(self):
        root,path,before,meta=self.files();folder=root/"recovery"
        with self.assertRaisesRegex(connect.Block,"CONNECTION_FAILED_ORIGINAL_CONFIG_RESTORED"):
            connect.connect_transaction(folder,path,before,before+b"\n",meta,"target",Mock(side_effect=RuntimeError("private database error")))
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(json.loads((folder/"journal.json").read_text())["status"],"ROLLED_BACK")

    def test_crash_after_replace_can_rollback_without_database_or_source(self):
        root,path,before,meta=self.files();folder=root/"recovery";after=before+b"\n"
        with self.assertRaises(SystemExit):
            connect.connect_transaction(folder,path,before,after,meta,"target",Mock(side_effect=SystemExit(99)))
        self.assertEqual(path.read_bytes(),after)
        with patch.object(subprocess,"run",side_effect=AssertionError("rollback must not contact DB/source")),connect.lock_dir(folder):
            connect.rollback(folder,"target",path)
        self.assertEqual(path.read_bytes(),before)

    def test_prewrite_drift_is_retained_and_postwrite_drift_is_not_overwritten(self):
        for timing in ("before","after"):
            with self.subTest(timing=timing):
                root,path,before,meta=self.files();folder=root/"recovery";drift=before+b"// user edit\n"
                if timing=="before":path.write_bytes(drift)
                def postcheck():
                    if timing=="after":path.write_bytes(drift)
                with self.assertRaisesRegex(connect.Block,"CONFIG_ROLLBACK_UNPROVEN_RETAIN_ALL"):
                    connect.connect_transaction(folder,path,before,before+b"\n",meta,"target",postcheck)
                self.assertEqual(path.read_bytes(),drift)
                self.assertEqual((folder/"original.php").read_bytes(),before)

    def test_tampered_backup_wrong_identity_and_wrong_path_block_rollback(self):
        for cause in ("backup","target","path"):
            with self.subTest(cause=cause):
                root,path,before,meta=self.files();folder=root/"recovery";after=before+b"\n"
                connect.connect_transaction(folder,path,before,after,meta,"target",lambda:None)
                if cause=="backup":(folder/"original.php").write_bytes(b"modified")
                with connect.lock_dir(folder),self.assertRaises(connect.Block):
                    connect.rollback(folder,"other" if cause=="target" else "target",root/"other.php" if cause=="path" else path)
                self.assertEqual(path.read_bytes(),after)

    def test_symlinks_hardlinks_and_unsafe_modes_are_rejected(self):
        root,path,_,_=self.files()
        link=root/"link";link.symlink_to(path)
        with self.assertRaises(OSError):connect.read_file(link,owner=os.getuid())
        link.unlink();os.link(path,link)
        with self.assertRaises(connect.Block):connect.read_file(path,owner=os.getuid())
        link.unlink();path.chmod(0o666)
        with self.assertRaises(connect.Block):connect.read_file(path,owner=os.getuid())

    def test_transaction_lock_rejects_concurrent_access(self):
        root,_,_,_=self.files();folder=root/"recovery";folder.mkdir(mode=0o700)
        with connect.lock_dir(folder):
            with self.assertRaisesRegex(connect.Block,"CONFIG_TRANSACTION_BUSY"):
                with connect.lock_dir(folder):pass

    def test_config_staging_directory_is_private_until_atomic_replace(self):
        root,path,before,meta=self.files();real_replace=os.replace
        def inspect(source,target):
            if Path(target)==path:
                source=Path(source)
                self.assertEqual(source.parent.stat().st_mode&0o777,0o700)
                self.assertEqual(source.parent.stat().st_uid,0)
                self.assertEqual(source.name,"config.php")
            return real_replace(source,target)
        with patch.object(connect.os,"replace",side_effect=inspect):
            connect.replace_config(path,before,before+b"\n",meta)
        self.assertFalse(list(root.glob(".p07-db-write-*")))

    def test_offline_rollback_bundle_integrity_and_no_embedded_credentials(self):
        root,path,before,meta=self.files();folder=root/"recovery"
        # A synthetic standalone rollback entry proves shell integrity gating;
        # the real rollback transaction is independently exercised above.
        name="p07-www3-candidate-connect.py";data=b"print('OFFLINE_ENTRY_REACHED=YES')\n"
        connect.connect_transaction(folder,path,before,before+b"\n",meta,"target",lambda:None,bundle={name:data})
        wrapper=folder/"rollback.sh"
        self.assertNotIn(b"oldpassword",wrapper.read_bytes())
        result=subprocess.run(["bash",str(wrapper)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(b"OFFLINE_ENTRY_REACHED=YES",result.stdout)
        (folder/name).write_bytes(b"raise RuntimeError('should never run')\n")
        result=subprocess.run(["bash",str(wrapper)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b"ROLLBACK_BUNDLE_CHANGED",result.stderr)

    def test_changed_fresh_readback_blocks_without_config_transaction(self):
        with tempfile.TemporaryDirectory() as td:
            base=SimpleNamespace();ro=SimpleNamespace(live_source_catalog=Mock(return_value={}),native_readonly_scratch_dump=Mock(return_value="COMPLETE"),live_target_catalog=Mock(return_value={}))
            stage=SimpleNamespace(import_existing_verified_source=Mock(return_value="digest"))
            candidate=SimpleNamespace(prepare_copy=Mock(return_value=({str(i):"rule" for i in range(25)},1848)),verify_copy=Mock(return_value=(10,198749)))
            temp=tempfile.TemporaryDirectory
            with patch.object(connect.tempfile,"TemporaryDirectory",side_effect=lambda **kw:temp(dir=td)):
                with self.assertRaisesRegex(connect.Block,"CANDIDATE_PRECONNECT_CONTENT_CHANGED"):
                    connect.fresh_proof(candidate,ro,base,stage,object(),{},"source",{"source_snapshot_sha256":"digest"})

    def test_receipt_identity_proof_and_private_file_security(self):
        import site_lifecycle
        root,_,_,_=self.files();base=SimpleNamespace(BASE=root,TAIL="fixture-tail",DOMAIN="fixture.example")
        folder=root/base.TAIL/"target-transactions";folder.mkdir(parents=True,mode=0o700)
        db,user,_=site_lifecycle.derive_database_identity(base.DOMAIN,base.TAIL+":source-rule-copy-v1",1)
        token=hashlib.sha256((base.TAIL+":"+base.DOMAIN+":"+db).encode()).hexdigest()[:20]
        path=folder/("www3-hex-scratch-"+token+".json")
        record={"schema":"p07.www3.source-rule-candidate.v1","migration_id":base.TAIL,"domain":base.DOMAIN,"source_database":"original_copy","scratch_database":db,"username":user,"password":"synthetic_password_only","target_server_identity":"target","status":"VERIFIED_STATIC_COPY_NOT_ACTIVATED","table_collations_explicit":25,"ascii_hex_defaults_equal":10,"verified_rows":198750,"dynamic_groups_omitted":3,"memory_table_count":1,"source_snapshot_sha256":"a"*64}
        record.update({k:False for k in ("source_runtime_frozen","website_activated","original_database_modified","cutover_allowed")})
        record.update({k:True for k in ("previous_scratch_retained","source_engines_preserved","fresh_readback_required_before_activation")})
        connect.write_private(path,json.dumps(record).encode())
        self.assertEqual(connect.candidate_receipt(base,"target","original_copy"),record)
        for key,value in (("target_server_identity","other"),("status","IMPORTED_NOT_VERIFIED"),("verified_rows",198749),("memory_table_count",True),("website_activated",True),("source_snapshot_sha256","missing")):
            path.write_text(json.dumps(dict(record,**{key:value})))
            with self.subTest(key=key),self.assertRaises(connect.Block):connect.candidate_receipt(base,"target","original_copy")
        path.write_text(json.dumps(record));path.chmod(0o644)
        with self.assertRaises(connect.Block):connect.candidate_receipt(base,"target","original_copy")

    def test_cli_fresh_failure_makes_no_config_write_and_rollback_needs_no_sql(self):
        import server_migration_pull as engine
        for action in ("fresh_failure","rollback"):
            with self.subTest(action=action),contextlib.ExitStack() as stack:
                root,path,before,meta=self.files();parent=root/"fixture-tail/target-transactions";parent.mkdir(parents=True,mode=0o700)
                tail={"target_server_identity":"target"}
                base=SimpleNamespace(BASE=root,TAIL="fixture-tail",RUNTIME=root,private_state=Mock(return_value=tail),verify_state=Mock(return_value=(tail,"original_copy")),verify_current_runtime=Mock())
                stage=SimpleNamespace();ro=SimpleNamespace(HELPER_NAME="helper",HELPER_BLOB="h",STAGE_NAME="stage",STAGE_BLOB="s",load=Mock(side_effect=[base,stage]))
                candidate=SimpleNamespace(load_readonly=Mock(return_value=ro))
                stack.enter_context(patch.object(connect,"load_candidate",return_value=candidate))
                stack.enter_context(patch.object(engine,"target_identity",return_value="target"))
                site=stack.enter_context(patch.object(connect,"site_config",return_value=(path,os.getuid(),PHP)))
                receipt=stack.enter_context(patch.object(connect,"candidate_receipt",return_value=RECORD))
                check=stack.enter_context(patch.object(connect,"connection_check"))
                fresh=stack.enter_context(patch.object(connect,"fresh_proof",side_effect=connect.Block("fresh failed")))
                stack.enter_context(patch.object(connect,"render",return_value=before+b"\n"))
                stack.enter_context(patch.object(sys,"path",list(sys.path)))
                stack.enter_context(patch.object(connect.os,"umask"))
                flag=connect.CONNECT if action=="fresh_failure" else connect.ROLLBACK
                stack.enter_context(patch.object(sys,"argv",["connect",flag]))
                folder=parent/connect.JOURNAL_NAME
                if action=="rollback":connect.connect_transaction(folder,path,before,before+b"\n",meta,"target",lambda:None)
                with contextlib.redirect_stdout(__import__('io').StringIO()):
                    if action=="fresh_failure":
                        with self.assertRaisesRegex(connect.Block,"fresh failed"):connect.run()
                        self.assertFalse(folder.exists())
                    else:
                        self.assertEqual(connect.run(),0)
                        receipt.assert_not_called();check.assert_not_called();fresh.assert_not_called()
                        base.verify_state.assert_not_called();base.verify_current_runtime.assert_not_called()
                        site.assert_called_once_with(base,tail,require_php=False)
                self.assertEqual(path.read_bytes(),before)

def real_mapping_proof(container,mysql,root):
    """Called inside the existing 157-table MariaDB restoration fixture."""
    assert PHP is not None and os.geteuid()==0
    mysql("CREATE USER 'candidate_user'@'127.0.0.1' IDENTIFIED BY 'synthetic_candidate_password'; GRANT ALL ON corrected_copy.* TO 'candidate_user'@'127.0.0.1';")
    mysql("CREATE USER 'olduser'@'localhost' IDENTIFIED BY 'oldpassword'; GRANT SELECT ON original_copy.* TO 'olduser'@'localhost';")
    path=root/"wp-config.php";path.write_bytes(CONFIG);path.chmod(0o640)
    before,meta=connect.read_file(path,owner=0);after=connect.render(before,RECORD,"original_copy",PHP)
    def actual_config_readonly_connection(expected_db="corrected_copy"):
        # This config is wholly synthetic (four literals + a salt), so execute
        # it here to independently verify actual PHP literal interpretation.
        result=subprocess.run([PHP,"-r","require $argv[1]; echo json_encode([DB_NAME,DB_USER,DB_PASSWORD,DB_HOST]);",str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
        db,user,password,host=json.loads(result.stdout)
        assert host==("127.0.0.1" if expected_db=="corrected_copy" else "localhost") and db==expected_db
        env=os.environ.copy();env["MYSQL_PWD"]=password
        protocol="socket" if host=="localhost" else "tcp"
        r=subprocess.run(["docker","exec","-e","MYSQL_PWD",container,"mariadb","--no-defaults","--protocol="+protocol,"--host="+host,"--user="+user,"--batch","--skip-column-names","--database="+db,"--execute=SELECT COUNT(*) FROM fixture_156"],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
        # This disposable server contains synthetic users/data only.
        assert r.returncode==0,r.stderr.decode()[:1024]
        assert r.stdout.strip()==b"1",r.stdout[:128]
    folder=root/"connection-recovery"
    actual_config_readonly_connection("original_copy")
    connect.connect_transaction(folder,path,before,after,meta,"fixture-target",actual_config_readonly_connection)
    actual_config_readonly_connection()
    with connect.lock_dir(folder):connect.rollback(folder,"fixture-target",path)
    assert connect.read_file(path,owner=0)==(before,meta)
    actual_config_readonly_connection("original_copy")
    assert mysql("SELECT COUNT(*) FROM corrected_copy.fixture_156;").strip()==b"1"
    assert mysql("SELECT COUNT(*) FROM original_copy.fixture_156;").strip()==b"1"
    print("P07_WWW3_REAL_PHP_CONFIG_AND_DB_CONNECTION=PASS",flush=True)
    print("P07_WWW3_REAL_CONFIG_ROLLBACK_AND_BOTH_DATABASES_RETAINED=PASS",flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["--real-engine"]:
        suite=load("p07-www3-source-rule-tests.py","source_rule_fixtures")
        suite.real_engine(mapping_check=real_mapping_proof)
    else:
        if "--require-php" in sys.argv:
            if PHP is None:raise SystemExit("PHP_REQUIRED_FOR_MACHINE_GATE")
            sys.argv.remove("--require-php")
        unittest.main()
