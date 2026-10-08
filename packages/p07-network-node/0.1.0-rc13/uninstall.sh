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

confirm_uninstall() {
  say
  say "${C_BOLD}卸载前会保留安全恢复副本，只删除工具管理的 V2Ray。${C_RESET}"
  say "不会修改：Caddy / 防火墙 / DNS / 其他服务"
  say
  printf '确认卸载？[y/N]：'
  local choice=''
  read -r choice || choice=''
  [[ "$choice" =~ ^[Yy]$ ]]
}

section "P07 · 网络节点卸载"
if ! confirm_uninstall; then
  warn "已取消卸载。节点没有任何变化。"
  exit 2
fi

create_uninstall_recovery_copy() {
  local ts out archive_sha
  if [[ ! -d /etc/v2ray ]]; then
    fail "未找到节点配置目录，为防误删已取消卸载。"
    return 1
  fi
  install -d -m 0700 "$VF_NODE_BACKUP_DIR" || return 1
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  out="${VF_NODE_BACKUP_DIR}/vf-node-before-uninstall-${ts}.tar.gz"
  local items=(etc/v2ray)
  [[ -d "$VF_NODE_STATE_DIR" ]] && items+=(etc/vf-node)
  if ! tar -C / -czf "$out" "${items[@]}"; then
    rm -f -- "$out"
    fail "恢复副本创建失败，已取消卸载。"
    return 1
  fi
  chmod 0600 "$out"
  if ! tar -tzf "$out" >/dev/null; then
    rm -f -- "$out"
    fail "恢复副本验证失败，已取消卸载。"
    return 1
  fi
  archive_sha="${out}.sha256"
  if ! sha256sum "$out" >"$archive_sha"; then
    rm -f -- "$out" "$archive_sha"
    fail "恢复副本校验失败，已取消卸载。"
    return 1
  fi
  chmod 0600 "$archive_sha"
  ok "卸载前安全恢复副本已校验"
}
create_uninstall_recovery_copy || exit 1

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

say
ok "P07 节点卸载完成"
ok "安全恢复副本保存在 $VF_NODE_BACKUP_DIR"
say "未触碰：Caddy / 防火墙 / DNS / 其他服务"
