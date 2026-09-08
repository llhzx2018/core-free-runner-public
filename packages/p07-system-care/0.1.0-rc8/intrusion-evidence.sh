#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR='.'
source "$SCRIPT_DIR/lib/common.sh"

PY_HELPER="$SCRIPT_DIR/lib/intrusion_evidence.py"
STATE_DIR="${P07_IE_STATE_DIR:-/var/lib/vf-system-care/intrusion-evidence}"
SYSTEMD_DIR="${P07_IE_SYSTEMD_DIR:-/etc/systemd/system}"
CRON_FILE="${P07_IE_CRON_FILE:-/etc/cron.d/vf-system-care-intrusion-evidence}"
ENTRY="${P07_IE_ENTRY:-/usr/local/bin/vf-system-care}"
SERVICE_NAME='vf-system-care-intrusion-evidence.service'
TIMER_NAME='vf-system-care-intrusion-evidence.timer'

require_python() {
  command -v python3 >/dev/null 2>&1 || { fail '缺少 python3，无法运行网站入侵留证。'; return 80; }
  [[ -r "$PY_HELPER" ]] || { fail '入侵留证 helper 缺失。'; return 81; }
}

helper() {
  require_python || return $?
  python3 "$PY_HELPER" --state-dir "$STATE_DIR" "$@"
}

read_status() {
  IE_ENABLED=0 IE_STATUS='NOT_ENABLED' IE_RESULT='NOT_ENABLED'
  IE_LAST_SCAN='-' IE_LAST_CLEAN='-' IE_FIRST='-' IE_EVENTS=0 IE_UNBASELINED=0 IE_ERROR='-'
  IE_ERROR_RESOURCE='-' IE_ERROR_LIMIT='-' IE_SCHEDULER='UNKNOWN'
  local line key value output rc saw_enabled=0 saw_status=0
  set +e
  output="$(helper status --kv 2>/dev/null)"
  rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    IE_ENABLED=1 IE_STATUS='FAILED' IE_RESULT='STATUS_UNAVAILABLE' IE_ERROR='StatusUnavailableError'
    return 0
  fi
  while IFS= read -r line; do
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"; value="${line#*=}"
    case "$key" in
      P07_IE_ENABLED) IE_ENABLED="$value"; saw_enabled=1 ;;
      P07_IE_STATUS) IE_STATUS="$value"; saw_status=1 ;;
      P07_IE_RESULT) IE_RESULT="$value" ;;
      P07_IE_LAST_SCAN_AT) IE_LAST_SCAN="$value" ;;
      P07_IE_LAST_KNOWN_CLEAN_AT) IE_LAST_CLEAN="$value" ;;
      P07_IE_FIRST_DETECTED_AT) IE_FIRST="$value" ;;
      P07_IE_EVENT_COUNT) IE_EVENTS="$value" ;;
      P07_IE_UNBASELINED_SITE_COUNT) IE_UNBASELINED="$value" ;;
      P07_IE_ERROR_CLASS) IE_ERROR="$value" ;;
      P07_IE_ERROR_RESOURCE) IE_ERROR_RESOURCE="$value" ;;
      P07_IE_ERROR_LIMIT) IE_ERROR_LIMIT="$value" ;;
    esac
  done <<< "$output"
  if [[ $saw_enabled -ne 1 || $saw_status -ne 1 ]]; then
    IE_ENABLED=1 IE_STATUS='FAILED' IE_RESULT='STATUS_UNAVAILABLE' IE_ERROR='StatusUnavailableError'
  fi
}

scheduler_kind() {
  local service="$SYSTEMD_DIR/$SERVICE_NAME" timer="$SYSTEMD_DIR/$TIMER_NAME"
  local has_service=0 has_timer=0 has_cron=0
  [[ -e "$service" ]] && has_service=1
  [[ -e "$timer" ]] && has_timer=1
  [[ -e "$CRON_FILE" ]] && has_cron=1

  if (( has_service != has_timer )); then
    printf 'broken'
    return 0
  fi
  if (( has_timer == 1 && has_cron == 1 )); then
    printf 'broken'
    return 0
  fi
  if (( has_timer == 1 )); then
    [[ -x "$ENTRY" ]] || { printf 'broken'; return 0; }
    if [[ "$SYSTEMD_DIR" == '/etc/systemd/system' ]]; then
      command -v systemctl >/dev/null 2>&1 || { printf 'broken'; return 0; }
      systemctl is-enabled --quiet "$TIMER_NAME" >/dev/null 2>&1 || { printf 'broken'; return 0; }
      systemctl is-active --quiet "$TIMER_NAME" >/dev/null 2>&1 || { printf 'broken'; return 0; }
    fi
    printf 'systemd'
    return 0
  fi
  if (( has_cron == 1 )); then
    [[ -x "$ENTRY" ]] || { printf 'broken'; return 0; }
    if [[ "$CRON_FILE" == /etc/cron.d/* ]]; then
      if ! command -v cron >/dev/null 2>&1 && ! command -v crond >/dev/null 2>&1; then
        printf 'broken'
        return 0
      fi
    fi
    printf 'cron'
    return 0
  fi
  printf 'none'
}

refresh_cache() {
  read_status
  IE_SCHEDULER="$(scheduler_kind)"
  write_kv_cache intrusion \
    "STATUS=${IE_STATUS}" \
    "RESULT=${IE_RESULT}" \
    "ENABLED=${IE_ENABLED}" \
    "LAST_SCAN=${IE_LAST_SCAN}" \
    "FIRST=${IE_FIRST}" \
    "EVENTS=${IE_EVENTS}" \
    "UNBASELINED=${IE_UNBASELINED}" \
    "ERROR=${IE_ERROR}" \
    "ERROR_RESOURCE=${IE_ERROR_RESOURCE}" \
    "ERROR_LIMIT=${IE_ERROR_LIMIT}" \
    "SCHEDULER=${IE_SCHEDULER}"
}

atomic_write_owned_file() {
  local target="$1" mode="$2" dir tmp
  dir="${target%/*}"
  [[ "$dir" == "$target" ]] && dir='.'
  mkdir -p "$dir"
  tmp="${target}.tmp.$$.$RANDOM"
  umask 077
  if ! cat > "$tmp"; then
    rm -f -- "$tmp"
    return 1
  fi
  if ! chmod "$mode" "$tmp" || ! mv -f -- "$tmp" "$target"; then
    rm -f -- "$tmp"
    return 1
  fi
}

restore_owned_file() {
  local target="$1" backup="$2" had_old="$3"
  if [[ "$had_old" == 1 && -e "$backup" ]]; then
    mv -f -- "$backup" "$target" || true
  else
    rm -f -- "$target" "$backup"
  fi
}

install_systemd_scheduler() {
  local service="$SYSTEMD_DIR/$SERVICE_NAME" timer="$SYSTEMD_DIR/$TIMER_NAME"
  local service_backup="$SYSTEMD_DIR/.${SERVICE_NAME}.vf-prev.$$"
  local timer_backup="$SYSTEMD_DIR/.${TIMER_NAME}.vf-prev.$$"
  local service_had=0 timer_had=0 was_enabled=0 was_active=0
  mkdir -p "$SYSTEMD_DIR"

  if [[ -e "$service" ]]; then cp -p -- "$service" "$service_backup"; service_had=1; fi
  if [[ -e "$timer" ]]; then cp -p -- "$timer" "$timer_backup"; timer_had=1; fi

  if [[ "$SYSTEMD_DIR" == '/etc/systemd/system' ]] && command -v systemctl >/dev/null 2>&1; then
    systemctl is-enabled --quiet "$TIMER_NAME" >/dev/null 2>&1 && was_enabled=1 || true
    systemctl is-active --quiet "$TIMER_NAME" >/dev/null 2>&1 && was_active=1 || true
  fi

  if ! atomic_write_owned_file "$service" 0644 <<EOF
[Unit]
Description=P07 System Care intrusion evidence scan
After=local-fs.target

[Service]
Type=oneshot
ExecStart=$ENTRY evidence scan-scheduled
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
TimeoutStartSec=35m
EOF
  then
    restore_owned_file "$service" "$service_backup" "$service_had"
    rm -f -- "$timer_backup"
    return 1
  fi

  if ! atomic_write_owned_file "$timer" 0644 <<'EOF'
[Unit]
Description=P07 System Care daily intrusion evidence scan

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=45m
Unit=vf-system-care-intrusion-evidence.service

[Install]
WantedBy=timers.target
EOF
  then
    restore_owned_file "$service" "$service_backup" "$service_had"
    restore_owned_file "$timer" "$timer_backup" "$timer_had"
    if [[ "$SYSTEMD_DIR" == '/etc/systemd/system' ]] && command -v systemctl >/dev/null 2>&1; then
      systemctl daemon-reload >/dev/null 2>&1 || true
    fi
    return 1
  fi

  if [[ "$SYSTEMD_DIR" == '/etc/systemd/system' ]]; then
    if ! systemctl daemon-reload >/dev/null 2>&1 || ! systemctl enable --now "$TIMER_NAME" >/dev/null 2>&1; then
      systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1 || true
      restore_owned_file "$service" "$service_backup" "$service_had"
      restore_owned_file "$timer" "$timer_backup" "$timer_had"
      systemctl daemon-reload >/dev/null 2>&1 || true
      if [[ "$was_enabled" == 1 ]]; then systemctl enable "$TIMER_NAME" >/dev/null 2>&1 || true; fi
      if [[ "$was_active" == 1 ]]; then systemctl start "$TIMER_NAME" >/dev/null 2>&1 || true; fi
      return 1
    fi
  fi

  rm -f -- "$service_backup" "$timer_backup"
}

install_cron_scheduler() {
  if ! atomic_write_owned_file "$CRON_FILE" 0644 <<EOF
# P07 System Care · 网站入侵留证（P07-owned）
17 3 * * * root $ENTRY evidence scan-scheduled >/dev/null 2>&1
EOF
  then
    return 1
  fi
}

install_scheduler() {
  if command -v systemctl >/dev/null 2>&1 && { [[ -d /run/systemd/system ]] || [[ "$SYSTEMD_DIR" != '/etc/systemd/system' ]]; }; then
    install_systemd_scheduler || return $?
    rm -f -- "$CRON_FILE"
    printf 'systemd'
  else
    install_cron_scheduler || return $?
    rm -f -- "$SYSTEMD_DIR/$TIMER_NAME" "$SYSTEMD_DIR/$SERVICE_NAME"
    printf 'cron'
  fi
}

remove_scheduler() {
  if [[ -e "$SYSTEMD_DIR/$TIMER_NAME" || -e "$SYSTEMD_DIR/$SERVICE_NAME" ]]; then
    if [[ "$SYSTEMD_DIR" == '/etc/systemd/system' ]] && command -v systemctl >/dev/null 2>&1; then
      systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1 || true
    fi
    rm -f "$SYSTEMD_DIR/$TIMER_NAME" "$SYSTEMD_DIR/$SERVICE_NAME"
    if [[ "$SYSTEMD_DIR" == '/etc/systemd/system' ]] && command -v systemctl >/dev/null 2>&1; then
      systemctl daemon-reload >/dev/null 2>&1 || true
    fi
  fi
  if [[ -e "$CRON_FILE" ]]; then
    rm -f "$CRON_FILE"
  fi
  return 0
}

show_failure_reason() {
  case "$IE_ERROR" in
    TimeoutError) say '失败原因   扫描超过安全时限' ;;
    ScanBudgetExceededError)
      say "失败原因   扫描达到安全资源上限 · ${IE_ERROR_RESOURCE} / ${IE_ERROR_LIMIT}"
      say '说明       未完成全量校验，参考状态不会推进'
      ;;
    EvidenceCapacityExceededError)
      say "失败原因   异常证据达到安全容量上限 · ${IE_ERROR_LIMIT} 条"
      say '说明       旧证据继续保留；不会静默丢弃新异常后再显示正常'
      ;;
    StateEventsMissingError|StateEventsCorruptError|StateEventCountMismatchError)
      say '失败原因   异常证据仓缺失、损坏或与状态记录不一致'
      ;;
    StateScanCorruptError|JSONDecodeError) say '失败原因   留证状态文件损坏' ;;
    StateBaselineMissingError|StateGenerationMissingError|StateGenerationMismatchError|StateScanStateMissingError|StateScanStateInvalidError) say '失败原因   参考状态不一致，请确认网站当前正常后更新参考状态' ;;
    ResourceBudgetConfigError) say '失败原因   留证资源预算配置无效' ;;
    StatusUnavailableError) say '失败原因   留证状态读取不可用' ;;
    '-'|'') ;;
    *) say "失败类型   ${IE_ERROR}" ;;
  esac
}

show_status() {
  refresh_cache
  local sched="$IE_SCHEDULER"
  say "${C_BOLD}P07 · 网站入侵留证${C_RESET}"
  say
  if [[ "$IE_ENABLED" != 1 ]]; then
    say '网站安全   未开启'
    say '自动检查   未开启'
    say '下一步     选择 1 开启一次；以后每天会自动检查'
    return 0
  fi

  case "$IE_STATUS" in
    NORMAL)
      printf '网站安全   %b正常%b\n' "$C_GREEN" "$C_RESET"
      say '处理       当前不用处理'
      ;;
    ATTENTION)
      if [[ "$IE_EVENTS" =~ ^[0-9]+$ ]] && (( IE_EVENTS > 0 )); then
        printf '网站安全   %b需处理%b · %s 条异常\n' "$C_YELLOW" "$C_RESET" "$IE_EVENTS"
      else
        printf '网站安全   %b需处理%b\n' "$C_YELLOW" "$C_RESET"
      fi
      say '下一步     选择 2 查看异常详情'
      ;;
    FAILED)
      printf '网站安全   %b检查失败%b\n' "$C_RED" "$C_RESET"
      show_failure_reason
      say '下一步     根据失败原因处理后，再选择 1 重新检查'
      ;;
    *)
      say '网站安全   未知'
      say '下一步     选择 1 重新检查'
      ;;
  esac

  say "最近检查   ${IE_LAST_SCAN}"
  if [[ "$IE_STATUS" == ATTENTION ]]; then
    say "异常时间   ${IE_LAST_CLEAN} → ${IE_FIRST}"
    say "异常记录   ${IE_EVENTS}"
  fi
  if [[ "$IE_UNBASELINED" =~ ^[0-9]+$ ]] && (( IE_UNBASELINED > 0 )); then
    say "新站点     ${IE_UNBASELINED} 个尚未纳入参考状态"
  fi
  case "$sched" in
    systemd|cron) say '自动检查   已开启 · 每天' ;;
    broken) say '自动检查   异常 · 选择 4 修复' ;;
    *) say '自动检查   未开启 · 选择 4 开启' ;;
  esac
}

enable_evidence() {
  require_root || return $?
  require_python || return $?
  say 'P07 会识别 WordPress 站点，并把当前文件状态保存为以后比较用的参考状态。'
  say '这不是木马扫描，不能证明当前站点没有已经存在的问题。'
  say '开启后每天静默检查；不会修改网站，也不会自动删除文件。'
  say
  confirm_numeric '开启网站入侵留证？' || return 0
  info '正在建立网站文件参考状态...'
  if ! helper baseline >/dev/null; then
    fail '未能建立参考状态。没有创建自动任务。'
    return 82
  fi
  local sched
  if ! sched="$(install_scheduler)"; then
    fail '参考状态已建立，但自动任务创建失败；P07 已回滚本次调度文件。'
    refresh_cache
    return 83
  fi
  refresh_cache
  ok '网站安全保护已开启 · 以后每天自动检查'
}

scan_now() {
  require_root || return $?
  require_python || return $?
  info '正在检查网站关键文件变化...'
  set +e
  helper scan >/dev/null 2>&1
  local rc=$?
  set -e
  refresh_cache
  if [[ $rc -ne 0 ]]; then
    fail '本次检查失败；参考状态不会被推进。'
    [[ "$IE_STATUS" == FAILED ]] && show_failure_reason
    return "$rc"
  fi
  if [[ "$IE_STATUS" == ATTENTION ]]; then
    warn "发现需要查看的异常 · ${IE_EVENTS} 条历史记录"
    say '下一步：选择 2 查看异常详情。'
    if [[ "$IE_UNBASELINED" =~ ^[0-9]+$ ]] && (( IE_UNBASELINED > 0 )); then
      say "另有 ${IE_UNBASELINED} 个新 WordPress 站点尚未纳入参考状态；P07 不会自动信任它们。"
    fi
    say '即使异常文件后来消失，状态也会继续提示，直到你确认处理完成并更新参考状态。'
  else
    ok '网站安全正常 · 当前不用处理。'
  fi
}

scan_scheduled() {
  require_root || return $?
  require_python || return $?
  set +e
  helper scan >/dev/null 2>&1
  local rc=$?
  set -e
  refresh_cache
  return "$rc"
}

show_report() {
  require_root || return $?
  require_python || return $?
  helper report --limit 20
}

rebuild_baseline() {
  require_root || return $?
  say '这一步会把当前网站文件状态保存为新的参考状态。'
  say '只有在你已经确认异常处理完成、当前网站状态可以接受时才执行。'
  say '新发现的 WordPress 站点也会在这一步加入参考状态。'
  say '历史异常记录会保留，不会删除。'
  say
  confirm_numeric '确认当前网站状态正常，并更新参考状态？' || return 0
  info '正在更新网站参考状态...'
  if ! helper baseline >/dev/null; then
    fail '参考状态更新失败；请先处理当前留证状态问题。'
    refresh_cache
    return 84
  fi
  refresh_cache
  ok '参考状态已更新 · 历史异常记录仍保留。'
}

disable_evidence() {
  require_root || return $?
  say '关闭后将停止每天自动检查。已有参考状态和历史证据继续保留。'
  say
  confirm_numeric '关闭网站入侵留证？' || return 0
  remove_scheduler
  refresh_cache
  ok '自动检查已关闭 · 历史证据未删除。'
}

enable_scheduler_only() {
  require_root || return $?
  info '正在开启每天自动检查...'
  local sched
  if ! sched="$(install_scheduler)"; then
    fail '自动任务创建失败；P07 已回滚本次调度文件。'
    return 83
  fi
  refresh_cache
  ok '每天自动检查已开启。'
}

menu() {
  local choice
  while true; do
    screen_clear
    show_status
    say
    if [[ "$IE_ENABLED" != 1 ]]; then
      say '1. 开启网站安全保护'
      say '0. 返回'
      say
      printf '请选择 [0-1]：'
      read -r choice || return 0
      case "$choice" in
        1) enable_evidence; pause_menu ;;
        0) return 0 ;;
        *) warn '无效选择，请输入 0-1。'; sleep 1 ;;
      esac
      continue
    fi
    local sched="$IE_SCHEDULER"
    say '1. 立即检查网站'
    say '2. 查看异常详情'
    say '3. 我确认当前网站正常，更新参考状态'
    case "$sched" in
      none) say '4. 开启每天自动检查' ;;
      broken) say '4. 修复每天自动检查' ;;
      *) say '4. 关闭每天自动检查' ;;
    esac
    say '0. 返回'
    say
    printf '请选择 [0-4]：'
    read -r choice || return 0
    case "$choice" in
      1) scan_now; pause_menu ;;
      2) screen_clear; show_report; pause_menu ;;
      3) rebuild_baseline; pause_menu ;;
      4)
        case "$sched" in
          none|broken) enable_scheduler_only ;;
          *) disable_evidence ;;
        esac
        pause_menu
        ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-4。'; sleep 1 ;;
    esac
  done
}

case "${1:-menu}" in
  menu) menu ;;
  status) show_status ;;
  refresh-cache) refresh_cache ;;
  enable) enable_evidence ;;
  scan) scan_now ;;
  scan-scheduled) scan_scheduled ;;
  report) show_report ;;
  rebaseline) rebuild_baseline ;;
  disable) disable_evidence ;;
  *) fail "未知入侵留证命令：${1:-}"; exit 2 ;;
esac
