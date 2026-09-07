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

Usage:
  vf-system-care.sh menu
  vf-system-care.sh status|check
  vf-system-care.sh audit
  vf-system-care.sh updates
  vf-system-care.sh cleanup
  vf-system-care.sh memory
  vf-system-care.sh services
  vf-system-care.sh security
  vf-system-care.sh --version
  vf-system-care.sh --help

RC5 boundary:
  - complements CloudPanel; does not replace panel site/PHP/Vhost/SSL/database management.
  - menu hot paths use Bash builtins + cache reads only; no status child process / awk / clear fork.
  - expensive checks run only after the user selects an explicit action.
  - system audit/security inspection is read-only.
  - update/cleanup writes are narrow, explicit, confirmed and never auto-reboot.
  - package updates are preflighted; downgrade/removal plans are blocked before write.
  - when CloudPanel is detected, P07 blocks automatic updates that touch the panel/web runtime stack.
HELP
}

show_header() {
  screen_clear
  say "${C_BOLD}P07 · 系统维护 / 安全${C_RESET}   ${C_GRAY}${VERSION}${C_RESET}"
  say

  local health updates disk failed
  cache_get summary STATUS health
  cache_get updates SECURITY updates
  cache_get summary DISK disk
  cache_get summary FAILED failed

  case "$health" in
    HEALTHY) printf '状态   %b正常%b\n' "$C_GREEN" "$C_RESET" ;;
    ATTENTION) printf '状态   %b需关注%b\n' "$C_YELLOW" "$C_RESET" ;;
    *) printf '状态   %b未检查%b\n' "$C_GRAY" "$C_RESET" ;;
  esac
  [[ "$updates" =~ ^[0-9]+$ ]] && printf '更新   %s 个安全更新\n' "$updates" || printf '更新   未检查\n'
  [[ "$disk" =~ ^[0-9]+$ ]] && printf '磁盘   %s%%\n' "$disk" || printf '磁盘   未检查\n'
  [[ "$failed" =~ ^[0-9]+$ ]] && printf '服务   %s 个异常\n' "$failed" || printf '服务   未检查\n'
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

menu() {
  local choice
  while true; do
    show_header
    say '1. 一键系统体检'
    say '2. 系统更新'
    say '3. 磁盘 / 日志清理'
    say '4. 内存 / Swap / OOM'
    say '5. 服务异常诊断'
    say '6. SSH / 安全检查'
    say '0. 返回'
    say
    printf '请选择 [0-6]：'
    read -r choice || return 0
    case "$choice" in
      1) run_action audit.sh; pause_menu ;;
      2) run_action updates.sh menu ;;
      3) run_action cleanup.sh menu ;;
      4) run_action memory.sh; pause_menu ;;
      5) run_action services.sh; pause_menu ;;
      6) run_action security-audit.sh; pause_menu ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-6。'; sleep 1 ;;
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
  menu|"")
    if [[ -t 0 && -t 1 ]]; then menu; else show_help; fi
    ;;
  *) fail "未知命令: $1"; exit 2 ;;
esac
