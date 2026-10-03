from __future__ import annotations

import importlib.util
import json
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
        ):
            result = pull.local_bootstrap_preflight()

        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["hardware_baseline_is_advisory"])
        self.assertIn(
            "MEMORY_BELOW_CLOUDPANEL_PUBLISHED_BASELINE",
            result["hardware_advisories"],
        )

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
            "一键初始化服务器（推荐）",
            "一键初始化服务器",
            "确认开始一键初始化？[y/N]",
            "基础设置 → 系统更新 → CloudPanel → 性能配置 → 最终检查",
            "首次空服务器会自动安装系统更新",
            "CloudPanel 已安装的服务器只检查更新",
            "性能配置会按 CPU / 内存自动生成方案",
            "本次初始化执行清单",
            "当前资源方案不能安全自动写入",
            "资源方案已校准，但本机安全检查阻止了自动调整",
            "性能配置未闭环",
            "服务器初始化完成",
            "render_indeterminate_bar",
            "1/3 安装前安全检查已通过",
            "2/3 [%s] 正在安装 CloudPanel · 已耗时 %s",
            "3/3 安装后检查通过",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("重新执行初始化检查（推荐）", text)
        self.assertNotIn("初始化 / 重新初始化服务器（推荐）", text)
        self.assertNotIn("CloudPanel 尚未安装，确认现在安装？[y/N]", text)
        self.assertNotIn("新服务器第一次使用时在这里完成基础设置", text)
        self.assertNotIn("应用基础设置（时区 / Swap）", text)


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


if __name__ == "__main__":
    unittest.main()
