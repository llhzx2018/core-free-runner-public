#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

ENGINE="$SCRIPT_DIR/lib/resource_apply.py"
BACKUP_ROOT="/var/lib/vf-system-care/resource-backups"

require_engine() {
  command -v python3 >/dev/null 2>&1 || { fail '缺少 python3。'; return 2; }
  [[ -f "$ENGINE" ]] || { fail 'Resource Safe Apply 引擎不存在。'; return 3; }
}

show_plan() {
  local mode="${1:-balanced}"
  require_engine
  python3 "$ENGINE" plan --mode "$mode"
}

calibrate_readonly() {
  require_engine
  local profile_engine="$SCRIPT_DIR/lib/resource_profile.py"
  [[ -f "$profile_engine" ]] || { fail 'Resource Profile 引擎不存在。'; return 3; }

  say "${C_BOLD}P07 · Production Read-only Calibration${C_RESET}"
  say
  say '本动作只读取当前 CPU / RAM / Swap / Load / PHP / MySQL 与配置。'
  say '不会 Apply，不会 reload/restart，不会写 PHP/MySQL/Swap/systemd。'
  say
  say '===== PROFILE PREVIEW ====='
  python3 "$profile_engine" preview --mode balanced
  say
  say '===== SAFE PLAN ====='
  python3 "$ENGINE" plan --mode balanced
  say
  say '===== CALIBRATION DECISION HINT ====='
  say '若当前 Production 已按推荐值调优，Safe Plan 应主要显示 KEEP / NO CHANGE。'
  say '若出现大量 CHANGE、BLOCKED 或识别错误，不应执行 Apply，应先修算法。'
  say
  say 'P07_PRODUCTION_CALIBRATION=READ_ONLY_COMPLETE'
}

apply_balanced() {
  require_root
  require_engine
  show_plan balanced
  say
  say "${C_YELLOW}只有已 Production-calibrated 的 1C/2GB Balanced 会放行。${C_RESET}"
  say 'CAP-ONLY：只降低超额上限，不自动提高资源。'
  say '不会自动 restart MySQL，不会自动改 Swap，不会自动停未引用 PHP。'
  say
  [[ -t 0 ]] || { fail 'Production Apply 需要交互式终端。'; return 78; }
  printf '请输入 APPLY_RESOURCE_PROFILE 确认执行，其他输入取消：'
  local token
  read -r token || return 78
  [[ "$token" == "APPLY_RESOURCE_PROFILE" ]] || { warn '已取消。'; return 0; }
  python3 "$ENGINE" apply --mode balanced --confirm APPLY_RESOURCE_PROFILE
}

list_backups() {
  say "${C_BOLD}最近 Resource Apply 状态${C_RESET}"
  say
  if [[ ! -d "$BACKUP_ROOT" ]]; then
    say '暂无 Resource Apply backup / receipt。'
    return 0
  fi
  find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null |
    sort -nr |
    head -n 8 |
    cut -d' ' -f2- || true
}

rollback_state() {
  local state_dir="${1:-}"
  require_root
  require_engine
  if [[ -z "$state_dir" ]]; then
    list_backups
    say
    [[ -t 0 ]] || { fail 'Rollback 需要交互式终端。'; return 78; }
    printf '请输入要回滚的完整 backup 目录：'
    read -r state_dir || return 78
  fi
  [[ -f "$state_dir/state.json" ]] || { fail '找不到 state.json。'; return 2; }
  say
  printf '请输入 ROLLBACK_RESOURCE_PROFILE 确认回滚：'
  local token
  read -r token || return 78
  [[ "$token" == "ROLLBACK_RESOURCE_PROFILE" ]] || { warn '已取消。'; return 0; }
  python3 "$ENGINE" rollback --state-dir "$state_dir" --confirm ROLLBACK_RESOURCE_PROFILE
}

menu() {
  local choice
  while true; do
    screen_clear
    say "${C_BOLD}P07 · Resource Safe Apply${C_RESET}"
    say
    say '1. Production 只读校准（Preview + Safe Plan）'
    say '2. 查看 Safe Plan'
    say '3. 执行 Balanced Safe Apply（仅已校准规格）'
    say '4. 查看最近 Backup / Receipt'
    say '5. 回滚指定 Backup'
    say '0. 返回'
    say
    printf '请选择 [0-5]：'
    read -r choice || return 0
    case "$choice" in
      1) calibrate_readonly; pause_menu ;;
      2) show_plan balanced; pause_menu ;;
      3) apply_balanced; pause_menu ;;
      4) list_backups; pause_menu ;;
      5) rollback_state; pause_menu ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-5。'; sleep 1 ;;
    esac
  done
}

case "${1:-menu}" in
  menu|"") menu ;;
  calibrate|calibration) calibrate_readonly ;;
  plan) shift; mode="balanced"; [[ "${1:-}" == "--mode" ]] && mode="${2:-balanced}"; show_plan "$mode" ;;
  apply) apply_balanced ;;
  backups|receipts) list_backups ;;
  rollback) shift; rollback_state "${1:-}" ;;
  -h|--help)
    cat <<'HELP'
P07 · Resource Safe Apply

Commands:
  resource-apply.sh menu
  resource-apply.sh calibrate
  resource-apply.sh plan [--mode conservative|balanced|performance]
  resource-apply.sh apply
  resource-apply.sh backups
  resource-apply.sh rollback [backup_dir]

Auto Apply V1 is restricted to the production-calibrated 1C/2GB Balanced
CloudPanel lane. Other profiles remain preview-only.
HELP
    ;;
  *) fail "未知命令: $1"; exit 2 ;;
esac
