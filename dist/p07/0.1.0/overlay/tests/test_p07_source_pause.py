"""P07 real source-pause boundary, synthetic exact-owner proof only."""
from __future__ import annotations
import copy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
import migration_chain_source_pause as pause
import server_migration as legacy
import server_migration_pull as pull
from tests.test_migration_chain_execution_scope import three_partial_tasks
from tests.test_migration_chain_final_saga import plan


class SourcePauseTests(unittest.TestCase):
    def setUp(self):
        self.states=tuple(three_partial_tasks())
        for s in self.states:
            s["runtime_assets"]={"system_cron":[],"user_cron":[],"pm2":[]}
        self.p=plan()
        self.target=self.states[0]["target_server_identity"]
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.parent=root/self.states[0]["migration_id"]
        self.parent.mkdir(mode=0o700)
        for obj in (legacy,pull):
            p=mock.patch.object(obj,"STATE_ROOT",root)
            p.start()
            self.addCleanup(p.stop)

    def preview(self):
        return pause.source_pause_preview(
            self.p,self.states,root=self.parent,target_identity=self.target)

    def stage(self,confirmation=pause.PAUSE_CONFIRM):
        return pause.stage_and_pause_source(
            self.p,self.states,root=self.parent,target_identity=self.target,
            authorize_source_outage=True,confirmation=confirmation)

    def successful_network(self,stack):
        mid,control,_=pause._control(self.p,self.states,self.target)
        calls={
          "target":stack.enter_context(mock.patch.object(
              pull,"target_identity",return_value=self.target)),
          "nginx":stack.enter_context(mock.patch.object(
              pull,"source_nginx_status",
              return_value={"site_nginx_running":True})),
          "stage":stack.enter_context(mock.patch.object(
              pull,"stage_source_runtime",return_value=
              f"/var/lib/vf-server-ops/pull-source/{mid}/runtime")),
          "hash":stack.enter_context(mock.patch.object(
              pull,"source_export_helper_matches_current",return_value=True)),
          "push":stack.enter_context(mock.patch.object(
              pull,"push_control_file")),
          "remote":stack.enter_context(mock.patch.object(
              pull,"source_python",return_value=SimpleNamespace(
              returncode=0,stdout=json.dumps({
                "status":"SOURCE_FROZEN","migration_id":mid,
                "dns_changed":False,"source_deleted":False})))),
        }
        return calls

    def test_pure_preview_17_3_no_remote(self):
        with mock.patch.object(pull,"source_python") as ssh:
            res=self.preview()
        self.assertEqual(res["status"],"SOURCE_PAUSE_PREVIEW_ONLY")
        self.assertEqual(res["site_count"],17)
        self.assertEqual(res["original_task_count"],3)
        self.assertFalse(res["source_business_writes_paused"])
        self.assertFalse(res["cutover_allowed"])
        self.assertEqual(list(self.parent.iterdir()),[])
        ssh.assert_not_called()

    def test_explicit_outage_before_any_state_or_transport(self):
        with mock.patch.object(pull,"target_identity") as target:
            for x in ("CUTOVER","",None):
                with self.assertRaisesRegex(
                    pause.SourcePauseBlocked,"SEPARATE_ALL_17_OUTAGE"):
                    self.stage(x)
            target.assert_not_called()
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_exactly_one_freeze_and_no_false_db_parity(self):
        before=copy.deepcopy(self.states)
        with ExitStack() as s:
            calls=self.successful_network(s)
            res=self.stage()
            self.assertEqual(res["status"],
                             "SOURCE_RUNTIME_PAUSED_DB_WRITE_FENCE_NOT_PROVEN")
            self.assertTrue(res["source_runtime_paused"])
            self.assertFalse(res["source_business_writes_paused"])
            self.assertFalse(res["source_final_database_parity"])
            self.assertFalse(res["cutover_allowed"])
            args=calls["remote"].call_args.args
            self.assertEqual(args[2],"_source-freeze")
            self.assertEqual(args.count("--require-fresh"),1)
            self.assertEqual(args[args.index("--expected-site-count")+1],"17")
            calls["remote"].assert_called_once()
            with self.assertRaisesRegex(
                pause.SourcePauseBlocked,"PREVIOUS_ATTEMPT_RETAINED"):
                self.stage()
            calls["remote"].assert_called_once()
        self.assertEqual(self.states,before)

    def test_uncertain_ssh_retained_without_retry_or_secret(self):
        with ExitStack() as s:
            calls=self.successful_network(s)
            calls["remote"].side_effect=TimeoutError("secret ssh")
            with self.assertRaisesRegex(
                pause.SourcePauseBlocked,"RECONCILIATION_REQUIRED"):
                self.stage()
            receipt=json.loads((self.parent/pause.ROOT_NAME/"journal.json").read_text())
            self.assertEqual(receipt["status"],
                             "SOURCE_PAUSE_RESULT_UNCERTAIN_RECOVERY_REQUIRED")
            self.assertNotIn("secret",json.dumps(receipt))
            with self.assertRaisesRegex(
                pause.SourcePauseBlocked,"PREVIOUS_ATTEMPT_RETAINED"):
                self.stage()

    def test_incomplete_original_runtime_inventory_blocks(self):
        original=copy.deepcopy(self.states)
        original[1]["runtime_assets"].pop("pm2")
        with mock.patch.object(pull,"source_python") as ssh:
            with self.assertRaises(pause.SourcePauseBlocked):
                pause.source_pause_preview(
                    self.p,tuple(original),root=self.parent,
                    target_identity=self.target)
            ssh.assert_not_called()

    def test_restoration_is_not_falsely_reported(self):
        with ExitStack() as stack:
            self.successful_network(stack)
            self.stage()
        with self.assertRaisesRegex(
            pause.SourcePauseBlocked,"EXPLICIT_AUTHORIZATION"):
            pause.restore_paused_source_pre_dns(
                self.p,self.states,root=self.parent,
                target_identity=self.target,confirmation="CUTOVER")
        with mock.patch.object(pull,"source_python") as remote:
            result=pause.restore_paused_source_pre_dns(
                self.p,self.states,root=self.parent,
                target_identity=self.target,
                confirmation=pause.RESTORE_CONFIRM,
                verified_old_dns_route=True)
            remote.assert_not_called()
        self.assertEqual(result["status"],
                         "RESTORE_REQUEST_PREPARED_EXECUTION_BLOCKED")
        self.assertFalse(result["source_restore_performed"])
        self.assertFalse(result["cutover_allowed"])

    def test_old_server_requires_exact_original_control_digest_before_stop(self):
        mid,ctl,_=pause._control(self.p,self.states,self.target)
        file=self.parent/"control.json"
        legacy.atomic_private_json(file,ctl)
        good=hashlib.sha256(file.read_bytes()).hexdigest()
        with mock.patch.object(legacy,"freeze_source_runtime") as do_stop:
            for digest in (good,"0"*64):
                with self.assertRaises(pull.PullMigrationError):
                    pull.source_freeze(
                        mid,file,require_fresh=True,expected_site_count=17
                        if digest!=good else 16,
                        expected_control_sha256=digest)
            do_stop.assert_not_called()


    def test_old_source_control_valid_only_for_original_17_and_owned_cron_pm2(self):
        _mid,ctl,_digest=pause._control(self.p,self.states,self.target)
        report=pull.validate_seventeen_site_source_freeze_control(
            ctl,check_live_source_files=False)
        self.assertEqual(report["site_count"],17)
        self.assertFalse(report["writers_stopped"])
        self.assertFalse(report["cutover_allowed"])
        changed=copy.deepcopy(ctl)
        one=changed["sites"][0]["site_user"]
        changed["pending_system_cron"].append({
            "source_path":"/etc/cron.d/17-approved",
            "activated":False})
        changed["pending_user_cron"].append({
            "user":one,
            "source_path":f"/var/spool/cron/crontabs/{one}",
            "activated":False})
        changed["pending_pm2"].append({
            "user":one,
            "source_path":f"/home/{one}/.pm2/dump.pm2",
            "activated":False})
        report=pull.validate_seventeen_site_source_freeze_control(
            changed,check_live_source_files=False)
        self.assertEqual(report["system_cron_count"],1)
        self.assertEqual(report["user_cron_count"],1)
        self.assertEqual(report["pm2_count"],1)

    def test_source_rejects_path_escape_missing_type_and_duplicate_user(self):
        _mid,ctl,_=pause._control(self.p,self.states,self.target)
        owner=ctl["sites"][0]["site_user"]
        cases=[
            lambda d:d["pending_system_cron"].append({
                "source_path":"/etc/cron.d/../shadow","activated":False}),
            lambda d:d["pending_system_cron"].append({
                "source_path":"/etc/passwd","activated":False}),
            lambda d:d["pending_user_cron"].append({
                "user":owner,"source_path":"/etc/shadow","activated":False}),
            lambda d:d["pending_pm2"].append({
                "user":"wrong-owner",
                "source_path":"/home/wrong-owner/.pm2/dump.pm2",
                "activated":False}),
            lambda d:d["pending_pm2"].append({
                "user":owner,"source_path":"/home/"+owner+"/.pm2/../root",
                "activated":False}),
            lambda d:d["sites"].append(copy.deepcopy(d["sites"][0])),
            lambda d:d["sites"][1].update(site_user=owner),
        ]
        with mock.patch.object(legacy,"freeze_source_runtime") as freeze:
            for mutate in cases:
                changed=copy.deepcopy(ctl)
                mutate(changed)
                with self.assertRaises(pull.PullMigrationError):
                    pull.validate_seventeen_site_source_freeze_control(
                        changed,check_live_source_files=False)
            freeze.assert_not_called()

    def test_source_requires_fresh_original_cron_dump_files_before_shutdown(self):
        _mid,ctl,_=pause._control(self.p,self.states,self.target)
        ctl["pending_system_cron"]=[{
            "source_path":"/etc/cron.d/p07-test-source-absent-synthetic",
            "activated":False}]
        with mock.patch.object(legacy,"freeze_source_runtime") as freeze:
            with self.assertRaisesRegex(
                pull.PullMigrationError,"SOURCE_RUNTIME_PATH_CHANGED"
            ):
                pull.validate_seventeen_site_source_freeze_control(
                    ctl,check_live_source_files=True)
            freeze.assert_not_called()


    def original_source_receipt(self):
        mid,control,_=pause._control(self.p,self.states,self.target)
        recovery=Path(self.tmp.name)/"old-source-private"
        original= {
            "schema":legacy.SCHEMA, "migration_id":mid,
            "status":"SOURCE_FROZEN", "sites":control["sites"],
            "pending_system_cron":control["pending_system_cron"],
            "pending_user_cron":control["pending_user_cron"],
            "pending_pm2":control["pending_pm2"],
            "source_system_cron_saved":[],
            "source_user_cron_saved":[],
            "source_pm2_stopped":[],
            "source_nginx_frozen":True, "source_still_live":False,
            "source_delete_allowed":False,"dns_changed_by_p07":False,
        }
        legacy.atomic_private_json(recovery/mid/"state.json",original)
        return mid,recovery,original

    def test_old_vps_readback_uses_real_nginx_probe_not_cp2_claim(self):
        mid,recovery,original=self.original_source_receipt()
        with mock.patch.object(pull,"SOURCE_RECOVERY_ROOT",recovery), \
             mock.patch.object(legacy,"run_local",return_value=SimpleNamespace(
                 stdout="inactive\n",returncode=3)) as nginx:
            result=pull.source_frozen_readback(mid)
        self.assertEqual(result["site_count"],17)
        self.assertTrue(result["source_nginx_inactive_verified"])
        self.assertTrue(result["cron_pm2_journal_verified"])
        self.assertFalse(result["source_business_writers_all_fenced"])
        self.assertFalse(result["source_final_sql_data_parity"])
        self.assertFalse(result["cutover_allowed"])
        nginx.assert_called_once()

    def test_old_vps_readback_rejects_stale_nginx_and_receipt(self):
        mid,recovery,original=self.original_source_receipt()
        with mock.patch.object(pull,"SOURCE_RECOVERY_ROOT",recovery), \
             mock.patch.object(legacy,"run_local",return_value=SimpleNamespace(
                 stdout="active\n",returncode=0)):
            with self.assertRaisesRegex(
                pull.PullMigrationError,"NGINX_NOT_INACTIVE"):
                pull.source_frozen_readback(mid)
        original["status"]="SOURCE_RESTORED"
        legacy.atomic_private_json(recovery/mid/"state.json",original)
        with mock.patch.object(pull,"SOURCE_RECOVERY_ROOT",recovery), \
             mock.patch.object(legacy,"run_local") as nginx:
            with self.assertRaisesRegex(
                pull.PullMigrationError,"STATE_NOT_PROVEN"):
                pull.source_frozen_readback(mid)
            nginx.assert_not_called()

    def test_old_vps_readback_requires_saved_cron_matches_control(self):
        mid,recovery,original=self.original_source_receipt()
        user=original["sites"][0]["site_user"]
        original["pending_pm2"]=[{
            "user":user,"source_path":f"/home/{user}/.pm2/dump.pm2",
            "activated":False}]
        original["source_pm2_stopped"]=[{
            "user":"foreign-user",
            "source_path":f"/home/{user}/.pm2/dump.pm2",
            "stopped":True}]
        legacy.atomic_private_json(recovery/mid/"state.json",original)
        with mock.patch.object(pull,"SOURCE_RECOVERY_ROOT",recovery), \
             mock.patch.object(legacy,"run_local") as nginx:
            with self.assertRaisesRegex(
                pull.PullMigrationError,"RECOVERY_NOT_PROVEN"):
                pull.source_frozen_readback(mid)
            nginx.assert_not_called()


if __name__ == "__main__":
    unittest.main()
