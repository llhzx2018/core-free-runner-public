#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

ENGINE="$SCRIPT_DIR/lib/resource_apply.py"
BACKUP_ROOT="/var/lib/vf-system-care/resource-backups"

require_engine() {
  command -v python3 >/dev/null 2>&1 || { fail '缺少 python3。'; return 2; }
  [[ -f "$ENGINE" ]] || { fail '资源安全应用 引擎不存在。'; return 3; }
}

show_plan() {
  local mode="${1:-balanced}"
  require_engine
  python3 "$ENGINE" plan --mode "$mode"
}

calibrate_readonly() {
  require_engine
  local profile_engine="$SCRIPT_DIR/lib/resource_profile.py"
  [[ -f "$profile_engine" ]] || { fail '资源配置方案 引擎不存在。'; return 3; }

  ui_title "P07 · 生产环境只读校准"
  say
  ui_note '本动作只读取当前 CPU / RAM / Swap / Load / PHP / MySQL 与配置。'
  ui_good '不会 Apply，不会 reload/restart，不会写 PHP/MySQL/Swap/systemd。'
  say
  say "${C_BOLD}${C_CYAN}===== 配置方案预览 =====${C_RESET}"
  python3 "$profile_engine" preview --mode balanced
  say
  say "${C_BOLD}${C_MAGENTA}===== 安全计划 =====${C_RESET}"
  python3 "$ENGINE" plan --mode balanced
  say
  say "${C_BOLD}${C_YELLOW}===== 校准判断提示 =====${C_RESET}"
  ui_good '若当前 生产环境已按推荐值调优，安全计划应主要显示“保持 / 无变化”。'
  ui_bad '若出现大量“调整 / 已阻止” 或识别错误，不应执行应用，应先修算法。'
  say
  say 'P07_PRODUCTION_CALIBRATION=READ_ONLY_COMPLETE'
}

apply_balanced() {
  require_root
  require_engine
  show_plan balanced
  say
  say "${C_YELLOW}只有已 完成生产校准 的 1C/2GB 平衡方案 会放行。${C_RESET}"
  say '仅降低上限：只降低超额上限，不自动提高资源。'
  say '不会自动 重启 MySQL，不会自动改 Swap，不会自动停未引用 PHP。'
  say
  [[ -t 0 ]] || { fail '生产环境应用需要交互式终端。'; return 78; }
  printf '请输入 APPLY_RESOURCE_PROFILE 确认执行，其他输入取消：'
  local token
  read -r token || return 78
  [[ "$token" == "APPLY_RESOURCE_PROFILE" ]] || { warn '已取消。'; return 0; }
  python3 "$ENGINE" apply --mode balanced --confirm APPLY_RESOURCE_PROFILE
}

list_backups() {
  ui_title "最近资源应用状态"
  say
  if [[ ! -d "$BACKUP_ROOT" ]]; then
    say '暂无 资源应用备份 / 执行记录。'
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
    [[ -t 0 ]] || { fail '回滚需要交互式终端。'; return 78; }
    printf '请输入要回滚的完整备份目录：'
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
    ui_title "P07 · 资源安全应用"
    say
    ui_menu_good 1 '生产环境只读校准（预览 + 安全计划）'
    ui_menu_info 2 '查看安全计划'
    ui_menu_danger 3 '执行平衡方案安全应用（仅已校准规格）'
    ui_menu_info 4 '查看最近备份 / 执行记录'
    ui_menu_danger 5 '回滚指定备份'
    ui_menu_back 0 '返回'
    say
    ui_note '红色项会写配置或执行回滚；均要求显式确认。'
    say
    printf '%b' "${C_BOLD}请选择 [0-5]：${C_RESET}"
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
P07 · 资源安全应用

用法：
  resource-apply.sh menu                         进入菜单
  resource-apply.sh calibrate                    生产环境只读校准
  resource-apply.sh plan [--mode ...]            查看安全计划
  resource-apply.sh apply                        应用平衡方案
  resource-apply.sh backups                      查看备份 / 执行记录
  resource-apply.sh rollback [backup_dir]        回滚指定备份

自动应用只允许已完成生产校准的 1 核 / 2GB 平衡方案。
其它规格保持只读预览，不能自动写配置。
HELP    ;;
  *) fail "未知命令：$1"; exit 2 ;;
esac
