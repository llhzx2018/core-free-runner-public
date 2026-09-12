#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"
PREVIOUS_DIR="${P07_PREVIOUS_DIR:-/opt/vf-server-ops.previous}"
BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"
PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"
RC3_URL="${PUBLIC_ROOT}/dist/p07/0.1.0-rc3/overlay"
BASE_PUBLIC_ROOT="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/ad5acb910262777e003cb4a9efaece667ba0e7e2"
BASE_INSTALLER_URL="${BASE_PUBLIC_ROOT}/installers/p07.sh"
BASE_INSTALLER_BLOB="2aecf4474fe8ca694269daf305e74c6f550a3382"
EXPECTED_VERSION="VF Server Ops 0.1.0 RC3"
EXPECTED_BUILD_ID="0.1.0-rc3-guided-init15"
BUILD_BLOB="392173a22e56e4764c95332b75d28886dac76bd2"
STORAGE_SETUP_BLOB="966bb88b4b5cee26c810c18c6aa55e6e79beee40"
GOOGLE_OAUTH_BLOB="ce79cfd7cc9a8a9dcbad8d33566f8f4ac915db30"
GOOGLE_TEST_BLOB="5a1397008b47905616c302045d6a84a66b314429"
ONBOARDING_TEST_BLOB="9aba22b71d26e5e778c292b4fb659bbbbe234bee"

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

verify_installed_init15() {
  [[ -x "$BIN_LINK" ]] || return 1
  [[ "$($BIN_LINK --version 2>/dev/null || true)" == "$EXPECTED_VERSION" ]] || return 1
  [[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "$EXPECTED_BUILD_ID" ]] || return 1
  verify_git_blob "$INSTALL_DIR/BUILD_ID" "$BUILD_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/bin/vfops-storage-setup" "$STORAGE_SETUP_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/google_device_oauth.py" "$GOOGLE_OAUTH_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/tests/test_google_device_oauth.py" "$GOOGLE_TEST_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/tests/test_storage_onboarding_ux.py" "$ONBOARDING_TEST_BLOB" >/dev/null 2>&1 || return 1
}

if verify_installed_init15; then
  say "R2 一键远程初始化 guided-init15 已是当前版本 ✓"
  if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
  exit 0
fi

[[ ${EUID:-$(id -u)} -eq 0 || "${P07_ALLOW_NONROOT:-0}" == "1" ]] || fail "请使用 root 运行。"
TMP_DIR="$(mktemp -d -t p07-init15-install.XXXXXX)"
PRE_RUN_INSTALL="$TMP_DIR/pre-run-install"
PRE_RUN_PREVIOUS="$TMP_DIR/pre-run-previous"
HAD_INSTALL=0
HAD_PREVIOUS=0
COMMITTED=0
if [[ -e "$INSTALL_DIR" ]]; then HAD_INSTALL=1; cp -a "$INSTALL_DIR" "$PRE_RUN_INSTALL"; fi
if [[ -e "$PREVIOUS_DIR" ]]; then HAD_PREVIOUS=1; cp -a "$PREVIOUS_DIR" "$PRE_RUN_PREVIOUS"; fi

restore_pre_run() {
  say "guided-init15 未完成，正在恢复执行前版本..."
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
  if [[ "$HAD_PREVIOUS" -eq 1 && -e "$PRE_RUN_PREVIOUS" ]]; then mv "$PRE_RUN_PREVIOUS" "$PREVIOUS_DIR"; fi
  if [[ "$HAD_INSTALL" -eq 1 ]]; then say "已恢复执行前版本。"; else say "执行前没有 P07，已清理未完成的新安装。"; fi
}

finish() {
  local rc=$?
  trap - EXIT
  if [[ "$rc" -ne 0 && "$COMMITTED" -eq 0 ]]; then restore_pre_run; fi
  rm -rf "$TMP_DIR" 2>/dev/null || true
  exit "$rc"
}
trap finish EXIT

say "准备已验证 guided-init14 基线..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$BASE_INSTALLER_URL" -o "$TMP_DIR/base-installer.sh" || fail "guided-init14 基线安装器下载失败。"
bash -n "$TMP_DIR/base-installer.sh" || fail "guided-init14 基线安装器语法校验失败。"
verify_git_blob "$TMP_DIR/base-installer.sh" "$BASE_INSTALLER_BLOB" || fail "guided-init14 基线安装器身份校验失败。"
P07_PUBLIC_ROOT="$BASE_PUBLIC_ROOT" P07_NO_EXEC=1 P07_TOOLBOX_PARENT=1 P07_PREVIOUS_DIR="$PREVIOUS_DIR" P07_INSTALL_DIR="$INSTALL_DIR" P07_BIN_LINK="$BIN_LINK" bash "$TMP_DIR/base-installer.sh" || fail "guided-init14 基线安装失败。"
[[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "0.1.0-rc3-guided-init14" ]] || fail "guided-init14 基线安装后身份不匹配。"

fetch_overlay() {
  local rel="$1" blob="$2"
  mkdir -p "$TMP_DIR/new/$(dirname "$rel")"
  curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "${RC3_URL}/${rel}" -o "$TMP_DIR/new/$rel" || fail "guided-init15 文件下载失败：$rel"
  verify_git_blob "$TMP_DIR/new/$rel" "$blob" || fail "guided-init15 文件身份校验失败：$rel"
}

say "下载并校验 R2 一键远程初始化 guided-init15..."
fetch_overlay "BUILD_ID" "$BUILD_BLOB"
fetch_overlay "bin/vfops-storage-setup" "$STORAGE_SETUP_BLOB"
fetch_overlay "lib/google_device_oauth.py" "$GOOGLE_OAUTH_BLOB"
fetch_overlay "tests/test_google_device_oauth.py" "$GOOGLE_TEST_BLOB"
fetch_overlay "tests/test_storage_onboarding_ux.py" "$ONBOARDING_TEST_BLOB"

bash -n "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init15 storage setup 语法校验失败。"
python3 -m py_compile "$TMP_DIR/new/lib/google_device_oauth.py" "$TMP_DIR/new/tests/test_google_device_oauth.py" "$TMP_DIR/new/tests/test_storage_onboarding_ux.py" || fail "guided-init15 Python 语法校验失败。"
grep -Fq 'Recovery Key：P07 自动生成，无需提前准备' "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init15 Recovery Key 自动生成 UX 缺失。"
grep -Fq '已准备好，一键初始化 Google + B2' "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init15 一键初始化入口缺失。"
grep -Fq '查看准备教程' "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init15 准备教程入口缺失。"
! grep -Fq 'Recovery Key（输入不回显）' "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init15 仍要求用户手工输入 Recovery Key。"
! grep -Fq 'Client Secret（输入不回显）' "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init15 仍要求 Google Client Secret。"
! grep -Fq '"client_secret": client_secret' "$TMP_DIR/new/lib/google_device_oauth.py" || fail "guided-init15 Device OAuth 仍发送 client_secret。"

say "升级 R2 一键远程初始化..."
cp "$TMP_DIR/new/BUILD_ID" "$INSTALL_DIR/BUILD_ID"
cp "$TMP_DIR/new/bin/vfops-storage-setup" "$INSTALL_DIR/bin/vfops-storage-setup"
cp "$TMP_DIR/new/lib/google_device_oauth.py" "$INSTALL_DIR/lib/google_device_oauth.py"
cp "$TMP_DIR/new/tests/test_google_device_oauth.py" "$INSTALL_DIR/tests/test_google_device_oauth.py"
cp "$TMP_DIR/new/tests/test_storage_onboarding_ux.py" "$INSTALL_DIR/tests/test_storage_onboarding_ux.py"
chmod 0644 "$INSTALL_DIR/BUILD_ID" "$INSTALL_DIR/lib/google_device_oauth.py" "$INSTALL_DIR/tests/test_google_device_oauth.py" "$INSTALL_DIR/tests/test_storage_onboarding_ux.py"
chmod 0755 "$INSTALL_DIR/bin/vfops-storage-setup"

if [[ "${P07_INIT15_TEST_FAIL:-0}" == "1" ]]; then fail "guided-init15 注入测试失败。"; fi
if ! verify_installed_init15; then fail "guided-init15 自检失败。"; fi
(
  cd "$INSTALL_DIR"
  python3 tests/test_google_device_oauth.py
  python3 tests/test_storage_onboarding_ux.py
) >/dev/null || fail "guided-init15 onboarding 测试失败。"

COMMITTED=1
say "R2 一键远程初始化 guided-init15 安装完成 ✓"
printf '版本：%s\n' "$EXPECTED_VERSION"
printf '首次准备：先显示 Google / B2 教程，不再半路要求未知材料。\n'
printf 'Google：Device OAuth 只需 Client ID；浏览器完成一次官方授权。\n'
printf 'Recovery Key：P07 自动生成，仅在 Google + B2 + crypt 全部健康后显示一次，请保存到 VPS 外。\n'
printf 'B2：只需 Bucket + Application Key ID + Application Key。\n'
printf '安全边界：失败自动回滚；不改 DNS、不删 SOURCE；R2 未通过前不自动启用 Scheduler。\n'
if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
