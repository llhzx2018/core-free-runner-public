# P07 · VF Server Ops · RC3 CURRENT TRUTH

Last reconciled: 2026-09-26 (America/Los_Angeles)

> This file is the current Authority for the Slot 3 RC3 candidate line. Machine/Runner closure, Real VPS/User evidence, Formal Release, Production, DNS cutover, and SOURCE retirement are separate states and must never be conflated.

## 1. Current product position

P07 ordinary users have exactly one permanent Toolbox entry:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-toolbox.sh)
```

Top-level Toolbox remains:

```text
1. 网络节点 / V2Ray
2. VPS 一键验机
3. CloudPanel 备份 / 恢复 / 迁移
4. 系统维护 / 安全
0. 退出
```

Slot 3 remains `测试中` until current Real gates R1-R4 are complete. Slot 4 is System Care RC15 and remains `可用`.

No second ordinary-user entry is authorized.

## 2. Current exact runtime identity — guided-init16

Source repository: `llhzx2018/vf-server-ops`  
Candidate line: `candidate-p07-v0.1.0-rc3`  
Source PR: `#19`  
Source runtime merge: `78691699d3b5186ff902550ec65facf0976c89a1`

```text
Version                                      VF Server Ops 0.1.0 RC3
BUILD_ID                                     0.1.0-rc3-guided-init16
BUILD_ID blob                                622b752887d46c17a8a5d05046037a2dc6a35475
bin/vfops-storage-setup blob                 b279677ae561f9feb689964bd8f09be98c9211c9
lib/google_device_oauth.py blob              3b023f307bf744650a351e19bde01b3597469992
tests/test_google_device_oauth.py blob       c72c938a5ed81b074c1ae8a3afbb0943df0aa683
tests/test_storage_onboarding_ux.py blob     59bf88d6b6a6493c536919ab67318513330d091f
```

Runtime identity is defined by the source merge plus exact code/blob identity. Later Authority-only commits may advance the candidate branch HEAD without changing this runtime identity.

Public repository: `llhzx2018/core-free-runner-public`  
Public PR: `#846`  
Public main merge: `fd02a3db860a0773a3587bf5d78de0daf4875861`

```text
init16 installer blob                        4a7889ea606fa2353f194abbb2c6b27345f35050
stable p07.sh blob                           006e6bf7766ac8f10227ed6e88605bfdc7efe9ee
Toolbox blob                                 69be6c8623addd6251e8f7fac596d1e93bc34789
Toolbox Slot3 expected                       0.1.0-rc3-guided-init16
Toolbox public version                       V0.1.0
Toolbox Slot3 public status                  测试中
System Care expected                         0.1.0-rc15
```

## 3. Why guided-init16 supersedes guided-init15

The Owner required the R2 first-time flow to be preparation-first and as close to one-click as possible. `guided-init15` implemented that direction, but before Owner Real R2 testing the Google Device OAuth contract was re-verified and the init15 assumption that token polling could omit the OAuth Client Secret was rejected.

`guided-init16` keeps the improved UX and corrects the credential contract:

```text
device authorization request  client_id only
token polling                 client_id + client_secret
Client Secret input           hidden terminal input
helper transport              stdin, not argv
rclone persistence            obscured value only
secret echo/log               DENY
```

`guided-init15` is now only the fixed verified baseline for the init16 layered installer. It is not the current Owner Real-test identity.

## 4. Current R2 first-time user flow

Before starting, the UI explicitly tells the user what must be prepared:

```text
Google：OAuth Client ID + Client Secret
B2：Bucket + Application Key ID + Application Key
Recovery Key：P07 自动生成，无需提前准备
```

The embedded tutorial explains:

- create/select Google Cloud project;
- enable Google Drive API;
- create OAuth Client of type `TVs and Limited Input devices`;
- save Client ID + Client Secret;
- create/select Backblaze B2 Bucket;
- create Application Key with required read/write and Bucket-list permissions;
- save Application Key ID + Application Key;
- Recovery Key does not need to be created by the user.

The menu is:

```text
1. 已准备好，一键初始化 Google + B2
2. 查看完整准备教程
3. 从已有 P07 服务器导入
4. 检查当前设置
0. 返回
```

After the user supplies the prepared third-party credentials, P07 automatically performs:

```text
Google Device OAuth browser authorization
→ Google direct verification
→ B2 Bucket discovery
→ automatic Recovery Key generation
→ Google crypt + B2 crypt creation
→ storage configuration
→ Google + B2 real health verification
→ reveal Recovery Key once only after health PASS
```

The plaintext Recovery Key is not persisted to P07 config or logs.

## 5. Current Menu 3 and capability state

The ordinary-user Slot 3 structure remains the single product path for:

```text
网站管理 / 备份
Restore-As / 原域恢复
跨 VPS 迁移
Google + B2 远程灾备
Guarded Scheduler
CloudPanel 管理
```

Current implementation includes:

```text
CloudPanel inventory / site management               IMPLEMENTED
verified local backup                                IMPLEMENTED
Restore-As to new domain                              IMPLEMENTED
TARGET site + DB automatic creation                  IMPLEMENTED
DB import/export verification                        IMPLEMENTED
app config remap / WordPress URL remap               IMPLEMENTED
Host + HTTPS SNI local verification                  IMPLEMENTED
cross-VPS migration path                             IMPLEMENTED
Google Device OAuth guided onboarding                IMPLEMENTED
Backblaze B2 guided onboarding                       IMPLEMENTED
dual crypt remote protection                         IMPLEMENTED
current-site-set first-verification guard            IMPLEMENTED
Guarded Scheduler                                    IMPLEMENTED
```

Implementation and Machine PASS do not equal current Real Owner/User PASS.

## 6. Current layered installer contract

Permanent route:

```text
P07 Toolbox
→ stable installers/p07.sh
→ installers/p07-rc3-r2-oauth-contract.sh
→ fixed verified guided-init15 public main aa4dbc32cdddd81a188d55714c050de6b28436f2
→ source-exact guided-init16 overlay
```

The installer verifies exact blobs and syntax before commit. `P07_INIT16_TEST_FAIL=1` fault injection proves a failed init16 upgrade restores the exact pre-run init15 installation tree rather than leaving a partial upgrade.

The older layered chain below init15 remains historical fixed infrastructure and is not the current identity.

## 7. guided-init16 Machine / distribution closure

Canonical evidence:

- `docs/evidence/P07_GUIDED_INIT16_R2_ONBOARDING_MACHINE_CLOSURE_20260911.md`
- `docs/evidence/P07_GUIDED_INIT12_REAL_R1_DBADD_CLOSURE_20260911.md` — retained Restore-As remediation evidence
- `docs/evidence/P07_GUIDED_INIT10_CLOUDPANEL_FOUNDATION_MACHINE_CLOSURE_20260911.md` — retained CloudPanel foundation evidence
- `docs/evidence/P07_REAL_GATE_CLOSURE_20260906.md` — historical Real engineering evidence for its exact older identities

Dedicated init16 public gate:

```text
PR #846 run 34670251605      PASS
main run 34670304430         PASS
System Care main 34670304410 PASS
```

The dedicated gate proves:

```text
exact init16 blobs                                 PASS
combined current runtime                           PASS
Google OAuth tests                                 PASS
onboarding UX tests                                PASS
storage_setup regression                           PASS
auto_backup regression                             PASS
first-run / scheduler guard regression             PASS
preparation-first + secret-boundary contract       PASS
init15 → injected init16 failure exact rollback    PASS
init15 → init16 normal upgrade                     PASS
stable p07.sh route                                PASS
permanent Toolbox route                            PASS
System Care RC12 preservation at guided-init16     PASS / HISTORICAL
```

## 8. Ordinary-user safety boundary

```text
DNS automatic mutation                        DENY
SOURCE / old-server automatic deletion        DENY
TARGET existing same-domain overwrite         DENY
SOURCE-domain certificate reuse on Restore-As DENY
site / DB / panel-user delete in ordinary UX  DENY / NOT EXPOSED
manual empty TARGET prerequisite              DENY
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

If a current transaction fails, P07 may roll back only resources/configuration created or changed by that transaction. SOURCE and DNS remain outside automatic mutation scope.

## 9. Current Real evidence and acceptance boundary

Historical Owner Restore-As failures remain evidence and are not erased by later Machine fixes:

```text
R1 attempt #1  guided-init10  MYSQL_CREATE_IMPORT_VERIFY / CloudPanelError
R1 attempt #2  guided-init11  db_add exit=1
```

The current required Real sequence remains:

```text
R1 Current Real Restore-As New Domain             RETRY_REQUIRED / NOT_PASS
R2 Current Full Local + Google + B2 First Verify  NOT_RUN
R3 Current Guarded Scheduler Real Gate            NOT_RUN
R4 Current Guided Cross-VPS Restore/Migration     NOT_RUN
CURRENT_RC3_REAL_OWNER_USER_PASS                  NOT_PROVEN
```

The init16 Machine closure does not promote any of these Real gates.

R2 can become `REAL_PASS` only after the Owner VPS uses the current permanent Toolbox/init16 flow, completes Google+B2 onboarding, refreshes the current CloudPanel site inventory, and successfully completes the required Local + Google + B2 first verification for the current site set.

R3 may run only after that current first-verification evidence exists. R4 still requires genuine cross-VPS execution evidence.

Until R1-R4 are complete, Slot 3 remains `测试中`.

## 10. Workflow / governance anomaly classification

Some older P07 workflows still encode a previous current BUILD_ID such as guided-init14 and may stop at an identity/setup assertion before running behavioral tests. Those red runs are current-identity migration debt, not proof that unchanged CloudPanel or Restore-As behavior failed.

Repository-global Public Runner Trigger / Workflow Archive findings remain separate pre-existing S01 governance debt. P07 must not mutate unrelated S01 history merely to manufacture green.

## 11. Current classification

```text
GUIDED_INIT16_SOURCE                         CURRENT / MERGED_TO_CANDIDATE
PUBLIC_GUIDED_INIT16_DISTRIBUTION            MAIN / TESTING
GUIDED_INIT16_R2_ONBOARDING_MACHINE_GATE     PASS
GUIDED_INIT16_TRANSACTION_ROLLBACK_GATE      PASS
GUIDED_INIT16_STABLE_TOOLBOX_ROUTING_GATE    PASS
SYSTEM_CARE_RC15                             MAIN / MACHINE_PASS
RESOURCE_PROFILE_1C_2G_BALANCED              PRODUCTION_CALIBRATED_VERIFIED
RESOURCE_PROFILE_2C_4G_BALANCED              CANDIDATE / REAL_NOT_RUN
RESOURCE_SAFE_APPLY_PRODUCTION               NOT_RUN
SYSTEM_CARE_RC14_PRODUCTION_INSTALL           PASS / HISTORICAL
SYSTEM_CARE_RC15_PRODUCTION_INSTALL           PASS
SYSTEM_CARE_RC15_PERMANENT_ROUTE              PASS
CLOUDPANEL_FOUNDATION_COMPLETE               MACHINE_PASS
RESTORE_AS_IMPLEMENTATION                    MACHINE_PASS
CURRENT_RESTORE_AS_NEW_DOMAIN_REAL_VPS       RETRY_REQUIRED / NOT_PASS
CURRENT_GOOGLE_B2_ALL_SITE_FIRST_VERIFY      NOT_RUN
CURRENT_GUARDED_SCHEDULER_REAL_GATE          NOT_RUN
CURRENT_CROSS_VPS_GUIDED_MIGRATION_REAL      NOT_RUN
CURRENT_RC3_REAL_OWNER_USER_PASS             NOT_PROVEN
MENU3_PUBLIC_STATUS                          TESTING
FORMAL_TAG_RELEASE                           NOT_AUTHORIZED
PRODUCTION_CUTOVER                           NOT_AUTHORIZED
DNS_CUTOVER                                  NOT_RUN
SOURCE_RETIREMENT                            NOT_RUN
```

## 12. Slot 4 Resource Intelligence RC14 current truth

On 2026-09-26, P07 System Care Slot 4 advanced from RC12 to RC14 on public main.

Current public main after the route-contract follow-up:

```text
core-free-runner-public main                  6c83875527271b90ddfc42cf9892d2e100e37813
System Care current package                   0.1.0-rc14
System Care manifest blob                     8c0498949d2ec5c255ba14c25e9cdbe0ce82c83e
Toolbox SYSTEM_CARE_EXPECTED                  0.1.0-rc14
```

RC14 provides:

```text
Resource Profile Engine
1G / 2G / 4G / 8G / Custom
1 / 2 / 4 vCPU / Custom
Conservative / Balanced / Performance
Production read-only calibration
Safe Plan
Backup → Validate → CAP-ONLY Apply → Verify → Receipt → Rollback
```

First Production-calibrated profile:

```text
VF-RP-2G-1C-BALANCED                         PRODUCTION_CALIBRATED_VERIFIED
Real Production read-only reconciliation      PASS
MySQL expected settings                       5 / 5 KEEP
Referenced PHP pools                          16 / 16 KEEP
Unexpected CHANGE                             0
Production Apply                              NOT_RUN
```

Main proof for the RC14 content merge at `28b4dde1bbf3a71aafd476c57bd953872ea28609`:

```text
P07 System Care Smoke #236                    SUCCESS
P07 Toolbox Smoke #343                        SUCCESS
P07 System Care Real Mutation Smoke #16       SUCCESS
Public Runner Current Self Test #709          SUCCESS
```

The first main push exposed one stale Slot 3 workflow assertion that still hard-coded System Care RC12. Slot 3 implementation checks themselves passed; only the old route identity assertion failed.

That workflow contract was repaired by PR #1382 and merged. Current main became `6c83875527271b90ddfc42cf9892d2e100e37813`.

Post-fix main proof:

```text
P07 Server Ops RC3 R2 One-Click Onboarding #28 SUCCESS
Public Runner Current Self Test #710            SUCCESS
```

This Slot 4 promotion does not alter Slot 3 Real gate truth:

```text
R1 Current Real Restore-As New Domain             RETRY_REQUIRED / NOT_PASS
R2 Current Full Local + Google + B2 First Verify  NOT_RUN
R3 Current Guarded Scheduler Real Gate            NOT_RUN
R4 Current Guided Cross-VPS Restore/Migration     NOT_RUN
CURRENT_RC3_REAL_OWNER_USER_PASS                  NOT_PROVEN
```

Merge / Distribution / Production Apply remain separate states. RC14 being current on public main does not mean a Production Safe Apply was executed.

## 13. Slot 4 RC14 Production installation closure

On 2026-09-26, the Owner executed the permanent public System Care route on the current DigitalOcean Production server.

Pre-install observation:

```text
System Care installed                         NO / NOT_INSTALLED
Production server                             1 vCPU / 1973 MB detected / 2047 MB Swap
```

Permanent distribution readback before install:

```text
Toolbox SYSTEM_CARE_EXPECTED                  0.1.0-rc14
Toolbox System Care installer                 main/installers/p07-system-care.sh
Installer VERSION                             0.1.0-rc14
Installer MANIFEST_BLOB                       8c0498949d2ec5c255ba14c25e9cdbe0ce82c83e
PERMANENT_ROUTE                               PASS
INSTALLER_IDENTITY                            PASS
```

Production install / capability verification:

```text
Installed System Care                         0.1.0-rc14
Resource menu                                 PASS
resource_profile.py                           PRESENT
resource_apply.py                             PRESENT
Production read-only calibration              PASS
Safe Plan                                     ELIGIBLE
MySQL expected settings                       5 / 5 KEEP
Referenced PHP pools                          16 / 16 KEEP
Unexpected CHANGE                             0
```

The post-install runtime measurement changed the PHP Worker RSS reference from the earlier idle/fallback observation to 132 MB, and the aggregate PHP child budget adapted from 7 to 5 while the single-core hot-pool ceiling remained 2. This is expected adaptive behavior; the Production plan still reconciled all real referenced pools as KEEP.

Write/restart proof:

```text
MySQL/PHP/WP-Cron config bytes                UNCHANGED
cron PID                                      UNCHANGED
nginx PID                                     UNCHANGED
mysql PID                                     UNCHANGED
php7.3-fpm PID                                UNCHANGED
php8.3-fpm PID                                UNCHANGED
php8.4-fpm PID                                UNCHANGED
Swap                                          UNCHANGED
Production Safe Apply                         NOT_RUN
```

Required services remained active after installation.

Resource observation at closure:

```text
RAM total                                     1.9 GiB
RAM used                                      1.3 GiB
RAM available                                 624 MiB
Swap used                                     ~409 MiB / 2 GiB
Load average                                  0.76 / 0.63 / 0.57
```

Final Production installation classification:

```text
P07_SYSTEM_CARE_RC14_PRODUCTION_INSTALL       PASS
P07_PERMANENT_DISTRIBUTION_READBACK           PASS
P07_RESOURCE_CALIBRATION_AFTER_INSTALL        PASS
RESOURCE_SAFE_APPLY                           NOT_RUN
MYSQL_CONFIG_WRITE                            NONE
PHP_CONFIG_WRITE                              NONE
SERVICE_RESTART                               NONE
SWAP_WRITE                                    NONE
```

A local rollback location was retained at installation time:

```text
/root/p07-system-care-before-rc14-20260926-041103
```

Because System Care was not installed before this run, the rollback directory is retained as transaction evidence but is not evidence of a prior installed System Care version.

This closes Distribution + Production Installation for Slot 4 RC14 only. It does not promote Slot 3 R1-R4, does not execute Resource Safe Apply, and does not authorize Source retirement or DNS mutation.

## 14. Slot 4 Resource Calibration Registry RC15 current truth

On 2026-09-26, P07 System Care advanced on public main from RC14 to RC15.

RC15 does not change the existing resource recommendation formulas. It introduces a Calibration Registry so recommendation math and Production verification state are separate truths.

Current public main:

```text
core-free-runner-public main                  99b2552606c68b6b278e3310b0cb2a0006474ad9
System Care current package                   0.1.0-rc15
System Care manifest blob                     e22557ae08fb79a13dffda6fbc91b34cdaf7ca1e
Toolbox SYSTEM_CARE_EXPECTED                  0.1.0-rc15
```

Registry states:

```text
PRODUCTION_VERIFIED
CANDIDATE
PREVIEW_ONLY
```

Initial registry truth:

```text
VF-RP-2G-1C-BALANCED                         PRODUCTION_VERIFIED
VF-RP-4G-2C-BALANCED                         CANDIDATE
all other non-registered profiles             PREVIEW_ONLY
```

Safe Apply is now registry-gated. A recommendation can be numerically valid while still being blocked from automatic Production mutation.

2C/4GB Balanced candidate baseline:

```text
innodb_buffer_pool_size                       512M
max_connections                               120
tmp_table_size                                48M
max_heap_table_size                           48M
table_open_cache                              2000
hot PHP pool ceiling                          4
low-traffic PHP ceiling                       2
Swap recommendation                           2GB
```

This 2C/4GB line is not Production-calibrated.

Machine proof on exact candidate head `a44513cd66a652c7be51ac878929238ebe9c8c94`:

```text
P07 System Care Smoke #237                    SUCCESS
Resource Profile tests                        11 / 11 PASS
Resource Safe Apply tests                     12 / 12 PASS
P07 Toolbox Smoke #344                        SUCCESS
P07 Server Ops Onboarding #29                 SUCCESS
Trigger Scope #2047                           SUCCESS
Archive Integrity #648                        SUCCESS
```

Main push proof after merge:

```text
P07 System Care Smoke #238                    SUCCESS
P07 System Care Real Mutation Smoke #17       SUCCESS
P07 Toolbox Smoke #345                        SUCCESS
P07 Server Ops Onboarding #30                 SUCCESS
Public Runner Current Self Test #711          SUCCESS
```

A read-only DigitalOcean inventory check found no existing 2C/4GB Droplet. No paid Droplet was created and the current Production server was not resized.

Therefore:

```text
VF-RP-4G-2C-BALANCED_REAL_CALIBRATION         NOT_RUN
VF-RP-4G-2C-BALANCED_PRODUCTION_VERIFIED      NOT_PROVEN
VF-RP-4G-2C-BALANCED_AUTO_APPLY               BLOCKED
```

Production installation truth remains separate:

```text
Public main System Care                       RC15
Current Production installed System Care      RC15
RC15 Production installation                  PASS
Resource Safe Apply                           NOT_RUN
```

The next Production step is only an RC14 → RC15 System Care software upgrade plus read-only reconciliation. It must not execute Resource Safe Apply and must not change PHP/MySQL/Swap/service state.

## 15. Slot 4 RC15 Production upgrade closure

On 2026-09-26, the Owner upgraded the real DigitalOcean Production server from System Care RC14 to RC15 through the permanent public P07 route.

Pre-upgrade identity:

```text
Installed System Care                         0.1.0-rc14
```

Permanent distribution and installer identity:

```text
Toolbox SYSTEM_CARE_EXPECTED                  0.1.0-rc15
Toolbox installer                             main/installers/p07-system-care.sh
Permanent route                               PASS
RC15 installer identity                       PASS
```

Upgrade result:

```text
Installed System Care                         0.1.0-rc15
Calibration Registry files                    PASS
```

Real 1C/2GB read-only reconciliation:

```text
Profile                                       VF-RP-2G-1C-BALANCED
Calibration                                  PRODUCTION_VERIFIED
Apply State                                  ELIGIBLE
MySQL expected settings                       5 / 5 KEEP
Referenced PHP pools                          16 / 16 KEEP
Unexpected CHANGE                             0
Production calibration                        READ_ONLY_COMPLETE
```

Registry matrix readback:

```text
VF-RP-2G-1C-BALANCED                         PRODUCTION_VERIFIED
VF-RP-4G-2C-BALANCED                         CANDIDATE
other tested cells                            PREVIEW_ONLY
```

Write/restart immutability proof:

```text
MySQL/PHP/WP-Cron config bytes                UNCHANGED
cron PID                                      UNCHANGED
nginx PID                                     UNCHANGED
mysql PID                                     UNCHANGED
php7.3-fpm PID                                UNCHANGED
php8.3-fpm PID                                UNCHANGED
php8.4-fpm PID                                UNCHANGED
Swap                                          UNCHANGED
Resource Safe Apply                           NOT_RUN
```

All required services remained active after the RC15 upgrade.

Resource observation at closure:

```text
RAM total                                     1.9 GiB
RAM used                                      1.0 GiB
RAM available                                 923 MiB
Swap used                                     ~660 MiB / 2 GiB
Load average                                  0.25 / 0.34 / 0.37
```

Final RC15 Production classification:

```text
P07_SYSTEM_CARE_RC15_PRODUCTION_UPGRADE       PASS
P07_RC15_PERMANENT_DISTRIBUTION               PASS
P07_RC15_1C2G_REGRESSION                      PASS
P07_RC15_CALIBRATION_REGISTRY                 PASS
VF_RP_2G_1C_BALANCED                          PRODUCTION_VERIFIED
VF_RP_4G_2C_BALANCED                          CANDIDATE
RESOURCE_SAFE_APPLY                           NOT_RUN
MYSQL_CONFIG_WRITE                            NONE
PHP_CONFIG_WRITE                              NONE
SERVICE_RESTART                               NONE
SWAP_WRITE                                    NONE
```

Rollback evidence retained at:

```text
/root/p07-system-care-before-rc15-20260926-093327
```

This closes RC15 Production software upgrade and Registry readback only.

It does not promote VF-RP-4G-2C-BALANCED beyond CANDIDATE and does not execute Resource Safe Apply.
