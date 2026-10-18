# P07 · VF Server Ops（服务器工具箱）

P07 是用于 CloudPanel VPS 的中文终端工具箱：服务器检查、网站备份与恢复、整机迁移、验证及服务器维护。它不是第二套服务器控制面板。

> 普通用户看到的公共版本为 **V0.1.0**。下面的内部构建号是 **2026-10-17 的已发布分发快照**，不代表任何 VPS 已经安装该版本。实际身份由公共安装器、产品 `BUILD_ID` 和现场回读分别确定。

## 唯一入口

在 Ubuntu / Debian VPS 上，以有权限的终端运行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-toolbox.sh)
```

当前顶层菜单：

```text
1. 网络代理节点          V0.1.0 · 0.1.0-rc13
2. 服务器性能检测        V2.1.0 · 2.1.0-rc7-field
3. 网站与数据            V0.1.0 · 0.1.0-release87
4. 服务器维护与安全      V0.1.0 · 0.1.0-rc56
5. 新服务器初始化        经由网站与数据模块，release87
0. 退出
```

**普通入口菜单为五项能力；底层只有四个可独立安装模块，初始化复用第三模块。** 不应将菜单项数与包数混淆。

## 实际使用边界

**新服务器初始化（5）**：仅针对全新、符合条件的 VPS 自动安装 CloudPanel，默认选择 **MariaDB 10.11**。发现现有 CloudPanel / MySQL / Percona 或业务数据时，拒绝覆盖和替换。MariaDB 专用数据库调优尚未校准，应安全跳过而非自动套用 MySQL 参数。

**网站与数据（3）**：查看网站和数据库、创建并校验本地备份、已验证备份恢复、Google Drive / Backblaze B2 加密远端副本、从旧服务器向当前新服务器 **TARGET_PULL** 迁移。整机迁移从**新 VPS** 发起、输入旧 VPS 地址；迁移任务可断点继续。不会自动覆盖旧数据或替使用者修改 DNS。

**服务器维护与安全（4）**：只读健康检查、系统更新预检、受控空间清理、资源配置、安全检查和操作记录。破坏性或影响网站运行的操作必须走独立确认，不因运行工具箱而自动执行。

**网络代理节点（1）与服务器性能检测（2）** 为独立安装组件。第二项当前实际固定分发的是 V2.1.0（并非部分历史文档记载的 V2.2.2）。

## 已验证到什么程度？

- **2026-10-05**：release68 曾经完成真实的 **16 站整机迁移、16/16 本机验证、人工 DNS 切换及公网 Production 验证**。这项证据只适用于当时的具体环境和源码，旧服务器需要继续保留作为 Recovery Copy。
- **2026-10-09**：release85 正式发布并通过公共安装器与独立机器测试；为全新服务器设置 MariaDB 10.11 默认目标。
- **2026-10-17**：release86 与 System Care rc55 已正式发布，公共安装器和升级/回滚机器测试 PASS；**新 VPS 实际 MariaDB 10.11 初始化、MySQL/Percona 8.4 → MariaDB 10.11 跨引擎实机恢复** 仍是 `NOT_RUN`。不能以 release68 的真实迁移成绩或机器模拟测试冒充新版本实机通过。
- **2026-10-17**：release87 与 System Care rc56 已正式发布，669/669 精确源码机器验证和公共分发 PASS；Owner 只确认 `--build-id=0.1.0-release87`、五个主菜单可打开。MariaDB、备份恢复、迁移及 System Care rc56 单独安装不能据此宣告实机 PASS。CloudPanel 密码 argv 可见性仍有残余风险。
- **P07 全模块 Owner 用户验收** 仍为 `PARTIAL`：独立 Restore-As、远程恢复、定时备份、卸载旧服务器等存在单独的验收边界。

备份文件存在不等于可恢复；只有恢复演练与数据验证合格，才能称为已证实可恢复。旧 VPS、DNS、真实数据库、网站 Nginx 不允许由普通开发和测试任务自动修改。

## 权威来源

| 信息 | 唯一责任来源 |
|---|---|
| 治理及操作边界 | `llhzx2018/gov-doc/main/CURRENT.md` |
| P07 代码、运行身份 | `AGENTS.md`、`docs/authority/CURRENT.md`、`VERSION`、`BUILD_ID`、live Git |
| 本次已发布模块快照 | `docs/authority/P07_INTEGRATION_MANIFEST.json`（记录，不代替实时渠道） |
| 正式公共安装器 | `llhzx2018/core-free-runner-public/main/installers/p07-toolbox.sh` |
| 真实用户验收 | `docs/authority/USER_ACCEPTANCE.md` + 对应真实证据 |
| 历史完整迁移证据 | `docs/evidence/P07_FULL_SERVER_MIGRATION_REAL_PRODUCTION_PASS_20261005.md` |
| release85 MariaDB 历史机器证据 | `docs/evidence/P07_MARIADB_1011_RELEASE85_MACHINE_GATE_20261009.md` |

更早 RC1/RC2、guided-init、release32 版本说明均属于 Git 历史记录；不能代替最新发布或实际安装状态。
