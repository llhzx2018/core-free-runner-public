#!/usr/bin/env python3
"""I/O bridge for the ONE Public-owned queue to GitHub Actions REST.

Not a VM controller. Never toggles systemd or repo isolation variables.
Live dispatch fails closed until reviewed workflow is present on main.
"""
from __future__ import annotations
import json
import os
import re
import urllib.error
import urllib.request

from shared_test_queue import InvalidTask
from shared_test_router import validate, route

REPO = "llhzx2018/core-free-runner-public"
WORKFLOW = "shared-test-on-demand.yml"
# Exact reviewed Draft workflow Git blob; will only dispatch when this blob
# is independently observed on default main after separate Owner approval.
REVIEWED_WORKFLOW_BLOB = "f9fa97a6afb59942e5c9a35119009274c93061b5"
OWNER = "llhzx2018"
TEST_IDS = {"git-integrity", "python-syntax"}

def run_title(job):
    validate(job)
    return "VF Shared "+job["task_id"]+" "+job["source"]["sha"]+" "+job["test_id"]


class GithubApiHTTPS:
    """Official GitHub REST transport; only an existing injected runtime token.

    Never log request headers, error body, authorization or private payload.
    """
    def __init__(self, token=None):
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        if not isinstance(self.token,str) or not self.token or "\n" in self.token:
            raise InvalidTask("GITHUB_ACTIONS_CREDENTIAL_NOT_INJECTED")
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, url):
                raise InvalidTask("UNTRUSTED_GITHUB_REDIRECT")
        self.opener=urllib.request.build_opener(NoRedirect())

    def __call__(self,method,path,payload=None):
        if method not in ("GET","POST") or not isinstance(path,str) or not path.startswith("/") or "://" in path or ".." in path:
            raise InvalidTask("GITHUB_API_ENDPOINT_UNSAFE")
        data=None if payload is None else json.dumps(payload,separators=(",",":")).encode("utf-8")
        req=urllib.request.Request("https://api.github.com"+path,data=data,method=method,
            headers={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
                     "Authorization":"Bearer "+self.token,
                     "Content-Type":"application/json"})
        try:
            with self.opener.open(req,timeout=15) as response:
                if response.status not in (200,201,202,204):
                    raise InvalidTask("GITHUB_API_STATUS_UNEXPECTED")
                raw=response.read(2_000_000)
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raise InvalidTask("GITHUB_API_HTTP_"+str(exc.code)) from None
        except urllib.error.URLError:
            raise InvalidTask("GITHUB_API_TRANSPORT_UNAVAILABLE") from None


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
        if not isinstance(lease,dict) or lease.get("lane")!="PUBLIC_HOSTED" or not isinstance(lease.get("job"),dict) or lease.get("task_id")!=lease["job"].get("task_id"):
            raise InvalidTask("INVALID_DISPATCH_LEASE")
        expected=run_title(lease["job"])
        if not isinstance(sent_after_iso,str) or not re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", sent_after_iso):
            raise InvalidTask("INVALID_DISPATCH_WINDOW")
        self.check_remote()
        raw=self.api("GET","/repos/"+REPO+"/actions/workflows/"+WORKFLOW+"/runs?event=workflow_dispatch&per_page=100")
        if not isinstance(raw.get("workflow_runs"),list):
            raise InvalidTask("UNVERIFIED_RUN_LIST")
        matches=[]
        for run in raw["workflow_runs"]:
            if (run.get("display_title")==expected
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


    def inspect_bound_run(self, run_id, job):
        """Prove an exact Owner run and its one approved public-safe job.

        A GitHub workflow run being completed is not sufficient for machine
        PASS: verified exact input title, successful source-pin step, actual
        allocated Runner, and cleanup step must all be observed.
        """
        if type(run_id) is not int or run_id<=0:
            raise InvalidTask("RUN_ID_INVALID")
        name=run_title(job)
        self.check_remote()
        run=self.api("GET","/repos/"+REPO+"/actions/runs/"+str(run_id))
        if (not isinstance(run,dict) or run.get("id")!=run_id
                or run.get("display_title")!=name
                or run.get("event")!="workflow_dispatch"
                or run.get("head_branch")!="main"
                or not isinstance(run.get("actor"),dict)
                or run["actor"].get("login")!=OWNER
                or not isinstance(run.get("triggering_actor"),dict)
                or run["triggering_actor"].get("login")!=OWNER):
            raise InvalidTask("RUN_IDENTITY_READBACK_MISMATCH")
        result=self.api("GET","/repos/"+REPO+"/actions/runs/"+str(run_id)+"/jobs?per_page=100")
        jobs=result.get("jobs") if isinstance(result,dict) else None
        if not isinstance(jobs,list) or len(jobs)!=1:
            raise InvalidTask("RUN_JOB_CARDINALITY_UNVERIFIED")
        one=jobs[0]
        if not isinstance(one,dict) or one.get("name")!="public-safe":
            raise InvalidTask("WRONG_RUN_JOB")
        run_terminal=run.get("status")=="completed" and one.get("status")=="completed"
        step_status={}
        for step in one.get("steps",[]):
            if not isinstance(step,dict) or not isinstance(step.get("name"),str):
                raise InvalidTask("MALFORMED_STEP")
            if step["name"] in step_status:
                raise InvalidTask("DUPLICATE_STEP")
            step_status[step["name"]]=step.get("conclusion")
        required=(
            "Fail closed on unauthorized actor or input",
            "Exact private source transient checkout",
            "Verify exact SHA and run public-safe check",
            "Remove temporary private checkout",
        )
        exact_steps_ok=all(step_status.get(name)=="success" for name in required)
        runner_id=one.get("runner_id")
        verified_pass=(run_terminal
            and run.get("conclusion")=="success"
            and one.get("conclusion")=="success"
            and type(runner_id) is int and runner_id>0
            and exact_steps_ok)
        return {"run_id":run_id,"job_id":one.get("id"),
                "state":run.get("status"),"conclusion":run.get("conclusion"),
                "remote_terminal":run_terminal,"exact_input_verified":True,
                "exact_steps_verified":exact_steps_ok,
                "machine_pass":bool(verified_pass),
                "cancel_confirmed":run_terminal and run.get("conclusion")=="cancelled"}

    def cancel_run(self, run_id, job):
        """Cancel ONLY a trusted task's exact GitHub run, not any repo run ID."""
        request=validate(job)
        if request["privacy"]!="PUBLIC_SAFE" or request["profile"]=="heavy" or route(request)!="PUBLIC_HOSTED":
            raise InvalidTask("CANCEL_LANE_NOT_AUTHORIZED")
        if request["test_id"] not in TEST_IDS:
            raise InvalidTask("CANCEL_TEST_NOT_ALLOWLISTED")
        # Run IDs are globally shared within a repo. Never POST to a supplied ID
        # without binding its Owner, source SHA, task/test identity and job.
        proof=self.inspect_bound_run(run_id,request)
        if proof["remote_terminal"]:
            return {"run_id":run_id,"state":"ALREADY_TERMINAL",
                    "cancel_confirmed":proof["cancel_confirmed"],"cancel_posted":False}
        self.api("POST","/repos/"+REPO+"/actions/runs/"+str(run_id)+"/cancel",{})
        return {"run_id":run_id,"state":"CANCEL_REQUESTED",
                "cancel_confirmed":False,"cancel_posted":True}

    def inspect_run(self, run_id):
        if type(run_id) is not int or run_id<=0:
            raise InvalidTask("RUN_ID_INVALID")
        self.check_remote()
        result=self.api("GET","/repos/"+REPO+"/actions/runs/"+str(run_id))
        if result.get("id")!=run_id or result.get("event")!="workflow_dispatch":
            raise InvalidTask("RUN_READBACK_MISMATCH")
        return {"run_id":run_id,"state":result.get("status"),
                "conclusion":result.get("conclusion"),
                "machine_pass":False,"job_readback_required":True}
