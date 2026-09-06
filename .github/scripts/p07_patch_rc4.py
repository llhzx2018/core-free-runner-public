from pathlib import Path

p = Path('experiments/p07-bench.sh')
s = p.read_text(encoding='utf-8')


def once(old: str, new: str) -> None:
    global s
    if old not in s:
        raise SystemExit('missing patch anchor: ' + old[:140])
    s = s.replace(old, new, 1)


once('VERSION="1.0.0-rc3-zh"', 'VERSION="1.0.0-rc4-zh"')
once('LIBRESPEED_VERSION="1.0.14"', '''SPEEDTEST_GO_VERSION="1.8.3"
SPEEDTEST_GO_X86_64_SHA256="c55caae22927cd719a2f8c0bef96ecf74b5fe8ca919ff9200d76328ae5de9477"
SPEEDTEST_GO_I386_SHA256="7b9641833a94c5937d9872f589e017c0fa5e3ef9c4a36a4d88f3b5c7355dc053"
SPEEDTEST_GO_ARM64_SHA256="48f51504548d76d5dc2ce7f72e713bd3b4e35554028b7131467060688754c657"
SPEEDTEST_GO_ARMV7_SHA256="29d6f7b1038d765970c4f0a24e2e26a80b2041f58a7ce3c2e1b4318317c0fbe0"
SPEEDTEST_GO_ARMV6_SHA256="395fd65509af7297b62d8942a323483b48c176cd9404889cc499870fe291d596"
SPEEDTEST_GO_ARMV5_SHA256="4b14cea63c7cf46cce348d8e221ee3f557c3449689e9ae6c6995613277dc6aa9"

LIBRESPEED_VERSION="1.0.14"''')

once("    LIBRESPEED_UNAVAILABLE) printf '备用测速节点不可用' ;;", "    SPEEDTESTGO_FALLBACK) printf '备用测速' ;;\n    SPEEDTESTGO_UNAVAILABLE) printf '备用测速节点不可用' ;;\n    LIBRESPEED_UNAVAILABLE) printf '备用测速节点不可用' ;;")
once("    'Hong Kong, CN') printf '中国香港' ;;", "    'Hong Kong, CN'|'Hong Kong') printf '中国香港' ;;")
once("    'Singapore, SG') printf '新加坡' ;;", "    'Singapore, SG'|'Singapore') printf '新加坡' ;;")
once('LIBRESPEED_BIN=""', 'SPEEDTEST_GO_BIN=""\nLIBRESPEED_BIN=""')

anchor = 'librespeed_arch(){\n'
speedtestgo = r'''speedtestgo_arch(){
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
      'Tokyo') up=520.1; down=680.4; lat=108.6 ;;
      *) return 1 ;;
    esac
  else
    [[ -n "$SPEEDTEST_GO_BIN" ]] || return 1
    out="$TMP_DIR/stg-$(printf '%s' "$display" | tr ' ' '-').json"
    err="$out.err"; parsed="$out.parsed"
    : >"$out"; : >"$err"; : >"$parsed"
    set +e
    timeout 80s "$SPEEDTEST_GO_BIN" --json --saving-mode --thread 1 --location "$coords" --ping-mode http >"$out" 2>"$err"
    rc=$?
    set -e 2>/dev/null || true
    (( rc == 0 )) || return 1
    parse_speedtestgo_json_file "$out" >"$parsed" || return 1
    IFS='|' read -r up down lat <"$parsed"
  fi
  printf 'stg\t%s\tPASS\tSPEEDTESTGO_FALLBACK\t%s\t%s\t%s\n' "$display" "$up" "$down" "$lat" >>"$NETWORK_TSV"
  tty_clean_line
  printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\n' \
    "$YELLOW" "$(zh_name "$display")" "$RESET" "$GREEN" "$up Mbps" "$RESET" "$RED" "$down Mbps" "$RESET" "$BLUE" "$lat ms" "$RESET" "$GREEN" '正常' "$RESET" '备用测速'
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
  speedtestgo_region 'Singapore' '1.3521,103.8198' && pass=$((pass+1)) || true
  speedtestgo_region 'Tokyo'     '35.6762,139.6503' && pass=$((pass+1)) || true
  GLOBAL_FALLBACK_PASS="$pass"
  GLOBAL_FALLBACK_PROVIDER="SPEEDTEST_GO"
  (( pass >= 5 ))
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

'''
once(anchor, speedtestgo + anchor)

old = r'''global_fallback_stack(){
  librespeed_global_fallback || true
  printf ' %s补充基准           : Cloudflare 单边缘节点（仅作参考）%s\n' "$BLUE" "$RESET"
  cloudflare_fallback || printf ' %sCloudflare 补充基准暂不可用。%s\n' "$YELLOW" "$RESET"
}'''
new = r'''global_fallback_stack(){
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
}'''
once(old, new)

once('''  : >"$NETWORK_TSV"
  if ! prepare_speedtest; then''', '''  : >"$NETWORK_TSV"
  if [[ "${P07_BENCH_FORCE_FALLBACK:-0}" == 1 ]]; then
    OOKLA_PROVIDER_STATE="UNAVAILABLE"
    OOKLA_PROVIDER_REASON="BACKEND_UNAVAILABLE"
    printf ' %s主测速平台已跳过，正在执行全球备用测速。%s\n' "$YELLOW" "$RESET"
    global_fallback_stack
    return 0
  fi
  if ! prepare_speedtest; then''')

once('''  [[ ${#LIBRESPEED_386_SHA256} -eq 64 ]] || f=1''', '''  [[ ${#SPEEDTEST_GO_X86_64_SHA256} -eq 64 ]] || f=1
  [[ ${#SPEEDTEST_GO_I386_SHA256} -eq 64 ]] || f=1
  [[ ${#SPEEDTEST_GO_ARM64_SHA256} -eq 64 ]] || f=1
  [[ ${#SPEEDTEST_GO_ARMV7_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_386_SHA256} -eq 64 ]] || f=1''')

p.write_text(s, encoding='utf-8')
