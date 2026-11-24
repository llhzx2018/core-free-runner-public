import copy
import importlib.util
import pathlib
import unittest

FILE = pathlib.Path(__file__).resolve().parents[1] / "scripts/shared_test_router.py"
spec = importlib.util.spec_from_file_location("shared_router", FILE)
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


def job(task_id="task-000001", project="P01", privacy="PUBLIC_SAFE", profile="light", kind="unit", time=1):
    return {"schema": router.SCHEMA, "task_id": task_id, "project": project,
            "source": {"repo": "llhzx2018/vf-startnew", "sha": "a" * 40, "tree_sha": None},
            "test_id": "unit_basic", "kind": kind, "privacy": privacy, "profile": profile,
            "timeout_seconds": 90, "submitted_at": time, "allow_public_ephemeral": False}


class TestRouter(unittest.TestCase):
    def test_parallel_two_projects(self):
        a, b = job(), job("task-000002", "P08", time=2)
        b["source"]["repo"] = "llhzx2018/vf-adops"
        result = router.plan([b, a], {"PUBLIC_HOSTED": 2, "PRIVATE": 1, "HYPERV_PRIVATE": 0})
        self.assertEqual([e["decision"] for e in result["entries"]], ["ADMIT", "ADMIT"])
        self.assertEqual([e["project"] for e in result["entries"]], ["P01", "P08"])

    def test_resource_limits_and_fifo(self):
        a, b = job(), job("task-000002", "P08", time=2)
        b["source"]["repo"] = "llhzx2018/vf-adops"
        self.assertEqual(router.plan([b, a], {"PUBLIC_HOSTED": 1, "PRIVATE": 0, "HYPERV_PRIVATE": 0})["entries"][1]["decision"], "DEFER_CAPACITY")

    def test_route(self):
        j = job(privacy="PRIVATE_SOURCE")
        self.assertEqual(router.route(j), "PRIVATE")
        j["allow_public_ephemeral"] = True
        self.assertEqual(router.route(j), "PUBLIC_HOSTED")
        j = job(privacy="PRIVATE_EVIDENCE")
        self.assertEqual(router.route(j), "PRIVATE")
        j = job(profile="heavy", kind="install_restore")
        self.assertEqual(router.route(j), "HYPERV_PRIVATE")

    def test_negative_inputs(self):
        for field, value in (("timeout_seconds", True), ("privacy", "PUBLIC_SAFE; TOKEN=xxx"), ("test_id", "bash -c foo"), ("project", "P09")):
            with self.subTest(field=field), self.assertRaises(router.InvalidTask):
                x = job(); x[field] = value; router.validate(x)
        with self.assertRaises(router.InvalidTask):
            x = job(); x["token"] = "secret"; router.validate(x)
        with self.assertRaises(router.InvalidTask):
            x = job(); x["source"]["sha"] = "main"; router.validate(x)
        with self.assertRaises(router.InvalidTask):
            router.plan([job(), copy.deepcopy(job())], {"PUBLIC_HOSTED": 2, "PRIVATE": 0, "HYPERV_PRIVATE": 0})
        with self.assertRaises(router.InvalidTask):
            x = job(kind="install_restore"); router.validate(x)

    def test_identity_does_not_depend_on_time(self):
        a = job(); b = job("task-000002", time=100)
        self.assertEqual(router.identity(a), router.identity(b))

    def test_capacity_zero_is_not_fake_runner(self):
        self.assertEqual(router.plan([job()], {"PUBLIC_HOSTED": 0, "PRIVATE": 0, "HYPERV_PRIVATE": 0})["entries"][0]["decision"], "DEFER_CAPACITY")


if __name__ == "__main__":
    unittest.main()
