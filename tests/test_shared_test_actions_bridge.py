import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from shared_test_actions_bridge import GithubActionsBridge, GithubApiHTTPS, InvalidTask

class Fake:
    def __init__(self):
        self.actor="llhzx2018";self.blob="b"*40;self.posts=[];self.runs=[]
    def __call__(self,method,path,payload=None):
        if path=="/user":return {"login":self.actor}
        if path=="/repos/llhzx2018/core-free-runner-public":return {"default_branch":"main","private":False}
        if "/contents/" in path:return {"sha":self.blob}
        if method=="POST":self.posts.append((path,payload));return {}
        if path.endswith("per_page=100"):return {"workflow_runs":self.runs}
        if "/actions/runs/" in path:return {"id":123,"event":"workflow_dispatch","status":"completed","conclusion":"success"}
        raise AssertionError("UNEXPECTED_MOCK_API_ROUTE")

def lease(privacy="PUBLIC_SAFE",profile="light"):
    j={"schema":"vf-shared-test-job/v1","task_id":"task-actions-0001","project":"P08",
       "source":{"repo":"llhzx2018/vf-adops","sha":"a"*40,"tree_sha":None},
       "test_id":"git-integrity","kind":"unit","privacy":privacy,"profile":profile,
       "timeout_seconds":90,"submitted_at":1,"allow_public_ephemeral":False}
    return {"task_id":j["task_id"],"lane":"PUBLIC_HOSTED",
            "lease_token":"private-leased-capability","job":j}

class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.api=Fake();self.bridge=GithubActionsBridge(self.api,expected_workflow_blob="b"*40)
    def test_dispatch_and_no_fake_run(self):
        r=self.bridge.dispatch(lease())
        self.assertEqual(r["state"],"DISPATCH_ACCEPTED")
        self.assertIsNone(r["run_id"]);self.assertFalse(r["machine_pass"])
        path,payload=self.api.posts[0]
        self.assertTrue(path.endswith("/shared-test-on-demand.yml/dispatches"))
        self.assertEqual(payload["ref"],"main")
        self.assertNotIn("private-leased-capability",str(payload))
    def test_owner_workflow_and_private_fail_closed(self):
        self.api.actor="untrusted"
        with self.assertRaisesRegex(InvalidTask,"UNAUTHORIZED_GITHUB_ACTOR"):self.bridge.dispatch(lease())
        self.api.actor="llhzx2018";self.api.blob="c"*40
        with self.assertRaisesRegex(InvalidTask,"WORKFLOW_NOT_REVIEWED_ON_MAIN"):self.bridge.dispatch(lease())
        self.api.blob="b"*40
        for p,prof in (("PRIVATE_EVIDENCE","light"),("PUBLIC_SAFE","heavy")):
            with self.assertRaises(InvalidTask):self.bridge.dispatch(lease(p,prof))
        self.assertEqual(self.api.posts,[])
    def test_unique_run_matching_and_rerun_actor(self):
        run={"id":123,"display_title":"VF Shared task-actions-0001","event":"workflow_dispatch",
             "head_branch":"main","actor":{"login":"llhzx2018"},
             "triggering_actor":{"login":"llhzx2018"},"created_at":"2026-11-24T14:00:00Z"}
        self.api.runs=[run]
        self.assertEqual(self.bridge.correlate(lease(),sent_after_iso="2026-11-24T13:59:59Z")["run_id"],123)
        self.api.runs=[run,dict(run,id=124)]
        with self.assertRaisesRegex(InvalidTask,"RUN_CORRELATION_NOT_UNIQUE"):
            self.bridge.correlate(lease(),sent_after_iso="2026-11-24T13:59:59Z")
        self.api.runs=[dict(run,triggering_actor={"login":"other"})]
        with self.assertRaises(InvalidTask):
            self.bridge.correlate(lease(),sent_after_iso="2026-11-24T13:59:59Z")
    def test_cancel_requires_remote_status_and_job_proof(self):
        r=self.bridge.cancel_run(123)
        self.assertFalse(r["cancel_confirmed"])
        self.assertFalse(self.bridge.inspect_run(123)["machine_pass"])
        self.assertTrue(self.bridge.inspect_run(123)["job_readback_required"])
    def test_secret_endpoint_and_workflow_identity(self):
        with self.assertRaises(InvalidTask):GithubApiHTTPS(token="")
        cli=GithubApiHTTPS(token="synthetic")
        for bad in ("http://evil.test","/../secrets"):
            with self.assertRaisesRegex(InvalidTask,"GITHUB_API_ENDPOINT_UNSAFE"):cli("GET",bad)
        flow=(ROOT/".github/workflows/shared-test-on-demand.yml").read_text()
        self.assertIn("run-name: VF Shared "+"$"+"{{ inputs.task_id }}",flow)

if __name__=="__main__":unittest.main()
