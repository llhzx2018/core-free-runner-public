#!/usr/bin/env bash
set -uo pipefail

APP="P07 VPS 一键验机"
VERSION="V2.1.0"
BUILD_ID="2.1.0-rc6-lowload"

BASE_EXPECTED="2.0.0-rc4-zh"
BASE_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/1197372f0b32b7cc9a8b35736c30563cb36633c9/experiments/p07-vps-audit-v20-rc4.sh"
BASE_SHA256="54325e92bdf78a90c74b5fed73be9d0633b402659fdfa2848dc751ff23efaecd"

YABS_COMMIT="f8c6a48cd6ff85b54c5cd2504f0807462dc58938"
FIO_X64_SHA256="b511bda3b26b6d840698f543d63e956d7466b8512c10ff0ada8292d556c33fb1"
FIO_AARCH64_SHA256="e2942a26d4b249076486677c9c12cd7f1a572854a5e136597d1391e8ad75ffb0"
FIO_TEST_MIB="${P07_FIO_TEST_MIB:-64}"
FIO_TIMEOUT_SEC="${P07_FIO_TIMEOUT_SEC:-25}"
BENCH_DIR="${P07_BENCH_DIR:-/var/tmp}"
ROUTE_TIMEOUT_SEC="${P07_ROUTE_TIMEOUT_SEC:-25}"

case "${1:-}" in
  --version|-V) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
  --build-id) printf '%s\n' "$BUILD_ID"; exit 0 ;;
  --help|-h)
    cat <<'EOF'
P07 VPS 一键验机 V2.1.0

自动完成：
- V2.0.0 全部基础验机
- 低负载 4K / 64K / 512K / 1M 混合随机磁盘测试
- 中国电信 / 联通 / 移动三网回程识别（环境支持时）
- 本地 Markdown 增强报告

安全边界：
- 不自动 apt/yum 安装软件
- 不上传报告到第三方
- fio 采用 64 MiB 有界文件、低队列深度、低调度优先级
- 三网回程不支持 raw socket 时自动跳过，不影响其它验机
EOF
    exit 0 ;;
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
  elif command -v wget >/dev/null 2>&1; then wget -q --https-only --timeout=90 --tries=2 -O "$out"
  else return 127
  fi
}

TMP="$(mktemp -d -t p07-v21.XXXXXX 2>/dev/null || printf '/tmp/p07-v21.%s' "$$")"
mkdir -p "$TMP" 2>/dev/null || exit 3
cleanup(){ rm -rf "$TMP" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

if [[ -n "${P07_REPORT_DIR:-}" ]]; then
  REPORT_DIR="$P07_REPORT_DIR"
elif [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  REPORT_DIR="/var/lib/p07-bench/reports"
else
  REPORT_DIR="${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/p07-bench/reports"
fi
mkdir -p "$REPORT_DIR" 2>/dev/null || REPORT_DIR="/tmp/p07-bench-reports"
mkdir -p "$REPORT_DIR" 2>/dev/null || true
STAMP="$(date +%Y%m%d_%H%M%S)"
START_EPOCH="$(date +%s)"
FIO_TSV="$TMP/fio.tsv"; : >"$FIO_TSV"
ROUTE_TSV="$TMP/route.tsv"; : >"$ROUTE_TSV"
FIO_VERDICT="未执行"
ROUTE_VERDICT="未执行"

run_base(){
  [[ "${P07_V21_SKIP_BASE:-0}" == 1 ]] && return 0
  local base="$TMP/base.sh" got version rc
  if ! fetch "$BASE_URL" "$base"; then printf '%s基础验机模块下载失败。%s\n' "$RED" "$RESET" >&2; return 4; fi
  got="$(sha256_file "$base" 2>/dev/null || true)"
  if [[ "$got" != "$BASE_SHA256" ]]; then printf '%s基础验机模块完整性校验失败，已停止。%s\n' "$RED" "$RESET" >&2; return 5; fi
  version="$(NO_COLOR=1 bash "$base" --version 2>/dev/null | awk '{print $NF}' || true)"
  if [[ "$version" != "$BASE_EXPECTED" ]]; then printf '%s基础验机模块版本不匹配，已停止。%s\n' "$RED" "$RESET" >&2; return 6; fi
  set +e
  bash "$base"
  rc=$?
  set -e 2>/dev/null || true
  return "$rc"
}

fio_arch(){
  case "$(uname -m 2>/dev/null || true)" in
    x86_64|amd64) printf 'x64|%s' "$FIO_X64_SHA256" ;;
    aarch64|arm64|armv8|armv8l) printf 'aarch64|%s' "$FIO_AARCH64_SHA256" ;;
    *) return 1 ;;
  esac
}
prepare_fio(){
  if command -v fio >/dev/null 2>&1 && fio --version 2>/dev/null | grep -Eq '^fio-[0-9]'; then
    FIO_BIN="$(command -v fio)"; FIO_SOURCE="系统现有 fio"; return 0
  fi
  command -v python3 >/dev/null 2>&1 || return 1
  local pair arch sha url got out
  pair="$(fio_arch 2>/dev/null || true)"; [[ -n "$pair" ]] || return 1
  IFS='|' read -r arch sha <<<"$pair"
  out="$TMP/fio"
  url="https://raw.githubusercontent.com/masonr/yet-another-bench-script/${YABS_COMMIT}/bin/fio/fio_${arch}"
  fetch "$url" "$out" || return 1
  got="$(sha256_file "$out" 2>/dev/null || true)"
  [[ "$got" == "$sha" ]] || return 1
  chmod 700 "$out"
  "$out" --version >/dev/null 2>&1 || return 1
  FIO_BIN="$out"; FIO_SOURCE="校验版 fio 3.39（临时）"
}
fio_qd(){
  case "$1" in
    4k) printf '4' ;;
    64k|512k) printf '2' ;;
    1m) printf '1' ;;
    *) printf '1' ;;
  esac
}
fio_preflight(){
  [[ "${P07_V21_SKIP_FIO:-0}" == 1 ]] && return 1
  [[ "$FIO_TEST_MIB" =~ ^[0-9]+$ ]] || return 1
  (( FIO_TEST_MIB >= 32 && FIO_TEST_MIB <= 128 )) || return 1
  [[ "$FIO_TIMEOUT_SEC" =~ ^[0-9]+$ ]] || return 1
  (( FIO_TIMEOUT_SEC >= 10 && FIO_TIMEOUT_SEC <= 60 )) || return 1
  [[ -d "$BENCH_DIR" && -w "$BENCH_DIR" ]] || return 1
  local fs free mem_avail cores load1 limit
  fs="$(df -PT "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $2}')"
  [[ "$fs" != tmpfs && "$fs" != devtmpfs ]] || return 1
  free="$(df -Pm "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $4}')"
  [[ "$free" =~ ^[0-9]+$ ]] && (( free >= FIO_TEST_MIB + 192 )) || return 1
  mem_avail="$(awk '/MemAvailable:/{print int($2/1024)}' /proc/meminfo 2>/dev/null || true)"
  [[ "$mem_avail" =~ ^[0-9]+$ ]] && (( mem_avail >= 192 )) || return 1
  cores="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)"; [[ "$cores" =~ ^[0-9]+$ ]] || cores=1
  load1="$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo 0)"
  limit="$(awk -v c="$cores" 'BEGIN{printf "%.2f", c*2.5}')"
  awk -v l="$load1" -v m="$limit" 'BEGIN{exit !(l<=m)}'
}
run_fio_row(){
  local bs="$1" qd file json result rc=0
  qd="$(fio_qd "$bs")"
  file="$BENCH_DIR/.p07-fio-$$-${bs}.bin"; json="$TMP/fio-${bs}.json"
  rm -f "$file" "$json"
  local -a cmd=("$FIO_BIN" --name="p07-${bs}" --filename="$file" --size="${FIO_TEST_MIB}M" --rw=randrw --rwmixread=50 --bs="$bs" --ioengine=libaio --direct=1 --iodepth="$qd" --numjobs=1 --group_reporting=1 --randrepeat=1 --eta=never --output-format=json --output="$json")
  if command -v ionice >/dev/null 2>&1; then cmd=(ionice -c2 -n7 "${cmd[@]}"); fi
  if command -v nice >/dev/null 2>&1; then cmd=(nice -n 10 "${cmd[@]}"); fi
  set +e
  if command -v timeout >/dev/null 2>&1; then timeout "${FIO_TIMEOUT_SEC}s" "${cmd[@]}" >/dev/null 2>&1; rc=$?
  else "${cmd[@]}" >/dev/null 2>&1; rc=$?; fi
  set -e 2>/dev/null || true
  rm -f "$file"
  (( rc == 0 )) || return "$rc"
  result="$(python3 - "$json" 2>/dev/null <<'PY' || true
import json,sys
try:
    j=json.load(open(sys.argv[1],encoding='utf-8'))['jobs'][0]
    r,w=j['read'],j['write']
    print(f"{r['bw_bytes']/1048576:.2f}|{r['iops']:.1f}|{w['bw_bytes']/1048576:.2f}|{w['iops']:.1f}")
except Exception:
    pass
PY
)"
  [[ -n "$result" ]] || return 1
  printf '%s\t%s\t%s\n' "$bs" "$qd" "$result" >>"$FIO_TSV"
}
assess_fio(){
  local row ri wi rb wb min_iops min_mb
  row="$(awk -F '[\t|]' '$1=="4k"{print $4"|"$6}' "$FIO_TSV")"
  if [[ -n "$row" ]]; then
    IFS='|' read -r ri wi <<<"$row"; min_iops="$(awk -v a="$ri" -v b="$wi" 'BEGIN{print (a<b?a:b)}')"
    if awk -v n="$min_iops" 'BEGIN{exit !(n>=3000)}'; then FIO_SMALL="良好"
    elif awk -v n="$min_iops" 'BEGIN{exit !(n>=800)}'; then FIO_SMALL="可用"
    else FIO_SMALL="偏弱"; fi
  else FIO_SMALL="未知"; fi
  row="$(awk -F '[\t|]' '$1=="1m"{print $3"|"$5}' "$FIO_TSV")"
  if [[ -n "$row" ]]; then
    IFS='|' read -r rb wb <<<"$row"; min_mb="$(awk -v a="$rb" -v b="$wb" 'BEGIN{print (a<b?a:b)}')"
    if awk -v n="$min_mb" 'BEGIN{exit !(n>=200)}'; then FIO_LARGE="良好"
    elif awk -v n="$min_mb" 'BEGIN{exit !(n>=60)}'; then FIO_LARGE="可用"
    else FIO_LARGE="偏弱"; fi
  else FIO_LARGE="未知"; fi
  if [[ "$FIO_SMALL" == 良好 && "$FIO_LARGE" == 良好 ]]; then FIO_VERDICT="良好"
  elif [[ "$FIO_SMALL" == 偏弱 || "$FIO_LARGE" == 偏弱 ]]; then FIO_VERDICT="需观察"
  elif [[ "$FIO_SMALL" != 未知 || "$FIO_LARGE" != 未知 ]]; then FIO_VERDICT="可用"
  else FIO_VERDICT="证据不足"; fi
}
print_fio(){
  rule
  printf '%s%s 增强磁盘低负载测试%s\n' "$BOLD" "$CYAN" "$RESET"
  printf ' %s64 MiB 有界文件；低队列深度；nice/ionice 降低对在线业务影响。%s\n' "$GRAY" "$RESET"
  if ! fio_preflight; then printf ' %s当前负载/内存/磁盘空间不满足安全条件，已自动跳过。%s\n' "$YELLOW" "$RESET"; FIO_VERDICT="未执行"; return 0; fi
  if ! prepare_fio; then printf ' %sfio 不可安全使用，已自动跳过。%s\n' "$YELLOW" "$RESET"; FIO_VERDICT="未执行"; return 0; fi
  printf ' 测试引擎           : %s\n' "$FIO_SOURCE"
  printf ' %-8s %-6s %-15s %-12s %-15s %-12s\n' '块大小' 'QD' '随机读取' '读IOPS' '随机写入' '写IOPS'
  local bs qd row rb ri wb wi rc pass=0
  for bs in 4k 64k 512k 1m; do
    set +e; run_fio_row "$bs"; rc=$?; set -e 2>/dev/null || true
    if (( rc == 0 )); then
      row="$(tail -n1 "$FIO_TSV")"; IFS=$'\t|' read -r _ qd rb ri wb wi <<<"$row"
      printf ' %-8s %-6s %-15s %-12s %-15s %-12s\n' "$bs" "$qd" "${rb} MB/s" "$ri" "${wb} MB/s" "$wi"
      pass=$((pass+1))
    else
      printf ' %-8s %-6s %s\n' "$bs" "$(fio_qd "$bs")" '已停止（超时/不支持）'
      break
    fi
  done
  assess_fio
  printf ' 有效档位           : %s / 4\n' "$pass"
  printf ' 小文件/数据库      : %s\n' "$FIO_SMALL"
  printf ' 大块混合吞吐       : %s\n' "$FIO_LARGE"
  printf ' 增强磁盘判断       : %s\n' "$FIO_VERDICT"
}

route_mock(){
  cat >"$ROUTE_TSV" <<'EOF'
北京电信	电信CN2	优质
北京联通	联通4837	普通
北京移动	移动CMI	普通
上海电信	电信163	普通
上海联通	联通9929	优质
上海移动	移动CMIN2	优质
广州电信	电信CN2	优质
广州联通	联通4837	普通
广州移动	移动CMI	普通
成都电信	电信163	普通
成都联通	联通9929	优质
成都移动	移动CMIN2	优质
EOF
}
run_three_carrier_route(){
  [[ "${P07_V21_SKIP_ROUTE:-0}" == 1 ]] && { ROUTE_VERDICT="未执行"; return 0; }
  if [[ "${P07_ROUTE_MOCK:-0}" == 1 ]]; then route_mock; return 0; fi
  command -v python3 >/dev/null 2>&1 || { ROUTE_VERDICT="环境不支持"; return 0; }
  set +e
  timeout "${ROUTE_TIMEOUT_SEC}s" python3 - "$ROUTE_TSV" <<'PY'
import socket,sys
out=sys.argv[1]
targets=[
('北京电信','219.141.140.10'),('北京联通','202.106.195.68'),('北京移动','221.179.155.161'),
('上海电信','202.96.209.133'),('上海联通','210.22.97.1'),('上海移动','211.136.112.200'),
('广州电信','58.60.188.222'),('广州联通','210.21.196.6'),('广州移动','120.196.165.24'),
('成都电信','61.139.2.69'),('成都联通','119.6.6.6'),('成都移动','211.137.96.205')]
def classify(ip):
    if ip.startswith('59.43.'): return ('电信CN2','优质')
    if ip.startswith('202.97.'): return ('电信163','普通')
    if ip.startswith('218.105.') or ip.startswith('210.51.'): return ('联通9929','优质')
    if ip.startswith('219.158.'): return ('联通4837','普通')
    if ip.startswith(('223.120.19.','223.120.17.','223.120.16.')): return ('移动CMIN2','优质')
    if ip.startswith(('223.118.','223.119.','223.120.','223.121.')): return ('移动CMI','普通')
    return None
try:
    test=socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_ICMP); test.close()
except Exception:
    sys.exit(77)
rows=[]
for name,dst in targets:
    found=None
    try:
        recv=socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_ICMP); recv.settimeout(0.12)
        send=socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        for ttl in range(1,13):
            send.setsockopt(socket.SOL_IP,socket.IP_TTL,ttl)
            try: send.sendto(b'p07',(dst,33434+ttl))
            except OSError: continue
            try:
                _,addr=recv.recvfrom(2048); hop=addr[0]
            except socket.timeout:
                continue
            c=classify(hop)
            if c:
                found=c; break
        recv.close(); send.close()
    except Exception:
        found=None
    if found: rows.append((name,found[0],found[1]))
with open(out,'w',encoding='utf-8') as f:
    for r in rows: f.write('\t'.join(r)+'\n')
sys.exit(0 if rows else 78)
PY
  rc=$?
  set -e 2>/dev/null || true
  if (( rc == 77 )); then ROUTE_VERDICT="环境不支持"; : >"$ROUTE_TSV"; return 0; fi
  if (( rc != 0 )); then ROUTE_VERDICT="证据不足"; : >"$ROUTE_TSV"; return 0; fi
}
print_three_carrier_route(){
  rule
  printf '%s%s 中国三网回程%s\n' "$BOLD" "$CYAN" "$RESET"
  printf ' %s只读短探测；识别电信 CN2/163、联通 9929/4837、移动 CMIN2/CMI。%s\n' "$GRAY" "$RESET"
  run_three_carrier_route
  local n
  n="$(wc -l <"$ROUTE_TSV" 2>/dev/null | tr -d ' ')"; [[ "$n" =~ ^[0-9]+$ ]] || n=0
  if (( n == 0 )); then
    printf ' %s当前内核/权限未取得可靠三网回程证据，已安全跳过，不影响其它验机结果。%s\n' "$YELLOW" "$RESET"
    return 0
  fi
  printf ' %-12s %-16s %-8s\n' '地区/运营商' '回程线路' '等级'
  while IFS=$'\t' read -r name route grade; do
    printf ' %-12s %-16s %-8s\n' "$name" "$route" "$grade"
  done <"$ROUTE_TSV"
  local good total
  total="$n"; good="$(awk -F '\t' '$3=="优质"{n++} END{print n+0}' "$ROUTE_TSV")"
  if (( total >= 9 )); then ROUTE_VERDICT="有效 ${total}/12，优质 ${good}/${total}"
  else ROUTE_VERDICT="部分有效 ${total}/12，优质 ${good}/${total}"; fi
  printf ' 三网回程证据       : %s\n' "$ROUTE_VERDICT"
}

write_markdown(){
  local md="$REPORT_DIR/p07-vps-audit-v21_${STAMP}.md"
  {
    printf '# P07 VPS 一键验机增强报告\n\n'
    printf -- '- 版本：`%s`\n' "$VERSION"
    printf -- '- 时间：`%s`\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
    printf -- '- 说明：仅保存本机，不自动上传第三方。\n\n'
    printf '## 增强磁盘低负载测试\n\n'
    printf '| 块大小 | QD | 随机读取 MB/s | 读 IOPS | 随机写入 MB/s | 写 IOPS |\n|---|---:|---:|---:|---:|---:|\n'
    while IFS=$'\t|' read -r bs qd rb ri wb wi; do [[ -n "$bs" ]] && printf '| %s | %s | %s | %s | %s | %s |\n' "$bs" "$qd" "$rb" "$ri" "$wb" "$wi"; done <"$FIO_TSV"
    printf '\n- 增强磁盘判断：**%s**\n' "$FIO_VERDICT"
    printf '\n## 中国三网回程\n\n'
    if [[ -s "$ROUTE_TSV" ]]; then
      printf '| 地区/运营商 | 回程线路 | 等级 |\n|---|---|---|\n'
      while IFS=$'\t' read -r name route grade; do printf '| %s | %s | %s |\n' "$name" "$route" "$grade"; done <"$ROUTE_TSV"
    else
      printf '当前环境未取得可靠回程证据。\n'
    fi
    printf '\n- 三网回程证据：**%s**\n' "$ROUTE_VERDICT"
  } >"$md"
  printf ' 增强 Markdown 报告 : %s\n' "$md"
}

printf '%s%s P07 VPS 一键验机 %s%s\n' "$BOLD" "$CYAN" "$VERSION" "$RESET"
set +e
run_base
base_rc=$?
set -e 2>/dev/null || true
if (( base_rc != 0 )); then printf '%s基础验机未正常完成，增强测试不继续。%s\n' "$RED" "$RESET" >&2; exit "$base_rc"; fi

print_fio
print_three_carrier_route
write_markdown
end_epoch="$(date +%s)"
rule
printf '%s%s V2.1.0 增强项结论%s\n' "$BOLD" "$CYAN" "$RESET"
printf ' 增强磁盘           : %s\n' "$FIO_VERDICT"
printf ' 中国三网回程       : %s\n' "$ROUTE_VERDICT"
printf ' 增强项耗时         : %s 秒\n' "$((end_epoch-START_EPOCH))"
printf ' 说明               : 本版本在 V2.0.0 基础上增加低负载 fio 与三网回程；任一增强项失败都不会拖住整套验机。\n'
