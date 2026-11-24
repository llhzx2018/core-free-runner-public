"""Regression for Public-owned durable scheduler; local Linux processes only."""
import importlib.util
import multiprocessing
import json
import subprocess
import os
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0,str(SCRIPTS))
from shared_test_queue import DurableQueue, InvalidTask

CAP={"PUBLIC_HOSTED":1,"PRIVATE":0,"HYPERV_PRIVATE":0}

def job(task="task-000001",project="P01",stamp=1):
    repo={"P01":"llhzx2018/vf-startnew","P02":"llhzx2018/vf-doc","P08":"llhzx2018/vf-adops"}[project]
    return {"schema":"vf-shared-test-job/v1","task_id":task,"project":project,
            "source":{"repo":repo,"sha":"a"*40,"tree_sha":None},
            "test_id":"git-integrity","kind":"unit","privacy":"PUBLIC_SAFE","profile":"light",
            "timeout_seconds":60,"submitted_at":stamp,"allow_public_ephemeral":False}

def race_claim(file,go,result):
    go.wait()
    try:
        q=DurableQueue(file)
        result.put(q.claim(CAP,now=100)["state"] if "state" in q.claim({"PUBLIC_HOSTED":0,"PRIVATE":0,"HYPERV_PRIVATE":0},now=100) else "IMPOSSIBLE")
    except Exception as e:
        result.put("ERROR:"+type(e).__name__)

class QueueTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)/"state"
        self.root.mkdir(mode=0o700)
        self.db=self.root/"queue.sqlite"
        self.q=DurableQueue(self.db)

    def test_persistence_and_replay_across_process_objects(self):
        a=job()
        self.q.enqueue(a)
        with self.assertRaisesRegex(InvalidTask,"DUPLICATE"):
            self.q.enqueue(job(task="task-000002",stamp=999))
        self.assertEqual(DurableQueue(self.db).status(a["task_id"])["state"],"QUEUED")
        self.assertEqual(self.db.stat().st_mode & 0o077,0)

    def test_rejects_private_fields_and_wrong_project_repo(self):
        j=job();j["credential"]="SECRET"
        with self.assertRaises(InvalidTask): self.q.enqueue(j)
        j=job();j["source"]["repo"]="llhzx2018/unrelated"
        with self.assertRaisesRegex(InvalidTask,"REPO_PROJECT_MISMATCH"): self.q.enqueue(j)
        other=job(task="task-000002",project="P02")
        other["privacy"]="PRIVATE_EVIDENCE"
        self.assertEqual(self.q.enqueue(other)["lane"],"PRIVATE")
        self.assertEqual(self.q.claim(CAP,now=10)["state"],"DEFERRED_CAPACITY_OR_EMPTY")

    def test_fifo_capacity_and_cancel(self):
        self.q.enqueue(job(task="task-000001",stamp=2))
        self.q.enqueue(job(task="task-000002",project="P08",stamp=1))
        first=self.q.claim(CAP,now=100)
        self.assertEqual(first["task_id"],"task-000002")
        self.assertFalse(first["dispatched"])
        self.assertEqual(self.q.claim(CAP,now=100)["state"],"DEFERRED_CAPACITY_OR_EMPTY")
        self.assertEqual(self.q.cancel("task-000001")["state"],"CANCELLED")
        self.assertEqual(self.q.cancel("task-000002")["state"],"CANCEL_REQUESTED")
        self.assertTrue(self.q.heartbeat(first["task_id"],first["lease_token"],now=100)["cancel_requested"])
        with self.assertRaisesRegex(InvalidTask,"CANCELLED_CANNOT_PASS"):
            self.q.finish(first["task_id"],first["lease_token"],"SUCCEEDED",now=100)
        self.assertEqual(self.q.finish(first["task_id"],first["lease_token"],"CANCELLED",now=100)["state"],"CANCELLED")

    def test_lease_expiry_fails_closed_no_replay(self):
        self.q.enqueue(job())
        r=self.q.claim(CAP,now=100,lease_seconds=10)
        self.assertEqual(self.q.recover(now=110)["recovered"],1)
        self.assertEqual(DurableQueue(self.db).status("task-000001")["state"],"INTERRUPTED_NO_REPLAY")
        self.assertEqual(self.q.claim(CAP,now=111)["state"],"DEFERRED_CAPACITY_OR_EMPTY")
        with self.assertRaises(InvalidTask): self.q.finish("task-000001",r["lease_token"],"SUCCEEDED",now=100)

    def test_lease_token_and_run_binding(self):
        self.q.enqueue(job())
        r=self.q.claim(CAP,now=100)
        with self.assertRaises(InvalidTask): self.q.bind_run("task-000001","wrong",123,now=100)
        self.assertEqual(self.q.bind_run("task-000001",r["lease_token"],123,now=100)["provider_attestation"],"REQUIRES_REAL_GITHUB_READBACK")
        with self.assertRaises(InvalidTask): self.q.bind_run("task-000001",r["lease_token"],124,now=100)
        self.assertEqual(self.q.finish("task-000001",r["lease_token"],"SUCCEEDED",now=100)["state"],"SUCCEEDED")
        self.assertNotIn("token",str(self.q.status("task-000001")))

    def test_sqlite_parallel_claim_single_slot(self):
        self.q.enqueue(job())
        ctx=multiprocessing.get_context("fork")
        start=ctx.Event()
        result=ctx.Queue()
        def run(path,ev,queue):
            ev.wait()
            s=DurableQueue(path).claim(CAP,now=100)
            queue.put(s.get("task_id","DEFERRED"))
        ps=[ctx.Process(target=run,args=(self.db,start,result)) for _ in range(2)]
        for p in ps:p.start()
        start.set()
        got=[result.get(timeout=5) for _ in ps]
        for p in ps:p.join(5);self.assertEqual(p.exitcode,0)
        self.assertEqual(sorted(got),["DEFERRED","task-000001"])

    def test_expired_old_worker_cannot_heartbeat_or_commit(self):
        self.q.enqueue(job())
        a=self.q.claim(CAP,now=100,lease_seconds=10)
        for action in (
            lambda: self.q.heartbeat(a["task_id"],a["lease_token"],now=110),
            lambda: self.q.finish(a["task_id"],a["lease_token"],"SUCCEEDED",now=110),
            lambda: self.q.bind_run(a["task_id"],a["lease_token"],123,now=110),
        ):
            with self.assertRaisesRegex(InvalidTask,"LEASE_EXPIRED"):
                action()

    def test_cli_claim_never_prints_private_lease_secret(self):
        self.q.enqueue(job())
        capacity=self.root/"capacity.json"
        capacity.write_text(json.dumps(CAP))
        token_path=self.root/"private-lease-token"
        command=[sys.executable,str(SCRIPTS/"shared_test_queue.py"),"--db",str(self.db),
                 "claim","--capacity",str(capacity),"--token-file",str(token_path)]
        completed=subprocess.run(command,check=True,capture_output=True,text=True,timeout=8)
        payload=json.loads(completed.stdout)
        secret=token_path.read_text()
        self.assertEqual(len(secret),48)
        self.assertNotIn(secret,completed.stdout+completed.stderr)
        self.assertTrue(payload["lease_token_stored_privately"])
        self.assertEqual(token_path.stat().st_mode & 0o077,0)

    def test_expired_dispatch_quarantine_prevents_oversubscription(self):
        self.q.enqueue(job())
        self.q.enqueue(job(task="task-000002", project="P08"))
        first=self.q.claim(CAP,now=100,lease_seconds=10)
        self.assertEqual(self.q.recover(now=110)["recovered"],1)
        self.assertEqual(self.q.status("task-000001")["state"],"INTERRUPTED_NO_REPLAY")
        # An expired local process does NOT prove its remote job stopped.
        self.assertEqual(self.q.claim(CAP,now=111)["state"],"DEFERRED_CAPACITY_OR_EMPTY")
        refusal=self.q.reconcile_interrupted("task-000001",None)
        self.assertEqual(refusal["state"],"BLOCKED_RUN_ID_NOT_ATTESTED")
        self.assertFalse(refusal["capacity_released"])
        self.assertEqual(self.q.claim(CAP,now=112)["state"],"DEFERRED_CAPACITY_OR_EMPTY")

    def test_reconcile_uses_exact_remote_terminal_confirmation(self):
        self.q.enqueue(job())
        self.q.enqueue(job(task="task-000002",project="P08"))
        first=self.q.claim(CAP,now=100,lease_seconds=10)
        self.q.bind_run(first["task_id"],first["lease_token"],123,now=101)
        self.q.recover(now=110)
        class Remote:
            def __init__(self,terminal):self.terminal=terminal
            def inspect_bound_run(self,run_id,request):
                assert run_id==123 and request["source"]["sha"]=="a"*40
                return {"remote_terminal":self.terminal,"conclusion":"cancelled"}
        hold=self.q.reconcile_interrupted("task-000001",Remote(False))
        self.assertFalse(hold["capacity_released"])
        self.assertEqual(self.q.claim(CAP,now=111)["state"],"DEFERRED_CAPACITY_OR_EMPTY")
        release=self.q.reconcile_interrupted("task-000001",Remote(True))
        self.assertTrue(release["capacity_released"])
        self.assertEqual(self.q.status("task-000001")["state"],"INTERRUPTED_NO_REPLAY")
        self.assertEqual(self.q.claim(CAP,now=112)["task_id"],"task-000002")

    def test_untrusted_queue_directory_and_symlink(self):
        self.assertEqual(self.db.stat().st_mode & 0o077,0)
        bad=self.root/"symlink.sqlite"
        bad.symlink_to(self.db)
        with self.assertRaises(InvalidTask): DurableQueue(bad)
        self.root.chmod(0o777)
        with self.assertRaises(InvalidTask): DurableQueue(self.db)

if __name__=="__main__":
    unittest.main()
