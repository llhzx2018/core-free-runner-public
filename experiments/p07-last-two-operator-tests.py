"""No real VPS, SSH, or database; negative bounds for last-two staging."""
import copy, importlib.util, json
from pathlib import Path
from unittest import mock
import unittest

p = Path(__file__).with_name("p07-release113-last-two-stage.py")
spec = importlib.util.spec_from_file_location("p07_last_two", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def state_pair():
    sites=[]
    for i in range(17):
        domain=m.PARENT_DOMAINS[i]
        sites.append(dict(domain=domain,site_user=f"user{i}",
                          site_root=f"/home/user{i}",document_root=f"/home/user{i}/htdocs",
                          runtime={"type":"php","version":"8.3"},
                          mysql_databases=[f"db{i}"] if i in (14,16) else [],
                          stage_status="PENDING"))
    a=dict(schema=m.SCHEMA,migration_id=m.ORIGINAL,status="PREPARE_FAILED",
           last_sql_guard_failure={"reason":"CONDITIONAL_DDL"},
           source=dict(host="192.0.2.1",ip="192.0.2.1",ssh_user="root",ssh_port=22),
           source_server_identity="sha256:synthetic-source",
           target_server_identity="sha256:synthetic-target",
           source_runtime_frozen=False,target_runtime_activated=False,
           dns_changed_by_p07=False,source_delete_allowed=False,
           existing_target_overwrite_allowed=False,sites=sites)
    for row in a["sites"][:7]: row["stage_status"]="PULLED_STAGED"
    b=copy.deepcopy(a)
    b.update(migration_id=m.NINE_CHILD,partial_parent_migration_id=m.ORIGINAL,
             cutover_prohibited=True,last_sql_guard_failure={"reason":"CONDITIONAL_DDL"},
             sites=copy.deepcopy(sites[8:]))
    for row in b["sites"][:6]: row["stage_status"]="PULLED_STAGED"
    return a,b

class Tests(unittest.TestCase):
    def test_exact_scope(self):
        a,b=state_pair()
        baseline=json.dumps([a,b],sort_keys=True)
        self.assertEqual([r["domain"] for r in m.prove_original_and_child(a,b)],list(m.DOMAINS))
        self.assertEqual(baseline,json.dumps([a,b],sort_keys=True))

    def test_status_and_cutover_fail_closed(self):
        for which,key,value in [
            ("a","status","PREPARED"),("b","status","PREPARED"),
            ("b","cutover_prohibited",False),
            ("a","last_sql_guard_failure",None),
            ("a","last_sql_guard_failure",{"reason":"OTHER"}),
            ("b","last_sql_guard_failure",None),
            ("b","source_runtime_frozen",True),
            ("b","dns_changed_by_p07",True),
            ("b","source_server_identity","wrong"),
            ("b","target_server_identity","wrong"),
            ("b","partial_parent_migration_id","wrong")]:
            with self.subTest(which=which,key=key):
                a,b=state_pair()
                (a if which=="a" else b)[key]=value
                with self.assertRaises(m.Stop):m.prove_original_and_child(a,b)

    def test_real_november_1_identity_and_order(self):
        self.assertEqual(m.ORIGINAL, "pull-20261101T045943Z-923729a1")
        self.assertEqual(m.NINE_CHILD, "pull-20261101T052411Z-35663c25")
        self.assertEqual(m.PARENT_DOMAINS[7], "ilovem3u8.kewaro.com")
        self.assertEqual(m.NINE_DOMAINS[6], "unzip.kewaro.com")
        self.assertEqual(list(m.DOMAINS), list(m.PARENT_DOMAINS[-2:]))

    def test_parent_prefix_and_pending_tail_are_immutable(self):
        for index, changed in ((0,"PENDING"),(6,"PENDING"),(7,"PULLED_STAGED"),
                               (14,"PULLED_STAGED"),(15,"PULLED_STAGED"),(16,"PULLED_STAGED")):
            a,b=state_pair()
            a["sites"][index]["stage_status"]=changed
            with self.subTest(index=index), self.assertRaises(m.Stop):
                m.prove_original_and_child(a,b)

    def test_parent_site_order_and_original_guard_are_required(self):
        for index in (0,7,14,16):
            a,b=state_pair()
            a["sites"][index]["domain"]="modified.example.test"
            with self.subTest(index=index), self.assertRaises(m.Stop):
                m.prove_original_and_child(a,b)

    def test_no_restage_unzip_or_six_or_last_two(self):
        for index,stage in [(0,"PENDING"),(6,"PULLED_STAGED"),(7,"PULLED_STAGED"),(8,"PULLED_STAGED")]:
            a,b=state_pair()
            b["sites"][index]["stage_status"]=stage
            with self.subTest(index=index),self.assertRaises(m.Stop):
                m.prove_original_and_child(a,b)

    def test_scope_drift_rejected(self):
        for site_index,field,value in [(7,"site_user","different"),
                         (8,"mysql_databases",[]),(7,"document_root","/wrong"),
                         (6,"domain","different.invalid")]:
            a,b=state_pair()
            b["sites"][site_index][field]=value
            with self.subTest(site=site_index,field=field),self.assertRaises(m.Stop):
                m.prove_original_and_child(a,b)

    def test_existing_child_is_not_resumable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,parent in [("nine",m.ORIGINAL),("two",m.NINE_CHILD)]:
                x=root/name;x.mkdir()
                (x/"state.json").write_text(json.dumps({
                    "partial_parent_migration_id":parent,
                    "migration_id":m.NINE_CHILD if name=="nine" else "child2"}))
            with mock.patch.object(m,"STATES",root),self.assertRaises(m.Stop):
                m.ensure_no_duplicate_child()

    def test_existing_website_prevents_write(self):
        import sys
        a,b=state_pair()
        inventory=type("Invent",(),{"build_manifest":staticmethod(lambda root:{
            "discovery_source":"cloudpanel_db+vhost",
            "sites":[{"domain":"updates.kewaro.com","site_user":"any",
                      "mysql_databases":[]}]})})
        with mock.patch.dict(sys.modules,{"inventory":inventory}),self.assertRaises(m.Stop):
            m.ensure_target_unoccupied(b["sites"][7:])

    def test_code_does_not_invoke_cutover_or_retry(self):
        s=p.read_text()
        self.assertIn("remainder_parent=NINE_CHILD",s)
        self.assertIn("expected_remainder_sites=[dict(row) for row in last_two]",s)
        self.assertIn('descendant.get("cutover_prohibited") is True',s)
        self.assertNotIn("engine.cutover_migration(",s)
        self.assertNotIn("engine.resume_prepare_migration(",s)
        self.assertNotIn("engine.freeze_old_server(",s)

if __name__=="__main__":unittest.main()
