"""Three original DB two-sweep paused-source private copy; synthetic no VPS."""
from __future__ import annotations
import copy
import gzip
import hashlib
import json
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
import migration_chain_paused_sql as sql
import migration_chain_source_pause as pause
import server_migration as legacy
import server_migration_pull as pull
from tests.test_migration_chain_execution_scope import three_partial_tasks
from tests.test_migration_chain_final_saga import plan


class PausedThreeOriginalDatabasesTests(unittest.TestCase):
    def setUp(self):
        self.tasks=tuple(three_partial_tasks())
        for task in self.tasks:
            task["runtime_assets"]={"system_cron":[],"user_cron":[],"pm2":[]}
        self.p=plan()
        self.target=self.tasks[0]["target_server_identity"]
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.parent=root/self.tasks[0]["migration_id"]
        self.parent.mkdir(mode=0o700)
        for mod in (legacy,pull):
            m=mock.patch.object(mod,"STATE_ROOT",root)
            m.start()
            self.addCleanup(m.stop)
        mid,control,digest=pause._control(self.p,self.tasks,self.target)
        self.pause_mid=mid
        paused=pause._private(self.p,self.parent)
        paused.mkdir(mode=0o700)
        legacy.atomic_private_json(paused/"journal.json",{
            "schema":pause.SCHEMA,
            "status":"SOURCE_RUNTIME_PAUSED_DB_WRITE_FENCE_NOT_PROVEN",
            "site_count":17,
            "plan_sha256":self.p["plan_sha256"],
            "target_identity_sha256":self.p["target_identity_sha256"],
            "control_sha256":digest,
            "source_recovery_id":mid,
            "source_runtime_paused":True,
            "source_business_writes_paused":False,
            "source_final_database_parity":False,
            "source_deleted":False,
            "dns_changed":False,
            "cutover_allowed":False,
        })
        self.exports=[]
        self.copies=[]
        self.cleanup=[]

    def source_python(self,source,runtime,command,*args,**kw):
        if command=="_source-frozen-readback":
            return SimpleNamespace(returncode=0,stdout=json.dumps({
                "status":"SOURCE_17_RUNTIME_STOP_READBACK_PASS_NOT_DATABASE_FENCE",
                "migration_id":self.pause_mid,
                "site_count":17,
                "source_nginx_inactive_verified":True,
                "cron_pm2_journal_verified":True,
                "source_business_writers_all_fenced":False,
                "cutover_allowed":False,
            }))
        self.exports.append((command,args))
        return SimpleNamespace(returncode=0,stdout='{"status":"PASS"}')

    def pull_source(self,source,remote,local,**kw):
        self.copies.append((remote,local,kw))
        with gzip.open(local,"wt",encoding="utf8") as f:
            f.write("CREATE TABLE posts (id INT);\nINSERT INTO posts VALUES (1);\n")

    def source_cleanup(self,source,command,**kw):
        self.cleanup.append(command)
        return SimpleNamespace(returncode=0)

    def _transport(self,stack):
        stage=stack.enter_context(mock.patch.object(
            pull,"source_python",side_effect=self.source_python))
        transfer=stack.enter_context(mock.patch.object(
            pull,"pull_path",side_effect=self.pull_source))
        cleanup=stack.enter_context(mock.patch.object(
            pull,"source_remote",side_effect=self.source_cleanup))
        stack.enter_context(mock.patch.object(
            pull,"target_identity",return_value=self.target))
        compare=stack.enter_context(mock.patch.object(
            pull,"compare_database_dumps",
            return_value="CANONICAL_SQL_EXACT"))
        return stage,transfer,cleanup,compare

    def stage(self):
        return sql.copy_paused_three_source_dbs(
            self.p,self.tasks,root=self.parent,target_identity=self.target,
            confirmation=sql.CONFIRM)

    def test_original_three_two_sweeps_no_existing_target_writes(self):
        original=copy.deepcopy(self.tasks)
        with ExitStack() as stack:
            _,puller,cleaner,compare=self._transport(stack)
            target=stack.enter_context(mock.patch.object(
                pull.cloudpanel,"import_database"))
            saved=stack.enter_context(mock.patch.object(
                pull,"save_state"))
            stop=stack.enter_context(mock.patch.object(
                pull,"freeze_old_server"))
            result=self.stage()
            self.assertEqual(result["original_database_count"],3)
            self.assertEqual(result["private_source_dumps_verified"],6)
            self.assertFalse(result["source_business_writers_all_fenced"])
            self.assertFalse(result["source_target_database_parity"])
            self.assertFalse(result["cutover_allowed"])
            self.assertEqual(len(self.exports),6)
            self.assertEqual(len(self.copies),6)
            self.assertEqual(len(self.cleanup),6)
            self.assertEqual(compare.call_count,3)
            self.assertTrue(all(k["delete"] is False
                                for _r,_p,k in self.copies))
            for effect in (target,saved,stop):effect.assert_not_called()
        self.assertEqual(original,self.tasks)
        result=sql.verify_paused_three_source_dbs(
            self.p,self.tasks,root=self.parent,target_identity=self.target)
        self.assertEqual(result["database_count"],3)
        self.assertFalse(result["target_import_performed"])
        self.assertFalse(result["cutover_allowed"])
        with mock.patch.object(pull,"source_python") as remote:
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,"PREVIOUS_ATTEMPT_RETAINED"):
                self.stage()
            remote.assert_not_called()

    def test_no_confirmation_refuses_before_any_remote_write(self):
        with mock.patch.object(pull,"source_python") as remote:
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,"CONFIRM"):
                sql.copy_paused_three_source_dbs(
                    self.p,self.tasks,root=self.parent,
                    target_identity=self.target,confirmation="CUTOVER")
            remote.assert_not_called()

    def test_no_proven_pause_receipt_blocks_before_export(self):
        (pause._private(self.p,self.parent)/"journal.json").unlink()
        with mock.patch.object(pull,"target_identity",return_value=self.target), \
             mock.patch.object(pull,"source_python") as remote:
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,"PAUSE_RECEIPT_UNAVAILABLE"):
                self.stage()
            remote.assert_not_called()
        self.assertFalse((self.parent/sql.ROOT_NAME).exists())

    def test_ambiguous_remote_pause_refuses_before_private_stage(self):
        with mock.patch.object(pull,"target_identity",return_value=self.target), \
             mock.patch.object(pull,"source_python",
                return_value=SimpleNamespace(returncode=9,stdout="")):
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,"READBACK_UNAVAILABLE"):
                self.stage()
        self.assertFalse((self.parent/sql.ROOT_NAME).exists())

    def test_sixth_export_failure_keeps_private_intent_without_replay(self):
        with ExitStack() as stack:
            self._transport(stack)
            def interrupted(source,runtime,cmd,*args,**kw):
                x=self.source_python(source,runtime,cmd,*args,**kw)
                if len(self.exports)==6:
                    raise TimeoutError("undisclosed sql")
                return x
            stack.enter_context(mock.patch.object(
                pull,"source_python",side_effect=interrupted))
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,"RECOVERY_REQUIRED"):
                self.stage()
        receipt=json.loads(
            (self.parent/sql.ROOT_NAME/"journal.json").read_text())
        self.assertEqual(receipt["status"],
                         "PRIVATE_OR_SOURCE_RECOVERY_REQUIRED_RETAIN")
        self.assertEqual(len(self.cleanup),5)
        self.assertFalse(receipt["cutover_allowed"])
        self.assertNotIn("undisclosed",json.dumps(receipt))
        with mock.patch.object(pull,"source_python") as remote:
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,"PREVIOUS_ATTEMPT_RETAINED"):
                self.stage()
            remote.assert_not_called()

    def test_original_guarded_sql_comparator_detects_real_row_drift(self):
        # Exercise the real existing P07 SQL guard, not only mock statuses.
        a=self.parent/"sql-a.gz"
        b=self.parent/"sql-b.gz"
        for path,value in ((a,1),(b,1)):
            with gzip.open(path,"wt",encoding="utf8") as stream:
                stream.write(
                    "CREATE TABLE posts (id INT);\n"
                    f"INSERT INTO posts VALUES ({value});\n")
        self.assertEqual(
            pull.compare_database_dumps(a,b),"CANONICAL_SQL_EXACT")
        with gzip.open(b,"wt",encoding="utf8") as stream:
            stream.write(
                "CREATE TABLE posts (id INT);\n"
                "INSERT INTO posts VALUES (2);\n")
        with self.assertRaises(pull.PullMigrationError):
            pull.compare_database_dumps(a,b)

    def test_original_guarded_sql_comparator_refuses_identical_privilege_sql(self):
        a=self.parent/"priv-a.gz"
        b=self.parent/"priv-b.gz"
        for path in (a,b):
            with gzip.open(path,"wt",encoding="utf8") as stream:
                stream.write(
                    "CREATE TABLE posts (id INT);\n"
                    "SET GLOBAL sql_mode = '';\n"
                    "INSERT INTO posts VALUES (1);\n")
        with self.assertRaises(pull.PullMigrationError):
            pull.compare_database_dumps(a,b)

    def test_failed_old_source_export_retains_original_temp_no_delete(self):
        with ExitStack() as stack:
            self._transport(stack)
            def rejected(source,runtime,command,*args,**kwargs):
                if command=="_source-frozen-readback":
                    return self.source_python(
                        source,runtime,command,*args,**kwargs)
                self.exports.append((command,args))
                return SimpleNamespace(returncode=12,stdout="")
            stack.enter_context(mock.patch.object(
                pull,"source_python",side_effect=rejected))
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,"RECOVERY_REQUIRED"):
                self.stage()
        self.assertEqual(len(self.exports),1)
        self.assertEqual(len(self.copies),0)
        self.assertEqual(len(self.cleanup),0)
        receipt=json.loads(
            (self.parent/sql.ROOT_NAME/"journal.json").read_text())
        self.assertEqual(receipt["status"],
                         "PRIVATE_OR_SOURCE_RECOVERY_REQUIRED_RETAIN")
        self.assertEqual(receipt["active_pass"],1)
        self.assertFalse(receipt["cutover_allowed"])

    def test_failed_transfer_leaves_private_old_source_sql_for_recovery(self):
        with ExitStack() as stack:
            self._transport(stack)
            def interrupted_copy(source,remote,local,**kwargs):
                self.copies.append((remote,local,kwargs))
                raise OSError("secret connection reset")
            stack.enter_context(mock.patch.object(
                pull,"pull_path",side_effect=interrupted_copy))
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,"RECOVERY_REQUIRED"):
                self.stage()
        self.assertEqual(len(self.exports),1)
        self.assertEqual(len(self.copies),1)
        self.assertEqual(len(self.cleanup),0)
        receipt=json.loads(
            (self.parent/sql.ROOT_NAME/"journal.json").read_text())
        self.assertEqual(receipt["active_pass"],1)
        self.assertNotIn("secret",json.dumps(receipt))

    def test_failed_source_temp_cleanup_retains_specific_recovery_status(self):
        with ExitStack() as stack:
            self._transport(stack)
            stack.enter_context(mock.patch.object(
                pull,"source_remote",
                return_value=SimpleNamespace(returncode=7)))
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,"RECOVERY_REQUIRED"):
                self.stage()
        receipt=json.loads(
            (self.parent/sql.ROOT_NAME/"journal.json").read_text())
        self.assertEqual(
            receipt["status"],"SOURCE_PRIVATE_SQL_CLEANUP_UNVERIFIED")
        self.assertEqual(receipt["active_pass"],1)
        self.assertFalse(receipt["cutover_allowed"])

    def test_two_pass_drift_refuses_target_promotion(self):
        with ExitStack() as stack:
            self._transport(stack)
            stack.enter_context(mock.patch.object(
                pull,"compare_database_dumps",return_value=""))
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,"RECOVERY_REQUIRED"):
                self.stage()
        receipt=json.loads(
            (self.parent/sql.ROOT_NAME/"journal.json").read_text())
        self.assertFalse(receipt["source_target_database_parity"])
        self.assertFalse(receipt["cutover_allowed"])

    def test_copied_private_sql_hash_tamper_detected(self):
        with ExitStack() as stack:
            self._transport(stack)
            self.stage()
        folder=self.parent/sql.ROOT_NAME
        data=next(folder.glob("*-pass1.sql.gz"))
        data.write_bytes(b"tampered")
        with self.assertRaisesRegex(
            sql.PausedDatabaseBlocked,"CONTENT_CHANGED|DUMP_UNSAFE"):
            sql.verify_paused_three_source_dbs(
                self.p,self.tasks,root=self.parent,target_identity=self.target)

    def test_receipt_rehashed_but_two_pass_sql_rows_differ_rejected(self):
        # A matching journal hash only proves byte identity to that journal.
        # It must not turn a semantically different second export into PASS.
        with ExitStack() as stack:
            self._transport(stack)
            self.stage()
        folder=self.parent/sql.ROOT_NAME
        journal=folder/"journal.json"
        record=json.loads(journal.read_text())
        row=record["completed"][0]
        target=folder/row["pass_2_name"]
        with gzip.open(target,"wt",encoding="utf8") as stream:
            stream.write("CREATE TABLE posts (id INT);\n")
            stream.write("INSERT INTO posts VALUES (999);\n")
        row["pass_2_sha256"]=hashlib.sha256(target.read_bytes()).hexdigest()
        row["pass_2_bytes"]=target.stat().st_size
        legacy.atomic_private_json(journal,record)
        with mock.patch.object(pull,"source_python") as remote, \
             mock.patch.object(pull.cloudpanel,"import_database") as importer, \
             mock.patch.object(pull,"save_state") as saved:
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,
                "SECONDARY_SQL_CONTENT_COMPARE_FAILED"):
                sql.verify_paused_three_source_dbs(
                    self.p,self.tasks,root=self.parent,
                    target_identity=self.target)
            remote.assert_not_called()
            importer.assert_not_called()
            saved.assert_not_called()

    def test_receipt_mode_forgery_rejected_even_when_bytes_unchanged(self):
        with ExitStack() as stack:
            self._transport(stack)
            self.stage()
        journal=self.parent/sql.ROOT_NAME/"journal.json"
        record=json.loads(journal.read_text())
        record["completed"][0]["source_two_pass_verification_mode"]=(
            "CROSS_ENGINE_LOGICAL_CONTENT")
        legacy.atomic_private_json(journal,record)
        with self.assertRaisesRegex(
            sql.PausedDatabaseBlocked,"SECONDARY_SQL_MODE_CHANGED"):
            sql.verify_paused_three_source_dbs(
                self.p,self.tasks,root=self.parent,
                target_identity=self.target)

    def test_cross_owner_sql_file_names_rejected_even_if_bytes_match(self):
        with ExitStack() as stack:
            self._transport(stack)
            self.stage()
        journal=self.parent/sql.ROOT_NAME/"journal.json"
        record=json.loads(journal.read_text())
        one,two=record["completed"][:2]
        for key in (
            "pass_1_name", "pass_2_name",
            "pass_1_sha256", "pass_2_sha256",
            "pass_1_bytes", "pass_2_bytes",
        ):
            one[key],two[key]=two[key],one[key]
        legacy.atomic_private_json(journal,record)
        with mock.patch.object(pull,"source_python") as remote, \
             mock.patch.object(pull.cloudpanel,"import_database") as db_write:
            with self.assertRaisesRegex(
                sql.PausedDatabaseBlocked,
                "PRIVATE_OWNER_FILENAME_CHANGED"):
                sql.verify_paused_three_source_dbs(
                    self.p,self.tasks,root=self.parent,
                    target_identity=self.target)
            remote.assert_not_called()
            db_write.assert_not_called()

    def test_unknown_journal_comparison_mode_rejected(self):
        with ExitStack() as stack:
            self._transport(stack)
            self.stage()
        journal=self.parent/sql.ROOT_NAME/"journal.json"
        record=json.loads(journal.read_text())
        record["completed"][0]["source_two_pass_verification_mode"]=(
            "SKIP_GUARDS")
        legacy.atomic_private_json(journal,record)
        with self.assertRaisesRegex(
            sql.PausedDatabaseBlocked,"ORIGINAL_OWNER_OR_MODE_DRIFT"):
            sql.verify_paused_three_source_dbs(
                self.p,self.tasks,root=self.parent,
                target_identity=self.target)

    def test_existing_cli_no_frozen_pause_gives_no_cutover(self):
        byid={s["migration_id"]:s for s in self.tasks}
        ids=tuple(byid)
        with mock.patch.object(pull,"load_state",side_effect=byid.__getitem__), \
             mock.patch.object(pull,"target_identity",return_value=self.target), \
             mock.patch.object(pull,"source_python") as ssh:
            with self.assertRaisesRegex(
                pull.PullMigrationError,"COPY_CONFIRMATION_REQUIRED"):
                pull.chain_seventeen_site_delivery(
                    *ids,action="paused-db-copy",confirm="CUTOVER")
            ssh.assert_not_called()

    def test_existing_cli_wires_exact_three_dbs_only_and_read_only_verify(self):
        byid={s["migration_id"]:s for s in self.tasks}
        ids=tuple(byid)
        with mock.patch.object(pull,"load_state",side_effect=byid.__getitem__), \
             mock.patch.object(pull,"target_identity",return_value=self.target), \
             mock.patch.object(sql,"copy_paused_three_source_dbs",
                               return_value={"status":"PRIVATE_TWO_PASS_NOT_CUTOVER"}) as copy_db, \
             mock.patch.object(sql,"verify_paused_three_source_dbs",
                               return_value={"status":"READBACK_NOT_CUTOVER"}) as verify_db:
            first=pull.chain_seventeen_site_delivery(
                *ids,action="paused-db-copy",confirm=sql.CONFIRM)
            self.assertEqual(first["status"],"PRIVATE_TWO_PASS_NOT_CUTOVER")
            self.assertEqual(copy_db.call_args.args[1],self.tasks)
            self.assertEqual(copy_db.call_args.kwargs["confirmation"],sql.CONFIRM)
            second=pull.chain_seventeen_site_delivery(
                *ids,action="verify-paused-dbs")
            self.assertEqual(second["status"],"READBACK_NOT_CUTOVER")
            copy_db.assert_called_once()
            verify_db.assert_called_once()



if __name__ == "__main__":
    unittest.main()
