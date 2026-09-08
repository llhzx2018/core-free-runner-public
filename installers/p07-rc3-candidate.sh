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
EXPECTED_BUILD_ID="0.1.0-rc3-guided-init6"

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

say "下载并校验 RC3 增量..."
fetch_overlay "BUILD_ID"                    "5ac1ccb58198dcc5a5911e93d261fb869571a37f"
fetch_overlay "bin/vfops-user"              "bd3cb33f4a7b6811aa81528d6e9f1b410d2a12be"
fetch_overlay "bin/vfops-auto-backup"       "cae9e02e802ce78f3f31ff521f4004ba01bbd748"
fetch_overlay "bin/vfops-storage-setup"     "eabd9dc4d05e6ec9113507157344a5b5ab82e0b8"
fetch_overlay "lib/auto_backup.py"           "c3d6a2152a60f11c27a3b1ac1a4f86326e2d9986"
fetch_overlay "lib/storage_setup.py"         "2ff7077e1c2328a0eaeee6c4e85bdb5a3a971682"
fetch_overlay "lib/google_device_oauth.py"   "5df0530f3a70ed93d6349c35c2b0fbee3d4d453f"

say "安装前自检..."
chmod +x "$SRC_DIR/bin/vfops" "$SRC_DIR/bin/vfops-user" "$SRC_DIR/bin/vfops-auto-backup" "$SRC_DIR/bin/vfops-storage-setup"
bash -n "$SRC_DIR/bin/vfops"
bash -n "$SRC_DIR/bin/vfops-user"
bash -n "$SRC_DIR/bin/vfops-auto-backup"
bash -n "$SRC_DIR/bin/vfops-storage-setup"
python3 -m py_compile "$SRC_DIR"/lib/*.py
find "$SRC_DIR/lib" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

[[ "$(cat "$SRC_DIR/BUILD_ID")" == "$EXPECTED_BUILD_ID" ]] || fail "RC3 Build ID 不匹配。"
grep -Fq '5. 自动备份（本地 + Google + B2）' "$SRC_DIR/bin/vfops-user" || fail "RC3 用户入口缺少自动备份。"
grep -Fq '设置 / 检查 Google + B2' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 自动备份菜单缺少存储设置入口。"
grep -Fq 'Google 实时：' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 自动备份状态缺少 Google 实时健康。"
grep -Fq 'B2 实时：' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 自动备份状态缺少 B2 实时健康。"
grep -Fq '下一步：' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 自动备份状态缺少下一步指引。"
grep -Fq '状态检查不会删除 SOURCE' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 自动备份状态缺少只读安全边界。"
grep -Fq '自动备份返回格式异常' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 立即备份缺少 fail-closed 结果 UX。"
grep -Fq '失败运行不会执行本地自动清理' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 立即备份缺少失败保留策略。"
grep -Fq 'SOURCE 保留' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 立即备份缺少 SOURCE retained 提示。"
grep -Fq 'prepare_first_run_config' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 缺少首次验证配置流程。"
grep -Fq '当前网站：已重新读取 CloudPanel 全部站点' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 缺少当前站点刷新验证。"
grep -Fq '首次启用定时备份前，当前全部 CloudPanel 网站必须先完成一次真实双远程备份验证' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 缺少当前站点 Scheduler Verify Gate。"
grep -Fq '旧 PASS 不会覆盖新站点' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 缺少站点集合漂移保护。"
grep -Fq '本次验证不会创建或修改 P07 Cron' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 缺少首次验证 Cron 安全边界。"
grep -Fq '首次验证已通过 · 定时未开启' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 缺少首次验证状态 UX。"
grep -Fq '1. 全新初始化 Google + B2' "$SRC_DIR/bin/vfops-storage-setup" || fail "RC3 远程存储缺少全新初始化入口。"
grep -Fq '2. 从已有 P07 服务器导入' "$SRC_DIR/bin/vfops-storage-setup" || fail "RC3 远程存储缺少既有服务器导入入口。"
grep -Fq 'P07 远程备份健康状态' "$SRC_DIR/bin/vfops-storage-setup" || fail "RC3 远程存储缺少健康摘要。"
grep -Fq 'SOURCE：保留，未修改 / 未删除' "$SRC_DIR/bin/vfops-storage-setup" || fail "RC3 SOURCE retained 提示缺失。"
grep -Fq 'TVs and Limited Input devices' "$SRC_DIR/bin/vfops-storage-setup" || fail "RC3 Google Device OAuth 引导缺失。"
grep -Fq 'https://oauth2.googleapis.com/device/code' "$SRC_DIR/lib/google_device_oauth.py" || fail "RC3 Google Device OAuth helper 缺失。"
grep -Fq 'friendly_oauth_error' "$SRC_DIR/lib/google_device_oauth.py" || fail "RC3 Google OAuth 异常 UX 缺失。"
grep -Fq 'PROVENANCE_FRESH = "GUIDED_DEVICE_OAUTH_FRESH"' "$SRC_DIR/lib/storage_setup.py" || fail "RC3 Fresh 初始化来源标记缺失。"
grep -Fq 'DEFAULT_MACHINE_ID = Path("/etc/machine-id")' "$SRC_DIR/lib/storage_setup.py" || fail "RC3 Fresh 初始化缺少本机绑定。"
grep -Fq 'setup_provenance' "$SRC_DIR/lib/storage_setup.py" || fail "RC3 storage provenance 缺失。"

say "安装 P07 RC3 Candidate..."
rm -rf "${INSTALL_DIR}.new"
mkdir -p "${INSTALL_DIR}.new"
cp -a "$SRC_DIR"/. "${INSTALL_DIR}.new"/
chmod +x "${INSTALL_DIR}.new/bin/vfops" "${INSTALL_DIR}.new/bin/vfops-user" "${INSTALL_DIR}.new/bin/vfops-auto-backup" "${INSTALL_DIR}.new/bin/vfops-storage-setup"

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
for required in \
  "$INSTALL_DIR/bin/vfops-auto-backup" \
  "$INSTALL_DIR/bin/vfops-storage-setup" \
  "$INSTALL_DIR/lib/auto_backup.py" \
  "$INSTALL_DIR/lib/storage_setup.py" \
  "$INSTALL_DIR/lib/google_device_oauth.py"; do
  if [[ ! -f "$required" ]]; then
    rollback_install
    fail "RC3 运行文件缺失；已回滚。"
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
printf '自动备份：先真实验证本地 + Google + B2，再启用 Guarded Scheduler\n'
printf '远程初始化：Google Device OAuth + B2 引导；也支持从已有 P07 服务器导入\n'
printf '状态检查：Google + B2 实时健康 + 下一步指引\n'
printf '立即备份结果：PASS / FAIL / Busy 可读结果 + 下一步指引\n'
printf '首次 Scheduler Gate：当前全部 CloudPanel 网站双远程未验证 PASS 时不会安装 P07 Cron\n'
printf 'CloudPanel 定时任务：不会修改\n'
printf 'DNS：不会自动修改\n'
printf '旧服务器：不会自动删除\n'

if [[ "${P07_TOOLBOX_PARENT:-0}" == "1" ]]; then
  printf '退出模块后会返回 P07 Toolbox。\n'
else
  printf '普通用户仍从统一 P07 Toolbox 入口进入。\n'
fi

if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then
  printf '\n正在进入 CloudPanel 运维模块...\n'
  exec "$BIN_LINK"
fi
