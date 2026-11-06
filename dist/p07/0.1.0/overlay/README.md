# P07 · VF Server Ops（服务器工具箱）

面向 CloudPanel VPS 的中文终端工具箱，提供站点保护、备份恢复、目标端主动迁入及服务器维护。日常站点管理由 CloudPanel 负责。

## 工具箱

[正式公共入口](https://github.com/llhzx2018/core-free-runner-public/blob/main/installers/p07-toolbox.sh)路由网络代理节点、服务器性能检测、网站与数据、服务器维护与安全四个模块。「新服务器初始化」是独立菜单，复用网站与数据模块。

- 网站与数据负责站点资产、本地和加密远端备份、隔离或新站恢复、迁入和续迁。
- 服务器维护与安全负责健康、诊断、历史及受保护的维护。初始化服务于符合条件的空机。
- 普通迁移从接收端发起，保护原有目标数据和旧机恢复副本。DNS 切换由 Owner 手工执行。

在符合条件且有权限的 Ubuntu / Debian VPS 上，原有终端入口为：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-toolbox.sh)
```

## 文档与版本

- [需求开发书](docs/authority/RPD.md) · [工程 SSOT](docs/authority/SSOT.md) · [验收矩阵](docs/authority/ACCEPTANCE_MATRIX.md)
- [项目 Current](docs/authority/CURRENT.md) · [开发入口](AGENTS.md) · [真实用户验收](docs/authority/USER_ACCEPTANCE.md)

[历史 README](https://github.com/llhzx2018/vf-server-ops/blob/aa0f6242f60033d626d9dc6543781322e6e32507/README.md)保留 2026-10-17 的 `0.1.0-rc13`、`2.1.0-rc7-field`、`0.1.0-release87` 和 `0.1.0-rc56` 分发快照，以及当时的现场 `NOT_RUN` 项。实际工程、分发和已安装身份从 Current 分别回读。
