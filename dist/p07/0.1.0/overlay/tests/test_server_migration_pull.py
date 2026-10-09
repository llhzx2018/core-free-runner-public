from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"

spec = importlib.util.spec_from_file_location(
    "server_migration_pull",
    LIB / "server_migration_pull.py",
)
assert spec and spec.loader
pull = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pull)


class TargetPullContractTests(unittest.TestCase):
    def setUp(self) -> None:
        # Other migration tests exercise workflow invariants in a MariaDB target
        # fixture; negative daemon/version cases are separately tested below.
        patcher = mock.patch.object(
            pull, "local_target_db_engine_version", return_value="MARIADB_10.11"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_wrong_target_engine_fails_without_inventory_mutation(self) -> None:
        with mock.patch.object(pull, "cloudpanel_ready_local", return_value=True), \
             mock.patch.object(pull, "cloudpanel_database_server_ready_local", return_value=True), \
             mock.patch.object(pull, "local_target_db_engine_version", return_value="MYSQL_OR_PERCONA"), \
             mock.patch.object(pull.inventory, "build_manifest") as inventory:
            with self.assertRaisesRegex(
                pull.PullMigrationError, "NEW_SERVER_REQUIRES_MARIADB_10_11"
            ):
                pull.target_preflight_local({"sites": []})
            inventory.assert_not_called()

    def test_progress_note_is_opt_in_and_secret_free_channel(self) -> None:
        import io
        from contextlib import redirect_stderr
        buf = io.StringIO()
        with mock.patch.dict(pull.os.environ, {"VFOPS_MIGRATION_PROGRESS": "1"}, clear=False), redirect_stderr(buf):
            pull.progress_note("2/7 · 网站 1/16 · example.com")
        self.assertIn("迁移阶段：2/7 · 网站 1/16 · example.com", buf.getvalue())

        silent = io.StringIO()
        with mock.patch.dict(pull.os.environ, {"VFOPS_MIGRATION_PROGRESS": "0"}, clear=False), redirect_stderr(silent):
            pull.progress_note("should-not-print")
        self.assertEqual(silent.getvalue(), "")

    def test_structured_progress_event_keeps_phase_and_item_counts(self) -> None:
        event = pull.migration_progress_event(
            "2/7 · 网站 3/16 · press.example.test"
        )
        self.assertEqual(
            event["schema"],
            "vf-server-ops.migration-progress.v1",
        )
        self.assertEqual(event["kind"], "MIGRATION_PROGRESS")
        self.assertEqual(event["phase_step"], 2)
        self.assertEqual(event["phase_total"], 7)
        self.assertEqual(event["item_current"], 3)
        self.assertEqual(event["item_total"], 16)
        self.assertEqual(event["scope"], "SITE_FILES")
        self.assertEqual(
            event["message"],
            "2/7 · 网站 3/16 · press.example.test",
        )

    def test_progress_note_jsonl_is_opt_in_and_default_text_stays_compatible(self) -> None:
        import io
        from contextlib import redirect_stderr

        structured = io.StringIO()
        with mock.patch.dict(
            pull.os.environ,
            {
                "VFOPS_MIGRATION_PROGRESS": "1",
                "VFOPS_MIGRATION_PROGRESS_FORMAT": "jsonl",
            },
            clear=False,
        ), redirect_stderr(structured):
            pull.progress_note("5/7 · 正在生成并同步 SQLite 一致性快照")

        event = json.loads(structured.getvalue())
        self.assertEqual(event["phase_step"], 5)
        self.assertEqual(event["phase_total"], 7)
        self.assertEqual(event["scope"], "SQLITE")
        self.assertEqual(
            event["message"],
            "5/7 · 正在生成并同步 SQLite 一致性快照",
        )

        text_output = io.StringIO()
        with mock.patch.dict(
            pull.os.environ,
            {
                "VFOPS_MIGRATION_PROGRESS": "1",
                "VFOPS_MIGRATION_PROGRESS_FORMAT": "text",
            },
            clear=False,
        ), redirect_stderr(text_output):
            pull.progress_note("5/7 · 正在生成并同步 SQLite 一致性快照")

        self.assertEqual(
            text_output.getvalue(),
            "迁移阶段：5/7 · 正在生成并同步 SQLite 一致性快照\n",
        )

    def test_migration_state_transition_guard_accepts_existing_runtime_paths(self) -> None:
        state = {"status": "PREPARE_FAILED"}
        pull.transition_migration_status(state, "PREPARING")
        pull.transition_migration_status(state, "PREPARED")
        pull.transition_migration_status(state, "CUTOVER_RUNNING")
        pull.transition_migration_status(state, "CUTOVER_PREP_READY")
        pull.transition_migration_status(state, "WAITING_DNS")
        pull.transition_migration_status(state, "PRODUCTION_PASS")
        self.assertEqual(state["status"], "PRODUCTION_PASS")

    def test_migration_state_transition_guard_rejects_skip_and_terminal_reopen(self) -> None:
        state = {"status": "PREPARED"}
        with self.assertRaisesRegex(
            pull.PullMigrationError,
            "invalid migration status transition: PREPARED -> PRODUCTION_PASS",
        ):
            pull.transition_migration_status(state, "PRODUCTION_PASS")
        self.assertEqual(state["status"], "PREPARED")

        terminal = {"status": "PRODUCTION_PASS"}
        with self.assertRaisesRegex(
            pull.PullMigrationError,
            "invalid migration status transition: PRODUCTION_PASS -> CUTOVER_RUNNING",
        ):
            pull.transition_migration_status(terminal, "CUTOVER_RUNNING")
        self.assertEqual(terminal["status"], "PRODUCTION_PASS")

    def test_migration_state_transition_guard_preserves_failure_recovery_paths(self) -> None:
        prepared = {"status": "PREPARED"}
        pull.transition_migration_status(prepared, "PREPARE_FAILED")
        self.assertEqual(prepared["status"], "PREPARE_FAILED")

        cutover_ready = {"status": "CUTOVER_PREP_READY"}
        pull.transition_migration_status(
            cutover_ready,
            "CUTOVER_FAILED_ROLLED_BACK",
        )
        self.assertEqual(
            cutover_ready["status"],
            "CUTOVER_FAILED_ROLLED_BACK",
        )

        cutover_ready_partial = {"status": "CUTOVER_PREP_READY"}
        pull.transition_migration_status(
            cutover_ready_partial,
            "CUTOVER_FAILED_ROLLBACK_PARTIAL",
        )
        self.assertEqual(
            cutover_ready_partial["status"],
            "CUTOVER_FAILED_ROLLBACK_PARTIAL",
        )

    def test_cloudpanel_database_server_readiness_requires_active_default_record(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sq3"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE database_server ("
                "id INTEGER PRIMARY KEY, is_active INTEGER, is_default INTEGER, "
                "host TEXT, user_name TEXT, password TEXT)"
            )
            conn.commit()
            self.assertFalse(pull.cloudpanel_database_server_ready_local(db))
            conn.execute(
                "INSERT INTO database_server "
                "(id,is_active,is_default,host,user_name,password) "
                "VALUES (1,1,1,'127.0.0.1','root','encrypted')"
            )
            conn.commit()
            conn.close()
            self.assertTrue(pull.cloudpanel_database_server_ready_local(db))

    def test_cloudpanel_user_count_models_first_admin_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sq3"
            conn = sqlite3.connect(db)
            conn.execute('CREATE TABLE "user" (id INTEGER PRIMARY KEY, user_name TEXT)')
            conn.commit()
            self.assertEqual(pull.cloudpanel_user_count_local(db), 0)
            conn.execute('INSERT INTO "user" (id,user_name) VALUES (1, "admin")')
            conn.commit()
            conn.close()
            self.assertEqual(pull.cloudpanel_user_count_local(db), 1)

    def test_resume_fails_before_more_writes_when_cloudpanel_database_server_missing(self) -> None:
        state = {"migration_id": "pull-20261005T000000Z-deadbeef", "status": "PREPARE_FAILED"}
        with mock.patch.object(pull, "load_state", return_value=state), mock.patch.object(
            pull, "cloudpanel_database_server_ready_local", return_value=False
        ), mock.patch.object(pull, "save_state") as save:
            with self.assertRaisesRegex(pull.PullMigrationError, "database server metadata is missing"):
                pull.resume_prepare_migration(state["migration_id"])
        save.assert_not_called()

    def test_plan_is_current_server_receiver_and_old_server_is_source(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "managed_identity_file": False,
            "ssh": "ssh",
        }
        source_plan = {
            "status": "READY",
            "source_server_identity": "sha256:old",
            "sites": [{"domain": "example.com"}],
            "capacity_estimate": {"target_required_bytes": 1},
            "source_external_listeners": [],
        }
        with mock.patch.object(pull, "source_probe", return_value=source_plan), mock.patch.object(
            pull,
            "target_preflight_local",
            return_value={"status": "READY", "target_identity": "sha256:new"},
        ):
            result = pull.plan_payload(source, [])
        self.assertEqual(result["migration_direction"], "CURRENT_SERVER_PULLS_OLD_SERVER")
        self.assertEqual(result["current_server_role"], "RECEIVER")
        self.assertEqual(result["old_server_ip"], "192.0.2.10")
        self.assertFalse(result["automatic_dns_change"])
        self.assertFalse(result["old_server_delete_allowed"])
        self.assertFalse(result["existing_target_overwrite_allowed"])
        self.assertNotIn("target_ip", result)

    def test_rsync_business_data_direction_is_remote_old_to_local_new(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "ssh": "ssh",
        }
        with tempfile.TemporaryDirectory() as td, mock.patch.object(
            pull, "run_local"
        ) as run:
            target = Path(td)
            pull.pull_path(source, "/home/site/htdocs/example.com/", target)
            args = run.call_args.args[0]
        self.assertIn("root@192.0.2.10:/home/site/htdocs/example.com/", args)
        self.assertEqual(args[-1], str(target))
        remote_index = args.index("root@192.0.2.10:/home/site/htdocs/example.com/")
        self.assertLess(remote_index, len(args) - 1)

    def test_rsync_progress_streams_when_enabled(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "ssh": "ssh",
        }
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            pull.os.environ, {"VFOPS_MIGRATION_PROGRESS": "1"}, clear=False
        ), mock.patch.object(pull, "run_local") as run:
            pull.pull_path(source, "/home/site/htdocs/example.com/", Path(td))
        args = run.call_args.args[0]
        self.assertIn("--info=progress2,stats2", args)
        self.assertIn("--human-readable", args)
        self.assertTrue(run.call_args.kwargs["stream_to_stderr"])

    def test_rsync_file_source_does_not_gain_trailing_slash_from_local_directory(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "ssh": "ssh",
        }
        with tempfile.TemporaryDirectory() as td, mock.patch.object(
            pull, "run_local"
        ) as run:
            target = Path(td)
            pull.pull_path(source, "/home/site/.vf-file-marker", target)
            args = run.call_args.args[0]
        self.assertIn("root@192.0.2.10:/home/site/.vf-file-marker", args)
        self.assertNotIn("root@192.0.2.10:/home/site/.vf-file-marker/", args)

    def test_external_file_resume_removes_only_empty_release62_placeholder(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "ssh": "ssh",
        }
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / ".vf-file-marker"
            target.mkdir()
            state = {
                "source": source,
                "external_assets": [{"path": str(target), "user": "site"}],
            }
            with mock.patch.object(
                pull, "ensure_local_parent"
            ), mock.patch.object(
                pull, "source_path_kind", return_value="FILE"
            ), mock.patch.object(
                pull, "pull_path"
            ) as transfer:
                result = pull.sync_external_assets(state, final=False)

            self.assertFalse(target.exists())
            self.assertEqual(result, [str(target)])
            self.assertEqual(state["external_assets"][0]["kind"], "FILE")
            transfer.assert_called_once_with(
                source,
                str(target),
                target,
                user="site",
                delete=False,
            )

    def test_external_file_resume_refuses_nonempty_directory_conflict(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "ssh": "ssh",
        }
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / ".vf-file-marker"
            target.mkdir()
            (target / "unexpected").write_text("keep", encoding="utf-8")
            state = {
                "source": source,
                "external_assets": [{"path": str(target), "user": "site"}],
            }
            with mock.patch.object(
                pull, "ensure_local_parent"
            ), mock.patch.object(
                pull, "source_path_kind", return_value="FILE"
            ), mock.patch.object(
                pull, "pull_path"
            ) as transfer:
                with self.assertRaisesRegex(
                    pull.PullMigrationError,
                    "external target type conflict",
                ):
                    pull.sync_external_assets(state, final=False)

            self.assertTrue(target.is_dir())
            self.assertTrue((target / "unexpected").is_file())
            transfer.assert_not_called()

    def test_refresh_external_assets_merges_new_hidden_runtime_into_existing_task(self) -> None:
        state = {
            "source_server_identity": "sha256:old",
            "source": {"host": "192.0.2.10"},
            "sites": [{
                "domain": "press.example.com",
                "site_user": "press-user",
            }],
            "external_assets": [{
                "path": "/home/press-user/.vf-token",
                "user": "press-user",
            }],
        }
        plan = {
            "source_server_identity": "sha256:old",
            "sites": [{
                "domain": "press.example.com",
                "site_user": "press-user",
            }],
            "external_assets": [
                {
                    "path": "/home/press-user/.vf-token",
                    "user": "press-user",
                    "reason": "SITE_USER_HOME",
                },
                {
                    "path": "/home/press-user/htdocs/.press.example.com-vfpress-runtime",
                    "user": "press-user",
                    "reason": "WEBROOT_SIBLING",
                },
                {
                    "path": "/home/press-user/htdocs/.press.example.com-vfpress-data",
                    "user": "press-user",
                    "reason": "WEBROOT_SIBLING",
                },
            ],
            "sqlite_assets": [],
            "runtime_assets": {},
            "source_external_listeners": [],
        }
        with mock.patch.object(
            pull, "source_probe", return_value=plan
        ) as probe, mock.patch.object(
            pull, "save_state"
        ) as save:
            added = pull.refresh_external_assets_from_source(state)

        self.assertEqual(added, 2)
        self.assertEqual(len(state["external_assets"]), 3)
        self.assertIn(
            "/home/press-user/htdocs/.press.example.com-vfpress-runtime",
            {row["path"] for row in state["external_assets"]},
        )
        runtime_row = next(
            row for row in state["external_assets"]
            if row["path"].endswith("-vfpress-runtime")
        )
        self.assertEqual(runtime_row["reason"], "WEBROOT_SIBLING")
        probe.assert_called_once_with(state["source"], ["press.example.com"])
        save.assert_called_once_with(state)

    def test_release68_press_field_regression_fixture_closes_original_gap(self) -> None:
        fixture = json.loads(
            (
                ROOT
                / "tests"
                / "fixtures"
                / "release68_press_webroot_sibling_regression.json"
            ).read_text(encoding="utf-8")
        )
        site_meta = fixture["site"]
        user = site_meta["site_user"]
        domain = site_meta["domain"]
        canonical_site_root = f"/home/{user}/htdocs/{domain}"
        canonical_site = {
            **site_meta,
            "site_root": canonical_site_root,
            "document_root": canonical_site_root,
        }
        canonical_external = [
            {
                "path": f"/home/{user}/htdocs/{row['name']}",
                "user": user,
                "reason": row["reason"],
            }
            for row in fixture["hidden_siblings"]
        ]
        sqlite_meta = fixture["sqlite"]
        canonical_sqlite = (
            f"/home/{user}/htdocs/{sqlite_meta['parent']}/{sqlite_meta['name']}"
        )
        state = {
            "source_server_identity": fixture["source_identity"],
            "source": {"host": "192.0.2.10"},
            "sites": [dict(canonical_site)],
            "external_assets": [],
            "sqlite_assets": [],
            "runtime_assets": {
                "system_cron": [],
                "user_cron": [],
                "pm2": [],
            },
            "source_external_listeners": [],
        }
        plan = {
            "source_server_identity": fixture["source_identity"],
            "sites": [dict(canonical_site)],
            "external_assets": canonical_external,
            "sqlite_assets": [{
                "path": canonical_sqlite,
                "user": user,
                "mode": sqlite_meta["mode"],
            }],
            "runtime_assets": {
                "system_cron": [],
                "user_cron": [],
                "pm2": [],
            },
            "source_external_listeners": [],
        }

        with mock.patch.object(
            pull, "source_probe", return_value=plan
        ), mock.patch.object(
            pull, "save_state"
        ):
            refreshed = pull.refresh_migration_assets_from_source(state)

        self.assertEqual(refreshed["external_added"], 2)
        self.assertEqual(refreshed["sqlite_added"], 1)
        self.assertEqual(
            {row["reason"] for row in state["external_assets"]},
            {"WEBROOT_SIBLING"},
        )
        self.assertIn(
            f"/home/{user}/htdocs/{fixture['hidden_siblings'][0]['name']}",
            refreshed["external_added_paths"],
        )
        self.assertIn(canonical_sqlite, refreshed["sqlite_added_paths"])

        with tempfile.TemporaryDirectory() as td:
            home_root = Path(td) / "home"
            home = home_root / user
            site_root = home / "htdocs" / domain
            site_root.mkdir(parents=True)

            local_assets = {}
            for row in fixture["hidden_siblings"]:
                path = site_root.parent / row["name"]
                path.mkdir()
                local_assets[row["name"]] = path

            sqlite_path = (
                site_root.parent / sqlite_meta["parent"] / sqlite_meta["name"]
            )
            conn = sqlite3.connect(sqlite_path)
            conn.execute("CREATE TABLE regression_fixture(id INTEGER PRIMARY KEY)")
            conn.commit()
            conn.close()

            discovered = pull.legacy.external_assets_for_site(
                {
                    **site_meta,
                    "site_root": str(site_root),
                    "document_root": str(site_root),
                },
                home_root,
            )
            discovered_reasons = {
                Path(row["path"]).name: row["reason"]
                for row in discovered
            }
            for row in fixture["hidden_siblings"]:
                self.assertEqual(
                    discovered_reasons[row["name"]],
                    row["reason"],
                )

            runtime_name = fixture["hidden_siblings"][0]["name"]
            runtime_path = local_assets[runtime_name]
            runtime_path.rmdir()

            reconcile_state = {
                "source": {"host": "192.0.2.10"},
                "sites": [{
                    **site_meta,
                    "site_root": str(site_root),
                    "document_root": str(site_root),
                    "stage_status": "PULLED_STAGED",
                }],
                "external_assets": [
                    {
                        "path": str(local_assets[row["name"]]),
                        "user": user,
                        "reason": row["reason"],
                        "kind": row["kind"],
                    }
                    for row in fixture["hidden_siblings"]
                ],
                "sqlite_assets": [{
                    "path": str(sqlite_path),
                    "user": user,
                    "mode": sqlite_meta["mode"],
                }],
                "runtime_assets": {
                    "system_cron": [],
                    "user_cron": [],
                    "pm2": [],
                },
                "pending_system_cron": [],
                "pending_user_cron": [],
                "pending_pm2": [],
                "source_http_baseline_required": True,
                "source_http_baseline": {
                    domain: {
                        "status": "PASS",
                        "http_code": fixture["http"]["source"],
                        "family": "SUCCESS_OR_REDIRECT",
                    }
                },
            }

            missing = pull.pre_cutover_reconcile(
                reconcile_state,
                home_root=home_root,
            )
            self.assertEqual(missing["status"], "FAIL")
            self.assertIn(
                f"EXTERNAL_DIRECTORY_MISSING:{runtime_path}",
                missing["failures"],
            )

            runtime_path.mkdir()
            complete = pull.pre_cutover_reconcile(
                reconcile_state,
                home_root=home_root,
            )
            self.assertEqual(complete["status"], "PASS")
            self.assertEqual(complete["failures"], [])

        self.assertFalse(
            pull.http_baseline_compatible(
                fixture["http"]["source"],
                fixture["http"]["bad_target"],
            )
        )
        self.assertTrue(
            pull.http_baseline_compatible(
                fixture["http"]["source"],
                fixture["http"]["good_target"],
            )
        )

    def test_refresh_migration_assets_adds_sqlite_and_runtime_changes(self) -> None:
        state = {
            "source_server_identity": "sha256:old",
            "source": {"host": "192.0.2.10"},
            "sites": [{
                "domain": "press.example.com",
                "site_user": "press-user",
            }],
            "external_assets": [],
            "sqlite_assets": [],
            "runtime_assets": {
                "system_cron": [],
                "user_cron": [],
                "pm2": [],
            },
            "source_external_listeners": [],
        }
        plan = {
            "source_server_identity": "sha256:old",
            "sites": [{
                "domain": "press.example.com",
                "site_user": "press-user",
            }],
            "external_assets": [],
            "sqlite_assets": [{
                "path": "/home/press-user/htdocs/.press.example-data/app.db",
                "user": "press-user",
                "mode": 0o600,
            }],
            "runtime_assets": {
                "system_cron": [],
                "user_cron": [{
                    "path": "/var/spool/cron/crontabs/press-user",
                    "user": "press-user",
                }],
                "pm2": [],
            },
            "source_external_listeners": [{"protocol": "tcp", "port": 8080}],
        }

        with mock.patch.object(
            pull, "source_probe", return_value=plan
        ), mock.patch.object(
            pull, "save_state"
        ) as save:
            result = pull.refresh_migration_assets_from_source(state)

        self.assertEqual(result["external_added"], 0)
        self.assertEqual(result["sqlite_added"], 1)
        self.assertTrue(result["runtime_assets_changed"])
        self.assertEqual(
            state["sqlite_assets"][0]["path"],
            "/home/press-user/htdocs/.press.example-data/app.db",
        )
        self.assertEqual(len(state["runtime_assets"]["user_cron"]), 1)
        self.assertEqual(
            state["source_external_listeners"],
            [{"protocol": "tcp", "port": 8080}],
        )
        save.assert_called_once_with(state)

    def test_refresh_migration_assets_blocks_selected_site_structure_drift(self) -> None:
        state = {
            "source_server_identity": "sha256:old",
            "source": {"host": "192.0.2.10"},
            "sites": [{
                "domain": "example.com",
                "site_user": "site",
                "site_root": "/home/site/htdocs/example.com",
                "document_root": "/home/site/htdocs/example.com",
                "runtime": {"type": "php", "version": "8.4"},
                "mysql_databases": ["old_db"],
            }],
            "external_assets": [],
            "sqlite_assets": [],
            "runtime_assets": {},
        }
        plan = {
            "source_server_identity": "sha256:old",
            "sites": [{
                "domain": "example.com",
                "site_user": "site",
                "site_root": "/home/site/htdocs/example.com",
                "document_root": "/home/site/htdocs/example.com",
                "runtime": {"type": "php", "version": "8.4"},
                "mysql_databases": ["new_db"],
            }],
            "external_assets": [],
            "sqlite_assets": [],
            "runtime_assets": {},
        }

        with mock.patch.object(pull, "source_probe", return_value=plan):
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "structure changed",
            ):
                pull.refresh_migration_assets_from_source(state)

    def test_refresh_external_assets_rejects_changed_source_identity(self) -> None:
        state = {
            "source_server_identity": "sha256:old",
            "source": {"host": "192.0.2.10"},
            "sites": [{"domain": "press.example.com", "site_user": "press-user"}],
            "external_assets": [],
        }
        with mock.patch.object(
            pull,
            "source_probe",
            return_value={
                "source_server_identity": "sha256:different",
                "external_assets": [],
            },
        ):
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "identity changed",
            ):
                pull.refresh_external_assets_from_source(state)

    def test_prepare_state_is_owned_by_current_new_server(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "managed_identity_file": False,
            "ssh": "ssh",
        }
        source_plan = {
            "status": "READY",
            "source_server_identity": "sha256:old",
            "sites": [],
            "capacity_estimate": {"target_required_bytes": 0},
            "external_assets": [],
            "sqlite_assets": [],
            "runtime_assets": {},
            "source_external_listeners": [],
        }
        with tempfile.TemporaryDirectory() as td:
            old_root = pull.STATE_ROOT
            old_legacy_root = pull.legacy.STATE_ROOT
            pull.STATE_ROOT = Path(td)
            pull.legacy.STATE_ROOT = Path(td)
            try:
                with mock.patch.object(pull, "source_probe", return_value=source_plan), mock.patch.object(
                    pull,
                    "target_preflight_local",
                    return_value={"status": "READY", "target_identity": "sha256:new"},
                ), mock.patch.object(
                    pull, "stage_source_runtime", return_value="/remote/runtime"
                ), mock.patch.object(
                    pull, "ensure_old_server_rsync", return_value={"status": "READY", "installed": False}
                ), mock.patch.object(
                    pull, "resume_prepare_migration", side_effect=lambda mid: pull.load_state(mid)
                ):
                    state = pull.prepare_migration(source, [], "PREPARE_PULL_MIGRATION")
                self.assertEqual(state["schema"], pull.SCHEMA)
                self.assertEqual(state["direction"], "TARGET_PULL")
                self.assertEqual(state["current_server_role"], "RECEIVER")
                self.assertEqual(state["source"]["ip"], "192.0.2.10")
                self.assertTrue((Path(td) / state["migration_id"] / "state.json").is_file())
            finally:
                pull.STATE_ROOT = old_root
                pull.legacy.STATE_ROOT = old_legacy_root

    def test_source_runtime_staging_uses_only_installed_runtime_files(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "managed_identity_file": False,
            "ssh": "ssh",
        }
        captured = {}

        def fake_stream(tar, source_cwd, members, base, remote_command, stage):
            captured["members"] = list(members)
            captured["stage"] = stage

        with mock.patch.object(pull.transport, "stream_tar_to_remote", side_effect=fake_stream):
            runtime = pull.stage_source_runtime(source, "probe-12345678")

        self.assertEqual(
            captured["members"],
            ["bin", "lib", "VERSION", "BUILD_ID"],
        )
        self.assertNotIn("VF_PROJECT.json", captured["members"])
        self.assertEqual(captured["stage"], "old-server helper staging")
        self.assertTrue(runtime.endswith("/probe-12345678/runtime"))

    def test_local_runtime_archive_failure_is_not_misreported_as_old_server_failure(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "managed_identity_file": False,
            "ssh": "ssh",
        }
        with mock.patch.object(
            pull.transport,
            "stream_tar_to_remote",
            side_effect=pull.transport.TransportError("old-server helper staging local archive failed"),
        ):
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "current-server migration runtime is incomplete",
            ):
                pull.stage_source_runtime(source, "probe-12345678")

    def test_wrong_prepare_token_fails_before_any_source_write(self) -> None:
        with self.assertRaises(pull.PullMigrationError):
            pull.prepare_migration(
                {
                    "host": "192.0.2.10",
                    "ip": "192.0.2.10",
                    "ssh_user": "root",
                    "ssh_port": 22,
                    "identity_file": None,
                    "managed_identity_file": False,
                    "ssh": "ssh",
                },
                [],
                "PREPARE_SERVER_MIGRATION",
            )

    def test_target_smoke_accepts_local_404_as_reachable(self) -> None:
        state = {
            "sites": [{
                "domain": "example.com",
                "domains": ["example.com"],
                "document_root": "/home/site/htdocs/example.com",
                "runtime": {"type": "php", "version": "8.4"},
                "mysql_databases": [],
                "sqlite_paths": [],
                "cron": {"entry_count": 0},
                "pm2": {"processes": []},
                "ssl": {"configured": True},
            }]
        }
        target = json.loads(json.dumps(state["sites"][0]))
        manifest = {"sites": [target]}
        with mock.patch.object(
            pull.inventory, "build_manifest", return_value=manifest
        ), mock.patch.object(
            pull, "run_local",
            return_value=subprocess.CompletedProcess([], 0, "404", ""),
        ):
            result = pull.target_smoke(state)
        self.assertEqual(result["pass"], 1)
        self.assertEqual(result["fail"], 0)
        self.assertEqual(result["failures"], [])

    def test_target_smoke_rejects_404_when_source_baseline_was_200(self) -> None:
        state = {
            "source_http_baseline": {
                "example.com": {
                    "status": "PASS",
                    "http_code": "200",
                    "family": "SUCCESS_OR_REDIRECT",
                    "curl_exit": 0,
                }
            },
            "sites": [{
                "domain": "example.com",
                "domains": ["example.com"],
                "document_root": "/home/site/htdocs/example.com",
                "runtime": {"type": "php", "version": "8.4"},
                "mysql_databases": [],
                "sqlite_paths": [],
                "cron": {"entry_count": 0},
                "pm2": {"processes": []},
                "ssl": {"configured": True},
            }],
        }
        target = json.loads(json.dumps(state["sites"][0]))
        manifest = {"sites": [target]}
        with mock.patch.object(
            pull.inventory, "build_manifest", return_value=manifest
        ), mock.patch.object(
            pull, "run_local",
            return_value=subprocess.CompletedProcess([], 0, "404", ""),
        ):
            result = pull.target_smoke(state, attempts=1, delay=0)

        self.assertEqual(result["pass"], 0)
        self.assertEqual(result["fail"], 1)
        self.assertEqual(
            result["failures"][0]["reason"],
            "HTTP_BASELINE_REGRESSION",
        )
        self.assertEqual(
            result["failures"][0]["source_http_baseline"]["source_http_code"],
            "200",
        )

    def test_target_smoke_accepts_matching_404_source_baseline(self) -> None:
        state = {
            "source_http_baseline": {
                "example.com": {
                    "status": "PASS",
                    "http_code": "404",
                    "family": "CLIENT_ERROR",
                    "curl_exit": 0,
                }
            },
            "sites": [{
                "domain": "example.com",
                "domains": ["example.com"],
                "document_root": "/home/site/htdocs/example.com",
                "runtime": {"type": "php", "version": "8.4"},
                "mysql_databases": [],
                "sqlite_paths": [],
                "cron": {"entry_count": 0},
                "pm2": {"processes": []},
                "ssl": {"configured": True},
            }],
        }
        target = json.loads(json.dumps(state["sites"][0]))
        manifest = {"sites": [target]}
        with mock.patch.object(
            pull.inventory, "build_manifest", return_value=manifest
        ), mock.patch.object(
            pull, "run_local",
            return_value=subprocess.CompletedProcess([], 0, "404", ""),
        ):
            result = pull.target_smoke(state, attempts=1, delay=0)

        self.assertEqual(result["pass"], 1)
        self.assertEqual(result["fail"], 0)

    def test_target_smoke_retries_transient_503_until_ready(self) -> None:
        state = {
            "sites": [{
                "domain": "example.com",
                "domains": ["example.com"],
                "document_root": "/home/site/htdocs/example.com",
                "runtime": {"type": "node", "version": "22"},
                "mysql_databases": [],
                "sqlite_paths": [],
                "cron": {"entry_count": 0},
                "pm2": {"processes": [{"name": "web"}]},
                "ssl": {"configured": True},
            }]
        }
        target = json.loads(json.dumps(state["sites"][0]))
        manifest = {"sites": [target]}
        responses = [
            subprocess.CompletedProcess([], 0, "503", ""),
            subprocess.CompletedProcess([], 0, "200", ""),
        ]
        with mock.patch.object(
            pull.inventory, "build_manifest", return_value=manifest
        ), mock.patch.object(
            pull, "run_local", side_effect=responses
        ) as run, mock.patch.object(
            pull.time, "sleep"
        ) as sleep:
            result = pull.target_smoke(state, attempts=4, delay=0.1)
        self.assertEqual(result["pass"], 1)
        self.assertEqual(result["fail"], 0)
        self.assertEqual(result["failures"], [])
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(0.1)

    def test_php_backend_starts_inactive_service_without_nginx_restart(self) -> None:
        site = {
            "domain": "example.com",
            "runtime": {"type": "php", "version": "8.4"},
        }
        calls = [
            subprocess.CompletedProcess([], 3, "inactive\n", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        ]
        with mock.patch.object(
            pull, "run_local", side_effect=calls
        ) as run, mock.patch.object(
            pull, "php_fpm_listener_for_domain", return_value=19011
        ), mock.patch.object(
            pull, "tcp_listener_ready", return_value=True
        ):
            result = pull.reconcile_php_fpm_backend(site)

        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["action"], "STARTED")
        self.assertEqual(result["listener_port"], 19011)
        self.assertEqual(run.call_args_list[0].args[0], ["systemctl", "is-active", "php8.4-fpm"])
        self.assertEqual(run.call_args_list[1].args[0], ["systemctl", "start", "php8.4-fpm"])
        self.assertFalse(any("nginx" in " ".join(call.args[0]) for call in run.call_args_list))

    def test_php_backend_reloads_active_pool_when_listener_missing(self) -> None:
        site = {
            "domain": "example.com",
            "runtime": {"type": "php", "version": "8.3"},
        }
        calls = [
            subprocess.CompletedProcess([], 0, "active\n", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        ]
        with mock.patch.object(
            pull, "run_local", side_effect=calls
        ) as run, mock.patch.object(
            pull, "php_fpm_listener_for_domain", return_value=18001
        ), mock.patch.object(
            pull, "tcp_listener_ready", side_effect=[False, True]
        ), mock.patch.object(
            pull.time, "sleep"
        ) as sleep:
            result = pull.reconcile_php_fpm_backend(site)

        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["action"], "RELOADED")
        self.assertEqual(result["listener_port"], 18001)
        self.assertEqual(run.call_args_list[1].args[0], ["systemctl", "reload", "php8.3-fpm"])
        sleep.assert_called_once_with(1.0)

    def test_target_smoke_rejects_persistent_502_after_php_backend_is_ready(self) -> None:
        state = {
            "sites": [{
                "domain": "example.com",
                "domains": ["example.com"],
                "document_root": "/home/site/htdocs/example.com",
                "runtime": {"type": "php", "version": "8.4"},
                "mysql_databases": [],
                "sqlite_paths": [],
                "cron": {"entry_count": 0},
                "pm2": {"processes": []},
                "ssl": {"configured": True},
            }]
        }
        target = json.loads(json.dumps(state["sites"][0]))
        manifest = {"sites": [target]}
        with mock.patch.object(
            pull.inventory, "build_manifest", return_value=manifest
        ), mock.patch.object(
            pull, "run_local",
            return_value=subprocess.CompletedProcess([], 0, "502", ""),
        ) as run, mock.patch.object(
            pull, "reconcile_php_fpm_backend",
            return_value={
                "status": "READY",
                "service": "php8.4-fpm",
                "listener_port": 19011,
                "action": "NONE",
            },
        ), mock.patch.object(
            pull.time, "sleep"
        ) as sleep:
            result = pull.target_smoke(state, attempts=3, delay=0.1)
        self.assertEqual(result["pass"], 0)
        self.assertEqual(result["fail"], 1)
        self.assertEqual(result["failures"][0]["domain"], "example.com")
        self.assertEqual(result["failures"][0]["reason"], "LOCAL_HTTP_PROBE")
        self.assertEqual(result["failures"][0]["http_code"], "502")
        self.assertEqual(result["failures"][0]["attempts"], 3)
        self.assertEqual(result["failures"][0]["backend"]["status"], "READY")
        self.assertEqual(run.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_pre_cutover_reconcile_catches_missing_external_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site_root = root / "site"
            site_root.mkdir()
            missing_runtime = root / ".press.example-runtime"
            state = {
                "source": {"host": "192.0.2.10"},
                "sites": [{
                    "domain": "example.com",
                    "document_root": str(site_root),
                    "stage_status": "PULLED_STAGED",
                    "mysql_databases": [],
                }],
                "external_assets": [{
                    "path": str(missing_runtime),
                    "user": "site",
                    "kind": "DIRECTORY",
                }],
                "sqlite_assets": [],
                "runtime_assets": {
                    "system_cron": [],
                    "user_cron": [],
                    "pm2": [],
                },
                "pending_system_cron": [],
                "pending_user_cron": [],
                "pending_pm2": [],
                "source_http_baseline_required": True,
                "source_http_baseline": {
                    "example.com": {
                        "status": "PASS",
                        "http_code": "200",
                        "family": "SUCCESS_OR_REDIRECT",
                    }
                },
            }

            result = pull.pre_cutover_reconcile(state)

        self.assertEqual(result["status"], "FAIL")
        self.assertIn(
            f"EXTERNAL_DIRECTORY_MISSING:{missing_runtime}",
            result["failures"],
        )

    def test_pre_cutover_reconcile_passes_verified_sqlite_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site_root = root / "site"
            site_root.mkdir()
            runtime = root / ".press.example-runtime"
            runtime.mkdir()
            sqlite_path = root / "app.db"
            conn = sqlite3.connect(sqlite_path)
            conn.execute("CREATE TABLE x(id INTEGER)")
            conn.commit()
            conn.close()
            state = {
                "source": {"host": "192.0.2.10"},
                "sites": [{
                    "domain": "example.com",
                    "document_root": str(site_root),
                    "stage_status": "PULLED_STAGED",
                    "mysql_databases": [],
                }],
                "external_assets": [{
                    "path": str(runtime),
                    "user": "site",
                    "kind": "DIRECTORY",
                }],
                "sqlite_assets": [{
                    "path": str(sqlite_path),
                    "user": "site",
                    "mode": 0o600,
                }],
                "runtime_assets": {
                    "system_cron": [],
                    "user_cron": [],
                    "pm2": [],
                },
                "pending_system_cron": [],
                "pending_user_cron": [],
                "pending_pm2": [],
                "source_http_baseline_required": True,
                "source_http_baseline": {
                    "example.com": {
                        "status": "PASS",
                        "http_code": "200",
                        "family": "SUCCESS_OR_REDIRECT",
                    }
                },
            }

            result = pull.pre_cutover_reconcile(state, home_root=root)

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["checked"]["external_assets"], 1)
        self.assertEqual(result["checked"]["sqlite_assets"], 1)

    def test_cutover_reconciliation_failure_does_not_freeze_source(self) -> None:
        mid = "pull-20261005T000000Z-preflight"
        state = {
            "migration_id": mid,
            "status": "PREPARED",
            "source_runtime_frozen": False,
            "sites": [],
            "external_assets": [],
            "sqlite_assets": [],
            "runtime_assets": {},
            "source": {},
        }
        with mock.patch.object(
            pull, "load_state", return_value=state
        ), mock.patch.object(
            pull, "save_state"
        ), mock.patch.object(
            pull,
            "refresh_migration_assets_from_source",
            return_value={
                "external_added": 0,
                "external_added_paths": [],
                "sqlite_added": 0,
                "sqlite_added_paths": [],
                "runtime_assets_changed": False,
            },
        ), mock.patch.object(
            pull, "ensure_source_http_baseline", return_value={}
        ), mock.patch.object(
            pull,
            "pre_cutover_reconcile",
            return_value={
                "status": "FAIL",
                "checked": {},
                "failures": ["EXTERNAL_DIRECTORY_MISSING:/home/site/runtime"],
            },
        ), mock.patch.object(
            pull, "freeze_old_server"
        ) as freeze:
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "pre-cutover completeness reconciliation failed",
            ):
                pull.cutover_migration(mid, f"CUTOVER_PULL:{mid}")

        freeze.assert_not_called()
        self.assertEqual(state["status"], "PREPARED")

    def test_cutover_can_retry_same_task_after_successful_rollback(self) -> None:
        mid = "pull-20261005T000000Z-deadbeef"
        state = {
            "migration_id": mid,
            "status": "CUTOVER_FAILED_ROLLED_BACK",
            "source_runtime_frozen": False,
            "sites": [],
            "external_assets": [],
            "sqlite_assets": [],
            "source": {},
        }
        with mock.patch.object(pull, "load_state", return_value=state), mock.patch.object(
            pull, "save_state"
        ), mock.patch.object(
            pull,
            "refresh_migration_assets_from_source",
            return_value={
                "external_added": 0,
                "external_added_paths": [],
                "sqlite_added": 0,
                "sqlite_added_paths": [],
                "runtime_assets_changed": False,
            },
        ), mock.patch.object(
            pull, "ensure_source_http_baseline", return_value={}
        ), mock.patch.object(
            pull,
            "pre_cutover_reconcile",
            return_value={"status": "PASS", "checked": {}, "failures": []},
        ), mock.patch.object(
            pull, "freeze_old_server"
        ), mock.patch.object(
            pull, "sync_external_assets", return_value=[]
        ), mock.patch.object(
            pull, "sync_site_databases", return_value=0
        ), mock.patch.object(
            pull, "sync_sqlite_assets", return_value=0
        ), mock.patch.object(
            pull, "activate_target_runtime"
        ), mock.patch.object(
            pull, "target_smoke", return_value={"pass": 0, "fail": 0, "failures": []}
        ):
            result = pull.cutover_migration(mid, f"CUTOVER_PULL:{mid}")
        self.assertEqual(result["status"], "CUTOVER_PREP_READY")

    def test_production_verify_rejects_404_when_source_was_200(self) -> None:
        state = {
            "source": {"host": "192.0.2.10"},
            "source_http_baseline": {
                "example.com": {
                    "status": "PASS",
                    "http_code": "200",
                    "family": "SUCCESS_OR_REDIRECT",
                }
            },
            "sites": [{"domain": "example.com"}],
        }
        with mock.patch.object(
            pull,
            "run_local",
            return_value=subprocess.CompletedProcess(
                [], 0, "404|0|203.0.113.20", ""
            ),
        ), mock.patch.object(
            pull,
            "source_remote",
            return_value=subprocess.CompletedProcess([], 3, "", ""),
        ):
            result = pull.production_verify(state)

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("example.com", result["failures"])
        self.assertFalse(result["sites"][0]["baseline_compatible"])
        self.assertEqual(result["sites"][0]["source_http_code"], "200")

    def test_http_baseline_treats_200_to_301_as_compatible(self) -> None:
        self.assertTrue(pull.http_baseline_compatible("200", "301"))
        self.assertFalse(pull.http_baseline_compatible("200", "404"))
        self.assertTrue(pull.http_baseline_compatible("404", "404"))
        self.assertFalse(pull.http_baseline_compatible("403", "404"))

    def test_post_dns_waiting_state_denies_runtime_only_rollback(self) -> None:
        state = {
            "schema": pull.SCHEMA,
            "migration_id": "pull-20260929T000000Z-deadbeef",
            "status": "WAITING_DNS",
        }
        with mock.patch.object(pull, "load_state", return_value=state):
            with self.assertRaises(pull.PullMigrationError):
                pull.rollback_migration(
                    state["migration_id"],
                    f"ROLLBACK_PULL:{state['migration_id']}",
                )

    def test_post_migration_audit_verifies_closure_but_keeps_old_server(self) -> None:
        state = {
            "status": "PRODUCTION_PASS",
            "public_route_proof": {"status": "PASS"},
            "production_verification": {"status": "PASS"},
            "source_retained_for_recovery": True,
            "source_delete_allowed": False,
            "dns_changed_by_p07": False,
            "source_runtime_frozen": True,
            "source_helper_retained_for_recovery": True,
            "production_passed_at": "2026-10-05T00:00:00+00:00",
        }

        result = pull.post_migration_audit(state)

        self.assertEqual(result["status"], "PRODUCTION_CLOSURE_VERIFIED")
        self.assertEqual(result["old_server_disposition"], "RETAIN_RECOVERY_COPY")
        self.assertEqual(result["retirement_readiness"], "NOT_AUTHORIZED")
        self.assertTrue(result["owner_retirement_gate_required"])
        self.assertFalse(result["old_server_delete_allowed"])
        self.assertEqual(result["source_runtime_state"], "FROZEN")
        self.assertEqual(result["closure_blockers"], [])
        self.assertIn(
            "OWNER_RETIREMENT_GATE_REQUIRED",
            result["retirement_blockers"],
        )
        self.assertIn(
            "SOURCE_HELPER_RETAINED_FOR_RECOVERY",
            result["retirement_blockers"],
        )
        self.assertFalse(result["writes_performed"])

    def test_post_migration_audit_fails_closed_on_conflicting_state(self) -> None:
        state = {
            "status": "PRODUCTION_PASS",
            "public_route_proof": {"status": "FAIL"},
            "production_verification": {"status": "PASS"},
            "source_retained_for_recovery": True,
            "source_delete_allowed": True,
            "dns_changed_by_p07": True,
            "existing_target_overwrite_allowed": True,
            "secrets_emitted": True,
            "source_runtime_frozen": False,
        }

        result = pull.post_migration_audit(state)

        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["old_server_disposition"], "RETAIN_RECOVERY_COPY")
        self.assertEqual(result["retirement_readiness"], "NOT_AUTHORIZED")
        self.assertFalse(result["old_server_delete_allowed"])
        self.assertEqual(result["source_runtime_state"], "LIVE")
        self.assertIn("PUBLIC_ROUTE_NOT_VERIFIED", result["closure_blockers"])
        self.assertIn(
            "SOURCE_DELETE_POLICY_VIOLATION",
            result["closure_blockers"],
        )
        self.assertIn(
            "DNS_MUTATION_POLICY_VIOLATION",
            result["closure_blockers"],
        )
        self.assertIn(
            "TARGET_OVERWRITE_POLICY_VIOLATION",
            result["closure_blockers"],
        )
        self.assertIn(
            "SECRET_OUTPUT_POLICY_VIOLATION",
            result["closure_blockers"],
        )
        self.assertIn(
            "SOURCE_RUNTIME_NOT_FROZEN",
            result["closure_blockers"],
        )

    def test_summary_never_exposes_identity_path_or_secrets(self) -> None:
        state = {
            "schema": pull.SCHEMA,
            "migration_id": "pull-20260929T000000Z-deadbeef",
            "status": "PREPARED",
            "direction": "TARGET_PULL",
            "current_server_role": "RECEIVER",
            "source": {
                "ip": "192.0.2.10",
                "identity_file": "/root/.ssh/private",
            },
            "sites": [],
        }
        result = pull.summary(state)
        serialized = json.dumps(result)
        self.assertNotIn("identity_file", serialized)
        self.assertNotIn("/root/.ssh/private", serialized)
        self.assertFalse(result["source_delete_allowed"])
        self.assertFalse(result["dns_changed_by_p07"])
        self.assertFalse(result["existing_target_overwrite_allowed"])
        self.assertEqual(result["post_audit"]["status"], "INCOMPLETE")
        self.assertFalse(result["post_audit"]["old_server_delete_allowed"])

    def test_summary_does_not_mask_safety_policy_violations(self) -> None:
        state = {
            "schema": pull.SCHEMA,
            "migration_id": "pull-20261006T000000Z-conflict",
            "status": "PRODUCTION_PASS",
            "direction": "TARGET_PULL",
            "current_server_role": "RECEIVER",
            "source": {"ip": "192.0.2.10"},
            "sites": [],
            "source_delete_allowed": True,
            "dns_changed_by_p07": True,
            "existing_target_overwrite_allowed": True,
            "secrets_emitted": True,
        }

        result = pull.summary(state)

        self.assertTrue(result["source_delete_allowed"])
        self.assertTrue(result["dns_changed_by_p07"])
        self.assertTrue(result["existing_target_overwrite_allowed"])
        self.assertTrue(result["secrets_emitted"])
        self.assertIn(
            "SOURCE_DELETE_POLICY_VIOLATION",
            result["post_audit"]["closure_blockers"],
        )
        self.assertIn(
            "DNS_MUTATION_POLICY_VIOLATION",
            result["post_audit"]["closure_blockers"],
        )
        self.assertIn(
            "TARGET_OVERWRITE_POLICY_VIOLATION",
            result["post_audit"]["closure_blockers"],
        )
        self.assertIn(
            "SECRET_OUTPUT_POLICY_VIOLATION",
            result["post_audit"]["closure_blockers"],
        )

    def test_source_nginx_status_distinguishes_site_from_cloudpanel_control_plane(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "managed_identity_file": False,
            "ssh": "ssh",
        }
        responses = [
            subprocess.CompletedProcess([], 3, "inactive\n", ""),
            subprocess.CompletedProcess([], 0, "active\n", ""),
            subprocess.CompletedProcess(
                [],
                0,
                "LISTEN 0 511 0.0.0.0:8443 0.0.0.0:*\n",
                "",
            ),
        ]
        with mock.patch.object(pull, "source_remote", side_effect=responses):
            result = pull.source_nginx_status(source)

        self.assertFalse(result["site_nginx_running"])
        self.assertEqual(result["site_nginx_state"], "inactive")
        self.assertEqual(result["cloudpanel_nginx_state"], "active")
        self.assertEqual(result["web_listener_80_443"], "NO")
        self.assertEqual(result["cloudpanel_listener_8443"], "YES")
        self.assertFalse(result["writes_performed"])

    def test_source_nginx_start_requires_config_pass_and_touches_only_site_service(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "managed_identity_file": False,
            "ssh": "ssh",
        }
        before = {"site_nginx_running": False}
        after = {
            "site_nginx_running": True,
            "site_nginx_state": "active",
            "cloudpanel_nginx_state": "active",
            "web_listener_80_443": "YES",
            "cloudpanel_listener_8443": "YES",
        }
        calls = [
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        ]
        with mock.patch.object(
            pull,
            "source_nginx_status",
            side_effect=[before, after],
        ), mock.patch.object(
            pull,
            "source_remote",
            side_effect=calls,
        ) as remote:
            result = pull.source_nginx_start(
                source,
                "START_SOURCE_NGINX:192.0.2.10",
            )

        self.assertEqual(result["status"], "STARTED")
        self.assertTrue(result["writes_performed"])
        self.assertEqual(remote.call_args_list[0].args[1], "nginx -t")
        self.assertEqual(
            remote.call_args_list[1].args[1],
            "systemctl start nginx",
        )
        self.assertNotIn(
            "clp-nginx",
            " ".join(call.args[1] for call in remote.call_args_list),
        )

    def test_source_nginx_start_fails_closed_when_config_test_fails(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "managed_identity_file": False,
            "ssh": "ssh",
        }
        with mock.patch.object(
            pull,
            "source_nginx_status",
            return_value={"site_nginx_running": False},
        ), mock.patch.object(
            pull,
            "source_remote",
            return_value=subprocess.CompletedProcess([], 1, "", "bad config"),
        ) as remote:
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "config test failed",
            ):
                pull.source_nginx_start(
                    source,
                    "START_SOURCE_NGINX:192.0.2.10",
                )

        remote.assert_called_once()
        self.assertEqual(remote.call_args.args[1], "nginx -t")

    def test_source_nginx_stop_touches_only_site_service(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "managed_identity_file": False,
            "ssh": "ssh",
        }
        before = {"site_nginx_running": True}
        after = {
            "site_nginx_running": False,
            "site_nginx_state": "inactive",
            "cloudpanel_nginx_state": "active",
            "web_listener_80_443": "NO",
            "cloudpanel_listener_8443": "YES",
        }
        with mock.patch.object(
            pull,
            "source_nginx_status",
            side_effect=[before, after],
        ), mock.patch.object(
            pull,
            "source_remote",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ) as remote:
            result = pull.source_nginx_stop(
                source,
                "STOP_SOURCE_NGINX:192.0.2.10",
            )

        self.assertEqual(result["status"], "STOPPED")
        self.assertTrue(result["writes_performed"])
        remote.assert_called_once()
        self.assertEqual(remote.call_args.args[1], "systemctl stop nginx")
        self.assertNotIn("clp-nginx", remote.call_args.args[1])

    def test_source_nginx_control_wrong_confirmation_is_zero_write(self) -> None:
        source = {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "ssh_user": "root",
            "ssh_port": 22,
            "identity_file": None,
            "managed_identity_file": False,
            "ssh": "ssh",
        }
        with mock.patch.object(
            pull,
            "source_nginx_status",
            return_value={"site_nginx_running": True},
        ), mock.patch.object(pull, "source_remote") as remote:
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "explicit confirmation required",
            ):
                pull.source_nginx_stop(source, "NO")
            remote.assert_not_called()

    def test_local_nginx_status_reads_current_machine_without_ssh(self) -> None:
        responses = [
            subprocess.CompletedProcess([], 3, "inactive\n", ""),
            subprocess.CompletedProcess([], 0, "active\n", ""),
            subprocess.CompletedProcess([], 0, "LISTEN 0 511 0.0.0.0:8443 0.0.0.0:*\n", ""),
        ]
        with mock.patch.object(pull, "run_local", side_effect=responses) as local:
            result = pull.local_nginx_status()
        self.assertFalse(result["site_nginx_running"])
        self.assertEqual(result["site_nginx_state"], "inactive")
        self.assertEqual(result["cloudpanel_nginx_state"], "active")
        self.assertEqual(result["web_listener_80_443"], "NO")
        self.assertEqual(result["cloudpanel_listener_8443"], "YES")
        self.assertEqual(local.call_args_list[0].args[0], ["systemctl", "is-active", "nginx"])
        self.assertEqual(local.call_args_list[1].args[0], ["systemctl", "is-active", "clp-nginx"])

    def test_local_nginx_start_checks_config_and_never_touches_cloudpanel_service(self) -> None:
        with mock.patch.object(
            pull, "local_nginx_status",
            side_effect=[{"site_nginx_running": False}, {"site_nginx_running": True, "site_nginx_state": "active"}],
        ), mock.patch.object(
            pull, "run_local",
            side_effect=[
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 0, "", ""),
            ],
        ) as local:
            result = pull.local_nginx_start("START_LOCAL_NGINX")
        self.assertEqual(result["status"], "STARTED")
        self.assertEqual(local.call_args_list[0].args[0], ["nginx", "-t"])
        self.assertEqual(local.call_args_list[1].args[0], ["systemctl", "start", "nginx"])
        self.assertNotIn("clp-nginx", " ".join(" ".join(call.args[0]) for call in local.call_args_list))

    def test_local_nginx_stop_only_stops_current_website_service(self) -> None:
        with mock.patch.object(
            pull, "local_nginx_status",
            side_effect=[{"site_nginx_running": True}, {"site_nginx_running": False, "site_nginx_state": "inactive"}],
        ), mock.patch.object(
            pull, "run_local",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ) as local:
            result = pull.local_nginx_stop("STOP_LOCAL_NGINX")
        self.assertEqual(result["status"], "STOPPED")
        local.assert_called_once()
        self.assertEqual(local.call_args.args[0], ["systemctl", "stop", "nginx"])

    def test_source_recovery_state_has_separate_root(self) -> None:
        self.assertNotEqual(pull.SOURCE_RECOVERY_ROOT, pull.STATE_ROOT)
        self.assertIn("source-recovery", str(pull.SOURCE_RECOVERY_ROOT))



class BootstrapHardwareSizingContractTests(unittest.TestCase):
    def test_one_core_one_gb_is_advisory_not_blocked(self) -> None:
        with mock.patch.object(
            pull.os, "geteuid", return_value=0
        ), mock.patch.object(
            pull.Path,
            "read_text",
            side_effect=[
                'ID=debian\\nVERSION_ID="13"\\n',
                "MemTotal:       1000000 kB\\n",
            ],
        ), mock.patch.object(
            pull.legacy,
            "parse_os_release",
            return_value=("debian", "13"),
        ), mock.patch.object(
            pull.os, "uname", return_value=mock.Mock(machine="x86_64")
        ), mock.patch.object(
            pull.os, "cpu_count", return_value=1
        ), mock.patch.object(
            pull.shutil,
            "disk_usage",
            return_value=mock.Mock(total=20 * 1024**3),
        ), mock.patch.object(
            pull.shutil, "which", return_value=None
        ), mock.patch.object(
            pull.Path, "exists", return_value=False
        ), mock.patch.object(
            pull, "local_cloud_hint", return_value="generic"
        ):
            result = pull.local_bootstrap_preflight()

        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["hardware_baseline_is_advisory"])
        self.assertIn(
            "MEMORY_BELOW_CLOUDPANEL_PUBLISHED_BASELINE",
            result["hardware_advisories"],
        )

    def test_local_provider_detection_maps_vultr(self) -> None:
        def read_text(path: Path, *args, **kwargs) -> str:
            if str(path).endswith("/sys_vendor"):
                return "Vultr"
            if str(path).endswith("/product_name"):
                return "Cloud Compute"
            raise OSError("unexpected")

        with mock.patch.object(pull.Path, "read_text", autospec=True, side_effect=read_text):
            self.assertEqual(pull.local_cloud_hint(), "vultr")

    def test_unsupported_architecture_still_fails_closed(self) -> None:
        with mock.patch.object(
            pull.os, "geteuid", return_value=0
        ), mock.patch.object(
            pull.Path,
            "read_text",
            side_effect=[
                'ID=debian\\nVERSION_ID="13"\\n',
                "MemTotal:       2500000 kB\\n",
            ],
        ), mock.patch.object(
            pull.legacy,
            "parse_os_release",
            return_value=("debian", "13"),
        ), mock.patch.object(
            pull.os, "uname", return_value=mock.Mock(machine="riscv64")
        ), mock.patch.object(
            pull.os, "cpu_count", return_value=1
        ), mock.patch.object(
            pull.shutil,
            "disk_usage",
            return_value=mock.Mock(total=20 * 1024**3),
        ):
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                "unsupported architecture",
            ):
                pull.local_bootstrap_preflight()


    def test_existing_environment_reports_detected_conflicts(self) -> None:
        def which(name: str):
            return "/usr/sbin/nginx" if name == "nginx" else None

        with mock.patch.object(
            pull.os, "geteuid", return_value=0
        ), mock.patch.object(
            pull.Path,
            "read_text",
            side_effect=[
                'ID=debian\\nVERSION_ID="13"\\n',
                "MemTotal:       2500000 kB\\n",
            ],
        ), mock.patch.object(
            pull.legacy,
            "parse_os_release",
            return_value=("debian", "13"),
        ), mock.patch.object(
            pull.os, "uname", return_value=mock.Mock(machine="x86_64")
        ), mock.patch.object(
            pull.os, "cpu_count", return_value=1
        ), mock.patch.object(
            pull.shutil,
            "disk_usage",
            return_value=mock.Mock(total=20 * 1024**3),
        ), mock.patch.object(
            pull.shutil, "which", side_effect=which
        ), mock.patch.object(
            pull.Path, "exists", return_value=False
        ):
            with self.assertRaisesRegex(
                pull.PullMigrationError,
                r"nginx",
            ):
                pull.local_bootstrap_preflight()

    def test_stale_apache_config_directory_is_advisory_not_blocked(self) -> None:
        def exists(path: Path) -> bool:
            return str(path) == "/etc/apache2"

        with mock.patch.object(
            pull.os, "geteuid", return_value=0
        ), mock.patch.object(
            pull.Path,
            "read_text",
            side_effect=[
                'ID=debian\\nVERSION_ID="13"\\n',
                "MemTotal:       2500000 kB\\n",
            ],
        ), mock.patch.object(
            pull.legacy,
            "parse_os_release",
            return_value=("debian", "13"),
        ), mock.patch.object(
            pull.os, "uname", return_value=mock.Mock(machine="x86_64")
        ), mock.patch.object(
            pull.os, "cpu_count", return_value=1
        ), mock.patch.object(
            pull.shutil,
            "disk_usage",
            return_value=mock.Mock(total=20 * 1024**3),
        ), mock.patch.object(
            pull.shutil, "which", return_value=None
        ), mock.patch.object(
            pull.Path, "exists", autospec=True, side_effect=exists
        ), mock.patch.object(
            pull, "local_cloud_hint", return_value="generic"
        ):
            result = pull.local_bootstrap_preflight()

        self.assertEqual(result["status"], "READY")
        self.assertIn(
            "STALE_CONFIG_DIR:/etc/apache2",
            result["environment_advisories"],
        )


class TargetPullUiContractTests(unittest.TestCase):
    def test_init_ui_is_repeatable_and_shows_install_progress(self) -> None:
        text = (ROOT / "bin/vfops-init-ui").read_text(encoding="utf-8")
        for marker in (
            "完整初始化：更新 / 时区 / Swap / CloudPanel / 性能配置",
            "一键初始化可以安全重复执行；已正确的项目会跳过，CloudPanel 已健康时不会重复安装。",
            "一键初始化服务器",
            "确认开始一键初始化？[y/N]",
            "基础设置 → 系统更新 → CloudPanel → 性能配置 → 最终检查",
            "首次空服务器会自动安装系统更新",
            "CloudPanel 已安装的服务器只检查更新",
            "性能配置统一调用一级菜单 4 的同一套正式调优；初始化不再维护第二套调优逻辑。",
            "本次初始化执行清单",
            "性能配置未闭环",
            "无法从 CloudPanel 读取本机数据库连接信息",
            "CloudPanel 数据库连接信息读取超时",
            "性能配置处理中 · 已耗时",
            "服务器资源评估完成",
            "当前不适合自动调整",
            "性能配置已按推荐值调整并验证",
            "P07_RESOURCE_APPLY_CONFIRMED=1",
            "已读取到 CloudPanel 本机数据库连接信息，但本机连接验证失败",
            "安全检查返回了未识别的阻断条件，已停止自动调整",
            "服务器初始化完成",
            "render_indeterminate_bar",
            "1/3 安装前安全检查已通过",
            "2/3 [%s] 正在安装 CloudPanel · 已耗时 %s",
            "3/3 安装后检查通过",
            "CloudPanel 安装不完整：本机数据库服务器主记录缺失。",
            "这台机器不能作为迁移目标继续使用",
            "CloudPanel 已安装；首次使用必须先创建管理员",
            "管理员密码只在当前服务器终端隐藏输入；不会发送给 ChatGPT，不写入 P07 日志。",
            "CloudPanel 首次管理员与本机数据库服务器初始化完成",
            "read -r -s password",
            "CLOUDPANEL_ADMIN_REQUIRED",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("一键初始化服务器（推荐）", text)
        self.assertNotIn("请选择 [0-1]", text)
        self.assertIn("\npreflight\nrun_initialization\n", text)
        self.assertNotIn("ui_menu_warn 2 '基础设置（时区 / Swap）'", text)
        self.assertNotIn("ui_menu_warn 3 'CloudPanel 状态 / 安装'", text)
        self.assertNotIn("请选择 [0-3]", text)
        self.assertNotIn("重新执行初始化检查（推荐）", text)
        self.assertNotIn("初始化 / 重新初始化服务器（推荐）", text)
        self.assertNotIn("CloudPanel 尚未安装，确认现在安装？[y/N]", text)
        self.assertNotIn("新服务器第一次使用时在这里完成基础设置", text)
        self.assertNotIn("应用基础设置（时区 / Swap）", text)
        self.assertIn("resource-profile.sh", text)
        self.assertIn("resource-apply.sh", text)
        self.assertIn("apply-empty-server-confirmed-json", text)
        self.assertNotIn("lib/resource_profile.py", text)
        self.assertNotIn("lib/resource_apply.py", text)


    def test_bootstrap_ui_shows_specific_blocker_in_chinese(self) -> None:
        text = (ROOT / "bin/vfops-init-ui").read_text(encoding="utf-8")
        for marker in (
            "show_bootstrap_blocker",
            "需要使用 root 用户执行 CloudPanel 安装检查",
            "当前 Linux 系统版本不在自动安装支持范围内",
            "当前 CPU 架构不在 CloudPanel 自动安装支持范围内",
            "检测到这台服务器已经存在网站或数据库环境",
            "检测到 80 / 443 网站端口已经被其他程序占用",
            "检测到残留目录 /etc/apache2，但未发现 Apache 程序；只提示，不阻止安装。",
            "这不是低配限制",
        ):
            self.assertIn(marker, text)
        self.assertNotIn(
            "当前服务器不满足自动安装 CloudPanel 的条件。",
            text,
        )

    def test_ordinary_ui_uses_new_server_receiver_language(self) -> None:
        text = (ROOT / "bin/vfops-migrate-ui").read_text(encoding="utf-8")
        for marker in (
            "服务器迁移",
            "当前：",
            "这台新服务器（接收数据）",
            "迁入整台旧服务器",
            "迁入一个网站",
            "继续未完成迁移",
            "旧服务器 IP",
            "新服务器开始从旧服务器复制数据",
            "实时显示已传输量 / 百分比 / 速度",
            "VFOPS_MIGRATION_PROGRESS=1",
            "run_migration_live",
            "唯一剩余人工步骤",
            "DNS 不自动修改",
            "旧服务器永不自动删除",
            "新服务器已有资源不覆盖",
            "PREPARE_PULL_MIGRATION",
            "CUTOVER_PULL:",
            "旧服务器网站开关",
            "开启这台服务器全部网站",
            "停止这台服务器全部网站",
            "迁移后如果你登录的是旧服务器，就直接在这里操作，不需要输入 IP",
            "一次操作整台服务器的网站，不需要一个网站一个网站处理",
            "不会影响 CloudPanel 后台，也不会修改 DNS",
            "local-nginx-status",
            "local-nginx-start",
            "local-nginx-stop",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("目标服务器 IP", text)
        self.assertNotIn("SOURCE → TARGET", text)

        start = text.index("old_server_nginx_control()")
        end = text.index("select_existing_migration()", start)
        ordinary = text[start:end]
        for technical in (
            "nginx.service",
            "clp-nginx.service",
            "systemctl",
            "nginx -t",
            "80/443",
            "8443",
            "START_NGINX",
            "STOP_NGINX",
        ):
            self.assertNotIn(technical, ordinary)
        self.assertIn("确认开启？[y/N]", ordinary)
        self.assertIn("确认停止？[y/N]", ordinary)
        self.assertNotIn("输入“开启”", ordinary)
        self.assertNotIn("输入“停止”", ordinary)
        self.assertNotIn("read_old_ip", ordinary)
        self.assertNotIn("OLD_SERVER_IP", ordinary)
        self.assertNotIn("ensure_source_access", ordinary)
        self.assertNotIn("source_args", ordinary)

    def test_cli_routes_ordinary_server_migration_to_pull_engine(self) -> None:
        text = (ROOT / "bin/vfops").read_text(encoding="utf-8")
        self.assertIn('python3 "$ROOT_DIR/lib/server_migration_pull.py"', text)
        self.assertIn("--source-ip OLD_IP", text)
        self.assertIn("source-nginx-status --source-ip OLD_IP", text)
        self.assertIn("source-nginx-start --source-ip OLD_IP", text)
        self.assertIn("source-nginx-stop --source-ip OLD_IP", text)
        self.assertIn("server-migrate local-nginx-status", text)
        self.assertIn("server-migrate local-nginx-start", text)
        self.assertIn("server-migrate local-nginx-stop", text)
        self.assertNotIn("server-migrate plan --target-ip", text)

    def test_migration_dependencies_are_lazy_and_include_pull_transport(self) -> None:
        text = (ROOT / "bin/vfops-migrate-ui").read_text(encoding="utf-8")
        self.assertIn("ssh-copy-id", text)
        self.assertIn("rsync", text)
        self.assertIn("首次使用服务器迁移", text)
        self.assertIn("按需准备", text)
        self.assertIn("第一次连接旧服务器，需要输入旧服务器 root 密码一次", text)
        self.assertIn("密码只交给系统 ssh-copy-id；P07 不读取、不保存。", text)
        self.assertNotIn("现在为新服务器准备专用迁移密钥", text)


if __name__ == "__main__":
    unittest.main()
