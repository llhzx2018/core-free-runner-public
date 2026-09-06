#!/usr/bin/env bash
set -euo pipefail

REPO="llhzx2018/vf-server-ops"
REF="candidate-p07-v0.1.0-rc1"
INSTALL_DIR="/opt/vf-server-ops"
BIN_LINK="/usr/local/bin/vfops"
API_URL="https://api.github.com/repos/${REPO}/tarball/${REF}"

say() { printf '\n[P07] %s\n' "$*"; }
fail() { printf '\n[P07] ERROR: %s\n' "$*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] || fail "请使用 root 运行。"

if command -v apt-get >/dev/null 2>&1; then
  missing=()
  command -v curl >/dev/null 2>&1 || missing+=(curl)
  command -v tar >/dev/null 2>&1 || missing+=(tar)
  command -v python3 >/dev/null 2>&1 || missing+=(python3)
  if ((${#missing[@]})); then
    say "安装依赖：${missing[*]}"
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
  fi
fi

for cmd in curl tar python3; do
  command -v "$cmd" >/dev/null 2>&1 || fail "缺少依赖：$cmd"
done

TOKEN="${GITHUB_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
  printf 'P07 当前为 Private Candidate。请输入可读取 llhzx2018/vf-server-ops 的 GitHub Token（输入不回显）：'
  IFS= read -r -s TOKEN
  printf '\n'
fi
[[ -n "$TOKEN" ]] || fail "没有提供 GitHub Token。"

TMP_DIR="$(mktemp -d -t p07-install.XXXXXX)"
trap 'rm -rf "$TMP_DIR"; unset TOKEN GITHUB_TOKEN || true' EXIT
ARCHIVE="$TMP_DIR/p07.tar.gz"

say "下载 P07 0.1.0 RC1..."
HTTP_CODE="$(curl -sS -L \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -o "$ARCHIVE" \
  -w '%{http_code}' \
  "$API_URL")"
[[ "$HTTP_CODE" == "200" ]] || fail "下载失败（HTTP $HTTP_CODE）。请确认 Token 对 Private 仓库有 Contents: Read。"

tar -tzf "$ARCHIVE" >/dev/null 2>&1 || fail "下载包不是有效 tar.gz。"
mkdir -p "$TMP_DIR/src"
tar -xzf "$ARCHIVE" -C "$TMP_DIR/src"
SRC_DIR="$(find "$TMP_DIR/src" -mindepth 1 -maxdepth 1 -type d | head -n1)"
[[ -n "$SRC_DIR" && -f "$SRC_DIR/bin/vfops" ]] || fail "Candidate 包结构异常。"

say "安装到 $INSTALL_DIR ..."
rm -rf "$INSTALL_DIR.new"
mkdir -p "$INSTALL_DIR.new"
cp -a "$SRC_DIR"/. "$INSTALL_DIR.new"/
chmod +x "$INSTALL_DIR.new/bin/vfops"
python3 -m py_compile "$INSTALL_DIR.new"/lib/*.py

if [[ -e "$INSTALL_DIR" ]]; then
  rm -rf "$INSTALL_DIR.previous"
  mv "$INSTALL_DIR" "$INSTALL_DIR.previous"
fi
mv "$INSTALL_DIR.new" "$INSTALL_DIR"
ln -sfn "$INSTALL_DIR/bin/vfops" "$BIN_LINK"

say "安装完成。"
printf '版本：'; "$BIN_LINK" --version || true
printf '\n现在直接运行：\n\n  vfops\n\n'
printf '首次建议：1 服务器检查 -> 2 网站备份 -> 5 备份/恢复验证。\n'
printf 'P07 不会自动改 DNS，也不会自动删除旧服务器。\n'
