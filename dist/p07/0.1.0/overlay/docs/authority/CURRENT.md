# P07 · VF Server Ops · CURRENT AUTHORITY RESOLVER

Status: `CURRENT_AUTHORITY_RESOLVER`  
Policy: `DYNAMIC_TRUTH_NOT_STORED_HERE`  
Authority: `llhzx2018/vf-server-ops` + each owning external authority

> 本文件位于 `main`，负责 **fresh-window 路由与 fail-closed 解析**，不把 Working Phase、Candidate Runtime SHA、Machine/Real Gate、Release、Production 或 Next Action 缓存成 main 的长期 Current Truth。

## 1. Current Development Line Pointer

```text
Stable / canonical baseline branch = main (V0.1.0 release source)
Current working authority branch   = main
```

`current working authority branch` 只是读取路由：

```text
branch pointer != merge to main
branch pointer != Formal Release
branch pointer != Distribution
branch pointer != Production
branch pointer != OWNER Real/User PASS
```

OWNER 最新明确任务若锁定了另一条 exact branch / PR，则 OWNER 指令优先，并必须用 live Git 验证；不得静默沿用本 Pointer。

当 P07 正式切换 current working line 时，只更新本 Pointer / `VF_PROJECT.json.current_working_branch`，不要把整套动态 Gate/Phase/Next Action 再复制回 main。

## 2. Fresh-window Current Resolver

进入 P07 bounded task 时按以下顺序解析：

```text
1. OWNER 最新明确指令
2. llhzx2018/gov-doc/main/CURRENT.md -> Current Runtime Entry
3. main/AGENTS.md
4. 本 CURRENT Resolver
5. resolve exact task line:
   - stable/main task -> main
   - ordinary current development -> current working authority branch
   - OWNER named branch/PR -> that exact live branch/PR
6. exact line docs/authority/CURRENT.md + VERSION + BUILD_ID/module identity when relevant
7. live Git branch / PR / changed-file / workflow evidence required by the task
8. Release / Distribution / Production evidence only when the task actually enters those stages
```

不得从 main 的历史 Bootstrap snapshot 推断当前 development phase，也不得因为某个旧 OPEN PR 存在就自动选择它。

## 3. Dynamic Truth Ownership

| Fact | Owning truth | Resolver rule |
|---|---|---|
| Stable product baseline | `main` + stable RPD / SSOT / Acceptance | 只代表已晋级稳定合同/源码，不代表 current working candidate |
| Current working line | 本文件 branch pointer + live Git | branch 必须真实存在；任务开始时重新验证 |
| Current working runtime / BUILD_ID | exact working branch files | 不复制到 main Resolver |
| Current Phase / Next Action | OWNER instruction + exact working branch Current + live PR/Git | 不写进 main `VF_PROJECT.json` |
| Machine / Real evidence | exact-source workflow / registered Runner / evidence | `UNKNOWN / NOT_RUN != PASS` |
| Formal Release / Tag / assets | GitHub Release / Tag live-read | working branch merge不能外推 Release |
| Distribution | owning distribution manifest / core-updates | 与 Source 独立 |
| Production / Server state | OWNER-authorized runtime / Production evidence | 不从 Git branch 推导 |

## 4. Fail-Closed Rules

以下任一情况必须停止动态结论并标记 `RECOVERY_REQUIRED / UNKNOWN / NOT_PROVEN`：

- `current working authority branch` 不存在或已被替换；
- OWNER 当前任务与本 Pointer 指向不同且无法确定 exact branch/PR；
- main Resolver、working branch Current、live Git 相互冲突；
- 试图使用旧 `VF_PROJECT.json` 的 phase/status/next_action 作为当前事实；
- Machine evidence 没有绑定 exact source；
- Release / Distribution / Production 无法从 owning source live-read。

禁止退回 2026-09-05 Bootstrap / Phase 1 snapshot 自证当前状态。

## 5. Stable Product Guard

P07 长期产品边界继续由 `RPD.md` / `SSOT.md` / `ACCEPTANCE_MATRIX.md` 定义。本 Resolver 不重写产品合同。

稳定安全边界至少包括：

```text
ordinary user = one P07 Toolbox entry
no automatic DNS cutover
no SOURCE deletion by default
no existing TARGET overwrite
remote private backup requires encryption
BACKUP_CREATED != RECOVERABLE
Production Restore / Migration / Cutover / Destructive Action = separate OWNER gate
Secret / PRIVATE_DATA / Production backup != public Git / public Runner
```

CloudPanel 已拥有的常规面板能力不得被 P07 重建成第二套通用 Web 面板。

## 6. VF_PROJECT Boundary

`VF_PROJECT.json` 只保存结构 metadata 与 Authority pointers：

```text
project identity
repository
branch roles / current working-line pointer
authority paths
```

以下动态字段禁止重新作为长期 main cache，除非先证明存在不可替代的 active machine consumer：

```text
lifecycle / status / current_phase
working/candidate/release/production version snapshots
machine_gate / latest_ci / last_real_gate
owner_acceptance / next_action
full backup/restore/migration Gate result matrices
```

历史 Git 中的旧字段继续保留 provenance，不回填到 Current。

## 7. Same-project Continuation / Handoff

P07 不复制 shared Runtime/Handoff 版本。每次 continuation 先读：

```text
llhzx2018/gov-doc/main/CURRENT.md
-> Current Runtime Entry
-> P07 main/AGENTS.md
-> 本 Resolver
-> exact working branch truth
```

同一 ChatGPT Project 新聊天不是 Handoff，`OLD_WINDOW_ACTION = NONE`。真正跨 Project / Workspace / Environment、不可重建输入、OWNER 明确要求或 Disaster Recovery 才进入 root Current 指向的 `skill-handoff`。

存在更高层 Master Mission 时：

```text
Master Mission > P07 validation sample > current P07 task / branch / PR
```

项目任务完成不得冒充 Master Mission 完成。

## 8. V0.1.0 Release State

```text
P07 V0.1.0 Final Integration Source  = RELEASED
Four-slot Integration Manifest       = PRESENT
Product-wide terminal language       = ZH_FIRST
Slot 1 Network Node                  = 0.1.0-rc10 / ZH_FIRST / PUBLIC_DISTRIBUTED
Slot 2 VPS Audit                     = V2.2.2 / 2.2.2-rc2-chinese-first / PUBLIC_DISTRIBUTED
Slot 3 CloudPanel Ops                = 0.1.0-release24 / ZH_BEGINNER_FIRST_V1 / CURRENT_RUNTIME_LAZY_V1 / TARGET_OWNED_PULL / TERMINAL_UX_V2 / WEBSITE_DATA_ONLY_V1
Slot 4 System Care                   = 0.1.0-rc18 / ZH_FIRST / PUBLIC_DISTRIBUTED
Automatic DNS mutation               = DENY
Automatic SOURCE deletion            = DENY
Resource Safe Apply auto-run         = DENY
Formal Release Tag                    = p07-v0.1.0
GitHub Release                        = PUBLISHED
Public Distribution                   = 9151216074fd3dc4bf049f575657d44e460ae085
```

Formal Tag/Release is complete. main is the canonical released source. Production destructive actions remain separately gated.


## 9. V0.1.0 Production Installation Closure

On 2026-09-28, the released P07 V0.1.0 was installed and verified on the real DigitalOcean Production server through the permanent public Toolbox route.

```text
P07_V010_PRODUCTION_INSTALL          PASS
P07_FOUR_SLOT_TOOLBOX                PASS
P07_SLOT3_FINAL_RUNTIME              PASS
P07_SLOT4_RC15                       PASS
CONFIG_BYTES_UNCHANGED               PASS
SERVICE_PID_UNCHANGED                PASS
MIGRATION_EXECUTED                   NO
DNS_WRITE                            NONE
SOURCE_DELETE                        NONE
RESOURCE_SAFE_APPLY                  NOT_RUN
```

Installed identities:

```text
VF Server Ops                        0.1.0
Slot 3 Build                         0.1.0-release1
System Care                          0.1.0-rc15
```

The four top-level Toolbox entries were visible and routable:

```text
1. 网络节点 / V2Ray
2. VPS 一键验机
3. CloudPanel 备份 / 恢复 / 迁移
4. 系统维护 / 安全
```

Slot 3 Final Release self-test passed:

```text
9 tests   PASS
4 tests   PASS
49 tests  PASS
```

Core services remained active with unchanged MainPID during the installation:

```text
cron
nginx
mysql
php7.3-fpm
php8.3-fpm
php8.4-fpm
```

Swap note:

The first closure helper attempted a util-linux `swapon --output=...` syntax that is not supported by this server build, so that specific shell assertion is not used as evidence.

The final direct runtime readback confirmed:

```text
NAME         /home/.swap
TYPE         file
SIZE         2G
PRIO         -2
```

No Swap write operation was executed by the P07 installation.

Resource observation at closure:

```text
RAM total      1.9 GiB
RAM used       1.1 GiB
RAM available  869 MiB
Swap total     2.0 GiB
Swap used      ~950 MiB
Load average   0.58 / 0.62 / 0.38
```

Rollback copy retained:

```text
/root/p07-before-v010-20260928-092139
```

Final classification:

```text
P07_V0.1.0_SOURCE_MAIN               RELEASED
P07_V0.1.0_PUBLIC_DISTRIBUTION       RELEASED
P07_V0.1.0_GITHUB_RELEASE            PUBLISHED
P07_V0.1.0_PRODUCTION_INSTALL        PASS
P07_V0.1.0_FOUR_SLOT_INTEGRATION     PASS
```

Production destructive actions remain separately gated and were not executed by this installation.


## 10. VPS Audit V2.2.2 usage-value verdict + semantic terminal colors

Current P07 Slot 2 public route:

```text
Public version                         V2.2.2
Internal build                         2.2.2-rc1-semantic-color
Public main                            70d1b32e731f8cb7dd7a0f4b36efe273b09525d7
Candidate SHA256                       376f3cf791dcac00ba870697db9233a5ad4f765400a4dbe4418c20aafbc3b401
```

V2.2 keeps the existing benchmark scope and adds a user-facing value verdict so a single VPS can be judged without another VPS for comparison.

It reports:

```text
machine performance
single-core CPU class
database-style I/O class
CPU steal class
CloudPanel / WordPress fit
main bottlenecks
suitable / unsuitable workloads
retain / replace guidance
price/performance = NOT CLAIMED when monthly price is unknown
```

Calibration fixtures:

```text
DO-like 1C/2GB     weak single-core -> machine verdict 偏弱
Linode-like 1C/1GB strong CPU/I/O -> 良好, but RAM is the CloudPanel limitation
Balanced 2C/4GB    良好
```

This is a P07 workload-fit classification, not a global VPS market ranking.


V2.2.1 makes the judgment thresholds visible to the user and exposes the same table through `--reference`.

```text
Single-core SHA256
  Strong        >= 900 MB/s
  Good          >= 500 MB/s
  Usable        >= 250 MB/s
  Weak          >= 150 MB/s
  Very weak     < 150 MB/s

Database-style I/O
  Strong        >=1000 IOPS and fsync P95 <=2.5 ms
  Good          >=500 IOPS and fsync P95 <=5 ms
  Usable        >=300 IOPS and fsync P95 <=10 ms
  Weak          otherwise

CPU Steal
  Normal        <=2%
  Acceptable    <=5%
  Watch         <=10%
  Abnormal      >10%

CloudPanel memory baseline
  >=1800 MiB    treated as 2GB-class
  <1800 MiB     memory bottleneck
```

These are P07 workload-fit thresholds for CloudPanel / WordPress / PHP / MySQL / tool sites, not a global VPS market ranking.


V2.2.2 restores the original colored section hierarchy through a PTY when the user is in an interactive terminal, while retaining plain output for NO_COLOR / non-TTY use.

Semantic color contract:

```text
Green   strong / good / normal / recommended
Yellow  usable / attention / constrained
Red     weak / abnormal / not recommended
Gray    explanatory boundary / note
Cyan    section / summary title
```

Machine proof:

```text
Bash syntax                         PASS
DO / Linode / 2C4G verdicts        PASS
PTY color preservation             PASS
ANSI semantic-color smoke          PASS
Toolbox Smoke                      PASS
System Care Smoke                  PASS
Slot 3 Onboarding regression       PASS
```

## 11. Slot 3 release2 terminal UI distribution closure

On 2026-09-29, Slot 3 was promoted from the released V0.1.0 source line to internal Build `0.1.0-release2` without changing the top-level public product version.

Source and distribution identities:

```text
P07 public product version            V0.1.0
Slot 3 source version                 0.1.0
Slot 3 Build                          0.1.0-release2
Runtime source main                   b52c710519430122ac443b7f7ebc54a84a9a2be4
Public distribution main              70d1b32e731f8cb7dd7a0f4b36efe273b09525d7
Overlay manifest blob                 bf6d14d55546013801b275d4a1740fced1df2661
Final installer blob                  2e0185bba6b69ce79818836b723ab8faff0cb5eb
Stable installer blob                 0fba033a74df0b688b9ec1937066601bb9a3c7a1
```

The canonical Terminal UI / Color System is now part of the owning RPD and Acceptance Matrix. Slot 3 normal-user surfaces use one shared semantic mapping:

```text
Cyan      title / structure / neutral information
Green     PASS / READY / safe / healthy / recommended
Yellow    attention / configuration / restore / review
Red       fail / block / destructive / rollback / high-risk
Magenta   migration / cutover / transactional flow
Gray      version / boundary / help / immutable safety rule / back
```

Machine proof bound to the exact merged private source passed:

```text
Bash syntax                           PASS
Python compile                        PASS
Interactive TTY ANSI hierarchy       PASS
Semantic status colors               PASS
NO_COLOR plain text                  PASS
Non-TTY plain text                   PASS
Machine-output boundary              PASS
Secret boundary                      PASS
Slot 3 regressions                    PASS
Migration regressions                 PASS
Backup / Restore regressions          PASS
CloudPanel regressions                PASS
UI bloat guard                        PASS
```

Public distribution proof passed:

```text
Stable Installer Smoke               PASS
Final Distribution + R2 Onboarding   PASS
Toolbox Smoke                         PASS
System Care Smoke                     PASS
Runner Trigger Scope Gate             PASS
Runner Archive Integrity Gate         PASS
```

Production is deliberately not promoted by distribution alone:

```text
Production currently verified Slot 3 Build   0.1.0-release1
release2 Production install                  NOT_YET_OWNER_VERIFIED
Production migration / DNS / SOURCE delete   NOT_RUN
Restore overwrite                            NOT_RUN
Resource Safe Apply                          NOT_RUN
```

The Owner must run the normal one-line Toolbox route and visually verify release2 before Production truth is advanced.

## 12. Slot 3 release3 中文优先终端文案 distribution closure

On 2026-09-29, Owner Production visual acceptance exposed a terminology problem: ordinary-user migration screens still required understanding internal engineering words such as `TARGET`, `SOURCE`, `READY`, `Runtime`, `Gate`, and `Recovery`.

Slot 3 was therefore advanced to internal Build `0.1.0-release3` while the public product version remains `V0.1.0`.

Current exact identities:

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release3
Exact runtime source main             424b539b331236d85a35b310943b810046be0927
Public distribution main              477d88f775356f82a661e74baacf7977242b8748
Overlay manifest blob                 f8b5c7e9031c2b8adc40ffd24cf30e2c817189b6
Final installer blob                  2a7f554f5cdf2f94742391b7aeeaf384c30dd0fb
Stable installer blob                 7f360a78d4faf3aaa8c0ce581b8ffa57fea92d63
Toolbox blob                          4037706ee489be40bf1eb1bfa57e3da2a3d39e35
```

The user-facing terminal contract is now Chinese-first:

```text
TARGET           -> 目标服务器
SOURCE           -> 源服务器
READY            -> 已就绪
PASS / FAIL      -> 通过 / 失败
Runtime          -> 运行环境
Production       -> 正式环境
Recovery         -> 恢复保护 / 恢复副本
Gate             -> 人工确认
Migration ID     -> 迁移任务编号
SSH Key          -> SSH 密钥
```

Stable machine tokens, JSON fields, shell variables, confirmation tokens, and parser contracts remain unchanged. Common product/protocol names such as CloudPanel, DNS, SSH, IP, MySQL, SQLite, Cron, PM2, and HTTPS may remain in English with Chinese surrounding explanation.

Exact-source Machine Proof on merged private main:

```text
Source                                      424b539b331236d85a35b310943b810046be0927
Workflow run                                36526229331
Bash syntax                                 PASS
Python compile                              PASS
Chinese-first terminal copy                 PASS
Terminal semantic color contract            PASS
Slot 3 product regressions                  PASS
Machine-output boundary                     PASS
Secret boundary                             PASS
```

Public distribution PR/head gates all passed before merge:

```text
Stable Installer Smoke                      PASS
Final Distribution + R2 Onboarding          PASS
Toolbox Smoke                               PASS
System Care Smoke                           PASS
Runner Trigger Scope Gate                   PASS
Runner Archive Integrity Gate               PASS
```

Public main readback confirms `0.1.0-release3` and the exact installer / overlay identities above.

Production truth after Owner visual acceptance:

```text
Production currently verified Slot 3 Build  0.1.0-release3
release3 Production install                 OWNER_VERIFIED
Migration executed                          NO
DNS write                                   NO
SOURCE delete                               NO
Restore overwrite                           NO
Resource Safe Apply                         NO
```

Owner screenshots and terminal output confirmed the release3 Chinese-first migration screen and Build identity on 2026-09-29.

## 13. Slot 3 release4 按需加载 / 当前运行时直接安装 distribution closure

On 2026-09-29, Owner Production output showed that entering Slot 3 still replayed the historical RC / guided-init installer chain and re-ran many tests before reaching the already-released current runtime.

This was classified as installer debt, not desired product behavior. Slot 3 was advanced to internal Build `0.1.0-release4` while the public product version remains `V0.1.0`.

Current exact identities:

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release4
Exact runtime source main             532eeab3fbe62f33a281dbf4af3c22f3e51d3d26
Public distribution main              0311e657393e2fb98f366b264b56fbe85b9fb2ff
Full overlay manifest blob            f7b95e33b319beadf768fe234e9f562d8b6c1ae1
Runtime manifest blob                 43c88e83ae8f1325395086b9225bd0b9decfacdd
Final installer blob                  cf140e00dfb507a698c925a59a9b6e0d157117e0
Stable installer blob                 49bc8364e87cd6dc0aac4d73ae1f249d445185ba
Toolbox blob                          cd232fe6025ff73f7c77c9810a019af3fc0aefd6
```

Canonical loading behavior is now:

```text
Open Toolbox
    -> no Slot 3 download

Choose Slot 3
    -> if current Build is already installed: run local runtime immediately
    -> if install/upgrade is required: install the current runtime directly
    -> do not replay RC / guided-init history
    -> do not run the full unit/regression suite on Production install

Enter Remote Backup
    -> only then check/install rclone

Enter Server Migration
    -> only then check/install OpenSSH client
```

The Slot 3 runtime itself is installed as one coherent local product rather than downloading individual scripts every time a page is opened. This avoids network/runtime fragility while keeping feature-specific external dependencies lazy.

Exact-source Machine Proof on merged private main:

```text
Source                                      532eeab3fbe62f33a281dbf4af3c22f3e51d3d26
Workflow run                                36532156972
Bash syntax / Python compile                PASS
Chinese-first UI contract                   PASS
Lazy dependency contract                    PASS
Terminal UI color contract                  PASS
Full Slot 3 regressions                     PASS
Root-only auto-backup UX                    PASS
Machine-output boundary                     PASS
Secret boundary                             PASS
```

Public distribution PR/head gates all passed before merge:

```text
Stable Installer Smoke                      PASS
Final Distribution + R2 Onboarding          PASS
Toolbox Smoke                               PASS
System Care Smoke                           PASS
Runner Trigger Scope Gate                   PASS
Runner Archive Integrity Gate               PASS
```

Production truth remains separate:

```text
Production currently verified Slot 3 Build  0.1.0-release3
release4 Production install                 NOT_YET_OWNER_VERIFIED
Migration executed                          NO
DNS write                                   NO
SOURCE delete                               NO
Restore overwrite                           NO
Resource Safe Apply                         NO
```

The next Owner run of the normal one-line Toolbox route should upgrade Slot 3 directly to release4 without replaying guided-init history.

## 14. P07 全产品中文优先 / Slot 3 release5 distribution closure

2026-09-29，Owner 明确要求“中文化”不是只改 Slot 3，而是 **整个 P07 普通用户界面**。本轮因此同时收口 Toolbox、Slot 1、Slot 2、Slot 3、Slot 4 的普通终端文案，并保留机器接口的稳定英文状态码。

当前公共路由：

```text
P07 public product version             V0.1.0
Toolbox public main                    ce836793de0c542b8254aada060071bb933edc7b

Slot 1 网络节点                        0.1.0-rc10 / 中文优先
Slot 2 VPS 一键验机                    V2.2.2 / 2.2.2-rc2-chinese-first
Slot 3 CloudPanel 运维                 0.1.0-release5 / 中文优先
Slot 4 系统维护 / 安全                 0.1.0-rc17 / 中文优先
```

关键公开身份：

```text
Toolbox blob                           64b3680baadbaf7cf929b5bbb8942df9b6c40a66
Slot 1 installer blob                  67c2dbb0229f70fba6cf2f673924b27c43792c22
Slot 2 pinned source commit            29f737e68d1464fb209565acd9b77e297c1bb81b
Slot 2 SHA256                          1104724afc221ea8100841ab66f6814936d6673aa63700cacc359e7906ce7f36
Slot 3 exact private runtime source    eaed2a423cfec7bcf4e57b3aa0d38c6db610606e
Slot 3 public distribution commit      ce836793de0c542b8254aada060071bb933edc7b
Slot 3 runtime manifest blob           320c0c9030c1185bf6bc0a3de9bfee8475791da9
Slot 3 final installer blob            288cc1f9f4dbb4a027e6242b44bf2a8662f0b859
Slot 3 stable installer blob           79586aa4695da23e197173aab0c3c1c611401e64
Slot 4 installer blob                  7cceece3e7c97cef6112ca9f61ab871156577116
```

普通用户文案规则：

```text
优先中文：
  源服务器 / 目标服务器
  已就绪 / 通过 / 未通过
  运行环境 / 正式环境验证
  恢复保护 / 人工确认 / 迁移任务编号
  网站公开目录 / 资源清单 / 网站数量

允许保留通用技术名：
  CloudPanel / DNS / SSH / IP
  MySQL / SQLite / Cron / PM2 / HTTPS
  Google Drive / Backblaze B2 / OAuth / rclone
```

内部状态码、JSON 字段、Shell 变量、确认令牌和机器输出仍保持稳定英文，不得为了界面中文化破坏解析器或自动化合同。

按需加载合同继续有效：

```text
Toolbox                 只显示入口，不预装所有 Slot
已安装当前 Slot         直接本地运行
首次安装 / 升级         只安装当前正式运行时，不回放 guided-init 历史链
远程备份                使用时才检查 / 安装 rclone
服务器迁移              使用时才检查 / 安装 OpenSSH 客户端
```

Public distribution gates 已通过：

```text
P07 Network Node Package Gate           PASS
P07 Network Node Installer Smoke        PASS
P07 Toolbox Smoke                       PASS
P07 System Care Smoke                   PASS
P07 Server Ops Final Distribution       PASS
Public Runner Trigger Scope Gate        PASS
Public Runner Archive Integrity Gate    PASS
```

Production truth 仍单独记录：

```text
Production currently verified Slot 3 Build   0.1.0-release3
release4 Production install                  NOT_YET_OWNER_VERIFIED
release5 Production install                  NOT_YET_OWNER_VERIFIED
Migration executed                           NO
DNS write                                    NO
SOURCE delete                                NO
Restore overwrite                            NO
Resource Safe Apply                          NO
```

发布到 public main 不等于 Owner 正式机已经升级。下一次 Owner 运行正常一行入口后，再按实际 Build 回读更新 Production truth。



## 15. Slot 3 release6 Target-owned Pull migration distribution closure

2026-09-29，服务器迁移普通正式流程已从旧的“旧服务器发起并推送到新服务器”改为 **Target-owned Pull Model**。

固定用户模型：

```text
登录新服务器
→ 运行 P07
→ 服务器迁移
→ 整机迁入 / 单站迁入
→ 输入旧服务器 IP
→ 新服务器主动 SSH / rsync 拉取旧服务器
→ 首轮迁入
→ 最终增量同步
→ 新服务器本地验证
→ DNS 唯一人工确认
→ 正式环境验证
→ 旧服务器继续保留为 Recovery Copy
```

当前身份：

```text
P07 public product version             V0.1.0
Slot 3 Build                           0.1.0-release6
Private source main                    3cb565eaf3d15764fc6a77840bd92ee6a385fe85
Public distribution main               96faec305fd5a43a17ff4757490cae929496c84c
Runtime manifest blob                  6871192d26ed875f68b7eeb3959871c6d856e0d4
Final installer blob                   f3fdea95a97f59ca32e3777e2c7d6e410e512037
Toolbox Slot 3 expected build          0.1.0-release6
```

Exact-source / distribution evidence：

```text
Private exact-source Gate              36563032316 PASS
Authority exact-source Gate            36563389838 PASS
Public release6 distribution Gate      36576986038 PASS
Toolbox Smoke                          36576985964 PASS
Public Runner Scope Gate               PASS
Public Runner Archive Integrity        PASS
```

旧 workflow 的 release5 / guided-init16 固定身份断言在 release6 candidate 上会提前失败；该失败发生在旧身份校验阶段，不是 release6 Runtime 行为失败。release6 的 owning distribution Gate 已覆盖当前 Runtime manifest、Pull Model、中文界面、Lazy Install、隔离安装、重复执行短路和安全边界。

Production truth 仍保持：

```text
Production currently verified Slot 3 Build   0.1.0-release3
release6 Production install                  NOT_YET_OWNER_VERIFIED
Migration executed                           NO
DNS write                                    NO
SOURCE delete                                NO
Restore overwrite                            NO
Resource Safe Apply                          NO
```

Public Distribution 不得被解释为 Production 已升级。


## 16. Slot 3 release7 全菜单可见反馈修复

2026-09-29，Owner 在真实 FinalShell TTY 中确认：Slot 3 主菜单选择“3. 恢复网站”时，在没有可恢复备份的情况下看起来“没有反应”。

根因：

```text
空状态提示已经打印
→ 子模块立即 return
→ P07 主菜单重新绘制
→ 真实 TTY 执行清屏
→ 提示被瞬间擦除
→ 用户感知为“按钮没反应”
```

release7 将该问题提升为整个 Slot 3 主菜单 1–7 的统一交互合同：

```text
1. 服务器 / 网站概览
2. 备份网站
3. 恢复网站
4. 服务器迁移
5. 自动备份 / 远程灾备
6. 网站管理
7. CloudPanel 管理
```

固定：

```text
无网站 / 无备份 / 模块异常 -> 中文可见结果 + 等待用户确认后返回
子模块非零退出 -> 主菜单显示失败入口与退出码，并继续可用
明确 0 / 返回 -> 可以直接返回
真实 TTY 清屏不得吞掉需要用户看到的信息
```

当前身份：

```text
P07 public product version             V0.1.0
Slot 3 Build                           0.1.0-release7
Private source main                    afed5e68d431b45bd5316d3bd456634d96b73e6b
Public distribution main               84e186448ea2afda4b09bbae578977721987146a
Runtime manifest blob                  43469d018a72f4e24ea3fd644ac7af5970a06c74
Final installer blob                   a3ffbdfb35ed201411bfa9463c8fea6e26702582
Toolbox expected Build                 0.1.0-release7
```

Machine / Distribution evidence：

```text
Exact-source full-menu Gate             36580337400 PASS
Release7 distribution Gate              36581173176 PASS
Toolbox Smoke                            36581172601 PASS
Runner Trigger Scope Gate                PASS
Runner Archive Integrity Gate            PASS
```

Production truth 仍保持独立：

```text
Production currently verified Slot 3 Build   0.1.0-release3
release7 Production install                  NOT_YET_OWNER_VERIFIED
Migration executed                           NO
DNS write                                    NO
SOURCE delete                                NO
Restore overwrite                            NO
Resource Safe Apply                          NO
```

Public Distribution 不得解释为 Production 已升级。


## 17. Slot 3 release8 Terminal UX System V2 distribution closure

2026-09-30，P07 普通终端交互进入 Terminal UX System V2。Owner 的真实反馈是：提示、上一级菜单、历史输出混在同一屏，虽然功能存在，但阅读层级混乱。

本轮把 Slot 3 普通用户主路径收敛为：

```text
清屏
→ 独立页面标题
→ 当前状态 / 当前对象
→ 主要内容
→ 下一步动作
→ 返回
```

已采用该页面模型的 Slot 3 入口：

```text
主菜单
服务器 / 网站概览
备份网站
恢复网站
服务器迁移
整机迁入
单站迁入
自动备份 / 远程灾备
网站管理
CloudPanel 管理
```

结果 / 空状态规则：

```text
成功结果 -> 独立结果页
失败结果 -> 独立错误页
无网站 / 无备份 / 无迁移任务 -> 独立空状态页
子模块异常 -> 不杀死 P07 主菜单
机器输出 / 非 TTY / --version / --build-id -> 保持稳定、无 ANSI / 无清屏副作用
```

Toolbox 顶层 Slot 1 / 2 / 3 / 4 在进入子模块前也会先清屏，避免 Toolbox 菜单残留与子模块内容混在一起。Slot 1 / Slot 4 自身已有重绘菜单；Slot 2 是一次性验机结果。本轮没有声称把 Slot 1 / Slot 4 的所有深层页面都重写成同一实现原语。

当前身份：

```text
P07 public product version             V0.1.0
Slot 3 Build                           0.1.0-release8
Private source main                    4ba15df96425bdba832ae80dd08dbfcb5dd19169
Public distribution main               70dd9d238ee6bd7bf1bd172a6e1acbf8ddbde576
Runtime manifest blob                  e7cee6c3614c00a51598f3ec2b4a57ccc9f344e4
Final installer blob                   73fff27c1d9ca6d8c757813723228680495b05fc
Stable installer blob                  fab78a8a5401a1ec84a31f296f37dc61857fe8f0
Toolbox blob                           23689f19140637058158c31b4864c7feea4821b0
```

Machine / Distribution evidence：

```text
Exact-source Terminal UX V2 Gate       36651107701 PASS
Release8 Distribution Gate             36651592677 PASS
Toolbox Smoke                           36651592618 PASS
Public Runner Scope Gate                PASS
Public Runner Archive Integrity Gate    PASS
```

旧 release6 / release7 / guided-init 身份型 workflow 在 release8 candidate 上可能因旧固定身份断言而失败；这不代表 release8 Runtime 行为失败。release8 owning exact-source 与 distribution Gate 已覆盖当前源码、Runtime manifest、页面隔离、Lazy Install、隔离安装、重复执行短路、机器输出和安全边界。

Production truth 仍独立：

```text
Production currently verified Slot 3 Build   0.1.0-release3
release8 Production install                  NOT_YET_OWNER_VERIFIED
Migration executed                           NO
DNS write                                    NO
SOURCE delete                                NO
Restore overwrite                            NO
Resource Safe Apply                          NO
```

Public Distribution 不得解释为 Production 已升级。


## 18. Slot 3 release9 Ops Console

2026-09-30：0.1.0-release9 已分发到 public main `e053b8a0c87034868f2e6aeb5a847b96acca8bae`。新增诊断中心、最近操作、P07 自检和新 VPS 初始化入口。Exact-source Gate `36654984844` PASS；Distribution Gate `36655669100` PASS。Production 仍以 Owner 已验证 release3 为准，release9 尚未正式机验收。


## 19. Slot 3 release10 小白化中文菜单

2026-09-30，Owner 真实 FinalShell 截图确认 P07 普通菜单仍有两个问题：

```text
1. Toolbox 主菜单把版本号与“可用”用手工空格拼在每一行，视觉错乱；
2. APT / systemd / Swap / OOM / SSH / SSL / Varnish / 2FA / Vhost / rclone 等工程词直接暴露给普通用户。
```

release10 建立 Beginner Chinese Menu Contract：

```text
菜单：只说“用户想做什么”
说明：必要时补充技术名词（括号）
详情 / 高级页：才保留工程词
```

Toolbox 主菜单改为：

```text
功能状态：4 项均可用

1. 网络代理节点（V2Ray）
2. 服务器性能检测（VPS 验机）
3. 网站备份 / 恢复 / 迁移（CloudPanel）
4. 系统维护 / 安全
0. 退出
```

不再在每行显示版本 / 可用列；版本进入对应功能后查看。

System Care 与 Slot 3 同步小白化：

```text
APT               -> 软件安装缓存 / 系统更新
systemd journal   -> 系统运行日志
Swap              -> 虚拟内存（Swap）
SSH               -> 远程登录（SSH）
SSL               -> HTTPS 证书
Varnish           -> 网站加速缓存（Varnish）
2FA               -> 两步验证（2FA）
Vhost             -> 网站配置模板（Vhost）
rclone            -> 异地备份组件（rclone）
VPS               -> 服务器（必要时括号保留 VPS）
```

Slot 3 普通菜单同时统一：

```text
服务器与网站概况
自动备份 / 异地备份
面板管理（CloudPanel）
新服务器初始化
HTTPS 证书状态
申请免费 HTTPS 证书（Let’s Encrypt）
网站加速缓存（Varnish）
面板登录安全
两步验证（2FA）
异地备份设置
远程连接与文件同步组件（SSH / rsync）
```

最后一次完整回归还发现“主菜单已改为服务器与网站概况，但页面标题仍为旧文案”，已作为真实遗漏修复，不以修改测试绕过。

当前身份：

```text
P07 public product version             V0.1.0
Slot 3 Build                           0.1.0-release10
Private source main                    90217676ca343b0a64de3d072d824ece17f6bad2
Public distribution main               0567d9cbfe8cd83cd3569f6bc37880bfca523cdd
Runtime manifest blob                  623d479a86aba977f98047c5edb1d42ebd12dbd0
Final installer blob                   9b3f168edf0e1dee2b79476dfddc709b76648d98
```

Machine / Distribution evidence：

```text
Release10 exact-source Gate            36677009690 PASS
Release10 Distribution Gate            36677155521 PASS
Toolbox Smoke                           36677155588 PASS
System Care Smoke                       36677155502 PASS
Beginner Menu Gate                      PASS
Runner Trigger Scope                    PASS
Archive Integrity                       PASS
```

Production truth 保持独立：

```text
Production currently verified Slot 3 Build   0.1.0-release3
release10 Production install                 NOT_YET_OWNER_VERIFIED
Migration executed                           NO
DNS write                                    NO
SOURCE delete                                NO
Restore overwrite                            NO
Resource Safe Apply                          NO
```

Public Distribution 不得解释为 Production 已升级。


## 20. release11 菜单 3 / 4 重构与恢复可靠性

Owner 真实 FinalShell 验证暴露出四类问题：网站概况工程信息过多且出现 ANSI 转义文本；刚创建的备份在恢复前 fresh verification 失败；P07 自检错误要求不存在于运行包的 Authority 文档；菜单 3 混入诊断、自检、初始化等服务器运维能力。

release11 固化两条用户主线：

```text
主菜单 3 = 网站与数据
主菜单 4 = 服务器维护 / 安全
```

菜单 3：

```text
1. 网站与服务器概况
2. 备份与恢复
3. 服务器迁移
4. 网站管理
5. 面板管理（CloudPanel）
0. 返回
```

菜单 4：

```text
1. 服务器体检
2. 日常维护
3. 安全检查
4. 新服务器初始化
5. P07 检查 / 修复
6. 最近操作
0. 返回
```

恢复可靠性修复：

```text
- 备份 metadata 不再保留指向源服务器实时文件的外部 symlink；
- 包写入 / fresh verify 对外部 symlink fail closed；
- 恢复列表只展示当前仍通过 fresh verification 的备份；
- 恢复失败默认中文解释，不直接把 Python / CloudPanel 工程异常原文扔给普通用户；
- 自检只验证实际安装运行文件，不再把 docs/authority/P07_INTEGRATION_MANIFEST.json 当 Runtime 必需文件；
- 修复确认改为中文“修复”，不再要求输入 REPAIR。
```

当前身份：

```text
Slot 3 Build                           0.1.0-release11
Slot 4 System Care                     0.1.0-rc18
Private source main                    9e4df79c2c6918d6d61d7413b1e856ddb162bcda
Public distribution main               3f5210fc8c4123fe168298d6a85abfc47845ecf0
Runtime manifest blob                  6cdba91349d0f4659f06ddb89b5a30d86273ef38
Final installer blob                   54680a674367dfb32a434c267bb5f19eedee0af7
Stable installer blob                  8da410897f11b47330653f82b11a0769ad8cdfc8
Toolbox blob                           c5bad778f56e9f43ad083f25abeedbdc3c277fe2
```

Evidence：

```text
Release11 exact-source Gate            36684513855 PASS
Release11 Distribution Gate            36686124730 PASS
Toolbox Smoke                           36686124599 PASS
System Care Smoke                       36686124872 PASS
Beginner Menu Gate                      PASS
Runner Trigger Scope                    PASS
Archive Integrity                       PASS
```

旧 release6/7/8/9/10 Distribution workflows 对 release11 失败属于历史固定身份工作流，不作为 release11 owning Gate。

Production truth 仍独立：

```text
Production verified Slot 3 Build        0.1.0-release3
release11 Production install            NOT_YET_OWNER_VERIFIED
Production System Care                  0.1.0-rc15
Migration executed                      NO
DNS write                               NO
SOURCE delete                           NO
Restore overwrite                       NO
Resource Safe Apply                     NO
```

## Slot 3 release12 备份新鲜度 / 恢复可见性 distribution closure

2026-09-30 的 OWNER 真实服务器使用暴露了一个 release11-era 备份/恢复缺口：刚创建的 `123.kewaro.com` 备份在界面中显示“已验证，可恢复”，但紧接着进入恢复列表时没有被列出。该真实会话没有独立回读当时已安装的内部 Build，因此此证据只证明产品行为失败，不反向修改 Production 的 exact Build identity。

release12 将该失败收敛为 B44：

```text
MySQL 导出结束
→ 等待导出文件无外部写入且稳定
→ 完整读取 gzip
→ 写入 checksum
→ staging verify
→ atomic commit
→ final fresh verify
→ 成功后才允许显示“已验证，可恢复”
```

恢复列表不再吞掉 fresh verification 异常并伪装成“没有备份”；不能恢复的本地备份会保持 fail-closed，并用中文显示阻断原因。与此同时，`lib/inventory.py` 被正式加入 Runtime manifest，避免基础包旧 renderer 继续显示 CloudPanel CLI 的整段工程输出；当前解析只显示版本号，例如 `6.0.8`。

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release12
Exact runtime source merge            e4a72657cc87ff970012c7e89adf4ba143cd0a44
Public distribution main              ec8d2587c411b36178c12160960a8ea3bf62cf6c
Runtime manifest blob                 5a278aec6d9a49c257589f762d8abeb09847f990
Full overlay manifest blob            d743dc37bf6d7fd5649513b24372d30f205a0400
Final installer blob                  61ef13cd9de032000c5da1ad496429f03b72cf09
Stable installer blob                 cfb88ff2491dc9fb606e087256dab502d0f285a7
Toolbox blob                          121dbebdf9c3e85577be0a279c00b177012e8475
Inventory runtime blob                fe988adcbe76d31c1f13dfb0dade4443868f9210
```

Machine / Distribution proof：

```text
Release12 Exact-source Gate           36699115238 PASS
Release12 Distribution Gate           36701825127 PASS
Toolbox Smoke                         36701825096 PASS
System Care Smoke                     36701825068 PASS
Beginner Menu Gate                    36701825112 PASS
Public Runner Trigger Scope           36701825010 PASS
Workflow Archive Integrity            36701825140 PASS
```

Release12 Distribution Gate 还在隔离路径证明：

```text
focused backup / restore regressions  PASS
isolated current-runtime install      PASS
second install short-circuit          PASS
inventory.py installed by Runtime     PASS
CloudPanel long CLI output → 6.0.8    PASS
DNS / SOURCE delete / overwrite       NOT_RUN
Production write                      NOT_RUN
```

Current Production truth 不由 Public Distribution 推导：

```text
Production exact verified Slot 3 Build  0.1.0-release3
release12 Production install            NOT_YET_OWNER_VERIFIED
release12 Owner Real Use                PENDING
Migration executed                      NO
DNS write                               NO
SOURCE delete                           NO
Restore overwrite                       NO
Resource Safe Apply                     NO
```

OWNER 后续通过永久一行 Toolbox 路由升级后，需要用**新创建的备份**重新验证“立即备份 → 立即进入恢复列表 → 可选中备份 → 受控恢复”的 Real path。旧失败备份不能替代 release12 Real proof。

## Slot 3 release13 source closure · Public Distribution pending

2026-09-30，OWNER 在永久 Toolbox 路径重新创建 `123.kewaro.com` 备份时，release12 真实服务器仍在备份阶段 fail closed：

```text
备份完整性检查没有通过
阶段：BACKUP
原因代码：FRESH_VERIFY_NOT_PASS
原网站未修改
```

该证据把 release12 的 Owner Real Use 判定为 **REAL_FAIL**；由于截图没有独立显示 `--build-id` 回读，Production exact installed Build 不从该截图反推，原已验证 Production identity 继续保持 release3。

release13 源码修复：

```text
CloudPanel export path
→ external work file only
→ true detached-writer settle observation
→ full gzip read
→ separate P07-owned snapshot
→ fsync
→ source/snapshot digest equality
→ checksum only immutable snapshot
→ staging verify
→ atomic commit
→ final fresh verify
```

同时普通错误页把机器 token 转成中文：

```text
BACKUP                 → 备份
FRESH_VERIFY_NOT_PASS  → 备份最终完整性复检没有通过
MYSQL_SNAPSHOT_CHANGED → MySQL 数据库导出在封存时仍发生变化
```

Exact source evidence：

```text
Slot 3 source Build                  0.1.0-release13
Private source main merge            d7cdcd45370bc0a177b4b2dceec38e95a67a3824
Release13 Exact-source Gate          36705735350 PASS
Detached delayed atomic replace      PASS
Focused backup regressions           PASS
Chinese diagnostic regression        PASS
Secret / DNS / delete boundary       PASS
```

当前阶段严格保持：

```text
release13 Private Source             MERGED
release13 Public Distribution        NOT_RUN
release13 Production install         NOT_RUN
release13 Owner Real Use             NOT_RUN
Migration / DNS / SOURCE delete      NOT_RUN
Restore overwrite                    NOT_RUN
```

因此 release13 现在是 **Source Ready**，但永久一行 Toolbox 仍指向 public main 的 release12；只有经过单独 Public Distribution Gate 后，OWNER 才能在真实服务器测试 release13。

## Slot 3 release13 immutable MySQL snapshot distribution closure

release13 已完成 Public Distribution，用来收敛 release12 在 OWNER 真实服务器上的备份阶段失败。release12 的真实失败仍保留为 Real evidence；Machine PASS 不覆盖它。

release13 的核心修复不是继续延长等待时间，而是把 CloudPanel 导出路径降级为外部工作文件：

```text
CloudPanel export work path
→ settle + no-open-writer observation
→ full gzip read
→ copy to separate P07-owned snapshot
→ fsync
→ observe source again
→ source/snapshot digest equality
→ checksum only P07-owned snapshot
→ staging verify
→ atomic commit
→ final fresh verify
```

普通用户诊断同时改为中文阶段 / 中文原因，不再要求理解 `BACKUP`、`FRESH_VERIFY_NOT_PASS`、`MYSQL_SNAPSHOT_CHANGED`。

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release13
Exact runtime source merge            d7cdcd45370bc0a177b4b2dceec38e95a67a3824
Public distribution main              cc94582ff03766820e489eb03bfa4f12b343142c
Runtime manifest blob                 2a3bb3dee14e6236138a86e271dac74df81f17eb
Full overlay manifest blob            24d2dd09d04e6330a73ec28d928ef9e435a94984
Final installer blob                  e62cbde514c77270fc75ed9c72d6752776092a36
Stable installer blob                 1eebe7cd4e8146b38fc056be76501b398a29c078
Toolbox blob                          011ce3b7e1d7de6a94d036f49c137530a96f7b86
```

Machine / Distribution proof：

```text
Release13 Exact-source Gate           36705735350 PASS
Release13 Distribution Gate           36707407078 PASS
Toolbox Smoke                         36707407264 PASS
System Care Smoke                     36707407171 PASS
Beginner Menu Gate                    36707407121 PASS
Public Runner Trigger Scope           36707407236 PASS
Workflow Archive Integrity            36707407314 PASS
```

Distribution Gate 还证明：

```text
Public overlay focused regressions    PASS
detached delayed atomic replace       PASS
isolated release13 runtime install    PASS
second install short-circuit          PASS
beginner Chinese diagnostics          PASS
DNS / SOURCE delete / overwrite       NOT_RUN
Production write                      NOT_RUN
```

Current Production truth 继续独立：

```text
Production exact verified Slot 3 Build  0.1.0-release3
release12 Owner real backup path        REAL_FAIL / FRESH_VERIFY_NOT_PASS
release13 Production install            NOT_YET_OWNER_VERIFIED
release13 Owner Real Use                PENDING
Migration executed                      NO
DNS write                               NO
SOURCE delete                           NO
Restore overwrite                       NO
Resource Safe Apply                     NO
```

下一次 OWNER 运行永久 Toolbox 后，必须用**新创建的备份**验证 release13 的真实链路。旧失败备份和 Machine PASS 都不能替代 release13 Owner Real Use。

## Slot 3 release14 source closure · Public Distribution pending

2026-09-30，OWNER 在 release13 Public Runtime 上再次创建 `123.kewaro.com` 备份，仍在最终完整性复检阶段 fail closed。与 release12 相比，release13 的中文诊断已生效，但原因仍被归为泛化的“备份最终完整性复检没有通过”。

因此 release14 不再继续猜测 MySQL，而是同时收敛两件事：

```text
1. post-commit final verify 使用 bounded stability window；
2. 最终失败必须归类到具体组件并显示中文原因。
```

稳定复检规则：

```text
atomic commit
→ full verify
→ full verify
→ 连续 PASS >= 2
→ 才允许“已验证，可恢复”
```

持续失败仍然 fail closed；分类至少覆盖 MySQL、SQLite、网站压缩包、metadata、manifest、checksum index、external link 与其它 package file change。

Exact source evidence：

```text
Slot 3 source Build                  0.1.0-release14
Private source main merge            1dd186ef9786cd538d8c55c329f9857aa6dca240
Release14 Exact-source Gate          36708781490 PASS
Focused regressions                  PASS
Stable verifier fail-closed          PASS
Exact Chinese diagnosis              PASS
Secret / DNS / delete boundary       PASS
```

当前阶段：

```text
release13 Owner Real Use             REAL_FAIL / FINAL_VERIFY_NOT_PASS
release14 Private Source             MERGED
release14 Public Distribution        NOT_RUN
release14 Production install         NOT_RUN
release14 Owner Real Use             NOT_RUN
Migration / DNS / SOURCE delete      NOT_RUN
Restore overwrite                    NOT_RUN
```

因此永久一行 Toolbox 目前仍是 Public release13；只有单独完成 release14 Public Distribution Gate 后，OWNER 才能测试 release14。

## Slot 3 release14 stable final verification distribution closure

release14 已完成 Public Distribution，用来收敛 release13 在 OWNER 真实服务器上的最终完整性复检失败。release13 的真实失败继续保留为 Real evidence；Machine PASS 不覆盖它。

release14 的核心合同：

```text
atomic commit
→ full verify
→ full verify
→ 连续 PASS >= 2
→ 才允许“已验证，可恢复”
```

若最终仍失败，必须 fail closed，并将原因归类到固定安全类别：MySQL、SQLite、网站压缩包、metadata、manifest、checksum index、external link 或其它 package file change。普通用户只看到中文原因，不要求理解机器 token。

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release14
Exact runtime source merge            1dd186ef9786cd538d8c55c329f9857aa6dca240
Public distribution main              32d53b8350145f6a229211cc96ea591b1b8045da
Runtime manifest blob                 e437d91b0ba6f257464659b50858e96a099184ce
Full overlay manifest blob            543d50ee7eb6bd1870e3fbe007e875132b0d9852
Final installer blob                  28c92ee9abb0cb36f190567fde2de4fe36305521
Stable installer blob                 1d3e0dfc2b0ac97afd677fc2109006d193175dc0
Toolbox blob                          3b3e445cb86e15db29f203b447064a522224ddb7
```

Machine / Distribution proof：

```text
Release14 Exact-source Gate           36708781490 PASS
Release14 Distribution Gate           36710551712 PASS
Toolbox Smoke                         36710551825 PASS
System Care Smoke                     36710551566 PASS
Beginner Menu Gate                    36710551659 PASS
Public Runner Trigger Scope           36710551743 PASS
Workflow Archive Integrity            36710551623 PASS
```

Distribution Gate 还证明：

```text
Public overlay focused regressions    PASS
stable final verifier                 PASS
persistent failure fail-closed        PASS
component-level Chinese diagnosis     PASS
isolated release14 runtime install    PASS
second install short-circuit          PASS
DNS / SOURCE delete / overwrite       NOT_RUN
Production write                      NOT_RUN
```

Current Production truth 继续独立：

```text
Production exact verified Slot 3 Build  0.1.0-release3
release13 Owner real backup path        REAL_FAIL / FINAL_VERIFY_NOT_PASS
release14 Production install            NOT_YET_OWNER_VERIFIED
release14 Owner Real Use                PENDING
Migration executed                      NO
DNS write                               NO
SOURCE delete                           NO
Restore overwrite                       NO
Resource Safe Apply                     NO
```

下一次 OWNER 通过永久一行 Toolbox 进入 Slot 3 后，必须用**新创建的备份**验证 release14 的真实链路；如果仍失败，界面应给出具体组件级中文原因。旧失败备份与 Machine PASS 都不能替代 release14 Owner Real Use。

## Slot 3 release15 SQLite WAL source closure · Public Distribution pending

2026-09-30，OWNER 在真实服务器明确回读安装结果：

```text
构建：0.1.0-release14
```

因此 Production exact installed Slot 3 Build 从旧的 release3 更新为 **0.1.0-release14**。同一真实会话随后对 `123.kewaro.com` 执行新备份，release14 fail closed：

```text
阶段：备份
原因：SQLite 数据库备份完整性检查失败，P07 已停止使用这个备份。
```

这证明 release14 的组件级中文诊断已生效，也把真实失败点钉到 SQLite verification。

代码根因：旧 verifier 用 `sqlite/*.glob("*")` 把目录内所有文件都当独立 SQLite 数据库；WAL 模式快照校验可能出现 `-wal` / `-shm` / `-journal` 辅助文件，后续 fresh verify 会把这些辅助文件错误当成数据库执行 `PRAGMA integrity_check`。

release15 固化：

```text
live WAL SQLite
→ SQLite Backup API
→ destination commit
→ journal_mode = DELETE
→ integrity_check
→ close
→ remove destination -wal / -shm / -journal
→ checksum
→ manifest-declared snapshot only
→ immutable read-only integrity_check
```

并且 `sqlite/` 中任何未登记普通文件都会 fail closed，不再被误当数据库。

Exact source evidence：

```text
Slot 3 source Build                  0.1.0-release15
Private source main merge            63e1ebdb0ce043bcb65ec06dbadc9ee69f162954
Release15 Exact-source Gate          36724452422 PASS
WAL source snapshot regression        PASS
Manifest-only SQLite verification     PASS
Undeclared WAL/SHM fail-closed        PASS
Beginner Chinese diagnosis            PASS
Secret / DNS / delete boundary        PASS
```

当前阶段：

```text
Production exact installed Slot 3    0.1.0-release14
release14 Owner Real Use             REAL_FAIL / SQLITE_INTEGRITY
release15 Private Source             MERGED
release15 Public Distribution        NOT_RUN
release15 Production install         NOT_RUN
release15 Owner Real Use             NOT_RUN
Migration / DNS / SOURCE delete      NOT_RUN
Restore overwrite                    NOT_RUN
```

因此永久一行 Toolbox 当前仍为 Public release14；只有单独完成 release15 Public Distribution Gate 后，OWNER 才能测试 release15。

## Slot 3 release15 SQLite WAL verification distribution closure

release15 已完成 Public Distribution，用来收敛 release14 在 OWNER 真实服务器上的 SQLite 完整性失败。release14 的真实失败继续保留为 Real evidence；Machine PASS 不覆盖它。

release15 的核心合同：

```text
live SQLite（可能 WAL）
→ SQLite Backup API
→ destination commit
→ journal_mode = DELETE
→ integrity_check
→ close
→ remove destination -wal / -shm / -journal
→ checksum
→ manifest-declared SQLite snapshot only
→ immutable read-only integrity_check
```

额外 fail-closed：

```text
sqlite/ 中出现未登记普通文件
→ FAIL
→ 中文提示“SQLite 备份目录出现未登记的辅助文件”
```

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release15
Exact runtime source merge            63e1ebdb0ce043bcb65ec06dbadc9ee69f162954
Public distribution main              75ffa26993d79e0d9768c2d0ef13fe42c9ffda25
Runtime manifest blob                 eb0d6635e846a19822b354fd114e7c8a74d4fac6
Full overlay manifest blob            9fba2e9207831df97df60a9dd3452fe25c1aa70d
Final installer blob                  29009fcf49fd79458e391103bbe8be1a868c4c4b
Stable installer blob                 5c35e9e05a0f99e559e79c930e118761e07d3d04
Toolbox blob                          1860eeea3b939c8ca5a475af20c2ef295542ce75
```

Machine / Distribution proof：

```text
Release15 Exact-source Gate           36724452422 PASS
Release15 Distribution Gate           36726942820 PASS
Toolbox Smoke                         36726942702 PASS
System Care Smoke                     36726942525 PASS
Beginner Menu Gate                    36726943008 PASS
Public Runner Trigger Scope           36726942502 PASS
Workflow Archive Integrity            36726942585 PASS
```

Distribution Gate 还证明：

```text
Public overlay WAL-source regression   PASS
manifest-only SQLite verification      PASS
undeclared WAL/SHM fail-closed         PASS
isolated release15 runtime install     PASS
beginner Chinese diagnosis             PASS
second install short-circuit           PASS
DNS / SOURCE delete / overwrite        NOT_RUN
Production write                       NOT_RUN
```

说明：历史 release6/7/8/9/10/11/12/13/14 和旧 Stable/R2 Gate 中仍有硬编码旧 Build 的 Workflow，在 release15 PR 上出现身份失败属于 workflow archive debt，不作为 release15 owning evidence。release15 owning Gate 与当前通用 Toolbox / System Care / Beginner Menu / Runner Scope / Archive Integrity 均已 PASS。

Current Production truth 继续独立：

```text
Production exact installed Slot 3 Build  0.1.0-release14
release14 Owner real backup path         REAL_FAIL / SQLITE_INTEGRITY
release15 Production install             NOT_YET_OWNER_VERIFIED
release15 Owner Real Use                 PENDING
Migration executed                       NO
DNS write                                NO
SOURCE delete                            NO
Restore overwrite                        NO
Resource Safe Apply                      NO
```

下一次 OWNER 通过永久一行 Toolbox 进入 Slot 3 后，必须用**新创建的备份**验证 release15 的真实链路。只有新备份成功通过验证并出现在恢复列表，才能推进真正恢复测试。

## Slot 3 release15 Owner Real Backup PASS · Restore list next

2026-10-01，OWNER 在真实 DigitalOcean / CloudPanel 服务器上通过永久 Toolbox 路径新建 `123.kewaro.com` 备份，终端截图显示：

```text
P07 · 备份完成
已创建并通过恢复校验

备份完成 ✓
网站：123.kewaro.com
大小：2.7M
状态：已验证，可恢复
位置：/var/backups/vf-server-ops/123.kewaro.com_20261001T024818Z
DNS：未修改 · 源服务器：保留
```

这证明 release15 分发之后的真实备份链已经从 release14 的 SQLite integrity fail 推进到：

```text
OWNER_REAL_BACKUP = PASS
BACKUP_CREATED = YES
FRESH_VERIFY = PASS
RECOVERABLE_FLAG = YES
DNS_WRITE = NO
SOURCE_DELETE = NO
```

但本张截图没有同时显示 `--build-id` / 安装页，因此不单凭该截图把 Production exact installed Build 从已证实的 release14 改写成 release15。release15 安装身份仍需同一真实会话中的独立 Build 回读，或后续截图证据。

下一步仅验证：

```text
备份与恢复
→ 从备份恢复网站
→ 新备份必须出现在恢复列表
```

只有恢复列表 PASS 后，才进入单独高风险 Restore-As-New Real Gate；不得直接覆盖现有网站。

## Slot 3 release16 Restore-As SQLite source closure · Public Distribution pending

2026-10-01，OWNER 使用新备份 `123.kewaro.com_20261001T024818Z` 进入恢复流程：

```text
恢复列表：
1. 123.kewaro.com (2026-10-01T02:48:18+00:00)
另外有 2 个旧备份未通过当前复检，已禁止恢复。
```

因此：

```text
RESTORE_LIST = PASS
OLD_INVALID_BACKUPS = FAIL_CLOSED
```

随后 OWNER 选择“恢复为新网站”，输入 `455.kewaro.com` 并显式确认真实 Restore-As 写入。P07 创建 / 恢复 / 自动验证过程中 fail closed：

```text
Restore-As-New = REAL_FAIL
SOURCE = retained / unchanged
DNS = unchanged
existing source overwrite = NO
```

截图没有给出内部 failure stage，也没有独立证明新目标清理结果，因此不虚报 target cleanup PASS。

源码核对发现 Restore-As 与成熟 sandbox 恢复路径不一致：

```text
backup files/site.tar.gz = 整站 broad archive，可能包含 live SQLite + WAL/SHM
backup sqlite/           = SQLite Backup API 生成的 canonical consistent snapshot

旧 Restore-As：
extract broad archive
→ 直接 verify archived SQLite against canonical snapshot
→ WAL/live bytes 可能不一致
→ fail

sandbox path：
extract broad archive
→ restore canonical sqlite snapshot
→ verify
```

release16 将 Restore-As 统一到正确顺序：

```text
extract broad site archive
→ restore manifest-declared canonical SQLite snapshots
→ remove archived -wal / -shm / -journal
→ regular-file verify excludes SQLite main + sidecars
→ immutable SQLite verify
→ MySQL / config remap / ownership / atomic commit
→ local Host / SNI verify
```

同时 Restore-As 错误页保留固定中文阶段，例如 CloudPanel 建站、SQLite 快照恢复、文件验证、MySQL、应用配置改写、原子提交、WordPress 域名、权限、本机 Host / SNI；不向普通用户输出原始 stderr / secret。

Exact source evidence：

```text
Slot 3 source Build                    0.1.0-release16
Private source main merge              bb5b92f2b6cfa2bd63a6dcca3d837f34bfb0ef88
Release16 Exact-source Gate            36808626280 PASS
Archived stale SQLite/WAL regression   PASS
Canonical snapshot restore ordering    PASS
Restore-As focused regressions         PASS
Bounded site UI                        PASS
Secret / DNS / source safety           PASS
```

当前阶段：

```text
Current Public Distribution            0.1.0-release15
Production exact independently proven  0.1.0-release14
release15-era backup                    PASS
release15-era restore list              PASS
release15-era Restore-As-New            REAL_FAIL
release16 Private Source                MERGED
release16 Public Distribution           NOT_RUN
release16 Production install            NOT_RUN
release16 Owner Real Use                NOT_RUN
Migration / DNS / SOURCE delete         NOT_RUN
Existing target overwrite               NOT_RUN
```

只有单独完成 release16 Public Distribution Gate 后，OWNER 才应再次创建 / 选择已验证备份并测试 Restore-As-New。恢复属于高风险独立 Gate，不从 Source/Machine PASS 自动推进。

## Slot 3 release16 Restore-As canonical SQLite distribution closure

release16 已完成 Public Distribution，用来收敛 OWNER 在 release15-era 真实恢复链中暴露的 Restore-As-New fail-closed 问题。release15-era 的真实恢复失败继续保留为 Real evidence；Machine PASS 不覆盖它。

release16 固定 Restore-As SQLite 真相来源：

```text
files/site.tar.gz = broad site archive，可能包含 live SQLite / WAL / SHM
sqlite/            = manifest-declared canonical SQLite snapshots

Restore-As:
extract broad site archive
→ restore canonical SQLite snapshots
→ remove archived -wal / -shm / -journal
→ regular-file verification excludes SQLite main + sidecars
→ immutable SQLite integrity verification
→ MySQL / application config remap / ownership / atomic commit
→ local Host / SNI verification
```

普通错误页同时改为安全中文阶段，不再把真实 `stage=...` 丢成一句泛化错误。阶段至少覆盖 CloudPanel 建站、网站文件、SQLite 快照、文件/SQLite 校验、MySQL、应用配置改写、权限、原子提交、WordPress 域名以及本机 Host / SNI 验证。

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release16
Exact runtime source merge            bb5b92f2b6cfa2bd63a6dcca3d837f34bfb0ef88
Public distribution main              850e41b8aeb4d58f930e5e0f9ba432840c8f962e
Runtime manifest blob                 3461782c9326bd599e841fa437477dabeb472f4c
Full overlay manifest blob            e71740c9614f500351b3375b35c7c870794e9217
Final installer blob                  867e5d99ba2eb6241caaafb94dc43753644cc2e4
Stable installer blob                 36d47f187d45a0f2129afc87a3717994466a5182
Toolbox blob                          ca80a5d82c91f4adc757e69cc3c10f9731a816c4
```

Machine / Distribution proof：

```text
Release16 Exact-source Gate           36808626280 PASS
Release16 Distribution Gate           36809546508 PASS
Toolbox Smoke                         36809546788 PASS
System Care Smoke                     36809546554 PASS
Beginner Menu Gate                    36809546704 PASS
Public Runner Trigger Scope           36809546481 PASS
Workflow Archive Integrity            36809546609 PASS
```

Distribution Gate 还证明：

```text
public overlay Restore-As regressions  PASS
archived stale SQLite/WAL regression   PASS
canonical SQLite restore ordering      PASS
isolated release16 runtime install     PASS
restore_failure_ui runtime presence    PASS
beginner Chinese failure-stage UI      PASS
DNS / SOURCE delete / overwrite        NOT_RUN
Production write                       NOT_RUN
```

说明：旧 Stable Installer Smoke / Final Distribution + R2 Onboarding 仍硬编码 release5，因此在 release16 PR 上的 identity failure 属于历史 workflow debt，不作为 release16 owning evidence。

Current Production truth 继续独立：

```text
Production exact independently proven Slot 3 Build  0.1.0-release14
release15-era new backup                         PASS
release15-era restore list                       PASS
release15-era Restore-As-New                     REAL_FAIL
release16 Production install                     NOT_YET_OWNER_VERIFIED
release16 Owner Real Use                         PENDING
Migration executed                               NO
DNS write                                        NO
SOURCE delete                                    NO
Existing target overwrite                        NO
Resource Safe Apply                              NO
```

下一次 OWNER 通过永久一行 Toolbox 进入 Slot 3 后，先确认 Build 已升级到 release16，再使用已验证备份测试“恢复为新网站”。Restore 仍是独立高风险 Gate；Public Distribution 不等于 Production Restore PASS。

## Slot 3 release17 local HTTP probe source closure · Public Distribution pending

2026-10-01，OWNER 在 release16 Public Distribution 之后继续真实 Restore-As-New 测试，目标域名为 `111.kewaro.com`。终端截图显示恢复主体已推进到最终本机验证阶段，但 HTTP 路由探针失败，P07 按 fail-closed 规则回滚新目标：

```text
新网站已恢复，但本机 HTTP 路由验证没有通过，P07 已回滚新目标。
DNS 没有修改，原网站没有修改。
域名解析：未修改 · 原网站：保留
```

因此本轮真实证据分类为：

```text
Restore-As core restore path       reached local verification
Local HTTP verification           REAL_FAIL
New target retained               NO / rollback path invoked
DNS write                         NO
SOURCE mutation                   NO
```

该截图没有单独显示 `--build-id`，因此不把 Production exact installed Build 从已独立证明的 release14 直接改写为 release16；只记录为 release16 Public Distribution 后的真实 Restore-As 证据。

源码核对发现本机 HTTP/SNI probe 仍有两个真机缺口：

```text
1. curl 继承服务器代理环境，未强制本机直连；
2. CloudPanel / Nginx 新站点创建后只探测一次，没有 bounded reload retry。
```

release17 固化：

```text
curl --noproxy "*"
+ --resolve target:port:127.0.0.1
+ bounded retry
+ accept any real HTTP status 100..599
+ final failure classify target_vhost=PRESENT / MISSING
+ failure still rolls back new target
```

Exact source evidence：

```text
Slot 3 source Build                  0.1.0-release17
Private source main merge            3b115516f52f61d535606d89fefbb9877afbf3ef
Release17 Exact-source Gate          36810512935 PASS
Direct no-proxy loopback regression  PASS
Transient retry regression           PASS
vhost PRESENT/MISSING classification PASS
Restore-As regressions               PASS
Rollback / DNS / SOURCE safety       PASS
```

当前阶段：

```text
Current Public Distribution          0.1.0-release16
Production exact independently proven 0.1.0-release14
release16-era Restore-As             REAL_FAIL / LOCAL_HTTP_ROUTE
release17 Private Source             MERGED
release17 Public Distribution        NOT_RUN
release17 Production install         NOT_RUN
release17 Owner Real Use             NOT_RUN
Migration / DNS / SOURCE delete      NOT_RUN
Existing target overwrite            NOT_RUN
```

## Slot 3 release17 local HTTP probe distribution closure

release17 已完成 Public Distribution，用来收敛 OWNER 在 release16-era 真实 Restore-As 中暴露的最终本机 HTTP 路由验证失败。release16-era 的真实失败继续保留为 Real evidence；Machine PASS 不覆盖它。

release17 固化本机验证：

```text
curl --noproxy "*"
+ --resolve target:port:127.0.0.1
+ bounded retry
+ accept any real HTTP status 100..599
+ final failure classify target_vhost=PRESENT / MISSING
+ failure still rolls back new target
```

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release17
Exact runtime source merge            3b115516f52f61d535606d89fefbb9877afbf3ef
Public distribution main              7240858005bc29bb4a705a95ab1e8126862c940c
Runtime manifest blob                 a783b1cbdb9473ea73cf263d0a7b2b798c9c8b3d
Full overlay manifest blob            40f8d364c92a25ebcddf70146a32e1d980b6c311
Final installer blob                  d988fcb80e1c196254d0e8a1ae66f2244ea64867
Stable installer blob                 12fcc03c7818487b1c19be0fd096e0b49ae6f71c
Toolbox blob                          b1928d11294b7103d6ae9ab44051812f45d49f51
```

Machine / Distribution proof：

```text
Release17 Exact-source Gate           36810512935 PASS
Release17 Distribution Gate           36811305606 PASS
Toolbox Smoke                         36811305815 PASS
System Care Smoke                     36811305720 PASS
Beginner Menu Gate                    36811305588 PASS
Public Runner Trigger Scope           36811305755 PASS
Workflow Archive Integrity            36811305608 PASS
```

Distribution Gate 还证明：

```text
Public overlay release17 regressions  PASS
direct no-proxy loopback probe        PASS
bounded retry                         PASS
target vhost classification           PASS
isolated release17 runtime install    PASS
beginner Chinese failure rendering    PASS
rollback / DNS / SOURCE safety        PASS
Production write                      NOT_RUN
```

说明：旧 Stable Installer Smoke 仍硬编码检查 `0.1.0-release5`，因此在 release17 PR 上 identity failure 属于历史 workflow debt，不作为 release17 owning evidence。

Current Production truth 继续独立：

```text
Production exact independently proven Slot 3 Build  0.1.0-release14
release16-era Restore-As                        REAL_FAIL / LOCAL_HTTP_ROUTE
release17 Production install                    NOT_YET_OWNER_VERIFIED
release17 Owner Real Use                        PENDING
Migration executed                              NO
DNS write                                       NO
SOURCE delete                                   NO
Existing target overwrite                       NO
Resource Safe Apply                             NO
```

下一次 OWNER 通过永久一行 Toolbox 进入 Slot 3 后，先确认 Build 已升级到 release17，再用全新目标域名继续 Restore-As-New 真机验证。Public Distribution 不等于 Production Restore PASS。

## Slot 3 release18 Nginx listener-aware source closure · Public Distribution pending

2026-10-01，OWNER 在 release17 Public Distribution 后继续真实 Restore-As-New，目标域名为 `112.kewaro.com`。release17 新诊断明确证明：

```text
target vhost                  PRESENT
fixed loopback HTTP probe     FAIL
new target rollback           invoked
DNS write                     NO
SOURCE mutation               NO
```

终端普通用户信息为：

```text
新网站已恢复，Nginx 也已有新站点配置，但本机 HTTP 直连暂未响应，P07 已回滚新目标。
DNS 没有修改，原网站没有修改。
```

因此 release17 已把问题从 backup / SQLite / MySQL / config / vhost creation 收敛到最终本机 listener probe。截图仍未单独显示 exact installed Build，因此 Production exact installed Build 继续只保留已独立证明的 release14，不从聊天推断 release17 installed PASS。

release18 不再固定假设 `127.0.0.1:80/443` 是目标 Nginx 实际监听入口，改为：

```text
nginx -T
→ parse only target-domain server blocks
→ derive target-domain listen directives
→ listen 80 / 0.0.0.0:80 -> 127.0.0.1
→ listen [::]:80             -> ::1
→ explicit IP:80             -> exact configured IP
→ curl --noproxy "*"
→ --resolve target:port:<listener>
→ bounded per-listener retry
→ any real HTTP 100..599 = PASS
```

Fail-closed 分类：

```text
target vhost missing                 -> target_vhost=MISSING
target vhost present / no port 80    -> target_listener=MISSING
target listeners found / all fail    -> target_listener=UNREACHABLE
```

Exact source evidence：

```text
Slot 3 source Build                     0.1.0-release18
Private source main merge               26e9235edd92d34d4837abe3a1876a8d78a2e555
Release18 Exact-source Gate             36812999690 PASS
Target-only server-block parsing        PASS
Wildcard IPv4 / IPv6 listener mapping   PASS
Explicit listener-IP mapping            PASS
Cross-site listener isolation           PASS
Multi-listener probing                  PASS
Restore-As / SQLite regressions         PASS
Rollback / DNS / SOURCE safety          PASS
```

当前阶段：

```text
Current Public Distribution             0.1.0-release17
Production exact independently proven   0.1.0-release14
release17-era Restore-As                 REAL_FAIL / VHOST_PRESENT / FIXED_LOOPBACK_HTTP_FAIL
release18 Private Source                 MERGED
release18 Public Distribution            NOT_RUN
release18 Production install             NOT_RUN
release18 Owner Real Use                 NOT_RUN
Migration / DNS / SOURCE delete          NOT_RUN
Existing target overwrite                NOT_RUN
```

release18 必须单独完成 Public Distribution Gate 后，OWNER 才继续新的 Restore-As 真机验证。

## Slot 3 release18 Nginx listener-aware distribution closure

release18 已完成 Public Distribution。它针对 release17-era 真机证据中“目标 vhost 已存在，但固定 127.0.0.1 HTTP 探针失败”的问题，把最终本机验证改为读取目标域名自己的 Nginx `listen`。

Exact identities：

```text
Slot 3 Build                          0.1.0-release18
Exact runtime source merge            26e9235edd92d34d4837abe3a1876a8d78a2e555
Public distribution main              f618aad35da7df05fb298455be186691d4b5362b
Runtime manifest blob                 a7ae163c8c6ddbe402ad04797098e321d8f42e64
Full overlay manifest blob            4cce8bcf9b91452359dba6c5175f8fc1582ed6fe
Final installer blob                  3e5e6bf4cfbbf1232d3a28f9696efb29430d234c
Stable installer blob                 e5c38062d6c4d821e303c4caebfb103c6517d085
Toolbox blob                          143e5fbc28adfa05c61248829e5f56540823643b
```

Machine / Distribution proof：

```text
Release18 Exact-source Gate           36812999690 PASS
Release18 Distribution Gate           36813781522 PASS
Toolbox Smoke                         36813781495 PASS
System Care Smoke                     36813781475 PASS
Beginner Menu Gate                    36813781578 PASS
Public Runner Trigger Scope           36813781483 PASS
Workflow Archive Integrity            36813781472 PASS
```

Distribution Gate 证明 target-only Nginx server block 解析、wildcard / explicit listen 映射、多 listener 探测、Public overlay Restore-As 回归、隔离安装、中文 listener 错误分类以及 rollback / DNS / SOURCE 安全边界均 PASS。

旧 Stable Installer Smoke 仍硬编码 `0.1.0-release5`，其 identity failure 属于历史 workflow debt，不作为 release18 owning evidence。

Current Production truth 继续独立：

```text
Production exact independently proven Slot 3 Build  0.1.0-release14
release17-era Restore-As                        REAL_FAIL / VHOST_PRESENT / FIXED_LOOPBACK_HTTP_FAIL
release18 Production install                    NOT_YET_OWNER_VERIFIED
release18 Owner Real Use                        PENDING
Migration executed                              NO
DNS write                                       NO
SOURCE delete                                   NO
Existing target overwrite                       NO
Resource Safe Apply                             NO
```

## Slot 3 release19 guarded Nginx reload source closure · Public Distribution pending

2026-10-01，OWNER 在 release18 Public Distribution 后继续真实 Restore-As-New，目标域名为 `113.kewaro.com`。release18 诊断明确证明：

```text
target Nginx listener           FOUND
local HTTP verification         REAL_FAIL
new target rollback             invoked
DNS write                       NO
SOURCE mutation                 NO
```

普通用户终端信息为：

```text
新网站已恢复，P07 也找到了 Nginx 实际 HTTP 监听地址，但本机仍无法连通，已回滚新目标。
这表示问题已经缩小到服务器本机监听/网络层，不是备份、SQLite 或数据库恢复本身。
DNS 没有修改，原网站没有修改。
```

该证据证明 release18 已排除“只是假设 127.0.0.1”的问题，但仍不能证明运行中的 Nginx 已加载磁盘上的新 vhost。release19 因此增加 guarded reload：

```text
CloudPanel new site exists
→ nginx -t
→ only PASS may continue
→ nginx -s reload
→ listener / Host / SNI verification
```

若最终本机 HTTP 仍失败，release19 同时把 curl transport 安全分类为：

```text
CONNECT_FAILED
TIMEOUT
EMPTY_REPLY
OTHER
```

不向普通用户暴露真实 listener IP、原始 stderr、Secret 或数据库口令。

Exact source evidence：

```text
Slot 3 source Build                  0.1.0-release19
Private source main merge            728568b00505a206f7e6b66740bede0ad25034ed
Release19 Exact-source Gate          36815000676 PASS
Guarded nginx -t -> reload ordering  PASS
Reload fail-closed regression        PASS
Transport classification             PASS
Restore-As / SQLite regressions      PASS
Rollback / DNS / SOURCE safety       PASS
Secret boundary                      PASS
```

当前阶段：

```text
Current Public Distribution          0.1.0-release18
Production exact independently proven 0.1.0-release14
release18-era Restore-As             REAL_FAIL / LISTENER_FOUND / LOCAL_HTTP_UNREACHABLE
release19 Private Source             MERGED
release19 Public Distribution        NOT_RUN
release19 Production install         NOT_RUN
release19 Owner Real Use             NOT_RUN
Migration / DNS / SOURCE delete      NOT_RUN
Existing target overwrite            NOT_RUN
```

## Slot 3 release19 guarded Nginx reload distribution closure

release19 已完成 Public Distribution，用于收敛 OWNER 在 release18-era Restore-As 真机验证中暴露的“目标 listener 已发现，但本机 HTTP 仍不可达”问题。

release19 固定：

```text
CloudPanel create/restore
→ nginx -t
→ syntax PASS 才允许 nginx -s reload
→ target listener / Host / SNI verification
→ curl failure classify CONNECT_FAILED / TIMEOUT / EMPTY_REPLY / OTHER
→ beginner Chinese diagnosis
→ any failure = rollback new target
```

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release19
Exact runtime source merge            728568b00505a206f7e6b66740bede0ad25034ed
Public distribution main              1c218b5dd2ed5c1ef1193ce664c8de42180a51cf
Runtime manifest blob                 67f40e615003d8c302ec391c73c836f05113db57
Full overlay manifest blob            07a4ba0aa2a4679cb80324bfcd11e6cc785ba6b6
Final installer blob                  ab42d2d1b84669372b8615819de63f0c19619067
Stable installer blob                 3a1853e4fdf30c0327a1e6d4390fb8b6de57ca35
Toolbox blob                          83a7b38e69c6db1d30a16f1f648172163f693b5e
```

Machine / Distribution proof：

```text
Release19 Exact-source Gate           36815000676 PASS
Release19 Distribution Gate           36816117494 PASS
Toolbox Smoke                         36816117429 PASS
System Care Smoke                     36816117478 PASS
Beginner Menu Gate                    36816117399 PASS
Public Runner Trigger Scope           36816117468 PASS
Workflow Archive Integrity            36816117483 PASS
```

Distribution Gate 还证明：

```text
public overlay release19 regressions  PASS
nginx -t then nginx -s reload         PASS
curl transport diagnosis              PASS
isolated release19 runtime install    PASS
beginner Chinese transport rendering  PASS
rollback / DNS / SOURCE safety        PASS
Production write                      NOT_RUN
```

说明：旧 Stable Installer Smoke 与旧 Final Distribution + R2 Onboarding 仍硬编码 `release5 / guided-init16` 身份，因此在 release19 PR 上失败属于历史 workflow debt，不作为 release19 owning evidence。

Current Production truth 继续独立：

```text
Production exact independently proven Slot 3 Build  0.1.0-release14
release18-era Restore-As                        REAL_FAIL / LISTENER_FOUND / LOCAL_HTTP_UNREACHABLE
release19 Production install                    NOT_YET_OWNER_VERIFIED
release19 Owner Real Use                        PENDING
Migration executed                              NO
DNS write                                       NO
SOURCE delete                                   NO
Existing target overwrite                       NO
Resource Safe Apply                             NO
```

下一次 OWNER 通过永久一行 Toolbox 进入 Slot 3 后，先确认 Build 已升级到 release19，再使用全新目标域名继续 Restore-As-New 真机验证。Public Distribution 不等于 Production Restore PASS。

## Slot 3 release19 Owner Real Restore-As · Nginx reload fail

2026-10-01，OWNER 在 release19 Public Distribution 后继续真实 Restore-As-New，目标域名为 `114.kewaro.com`。终端截图显示：

```text
新网站恢复失败。
Nginx 配置检查通过，但重新加载失败，P07 已回滚新目标。
DNS 没有修改，原网站没有修改。
域名解析：未修改 · 原网站：保留
```

这把真实故障进一步收敛为：

```text
backup / restore package                 已通过此前链路
SQLite / MySQL / files                  已推进到后段
target site / vhost creation            已推进
nginx -t                                PASS
nginx reload                            REAL_FAIL
new target rollback                     invoked
DNS write                               NO
SOURCE mutation                         NO
```

因此 release19 的 guarded reload 设计本身成功暴露了真正失败点，但 OWNER Real Restore-As 仍未 PASS。

本张截图没有单独显示 `--build-id`，因此仍不把 Production exact installed Build 从已独立证明的 release14 改写成 release19；这里只记录为 release19 Public Distribution 后的真实使用证据。

下一轮必须优先查明本机 Nginx 的真实 reload 方式与失败原因，不得继续通过增加等待、改 listener 或放宽验证来绕过：

```text
nginx -t PASS
+ nginx -s reload FAIL
→ inspect actual systemd / master PID / executable / permissions / stderr-safe classification
→ determine CloudPanel-managed reload path
→ preserve fail-closed rollback
```

## Slot 3 release20 systemd-first Nginx reload source closure · Public Distribution pending

2026-10-01，OWNER 在 release19 Public Distribution 后真实 Restore-As-New 到 `114.kewaro.com`，已证明：

```text
nginx -t                     PASS
nginx reload                 REAL_FAIL
new target rollback          invoked
DNS write                    NO
SOURCE mutation              NO
```

release20 不再把 CloudPanel / Ubuntu 上的 Nginx 默认按 direct signal 管理。固定：

```text
nginx -t
→ PASS
→ systemctl is-active nginx
   → active: systemctl reload nginx
   → inactive / unavailable: nginx -s reload
→ reload PASS
→ target listener / Host / SNI verification
```

若 systemd 已 active 但 `systemctl reload nginx` 失败，必须 fail closed，不得静默退回 direct signal；失败仍回滚本次新目标，DNS / SOURCE / existing target 均不修改。

Exact source evidence：

```text
Slot 3 source Build                       0.1.0-release20
Candidate exact-source Gate               36818650825 PASS
Candidate head                            53067e953183cd7902382db9b76165a33bf0b21f
Private source main merge                 2b0fc8b51b66a0d01b2e96bc7b91a385004628f6
systemd-first reload regression           PASS
direct-signal fallback regression         PASS
active-systemd failure fail-closed        PASS
Restore-As verified local gate            PASS
Real R1 database compatibility gate       PASS
Synthetic CloudPanel Restore-As E2E       PASS
full bootstrap CI                         PASS
```

当前阶段：

```text
Current Public Distribution               0.1.0-release19
Production exact independently proven     0.1.0-release14
release19-era Restore-As                   REAL_FAIL / NGINX_T_PASS / NGINX_RELOAD_FAIL
release20 Private Source                   MERGED
release20 Public Distribution              NOT_RUN
release20 Production install               NOT_RUN
release20 Owner Real Use                   NOT_RUN
Migration / DNS / SOURCE delete            NOT_RUN
Existing target overwrite                  NOT_RUN
```

release20 必须完成现有 Public Distribution Gate 后，才进入新的 OWNER 真机 Restore-As 验证；Public Distribution 仍不等于 Production Restore PASS。

## Slot 3 release20 systemd-first Nginx reload distribution closure

release20 已完成现有 V0.1.0 Public Distribution，用来修复 release19-era 真机 Restore-As 已明确暴露的 `nginx -t PASS / nginx reload FAIL`。

release20 固定：

```text
CloudPanel create/restore
→ nginx -t
→ systemctl is-active nginx
   → active: systemctl reload nginx
   → inactive / unavailable: nginx -s reload
→ target listener / Host / SNI verification
→ any failure = rollback new target
```

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release20
Exact runtime source merge            2b0fc8b51b66a0d01b2e96bc7b91a385004628f6
Source authority closure merge        f0a74e99ea4341ce6bcf3a8defb45db4312f90a4
Public distribution main              25f192fb6d54242515e007a5b4ffa34c98bad8d7
Runtime manifest blob                 0b5de474284a2ee5f52030736ab64c0a0e07182a
Full overlay manifest blob            6628a1fe5245894dc36ff67120bd97ba159bf38a
Final installer blob                  c94e9abad001d9724f31f435265691257801cff6
Stable installer blob                 104af730d80df1272157a73835fcdd656d446a73
Toolbox blob                          56f7861090b5666481d2a4fa5695b0a885f3bdd3
```

Machine / Distribution proof：

```text
Release20 Candidate Exact-source Gate 36818650825 PASS
Source main bootstrap CI              36819895048 PASS
Source closure CI                     36820623277 PASS
Release20 Distribution Gate           36820647201 PASS
Toolbox Smoke                         36820647232 PASS
System Care Smoke                     36820647145 PASS
Beginner Menu Gate                    36820647193 PASS
Public Runner Trigger Scope           36820647152 PASS
Workflow Archive Integrity            36820647185 PASS
```

Distribution Gate 还证明：

```text
systemd-first nginx reload             PASS
inactive/unavailable direct fallback  PASS
active-systemd failure fail-closed    PASS
exact runtime / overlay manifests     PASS
isolated release20 runtime install    PASS
rollback / DNS / SOURCE safety        PASS
Production write                      NOT_RUN
```

历史 release6–19 workflow 仍可能因硬编码旧 Build 身份而在 release20 PR 上失败；这些属于历史 workflow debt，不作为 release20 owning evidence。release20 owning Gate 与当前公共 smoke 已独立 PASS。

Current Production truth 继续独立：

```text
Production exact independently proven Slot 3 Build  0.1.0-release14
release19-era Restore-As                        REAL_FAIL / NGINX_T_PASS / NGINX_RELOAD_FAIL
release20 Production install                    NOT_YET_OWNER_VERIFIED
release20 Owner Real Use                        PENDING
Migration executed                              NO
DNS write                                       NO
SOURCE delete                                   NO
Existing target overwrite                       NO
Resource Safe Apply                             NO
```

下一次 OWNER 通过永久一行 Toolbox 进入 Slot 3 后，应先确认 Build 已升级到 release20，再使用全新目标域名继续 Restore-As-New 真机验证。Public Distribution 不等于 Production Restore PASS。

## Slot 3 release21 managed Nginx main-process HUP source closure · Public Distribution pending

2026-10-01，OWNER 在 release20 Public Distribution 后继续真实 Restore-As-New，目标域名为 `116.kewaro.com`。终端结果：

```text
new target site/config          created
Nginx reload                    REAL_FAIL
new target rollback             invoked
DNS write                       NO
SOURCE mutation                 NO
```

截图没有单独显示 exact installed Build，因此 Production exact independently proven Build 仍保持 release14；这里只记录为 release20 Public Distribution 后的真实使用证据。

release21 针对“systemctl reload nginx 仍失败”增加受管的主进程 HUP fallback：

```text
nginx -t
→ systemd active
→ systemctl reload nginx
   → PASS: continue
   → non-permission/non-bus FAIL:
       confirm nginx still active
       systemctl kill --kill-whom=main --signal=HUP nginx
       confirm nginx still active
→ listener / Host / SNI verification
```

不允许自动 restart。任何阶段失败仍回滚本次新目标；DNS、SOURCE、existing target 均不自动修改。

Exact source evidence：

```text
Slot 3 source Build                  0.1.0-release21
Candidate exact-source Gate          36826060883 PASS
Private source main merge            71f5089e42e56b0f432ee59d7cfc7a70854da2f0
managed main-process HUP success      PASS
managed HUP failure fail-closed       PASS
permission failure no-fallback        PASS
inactive-systemd direct fallback      PASS
Restore-As / migration regressions    PASS
full candidate CI                     43/43 PASS
```

当前阶段：

```text
Current Public Distribution           0.1.0-release20
Production exact independently proven 0.1.0-release14
release20-era Restore-As              REAL_FAIL / NGINX_RELOAD_FAIL
release21 Private Source              MERGED
release21 Public Distribution         NOT_RUN
release21 Production install          NOT_RUN
release21 Owner Real Use              NOT_RUN
DNS / SOURCE delete                   NOT_RUN
Existing target overwrite             NOT_RUN
```

release21 只有完成 Public Distribution 后，才进入下一次 OWNER 真机 Restore-As 验证；Public Distribution 不等于 Production Restore PASS。

## Slot 3 release21 managed Nginx HUP distribution closure

release21 已完成现有 V0.1.0 Public Distribution。它针对 release20-era 真机 Restore-As 在 `116.kewaro.com` 暴露的 Nginx reload REAL_FAIL，保留常规 systemd reload 为第一路径，并增加由 systemd 精确向 Nginx 主进程发送 HUP 的受管优雅重载 fallback。

固定路径：

```text
nginx -t
→ systemd active
→ systemctl reload nginx
   → PASS: continue
   → non-permission/non-bus FAIL:
       confirm nginx still active
       systemctl kill --kill-whom=main --signal=HUP nginx
       confirm nginx still active
→ target listener / Host / SNI verification
→ any failure = rollback new target
```

禁止自动 restart；DNS、SOURCE、existing target 仍不自动修改。

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release21
Exact runtime source merge            71f5089e42e56b0f432ee59d7cfc7a70854da2f0
Source authority closure merge        f3b305951771441b4a67e875a9ee21f88b6dc9f3
Public distribution main              32703dc47e2ae8a0f344e1525f44be946be77b62
Runtime manifest blob                 32583b097d33c32b68e3bca7d9dce2fd08c0c778
Full overlay manifest blob            29eb8537ee0edac5d4f4932255ba469ad0b9f5fd
Final installer blob                  8da9b42cc4e2d6d5a6c649812a8fe074fd71cf28
Stable installer blob                 3fbbdb7b501470d5387a8c1b7674177d025a52d7
Toolbox blob                          c2782154f9617f30a6a92d1e49dec557df3459e2
```

Machine / Distribution proof：

```text
Release21 Candidate Gate              36826060883 PASS
Source main bootstrap CI              36826817099 PASS
Source authority closure main CI      36827736992 PASS
Release21 Distribution Gate           36827256710 PASS
Toolbox Smoke                         36827256562 PASS
System Care Smoke                     36827256673 PASS
Beginner Menu Gate                    36827256645 PASS
Public Runner Trigger Scope           36827256739 PASS
Workflow Archive Integrity            36827256744 PASS
Public Runner Current Self Test       36827758259 PASS
```

历史旧版本 workflow 继续可能因写死旧 Build 身份而失败；这些不作为 release21 owning evidence。release21 owning Gate 与当前公共 smoke 已独立 PASS。

Current Production truth 继续独立：

```text
Production exact independently proven Slot 3 Build  0.1.0-release14
release20-era Restore-As                        REAL_FAIL / NGINX_RELOAD_FAIL
release21 Production install                    NOT_YET_OWNER_VERIFIED
release21 Owner Real Use                        PENDING
Migration executed                              NO
DNS write                                       NO
SOURCE delete                                   NO
Existing target overwrite                       NO
Resource Safe Apply                             NO
```

下一次 OWNER 通过永久一行 Toolbox 进入 Slot 3 后，应先确认 Build 已升级到 release21，再使用全新目标域名继续 Restore-As-New 真机验证。Public Distribution 不等于 Production Restore PASS。

## Slot 3 release22 live CloudPanel Nginx instance source closure · Public Distribution pending

2026-10-01，OWNER 在 release21 Public Distribution 后完成真机只读诊断并证明前两轮 reload 假设不适用于该 CloudPanel 机器：

```text
installed P07 Build                  0.1.0-release21
systemctl is-active nginx            inactive
nginx.service MainPID                0
nginx.service state                  inactive / dead
live Nginx master PID                856
live master command                  /usr/sbin/nginx ... -c /home/clp/services/nginx/nginx.conf
default /run/nginx.pid               empty
default /var/run/nginx.pid           empty
default nginx -t                     PASS, but tests /etc/nginx/nginx.conf
```

因此 release20 / release21 的问题根因已收敛为：P07 控制了默认/systemd Nginx 身份，而 CloudPanel 实际运行的是独立启动、带自定义 `-c` 的 live Nginx master。

release22 固定：

```text
discover exact live Nginx master
→ extract live -p/-c runtime args
→ nginx -t against the same live config
→ systemd active: managed path
→ systemd inactive + live master:
   revalidate exact PID/runtime args
   SIGHUP exact master PID
   confirm same master still exists
→ nginx -T against the same live config
→ listener / Host / SNI verification
```

任何 master ambiguous / changed / missing / signal failure 都 fail closed；不自动 restart，不修改 DNS / SOURCE / existing target。

Exact source evidence：

```text
Slot 3 source Build                  0.1.0-release22
Candidate exact-source Gate          36833721873 PASS
Private source main merge            0db20d21100aac2099484468fd7ab8d647e0fa12
live master discovery                PASS
CloudPanel custom -c binding         PASS
exact master HUP safety              PASS
nginx -t/-T same-instance binding    PASS
Restore-As / migration regressions   PASS
full candidate CI                    43/43 PASS
```

当前阶段：

```text
Current Public Distribution           0.1.0-release21
Production exact readback             0.1.0-release21
release21-era Restore-As              REAL_FAIL / NGINX_RELOAD_FAIL
release22 Private Source              MERGED
release22 Public Distribution         NOT_RUN
release22 Production install          NOT_RUN
release22 Owner Real Use              NOT_RUN
DNS / SOURCE delete                   NOT_RUN
Existing target overwrite             NOT_RUN
```

release22 完成 Public Distribution 后，才进入下一次 OWNER 真机 Restore-As 验证。

## Slot 3 release22 live CloudPanel Nginx instance distribution closure

release22 已完成 V0.1.0 Public Distribution。它来自 OWNER 对 release21 真机的只读诊断证据：

```text
installed Build                  0.1.0-release21
nginx.service                    inactive / dead
systemd MainPID                  0
live Nginx master PID            856
live Nginx config                /home/clp/services/nginx/nginx.conf
default /run/nginx.pid           empty
default nginx -t                 PASS / wrong instance
```

因此 release22 不再假定 CloudPanel 的实际 Nginx 由默认 `nginx.service` / 默认 pid / 默认 config 管理。固定：

```text
discover exactly one root nginx master
→ capture live -p / -c runtime args
→ nginx -t with the same live args
→ if systemd owns nginx: managed reload path
→ else:
   revalidate exact same master identity
   send SIGHUP only to that master PID
   confirm same master remains running
→ nginx -T with the same live args
→ target listener / Host / SNI verification
→ any failure = rollback new target
```

禁止自动 restart；ambiguous / changed / missing master 必须 fail closed。DNS、SOURCE、existing target 均不自动修改。

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release22
Exact runtime source merge            0db20d21100aac2099484468fd7ab8d647e0fa12
Source authority closure merge        1cbe3b5b2eb8b6d33126f1053bb061817991cdf7
Public distribution main              3eeda218ab2f7d8fea6f498ba71c97265cc7d738
Runtime manifest blob                 11dcf42809aacf6796ef0b2ab6a31884c01860cb
Full overlay manifest blob            5bb0336e51a9466f7d35589403811d2cc9e9cbc7
Final installer blob                  1894300e65c0fb7ca655709ebd3a0ae82bf3fe5e
Stable installer blob                 3368c3aa91304553d7ffd09e83b092da2d6d8708
Toolbox blob                          f90a31aba2f755ac2a07de0bb4f81ac7d0202deb
```

Machine / Distribution proof：

```text
Release22 Candidate Gate              36833721873 PASS
Source runtime main CI                36834580261 PASS
Source closure PR CI                  36834749434 PASS
Release22 Distribution Gate           36836662878 PASS
Toolbox Smoke                         36836662810 PASS
System Care Smoke                     36836663188 PASS
Beginner Menu Gate                    36836663039 PASS
Public Runner Trigger Scope           36836662983 PASS
Workflow Archive Integrity            36836663069 PASS
Public main Toolbox Smoke             36836750608 PASS
Public main System Care Smoke         36836750571 PASS
Public main Current Self Test         36836750628 PASS
```

历史 Stable Installer / R2 Onboarding 与旧 release workflow 仍可能因硬编码旧身份失败；它们不属于 release22 owning evidence。

Current Production truth：

```text
Production exact independently proven Slot 3 Build  0.1.0-release21
release21 Owner real use                       REAL_FAIL / LIVE_INSTANCE_MISMATCH
release22 Production install                   NOT_YET_OWNER_VERIFIED
release22 Owner Real Use                       PENDING
Migration executed                             NO
DNS write                                      NO
SOURCE delete                                  NO
Existing target overwrite                      NO
Automatic Nginx restart                        NO
Resource Safe Apply                            NO
```

下一次 OWNER 应通过永久一行 Toolbox 进入 Slot 3，确认已升级到 release22，再用新的完整域名执行 Restore-As-New 真机验证。

## Slot 3 release23 Nginx stabilization source closure · Public Distribution pending

OWNER 已完成 release22 真机回读：

```text
installed Build                       0.1.0-release22
Restore-As target                     118.kewaro.com
Restore-As result                     REAL_FAIL / NGINX_RELOAD_FAIL
rollback                              invoked
DNS write                             NO
SOURCE mutation                       NO

live Nginx master                     PID 856
live config                           /home/clp/services/nginx/nginx.conf
systemd nginx                         inactive
standalone _discover_nginx_master     PASS
standalone _reload_nginx              LIVE_MASTER_HUP PASS
```

这证明 release22 的 live-instance discovery 与 HUP 能力本身可用；剩余差异只发生在 CloudPanel 刚完成新站创建后的 Restore-As 时序内。

release23 固定：
- 等待两个连续相同的 live-master 观察值后才绑定运行实例；
- systemd inactive + stable live master 未找到时直接 fail closed；
- 不再回退到默认 `nginx -s reload`；
- HUP 前再次确认同一 master；
- HUP 后在 bounded window 内确认同一 master 仍存在；
- 所有失败继续回滚新目标，不 restart Nginx。

Exact source evidence：

```text
Slot 3 source Build                   0.1.0-release23
Candidate Gate                        36844904239 PASS
Private source main merge             0f8d5175fdd425668021b6c1d106dbee9d1ed6a9
Public Distribution                   NOT_RUN
Production install                    NOT_RUN
Owner Real Use                        NOT_RUN
```

当前 Public Distribution 仍为 release22；不得在 Public Distribution 完成前把 release23 记为已发布。

## Slot 3 release23 Nginx stabilization distribution closure

release23 已完成 V0.1.0 Public Distribution。它针对 release22 的真实差异：独立 `LIVE_MASTER_HUP` 验证 PASS，但 CloudPanel 新站刚创建完成后 Restore-As 仍可能在 Nginx reload 阶段失败。

release23 固定：

```text
CloudPanel restore/create complete
→ bounded live-master stabilization window
→ two consecutive matching master observations
→ bind exact live -p/-c args
→ nginx -t
→ managed systemd reload OR exact-master HUP
→ bounded post-HUP confirmation
→ nginx -T with same live args
→ Host / listener / SNI verification
```

systemd inactive 且 stable live master 未找到时不再使用默认 direct reload；必须 `MASTER_NOT_FOUND` fail closed。自动 restart 继续禁止。

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release23
Exact runtime source merge            0f8d5175fdd425668021b6c1d106dbee9d1ed6a9
Source authority closure merge        a1bf2785f61b7c224bdf70f401c38f8d2fe54c1d
Public distribution main              b063d07c7c1bb807ad1ada51becc46030cb40c3e
Runtime manifest blob                 346edfe702d95ff2f5ee9b6150e84fcae5adf9fc
Full overlay manifest blob            1b2ff1798d64b655b8a6d69f87735b82a9d88152
Final installer blob                  cd37639255976a5de11e022de430f78b7de95621
Stable installer blob                 51d2d84ab951692ddda4e9bc87038a470030938c
Toolbox blob                          638789c331fd2987370ec787806aa87c81431448
```

Machine / Distribution proof：

```text
Release23 Candidate Gate              36844904239 PASS
Release23 source main CI              36845778634 PASS
Release23 source closure PR CI        36846274754 PASS
Release23 source closure main CI      36847222083 PASS
Release23 Distribution Gate           36847242129 PASS
Toolbox Smoke                         36847242134 PASS
System Care Smoke                     36847242061 PASS
Beginner Menu Gate                    36847242180 PASS
Public Runner Trigger Scope           36847242191 PASS
Workflow Archive Integrity            36847242082 PASS
Public main Toolbox Smoke             36847342593 PASS
Public main System Care Smoke         36847342775 PASS
Public main Current Self Test         36847342628 PASS
```

旧 Stable Installer / R2 Onboarding 与旧 release workflow 的版本硬编码失败不作为 release23 owning evidence。

Current Production truth：

```text
Production exact independently proven Slot 3 Build  0.1.0-release22
release22 Owner real use                       REAL_FAIL / RESTORE_TIME_NGINX_RELOAD
release22 standalone LIVE_MASTER_HUP            PASS
release23 Production install                    NOT_YET_OWNER_VERIFIED
release23 Owner Real Use                        PENDING
DNS write                                       NO
SOURCE delete                                   NO
Existing target overwrite                       NO
Automatic Nginx restart                         NO
```

下一次 OWNER 通过永久一行 Toolbox 进入 Slot 3 后，应先确认 Build 已升级到 release23，再自行输入任意合法、未占用且不覆盖现有站点的目标域名执行 Restore-As-New 真机验证。P07 不预设 OWNER 应使用哪个域名。

## Slot 3 release24 site-serving Nginx role separation source closure · Public Distribution pending

OWNER 在 release23-era 真机 Restore-As 中已证明 reload 阶段可越过，但最终得到：

```text
target domain                         120.ke.com
Restore-As result                    REAL_FAIL / TARGET_VHOST_MISSING
rollback                             invoked
DNS write                            NO
SOURCE mutation                      NO
```

结合此前只读真机证据：

```text
nginx.service                        inactive / dead
systemd MainPID                      0
observed root nginx master           PID 856
observed master config               /home/clp/services/nginx/nginx.conf
80/443 listener readback             none in captured check
```

以及 CloudPanel 当前服务边界，release24 修正前几轮的实例归属判断：CloudPanel 控制面 Nginx 与网站 Nginx 不是同一个职责，不能仅凭 root master 身份绑定。

release24 固定：

```text
preflight before any Restore-As write
→ active nginx.service = managed website-Nginx path
→ otherwise inspect each live master with its own nginx -T args
→ require actual 80/443 website listener role
→ only qualified site Nginx can be HUPed / verified
→ no qualified site Nginx = SITE_NGINX_NOT_RUNNING fail closed before target create
```

Exact source evidence：

```text
Slot 3 source Build                  0.1.0-release24
Candidate Gate                       36854715322 PASS
Private source main merge            2a57a0c32a44cb30f15a49dece253ec917c901ca
panel-only Nginx rejection           PASS
site-Nginx preflight-before-write    PASS
systemd site-Nginx path              PASS
live site-master path                PASS
Restore-As machine E2E               PASS
Public Distribution                  NOT_RUN
Production install                   NOT_RUN
Owner Real Use                       NOT_RUN
```

安全边界保持：不自动 start/restart Nginx，不修改 DNS，不删除 SOURCE，不覆盖 existing target。当前 Public Distribution 仍为 release23。

## Slot 3 release24 site-serving Nginx role separation distribution closure

release24 已完成 V0.1.0 Public Distribution。它修正 release22 / release23 对 CloudPanel Nginx 实例角色的错误归属：仅发现 root Nginx master 不代表该实例承载网站 80/443 流量。

release24 固定：

```text
Restore-As preflight before target write
→ active nginx.service = managed website-Nginx path
→ otherwise enumerate live root Nginx masters
→ run each instance's own nginx -T runtime args
→ only 80/443 site-serving instance qualifies
→ control-plane-only Nginx is ignored
→ no site-serving Nginx = fail closed before target creation
→ only qualified site Nginx may be reloaded / HUPed
→ Host / listener / SNI remain local verification; DNS not required
```

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release24
Exact runtime source merge            2a57a0c32a44cb30f15a49dece253ec917c901ca
Source authority closure merge        b5beec4133acede30ad8a40de067df505b2fd141
Public distribution main              9151216074fd3dc4bf049f575657d44e460ae085
Runtime manifest blob                 c6435a15a576c3dd7bd7c48cd8828f782391a2c9
Full overlay manifest blob            b08f5fee96505eed64a5b88f02d1f2279047fa39
Final installer blob                  2448051ba708af11e2de3fb53deb13a4dadc86c5
Stable installer blob                 e309806cf4a6218baee5b0982df753d14022ea28
Toolbox blob                          eec990218e260745cd847382bdbf0576a316a976
```

Machine / Distribution proof：

```text
Release24 Candidate Gate              36854715322 PASS
Release24 runtime source main CI      36855594436 PASS
Release24 source closure PR CI        36855828760 PASS
Release24 Distribution Gate           36858661463 PASS
Toolbox Smoke                         36858661096 PASS
System Care Smoke                     36858661074 PASS
Beginner Menu Gate                    36858661080 PASS
Public Runner Trigger Scope           36858661072 PASS
Workflow Archive Integrity            36858661109 PASS
Public main Toolbox Smoke             36858734545 PASS
Public main System Care Smoke         36858734543 PASS
Public main Current Self Test         36858734529 PASS
```

旧 release-specific workflow、Stable Installer / R2 Onboarding 中仍可能存在旧身份硬编码失败；它们不是 release24 owning evidence。

Current Production truth：

```text
Production exact independently proven Slot 3 Build  0.1.0-release22
release23 Owner real-use evidence              REAL_FAIL / TARGET_VHOST_MISSING
release24 Production install                   NOT_YET_OWNER_VERIFIED
release24 Owner Real Use                       PENDING
DNS write                                      NO
SOURCE delete                                  NO
Existing target overwrite                      NO
Automatic Nginx start/restart                  NO
Resource Safe Apply                            NO
```

下一次 OWNER 通过永久一行 Toolbox 进入 Slot 3 后，应先确认 Build 已升级到 release24，再自行输入任意合法、未占用且不覆盖现有站点的目标域名执行 Restore-As-New 真机验证。P07 不预设目标域名，也不要求测试域名提前修改 DNS。

## Slot 3 release25 offline Recovery Restore-As source closure · Public Distribution pending

2026-10-01，OWNER 明确确认本轮备份 / Restore-As 真机验证一直在**保留的旧 Linode Recovery Copy** 上执行，并不是误连测试机。该机器在 2026-09-24 Linode → DigitalOcean 迁移过程中主动停止了网站 `nginx.service`，用于保留旧机恢复副本；CloudPanel 控制面 `clp-nginx` 仍监听 8443。

release24 真机证据：

```text
environment                         preserved Linode Recovery Copy
website nginx.service               inactive / intentionally stopped after migration
CloudPanel control Nginx            active / 8443
site 80/443 live listeners          none
default /etc/nginx config           present
default nginx -t                    PASS
Restore-As release24 result         SAFE_STOP / SITE_NGINX_NOT_RUNNING
target created                      NO
DNS write                           NO
SOURCE mutation                     NO
automatic Nginx start/restart       NO
```

这证明 release24 的**Nginx 角色分离**是正确的：P07 不再把 8443-only CloudPanel 控制面 Nginx 当成网站 Nginx，也没有 HUP 错误实例。但同时暴露出一个真实 Recovery 场景缺口：网站 Nginx 被有意停机时，release24 在恢复前直接阻断整个 Restore-As，无法完成“离线恢复验证”。

release25 将 Restore-As 明确分成两种验证模式：

```text
A. ONLINE
   website Nginx running
   → existing reload / Host / SNI path
   → files / DB / app / Host / SNI PASS required

B. OFFLINE_STATIC
   website Nginx intentionally not running
   → pre-write static nginx -t required
   → CloudPanel new target + files + DB restore allowed
   → post-restore nginx -t / nginx -T
   → target vhost + configured 80/443 listener presence
   → files / DB / app / Nginx config verification
   → Host / SNI = NOT_RUN
   → no Nginx start / restart / reload
```

离线成功必须使用独立结果身份：

```text
RESTORE_AS_OFFLINE_VERIFIED
verification_mode = OFFLINE_STATIC
machine_verification_scope = FILES_DB_APP_NGINX_CONFIG
online_verification = NOT_RUN / SITE_NGINX_NOT_RUNNING
nginx_reload = NOT_RUN
```

不得把离线恢复写成完整在线 PASS。若离线 `nginx -t` 失败、目标 vhost 缺失或没有网站 listener 配置，仍回滚**仅本次新建目标**。DNS、SOURCE、existing target 与旧证书安全边界保持不变。

Exact source evidence：

```text
Slot 3 source Build                  0.1.0-release25
Candidate PR                         #109
Candidate head                       2caaedc93724fa8e1ebbd197568243ba5a5034bf
Candidate exact-source CI            36878240140 PASS
Private source main merge            4260aa6553c6a4f20c631a2f6b6ea5baec3f3f82
Source main CI                       36879393432 PASS
offline preflight regression         PASS
offline no-reload regression         PASS
offline Recovery machine E2E         PASS
online Restore-As path               PASS
rollback / DNS / SOURCE safety       PASS
```

当前阶段严格保持：

```text
Current Public Distribution          0.1.0-release24
Production exact independently proven 0.1.0-release22
release24 Recovery real-use          SAFE_STOP / SITE_NGINX_NOT_RUNNING
release25 Private Source             MERGED
release25 Public Distribution        NOT_RUN
release25 Production install         NOT_RUN
release25 Owner Real Use             NOT_RUN
DNS / SOURCE delete                  NOT_RUN
Existing target overwrite            NOT_RUN
Automatic Nginx start/restart        NO
```

release25 只有完成独立 Public Distribution Gate 后，OWNER 才继续在同一 Linode Recovery Copy 上执行新的 Restore-As 真机验证。Public Distribution 仍不等于 Production 或完整在线 Restore PASS。

## Slot 3 release25 offline Recovery Restore-As distribution closure

release25 已完成 V0.1.0 Public Distribution，用于补齐保留旧 Linode Recovery Copy 上“网站 Nginx 有意停止”时的 Restore-As 真机恢复场景。release24 的 Nginx 角色分离继续成立：8443-only CloudPanel 控制面 Nginx 不得当作网站 Nginx，也不得被错误 HUP。

release25 固定双模式验证：

```text
ONLINE
→ website Nginx running
→ existing reload + Host / SNI verification
→ FILES_DB_APP_HOST_SNI

OFFLINE_STATIC
→ website Nginx intentionally stopped
→ static nginx -t before write
→ CloudPanel target + files + DB restore
→ post-restore nginx -t / nginx -T
→ target vhost + configured 80/443 listener presence
→ Host / SNI = NOT_RUN
→ nginx start / restart / reload = NOT_RUN
→ FILES_DB_APP_NGINX_CONFIG
```

离线成功使用独立状态 `RESTORE_AS_OFFLINE_VERIFIED`，不得冒充完整在线 PASS。离线配置校验失败仍只回滚本次新目标；DNS、SOURCE、existing target 与旧证书边界不变。

Exact identities：

```text
P07 public product version            V0.1.0
Slot 3 Build                          0.1.0-release25
Exact runtime source merge            4260aa6553c6a4f20c631a2f6b6ea5baec3f3f82
Source authority closure merge        075d24158428282699257053d317a66c85abb5b0
Public distribution PR                #1685
Public distribution main              c817251bf4374a69eb27ea6e563e52d67e40d838
Runtime manifest blob                 5e688084e88e533d8446905950ca7d4519b4ff5e
Full overlay manifest blob            db6f9c013bed4f3d7cc7953446ea73e6592b271f
Final installer blob                  fb88cf8f05d36866ea3e396ca6ac6992def3cd05
Stable installer blob                 e4fde9c740ee7476748f2a1e8ef96508fd89dc23
Toolbox blob                          7c8f1a6a5a787b2415d08c9af72ce2d32dcac48c
```

Machine / Distribution proof：

```text
Release25 Candidate Exact-source CI   36878240140 PASS
Release25 Source main CI              36879393432 PASS
Release25 Distribution Gate           36883195967 PASS
Toolbox Smoke                         36883195907 PASS
System Care Smoke                     36883195699 PASS
Beginner Menu Gate                    36883195777 PASS
Public Runner Trigger Scope           36883195834 PASS
Workflow Archive Integrity            36883195933 PASS
Public main Toolbox Smoke             36883343351 PASS
Public main System Care Smoke         36883343205 PASS
Public main Current Self Test         36883343207 PASS
```

Current Production / Owner truth 继续独立：

```text
Production exact independently proven Slot 3 Build  0.1.0-release22
release24 Recovery real-use                    SAFE_STOP / SITE_NGINX_NOT_RUNNING
release25 Production install                   NOT_YET_OWNER_VERIFIED
release25 Owner Real Use                       PENDING
DNS write                                      NO
SOURCE delete                                  NO
Existing target overwrite                      NO
Automatic website Nginx start/restart          NO
```

下一步：OWNER 继续在同一保留的 Linode Recovery Copy 上，通过永久一行 Toolbox 升级到 release25，确认 Build 后再次执行“恢复为新网站”。目标域名由 OWNER 自行输入；DNS 不要求提前解析。预期离线成功应明确显示“离线验证通过 / 在线 Host/SNI 未执行 / Nginx 未启动、未重启、未重载”。

## Slot 3 release25 Owner Real Restore-As · Offline Recovery PASS

2026-10-01，OWNER 在保留的旧 Linode Recovery Copy（网站 `nginx.service` 有意保持停止）上完成 release25-era Restore-As 真机验证。目标域名由 OWNER 自行输入为 `444.ke.com`，未要求提前修改 DNS。

终端结果：

```text
source domain                        123.kewaro.com
target domain                        444.ke.com
CloudPanel target create             PASS
target site user                     p07444d03b6b
MySQL                                NO_MYSQL
application config                   NO_DATABASE
offline verification                 PASS / FILES_DB_NGINX_CONFIG
online Host / SNI                    NOT_RUN / SITE_NGINX_NOT_RUNNING
website Nginx start                  NOT_RUN
website Nginx restart                NOT_RUN
website Nginx reload                 NOT_RUN
source certificate reused            NO
new certificate                      DNS_REQUIRED_FOR_NEW_CERTIFICATE
DNS write                             NO
SOURCE delete                         NO
existing target overwrite             NO
```

OWNER 可见结果明确为：

```text
恢复为新网站完成 · 离线验证通过 ✓
离线验证：通过 · 文件 / DB / Nginx 配置
在线 Host / SNI：未执行 · 网站 Nginx 当前未运行
Nginx：未启动、未重启、未重载
DNS：未修改
原网站：未删除、未覆盖
```

这完成了 release25 的**离线 Recovery Restore-As Owner Real Use PASS**。它不是完整在线 Restore PASS：网站 Nginx 仍未运行，因此 Host / SNI 在线验证按设计保持 NOT_RUN。

本张截图没有把 `--build-id` 与恢复结果同时显示在同一画面，所以 exact installed Build 证据仍单独管理；但该结果页与 release25 新增的 `OFFLINE_STATIC / RESTORE_AS_OFFLINE_VERIFIED` 行为一致。

Current Owner truth：

```text
release25 Owner Real Use                       PASS_OFFLINE_STATIC_RECOVERY
offline restore layer                          PASS
online Host/SNI layer                          NOT_RUN
DNS write                                      NO
SOURCE delete                                  NO
Existing target overwrite                      NO
Automatic website Nginx start/restart/reload   NO
Full online Restore PASS                       NOT_YET_PROVEN
```

下一步不需要为了该结果继续开发 release26。若要证明完整在线 Restore PASS，应在网站 Nginx 正常运行的环境中独立验证 ONLINE 路径；保留旧 Linode Recovery Copy 不因本次离线 PASS 自动启动网站 Nginx。

## Slot 3 release26 source candidate · old-server whole-site switch

OWNER 在 release25 Restore-As 离线 Recovery PASS 后明确补充迁移需求：迁移脚本停掉旧服务器网站服务以后，必须有一个对应的“重新开启旧服务器全部网站”能力，而且普通用户不能被迫理解 Nginx、端口或 systemd 等内部实现。

release26 Source Candidate 已实现并完成一轮 Beginner UX 收敛。普通迁移界面固定为：

```text
服务器迁移
→ 旧服务器网站开关

当前状态：
→ 旧服务器全部网站已开启
或
→ 旧服务器全部网站已停止

1. 开启旧服务器全部网站
2. 停止旧服务器全部网站
0. 返回
```

普通界面不再暴露：

```text
nginx.service
clp-nginx.service
80 / 443
8443
systemctl
nginx -t
START_NGINX / STOP_NGINX
```

复杂安全逻辑继续保留在后台，不改变已有合同：

```text
开启
→ 检查网站服务当前状态
→ 已开启则直接结束
→ OWNER 中文确认“开启”
→ 后台先做配置检查
→ 只启动网站服务
→ 回读状态确认成功

停止
→ 检查网站服务当前状态
→ 已停止则直接结束
→ OWNER 中文确认“停止”
→ 只停止网站服务
→ 回读状态确认成功

CloudPanel 后台服务                  = 不动
DNS                                  = 不改
SOURCE                               = 不删
existing target                      = 不覆盖
迁移成功后自动重新开启旧服务器网站       = NO
```

这仍然是整台旧服务器的网站总开关，不是逐站开关。OWNER 不需要一个网站一个网站处理。

Exact Source identities：

```text
Source Build                         0.1.0-release26
Nginx-control feature merge          a4efc4be853bbf0b79ee3c53cbd37eb3b9bad21e
Feature main CI                      36894317890 PASS
release26 Candidate exact-source CI  36897336937 PASS
release26 Source main                b48f14273f06357b2e7fb8abb223486c80302270
release26 Source main CI             36898401114 PASS
Beginner UX simplification PR        #118
Beginner UX source merge             2a4a0065b247f5ba8d5614053c8a6275068155cd
Beginner UX main CI                  36903446105 PASS
```

Distribution / Production 保持独立：

```text
Public Distribution current          0.1.0-release25
release26 Public Distribution        NOT_RUN
release26 Production install         NOT_RUN
real old-server website on/off       NOT_RUN
DNS write                            NO
SOURCE delete                        NO
```

因此当前结论：

```text
SOURCE_IMPLEMENTATION                PASS
BEGINNER_UX_SIMPLIFICATION           PASS
SOURCE_CANDIDATE                     PASS
PUBLIC_DISTRIBUTION                  release25 / unchanged
PRODUCTION                           unchanged
OWNER_REAL_WEBSITE_SWITCH            NOT_RUN
```

下一步若 OWNER 明确要求“发布”，再独立进入 release26 Public Distribution Gate；在此之前永久一行 Toolbox 仍然是 release25，不得声称这个简化后的“旧服务器网站开关”已经在公共入口可用。

## release26 beginner UI freeze · old-server website switch

OWNER 明确要求该能力不得越做越复杂。release26 的普通迁移界面因此进一步冻结为**整台旧服务器网站的一键开 / 关**，不向普通用户暴露 Nginx / systemd / listener 等工程实现。

普通界面固定为：

```text
4. 旧服务器网站开关

当前状态：旧服务器全部网站已开启 / 已停止

1. 开启旧服务器全部网站
2. 停止旧服务器全部网站
0. 返回
```

普通界面不得重新暴露：

```text
nginx.service
clp-nginx.service
systemctl
nginx -t
80 / 443
8443
START_NGINX / STOP_NGINX 等机器确认词
```

用户确认词改为中文：

```text
开启
停止
```

后台安全合同完全不变：仍只操作网站服务；开启前必须完成配置检查；CloudPanel 后台服务不受控制；DNS 不自动修改；SOURCE 不删除。

Exact evidence：

```text
Beginner UI PR                   #118
Beginner UI exact-source CI      36902397147 PASS
Beginner UI main merge           2a4a0065b247f5ba8d5614053c8a6275068155cd
Beginner UI main CI              36903446105 PASS
Source Build                     0.1.0-release26
Public Distribution              0.1.0-release25 / unchanged
Production                       unchanged
```

该条作为后续开发约束：**复杂逻辑可以留在后台，普通菜单只展示用户需要知道的状态、动作和结果。**

## release28 · initialization first-level separation + standard Y/N confirmations

OWNER real-use on release27 exposed two ordinary-UX issues:

1. Linux terminal confirmation must use standard Y/N instead of requiring Chinese words such as “开启 / 停止”.
2. Server initialization must be a standalone script and a P07 first-level menu item, not embedded inside the migration flow or duplicated inside System Care.

release28 freezes the ordinary IA as:

```text
P07 first-level menu

1. 网络代理节点（V2Ray）
2. 服务器性能检测（VPS 验机）
3. 网站与数据（CloudPanel）
4. 服务器维护 / 安全
5. 初始化服务器
0. 退出
```

Initialization implementation remains the standalone `bin/vfops-init-ui` script. Toolbox item 5 prepares the current VF Server Ops runtime if needed and launches that script directly.

Migration boundary is now explicit:

```text
current server CloudPanel ready
→ migration may continue

current server not initialized
→ migration stops
→ tell OWNER: return to first-level menu → 5. 初始化服务器
→ migration does NOT install / initialize CloudPanel
```

Ordinary confirmation input is standardized:

```text
开启这台服务器全部网站？ [y/N]
停止这台服务器全部网站？ [y/N]
应用初始化基础项？        [y/N]
安装 CloudPanel？         [y/N]
```

Machine confirmation tokens remain backend-only and are not exposed to ordinary users.

System Care is simultaneously simplified to remove the duplicated initialization entry:

```text
1. 服务器体检
2. 日常维护
3. 安全检查
4. P07 检查 / 修复
5. 最近操作
0. 返回
```

Exact identities and proof:

```text
Source Build                         0.1.0-release28
Source PR                            #121
Source candidate CI                  36914704500 PASS
Source main                          2265bd2b69c0ddd82ebc07eb01ad7c156ef78507
Source main CI                       36915934302 PASS

Public Distribution PR              #1706
Public main                          03b0549c52ba10ced6eb1e92e4655b34004b11db
Release28 Distribution Gate          36917500446 PASS
Toolbox Smoke                        36917500367 PASS
System Care Smoke                    36917500505 PASS
Beginner Menu Gate                   36917500523 PASS
Stable Installer Smoke               36917500600 PASS
Public Runner Trigger Scope          36917500563 PASS
Workflow Archive Integrity           36917500494 PASS

Public main Toolbox Smoke             36917600701 PASS
Public main System Care Smoke         36917600697 PASS
Public main Current Self Test         36917600514 PASS
Public main Stable Installer Smoke    36917600557 PASS

Runtime manifest blob                5eb6a7461f38d073005fe6f98fe79b3063431187
Final installer blob                 083d5e16e9e03a23274e12c696e52ecb0521718d
Stable installer blob                ab53dde1627b88e358edda1677f50f5e524fc7a5
Toolbox blob                         8b76392af65e544067efe78c811a8f5e7081b097
System Care                          0.1.0-rc19
```

Current Production / Owner truth remains independent:

```text
release28 Public Distribution        PASS
release28 Production install         NOT_YET_OWNER_VERIFIED
release28 initialization real-use    NOT_RUN
DNS write                            NO
SOURCE delete                        NO
```

This supersedes the release26 ordinary-confirmation wording that required Chinese action words. The backend safety checks remain unchanged; only the ordinary interaction and information architecture were simplified.

## release29 · Beginner Menu / Naming Closure

release29 closes the ordinary-user information architecture for first-level menus 3 / 4 / 5.

User-facing product name:

```text
服务器工具箱
```

Internal engineering identifiers such as `P07`, repository names, Build IDs and machine confirmation tokens remain internal and must not be used as ordinary menu/page names.

Frozen first-level ordinary menu:

```text
1. 网络代理节点
2. 服务器性能检测
3. 网站与数据
4. 服务器维护与安全
5. 初始化服务器
0. 退出
```

Menu 3 is frozen as:

```text
网站与数据

1. 网站与数据概况
2. 备份与恢复
3. 服务器迁移
4. 网站管理
5. 网站面板（CloudPanel）
0. 返回
```

Website Management no longer exposes a flat list of technical actions. After selecting an existing site it uses grouped actions:

```text
1. 网站概览
2. 网站健康检查
3. 数据库
4. 网站证书（HTTPS）
5. 权限与缓存
98. 更换网站
0. 返回
```

Creating a website belongs to Website Management. Website Panel keeps only panel-level settings:

```text
1. 登录安全
2. 面板用户
3. 面板状态检查
0. 返回
```

Migration naming and routing are frozen as:

```text
1. 迁入整台旧服务器
2. 迁入一个网站
3. 继续未完成迁移
4. 旧服务器网站开关
0. 返回
```

Migration dependencies are lazy: entering the migration menu does not prepare SSH / rsync. Those components are prepared only after selecting a migration action. The old-server website switch operates the current machine directly and does not trigger migration dependency setup.

Menu 4 is frozen as:

```text
服务器维护与安全

1. 服务器健康检查
2. 日常维护
3. 安全检查
4. 工具检查 / 修复
5. 最近操作
0. 返回
```

WordPress-specific security is explicitly named `WordPress 网站安全`.

Menu 5 is frozen as:

```text
初始化服务器

1. 应用基础设置（时区 / Swap）
2. 检查 / 安装 CloudPanel
0. 返回
```

`重新检查` and `查看初始化完成条件` are removed as redundant ordinary actions.

Ordinary confirmation input is standardized to `[y/N]`. Machine confirmation tokens remain backend-only.

Exact release evidence:

```text
Source Build                         0.1.0-release29
Source PR                            #123
Source candidate CI                  36988875935 PASS
Source main                          ce51e3effe51df3627bd0cc5149b34af1eae3cfd
Source main CI                       36993188227 PASS

Public Distribution PR              #1731
Public main                          717fd9e84cbb3bbb947f7f485942af4ce8ff60b5
Release29 Distribution Gate          37000577393 PASS
Toolbox Smoke                        37000577542 PASS
Beginner Menu Gate                   37000577592 PASS
Stable Installer Smoke               37000577524 PASS
Public Runner Trigger Scope          37000577467 PASS
Workflow Archive Integrity           37000577403 PASS

Public main Toolbox Smoke             37000742894 PASS
Public main Stable Installer Smoke    37000742917 PASS
Public main Current Self Test         37000742928 PASS

Runtime manifest blob                ca410a2be01fb9a93bde54085187027560f8cffb
Final installer blob                 23c9e50d6fe4106047307ed4701665833002af36
Stable installer blob                48cfffb2d9ba8ee98f2acc1fa11f02d72c4227d5
System Care                          0.1.0-rc20
```

Production / Owner acceptance remains independent:

```text
release29 Public Distribution        PASS
release29 Production install         NOT_YET_OWNER_VERIFIED
release29 Owner real use             PENDING
DNS write                            NO
SOURCE delete                        NO
```

Menu 3 / 4 / 5 IA is now frozen. Future changes should be limited to real functional defects, missing capabilities with clear ownership, or evidence-backed usability issues; do not reopen broad menu redesign by default.



## release49 · New-server initialization submenu simplification

OWNER 在 release48 Vultr 真机完成「一键初始化服务器」Owner Product PASS 后，确认初始化子菜单不应继续保留被完整流程覆盖的重复入口。

普通界面收敛为：

```text
初始化服务器

1. 一键初始化服务器（推荐）
0. 返回
```

删除普通入口：

```text
2. 基础设置（时区 / Swap）
3. CloudPanel 状态 / 安装
```

功能并未删除：时区、Swap、CloudPanel 检查 / 安装继续由「一键初始化服务器」内部按既有安全规则执行；已正确项目自动保持 / 跳过，健康 CloudPanel 不重复安装。

本次仅做可逆 UI / IA 简化，不改变：

```text
resource tuning single-source implementation
CloudPanel bootstrap safety preflight
DNS write = NO
SOURCE delete = NO
Production migration = NO
automatic website Nginx stop/restart = NO
```

Source Build：`0.1.0-release49`。


## release50 · Fresh CloudPanel database readiness closure

release49 Owner real-use on a freshly initialized Vultr server exposed one remaining timing gap:

```text
CloudPanel install + post-install health PASS
→ resource tuning starts immediately
→ clpctl root database credential output is not ready yet
→ MYSQL_MASTER_CREDENTIAL_PARSE_FAILED
→ performance tuning correctly stops fail-closed
```

release50 keeps the single resource-tuning implementation and fixes the readiness boundary inside the canonical System Care engine.

Canonical behavior:

```text
_mysql_client()
→ first try the official CloudPanel master-credentials path
→ on credential-not-ready / local-login-not-ready only:
   bounded retry = 13 attempts total / 5 seconds between attempts
→ credential command timeout still fails closed immediately
→ all unrelated safety blockers still fail closed immediately
→ password is never printed or persisted
```

This does not duplicate credential, Apply, Verify or Rollback logic in initialization.

Identities:

```text
Source Build       0.1.0-release50
System Care tuning 0.1.0-rc27
```

Safety boundaries unchanged:

```text
DNS write = NO
SOURCE delete = NO
Production migration = NO
automatic website Nginx stop/restart = NO
```


## release51 · CloudPanel CLI wrapper execution compatibility

release50 Owner real-use disproved the pure-readiness hypothesis: bounded retry still ended in
`MYSQL_MASTER_CREDENTIAL_PARSE_FAILED`.

CloudPanel official documentation keeps `clpctl db:show:master-credentials` as the root command.
CloudPanel's own issue tracker documents CLI 6.0.8 installations where `/usr/bin/clpctl` begins
with malformed `#/bin/bash`; interactive Bash can execute it, but programmatic / nested-shell
execution can fail.

release51 fixes only the canonical System Care credential invocation layer:

```text
resolve clpctl path
→ inspect first line
→ if it is a Bash wrapper:
     exec bash /usr/bin/clpctl <official command>
→ otherwise:
     exec clpctl <official command>
→ existing parser / secret handling / retry / Apply / Verify / Rollback unchanged
```

The tool does not edit `/usr/bin/clpctl`, does not reveal or persist the database password, and
does not reintroduce the removed legacy `db:show:credentials` path.

Identities:

```text
Source Build       0.1.0-release51
System Care tuning 0.1.0-rc28
```

Safety boundaries remain unchanged:

```text
DNS write = NO
SOURCE delete = NO
Production migration = NO
automatic website Nginx stop/restart = NO
```


## release52 · CloudPanel credential execution-context fallback

release51 Owner real-use still ended at `MYSQL_MASTER_CREDENTIAL_PARSE_FAILED`, so the issue is not
only the known malformed shebang case.

CloudPanel's current documentation shows `db:show:master-credentials` returning a two-column
`Name / Value` table with `Host / User Name / Password / Port`. The existing parser already
accepts that structure. release52 therefore hardens only command execution semantics:

```text
official command
  clpctl db:show:master-credentials
      ↓
primary invocation
      ↓ if no usable structured credentials
Bash login-shell invocation of the same official command
      ↓
parse complete credential structure even if wrapper exit code is non-zero
      ↓
mandatory real MySQL SELECT 1 validation
      ↓
Apply / Verify / Rollback
```

A non-zero clpctl exit code never authorizes a write by itself. Parsed credentials must still pass
the existing live MySQL connection validation before any tuning mutation can proceed.

No raw command output, password, token, or secret is shown or persisted.

Identities:

```text
Source Build       0.1.0-release52
System Care tuning 0.1.0-rc29
```

Safety boundaries unchanged:

```text
DNS write = NO
SOURCE delete = NO
Production migration = NO
automatic website Nginx stop/restart = NO
```


## release53 · Fresh empty-server MySQL credential recovery

Owner diagnostic on the Vultr initialization target established the real failure shape:

```text
uid=0
/usr/bin/clpctl first line = #/bin/bash
db:show:master-credentials via Bash wrapper:
  rc=0
  stdout=0
  stderr=0
db:show:master-credentials via Bash login shell:
  rc=0
  stdout=0
  stderr=0
db:show:master-password:
  timeout
```

Therefore release50-release52 compatibility changes were not sufficient: there was no credential
payload to parse.

release53 adds one narrowly-scoped recovery path for new-server initialization only:

```text
vfops-init-ui
→ read CloudPanel db.sq3 read-only
→ require site count = 0
→ require registered database count = 0
→ set P07_FRESH_INIT_EMPTY_SERVER=1 only when both are zero
→ canonical System Care resource engine
→ credential lookup parse/timeout failure
→ restart mysql ONCE
→ require mysql service active
→ retry official CloudPanel credential lookup
→ mandatory MySQL SELECT 1
→ normal Apply / Verify / Rollback
```

Ordinary System Care does not set the recovery flag.
Any CloudPanel site or registered database disables automatic MySQL restart.
The recovery never modifies DNS, Nginx, websites, databases, or the clpctl file itself.

Identities:

```text
Source Build       0.1.0-release53
System Care tuning 0.1.0-rc30
```

Safety boundaries:

```text
DNS write = NO
SOURCE delete = NO
Production migration = NO
automatic website Nginx stop/restart = NO
automatic MySQL restart on existing CloudPanel workloads = NO
fresh empty-server MySQL recovery = AT MOST ONCE
```


## release54 · CloudPanel CLI 6.0.8 shebang root-cause closure

Owner diagnostic on the Vultr target proved the installed CloudPanel CLI wrapper itself is malformed:

```text
/usr/bin/clpctl first line = #/bin/bash
db:show:master-credentials:
  rc=0
  stdout=0
  stderr=0
db:show:master-password:
  timeout
```

This matches the known CloudPanel CLI 6.0.8 wrapper defect where the first line is `#/bin/bash`
instead of `#!/bin/bash`. release53's speculative MySQL restart recovery is therefore removed.

release54 behavior:

```text
new-server initialization
→ CloudPanel ready
→ inspect the resolved clpctl executable
→ ONLY when first line is exactly "#/bin/bash"
→ cp -a backup under /var/lib/vf-server-ops/vendor-backups/
→ rewrite only the first line to "#!/bin/bash"
→ bash -n verification
→ atomic replacement
→ canonical System Care resource-apply.sh
→ official CloudPanel credential lookup
→ mandatory MySQL SELECT 1
→ normal Apply / Verify / Rollback
```

The repair is intentionally narrow:
- no generic clpctl rewrite;
- no password output or persistence;
- no MySQL restart;
- no Nginx restart;
- no DNS change;
- no website/database deletion;
- if the first line is anything other than the exact known bad value, the file is left untouched.

Identities:

```text
Source Build       0.1.0-release54
System Care tuning 0.1.0-rc31
```

release53 is superseded for Owner Product validation.


## release55 · CloudPanel stored master credential fallback

Owner validation after release54 still ended at `MYSQL_MASTER_CREDENTIAL_PARSE_FAILED`.
The release54 vendor-wrapper repair did not close the real initialization failure, so P07 no longer
rewrites CloudPanel's `clpctl` file during initialization.

CloudPanel already stores its encrypted database-server master password in its local SQLite state.
release55 keeps the official CLI path first, then falls back to CloudPanel's own stored credential
when the CLI produces no usable payload:

```text
official clpctl master-credentials
→ official clpctl master-password
→ if still no usable credential:
   read /home/clp/htdocs/app/.env
   read encrypted password from data/db.sq3 / database_server
   decrypt in memory with CloudPanel's bundled Defuse Crypto
→ mandatory local MySQL SELECT 1
→ Apply / Verify / Rollback
```

Security properties:

```text
password shown to Owner = NO
password persisted by P07 = NO
secret placed in process argv = NO
CloudPanel vendor file rewrite = NO
MySQL restart = NO
website Nginx restart = NO
DNS change = NO
```

The fallback is part of the single canonical System Care credential resolver, not a second tuning
implementation.

Identities:

```text
Source Build       0.1.0-release55
System Care tuning 0.1.0-rc32
```


## release56 · CloudPanel 2.5.4 current APP_SECRET path

release55 Owner real-use on the Debian 13 / CloudPanel 2.5.4-3+clp-trixie target proved the stored-credential fallback was correct in principle but read the wrong env location.

Owner no-secret diagnostics established:

```text
/home/clp/htdocs/app/files/vendor/autoload.php = present
/home/clp/htdocs/app/data/db.sq3              = present
PHP SQLite3                                    = present
Defuse Crypto                                  = present
/home/clp/htdocs/app/.env                      = absent
/home/clp/htdocs/app/files/.env                = present
APP_SECRET location                            = /home/clp/htdocs/app/files/.env
root MySQL socket login without credential     = unavailable
```

release56 fixes only the canonical System Care credential resolver:

```text
official clpctl master-credentials
→ official clpctl master-password
→ stored credential fallback
→ prefer /home/clp/htdocs/app/files/.env
→ retain /home/clp/htdocs/app/.env only as narrow legacy-layout compatibility
→ decrypt database_server.password in memory with bundled Defuse Crypto
→ mandatory local MySQL SELECT 1
→ normal Apply / Verify / Rollback
```

No secret is displayed, persisted by P07, or placed in process argv. Initialization still calls the single formal System Care resource-apply implementation. No MySQL restart, website Nginx restart, DNS write, migration, or vendor-file rewrite is added.

Identities:

```text
Source Build       0.1.0-release56
System Care tuning 0.1.0-rc33
```


## release57 · CloudPanel native crypto credential closure

release56 Owner real-use proved the current env path was correct but direct Defuse decryption with APP_SECRET was not:

```text
Build                                      0.1.0-release56
System Care                                0.1.0-rc33
files/.env                                 present
APP_SECRET                                 readable
SQLite database_server.password            present
Direct Defuse decryptWithPassword          FAIL
MySQL SELECT 1                             NOT_RUN
```

Additional source investigation found the actual CloudPanel application pattern: `DatabaseServer::getDecryptedPassword()` delegates to CloudPanel's own `App\\Service\\Crypto::decrypt()`, which owns the real encryption-secret semantics. P07 therefore stops assuming that Symfony APP_SECRET is the database credential encryption password.

release57 canonical credential resolver:

```text
official clpctl master-credentials
→ official clpctl master-password
→ stored credential fallback
→ load CloudPanel bundled autoloader
→ read database_server.password from local SQLite
→ prefer CloudPanel App\\Service\\Crypto::decrypt()
→ only if that service is unavailable/fails, retain the already-known legacy direct-Defuse compatibility path
→ mandatory local MySQL SELECT 1
→ normal Apply / Verify / Rollback
```

Security properties remain unchanged:

```text
password shown to Owner = NO
password persisted by P07 = NO
secret placed in process argv = NO
CloudPanel vendor file rewrite = NO
MySQL restart = NO
website Nginx restart = NO
DNS change = NO
```

Identities:

```text
Source Build       0.1.0-release57
System Care tuning 0.1.0-rc34
```


## release58 · empty-server tuning no longer depends on database credentials

Owner real-use after release57 identified the architectural issue: the current target is a newly initialized CloudPanel machine with no websites and no managed databases. New-server initialization should not fail solely because CloudPanel's internal database master credential cannot be obtained.

release58 keeps the single-source tuning rule but separates **empty-server initialization semantics** from **existing-workload runtime tuning**.

Canonical flow:

```text
vfops-init-ui
→ resource-profile.sh
→ resource-apply.sh apply-empty-server-confirmed-json
→ lib/resource_apply.py
→ independently prove CloudPanel workload is empty
   site = 0
   database = 0
   referenced PHP pool = 0
→ use the same calibrated VF-RP-2G-1C-BALANCED CAP-ONLY plan
→ backup + atomic persistent MySQL config write
→ mysqld --validate-config
→ exact persistent value readback
→ service/Nginx health verification
→ prove workload is still empty
→ receipt + rollback state
```

Explicit boundaries:

```text
CloudPanel/MySQL master credential required = NO for proven-empty initialization
MySQL SET GLOBAL                            = NO for proven-empty initialization
MySQL restart/reload                       = NO
Nginx restart/reload                       = NO
website/database secret read               = NO
existing workload auto-tuning              = NO from initialization
normal System Care runtime path             = unchanged
single tuning engine                        = YES
```

The UI may declare the profile applied and verified only after the persistent configuration transaction and validations succeed, and must explicitly state that verification is at the persistent configuration layer with no MySQL/Nginx restart.

Identities:

```text
Source Build       0.1.0-release58
System Care tuning 0.1.0-rc35
```


## release59 · migration first-use flow + helper staging root cause

Owner real-use on the freshly initialized Vultr target reached migration authentication successfully:

```text
old server SSH       READY
old CloudPanel       DETECTED
managed migration key READY
```

but the first migration plan then failed at:

```text
cannot stage migration helper on old server
exit_code=13
```

Live distribution readback found the actual source-side packaging defect: the installed P07 runtime is assembled from the rc2 base plus the current RUNTIME manifest. `VF_PROJECT.json` is not part of that installed runtime, but `stage_source_runtime()` still tried to archive it. The local tar therefore failed before a valid helper archive could be streamed, and the wrapper misleadingly surfaced that as an old-server staging failure.

release59 fixes both observed Owner issues:

```text
Migration first-use UX:
old server IP
→ existing SSH key check
→ if no access: directly explain one-time root password handoff
→ system ssh-copy-id password prompt
→ dedicated migration SSH key
→ continue plan
```

There is no intermediate "prepare migration key" submenu.

Helper staging now packages only files guaranteed to exist in the installed runtime:

```text
bin/
lib/
VERSION
BUILD_ID
```

`VF_PROJECT.json` is not required by the source-side migration helper and is no longer included.
A local archive failure is also classified as a current-server runtime packaging problem instead of being falsely reported as an old-server failure.

Security and migration boundaries remain unchanged:

```text
Owner password read by P07 = NO
Owner password stored by P07 = NO
password recipient = system ssh-copy-id only
DNS automatic change = NO
old server delete = NO
existing target overwrite = NO
real Production migration = NOT_RUN by release
```

Identity:

```text
Source Build 0.1.0-release59
```


## release60 · CloudPanel database-server readiness + Vultr installer closure

Owner real-use on the release59 fresh Vultr receiver proved that CloudPanel could pass the old P07 "ready" check while its internal database-server layer was absent.

No-secret readback:

```text
P07 Build                   0.1.0-release59
migration state             PREPARE_FAILED
target site                 ilovem3u8.kewaro.com = CREATED
MySQL service               active
target database marker      NO
target MySQL database files NO
CloudPanel database row     NO
CloudPanel cloud provider   NOT_SET

database_server rows        0
active rows                 0
engine/version              NONE
host/user/password metadata absent
```

This proves the first database failure happened before SQL import or WordPress config remap. CloudPanel had no active database-server metadata for `db:add` to use.

The P07-owned defect was broader than provider metadata: `cloudpanel_ready_local()` treated only `clpctl + db.sq3` as a complete CloudPanel install. That allowed an incomplete panel install to be declared healthy and later accepted as a migration target.

release60 closes that false-positive path:

```text
fresh CloudPanel install
→ detect provider from local DMI
→ Vultr -> CLOUD=vultr
→ DB_ENGINE=MYSQL_8.4
→ installer checksum verification
→ clpctl + db.sq3 verification
→ require >=1 active database_server row
→ require non-empty host / user / encrypted password metadata
→ only then CLOUDPANEL_READY
```

CloudPanel's current Vultr installation documentation uses `CLOUD=vultr DB_ENGINE=MYSQL_8.4`. Generic installation remains a documented path for other providers, so release60 does not claim that a missing CLOUD value alone explains every possible incomplete installation. The decisive P07 closure is the stronger post-install/readiness contract.

Migration fail-closed behavior:

```text
target preflight with incomplete CloudPanel -> BLOCK
resume PREPARE_FAILED with incomplete DB server -> BLOCK before further writes
target-status -> CLOUDPANEL_INCOMPLETE_DATABASE_SERVER
```

P07 does **not** synthesize or directly write CloudPanel internal master-database credentials to repair an already incomplete installation. That would cross the secret/internal-state boundary and could create a panel/MySQL mismatch. An already broken empty receiver should be rebuilt cleanly and initialized again after this fix.

Unchanged safety boundary:

```text
DNS automatic change       NO
old server deletion        NO
Production cutover         NO
existing target overwrite  NO
MySQL/Nginx forced restart NO
Owner secret input to P07  NO
```

Identity:

```text
Source Build 0.1.0-release60
System Care  0.1.0-rc35 (unchanged)
```


## release61 · CloudPanel first-admin lifecycle closure

Owner real-use on a freshly rebuilt Vultr receiver with release60 proved that `database_server=0` immediately after installation is not automatically evidence of a broken installer.

CloudPanel's first-run lifecycle creates the local database-server master record only after the first CloudPanel user exists and a subsequent application/CLI request runs. Official documentation also instructs the operator to create the first administrator immediately after installation.

release60 correctly blocked migration on a receiver with no active database-server metadata, but it incorrectly classified the normal zero-user first-run state as an incomplete installation.

release61 models the lifecycle explicitly:

```text
fresh empty server
→ install CloudPanel with pinned installer
→ clpctl + db.sq3 present
→ users = 0 and database_server = 0
→ CLOUDPANEL_ADMIN_REQUIRED
→ P07 asks locally for first admin username/email/password
→ password input is hidden in the local terminal
→ official clpctl user:add creates the first admin
→ next official CloudPanel CLI request triggers CloudPanel's own database-server initialization
→ require active database_server + host/user/encrypted password metadata
→ CLOUDPANEL_READY
→ continue performance tuning
```

Security and ownership:

```text
admin password sent to ChatGPT = NO
admin password written to P07 logs = NO
database master password requested from Owner = NO
database master password displayed = NO
CloudPanel SQLite master row synthesized by P07 = NO
CloudPanel/MySQL internal password generated by P07 = NO
CloudPanel first-user creation = official clpctl
CloudPanel DB-server initialization = CloudPanel's own first-run listener
DNS change = NO
migration/cutover = NO during initialization
```

If CloudPanel already has one or more users but still lacks an active database-server record, the state remains `CLOUDPANEL_INCOMPLETE_DATABASE_SERVER` and stays fail-closed; release61 does not weaken the release60 true-positive safety gate.

Identity:

```text
Source Build 0.1.0-release61
System Care  0.1.0-rc35 (unchanged)
```


## release62 · migration DB import root-context + live rsync progress

Owner real-use on release61 produced a precise target-side state for the first migrated database:

```text
Build                0.1.0-release61
migration state      PREPARE_FAILED
domain               ilovem3u8.kewaro.com
database             kewaro-ilovem3u8
target DB marker     YES
CloudPanel DB row    YES
wp-config.php        YES
```

P07 writes the private target database marker only after `clpctl db:add` succeeds and before `db:import`. Therefore database creation is proven complete; the previously combined "import/config remap" error hid the remaining failure stage.

CloudPanel's CLI database import/export authorization resolves the calling system user through `SUDO_USER`. A direct root shell may legitimately have no `SUDO_USER`. release62 normalizes that root execution context in the centralized CloudPanel adapter by setting an in-memory child-process environment value `SUDO_USER=root` only when the P07 process is already effective UID 0 and no SUDO_USER is present. No password/token is added or persisted.

Database errors are now separated:

```text
db:add failure                -> target database creation/recreation failure
db:import failure             -> new-server MySQL import failed
application config remap      -> new-server application DB config remap failed
verification export/fingerprint remains its own existing gate
```

Migration transfer progress is also no longer hidden by JSON capture:

```text
UI sets VFOPS_MIGRATION_PROGRESS=1 for prepare/resume/cutover
rsync uses --info=progress2,stats2 --human-readable
progress stdout/stderr is streamed live to the terminal via stderr
final machine JSON remains isolated on stdout for the UI parser
```

Owner can therefore see transferred bytes, percentage and throughput during multi-GB site copies while resumable migration state and machine-readable results remain intact.

Safety boundary remains unchanged:

```text
DNS automatic change       NO
old server deletion        NO
Production cutover         NO during prepare/resume
existing target overwrite  NO
database secrets displayed NO
migration state preserved  YES
```

Identity:

```text
Source Build 0.1.0-release62
System Care  0.1.0-rc35 (unchanged)
```


## release63 · external asset file/directory rsync type-safe resume

Owner real-use on release62 proved live rsync progress is visible, then exposed a different prepare-stage defect after the already-staged site/database work resumed.

A hidden external asset matched by the existing `.vf*` discovery rule was a regular file. The target-pull external sync path incorrectly pre-created every external asset as a directory and then forced a trailing slash on the old-server rsync source. rsync therefore tried to `change_dir` into a regular file and returned code 23.

release63 makes external-path semantics explicit and remains compatible with the already-created PREPARE_FAILED migration state:

```text
old-server external path -> probe as FILE or DIRECTORY
DIRECTORY -> keep directory/content rsync semantics
FILE      -> exact-file rsync semantics, no trailing slash
release62 empty wrong-type placeholder -> remove only if empty
non-empty wrong-type target            -> fail closed, never delete it
symlink / other / missing source type  -> fail closed
```

The generic pull primitive no longer infers old-server source type from whether the current local target happens to be a directory. Callers now own the trailing-slash semantics.

This specifically preserves resumability:

```text
existing migration id          PRESERVED
already PULLED_STAGED sites    SKIPPED
completed multi-GB data        NOT intentionally recopied
new migration task             NOT required
```

Safety boundary remains unchanged:

```text
DNS automatic change       NO
old server deletion        NO
Production cutover         NO during prepare/resume
existing unrelated overwrite NO
non-empty conflict deletion NO
Production Nginx stop/restart NO
database secrets displayed NO
```

Identity:

```text
Source Build 0.1.0-release63
System Care  0.1.0-rc35 (unchanged)
```


## release64 · local cutover smoke semantics + same-task retry

Owner real-use on release63 completed the resumed file/SQLite transfer and reached final local verification, then produced:

```text
new-server local verification failed: pass=13 fail=3
```

The pre-DNS local smoke used HTTPS root responses and required only 2xx/3xx. That is too strict for a reachability gate: a migrated site can intentionally return 401/403/404 at `/` while the vhost/runtime is correctly reachable. The old aggregation also hid which domains or inventory fields failed, and a successful automatic rollback moved the task into `CUTOVER_FAILED_ROLLED_BACK` without allowing the same migration ID to retry.

release64 changes only this bounded cutover verification/resume behavior:

```text
local pre-DNS probe:
  2xx/3xx/4xx + curl success -> reachable PASS
  5xx / 000 / transport error -> FAIL

inventory parity:
  still fail-closed
  domain + mismatch fields retained in target_smoke diagnostics

successful cutover rollback:
  same migration ID may re-enter final synchronization
  explicit Owner confirmation is still required
  no new migration task is created
```

Failure output now includes bounded domain/reason details instead of only pass/fail totals.

Safety boundary remains unchanged:

```text
DNS automatic change          NO
old server deletion           NO
existing unrelated overwrite  NO
automatic cutover without Owner confirmation NO
Production Nginx stop/restart by release      NO
secret output                 NO
5xx accepted as healthy       NO
```

Identity:

```text
Source Build 0.1.0-release64
System Care  0.1.0-rc35 (unchanged)
```


## release65 · migration long-wait progress visibility

Owner real-use on release64 showed a remaining UX defect: after confirming final synchronization, the migration can spend meaningful time in quiet non-rsync work (source runtime freeze, database export/import/verification, SQLite snapshotting, runtime activation, local smoke, DNS/public verification) before the next rsync line appears. The terminal therefore looks frozen even though the migration is still working.

release65 adds a single migration progress contract:

```text
file copy            -> exact rsync bytes / percentage / speed remains visible
quiet long operation -> moving indeterminate progress bar + elapsed time
cutover              -> explicit 1/7 .. 7/7 phase messages
site loop            -> current site index / total / domain
MySQL                -> export / transfer / import / verify phase
SQLite               -> consistency snapshot phase
rollback             -> target deactivation / source restoration phase
plan / status / DNS  -> indeterminate progress + elapsed time when waiting
```

The generic progress bar only appears while the migration command has produced no fresh stderr activity, so it supplements rather than replaces rsync progress.

This is observability/UI only. Migration state, data write order, confirmation gates and safety boundaries remain unchanged.

Identity:

```text
Source Build 0.1.0-release65
System Care  0.1.0-rc35 (unchanged)
```


## release66 · local readiness retry

Owner real-use on release65 isolated final local verification to `press.kewaro.com` returning HTTP 503 immediately after runtime activation. release66 adds a bounded local readiness retry: 10 attempts, 3 seconds apart. 2xx/3xx/4xx remain reachable PASS; 5xx/000 are retried and remain FAIL if persistent. Progress reports domain and attempt number. The same migration ID remains resumable after rollback. Build: `0.1.0-release66`; System Care remains `0.1.0-rc35`.


## release67 · PHP-FPM backend readiness repair

Owner real-use on release66 proved the remaining failures are persistent local HTTP 503s after ten retries. The known failing sites are PHP sites, not Node/PM2. release67 makes the local verification backend-aware: after the first PHP 5xx/000, P07 checks the exact phpX.Y-fpm service and the target vhost FastCGI listener. If the service is inactive it starts only that PHP-FPM service; if the service is active but the site listener is missing it performs a safe PHP-FPM reload and rechecks the listener. It never restarts/stops Nginx. Persistent HTTP failure after a healthy PHP-FPM backend still fails closed and carries backend status in diagnostics. Existing migration ID remains resumable. Build 0.1.0-release67; System Care remains 0.1.0-rc35.
