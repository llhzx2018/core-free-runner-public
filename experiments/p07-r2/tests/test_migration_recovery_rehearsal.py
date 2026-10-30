"""Synthetic-only P07 private reconciliation rehearsal tests, no live DB."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import migration_recovery_rehearsal as engine

def cell(kind, value):
    return {"type": kind, "value": value}

def row(pk, text):
    return {"pk": [cell("INT", str(pk))],
            "cells": {"id": cell("INT", str(pk)), "payload": cell("TEXT", text)}}

def sample():
    source = [row(i, "identical") for i in range(1, 197)]
    target = deepcopy(source)
    for i in range(197, 202):
        source.append(row(i, "source-version"))
        target.append(row(i, "target-version"))
    source.extend([row(i, "source-only") for i in range(202, 205)])
    target.extend([row(i, "target-only") for i in range(205, 210)])
    expected = {"identical": 196, "source_only": 3, "target_only": 5, "different": 5}
    decisions = [
        {"pk": [cell("INT", str(i))], "decision": "USE_TARGET"}
        for i in range(197, 202)
    ]
    return source, target, expected, decisions

class RehearsalTest(unittest.TestCase):
    def run_rehearsal(self, source=None, target=None, expected=None, decisions=None, pk_columns=None):
        s, t, e, d = sample()
        return engine.rehearse(
            s if source is None else source,
            t if target is None else target,
            e if expected is None else expected,
            d if decisions is None else decisions,
            ["id"] if pk_columns is None else pk_columns,
        )

    def test_complete_204_206_rehearsal_and_actual_in_memory_reverse(self):
        source, target, expected, choices = sample()
        old_source, old_target = deepcopy(source), deepcopy(target)
        result = self.run_rehearsal(source, target, expected, choices)
        self.assertEqual(result["status"], "REHEARSAL_ONLY_BLOCKED_FOR_PRODUCTION")
        self.assertEqual(result["counts"], expected)
        self.assertEqual(result["recorded_conflict_decisions"], 5)
        self.assertTrue(result["target_rollback_rehearsed_in_memory"])
        self.assertEqual(source, old_source)
        self.assertEqual(target, old_target)
        for field in (
            "actual_source_restore_verified", "actual_target_restore_verified",
            "cross_engine_semantics_verified", "dynamic_sql_guards_verified",
            "snapshot_consistency_verified", "foreign_key_and_trigger_effects_verified",
            "data_writes_allowed", "migration_resume_allowed", "cutover_allowed",
        ):
            self.assertIs(result[field], False, field)

    def test_source_and_target_alternatives_are_all_reversible(self):
        for mode in ("USE_SOURCE", "USE_TARGET"):
            with self.subTest(mode=mode):
                s,t,e,d=sample()
                for item in d:
                    item["decision"] = mode
                self.assertTrue(self.run_rehearsal(s,t,e,d)["target_rollback_rehearsed_in_memory"])

    def test_reviewed_merge_keeps_keys_and_snapshot_schema(self):
        s,t,e,d=sample()
        d[0] = {"pk": [cell("INT", "197")], "decision": "MERGE_REVIEWED",
                "merged_cells": {"id": cell("INT", "197"), "payload": cell("TEXT", "both variants reviewed privately")}}
        result = self.run_rehearsal(s,t,e,d)
        self.assertTrue(result["target_rollback_rehearsed_in_memory"])

    def test_missing_duplicate_wrong_key_or_delete_choice_fails_closed(self):
        s,t,e,d=sample()
        malicious = [
            d[:-1],
            d + [deepcopy(d[0])],
            d[:-1] + [deepcopy(d[0])],
            d[:-1] + [{"pk": [cell("INT", "999")], "decision": "USE_SOURCE"}],
            d[:-1] + [{"pk": [cell("INT", "201")], "decision": "DELETE_TARGET"}],
            d[:-1] + [{"pk": [cell("INT", "201")], "decision": "USE_SOURCE",
                       "sql": "DROP DATABASE PRIVATE_SECRET"}],
            "DO_NOT_CHECK",
            [{"pk": [cell("INT", "197")], "decision": "MERGE_REVIEWED"}] + d[1:],
        ]
        for choices in malicious:
            with self.subTest(variant=str(type(choices))):
                result=self.run_rehearsal(s,t,e,choices)
                self.assertEqual(result["status"],"BLOCKED")
                self.assertIs(result["data_writes_allowed"],False)
                self.assertNotIn("PRIVATE_SECRET",json.dumps(result))

    def test_count_drift_fails_even_if_only_one_row(self):
        s,t,e,d=sample()
        s.append(row(210, "changed outside source snapshot"))
        result=self.run_rehearsal(s,t,e,d)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["reason"],"OBSERVED_COUNTS_DRIFT")

    def test_pk_cannot_be_spoofed_separately_from_row(self):
        s,t,e,d=sample()
        s[0]["cells"]["id"]=cell("INT","999999")
        self.assertEqual(self.run_rehearsal(s,t,e,d)["status"],"BLOCKED")

    def test_duplicate_pk_and_missing_column_fail_closed(self):
        for change in ("duplicate","missing","extra","type"):
            with self.subTest(change=change):
                s,t,e,d=sample()
                if change=="duplicate":
                    s.append(deepcopy(s[0]))
                elif change=="missing":
                    s[0]["cells"].pop("payload")
                elif change=="extra":
                    s[0]["cells"]["extra"]=cell("TEXT","unexpected")
                else:
                    s[0]["cells"]["payload"]=cell("BINARY","ff")
                self.assertEqual(self.run_rehearsal(s,t,e,d)["status"],"BLOCKED")

    def test_cross_engine_decimal_format_diff_is_not_auto_equal(self):
        s=[{"pk":[cell("INT","1")],"cells":{"id":cell("INT","1"),"n":cell("DECIMAL","1.0")}}]
        t=[{"pk":[cell("INT","1")],"cells":{"id":cell("INT","1"),"n":cell("DECIMAL","1.00")}}]
        e={"identical":0,"source_only":0,"target_only":0,"different":1}
        self.assertEqual(self.run_rehearsal(s,t,e,[])["reason"],"MISSING_OR_EXTRA_CONFLICT_DECISIONS")
        d=[{"pk":[cell("INT","1")],"decision":"USE_TARGET"}]
        self.assertEqual(self.run_rehearsal(s,t,e,d)["status"],"REHEARSAL_ONLY_BLOCKED_FOR_PRODUCTION")

    def test_null_binary_dates_are_strict_typed_and_not_reinterpreted(self):
        s=[{"pk":[cell("INT","1")],"cells":{"id":cell("INT","1"),"n":cell("NULL",None),
             "blob":cell("BINARY","00ff"),"when":cell("TIMESTAMP","2026-10-30 13:00:00")}}]
        t=deepcopy(s)
        e={"identical":1,"source_only":0,"target_only":0,"different":0}
        self.assertTrue(self.run_rehearsal(s,t,e,[])["target_rollback_rehearsed_in_memory"])
        t[0]["cells"]["when"]=cell("TIMESTAMP","2026-10-30 05:00:00")
        self.assertEqual(self.run_rehearsal(s,t,e,[])["reason"],"OBSERVED_COUNTS_DRIFT")

    def test_composite_pk_and_merging_pk_mutation_refused(self):
        k=lambda a,b:[cell("TEXT",a),cell("INT",str(b))]
        r=lambda a,b,x:{"pk":k(a,b),"cells":{"tenant":cell("TEXT",a),"id":cell("INT",str(b)),"payload":cell("TEXT",x)}}
        s=[r("tenant",1,"src")]
        t=[r("tenant",1,"tgt")]
        e={"identical":0,"source_only":0,"target_only":0,"different":1}
        d=[{"pk":k("tenant",1),"decision":"MERGE_REVIEWED",
            "merged_cells":r("tenant",2,"bad")["cells"]}]
        self.assertEqual(self.run_rehearsal(s,t,e,d,["tenant","id"])["status"],"BLOCKED")
        d[0]["merged_cells"]=r("tenant",1,"reviewed")["cells"]
        self.assertTrue(self.run_rehearsal(s,t,e,d,["tenant","id"])["target_rollback_rehearsed_in_memory"])

    def test_untrusted_backup_and_approval_claims_cannot_unlock_migration(self):
        s,t,e,d=sample()
        e.update({"restored_source":True,"restored_target":True,"owner_approved":True})
        result=self.run_rehearsal(s,t,e,d)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertFalse(result["migration_resume_allowed"])

    def test_raw_values_are_never_echoed(self):
        s,t,e,d=sample()
        s[200]["cells"]["payload"]=cell("TEXT","TOP_SECRET_SQL_PASSWORD")
        result=self.run_rehearsal(s,t,e,d)
        self.assertNotIn("TOP_SECRET_SQL_PASSWORD",json.dumps(result))
        self.assertFalse(result["data_writes_allowed"])

if __name__=="__main__":
    unittest.main()
