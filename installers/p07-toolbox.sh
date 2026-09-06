#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="0.1.0-preview2"
VF_NODE_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/vf-node.sh"

C_RESET=''; C_BOLD=''; C_CYAN=''; C_GREEN=''; C_YELLOW=''; C_RED=''; C_GRAY=''
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_CYAN=$'\033[36m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_GRAY=$'\033[90m'
fi

say() { printf '%b\n' "$*"; }
pause_menu() { [[ -t 0 ]] || return 0; printf '\n按 Enter 返回主菜单...'; read -r _ || true; }

show_header() {
  clear 2>/dev/null || true
  say "${C_CYAN}┌──────────────────────────────────────────────────────────────┐${C_RESET}"
  say "${C_CYAN}│${C_RESET}  ${C_BOLD}P07 · VF Server Ops${C_RESET}   ${C_GRAY}${VERSION}${C_RESET}                            ${C_CYAN}│${C_RESET}"
  say "${C_CYAN}└──────────────────────────────────────────────────────────────┘${C_RESET}"
  say
}

show_menu() {
  show_header
  say "  ${C_GREEN}1.${C_RESET} 网络节点 / V2Ray                    ${C_GREEN}可用${C_RESET}"
  say "  ${C_YELLOW}2.${C_RESET} 功能模块 B                         ${C_YELLOW}待接入${C_RESET}"
  say "  ${C_YELLOW}3.${C_RESET} 功能模块 C                         ${C_YELLOW}待接入${C_RESET}"
  say "  ${C_GRAY}0.${C_RESET} 退出"
  say
}

run_network_node() {
  if command -v vf-node >/dev/null 2>&1; then
    vf-node
    return $?
  fi
  command -v curl >/dev/null 2>&1 || { say "${C_RED}✗ 当前系统没有 curl。${C_RESET}" >&2; return 3; }
  local tmp rc
  tmp="$(mktemp -t p07-vf-node.XXXXXX)"
  chmod 700 "$tmp"
  curl -fsSL "$VF_NODE_INSTALLER" -o "$tmp" || { rm -f "$tmp"; say "${C_RED}✗ 网络节点入口下载失败。${C_RESET}" >&2; return 4; }
  set +e
  bash "$tmp"
  rc=$?
  set -e
  rm -f "$tmp"
  return "$rc"
}

pending_slot() {
  say
  say "${C_YELLOW}⚠ $1 尚未接入。${C_RESET}"
}

main_menu() {
  local choice rc
  while true; do
    show_menu
    printf '请选择 [0-3]：'
    read -r choice || return 0
    case "$choice" in
      1)
        set +e
        run_network_node
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || { say "${C_YELLOW}⚠ 网络节点模块返回退出码 ${rc}。${C_RESET}"; pause_menu; }
        ;;
      2) pending_slot "功能模块 B"; pause_menu ;;
      3) pending_slot "功能模块 C"; pause_menu ;;
      0) return 0 ;;
      *) say "${C_YELLOW}⚠ 无效选择，请输入 0-3。${C_RESET}" ;;
    esac
  done
}

case "${1:-}" in
  --version|-V) printf 'P07 Toolbox %s\n' "$VERSION" ;;
  --help|-h)
    cat <<'EOF'
P07 · VF Server Ops

Usage:
  p07-toolbox

1. 网络节点 / V2Ray
2. 功能模块 B（待接入）
3. 功能模块 C（待接入）
EOF
    ;;
  "")
    if [[ -t 0 && -t 1 ]]; then main_menu; else printf 'ERROR: P07 Toolbox menu requires an interactive terminal.\n' >&2; exit 2; fi
    ;;
  *) printf 'ERROR: unknown argument: %s\n' "$1" >&2; exit 2 ;;
esac
