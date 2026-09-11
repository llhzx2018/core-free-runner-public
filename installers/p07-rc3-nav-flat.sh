#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"
PREVIOUS_DIR="${P07_PREVIOUS_DIR:-/opt/vf-server-ops.previous}"
BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"
PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"
RC3_URL="${PUBLIC_ROOT}/dist/p07/0.1.0-rc3/overlay"
BASE_PUBLIC_ROOT="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/8ed82495a80f2b11a2d47dc8f33648d87e291da5"
BASE_INSTALLER_URL="${BASE_PUBLIC_ROOT}/installers/p07.sh"
BASE_INSTALLER_BLOB="a16e4889128bdc2575b8f5e174e332e7a5b76700"
EXPECTED_VERSION="VF Server Ops 0.1.0 RC3"
EXPECTED_BUILD_ID="0.1.0-rc3-guided-init13"
BUILD_BLOB="2d34fdf9e3fc99310e7ff2d56396c422f72593b9"
USER_UI_BLOB="1028b939ecd4c52377c846ab8e12ff136667981c"
CLOUDPANEL_UI_BLOB="378412db5abba18dd6bc8f6f7125fa1098d765d8"
COMMON_UI_BLOB="b591cd9b7e1ab9e715cf60cd702fee44f448e7ff"

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

verify_installed_init13() {
  [[ -x "$BIN_LINK" ]] || return 1
  [[ "$($BIN_LINK --version 2>/dev/null || true)" == "$EXPECTED_VERSION" ]] || return 1
  [[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "$EXPECTED_BUILD_ID" ]] || return 1
  [[ -f "$INSTALL_DIR/BUILD_ID" ]] || return 1
  verify_git_blob "$INSTALL_DIR/BUILD_ID" "$BUILD_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/bin/vfops-user" "$USER_UI_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/bin/vfops-cloudpanel-ui" "$CLOUDPANEL_UI_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/cloudpanel_ui_common.sh" "$COMMON_UI_BLOB" >/dev/null 2>&1 || return 1
}

if verify_installed_init13; then
  say "CloudPanel 导航 guided-init13 已是当前版本 ✓"
  if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
  exit 0
fi

[[ ${EUID:-$(id -u)} -eq 0 || "${P07_ALLOW_NONROOT:-0}" == "1" ]] || fail "请使用 root 运行。"
TMP_DIR="$(mktemp -d -t p07-init13-install.XXXXXX)"
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
  say "guided-init13 未完成，正在恢复执行前版本..."
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

say "准备已验证 guided-init12 基线..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$BASE_INSTALLER_URL" -o "$TMP_DIR/base-installer.sh" || fail "guided-init12 基线安装器下载失败。"
bash -n "$TMP_DIR/base-installer.sh" || fail "guided-init12 基线安装器语法校验失败。"
verify_git_blob "$TMP_DIR/base-installer.sh" "$BASE_INSTALLER_BLOB" || fail "guided-init12 基线安装器身份校验失败。"
P07_PUBLIC_ROOT="$BASE_PUBLIC_ROOT" P07_NO_EXEC=1 P07_TOOLBOX_PARENT=1 P07_PREVIOUS_DIR="$PREVIOUS_DIR" bash "$TMP_DIR/base-installer.sh" || fail "guided-init12 基线安装失败。"
[[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "0.1.0-rc3-guided-init12" ]] || fail "guided-init12 基线安装后身份不匹配。"

fetch_overlay() {
  local rel="$1" blob="$2"
  mkdir -p "$TMP_DIR/new/$(dirname "$rel")"
  curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "${RC3_URL}/${rel}" -o "$TMP_DIR/new/$rel" || fail "guided-init13 文件下载失败：$rel"
  verify_git_blob "$TMP_DIR/new/$rel" "$blob" || fail "guided-init13 文件身份校验失败：$rel"
}

say "下载并校验 CloudPanel 导航 guided-init13..."
fetch_overlay "BUILD_ID" "$BUILD_BLOB"
fetch_overlay "bin/vfops-user" "$USER_UI_BLOB"
fetch_overlay "bin/vfops-cloudpanel-ui" "$CLOUDPANEL_UI_BLOB"
fetch_overlay "lib/cloudpanel_ui_common.sh" "$COMMON_UI_BLOB"
bash -n "$TMP_DIR/new/bin/vfops-user" || fail "guided-init13 Slot3 菜单语法校验失败。"
bash -n "$TMP_DIR/new/bin/vfops-cloudpanel-ui" || fail "guided-init13 CloudPanel UI 语法校验失败。"
bash -n "$TMP_DIR/new/lib/cloudpanel_ui_common.sh" || fail "guided-init13 common UI 语法校验失败。"
grep -Fq '6. 网站管理' "$TMP_DIR/new/bin/vfops-user" || fail "guided-init13 网站管理入口缺失。"
grep -Fq '7. CloudPanel 管理' "$TMP_DIR/new/bin/vfops-user" || fail "guided-init13 CloudPanel 管理入口缺失。"
grep -Fq '98. 更换网站' "$TMP_DIR/new/bin/vfops-cloudpanel-ui" || fail "guided-init13 更换网站入口缺失。"
grep -Fq '0. 返回 P07 主菜单' "$TMP_DIR/new/bin/vfops-cloudpanel-ui" || fail "guided-init13 直接返回入口缺失。"
grep -Fq '网站只选择一次' "$TMP_DIR/new/bin/vfops-cloudpanel-ui" || fail "guided-init13 持久选站 UX 缺失。"
grep -Fq 'SELECTED_DOMAIN=""' "$TMP_DIR/new/lib/cloudpanel_ui_common.sh" || fail "guided-init13 持久选站状态缺失。"
for forbidden in 'site:delete' 'db:delete' 'user:delete' 'REAL_PASS'; do
  ! grep -Fq "$forbidden" "$TMP_DIR/new/bin/vfops-cloudpanel-ui" || fail "guided-init13 包含禁止普通入口：$forbidden"
done

say "升级 CloudPanel 导航..."
cp "$TMP_DIR/new/BUILD_ID" "$INSTALL_DIR/BUILD_ID"
cp "$TMP_DIR/new/bin/vfops-user" "$INSTALL_DIR/bin/vfops-user"
cp "$TMP_DIR/new/bin/vfops-cloudpanel-ui" "$INSTALL_DIR/bin/vfops-cloudpanel-ui"
cp "$TMP_DIR/new/lib/cloudpanel_ui_common.sh" "$INSTALL_DIR/lib/cloudpanel_ui_common.sh"
chmod 0644 "$INSTALL_DIR/BUILD_ID" "$INSTALL_DIR/lib/cloudpanel_ui_common.sh"
chmod 0755 "$INSTALL_DIR/bin/vfops-user" "$INSTALL_DIR/bin/vfops-cloudpanel-ui"

if [[ "${P07_INIT13_TEST_FAIL:-0}" == "1" ]]; then fail "guided-init13 注入测试失败。"; fi
if ! verify_installed_init13; then fail "guided-init13 自检失败。"; fi

COMMITTED=1
say "CloudPanel 导航 guided-init13 安装完成 ✓"
printf '版本：%s\n' "$EXPECTED_VERSION"
printf '导航：Slot3 直接提供「网站管理 / CloudPanel 管理」。\n'
printf '网站管理：选择一次网站后连续操作；98 更换网站；0 直接返回 P07 主菜单。\n'
printf '安全边界：不改 DNS、不删 SOURCE、不覆盖 existing TARGET；Restore-As / 迁移逻辑未改。\n'
if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
