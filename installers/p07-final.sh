#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"
PREVIOUS_DIR="${P07_PREVIOUS_DIR:-/opt/vf-server-ops.previous}"
BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"
PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"
FINAL_URL="${PUBLIC_ROOT}/dist/p07/0.1.0/overlay"

BASE_PUBLIC_ROOT="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/99b2552606c68b6b278e3310b0cb2a0006474ad9"
BASE_INSTALLER_URL="${BASE_PUBLIC_ROOT}/installers/p07-rc3-r2-oauth-contract.sh"
BASE_INSTALLER_BLOB="4a7889ea606fa2353f194abbb2c6b27345f35050"

EXPECTED_VERSION="VF Server Ops 0.1.0"
EXPECTED_BUILD_ID="0.1.0-release1"
BUILD_BLOB="ba9759efbe649502f8908787c3d1a8c867635d0e"
STORAGE_SETUP_BLOB="b279677ae561f9feb689964bd8f09be98c9211c9"
GOOGLE_OAUTH_BLOB="3b023f307bf744650a351e19bde01b3597469992"
SERVER_MIGRATION_BLOB="4b06d04c93227d55286c6629eb031d262b21f3aa"
INTEGRATION_MANIFEST_BLOB="9b9bd90a6ff6de339923b7b853c12f579e5a0667"
MANIFEST_BLOB="f646160afc202118c6df18f8e23fe35d688e8bde"

say() { printf '\n[P07] %s\n' "$*"; }
fail() { printf '\n[P07] ERROR: %s\n' "$*" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || fail "缺少依赖：curl"
command -v python3 >/dev/null 2>&1 || fail "缺少依赖：python3"
command -v sha1sum >/dev/null 2>&1 || fail "缺少依赖：sha1sum"
command -v install >/dev/null 2>&1 || fail "缺少依赖：install"

verify_git_blob() {
  local file="$1" expected="$2"
  python3 - "$file" "$expected" <<'PY'
import hashlib,sys
path,expected=sys.argv[1:]
data=open(path,'rb').read()
actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
if actual != expected:
    print(f'blob mismatch: {path}: {actual} != {expected}', file=sys.stderr)
    raise SystemExit(1)
PY
}

verify_installed_final() {
  [[ -x "$BIN_LINK" ]] || return 1
  [[ "$("$BIN_LINK" --version 2>/dev/null || true)" == "$EXPECTED_VERSION" ]] || return 1
  [[ "$("$BIN_LINK" --build-id 2>/dev/null || true)" == "$EXPECTED_BUILD_ID" ]] || return 1
  verify_git_blob "$INSTALL_DIR/BUILD_ID" "$BUILD_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/bin/vfops-user" "e7183974dce0a8e6ba4ba3bd26a7561e2377e563" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/lib/server_migration.py" "$SERVER_MIGRATION_BLOB" >/dev/null 2>&1 || return 1
  verify_git_blob "$INSTALL_DIR/docs/authority/P07_INTEGRATION_MANIFEST.json" "$INTEGRATION_MANIFEST_BLOB" >/dev/null 2>&1 || return 1
}

if verify_installed_final; then
  say "P07 V0.1.0 已是正式当前版本 ✓"
  if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
  exit 0
fi

if [[ "${P07_ALLOW_NONROOT:-0}" != "1" ]]; then
  [[ ${EUID:-$(id -u)} -eq 0 ]] || fail "请使用 root 运行。"
fi

TMP_DIR="$(mktemp -d -t p07-v010-final.XXXXXX)"
PRE_RUN_INSTALL="$TMP_DIR/pre-run-install"
PRE_RUN_PREVIOUS="$TMP_DIR/pre-run-previous"
HAD_INSTALL=0
HAD_PREVIOUS=0
COMMITTED=0

if [[ -e "$INSTALL_DIR" ]]; then HAD_INSTALL=1; cp -a "$INSTALL_DIR" "$PRE_RUN_INSTALL"; fi
if [[ -e "$PREVIOUS_DIR" ]]; then HAD_PREVIOUS=1; cp -a "$PREVIOUS_DIR" "$PRE_RUN_PREVIOUS"; fi

restore_pre_run() {
  say "V0.1.0 安装未完成，正在恢复执行前版本..."
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
  if [[ "$HAD_INSTALL" -eq 1 ]]; then say "已恢复执行前 P07。"; else say "执行前没有 P07，已清理未完成安装。"; fi
}

finish() {
  local rc=$?
  trap - EXIT
  if [[ "$rc" -ne 0 && "$COMMITTED" -eq 0 ]]; then restore_pre_run; fi
  rm -rf "$TMP_DIR" 2>/dev/null || true
  exit "$rc"
}
trap finish EXIT

say "准备已验证 guided-init16 安全基线..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$BASE_INSTALLER_URL" -o "$TMP_DIR/base-installer.sh" || fail "基础安装器下载失败。"
bash -n "$TMP_DIR/base-installer.sh" || fail "基础安装器语法校验失败。"
verify_git_blob "$TMP_DIR/base-installer.sh" "$BASE_INSTALLER_BLOB" || fail "基础安装器身份校验失败。"

P07_PUBLIC_ROOT="$BASE_PUBLIC_ROOT" P07_NO_EXEC=1 P07_TOOLBOX_PARENT=1 P07_PREVIOUS_DIR="$PREVIOUS_DIR" P07_INSTALL_DIR="$INSTALL_DIR" P07_BIN_LINK="$BIN_LINK" P07_ALLOW_NONROOT="${P07_ALLOW_NONROOT:-0}" bash "$TMP_DIR/base-installer.sh" || fail "guided-init16 安全基线安装失败。"

[[ "$("$BIN_LINK" --build-id 2>/dev/null || true)" == "0.1.0-rc3-guided-init16" ]] || fail "基线身份不匹配。"

say "下载并校验 P07 V0.1.0 Final Release overlay..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$FINAL_URL/MANIFEST.gitblob" -o "$TMP_DIR/MANIFEST.gitblob" || fail "Final Manifest 下载失败。"
verify_git_blob "$TMP_DIR/MANIFEST.gitblob" "$MANIFEST_BLOB" || fail "Final Manifest 身份校验失败。"

mkdir -p "$TMP_DIR/overlay"
while read -r expected path; do
  [[ -n "$expected" && -n "$path" ]] || continue
  case "$path" in
    /*|*../*|../*|*/..) fail "非法 overlay 路径：$path" ;;
  esac
  mkdir -p "$TMP_DIR/overlay/$(dirname "$path")"
  curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$FINAL_URL/$path" -o "$TMP_DIR/overlay/$path" || fail "Final 文件下载失败：$path"
  verify_git_blob "$TMP_DIR/overlay/$path" "$expected" || fail "Final 文件身份校验失败：$path"
done < "$TMP_DIR/MANIFEST.gitblob"

say "应用 Final Release overlay..."
while read -r expected path; do
  [[ -n "$expected" && -n "$path" ]] || continue
  mode=0644
  case "$path" in bin/*) mode=0755 ;; esac
  install -D -m "$mode" "$TMP_DIR/overlay/$path" "$INSTALL_DIR/$path"
done < "$TMP_DIR/MANIFEST.gitblob"

say "执行 Final Release 自检..."
bash -n "$INSTALL_DIR/bin/vfops"
bash -n "$INSTALL_DIR/bin/vfops-user"
bash -n "$INSTALL_DIR/bin/vfops-migrate-ui"
python3 -m py_compile   "$INSTALL_DIR/lib/app_config.py"   "$INSTALL_DIR/lib/backup_frontend.py"   "$INSTALL_DIR/lib/migrate.py"   "$INSTALL_DIR/lib/restore.py"   "$INSTALL_DIR/lib/restore_apply_core.py"   "$INSTALL_DIR/lib/restore_new.py"   "$INSTALL_DIR/lib/runtime.py"   "$INSTALL_DIR/lib/server_migration.py"   "$INSTALL_DIR/lib/transport.py"   "$INSTALL_DIR/lib/verify.py"

(
  cd "$INSTALL_DIR"
  python3 -m unittest -q tests.test_p07_integration_manifest
  python3 -m unittest -q tests.test_app_config
  python3 -m unittest -q tests.test_server_migration
) || fail "Final Release 安装后回归测试失败。"

[[ "$("$BIN_LINK" --version 2>/dev/null || true)" == "$EXPECTED_VERSION" ]] || fail "Final Version 自检失败。"
[[ "$("$BIN_LINK" --build-id 2>/dev/null || true)" == "$EXPECTED_BUILD_ID" ]] || fail "Final Build ID 自检失败。"

while read -r expected path; do
  [[ -n "$expected" && -n "$path" ]] || continue
  [[ -f "$INSTALL_DIR/$path" ]] || fail "Final 安装文件缺失：$path"
  verify_git_blob "$INSTALL_DIR/$path" "$expected" || fail "Final 安装文件身份不匹配：$path"
done < "$TMP_DIR/MANIFEST.gitblob"

verify_git_blob "$INSTALL_DIR/bin/vfops-storage-setup" "$STORAGE_SETUP_BLOB" || fail "R2 Storage Setup 基线发生漂移。"
verify_git_blob "$INSTALL_DIR/lib/google_device_oauth.py" "$GOOGLE_OAUTH_BLOB" || fail "R2 Google OAuth 基线发生漂移。"
grep -Fq 'server-migrate' "$INSTALL_DIR/bin/vfops" || fail "整机迁移 CLI 未进入 Final Runtime。"
grep -Fq '服务器迁移（整机 / 单站）' "$INSTALL_DIR/bin/vfops-user" || fail "整机迁移入口未进入 Final Runtime。"
grep -Fq 'Google：OAuth Client ID + Client Secret' "$INSTALL_DIR/bin/vfops-storage-setup" || fail "Google+B2 初始化入口发生回归。"

COMMITTED=1
rm -rf "$PREVIOUS_DIR" 2>/dev/null || true

say "P07 V0.1.0 Final Release 安装完成 ✓"
printf '版本：%s\n' "$EXPECTED_VERSION"
printf 'Build：%s\n' "$EXPECTED_BUILD_ID"
printf '已集成：网络节点 / VPS 验机 / CloudPanel 备份恢复整机迁移 / 系统维护安全（由 Toolbox 统一入口提供）。\n'
printf '安全边界：不自动改 DNS、不自动删除 SOURCE、不自动覆盖已有 TARGET。\n'
if [[ "${P07_TOOLBOX_PARENT:-0}" == "1" ]]; then
  printf '退出模块后返回 P07 Toolbox。\n'
else
  printf '普通用户从 P07 Toolbox 唯一入口进入。\n'
fi

if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then
  exec "$BIN_LINK"
fi
