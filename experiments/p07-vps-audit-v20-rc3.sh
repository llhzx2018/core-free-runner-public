#!/usr/bin/env bash
set -uo pipefail

APP="P07 VPS 一键验机 2.0"
VERSION="2.0.0-rc3-zh"
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

SPEEDTEST_GO_VERSION="1.8.3"
SPEEDTEST_GO_X86_64_SHA256="c55caae22927cd719a2f8c0bef96ecf74b5fe8ca919ff9200d76328ae5de9477"
SPEEDTEST_GO_I386_SHA256="7b9641833a94c5937d9872f589e017c0fa5e3ef9c4a36a4d88f3b5c7355dc053"
SPEEDTEST_GO_ARM64_SHA256="48f51504548d76d5dc2ce7f72e713bd3b4e35554028b7131467060688754c657"
SPEEDTEST_GO_ARMV7_SHA256="29d6f7b1038d765970c4f0a24e2e26a80b2041f58a7ce3c2e1b4318317c0fbe0"
SPEEDTEST_GO_ARMV6_SHA256="395fd65509af7297b62d8942a323483b48c176cd9404889cc499870fe291d596"
SPEEDTEST_GO_ARMV5_SHA256="4b14cea63c7cf46cce348d8e221ee3f557c3449689e9ae6c6995613277dc6aa9"

LIBRESPEED_VERSION="1.0.14"
LIBRESPEED_386_SHA256="e2671230b8b6372df3a5910959dfea960915727b4db05f42856dc66dfb6132b2"
LIBRESPEED_AMD64_SHA256="89800767ac14085c78a20847ebea23340f6c14a78de0a15c2ac7db8b565c961f"
LIBRESPEED_ARM64_SHA256="75e51a2494d03cb35a92ddbf862b40571a25a1526f3cf3dfa8b1d5d7bc622bd9"
LIBRESPEED_ARMV5_SHA256="8de0df391623e0ae1dc15c58bd4db800de3bc2c71fd9e8eb9a395ff22e865b40"
LIBRESPEED_ARMV6_SHA256="2300a88101aab950842ca64ad61b9ba901f682d6c1e8de19af26f9442685caf4"
LIBRESPEED_ARMV7_SHA256="527591b4049136feeed73a00203f27362ce6aab7f11973c4985d1507ee469ec4"

while (($#)); do
  case "$1" in
    --demo) DEMO=1 ;;
    --self-test) SELF_TEST=1 ;;
    --version) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
    -h|--help)
      cat <<'EOF'
P07 VPS 一键验机
用法：
  p07-bench.sh              自动完成整台 VPS 验机
  p07-bench.sh --demo       显示无影响演示结果
  p07-bench.sh --self-test  运行内部自检
  p07-bench.sh --version    显示版本

可选环境变量：
  P07_BENCH_IO_MIB=256      每轮磁盘写入大小（共 3 轮）
  P07_BENCH_DIR=/var/tmp    磁盘测速使用的真实目录
EOF
      exit 0 ;;
    *) printf '未知参数：%s\n' "$1" >&2; exit 2 ;;
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
display_width(){
  local text="$1" w
  w="$(LC_ALL=C.UTF-8 printf '%s\n' "$text" | wc -L 2>/dev/null | tr -d '[:space:]')"
  [[ "$w" =~ ^[0-9]+$ ]] || w=${#text}
  printf '%s' "$w"
}
pad_cell(){
  local text="$1" width="$2" w pad
  w="$(display_width "$text")"
  pad=$(( width - w ))
  (( pad < 0 )) && pad=0
  printf '%s' "$text"
  printf '%*s' "$pad" ''
}
print_net_header(){
  printf '%s ' "$BOLD$YELLOW"
  pad_cell '节点/地区' 22; printf ' '
  pad_cell '上传' 15; printf ' '
  pad_cell '下载' 15; printf ' '
  pad_cell '延迟' 11; printf ' '
  pad_cell '状态' 8; printf ' '
  pad_cell '说明' 18
  printf '%s\n' "$RESET"
}
print_net_row(){
  local name="$1" up="$2" down="$3" lat="$4" state="$5" reason="$6"
  local shown_name shown_up shown_down shown_lat shown_state shown_reason state_color
  shown_name="$(zh_name "$name")"
  if [[ "$state" == PASS ]]; then
    shown_up="${up} Mbps"; shown_down="${down} Mbps"; shown_lat="${lat} ms"; shown_state='正常'
    case "$reason" in
      SUPPLEMENTAL) shown_reason='补充参考' ;;
      *) shown_reason='-' ;;
    esac
    state_color="$GREEN"
  else
    shown_up='-'; shown_down='-'; shown_lat='-'; shown_state="$(zh_state "$state")"; shown_reason="$(zh_reason "$reason")"
    state_color="$RED"
  fi
  printf ' '
  printf '%s' "$YELLOW"; pad_cell "$shown_name" 22; printf '%s ' "$RESET"
  printf '%s' "$GREEN"; pad_cell "$shown_up" 15; printf '%s ' "$RESET"
  printf '%s' "$RED"; pad_cell "$shown_down" 15; printf '%s ' "$RESET"
  printf '%s' "$BLUE"; pad_cell "$shown_lat" 11; printf '%s ' "$RESET"
  printf '%s' "$state_color"; pad_cell "$shown_state" 8; printf '%s ' "$RESET"
  pad_cell "$shown_reason" 18
  printf '\n'
}
zh_state(){
  case "$1" in
    PASS|NORMAL) printf '正常' ;;
    FAIL) printf '失败' ;;
    RISK) printf '有风险' ;;
    HIGH_RISK) printf '高风险' ;;
    PARTIAL) printf '部分有效' ;;
    INCONCLUSIVE) printf '证据不足' ;;
    UNKNOWN) printf '未知' ;;
    SKIPPED) printf '已跳过' ;;
    UNAVAILABLE) printf '不可用' ;;
    NOT_RUN) printf '未执行' ;;
    GOOD) printf '良好' ;;
    LOW) printf '较低' ;;
    LIMITED) printf '发现限额' ;;
    *) printf '%s' "$1" ;;
  esac
}
zh_reason(){
  case "$1" in
    NONE) printf '-' ;;
    TIMEOUT) printf '超时' ;;
    RATE_LIMITED) printf '测速平台限流' ;;
    BACKEND_UNAVAILABLE) printf '测速平台暂不可用' ;;
    BACKEND_FAILURE) printf '测速平台异常' ;;
    NODE_UNAVAILABLE) printf '测速节点不可用' ;;
    DNS_FAILURE) printf 'DNS 解析失败' ;;
    TLS_FAILURE) printf 'TLS 连接失败' ;;
    CONNECTION_FAILED) printf '连接失败' ;;
    PARSE_ERROR) printf '结果解析失败' ;;
    SPEEDTEST_UNAVAILABLE) printf 'Ookla 测速不可用' ;;
    TIMEOUT_COMMAND_MISSING) printf '系统缺少超时控制命令' ;;
    LIBRESPEED_FALLBACK) printf '全球备用测速' ;;
    SPEEDTESTGO_FALLBACK) printf '备用测速' ;;
    SPEEDTESTGO_UNAVAILABLE) printf '备用测速节点不可用' ;;
    LIBRESPEED_UNAVAILABLE) printf '备用测速节点不可用' ;;
    SUPPLEMENTAL) printf '补充基准' ;;
    *) printf '%s' "$1" ;;
  esac
}
zh_name(){
  case "$1" in
    'Speedtest.net') printf '自动测速节点' ;;
    'Los Angeles, US') printf '美国西部 洛杉矶' ;;
    'Dallas, US') printf '美国中部 达拉斯' ;;
    'Montreal, CA') printf '加拿大 蒙特利尔' ;;
    'Paris, FR') printf '欧洲 巴黎' ;;
    'Amsterdam, NL') printf '欧洲 阿姆斯特丹' ;;
    'China Unicom, CN') printf '中国联通' ;;
    'China Telecom, CN') printf '中国电信' ;;
    'China Backup, CN') printf '中国大陆备用' ;;
    'Hong Kong, CN'|'Hong Kong') printf '中国香港' ;;
    'Singapore, SG'|'Singapore') printf '新加坡' ;;
    'Kuala Lumpur') printf '马来西亚 吉隆坡' ;;
    'Bangkok') printf '泰国 曼谷' ;;
    'Taipei, CN') printf '台北' ;;
    'Tokyo, JP'|'Tokyo') printf '日本 东京' ;;
    'US West'|'美国西部') printf '美国西部' ;;
    'US Central'|'美国中部') printf '美国中部' ;;
    'US East'|'美国东部') printf '美国东部' ;;
    'Europe'|'欧洲') printf '欧洲' ;;
    'Asia South'|'亚洲南部') printf '亚洲南部' ;;
    'Cloudflare Edge') printf 'Cloudflare 边缘基准' ;;
    *) printf '%s' "$1" ;;
  esac
}
color_state(){
  local shown; shown="$(zh_state "$1")"
  case "$1" in
    PASS|NORMAL) printf '%s%s%s' "$GREEN" "$shown" "$RESET" ;;
    FAIL|HIGH_RISK) printf '%s%s%s' "$RED" "$shown" "$RESET" ;;
    *) printf '%s%s%s' "$YELLOW" "$shown" "$RESET" ;;
  esac
}

# One-shot mode never asks for stdin. Remove accidental terminal echo before each result row
# and drain pending keystrokes before returning to the parent shell.
tty_clean_line(){ [[ -t 1 ]] && printf '\r\033[2K' || true; }
drain_tty_input(){
  [[ -t 0 || -t 1 ]] || return 0
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
OOKLA_PROVIDER_STATE="NOT_RUN"
OOKLA_PROVIDER_REASON="NOT_RUN"
EVIDENCE_QUALITY="UNKNOWN"
MAINLAND_HTTP_PASS=0
MAINLAND_HTTP_FAIL=0
MAINLAND_HTTP_FAILED=""
SPEEDTEST_GO_BIN=""
LIBRESPEED_BIN=""
LIBRESPEED_SERVER_JSON="$TMP_DIR/librespeed-servers.json"
GLOBAL_FALLBACK_PROVIDER="NOT_RUN"
GLOBAL_FALLBACK_PASS=0

cleanup(){
  drain_tty_input
  if [[ $SPEEDTEST_TEMP -eq 1 && -n "$SPEEDTEST_BIN" ]]; then
    rm -rf "$(dirname "$SPEEDTEST_BIN")" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR" 2>/dev/null || true
}
trap cleanup EXIT
trap 'printf "\n%s测速已中断，正在清理临时文件……%s\n" "$RED" "$RESET"; exit 130' INT TERM

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
  printf '%s%s-------------------- P07 VPS 一键验机 2.0 --------------------%s\n' "$BOLD" "$BLUE" "$RESET"
  printf ' 版本               : %s%s%s\n' "$GREEN" "$VERSION" "$RESET"
  printf ' CPU 型号           : %s%s%s\n' "$BLUE" "${CPU:-未知}" "$RESET"
  printf ' CPU 核心           : %s%s%s @ %s\n' "$GREEN" "$CORES" "$RESET" "$FREQ"
  printf ' CPU 缓存           : %s\n' "${CACHE:-未知}"
  printf ' AES-NI             : %s\n' "$([[ "$AES" == Enabled ]] && printf '已启用' || printf '未启用')"
  printf ' 硬件虚拟化         : %s\n' "$([[ "$NESTED" == Enabled ]] && printf '已启用' || printf '未启用')"
  printf ' 磁盘总量           : %s%s%s  （已用 %s）\n' "$YELLOW" "$DISK_TOTAL" "$RESET" "$DISK_USED"
  printf ' 内存总量           : %s%s%s  （已用 %s）\n' "$YELLOW" "$RAM_TOTAL" "$RESET" "$RAM_USED"
  printf ' 交换分区           : %s  （已用 %s）\n' "$SWAP_TOTAL" "$SWAP_USED"
  printf ' 运行时间           : %s\n' "$(sed -e 's/weeks\?/周/g' -e 's/days\?/天/g' -e 's/hours\?/小时/g' -e 's/minutes\?/分钟/g' -e 's/seconds\?/秒/g' <<<"$UPTIME")"
  printf ' 系统负载           : %s\n' "$LOAD"
  printf ' 操作系统           : %s\n' "$OS"
  printf ' 系统架构           : %s（%s 位）\n' "$ARCH" "$BITS"
  printf ' 内核版本           : %s\n' "$KERNEL"
  printf ' TCP 拥塞控制       : %s%s%s\n' "$YELLOW" "$TCP" "$RESET"
  printf ' 虚拟化类型         : %s%s%s\n' "$BLUE" "$VIRT" "$RESET"
  if [[ "$CLOUDPANEL_STATE" == Installed ]]; then
    printf ' CloudPanel         : %s已安装%s · %s 个网站\n' "$GREEN" "$RESET" "$CLOUDPANEL_SITES"
  else
    printf ' CloudPanel         : %s未检测到%s\n' "$GRAY" "$RESET"
  fi
  if [[ "$IPV4" == OFFLINE || "$IPV4" == UNAVAILABLE ]]; then
    printf ' IPv4               : %s不可用%s\n' "$RED" "$RESET"
  else
    printf ' IPv4               : %s%s%s  （在线）\n' "$GREEN" "$IPV4" "$RESET"
  fi
  if [[ "$IPV6" == OFFLINE || "$IPV6" == UNAVAILABLE ]]; then
    printf ' IPv6               : %s不可用%s\n' "$RED" "$RESET"
  else
    printf ' IPv6               : %s%s%s  （在线）\n' "$GREEN" "$IPV6" "$RESET"
  fi
  printf ' 网络运营商/组织    : %s%s%s\n' "$BLUE" "$ORG" "$RESET"
  printf ' 机房位置           : %s / %s\n' "$CITY" "$COUNTRY"
  printf ' 地区               : %s%s%s\n' "$YELLOW" "$REGION" "$RESET"
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
  printf '%s%s 磁盘 I/O 测速%s  %s（3 轮 × %s MiB，目录：%s）%s\n' "$BOLD" "$MAGENTA" "$RESET" "$GRAY" "$IO_MIB" "$BENCH_DIR" "$RESET"
  IO_STATE="PASS"; IO_AVG_MB="0"; IO_RATES=()
  if ! [[ "$IO_MIB" =~ ^[0-9]+$ ]] || (( IO_MIB < 64 || IO_MIB > 1024 )); then
    IO_STATE="SKIPPED"; printf ' 磁盘测速           : 参数无效（P07_BENCH_IO_MIB 必须为 64-1024）\n'; return
  fi
  if (( ! DEMO )); then
    [[ -d "$BENCH_DIR" && -w "$BENCH_DIR" ]] || { IO_STATE="SKIPPED"; printf ' 磁盘测速           : 目录不可写，已跳过\n'; return; }
    local fs free_mib
    fs="$(df -PT "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $2}')"
    if [[ "$fs" == tmpfs || "$fs" == devtmpfs ]]; then
      IO_STATE="SKIPPED"; printf ' 磁盘测速           : %s 不是真实磁盘，已跳过\n' "$fs"; return
    fi
    free_mib="$(df -Pm "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $4}')"
    [[ "$free_mib" =~ ^[0-9]+$ ]] && (( free_mib >= IO_MIB + 256 )) || {
      IO_STATE="SKIPPED"; printf ' 磁盘测速           : 可用空间不足，已跳过\n'; return
    }
  fi

  local i raw mb sum=0
  for i in 1 2 3; do
    raw="$(run_dd_once "$BENCH_DIR/.p07-bench-$$-$i.dat" "$i" || true)"
    if [[ "$raw" == FAIL || -z "$raw" ]]; then
      IO_STATE="FAIL"; printf ' 第 %-2s 轮            : %s失败%s\n' "$i" "$RED" "$RESET"; continue
    fi
    mb="$(rate_to_mb "$raw")"
    IO_RATES+=("$mb")
    sum="$(awk -v a="$sum" -v b="$mb" 'BEGIN{printf "%.2f",a+b}')"
    printf ' 第 %-2s 轮            : %s%s%s\n' "$i" "$GREEN" "$(format_mb_rate "$mb")" "$RESET"
  done
  if ((${#IO_RATES[@]})); then
    IO_AVG_MB="$(awk -v s="$sum" -v n="${#IO_RATES[@]}" 'BEGIN{printf "%.2f",s/n}')"
    printf ' 三轮平均           : %s%s%s\n' "$GREEN" "$(format_mb_rate "$IO_AVG_MB")" "$RESET"
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
    printf '%s测速组件校验失败，网络测速已安全跳过。%s\n' "$RED" "$RESET"
    return 1
  }
  tar -xzf "$d/speedtest.tgz" -C "$d" speedtest >/dev/null 2>&1 || return 1
  chmod 0755 "$d/speedtest"
  SPEEDTEST_BIN="$d/speedtest"; SPEEDTEST_TEMP=1
}
network_reason(){
  local rc="$1" text="$2"
  if (( rc == 124 )); then printf TIMEOUT
  elif grep -qiE 'too many requests|rate.?limit|http[^0-9]*429|429' <<<"$text"; then printf RATE_LIMITED
  elif grep -qiE 'cannot retrieve.*configuration|failed to retrieve.*configuration|configurationerror|configuration.*failed|service unavailable|temporarily unavailable' <<<"$text"; then printf BACKEND_UNAVAILABLE
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
parse_speed_json_file(){
  local file="$1"
  command -v python3 >/dev/null 2>&1 || return 1
  python3 - "$file" <<'PYJSON' 2>/dev/null
import json,sys
from pathlib import Path
text=Path(sys.argv[1]).read_text(errors='replace').lstrip('\ufeff').strip()
if not text:
    raise SystemExit(1)
obj=None
for candidate in [text] + [x.strip() for x in reversed(text.splitlines()) if x.strip().startswith('{')]:
    try:
        obj=json.loads(candidate); break
    except Exception:
        pass
if obj is None:
    dec=json.JSONDecoder()
    for i,ch in enumerate(text):
        if ch!='{':
            continue
        try:
            obj,_=dec.raw_decode(text[i:]); break
        except Exception:
            pass
if obj is None:
    raise SystemExit(1)
try:
    up=float(obj['upload']['bandwidth'])*8/1e6
    down=float(obj['download']['bandwidth'])*8/1e6
    lat=float(obj['ping']['latency'])
except Exception:
    raise SystemExit(1)
print(f"{up:.2f}|{down:.2f}|{lat:.2f}")
PYJSON
}
speed_node(){
  local id="$1" name="$2" state reason up down lat raw rc parsed
  if (( DEMO )); then
    case "$name" in
      'Suzhou, CN'|'Ningbo, CN') state=FAIL; reason=TIMEOUT; up='-'; down='-'; lat='-' ;;
      'China Unicom 5G') state=FAIL; reason=NODE_UNAVAILABLE; up='-'; down='-'; lat='-' ;;
      'BJ Unicom') state=PASS; reason=NONE; up=820.4; down=910.2; lat=188.1 ;;
      'China Telecom JiangSu 5G') state=FAIL; reason=NODE_UNAVAILABLE; up='-'; down='-'; lat='-' ;;
      'Zhejiang Telecom') state=PASS; reason=NONE; up=760.2; down=845.8; lat=202.4 ;;
      'JSQY'|'Duke Kunshan University') state=PASS; reason=NONE; up=700.1; down=780.5; lat=210.0 ;;
      'Speedtest.net')
        if [[ -n "${P07_BENCH_DEMO_BACKEND_REASON:-}" ]]; then
          state=FAIL; reason="$P07_BENCH_DEMO_BACKEND_REASON"; up='-'; down='-'; lat='-'
        else
          state=PASS; reason=NONE; up=1180.2; down=1260.4; lat=1.1
        fi
        ;;
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
    local key out_file err_file
    key="${id:-auto}"
    out_file="$TMP_DIR/speed-${key}.out"; err_file="$TMP_DIR/speed-${key}.err"
    : >"$out_file"; : >"$err_file"
    if command -v python3 >/dev/null 2>&1; then
      timeout 65s "$SPEEDTEST_BIN" "${args[@]}" --format=json >"$out_file" 2>"$err_file"; rc=$?
      parsed=""
      if (( rc == 0 )); then
        parsed="$(parse_speed_json_file "$out_file" || true)"
        [[ -n "$parsed" ]] || parsed="$(parse_speed_json_file "$err_file" || true)"
      fi
    else
      timeout 65s "$SPEEDTEST_BIN" "${args[@]}" >"$out_file" 2>"$err_file"; rc=$?
      parsed=""
    fi
    raw="$(cat "$out_file" 2>/dev/null; cat "$err_file" 2>/dev/null)"
    [[ -n "$parsed" ]] || { (( rc == 0 )) && parsed="$(parse_speed_text "$raw" || true)"; }
    if [[ -n "$parsed" ]]; then
      IFS='|' read -r up down lat <<<"$parsed"; state=PASS; reason=NONE
    else
      state=FAIL; reason="$(network_reason "${rc:-1}" "$raw")"; up='-'; down='-'; lat='-'
    fi
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$name" "$state" "$reason" "$up" "$down" "$lat" >>"$NETWORK_TSV"
  tty_clean_line
  print_net_row "$name" "$up" "$down" "$lat" "$state" "$reason"
}
speed_node_retry(){
  local id="$1" name="$2" original="$NETWORK_TSV" tmp="$TMP_DIR/retry-$$-$RANDOM.tsv"
  local out="$TMP_DIR/retry-output-$$-$RANDOM.txt" output row state reason attempt
  for attempt in 1 2; do
    : >"$tmp"; : >"$out"
    NETWORK_TSV="$tmp"
    speed_node "$id" "$name" >"$out" || true
    NETWORK_TSV="$original"
    output="$(cat "$out" 2>/dev/null || true)"
    row="$(tail -n1 "$tmp" 2>/dev/null || true)"
    [[ -n "$row" ]] || continue
    state="$(awk -F '\t' 'END{print $3}' "$tmp")"
    reason="$(awk -F '\t' 'END{print $4}' "$tmp")"
    if [[ "$state" == PASS || ! "$reason" =~ ^(BACKEND_FAILURE|BACKEND_UNAVAILABLE|RATE_LIMITED|TIMEOUT|CONNECTION_FAILED)$ || "$attempt" == 2 ]]; then
      cat "$tmp" >>"$original"
      printf '%s\n' "$output"
      [[ "$state" == PASS ]]
      return
    fi
    (( DEMO )) || sleep 2
  done
  NETWORK_TSV="$original"
  [[ -s "$tmp" ]] && cat "$tmp" >>"$original"
  [[ -n "${output:-}" ]] && printf '%s\n' "$output"
  return 1
}
speed_node_pool(){
  local display="$1"; shift
  local original="$NETWORK_TSV" tmp="$TMP_DIR/pool-$$-$RANDOM.tsv"
  local out="$TMP_DIR/pool-output-$$-$RANDOM.txt" spec id label row state reason up down lat output best_reason=NODE_UNAVAILABLE best_id=0
  for spec in "$@"; do
    IFS='|' read -r id label <<<"$spec"
    : >"$tmp"; : >"$out"
    NETWORK_TSV="$tmp"
    speed_node "$id" "$label" >"$out" || true
    NETWORK_TSV="$original"
    output="$(cat "$out" 2>/dev/null || true)"
    row="$(tail -n1 "$tmp" 2>/dev/null || true)"
    [[ -n "$row" ]] || continue
    state="$(awk -F '\t' 'END{print $3}' "$tmp")"
    reason="$(awk -F '\t' 'END{print $4}' "$tmp")"
    up="$(awk -F '\t' 'END{print $5}' "$tmp")"
    down="$(awk -F '\t' 'END{print $6}' "$tmp")"
    lat="$(awk -F '\t' 'END{print $7}' "$tmp")"
    if [[ "$state" == PASS ]]; then
      printf '%s\t%s\tPASS\tNONE\t%s\t%s\t%s\n' "$id" "$display" "$up" "$down" "$lat" >>"$original"
      tty_clean_line
      print_net_row "$display" "$up" "$down" "$lat" PASS NONE
      return 0
    fi
    if [[ "$reason" != NODE_UNAVAILABLE ]]; then best_reason="$reason"; best_id="$id"; fi
  done
  NETWORK_TSV="$original"
  printf '%s\t%s\tFAIL\t%s\t-\t-\t-\n' "$best_id" "$display" "$best_reason" >>"$original"
  tty_clean_line
  print_net_row "$display" '-' '-' '-' FAIL "$best_reason"
  return 1
}
speedtestgo_arch(){
  local machine
  machine="$(uname -m 2>/dev/null || true)"
  case "$machine" in
    x86_64|amd64) printf 'x86_64|%s' "$SPEEDTEST_GO_X86_64_SHA256" ;;
    i386|i486|i586|i686) printf 'i386|%s' "$SPEEDTEST_GO_I386_SHA256" ;;
    aarch64|arm64|armv8|armv8l) printf 'arm64|%s' "$SPEEDTEST_GO_ARM64_SHA256" ;;
    armv7|armv7l) printf 'armv7|%s' "$SPEEDTEST_GO_ARMV7_SHA256" ;;
    armv6|armv6l) printf 'armv6|%s' "$SPEEDTEST_GO_ARMV6_SHA256" ;;
    armv5|armv5l) printf 'armv5|%s' "$SPEEDTEST_GO_ARMV5_SHA256" ;;
    *) return 1 ;;
  esac
}
prepare_speedtestgo(){
  if (( DEMO )); then SPEEDTEST_GO_BIN="DEMO"; return 0; fi
  command -v sha256sum >/dev/null 2>&1 || return 1
  command -v tar >/dev/null 2>&1 || return 1
  local pair pkg sha d url got bin
  pair="$(speedtestgo_arch 2>/dev/null || true)"
  [[ -n "$pair" ]] || return 1
  IFS='|' read -r pkg sha <<<"$pair"
  d="$TMP_DIR/speedtest-go"; mkdir -p "$d"
  url="https://github.com/showwin/speedtest-go/releases/download/v${SPEEDTEST_GO_VERSION}/speedtest-go_${SPEEDTEST_GO_VERSION}_Linux_${pkg}.tar.gz"
  fetch_to_file "$url" "$d/speedtest-go.tgz" || return 1
  got="$(sha256sum "$d/speedtest-go.tgz" | awk '{print $1}')"
  [[ "$got" == "$sha" ]] || {
    printf '%s备用测速组件校验失败，已安全跳过该提供者。%s\n' "$RED" "$RESET"
    return 1
  }
  tar -xzf "$d/speedtest-go.tgz" -C "$d" >/dev/null 2>&1 || return 1
  bin="$(find "$d" -maxdepth 2 -type f -name 'speedtest-go*' ! -name '*.tgz' | head -n1)"
  [[ -n "$bin" ]] || return 1
  chmod 0755 "$bin"
  SPEEDTEST_GO_BIN="$bin"
}
parse_speedtestgo_json_file(){
  local file="$1"
  command -v python3 >/dev/null 2>&1 || return 1
  python3 - "$file" <<'PYSTG' 2>/dev/null
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
servers=obj.get('servers') if isinstance(obj,dict) else None
if not servers:
    raise SystemExit(1)
srv=servers[0]
try:
    up=float(srv['ul_speed'])/125000.0
    down=float(srv['dl_speed'])/125000.0
    latency=float(srv['latency'])/1000000.0
except Exception:
    raise SystemExit(1)
if min(up,down,latency) < 0:
    raise SystemExit(1)
print(f"{up:.2f}|{down:.2f}|{latency:.2f}")
PYSTG
}
speedtestgo_region(){
  local display="$1" coords="$2" out err parsed rc up down lat
  if (( DEMO )); then
    case "$display" in
      'US West') up=810.2; down=930.4; lat=15.2 ;;
      'US East') up=720.8; down=860.1; lat=71.7 ;;
      'Europe') up=510.3; down=650.9; lat=142.4 ;;
      'Hong Kong') up=420.7; down=590.2; lat=164.8 ;;
      'Singapore') up=460.4; down=610.6; lat=171.2 ;;
      'Kuala Lumpur') up=430.8; down=570.5; lat=176.4 ;;
      'Jakarta') up=390.6; down=520.3; lat=188.7 ;;
      'Bangkok') up=410.2; down=545.8; lat=181.5 ;;
      'Tokyo') up=520.1; down=680.4; lat=108.6 ;;
      *) return 1 ;;
    esac
  else
    [[ -n "$SPEEDTEST_GO_BIN" ]] || return 1
    out="$TMP_DIR/stg-$(printf '%s' "$display" | tr ' ' '-').json"
    err="$out.err"; parsed="$out.parsed"
    : >"$out"; : >"$err"; : >"$parsed"
    set +e
    timeout 80s "$SPEEDTEST_GO_BIN" --json --saving-mode --thread 1 --location="$coords" --ping-mode http >"$out" 2>"$err"
    rc=$?
    set -e 2>/dev/null || true
    (( rc == 0 )) || return 1
    parse_speedtestgo_json_file "$out" >"$parsed" || return 1
    IFS='|' read -r up down lat <"$parsed"
  fi
  printf 'stg\t%s\tPASS\tSPEEDTESTGO_FALLBACK\t%s\t%s\t%s\n' "$display" "$up" "$down" "$lat" >>"$NETWORK_TSV"
  tty_clean_line
  print_net_row "$display" "$up" "$down" "$lat" PASS SPEEDTESTGO_FALLBACK
  return 0
}
speedtestgo_global_fallback(){
  if ! prepare_speedtestgo; then
    printf ' %s第一备用测速提供者暂不可用，继续尝试第二备用提供者。%s\n' "$YELLOW" "$RESET"
    return 1
  fi
  local pass=0
  speedtestgo_region 'US West'   '37.7749,-122.4194' && pass=$((pass+1)) || true
  speedtestgo_region 'US East'   '40.7128,-74.0060' && pass=$((pass+1)) || true
  speedtestgo_region 'Europe'    '50.1109,8.6821' && pass=$((pass+1)) || true
  speedtestgo_region 'Hong Kong' '22.3193,114.1694' && pass=$((pass+1)) || true
  speedtestgo_region 'Singapore'    '1.3521,103.8198' && pass=$((pass+1)) || true
  speedtestgo_region 'Kuala Lumpur' '3.1390,101.6869' && pass=$((pass+1)) || true
  speedtestgo_region 'Bangkok'      '13.7563,100.5018' && pass=$((pass+1)) || true
  speedtestgo_region 'Tokyo'        '35.6762,139.6503' && pass=$((pass+1)) || true
  GLOBAL_FALLBACK_PASS="$pass"
  GLOBAL_FALLBACK_PROVIDER="SPEEDTEST_GO"
  (( pass >= 5 ))
}
speedtestgo_sea_supplement(){
  prepare_speedtestgo || return 0
  speedtestgo_region 'Kuala Lumpur' '3.1390,101.6869' || true
  speedtestgo_region 'Bangkok' '13.7563,100.5018' || true
}

fallback_has_pass(){
  local pattern="$1"
  awk -F '\t' -v p="$pattern" '$2~p && $3=="PASS" && $4~/(SPEEDTESTGO_FALLBACK|LIBRESPEED_FALLBACK)/{ok=1} END{exit !ok}' "$NETWORK_TSV"
}
librespeed_fill_missing(){
  prepare_librespeed || return 1
  printf ' %s第二备用测速       : 正在补齐缺失地区%s\n' "$BLUE" "$RESET"
  fallback_has_pass '^US West$' || librespeed_region_pool 'US West' '91|Los Angeles Sharktech' '54|Los Angeles Clouvider' || true
  fallback_has_pass '^US East$' || librespeed_region_pool 'US East' '52|New York Clouvider' '78|Virginia Riverside' || true
  fallback_has_pass '^Europe$' || librespeed_region_pool 'Europe' '50|Frankfurt Clouvider' '94|Amsterdam Sharktech' '49|London Clouvider' || true
  if ! fallback_has_pass '^(Hong Kong|Singapore|Asia South)$'; then
    librespeed_region_pool 'Asia South' '68|Singapore' '75|Bangalore' || true
  fi
  fallback_has_pass '^Tokyo$' || librespeed_region_pool 'Tokyo' '82|Tokyo' || true
}
count_global_fallback_pass(){
  awk -F '\t' '$3=="PASS" && $4~/(SPEEDTESTGO_FALLBACK|LIBRESPEED_FALLBACK)/{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV"
}

librespeed_arch(){
  local machine
  machine="$(uname -m 2>/dev/null || true)"
  case "$machine" in
    x86_64|amd64) printf 'amd64|%s' "$LIBRESPEED_AMD64_SHA256" ;;
    i386|i486|i586|i686) printf '386|%s' "$LIBRESPEED_386_SHA256" ;;
    aarch64|arm64|armv8|armv8l) printf 'arm64|%s' "$LIBRESPEED_ARM64_SHA256" ;;
    armv7|armv7l) printf 'armv7|%s' "$LIBRESPEED_ARMV7_SHA256" ;;
    armv6|armv6l) printf 'armv6|%s' "$LIBRESPEED_ARMV6_SHA256" ;;
    armv5|armv5l) printf 'armv5|%s' "$LIBRESPEED_ARMV5_SHA256" ;;
    *) return 1 ;;
  esac
}
write_librespeed_server_json(){
  cat >"$LIBRESPEED_SERVER_JSON" <<'JSONLS'
[
  {"id":91,"name":"Los Angeles, USA","server":"https://laxspeed.sharktech.net","dlURL":"backend/garbage.php","ulURL":"backend/empty.php","pingURL":"backend/empty.php","getIpURL":"backend/getIP.php"},
  {"id":54,"name":"Los Angeles, USA (2)","server":"https://la.speedtest.clouvider.net/backend","dlURL":"garbage.php","ulURL":"empty.php","pingURL":"empty.php","getIpURL":"getIP.php"},
  {"id":93,"name":"Chicago, USA","server":"https://chispeed.sharktech.net","dlURL":"backend/garbage.php","ulURL":"backend/empty.php","pingURL":"backend/empty.php","getIpURL":"backend/getIP.php"},
  {"id":92,"name":"Denver, USA","server":"https://denspeed.sharktech.net","dlURL":"backend/garbage.php","ulURL":"backend/empty.php","pingURL":"backend/empty.php","getIpURL":"backend/getIP.php"},
  {"id":52,"name":"New York, USA","server":"https://nyc.speedtest.clouvider.net/backend","dlURL":"garbage.php","ulURL":"empty.php","pingURL":"empty.php","getIpURL":"getIP.php"},
  {"id":78,"name":"Virginia, USA","server":"https://speed.riverside.rocks/","dlURL":"garbage.php","ulURL":"empty.php","pingURL":"empty.php","getIpURL":"getIP.php"},
  {"id":50,"name":"Frankfurt, Germany","server":"https://fra.speedtest.clouvider.net/backend","dlURL":"garbage.php","ulURL":"empty.php","pingURL":"empty.php","getIpURL":"getIP.php"},
  {"id":94,"name":"Amsterdam, Netherlands","server":"https://amsspeed.sharktech.net","dlURL":"backend/garbage.php","ulURL":"backend/empty.php","pingURL":"backend/empty.php","getIpURL":"backend/getIP.php"},
  {"id":49,"name":"London, England","server":"https://lon.speedtest.clouvider.net/backend","dlURL":"garbage.php","ulURL":"empty.php","pingURL":"empty.php","getIpURL":"getIP.php"},
  {"id":68,"name":"Singapore","server":"https://speedtest.dsgroupmedia.com","dlURL":"backend/garbage.php","ulURL":"backend/empty.php","pingURL":"backend/empty.php","getIpURL":"backend/getIP.php"},
  {"id":75,"name":"Bangalore, India","server":"https://in1.backend.librespeed.org/","dlURL":"garbage.php","ulURL":"empty.php","pingURL":"empty.php","getIpURL":"getIP.php"},
  {"id":82,"name":"Tokyo, Japan","server":"https://librespeed.a573.net/","dlURL":"backend/garbage.php","ulURL":"backend/empty.php","pingURL":"backend/empty.php","getIpURL":"backend/getIP.php"}
]
JSONLS
}
prepare_librespeed(){
  if (( DEMO )); then LIBRESPEED_BIN="DEMO"; return 0; fi
  command -v sha256sum >/dev/null 2>&1 || return 1
  command -v tar >/dev/null 2>&1 || return 1
  local pair pkg sha url d got bin
  pair="$(librespeed_arch 2>/dev/null || true)"
  [[ -n "$pair" ]] || return 1
  IFS='|' read -r pkg sha <<<"$pair"
  d="$TMP_DIR/librespeed"; mkdir -p "$d"
  url="https://github.com/librespeed/speedtest-cli/releases/download/v${LIBRESPEED_VERSION}/librespeed-cli_${LIBRESPEED_VERSION}_linux_${pkg}.tar.gz"
  fetch_to_file "$url" "$d/librespeed.tgz" || return 1
  got="$(sha256sum "$d/librespeed.tgz" | awk '{print $1}')"
  [[ "$got" == "$sha" ]] || {
    printf '%s备用测速组件校验失败，全球备用测速已跳过。%s\n' "$RED" "$RESET"
    return 1
  }
  tar -xzf "$d/librespeed.tgz" -C "$d" >/dev/null 2>&1 || return 1
  bin="$(find "$d" -maxdepth 2 -type f -name 'librespeed-cli*' | head -n1)"
  [[ -n "$bin" ]] || return 1
  chmod 0755 "$bin"
  LIBRESPEED_BIN="$bin"
  write_librespeed_server_json
}
parse_librespeed_json_file(){
  local file="$1"
  command -v python3 >/dev/null 2>&1 || return 1
  python3 - "$file" <<'PYLS' 2>/dev/null
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
if isinstance(obj,list):
    if not obj: raise SystemExit(1)
    obj=obj[0]
try:
    up=float(obj['upload']); down=float(obj['download']); ping=float(obj['ping'])
except Exception:
    raise SystemExit(1)
if min(up,down,ping) < 0: raise SystemExit(1)
print(f"{up:.2f}|{down:.2f}|{ping:.2f}")
PYLS
}
librespeed_probe(){
  local id="$1" out="$2" parsed="$3" err="$4" rc
  : >"$out"; : >"$parsed"; : >"$err"
  set +e
  timeout 45s "$LIBRESPEED_BIN" --json --local-json "$LIBRESPEED_SERVER_JSON" --server "$id" --no-icmp --duration 2 --concurrent 2 --chunks 12 --upload-size 512 --timeout 10 --telemetry-level disabled >"$out" 2>"$err"
  rc=$?
  set -e 2>/dev/null || true
  (( rc == 0 )) || return 1
  parse_librespeed_json_file "$out" >"$parsed" || return 1
  [[ -s "$parsed" ]]
}
librespeed_region_pool(){
  local display="$1"; shift
  local spec id label work out parsed err up down lat
  if (( DEMO )); then
    case "$display" in
      'US West') up=780.2; down=910.4; lat=12.3 ;;
      'US Central') up=720.8; down=860.1; lat=42.7 ;;
      'US East') up=680.5; down=790.6; lat=71.8 ;;
      'Europe') up=510.2; down=650.9; lat=142.4 ;;
      'Asia South') up=460.7; down=590.2; lat=164.8 ;;
      'Tokyo') up=520.1; down=680.4; lat=108.6 ;;
      *) return 1 ;;
    esac
    printf 'ls-demo\t%s\tPASS\tLIBRESPEED_FALLBACK\t%s\t%s\t%s\n' "$display" "$up" "$down" "$lat" >>"$NETWORK_TSV"
    print_net_row "$display" "$up" "$down" "$lat" PASS LIBRESPEED_FALLBACK
    return 0
  fi
  for spec in "$@"; do
    IFS='|' read -r id label <<<"$spec"
    work="$TMP_DIR/ls-${id}"
    out="${work}.json"; parsed="${work}.parsed"; err="${work}.err"
    if librespeed_probe "$id" "$out" "$parsed" "$err"; then
      IFS='|' read -r up down lat <"$parsed"
      printf 'ls-%s\t%s\tPASS\tLIBRESPEED_FALLBACK\t%s\t%s\t%s\n' "$id" "$display" "$up" "$down" "$lat" >>"$NETWORK_TSV"
      tty_clean_line
      print_net_row "$display" "$up" "$down" "$lat" PASS LIBRESPEED_FALLBACK
      return 0
    fi
  done
  printf 'ls-none\t%s\tFAIL\tLIBRESPEED_UNAVAILABLE\t-\t-\t-\n' "$display" >>"$NETWORK_TSV"
  tty_clean_line
  # Supplementary fallback failures stay internal; only useful rows are shown.
  return 1
}
librespeed_global_fallback(){
  printf ' %s全球备用测速       : 正在使用多地区备用节点%s\n' "$BLUE" "$RESET"
  if ! prepare_librespeed; then
    GLOBAL_FALLBACK_PROVIDER="UNAVAILABLE"
    printf ' %s全球备用测速暂不可用。%s\n' "$YELLOW" "$RESET"
    return 1
  fi
  GLOBAL_FALLBACK_PROVIDER="LIBRESPEED"
  GLOBAL_FALLBACK_PASS=0
  librespeed_region_pool 'US West'    '91|Los Angeles Sharktech' '54|Los Angeles Clouvider' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  librespeed_region_pool 'US Central' '93|Chicago Sharktech' '92|Denver Sharktech' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  librespeed_region_pool 'US East'    '52|New York Clouvider' '78|Virginia Riverside' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  librespeed_region_pool 'Europe'     '50|Frankfurt Clouvider' '94|Amsterdam Sharktech' '49|London Clouvider' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  librespeed_region_pool 'Asia South' '68|Singapore' '75|Bangalore' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  librespeed_region_pool 'Tokyo'      '82|Tokyo' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  (( GLOBAL_FALLBACK_PASS >= 3 ))
}
cloudflare_fallback(){
  local down_url='https://speed.cloudflare.com/__down?bytes=50000000'
  local up_url='https://speed.cloudflare.com/__up'
  local dres ures d_speed d_ttfb d_code u_speed u_code up_file down_mbps up_mbps ttfb_ms
  if (( DEMO )); then
    print_net_row 'Cloudflare Edge' '850.0' '920.0' '24.0' PASS SUPPLEMENTAL
    printf 'cf-fallback	Cloudflare Edge	PASS	SUPPLEMENTAL	850.0	920.0	24.0
' >>"$NETWORK_TSV"
    return 0
  fi
  command -v curl >/dev/null 2>&1 || return 1
  dres="$(curl -fLsS --connect-timeout 5 --max-time 35 -o /dev/null -w '%{speed_download}|%{time_starttransfer}|%{http_code}' "$down_url" 2>/dev/null || true)"
  IFS='|' read -r d_speed d_ttfb d_code <<<"$dres"
  [[ "$d_code" == 200 && "$d_speed" =~ ^[0-9.]+$ ]] || return 1
  up_file="$TMP_DIR/cf-upload.bin"
  dd if=/dev/zero of="$up_file" bs=1M count=10 status=none 2>/dev/null || return 1
  ures="$(curl -fLsS --connect-timeout 5 --max-time 35 -X POST --data-binary @"$up_file" -o /dev/null -w '%{speed_upload}|%{http_code}' "$up_url" 2>/dev/null || true)"
  IFS='|' read -r u_speed u_code <<<"$ures"
  [[ "$u_code" =~ ^2[0-9][0-9]$ && "$u_speed" =~ ^[0-9.]+$ ]] || u_speed=0
  down_mbps="$(awk -v b="$d_speed" 'BEGIN{printf "%.1f",b*8/1000000}')"
  up_mbps="$(awk -v b="$u_speed" 'BEGIN{printf "%.1f",b*8/1000000}')"
  ttfb_ms="$(awk -v t="$d_ttfb" 'BEGIN{printf "%.1f",t*1000}')"
  printf 'cf-fallback\tCloudflare Edge\tPASS\tSUPPLEMENTAL\t%s\t%s\t%s\n' "$up_mbps" "$down_mbps" "$ttfb_ms" >>"$NETWORK_TSV"
  tty_clean_line
  print_net_row 'Cloudflare Edge' "$up_mbps" "$down_mbps" "$ttfb_ms" PASS SUPPLEMENTAL
  return 0
}
global_fallback_stack(){
  printf ' %s全球备用测速       : 正在自动选择可用的多地区测速节点%s\n' "$BLUE" "$RESET"
  if ! speedtestgo_global_fallback; then
    librespeed_fill_missing || librespeed_global_fallback || true
  fi
  GLOBAL_FALLBACK_PASS="$(count_global_fallback_pass)"
  if (( GLOBAL_FALLBACK_PASS < 5 )); then
    librespeed_fill_missing || true
    GLOBAL_FALLBACK_PASS="$(count_global_fallback_pass)"
  fi
  if (( GLOBAL_FALLBACK_PASS >= 5 )); then
    printf ' 全球备用覆盖       : %s%s 个地区正常%s\n' "$GREEN" "$GLOBAL_FALLBACK_PASS" "$RESET"
  else
    printf ' 全球备用覆盖       : %s仅 %s 个地区有效，结果仅供参考%s\n' "$YELLOW" "$GLOBAL_FALLBACK_PASS" "$RESET"
  fi
  printf ' %s补充基准           : Cloudflare 单边缘节点（仅作参考）%s\n' "$BLUE" "$RESET"
  cloudflare_fallback || printf ' %sCloudflare 补充基准暂不可用。%s\n' "$YELLOW" "$RESET"
}

print_network(){
  rule
  print_net_header
  : >"$NETWORK_TSV"
  if [[ "${P07_BENCH_FORCE_FALLBACK:-0}" == 1 ]]; then
    OOKLA_PROVIDER_STATE="UNAVAILABLE"
    OOKLA_PROVIDER_REASON="BACKEND_UNAVAILABLE"
    printf ' %s主测速平台已跳过，正在执行全球备用测速。%s
' "$YELLOW" "$RESET"
    global_fallback_stack
    return 0
  fi
  if ! prepare_speedtest; then
    SPEEDTEST_BIN=""
    OOKLA_PROVIDER_STATE="UNAVAILABLE"
    OOKLA_PROVIDER_REASON="SPEEDTEST_UNAVAILABLE"
    speed_node '' 'Speedtest.net' || true
    printf ' %sOokla 测速平台当前不可用，已自动切换全球备用测速。%s\n' "$YELLOW" "$RESET"
    global_fallback_stack
    return 0
  fi

  speed_node_retry '' 'Speedtest.net' || true
  local pre_state pre_reason
  pre_state="$(awk -F '\t' '$2=="Speedtest.net"{s=$3} END{print s}' "$NETWORK_TSV")"
  pre_reason="$(awk -F '\t' '$2=="Speedtest.net"{r=$4} END{print r}' "$NETWORK_TSV")"
  OOKLA_PROVIDER_STATE="$pre_state"
  OOKLA_PROVIDER_REASON="${pre_reason:-UNKNOWN}"
  if [[ "$pre_state" != PASS && "$pre_reason" =~ ^(RATE_LIMITED|BACKEND_UNAVAILABLE|BACKEND_FAILURE)$ ]]; then
    printf ' %sOokla 预检未通过：%s。已自动切换全球备用测速。%s\n' "$YELLOW" "$(zh_reason "$pre_reason")" "$RESET"
    global_fallback_stack
    return 0
  fi

  speed_node_retry 7190    'Los Angeles, US' || true
  speed_node_retry 22288   'Dallas, US' || true
  speed_node_retry 64420   'Montreal, CA' || true
  speed_node_retry 61933   'Paris, FR' || true
  speed_node_retry 41423   'Amsterdam, NL' || true
  speed_node_retry 32155   'Hong Kong, CN' || true
  speed_node_retry 13623   'Singapore, SG' || true
  speedtestgo_sea_supplement
  speed_node_retry 65092   'Taipei, CN' || true
  speed_node_retry 48463   'Tokyo, JP' || true
}

http_probe(){
  local url="$1"
  if (( DEMO )); then
    if [[ -n "${P07_BENCH_DEMO_MAINLAND_FAIL_HOST:-}" && "$url" == *"$P07_BENCH_DEMO_MAINLAND_FAIL_HOST"* ]]; then
      return 1
    fi
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
  local measured_pass sea_pass overall
  measured_pass="$(awk -F '	' '$3=="PASS" && $2!="Cloudflare Edge"{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  sea_pass="$(awk -F '	' '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Jakarta|Bangkok)/{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  CHINA_VERDICT="UNKNOWN"
  EVIDENCE_QUALITY="LOW"
  MAINLAND_HTTP_PASS=0
  MAINLAND_HTTP_FAIL=0
  MAINLAND_HTTP_FAILED=""
  if [[ "$IO_STATE" == PASS && "$measured_pass" -ge 5 && "$sea_pass" -ge 2 ]]; then
    overall=PASS
    CHINA_RECOMMENDATION="服务器基础性能与国际/东南亚网络表现可用；中国大陆直连必须用大陆入口探针单独验证"
  elif [[ "$measured_pass" -ge 3 ]]; then
    overall=PARTIAL
    CHINA_RECOMMENDATION="基础网络有有效结果，但覆盖不足；中国大陆直连仍需大陆入口探针"
  else
    overall=RISK
    CHINA_RECOMMENDATION="有效测速地区过少，建议先排查网络再迁移"
  fi

  rule
  printf '%s%s 验机结论%s
' "$BOLD" "$BLUE" "$RESET"
  printf ' 基础验机结果       : '; color_state "$overall"; printf '
'
  printf ' 全球有效测速       : %s 个地区
' "$measured_pass"
  printf ' 东南亚有效测速     : %s 个地区
' "$sea_pass"
  printf ' 中国大陆直连       : %s未直接检测%s
' "$YELLOW" "$RESET"
  printf ' 说明               : 当前 VPS→外部 的测速不能代表中国大陆用户→VPS 的真实访问
'
  printf ' 建议               : %s%s%s
' "$YELLOW" "$CHINA_RECOMMENDATION" "$RESET"
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
    python3 - "$REPORT_JSON" "$VERSION" "$OS" "$CPU" "$CORES" "$RAM_TOTAL" "$DISK_TOTAL" "$DISK_USED" "$DISK_SCOPE" "$IPV4" "$ORG" "$CITY" "$COUNTRY" "$IO_STATE" "$IO_AVG_MB" "$CHINA_VERDICT" "$CHINA_RECOMMENDATION" "$elapsed" "$NETWORK_TSV" "$OOKLA_PROVIDER_STATE" "$OOKLA_PROVIDER_REASON" "$EVIDENCE_QUALITY" "$MAINLAND_HTTP_PASS" "$MAINLAND_HTTP_FAIL" "$MAINLAND_HTTP_FAILED" <<'PY' 2>/dev/null || true
import json,sys,datetime
(path,version,osname,cpu,cores,ram,disk,disk_used,disk_scope,ipv4,org,city,country,io_state,io_avg,verdict,reco,elapsed,tsv,provider_state,provider_reason,evidence_quality,mainland_pass,mainland_fail,mainland_failed)=sys.argv[1:]
nodes=[]
try:
    for line in open(tsv,encoding='utf-8'):
        sid,name,state,reason,up,down,lat=line.rstrip('\n').split('\t')
        nodes.append({'server_id':sid,'name':name,'state':state,'reason':reason,'upload_mbps':up,'download_mbps':down,'latency_ms':lat})
except Exception:
    pass
payload={
  'schema_version':3,'module':'p07-bench','version':version,
  'timestamp':datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
  'system':{'os':osname,'cpu':cpu,'cores':cores,'ram':ram,'total_disk':disk,'disk_used':disk_used,'disk_scope':disk_scope,'ipv4':ipv4,'organization':org,'city':city,'country':country},
  'io':{'state':io_state,'average_mb_s':io_avg},
  'network_nodes':nodes,
  'china_ip_assessment':{'verdict':verdict,'recommendation':reco,'evidence_scope':'VPS_OUTBOUND_ONLY','mainland_origin_probe':'NOT_IMPLEMENTED','evidence_quality':evidence_quality,'ookla_provider':{'state':provider_state,'reason':provider_reason},'mainland_https':{'pass':int(mainland_pass),'fail':int(mainland_fail),'failed_hosts':[x for x in mainland_failed.split(',') if x]}},
  'elapsed_seconds':int(elapsed)
}
with open(path,'w',encoding='utf-8') as f:
    json.dump(payload,f,ensure_ascii=False,indent=2)
PY
  fi
}

# ===== P07 VPS Audit 2.0 =====
V20_CPU_STEAL="UNKNOWN"
V20_CPU_QUOTA="UNKNOWN"
V20_CPU_QUOTA_STATE="UNKNOWN"
V20_CPU_SINGLE="UNKNOWN"
V20_CPU_MULTI="UNKNOWN"
V20_CPU_BENCH_STATE="NOT_RUN"
V20_CPU_LOAD_STEAL="UNKNOWN"
V20_CPU_SCALE_EFF="UNKNOWN"
V20_CGROUP_BASE="UNKNOWN"
V20_MEM_LIMIT="UNKNOWN"
V20_SWAP_LIMIT="UNKNOWN"
V20_PIDS_LIMIT="UNKNOWN"
V20_GLOBAL_MEDIAN_UP="UNKNOWN"
V20_GLOBAL_MEDIAN_DOWN="UNKNOWN"
V20_SEA_MEDIAN_UP="UNKNOWN"
V20_SEA_MEDIAN_DOWN="UNKNOWN"
V20_SLOW_REGION_COUNT=0
V20_ASYMMETRY_COUNT=0
V20_DISK_IOPS="UNKNOWN"
V20_FSYNC_AVG="UNKNOWN"
V20_FSYNC_P95="UNKNOWN"
V20_PING_STATE="NOT_RUN"
V20_PING_LOSS="UNKNOWN"
V20_PING_JITTER="UNKNOWN"
V20_HTTPS_PASS=0
V20_HTTPS_TOTAL=0
V20_HTTPS_JITTER="UNKNOWN"
V20_DNS_PASS=0
V20_DNS_TOTAL=0
V20_IP_HEALTH="UNKNOWN"
V20_RESOURCE_STATE="UNKNOWN"
CHINA_VERDICT="UNKNOWN"
CHINA_RECOMMENDATION="VPS 验机 2.0 请读取 vps_audit_v20.verdict"
EVIDENCE_QUALITY="V20"
MAINLAND_HTTP_PASS=0
MAINLAND_HTTP_FAIL=0
MAINLAND_HTTP_FAILED=""
V20_SCORE=0
V20_COMPLETENESS=0
V20_GRADE="UNKNOWN"
V20_ADVICE="UNKNOWN"
V20_ISSUES=""

v20_add_issue(){
  local x="$1"
  [[ -n "$x" ]] || return 0
  if [[ -n "$V20_ISSUES" ]]; then V20_ISSUES+="；$x"; else V20_ISSUES="$x"; fi
}

v20_cpu_steal(){
  if (( DEMO )); then printf '0.30'; return; fi
  [[ -r /proc/stat ]] || { printf 'UNKNOWN'; return; }
  local a b t1 t2 s1 s2
  a="$(awk '/^cpu /{for(i=2;i<=NF;i++)t+=$i; print t"|"$9; exit}' /proc/stat 2>/dev/null)"
  sleep 2
  b="$(awk '/^cpu /{for(i=2;i<=NF;i++)t+=$i; print t"|"$9; exit}' /proc/stat 2>/dev/null)"
  IFS='|' read -r t1 s1 <<<"$a"; IFS='|' read -r t2 s2 <<<"$b"
  if [[ "$t1" =~ ^[0-9]+$ && "$t2" =~ ^[0-9]+$ && "$s1" =~ ^[0-9]+$ && "$s2" =~ ^[0-9]+$ ]] && (( t2 > t1 )); then
    awk -v ds="$((s2-s1))" -v dt="$((t2-t1))" 'BEGIN{printf "%.2f",100*ds/dt}'
  else printf 'UNKNOWN'; fi
}

v20_cgroup2_base(){
  local rel base
  rel="$(awk -F: '$1=="0"{print $3; exit}' /proc/self/cgroup 2>/dev/null)"
  [[ -n "$rel" ]] || rel='/'
  base="/sys/fs/cgroup${rel%/}"
  if [[ -d "$base" ]]; then printf '%s' "$base"; return; fi
  [[ -d /sys/fs/cgroup ]] && printf '/sys/fs/cgroup' || printf 'UNKNOWN'
}

v20_human_limit(){
  local x="$1"
  if [[ "$x" == max || "$x" == '-1' ]]; then printf '无限制';
  elif [[ "$x" =~ ^[0-9]+$ ]]; then awk -v x="$x" 'BEGIN{if(x>=1073741824)printf "%.2f GiB",x/1073741824; else if(x>=1048576)printf "%.1f MiB",x/1048576; else printf "%s B",x}'
  else printf '未知'; fi
}

v20_read_resource_limits(){
  local base raw
  base="$(v20_cgroup2_base)"; V20_CGROUP_BASE="$base"
  if [[ "$base" != UNKNOWN && -r "$base/memory.max" ]]; then raw="$(cat "$base/memory.max" 2>/dev/null)"; V20_MEM_LIMIT="$(v20_human_limit "$raw")"; else V20_MEM_LIMIT=UNKNOWN; fi
  if [[ "$base" != UNKNOWN && -r "$base/memory.swap.max" ]]; then raw="$(cat "$base/memory.swap.max" 2>/dev/null)"; V20_SWAP_LIMIT="$(v20_human_limit "$raw")"; else V20_SWAP_LIMIT=UNKNOWN; fi
  if [[ "$base" != UNKNOWN && -r "$base/pids.max" ]]; then raw="$(cat "$base/pids.max" 2>/dev/null)"; [[ "$raw" == max ]] && V20_PIDS_LIMIT='无限制' || V20_PIDS_LIMIT="${raw:-UNKNOWN}"; else V20_PIDS_LIMIT=UNKNOWN; fi
}

v20_cpu_quota(){
  if (( DEMO )); then printf '%s 核|%s' "$CORES" NORMAL; return; fi
  local quota period cores state=NORMAL base rel
  base="$(v20_cgroup2_base)"
  if [[ "$base" != UNKNOWN && -r "$base/cpu.max" ]]; then
    read -r quota period <"$base/cpu.max" || true
    if [[ "$quota" == max || -z "$quota" ]]; then printf '无限制|NORMAL'; return; fi
  elif [[ -r /sys/fs/cgroup/cpu.max ]]; then
    read -r quota period </sys/fs/cgroup/cpu.max || true
    if [[ "$quota" == max || -z "$quota" ]]; then printf '无限制|NORMAL'; return; fi
  elif [[ -r /sys/fs/cgroup/cpu/cpu.cfs_quota_us && -r /sys/fs/cgroup/cpu/cpu.cfs_period_us ]]; then
    quota="$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null)"; period="$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null)"
    if [[ "$quota" == -1 ]]; then printf '无限制|NORMAL'; return; fi
  else printf '未知|UNKNOWN'; return; fi
  if [[ "$quota" =~ ^[0-9]+$ && "$period" =~ ^[0-9]+$ && "$period" -gt 0 ]]; then
    cores="$(awk -v q="$quota" -v p="$period" 'BEGIN{printf "%.2f",q/p}')"
    if awk -v q="$cores" -v c="${CORES:-1}" 'BEGIN{exit !(q+0.01<c*0.90)}'; then state=LIMITED; fi
    printf '%s 核|%s' "$cores" "$state"
  else printf '未知|UNKNOWN'; fi
}

v20_parse_sha_mb(){
  awk '$1=="sha256"{x=$NF; sub(/k$/,"",x); if(x~/^[0-9.]+$/)v=x/1000} END{if(v>0)printf "%.1f",v}'
}

v20_cpu_stat_pair(){
  awk '/^cpu /{for(i=2;i<=NF;i++)t+=$i; print t"|"$9; exit}' /proc/stat 2>/dev/null
}

v20_cpu_bench(){
  local workers single out i f val total before after t1 st1 t2 st2 loadsteal=UNKNOWN
  if (( DEMO )); then printf 'PASS|780.0|2800.0|0.40'; return; fi
  command -v openssl >/dev/null 2>&1 || { printf 'MISSING|UNKNOWN|UNKNOWN|UNKNOWN'; return; }

  # OpenSSL speed visits six block sizes. One-second mode needs about six seconds,
  # so allow enough wall time for the summary line instead of killing it early.
  out="$(timeout 10s openssl speed -seconds 1 -evp sha256 2>&1 || true)"
  single="$(v20_parse_sha_mb <<<"$out")"
  [[ "$single" =~ ^[0-9.]+$ ]] || { printf 'PARSE_ERROR|UNKNOWN|UNKNOWN|UNKNOWN'; return; }

  workers="${CORES:-1}"; [[ "$workers" =~ ^[0-9]+$ ]] || workers=1
  (( workers>4 )) && workers=4; (( workers<1 )) && workers=1
  before="$(v20_cpu_stat_pair)"
  for ((i=1;i<=workers;i++)); do
    f="$TMP_DIR/cpu-worker-$i.txt"
    timeout 10s openssl speed -seconds 1 -evp sha256 >"$f" 2>&1 &
  done
  wait || true
  after="$(v20_cpu_stat_pair)"
  total=0
  for ((i=1;i<=workers;i++)); do
    val="$(v20_parse_sha_mb <"$TMP_DIR/cpu-worker-$i.txt")"
    [[ "$val" =~ ^[0-9.]+$ ]] || { printf 'PARSE_ERROR|%s|UNKNOWN|UNKNOWN' "$single"; return; }
    total="$(awk -v a="$total" -v b="$val" 'BEGIN{printf "%.1f",a+b}')"
  done
  if [[ "$before" == *'|'* && "$after" == *'|'* ]]; then
    IFS='|' read -r t1 st1 <<<"$before"; IFS='|' read -r t2 st2 <<<"$after"
    if [[ "$t1" =~ ^[0-9]+$ && "$t2" =~ ^[0-9]+$ && "$st1" =~ ^[0-9]+$ && "$st2" =~ ^[0-9]+$ ]] && (( t2>t1 )); then
      loadsteal="$(awk -v ds="$((st2-st1))" -v dt="$((t2-t1))" 'BEGIN{printf "%.2f",100*ds/dt}')"
    fi
  fi
  printf 'PASS|%s|%s|%s' "$single" "$total" "$loadsteal"
}

v20_cpu_test(){
  rule
  printf '%s%s CPU 真实表现%s
' "$BOLD" "$MAGENTA" "$RESET"
  V20_CPU_STEAL="$(v20_cpu_steal)"
  IFS='|' read -r V20_CPU_QUOTA V20_CPU_QUOTA_STATE <<<"$(v20_cpu_quota)"
  IFS='|' read -r V20_CPU_BENCH_STATE V20_CPU_SINGLE V20_CPU_MULTI V20_CPU_LOAD_STEAL <<<"$(v20_cpu_bench)"
  if [[ "$V20_CPU_BENCH_STATE" == PASS && "$V20_CPU_SINGLE" =~ ^[0-9.]+$ && "$V20_CPU_MULTI" =~ ^[0-9.]+$ ]]; then local w="${CORES:-1}"; [[ "$w" =~ ^[0-9]+$ ]] || w=1; ((w>4))&&w=4; ((w<1))&&w=1; V20_CPU_SCALE_EFF="$(awk -v m="$V20_CPU_MULTI" -v s="$V20_CPU_SINGLE" -v w="$w" 'BEGIN{if(s>0&&w>0){x=100*m/(s*w); if(x>120)x=120; printf "%.1f",x}else print "UNKNOWN"}')"; fi
  printf ' CPU Steal（空载）  : %s%%  （宿主机争抢信号，越低越好）
' "$V20_CPU_STEAL"
  if [[ "$V20_CPU_LOAD_STEAL" =~ ^[0-9.]+$ ]]; then printf ' CPU Steal（负载）  : %s%%
' "$V20_CPU_LOAD_STEAL"; fi
  if [[ "$V20_CPU_QUOTA_STATE" == LIMITED ]]; then
    printf ' CPU 有效配额       : %s%s%s  （低于系统可见 %s 核）
' "$RED" "$V20_CPU_QUOTA" "$RESET" "$CORES"
  else
    printf ' CPU 有效配额       : %s
' "$V20_CPU_QUOTA"
  fi
  case "$V20_CPU_BENCH_STATE" in
    PASS)
      printf ' SHA256 单核        : %s MB/s
' "$V20_CPU_SINGLE"
      printf ' SHA256 多核        : %s MB/s  （最多使用 4 核）
' "$V20_CPU_MULTI"
      printf ' 多核扩展效率       : %s%%
' "$V20_CPU_SCALE_EFF"
      ;;
    MISSING) printf ' CPU 轻量跑分       : 未执行（系统没有 OpenSSL）
' ;;
    PARSE_ERROR) printf ' CPU 轻量跑分       : 已执行，但结果解析失败（不据此扣分）
' ;;
    *) printf ' CPU 轻量跑分       : 未执行
' ;;
  esac
}

v20_disk_sync_probe(){
  local file="$BENCH_DIR/.p07-v20-disk-$$.bin"
  if (( DEMO )); then printf '820|1.20|2.80'; return; fi
  command -v python3 >/dev/null 2>&1 || { printf 'UNKNOWN|UNKNOWN|UNKNOWN'; return; }
  python3 - "$file" <<'PYV20DISK' 2>/dev/null || printf 'UNKNOWN|UNKNOWN|UNKNOWN'
import os,sys,time,random,statistics
p=sys.argv[1]
try:
    fd=os.open(p,os.O_CREAT|os.O_RDWR|os.O_TRUNC,0o600)
    size=16*1024*1024
    os.ftruncate(fd,size)
    buf=b'0'*4096
    n=128
    start=time.perf_counter()
    for _ in range(n):
        off=random.randrange(0,size//4096)*4096
        os.pwrite(fd,buf,off)
        os.fdatasync(fd)
    elapsed=time.perf_counter()-start
    iops=n/elapsed if elapsed>0 else 0
    samples=[]
    for _ in range(40):
        off=random.randrange(0,size//4096)*4096
        t=time.perf_counter(); os.pwrite(fd,buf,off); os.fsync(fd); samples.append((time.perf_counter()-t)*1000)
    os.close(fd); os.unlink(p)
    s=sorted(samples); p95=s[max(0,min(len(s)-1,int(len(s)*0.95)-1))]
    print(f'{iops:.0f}|{statistics.mean(samples):.2f}|{p95:.2f}')
except Exception:
    try: os.close(fd)
    except Exception: pass
    try: os.unlink(p)
    except Exception: pass
    raise
PYV20DISK
}

v20_disk_test(){
  printf '%s%s 磁盘数据库型负载%s\n' "$BOLD" "$MAGENTA" "$RESET"
  if (( ! DEMO )); then
    [[ -d "$BENCH_DIR" && -w "$BENCH_DIR" ]] || { printf ' 4K / fsync         : 目录不可写，已跳过\n'; return; }
    local fs; fs="$(df -PT "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $2}')"
    [[ "$fs" != tmpfs && "$fs" != devtmpfs ]] || { printf ' 4K / fsync         : 内存文件系统，已跳过\n'; return; }
  fi
  IFS='|' read -r V20_DISK_IOPS V20_FSYNC_AVG V20_FSYNC_P95 <<<"$(v20_disk_sync_probe)"
  if [[ "$V20_DISK_IOPS" != UNKNOWN ]]; then
    printf ' 4K 同步写 IOPS     : %s\n' "$V20_DISK_IOPS"
    printf ' fsync 平均延迟     : %s ms\n' "$V20_FSYNC_AVG"
    printf ' fsync P95 延迟     : %s ms\n' "$V20_FSYNC_P95"
  else
    printf ' 4K / fsync         : 未执行（缺少 Python3 或文件系统不支持）\n'
  fi
}

v20_ping_target(){
  local target="$1" out loss jitter
  out="$(ping -n -c 10 -i 0.2 -W 1 "$target" 2>/dev/null || true)"
  loss="$(grep -oE '[0-9.]+% packet loss' <<<"$out" | tail -n1 | awk '{print $1}' | tr -d '%')"
  jitter="$(awk -F'=' '/(rtt|round-trip).*min\/avg\/max\/(mdev|stddev)/{gsub(/ ms/,"",$2); split($2,a,"/"); gsub(/ /,"",a[4]); print a[4]}' <<<"$out" | tail -n1)"
  [[ "$loss" =~ ^[0-9.]+$ ]] || return 1
  [[ "$jitter" =~ ^[0-9.]+$ ]] || jitter=UNKNOWN
  printf '%s|%s' "$loss" "$jitter"
}

v20_ping_stability(){
  if (( DEMO )); then printf 'PASS|0.0|0.45|3'; return; fi
  command -v ping >/dev/null 2>&1 || { printf 'NOT_RUN|UNKNOWN|UNKNOWN|0'; return; }
  local t r loss jit ok=0 worst=0 maxjit=0 all100=1
  for t in 1.1.1.1 8.8.8.8 9.9.9.9; do
    r="$(v20_ping_target "$t" || true)"; [[ -n "$r" ]] || continue
    IFS='|' read -r loss jit <<<"$r"; ok=$((ok+1))
    worst="$(awk -v a="$worst" -v b="$loss" 'BEGIN{print (b>a)?b:a}')"
    if awk -v x="$loss" 'BEGIN{exit !(x<100)}'; then all100=0; fi
    if [[ "$jit" =~ ^[0-9.]+$ ]]; then maxjit="$(awk -v a="$maxjit" -v b="$jit" 'BEGIN{print (b>a)?b:a}')"; fi
  done
  if (( ok==0 )); then printf 'NOT_RUN|UNKNOWN|UNKNOWN|0'
  elif (( all100==1 )); then printf 'ICMP_BLOCKED|UNKNOWN|UNKNOWN|%s' "$ok"
  else printf 'PASS|%s|%s|%s' "$worst" "$maxjit" "$ok"; fi
}

v20_https_stability(){
  if (( DEMO )); then printf '15|15|8.40'; return; fi
  command -v curl >/dev/null 2>&1 || { printf '0|0|UNKNOWN'; return; }
  local url i result code t tmp="$TMP_DIR/v20-https.tsv"
  : >"$tmp"
  for url in 'https://www.cloudflare.com/cdn-cgi/trace' 'https://github.com/' 'https://www.google.com/generate_204'; do
    for i in 1 2 3 4 5; do
      result="$(curl -LsS -o /dev/null --connect-timeout 4 --max-time 8 -w '%{http_code}|%{time_starttransfer}' "$url" 2>/dev/null || true)"
      IFS='|' read -r code t <<<"$result"
      if [[ "$code" =~ ^[23][0-9][0-9]$ && "$t" =~ ^[0-9.]+$ ]]; then printf '1\t%s\n' "$t" >>"$tmp"; else printf '0\t0\n' >>"$tmp"; fi
    done
  done
  awk -F '\t' '{n++; if($1==1){p++; x=$2*1000; s+=x; ss+=x*x}} END{if(p>1){m=s/p; v=ss/p-m*m; if(v<0)v=0; j=sqrt(v); printf "%d|%d|%.2f",p,n,j}else printf "%d|%d|UNKNOWN",p,n}' "$tmp"
}

v20_network_stability(){
  rule
  printf '%s%s 网络稳定性%s
' "$BOLD" "$MAGENTA" "$RESET"
  local ping_ok
  IFS='|' read -r V20_PING_STATE V20_PING_LOSS V20_PING_JITTER ping_ok <<<"$(v20_ping_stability)"
  IFS='|' read -r V20_HTTPS_PASS V20_HTTPS_TOTAL V20_HTTPS_JITTER <<<"$(v20_https_stability)"
  case "$V20_PING_STATE" in
    PASS)
      printf ' ICMP 丢包（最差）  : %s%%  （%s/3 个探针有效）
' "$V20_PING_LOSS" "$ping_ok"
      printf ' ICMP 抖动（最差）  : %s ms
' "$V20_PING_JITTER"
      ;;
    ICMP_BLOCKED)
      printf ' ICMP 丢包/抖动     : 受限（%s/3 目标均不响应，不作为线路丢包证据）
' "$ping_ok"
      ;;
    *) printf ' ICMP 丢包/抖动     : 未执行（不据此判坏）
' ;;
  esac
  printf ' HTTPS 稳定性       : %s/%s 成功
' "$V20_HTTPS_PASS" "$V20_HTTPS_TOTAL"
  printf ' HTTPS 响应抖动     : %s ms
' "$V20_HTTPS_JITTER"
}

v20_dns_health(){
  if (( DEMO )); then printf '4|4'; return; fi
  local h ok=0 total=0
  for h in github.com cloudflare.com google.com baidu.com; do
    total=$((total+1))
    if command -v getent >/dev/null 2>&1 && getent ahosts "$h" >/dev/null 2>&1; then ok=$((ok+1));
    elif command -v nslookup >/dev/null 2>&1 && nslookup "$h" >/dev/null 2>&1; then ok=$((ok+1)); fi
  done
  printf '%s|%s' "$ok" "$total"
}

v20_ip_test(){
  rule
  printf '%s%s IP 与基础可达性%s\n' "$BOLD" "$MAGENTA" "$RESET"
  IFS='|' read -r V20_DNS_PASS V20_DNS_TOTAL <<<"$(v20_dns_health)"
  printf ' DNS 解析           : %s/%s 正常\n' "$V20_DNS_PASS" "$V20_DNS_TOTAL"
  printf ' HTTPS 基础连通     : %s/%s 正常\n' "$V20_HTTPS_PASS" "$V20_HTTPS_TOTAL"
  printf ' ASN / 运营商       : %s\n' "${ORG:-未知}"
  if [[ "$IPV4" != OFFLINE && "$ORG" != UNKNOWN && "$V20_DNS_PASS" -ge 3 && "$V20_HTTPS_PASS" -ge 12 ]]; then V20_IP_HEALTH=NORMAL; else V20_IP_HEALTH=PARTIAL; fi
  printf ' IP 基础健康        : '; color_state "$V20_IP_HEALTH"; printf '\n'
  printf ' 说明               : 这里只检查基础健康，不使用不可靠的免费黑名单给 IP 下结论\n'
}

v20_resource_health(){
  v20_read_resource_limits
  local base raw mem_kb mem_bytes swap_kb swap_bytes limited=0 partial=0 evidence=0
  [[ "$V20_CPU_QUOTA_STATE" == NORMAL ]] && evidence=$((evidence+1))
  [[ "$V20_MEM_LIMIT" != UNKNOWN ]] && evidence=$((evidence+1))
  [[ "$V20_SWAP_LIMIT" != UNKNOWN ]] && evidence=$((evidence+1))
  [[ "$V20_PIDS_LIMIT" != UNKNOWN ]] && evidence=$((evidence+1))

  if [[ "$V20_CPU_QUOTA_STATE" == LIMITED ]]; then
    limited=1; v20_add_issue "CPU 有效配额低于系统可见核心"
  fi

  base="$V20_CGROUP_BASE"
  if [[ "$base" != UNKNOWN && -r "$base/memory.max" ]]; then
    raw="$(cat "$base/memory.max" 2>/dev/null)"; mem_kb="$(awk '/^MemTotal:/{print $2;exit}' /proc/meminfo 2>/dev/null)"
    if [[ "$raw" =~ ^[0-9]+$ && "$mem_kb" =~ ^[0-9]+$ ]]; then
      mem_bytes=$((mem_kb*1024))
      if awk -v lim="$raw" -v visible="$mem_bytes" 'BEGIN{exit !(lim<visible*0.90)}'; then limited=1; v20_add_issue "内存有效上限低于系统可见内存"; fi
    fi
  fi

  if [[ "$base" != UNKNOWN && -r "$base/memory.swap.max" ]]; then
    raw="$(cat "$base/memory.swap.max" 2>/dev/null)"; swap_kb="$(awk '/^SwapTotal:/{print $2;exit}' /proc/meminfo 2>/dev/null)"
    if [[ "$raw" =~ ^[0-9]+$ && "$swap_kb" =~ ^[0-9]+$ && "$swap_kb" -gt 0 ]]; then
      swap_bytes=$((swap_kb*1024))
      if awk -v lim="$raw" -v visible="$swap_bytes" 'BEGIN{exit !(lim<visible*0.90)}'; then limited=1; v20_add_issue "Swap 有效上限低于系统可见 Swap"; fi
    fi
  fi

  if [[ "$V20_PIDS_LIMIT" =~ ^[0-9]+$ ]]; then
    if (( V20_PIDS_LIMIT<256 )); then limited=1; v20_add_issue "进程数上限异常偏低（${V20_PIDS_LIMIT}）"
    elif (( V20_PIDS_LIMIT<512 )); then partial=1; v20_add_issue "进程数上限偏低（${V20_PIDS_LIMIT}）"
    fi
  fi

  if (( limited )); then V20_RESOURCE_STATE=LIMITED
  elif (( partial )); then V20_RESOURCE_STATE=PARTIAL
  elif (( evidence>=4 )); then V20_RESOURCE_STATE=NORMAL
  elif (( evidence>=2 )); then V20_RESOURCE_STATE=PARTIAL
  else V20_RESOURCE_STATE=UNKNOWN
  fi
}

v20_median_col(){
  local filter="$1" col="$2"
  awk -F '\t' "$filter" "$NETWORK_TSV" 2>/dev/null | sort -n | awk '{a[NR]=$1} END{if(NR==0)print "UNKNOWN"; else if(NR%2)printf "%.2f",a[(NR+1)/2]; else printf "%.2f",(a[NR/2]+a[NR/2+1])/2}'
}

v20_network_metrics(){
  V20_GLOBAL_MEDIAN_UP="$(v20_median_col '$3=="PASS" && $2!="Cloudflare Edge" && $5+0>0 {print $5}' 5)"
  V20_GLOBAL_MEDIAN_DOWN="$(v20_median_col '$3=="PASS" && $2!="Cloudflare Edge" && $6+0>0 {print $6}' 6)"
  V20_SEA_MEDIAN_UP="$(v20_median_col '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Bangkok)/ && $5+0>0 {print $5}' 5)"
  V20_SEA_MEDIAN_DOWN="$(v20_median_col '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Bangkok)/ && $6+0>0 {print $6}' 6)"
  V20_SLOW_REGION_COUNT="$(awk -F '\t' '$3=="PASS" && $2!="Cloudflare Edge" && (($5+0<5)||($6+0<5)){n++} END{print n+0}' "$NETWORK_TSV")"
  V20_ASYMMETRY_COUNT="$(awk -F '\t' '$3=="PASS" && $2!="Cloudflare Edge" && $5+0>0 && $6+0>0 {a=$5+0;b=$6+0; lo=(a<b?a:b); hi=(a>b?a:b); if(lo<10 && hi/lo>=10)n++} END{print n+0}' "$NETWORK_TSV")"
}

v20_score_and_verdict(){
  local score=0 tested=0 global sea x
  global="$(awk -F '	' '$3=="PASS" && $2!="Cloudflare Edge"{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  sea="$(awk -F '	' '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Bangkok)/{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  v20_network_metrics

  # Network 50: coverage 8 + global throughput 12 + SEA 10 + ICMP 10 + HTTPS 10.
  tested=$((tested+8)); if (( global>=8 )); then score=$((score+8)); elif ((global>=6)); then score=$((score+7)); elif ((global>=4)); then score=$((score+5)); elif ((global>=2)); then score=$((score+2)); fi
  if [[ "$V20_GLOBAL_MEDIAN_UP" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+8)); x="$V20_GLOBAL_MEDIAN_UP"
    if awk -v x="$x" 'BEGIN{exit !(x>=100)}'; then score=$((score+8)); elif awk -v x="$x" 'BEGIN{exit !(x>=50)}'; then score=$((score+7)); elif awk -v x="$x" 'BEGIN{exit !(x>=20)}'; then score=$((score+5)); elif awk -v x="$x" 'BEGIN{exit !(x>=10)}'; then score=$((score+3)); else score=$((score+1)); v20_add_issue "全球上行中位数偏低（${x} Mbps）"; fi
  fi
  if [[ "$V20_GLOBAL_MEDIAN_DOWN" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+4)); x="$V20_GLOBAL_MEDIAN_DOWN"
    if awk -v x="$x" 'BEGIN{exit !(x>=200)}'; then score=$((score+4)); elif awk -v x="$x" 'BEGIN{exit !(x>=100)}'; then score=$((score+3)); elif awk -v x="$x" 'BEGIN{exit !(x>=50)}'; then score=$((score+2)); elif awk -v x="$x" 'BEGIN{exit !(x>=20)}'; then score=$((score+1)); else v20_add_issue "全球下行中位数偏低（${x} Mbps）"; fi
  fi
  tested=$((tested+4)); if ((sea>=3)); then score=$((score+4)); elif ((sea==2)); then score=$((score+3)); elif ((sea==1)); then score=$((score+1)); fi
  if [[ "$V20_SEA_MEDIAN_UP" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+4)); x="$V20_SEA_MEDIAN_UP"
    if awk -v x="$x" 'BEGIN{exit !(x>=100)}'; then score=$((score+4)); elif awk -v x="$x" 'BEGIN{exit !(x>=50)}'; then score=$((score+3)); elif awk -v x="$x" 'BEGIN{exit !(x>=20)}'; then score=$((score+2)); elif awk -v x="$x" 'BEGIN{exit !(x>=10)}'; then score=$((score+1)); else v20_add_issue "东南亚上行中位数偏低（${x} Mbps）"; fi
  fi
  if [[ "$V20_SEA_MEDIAN_DOWN" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+2)); x="$V20_SEA_MEDIAN_DOWN"
    if awk -v x="$x" 'BEGIN{exit !(x>=100)}'; then score=$((score+2)); elif awk -v x="$x" 'BEGIN{exit !(x>=50)}'; then score=$((score+1)); else v20_add_issue "东南亚下行中位数偏低（${x} Mbps）"; fi
  fi
  if [[ "$V20_PING_STATE" == PASS && "$V20_PING_LOSS" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+10));
    if awk -v x="$V20_PING_LOSS" 'BEGIN{exit !(x<=1)}'; then score=$((score+10)); elif awk -v x="$V20_PING_LOSS" 'BEGIN{exit !(x<=3)}'; then score=$((score+7)); elif awk -v x="$V20_PING_LOSS" 'BEGIN{exit !(x<=5)}'; then score=$((score+4)); else v20_add_issue "网络丢包偏高（${V20_PING_LOSS}%）"; fi
  fi
  tested=$((tested+10)); if (( V20_HTTPS_TOTAL>0 && V20_HTTPS_PASS==V20_HTTPS_TOTAL )); then score=$((score+10)); elif (( V20_HTTPS_PASS>=12 )); then score=$((score+7)); else v20_add_issue "HTTPS 稳定性不足（${V20_HTTPS_PASS}/${V20_HTTPS_TOTAL}）"; fi
  (( V20_SLOW_REGION_COUNT>0 )) && v20_add_issue "存在 ${V20_SLOW_REGION_COUNT} 个极慢测速地区（<5 Mbps）"
  (( V20_ASYMMETRY_COUNT>0 )) && v20_add_issue "存在 ${V20_ASYMMETRY_COUNT} 个严重上下行不对称地区"

  # CPU 15: steal 8, quota 4, actual benchmark 3.
  local steal_for_score="$V20_CPU_LOAD_STEAL"
  [[ "$steal_for_score" =~ ^[0-9.]+$ ]] || steal_for_score="$V20_CPU_STEAL"
  if [[ "$steal_for_score" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+8));
    if awk -v x="$steal_for_score" 'BEGIN{exit !(x<=2)}'; then score=$((score+8)); elif awk -v x="$steal_for_score" 'BEGIN{exit !(x<=5)}'; then score=$((score+6)); elif awk -v x="$steal_for_score" 'BEGIN{exit !(x<=10)}'; then score=$((score+3)); v20_add_issue "CPU Steal 偏高（${steal_for_score}%）"; else v20_add_issue "CPU Steal 很高（${steal_for_score}%）"; fi
  fi
  if [[ "$V20_CPU_QUOTA_STATE" != UNKNOWN ]]; then tested=$((tested+4)); if [[ "$V20_CPU_QUOTA_STATE" == NORMAL ]]; then score=$((score+4)); else v20_add_issue "CPU 配额低于系统可见核心"; fi; fi
  if [[ "$V20_CPU_BENCH_STATE" == PASS && "$V20_CPU_SCALE_EFF" =~ ^[0-9.]+$ ]]; then tested=$((tested+3)); if awk -v x="$V20_CPU_SCALE_EFF" 'BEGIN{exit !(x>=75)}'; then score=$((score+3)); elif awk -v x="$V20_CPU_SCALE_EFF" 'BEGIN{exit !(x>=55)}'; then score=$((score+2)); elif awk -v x="$V20_CPU_SCALE_EFF" 'BEGIN{exit !(x>=35)}'; then score=$((score+1)); else v20_add_issue "CPU 多核扩展效率偏低（${V20_CPU_SCALE_EFF}%）"; fi; fi

  # Disk 15.
  if [[ "$IO_STATE" == PASS && "$IO_AVG_MB" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+5)); if awk -v x="$IO_AVG_MB" 'BEGIN{exit !(x>=500)}'; then score=$((score+5)); elif awk -v x="$IO_AVG_MB" 'BEGIN{exit !(x>=200)}'; then score=$((score+4)); elif awk -v x="$IO_AVG_MB" 'BEGIN{exit !(x>=100)}'; then score=$((score+3)); else score=$((score+1)); v20_add_issue "顺序磁盘写入较慢"; fi
  fi
  if [[ "$V20_DISK_IOPS" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+5)); if awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=1000)}'; then score=$((score+5)); elif awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=300)}'; then score=$((score+4)); elif awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=100)}'; then score=$((score+3)); elif awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=30)}'; then score=$((score+2)); else v20_add_issue "4K 同步写 IOPS 很低"; fi
  fi
  if [[ "$V20_FSYNC_P95" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+5)); if awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<5)}'; then score=$((score+5)); elif awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<10)}'; then score=$((score+4)); elif awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<20)}'; then score=$((score+3)); elif awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<50)}'; then score=$((score+1)); v20_add_issue "fsync 延迟偏高"; else v20_add_issue "fsync 延迟很高"; fi
  fi

  # IP 10.
  tested=$((tested+10)); if [[ "$V20_IP_HEALTH" == NORMAL ]]; then score=$((score+10)); else score=$((score+5)); v20_add_issue "IP/DNS/HTTPS 基础健康存在缺项"; fi

  # Resource constraints 10; missing quota evidence reduces completeness instead of pretending PASS.
  v20_resource_health
  case "$V20_RESOURCE_STATE" in
    NORMAL) tested=$((tested+10)); score=$((score+10)) ;;
    PARTIAL) tested=$((tested+6)); score=$((score+6)); v20_add_issue "CPU 配额信息不可确认，资源证据部分有效" ;;
    LIMITED) tested=$((tested+10)); score=$((score+2)) ;;
    *) tested=$((tested+3)); score=$((score+3)); v20_add_issue "资源限制信号无法完整判断" ;;
  esac

  V20_COMPLETENESS="$tested"
  local normalized=0
  (( tested>0 )) && normalized=$(( score*100/tested ))
  V20_SCORE="$normalized"
  if (( normalized>=85 )); then V20_GRADE=GOOD; V20_ADVICE='建议保留';
  elif (( normalized>=70 )); then V20_GRADE=FAIR; V20_ADVICE='可以使用，建议观察';
  elif (( normalized>=55 )); then V20_GRADE=CAUTION; V20_ADVICE='谨慎保留，建议观察稳定性';
  else V20_GRADE=POOR; V20_ADVICE='建议更换或先排查明显问题'; fi
  if (( tested<75 )); then [[ "$V20_GRADE" == GOOD ]] && V20_GRADE=FAIR; V20_ADVICE="${V20_ADVICE}（部分测试未完成）"; fi
}

v20_grade_zh(){
  case "$1" in GOOD) printf '良好';; FAIR) printf '一般';; CAUTION) printf '偏弱';; POOR) printf '较差';; *) printf '未知';; esac
}

v20_usecase_fit(){
  V20_SITE_FIT='观察'; V20_SEA_FIT='较弱'; V20_DB_FIT='较弱'
  local steal="$V20_CPU_LOAD_STEAL"
  [[ "$steal" =~ ^[0-9.]+$ ]] || steal="$V20_CPU_STEAL"

  if [[ "$V20_RESOURCE_STATE" == LIMITED ]] || (( V20_HTTPS_TOTAL>0 && V20_HTTPS_PASS<12 )); then
    V20_SITE_FIT='不建议'
  elif [[ "$V20_IP_HEALTH" == NORMAL && "$V20_DISK_IOPS" =~ ^[0-9.]+$ && "$V20_FSYNC_P95" =~ ^[0-9.]+$ && "$V20_GLOBAL_MEDIAN_DOWN" =~ ^[0-9.]+$ ]] \
       && awk -v i="$V20_DISK_IOPS" -v f="$V20_FSYNC_P95" -v d="$V20_GLOBAL_MEDIAN_DOWN" 'BEGIN{exit !(i>=500 && f<=5 && d>=20)}'; then
    V20_SITE_FIT='适合'
  fi

  if [[ "$V20_SEA_MEDIAN_UP" =~ ^[0-9.]+$ && "$V20_SEA_MEDIAN_DOWN" =~ ^[0-9.]+$ ]]; then
    if awk -v u="$V20_SEA_MEDIAN_UP" -v d="$V20_SEA_MEDIAN_DOWN" 'BEGIN{exit !(u>=50&&d>=100)}'; then V20_SEA_FIT='良好'
    elif awk -v u="$V20_SEA_MEDIAN_UP" -v d="$V20_SEA_MEDIAN_DOWN" 'BEGIN{exit !(u>=15&&d>=30)}'; then V20_SEA_FIT='可用'
    else V20_SEA_FIT='较弱'; fi
  fi

  if [[ "$V20_DISK_IOPS" =~ ^[0-9.]+$ && "$V20_FSYNC_P95" =~ ^[0-9.]+$ ]]; then
    if awk -v i="$V20_DISK_IOPS" -v f="$V20_FSYNC_P95" 'BEGIN{exit !(i>=1000&&f<=2)}'; then V20_DB_FIT='良好'
    elif awk -v i="$V20_DISK_IOPS" -v f="$V20_FSYNC_P95" 'BEGIN{exit !(i>=500&&f<=5)}'; then V20_DB_FIT='一般'
    else V20_DB_FIT='较弱'; fi
  fi

  if [[ "$steal" =~ ^[0-9.]+$ ]] && awk -v x="$steal" 'BEGIN{exit !(x>10)}'; then
    [[ "$V20_SITE_FIT" == '适合' ]] && V20_SITE_FIT='观察'
    [[ "$V20_DB_FIT" == '良好' ]] && V20_DB_FIT='一般'
  fi
}

v20_final_verdict(){
  v20_score_and_verdict
  v20_usecase_fit
  local global sea
  global="$(awk -F '\t' '$3=="PASS" && $2!="Cloudflare Edge"{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  sea="$(awk -F '\t' '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Bangkok)/{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  rule
  printf '%s%s 最终验机结论%s\n' "$BOLD" "$BLUE" "$RESET"
  printf ' 综合评级           : %s%s%s\n' "$GREEN" "$(v20_grade_zh "$V20_GRADE")" "$RESET"
  printf ' 建议               : %s%s%s\n' "$YELLOW" "$V20_ADVICE" "$RESET"
  printf ' 综合得分           : %s/100\n' "$V20_SCORE"
  printf ' 证据完整度         : %s%%\n' "$V20_COMPLETENESS"
  printf ' 全球有效测速       : %s 个地区\n' "$global"
  printf ' 全球上行中位数     : %s Mbps\n' "$V20_GLOBAL_MEDIAN_UP"
  printf ' 全球下行中位数     : %s Mbps\n' "$V20_GLOBAL_MEDIAN_DOWN"
  printf ' 东南亚有效测速     : %s/3\n' "$sea"
  printf ' 东南亚上行中位数   : %s Mbps\n' "$V20_SEA_MEDIAN_UP"
  printf ' 东南亚下行中位数   : %s Mbps\n' "$V20_SEA_MEDIAN_DOWN"
  printf ' CPU Steal（空载）  : %s%%\n' "$V20_CPU_STEAL"
  if [[ "$V20_CPU_LOAD_STEAL" =~ ^[0-9.]+$ ]]; then printf ' CPU Steal（负载）  : %s%%\n' "$V20_CPU_LOAD_STEAL"; fi
  printf ' CPU 多核效率       : %s%%\n' "$V20_CPU_SCALE_EFF"
  printf ' 磁盘 4K IOPS       : %s\n' "$V20_DISK_IOPS"
  if [[ "$V20_PING_STATE" == PASS ]]; then printf ' 网络丢包           : %s%%\n' "$V20_PING_LOSS"; elif [[ "$V20_PING_STATE" == ICMP_BLOCKED ]]; then printf ' 网络丢包           : ICMP 受限，未作为丢包证据\n'; else printf ' 网络丢包           : 未直接测得\n'; fi
  printf ' IP 基础健康        : '; color_state "$V20_IP_HEALTH"; printf '\n'
  printf ' 资源限制信号       : '; color_state "$V20_RESOURCE_STATE"; printf '\n'
  printf ' 内存有效上限       : %s\n' "$V20_MEM_LIMIT"
  printf ' Swap 有效上限      : %s\n' "$V20_SWAP_LIMIT"
  printf ' 进程数上限         : %s\n' "$V20_PIDS_LIMIT"
  printf ' 资源说明           : 未输入购买套餐，本项只检查隐藏限额/异常，不声称套餐规格完全一致\n'
  printf ' 中国大陆入站       : %s未直接检测%s（需要大陆来源探针，当前不据此扣分）\n' "$YELLOW" "$RESET"
  printf ' 常规网站/WordPress : %s\n' "$V20_SITE_FIT"
  printf ' 东南亚业务         : %s\n' "$V20_SEA_FIT"
  printf ' 数据库型负载       : %s\n' "$V20_DB_FIT"
  printf ' 时段说明           : 本次为即时验机；陌生商家建议晚高峰再运行同一命令复测\n'
  if [[ -n "$V20_ISSUES" ]]; then printf ' 主要问题           : %s%s%s\n' "$YELLOW" "$V20_ISSUES" "$RESET"; else printf ' 主要问题           : 未发现明显硬伤\n'; fi
}

v20_patch_report_json(){
  [[ -f "${REPORT_JSON:-}" ]] || return 0
  command -v python3 >/dev/null 2>&1 || return 0
  python3 - "$REPORT_JSON" "$V20_CPU_STEAL" "$V20_CPU_QUOTA" "$V20_CPU_QUOTA_STATE" "$V20_CPU_SINGLE" "$V20_CPU_MULTI" "$V20_DISK_IOPS" "$V20_FSYNC_AVG" "$V20_FSYNC_P95" "$V20_PING_STATE" "$V20_PING_LOSS" "$V20_PING_JITTER" "$V20_HTTPS_PASS" "$V20_HTTPS_TOTAL" "$V20_HTTPS_JITTER" "$V20_DNS_PASS" "$V20_DNS_TOTAL" "$V20_IP_HEALTH" "$V20_SCORE" "$V20_COMPLETENESS" "$V20_GRADE" "$V20_ADVICE" "$V20_ISSUES" <<'PYV20JSON' 2>/dev/null || true
import json,sys
p=sys.argv[1]; a=sys.argv[2:]
try:
 d=json.load(open(p,encoding='utf-8'))
 d['schema_version']=5
 d['vps_audit_v20']={
  'cpu':{'steal_percent':a[0],'quota':a[1],'quota_state':a[2],'sha256_single_mb_s':a[3],'sha256_multi_mb_s':a[4],'bench_state':__import__('os').environ.get('P07_V20_CPU_BENCH_STATE','UNKNOWN'),'load_steal_percent':__import__('os').environ.get('P07_V20_CPU_LOAD_STEAL','UNKNOWN'),'multi_core_efficiency_percent':__import__('os').environ.get('P07_V20_CPU_SCALE_EFF','UNKNOWN')},
  'disk':{'sync_4k_iops':a[5],'fsync_avg_ms':a[6],'fsync_p95_ms':a[7]},
  'stability':{'icmp_state':a[8],'worst_loss_percent':a[9],'worst_jitter_ms':a[10],'https_pass':int(a[11]),'https_total':int(a[12]),'https_ttfb_jitter_ms':a[13]},
  'network_quality':{'global_median_upload_mbps':__import__('os').environ.get('P07_V20_GLOBAL_MEDIAN_UP','UNKNOWN'),'global_median_download_mbps':__import__('os').environ.get('P07_V20_GLOBAL_MEDIAN_DOWN','UNKNOWN'),'sea_median_upload_mbps':__import__('os').environ.get('P07_V20_SEA_MEDIAN_UP','UNKNOWN'),'sea_median_download_mbps':__import__('os').environ.get('P07_V20_SEA_MEDIAN_DOWN','UNKNOWN'),'slow_region_count':int(__import__('os').environ.get('P07_V20_SLOW_REGION_COUNT','0')),'severe_asymmetry_count':int(__import__('os').environ.get('P07_V20_ASYMMETRY_COUNT','0'))},
  'ip_health':{'dns_pass':int(a[14]),'dns_total':int(a[15]),'state':a[16]},
  'resource_constraints':{'state':__import__('os').environ.get('P07_V20_RESOURCE_STATE','UNKNOWN'),'scope':'EFFECTIVE_CGROUP_LIMIT_SIGNALS','cgroup_base':__import__('os').environ.get('P07_V20_CGROUP_BASE','UNKNOWN'),'memory_limit':__import__('os').environ.get('P07_V20_MEM_LIMIT','UNKNOWN'),'swap_limit':__import__('os').environ.get('P07_V20_SWAP_LIMIT','UNKNOWN'),'pids_limit':__import__('os').environ.get('P07_V20_PIDS_LIMIT','UNKNOWN')},
  'workload_fit':{'website_wordpress':__import__('os').environ.get('P07_V20_SITE_FIT','UNKNOWN'),'southeast_asia':__import__('os').environ.get('P07_V20_SEA_FIT','UNKNOWN'),'database':__import__('os').environ.get('P07_V20_DB_FIT','UNKNOWN')},
  'verdict':{'score':int(a[17]),'evidence_completeness_percent':int(a[18]),'grade':a[19],'advice':a[20],'issues':[x for x in a[21].split('；') if x]},
  'mainland_inbound_probe':'NOT_RUN'
 }
 json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
except Exception: pass
PYV20JSON
}

v20_rc2_semantic_self_test(){
  local f=0 n
  : >"$NETWORK_TSV"
  # Adversarial case: every region connects, but performance is unusably low.
  for n in 'US West' 'US East' 'Europe' 'Hong Kong' 'Singapore' 'Kuala Lumpur' 'Bangkok' 'Tokyo'; do
    printf 'test\t%s\tPASS\tSPEEDTESTGO_FALLBACK\t2.00\t2.00\t80\n' "$n" >>"$NETWORK_TSV"
  done
  V20_PING_STATE=ICMP_BLOCKED
  V20_PING_LOSS=UNKNOWN
  V20_PING_JITTER=UNKNOWN
  V20_HTTPS_PASS=15; V20_HTTPS_TOTAL=15; V20_HTTPS_JITTER=5.0
  V20_CPU_STEAL=0.10; V20_CPU_LOAD_STEAL=0.20
  V20_CPU_QUOTA='无限制'; V20_CPU_QUOTA_STATE=NORMAL
  V20_CPU_BENCH_STATE=PASS; V20_CPU_SINGLE=500; V20_CPU_MULTI=1000
  IO_STATE=PASS; IO_AVG_MB=500
  V20_DISK_IOPS=1000; V20_FSYNC_P95=2; V20_FSYNC_AVG=1
  V20_IP_HEALTH=NORMAL
  CORES=2; RAM_TOTAL='2.0 GiB'; DISK_TOTAL='50 GiB'; VIRT='KVM'
  V20_ISSUES=''
  v20_score_and_verdict
  [[ "$V20_GRADE" != GOOD ]] || f=1
  (( V20_SCORE < 85 )) || f=1
  [[ "$V20_ISSUES" != *'网络丢包偏高'* ]] || f=1
  [[ "$V20_GLOBAL_MEDIAN_UP" == '2.00' ]] || f=1
  [[ "$V20_SEA_MEDIAN_UP" == '2.00' ]] || f=1

  # Missing CPU quota evidence must reduce evidence, not masquerade as healthy.
  V20_CPU_QUOTA_STATE=UNKNOWN
  v20_resource_health
  [[ "$V20_RESOURCE_STATE" == PARTIAL ]] || f=1

  if (( f==0 )); then printf 'V20_RC2_SEMANTIC_SELF_TEST=PASS\n'; else printf 'V20_RC2_SEMANTIC_SELF_TEST=FAIL\n'; return 1; fi
}

v20_self_test(){
  local old="$DEMO" f=0
  DEMO=1
  collect_system
  v20_cpu_test >/dev/null || f=1
  print_io >/dev/null || f=1
  v20_disk_test >/dev/null || f=1
  : >"$NETWORK_TSV"
  for n in 'US West' 'US East' 'Europe' 'Hong Kong' 'Singapore' 'Kuala Lumpur' 'Bangkok' 'Tokyo'; do
    printf 'demo\t%s\tPASS\tSPEEDTESTGO_FALLBACK\t500\t600\t50\n' "$n" >>"$NETWORK_TSV"
  done
  v20_network_stability >/dev/null || f=1
  v20_ip_test >/dev/null || f=1
  v20_final_verdict >/dev/null || f=1
  [[ "$V20_CPU_STEAL" == '0.30' ]] || f=1
  [[ "$V20_CPU_BENCH_STATE" == PASS ]] || f=1
  [[ "$V20_CPU_LOAD_STEAL" == '0.40' ]] || f=1
  [[ "$V20_DISK_IOPS" == '820' ]] || f=1
  [[ "$V20_HTTPS_PASS" == '15' ]] || f=1
  [[ "$V20_GRADE" == GOOD ]] || f=1
  DEMO="$old"
  (( f==0 )) && printf 'V20_SELF_TEST=PASS\n' || { printf 'V20_SELF_TEST=FAIL\n'; return 1; }
}
# ===== /P07 VPS Audit 2.0 =====

self_test(){
  local f=0
  [[ "$(rate_to_mb '1.20 GB/s')" == "1200.00" ]] || f=1
  [[ "$(rate_to_mb '577 MB/s')" == "577.00" ]] || f=1
  [[ "$(format_mb_rate '1500.00')" == "1.50 GB/s" ]] || f=1
  local jf="$TMP_DIR/self-json.txt"
  cat >"$jf" <<'EOFJ'
warning-prefix
{"ping":{"latency":1.23},"download":{"bandwidth":4000000},"upload":{"bandwidth":2000000}}
EOFJ
  [[ "$(parse_speed_json_file "$jf")" == "16.00|32.00|1.23" ]] || f=1
  [[ "$(china_verdict_from_counts 0 0 2 9 6 0 3)" == "INCONCLUSIVE" ]] || f=1
  [[ "$(china_verdict_from_counts 1 0 1 9 6 0 3)" == "NORMAL" ]] || f=1
  [[ "$(china_verdict_from_counts 0 2 0 9 2 4 3)" == "HIGH_RISK" ]] || f=1
  [[ ${#OOKLA_X86_64_SHA256} -eq 64 ]] || f=1
  [[ ${#OOKLA_I386_SHA256} -eq 64 ]] || f=1
  [[ ${#OOKLA_AARCH64_SHA256} -eq 64 ]] || f=1
  [[ ${#OOKLA_ARMHF_SHA256} -eq 64 ]] || f=1
  [[ ${#OOKLA_ARMEL_SHA256} -eq 64 ]] || f=1
  [[ ${#SPEEDTEST_GO_X86_64_SHA256} -eq 64 ]] || f=1
  [[ ${#SPEEDTEST_GO_I386_SHA256} -eq 64 ]] || f=1
  [[ ${#SPEEDTEST_GO_ARM64_SHA256} -eq 64 ]] || f=1
  [[ ${#SPEEDTEST_GO_ARMV7_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_386_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_AMD64_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_ARM64_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_ARMV5_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_ARMV6_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_ARMV7_SHA256} -eq 64 ]] || f=1
  local old_demo="$DEMO"; DEMO=1
  : >"$NETWORK_TSV"
  speed_node '' 'Speedtest.net' >/dev/null || f=1
  speedtestgo_sea_supplement >/dev/null || true
  [[ "$(awk -F '	' '$2=="Kuala Lumpur" && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1
  [[ "$(awk -F '	' '$2=="Bangkok" && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1
  DEMO="$old_demo"
  # Retry lifecycle regression: exercise non-demo retry twice with a fake backend.
  local fake="$TMP_DIR/fake-speedtest" saved_bin="$SPEEDTEST_BIN" saved_temp="$SPEEDTEST_TEMP" saved_demo="$DEMO" saved_tsv="$NETWORK_TSV"
  cat >"$fake" <<'EOFFAKE'
#!/usr/bin/env bash
printf '%s\n' '{"ping":{"latency":1.25},"download":{"bandwidth":4000000},"upload":{"bandwidth":2000000}}'
EOFFAKE
  chmod +x "$fake"
  SPEEDTEST_BIN="$fake"; SPEEDTEST_TEMP=0; DEMO=0; NETWORK_TSV="$TMP_DIR/lifecycle.tsv"; : >"$NETWORK_TSV"
  speed_node_retry '' 'Lifecycle A' >/dev/null || f=1
  [[ -x "$fake" && -d "$TMP_DIR" ]] || f=1
  speed_node_retry '' 'Lifecycle B' >/dev/null || f=1
  [[ "$(awk -F '\t' '$3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "2" ]] || f=1
  [[ -x "$fake" && -d "$TMP_DIR" ]] || f=1
  : >"$NETWORK_TSV"
  speed_node_pool 'Lifecycle Pool' '1|Lifecycle A' '2|Lifecycle B' >/dev/null || f=1
  [[ "$(awk -F '\t' '$2=="Lifecycle Pool" && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1
  [[ -x "$fake" && -d "$TMP_DIR" ]] || f=1
  [[ "$(network_reason 1 'HTTP 429 Too Many Requests')" == RATE_LIMITED ]] || f=1
  [[ "$(network_reason 1 'Cannot retrieve speedtest configuration')" == BACKEND_UNAVAILABLE ]] || f=1
  [[ "$(network_reason 1 'HTTP 429 Too Many Requests')" == RATE_LIMITED ]] || f=1
  DEMO=1; : >"$NETWORK_TSV"; cloudflare_fallback >/dev/null || f=1
  [[ "$(awk -F '\t' '$2=="Cloudflare Edge" && $3=="PASS" && $4=="SUPPLEMENTAL"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1
  : >"$NETWORK_TSV"; GLOBAL_FALLBACK_PASS=0; librespeed_global_fallback >/dev/null || f=1
  [[ "$(awk -F '\t' '$4=="LIBRESPEED_FALLBACK" && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "6" ]] || f=1
  SPEEDTEST_BIN="$saved_bin"; SPEEDTEST_TEMP="$saved_temp"; DEMO="$saved_demo"; NETWORK_TSV="$saved_tsv"
  if (( f )); then printf 'SELF_TEST=FAIL\n'; return 1; else printf 'SELF_TEST=PASS\n'; fi
}

if (( SELF_TEST )); then self_test && v20_self_test && v20_rc2_semantic_self_test; exit $?; fi

collect_system
print_system
v20_cpu_test
print_io
v20_disk_test
print_network
v20_network_stability
v20_ip_test
v20_final_verdict
rule
ELAPSED=$(( $(date +%s) - START_EPOCH ))
printf ' 总耗时             : %s%s 分 %s 秒%s\n' "$GREEN" "$((ELAPSED/60))" "$((ELAPSED%60))" "$RESET"
printf ' 完成时间           : %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
write_reports
P07_V20_RESOURCE_STATE="$V20_RESOURCE_STATE" P07_V20_CGROUP_BASE="$V20_CGROUP_BASE" P07_V20_SITE_FIT="$V20_SITE_FIT" P07_V20_SEA_FIT="$V20_SEA_FIT" P07_V20_DB_FIT="$V20_DB_FIT" P07_V20_MEM_LIMIT="$V20_MEM_LIMIT" P07_V20_SWAP_LIMIT="$V20_SWAP_LIMIT" P07_V20_PIDS_LIMIT="$V20_PIDS_LIMIT" P07_V20_CPU_SCALE_EFF="$V20_CPU_SCALE_EFF" P07_V20_CPU_BENCH_STATE="$V20_CPU_BENCH_STATE" P07_V20_CPU_LOAD_STEAL="$V20_CPU_LOAD_STEAL" P07_V20_GLOBAL_MEDIAN_UP="$V20_GLOBAL_MEDIAN_UP" P07_V20_GLOBAL_MEDIAN_DOWN="$V20_GLOBAL_MEDIAN_DOWN" P07_V20_SEA_MEDIAN_UP="$V20_SEA_MEDIAN_UP" P07_V20_SEA_MEDIAN_DOWN="$V20_SEA_MEDIAN_DOWN" P07_V20_SLOW_REGION_COUNT="$V20_SLOW_REGION_COUNT" P07_V20_ASYMMETRY_COUNT="$V20_ASYMMETRY_COUNT" v20_patch_report_json
printf ' 中文报告           : %s%s%s\n' "$BLUE" "$REPORT_TXT" "$RESET"
[[ -f "${REPORT_JSON:-}" ]] && printf ' 机器数据（JSON）   : %s%s%s\n' "$BLUE" "$REPORT_JSON" "$RESET"
rule
