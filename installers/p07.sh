#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/vf-server-ops"
BIN_LINK="/usr/local/bin/vfops"
CHANNEL="0.1.0-rc2"
BASE_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/dist/p07/${CHANNEL}"
PACKAGE_NAME="P07_VF_SERVER_OPS_0.1.0-rc2.tar.gz"
PACKAGE_URL="${BASE_URL}/${PACKAGE_NAME}"
CHECKSUM_URL="${BASE_URL}/SHA256SUMS.txt"

say() { printf '\n[P07] %s\n' "$*"; }
fail() { printf '\n[P07] ERROR: %s\n' "$*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] || fail "请使用 root 运行。"

if command -v apt-get >/dev/null 2>&1; then
  missing=()
  command -v curl >/dev/null 2>&1 || missing+=(curl)
  command -v tar >/dev/null 2>&1 || missing+=(tar)
  command -v python3 >/dev/null 2>&1 || missing+=(python3)
  command -v sha256sum >/dev/null 2>&1 || missing+=(coreutils)
  if ((${#missing[@]})); then
    say "自动安装依赖：${missing[*]}"
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
  fi
fi

for cmd in curl tar python3 sha256sum readlink; do
  command -v "$cmd" >/dev/null 2>&1 || fail "缺少依赖：$cmd"
done

TMP_DIR="$(mktemp -d -t p07-install.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT
cd "$TMP_DIR"

say "下载 P07 RC2..."
curl -fL --retry 3 --connect-timeout 15 "$PACKAGE_URL" -o "$PACKAGE_NAME"
curl -fL --retry 3 --connect-timeout 15 "$CHECKSUM_URL" -o SHA256SUMS.txt

say "校验安装包..."
sha256sum -c SHA256SUMS.txt >/dev/null || fail "安装包 SHA256 校验失败。"
tar -tzf "$PACKAGE_NAME" >/dev/null 2>&1 || fail "安装包不是有效 tar.gz。"
mkdir -p extracted
tar -xzf "$PACKAGE_NAME" -C extracted
SRC_DIR="$TMP_DIR/extracted/vf-server-ops"
[[ -f "$SRC_DIR/bin/vfops" ]] || fail "安装包结构异常：缺少核心程序。"
[[ -f "$SRC_DIR/bin/vfops-user" ]] || fail "安装包结构异常：缺少用户入口。"
[[ -f "$SRC_DIR/VERSION" ]] || fail "安装包结构异常：缺少 VERSION。"

say "安装 P07..."
rm -rf "$INSTALL_DIR.new"
mkdir -p "$INSTALL_DIR.new"
cp -a "$SRC_DIR"/. "$INSTALL_DIR.new"/
chmod +x "$INSTALL_DIR.new/bin/vfops" "$INSTALL_DIR.new/bin/vfops-user"
bash -n "$INSTALL_DIR.new/bin/vfops"
bash -n "$INSTALL_DIR.new/bin/vfops-user"
python3 -m py_compile "$INSTALL_DIR.new"/lib/*.py
find "$INSTALL_DIR.new/lib" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

if [[ -e "$INSTALL_DIR" ]]; then
  rm -rf "$INSTALL_DIR.previous"
  mv "$INSTALL_DIR" "$INSTALL_DIR.previous"
fi
mv "$INSTALL_DIR.new" "$INSTALL_DIR"
ln -sfn "$INSTALL_DIR/bin/vfops-user" "$BIN_LINK"

say "安装后自检..."
VERSION_OUT="$($BIN_LINK --version)"
[[ "$VERSION_OUT" == "VF Server Ops 0.1.0 RC2" ]] || fail "版本自检失败：$VERSION_OUT"
SELFTEST_JSON="$TMP_DIR/inventory.json"
$BIN_LINK inventory --compact > "$SELFTEST_JSON" || fail "服务器检查自检失败。"
python3 - "$SELFTEST_JSON" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
if p.get('schema') != 'vf-server-ops.inventory.v1':
    raise SystemExit(1)
PY

say "安装完成 ✓"
printf '版本：%s\n' "$VERSION_OUT"
printf '以后只需要输入：vfops\n'
printf '升级也继续使用同一条 p07.sh 安装命令。\n'
printf 'P07 不会自动改 DNS，也不会自动删除旧服务器。\n'

if [[ -t 0 && -t 1 ]]; then
  printf '\n正在进入 P07...\n'
  exec "$BIN_LINK"
fi
