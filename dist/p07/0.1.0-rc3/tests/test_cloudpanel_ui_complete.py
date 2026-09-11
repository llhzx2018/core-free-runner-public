from __future__ import annotations

from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
PARENT = REPO_ROOT / "bin" / "vfops-cloudpanel-ui"
HELPERS = [
    REPO_ROOT / "lib" / "cloudpanel_ui_common.sh",
    REPO_ROOT / "lib" / "cloudpanel_ui_sites.sh",
    REPO_ROOT / "lib" / "cloudpanel_ui_ops.sh",
    REPO_ROOT / "lib" / "cloudpanel_ui_admin.sh",
]


class CloudPanelCompleteUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parent = PARENT.read_text(encoding="utf-8")
        cls.helpers = "\n".join(path.read_text(encoding="utf-8") for path in HELPERS)
        cls.all_text = cls.parent + "\n" + cls.helpers

    def test_complete_task_groups_are_exposed(self) -> None:
        for label in (
            "网站详情",
            "网站健康检查",
            "创建网站",
            "数据库工具",
            "SSL / HTTPS",
            "权限 / 缓存",
            "CloudPanel 安全",
            "CloudPanel 用户",
            "Vhost 模板",
            "平台基础能力检查",
        ):
            self.assertIn(label, self.parent)

    def test_parent_is_thin_and_sources_bounded_helpers(self) -> None:
        self.assertLess(len(self.parent.splitlines()), 80)
        for helper in (
            "cloudpanel_ui_common.sh",
            "cloudpanel_ui_sites.sh",
            "cloudpanel_ui_ops.sh",
            "cloudpanel_ui_admin.sh",
        ):
            self.assertIn(helper, self.parent)

    def test_all_supported_site_types_are_wired(self) -> None:
        for adapter in (
            "cloudpanel.add_php_site",
            "cloudpanel.add_static_site",
            "cloudpanel.add_nodejs_site",
            "cloudpanel.add_python_site",
            "cloudpanel.add_reverse_proxy_site",
        ):
            self.assertIn(adapter, self.helpers)

    def test_database_ssl_security_user_template_adapters_are_wired(self) -> None:
        for adapter in (
            "cloudpanel.add_database",
            "cloudpanel_site.export_database",
            "cloudpanel_site.import_database",
            "cloudpanel.install_lets_encrypt",
            "cloudpanel.install_certificate",
            "cloudpanel_site.reset_permissions",
            "cloudpanel_site.purge_varnish",
            "cloudpanel.enable_panel_basic_auth",
            "cloudpanel.disable_panel_basic_auth",
            "cloudpanel.update_cloudflare_ips",
            "cloudpanel.list_panel_users",
            "cloudpanel.add_panel_user",
            "cloudpanel.reset_panel_user_password",
            "cloudpanel.disable_panel_user_mfa",
            "cloudpanel.list_vhost_templates",
            "cloudpanel.import_vhost_templates",
            "cloudpanel.view_vhost_template",
            "cloudpanel.add_vhost_template",
        ):
            self.assertIn(adapter, self.helpers)

    def test_destructive_delete_actions_are_not_exposed(self) -> None:
        for forbidden in (
            "site:delete",
            "db:delete",
            "user:delete",
            "cloudpanel.delete_site",
            "cloudpanel.delete_database",
            "cloudpanel.delete_panel_user",
        ):
            self.assertNotIn(forbidden, self.all_text)

    def test_dns_source_and_target_boundaries_are_explicit(self) -> None:
        self.assertIn("不自动修改 DNS", self.parent)
        self.assertIn("不删除 SOURCE", self.parent)
        self.assertIn("不覆盖已有 TARGET", self.parent)
        for forbidden in ("update_dns", "write_dns", "set_dns", "delete_dns"):
            self.assertNotIn(forbidden, self.all_text)

    def test_passwords_are_silent_and_not_passed_as_cli_arguments(self) -> None:
        self.assertIn("read -r -s", self.helpers)
        self.assertIn('P07_SECRET="$SECRET_VALUE"', self.helpers)
        self.assertIn("os.environ.pop('P07_SECRET')", self.helpers)
        self.assertNotIn("REAL_PASS", self.all_text)

    def test_site_collision_is_checked_before_creation(self) -> None:
        self.assertIn('site_domain_exists "$domain"', self.helpers)
        self.assertIn("TARGET 已存在，P07 不会覆盖", self.helpers)

    def test_health_check_is_local_without_hosts_or_dns_mutation(self) -> None:
        self.assertIn('--resolve "$domain:80:127.0.0.1"', self.helpers)
        self.assertIn('--resolve "$domain:443:127.0.0.1"', self.helpers)
        self.assertIn("不修改 DNS、不修改 hosts", self.helpers)


if __name__ == "__main__":
    unittest.main()
