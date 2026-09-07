#!/usr/bin/env bash
set -uo pipefail

APP="P07 VPS 一键验机 2.0"
VERSION="2.0.0-rc4-zh"
BASE_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/e765c5547a4a92972428042c8594f9359346d3e6/experiments/p07-vps-audit-v20-rc3.sh"
BASE_SHA256="53b30d3616d40f8e64780e97486e36227afb5c07b651923f9205f2906c860951"

case "${1:-}" in
  --version|-V) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
  --help|-h)
    cat <<'EOF'
P07 VPS 一键验机 2.0

自动执行完整 VPS 验机，并增加真实中国大陆区域线路参考：
北京 / 上海 / 华南深圳 / 西南重庆。

大陆区域使用真实位于中国大陆的高校/骨干网 HTTPS 镜像节点，
测量大陆节点 → VPS 的有界下载速度和首字节时间。

注意：这不是中国大陆用户 → VPS 的真实入站可达性测试，
也不会把台湾、香港或境外邻近节点冒充中国大陆地区。
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
  if command -v curl >/dev/null 2>&1; then curl -fsSL --connect-timeout 10 --max-time 90 "$url" -o "$out"
  elif command -v wget >/dev/null 2>&1; then wget -q --https-only --timeout=90 -O "$out" "$url"
  else return 127
  fi
}
display_width(){
  local text="$1" w
  w="$(LC_ALL=C.UTF-8 printf '%s\n' "$text" | wc -L 2>/dev/null | tr -d '[:space:]')"
  [[ "$w" =~ ^[0-9]+$ ]] || w=${#text}
  printf '%s' "$w"
}
pad(){
  local text="$1" width="$2" w n
  w="$(display_width "$text")"; n=$((width-w)); ((n<0)) && n=0
  printf '%s' "$text"; printf '%*s' "$n" ''
}
print_header(){
  printf ' %s' "$BOLD$YELLOW"
  pad '大陆区域' 16; printf ' '
  pad '真实节点' 24; printf ' '
  pad '大陆→VPS下载' 17; printf ' '
  pad '首字节' 12; printf ' '
  pad '状态' 8
  printf '%s\n' "$RESET"
}
print_row(){
  local region="$1" label="$2" mbps="$3" ttfb="$4"
  printf ' %s' "$YELLOW"; pad "$region" 16; printf '%s ' "$RESET"
  pad "$label" 24; printf ' '
  printf '%s' "$GREEN"; pad "${mbps} Mbps" 17; printf '%s ' "$RESET"
  printf '%s' "$CYAN"; pad "${ttfb} ms" 12; printf '%s ' "$RESET"
  printf '%s正常%s\n' "$GREEN" "$RESET"
}

TMP="$(mktemp -d -t p07-audit-rc4.XXXXXX)" || exit 3
cleanup(){ rm -rf "$TMP" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

BASE="$TMP/base.sh"
if ! fetch "$BASE_URL" "$BASE"; then printf '%s基础验机模块下载失败。%s\n' "$RED" "$RESET" >&2; exit 4; fi
base_sha="$(sha256_file "$BASE" 2>/dev/null || true)"
if [[ "$base_sha" != "$BASE_SHA256" ]]; then printf '%s基础验机模块完整性校验失败，已停止。%s\n' "$RED" "$RESET" >&2; exit 5; fi

set +e
bash "$BASE"
base_rc=$?
set -e 2>/dev/null || true
if (( base_rc != 0 )); then
  printf '%s基础验机未正常完成，退出码 %s；大陆区域参考不再继续。%s\n' "$RED" "$base_rc" "$RESET" >&2
  exit "$base_rc"
fi

if ! command -v curl >/dev/null 2>&1; then
  rule
  printf '%s%s 中国大陆区域线路参考%s\n' "$BOLD" "$CYAN" "$RESET"
  printf ' %s当前系统没有 curl，已安全跳过大陆区域参考。%s\n' "$YELLOW" "$RESET"
  exit 0
fi

TSV="$TMP/mainland.tsv"; : >"$TSV"
FAILED_REGIONS=""
probe_url(){
  local region="$1" label="$2" url="$3" out="$TMP/data.bin" meta rc code size ttfb speed mbps ttfb_ms
  rm -f "$out"
  set +e
  meta="$(curl -4 -L -sS --fail --connect-timeout 8 --max-time 35 --range 0-4194303 -o "$out" -w '%{http_code}|%{size_download}|%{time_starttransfer}|%{speed_download}' "$url" 2>"$TMP/curl.err")"
  rc=$?
  set -e 2>/dev/null || true
  (( rc == 0 )) || return 1
  IFS='|' read -r code size ttfb speed <<<"$meta"
  [[ "$code" == 200 || "$code" == 206 ]] || return 1
  [[ "${size%.*}" =~ ^[0-9]+$ ]] && (( ${size%.*} >= 524288 )) || return 1
  mbps="$(awk -v b="$speed" 'BEGIN{printf "%.2f",b*8/1000000}')"
  ttfb_ms="$(awk -v t="$ttfb" 'BEGIN{printf "%.0f",t*1000}')"
  printf '%s\t%s\tPASS\t%s\t%s\t%s\n' "$region" "$label" "$mbps" "$ttfb_ms" "$url" >>"$TSV"
  print_row "$region" "$label" "$mbps" "$ttfb_ms"
  return 0
}
probe_pool(){
  local region="$1"; shift
  local spec label url
  for spec in "$@"; do
    label="${spec%%|*}"; url="${spec#*|}"
    probe_url "$region" "$label" "$url" && return 0
  done
  if [[ -n "$FAILED_REGIONS" ]]; then FAILED_REGIONS+="、$region"; else FAILED_REGIONS="$region"; fi
  return 1
}

rule
printf '%s%s 中国大陆区域线路参考%s\n' "$BOLD" "$CYAN" "$RESET"
printf ' %s真实大陆节点；每区下载最多 4 MiB，不使用台湾/香港/境外邻近节点冒充大陆。%s\n' "$YELLOW" "$RESET"
printf ' %s“首字节”包含 VPS→大陆请求、TLS/服务器响应与回程首包时间，适合做跨境线路参考。%s\n' "$GRAY" "$RESET"
print_header
probe_pool '北京' '清华 TUNA|https://mirrors.tuna.tsinghua.edu.cn/debian/ls-lR.gz' '北外 BFSU|https://mirrors.bfsu.edu.cn/debian/ls-lR.gz' || true
probe_pool '上海' '上海交大 SJTUG|https://mirror.sjtu.edu.cn/debian/ls-lR.gz' '上海交大 SJTUG2|https://mirrors.sjtug.sjtu.edu.cn/debian/ls-lR.gz' || true
probe_pool '华南 深圳' '南科大 SUSTech|https://mirrors.sustech.edu.cn/debian/ls-lR.gz' || true
probe_pool '西南 重庆' '重庆邮电 CQUPT|https://mirrors.cqupt.edu.cn/debian/ls-lR.gz' '重庆邮电 IPv4|https://ipv4.mirrors.cqupt.edu.cn/debian/ls-lR.gz' || true

summary="$(python3 - "$TSV" 2>/dev/null <<'PY' || true
import csv,statistics,sys
rows=[]
try:
    for r in csv.reader(open(sys.argv[1],encoding='utf-8'),delimiter='\t'):
        if len(r)>=6 and r[2]=='PASS': rows.append((float(r[3]),float(r[4])))
except Exception: pass
if not rows: print('0|-|-|证据不足')
else:
    d=statistics.median(x[0] for x in rows); t=statistics.median(x[1] for x in rows)
    if len(rows)>=3 and d>=10 and t<1500: g='良好'
    elif len(rows)>=3 and d>=3 and t<3000: g='可用'
    elif len(rows)>=2: g='部分可用'
    else: g='证据不足'
    print(f'{len(rows)}|{d:.2f}|{t:.0f}|{g}')
PY
)"
if [[ -z "$summary" ]]; then summary='0|-|-|证据不足'; fi
IFS='|' read -r pass med_down med_ttfb grade <<<"$summary"
rule
printf '%s%s 中国大陆区域参考结论%s\n' "$BOLD" "$CYAN" "$RESET"
printf ' 有效大陆区域       : %s / 4\n' "$pass"
printf ' 大陆→VPS下载中位数: %s Mbps\n' "$med_down"
printf ' 首字节中位数       : %s ms\n' "$med_ttfb"
printf ' 大陆区域线路       : %s%s%s\n' "$GREEN" "$grade" "$RESET"
if [[ -n "$FAILED_REGIONS" ]]; then printf ' 未取得有效结果     : %s\n' "$FAILED_REGIONS"; fi
printf ' 大陆用户→VPS      : %s未直接检测%s\n' "$YELLOW" "$RESET"
printf ' 结论边界           : 本区块反映真实大陆节点到 VPS 的下载/往返响应参考，不判断 IP 是否被屏蔽。\n'
