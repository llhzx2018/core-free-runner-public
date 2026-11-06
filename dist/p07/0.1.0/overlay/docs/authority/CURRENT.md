# P07 · VF Server Ops · CURRENT AUTHORITY RESOLVER

Status: `CURRENT_AUTHORITY_RESOLVER`  
Policy: `DYNAMIC_TRUTH_NOT_STORED_HERE`  
Authority: `llhzx2018/vf-server-ops` + each owning external authority

> 本文件位于 `main`，负责 **fresh-window 路由与 fail-closed 解析**，不把 Working Phase、Candidate Runtime SHA、Machine/Real Gate、Release、Production 或 Next Action 缓存成 main 的长期 Current Truth。

## 1. Current Development Line Pointer

```text
稳定产品合同与工程基线 = main
普通默认工作线 = main，已有任务按 exact branch / PR 继续
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
| 稳定产品合同 | 主分支 [需求开发书](RPD.md) / [SSOT](SSOT.md) / [验收矩阵](ACCEPTANCE_MATRIX.md) | 任务分支提供实现与证据，明确纳入任务的合同差异按候选核对 |
| Current working line | 本文件 branch pointer + live Git | branch 必须真实存在；任务开始时重新验证 |
| Current working runtime / BUILD_ID | exact working branch files | 不复制到 main Resolver |
| Current Phase / Next Action | OWNER instruction + exact working branch Current + live PR/Git | 不写进 main `VF_PROJECT.json` |
| Machine / Real evidence | exact-source workflow / registered Runner / evidence | `UNKNOWN / NOT_RUN != PASS` |
| Formal Release / Tag / assets | GitHub Release / Tag live-read | working branch merge不能外推 Release |
| Distribution | [公共 Toolbox 安装器](https://github.com/llhzx2018/core-free-runner-public/blob/main/installers/p07-toolbox.sh)及对应产品安装器、分发清单 | 核对精确模块、运行包和制品身份 |
| Production / Server state | OWNER-authorized runtime / Production evidence | 绑定现场构建、目标和操作范围 |
| 用户验收 | [用户验收说明](USER_ACCEPTANCE.md)与对应认证证据 | 按能力和任务核对安装、恢复、迁移与 DNS 后验证 |

## 4. Fail-Closed Rules

以下任一情况必须停止动态结论并标记 `RECOVERY_REQUIRED / UNKNOWN / NOT_PROVEN`：

- `current working authority branch` 不存在或已被替换；
- OWNER 当前任务与本 Pointer 指向不同且无法确定 exact branch/PR；
- main Resolver、working branch Current、live Git 相互冲突；
- 试图使用旧 `VF_PROJECT.json` 的 phase/status/next_action 作为当前事实；
- Machine evidence 没有绑定 exact source；
- Release / Distribution / Production 无法从 owning source live-read。

历史 Bootstrap、发布或安装记录只用于追溯。

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

## 8. 历史记录

此前累计的发行、候选、机器和实机记录完整保留在 [历史 Current 快照](https://github.com/llhzx2018/vf-server-ops/blob/aa0f6242f60033d626d9dc6543781322e6e32507/docs/authority/CURRENT.md)。[集成清单](P07_INTEGRATION_MANIFEST.json)是固定分发快照。新任务按本文件 §3 获取各自实时证据，勿把旧版本或当时的下一步作为当前判断。

[公共规范适用性](PUBLIC_AUTHORITY_APPLICABILITY.md)路由安全、数据、运行及发布所需的专项门禁。
