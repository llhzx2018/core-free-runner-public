#!/usr/bin/env bash
set -uo pipefail

APP="P07 Benchmark"
VERSION="0.3.0"
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
NETWORK_TMP="$(mktemp -t p07-benchmark-network.XXXXXX 2>/dev/null || printf '/tmp/p07-benchmark-network.%s' "$$")"
: >"$NETWORK_TMP" 2>/dev/null || true

cleanup(){
  [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]] && rm -rf "$TMP_DIR" 2>/dev/null || true
  rm -f "$NETWORK_TMP" 2>/dev/null || true
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT TERM

rule(){ printf '%s\n' '────────────────────────────────────────────────────────────────────────────'; }
clear_screen(){ [[ -t 1 ]] && clear 2>/dev/null || true; }
pause(){ printf '\n%s按 Enter 返回...%s' "$GRAY" "$RESET"; read -r _ || true; }
status_color(){
  case "$1" in
    PASS) printf '%s' "$GREEN" ;;
    FAIL|TIMEOUT|DNS_FAILURE|TLS_FAILURE|CONNECTION_FAILED|BACKEND_FAILURE|PARSE_ERROR) printf '%s' "$RED" ;;
    UNAVAILABLE|NODE_UNAVAILABLE|TIMEOUT_COMMAND_MISSING|SPEEDTEST_NOT_INSTALLED) printf '%s' "$YELLOW" ;;
    *) printf '%s' "$GRAY" ;;
  esac
}

header(){
  printf '%s%sP07 · Benchmark%s  %sv%s%s\n' "$BOLD" "$CYAN" "$RESET" "$BLUE" "$VERSION" "$RESET"
  rule
}

menu(){
  clear_screen; header; printf '\n'
  printf '  %s1%s  %-18s %s\n' "$YELLOW" "$RESET" '磁盘性能' "顺序写 / 读，默认 ${DISK_MIB} MiB"
  printf '  %s2%s  %-18s %s\n' "$CYAN" "$RESET" '全球网络测速' 'Upload / Download / Latency'
  printf '  %s3%s  %-18s %s\n' "$ORANGE" "$RESET" '完整性能测试' '磁盘 + 全球网络'
  printf '  %s4%s  %-18s %s\n' "$MAGENTA" "$RESET" '历史结果' '磁盘与节点测速结构化记录'
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

free_mib(){ df -Pm "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $4}'; }
fs_type(){ df -PT "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $2}'; }
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

save_disk_history(){
  local write_speed="$1" read_speed="$2" method="$3" fstype="$4" path="$5" ts file
  ts="$(date +%Y%m%d_%H%M%S)"; file="$HISTORY_DIR/disk_${ts}.json"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$file" "$VERSION" "$write_speed" "$read_speed" "$method" "$fstype" "$path" "$DISK_MIB" <<'PY'
import json,sys,datetime
path,v,w,r,method,fstype,test_path,size=sys.argv[1:]
data={
 "schema_version":2,"module":"p07-benchmark","version":v,
 "timestamp":datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
 "kind":"disk","test_size_mib":int(size),"test_path":test_path,"filesystem_type":fstype,
 "seq_write_mb_s":w,"seq_read_mb_s":r,"method":method
}
with open(path,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
PY
  fi
}

disk_test(){
  clear_screen; header
  printf '\n%s%s磁盘性能测试%s\n' "$YELLOW" "$BOLD" "$RESET"; rule
  local need free file write_raw read_raw write_speed read_speed method fstype
  need=$(( DISK_MIB + 256 ))
  free="$(free_mib)"; fstype="$(fs_type)"
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
    file="$TMP_DIR/disk.bin"; method="DIRECT"
    write_raw="$(LC_ALL=C dd if=/dev/zero of="$file" bs=1M count="$DISK_MIB" oflag=direct conv=fdatasync 2>&1)" || {
      method="FDATASYNC"; rm -f "$file"
      write_raw="$(LC_ALL=C dd if=/dev/zero of="$file" bs=1M count="$DISK_MIB" conv=fdatasync 2>&1)" || true
    }
    if [[ ! -s "$file" ]]; then
      printf '%s磁盘写测试失败。%s\n' "$RED" "$RESET"; cleanup; TMP_DIR=""; return 1
    fi
    read_raw="$(LC_ALL=C dd if="$file" of=/dev/null bs=1M iflag=direct 2>&1)" || {
      read_raw="$(LC_ALL=C dd if="$file" of=/dev/null bs=1M 2>&1)" || true
      method="${method}+BUFFERED_READ"
    }
    write_speed="$(parse_dd_mib_s "$write_raw")"; read_speed="$(parse_dd_mib_s "$read_raw")"
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
  save_disk_history "$write_speed" "$read_speed" "$method" "$fstype" "$BENCH_DIR"
}

find_speedtest(){
  if command -v speedtest >/dev/null 2>&1; then printf ookla
  elif command -v speedtest-cli >/dev/null 2>&1; then printf python
  else printf none
  fi
}
have_timeout(){ command -v timeout >/dev/null 2>&1; }
with_timeout(){ timeout "$1" "${@:2}"; }

speed_failure_reason(){
  local rc="$1" text="$2"
  if (( rc == 124 )); then printf TIMEOUT
  elif grep -qiE 'server.*not found|no servers|invalid server' <<<"$text"; then printf NODE_UNAVAILABLE
  elif grep -qiE 'resolve|dns|name or service not known' <<<"$text"; then printf DNS_FAILURE
  elif grep -qiE 'ssl|tls|certificate' <<<"$text"; then printf TLS_FAILURE
  elif grep -qiE 'connect|network|route|unreachable' <<<"$text"; then printf CONNECTION_FAILED
  elif (( rc != 0 )); then printf BACKEND_FAILURE
  else printf PARSE_ERROR
  fi
}

record_network(){
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" >>"$NETWORK_TMP" 2>/dev/null || true
}

speed_node(){
  local id="$1" name="$2" backend raw rc parsed up down lat state reason
  backend="$(find_speedtest)"
  if (( DEMO )); then
    case "$name" in
      *Los*) up=1180.2;down=1258.4;lat=0.9;state=PASS;reason=NONE ;;
      *Tokyo*) up=1022.2;down=980.7;lat=36.1;state=PASS;reason=NONE ;;
      *Singapore*) up=801.4;down=832.3;lat=62.2;state=PASS;reason=NONE ;;
      *Suzhou*|*Ningbo*) up=-;down=-;lat=-;state=FAIL;reason=TIMEOUT ;;
      *) up=620.0;down=710.0;lat=90.0;state=PASS;reason=NONE ;;
    esac
  elif [[ "$backend" == none ]]; then
    up=-;down=-;lat=-;state=UNAVAILABLE;reason=SPEEDTEST_NOT_INSTALLED
  elif ! have_timeout; then
    up=-;down=-;lat=-;state=UNAVAILABLE;reason=TIMEOUT_COMMAND_MISSING
  elif [[ "$backend" == ookla ]]; then
    raw="$(with_timeout 55s speedtest --progress=no --accept-license --accept-gdpr --format=json --server-id="$id" 2>&1)"; rc=$?
    parsed=""
    if (( rc==0 )) && command -v python3 >/dev/null 2>&1; then
      parsed="$(python3 - "$raw" <<'PY' 2>/dev/null || true
import json,sys
try:
 d=json.loads(sys.argv[1]); print(f"{d['upload']['bandwidth']*8/1e6:.1f}|{d['download']['bandwidth']*8/1e6:.1f}|{d['ping']['latency']:.1f}")
except Exception: pass
PY
)"
    fi
    if [[ -n "$parsed" ]]; then IFS='|' read -r up down lat <<<"$parsed"; state=PASS;reason=NONE
    else up=-;down=-;lat=-;state=FAIL;reason="$(speed_failure_reason "$rc" "$raw")"; fi
  else
    raw="$(with_timeout 55s speedtest-cli --server "$id" --json 2>&1)"; rc=$?
    parsed=""
    if (( rc==0 )) && command -v python3 >/dev/null 2>&1; then
      parsed="$(python3 - "$raw" <<'PY' 2>/dev/null || true
import json,sys
try:
 d=json.loads(sys.argv[1]); print(f"{d['upload']/1e6:.1f}|{d['download']/1e6:.1f}|{d['ping']:.1f}")
except Exception: pass
PY
)"
    fi
    if [[ -n "$parsed" ]]; then IFS='|' read -r up down lat <<<"$parsed"; state=PASS;reason=NONE
    else up=-;down=-;lat=-;state=FAIL;reason="$(speed_failure_reason "$rc" "$raw")"; fi
  fi
  record_network "$id" "$name" "$backend" "$up" "$down" "$lat" "$state" "$reason"
  printf '%s|%s|%s|%s|%s|%s\n' "$name" "$up" "$down" "$lat" "$state" "$reason"
}

save_network_history(){
  local backend="$1" ts file
  ts="$(date +%Y%m%d_%H%M%S)"; file="$HISTORY_DIR/network_${ts}.json"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$file" "$VERSION" "$backend" "$NETWORK_TMP" <<'PY'
import json,sys,datetime
path,v,backend,tsv=sys.argv[1:]
nodes=[]
try:
    with open(tsv,encoding='utf-8') as f:
        for line in f:
            parts=line.rstrip('\n').split('\t')
            if len(parts)!=8: continue
            sid,name,b,u,d,l,state,reason=parts
            nodes.append({"server_id":sid,"name":name,"backend":b,"upload_mbps":u,"download_mbps":d,"latency_ms":l,"state":state,"reason":reason})
except FileNotFoundError:
    pass
data={"schema_version":2,"module":"p07-benchmark","version":v,"timestamp":datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),"kind":"network","speedtest_backend":backend,"nodes":nodes}
with open(path,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
PY
  else
    cp "$NETWORK_TMP" "$HISTORY_DIR/network_${ts}.tsv" 2>/dev/null || true
  fi
}

network_test(){
  clear_screen; header; : >"$NETWORK_TMP"
  printf '\n%s%s全球网络测速%s\n' "$CYAN" "$BOLD" "$RESET"; rule
  local backend; backend="$(find_speedtest)"
  if [[ "$backend" == none && $DEMO -eq 0 ]]; then
    printf '%s未检测到 speedtest / speedtest-cli。不会静默下载未校验二进制。%s\n' "$YELLOW" "$RESET"
    return 0
  fi
  if [[ "$backend" != none && $DEMO -eq 0 ]] && ! have_timeout; then
    printf '%s系统缺少 timeout。为保证单节点有硬超时，本次网络测速不执行。%s\n' "$YELLOW" "$RESET"
    return 0
  fi
  confirm_impact '此测试会产生较大上下行流量，可能影响当前网站。' || { printf '已取消。\n'; return 0; }
  printf '  %-18s %-11s %-11s %-9s %-12s 原因\n' 'Node' 'Upload' 'Download' 'Latency' '状态'
  local name up down lat state reason c
  while IFS='|' read -r name up down lat state reason; do
    c="$(status_color "$state")"
    if [[ "$state" == PASS ]]; then
      printf '  %-18s %s↑%-9s%s %s↓%-9s%s %-9s %s%-12s%s\n' "$name" "$GREEN" "$up" "$RESET" "$CYAN" "$down" "$RESET" "$lat" "$c" "$state" "$RESET"
    else
      printf '  %-18s %-11s %-11s %-9s %s%-12s%s %s%s%s\n' "$name" "$up" "$down" "$lat" "$c" "$state" "$RESET" "$GRAY" "$reason" "$RESET"
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
  save_network_history "$backend"
}

history(){
  clear_screen; header
  printf '\n%s%s最近性能测试%s\n' "$MAGENTA" "$BOLD" "$RESET"; rule
  if ! compgen -G "$HISTORY_DIR/*" >/dev/null 2>&1; then printf '暂无历史记录。\n'; return; fi
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$HISTORY_DIR" <<'PY'
import json,glob,os,sys
files=sorted(glob.glob(os.path.join(sys.argv[1],'*.json')),reverse=True)[:10]
for p in files:
    try:
        d=json.load(open(p,encoding='utf-8')); ts=d.get('timestamp','')[:19].replace('T',' '); kind=d.get('kind','?')
        if kind=='disk':
            print(f"  {ts}  DISK     write {d.get('seq_write_mb_s','?')} MB/s · read {d.get('seq_read_mb_s','?')} MB/s · {d.get('method','?')}")
        elif kind=='network':
            nodes=d.get('nodes',[]); passed=sum(1 for n in nodes if n.get('state')=='PASS'); failed=sum(1 for n in nodes if n.get('state')=='FAIL')
            print(f"  {ts}  NETWORK  {passed} pass / {failed} fail · {d.get('speedtest_backend','?')}")
    except Exception:
        pass
PY
  else
    ls -1t "$HISTORY_DIR"/* | head -10 | sed 's#^.*/#  #'
  fi
}

full_test(){ disk_test; printf '\n'; network_test; }

self_test(){
  local f=0 old_demo
  [[ "$DISK_MIB" =~ ^[0-9]+$ ]] || f=1
  [[ "$(find_speedtest)" =~ ^(ookla|python|none)$ ]] || f=1
  [[ "$(parse_dd_mib_s "268435456 bytes copied, 0.5 s, 537 MB/s")" == "537.0" ]] || f=1
  [[ "$(speed_failure_reason 124 '')" == TIMEOUT ]] || f=1
  [[ "$(speed_failure_reason 1 'Invalid server')" == NODE_UNAVAILABLE ]] || f=1
  old_demo="$DEMO"; DEMO=1
  local demo; demo="$(speed_node 5396 'Suzhou CN')"
  [[ "$demo" == *"|FAIL|TIMEOUT" ]] || f=1
  DEMO="$old_demo"
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
