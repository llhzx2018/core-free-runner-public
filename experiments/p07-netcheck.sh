#!/usr/bin/env bash
set -uo pipefail

APP="P07 NetCheck"
VERSION="0.4.0"
MODE="interactive"
DEMO=0
ASSUME_YES=0

while (($#)); do
  case "$1" in
    --demo) DEMO=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --quick) MODE="quick" ;;
    --china) MODE="china" ;;
    --global) MODE="global" ;;
    --ports) MODE="ports" ;;
    --report) MODE="report" ;;
    --history) MODE="history" ;;
    --compare) MODE="compare" ;;
    --self-test) MODE="selftest" ;;
    --version) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
    -h|--help)
      cat <<EOF
$APP $VERSION
Usage:
  p07-netcheck.sh
  p07-netcheck.sh --quick
  p07-netcheck.sh --china
  p07-netcheck.sh --global [--yes]
  p07-netcheck.sh --ports
  p07-netcheck.sh --report
  p07-netcheck.sh --history
  p07-netcheck.sh --compare
  p07-netcheck.sh --demo
EOF
      exit 0
      ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RESET=$'\033[0m'; BOLD=$'\033[1m'; DIM=$'\033[2m'
  CYAN=$'\033[38;5;45m'; BLUE=$'\033[38;5;39m'; GREEN=$'\033[38;5;48m'
  YELLOW=$'\033[38;5;220m'; ORANGE=$'\033[38;5;208m'; RED=$'\033[38;5;203m'
  MAGENTA=$'\033[38;5;141m'; GRAY=$'\033[38;5;245m'; WHITE=$'\033[38;5;255m'
else
  RESET=""; BOLD=""; DIM=""; CYAN=""; BLUE=""; GREEN=""; YELLOW=""; ORANGE=""
  RED=""; MAGENTA=""; GRAY=""; WHITE=""
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  STATE_BASE="/var/lib/p07-netcheck"
else
  STATE_BASE="${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/p07-netcheck"
fi

REPORT_DIR="$STATE_BASE/reports"
HISTORY_DIR="$STATE_BASE/history"
mkdir -p "$REPORT_DIR" "$HISTORY_DIR" 2>/dev/null || true

TMP_RESULT="$(mktemp -t p07-netcheck.XXXXXX 2>/dev/null || printf '/tmp/p07-netcheck.%s' "$$")"
: >"$TMP_RESULT" 2>/dev/null || true

cleanup(){ rm -f "$TMP_RESULT" 2>/dev/null || true; }
trap cleanup EXIT
trap 'cleanup; exit 130' INT TERM

clear_screen(){ [[ -t 1 ]] && clear 2>/dev/null || true; }
rule(){ printf '%s\n' '────────────────────────────────────────────────────────────────────────────'; }
pause(){ printf '\n%s按 Enter 返回...%s' "$GRAY" "$RESET"; read -r _ || true; }
status_color(){
  case "$1" in
    PASS|NORMAL|READY|LISTENING) printf '%s' "$GREEN" ;;
    RISK|WARN|PARTIAL|UNAVAILABLE|NOT_RUN) printf '%s' "$YELLOW" ;;
    HIGH_RISK|FAIL|TIMEOUT|DNS_FAILURE|TLS_FAILURE|CONNECTION_FAILED) printf '%s' "$RED" ;;
    *) printf '%s' "$GRAY" ;;
  esac
}
print_state(){
  local s="$1" c
  c="$(status_color "$s")"
  printf '%s%s%s' "$c" "$s" "$RESET"
}

get_os(){
  if [[ -r /etc/os-release ]]; then
    awk -F= '/^PRETTY_NAME=/{gsub(/^"|"$/,"",$2);print $2}' /etc/os-release
  else
    uname -s
  fi
}
get_cpu(){ awk -F: '/model name/{gsub(/^[ \t]+/,"",$2);print $2;exit}' /proc/cpuinfo 2>/dev/null || printf UNKNOWN; }
get_cores(){ getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || printf '?'; }
get_mem(){ free -h 2>/dev/null | awk '/^Mem:/{print $2" total · "$3" used"}' || printf '?'; }
get_disk(){ df -hP / 2>/dev/null | awk 'NR==2{print $2" total · "$4" free"}' || printf '?'; }
get_virt(){
  if command -v systemd-detect-virt >/dev/null 2>&1; then
    local v; v="$(systemd-detect-virt 2>/dev/null || true)"; printf '%s' "${v:-none}"
  else
    printf unknown
  fi
}
get_uptime(){ uptime -p 2>/dev/null | sed 's/^up //' || printf '?'; }
get_tcp_cc(){ sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || printf UNKNOWN; }
get_ip(){
  if (( DEMO )); then
    printf '103.123.45.67'
  elif command -v curl >/dev/null 2>&1; then
    curl -4fsS --connect-timeout 3 --max-time 5 https://api.ipify.org 2>/dev/null || printf UNKNOWN
  else
    printf UNKNOWN
  fi
}
mask_ip(){
  local ip="$1"
  if [[ "$ip" =~ ^([0-9]+\.[0-9]+)\.[0-9]+\.[0-9]+$ ]]; then printf '%s.x.x' "${BASH_REMATCH[1]}"; else printf '%s' "$ip"; fi
}

header(){
  local ip os
  ip="$(get_ip)"; os="$(get_os)"
  printf '%s%sP07 · NetCheck%s  %sv%s%s  %sIP %s%s  %s%s%s\n' \
    "$BOLD" "$CYAN" "$RESET" "$BLUE" "$VERSION" "$RESET" \
    "$GRAY" "$ip" "$RESET" "$DIM" "${os:0:38}" "$RESET"
  rule
}

main_menu(){
  clear_screen
  header
  printf '\n'
  printf '  %s1%s  %-22s %s%s\n' "$GREEN" "$RESET" '快速检测' '系统 / HTTPS / 网络基础' "$RESET"
  printf '  %s2%s  %-22s %s%s\n' "$RED" "$RESET" '中国访问 / IP 可用性' '大陆方向 / 三网参考 / 风险判断' "$RESET"
  printf '  %s3%s  %-22s %s%s\n' "$CYAN" "$RESET" '全球节点测速' 'Upload / Download / Latency' "$RESET"
  printf '  %s4%s  %-22s %s%s\n' "$ORANGE" "$RESET" '端口 / 服务' 'SSH / HTTP / HTTPS 本机监听' "$RESET"
  printf '  %s5%s  %-22s %s%s\n' "$MAGENTA" "$RESET" '历史 / 对比' '查看最近结果 / 对比两次中国检测' "$RESET"
  printf '  %s6%s  %-22s %s%s\n' "$BLUE" "$RESET" '生成报告' 'TXT + JSON，本机保存' "$RESET"
  printf '\n  %s0 退出%s\n' "$GRAY" "$RESET"
  rule
}

reset_results(){ : >"$TMP_RESULT" 2>/dev/null || true; }
record(){
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" "${10}" >>"$TMP_RESULT" 2>/dev/null || true
}

curl_reason(){
  case "$1" in
    0) printf NONE ;;
    6) printf DNS_FAILURE ;;
    7) printf CONNECTION_FAILED ;;
    28) printf TIMEOUT ;;
    35|51|58|60) printf TLS_FAILURE ;;
    47) printf REDIRECT_LOOP ;;
    *) printf CURL_ERROR_%s "$1" ;;
  esac
}

http_probe(){
  local group="$1" name="$2" url="$3"
  local tmp raw code conn total rc state reason
  tmp="$(mktemp -t p07-http.XXXXXX 2>/dev/null || printf '/tmp/p07-http.%s' "$$")"

  if (( DEMO )); then
    case "$name" in
      *电信*|*联通*|*移动*|*百度*|*腾讯*|*淘宝*)
        code=000; conn=timeout; total=timeout; rc=28; state=FAIL; reason=TIMEOUT ;;
      *)
        code=200; conn=0.031; total=0.115; rc=0; state=PASS; reason=NONE ;;
    esac
  elif ! command -v curl >/dev/null 2>&1; then
    code=NA; conn=NA; total=NA; rc=127; state=UNAVAILABLE; reason=CURL_NOT_INSTALLED
  else
    raw="$(curl -LsS -o /dev/null --connect-timeout 4 --max-time 8 \
      -w '%{http_code}|%{time_connect}|%{time_total}' "$url" 2>"$tmp")"
    rc=$?
    if [[ -z "$raw" ]]; then raw='000|timeout|timeout'; fi
    IFS='|' read -r code conn total <<<"$raw"
    if (( rc == 0 )) && [[ "$code" =~ ^[1-5][0-9][0-9]$ ]]; then
      state=PASS; reason=NONE
    else
      state=FAIL; reason="$(curl_reason "$rc")"
    fi
  fi
  rm -f "$tmp" 2>/dev/null || true
  record HTTP "$group" "$name" "$url" "$state" "$reason" "$code" "$conn" "$total" '-'
  printf '%s|%s|%s|%s|%s|%s\n' "$name" "$code" "$conn" "$total" "$state" "$reason"
}

print_probe_row(){
  local name="$1" code="$2" conn="$3" total="$4" state="$5" reason="$6"
  printf '  %-18s  HTTP %-3s  %-8s  %-8s  ' "$name" "$code" "$conn" "$total"
  print_state "$state"
  [[ "$reason" != NONE ]] && printf '  %s%s%s' "$GRAY" "$reason" "$RESET"
  printf '\n'
}

run_probe_group(){
  local group="$1"; shift
  local item name url code conn total state reason
  printf '%s%s%s\n' "$BOLD" "$group" "$RESET"
  for item in "$@"; do
    name="${item%%|*}"; url="${item#*|}"
    IFS='|' read -r name code conn total state reason < <(http_probe "$group" "$name" "$url")
    print_probe_row "$name" "$code" "$conn" "$total" "$state" "$reason"
  done
}

count_group(){ awk -F '\t' -v g="$1" -v s="$2" '$2==g&&$5==s{n++}END{print n+0}' "$TMP_RESULT" 2>/dev/null; }

quick_test(){
  reset_results; clear_screen; header
  printf '\n%s%s快速检测%s\n' "$GREEN" "$BOLD" "$RESET"; rule
  printf '  CPU       %s\n' "$(get_cpu)"
  printf '  vCPU      %s\n' "$(get_cores)"
  printf '  内存      %s\n' "$(get_mem)"
  printf '  磁盘      %s\n' "$(get_disk)"
  printf '  虚拟化    %s\n' "$(get_virt)"
  printf '  TCP       %s\n' "$(get_tcp_cc)"
  printf '  Uptime    %s\n\n' "$(get_uptime)"
  run_probe_group '海外基础' \
    'Cloudflare|https://www.cloudflare.com/' \
    'GitHub|https://github.com/'
  printf '\n'
  run_probe_group '大陆基础' \
    '百度|https://www.baidu.com/' \
    '腾讯|https://www.qq.com/'
  printf '\n%s快速检测不会写大量磁盘，也不会跑满带宽。%s\n' "$GRAY" "$RESET"
}

classify_china(){
  local overseas_pass="$1" mainland_fail="$2" carrier_fail="$3" mainland_pass="$4"
  if (( mainland_fail == 0 && mainland_pass >= 3 )); then
    printf NORMAL
  elif (( overseas_pass >= 2 && mainland_fail >= 3 && carrier_fail >= 2 )); then
    printf HIGH_RISK
  elif (( mainland_fail >= 1 )); then
    printf RISK
  else
    printf PARTIAL
  fi
}

save_china_history(){
  local verdict="$1" overseas_pass="$2" mainland_pass="$3" mainland_fail="$4" carrier_fail="$5"
  local ts file ip
  ts="$(date +%Y%m%d_%H%M%S)"
  file="$HISTORY_DIR/china_${ts}.json"
  ip="$(mask_ip "$(get_ip)")"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$file" "$VERSION" "$verdict" "$overseas_pass" "$mainland_pass" "$mainland_fail" "$carrier_fail" "$ip" <<'PY'
import json,sys,datetime
path,version,verdict,op,mp,mf,cf,ip=sys.argv[1:]
data={
  "schema_version":1,
  "module":"p07-netcheck",
  "version":version,
  "timestamp":datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
  "public_ip_masked":ip,
  "verdict":verdict,
  "overseas_pass":int(op),
  "mainland_pass":int(mp),
  "mainland_fail":int(mf),
  "carrier_fail":int(cf),
}
with open(path,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
PY
  else
    printf '{"version":"%s","verdict":"%s","overseas_pass":%s,"mainland_pass":%s,"mainland_fail":%s,"carrier_fail":%s}\n' \
      "$VERSION" "$verdict" "$overseas_pass" "$mainland_pass" "$mainland_fail" "$carrier_fail" >"$file" 2>/dev/null || true
  fi
}

print_china_verdict(){
  case "$1" in
    NORMAL)
      printf '\n%s%s综合判断：正常 ✓%s\n' "$GREEN" "$BOLD" "$RESET"
      printf '暂未发现明显的中国大陆方向异常。\n' ;;
    HIGH_RISK)
      printf '\n%s%s综合判断：高风险 ✗%s\n' "$RED" "$BOLD" "$RESET"
      printf '多个大陆方向失败，而海外对照正常。\n'
      printf '%s建议：正式迁移前优先换 IP / VPS，或继续做大陆→VPS反向探测。%s\n' "$YELLOW" "$RESET" ;;
    RISK)
      printf '\n%s%s综合判断：有风险 ⚠%s\n' "$YELLOW" "$BOLD" "$RESET"
      printf '部分大陆方向异常，当前证据不足以直接判定 IP 被封。\n' ;;
    *)
      printf '\n%s结果不完整，暂不下结论。%s\n' "$GRAY" "$RESET" ;;
  esac
  printf '%s注意：本机只能观察 VPS→中国；最强结论仍需要大陆→VPS探针。%s\n' "$GRAY" "$RESET"
}

china_quick(){
  reset_results; clear_screen; header
  printf '\n%s%s中国访问 / IP 快速检查%s\n' "$RED" "$BOLD" "$RESET"; rule
  printf '%s低影响：HTTPS/TLS 可达性 + 海外对照，不跑满带宽。%s\n\n' "$GRAY" "$RESET"

  run_probe_group '海外对照' \
    'Cloudflare|https://www.cloudflare.com/' \
    'GitHub|https://github.com/' \
    'Google|https://www.google.com/'
  printf '\n'
  run_probe_group '中国常用站点' \
    '百度|https://www.baidu.com/' \
    '腾讯|https://www.qq.com/' \
    '淘宝|https://www.taobao.com/'
  printf '\n'
  run_probe_group '中国三网门户参考' \
    '电信 189|https://www.189.cn/' \
    '联通 10010|https://www.10010.com/' \
    '移动 10086|https://www.10086.cn/'

  local op mp mf cf verdict
  op="$(count_group '海外对照' PASS)"
  mp=$(( $(count_group '中国常用站点' PASS) + $(count_group '中国三网门户参考' PASS) ))
  mf=$(( $(count_group '中国常用站点' FAIL) + $(count_group '中国三网门户参考' FAIL) ))
  cf="$(count_group '中国三网门户参考' FAIL)"
  verdict="$(classify_china "$op" "$mf" "$cf" "$mp")"
  print_china_verdict "$verdict"
  save_china_history "$verdict" "$op" "$mp" "$mf" "$cf"
}

find_speedtest(){
  if command -v speedtest >/dev/null 2>&1; then printf ookla
  elif command -v speedtest-cli >/dev/null 2>&1; then printf python
  else printf none
  fi
}

with_timeout(){
  local limit="$1"; shift
  if command -v timeout >/dev/null 2>&1; then timeout "$limit" "$@"; else "$@"; fi
}

speedtest_failure_reason(){
  local rc="$1" text="$2"
  if (( rc == 124 )); then printf TIMEOUT
  elif grep -qiE 'server.*not found|no servers|invalid server' <<<"$text"; then printf NODE_UNAVAILABLE
  elif grep -qiE 'resolve|dns' <<<"$text"; then printf DNS_FAILURE
  elif grep -qiE 'ssl|tls|certificate' <<<"$text"; then printf TLS_FAILURE
  elif grep -qiE 'connect|network|route|unreachable' <<<"$text"; then printf CONNECTION_FAILED
  elif (( rc != 0 )); then printf BACKEND_FAILURE
  else printf PARSE_ERROR
  fi
}

speedtest_node(){
  local id="$1" name="$2" group="$3"
  local backend raw parsed state up down lat reason rc
  backend="$(find_speedtest)"
  if (( DEMO )); then
    case "$name" in
      *Suzhou*|*Ningbo*) state=FAIL;up=-;down=-;lat=-;reason=TIMEOUT ;;
      *Los*) state=PASS;up=1180.24;down=1258.36;lat=0.89;reason=NONE ;;
      *Tokyo*) state=PASS;up=1022.15;down=980.72;lat=36.12;reason=NONE ;;
      *Singapore*) state=PASS;up=801.36;down=832.27;lat=62.18;reason=NONE ;;
      *Hong*) state=PASS;up=702.11;down=689.45;lat=48.37;reason=NONE ;;
      *) state=PASS;up=620.00;down=710.00;lat=90.00;reason=NONE ;;
    esac
  elif [[ "$backend" == none ]]; then
    state=UNAVAILABLE;up=-;down=-;lat=-;reason=SPEEDTEST_NOT_INSTALLED
  elif [[ "$backend" == ookla ]]; then
    raw="$(with_timeout 55s speedtest --progress=no --accept-license --accept-gdpr --format=json --server-id="$id" 2>&1)"
    rc=$?
    parsed=""
    if (( rc == 0 )) && [[ -n "$raw" ]] && command -v python3 >/dev/null 2>&1; then
      parsed="$(python3 - "$raw" <<'PY' 2>/dev/null || true
import json,sys
try:
 d=json.loads(sys.argv[1])
 print(f"PASS|{d['upload']['bandwidth']*8/1e6:.2f}|{d['download']['bandwidth']*8/1e6:.2f}|{d['ping']['latency']:.2f}|NONE")
except Exception:
 pass
PY
)"
    fi
    if [[ -n "$parsed" ]]; then
      IFS='|' read -r state up down lat reason <<<"$parsed"
    else
      state=FAIL;up=-;down=-;lat=-;reason="$(speedtest_failure_reason "$rc" "$raw")"
    fi
  else
    raw="$(with_timeout 55s speedtest-cli --server "$id" --json 2>&1)"
    rc=$?
    parsed=""
    if (( rc == 0 )) && [[ -n "$raw" ]] && command -v python3 >/dev/null 2>&1; then
      parsed="$(python3 - "$raw" <<'PY' 2>/dev/null || true
import json,sys
try:
 d=json.loads(sys.argv[1])
 print(f"PASS|{d['upload']/1e6:.2f}|{d['download']/1e6:.2f}|{d['ping']:.2f}|NONE")
except Exception:
 pass
PY
)"
    fi
    if [[ -n "$parsed" ]]; then
      IFS='|' read -r state up down lat reason <<<"$parsed"
    else
      state=FAIL;up=-;down=-;lat=-;reason="$(speedtest_failure_reason "$rc" "$raw")"
    fi
  fi
  record SPEED "$group" "$name" "$id" "$state" "$reason" "$up" "$down" "$lat" "$backend"
  printf '%s|%s|%s|%s|%s|%s\n' "$name" "$state" "$up" "$down" "$lat" "$reason"
}

print_speed_row(){
  local name="$1" state="$2" up="$3" down="$4" lat="$5" reason="$6"
  printf '  %-18s  ↑%-9s  ↓%-9s  %-8s  ' "$name" "$up" "$down" "$lat"
  print_state "$state"
  [[ "$reason" != NONE ]] && printf '  %s%s%s' "$GRAY" "$reason" "$RESET"
  printf '\n'
}

confirm_heavy_network(){
  (( ASSUME_YES || DEMO )) && return 0
  printf '%s此测试会产生较大上传/下载流量，并可能影响正在运行的网站。%s\n' "$YELLOW" "$RESET"
  printf '继续？[y/N]：'
  local yn; read -r yn || return 1
  [[ "$yn" =~ ^[Yy]$ ]]
}

global_test(){
  reset_results; clear_screen; header
  printf '\n%s%s全球节点测速%s\n' "$CYAN" "$BOLD" "$RESET"; rule
  local backend; backend="$(find_speedtest)"
  if [[ "$backend" == none && $DEMO -eq 0 ]]; then
    printf '%s未检测到 speedtest / speedtest-cli。%s\n' "$YELLOW" "$RESET"
    printf '为保证供应链安全，本脚本不会静默下载未校验可执行文件。\n'
    return
  fi
  confirm_heavy_network || { printf '已取消。\n'; return; }
  printf '  %-18s  %-11s %-11s %-9s  状态\n' '节点' '上传Mbps' '下载Mbps' '延迟ms'
  local name state up down lat reason
  while IFS='|' read -r name state up down lat reason; do
    print_speed_row "$name" "$state" "$up" "$down" "$lat" "$reason"
  done < <(
    speedtest_node 7190  'Los Angeles US' GLOBAL
    speedtest_node 22288 'Dallas US' GLOBAL
    speedtest_node 64420 'Montreal CA' GLOBAL
    speedtest_node 61933 'Paris FR' GLOBAL
    speedtest_node 41423 'Amsterdam NL' GLOBAL
    speedtest_node 5396  'Suzhou CN' GLOBAL
    speedtest_node 59387 'Ningbo CN' GLOBAL
    speedtest_node 32155 'Hong Kong' GLOBAL
    speedtest_node 13623 'Singapore SG' GLOBAL
    speedtest_node 65092 'Taipei' GLOBAL
    speedtest_node 48463 'Tokyo JP' GLOBAL
  )
  printf '\n%s单个大陆 Speedtest 节点失败不能单独判定 IP 被封。%s\n' "$GRAY" "$RESET"
}

china_speedtest(){
  reset_results; clear_screen; header
  printf '\n%s%s中国大陆 Speedtest 参考%s\n' "$RED" "$BOLD" "$RESET"; rule
  local backend; backend="$(find_speedtest)"
  if [[ "$backend" == none && $DEMO -eq 0 ]]; then
    printf '%s未检测到 Speedtest 后端，本项不可用。%s\n' "$YELLOW" "$RESET"; return
  fi
  confirm_heavy_network || { printf '已取消。\n'; return; }
  printf '  %-18s  %-11s %-11s %-9s  状态\n' '节点' '上传Mbps' '下载Mbps' '延迟ms'
  local name state up down lat reason
  while IFS='|' read -r name state up down lat reason; do
    print_speed_row "$name" "$state" "$up" "$down" "$lat" "$reason"
  done < <(
    speedtest_node 5396 'Suzhou CN' CHINA_SPEED
    speedtest_node 59387 'Ningbo CN' CHINA_SPEED
  )
}

china_menu(){
  local c
  while true; do
    clear_screen; header
    printf '\n%s%s中国访问 / IP 可用性%s\n' "$RED" "$BOLD" "$RESET"; rule
    printf '  %s1%s  快速检查（推荐）        HTTPS/TLS + 三网门户 + 海外对照\n' "$GREEN" "$RESET"
    printf '  %s2%s  苏州 / 宁波测速参考    会占用较多带宽\n' "$RED" "$RESET"
    printf '  %s3%s  查看历史结果           最近中国访问判定\n' "$MAGENTA" "$RESET"
    printf '  %s4%s  对比最近两次           看风险是否变化\n' "$CYAN" "$RESET"
    printf '\n  %s0 返回%s\n' "$GRAY" "$RESET"; rule
    printf '请选择 [0-4]：'; read -r c || return
    case "$c" in
      1) china_quick; pause ;;
      2) china_speedtest; pause ;;
      3) history_list; pause ;;
      4) compare_last_two; pause ;;
      0) return ;;
      *) sleep 1 ;;
    esac
  done
}

port_test(){
  clear_screen; header
  printf '\n%s%s端口 / 服务检查%s\n' "$ORANGE" "$BOLD" "$RESET"; rule
  if ! command -v ss >/dev/null 2>&1; then
    printf '%s未找到 ss，无法读取本机监听端口。%s\n' "$YELLOW" "$RESET"; return
  fi
  local item p label state
  for item in '22:SSH' '80:HTTP' '443:HTTPS'; do
    p="${item%%:*}"; label="${item#*:}"
    if ss -lnt 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)$p$"; then state=LISTENING; else state=NOT_LISTENING; fi
    printf '  %-8s TCP %-5s  ' "$label" "$p"; print_state "$state"; printf '\n'
  done
  printf '\n%s这里只检查本机监听，不代表中国大陆外部一定可以访问。%s\n' "$GRAY" "$RESET"
}

history_list(){
  clear_screen; header
  printf '\n%s%s中国访问历史%s\n' "$MAGENTA" "$BOLD" "$RESET"; rule
  if ! compgen -G "$HISTORY_DIR/china_*.json" >/dev/null 2>&1; then
    printf '暂无历史记录。\n'; return
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$HISTORY_DIR" <<'PY'
import json,glob,os,sys
files=sorted(glob.glob(os.path.join(sys.argv[1],"china_*.json")), reverse=True)[:10]
print("  时间                     结论        大陆通过/失败  三网失败")
for p in files:
    try:
        d=json.load(open(p,encoding="utf-8"))
        ts=d.get("timestamp","")[:19].replace("T"," ")
        print(f"  {ts:<24} {d.get('verdict','?'):<11} {d.get('mainland_pass','?')}/{d.get('mainland_fail','?'):<10} {d.get('carrier_fail','?')}")
    except Exception:
        pass
PY
  else
    ls -1t "$HISTORY_DIR"/china_*.json | head -10
  fi
}

compare_last_two(){
  clear_screen; header
  printf '\n%s%s最近两次中国访问对比%s\n' "$CYAN" "$BOLD" "$RESET"; rule
  if ! command -v python3 >/dev/null 2>&1; then
    printf '需要 python3 才能生成结构化对比。\n'; return
  fi
  python3 - "$HISTORY_DIR" <<'PY'
import json,glob,os,sys
files=sorted(glob.glob(os.path.join(sys.argv[1],"china_*.json")), reverse=True)[:2]
if len(files)<2:
    print("至少需要两次中国访问快速检查。")
    raise SystemExit
rows=[]
for p in reversed(files):
    with open(p,encoding="utf-8") as f: rows.append(json.load(f))
a,b=rows
def short(d):
    return {
      "time":d.get("timestamp","")[:19].replace("T"," "),
      "verdict":d.get("verdict","?"),
      "pass":d.get("mainland_pass","?"),
      "fail":d.get("mainland_fail","?"),
      "carrier":d.get("carrier_fail","?"),
    }
a,b=short(a),short(b)
print(f"  较早  {a['time']}  {a['verdict']}  大陆 {a['pass']}通过/{a['fail']}失败  三网失败 {a['carrier']}")
print(f"  最近  {b['time']}  {b['verdict']}  大陆 {b['pass']}通过/{b['fail']}失败  三网失败 {b['carrier']}")
if a["verdict"]==b["verdict"]:
    print("\n  结论：风险等级未变化。")
else:
    print(f"\n  结论：{a['verdict']} → {b['verdict']}")
PY
}

save_report(){
  local ts txt json ip
  ts="$(date +%Y%m%d_%H%M%S)"
  txt="$REPORT_DIR/netcheck_${ts}.txt"
  json="$REPORT_DIR/netcheck_${ts}.json"
  ip="$(get_ip)"
  {
    printf 'P07 NetCheck %s\n' "$VERSION"
    printf 'time=%s\n' "$(date -Is 2>/dev/null || date)"
    printf 'public_ip=%s\n' "$ip"
    printf 'os=%s\n' "$(get_os)"
    printf 'cpu=%s\n' "$(get_cpu)"
    printf 'cores=%s\n' "$(get_cores)"
    printf 'memory=%s\n' "$(get_mem)"
    printf 'disk=%s\n' "$(get_disk)"
    printf 'virtualization=%s\n' "$(get_virt)"
    printf 'tcp_congestion=%s\n' "$(get_tcp_cc)"
    printf 'speedtest_backend=%s\n' "$(find_speedtest)"
    printf 'note=China outbound checks are signals only; strongest verdict requires mainland-origin probes.\n'
  } >"$txt" 2>/dev/null || { printf '无法写入报告目录：%s\n' "$REPORT_DIR"; return 1; }
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$json" "$VERSION" "$(mask_ip "$ip")" "$(get_os)" "$(get_cpu)" "$(get_cores)" "$(get_mem)" "$(get_disk)" "$(get_virt)" "$(get_tcp_cc)" "$(find_speedtest)" <<'PY'
import json,sys,datetime
path,version,ip,osname,cpu,cores,mem,disk,virt,tcp,backend=sys.argv[1:]
data={
 "schema_version":1,
 "module":"p07-netcheck",
 "version":version,
 "timestamp":datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
 "public_ip_masked":ip,
 "system":{"os":osname,"cpu":cpu,"cores":cores,"memory":mem,"disk":disk,"virtualization":virt,"tcp_congestion":tcp},
 "speedtest_backend":backend
}
with open(path,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
PY
  fi
  printf '%s报告已保存%s\n  %s\n' "$GREEN" "$RESET" "$txt"
  [[ -f "$json" ]] && printf '  %s\n' "$json"
}

report_screen(){
  clear_screen; header
  printf '\n%s%s生成测试报告%s\n' "$MAGENTA" "$BOLD" "$RESET"; rule
  save_report
}

self_test(){
  local fail=0
  [[ "$(classify_china 3 0 0 6)" == NORMAL ]] || fail=1
  [[ "$(classify_china 3 4 3 2)" == HIGH_RISK ]] || fail=1
  [[ "$(classify_china 3 1 0 5)" == RISK ]] || fail=1
  [[ "$(curl_reason 6)" == DNS_FAILURE ]] || fail=1
  [[ "$(curl_reason 28)" == TIMEOUT ]] || fail=1
  [[ "$(speedtest_failure_reason 124 '')" == TIMEOUT ]] || fail=1
  if (( fail )); then printf 'SELF_TEST=FAIL\n'; return 1; else printf 'SELF_TEST=PASS\n'; fi
}

run_interactive(){
  local c
  while true; do
    main_menu
    printf '请选择 [0-6]：'; read -r c || break
    case "$c" in
      1) quick_test; pause ;;
      2) china_menu ;;
      3) global_test; pause ;;
      4) port_test; pause ;;
      5) history_list; printf '\n'; compare_last_two; pause ;;
      6) report_screen; pause ;;
      0) clear_screen; printf '%s安全退出 P07 NetCheck。%s\n' "$GRAY" "$RESET"; break ;;
      *) sleep 1 ;;
    esac
  done
}

case "$MODE" in
  quick) quick_test ;;
  china) china_quick ;;
  global) global_test ;;
  ports) port_test ;;
  report) report_screen ;;
  history) history_list ;;
  compare) compare_last_two ;;
  selftest) self_test ;;
  *) run_interactive ;;
esac
