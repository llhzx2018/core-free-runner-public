#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
VERSION='UNKNOWN'
IFS= read -r VERSION < "$SCRIPT_DIR/VERSION" 2>/dev/null || VERSION='UNKNOWN'
source "$SCRIPT_DIR/lib/common.sh"




show_help() {
  cat <<'HELP'
服务器维护与安全

用法：
  vf-system-care.sh menu                         进入菜单
  vf-system-care.sh status|check                 查看快速状态
  vf-system-care.sh audit                        执行完整体检
  vf-system-care.sh updates                      系统更新
  vf-system-care.sh cleanup                      磁盘 / 日志清理
  vf-system-care.sh memory                       内存检查（含虚拟内存 Swap / 内存不足保护 OOM）
  vf-system-care.sh services                     服务异常诊断
  vf-system-care.sh security                     服务器登录安全（含远程登录 SSH）
  vf-system-care.sh resources [...]              性能配置建议
  vf-system-care.sh evidence [...]               WordPress 网站安全
  vf-system-care.sh --version                    显示版本
  vf-system-care.sh --help                       显示帮助

安全边界：
  - 与网站面板（CloudPanel）配合使用，不替代网站运行环境（PHP）、网站配置模板（Vhost）、HTTPS 证书和数据库管理。
  - 菜单首页只读取缓存；耗时检查只在你明确选择后执行。
  - 系统运行状态与安全建议分开判断，不把远程登录（SSH）方式直接当作服务器故障。
  - 资源优化默认只生成建议；只有已完成真实校准的规格才允许安全应用。
  - WordPress 网站安全只读取网站文件和访问日志，不自动修改或删除网站文件。
  - 系统更新和清理必须经过预检与确认，不自动重启。
  - 检测到 CloudPanel 时，工具不会自动升级可能影响面板 / 网站运行环境的关键包。
HELP
}

show_header() {
  screen_clear
  ui_title '服务器维护与安全'
  local health advisory evidence
  cache_get summary STATUS health
  cache_get summary SECURITY_ADVISORIES advisory
  cache_get intrusion STATUS evidence
  if [[ "$health" == ATTENTION ]]; then
    ui_attention '服务器有待检查项'
  elif [[ "$health" == HEALTHY ]]; then
    ui_good '服务器状态：正常'
  fi
  if [[ "$evidence" == ATTENTION || "$evidence" == FAILED ]]; then
    ui_attention 'WordPress 安全需检查'
  fi
  say
}

run_action() {
  local script="$1"; shift || true
  set +e
  bash "$SCRIPT_DIR/$script" "$@"
  local rc=$?
  set -e
  [[ $rc -eq 0 ]] || warn '操作未完成，请查看上方提示。'
  return 0
}

run_action_friendly() {
  local script="$1"; shift || true
  # Never pipe an interactive child through sed: a Y/N prompt without a newline
  # remains buffered, so FinalShell looks frozen although it is awaiting input.
  # All user-facing labels live in the child scripts, preserving native TTY I/O.
  local rc
  set +e
  bash "$SCRIPT_DIR/$script" "$@"
  rc=$?
  set -e
  [[ $rc -eq 0 ]] || warn '操作未完成，请查看上方提示。'
  return 0
}

updates_flow_beginner() {
  local updates security
  screen_clear
  ui_title '系统更新'
  say
  ui_note '正在检查可用更新，请稍候...'
  updates="$(apt_upgradable_count)"
  security="$(apt_security_count)"
  write_update_cache "$updates" "$security"
  say
  printf '可更新     %s\n' "$updates"
  printf '安全更新   %s\n' "$security"
  if reboot_required; then
    printf '重启状态   %b需要重启%b\n' "$C_YELLOW" "$C_RESET"
    ui_note '这是之前更新留下的重启提示；P07 不会自动重启服务器。'
  else
    printf '重启状态   当前无需重启\n'
  fi
  say

  if [[ "$updates" =~ ^[0-9]+$ ]] && (( updates == 0 )); then
    ui_good '当前没有可安装更新 ✓'
    pause_menu
    return 0
  fi

  if [[ "$security" =~ ^[0-9]+$ ]] && (( security > 0 )); then
    ui_note '优先处理安全更新；如果之后仍有普通更新，再次进入“系统更新”即可继续检查。'
    run_action_friendly updates.sh security
  else
    ui_note '当前没有单独识别到安全更新；下面只在安全预检通过后安装普通系统更新。'
    run_action_friendly updates.sh all
  fi
  pause_menu
}

cleanup_flow_beginner() {
  screen_clear
  ui_title '磁盘空间清理'
  say
  run_action_friendly cleanup.sh safe
  pause_menu
}

resource_flow_beginner() {
  local choice rc=0
  screen_clear
  ui_title '性能配置'
  say
  set +e
  python3 "$SCRIPT_DIR/lib/resource_brief.py" overview
  rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    # The actual application plan did not clear the safety gate.
    # Do not offer a write action for an ineligible VPS.
    pause_menu
    return 0
  fi
  say
  printf '按 Enter 返回；输入 A 申请安全应用：'
  read -r choice || return 0
  if [[ "$choice" == [Aa] ]]; then
    say
    run_action_friendly resource-apply.sh apply
    pause_menu
  fi
}


selfcheck_local_module() {
  screen_clear
  ui_title '检查本模块'
  ui_rule
  local name missing=0 actual=''
  for name in vf-system-care.sh status.sh audit.sh updates.sh cleanup.sh memory.sh services.sh security-audit.sh resource-profile.sh resource-apply.sh lib/common.sh; do
    if [[ ! -f "$SCRIPT_DIR/$name" || -L "$SCRIPT_DIR/$name" ]]; then
      ui_bad "本模块文件缺失或存在链接：$name"
      missing=$((missing + 1))
    fi
  done
  if [[ -f "$SCRIPT_DIR/VERSION" && ! -L "$SCRIPT_DIR/VERSION" ]]; then
    IFS= read -r actual < "$SCRIPT_DIR/VERSION" || actual=''
    if [[ "$actual" != "$VERSION" ]]; then
      ui_bad '模块版本标记不一致'
      missing=$((missing + 1))
    fi
  else
    ui_bad '模块版本文件缺失'
    missing=$((missing + 1))
  fi
  if (( missing == 0 )); then
    ui_good '本模块基础文件与版本检查通过；其他模块未安装、升级或修改'
  else
    ui_attention '本模块检查失败；请从工具箱的 P07-M04 服务器维护与安全入口单独安装或修复'
  fi
  pause_menu
}

recent_local_actions() {
  screen_clear
  ui_title '最近检查结果'
  ui_rule
  local name value found=0
  # Read M04-owned cache only, not M03 migration history.
  for name in summary intrusion; do
    value=''
    cache_get "$name" STATUS value
    if [[ -n "$value" ]]; then
      ui_note "$name：$value"
      found=1
    fi
  done
  if (( found == 0 )); then
    ui_note '暂无本模块缓存的检查结果。'
  fi
  ui_note '这是最近检查缓存，不是持久操作审计日志。'
  pause_menu
}

wordpress_present() (
  shopt -s nullglob
  local file
  for file in /home/*/htdocs/*/wp-config.php /home/*/htdocs/*/*/wp-config.php; do
    [[ -f "$file" ]] && exit 0
  done
  exit 1
)

wordpress_flow_beginner() {
  # Display existing evidence status before performing any new scan. The child
  # menu has its own 0 → return path; do not require a second Enter here.
  screen_clear
  run_action intrusion-evidence-entry.sh menu
}

menu() {
  local choice has_wordpress=0
  while true; do
    wordpress_present && has_wordpress=1 || has_wordpress=0
    show_header
    ui_menu_good 1 '检查服务器健康（完整）'
    ui_menu_warn 2 '检查并安装系统更新'
    ui_menu_warn 3 '扫描并清理磁盘空间'
    ui_menu_good 4 '查看性能配置'
    ui_menu_warn 5 '检查服务器登录安全'
    if [[ "$has_wordpress" -eq 1 ]]; then
      ui_menu_info 6 '检查 WordPress 网站安全'
    fi
    ui_menu_good 7 '检查本模块（只读）'
    ui_menu_info 8 '查看最近检查结果'
    ui_menu_back 0 '返回工具箱'
    ui_prompt '请选择 [0-8]：'
    read -r choice || return 0
    case "$choice" in
      1) screen_clear; run_action_friendly audit.sh; pause_menu ;;
      2) updates_flow_beginner ;;
      3) cleanup_flow_beginner ;;
      4) resource_flow_beginner ;;
      5) screen_clear; run_action_friendly security-audit.sh; pause_menu ;;
      6)
        if [[ "$has_wordpress" -eq 1 ]]; then
          wordpress_flow_beginner
        else
          ui_attention '未发现 WordPress 网站，未执行扫描。'
        fi ;;
      7) selfcheck_local_module ;;
      8) recent_local_actions ;;
      0) return 0 ;;
      *) ui_attention '无效选择，请输入 0-8。' ;;
    esac
  done
}
case "${1:-menu}" in
  --version|-V) printf '服务器维护与安全 %s\n' "$VERSION" ;;
  --ui-contract) printf 'P07_BEGINNER_ZH_V1\n' ;;
  --help|-h) show_help ;;
  status|check) exec bash "$SCRIPT_DIR/status.sh" ;;
  audit) exec bash "$SCRIPT_DIR/audit.sh" ;;
  updates) shift; exec bash "$SCRIPT_DIR/updates.sh" "${@:-menu}" ;;
  cleanup) shift; exec bash "$SCRIPT_DIR/cleanup.sh" "${@:-menu}" ;;
  memory) exec bash "$SCRIPT_DIR/memory.sh" ;;
  services) exec bash "$SCRIPT_DIR/services.sh" ;;
  security) exec bash "$SCRIPT_DIR/security-audit.sh" ;;
  resources|resource|optimize) shift; exec bash "$SCRIPT_DIR/resource-profile.sh" "${@:-menu}" ;;
  evidence) shift; exec bash "$SCRIPT_DIR/intrusion-evidence-entry.sh" "${@:-menu}" ;;
  menu|"")
    if [[ ( -t 0 && -t 1 ) || "${P07_FORCE_INTERACTIVE:-0}" == "1" ]]; then menu; else show_help; fi
    ;;
  *) fail "未知命令：$1"; exit 2 ;;
esac
