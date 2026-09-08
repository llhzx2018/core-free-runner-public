#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

say "${C_BOLD}P07 · SSH / 安全检查${C_RESET}"
say

risk_count=0
root='UNKNOWN'; pass='UNKNOWN'; firewall_label='UNKNOWN'; fail2ban_label='UNKNOWN'

if command -v sshd >/dev/null 2>&1; then
  effective="$(sshd -T 2>/dev/null || true)"
  port="$(awk '$1=="port" {print $2; exit}' <<<"$effective")"; port="${port:-UNKNOWN}"
  root="$(awk '$1=="permitrootlogin" {print $2; exit}' <<<"$effective")"; root="${root:-UNKNOWN}"
  pass="$(awk '$1=="passwordauthentication" {print $2; exit}' <<<"$effective")"; pass="${pass:-UNKNOWN}"
  printf 'SSH 端口       %s\n' "$port"
  printf 'Root 登录      %s\n' "$root"
  printf '密码认证       %s\n' "$pass"
  [[ "$root" == yes ]] && risk_count=$((risk_count+1))
  [[ "$pass" == yes ]] && risk_count=$((risk_count+1))
else
  printf 'SSH            未检测到 sshd / 无法读取\n'
fi

if command -v ufw >/dev/null 2>&1; then
  firewall_label="UFW $(ufw status 2>/dev/null | awk -F': ' '/^Status:/ {print $2; exit}' || printf UNKNOWN)"
  printf '防火墙         %s\n' "$firewall_label"
elif command -v firewall-cmd >/dev/null 2>&1; then
  firewall_label="firewalld $(firewall-cmd --state 2>/dev/null || printf UNKNOWN)"
  printf '防火墙         %s\n' "$firewall_label"
elif command -v nft >/dev/null 2>&1 && nft list ruleset >/dev/null 2>&1; then
  firewall_label='nftables 已有规则'
  printf '防火墙         %s\n' "$firewall_label"
else
  firewall_label='未检测到常见活动规则'
  printf '防火墙         %s\n' "$firewall_label"
fi

if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet fail2ban 2>/dev/null; then
  fail2ban_label='运行中'
elif command -v fail2ban-client >/dev/null 2>&1; then
  fail2ban_label='已安装但未运行'
else
  fail2ban_label='未安装'
fi
printf 'Fail2ban       %s\n' "$fail2ban_label"

printf 'CloudPanel     %s\n' "$(cloudpanel_label)"
security="$(cached_update_value SECURITY)"
[[ "$security" =~ ^[0-9]+$ ]] && printf '安全更新       %s\n' "$security" || printf '安全更新       未检查（请到“系统更新”检查）\n'
say

if (( risk_count == 0 )); then
  ok 'SSH 检查     当前没有发现 P07 明确标记的 SSH 高风险配置'
else
  warn "SSH 检查     发现 ${risk_count} 项需要你知情的配置"
  [[ "$root" == yes ]] && say '             - Root 可直接 SSH 登录'
  [[ "$pass" == yes ]] && say '             - SSH 允许密码认证'
  say '下一步       这里已经是风险详情页；当前版本不会自动改 SSH。'
  say '             如果以后提供“收紧 SSH”，必须先验证密钥登录可用并保留回滚，避免把你锁在服务器外。'
fi
say
say '当前监听端口：'
if command -v ss >/dev/null 2>&1; then
  ss -lntupH 2>/dev/null | awk '{print "  "$1" "$5" "$7}' | head -n 30 || true
else
  warn '没有 ss，无法列出监听端口。'
fi
say
say "${C_GRAY}此页只检查，不修改 SSH、防火墙、Fail2ban 或 CloudPanel 规则。主菜单写“需检查”，不是承诺存在一个自动修复按钮。${C_RESET}"
