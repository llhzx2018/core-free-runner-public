"""R2: real MySQL 8.4 / MariaDB 11.8 *synthetic-only* transaction drill.

The databases are ephemeral GitHub Actions containers, never Owner VPS data.
Existing Source and Target data are not modified. Only separately restored
synthetic target candidate databases can receive INSERT / UPDATE statements.
A local commit/rollback test is NOT a production restore or migration approval.
"""
from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import migration_recovery_rehearsal as review
import test_dual_engine_restore_drill as base

PREFIX = base.PREFIX
EXPECTED = {"identical": 196, "source_only": 3, "target_only": 5, "different": 5}
VALID_MYSQL_ENGINES = {"mysql", "mariadb"}


def _typed(rows: dict[int, tuple[str, str]]) -> list[dict]:
    data = []
    for pk, (payload_hex, tag_hex) in sorted(rows.items()):
        data.append({
            "pk": [{"type": "INT", "value": str(pk)}],
            "cells": {
                "id": {"type": "INT", "value": str(pk)},
                "payload": {
                    "type": "TEXT", "value": bytes.fromhex(payload_hex).decode("utf8")
                },
                "tag": {
                    "type": "TEXT", "value": bytes.fromhex(tag_hex).decode("utf8")
                },
            },
        })
    return data


def _changes(source: dict[int, tuple[str, str]], target: dict[int, tuple[str, str]],
             *, keep_target_ids: frozenset[int]) -> str:
    """SQL constructed exclusively from *synthetic* fixed primary-key fixtures."""
    if set(source) != set(range(1, 205)) or set(target) != set(range(1, 202)) | set(range(205, 210)):
        raise RuntimeError("SYNTHETIC_DATASET_IDENTITY_UNPROVEN")
    if keep_target_ids - set(range(197, 202)):
        raise RuntimeError("INVALID_SYNTHETIC_CONFLICT_POLICY")
    sql = []
    for pk in range(202, 205):
        payload, tag = (bytes.fromhex(x).decode("utf8") for x in source[pk])
        sql.append(
            f"INSERT INTO vf_rows (id,payload,tag) VALUES ({pk},"
            f"{base._sql_quote(payload)},{base._sql_quote(tag)});"
        )
    for pk in range(197, 202):
        if pk in keep_target_ids:
            continue
        payload, tag = (bytes.fromhex(x).decode("utf8") for x in source[pk])
        sql.append(
            f"UPDATE vf_rows SET payload={base._sql_quote(payload)},"
            f"tag={base._sql_quote(tag)} WHERE id={pk};"
        )
    return "\n".join(sql) + "\n"


class MySQLMariaDBRealEngineR2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base._enabled()
        mysql_version = base._run("mysql", "SELECT VERSION();")
        maria_version = base._run("mariadb", "SELECT VERSION();")
        if not mysql_version.startswith("8.4.") or not maria_version.startswith("11.8."):
            raise RuntimeError("EXACT_SYNTHETIC_ENGINE_IMAGES_REQUIRED")

        cls.orig = {}
        cls.backups = {}
        for engine, side in (("mysql", "source"), ("mariadb", "target")):
            schema = PREFIX + "rtwo" + side
            base._create(engine, schema)
            base._run(engine, base._data_sql(side), database=schema)
            cls.orig[side] = base._rows(engine, schema)
            cls.backups[side] = base._dump(engine, schema)

        # Independently restore both backups before any candidate mutations.
        for engine, side in (("mysql", "source"), ("mariadb", "target")):
            recovered = PREFIX + "rtwo" + side + "_recovered"
            base._create(engine, recovered)
            blob = cls.backups[side]
            base._restore(engine, recovered, blob, hashlib.sha256(blob).hexdigest())
            if base._rows(engine, recovered) != cls.orig[side]:
                raise RuntimeError("INDEPENDENT_RESTORE_DATA_MISMATCH")

        # The target SQL dump is deliberately restored to BOTH engines
        # to establish separate writable scratch copies.
        for engine in ("mysql", "mariadb"):
            for mode in ("commit", "rollback"):
                scratch = PREFIX + "rtwo" + mode + "_" + engine
                base._create(engine, scratch)
                blob = cls.backups["target"]
                base._restore(engine, scratch, blob, hashlib.sha256(blob).hexdigest())
                if base._rows(engine, scratch) != cls.orig["target"]:
                    raise RuntimeError("RESTORED_CANDIDATE_INITIAL_STATE_UNPROVEN")

    @classmethod
    def tearDownClass(cls):
        # GitHub Actions test containers are disposed as a unit; no production
        # or external service is reachable by this intentionally restricted test.
        pass

    def test_two_restore_points_and_policy_only_block_production(self):
        source = _typed(self.orig["source"])
        target = _typed(self.orig["target"])
        selections = [
            {"pk": [{"type": "INT", "value": str(pk)}], "decision": "USE_TARGET"}
            for pk in range(197, 202)
        ]
        outcome = review.rehearse(source, target, EXPECTED, selections, ["id"])
        self.assertEqual(outcome["counts"], EXPECTED)
        self.assertEqual(outcome["status"], "REHEARSAL_ONLY_BLOCKED_FOR_PRODUCTION")
        self.assertTrue(outcome["target_rollback_rehearsed_in_memory"])
        self.assertFalse(outcome["actual_source_restore_verified"])
        self.assertFalse(outcome["actual_target_restore_verified"])
        self.assertFalse(outcome["dynamic_sql_guards_verified"])
        self.assertFalse(outcome["data_writes_allowed"])
        self.assertFalse(outcome["migration_resume_allowed"])

    def test_transaction_rollback_preserves_all_target_business_rows(self):
        sql = _changes(self.orig["source"], self.orig["target"],
                       keep_target_ids=frozenset({197, 198}))
        for engine in VALID_MYSQL_ENGINES:
            with self.subTest(engine=engine):
                scratch = PREFIX + "rtworollback_" + engine
                before = base._rows(engine, scratch)
                # No DDL in this transaction. The SELECT runs before ROLLBACK.
                inside = base._run(engine,
                                   "START TRANSACTION;\n" + sql +
                                   "SELECT COUNT(*) FROM vf_rows;\nROLLBACK;",
                                   database=scratch)
                self.assertEqual(inside.splitlines()[-1], "209")
                self.assertEqual(base._rows(engine, scratch), before)
                self.assertEqual(base._rows(engine, scratch), self.orig["target"])
                self.assertEqual(base._rows("mysql", PREFIX + "rtwosource"), self.orig["source"])
                self.assertEqual(base._rows("mariadb", PREFIX + "rtwotarget"), self.orig["target"])

    def test_committed_isolated_reconciliation_preserves_source_and_target(self):
        sql = _changes(self.orig["source"], self.orig["target"],
                       keep_target_ids=frozenset({197, 198}))
        for engine in VALID_MYSQL_ENGINES:
            with self.subTest(engine=engine):
                scratch = PREFIX + "rtwocommit_" + engine
                base._run(engine, "START TRANSACTION;\n" + sql + "COMMIT;", database=scratch)
                merged = base._rows(engine, scratch)
                self.assertEqual(len(merged), 209)
                self.assertEqual(set(merged), set(self.orig["source"]) | set(self.orig["target"]))
                for pk in range(205, 210):
                    self.assertEqual(merged[pk], self.orig["target"][pk])
                for pk in range(202, 205):
                    self.assertEqual(merged[pk], self.orig["source"][pk])
                for pk in (197, 198):
                    self.assertEqual(merged[pk], self.orig["target"][pk])
                for pk in (199, 200, 201):
                    self.assertEqual(merged[pk], self.orig["source"][pk])
                self.assertEqual(base._rows("mysql", PREFIX + "rtwosource"), self.orig["source"])
                self.assertEqual(base._rows("mariadb", PREFIX + "rtwotarget"), self.orig["target"])

    def test_failure_after_savepoint_can_revert_candidate_to_original(self):
        # A separate scratch candidate with target restored afresh. The failed
        # DML statement must be caught *inside the same client transaction*;
        # on any failure the whole candidate is discarded by disconnecting.
        for engine in VALID_MYSQL_ENGINES:
            with self.subTest(engine=engine):
                scratch = PREFIX + "rtwoinjected_" + engine
                base._create(engine, scratch)
                backup = self.backups["target"]
                base._restore(engine, scratch, backup, hashlib.sha256(backup).hexdigest())
                original = base._rows(engine, scratch)
                invalid = (
                    "START TRANSACTION;\n"
                    "INSERT INTO vf_rows VALUES (202,'new','test');\n"
                    "INSERT INTO vf_rows VALUES (205,'duplicate','bad');\n"
                )
                with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_MYSQL_OPERATION_FAILED"):
                    base._run(engine, invalid, database=scratch)
                self.assertEqual(base._rows(engine, scratch), original)

    def test_originals_unchanged_and_three_dynamic_sql_guards_remain_blocked(self):
        self.assertEqual(base._rows("mysql", PREFIX + "rtwosource"), self.orig["source"])
        self.assertEqual(base._rows("mariadb", PREFIX + "rtwotarget"), self.orig["target"])
        sample = _typed(self.orig["source"])
        # Three unknown guarded SQL statements cannot be approved by any
        # successful synthetic data exercise.
        selections = [
            {"pk": [{"type": "INT", "value": str(pk)}], "decision": "USE_SOURCE"}
            for pk in range(197, 202)
        ]
        result = review.rehearse(sample, _typed(self.orig["target"]),
                                 EXPECTED, selections, ["id"])
        self.assertFalse(result["dynamic_sql_guards_verified"])
        self.assertFalse(result["migration_resume_allowed"])
        self.assertFalse(result["cutover_allowed"])


if __name__ == "__main__":
    unittest.main()
