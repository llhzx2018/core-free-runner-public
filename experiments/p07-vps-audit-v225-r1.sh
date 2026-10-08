#!/usr/bin/env bash
set -uo pipefail

APP="P07 VPS 一键验机"
VERSION="V2.2.5"
BUILD_ID="2.2.5-rc1-bounded-quick"

BASE_VERSION="V2.1.0"
BASE_BUILD="2.1.0-rc7-field"
BASE_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/0a851b9fe1819c7970ed5bb8e3633f2fc8e73166/experiments/p07-vps-audit-v21.sh"
BASE_SHA256="d1846e751bba5c860c623e3db26641908e27ca43b39cf37016758853b65a952d"

case "${1:-}" in
  --version|-V) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
  --build-id) printf '%s\n' "$BUILD_ID"; exit 0 ;;
  --help|-h)
    cat <<'EOF'
P07 VPS 一键验机 V2.2.5

默认运行低负载、有超时的 CPU、4K 同步写与 CPU 争抢快速检测：
- CPU 最长 12 秒；磁盘最长 15 秒、最多写入 256 KiB；完成自动删除。
- 每步独立显示进度，终端不再长时间停在同一句提示。
- 高负载、内存不足或磁盘空间不足时安全跳过，不虚构性能结论。
- 不做公网测速、三网回程、多轮磁盘大文件压力测试。
- 支持 --reference 查看判定基线、--self-test 运行不写盘分类测试。
- 基于快速抽样做用途判断，不当作行业 VPS 排名或价格评估。
EOF
    exit 0
    ;;
  --reference)
    cat <<'EOF'
P07 VPS 一键验机 V2.2.5 · 判定参考线

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
  elif [[ "$cc" == 证据不足 || "$dc" == 证据不足 || "$sc" == 证据不足 ]]; then
    machine="证据不足"
    keep="请稍后重新检测"
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
    cloud="本次数据不足，暂不判断"
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


TMP="$(mktemp -d -t p07-quick.XXXXXX)" || { printf '无法准备安全临时区，本次检查取消。\n' >&2; exit 3; }
trap 'rm -rf -- "$TMP"' EXIT
PLAIN="$TMP/probe.txt"
: >"$PLAIN"
printf '%s%s 服务器性能检测 %s%s\n' "$BOLD" "$CYAN" "$VERSION" "$RESET"
printf '安全快速检测：CPU / 4K 同步写 / CPU 争抢；不进行公网测速或重负载写盘。\n'
if ! command -v timeout >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  printf '缺少安全超时工具或 Python3，本次检查已停止。\n' >&2
  exit 5
fi
CORES="$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf '1')"
[[ "$CORES" =~ ^[1-9][0-9]*$ ]] || CORES=1
LOAD="$(awk '{print $1}' /proc/loadavg 2>/dev/null || printf '0')"
if awk -v l="$LOAD" -v n="$CORES" 'BEGIN{exit !(l > n*2)}'; then
  printf '当前机器正忙（1 分钟平均负载 %s，CPU %s 核）；为保护线上网站，已跳过性能测试。\n' "$LOAD" "$CORES"
  printf '不是机器性能不合格；待服务器空闲时重新进入菜单 2 即可。\n'
  exit 12
fi
printf '\n[1/3] CPU 轻量测试 · 最长 12 秒...\n'
cpu='未知'
if command -v openssl >/dev/null 2>&1; then
  cpu_text="$(timeout --signal=TERM --kill-after=2s 12s openssl speed -seconds 1 -evp sha256 2>/dev/null)"
  cpu_rc=$?
  if [[ "$cpu_rc" -eq 0 ]]; then
    cpu="$(printf '%s\n' "$cpu_text" | awk '$1=="sha256"{x=$NF;gsub(/k$/,"",x);if(x~/^[0-9]+([.][0-9]+)?$/){printf "%.1f",x/1024;exit}}')"
    [[ -n "$cpu" ]] || cpu='未知'
  fi
fi
printf 'SHA256 单核           : %s MB/s\n' "$cpu" >>"$PLAIN"
[[ "$cpu" == 未知 ]] && printf 'CPU 测试没有取得有效结果。\n' || printf 'CPU 测试完成。\n'
printf '\n[2/3] 磁盘 4K 同步写 · 最多 256 KiB · 最长 15 秒...\n'
disk_dir="$(printenv P07_BENCH_DIR 2>/dev/null || printf '/var/tmp')"
PROBE_FILE=''
if [[ -d "$disk_dir" && -w "$disk_dir" ]]; then
  PROBE_FILE="$(mktemp -p "$disk_dir" .p07-quick.XXXXXX 2>/dev/null || true)"
fi
trap '[[ -z "$PROBE_FILE" ]] || rm -f -- "$PROBE_FILE"; rm -rf -- "$TMP"' EXIT
if [[ -z "$PROBE_FILE" ]]; then
  printf '无法安全创建小型测试文件，磁盘项目跳过。\n'
  disk_result='SKIP|临时文件不可用'; disk_rc=12
else
  disk_result="$(timeout --signal=TERM --kill-after=2s 15s python3 - "$PROBE_FILE" <<'PY'
import os,sys,time,tempfile
path=sys.argv[1]
try:
    v=os.statvfs(path)
    if v.f_bavail*v.f_frsize < 128*1024*1024:
        print("SKIP|磁盘空间不足");sys.exit(0)
    with open('/proc/meminfo',encoding='ascii') as f:
        mem=next((int(x.split()[1]) for x in f if x.startswith('MemAvailable:')),0)
    if mem < 256*1024:
        print("SKIP|可用内存不足");sys.exit(0)
    fd=os.open(path,os.O_WRONLY|os.O_TRUNC)
    times=[]
    try:
        data=b'\0'*4096
        for i in range(64):
            start=time.monotonic()
            os.write(fd,data)
            os.fsync(fd)
            times.append((time.monotonic()-start)*1000)
            if sum(times)>8000:break
    finally:
        os.close(fd)
    if times:
        t=sorted(times)
        p95=t[max(0,min(len(t)-1,int(len(t)*0.95)-1))]
        print(f'PASS|{len(t)*1000/sum(t):.0f}|{p95:.2f}')
    else:
        print('SKIP|磁盘无有效读数')
except (OSError,ValueError,StopIteration):
    print('SKIP|磁盘检测不可安全执行')
PY
)"
disk_rc=$?
fi
[[ -z "$PROBE_FILE" ]] || rm -f -- "$PROBE_FILE"
PROBE_FILE=''
iops='未知';fsync='未知'
if [[ "$disk_rc" -eq 0 && "$disk_result" == PASS\|* ]]; then
  IFS='|' read -r _ iops fsync <<<"$disk_result"
  printf '磁盘抽样完成，临时数据已删除。\n'
else
  printf '磁盘检测已安全跳过或超时，不进行猜测评分。\n'
fi
printf '4K 同步写 IOPS       : %s\n' "$iops" >>"$PLAIN"
printf 'fsync P95 延迟      : %s ms\n' "$fsync" >>"$PLAIN"
printf '\n[3/3] CPU 争抢与系统容量 · 最长 4 秒...\n'
steal="$(timeout --signal=TERM --kill-after=2s 4s python3 - <<'PY'
import time
def read():
    with open('/proc/stat',encoding='ascii') as f:v=list(map(int,f.readline().split()[1:]))
    return sum(v),v[7] if len(v)>7 else 0
try:
    a,b=read();time.sleep(.25);c,d=read()
    print(f'{100*(d-b)/(c-a):.2f}' if c>a else '未知')
except (OSError,ValueError,IndexError):
    print('未知')
PY
)" || steal='未知'
printf 'CPU 争抢（Steal）（负载） : %s%%\n' "$steal" >>"$PLAIN"
printf '资源限制信号          : UNKNOWN\n' >>"$PLAIN"
printf '\n'
print_value_verdict "$PLAIN"
if [[ "$cpu" == 未知 || "$iops" == 未知 || "$fsync" == 未知 || "$steal" == 未知 ]]; then
  printf '本次数据不完整，没有给出硬件合格结论；未修改系统配置。\n'
  exit 12
fi
printf '检测结束：未修改网站配置或服务，临时测试文件已删除。\n'
