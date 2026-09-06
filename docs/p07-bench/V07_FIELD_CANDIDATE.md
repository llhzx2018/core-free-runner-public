# P07 Enhanced Bench v0.7 Field Candidate

## Status

- v0.5 real VPS field result: FAIL / RETIRED
- v0.6 real VPS field result: FAIL / RETIRED
- v0.7 automated exact candidate gate: PASS
- v0.7 real VPS field retest: NOT_RUN
- Stable: NO
- vfops integration: NOT_RUN

## v0.6 field failure

Observed on real VPS:

- I/O completed normally.
- Overseas HTTPS = 3/3 PASS.
- Mainland HTTPS = 6/6 PASS.
- All Speedtest rows returned `BACKEND_FAILURE`.
- Total run time was about 8 seconds, which is incompatible with twelve real throughput tests completing normally.

Conclusion: the field failure is in the Speedtest execution/backend path, not evidence that the VPS global network is down.

## v0.7 changes

1. Added a global Speedtest preflight using the default Speedtest.net test.
2. If the global backend returns `RATE_LIMITED`, `BACKEND_UNAVAILABLE`, or `BACKEND_FAILURE`, remaining throughput nodes are skipped instead of printing a full table of misleading node failures.
3. Added explicit backend classification for HTTP 429/rate limit and configuration-service failures.
4. Retry backoff added for transient backend errors.
5. Removed the remaining `speed_node` execution through command substitution in `speed_node_pool`; all wrappers now execute `speed_node` in the same shell.
6. Fixed-column TSV parsing remains required for empty `server_id` rows.
7. Lifecycle self-test now covers both retry wrapper and pool wrapper.

## Exact candidate

- Public exact commit: `0b61919574f944e538af89ffd9c1522ae2c28c9e`
- Independent candidate gate run: `34053897870`
- Gate result: PASS

## Required field acceptance

F01. One-shot execution remains menu-free.
F02. If Speedtest.net preflight passes, normal overseas node tests must proceed.
F03. If Speedtest backend is rate-limited/unavailable, only one global backend failure should be shown and remaining node tests should be skipped.
F04. The script must not render every geographic node as failed when the global Speedtest backend itself is unavailable.
F05. China pool fallback must not delete temporary files or the temporary Ookla binary.
F06. `NODE_UNAVAILABLE` remains neutral evidence for IP blocking.
F07. `Mainland -> VPS` remains `NOT_RUN` until a real mainland-origin probe exists.
F08. TXT and JSON reports must still be generated.

Do not promote v0.7 to Stable until real VPS field retest passes.
