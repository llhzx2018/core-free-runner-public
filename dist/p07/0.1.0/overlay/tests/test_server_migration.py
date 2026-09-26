from __future__ import annotations

import ast
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import server_migration as engine


class ServerMigrationAutomationTests(unittest.TestCase):
    def test_server_migration_module_has_unique_top_level_functions(self) -> None:
        source = (ROOT / "lib/server_migration.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        duplicates = sorted({
            name for name in names if names.count(name) > 1
        })
        self.assertEqual(duplicates, [])
        self.assertEqual(names.count("main"), 1)
        self.assertEqual(source.count('if __name__ == "__main__":'), 1)

    def target(self) -> dict:
        return {
            "host": "203.0.113.20",
            "ip": "203.0.113.20",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "ssh": "ssh",
        }

    def source_inventory(self) -> dict:
        return {
            "source_server": {"hostname_hash": "sha256:source"},
            "sites": [
                {
                    "domain": "a.example.com",
                    "site_user": "alice",
                    "site_root": "/home/alice/htdocs/a.example.com",
                    "document_root": "/home/alice/htdocs/a.example.com",
                    "runtime": {"type": "php", "version": "8.4"},
                    "mysql_databases": [],
                    "cron": {"entry_count": 0, "source_paths": []},
                    "pm2": {"present": False, "processes": []},
                    "ssl": {"configured": True},
                    "domains": ["a.example.com"],
                    "sqlite_paths": [],
                },
                {
                    "domain": "b.example.com",
                    "site_user": "bob",
                    "site_root": "/home/bob/htdocs/b.example.com",
                    "document_root": "/home/bob/htdocs/b.example.com",
                    "runtime": {"type": "php", "version": "8.3"},
                    "mysql_databases": ["bdb"],
                    "cron": {"entry_count": 1, "source_paths": ["/etc/cron.d/b-example"]},
                    "pm2": {"present": False, "processes": []},
                    "ssl": {"configured": True},
                    "domains": ["b.example.com"],
                    "sqlite_paths": [],
                },
            ],
        }

    def test_plan_is_read_only_and_keeps_dns_as_separate_gate(self) -> None:
        capacity = {
            "site_and_external_bytes": 100,
            "mysql_raw_reference_bytes": 20,
            "estimated_payload_bytes": 120,
            "target_required_bytes": 700,
            "source_transient_required_bytes": 300,
        }
        with mock.patch.object(engine, "current_inventory", return_value=self.source_inventory()), \
             mock.patch.object(engine, "validate_full_server_site_set", return_value={"status": "READY"}), \
             mock.patch.object(engine, "migration_capacity_estimate", return_value=capacity), \
             mock.patch.object(engine, "source_dependency_preflight", return_value={"status": "READY"}), \
             mock.patch.object(engine, "target_preflight", return_value={"status": "READY"}):
            result = engine.plan_payload(self.target(), [])
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["site_count"], 2)
        self.assertTrue(result["dns_manual_gate_required"])
        self.assertFalse(result["automatic_dns_change"])
        self.assertFalse(result["source_delete_allowed"])
        self.assertFalse(result["writes_performed"])

    def test_hidden_home_data_discovery_covers_vf_press_and_local_share(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home_root = Path(td) / "home"
            home = home_root / "alice"
            site_root = home / "htdocs/a.example.com"
            site_root.mkdir(parents=True)
            for rel in (
                ".vfasset-data-abc",
                ".vfinfra-data",
                ".press.example-data",
                ".local/share/vf-seo",
            ):
                (home / rel).mkdir(parents=True)
            # htdocs hidden data is already in the normal site package and must not
            # be reclassified as external home data.
            (site_root / ".vfinside").mkdir()

            site = {
                "site_user": "alice",
                "site_root": str(site_root),
            }
            result = engine.external_paths_for_site(site, home_root)
            rendered = "\n".join(result)
            self.assertIn(".vfasset-data-abc", rendered)
            self.assertIn(".vfinfra-data", rendered)
            self.assertIn(".press.example-data", rendered)
            self.assertIn(".local/share/vf-seo", rendered)
            self.assertNotIn(".vfinside", rendered)

    def test_whole_home_sqlite_discovery_finds_external_and_site_databases(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home_root = Path(td) / "home"
            home = home_root / "alice"
            outside = home / ".vfforge-data/database"
            inside = home / "htdocs/a.example.com/data"
            backup = home / "backups"
            outside.mkdir(parents=True)
            inside.mkdir(parents=True)
            backup.mkdir(parents=True)

            for path in (outside / "forge.sqlite", inside / "app.sqlite", backup / "old.sqlite"):
                conn = sqlite3.connect(path)
                conn.execute("CREATE TABLE x(id INTEGER)")
                conn.commit()
                conn.close()

            found = engine.sqlite_paths_for_sites(
                [{"site_user": "alice"}],
                home_root,
            )
            names = {str(path) for path, _ in found}
            self.assertIn(str(outside / "forge.sqlite"), names)
            self.assertIn(str(inside / "app.sqlite"), names)
            self.assertNotIn(str(backup / "old.sqlite"), names)

    def test_sqlite_snapshot_uses_consistent_backup_api(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "live.sqlite"
            target = Path(td) / "snapshot.sqlite"
            conn = sqlite3.connect(source)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO items(name) VALUES ('one')")
            conn.commit()
            engine.sqlite_snapshot(source, target)
            conn.execute("INSERT INTO items(name) VALUES ('two')")
            conn.commit()
            conn.close()

            check = sqlite3.connect(target)
            try:
                self.assertEqual(check.execute("PRAGMA quick_check").fetchone()[0], "ok")
                self.assertEqual(check.execute("SELECT COUNT(*) FROM items").fetchone()[0], 1)
            finally:
                check.close()

    def test_target_site_creation_contract_detects_missing_alias_or_docroot_drift(self) -> None:
        source = {
            "domain": "a.example.com",
            "domains": ["a.example.com", "www.a.example.com"],
            "site_user": "alice",
            "site_root": "/home/alice/htdocs/a.example.com",
            "document_root": "/home/alice/htdocs/a.example.com/public",
            "runtime": {"type": "php", "version": "8.4", "app_port": "UNKNOWN"},
        }
        target = {
            "domain": "a.example.com",
            "domains": ["a.example.com"],
            "site_user": "alice",
            "site_root": "/home/alice/htdocs/a.example.com",
            "document_root": "/home/alice/htdocs/a.example.com",
            "runtime": {"type": "php", "version": "8.4", "app_port": "UNKNOWN"},
        }
        self.assertEqual(
            engine.target_site_creation_mismatches(source, target),
            ["document_root", "domains"],
        )

    def test_target_site_creation_contract_accepts_equivalent_runtime_with_extra_target_alias(self) -> None:
        source = {
            "domain": "a.example.com",
            "domains": ["a.example.com"],
            "site_user": "alice",
            "site_root": "/home/alice/htdocs/a.example.com",
            "document_root": "/home/alice/htdocs/a.example.com",
            "runtime": {"type": "php", "version": "8.4", "app_port": "UNKNOWN"},
        }
        target = dict(source)
        target["domains"] = ["a.example.com", "www.a.example.com"]
        self.assertEqual(
            engine.target_site_creation_mismatches(source, target),
            [],
        )

    def test_site_set_portability_gate_accepts_canonical_cloudpanel_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            site_root = home / "alice/htdocs/a.example.com"
            site_root.mkdir(parents=True)
            sites = [{
                "domain": "a.example.com",
                "site_user": "alice",
                "site_root": str(site_root),
                "runtime": {"type": "php", "version": "8.4", "app_port": "UNKNOWN"},
                "mysql_databases": [],
                "cron": {"entry_count": 0, "source_paths": []},
                "pm2": {"present": False, "processes": []},
            }]
            result = engine.validate_full_server_site_set(sites, home)
            self.assertEqual(result["status"], "READY")
            self.assertEqual(result["unique_site_users"], 1)

    def test_site_set_portability_gate_rejects_duplicate_site_users(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            for domain in ("a.example.com", "b.example.com"):
                (home / f"alice/htdocs/{domain}").mkdir(parents=True, exist_ok=True)
            sites = [
                {
                    "domain": domain,
                    "site_user": "alice",
                    "site_root": str(home / f"alice/htdocs/{domain}"),
                    "runtime": {"type": "php", "version": "8.4"},
                    "mysql_databases": [],
                    "cron": {"entry_count": 0, "source_paths": []},
                    "pm2": {"present": False, "processes": []},
                }
                for domain in ("a.example.com", "b.example.com")
            ]
            with self.assertRaisesRegex(engine.ServerMigrationError, "unique Site Users"):
                engine.validate_full_server_site_set(sites, home)

    def test_site_set_portability_gate_rejects_malformed_cron_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            site_root = home / "alice/htdocs/a.example.com"
            site_root.mkdir(parents=True)
            site = {
                "domain": "a.example.com",
                "site_user": "alice",
                "site_root": str(site_root),
                "runtime": {"type": "php", "version": "8.4"},
                "mysql_databases": [],
                "cron": {"entry_count": "UNKNOWN", "source_paths": []},
                "pm2": {"present": False, "processes": []},
            }
            with self.assertRaisesRegex(engine.ServerMigrationError, "Cron entry count"):
                engine.validate_full_server_site_set([site], home)

    def test_site_set_portability_gate_rejects_ambiguous_pm2_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            site_root = home / "alice/htdocs/a.example.com"
            site_root.mkdir(parents=True)
            site = {
                "domain": "a.example.com",
                "site_user": "alice",
                "site_root": str(site_root),
                "runtime": {"type": "php", "version": "8.4"},
                "mysql_databases": [],
                "cron": {"entry_count": 0, "source_paths": []},
                "pm2": {"present": True, "processes": "UNKNOWN"},
            }
            with self.assertRaisesRegex(engine.ServerMigrationError, "PM2 metadata"):
                engine.validate_full_server_site_set([site], home)

    def test_non_cloudpanel_public_listener_detection_preserves_vpn_proxy_port(self) -> None:
        sample = (
            "tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n"
            "tcp LISTEN 0 128 0.0.0.0:80 0.0.0.0:*\n"
            "tcp LISTEN 0 128 [::]:8443 [::]:*\n"
            "udp UNCONN 0 0 *:31535 *:*\n"
            "tcp LISTEN 0 128 127.0.0.1:6379 0.0.0.0:*\n"
        )
        result = engine.parse_public_listener_rows(sample)
        self.assertEqual(
            result,
            [{"protocol": "udp", "port": 31535, "classification": "NON_CLOUDPANEL_PUBLIC_LISTENER"}],
        )

    def test_bootstrap_script_is_checksum_pinned_and_never_curl_pipe_bash(self) -> None:
        script = engine.cloudpanel_bootstrap_script("do")
        self.assertIn(engine.CLOUDPANEL_INSTALLER_URL, script)
        self.assertIn(engine.CLOUDPANEL_INSTALLER_SHA256, script)
        self.assertIn("sha256sum -c", script)
        self.assertIn("CLOUD=do", script)
        self.assertIn("DB_ENGINE=MYSQL_8.4", script)
        self.assertNotIn("| bash", script)
        self.assertNotIn("| sudo", script)

    def test_bootstrap_os_and_cloud_detection_are_allowlisted(self) -> None:
        self.assertEqual(
            engine.parse_os_release('ID=ubuntu\nVERSION_ID="24.04"\n'),
            ("ubuntu", "24.04"),
        )
        self.assertIn(("ubuntu", "24.04"), engine.SUPPORTED_BOOTSTRAP_OS)
        self.assertEqual(engine.detect_cloud_hint("DigitalOcean Droplet"), "do")
        self.assertEqual(engine.detect_cloud_hint("Amazon EC2"), "aws")
        self.assertEqual(engine.detect_cloud_hint("unknown vendor"), "")

    def test_bootstrap_preflight_accepts_supported_two_gb_class_empty_target(self) -> None:
        responses = [
            subprocess.CompletedProcess([], 0, 'ID=ubuntu\nVERSION_ID="24.04"\n', ''),
            subprocess.CompletedProcess([], 0, 'x86_64|1|2100000|12884901888', ''),
            subprocess.CompletedProcess([], 0, '', ''),
            subprocess.CompletedProcess([], 0, 'DigitalOcean Droplet\n', ''),
        ]
        with mock.patch.object(
            engine.transport,
            "run_ssh",
            side_effect=responses,
        ):
            result = engine.target_bootstrap_preflight(self.target())
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["architecture"], "x86_64")
        self.assertEqual(result["cores"], 1)
        self.assertEqual(result["cloud_hint"], "do")
        self.assertEqual(result["db_engine"], "MYSQL_8.4")

    def test_bootstrap_preflight_rejects_low_memory_before_empty_server_guard(self) -> None:
        responses = [
            subprocess.CompletedProcess([], 0, 'ID=debian\nVERSION_ID="12"\n', ''),
            subprocess.CompletedProcess([], 0, 'x86_64|1|1000000|12884901888', ''),
        ]
        with mock.patch.object(
            engine.transport,
            "run_ssh",
            side_effect=responses,
        ) as run_ssh:
            with self.assertRaisesRegex(engine.ServerMigrationError, "memory"):
                engine.target_bootstrap_preflight(self.target())
        self.assertEqual(run_ssh.call_count, 2)

    def test_bootstrap_requires_exact_target_confirmation_before_remote_write(self) -> None:
        target = self.target()
        with mock.patch.object(engine, "target_bootstrap_preflight") as preflight, \
             mock.patch.object(engine, "remote") as remote:
            with self.assertRaisesRegex(engine.ServerMigrationError, "explicit confirmation required"):
                engine.bootstrap_target_cloudpanel(target, "NO")
        preflight.assert_not_called()
        remote.assert_not_called()

    def test_capacity_estimate_deduplicates_paths_and_adds_headroom(self) -> None:
        sites = [
            {
                "domain": "a.example.com",
                "site_user": "alice",
                "site_root": "/home/alice/htdocs/a.example.com",
                "mysql_databases": ["adb"],
            },
            {
                "domain": "b.example.com",
                "site_user": "alice",
                "site_root": "/home/alice/htdocs/b.example.com",
                "mysql_databases": [],
            },
        ]
        sizes = {
            "/home/alice/htdocs/a.example.com": 1000,
            "/home/alice/htdocs/b.example.com": 2000,
            "/home/alice/.vfinfra-data": 3000,
            "/home/mysql": 4000,
        }
        with mock.patch.object(
            engine,
            "external_paths_for_site",
            return_value=["/home/alice/.vfinfra-data"],
        ), mock.patch.object(
            engine,
            "path_apparent_size",
            side_effect=lambda path: sizes.get(str(path), 0),
        ):
            result = engine.migration_capacity_estimate(sites)
        self.assertEqual(result["site_and_external_bytes"], 6000)
        self.assertEqual(result["mysql_raw_reference_bytes"], 4000)
        self.assertEqual(result["estimated_payload_bytes"], 10000)
        self.assertGreater(result["target_required_bytes"], 10000)

    def test_read_only_source_preflight_can_advertise_missing_rsync_autofix(self) -> None:
        sites = [{"domain": "a.example.com", "cron": {"entry_count": 0}, "pm2": {"present": False}}]
        capacity = {"source_transient_required_bytes": 100}
        fake_usage = type("Usage", (), {"total": 100_000, "used": 10_000, "free": 90_000})()

        def which(name: str):
            return None if name == "rsync" else f"/usr/bin/{name}"

        with mock.patch.object(engine.shutil, "which", side_effect=which), \
             mock.patch.object(engine.shutil, "disk_usage", return_value=fake_usage):
            result = engine.source_dependency_preflight(
                sites,
                capacity,
                allow_missing_rsync_autofix=True,
            )
        self.assertEqual(result["status"], "READY_WITH_AUTO_FIX")
        self.assertEqual(result["missing_commands"], ["rsync"])
        self.assertEqual(result["auto_install_on_prepare"], ["rsync"])

    def test_source_preflight_blocks_when_low_disk_transient_reserve_is_unavailable(self) -> None:
        sites = [{"domain": "a.example.com", "cron": {"entry_count": 0}, "pm2": {"present": False}}]
        capacity = {"source_transient_required_bytes": 10_000}
        fake_usage = type("Usage", (), {"total": 100_000, "used": 95_000, "free": 5_000})()
        with mock.patch.object(engine.shutil, "which", return_value="/usr/bin/tool"), \
             mock.patch.object(engine.shutil, "disk_usage", return_value=fake_usage):
            with self.assertRaisesRegex(engine.ServerMigrationError, "source free disk"):
                engine.source_dependency_preflight(sites, capacity)

    def test_system_cron_user_parser_accepts_env_and_site_user_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "infra"
            path.write_text(
                "MAILTO=\"\"\n"
                "*/5 * * * * kewaro-infra /usr/bin/php8.4 /home/kewaro-infra/htdocs/infra.example/cron.php\n"
                "@reboot kewaro-infra /usr/local/bin/start-infra\n",
                encoding="utf-8",
            )
            self.assertEqual(
                engine.system_cron_job_users(path),
                {"kewaro-infra"},
            )

    def test_system_cron_user_parser_reveals_shared_file_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shared"
            path.write_text(
                "* * * * * alice /usr/local/bin/a\n"
                "* * * * * unrelated /usr/local/bin/b\n",
                encoding="utf-8",
            )
            self.assertEqual(
                engine.system_cron_job_users(path),
                {"alice", "unrelated"},
            )

    def test_source_pm2_runtime_resolution_is_exact_and_bounded_to_one_nvm_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home_root = Path(td) / "home"
            user = "alice"
            version_root = home_root / user / ".nvm/versions/node/v20.17.0"
            pm2 = version_root / "bin/pm2"
            pm2.parent.mkdir(parents=True)
            pm2.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            pm2.chmod(0o755)
            dump = Path(td) / "dump.pm2"
            dump.write_text(
                json.dumps([{"name": "app", "node_version": "20.17.0"}]),
                encoding="utf-8",
            )
            result = engine.resolve_source_pm2_node_runtime(user, dump, home_root)
            self.assertEqual(result, version_root)

    def test_prepare_uses_low_disk_direct_staging_and_never_builds_full_backup_packages(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            backup_builder = mock.Mock(side_effect=AssertionError("full backup package must not be built"))

            def stage_runtime(state):
                state["target_runtime_path"] = "/private/runtime"
                state["target_data_root"] = "/private/data"

            staged: list[str] = []

            def prepare_site(state, site):
                staged.append(site["domain"])
                site["stage_status"] = "DIRECT_STAGED"
                site["mysql_prepare_count"] = len(site.get("mysql_databases", []))

            def stage_runtime_sources(state):
                state["pending_system_cron"] = []
                state["pending_user_cron"] = []
                state["pending_pm2"] = []

            with mock.patch.object(engine, "STATE_ROOT", state_root), \
                 mock.patch.object(engine, "current_inventory", return_value=self.source_inventory()), \
                 mock.patch.object(engine, "validate_full_server_site_set", return_value={"status": "READY"}), \
                 mock.patch.object(engine, "migration_capacity_estimate", return_value={
                     "site_and_external_bytes": 100,
                     "mysql_raw_reference_bytes": 20,
                     "estimated_payload_bytes": 120,
                     "target_required_bytes": 700,
                     "source_transient_required_bytes": 300,
                 }), \
                 mock.patch.object(engine, "ensure_source_rsync_for_prepare", return_value={"status": "READY", "installed": False}), \
                 mock.patch.object(engine, "source_dependency_preflight", return_value={"status": "READY"}), \
                 mock.patch.object(engine, "target_preflight", return_value={"status": "READY"}), \
                 mock.patch.object(engine, "external_paths_for_site", return_value=[]), \
                 mock.patch.object(engine.package_engine, "build_backup", backup_builder), \
                 mock.patch.object(engine, "stage_target_runtime", side_effect=stage_runtime), \
                 mock.patch.object(engine, "prepare_one_site_direct", side_effect=prepare_site), \
                 mock.patch.object(engine, "sync_external_paths", return_value=[]), \
                 mock.patch.object(engine, "sync_sqlite_snapshots", return_value=7), \
                 mock.patch.object(engine, "stage_runtime_sources", side_effect=stage_runtime_sources):
                result = engine.prepare_migration(
                    self.target(), [], "PREPARE_SERVER_MIGRATION"
                )

            self.assertEqual(result["status"], "PREPARED")
            self.assertEqual(result["transfer_mode"], "LOW_DISK_DIRECT_RSYNC")
            self.assertEqual(result["source_full_backup_packages_created"], 0)
            self.assertEqual(result["sqlite_snapshot_count_prepare"], 7)
            self.assertEqual(staged, ["a.example.com", "b.example.com"])
            self.assertTrue(all(site["stage_status"] == "DIRECT_STAGED" for site in result["sites"]))
            backup_builder.assert_not_called()
            saved = json.loads((state_root / result["migration_id"] / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "PREPARED")

    def test_target_database_transaction_marker_is_private_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            state_root = base / "state"
            site_root = base / "home/alice/htdocs/a.example.com"
            site_root.mkdir(parents=True)
            config = site_root / "wp-config.php"
            config.write_text(
                "<?php\n"
                "define('DB_NAME', 'old');\n"
                "define('DB_USER', 'old_user');\n"
                "define('DB_PASSWORD', 'old-pass');\n",
                encoding="utf-8",
            )
            first_dump = base / "first.sql.gz"
            first_dump.write_bytes(b"synthetic")
            second_dump = base / "second.sql.gz"
            second_dump.write_bytes(b"synthetic2")

            with mock.patch.object(engine, "STATE_ROOT", state_root), \
                 mock.patch.object(engine.cloudpanel, "add_database") as add_db, \
                 mock.patch.object(engine.cloudpanel, "import_database") as import_db, \
                 mock.patch.object(engine.site_lifecycle, "cleanup_database", return_value=True) as cleanup_db, \
                 mock.patch.object(engine.os, "chown"):
                first = engine.target_create_database_local(
                    "server-test", "a.example.com", site_root, "adb", 1, first_dump
                )
                second = engine.target_create_database_local(
                    "server-test", "a.example.com", site_root, "adb", 1, second_dump
                )

            self.assertEqual(first["status"], "DATABASE_IMPORTED")
            self.assertFalse(first["resumed"])
            self.assertTrue(second["resumed"])
            self.assertNotIn("password", json.dumps(first).lower())
            self.assertEqual(add_db.call_count, 2)
            self.assertEqual(import_db.call_count, 2)
            cleanup_db.assert_called_once_with("adb", clpctl="clpctl")

            with mock.patch.object(engine, "STATE_ROOT", state_root):
                marker = engine.target_db_marker(
                    "server-test",
                    "a.example.com",
                    "adb",
                    1,
                )
            self.assertTrue(marker.is_file())
            self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
            private = json.loads(marker.read_text(encoding="utf-8"))
            self.assertIn("password", private)
            rewritten = config.read_text(encoding="utf-8")
            self.assertNotIn("old_user", rewritten)
            self.assertNotIn("old-pass", rewritten)

    def test_full_server_multi_database_app_config_remap_fails_closed(self) -> None:
        site = {
            "domain": "multi.example.com",
            "site_user": "alice",
            "mysql_databases": ["one", "two"],
        }
        with self.assertRaisesRegex(
            engine.ServerMigrationError,
            "ambiguous for multi-database site",
        ):
            engine.initial_mysql_sync(
                {"migration_id": "server-test"},
                site,
            )

    def test_final_mysql_sync_rebuilds_transaction_owned_database_before_verify(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": "server-final-db",
                "target": self.target(),
                "sites": [{
                    "domain": "wp.example.com",
                    "site_user": "alice",
                    "site_root": "/home/alice/htdocs/wp.example.com",
                    "mysql_databases": ["wpdb"],
                }],
            }

            remote_calls: list[str] = []

            def fake_remote(_state, command, **_kwargs):
                remote_calls.append(command)
                return subprocess.CompletedProcess([], 0, "", "")

            with mock.patch.object(engine, "STATE_ROOT", state_root), \
                 mock.patch.object(engine.cloudpanel, "export_database"), \
                 mock.patch.object(engine, "rsync_to_target"), \
                 mock.patch.object(
                     engine,
                     "target_create_database",
                     return_value={"status": "DATABASE_IMPORTED"},
                 ) as create_db, \
                 mock.patch.object(engine, "remote", side_effect=fake_remote), \
                 mock.patch.object(
                     engine,
                     "run_local",
                     return_value=subprocess.CompletedProcess([], 0, "", ""),
                 ), \
                 mock.patch.object(
                     engine.verify_engine,
                     "sql_fingerprint",
                     return_value=("same", 1),
                 ):
                count = engine.final_mysql_sync(state)

            self.assertEqual(count, 1)
            create_db.assert_called_once()
            args = create_db.call_args.args
            self.assertEqual(args[2], "wpdb")
            self.assertEqual(args[3], 1)
            self.assertFalse(any("db:import" in command for command in remote_calls))
            self.assertTrue(any("db:export" in command for command in remote_calls))
            self.assertTrue(any("rm -f --" in command for command in remote_calls))

    def test_pre_dns_smoke_defers_only_ssl_config_parity(self) -> None:
        state = {
            "migration_id": "server-smoke",
            "target": self.target(),
            "sites": [{
                "domain": "a.example.com",
                "site_user": "alice",
                "site_root": "/home/alice/htdocs/a.example.com",
            }],
        }
        compare = {
            "status": "FAIL",
            "failures": ["ssl.configured"],
            "unknowns": [],
            "checks": [{
                "field": "ssl.configured",
                "status": "FAIL",
            }],
        }
        target_inventory = {
            "sites": [{
                "domain": "a.example.com",
                "site_user": "alice",
                "site_root": "/home/alice/htdocs/a.example.com",
            }],
        }
        curl_ok = subprocess.CompletedProcess([], 0, "200", "")
        with mock.patch.object(
            engine,
            "remote_inventory",
            return_value=target_inventory,
        ), mock.patch.object(
            engine.cutover,
            "compare_site",
            return_value=compare,
        ), mock.patch.object(
            engine,
            "remote",
            return_value=curl_ok,
        ):
            result = engine.smoke_target(state)

        self.assertEqual(result, {"pass": 1, "fail": 0})
        self.assertEqual(compare["status"], "PASS")
        self.assertEqual(compare["checks"][0]["status"], "DEFERRED")

    def test_source_freeze_resume_finishes_incomplete_system_cron_intent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            state_root = base / "state"
            source = base / "system-cron"
            saved = base / "saved-system-cron"
            source.write_text("* * * * * alice /usr/bin/true\n", encoding="utf-8")
            saved.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            state = {
                "schema": engine.SCHEMA,
                "migration_id": "server-freeze-system",
                "source_nginx_frozen": True,
                "pending_system_cron": [{"source_path": str(source)}],
                "pending_user_cron": [],
                "pending_pm2": [],
                "source_system_cron_saved": [{
                    "source_path": str(source),
                    "saved_file": str(saved),
                    "disable_intent": True,
                    "disabled": False,
                }],
                "source_user_cron_saved": [],
                "source_pm2_stopped": [],
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.freeze_source_runtime(state)

            self.assertFalse(source.exists())
            self.assertTrue(state["source_system_cron_saved"][0]["disabled"])

    def test_source_freeze_resume_finishes_incomplete_user_cron_intent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            state_root = base / "state"
            saved = base / "alice.cron"
            saved.write_text("* * * * * /usr/bin/true\n", encoding="utf-8")
            state = {
                "schema": engine.SCHEMA,
                "migration_id": "server-freeze-user",
                "source_nginx_frozen": True,
                "pending_system_cron": [],
                "pending_user_cron": [{"user": "alice"}],
                "pending_pm2": [],
                "source_system_cron_saved": [],
                "source_user_cron_saved": [{
                    "user": "alice",
                    "saved_file": str(saved),
                    "existed": True,
                    "disable_intent": True,
                    "disabled": False,
                }],
                "source_pm2_stopped": [],
            }
            removed = subprocess.CompletedProcess([], 0, "", "")
            with mock.patch.object(engine, "STATE_ROOT", state_root), \
                 mock.patch.object(engine, "run_local", return_value=removed) as run_local:
                engine.freeze_source_runtime(state)

            self.assertTrue(state["source_user_cron_saved"][0]["disabled"])
            run_local.assert_called_once_with(
                ["crontab", "-u", "alice", "-r"],
                timeout=30,
                check=False,
            )

    def test_source_freeze_resume_finishes_incomplete_pm2_stop_intent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            state_root = base / "state"
            dump = base / "dump.pm2"
            dump.write_text('{"apps":[]}\n', encoding="utf-8")
            state = {
                "schema": engine.SCHEMA,
                "migration_id": "server-freeze-pm2",
                "source_nginx_frozen": True,
                "pending_system_cron": [],
                "pending_user_cron": [],
                "pending_pm2": [{
                    "user": "alice",
                    "source_path": str(dump),
                }],
                "source_system_cron_saved": [],
                "source_user_cron_saved": [],
                "source_pm2_stopped": [{
                    "user": "alice",
                    "source_path": str(dump),
                    "stop_intent": True,
                    "stopped": False,
                }],
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root), \
                 mock.patch.object(
                     engine.runtime_engine,
                     "resolve_site_user_nvm_pm2",
                     return_value=("/home/alice/.nvm/versions/node/v22/bin/pm2", "/usr/bin"),
                 ), \
                 mock.patch.object(
                     engine.runtime_engine,
                     "best_effort_pm2_shutdown",
                     return_value=True,
                 ) as shutdown:
                engine.freeze_source_runtime(state)

            self.assertTrue(state["source_pm2_stopped"][0]["stopped"])
            shutdown.assert_called_once()

    def test_cutover_running_state_resumes_to_dns_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-resume"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "CUTOVER_RUNNING",
                "target": self.target(),
                "sites": [],
                "source_nginx_frozen": True,
                "target_runtime_activated": False,
                "dns_changed_by_p07": False,
                "source_delete_allowed": False,
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(engine, "freeze_source_runtime") as freeze, \
                     mock.patch.object(engine, "sync_site_roots_final") as sync_roots, \
                     mock.patch.object(engine, "sync_external_paths", return_value=[]), \
                     mock.patch.object(engine, "final_mysql_sync", return_value=0), \
                     mock.patch.object(engine, "sync_sqlite_snapshots", return_value=0), \
                     mock.patch.object(engine, "remote_activate_runtime") as activate, \
                     mock.patch.object(engine, "smoke_target", return_value={"pass": 0, "fail": 0}):
                    result = engine.cutover_migration(
                        mid,
                        f"CUTOVER_SERVER:{mid}",
                    )
            self.assertEqual(result["status"], "CUTOVER_PREP_READY")
            freeze.assert_called_once()
            sync_roots.assert_called_once()
            activate.assert_called_once()

    def test_target_runtime_resume_skips_rows_already_activated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": "server-target-runtime",
                "status": "CUTOVER_RUNNING",
                "target": self.target(),
                "sites": [],
                "target_runtime_path": "/private/runtime",
                "pending_user_cron": [{
                    "user": "alice",
                    "staged_target": "/private/user.cron",
                    "activated": True,
                }],
                "pending_pm2": [{
                    "user": "alice",
                    "staged_target": "/private/dump.pm2",
                    "activated": True,
                }],
                "pending_system_cron": [{
                    "source_path": "/etc/cron.d/app",
                    "staged_target": "/private/system.cron",
                    "activated": True,
                }],
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root), \
                 mock.patch.object(engine, "remote") as remote, \
                 mock.patch.object(engine, "target_python") as target_python:
                engine.remote_activate_runtime(state)
            remote.assert_not_called()
            target_python.assert_not_called()
            self.assertTrue(state["target_runtime_activated"])

    def test_target_runtime_rollback_keeps_failed_component_marked_active(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": "server-target-rollback",
                "status": "CUTOVER_RUNNING",
                "target": self.target(),
                "sites": [],
                "target_runtime_path": "/private/runtime",
                "pending_system_cron": [{
                    "source_path": "/etc/cron.d/app",
                    "staged_target": "/private/system.cron",
                    "activated": True,
                }],
                "pending_user_cron": [],
                "pending_pm2": [],
            }
            failed = subprocess.CompletedProcess([], 9, "", "")
            with mock.patch.object(engine, "STATE_ROOT", state_root), \
                 mock.patch.object(engine, "remote", return_value=failed):
                ok = engine.deactivate_target_runtime(state)
            self.assertFalse(ok)
            self.assertTrue(state["pending_system_cron"][0]["activated"])
            self.assertTrue(state["target_runtime_activated"])

    def test_cutover_failure_restores_source_and_does_not_claim_ready(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-test"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "PREPARED",
                "target": self.target(),
                "sites": [],
                "source_nginx_frozen": False,
                "target_runtime_activated": False,
                "dns_changed_by_p07": False,
                "source_delete_allowed": False,
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(engine, "freeze_source_runtime"), \
                     mock.patch.object(engine, "sync_site_roots_final", side_effect=engine.ServerMigrationError("boom")), \
                     mock.patch.object(engine, "deactivate_target_runtime", return_value=True), \
                     mock.patch.object(engine, "restore_source_runtime", return_value=True):
                    with self.assertRaises(engine.ServerMigrationError):
                        engine.cutover_migration(mid, f"CUTOVER_SERVER:{mid}")
                saved = engine.load_state(mid)
            self.assertEqual(saved["status"], "CUTOVER_FAILED_ROLLED_BACK")
            self.assertFalse(saved["source_delete_allowed"])

    def test_managed_ssh_key_cleanup_refuses_unmanaged_identity(self) -> None:
        state = {
            "migration_id": "server-key",
            "target": {
                "identity_file": "/root/.ssh/id_ed25519",
                "managed_identity_file": False,
            },
        }
        result = engine.cleanup_managed_ssh_identity(state)
        self.assertEqual(result["status"], "NOT_MANAGED")
        self.assertFalse(result["remote_key_removed"])
        self.assertFalse(result["local_key_removed"])

    def test_managed_ssh_key_cleanup_removes_only_proven_p07_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            state_root = base / "state"
            identity = base / "vfops-migration-test"
            public = Path(str(identity) + ".pub")
            marker_file = Path(str(identity) + ".vfops-managed")
            identity.write_text("private", encoding="utf-8")
            public.write_text("ssh-ed25519 AAAATEST p07\n", encoding="utf-8")
            marker_file.write_text(
                "VFOPS_MANAGED_MIGRATION_KEY_V1\n",
                encoding="utf-8",
            )
            state = {
                "schema": engine.SCHEMA,
                "migration_id": "server-key",
                "status": "PRODUCTION_PASS",
                "target": {
                    **self.target(),
                    "identity_file": str(identity),
                    "managed_identity_file": True,
                },
            }
            keygen = subprocess.CompletedProcess(
                [],
                0,
                "ssh-ed25519 AAAATEST\n",
                "",
            )
            remote_ok = subprocess.CompletedProcess([], 0, "", "")
            with mock.patch.object(engine, "STATE_ROOT", state_root), \
                 mock.patch.object(engine, "run_local", return_value=keygen), \
                 mock.patch.object(engine, "remote", return_value=remote_ok) as remote:
                engine.save_state(state)
                result = engine.cleanup_managed_ssh_identity(state)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["remote_key_removed"])
            self.assertTrue(result["local_key_removed"])
            self.assertFalse(identity.exists())
            self.assertFalse(public.exists())
            self.assertFalse(marker_file.exists())
            remote.assert_called_once()

    def test_managed_ssh_key_cleanup_retry_after_remote_remove_is_local_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            state_root = base / "state"
            identity = base / "vfops-migration-retry"
            public = Path(str(identity) + ".pub")
            marker_file = Path(str(identity) + ".vfops-managed")
            for path, text in (
                (identity, "private"),
                (public, "ssh-ed25519 AAAATEST p07\n"),
                (marker_file, "VFOPS_MANAGED_MIGRATION_KEY_V1\n"),
            ):
                path.write_text(text, encoding="utf-8")

            state = {
                "schema": engine.SCHEMA,
                "migration_id": "server-key-retry",
                "status": "PRODUCTION_PASS",
                "target": {
                    **self.target(),
                    "identity_file": str(identity),
                    "managed_identity_file": True,
                },
                "managed_ssh_key_cleanup": "REMOTE_REMOVED",
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root), \
                 mock.patch.object(engine, "remote") as remote, \
                 mock.patch.object(engine, "run_local") as run_local:
                engine.save_state(state)
                result = engine.cleanup_managed_ssh_identity(state)

            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["remote_key_removed"])
            self.assertTrue(result["local_key_removed"])
            self.assertFalse(identity.exists())
            self.assertFalse(public.exists())
            self.assertFalse(marker_file.exists())
            remote.assert_not_called()
            run_local.assert_not_called()

    def test_partial_local_key_cleanup_still_closes_remote_rollback_channel(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-key-partial"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "PRODUCTION_PASS",
                "target": {
                    **self.target(),
                    "identity_file": "/root/.ssh/vfops-migration-test",
                    "managed_identity_file": True,
                },
                "managed_ssh_key_cleanup": "RETAINED_FOR_RECOVERY",
                "recovery_protection_key_active": True,
                "target_staging_cleanup": "PASS",
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(
                    engine,
                    "cleanup_managed_ssh_identity",
                    return_value={
                        "status": "LOCAL_REMOVE_PARTIAL",
                        "remote_key_removed": True,
                        "local_key_removed": False,
                    },
                ):
                    result = engine.cleanup_managed_key_after_recovery_window(
                        mid,
                        f"CLEANUP_MANAGED_SSH_KEY:{mid}",
                    )

            self.assertFalse(result["recovery_protection_key_active"])
            self.assertIsNotNone(result["recovery_protection_key_closed_at"])
            self.assertEqual(
                result["managed_ssh_key_cleanup_result"]["status"],
                "LOCAL_REMOVE_PARTIAL",
            )

    def test_finalize_retains_managed_key_for_recovery_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-key-window"
            target = self.target()
            target["identity_file"] = "/root/.ssh/vfops-migration-test"
            target["managed_identity_file"] = True
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "CUTOVER_PREP_READY",
                "target": target,
                "sites": [],
                "source_delete_allowed": False,
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(
                    engine, "public_route_proof",
                    return_value={"status": "PASS", "pass": 0, "fail": 0, "pending": []},
                ), mock.patch.object(
                    engine, "public_production_check",
                    return_value={"status": "PASS", "site_pass": 0, "site_fail": 0, "failures": []},
                ), mock.patch.object(engine, "cleanup_target_staging"):
                    result = engine.finalize_migration(
                        mid,
                        f"DNS_UPDATED:{mid}",
                        attempts=1,
                        delay=0,
                    )
            self.assertEqual(result["status"], "PRODUCTION_PASS")
            self.assertEqual(
                result["managed_ssh_key_cleanup"],
                "RETAINED_FOR_RECOVERY",
            )
            self.assertTrue(result["recovery_protection_key_active"])

    def test_cleanup_managed_key_requires_exact_gate_and_closes_recovery_channel(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-key-close"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "PRODUCTION_PASS",
                "target": {
                    **self.target(),
                    "identity_file": "/root/.ssh/vfops-migration-test",
                    "managed_identity_file": True,
                },
                "managed_ssh_key_cleanup": "RETAINED_FOR_RECOVERY",
                "recovery_protection_key_active": True,
                "target_staging_cleanup": "PASS",
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(
                    engine,
                    "cleanup_managed_ssh_identity",
                    return_value={
                        "status": "PASS",
                        "remote_key_removed": True,
                        "local_key_removed": True,
                    },
                ) as cleanup:
                    with self.assertRaisesRegex(
                        engine.ServerMigrationError,
                        "explicit confirmation required",
                    ):
                        engine.cleanup_managed_key_after_recovery_window(
                            mid,
                            "NO",
                        )
                    cleanup.assert_not_called()

                    result = engine.cleanup_managed_key_after_recovery_window(
                        mid,
                        f"CLEANUP_MANAGED_SSH_KEY:{mid}",
                    )

            self.assertFalse(result["recovery_protection_key_active"])
            self.assertIsNotNone(result["recovery_protection_key_closed_at"])
            self.assertEqual(
                result["managed_ssh_key_cleanup_result"]["status"],
                "PASS",
            )

    def test_post_dns_rollback_is_denied_without_reverse_data_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-post-dns"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "PRODUCTION_PASS",
                "target": self.target(),
                "source_delete_allowed": False,
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(engine, "deactivate_target_runtime") as deactivate, \
                     mock.patch.object(engine, "restore_source_runtime") as restore:
                    with self.assertRaisesRegex(
                        engine.ServerMigrationError,
                        "post-DNS rollback requires TARGET-to-SOURCE data reconciliation",
                    ):
                        engine.rollback_migration(
                            mid,
                            f"ROLLBACK_SERVER:{mid}",
                        )
                    deactivate.assert_not_called()
                    restore.assert_not_called()

    def test_pre_dns_cutover_ready_can_rollback_runtime_safely(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-pre-dns"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "CUTOVER_PREP_READY",
                "target": self.target(),
                "source_delete_allowed": False,
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(
                    engine, "deactivate_target_runtime", return_value=True
                ) as deactivate, mock.patch.object(
                    engine, "restore_source_runtime", return_value=True
                ) as restore:
                    result = engine.rollback_migration(
                        mid,
                        f"ROLLBACK_SERVER:{mid}",
                    )
            self.assertEqual(result["status"], "ROLLED_BACK")
            self.assertTrue(result["target_sites_retained"])
            self.assertTrue(result["dns_rollback_required_if_already_changed"])
            deactivate.assert_called_once()
            restore.assert_called_once()

    def test_public_production_check_rejects_reactivated_source_cron_and_pm2(self) -> None:
        state = {
            "migration_id": "server-source-runtime",
            "target": self.target(),
            "sites": [{"domain": "a.example.com"}],
            "source_system_cron_saved": [],
            "pending_user_cron": [{"user": "alice"}],
            "pending_pm2": [{"user": "alice"}],
        }

        def fake_run(args, **_kwargs):
            if args[0] == "curl":
                return subprocess.CompletedProcess([], 0, "200|0|203.0.113.20", "")
            if args[:3] == ["systemctl", "is-active", "nginx"]:
                return subprocess.CompletedProcess([], 3, "inactive", "")
            return subprocess.CompletedProcess([], 0, "", "")

        with mock.patch.object(engine, "run_local", side_effect=fake_run), \
             mock.patch.object(
                 engine.runtime_engine,
                 "current_crontab",
                 return_value=(True, "* * * * * /usr/bin/true\n"),
             ), \
             mock.patch.object(
                 engine,
                 "source_pm2_daemon_present",
                 return_value=True,
             ):
            result = engine.public_production_check(state)

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("SOURCE_USER_CRON_ACTIVE:alice", result["failures"])
        self.assertIn("SOURCE_PM2_ACTIVE:alice", result["failures"])

    def test_finalize_waits_for_dns_without_false_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-test"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "CUTOVER_PREP_READY",
                "target": self.target(),
                "sites": [],
                "source_delete_allowed": False,
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(
                    engine,
                    "public_route_proof",
                    return_value={"status": "WAITING_DNS", "pass": 1, "fail": 1, "pending": ["b.example.com"]},
                ), mock.patch.object(engine, "public_production_check") as production:
                    result = engine.finalize_migration(
                        mid, f"DNS_UPDATED:{mid}", attempts=1, delay=0
                    )
                saved = engine.load_state(mid)
            self.assertEqual(result["status"], "WAITING_DNS")
            self.assertEqual(saved["status"], "WAITING_DNS")
            production.assert_not_called()

    def test_finalize_keeps_production_pass_when_target_staging_cleanup_needs_retry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-prod-cleanup"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "CUTOVER_PREP_READY",
                "target": self.target(),
                "sites": [],
                "source_delete_allowed": False,
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(
                    engine,
                    "public_route_proof",
                    return_value={
                        "status": "PASS",
                        "pass": 0,
                        "fail": 0,
                        "pending": [],
                    },
                ), mock.patch.object(
                    engine,
                    "public_production_check",
                    return_value={
                        "status": "PASS",
                        "site_pass": 0,
                        "site_fail": 0,
                        "failures": [],
                    },
                ), mock.patch.object(
                    engine,
                    "cleanup_target_staging",
                    return_value=False,
                ):
                    result = engine.finalize_migration(
                        mid,
                        f"DNS_UPDATED:{mid}",
                        attempts=1,
                        delay=0,
                    )
                    saved = engine.load_state(mid)

            self.assertEqual(result["status"], "PRODUCTION_PASS")
            self.assertEqual(saved["status"], "PRODUCTION_PASS")
            self.assertEqual(
                saved["target_staging_cleanup"],
                "RETRY_REQUIRED",
            )

    def test_recovery_key_cleanup_refuses_when_target_staging_is_not_clean(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-recovery-staging-block"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "PRODUCTION_PASS",
                "target": {
                    **self.target(),
                    "identity_file": "/root/.ssh/vfops-migration-test",
                    "managed_identity_file": True,
                },
                "target_staging_cleanup": "RETRY_REQUIRED",
                "managed_ssh_key_cleanup": "RETAINED_FOR_RECOVERY",
                "recovery_protection_key_active": True,
            }

            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(
                    engine,
                    "cleanup_target_staging",
                    return_value=False,
                ), mock.patch.object(
                    engine,
                    "cleanup_managed_ssh_identity",
                ) as cleanup_key:
                    with self.assertRaisesRegex(
                        engine.ServerMigrationError,
                        "private staging cleanup must pass",
                    ):
                        engine.cleanup_managed_key_after_recovery_window(
                            mid,
                            f"CLEANUP_MANAGED_SSH_KEY:{mid}",
                        )
                    cleanup_key.assert_not_called()
                saved = engine.load_state(mid)

            self.assertEqual(
                saved["target_staging_cleanup"],
                "RETRY_REQUIRED",
            )
            self.assertTrue(saved["recovery_protection_key_active"])

    def test_recovery_key_cleanup_retries_target_staging_before_key_removal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-recovery-cleanup"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "PRODUCTION_PASS",
                "target": {
                    **self.target(),
                    "identity_file": "/root/.ssh/vfops-migration-test",
                    "managed_identity_file": True,
                },
                "target_staging_cleanup": "RETRY_REQUIRED",
                "managed_ssh_key_cleanup": "RETAINED_FOR_RECOVERY",
                "recovery_protection_key_active": True,
            }
            events: list[str] = []

            def cleanup_staging(_state):
                events.append("staging")
                return True

            def cleanup_key(_state):
                events.append("key")
                return {
                    "status": "PASS",
                    "remote_key_removed": True,
                    "local_key_removed": True,
                }

            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(
                    engine,
                    "cleanup_target_staging",
                    side_effect=cleanup_staging,
                ), mock.patch.object(
                    engine,
                    "cleanup_managed_ssh_identity",
                    side_effect=cleanup_key,
                ):
                    result = engine.cleanup_managed_key_after_recovery_window(
                        mid,
                        f"CLEANUP_MANAGED_SSH_KEY:{mid}",
                    )

            self.assertEqual(events, ["staging", "key"])
            self.assertEqual(result["target_staging_cleanup"], "PASS")
            self.assertFalse(result["recovery_protection_key_active"])

    def test_finalize_production_pass_keeps_source_as_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mid = "server-test"
            state = {
                "schema": engine.SCHEMA,
                "migration_id": mid,
                "status": "CUTOVER_PREP_READY",
                "target": self.target(),
                "sites": [],
                "source_delete_allowed": False,
            }
            with mock.patch.object(engine, "STATE_ROOT", state_root):
                engine.save_state(state)
                with mock.patch.object(
                    engine, "public_route_proof",
                    return_value={"status": "PASS", "pass": 2, "fail": 0, "pending": []},
                ), mock.patch.object(
                    engine, "public_production_check",
                    return_value={"status": "PASS", "site_pass": 2, "site_fail": 0, "failures": []},
                ), mock.patch.object(engine, "cleanup_target_staging"):
                    result = engine.finalize_migration(
                        mid, f"DNS_UPDATED:{mid}", attempts=1, delay=0
                    )
            self.assertEqual(result["status"], "PRODUCTION_PASS")
            self.assertTrue(result["source_retained_for_rollback"])
            self.assertFalse(result["source_delete_allowed"])
            self.assertFalse(result["dns_changed_by_p07"])


if __name__ == "__main__":
    unittest.main()
