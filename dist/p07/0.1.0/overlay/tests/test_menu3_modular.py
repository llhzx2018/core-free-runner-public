from __future__ import annotations

from pathlib import Path
import importlib.util
import subprocess
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class Menu3ModularTests(unittest.TestCase):
    def test_top_level_menu_is_thin_and_task_oriented(self) -> None:
        proc = subprocess.run(
            ["bash", str(ROOT / "bin/vfops-user")],
            input="0\n",
            text=True,
            capture_output=True,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for text in (
            "1. 网站与数据概况",
            "2. 备份与恢复",
            "3. 服务器迁移",
            "4. 网站创建与维护",
            "5. 面板账号与安全",
            "网站状态",
            "网站数据",
            "整机/单站",
            "网站/数据库",
            "面板账户",
        ):
            self.assertIn(text, proc.stdout)

    def test_top_level_routes_to_separate_modules(self) -> None:
        text = (ROOT / "bin/vfops-user").read_text(encoding="utf-8")
        self.assertIn("vfops-site-ui", text)
        self.assertIn("vfops-migrate-ui", text)
        self.assertIn("vfops-auto-backup", text)
        self.assertIn("vfops-cloudpanel-ui", text)
        self.assertIn('run_module "$CLOUDPANEL_UI" site', text)
        self.assertIn('run_module "$CLOUDPANEL_UI" admin', text)
        self.assertIn("backup_menu()", text)
        self.assertIn("立即备份一个网站", text)
        self.assertIn("从备份恢复网站", text)
        self.assertIn("自动备份与异地备份", text)
        self.assertNotIn('8) run_module "$DIAG_UI"', text)
        self.assertNotIn('10) run_module "$SELFCHECK_UI"', text)
        self.assertIn("--advanced", text)

    def test_restore_ui_exposes_restore_as_and_preserves_no_overwrite(self) -> None:
        text = (ROOT / "bin/vfops-site-ui").read_text(encoding="utf-8")
        self.assertIn("恢复为新网站（推荐，可在本机测试）", text)
        self.assertIn("RESTORE_AS:", text)
        self.assertIn("restore_as_verified.py", text)
        self.assertIn("恢复后会先验证文件、数据库和 Nginx 配置", text)
        self.assertIn("网站 Nginx 正在运行时，再做 Host / SNI 在线验证", text)
        self.assertIn("不会自动启动或重启", text)
        self.assertIn("只做离线恢复验证", text)
        self.assertIn("无需先在 CloudPanel 手工创建空网站", text)
        self.assertIn("按原域名恢复", text)
        self.assertIn("不会覆盖", text)
        self.assertIn("DNS：未修改", text)

    def test_restore_ui_persists_secret_safe_result_evidence(self) -> None:
        text = (ROOT / "bin/vfops-site-ui").read_text(encoding="utf-8")
        self.assertIn("VFOPS_EVIDENCE_DIR", text)
        self.assertIn("/var/lib/vf-server-ops/evidence/restore-as", text)
        self.assertIn('install -d -m 700 "$EVIDENCE_DIR"', text)
        self.assertIn('install -m 600 "$result_file" "$evidence_file"', text)
        for marker in (
            "P07_RESTORE_AS_VERIFIED=",
            "P07_RESTORE_SOURCE_DOMAIN=",
            "P07_RESTORE_TARGET_DOMAIN=",
            "P07_RESTORE_LOCAL_VERIFY=",
            "P07_RESTORE_TLS_MODE=",
            "P07_RESTORE_DNS_CHANGED=0",
            "P07_RESTORE_SOURCE_DELETED=0",
            "P07_RESTORE_EXISTING_TARGET_OVERWRITE=0",
            "P07_RESTORE_EVIDENCE=",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("P07_R1_RESTORE_AS=PASS", text)
        self.assertNotIn("REAL_PASS", text)

    def test_restore_ui_preserves_selection_return_codes(self) -> None:
        text = (ROOT / "bin/vfops-site-ui").read_text(encoding="utf-8")
        self.assertNotIn("if ! select_site; then rc=$?", text)
        self.assertNotIn("if ! select_backup; then rc=$?", text)
        self.assertIn("if select_site; then", text)
        self.assertIn("if select_backup; then", text)
        self.assertIn("[[ $rc -eq 2 ]] && return 0", text)

    def test_cloudpanel_tools_complete_bundle_preserves_no_delete_boundary(self) -> None:
        paths = [
            ROOT / "bin/vfops-cloudpanel-ui",
            ROOT / "lib/cloudpanel_ui_common.sh",
            ROOT / "lib/cloudpanel_ui_sites.sh",
            ROOT / "lib/cloudpanel_ui_ops.sh",
            ROOT / "lib/cloudpanel_ui_admin.sh",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for marker in (
            "网站创建与维护",
            "数据库清单",
            "新增数据库",
            "HTTPS 证书状态",
            "修复网站权限",
            "清理网站缓存（Varnish）",
            "面板账号与安全（CloudPanel）",
            "面板登录安全",
            "面板用户",
            "网站配置模板（Vhost）· 高级",
        ):
            self.assertIn(marker, text)
        parent = (ROOT / "bin/vfops-cloudpanel-ui").read_text(encoding="utf-8")
        self.assertNotIn("  4. Vhost 模板", parent)
        self.assertIn("网站底层配置由 CloudPanel 和工具自动处理", parent)
        for forbidden in (
            "site:delete",
            "db:delete",
            "user:delete",
            "cloudpanel.delete_site",
            "cloudpanel.delete_database",
            "cloudpanel.delete_panel_user",
        ):
            self.assertNotIn(forbidden, text)

    def test_cloudpanel_site_management_selects_once_and_can_change_explicitly(self) -> None:
        parent = (ROOT / "bin/vfops-cloudpanel-ui").read_text(encoding="utf-8")
        common = (ROOT / "lib/cloudpanel_ui_common.sh").read_text(encoding="utf-8")
        self.assertIn("管理已有网站", parent)
        self.assertIn("创建新网站", parent)
        self.assertIn("ui_menu_info 3 '数据库'", parent)
        self.assertIn("ui_menu_info 4 '网站证书（HTTPS）'", parent)
        self.assertIn("ui_menu_warn 5 '权限与缓存'", parent)
        self.assertIn("ui_menu_flow 98 '更换网站'", parent)
        self.assertIn('SELECTED_DOMAIN=""', common)
        self.assertIn('if [[ -n "$SELECTED_DOMAIN" ]]', common)

    def test_migration_ui_prioritizes_target_pull_and_resume(self) -> None:
        text = (ROOT / "bin/vfops-migrate-ui").read_text(encoding="utf-8")
        for marker in (
            "服务器迁移",
            "当前：",
            "这台新服务器（接收数据）",
            "迁入整台旧服务器",
            "迁入一个网站",
            "继续未完成迁移",
            "旧服务器 IP",
            "server-migrate prepare",
            "server-migrate resume",
            "server-migrate cutover",
            "server-migrate finalize",
            "新服务器开始从旧服务器复制数据",
            "旧服务器：继续保留为恢复副本",
            "PREPARE_PULL_MIGRATION",
            "CUTOVER_PULL:",
            "请返回一级菜单 → 5. 初始化服务器",
            "迁移流程本身不再负责安装或初始化服务器",
            "非网站面板管理的公网服务",
            "旧服务器网站开关",
            "开启这台服务器全部网站",
            "停止这台服务器全部网站",
            "仅在旧服务器上使用；直接操作当前机器，不需要输入 IP",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("目标服务器 IP", text)
        self.assertNotIn("回滚 Runtime 到 SOURCE", text)
        self.assertNotIn("DNS：自动修改", text)
        start = text.index("old_server_nginx_control()")
        end = text.index("select_existing_migration()", start)
        ordinary = text[start:end]
        self.assertNotIn("nginx.service", ordinary)
        self.assertNotIn("clp-nginx.service", ordinary)
        self.assertNotIn("systemctl", ordinary)
        self.assertNotIn("nginx -t", ordinary)
        self.assertNotIn("80/443", ordinary)
        self.assertNotIn("8443", ordinary)
        self.assertNotIn("read_old_ip", ordinary)
        self.assertNotIn("OLD_SERVER_IP", ordinary)
        self.assertIn("local-nginx-status", ordinary)
        self.assertIn("local-nginx-start", ordinary)
        self.assertIn("local-nginx-stop", ordinary)
        self.assertIn("确认开启？[y/N]", ordinary)
        self.assertIn("确认停止？[y/N]", ordinary)
        self.assertNotIn("ui_confirm_exact 开启", ordinary)
        self.assertNotIn("ui_confirm_exact 停止", ordinary)
        self.assertNotIn("BOOTSTRAP_LOCAL_CLOUDPANEL", text)


    def test_initialization_repairs_known_cloudpanel_608_shebang(self) -> None:
        init = (ROOT / "bin/vfops-init-ui").read_text(encoding="utf-8")
        self.assertIn("repair_cloudpanel_cli_shebang_for_init()", init)
        self.assertIn("[[ \"$first_line\" == '#/bin/bash' ]] || return 0", init)
        self.assertIn("b\"#!/bin/bash\"", init)
        self.assertIn("cp -a -- \"$clpctl_path\" \"$backup_path\"", init)
        self.assertIn("bash -n \"$tmp\"", init)
        self.assertIn("mv -f -- \"$tmp\" \"$clpctl_path\"", init)
        self.assertIn("CloudPanel CLI 已修复官方 6.0.8 启动行错误", init)
        self.assertNotIn("P07_FRESH_INIT_EMPTY_SERVER", init)
        self.assertNotIn("systemctl restart mysql", init)

    def test_resource_apply_accepts_structured_credentials_from_nonzero_wrapper(self) -> None:
        path = ROOT / "components/resource-tuning/lib/resource_apply.py"
        if not path.is_file():
            self.skipTest("source-only canonical tuning component is not shipped in runtime overlay")
        spec = importlib.util.spec_from_file_location("resource_apply_release52", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        table = """+-----------+-----------+
| Name      | Value     |
+-----------+-----------+
| Host      | 127.0.0.1 |
| User Name | root      |
| Password  | secret    |
| Port      | 3306      |
+-----------+-----------+
"""
        failed = subprocess.CompletedProcess(["first"], 1, stdout="", stderr="wrapper error")
        usable = subprocess.CompletedProcess(["second"], 1, stdout=table, stderr="warning")
        with mock.patch.object(
            mod,
            "_clpctl_commands",
            return_value=[["first"], ["second"]],
        ), mock.patch.object(
            mod,
            "_run_clp_probe",
            side_effect=[failed, usable],
        ):
            self.assertEqual(
                mod._try_clp_credentials(),
                ("root", "secret", "127.0.0.1", 3306),
            )

    def test_resource_apply_handles_cloudpanel_608_bash_wrapper(self) -> None:
        path = ROOT / "components/resource-tuning/lib/resource_apply.py"
        if not path.is_file():
            self.skipTest("source-only canonical tuning component is not shipped in runtime overlay")
        spec = importlib.util.spec_from_file_location("resource_apply_release51", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        def which(name: str):
            return {"clpctl": "/usr/bin/clpctl", "bash": "/bin/bash"}.get(name)

        with mock.patch.object(mod.shutil, "which", side_effect=which), \
             mock.patch.object(mod.Path, "read_text", return_value="#/bin/bash\nprintf '%q'\n"):
            self.assertEqual(
                mod._clpctl_command("db:show:master-credentials"),
                ["/bin/bash", "/usr/bin/clpctl", "db:show:master-credentials"],
            )

        with mock.patch.object(mod.shutil, "which", side_effect=which), \
             mock.patch.object(mod.Path, "read_text", return_value="#!/usr/bin/env python3\n"):
            self.assertEqual(
                mod._clpctl_command("db:show:master-credentials"),
                ["/usr/bin/clpctl", "db:show:master-credentials"],
            )

    def test_resource_apply_retries_fresh_cloudpanel_readiness_only(self) -> None:
        path = ROOT / "components/resource-tuning/lib/resource_apply.py"
        if not path.is_file():
            self.skipTest("source-only canonical tuning component is not shipped in runtime overlay")
        spec = importlib.util.spec_from_file_location("resource_apply_release50", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        ready = (["mysql"], {"MYSQL_PWD": "ephemeral"})
        with mock.patch.object(
            mod,
            "_mysql_client_once",
            side_effect=[mod.ApplyBlocked("MYSQL_MASTER_CREDENTIAL_PARSE_FAILED"), ready],
        ) as probe, mock.patch.object(mod.time, "sleep") as sleeper:
            self.assertEqual(mod._mysql_client(), ready)
        self.assertEqual(probe.call_count, 2)
        sleeper.assert_called_once_with(mod.MYSQL_READY_RETRY_DELAY_SECONDS)

        with mock.patch.object(
            mod,
            "_mysql_client_once",
            side_effect=mod.ApplyBlocked("MYSQL_MASTER_CREDENTIAL_LOOKUP_TIMEOUT"),
        ) as probe, mock.patch.object(mod.time, "sleep") as sleeper:
            with self.assertRaises(mod.ApplyBlocked) as ctx:
                mod._mysql_client()
        self.assertEqual(str(ctx.exception), "MYSQL_MASTER_CREDENTIAL_LOOKUP_TIMEOUT")
        self.assertEqual(probe.call_count, 1)
        sleeper.assert_not_called()

    def test_server_initialization_is_standalone_and_uses_yes_no(self) -> None:
        user = (ROOT / "bin/vfops-user").read_text(encoding="utf-8")
        init = (ROOT / "bin/vfops-init-ui").read_text(encoding="utf-8")
        canonical_apply_path = ROOT / "components/resource-tuning/resource-apply.sh"
        canonical_profile_path = ROOT / "components/resource-tuning/resource-profile.sh"
        canonical_apply = canonical_apply_path.read_text(encoding="utf-8") if canonical_apply_path.is_file() else ""
        canonical_profile = canonical_profile_path.read_text(encoding="utf-8") if canonical_profile_path.is_file() else ""
        self.assertIn('exec bash "$INIT_UI"', user)
        self.assertIn("--init", user)
        self.assertIn("初始化服务器", init)
        self.assertIn("一键初始化服务器（推荐）", init)
        self.assertIn("请选择 [0-1]", init)
        self.assertNotIn("ui_menu_warn 2 '基础设置（时区 / Swap）'", init)
        self.assertNotIn("ui_menu_warn 3 'CloudPanel 状态 / 安装'", init)
        self.assertNotIn("请选择 [0-3]", init)
        self.assertIn("确认开始一键初始化？[y/N]", init)
        self.assertIn("2/5 系统更新", init)
        self.assertIn("1/5 基础设置", init)
        self.assertIn("3/5 CloudPanel", init)
        self.assertIn("4/5 性能配置", init)
        self.assertIn("5/5 最终检查", init)
        self.assertIn("resource-profile.sh", init)
        self.assertIn("resource-apply.sh", init)
        self.assertIn("apply-confirmed-json", init)
        self.assertIn("P07_RESOURCE_APPLY_CONFIRMED=1", init)
        self.assertIn("repair_cloudpanel_cli_shebang_for_init()", init)
        self.assertIn("[[ \"$first_line\" == '#/bin/bash' ]] || return 0", init)
        self.assertIn("CloudPanel CLI 已修复官方 6.0.8 启动行错误", init)
        self.assertNotIn("P07_FRESH_INIT_EMPTY_SERVER", init)
        self.assertNotIn("systemctl restart mysql", init)
        self.assertIn("plan-json --mode balanced", init)
        self.assertNotIn("lib/resource_profile.py", init)
        self.assertNotIn("lib/resource_apply.py", init)
        self.assertIn("检测到已有网站运行配置", init)
        self.assertIn("初始化只给资源建议，不自动改现有站点参数", init)
        self.assertIn("本次初始化执行清单", init)
        self.assertIn("DNS 未修改；旧服务器未删除；网站迁移未执行；网站 Nginx 未自动停止或重启", init)
        self.assertIn("服务器初始化完成", init)
        self.assertIn("resource_block_reason_cn", init)
        self.assertIn("当前 MySQL 配置结构与已校准模板不同", init)
        self.assertIn("resource_result_complete", init)
        self.assertIn("性能配置未闭环", init)
        self.assertIn("无法从 CloudPanel 读取本机数据库连接信息", init)
        self.assertIn("CloudPanel 数据库连接信息读取超时", init)
        self.assertIn("run_resource_apply_with_progress", init)
        self.assertIn("初始化不再维护第二套调优逻辑", init)
        self.assertIn("性能配置处理中 · 已耗时", init)
        self.assertIn("低配服务器可能需要几十秒", init)
        self.assertIn("已读取到 CloudPanel 本机数据库连接信息，但本机连接验证失败", init)
        self.assertIn("未找到 MySQL / Percona 服务程序", init)
        self.assertNotIn("重新执行初始化检查（推荐）", init)
        self.assertNotIn("初始化 / 重新初始化服务器（推荐）", init)
        self.assertNotIn("CloudPanel 尚未安装，确认现在安装？[y/N]", init)
        self.assertNotIn("输入 APPLY_BASELINE", init)
        self.assertNotIn("输入 INSTALL_CLOUDPANEL", init)
        self.assertIn("/^SwapTotal:/", init)
        if canonical_apply_path.is_file():
            self.assertIn("plan-json", canonical_apply)
            self.assertIn("apply-confirmed-json", canonical_apply)
            self.assertIn("P07_RESOURCE_APPLY_CONFIRMED", canonical_apply)
            self.assertIn("--confirmed-noninteractive", canonical_apply)
            canonical_engine = (ROOT / "components/resource-tuning/lib/resource_apply.py").read_text(encoding="utf-8")
            self.assertIn('require_tty: bool = True', canonical_engine)
            self.assertIn('OWNER_CONFIRMATION_BRIDGE_REQUIRED', canonical_engine)
            self.assertIn('require_tty=not args.confirmed_noninteractive', canonical_engine)
            self.assertIn('ENGINE="$SCRIPT_DIR/lib/resource_apply.py"', canonical_apply)
            self.assertIn('ENGINE="$SCRIPT_DIR/lib/resource_profile.py"', canonical_profile)
        self.assertEqual(init.count("lib/resource_apply.py"), 0)
        self.assertEqual(init.count("lib/resource_profile.py"), 0)


    def test_beginner_surfaces_hide_project_code_and_group_site_tools(self) -> None:
        paths = [
            ROOT / "bin/vfops-user",
            ROOT / "bin/vfops-site-ui",
            ROOT / "bin/vfops-migrate-ui",
            ROOT / "bin/vfops-cloudpanel-ui",
            ROOT / "bin/vfops-auto-backup",
            ROOT / "bin/vfops-init-ui",
            ROOT / "bin/vfops-diagnostics-ui",
            ROOT / "bin/vfops-selfcheck-ui",
            ROOT / "bin/vfops-history-ui",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertNotIn("P07 ·", text)
        self.assertIn("网站与数据概况", text)
        self.assertIn("服务器健康检查", text)
        self.assertIn("工具检查 / 修复", text)
        self.assertIn("面板账号与安全（CloudPanel）", text)

    def test_migration_preserves_old_server_dns_and_target_collision_boundaries(self) -> None:
        ui = (ROOT / "bin/vfops-migrate-ui").read_text(encoding="utf-8")
        engine = (ROOT / "lib/server_migration_pull.py").read_text(encoding="utf-8")
        self.assertIn("新服务器已有资源不覆盖", ui)
        self.assertIn("DNS 不自动修改", ui)
        self.assertIn("旧服务器永不自动删除", ui)
        self.assertIn("ssh-copy-id", ui)
        self.assertIn("existing_target_overwrite_allowed", engine)
        self.assertIn("source_delete_allowed", engine)
        self.assertIn("dns_changed_by_p07", engine)
        self.assertIn("CURRENT_SERVER_PULLS_OLD_SERVER", engine)


if __name__ == "__main__":
    unittest.main()
