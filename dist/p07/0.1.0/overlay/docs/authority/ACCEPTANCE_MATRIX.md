# P07 · VF Server Ops · 验收矩阵

> 现行验收条件。每项结论绑定任务、源码、构建与验证范围。项目状态从 [Current](CURRENT.md) 读取，用户现场验收按 [USER_ACCEPTANCE](USER_ACCEPTANCE.md) 记账。

## 1. 产品与迁移验收

| ID | 条件 | 证据入口 |
|---|---|---|
| P07-01 | 工具箱入口、组件归属和独立初始化符合 [RPD](RPD.md)。发现既有 CloudPanel、数据库或业务冲突时拒绝覆盖；验证实际目标 SQL 端点及 OS/引擎组合。 | [入口回归](../../tests/test_user_entry.py)、相应构建的空机安装与拒绝路径 |
| P07-02 | 本地备份包及适用的加密远端副本具有完整清单、校验和 Fresh Verify。恢复证明覆盖文件、数据库、SQLite 与附件或外置资产，区分备份生成、包校验、隔离恢复、本机验证。 | [备份](../../tests/test_backup.py)、[Restore-As](../../tests/test_restore_as.py)、[恢复实引擎](../../tests/integration/test_dual_engine_restore_drill.py)和目标独立回读 |
| P07-03 | 目标端主动 Pull。核对源、目标、任务范围和每个站点归属。暂存、失败和续迁保留已有结果；无归属、重复、越界、未知目标或既有业务冲突须阻断。 | [Pull 编排](../../tests/test_server_migration_pull.py)、[防覆盖续传](../../tests/test_migration_no_overwrite_resume.py)和实际目标只读回读 |
| P07-04 | MySQL/MariaDB 四方向逐版本证明。对 SQL 完整性、DDL 与对象、行值、时间一致性、未知副作用和隔离恢复分别检查。主键差异、快照不同步或过滤过的 SQL 按其覆盖范围报告。 | [SQL 诊断](../../tests/test_sql_diff_evidence.py)、[私有证据门禁](../../tests/test_private_recovery_gate.py)和隔离目标引擎回读 |
| P07-05 | 多任务按原父任务、续迁和余站任务核对完整站点集。检查外置文件、SQLite、配置、Cron/PM2 与源 HTTP 基线；归属、最终同步、现场回读和整体回滚逐项独立证实。 | 精确候选的锁定范围、目标所有权、资产清单、故障注入和真实任务证据 |
| P07-06 | 切换前按授权建立恢复点和冻结证明，目标端本机 Host/SNI/业务验证覆盖全量范围。回滚先确认目标停止且公网路由条件允许；公网已经变更或目标开始产生新写入时另行对账。 | [切换回归](../../tests/test_cutover.py)、真实环境范围、故障恢复与回读 |
| P07-07 | 人工 DNS 完成后，以仅目标端拥有的证明、HTTPS 及源基线验证公网到达和关键业务。保留旧 VPS 恢复副本，另行评估处置。 | Owner 授权的 DNS 后实际回读与独立业务验证 |
| P07-08 | 验证 CLI 可理解的中文状态和下一步。诊断输出脱敏，真实数据和凭据留在批准环境；任务须可区分只读、临时文件、状态写入、数据库或配置写入。 | 终端合同、负向安全测试和实际任务授权记录 |

## 2. 候选、发布与实机验收

- 首先锁定精确源码、构建和改动范围，按 [公共规范适用性](PUBLIC_AUTHORITY_APPLICABILITY.md) 选择测试。隔离实引擎可以证明测试环境内的数据库行为，真实服务器与业务数据一致性分别取证。
- 声称可升级前，验证安装包清单包含实际运行依赖、身份与校验和，隔离安装、升级、失败保留旧版和回滚各有证据。合并、正式发布、公共分发、实际安装分别回读。
- 用真实现场证据判定业务阶段。临时恢复、已暂存、已认领、连接配置回读、本机验证、技术可切换与公网验收分别记录。缺少证据时保持该阶段的未知或阻断状态。

## Terminal UI Color Contract

| Gate | Requirement | PASS condition |
|---|---|---|
| Terminal UI hierarchy | Interactive P07 pages must not degrade into full-screen plain white text | Titles, sections, actions and statuses follow the RPD canonical semantic color map |
| Semantic status color | PASS/READY/KEEP/normal vs attention/review vs fail/block/risk must be visually distinct | Green / Yellow / Red semantics match RPD |
| High-risk action color | Apply/Rollback/Uninstall/destructive actions must not look like ordinary safe actions | High-risk entry/action uses Red semantics plus existing explicit confirmation gate |
| NO_COLOR compatibility | Color must remain optional | `NO_COLOR` output is plain text and semantically complete |
| Non-TTY compatibility | Machine workflows must not depend on ANSI | Non-TTY output remains parseable/plain unless a documented PTY wrapper is intentionally used |
| Machine-output integrity | JSON / machine-readable formats must never receive ANSI escapes | Parser/regression Gate PASS |
| Shared implementation | New pages must reuse the P07 color helpers / canonical map | No ad-hoc conflicting color vocabulary |
| Product-wide Chinese-first terminal copy | Toolbox + Slot 1/2/3/4 + ordinary sub-pages must not require understanding internal English engineering tokens | 普通界面统一中文优先；TARGET/SOURCE/READY/PASS/Runtime/Gate 等仅保留为内部机器合同；CloudPanel/DNS/SSH/IP/MySQL/SQLite/Cron/PM2/HTTPS 等通用技术名可保留并配中文说明 |
| Lazy loading / current-runtime install | Toolbox and Slot entry must not replay historical installer chains or preinstall unrelated feature dependencies | Toolbox only loads selected Slot; current Slot runs locally; upgrade installs current runtime directly; rclone/OpenSSH are installed only when their feature is entered; Production install does not rerun full unit suite |

## Historical guided-init16 acceptance layer

[历史验收矩阵](https://github.com/llhzx2018/vf-server-ops/blob/aa0f6242f60033d626d9dc6543781322e6e32507/docs/authority/ACCEPTANCE_MATRIX.md)保留 guided-init16、A01–A20、旧 Release 及 B 系列完整证据。历史 16 站迁移记录为 `HISTORICAL_OWNER_REAL_PASS_FOR_EXACT_SOURCE`。历史 System Care 的 `MACHINE_PASS / OWNER_REAL_PARTIAL` 分层按原记录解释。
