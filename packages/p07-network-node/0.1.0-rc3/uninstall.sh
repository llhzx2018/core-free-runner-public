#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

require_root

if [[ ! -s "$VF_NODE_STATE_FILE" ]]; then
  fail "没有找到 P07 节点状态。为避免误删，不会卸载非 P07 管理的 V2Ray。"
  exit 1
fi

section "VF Node · 卸载"
warn "这会卸载当前 P07 V2Ray 节点。P07 会先创建本地 PRIVATE 备份。"
warn "不会删除 Caddy、系统防火墙或其他无关服务。"
if ! exact_confirm "UNINSTALL_VF_NODE" "这是破坏性操作。"; then
  warn "确认不匹配，已取消。"
  exit 2
fi

bash "$SCRIPT_DIR/backup.sh"

info "停止并禁用 V2Ray 服务..."
systemctl stop v2ray.service >/dev/null 2>&1 || true
systemctl disable v2ray.service >/dev/null 2>&1 || true

info "删除 P07 节点的 V2Ray 运行文件与配置..."
rm -rf /usr/bin/v2ray
rm -f /usr/local/sbin/v2ray
rm -rf /etc/v2ray /var/log/v2ray
rm -f /lib/systemd/system/v2ray.service /etc/systemd/system/v2ray.service /etc/init.d/v2ray

# The pinned upstream installer adds an alias for its management command.
# Remove only that exact alias class; do not touch unrelated shell settings.
if [[ -f /root/.bashrc ]]; then
  sed -i '/^[[:space:]]*alias[[:space:]]\+v2ray=/d' /root/.bashrc
fi

systemctl daemon-reload >/dev/null 2>&1 || true
systemctl reset-failed v2ray.service >/dev/null 2>&1 || true

if service_active || [[ -e /etc/v2ray/config.json ]] || [[ -d /usr/bin/v2ray ]]; then
  fail "卸载后仍检测到 V2Ray 运行面，请人工检查；P07 不会继续扩大删除范围。"
  exit 3
fi

rm -f "$VF_NODE_STATE_FILE"
rmdir "$VF_NODE_STATE_DIR" 2>/dev/null || true

ok "P07 节点卸载完成"
ok "PRIVATE 备份仍保留在 $VF_NODE_BACKUP_DIR"
say "未触碰：Caddy / 防火墙 / DNS / 其他服务"
