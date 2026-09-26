# P07 · VF Server Ops · Product RPD V1.0

状态：CURRENT / V1 REAL PRE-PRODUCTION CLOSURE PASS / OWNER CUTOVER OPEN  
日期：2026-09-06

## 1. 产品定义

VF Server Ops 是面向个人长期运营的 CloudPanel 服务器业务保护与可迁移工具。目标不是管理 Linux 的所有能力，而是确保业务资产能够被识别、备份、验证、恢复并直接迁移到新的 CloudPanel VPS。

V1 用户主入口为纯终端 5 项菜单；Advanced CLI 只作为高级/自动化入口，不另造 Web UI。

## 2. 用户问题

- CloudPanel 远程备份目的地存在成本或账号限制；
- 网站文件、MySQL、SQLite、PRIVATE、`.env`、Cron、PM2 等恢复边界分散；
- 有备份文件不代表真正能恢复；
- CloudPanel → CloudPanel 缺少类似面板一键搬家的完整体验；
- 换 VPS 时人工步骤多，容易漏配置、漏数据、漏验证；
- “备份包已经在目标机后再恢复”不等于完整迁移，源机到目标机的安全传输必须属于迁移产品本身。

## 3. V1 一级能力

### 3.1 服务器检查

只读识别需要保护的业务资产与异常，不替代 CloudPanel 的日常管理面板。

### 3.2 网站备份

支持指定网站生成统一 Portable Backup Package；支持本地、Google Drive Pool 与 Backblaze B2。单站迁移继续使用 Portable Backup。整机迁移复用同一 CloudPanel / MySQL / SQLite / Runtime / Verify 安全原语，但文件层使用低磁盘 Direct Rsync 编排，不为了批量迁移在 SOURCE 同时制造 N 份整站备份包，也不建立第二种备份包格式。

### 3.3 网站恢复

同一 Backup Package 可恢复到当前服务器、新服务器或隔离测试位置；真实写入默认只允许 brand-new controlled target，不实现 existing Production overwrite。

### 3.4 服务器迁移

CloudPanel → CloudPanel，必须是完整 Source → Target 流程，而不是“用户手工把 ZIP 搬过去以后才开始”。

普通用户迁移入口分为：

```text
整机迁移（推荐）
单站迁移
```

整机迁移是服务器级编排层，不复制单站迁移实现：

```text
SOURCE→TARGET SSH Key 预检
→ TARGET 若为受支持的全新空服务器且未装 CloudPanel：可自动校验官方 installer 并安装 CloudPanel + MySQL 8.4
→ 只读 SOURCE/TARGET Preflight
→ 自动发现所选/全部 CloudPanel 网站
→ TARGET 自动建同运行时站点
→ SOURCE→TARGET 首轮 Direct Rsync（低磁盘）
→ MySQL 逐库 transient logical dump/import（传完即清）
→ TARGET 自动改写兼容 DB 配置
→ Runtime 暂缓，SOURCE 保持在线
→ Site User Home 外部 VF/Press 数据补充同步
→ 全 Site User Home SQLite Online Backup + quick_check
→ PREPARED
→ 独立 CUTOVER Gate
→ 冻结 SOURCE Nginx / Cron / PM2
→ 最终文件 Delta
→ fresh logical MySQL export/import + semantic verify
→ 最终全 Home SQLite snapshot
→ TARGET Cron / PM2 / system Cron 激活
→ TARGET local Host/SNI/asset verification
→ CUTOVER_PREP_READY
→ OWNER 唯一人工 DNS Gate
→ TARGET-only random public-route proof
→ public HTTPS/TLS Production verify
→ PRODUCTION_PASS
→ SOURCE retained for rollback
```

硬规则：

- TARGET 已有 CloudPanel 时绝不重装；仅对通过“受支持 OS/架构 + ≥1 Core + 2 GB 级内存 + ≥10 GB 磁盘 + 无 CloudPanel/MySQL/MariaDB/Nginx/Apache + 无 80/443 Web 服务 + 无现有 htdocs”空机 Gate 的 TARGET 提供自动安装；
- 自动安装使用 P07 发布时固定的官方 CloudPanel installer URL + SHA256，校验失败禁止执行；默认 MySQL 8.4；
- SOURCE 如仅缺少 rsync，进入已确认的 prepare 后可用 apt 自动补齐；其它关键运行命令缺失仍 fail closed；
- `prepare` 阶段不得提前启用 TARGET Cron / PM2，避免 SOURCE/TARGET 双跑；`/etc/cron.d/*` 只有在文件内全部实际任务用户都属于本次迁移 Site User 集合时才允许自动冻结/迁移，共享或解析不明确的 system Cron fail closed；
- 整机模式不得在 SOURCE 同时保留全部站点的大型迁移包；默认 `LOW_DISK_DIRECT_RSYNC`，SOURCE 额外磁盘占用只允许私有状态、单个 transient DB dump、单个 transient SQLite snapshot；
- MySQL/MariaDB 跨版本迁移使用逐库 transient logical dump/import，不复制 raw database directory；
- 单站 Portable Backup 迁移优先保留 SOURCE DB identity；仅在真实 CloudPanel 拒绝 legacy database user 时，允许本次 transaction-owned TARGET fallback 到兼容账号并改写 WordPress `wp-config.php` / 支持的 `.env`。整机低磁盘模式不持久化 SOURCE CloudPanel 私有 DB 凭据，直接保留数据库名并生成 TARGET-compatible DB user，再做同样的原子应用配置 remap；
- Site-root Inventory 的 SQLite 不是整机迁移完整分母；整机迁移必须补充扫描选中 Site User Home，并对真实 SQLite 使用 online backup；TARGET 对应 `-wal/-shm/-journal` sidecar 必须在 authoritative snapshot 写入前后清理，避免旧 WAL 污染；
- `.vf*`、`.press*`、`.local/share/vf-*` 等站点 Web Root 外业务数据属于整机迁移资产；
- PM2 站点必须从 SOURCE 精确解析 dump 对应的 Site User NVM Node 版本，并只迁移该版本运行时；不要求用户在干净 TARGET 手工安装 NVM/PM2；
- plan 必须给出 SOURCE 临时空间与 TARGET 容量预检；容量不足时在写入前阻断；同时提前拒绝 TARGET 同域名、同 Site User、同数据库名冲突；
- TARGET `site:add` 后必须立即重新 Inventory，证明 Site User / Site Root / Document Root / Runtime / SOURCE 域名集合可在 TARGET 重建；不等价则在大文件同步前清理本次 transaction-owned site 并停止；
- final MySQL 验证先使用 canonical SQL exact fingerprint；MariaDB→MySQL 只允许在 exact 不同但 logical object + DML content fingerprint 完全一致时继续；
- DNS 仍不由 P07 自动修改；Provider/Cloudflare 管理不是 P07 V1 职责；
- plan 必须识别 SOURCE 对公网监听的非标准端口；它们不被网站迁移链假装“已经迁走”，并使 `source_decommission_safe=false`，旧服务器继续保留直到这些代理/VPN/其它服务单独处理；
- DNS 修改后必须用仅 TARGET 存在的随机 proof file 证明公网已经到 TARGET，不能只看 DNS lookup；
- Production PASS 前旧服务器不得删除；Rollback 只恢复 SOURCE Runtime，不自动删除 TARGET；
- 自动 Runtime 回滚只允许发生在 DNS 交接前的 `CUTOVER_PREP_READY`；DNS 已交接或 Production PASS 后，普通菜单不得提供“只恢复旧机”的回滚，因为 TARGET 可能已经产生更新的文件/MySQL/SQLite 写入。此时 SOURCE 仅作为 Recovery Copy；若未来需要回退，必须先完成 TARGET→SOURCE 数据对账/反向同步事务，再决定 DNS 回切；
- 整机首次 SSH 授权若需要新 Key，必须使用 P07 专用迁移 SSH Key；用户已有 Key 永不标记为 managed、永不自动删除；Production PASS 后专用 Key 默认只作为 Recovery / 清理 SSH 通道保留，不代表允许 Runtime-only 数据回滚；Recovery 保护期结束后由普通菜单的一键 Gate 精确清理；
- 中断的 `prepare` 必须保存私有状态并支持断点续跑。

单站迁移复用 Backup Package；整机迁移复用同一 Platform / DB / SQLite / Runtime / Verify 原语，并以私有 Migration State 编排，不把整机临时传输物伪装成新的 Backup Package。

### 3.5 验证与恢复演练

区分 Backup Created、Backup Verified、Restore Verified、Migration Transport Verified、Technical Cutover Ready、OWNER Cutover Approved。必须能证明数据库、SQLite、Archive、Checksum、Manifest 与目标 HTTP/HTTPS 的可用性。

### 3.6 设置

管理备份目的地、保留策略、加密、自动任务与安全阈值；Secret 不进入 Git。设置不是第六个首页功能，属于 Backup/Advanced CLI 的支持能力。

## 4. 存储策略

- Local：最近少量副本，用于快速恢复；
- Google Drive Pool：多个个人 Google Drive 账号形成主免费远程池；同一备份默认落在一个账号，不跨账号切片；
- Backblaze B2：独立于 Google 的备用灾备；
- 存储访问通过 rclone 等稳定 CLI 抽象，不把产品绑死在 CloudPanel Remote Backup UI；
- Google 可用空间必须读取真实 quota；reserve 是配置，不假定每个账号永远有完整 15 GB 可用空间。

Real Storage 已完成 Google Drive Pool + B2 + `rclone crypt` + `cryptcheck` + fresh fetch/verify 真实闭环。

## 5. Portable Backup Package 最低内容

```text
manifest.json
files archive
mysql dumps
sqlite backups
runtime/config metadata
cron metadata
pm2 metadata
checksums
verification result
```

Secret 与私有数据在远程存储前必须具备加密路径。用于 SSH direct migration 的 package 通过 SSH 私密流传输，并在目标端再次 Fresh Verify。

## 6. 迁移 Transport 安全合同

- 默认使用 SSH key / ssh-agent；产品不设计 SSH password 参数；
- `BatchMode=yes`；
- `StrictHostKeyChecking=accept-new`，允许新 VPS 首次 TOFU，已知主机 key 变化必须拒绝；
- 禁止 `StrictHostKeyChecking=no` 与空 known_hosts；
- target host / user / port 必须先验证，注入型输入 fail-closed；
- exact `MIGRATE_NEW_SITE:DOMAIN:BACKUP_ID` confirmation 在首次目标 SSH 接触前验证；
- wrong confirmation = no target SSH contact；
- 目标端仍执行 Fresh Verify + existing-site refuse，Transport 不得绕过 Restore Guard；
- source pre_migration backup 保留，不因迁移成功自动删除。

## 7. 安全与高风险 Gate

- 默认只读优先；
- Production Restore Overwrite：V1 不实现；
- Migration technical readiness 与 OWNER Cutover 分离；
- DNS 不自动修改；
- 删除旧服务器 / 删除旧备份不是迁移完成的自动后续；
- 任何 destructive operation 必须显式目标、预检查与可回滚证据；
- Synthetic / Real / Release / Production evidence 必须分层，不能互相冒充。

## 8. Anti-goals

V1 不做：Web 后台、网站 CRUD、数据库/文件管理器、SSH Web Terminal、实时性能监控、Docker、Cloudflare、通用防火墙、通用 Nginx/PHP/PM2 管理器、VPS Provider 控制台、自动 DNS cutover、旧 VPS 自动销毁。

## 9. 成功定义

V1 pre-production 产品闭环必须达到：

1. 一台现有 CloudPanel VPS 可以被准确盘点；
2. 生成的备份包可以通过验证与恢复演练；
3. 同一恢复引擎能够在全新 CloudPanel VPS 上重建业务；
4. 用户从源服务器发起迁移时，VF Server Ops 自己完成安全 Source → Target 传输，不要求人工搬备份包；
5. 迁移完成后能够给出可审计的 `TECHNICAL_CUTOVER_READY`；
6. DNS 与旧服务器处置仍保留给 OWNER 明确决定；
7. runtime/secret/log/DR 等 required Real Gates 必须独立闭环。

上述 pre-production Real Gate 已于 2026-09-06 完成。Canonical evidence：`docs/evidence/P07_REAL_GATE_CLOSURE_20260906.md`。

## 10. 当前边界

当前状态：

```text
V1_REAL_PREPRODUCTION_CLOSURE = PASS
OWNER_CUTOVER                 = NOT_EXECUTED
FORMAL_RELEASE                = NOT_RELEASED
PRODUCTION                    = NOT_PRODUCTION
```

这意味着产品已经通过 required Real pre-production Gates，但**不**自动授权：

- merge 到 `main`；
- Tag / Release；
- Production restore/migration；
- DNS cutover；
- old-server deletion；
- existing Production overwrite。

下一工程主线返回 L2 Product Optimization；任何 Release / Production 动作仍需单独 OWNER Gate。
