#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

say "${C_BOLD}P07 · 服务异常诊断${C_RESET}"
say
if ! command -v systemctl >/dev/null 2>&1; then
  warn '当前系统没有 systemctl。'
  exit 0
fi

mapfile -t units < <({ systemctl --failed --no-legend --plain 2>/dev/null || true; } | awk 'NF {print $1}')
if [[ ${#units[@]} -eq 0 ]]; then
  ok '没有 failed systemd unit。'
  exit 0
fi

warn "发现 ${#units[@]} 个异常服务："
for i in "${!units[@]}"; do printf '%d. %s\n' "$((i+1))" "${units[$i]}"; done
printf '0. 返回\n'

[[ -t 0 ]] || exit 0
say
printf '选择查看最近错误 [0-%d]：' "${#units[@]}"
read -r choice || exit 0
[[ "$choice" =~ ^[0-9]+$ ]] || exit 0
[[ "$choice" -ge 1 && "$choice" -le "${#units[@]}" ]] || exit 0
unit="${units[$((choice-1))]}"
say
systemctl status "$unit" --no-pager -l 2>/dev/null | tail -n 20 || true
say
journalctl -u "$unit" -n 30 --no-pager 2>/dev/null || true
say
if [[ "$unit" =~ nginx|apache|php|mysql|mariadb|redis|cloudpanel|clp ]]; then
  warn '该服务可能属于 CloudPanel / 网站运行栈。P07 RC3 只诊断，不改面板配置，也不自动重启。'
else
  say "${C_GRAY}P07 RC3 只诊断异常服务，不自动重启任何服务。${C_RESET}"
fi
