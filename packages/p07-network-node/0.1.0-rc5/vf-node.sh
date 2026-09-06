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

show_live_summary() {
  load_state
  say
  if [[ -r "$VF_NODE_STATE_FILE" ]]; then
    if service_active; then
      say "状态   ${C_GREEN}● 已安装 · 运行中${C_RESET}"
    else
      say "状态   ${C_RED}● 已安装 · 服务异常${C_RESET}"
    fi
    say "Profile ${C_GREEN}${PROFILE:-VMESS_MKCP_DTLS}${C_RESET}"
    say "Core    ${C_CYAN}${CORE_VERSION:-UNKNOWN}${C_RESET}   ${C_GRAY}Source ${SOURCE_COMMIT:-UNKNOWN}${C_RESET}"
    if [[ -n "${PORT:-}" ]]; then
      if port_in_use_udp "$PORT"; then
        say "UDP     ${C_GREEN}${PORT}/UDP · LISTEN${C_RESET}"
      else
        say "UDP     ${C_RED}${PORT}/UDP · NOT LISTENING${C_RESET}"
      fi
    fi
  elif v2ray_cli >/dev/null 2>&1; then
    say "状态   ${C_YELLOW}● 检测到外部 V2Ray · P07 不接管${C_RESET}"
  else
    say "状态   ${C_GRAY}● 未安装${C_RESET}"
  fi
}

show_menu() {
  show_header
  show_live_summary
  say
  say "${C_GRAY}──────────────────────────────────────────────────────────────${C_RESET}"
  say
  say "  ${C_GREEN}1. [稳定]${C_RESET} 安装稳定节点"
  say "     ${C_GRAY}VMess + mKCP + dtls · 自动选端口${C_RESET}"
  say
  say "  ${C_CYAN}2. [检查]${C_RESET} 查看节点状态"
  say "     ${C_GRAY}服务 / UDP / Core / Source Identity${C_RESET}"
  say
  say "  ${C_MAGENTA}3. [分享]${C_RESET} 生成分享链接"
  say "     ${C_GRAY}仅当前终端显示 · 包含节点凭据${C_RESET}"
  say
  say "  ${C_BLUE}4. [备份]${C_RESET} 备份节点配置"
  say "     ${C_GRAY}root PRIVATE 备份 + SHA256${C_RESET}"
  say
  say "  ${C_YELLOW}5. [实验]${C_RESET} 高速实验 Profile"
  say "     ${C_GRAY}尚未开放 · 不影响长期稳定基线${C_RESET}"
  say
  say "  ${C_RED}6. [危险]${C_RESET} 卸载节点"
  say "     ${C_GRAY}数字确认 + 自动备份 · 不碰其他服务${C_RESET}"
  say
  say "  ${C_GRAY}0. [返回]${C_RESET} 返回 P07"
  say
}

run_and_pause() {
  "$@" || true
  pause_if_tty
}

post_install_menu() {
  local choice=''
  while true; do
    say
    say "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
    say "${C_BOLD}${C_GREEN}节点已就绪 · 下一步${C_RESET}"
    say "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
    say
    say "  ${C_MAGENTA}1. [分享]${C_RESET} 再次显示分享链接"
    say "  ${C_CYAN}2. [检查]${C_RESET} 查看节点状态"
    say "  ${C_BLUE}3. [备份]${C_RESET} 立即备份节点配置"
    say "  ${C_GRAY}0. [返回]${C_RESET} 回到主菜单"
    say
    printf '%b' "${C_BOLD}请选择 [0-3]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) run_and_pause bash "$SCRIPT_DIR/share.sh" ;;
      2) run_and_pause bash "$SCRIPT_DIR/status.sh" ;;
      3) run_and_pause bash "$SCRIPT_DIR/backup.sh" ;;
      0|'') return 0 ;;
      *) warn "请输入 0-3。" ;;
    esac
  done
}

install_from_menu() {
  if bash "$SCRIPT_DIR/install.sh"; then
    post_install_menu
  else
    pause_if_tty
  fi
}

menu_loop() {
  while true; do
    show_menu
    printf '%b' "${C_BOLD}请选择 [0-6]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) install_from_menu ;;
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
  vf-node                    进入彩色菜单
  vf-node --version          显示模块版本
  vf-node install [args]     安装稳定 Profile
  vf-node status             非破坏状态检查
  vf-node check              同 status --quiet
  vf-node url                显示分享链接
  vf-node share              同 url
  vf-node backup             创建并验证 PRIVATE 备份
  vf-node uninstall          数字菜单确认后卸载

兼容：
  v2ray url                  保留原脚本的分享链接命令
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
  url|share)
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
