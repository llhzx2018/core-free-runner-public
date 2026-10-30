"""Synthetic-only recovery-work-order tests; no credentials or customer data."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_conflict_recovery as module


def sample():
    # Counts copied from anonymized observational diagnostics, never SQL rows.
    return {
        "status": "ADVISORY_DIAGNOSTIC_ONLY",
        "database_writes_performed": False,
        "migration_state_modified": False,
        "secret_sql": "SENSITIVE_VALUE_SHOULD_NOT_LEAK",
        "evidence": {
            "verification": "NOT_A_PASS_GATE",
            "pk_conflicts": {
                "comparison": "PK_LITERAL_DIFFER",
                "verification": "NOT_A_PASS_GATE",
                "tables_examined": 42,
                "pk_tables_evaluable": 42,
                "pk_tables_unavailable": 0,
                "differing_pk_tables": 1,
                "differing_table_ordinals": [{
                    "table_ordinal": 4,
                    "identical_key_identical_literals": 196,
                    "same_key_changed_literals": 5,
                    "source_only_keys": 3,
                    "target_only_keys": 5,
                }],
                "source_only_keys": 3,
                "target_only_keys": 5,
                "same_key_changed_literals": 5,
                "row_dump": "SENSITIVE_VALUE_SHOULD_NOT_LEAK",
            },
            "row_tuples": {
                "tables_examined": 42, "differing_tables": 1,
                "differing_table_ordinals": [{
                    "table_ordinal": 4,
                    "source_rows": 204,
                    "target_rows": 206,
                }],
            },
            "row_multiset": {"tables_examined": 42},
            "dynamic_guard": {"recognized_unsafe": 3},
        },
    }


class ConflictRecoveryTests(unittest.TestCase):
    def test_real_counts_generate_non_executable_retain_both_work_order(self):
        source = sample()
        before = deepcopy(source)
        plan = module.draft(source)
        self.assertEqual(source, before)
        self.assertEqual(plan["status"], "BLOCKED_RECOVERY_AND_OPERATOR_DECISIONS")
        self.assertEqual(plan["conflict_tables"], 1)
        self.assertEqual(plan["conflicts"], [{
            "table_ordinal": 4, "source_only_keys": 3,
            "target_only_keys": 5, "same_key_changed_literals": 5,
            "default_handling": "RETAIN_BOTH_COPIES_REVIEW_REQUIRED",
            "delete_or_replace_allowed": False,
        }])
        self.assertFalse(plan["data_writes_allowed"])
        self.assertFalse(plan["migration_resume_allowed"])
        self.assertFalse(plan["cutover_allowed"])
        self.assertEqual(plan["dynamic_sql"], "UNPROVEN_GUARDED_SQL_REMAINS")
        self.assertEqual(plan["verification"], "NOT_A_PASS_GATE")
        self.assertIn("SOURCE_INDEPENDENT_RECOVERY_POINT_RESTORE_TEST", plan["requires"])
        self.assertIn("TARGET_INDEPENDENT_RECOVERY_POINT_RESTORE_TEST", plan["requires"])
        self.assertIn("EXPLICIT_OPERATOR_CONFLICT_POLICY", plan["requires"])
        self.assertNotIn("SENSITIVE_VALUE_SHOULD_NOT_LEAK", json.dumps(plan))

    def test_false_authority_or_non_advisory_source_fails_closed(self):
        for field, value in (
            ("status", "COMPLETED"),
            ("database_writes_performed", True),
            ("database_writes_performed", "false"),
            ("migration_state_modified", True),
        ):
            with self.subTest(field=field):
                item = sample()
                item[field] = value
                output = module.draft(item)
                self.assertEqual(output["status"], "BLOCKED_UNPROVEN_EVIDENCE")
                self.assertFalse(output["data_writes_allowed"])

    def test_bad_counts_fail_closed_not_autocorrected(self):
        for key, value in (
            ("source_only_keys", -1),
            ("target_only_keys", True),
            ("same_key_changed_literals", "5"),
            ("identical_key_identical_literals", 197),
        ):
            with self.subTest(field=key):
                item = sample()
                item["evidence"]["pk_conflicts"]["differing_table_ordinals"][0][key] = value
                output = module.draft(item)
                self.assertEqual(output["status"], "BLOCKED_UNPROVEN_EVIDENCE")
                self.assertEqual(output["reason"], "CROSS_EVIDENCE_INCOMPLETE_OR_INCONSISTENT")

    def test_count_mismatch_with_row_tuples_blocks(self):
        item = sample()
        item["evidence"]["row_tuples"]["differing_table_ordinals"][0]["source_rows"] = 203
        self.assertEqual(module.draft(item)["status"], "BLOCKED_UNPROVEN_EVIDENCE")

    def test_table_scope_and_coverage_incomplete_blocks(self):
        for path, value in (
            (("pk_conflicts", "pk_tables_evaluable"), 41),
            (("pk_conflicts", "pk_tables_unavailable"), 1),
            (("row_tuples", "tables_examined"), 43),
            (("row_multiset", "tables_examined"), 43),
        ):
            with self.subTest(field=path):
                item = sample()
                item["evidence"][path[0]][path[1]] = value
                self.assertEqual(module.draft(item)["status"], "BLOCKED_UNPROVEN_EVIDENCE")

    def test_untrusted_payload_is_never_echoed(self):
        item = sample()
        item["evidence"]["pk_conflicts"]["comparison"] = "SQL SECRET DO NOT ECHO"
        p = module.draft(item)
        self.assertEqual(p["status"], "BLOCKED_UNPROVEN_EVIDENCE")
        self.assertNotIn("SECRET", json.dumps(p))
        self.assertNotIn("SQL SECRET DO NOT ECHO", json.dumps(p))

    def test_empty_or_malformed_evidence_is_not_a_pass(self):
        for inp in ({}, [], None, {"evidence": {}}, {"evidence": {"pk_conflicts": {}}}):
            with self.subTest(example=str(type(inp))):
                result = module.draft(inp)
                self.assertFalse(result["data_writes_allowed"])
                self.assertEqual(result["status"], "BLOCKED_UNPROVEN_EVIDENCE")
                self.assertEqual(result["verification"], "NOT_A_PASS_GATE")

    def test_zero_unsafe_sql_does_not_grant_execution(self):
        item = sample()
        item["evidence"]["dynamic_guard"]["recognized_unsafe"] = 0
        result = module.draft(item)
        self.assertEqual(result["dynamic_sql"], "DYNAMIC_SQL_INDEPENDENT_GATE_REQUIRED")
        self.assertFalse(result["data_writes_allowed"])
        self.assertFalse(result["cutover_allowed"])

    def test_cannot_turn_user_supplied_backups_into_verified_restore(self):
        item = sample()
        item["backups_restored_verified"] = True
        item["operator_approved"] = True
        item["evidence"]["backup_gate"] = "PASS"
        out = module.draft(item)
        self.assertEqual(out["recovery_proof"], "NOT_ESTABLISHED")
        self.assertEqual(out["conflict_policy"], "UNSELECTED")
        self.assertEqual(out["consistent_snapshot"], "NOT_ESTABLISHED")
        self.assertFalse(out["data_writes_allowed"])


if __name__ == "__main__":
    unittest.main()
