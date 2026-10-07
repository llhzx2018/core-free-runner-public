#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
VERSION='UNKNOWN'
IFS= read -r VERSION < "$SCRIPT_DIR/VERSION" 2>/dev/null || VERSION='UNKNOWN'
source "$SCRIPT_DIR/lib/common.sh"
VFOPS_DIR="\${P07_VFOPS_DIR:-/opt/vf-server-ops}"
VFOPS_INSTALLER='https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-final.sh'

show_help() {
  cat <<'HELP'
服务器维护与安全

用法：
  vf-system-care.sh menu                         进入菜单
  vf-system-care.sh status|check                 查看快速状态
  vf-system-care.sh audit                        执行完整体检
  vf-system-care.sh updates                      系统更新
  vf-system-care.sh cleanup                      磁盘 / 日志清理
  vf-system-care.sh memory                       内存检查（含虚拟内存 Swap / 内存不足保护 OOM）
  vf-system-care.sh services                     服务异常诊断
  vf-system-care.sh security                     服务器登录安全（含远程登录 SSH）
  vf-system-care.sh resources [...]              性能配置建议
  vf-system-care.sh evidence [...]               WordPress 网站安全
  vf-system-care.sh --version                    显示版本
  vf-system-care.sh --help                       显示帮助

安全边界：
  - 与网站面板（CloudPanel）配合使用，不替代网站运行环境（PHP）、网站配置模板（Vhost）、HTTPS 证书和数据库管理。
  - 菜单首页只读取缓存；耗时检查只在你明确选择后执行。
  - 系统运行状态与安全建议分开判断，不把远程登录（SSH）方式直接当作服务器故障。
  - 资源优化默认只生成建议；只有已完成真实校准的规格才允许安全应用。
  - WordPress 网站安全只读取网站文件和访问日志，不自动修改或删除网站文件。
  - 系统更新和清理必须经过预检与确认，不自动重启。
  - 检测到 CloudPanel 时，工具不会自动升级可能影响面板 / 网站运行环境的关键包。
HELP
}

show_header() {
  screen_clear
  say "${C_BOLD}${C_CYAN}服务器维护与安全${C_RESET}   ${C_GRAY}${VERSION}${C_RESET}"
  say

  local health advisories evidence events scheduler
  cache_get summary STATUS health
  cache_get summary SECURITY_ADVISORIES advisories
  cache_get intrusion STATUS evidence
  cache_get intrusion EVENTS events
  cache_get intrusion SCHEDULER scheduler

  case "$health" in
    HEALTHY) printf '服务器      %b正常%b\n' "$C_GREEN" "$C_RESET" ;;
    ATTENTION) printf '服务器      %b需检查%b · 按 1 查看\n' "$C_YELLOW" "$C_RESET" ;;
    *) printf '服务器      %b未检查%b · 按 1 体检\n' "$C_GRAY" "$C_RESET" ;;
  esac

  if [[ "$advisories" =~ ^[0-9]+$ ]] && (( advisories > 0 )); then
    printf '安全建议    %b%s 项%b · 按 3 查看\n' "$C_YELLOW" "$advisories" "$C_RESET"
  fi

  case "$evidence" in
    NORMAL) printf '网站安全    %b正常%b\n' "$C_GREEN" "$C_RESET" ;;
    ATTENTION)
      if [[ "$events" =~ ^[0-9]+$ ]] && (( events > 0 )); then
        printf '网站安全    %b需查看%b · %s 条异常 · 按 3 查看\n' "$C_YELLOW" "$C_RESET" "$events"
      else
        printf '网站安全    %b需查看%b · 按 3 查看\n' "$C_YELLOW" "$C_RESET"
      fi
      ;;
    FAILED) printf '网站安全    %b检查失败%b · 按 3 查看原因\n' "$C_RED" "$C_RESET" ;;
    NOT_ENABLED) printf '网站安全    未开启 · 按 3 查看\n' ;;
    *) printf '网站安全    %b未检查%b · 按 3 查看\n' "$C_GRAY" "$C_RESET" ;;
  esac

  case "$scheduler" in
    systemd|cron) printf '自动检查    %b已开启%b\n' "$C_GREEN" "$C_RESET" ;;
    broken) printf '自动检查    %b异常%b · 按 3 查看\n' "$C_RED" "$C_RESET" ;;
    none)
      if [[ "$evidence" == NOT_ENABLED ]]; then
        printf '自动检查    未开启\n'
      else
        printf '自动检查    未开启 · 按 3 查看\n'
      fi
      ;;
    *) printf '自动检查    %b未检查%b\n' "$C_GRAY" "$C_RESET" ;;
  esac
  say
}

run_action() {
  local script="$1"; shift || true
  set +e
  bash "$SCRIPT_DIR/$script" "$@"
  local rc=$?
  set -e
  [[ $rc -eq 0 ]] || warn "操作返回退出码 ${rc}。"
  return 0
}

run_action_friendly() {
  local script="$1"; shift || true
  set +e
  bash "$SCRIPT_DIR/$script" "$@" 2>&1 | sed -u     -e 's/APT 缓存/软件安装缓存/g'     -e 's/APT 更新列表/系统更新列表/g'     -e 's/systemd 日志/系统运行日志/g'     -e 's/systemd 服务/系统服务/g'     -e 's/Swap/虚拟内存（Swap）/g'     -e 's/OOM/内存不足保护（OOM）/g'     -e 's/SSH \/ 安全检查/服务器登录安全/g'     -e 's/SSH/远程登录（SSH）/g'     -e 's/Fail2ban/登录防护（Fail2ban）/g'     -e 's/Vhost/网站运行配置（Vhost）/g'     -e 's/JSON/工程数据（JSON）/g'     -e 's/Cron/定时任务（Cron）/g'     -e 's/PM2/Node.js 进程管理（PM2）/g'     -e 's/inode/文件索引（inode）/g'     -e 's/Root 登录/管理员（root）登录/g'
  local rc=${PIPESTATUS[0]}
  set -e
  [[ $rc -eq 0 ]] || warn "操作返回退出码 ${rc}。"
  return 0
}

updates_menu_beginner() {
  local choice
  while true; do
    screen_clear
    ui_title '系统更新'
    say
    ui_menu_good 1 '检查是否需要更新'
    ui_menu_warn 2 '安装安全更新（推荐）'
    ui_menu_warn 3 '安装全部可用更新（谨慎）'
    ui_menu_back 0 '返回'
    say
    ui_note '安全更新：主要修复系统漏洞。'
    ui_note '全部更新：还会升级普通系统软件；工具会先做安全检查，不会自动重启。'
    say
    printf '%b' "${C_BOLD}请选择 [0-3]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) run_action_friendly updates.sh status; pause_menu ;;
      2) run_action_friendly updates.sh security; pause_menu ;;
      3) run_action_friendly updates.sh all; pause_menu ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-3。'; sleep 1 ;;
    esac
  done
}

cleanup_menu_beginner() {
  local choice
  while true; do
    screen_clear
    ui_title '磁盘空间清理'
    say
    ui_menu_good 1 '查看可以安全清理多少空间'
    ui_menu_warn 2 '清理软件安装缓存'
    ui_menu_warn 3 '清理旧系统运行日志（保留 14 天）'
    ui_menu_back 0 '返回'
    say
    ui_note '软件安装缓存：系统下载过的安装包，不是网站文件。'
    ui_note '系统运行日志：Linux 自己的运行记录，不是网站访问日志。'
    say
    printf '%b' "${C_BOLD}请选择 [0-3]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) run_action_friendly cleanup.sh scan; pause_menu ;;
      2) run_action_friendly cleanup.sh apt; pause_menu ;;
      3) run_action_friendly cleanup.sh journal; pause_menu ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-3。'; sleep 1 ;;
    esac
  done
}

resource_menu_beginner() {
  local choice
  while true; do
    screen_clear
    ui_title '性能配置'
    say
    ui_menu_good 1 '查看推荐配置'
    ui_menu_warn 2 '应用推荐配置'
    ui_menu_back 0 '返回'
    say
    ui_note '工具会根据当前服务器资源自动给出推荐方案；普通用户不需要手工选择保守/性能模式。'
    ui_note '应用前仍会显示计划并再次确认；未完成真实校准的规格会自动阻止写入。'
    say
    printf '%b' "${C_BOLD}请选择 [0-2]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) run_action_friendly resource-profile.sh preview --mode balanced; pause_menu ;;
      2) run_action_friendly resource-apply.sh apply; pause_menu ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-2。'; sleep 1 ;;
    esac
  done
}


ensure_vfops_tools() {
  local required="$1"
  [[ -x "$VFOPS_DIR/bin/$required" ]] && return 0
  command -v curl >/dev/null 2>&1 || { fail '缺少下载工具 curl，无法准备共享运维组件。'; return 1; }
  local tmp
  tmp="$(mktemp -t p07-shared-runtime.XXXXXX)"
  ui_note '首次使用此功能：正在准备 服务器工具箱运行文件。不会迁移服务器、修改域名解析或恢复网站。'
  if ! curl -fsSL "$VFOPS_INSTALLER" -o "$tmp"; then
    rm -f "$tmp"; fail '服务器工具箱运行文件下载失败。'; return 1
  fi
  if ! P07_NO_EXEC=1 bash "$tmp"; then
    rm -f "$tmp"; fail '服务器工具箱运行文件准备失败。'; return 1
  fi
  rm -f "$tmp"
  [[ -x "$VFOPS_DIR/bin/$required" ]] || { fail '需要的工具功能仍未就绪。'; return 1; }
}

run_vfops_tool() {
  local tool="$1"
  ensure_vfops_tools "$tool" || { pause_menu; return 0; }
  set +e
  bash "$VFOPS_DIR/bin/$tool"
  local rc=$?
  set -e
  [[ $rc -eq 0 ]] || warn '功能没有正常完成，请按页面提示处理。'
  return 0
}

maintenance_menu() {
  local choice
  while true; do
    screen_clear
    ui_title '日常维护'
    say
    ui_menu_warn 1 '系统更新'
    ui_menu_warn 2 '磁盘空间清理'
    ui_menu_good 3 '性能配置'
    ui_menu_back 0 '返回'
    say
    ui_note '内存和异常服务已经纳入“服务器健康检查”，普通菜单不再重复入口。'
    ui_note '这里处理服务器日常维护，不管理网站备份或迁移。'
    say
    printf '%b' "${C_BOLD}请选择 [0-3]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) updates_menu_beginner ;;
      2) cleanup_menu_beginner ;;
      3) resource_menu_beginner ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-3。'; sleep 1 ;;
    esac
  done
}

wordpress_present() (
  shopt -s nullglob
  local file
  for file in /home/*/htdocs/*/wp-config.php /home/*/htdocs/*/*/wp-config.php; do
    [[ -f "$file" ]] && exit 0
  done
  exit 1
)

security_menu() {
  local choice has_wordpress=0 prompt_range='0-1'
  while true; do
    wordpress_present && has_wordpress=1 || has_wordpress=0
    [[ "$has_wordpress" -eq 1 ]] && prompt_range='0-2' || prompt_range='0-1'
    screen_clear
    ui_title '安全检查'
    say
    ui_menu_warn 1 '服务器登录安全'
    if [[ "$has_wordpress" -eq 1 ]]; then
      ui_menu_info 2 'WordPress 网站安全'
    else
      ui_note '未检测到 WordPress 网站，因此不显示 WordPress 专项安全入口。'
    fi
    ui_menu_back 0 '返回'
    say
    ui_note '默认只检查；需要修改配置时会再次明确确认。'
    say
    printf '%b' "${C_BOLD}请选择 [${prompt_range}]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) run_action_friendly security-audit.sh; pause_menu ;;
      2)
        if [[ "$has_wordpress" -eq 1 ]]; then
          run_action intrusion-evidence-entry.sh menu
        else
          warn '当前没有检测到 WordPress 网站。'
          sleep 1
        fi
        ;;
      0) return 0 ;;
      *) warn "无效选择，请输入 ${prompt_range}。"; sleep 1 ;;
    esac
  done
}

menu() {
  local choice
  while true; do
    show_header
    ui_rule
    say
    ui_menu_good 1 '服务器健康检查'
    ui_menu_info 2 '日常维护'
    ui_menu_warn 3 '安全检查'
    ui_menu_good 4 '工具检查 / 修复'
    ui_menu_info 5 '最近操作'
    ui_menu_back 0 '返回'
    say
    ui_note '初始化服务器已独立放在一级菜单 5；这里不再重复入口。'
    ui_note '网站概况、备份恢复和服务器迁移统一放在一级菜单 3。'
    say
    printf '%b' "${C_BOLD}请选择 [0-5]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) run_vfops_tool vfops-diagnostics-ui ;;
      2) maintenance_menu ;;
      3) security_menu ;;
      4) run_vfops_tool vfops-selfcheck-ui ;;
      5) run_vfops_tool vfops-history-ui ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-5。'; sleep 1 ;;
    esac
  done
}

case "${1:-menu}" in
  --version|-V) printf '服务器维护与安全 %s\n' "$VERSION" ;;
  --ui-contract) printf 'P07_BEGINNER_ZH_V1\n' ;;
  --help|-h) show_help ;;
  status|check) exec bash "$SCRIPT_DIR/status.sh" ;;
  audit) exec bash "$SCRIPT_DIR/audit.sh" ;;
  updates) shift; exec bash "$SCRIPT_DIR/updates.sh" "${@:-menu}" ;;
  cleanup) shift; exec bash "$SCRIPT_DIR/cleanup.sh" "${@:-menu}" ;;
  memory) exec bash "$SCRIPT_DIR/memory.sh" ;;
  services) exec bash "$SCRIPT_DIR/services.sh" ;;
  security) exec bash "$SCRIPT_DIR/security-audit.sh" ;;
  resources|resource|optimize) shift; exec bash "$SCRIPT_DIR/resource-profile.sh" "${@:-menu}" ;;
  evidence) shift; exec bash "$SCRIPT_DIR/intrusion-evidence-entry.sh" "${@:-menu}" ;;
  menu|"")
    if [[ ( -t 0 && -t 1 ) || "${P07_FORCE_INTERACTIVE:-0}" == "1" ]]; then menu; else show_help; fi
    ;;
  *) fail "未知命令：$1"; exit 2 ;;
esac
