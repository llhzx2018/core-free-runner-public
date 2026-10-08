#!/usr/bin/env bash
set -uo pipefail

APP="P07 VPS 一键验机"
VERSION="V2.2.7"
BUILD_ID="2.2.7-rc1-full-native-stream"

BASE_VERSION="V2.1.0"
BASE_BUILD="2.1.0-rc7-field"
BASE_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/0a851b9fe1819c7970ed5bb8e3633f2fc8e73166/experiments/p07-vps-audit-v21.sh"
BASE_SHA256="d1846e751bba5c860c623e3db26641908e27ca43b39cf37016758853b65a952d"

AUDIT_DETAILS=0; AUDIT_QUICK=0
case "${1:-}" in
  --version|-V) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
  --build-id) printf '%s\n' "$BUILD_ID"; exit 0 ;;
  --help|-h)
    cat <<'EOF'
P07 VPS 一键验机 V2.2.7

默认完整还原原版验机的显示与测试顺序：
- 首先显示服务器基础配置（系统、CPU、内存、磁盘、IP 等）
- 接着实时逐项显示 CPU、磁盘 I/O、全球和大陆网络测速的原始结果
- 增强 fio 4K/64K/512K/1M、三网回程和详细中文报告均保留
- 不再隐藏真实输出、延迟到测试结束才显示，也不折叠或截断测速数据
- 仅在原始输出超过 20 秒无变化时提示仍在运行，整体最长 12 分钟
- --quick 可单独调用快速检查；菜单 2 默认始终完整验机
EOF
    exit 0
    ;;
  --reference)
    cat <<'EOF'
P07 VPS 一键验机 V2.2.7 · 判定参考线

单核 CPU（SHA256）
  强      >= 900 MB/s
  良好    >= 500 MB/s
  可用    >= 250 MB/s
  偏弱    >= 150 MB/s
  很弱    <  150 MB/s

数据库型 I/O（4K 同步写 + fsync P95）
  强      >= 1000 IOPS 且 fsync P95 <= 2.5 ms
  良好    >=  500 IOPS 且 fsync P95 <= 5 ms
  可用    >=  300 IOPS 且 fsync P95 <= 10 ms
  偏弱    其它

CPU 争抢（Steal）
  正常    <= 2%
  可接受  <= 5%
  需观察  <= 10%
  异常    > 10%

CloudPanel / 多站内存基线
  >= 1800 MiB   视为 2GB 级别
  <  1800 MiB   标记为内存短板

CPU 核数
  1 vCPU        标记并发上限
  >= 2 vCPU     不触发“1 vCPU 并发上限”短板

边界：
  这些是 P07 针对 CloudPanel / WordPress / PHP / MySQL / 小工具站的工作负载参考线，
  不是行业统一 VPS 排名，也不是商家宣传评分。
EOF
    exit 0
    ;;
  --color-demo) ;;
  --self-test) ;;
  --details) AUDIT_DETAILS=1 ;;
  --quick) AUDIT_QUICK=1 ;;
  "") ;;
  *) printf '未知参数：%s\n' "$1" >&2; exit 2 ;;
esac

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RESET=$'\033[0m'; BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; CYAN=$'\033[36m'; GRAY=$'\033[90m'
else
  RESET=""; BOLD=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; GRAY=""
fi

rule(){ printf '%s\n' '----------------------------------------------------------------------'; }
sha256_file(){
  local f="$1"
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$f" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$f" | awk '{print $1}'
  else return 127
  fi
}
fetch(){
  local url="$1" out="$2"
  if command -v curl >/dev/null 2>&1; then curl -fsSL --retry 2 --connect-timeout 10 --max-time 90 "$url" -o "$out"
  elif command -v wget >/dev/null 2>&1; then wget -q --https-only --timeout=90 --tries=2 -O "$out" "$url"
  else return 127
  fi
}
strip_terminal_codes(){
  sed -E $'s/\x1B\\[[0-9;?]*[ -/]*[@-~]//g; s/\r$//'
}
last_value(){
  local label="$1" file="$2"
  grep -F "$label" "$file" 2>/dev/null | tail -n1 | sed 's/^[^:]*:[[:space:]]*//' | sed 's/[[:space:]]*$//'
}
first_number(){
  printf '%s\n' "$1" | grep -Eo '[0-9]+([.][0-9]+)?' | head -n1
}
num_ge(){ awk -v a="$1" -v b="$2" 'BEGIN{exit !(a>=b)}'; }
num_le(){ awk -v a="$1" -v b="$2" 'BEGIN{exit !(a<=b)}'; }
num_gt(){ awk -v a="$1" -v b="$2" 'BEGIN{exit !(a>b)}'; }

semantic_color(){
  local value="${1:-}"
  case "$value" in
    强|良好|正常|适合|建议保留) printf '%s' "$GREEN" ;;
    可用|可接受|需观察|有条件保留|可以保留*|能用*|CPU/I\ O\ 可以*) printf '%s' "$YELLOW" ;;
    偏弱|很弱|异常偏高|不建议|不建议*|建议更换*) printf '%s' "$RED" ;;
    *) printf '%s' "$CYAN" ;;
  esac
}
paint_semantic(){
  local value="${1:-}" color
  color="$(semantic_color "$value")"
  printf '%s%s%s' "$color" "$value" "$RESET"
}
paint_bottleneck(){
  local value="${1:-}"
  if [[ "$value" == "未发现明显硬伤" ]]; then
    printf '%s%s%s' "$GREEN" "$value" "$RESET"
  elif [[ "$value" == *"隐藏资源限制"* ]]; then
    printf '%s%s%s' "$RED" "$value" "$RESET"
  else
    printf '%s%s%s' "$YELLOW" "$value" "$RESET"
  fi
}

cpu_class(){
  local x="$1"
  if ! [[ "$x" =~ ^[0-9.]+$ ]]; then printf '证据不足'; return; fi
  if num_ge "$x" 900; then printf '强'
  elif num_ge "$x" 500; then printf '良好'
  elif num_ge "$x" 250; then printf '可用'
  elif num_ge "$x" 150; then printf '偏弱'
  else printf '很弱'; fi
}

disk_class(){
  local i="$1" f="$2"
  if ! [[ "$i" =~ ^[0-9.]+$ && "$f" =~ ^[0-9.]+$ ]]; then printf '证据不足'; return; fi
  if num_ge "$i" 1000 && num_le "$f" 2.5; then printf '强'
  elif num_ge "$i" 500 && num_le "$f" 5; then printf '良好'
  elif num_ge "$i" 300 && num_le "$f" 10; then printf '可用'
  else printf '偏弱'; fi
}

steal_class(){
  local x="$1"
  if ! [[ "$x" =~ ^[0-9.]+$ ]]; then printf '证据不足'; return; fi
  if num_le "$x" 2; then printf '正常'
  elif num_le "$x" 5; then printf '可接受'
  elif num_le "$x" 10; then printf '需观察'
  else printf '异常偏高'; fi
}

classify_values(){
  local cpu="$1" iops="$2" fsync="$3" steal="$4" ram_mib="$5" cores="$6" resource="$7"
  local cc dc sc machine cloud keep bottlenecks="" suitable="" avoid=""

  cc="$(cpu_class "$cpu")"
  dc="$(disk_class "$iops" "$fsync")"
  sc="$(steal_class "$steal")"

  if [[ "$resource" == LIMITED ]]; then
    machine="不建议"
    keep="建议更换或先排查隐藏资源限制"
    bottlenecks="存在隐藏资源限制"
  elif [[ "$cc" == 证据不足 || "$dc" == 证据不足 || "$sc" == 证据不足 ]]; then
    machine="证据不足"
    keep="当前证据不足，建议重新检测"
  elif [[ "$cc" == 很弱 || "$cc" == 偏弱 || "$dc" == 偏弱 || "$sc" == 异常偏高 ]]; then
    machine="偏弱"
    keep="有条件保留"
  elif [[ "$cc" == 强 || "$cc" == 良好 ]] && [[ "$dc" == 强 || "$dc" == 良好 ]] && [[ "$sc" == 正常 || "$sc" == 可接受 ]]; then
    machine="良好"
    keep="建议保留"
  else
    machine="可用"
    keep="可以保留，建议观察"
  fi

  if [[ "$cc" == 偏弱 || "$cc" == 很弱 ]]; then
    bottlenecks="${bottlenecks:+$bottlenecks、}单核 CPU"
  fi
  if [[ "$dc" == 偏弱 ]]; then
    bottlenecks="${bottlenecks:+$bottlenecks、}数据库型磁盘 I/O"
  fi
  if [[ "$sc" == 需观察 || "$sc" == 异常偏高 ]]; then
    bottlenecks="${bottlenecks:+$bottlenecks、}宿主机 CPU 争抢"
  fi
  if [[ "$ram_mib" =~ ^[0-9]+$ ]] && (( ram_mib < 1800 )); then
    bottlenecks="${bottlenecks:+$bottlenecks、}内存不足 2GB 级别"
  fi
  if [[ "$cores" =~ ^[0-9]+$ ]] && (( cores == 1 )); then
    bottlenecks="${bottlenecks:+$bottlenecks、}1 vCPU 并发上限"
  fi
  [[ -n "$bottlenecks" ]] || bottlenecks="未发现明显硬伤"

  if [[ "$resource" == LIMITED ]]; then
    cloud="不建议"
  elif [[ "$machine" == 证据不足 ]]; then
    cloud="性能证据不完整，暂不判断"
  elif [[ "$ram_mib" =~ ^[0-9]+$ ]] && (( ram_mib < 1800 )); then
    if [[ "$cc" == 强 || "$cc" == 良好 ]]; then
      cloud="CPU/I/O 可以，但内存不足；不建议直接作为 CloudPanel 多站主机"
    else
      cloud="不建议作为 CloudPanel 多站主机"
    fi
  elif [[ "$cc" == 很弱 || "$cc" == 偏弱 ]]; then
    cloud="能用，但后台和动态页面响应会偏慢"
  elif [[ "$dc" == 偏弱 ]]; then
    cloud="能用，但数据库和后台写入会偏慢"
  elif [[ "$cores" =~ ^[0-9]+$ ]] && (( cores == 1 )); then
    cloud="适合低流量网站；高并发受 1 vCPU 限制"
  else
    cloud="适合"
  fi

  if [[ "$machine" == 良好 ]]; then
    suitable="CloudPanel、WordPress、工具站、常规数据库应用"
  elif [[ "$machine" == 可用 ]]; then
    suitable="轻量工具站、低流量网站、普通服务"
  else
    suitable="静态站、轻量工具、低负载服务"
  fi

  if [[ "$cc" == 偏弱 || "$cc" == 很弱 ]]; then
    avoid="重后台、高动态 PHP、高并发应用"
  elif [[ "$dc" == 偏弱 ]]; then
    avoid="重数据库、频繁写入、I/O 密集应用"
  elif [[ "$cores" =~ ^[0-9]+$ ]] && (( cores == 1 )); then
    avoid="高并发、多任务同时运行"
  else
    avoid="暂无明显用途禁区；仍需按实际负载观察"
  fi

  printf '%s|%s|%s|%s|%s|%s|%s\n' "$machine" "$cc" "$dc" "$cloud" "$keep" "$bottlenecks" "$suitable|$avoid"
}

print_value_verdict(){
  local file="$1"
  local cpu iops fsync steal resource ram_kib ram_mib cores row machine cc dc cloud keep bottlenecks suitable avoid

  cpu="$(first_number "$(last_value 'SHA256 单核' "$file")")"
  iops="$(first_number "$(last_value '磁盘 4K IOPS' "$file")")"
  [[ -n "$iops" ]] || iops="$(first_number "$(last_value '4K 同步写 IOPS' "$file")")"
  fsync="$(first_number "$(last_value 'fsync P95 延迟' "$file")")"
  steal="$(first_number "$(last_value 'CPU 争抢（Steal）（负载）' "$file")")"
  [[ -n "$steal" ]] || steal="$(first_number "$(last_value 'CPU 争抢（Steal）（空载）' "$file")")"
  resource="$(last_value '资源限制信号' "$file" | awk '{print $1}')"
  [[ -n "$resource" ]] || resource="UNKNOWN"
  ram_kib="$(awk '/MemTotal:/{print $2; exit}' /proc/meminfo 2>/dev/null || echo 0)"
  [[ "$ram_kib" =~ ^[0-9]+$ ]] || ram_kib=0
  ram_mib=$((ram_kib/1024))
  cores="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)"
  [[ "$cores" =~ ^[0-9]+$ ]] || cores=1

  row="$(classify_values "${cpu:-UNKNOWN}" "${iops:-UNKNOWN}" "${fsync:-UNKNOWN}" "${steal:-UNKNOWN}" "$ram_mib" "$cores" "$resource")"
  IFS='|' read -r machine cc dc cloud keep bottlenecks suitable avoid <<<"$row"

  rule
  printf '%s%s 服务器结论%s\n' "$BOLD" "$CYAN" "$RESET"
  printf ' 机器性能           : '; paint_semantic "$machine"; printf '\n'
  printf ' 单核 CPU           : '; paint_semantic "$cc"; printf '  （%s MB/s）\n' "${cpu:-未知}"
  printf ' 数据库型 I/O       : '; paint_semantic "$dc"; printf '  （4K %s IOPS / fsync P95 %s ms）\n' "${iops:-未知}" "${fsync:-未知}"
  printf ' CPU 争抢           : '; paint_semantic "$(steal_class "${steal:-UNKNOWN}")"; printf '  （%s%%）\n' "${steal:-未知}"
  printf ' CloudPanel/WordPress: '; paint_semantic "$cloud"; printf '\n'
  printf ' 主要短板           : '; paint_bottleneck "$bottlenecks"; printf '\n'
  printf ' 适合               : %s%s%s\n' "$GREEN" "$suitable" "$RESET"
  printf ' 不适合             : %s%s%s\n' "$RED" "$avoid" "$RESET"
  printf ' 保留建议           : '; paint_semantic "$keep"; printf '\n'
  printf ' 性价比             : %s月费未知，不做假判断%s\n' "$GRAY" "$RESET"
  printf ' 判断边界           : %s这是 P07 工作负载阈值，不是全网 VPS 排名；建议晚高峰复测一次确认稳定性。%s\n' "$GRAY" "$RESET"
  printf '\n'
  printf ' %s完整判定标准：运行 --reference 查看。%s\n' "$GRAY" "$RESET"
}

color_demo(){
  local demo
  demo="$(mktemp -t p07-color-demo.XXXXXX 2>/dev/null || printf '/tmp/p07-color-demo.%s' "$")"
  cat >"$demo" <<'EOF'
SHA256 单核           : 236.0 MB/s
4K 同步写 IOPS       : 512
fsync P95 延迟       : 1.86 ms
CPU 争抢（Steal）（负载）    : 0.50%
资源限制信号         : NORMAL
EOF
  print_value_verdict "$demo"
  rm -f "$demo"
}

if [[ "${1:-}" == "--color-demo" ]]; then
  color_demo
  exit $?
fi

self_test(){
  local r
  r="$(classify_values 236 512 1.86 0.5 1973 1 NORMAL)"
  case "$r" in 偏弱\|偏弱\|良好\|能用，但后台和动态页面响应会偏慢*) ;; *) printf 'DO 类测试样例失败：%s\n' "$r" >&2; return 1 ;; esac

  r="$(classify_values 1479 1363 0.59 0 961 1 NORMAL)"
  case "$r" in 良好\|强\|强\|CPU/I/O\ 可以，但内存不足*) ;; *) printf 'Linode 类测试样例失败：%s\n' "$r" >&2; return 1 ;; esac

  r="$(classify_values 700 850 3 1 4096 2 NORMAL)"
  case "$r" in 良好\|良好\|良好\|适合*) ;; *) printf '平衡型测试样例失败：%s\n' "$r" >&2; return 1 ;; esac

  local ref
  ref="$(NO_COLOR=1 bash "$0" --reference 2>/dev/null || true)"
  grep -Fq '强      >= 900 MB/s' <<<"$ref" || { printf 'CPU 参考线自检失败\n' >&2; return 1; }
  grep -Fq '>= 1000 IOPS' <<<"$ref" || { printf 'I/O 参考线自检失败\n' >&2; return 1; }
  grep -Fq '正常    <= 2%' <<<"$ref" || { printf 'CPU 争抢参考线自检失败\n' >&2; return 1; }
  grep -Fq '>= 1800 MiB' <<<"$ref" || { printf '内存参考线自检失败\n' >&2; return 1; }

  printf 'P07_VPS_VALUE_VERDICT_SELF_TEST=PASS\n'
}

if [[ "${1:-}" == "--self-test" ]]; then
  self_test
  exit $?
fi


if [[ "$AUDIT_QUICK" == 1 ]]; then
  QUICK="$(mktemp -t p07-quick.XXXXXX)" || exit 3
  trap 'rm -f -- "$QUICK"' EXIT
  if ! fetch "https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/3d05e25adca486085362782c26758014b8f04bcf/experiments/p07-vps-audit-v225-r1.sh" "$QUICK"; then
    printf '快速验机模块无法下载。\n' >&2; exit 4
  fi
  if [[ "$(sha256_file "$QUICK" 2>/dev/null || true)" != '3748b3b5b85527c57f23ff563bb926f96d0ac002a326a53f3459ff77d365048a' ]]; then
    printf '快速验机模块完整性校验失败。\n' >&2; exit 5
  fi
  bash "$QUICK"
  exit $?
fi


TMP="$(mktemp -d -t p07-full.XXXXXX)" || exit 3
BASE="$TMP/v21.sh"
OUT="$TMP/full-output.txt"
PLAIN="$TMP/full-plain.txt"
heartbeat_pid=''
cleanup_full(){
  if [[ -n "$heartbeat_pid" ]]; then
    kill "$heartbeat_pid" 2>/dev/null || true
    wait "$heartbeat_pid" 2>/dev/null || true
  fi
  rm -rf -- "$TMP"
}
trap cleanup_full EXIT
trap 'printf "\n用户已取消完整验机，正在结束测试并清理临时文件。\n" >&2; exit 130' INT
trap 'printf "\n完整验机收到停止信号，正在清理。\n" >&2; exit 143' TERM

if ! command -v timeout >/dev/null 2>&1; then
  printf '缺少安全超时工具，已停止，避免启动无法限制时长的测速。\n' >&2
  exit 5
fi
if ! fetch "$BASE_URL" "$BASE"; then
  printf '完整验机基础模块下载失败，未开始测速。\n' >&2
  exit 4
fi
if [[ "$(sha256_file "$BASE" 2>/dev/null || true)" != "$BASE_SHA256" ]]; then
  printf '完整验机基础模块校验失败，已停止。\n' >&2
  exit 5
fi
base_version="$(NO_COLOR=1 bash "$BASE" --version 2>/dev/null | awk '{print $NF}' || true)"
base_build="$(NO_COLOR=1 bash "$BASE" --build-id 2>/dev/null || true)"
if [[ "$base_version" != "$BASE_VERSION" || "$base_build" != "$BASE_BUILD" ]]; then
  printf '完整验机基础模块版本身份不匹配，已停止。\n' >&2
  exit 6
fi

# The original base prints the machine configuration first, followed by the real tests.
printf '服务器性能检测 %s · 完整版\n' "$VERSION"
printf '服务器配置 → CPU / 磁盘 → 全球测速 / 大陆测速 → 增强磁盘 / 三网回程 → 综合报告\n'
printf '以下是实时测试内容，整体最长 12 分钟；如果安静超过 20 秒才提示一次进度。\n\n'
: >"$OUT"

heartbeat(){
  local last_size=-1 quiet=0 current_size
  while sleep 10; do
    current_size="$(wc -c <"$OUT" 2>/dev/null || printf 0)"
    if [[ "$current_size" == "$last_size" ]]; then
      quiet=$((quiet+10))
    else
      quiet=0
    fi
    last_size="$current_size"
    if (( quiet>=20 )); then
      printf '\n[提示] 本项测速仍在运行，已连续约 %s 秒没有新数据；整体有 12 分钟保护上限。\n' "$quiet"
    fi
  done
}
heartbeat &
heartbeat_pid=$!

# Do NOT silence V2.1/V2.0: show the original system inventory before network speed tests.
# Keep original network pools, China region probes, fio modes, route and report behavior.
# Reduce bulk disk writes to 64 MiB per round on a busy production VPS.
P07_BENCH_IO_MIB=64 P07_FIO_TEST_MIB=64 P07_FIO_TIMEOUT_SEC=20 P07_ROUTE_TIMEOUT_SEC=25 \
  NO_COLOR=1 timeout --signal=TERM --kill-after=5s 720s bash "$BASE" 2>&1 | tee "$OUT"
rc=$?
kill "$heartbeat_pid" 2>/dev/null || true
wait "$heartbeat_pid" 2>/dev/null || true
heartbeat_pid=''

strip_terminal_codes <"$OUT" >"$PLAIN"
if (( rc!=0 )); then
  printf '\n完整测试未结束（中断、网络异常或超时），以上保留已完成的真实测试结果。\n' >&2
  if (( rc==124 || rc==137 )); then printf '已达到 12 分钟安全上限并停止，不会无限卡住。\n' >&2; fi
  printf '不输出虚假的最终评级，可稍后重新检测。\n' >&2
  exit 12
fi
if ! grep -Eq '^[[:space:]]*SHA256 单核[[:space:]]*:[[:space:]]*[0-9]' "$PLAIN" ||
   ! grep -Eq '^[[:space:]]*4K 同步写 IOPS[[:space:]]*:[[:space:]]*[0-9]' "$PLAIN"; then
  printf '\n基础 CPU 或磁盘证据不足，不能判定完整验机 PASS。\n' >&2
  exit 12
fi
printf '\n服务器用途总结（基于上述实际数据）：\n'
print_value_verdict "$PLAIN"
printf '\n完整验机结束：配置、全球/大陆测速、增强磁盘和三网回程信息均已实时显示；报告见上方原始输出。\n'
