# 公共 Runner 历史 Workflow 归档

此目录保存已经退出 GitHub Actions 自动注册范围、但仍需保留 Git 历史与恢复能力的 Workflow。

规则：

- `.github/workflows/` 只放仍需要被 GitHub 注册的执行入口；
- `archive/workflows/` 中的 YAML 是被动历史材料，不会自动执行；
- 归档采用移动，不修改原 Workflow blob 内容；
- 恢复任何 Workflow 必须建立 Candidate、说明用途、重新限定触发路径并通过机器 Gate；
- 归档目录不得保存 Secret、私有源码、PRIVATE_DATA、真实数据库或生产备份。

## Current Archive Authority

当前机器入口：[`归档清单_V13.json`](归档清单_V13.json)。

V13 延续“封板基线 + 增量 Git Tree”结构，避免每次新增归档都重新复制数百条历史元数据：

- `归档清单_V10.json`：封板基线，421 个历史 Workflow；每个条目继续按 bytes + SHA-256 + source commit 验证；它是 V11 的历史基线，不再是 Current manifest。
- `2026-08/late-active-v11/`：V10 之后又进入 Active 注册区、但使命已经结束的 86 个 Workflow；从 `core-free-runner-public/main@e90d10a76f01f6166ed49516d44a82019205fe84` 原 blob 集合移动而来。
- V11 对 2026-08 增量批次锁定 Git Tree SHA `fc14bb126badeacedd455f974d60b29105d34883`；其中 `active_current_workflows` 只是当时历史快照，不再作为 live allowlist。
- V12 新增 `2026-09/historical-version/s01-v12/`，归档已被 Theme 1.35.31 明确 supersede 的 4 个 S01 exact-version / exact-SHA Workflow，并锁定独立 Git Tree 身份。
- V13 新增 `2026-09/historical-version/p07-v13/`，归档已被 System Care RC12 Current Route 明确 supersede 的 RC10 Discovery Gate，并锁定独立 Git Tree 身份。

当前 Active Workflow Surface 是动态 Git Truth，由 Trigger Scope / Estate Gate 与任务对应 Authority 判断，不在 Archive Manifest / README 复制固定 allowlist。

任何一次性 P01～P07 / S01 / Release / Publication / Diagnostic Gate 完成使命后，都不得因为“留作历史”继续占用 `.github/workflows/`；历史应进入被动 Archive 或保留在 closed PR / Run。

## 历史分类

- `2026-08/temporary/`：文件身份已明确声明为 `temp-*` 的一次性流程；
- `2026-08/invalid-yaml/`：已经无法被 GitHub 正确解析的历史 YAML；
- `2026-08/historical-version/`：已被唯一 Current 入口替代的旧版本执行包装；可复用逻辑仍由当前源码或 Harness 承担；
- `2026-08/late-active-v11/`：V10 封板后再次堆入 Active 注册区、现按 Git Tree Exact Identity 收口的 86 个一次性/版本化 Gate。
- `2026-09/historical-version/s01-v12/`：已被 S01 Theme 1.35.31 supersede 的 1.35.24 / SEO Reference exact-source Workflow，共 4 个。
- `2026-09/historical-version/p07-v13/`：已被 System Care RC12 Current Route supersede 的 RC10 CloudPanel Discovery Smoke，共 1 个。
