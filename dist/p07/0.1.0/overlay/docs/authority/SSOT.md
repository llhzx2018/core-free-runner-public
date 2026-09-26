# P07 · VF Server Ops · Engineering SSOT V1.0

状态：CURRENT / V1 REAL PRE-PRODUCTION CLOSURE PASS / OWNER CUTOVER OPEN  
日期：2026-09-06

Canonical Real closure evidence：`docs/evidence/P07_REAL_GATE_CLOSURE_20260906.md`。

## 1. Runtime / Product Boundary

- Primary entry：Bash `bin/vfops`
- TTY default：5 项中文交互菜单
- Non-TTY no-arg：help
- Implementation helper：Python 3 stdlib
- Storage transport：rclone
- Migration transport：OpenSSH + tar private stream
- Remote encryption：rclone `crypt` REQUIRED for PRIVATE remote backup
- CloudPanel integration：read-only capability discovery + official `clpctl`
- V1 Web UI：N/A
- V1 does **not** implement existing Production-site overwrite, automatic DNS cutover, or old-server deletion

## 2. Module Boundary

```text
bin/vfops                 CLI/menu entry
lib/inventory.py          read-only discovery + inventory manifest
lib/package.py            Portable Backup Package + local verification
lib/storage.py            Google Pool / B2 encrypted rclone adapter
lib/restore.py            zero-write restore plan
lib/restore_apply.py      isolated sandbox restore
lib/restore_new.py        guarded brand-new CloudPanel site restore
lib/runtime.py            guarded user Cron / Site User PM2 activation
lib/verify.py             post-restore file/DB/runtime verification
lib/cutover.py            cross-server compare + curl --resolve target probe
lib/migrate.py            target-local single-site migration orchestration
lib/transport.py          source-to-target SSH/tar transport
lib/server_migration.py   low-disk full-server two-phase migration orchestrator
lib/app_config.py         atomic WordPress/dotenv database identity remap
lib/policy.py             settings / automatic backup / retention / Cron render
scripts/secret_scan.py    tracked-source Secret Gate
```

Backup / Restore / Migration MUST use the same Portable Package Contract. Transport may move a package, but must never become a second restore implementation.

## 3. Inventory Contract

Schema：`vf-server-ops.inventory.v1`。

Source order：CloudPanel `db.sq3` read-only capability detection + Nginx vhost + filesystem metadata + bounded Cron/PM2 discovery.

Rules：

- CloudPanel internal DB schema drift → fallback / `UNKNOWN`；
- credential/password columns are not Inventory output；
- `.env` is not an Inventory data source；
- Cron command body / PM2 env do not enter manifest；
- PRIVATE `--output` = exclusive create + 0600 + refuse overwrite；
- Ordinary Inventory 的 SQLite discovery boundary = site root；candidate must pass `SQLite format 3` header validation。Full-server migration 另有私有 supplement scan，覆盖所选 Site User Home 内真实 SQLite；该补充扫描不扩大普通 Inventory 输出面。

A02 real status：**REAL_PASS**。

## 4. Portable Backup Package

Schema：`vf-server-ops.backup-package.v1`。

```text
<backup_id>/                       0700
├── manifest.json                  0600
├── files/site.tar.gz              0600
├── mysql/<db>.sql.gz              0600
├── sqlite/<safe-copy>             0600
├── metadata/inventory-site.json   0600
├── metadata/cloudpanel-private.json 0600
├── metadata/ssl/*                 0600
├── metadata/vhost/*               0600
├── metadata/cron/*                0600
├── metadata/pm2/*                 0600
├── checksums.sha256               0600
└── verification.json              0600
```

Classification：`PRIVATE_SENSITIVE_BACKUP`。

Pipeline：Fresh Inventory → private staging → archive/MySQL/SQLite/runtime metadata → checksums/verification → PASS only → atomic rename。

A04/A08/A09/A10 real status：**REAL_PASS**。

## 5. Secret / Recovery Boundary

Inventory remains `WHITELIST_ONLY`.

A complete disaster-recovery package may contain recovery-critical private material such as `.env`, private app data, CloudPanel recovery metadata, SSL private key, Cron/PM2/vhost recovery metadata. Therefore：

- package always PRIVATE；
- 0700 directories / 0600 files；
- no package under public web root；
- no recovery Secret in ordinary stdout/stderr/report；
- no plaintext remote PRIVATE backup；
- fetched remote package remains private；
- direct migration uses SSH private stream；
- product SSH password CLI/config remains unsupported。

A17 tracked-source + real runtime/log scan：**REAL_PASS**。

## 6. Storage Adapter

Config stores only business metadata. OAuth/B2/crypt credentials stay in protected rclone runtime config / secret injection.

### Google Drive Pool

- verify crypt remote；
- query actual free quota；
- apply reserve；
- one complete backup per selected account；
- no cross-account package splitting。

### Backblaze B2

Role = `disaster_recovery`; same encrypted adapter / immutable / cryptcheck / COMPLETE protocol. Unsupported quota stays `N_A`.

### Remote Completion

```text
fresh local verify
→ verified rclone crypt
→ immutable copy
→ rclone cryptcheck --one-way
→ _VFOPS_COMPLETE.json LAST
```

Only COMPLETE packages are listed/fetched. Fetch uses private staging → fresh package verify → marker verification → atomic local finalize.

A05/A06/A07 Real Storage：**REAL_PASS**。

## 7. Restore Contract

### Zero-write plan

`vfops restore plan` remains zero-write and validates package/tar/path/link/overwrite/secret boundaries.

### Brand-new CloudPanel restore

`vfops restore apply-new-site` requires exact：

```text
RESTORE_NEW_SITE:DOMAIN:BACKUP_ID
```

Hard rules：

- pre-existing site → deny；
- only brand-new controlled CloudPanel target；
- reuse official `clpctl site:add:* / db:add / db:import / site:install:certificate` shapes；
- staged files atomically replace only the new CloudPanel-created empty site tree；
- target ownership reconciled to CloudPanel bootstrap Site User UID/GID without following symlinks；
- Restore Verify required；
- DB rollback deletes only DBs created by current operation；
- DNS untouched。

A12 real status：**REAL_PASS**。

## 8. Runtime Activation

`vfops runtime apply-new-site` requires exact：

```text
ACTIVATE_RUNTIME:DOMAIN:BACKUP_ID
```

Automatic activation scope：

- site-user crontab only；
- no conflicting non-empty target user crontab；
- Cron install/rollback stages content through short private 0700/0600 runtime paths；
- Site User NVM PM2 is auto-resolved only when exactly compatible；
- PM2 `resurrect` and cleanup execute with Site User HOME/PM2_HOME/PATH and Site User-accessible cwd；
- missing/multiple/ambiguous NVM/PM2 prerequisite → fail closed；
- failure rolls back newly installed Cron/new PM2 state；
- `/etc/cron.d/*` remains Manual Gate；
- no Secret values emitted。

A20 real status：**REAL_PASS**，including negative rollback probe。

## 9. Verify / Technical Cutover

Restore Verify covers files, SQLite, MySQL re-export semantic comparison and runtime metadata.

Cross-server comparison covers business assets, not machine identity. Critical UNKNOWN is non-PASS.

Target HTTP/HTTPS probe uses `curl --resolve` so Host header + TLS SNI are tested without DNS mutation.

```text
RESTORE_VERIFIED
+ RUNTIME_ACTIVATED
+ CROSS_SERVER PASS
+ HTTP PASS
+ HTTPS PASS
= TECHNICAL_CUTOVER_READY
```

Formal real SOURCE→TARGET gate reached `TECHNICAL_CUTOVER_READY=PASS`.

OWNER Cutover remains separate and **NOT_EXECUTED**。

## 10. Source-to-target Migration

User-facing command：

```text
vfops migrate transfer-new-site \
  --package <verified-pre_migration-package> \
  --target-host <ssh-host> \
  --target-ip <http-https-probe-ip> \
  [--ssh-user root] [--ssh-port 22] [--identity-file path] \
  --confirm MIGRATE_NEW_SITE:DOMAIN:BACKUP_ID
```

Pipeline：

```text
fresh source package verify
→ exact migration confirmation
→ target endpoint validation
→ SSH CloudPanel preflight
→ PRIVATE runtime stream
→ PRIVATE package stream
→ target same migrate/restore/runtime/verify engine
→ target inventory + cross-server verify
→ HTTP/HTTPS probe
→ TECHNICAL_CUTOVER_READY or NOT_READY
```

SSH hard rules：

- `BatchMode=yes`；
- no product SSH password argument/API；
- `StrictHostKeyChecking=accept-new`；
- changed known host key refused；
- wrong confirmation before target contact；
- hostile host/user input rejected；
- target existing-site guard cannot be bypassed；
- source backup retained；
- remote runtime/package staging private and cleaned；
- no DNS mutation / no old-server delete。

A13/A14 real status：**REAL_PASS**。


### 10.1 Full-server two-phase orchestrator

Target bootstrap contract：

- normal path requires only reachable root SSH; a preinstalled CloudPanel is not mandatory for a genuinely empty supported TARGET；
- if CloudPanel is absent, P07 may bootstrap only after exact `BOOTSTRAP_CLOUDPANEL:<target_ip>` confirmation；
- supported OS/arch is an explicit release-pinned allowlist；current feature line covers Ubuntu 22.04/24.04/26.04 and Debian 12/13 on x86_64/ARM64；bootstrap additionally requires ≥1 Core, a genuine 2 GB-class VM, and ≥10 GB disk；
- bootstrap refuses a TARGET with CloudPanel state, MySQL/MariaDB data, existing htdocs, or a listener on 80/443；
- installer URL and SHA256 are release-pinned from official CloudPanel documentation；checksum failure = no execution；
- current bootstrap DB engine = MySQL 8.4；
- bootstrap also ensures rsync/cron prerequisites；
- source prepare may auto-install only missing rsync after the migration confirmation; other missing critical dependencies fail closed；
- plan performs low-disk SOURCE transient-reserve and TARGET capacity checks before migration writes。
- plan also records public non-standard SOURCE listeners; any such listener keeps `source_decommission_safe=false` and is never silently classified as migrated CloudPanel workload。
- full-server guided SSH bootstrap uses a dedicated P07-managed migration key only when no existing key works; user-owned keys are never marked managed or deleted；after Production PASS the P07-managed key remains `RETAINED_FOR_RECOVERY` only as a Recovery/Cleanup SSH channel while SOURCE is intentionally retained as a Recovery Copy；this does not authorize runtime-only post-production rollback。The key is removable only through the exact post-window cleanup gate `CLEANUP_MANAGED_SSH_KEY:<migration_id>`。


Full-server migration state schema：`vf-server-ops.server-migration.v1`。

Persistent private state：

```text
/var/lib/vf-server-ops/server-migrations/<migration_id>/state.json
directory = 0700
state.json = 0600
```

Canonical states：

```text
PREPARING
PREPARE_FAILED
PREPARED
CUTOVER_RUNNING
CUTOVER_PREP_READY
WAITING_DNS
PRODUCTION_PASS
CUTOVER_FAILED_ROLLED_BACK
CUTOVER_FAILED_ROLLBACK_PARTIAL
ROLLED_BACK
ROLLBACK_PARTIAL
```

Prepare contract：

- selected/all sites use `LOW_DISK_DIRECT_RSYNC` for site files; full-server mode does not retain one complete source backup package per site；
- TARGET CloudPanel sites are created from source inventory runtime identity with generated target-only site passwords；immediately after `site:add`, a fresh TARGET Inventory readback must prove site_user/site_root/document_root/runtime and all SOURCE domains are reproducible before bulk transfer；
- MySQL is staged one database at a time with transient logical dumps, target-owned compatible DB users, and atomic WordPress/dotenv config remap；
- TARGET Runtime remains deferred during prepare；
- source remains live；SOURCE full backup package count for full-server prepare = 0；
- supplement copies `.vf* / .press* / .local/share/vf-*` outside site root；
- whole Site User Home SQLite uses SQLite online backup API + target `quick_check`；the target DB is authoritative only after stale `-wal/-shm/-journal` sidecars are removed before and after the snapshot write；
- when PM2 exists, P07 resolves the exact SOURCE Site User NVM Node version from the dump and transfers only that version tree to the same TARGET Site User path before activation；
- system Cron is privately staged, not activated；a `/etc/cron.d/*` file is automation-eligible only when every real job user parses successfully and belongs to the selected migration Site User set；shared/ambiguous files fail closed；
- SOURCE and TARGET both persist private transaction markers so interruption after target site/DB creation can resume without guessing ownership；
- interrupted prepare persists progress and may resume completed-site-aware；
- TARGET existing same-domain site still fails closed。

Cutover contract：

- exact `CUTOVER_SERVER:<migration_id>` confirmation；
- save/disable SOURCE `/etc/cron.d` + selected user Cron + PM2, then stop SOURCE Nginx；
- final site-root rsync delta；for each migration-owned TARGET database, the private marker must prove ownership before reset/recreate with the same TARGET credentials, then import the frozen SOURCE logical dump；verification first attempts canonical SQL exact fingerprint and, only for legitimate MariaDB→MySQL dump-shape drift, requires equal logical object names + DML content fingerprint；final whole-home SQLite snapshots；
- target database-remapped config files are protected from final source overwrite；
- final MySQL sync again uses one transient logical dump at a time and verifies target re-export semantic fingerprint；
- activate TARGET user Cron/PM2 while deferring system Cron to orchestrator, then install staged system Cron；
- target fresh inventory + cross-server business-asset compare + local HTTPS Host/SNI probe；
- failure before readiness triggers TARGET Runtime deactivation + SOURCE Runtime/Nginx restore attempt；
- success stops at `CUTOVER_PREP_READY`; DNS remains unchanged by P07。

DNS/finalization contract：

- exact `DNS_UPDATED:<migration_id>` confirms OWNER performed provider-side DNS action；
- P07 creates a random proof file only on TARGET document roots and performs public HTTPS requests with cache busting；
- DNS lookup alone is never sufficient evidence；
- partial propagation returns `WAITING_DNS`, not PASS；
- after route proof, public HTTPS must pass certificate verification and 2xx/3xx response checks；
- final Production verification also re-checks that SOURCE Nginx, staged system Cron, selected Site User crontabs, and selected PM2 daemons remain frozen throughout the DNS wait; any reactivation is a hard FAIL。
- `PRODUCTION_PASS` retains SOURCE as rollback and never authorizes SOURCE deletion。

Rollback contract：

- exact `ROLLBACK_SERVER:<migration_id>` and current state must be `CUTOVER_PREP_READY`；
- remove only TARGET runtime/system-Cron activation owned by this migration；
- restore saved SOURCE Cron/PM2/Nginx；
- TARGET sites/data are retained by default；
- if DNS had already changed, DNS rollback remains an explicit OWNER/provider action。
- automatic Runtime rollback is allowed only before DNS handoff while state = `CUTOVER_PREP_READY`；after `DNS_UPDATED` / Production traffic handoff, P07 must DENY runtime-only rollback because TARGET may contain newer file/MySQL/SQLite writes。A future post-production rollback requires a separate TARGET→SOURCE data reconciliation/reverse-sync transaction before SOURCE may become authoritative again。

CloudPanel DB compatibility：

- single-site Portable Backup restore first attempts the SOURCE DB name/user/password；if real `db:add` rejects a legacy non-alphanumeric DB username, only a transaction-owned brand-new TARGET may retry with a strict alphanumeric identity；
- full-server `LOW_DISK_DIRECT_RSYNC` preserves the SOURCE database name but intentionally does not materialize N complete packages containing SOURCE CloudPanel private DB credentials；it directly creates a transaction-owned TARGET-compatible database user；
- both paths atomically remap single-DB WordPress / supported dotenv application config without secret output；
- multi-DB ambiguous automatic remap fails closed。

## 11. Destructive Guard

A16 real negative gate proves：

- wrong confirmation = zero target contact；
- correct confirmation still cannot overwrite existing target；
- full transport cannot bypass existing-site refusal；
- source preserved；
- target business assets remain unchanged on refusal；
- failed migration leaves no private transport staging；
- DNS/Production/old-server destructive writes remain zero。

A16：**REAL_PASS**。

## 12. Settings / Retention / Automation

Policy files may not contain password/token/private-key/OAuth-style fields.

Retention：

- only `automatic` packages may be auto-delete candidates；
- `manual / pre_migration / pre_upgrade` protected；
- legacy/no-kind protected；
- plan read-only；
- apply requires policy authorization + exact `DELETE_AUTOMATIC_BACKUPS` + fresh verify；
- corrupt/unverifiable package is not auto-deleted。

Automation only renders VF policy-run Cron; it is not a generic Cron manager.

A19 real status：**REAL_PASS / 8 of 8**。

## 13. Disaster Recovery

A18 real DR pipeline：

```text
SOURCE real PHP/MySQL/SQLite/Cron/SSL/private package
→ one isolated encrypted B2 DR seed
→ TARGET fresh encrypted fetch
→ fresh package verify
→ brand-new CloudPanel restore
→ guarded Cron runtime activation
→ independent Site User / SQLite / MySQL / Cron / TLS business verification
→ strict remote seed purge
```

A18：**REAL_PASS**。

The DR seed is fixture preparation only. It does not rerun or replace the separate Real Storage authority.

## 14. Final Secret / Credential Cleanup

Final A17 observed：

```text
P07_A17_SOURCE_LOG_SCAN=PASS
P07_A17_TARGET_LOG_SCAN=PASS
P07_A17_DIRECT_TEMP_CREDENTIAL_CLEANUP=PASS
P07_A17_FINAL_SECRET_LOG_SCAN=PASS
```

Test-only copied rclone config, A18 remote config, DB recovery input, temporary direct SSH key/authorized-key entries and Windows test-only VPS password file were removed. User original local rclone config was preserved.

## 15. Exact Real Closure Identity

```text
Product real-fix candidate  c189a0620e8ed1471767b4f1bb29799ce9155053
Baseline                    9d3b5d1e022c3434244a52a6686ebc6fe6f1870f
Formal execution            1788683001-1 · 9/9 PASS · rc=0
A20 execution               1788684001-1 · 8/8 PASS · rc=0
A18 execution               1788691001-1 · 9/9 PASS
Runner one-time head         572b5213d71c920c10b1619584cadc44f5db28cc
Runner PR                    #19 CLOSED / UNMERGED
```

The exact `9d3... → c189...` product delta is only `lib/runtime.py` plus its regression test.

Private GitHub-hosted Actions for the one-time Runner PR remained `steps=[] / runner_id=0`; classification stays `BLOCKED_ENV_ACTIONS_START` and is not used as Real evidence.

## 16. Current Safety State

```text
V1_REAL_PREPRODUCTION_CLOSURE = PASS
TECHNICAL_CUTOVER_READY       = PASS
OWNER_CUTOVER                 = NOT_EXECUTED
FORMAL_RELEASE                = NOT_RELEASED
PRODUCTION                    = NOT_PRODUCTION
```

No main promotion / Tag / Release / Production restore / DNS cutover / old-server deletion is authorized by Real Gate closure alone.

## 17. Next Engineering Phase

Current engineering line returns to **L2 Product Optimization**：UX, diagnostics, maintainability, test quality and operational ergonomics may continue on `develop` without weakening any security contract.

Release / Production remain separately Owner-gated.
