from __future__ import annotations

import importlib.util
import json
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

    def test_source_recovery_state_has_separate_root(self) -> None:
        self.assertNotEqual(pull.SOURCE_RECOVERY_ROOT, pull.STATE_ROOT)
        self.assertIn("source-recovery", str(pull.SOURCE_RECOVERY_ROOT))


class TargetPullUiContractTests(unittest.TestCase):
    def test_ordinary_ui_uses_new_server_receiver_language(self) -> None:
        text = (ROOT / "bin/vfops-migrate-ui").read_text(encoding="utf-8")
        for marker in (
            "P07 · 服务器迁移",
            "当前服务器：",
            "新服务器 / 接收端",
            "整机迁入",
            "单站迁入",
            "继续未完成迁移",
            "旧服务器 IP",
            "新服务器开始主动拉取旧服务器数据",
            "唯一剩余人工步骤",
            "DNS 不自动修改",
            "旧服务器永不自动删除",
            "新服务器已有资源不覆盖",
            "PREPARE_PULL_MIGRATION",
            "CUTOVER_PULL:",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("目标服务器 IP", text)
        self.assertNotIn("SOURCE → TARGET", text)

    def test_cli_routes_ordinary_server_migration_to_pull_engine(self) -> None:
        text = (ROOT / "bin/vfops").read_text(encoding="utf-8")
        self.assertIn('python3 "$ROOT_DIR/lib/server_migration_pull.py"', text)
        self.assertIn("--source-ip OLD_IP", text)
        self.assertNotIn("server-migrate plan --target-ip", text)

    def test_migration_dependencies_are_lazy_and_include_pull_transport(self) -> None:
        text = (ROOT / "bin/vfops-migrate-ui").read_text(encoding="utf-8")
        self.assertIn("ssh-copy-id", text)
        self.assertIn("rsync", text)
        self.assertIn("首次使用服务器迁移", text)
        self.assertIn("按需安装", text)


if __name__ == "__main__":
    unittest.main()
