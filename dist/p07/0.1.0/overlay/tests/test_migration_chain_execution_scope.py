"""Synthetic proof for fail-closed cross-task execution ownership; no CP2 access."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_chain_execution_scope as execution
import migration_db_adoption as adoption
import server_migration_pull as pull
from tests.test_migration_chain_recovery import PARENT, CHILD, two_tasks
from tests.test_migration_db_adoption import proof


TAIL = "pull-20261102T005644Z-7178c7d5"


def three_partial_tasks():
    parent, child = two_tasks()
    tail = copy.deepcopy(parent)
    tail["migration_id"] = TAIL
    tail["partial_parent_migration_id"] = PARENT
    tail["cutover_prohibited"] = True
    tail["sites"] = copy.deepcopy(parent["sites"][-2:])
    tail["sites"][0]["stage_status"] = "PULLED_STAGED"
    tail["sites"][1]["stage_status"] = "PENDING"
    return parent, child, tail


def save_private(path: Path, payload: bytes):
    path.write_bytes(payload)
    path.chmod(0o600)


class ChainExecutionScopeTests(unittest.TestCase):
    def test_real_14_of_17_partial_ownership_mapped_once_without_mutations(self):
        original = three_partial_tasks()
        snapshot = copy.deepcopy(original)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(pull, "save_state") as save, mock.patch.object(
                pull, "source_remote"
            ) as remote, mock.patch.object(
                pull, "freeze_old_server"
            ) as freeze, mock.patch.object(
                pull, "sync_site_databases"
            ) as import_db:
                report = execution.scope(*original, root=Path(tmp),
                                         private_owner=os.getuid())
        self.assertEqual(report["schema"], execution.SCHEMA)
        self.assertEqual(report["site_count"], 17)
        self.assertEqual(report["staged_count"], 14)
        self.assertEqual(report["pending_count"], 3)
        self.assertEqual(report["source_task_count"], 3)
        self.assertEqual(report["final_sync_plan"]["step_count"], 21)
        self.assertEqual(report["final_sync_plan"]["site_count"], 17)
        self.assertEqual(len(report["final_sync_plan"]["pending_domains"]), 3)
        self.assertFalse(report["final_sync_plan"]["cutover_allowed"])
        self.assertEqual([x["owner_migration_id"] for x in report["sites"]],
                         [PARENT] * 8 + [CHILD] * 7 + [TAIL] * 2)
        self.assertEqual([x["domain"] for x in report["sites"]
                          if x["stage_status"] == "PENDING"],
                         ["ilovem3u8.kewaro.com",
                          "unzip.kewaro.com", "www3.m3u8.one"])
        self.assertEqual(report["www3_connection"]["status"], "ABSENT_NOT_PROVEN")
        self.assertIn("WWW3_STAGE_NOT_VERIFIED", report["blockers"])
        self.assertFalse(report["source_freeze_allowed"])
        self.assertFalse(report["cutover_allowed"])
        self.assertEqual(original, snapshot)
        for handler in (save, remote, freeze, import_db):
            handler.assert_not_called()
        text = json.dumps(report)
        for secret in ("origpass", "shadow_password", "/home/"):
            self.assertNotIn(secret, text)

    def _with_receipt(self, tasks, home: Path, state="CONNECTED_NOT_CUTOVER_READY",
                      live_candidate=True):
        parent, child, tail = tasks
        site_root = home / "docroot"
        site_root.mkdir()
        for task in tasks:
            for site in task["sites"]:
                if site["domain"] == "www3.m3u8.one":
                    site["site_root"] = str(site_root)
        original = b"<?php define('DB_NAME','db_original');"
        candidate = b"<?php define('DB_NAME','db_candidate');"
        config = site_root / "wp-config.php"
        save_private(config, candidate if live_candidate else original)
        folder = (home / tail["migration_id"] / "target-transactions"
                  / execution.CONNECTION_DIR)
        folder.mkdir(parents=True, mode=0o700)
        folder.chmod(0o700)
        save_private(folder / "original.php", original)
        save_private(folder / "candidate.php", candidate)
        save_private(folder / "rollback.sh", b"#!/bin/bash\nexit 0\n")
        s = config.stat()
        journal = {
            "schema": execution.CONNECTION_SCHEMA,
            "target_identity": tail["target_server_identity"],
            "config_path": str(config),
            "metadata": {"uid": s.st_uid, "gid": s.st_gid,
                         "mode": s.st_mode & 0o777},
            "site_owner_uid": s.st_uid,
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
            "status": state,
            "cutover_allowed": False,
            "database_writes": False,
            "migration_state_promoted": False,
        }
        save_private(folder / "journal.json", json.dumps(journal).encode())
        return folder, config

    def test_connected_www3_config_is_recognized_but_never_promoted(self):
        tasks = three_partial_tasks()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            folder, config = self._with_receipt(tasks, home)
            before = copy.deepcopy(tasks)
            report = execution.scope(*tasks, root=home, private_owner=os.getuid())
            self.assertEqual(tasks, before)
            self.assertEqual(report["staged_count"], 14)
            self.assertEqual(report["pending_count"], 3)
            self.assertEqual(report["www3_connection"]["status"],
                             "CONNECTED_NOT_CUTOVER_READY")
            self.assertEqual(report["www3_connection"]["config"],
                             "CANDIDATE_MATCH")
            self.assertTrue(report["www3_connection"]["rollback_bundle_present"])
            self.assertNotIn("WWW3_CANDIDATE_CONNECTION_UNVERIFIED", report["blockers"])
            self.assertIn("WWW3_STAGE_NOT_VERIFIED", report["blockers"])
            self.assertIn("FINAL_17_SITE_SYNC_AND_ROLLBACK_NOT_PROVEN",
                          report["blockers"])
            self.assertFalse(report["cutover_allowed"])
            self.assertEqual(config.read_bytes(),
                             (folder / "candidate.php").read_bytes())

    def test_journal_tamper_or_missing_rollback_fails_closed(self):
        for action in ("target", "status", "hash", "rollback", "symlink"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                tasks = three_partial_tasks()
                root = Path(tmp)
                folder, _ = self._with_receipt(tasks, root)
                journal = folder / "journal.json"
                raw = json.loads(journal.read_text())
                if action == "target":
                    raw["target_identity"] = "sha256:other"
                elif action == "status":
                    raw["status"] = "CUTOVER_PREP_READY"
                elif action == "hash":
                    raw["candidate_sha256"] = "0" * 64
                elif action == "rollback":
                    (folder / "rollback.sh").unlink()
                elif action == "symlink":
                    original = folder / "original.php"
                    original.unlink()
                    original.symlink_to(folder / "candidate.php")
                if action in ("target", "status", "hash"):
                    save_private(journal, json.dumps(raw).encode())
                with self.assertRaises(execution.RecoveryScopeBlocked):
                    execution.scope(*tasks, root=root,
                                    private_owner=os.getuid())

    def test_connected_status_and_live_config_must_agree(self):
        for status, candidate in [
            ("CONNECTED_NOT_CUTOVER_READY", False),
            ("ROLLED_BACK", True),
        ]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                tasks = three_partial_tasks()
                root = Path(tmp)
                self._with_receipt(tasks, root, state=status,
                                   live_candidate=candidate)
                with self.assertRaises(execution.RecoveryScopeBlocked):
                    execution.scope(*tasks, root=root,
                                    private_owner=os.getuid())

    def test_parent_child_or_tail_contract_forgery_is_rejected(self):
        for kind in ("parent", "child", "tail", "status"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                tasks = list(three_partial_tasks())
                if kind == "parent":
                    tasks[0]["sites"][7]["stage_status"] = "PULLED_STAGED"
                elif kind == "child":
                    tasks[1]["sites"][6]["stage_status"] = "PULLED_STAGED"
                elif kind == "tail":
                    tasks[2]["sites"][0]["site_user"] = "otheruser"
                else:
                    tasks[2]["status"] = "PREPARED"
                with self.assertRaises(execution.RecoveryScopeBlocked):
                    execution.scope(*tasks, root=Path(tmp),
                                    private_owner=os.getuid())

    def test_independently_adopted_two_db_sites_are_counted_once(self):
        a, b, t = three_partial_tasks()
        a = adoption.stage_existing_verified_site(
            a, "ilovem3u8.kewaro.com", proof("ilovem3u8.kewaro.com", PARENT, "db7"))
        b = adoption.stage_existing_verified_site(
            b, "unzip.kewaro.com", proof("unzip.kewaro.com", CHILD, "db14"))
        with tempfile.TemporaryDirectory() as tmp:
            out = execution.scope(a, b, t, root=Path(tmp),
                                  private_owner=os.getuid())
        self.assertEqual(out["staged_count"], 16)
        self.assertEqual(out["pending_count"], 1)
        self.assertNotIn("ILOVE_EXISTING_DB_ADOPTION_REQUIRED", out["blockers"])
        self.assertNotIn("UNZIP_EXISTING_DB_ADOPTION_REQUIRED", out["blockers"])
        self.assertFalse(out["cutover_allowed"])

    def test_cli_reuses_exact_three_task_state_and_never_contacts_source(self):
        tasks = three_partial_tasks()
        with tempfile.TemporaryDirectory() as tmp:
            argv = ["vfops", "chain-execution-scope",
                    "--parent-migration-id", PARENT,
                    "--child-migration-id", CHILD,
                    "--tail-migration-id", TAIL]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                pull, "load_state", side_effect=tasks
            ) as read, mock.patch.object(
                pull, "target_identity", return_value="sha256:cp2"
            ) as identity, mock.patch.object(
                pull.migration_chain_execution_scope, "scope",
                return_value={"schema": execution.SCHEMA,
                              "status": "OWNERSHIP_RESOLVED_EXECUTION_BLOCKED",
                              "site_count": 17, "cutover_allowed": False}
            ) as scope, mock.patch.object(
                pull, "save_state"
            ) as save, mock.patch.object(
                pull, "source_remote"
            ) as remote, mock.patch.object(
                pull, "freeze_old_server"
            ) as freeze, contextlib.redirect_stdout(io.StringIO()) as stdout:
                result = pull.main()
        self.assertEqual(result, 0)
        self.assertEqual(read.call_count, 3)
        scope.assert_called_once()
        identity.assert_called_once()
        save.assert_not_called()
        remote.assert_not_called()
        freeze.assert_not_called()
        self.assertEqual(json.loads(stdout.getvalue())["site_count"], 17)


    def test_cli_blocks_wrong_local_identity_before_reading_config(self):
        tasks = three_partial_tasks()
        argv = ["vfops", "chain-execution-scope",
                "--parent-migration-id", PARENT,
                "--child-migration-id", CHILD,
                "--tail-migration-id", TAIL]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(
            pull, "load_state", side_effect=tasks
        ), mock.patch.object(
            pull, "target_identity", return_value="sha256:wrong-cp2"
        ), mock.patch.object(
            pull.migration_chain_execution_scope, "scope"
        ) as scope, mock.patch.object(
            pull, "save_state"
        ) as save, mock.patch.object(
            pull, "freeze_old_server"
        ) as freeze, contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(pull.main(), 13)
        self.assertIn("CHAIN_EXECUTION_LOCAL_TARGET_IDENTITY_CHANGED",
                      stderr.getvalue())
        scope.assert_not_called()
        save.assert_not_called()
        freeze.assert_not_called()


class ThreeDatabaseReadinessTests(unittest.TestCase):
    def test_one_local_read_covers_exact_three_blockers_with_no_writes(self):
        tasks = three_partial_tasks()
        before = copy.deepcopy(tasks)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(pull, "source_remote") as remote, \
             mock.patch.object(pull, "sync_site_databases") as db_import, \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(pull, "freeze_old_server") as freeze:
            view = execution.original_database_readiness(
                *tasks, root=Path(tmp), private_owner=os.getuid())
            for handler in (remote, db_import, save, freeze):
                handler.assert_not_called()
        self.assertEqual(tasks, before)
        self.assertEqual(view["schema"],
                         "P07_CHAIN_ORIGINAL_DATABASE_READINESS_V1")
        self.assertEqual(view["staged_site_count"], 14)
        self.assertEqual(view["pending_site_count"], 3)
        self.assertEqual(view["database_count"], 3)
        self.assertEqual({r["domain"]: r["original_owner"]
                          for r in view["databases"]}, {
            "ilovem3u8.kewaro.com": tasks[0]["migration_id"],
            "unzip.kewaro.com": tasks[1]["migration_id"],
            "www3.m3u8.one": tasks[2]["migration_id"],
        })
        self.assertEqual(view["www3_connection_status"],
                         "ABSENT_NOT_PROVEN")
        self.assertTrue(all(r["source_target_row_parity"] == "NOT_PROVEN"
                            for r in view["databases"]))
        self.assertTrue(all(r["initial_stage"] ==
                            "PENDING_ORIGINAL_RECOVERY_PROOF"
                            for r in view["databases"]))
        for key in ("cutover_allowed", "source_freeze_allowed",
                    "target_runtime_activation_allowed",
                    "database_shadow_batch_execution_allowed",
                    "database_writes_performed",
                    "site_config_writes_performed",
                    "migration_state_writes_performed",
                    "source_server_contacted",
                    "www3_connection_or_import_retried"):
            self.assertIs(view[key], False)
        response = json.dumps(view)
        for secret in ("/home/", "db7", "db14", "db16",
                       "origpass", "shadow_password", "root@"):
            self.assertNotIn(secret, response)

    def test_readiness_reuses_connected_www3_journal_without_reconnect(self):
        tasks = three_partial_tasks()
        helper = ChainExecutionScopeTests()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            helper._with_receipt(tasks, home)
            with mock.patch.object(pull, "source_remote") as ssh, \
                 mock.patch.object(pull, "save_state") as save:
                result = execution.original_database_readiness(
                    *tasks, root=home, private_owner=os.getuid())
            ssh.assert_not_called()
            save.assert_not_called()
        self.assertEqual(result["www3_connection_status"],
                         "CONNECTED_NOT_CUTOVER_READY")
        self.assertFalse(result["source_target_final_parity_verified"])
        self.assertEqual(result["staged_site_count"], 14)
        self.assertEqual(result["databases"][-1]["final_sql_effects"],
                         "NOT_PROVEN")

    def test_valid_first_stage_adoption_does_not_claim_final_snapshot(self):
        tasks = list(three_partial_tasks())
        tasks[0] = adoption.stage_existing_verified_site(
            tasks[0], "ilovem3u8.kewaro.com",
            proof("ilovem3u8.kewaro.com", PARENT, "db7"))
        tasks[1] = adoption.stage_existing_verified_site(
            tasks[1], "unzip.kewaro.com",
            proof("unzip.kewaro.com", CHILD, "db14"))
        with tempfile.TemporaryDirectory() as tmp:
            result = execution.original_database_readiness(
                *tasks, root=Path(tmp), private_owner=os.getuid())
        self.assertEqual(result["staged_site_count"], 16)
        self.assertEqual(result["pending_site_count"], 1)
        for item in result["databases"][:2]:
            self.assertEqual(
                item["initial_stage"],
                "ADOPTION_CHECKPOINT_RECORDED_FINAL_PROOF_MISSING")
            self.assertEqual(
                item["next_unresolved_gate"],
                "FINAL_SOURCE_TARGET_PARITY_AND_RECOVERY_POINT")
            self.assertEqual(item["final_recovery_point"], "NOT_VERIFIED")
        self.assertFalse(result["cutover_allowed"])

    def test_www3_staged_flag_cannot_prove_sql_dynamic_or_row_parity(self):
        tasks = list(three_partial_tasks())
        tasks[2]["sites"][1]["stage_status"] = "PULLED_STAGED"
        with tempfile.TemporaryDirectory() as tmp:
            out = execution.original_database_readiness(
                *tasks, root=Path(tmp), private_owner=os.getuid())
        self.assertEqual(out["staged_site_count"], 15)
        self.assertEqual(out["pending_site_count"], 2)
        www3 = out["databases"][-1]
        self.assertEqual(www3["domain"], "www3.m3u8.one")
        self.assertEqual(www3["initial_stage"],
                         "STAGED_FLAG_ONLY_FINAL_DB_PROOF_UNVERIFIED")
        self.assertEqual(www3["final_sql_effects"], "NOT_PROVEN")
        self.assertEqual(www3["source_target_row_parity"], "NOT_PROVEN")
        self.assertFalse(out["cutover_allowed"])

    def test_readiness_rejects_forged_owner_and_cutover_state(self):
        for case in ("changed-db", "wrong-tail", "freeze", "fake-stage"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                tasks = list(three_partial_tasks())
                if case == "changed-db":
                    tasks[2]["sites"][1]["mysql_databases"] = ["other"]
                elif case == "wrong-tail":
                    tasks[2]["partial_parent_migration_id"] = "foreign"
                elif case == "freeze":
                    tasks[0]["source_runtime_frozen"] = True
                else:
                    tasks[0]["sites"][7]["stage_status"] = "PULLED_STAGED"
                with self.assertRaises(execution.RecoveryScopeBlocked):
                    execution.original_database_readiness(
                        *tasks, root=Path(tmp), private_owner=os.getuid())

    def test_chain_db_readiness_cli_is_read_only_and_checks_local_cp2(self):
        original = three_partial_tasks()
        argv = ["vfops", "chain-db-readiness",
                "--parent-migration-id", PARENT,
                "--child-migration-id", CHILD,
                "--tail-migration-id", TAIL]
        expected = {"schema": "P07_CHAIN_ORIGINAL_DATABASE_READINESS_V1",
                    "database_count": 3, "cutover_allowed": False}
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pull, "load_state",
                               side_effect=original) as load, \
             mock.patch.object(pull, "target_identity",
                               return_value="sha256:cp2") as target, \
             mock.patch.object(execution, "original_database_readiness",
                               return_value=expected) as triage, \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(pull, "source_remote") as ssh, \
             contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = pull.main()
        self.assertEqual(code, 0)
        self.assertEqual(load.call_count, 3)
        target.assert_called_once()
        triage.assert_called_once_with(*original, verify_original_markers=False)
        save.assert_not_called()
        ssh.assert_not_called()
        self.assertEqual(json.loads(stdout.getvalue()), expected)

    def test_cli_rejects_wrong_cp2_before_all_receipt_readback(self):
        original = three_partial_tasks()
        argv = ["vfops", "chain-db-readiness",
                "--parent-migration-id", PARENT,
                "--child-migration-id", CHILD,
                "--tail-migration-id", TAIL]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pull, "load_state", side_effect=original), \
             mock.patch.object(pull, "target_identity",
                               return_value="sha256:wrong"), \
             mock.patch.object(execution, "original_database_readiness") as check, \
             mock.patch.object(pull, "save_state") as save, \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(pull.main(), 13)
        self.assertIn("CHAIN_DB_LOCAL_TARGET_IDENTITY_CHANGED",
                      stderr.getvalue())
        check.assert_not_called()
        save.assert_not_called()

    def test_private_receipt_does_not_follow_raced_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "private.json"
            target = root / "untrusted.json"
            save_private(path, b'{"safe":true}')
            save_private(target, b'{"safe":false}')
            actual = execution.os.open
            def race(file, flags, mode=0o777):
                if Path(file) == path:
                    path.unlink()
                    path.symlink_to(target)
                return actual(file, flags, mode)
            with mock.patch.object(execution.os, "open", side_effect=race):
                with self.assertRaises(execution.RecoveryScopeBlocked):
                    execution._read_private(path, owner=os.getuid())
            self.assertTrue(path.is_symlink())

    def test_live_www3_config_raced_symlink_never_proves_candidate(self):
        tasks = three_partial_tasks()
        helper = ChainExecutionScopeTests()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _folder, config = helper._with_receipt(tasks, home)
            forged = home / "forged.php"
            save_private(forged, config.read_bytes())
            actual = execution.os.open
            def race(file, flags, mode=0o777):
                if Path(file) == config:
                    config.unlink()
                    config.symlink_to(forged)
                return actual(file, flags, mode)
            with mock.patch.object(execution.os, "open", side_effect=race):
                with self.assertRaises(execution.RecoveryScopeBlocked):
                    execution.connected_www3_proof(
                        tasks[2], root=home, private_owner=os.getuid())
            self.assertTrue(config.is_symlink())



class CP2ExistingOriginalMarkerReadbackTests(unittest.TestCase):
    """Preexisting transaction files, never created by the tested reader."""

    def _fixture(self, root: Path):
        tasks = list(three_partial_tasks())
        owners = {
            "ilovem3u8.kewaro.com": tasks[0]["migration_id"],
            "unzip.kewaro.com": tasks[1]["migration_id"],
            "www3.m3u8.one": tasks[2]["migration_id"],
        }
        paths = {}
        for domain, mid in owners.items():
            folder = root / domain
            folder.mkdir(mode=0o700)
            for state in tasks:
                for row in state["sites"]:
                    if row["domain"] == domain:
                        row["site_root"] = str(folder)
            db = next(row["mysql_databases"][0] for state in tasks
                      if state["migration_id"] == mid
                      for row in state["sites"] if row["domain"] == domain)
            username = "owner-" + domain.replace(".", "-")
            password = "private-secret-" + domain
            (folder / "wp-config.php").write_text(
                "define('DB_NAME', '" + db + "');\n"
                "define('DB_USER', '" + username + "');\n"
                "define('DB_PASSWORD', '" + password + "');\n")
            tx = root / mid / "target-transactions"
            tx.mkdir(parents=True, mode=0o700, exist_ok=True)
            tx.parent.chmod(0o700)
            tx.chmod(0o700)
            def put(name, data):
                path = tx / name
                save_private(path, json.dumps(data).encode())
                return path
            site_name = ("site-" + hashlib.sha256(
                domain.encode()).hexdigest()[:16] + ".json")
            db_name = ("db-" + hashlib.sha256(
                f"{domain}:{db}:1".encode()).hexdigest()[:16] + ".json")
            paths[domain] = {
                "site": put(site_name, {
                    "domain": domain, "created_by_migration": mid}),
                "db": put(db_name, {
                    "domain": domain, "database": db,
                    "created_by_migration": mid,
                    "username": username, "password": password}),
                "config": folder / "wp-config.php",
            }
        return tasks, paths

    def test_three_real_owner_markers_and_app_mappings_are_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks, paths = self._fixture(root)
            before = {
                key: tuple(p.read_bytes() for p in files.values())
                for key, files in paths.items()}
            with mock.patch.object(pull, "save_state") as save, \
                 mock.patch.object(pull, "source_remote") as ssh, \
                 mock.patch.object(pull, "sync_site_databases") as importer, \
                 mock.patch.object(execution.legacy, "target_db_marker") as write_root, \
                 mock.patch.object(execution.legacy, "target_tx_root") as mkdir:
                report = execution.original_database_readiness(
                    *tasks, root=root, private_owner=os.getuid(),
                    verify_original_markers=True)
            for callable_ in (save, ssh, importer, write_root, mkdir):
                callable_.assert_not_called()
            after = {key: tuple(p.read_bytes() for p in files.values())
                     for key, files in paths.items()}
            self.assertEqual(before, after)
        audit = report["local_original_marker_readback"]
        self.assertEqual(audit["original_owner_site_markers_verified"], 3)
        self.assertEqual(audit["original_owner_db_markers_verified"], 3)
        self.assertEqual(audit["application_original_binding_verified"], 3)
        self.assertEqual(len(audit["databases"]), 3)
        self.assertFalse(audit["source_target_row_parity_verified"])
        self.assertFalse(report["cutover_allowed"])
        rendered = json.dumps(report)
        self.assertNotIn("private-secret", rendered)
        self.assertNotIn("wp-config.php", rendered)
        self.assertNotIn("/home/", rendered)

    def test_absent_original_db_receipt_is_unknown_not_missing_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks, paths = self._fixture(root)
            paths["www3.m3u8.one"]["db"].unlink()
            result = execution.original_database_readiness(
                *tasks, root=root, private_owner=os.getuid(),
                verify_original_markers=True)
        audit = result["local_original_marker_readback"]
        self.assertEqual(audit["original_owner_db_markers_verified"], 2)
        self.assertEqual(audit["application_original_binding_verified"], 2)
        www3 = audit["databases"][-1]
        self.assertEqual(www3["original_database_marker"],
                         "ABSENT_UNVERIFIED")
        self.assertEqual(www3["application_binding"],
                         "NOT_CHECKED_MISSING_OWNER_MARKER")
        self.assertFalse(result["source_target_final_parity_verified"])

    def test_wrong_owner_db_marker_blocks_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks, paths = self._fixture(root)
            path = paths["ilovem3u8.kewaro.com"]["db"]
            data = json.loads(path.read_text())
            data["created_by_migration"] = "pull-another-task"
            save_private(path, json.dumps(data).encode())
            with self.assertRaisesRegex(
                    execution.RecoveryScopeBlocked,
                    "CHAIN_DB_ORIGINAL_MARKER_OWNER_CHANGED"):
                execution.original_database_readiness(
                    *tasks, root=root, private_owner=os.getuid(),
                    verify_original_markers=True)

    def test_symlinked_owner_db_receipt_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks, paths = self._fixture(root)
            path = paths["unzip.kewaro.com"]["db"]
            shadow = root / "untrusted.json"
            save_private(shadow, path.read_bytes())
            path.unlink()
            path.symlink_to(shadow)
            with self.assertRaises(execution.RecoveryScopeBlocked):
                execution.original_database_readiness(
                    *tasks, root=root, private_owner=os.getuid(),
                    verify_original_markers=True)

    def test_symlinked_original_owner_state_directory_is_refused(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks, _paths = self._fixture(root)
            mid = tasks[0]["migration_id"]
            original = root / mid
            moved = root / "moved-owner"
            original.rename(moved)
            original.symlink_to(moved, target_is_directory=True)
            with self.assertRaisesRegex(
                    execution.RecoveryScopeBlocked,
                    "CHAIN_DB_ORIGINAL_OWNER_DIRECTORY_UNSAFE"):
                execution.original_database_readiness(
                    *tasks, root=root, private_owner=os.getuid(),
                    verify_original_markers=True)

    def test_changed_site_credentials_do_not_relabel_marker_as_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks, paths = self._fixture(root)
            config = paths["ilovem3u8.kewaro.com"]["config"]
            config.write_text(config.read_text().replace(
                "private-secret-ilovem3u8.kewaro.com",
                "modified-target-password"))
            audit = execution.original_database_readiness(
                *tasks, root=root, private_owner=os.getuid(),
                verify_original_markers=True)["local_original_marker_readback"]
        self.assertEqual(audit["original_owner_db_markers_verified"], 3)
        self.assertEqual(audit["application_original_binding_verified"], 2)
        self.assertEqual(audit["databases"][0]["application_binding"],
                         "UNVERIFIED_OR_CHANGED")
        self.assertFalse(audit["cutover_allowed"])

    def test_opt_in_cli_routes_explicit_marker_probe_without_source_or_writes(self):
        original = three_partial_tasks()
        argv = ["vfops", "chain-db-readiness",
                "--parent-migration-id", PARENT,
                "--child-migration-id", CHILD,
                "--tail-migration-id", TAIL,
                "--verify-original-markers"]
        response = {"schema": "P07_CHAIN_ORIGINAL_DATABASE_READINESS_V1",
                    "database_count": 3, "cutover_allowed": False}
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pull, "load_state",
                               side_effect=original) as load, \
             mock.patch.object(pull, "target_identity",
                               return_value="sha256:cp2"), \
             mock.patch.object(execution, "original_database_readiness",
                               return_value=response) as audit, \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(pull, "source_remote") as ssh, \
             contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(pull.main(), 0)
        self.assertEqual(load.call_count, 3)
        audit.assert_called_once_with(
            *original, verify_original_markers=True)
        for op in (save, ssh):
            op.assert_not_called()
        self.assertEqual(json.loads(stdout.getvalue()), response)


if __name__ == "__main__":
    unittest.main()
