# 公共 Runner PR 扇出收敛候选说明

> 状态：`CANDIDATE / NOT MERGED`  
> 范围：8 个已由真实 PR Run 证明的可执行错误触发源  
> Source Authority：`llhzx2018/core-free-runner-public`

## 问题

一次只修改 Core Agent A/B Harness 的 PR，同时启动了多条历史 P01/P02 Workflow。部分 Workflow 会读取私有仓、安装浏览器、检查正式 Release 元数据，甚至持有写入能力；这些任务与当前 PR 没有关系，却持续消耗 GitHub Actions 时间并扩大 Agent Evidence 噪音。

## 首批处理

机器聚合基线确认仓库共有 423 个 Workflow、123 个文本声明 PR 的 Workflow；其中 10 个没有任何 Path 范围。真实 Run 证明以下 8 个可执行 Workflow 会被无关 PR 触发，因此停止自动响应任意 `pull_request`，改为仅允许明确的 `workflow_dispatch`：

- P01 PR Runner Probe；
- P01 V2.21.21 Navigation Backend Browser Gate；
- P01 V2.21.21 Final Source Gate；
- P02 V2.5.18 Final Candidate Verify；
- P02 V2.5.17 Production Readiness；
- P02 V2.5.16 Production Readiness；
- P02 V2.5.16 Source Manifest Reseal；
- P02 V2.5.18 Source Manifest Reseal。

原 Workflow 内容和历史能力均保留，需要复核时仍可手动运行。本 Candidate 不删除文件、不修改产品源码、不使用 Release、不进入 Production。

## 验收

- 8 个 Workflow 均不存在自动 `pull_request` 触发；
- 8 个 Workflow 均保留 `workflow_dispatch` 恢复入口；
- 新增机器检查，防止这些触发器重新漂移；
- Candidate PR 创建后，上述 8 个 Workflow 不再产生 Run/Job；
- 新增一个不读取私有仓、不使用 Secret、3 分钟硬超时的统一 Trigger Scope Gate；
- 其余历史 Workflow 只记录聚合数量，不在本批次扩大修改范围。

本批完成后，旧的文本声明 PR Workflow 降为 115 个；Candidate 新增 1 个严格 Path 限定的轻量守卫。仍有 2 个无 Path 的历史文件，但它们本身是无法注册执行的损坏 YAML，且未出现在真实 PR Run 中。本轮不修复并复活它们，后续应作为归档/删除候选单独治理。其余 PR Workflow 已声明 Path 范围。
