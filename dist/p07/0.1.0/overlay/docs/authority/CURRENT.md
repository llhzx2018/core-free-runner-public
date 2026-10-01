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
Slot 3 CloudPanel Ops                = 0.1.0-release22 / ZH_BEGINNER_FIRST_V1 / CURRENT_RUNTIME_LAZY_V1 / TARGET_OWNED_PULL / TERMINAL_UX_V2 / WEBSITE_DATA_ONLY_V1
Slot 4 System Care                   = 0.1.0-rc18 / ZH_FIRST / PUBLIC_DISTRIBUTED
Automatic DNS mutation               = DENY
Automatic SOURCE deletion            = DENY
Resource Safe Apply auto-run         = DENY
Formal Release Tag                    = p07-v0.1.0
GitHub Release                        = PUBLISHED
Public Distribution                   = 3eeda218ab2f7d8fea6f498ba71c97265cc7d738
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

