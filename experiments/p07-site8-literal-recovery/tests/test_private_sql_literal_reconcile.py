"""Synthetic private SQL backup fixtures. No real site data or server access."""
from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import private_sql_literal_reconcile as module
import private_conflict_preservation as original
import private_recovery_gate as gate

SITE = "synthetic.test"
DDL = "CREATE TABLE `{table}` (`id` INT NOT NULL, `payload` TEXT, PRIMARY KEY (`id`)) ENGINE=InnoDB;\n"


def pack(root, label, dump):
    root.mkdir()
    sql = root / "mysql" / "backup.sql.gz"
    sql.parent.mkdir()
    with gzip.open(sql, "wt", encoding="utf-8") as out:
        out.write(dump)
    (root / "manifest.json").write_text(json.dumps({
        "schema": gate.package_core.PACKAGE_SCHEMA,
        "backup_id": label,
        "backup_kind": "pre_migration",
        "site": {"domain": SITE},
        "contents": {"mysql": [{"database": "synthetic", "file": "mysql/backup.sql.gz"}]},
    }), encoding="utf-8")
    return root, sql


def dump(source=True, *, replace=False, unsafe=False, mutate=False):
    out = "".join(DDL.format(table=t) for t in ("a", "b", "c", "delta"))
    out += "INSERT INTO `a` VALUES (1,'a');\n"
    out += "INSERT INTO `b` VALUES (1,'b');\n"
    out += "INSERT INTO `c` VALUES (1,'c');\n"
    kind = "REPLACE" if replace else "INSERT"
    changed = "first" if source else "second"
    unique = 4 if source else 5
    out += (f"{kind} INTO `delta` VALUES "
            f"(1,'same'),(2,'same'),(3,'{changed}'),({unique},'unique');\n")
    if mutate:
        out += "UPDATE `delta` SET `payload`='evil';\n"
    if unsafe:
        out += "/*!50003 SET @cmd=IF(@flag,'DROP TABLE delta','SELECT 1') */;\n"
    return out


class PrivateLiteralTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        os.chmod(self.root, 0o700)
        self.src, self.sql_a = pack(self.root / "source", "source-backup", dump(True, unsafe=True))
        self.tgt, self.sql_b = pack(self.root / "target", "target-backup", dump(False))
        patch = mock.patch.object(gate.package_core, "verify_package_stable",
                                  return_value={"status": "PASS"})
        patch.start()
        self.addCleanup(patch.stop)

    def test_verified_packages_produce_real_literal_dual_originals_and_hash_binding(self):
        bundle, a, b, expected, keys, origin = module.extract_verified(
            self.src, self.tgt, SITE, 4)
        self.assertEqual(expected, {"identical": 2, "source_only": 1,
                                    "target_only": 1, "different": 1})
        self.assertEqual(keys, ["id"])
        self.assertEqual(len(bundle["conflicting_dual_originals"]), 1)
        item = bundle["conflicting_dual_originals"][0]
        self.assertEqual(item["resolution"], "UNRESOLVED_KEEP_BOTH")
        self.assertEqual(item["source_original"]["cells"]["payload"]["value"], "'first'")
        self.assertEqual(item["target_original"]["cells"]["payload"]["value"], "'second'")
        self.assertEqual(origin["source_sql_sha256"], module._digest(self.sql_a))
        self.assertEqual(bundle["verified_backup_sql_identity_digests"], origin)
        self.assertTrue(original.compare_to_inputs(bundle, a, b, expected, keys, origin))
        self.assertFalse(bundle["actual_original_sql_restores_verified"])
        self.assertFalse(bundle["migration_resume_allowed"])

    def test_only_counts_and_fixed_labels_leave_command(self):
        report = module.evaluate(self.src, self.tgt, SITE, 4)
        self.assertEqual(report["status"], "PRIVATE_SQL_LITERALS_CAPTURED_NOT_RESTORED")
        self.assertEqual(report["private_artifact"], "NOT_WRITTEN")
        self.assertEqual(report["unresolved_conflicts"], 1)
        self.assertFalse(report["original_sql_restored"])
        self.assertFalse(report["migration_resume_allowed"])
        body = json.dumps(report)
        for secret in ("'first'", "'second'", str(self.src), "synthetic.test", "delta"):
            self.assertNotIn(secret, body)

    def test_private_original_artifact_requires_explicit_confirmation(self):
        out = self.root / "private"
        blocked = module.evaluate(self.src, self.tgt, SITE, 4, private_output=out)
        self.assertEqual(blocked["reason"], "EXPLICIT_PRIVATE_ARTIFACT_CONFIRMATION_REQUIRED")
        self.assertFalse(out.exists())
        status = module.evaluate(
            self.src, self.tgt, SITE, 4, private_output=out,
            confirm="PRESERVE_PRIVATE_SQL_LITERALS_ONLY")
        self.assertEqual(status["private_artifact"], "LOCAL_BYTES_VERIFIED_NOT_ENCRYPTED")
        self.assertEqual(original.verify_private(out)["artifact_bytes_verified"], True)
        body = json.loads((out / "originals.json").read_text())
        self.assertEqual(body["verified_backup_sql_identity_digests"]["target_sql_sha256"],
                         module._digest(self.sql_b))
        again = module.evaluate(
            self.src, self.tgt, SITE, 4, private_output=out,
            confirm="PRESERVE_PRIVATE_SQL_LITERALS_ONLY")
        self.assertEqual(again["status"], "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE")
        self.assertTrue(original.verify_private(out)["artifact_bytes_verified"])

    def test_unknown_table_or_inconsistent_backup_blocks_no_sql_leak(self):
        for table in (0, 3, 5, 999):
            with self.subTest(table=table):
                report = module.evaluate(self.src, self.tgt, SITE, table)
                self.assertEqual(report["status"], "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE")
        self.sql_b.write_bytes(b"NOT GZIP")
        out = module.evaluate(self.src, self.tgt, SITE, 4)
        self.assertEqual(out["status"], "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE")

    def test_no_replace_or_update_semantics_are_silently_accepted(self):
        with gzip.open(self.sql_a, "wt") as out:
            out.write(dump(True, replace=True))
        report = module.evaluate(self.src, self.tgt, SITE, 4)
        self.assertEqual(report["status"], "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE")
        with gzip.open(self.sql_a, "wt") as out:
            out.write(dump(True, mutate=True))
        report = module.evaluate(self.src, self.tgt, SITE, 4)
        self.assertEqual(report["status"], "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE")

    def test_backup_sql_changed_between_checks_blocks_and_never_writes(self):
        original_digest = module._digest
        counter = {"n": 0}
        def change_second_read(path):
            counter["n"] += 1
            if counter["n"] == 3:
                return "0"*64
            return original_digest(path)
        with mock.patch.object(module, "_digest", side_effect=change_second_read):
            report = module.evaluate(self.src, self.tgt, SITE, 4,
                                     private_output=self.root / "not-written",
                                     confirm="PRESERVE_PRIVATE_SQL_LITERALS_ONLY")
        self.assertEqual(report["status"], "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE")
        self.assertFalse((self.root / "not-written").exists())

    def test_cli_always_requires_private_package_and_blocks_by_default(self):
        argv = ["--source-package", str(self.src),
                "--target-package", str(self.tgt),
                "--site", SITE, "--table-ordinal", "4"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = module.main(argv)
        self.assertEqual(rc, 0)
        self.assertFalse(json.loads(output.getvalue())["cutover_allowed"])


if __name__ == "__main__":
    unittest.main()
