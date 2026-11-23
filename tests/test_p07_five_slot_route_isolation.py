"""P07 五个主模块的公共单入口分发边界静态负例。

Only verifies the selected-module dispatch surface. Individual installer
runtime effects, remote dependencies and Production require separate proof.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "installers/p07-toolbox.sh"

SLOTS = {
    "P07-M01 网络代理节点（V2Ray）": ("run_network_node", "M01_RUNTIME"),
    "P07-M02 服务器性能检测（VPS 验机）": ("run_vps_audit", "M02_ROOT"),
    "P07-M03 网站与数据": ("run_server_ops", "ensure_server_ops_current"),
    "P07-M04 服务器维护与安全": ("run_system_care", "M04_RUNTIME"),
    "P07-M05 新服务器初始化": ("run_server_init", "M05_RUNTIME"),
}

CROSS_MODULE_INSTALLERS = (
    "ensure_server_ops_current", "ensure_system_care_current",
    "VF_NODE_INSTALLER", "M01_RUNTIME", "VPS_AUDIT_URL", "M02_ROOT", "M04_RUNTIME", "M05_RUNTIME",
)


def body_of(source: str, function: str) -> str:
    begin = re.search(r"^" + re.escape(function) + r"\(\) \{\s*$", source, re.M)
    if not begin:
        raise AssertionError("module entry function missing: " + function)
    closing = re.search(r"^}\s*$", source[begin.end():], re.M)
    if not closing:
        raise AssertionError("module function closing delimiter missing: " + function)
    return source[begin.start():begin.end()+closing.end()]


def enforce_dispatch_surface(source: str) -> None:
    for title, (fn, owned) in SLOTS.items():
        fragment = body_of(source, fn)
        if owned not in fragment:
            raise AssertionError(title + " has no owned executable/installer")
        for foreign in CROSS_MODULE_INSTALLERS:
            if foreign != owned and foreign in fragment:
                raise AssertionError(title + " installs/executes foreign module: " + foreign)
    menu = body_of(source, "main_menu")
    for selected in ("run_network_node", "run_vps_audit",
                     "run_server_ops", "run_system_care", "run_server_init"):
        if menu.count(selected) != 1:
            raise AssertionError("main Toolbox module routing changed: " + selected)


class FiveIndependentToolboxSlots(unittest.TestCase):
    def test_exact_five_module_routes_have_no_cross_installers(self):
        enforce_dispatch_surface(SOURCE.read_text(encoding="utf-8"))

    def test_forged_cross_module_upgrade_is_rejected(self):
        source = SOURCE.read_text(encoding="utf-8")
        fragment = body_of(source, "run_server_init")
        mutated = source.replace(fragment, fragment.replace(
            "  screen_clear", "  screen_clear\n  ensure_server_ops_current\n",
            1,
        ), 1)
        with self.assertRaisesRegex(AssertionError, "foreign module"):
            enforce_dispatch_surface(mutated)

    def test_toolbox_still_has_all_five_chinese_visible_names(self):
        source = SOURCE.read_text(encoding="utf-8")
        for title in ("网络代理节点", "服务器性能检测",
                      "网站与数据", "服务器维护与安全", "新服务器初始化"):
            self.assertIn(title, body_of(source, "show_menu"))

    def test_m03_default_route_is_stable_only_not_historical_trial(self):
        source = SOURCE.read_text(encoding="utf-8")
        fragment = body_of(source, "run_server_ops")
        self.assertIn("ensure_server_ops_current || return $?",fragment)
        self.assertIn("\n  vfops\n",fragment)
        for historical in ("run_server_ops_owner124_trial",
                           "run_server_ops_owner143_trial",
                           "release124","release143"):
            self.assertNotIn(historical,fragment)
        self.assertNotIn("read -r",fragment)
        self.assertNotIn("请选择 [0-3]",fragment)

    def test_m03_owner_trial_only_on_explicit_selected_branch(self):
        source = SOURCE.read_text(encoding="utf-8")
        menu = body_of(source,"main_menu")
        self.assertEqual(menu.count("run_server_ops"),1)
        self.assertEqual(menu.count("run_m03_owner_trial"),1)
        self.assertIn('read -r m03_choice',menu)
        self.assertIn('case "$m03_choice" in',menu)
        self.assertIn('1)\n            set +e\n            run_server_ops',menu)
        self.assertIn('2)\n            set +e\n            run_m03_owner_trial',menu)
        self.assertIn('0) continue ;;',menu)
        trial = body_of(source,"run_m03_owner_trial")
        self.assertIn('m03_verified_owner_trial',trial)
        self.assertIn('[[ -t 0 && -t 1 ]]',trial)
        self.assertIn('read -r answer',trial)
        self.assertIn('[[ "$answer" =~ ^[Yy]$ ]]',trial)
        self.assertIn('P07_INSTALL_DIR="$M03_OWNER_TRIAL_ROOT"',trial)
        self.assertIn('P07_BIN_LINK="$M03_OWNER_TRIAL_BIN"',trial)
        self.assertIn('P07_TOOLBOX_PARENT=1',trial)
        self.assertIn('M03_OWNER_TRIAL_INSTALLER_BLOB',trial)
        self.assertIn('m03_verified_owner_trial ||',trial)
        self.assertNotIn('ensure_server_ops_current',trial)
        self.assertNotIn('VF_SERVER_OPS_INSTALLER',trial)
        self.assertNotIn('P07_INSTALL_DIR="/opt/vf-server-ops"',trial)
    def test_owner_trial_main_menu_five_slots_unchanged(self):
        src = SOURCE.read_text(encoding="utf-8")
        menu = body_of(src, "show_menu")
        for title in ("网络代理节点", "服务器性能检测", "网站与数据",
                      "服务器维护与安全", "新服务器初始化"):
            self.assertIn(title,menu)
        self.assertIn("功能：5 项",menu)
        route=body_of(src,"main_menu")
        self.assertEqual(route.count("run_server_ops"),1)
        self.assertEqual(route.count("run_m03_owner_trial"),1)

    def test_owner_trial_readonly_stable_build_unchanged(self):
        src=SOURCE.read_text(encoding="utf-8")
        self.assertIn('VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release146"',src)
        self.assertIn('M03_OWNER_TRIAL_BUILD="0.1.0-release147-rc2"',src)
        self.assertIn('M03_OWNER_TRIAL_ROOT="/opt/vf-server-ops-ownertrial147rc2"',src)
        self.assertIn('M03_OWNER_TRIAL_BIN="/usr/local/bin/vfops-rc147rc2"',src)
        self.assertIn('M03_OWNER_TRIAL_MANIFEST_BLOB=',src)

    def test_owner_trial_write_confirmation_required(self):
        src=SOURCE.read_text(encoding="utf-8")
        body=body_of(src,"run_m03_owner_trial")
        self.assertIn('[[ -t 0 && -t 1 ]]',body)
        self.assertIn('read -r answer',body)
        self.assertIn('[[ "$answer" =~ ^[Yy]$ ]]',body)
        self.assertIn('P07_TOOLBOX_PARENT=1 P07_NO_EXEC=1',body)

    def test_owner_trial_cancel_eof_invalid_no_write(self):
        src=SOURCE.read_text(encoding="utf-8")
        route=body_of(src,"main_menu")
        self.assertIn('read -r m03_choice || return 0',route)
        self.assertIn('0) continue ;;',route)
        self.assertIn("无效选择，未修改服务器",route)
        body=body_of(src,"run_m03_owner_trial")
        self.assertIn("已取消；正式版不变",body)
        self.assertLess(body.index('read -r answer'),body.index('curl --proto'))

    def test_owner_trial_success_must_verify_full_runtime(self):
        src=SOURCE.read_text(encoding="utf-8")
        body=body_of(src,"run_m03_owner_trial")
        self.assertIn('m03_verified_owner_trial ||',body)
        self.assertIn('已校验隔离试用版安装',body)
        verified=body_of(src,"m03_verified_owner_trial")
        self.assertIn('M03_OWNER_TRIAL_MANIFEST_BLOB',verified)
        self.assertIn('p07_git_blob_sha1',verified)
        self.assertIn('bin/vfops-user',verified)

    def test_owner_trial_failure_block_preserves_stable(self):
        src=SOURCE.read_text(encoding="utf-8")
        body=body_of(src,"run_m03_owner_trial")
        self.assertIn('M03_OWNER_TRIAL_INSTALLER_BLOB',body)
        self.assertIn('拒绝覆盖，请保留现场',body)
        self.assertIn('试用包安装失败，请保留现场；正式版不变',body)
        wrapper=(SOURCE.parent/"p07-m03-ownertrial147rc2-atomic.sh").read_text()
        self.assertIn('P07_INSTALL_DIR:-',wrapper)
        self.assertIn('/opt/vf-server-ops-ownertrial147rc2',wrapper)
        self.assertIn('P07_TOOLBOX_PARENT:-0',wrapper)
        self.assertNotIn('P07_INSTALL_DIR:-/opt/vf-server-ops}',wrapper)

    def test_unsafe_rc1_new_installs_are_revoked_without_deleting_old_runtime(self):
        retired=(SOURCE.parent/"p07-m03-ownertrial147-atomic.sh").read_text()
        self.assertIn("已停止分发",retired)
        self.assertIn("exit 13",retired.split("MODULE='P07-M03'")[0])
        self.assertNotIn("rm -rf",retired.split("MODULE='P07-M03'")[0])
        src=SOURCE.read_text(encoding="utf-8")
        self.assertNotIn('M03_OWNER_TRIAL_INSTALLER_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-m03-ownertrial147-atomic.sh"',src)

    def test_rc2_is_new_root_and_keeps_rc1_field_evidence(self):
        src=SOURCE.read_text(encoding="utf-8")
        self.assertIn("旧 147-rc1 曾在全选22站",src)
        self.assertIn("原来的失败任务和旧试用目录均保留",src)
        self.assertIn('M03_OWNER_TRIAL_BIN="/usr/local/bin/vfops-rc147rc2"',src)
        self.assertNotIn('M03_OWNER_TRIAL_ROOT="/opt/vf-server-ops-ownertrial147"',src)
        wrapper=(SOURCE.parent/"p07-m03-ownertrial147rc2-atomic.sh").read_text()
        self.assertIn("0.1.0-release147-rc2",wrapper)
        self.assertIn("/opt/vf-server-ops-ownertrial147rc2",wrapper)
        self.assertIn("/usr/local/bin/vfops-rc147rc2",wrapper)
        self.assertIn("P07_TOOLBOX_PARENT:-0",wrapper)
        self.assertIn("09406d27e47ad2f1946cc129e9492fc009b30e278b0ae65df56775a145244c0d",wrapper)

    def test_owner_trial_no_color_non_tty_and_zero_loading(self):
        src=SOURCE.read_text(encoding="utf-8")
        route=body_of(src,"main_menu")
        self.assertIn("只在选定操作后下载安装",route)
        body=body_of(src,"run_m03_owner_trial")
        self.assertIn("交互式 SSH 终端确认",body)
        self.assertIn('[[ -t 0 && -t 1 ]]',body)
        self.assertIn('NO_COLOR=1',body_of(src,"m03_verified_owner_trial"))
        self.assertIn("C_RESET=''",src)

    def test_main_entry_does_not_install_all_modules_on_start(self):
        source = SOURCE.read_text(encoding="utf-8")
        startup = source[:source.index("main_menu() {")]
        # Presence of definitions is okay; only top-level invocation of an
        # installer when launching the menu is forbidden.
        epilogue = source[source.index("case \"${1:-}\" in"):]
        self.assertNotIn("ensure_server_ops_current", epilogue)
        self.assertNotIn("ensure_system_care_current", epilogue)


if __name__ == "__main__":
    unittest.main()
