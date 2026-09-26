#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import package as package_engine  # noqa: E402
import transport  # noqa: E402


class TransportTest(unittest.TestCase):
    def make_package(self, base: Path) -> Path:
        package = base / "example.com_20260906T120000Z"
        (package / "files").mkdir(parents=True)
        payload = base / "payload.txt"
        payload.write_text("transport fixture\n", encoding="utf-8")
        with tarfile.open(package / "files/site.tar.gz", "w:gz") as archive:
            archive.add(payload, arcname="site/payload.txt")
        manifest = {
            "schema": "vf-server-ops.backup-package.v1",
            "backup_id": package.name,
            "created_at": "2026-09-06T12:00:00+00:00",
            "status": "CREATED",
            "source": {"server": {"hostname_hash": "sha256:source"}, "cloudpanel_version": "2.5.0"},
            "site": {"domain": "example.com", "domains": ["example.com"]},
            "contents": {"files_archive": "files/site.tar.gz", "mysql": [], "sqlite": [], "metadata": {}},
            "security": {
                "classification": "PRIVATE_SENSITIVE_BACKUP",
                "contains_sensitive_data": True,
                "remote_storage_requires_encryption": True,
                "ssl_private_key_included": False,
            },
        }
        package_engine.write_json_private(package / "manifest.json", manifest)
        package_engine.write_checksums(package)
        verification = package_engine.verify_package(package)
        self.assertEqual(verification["status"], "PASS")
        package_engine.write_json_private(package / "verification.json", verification)
        return package

    def make_fake_ssh(self, base: Path) -> Path:
        script = base / "fake-ssh"
        script.write_text(
            r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

log = Path(os.environ["FAKE_SSH_LOG"])
command = sys.argv[-1] if len(sys.argv) > 1 else ""
options = " ".join(sys.argv[1:-2]) if len(sys.argv) > 2 else ""
endpoint = sys.argv[-2] if len(sys.argv) > 2 else ""

def append(kind):
    with log.open("a", encoding="utf-8") as handle:
        handle.write(kind + "\tOPTIONS=" + options + "\tENDPOINT=" + endpoint + "\tCOMMAND=" + command + "\n")

if "command -v clpctl" in command:
    append("PREFLIGHT")
    sys.exit(0)

if "rm -rf --" in command and "/var/lib/vf-server-ops/transport-runtime/" in command:
    append("CLEANUP")
    sys.exit(9 if os.environ.get("FAKE_CLEANUP_FAIL") == "1" else 0)

if "tar -xzf -" in command:
    payload = sys.stdin.buffer.read()
    if not payload:
        sys.exit(4)
    append("TRANSFER")
    sys.exit(0)

if "migrate apply-new-site" in command:
    append("MIGRATE")
    ready = os.environ.get("FAKE_MIGRATION_NOT_READY") != "1"
    staged = "--defer-runtime" in command
    result = {
        "schema": "vf-server-ops.migration-result.v1",
        "status": ("MIGRATION_STAGED" if staged and ready else ("TECHNICAL_CUTOVER_READY" if ready else "NEW_SITE_MIGRATION_NOT_READY")),
        "restore_status": "RESTORE_VERIFIED" if ready else "FAIL",
        "runtime_status": "RUNTIME_DEFERRED" if staged and ready else ("RUNTIME_ACTIVATED" if ready else "NOT_RUN"),
        "cross_server_status": "PASS" if ready else "FAIL",
        "http_https_status": "DEFERRED_WITH_RUNTIME" if staged and ready else ("PASS" if ready else "FAIL"),
        "blockers": [] if ready else ["RESTORE_NOT_VERIFIED", "RUNTIME_NOT_ACTIVATED"],
        "technical_cutover_ready": ready and not staged,
        "staged_for_cutover": ready and staged,
        "runtime_deferred": staged,
        "owner_cutover_gate_required": True,
        "dns_changed": False,
        "old_server_delete_requested": False,
        "secret": "DO_NOT_FORWARD_THIS_VALUE",
    }
    print(json.dumps(result))
    sys.exit(0 if ready else 9)

append("UNKNOWN")
sys.exit(9)
''',
            encoding="utf-8",
        )
        script.chmod(0o700)
        return script

    def with_env(self, **values: str) -> dict[str, str | None]:
        old = {key: os.environ.get(key) for key in values}
        for key, value in values.items():
            os.environ[key] = value
        return old

    def restore_env(self, old: dict[str, str | None]) -> None:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_transfer_reuses_target_migration_cleans_private_staging_and_stops_before_cutover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            fake_ssh = self.make_fake_ssh(base)
            log = base / "ssh.log"
            old = self.with_env(FAKE_SSH_LOG=str(log))
            try:
                result = transport.transfer_new_site(
                    package,
                    "203.0.113.20",
                    "203.0.113.20",
                    "root",
                    22,
                    None,
                    f"MIGRATE_NEW_SITE:example.com:{package.name}",
                    str(fake_ssh),
                    "tar",
                )
            finally:
                self.restore_env(old)

            self.assertEqual(result["status"], "TECHNICAL_CUTOVER_READY")
            self.assertEqual(result["transport"], "SSH_TAR_PRIVATE_STREAM")
            self.assertTrue(result["technical_cutover_ready"])
            self.assertTrue(result["owner_cutover_gate_required"])
            self.assertEqual(result["remote_private_staging_cleanup"], "PASS")
            self.assertFalse(result["runtime_staging_retained"])
            self.assertFalse(result["package_staging_retained"])
            self.assertFalse(result["dns_changed"])
            self.assertFalse(result["old_server_delete_requested"])
            self.assertFalse(result["existing_site_overwrite"])
            self.assertFalse(result["source_backup_deleted"])
            self.assertFalse(result["ssh_password_accepted"])
            self.assertEqual(result["host_key_policy"], "STRICT_ACCEPT_NEW_REFUSE_CHANGED")
            self.assertTrue(result["target_endpoint"].startswith("sha256:"))
            self.assertNotIn("203.0.113.20", result["target_endpoint"])

            lines = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(sum(line.startswith("PREFLIGHT\t") for line in lines), 1)
            self.assertEqual(sum(line.startswith("TRANSFER\t") for line in lines), 2)
            self.assertEqual(sum(line.startswith("MIGRATE\t") for line in lines), 1)
            self.assertEqual(sum(line.startswith("CLEANUP\t") for line in lines), 1)
            self.assertTrue(any("StrictHostKeyChecking=accept-new" in line for line in lines))
            self.assertTrue(all("BatchMode=yes" in line for line in lines))

    def test_staged_transfer_defers_runtime_and_never_claims_cutover_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            fake_ssh = self.make_fake_ssh(base)
            log = base / "ssh.log"
            old = self.with_env(FAKE_SSH_LOG=str(log))
            try:
                result = transport.transfer_new_site(
                    package,
                    "203.0.113.20",
                    "203.0.113.20",
                    "root",
                    22,
                    None,
                    f"MIGRATE_NEW_SITE:example.com:{package.name}",
                    str(fake_ssh),
                    "tar",
                    True,
                )
            finally:
                self.restore_env(old)

            self.assertEqual(result["status"], "MIGRATION_STAGED")
            self.assertFalse(result["technical_cutover_ready"])
            self.assertTrue(result["staged_for_cutover"])
            self.assertTrue(result["runtime_deferred"])
            self.assertEqual(result["runtime_status"], "RUNTIME_DEFERRED")
            self.assertFalse(result["dns_changed"])
            self.assertFalse(result["old_server_delete_requested"])
            text = log.read_text(encoding="utf-8")
            self.assertIn("--defer-runtime", text)

    def test_wrong_confirmation_never_contacts_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            fake_ssh = self.make_fake_ssh(base)
            log = base / "ssh.log"
            old = self.with_env(FAKE_SSH_LOG=str(log))
            try:
                with self.assertRaises(transport.TransportError):
                    transport.transfer_new_site(
                        package, "203.0.113.20", "203.0.113.20", "root", 22, None,
                        "WRONG", str(fake_ssh), "tar",
                    )
            finally:
                self.restore_env(old)
            self.assertFalse(log.exists())

    def test_target_not_ready_reports_safe_structured_diagnostics_and_cleans_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            fake_ssh = self.make_fake_ssh(base)
            log = base / "ssh.log"
            old = self.with_env(FAKE_SSH_LOG=str(log), FAKE_MIGRATION_NOT_READY="1")
            try:
                with self.assertRaises(transport.TransportError) as caught:
                    transport.transfer_new_site(
                        package, "203.0.113.20", "203.0.113.20", "root", 22, None,
                        f"MIGRATE_NEW_SITE:example.com:{package.name}", str(fake_ssh), "tar",
                    )
            finally:
                self.restore_env(old)
            message = str(caught.exception)
            self.assertIn("stage=RESTORE_VERIFY", message)
            self.assertIn("target_status=NEW_SITE_MIGRATION_NOT_READY", message)
            self.assertIn("restore_status=FAIL", message)
            self.assertIn("runtime_status=NOT_RUN", message)
            self.assertIn("blockers=RESTORE_NOT_VERIFIED,RUNTIME_NOT_ACTIVATED", message)
            self.assertNotIn("DO_NOT_FORWARD_THIS_VALUE", message)
            text = log.read_text(encoding="utf-8")
            self.assertIn("MIGRATE\t", text)
            self.assertIn("CLEANUP\t", text)

    def test_real_like_runtime_failure_is_inferred_without_raw_output(self) -> None:
        payload = json.dumps(
            {
                "status": "NEW_SITE_MIGRATION_NOT_READY",
                "restore_status": "RESTORE_VERIFIED",
                "runtime_status": "FAILED",
                "cross_server_status": "FAIL",
                "http_https_status": "PASS",
                "blockers": ["RUNTIME_NOT_ACTIVATED", "CROSS_SERVER_VERIFY_NOT_PASS"],
                "runtime_error_class": "RuntimeActivationError",
                "private": "DO_NOT_FORWARD_THIS_VALUE",
            }
        )
        diagnostics = transport.safe_target_failure_diagnostics(payload, "")
        self.assertEqual(diagnostics["stage"], "RUNTIME_ACTIVATION")
        self.assertEqual(diagnostics["restore_status"], "RESTORE_VERIFIED")
        self.assertEqual(diagnostics["runtime_status"], "FAILED")
        rendered = transport.format_target_failure_diagnostics(diagnostics)
        self.assertIn("stage=RUNTIME_ACTIVATION", rendered)
        self.assertIn("blockers=RUNTIME_NOT_ACTIVATED,CROSS_SERVER_VERIFY_NOT_PASS", rendered)
        self.assertNotIn("RuntimeActivationError", rendered)
        self.assertNotIn("DO_NOT_FORWARD_THIS_VALUE", rendered)

    def test_invalid_target_stdout_is_never_forwarded(self) -> None:
        diagnostics = transport.safe_target_failure_diagnostics(
            "password=DO_NOT_FORWARD_THIS_VALUE",
            "ERROR: secret=DO_NOT_FORWARD_THIS_VALUE",
        )
        self.assertEqual(diagnostics, {"stage": "TARGET_MIGRATION"})
        rendered = transport.format_target_failure_diagnostics(diagnostics)
        self.assertEqual(rendered, "stage=TARGET_MIGRATION")
        self.assertNotIn("DO_NOT_FORWARD_THIS_VALUE", rendered)

    def test_cleanup_failure_blocks_ready_migration_from_becoming_transport_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            fake_ssh = self.make_fake_ssh(base)
            log = base / "ssh.log"
            old = self.with_env(FAKE_SSH_LOG=str(log), FAKE_CLEANUP_FAIL="1")
            try:
                with self.assertRaisesRegex(transport.TransportError, "private staging cleanup failed"):
                    transport.transfer_new_site(
                        package, "203.0.113.20", "203.0.113.20", "root", 22, None,
                        f"MIGRATE_NEW_SITE:example.com:{package.name}", str(fake_ssh), "tar",
                    )
            finally:
                self.restore_env(old)
            lines = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(sum(line.startswith("MIGRATE\t") for line in lines), 1)
            self.assertGreaterEqual(sum(line.startswith("CLEANUP\t") for line in lines), 2)

    def test_safe_target_failure_stage_only_exposes_allowlisted_marker(self) -> None:
        self.assertEqual(
            transport.safe_target_failure_stage(
                "ERROR: new-site restore failed; stage=SSL_INSTALL; cleanup=SITE_DELETE_REQUESTED; reason=SandboxRestoreError"
            ),
            "SSL_INSTALL",
        )
        self.assertIsNone(transport.safe_target_failure_stage("ERROR: password=do-not-emit"))
        self.assertIsNone(transport.safe_target_failure_stage("ERROR: stage=bad/value"))

    def test_explicit_stderr_stage_wins_over_json_inference(self) -> None:
        payload = json.dumps(
            {
                "status": "NEW_SITE_MIGRATION_NOT_READY",
                "restore_status": "RESTORE_VERIFIED",
                "runtime_status": "FAILED",
            }
        )
        diagnostics = transport.safe_target_failure_diagnostics(
            payload,
            "ERROR: new-site restore failed; stage=SSL_INSTALL; password=DO_NOT_FORWARD",
        )
        self.assertEqual(diagnostics["stage"], "SSL_INSTALL")
        self.assertNotIn("DO_NOT_FORWARD", transport.format_target_failure_diagnostics(diagnostics))

    def test_host_and_user_injection_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            package = self.make_package(base)
            fake_ssh = self.make_fake_ssh(base)
            log = base / "ssh.log"
            old = self.with_env(FAKE_SSH_LOG=str(log))
            confirm = f"MIGRATE_NEW_SITE:example.com:{package.name}"
            try:
                with self.assertRaises(transport.TransportError):
                    transport.transfer_new_site(
                        package, "host;touch-pwned", "203.0.113.20", "root", 22, None,
                        confirm, str(fake_ssh), "tar",
                    )
                with self.assertRaises(transport.TransportError):
                    transport.transfer_new_site(
                        package, "203.0.113.20", "203.0.113.20", "bad;user", 22, None,
                        confirm, str(fake_ssh), "tar",
                    )
            finally:
                self.restore_env(old)
            self.assertFalse(log.exists())


if __name__ == "__main__":
    unittest.main()
