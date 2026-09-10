#!/usr/bin/env bash
set -euo pipefail

PUBLIC_ROOT="${P07_PUBLIC_ROOT:-https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main}"
INSTALLER_URL="${PUBLIC_ROOT}/installers/p07-rc3-candidate.sh"
EXPECTED_BLOB="b1ea8c123d3614e4da5096c27365e06c0bae5886"

fail() { printf '\n[P07] ERROR: %s\n' "$*" >&2; exit 1; }

if ! command -v curl >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  if [[ ${EUID:-$(id -u)} -eq 0 ]] && command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y curl python3
  fi
fi

command -v curl >/dev/null 2>&1 || fail "缺少依赖：curl"
command -v python3 >/dev/null 2>&1 || fail "缺少依赖：python3"

TMP="$(mktemp -t p07-server-ops.XXXXXX)"
trap 'rm -f "$TMP"' EXIT

curl -fsSL --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 15 "$INSTALLER_URL" -o "$TMP" || fail "CloudPanel 运维模块安装器下载失败。"
bash -n "$TMP" || fail "CloudPanel 运维模块安装器语法校验失败。"

python3 - "$TMP" "$EXPECTED_BLOB" <<'PY' || fail "CloudPanel 运维模块安装器身份校验失败。"
import hashlib,sys
path,expected=sys.argv[1],sys.argv[2]
data=open(path,'rb').read()
actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
if actual != expected:
    print(f'installer blob mismatch: {actual} != {expected}', file=sys.stderr)
    raise SystemExit(1)
PY

P07_TOOLBOX_PARENT="${P07_TOOLBOX_PARENT:-0}" bash "$TMP" "$@"
