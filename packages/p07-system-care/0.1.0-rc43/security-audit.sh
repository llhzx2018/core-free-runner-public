#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

ui_title "服务器登录安全"
say

risk_count=0
root='UNKNOWN'; pass='UNKNOWN'; port='未知'

if command -v sshd >/dev/null 2>&1; then
  effective="$(sshd -T 2>/dev/null || true)"
  port="$(awk '$1=="port" {print $2; exit}' <<<"$effective")"; port="${port:-未知}"
  root="$(awk '$1=="permitrootlogin" {print $2; exit}' <<<"$effective")"; root="${root:-UNKNOWN}"
  pass="$(awk '$1=="passwordauthentication" {print $2; exit}' <<<"$effective")"; pass="${pass:-UNKNOWN}"
  [[ "$root" == yes ]] && risk_count=$((risk_count+1))
  [[ "$pass" == yes ]] && risk_count=$((risk_count+1))
fi

root_text='未知'
case "$root" in
  yes) root_text='允许 · 建议确认是否需要' ;;
  no) root_text='已关闭' ;;
  prohibit-password|without-password) root_text='仅允许密钥登录' ;;
esac

pass_text='未知'
case "$pass" in
  yes) pass_text='允许 · 建议使用密钥登录' ;;
  no) pass_text='已关闭' ;;
esac

firewall='未检测到常见防火墙规则'
if command -v ufw >/dev/null 2>&1; then
  state="$(ufw status 2>/dev/null | awk -F': ' '/^Status:/ {print $2; exit}' || true)"
  [[ "$state" == active ]] && firewall='已启用' || firewall='未启用'
elif command -v firewall-cmd >/dev/null 2>&1; then
  state="$(firewall-cmd --state 2>/dev/null || true)"
  [[ "$state" == running ]] && firewall='已启用' || firewall='未启用'
elif command -v nft >/dev/null 2>&1 && nft list ruleset >/dev/null 2>&1; then
  firewall='已检测到规则'
fi

if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet fail2ban 2>/dev/null; then
  protection='已启用'
elif command -v fail2ban-client >/dev/null 2>&1; then
  protection='已安装但未运行'
else
  protection='未安装'
fi

security="$(cached_update_value SECURITY)"
[[ "$security" =~ ^[0-9]+$ ]] || security='未检查'

if (( risk_count == 0 )); then
  printf '结论        当前未发现明显登录风险\n'
else
  printf '结论        有 %s 项登录设置需要你确认\n' "$risk_count"
fi
say
printf '远程登录    正常 · 端口 %s\n' "$port"
printf '管理员登录  %s\n' "$root_text"
printf '密码登录    %s\n' "$pass_text"
printf '防火墙      %s\n' "$firewall"
printf '登录防护    %s\n' "$protection"
printf '网站面板    %s\n' "$(cloudpanel_label)"
printf '安全更新    %s\n' "$security"
say
if (( risk_count > 0 )); then
  ui_note '这里只提醒，不自动修改登录方式，避免把你锁在服务器外。'
else
  ui_note '这里只检查，不修改远程登录、防火墙或网站面板规则。'
fi
