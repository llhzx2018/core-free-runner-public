"""P07 imported-database adoption proof: precise ownership and SQL, no import."""
from __future__ import annotations
import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_db_adoption as rule
import server_migration_pull as pull
from tests.test_migration_chain_recovery import two_tasks, PARENT, CHILD

def proof(domain, mid, db="db", *, snapshot="b"*64, readback="b"*64, mode="CANONICAL_SQL_EXACT"):
    return {
        "domain":domain, "migration_id":mid, "database":db,
        "comparison_mode":mode, "source_readback_mode":"CANONICAL_SQL_EXACT",
        "source_dump_sha256":"a"*64, "target_dump_sha256":"c"*64,
        "source_readback_sha256":"d"*64,
        "source_snapshot_fingerprint":snapshot,
        "readback_snapshot_fingerprint":readback,
    }


class DBAdoptionTests(unittest.TestCase):
    def test_existing_app_database_mapping_must_still_match_original_marker(self):
        import app_config
        with tempfile.TemporaryDirectory() as d:
            site=Path(d)
            wp=site/"wp-config.php"
            for key in ("DB_NAME","DB_USER","DB_PASSWORD"):
                pass
            wp.write_text(
                "define('DB_NAME', 'targetdb');\n"
                "define('DB_USER', 'targetuser');\n"
                "define('DB_PASSWORD', 'secret-pw');\n",
                encoding="utf-8",
            )
            self.assertTrue(app_config.verify_rewritten_application_database_config(
                site,"targetdb","targetuser","secret-pw"))
            self.assertFalse(app_config.verify_rewritten_application_database_config(
                site,"targetdb","targetuser","other-pw"))
            wp.unlink()
            env=site/".env"
            env.write_text(
                "DB_DATABASE=targetdb\nDB_USERNAME=targetuser\n"
                "DB_PASSWORD='secret-pw'\n",
                encoding="utf-8",
            )
            self.assertTrue(app_config.verify_rewritten_application_database_config(
                site,"targetdb","targetuser","secret-pw"))
            env.write_text("DB_DATABASE=targetdb\nDB_USERNAME=targetuser\n",
                           encoding="utf-8")
            self.assertFalse(app_config.verify_rewritten_application_database_config(
                site,"targetdb","targetuser","secret-pw"))
            env.unlink()
            env.symlink_to(site/"does-not-exist")
            self.assertFalse(app_config.verify_rewritten_application_database_config(
                site,"targetdb","targetuser","secret-pw"))

    def test_wp_comment_or_duplicate_cannot_prove_db_binding(self):
        import app_config
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            wp = site / "wp-config.php"
            correct = (
                "define('DB_NAME', 'targetdb');\n"
                "define('DB_USER', 'targetuser');\n"
                "define('DB_PASSWORD', 'correct-pw');\n"
            )
            # A matching commented line cannot override an active wrong key.
            wp.write_text(
                "// define('DB_NAME', 'targetdb');\n"
                "define('DB_NAME', 'wrongdb');\n"
                "define('DB_USER', 'targetuser');\n"
                "define('DB_PASSWORD', 'correct-pw');\n",
                encoding="utf-8",
            )
            self.assertFalse(app_config.verify_rewritten_application_database_config(
                site, "targetdb", "targetuser", "correct-pw"))
            # The exact expected line may exist but an extra active definition
            # must not make the mapping unambiguous.
            wp.write_text(correct + "define('DB_NAME', 'anotherdb');\n",
                          encoding="utf-8")
            self.assertFalse(app_config.verify_rewritten_application_database_config(
                site, "targetdb", "targetuser", "correct-pw"))
            wp.write_text(correct, encoding="utf-8")
            self.assertTrue(app_config.verify_rewritten_application_database_config(
                site, "targetdb", "targetuser", "correct-pw"))

    def test_conflicting_dotenv_overrides_and_duplicate_keys_block_adoption(self):
        import app_config
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            base = site / ".env"
            other = site / ".env.production"
            good = (
                "DB_DATABASE=targetdb\nDB_USERNAME=targetuser\n"
                "DB_PASSWORD='correct-pw'\n"
            )
            base.write_text(good, encoding="utf-8")
            other.write_text("DB_DATABASE=wrongdb\nDB_USERNAME=targetuser\n"
                             "DB_PASSWORD='correct-pw'\n", encoding="utf-8")
            self.assertFalse(app_config.verify_rewritten_application_database_config(
                site, "targetdb", "targetuser", "correct-pw"))
            other.unlink()
            base.write_text(good + "DB_DATABASE=wrongdb\n", encoding="utf-8")
            self.assertFalse(app_config.verify_rewritten_application_database_config(
                site, "targetdb", "targetuser", "correct-pw"))
            base.write_text(good, encoding="utf-8")
            self.assertTrue(app_config.verify_rewritten_application_database_config(
                site, "targetdb", "targetuser", "correct-pw"))

    def test_ambiguous_wordpress_paths_cannot_fall_through_to_matching_dotenv(self):
        import app_config
        with tempfile.TemporaryDirectory() as d:
            site=Path(d)
            (site / ".env").write_text(
                "DB_DATABASE=targetdb\\nDB_USERNAME=targetuser\\nDB_PASSWORD=correct-pw\\n".replace("\\n", "\n"),
                encoding="utf-8",
            )
            (site / "wp-config.php").symlink_to(site / "outside-wp-config")
            self.assertFalse(app_config.verify_rewritten_application_database_config(
                site, "targetdb", "targetuser", "correct-pw"))
            (site / "wp-config.php").unlink()
            (site / "public").mkdir()
            good=("define('DB_NAME', 'targetdb');\\n"
                  "define('DB_USER', 'targetuser');\\n"
                  "define('DB_PASSWORD', 'correct-pw');\\n").replace("\\n", "\n")
            (site / "wp-config.php").write_text(good, encoding="utf-8")
            (site / "public" / "wp-config.php").write_text(
                good.replace("targetdb", "wrongdb"), encoding="utf-8")
            self.assertFalse(app_config.verify_rewritten_application_database_config(
                site, "targetdb", "targetuser", "correct-pw"))

    def test_chain_two_owned_imports_only_produce_nonexecuting_proof(self):
        parent,child=two_tasks()
        original=copy.deepcopy((parent,child))
        rows=[
            proof("ilovem3u8.kewaro.com",PARENT,"db7"),
            proof("unzip.kewaro.com",CHILD,"db14"),
        ]
        with mock.patch.object(pull,"load_state",side_effect=[parent,child]), \
             mock.patch.object(pull,"target_identity",return_value="sha256:cp2"), \
             mock.patch.object(pull,"_owned_pending_database_readback",side_effect=rows) as read, \
             mock.patch.object(pull,"save_state") as save, \
             mock.patch.object(pull,"sync_site_databases") as imp, \
             mock.patch.object(pull,"create_target_site") as create, \
             mock.patch.object(pull,"freeze_old_server") as freeze:
            result=pull.chain_adopt_database_proof(PARENT,CHILD)
        self.assertEqual(result["status"],"PREPARE_READBACK_MATCH_NOT_RESUMED")
        self.assertEqual(result["database_imports"],0)
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["site_stage_promoted"])
        self.assertFalse(result["source_freeze_allowed"])
        self.assertEqual(read.call_count,2)
        self.assertEqual(result["sites"][0]["domain"],"ilovem3u8.kewaro.com")
        self.assertEqual(result["sites"][1]["domain"],"unzip.kewaro.com")
        save.assert_not_called()
        imp.assert_not_called()
        create.assert_not_called()
        freeze.assert_not_called()
        self.assertEqual((parent,child),original)

    def test_mismatched_source_readback_rejects_proof_without_partial_state(self):
        p,c=two_tasks()
        rows=[
            proof("ilovem3u8.kewaro.com",PARENT,"db7"),
            proof("unzip.kewaro.com",CHILD,"db14",readback="e"*64),
        ]
        with mock.patch.object(pull,"load_state",side_effect=[p,c]), \
             mock.patch.object(pull,"target_identity",return_value="sha256:cp2"), \
             mock.patch.object(pull,"_owned_pending_database_readback",side_effect=rows), \
             mock.patch.object(pull,"save_state") as save:
            with self.assertRaisesRegex(pull.PullMigrationError,"ADOPT_SOURCE_EXPORT_CHANGED"):
                pull.chain_adopt_database_proof(PARENT,CHILD)
        save.assert_not_called()

    def test_drifted_target_or_source_scope_blocks_before_remote_work(self):
        for change in ("target","source","guard","db"):
            p,c=two_tasks()
            identity="sha256:cp2"
            if change=="target":identity="sha256:other"
            if change=="source":c["source_server_identity"]="other"
            if change=="guard":c["last_sql_guard_failure"]={"reason":"UNKNOWN"}
            if change=="db":c["sites"][6]["mysql_databases"]=[]
            with self.subTest(change=change), \
                 mock.patch.object(pull,"load_state",side_effect=[p,c]), \
                 mock.patch.object(pull,"target_identity",return_value=identity), \
                 mock.patch.object(pull,"_owned_pending_database_readback") as read:
                with self.assertRaises(pull.PullMigrationError):
                    pull.chain_adopt_database_proof(PARENT,CHILD)
            read.assert_not_called()

    def test_missing_and_foreign_private_markers_are_denied(self):
        with tempfile.TemporaryDirectory() as d:
            marker=Path(d)/"marker.json"
            with self.assertRaisesRegex(pull.PullMigrationError,"MARKER_MISSING"):
                pull._private_marker_readback(marker,{"domain":"example.org"})
            marker.write_text('{"domain":"another.org"}')
            marker.chmod(0o644)
            with self.assertRaisesRegex(pull.PullMigrationError,"MARKER_UNSAFE"):
                pull._private_marker_readback(marker,{"domain":"example.org"})
            marker.chmod(0o600)
            # CI runs as an unprivileged user; production migration markers
            # MUST be root-owned, so simulate only uid for this mismatch test.
            marker_stat = marker.lstat()
            owned = mock.Mock(st_uid=0, st_mode=marker_stat.st_mode)
            with mock.patch.object(Path, "lstat", return_value=owned):
                with self.assertRaisesRegex(pull.PullMigrationError,"OWNERSHIP_UNVERIFIED"):
                    pull._private_marker_readback(marker,{"domain":"example.org"})
            marker.unlink()
            marker.symlink_to(Path(d)/"invalid")
            with self.assertRaisesRegex(pull.PullMigrationError,"MARKER_UNSAFE"):
                pull._private_marker_readback(marker,{"domain":"example.org"})

    def test_receipt_rejects_all_unproven_modes_and_missing_digest(self):
        rows=[proof("ilovem3u8.kewaro.com",PARENT),
              proof("unzip.kewaro.com",CHILD)]
        for key,value in (
            ("comparison_mode","ADVISORY_ROW_PARITY"),
            ("source_readback_mode","UNKNOWN"),
            ("source_dump_sha256","not-a-digest"),
            ("source_snapshot_fingerprint","nope"),
        ):
            changed=copy.deepcopy(rows)
            changed[0][key]=value
            with self.subTest(key=key),self.assertRaises(rule.AdoptBlocked):
                rule.sealed_receipt(changed)
        with self.assertRaises(rule.AdoptBlocked):
            rule.sealed_receipt([rows[0],rows[0]])

    def test_confirmed_single_site_checkpoint_is_staged_but_not_cutover(self):
        for domain,mid,site_index in (("ilovem3u8.kewaro.com",PARENT,7),
                                       ("unzip.kewaro.com",CHILD,6)):
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as d:
                parent,child=two_tasks()
                state=parent if mid==PARENT else child
                original=copy.deepcopy(state)
                status_file=Path(d)/"state.json"
                status_file.write_text("original-private-state")
                def fresh(source,domains):
                    return {"source_server_identity":"sha256:source",
                            "sites":[copy.deepcopy(state["sites"][site_index])]}
                record=proof(domain,mid,state["sites"][site_index]["mysql_databases"][0])
                with mock.patch.object(pull,"state_dir",return_value=Path(d)), \
                     mock.patch.object(pull,"state_path",return_value=status_file), \
                     mock.patch.object(pull,"load_state",return_value=state), \
                     mock.patch.object(pull,"target_identity",return_value="sha256:cp2"), \
                     mock.patch.object(pull,"source_probe",side_effect=fresh) as scan, \
                     mock.patch.object(pull,"_owned_pending_database_readback",return_value=record) as verify, \
                     mock.patch.object(pull,"save_state") as save, \
                     mock.patch.object(pull,"sync_site_databases") as importer, \
                     mock.patch.object(pull,"freeze_old_server") as freeze:
                    result=pull.adopt_existing_guarded_site(
                        mid,domain,"ADOPT_EXISTING_DB:"+mid+":"+domain)
                self.assertEqual(result["status"],"FIRST_STAGE_ADOPTED_REQUIRES_CHAIN_RECOVERY")
                save.assert_called_once()
                modified=save.call_args.args[0]
                self.assertEqual(modified["status"],"PREPARE_FAILED")
                self.assertEqual(modified["last_sql_guard_failure"],original["last_sql_guard_failure"])
                self.assertEqual(modified["sites"][site_index]["stage_status"],"PULLED_STAGED")
                self.assertEqual(modified["sites"][site_index]["mysql_verification"][0]["status"],"PASS")
                self.assertTrue(modified["sites"][site_index]["database_adoption"]["cutover_allowed"] is False)
                self.assertEqual(state,original)
                self.assertEqual(verify.call_count,1)
                scan.assert_called_once()
                importer.assert_not_called()
                freeze.assert_not_called()

    def test_idempotent_repeat_does_not_read_source_or_update_status(self):
        p,_=two_tasks()
        original=copy.deepcopy(p)
        site=p["sites"][7]
        site["stage_status"]="PULLED_STAGED"
        site["database_adoption"]={
            "schema":"P07_EXISTING_DB_ADOPTION_CHECKPOINT_V1",
            "status":"SOURCE_TARGET_PREPARE_READBACK_PASS",
            "db_reimported":False,"cutover_allowed":False,
        }
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(pull,"state_dir",return_value=Path(d)), \
             mock.patch.object(pull,"load_state",return_value=p), \
             mock.patch.object(pull,"source_probe") as source, \
             mock.patch.object(pull,"save_state") as save, \
             mock.patch.object(pull,"_owned_pending_database_readback") as read:
            result=pull.adopt_existing_guarded_site(
                PARENT,"ilovem3u8.kewaro.com",
                "ADOPT_EXISTING_DB:"+PARENT+":ilovem3u8.kewaro.com")
        self.assertEqual(result["status"],"ALREADY_ADOPTED_FIRST_STAGE")
        source.assert_not_called()
        save.assert_not_called()
        read.assert_not_called()
        self.assertEqual(p["status"],original["status"])

    def test_owner_confirmation_is_required_before_any_file_lock(self):
        with mock.patch.object(pull,"load_state") as state, \
             mock.patch.object(pull,"state_dir") as directory:
            with self.assertRaisesRegex(pull.PullMigrationError,
                                         "OWNER_CONFIRMATION_REQUIRED"):
                pull.adopt_existing_guarded_site(
                    PARENT,"ilovem3u8.kewaro.com","WRONG")
        state.assert_not_called()
        directory.assert_not_called()

    def test_source_identity_drift_and_state_change_block_promotion(self):
        for scenario in ("source_drift","state_drift"):
            p,_=two_tasks()
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as d:
                state_path=Path(d)/"state.json"
                state_path.write_text("start")
                def source_probe(source,domains):
                    if scenario=="state_drift":
                        state_path.write_text("changed-during-export")
                    return {"source_server_identity":("other" if scenario=="source_drift" else "sha256:source"),
                            "sites":[copy.deepcopy(p["sites"][7])]}
                record=proof("ilovem3u8.kewaro.com",PARENT,"db7")
                with mock.patch.object(pull,"state_dir",return_value=Path(d)), \
                     mock.patch.object(pull,"state_path",return_value=state_path), \
                     mock.patch.object(pull,"load_state",return_value=p), \
                     mock.patch.object(pull,"target_identity",return_value="sha256:cp2"), \
                     mock.patch.object(pull,"source_probe",side_effect=source_probe), \
                     mock.patch.object(pull,"_owned_pending_database_readback",return_value=record) as read, \
                     mock.patch.object(pull,"save_state") as save:
                    if scenario=="state_drift":
                        # Our proof routine changes the source state after
                        # the readback pre-hash rather than during probe.
                        def racing_readback(*args):
                            state_path.write_text("changed-after-hash")
                            return record
                        read.side_effect=racing_readback
                    with self.assertRaises(pull.PullMigrationError):
                        pull.adopt_existing_guarded_site(
                            PARENT,"ilovem3u8.kewaro.com",
                            "ADOPT_EXISTING_DB:"+PARENT+":ilovem3u8.kewaro.com")
                save.assert_not_called()
                if scenario=="source_drift":
                    read.assert_not_called()

    def test_unsafe_site_status_and_denied_db_are_not_adopted(self):
        p,c=two_tasks()
        for bad in ("PREPARED","CUTOVER_RUNNING"):
            p["status"]=bad
            with self.assertRaises(rule.AdoptBlocked):
                rule.selected_db(p,"ilovem3u8.kewaro.com")
        p["status"]="PREPARE_FAILED"
        p["sites"][7]["stage_status"]="PULLED_STAGED"
        with self.assertRaises(rule.AdoptBlocked):
            rule.selected_db(p,"ilovem3u8.kewaro.com")


if __name__=="__main__":
    unittest.main()
