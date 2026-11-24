# VF Shared Test Protocol v1 · Public-owned candidate

Authority: Public #4471 + Private #42. This is one interface, not another controller. Do not install/activate P02 PR #2.

## Request (input JSON array, 1–128 entries)
Each item has exactly: task_id, repository, commit_sha, tree_sha, test_id, tier, privacy, resource_key, timeout_seconds.
IDs and resource keys are restricted ASCII slugs; repo must be explicit llhzx2018/<slug>; source SHA/Tree are 40 lowercase hex. That validates syntax ONLY, not independently attested source identity.
Tier: light, integration or heavy. Privacy: public_safe, private_source or private_evidence. Timeout: integer 1–3600 seconds.
Reject arbitrary command, token, secrets and unknown fields; duplicate task IDs are blocked per batch. There is no durable global replay authority at this stage.

## Public output
python3 scripts/shared_test_router.py plan --input requests.json
Emits protocol vf.shared-test/v1 with tasks[].request, lane and resource_class.
Routes light/integration public_safe -> PUBLIC_HOSTED; private_source -> PUBLIC_TRANSIENT_PRIVATE_SOURCE; private_evidence -> PRIVATE_SANDBOX; all heavy -> EXISTING_HYPERV.
Public run-public executes ONLY locally trusted catalog commands for public_safe items, with bounded parallelism, clean temporary cwd, discarded stdout/stderr, restricted environment, process-group timeout termination and public-safe receipts.
Private-source checkout is not implemented by this helper; it returns BLOCKED_PRIVATE_CHECKOUT_NOT_ATTESTED. All Private/Hyper-V tasks are deferred without execution.

## Private consumption
python3 scripts/shared_test_private_adapter.py --plan one-task.json --catalog trusted.json --lock-root <private-0700-lock-directory>
Private recomputes lane/class, requires an on-host trusted catalog, isolates process workspace, and uses no-follow 0600 Linux flock locks.
Integration locks are keyed by resource_key; all heavy tasks use one fixed cooperative lock. Bounded contention yields BLOCKED_RESOURCE_BUSY, not an infinite retry.
Default real heavy execution returns BLOCKED_HYPERV_REAL_ADMISSION_NOT_PROVEN; --simulate-heavy is local simulation only, never an actual Runner invocation.
Receipts contain task ID, status, exit code, elapsed milliseconds, command hash and cleanup marker, not raw stdout or secrets.

## Safety and evidence
Exact GitHub Hosted multi-project concurrency, actual private transient checkout, real resource measurements, Owner identity, GitHub Run/Job dispatch, durable queue/fairness/replay, automatic Runner stop+disable and variable NO readback, PowerShell installer and Hyper-V power-cycle recovery remain NOT_RUN.
These features require independent exact-source native and real VM gates. Never infer real machine PASS from local simulations.
Evidence is in branch-local evidence/shared-test/phase-a-20261124.json; no Production, Release, Runner/Workflow activation or Secrets mutated.
