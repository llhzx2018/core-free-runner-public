#!/usr/bin/env bash
set -uo pipefail

APP="P07 Enhanced Bench"
VERSION="0.3.0"
DEMO=0
SELF_TEST=0
IO_MIB="${P07_BENCH_IO_MIB:-256}"
BENCH_DIR="${P07_BENCH_DIR:-/var/tmp}"
OOKLA_VERSION="1.2.0"

OOKLA_X86_64_SHA256="5690596c54ff9bed63fa3732f818a05dbc2db19ad36ed68f21ca5f64d5cfeeb7"
OOKLA_I386_SHA256="9ff7e18dbae7ee0e03c66108445a2fb6ceea6c86f66482e1392f55881b772fe8"
OOKLA_AARCH64_SHA256="3953d231da3783e2bf8904b6dd72767c5c6e533e163d3742fd0437affa431bd3"
OOKLA_ARMHF_SHA256="e45fcdebbd8a185553535533dd032d6b10bc8c64eee4139b1147b9c09835d08d"
OOKLA_ARMEL_SHA256="629a455a2879224bd0dbd4b36d8c721dda540717937e4660b4d2c966029466bf"

while (($#)); do
  case "$1" in
    --demo) DEMO=1 ;;
    --self-test) SELF_TEST=1 ;;
    --version) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
    -h|--help)
      cat <<'EOF'
P07 Enhanced Bench
Usage:
  p07-bench.sh              Run complete one-shot VPS acceptance
  p07-bench.sh --demo       Render a no-impact demo
  p07-bench.sh --self-test  Run internal logic tests
  p07-bench.sh --version

Environment:
  P07_BENCH_IO_MIB=256      Per-round disk write size (3 rounds)
  P07_BENCH_DIR=/var/tmp    Real filesystem path used for I/O
EOF
      exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RESET=$'\033[0m'; BOLD=$'\033[1m'
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'
  BLUE=$'\033[0;36m'; MAGENTA=$'\033[0;35m'; GRAY=$'\033[0;90m'
else
  RESET=""; BOLD=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; MAGENTA=""; GRAY=""
fi

rule(){ printf '%s\n' '----------------------------------------------------------------------'; }
color_state(){
  case "$1" in
    PASS|NORMAL) printf '%s%s%s' "$GREEN" "$1" "$RESET" ;;
    RISK|PARTIAL|INCONCLUSIVE|SKIPPED|UNAVAILABLE) printf '%s%s%s' "$YELLOW" "$1" "$RESET" ;;
    FAIL|HIGH_RISK) printf '%s%s%s' "$RED" "$1" "$RESET" ;;
    *) printf '%s' "$1" ;;
  esac
}

# One-shot mode never asks for stdin. Remove accidental terminal echo before each result row
# and drain pending keystrokes before returning to the parent shell.
tty_clean_line(){ [[ -t 1 ]] && printf '\r\033[2K' || true; }
drain_tty_input(){
  [[ -r /dev/tty ]] || return 0
  while IFS= read -r -t 0.001 -n 1 _ </dev/tty 2>/dev/null; do :; done
  return 0
}

START_EPOCH="$(date +%s)"
if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  STATE_BASE="/var/lib/p07-bench"
else
  STATE_BASE="${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/p07-bench"
fi
REPORT_DIR="$STATE_BASE/reports"
mkdir -p "$REPORT_DIR" 2>/dev/null || REPORT_DIR="/tmp/p07-bench-reports"
mkdir -p "$REPORT_DIR" 2>/dev/null || true

TMP_DIR="$(mktemp -d -t p07-bench.XXXXXX 2>/dev/null || printf '/tmp/p07-bench.%s' "$$")"
mkdir -p "$TMP_DIR" 2>/dev/null || true
RAW_LOG="$TMP_DIR/raw.log"
NETWORK_TSV="$TMP_DIR/network.tsv"
: >"$NETWORK_TSV"
SPEEDTEST_BIN=""
SPEEDTEST_TEMP=0

cleanup(){
  drain_tty_input
  if [[ $SPEEDTEST_TEMP -eq 1 && -n "$SPEEDTEST_BIN" ]]; then
    rm -rf "$(dirname "$SPEEDTEST_BIN")" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR" 2>/dev/null || true
}
trap cleanup EXIT
trap 'printf "\n%sTest interrupted. Cleaning up...%s\n" "$RED" "$RESET"; exit 130' INT TERM

exec > >(tee -a "$RAW_LOG") 2>&1

get_os(){
  if [[ -r /etc/os-release ]]; then
    awk -F= '/^PRETTY_NAME=/{gsub(/^"|"$/,"",$2);print $2}' /etc/os-release
  elif [[ -r /etc/lsb-release ]]; then
    awk -F= '/^DISTRIB_DESCRIPTION=/{gsub(/^"|"$/,"",$2);print $2}' /etc/lsb-release
  elif [[ -r /etc/redhat-release ]]; then
    cat /etc/redhat-release
  else
    uname -s
  fi
}
get_arch(){ uname -m 2>/dev/null || printf UNKNOWN; }
get_bits(){ getconf LONG_BIT 2>/dev/null || { [[ "$(uname -m)" == *64* ]] && printf 64 || printf 32; }; }
get_kernel(){ uname -r 2>/dev/null || printf UNKNOWN; }
get_cpu(){
  if command -v lscpu >/dev/null 2>&1; then
    lscpu 2>/dev/null | awk -F: '/Model name/{gsub(/^[ \t]+/,"",$2);print $2;exit}'
  else
    awk -F: '/model name/{gsub(/^[ \t]+/,"",$2);print $2;exit}' /proc/cpuinfo 2>/dev/null
  fi
}
get_cores(){ getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || printf '?'; }
get_freq(){
  local v=""
  if command -v lscpu >/dev/null 2>&1; then
    v="$(lscpu 2>/dev/null | awk -F: '/CPU max MHz/{gsub(/^[ \t]+/,"",$2);printf "%.0f MHz",$2;exit}')"
  fi
  [[ -n "$v" ]] && { printf '%s' "$v"; return; }
  awk -F: '/cpu MHz/{gsub(/^[ \t]+/,"",$2);printf "%.0f MHz",$2;exit}' /proc/cpuinfo 2>/dev/null || printf UNKNOWN
}
get_cache(){ awk -F: '/cache size/{gsub(/^[ \t]+/,"",$2);print $2;exit}' /proc/cpuinfo 2>/dev/null || printf UNKNOWN; }
has_flag(){ grep -Eq "(^|[[:space:]])$1([[:space:]]|$)" /proc/cpuinfo 2>/dev/null; }
get_mem(){ free -h 2>/dev/null | awk '/^Mem:/{print $2"|"$3}' || printf 'UNKNOWN|UNKNOWN'; }
get_swap(){ free -h 2>/dev/null | awk '/^Swap:/{print $2"|"$3}' || printf 'UNKNOWN|UNKNOWN'; }
get_uptime(){ uptime -p 2>/dev/null | sed 's/^up //' || printf UNKNOWN; }
get_load(){ awk '{print $1", "$2", "$3}' /proc/loadavg 2>/dev/null || printf UNKNOWN; }
get_tcp(){ sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || printf UNKNOWN; }

human_kib(){
  awk -v k="${1:-0}" 'BEGIN{
    if(k!~/^[0-9.]+$/){print "UNKNOWN";exit}
    b=k*1024;
    if(b>=1099511627776)printf "%.1f TB",b/1099511627776;
    else if(b>=1073741824)printf "%.1f GB",b/1073741824;
    else if(b>=1048576)printf "%.1f MB",b/1048576;
    else printf "%.1f KB",b/1024
  }'
}

get_total_disk_kib(){
  local pair swap_kib zsize zused
  pair="$(
    df -kPT 2>/dev/null | awk '
      NR>1 && $2 ~ /^(simfs|ext2|ext3|ext4|btrfs|xfs|vfat|ntfs|f2fs)$/ {
        key=$1 "|" $3;
        if(!seen[key]++){total+=$3; used+=$4}
      }
      END{printf "%.0f|%.0f",total,used}'
  )"
  IFS='|' read -r DISK_FS_TOTAL_KIB DISK_FS_USED_KIB <<<"${pair:-0|0}"
  DISK_FS_TOTAL_KIB="${DISK_FS_TOTAL_KIB:-0}"
  DISK_FS_USED_KIB="${DISK_FS_USED_KIB:-0}"

  swap_kib="$(awk '/^SwapTotal:/{print $2+0}' /proc/meminfo 2>/dev/null || printf 0)"
  DISK_SWAP_TOTAL_KIB="${swap_kib:-0}"
  DISK_SWAP_USED_KIB="$(free -k 2>/dev/null | awk '/^Swap:/{print $3+0}' || printf 0)"

  DISK_ZFS_TOTAL_KIB=0
  DISK_ZFS_USED_KIB=0
  if command -v zpool >/dev/null 2>&1; then
    zsize="$(zpool list -Hp -o size 2>/dev/null | awk '{s+=$1} END{printf "%.0f",s/1024}')"
    zused="$(zpool list -Hp -o allocated 2>/dev/null | awk '{s+=$1} END{printf "%.0f",s/1024}')"
    DISK_ZFS_TOTAL_KIB="${zsize:-0}"
    DISK_ZFS_USED_KIB="${zused:-0}"
  fi

  DISK_TOTAL_KIB=$(( ${DISK_FS_TOTAL_KIB%.*} + ${DISK_SWAP_TOTAL_KIB%.*} + ${DISK_ZFS_TOTAL_KIB%.*} ))
  DISK_USED_KIB=$(( ${DISK_FS_USED_KIB%.*} + ${DISK_SWAP_USED_KIB%.*} + ${DISK_ZFS_USED_KIB%.*} ))

  if (( DISK_TOTAL_KIB <= 0 )); then
    DISK_TOTAL_KIB="$(df -kP / 2>/dev/null | awk 'NR==2{print $2+0}')"
    DISK_USED_KIB="$(df -kP / 2>/dev/null | awk 'NR==2{print $3+0}')"
    DISK_SCOPE="ROOT_FALLBACK"
  else
    DISK_SCOPE="SUPPORTED_FS_PLUS_SWAP_ZFS"
  fi
  DISK_TOTAL="$(human_kib "$DISK_TOTAL_KIB")"
  DISK_USED="$(human_kib "$DISK_USED_KIB")"
}

read_dmi(){
  local p="$1"
  [[ -r "$p" ]] && tr -d '\000' <"$p" 2>/dev/null || true
}
get_virt(){
  local v="" vendor="" product="" bios=""
  if command -v systemd-detect-virt >/dev/null 2>&1; then
    v="$(systemd-detect-virt 2>/dev/null || true)"
    if [[ -n "$v" && "$v" != none ]]; then printf '%s' "${v^^}"; return; fi
  fi

  if grep -qa docker /proc/1/cgroup 2>/dev/null || [[ -f /.dockerenv ]]; then printf Docker; return; fi
  if grep -qa lxc /proc/1/cgroup 2>/dev/null || grep -qa 'container=lxc' /proc/1/environ 2>/dev/null; then printf LXC; return; fi
  if [[ -f /proc/user_beancounters || -d /proc/vz ]]; then printf OpenVZ; return; fi
  if [[ -e /proc/xen ]]; then
    grep -q control_d /proc/xen/capabilities 2>/dev/null && printf Xen-Dom0 || printf Xen-DomU
    return
  fi

  vendor="$(read_dmi /sys/class/dmi/id/sys_vendor)"
  product="$(read_dmi /sys/class/dmi/id/product_name)"
  bios="$(read_dmi /sys/class/dmi/id/bios_vendor)"
  case "$vendor $product $bios" in
    *KVM*|*QEMU*) printf KVM ;;
    *VMware*) printf VMware ;;
    *VirtualBox*|*innotek*) printf VirtualBox ;;
    *Parallels*) printf Parallels ;;
    *Microsoft*Virtual*Machine*|*Hyper-V*) printf Hyper-V ;;
    *Xen*) printf Xen ;;
    *) printf Dedicated/Unknown ;;
  esac
}

fetch_stdout(){
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 4 --max-time 8 "$url" 2>/dev/null
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- -T 8 "$url" 2>/dev/null
  else
    return 127
  fi
}
fetch_to_file(){
  local url="$1" out="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 2 --connect-timeout 8 --max-time 60 "$url" -o "$out" >/dev/null 2>&1
  elif command -v wget >/dev/null 2>&1; then
    wget -q --https-only --timeout=60 --tries=2 -O "$out" "$url"
  else
    return 127
  fi
}

get_public_ip(){
  local fam="$1"
  if (( DEMO )); then [[ "$fam" == 4 ]] && printf '137.184.42.82' || printf '2604:a880::1234'; return; fi
  if command -v curl >/dev/null 2>&1; then
    curl "-$fam" -fsS --connect-timeout 4 --max-time 7 https://api64.ipify.org 2>/dev/null || printf OFFLINE
  elif command -v wget >/dev/null 2>&1 && [[ "$fam" == 4 ]]; then
    wget -qO- -T 7 https://api.ipify.org 2>/dev/null || printf OFFLINE
  else
    printf OFFLINE
  fi
}
get_cloudpanel_summary(){
  if (( DEMO )); then printf 'Installed|3'; return; fi
  local db='/home/clp/htdocs/app/data/db.sq3'
  if [[ -r "$db" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$db" <<'PYCP' 2>/dev/null || printf 'Installed|UNKNOWN'
import sqlite3,sys
try:
    c=sqlite3.connect(f'file:{sys.argv[1]}?mode=ro',uri=True)
    n=c.execute('select count(*) from site').fetchone()[0]
    c.close()
    print(f'Installed|{n}')
except Exception:
    print('Installed|UNKNOWN')
PYCP
  elif command -v clpctl >/dev/null 2>&1 || [[ -d /home/clp/htdocs/app ]]; then
    printf 'Installed|UNKNOWN'
  else
    printf 'Not detected|0'
  fi
}
get_ipmeta(){
  if (( DEMO )); then printf 'AS14061 DigitalOcean, LLC|San Francisco|California|US'; return; fi
  local raw
  raw="$(fetch_stdout https://ipinfo.io/json 2>/dev/null || true)"
  if [[ -n "$raw" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$raw" <<'PY' 2>/dev/null || printf 'UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN'
import json,sys
try:
    d=json.loads(sys.argv[1])
    print('|'.join(str(d.get(k,'UNKNOWN')) for k in ('org','city','region','country')))
except Exception:
    print('UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN')
PY
  else
    printf 'UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN'
  fi
}

collect_system(){
  OS="$(get_os)"; ARCH="$(get_arch)"; BITS="$(get_bits)"; KERNEL="$(get_kernel)"
  CPU="$(get_cpu)"; CORES="$(get_cores)"; FREQ="$(get_freq)"; CACHE="$(get_cache)"
  AES="Disabled"; has_flag aes && AES="Enabled"
  NESTED="Disabled"; { has_flag vmx || has_flag svm; } && NESTED="Enabled"
  IFS='|' read -r RAM_TOTAL RAM_USED <<<"$(get_mem)"
  IFS='|' read -r SWAP_TOTAL SWAP_USED <<<"$(get_swap)"
  get_total_disk_kib
  UPTIME="$(get_uptime)"; LOAD="$(get_load)"; TCP="$(get_tcp)"; VIRT="$(get_virt)"
  IFS='|' read -r CLOUDPANEL_STATE CLOUDPANEL_SITES <<<"$(get_cloudpanel_summary)"
  IPV4="$(get_public_ip 4)"; IPV6="$(get_public_ip 6)"
  IFS='|' read -r ORG CITY REGION COUNTRY <<<"$(get_ipmeta)"
}

print_system(){
  printf '%s%s-------------------- P07 Enhanced Bench --------------------%s\n' "$BOLD" "$BLUE" "$RESET"
  printf ' Version            : %s%s%s\n' "$GREEN" "$VERSION" "$RESET"
  printf ' CPU Model          : %s%s%s\n' "$BLUE" "${CPU:-UNKNOWN}" "$RESET"
  printf ' CPU Cores          : %s%s%s @ %s\n' "$GREEN" "$CORES" "$RESET" "$FREQ"
  printf ' CPU Cache          : %s\n' "${CACHE:-UNKNOWN}"
  printf ' AES-NI             : %s\n' "$AES"
  printf ' VM-x / AMD-V Flag  : %s\n' "$NESTED"
  printf ' Total Disk         : %s%s%s  (%s used)\n' "$YELLOW" "$DISK_TOTAL" "$RESET" "$DISK_USED"
  printf ' Total RAM          : %s%s%s  (%s used)\n' "$YELLOW" "$RAM_TOTAL" "$RESET" "$RAM_USED"
  printf ' Total Swap         : %s  (%s used)\n' "$SWAP_TOTAL" "$SWAP_USED"
  printf ' System Uptime      : %s\n' "$UPTIME"
  printf ' Load Average       : %s\n' "$LOAD"
  printf ' OS                 : %s\n' "$OS"
  printf ' Arch               : %s (%s Bit)\n' "$ARCH" "$BITS"
  printf ' Kernel             : %s\n' "$KERNEL"
  printf ' TCP Congestion Ctrl: %s%s%s\n' "$YELLOW" "$TCP" "$RESET"
  printf ' Virtualization     : %s%s%s\n' "$BLUE" "$VIRT" "$RESET"
  if [[ "$CLOUDPANEL_STATE" == Installed ]]; then
    printf ' CloudPanel         : %sInstalled%s · %s site(s)\n' "$GREEN" "$RESET" "$CLOUDPANEL_SITES"
  else
    printf ' CloudPanel         : %sNot detected%s\n' "$GRAY" "$RESET"
  fi
  if [[ "$IPV4" == OFFLINE || "$IPV4" == UNAVAILABLE ]]; then
    printf ' IPv4              : %s%s%s\n' "$RED" "$IPV4" "$RESET"
  else
    printf ' IPv4              : %s%s%s  (ONLINE)\n' "$GREEN" "$IPV4" "$RESET"
  fi
  if [[ "$IPV6" == OFFLINE || "$IPV6" == UNAVAILABLE ]]; then
    printf ' IPv6              : %s%s%s\n' "$RED" "$IPV6" "$RESET"
  else
    printf ' IPv6              : %s%s%s  (ONLINE)\n' "$GREEN" "$IPV6" "$RESET"
  fi
  printf ' Organization       : %s%s%s\n' "$BLUE" "$ORG" "$RESET"
  printf ' Location           : %s / %s\n' "$CITY" "$COUNTRY"
  printf ' Region             : %s%s%s\n' "$YELLOW" "$REGION" "$RESET"
}

rate_to_mb(){
  local raw="$1" value unit
  value="$(awk '{print $1}' <<<"$raw")"; unit="$(awk '{print $2}' <<<"$raw")"
  awk -v v="$value" -v u="$unit" 'BEGIN{
    if(v!~/^[0-9.]+$/){print 0;exit}
    if(u=="GB/s")printf "%.2f",v*1000;
    else if(u=="MB/s")printf "%.2f",v;
    else if(u=="kB/s")printf "%.2f",v/1000;
    else if(u=="B/s")printf "%.2f",v/1000000;
    else print 0
  }'
}
format_mb_rate(){
  awk -v m="${1:-0}" 'BEGIN{if(m!~/^[0-9.]+$/){print "FAIL";exit} if(m>=1000)printf "%.2f GB/s",m/1000; else printf "%.0f MB/s",m}'
}
run_dd_once(){
  local file="$1" round="$2" out rc raw
  if (( DEMO )); then
    case "$round" in 1) printf '577 MB/s';; 2) printf '581 MB/s';; *) printf '565 MB/s';; esac
    return 0
  fi
  out="$(LANG=C dd if=/dev/zero of="$file" bs=1M count="$IO_MIB" oflag=direct conv=fdatasync 2>&1)"; rc=$?
  if (( rc != 0 )); then
    out="$(LANG=C dd if=/dev/zero of="$file" bs=1M count="$IO_MIB" conv=fdatasync 2>&1)"; rc=$?
  fi
  (( rc == 0 )) || { printf FAIL; rm -f "$file" 2>/dev/null || true; return 1; }
  raw="$(awk -F, 'END{gsub(/^[ \t]+|[ \t]+$/,"",$NF);print $NF}' <<<"$out")"
  rm -f "$file" 2>/dev/null || true
  printf '%s' "$raw"
}
print_io(){
  rule
  printf '%s%s I/O Speed%s  %s(3 x %s MiB, %s)%s\n' "$BOLD" "$MAGENTA" "$RESET" "$GRAY" "$IO_MIB" "$BENCH_DIR" "$RESET"
  IO_STATE="PASS"; IO_AVG_MB="0"; IO_RATES=()
  if ! [[ "$IO_MIB" =~ ^[0-9]+$ ]] || (( IO_MIB < 64 || IO_MIB > 1024 )); then
    IO_STATE="SKIPPED"; printf ' %-18s: invalid P07_BENCH_IO_MIB (64-1024 required)\n' 'I/O Test'; return
  fi
  if (( ! DEMO )); then
    [[ -d "$BENCH_DIR" && -w "$BENCH_DIR" ]] || { IO_STATE="SKIPPED"; printf ' %-18s: directory not writable\n' 'I/O Test'; return; }
    local fs free_mib
    fs="$(df -PT "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $2}')"
    if [[ "$fs" == tmpfs || "$fs" == devtmpfs ]]; then
      IO_STATE="SKIPPED"; printf ' %-18s: blocked on %s (not real disk)\n' 'I/O Test' "$fs"; return
    fi
    free_mib="$(df -Pm "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $4}')"
    [[ "$free_mib" =~ ^[0-9]+$ ]] && (( free_mib >= IO_MIB + 256 )) || {
      IO_STATE="SKIPPED"; printf ' %-18s: insufficient free space\n' 'I/O Test'; return
    }
  fi

  local i raw mb sum=0
  for i in 1 2 3; do
    raw="$(run_dd_once "$BENCH_DIR/.p07-bench-$$-$i.dat" "$i" || true)"
    if [[ "$raw" == FAIL || -z "$raw" ]]; then
      IO_STATE="FAIL"; printf ' I/O #%-13s: %sFAIL%s\n' "$i" "$RED" "$RESET"; continue
    fi
    mb="$(rate_to_mb "$raw")"
    IO_RATES+=("$mb")
    sum="$(awk -v a="$sum" -v b="$mb" 'BEGIN{printf "%.2f",a+b}')"
    printf ' I/O Speed(%s run)  : %s%s%s\n' "$i" "$GREEN" "$(format_mb_rate "$mb")" "$RESET"
  done
  if ((${#IO_RATES[@]})); then
    IO_AVG_MB="$(awk -v s="$sum" -v n="${#IO_RATES[@]}" 'BEGIN{printf "%.2f",s/n}')"
    printf ' I/O Speed(average) : %s%s%s\n' "$GREEN" "$(format_mb_rate "$IO_AVG_MB")" "$RESET"
  else
    IO_STATE="FAIL"
  fi
}

speedtest_arch(){
  local machine
  machine="$(uname -m 2>/dev/null || true)"
  case "$machine" in
    x86_64|amd64) printf 'x86_64|%s' "$OOKLA_X86_64_SHA256" ;;
    i386|i486|i586|i686) printf 'i386|%s' "$OOKLA_I386_SHA256" ;;
    aarch64|arm64|armv8|armv8l) printf 'aarch64|%s' "$OOKLA_AARCH64_SHA256" ;;
    armv7|armv7l) printf 'armhf|%s' "$OOKLA_ARMHF_SHA256" ;;
    armv6|armv6l) printf 'armel|%s' "$OOKLA_ARMEL_SHA256" ;;
    *) return 1 ;;
  esac
}
prepare_speedtest(){
  if (( DEMO )); then SPEEDTEST_BIN="DEMO"; return 0; fi
  if command -v speedtest >/dev/null 2>&1; then SPEEDTEST_BIN="$(command -v speedtest)"; return 0; fi
  command -v sha256sum >/dev/null 2>&1 || return 1
  command -v tar >/dev/null 2>&1 || return 1
  local pair pkg sha url d got
  pair="$(speedtest_arch 2>/dev/null || true)"
  [[ -n "$pair" ]] || return 1
  IFS='|' read -r pkg sha <<<"$pair"
  d="$TMP_DIR/ookla"; mkdir -p "$d"
  url="https://install.speedtest.net/app/cli/ookla-speedtest-${OOKLA_VERSION}-linux-${pkg}.tgz"
  fetch_to_file "$url" "$d/speedtest.tgz" || return 1
  got="$(sha256sum "$d/speedtest.tgz" | awk '{print $1}')"
  [[ "$got" == "$sha" ]] || {
    printf '%sSpeedtest checksum mismatch; network benchmark skipped.%s\n' "$RED" "$RESET"
    return 1
  }
  tar -xzf "$d/speedtest.tgz" -C "$d" speedtest >/dev/null 2>&1 || return 1
  chmod 0755 "$d/speedtest"
  SPEEDTEST_BIN="$d/speedtest"; SPEEDTEST_TEMP=1
}
network_reason(){
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
parse_speed_text(){
  local text="$1" up down lat
  up="$(awk '/Upload:/{print $2;exit}' <<<"$text")"
  down="$(awk '/Download:/{print $2;exit}' <<<"$text")"
  lat="$(awk '/Latency:/{print $2;exit}' <<<"$text")"
  [[ -n "$up" && -n "$down" && -n "$lat" ]] && printf '%s|%s|%s' "$up" "$down" "$lat"
}
speed_node(){
  local id="$1" name="$2" state reason up down lat raw rc parsed
  if (( DEMO )); then
    case "$name" in
      'Suzhou, CN'|'Ningbo, CN') state=FAIL; reason=TIMEOUT; up='-'; down='-'; lat='-' ;;
      'Speedtest.net') state=PASS; reason=NONE; up=1180.2; down=1260.4; lat=1.1 ;;
      'Los Angeles, US') state=PASS; reason=NONE; up=1120.1; down=1202.3; lat=1.3 ;;
      'Dallas, US') state=PASS; reason=NONE; up=930.4; down=1010.6; lat=32.1 ;;
      'Montreal, CA') state=PASS; reason=NONE; up=760.3; down=830.2; lat=72.4 ;;
      'Paris, FR') state=PASS; reason=NONE; up=720.1; down=840.7; lat=142.3 ;;
      'Amsterdam, NL') state=PASS; reason=NONE; up=760.2; down=810.4; lat=150.4 ;;
      'Hong Kong, CN') state=PASS; reason=NONE; up=690.1; down=720.4; lat=151.1 ;;
      'Singapore, SG') state=PASS; reason=NONE; up=720.8; down=760.2; lat=168.4 ;;
      'Taipei, CN') state=PASS; reason=NONE; up=700.5; down=735.4; lat=142.0 ;;
      'Tokyo, JP') state=PASS; reason=NONE; up=810.7; down=850.2; lat=112.2 ;;
      *) state=FAIL; reason=UNKNOWN; up='-'; down='-'; lat='-' ;;
    esac
  elif [[ -z "$SPEEDTEST_BIN" ]]; then
    state=UNAVAILABLE; reason=SPEEDTEST_UNAVAILABLE; up='-'; down='-'; lat='-'
  elif ! command -v timeout >/dev/null 2>&1; then
    state=UNAVAILABLE; reason=TIMEOUT_COMMAND_MISSING; up='-'; down='-'; lat='-'
  else
    local args=(--progress=no --accept-license --accept-gdpr)
    [[ -n "$id" ]] && args+=(--server-id="$id")
    if command -v python3 >/dev/null 2>&1; then
      raw="$(timeout 65s "$SPEEDTEST_BIN" "${args[@]}" --format=json 2>&1)"; rc=$?
      parsed=""
      if (( rc == 0 )); then
        parsed="$(python3 - "$raw" <<'PY' 2>/dev/null || true
import json,sys
try:
    d=json.loads(sys.argv[1])
    print(f"{d['upload']['bandwidth']*8/1e6:.2f}|{d['download']['bandwidth']*8/1e6:.2f}|{d['ping']['latency']:.2f}")
except Exception:
    pass
PY
)"
      fi
    else
      raw="$(timeout 65s "$SPEEDTEST_BIN" "${args[@]}" 2>&1)"; rc=$?
      parsed=""; (( rc == 0 )) && parsed="$(parse_speed_text "$raw" || true)"
    fi
    if [[ -n "$parsed" ]]; then
      IFS='|' read -r up down lat <<<"$parsed"; state=PASS; reason=NONE
    else
      state=FAIL; reason="$(network_reason "${rc:-1}" "$raw")"; up='-'; down='-'; lat='-'
    fi
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$name" "$state" "$reason" "$up" "$down" "$lat" >>"$NETWORK_TSV"
  tty_clean_line
  if [[ "$state" == PASS ]]; then
    printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\n' \
      "$YELLOW" "$name" "$RESET" "$GREEN" "$up Mbps" "$RESET" "$RED" "$down Mbps" "$RESET" "$BLUE" "$lat ms" "$RESET" "$GREEN" "PASS" "$RESET" '-'
  else
    printf ' %s%-17s%s %-13s %-15s %-9s %s%-7s%s %s%-18s%s\n' \
      "$YELLOW" "$name" "$RESET" '-' '-' '-' "$RED" "$state" "$RESET" "$YELLOW" "$reason" "$RESET"
  fi
}
print_network(){
  rule
  printf '%s Node Name         Upload        Download        Latency   State   Reason%s\n' "$BOLD$YELLOW" "$RESET"
  : >"$NETWORK_TSV"
  if ! prepare_speedtest; then SPEEDTEST_BIN=""; fi

  speed_node ''      'Speedtest.net'
  speed_node 7190    'Los Angeles, US'
  speed_node 22288   'Dallas, US'
  speed_node 64420   'Montreal, CA'
  speed_node 61933   'Paris, FR'
  speed_node 41423   'Amsterdam, NL'
  speed_node 5396    'Suzhou, CN'
  speed_node 59387   'Ningbo, CN'
  speed_node 32155   'Hong Kong, CN'
  speed_node 13623   'Singapore, SG'
  speed_node 65092   'Taipei, CN'
  speed_node 48463   'Tokyo, JP'
}

http_probe(){
  local url="$1"
  if (( DEMO )); then
    [[ "$url" == *baidu* || "$url" == *qq.com* || "$url" == *taobao* || "$url" == *189.cn* || "$url" == *10010* || "$url" == *10086* ]] && return 1
    return 0
  fi
  if command -v curl >/dev/null 2>&1; then
    curl -LsS -o /dev/null --connect-timeout 4 --max-time 8 "$url" >/dev/null 2>&1
  elif command -v wget >/dev/null 2>&1; then
    wget -q --spider --https-only --timeout=8 "$url" >/dev/null 2>&1
  else
    return 127
  fi
}
count_speed(){
  local pattern="$1" state="$2"
  awk -F '\t' -v p="$pattern" -v s="$state" '$2~p && $3==s{n++} END{print n+0}' "$NETWORK_TSV"
}
count_speed_reason(){
  local pattern="$1" reason_re="$2"
  awk -F '\t' -v p="$pattern" -v r="$reason_re" '$2~p && $3=="FAIL" && $4~r{n++} END{print n+0}' "$NETWORK_TSV"
}
china_verdict_from_counts(){
  local cn_pass="$1" cn_path_fail="$2" cn_node_unavailable="$3" overseas_speed_pass="$4" mainland_http="$5" mainland_fail="$6" overseas_http="$7"
  if (( cn_pass >= 1 && mainland_http >= 4 )); then printf NORMAL
  elif (( cn_path_fail >= 2 && overseas_speed_pass >= 5 && mainland_fail >= 3 && overseas_http >= 2 )); then printf HIGH_RISK
  elif (( cn_path_fail >= 2 && overseas_speed_pass >= 3 )) || (( mainland_fail >= 2 && overseas_http >= 2 )); then printf RISK
  else printf INCONCLUSIVE
  fi
}
china_assessment(){
  local overseas_http=0 mainland_http=0 mainland_fail=0 u cn_speed_pass cn_speed_fail cn_path_fail cn_node_unavailable overseas_speed_pass
  for u in https://www.cloudflare.com/ https://github.com/ https://www.google.com/; do http_probe "$u" && overseas_http=$((overseas_http+1)); done
  for u in https://www.baidu.com/ https://www.qq.com/ https://www.taobao.com/ https://www.189.cn/ https://www.10010.com/ https://www.10086.cn/; do
    if http_probe "$u"; then mainland_http=$((mainland_http+1)); else mainland_fail=$((mainland_fail+1)); fi
  done
  cn_speed_pass="$(count_speed 'Suzhou, CN|Ningbo, CN' PASS)"
  cn_speed_fail="$(count_speed 'Suzhou, CN|Ningbo, CN' FAIL)"
  cn_path_fail="$(count_speed_reason 'Suzhou, CN|Ningbo, CN' '^(TIMEOUT|CONNECTION_FAILED|DNS_FAILURE|TLS_FAILURE)$')"
  cn_node_unavailable="$(count_speed_reason 'Suzhou, CN|Ningbo, CN' '^NODE_UNAVAILABLE$')"
  overseas_speed_pass="$(awk -F '\t' '$2 !~ /Suzhou, CN|Ningbo, CN/ && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")"
  CHINA_VERDICT="$(china_verdict_from_counts "$cn_speed_pass" "$cn_path_fail" "$cn_node_unavailable" "$overseas_speed_pass" "$mainland_http" "$mainland_fail" "$overseas_http")"
  case "$CHINA_VERDICT" in
    NORMAL) CHINA_RECOMMENDATION="Current outbound signals look normal" ;;
    HIGH_RISK) CHINA_RECOMMENDATION="CHANGE IP BEFORE MIGRATION" ;;
    RISK) CHINA_RECOMMENDATION="VERIFY FROM MAINLAND BEFORE MIGRATION" ;;
    *) if (( cn_node_unavailable >= 1 )); then CHINA_RECOMMENDATION="RETRY WITH ALTERNATE MAINLAND SPEEDTEST NODES"; else CHINA_RECOMMENDATION="NEED MAINLAND-ORIGIN PROBE"; fi ;;
  esac
  rule
  printf '%s%s China Access Assessment%s\n' "$BOLD" "$BLUE" "$RESET"
  printf ' VPS -> Overseas HTTPS : %s%s / 3 PASS%s\n' "$GREEN" "$overseas_http" "$RESET"
  printf ' VPS -> Mainland HTTPS : %s / 6 PASS\n' "$mainland_http"
  printf ' VPS -> Mainland Speed : %s PASS / %s FAIL\n' "$cn_speed_pass" "$cn_speed_fail"
  printf '   Path failures         : %s\n' "$cn_path_fail"
  printf '   Node unavailable      : %s\n' "$cn_node_unavailable"
  printf ' Mainland -> VPS Probe: %sNOT_RUN%s\n' "$YELLOW" "$RESET"
  printf ' Risk                 : '; color_state "$CHINA_VERDICT"; printf '\n'
  printf ' Recommendation       : %s%s%s\n' "$YELLOW" "$CHINA_RECOMMENDATION" "$RESET"
  printf ' %sEvidence scope: current VPS outbound only. NODE_UNAVAILABLE is a test-node problem and is not counted as IP blocking evidence.%s\n' "$GRAY" "$RESET"
}


write_reports(){
  local ts clean elapsed
  ts="$(date +%Y%m%d_%H%M%S)"
  REPORT_TXT="$REPORT_DIR/p07-bench_${ts}.txt"
  REPORT_JSON="$REPORT_DIR/p07-bench_${ts}.json"
  clean="$TMP_DIR/clean.txt"
  sed -r 's/\x1B\[[0-9;]*[mK]//g' "$RAW_LOG" >"$clean" 2>/dev/null || cp "$RAW_LOG" "$clean"
  cp "$clean" "$REPORT_TXT" 2>/dev/null || REPORT_TXT="$clean"
  elapsed=$(( $(date +%s) - START_EPOCH ))

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$REPORT_JSON" "$VERSION" "$OS" "$CPU" "$CORES" "$RAM_TOTAL" "$DISK_TOTAL" "$DISK_USED" "$DISK_SCOPE" "$IPV4" "$ORG" "$CITY" "$COUNTRY" "$IO_STATE" "$IO_AVG_MB" "$CHINA_VERDICT" "$CHINA_RECOMMENDATION" "$elapsed" "$NETWORK_TSV" <<'PY' 2>/dev/null || true
import json,sys,datetime
(path,version,osname,cpu,cores,ram,disk,disk_used,disk_scope,ipv4,org,city,country,io_state,io_avg,verdict,reco,elapsed,tsv)=sys.argv[1:]
nodes=[]
try:
    for line in open(tsv,encoding='utf-8'):
        sid,name,state,reason,up,down,lat=line.rstrip('\n').split('\t')
        nodes.append({'server_id':sid,'name':name,'state':state,'reason':reason,'upload_mbps':up,'download_mbps':down,'latency_ms':lat})
except Exception:
    pass
payload={
  'schema_version':2,'module':'p07-bench','version':version,
  'timestamp':datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
  'system':{'os':osname,'cpu':cpu,'cores':cores,'ram':ram,'total_disk':disk,'disk_used':disk_used,'disk_scope':disk_scope,'ipv4':ipv4,'organization':org,'city':city,'country':country},
  'io':{'state':io_state,'average_mb_s':io_avg},
  'network_nodes':nodes,
  'china_ip_assessment':{'verdict':verdict,'recommendation':reco,'evidence_scope':'VPS_OUTBOUND_ONLY','mainland_origin_probe':'NOT_IMPLEMENTED'},
  'elapsed_seconds':int(elapsed)
}
with open(path,'w',encoding='utf-8') as f:
    json.dump(payload,f,ensure_ascii=False,indent=2)
PY
  fi
}

self_test(){
  local f=0
  [[ "$(rate_to_mb '1.20 GB/s')" == "1200.00" ]] || f=1
  [[ "$(rate_to_mb '577 MB/s')" == "577.00" ]] || f=1
  [[ "$(format_mb_rate '1500.00')" == "1.50 GB/s" ]] || f=1
  [[ "$(china_verdict_from_counts 0 0 2 9 6 0 3)" == "INCONCLUSIVE" ]] || f=1
  [[ "$(china_verdict_from_counts 0 2 0 9 2 4 3)" == "HIGH_RISK" ]] || f=1
  [[ ${#OOKLA_X86_64_SHA256} -eq 64 ]] || f=1
  [[ ${#OOKLA_I386_SHA256} -eq 64 ]] || f=1
  [[ ${#OOKLA_AARCH64_SHA256} -eq 64 ]] || f=1
  [[ ${#OOKLA_ARMHF_SHA256} -eq 64 ]] || f=1
  [[ ${#OOKLA_ARMEL_SHA256} -eq 64 ]] || f=1
  local old_demo="$DEMO"; DEMO=1
  : >"$NETWORK_TSV"
  speed_node 5396 'Suzhou, CN' >/dev/null
  speed_node 59387 'Ningbo, CN' >/dev/null
  [[ "$(count_speed 'Suzhou, CN|Ningbo, CN' FAIL)" == "2" ]] || f=1
  DEMO="$old_demo"
  if (( f )); then printf 'SELF_TEST=FAIL\n'; return 1; else printf 'SELF_TEST=PASS\n'; fi
}

if (( SELF_TEST )); then self_test; exit $?; fi

collect_system
print_system
print_io
print_network
china_assessment
rule
ELAPSED=$(( $(date +%s) - START_EPOCH ))
printf ' Finished in        : %s%s min %s sec%s\n' "$GREEN" "$((ELAPSED/60))" "$((ELAPSED%60))" "$RESET"
printf ' Timestamp          : %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
write_reports
printf ' Report saved       : %s%s%s\n' "$BLUE" "$REPORT_TXT" "$RESET"
[[ -f "${REPORT_JSON:-}" ]] && printf ' JSON report        : %s%s%s\n' "$BLUE" "$REPORT_JSON" "$RESET"
rule
