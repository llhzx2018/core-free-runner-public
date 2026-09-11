#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"
PREVIOUS_DIR="${P07_PREVIOUS_DIR:-/opt/vf-server-ops.previous}"
BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"
BASE_CHANNEL="0.1.0-rc2"
RC3_CHANNEL="0.1.0-rc3"
PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"
BASE_URL="${PUBLIC_ROOT}/dist/p07/${BASE_CHANNEL}"
RC3_URL="${PUBLIC_ROOT}/dist/p07/${RC3_CHANNEL}/overlay"
PACKAGE_NAME="P07_VF_SERVER_OPS_0.1.0-rc2.tar.gz"
EXPECTED_VERSION="VF Server Ops 0.1.0 RC3"
EXPECTED_BUILD_ID="0.1.0-rc3-guided-init9"

say() { printf '\n[P07] %s\n' "$*"; }
fail() { printf '\n[P07] ERROR: %s\n' "$*" >&2; exit 1; }

if [[ "${P07_ALLOW_NONROOT:-0}" != "1" ]]; then
  [[ ${EUID:-$(id -u)} -eq 0 ]] || fail "请使用 root 运行。"
fi

if [[ "${P07_SKIP_APT:-0}" != "1" ]] && command -v apt-get >/dev/null 2>&1; then
  missing=()
  command -v curl >/dev/null 2>&1 || missing+=(curl)
  command -v tar >/dev/null 2>&1 || missing+=(tar)
  command -v python3 >/dev/null 2>&1 || missing+=(python3)
  command -v sha256sum >/dev/null 2>&1 || missing+=(coreutils)
  command -v ssh >/dev/null 2>&1 || missing+=(openssh-client)
  command -v scp >/dev/null 2>&1 || missing+=(openssh-client)
  command -v ssh-copy-id >/dev/null 2>&1 || missing+=(openssh-client)
  command -v ssh-keygen >/dev/null 2>&1 || missing+=(openssh-client)
  command -v rclone >/dev/null 2>&1 || missing+=(rclone)
  if ((${#missing[@]})); then
    mapfile -t missing < <(printf '%s\n' "${missing[@]}" | awk '!seen[$0]++')
    say "自动安装依赖：${missing[*]}"
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
  fi
fi

for cmd in curl tar python3 sha256sum readlink ssh scp ssh-copy-id ssh-keygen rclone; do
  command -v "$cmd" >/dev/null 2>&1 || fail "缺少依赖：$cmd"
done

TMP_DIR="$(mktemp -d -t p07-rc3-install.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT
cd "$TMP_DIR"

say "下载并校验 P07 RC2 基础包..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "${BASE_URL}/${PACKAGE_NAME}" -o "$PACKAGE_NAME" || fail "RC2 基础包下载失败。"
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "${BASE_URL}/SHA256SUMS.txt" -o SHA256SUMS.txt || fail "RC2 校验文件下载失败。"
sha256sum -c SHA256SUMS.txt >/dev/null || fail "RC2 基础包 SHA256 校验失败。"
tar -tzf "$PACKAGE_NAME" >/dev/null 2>&1 || fail "RC2 基础包不是有效 tar.gz。"
mkdir -p extracted
tar -xzf "$PACKAGE_NAME" -C extracted
SRC_DIR="$TMP_DIR/extracted/vf-server-ops"
[[ -f "$SRC_DIR/bin/vfops" && -f "$SRC_DIR/bin/vfops-user" && -f "$SRC_DIR/VERSION" ]] || fail "RC2 基础包结构异常。"

verify_git_blob() {
  local file="$1" expected="$2"
  python3 - "$file" "$expected" <<'PY'
import hashlib,sys
p=sys.argv[1]
expected=sys.argv[2]
data=open(p,'rb').read()
actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
if actual != expected:
    print(f'blob mismatch: {p}: {actual} != {expected}', file=sys.stderr)
    raise SystemExit(1)
PY
}

fetch_overlay() {
  local rel="$1" blob="$2"
  mkdir -p "$TMP_DIR/overlay/$(dirname "$rel")"
  curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "${RC3_URL}/${rel}" -o "$TMP_DIR/overlay/$rel" || fail "RC3 增量文件下载失败：$rel"
  verify_git_blob "$TMP_DIR/overlay/$rel" "$blob" || fail "RC3 增量文件身份校验失败：$rel"
  mkdir -p "$SRC_DIR/$(dirname "$rel")"
  cp "$TMP_DIR/overlay/$rel" "$SRC_DIR/$rel"
}

say "下载并校验 RC3 guided-init9 完整基础运行时..."
fetch_overlay "BUILD_ID"                    "62541d7c97ba0cf87ae0b2c46361d72a40dbe298"
fetch_overlay "bin/vfops-user"              "71b35360d24fa2a4d8fc55ea1f3e2ae1598c5032"
fetch_overlay "bin/vfops-site-ui"           "9b74fbfea635ecb28bf2cd452016705118fadaba"
fetch_overlay "bin/vfops-migrate-ui"        "acd3230599fda6eb9f2901bf0ac68ec08964c18b"
fetch_overlay "bin/vfops-cloudpanel-ui"     "a37d218a3ba0614a59a9e9c53230425215406cae"
fetch_overlay "bin/vfops-auto-backup"       "cae9e02e802ce78f3f31ff521f4004ba01bbd748"
fetch_overlay "bin/vfops-storage-setup"     "eabd9dc4d05e6ec9113507157344a5b5ab82e0b8"
fetch_overlay "lib/cloudpanel.py"           "fb9f7ab742d981a0fe180b1c2304afb81a6b3b48"
fetch_overlay "lib/cloudpanel_site.py"      "3de08127e517c1a460706f64aa7fde9aa6b86f2b"
fetch_overlay "lib/site_lifecycle.py"       "9a24156d87223de67aae57d744abed7a63fbce4a"
fetch_overlay "lib/restore_as.py"           "296373b81a1af46fbccd922926520b85cd49a9bf"
fetch_overlay "lib/restore_as_verified.py"  "05897451b0f8e068271211f2052e2af9197f5736"
fetch_overlay "lib/restore_apply.py"        "0a5aec9467b8da3290fbd93ad66b22bff816f124"
fetch_overlay "lib/restore_apply_core.py"   "06cf797a3ff0948c5df65dfcf526f56037f6d461"
fetch_overlay "lib/auto_backup.py"          "c3d6a2152a60f11c27a3b1ac1a4f86326e2d9986"
fetch_overlay "lib/storage_setup.py"        "2ff7077e1c2328a0eaeee6c4e85bdb5a3a971682"
fetch_overlay "lib/google_device_oauth.py"  "5df0530f3a70ed93d6349c35c2b0fbee3d4d453f"
fetch_overlay "lib/package_core.py"         "a997b70ab0450df193977d8e449dd604c38b49ea"
fetch_overlay "lib/package.py"              "b5671d3a66b27fb569f8b774e6f9b7e7902843c3"
fetch_overlay "lib/backup_frontend.py"      "4e3f4d3f1f76b2a301bad5d0c9aad68e5a1c2c23"
fetch_overlay "lib/diagnostics.py"          "7f5d8f763e04c9178352cecd94612dc165abb018"
fetch_overlay "lib/restore.py"              "bc698febb2e9df920f3396963c7e63ac8a04e977"

say "安装前自检..."
for script in \
  "$SRC_DIR/bin/vfops" \
  "$SRC_DIR/bin/vfops-user" \
  "$SRC_DIR/bin/vfops-site-ui" \
  "$SRC_DIR/bin/vfops-migrate-ui" \
  "$SRC_DIR/bin/vfops-cloudpanel-ui" \
  "$SRC_DIR/bin/vfops-auto-backup" \
  "$SRC_DIR/bin/vfops-storage-setup"; do
  chmod +x "$script"
  bash -n "$script"
done
python3 -m py_compile "$SRC_DIR"/lib/*.py
PYTHONPATH="$SRC_DIR/lib" python3 - <<'PY'
import backup_frontend
import cloudpanel
import cloudpanel_site
import package
import package_core
import restore
import restore_as
import restore_as_verified
import site_lifecycle
assert package.build_backup is backup_frontend.build_backup_with_discovery
assert callable(package_core.build_backup)
assert package_core.build_backup is not package.build_backup
assert callable(restore.target_has_site)
assert callable(restore_as.restore_as)
assert callable(restore_as_verified.restore_as_verified)
assert callable(site_lifecycle.create_site)
assert callable(cloudpanel.add_php_site)
assert callable(cloudpanel_site.reset_permissions)
PY
find "$SRC_DIR/lib" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

[[ "$(cat "$SRC_DIR/BUILD_ID")" == "$EXPECTED_BUILD_ID" ]] || fail "RC3 Build ID 不匹配。"

grep -Fq '1. 服务器 / 网站概览' "$SRC_DIR/bin/vfops-user" || fail "Menu 3 缺少服务器 / 网站概览。"
grep -Fq '2. 备份网站' "$SRC_DIR/bin/vfops-user" || fail "Menu 3 缺少备份网站。"
grep -Fq '3. 恢复网站' "$SRC_DIR/bin/vfops-user" || fail "Menu 3 缺少恢复网站。"
grep -Fq '4. 迁移网站到新服务器' "$SRC_DIR/bin/vfops-user" || fail "Menu 3 缺少迁移网站。"
grep -Fq '5. 自动备份 / 远程灾备' "$SRC_DIR/bin/vfops-user" || fail "Menu 3 缺少自动备份 / 远程灾备。"
grep -Fq '6. CloudPanel 网站工具' "$SRC_DIR/bin/vfops-user" || fail "Menu 3 缺少 CloudPanel 网站工具。"
grep -Fq 'vfops-site-ui' "$SRC_DIR/bin/vfops-user" || fail "Menu 3 网站模块路由缺失。"
grep -Fq 'vfops-migrate-ui' "$SRC_DIR/bin/vfops-user" || fail "Menu 3 迁移模块路由缺失。"
grep -Fq 'vfops-cloudpanel-ui' "$SRC_DIR/bin/vfops-user" || fail "Menu 3 CloudPanel 工具路由缺失。"
grep -Fq '--build-id' "$SRC_DIR/bin/vfops-user" || fail "Menu 3 缺少独立 build identity 输出。"

grep -Fq 'restore_as_verified.py' "$SRC_DIR/bin/vfops-site-ui" || fail "Restore-As 未接入自动本机验证。"
grep -Fq '无需先在 CloudPanel 手工创建空网站' "$SRC_DIR/bin/vfops-site-ui" || fail "Restore-As 仍要求人工预建站点。"
grep -Fq '失败会回滚本次新建目标' "$SRC_DIR/bin/vfops-site-ui" || fail "Restore-As 缺少失败回滚 UX。"
grep -Fq 'RESTORE_AS:' "$SRC_DIR/bin/vfops-site-ui" || fail "Restore-As 显式确认契约缺失。"
grep -Fq '按原域名恢复' "$SRC_DIR/bin/vfops-site-ui" || fail "原域恢复入口缺失。"

grep -Fq 'TARGET_SITE_CONFLICT' "$SRC_DIR/bin/vfops-migrate-ui" || fail "迁移缺少 TARGET 冲突保护。"
grep -Fq 'DNS：未修改' "$SRC_DIR/bin/vfops-migrate-ui" || fail "迁移缺少 DNS 不修改边界。"
grep -Fq 'SOURCE：保留' "$SRC_DIR/bin/vfops-migrate-ui" || fail "迁移缺少 SOURCE 保留边界。"

grep -Fq '修复网站权限' "$SRC_DIR/bin/vfops-cloudpanel-ui" || fail "CloudPanel 工具缺少权限修复。"
grep -Fq '清理 Varnish 缓存' "$SRC_DIR/bin/vfops-cloudpanel-ui" || fail "CloudPanel 工具缺少缓存清理。"
grep -Fq '查看 SSL 状态' "$SRC_DIR/bin/vfops-cloudpanel-ui" || fail "CloudPanel 工具缺少 SSL 状态。"
if grep -Fq 'site:delete' "$SRC_DIR/bin/vfops-cloudpanel-ui" || grep -Fq 'db:delete' "$SRC_DIR/bin/vfops-cloudpanel-ui"; then
  fail "普通 CloudPanel 工具错误暴露破坏性删除。"
fi

grep -Fq '设置 / 检查 Google + B2' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 自动备份菜单缺少存储设置入口。"
grep -Fq 'Google 实时：' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 自动备份状态缺少 Google 实时健康。"
grep -Fq 'B2 实时：' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 自动备份状态缺少 B2 实时健康。"
grep -Fq '当前网站：已重新读取 CloudPanel 全部站点' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 缺少当前站点刷新验证。"
grep -Fq '首次启用定时备份前，当前全部 CloudPanel 网站必须先完成一次真实双远程备份验证' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 缺少当前站点 Scheduler Verify Gate。"
grep -Fq '旧 PASS 不会覆盖新站点' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 缺少站点集合漂移保护。"
grep -Fq '本次验证不会创建或修改 P07 Cron' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 缺少首次验证 Cron 安全边界。"

grep -Fq '1. 全新初始化 Google + B2' "$SRC_DIR/bin/vfops-storage-setup" || fail "RC3 远程存储缺少全新初始化入口。"
grep -Fq '2. 从已有 P07 服务器导入' "$SRC_DIR/bin/vfops-storage-setup" || fail "RC3 远程存储缺少既有服务器导入入口。"
grep -Fq 'TVs and Limited Input devices' "$SRC_DIR/bin/vfops-storage-setup" || fail "RC3 Google Device OAuth 引导缺失。"
grep -Fq 'https://oauth2.googleapis.com/device/code' "$SRC_DIR/lib/google_device_oauth.py" || fail "RC3 Google Device OAuth helper 缺失。"

grep -Fq 'def add_php_site' "$SRC_DIR/lib/cloudpanel.py" || fail "CloudPanel Foundation 缺少 PHP site adapter。"
grep -Fq 'def add_database' "$SRC_DIR/lib/cloudpanel.py" || fail "CloudPanel Foundation 缺少 database adapter。"
grep -Fq 'def derive_target_identity' "$SRC_DIR/lib/site_lifecycle.py" || fail "CloudPanel 生命周期缺少目标身份生成。"
grep -Fq 'target domain already exists' "$SRC_DIR/lib/site_lifecycle.py" || fail "CloudPanel 生命周期缺少 target collision guard。"
grep -Fq 'source_ssl_reused' "$SRC_DIR/lib/restore_as.py" || fail "Restore-As 缺少 SOURCE TLS 不复用结果。"
grep -Fq 'existing_site_overwrite_allowed' "$SRC_DIR/lib/restore_as.py" || fail "Restore-As 缺少 no-overwrite contract。"
grep -Fq 'search-replace' "$SRC_DIR/lib/restore_as.py" || fail "Restore-As 缺少 WordPress serialization-safe URL remap。"
grep -Fq 'LOCAL_HTTPS_SNI' "$SRC_DIR/lib/restore_as_verified.py" || fail "Restore-As 缺少本机 SNI 验证。"
grep -Fq 'TARGET_VHOST_PRESENT_TLS_DEFERRED' "$SRC_DIR/lib/restore_as_verified.py" || fail "Restore-As 缺少 DNS 未就绪 TLS defer 验证。"
grep -Fq 'FILES_DB_APP_HOST_SNI' "$SRC_DIR/lib/restore_as_verified.py" || fail "Restore-As 验证范围不完整。"

grep -Fq 'build_backup_with_discovery' "$SRC_DIR/lib/package.py" || fail "RC3 真实数据库备份兼容 facade 缺失。"
grep -Fq 'wp-config.php' "$SRC_DIR/lib/backup_frontend.py" || fail "RC3 WordPress 数据库恢复凭据发现缺失。"
grep -Fq 'DATABASE_URL' "$SRC_DIR/lib/backup_frontend.py" || fail "RC3 DATABASE_URL 数据库恢复凭据发现缺失。"
grep -Fq 'O_NOFOLLOW' "$SRC_DIR/lib/backup_frontend.py" || fail "RC3 数据库凭据读取缺少 nofollow 防竞态保护。"
grep -Fq 'TARGET_SITE_ALREADY_EXISTS' "$SRC_DIR/lib/restore.py" || fail "RC3 恢复计划缺少 TARGET 冲突 blocker。"
grep -Fq 'existing_site_overwrite_allowed' "$SRC_DIR/lib/restore.py" || fail "RC3 恢复计划缺少 no-overwrite contract。"
if grep -Fq 'gates.append("OWNER_OVERWRITE_GATE_REQUIRED")' "$SRC_DIR/lib/restore.py"; then
  fail "RC3 恢复计划仍错误允许 OWNER overwrite gate。"
fi

say "安装 P07 RC3 Candidate..."
rm -rf "${INSTALL_DIR}.new"
mkdir -p "${INSTALL_DIR}.new"
cp -a "$SRC_DIR"/. "${INSTALL_DIR}.new"/
for script in \
  "${INSTALL_DIR}.new/bin/vfops" \
  "${INSTALL_DIR}.new/bin/vfops-user" \
  "${INSTALL_DIR}.new/bin/vfops-site-ui" \
  "${INSTALL_DIR}.new/bin/vfops-migrate-ui" \
  "${INSTALL_DIR}.new/bin/vfops-cloudpanel-ui" \
  "${INSTALL_DIR}.new/bin/vfops-auto-backup" \
  "${INSTALL_DIR}.new/bin/vfops-storage-setup"; do
  chmod +x "$script"
done

HAD_PREVIOUS=0
if [[ -e "$INSTALL_DIR" ]]; then
  HAD_PREVIOUS=1
  rm -rf "$PREVIOUS_DIR"
  mv "$INSTALL_DIR" "$PREVIOUS_DIR"
fi
mv "${INSTALL_DIR}.new" "$INSTALL_DIR"
mkdir -p "$(dirname "$BIN_LINK")"
ln -sfn "$INSTALL_DIR/bin/vfops-user" "$BIN_LINK"

rollback_install() {
  say "RC3 自检未通过，正在自动恢复安装前版本..."
  rm -rf "$INSTALL_DIR"
  if [[ "$HAD_PREVIOUS" -eq 1 && -e "$PREVIOUS_DIR" ]]; then
    mv "$PREVIOUS_DIR" "$INSTALL_DIR"
    if [[ -f "$INSTALL_DIR/bin/vfops-user" ]]; then
      ln -sfn "$INSTALL_DIR/bin/vfops-user" "$BIN_LINK"
    elif [[ -f "$INSTALL_DIR/bin/vfops" ]]; then
      ln -sfn "$INSTALL_DIR/bin/vfops" "$BIN_LINK"
    else
      rm -f "$BIN_LINK"
    fi
    say "已恢复安装前版本。"
  else
    rm -f "$BIN_LINK"
    say "这台服务器之前没有 P07，已清理失败的新安装。"
  fi
}

say "安装后自检..."
if ! VERSION_OUT="$($BIN_LINK --version 2>/dev/null)"; then
  rollback_install
  fail "版本自检失败；未保留失败的新版本。"
fi
if [[ "$VERSION_OUT" != "$EXPECTED_VERSION" ]]; then
  rollback_install
  fail "版本自检不匹配；未保留失败的新版本。"
fi
if [[ ! -f "$INSTALL_DIR/BUILD_ID" || "$(cat "$INSTALL_DIR/BUILD_ID")" != "$EXPECTED_BUILD_ID" ]]; then
  rollback_install
  fail "Build ID 自检不匹配；未保留失败的新版本。"
fi
if [[ "$($BIN_LINK --build-id 2>/dev/null)" != "$EXPECTED_BUILD_ID" ]]; then
  rollback_install
  fail "运行入口 Build ID 自检不匹配；未保留失败的新版本。"
fi
for required in \
  "$INSTALL_DIR/bin/vfops-site-ui" \
  "$INSTALL_DIR/bin/vfops-migrate-ui" \
  "$INSTALL_DIR/bin/vfops-cloudpanel-ui" \
  "$INSTALL_DIR/bin/vfops-auto-backup" \
  "$INSTALL_DIR/bin/vfops-storage-setup" \
  "$INSTALL_DIR/lib/cloudpanel.py" \
  "$INSTALL_DIR/lib/cloudpanel_site.py" \
  "$INSTALL_DIR/lib/site_lifecycle.py" \
  "$INSTALL_DIR/lib/restore_as.py" \
  "$INSTALL_DIR/lib/restore_as_verified.py" \
  "$INSTALL_DIR/lib/restore_apply.py" \
  "$INSTALL_DIR/lib/restore_apply_core.py" \
  "$INSTALL_DIR/lib/auto_backup.py" \
  "$INSTALL_DIR/lib/storage_setup.py" \
  "$INSTALL_DIR/lib/google_device_oauth.py" \
  "$INSTALL_DIR/lib/package_core.py" \
  "$INSTALL_DIR/lib/package.py" \
  "$INSTALL_DIR/lib/backup_frontend.py" \
  "$INSTALL_DIR/lib/diagnostics.py" \
  "$INSTALL_DIR/lib/restore.py"; do
  if [[ ! -f "$required" ]]; then
    rollback_install
    fail "RC3 guided-init9 运行文件缺失；已回滚。"
  fi
done

if [[ "${P07_SKIP_INVENTORY_SELFTEST:-0}" != "1" ]]; then
  SELFTEST_JSON="$TMP_DIR/inventory.json"
  if ! "$BIN_LINK" inventory --compact > "$SELFTEST_JSON" 2>/dev/null; then
    rollback_install
    fail "服务器检查自检失败；未保留失败的新版本。"
  fi
  if ! python3 - "$SELFTEST_JSON" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
if p.get('schema') != 'vf-server-ops.inventory.v1':
    raise SystemExit(1)
PY
  then
    rollback_install
    fail "Inventory 结果自检不匹配；未保留失败的新版本。"
  fi
fi

say "安装完成 ✓"
printf '版本：%s\n' "$VERSION_OUT"
printf '基础功能：网站概览 / 备份 / Restore-As / 原域恢复 / 跨 VPS 迁移 / 双远程灾备 / CloudPanel 网站工具\n'
printf 'Restore-As：自动创建 TARGET 网站与数据库；自动恢复文件、导入数据库、重写应用配置并做本机 Host/SNI 验证\n'
printf '安全边界：不改 DNS、不删除 SOURCE、不覆盖已存在 TARGET、不复用 SOURCE 域名证书\n'
printf '失败处理：只回滚本次新建 TARGET 资源；SOURCE 保留\n'
printf '自动备份：先真实验证本地 + Google + B2，再启用 Guarded Scheduler\n'
printf 'CloudPanel 定时任务：不会修改\n'

if [[ "${P07_TOOLBOX_PARENT:-0}" == "1" ]]; then
  printf '退出模块后会返回 P07 Toolbox。\n'
else
  printf '普通用户仍从统一 P07 Toolbox 入口进入。\n'
fi

if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then
  printf '\n正在进入 CloudPanel 运维模块...\n'
  exec "$BIN_LINK"
fi
