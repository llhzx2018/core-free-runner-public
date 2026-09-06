# P07 Enhanced Bench v0.8 Field Candidate

## Status

- v0.5 real VPS: FAIL / RETIRED
- v0.6 real VPS: FAIL / RETIRED
- v0.7: superseded by v0.8 before field retest
- v0.8 automated exact gate: PASS
- v0.8 real VPS field retest: NOT_RUN
- Stable: NO
- vfops integration: NOT_RUN

## Field evidence from v0.6

Real VPS showed:

- I/O normal.
- Overseas HTTPS 3/3 PASS.
- Mainland HTTPS 6/6 PASS.
- Every Ookla Speedtest row returned BACKEND_FAILURE.
- Whole run finished in about 8 seconds.

This pattern is treated as a global Speedtest backend/execution failure, not as evidence that every geographic route is down.

## v0.7 corrections retained in v0.8

- Default Speedtest.net is a global preflight.
- Global `RATE_LIMITED`, `BACKEND_UNAVAILABLE`, or `BACKEND_FAILURE` stops remaining Ookla node execution.
- `network_reason` recognizes rate-limit and configuration-service failure signatures.
- Retry wrapper and China pool wrapper both execute `speed_node` in the same shell.
- Empty server_id TSV rows are parsed by fixed columns.
- Transient backend retries use a short backoff.

## v0.8 new fallback

If Ookla cannot be prepared or the global preflight fails, P07 automatically attempts a Cloudflare Edge fallback:

- download endpoint: `https://speed.cloudflare.com/__down`
- upload endpoint: `https://speed.cloudflare.com/__up`
- fallback is labeled `FALLBACK` and is not counted as China carrier evidence.
- real fallback payload is bounded: 50 MB download + 10 MB upload in field mode.

## Exact candidate

- Public exact source commit: `c0f359a7dff7e5b7cbcdff5052cef0549316e349`
- Independent Gate run: `34054050747`
- Result: PASS

The independent Gate verified:

1. exact candidate identity;
2. bash syntax and self-test;
3. menu-free one-shot demo;
4. backend fail-fast contract;
5. same-shell wrapper contract;
6. security boundary;
7. real Cloudflare fallback endpoint smoke using 1 MB download and 256 KB upload.

## Field acceptance

F01. If Ookla works, normal global node table proceeds.
F02. If Ookla is globally unavailable/rate-limited, the table must not render every geographic node as failed.
F03. The output must identify the global backend reason once.
F04. Cloudflare Edge fallback should run and display an upload/download baseline when available.
F05. Cloudflare fallback must remain clearly labeled FALLBACK and must not become China carrier/IP-block evidence.
F06. `Mainland -> VPS` stays NOT_RUN until a true mainland-origin probe exists.
F07. TXT/JSON report generation remains intact.
F08. No Stable promotion before real VPS field PASS.
