#!/usr/bin/env python3
"""Public-owned persistent admission queue. No remote dispatch or VM control."""
from __future__ import annotations
import argparse
import json
import os
import secrets
import sqlite3
import stat
import time
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from shared_test_router import validate, identity, route, InvalidTask

SCHEMA = "vf-shared-test-queue/v1"
LANES = {"PUBLIC_HOSTED", "PRIVATE", "HYPERV_PRIVATE"}
REPOS = {"P01": {"llhzx2018/vf-startnew"}, "P02": {"llhzx2018/vf-doc"},
         "P07": {"llhzx2018/vf-server-ops"}, "P08": {"llhzx2018/vf-adops"},
         "S01": {"llhzx2018/vf-tools-theme", "llhzx2018/vf-tools-ops", "llhzx2018/vf-tools-m3u8"}}
STATES = {"QUEUED", "LEASED", "CANCEL_REQUESTED", "SUCCEEDED", "TEST_FAILED",
          "INFRA_FAILED", "CANCELLED", "INTERRUPTED_NO_REPLAY"}

class DurableQueue:
    """One trusted host, SQLite BEGIN IMMEDIATE; not shared across Hosted VMs."""
    def __init__(self, path):
        self.path = Path(path)
        parent = self.path.parent
        if not parent.is_dir() or parent.is_symlink() or (parent.stat().st_mode & 0o077) or parent.stat().st_uid != os.geteuid():
            raise InvalidTask("QUEUE_PARENT_UNSAFE")
        if self.path.is_symlink():
            raise InvalidTask("QUEUE_SYMLINK")
        if self.path.exists():
            st = self.path.stat()
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.geteuid() or (st.st_mode & 0o077):
                raise InvalidTask("QUEUE_FILE_UNSAFE")
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tasks(
               task_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE,
               job_json TEXT NOT NULL, lane TEXT NOT NULL, submitted_at INTEGER NOT NULL,
               state TEXT NOT NULL, token TEXT, deadline INTEGER, cancel_requested INTEGER NOT NULL DEFAULT 0,
               run_id INTEGER, job_id INTEGER, result_reason TEXT)""")
            db.execute("CREATE INDEX IF NOT EXISTS vf_queue_fifo ON tasks(state,submitted_at,task_id)")
            # Safe candidate migration: this timestamp is written before any
            # non-idempotent GitHub dispatch POST, to recover unknown replies.
            columns={row[1] for row in db.execute("PRAGMA table_info(tasks)")}
            if "dispatch_started_at" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN dispatch_started_at TEXT")

    @contextmanager
    def connect(self):
        if self.path.is_symlink():
            raise InvalidTask("QUEUE_SYMLINK")
        db = sqlite3.connect(self.path, isolation_level=None, timeout=5)
        try:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            os.chmod(self.path, 0o600)
            yield db
        finally:
            db.close()

    @contextmanager
    def tx(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def enqueue(self, job):
        validate(job)
        if job["source"]["repo"] not in REPOS[job["project"]]:
            raise InvalidTask("REPO_PROJECT_MISMATCH")
        lane = route(job)  # request flag cannot grant private source on Public
        if lane=="PUBLIC_HOSTED" and job["timeout_seconds"]>1200:
            raise InvalidTask("PUBLIC_HOSTED_TIMEOUT_EXCEEDS_20_MIN")
        with self.tx() as db:
            try:
                db.execute("INSERT INTO tasks(task_id,fingerprint,job_json,lane,submitted_at,state) VALUES(?,?,?,?,?,'QUEUED')",
                           (job["task_id"], identity(job), json.dumps(job, sort_keys=True, separators=(",", ":")),
                            lane, job["submitted_at"]))
            except sqlite3.IntegrityError as e:
                raise InvalidTask("DUPLICATE_OR_REPLAY") from e
        return {"task_id": job["task_id"], "state": "QUEUED", "lane": lane}

    @staticmethod
    def _expire(db, now):
        db.execute("""UPDATE tasks SET state='INTERRUPTED_NO_REPLAY',token=NULL,result_reason='LEASE_EXPIRED'
                   WHERE state IN ('LEASED','CANCEL_REQUESTED') AND deadline<=?""", (now,))
        return db.execute("SELECT changes()").fetchone()[0]

    def recover(self, now=None):
        if now is None: now=int(time.time())
        with self.tx() as db:
            count=self._expire(db, now)
        return {"recovered":count,"hyperv_runner":"NOT_VERIFIED","isolation_variable":"NOT_VERIFIED"}

    def claim(self, capacities, now=None, lease_seconds=300):
        if not isinstance(capacities, dict) or set(capacities)!=LANES or any(type(v) is not int or not 0<=v<=32 for v in capacities.values()):
            raise InvalidTask("INVALID_CAPACITY")
        if type(lease_seconds) is not int or not 1<=lease_seconds<=7200:
            raise InvalidTask("INVALID_LEASE")
        if now is None: now=int(time.time())
        with self.tx() as db:
            self._expire(db, now)
            # Expired leases are quarantined until the exact remote run is
            # independently confirmed terminal; never oversubscribe a lane
            # while an unobserved Hosted job may still be running.
            active=dict(db.execute("""SELECT lane,COUNT(*) FROM tasks
                  WHERE state IN ('LEASED','CANCEL_REQUESTED')
                     OR (state='INTERRUPTED_NO_REPLAY' AND
                         COALESCE(result_reason,'')!='REMOTE_TERMINAL_VERIFIED')
                  GROUP BY lane"""))
            rows=db.execute("SELECT task_id,job_json,lane FROM tasks WHERE state='QUEUED' ORDER BY submitted_at,task_id").fetchall()
            for task_id, raw, lane in rows:
                if active.get(lane,0)>=capacities[lane]: continue
                token=secrets.token_hex(24)
                db.execute("UPDATE tasks SET state='LEASED',token=?,deadline=? WHERE task_id=?",
                           (token,now+lease_seconds,task_id))
                return {"task_id":task_id,"job":json.loads(raw),"lane":lane,
                        "lease_token":token,"deadline":now+lease_seconds,"dispatched":False}
        return {"state":"DEFERRED_CAPACITY_OR_EMPTY","dispatched":False}

    @staticmethod
    def _lease(db, task_id, token, now=None):
        if now is None: now=int(time.time())
        row=db.execute("SELECT state,token,cancel_requested,deadline FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        if not row or not isinstance(token,str) or row[1] is None or not secrets.compare_digest(row[1],token):
            raise InvalidTask("INVALID_LEASE_TOKEN")
        if row[0] not in {"LEASED","CANCEL_REQUESTED"}:
            raise InvalidTask("LEASE_NOT_ACTIVE")
        if row[3] is None or row[3] <= now:
            raise InvalidTask("LEASE_EXPIRED")
        return row

    def heartbeat(self,task_id,token,now=None,lease_seconds=300):
        if now is None: now=int(time.time())
        if type(lease_seconds) is not int or not 1<=lease_seconds<=7200:
            raise InvalidTask("INVALID_LEASE")
        with self.tx() as db:
            row=self._lease(db,task_id,token,now)
            db.execute("UPDATE tasks SET deadline=? WHERE task_id=?",(now+lease_seconds,task_id))
        return {"task_id":task_id,"cancel_requested":bool(row[2])}

    def cancel(self,task_id):
        with self.tx() as db:
            row=db.execute("SELECT state FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if row is None: raise InvalidTask("UNKNOWN_TASK")
            if row[0]=="QUEUED":
                new="CANCELLED"
                db.execute("UPDATE tasks SET state=?,result_reason='BEFORE_DISPATCH' WHERE task_id=?",(new,task_id))
            elif row[0] in ("LEASED","CANCEL_REQUESTED"):
                new="CANCEL_REQUESTED"
                db.execute("UPDATE tasks SET state=?,cancel_requested=1 WHERE task_id=?",(new,task_id))
            else: new=row[0]
        return {"task_id":task_id,"state":new}

    def bind_run(self,task_id,token,run_id,job_id=None,now=None):
        if type(run_id) is not int or run_id<=0 or (job_id is not None and (type(job_id) is not int or job_id<=0)):
            raise InvalidTask("INVALID_RUN_ID")
        with self.tx() as db:
            self._lease(db,task_id,token,now)
            old=db.execute("SELECT run_id FROM tasks WHERE task_id=?",(task_id,)).fetchone()[0]
            if old is not None and old!=run_id: raise InvalidTask("RUN_BINDING_IMMUTABLE")
            db.execute("UPDATE tasks SET run_id=?,job_id=COALESCE(job_id,?) WHERE task_id=?",(run_id,job_id,task_id))
        return {"task_id":task_id,"run_id":run_id,"provider_attestation":"REQUIRES_REAL_GITHUB_READBACK"}

    def finish(self,task_id,token,result,now=None):
        if result not in {"SUCCEEDED","TEST_FAILED","INFRA_FAILED","CANCELLED"}:
            raise InvalidTask("INVALID_RESULT")
        with self.tx() as db:
            row=self._lease(db,task_id,token,now)
            if row[2] and result=="SUCCEEDED": raise InvalidTask("CANCELLED_CANNOT_PASS")
            db.execute("UPDATE tasks SET state=?,token=NULL WHERE task_id=?",(result,task_id))
        return {"task_id":task_id,"state":result}


    def dispatch_public_once(self, bridge, *, capacity=2, now=None):
        """One local queue -> reviewed GitHub workflow, with no second daemon.

        Preflight checks main/Owner BEFORE admission. POST intent is durable
        before network call, so network loss can never trigger silent replay.
        """
        if type(capacity) is not int or not 0<=capacity<=2:
            raise InvalidTask("UNVERIFIED_PUBLIC_HOSTED_CAPACITY")
        bridge.check_remote()
        lease=self.claim({"PUBLIC_HOSTED":capacity,"PRIVATE":0,"HYPERV_PRIVATE":0},
                         now=now,lease_seconds=3600)
        if "task_id" not in lease:
            return lease
        task_id=lease["task_id"]
        at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.tx() as db:
            row=self._lease(db,task_id,lease["lease_token"],now)
            if row[2]:
                db.execute("UPDATE tasks SET state='CANCELLED',token=NULL WHERE task_id=?",(task_id,))
                return {"task_id":task_id,"state":"CANCELLED_BEFORE_NETWORK"}
            db.execute("""UPDATE tasks SET dispatch_started_at=?,result_reason='DISPATCH_OUTCOME_UNCERTAIN'
                          WHERE task_id=? AND dispatch_started_at IS NULL""",(at,task_id))
            if db.execute("SELECT changes()").fetchone()[0]!=1:
                raise InvalidTask("DUPLICATE_DISPATCH_INTENT")
        try:
            bridge.dispatch(lease)
        except Exception:
            # Includes network errors AFTER GitHub could have accepted the
            # POST. Never call dispatch again or free capacity automatically.
            return {"task_id":task_id,"state":"DISPATCH_OUTCOME_UNKNOWN_NO_REPLAY",
                    "run_id":None,"machine_pass":False}
        return {"task_id":task_id,"state":"DISPATCH_ACCEPTED_AWAIT_RUN_READBACK",
                "run_id":None,"machine_pass":False}

    def poll_public_once(self, task_id, bridge, *, now=None):
        """Advance one existing dispatched job; real Run/Job readback required."""
        if now is None: now=int(time.time())
        with self.connect() as db:
            row=db.execute("""SELECT state,token,run_id,job_json,dispatch_started_at
                              FROM tasks WHERE task_id=?""",(task_id,)).fetchone()
        if not row: raise InvalidTask("UNKNOWN_TASK")
        state,token,run_id,raw,dispatch_at=row
        if state not in ("LEASED","CANCEL_REQUESTED"):
            return {"task_id":task_id,"state":state,"machine_pass":False}
        if not dispatch_at:
            return {"task_id":task_id,"state":"BLOCKED_NO_REMOTE_DISPATCH_INTENT","machine_pass":False}
        job=json.loads(raw)
        if run_id is None:
            try:
                match=bridge.correlate({"task_id":task_id,"lane":"PUBLIC_HOSTED",
                                        "job":job},sent_after_iso=dispatch_at)
                run_id=match["run_id"]
                self.bind_run(task_id,token,run_id,now=now)
            except InvalidTask:
                return {"task_id":task_id,"state":"RUN_CORRELATION_NOT_PROVEN","machine_pass":False}
        proof=bridge.inspect_bound_run(run_id,job)
        if proof["remote_terminal"]:
            if state=="CANCEL_REQUESTED":
                final="CANCELLED" if proof["cancel_confirmed"] else "INFRA_FAILED"
            elif proof["machine_pass"]:
                final="SUCCEEDED"
            else:
                final="INFRA_FAILED"
            self.finish(task_id,token,final,now=now)
            return {"task_id":task_id,"state":final,"run_id":run_id,
                    "job_id":proof.get("job_id"),
                    "machine_pass":final=="SUCCEEDED" and proof["machine_pass"],
                    "cancel_confirmed":proof["cancel_confirmed"]}
        if state=="CANCEL_REQUESTED":
            bridge.cancel_run(run_id)  # POST is intent only; never claim cancel
            self.heartbeat(task_id,token,now=now,lease_seconds=3600)
            return {"task_id":task_id,"state":"REMOTE_CANCEL_REQUESTED",
                    "run_id":run_id,"machine_pass":False}
        self.heartbeat(task_id,token,now=now,lease_seconds=3600)
        return {"task_id":task_id,"state":"REMOTE_RUNNING","run_id":run_id,
                "machine_pass":False}

    def reconcile_interrupted(self, task_id, bridge):
        """Release capacity only after authenticated GitHub terminal readback.

        The task stays INTERRUPTED_NO_REPLAY and is NEVER re-enqueued. Missing
        Run ID leaves capacity quarantined, including a dispatch whose HTTP
        response was lost before GitHub supplied a Run ID.
        """
        with self.connect() as db:
            row=db.execute("SELECT state,run_id,job_json,result_reason FROM tasks WHERE task_id=?",
                           (task_id,)).fetchone()
        if row is None: raise InvalidTask("UNKNOWN_TASK")
        state,run_id,raw,reason=row
        if state!="INTERRUPTED_NO_REPLAY":
            raise InvalidTask("NOT_INTERRUPTED")
        if reason=="REMOTE_TERMINAL_VERIFIED":
            return {"task_id":task_id,"state":state,"capacity_released":True}
        if type(run_id) is not int or run_id<=0:
            return {"task_id":task_id,"state":"BLOCKED_RUN_ID_NOT_ATTESTED",
                    "capacity_released":False}
        proof=bridge.inspect_bound_run(run_id,json.loads(raw))
        if proof.get("remote_terminal") is not True:
            return {"task_id":task_id,"state":"WAITING_REMOTE_TERMINAL",
                    "capacity_released":False}
        with self.tx() as db:
            db.execute("""UPDATE tasks SET result_reason='REMOTE_TERMINAL_VERIFIED'
                          WHERE task_id=? AND state='INTERRUPTED_NO_REPLAY'
                            AND run_id=?""",(task_id,run_id))
            if db.execute("SELECT changes()").fetchone()[0]!=1:
                raise InvalidTask("RECONCILE_STATE_DRIFT")
        return {"task_id":task_id,"state":"INTERRUPTED_NO_REPLAY",
                "capacity_released":True,"run_id":run_id,
                "remote_conclusion":proof.get("conclusion"),
                "machine_pass":False}

    def status(self,task_id):
        with self.connect() as db:
            row=db.execute("SELECT state,lane,cancel_requested,run_id,job_id FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        if row is None: raise InvalidTask("UNKNOWN_TASK")
        return dict(zip(("state","lane","cancel_requested","run_id","job_id"),row))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",type=Path,required=True)
    subs=p.add_subparsers(dest="action",required=True)
    e=subs.add_parser("enqueue");e.add_argument("--job",type=Path,required=True)
    c=subs.add_parser("claim");c.add_argument("--capacity",type=Path,required=True);c.add_argument("--token-file",type=Path,required=True)
    for action in ("status","cancel"):
        a=subs.add_parser(action);a.add_argument("--task-id",required=True)
    subs.add_parser("recover")
    args=p.parse_args()
    try:
        q=DurableQueue(args.db)
        if args.action=="enqueue": ans=q.enqueue(json.loads(args.job.read_text()))
        elif args.action=="claim":
            # Capability token never goes to stdout, GitHub logs or artifacts.
            ans=q.claim(json.loads(args.capacity.read_text()))
            if "lease_token" in ans:
                out=args.token_file
                parent=out.parent
                if parent.is_symlink() or not parent.is_dir() or parent.stat().st_uid != os.geteuid() or parent.stat().st_mode & 0o077:
                    raise InvalidTask("TOKEN_DIR_UNSAFE")
                fd=os.open(out,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,"w") as f:
                    f.write(ans.pop("lease_token"))
                    f.flush()
                    os.fsync(f.fileno())
                ans["lease_token_stored_privately"]=True
        elif args.action=="status": ans=q.status(args.task_id)
        elif args.action=="cancel": ans=q.cancel(args.task_id)
        else: ans=q.recover()
        print(json.dumps({"schema":SCHEMA,**ans},sort_keys=True));return 0
    except (InvalidTask,OSError,ValueError,sqlite3.Error) as exc:
        print(json.dumps({"status":"BLOCKED_VALIDATION","reason":str(exc) if isinstance(exc,InvalidTask) else "LOCAL_STATE_ERROR"}));return 2

if __name__=="__main__":
    raise SystemExit(main())
