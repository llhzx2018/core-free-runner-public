#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
VERSION='UNKNOWN'
IFS= read -r VERSION < "$SCRIPT_DIR/VERSION" 2>/dev/null || VERSION='UNKNOWN'
source "$SCRIPT_DIR/lib/common.sh"

show_help() {
  cat <<'HELP'
P07 · 系统维护 / 安全

用法：
  vf-system-care.sh menu                         进入菜单
  vf-system-care.sh status|check                 查看快速状态
  vf-system-care.sh audit                        执行完整体检
  vf-system-care.sh updates                      系统更新
  vf-system-care.sh cleanup                      磁盘 / 日志清理
  vf-system-care.sh memory                       内存 / Swap / OOM
  vf-system-care.sh services                     服务异常诊断
  vf-system-care.sh security                     SSH / 安全检查
  vf-system-care.sh resources [...]              资源优化 / 配置推荐
  vf-system-care.sh evidence [...]               网站入侵留证
  vf-system-care.sh --version                    显示版本
  vf-system-care.sh --help                       显示帮助

安全边界：
  - 与 CloudPanel 配合使用，不替代网站、PHP、Vhost、SSL、数据库管理。
  - 菜单首页只读取缓存；耗时检查只在你明确选择后执行。
  - 系统运行状态与安全建议分开判断，不把 SSH 登录方式直接当作服务器故障。
  - 资源优化默认只生成建议；只有已完成真实校准的规格才允许安全应用。
  - 网站入侵留证只读取网站文件和访问日志，不自动修改或删除网站文件。
  - 系统更新和清理必须经过预检与确认，不自动重启。
  - 检测到 CloudPanel 时，P07 不会自动升级可能影响面板 / 网站运行环境的关键包。
HELP
}

show_header() {
  screen_clear
  say "${C_BOLD}${C_CYAN}P07 · 系统维护 / 安全${C_RESET}   ${C_GRAY}${VERSION}${C_RESET}"
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
    printf '安全建议    %b%s 项%b · 按 6 查看\n' "$C_YELLOW" "$advisories" "$C_RESET"
  fi

  case "$evidence" in
    NORMAL) printf '网站安全    %b正常%b\n' "$C_GREEN" "$C_RESET" ;;
    ATTENTION)
      if [[ "$events" =~ ^[0-9]+$ ]] && (( events > 0 )); then
        printf '网站安全    %b需查看%b · %s 条异常 · 按 7 查看\n' "$C_YELLOW" "$C_RESET" "$events"
      else
        printf '网站安全    %b需查看%b · 按 7 查看\n' "$C_YELLOW" "$C_RESET"
      fi
      ;;
    FAILED) printf '网站安全    %b检查失败%b · 按 7 查看原因\n' "$C_RED" "$C_RESET" ;;
    NOT_ENABLED) printf '网站安全    未开启 · 按 7 查看\n' ;;
    *) printf '网站安全    %b未检查%b · 按 7 查看\n' "$C_GRAY" "$C_RESET" ;;
  esac

  case "$scheduler" in
    systemd|cron) printf '自动检查    %b已开启%b\n' "$C_GREEN" "$C_RESET" ;;
    broken) printf '自动检查    %b异常%b · 按 7 修复\n' "$C_RED" "$C_RESET" ;;
    none)
      if [[ "$evidence" == NOT_ENABLED ]]; then
        printf '自动检查    未开启\n'
      else
        printf '自动检查    未开启 · 按 7 查看\n'
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
  bash "$SCRIPT_DIR/$script" "$@" 2>&1 | sed -u     -e 's/APT 缓存/软件安装缓存/g'     -e 's/APT 更新列表/系统更新列表/g'     -e 's/systemd 日志/系统运行日志/g'     -e 's/systemd 服务/系统服务/g'     -e 's/Swap/虚拟内存（Swap）/g'     -e 's/OOM/内存不足保护（OOM）/g'     -e 's/SSH \/ 安全检查/登录与安全检查/g'     -e 's/SSH/远程登录（SSH）/g'     -e 's/Fail2ban/登录防护（Fail2ban）/g'     -e 's/Vhost/网站运行配置（Vhost）/g'     -e 's/JSON/工程数据（JSON）/g'     -e 's/Cron/定时任务（Cron）/g'     -e 's/PM2/Node.js 进程管理（PM2）/g'     -e 's/inode/文件索引（inode）/g'     -e 's/Root 登录/管理员（root）登录/g'
  local rc=${PIPESTATUS[0]}
  set -e
  [[ $rc -eq 0 ]] || warn "操作返回退出码 ${rc}。"
  return 0
}

updates_menu_beginner() {
  local choice
  while true; do
    screen_clear
    ui_title 'P07 · 系统更新'
    say
    ui_menu_good 1 '检查是否需要更新'
    ui_menu_warn 2 '安装安全更新（推荐）'
    ui_menu_warn 3 '安装全部可用更新（谨慎）'
    ui_menu_back 0 '返回'
    say
    ui_note '安全更新：主要修复系统漏洞。'
    ui_note '全部更新：还会升级普通系统软件；P07 会先做安全检查，不会自动重启。'
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
    ui_title 'P07 · 磁盘空间清理'
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
    ui_title 'P07 · 资源配置建议'
    say
    ui_menu_good 1 '查看推荐配置（默认）'
    ui_menu_info 2 '查看保守配置（稳定优先）'
    ui_menu_info 3 '查看性能配置（并发优先）'
    ui_menu_warn 9 '高级配置管理（懂技术再用）'
    ui_menu_back 0 '返回'
    say
    ui_note '前 3 项只给建议，不会修改服务器。高级配置管理才可能写配置。'
    say
    printf '%b' "${C_BOLD}请选择 [0-3,9]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) run_action_friendly resource-profile.sh preview --mode balanced; pause_menu ;;
      2) run_action_friendly resource-profile.sh preview --mode conservative; pause_menu ;;
      3) run_action_friendly resource-profile.sh preview --mode performance; pause_menu ;;
      9) run_action_friendly resource-apply.sh menu; pause_menu ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0、1、2、3 或 9。'; sleep 1 ;;
    esac
  done
}

menu() {
  local choice
  while true; do
    show_header
    ui_rule
    say
    ui_menu_good 1 '一键系统体检'
    ui_menu_warn 2 '系统更新'
    ui_menu_warn 3 '磁盘空间清理'
    ui_menu_info 4 '内存检查'
    ui_menu_info 5 '异常服务检查'
    ui_menu_warn 6 '登录与安全检查'
    ui_menu_info 7 '网站安全检查'
    ui_menu_good 8 '资源配置建议'
    ui_menu_back 0 '返回'
    say
    ui_note '绿色=检查/推荐 · 黄色=会修改配置或需要关注 · 红色=高风险/回滚'
    say
    printf '%b' "${C_BOLD}请选择 [0-8]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) run_action audit.sh; pause_menu ;;
      2) updates_menu_beginner ;;
      3) cleanup_menu_beginner ;;
      4) run_action_friendly memory.sh; pause_menu ;;
      5) run_action_friendly services.sh; pause_menu ;;
      6) run_action_friendly security-audit.sh; pause_menu ;;
      7) run_action intrusion-evidence-entry.sh menu ;;
      8) resource_menu_beginner ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-8。'; sleep 1 ;;
    esac
  done
}

case "${1:-menu}" in
  --version|-V) printf 'P07 System Care %s\n' "$VERSION" ;;
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
