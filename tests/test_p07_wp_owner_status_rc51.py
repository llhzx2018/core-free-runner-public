#!/usr/bin/env python3
"""P07 rc51 owner summary: isolated status output; never read Production."""
import os
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = ROOT / "packages/p07-system-care/0.1.0-rc51"
SCRIPT = (PKG / "intrusion-evidence.sh").read_text(encoding="utf-8")
STATUS = (PKG / "status.sh").read_text(encoding="utf-8")

def cut_function(start, next_name):
    begin = SCRIPT.index(start + "() {")
    end = SCRIPT.index("\n" + next_name + "() {", begin)
    return SCRIPT[begin:end]

class OwnerStatusClarity(unittest.TestCase):
    def output(self, result):
        fn = cut_function("show_status", "run_baseline_helper")
        harness = """set -euo pipefail
IE_STATUS=ATTENTION
IE_ENABLED=1
IE_EVENTS=30
IE_UNBASELINED=0
IE_RESULT="$P07_MOCK_RESULT"
IE_LAST_SCAN=2026-10-09T00:03:00Z
IE_SCHEDULER=systemd
C_BOLD='' C_CYAN='' C_RESET='' C_YELLOW='' C_RED='' C_GREEN=''
refresh_cache(){ :; }
say(){ printf '%s\n' "$*"; }
wp_display_time(){ printf '10-09 08:03'; }
show_failure_reason(){ :; }
""" + fn + "\nshow_status\n"
        p = subprocess.run(["bash", "-c", harness],
                           env={**os.environ, "P07_MOCK_RESULT": result},
                           capture_output=True, text=True, timeout=4)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_current_difference_never_claims_30_new_attacks(self):
        out = self.output("ANOMALY")
        self.assertIn("本次检出文件差异", out)
        self.assertIn("历史变更   30 条", out)
        self.assertIn("不代表本次新增", out)
        self.assertNotIn("已确认入侵", out)

    def test_history_only_distinguishes_current_scan(self):
        out = self.output("ANOMALY_HISTORY")
        self.assertIn("历史变化待核实", out)
        self.assertIn("未再检出文件差异", out)
        self.assertIn("历史记录仍待核实", out)
        self.assertNotIn("本次检出文件差异", out)

    def test_evidence_stays_protected(self):
        self.assertIn('if [[ "$IE_ENABLED" != 1 || ! "$IE_STATUS" =~ ^(NORMAL|ATTENTION)$', SCRIPT)
        self.assertIn('helper report --triage --page "$page"', SCRIPT)
        self.assertIn("确认更新参考状态？", SCRIPT)
        self.assertIn('if [[ "$advisories" =~ ^[0-9]+$ ]]; then', STATUS)
        self.assertIn('P07_SYSTEM_CARE_SECURITY_ADVISORIES=%s', STATUS)

if __name__ == "__main__":
    unittest.main()
