#!/usr/bin/env python3
"""Isolated WordPress evidence UX. Never touch a real website or scan data."""
import argparse
import contextlib
import io
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
SYS = HERE / "packages/p07-system-care/0.1.0-rc47"
sys.path.insert(0, str(SYS / "lib"))
import intrusion_evidence as evidence


class EvidenceSummaryContract(unittest.TestCase):
    def setUp(self):
        self.scan = {
            "result": "ANOMALY_HISTORY",
            "scan_finished_at": "2026-10-08T11:01:52Z",
            "last_known_clean_at": "2026-10-08T09:06:15Z",
            "unbaselined_site_count": 0,
        }
        self.events = [
            {
                "site": "test-a.example", "type": "MODIFIED_PHP",
                "first_detected_at": "2026-10-08T11:01:48Z",
                "relative_path": f"wp-includes/file{i}.php",
                "correlated_requests": [
                    {"timestamp": "2026-10-08T10:00:00Z", "source_ip": "192.0.2.14",
                     "method": "POST", "path_without_query": "/wp-cron.php", "status": 200}
                ],
            } for i in range(9)
        ] + [
            {
                "site": "test-b.example", "type": "MODIFIED_PHP",
                "first_detected_at": "2026-10-08T11:01:48Z",
                "relative_path": f"wp-content/plugins/demo/file{i}.php",
                "correlated_requests": [],
            } for i in range(9)
        ]

    def test_summary_counts_all_events_by_site_not_truncated(self):
        text = evidence.compact_evidence_report(self.scan, self.events)
        assert "18 条历史记录" in text
        assert "涉及网站   2 个" in text
        assert "test-a.example   9 条" in text
        assert "test-b.example   9 条" in text
        assert "PHP 文件发生变化 18" in text
        assert "不等于已确认入侵" in text
        assert "不要更新参考状态" in text
        assert "192.0.2.14" not in text
        assert "file0.php" not in text
        assert len(text.splitlines()) <= 15

    def test_summary_sanitizes_newline_in_site(self):
        self.events[0]["site"] = "bad\nredirect"
        text = evidence.compact_evidence_report(self.scan, self.events)
        assert "bad\nredirect" not in text
        assert "bad redirect" in text

    def test_saved_data_report_full_detail_and_json_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = pathlib.Path(tmp)
            (state / "scan_state.json").write_text("{}", encoding="utf8")
            def get_report(*, summary=False, as_json=False):
                args = argparse.Namespace(state_dir=tmp, limit=20, summary=summary, json=as_json)
                out = io.StringIO()
                with mock.patch.object(evidence, "status_doc", return_value={"status": "ATTENTION"}), \
                     mock.patch.object(evidence, "read_json", return_value=self.scan), \
                     mock.patch.object(evidence, "load_events_consistent", return_value=self.events), \
                     contextlib.redirect_stdout(out):
                    assert evidence.command_report(args) == 0
                return out.getvalue()
            summary = get_report(summary=True)
            full = get_report()
            raw = get_report(as_json=True)
            assert "test-a.example   9 条" in summary
            assert "关联请求" not in summary
            assert "关联请求" in full
            assert "/wp-cron.php" in full
            assert '"events"' in raw
            assert "192.0.2.14" in raw
            assert len(self.events) == 18

    def test_unavailable_state_refuses_read(self):
        args = argparse.Namespace(state_dir="/tmp/unused", limit=20, summary=True, json=False)
        output = io.StringIO()
        with mock.patch.object(evidence, "status_doc",
                               return_value={"status": "FAILED", "result": "STATE_EVENTS_CORRUPT",
                                             "error_class": "StateEventsCorruptError"}), \
             contextlib.redirect_stdout(output):
            assert evidence.command_report(args) == 20
        assert "检查失败" in output.getvalue()
        assert "留证状态不完整" in output.getvalue()

    def test_full_evidence_and_baseline_action_remain_explicit(self):
        wp = (SYS / "intrusion-evidence.sh").read_text()
        ui = (SYS / "vf-system-care.sh").read_text()
        assert 'intrusion-evidence-entry.sh menu' in ui
        assert 'intrusion-evidence-entry.sh direct' not in ui
        assert '5. 查看完整异常记录（含请求线索）' in wp
        assert '5) screen_clear; show_report; pause_menu' in wp
        assert '2) screen_clear; show_summary; pause_menu' in wp
        assert 'confirm_numeric' in wp[wp.index("rebuild_baseline() {"):wp.index("disable_evidence() {")]
        assert 'helper report --limit 20' in wp
        assert 'helper report --summary' in wp

if __name__ == "__main__":
    unittest.main()
