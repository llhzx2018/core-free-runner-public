from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

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
            "1. 服务器 / 网站概览",
            "2. 备份网站",
            "3. 恢复网站",
            "4. 服务器迁移（整机 / 单站）",
            "5. 自动备份 / 远程灾备",
            "6. 网站管理",
            "7. CloudPanel 管理",
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
        self.assertIn("--advanced", text)

    def test_restore_ui_exposes_restore_as_and_preserves_no_overwrite(self) -> None:
        text = (ROOT / "bin/vfops-site-ui").read_text(encoding="utf-8")
        self.assertIn("恢复为新网站（推荐，可在本机测试）", text)
        self.assertIn("RESTORE_AS:", text)
        self.assertIn("restore_as_verified.py", text)
        self.assertIn("自动完成本机文件、数据库、Host 与 SNI/vhost 验证", text)
        self.assertIn("失败会回滚本次新建目标", text)
        self.assertIn("无需先在 CloudPanel 手工创建空网站", text)
        self.assertIn("按原域名恢复", text)
        self.assertIn("P07 不会覆盖", text)
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
            "网站管理",
            "数据库清单",
            "新增数据库",
            "SSL 状态",
            "修复网站权限",
            "清理 Varnish 缓存",
            "CloudPanel 管理",
            "CloudPanel 安全",
            "CloudPanel 用户",
            "Vhost Templates（高级）",
        ):
            self.assertIn(marker, text)
        parent = (ROOT / "bin/vfops-cloudpanel-ui").read_text(encoding="utf-8")
        self.assertNotIn("  4. Vhost 模板", parent)
        self.assertIn("Vhost 模板由 CloudPanel / P07 自动处理", parent)
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
        self.assertIn("网站只选择一次", parent)
        self.assertIn("98. 更换网站", parent)
        self.assertIn("0. 返回 P07 主菜单", parent)
        self.assertIn('SELECTED_DOMAIN=""', common)
        self.assertIn('if [[ -n "$SELECTED_DOMAIN" ]]', common)

    def test_migration_ui_prioritizes_resumable_whole_server_path(self) -> None:
        text = (ROOT / "bin/vfops-migrate-ui").read_text(encoding="utf-8")
        for marker in (
            "整机迁移（推荐）",
            "继续已有整机迁移",
            "全 Home SQLite",
            "唯一人工 Gate：现在修改 DNS",
            "server-migrate prepare",
            "server-migrate resume",
            "server-migrate cutover",
            "server-migrate finalize",
            "SOURCE 继续保留作为 Recovery Copy（恢复副本）",
            "P07 专用临时 Key",
            "RETAINED_FOR_RECOVERY",
            "结束 Recovery 保护并清理 P07 专用迁移 Key",
            "CLEANUP_MANAGED_SSH_KEY:",
            "只删除 P07 自己创建的迁移 Key",
            "Recovery / 清理通道",
            "TARGET → SOURCE 数据对账/反向同步",
            "不提供“只开旧机”的一键回滚",
            "CUTOVER_RUNNING",
            "最终切换已从断点继续完成",
            "自动安装 CloudPanel",
            "BOOTSTRAP_CLOUDPANEL:",
            "MySQL 8.4",
            "SOURCE 额外公网服务",
            "非 CloudPanel 公网服务",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("回滚 Runtime 到 SOURCE", text)
        self.assertNotIn("SOURCE 可安全识别的公网地址", text)
        self.assertNotIn("DNS：自动修改", text)
        self.assertIn("DNS：不会自动修改", text)

    def test_migration_preserves_source_dns_and_target_collision_boundaries(self) -> None:
        text = (ROOT / "bin/vfops-migrate-ui").read_text(encoding="utf-8")
        self.assertIn("TARGET_SITE_CONFLICT", text)
        self.assertIn("P07 不会覆盖", text)
        self.assertIn("DNS：未修改", text)
        self.assertIn("SOURCE：保留", text)
        self.assertIn("ssh-copy-id", text)


if __name__ == "__main__":
    unittest.main()
