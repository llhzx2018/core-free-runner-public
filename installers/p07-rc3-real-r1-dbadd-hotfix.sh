#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"
PREVIOUS_DIR="${P07_PREVIOUS_DIR:-/opt/vf-server-ops.previous}"
BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"
PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"
RC3_URL="${PUBLIC_ROOT}/dist/p07/0.1.0-rc3/overlay"
BASE_PUBLIC_ROOT="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/323c10d28c56fc9a4bf327efae998b8d973116ef"
BASE_INSTALLER_URL="${BASE_PUBLIC_ROOT}/installers/p07.sh"
BASE_INSTALLER_BLOB="843fece49262dd030462273d0b188bdab75d8234"
EXPECTED_VERSION="VF Server Ops 0.1.0 RC3"
EXPECTED_BUILD_ID="0.1.0-rc3-guided-init12"
BUILD_BLOB="0124420981d74b7db119f557d1c39fc1ec79dd6c"
SITE_LIFECYCLE_BLOB="3e84dfa74b4df8413c3228322b8dc1c22d901761"

say() { printf '\n[P07] %s\n' "$*"; }
fail() { printf '\n[P07] ERROR: %s\n' "$*" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || fail "缺少依赖：curl"
command -v python3 >/dev/null 2>&1 || fail "缺少依赖：python3"

verify_git_blob() {
  local file="$1" expected="$2"
  python3 - "$file" "$expected" <<'PY'
import hashlib,sys
p,expected=sys.argv[1:]
data=open(p,'rb').read()
actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
if actual != expected:
    print(f'blob mismatch: {p}: {actual} != {expected}', file=sys.stderr)
    raise SystemExit(1)
PY
}

verify_installed_init12() {
  [[ -x "$BIN_LINK" ]] || return 1
  [[ "$($BIN_LINK --version 2>/dev/null || true)" == "$EXPECTED_VERSION" ]] || return 1
  [[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "$EXPECTED_BUILD_ID" ]] || return 1
  [[ -f "$INSTALL_DIR/BUILD_ID" && -f "$INSTALL_DIR/lib/site_lifecycle.py" ]] || return 1
  verify_git_blob "$INSTALL_DIR/BUILD_ID" "$BUILD_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/site_lifecycle.py" "$SITE_LIFECYCLE_BLOB" >/dev/null 2>&1 || return 1
}

if verify_installed_init12; then
  say "Restore-As Real R1 guided-init12 已是当前版本 ✓"
  if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
  exit 0
fi

[[ ${EUID:-$(id -u)} -eq 0 || "${P07_ALLOW_NONROOT:-0}" == "1" ]] || fail "请使用 root 运行。"
TMP_DIR="$(mktemp -d -t p07-init12-install.XXXXXX)"
PRE_RUN_INSTALL="$TMP_DIR/pre-run-install"
PRE_RUN_PREVIOUS="$TMP_DIR/pre-run-previous"
HAD_INSTALL=0
HAD_PREVIOUS=0
COMMITTED=0
if [[ -e "$INSTALL_DIR" ]]; then
  HAD_INSTALL=1
  cp -a "$INSTALL_DIR" "$PRE_RUN_INSTALL"
fi
if [[ -e "$PREVIOUS_DIR" ]]; then
  HAD_PREVIOUS=1
  cp -a "$PREVIOUS_DIR" "$PRE_RUN_PREVIOUS"
fi

restore_pre_run() {
  say "guided-init12 未完成，正在恢复执行前版本..."
  rm -rf "$INSTALL_DIR" "$PREVIOUS_DIR" 2>/dev/null || true
  if [[ "$HAD_INSTALL" -eq 1 && -e "$PRE_RUN_INSTALL" ]]; then
    mv "$PRE_RUN_INSTALL" "$INSTALL_DIR"
    if [[ -f "$INSTALL_DIR/bin/vfops-user" ]]; then
      mkdir -p "$(dirname "$BIN_LINK")"
      ln -sfn "$INSTALL_DIR/bin/vfops-user" "$BIN_LINK"
    elif [[ -f "$INSTALL_DIR/bin/vfops" ]]; then
      mkdir -p "$(dirname "$BIN_LINK")"
      ln -sfn "$INSTALL_DIR/bin/vfops" "$BIN_LINK"
    fi
  else
    rm -f "$BIN_LINK" 2>/dev/null || true
  fi
  if [[ "$HAD_PREVIOUS" -eq 1 && -e "$PRE_RUN_PREVIOUS" ]]; then
    mv "$PRE_RUN_PREVIOUS" "$PREVIOUS_DIR"
  fi
  if [[ "$HAD_INSTALL" -eq 1 ]]; then
    say "已恢复执行前版本。"
  else
    say "执行前没有 P07，已清理未完成的新安装。"
  fi
}

finish() {
  local rc=$?
  trap - EXIT
  if [[ "$rc" -ne 0 && "$COMMITTED" -eq 0 ]]; then
    restore_pre_run
  fi
  rm -rf "$TMP_DIR" 2>/dev/null || true
  exit "$rc"
}
trap finish EXIT

say "准备已验证 guided-init11 基线..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$BASE_INSTALLER_URL" -o "$TMP_DIR/base-installer.sh" || fail "guided-init11 基线安装器下载失败。"
bash -n "$TMP_DIR/base-installer.sh" || fail "guided-init11 基线安装器语法校验失败。"
verify_git_blob "$TMP_DIR/base-installer.sh" "$BASE_INSTALLER_BLOB" || fail "guided-init11 基线安装器身份校验失败。"
P07_PUBLIC_ROOT="$BASE_PUBLIC_ROOT" P07_NO_EXEC=1 P07_TOOLBOX_PARENT=1 P07_PREVIOUS_DIR="$PREVIOUS_DIR" bash "$TMP_DIR/base-installer.sh" || fail "guided-init11 基线安装失败。"
[[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "0.1.0-rc3-guided-init11" ]] || fail "guided-init11 基线安装后身份不匹配。"

fetch_overlay() {
  local rel="$1" blob="$2"
  mkdir -p "$TMP_DIR/new/$(dirname "$rel")"
  curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "${RC3_URL}/${rel}" -o "$TMP_DIR/new/$rel" || fail "guided-init12 文件下载失败：$rel"
  verify_git_blob "$TMP_DIR/new/$rel" "$blob" || fail "guided-init12 文件身份校验失败：$rel"
}

say "下载并校验 Restore-As Real R1 db:add guided-init12..."
fetch_overlay "BUILD_ID" "$BUILD_BLOB"
fetch_overlay "lib/site_lifecycle.py" "$SITE_LIFECYCLE_BLOB"
python3 -m py_compile "$TMP_DIR/new/lib/site_lifecycle.py" || fail "guided-init12 Python 语法校验失败。"
grep -Fq 'database = cloudpanel.validate_name(f"p07{token}{index}"' "$TMP_DIR/new/lib/site_lifecycle.py" || fail "guided-init12 database identity 规则缺失。"
grep -Fq 'username = cloudpanel.validate_name(f"p07u{token[:8]}{index}"' "$TMP_DIR/new/lib/site_lifecycle.py" || fail "guided-init12 database user identity 规则缺失。"
if grep -Fq 'p07_{token}' "$TMP_DIR/new/lib/site_lifecycle.py" || grep -Fq 'p07u_{token' "$TMP_DIR/new/lib/site_lifecycle.py"; then
  fail "guided-init12 仍包含 CloudPanel 不兼容的下划线数据库 identity。"
fi

say "升级 Restore-As Real R1 db:add 兼容层..."
cp "$TMP_DIR/new/BUILD_ID" "$INSTALL_DIR/BUILD_ID"
cp "$TMP_DIR/new/lib/site_lifecycle.py" "$INSTALL_DIR/lib/site_lifecycle.py"
chmod 0644 "$INSTALL_DIR/BUILD_ID" "$INSTALL_DIR/lib/site_lifecycle.py"

if [[ "${P07_INIT12_TEST_FAIL:-0}" == "1" ]]; then
  fail "guided-init12 注入测试失败。"
fi
if ! verify_installed_init12; then
  fail "guided-init12 自检失败。"
fi

COMMITTED=1
say "Restore-As Real R1 guided-init12 安装完成 ✓"
printf '版本：%s\n' "$EXPECTED_VERSION"
printf 'Restore-As DB identity：数据库名 / 用户名使用纯字母数字短名，兼容 CloudPanel db:add。\n'
printf '保留 init11：TARGET Site User 私有 staging + CloudPanel operation / exit code 诊断。\n'
printf '安全边界：不改 DNS、不删 SOURCE、不覆盖 existing TARGET。\n'
if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
