#!/usr/bin/env python3
"""P07 owner-readable security triage regression: no VPS data, no writes."""
import argparse
import contextlib
import io
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
PKG = HERE / "packages/p07-system-care/0.1.0-rc48"
sys.path.insert(0, str(PKG / "lib"))
import intrusion_evidence as ev


class OwnerReview(unittest.TestCase):
    def setUp(self):
        self.scan = {
            "result": "ANOMALY_HISTORY",
            "scan_finished_at": "2026-10-08T11:01:52Z",
            "last_known_clean_at": "2026-10-08T09:06:15Z",
        }
        self.events = [
            {"site": "unzip.example", "type": "MODIFIED_PHP", "relative_path": "wp-admin/about.php",
             "first_detected_at": "2026-10-08T11:01:48Z", "correlated_requests": [
                 {"timestamp": "2026-10-08T09:42:46Z", "source_ip": "192.0.2.3",
                  "method": "POST", "path_without_query": "/wp-cron.php", "status": 200}]} 
            for _ in range(9)
        ] + [
            {"site": "www.example", "type": "MODIFIED_PHP", "relative_path": "wp-content/plugins/demo/main.php",
             "first_detected_at": "2026-10-08T11:01:48Z"} for _ in range(6)
        ] + [
            {"site": "www.example", "type": "MODIFIED_PHP", "relative_path": "wp-content/wflogs/config-synced.php",
             "first_detected_at": "2026-10-08T11:01:48Z"} for _ in range(3)
        ]

    def test_classification_only_flag_not_infection_claim(self):
        self.assertEqual(ev.event_review_level({"type": "UPLOADS_PHP", "relative_path": "wp-content/uploads/bad.php"})[0], 0)
        self.assertEqual(ev.event_review_level({"type": "KEY_FILE_CHANGED", "relative_path": "wp-config.php"})[0], 0)
        self.assertEqual(ev.event_review_level({"type": "MODIFIED_PHP", "relative_path": "wp-admin/about.php"})[0], 1)
        self.assertEqual(ev.event_review_level({"type": "MODIFIED_PHP", "relative_path": "wp-content/wflogs/config.php"})[0], 2)
        self.assertEqual(ev.event_review_level({"type": "NEW_PHP", "relative_path": "wp-content/plugins/demo/new.php"})[0], 1)

    def test_owner_summary_18_records_without_duplicated_request_ip(self):
        first = ev.human_evidence_page(self.scan, self.events)
        last = ev.human_evidence_page(self.scan, self.events, page=3)
        self.assertIn("18 条历史变更", first)
        self.assertIn("优先排查   0 项", first)
        self.assertIn("需要核实   15 项", first)
        self.assertIn("动态文件   3 项", first)
        self.assertIn("第 1/3 页", first)
        self.assertIn("第 3/3 页", last)
        self.assertNotIn("192.0.2.3", first)
        self.assertNotIn("关联请求  ", first)
        self.assertIn("尚不能证明遭入侵", first)
        self.assertIn("核实之前不要更新可信基线", first)
        self.assertLessEqual(len(first.splitlines()), 21)

    def test_all_items_accessible_but_no_page_overflow(self):
        for page in (1, 2, 3):
            output = ev.human_evidence_page(self.scan, self.events, page)
            self.assertEqual(output.count("  ["), min(7, 18-(page-1)*7))
        with self.assertRaises(ValueError):
            ev.human_evidence_page(self.scan, self.events, page=4)

    def test_sensitive_config_promoted_no_false_certain_compromise(self):
        changed = [{"site": "site", "type": "UPLOADS_PHP",
                    "relative_path": "wp-content/uploads/2026/evil.php"}]
        a = ev.human_evidence_page(self.scan, changed)
        self.assertIn("优先排查   1 项", a)
        self.assertNotIn("已确认入侵", a)

    def test_raw_original_request_and_json_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            state=pathlib.Path(d)
            (state/"scan_state.json").write_text("{}",encoding="utf8")
            def read(*, triage=False, as_json=False, pages=False):
                args=argparse.Namespace(state_dir=d,limit=20,json=as_json,summary=False,
                                        triage=triage,pages=pages,page=1)
                out=io.StringIO()
                with mock.patch.object(ev,"status_doc",return_value={"status":"ATTENTION"}), \
                     mock.patch.object(ev,"read_json",return_value=self.scan), \
                     mock.patch.object(ev,"load_events_consistent",return_value=self.events), \
                     contextlib.redirect_stdout(out):
                    self.assertEqual(ev.command_report(args),0)
                return out.getvalue()
            self.assertEqual(read(pages=True).strip(),"3")
            self.assertNotIn("192.0.2.3", read(triage=True))
            self.assertIn("192.0.2.3", read())
            self.assertIn("192.0.2.3", read(as_json=True))
            self.assertEqual(len(self.events),18)

    def test_no_hidden_write_or_extra_deep_menu(self):
        shell=(PKG/"intrusion-evidence.sh").read_text()
        self.assertIn('5) screen_clear; show_report ;;',shell)
        self.assertIn('helper report --triage --page "$page"',shell)
        self.assertIn('helper report --limit 20',shell)
        self.assertIn('3) rebuild_baseline; pause_menu',shell)
        self.assertIn('confirm_numeric', shell)

if __name__=="__main__":
    unittest.main()
