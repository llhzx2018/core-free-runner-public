#!/usr/bin/env bash
set -uo pipefail

APP="P07 Inspect"
VERSION="0.3.0"
DEMO=0
MODE="human"
INVENTORY_JSON="${VFOPS_INVENTORY_JSON:-}"

while (($#)); do
  case "$1" in
    --demo) DEMO=1 ;;
    --json) MODE="json" ;;
    --inventory-json) shift; INVENTORY_JSON="${1:-}" ;;
    --self-test) MODE="selftest" ;;
    --version) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
    -h|--help)
      cat <<EOH
$APP $VERSION
Usage:
  p07-inspect.sh [--demo]
  p07-inspect.sh --json [--inventory-json FILE]
  p07-inspect.sh --inventory-json FILE
  p07-inspect.sh --self-test
EOH
      exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RESET=$'\033[0m'; BOLD=$'\033[1m'; CYAN=$'\033[38;5;45m'; BLUE=$'\033[38;5;39m'
  GREEN=$'\033[38;5;48m'; YELLOW=$'\033[38;5;220m'; RED=$'\033[38;5;203m'; GRAY=$'\033[38;5;245m'
else
  RESET=""; BOLD=""; CYAN=""; BLUE=""; GREEN=""; YELLOW=""; RED=""; GRAY=""
fi

rule(){ printf '%s\n' '────────────────────────────────────────────────────────────────────────────'; }
yesno(){ if [[ "$1" == "1" ]]; then printf '%s✓ Enabled%s' "$GREEN" "$RESET"; else printf '%s✗ Disabled%s' "$GRAY" "$RESET"; fi; }
get_os(){ if [[ -r /etc/os-release ]]; then awk -F= '/^PRETTY_NAME=/{gsub(/^"|"$/,"",$2);print $2}' /etc/os-release; else uname -s; fi; }
get_arch(){ uname -m 2>/dev/null || printf UNKNOWN; }
get_kernel(){ uname -r 2>/dev/null || printf UNKNOWN; }
get_cpu(){ awk -F: '/model name/{gsub(/^[ \t]+/,"",$2);print $2;exit}' /proc/cpuinfo 2>/dev/null || printf UNKNOWN; }
get_cores(){ getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || printf '?'; }
get_freq(){ if command -v lscpu >/dev/null 2>&1; then local v; v="$(lscpu 2>/dev/null | awk -F: '/CPU max MHz/{gsub(/^[ \t]+/,"",$2);printf "%.0f MHz",$2;exit}')"; [[ -n "$v" ]] && { printf '%s' "$v"; return; }; fi; awk -F: '/cpu MHz/{gsub(/^[ \t]+/,"",$2);printf "%.0f MHz",$2;exit}' /proc/cpuinfo 2>/dev/null || printf UNKNOWN; }
get_cache(){ awk -F: '/cache size/{gsub(/^[ \t]+/,"",$2);print $2;exit}' /proc/cpuinfo 2>/dev/null || printf UNKNOWN; }
has_aes(){ grep -Eq '(^|[[:space:]])aes([[:space:]]|$)' /proc/cpuinfo 2>/dev/null; }
has_nested_virt_flag(){ grep -Eq '(^|[[:space:]])(vmx|svm)([[:space:]]|$)' /proc/cpuinfo 2>/dev/null; }
get_mem_line(){ free -h 2>/dev/null | awk '/^Mem:/{print $2"|"$3"|"$7}' || printf 'UNKNOWN|UNKNOWN|UNKNOWN'; }
get_swap_line(){ free -h 2>/dev/null | awk '/^Swap:/{print $2"|"$3}' || printf 'UNKNOWN|UNKNOWN'; }
get_rootfs_line(){ df -hPT / 2>/dev/null | awk 'NR==2{print $2"|"$3"|"$4"|"$5"|"$6"|"$7}' || printf 'UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|/'; }
get_uptime(){ uptime -p 2>/dev/null | sed 's/^up //' || printf UNKNOWN; }
get_load(){ awk '{print $1", "$2", "$3}' /proc/loadavg 2>/dev/null || printf UNKNOWN; }
get_tcp(){ sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || printf UNKNOWN; }
get_virt(){ if command -v systemd-detect-virt >/dev/null 2>&1; then local v; v="$(systemd-detect-virt 2>/dev/null || true)"; printf '%s' "${v:-none}"; elif grep -qa docker /proc/1/cgroup 2>/dev/null; then printf Docker; elif grep -qa lxc /proc/1/cgroup 2>/dev/null; then printf LXC; else printf UNKNOWN; fi; }
get_cloudpanel(){ if (( DEMO )); then printf INSTALLED; elif command -v clpctl >/dev/null 2>&1 || [[ -d /home/clp/htdocs/app ]]; then printf INSTALLED; else printf NOT_DETECTED; fi; }
get_public_ip(){ local fam="$1"; if (( DEMO )); then [[ "$fam" == 4 ]] && printf '134.199.214.199' || printf '2604:a880::1234'; return; fi; command -v curl >/dev/null 2>&1 || { printf UNAVAILABLE; return; }; curl "-$fam" -fsS --connect-timeout 3 --max-time 5 https://api64.ipify.org 2>/dev/null || printf OFFLINE; }
get_ipmeta(){
  if (( DEMO )); then printf 'AS14061 DigitalOcean, LLC|San Francisco|California|US'; return; fi
  command -v curl >/dev/null 2>&1 || { printf 'UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN'; return; }
  local raw; raw="$(curl -4fsS --connect-timeout 3 --max-time 6 https://ipinfo.io/json 2>/dev/null || true)"
  if [[ -n "$raw" ]] && command -v python3 >/dev/null 2>&1; then python3 - "$raw" <<'PY' 2>/dev/null || printf 'UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN'
import json,sys
try:
 d=json.loads(sys.argv[1]); print("|".join(str(d.get(k,"UNKNOWN")) for k in ("org","city","region","country")))
except Exception: print("UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN")
PY
  else printf 'UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN'; fi
}

find_inventory_py(){
  local script_dir p
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || pwd)"
  for p in "${VFOPS_INVENTORY_PY:-}" "$script_dir/../lib/inventory.py" "/opt/vf-server-ops/lib/inventory.py"; do
    [[ -n "$p" && -r "$p" ]] && { printf '%s' "$p"; return 0; }
  done
  return 1
}

inventory_payload(){
  if (( DEMO )); then
    cat <<'JSON'
{"schema":"vf-server-ops.inventory.v1","system":{"cloudpanel_version":"2.5-demo"},"discovery_source":"cloudpanel_db+vhost","summary":{"site_count":3,"mysql_database_count_known":2,"sqlite_file_count_known":1,"pm2_process_count_known":1},"warnings":[]}
JSON
    return 0
  fi
  if [[ -n "$INVENTORY_JSON" && -r "$INVENTORY_JSON" ]]; then cat "$INVENTORY_JSON"; return 0; fi
  local inv; inv="$(find_inventory_py 2>/dev/null || true)"
  [[ -n "$inv" && -x "$(command -v python3 2>/dev/null || true)" ]] || return 1
  command -v timeout >/dev/null 2>&1 || return 1
  timeout 20s python3 "$inv" --compact 2>/dev/null
}

get_inventory_summary(){
  local raw
  raw="$(inventory_payload 2>/dev/null || true)"
  if [[ -z "$raw" ]] || ! command -v python3 >/dev/null 2>&1; then printf 'UNAVAILABLE|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN'; return; fi
  python3 - "$raw" <<'PY' 2>/dev/null || printf 'UNAVAILABLE|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN'
import json,sys
try:
 d=json.loads(sys.argv[1]); s=d.get('summary') or {}; w=d.get('warnings') or []
 vals=['AVAILABLE',d.get('system',{}).get('cloudpanel_version','UNKNOWN'),d.get('discovery_source','UNKNOWN'),s.get('site_count','UNKNOWN'),s.get('mysql_database_count_known','UNKNOWN'),s.get('sqlite_file_count_known','UNKNOWN'),s.get('pm2_process_count_known','UNKNOWN'),len(w)]
 print('|'.join(map(str,vals)))
except Exception:
 print('UNAVAILABLE|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN')
PY
}

collect(){
  OS="$(get_os)"; ARCH="$(get_arch)"; KERNEL="$(get_kernel)"; CPU="$(get_cpu)"; CORES="$(get_cores)"; FREQ="$(get_freq)"; CACHE="$(get_cache)"
  AES=0; has_aes && AES=1; NESTED_VIRT=0; has_nested_virt_flag && NESTED_VIRT=1
  IFS='|' read -r RAM_TOTAL RAM_USED RAM_AVAIL <<<"$(get_mem_line)"; IFS='|' read -r SWAP_TOTAL SWAP_USED <<<"$(get_swap_line)"
  IFS='|' read -r FS_TYPE DISK_TOTAL DISK_USED DISK_FREE DISK_PCT FS_MOUNT <<<"$(get_rootfs_line)"
  UPTIME="$(get_uptime)"; LOAD="$(get_load)"; TCP="$(get_tcp)"; VIRT="$(get_virt)"; CLOUDPANEL="$(get_cloudpanel)"
  IPV4="$(get_public_ip 4)"; IPV6="$(get_public_ip 6)"; IFS='|' read -r ORG CITY REGION COUNTRY <<<"$(get_ipmeta)"
  IFS='|' read -r INV_STATUS CP_VERSION INV_SOURCE SITE_COUNT MYSQL_COUNT SQLITE_COUNT PM2_COUNT INV_WARNINGS <<<"$(get_inventory_summary)"
}

human(){
  collect
  printf '%s%sP07 · VPS Inspect%s  %sv%s%s\n' "$BOLD" "$CYAN" "$RESET" "$BLUE" "$VERSION" "$RESET"; rule
  printf '  CPU Model          %s%s%s\n' "$CYAN" "$CPU" "$RESET"; printf '  CPU Cores          %s @ %s\n' "$CORES" "$FREQ"; printf '  CPU Cache          %s\n' "$CACHE"
  printf '  AES-NI             '; yesno "$AES"; printf '\n'; printf '  Nested Virt Flag   '; yesno "$NESTED_VIRT"; printf '\n'
  printf '  Total RAM          %s%s%s  (%s used, %s available)\n' "$YELLOW" "$RAM_TOTAL" "$RESET" "$RAM_USED" "$RAM_AVAIL"; printf '  Total Swap         %s  (%s used)\n' "$SWAP_TOTAL" "$SWAP_USED"
  printf '  Root Filesystem    %s%s%s  (%s used, %s free, %s, %s)\n' "$YELLOW" "$DISK_TOTAL" "$RESET" "$DISK_USED" "$DISK_FREE" "$DISK_PCT" "$FS_TYPE"
  printf '  System Uptime      %s\n  Load Average       %s\n  OS                 %s\n  Arch               %s\n  Kernel             %s\n' "$UPTIME" "$LOAD" "$OS" "$ARCH" "$KERNEL"
  printf '  TCP Congestion     %s%s%s\n  Virtualization     %s%s%s\n' "$YELLOW" "$TCP" "$RESET" "$CYAN" "$VIRT" "$RESET"
  printf '  CloudPanel         '; [[ "$CLOUDPANEL" == INSTALLED ]] && printf '%s✓ Installed%s' "$GREEN" "$RESET" || printf '%sNot detected%s' "$GRAY" "$RESET"; [[ "$CP_VERSION" != UNKNOWN ]] && printf ' · %s' "$CP_VERSION"; printf '\n'
  if [[ "$INV_STATUS" == AVAILABLE ]]; then
    printf '  CloudPanel Sites   %s%s%s  (MySQL %s · SQLite %s · PM2 %s)\n' "$GREEN" "$SITE_COUNT" "$RESET" "$MYSQL_COUNT" "$SQLITE_COUNT" "$PM2_COUNT"
    printf '  Inventory Source   %s%s%s' "$CYAN" "$INV_SOURCE" "$RESET"; [[ "$INV_WARNINGS" =~ ^[0-9]+$ && "$INV_WARNINGS" -gt 0 ]] && printf ' · %s%s warning(s)%s' "$YELLOW" "$INV_WARNINGS" "$RESET"; printf '\n'
  else
    printf '  CloudPanel Sites   %sUNKNOWN%s  %s(P07 Inventory Authority unavailable in this standalone context)%s\n' "$GRAY" "$RESET" "$GRAY" "$RESET"
  fi
  printf '  IPv4               '; [[ "$IPV4" != OFFLINE && "$IPV4" != UNAVAILABLE ]] && printf '%s✓ %s%s\n' "$GREEN" "$IPV4" "$RESET" || printf '%s✗ %s%s\n' "$RED" "$IPV4" "$RESET"
  printf '  IPv6               '; [[ "$IPV6" != OFFLINE && "$IPV6" != UNAVAILABLE ]] && printf '%s✓ %s%s\n' "$GREEN" "$IPV6" "$RESET" || printf '%s✗ %s%s\n' "$GRAY" "$IPV6" "$RESET"
  printf '  Organization       %s\n  Location           %s / %s / %s\n' "$ORG" "$CITY" "$REGION" "$COUNTRY"; rule
  printf '%sCloudPanel 站点数量只接受 P07 Inventory Authority；Inspect 不复制第二套站点发现逻辑。%s\n' "$GRAY" "$RESET"
  printf '%s只读验机：未运行磁盘写入、CPU 跑分或满速网络测试。%s\n' "$GRAY" "$RESET"
}

json_output(){
  collect; command -v python3 >/dev/null 2>&1 || { printf '{"status":"UNAVAILABLE","reason":"python3_required"}\n'; return 1; }
  python3 - "$VERSION" "$OS" "$ARCH" "$KERNEL" "$CPU" "$CORES" "$FREQ" "$CACHE" "$AES" "$NESTED_VIRT" "$RAM_TOTAL" "$RAM_USED" "$RAM_AVAIL" "$SWAP_TOTAL" "$SWAP_USED" "$FS_TYPE" "$DISK_TOTAL" "$DISK_USED" "$DISK_FREE" "$DISK_PCT" "$FS_MOUNT" "$UPTIME" "$LOAD" "$TCP" "$VIRT" "$CLOUDPANEL" "$IPV4" "$IPV6" "$ORG" "$CITY" "$REGION" "$COUNTRY" "$INV_STATUS" "$CP_VERSION" "$INV_SOURCE" "$SITE_COUNT" "$MYSQL_COUNT" "$SQLITE_COUNT" "$PM2_COUNT" "$INV_WARNINGS" <<'PY'
import json,sys
(v,osname,arch,kernel,cpu,cores,freq,cache,aes,nested,rt,ru,ra,st,su,fstype,dt,du,df,dp,mount,uptime,load,tcp,virt,cp,ipv4,ipv6,org,city,region,country,inv_status,cpver,inv_source,sites,mysql,sqlite,pm2,warnings)=sys.argv[1:]
print(json.dumps({"schema_version":2,"module":"p07-inspect","version":v,"cpu":{"model":cpu,"cores":cores,"frequency":freq,"cache":cache,"aes_ni":aes=="1","nested_virtualization_flag":nested=="1"},"memory":{"total":rt,"used":ru,"available":ra,"swap_total":st,"swap_used":su},"disk":{"scope":"root_filesystem","filesystem_type":fstype,"total":dt,"used":du,"free":df,"used_percent":dp,"mount":mount},"system":{"os":osname,"arch":arch,"kernel":kernel,"uptime":uptime,"load_average":load,"tcp_congestion":tcp,"virtualization":virt,"cloudpanel_detected":cp},"inventory":{"status":inv_status,"cloudpanel_version":cpver,"discovery_source":inv_source,"site_count":sites,"mysql_database_count_known":mysql,"sqlite_file_count_known":sqlite,"pm2_process_count_known":pm2,"warning_count":warnings},"network":{"ipv4":ipv4,"ipv6":ipv6,"organization":org,"city":city,"region":region,"country":country}},ensure_ascii=False,indent=2))
PY
}

self_test(){
  local f=0 old="$DEMO"
  [[ -n "$(get_os)" ]] || f=1; [[ -n "$(get_cores)" ]] || f=1; [[ "$(get_rootfs_line)" == *"|"* ]] || f=1
  DEMO=1; [[ "$(get_public_ip 4)" == "134.199.214.199" ]] || f=1
  local inv; inv="$(get_inventory_summary)"; [[ "$inv" == AVAILABLE\|2.5-demo\|cloudpanel_db+vhost\|3\|2\|1\|1\|0 ]] || f=1
  DEMO="$old"
  if (( f )); then printf 'SELF_TEST=FAIL\n'; return 1; else printf 'SELF_TEST=PASS\n'; fi
}

case "$MODE" in json) json_output;; selftest) self_test;; *) human;; esac
