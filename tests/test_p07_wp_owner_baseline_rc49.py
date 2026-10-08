#!/usr/bin/env python3
"""Isolated read-only OWNER snapshot regression, no production commands."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "packages/p07-system-care/0.1.0-rc49/intrusion-evidence.sh"
SRC = PATH.read_text(encoding="utf-8")


def extract_function(name: str, next_name: str) -> str:
    begin = SRC.index(name + "() {")
    end = SRC.index("\n" + next_name + "() {", begin)
    return SRC[begin:end] + "\n"


class OwnerBaselineSafety(unittest.TestCase):
    def test_no_plain_y_skips_23_unverified_historical_events(self):
        self.run_mock("y\n", False)

    def test_blank_cancels(self):
        self.run_mock("\n", False)

    def test_wrong_count_cancels(self):
        self.run_mock("18\ny\n", False)

    def test_correct_count_still_requires_explicit_final_y(self):
        self.run_mock("23\nn\n", False)

    def test_correct_count_plus_final_y_is_the_only_mock_success(self):
        self.run_mock("23\ny\n", True)

    def run_mock(self, answers: str, expect_calls: bool):
        if shutil.which("script") is None:
            self.skipTest("util-linux script PTY unavailable")
        fn = extract_function("rebuild_baseline", "disable_evidence")
        with tempfile.TemporaryDirectory() as tmp:
            dest = pathlib.Path(tmp)
            witness = dest / "mock-applied"
            harness = r"""
set -euo pipefail
IE_EVENTS=23
require_root(){ :; }
refresh_cache(){ :; }
say(){ printf '%s\n' "$*"; }
warn(){ say "$*"; }
fail(){ say "$*"; }
info(){ say "$*"; }
ok(){ say "$*"; }
confirm_numeric(){
  local input
  printf '%s [y/N]：' "$1"
  read -r input || return 79
  [[ "$input" == y ]]
}
run_baseline_helper(){ printf 'MOCK_CALLED\n' >> "$MOCK_WITNESS"; }
""" + fn + '\nrebuild_baseline\n'
            mock_file = dest / "mock.sh"
            mock_file.write_text(harness, encoding="utf-8")
            r = subprocess.run(
                ["script", "-qfec", f"env MOCK_WITNESS='{witness}' bash '{mock_file}'", "/dev/null"],
                input=answers, capture_output=True, text=True, timeout=12,
            )
            self.assertEqual(r.returncode, 0, r.stdout[-800:])
            self.assertEqual(witness.exists(), expect_calls, r.stdout[-800:])
            if not expect_calls:
                self.assertNotIn("正在更新网站参考状态", r.stdout)
            self.assertIn("历史记录数量 23", r.stdout)

    def test_brief_owner_status_and_timezone(self):
        self.assertIn("历史变更", SRC)
        self.assertIn("累计记录，不代表本次新增或已经入侵", SRC)
        self.assertIn("TZ=Asia/Shanghai date -d", SRC)
        self.assertIn("下一步     选择 5 查看文件变化及排查建议", SRC)
        self.assertIn("3) screen_clear; rebuild_baseline; pause_menu", SRC)
        self.assertNotIn("3) rebuild_baseline; pause_menu", SRC)

    def test_existing_protection_preserved(self):
        self.assertIn("helper scan >/dev/null", SRC)
        self.assertIn("helper report --triage --page", SRC)
        self.assertIn("helper report --limit 20", SRC)
        self.assertIn("confirm_numeric '已核实文件与更新来源，确认更新参考状态？'", SRC)
        self.assertIn("remove_scheduler", SRC)
        self.assertIn("install_scheduler", SRC)


if __name__ == "__main__":
    unittest.main()
