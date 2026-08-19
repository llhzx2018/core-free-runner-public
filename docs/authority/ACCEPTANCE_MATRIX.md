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
| Machine PASS Self-sign by AI | FORBIDDEN |
| Runner Failure = Product Failure | FORBIDDEN CLASSIFICATION |
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
