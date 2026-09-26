#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_backup import BackupTest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "vfops"
sys.path.insert(0, str(ROOT / "lib"))
import verify as verify_engine


class RestoreVerifyTest(unittest.TestCase):
    def make_package(self, base: Path) -> Path:
        source_root = base / "source-root"
        output = base / "backups"
        helper = BackupTest()
        _, fake_export = helper.make_cloudpanel_fixture(source_root)
        proc = helper.run_backup(source_root, fake_export, output)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return Path(proc.stdout.strip())

    def make_sandbox(self, base: Path) -> Path:
        sandbox = base / "sandbox-root"
        sandbox.mkdir()
        (sandbox / ".vfops-sandbox-root").write_text("VF_SERVER_OPS_SANDBOX_V1\n", encoding="utf-8")
        return sandbox

    def make_stateful_clpctl(self, base: Path) -> Path:
        script = base / "fake-stateful-clpctl"
        script.write_text(
            r'''#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
import sys

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
args = {}
for item in sys.argv[2:]:
    if item.startswith("--") and "=" in item:
        key, value = item[2:].split("=", 1)
        args[key] = value
state = Path(os.environ["VFOPS_FAKE_DB_STATE"])
state.mkdir(parents=True, exist_ok=True)
if cmd == "db:import":
    db = args["databaseName"]
    shutil.copy2(Path(args["file"]), state / f"{db}.sql.gz")
    sys.exit(0)
if cmd == "db:export":
    db = args["databaseName"]
    source = state / f"{db}.sql.gz"
    if not source.is_file():
        sys.exit(9)
    target = Path(args["file"])
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    sys.exit(0)
if cmd == "site:delete":
    for item in state.glob("*.sql.gz"):
        item.unlink()
    sys.exit(0)
sys.exit(0)
''',
            encoding="utf-8",
        )
        script.chmod(0o700)
        return script

    def env(self, base: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["VFOPS_FAKE_DB_STATE"] = str(base / "db-state")
        return env

    def apply(self, package: Path, sandbox: Path, fake: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(CLI), "restore", "apply-sandbox",
                "--package", str(package),
                "--target-root", str(sandbox),
                "--clpctl", str(fake),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def verify(self, package: Path, sandbox: Path, fake: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(CLI), "verify", "restore",
                "--package", str(package),
                "--target-root", str(sandbox),
                "--clpctl", str(fake),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def prepared(self, base: Path) -> tuple[Path, Path, Path, dict[str, str]]:
        package = self.make_package(base)
        sandbox = self.make_sandbox(base)
        fake = self.make_stateful_clpctl(base)
        env = self.env(base)
        apply = self.apply(package, sandbox, fake, env)
        self.assertEqual(apply.returncode, 0, apply.stderr)
        return package, sandbox, fake, env

    def test_mysql_fingerprint_accepts_redundant_matching_character_set_before_collate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source.sql.gz"
            target = base / "target.sql.gz"
            source_text = """CREATE TABLE `p07_probe` (\n  `marker` varchar(255) COLLATE utf8mb4_general_ci NOT NULL\n);\nINSERT INTO `p07_probe` VALUES ('same');\n"""
            target_text = """CREATE TABLE `p07_probe` (\n  `marker` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL\n);\nINSERT INTO `p07_probe` VALUES ('same');\n"""
            with gzip.open(source, "wt", encoding="utf-8") as handle:
                handle.write(source_text)
            with gzip.open(target, "wt", encoding="utf-8") as handle:
                handle.write(target_text)
            self.assertEqual(verify_engine.sql_fingerprint(source), verify_engine.sql_fingerprint(target))

    def test_cross_engine_data_fingerprint_ignores_engine_session_ddl_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            maria = base / "maria.sql.gz"
            mysql = base / "mysql.sql.gz"
            maria_text = """-- MariaDB dump
/*!40101 SET NAMES utf8mb4 */;
CREATE TABLE `wp_posts` (
  `ID` bigint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
INSERT INTO `wp_posts` VALUES (1),(2);
"""
            mysql_text = """-- MySQL dump
/*!50503 SET NAMES utf8mb4 */;
CREATE TABLE `wp_posts` (
  `ID` bigint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
INSERT INTO `wp_posts` VALUES (1),(2);
"""
            with gzip.open(maria, "wt", encoding="utf-8") as handle:
                handle.write(maria_text)
            with gzip.open(mysql, "wt", encoding="utf-8") as handle:
                handle.write(mysql_text)
            self.assertNotEqual(
                verify_engine.sql_fingerprint(maria),
                verify_engine.sql_fingerprint(mysql),
            )
            self.assertEqual(
                verify_engine.sql_data_fingerprint(maria),
                verify_engine.sql_data_fingerprint(mysql),
            )

    def test_cross_engine_data_fingerprint_still_detects_changed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source.sql.gz"
            changed = base / "changed.sql.gz"
            with gzip.open(source, "wt", encoding="utf-8") as handle:
                handle.write(
                    "CREATE TABLE `t` (`id` int);\n"
                    "INSERT INTO `t` VALUES (1),(2);\n"
                )
            with gzip.open(changed, "wt", encoding="utf-8") as handle:
                handle.write(
                    "CREATE TABLE `t` (`id` int);\n"
                    "INSERT INTO `t` VALUES (1),(3);\n"
                )
            self.assertNotEqual(
                verify_engine.sql_data_fingerprint(source),
                verify_engine.sql_data_fingerprint(changed),
            )

    def test_mysql_fingerprint_keeps_real_collation_changes_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source.sql.gz"
            target = base / "target.sql.gz"
            with gzip.open(source, "wt", encoding="utf-8") as handle:
                handle.write("`marker` varchar(255) COLLATE utf8mb4_general_ci NOT NULL\n")
            with gzip.open(target, "wt", encoding="utf-8") as handle:
                handle.write("`marker` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL\n")
            self.assertNotEqual(verify_engine.sql_fingerprint(source), verify_engine.sql_fingerprint(target))

    def test_mysql_canonicalization_does_not_hide_conflicting_charset_and_collation(self) -> None:
        source = "`marker` varchar(255) COLLATE utf8mb4_general_ci NOT NULL"
        conflicting = "`marker` varchar(255) CHARACTER SET latin1 COLLATE utf8mb4_general_ci NOT NULL"
        self.assertNotEqual(
            verify_engine.canonical_sql_line(source),
            verify_engine.canonical_sql_line(conflicting),
        )

    def test_restore_verify_passes_files_mysql_sqlite_and_pending_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, sandbox, fake, env = self.prepared(base)
            proc = self.verify(package, sandbox, fake, env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("PRIVATE-RECOVERY-DB-SECRET", proc.stdout + proc.stderr)
            self.assertNotIn("SYNTHETIC-PRIVATE-KEY", proc.stdout + proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "RESTORE_VERIFIED")
            self.assertEqual(result["components"]["files"]["status"], "PASS")
            self.assertEqual(result["components"]["mysql"]["status"], "PASS")
            self.assertEqual(result["components"]["mysql"]["method"], "CLPCTL_REEXPORT_CANONICAL_SQL_FINGERPRINT")
            self.assertEqual(result["components"]["sqlite"]["status"], "PASS")
            self.assertEqual(result["components"]["runtime_metadata"]["status"], "PASS")
            self.assertFalse(result["cutover_ready"])
            self.assertFalse(result["dns_changed"])

    def test_changed_restored_file_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, sandbox, fake, env = self.prepared(base)
            target = sandbox / "home/alice/htdocs/example.com/public/index.php"
            target.write_text("tampered\n", encoding="utf-8")
            proc = self.verify(package, sandbox, fake, env)
            self.assertNotEqual(proc.returncode, 0)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("files", result["failed_components"])
            self.assertIn("public/index.php", result["components"]["files"]["content_mismatch"])

    def test_changed_sqlite_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, sandbox, fake, env = self.prepared(base)
            target = sandbox / "home/alice/htdocs/example.com/data/app.sqlite"
            with target.open("ab") as handle:
                handle.write(b"tamper")
            proc = self.verify(package, sandbox, fake, env)
            self.assertNotEqual(proc.returncode, 0)
            result = json.loads(proc.stdout)
            self.assertIn("sqlite", result["failed_components"])

    def test_changed_mysql_state_is_detected_by_reexport_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, sandbox, fake, env = self.prepared(base)
            state = Path(env["VFOPS_FAKE_DB_STATE"]) / "example_prod.sql.gz"
            with gzip.open(state, "wb") as handle:
                handle.write(b"CREATE TABLE changed(id INT);\n")
            proc = self.verify(package, sandbox, fake, env)
            self.assertNotEqual(proc.returncode, 0)
            result = json.loads(proc.stdout)
            self.assertIn("mysql", result["failed_components"])
            self.assertIn("MYSQL_FINGERPRINT_MISMATCH:example_prod", result["components"]["mysql"]["failures"])

    def test_missing_pending_runtime_metadata_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package, sandbox, fake, env = self.prepared(base)
            evidence = sandbox / "var/lib/vf-server-ops/restored-metadata" / package.name
            shutil.rmtree(evidence)
            proc = self.verify(package, sandbox, fake, env)
            self.assertNotEqual(proc.returncode, 0)
            result = json.loads(proc.stdout)
            self.assertIn("runtime_metadata", result["failed_components"])


if __name__ == "__main__":
    unittest.main()
