#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

section "VF Node · 分享配置"
warn "分享链接包含节点凭据，只显示在当前终端，不写入 P07 日志。"
say "${C_GRAY}──────────────────────────────────────────────────────────────${C_RESET}"
print_vmess_url
say "${C_GRAY}──────────────────────────────────────────────────────────────${C_RESET}"
