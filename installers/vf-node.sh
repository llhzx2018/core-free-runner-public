#!/usr/bin/env bash
set -Eeuo pipefail

VERSION='0.1.0-rc6'
PACKAGE_PATH="packages/p07-network-node/${VERSION}"
RAW_BASE="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/${PACKAGE_PATH}"
MANIFEST_SHA256='94855a3f9208ac939b0f73a5ce392dc41f1f1e850ebd4b1f142489eaae480603'
TARGET='/opt/vf-network-node'
ENTRY='/usr/local/bin/vf-node'
STATE='/etc/vf-node/state.env'

if [[ -t 1 && "${NO_COLOR:-0}" != '1' ]]; then
  R=$'\033[0m'; B=$'\033[1m'
  RED=$'\033[91m'; GREEN=$'\033[92m'; YELLOW=$'\033[93m'
  BLUE=$'\033[94m'; MAGENTA=$'\033[95m'; CYAN=$'\033[96m'; GRAY=$'\033[90m'
else
  R=''; B=''; RED=''; GREEN=''; YELLOW=''; BLUE=''; MAGENTA=''; CYAN=''; GRAY=''
fi

say()  { printf '%b\n' "$*"; }
ok()   { say "${GREEN}✓${R} $*"; }
info() { say "${CYAN}●${R} $*"; }
warn() { say "${YELLOW}⚠${R} $*"; }
fail() { say "${RED}✗${R} $*" >&2; }

pause_return() {
  [[ -t 0 ]] || return 0
  printf '\n按 Enter 返回菜单...'
  read -r _ || true
}

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

installed_version() {
  if [[ -x "$ENTRY" ]]; then
    NO_COLOR=1 "$ENTRY" --version 2>/dev/null | awk '{print $NF}' || true
  fi
}

print_header() {
  say "${CYAN}┌──────────────────────────────────────────────────────────────┐${R}"
  say "${CYAN}│${R}  ${B}P07 · VF Network Node${R}   ${GRAY}${VERSION}${R}                           ${CYAN}│${R}"
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

  info '下载并校验公开 RC6 Manifest...'
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

  info '下载 RC6 运行文件...'
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
    fail 'RC6 文件 SHA256 校验失败，已停止。'
    return 12
  fi
  ok 'RC6 运行文件校验通过'

  info '安装 / 更新 VF Network Node 管理模块...'
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
    fail 'vf-node 管理模块自检失败。'
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

refresh_manager_if_needed() {
  p07_installed || return 0
  local current
  current="$(installed_version)"
  if [[ "$current" != "$VERSION" ]]; then
    info "检测到 P07 管理模块 ${current:-UNKNOWN}，自动更新到 ${VERSION}..."
    install_runtime_files
    ok '只更新管理体验；现有节点配置、UUID、端口保持不变'
  fi
}

post_install_actions() {
  [[ -t 0 ]] || return 0
  local choice=''
  while :; do
    say
    say "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
    say "${B}${GREEN}节点已就绪 · 下一步${R}"
    say "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
    say
    say "  ${CYAN}1. [管理]${R} 打开节点管理菜单"
    say "  ${MAGENTA}2. [分享]${R} 再次显示干净分享链接"
    say "  ${BLUE}3. [备份]${R} 立即备份节点配置"
    say "  ${GRAY}0. [返回]${R} 回到一键主菜单"
    say
    printf '%b' "${B}请选择 [0-3]：${R}"
    read -r choice || return 0
    case "$choice" in
      1) "$ENTRY" ;;
      2) "$ENTRY" url; pause_return ;;
      3) "$ENTRY" backup; pause_return ;;
      0|'') return 0 ;;
      *) warn '请输入 0-3。' ;;
    esac
  done
}

install_node() {
  if p07_installed; then
    warn "这台服务器已经安装 P07 节点（$(installed_version)）。"
    say '无需重装；节点配置保持原样。'
    post_install_actions
    return 0
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

  say
  ok '节点安装与本机健康检查 PASS'
  say "${GRAY}无需记命令；下面直接给你下一步。${R}"
  post_install_actions
}

manage_node() {
  if p07_installed; then
    install_runtime_files || return $?
    "$ENTRY"
    return 0
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

  install_runtime_files || return $?
  "$ENTRY" uninstall
}

menu() {
  refresh_manager_if_needed
  while :; do
    clear 2>/dev/null || true
    print_header
    if p07_installed; then
      say "状态   ${GREEN}● 已安装 · $(installed_version)${R}"
    elif any_v2ray_present; then
      say "状态   ${YELLOW}● 检测到非 P07 V2Ray · 受保护${R}"
    else
      say "状态   ${GRAY}● 未安装${R}"
    fi
    say
    say "  ${GREEN}1. [安装]${R} 安装稳定节点"
    say "  ${CYAN}2. [管理]${R} 进入节点管理"
    say "  ${MAGENTA}3. [分享]${R} 显示分享链接"
    say "  ${RED}4. [危险]${R} 卸载节点"
    say "  ${GRAY}0. [退出]${R} 退出"
    say
    printf '%b' "${B}请选择 [0-4]：${R}"
    local choice
    read -r choice || return 0
    case "$choice" in
      1) if ! install_node; then pause_return; fi ;;
      2) if ! manage_node; then pause_return; fi ;;
      3)
        if p07_installed; then "$ENTRY" url; else warn '当前没有 P07 节点。'; fi
        pause_return
        ;;
      4) uninstall_node || true; pause_return ;;
      0) return 0 ;;
      *) warn '无效选择。'; sleep 1 ;;
    esac
  done
}

require_root

case "${1:-}" in
  install) refresh_manager_if_needed; install_node ;;
  manage|menu) menu ;;
  uninstall) refresh_manager_if_needed; uninstall_node ;;
  '')
    if [[ -t 0 ]]; then
      menu
    else
      refresh_manager_if_needed
      install_node
    fi
    ;;
  -h|--help)
    cat <<'EOF'
P07 · VF Network Node 一键入口

交互运行：直接显示安装 / 管理 / 分享 / 卸载菜单。
旧版 P07：再次运行一键入口会只升级管理模块，不改节点 UUID/端口/配置。
安装成功：只显示干净 vmess:// 分享链接，再显示下一步菜单。
非交互运行：默认执行安装。
EOF
    ;;
  *) fail "未知参数：$1"; exit 2 ;;
esac
