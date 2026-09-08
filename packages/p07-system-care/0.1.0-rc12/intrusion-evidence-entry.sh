#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

BASE="$SCRIPT_DIR/intrusion-evidence.sh"
DISCOVERY="$SCRIPT_DIR/lib/intrusion_discovery.py"
STATE_DIR="${P07_IE_STATE_DIR:-/var/lib/vf-system-care/intrusion-evidence}"

is_enabled() {
  local line key value output enabled=0
  set +e
  output="$(python3 "$SCRIPT_DIR/lib/intrusion_evidence.py" --state-dir "$STATE_DIR" status --kv 2>/dev/null)"
  set -e
  while IFS= read -r line; do
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"; value="${line#*=}"
    [[ "$key" == P07_IE_ENABLED ]] && enabled="$value"
  done <<< "$output"
  [[ "$enabled" == 1 ]]
}

run_discovery() {
  WP_DISCOVERY_STATUS='UNKNOWN'
  WP_DISCOVERY_SOURCE='unknown'
  WP_CLOUDPANEL_SITES='UNKNOWN'
  WP_SITES='UNKNOWN'
  local output rc line key value
  set +e
  output="$(python3 "$DISCOVERY" --kv 2>&1)"
  rc=$?
  set -e
  while IFS= read -r line; do
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"; value="${line#*=}"
    case "$key" in
      P07_WP_DISCOVERY_STATUS) WP_DISCOVERY_STATUS="$value" ;;
      P07_WP_DISCOVERY_SOURCE) WP_DISCOVERY_SOURCE="$value" ;;
      P07_WP_DISCOVERY_CLOUDPANEL_SITES) WP_CLOUDPANEL_SITES="$value" ;;
      P07_WP_DISCOVERY_WORDPRESS_SITES) WP_SITES="$value" ;;
    esac
  done <<< "$output"
  return "$rc"
}

classify_before_menu() {
  WP_DISCOVERY_RC=0
  set +e
  run_discovery
  WP_DISCOVERY_RC=$?
  set -e
}

preflight_enable() {
  info '正在识别 CloudPanel 网站类型...'
  classify_before_menu
  case "$WP_DISCOVERY_STATUS" in
    READY)
      say "CloudPanel   ${WP_CLOUDPANEL_SITES} 个网站"
      say "WordPress    ${WP_SITES} 个"
      say
      exec bash "$BASE" enable
      ;;
    NO_WORDPRESS)
      say "CloudPanel   ${WP_CLOUDPANEL_SITES} 个网站"
      say 'WordPress    0 个'
      say
      warn '结果         当前没有 WordPress，不需要开启网站安全保护。'
      say '说明         P07 不会把普通 PHP 网站误当成 WordPress，也不会创建空的自动任务。'
      return 0
      ;;
    UNSAFE_LAYOUT)
      warn '结果         识别到疑似 WordPress，但站点路径不符合安全读取规则。'
      say '说明         P07 已停止，不会跟随不安全路径，也不会创建自动任务。'
      return 0
      ;;
    BUDGET_EXCEEDED)
      warn '结果         网站识别达到安全扫描上限，已停止。'
      say '说明         没有建立不完整参考状态，也没有创建自动任务。'
      return 0
      ;;
    *)
      warn "结果         网站类型识别失败 · ${WP_DISCOVERY_STATUS}"
      say '说明         没有创建自动任务。'
      return "${WP_DISCOVERY_RC:-1}"
      ;;
  esac
}

menu_not_enabled() {
  local choice
  classify_before_menu
  while true; do
    screen_clear
    say "${C_BOLD}P07 · 网站入侵留证${C_RESET}"
    say
    case "$WP_DISCOVERY_STATUS" in
      READY)
        printf 'CloudPanel   %s 个网站\n' "$WP_CLOUDPANEL_SITES"
        printf 'WordPress    %s 个\n' "$WP_SITES"
        say '网站安全    未开启'
        say '自动检查    未开启'
        say '下一步      选择 1 开启一次；以后每天会自动检查'
        say
        say '1. 开启网站安全保护'
        say '0. 返回'
        say
        printf '请选择 [0-1]：'
        read -r choice || return 0
        case "$choice" in
          1) exec bash "$BASE" enable ;;
          0) return 0 ;;
          *) warn '无效选择，请输入 0-1。'; sleep 1 ;;
        esac
        ;;
      NO_WORDPRESS)
        printf 'CloudPanel   %s 个网站\n' "$WP_CLOUDPANEL_SITES"
        say 'WordPress    0 个'
        say '网站安全    当前不需要开启'
        say '自动检查    不需要'
        say '下一步      不用处理；以后新增 WordPress 后再回来检测'
        say
        say '1. 重新检测'
        say '0. 返回'
        say
        printf '请选择 [0-1]：'
        read -r choice || return 0
        case "$choice" in
          1) info '正在重新识别网站类型...'; classify_before_menu ;;
          0) return 0 ;;
          *) warn '无效选择，请输入 0-1。'; sleep 1 ;;
        esac
        ;;
      UNSAFE_LAYOUT)
        say '网站安全    暂不能开启'
        say '原因        疑似 WordPress 的站点路径不符合安全读取规则'
        say '说明        P07 已停止，不会跟随不安全路径，也不会创建自动任务'
        say
        say '1. 重新检测'
        say '0. 返回'
        say
        printf '请选择 [0-1]：'
        read -r choice || return 0
        case "$choice" in 1) classify_before_menu ;; 0) return 0 ;; *) warn '无效选择，请输入 0-1。'; sleep 1 ;; esac
        ;;
      BUDGET_EXCEEDED)
        say '网站安全    暂不能开启'
        say '原因        网站识别达到安全扫描上限'
        say '说明        没有建立不完整参考状态，也没有创建自动任务'
        say
        say '1. 重新检测'
        say '0. 返回'
        say
        printf '请选择 [0-1]：'
        read -r choice || return 0
        case "$choice" in 1) classify_before_menu ;; 0) return 0 ;; *) warn '无效选择，请输入 0-1。'; sleep 1 ;; esac
        ;;
      *)
        say '网站安全    暂不能判断'
        say "原因        网站类型识别失败 · ${WP_DISCOVERY_STATUS}"
        say '说明        没有创建自动任务'
        say
        say '1. 重新检测'
        say '0. 返回'
        say
        printf '请选择 [0-1]：'
        read -r choice || return 0
        case "$choice" in 1) classify_before_menu ;; 0) return 0 ;; *) warn '无效选择，请输入 0-1。'; sleep 1 ;; esac
        ;;
    esac
  done
}

case "${1:-menu}" in
  menu)
    if is_enabled; then exec bash "$BASE" menu; else menu_not_enabled; fi
    ;;
  enable)
    if is_enabled; then exec bash "$BASE" enable; else preflight_enable; fi
    ;;
  status|refresh-cache|scan|scan-scheduled|report|rebaseline|disable)
    exec bash "$BASE" "$@"
    ;;
  *)
    exec bash "$BASE" "$@"
    ;;
esac
