# 旧测试 Runner 退役迁移说明 V1

> 状态：`MIGRATION CANDIDATE / MACHINE ENVIRONMENT PROOF PENDING`  
> Source：`llhzx2018/core-test-runner@2db0a67fa811f2439b6ffb40be33dc3f1b3d19eb`  
> Target：`llhzx2018/core-free-runner-public/harness/wordpress-phase3`

## 一、目的

`core-test-runner` 已正式退役，但仍保存唯一的 WordPress/PHP/Apache/MariaDB 通用环境能力。本次只迁移未来仍可能复用的最小 Harness，不搬运502个历史文件、656次运行记录或26个旧分支。

## 二、迁移内容

- 固定版本 WordPress + MariaDB Compose；
- RUN_ID 隔离与强制 Cleanup；
- Job / Result V2 合同；
- 本地临时 Checkout 的 Exact Git SHA 校验；
- ZIP 安全解压；
- 标准化环境 Evidence；
- 合同与安全单元测试。

## 三、不迁移内容

- P03/P04/S01 历史项目 Adapter；
- 旧 Job、Payload、Fixture、分块传输与 Base64 绕行通道；
- 历史 Workflow、Release 或 Production 写入路径；
- 历史 Branch、Issue、Run 与 Artifact 副本。

这些对象的历史身份暂由旧仓恢复点保留；不会进入新 Runner 增加第二轮整理成本。

## 四、删除 Gate

旧仓只有同时满足以下条件才允许永久删除：

1. Target Harness 合并进入 Public Runner main；
2. 静态合同、安全测试与 Manifest Audit PASS；
3. Hosted Runner 真实启动 WordPress/MariaDB，并输出 V2 Result PASS；
4. `gov-doc` 将 Legacy Runner 从可回读仓库改为已删除 Tombstone；
5. 旧仓最终 Commit、迁移 Target Commit 与文件 Digest 已远端回读；
6. OWNER 另行明确批准永久删除仓库。

当前第3、4、5项尚未完成，因此旧仓仍不可删除。

