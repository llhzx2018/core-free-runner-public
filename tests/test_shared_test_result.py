import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from shared_test_result import summarize_junit

class SharedTestResultTests(unittest.TestCase):
    def test_phpunit_named_assertion_without_values(self):
        raw = b'<testsuite><testcase classname="Tests\\Feature\\AuthTest" name="test_login"><failure message="Expected response status 200 but received 403">token=SECRET</failure></testcase></testsuite>'
        result = summarize_junit(raw, known_names=frozenset({"test_login"}))
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failures"], [{"test":"test_login","kind":"failure","assertion":"ASSERT_HTTP_STATUS"}])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("403", json.dumps(result))

    def test_unknown_parameter_and_private_detail_never_echo(self):
        raw = b'<testsuites><testsuite><testcase name="customer_secret"><error message="Connection refused at https://private.example/key">PRIVATE</error></testcase></testsuite></testsuites>'
        r = summarize_junit(raw)
        self.assertTrue(r["failures"][0]["test"].startswith("case-"))
        self.assertEqual(r["failures"][0]["assertion"], "DB_CONNECTION")
        for s in ("customer_secret","private.example","PRIVATE"):
            self.assertNotIn(s, json.dumps(r))

    def test_reject_xml_entities_and_wrong_root(self):
        for raw in (b'<!DOCTYPE x [<!ENTITY s "private">]><testsuite/>', b'<x/>', b'<testsuite>', b'\xff'):
            self.assertEqual(summarize_junit(raw)["status"], "REPORT_INVALID")

    def test_pass_and_skipped_are_observations_only(self):
        r = summarize_junit(b'<testsuite><testcase name="a"/><testcase name="b"><skipped/></testcase></testsuite>')
        self.assertEqual((r["status"], r["cases"], r["skipped"], r["failed"]), ("REPORT_OBSERVED",2,1,0))
        self.assertEqual(summarize_junit(b'<testsuite/>')["status"], "REPORT_EMPTY")

    def test_vitest_playwright_style_cdata_and_reviewed_title(self):
        raw = b'<testsuites><testsuite><testcase name="suite &gt; shows the review list"><failure><![CDATA[expected source to contain PRIVATE_VALUE]]></failure></testcase></testsuite></testsuites>'
        r = summarize_junit(raw, known_names=frozenset({"shows the review list"}))
        self.assertEqual(r["failures"][0], {"test":"shows the review list","kind":"failure","assertion":"ASSERT_CONTAINS"})
        self.assertNotIn("PRIVATE_VALUE", json.dumps(r))

    def test_parameterized_private_label_is_not_emitted(self):
        raw = b'<testsuite><testcase name="test_login with data set private-value"><failure/></testcase></testsuite>'
        r = summarize_junit(raw, known_names=frozenset({"test_login"}))
        self.assertEqual(r["failures"][0]["test"], "test_login")
        self.assertNotIn("private-value", json.dumps(r))

    def test_bounded_failures(self):
        r = summarize_junit(b'<testsuite>' + b'<testcase name="x"><failure/></testcase>' * 50 + b'</testsuite>')
        self.assertEqual((r["failed"],len(r["failures"]),r["omitted_failures"]),(50,40,10))

if __name__ == "__main__":
    unittest.main()
