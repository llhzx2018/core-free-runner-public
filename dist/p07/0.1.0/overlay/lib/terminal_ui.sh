#!/usr/bin/env bash
# P07 Terminal UI Color System
# Canonical semantics are defined in docs/authority/RPD.md.

C_RESET=''; C_BOLD=''; C_CYAN=''; C_GREEN=''; C_YELLOW=''; C_RED=''; C_MAGENTA=''; C_GRAY=''
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_RESET='\033[0m'; C_BOLD='\033[1m'; C_CYAN='\033[36m'; C_GREEN='\033[32m'
  C_YELLOW='\033[33m'; C_RED='\033[31m'; C_MAGENTA='\033[35m'; C_GRAY='\033[90m'
fi

say() { printf '%b\n' "$*"; }
ui_title() { say "${C_BOLD}${C_CYAN}$*${C_RESET}"; }
ui_rule() { say "${C_GRAY}──────────────────────────────────────────────────────────────${C_RESET}"; }
ui_menu_good() { say "  ${C_GREEN}$1.${C_RESET} $2"; }
ui_menu_info() { say "  ${C_CYAN}$1.${C_RESET} $2"; }
ui_menu_warn() { say "  ${C_YELLOW}$1.${C_RESET} $2"; }
ui_menu_danger() { say "  ${C_RED}$1.${C_RESET} $2"; }
ui_menu_flow() { say "  ${C_MAGENTA}$1.${C_RESET} $2"; }
ui_menu_back() { say "  ${C_GRAY}$1.${C_RESET} $2"; }
ui_note() { say "${C_GRAY}$*${C_RESET}"; }
ui_good() { say "${C_GREEN}$*${C_RESET}"; }
ui_attention() { say "${C_YELLOW}$*${C_RESET}"; }
ui_warn() { ui_attention "$@"; }
ui_bad() { say "${C_RED}$*${C_RESET}"; }
ui_flow() { say "${C_MAGENTA}$*${C_RESET}"; }
ui_safe_diagnostic() {
  local raw="${1:-}" diag stage blocker
  diag="$(printf '%s\n' "$raw" | grep '^VFOPS_DIAGNOSTIC_V1 ' | tail -n1 || true)"
  [[ -n "$diag" ]] || return 1
  stage="$(printf '%s\n' "$diag" | sed -n 's/.* stage=\([A-Z0-9_]*\).*/\1/p')"
  blocker="$(printf '%s\n' "$diag" | sed -n 's/.* blocker=\([A-Z0-9_+-]*\).*/\1/p')"
  [[ -n "$stage" ]] && ui_note "阶段：$stage"
  [[ -n "$blocker" ]] && ui_note "原因代码：$blocker"
  return 0
}
ui_prompt() { printf '%b' "${C_BOLD}$*${C_RESET}"; }
