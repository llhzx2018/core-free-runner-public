# core-free-runner-public · Current Acceptance Matrix

> Rebaseline：2026-08-19

| Gate | Current Result |
|---|---|
| Infrastructure Role | PASS / Public-safe Runner + Evidence |
| Current Infrastructure Contract | PASS |
| Current Engineering SSOT | PASS |
| Synthetic Fixture in Public Space | ALLOWED |
| Public-safe Evidence | ALLOWED / REQUIRED |
| Private Source Persisted to Public Git | FORBIDDEN |
| Private Source Uploaded as Public Artifact | FORBIDDEN |
| PRIVATE_DATA / Real DB / Production Backup | FORBIDDEN |
| Secret Value in Git / Log / Artifact / Evidence | FORBIDDEN |
| Transient Private Checkout on Hosted Runner | ALLOWED WITH SECRET + CLEANUP |
| One-off Workflow / PR | ALLOWED / CLOSE WITHOUT MERGE DEFAULT |
| Reusable Harness Main Adoption | REQUIRE EXPLICIT REUSE DECISION |
| Repeated Version Lane Identity | SINGLE-SOURCE SPEC + PRE-TRIGGER `audit-rendered` / NO RAW COPY-REPLACE |
| Gate Ownership Isolation | PASS / NO GLOBAL TEST-DISCOVERY COUPLING |
| Release-capable Trigger Boundary | PUSH REQUIRES DEDICATED BRANCH / HISTORICAL EXACT RELEASE PREFERS MANUAL |
| Machine PASS Self-sign by AI | FORBIDDEN |
| Runner Failure = Product Failure | FORBIDDEN CLASSIFICATION |
| Private Hosted CI `runner_name=null + steps=[]` with healthy Public Runner | `BLOCKED_INFRA_PRIVATE_HOSTED` / NO PRODUCT FAIL / NO REPEAT EMPTY RERUN |
| Specific Billing / Budget / Payment Cause from zero-step fingerprint alone | NOT_PROVEN |
| Third Long-term Test Space | NOT ALLOWED BY DEFAULT |
| develop Sandbox Divergence | RECORDED / DO NOT MECHANICALLY MERGE |
| Runtime/Product Version Change by Rebaseline | NO |

## Current Gate

```text
PUBLIC RUNNER AUTHORITY: CURRENT
PUBLIC-SAFE BOUNDARY: LOCKED
TEMP WORKFLOW CLEANUP CONTRACT: LOCKED
PRODUCT BLOCK: NONE
```
