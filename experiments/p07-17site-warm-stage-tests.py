"""P07 14-site private warm-copy safety, synthetic-only; no server access."""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("p07-17site-owner-continuation.py")
spec = importlib.util.spec_from_file_location("p07_owner_warm", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class WarmStageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "bundle"
        (self.root / "sites").mkdir(parents=True, mode=0o700)
        patches = [
            mock.patch.object(mod, "BUNDLE_ROOT", self.root),
            mock.patch.object(mod, "private_dir",
                side_effect=lambda p: p.mkdir(parents=True, mode=0o700, exist_ok=True)),
            mock.patch.object(mod, "file_read_json",
                side_effect=lambda p: json.loads(p.read_text())),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.seen = {}
        for i, d in enumerate(mod.PENDING):
            self.seen[d] = (
                {"migration_id": mod.JOBS[i][1], "source": {"host": "test"}},
                {"site_root": "/home/" + d},
            )
            dest = self.dest(d)
            dest.mkdir(mode=0o700)
            (dest / "already-staged").write_text("preserved")
        for i in range(14):
            d = "site%02d.example.test" % i
            self.seen[d] = (
                {"migration_id": mod.JOBS[0][1], "source": {"host": "test"}},
                {"site_root": "/home/" + d},
            )
        mod.safe_write(mod.manifest_path(), {
            "schema": "P07_OWNER_STAGE_V1", "phase": "STAGED",
            "sites": {d: {"files_status": "TRANSFERRED"} for d in mod.PENDING},
        })
        self.remote_calls = []
        self.copies = []
        self.fail_on = None

    def dest(self, d):
        return self.root / "sites" / hashlib.sha256(d.encode()).hexdigest()[:16]

    def fake_pull(self):
        def remote(source, command, **kwargs):
            self.remote_calls.append(command)
            return subprocess.CompletedProcess([], 0, "1\t/home/test\n", "")
        def copy(source, path, dest, *, delete):
            self.assertFalse(delete)
            self.copies.append(dest)
            if self.fail_on == len(self.copies):
                raise RuntimeError("intentional interrupted copy")
            (dest / "data").write_text("fixture")
        return types.SimpleNamespace(source_remote=remote, pull_path=copy)

    def test_exact_fourteen_copies_and_three_preserved_without_repeat(self):
        pull = self.fake_pull()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            mod.warm_stage_remaining_site_files(pull, self.seen)
            mod.verify_warm_site_files(self.seen)
            mod.warm_stage_remaining_site_files(pull, self.seen)
        self.assertEqual(len(self.copies), 14)
        self.assertEqual(len(self.remote_calls), 14)
        self.assertIn("WARM_INACTIVE_SITE_ROOTS_VERIFIED=17/17", output.getvalue())
        self.assertIn("FINAL_FROZEN_FILE_PARITY=NOT_VERIFIED", output.getvalue())
        for d in mod.PENDING:
            self.assertEqual((self.dest(d) / "already-staged").read_text(), "preserved")

    def test_missing_pending_original_is_blocked_before_network(self):
        (self.dest(mod.PENDING[0]) / "already-staged").unlink()
        with self.assertRaisesRegex(mod.Block, "WARM_THREE_ORIGINAL_SITE_ROOTS_UNVERIFIED"):
            mod.warm_stage_remaining_site_files(self.fake_pull(), self.seen)
        self.assertEqual(self.remote_calls, [])

    def test_destination_collision_blocks_without_overwrite(self):
        dest = self.dest("site00.example.test")
        dest.mkdir()
        (dest / "protected").write_text("original")
        with self.assertRaisesRegex(mod.Block, "WARM_DESTINATION_EXISTS_NO_OVERWRITE"):
            mod.warm_stage_remaining_site_files(self.fake_pull(), self.seen)
        self.assertEqual((dest / "protected").read_text(), "original")
        self.assertEqual(self.remote_calls, [])

    def test_copy_interruption_retains_journal_and_refuses_retry(self):
        self.fail_on = 3
        pull = self.fake_pull()
        with self.assertRaisesRegex(RuntimeError, "intentional interrupted"):
            mod.warm_stage_remaining_site_files(pull, self.seen)
        statuses = [r["status"] for r in mod.read_manifest()["warm_sites"].values()]
        self.assertEqual(statuses.count("TRANSFERRED"), 2)
        self.assertEqual(statuses.count("TRANSFER_IN_PROGRESS"), 1)
        with self.assertRaisesRegex(mod.Block, "WARM_PARTIAL_COPY_NO_AUTO_RETRY"):
            mod.warm_stage_remaining_site_files(pull, self.seen)
        self.assertEqual(len(self.copies), 3)

    def test_original_owner_drift_blocks_before_new_copy(self):
        pull = self.fake_pull()
        with contextlib.redirect_stdout(io.StringIO()):
            mod.warm_stage_remaining_site_files(pull, self.seen)
        state, site = self.seen["site00.example.test"]
        self.seen["site00.example.test"] = (dict(state, migration_id="changed"), site)
        with self.assertRaisesRegex(mod.Block, "WARM_ORIGINAL_OWNER_IDENTITY_CHANGED"):
            mod.warm_stage_remaining_site_files(pull, self.seen)
        self.assertEqual(len(self.copies), 14)


if __name__ == "__main__":
    unittest.main()
