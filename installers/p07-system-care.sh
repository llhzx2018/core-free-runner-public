#!/usr/bin/env bash
set -Eeuo pipefail

VERSION='0.1.0-rc1'
PACKAGE_PATH="packages/p07-system-care/${VERSION}"
RAW_BASE="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/${PACKAGE_PATH}"
MANIFEST_BLOB='31c4a6cc55926783ea043b3ee548333413efc0a4'
TARGET='/opt/vf-system-care'
ENTRY='/usr/local/bin/vf-system-care'

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  R=$'\033[0m'; RED=$'\033[31m'; GREEN=$'\033[32m'; CYAN=$'\033[36m'
else
  R=''; RED=''; GREEN=''; CYAN=''
fi
say() { printf '%b\n' "$*"; }
ok() { say "${GREEN}完成${R}  $*"; }
info() { say "${CYAN}$*${R}"; }
fail() { say "${RED}FAIL${R}  $*" >&2; }

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    fail '请使用 root 运行。'
    exit 1
  fi
}

git_blob_sha1() {
  local file="$1" bytes
  bytes="$(wc -c < "$file" | tr -d '[:space:]')"
  { printf 'blob %s\0' "$bytes"; cat "$file"; } | sha1sum | awk '{print $1}'
}

write_entry() {
  rm -f "$ENTRY"
  cat > "$ENTRY" <<EOF
#!/usr/bin/env bash
exec "$TARGET/vf-system-care.sh" "\$@"
EOF
  chmod 0755 "$ENTRY"
}

installed_version() {
  if [[ -x "$ENTRY" ]]; then
    NO_COLOR=1 "$ENTRY" --version 2>/dev/null | awk '{print $NF}' || true
  fi
}

manager_ready() {
  [[ -x "$ENTRY" && -x "$TARGET/vf-system-care.sh" ]] || return 1
  [[ "$(installed_version)" == "$VERSION" ]] || return 1
  NO_COLOR=1 "$ENTRY" status >/dev/null 2>&1
}

install_runtime() {
  for cmd in curl sha1sum wc awk mktemp; do
    command -v "$cmd" >/dev/null 2>&1 || { fail "缺少必要命令：${cmd}"; return 2; }
  done

  local tmp stage manifest expected path actual
  tmp="$(mktemp -d /tmp/p07-system-care.XXXXXX)"
  stage="${TARGET}.new.$$"
  manifest="$tmp/MANIFEST.gitblob"
  mkdir -p "$tmp/pkg/lib" "$stage/lib"

  info "校验并安装 P07 系统维护 / 安全 ${VERSION}..."
  if ! curl -fsSL --proto '=https' --tlsv1.2 "${RAW_BASE}/MANIFEST.gitblob" -o "$manifest"; then
    rm -rf "$tmp" "$stage"
    fail '运行清单下载失败。'
    return 9
  fi
  actual="$(git_blob_sha1 "$manifest")"
  if [[ "$actual" != "$MANIFEST_BLOB" ]]; then
    rm -rf "$tmp" "$stage"
    fail '运行清单完整性校验失败。'
    return 10
  fi

  while read -r expected path; do
    [[ -n "$expected" && -n "$path" ]] || continue
    mkdir -p "$tmp/pkg/$(dirname "$path")"
    if ! curl -fsSL --proto '=https' --tlsv1.2 "${RAW_BASE}/${path}" -o "$tmp/pkg/$path"; then
      rm -rf "$tmp" "$stage"
      fail "运行文件下载失败：${path}"
      return 11
    fi
    actual="$(git_blob_sha1 "$tmp/pkg/$path")"
    if [[ "$actual" != "$expected" ]]; then
      rm -rf "$tmp" "$stage"
      fail "运行文件完整性校验失败：${path}"
      return 12
    fi
  done < "$manifest"

  cp -a "$tmp/pkg/." "$stage/"
  chmod 0755 "$stage/vf-system-care.sh" "$stage/status.sh" "$stage/audit.sh" "$stage/updates.sh" "$stage/cleanup.sh" "$stage/memory.sh" "$stage/services.sh" "$stage/security-audit.sh"
  chmod 0644 "$stage/VERSION" "$stage/lib/common.sh"

  if [[ -d "$TARGET" ]]; then
    rm -rf "${TARGET}.previous"
    mv "$TARGET" "${TARGET}.previous"
  fi
  mv "$stage" "$TARGET"
  write_entry

  if ! manager_ready; then
    fail 'System Care 管理器自检失败，正在回滚。'
    rm -rf "$TARGET"
    if [[ -d "${TARGET}.previous" ]]; then
      mv "${TARGET}.previous" "$TARGET"
      write_entry
    fi
    rm -rf "$tmp" "$stage"
    return 13
  fi

  rm -rf "${TARGET}.previous" "$tmp" "$stage"
  ok "System Care ${VERSION} 已就绪"
}

ensure_manager() {
  manager_ready && return 0
  local current
  current="$(installed_version)"
  [[ -n "$current" ]] && info "更新 System Care：${current} → ${VERSION}"
  install_runtime
}

require_root

case "${1:-}" in
  -h|--help)
    cat <<'HELP'
P07 · 系统维护 / 安全

此脚本仅供 P07 Toolbox 内部安装/更新模块使用。
普通用户继续使用唯一 P07 Toolbox 主入口。

Commands:
  menu
  status|check
  audit
  updates
  cleanup
  memory
  services
  security
HELP
    ;;
  status|check|audit|memory|services|security)
    cmd="$1"; ensure_manager; exec "$ENTRY" "$cmd"
    ;;
  updates|cleanup)
    cmd="$1"; shift; ensure_manager; exec "$ENTRY" "$cmd" "$@"
    ;;
  menu|manage)
    ensure_manager; exec "$ENTRY" menu
    ;;
  '')
    ensure_manager
    if [[ -t 0 && -t 1 ]]; then exec "$ENTRY" menu; else exec "$ENTRY" audit; fi
    ;;
  *) fail "未知参数：$1"; exit 2 ;;
esac
