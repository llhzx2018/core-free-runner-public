#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

ENGINE="$SCRIPT_DIR/lib/resource_profile.py"

require_engine() {
  command -v python3 >/dev/null 2>&1 || { fail '缺少 python3，无法生成资源配置方案。'; return 2; }
  [[ -f "$ENGINE" ]] || { fail '资源配置方案 引擎不存在。'; return 3; }
}

run_profile() {
  local action="${1:-preview}" mode="${2:-balanced}"
  require_engine
  python3 "$ENGINE" "$action" --mode "$mode"
}

menu() {
  local choice
  while true; do
    screen_clear
    ui_title "P07 · 资源优化 / 配置推荐"
    say
    ui_note '自动识别 CPU / 内存 / 交换分区（Swap）/ 负载 / PHP 进程池 / 进程内存 / MySQL。'
    ui_note '1-5 仅生成建议，不修改配置或重启服务。'
    ui_attention '第 6 项包含安全应用 / 回滚；仅已校准的配置方案可执行，并要求明确确认。'
    say
    ui_menu_good 1 '平衡方案（默认）'
    ui_menu_info 2 '保守方案（稳定优先）'
    ui_menu_info 3 '性能方案（并发优先）'
    ui_menu_info 4 '查看不同规格 配置方案 矩阵'
    ui_menu_info 5 '输出机器 JSON（工程接口）'
    ui_menu_danger 6 '安全计划 / 应用 / 回滚（会写配置，需确认）'
    ui_menu_back 0 '返回'
    say
    printf '%b' "${C_BOLD}请选择 [0-6]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) run_profile preview balanced; pause_menu ;;
      2) run_profile preview conservative; pause_menu ;;
      3) run_profile preview performance; pause_menu ;;
      4)
        say
        ui_menu_good 1 '平衡矩阵'
        ui_menu_info 2 '保守矩阵'
        ui_menu_info 3 '性能矩阵'
        printf '%b' "${C_BOLD}请选择 [1-3]：${C_RESET}"
        read -r choice || return 0
        case "$choice" in
          1) run_profile matrix balanced ;;
          2) run_profile matrix conservative ;;
          3) run_profile matrix performance ;;
          *) warn '无效选择。' ;;
        esac
        pause_menu
        ;;
      5) run_profile json balanced; pause_menu ;;
      6) bash "$SCRIPT_DIR/resource-apply.sh" menu; pause_menu ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-6。'; sleep 1 ;;
    esac
  done
}

case "${1:-menu}" in
  menu|"") menu ;;
  preview)
    shift
    mode="balanced"
    if [[ "${1:-}" == "--mode" ]]; then mode="${2:-balanced}"; fi
    run_profile preview "$mode"
    ;;
  matrix)
    shift
    mode="balanced"
    if [[ "${1:-}" == "--mode" ]]; then mode="${2:-balanced}"; fi
    run_profile matrix "$mode"
    ;;
  json)
    shift
    mode="balanced"
    if [[ "${1:-}" == "--mode" ]]; then mode="${2:-balanced}"; fi
    run_profile json "$mode"
    ;;
  safe) shift; exec bash "$SCRIPT_DIR/resource-apply.sh" menu "$@" ;;
  calibrate|calibration|plan|apply|backups|receipts|rollback)
    cmd="$1"; shift; exec bash "$SCRIPT_DIR/resource-apply.sh" "$cmd" "$@"
    ;;
  -h|--help)
    cat <<'HELP'
P07 · 资源优化 / 配置推荐

用法：
  resource-profile.sh menu                         进入菜单
  resource-profile.sh preview [--mode ...]         查看当前服务器建议
  resource-profile.sh matrix  [--mode ...]         查看不同规格参考矩阵
  resource-profile.sh json    [--mode ...]         输出机器 JSON
  resource-profile.sh calibrate                    只读校准
  resource-profile.sh plan                         查看安全计划
  resource-profile.sh apply                        应用已允许的配置
  resource-profile.sh backups                      查看备份 / 执行记录
  resource-profile.sh rollback [backup_dir]        回滚指定备份

边界：
  preview / matrix / json / plan 只读。
  apply / rollback 会写配置，属于高风险操作，必须明确确认。
  安全应用只允许已完成真实生产校准的配置方案，并且只降低超额上限。
  不自动重启 MySQL，不自动修改交换分区（Swap），不自动停用未引用 PHP。
HELP    ;;
  *) fail "未知命令：$1"; exit 2 ;;
esac
