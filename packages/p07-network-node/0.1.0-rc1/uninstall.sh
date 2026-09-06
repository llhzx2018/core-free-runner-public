#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

require_root
cli="$(v2ray_cli || true)"
if [[ -z "$cli" ]]; then
  fail "没有找到 v2ray 管理命令。"
  exit 1
fi

section "VF Node · 卸载"
warn "这会卸载当前 V2Ray 节点。P07 会先创建本地 PRIVATE 备份。"
if ! exact_confirm "UNINSTALL_VF_NODE" "这是破坏性操作。"; then
  warn "确认不匹配，已取消。"
  exit 2
fi

bash "$SCRIPT_DIR/backup.sh"
info "调用现有 V2Ray 管理命令执行卸载..."
"$cli" uninstall

if v2ray_cli >/dev/null 2>&1 || service_active; then
  fail "卸载命令结束，但仍检测到 V2Ray。请人工检查，不会继续删除目录。"
  exit 3
fi

if [[ -d "$VF_NODE_STATE_DIR" ]]; then
  rm -f "$VF_NODE_STATE_FILE"
  rmdir "$VF_NODE_STATE_DIR" 2>/dev/null || true
fi

ok "卸载流程完成。备份仍保留在 $VF_NODE_BACKUP_DIR"
