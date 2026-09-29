#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR="${P07_INSTALL_DIR:-/opt/vf-server-ops}"
PREVIOUS_DIR="${P07_PREVIOUS_DIR:-/opt/vf-server-ops.previous}"
BIN_LINK="${P07_BIN_LINK:-/usr/local/bin/vfops}"
PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"

BASE_URL="${PUBLIC_ROOT}/dist/p07/0.1.0-rc2"
BASE_PACKAGE="P07_VF_SERVER_OPS_0.1.0-rc2.tar.gz"
BASE_SHA256="de28a5e9dada500357be725e78e9e5cbacd51d26f1ec9bbb55ff92d21d49ada5"
RUNTIME_URL="${PUBLIC_ROOT}/dist/p07/0.1.0/overlay"
RUNTIME_MANIFEST_BLOB="43c88e83ae8f1325395086b9225bd0b9decfacdd"

EXPECTED_VERSION="VF Server Ops 0.1.0"
EXPECTED_BUILD_ID="0.1.0-release4"

say() { printf '\n[P07] %s\n' "$*"; }
fail() { printf '\n[P07] 错误：%s\n' "$*" >&2; exit 1; }

verify_git_blob() {
  local file="$1" expected="$2"
  python3 - "$file" "$expected" <<'PY'
import hashlib,sys
path,expected=sys.argv[1:]
data=open(path,'rb').read()
actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
if actual != expected:
    print(f'文件身份不匹配：{path}', file=sys.stderr)
    raise SystemExit(1)
PY
}

verify_tree_from_manifest() {
  local root="$1" manifest="$2" expected path
  while read -r expected path; do
    [[ -n "$expected" && -n "$path" ]] || continue
    [[ -f "$root/$path" ]] || return 1
    verify_git_blob "$root/$path" "$expected" >/dev/null 2>&1 || return 1
  done < "$manifest"
}

verify_installed_current() {
  [[ -x "$BIN_LINK" ]] || return 1
  [[ -f "$INSTALL_DIR/.runtime-manifest.gitblob" ]] || return 1
  verify_git_blob "$INSTALL_DIR/.runtime-manifest.gitblob" "$RUNTIME_MANIFEST_BLOB" >/dev/null 2>&1 || return 1
  [[ "$(NO_COLOR=1 "$BIN_LINK" --version 2>/dev/null || true)" == "$EXPECTED_VERSION" ]] || return 1
  [[ "$(NO_COLOR=1 "$BIN_LINK" --build-id 2>/dev/null || true)" == "$EXPECTED_BUILD_ID" ]] || return 1
  verify_tree_from_manifest "$INSTALL_DIR" "$INSTALL_DIR/.runtime-manifest.gitblob"
}

if verify_installed_current; then
  say "CloudPanel 运维模块已是当前版本，无需下载或重复安装 ✓"
  if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then exec "$BIN_LINK"; fi
  exit 0
fi

if [[ "${P07_ALLOW_NONROOT:-0}" != "1" ]]; then
  [[ ${EUID:-$(id -u)} -eq 0 ]] || fail "请使用 root 运行。"
fi

missing=()
command -v curl >/dev/null 2>&1 || missing+=(curl)
command -v tar >/dev/null 2>&1 || missing+=(tar)
command -v python3 >/dev/null 2>&1 || missing+=(python3)
command -v sha256sum >/dev/null 2>&1 || missing+=(coreutils)
if (("${#missing[@]}")); then
  command -v apt-get >/dev/null 2>&1 || fail "缺少安装所需基础工具：${missing[*]}"
  say "按需安装当前安装过程必需的基础工具：${missing[*]}"
  apt-get update -y >/dev/null
  DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}" >/dev/null
fi
for cmd in curl tar python3 sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || fail "缺少基础工具：$cmd"
done

TMP_DIR="$(mktemp -d -t p07-current.XXXXXX)"
NEW_DIR="${INSTALL_DIR}.new"
COMMITTED=0

cleanup() {
  local rc=$?
  trap - EXIT
  rm -rf "$TMP_DIR" "$NEW_DIR" 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT

say "下载当前正式运行时..."
curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15   "${BASE_URL}/${BASE_PACKAGE}" -o "$TMP_DIR/base.tar.gz" || fail "基础运行包下载失败。"
printf '%s  %s\n' "$BASE_SHA256" "$TMP_DIR/base.tar.gz" | sha256sum -c - >/dev/null || fail "基础运行包校验失败。"
tar -tzf "$TMP_DIR/base.tar.gz" >/dev/null 2>&1 || fail "基础运行包格式异常。"
mkdir -p "$TMP_DIR/extracted"
tar -xzf "$TMP_DIR/base.tar.gz" -C "$TMP_DIR/extracted"
SRC_DIR="$TMP_DIR/extracted/vf-server-ops"
[[ -f "$SRC_DIR/VERSION" && -f "$SRC_DIR/bin/vfops" ]] || fail "基础运行包结构异常。"

curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15   "${RUNTIME_URL}/RUNTIME.gitblob" -o "$TMP_DIR/RUNTIME.gitblob" || fail "当前运行时清单下载失败。"
verify_git_blob "$TMP_DIR/RUNTIME.gitblob" "$RUNTIME_MANIFEST_BLOB" || fail "当前运行时清单身份校验失败。"

while read -r expected path; do
  [[ -n "$expected" && -n "$path" ]] || continue
  case "$path" in
    /*|../*|*/../*|*/..) fail "运行时清单包含非法路径：$path" ;;
  esac
  mkdir -p "$SRC_DIR/$(dirname "$path")"
  curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15     "${RUNTIME_URL}/${path}" -o "$SRC_DIR/$path" || fail "当前运行时文件下载失败：$path"
  verify_git_blob "$SRC_DIR/$path" "$expected" || fail "当前运行时文件身份校验失败：$path"
done < "$TMP_DIR/RUNTIME.gitblob"
cp "$TMP_DIR/RUNTIME.gitblob" "$SRC_DIR/.runtime-manifest.gitblob"
chmod 0644 "$SRC_DIR/.runtime-manifest.gitblob"

say "执行轻量安装前自检..."
for file in "$SRC_DIR"/bin/* "$SRC_DIR"/lib/cloudpanel_ui_*.sh "$SRC_DIR"/lib/terminal_ui.sh; do
  [[ -f "$file" ]] || continue
  bash -n "$file"
done
chmod +x "$SRC_DIR"/bin/*
python3 -m py_compile "$SRC_DIR"/lib/*.py
find "$SRC_DIR/lib" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
[[ "$(NO_COLOR=1 bash "$SRC_DIR/bin/vfops-user" --version)" == "$EXPECTED_VERSION" ]] || fail "版本自检失败。"
[[ "$(NO_COLOR=1 bash "$SRC_DIR/bin/vfops-user" --build-id)" == "$EXPECTED_BUILD_ID" ]] || fail "构建身份自检失败。"
verify_tree_from_manifest "$SRC_DIR" "$TMP_DIR/RUNTIME.gitblob" || fail "运行时完整性自检失败。"

say "安装当前版本..."
rm -rf "$NEW_DIR"
mkdir -p "$NEW_DIR"
cp -a "$SRC_DIR"/. "$NEW_DIR"/

if [[ -e "$INSTALL_DIR" ]]; then
  rm -rf "$PREVIOUS_DIR"
  mv "$INSTALL_DIR" "$PREVIOUS_DIR"
fi
mv "$NEW_DIR" "$INSTALL_DIR"
mkdir -p "$(dirname "$BIN_LINK")"
ln -sfn "$INSTALL_DIR/bin/vfops-user" "$BIN_LINK"

if ! verify_installed_current; then
  say "安装后自检未通过，正在恢复安装前版本..."
  rm -rf "$INSTALL_DIR"
  if [[ -e "$PREVIOUS_DIR" ]]; then
    mv "$PREVIOUS_DIR" "$INSTALL_DIR"
    ln -sfn "$INSTALL_DIR/bin/vfops-user" "$BIN_LINK"
  else
    rm -f "$BIN_LINK"
  fi
  fail "已回滚，未保留不完整的新版本。"
fi

COMMITTED=1
say "CloudPanel 运维模块安装 / 升级完成 ✓"
printf '版本：%s\n' "$EXPECTED_VERSION"
printf 'Build：%s\n' "$EXPECTED_BUILD_ID"
printf '加载方式：只安装 Slot 3 当前运行时，不回放历史 RC / guided-init 安装链。\n'
printf '按需依赖：远程备份进入时才安装 rclone；服务器迁移进入时才安装 OpenSSH 客户端。\n'
printf '安全边界：不自动改 DNS、不自动删除源服务器、不自动覆盖已有目标服务器。\n'

if [[ -t 0 && -t 1 && "${P07_NO_EXEC:-0}" != "1" ]]; then
  exec "$BIN_LINK"
fi
