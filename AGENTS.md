# core-free-runner-public · Agent Bootstrap

`core-free-runner-public` 是 VF 固定的 **Public-safe GitHub Hosted Runner + Evidence 基础设施**，不是产品仓、Release 仓或私人数据仓。

## 1. Authority First

进入本仓任务时默认只读：

```text
1. docs/authority/CURRENT.md
2. 与当前 bounded task 直接相关的 workflow / harness / script
3. 当前任务对应的 Run / Job / Artifact / Evidence（需要时）
```

禁止机械预载：

- `README.md`；
- 整个 `.github/workflows/`；
- 全部 Harness；
- 历史 branch / PR / Run / Artifact；
- Private Runner 内容；
- Credential inventory。

只有当前任务本身是 Runner governance / authority change 时，才继续读取 `INFRASTRUCTURE_CONTRACT.md`、`SSOT.md`、`ACCEPTANCE_MATRIX.md` 等稳定治理文件。

`README.md` 只做人读简介，不是 Current Authority。

## 2. Activation Boundary

本仓不是普通 VF 开发任务的默认入口。

只有当前任务已经证明需要独立 Machine Proof、Public-safe Harness/Evidence，或 native CI 已分类为 `BLOCKED_INFRA` 且需要已注册 fallback 时，才进入本仓。

固定：

```text
P0X != Runner activation
L2/L3 != Runner activation
Git change != Runner activation
Runner = on demand proof capability
```

## 3. Runner Authority

固定测试空间只有：

```text
PUBLIC  = llhzx2018/core-free-runner-public
PRIVATE = llhzx2018/core-free-runner-private
```

`core-test-runner` = `DELETED / TOMBSTONE / MIGRATION PROVENANCE ONLY`。

禁止为同类问题创建第三套长期 Runner / Test Storage；先复用已注册能力。

## 4. Public / Private Boundary

Public 允许：Synthetic Fixture、公开测试输入、公共 Harness、脱敏 Evidence、非敏感日志与测试元数据。

Public 禁止持久化：私人源码、PRIVATE_DATA、真实数据库、Production Backup、Secret Value、Session/Cookie、管理员凭据或其它私密资产。

经授权验证私有 Exact Source 时，只能通过 Runtime Secret 在 Hosted Runner 临时工作区 checkout；私有源码不得进入 Public Git History 或 Public Artifact。

## 5. Workflow Lifecycle

`main` 只承载 Current Runner 基线与已裁决为可复用的公共 Harness。禁止 Force Push / History Rewrite。

一次性项目验证默认：

```text
temporary branch / PR
→ exact-source machine proof
→ public-safe evidence
→ CLOSE WITHOUT MERGE
```

只有正式裁决为可复用公共能力的内容才允许进入 main；一次性验证不得长期扩张 Active Workflow Surface。

## 6. Machine Truth

AI 不能自签 Machine PASS：

```text
PASS          = 机器真实执行并通过
FAIL          = 机器真实执行后失败
BLOCKED_*     = 基础设施 / Evidence 阻塞
NOT_PROVEN    = 尚无独立 Machine Proof
```

Harness / Assertion / Runner 故障必须与被测 Source FAIL 分开分类。

## 7. Safety / User Boundary

Secret / Token 只通过 GitHub Actions Secrets / Runtime Injection 使用，不写入普通文件、Fixture、Artifact、日志或 Evidence。

未经明确授权，不执行 Release、Tag、Production、Destructive 操作，不修改无关产品仓。

用户负责目标、重大治理裁决和高风险授权；用户不是 Runner / CI / Git / Shell Operator。能通过当前已注册能力完成的执行、诊断与重试应由 Agent 自动完成。
