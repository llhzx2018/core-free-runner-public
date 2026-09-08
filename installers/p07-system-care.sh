#!/usr/bin/env bash
set -Eeuo pipefail

VERSION='0.1.0-rc10'
BASE_VERSION='0.1.0-rc9'
BASE_PACKAGE_PATH="packages/p07-system-care/${BASE_VERSION}"
OVERLAY_PACKAGE_PATH="packages/p07-system-care/${VERSION}"
BASE_RAW="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/${BASE_PACKAGE_PATH}"
OVERLAY_RAW="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/${OVERLAY_PACKAGE_PATH}"
BASE_MANIFEST_BLOB='a6f75e96cf9b6971b6a431309f72f629ef6ed931'
OVERLAY_MANIFEST_BLOB='22da2481a09f3048fda79e3088ac4d021b000dd9'
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
  [[ -x "$ENTRY" && -x "$TARGET/vf-system-care.sh" && -x "$TARGET/status.sh" && -x "$TARGET/intrusion-evidence.sh" && -f "$TARGET/lib/intrusion_evidence.py" && -f "$TARGET/lib/intrusion_scan.py" && -f "$TARGET/lib/intrusion_scan_rc9.py" ]] || return 1
  [[ "$(installed_version)" == "$VERSION" ]] || return 1
  NO_COLOR=1 bash "$TARGET/status.sh" quick >/dev/null 2>&1
}

fetch_manifest_files() {
  local raw="$1" manifest="$2" out="$3" expected path actual
  while read -r expected path; do
    [[ -n "$expected" && -n "$path" ]] || continue
    mkdir -p "$out/$(dirname "$path")"
    if ! curl -fsSL --proto '=https' --tlsv1.2 "${raw}/${path}" -o "$out/$path"; then
      fail "运行文件下载失败：${path}"
      return 11
    fi
    actual="$(git_blob_sha1 "$out/$path")"
    if [[ "$actual" != "$expected" ]]; then
      fail "运行文件完整性校验失败：${path}"
      return 12
    fi
  done < "$manifest"
}

install_runtime() {
  local dep
  for dep in curl sha1sum wc awk mktemp dirname cp chmod mv rm python3; do
    command -v "$dep" >/dev/null 2>&1 || { fail "缺少必要命令：${dep}"; return 2; }
  done

  local tmp stage base_manifest overlay_manifest actual
  tmp="$(mktemp -d /tmp/p07-system-care.XXXXXX)"
  stage="${TARGET}.new.$$"
  base_manifest="$tmp/BASE_MANIFEST.gitblob"
  overlay_manifest="$tmp/OVERLAY_MANIFEST.gitblob"
  mkdir -p "$tmp/base/lib" "$tmp/overlay/lib" "$stage/lib"

  info "校验并安装 P07 系统维护 / 安全 ${VERSION}..."

  if ! curl -fsSL --proto '=https' --tlsv1.2 "${BASE_RAW}/MANIFEST.gitblob" -o "$base_manifest"; then
    rm -rf "$tmp" "$stage"; fail '基础运行清单下载失败。'; return 9
  fi
  actual="$(git_blob_sha1 "$base_manifest")"
  if [[ "$actual" != "$BASE_MANIFEST_BLOB" ]]; then
    rm -rf "$tmp" "$stage"; fail '基础运行清单完整性校验失败。'; return 10
  fi

  if ! curl -fsSL --proto '=https' --tlsv1.2 "${OVERLAY_RAW}/MANIFEST.gitblob" -o "$overlay_manifest"; then
    rm -rf "$tmp" "$stage"; fail 'RC10 修复清单下载失败。'; return 14
  fi
  actual="$(git_blob_sha1 "$overlay_manifest")"
  if [[ "$actual" != "$OVERLAY_MANIFEST_BLOB" ]]; then
    rm -rf "$tmp" "$stage"; fail 'RC10 修复清单完整性校验失败。'; return 15
  fi

  fetch_manifest_files "$BASE_RAW" "$base_manifest" "$tmp/base" || {
    local rc=$?; rm -rf "$tmp" "$stage"; return "$rc"
  }
  fetch_manifest_files "$OVERLAY_RAW" "$overlay_manifest" "$tmp/overlay" || {
    local rc=$?; rm -rf "$tmp" "$stage"; return "$rc"
  }

  cp -a "$tmp/base/." "$stage/"
  mv "$stage/lib/intrusion_scan.py" "$stage/lib/intrusion_scan_rc9.py"
  cp -a "$tmp/overlay/." "$stage/"

  chmod 0755 "$stage/vf-system-care.sh" "$stage/status.sh" "$stage/audit.sh" "$stage/updates.sh" "$stage/cleanup.sh" "$stage/memory.sh" "$stage/services.sh" "$stage/security-audit.sh" "$stage/intrusion-evidence.sh"
  chmod 0644 "$stage/VERSION" "$stage/lib/common.sh" "$stage/lib/intrusion_evidence.py" "$stage/lib/intrusion_logs.py" "$stage/lib/intrusion_scan.py" "$stage/lib/intrusion_scan_rc9.py" "$stage/lib/intrusion_state.py"

  if ! PYTHONPATH="$stage/lib" python3 - <<'PY'
import intrusion_scan
assert intrusion_scan.__name__ == "intrusion_scan"
assert callable(intrusion_scan.discover)
assert callable(intrusion_scan._cloudpanel_user_bounded_roots)
PY
  then
    rm -rf "$tmp" "$stage"
    fail 'RC10 WordPress 站点发现模块自检失败。'
    return 16
  fi

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

  NO_COLOR=1 "$ENTRY" evidence refresh-cache >/dev/null 2>&1 || true
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
