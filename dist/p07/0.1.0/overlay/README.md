# P07 · VF Server Ops

P07 是 VF / Kewaro 的统一服务器运维工具箱。普通用户只使用一个入口，所有能力都从同一个 P07 主菜单进入。

当前目标版本：`V0.1.0 Final Integration Candidate`。

## 唯一入口

在 Debian / Ubuntu VPS 上使用 root：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-toolbox.sh)
```

P07 顶层只保留四个功能域：

```text
1. 网络节点 / V2Ray
2. VPS 一键验机
3. CloudPanel 备份 / 恢复 / 迁移
4. 系统维护 / 安全
0. 退出
```

当前集成身份：

```text
Slot 1  Network Node              V0.1.0 / rc9
Slot 2  VPS Audit                 V2.1.0 / rc7-field
Slot 3  CloudPanel Ops            V0.1.0 / RC3 Final Integration Candidate
Slot 4  System Care / Security    V0.1.0 / RC15
```

Slot 3 已在 Final Integration 分支并入整机 CloudPanel 迁移自动化，包括低磁盘直接同步、MySQL/SQLite、Cron/PM2、Runtime freeze、TARGET bootstrap、Production proof、恢复保护和 DNS 人工 Gate。

Slot 4 已完成 RC15 Production 安装，并包含资源识别、配置 Profile、Calibration Registry、Safe Plan / Apply / Verify / Rollback；Resource Safe Apply 不会自动执行。

> 当前仍是 Final Integration Candidate。正式 V0.1.0 Tag / GitHub Release 尚未执行，必须先完成最终集成 Gate 与剩余真实验收。

## Slot 3 · CloudPanel 备份 / 恢复 / 迁移

下面是 Slot 3 的普通用户功能说明。

## 1. 查看这台服务器

选择 `1` 后，P07 只读盘点 CloudPanel，并显示系统、CloudPanel 版本、网站数量、MySQL / SQLite、网站列表、运行类型和 SSL 状态。

这个流程不修改网站、不修改数据库、不改 DNS。

## 2. 备份网站

选择 `2` 后，P07 自动读取 CloudPanel 并列出网站：

```text
请选择网站
----------------------------------------
  1. example.com
  2. api.example.com
  3. shop.example.com
  0. 返回
```

普通用户只选数字，不需要提前记住或手工输入域名。

之后 P07 自动完成：

```text
网站文件
→ MySQL
→ SQLite
→ SSL / Cron / PM2 / CloudPanel 恢复元数据
→ Manifest
→ Checksums
→ Fresh Verify
```

成功结果以用户可读卡片显示：

```text
备份完成 ✓
网站：example.com
备份编号：...
大小：...
状态：已验证，可恢复
保存：本机
位置：/var/backups/vf-server-ops/...
```

默认本地备份目录：

```text
/var/backups/vf-server-ops
```

备份包可能包含 SSL 私钥、数据库恢复数据等，所以属于 `PRIVATE_SENSITIVE_BACKUP`，不要放进公开 Web 目录。

### 可选加密远程副本

P07 底层已真实验证 Google Drive Pool、Backblaze B2、`rclone crypt`、`cryptcheck`、COMPLETE-only list/fetch 和 fresh local verification。

普通用户路径使用可选无密钥策略文件：

```text
/etc/vf-server-ops/storage.json
```

如果没有配置，P07 不会追问 rclone/Google/B2 参数，只显示：

```text
远程副本：未设置（本地备份不受影响）
```

如果已经配置，P07 在本地备份 PASS 后只问一次：

```text
发现已配置的加密远程备份。
是否再保存一份到远程？[y/N]：
```

选择 `y` 后使用已有加密存储配置的 `target=auto`，不让普通用户选择 rclone remote / Google / B2 账号。

远程上传失败也不会把已经验证 PASS 的本地备份改成失败，更不会删除本地备份。

## 3. 迁移网站到新服务器

准备：

```text
SOURCE = 旧 CloudPanel VPS
TARGET = 新 CloudPanel VPS
```

TARGET 应安装干净 CloudPanel，不要提前创建同域名网站。

在 SOURCE 选择 `3`，P07 先列出 SOURCE 网站供编号选择，然后普通用户只需输入 TARGET IP。

### 第 1 阶段：先检查 TARGET

**在创建迁移备份之前**，P07 先做只读检查，并区分：

```text
READY
NEEDS_KEY_SETUP
TARGET_NOT_CLOUDPANEL
TARGET_SITE_CONFLICT
UNREACHABLE
```

检查内容包括 SSH、TARGET CloudPanel 和明显同域名站点冲突。

只有 `READY` 才能进入迁移备份。

### 第一次 SSH Key 未准备

`NEEDS_KEY_SETUP` 时会显示：

```text
1. 现在准备 SOURCE → TARGET 连接
0. 返回
```

P07 可以在需要时生成标准 SOURCE Ed25519 SSH key，再调用系统 `ssh-copy-id`，授权完成后自动重新检查 TARGET。

如果系统 SSH 在首次授权时询问 TARGET root 密码，这个密码由系统 `ssh-copy-id` 临时读取；P07 自己不接收、不保存、不打印、不记录这个密码。

### 三阶段迁移

```text
[1/3] 检查新服务器
[2/3] 创建并验证迁移备份
[3/3] 传输、恢复 Runtime 并做技术验证
```

最后连续完成：

```text
private SSH transfer
→ TARGET Fresh Verify
→ 全新 CloudPanel 站点恢复
→ 文件 / MySQL / SQLite / SSL
→ Cron / PM2 Runtime
→ Cross-server Verify
→ HTTP / HTTPS Verify
→ TECHNICAL_CUTOVER_READY
```

技术成功后仍明确：

```text
当前网站流量：仍在旧服务器
DNS：未修改
旧服务器：保留
```

DNS Cutover 是后续独立 OWNER 决策。

P07 不会自动覆盖 TARGET 已存在的同域名网站。

## 4. 恢复备份

选择 `4` 后，P07 自动查找 `/var/backups/vf-server-ops`，并只显示 `verification.status == PASS` 的可恢复备份供编号选择。

普通用户不需要手工输入 Backup ID 或备份目录。

恢复流程：

```text
verified-only backup selection
→ zero-write Restore Plan
→ guarded new-site restore
→ Runtime Plan
→ guarded Cron / PM2 activation
→ RESTORE_COMPLETE
```

只允许恢复到 **全新的 CloudPanel 站点**，不会覆盖已经存在的同域名站点。

如果 Runtime 存在必须人工处理的系统级 Cron 等 Gate，P07 会明确显示 `NEEDS_MANUAL_RUNTIME_GATE`，不会把“数据恢复了”冒充完整恢复成功。

## 返回 / 取消

普通用户流程中的 `0. 返回`、No、Cancel 都是正常取消：不做隐藏写入，返回菜单，不应关闭整个 `vfops`。

## 高级 CLI

需要工程级操作时：

```bash
vfops --advanced --help
```

底层仍有：

```text
inventory
backup
storage
restore
runtime
verify
migrate
config
policy
retention
automation
```

高级 CLI 不替代新手菜单，也不会绕过原有安全 Gate。

## RC1 为什么被退役

2026-09-06，Owner 在真实服务器首次安装并使用 RC1。

RC1 User Field Test：**FAIL**。

真实问题包括：

```text
版本显示 UNKNOWN
/usr/local/bin 软链导致 ROOT_DIR 算错
服务器检查寻找 /usr/local/lib/*.py 而失败
首页菜单过于杂乱
备份要求用户手工输入域名
```

所以：

```text
RC1 Engineering Core PASS != RC1 User Acceptance PASS
```

RC1 已退役。

## RC2 当前状态

```text
Version                             0.1.0 RC2
Engineering Real Preproduction     PASS
Real SOURCE -> TARGET              PASS
Real Storage                       PASS
A16 Destructive Guard              PASS
A17 Secret / Log Boundary          PASS
A18 Disaster Recovery              PASS
A19 Retention / Automation         PASS
A20 Cron / PM2 Runtime             PASS
RC1 Real User Field Test           FAIL / RETIRED
RC2 Public Distribution            PASS
RC2 Automated Beginner UX Closure  PASS
RC2 Stable Installer Exact Smoke   PASS
RC2 Real Owner/User Retest         NOT_RUN
P07 User Acceptance                NOT_PASS
Owner DNS Cutover                  NOT_EXECUTED
Formal Release                     NOT_RELEASED
Production                         NOT_PRODUCTION
```

Automated UX PASS 不能冒充真实用户已经觉得好用。

## RC2 Public identity

```text
source_commit   = 06c9434a40f83ea0d5bb84231ea274623a9ef365
channel         = RC2
package_sha256  = de28a5e9dada500357be725e78e9e5cbacd51d26f1ec9bbb55ff92d21d49ada5
public_gate     = 34043230456 PASS
installer_smoke = 34043381109 PASS
```

## Authority

当前状态优先读取：

1. `docs/authority/CURRENT.md`
2. `docs/authority/USER_ACCEPTANCE.md`
3. `docs/product/RC2_BEGINNER_UX_CLOSURE.md`
4. `docs/product/RC2_REFINEMENT_STATUS.json`
5. `CANDIDATE_MANIFEST.txt`
6. `CANDIDATE_RC2.md`

真实工程闭环证据：

```text
docs/evidence/P07_REAL_GATE_CLOSURE_20260906.md
docs/evidence/P07_L2_R7_CANDIDATE_FREEZE_20260906.md
```

Git 边界：

```text
main = Canonical / Production Truth，目前未 Promotion
candidate-p07-v0.1.0-rc2 = 当前 Owner Test Candidate / docs line
```

没有 Owner Release Gate 不创建正式 Release；没有 Owner Production 授权不执行 Production migration、DNS cutover、existing-site overwrite 或 old-server deletion。
