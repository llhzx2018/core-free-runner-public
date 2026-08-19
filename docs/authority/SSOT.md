# core-free-runner-public · Current Engineering SSOT

> 状态：`CURRENT / PUBLIC-SAFE MACHINE EVIDENCE INFRASTRUCTURE`  
> Rebaseline：2026-08-19

## 1. Truth Precedence

```text
Governance / Infrastructure Contract
→ main Workflow / Harness Source
→ GitHub Actions Run / Job / Artifact metadata
→ public-safe Evidence
→ README / historical trigger / temporary PR
```

Temporary PR、Request、Trigger 或历史 Sandbox 不得成为 Current Infrastructure Authority。

## 2. Runtime Model

```text
Private/Public Source Authority
→ exact Commit / Ref
→ GitHub Hosted Runner ephemeral VM
→ test environment provision
→ Machine Verification
→ sanitize / summarize
→ public-safe Evidence / Artifact
→ runner cleanup
```

本仓不保存被测试产品的 Canonical Source。

## 3. Public-safe Evidence Contract

Public Evidence 可包含：

- Repository / Project public identity；
- Exact Commit SHA / Tree SHA；
- Run / Job / Artifact ID；
- file count / bytes / SHA-256；
- PASS / FAIL / DEFERRED / BLOCKED 分类；
- Synthetic Fixture；
- 脱敏测试日志摘要。

不得包含：Private Source contents、PRIVATE_DATA、真实数据库、Secret Value、Session/Cookie、管理员密码、Production Backup 或任何不可公开文件副本。

## 4. Artifact Contract

Artifact 在生成前必须判断 `PUBLIC_SAFE`。若 Artifact 包含私有源码或 PRIVATE_DATA，应转入 `core-free-runner-private` 或只输出 metadata / digest；不得因为 Repository 本身 Public 就默认 Artifact 可公开。

## 5. Workflow Lifecycle

两类 Workflow：

```text
REUSABLE HARNESS
  -> 经过正式复用裁决后进入 main

ONE-OFF PROJECT WORKFLOW
  -> temporary branch / PR
  -> run
  -> record evidence
  -> close without merge
```

一次性 Workflow 失败可修复/重跑，但不能为了“留下证据”把临时代码永久合入 main。

## 6. Failure Semantics

```text
Machine PASS  = Independent evidence only
DEFERRED      != PASS
UNKNOWN       != PASS
Runner Failure != Product Failure
Billing / Permission / Route Failure != Product Failure
```

失败必须先分类 Product / Infrastructure / Credential / Routing / Test Harness / Environment。

## 7. Secret / Credential Contract

Credential 只通过 Actions Secrets / Runtime 注入。日志必须脱敏；任何 checkout URL、curl header、API response 或 exception 不得回显 Secret Value。

## 8. Branch / Sandbox Contract

`main` = 当前公共 Runner 基础设施。`develop` / temporary branches 可保留 sandbox / pilot；它们不是 Production-like branch，也不要求与 main 机械一致。

历史 `sandbox/*`、`requests/*`、trigger 文件是执行 Provenance，不自动成为 Current Contract。

## 9. Current Gate

```text
PUBLIC RUNNER ROLE: CURRENT
PUBLIC/PRIVATE DATA BOUNDARY: LOCKED
PUBLIC EVIDENCE PRIVACY: REQUIRED
TEMP PR CLOSE-NO-MERGE DEFAULT: LOCKED
THIRD TEST SPACE: NOT REQUIRED / NOT ALLOWED BY DEFAULT
PRODUCT RUNTIME CHANGE BY REBASELINE: 0
```
