#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

info '正在执行完整系统体检，请稍候...'
os='UNKNOWN'; kernel="$(uname -r 2>/dev/null || printf UNKNOWN)"
if [[ -r /etc/os-release ]]; then
  source /etc/os-release
  os="${PRETTY_NAME:-${NAME:-UNKNOWN}}"
fi
load="$(awk '{print $1" "$2" "$3}' /proc/loadavg 2>/dev/null || printf UNKNOWN)"
mem="$(free -h 2>/dev/null | awk '/^Mem:/ {print $3" / "$2}' || true)"; mem="${mem:-UNKNOWN}"
swap="$(free -h 2>/dev/null | awk '/^Swap:/ {print $3" / "$2}' || true)"; swap="${swap:-UNKNOWN}"
disk="$(root_disk_pct)"; inode="$(root_inode_pct)"; failed="$(failed_unit_count)"
updates="$(apt_upgradable_count)"; security="$(apt_security_count)"
write_update_cache "$updates" "$security"
cp="$(cloudpanel_label)"
reboot='否'; reboot_cache='NO'; if reboot_required; then reboot='是'; reboot_cache='YES'; fi

journal='UNKNOWN'
if command -v journalctl >/dev/null 2>&1; then
  journal="$(journalctl --disk-usage 2>/dev/null | sed -E 's/^Archived and active journals take up //; s/\.$//' || true)"
  journal="${journal:-UNKNOWN}"
fi

oom='未发现本次启动 OOM 证据'
if command -v journalctl >/dev/null 2>&1 && journalctl -k -b --no-pager 2>/dev/null | grep -Eqi 'Out of memory|oom-kill|Killed process'; then
  oom='发现 OOM / 进程被内核终止证据'
fi

ntp='UNKNOWN'
if command -v timedatectl >/dev/null 2>&1; then
  ntp="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || true)"; ntp="${ntp:-UNKNOWN}"
fi

ssh_port='UNKNOWN'; root_login='UNKNOWN'; password_auth='UNKNOWN'
if command -v sshd >/dev/null 2>&1; then
  ssh_effective="$(sshd -T 2>/dev/null || true)"
  ssh_port="$(awk '$1=="port" {print $2; exit}' <<<"$ssh_effective")"; ssh_port="${ssh_port:-UNKNOWN}"
  root_login="$(awk '$1=="permitrootlogin" {print $2; exit}' <<<"$ssh_effective")"; root_login="${root_login:-UNKNOWN}"
  password_auth="$(awk '$1=="passwordauthentication" {print $2; exit}' <<<"$ssh_effective")"; password_auth="${password_auth:-UNKNOWN}"
fi

firewall='未检测到常见防火墙管理器'
if command -v ufw >/dev/null 2>&1; then
  firewall="UFW $(ufw status 2>/dev/null | awk -F': ' '/^Status:/ {print $2; exit}' || printf UNKNOWN)"
elif command -v firewall-cmd >/dev/null 2>&1; then
  firewall="firewalld $(firewall-cmd --state 2>/dev/null || printf UNKNOWN)"
elif command -v nft >/dev/null 2>&1; then
  if nft list ruleset >/dev/null 2>&1; then firewall='nftables 已有规则'; else firewall='nftables 状态未知'; fi
fi

fail2ban='未安装/未运行'
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet fail2ban 2>/dev/null; then fail2ban='运行中'
elif command -v fail2ban-client >/dev/null 2>&1; then fail2ban='已安装但未运行'; fi

ports='UNKNOWN'
if command -v ss >/dev/null 2>&1; then ports="$(ss -lntupH 2>/dev/null | awk 'NF {n++} END {print n+0}')"; fi

attention=0
issues=()
security_advisories=0
advice_items=()
need_updates=0 need_cleanup=0 need_memory=0 need_services=0 need_reboot=0
if [[ "$disk" =~ ^[0-9]+$ && "$disk" -ge 85 ]]; then issues+=("根分区使用率 ${disk}%"); attention=$((attention+1)); need_cleanup=1; fi
if [[ "$inode" =~ ^[0-9]+$ && "$inode" -ge 85 ]]; then issues+=("根分区 inode 使用率 ${inode}%"); attention=$((attention+1)); need_cleanup=1; fi
if [[ "$failed" =~ ^[0-9]+$ && "$failed" -gt 0 ]]; then issues+=("${failed} 个 systemd 服务异常"); attention=$((attention+1)); need_services=1; fi
if [[ "$security" =~ ^[0-9]+$ && "$security" -gt 0 ]]; then issues+=("${security} 个安全更新待安装"); attention=$((attention+1)); need_updates=1; fi
if [[ "$reboot" == '是' ]]; then issues+=("系统提示需要重启"); attention=$((attention+1)); need_reboot=1; fi
if [[ "$oom" == 发现* ]]; then issues+=("检测到 OOM 证据"); attention=$((attention+1)); need_memory=1; fi
if [[ "$root_login" == yes ]]; then advice_items+=("SSH 允许 root 直接登录"); security_advisories=$((security_advisories+1)); fi
if [[ "$password_auth" == yes ]]; then advice_items+=("SSH 允许密码认证"); security_advisories=$((security_advisories+1)); fi

health=HEALTHY
[[ "$attention" -gt 0 ]] && health=ATTENTION
write_summary_cache "$health" "$disk" "$inode" "$failed" "$reboot_cache" "$cp" "$security_advisories"

say "${C_BOLD}P07 · 一键系统体检${C_RESET}"
say
printf '系统       %s\n' "$os"
printf '内核       %s\n' "$kernel"
printf '负载       %s\n' "$load"
printf '内存       %s\n' "$mem"
printf 'Swap       %s\n' "$swap"
printf '根分区     %s%% · inode %s%%\n' "$disk" "$inode"
printf '系统日志   %s\n' "$journal"
printf '系统更新   %s · 安全更新 %s\n' "$updates" "$security"
printf '需要重启   %s\n' "$reboot"
printf '异常服务   %s\n' "$failed"
printf 'OOM        %s\n' "$oom"
printf '时间同步   %s\n' "$ntp"
printf 'SSH        port=%s · root=%s · password=%s\n' "$ssh_port" "$root_login" "$password_auth"
printf '监听端口   %s\n' "$ports"
printf '防火墙     %s\n' "$firewall"
printf 'Fail2ban   %s\n' "$fail2ban"
printf 'CloudPanel %s\n' "$cp"
say
if [[ "$attention" -eq 0 ]]; then
  ok '结果       正常 · 当前未发现需要立即处理的运行问题'
else
  warn "结果       需检查 · ${attention} 项运行问题"
  for item in "${issues[@]}"; do printf '           - %s\n' "$item"; done
  say
  say '下一步：'
  (( need_updates == 1 )) && say '  - 安全更新：返回后选 2. 系统更新'
  (( need_cleanup == 1 )) && say '  - 磁盘 / inode：返回后选 3. 磁盘 / 日志清理'
  (( need_memory == 1 )) && say '  - OOM / 内存：返回后选 4. 内存 / Swap / OOM'
  (( need_services == 1 )) && say '  - 服务异常：返回后选 5. 服务异常诊断'
  (( need_reboot == 1 )) && say '  - 需要重启：请在你自己的维护窗口手动安排；P07 不会自动重启'
fi

if [[ "$security_advisories" -gt 0 ]]; then
  say
  warn "安全建议   ${security_advisories} 项 · 不影响当前服务器运行状态"
  for item in "${advice_items[@]}"; do printf '           - %s\n' "$item"; done
  say '下一步     返回后选 6. SSH / 安全检查 查看详情；当前不会自动改 SSH。'
fi
say
say "${C_GRAY}说明：体检只读取服务器状态；CloudPanel 管理的网站、PHP、Vhost、SSL、数据库与面板规则不会被修改。${C_RESET}"
