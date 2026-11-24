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