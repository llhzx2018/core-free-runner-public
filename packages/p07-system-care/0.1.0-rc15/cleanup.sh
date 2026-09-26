#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

apt_cache_kb() {
  [[ -d /var/cache/apt/archives ]] || { printf '0'; return; }
  { du -sk /var/cache/apt/archives 2>/dev/null || true; } | awk 'NF {print $1+0; found=1} END {if (!found) print 0}'
}

journal_usage() {
  command -v journalctl >/dev/null 2>&1 || { printf 'UNKNOWN'; return; }
  journalctl --disk-usage 2>/dev/null | sed -E 's/^Archived and active journals take up //; s/\.$//' || printf 'UNKNOWN'
}

scan() {
  info '正在扫描可清理空间，请稍候...'
  local kb
  kb="$(apt_cache_kb)"
  printf 'APT 缓存     %s\n' "$(human_bytes_kb "$kb")"
  printf 'systemd 日志 %s\n' "$(journal_usage)"
  printf '根分区       %s%%\n' "$(root_disk_pct)"
  say
  say "${C_GRAY}只清理 OS 明确拥有的缓存/Journal；不会删除网站、数据库、SSL、备份或任意大文件。${C_RESET}"
}

clean_apt() {
  require_root
  command -v apt-get >/dev/null 2>&1 || { fail '没有 apt-get，无法清理 APT 缓存。'; return 65; }
  confirm_numeric '清理 APT 下载缓存？' || { warn '已取消。'; return 0; }
  local before after
  before="$(apt_cache_kb)"; apt-get clean; after="$(apt_cache_kb)"
  ok "APT 缓存已清理：$(human_bytes_kb "$before") -> $(human_bytes_kb "$after")"
}

clean_journal() {
  require_root
  command -v journalctl >/dev/null 2>&1 || { fail '没有 journalctl。'; return 65; }
  confirm_numeric '将 systemd journal 保留最近 14 天；不删除 CloudPanel 网站日志。' || { warn '已取消。'; return 0; }
  journalctl --vacuum-time=14d
  ok 'systemd journal 清理完成。'
}

case "${1:-menu}" in
  scan|status|check) scan ;;
  apt) clean_apt ;;
  journal) clean_journal ;;
  menu)
    while true; do
      screen_clear
      say "${C_BOLD}P07 · 磁盘 / 日志清理${C_RESET}"; say
      say '1. 扫描可清理空间'
      say '2. 清理 APT 缓存'
      say '3. 清理旧 systemd 日志（保留 14 天）'
      say '0. 返回'; say
      printf '请选择 [0-3]：'; read -r choice || exit 0
      case "$choice" in
        1) scan; pause_menu ;;
        2) clean_apt; pause_menu ;;
        3) clean_journal; pause_menu ;;
        0) exit 0 ;;
        *) warn '无效选择。'; sleep 1 ;;
      esac
    done
    ;;
  *) fail "未知清理命令: $1"; exit 2 ;;
esac
