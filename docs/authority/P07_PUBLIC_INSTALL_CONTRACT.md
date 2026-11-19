# P07 公共 SSH 工具箱 · 唯一匿名安装与升级渠道（OWNER 2026-11-19）

> CURRENT PUBLIC P07 DISTRIBUTION CONTRACT / REQUIRED。产品需求由 [P07 RPD](https://github.com/llhzx2018/vf-server-ops/blob/main/docs/authority/RPD.md) 持有，公共工具箱仓负责实施脚本身份、匿名分发与正反机器检查。本文件不授权发布未通过的正式版本，不改变现有五模块或任何真实 VPS。

## 唯一可以提供给用户的命令

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-toolbox.sh)
```

普通 Owner/用户一律从公开主入口启动和按需升级五模块：P07-M01 网络代理节点（V2Ray）、P07-M02 服务器性能检测（VPS 验机）、P07-M03 网站与数据、P07-M04 服务器维护与安全、P07-M05 新服务器初始化。**禁止让用户安装或授权 GitHub CLI / `gh`、登录 GitHub、输入 Git Token、获取私有仓权限、`git clone`、手工下载上传解压 ZIP，或使用第二条内部试用 SSH 命令**。开发方可内部使用 Git/Runner/ZIP，但绝不将其授权要求传递给公共使用者。

## 更新时必须维持的性质

1. 唯一公共 `main/installers/p07-toolbox.sh` 必须允许匿名 HTTPS 下载；不依赖 GitHub account、OAuth Device Flow、personal token 或私有仓库。不得把公共下载入口改为私有 GitHub API 或内网制品库。
2. 公开 Release 只在所有适用发行安全硬门禁通过后创建／晋升；需要其独立模块的正式 ZIP、manifest、Git blob / SHA-256 校验才能更新公共 ToolBox 对应模块 pin。未知/坏包拒绝；升级必须能原子回退；其他模块不被连带改变。
3. 私有 `OWNER_TRIAL_CANDIDATE` 只是一种开发证据，不代表对普通用户可下载安装。新版本未正式发布时，保持公共主入口现有正式版本，不以旧版安装脚本、无效 URL、私有包或新版本文字冒充已发布。
4. 新版用户说明不得创建不同于本页的第二个安装／升级命令。试用需其它授权时只能说明“目前还不能公开使用”，不能让用户在服务器上交出 GitHub 登录权限。
5. 项目标准：P07 [公开分发验收矩阵](https://github.com/llhzx2018/vf-server-ops/blob/main/docs/authority/ACCEPTANCE_MATRIX.md)。本仓机器接线：`scripts/check_p07_public_install_contract.py` + `tests/test_p07_public_install_contract.py`，由 `.github/workflows/p07-public-terminal-ux-v3.yml` 现有工作流执行；改公共安装器/相关说明时必须通过。但静态 Gate 不替代实际安装、升级、故障回滚、发行、Production 或三类跨机迁移。

## 当前使用边界

本页不复制任何动态 BUILD_ID 或版本 SHA。实际用户版本由 `installers/p07-toolbox.sh` 当前 release pin、对应 Release 资产和现场运行时回读三重核对。生产 VPS 的修改、CloudPanel 重装、网站/数据库恢复与迁移、DNS 切换都需要独立 Owner 操作。
