#!/usr/bin/env bash
set -u

APP="P07 NetCheck"
VERSION="0.1.0"
DEMO=0
MODE="interactive"
START_TS="$(date +%s)"

case "${1:-}" in
  --demo) DEMO=1 ;;
  --quick) MODE="quick" ;;
  --china) MODE="china" ;;
  --global) MODE="global" ;;
  --ports) MODE="ports" ;;
  --report) MODE="report" ;;
  --version) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
  -h|--help)
    cat <<HELP
$APP $VERSION
Usage: p07-netcheck.sh [--demo|--quick|--china|--global|--ports|--report|--version]
HELP
    exit 0
    ;;
esac

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RESET=$'\033[0m'; BOLD=$'\033[1m'; DIM=$'\033[2m'
  CYAN=$'\033[38;5;45m'; BLUE=$'\033[38;5;39m'; GREEN=$'\033[38;5;48m'
  YELLOW=$'\033[38;5;220m'; ORANGE=$'\033[38;5;208m'; RED=$'\033[38;5;203m'
  MAGENTA=$'\033[38;5;141m'; GRAY=$'\033[38;5;245m'; WHITE=$'\033[38;5;255m'
else
  RESET=""; BOLD=""; DIM=""; CYAN=""; BLUE=""; GREEN=""; YELLOW=""; ORANGE=""; RED=""; MAGENTA=""; GRAY=""; WHITE=""
fi

STATE_BASE="${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/p07-netcheck"
if [[ ${EUID:-$(id -u)} -eq 0 ]]; then STATE_BASE="/var/lib/p07-netcheck"; fi
REPORT_DIR="$STATE_BASE/reports"
mkdir -p "$REPORT_DIR" 2>/dev/null || true
LAST_REPORT=""

clear_screen(){ [[ -t 1 ]] && clear 2>/dev/null || true; }
line(){ printf '%s\n' "────────────────────────────────────────────────────────────────────────────"; }
pause(){ printf '\n%s按 Enter 返回...%s' "$GRAY" "$RESET"; read -r _ || true; }

get_os(){
  if [[ -r /etc/os-release ]]; then . /etc/os-release; printf '%s' "${PRETTY_NAME:-Linux}"; else uname -s; fi
}
get_cpu(){ awk -F: '/model name/{gsub(/^[ \t]+/,"",$2); print $2; exit}' /proc/cpuinfo 2>/dev/null || true; }
get_cores(){ getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || printf '?'; }
get_mem(){ free -h 2>/dev/null | awk '/^Mem:/{print $2}' || printf '?'; }
get_virt(){ if command -v systemd-detect-virt >/dev/null 2>&1; then systemd-detect-virt 2>/dev/null || printf 'none'; else printf 'unknown'; fi; }
get_uptime(){ uptime -p 2>/dev/null | sed 's/^up //' || printf '?'; }
get_ip(){
  if (( DEMO )); then printf '103.123.45.67'; return; fi
  command -v curl >/dev/null 2>&1 || { printf 'UNKNOWN'; return; }
  curl -4fsS --connect-timeout 3 --max-time 5 https://api.ipify.org 2>/dev/null || printf 'UNKNOWN'
}

header(){
  local ip os
  ip="$(get_ip)"; os="$(get_os)"
  printf '%s%s╭──────────────────────────────────────────────────────────────────────────╮%s\n' "$BOLD" "$BLUE" "$RESET"
  printf '%s%s│  P07 · NetCheck%s  %s服务器网络 / IP / 性能检测%s                         %s%s│%s\n' "$BOLD" "$CYAN" "$RESET" "$WHITE" "$RESET" "$BLUE" "$BOLD" "$RESET"
  printf '%s%s│  v%-8s  IP: %-15s  %-36s│%s\n' "$BLUE" "$BOLD" "$VERSION" "$ip" "${os:0:36}" "$RESET"
  printf '%s%s╰──────────────────────────────────────────────────────────────────────────╯%s\n' "$BOLD" "$BLUE" "$RESET"
}

main_menu(){
  clear_screen; header
  printf '\n%s%s  1. 快速检测%s\n' "$GREEN" "$BOLD" "$RESET"
  printf '     系统 / 网络 / HTTPS 基础可达性，低影响，推荐先跑\n\n'
  printf '%s%s  2. 中国访问 / IP 可用性%s\n' "$RED" "$BOLD" "$RESET"
  printf '     大陆方向 + 海外对照，输出 正常 / 风险 / 高风险\n\n'
  printf '%s%s  3. 全球节点测速%s\n' "$CYAN" "$BOLD" "$RESET"
  printf '     Ookla Speedtest 可用时测试全球及大陆节点\n\n'
  printf '%s%s  4. 端口 / 服务检查%s\n' "$ORANGE" "$BOLD" "$RESET"
  printf '     检查 SSH / HTTP / HTTPS 是否正在监听\n\n'
  printf '%s%s  5. 完整测试报告%s\n' "$MAGENTA" "$BOLD" "$RESET"
  printf '     汇总检测结果并保存到本机，不上传任何报告\n\n'
  printf '%s  0. 退出%s\n' "$GRAY" "$RESET"
  line
}

http_probe(){
  local name="$1" url="$2" raw code connect total
  if (( DEMO )); then
    case "$name" in
      *百度*|*腾讯*|*淘宝*) printf '%s|000|timeout|timeout\n' "$name" ;;
      *) printf '%s|200|0.031|0.115\n' "$name" ;;
    esac
    return
  fi
  if ! command -v curl >/dev/null 2>&1; then printf '%s|NA|NA|NA\n' "$name"; return; fi
  raw="$(curl -LksS -o /dev/null --connect-timeout 4 --max-time 8 -w '%{http_code}|%{time_connect}|%{time_total}' "$url" 2>/dev/null || true)"
  if [[ -z "$raw" ]]; then raw='000|timeout|timeout'; fi
  IFS='|' read -r code connect total <<<"$raw"
  printf '%s|%s|%s|%s\n' "$name" "$code" "$connect" "$total"
}

probe_status(){ local code="$1"; [[ "$code" =~ ^[23][0-9][0-9]$ ]] && printf 'PASS' || printf 'FAIL'; }

print_probe_row(){
  local name="$1" code="$2" conn="$3" total="$4" state color
  state="$(probe_status "$code")"
  [[ "$state" == PASS ]] && color="$GREEN" || color="$RED"
  printf '  %-18s  HTTP %-3s  connect %-8s  total %-8s  %s%s%s\n' "$name" "$code" "$conn" "$total" "$color" "$state" "$RESET"
}

quick_test(){
  clear_screen; header
  printf '\n%s%s⚡ 快速检测%s\n' "$GREEN" "$BOLD" "$RESET"; line
  printf 'CPU       %s · %s vCPU\n' "$(get_cpu)" "$(get_cores)"
  printf '内存      %s\n' "$(get_mem)"
  printf '虚拟化    %s\n' "$(get_virt)"
  printf '运行时间  %s\n' "$(get_uptime)"
  printf '\n%s网络基础可达性%s\n' "$CYAN" "$RESET"
  local row name code conn total
  while IFS='|' read -r name code conn total; do print_probe_row "$name" "$code" "$conn" "$total"; done < <(
    http_probe 'Cloudflare' 'https://www.cloudflare.com/'
    http_probe 'GitHub' 'https://github.com/'
    http_probe '百度 CN' 'https://www.baidu.com/'
  )
}

china_test(){
  clear_screen; header
  printf '\n%s%s🌐 中国访问 / IP 可用性%s\n' "$RED" "$BOLD" "$RESET"; line
  printf '%s说明：本机检测只能判断 VPS → 中国大陆方向；不能单独证明“中国已封 IP”。%s\n\n' "$GRAY" "$RESET"
  local overseas_pass=0 china_pass=0 china_fail=0
  local name code conn total state
  printf '%s海外对照%s\n' "$CYAN" "$RESET"
  while IFS='|' read -r name code conn total; do
    print_probe_row "$name" "$code" "$conn" "$total"
    [[ "$(probe_status "$code")" == PASS ]] && ((overseas_pass+=1)) || true
  done < <(http_probe 'Cloudflare' 'https://www.cloudflare.com/'; http_probe 'GitHub' 'https://github.com/')

  printf '\n%s中国大陆 HTTPS%s\n' "$YELLOW" "$RESET"
  while IFS='|' read -r name code conn total; do
    print_probe_row "$name" "$code" "$conn" "$total"
    state="$(probe_status "$code")"
    if [[ "$state" == PASS ]]; then ((china_pass+=1)); else ((china_fail+=1)); fi
  done < <(http_probe '百度' 'https://www.baidu.com/'; http_probe '腾讯' 'https://www.qq.com/'; http_probe '淘宝' 'https://www.taobao.com/')

  printf '\n'
  if (( china_fail == 0 )); then
    printf '%s%s综合判断：正常 ✓%s\n' "$GREEN" "$BOLD" "$RESET"
    printf '暂未发现明显的中国大陆方向访问异常。\n'
  elif (( china_fail >= 2 && overseas_pass >= 2 )); then
    printf '%s%s综合判断：高风险 ✗%s\n' "$RED" "$BOLD" "$RESET"
    printf '多个大陆 HTTPS 目标失败，而海外对照正常。\n'
    printf '%s建议：迁移正式网站前继续做三网反向检测；若多运营商入站也失败，优先换 IP。%s\n' "$YELLOW" "$RESET"
  else
    printf '%s%s综合判断：有风险 ⚠%s\n' "$YELLOW" "$BOLD" "$RESET"
    printf '部分大陆目标异常，当前证据不足以判定 IP 不可用。\n'
  fi

  printf '\n三网反向探测：%sV0.1 尚未接入外部大陆探针%s\n' "$GRAY" "$RESET"
  speedtest_china_summary
}

find_speedtest(){
  if command -v speedtest >/dev/null 2>&1; then printf 'ookla';
  elif command -v speedtest-cli >/dev/null 2>&1; then printf 'python';
  else printf 'none'; fi
}

speedtest_node(){
  local id="$1" name="$2" backend raw parsed
  backend="$(find_speedtest)"
  if (( DEMO )); then
    case "$name" in
      *Suzhou*|*Ningbo*) printf '%s|FAIL|-|-|-\n' "$name" ;;
      *Los*) printf '%s|PASS|1180.24|1258.36|0.89\n' "$name" ;;
      *Tokyo*) printf '%s|PASS|1022.15|980.72|36.12\n' "$name" ;;
      *Singapore*) printf '%s|PASS|801.36|832.27|62.18\n' "$name" ;;
      *Hong*) printf '%s|PASS|702.11|689.45|48.37\n' "$name" ;;
      *) printf '%s|PASS|620.00|710.00|90.00\n' "$name" ;;
    esac
    return
  fi
  if [[ "$backend" == none ]]; then printf '%s|UNAVAILABLE|-|-|-\n' "$name"; return; fi
  if [[ "$backend" == ookla ]]; then
    raw="$(speedtest --progress=no --accept-license --accept-gdpr --format=json --server-id="$id" 2>/dev/null || true)"
    if [[ -n "$raw" ]] && command -v python3 >/dev/null 2>&1; then
      parsed="$(python3 - "$name" "$raw" <<'PY' 2>/dev/null || true
import json,sys
name=sys.argv[1]
try:
 d=json.loads(sys.argv[2]); up=d['upload']['bandwidth']*8/1e6; down=d['download']['bandwidth']*8/1e6; lat=d['ping']['latency']; print(f"{name}|PASS|{up:.2f}|{down:.2f}|{lat:.2f}")
except Exception: pass
PY
)"
      [[ -n "$parsed" ]] && { printf '%s\n' "$parsed"; return; }
    fi
  else
    raw="$(speedtest-cli --server "$id" --json 2>/dev/null || true)"
    if [[ -n "$raw" ]] && command -v python3 >/dev/null 2>&1; then
      parsed="$(python3 - "$name" "$raw" <<'PY' 2>/dev/null || true
import json,sys
name=sys.argv[1]
try:
 d=json.loads(sys.argv[2]); print(f"{name}|PASS|{d['upload']/1e6:.2f}|{d['download']/1e6:.2f}|{d['ping']:.2f}")
except Exception: pass
PY
)"
      [[ -n "$parsed" ]] && { printf '%s\n' "$parsed"; return; }
    fi
  fi
  printf '%s|FAIL|-|-|-\n' "$name"
}

print_speed_row(){
  local name="$1" state="$2" up="$3" down="$4" lat="$5" color
  case "$state" in PASS) color="$GREEN";; FAIL) color="$RED";; *) color="$GRAY";; esac
  printf '  %-18s  %-10s  %-10s  %-9s  %s%s%s\n' "$name" "$up" "$down" "$lat" "$color" "$state" "$RESET"
}

speedtest_china_summary(){
  local backend
  backend="$(find_speedtest)"
  printf '\n%s大陆 Speedtest 参考%s\n' "$MAGENTA" "$RESET"
  if [[ "$backend" == none && $DEMO -eq 0 ]]; then
    printf '  Speedtest 未安装，本项记为 %sUNAVAILABLE%s；不会自动下载未校验二进制。\n' "$GRAY" "$RESET"
    return
  fi
  printf '  %-18s  %-10s  %-10s  %-9s  状态\n' '节点' '上传Mbps' '下载Mbps' '延迟ms'
  local name state up down lat
  while IFS='|' read -r name state up down lat; do print_speed_row "$name" "$state" "$up" "$down" "$lat"; done < <(
    speedtest_node 5396 'Suzhou CN'
    speedtest_node 59387 'Ningbo CN'
  )
}

global_test(){
  clear_screen; header
  printf '\n%s%s🚀 全球节点测速%s\n' "$CYAN" "$BOLD" "$RESET"; line
  local backend; backend="$(find_speedtest)"
  if [[ "$backend" == none && $DEMO -eq 0 ]]; then
    printf '%s未检测到 Ookla Speedtest / speedtest-cli。%s\n' "$YELLOW" "$RESET"
    printf '为保证供应链安全，V0.1 不会静默下载可执行文件。\n'
    printf '快速检测和中国 HTTPS 风险检测仍可正常使用。\n'
    return
  fi
  printf '  %-18s  %-10s  %-10s  %-9s  状态\n' '节点' '上传Mbps' '下载Mbps' '延迟ms'
  local name state up down lat
  while IFS='|' read -r name state up down lat; do print_speed_row "$name" "$state" "$up" "$down" "$lat"; done < <(
    speedtest_node 7190 'Los Angeles US'
    speedtest_node 48463 'Tokyo JP'
    speedtest_node 13623 'Singapore SG'
    speedtest_node 32155 'Hong Kong'
    speedtest_node 5396 'Suzhou CN'
    speedtest_node 59387 'Ningbo CN'
  )
  printf '\n%s注意：单个大陆 Speedtest 节点失败 ≠ IP 已被封。%s\n' "$GRAY" "$RESET"
}

port_test(){
  clear_screen; header
  printf '\n%s%s🔌 端口 / 服务检查%s\n' "$ORANGE" "$BOLD" "$RESET"; line
  if ! command -v ss >/dev/null 2>&1; then printf '未找到 ss，无法读取本机监听端口。\n'; return; fi
  local p label state color
  for item in '22:SSH' '80:HTTP' '443:HTTPS'; do
    p="${item%%:*}"; label="${item#*:}"
    if ss -lnt 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)$p$"; then state='监听中'; color="$GREEN"; else state='未监听'; color="$YELLOW"; fi
    printf '  %-8s TCP %-5s  %s%s%s\n' "$label" "$p" "$color" "$state" "$RESET"
  done
  printf '\n%s这里只检查服务器本机监听，不等于中国大陆外部一定能访问。%s\n' "$GRAY" "$RESET"
}

save_report(){
  local ts file
  ts="$(date +%Y%m%d_%H%M%S)"; file="$REPORT_DIR/netcheck_${ts}.txt"
  {
    printf 'P07 NetCheck %s\n' "$VERSION"
    printf 'time=%s\n' "$(date -Is 2>/dev/null || date)"
    printf 'public_ip=%s\n' "$(get_ip)"
    printf 'os=%s\n' "$(get_os)"
    printf 'cpu=%s\n' "$(get_cpu)"
    printf 'cores=%s\n' "$(get_cores)"
    printf 'memory=%s\n' "$(get_mem)"
    printf 'virtualization=%s\n' "$(get_virt)"
    printf 'speedtest_backend=%s\n' "$(find_speedtest)"
    printf 'note=China outbound checks are signals only; strongest blocked verdict requires mainland-origin probes.\n'
  } >"$file" 2>/dev/null || { printf '无法写入报告目录：%s\n' "$REPORT_DIR"; return 1; }
  LAST_REPORT="$file"
  printf '%s报告已保存：%s%s\n' "$GREEN" "$file" "$RESET"
}

full_report(){
  clear_screen; header
  printf '\n%s%s📄 完整测试报告%s\n' "$MAGENTA" "$BOLD" "$RESET"; line
  quick_test
  printf '\n'; china_test
  printf '\n'; port_test
  printf '\n'; save_report
}

run_interactive(){
  local choice
  while true; do
    main_menu
    printf '%s请选择 [0-5]：%s' "$CYAN" "$RESET"
    read -r choice || break
    case "$choice" in
      1) quick_test; pause ;;
      2) china_test; pause ;;
      3) global_test; pause ;;
      4) port_test; pause ;;
      5) full_report; pause ;;
      0) clear_screen; printf '%s安全退出 P07 NetCheck。%s\n' "$GRAY" "$RESET"; break ;;
      *) printf '%s请输入 0-5。%s\n' "$YELLOW" "$RESET"; sleep 1 ;;
    esac
  done
}

case "$MODE" in
  quick) quick_test ;;
  china) china_test ;;
  global) global_test ;;
  ports) port_test ;;
  report) full_report ;;
  *) run_interactive ;;
esac
