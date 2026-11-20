#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

ui_title '服务器登录安全'
say
port='未知'; root='UNKNOWN'; pass='UNKNOWN'
config_ok=0; ssh_state='未确认'; risk_count=0
sshd_bin="$(command -v sshd 2>/dev/null || true)"
[[ -n "$sshd_bin" ]] || { [[ -x /usr/sbin/sshd ]] && sshd_bin=/usr/sbin/sshd || true; }

if [[ -n "$sshd_bin" ]]; then
  if effective="$("$sshd_bin" -T 2>/dev/null)"; then
    config_ok=1
    port="$(awk '$1=="port" {print $2; exit}' <<<"$effective")"; port="${port:-未知}"
    root="$(awk '$1=="permitrootlogin" {print $2; exit}' <<<"$effective")"; root="${root:-UNKNOWN}"
    pass="$(awk '$1=="passwordauthentication" {print $2; exit}' <<<"$effective")"; pass="${pass:-UNKNOWN}"
    if [[ "$root" == yes ]]; then risk_count=$((risk_count+1)); fi
    if [[ "$pass" == yes ]]; then risk_count=$((risk_count+1)); fi
  fi
fi

if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet ssh 2>/dev/null || systemctl is-active --quiet sshd 2>/dev/null; then
    ssh_state='服务运行中'
  elif systemctl is-active --quiet ssh.socket 2>/dev/null; then
    ssh_state='按需启动'
  else
    ssh_state='未确认运行'
  fi
fi

if (( config_ok == 0 )); then
  ui_attention '结论        SSH 配置未能核实'
elif (( risk_count > 0 )); then
  ui_attention "结论        有 ${risk_count} 项登录配置建议"
else
  ui_good '结论        未发现明显的登录配置风险'
fi
say
case "$ssh_state" in
  服务运行中|按需启动) printf 'SSH 服务    %b%s%b\n' "$C_GREEN" "$ssh_state" "$C_RESET" ;;
  *) printf 'SSH 服务    %b%s%b\n' "$C_YELLOW" "$ssh_state" "$C_RESET" ;;
esac
printf 'SSH 端口    %s（配置值）\n' "$port"

root_text='未能确认'; root_color="$C_YELLOW"
case "$root" in
  yes) root_text='允许管理员直接登录'; root_color="$C_YELLOW" ;;
  no) root_text='禁止管理员远程登录'; root_color="$C_GREEN" ;;
  prohibit-password|without-password) root_text='管理员仅允许密钥认证'; root_color="$C_GREEN" ;;
  forced-commands-only) root_text='仅允许受限命令'; root_color="$C_GREEN" ;;
esac
printf '管理员登录  %b%s%b\n' "$root_color" "$root_text" "$C_RESET"

pass_text='未能确认'; pass_color="$C_YELLOW"
case "$pass" in
  yes) pass_text='允许密码认证'; pass_color="$C_YELLOW" ;;
  no) pass_text='禁止密码认证'; pass_color="$C_GREEN" ;;
esac
printf '密码认证    %b%s%b\n' "$pass_color" "$pass_text" "$C_RESET"

firewall='未确认'; fw_color="$C_YELLOW"
if command -v ufw >/dev/null 2>&1; then
  state="$(ufw status 2>/dev/null | awk -F': ' '/^Status:/ {print $2; exit}' || true)"
  case "$state" in
    active) firewall='已启用'; fw_color="$C_GREEN" ;;
    inactive) firewall='UFW 未启用' ;;
  esac
elif command -v firewall-cmd >/dev/null 2>&1; then
  state="$(firewall-cmd --state 2>/dev/null || true)"
  if [[ "$state" == running ]]; then firewall='已启用'; fw_color="$C_GREEN"; fi
elif command -v nft >/dev/null 2>&1; then
  if nft list ruleset 2>/dev/null | grep -qE '^[[:space:]]*(chain|table)[[:space:]]'; then
    firewall='检测到防火墙规则'; fw_color="$C_GREEN"
  fi
fi
printf '防火墙      %b%s%b\n' "$fw_color" "$firewall" "$C_RESET"

protection='未安装'; prot_color="$C_YELLOW"
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet fail2ban 2>/dev/null; then
  protection='已启用'; prot_color="$C_GREEN"
elif command -v fail2ban-client >/dev/null 2>&1; then
  protection='已安装，未确认运行'
fi
printf '登录防护    %b%s%b\n' "$prot_color" "$protection" "$C_RESET"
say
if (( config_ok == 0 )); then
  ui_note '检测无法确认 SSH 配置；请勿据此更改当前登录方式。'
elif (( risk_count > 0 )); then
  ui_note '建议先确认密钥可正常登录；本工具不会自动修改 SSH 设置。'
else
  ui_note '本页仅检查，不修改登录方式、防火墙或服务。'
fi
