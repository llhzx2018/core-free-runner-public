#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

cli="$(v2ray_cli || true)"
if [[ -z "$cli" ]]; then
  fail "没有找到 v2ray 管理命令。"
  exit 1
fi

section "VF Node · 分享配置"
warn "分享链接包含节点凭据，只显示在当前终端，不写入 P07 日志。"
say
"$cli" url
