# P07 · VF Server Ops · 工程 SSOT

> 维护运行、状态、数据与恢复合同。历史测试和实机证据由 [项目 Current](CURRENT.md) 路由。

## 1. Runtime / Product Boundary

- Primary entry：Bash `bin/vfops`
- TTY default：5 项中文交互菜单
- Non-TTY no-arg：help
- Implementation helper：Python 3 stdlib
- Storage transport：rclone
- 普通服务器迁移使用 OpenSSH 与 rsync 由目标机拉取；备份包传输兼容路径可用私有 SSH/tar 流
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
lib/server_migration_pull.py  普通单站/整机目标机主动拉取、状态与续迁
lib/server_migration.py       旧编排兼容与共用安全原语
lib/sql_diff_evidence.py      SQL 差异诊断，独立于写入准入
lib/app_config.py         atomic WordPress/dotenv database identity remap
lib/policy.py             settings / automatic backup / retention / Cron render
scripts/secret_scan.py    tracked-source Secret Gate
```

备份与包恢复遵循同一 Portable Package 合同。目标机 Pull 的文件层使用直接 rsync，并复用数据库、SQLite、运行时与独立验证原语。

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

技术就绪记录本机验证范围。DNS 由 Owner 独立执行，公网验证使用目标专有证明和实际 HTTPS 路由。

## 10. 服务器迁移与备份包兼容

以下为旧的备份包定向传输 CLI。普通服务器迁移从目标机发起，见本节 §10.2。

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


### 10.1 旧编排兼容与共用安全原语

以下初始化参数描述历史兼容编排，普通操作使用独立的「新服务器初始化」。发布允许的 OS、引擎组合与安装器身份按实际任务核验。

- normal path requires only reachable root SSH; a preinstalled CloudPanel is not mandatory for a genuinely empty supported TARGET；
- if CloudPanel is absent, P07 may bootstrap only after exact `BOOTSTRAP_CLOUDPANEL:<target_ip>` confirmation；
- supported OS/arch is an explicit release-pinned allowlist；current feature line covers Ubuntu 22.04/24.04/26.04 and Debian 12/13 on x86_64/ARM64；bootstrap additionally requires ≥1 Core, a genuine 2 GB-class VM, and ≥10 GB disk；
- bootstrap refuses a TARGET with CloudPanel state, MySQL/MariaDB data, existing htdocs, or a listener on 80/443；
- installer URL and SHA256 are release-pinned from official CloudPanel documentation；checksum failure = no execution；
- current fresh-target bootstrap DB engine = OS-matched MariaDB: Debian 13 requires 11.8 (`MARIADB_11.8`), Debian 12 / Ubuntu 22.04 / 24.04 require 10.11 (`MARIADB_10.11`); a migration TARGET must prove both installed daemon identity and active SQL endpoint version match the selected OS-specific engine, with unsupported OS/unknown/other engines refused; existing CloudPanel / MySQL / Percona / MariaDB databases are never automatically replaced；
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


### 10.2 目标机主动迁入与跨任务收口

- [目标端 Pull 编排](../../lib/server_migration_pull.py)是普通单站与整机入口。任务状态、主机和站点身份、事务标记、续传与回滚收据归目标机。准备阶段保护已存在的站点和数据库，旧机继续服务，目标端计划任务和应用写入保持未激活。
- 资产分母包含站点文件、Web Root 外业务资产、站点账户、应用配置、SQL 对象和数据、SQLite 权威快照及 sidecar、Cron/PM2/NVM、源端 HTTP 基线。最终同步前重新核对范围、目标归属、应用映射和安全恢复点。源身份、资产范围或现有目标状态发生歧义时阻断。
- [SQL 差异诊断](../../lib/sql_diff_evidence.py)只形成建议性证据。将导出完整性、主键/行值、DDL 与引擎语义、未知 SQL 副作用、时间一致性、隔离恢复分开校验。不同时间的快照或隔离过滤后的恢复不能直接授权使用原始 SQL。
- 跨任务处理保留父任务、续迁任务和余站任务的原身份。只有能证明站点与数据库均归属本次事务时才纳入执行范围。只读对账、隔离演练、状态认领、创建隔离数据库和应用连接切换分别标明写入范围。已暂存、已认领、已连接与最终同步、完整回滚、可切换分层记账。
- 最终操作前保全原目标数据库与应用配置。配置切换须有可恢复备份与回读，记录并拒绝未预期的并发改动。回滚先确认新端运行已停止且公网流量条件仍允许回退，才可恢复旧端；公网已改路由或已产生新端写入时，进入独立的数据对账和恢复评估。
- 跨任务候选接口、实现范围和机器证据以对应 PR 精确提交为准。单任务或隔离样本结果只覆盖该路径，整机验收按全部站点、资产和阶段逐一证明。

## 11. Destructive Guard

A16 real negative gate proves：

- wrong confirmation = zero target contact；
- correct confirmation still cannot overwrite existing target；
- full transport cannot bypass existing-site refusal；
- source preserved；
- target business assets remain unchanged on refusal；
- failed migration leaves no private transport staging；
- DNS/Production/old-server destructive writes remain zero。

## 12. Settings / Retention / Automation

Policy files may not contain password/token/private-key/OAuth-style fields.

Retention：

- automatic backup onboarding defaults to **1 verified local generation per site**；
- an existing config with an explicit `local_keep_last` value is preserved on upgrade; release install does not silently rewrite retention；
- local automatic pruning is allowed only after the same site's current Google + B2 uploads both PASS；
- only `automatic` packages may be auto-delete candidates；
- `manual / pre_migration / pre_upgrade` protected；
- legacy/no-kind protected；
- Google / B2 remote copies are not deleted by the local one-generation policy；
- plan read-only；
- apply requires policy authorization + exact `DELETE_AUTOMATIC_BACKUPS` + fresh verify；
- corrupt/unverifiable package is not auto-deleted。

Automation only renders VF policy-run Cron; it is not a generic Cron manager.

## 13. Disaster Recovery

历史 A18 验证覆盖的恢复流程：

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

The DR seed is fixture preparation only. It does not rerun or replace the separate Real Storage authority.

## 14. 证据归属

源码与候选、发布与分发、现场构建、实际迁移和用户验收由 [项目 Current](CURRENT.md) 分别路由。历史 A01–A20 和精确身份保留于 [历史 SSOT](https://github.com/llhzx2018/vf-server-ops/blob/aa0f6242f60033d626d9dc6543781322e6e32507/docs/authority/SSOT.md) 和 [历史实机证据](../evidence/P07_REAL_GATE_CLOSURE_20260906.md)。每项结果仅覆盖其任务、资产、运行环境和精确构建。
