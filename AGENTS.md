# core-free-runner-public Agent Instructions

## 仓库定位

`core-free-runner-public` 是 VF 固定的 **Public-safe GitHub Hosted Runner + Evidence 基础设施**，不是产品仓库、Release 仓库或私人数据仓。

## 开工前最小读取

按需读取：

1. `README.md`
2. `docs/authority/CURRENT.md`
3. 当前 `.github/workflows/`
4. 与本次任务直接相关的 Harness / Script / Test / Evidence

Current Truth 必须实时回读，不从旧窗口记忆、历史分支或旧 Workflow 名称推断。

## Runner Authority

固定测试空间只有：

```text
PUBLIC  = llhzx2018/core-free-runner-public
PRIVATE = llhzx2018/core-free-runner-private
```

`core-test-runner` = `DELETED / TOMBSTONE / MIGRATION PROVENANCE ONLY`。禁止把它作为兼容入口、fallback、执行目标或新任务路由，也不得为同类问题创建第三套长期 Runner / Test Storage。

## Public / Private Boundary

Public 允许：Synthetic Fixture、公开测试输入、公共 Harness、脱敏 Evidence、非敏感日志与测试元数据。

Public 禁止持久化：私人源码、PRIVATE_DATA、真实数据库、Production Backup、Secret Value、Session/Cookie、管理员凭据或其它私密资产。

经授权验证私有 Exact Source 时，只能通过 Runtime Secret 在 Hosted Runner 临时工作区 checkout；私有源码不得进入 Public Git History 或 Public Artifact，Job 结束后随临时环境清理。

## Git / Workflow Lifecycle

`main` 只承载经过治理晋级的 Current Runner 基线与可复用公共 Harness。禁止 Force Push、History Rewrite、直接把一次性项目验证写入 main。

默认治理链：

```text
controlled branch
→ PR
→ Exact Source
→ real Machine Gate
→ Owner Merge Gate（需要时）
→ main
→ remote readback
```

一次性项目验证默认使用 temporary branch / PR，Machine Evidence 完成后 **CLOSE WITHOUT MERGE**。只有被正式裁决为可复用公共 Harness 的内容才允许进入 main；这不等于增加长期注册 Workflow。

## Machine Truth

AI 不能自签 Machine PASS。

- `PASS`：机器真实执行且通过；
- `FAIL`：机器真实执行且失败；
- `BLOCKED_*` / `NOT_PROVEN`：没有获得成功机器证明，不得伪装成 PASS。

Harness / Assertion 自身错误必须与被测 Source FAIL 分开分类。

## 安全边界

Secret / Token 只通过 GitHub Actions Secrets / Runtime Injection 使用，不写入普通文件、Fixture、Artifact、日志或 Evidence。

未经明确授权，不执行 Release、Tag、Production、Destructive 操作，不修改无关产品仓或 `develop`。

## 用户中断原则

用户负责目标、重大治理裁决和高风险授权；用户不是 Runner / CI / Git / Shell Operator。能够通过现有 Runner、Repository、Credential 与只读发现完成的步骤，应由 Agent 自动完成后再汇报结果。
