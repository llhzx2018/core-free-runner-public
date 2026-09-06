#!/usr/bin/env bash
set -Eeuo pipefail

VERSION='0.1.0-rc1'
PACKAGE_PATH="packages/p07-network-node/${VERSION}"
RAW_BASE="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/${PACKAGE_PATH}"
MANIFEST_SHA256='465c9c6279700cf17f46133e4c3f6f334fe1a227871cf18b63079eade040170a'
TARGET='/opt/vf-network-node'
ENTRY='/usr/local/bin/vf-node'

if [[ -t 1 && "${NO_COLOR:-0}" != '1' ]]; then
  R=$'\033[0m'; B=$'\033[1m'; RED=$'\033[91m'; GREEN=$'\033[92m'; YELLOW=$'\033[93m'; CYAN=$'\033[96m'
else
  R=''; B=''; RED=''; GREEN=''; YELLOW=''; CYAN=''
fi

say()  { printf '%b\n' "$*"; }
ok()   { say "${GREEN}✓${R} $*"; }
info() { say "${CYAN}●${R} $*"; }
warn() { say "${YELLOW}⚠${R} $*"; }
fail() { say "${RED}✗${R} $*" >&2; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  fail '请使用 root 运行。'
  exit 1
fi

say "${CYAN}┌──────────────────────────────────────────────────────────────┐${R}"
say "${CYAN}│${R}  ${B}P07 · VF Network Node${R}   ${VERSION}                           ${CYAN}│${R}"
say "${CYAN}│${R}  VMess · mKCP · dtls   ${GREEN}长期稳定基线${R}                  ${CYAN}│${R}"
say "${CYAN}└──────────────────────────────────────────────────────────────┘${R}"
say

# The RC1 baseline intentionally refuses to touch an existing V2Ray node.
if [[ -e /etc/v2ray/config.json || -x /usr/local/sbin/v2ray || -x /usr/bin/v2ray/v2ray ]] || command -v v2ray >/dev/null 2>&1; then
  warn '检测到这台服务器已经存在 V2Ray。'
  warn '为保护你现有的长期节点，一键安装器不会覆盖、升级或修改它。'
  say '请在一台新的 VPS 上测试 RC1。'
  exit 3
fi

for cmd in curl sha256sum install; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    fail "缺少必要命令：${cmd}"
    exit 2
  fi
done

tmp="$(mktemp -d /tmp/vf-node-public.XXXXXX)"
stage="${TARGET}.new.$$"
cleanup() {
  rm -rf "$tmp" "$stage"
}
trap cleanup EXIT
mkdir -p "$tmp/pkg/lib" "$stage/lib"

info '下载并校验公开 RC1 Manifest...'
curl -fsSL --proto '=https' --tlsv1.2 "${RAW_BASE}/MANIFEST.sha256" -o "$tmp/pkg/MANIFEST.sha256"
printf '%s  %s\n' "$MANIFEST_SHA256" "$tmp/pkg/MANIFEST.sha256" | sha256sum -c - >/dev/null || {
  fail 'Manifest SHA256 校验失败，已停止。'
  exit 10
}
ok 'Manifest 校验通过'

files=(
  VERSION
  vf-node.sh
  install.sh
  status.sh
  share.sh
  backup.sh
  uninstall.sh
  lib/common.sh
  lib/core-pin.env
  lib/patch_upstream_core.py
)

info '下载 RC1 运行文件...'
for f in "${files[@]}"; do
  mkdir -p "$tmp/pkg/$(dirname "$f")"
  curl -fsSL --proto '=https' --tlsv1.2 "${RAW_BASE}/${f}" -o "$tmp/pkg/$f"
done

(
  cd "$tmp/pkg"
  sha256sum -c MANIFEST.sha256 >/dev/null
) || {
  fail 'RC1 文件 SHA256 校验失败，已停止。'
  exit 11
}
ok 'RC1 运行文件校验通过'

info '安装 VF Network Node...'
cp -a "$tmp/pkg/VERSION" "$tmp/pkg/vf-node.sh" "$tmp/pkg/install.sh" "$tmp/pkg/status.sh" "$tmp/pkg/share.sh" "$tmp/pkg/backup.sh" "$tmp/pkg/uninstall.sh" "$stage/"
cp -a "$tmp/pkg/lib/common.sh" "$tmp/pkg/lib/core-pin.env" "$tmp/pkg/lib/patch_upstream_core.py" "$stage/lib/"
chmod 0755 "$stage/vf-node.sh" "$stage/install.sh" "$stage/status.sh" "$stage/share.sh" "$stage/backup.sh" "$stage/uninstall.sh" "$stage/lib/patch_upstream_core.py"
chmod 0644 "$stage/VERSION" "$stage/lib/common.sh" "$stage/lib/core-pin.env"

if [[ -d "$TARGET" ]]; then
  rm -rf "${TARGET}.previous"
  mv "$TARGET" "${TARGET}.previous"
fi
mv "$stage" "$TARGET"
ln -sfn "$TARGET/vf-node.sh" "$ENTRY"

if [[ "$(NO_COLOR=1 "$ENTRY" --version)" != "VF Network Node ${VERSION}" ]]; then
  fail 'vf-node 安装自检失败。'
  if [[ -d "${TARGET}.previous" ]]; then
    rm -rf "$TARGET"
    mv "${TARGET}.previous" "$TARGET"
    ln -sfn "$TARGET/vf-node.sh" "$ENTRY"
  fi
  exit 12
fi
rm -rf "${TARGET}.previous"
ok "VF Network Node ${VERSION} 安装器已就绪"

say
info '正在自动安装稳定节点：VMess + mKCP + dtls ...'
# stdin is intentionally closed so the module auto-selects a free UDP port.
if ! NO_COLOR="${NO_COLOR:-0}" "$ENTRY" install </dev/null; then
  fail '节点安装未完成。上方错误就是当前真实状态。'
  exit 20
fi

if ! NO_COLOR="${NO_COLOR:-0}" "$ENTRY" check; then
  fail '节点安装完成，但健康检查没有 PASS。'
  exit 21
fi

ok '节点安装与本机健康检查 PASS'
say
say "以后直接输入：${B}vf-node${R}"
say '会进入彩色节点管理菜单。'

if [[ "${VF_NODE_INSTALLER_NO_SHARE:-0}" != '1' ]]; then
  say
  warn '下面的分享链接包含节点凭据，请只保存到你自己的客户端。'
  "$ENTRY" share
fi
