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
            active=dict(db.execute("SELECT lane,COUNT(*) FROM tasks WHERE state IN ('LEASED','CANCEL_REQUESTED') GROUP BY lane"))
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
