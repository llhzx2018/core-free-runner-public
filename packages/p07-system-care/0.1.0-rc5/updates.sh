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

cloudpanel_protected_package() {
  case "${1:-}" in
    cloudpanel*|clp-*|nginx*|apache2*|php*|mysql*|mariadb*|percona*|redis*|varnish*) return 0 ;;
    *) return 1 ;;
  esac
}

simulation_has_downgrade_or_removal() {
  local simulation="$1"
  grep -Eq 'The following packages will be DOWNGRADED:|The following packages will be REMOVED:|^Remv[[:space:]]' <<<"$simulation"
}

simulation_protected_packages() {
  local simulation="$1" pkg
  while read -r pkg; do
    [[ -n "$pkg" ]] || continue
    if cloudpanel_protected_package "$pkg"; then printf '%s\n' "$pkg"; fi
  done < <(awk '/^Inst / {print $2}' <<<"$simulation" | sort -u)
}

run_upgrade_simulation() {
  local outvar="$1" simulation rc
  set +e
  simulation="$(apt-get -s -o Debug::NoLocking=true upgrade 2>&1)"
  rc=$?
  set -e
  printf -v "$outvar" '%s' "$simulation"
  return "$rc"
}

preflight_upgrade() {
  local simulation protected=()
  info '正在做升级安全预检，请稍候...'
  if ! run_upgrade_simulation simulation; then
    fail 'APT 模拟升级失败，已阻止真实升级。'
    return 90
  fi

  if simulation_has_downgrade_or_removal "$simulation"; then
    warn '检测到降级或移除包计划，已阻止真实升级。'
    grep -E 'DOWNGRADED|REMOVED|^Remv[[:space:]]' <<<"$simulation" | head -n 20 || true
    return 91
  fi

  if cloudpanel_present; then
    mapfile -t protected < <(simulation_protected_packages "$simulation")
    if [[ ${#protected[@]} -gt 0 ]]; then
      warn '本轮升级包含 CloudPanel / 网站运行栈相关包，P07 不自动升级：'
      printf '  %s\n' "${protected[@]}"
      warn '请通过 CloudPanel 对应维护流程或单独维护窗口处理。'
      return 92
    fi
  fi

  ok '升级安全预检通过。'
  return 0
}

security_install_preflight() {
  local outvar="$1"; shift
  local packages=("$@") simulation rc protected=()
  [[ ${#packages[@]} -gt 0 ]] || return 0

  set +e
  simulation="$(apt-get -s -o Debug::NoLocking=true install --only-upgrade "${packages[@]}" 2>&1)"
  rc=$?
  set -e
  printf -v "$outvar" '%s' "$simulation"
  [[ $rc -eq 0 ]] || { fail '安全更新模拟安装失败，已阻止真实安装。'; return 93; }

  if simulation_has_downgrade_or_removal "$simulation"; then
    warn '安全更新计划出现降级或移除包，已阻止真实安装。'
    return 94
  fi

  if cloudpanel_present; then
    mapfile -t protected < <(simulation_protected_packages "$simulation")
    if [[ ${#protected[@]} -gt 0 ]]; then
      warn '安全更新计划会改动 CloudPanel / 网站运行栈相关包，P07 已阻止自动安装：'
      printf '  %s\n' "${protected[@]}"
      return 95
    fi
  fi
  return 0
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
  local packages=() simulation=''
  mapfile -t packages < <(security_packages)
  if [[ ${#packages[@]} -eq 0 ]]; then ok '当前缓存列表中没有识别到安全更新。'; check_state; return 0; fi

  printf '计划安装的安全更新：\n'
  printf '  %s\n' "${packages[@]}"
  if ! security_install_preflight simulation "${packages[@]}"; then
    warn '安全更新已安全停止，没有安装任何包。'
    return 0
  fi

  confirm_numeric '将刷新 APT 列表并安装以上安全更新；不会自动重启。' || { warn '已取消。'; return 0; }
  apt-get update
  mapfile -t packages < <(security_packages)
  if [[ ${#packages[@]} -eq 0 ]]; then ok '刷新后已没有待安装安全更新。'; check_state; return 0; fi
  if ! security_install_preflight simulation "${packages[@]}"; then
    warn '刷新后升级计划发生变化，已安全停止，没有安装任何包。'
    check_state
    return 0
  fi

  DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade -y "${packages[@]}"
  ok '安全更新步骤完成。'
  check_state
}

apply_all() {
  require_root; require_apt
  if ! preflight_upgrade; then
    warn '普通更新已安全停止，没有执行 apt-get upgrade。'
    return 0
  fi

  confirm_numeric '将刷新 APT 列表；刷新后会再次安全预检，通过后才安装可用更新。不会自动重启。' || { warn '已取消。'; return 0; }
  apt-get update

  if ! preflight_upgrade; then
    warn '刷新后升级计划发生变化，已安全停止，没有执行 apt-get upgrade。'
    check_state
    return 0
  fi

  DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
  ok '系统更新步骤完成。'
  check_state
}

case "${1:-menu}" in
  status|check) check_state ;;
  refresh) refresh; check_state ;;
  preflight) preflight_upgrade ;;
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
      say '4. 安装可用更新（安全模式）'
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
