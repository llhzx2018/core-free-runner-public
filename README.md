# core-free-runner-public

VF 固定的 **Public-safe GitHub Hosted Runner + Evidence 基础设施**。

## Current Authority

唯一 Current 入口：[`docs/authority/CURRENT.md`](docs/authority/CURRENT.md)

```text
PUBLIC TEST STORAGE / EXECUTION = core-free-runner-public
```

允许：Synthetic Fixture、公开测试输入、可公开 Workflow/Harness、脱敏 Evidence、非敏感日志与测试元数据。

禁止持久化：私人源码、PRIVATE_DATA、真实数据库、Production Backup、Secret Value、Session/Cookie、管理员凭据。

经授权可以在 Hosted Runner 临时工作区通过 Runtime Secret checkout exact private source 做验证，但私有源码不得进入 Public Git History 或 Public Artifact，Job 结束后必须随临时环境清理。

一次性项目 Workflow / PR 默认：

```text
create temporary branch / PR
→ run
→ record public-safe evidence
→ close WITHOUT merge
```

只有被正式裁决为可复用公共 Harness 的代码才进入 main；这不等于增加长期注册 Workflow。

## 可复用 Harness

- [`WordPress Phase 3 通用 Harness V2`](harness/wordpress-phase3/README.md)：固定 WordPress/PHP/MariaDB 真实环境、RUN_ID 隔离、Job/Result 合同与安全 Cleanup；从已退役 `core-test-runner` 提炼，不包含历史项目 Payload 或 Workflow。

`develop` / sandbox / request / trigger 文件可以作为历史执行 Provenance，不要求机械合并到 main。

Secret / Token 只通过 Actions Secrets / Runtime 注入，不作为普通文件长期存储，日志必须脱敏。默认不创建第三套长期测试空间。

