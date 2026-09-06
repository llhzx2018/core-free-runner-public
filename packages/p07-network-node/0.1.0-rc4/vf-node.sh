#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

show_header() {
  clear 2>/dev/null || true
  say "${C_CYAN}┌──────────────────────────────────────────────────────────────┐${C_RESET}"
  say "${C_CYAN}│${C_RESET}  ${C_BOLD}P07 · VF Network Node${C_RESET}   ${C_GRAY}v${VF_NODE_VERSION}${C_RESET}                         ${C_CYAN}│${C_RESET}"
  say "${C_CYAN}│${C_RESET}  VMess · mKCP · dtls   ${C_GREEN}长期稳定基线${C_RESET}                  ${C_CYAN}│${C_RESET}"
  say "${C_CYAN}└──────────────────────────────────────────────────────────────┘${C_RESET}"
}

show_menu() {
  show_header
  say
  say "  ${C_GREEN}1.${C_RESET} 安装稳定节点"
  say "     ${C_GRAY}固定 Profile：VMess + mKCP + dtls${C_RESET}"
  say
  say "  ${C_CYAN}2.${C_RESET} 查看节点状态"
  say "     ${C_GRAY}服务 / UDP 监听 / Source Identity${C_RESET}"
  say
  say "  ${C_MAGENTA}3.${C_RESET} 生成分享链接"
  say "     ${C_GRAY}仅显示在当前终端，不写日志${C_RESET}"
  say
  say "  ${C_BLUE}4.${C_RESET} 备份节点配置"
  say "     ${C_GRAY}root 私有备份 + SHA256 验证${C_RESET}"
  say
  say "  ${C_YELLOW}5.${C_RESET} 高速实验 Profile"
  say "     ${C_GRAY}尚未开放；不会影响稳定基线${C_RESET}"
  say
  say "  ${C_RED}6.${C_RESET} 卸载节点"
  say "     ${C_GRAY}数字确认 + 自动备份；不需要输入英文确认词${C_RESET}"
  say
  say "  ${C_GRAY}0.${C_RESET} 返回 P07"
  say
}

run_and_pause() {
  "$@" || true
  pause_if_tty
}

menu_loop() {
  while true; do
    show_menu
    printf '请选择 [0-6]：'
    read -r choice || return 0
    case "$choice" in
      1) run_and_pause bash "$SCRIPT_DIR/install.sh" ;;
      2) run_and_pause bash "$SCRIPT_DIR/status.sh" ;;
      3) run_and_pause bash "$SCRIPT_DIR/share.sh" ;;
      4) run_and_pause bash "$SCRIPT_DIR/backup.sh" ;;
      5)
        say
        warn "高速实验 Profile 仍处于设计/验证阶段。稳定基线不会被修改。"
        pause_if_tty
        ;;
      6) run_and_pause bash "$SCRIPT_DIR/uninstall.sh" ;;
      0) return 0 ;;
      *) warn "无效选择：$choice"; sleep 1 ;;
    esac
  done
}

usage() {
  cat <<EOF
VF Network Node ${VF_NODE_VERSION}

用法：
  vf-node.sh                 进入彩色菜单
  vf-node.sh --version       显示模块版本
  vf-node.sh install [args]  安装稳定 Profile
  vf-node.sh status          非破坏状态检查
  vf-node.sh check           同 status --quiet
  vf-node.sh share           显示分享链接
  vf-node.sh backup          创建并验证 PRIVATE 备份
  vf-node.sh uninstall       数字菜单确认后卸载
EOF
}

case "${1:-}" in
  --version|version)
    printf 'VF Network Node %s\n' "$VF_NODE_VERSION"
    ;;
  install)
    shift
    exec bash "$SCRIPT_DIR/install.sh" "$@"
    ;;
  status)
    exec bash "$SCRIPT_DIR/status.sh"
    ;;
  check)
    exec bash "$SCRIPT_DIR/status.sh" --quiet
    ;;
  share)
    exec bash "$SCRIPT_DIR/share.sh"
    ;;
  backup)
    exec bash "$SCRIPT_DIR/backup.sh"
    ;;
  uninstall)
    exec bash "$SCRIPT_DIR/uninstall.sh"
    ;;
  -h|--help|help)
    usage
    ;;
  '')
    if [[ -t 0 ]]; then
      menu_loop
    else
      usage
    fi
    ;;
  *)
    fail "未知命令：$1"
    usage
    exit 2
    ;;
esac
