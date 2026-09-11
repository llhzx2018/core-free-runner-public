#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"
BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"
PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"
RC3_URL="${PUBLIC_ROOT}/dist/p07/0.1.0-rc3/overlay"
BASE_PUBLIC_ROOT="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/3effb6a7554d8da33955df52f8707df71b13f204"
BASE_INSTALLER_URL="${BASE_PUBLIC_ROOT}/installers/p07-rc3-cloudpanel-complete.sh"
BASE_INSTALLER_BLOB="a98aa0a79d9ca3c5c5050e1505184c5b86208aa0"
EXPECTED_VERSION="VF Server Ops 0.1.0 RC3"
EXPECTED_BUILD_ID="0.1.0-rc3-guided-init11"
BUILD_BLOB="de0c6ef3893299c02257dd878a5c36b2d19cb2c8"
VERIFIED_BLOB="c0df2750e0cb79e16bf46cad88e85cacacfc2415"

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

verify_installed_init11() {
  [[ -x "$BIN_LINK" ]] || return 1
  [[ "$($BIN_LINK --version 2>/dev/null || true)" == "$EXPECTED_VERSION" ]] || return 1
  [[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "$EXPECTED_BUILD_ID" ]] || return 1
  [[ -f "$INSTALL_DIR/BUILD_ID" && -f "$INSTALL_DIR/lib/restore_as_verified.py" ]] || return 1
  verify_git_blob "$INSTALL_DIR/BUILD_ID" "$BUILD_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/restore_as_verified.py" "$VERIFIED_BLOB" >/dev/null 2>&1 || return 1
}

if verify_installed_init11; then
  say "Restore-As Real R1 guided-init11 已是当前版本 ✓"
  if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
  exit 0
fi

[[ ${EUID:-$(id -u)} -eq 0 || "${P07_ALLOW_NONROOT:-0}" == "1" ]] || fail "请使用 root 运行。"
TMP_DIR="$(mktemp -d -t p07-init11-install.XXXXXX)"
PRE_RUN_SNAPSHOT="$TMP_DIR/pre-run"
HAD_PRE_RUN=0
COMMITTED=0
if [[ -e "$INSTALL_DIR" ]]; then
  HAD_PRE_RUN=1
  cp -a "$INSTALL_DIR" "$PRE_RUN_SNAPSHOT"
fi

restore_pre_run() {
  say "guided-init11 未完成，正在恢复执行前版本..."
  rm -rf "$INSTALL_DIR" 2>/dev/null || true
  if [[ "$HAD_PRE_RUN" -eq 1 && -e "$PRE_RUN_SNAPSHOT" ]]; then
    mv "$PRE_RUN_SNAPSHOT" "$INSTALL_DIR"
    if [[ -f "$INSTALL_DIR/bin/vfops-user" ]]; then
      mkdir -p "$(dirname "$BIN_LINK")"
      ln -sfn "$INSTALL_DIR/bin/vfops-user" "$BIN_LINK"
    elif [[ -f "$INSTALL_DIR/bin/vfops" ]]; then
      mkdir -p "$(dirname "$BIN_LINK")"
      ln -sfn "$INSTALL_DIR/bin/vfops" "$BIN_LINK"
    fi
    say "已恢复执行前版本。"
  else
    rm -f "$BIN_LINK" 2>/dev/null || true
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

say "准备已验证 guided-init10 基线..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$BASE_INSTALLER_URL" -o "$TMP_DIR/base-installer.sh" || fail "guided-init10 基线安装器下载失败。"
bash -n "$TMP_DIR/base-installer.sh" || fail "guided-init10 基线安装器语法校验失败。"
verify_git_blob "$TMP_DIR/base-installer.sh" "$BASE_INSTALLER_BLOB" || fail "guided-init10 基线安装器身份校验失败。"
P07_PUBLIC_ROOT="$BASE_PUBLIC_ROOT" P07_NO_EXEC=1 P07_TOOLBOX_PARENT=1 bash "$TMP_DIR/base-installer.sh" || fail "guided-init10 基线安装失败。"
[[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "0.1.0-rc3-guided-init10" ]] || fail "guided-init10 基线安装后身份不匹配。"

fetch_overlay() {
  local rel="$1" blob="$2"
  mkdir -p "$TMP_DIR/new/$(dirname "$rel")"
  curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "${RC3_URL}/${rel}" -o "$TMP_DIR/new/$rel" || fail "guided-init11 文件下载失败：$rel"
  verify_git_blob "$TMP_DIR/new/$rel" "$blob" || fail "guided-init11 文件身份校验失败：$rel"
}

say "下载并校验 Restore-As Real R1 guided-init11..."
fetch_overlay "BUILD_ID" "$BUILD_BLOB"
fetch_overlay "lib/restore_as_verified.py" "$VERIFIED_BLOB"
python3 -m py_compile "$TMP_DIR/new/lib/restore_as_verified.py" || fail "guided-init11 Python 语法校验失败。"
for marker in '_database_compat_context' 'P07_CLOUDPANEL_OPERATION=' 'P07_CLOUDPANEL_EXIT=' 'os.chmod(path, 0o700)' 'os.chmod(target, 0o600)'; do
  grep -Fq "$marker" "$TMP_DIR/new/lib/restore_as_verified.py" || fail "guided-init11 缺少 Real R1 兼容标记：$marker"
done
if grep -Fq 'REAL_PASS' "$TMP_DIR/new/lib/restore_as_verified.py"; then
  fail "guided-init11 运行时不得自称 REAL_PASS。"
fi

say "升级 Restore-As Real R1 数据库兼容层..."
cp "$TMP_DIR/new/BUILD_ID" "$INSTALL_DIR/BUILD_ID"
cp "$TMP_DIR/new/lib/restore_as_verified.py" "$INSTALL_DIR/lib/restore_as_verified.py"
chmod 0644 "$INSTALL_DIR/BUILD_ID" "$INSTALL_DIR/lib/restore_as_verified.py"

if [[ "${P07_INIT11_TEST_FAIL:-0}" == "1" ]]; then
  fail "guided-init11 注入测试失败。"
fi
if ! verify_installed_init11; then
  fail "guided-init11 自检失败。"
fi

COMMITTED=1
say "Restore-As Real R1 guided-init11 安装完成 ✓"
printf '版本：%s\n' "$EXPECTED_VERSION"
printf 'Restore-As DB：使用 TARGET Site User 私有 staging（0700/0600）执行真实 CloudPanel import/export 验证。\n'
printf '失败诊断：仅输出 CloudPanel operation / exit code，不输出 SQL、密码或命令 stderr。\n'
printf '安全边界：不改 DNS、不删 SOURCE、不覆盖 existing TARGET。\n'
if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
