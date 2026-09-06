#!/usr/bin/env bash
set -uo pipefail
APP="P07 NetCheck"; VERSION="0.3.0"; DEMO=0; MODE="interactive"
case "${1:-}" in
  --demo) DEMO=1;; --quick) MODE=quick;; --china) MODE=china;; --global) MODE=global;; --ports) MODE=ports;; --report) MODE=report;; --self-test) MODE=selftest;;
  --version) printf '%s %s\n' "$APP" "$VERSION"; exit 0;;
  -h|--help) cat <<EOF
$APP $VERSION
Usage: p07-netcheck.sh [--demo|--quick|--china|--global|--ports|--report|--self-test|--version]
EOF
  exit 0;;
esac
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RESET=$'\033[0m'; BOLD=$'\033[1m'; CYAN=$'\033[38;5;45m'; BLUE=$'\033[38;5;39m'; GREEN=$'\033[38;5;48m'; YELLOW=$'\033[38;5;220m'; ORANGE=$'\033[38;5;208m'; RED=$'\033[38;5;203m'; MAGENTA=$'\033[38;5;141m'; GRAY=$'\033[38;5;245m'; WHITE=$'\033[38;5;255m'; BG_GREEN=$'\033[48;5;22m'; BG_YELLOW=$'\033[48;5;58m'; BG_RED=$'\033[48;5;52m'
else
  RESET=""; BOLD=""; CYAN=""; BLUE=""; GREEN=""; YELLOW=""; ORANGE=""; RED=""; MAGENTA=""; GRAY=""; WHITE=""; BG_GREEN=""; BG_YELLOW=""; BG_RED=""
fi
STATE_BASE="${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/p07-netcheck"; [[ ${EUID:-$(id -u)} -eq 0 ]] && STATE_BASE="/var/lib/p07-netcheck"
REPORT_DIR="$STATE_BASE/reports"; mkdir -p "$REPORT_DIR" 2>/dev/null || true
TMP_RESULT="$(mktemp -t p07-netcheck.XXXXXX 2>/dev/null || printf '/tmp/p07-netcheck.%s' "$$")"; : >"$TMP_RESULT" 2>/dev/null || true
cleanup(){ rm -f "$TMP_RESULT" 2>/dev/null || true; }
on_signal(){ cleanup; exit 130; }
trap cleanup EXIT; trap on_signal INT TERM
clear_screen(){ [[ -t 1 ]] && clear 2>/dev/null || true; }
rule(){ printf '%s\n' '──────────────────────────────────────────────────────────────────────────────'; }
pause(){ printf '\n%s按 Enter 返回菜单...%s' "$GRAY" "$RESET"; read -r _ || true; }
panel(){ local c="$1" k="$2" t="$3" d="$4"; printf '%s╭────────────────────────────────────────────────────────────────────────────╮%s\n' "$c" "$RESET"; printf '%s│%s  %s%s[%s] %s%s  %s\n' "$c" "$RESET" "$BOLD" "$c" "$k" "$t" "$RESET" "$d"; printf '%s╰────────────────────────────────────────────────────────────────────────────╯%s\n' "$c" "$RESET"; }
get_os(){ if [[ -r /etc/os-release ]]; then awk -F= '/^PRETTY_NAME=/{gsub(/^"|"$/,"",$2);print $2}' /etc/os-release; else uname -s; fi; }
get_cpu(){ awk -F: '/model name/{gsub(/^[ \t]+/,"",$2);print $2;exit}' /proc/cpuinfo 2>/dev/null || printf UNKNOWN; }
get_cores(){ getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || printf '?'; }
get_mem(){ free -h 2>/dev/null | awk '/^Mem:/{print $2}' || printf '?'; }
get_disk(){ df -hP / 2>/dev/null | awk 'NR==2{print $2" total · "$4" free"}' || printf '?'; }
get_virt(){ if command -v systemd-detect-virt >/dev/null 2>&1; then local v; v="$(systemd-detect-virt 2>/dev/null || true)"; printf '%s' "${v:-none}"; else printf unknown; fi; }
get_uptime(){ uptime -p 2>/dev/null | sed 's/^up //' || printf '?'; }
get_tcp_cc(){ sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || printf UNKNOWN; }
get_ip(){ if (( DEMO )); then printf '103.123.45.67'; elif command -v curl >/dev/null 2>&1; then curl -4fsS --connect-timeout 3 --max-time 5 https://api.ipify.org 2>/dev/null || printf UNKNOWN; else printf UNKNOWN; fi; }
header(){ local ip os; ip="$(get_ip)"; os="$(get_os)"; printf '%s%s╭────────────────────────────────────────────────────────────────────────────╮%s\n' "$BOLD" "$BLUE" "$RESET"; printf '%s│%s  %sP07 · NetCheck%s  服务器网络 · 中国访问 · IP 可用性\n' "$BLUE" "$RESET" "$CYAN$BOLD" "$RESET"; printf '%s│%s  v%-7s  IP %-15s  %s\n' "$BLUE" "$RESET" "$VERSION" "$ip" "${os:0:44}"; printf '%s%s╰────────────────────────────────────────────────────────────────────────────╯%s\n' "$BOLD" "$BLUE" "$RESET"; }
main_menu(){ clear_screen; header; printf '\n'; panel "$GREEN" 1 '快速检测' '低影响 · 系统 / HTTPS / 网络基础'; panel "$RED" 2 '中国访问 / IP' '大陆方向 · 三网参考 · 风险判断'; panel "$CYAN" 3 '全球节点测速' 'Speedtest 已安装时可用'; panel "$ORANGE" 4 '端口 / 服务' 'SSH / HTTP / HTTPS 本机监听'; panel "$MAGENTA" 5 '生成测试报告' '保存 TXT + JSON 到本机，不上传'; printf '%s  [0] 退出%s\n' "$GRAY" "$RESET"; rule; }
reset_results(){ : >"$TMP_RESULT" 2>/dev/null || true; }
record(){ printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" >>"$TMP_RESULT" 2>/dev/null || true; }
http_reachable(){ [[ "$1" =~ ^[1-5][0-9][0-9]$ ]]; }
http_probe(){ local group="$1" name="$2" url="$3" raw code conn total state; if (( DEMO )); then case "$name" in *电信*|*联通*|*移动*|*百度*|*腾讯*) code=000;conn=timeout;total=timeout;state=FAIL;; *) code=200;conn=0.031;total=0.115;state=PASS;; esac; elif ! command -v curl >/dev/null 2>&1; then code=NA;conn=NA;total=NA;state=UNAVAILABLE; else raw="$(curl -LsS -o /dev/null --connect-timeout 4 --max-time 8 -w '%{http_code}|%{time_connect}|%{time_total}' "$url" 2>/dev/null || true)"; [[ -n "$raw" ]] || raw='000|timeout|timeout'; IFS='|' read -r code conn total <<<"$raw"; if http_reachable "$code"; then state=PASS; else state=FAIL; fi; fi; record HTTP "$group" "$name" "$url" "$state" "$code" "$conn" "$total" ''; printf '%s|%s|%s|%s|%s\n' "$name" "$code" "$conn" "$total" "$state"; }
print_probe_row(){ local name="$1" code="$2" conn="$3" total="$4" state="$5" c; case "$state" in PASS)c="$GREEN";;FAIL)c="$RED";;*)c="$GRAY";;esac; printf '  %-20s HTTP %-4s connect %-8s total %-8s %s%-11s%s\n' "$name" "$code" "$conn" "$total" "$c" "$state" "$RESET"; }
run_probe_group(){ local group="$1"; shift; local item name url code conn total state; printf '%s%s%s\n' "$BOLD" "$group" "$RESET"; for item in "$@"; do name="${item%%|*}"; url="${item#*|}"; IFS='|' read -r name code conn total state < <(http_probe "$group" "$name" "$url"); print_probe_row "$name" "$code" "$conn" "$total" "$state"; done; }
count_group(){ awk -F '\t' -v g="$1" -v s="$2" '$2==g&&$5==s{n++}END{print n+0}' "$TMP_RESULT" 2>/dev/null; }
quick_test(){ reset_results; clear_screen; header; printf '\n%s%s⚡ 快速检测%s\n' "$GREEN" "$BOLD" "$RESET"; rule; printf '  CPU       %s\n  核心      %s vCPU\n  内存      %s\n  磁盘      %s\n  虚拟化    %s\n  TCP       %s\n  运行时间  %s\n\n' "$(get_cpu)" "$(get_cores)" "$(get_mem)" "$(get_disk)" "$(get_virt)" "$(get_tcp_cc)" "$(get_uptime)"; run_probe_group '海外基础' 'Cloudflare|https://www.cloudflare.com/' 'GitHub|https://github.com/'; printf '\n'; run_probe_group '大陆基础' '百度|https://www.baidu.com/' '腾讯|https://www.qq.com/'; printf '\n%s快速检测完成；不会跑满磁盘或带宽。%s\n' "$GRAY" "$RESET"; }
classify_china(){ local op="$1" cp="$2" cf="$3" carrier_fail="$4"; if (( cf==0 )); then printf NORMAL; elif (( op>=2 && carrier_fail>=2 && cf>=3 )); then printf HIGH_RISK; elif (( cf>=1 )); then printf RISK; else printf PARTIAL; fi; }
print_china_verdict(){ case "$1" in NORMAL) printf '\n%s%s  综合判断：正常 ✓  %s\n暂未发现明显大陆方向异常。\n' "$BG_GREEN" "$WHITE$BOLD" "$RESET";; HIGH_RISK) printf '\n%s%s  综合判断：高风险 ✗  %s\n多个大陆方向失败，而海外对照正常。\n%s建议：迁移正式网站前优先换 IP / VPS，或继续做大陆三网反向探测。%s\n' "$BG_RED" "$WHITE$BOLD" "$RESET" "$YELLOW" "$RESET";; RISK) printf '\n%s%s  综合判断：有风险 ⚠  %s\n部分大陆方向异常，证据不足以直接判断 IP 被禁用。\n' "$BG_YELLOW" "$WHITE$BOLD" "$RESET";; *) printf '\n结果不完整，暂不下结论。\n';; esac; printf '%s说明：本机只观察 VPS → 中国；最强结论需要大陆 → VPS 外部探针。%s\n' "$GRAY" "$RESET"; }
china_test(){ reset_results; clear_screen; header; printf '\n%s%s🌐 中国访问 / IP 可用性%s\n' "$RED" "$BOLD" "$RESET"; rule; printf '%s低影响模式：HTTPS/TLS 可达性 + 海外对照，不跑满带宽。%s\n\n' "$GRAY" "$RESET"; run_probe_group '海外对照' 'Cloudflare|https://www.cloudflare.com/' 'GitHub|https://github.com/' 'Google|https://www.google.com/'; printf '\n'; run_probe_group '中国常用站点' '百度|https://www.baidu.com/' '腾讯|https://www.qq.com/' '淘宝|https://www.taobao.com/'; printf '\n'; run_probe_group '中国三网门户参考' '电信 189|https://www.189.cn/' '联通 10010|https://www.10010.com/' '移动 10086|https://www.10086.cn/'; local op cp cf car verdict; op="$(count_group '海外对照' PASS)"; cp=$(( $(count_group '中国常用站点' PASS)+$(count_group '中国三网门户参考' PASS) )); cf=$(( $(count_group '中国常用站点' FAIL)+$(count_group '中国三网门户参考' FAIL) )); car="$(count_group '中国三网门户参考' FAIL)"; verdict="$(classify_china "$op" "$cp" "$cf" "$car")"; print_china_verdict "$verdict"; printf '\n'; speedtest_china_summary; }
find_speedtest(){ if command -v speedtest >/dev/null 2>&1; then printf ookla; elif command -v speedtest-cli >/dev/null 2>&1; then printf python; else printf none; fi; }
with_timeout(){ local s="$1"; shift; if command -v timeout >/dev/null 2>&1; then timeout "$s" "$@"; else "$@"; fi; }
speedtest_node(){ local id="$1" name="$2" group="$3" backend raw parsed state up down lat; backend="$(find_speedtest)"; if (( DEMO )); then case "$name" in *Suzhou*|*Ningbo*) state=FAIL;up=-;down=-;lat=-;;*Los*)state=PASS;up=1180.24;down=1258.36;lat=0.89;;*Tokyo*)state=PASS;up=1022.15;down=980.72;lat=36.12;;*Singapore*)state=PASS;up=801.36;down=832.27;lat=62.18;;*Hong*)state=PASS;up=702.11;down=689.45;lat=48.37;;*)state=PASS;up=620.00;down=710.00;lat=90.00;;esac; elif [[ "$backend" == none ]]; then state=UNAVAILABLE;up=-;down=-;lat=-; elif [[ "$backend" == ookla ]]; then raw="$(with_timeout 50s speedtest --progress=no --accept-license --accept-gdpr --format=json --server-id="$id" 2>/dev/null || true)"; parsed=""; if [[ -n "$raw" ]] && command -v python3 >/dev/null 2>&1; then parsed="$(python3 - "$raw" <<'PY' 2>/dev/null || true
import json,sys
try:
 d=json.loads(sys.argv[1]);print(f"PASS|{d['upload']['bandwidth']*8/1e6:.2f}|{d['download']['bandwidth']*8/1e6:.2f}|{d['ping']['latency']:.2f}")
except Exception: pass
PY
)"; fi; if [[ -n "$parsed" ]]; then IFS='|' read -r state up down lat <<<"$parsed"; else state=FAIL;up=-;down=-;lat=-;fi; else raw="$(with_timeout 50s speedtest-cli --server "$id" --json 2>/dev/null || true)"; parsed=""; if [[ -n "$raw" ]] && command -v python3 >/dev/null 2>&1; then parsed="$(python3 - "$raw" <<'PY' 2>/dev/null || true
import json,sys
try:
 d=json.loads(sys.argv[1]);print(f"PASS|{d['upload']/1e6:.2f}|{d['download']/1e6:.2f}|{d['ping']:.2f}")
except Exception: pass
PY
)"; fi; if [[ -n "$parsed" ]]; then IFS='|' read -r state up down lat <<<"$parsed"; else state=FAIL;up=-;down=-;lat=-;fi; fi; record SPEEDTEST "$group" "$name" "$id" "$state" - "$lat" - "up=$up;down=$down"; printf '%s|%s|%s|%s|%s\n' "$name" "$state" "$up" "$down" "$lat"; }
print_speed_row(){ local c; case "$2" in PASS)c="$GREEN";;FAIL)c="$RED";;*)c="$GRAY";;esac; printf '  %-20s %10s %10s %9s %s%-11s%s\n' "$1" "$3" "$4" "$5" "$c" "$2" "$RESET"; }
speedtest_china_summary(){ local backend name state up down lat; backend="$(find_speedtest)"; printf '%s大陆 Speedtest 参考%s\n' "$MAGENTA$BOLD" "$RESET"; if [[ "$backend" == none && $DEMO -eq 0 ]]; then printf '  %sSpeedtest 后端未安装：UNAVAILABLE%s\n  P07 不会静默下载未校验二进制。\n' "$GRAY" "$RESET"; return; fi; printf '  %-20s %10s %10s %9s 状态\n' '节点' '上传Mbps' '下载Mbps' '延迟ms'; while IFS='|' read -r name state up down lat; do print_speed_row "$name" "$state" "$up" "$down" "$lat"; done < <(speedtest_node 5396 'Suzhou CN' 'China Speedtest'; speedtest_node 59387 'Ningbo CN' 'China Speedtest'); printf '  %s单个 Speedtest 节点失败不会直接判定 IP 被封。%s\n' "$GRAY" "$RESET"; }
global_test(){ reset_results; clear_screen; header; printf '\n%s%s🚀 全球节点测速%s\n' "$CYAN" "$BOLD" "$RESET"; rule; local backend name state up down lat; backend="$(find_speedtest)"; if [[ "$backend" == none && $DEMO -eq 0 ]]; then printf '%s未检测到 Speedtest。%s\n为了供应链安全，不会静默下载可执行文件。\n' "$YELLOW" "$RESET"; return; fi; printf '%s注意：节点测速会明显占用网络带宽。%s\n\n' "$YELLOW" "$RESET"; printf '  %-20s %10s %10s %9s 状态\n' '节点' '上传Mbps' '下载Mbps' '延迟ms'; while IFS='|' read -r name state up down lat; do print_speed_row "$name" "$state" "$up" "$down" "$lat"; done < <(speedtest_node 7190 'Los Angeles US' Global; speedtest_node 48463 'Tokyo JP' Global; speedtest_node 13623 'Singapore SG' Global; speedtest_node 32155 'Hong Kong' Global; speedtest_node 5396 'Suzhou CN' Global; speedtest_node 59387 'Ningbo CN' Global); }
port_test(){ reset_results; clear_screen; header; printf '\n%s%s🔌 端口 / 服务检查%s\n' "$ORANGE" "$BOLD" "$RESET"; rule; if ! command -v ss >/dev/null 2>&1; then printf '未找到 ss。\n'; return; fi; local item p label state c; for item in '22:SSH' '80:HTTP' '443:HTTPS'; do p="${item%%:*}";label="${item#*:}"; if ss -lnt 2>/dev/null|awk '{print $4}'|grep -Eq "(^|:)$p$"; then state=LISTEN;c="$GREEN";else state=CLOSED;c="$YELLOW";fi; record PORT 'Local Ports' "$label" "$p" "$state" - - - ''; printf '  %-10s TCP %-5s %s%s%s\n' "$label" "$p" "$c" "$state" "$RESET"; done; printf '\n%s这里只检查本机监听，不等于中国大陆外部一定能访问。%s\n' "$GRAY" "$RESET"; }
json_report(){ local out="$1"; command -v python3 >/dev/null 2>&1 || return 1; python3 - "$TMP_RESULT" "$out" "$VERSION" "$(get_ip)" "$(get_os)" <<'PY'
import json,sys,datetime
src,out,version,ip,osname=sys.argv[1:];rows=[]
try:
 for line in open(src,encoding='utf-8'):
  p=line.rstrip('\n').split('\t')
  if len(p)>=9: rows.append(dict(type=p[0],group=p[1],name=p[2],target=p[3],state=p[4],code=p[5],connect=p[6],total=p[7],note=p[8]))
except FileNotFoundError: pass
with open(out,'w',encoding='utf-8') as f: json.dump({'schema_version':1,'product':'P07 NetCheck','version':version,'created_at':datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),'public_ip':ip,'os':osname,'results':rows,'boundary':'VPS outbound signals do not prove mainland inbound blocking.'},f,ensure_ascii=False,indent=2)
PY
}
save_report(){ local ts txt json; ts="$(date +%Y%m%d_%H%M%S)";txt="$REPORT_DIR/netcheck_${ts}.txt";json="$REPORT_DIR/netcheck_${ts}.json"; { printf 'P07 NetCheck %s\ntime=%s\npublic_ip=%s\nos=%s\ncpu=%s\ncores=%s\nmemory=%s\ndisk=%s\nvirtualization=%s\ntcp_cc=%s\nspeedtest_backend=%s\n\nRESULTS\n' "$VERSION" "$(date -Is 2>/dev/null||date)" "$(get_ip)" "$(get_os)" "$(get_cpu)" "$(get_cores)" "$(get_mem)" "$(get_disk)" "$(get_virt)" "$(get_tcp_cc)" "$(find_speedtest)"; cat "$TMP_RESULT" 2>/dev/null||true; printf '\nNOTE=China outbound checks are signals only; strongest verdict requires mainland-origin probes.\n'; } >"$txt" 2>/dev/null || { printf '无法写入报告目录。\n';return 1; }; json_report "$json" || json='UNAVAILABLE (python3 missing)'; printf '%s报告已保存%s\n  TXT  %s\n  JSON %s\n' "$GREEN$BOLD" "$RESET" "$txt" "$json"; }
full_report(){ reset_results; clear_screen; header; printf '\n%s%s📄 生成测试报告%s\n' "$MAGENTA" "$BOLD" "$RESET"; rule; printf '执行低影响 HTTPS + 三网参考 + 本机端口；不会自动跑全球满带宽 Speedtest。\n\n'; run_probe_group '海外基础' 'Cloudflare|https://www.cloudflare.com/' 'GitHub|https://github.com/'; run_probe_group '大陆基础' '百度|https://www.baidu.com/' '腾讯|https://www.qq.com/'; run_probe_group '中国三网门户参考' '电信 189|https://www.189.cn/' '联通 10010|https://www.10010.com/' '移动 10086|https://www.10086.cn/'; if command -v ss >/dev/null 2>&1; then local item p label state; for item in '22:SSH' '80:HTTP' '443:HTTPS'; do p="${item%%:*}";label="${item#*:}"; if ss -lnt 2>/dev/null|awk '{print $4}'|grep -Eq "(^|:)$p$";then state=LISTEN;else state=CLOSED;fi;record PORT 'Local Ports' "$label" "$p" "$state" - - - '';done;fi; printf '\n';save_report; }
self_test(){ local fail=0 got; got="$(classify_china 3 6 0 0)";[[ "$got" == NORMAL ]]||fail=1;got="$(classify_china 3 1 5 3)";[[ "$got" == HIGH_RISK ]]||fail=1;got="$(classify_china 2 5 1 1)";[[ "$got" == RISK ]]||fail=1;http_reachable 403||fail=1;if ((fail==0));then printf 'P07_NETCHECK_SELF_TEST=PASS\n';else printf 'P07_NETCHECK_SELF_TEST=FAIL\n';fi;return "$fail"; }
run_interactive(){ local choice; while true;do main_menu;printf '%s请选择 [0-5]：%s' "$CYAN$BOLD" "$RESET";read -r choice||break;case "$choice" in 1)quick_test;pause;;2)china_test;pause;;3)global_test;pause;;4)port_test;pause;;5)full_report;pause;;0)clear_screen;printf '%s安全退出 P07 NetCheck。%s\n' "$GRAY" "$RESET";break;;*)printf '%s请输入 0-5。%s\n' "$YELLOW" "$RESET";sleep 1;;esac;done; }
case "$MODE" in quick)quick_test;;china)china_test;;global)global_test;;ports)port_test;;report)full_report;;selftest)self_test;;*)run_interactive;;esac
