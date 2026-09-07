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

for cmd in curl tar python3 sha256sum readlink ssh ssh-copy-id ssh-keygen rclone; do
  command -v "$cmd" >/dev/null 2>&1 || fail "缺少依赖：$cmd"
done

TMP_DIR="$(mktemp -d -t p07-rc3-install.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT
cd "$TMP_DIR"

say "下载并校验 P07 RC2 基础包..."
curl -fsSL --retry 3 --retry-delay 1 --connect-timeout 15 "${BASE_URL}/${PACKAGE_NAME}" -o "$PACKAGE_NAME" || fail "RC2 基础包下载失败。"
curl -fsSL --retry 3 --retry-delay 1 --connect-timeout 15 "${BASE_URL}/SHA256SUMS.txt" -o SHA256SUMS.txt || fail "RC2 校验文件下载失败。"
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
  curl -fsSL --retry 3 --retry-delay 1 --connect-timeout 15 "${RC3_URL}/${rel}" -o "$TMP_DIR/overlay/$rel" || fail "RC3 增量文件下载失败：$rel"
  verify_git_blob "$TMP_DIR/overlay/$rel" "$blob" || fail "RC3 增量文件身份校验失败：$rel"
  mkdir -p "$SRC_DIR/$(dirname "$rel")"
  cp "$TMP_DIR/overlay/$rel" "$SRC_DIR/$rel"
}

say "下载并校验 RC3 增量..."
fetch_overlay "bin/vfops-user"          "bd3cb33f4a7b6811aa81528d6e9f1b410d2a12be"
fetch_overlay "bin/vfops-auto-backup"   "810dc7723b719700e230bcad8231d6d47b22240c"
fetch_overlay "bin/vfops-storage-setup" "c0ed546a12e09898122be00108501894c0bc465a"
fetch_overlay "lib/auto_backup.py"       "c3d6a2152a60f11c27a3b1ac1a4f86326e2d9986"
fetch_overlay "lib/storage_setup.py"     "a1a629a64fbd677696c3f09250eb2757fd534ef4"

say "安装前自检..."
chmod +x "$SRC_DIR/bin/vfops" "$SRC_DIR/bin/vfops-user" "$SRC_DIR/bin/vfops-auto-backup" "$SRC_DIR/bin/vfops-storage-setup"
bash -n "$SRC_DIR/bin/vfops"
bash -n "$SRC_DIR/bin/vfops-user"
bash -n "$SRC_DIR/bin/vfops-auto-backup"
bash -n "$SRC_DIR/bin/vfops-storage-setup"
python3 -m py_compile "$SRC_DIR"/lib/*.py
find "$SRC_DIR/lib" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

grep -Fq '5. 自动备份（本地 + Google + B2）' "$SRC_DIR/bin/vfops-user" || fail "RC3 用户入口缺少自动备份。"
grep -Fq '设置 / 检查 Google + B2' "$SRC_DIR/bin/vfops-auto-backup" || fail "RC3 自动备份菜单缺少存储设置入口。"
grep -Fq '1. 一键从已有 P07 服务器导入' "$SRC_DIR/bin/vfops-storage-setup" || fail "RC3 远程存储缺少一键导入入口。"

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
for required in \
  "$INSTALL_DIR/bin/vfops-auto-backup" \
  "$INSTALL_DIR/bin/vfops-storage-setup" \
  "$INSTALL_DIR/lib/auto_backup.py" \
  "$INSTALL_DIR/lib/storage_setup.py"; do
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
    fail "Inventory 结果自检失败；未保留失败的新版本。"
  fi
fi

say "安装完成 ✓"
printf '版本：%s\n' "$VERSION_OUT"
printf '自动备份：本地 + Google + B2 · Guarded Scheduler\n'
printf '远程初始化：支持从已有 P07 服务器一键导入\n'
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
