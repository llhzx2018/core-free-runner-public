#!/usr/bin/env bash
# P07 Terminal UI Color System
# Canonical semantics are defined in docs/authority/RPD.md.

C_RESET=''; C_BOLD=''; C_CYAN=''; C_GREEN=''; C_YELLOW=''; C_RED=''; C_MAGENTA=''; C_GRAY=''
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_RESET='\033[0m'; C_BOLD='\033[1m'; C_CYAN='\033[36m'; C_GREEN='\033[32m'
  C_YELLOW='\033[33m'; C_RED='\033[31m'; C_MAGENTA='\033[35m'; C_GRAY='\033[90m'
fi

say() { printf '%b\n' "$*"; }

ui_screen_clear() {
  [[ -t 1 ]] && printf '\033[H\033[2J' || true
}
ui_page() {
  local title="${1:-P07}" subtitle="${2:-}"
  ui_screen_clear
  say "${C_CYAN}┌──────────────────────────────────────────────────────────────┐${C_RESET}"
  say "${C_CYAN}│${C_RESET}  ${C_BOLD}${title}${C_RESET}"
  [[ -n "$subtitle" ]] && say "${C_CYAN}│${C_RESET}  ${C_GRAY}${subtitle}${C_RESET}"
  say "${C_CYAN}└──────────────────────────────────────────────────────────────┘${C_RESET}"
  say
}
ui_section() {
  say "${C_BOLD}${C_CYAN}${1:-}${C_RESET}"
  ui_rule
}
ui_kv() {
  printf '%s：%b\n' "$1" "$2"
}
ui_result_ok() {
  ui_page "${1:-操作完成}" "${2:-}"
  ui_good '✓ 已完成'
  say
}
ui_result_attention() {
  ui_page "${1:-需要处理}" "${2:-}"
  ui_attention '⚠ 需要关注'
  say
}
ui_result_error() {
  ui_page "${1:-操作未完成}" "${2:-}"
  ui_bad '✗ 未完成'
  say
}
ui_empty_state() {
  local title="${1:-暂无内容}" detail="${2:-}" next="${3:-}"
  ui_page "$title"
  ui_attention '⚠ 当前没有可用内容'
  [[ -n "$detail" ]] && { say; say "$detail"; }
  [[ -n "$next" ]] && { say; ui_section '下一步'; say "$next"; }
}
ui_pause_return() {
  [[ -t 0 ]] || return 0
  printf '\n按 Enter 返回...'
  read -r _ || true
}
ui_title() { say "${C_BOLD}${C_CYAN}$*${C_RESET}"; }
ui_rule() { say "${C_GRAY}──────────────────────────────────────────────────────────────${C_RESET}"; }
ui_menu_good() { say "  ${C_GREEN}$1.${C_RESET} $2"; }
ui_menu_info() { say "  ${C_CYAN}$1.${C_RESET} $2"; }
ui_menu_warn() { say "  ${C_YELLOW}$1.${C_RESET} $2"; }
ui_menu_danger() { say "  ${C_RED}$1.${C_RESET} $2"; }
ui_menu_flow() { say "  ${C_MAGENTA}$1.${C_RESET} $2"; }
ui_menu_back() { say "  ${C_GRAY}$1.${C_RESET} $2"; }
ui_note() { say "${C_GRAY}$*${C_RESET}"; }
ui_good() { say "${C_GREEN}$*${C_RESET}"; }
ui_attention() { say "${C_YELLOW}$*${C_RESET}"; }
ui_warn() { ui_attention "$@"; }
ui_bad() { say "${C_RED}$*${C_RESET}"; }
ui_flow() { say "${C_MAGENTA}$*${C_RESET}"; }
ui_safe_diagnostic() {
  local raw="${1:-}" diag stage blocker stage_text blocker_text
  diag="$(printf '%s\n' "$raw" | grep '^VFOPS_DIAGNOSTIC_V1 ' | tail -n1 || true)"
  [[ -n "$diag" ]] || return 1
  stage="$(printf '%s\n' "$diag" | sed -n 's/.* stage=\([A-Z0-9_]*\).*/\1/p')"
  blocker="$(printf '%s\n' "$diag" | sed -n 's/.* blocker=\([A-Z0-9_+-]*\).*/\1/p')"
  case "$stage" in
    BACKUP) stage_text='备份' ;;
    RESTORE|RESTORE_PLAN) stage_text='恢复' ;;
    INVENTORY) stage_text='读取服务器与网站信息' ;;
    STORAGE) stage_text='异地备份' ;;
    MIGRATION|TRANSPORT|CROSS_SERVER_VERIFY|CUTOVER_VERIFY) stage_text='服务器迁移' ;;
    RUNTIME_ACTIVATION|RUNTIME_PLAN) stage_text='网站运行环境' ;;
    VERIFY) stage_text='完整性验证' ;;
    *) stage_text='当前操作' ;;
  esac
  case "$blocker" in
    MYSQL_SNAPSHOT_CHANGED) blocker_text='MySQL 数据库导出在封存时仍发生变化，P07 已停止使用这个备份。' ;;
    SQLITE_SNAPSHOT_CHANGED) blocker_text='SQLite 数据库备份在封存时仍发生变化，P07 已停止使用这个备份。' ;;
    SITE_SNAPSHOT_CHANGED) blocker_text='网站文件备份在封存时发生变化，P07 已停止使用这个备份。' ;;
    METADATA_SNAPSHOT_CHANGED) blocker_text='网站配置快照在封存时发生变化，P07 已停止使用这个备份。' ;;
    FRESH_VERIFY_NOT_PASS) blocker_text='备份最终完整性复检没有通过，P07 已停止使用这个备份。' ;;
    DB_EXPORT_FAILED) blocker_text='MySQL 数据库导出没有完成。' ;;
    DB_EXPORT_INVALID) blocker_text='MySQL 数据库导出文件不完整或无法读取。' ;;
    DB_ASSOCIATION_UNKNOWN) blocker_text='无法安全确定这个网站关联的 MySQL 数据库。' ;;
    *) blocker_text='操作已安全停止；需要根据当前结果继续排查。' ;;
  esac
  ui_note "阶段：$stage_text"
  ui_note "原因：$blocker_text"
  return 0
}

ui_safety_tier() {
  local tier="${1:-read}" text="${2:-}"
  case "$tier" in
    read) say "${C_GREEN}只读：${C_RESET}${text}" ;;
    write) say "${C_YELLOW}会修改配置：${C_RESET}${text}" ;;
    migration) say "${C_MAGENTA}迁移 / 切换：${C_RESET}${text}" ;;
    danger) say "${C_RED}高风险写入：${C_RESET}${text}" ;;
    *) say "$text" ;;
  esac
}
ui_confirm_exact() {
  local token="$1" prompt="${2:-输入 $1 继续：}" value
  ui_prompt "$prompt"
  read -r value || return 1
  [[ "$value" == "$token" ]]
}

ui_prompt() { printf '%b' "${C_BOLD}$*${C_RESET}"; }
