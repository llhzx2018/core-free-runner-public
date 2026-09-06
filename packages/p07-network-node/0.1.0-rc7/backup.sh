#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

require_root
load_state

if [[ ! -d /etc/v2ray ]]; then
  fail "没有找到 /etc/v2ray，无法备份。"
  exit 1
fi

install -d -m 0700 "$VF_NODE_BACKUP_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="$VF_NODE_BACKUP_DIR/vf-node-${ts}.tar.gz"
sha_file="$out.sha256"

section "VF Node · 配置备份"
info "创建 PRIVATE 本地备份..."
items=(etc/v2ray)
[[ -d "$VF_NODE_STATE_DIR" ]] && items+=(etc/vf-node)

tar -C / -czf "$out" "${items[@]}"
chmod 0600 "$out"

tar -tzf "$out" >/dev/null
sha256sum "$out" > "$sha_file"
chmod 0600 "$sha_file"

ok "备份创建并验证完成"
say "文件：$out"
say "校验：$sha_file"
warn "备份内可能包含节点凭据，仅保存在 root 私有目录，不要公开上传。"
