#!/usr/bin/env bash
set -euo pipefail

C_RESET=''; C_BOLD=''; C_CYAN=''; C_GREEN=''; C_YELLOW=''; C_RED=''; C_BLUE=''; C_GRAY=''
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_CYAN=$'\033[36m'; C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BLUE=$'\033[34m'; C_GRAY=$'\033[90m'
fi

say() { printf '%b\n' "$*"; }
warn() { say "${C_YELLOW}$*${C_RESET}"; }
fail() { say "${C_RED}$*${C_RESET}" >&2; }
ok() { say "${C_GREEN}$*${C_RESET}"; }
info() { say "${C_CYAN}$*${C_RESET}"; }

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    fail '此操作需要 root 权限。'
    return 77
  fi
}

confirm_numeric() {
  local prompt="${1:-确认执行？}"
  [[ -t 0 ]] || { fail '需要交互式终端确认，已停止。'; return 78; }
  printf '%s\n\n1. 确认\n0. 取消\n\n请选择 [0-1]：' "$prompt"
  local choice
  read -r choice || return 78
  [[ "$choice" == 1 ]] || return 79
}

pause_menu() {
  [[ -t 0 ]] || return 0
  printf '\n按 Enter 返回...'
  read -r _ || true
}

cloudpanel_present() {
  command -v clpctl >/dev/null 2>&1 || [[ -d /home/clp ]] || [[ -d /etc/cloudpanel ]]
}

cloudpanel_label() {
  cloudpanel_present && printf '已检测' || printf '未检测'
}

pkg_manager() {
  if command -v apt-get >/dev/null 2>&1; then printf 'apt'
  elif command -v dnf >/dev/null 2>&1; then printf 'dnf'
  elif command -v yum >/dev/null 2>&1; then printf 'yum'
  else printf 'unknown'; fi
}

human_bytes_kb() {
  local kb="${1:-0}"
  if command -v numfmt >/dev/null 2>&1; then numfmt --to=iec --suffix=B "$((kb * 1024))" 2>/dev/null || printf '%s KB' "$kb"
  else printf '%s KB' "$kb"; fi
}

failed_unit_count() {
  command -v systemctl >/dev/null 2>&1 || { printf '0'; return; }
  { systemctl --failed --no-legend --plain 2>/dev/null || true; } | awk 'NF {n++} END {print n+0}'
}

root_disk_pct() {
  df -P / 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5+0}'
}

root_inode_pct() {
  df -Pi / 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5+0}'
}

apt_upgradable_count() {
  command -v apt >/dev/null 2>&1 || { printf 'UNKNOWN'; return; }
  apt list --upgradable 2>/dev/null | awk 'NR>1 && NF {n++} END {print n+0}'
}

apt_security_count() {
  command -v apt-get >/dev/null 2>&1 || { printf 'UNKNOWN'; return; }
  apt-get -s -o Debug::NoLocking=true upgrade 2>/dev/null | awk '/^Inst / && /[Ss]ecurity/ {n++} END {print n+0}'
}

cache_file_for() {
  local name="$1" uid="${EUID:-$(id -u)}"
  printf '/tmp/p07-system-care-%s-%s.cache\n' "$name" "$uid"
}

write_kv_cache() {
  local name="$1"; shift
  local file tmp item
  file="$(cache_file_for "$name")"
  tmp="${file}.tmp.$$"
  umask 077
  : > "$tmp" 2>/dev/null || return 0
  for item in "$@"; do printf '%s\n' "$item" >> "$tmp" || true; done
  mv -f "$tmp" "$file" 2>/dev/null || { rm -f "$tmp" 2>/dev/null || true; return 0; }
}

cached_kv() {
  local name="$1" key="$2" file value
  file="$(cache_file_for "$name")"
  [[ -r "$file" ]] || { printf 'UNKNOWN'; return 0; }
  value="$(awk -F= -v k="$key" '$1==k {print $2; exit}' "$file" 2>/dev/null || true)"
  [[ -n "$value" ]] && printf '%s' "$value" || printf 'UNKNOWN'
}

write_update_cache() {
  local updates="${1:-UNKNOWN}" security="${2:-UNKNOWN}"
  write_kv_cache updates \
    "UPDATES=${updates}" \
    "SECURITY=${security}" \
    "UPDATED_AT=$(date +%s 2>/dev/null || printf 0)"
}

cached_update_value() { cached_kv updates "$1"; }

write_summary_cache() {
  local health="${1:-UNKNOWN}" disk="${2:-UNKNOWN}" inode="${3:-UNKNOWN}" failed="${4:-UNKNOWN}" reboot="${5:-UNKNOWN}" cp="${6:-UNKNOWN}"
  write_kv_cache summary \
    "STATUS=${health}" \
    "DISK=${disk}" \
    "INODE=${inode}" \
    "FAILED=${failed}" \
    "REBOOT=${reboot}" \
    "CLOUDPANEL=${cp}" \
    "UPDATED_AT=$(date +%s 2>/dev/null || printf 0)"
}

cached_summary_value() { cached_kv summary "$1"; }

reboot_required() { [[ -f /var/run/reboot-required ]]; }
