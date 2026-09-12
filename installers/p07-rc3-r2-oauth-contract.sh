#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"
PREVIOUS_DIR="${P07_PREVIOUS_DIR:-/opt/vf-server-ops.previous}"
BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"
PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"
RC3_URL="${PUBLIC_ROOT}/dist/p07/0.1.0-rc3/overlay"
BASE_PUBLIC_ROOT="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/aa4dbc32cdddd81a188d55714c050de6b28436f2"
BASE_INSTALLER_URL="${BASE_PUBLIC_ROOT}/installers/p07.sh"
BASE_INSTALLER_BLOB="d943858a9b664567952942a1a404f8d5fa62190c"
EXPECTED_VERSION="VF Server Ops 0.1.0 RC3"
EXPECTED_BUILD_ID="0.1.0-rc3-guided-init16"
BUILD_BLOB="622b752887d46c17a8a5d05046037a2dc6a35475"
STORAGE_SETUP_BLOB="b279677ae561f9feb689964bd8f09be98c9211c9"
GOOGLE_OAUTH_BLOB="3b023f307bf744650a351e19bde01b3597469992"
GOOGLE_TEST_BLOB="c72c938a5ed81b074c1ae8a3afbb0943df0aa683"
ONBOARDING_TEST_BLOB="59bf88d6b6a6493c536919ab67318513330d091f"

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

verify_installed_init16() {
  [[ -x "$BIN_LINK" ]] || return 1
  [[ "$($BIN_LINK --version 2>/dev/null || true)" == "$EXPECTED_VERSION" ]] || return 1
  [[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "$EXPECTED_BUILD_ID" ]] || return 1
  verify_git_blob "$INSTALL_DIR/BUILD_ID" "$BUILD_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/bin/vfops-storage-setup" "$STORAGE_SETUP_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/google_device_oauth.py" "$GOOGLE_OAUTH_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/tests/test_google_device_oauth.py" "$GOOGLE_TEST_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/tests/test_storage_onboarding_ux.py" "$ONBOARDING_TEST_BLOB" >/dev/null 2>&1 || return 1
}

if verify_installed_init16; then
  say "R2 Google + B2 guided-init16 已是当前版本 ✓"
  if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
  exit 0
fi

[[ ${EUID:-$(id -u)} -eq 0 || "${P07_ALLOW_NONROOT:-0}" == "1" ]] || fail "请使用 root 运行。"
TMP_DIR="$(mktemp -d -t p07-init16-install.XXXXXX)"
PRE_RUN_INSTALL="$TMP_DIR/pre-run-install"
PRE_RUN_PREVIOUS="$TMP_DIR/pre-run-previous"
HAD_INSTALL=0
HAD_PREVIOUS=0
COMMITTED=0
if [[ -e "$INSTALL_DIR" ]]; then HAD_INSTALL=1; cp -a "$INSTALL_DIR" "$PRE_RUN_INSTALL"; fi
if [[ -e "$PREVIOUS_DIR" ]]; then HAD_PREVIOUS=1; cp -a "$PREVIOUS_DIR" "$PRE_RUN_PREVIOUS"; fi

restore_pre_run() {
  say "guided-init16 未完成，正在恢复执行前版本..."
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

say "准备已验证 guided-init15 基线..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$BASE_INSTALLER_URL" -o "$TMP_DIR/base-installer.sh" || fail "guided-init15 基线安装器下载失败。"
bash -n "$TMP_DIR/base-installer.sh" || fail "guided-init15 基线安装器语法校验失败。"
verify_git_blob "$TMP_DIR/base-installer.sh" "$BASE_INSTALLER_BLOB" || fail "guided-init15 基线安装器身份校验失败。"
P07_PUBLIC_ROOT="$BASE_PUBLIC_ROOT" P07_NO_EXEC=1 P07_TOOLBOX_PARENT=1 P07_PREVIOUS_DIR="$PREVIOUS_DIR" P07_INSTALL_DIR="$INSTALL_DIR" P07_BIN_LINK="$BIN_LINK" bash "$TMP_DIR/base-installer.sh" || fail "guided-init15 基线安装失败。"
[[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "0.1.0-rc3-guided-init15" ]] || fail "guided-init15 基线安装后身份不匹配。"

fetch_overlay() {
  local rel="$1" blob="$2"
  mkdir -p "$TMP_DIR/new/$(dirname "$rel")"
  curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "${RC3_URL}/${rel}" -o "$TMP_DIR/new/$rel" || fail "guided-init16 文件下载失败：$rel"
  verify_git_blob "$TMP_DIR/new/$rel" "$blob" || fail "guided-init16 文件身份校验失败：$rel"
}

say "下载并校验 R2 Google OAuth guided-init16..."
fetch_overlay "BUILD_ID" "$BUILD_BLOB"
fetch_overlay "bin/vfops-storage-setup" "$STORAGE_SETUP_BLOB"
fetch_overlay "lib/google_device_oauth.py" "$GOOGLE_OAUTH_BLOB"
fetch_overlay "tests/test_google_device_oauth.py" "$GOOGLE_TEST_BLOB"
fetch_overlay "tests/test_storage_onboarding_ux.py" "$ONBOARDING_TEST_BLOB"

bash -n "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init16 storage setup 语法校验失败。"
python3 -m py_compile "$TMP_DIR/new/lib/google_device_oauth.py" "$TMP_DIR/new/tests/test_google_device_oauth.py" "$TMP_DIR/new/tests/test_storage_onboarding_ux.py" || fail "guided-init16 Python 语法校验失败。"
grep -Fq 'Google：OAuth Client ID + Client Secret' "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init16 Google 准备清单缺失。"
grep -Fq 'OAuth Client Secret（输入不回显）' "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init16 Google Secret 隐藏输入缺失。"
grep -Fq 'Recovery Key：P07 自动生成，无需提前准备' "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init16 Recovery Key 自动生成 UX 缺失。"
grep -Fq '"client_secret": client_secret' "$TMP_DIR/new/lib/google_device_oauth.py" || fail "guided-init16 token polling 未携带 client_secret。"
! grep -Fq -- '--client-secret' "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init16 禁止把 Google Secret 放在 argv。"
! grep -Fq 'Recovery Key（输入不回显）' "$TMP_DIR/new/bin/vfops-storage-setup" || fail "guided-init16 不应要求手工生成 Recovery Key。"

say "升级 R2 Google + B2 初始化..."
mkdir -p "$INSTALL_DIR/tests"
cp "$TMP_DIR/new/BUILD_ID" "$INSTALL_DIR/BUILD_ID"
cp "$TMP_DIR/new/bin/vfops-storage-setup" "$INSTALL_DIR/bin/vfops-storage-setup"
cp "$TMP_DIR/new/lib/google_device_oauth.py" "$INSTALL_DIR/lib/google_device_oauth.py"
cp "$TMP_DIR/new/tests/test_google_device_oauth.py" "$INSTALL_DIR/tests/test_google_device_oauth.py"
cp "$TMP_DIR/new/tests/test_storage_onboarding_ux.py" "$INSTALL_DIR/tests/test_storage_onboarding_ux.py"
chmod 0644 "$INSTALL_DIR/BUILD_ID" "$INSTALL_DIR/lib/google_device_oauth.py" "$INSTALL_DIR/tests/test_google_device_oauth.py" "$INSTALL_DIR/tests/test_storage_onboarding_ux.py"
chmod 0755 "$INSTALL_DIR/bin/vfops-storage-setup"

if [[ "${P07_INIT16_TEST_FAIL:-0}" == "1" ]]; then fail "guided-init16 注入测试失败。"; fi
if ! verify_installed_init16; then fail "guided-init16 自检失败。"; fi
(
  cd "$INSTALL_DIR"
  python3 tests/test_google_device_oauth.py
  python3 tests/test_storage_onboarding_ux.py
) >/dev/null || fail "guided-init16 onboarding 测试失败。"

COMMITTED=1
say "R2 Google + B2 guided-init16 安装完成 ✓"
printf '版本：%s\n' "$EXPECTED_VERSION"
printf '首次准备：Google Client ID + Client Secret；B2 Bucket + Key ID + Application Key。\n'
printf 'Google Secret：隐藏输入，经 stdin 使用；不放 argv、不回显。\n'
printf 'Recovery Key：P07 自动生成，仅在 Google + B2 + crypt 全部健康后显示一次。\n'
printf '安全边界：失败自动回滚；不改 DNS、不删 SOURCE；R2 未通过前不自动启用 Scheduler。\n'
if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
