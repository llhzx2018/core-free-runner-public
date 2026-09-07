#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

say "${C_BOLD}P07 · SSH / 安全检查${C_RESET}"
say

if command -v sshd >/dev/null 2>&1; then
  effective="$(sshd -T 2>/dev/null || true)"
  port="$(awk '$1=="port" {print $2; exit}' <<<"$effective")"; port="${port:-UNKNOWN}"
  root="$(awk '$1=="permitrootlogin" {print $2; exit}' <<<"$effective")"; root="${root:-UNKNOWN}"
  pass="$(awk '$1=="passwordauthentication" {print $2; exit}' <<<"$effective")"; pass="${pass:-UNKNOWN}"
  printf 'SSH 端口       %s\n' "$port"
  printf 'Root 登录      %s\n' "$root"
  printf '密码认证       %s\n' "$pass"
else
  printf 'SSH            未检测到 sshd / 无法读取\n'
fi

if command -v ufw >/dev/null 2>&1; then
  printf '防火墙         UFW %s\n' "$(ufw status 2>/dev/null | awk -F': ' '/^Status:/ {print $2; exit}' || printf UNKNOWN)"
elif command -v firewall-cmd >/dev/null 2>&1; then
  printf '防火墙         firewalld %s\n' "$(firewall-cmd --state 2>/dev/null || printf UNKNOWN)"
elif command -v nft >/dev/null 2>&1 && nft list ruleset >/dev/null 2>&1; then
  printf '防火墙         nftables 已有规则\n'
else
  printf '防火墙         未检测到常见活动规则\n'
fi

if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet fail2ban 2>/dev/null; then
  printf 'Fail2ban       运行中\n'
elif command -v fail2ban-client >/dev/null 2>&1; then
  printf 'Fail2ban       已安装但未运行\n'
else
  printf 'Fail2ban       未安装\n'
fi

printf 'CloudPanel     %s\n' "$(cloudpanel_label)"
security="$(apt_security_count)"
write_update_cache "$(cached_update_value UPDATES)" "$security"
printf '安全更新       %s\n' "$security"
say
say '当前监听端口：'
if command -v ss >/dev/null 2>&1; then
  ss -lntupH 2>/dev/null | awk '{print "  "$1" "$5" "$7}' | head -n 30 || true
else
  warn '没有 ss，无法列出监听端口。'
fi
say
say "${C_GRAY}当前安全模块只检查，不修改 SSH、防火墙、Fail2ban 或 CloudPanel 规则。发现风险后给出证据，不为了“得分”自动改服务器。${C_RESET}"
