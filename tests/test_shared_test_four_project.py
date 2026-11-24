"""Four project VF Test admission regression; only local synthetic CPU-light tasks.

This is not evidence of a remote GitHub workflow_dispatch or Hyper-V control.
"""
import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from shared_test_queue import DurableQueue, InvalidTask
from shared_test_router import route

PINS = {
    "P01": ("llhzx2018/vf-startnew", "a37927c5b2ecb0372816adfb53aef17d0d575611"),
    "P02": ("llhzx2018/vf-doc", "a292cbe9f5d17e1ca62a70fa5ba6f1f50dc39ba1"),
    "P07": ("llhzx2018/vf-server-ops", "e379e29a8c3d5a425da8551d4f67ff373a837b8b"),
    "P08": ("llhzx2018/vf-adops", "42bc1199835789aa55a7f5f60383a1270e2e15e5"),
}
CAPACITY = {"PUBLIC_HOSTED": 2, "PRIVATE": 0, "HYPERV_PRIVATE": 0}

def make(project):
    repo, sha = PINS[project]
    return {"schema": "vf-shared-test-job/v1", "task_id": "vf4-20261124-" + project.lower() + "-01",
            "project": project, "source": {"repo": repo, "sha": sha, "tree_sha": None},
            "test_id": "git-integrity", "kind": "lint", "privacy": "PUBLIC_SAFE",
            "profile": "light", "timeout_seconds": 90,
            "submitted_at": {"P01": 1, "P02": 2, "P07": 3, "P08": 4}[project],
            "allow_public_ephemeral": False}

def competing_worker(db, begin, results):
    begin.wait(5)
    try:
        r = DurableQueue(db).claim(CAPACITY, now=100)
        results.put((r.get("task_id", "DEFERRED"), r.get("lane", "")))
    except Exception:
        results.put(("WORKER_FAILURE", ""))

class FourProjectTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name) / "private-state"
        root.mkdir(mode=0o700)
        self.q = DurableQueue(root / "tasks.sqlite")

    def seed(self):
        for project in PINS:
            self.q.enqueue(make(project))

    def test_distinct_project_source_sha_task_identity(self):
        self.seed()
        ids = set()
        for project, (repo, sha) in PINS.items():
            j = make(project)
            self.assertNotIn(j["task_id"], ids)
            ids.add(j["task_id"])
            self.assertEqual(j["source"]["repo"], repo)
            self.assertEqual(j["source"]["sha"], sha)
            self.assertEqual(self.q.status(j["task_id"])["state"], "QUEUED")

    def test_four_actual_competing_local_processes_respect_two_slots(self):
        self.seed()
        ctx = multiprocessing.get_context("fork")
        start, result = ctx.Event(), ctx.Queue()
        jobs = [ctx.Process(target=competing_worker, args=(self.q.path, start, result))
                for _ in range(4)]
        for p in jobs:
            p.start()
        start.set()
        states = [result.get(timeout=8)[0] for _ in jobs]
        for p in jobs:
            p.join(8)
            self.assertEqual(p.exitcode, 0)
        active = [s for s in states if s != "DEFERRED"]
        self.assertEqual(len(active), 2)
        self.assertEqual(len(set(active)), 2)
        self.assertEqual(states.count("DEFERRED"), 2)
        self.assertEqual({self.q.status(x)["state"] for x in active}, {"LEASED"})

    def test_cancel_p07_does_not_cancel_p01_p02_p08(self):
        self.seed()
        target = make("P07")["task_id"]
        self.assertEqual(self.q.cancel(target)["state"], "CANCELLED")
        self.assertEqual(self.q.status(target)["state"], "CANCELLED")
        for other in ("P01", "P02", "P08"):
            self.assertEqual(self.q.status(make(other)["task_id"])["state"], "QUEUED")
        first, second = self.q.claim(CAPACITY, now=100), self.q.claim(CAPACITY, now=100)
        self.assertEqual([first["task_id"], second["task_id"]],
                         [make("P01")["task_id"], make("P02")["task_id"]])
        self.assertEqual(self.q.claim(CAPACITY, now=100)["state"], "DEFERRED_CAPACITY_OR_EMPTY")
        self.q.finish(first["task_id"], first["lease_token"], "SUCCEEDED", now=100)
        self.assertEqual(self.q.claim(CAPACITY, now=100)["task_id"], make("P08")["task_id"])

    def test_replay_and_forged_project_rejected_without_queue_damage(self):
        self.seed()
        spoof = make("P08")
        spoof["project"] = "P01"
        with self.assertRaisesRegex(InvalidTask, "REPO_PROJECT_MISMATCH"):
            self.q.enqueue(spoof)
        with self.assertRaisesRegex(InvalidTask, "DUPLICATE_OR_REPLAY"):
            self.q.enqueue(make("P02"))
        duplicate_content = make("P02")
        duplicate_content["task_id"] = "vf4-20261124-p02-copy"
        duplicate_content["submitted_at"] = 999
        with self.assertRaisesRegex(InvalidTask, "DUPLICATE_OR_REPLAY"):
            self.q.enqueue(duplicate_content)
        for project in PINS:
            self.assertEqual(self.q.status(make(project)["task_id"])["state"], "QUEUED")

    def test_private_source_flag_cannot_self_grant_public_route(self):
        j = make("P02")
        j["privacy"] = "PRIVATE_SOURCE"
        j["allow_public_ephemeral"] = True
        self.assertEqual(route(j), "PRIVATE")
        self.assertEqual(route(j, approved_ephemeral_source=True), "PUBLIC_HOSTED")
        j["profile"] = "heavy"
        self.assertEqual(route(j, approved_ephemeral_source=True), "HYPERV_PRIVATE")

if __name__ == "__main__":
    unittest.main()
