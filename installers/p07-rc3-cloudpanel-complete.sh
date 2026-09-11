#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"
PREVIOUS_DIR="${P07_PREVIOUS_DIR:-/opt/vf-server-ops.previous}"
BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"
PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"
RC3_URL="${PUBLIC_ROOT}/dist/p07/0.1.0-rc3/overlay"
BASE_PUBLIC_ROOT="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/2ed5905103621693a8e8428229b501f1110be381"
BASE_INSTALLER_URL="${BASE_PUBLIC_ROOT}/installers/p07-rc3-candidate.sh"
BASE_INSTALLER_BLOB="92e5f0079294ca22bc77b7e7f48d64d779de263d"
EXPECTED_VERSION="VF Server Ops 0.1.0 RC3"
EXPECTED_BUILD_ID="0.1.0-rc3-guided-init10"

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

verify_installed_init10() {
  [[ -x "$BIN_LINK" ]] || return 1
  [[ "$($BIN_LINK --version 2>/dev/null || true)" == "$EXPECTED_VERSION" ]] || return 1
  [[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "$EXPECTED_BUILD_ID" ]] || return 1
  [[ -f "$INSTALL_DIR/BUILD_ID" ]] || return 1
  verify_git_blob "$INSTALL_DIR/BUILD_ID" "2e860375f5e801262bd200e5251c5524f5e2ec32" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/bin/vfops-cloudpanel-ui" "d3f9dea0e6bb6d80e45b69db51c547fcca06ad9c" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/cloudpanel_ui_common.sh" "3d8409c0f8fa5227064ddde0113d9bb4ba4a03b7" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/cloudpanel_ui_sites.sh" "dc1458efb9a669185b07171f7748959711ac59de" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/cloudpanel_ui_ops.sh" "4eeedb7facfe709583476e3b84ebce00d0a8ab03" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/cloudpanel_ui_admin.sh" "6cc6a716ba72413b3b5e05606711c7e7bdb97aed" >/dev/null 2>&1 || return 1
}

if verify_installed_init10; then
  say "CloudPanel Foundation guided-init10 已是当前版本 ✓"
  if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
  exit 0
fi

[[ ${EUID:-$(id -u)} -eq 0 || "${P07_ALLOW_NONROOT:-0}" == "1" ]] || fail "请使用 root 运行。"
TMP_DIR="$(mktemp -d -t p07-init10-install.XXXXXX)"
HAD_PRE_RUN=0
BASE_INSTALLED=0
COMMITTED=0
[[ -e "$INSTALL_DIR" ]] && HAD_PRE_RUN=1

restore_pre_run() {
  say "guided-init10 未完成，正在恢复执行前版本..."
  rm -rf "$INSTALL_DIR" 2>/dev/null || true
  if [[ "$HAD_PRE_RUN" -eq 1 && -e "$PREVIOUS_DIR" ]]; then
    mv "$PREVIOUS_DIR" "$INSTALL_DIR" 2>/dev/null || true
    if [[ -f "$INSTALL_DIR/bin/vfops-user" ]]; then
      mkdir -p "$(dirname "$BIN_LINK")" 2>/dev/null || true
      ln -sfn "$INSTALL_DIR/bin/vfops-user" "$BIN_LINK" 2>/dev/null || true
    elif [[ -f "$INSTALL_DIR/bin/vfops" ]]; then
      mkdir -p "$(dirname "$BIN_LINK")" 2>/dev/null || true
      ln -sfn "$INSTALL_DIR/bin/vfops" "$BIN_LINK" 2>/dev/null || true
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
  if [[ "$rc" -ne 0 && "$BASE_INSTALLED" -eq 1 && "$COMMITTED" -eq 0 ]]; then
    restore_pre_run
  fi
  rm -rf "$TMP_DIR" 2>/dev/null || true
  exit "$rc"
}
trap finish EXIT

say "准备已验证 guided-init9 基线..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$BASE_INSTALLER_URL" -o "$TMP_DIR/base-installer.sh" || fail "guided-init9 基线安装器下载失败。"
bash -n "$TMP_DIR/base-installer.sh" || fail "guided-init9 基线安装器语法校验失败。"
verify_git_blob "$TMP_DIR/base-installer.sh" "$BASE_INSTALLER_BLOB" || fail "guided-init9 基线安装器身份校验失败。"
P07_PUBLIC_ROOT="$BASE_PUBLIC_ROOT" P07_NO_EXEC=1 P07_TOOLBOX_PARENT=1 bash "$TMP_DIR/base-installer.sh" || fail "guided-init9 基线安装失败。"
[[ "$($BIN_LINK --build-id 2>/dev/null || true)" == "0.1.0-rc3-guided-init9" ]] || fail "guided-init9 基线安装后身份不匹配。"
BASE_INSTALLED=1
if [[ "$HAD_PRE_RUN" -eq 1 && ! -e "$PREVIOUS_DIR" ]]; then
  fail "guided-init9 基线未保留执行前版本，已停止。"
fi

fetch_overlay() {
  local rel="$1" blob="$2"
  mkdir -p "$TMP_DIR/new/$(dirname "$rel")"
  curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "${RC3_URL}/${rel}" -o "$TMP_DIR/new/$rel" || fail "guided-init10 文件下载失败：$rel"
  verify_git_blob "$TMP_DIR/new/$rel" "$blob" || fail "guided-init10 文件身份校验失败：$rel"
}

say "下载并校验 CloudPanel Foundation guided-init10..."
fetch_overlay "BUILD_ID"                        "2e860375f5e801262bd200e5251c5524f5e2ec32"
fetch_overlay "bin/vfops-cloudpanel-ui"         "d3f9dea0e6bb6d80e45b69db51c547fcca06ad9c"
fetch_overlay "lib/cloudpanel_ui_common.sh"     "3d8409c0f8fa5227064ddde0113d9bb4ba4a03b7"
fetch_overlay "lib/cloudpanel_ui_sites.sh"      "dc1458efb9a669185b07171f7748959711ac59de"
fetch_overlay "lib/cloudpanel_ui_ops.sh"        "4eeedb7facfe709583476e3b84ebce00d0a8ab03"
fetch_overlay "lib/cloudpanel_ui_admin.sh"      "6cc6a716ba72413b3b5e05606711c7e7bdb97aed"

for script in "$TMP_DIR/new/bin/vfops-cloudpanel-ui" "$TMP_DIR/new/lib/"cloudpanel_ui_*.sh; do
  bash -n "$script" || fail "guided-init10 Shell 语法校验失败。"
done
BUNDLE="$(cat "$TMP_DIR/new/bin/vfops-cloudpanel-ui" "$TMP_DIR/new/lib/"cloudpanel_ui_*.sh)"
for marker in '网站健康检查' '创建网站' '数据库工具' 'SSL / HTTPS' 'CloudPanel 安全' 'CloudPanel 用户' 'Vhost 模板' '平台基础能力检查'; do
  grep -Fq "$marker" <<<"$BUNDLE" || fail "CloudPanel Foundation 缺少任务：$marker"
done
for forbidden in 'site:delete' 'db:delete' 'user:delete' 'REAL_PASS'; do
  if grep -Fq "$forbidden" <<<"$BUNDLE"; then fail "CloudPanel 普通入口包含禁止内容：$forbidden"; fi
done
grep -Fq 'read -r -s' <<<"$BUNDLE" || fail "CloudPanel 密码输入不是静默模式。"
grep -Fq 'P07_SECRET="$SECRET_VALUE"' <<<"$BUNDLE" || fail "CloudPanel secret handoff 边界缺失。"
grep -Fq 'TARGET 已存在，P07 不会覆盖' <<<"$BUNDLE" || fail "CloudPanel TARGET collision guard 缺失。"
grep -Fq -- '--resolve "$domain:443:127.0.0.1"' <<<"$BUNDLE" || fail "CloudPanel 本机 HTTPS SNI 健康检查缺失。"

say "升级 CloudPanel Foundation..."
mkdir -p "$INSTALL_DIR/bin" "$INSTALL_DIR/lib"
cp "$TMP_DIR/new/BUILD_ID" "$INSTALL_DIR/BUILD_ID"
cp "$TMP_DIR/new/bin/vfops-cloudpanel-ui" "$INSTALL_DIR/bin/vfops-cloudpanel-ui"
cp "$TMP_DIR/new/lib/"cloudpanel_ui_*.sh "$INSTALL_DIR/lib/"
chmod +x "$INSTALL_DIR/bin/vfops-cloudpanel-ui"

if [[ "${P07_INIT10_TEST_FAIL:-0}" == "1" ]]; then
  fail "guided-init10 注入测试失败。"
fi
if ! verify_installed_init10; then
  fail "guided-init10 自检失败。"
fi
if ! printf '0\n' | "$INSTALL_DIR/bin/vfops-cloudpanel-ui" >/dev/null 2>&1; then
  fail "CloudPanel UI 启动自检失败。"
fi

COMMITTED=1
say "CloudPanel Foundation guided-init10 安装完成 ✓"
printf '版本：%s\n' "$EXPECTED_VERSION"
printf 'CloudPanel：网站详情 / 健康检查 / 五类建站 / 数据库 / SSL / 权限缓存 / Panel 安全 / 用户 / Vhost 模板 / 平台基础能力检查\n'
printf '安全边界：普通入口不提供站点、数据库或用户删除；不改 DNS、不删 SOURCE、不覆盖 existing TARGET。\n'
if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
