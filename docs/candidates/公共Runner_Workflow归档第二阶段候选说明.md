# 公共 Runner Workflow 归档第二阶段候选说明

> 状态：`CANDIDATE / NOT MERGED`  
> 基线：`main@060e65f9adec05e1fe4b3798f86f10513764c97f`  
> 行为：`MOVE ONLY / NO CONTENT CHANGE / NO RELEASE / NO PRODUCTION`

## 本批范围

从 `.github/workflows/` 移出 39 个不应继续注册的历史入口：

- 37 个文件名明确以 `temp-` 开头的一次性 Workflow；
- 2 个已经无法解析、也未被 GitHub 注册执行的损坏 YAML。

文件完整移动到 `archive/workflows/2026-08/`，内容、Git Blob 和恢复能力保留，不执行永久删除。

## 明确不处理

- 不根据版本号猜测其它 385 个 Workflow 是否过期；
- 不移动 Current Core Agent、Skill 发布、项目当前 Gate；
- 不修复并重新激活损坏历史 Workflow；
- 不执行 Tag、Release、Production 或产品源码写入。

## 验收

- 归档文件：39；
- 临时分类：37；
- 损坏 YAML 分类：2；
- `.github/workflows/` 不再存在 `temp-*.yml`；
- 两个损坏 YAML 不再处于 GitHub Actions 注册目录；
- Manifest 路径、字节数和 SHA256 与归档文件逐项一致；
- PR 只启动一个无 Secret 的轻量 Archive Gate。

本批完成后，活跃 Workflow 文件数将从 424 降至 386（包含新增的 Archive Gate）。后续是否继续归档版本化但仍有效的 Workflow，需要结合项目 Current Authority 分批判断。
