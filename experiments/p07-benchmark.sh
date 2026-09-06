#!/usr/bin/env bash
set -uo pipefail

APP="P07 Benchmark"
VERSION="0.2.0"
MODE="interactive"
DEMO=0
ASSUME_YES=0
DISK_MIB=256
BENCH_DIR="${VF_BENCH_DIR:-/var/tmp}"
[[ -d "$BENCH_DIR" && -w "$BENCH_DIR" ]] || BENCH_DIR="${TMPDIR:-/tmp}"

while (($#)); do
  case "$1" in
    --demo) DEMO=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --disk) MODE="disk" ;;
    --network) MODE="network" ;;
    --full) MODE="full" ;;
    --history) MODE="history" ;;
    --self-test) MODE="selftest" ;;
    --disk-mib)
      shift; [[ ${1:-} =~ ^[0-9]+$ ]] || { printf 'Invalid --disk-mib\n' >&2; exit 2; }
      DISK_MIB="$1"
      ;;
    --version) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
    -h|--help)
      cat <<EOF
$APP $VERSION
Usage:
  p07-benchmark.sh
  p07-benchmark.sh --disk [--disk-mib 256] [--yes]
  p07-benchmark.sh --network [--yes]
  p07-benchmark.sh --full [--yes]
  p07-benchmark.sh --history
  p07-benchmark.sh --demo
EOF
      exit 0
      ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RESET=$'\033[0m'; BOLD=$'\033[1m'
  CYAN=$'\033[38;5;45m'; BLUE=$'\033[38;5;39m'; GREEN=$'\033[38;5;48m'
  YELLOW=$'\033[38;5;220m'; ORANGE=$'\033[38;5;208m'; RED=$'\033[38;5;203m'
  MAGENTA=$'\033[38;5;141m'; GRAY=$'\033[38;5;245m'
else
  RESET=""; BOLD=""; CYAN=""; BLUE=""; GREEN=""; YELLOW=""; ORANGE=""; RED=""; MAGENTA=""; GRAY=""
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  STATE_BASE="/var/lib/p07-benchmark"
else
  STATE_BASE="${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/p07-benchmark"
fi
HISTORY_DIR="$STATE_BASE/history"
mkdir -p "$HISTORY_DIR" 2>/dev/null || true

TMP_DIR=""
cleanup(){
  [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]] && rm -rf "$TMP_DIR" 2>/dev/null || true
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT TERM

rule(){ printf '%s\n' '────────────────────────────────────────────────────────────────────────────'; }
clear_screen(){ [[ -t 1 ]] && clear 2>/dev/null || true; }
pause(){ printf '\n%s按 Enter 返回...%s' "$GRAY" "$RESET"; read -r _ || true; }

header(){
  printf '%s%sP07 · Benchmark%s  %sv%s%s\n' "$BOLD" "$CYAN" "$RESET" "$BLUE" "$VERSION" "$RESET"
  rule
}

menu(){
  clear_screen; header; printf '\n'
  printf '  %s1%s  %-18s %s\n' "$YELLOW" "$RESET" '磁盘性能' "顺序写 / 读，默认 ${DISK_MIB} MiB"
  printf '  %s2%s  %-18s %s\n' "$CYAN" "$RESET" '全球网络测速' 'Upload / Download / Latency'
  printf '  %s3%s  %-18s %s\n' "$ORANGE" "$RESET" '完整性能测试' '磁盘 + 全球网络'
  printf '  %s4%s  %-18s %s\n' "$MAGENTA" "$RESET" '历史结果' '最近测试记录'
  printf '\n  %s0 返回%s\n' "$GRAY" "$RESET"; rule
}

confirm_impact(){
  local text="$1"
  (( ASSUME_YES || DEMO )) && return 0
  printf '%s%s%s\n' "$YELLOW" "$text" "$RESET"
  printf '继续？[y/N]：'
  local yn; read -r yn || return 1
  [[ "$yn" =~ ^[Yy]$ ]]
}

free_mib(){
  df -Pm "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $4}'
}
fs_type(){
  df -PT "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $2}'
}
parse_dd_mib_s(){
  local text="$1" rate value unit
  rate="$(printf '%s\n' "$text" | awk -F, 'END{gsub(/^[ \t]+|[ \t]+$/,"",$NF); print $NF}')"
  value="$(printf '%s\n' "$rate" | awk '{print $1}')"
  unit="$(printf '%s\n' "$rate" | awk '{print $2}')"
  [[ "$value" =~ ^[0-9.]+$ ]] || return 0
  case "$unit" in
    GB/s) awk -v v="$value" 'BEGIN{printf "%.1f",v*1000}' ;;
    MB/s) awk -v v="$value" 'BEGIN{printf "%.1f",v}' ;;
    kB/s) awk -v v="$value" 'BEGIN{printf "%.1f",v/1000}' ;;
    B/s)  awk -v v="$value" 'BEGIN{printf "%.1f",v/1000000}' ;;
  esac
}

disk_test(){
  clear_screen; header
  printf '\n%s%s磁盘性能测试%s\n' "$YELLOW" "$BOLD" "$RESET"; rule
  local need free file write_raw read_raw write_speed read_speed method fstype
  need=$(( DISK_MIB + 256 ))
  free="$(free_mib)"
  fstype="$(fs_type)"
  if [[ "$fstype" =~ ^(tmpfs|devtmpfs)$ && "${VF_BENCH_ALLOW_TMPFS:-0}" != "1" ]]; then
    printf '%s测试目录 %s 位于 %s，不代表真实 VPS 磁盘性能，已安全停止。%s\n' "$RED" "$BENCH_DIR" "$fstype" "$RESET"
    printf '可设置 VF_BENCH_DIR=/真实磁盘目录 后重试。\n'
    return 1
  fi
  if [[ ! "$free" =~ ^[0-9]+$ ]]; then
    printf '%s无法确认测试目录剩余空间，安全停止。%s\n' "$RED" "$RESET"; return 1
  fi
  if (( free < need )); then
    printf '%s空间不足：需要至少 %s MiB，可用 %s MiB。%s\n' "$RED" "$need" "$free" "$RESET"; return 1
  fi
  confirm_impact "此测试会在临时目录写入约 ${DISK_MIB} MiB 数据，测试后自动删除。" || { printf '已取消。\n'; return 0; }

  if (( DEMO )); then
    fstype="ext4"; BENCH_DIR="/var/tmp"; write_speed="575.8"; read_speed="812.4"; method="DIRECT"
  else
    TMP_DIR="$(mktemp -d "$BENCH_DIR/p07-benchmark.XXXXXX")" || { printf '无法创建临时目录。\n'; return 1; }
    file="$TMP_DIR/disk.bin"
    method="DIRECT"
    write_raw="$(LC_ALL=C dd if=/dev/zero of="$file" bs=1M count="$DISK_MIB" oflag=direct conv=fdatasync 2>&1)" || {
      method="FDATASYNC"
      rm -f "$file"
      write_raw="$(LC_ALL=C dd if=/dev/zero of="$file" bs=1M count="$DISK_MIB" conv=fdatasync 2>&1)" || true
    }
    if [[ ! -s "$file" ]]; then
      printf '%s磁盘写测试失败。%s\n' "$RED" "$RESET"; cleanup; TMP_DIR=""; return 1
    fi
    read_raw="$(LC_ALL=C dd if="$file" of=/dev/null bs=1M iflag=direct 2>&1)" || {
      read_raw="$(LC_ALL=C dd if="$file" of=/dev/null bs=1M 2>&1)" || true
      method="${method}+BUFFERED_READ"
    }
    write_speed="$(parse_dd_mib_s "$write_raw")"
    read_speed="$(parse_dd_mib_s "$read_raw")"
    rm -rf "$TMP_DIR"; TMP_DIR=""
    [[ -n "$write_speed" ]] || write_speed="UNKNOWN"
    [[ -n "$read_speed" ]] || read_speed="UNKNOWN"
  fi

  printf '  Test path      %s\n' "$BENCH_DIR"
  printf '  Filesystem     %s\n' "$fstype"
  printf '  Test size      %s MiB\n' "$DISK_MIB"
  printf '  Method         %s\n' "$method"
  printf '  Seq write      %s%s MB/s%s\n' "$GREEN" "$write_speed" "$RESET"
  printf '  Seq read       %s%s MB/s%s\n' "$CYAN" "$read_speed" "$RESET"
  printf '  Temp cleanup   %sPASS%s\n' "$GREEN" "$RESET"
  save_history disk "$write_speed" "$read_speed" "$method"
}

find_speedtest(){
  if command -v speedtest >/dev/null 2>&1; then printf ookla
  elif command -v speedtest-cli >/dev/null 2>&1; then printf python
  else printf none
  fi
}
with_timeout(){ if command -v timeout >/dev/null 2>&1; then timeout "$1" "${@:2}"; else "${@:2}"; fi; }

speed_node(){
  local id="$1" name="$2" backend raw rc parsed
  backend="$(find_speedtest)"
  if (( DEMO )); then
    case "$name" in
      *Los*) printf '%s|1180.2|1258.4|0.9|PASS\n' "$name" ;;
      *Tokyo*) printf '%s|1022.2|980.7|36.1|PASS\n' "$name" ;;
      *Singapore*) printf '%s|801.4|832.3|62.2|PASS\n' "$name" ;;
      *Suzhou*|*Ningbo*) printf '%s|-|-|-|FAIL\n' "$name" ;;
      *) printf '%s|620.0|710.0|90.0|PASS\n' "$name" ;;
    esac
    return
  fi
  [[ "$backend" != none ]] || { printf '%s|-|-|-|UNAVAILABLE\n' "$name"; return; }
  if [[ "$backend" == ookla ]]; then
    raw="$(with_timeout 55s speedtest --progress=no --accept-license --accept-gdpr --format=json --server-id="$id" 2>/dev/null)"; rc=$?
    if (( rc==0 )) && command -v python3 >/dev/null 2>&1; then
      parsed="$(python3 - "$name" "$raw" <<'PY' 2>/dev/null || true
import json,sys
try:
 d=json.loads(sys.argv[2]); print(f"{sys.argv[1]}|{d['upload']['bandwidth']*8/1e6:.1f}|{d['download']['bandwidth']*8/1e6:.1f}|{d['ping']['latency']:.1f}|PASS")
except Exception: pass
PY
)"
      [[ -n "$parsed" ]] && { printf '%s\n' "$parsed"; return; }
    fi
  else
    raw="$(with_timeout 55s speedtest-cli --server "$id" --json 2>/dev/null)"; rc=$?
    if (( rc==0 )) && command -v python3 >/dev/null 2>&1; then
      parsed="$(python3 - "$name" "$raw" <<'PY' 2>/dev/null || true
import json,sys
try:
 d=json.loads(sys.argv[2]); print(f"{sys.argv[1]}|{d['upload']/1e6:.1f}|{d['download']/1e6:.1f}|{d['ping']:.1f}|PASS")
except Exception: pass
PY
)"
      [[ -n "$parsed" ]] && { printf '%s\n' "$parsed"; return; }
    fi
  fi
  printf '%s|-|-|-|FAIL\n' "$name"
}

network_test(){
  clear_screen; header
  printf '\n%s%s全球网络测速%s\n' "$CYAN" "$BOLD" "$RESET"; rule
  local backend; backend="$(find_speedtest)"
  if [[ "$backend" == none && $DEMO -eq 0 ]]; then
    printf '%s未检测到 speedtest / speedtest-cli。不会静默下载未校验二进制。%s\n' "$YELLOW" "$RESET"
    return 0
  fi
  confirm_impact '此测试会产生较大上下行流量，可能影响当前网站。' || { printf '已取消。\n'; return 0; }
  printf '  %-18s %-11s %-11s %-9s 状态\n' 'Node' 'Upload' 'Download' 'Latency'
  local name up down lat state
  while IFS='|' read -r name up down lat state; do
    if [[ "$state" == PASS ]]; then
      printf '  %-18s %s↑%-9s%s %s↓%-9s%s %-9s %sPASS%s\n' "$name" "$GREEN" "$up" "$RESET" "$CYAN" "$down" "$RESET" "$lat" "$GREEN" "$RESET"
    else
      printf '  %-18s %-11s %-11s %-9s %s%s%s\n' "$name" "$up" "$down" "$lat" "$RED" "$state" "$RESET"
    fi
  done < <(
    speed_node 7190 'Los Angeles US'
    speed_node 22288 'Dallas US'
    speed_node 61933 'Paris FR'
    speed_node 41423 'Amsterdam NL'
    speed_node 5396 'Suzhou CN'
    speed_node 59387 'Ningbo CN'
    speed_node 32155 'Hong Kong'
    speed_node 13623 'Singapore SG'
    speed_node 48463 'Tokyo JP'
  )
  save_history network "-" "-" "$backend"
}

save_history(){
  local kind="$1" a="$2" b="$3" c="$4" ts file
  ts="$(date +%Y%m%d_%H%M%S)"
  file="$HISTORY_DIR/${kind}_${ts}.json"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$file" "$VERSION" "$kind" "$a" "$b" "$c" <<'PY'
import json,sys,datetime
path,v,kind,a,b,c=sys.argv[1:]
data={"schema_version":1,"module":"p07-benchmark","version":v,"timestamp":datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),"kind":kind}
if kind=="disk":
 data["seq_write_mb_s"]=a; data["seq_read_mb_s"]=b; data["method"]=c
else:
 data["speedtest_backend"]=c
with open(path,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
PY
  fi
}

history(){
  clear_screen; header
  printf '\n%s%s最近性能测试%s\n' "$MAGENTA" "$BOLD" "$RESET"; rule
  if ! compgen -G "$HISTORY_DIR/*.json" >/dev/null 2>&1; then printf '暂无历史记录。\n'; return; fi
  ls -1t "$HISTORY_DIR"/*.json | head -10 | sed 's#^.*/#  #'
}

full_test(){
  disk_test
  printf '\n'
  network_test
}

self_test(){
  local f=0
  [[ "$DISK_MIB" =~ ^[0-9]+$ ]] || f=1
  [[ "$(find_speedtest)" =~ ^(ookla|python|none)$ ]] || f=1
  [[ "$(parse_dd_mib_s "268435456 bytes copied, 0.5 s, 537 MB/s")" == "537.0" ]] || f=1
  (( DEMO=1 ))
  local demo; demo="$(speed_node 5396 'Suzhou CN')"
  [[ "$demo" == *"|FAIL" ]] || f=1
  if (( f )); then printf 'SELF_TEST=FAIL\n'; return 1; else printf 'SELF_TEST=PASS\n'; fi
}

interactive(){
  local c
  while true; do
    menu
    printf '请选择 [0-4]：'; read -r c || break
    case "$c" in
      1) disk_test; pause ;;
      2) network_test; pause ;;
      3) full_test; pause ;;
      4) history; pause ;;
      0) return ;;
      *) sleep 1 ;;
    esac
  done
}

case "$MODE" in
  disk) disk_test ;;
  network) network_test ;;
  full) full_test ;;
  history) history ;;
  selftest) self_test ;;
  *) interactive ;;
esac
