#!/usr/bin/env bash
set -uo pipefail

APP="P07 VPS 一键验机 2.0"
VERSION="2.0.0-rc4-zh"
BASE_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/e765c5547a4a92972428042c8594f9359346d3e6/experiments/p07-vps-audit-v20-rc3.sh"
BASE_SHA256="53b30d3616d40f8e64780e97486e36227afb5c07b651923f9205f2906c860951"
SPEEDTEST_GO_VERSION="1.8.3"
SPEEDTEST_GO_X86_64_SHA256="c55caae22927cd719a2f8c0bef96ecf74b5fe8ca919ff9200d76328ae5de9477"
SPEEDTEST_GO_I386_SHA256="7b9641833a94c5937d9872f589e017c0fa5e3ef9c4a36a4d88f3b5c7355dc053"
SPEEDTEST_GO_ARM64_SHA256="48f51504548d76d5dc2ce7f72e713bd3b4e35554028b7131467060688754c657"
SPEEDTEST_GO_ARMV7_SHA256="29d6f7b1038d765970c4f0a24e2e26a80b2041f58a7ce3c2e1b4318317c0fbe0"
SPEEDTEST_GO_ARMV6_SHA256="395fd65509af7297b62d8942a323483b48c176cd9404889cc499870fe291d596"
SPEEDTEST_GO_ARMV5_SHA256="4b14cea63c7cf46cce348d8e221ee3f557c3449689e9ae6c6995613277dc6aa9"

case "${1:-}" in
  --version|-V) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
  --help|-h)
    cat <<'EOF'
P07 VPS 一键验机 2.0

自动执行完整 VPS 验机，并增加中国大陆方向测速：
北京 / 上海 / 广州 / 成都。

注意：中国大陆方向测速是 VPS → 中国大陆测速服务器的线路参考，
不能替代中国大陆真实用户 → VPS 的入站探针。
EOF
    exit 0 ;;
  "") ;;
  *) printf '未知参数：%s\n' "$1" >&2; exit 2 ;;
esac

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RESET=$'\033[0m'; BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; CYAN=$'\033[36m'
else
  RESET=""; BOLD=""; RED=""; GREEN=""; YELLOW=""; CYAN=""
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
  printf '%s' "$BOLD$YELLOW"; pad '中国大陆地区' 18; printf ' '; pad 'VPS→大陆' 15; printf ' '; pad '大陆→VPS' 15; printf ' '; pad '延迟' 11; printf ' '; pad '状态' 8; printf '%s\n' "$RESET"
}
print_row(){
  local name="$1" up="$2" down="$3" lat="$4" state="$5"
  printf ' '; printf '%s' "$YELLOW"; pad "$name" 18; printf '%s ' "$RESET"
  if [[ "$state" == PASS ]]; then
    printf '%s' "$GREEN"; pad "${up} Mbps" 15; printf '%s ' "$RESET"
    printf '%s' "$CYAN"; pad "${down} Mbps" 15; printf '%s ' "$RESET"
    pad "${lat} ms" 11; printf ' '; printf '%s正常%s\n' "$GREEN" "$RESET"
  else
    pad '-' 15; printf ' '; pad '-' 15; printf ' '; pad '-' 11; printf ' '; printf '%s未取得有效结果%s\n' "$RED" "$RESET"
  fi
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
  printf '%s基础验机未正常完成，退出码 %s；中国大陆方向测速不再继续。%s\n' "$RED" "$base_rc" "$RESET" >&2
  exit "$base_rc"
fi

stg_arch(){
  case "$(uname -m 2>/dev/null || true)" in
    x86_64|amd64) printf 'x86_64|%s' "$SPEEDTEST_GO_X86_64_SHA256" ;;
    i386|i486|i586|i686) printf 'i386|%s' "$SPEEDTEST_GO_I386_SHA256" ;;
    aarch64|arm64|armv8|armv8l) printf 'arm64|%s' "$SPEEDTEST_GO_ARM64_SHA256" ;;
    armv7|armv7l) printf 'armv7|%s' "$SPEEDTEST_GO_ARMV7_SHA256" ;;
    armv6|armv6l) printf 'armv6|%s' "$SPEEDTEST_GO_ARMV6_SHA256" ;;
    armv5|armv5l) printf 'armv5|%s' "$SPEEDTEST_GO_ARMV5_SHA256" ;;
    *) return 1 ;;
  esac
}
prepare_stg(){
  command -v tar >/dev/null 2>&1 || return 1
  local pair arch expected url got bin
  pair="$(stg_arch 2>/dev/null || true)"; [[ -n "$pair" ]] || return 1
  IFS='|' read -r arch expected <<<"$pair"
  url="https://github.com/showwin/speedtest-go/releases/download/v${SPEEDTEST_GO_VERSION}/speedtest-go_${SPEEDTEST_GO_VERSION}_Linux_${arch}.tar.gz"
  fetch "$url" "$TMP/stg.tgz" || return 1
  got="$(sha256_file "$TMP/stg.tgz" 2>/dev/null || true)"; [[ "$got" == "$expected" ]] || return 1
  mkdir -p "$TMP/stg"; tar -xzf "$TMP/stg.tgz" -C "$TMP/stg" >/dev/null 2>&1 || return 1
  bin="$(find "$TMP/stg" -maxdepth 2 -type f -name 'speedtest-go*' ! -name '*.tgz' | head -n1)"; [[ -n "$bin" ]] || return 1
  chmod 0755 "$bin"; STG="$bin"
}

TSV="$TMP/china.tsv"; : >"$TSV"
probe_region(){
  local name="$1" coords="$2" out="$TMP/${name}.json" err="$TMP/${name}.err" parsed rc up down lat
  set +e
  if command -v timeout >/dev/null 2>&1; then
    timeout 90s "$STG" --json --saving-mode --thread 1 --location="$coords" --ping-mode http >"$out" 2>"$err"
  else
    "$STG" --json --saving-mode --thread 1 --location="$coords" --ping-mode http >"$out" 2>"$err"
  fi
  rc=$?
  set -e 2>/dev/null || true
  if (( rc != 0 )); then printf '%s\tFAIL\t-\t-\t-\n' "$name" >>"$TSV"; print_row "$name" - - - FAIL; return 1; fi
  parsed="$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); s=(p.get("servers") or [{}])[0]; print("%.2f|%.2f|%.2f"%(float(s["ul_speed"])/125000,float(s["dl_speed"])/125000,float(s["latency"])/1000000))' "$out" 2>/dev/null || true)"
  IFS='|' read -r up down lat <<<"$parsed"
  if [[ -z "$up" || -z "$down" || -z "$lat" ]]; then printf '%s\tFAIL\t-\t-\t-\n' "$name" >>"$TSV"; print_row "$name" - - - FAIL; return 1; fi
  printf '%s\tPASS\t%s\t%s\t%s\n' "$name" "$up" "$down" "$lat" >>"$TSV"
  print_row "$name" "$up" "$down" "$lat" PASS
}

rule
printf '%s%s 中国大陆方向测速%s\n' "$BOLD" "$CYAN" "$RESET"
printf ' %s说明：上传列表示 VPS→大陆测速节点；下载列表示大陆测速节点→VPS。%s\n' "$YELLOW" "$RESET"
printf ' %s这是跨境线路参考，不等于中国大陆真实用户入站可达性。%s\n' "$YELLOW" "$RESET"

if ! command -v python3 >/dev/null 2>&1 || ! prepare_stg; then
  printf ' %s中国大陆测速组件暂不可用，已安全跳过，不影响前面的基础验机结果。%s\n' "$YELLOW" "$RESET"
  exit 0
fi

print_header
probe_region '北京' '39.9042,116.4074' || true
probe_region '上海' '31.2304,121.4737' || true
probe_region '广州' '23.1291,113.2644' || true
probe_region '成都' '30.5728,104.0668' || true

python3 - "$TSV" <<'PY'
import csv,statistics,sys
rows=[]
with open(sys.argv[1],encoding='utf-8') as f:
    for r in csv.reader(f,delimiter='\t'):
        if len(r)>=5 and r[1]=='PASS':
            rows.append((r[0],float(r[2]),float(r[3]),float(r[4])))
print('PASS_COUNT='+str(len(rows)))
if rows:
    print('MEDIAN_UP=%.2f'%statistics.median(x[1] for x in rows))
    print('MEDIAN_DOWN=%.2f'%statistics.median(x[2] for x in rows))
    print('MEDIAN_LAT=%.2f'%statistics.median(x[3] for x in rows))
PY
summary="$(python3 - "$TSV" <<'PY'
import csv,statistics,sys
rows=[]
for r in csv.reader(open(sys.argv[1],encoding='utf-8'),delimiter='\t'):
    if len(r)>=5 and r[1]=='PASS': rows.append((float(r[2]),float(r[3]),float(r[4])))
if not rows: print('0|-|-|-|未取得有效结果')
else:
    up=statistics.median(x[0] for x in rows); down=statistics.median(x[1] for x in rows); lat=statistics.median(x[2] for x in rows)
    if len(rows)>=3 and up>=80 and lat<220: grade='良好'
    elif len(rows)>=2 and up>=25 and lat<280: grade='可用'
    else: grade='较弱/证据不足'
    print(f'{len(rows)}|{up:.2f}|{down:.2f}|{lat:.2f}|{grade}')
PY
)"
IFS='|' read -r pass med_up med_down med_lat grade <<<"$summary"
rule
printf '%s%s 中国大陆方向参考%s\n' "$BOLD" "$CYAN" "$RESET"
printf ' 有效地区           : %s / 4\n' "$pass"
printf ' VPS→大陆中位数    : %s Mbps\n' "$med_up"
printf ' 大陆→VPS中位数    : %s Mbps\n' "$med_down"
printf ' 延迟中位数         : %s ms\n' "$med_lat"
printf ' 方向评价           : %s%s%s\n' "$GREEN" "$grade" "$RESET"
printf ' 大陆用户→VPS      : %s未直接检测%s\n' "$YELLOW" "$RESET"
printf ' 结论边界           : 本区块只判断跨境线路表现，不判断 IP 是否被屏蔽。\n'
