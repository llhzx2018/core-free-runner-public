#!/usr/bin/env bash
set -Eeuo pipefail

VERSION='0.1.0-rc2'
PACKAGE_PATH="packages/p07-network-node/${VERSION}"
RAW_BASE="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/${PACKAGE_PATH}"
MANIFEST_SHA256='819634dc645652899039e73ffc9569715f270b5a80a808d3cf1d450b1e164f68'
TARGET='/opt/vf-network-node'
ENTRY='/usr/local/bin/vf-node'
STATE='/etc/vf-node/state.env'

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

write_entry() {
  rm -f "$ENTRY"
  cat > "$ENTRY" <<EOF
#!/usr/bin/env bash
exec "$TARGET/vf-node.sh" "\$@"
EOF
  chmod 0755 "$ENTRY"
}

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    fail '请使用 root 运行。'
    exit 1
  fi
}

p07_installed() {
  [[ -x "$ENTRY" && -x "$TARGET/vf-node.sh" && -s "$STATE" ]]
}

any_v2ray_present() {
  [[ -e /etc/v2ray/config.json || -x /usr/local/sbin/v2ray || -x /usr/bin/v2ray/v2ray ]] || command -v v2ray >/dev/null 2>&1
}

print_header() {
  say "${CYAN}┌──────────────────────────────────────────────────────────────┐${R}"
  say "${CYAN}│${R}  ${B}P07 · VF Network Node${R}   ${VERSION}                           ${CYAN}│${R}"
  say "${CYAN}│${R}  VMess · mKCP · dtls   ${GREEN}长期稳定基线${R}                  ${CYAN}│${R}"
  say "${CYAN}└──────────────────────────────────────────────────────────────┘${R}"
  say
}

install_runtime_files() {
  for cmd in curl sha256sum install; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      fail "缺少必要命令：${cmd}"
      return 2
    fi
  done

  local tmp stage
  tmp="$(mktemp -d /tmp/vf-node-public.XXXXXX)"
  stage="${TARGET}.new.$$"
  mkdir -p "$tmp/pkg/lib" "$stage/lib"

  info '下载并校验公开 RC2 Manifest...'
  if ! curl -fsSL --proto '=https' --tlsv1.2 "${RAW_BASE}/MANIFEST.sha256" -o "$tmp/pkg/MANIFEST.sha256"; then
    rm -rf "$tmp" "$stage"
    fail 'Manifest 下载失败，已停止。'
    return 9
  fi
  if ! printf '%s  %s\n' "$MANIFEST_SHA256" "$tmp/pkg/MANIFEST.sha256" | sha256sum -c - >/dev/null; then
    rm -rf "$tmp" "$stage"
    fail 'Manifest SHA256 校验失败，已停止。'
    return 10
  fi
  ok 'Manifest 校验通过'

  local files=(
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

  info '下载 RC2 运行文件...'
  local f
  for f in "${files[@]}"; do
    mkdir -p "$tmp/pkg/$(dirname "$f")"
    if ! curl -fsSL --proto '=https' --tlsv1.2 "${RAW_BASE}/${f}" -o "$tmp/pkg/$f"; then
      rm -rf "$tmp" "$stage"
      fail "运行文件下载失败：${f}"
      return 11
    fi
  done

  if ! (
    cd "$tmp/pkg"
    sha256sum -c MANIFEST.sha256 >/dev/null
  ); then
    rm -rf "$tmp" "$stage"
    fail 'RC2 文件 SHA256 校验失败，已停止。'
    return 12
  fi
  ok 'RC2 运行文件校验通过'

  info '安装 VF Network Node 管理模块...'
  cp -a "$tmp/pkg/VERSION" "$tmp/pkg/vf-node.sh" "$tmp/pkg/install.sh" "$tmp/pkg/status.sh" "$tmp/pkg/share.sh" "$tmp/pkg/backup.sh" "$tmp/pkg/uninstall.sh" "$stage/"
  cp -a "$tmp/pkg/lib/common.sh" "$tmp/pkg/lib/core-pin.env" "$tmp/pkg/lib/patch_upstream_core.py" "$stage/lib/"
  chmod 0755 "$stage/vf-node.sh" "$stage/install.sh" "$stage/status.sh" "$stage/share.sh" "$stage/backup.sh" "$stage/uninstall.sh" "$stage/lib/patch_upstream_core.py"
  chmod 0644 "$stage/VERSION" "$stage/lib/common.sh" "$stage/lib/core-pin.env"

  if [[ -d "$TARGET" ]]; then
    rm -rf "${TARGET}.previous"
    mv "$TARGET" "${TARGET}.previous"
  fi
  mv "$stage" "$TARGET"
  write_entry

  if [[ "$(NO_COLOR=1 "$ENTRY" --version)" != "VF Network Node ${VERSION}" ]]; then
    fail 'vf-node 安装自检失败。'
    if [[ -d "${TARGET}.previous" ]]; then
      rm -rf "$TARGET"
      mv "${TARGET}.previous" "$TARGET"
      write_entry
    fi
    rm -rf "$tmp" "$stage"
    return 13
  fi
  rm -rf "${TARGET}.previous" "$tmp" "$stage"
  ok "VF Network Node ${VERSION} 管理模块已就绪"
}

install_node() {
  if p07_installed; then
    warn '这台服务器已经安装 P07 节点。'
    say '请使用「进入节点管理」查看状态、分享、备份或卸载。'
    return 3
  fi

  if any_v2ray_present; then
    warn '检测到这台服务器已经存在 V2Ray，但不是当前 P07 管理节点。'
    warn '为保护旧节点，P07 不会覆盖、升级或修改它。'
    return 3
  fi

  install_runtime_files || return $?

  say
  info '正在自动安装稳定节点：VMess + mKCP + dtls ...'
  if ! NO_COLOR="${NO_COLOR:-0}" "$ENTRY" install </dev/null; then
    fail '节点安装未完成。上方错误就是当前真实状态。'
    return 20
  fi

  if ! NO_COLOR="${NO_COLOR:-0}" "$ENTRY" check; then
    fail '节点安装完成，但健康检查没有 PASS。'
    return 21
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
}

manage_node() {
  if p07_installed; then
    exec "$ENTRY"
  fi
  if any_v2ray_present; then
    warn '检测到 V2Ray，但它不是当前 P07 管理节点。'
    warn '为了安全，不接管、不改写旧节点。'
    return 3
  fi
  warn '当前还没有安装 P07 节点。'
  return 1
}

uninstall_node() {
  if ! p07_installed; then
    if any_v2ray_present; then
      warn '检测到 V2Ray，但它不是当前 P07 管理节点。'
      warn '为了避免误删，P07 不会卸载这个旧节点。'
      return 3
    fi
    warn '当前没有 P07 节点可以卸载。'
    return 1
  fi
  "$ENTRY" uninstall
}

menu() {
  while :; do
    clear 2>/dev/null || true
    print_header
    if p07_installed; then
      say "状态：${GREEN}● 已安装${R}"
    elif any_v2ray_present; then
      say "状态：${YELLOW}● 检测到非 P07 V2Ray，受保护${R}"
    else
      say "状态：${YELLOW}● 未安装${R}"
    fi
    say
    say "  ${CYAN}1.${R} 安装稳定节点"
    say "  ${CYAN}2.${R} 进入节点管理"
    say "  ${RED}3.${R} 卸载节点"
    say "  0. 退出"
    say
    printf '请选择 [0-3]：'
    local choice
    read -r choice || return 0
    case "$choice" in
      1) install_node; say; read -r -p '按 Enter 返回菜单...' _ || true ;;
      2) manage_node; say; read -r -p '按 Enter 返回菜单...' _ || true ;;
      3) uninstall_node; say; read -r -p '按 Enter 返回菜单...' _ || true ;;
      0) return 0 ;;
      *) warn '无效选择。'; sleep 1 ;;
    esac
  done
}

require_root

case "${1:-}" in
  install) install_node ;;
  manage|menu) menu ;;
  uninstall) uninstall_node ;;
  '')
    if [[ -t 0 ]]; then
      menu
    else
      install_node
    fi
    ;;
  -h|--help)
    cat <<'EOF'
P07 · VF Network Node 一键入口

交互运行：直接显示安装 / 管理 / 卸载菜单。
非交互运行：默认执行安装。
EOF
    ;;
  *) fail "未知参数：$1"; exit 2 ;;
esac
