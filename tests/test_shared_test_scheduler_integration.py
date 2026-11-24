"""One Public queue + one reviewed Actions adapter; no additional controller."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"tests"))
from shared_test_queue import DurableQueue, InvalidTask
from shared_test_actions_bridge import GithubActionsBridge
from test_shared_test_actions_bridge import Fake, lease

CAP={"PUBLIC_HOSTED":1,"PRIVATE":0,"HYPERV_PRIVATE":0}

class Remote(Fake):
    def __init__(self):
        super().__init__()
        self.mode="success"
        run={"id":123,"display_title":"VF Shared task-actions-0001 "+"a"*40+" git-integrity",
             "event":"workflow_dispatch","head_branch":"main",
             "actor":{"login":"llhzx2018"},"triggering_actor":{"login":"llhzx2018"},
             "created_at":"2099-01-01T00:00:00Z"}
        self.runs=[run]
        self.run=run

    def __call__(self,method,path,payload=None):
        if path=="/repos/llhzx2018/core-free-runner-public/actions/runs/123":
            return dict(self.run,status="in_progress" if self.mode=="running" else "completed",
                        conclusion=None if self.mode=="running" else self.mode)
        if path.endswith("/jobs?per_page=100"):
            return {"jobs":[{"id":456,"name":"public-safe",
                    "status":"in_progress" if self.mode=="running" else "completed",
                    "conclusion":None if self.mode=="running" else self.mode,
                    "runner_id":789,
                    "steps":[{"name":name,"conclusion":"success" if self.mode=="success" else None}
                             for name in ("Fail closed on unauthorized actor or input",
                                          "Exact private source transient checkout",
                                          "Verify exact SHA and run public-safe check",
                                          "Remove temporary private checkout")]}]}
        return super().__call__(method,path,payload)

class IntegratedTest(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
        folder=Path(td.name)/"restricted";folder.mkdir(mode=0o700)
        self.q=DurableQueue(folder/"queue.db")
        self.api=Remote()
        self.bridge=GithubActionsBridge(self.api,expected_workflow_blob="b"*40)
        self.j=lease()["job"]

    def test_no_main_review_no_dispatch_and_queue_unchanged(self):
        self.q.enqueue(self.j)
        self.api.blob="c"*40
        with self.assertRaisesRegex(InvalidTask,"WORKFLOW_NOT_REVIEWED_ON_MAIN"):
            self.q.dispatch_public_once(self.bridge,now=100)
        self.assertEqual(self.q.status(self.j["task_id"])["state"],"QUEUED")
        self.assertEqual(self.api.posts,[])

    def test_real_single_queue_method_fake_provider_success(self):
        self.q.enqueue(self.j)
        result=self.q.dispatch_public_once(self.bridge,capacity=1,now=100)
        self.assertEqual(result["state"],"DISPATCH_ACCEPTED_AWAIT_RUN_READBACK")
        self.assertNotIn("lease_token",json.dumps(result))
        proof=self.q.poll_public_once(self.j["task_id"],self.bridge,now=101)
        self.assertEqual(proof["state"],"SUCCEEDED")
        self.assertTrue(proof["machine_pass"]) # MOCK provider, never machine evidence
        persisted=DurableQueue(self.q.path).status(self.j["task_id"])
        self.assertEqual(persisted["run_id"],123)
        self.assertEqual(persisted["job_id"],456)
        self.assertEqual(self.q.dispatch_public_once(self.bridge,capacity=1,now=102)["state"],
                         "DEFERRED_CAPACITY_OR_EMPTY")

    def test_remote_cancel_request_and_verified_terminal(self):
        self.q.enqueue(self.j)
        self.q.dispatch_public_once(self.bridge,capacity=1,now=100)
        self.api.mode="running"
        self.assertEqual(self.q.cancel(self.j["task_id"])["state"],"CANCEL_REQUESTED")
        progress=self.q.poll_public_once(self.j["task_id"],self.bridge,now=101)
        self.assertEqual(progress["state"],"REMOTE_CANCEL_REQUESTED")
        self.assertFalse(progress["machine_pass"])
        self.assertTrue(any(path.endswith("/actions/runs/123/cancel") for path,_ in self.api.posts))
        self.api.mode="cancelled"
        final=self.q.poll_public_once(self.j["task_id"],self.bridge,now=102)
        self.assertEqual(final["state"],"CANCELLED")
        self.assertTrue(final["cancel_confirmed"])
        self.assertFalse(final["machine_pass"])

    def test_unknown_network_outcome_quarantines_capacity(self):
        self.q.enqueue(self.j)
        other=lease()["job"].copy()
        other["source"]={**other["source"],"sha":"f"*40}
        other["task_id"]="task-actions-0002"
        self.q.enqueue(other)
        original=self.api.__call__
        class Loss:
            def __call__(_,method,path,payload=None):
                if method=="POST" and path.endswith("/dispatches"):
                    self.api.posts.append((path,payload))
                    raise RuntimeError("synthetic_http_reply_lost")
                return original(method,path,payload)
        bridge=GithubActionsBridge(Loss(),expected_workflow_blob="b"*40)
        response=self.q.dispatch_public_once(bridge,capacity=1,now=100)
        self.assertEqual(response["state"],"DISPATCH_OUTCOME_UNKNOWN_NO_REPLAY")
        self.assertEqual(self.q.recover(now=3700)["recovered"],1)
        self.assertEqual(self.q.claim(CAP,now=3701)["state"],"DEFERRED_CAPACITY_OR_EMPTY")
        self.assertEqual(sum(path.endswith("/dispatches") for path,_ in self.api.posts),1)
        # No Run indexed yet -> still quarantined, not a fake recovery PASS.
        known=self.api.runs
        self.api.runs=[]
        self.assertFalse(self.q.reconcile_interrupted(self.j["task_id"],self.bridge)["capacity_released"])
        self.assertEqual(self.q.claim(CAP,now=3702)["state"],"DEFERRED_CAPACITY_OR_EMPTY")
        # An independently attested exact Run may release capacity, but the
        # interrupted task itself is NEVER replayed.
        self.api.runs=known
        clean=self.q.reconcile_interrupted(self.j["task_id"],self.bridge)
        self.assertTrue(clean["capacity_released"])
        self.assertEqual(clean["run_id"],123)
        self.assertEqual(self.q.status(self.j["task_id"])["state"],"INTERRUPTED_NO_REPLAY")
        self.assertEqual(self.q.claim(CAP,now=3703)["task_id"],other["task_id"])

if __name__=="__main__":
    unittest.main()
