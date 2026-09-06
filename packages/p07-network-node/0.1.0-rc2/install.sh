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

usage() {
  cat <<'EOF'
用法：install.sh [--port PORT]

安装长期实测基线：VMess + mKCP + dtls header。
默认自动选择一个未占用的 UDP 端口。
EOF
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
  fail "检测到现有 V2Ray。V0.1 为保护老节点，不会自动覆盖。"
  say "请先使用：vf-node status / vf-node backup"
  exit 3
fi

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
    fail "V0.1 固定 Core 暂不支持当前 CPU 架构：$(uname -m)"
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

tmp="$(mktemp -d /tmp/vf-node-install.XXXXXX)"
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

section "VF Node · 稳定基线安装"
say "Profile  : ${C_GREEN}${PROFILE_ID}${C_RESET}"
say "Transport: VMess + mKCP + dtls header"
say "UDP Port : ${C_YELLOW}${port}${C_RESET}"
say "Script   : xyz690/v2ray @ ${UPSTREAM_COMMIT:0:12}"
say "Core     : ${V2RAY_CORE_VERSION} / ${core_asset}"

info "获取固定上游脚本快照..."
git clone -q --no-checkout "$UPSTREAM_REPO" "$tmp/upstream"
git -C "$tmp/upstream" checkout -q --detach "$UPSTREAM_COMMIT"
actual="$(git -C "$tmp/upstream" rev-parse HEAD)"
if [[ "$actual" != "$UPSTREAM_COMMIT" ]]; then
  fail "上游 Source Identity 校验失败。"
  exit 5
fi
ok "上游 Script Source Identity 校验通过"

info "将上游 Core 下载逻辑冻结到 ${V2RAY_CORE_VERSION} 并启用 SHA256 校验..."
python3 "$SCRIPT_DIR/lib/patch_upstream_core.py" \
  "$tmp/upstream/src/download-v2ray.sh" \
  "$V2RAY_CORE_VERSION" \
  "$V2RAY_CORE_AMD64_SHA256" \
  "$V2RAY_CORE_ARM64_SHA256" \
  "$UPSTREAM_COMMIT"

if grep -Eq 'releases/latest|--no-check-certificate' "$tmp/upstream/src/download-v2ray.sh"; then
  fail "Core 固定补丁自检失败：仍检测到 mutable/insecure 下载路径。"
  exit 8
fi
grep -Fq "P07_V2RAY_CORE_VERSION=${V2RAY_CORE_VERSION}" "$tmp/upstream/src/download-v2ray.sh"
ok "Core Source Identity 已冻结"

info "执行固定 Profile 安装（选项 10：mKCP_dtls）..."
upstream_log="$tmp/upstream-install.log"
if ! (
  cd "$tmp/upstream"
  printf '1\n10\n%s\n\n\n\n' "$port" | bash ./install.sh local
) >"$upstream_log" 2>&1; then
  fail_log="/root/vf-node-install-failed-$(date -u +%Y%m%dT%H%M%SZ).log"
  install -m 0600 "$upstream_log" "$fail_log"
  fail "底层兼容安装失败，已停止。诊断日志保存在：$fail_log"
  exit 11
fi
ok "固定 Profile 兼容层安装完成"

cli="$(v2ray_cli || true)"
if [[ -z "$cli" ]]; then
  fail "安装脚本结束，但没有找到 v2ray 管理命令。"
  exit 6
fi

core_bin="/usr/bin/v2ray/v2ray"
if [[ ! -x "$core_bin" ]]; then
  fail "安装结束，但没有找到固定 V2Ray Core。"
  exit 9
fi
core_version_line="$($core_bin version 2>/dev/null | head -n1 || true)"
if [[ "$core_version_line" != *"${V2RAY_CORE_VERSION#v}"* ]]; then
  fail "V2Ray Core 版本与固定版本不一致。"
  exit 10
fi
ok "V2Ray Core 版本验证通过：${V2RAY_CORE_VERSION}"

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

if service_active; then
  ok "V2Ray 服务已运行"
else
  warn "V2Ray 已安装，但 systemd 当前未报告 active；请运行 status 检查。"
fi

say
ok "稳定基线安装完成"
say "Profile：${C_BOLD}VMess + mKCP + dtls${C_RESET}"
say "Core：${C_BOLD}${V2RAY_CORE_VERSION}${C_RESET}"
say "端口：${C_BOLD}${port}/UDP${C_RESET}"
say
say "查看状态：${C_CYAN}bash $SCRIPT_DIR/vf-node.sh status${C_RESET}"
say "生成链接：${C_CYAN}bash $SCRIPT_DIR/vf-node.sh share${C_RESET}"
