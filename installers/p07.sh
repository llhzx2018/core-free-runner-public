#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/vf-server-ops"
PREVIOUS_DIR="/opt/vf-server-ops.previous"
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
curl -fsSL --retry 3 --retry-delay 1 --connect-timeout 15 "$PACKAGE_URL" -o "$PACKAGE_NAME" || fail "安装包下载失败。"
curl -fsSL --retry 3 --retry-delay 1 --connect-timeout 15 "$CHECKSUM_URL" -o SHA256SUMS.txt || fail "校验文件下载失败。"

say "校验安装包..."
sha256sum -c SHA256SUMS.txt >/dev/null || fail "安装包 SHA256 校验失败。"
tar -tzf "$PACKAGE_NAME" >/dev/null 2>&1 || fail "安装包不是有效 tar.gz。"
mkdir -p extracted
tar -xzf "$PACKAGE_NAME" -C extracted
SRC_DIR="$TMP_DIR/extracted/vf-server-ops"
[[ -f "$SRC_DIR/bin/vfops" ]] || fail "安装包结构异常：缺少核心程序。"
[[ -f "$SRC_DIR/bin/vfops-user" ]] || fail "安装包结构异常：缺少用户入口。"
[[ -f "$SRC_DIR/VERSION" ]] || fail "安装包结构异常：缺少 VERSION。"

say "安装前自检..."
chmod +x "$SRC_DIR/bin/vfops" "$SRC_DIR/bin/vfops-user"
bash -n "$SRC_DIR/bin/vfops" || fail "核心程序 Bash 自检失败。"
bash -n "$SRC_DIR/bin/vfops-user" || fail "用户入口 Bash 自检失败。"
python3 -m py_compile "$SRC_DIR"/lib/*.py || fail "Python 模块自检失败。"
find "$SRC_DIR/lib" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

say "安装 P07..."
rm -rf "$INSTALL_DIR.new"
mkdir -p "$INSTALL_DIR.new"
cp -a "$SRC_DIR"/. "$INSTALL_DIR.new"/
chmod +x "$INSTALL_DIR.new/bin/vfops" "$INSTALL_DIR.new/bin/vfops-user"

HAD_PREVIOUS=0
if [[ -e "$INSTALL_DIR" ]]; then
  HAD_PREVIOUS=1
  rm -rf "$PREVIOUS_DIR"
  mv "$INSTALL_DIR" "$PREVIOUS_DIR"
fi
mv "$INSTALL_DIR.new" "$INSTALL_DIR"
ln -sfn "$INSTALL_DIR/bin/vfops-user" "$BIN_LINK"

rollback_install() {
  say "新版本自检未通过，正在自动恢复安装前版本..."
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
if [[ "$VERSION_OUT" != "VF Server Ops 0.1.0 RC2" ]]; then
  rollback_install
  fail "版本自检不匹配；未保留失败的新版本。"
fi
SELFTEST_JSON="$TMP_DIR/inventory.json"
if ! $BIN_LINK inventory --compact > "$SELFTEST_JSON" 2>/dev/null; then
  rollback_install
  fail "服务器检查自检失败；未保留失败的新版本。"
fi
if ! python3 - "$SELFTEST_JSON" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
if p.get('schema') != 'vf-server-ops.inventory.v1':
    raise SystemExit(1)
PY
then
  rollback_install
  fail "Inventory 结果自检失败；未保留失败的新版本。"
fi

say "安装完成 ✓"
printf '版本：%s\n' "$VERSION_OUT"
printf '以后只需要输入：vfops\n'
printf '升级也继续使用同一条 p07.sh 安装命令。\n'
printf 'P07 不会自动改 DNS，也不会自动删除旧服务器。\n'

if [[ -t 0 && -t 1 ]]; then
  printf '\n正在进入 P07...\n'
  exec "$BIN_LINK"
fi
