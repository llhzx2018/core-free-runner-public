#!/usr/bin/env bash
set -uo pipefail

APP="P07 Inspect"
VERSION="0.2.0"
DEMO=0
MODE="human"

while (($#)); do
  case "$1" in
    --demo) DEMO=1 ;;
    --json) MODE="json" ;;
    --self-test) MODE="selftest" ;;
    --version) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
    -h|--help)
      cat <<EOF
$APP $VERSION
Usage: p07-inspect.sh [--demo] [--json|--self-test|--version]
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
  YELLOW=$'\033[38;5;220m'; RED=$'\033[38;5;203m'; GRAY=$'\033[38;5;245m'
else
  RESET=""; BOLD=""; DIM=""; CYAN=""; BLUE=""; GREEN=""; YELLOW=""; RED=""; GRAY=""
fi

rule(){ printf '%s\n' '────────────────────────────────────────────────────────────────────────────'; }
yesno(){
  if [[ "$1" == "1" ]]; then printf '%s✓ Enabled%s' "$GREEN" "$RESET"; else printf '%s✗ Disabled%s' "$GRAY" "$RESET"; fi
}
get_os(){ if [[ -r /etc/os-release ]]; then awk -F= '/^PRETTY_NAME=/{gsub(/^"|"$/,"",$2);print $2}' /etc/os-release; else uname -s; fi; }
get_arch(){ uname -m 2>/dev/null || printf UNKNOWN; }
get_kernel(){ uname -r 2>/dev/null || printf UNKNOWN; }
get_cpu(){ awk -F: '/model name/{gsub(/^[ \t]+/,"",$2);print $2;exit}' /proc/cpuinfo 2>/dev/null || printf UNKNOWN; }
get_cores(){ getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || printf '?'; }
get_freq(){
  if command -v lscpu >/dev/null 2>&1; then
    local v
    v="$(lscpu 2>/dev/null | awk -F: '/CPU max MHz/{gsub(/^[ \t]+/,"",$2);printf "%.0f MHz",$2;exit}')"
    [[ -n "$v" ]] && { printf '%s' "$v"; return; }
  fi
  awk -F: '/cpu MHz/{gsub(/^[ \t]+/,"",$2);printf "%.0f MHz",$2;exit}' /proc/cpuinfo 2>/dev/null || printf UNKNOWN
}
get_cache(){ awk -F: '/cache size/{gsub(/^[ \t]+/,"",$2);print $2;exit}' /proc/cpuinfo 2>/dev/null || printf UNKNOWN; }
has_aes(){ grep -Eq '(^|[[:space:]])aes([[:space:]]|$)' /proc/cpuinfo 2>/dev/null; }
has_nested_virt_flag(){ grep -Eq '(^|[[:space:]])(vmx|svm)([[:space:]]|$)' /proc/cpuinfo 2>/dev/null; }
get_mem_line(){ free -h 2>/dev/null | awk '/^Mem:/{print $2"|"$3"|"$7}' || printf 'UNKNOWN|UNKNOWN|UNKNOWN'; }
get_swap_line(){ free -h 2>/dev/null | awk '/^Swap:/{print $2"|"$3}' || printf 'UNKNOWN|UNKNOWN'; }
get_rootfs_line(){ df -hPT / 2>/dev/null | awk 'NR==2{print $2"|"$3"|"$4"|"$5"|"$6"|"$7}' || printf 'UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|/'; }
get_uptime(){ uptime -p 2>/dev/null | sed 's/^up //' || printf UNKNOWN; }
get_load(){ awk '{print $1", "$2", "$3}' /proc/loadavg 2>/dev/null || printf UNKNOWN; }
get_tcp(){ sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || printf UNKNOWN; }
get_virt(){
  if command -v systemd-detect-virt >/dev/null 2>&1; then
    local v; v="$(systemd-detect-virt 2>/dev/null || true)"; printf '%s' "${v:-none}"
  elif grep -qa docker /proc/1/cgroup 2>/dev/null; then printf Docker
  elif grep -qa lxc /proc/1/cgroup 2>/dev/null; then printf LXC
  else printf UNKNOWN
  fi
}
get_cloudpanel(){ if command -v clpctl >/dev/null 2>&1 || [[ -d /home/clp/htdocs/app ]]; then printf INSTALLED; else printf NOT_DETECTED; fi; }
get_public_ip(){
  local fam="$1"
  if (( DEMO )); then
    [[ "$fam" == 4 ]] && printf '134.199.214.199' || printf '2604:a880::1234'
    return
  fi
  command -v curl >/dev/null 2>&1 || { printf UNAVAILABLE; return; }
  curl "-$fam" -fsS --connect-timeout 3 --max-time 5 https://api64.ipify.org 2>/dev/null || printf OFFLINE
}
get_ipmeta(){
  if (( DEMO )); then printf 'AS14061 DigitalOcean, LLC|San Francisco|California|US'; return; fi
  command -v curl >/dev/null 2>&1 || { printf 'UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN'; return; }
  local raw
  raw="$(curl -4fsS --connect-timeout 3 --max-time 6 https://ipinfo.io/json 2>/dev/null || true)"
  if [[ -n "$raw" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$raw" <<'PY' 2>/dev/null || printf 'UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN'
import json,sys
try:
 d=json.loads(sys.argv[1])
 print("|".join(str(d.get(k,"UNKNOWN")) for k in ("org","city","region","country")))
except Exception:
 print("UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN")
PY
  else
    printf 'UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN'
  fi
}

collect(){
  OS="$(get_os)"; ARCH="$(get_arch)"; KERNEL="$(get_kernel)"
  CPU="$(get_cpu)"; CORES="$(get_cores)"; FREQ="$(get_freq)"; CACHE="$(get_cache)"
  AES=0; has_aes && AES=1
  NESTED_VIRT=0; has_nested_virt_flag && NESTED_VIRT=1
  IFS='|' read -r RAM_TOTAL RAM_USED RAM_AVAIL <<<"$(get_mem_line)"
  IFS='|' read -r SWAP_TOTAL SWAP_USED <<<"$(get_swap_line)"
  IFS='|' read -r FS_TYPE DISK_TOTAL DISK_USED DISK_FREE DISK_PCT FS_MOUNT <<<"$(get_rootfs_line)"
  UPTIME="$(get_uptime)"; LOAD="$(get_load)"; TCP="$(get_tcp)"; VIRT="$(get_virt)"
  CLOUDPANEL="$(get_cloudpanel)"; IPV4="$(get_public_ip 4)"; IPV6="$(get_public_ip 6)"
  IFS='|' read -r ORG CITY REGION COUNTRY <<<"$(get_ipmeta)"
}

human(){
  collect
  printf '%s%sP07 · VPS Inspect%s  %sv%s%s\n' "$BOLD" "$CYAN" "$RESET" "$BLUE" "$VERSION" "$RESET"
  rule
  printf '  CPU Model          %s%s%s\n' "$CYAN" "$CPU" "$RESET"
  printf '  CPU Cores          %s @ %s\n' "$CORES" "$FREQ"
  printf '  CPU Cache          %s\n' "$CACHE"
  printf '  AES-NI             '; yesno "$AES"; printf '\n'
  printf '  Nested Virt Flag   '; yesno "$NESTED_VIRT"; printf '\n'
  printf '  Total RAM          %s%s%s  (%s used, %s available)\n' "$YELLOW" "$RAM_TOTAL" "$RESET" "$RAM_USED" "$RAM_AVAIL"
  printf '  Total Swap         %s  (%s used)\n' "$SWAP_TOTAL" "$SWAP_USED"
  printf '  Root Filesystem    %s%s%s  (%s used, %s free, %s, %s)\n' "$YELLOW" "$DISK_TOTAL" "$RESET" "$DISK_USED" "$DISK_FREE" "$DISK_PCT" "$FS_TYPE"
  printf '  System Uptime      %s\n' "$UPTIME"
  printf '  Load Average       %s\n' "$LOAD"
  printf '  OS                 %s\n' "$OS"
  printf '  Arch               %s\n' "$ARCH"
  printf '  Kernel             %s\n' "$KERNEL"
  printf '  TCP Congestion     %s%s%s\n' "$YELLOW" "$TCP" "$RESET"
  printf '  Virtualization     %s%s%s\n' "$CYAN" "$VIRT" "$RESET"
  printf '  CloudPanel         '
  [[ "$CLOUDPANEL" == INSTALLED ]] && printf '%s✓ Installed%s\n' "$GREEN" "$RESET" || printf '%sNot detected%s\n' "$GRAY" "$RESET"
  printf '  IPv4               '
  [[ "$IPV4" != OFFLINE && "$IPV4" != UNAVAILABLE ]] && printf '%s✓ %s%s\n' "$GREEN" "$IPV4" "$RESET" || printf '%s✗ %s%s\n' "$RED" "$IPV4" "$RESET"
  printf '  IPv6               '
  [[ "$IPV6" != OFFLINE && "$IPV6" != UNAVAILABLE ]] && printf '%s✓ %s%s\n' "$GREEN" "$IPV6" "$RESET" || printf '%s✗ %s%s\n' "$GRAY" "$IPV6" "$RESET"
  printf '  Organization       %s\n' "$ORG"
  printf '  Location           %s / %s / %s\n' "$CITY" "$REGION" "$COUNTRY"
  rule
  printf '%s只读验机：Root Filesystem 不代表多盘机器的总磁盘容量；Nested Virt Flag 仅表示来宾系统是否暴露 vmx/svm。%s\n' "$GRAY" "$RESET"
  printf '%s未运行磁盘写入、CPU 跑分或满速网络测试。%s\n' "$GRAY" "$RESET"
}

json_output(){
  collect
  if ! command -v python3 >/dev/null 2>&1; then printf '{"status":"UNAVAILABLE","reason":"python3_required"}\n'; return 1; fi
  python3 - "$VERSION" "$OS" "$ARCH" "$KERNEL" "$CPU" "$CORES" "$FREQ" "$CACHE" "$AES" "$NESTED_VIRT" "$RAM_TOTAL" "$RAM_USED" "$RAM_AVAIL" "$SWAP_TOTAL" "$SWAP_USED" "$FS_TYPE" "$DISK_TOTAL" "$DISK_USED" "$DISK_FREE" "$DISK_PCT" "$FS_MOUNT" "$UPTIME" "$LOAD" "$TCP" "$VIRT" "$CLOUDPANEL" "$IPV4" "$IPV6" "$ORG" "$CITY" "$REGION" "$COUNTRY" <<'PY'
import json,sys
(v,osname,arch,kernel,cpu,cores,freq,cache,aes,nested,rt,ru,ra,st,su,fstype,dt,du,df,dp,mount,uptime,load,tcp,virt,cp,ipv4,ipv6,org,city,region,country)=sys.argv[1:]
print(json.dumps({
 "schema_version":1,"module":"p07-inspect","version":v,
 "cpu":{"model":cpu,"cores":cores,"frequency":freq,"cache":cache,"aes_ni":aes=="1","nested_virtualization_flag":nested=="1"},
 "memory":{"total":rt,"used":ru,"available":ra,"swap_total":st,"swap_used":su},
 "disk":{"scope":"root_filesystem","filesystem_type":fstype,"total":dt,"used":du,"free":df,"used_percent":dp,"mount":mount},
 "system":{"os":osname,"arch":arch,"kernel":kernel,"uptime":uptime,"load_average":load,"tcp_congestion":tcp,"virtualization":virt,"cloudpanel":cp},
 "network":{"ipv4":ipv4,"ipv6":ipv6,"organization":org,"city":city,"region":region,"country":country}
},ensure_ascii=False,indent=2))
PY
}

self_test(){
  local f=0
  [[ -n "$(get_os)" ]] || f=1
  [[ -n "$(get_cores)" ]] || f=1
  [[ "$(get_rootfs_line)" == *"|"* ]] || f=1
  local old="$DEMO"; DEMO=1
  [[ "$(get_public_ip 4)" == "134.199.214.199" ]] || f=1
  DEMO="$old"
  if (( f )); then printf 'SELF_TEST=FAIL\n'; return 1; else printf 'SELF_TEST=PASS\n'; fi
}

case "$MODE" in
  json) json_output ;;
  selftest) self_test ;;
  *) human ;;
esac
