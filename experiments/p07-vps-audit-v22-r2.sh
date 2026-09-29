#!/usr/bin/env bash
set -uo pipefail

APP="P07 VPS 一键验机"
VERSION="V2.2.2"
BUILD_ID="2.2.2-rc2-chinese-first"

BASE_VERSION="V2.1.0"
BASE_BUILD="2.1.0-rc7-field"
BASE_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/0a851b9fe1819c7970ed5bb8e3633f2fc8e73166/experiments/p07-vps-audit-v21.sh"
BASE_SHA256="d1846e751bba5c860c623e3db26641908e27ca43b39cf37016758853b65a952d"

case "${1:-}" in
  --version|-V) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
  --build-id) printf '%s\n' "$BUILD_ID"; exit 0 ;;
  --help|-h)
    cat <<'EOF'
P07 VPS 一键验机 V2.2.2

在 V2.1.0 完整验机基础上增加“使用价值判断”：
- 不需要另一台 VPS 做对比
- 直接判断 CPU / 数据库型 I/O / 宿主机争抢 / 内存是否存在明显短板
- 给出 CloudPanel / WordPress / 轻量工具站 / 数据库型负载的用途结论
- 明确区分“机器性能”与“性价比”；没有月费证据时不伪造性价比结论
- 输出主要短板和保留建议
- 直接显示 CPU / I/O / CPU 争抢（Steal） / CloudPanel 内存判定参考线
- 支持 --reference 单独查看当前 P07 判定基线
- 恢复终端彩色分区，并用绿色 / 黄色 / 红色表达正常、注意和风险

判断是 P07 的工作负载阈值，不是全网 VPS 排名，也不是商家宣传评分。
EOF
    exit 0
    ;;
  --reference)
    cat <<'EOF'
P07 VPS 一键验机 V2.2.2 · 判定参考线

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
  printf '%s%s P07 使用价值判断%s\n' "$BOLD" "$CYAN" "$RESET"
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
  printf '%s%s判定参考线%s\n' "$BOLD" "$CYAN" "$RESET"
  printf ' 单核 CPU（SHA256） : %s强 >=900%s ｜ %s良好 >=500%s ｜ %s可用 >=250%s ｜ %s偏弱 >=150%s ｜ %s很弱 <150%s MB/s\n' "$GREEN" "$RESET" "$GREEN" "$RESET" "$YELLOW" "$RESET" "$RED" "$RESET" "$RED" "$RESET"
  printf ' 数据库型 I/O       : %s强 >=1000 IOPS + <=2.5ms%s ｜ %s良好 >=500 + <=5ms%s ｜ %s可用 >=300 + <=10ms%s ｜ %s其它偏弱%s\n' "$GREEN" "$RESET" "$GREEN" "$RESET" "$YELLOW" "$RESET" "$RED" "$RESET"
  printf ' CPU 争抢（Steal）          : %s正常 <=2%%%s ｜ %s可接受 <=5%%%s ｜ %s需观察 <=10%%%s ｜ %s异常 >10%%%s\n' "$GREEN" "$RESET" "$YELLOW" "$RESET" "$YELLOW" "$RESET" "$RED" "$RESET"
  printf ' CloudPanel 内存    : %s>=1800 MiB%s 视为 2GB 级；%s低于此值%s标记内存短板\n' "$GREEN" "$RESET" "$YELLOW" "$RESET"
  printf ' CPU 核数           : %s1 vCPU%s 标记并发上限；%s>=2 vCPU%s 不触发该短板\n' "$YELLOW" "$RESET" "$GREEN" "$RESET"
  printf ' 参考线用途         : %sCloudPanel / WordPress / PHP / MySQL / 小工具站，不代表行业统一排名%s\n' "$GRAY" "$RESET"
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

TMP="$(mktemp -d -t p07-v22.XXXXXX 2>/dev/null || printf '/tmp/p07-v22.%s' "$$")"
mkdir -p "$TMP" 2>/dev/null || exit 3
cleanup(){ rm -rf "$TMP" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

BASE="$TMP/v21.sh"
OUT="$TMP/v21-output.txt"
PLAIN="$TMP/v21-plain.txt"

if ! fetch "$BASE_URL" "$BASE"; then
  printf '%sV2.1 基础模块下载失败。%s\n' "$RED" "$RESET" >&2
  exit 4
fi
got="$(sha256_file "$BASE" 2>/dev/null || true)"
if [[ "$got" != "$BASE_SHA256" ]]; then
  printf '%sV2.1 基础模块完整性校验失败。%s\n' "$RED" "$RESET" >&2
  exit 5
fi
base_version="$(NO_COLOR=1 bash "$BASE" --version 2>/dev/null | awk '{print $NF}' || true)"
base_build="$(NO_COLOR=1 bash "$BASE" --build-id 2>/dev/null || true)"
if [[ "$base_version" != "$BASE_VERSION" || "$base_build" != "$BASE_BUILD" ]]; then
  printf '%sV2.1 基础模块身份不匹配。%s\n' "$RED" "$RESET" >&2
  exit 6
fi

printf '%s%s P07 VPS 一键验机 %s%s\n' "$BOLD" "$CYAN" "$VERSION" "$RESET"
printf ' %sV2.2.2：恢复彩色分区；强/弱/风险按统一语义色显示，并保留可见参考线。%s\n' "$GRAY" "$RESET"

set +e
if [[ -t 1 && -z "${NO_COLOR:-}" ]] && command -v script >/dev/null 2>&1; then
  # The wrapper captures output for the verdict; a normal pipe disables the base ANSI colors.
  # Use a PTY so the original colored section hierarchy remains visible in a real terminal.
  script -qefc "bash '$BASE'" /dev/null 2>&1 |
    sed -u \
    -e 's/V2\\.1\\.0/V2.2.2/g' \
    -e 's/CPU Steal/CPU 争抢（Steal）/g' \
    -e 's/增强 Markdown 报告/增强报告/g' \
    -e 's/fail-closed/安全失败保护/g' |
    tee "$OUT"
  rc=${PIPESTATUS[0]}
else
  NO_COLOR="${NO_COLOR:-}" bash "$BASE" 2>&1 |
    sed -u 's/V2\.1\.0/V2.2.2/g' |
    tee "$OUT"
  rc=${PIPESTATUS[0]}
fi
set -e 2>/dev/null || true
(( rc == 0 )) || exit "$rc"

strip_terminal_codes <"$OUT" >"$PLAIN"
print_value_verdict "$PLAIN"
