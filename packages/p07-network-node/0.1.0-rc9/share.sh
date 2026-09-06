#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

if ! node_healthy; then
  section "VF Node · 分享配置"
  fail "当前节点没有通过健康检查，暂不显示分享链接。"
  say "请先在主菜单选择“安装 / 修复节点”。"
  exit 2
fi

section "VF Node · 分享配置"
warn "分享链接包含节点凭据，只显示在当前终端，不写入 P07 日志。"
say "${C_GRAY}──────────────────────────────────────────────────────────────${C_RESET}"
print_vmess_url
say "${C_GRAY}──────────────────────────────────────────────────────────────${C_RESET}"
