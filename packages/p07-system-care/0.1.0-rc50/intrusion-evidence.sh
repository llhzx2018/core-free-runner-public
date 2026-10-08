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
  command -v python3 >/dev/null 2>&1 || { fail '缺少 python3，无法运行WordPress 网站安全。'; return 80; }
  [[ -r "$PY_HELPER" ]] || { fail '网站安全组件不完整。'; return 81; }
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
Description=WordPress website security scan
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
Description=Daily WordPress website security scan

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
# WordPress 网站安全（由服务器工具箱管理）
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
      say '失败原因   异常历史记录不完整或损坏'
      ;;
    StateScanCorruptError|JSONDecodeError) say '失败原因   网站安全状态文件损坏' ;;
    StateBaselineMissingError|StateGenerationMissingError|StateGenerationMismatchError|StateScanStateMissingError|StateScanStateInvalidError) say '失败原因   参考状态不一致，请确认网站当前正常后更新参考状态' ;;
    ResourceBudgetConfigError) say '失败原因   网站安全扫描配置无效' ;;
    StatusUnavailableError) say '失败原因   网站安全状态暂时无法读取' ;;
    '-'|'') ;;
    *) say '失败原因   本次检查没有取得明确原因，请稍后重试' ;;
  esac
}

wp_display_time() {
  local v="${1:--}" readable
  if [[ "$v" == "-" || -z "$v" ]]; then printf '暂无'; return 0; fi
  readable="$(TZ=Asia/Shanghai date -d "$v" '+%m-%d %H:%M' 2>/dev/null || true)"
  [[ -n "$readable" ]] && printf '%s' "$readable" || printf '%s' "$v"
}

show_status() {
  refresh_cache
  local sched="$IE_SCHEDULER"
  say "${C_BOLD}WordPress 网站安全${C_RESET}"
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
        printf '网站安全   %b有文件变化待核实%b\n' "$C_YELLOW" "$C_RESET"
      else
        printf '网站安全   %b需查看%b\n' "$C_YELLOW" "$C_RESET"
      fi
      say '下一步     选择 5 查看文件变化及排查建议'
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

  say "最近检查   $(wp_display_time "$IE_LAST_SCAN")（北京时间）"
  if [[ "$IE_STATUS" == ATTENTION ]]; then
    say "历史变更   ${IE_EVENTS} 条（累计记录，不代表本次新增或已经入侵）"
    say '处理建议   先核实文件变更来源，不要直接更新参考状态'
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

run_baseline_helper() {
  BASELINE_ERROR='UnknownError'
  local output rc line
  set +e
  output="$(helper baseline 2>&1)"
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    return 0
  fi
  while IFS= read -r line; do
    case "$line" in
      P07_IE_ERROR=*) BASELINE_ERROR="${line#P07_IE_ERROR=}" ;;
    esac
  done <<< "$output"
  return "$rc"
}

show_baseline_failure() {
  case "$BASELINE_ERROR" in
    UnsupportedWordPressLayoutError)
      fail '识别到 WordPress，但站点目录不符合 工具的安全读取规则。'
      say '说明       工具不会跟随不安全的 WordPress 配置文件（wp-config.php）/ 站点路径，也不会建立半套参考状态。'
      ;;
    ScanBudgetExceededError)
      fail '首次参考状态超过安全资源上限，已停止。'
      say '说明       没有建立不完整参考状态，也没有创建自动任务。'
      ;;
    EvidenceCapacityExceededError|StateEventsMissingError|StateEventsCorruptError|StateEventCountMismatchError)
      fail '已有留证历史状态不完整，工具拒绝覆盖历史证据。'
      ;;
    ValueError)
      fail '没有识别到可安全建立参考状态的 WordPress 站点，或站点目录结构不符合规则。'
      say '说明       已停止而不是猜目录；没有创建自动任务。'
      ;;
    FileNotFoundError)
      fail '建立参考状态时站点文件发生缺失或变化，请稍后再试。'
      ;;
    *)
      fail '检查基准建立失败；没有修改网站文件。'
      say '说明       没有创建自动任务。'
      ;;
  esac
}

enable_evidence() {
  require_root || return $?
  require_python || return $?
  say '工具会优先读取网站面板（CloudPanel）中的已知站点，并把当前 WordPress 文件状态保存为以后比较用的参考状态。'
  say '这不是木马扫描，不能证明当前站点没有已经存在的问题。'
  say '开启后每天静默检查；不会修改网站，也不会自动删除文件。'
  say
  confirm_numeric '开启WordPress 网站安全？' || return 0
  info '正在建立网站文件参考状态...'
  if ! run_baseline_helper; then
    show_baseline_failure
    return 82
  fi
  local sched
  if ! sched="$(install_scheduler)"; then
    fail '参考状态已建立，但自动任务创建失败；已回滚本次调度文件。'
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
    warn "发现需要核实的文件变化 · 历史累计 ${IE_EVENTS} 条"
    if [[ "$IE_UNBASELINED" =~ ^[0-9]+$ ]] && (( IE_UNBASELINED > 0 )); then
      say "另有 ${IE_UNBASELINED} 个新 WordPress 站点尚未纳入参考状态；工具不会自动信任它们。"
    fi
    say
    say '核实摘要（更多文件请通过菜单 5 查看）：'
    show_summary
    say
    ui_note '文件变化不等于入侵；核实更新来源之前不要更新可信基线。'
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

show_summary() {
  require_root || return $?
  require_python || return $?
  helper report --summary
}

show_report() {
  require_root || return $?
  require_python || return $?
  local page=1 pages=1 choice
  pages="$(helper report --pages)" || return $?
  [[ "$pages" =~ ^[1-9][0-9]*$ ]] || { fail '异常分页信息读取失败，原始证据没有修改。'; return 20; }
  while true; do
    screen_clear
    helper report --triage --page "$page" || return $?
    say
    printf '按 Enter 返回'
    if (( page < pages )); then printf '  ·  N 下一页'; fi
    if (( page > 1 )); then printf '  ·  P 上一页'; fi
    printf '  ·  R 查看原始请求线索：'
    read -r choice || return 0
    case "$choice" in
      [Nn]) if (( page < pages )); then page=$((page+1)); fi ;;
      [Pp]) if (( page > 1 )); then page=$((page-1)); fi ;;
      [Rr])
        screen_clear
        helper report --limit 20 || return $?
        say
        ui_note '这里是原始线索，不是已确认的入侵证据。'
        pause_menu
        ;;
      '') return 0 ;;
      *) warn '请输入 N、P、R 或直接按 Enter 返回。' ;;
    esac
  done
}

rebuild_baseline() {
  require_root || return $?
  refresh_cache
  # A failed/unavailable status is not evidence of zero historical events.
  # Require a trustworthy status and numeric event count before any baseline write.
  if [[ "$IE_ENABLED" != 1 || ! "$IE_STATUS" =~ ^(NORMAL|ATTENTION)$ || ! "$IE_EVENTS" =~ ^(0|[1-9][0-9]*)$ ]]; then
    fail '网站安全状态或历史记录数量无法确认；已停止更新参考状态。'
    return 78
  fi
  say '更新参考状态（高风险操作）'
  say
  if [[ "$IE_EVENTS" =~ ^[1-9][0-9]*$ ]]; then
    warn "当前还有 ${IE_EVENTS} 条历史文件变更。此操作不会证明文件安全。"
    say '你必须先核实 WordPress 核心及插件更新来源、文件校验结果。'
    say '操作后新扫描会与当前文件作比较；旧事件继续保留。'
    say
    [[ -t 0 ]] || { fail '需要终端交互确认。'; return 78; }
    local entered
    printf '如果已逐项核实，请输入历史记录数量 %s 继续（其它输入取消）：' "$IE_EVENTS"
    read -r entered || return 78
    if [[ "$entered" != "$IE_EVENTS" ]]; then
      warn '已取消，没有更新参考状态。'
      return 0
    fi
  else
    say '当前仍需确认网站文件状态可接受，才能更新比较参考。'
    say '原有历史证据不会删除；工具不能证明网站没有木马。'
  fi
  say
  confirm_numeric '已核实文件与更新来源，确认更新参考状态？' || return 0
  info '正在更新网站参考状态...'
  if ! run_baseline_helper; then
    show_baseline_failure
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
  confirm_numeric '关闭WordPress 网站安全？' || return 0
  remove_scheduler
  refresh_cache
  ok '自动检查已关闭 · 历史证据未删除。'
}

enable_scheduler_only() {
  require_root || return $?
  info '正在开启每天自动检查...'
  local sched
  if ! sched="$(install_scheduler)"; then
    fail '自动任务创建失败；已回滚本次调度文件。'
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
    say '2. 查看异常摘要'
    say '3. 已核实异常后更新参考状态'
    case "$sched" in
      none) say '4. 开启每天自动检查' ;;
      broken) say '4. 修复每天自动检查' ;;
      *) say '4. 关闭每天自动检查' ;;
    esac
    say '5. 查看文件变化及排查建议'
    say '0. 返回'
    say
    printf '请选择 [0-5]：'
    read -r choice || return 0
    case "$choice" in
      1) screen_clear; scan_now; pause_menu ;;
      2) screen_clear; show_summary; pause_menu ;;
      3) screen_clear; rebuild_baseline; pause_menu ;;
      4)
        case "$sched" in
          none|broken) enable_scheduler_only ;;
          *) disable_evidence ;;
        esac
        pause_menu
        ;;
      5) screen_clear; show_report ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-5。'; sleep 1 ;;
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
  report-summary) show_summary ;;
  rebaseline) rebuild_baseline ;;
  disable) disable_evidence ;;
  *) fail "未知入侵留证命令：${1:-}"; exit 2 ;;
esac
