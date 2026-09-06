#!/usr/bin/env bash
set -Eeuo pipefail

VERSION='0.1.0-rc9'
PACKAGE_PATH="packages/p07-network-node/${VERSION}"
RAW_BASE="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/${PACKAGE_PATH}"
MANIFEST_SHA256='0f2db8e08ac610f870cbe0e979fc90e904f36b07e561d8f657d77cc1f073f3c3'
TARGET='/opt/vf-network-node'
ENTRY='/usr/local/bin/vf-node'

if [[ -t 1 && "${NO_COLOR:-0}" != '1' ]]; then
  R=$'\033[0m'; RED=$'\033[91m'; GREEN=$'\033[92m'; CYAN=$'\033[96m'
else
  R=''; RED=''; GREEN=''; CYAN=''
fi
say()  { printf '%b\n' "$*"; }
ok()   { say "${GREEN}✓${R} $*"; }
info() { say "${CYAN}●${R} $*"; }
fail() { say "${RED}✗${R} $*" >&2; }

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    fail '请使用 root 运行。'
    exit 1
  fi
}

write_entry() {
  rm -f "$ENTRY"
  cat > "$ENTRY" <<EOF
#!/usr/bin/env bash
exec "$TARGET/vf-node.sh" "\$@"
EOF
  chmod 0755 "$ENTRY"
}

installed_version() {
  if [[ -x "$ENTRY" ]]; then
    NO_COLOR=1 "$ENTRY" --version 2>/dev/null | awk '{print $NF}' || true
  fi
}

manager_ready() {
  [[ -x "$ENTRY" && -x "$TARGET/vf-node.sh" ]] || return 1
  [[ "$(installed_version)" == "$VERSION" ]]
}

install_runtime_files() {
  for cmd in curl sha256sum install; do
    command -v "$cmd" >/dev/null 2>&1 || { fail "缺少必要命令：${cmd}"; return 2; }
  done

  local tmp stage f
  tmp="$(mktemp -d /tmp/vf-node-public.XXXXXX)"
  stage="${TARGET}.new.$$"
  mkdir -p "$tmp/pkg/lib" "$stage/lib"

  info "下载并校验 VF Network Node ${VERSION}..."
  if ! curl -fsSL --proto '=https' --tlsv1.2 "${RAW_BASE}/MANIFEST.sha256" -o "$tmp/pkg/MANIFEST.sha256"; then
    rm -rf "$tmp" "$stage"
    fail '安装包清单下载失败。'
    return 9
  fi
  if ! printf '%s  %s\n' "$MANIFEST_SHA256" "$tmp/pkg/MANIFEST.sha256" | sha256sum -c - >/dev/null; then
    rm -rf "$tmp" "$stage"
    fail '安装包清单校验失败。'
    return 10
  fi

  local files=(
    VERSION vf-node.sh install.sh status.sh share.sh backup.sh uninstall.sh
    lib/common.sh lib/core-pin.env lib/patch_upstream_core.py
  )
  for f in "${files[@]}"; do
    mkdir -p "$tmp/pkg/$(dirname "$f")"
    if ! curl -fsSL --proto '=https' --tlsv1.2 "${RAW_BASE}/${f}" -o "$tmp/pkg/$f"; then
      rm -rf "$tmp" "$stage"
      fail "运行文件下载失败：${f}"
      return 11
    fi
  done

  if ! (cd "$tmp/pkg" && sha256sum -c MANIFEST.sha256 >/dev/null); then
    rm -rf "$tmp" "$stage"
    fail '运行文件校验失败。'
    return 12
  fi

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

  if ! manager_ready; then
    fail 'VF Network Node 管理器自检失败。'
    if [[ -d "${TARGET}.previous" ]]; then
      rm -rf "$TARGET"
      mv "${TARGET}.previous" "$TARGET"
      write_entry
    fi
    rm -rf "$tmp" "$stage"
    return 13
  fi

  rm -rf "${TARGET}.previous" "$tmp" "$stage"
  ok "VF Network Node ${VERSION} 已就绪"
}

ensure_manager() {
  if manager_ready; then
    return 0
  fi
  local current
  current="$(installed_version)"
  if [[ -n "$current" ]]; then
    info "更新管理器：${current} → ${VERSION}"
  fi
  install_runtime_files
}

require_root

case "${1:-}" in
  -h|--help)
    cat <<'EOF'
P07 · VF Network Node

交互运行：安装/更新管理器后进入唯一主菜单。
非交互运行：安装/更新管理器后执行稳定节点安装。

可选：
  install      安装 / 修复节点
  status       查看节点状态
  url|share    显示分享链接
  backup       备份节点配置
  uninstall    卸载节点
EOF
    ;;
  install|status|url|share|backup|uninstall)
    cmd="$1"
    ensure_manager
    exec "$ENTRY" "$cmd"
    ;;
  menu|manage)
    ensure_manager
    exec "$ENTRY"
    ;;
  '')
    ensure_manager
    if [[ -t 0 && -t 1 ]]; then
      exec "$ENTRY"
    else
      exec "$ENTRY" install
    fi
    ;;
  *) fail "未知参数：$1"; exit 2 ;;
esac
