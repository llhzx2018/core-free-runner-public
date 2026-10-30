"""Source-only export readback must be scoped, fail-closed and state-preserving."""
from __future__ import annotations

from copy import deepcopy
import gzip
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import server_migration_pull as migration

SCHEMA = "CREATE TABLE \x60t\x60 (\x60id\x60 INT, \x60v\x60 TEXT);\n"
ONE = SCHEMA + "INSERT INTO \x60t\x60 VALUES (1,'a');\n"
TWO = SCHEMA + "INSERT INTO \x60t\x60 VALUES (1,'a'),(2,'b');\n"


class ScopedReadbackTests(unittest.TestCase):
    def state(self):
        return {
            "status": "PREPARE_FAILED",
            "migration_id": "pull-synthetic",
            "source": {"host": "example.invalid"},
            "source_runtime_path": "/private/helper",
            "sites": [{"domain": "site.example", "mysql_databases": ["private_db"]}],
        }

    def scenario(self, *, source_second=ONE, extra_fails=False, identical_target=False):
        state=self.state()
        original=deepcopy(state)
        counters={"pull": 0, "source":0, "target":0}

        def export_source(*args):
            counters["source"]+=1
            if extra_fails and counters["source"] == 2:
                raise migration.PullMigrationError("SYNTHETIC_SOURCE_EXPORT_FAILURE")

        def pull(*args):
            counters["pull"]+=1
            dst=Path(args[-1])
            body=ONE if counters["pull"]==1 else source_second
            with gzip.open(dst,"wt",encoding="utf-8") as h:h.write(body)

        def export_target(database, path, **_kwargs):
            counters["target"]+=1
            with gzip.open(path,"wt",encoding="utf-8") as h:
                h.write(ONE if identical_target else TWO)

        with (
            patch.object(migration,"load_state",return_value=state),
            patch.object(migration,"source_export_helper_matches_current",return_value=True),
            patch.object(migration,"source_export_database",side_effect=export_source),
            patch.object(migration,"pull_path",side_effect=pull),
            patch.object(migration.cloudpanel,"export_database",side_effect=export_target),
            patch.object(migration,"source_remote") as cleanup,
            patch.object(migration,"save_state") as save,
            patch.object(migration,"stage_source_runtime") as stage,
        ):
            result=migration.diagnose_sql_difference(
                "pull-synthetic", "site.example", expected_source_tables=1,
            )
            self.assertEqual(state,original)
            save.assert_not_called()
            stage.assert_not_called()
            self.assertEqual(cleanup.call_count,counters["source"])
        self.assertEqual(result["status"],"ADVISORY_DIAGNOSTIC_ONLY")
        self.assertFalse(result["database_writes_performed"])
        self.assertFalse(result["migration_state_modified"])
        self.assertFalse(result["dns_changed"])
        self.assertNotIn("private_db",str(result))
        self.assertNotIn("site.example",str(result))
        return result,counters

    def test_source_unchanged_twice_is_window_only_not_transactional_proof(self):
        data,counters=self.scenario()
        self.assertEqual(counters,{"source":2,"pull":2,"target":1})
        self.assertEqual(data["evidence"]["row_tuples"]["comparison"],"ROW_TUPLES_DIFFER")
        self.assertEqual(data["evidence"]["source_readback_stability"],{
            "comparison":"SAME_DUMP_TUPLES_IN_READBACK_WINDOW",
            "verification":"NOT_A_PASS_GATE",
        })

    def test_source_changed_between_exports_is_detected(self):
        data,counters=self.scenario(source_second=TWO)
        self.assertEqual(counters,{"source":2,"pull":2,"target":1})
        self.assertEqual(data["evidence"]["source_readback_stability"]["comparison"],
                         "SOURCE_TUPLES_CHANGED_BETWEEN_EXPORTS")

    def test_second_export_failure_keeps_first_diagnosis_and_cleanup(self):
        data,counters=self.scenario(extra_fails=True)
        self.assertEqual(counters,{"source":2,"pull":1,"target":1})
        self.assertEqual(data["evidence"]["source_readback_stability"]["comparison"],
                         "UNAVAILABLE")
        self.assertEqual(data["evidence"]["row_multiset"]["comparison"],
                         "ROW_MULTISET_DIFFER")

    def test_no_discrepancy_does_not_repeat_source_export(self):
        data,counters=self.scenario(identical_target=True)
        self.assertEqual(counters,{"source":1,"pull":1,"target":1})
        self.assertNotIn("source_readback_stability",data["evidence"])

    def test_wrong_state_denies_before_exports(self):
        st=self.state()
        st["status"]="COMPLETED"
        with (
            patch.object(migration,"load_state",return_value=st),
            patch.object(migration,"source_export_database") as x,
            patch.object(migration.cloudpanel,"export_database") as y,
        ):
            with self.assertRaises(migration.PullMigrationError):
                migration.diagnose_sql_difference("pull-synthetic","site.example")
            x.assert_not_called()
            y.assert_not_called()


if __name__=="__main__":
    unittest.main()
