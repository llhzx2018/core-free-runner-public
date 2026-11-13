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
        self.assertIn("\\n  vfops\\n",fragment)
        for historical in ("run_server_ops_owner124_trial",
                           "run_server_ops_owner143_trial",
                           "release124","release143"):
            self.assertNotIn(historical,fragment)
        self.assertNotIn("read -r",fragment)
        self.assertNotIn("请选择 [0-3]",fragment)

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
