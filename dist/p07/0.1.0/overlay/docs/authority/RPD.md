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

CloudPanel → CloudPanel 的普通正式流程采用 **新服务器主动迁入（Target-owned Pull Model）**。Owner 登录新服务器运行 P07；当前机器固定是“新服务器 / 接收端”，只需要提供旧服务器 IP。不得再把“去旧服务器运行 P07、再输入目标服务器 IP”作为普通用户正式路径。

普通用户迁移入口固定为：

```text
P07 · 服务器迁移
当前服务器：新服务器 / 接收端

1. 整机迁入
2. 单站迁入
3. 继续未完成迁移
0. 返回
```

正式编排方向：

```text
NEW SERVER（当前机器 / 接收端）
→ 按需检查 OpenSSH client + rsync
→ 输入旧服务器 IP
→ NEW → OLD 建立 SSH
→ NEW 读取 OLD CloudPanel / 网站 / 数据库 / Runtime 清单
→ NEW 本地检查目标冲突与容量
→ NEW 创建本地主 Migration ID / 私有状态
→ NEW 在 OLD 仅暂存受控 helper / transient dump / Recovery Point
→ NEW 主动 rsync PULL 网站文件与 Site User Home 业务数据
→ OLD transient logical MySQL export
→ NEW 主动 PULL dump → 本地 CloudPanel import → 应用配置 remap → semantic verify
→ OLD SQLite Online Backup
→ NEW 主动 PULL authoritative snapshot → quick_check
→ Cron / PM2 / NVM 精确运行环境先暂存、不启用
→ PREPARED；OLD 继续在线
→ 独立最终同步 Gate
→ NEW 请求 OLD 保存 Recovery Point 并冻结 Nginx / Cron / PM2
→ NEW 再次主动 PULL 最终文件 Delta / MySQL / SQLite
→ NEW 激活本地 Cron / PM2 / system Cron
→ NEW 本地 Host / SNI / asset 验证
→ CUTOVER_PREP_READY
→ OWNER 唯一人工 DNS 切换
→ NEW 创建仅新机存在的随机公网 proof
→ public HTTPS / TLS / route verify
→ PRODUCTION_PASS
→ OLD 永久保留为 Recovery Copy，除非 Owner 未来另行处置
```

整机迁入与单站迁入使用同一 Pull Orchestrator；单站仅收窄 site set，不允许回退到旧 Push UX。旧 `server_migration.py` 的 Push 实现可以继续作为内部兼容/安全原语来源，但普通 `vfops server-migrate` 与交互菜单必须路由到 Target-owned Pull Engine。

硬规则：

- **Migration State Ownership**：主迁移状态、Migration ID、断点续传状态与目标事务标记全部由 NEW SERVER 持有；OLD SERVER 只能保留 Recovery Point、受控 helper 与 transient staging，不得成为主 Authority；
- **Business Data Direction**：网站文件、VF/Press 隐藏业务数据、MySQL dump、SQLite snapshot、Cron/PM2 metadata 与所需 NVM Runtime 的业务传输必须由 NEW SERVER 发起并从 OLD SERVER 拉取；控制面为执行 helper 而上传的无业务 Secret 运行时代码不改变 Pull Model 语义；
- **Target Bootstrap**：当前新服务器已有 CloudPanel 时绝不重装；仅当当前机通过“受支持 OS/架构 + ≥1 Core + 2 GB 级内存 + ≥10 GB 磁盘 + 无 CloudPanel/MySQL/MariaDB/Nginx/Apache + 无 80/443 Web 服务 + 无现有 htdocs”空机 Gate 时，才允许使用发布时固定的 CloudPanel 官方 installer URL + SHA256 安装，默认 MySQL 8.4；
- **Lazy Dependency**：进入服务器迁移时才检查 OpenSSH client 与 rsync；OLD SERVER 如仅缺 rsync，只有用户确认开始迁移后才允许通过 apt 按需补齐；不得在 Toolbox 启动或其它 Slot 入口预装；
- **No Overwrite**：NEW SERVER 上同域名、同 Site User、同数据库名或已存在 `/home/<site_user>` 任一冲突都必须在业务写入前阻断；只允许本次 transaction-owned 资源做清理/重试；
- **Prepare No Double-run**：首轮迁入期间 OLD 保持在线，NEW 的 Cron / PM2 / system Cron 只暂存不得启动；
- **Low-disk Pull**：整机迁入不得在 OLD 同时制造 N 份整站大包；网站文件使用 Direct Rsync Pull；MySQL 与 SQLite 仅允许单项 transient staging，用完即清；
- **MySQL**：MariaDB/MySQL 跨版本只走 logical dump/import；NEW 可为本次 transaction-owned DB 生成兼容账号并原子改写 WordPress `wp-config.php` / 支持的 `.env`；final 验证先用 canonical SQL exact fingerprint，exact 不同只允许在 logical object + DML content 完全一致时通过；
- **SQLite**：必须扫描所选 Site User Home，不以 Site Root Inventory 作为完整分母；OLD 使用 SQLite online backup，NEW 写入 authoritative snapshot 前后清理 `-wal/-shm/-journal` 并执行 `quick_check`；
- **External Data**：`.vf*`、`.press*`、`.local/share/vf-*` 等 Web Root 外业务数据属于整机迁入资产；
- **Runtime**：PM2 必须从 OLD 精确解析 Site User dump 对应的 NVM Node 版本并只拉取该版本；`/etc/cron.d/*` 只有全部真实任务用户均属于本次迁入 Site User 集合时才允许自动迁入，否则 fail closed；
- **Recovery Point Before Mutation**：最终同步在冻结 OLD Runtime 前必须先把可恢复状态写到 OLD 独立 Recovery Root；失败时先停止 NEW 已启用 Runtime，再恢复 OLD Nginx/Cron/PM2；
- **DNS**：P07 绝不自动修改 DNS；Provider/Cloudflare 管理不是 P07 V1 迁移职责；只有 Owner 明确完成 DNS 切换后才进入公网验证；
- **Post-DNS Boundary**：Owner 已声明 DNS 切换、进入 `WAITING_DNS` / `PRODUCTION_VERIFY_FAILED`，或已经 `PRODUCTION_PASS` 后，禁止 Runtime-only 回退到 OLD，因为 NEW 可能已经产生新写入；未来若需回退必须先做 NEW→OLD 数据对账/反向同步事务；
- **Public Route Proof**：DNS 后必须用仅 NEW SERVER 本地生成的随机 proof file 证明公网真正到达 NEW，不能只看 DNS lookup；
- **Old Server Retention**：OLD SERVER 永不由 P07 自动删除、关机或格式化；Production PASS 后继续作为 Recovery Copy；
- **External Listener Disclosure**：必须识别 OLD 对公网监听的非 CloudPanel 端口，并明确提示这些代理/VPN/其它服务未被网站迁入链自动处理；
- **Secret Boundary**：root 密码只允许交给系统 `ssh-copy-id`；P07 不读取、不保存、不回显；SSH 私钥内容、DB 密码、OAuth/Token 等不得进入普通输出、日志、Machine Result；
- **Resume**：`PREPARING` / `PREPARE_FAILED` / `CUTOVER_RUNNING` 必须可从目标端私有状态继续；不得要求 Owner 回旧服务器找 Migration ID。

单站迁入与整机迁入共享 CloudPanel / DB / SQLite / Runtime / Verify 安全原语。Portable Backup 仍是“备份/恢复”产品合同；服务器迁入不应为了复用旧 Push 逻辑强迫用户先制作并手工搬运 ZIP。

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
4. 用户在新服务器运行 P07 并输入旧服务器 IP 后，VF Server Ops 由新服务器主动完成旧机 → 新机 Pull 迁入，不要求回旧服务器运行迁移，也不要求人工搬备份包；
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


## 11. Terminal UI / Color System Contract

P07 的普通用户入口是终端产品，不允许把终端 UI 当作“纯日志输出”。所有新增菜单、详情页、状态页、诊断页、资源页、迁移页与高风险操作页必须遵守本节。

### 11.1 目标

终端颜色只用于建立信息层级和表达语义，不用于装饰。

用户应在不逐行阅读全部文本的情况下，能够快速识别：

```text
当前页面 / 区块
正常 / 推荐
注意 / 受限
风险 / 阻断
只读 / 写入
返回 / 说明
```

禁止出现：

- 整页正文全部白色、只能靠逐行阅读理解层级；
- 不同页面对同一语义使用不同颜色；
- 红色用于普通标题或装饰，导致风险语义失真；
- 绿色显示失败、受限、阻断或 destructive action；
- 仅菜单标题有颜色，关键状态 / PASS / FAIL / KEEP / CHANGE 仍无语义区分；
- 为了彩色输出而污染 JSON、机器可读输出、Pipe 或非交互执行。

### 11.2 固定颜色语义

P07 Terminal UI 的 Canonical Color Map：

```text
Cyan / Bright Cyan
  页面标题
  区块标题
  中性信息入口
  当前结构 / 当前对象

Green
  PASS
  READY
  HEALTHY
  KEEP
  正常
  强 / 良好
  推荐
  只读检查
  安全执行结果

Yellow
  注意
  可用但有限制
  REVIEW
  Candidate
  未开启
  配置类动作
  恢复类动作
  需要人工确认但非 destructive 的动作

Red
  FAIL
  BLOCKED
  ERROR
  异常
  偏弱 / 很弱
  不建议
  destructive / rollback / uninstall
  真实写入或高风险动作

Magenta
  迁移 / Cutover / 编排类主区块
  复杂事务型流程
  不代表 PASS 或 FAIL

Gray
  版本
  边界
  注释
  帮助说明
  不可变安全规则
  返回项
  次要元数据
```

颜色只是语义增强，文字本身仍必须完整表达状态。不得使用“只有颜色、没有文字”的设计。

### 11.3 菜单规范

普通菜单必须满足：

```text
页面标题      Cyan + Bold
安全/查看项   Green / Cyan
配置项        Yellow
迁移项        Magenta
高风险项      Red
返回项        Gray
输入提示      Bold
说明/边界     Gray
```

示例：

```text
P07 · 资源优化 / 配置推荐

  1. 平衡方案（默认）                 Green
  2. 保守方案                         Cyan
  3. 性能方案                         Cyan
  4. 查看 Profile 矩阵                Cyan
  5. 输出机器 JSON                    Cyan
  6. Safe Plan / Apply / Rollback      Red
  0. 返回                              Gray
```

不得为了“好看”给每个菜单项随机分配不同颜色。

### 11.4 状态页 / 详情页规范

状态值必须使用语义色，标签保持稳定。

示例：

```text
服务器        正常                 Green
网站安全      需查看               Yellow
Apply State   ELIGIBLE             Green
Apply State   BLOCKED              Red
MySQL         KEEP                 Green
MySQL         CHANGE               Yellow / Red by risk
CPU           偏弱                 Red
CPU           良好                 Green
```

“注意”“主要短板”“边界”“建议”等信息必须有可扫描层级，避免整屏白字。

### 11.5 高风险操作规范

以下类型必须使用 Red 语义，不得伪装成普通绿色操作：

```text
Rollback
Uninstall
Delete
Apply Production Write
Destructive Cleanup
Cutover irreversible step
```

同时必须继续遵守原有高风险 Gate：

- 明确目标；
- 显式确认；
- Preflight；
- Rollback / Recovery evidence；
- 不因颜色变化削弱任何安全合同。

### 11.6 TTY / NO_COLOR / Machine Output

颜色只属于交互式终端表现层。

必须满足：

```text
interactive TTY + NO_COLOR unset
    → ANSI semantic colors enabled

NO_COLOR set
    → plain text

non-TTY / pipe / machine execution
    → plain text unless exact PTY preservation is intentionally required

JSON / machine-readable output
    → never contain ANSI escape sequences
```

如果 Wrapper 需要捕获下游输出，又必须保留交互终端颜色，可以使用受控 PTY；但必须有 Machine Gate 证明：

```text
plain-output compatibility PASS
ANSI interactive output PASS
no JSON contamination
no parser regression
```

### 11.7 Shared Implementation Rule

同一模块必须优先使用共享颜色 helper，而不是每个页面自行定义一套颜色。

Bash 建议统一使用：

```text
ui_title
ui_rule
ui_menu_good
ui_menu_info
ui_menu_warn
ui_menu_danger
ui_menu_back
ui_note
ui_good
ui_attention
ui_bad
```

Python TTY 输出必须使用同一 Canonical Color Map，并在 `NO_COLOR` / non-TTY 下返回纯文本。

### 11.8 UI Gate

任何 P07 新功能或菜单在晋级前至少验证：

```text
Terminal syntax / render             PASS
Interactive ANSI hierarchy          PASS
Semantic status colors              PASS
NO_COLOR plain text                 PASS
Non-TTY plain text                  PASS
Existing parser / machine output    PASS
Safety wording / destructive color  PASS
```

“功能正确但整屏白字”不再视为完成。

### 11.9 Scope

本合同适用于 P07 四个 Slot 的所有普通用户终端表面：

```text
Slot 1  Network Node
Slot 2  VPS Audit
Slot 3  CloudPanel Backup / Restore / Migration
Slot 4  System Care / Security
```

已成熟页面可以冻结；后续新增功能必须直接按本合同实现，不允许先做白字版再补色。

### 11.10 中文优先文案规范

P07 **整个产品**面向普通用户的终端界面采用 **中文优先**，范围包括 Toolbox、网络节点 / V2Ray、VPS 一键验机、CloudPanel 备份 / 恢复 / 迁移、系统维护 / 安全及其所有普通子页面。能够直接用中文准确表达的状态、角色和动作，不得要求用户先理解内部英文术语。

普通用户界面应优先使用：

```text
源服务器
目标服务器
已就绪
通过 / 未通过
运行环境
正式环境验证
恢复保护 / 恢复副本
人工确认
迁移任务编号
SSH 密钥
```

内部状态码、确认令牌、JSON 字段、Shell 变量、协议名与机器接口可以继续使用稳定英文标识，例如：

```text
TARGET_SITE_CONFLICT
PRODUCTION_PASS
CUTOVER_SERVER
DNS_UPDATED
P07_SSH_READY
```

这些内部标识不得直接作为普通用户必须理解的界面文案。CloudPanel、DNS、SSH、IP、MySQL、SQLite、Cron、PM2、HTTPS 等通用产品名 / 协议名 / 技术缩写可以保留，但周围说明必须使用中文。

### 11.11 按需加载 / 安装规范

P07 普通入口采用 **按需加载**，不得因为进入 Toolbox 就安装全部模块，也不得在当前版本安装时回放历史 guided-init 安装链。

固定规则：

```text
进入 P07 Toolbox
    → 只加载 Toolbox

选择 Slot 1 / 2 / 3 / 4
    → 只检查并加载被选择的 Slot

Slot 已是当前版本
    → 直接运行，不重复下载 / 安装

Slot 需要首次安装或升级
    → 直接安装“当前正式运行时”
    → 不逐级执行 RC / guided-init 历史安装器
    → Production 安装阶段只做轻量身份 / 语法 / 运行入口自检
    → 完整单元 / 回归测试必须在发布 Gate 预先完成，不在 Owner Production 安装时重复执行

功能专用外部依赖
    → 进入对应功能时才检查 / 安装
```

首批明确按需依赖：

```text
远程备份 / Google + B2    rclone
服务器迁移                openssh-client（ssh / ssh-copy-id / ssh-keygen）+ rsync
```

服务器迁移依赖只允许在用户真正进入“服务器迁移”后检查 / 安装；进入 Toolbox 或其它 Slot 不得提前安装。

不得为了“以后可能会用”而在 Slot 3 初次打开时预装上述依赖。安装动作必须发生在用户明确进入对应功能之后，并用中文说明正在安装什么、为什么需要。

历史 installer / candidate / guided-init 文件可以作为工程证据保留，但不得继续出现在普通用户当前安装链。


### Main Menu Interaction Contract

P07 Slot 3 主菜单 1–7 的普通用户入口必须满足“有动作就有可见反馈”：

```text
1 服务器 / 网站概览
2 备份网站
3 恢复网站
4 服务器迁移
5 自动备份 / 远程灾备
6 网站管理
7 CloudPanel 管理
```

固定：

```text
菜单项被选择后不得静默返回主菜单。
无网站 / 无备份 / 依赖缺失 / 子模块异常时，必须给出中文可见结果并等待用户确认后再返回。
真实 TTY 清屏不得把错误 / 空状态瞬间擦除。
子模块非零退出不得杀死整个 P07 主菜单；主菜单必须显示失败入口和退出码，并允许继续操作。
0 / 明确“返回”操作可以直接返回，不额外制造无意义确认。
```


## Terminal UX System V2

P07 普通用户终端界面采用“一屏一任务”的页面模型，避免上一级菜单、历史输出、当前提示和结果混在同一屏。

固定页面层级：

```text
清屏
→ 页面标题
→ 当前状态 / 当前对象
→ 主要内容
→ 下一步动作
→ 返回
```

交互规则：

```text
1. 从主菜单进入任何功能前先清屏。
2. 子菜单 / 功能页不得把主菜单残留在当前屏幕。
3. 成功结果使用独立结果页；失败 / 空状态使用独立状态页。
4. 无网站 / 无备份 / 无迁移任务 / 依赖缺失，不得只打印一行后立即返回。
5. 纯结果页使用“按 Enter 返回”；有明确下一步时优先展示数字动作。
6. 普通用户默认只看结构化状态，不直接展示 JSON、内部状态码、Manifest、SHA 或原始工程日志。
7. 机器输出 / 非 TTY / --version / --build-id 保持稳定，不为了 UI 美化加入 ANSI 或清屏。
8. 主菜单和子模块异常必须相互隔离：子模块失败不得杀死整个 P07。
```

标准 Terminal UX V2 原语：

```text
ui_screen_clear
ui_page
ui_section
ui_kv
ui_result_ok
ui_result_attention
ui_result_error
ui_empty_state
ui_pause_return
```

Slot 3 的主菜单、服务器 / 网站概览、备份、恢复、服务器迁移、自动备份、网站管理、CloudPanel 管理必须使用该页面模型。P07 Toolbox 及其它 Slot 的普通交互入口应采用同一视觉层级；独立 benchmark / machine output 可保留其专用输出结构。


## Ops Console V1

P07 在 Terminal UX System V2 之上新增统一运维控制面：

```text
状态摘要
诊断中心
最近操作
P07 自检 / 修复
新 VPS 初始化
```

产品合同：

- 主菜单显示轻量状态摘要，但不得自动执行修复。
- 诊断中心只读检查 P07、CloudPanel、Nginx、MySQL、PHP-FPM、磁盘、内存、Swap 与最近验证备份。
- 最近操作使用本机 JSONL 轻量历史；只记录动作、结果与简短摘要，不保存认证资料。
- P07 自检检查自身运行文件、入口与链接；重新安装当前正式 Runtime 必须精确输入 `REPAIR`。
- 新 VPS 初始化默认先做只读 Preflight；低风险基线写入必须输入 `APPLY_BASELINE`；CloudPanel 安装必须额外输入 `INSTALL_CLOUDPANEL`。
- 初始化不得自动修改 DNS、不得自动关闭 SSH、不得自动收紧防火墙导致远程失联、不得删除旧服务器。
- 安全等级统一为：绿色只读、黄色配置写入、洋红迁移/切换、红色高风险写入；高风险操作使用 exact-token confirmation。


## Beginner Chinese Menu Contract

普通用户菜单必须优先使用中文任务名称，不要求用户理解 Linux / 面板 / 网络工程术语。

规则：

```text
菜单：说“用户想做什么”
说明：必要时补充技术名词（英文/产品名）
详情：工程词只在诊断或高级页面出现
```

示例：

```text
APT                → 软件安装缓存 / 系统更新
systemd journal    → 系统运行日志
Swap               → 虚拟内存（Swap）
SSH                → 远程登录（SSH）
Varnish            → 网站加速缓存（Varnish）
SSL                 → HTTPS 证书
2FA                 → 两步验证（2FA）
Vhost               → 网站配置模板（Vhost）
rclone              → 异地备份组件（rclone）
VPS                 → 服务器（必要时括号保留 VPS）
```

P07 Toolbox 主菜单不得用手工空格拼接版本/状态列。主菜单只显示功能；版本进入对应模块查看。若所有模块可用，只显示一条“功能状态：全部可用”摘要。
