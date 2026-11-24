#!/usr/bin/env python3
"""I/O bridge for the ONE Public-owned queue to GitHub Actions REST.

Not a VM controller. Never toggles systemd or repo isolation variables.
Live dispatch fails closed until reviewed workflow is present on main.
"""
from __future__ import annotations
import re
import time
from datetime import datetime, timezone

from shared_test_queue import InvalidTask
from shared_test_router import validate, route

REPO = "llhzx2018/core-free-runner-public"
WORKFLOW = "shared-test-on-demand.yml"
OWNER = "llhzx2018"
TEST_IDS = {"git-integrity", "python-syntax"}

class GithubActionsBridge:
    """api(method, path, payload=None) is a trusted HTTP GitHub API adapter.

    Caller injects an authenticated real adapter with HTTPS and no logging of
    Authorization, or a fake for isolated test. No GitHub token in task JSON.
    """

    def __init__(self, api, *, expected_workflow_blob):
        if not isinstance(expected_workflow_blob, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_workflow_blob):
            raise InvalidTask("UNPINNED_WORKFLOW")
        self.api = api
        self.expected_workflow_blob = expected_workflow_blob

    def check_remote(self):
        actor=self.api("GET", "/user")
        if actor.get("login") != OWNER:
            raise InvalidTask("UNAUTHORIZED_GITHUB_ACTOR")
        repo=self.api("GET", "/repos/"+REPO)
        if repo.get("default_branch")!="main" or repo.get("private") is not False:
            raise InvalidTask("INVALID_PUBLIC_REPOSITORY")
        file=self.api("GET","/repos/"+REPO+"/contents/.github/workflows/"+WORKFLOW+"?ref=main")
        if file.get("sha") != self.expected_workflow_blob:
            raise InvalidTask("WORKFLOW_NOT_REVIEWED_ON_MAIN")
        return True

    def dispatch(self, lease):
        if not isinstance(lease,dict) or lease.get("lane")!="PUBLIC_HOSTED" or "lease_token" not in lease:
            raise InvalidTask("INVALID_DISPATCH_LEASE")
        job=validate(lease["job"])
        if job["privacy"]!="PUBLIC_SAFE" or job["profile"]=="heavy" or route(job)!="PUBLIC_HOSTED":
            raise InvalidTask("PRIVATE_OR_HEAVY_NOT_DISPATCHABLE")
        if job["test_id"] not in TEST_IDS:
            raise InvalidTask("TEST_NOT_ON_WORKFLOW_ALLOWLIST")
        if lease.get("task_id")!=job["task_id"]:
            raise InvalidTask("LEASE_TASK_MISMATCH")
        self.check_remote()
        repo=job["source"]["repo"].split("/",1)[1]
        inputs={"project":job["project"],"repo":repo,"source_sha":job["source"]["sha"],
                "tree_sha":job["source"]["tree_sha"] or "",
                "test_id":job["test_id"],"task_id":job["task_id"]}
        self.api("POST","/repos/"+REPO+"/actions/workflows/"+WORKFLOW+"/dispatches",
                 {"ref":"main","inputs":inputs})
        # GitHub returns HTTP 204 WITHOUT a Run ID. A Run must be located by
        # exact unique task ID, trusted source pins, actor and workflow readback.
        return {"task_id":job["task_id"],"state":"DISPATCH_ACCEPTED",
                "run_id":None,"machine_pass":False}

    def correlate(self, lease, *, sent_after_iso):
        if not isinstance(lease,dict) or lease.get("lane")!="PUBLIC_HOSTED":
            raise InvalidTask("INVALID_DISPATCH_LEASE")
        if not isinstance(sent_after_iso,str) or not re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", sent_after_iso):
            raise InvalidTask("INVALID_DISPATCH_WINDOW")
        self.check_remote()
        raw=self.api("GET","/repos/"+REPO+"/actions/workflows/"+WORKFLOW+"/runs?event=workflow_dispatch&per_page=100")
        if not isinstance(raw.get("workflow_runs"),list):
            raise InvalidTask("UNVERIFIED_RUN_LIST")
        matches=[]
        for run in raw["workflow_runs"]:
            if (run.get("display_title")=="VF Shared "+lease["task_id"]
                and run.get("event")=="workflow_dispatch"
                and run.get("head_branch")=="main"
                and run.get("actor",{}).get("login")==OWNER
                and run.get("triggering_actor",{}).get("login")==OWNER
                and run.get("created_at","")>=sent_after_iso
                and type(run.get("id")) is int and run["id"]>0):
                matches.append(run["id"])
        if len(matches)!=1:
            raise InvalidTask("RUN_CORRELATION_NOT_UNIQUE")
        return {"task_id":lease["task_id"],"run_id":matches[0],
                "verified_source":"GITHUB_ACTIONS_READBACK","machine_pass":False}

    def cancel_run(self, run_id):
        if type(run_id) is not int or run_id<=0:
            raise InvalidTask("RUN_ID_REQUIRED_FOR_CANCEL")
        self.check_remote()
        self.api("POST","/repos/"+REPO+"/actions/runs/"+str(run_id)+"/cancel",{})
        return {"run_id":run_id,"state":"CANCEL_REQUESTED",
                "cancel_confirmed":False}  # requires GET on real run

    def inspect_run(self, run_id):
        if type(run_id) is not int or run_id<=0:
            raise InvalidTask("RUN_ID_INVALID")
        self.check_remote()
        result=self.api("GET","/repos/"+REPO+"/actions/runs/"+str(run_id))
        if result.get("id")!=run_id or result.get("event")!="workflow_dispatch":
            raise InvalidTask("RUN_READBACK_MISMATCH")
        return {"run_id":run_id,"state":result.get("status"),
                "conclusion":result.get("conclusion"),
                "machine_pass":result.get("status")=="completed" and result.get("conclusion")=="success"}
