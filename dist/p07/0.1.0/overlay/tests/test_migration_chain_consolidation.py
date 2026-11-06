"""Read-only 17-site three-migration consolidation; no live DB or source."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_chain_consolidation as con
import migration_db_adoption as adopt
import server_migration_pull as pull
from tests.test_migration_chain_recovery import (
    CHILD, DOMAINS, PARENT, two_tasks,
)
from tests.test_migration_db_adoption import proof


TAIL = "pull-20261101T060000Z-11111111"


def full_three_tasks():
    parent, child = two_tasks()
    parent = adopt.stage_existing_verified_site(
        parent, "ilovem3u8.kewaro.com",
        proof("ilovem3u8.kewaro.com", PARENT, "db7"),
    )
    child = adopt.stage_existing_verified_site(
        child, "unzip.kewaro.com",
        proof("unzip.kewaro.com", CHILD, "db14"),
    )
    tail = copy.deepcopy(child)
    tail["migration_id"] = TAIL
    tail["sites"] = copy.deepcopy(parent["sites"][-2:])
    tail["status"] = "PREPARED"
    tail["partial_parent_migration_id"] = PARENT
    tail["cutover_prohibited"] = True
    for site in tail["sites"]:
        site["stage_status"] = "PULLED_STAGED"
        if site["mysql_databases"]:
            site["mysql_verification"] = [{
                "database": site["mysql_databases"][0],
                "phase": "prepare", "status": "PASS",
                "mode": "CANONICAL_SQL_EXACT",
            }]
    return parent, child, tail


class ThreeTaskConsolidationTests(unittest.TestCase):
    def test_17_sites_have_exact_one_owner_and_no_executable_status(self):
        tasks = full_three_tasks()
        before = copy.deepcopy(tasks)
        result = con.consolidate(*tasks)
        self.assertEqual(result["site_count"], 17)
        self.assertEqual(result["staged_site_count"], 17)
        self.assertEqual(result["status"],
                         "RECONCILED_PROVENANCE_ONLY_NOT_CUTOVER_READY")
        self.assertEqual([x["domain"] for x in result["sites"]], list(DOMAINS))
        self.assertEqual([x["origin_migration_id"] for x in result["sites"]],
                         [PARENT] * 8 + [CHILD] * 7 + [TAIL] * 2)
        self.assertEqual(len(result["site_contract_sha256"]), 64)
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["source_freeze_allowed"])
        self.assertFalse(result["db_reimport_allowed"])
        self.assertFalse(result["migration_state_writes_performed"])
        self.assertEqual(result["real_server_verification"], "NOT_PERFORMED")
        self.assertEqual(result["final_consistency_snapshot"], "NOT_VERIFIED")
        self.assertEqual(tasks, before)
        output = json.dumps(result)
        for name in ("origpass", "shadow_password", "db16", "/home/"):
            self.assertNotIn(name, output)
        # Does not have target-pull's executable schema/status.
        self.assertNotEqual(result["schema"], pull.SCHEMA)
        with mock.patch.object(pull, "load_state", return_value=result), \
             mock.patch.object(pull, "freeze_old_server") as freeze:
            with self.assertRaises(pull.PullMigrationError):
                pull.cutover_migration(TAIL, "CUTOVER_PULL:" + TAIL)
            freeze.assert_not_called()

    def test_all_three_original_db_owners_bound_by_provenance(self):
        import migration_final_db_shadow as shadow
        a, b, tail = full_three_tasks()
        mapping = con.original_database_provenance_map(a, b, tail)
        self.assertEqual(mapping, {
            "ilovem3u8.kewaro.com": PARENT,
            "unzip.kewaro.com": CHILD,
            "www3.m3u8.one": TAIL,
        })
        candidate = {
            "migration_id": "pull-20261101T080000Z-22222222",
            "sites": copy.deepcopy(a["sites"]),
            "original_db_migration_owners": mapping,
        }
        for row in candidate["sites"]:
            if row["mysql_databases"]:
                self.assertEqual(
                    shadow.original_database_owner(candidate, row),
                    mapping[row["domain"]],
                )
        before = copy.deepcopy((a, b, tail))
        bad = copy.deepcopy(tail)
        bad["source_server_identity"] = "sha256:untrusted"
        with self.assertRaises(con.ConsolidationBlocked):
            con.original_database_provenance_map(a, b, bad)
        self.assertEqual((a, b, tail), before)

    def test_locked_17_site_candidate_has_all_source_owners_but_no_cutover_power(self):
        a, b, tail = full_three_tasks()
        original = copy.deepcopy((a, b, tail))
        proposed = "pull-20261101T160000Z-cafe2026"
        expected = con.consolidate(a, b, tail)
        def local_proof(*args, **kwargs):
            self.assertEqual(kwargs["local_target_identity"], "sha256:cp2")
            return {
                "schema": "P07_17_SITE_LOCAL_OWNERSHIP_EVIDENCE_V1",
                "status": "LOCAL_MARKERS_AND_APP_BINDINGS_ONLY_NOT_CUTOVER_READY",
                "site_count": 17,
                "database_count": 3,
                "contract_sha256": expected["site_contract_sha256"],
                "local_target_identity_match": True,
                "all_migration_markers_owned": True,
                "all_database_app_bindings_checked": True,
                "cutover_allowed": False,
            }
        with mock.patch.object(
            con, "local_target_marker_proof", side_effect=local_proof
        ) as target_proof, mock.patch.object(
            pull, "save_state"
        ) as save, mock.patch.object(
            pull, "source_remote"
        ) as remote:
            result = con.build_locked_execution_candidate(
                a, b, tail, proposed_migration_id=proposed,
                local_target_identity="sha256:cp2",
            )
            target_proof.assert_called_once()
            save.assert_not_called()
            remote.assert_not_called()
        self.assertEqual(result["site_count"], 17)
        self.assertEqual(result["database_count"], 3)
        self.assertEqual(result["migration_id"], proposed)
        self.assertEqual(
            result["original_database_migration_owners"],
            {"ilovem3u8.kewaro.com": PARENT,
             "unzip.kewaro.com": CHILD,
             "www3.m3u8.one": TAIL},
        )
        self.assertEqual(
            [row["original_migration_id"] for row in result["sites"]],
            [PARENT] * 8 + [CHILD] * 7 + [TAIL] * 2,
        )
        self.assertEqual(len(result["original_asset_inventory_sha256"]), 3)
        self.assertNotEqual(result["schema"], pull.SCHEMA)
        self.assertNotEqual(result["status"], "PREPARED")
        self.assertTrue(result["cutover_prohibited"])
        self.assertFalse(result["cutover_allowed"])
        self.assertFalse(result["source_freeze_allowed"])
        self.assertFalse(result["state_writes_performed"])
        self.assertFalse(result["all_site_files_final_verified"])
        self.assertFalse(result["all_sqlite_snapshots_final_verified"])
        self.assertFalse(result["all_cron_pm2_jobs_final_verified"])
        self.assertEqual((a, b, tail), original)
        with mock.patch.object(
            pull, "load_state", return_value=result
        ), mock.patch.object(
            pull, "freeze_old_server"
        ) as freeze:
            with self.assertRaises(pull.PullMigrationError):
                pull.cutover_migration(proposed, f"CUTOVER_PULL:{proposed}")
            freeze.assert_not_called()

    def test_locked_candidate_refuses_bad_target_lineage_or_local_proof(self):
        a, b, tail = full_three_tasks()
        mid = "pull-20261101T160000Z-cafe2026"
        with mock.patch.object(con, "local_target_marker_proof") as proof:
            for candidate in (PARENT, CHILD, TAIL, "../unsafe", "", "unknown"):
                with self.subTest(id=candidate):
                    with self.assertRaises(con.ConsolidationBlocked):
                        con.build_locked_execution_candidate(
                            a, b, tail, proposed_migration_id=candidate,
                            local_target_identity="sha256:cp2",
                        )
            with self.assertRaisesRegex(
                con.ConsolidationBlocked,
                "CONSOLIDATED_EXECUTION_TARGET_IDENTITY_CHANGED",
            ):
                con.build_locked_execution_candidate(
                    a, b, tail, proposed_migration_id=mid,
                    local_target_identity="sha256:wrong",
                )
            proof.assert_not_called()
        expected = con.consolidate(a, b, tail)
        with mock.patch.object(
            con, "local_target_marker_proof",
            return_value={
                "schema": "P07_17_SITE_LOCAL_OWNERSHIP_EVIDENCE_V1",
                "status": "LOCAL_MARKERS_AND_APP_BINDINGS_ONLY_NOT_CUTOVER_READY",
                "site_count": 17, "database_count": 2,
                "contract_sha256": expected["site_contract_sha256"],
                "local_target_identity_match": True,
                "all_migration_markers_owned": True,
                "all_database_app_bindings_checked": True,
                "cutover_allowed": False,
            },
        ):
            with self.assertRaisesRegex(
                con.ConsolidationBlocked,
                "CONSOLIDATED_EXECUTION_DATABASE_COUNT_DRIFT",
            ):
                con.build_locked_execution_candidate(
                    a, b, tail, proposed_migration_id=mid,
                    local_target_identity="sha256:cp2",
                )

    def test_locked_candidate_cli_requires_live_target_marker_check_and_is_read_only(self):
        import contextlib
        import io
        a, b, tail = full_three_tasks()
        mid = "pull-20261101T160000Z-cafe2026"
        args = [
            "server-migrate", "chain-consolidation-proof",
            "--parent-migration-id", PARENT,
            "--child-migration-id", CHILD,
            "--tail-migration-id", TAIL,
            "--locked-candidate-id", mid,
        ]
        with mock.patch.object(sys, "argv", args), mock.patch.object(
            pull, "load_state", side_effect=[a, b, tail]
        ), mock.patch.object(
            con, "build_locked_execution_candidate"
        ) as build, mock.patch.object(
            pull, "target_identity"
        ) as identity, mock.patch.object(
            pull, "source_remote"
        ) as remote, mock.patch.object(
            pull, "save_state"
        ) as write, contextlib.redirect_stdout(io.StringIO()):
            self.assertNotEqual(pull.main(), 0)
            build.assert_not_called()
            identity.assert_not_called()
            remote.assert_not_called()
            write.assert_not_called()
        args.append("--verify-target-markers")
        with mock.patch.object(sys, "argv", args), mock.patch.object(
            pull, "load_state", side_effect=[a, b, tail]
        ) as read, mock.patch.object(
            pull, "target_identity", return_value="sha256:cp2"
        ), mock.patch.object(
            con, "build_locked_execution_candidate",
            return_value={
                "schema": con.EXECUTION_LOCKED_SCHEMA,
                "status": "LOCKED_AWAITING_FULL_ASSET_AND_FREEZE_RECOVERY_PROOF",
                "cutover_allowed": False, "site_count": 17,
            },
        ) as build, mock.patch.object(
            pull, "source_remote"
        ) as remote, mock.patch.object(
            pull, "save_state"
        ) as write, contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(pull.main(), 0)
            self.assertEqual(read.call_count, 3)
            build.assert_called_once()
            remote.assert_not_called()
            write.assert_not_called()
        output = json.loads(printed.getvalue())
        self.assertEqual(output["schema"], con.EXECUTION_LOCKED_SCHEMA)
        self.assertFalse(output["cutover_allowed"])
        self.assertEqual(build.call_args.kwargs["proposed_migration_id"], mid)

    def test_refuses_unadopted_parent_or_child_without_forging_checkpoint(self):
        a, b, tail = full_three_tasks()
        a["sites"][7]["database_adoption"]["status"] = "FORGED"
        with self.assertRaises(con.ConsolidationBlocked):
            con.consolidate(a, b, tail)
        a, b, tail = full_three_tasks()
        b["sites"][6]["database_adoption"]["db_reimported"] = True
        with self.assertRaises(con.ConsolidationBlocked):
            con.consolidate(a, b, tail)

    def test_read_only_cli_reads_exact_three_task_states_and_no_remote_write(self):
        import contextlib
        import io
        a, b, t = full_three_tasks()
        original = copy.deepcopy((a, b, t))
        args = [
            "server-migrate", "chain-consolidation-proof",
            "--parent-migration-id", PARENT,
            "--child-migration-id", CHILD,
            "--tail-migration-id", TAIL,
        ]
        with mock.patch.object(sys, "argv", args), \
             mock.patch.object(pull, "load_state", side_effect=[a, b, t]) as read, \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(pull, "source_remote") as remote, \
             mock.patch.object(pull, "source_export_database") as export, \
             mock.patch.object(pull, "sync_site_databases") as import_db, \
             mock.patch.object(pull, "freeze_old_server") as freeze, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            result = pull.main()
        self.assertEqual(result, 0)
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt["site_count"], 17)
        self.assertFalse(receipt["cutover_allowed"])
        self.assertEqual(read.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in read.call_args_list],
            [PARENT, CHILD, TAIL],
        )
        self.assertEqual((a, b, t), original)
        save.assert_not_called()
        remote.assert_not_called()
        export.assert_not_called()
        import_db.assert_not_called()
        freeze.assert_not_called()

    def test_wrong_tail_domains_order_or_parent_lineage_fails(self):
        for kind in ("wrong_parent", "not_cutover_prohibited",
                     "same_id", "wrong_domains", "reordered",
                     "wrong_original_contract"):
            with self.subTest(kind=kind):
                a, b, t = full_three_tasks()
                if kind == "wrong_parent":
                    t["partial_parent_migration_id"] = CHILD
                elif kind == "not_cutover_prohibited":
                    t["cutover_prohibited"] = False
                elif kind == "same_id":
                    t["migration_id"] = CHILD
                elif kind == "wrong_domains":
                    t["sites"][1]["domain"] = "wrong.example.test"
                elif kind == "reordered":
                    t["sites"] = list(reversed(t["sites"]))
                else:
                    t["sites"][1]["document_root"] = "/unrelated"
                with self.assertRaises(con.ConsolidationBlocked):
                    con.consolidate(a, b, t)

    def test_missing_db_prepare_evidence_or_forged_stage_is_rejected(self):
        for kind in ("db_proof", "stage", "duplicate_db", "bad_version"):
            with self.subTest(kind=kind):
                a, b, t = full_three_tasks()
                if kind == "db_proof":
                    t["sites"][-1]["mysql_verification"] = []
                elif kind == "stage":
                    t["sites"][0]["stage_status"] = "PENDING"
                elif kind == "duplicate_db":
                    t["sites"][-1]["mysql_databases"] = ["db7"]
                else:
                    t["sites"][-1]["mysql_verification"][0]["mode"] = "NOT_PROVEN"
                with self.assertRaises(con.ConsolidationBlocked):
                    con.consolidate(a, b, t)

    def test_local_target_marker_option_requires_matching_server_and_markers(self):
        import tempfile
        import server_migration as legacy
        parent, child, tail = full_three_tasks()
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(legacy, "STATE_ROOT", Path(directory)):
                with self.assertRaisesRegex(
                    con.ConsolidationBlocked,
                    "CONSOLIDATION_LOCAL_SERVER_IDENTITY_CHANGED",
                ):
                    con.local_target_marker_proof(
                        parent, child, tail,
                        local_target_identity="sha256:unknown",
                    )
                with self.assertRaisesRegex(
                    con.ConsolidationBlocked,
                    "CONSOLIDATION_TARGET_MARKER_ROOT_UNVERIFIED",
                ):
                    con.local_target_marker_proof(
                        parent, child, tail,
                        local_target_identity="sha256:cp2",
                    )

    def test_target_marker_cli_is_read_only(self):
        parent, child, tail = full_three_tasks()
        with mock.patch.object(
            pull, "load_state", side_effect=[parent, child, tail]
        ) as read, mock.patch.object(
            pull, "target_identity", return_value="sha256:cp2"
        ) as identify, mock.patch.object(
            pull.migration_chain_consolidation, "local_target_marker_proof",
            return_value={"status": "LOCAL_ONLY", "cutover_allowed": False},
        ) as verify, mock.patch.object(
            pull, "save_state"
        ) as save, mock.patch.object(
            pull, "source_remote"
        ) as remote:
            result = pull.consolidated_chain_scope(
                PARENT, CHILD, TAIL, verify_target_markers=True,
            )
        self.assertEqual(result["status"], "LOCAL_ONLY")
        self.assertEqual(read.call_count, 3)
        identify.assert_called_once_with()
        verify.assert_called_once()
        save.assert_not_called()
        remote.assert_not_called()

    def test_failed_or_partially_active_tail_is_rejected(self):
        for kind in ("status", "source_freeze", "runtime", "dns",
                     "overwrite", "source_drift", "target_drift"):
            with self.subTest(kind=kind):
                a, b, t = full_three_tasks()
                if kind == "status":
                    t["status"] = "PREPARE_FAILED"
                elif kind == "source_freeze":
                    t["source_runtime_frozen"] = True
                elif kind == "runtime":
                    t["target_runtime_activated"] = True
                elif kind == "dns":
                    t["dns_changed_by_p07"] = True
                elif kind == "overwrite":
                    t["existing_target_overwrite_allowed"] = True
                elif kind == "source_drift":
                    t["source_server_identity"] = "sha256:other"
                else:
                    t["target_server_identity"] = "sha256:other"
                with self.assertRaises(con.ConsolidationBlocked):
                    con.consolidate(a, b, t)

    def test_plain_and_duplicate_domain_site_user_contracts_denied(self):
        a, b, t = full_three_tasks()
        a["sites"][1]["site_user"] = a["sites"][0]["site_user"]
        with self.assertRaises(con.ConsolidationBlocked):
            con.consolidate(a, b, t)
        a, b, t = full_three_tasks()
        b["sites"][0]["site_root"] = "/other"
        with self.assertRaises(con.ConsolidationBlocked):
            con.consolidate(a, b, t)


if __name__ == "__main__":
    unittest.main()
