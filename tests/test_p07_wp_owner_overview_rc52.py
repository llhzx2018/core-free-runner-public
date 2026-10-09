#!/usr/bin/env python3
"""P07 rc52: isolated one-page WordPress evidence overview, never writes production."""
import argparse
import contextlib
import io
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = ROOT / "packages/p07-system-care/0.1.0-rc52"
sys.path.insert(0, str(PKG / "lib"))
import intrusion_evidence as ev


class OwnerOnePageOverview(unittest.TestCase):
    def setUp(self):
        self.scan = {"result": "ANOMALY_HISTORY", "scan_finished_at": "2026-10-09T00:03:00Z"}
        core = [
            "wp-admin/about.php", "wp-admin/includes/export.php",
            "wp-admin/includes/image.php", "wp-includes/class-wp-http.php",
            "wp-includes/class-wp-oembed.php", "wp-includes/class-wp-query.php",
            "wp-includes/post.php", "wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php",
            "wp-includes/version.php",
        ]
        # 30 historical events, 16 unique (site, path) groups.
        self.events = [
            {"site": "unzip.kewaro.com", "type": "MODIFIED_PHP", "relative_path": path}
            for path in core
        ]
        plugins = [
            "wp-content/plugins/vf-ops/vf-ops.php",
            "wp-content/plugins/vf-ops/includes/admin-v13/views/very-long-file-controller.php",
            "wp-content/plugins/vf-tool-m3u8/admin/Controller/class-example-do-not-truncate.php",
            "wp-content/plugins/vf-tool-m3u8/includes/v6-provider.php",
            "wp-content/plugins/vf-tool-m3u8/vf-tool-m3u8.php",
        ]
        self.events.extend(
            {"site": "www3.m3u8.one", "type": "MODIFIED_PHP", "relative_path": path}
            for path in plugins for _ in range(3)
        )
        self.events.extend(
            {"site": "www3.m3u8.one", "type": "MODIFIED_PHP",
             "relative_path": "wp-content/wflogs/" + name}
            for name in ("config-livewaf.php", "config-synced.php")
            for _ in range(3)
        )
        self.assertEqual(len(self.events), 30)

    def test_all_30_records_grouped_without_page_navigation(self):
        rendered = ev.human_evidence_overview(self.scan, self.events)
        self.assertIn("30 条历史记录 · 涉及 16 个不同文件", rendered)
        self.assertIn("优先 0 条 · 需核实 24 条 · 动态文件 6 条", rendered)
        self.assertIn("网站：unzip.kewaro.com · 9 条历史记录 · 9 个文件", rendered)
        self.assertIn("网站：www3.m3u8.one · 21 条历史记录 · 7 个文件", rendered)
        self.assertNotIn("第 1/5 页", rendered)
        self.assertNotIn("N 下一页", rendered)
        self.assertNotIn("未展开", rendered)

    def test_duplicate_records_do_not_disappear_or_appear_as_distinct_files(self):
        rendered = ev.human_evidence_overview(self.scan, self.events)
        target = "wp-content/plugins/vf-ops/vf-ops.php（历史记录 3 条）"
        self.assertEqual(rendered.count(target), 1)
        self.assertEqual(len(self.events), 30)
        self.assertIn("按网站合并", rendered)

    def test_full_file_paths_and_types_survive(self):
        rendered = ev.human_evidence_overview(self.scan, self.events)
        self.assertIn("wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php", rendered)
        self.assertIn("wp-content/plugins/vf-tool-m3u8/admin/Controller/class-example-do-not-truncate.php", rendered)
        self.assertIn("安全插件动态文件 · 尚未验证更新来源", rendered)
        self.assertNotIn("已确认为安全", rendered)
        self.assertIn("不要因为同名文件合并，就更新参考状态", rendered)

    def test_large_incident_has_explicit_bounded_output_without_false_all_clear(self):
        events = [
            {"site": "large.example", "type": "NEW_PHP",
             "relative_path": f"wp-content/plugins/large/file{i:04}.php"}
            for i in range(130)
        ]
        rendered = ev.human_evidence_overview(self.scan, events)
        self.assertIn("130 条历史记录 · 涉及 130 个不同文件", rendered)
        self.assertIn("另有 10 个未展开", rendered)
        self.assertIn("并非其余文件安全", rendered)
        self.assertNotIn("file0129.php", rendered)

    def test_terminal_control_characters_are_never_printed(self):
        events = [{"site": "example\n\033[31m.com", "type": "NEW_PHP",
                   "relative_path": "wp-content/plugins/ok/\r\033[0m.php"}]
        rendered = ev.human_evidence_overview(self.scan, events)
        self.assertNotIn("\033", rendered)
        self.assertNotIn("\r", rendered)
        self.assertIn("1 条历史记录", rendered)

    def test_readonly_cli_dispatch_and_legacy_contract_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = pathlib.Path(tmp)
            (state / "scan_state.json").write_text("{}", encoding="utf8")
            args = argparse.Namespace(state_dir=tmp, limit=20, json=False,
                                      summary=False, overview=True, triage=False,
                                      pages=False, page=1)
            out = io.StringIO()
            with mock.patch.object(ev, "status_doc", return_value={"status": "ATTENTION"}), \
                 mock.patch.object(ev, "read_json", return_value=self.scan), \
                 mock.patch.object(ev, "load_events_consistent", return_value=self.events), \
                 contextlib.redirect_stdout(out):
                self.assertEqual(ev.command_report(args), 0)
            self.assertIn("30 条历史记录", out.getvalue())
            self.assertEqual((state / "scan_state.json").read_text(), "{}")
        self.assertTrue(callable(ev.human_evidence_page))
        shell = (PKG / "intrusion-evidence.sh").read_text(encoding="utf8")
        self.assertIn("helper report --overview", shell)
        self.assertNotIn('helper report --triage --page "$page"', shell)
        self.assertIn("helper report --limit 20", shell)
        self.assertIn("确认更新参考状态？", shell)
        self.assertIn("历史记录数量", shell)

if __name__ == "__main__":
    unittest.main()
