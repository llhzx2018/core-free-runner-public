#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

say "${C_BOLD}P07 · 内存 / Swap / OOM${C_RESET}"
say
free -h 2>/dev/null || true
say
if command -v swapon >/dev/null 2>&1; then
  swapon --show 2>/dev/null || true
fi
say
say '内存占用最高进程：'
ps -eo pid,user,comm,%mem,%cpu --sort=-%mem 2>/dev/null | head -n 8 || true
say
if command -v journalctl >/dev/null 2>&1; then
  if journalctl -k -b --no-pager 2>/dev/null | grep -Eqi 'Out of memory|oom-kill|Killed process'; then
    warn '本次启动检测到 OOM / 内核终止进程证据：'
    journalctl -k -b --no-pager 2>/dev/null | grep -Ei 'Out of memory|oom-kill|Killed process' | tail -n 8 || true
  else
    ok '本次启动未发现 OOM 证据。'
  fi
else
  warn '无法读取 journal，OOM 状态未知。'
fi
say
say "${C_GRAY}当前版本只诊断内存/Swap，不自动创建 Swap，也不自动 kill 应用进程。${C_RESET}"
