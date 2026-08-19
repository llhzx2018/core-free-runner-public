# core-free-runner-public · Current Infrastructure Contract

> 状态：`CURRENT / PUBLIC-SAFE RUNNER INFRASTRUCTURE`  
> Repository：`llhzx2018/core-free-runner-public`  
> Rebaseline：2026-08-19

## 1. Role

`core-free-runner-public` 是 VF 固定的**公开 GitHub Hosted Runner 执行壳 + Public-safe Evidence 空间**。

它用于：

- Synthetic Fixture；
- 公开测试输入；
- 可公开 Workflow / Harness；
- 脱敏 Evidence；
- 非敏感日志与测试元数据；
- 在 GitHub Hosted Runner 临时工作区中读取 exact private source 后执行测试，但不得把私有源码持久化到公开仓库或 Artifact。

## 2. Public Boundary

允许进入公开 Git / Artifact / Evidence 的内容必须满足：

```text
PUBLIC_SAFE = YES
PRIVATE_SOURCE = NO
PRIVATE_DATA = NO
REAL_DATABASE = NO
SECRET_VALUE = NO
SESSION / COOKIE = NO
PRIVATE_BACKUP = NO
```

Hash、文件数量、测试状态、脱敏错误分类、公开 Synthetic Fixture 可保留；私有源码正文、真实业务数据、Token、Cookie、管理员凭据不可保留。

## 3. Private Source Transient Rule

经授权可通过 Runtime Secret 在 Hosted Runner 临时 checkout 私有仓库 exact Commit，用于 Machine Verification。

必须满足：

- private source 只存在 Runner 临时工作目录；
- Job 结束后由 Hosted Runner 生命周期清理；
- 不 commit 到 public repo；
- 不 upload 私有源码为 public Artifact；
- 日志不得打印源码 / Secret / PRIVATE_DATA；
- Evidence 仅保留 public-safe metadata / SHA / result。

## 4. Temporary Workflow / PR Rule

项目专用一次性 Workflow / Request / Trigger 可以在临时分支 / PR 中创建，用于受控验证。

完成后默认：

```text
Evidence PASS / FAIL recorded
→ temporary PR CLOSED WITHOUT MERGE
→ temporary workflow does not become main permanent contract
```

只有被明确裁决为可复用公共 Harness 的 Workflow 才允许进入 main。

临时 PR 不得因为“Runner 已运行”而机械合并。

## 5. Secret Boundary

Secret / Token 仅通过 GitHub Actions Secrets / Runtime 注入。Secret 名可以出现在 Workflow 合同中，Secret Value 永远不得进入：Git、Artifact、日志、Evidence、Issue/PR 正文、URL 或普通文件。

## 6. Role Separation

```text
core-free-runner-public  = public-safe execution + evidence
core-free-runner-private = private test input / private evidence when truly required
```

不得创建第三套长期测试空间解决普通路由问题。

## 7. Branch Boundary

`main` 是当前 Public Runner Workflow / Evidence 基础设施真相。

`develop` 可能保留历史 sandbox / pilot 写入，不保证与 main 同步；不得为了分支整齐机械 fast-forward / merge sandbox 内容到 main。

## 8. Non-goals

本仓不是：

- 产品源码仓；
- Release Asset 仓；
- 私有源码镜像；
- Production Backup；
- PRIVATE_DATA 长期仓；
- Secret Store；
- 用户个人电脑替代品。
