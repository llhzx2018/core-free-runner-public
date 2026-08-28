# 公共 Runner 历史 Workflow 归档

此目录保存已经退出 GitHub Actions 自动注册范围、但仍需保留 Git 历史与恢复能力的 Workflow。

规则：

- `.github/workflows/` 只放仍需要被 GitHub 注册的执行入口；
- `archive/workflows/` 中的 YAML 是被动历史材料，不会自动执行；
- 归档采用移动，不修改原 Workflow blob 内容；
- 恢复任何 Workflow 必须建立 Candidate、说明用途、重新限定触发路径并通过机器 Gate；
- 归档目录不得保存 Secret、私有源码、PRIVATE_DATA、真实数据库或生产备份。

## Current Archive Authority

当前机器入口：[`归档清单_V11.json`](归档清单_V11.json)。

V11 采用“封板基线 + 增量 Git Tree”结构，避免每次新增归档都重新复制数百条历史元数据：

- `归档清单_V10.json`：封板基线，421 个历史 Workflow；每个条目继续按 bytes + SHA-256 + source commit 验证；它是 V11 的历史基线，不再是 Current manifest。
- `2026-08/late-active-v11/`：V10 之后又进入 Active 注册区、但使命已经结束的 86 个 Workflow；从 `core-free-runner-public/main@e90d10a76f01f6166ed49516d44a82019205fe84` 原 blob 集合移动而来。
- V11 对增量批次锁定 Git Tree SHA `fc14bb126badeacedd455f974d60b29105d34883`，同时要求 active workflow allowlist 精确只剩 4 个 Current 入口。

当前允许注册的 Workflow 只有：

```text
core-agent-current-verify.yml
runner-selftest-current.yml
runner-trigger-scope-gate.yml
runner-workflow-archive-gate.yml
```

任何临时 P01～P06 / S01 / Release / Publication / Diagnostic Gate 完成使命后，都不得继续留在 `.github/workflows/`。

## 历史分类

- `2026-08/temporary/`：文件身份已明确声明为 `temp-*` 的一次性流程；
- `2026-08/invalid-yaml/`：已经无法被 GitHub 正确解析的历史 YAML；
- `2026-08/historical-version/`：已被唯一 Current 入口替代的旧版本执行包装；可复用逻辑仍由当前源码或 Harness 承担；
- `2026-08/late-active-v11/`：V10 封板后再次堆入 Active 注册区、现按 Git Tree Exact Identity 收口的 86 个一次性/版本化 Gate。
