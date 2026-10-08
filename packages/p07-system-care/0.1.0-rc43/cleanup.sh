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
  command -v journalctl >/dev/null 2>&1 || { printf '未知'; return; }
  journalctl --disk-usage 2>/dev/null | sed -E 's/^Archived and active journals take up //; s/\.$//' || printf '未知'
}

scan() {
  info '正在扫描可清理空间，请稍候...'
  local kb
  kb="$(apt_cache_kb)"
  printf '软件安装缓存 %s\n' "$(human_bytes_kb "$kb")"
  printf '系统运行日志 %s\n' "$(journal_usage)"
  printf '根分区       %s%%\n' "$(root_disk_pct)"
  say
  ui_note '只清理系统缓存及旧日志；网站、数据库、证书和备份均不删除。'
}

clean_apt() {
  require_root
  command -v apt-get >/dev/null 2>&1 || { fail '没有 apt-get，无法清理 APT 缓存。'; return 65; }
  if [[ "${P07_CLEANUP_CONFIRMED:-0}" != 1 ]]; then
    confirm_numeric '清理软件安装缓存？' || { warn '已取消。'; return 0; }
  fi
  local before after
  before="$(apt_cache_kb)"; apt-get clean; after="$(apt_cache_kb)"
  ok "软件缓存清理：$(human_bytes_kb "$before") → $(human_bytes_kb "$after")"
}

clean_journal() {
  require_root
  command -v journalctl >/dev/null 2>&1 || { fail '没有 journalctl。'; return 65; }
  if [[ "${P07_CLEANUP_CONFIRMED:-0}" != 1 ]]; then
    confirm_numeric '保留最近 14 天的系统运行日志？不删除网站日志。' || { warn '已取消。'; return 0; }
  fi
  journalctl --vacuum-time=14d
  ok '旧系统日志已清理。'
}


clean_safe() {
  require_root
  scan
  say
  confirm_numeric '清理软件安装缓存，并把系统运行日志保留最近 14 天？' || { warn '已取消。'; return 0; }
  P07_CLEANUP_CONFIRMED=1 clean_apt
  P07_CLEANUP_CONFIRMED=1 clean_journal
  say
  ui_good '清理完成；原网站和备份未改动。'
}

case "${1:-menu}" in
  scan|status|check) scan ;;
  safe) clean_safe ;;
  apt) clean_apt ;;
  journal) clean_journal ;;
  menu)
    while true; do
      screen_clear
      ui_title "磁盘空间清理"; say
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
