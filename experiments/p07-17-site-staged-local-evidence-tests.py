"""Synthetic P07 17-site read-only local stage-evidence tests."""
import contextlib
import copy
import importlib.util
import io
from pathlib import Path
import types
import unittest
from unittest import mock

FILE=Path(__file__).with_name("p07-17-site-staged-local-evidence.py")
spec=importlib.util.spec_from_file_location("p07_staged",FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def row(name,staged=False):
    db="sample_"+name.replace(".","_").replace("-","_")
    return {
      "domain":name,
      "stage_status":"PULLED_STAGED" if staged else "PENDING",
      "site_root":"/home/"+name,
      "document_root":"/home/"+name+"/htdocs",
      "site_user":"s_"+name.replace(".","_").replace("-","_"),
      "mysql_databases":[db],
      "mysql_prepare_count":1 if staged else 0,
      "mysql_verification":[{"phase":"prepare","database":db,"status":"PASS"}] if staged else [],
    }

def make_states():
    a=["123.kewaro.com","123.m3u8.one","assetbox.kewaro.com",
      "doc.kewaro.com","domain.kewaro.com","example.cloudpanel.io",
      "forge.kewaro.com"]
    b=["infra.kewaro.com","lib.kewaro.com","press.kewaro.com",
       "seo.kewaro.com","start.kewaro.com","textbox.kewaro.com"]
    originals=[row(x,True) for x in a]+[row("ilovem3u8.kewaro.com")]
    originals += [row(x) for x in b]
    originals += [row("unzip.kewaro.com"),row("updates.kewaro.com"),row("www3.m3u8.one")]
    nine=[row(x,True) for x in b]+[row("unzip.kewaro.com"),
         row("updates.kewaro.com"),row("www3.m3u8.one")]
    two=[row("updates.kewaro.com",True),row("www3.m3u8.one")]
    entries=[originals,nine,two]
    result={}
    for n,(label,mid,count) in enumerate(m.JOBS):
        state={
          "schema":m.SCHEMA,"migration_id":mid,
          "status":"PREPARE_FAILED","sites":entries[n],
          "target_server_identity":"stable-cp2",
          "source_runtime_frozen":False,
          "target_runtime_activated":False,
          "dns_changed_by_p07":False,
          "source_delete_allowed":False,
          "existing_target_overwrite_allowed":False,
          "partial_parent_migration_id":m.JOBS[n-1][1] if n else None,
        }
        assert len(state["sites"])==count
        result[mid]=state
    return result

def run(states,manifest):
    output=io.StringIO()
    with mock.patch.object(m,"secure_state",side_effect=lambda p: states[p.parent.name]), \
         mock.patch.object(m.os,"geteuid",return_value=0), \
         mock.patch.object(m,"safe_site_path",return_value=True), \
         mock.patch.object(m.pwd,"getpwnam",return_value=types.SimpleNamespace()), \
         contextlib.redirect_stdout(output):
         m.audit(root=Path("/no-real-files"),inventory_fn=lambda _:manifest)
    return output.getvalue()

class Tests(unittest.TestCase):
    def test_all_14_staged_have_local_structure_and_import_proofs(self):
        states=make_states()
        manifest={"sites":[]}
        for state in states.values():
            for site in state["sites"]:
                if site["stage_status"]=="PULLED_STAGED":
                    manifest["sites"].append({"domain":site["domain"],"site_user":site["site_user"],
                                              "mysql_databases":site["mysql_databases"]})
        output=run(states,manifest)
        self.assertIn("STAGED_SITES=14",output)
        self.assertIn("PENDING_SITES=3",output)
        self.assertIn("STAGED_SITE_LOCAL_EVIDENCE=PASS",output)
        self.assertIn("STAGED_SITE_GAP_COUNT=0",output)
        self.assertEqual(len([v for v in output.splitlines() if v.startswith("SITE=")]),14)
        self.assertEqual(output.count("PENDING_SITE="),3)
        self.assertIn("CUTOVER_ALLOWED=NO",output)
        self.assertIn("EXTERNAL_ASSETS_SQLITE_CRON_PHP_SMOKE=NOT_YET_VERIFIED",output)
        self.assertNotIn("password",output.lower())

    def test_missing_panel_database_is_reported_not_falsely_passed(self):
        states=make_states()
        manifest={"sites":[]}
        for state in states.values():
            for site in state["sites"]:
                if site["stage_status"]=="PULLED_STAGED":
                    manifest["sites"].append({"domain":site["domain"],"site_user":site["site_user"],
                                              "mysql_databases":site["mysql_databases"]})
        manifest["sites"][0]["mysql_databases"]=[]
        output=run(states,manifest)
        self.assertIn("STAGED_SITE_LOCAL_EVIDENCE=GAPS_FOUND",output)
        self.assertIn("STAGED_SITE_GAP_COUNT=1",output)
        self.assertIn("PANEL_INVENTORY=MISSING",output)

    def test_parent_guard_mutation_fails_closed(self):
        states=make_states()
        states[m.JOBS[1][1]]["source_runtime_frozen"]=True
        with self.assertRaisesRegex(m.Block,"MIGRATION_GUARD_CHANGED"):
            run(states,{"sites":[]})

    def test_remaining_pending_site_does_not_promote(self):
        states=make_states()
        states[m.JOBS[2][1]]["sites"][-1]["stage_status"]="PULLED_STAGED"
        with self.assertRaisesRegex(m.Block,"STAGED_PENDING_SCOPE_CHANGED"):
            run(states,{"sites":[]})

    def test_current_cp2_task_ids_and_exact_stage_counts(self):
        self.assertEqual(
            [mid for _,mid,_ in m.JOBS],
            [
                "pull-20261101T045943Z-923729a1",
                "pull-20261101T052411Z-35663c25",
                "pull-20261102T005644Z-7178c7d5",
            ],
        )
        self.assertEqual(m.EXPECTED_STAGE_COUNTS,(7,6,1))
        states=make_states()
        self.assertEqual(
            [sum(site["stage_status"]=="PULLED_STAGED" for site in states[mid]["sites"])
             for _,mid,_ in m.JOBS],
            list(m.EXPECTED_STAGE_COUNTS),
        )

    def test_noncurrent_older_task_id_fails_closed(self):
        states=make_states()
        states[m.JOBS[0][1]]["migration_id"]="pull-20261028T103425Z-98050c76"
        with self.assertRaisesRegex(m.Block,"MIGRATION_ID_OR_SCHEMA_CHANGED"):
            run(states,{"sites":[]})

    def test_stage_count_drift_refused_before_panel_inventory(self):
        states=make_states()
        first=states[m.JOBS[0][1]]["sites"][0]
        first["stage_status"]="PENDING"
        with self.assertRaisesRegex(m.Block,"PER_OWNER_STAGED_COUNT_CHANGED"):
            run(states,{"sites":[]})

    def test_unverified_database_phase_is_missing(self):
        x=row("sample.example",True)
        x["mysql_verification"][0]["phase"]="final"
        result=m.check_site(x,{"domain":x["domain"],"site_user":x["site_user"],
                               "mysql_databases":x["mysql_databases"]})
        self.assertEqual(result[3],"MISSING")

    def test_no_write_paths(self):
        text=FILE.read_text()
        for bad in ("subprocess.Popen","subprocess.run","ssh -","rsync ","db:import",
                    "db:delete","DROP DATABASE","create_target_site(",
                    "resume_prepare_migration("):
            self.assertNotIn(bad,text)

if __name__=="__main__":
    unittest.main()
