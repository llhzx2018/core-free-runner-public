#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

ENGINE="$SCRIPT_DIR/lib/resource_profile.py"

require_engine() {
  command -v python3 >/dev/null 2>&1 || { fail '缺少 python3，无法生成资源 Profile。'; return 2; }
  [[ -f "$ENGINE" ]] || { fail '资源 Profile 引擎不存在。'; return 3; }
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
    say "${C_BOLD}P07 · 资源优化 / 配置推荐${C_RESET}"
    say
    say '自动识别 CPU / RAM / Swap / Load / PHP Pool / Worker RSS / MySQL。'
    say '这里只生成建议，不会修改配置或重启服务。'
    say
    say '1. 平衡方案（默认）'
    say '2. 保守方案（稳定优先）'
    say '3. 性能方案（并发优先）'
    say '4. 查看不同规格 Profile 矩阵'
    say '5. 输出机器 JSON'
    say '0. 返回'
    say
    printf '请选择 [0-5]：'
    read -r choice || return 0
    case "$choice" in
      1) run_profile preview balanced; pause_menu ;;
      2) run_profile preview conservative; pause_menu ;;
      3) run_profile preview performance; pause_menu ;;
      4)
        say
        say '1. 平衡矩阵'
        say '2. 保守矩阵'
        say '3. 性能矩阵'
        printf '请选择 [1-3]：'
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
      0) return 0 ;;
      *) warn '无效选择，请输入 0-5。'; sleep 1 ;;
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
  -h|--help)
    cat <<'HELP'
P07 · 资源优化 / 配置推荐

Commands:
  resource-profile.sh menu
  resource-profile.sh preview [--mode conservative|balanced|performance]
  resource-profile.sh matrix  [--mode conservative|balanced|performance]
  resource-profile.sh json    [--mode conservative|balanced|performance]

Boundary:
  READ_ONLY_RECOMMENDATION
  No PHP/MySQL/Swap/systemd writes.
  No service restart.
HELP
    ;;
  *) fail "未知命令: $1"; exit 2 ;;
esac
