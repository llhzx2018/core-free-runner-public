# VF shared free test protocol v1 (Public-owned)

Applies to the registered Public #4471 / Private #42 Runner pair. This owns only the shared interface; no third Runner, controller or central state store.

Request keys (all mandatory; unknown keys rejected): `schema`, `task_id`, `project`, `source`, `test_id`, `kind`, `privacy`, `profile`, `timeout_seconds`, `submitted_at`, `allow_public_ephemeral`.
`schema`: `vf-shared-test-job/v1`; `source`: `{repo: llhzx2018/<repo>, sha: 40 lowercase hex, tree_sha: 40 lowercase hex or null}`. Projects: P01/P02/P07/P08/S01. Types: lint/unit/build/integration/install_restore. Profile: light/normal/heavy. Privacy: PUBLIC_SAFE/PRIVATE_SOURCE/PRIVATE_EVIDENCE.

Project's test command must come from **trusted executor configuration**, selected by the opaque `test_id`. **Never execute shell text from a request.** Verify checked-out Git HEAD SHA and optional Tree SHA before running; reject dirty workspaces and unknown files/fields.

Public routes PUBLIC_SAFE light/normal to `PUBLIC_HOSTED`; PRIVATE_SOURCE requires both `allow_public_ephemeral` and a separate trusted runtime approval (a self-declared request boolean is never authorization) and mandatory transient checkout+cleanup to use Public; PRIVATE_EVIDENCE goes Private; every heavy task is `HYPERV_PRIVATE`. Routing is not dispatch. Public `ADMIT` is only planning; actual free Hosted capacity and GitHub Run/Job must be independently verified.

Dedup: Public stable fingerprint SHA-256 over canonical JSON without `task_id` and `submitted_at`; Private atomically creates per-task ID receipt to prevent replay. Private process-level project locks + global heavy lock allow non-conflicting projects to run in parallel. Heavy installation/recovery requires independent resource guards, not merely a YAML `max-parallel` claim.

Private receipt `vf-shared-test-receipt/v1`: task_id/project/source_sha/test_id/status/exit_code/failure reason. Raw private output, source, secrets, cookies, backup, and data never reach Public logs or evidence. Actual Run/Job pointers must be attached only after reading real GitHub responses.

Interrupted process: do not replay; inspect any live child PID; mark abandoned task `INTERRUPTED_NO_REPLAY` only if no process is alive. Runner disabled + GitHub isolation variable `NO` remain NOT_VERIFIED unless independently read back. Existing P02 Draft PR #2 is review-only and must not be enabled by this protocol.

This PR is DEV source, not active deployment, dispatched jobs, free capacity proof or Hyper-V machine PASS.

## Stage A durable admission (candidate, not activated)

One owner of scheduling: Public scripts/shared_test_router.py for route policy and scripts/shared_test_queue.py for persistent queue. Private's file tickets are only a local mutex/fairness mechanism, not another global scheduler.

- Request payload is exactly the v1 envelope above; source repo is cross-checked against project allowlist; no command/credential values are accepted. Caller-supplied public ephemeral approval is never trusted.
- The queue is a private local SQLite file under a trusted owner-owned 0700 directory, mode 0600 with BEGIN IMMEDIATE transactions, distinct task_id and stable fingerprint unique constraints, and FIFO per admission cycle.
- Queue states: QUEUED, LEASED, CANCEL_REQUESTED, SUCCEEDED, TEST_FAILED, INFRA_FAILED, CANCELLED, INTERRUPTED_NO_REPLAY. After lease expiry the old worker cannot heartbeat, attach a Run ID or declare success. Restart recovery never automatically replays a possibly executed job.
- Each lane has a separately declared 0–32 admission capacity. Capacity=0 means defer, NOT a fake Runner. This is a single-host bound, **not** an actual measurement of available GitHub Hosted or Hyper-V capacity.
- Cancel a queued task immediately. A leased task is only marked CANCEL_REQUESTED until its trusted executor actually cancels it and returns a final receipt. There is **no** claim of remote GitHub cancellation by the queue alone.
- Queue can bind a positive GitHub Run ID immutably when passed by a trusted adapter, but external GitHub Run/Job readback is mandatory before a machine-pass claim. No user-supplied run ID means machine evidence.
- The Python API returns a single-use 48-character lease capability. CLI claim requires --token-file, writes it only to a trusted 0700 directory using O_EXCL mode 0600, and never prints it. It must never be saved in Public Git, Actions artifact or public logs.
- The local SQLite file persists across local process restarts ONLY. GitHub Hosted ephemeral VMs are not a shared persistent disk. Real multi-host dispatch/state needs a separately reviewed, existing authorized control plane; neither Public nor Private has been activated as that service.

## Private execution compatibility

Private scripts/shared_test_private.py consumes exactly vf-shared-test-job/v1, requires a trusted local catalog, exact clean git SHA/tree, a 0700 state root, single-use task fingerprint, bounded project-ticket queues, process-group timeout and sanitized receipt. Test subprocess env is explicit allowlist, never inherits Host's GitHub token/SSH socket.

For every heavy task, Private obtains the **same physical path** as P02 Draft PR #2: /run/lock/vf-shared-heavy.lock, root-owned, opened O_NOFOLLOW and kept through the job. This avoids a second local heavy.lock inode. Cooperative locks protect only participants; other workloads that do not use that lock remain outside the guarantee. The synthetic unit tests use an injected lock accessible only from Python test code; the real CLI cannot override the hardware path.

On interrupted runs, Private checks recorded controller/child PIDs. It only removes a stale FIFO ticket when neither process exists; it retains dedup evidence, returns INTERRUPTED_NO_REPLAY and still reports GitHub variable NO/Runner stop state NOT_VERIFIED. Never start a new Hyper-V heavy task without independent live host/remote proof.

## Evidence classification

- Public existing free Hosted selftest #45413438154: durable queue local subprocess/SQLite test PASS on exact Public candidate.
- Cross-repo Hosted #45414019474: Public queue code, exact Private source checkout at 87131354beff322d768ac4c32a3d8fc84546976a, real Linux private-process tests, protocol interop, and ephemeral cleanup PASS. This is a **real Github machine executing local processes**, not real workflow_dispatch or owner VM.
- Previously observed P01/P08 independent lightweight Hosted jobs at run #45404452141 stay reusable; do not rerun them for this source-only scheduler change.
- Actual workflow_dispatch on Shared Free Test V1, durable GitHub Run/Job correlation, remote cancellation, Private native Hosted allocation, Windows/Hyper-V capacity, systemd auto start/stop, GitHub variable NO readback, restart/reset and rollback remain NOT_PROVEN. Safe operator command is not yet issued.

