#!/usr/bin/env bash
set -Eeuo pipefail
# Shared globals are consumed by scripts that source this file.
# shellcheck disable=SC2034

VF_NODE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
VF_NODE_VERSION="$(tr -d '\r\n' < "$VF_NODE_ROOT/VERSION" 2>/dev/null || printf 'UNKNOWN')"
VF_NODE_STATE_DIR="/etc/vf-node"
VF_NODE_STATE_FILE="$VF_NODE_STATE_DIR/state.env"
VF_NODE_BACKUP_DIR="/root/vf-node-backups"

if [[ -t 1 && "${NO_COLOR:-0}" != "1" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'
  C_RED=$'\033[91m'; C_GREEN=$'\033[92m'; C_YELLOW=$'\033[93m'
  C_BLUE=$'\033[94m'; C_MAGENTA=$'\033[95m'; C_CYAN=$'\033[96m'; C_GRAY=$'\033[90m'
else
  C_RESET=''; C_BOLD=''; C_RED=''; C_GREEN=''; C_YELLOW=''; C_BLUE=''; C_MAGENTA=''; C_CYAN=''; C_GRAY=''
fi

say()      { printf '%b\n' "$*"; }
info()     { say "${C_CYAN}●${C_RESET} $*"; }
ok()       { say "${C_GREEN}✓${C_RESET} $*"; }
warn()     { say "${C_YELLOW}⚠${C_RESET} $*"; }
fail()     { say "${C_RED}✗${C_RESET} $*" >&2; }
section()  { say "\n${C_BOLD}${C_CYAN}$*${C_RESET}"; }

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    fail "请使用 root 运行。"
    exit 1
  fi
}

pause_if_tty() {
  [[ -t 0 ]] || return 0
  printf '\n按 Enter 继续...'
  read -r _ || true
}

v2ray_cli() {
  if command -v v2ray >/dev/null 2>&1; then
    command -v v2ray
  elif [[ -x /usr/local/sbin/v2ray ]]; then
    printf '%s\n' /usr/local/sbin/v2ray
  else
    return 1
  fi
}

# The historical `v2ray url` command may print banners/tutorial/promotional
# text around the useful result. P07 treats that command as a compatibility
# data source only and emits the vmess:// token itself as the product output.
print_vmess_url() {
  local cli raw url
  cli="$(v2ray_cli || true)"
  if [[ -z "$cli" ]]; then
    fail "没有找到 V2Ray 分享配置命令。"
    return 1
  fi

  raw="$("$cli" url 2>&1 || true)"
  url="$(printf '%s\n' "$raw" | LC_ALL=C grep -oE 'vmess://[A-Za-z0-9+/=_-]+' | head -n1 || true)"
  if [[ -z "$url" ]]; then
    fail "没有从节点配置中生成 vmess:// 分享链接。"
    return 1
  fi

  printf '%s\n' "$url"
}

service_active() {
  command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet v2ray.service
}

load_state() {
  PROFILE=''; PORT=''; SOURCE_REPO=''; SOURCE_COMMIT=''; INSTALLED_AT=''
  CORE_VERSION=''; CORE_ASSET=''; CORE_SHA256=''
  if [[ -r "$VF_NODE_STATE_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$VF_NODE_STATE_FILE"
  fi
}

ensure_state_dir() {
  install -d -m 0700 "$VF_NODE_STATE_DIR"
}

pkg_install() {
  local pkgs=("$@")
  if command -v apt-get >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}" >/dev/null 2>&1 || {
      apt-get update >/dev/null
      DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}"
    }
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y "${pkgs[@]}"
  elif command -v yum >/dev/null 2>&1; then
    yum install -y "${pkgs[@]}"
  else
    fail "不支持的包管理器。"
    return 1
  fi
}

ensure_dependencies() {
  local missing=()
  command -v curl >/dev/null 2>&1 || missing+=(curl)
  command -v git >/dev/null 2>&1 || missing+=(git)
  command -v tar >/dev/null 2>&1 || missing+=(tar)
  command -v python3 >/dev/null 2>&1 || missing+=(python3)
  command -v sha256sum >/dev/null 2>&1 || missing+=(coreutils)
  if ((${#missing[@]})); then
    info "安装必要依赖：${missing[*]}"
    pkg_install "${missing[@]}"
  fi
  if ! command -v ss >/dev/null 2>&1; then
    info "安装网络检查工具..."
    if command -v apt-get >/dev/null 2>&1; then
      pkg_install iproute2
    else
      pkg_install iproute
    fi
  fi
}

valid_port() {
  local p="$1"
  [[ "$p" =~ ^[0-9]+$ ]] && ((1 <= p && p <= 65535))
}

port_in_use_udp() {
  local port="$1"
  command -v ss >/dev/null 2>&1 || return 1
  # With `ss -H -lun`, local-address:port is field 4. Field 5 is the peer.
  ss -H -lun 2>/dev/null | awk -v p="$port" '$4 ~ (":" p "$") { found=1 } END { exit !found }'
}

random_free_udp_port() {
  local p
  for _ in {1..40}; do
    p=$(shuf -i 20001-60000 -n 1)
    if ! port_in_use_udp "$p"; then
      printf '%s\n' "$p"
      return 0
    fi
  done
  return 1
}

exact_confirm() {
  local expected="$1" prompt="$2" got=''
  printf '%b' "${C_YELLOW}${prompt}${C_RESET}\n输入 ${C_BOLD}${expected}${C_RESET} 继续："
  read -r got || true
  [[ "$got" == "$expected" ]]
}
