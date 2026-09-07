#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

require_apt() { [[ "$(pkg_manager)" == apt ]] || { fail '当前仅支持 Debian/Ubuntu APT 更新。'; return 65; }; }
refresh() { require_root; require_apt; apt-get update; }

security_packages() {
  apt-get -s -o Debug::NoLocking=true upgrade 2>/dev/null | awk '/^Inst / && /[Ss]ecurity/ {print $2}' | sort -u
}

show_cached_state() {
  local updates security
  cache_get updates UPDATES updates
  cache_get updates SECURITY security
  [[ "$updates" =~ ^[0-9]+$ ]] && printf '可更新     %s\n' "$updates" || printf '可更新     未检查\n'
  [[ "$security" =~ ^[0-9]+$ ]] && printf '安全更新   %s\n' "$security" || printf '安全更新   未检查\n'
  if reboot_required; then printf '重启状态   需要重启\n'; else printf '重启状态   当前无需重启\n'; fi
}

check_state() {
  require_apt
  info '正在检查更新，请稍候...'
  local updates security
  updates="$(apt_upgradable_count)"
  security="$(apt_security_count)"
  write_update_cache "$updates" "$security"
  printf '可更新     %s\n' "$updates"
  printf '安全更新   %s\n' "$security"
  if reboot_required; then printf '重启状态   需要重启\n'; else printf '重启状态   当前无需重启\n'; fi
}

apply_security() {
  require_root; require_apt
  info '正在检查安全更新，请稍候...'
  local packages=()
  mapfile -t packages < <(security_packages)
  if [[ ${#packages[@]} -eq 0 ]]; then ok '当前缓存列表中没有识别到安全更新。'; check_state; return 0; fi
  printf '将仅升级以下安全更新包：\n'
  printf '  %s\n' "${packages[@]}"
  confirm_numeric '将刷新 APT 列表并安装以上安全更新；不会自动重启。' || { warn '已取消。'; return 0; }
  apt-get update
  mapfile -t packages < <(security_packages)
  [[ ${#packages[@]} -gt 0 ]] && DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade -y "${packages[@]}"
  ok '安全更新步骤完成。'
  check_state
}

apply_all() {
  require_root; require_apt
  confirm_numeric '将运行 apt-get update + upgrade；不会自动重启，也不会修改 CloudPanel 站点配置。' || { warn '已取消。'; return 0; }
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
  ok '系统更新步骤完成。'
  check_state
}

case "${1:-menu}" in
  status|check) check_state ;;
  refresh) refresh; check_state ;;
  security) apply_security ;;
  all) apply_all ;;
  menu)
    while true; do
      screen_clear
      say "${C_BOLD}P07 · 系统更新${C_RESET}"; say
      show_cached_state
      say
      say '1. 检查更新'
      say '2. 刷新更新列表'
      say '3. 安装安全更新'
      say '4. 安装全部更新'
      say '0. 返回'; say
      printf '请选择 [0-4]：'; read -r choice || exit 0
      case "$choice" in
        1) check_state; pause_menu ;;
        2) if confirm_numeric '刷新 APT 更新列表？'; then refresh; check_state; else warn '已取消。'; fi; pause_menu ;;
        3) apply_security; pause_menu ;;
        4) apply_all; pause_menu ;;
        0) exit 0 ;;
        *) warn '无效选择。'; sleep 1 ;;
      esac
    done
    ;;
  *) fail "未知更新命令: $1"; exit 2 ;;
esac
