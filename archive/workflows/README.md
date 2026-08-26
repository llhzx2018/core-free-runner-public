# 公共 Runner 历史 Workflow 归档

此目录保存已经退出 GitHub Actions 自动注册范围、但仍需保留 Git 历史与恢复能力的 Workflow。

规则：

- `.github/workflows/` 只放仍需要被 GitHub 注册的执行入口；
- `archive/workflows/` 中的 YAML 是被动历史材料，不会自动执行；
- 归档采用移动，不修改原文件内容；
- 恢复任何 Workflow 必须建立 Candidate、说明用途、重新限定触发路径并通过机器 Gate；
- 归档目录不得保存 Secret、私有源码、PRIVATE_DATA、真实数据库或生产备份。

当前分类：

- `2026-08/temporary/`：文件身份已明确声明为 `temp-*` 的一次性流程；
- `2026-08/invalid-yaml/`：已经无法被 GitHub 正确解析的历史 YAML。
- `2026-08/historical-version/`：已被唯一 Current 入口替代的旧版本执行包装；可复用逻辑仍由当前源码或 Harness 承担。

当前机器清单：[`归档清单_V7.json`](归档清单_V7.json)。旧清单不并存，避免多份 Current。
