# P07 · 服务器工具箱 · 公共入口终端 UX V3 强制接线

> CURRENT PUBLIC P07 UI APPLICABILITY / REQUIRED。唯一项目规范：[`vf-server-ops/docs/authority/P07_TERMINAL_UX_STANDARD_V3.md`](https://github.com/llhzx2018/vf-server-ops/blob/main/docs/authority/P07_TERMINAL_UX_STANDARD_V3.md)。模块与子模块以 [P07 UX 机器矩阵](https://github.com/llhzx2018/vf-server-ops/blob/main/docs/authority/P07_TERMINAL_UX_MODULES_V1.json) 为准。本文件只记录**公共分发仓的接线**，不创建第二份 UX 标准。

## 哪些公共源码受约束

- 公共 Toolbox `installers/p07-toolbox.sh`：五项一级入口、按需分发、用户确认与错误反馈（统一入口，绝不自动跨模块升级）。
- **P07-M01 网络代理节点（V2Ray）**：`installers/vf-node.sh` 及同模块后续用户交互入口。
- **P07-M02 服务器性能检测（VPS 验机）**：公共 Toolbox 调用独立 VPS Audit 正式资源；未来 `experiments/p07-vps-audit-*.sh`、`installers/p07-vpscheck.sh` 的普通交互。原 `v21` 属于 Toolbox **固定 Git commit** 的历史发行资源，公共 `main` 无同名文件不是可将本模块标为无 UX 的理由。
- **P07-M03 网站与数据**：`installers/p07.sh` 调度和公共分发提示；实际 D01 概况、D02 备份、D03 恢复、D04 服务器迁移的终端运行时由 P07 产品仓的同一 UX V3 Gate 约束。
- **P07-M04 服务器维护与安全**：`installers/p07-system-care.sh` 和本模块对用户可见的分发/提示。
- **P07-M05 新服务器初始化**：公共 Toolbox 对 M05 的升级确认与安装状态；实际 `bin/vfops-init-ui` 由 P07 产品仓负责，公共层不得冒称其已通过现场 UX 验收。

## 所有后续 P07 公共入口改动的硬要求

1. **按企业成熟原型先设计**：Canonical Subiquity（安装向导）、Red Hat nmtui（运维菜单）、GitHub CLI（无障碍/纯文本）、Heroku CLI（简洁一致输出）；以 P07 V3 为最终项目规则。
2. 用户交互应是**简短中文动作、明确当前状态、0 返回、只读不重复确认、写入保留安全确认、成功/失败/阻断与下一步、NO_COLOR/非 TTY**。不可堆说明书/原始工程日志，不能因为“只是 Shell/SSH”判 UA_UI 不适用。
3. 用户可见行为变更的 PR 要在同一仓库 `docs/ux-reviews/*.json` 附 `vf.p07.public-ux-review.v1` 证据，对应真实模块及本次改变的文件，七类场景绑定存在的 `tests/*.py` 测试函数；机器检查只验证结构，实际测试仍须单独运行。纯不可见的版本 URL/哈希改动不自动强迫写 UI 审查，但真实用户提示改变必须检查。
4. 本仓复用现有公共 GitHub Actions Runner，`.github/workflows/p07-public-terminal-ux-v3.yml` 在有关 PR 里调用 `scripts/check_p07_public_terminal_ux.py --base-ref ...`；矩阵/工作流/AGENTS 文档缺失也必须报错。任何只改文案但未测试取消、错误及危险确认的提交不得宣称 UX 完工。
5. 本文件与脚本只保障公共拥有的分发/菜单入口；不能用静态 PASS 代替 P07 私有运行时 TTY、人类可用性、正式发布、真实 VPS 或其它模块安装结果。禁止自动 Production、DNS、迁移或系统重装。

**项目责任归属**：设计规范只在 P07 产品仓维护；公共仓只负责自身现有真实用户触点的执行接线与 CI。改 P07 公共入口不要求创建新 Runner/新运行服务/新的安装流程，不能修改不相关项目。
