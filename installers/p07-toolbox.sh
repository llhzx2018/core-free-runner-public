#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="0.1.0-preview1"
VF_NODE_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/vf-node.sh"

C_RESET=''
C_BOLD=''
C_CYAN=''
C_GREEN=''
C_YELLOW=''
C_RED=''
C_GRAY=''

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'
  C_BOLD=$'\033[1m'
  C_CYAN=$'\033[36m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m'
  C_GRAY=$'\033[90m'
fi

say() { printf '%b\n' "$*"; }

pause_menu() {
  if [[ -t 0 ]]; then
    printf '\n按 Enter 返回主菜单...'
    read -r _ || true
  fi
}

show_header() {
  clear 2>/dev/null || true
  say "${C_CYAN}┌──────────────────────────────────────────────────────────────┐${C_RESET}"
  say "${C_CYAN}│${C_RESET}  ${C_BOLD}P07 · 扩展工具箱${C_RESET}   ${C_GRAY}${VERSION}${C_RESET}                           ${C_CYAN}│${C_RESET}"
  say "${C_CYAN}│${C_RESET}  独立模块 · 统一入口 · 各模块互不干扰                    ${C_CYAN}│${C_RESET}"
  say "${C_CYAN}└──────────────────────────────────────────────────────────────┘${C_RESET}"
  say
}

show_menu() {
  show_header
  say "  ${C_GREEN}1. [可用] 网络节点 / V2Ray${C_RESET}"
  say "     ${C_GRAY}VMess + mKCP + dtls 稳定节点安装与管理${C_RESET}"
  say
  say "  ${C_YELLOW}2. [待接入] 功能模块 B${C_RESET}"
  say "     ${C_GRAY}预留给另一个 P07 独立模块${C_RESET}"
  say
  say "  ${C_YELLOW}3. [待接入] 功能模块 C${C_RESET}"
  say "     ${C_GRAY}预留给另一个 P07 独立模块${C_RESET}"
  say
  say "  ${C_GRAY}0. [退出] 退出${C_RESET}"
  say
}

run_network_node() {
  say
  say "${C_CYAN}▶ 进入：网络节点 / V2Ray${C_RESET}"
  say

  if command -v vf-node >/dev/null 2>&1; then
    set +e
    vf-node
    local rc=$?
    set -e
    return "$rc"
  fi

  if ! command -v curl >/dev/null 2>&1; then
    say "${C_RED}✗ 当前系统没有 curl，无法打开网络节点模块。${C_RESET}" >&2
    return 3
  fi

  local tmp rc
  tmp="$(mktemp -t p07-vf-node.XXXXXX)"
  chmod 700 "$tmp"

  if ! curl -fsSL "$VF_NODE_INSTALLER" -o "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ VF Node 公共入口下载失败。${C_RESET}" >&2
    return 4
  fi

  set +e
  bash "$tmp"
  rc=$?
  set -e
  rm -f "$tmp"
  return "$rc"
}

pending_slot() {
  local label="$1"
  say
  say "${C_YELLOW}⚠ ${label}尚未接入。${C_RESET}"
  say "${C_GRAY}这个位置已经锁定，等待对应开发者按 P07 模块规则接入；当前不会执行任何假功能。${C_RESET}"
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
        if [[ $rc -ne 0 ]]; then
          say "${C_YELLOW}⚠ 网络节点模块返回退出码 ${rc}；以上方模块自身信息为准。${C_RESET}"
        fi
        pause_menu
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
P07 · 扩展工具箱

Usage:
  p07-toolbox

Slots:
  1. 网络节点 / V2Ray    ready
  2. 功能模块 B          pending
  3. 功能模块 C          pending
EOF
    ;;
  "")
    if [[ -t 0 && -t 1 ]]; then
      main_menu
    else
      printf 'ERROR: P07 Toolbox menu requires an interactive terminal.\n' >&2
      exit 2
    fi
    ;;
  *) printf 'ERROR: unknown argument: %s\n' "$1" >&2; exit 2 ;;
esac
