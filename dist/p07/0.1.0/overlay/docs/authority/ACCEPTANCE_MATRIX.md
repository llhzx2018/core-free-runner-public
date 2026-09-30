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
| B27 | New-server Web Contract Readback | immediately after local `site:add`, current NEW server inventory must prove site_user/site_root/document_root/runtime and all OLD-server domains are reproducible; mismatch cleans only the new transaction-owned site before bulk pull | local target-site readback helper + tests | **IMPLEMENTED / GATE_PENDING** |
| B28 | New-server Collision Guard | Plan rejects selected domain, Site User, `/home/<user>`, or database-name collisions on the current NEW server before business-data pull | local target preflight + tests | **IMPLEMENTED / GATE_PENDING** |
| B29 | Managed Old-server SSH Key Boundary | first authorization may create a dedicated P07-managed key on NEW and authorize it on OLD; user-owned keys are never marked managed or deleted; Production PASS retains the P07 key/helper only as a Recovery channel unless a later explicit cleanup contract is executed | guided migration UX + static/security tests | **IMPLEMENTED / GATE_PENDING** |
| B30 | Post-DNS Rollback Safety Boundary | Runtime-only rollback is allowed only before Owner DNS handoff; once `DNS_UPDATED` is declared (`WAITING_DNS` / `PRODUCTION_VERIFY_FAILED`) or after `PRODUCTION_PASS`, rollback to OLD is DENIED because NEW may contain newer writes; future rollback requires NEW→OLD data reconciliation | pull rollback guard + negative tests | **IMPLEMENTED / GATE_PENDING** |
| B31 | Production Proof / Recovery Preservation | public proof file must exist only on NEW; HTTPS/TLS + public route + OLD-runtime-frozen verification must PASS before `PRODUCTION_PASS`; OLD and its Recovery Point/helper remain preserved, and P07 never deletes OLD | pull finalize + recovery-retention tests | **IMPLEMENTED / GATE_PENDING** |
| B32 | Target-owned Pull Direction | ordinary migration must be launched on NEW, ask for OLD server IP, and transfer business data OLD→NEW by NEW-initiated pull; ordinary UX must not ask for target IP | `server_migration_pull.py` + migration UI direction tests | **IMPLEMENTED / GATE_PENDING** |
| B33 | Target-owned Migration State | Migration ID, primary private state, resume state and target transaction markers live on NEW; OLD only holds subordinate recovery/staging state | state ownership tests | **IMPLEMENTED / GATE_PENDING** |
| B34 | Pull Asset Completeness | site files, external VF/Press data, MySQL logical dumps, SQLite online snapshots, Cron/PM2 metadata and required NVM runtime are read from OLD by NEW; final delta repeats after OLD freeze | pull orchestration + unit/static tests | **IMPLEMENTED / GATE_PENDING** |
| B35 | Old-server Recovery Before Freeze | final synchronization must create OLD-side Recovery Point before stopping Nginx/Cron/PM2; pre-DNS failure stops NEW runtime and restores OLD runtime; OLD is never deleted | source recovery root + freeze/restore tests | **IMPLEMENTED / GATE_PENDING** |
| B36 | Role-intuitive Chinese Migration UX | ordinary screen says “当前服务器：新服务器 / 接收端”, “旧服务器 IP”, “整机迁入 / 单站迁入 / 继续未完成迁移”; SOURCE/TARGET are not required user concepts | migration UI gate | **IMPLEMENTED / GATE_PENDING** |
| B37 | Migration-only Lazy Dependencies | OpenSSH client + rsync are checked only after entering migration; OLD rsync may be installed only after migration approval; Toolbox/other Slots do not preinstall them | migration UI + engine tests | **IMPLEMENTED / GATE_PENDING** |
| B38 | Legacy Push Not Ordinary Route | old push engine may remain as internal compatibility primitive, but `vfops server-migrate` and ordinary migration UI route only to the target-owned pull engine | CLI routing gate | **IMPLEMENTED / GATE_PENDING** |
| B32 | Target-owned Pull Migration | ordinary migration runs on NEW/current server; asks only for old-server IP; current server owns Migration ID/state; SSH/rsync/MySQL/SQLite data direction is OLD(remote) → NEW(local); DNS remains manual; old server retained; existing target overwrite denied; legacy push engine not exposed as ordinary UX | `server_migration_pull.py` + `test_server_migration_pull.py` + Menu3 contract + exact-source public Runner #36563032316 against candidate `a30d32318dea53e5838f9216f532096d24021f5e` | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B33 | Main Menu Visible Feedback | Slot 3 menu routes 1–7 are wired; empty-site / empty-backup / module-failure states remain visibly readable before TTY redraw; child non-zero exit does not kill parent menu | `test_main_menu_routes.py` + full Slot3 regressions + exact-source public Runner `36580337400` against candidate `7b5a7e2e1f596c6ee5f2ba57005727a271820e45` | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B34 | Terminal UX System V2 | interactive Slot 3 surfaces use one-screen-one-task page isolation; main menu is cleared before child entry; overview/backup/restore/migration/auto-backup/site/admin use page primitives; empty/error/result states are isolated; machine/non-TTY output remains stable | `terminal_ui.sh` + full Slot3 regressions + exact-source public Runner `36651107701` against candidate `c6feba4bcd6002f8baf8e332d7388e78ca71cc16` | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B35 | Ops Diagnostics Center | read-only diagnostics cover P07/CloudPanel/Nginx/MySQL/PHP-FPM/disk/memory/swap/latest verified backup; main menu exposes a lightweight summary | `ops_diagnostics.py` + `vfops-diagnostics-ui` + `test_ops_console_r9.py` | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC · RUN 36654984844** |
| B36 | Local Operation History | P07 records action/result/non-sensitive summary to 0600 JSONL and exposes recent history UI | `ops_history.py` + `vfops-history-ui` + `test_ops_console_r9.py` | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC · RUN 36654984844** |
| B37 | Unified Safety Model | read/write/migration/danger tiers and exact-token helper exist; migration cutover, remote-backup disable, DB import and CloudPanel security writes adopt it | `terminal_ui.sh` + focused regressions | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC · RUN 36654984844** |
| B38 | P07 Self Check / Repair | self-check validates runtime identity/files; repair reinstalls current official runtime only after exact REPAIR token | `vfops-selfcheck-ui` + tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC · RUN 36654984844** |
| B39 | New VPS Initialization | guided preflight + guarded low-risk baseline + guarded CloudPanel bootstrap + explicit completion checklist; no DNS or destructive server action | `vfops-init-ui` + tests | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC · RUN 36654984844** |
| B40 | Beginner Chinese Menu | ordinary menus use Chinese task language; technical terms move to explanatory parentheses/details; Toolbox home removes per-row version/status columns; Slot3 site/backup/migration/init/admin menus follow same contract | final exact-source Runner `36677009690` against candidate `d2b19735be3985388506c16bcf0a3480d60faa00` + release10 Distribution Gate `36677155521` + Toolbox Smoke `36677155588` + System Care Smoke `36677155502` | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
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

- Current full-server migration rows B16–B31 retain their previously recorded exact-source synthetic evidence; B32 Target-owned Pull Migration passed exact-source public Runner `36563032316` against candidate `a30d32318dea53e5838f9216f532096d24021f5e`. Production migration remains NOT_RUN.
- GitHub Actions classification: **BLOCKED_ENV_ACTIONS_START** — job objects are created but return `steps=null` / `logs_url=null`, so no Bash/Python/unit-test step executes.
- This condition predates PR #24: develop had successful bootstrap-ci through 2026-09-06; develop Runs #497/#498 on 2026-09-10 already exhibit the same pre-step failure.
- Therefore the blocker is not promoted to Machine FAIL and must not be promoted to Machine PASS. Merge/Release/Production remain gated.


## Terminal UI Color Contract

| Gate | Requirement | PASS condition |
|---|---|---|
| Terminal UI hierarchy | Interactive P07 pages must not degrade into full-screen plain white text | Titles, sections, actions and statuses follow the RPD canonical semantic color map |
| Semantic status color | PASS/READY/KEEP/normal vs attention/review vs fail/block/risk must be visually distinct | Green / Yellow / Red semantics match RPD |
| High-risk action color | Apply/Rollback/Uninstall/destructive actions must not look like ordinary safe actions | High-risk entry/action uses Red semantics plus existing explicit confirmation gate |
| NO_COLOR compatibility | Color must remain optional | `NO_COLOR` output is plain text and semantically complete |
| Non-TTY compatibility | Machine workflows must not depend on ANSI | Non-TTY output remains parseable/plain unless a documented PTY wrapper is intentionally used |
| Machine-output integrity | JSON / machine-readable formats must never receive ANSI escapes | Parser/regression Gate PASS |
| Shared implementation | New pages must reuse the P07 color helpers / canonical map | No ad-hoc conflicting color vocabulary |
| Product-wide Chinese-first terminal copy | Toolbox + Slot 1/2/3/4 + ordinary sub-pages must not require understanding internal English engineering tokens | 普通界面统一中文优先；TARGET/SOURCE/READY/PASS/Runtime/Gate 等仅保留为内部机器合同；CloudPanel/DNS/SSH/IP/MySQL/SQLite/Cron/PM2/HTTPS 等通用技术名可保留并配中文说明 |
| Lazy loading / current-runtime install | Toolbox and Slot entry must not replay historical installer chains or preinstall unrelated feature dependencies | Toolbox only loads selected Slot; current Slot runs locally; upgrade installs current runtime directly; rclone/OpenSSH are installed only when their feature is entered; Production install does not rerun full unit suite |

| B41 | Menu 3 / 4 IA Separation | Slot3 contains only website/data/backup/migration/site/panel tasks; diagnostics/history/selfcheck/init move to Slot4; backup/restore/auto-backup grouped under one submenu | release11 exact-source Gate `36684513855` + Distribution Gate `36686124730` + Toolbox Smoke `36686124599` + System Care Smoke `36686124872` | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B42 | Immutable Backup Metadata | backup metadata symlinks are dereferenced into private snapshots; package writer/verify rejects external symlinks; restore list requires fresh package verification | backup symlink regression + release11 exact-source Gate `36684513855` | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B43 | Beginner Selfcheck / Restore Failure UX | selfcheck validates only installed runtime files, uses Chinese repair confirmation, and restore failure hides raw engineering output behind actionable Chinese guidance | release11 exact-source Gate `36684513855` + Beginner Menu Gate PASS | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC** |
| B44 | Backup Freshness / Restore Visibility | MySQL export must be quiescent and fully gzip-readable before checksum; committed backup is fresh-verified again before success; restore list must expose blocked backup reason instead of silently treating it as absent; current-runtime install must include the current inventory renderer | release12 focused regression + exact-source Gate `36699115238` PASS | **IMPLEMENTED / MACHINE_PASS · EXACT_SOURCE_SYNTHETIC / DISTRIBUTION_PENDING** |
