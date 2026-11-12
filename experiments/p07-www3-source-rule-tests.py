#!/usr/bin/env python3
"""Synthetic fixtures only. Optional Docker MariaDB 11.8 integration."""
import contextlib,gzip,importlib.util,io,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT.parent/"dist/p07/0.1.0/overlay/lib"))
def load(name,label):
    spec=importlib.util.spec_from_file_location(label,ROOT/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
candidate=load("p07-www3-source-rule-candidate.py","candidate")
ro=load("p07-www3-existing-scratch-parity-readonly.py","readonly")
stage=load("p07-www3-isolated-stage.py","stage")

def controls(*, otherwise=("SELECT 0","SET @dummy = 0","SET @dummy = 0")):
    def group(stmt,flag,yes,no):
        yes=yes.replace("'","\\'");no=no.replace("'","\\'")
        return "\n".join([f"/*!50603 SET @{stmt} = IF(@{flag}, '{yes}', '{no}') */;",
            f"/*!50603 PREPARE stmt FROM @{stmt} */;","/*!50603 EXECUTE stmt */;","/*!50603 DEALLOCATE PREPARE stmt */;"])+"\n"
    text="/*!50603 SELECT COUNT(*) INTO @have_pfs FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='performance_schema' AND TABLE_NAME='session_variables' */;\n"
    text+=group("probe","have_pfs","SELECT COUNT(*) INTO @has_rocks FROM performance_schema.session_variables WHERE VARIABLE_NAME='rocksdb_bulk_load'",otherwise[0])
    text+=group("enable","has_rocks","SET SESSION rocksdb_bulk_load=1",otherwise[1])
    text+=group("restore","has_rocks","SET SESSION rocksdb_bulk_load=@saved",otherwise[2])
    return text

def fixture(count=157, *, memory=False):
    text=controls();tables=[];cols=[]
    for i in range(count):
        name=f"fixture_{i:03d}"
        engine="MEMORY" if memory and i==count-1 else "InnoDB"
        text+=f"DROP TABLE IF EXISTS `{name}`;\nCREATE TABLE `{name}` (\n  `id` int NOT NULL,\n  `v` varchar(20) DEFAULT '0',\n"
        if i<10:text+="  `b` varbinary(20) DEFAULT 'abc',\n"
        text+="  PRIMARY KEY (`id`)\n) ENGINE="+engine+" DEFAULT CHARSET=utf8mb3"
        if i>=25:text+=" COLLATE=utf8mb3_general_ci"
        text+=";\n"
        text+=f"INSERT INTO `{name}` VALUES (1,'value'"+(",0x616263" if i<10 else "")+");\n"
        tables.append({"name":name,"engine":engine,"collation":"utf8mb3_general_ci"})
        cols.append({"table":name,"column":"v","charset":"utf8mb3","collation":"utf8mb3_general_ci"})
    return text,{"server":[{"version":"fixture"}],"tables":tables,"columns":cols,
        "collations":[{"name":"utf8mb3_general_ci","charset":"utf8mb3"}]}

class SourceRuleTests(unittest.TestCase):
    def files(self,text=None):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
        root=Path(td.name);source=root/"source.sql.gz"
        text,catalog=fixture() if text is None else (text,fixture()[1])
        with gzip.open(source,"wb") as f:f.write(text.encode())
        return root,source,catalog

    def test_hex_actual_bytes_and_true_difference(self):
        for source,target,expected in [("'abc'","X'616263'","EQUAL_ASCII_HEX_BYTES"),("'abc'","X'616264'","HEX_STRING_BYTES_DIFFER"),("''","X''","EQUAL_ASCII_HEX_BYTES"),("'0'","X'00'","HEX_STRING_BYTES_DIFFER"),("'\\0'","X'00'","EQUAL_ASCII_HEX_BYTES")]:
            result=ro._default_resolution("varbinary(20) DEFAULT "+source,"varbinary(20) DEFAULT "+target)
            self.assertEqual(result["relation"],expected)
            self.assertNotIn("6162",json.dumps(result))

    def test_invalid_hex_bit_and_nonascii_stay_unproven(self):
        for value in ("X'1'","X'zz'","X'61 62'","B'01'","0x31"):
            result=ro._default_resolution("varchar(20) DEFAULT '1'","varchar(20) DEFAULT "+value)
            self.assertNotEqual(result["relation"],"EQUAL_ASCII_HEX_BYTES")
        for typ,value in (("int","'1'"),("varchar(20)","'中'")):
            result=ro._default_resolution(typ+" DEFAULT "+value,typ+" DEFAULT X'31'")
            self.assertEqual(result["relation"],"HEX_STRING_CHARSET_OR_TYPE_UNPROVEN")

    def test_public_rocksdb_shapes_only_and_no_execution(self):
        root,source,_=self.files()
        candidate.prove_rocksdb_only(source,ro)
        for change in ("SET GLOBAL rocksdb_bulk_load=1","SET SESSION rocksdb_bulk_load=2","SET SESSION rocksdb_bulk_load=1; DROP TABLE x"):
            _,altered,_=self.files(fixture()[0].replace("SET SESSION rocksdb_bulk_load=1",change))
            with self.assertRaises(candidate.Block):candidate.prove_rocksdb_only(altered,ro)

    def test_constant_else_variants_pass_complete_preparation_without_execution(self):
        # The old candidate incorrectly required SELECT 1 and SET @dummy=0.
        # Exercise the pinned quarantine and retained-SQL guard too, not just
        # the candidate regex, using both accepted SELECT constants.
        cases=(("SELECT 0","SET @dummy = 0","SET @dummy = 0"),
               ("SELECT 1","SET @dummy = 1","SET @dummy = 2"),
               ("select 0","SET @dummy$ = -17","set @other$ = +3.25"),
               ("SELECT 1","SET @dummy = 99999999999999999999","SET @dummy = -0.125"))
        for branches in cases:
            with self.subTest(branches=branches):
                text=fixture()[0].replace(controls(),controls(otherwise=branches),1)
                if "$" in branches[1]:text=text.replace("@has_rocks","@has$rocks").replace("@saved","@saved$value")
                root,source,catalog=self.files(text);original=source.read_bytes()
                q=root/"q.gz";fixed=root/"fixed.gz"
                with contextlib.redirect_stdout(io.StringIO()),patch.object(subprocess,"run",side_effect=AssertionError("no SQL execution during preparation")):
                    self.assertEqual(candidate.prepare_copy(source,q,fixed,catalog,ro,stage)[1],324)
                self.assertEqual(source.read_bytes(),original)
                data=gzip.decompress(fixed.read_bytes())
                for forbidden in (b"PREPARE",b"EXECUTE",b"rocksdb_bulk_load",b"@dummy"):
                    self.assertNotIn(forbidden,data)
                self.assertEqual(candidate.verify_copy(fixed,fixed,catalog,catalog,ro),(0,157))

    def test_unsafe_or_nonconstant_else_stays_blocked(self):
        rejects={0:("SELECT 2","SELECT @dummy","SELECT NULL","SELECT 0 FROM private_table",
                    "SELECT SLEEP(1)","SELECT 0 INTO OUTFILE 'private'","SELECT 0; DROP TABLE x",
                    "SELECT 0 /* comment */","SELECT 0 -- comment","SELECT 0 # comment"),
                 1:("SET @@GLOBAL.sql_mode=0","SET SESSION rocksdb_bulk_load=0","SET @@session.sql_mode=0",
                    "SET @dummy = SLEEP(1)","SET @dummy = (SELECT 0)","SET @dummy = @other",
                    "SET @dummy = 0+1","SET @dummy = 0, @other = 1","SET @dummy = '0'",
                    "SET @dummy = 0; DROP TABLE x","SET @dummy = 0 /* comment */",
                    "SET @dummy = 0 -- comment","SET @dummy = 0 # comment",
                    "SET @dummy = 0\\n","SET @dummy = "+"9"*21)}
        rejects[2]=rejects[1]
        for index,values in rejects.items():
            for value in values:
                with self.subTest(index=index,value=value):
                    branches=["SELECT 0","SET @dummy = 0","SET @dummy = 0"];branches[index]=value
                    text=fixture()[0].replace(controls(),controls(otherwise=branches),1)
                    root,source,_=self.files(text)
                    with self.assertRaisesRegex(candidate.Block,"ROCKSDB_ELSE_UNPROVEN"):
                        candidate.prove_rocksdb_only(source,ro)

    def test_complete_transform_preserves_data_and_explicit_rules(self):
        root,source,catalog=self.files();q=root/"q.gz";fixed=root/"fixed.gz"
        with contextlib.redirect_stdout(io.StringIO()):plan,count=candidate.prepare_copy(source,q,fixed,catalog,ro,stage)
        self.assertEqual((len(plan),count),(25,324))
        before=gzip.decompress(q.read_bytes());after=gzip.decompress(fixed.read_bytes())
        self.assertEqual(after.count(b"COLLATE=utf8mb3_general_ci"),157)
        self.assertEqual(after.replace(b"DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci;",b"DEFAULT CHARSET=utf8mb3;"),before.replace(b"DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci;",b"DEFAULT CHARSET=utf8mb3;"))
        self.assertEqual(candidate.compatible_schema(fixed,fixed,ro),0)
        self.assertEqual(candidate.verify_copy(fixed,fixed,catalog,catalog,ro),(0,157))
        with self.assertRaises(candidate.Block):candidate.inject_source_rules(q,fixed,plan,ro)

    def test_engine_or_column_or_source_rule_drift_blocks(self):
        for mutate in (lambda c:c["tables"][0].update(engine="ROCKSDB"),lambda c:c["columns"][0].update(collation="other"),lambda c:c["tables"].pop()):
            root,source,catalog=self.files();mutate(catalog)
            with self.assertRaises((candidate.Block,ro.Block)):candidate.source_rule_plan(source,catalog,ro)

    def test_engine_readback_distinguishes_policy_gap_from_actual_drift(self):
        for snapshot,current,expected in (("MEMORY","MEMORY",(0,0)),("InnoDB","MyISAM",(1,0)),("ROCKSDB","ROCKSDB",(0,1)),("private_engine","private_engine",(0,1))):
            text,catalog=fixture();text=text.replace("ENGINE=InnoDB","ENGINE="+snapshot,1)
            root,source,_=self.files(text);catalog["tables"][0]["engine"]=current
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(candidate.source_engine_evidence(source,catalog,ro),expected)
            self.assertNotIn("fixture_",out.getvalue());self.assertNotIn("private_engine",out.getvalue())
            if expected==(0,0):candidate.source_rule_plan(source,catalog,ro)
            else:
                with self.assertRaisesRegex(candidate.Block,"SOURCE_SNAPSHOT_LIVE_ENGINE_DIFFER" if snapshot!=current else "SOURCE_ENGINE_OUTSIDE_CURRENT_COPY_POLICY"):
                    candidate.source_rule_plan(source,catalog,ro)

    def test_memory_is_preserved_and_its_missing_rows_are_not_waived(self):
        text,catalog=fixture(memory=True)
        root,source,_=self.files(text);q=root/"q.gz";fixed=root/"fixed.gz"
        with contextlib.redirect_stdout(io.StringIO()):candidate.prepare_copy(source,q,fixed,catalog,ro,stage)
        data=gzip.decompress(fixed.read_bytes())
        self.assertEqual(data.count(b"ENGINE=MEMORY"),1)
        self.assertEqual(candidate.verify_copy(fixed,fixed,catalog,catalog,ro)[1],157)
        missing=root/"missing.sql"
        missing.write_bytes(data.replace(b"INSERT INTO `fixture_156` VALUES (1,'value');\n",b""))
        with self.assertRaisesRegex(candidate.Block,"CANDIDATE_ROWS_UNPROVEN"):
            candidate.verify_copy(fixed,missing,catalog,catalog,ro)
        catalog["tables"][-1]["engine"]="InnoDB"
        with self.assertRaisesRegex(candidate.Block,"SOURCE_SNAPSHOT_LIVE_ENGINE_DIFFER"):
            candidate.source_rule_plan(source,catalog,ro)

    def test_readonly_engine_mode_cannot_reach_database_or_receipt_writes(self):
        import cloudpanel,server_migration_pull,site_lifecycle
        for digest in ("verified","changed"):
            with self.subTest(digest=digest),tempfile.TemporaryDirectory() as td,contextlib.ExitStack() as s:
                base=SimpleNamespace(RUNTIME=Path(td),DOMAIN="fixture.example",verify_state=lambda:({"target_server_identity":"target"},"source_db"),verify_current_runtime=Mock(),inspect_existing_site=Mock())
                stage_mock=SimpleNamespace(import_existing_verified_source=Mock(return_value=digest),save=Mock(side_effect=AssertionError("no receipt writes")),receipt_path=Mock(side_effect=AssertionError("no intent reservation")),absent_sql=Mock(side_effect=AssertionError("no create path")))
                ro_mock=SimpleNamespace(HELPER_NAME="helper",HELPER_BLOB="x",STAGE_NAME="stage",STAGE_BLOB="y",load=Mock(side_effect=[base,stage_mock]),load_receipt=Mock(return_value={"source_snapshot_sha256":"verified"}),live_source_catalog=Mock(return_value=fixture()[1]))
                s.enter_context(patch.object(sys,"argv",["probe","--read-only-source-engine-evidence"]))
                s.enter_context(patch.object(sys,"path",list(sys.path)))
                s.enter_context(patch.object(candidate.os,"geteuid",return_value=0));s.enter_context(patch.object(candidate.os,"umask"))
                s.enter_context(patch.object(candidate,"load_readonly",return_value=ro_mock))
                s.enter_context(patch.object(server_migration_pull,"target_identity",return_value="target"))
                create=s.enter_context(patch.object(cloudpanel,"add_database",side_effect=AssertionError("no database create")))
                identity=s.enter_context(patch.object(site_lifecycle,"derive_database_identity",side_effect=AssertionError("no candidate identity")))
                report=s.enter_context(patch.object(candidate,"source_engine_evidence"))
                temp=tempfile.TemporaryDirectory
                s.enter_context(patch.object(candidate.tempfile,"TemporaryDirectory",side_effect=lambda **kw:temp(dir=td)))
                out=s.enter_context(contextlib.redirect_stdout(io.StringIO()))
                if digest=="verified":self.assertEqual(candidate.run(),0);report.assert_called_once()
                else:
                    with self.assertRaisesRegex(candidate.Block,"SOURCE_ARCHIVE_RECEIPT_MISMATCH"):candidate.run()
                    report.assert_not_called()
                create.assert_not_called();identity.assert_not_called();stage_mock.save.assert_not_called();stage_mock.receipt_path.assert_not_called();stage_mock.absent_sql.assert_not_called()
                self.assertIn("DATABASE_CREATE_IMPORT_ALTER_DELETE=NONE",out.getvalue())

    def test_schema_true_default_index_and_column_changes_still_block(self):
        root,source,catalog=self.files();q=root/"q.gz";fixed=root/"fixed.gz"
        with contextlib.redirect_stdout(io.StringIO()):candidate.prepare_copy(source,q,fixed,catalog,ro,stage)
        text=gzip.decompress(fixed.read_bytes()).decode()
        for changed in (text.replace("DEFAULT 'abc'","DEFAULT X'616264'",1),text.replace("varchar(20)","varchar(21)",1),text.replace("PRIMARY KEY (`id`)","UNIQUE KEY (`id`)",1)):
            other=root/"other.sql";other.write_text(changed)
            with self.assertRaises(candidate.Block):candidate.compatible_schema(fixed,other,ro)

    def test_one_byte_row_change_is_rejected(self):
        root,source,catalog=self.files();q=root/"q.gz";fixed=root/"fixed.gz"
        with contextlib.redirect_stdout(io.StringIO()):candidate.prepare_copy(source,q,fixed,catalog,ro,stage)
        other=root/"other.sql";other.write_bytes(gzip.decompress(fixed.read_bytes()).replace(b"(1,'value'",b"(1,'changed'",1))
        with self.assertRaisesRegex(candidate.Block,"CANDIDATE_ROWS_UNPROVEN"):candidate.verify_copy(fixed,other,catalog,catalog,ro)

    def test_cli_does_not_accept_implicit_writes(self):
        for args in ([],["--force"],["--create-new-www3-source-rule-candidate","--retry"]):
            with patch.object(sys,"argv",["probe"]+args),patch.object(candidate,"load_readonly") as load:
                with self.assertRaises(candidate.Block):candidate.run()
                load.assert_not_called()

    def test_companion_is_exactly_pinned(self):
        self.assertEqual(candidate.load_readonly().HELPER_BLOB,ro.HELPER_BLOB)

    def test_transaction_retains_old_receipt_and_failed_candidate(self):
        import cloudpanel,inventory,server_migration_pull,site_lifecycle
        for failure in (None,"source","else","create","import","verify","prior_attempt"):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as td,contextlib.ExitStack() as s:
                base=SimpleNamespace(RUNTIME=Path(td),TAIL="tail",DOMAIN="fixture.example",verify_state=lambda:({"target_server_identity":"target"},"source_db"),verify_current_runtime=Mock(),inspect_existing_site=Mock())
                old={"scratch_database":"old_scratch","source_snapshot_sha256":"digest"};old_copy=dict(old)
                saves=[];marker=Path(td)/"new-receipt.json"
                stage_mock=SimpleNamespace(receipt_path=Mock(return_value=marker),absent_sql=Mock(return_value="mysql"),
                    import_existing_verified_source=Mock(return_value="bad" if failure=="source" else "digest"),
                    save=lambda path,record,**kw:saves.append((path,dict(record))),restricted_user=Mock(return_value=(["mysql"],{})),import_only_scratch=Mock())
                if failure=="prior_attempt":stage_mock.receipt_path.side_effect=candidate.Block("SCRATCH_PRIOR_ATTEMPT_RETAINED")
                if failure=="import":stage_mock.import_only_scratch.side_effect=RuntimeError("private import failure")
                catalog=fixture()[1]
                ro_mock=SimpleNamespace(HELPER_NAME="helper",HELPER_BLOB="x",STAGE_NAME="stage",STAGE_BLOB="y",load=Mock(side_effect=[base,stage_mock]),load_receipt=Mock(return_value=old),
                    _catalog_maps=ro._catalog_maps,live_source_catalog=Mock(return_value=catalog),native_readonly_scratch_dump=Mock(return_value="COMPLETE"),live_target_catalog=Mock(return_value=catalog))
                s.enter_context(patch.object(sys,"argv",["probe","--create-new-www3-source-rule-candidate"]))
                s.enter_context(patch.object(sys,"path",list(sys.path)))
                s.enter_context(patch.object(candidate.os,"geteuid",return_value=0));s.enter_context(patch.object(candidate.os,"umask"))
                s.enter_context(patch.object(candidate,"load_readonly",return_value=ro_mock))
                s.enter_context(patch.object(server_migration_pull,"target_identity",return_value="target"))
                s.enter_context(patch.object(site_lifecycle,"derive_database_identity",return_value=("p07candidate000","user","private_password")))
                s.enter_context(patch.object(inventory,"build_manifest",return_value={"sites":[]}))
                create=s.enter_context(patch.object(cloudpanel,"add_database",side_effect=RuntimeError("private create failure") if failure=="create" else None))
                temp=tempfile.TemporaryDirectory
                s.enter_context(patch.object(candidate.tempfile,"TemporaryDirectory",side_effect=lambda **kw:temp(dir=td)))
                def prepare(original,q,repaired,*args):
                    if failure=="else":raise candidate.Block("ROCKSDB_ELSE_UNPROVEN")
                    repaired.write_bytes(b"synthetic");return ({str(i):"rule" for i in range(25)},1848)
                s.enter_context(patch.object(candidate,"prepare_copy",side_effect=prepare))
                s.enter_context(patch.object(candidate,"verify_copy",return_value=(10,157),side_effect=candidate.Block("CANDIDATE_ROWS_UNPROVEN") if failure=="verify" else None))
                out=s.enter_context(contextlib.redirect_stdout(io.StringIO()))
                if failure:
                    with self.assertRaises(Exception):candidate.run()
                else:self.assertEqual(candidate.run(),0)
                self.assertEqual(old,old_copy)
                self.assertTrue(all(path==marker for path,record in saves))
                self.assertNotIn("private_password",out.getvalue())
                if failure in ("source","else","prior_attempt"):create.assert_not_called();self.assertEqual(saves,[])
                elif failure:self.assertEqual(saves[-1][1]["status"],"CANDIDATE_UNPROVEN_RETAIN_NO_RETRY")
                else:
                    self.assertEqual(saves[-1][1]["status"],"VERIFIED_STATIC_COPY_NOT_ACTIVATED")
                    self.assertTrue(saves[-1][1]["fresh_readback_required_before_activation"])
                    self.assertTrue(saves[-1][1]["source_engines_preserved"])


def real_engine(mapping_check=None):
    """No network/ports/host DB mounts; only this disposable synthetic server."""
    container="p07-rule-fixture-"+str(os.getpid())
    subprocess.run(["docker","run","-d","--name",container,"--network=none","--tmpfs","/var/lib/mysql:rw","-e","MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=1","mariadb:11.8"],check=True,stdout=subprocess.DEVNULL)
    def mysql(sql):
        p=subprocess.run(["docker","exec","-i",container,"mariadb","--no-defaults","-uroot","--batch","--raw","--skip-column-names"],input=sql.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if p.returncode:raise AssertionError("synthetic SQL failed: "+p.stderr.decode())
        return p.stdout
    try:
        for i in range(60):
            # The image starts a temporary socket-only server during init.
            # A socket ping can pass before that server shuts down, destroying
            # MEMORY rows. Require a real query on final TCP loopback instead.
            check=subprocess.run(["docker","exec",container,"mariadb","--no-defaults","--protocol=tcp","--host=127.0.0.1","-uroot","--execute=SELECT 1"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if check.returncode==0:break
            time.sleep(1)
        else:raise AssertionError("synthetic DB not ready")
        version=mysql("SELECT VERSION();").decode().strip();assert version.startswith("11.8.")
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/"source.sql.gz";q=root/"q.gz";fixed=root/"fixed.gz"
            text,catalog=fixture(memory=True)
            with gzip.open(source,"wb") as f:f.write(text.encode())
            candidate.prepare_copy(source,q,fixed,catalog,ro,stage)
            mysql("CREATE DATABASE original_copy; CREATE DATABASE corrected_copy;")
            # Existing target fixture deliberately keeps the unfixed new default.
            mysql("USE original_copy;\n"+gzip.decompress(q.read_bytes()).decode())
            old=mysql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='original_copy' AND TABLE_COLLATION='utf8mb3_uca1400_ai_ci';").strip()
            assert old==b"25",old
            mysql("USE corrected_copy;\n"+gzip.decompress(fixed.read_bytes()).decode())
            readback=root/"target.sql"
            result=subprocess.run(["docker","exec",container,"mariadb-dump","--no-defaults","-uroot","--single-transaction","--skip-lock-tables","--hex-blob","--skip-extended-insert","--skip-comments","--skip-dump-date","corrected_copy"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
            readback.write_bytes(result.stdout)
            target={key:[json.loads(line) for line in mysql(query).decode().splitlines()] for key,query in ro._metadata_queries("corrected_copy").items()}
            result=candidate.verify_copy(fixed,readback,catalog,target,ro)
            assert result[1]==157,result
            if mapping_check is not None:mapping_check(container,mysql,root)
            engine_counts=mysql("SELECT ENGINE,COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='corrected_copy' GROUP BY ENGINE ORDER BY ENGINE;").decode().strip().splitlines()
            assert engine_counts==["InnoDB\t156","MEMORY\t1"],engine_counts
            assert mysql("SELECT COUNT(*) FROM corrected_copy.fixture_156;").strip()==b"1"
            assert mysql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='original_copy' AND TABLE_COLLATION='utf8mb3_uca1400_ai_ci';").strip()==b"25"
            # Real changed bytes must still fail the verifier.
            mysql("UPDATE corrected_copy.fixture_000 SET v='changed' WHERE id=1;")
            changed=subprocess.run(["docker","exec",container,"mariadb-dump","--no-defaults","-uroot","--hex-blob","--skip-extended-insert","--skip-comments","--skip-dump-date","corrected_copy"],stdout=subprocess.PIPE,check=True)
            readback.write_bytes(changed.stdout)
            try:candidate.verify_copy(fixed,readback,catalog,target,ro)
            except candidate.Block as exc:assert str(exc)=="CANDIDATE_ROWS_UNPROVEN",str(exc)
            else:raise AssertionError("changed row incorrectly accepted")
            # Loss of a volatile MEMORY row must invalidate the new readback.
            mysql("UPDATE corrected_copy.fixture_000 SET v='value' WHERE id=1; DELETE FROM corrected_copy.fixture_156;")
            missing=subprocess.run(["docker","exec",container,"mariadb-dump","--no-defaults","-uroot","--hex-blob","--skip-extended-insert","--skip-comments","--skip-dump-date","corrected_copy"],stdout=subprocess.PIPE,check=True)
            readback.write_bytes(missing.stdout)
            try:candidate.verify_copy(fixed,readback,catalog,target,ro)
            except candidate.Block as exc:assert str(exc)=="CANDIDATE_ROWS_UNPROVEN",str(exc)
            else:raise AssertionError("missing MEMORY row incorrectly accepted")
            print("P07_SOURCE_RULE_REAL_MARIADB_11_8=PASS",flush=True)
            print("P07_SOURCE_RULE_SELECT_ZERO_QUARANTINE_RESTORE=PASS",flush=True)
            print("P07_SOURCE_RULE_EXISTING_DATABASE_RETAINED=PASS",flush=True)
            print("P07_SOURCE_RULE_TRUE_ROW_DIFFERENCE_DENIED=PASS",flush=True)
            print("P07_SOURCE_RULE_REAL_HEX_DEFAULTS="+str(result[0]),flush=True)
            print("P07_SOURCE_RULE_REAL_ENGINES=INNODB:156,MEMORY:1",flush=True)
            print("P07_SOURCE_RULE_MEMORY_ROW_LOSS_DENIED=PASS",flush=True)
    finally:
        subprocess.run(["docker","rm","-f",container],check=False,stdout=subprocess.DEVNULL)

if __name__=="__main__":
    if sys.argv[1:]==["--real-engine"]:real_engine()
    else:unittest.main()
