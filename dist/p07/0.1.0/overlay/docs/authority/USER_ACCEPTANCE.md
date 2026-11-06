# P07 · 真实用户验收

本文件规定如何解释真实用户证据。产品、分发、运行与现场证据的读取入口见 [Current](CURRENT.md)，验收条件见 [验收矩阵](ACCEPTANCE_MATRIX.md)。

| 验收层 | 有效证据 |
|---|---|
| 已安装 | 认证现场返回的精确构建、模块、安装目标和操作范围 |
| 备份与恢复 | 现场保护对象、恢复位置、可读包与数据库/文件回读；离线和在线验收分别记录 |
| 单站或整机迁入 | 原任务与实际站点分母、源/目标身份、数据校验、应用配置与运行验证 |
| DNS 与公网 | Owner 切换记录、仅目标端具有的证明和真实公网业务回读 |
| 旧服务器处置 | 独立评估恢复能力、非网站业务和授权 |

历史记录在 [旧版用户验收](https://github.com/llhzx2018/vf-server-ops/blob/aa0f6242f60033d626d9dc6543781322e6e32507/docs/authority/USER_ACCEPTANCE.md)和[历史 16 站实机结果](../evidence/P07_FULL_SERVER_MIGRATION_REAL_PRODUCTION_PASS_20261005.md)。例如 release87 MariaDB 现场初始化当时为 `NOT_RUN`，菜单和构建号只证明其各自范围。各次迁移、不同引擎和不同构建分别取证。
