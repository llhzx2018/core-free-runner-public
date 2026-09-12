#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"
PREVIOUS_DIR="${P07_PREVIOUS_DIR:-/opt/vf-server-ops.previous}"
BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"
PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"
RC3_URL="${PUBLIC_ROOT}/dist/p07/0.1.0-rc3/overlay"
BASE_PUBLIC_ROOT="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/394bce967d4fc33698b4e8aa6361ed7fe38ab472"
BASE_INSTALLER_URL="${BASE_PUBLIC_ROOT}/installers/p07.sh"
BASE_INSTALLER_BLOB="e3f91a6d0aacff4fe7c7ba0a2e861b7170dad03d"
EXPECTED_VERSION="VF Server Ops 0.1.0 RC3"
EXPECTED_BUILD_ID="0.1.0-rc3-guided-init14"
BUILD_BLOB="1e07e5b18f89058da04cd2dddaf8e7f7414bb6d2"
CLOUDPANEL_UI_BLOB="5b0fa75d6951586c82404e361b88ab5e10661212"
ADMIN_UI_BLOB="eeae6b514b27e15e20ea596f5cd363e7779e461b"

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

verify_installed_init14() {
  [[ -x "$BIN_LINK" ]] || return 1
  [[ "$($BIN_LINK --version 2>/dev/null || true)" == "$EXPECTED_VERSION" ]] || return 1
  [[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "$EXPECTED_BUILD_ID" ]] || return 1
  verify_git_blob "$INSTALL_DIR/BUILD_ID" "$BUILD_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/bin/vfops-cloudpanel-ui" "$CLOUDPANEL_UI_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/cloudpanel_ui_admin.sh" "$ADMIN_UI_BLOB" >/dev/null 2>&1 || return 1
}

if verify_installed_init14; then
  say "CloudPanel 简化 UX guided-init14 已是当前版本 ✓"
  if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
  exit 0
fi

[[ ${EUID:-$(id -u)} -eq 0 || "${P07_ALLOW_NONROOT:-0}" == "1" ]] || fail "请使用 root 运行。"
TMP_DIR="$(mktemp -d -t p07-init14-install.XXXXXX)"
PRE_RUN_INSTALL="$TMP_DIR/pre-run-install"
PRE_RUN_PREVIOUS="$TMP_DIR/pre-run-previous"
HAD_INSTALL=0
HAD_PREVIOUS=0
COMMITTED=0
if [[ -e "$INSTALL_DIR" ]]; then HAD_INSTALL=1; cp -a "$INSTALL_DIR" "$PRE_RUN_INSTALL"; fi
if [[ -e "$PREVIOUS_DIR" ]]; then HAD_PREVIOUS=1; cp -a "$PREVIOUS_DIR" "$PRE_RUN_PREVIOUS"; fi

restore_pre_run() {
  say "guided-init14 未完成，正在恢复执行前版本..."
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

say "准备已验证 guided-init13 基线..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$BASE_INSTALLER_URL" -o "$TMP_DIR/base-installer.sh" || fail "guided-init13 基线安装器下载失败。"
bash -n "$TMP_DIR/base-installer.sh" || fail "guided-init13 基线安装器语法校验失败。"
verify_git_blob "$TMP_DIR/base-installer.sh" "$BASE_INSTALLER_BLOB" || fail "guided-init13 基线安装器身份校验失败。"
P07_PUBLIC_ROOT="$BASE_PUBLIC_ROOT" P07_NO_EXEC=1 P07_TOOLBOX_PARENT=1 P07_PREVIOUS_DIR="$PREVIOUS_DIR" P07_INSTALL_DIR="$INSTALL_DIR" P07_BIN_LINK="$BIN_LINK" bash "$TMP_DIR/base-installer.sh" || fail "guided-init13 基线安装失败。"
[[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "0.1.0-rc3-guided-init13" ]] || fail "guided-init13 基线安装后身份不匹配。"

fetch_overlay() {
  local rel="$1" blob="$2"
  mkdir -p "$TMP_DIR/new/$(dirname "$rel")"
  curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "${RC3_URL}/${rel}" -o "$TMP_DIR/new/$rel" || fail "guided-init14 文件下载失败：$rel"
  verify_git_blob "$TMP_DIR/new/$rel" "$blob" || fail "guided-init14 文件身份校验失败：$rel"
}

say "下载并校验 CloudPanel 简化 UX guided-init14..."
fetch_overlay "BUILD_ID" "$BUILD_BLOB"
fetch_overlay "bin/vfops-cloudpanel-ui" "$CLOUDPANEL_UI_BLOB"
fetch_overlay "lib/cloudpanel_ui_admin.sh" "$ADMIN_UI_BLOB"
bash -n "$TMP_DIR/new/bin/vfops-cloudpanel-ui" || fail "guided-init14 CloudPanel UI 语法校验失败。"
bash -n "$TMP_DIR/new/lib/cloudpanel_ui_admin.sh" || fail "guided-init14 admin UI 语法校验失败。"
grep -Fq '4. 平台基础能力检查' "$TMP_DIR/new/bin/vfops-cloudpanel-ui" || fail "guided-init14 自检入口缺失。"
! grep -Fq '4. Vhost 模板' "$TMP_DIR/new/bin/vfops-cloudpanel-ui" || fail "guided-init14 普通菜单仍暴露 Vhost 模板。"
grep -Fq 'Vhost 模板由 CloudPanel / P07 自动处理' "$TMP_DIR/new/bin/vfops-cloudpanel-ui" || fail "guided-init14 自动模板说明缺失。"
grep -Fq 'Vhost Templates（高级）' "$TMP_DIR/new/lib/cloudpanel_ui_admin.sh" || fail "guided-init14 高级模板能力缺失。"
grep -Fq '模板名不能为空。' "$TMP_DIR/new/lib/cloudpanel_ui_admin.sh" || fail "guided-init14 空模板名保护缺失。"
grep -Fq '模板来源不能为空。' "$TMP_DIR/new/lib/cloudpanel_ui_admin.sh" || fail "guided-init14 空模板来源保护缺失。"
for forbidden in 'site:delete' 'db:delete' 'user:delete' 'REAL_PASS'; do
  ! grep -Fq "$forbidden" "$TMP_DIR/new/bin/vfops-cloudpanel-ui" "$TMP_DIR/new/lib/cloudpanel_ui_admin.sh" || fail "guided-init14 包含禁止普通入口：$forbidden"
done

say "升级 CloudPanel 简化 UX..."
cp "$TMP_DIR/new/BUILD_ID" "$INSTALL_DIR/BUILD_ID"
cp "$TMP_DIR/new/bin/vfops-cloudpanel-ui" "$INSTALL_DIR/bin/vfops-cloudpanel-ui"
cp "$TMP_DIR/new/lib/cloudpanel_ui_admin.sh" "$INSTALL_DIR/lib/cloudpanel_ui_admin.sh"
chmod 0644 "$INSTALL_DIR/BUILD_ID" "$INSTALL_DIR/lib/cloudpanel_ui_admin.sh"
chmod 0755 "$INSTALL_DIR/bin/vfops-cloudpanel-ui"

if [[ "${P07_INIT14_TEST_FAIL:-0}" == "1" ]]; then fail "guided-init14 注入测试失败。"; fi
if ! verify_installed_init14; then fail "guided-init14 自检失败。"; fi

COMMITTED=1
say "CloudPanel 简化 UX guided-init14 安装完成 ✓"
printf '版本：%s\n' "$EXPECTED_VERSION"
printf 'CloudPanel 管理：普通入口不再显示 Vhost 模板维护。\n'
printf 'Vhost：建站时由 CloudPanel / P07 自动处理；高级底层能力仍保留。\n'
printf '错误 UX：空模板名 / 空来源不再输出 Python Traceback。\n'
printf '安全边界：不改 DNS、不删 SOURCE、不覆盖 existing TARGET；Restore-As / 迁移 / 远程备份逻辑未改。\n'
if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
