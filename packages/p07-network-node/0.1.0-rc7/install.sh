#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=lib/core-pin.env
source "$SCRIPT_DIR/lib/core-pin.env"

UPSTREAM_REPO="https://github.com/xyz690/v2ray.git"
UPSTREAM_COMMIT="b73e9c35bb11df60776ddec831d44d02b7fe9ab2"
PROFILE_ID="VMESS_MKCP_DTLS"
VERBOSE="${VF_NODE_VERBOSE:-0}"

usage() {
  cat <<'EOF'
用法：install.sh [--port PORT]

安装长期实测基线：VMess + mKCP + dtls header。
默认自动选择一个未占用的 UDP 端口。
设置 VF_NODE_VERBOSE=1 可显示工程细节。
EOF
}

detail() {
  [[ "$VERBOSE" == '1' ]] || return 0
  say "${C_GRAY}$*${C_RESET}"
}

port=''
while (($#)); do
  case "$1" in
    --port) port="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "未知参数：$1"; usage; exit 2 ;;
  esac
done

require_root

if v2ray_cli >/dev/null 2>&1 || [[ -e /etc/v2ray/config.json ]]; then
  fail "检测到现有 V2Ray。为保护老节点，不会自动覆盖。"
  exit 3
fi

section "VF Node · 安装稳定节点"
info "检查系统环境..."
ensure_dependencies

case "$(uname -m)" in
  x86_64|amd64)
    core_asset="$V2RAY_CORE_AMD64_ASSET"
    core_sha256="$V2RAY_CORE_AMD64_SHA256"
    ;;
  aarch64|arm64)
    core_asset="$V2RAY_CORE_ARM64_ASSET"
    core_sha256="$V2RAY_CORE_ARM64_SHA256"
    ;;
  *)
    fail "暂不支持当前 CPU 架构：$(uname -m)"
    exit 7
    ;;
esac

if [[ -z "$port" ]]; then
  if [[ -t 0 ]]; then
    printf '节点 UDP 端口（直接 Enter 自动选择）：'
    read -r port || true
  fi
  [[ -n "$port" ]] || port="$(random_free_udp_port)"
fi

if ! valid_port "$port"; then
  fail "端口无效：$port"
  exit 2
fi
if port_in_use_udp "$port"; then
  fail "UDP 端口 $port 已被占用。"
  exit 4
fi

say "方案   ${C_GREEN}VMess + mKCP + dtls${C_RESET}"
say "端口   ${C_YELLOW}${port}/UDP${C_RESET}"
say

tmp="$(mktemp -d /tmp/vf-node-install.XXXXXX)"
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

info "准备已审核安装组件..."
detail "Script: xyz690/v2ray @ ${UPSTREAM_COMMIT}"
detail "Core: ${V2RAY_CORE_VERSION} / ${core_asset}"
if ! git clone -q --no-checkout "$UPSTREAM_REPO" "$tmp/upstream"; then
  fail "安装组件下载失败，已停止。"
  exit 5
fi
git -C "$tmp/upstream" checkout -q --detach "$UPSTREAM_COMMIT"
actual="$(git -C "$tmp/upstream" rev-parse HEAD)"
if [[ "$actual" != "$UPSTREAM_COMMIT" ]]; then
  fail "安装组件身份校验失败，已停止。"
  exit 5
fi

patch_log="$tmp/core-patch.log"
if ! python3 "$SCRIPT_DIR/lib/patch_upstream_core.py" \
  "$tmp/upstream/src/download-v2ray.sh" \
  "$V2RAY_CORE_VERSION" \
  "$V2RAY_CORE_AMD64_SHA256" \
  "$V2RAY_CORE_ARM64_SHA256" \
  "$UPSTREAM_COMMIT" >"$patch_log" 2>&1; then
  fail "安装组件安全校验失败，已停止。"
  exit 8
fi
if grep -Eq 'releases/latest|--no-check-certificate' "$tmp/upstream/src/download-v2ray.sh"; then
  fail "安装组件安全校验失败，已停止。"
  exit 8
fi
grep -Fq "P07_V2RAY_CORE_VERSION=${V2RAY_CORE_VERSION}" "$tmp/upstream/src/download-v2ray.sh"
ok "安装组件校验通过"

info "安装稳定节点..."
upstream_log="$tmp/upstream-install.log"
if ! (
  cd "$tmp/upstream"
  printf '1\n10\n%s\n\n\n\n' "$port" | bash ./install.sh local
) >"$upstream_log" 2>&1; then
  fail_log="/root/vf-node-install-failed-$(date -u +%Y%m%dT%H%M%SZ).log"
  install -m 0600 "$upstream_log" "$fail_log"
  fail "节点安装失败。诊断日志：$fail_log"
  exit 11
fi

if ! v2ray_cli >/dev/null 2>&1; then
  fail "安装结束，但没有找到 V2Ray 管理命令。"
  exit 6
fi

core_bin="/usr/bin/v2ray/v2ray"
if [[ ! -x "$core_bin" ]]; then
  fail "安装结束，但没有找到 V2Ray Core。"
  exit 9
fi
core_version_line="$($core_bin version 2>/dev/null | head -n1 || true)"
if [[ "$core_version_line" != *"${V2RAY_CORE_VERSION#v}"* ]]; then
  fail "V2Ray Core 版本校验失败。"
  exit 10
fi

ensure_state_dir
cat > "$VF_NODE_STATE_FILE" <<EOF
PROFILE=${PROFILE_ID}
PORT=${port}
SOURCE_REPO=xyz690/v2ray
SOURCE_COMMIT=${UPSTREAM_COMMIT}
CORE_VERSION=${V2RAY_CORE_VERSION}
CORE_ASSET=${core_asset}
CORE_SHA256=${core_sha256}
INSTALLED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
chmod 0600 "$VF_NODE_STATE_FILE"

info "启动并检查节点..."
if ! service_active; then
  fail "节点已安装，但服务没有正常运行。"
  exit 12
fi
if ! port_in_use_udp "$port"; then
  fail "节点服务已启动，但 UDP 端口没有监听。"
  exit 13
fi
ok "服务与 UDP 检查通过"

say
say "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
say "${C_BOLD}${C_GREEN}✓ 节点安装完成${C_RESET}"
say "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
say "方案   ${C_GREEN}VMess + mKCP + dtls${C_RESET}"
say "端口   ${C_YELLOW}${port}/UDP${C_RESET}"
say "状态   ${C_GREEN}● 运行正常${C_RESET}"
say

if [[ -t 1 && "${VF_NODE_INSTALLER_NO_SHARE:-0}" != '1' ]]; then
  say "${C_MAGENTA}分享链接${C_RESET}"
  say "${C_GRAY}──────────────────────────────────────────────────────────────${C_RESET}"
  print_vmess_url
  say "${C_GRAY}──────────────────────────────────────────────────────────────${C_RESET}"
  say
fi

if [[ -t 0 ]]; then
  say "${C_GRAY}按 Enter 返回主菜单。${C_RESET}"
else
  say "${C_GRAY}运行 vf-node 可进入管理菜单。${C_RESET}"
fi
