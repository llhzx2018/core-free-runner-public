"""Synthetic-only proof of P07 release113 legacy nine-site staging wrapper.

Does not import business data or execute any SSH/CloudPanel command.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

S = Path(__file__).with_name("p07-release113-legacy-nine-stage.py")
spec = importlib.util.spec_from_file_location("p07_nine_operator", S)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def parent_fixture():
    rows = [
        {"domain": f"done{i}.example.test", "site_user": f"old{i}",
         "site_root": f"/home/old{i}", "document_root": f"/home/old{i}/htdocs",
         "mysql_databases": []}
        for i in range(7)
    ]
    rows.append({
        "domain": "ilovem3u8.kewaro.com", "site_user": "blocked8",
        "site_root": "/home/blocked8",
        "document_root": "/home/blocked8/htdocs",
        "mysql_databases": ["blocked8_db"],
    })
    for i, domain in enumerate(module.DOMAINS, 9):
        rows.append({
            "domain": domain, "site_user": f"next{i}",
            "site_root": f"/home/next{i}",
            "document_root": f"/home/next{i}/htdocs",
            "mysql_databases": [f"next{i}_db"],
        })
    return {
        "schema": "vf-server-ops.server-migration.target-pull.v1",
        "migration_id": module.PARENT_ID,
        "status": "PREPARE_FAILED",
        "last_sql_guard_failure": None,
        "source": {
            "host": "192.0.2.1", "ip": "192.0.2.1",
            "ssh_user": "root", "ssh_port": 22
        },
        "source_server_identity": "sha256:safe-synthetic-test",
        "source_runtime_frozen": False,
        "target_runtime_activated": False,
        "dns_changed_by_p07": False,
        "source_delete_allowed": False,
        "existing_target_overwrite_allowed": False,
        "sites": rows,
    }

class OperatorBoundary(unittest.TestCase):
    def test_exact_legacy_scope_accepted_without_mutating_parent(self):
        p = parent_fixture()
        saved = json.dumps(p, sort_keys=True)
        selected = module.validate_parent(p)
        self.assertEqual(tuple(x["domain"] for x in selected), module.DOMAINS)
        self.assertEqual(json.dumps(p, sort_keys=True), saved)

    def test_fails_closed_for_parent_state_drift(self):
        for key, bad in (
            ("status", "PREPARED"),
            ("source_runtime_frozen", True),
            ("target_runtime_activated", True),
            ("dns_changed_by_p07", True),
            ("source_delete_allowed", True),
            ("existing_target_overwrite_allowed", True),
            ("last_sql_guard_failure", {"reason":"CONDITIONAL_DDL"}),
            ("source_server_identity", ""),
            ("partial_parent_migration_id", "other"),
        ):
            with self.subTest(key=key):
                p = parent_fixture()
                p[key] = bad
                with self.assertRaises(module.Stop):
                    module.validate_parent(p)

    def test_fails_closed_for_any_change_to_nine_sites(self):
        for kind in ("domain", "order", "site_user", "database", "staged", "broken_root", "site8"):
            with self.subTest(kind=kind):
                p = parent_fixture()
                s = p["sites"]
                if kind == "domain":
                    s[8]["domain"] = "surprise.example.test"
                elif kind == "order":
                    s[8], s[9] = s[9], s[8]
                elif kind == "site_user":
                    s[8]["site_user"] = s[0]["site_user"]
                elif kind == "database":
                    s[8]["mysql_databases"] = ["/private/escape"]
                elif kind == "staged":
                    s[8]["stage_status"] = "PULLED_STAGED"
                elif kind == "broken_root":
                    s[8].pop("document_root")
                elif kind == "site8":
                    s[7]["domain"] = "other.example.test"
                with self.assertRaises(module.Stop):
                    module.validate_parent(p)

    def test_existing_child_is_hard_block(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            child=root/"existing-child"
            child.mkdir()
            (child/"state.json").write_text(json.dumps({
                "migration_id":"existing-child",
                "partial_parent_migration_id":module.PARENT_ID,
                "status":"PREPARE_FAILED",
            }))
            with mock.patch.object(module, "STATES", root):
                self.assertEqual(module.existing_children(),["existing-child"])

    def test_guarded_engine_call_keeps_exact_scope_and_forbids_cutover(self):
        src = S.read_text()
        self.assertIn("remainder_parent=PARENT_ID",src)
        self.assertIn("expected_source_identity=parent",src)
        self.assertIn("expected_remainder_sites=[dict(row) for row in sites]",src)
        self.assertIn('child.get("cutover_prohibited") is True',src)
        self.assertIn('child.get("existing_target_overwrite_allowed") is False',src)
        self.assertIn('child.get("source_runtime_frozen") is False',src)
        self.assertNotIn("engine.cutover_migration(",src)
        self.assertNotIn("engine.rollback_migration(",src)
        self.assertNotIn("engine.freeze_old_server(",src)

if __name__=="__main__":
    unittest.main()
