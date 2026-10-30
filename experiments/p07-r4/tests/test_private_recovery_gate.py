"""Synthetic-only verification of P07 private backup recovery gate.

No production database, SSH, real SQL, CloudPanel service, or restore is used.
"""
from __future__ import annotations

import contextlib
import copy
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import private_recovery_gate as gate
import server_migration_pull as pull

DDL = ("CREATE TABLE `one_table` (`id` INT NOT NULL, `payload` TEXT, "
       "PRIMARY KEY (`id`)) ENGINE=InnoDB;\n")
SOURCE = DDL + "INSERT INTO `one_table` VALUES (1,'same'),(2,'source_only'),(3,'source_changed');\n"
TARGET = DDL + "INSERT INTO `one_table` VALUES (1,'same'),(3,'target_changed'),(4,'target_only');\n"
SITE = "my-site.example.test"


def package(root: Path, backup_id: str, dump: str, *, rel="mysql/export.sql.gz", site=SITE) -> Path:
    root.mkdir()
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(dump)
    (root / "manifest.json").write_text(json.dumps({
        "schema": gate.package_core.PACKAGE_SCHEMA,
        "backup_id": backup_id, "backup_kind": "pre_migration",
        "site": {"domain": site},
        "contents": {"mysql": [{"database": backup_id, "file": rel}]},
    }), encoding="utf-8")
    return root


class PrivateRecoveryGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = package(self.root / "source", "backup-source", SOURCE)
        self.target = package(self.root / "target", "backup-target", TARGET)
        verifier = mock.patch.object(gate.package_core, "verify_package_stable",
                                     return_value={"status": "PASS"})
        verifier.start()
        self.addCleanup(verifier.stop)

    def test_two_verified_backups_are_not_restore_proof(self):
        before = [(p.stat().st_size, p.stat().st_mtime_ns)
                  for p in self.root.rglob("*") if p.is_file()]
        evidence = gate.evaluate(self.source, self.target, SITE)
        after = [(p.stat().st_size, p.stat().st_mtime_ns)
                 for p in self.root.rglob("*") if p.is_file()]
        self.assertEqual(before, after)
        self.assertEqual(evidence["status"],
                         "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY")
        self.assertEqual(evidence["source_backup_integrity"], "PASS")
        self.assertEqual(evidence["target_backup_integrity"], "PASS")
        self.assertEqual(evidence["source_tables"], 1)
        self.assertEqual(evidence["target_tables"], 1)
        self.assertEqual(evidence["primary_key_summary"]["source_only_keys"], 1)
        self.assertEqual(evidence["primary_key_summary"]["target_only_keys"], 1)
        self.assertEqual(evidence["primary_key_summary"]["same_key_changed_literals"], 1)
        for key in ("actual_source_restore_verified", "actual_target_restore_verified",
                    "data_writes_performed", "migration_state_modified",
                    "migration_resume_allowed", "cutover_allowed", "dynamic_sql_approved"):
            self.assertFalse(evidence[key])
        serialized = json.dumps(evidence)
        for private in ("source_changed", "target_changed",
                        str(self.root), "one_table", "backup-source", SITE):
            self.assertNotIn(private, serialized)

    def test_identical_path_is_not_two_recovery_points(self):
        e = gate.evaluate(self.source, self.source, SITE)
        self.assertEqual(e["reason"], "TWO_INDEPENDENT_BACKUP_POINTS_REQUIRED")
        self.assertFalse(e["cutover_allowed"])

    def test_distinct_folders_with_same_backup_id_are_rejected(self):
        item = json.loads((self.target / "manifest.json").read_text())
        item["backup_id"] = "backup-source"
        (self.target / "manifest.json").write_text(json.dumps(item))
        e = gate.evaluate(self.source, self.target, SITE)
        self.assertEqual(e["reason"], "TWO_DISTINCT_BACKUP_IDENTITIES_REQUIRED")

    def test_input_site_identity_must_match_both(self):
        e = gate.evaluate(self.source, self.target, "other.example.test")
        self.assertEqual(e["reason"], "PRIVATE_PACKAGE_IDENTITY_NOT_PROVEN")

    def test_failed_checksum_gate_stops_before_reading_sql(self):
        with mock.patch.object(gate.package_core, "verify_package_stable",
                               return_value={"status": "FAIL"}), \
             mock.patch.object(gate.sql_diff_evidence, "diagnostic") as diff:
            e = gate.evaluate(self.source, self.target, SITE)
        self.assertEqual(e["reason"], "PRIVATE_BACKUP_INTEGRITY_NOT_PASS")
        diff.assert_not_called()

    def test_sql_path_traversal_refused(self):
        manifest = json.loads((self.source / "manifest.json").read_text())
        manifest["contents"]["mysql"][0]["file"] = "mysql/../../root/private.sql.gz"
        (self.source / "manifest.json").write_text(json.dumps(manifest))
        e = gate.evaluate(self.source, self.target, SITE)
        self.assertEqual(e["reason"], "PRIVATE_SQL_PATH_UNSAFE")

    def test_sql_symlink_refused(self):
        sql = self.source / "mysql" / "export.sql.gz"
        alt = self.source / "mysql" / "alternate.sql.gz"
        sql.rename(alt)
        sql.symlink_to(alt)
        e = gate.evaluate(self.source, self.target, SITE)
        self.assertEqual(e["reason"], "PRIVATE_SQL_SYMLINK_REFUSED")

    def test_missing_sql_and_invalid_json_fail_without_private_values(self):
        (self.source / "mysql" / "export.sql.gz").unlink()
        e = gate.evaluate(self.source, self.target, SITE)
        self.assertEqual(e["status"], "BLOCKED_UNVERIFIED_INPUT")
        self.assertFalse(e["migration_resume_allowed"])
        (self.source / "manifest.json").write_text("PRIVATE_VALUE_SECRET not JSON")
        e = gate.evaluate(self.source, self.target, SITE)
        self.assertNotIn("PRIVATE_VALUE_SECRET", json.dumps(e))

    def test_advisory_injection_cannot_leak_sql_or_private_names(self):
        with mock.patch.object(gate.sql_diff_evidence, "diagnostic") as run:
            run.return_value = {"verification": "NOT_A_PASS_GATE",
                                "pk_conflicts": {
                                    "comparison": "PK_LITERAL_DIFFER",
                                    "tables_examined": 1,
                                    "pk_tables_evaluable": 1,
                                    "pk_tables_unavailable": 0,
                                    "source_only_keys": 1,
                                    "target_only_keys": 0,
                                    "same_key_changed_literals": 1,
                                    "identical_key_identical_literals": 0,
                                    "differing_table_ordinals": [{
                                        "table_ordinal": 1, "source_only_keys": 1,
                                        "target_only_keys": 0,
                                        "same_key_changed_literals": 1,
                                        "identical_key_identical_literals": 0,
                                        "private_sql": "PRIVATE_VALUE_SECRET"}],
                                },
                                "schema_difference": {"source_tables": 1,
                                                      "target_tables": 1,
                                                      "common_tables": 1,
                                                      "mismatched_tables": 0},
                                "dynamic_guard": {
                                    "recognized_unsafe": 3,
                                    "unsafe_branch_reasons": {
                                        "CONTROL_OR_MULTISTATEMENT": 1,
                                        "GLOBAL_OR_PERSIST": 0,
                                        "SIDE_EFFECT_OR_CONTROL_KEYWORD": 2,
                                        "SESSION_GRAMMAR_UNPROVEN": 0,
                                        "READ_GRAMMAR_UNPROVEN": 0,
                                        "UNKNOWN_GRAMMAR": 0,
                                        "PRIVATE_VALUE_SECRET": "SQL"}},
                                "row_tuples": {"tables_examined": 1,
                                               "differing_tables": 0,
                                               "differing_table_ordinals": []},
                                "row_multiset": {"tables_examined": 1}}
            e = gate.evaluate(self.source, self.target, SITE)
        self.assertNotIn("PRIVATE_VALUE_SECRET", json.dumps(e))
        self.assertEqual(e["dynamic_unsafe"], 3)
        self.assertEqual(e["conflict_table_ordinals"][0]["table_ordinal"], 1)
        self.assertFalse(e["cutover_allowed"])

    def test_cli_reports_block_not_pass(self):
        args = ["--source-package", str(self.source),
                "--target-package", str(self.target), "--site", SITE]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = gate.main(args)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(output.getvalue())["verification"], "NOT_A_PASS_GATE")

    def test_migration_entry_uses_offline_gate_without_source_calls(self):
        data = {"schema": gate.SCHEMA, "status": "BLOCKED_UNVERIFIED_INPUT",
                "cutover_allowed": False}
        with mock.patch.object(pull.private_recovery_gate, "evaluate",
                               return_value=data) as evaluate, \
             mock.patch.object(pull, "source_probe") as probe, \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(sys, "argv", [
                 "server_migration_pull.py", "recovery-evidence",
                 "--source-package", str(self.source),
                 "--target-package", str(self.target), "--site", SITE]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                rc = pull.main()
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(output.getvalue()), data)
        evaluate.assert_called_once()
        probe.assert_not_called()
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
