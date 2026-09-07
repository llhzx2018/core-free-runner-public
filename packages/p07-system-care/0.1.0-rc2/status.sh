#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

mode="${1:-full}"

if [[ "$mode" == quick ]]; then
  updates="$(cached_update_value UPDATES)"
  security="$(cached_update_value SECURITY)"
else
  updates="$(apt_upgradable_count)"
  security="$(apt_security_count)"
  write_update_cache "$updates" "$security"
fi

disk="$(root_disk_pct)"
inode="$(root_inode_pct)"
failed="$(failed_unit_count)"
cp="$(cloudpanel_label)"
reboot=NO; reboot_required && reboot=YES

attention=0
[[ "$disk" =~ ^[0-9]+$ && "$disk" -ge 85 ]] && attention=$((attention+1))
[[ "$inode" =~ ^[0-9]+$ && "$inode" -ge 85 ]] && attention=$((attention+1))
[[ "$failed" =~ ^[0-9]+$ && "$failed" -gt 0 ]] && attention=$((attention+1))
[[ "$security" =~ ^[0-9]+$ && "$security" -gt 0 ]] && attention=$((attention+1))
[[ "$reboot" == YES ]] && attention=$((attention+1))

health=HEALTHY
[[ "$attention" -gt 0 ]] && health=ATTENTION

printf 'P07_SYSTEM_CARE_STATUS=%s\n' "$health"
printf 'P07_SYSTEM_CARE_ATTENTION=%s\n' "$attention"
printf 'P07_SYSTEM_CARE_UPDATES=%s\n' "$updates"
printf 'P07_SYSTEM_CARE_SECURITY_UPDATES=%s\n' "$security"
printf 'P07_SYSTEM_CARE_ROOT_DISK_PCT=%s\n' "$disk"
printf 'P07_SYSTEM_CARE_ROOT_INODE_PCT=%s\n' "$inode"
printf 'P07_SYSTEM_CARE_FAILED_UNITS=%s\n' "$failed"
printf 'P07_SYSTEM_CARE_REBOOT_REQUIRED=%s\n' "$reboot"
printf 'P07_SYSTEM_CARE_CLOUDPANEL=%s\n' "$cp"
