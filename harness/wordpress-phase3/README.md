# WordPress Phase 3 通用 Harness V2

> 状态：`CURRENT / REUSABLE HARNESS / NOT A REGISTERED WORKFLOW`

这是从已退役 `llhzx2018/core-test-runner` 提炼出的最小通用能力，用于在 GitHub Hosted Runner 临时环境中验证固定版本的 WordPress、PHP、Apache 与 MariaDB 基线。

它不是第五个长期 Workflow，也不会自动接收项目任务。具体项目测试必须在临时 Candidate Workflow 中：

1. Checkout `core-free-runner-public` 与目标项目 Exact SHA；
2. 生成符合 `schemas/job.schema.json` 的 Job Manifest；
3. 在本目录执行 `bash scripts/run_job.sh <manifest>`；
4. 执行项目自身测试；
5. 上传最小必要 Evidence；
6. 删除临时 Workflow，不进入长期 Allowlist。

## 保留能力

- WordPress 7.0.2 + PHP 8.4 + Apache；
- MariaDB 11.8.8、InnoDB、utf8mb4；
- RUN_ID 隔离、动态本机端口与强制 Cleanup；
- Job / Result 机器合同；
- 本地目录 Exact Git SHA 校验；
- ZIP 安全解压工具；
- 标准化 Environment / Checks / Result Evidence。

## 明确不迁移

- 旧 P03/P04/S01 项目 Adapter；
- 旧 Job、Payload、Fixture 与版本包；
- Git Blob 分块、Base64、Issue Transport 等历史绕行通道；
- Release、Production、Backup 写入流程；
- 已退役 Workflow。

私有源码由临时 Private Runner Workflow Checkout；本 Harness 只接收已经存在于 Runner 临时工作区的目录，不保存源码或 Secret。

来源与裁决见 [`迁移来源清单_V1.json`](迁移来源清单_V1.json)。

