# P07 · VF Server Ops · Acceptance Matrix V1.5

状态：CURRENT  
Last reconciled: 2026-09-11 (America/Los_Angeles)  
原则：`NOT_RUN / UNKNOWN / DEFERRED / BLOCKED_ENV / SYNTHETIC_PASS / MACHINE_PASS != REAL_PASS`

Current canonical Machine evidence:

- `docs/evidence/P07_GUIDED_INIT16_R2_ONBOARDING_MACHINE_CLOSURE_20260911.md`
- `docs/evidence/P07_GUIDED_INIT12_REAL_R1_DBADD_CLOSURE_20260911.md` — retained Restore-As DB remediation evidence
- `docs/evidence/P07_GUIDED_INIT10_CLOUDPANEL_FOUNDATION_MACHINE_CLOSURE_20260911.md` — retained CloudPanel foundation evidence
- `docs/evidence/P07_REAL_GATE_CLOSURE_20260906.md` — historical Real engineering closure for its exact older identities

## Current guided-init16 acceptance layer

This section governs the current Slot 3 product line. Historical Real engineering evidence remains valid only for the exact identities recorded in its evidence and does not automatically promote guided-init16 to current Owner/User `REAL_PASS`.

| ID | Capability | Acceptance | Evidence | Current |
|---|---|---|---|---|
| B01 | guided-init16 Source Identity | Current preparation-first Google+B2 onboarding; correct Device OAuth secret contract; Recovery auto-generation; existing safety/import paths retained | source PR #19; runtime merge `78691699d3b5186ff902550ec65facf0976c89a1`; exact blobs in init16 evidence | **PASS** |
| B02 | Public Distribution Identity | Public main distributes source-exact init16 through existing stable `p07.sh`; no second ordinary-user entry | public PR #846; main `fd02a3db860a0773a3587bf5d78de0daf4875861` | **PASS** |
| B03 | Preparation-first Onboarding | UI tells user all Google/B2 prerequisites before configuration; embedded Google/B2 tutorial is available before secret input | `test_storage_onboarding_ux.py`; dedicated R2 gate PR/main | **MACHINE_PASS** |
| B04 | Google Device OAuth Contract | device-code request uses `client_id`; token polling uses `client_id + client_secret`; Secret is hidden input via stdin and not argv/log output | `google_device_oauth.py`; OAuth tests; secret-boundary gate | **MACHINE_PASS** |
| B05 | Recovery Key UX | P07 auto-generates high-entropy Recovery Key; user does not pre-create it; plaintext is revealed once only after Google+B2+crypt health PASS and is not persisted | onboarding UX gate + static contract | **MACHINE_PASS** |
| B06 | Backblaze B2 Guided Setup | tutorial covers Bucket + Application Key ID + Application Key; read/write and Bucket-list requirement; runtime discovers/selects Bucket and verifies access | onboarding runtime + tests | **MACHINE_PASS** |
| B07 | Dual Crypt Remote Protection | Google/B2 crypt remotes derive from the same auto-generated Recovery Key; P07 does not expose naked ordinary-user rclone config | storage setup regression + safety contract | **MACHINE_PASS** |
| B08 | Current-site-set First Verification Guard | current CloudPanel site inventory must be refreshed; previous PASS cannot cover newly added sites; scheduler remains blocked until current first verify | `test_auto_backup.py` + `test_auto_backup_run_now_ux.py` in init16 gate | **MACHINE_PASS** |
| B09 | Install / Upgrade / Exact Rollback | fixed init15 baseline; exact init16 blob validation; injected init16 failure restores pre-run init15 tree; normal upgrade reaches init16 | PR run `34670251605`; main run `34670304430` | **MACHINE_PASS** |
| B10 | Permanent Toolbox Routing | permanent Toolbox expects init16 internally while public Slot3 remains `V0.1.0 / 测试中`; System Care RC12 unchanged | init16 route gate; Toolbox blob `69be6c8623addd6251e8f7fac596d1e93bc34789`; System Care main PASS | **MACHINE_PASS** |
| B11 | CloudPanel Platform Foundation | details/health, five site-create types, DB add/export/import, SSL, permissions/Varnish, Panel security/users, safe admin functions retained | guided-init10 closure + unchanged runtime blobs | **MACHINE_PASS** |
| B12 | Restore-As Transaction | verified backup → auto TARGET create → DB create/import/verify → app remap → local Host/SNI verification; existing TARGET refused | retained Restore-As Machine evidence; init12 DB remediation | **MACHINE_PASS** |
| B13 | Secret Boundary | no Google account password, no Google Client Secret argv/echo, no plaintext Recovery persistence, no secret output in ordinary logs | init16 OAuth/onboarding tests + static gate | **MACHINE_PASS** |
| B14 | Stable Public Installer | stable `p07.sh` pins init16 installer blob `4a7889ea606fa2353f194abbb2c6b27345f35050` over fixed init15 main | dedicated init16 route + transaction gate | **MACHINE_PASS** |
| B15 | System Care Isolation | Menu4 remains RC12 and available while Slot3 evolves | post-merge run `34670304410` | **MACHINE_PASS / UNCHANGED** |
> B16–B31 Machine Evidence：Public Runner exact-private-source fallback，`vf-server-ops@3b717a9de58d0d46af6d12422ad35646b9a4129d`，Run `36087195784` / Machine Gate #13 = PASS；Bash / Python compile / Identity / Smoke / native-CI mirrored Units / tracked-source Secret Scan 全 PASS。`EXACT_SOURCE_SYNTHETIC` 仅表示独立机器执行的 synthetic/fixture 证明，不表示真实 Production Migration、DNS Cutover 或 Production Data Proof。
| B16 | Full-server Migration Orchestrator | automatic all/selected-site plan → low-disk direct prepare → cutover → finalize state machine; no N-site source package accumulation | feature source + `test_server_migration.py` | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B17 | Two-phase Runtime Isolation | TARGET Cron/PM2 deferred during live prepare; `/etc/cron.d` is automated only when every real job belongs to selected Site Users; SOURCE remains live until explicit cutover; from cutover through DNS wait/final proof, SOURCE Nginx + system Cron + user Cron + PM2 must remain frozen or Production FAILs | staged Runtime + exclusive system-Cron ownership + final source-runtime tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B18 | Whole-home Data Completeness | direct site-root rsync plus `.vf*` / `.press*` / `.local/share/vf-*`; whole Site User Home SQLite online backup + target quick_check; target WAL/SHM/journal sidecars removed before/after authoritative snapshot | `server_migration.py` discovery/snapshot tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B19 | Final Delta / Database Consistency | source freeze → final rsync delta → prove migration-owned TARGET DB marker → reset/recreate DB with same private TARGET identity → import frozen SOURCE dump; exact SQL fingerprint first, MariaDB→MySQL cross-engine logical data/object fingerprint fallback; final authoritative SQLite snapshot | server migration cutover engine + verify/final-DB tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B20 | DB Identity Compatibility | single-site restore preserves source DB identity then falls back on rejection; full-server direct mode creates target-compatible DB user and atomically remaps WordPress/dotenv config | `app_config.py`; restore-new + server-migration regression | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B21 | DNS Manual Gate / Public Route Proof | P07 never edits DNS; after Owner DNS action, random TARGET-only proof must reach every domain before Production verification | server migration finalize engine + tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B22 | Automatic Cutover Rollback | SOURCE freeze persists Intent before destructive actions and Completed only after success; resume must finish incomplete system-Cron/user-Cron/PM2 intents; pre-ready failure deactivates migration-owned TARGET runtime and restores saved SOURCE Cron/PM2/Nginx; no source/target delete | crash-window freeze-resume + state-machine rollback tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B23 | Resumable Beginner UX | `整机迁移（推荐）`; prepare checkpoint state; resume; one DNS Gate; old server retained | `vfops-migrate-ui`; modular menu gate | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B24 | Guarded Empty-target Bootstrap | reachable root SSH + supported empty OS/arch + >=1 Core / 2 GB-class RAM / 10 GB disk can auto-install checksum-verified official CloudPanel + MySQL 8.4; non-empty target refused | server migration bootstrap + UX + bootstrap tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B25 | Capacity / Runtime Prerequisite Automation | low-disk SOURCE reserve + TARGET free-space preflight; missing SOURCE rsync can auto-install after confirmation; PM2 exact Site User NVM version is migrated automatically | server migration preflight + PM2 tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B26 | Source External-service Decommission Guard | public non-standard listeners are surfaced and keep `source_decommission_safe=false`; website migration never pretends proxy/VPN/other services were moved | listener parser + migration UX | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B27 | Target Web Contract Readback | immediately after `site:add`, TARGET inventory must prove site_user/site_root/document_root/runtime and all SOURCE domains are reproducible; mismatch cleans the new transaction-owned site before bulk transfer | target-site readback helper + tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B28 | Target Collision Guard | Plan rejects selected domain, Site User or database-name collisions on TARGET before migration writes | target preflight filesystem + CloudPanel DB checks | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B29 | Managed Migration SSH Key Lifecycle | full-server first-auth uses dedicated P07-managed key; user-owned keys are never deleted; Production PASS retains the managed key only as a Recovery/Cleanup channel; exact post-window cleanup removes only the proven P07 key and closes that managed TARGET SSH channel | guided migration UX + server migration key lifecycle tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B30 | Post-production Rollback Safety Boundary | automatic Runtime rollback is allowed only before DNS handoff at `CUTOVER_PREP_READY`; after DNS handoff / Production PASS, runtime-only rollback is DENIED because TARGET may contain newer writes; a future rollback requires TARGET→SOURCE data reconciliation/reverse sync; SOURCE remains a Recovery Copy | rollback guard + guided UX negative/positive tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B31 | Production Proof / Housekeeping Separation | once public route + HTTPS/TLS + SOURCE-runtime freeze verification PASS, `PRODUCTION_PASS` is persisted before TARGET private-staging housekeeping; cleanup failure becomes `RETRY_REQUIRED` without erasing Production truth; P07-managed Recovery SSH key cannot be removed until private staging cleanup PASSes | finalize housekeeping + recovery-key negative/positive tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| R1-A1 | Real Restore-As attempt #1 | Owner VPS guided-init10 attempt preserved | `MYSQL_CREATE_IMPORT_VERIFY / CloudPanelError`; SOURCE retained; DNS unchanged | **REAL_FAIL / RETRY_REQUIRED** |
| R1-A2 | Real Restore-As attempt #2 | Owner VPS guided-init11 attempt preserved | `P07_CLOUDPANEL_OPERATION=db_add`; `P07_CLOUDPANEL_EXIT=1`; SOURCE retained; DNS unchanged | **REAL_FAIL / RETRY_REQUIRED** |
| R1 | Current Real Restore-As New Domain | genuine current permanent-Toolbox run on brand-new TARGET through create/import/remap/Host/SNI/private evidence | Current Real evidence still required; previous failures are not PASS | **RETRY_REQUIRED / NOT_PASS** |
| R2 | Current Full Local + Google + B2 First Verify | current CloudPanel site inventory; required current sites successfully protected and verified on Local+Google+B2 using guided-init16 onboarding | Owner VPS Real evidence required | **NOT_RUN** |
| R3 | Current Guarded Scheduler Real Gate | scheduler installed only after current R2 first-verification PASS; collision/readback verified | Owner VPS Real evidence required | **NOT_RUN** |
| R4 | Current Guided Cross-VPS Restore/Migration | brand-new TARGET, source retained, cross-server verification PASS, DNS unchanged | genuine cross-VPS Real evidence required | **NOT_RUN** |

### Current guided-init16 safety invariants

```text
DNS automatic mutation                        DENY
SOURCE / old-server automatic deletion        DENY
TARGET existing same-domain overwrite         DENY
SOURCE-domain certificate reuse on Restore-As DENY
site / DB / panel-user delete in ordinary UX  DENY / NOT EXPOSED
manual empty CloudPanel TARGET prerequisite   DENY
normal-user naked rclone config UX             DENY
Google account password request               DENY
Google Client Secret argv exposure            DENY
Google Client Secret terminal echo            DENY
plaintext Recovery Key persistence             DENY
secret output in logs                          DENY
scheduler before required first verification  DENY
old PASS covering newly added sites            DENY
runtime self-claim of REAL_PASS                DENY
```

### Current evidence classification

```text
GUIDED_INIT16_SOURCE                         CURRENT / MERGED_TO_CANDIDATE
PUBLIC_GUIDED_INIT16_DISTRIBUTION            MAIN / TESTING
GUIDED_INIT16_R2_ONBOARDING_MACHINE_GATE     PASS
GUIDED_INIT16_TRANSACTION_ROLLBACK_GATE      PASS
GUIDED_INIT16_STABLE_TOOLBOX_ROUTING_GATE    PASS
SYSTEM_CARE_RC12                             PASS / UNCHANGED
CLOUDPANEL_FOUNDATION_COMPLETE               MACHINE_PASS
RESTORE_AS_IMPLEMENTATION                    MACHINE_PASS
R1_ATTEMPT_1_GUIDED_INIT10                   REAL_FAIL / RETRY_REQUIRED
R1_ATTEMPT_2_GUIDED_INIT11                   REAL_FAIL / DB_ADD_EXIT_1 / RETRY_REQUIRED
CURRENT_RESTORE_AS_NEW_DOMAIN_REAL_VPS       RETRY_REQUIRED / NOT_PASS
CURRENT_GOOGLE_B2_ALL_SITE_FIRST_VERIFY      NOT_RUN
CURRENT_GUARDED_SCHEDULER_REAL_GATE          NOT_RUN
CURRENT_CROSS_VPS_GUIDED_MIGRATION_REAL      NOT_RUN
CURRENT_RC3_REAL_OWNER_USER_PASS             NOT_PROVEN
MENU3_PUBLIC_STATUS                          TESTING
FORMAL_TAG_RELEASE                           NOT_AUTHORIZED
PRODUCTION_CUTOVER                           NOT_AUTHORIZED
```

Older P07 workflows can still contain previous current-BUILD assertions (for example guided-init14) and may fail before behavioral steps execute after the current identity advances. Such runs are identity-migration debt, not current Product/Real evidence. Repository-global Public Runner Trigger/Workflow Archive findings remain separate pre-existing S01 governance debt.

---

## Historical A01-A20 engineering acceptance

The following historical matrix remains valid only for the exact identities recorded in the historical closure evidence.

| ID | Capability | Current |
|---|---|---|
| A01 | Repository Bootstrap / CLI Entry | **PASS** |
| A02 | Inventory | **REAL_PASS** |
| A03 | Manifest | **PASS** |
| A04 | Local Backup | **REAL_PASS** |
| A05 | Google Drive Pool | **REAL_PASS** |
| A06 | Backblaze B2 | **REAL_PASS** |
| A07 | Encryption | **REAL_PASS** |
| A08 | MySQL Consistency | **REAL_PASS** |
| A09 | SQLite Consistency | **REAL_PASS** |
| A10 | Backup Verify | **REAL_PASS** |
| A11 | Restore Dry-run | **PASS** |
| A12 | Site Restore | **REAL_PASS** |
| A13 | Migration | **REAL_PASS** |
| A14 | Cross-server Verify | **REAL_PASS** |
| A15 | Cutover Safety | **REAL_TECHNICAL_READY / OWNER_CUTOVER_NOT_RUN** |
| A16 | Destructive Guard | **REAL_PASS** |
| A17 | Secret Boundary | **REAL_PASS** |
| A18 | Disaster Recovery | **REAL_PASS** |
| A19 | Settings / Retention / Automation Policy | **REAL_PASS** |
| A20 | Runtime Activation | **REAL_PASS** |

Historical Real closure identity and detailed evidence remain canonical in `docs/evidence/P07_REAL_GATE_CLOSURE_20260906.md`; the compact table above does not change or reclassify those historical results.

## Completion boundary

Current guided-init16 Machine/distribution closure is complete. This does **not** equal current guided-init16 Owner/User qualification, Formal Tag/Release, Production restore/migration, DNS cutover, old-server deletion, or existing Production overwrite.

Current progression remains `R1 retry → R2 → R3 → R4`; until those required Real gates are complete, Slot 3 remains `测试中`.

### Current Machine Gate Blocker

- Current full-server migration rows B16–B30 remain **IMPLEMENTED / MACHINE_NOT_RUN**.
- GitHub Actions classification: **BLOCKED_ENV_ACTIONS_START** — job objects are created but return `steps=null` / `logs_url=null`, so no Bash/Python/unit-test step executes.
- This condition predates PR #24: develop had successful bootstrap-ci through 2026-09-06; develop Runs #497/#498 on 2026-09-10 already exhibit the same pre-step failure.
- Therefore the blocker is not promoted to Machine FAIL and must not be promoted to Machine PASS. Merge/Release/Production remain gated.
