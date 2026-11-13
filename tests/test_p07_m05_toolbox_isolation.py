"""P07-M05 新服务器初始化 Toolbox 路由隔离负例。

Tests operate on Bash function extracted from THIS candidate public toolbox.
No root, network, VPS, installers, or real module directories touched.
"""
from __future__ import annotations

from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
TOOLBOX = HERE / "installers/p07-toolbox.sh"


def m05_body(source: str) -> str:
    start = source.find("run_server_init() {\n")
    end = source.find("\nlocal_system_care_version() {", start)
    if start == -1 or end == -1:
        raise AssertionError("P07-M05 tool dispatcher missing")
    return source[start:end]


def assert_independent(body: str) -> None:
    for prohibited in (
        "ensure_server_ops_current", "ensure_system_care_current",
        "server_ops_root", "P07_SYSTEM_CARE_ROOT=", "P07_SYSTEM_CARE_ENTRY=",
        'bash "$init_ui"', "run_server_ops", "run_system_care",
    ):
        if prohibited in body:
            raise AssertionError("P07-M05 dispatch invokes unrelated module")
    if ('"$M05_RUNTIME" menu' not in body
            or '"$M05_RUNTIME" --version' not in body
            or "M05_BUILD_EXPECTED" not in body):
        raise AssertionError("P07-M05 private entry/version not proven")


class ToolboxFiveModuleIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.body = m05_body(TOOLBOX.read_text())

    def harness(self, entry: Path) -> Path:
        script = self.folder / "entry-test.sh"
        text = (
            "#!/usr/bin/env bash\nset -Eeuo pipefail\n"
            + "M05_RUNTIME=" + shlex.quote(str(entry)) + "\n"
            + "M05_BUILD_EXPECTED=0.1.0-m05-candidate1\n"
            + "C_YELLOW=''\nC_RED=''\nC_RESET=''\n"
            + "screen_clear() { :; }\n"
            + "say() { printf '%s\\n' \"$*\"; }\n"
            + self.body + "\nrun_server_init\n"
        )
        script.write_text(text)
        return script

    def test_legacy_cross_module_dispatch_would_fail(self):
        legacy = (
            "run_server_init() {\n"
            "  ensure_server_ops_current\n"
            "  ensure_system_care_current\n"
            "  bash \"$init_ui\"\n}\n"
        )
        with self.assertRaises(AssertionError):
            assert_independent(legacy)

    def test_current_candidate_m05_dispatch_is_independent(self):
        assert_independent(self.body)

    def test_missing_m05_does_not_install_other_modules(self):
        script = self.harness(self.folder / "missing")
        p = subprocess.run(["bash", str(script)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 7)
        self.assertIn("尚未正式分发", p.stdout)

    def test_exact_version_runs_only_private_m05_entry(self):
        entry = self.folder / "init-entry"
        marker = self.folder / "m05-menu-called"
        entry.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ \"$1\" == '--version' ]]; then\n"
            "  echo 'P07-M05 新服务器初始化 0.1.0-m05-candidate1'\n"
            "else\n"
            "  echo menu > " + shlex.quote(str(marker)) + "\n"
            "fi\n"
        )
        entry.chmod(0o755)
        script = self.harness(entry)
        p = subprocess.run(["bash", str(script)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(marker.read_text().strip(), "menu")

    def test_wrong_build_fails_closed_without_install(self):
        entry = self.folder / "foreign-entry"
        marker = self.folder / "menu-called"
        entry.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ \"$1\" == '--version' ]]; then\n"
            "  echo 'P07-M05 新服务器初始化 WRONG'\n"
            "else\n"
            "  echo RUN > " + shlex.quote(str(marker)) + "\n"
            "fi\n"
        )
        entry.chmod(0o755)
        p = subprocess.run(["bash", str(self.harness(entry))],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 13)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
