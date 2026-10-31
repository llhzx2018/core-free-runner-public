"""Synthetic-only CLI safety: offline literal review never calls migration writer."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import server_migration_pull as pull


class OfflineReviewCLITests(unittest.TestCase):
    def run_cli(self, *arguments):
        args = [
            "server_migration_pull.py", "recovery-literal-review",
            "--source-package", "/synthetic/source",
            "--target-package", "/synthetic/target",
            "--site", "synthetic.example.test",
            "--table-ordinal", "4",
            *arguments,
        ]
        output = io.StringIO()
        with mock.patch.object(sys, "argv", args), contextlib.redirect_stdout(output):
            exit_code = pull.main()
        return exit_code, json.loads(output.getvalue())

    def test_read_only_default_calls_private_kernel_only(self):
        allowed = {
            "status": "PRIVATE_SQL_LITERALS_CAPTURED_NOT_RESTORED",
            "data_writes_allowed": False, "migration_resume_allowed": False,
            "cutover_allowed": False, "verification": "NOT_A_PASS_GATE",
        }
        with mock.patch.object(pull.private_sql_literal_reconcile, "evaluate",
                               return_value=allowed) as evaluation, \
             mock.patch.object(pull, "source_probe") as probe, \
             mock.patch.object(pull, "save_state") as save, \
             mock.patch.object(pull, "prepare_migration") as prepare:
            rc, result = self.run_cli()
        self.assertEqual(rc, 0)
        self.assertEqual(result, allowed)
        evaluation.assert_called_once_with(
            Path("/synthetic/source"), Path("/synthetic/target"),
            "synthetic.example.test", 4,
            private_output=None, confirm=None)
        probe.assert_not_called()
        save.assert_not_called()
        prepare.assert_not_called()

    def test_private_output_flags_are_not_automatically_approved(self):
        rejected = {
            "status": "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE",
            "reason": "EXPLICIT_PRIVATE_ARTIFACT_CONFIRMATION_REQUIRED",
            "data_writes_allowed": False, "migration_resume_allowed": False,
            "cutover_allowed": False, "verification": "NOT_A_PASS_GATE",
        }
        with mock.patch.object(pull.private_sql_literal_reconcile, "evaluate",
                               return_value=rejected) as evaluation:
            rc, result = self.run_cli("--private-output", "/synthetic/private")
        self.assertEqual(rc, 13)
        self.assertEqual(result["reason"],
                         "EXPLICIT_PRIVATE_ARTIFACT_CONFIRMATION_REQUIRED")
        self.assertIsNone(evaluation.call_args.kwargs["confirm"])

    def test_untrusted_pass_claim_cannot_unlock_database_writes(self):
        for changed in (
            {"data_writes_allowed": True},
            {"migration_resume_allowed": True},
            {"cutover_allowed": True},
            {"status": "BLOCKED_PRIVATE_SQL_LITERAL_EVIDENCE"},
        ):
            with self.subTest(changed=changed):
                payload = {
                    "status": "PRIVATE_SQL_LITERALS_CAPTURED_NOT_RESTORED",
                    "data_writes_allowed": False,
                    "migration_resume_allowed": False,
                    "cutover_allowed": False, **changed,
                }
                with mock.patch.object(pull.private_sql_literal_reconcile,
                                       "evaluate", return_value=payload):
                    code, _ = self.run_cli()
                self.assertEqual(code, 13)


if __name__ == "__main__":
    unittest.main()
