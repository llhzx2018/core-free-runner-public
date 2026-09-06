from pathlib import Path

p = Path('experiments/p07-bench.sh')
s = p.read_text()

s = s.replace('VERSION="0.9.0"', 'VERSION="1.0.0-rc1"', 1)

ookla_tail = 'OOKLA_ARMEL_SHA256="629a455a2879224bd0dbd4b36d8c721dda540717937e4660b4d2c966029466bf"\n'
libre_constants = r'''OOKLA_ARMEL_SHA256="629a455a2879224bd0dbd4b36d8c721dda540717937e4660b4d2c966029466bf"

LIBRESPEED_VERSION="1.0.14"
LIBRESPEED_386_SHA256="e2671230b8b6372df3a5910959dfea960915727b4db05f42856dc66dfb6132b2"
LIBRESPEED_AMD64_SHA256="89800767ac14085c78a20847ebea23340f6c14a78de0a15c2ac7db8b565c961f"
LIBRESPEED_ARM64_SHA256="75e51a2494d03cb35a92ddbf862b40571a25a1526f3cf3dfa8b1d5d7bc622bd9"
LIBRESPEED_ARMV5_SHA256="8de0df391623e0ae1dc15c58bd4db800de3bc2c71fd9e8eb9a395ff22e865b40"
LIBRESPEED_ARMV6_SHA256="2300a88101aab950842ca64ad61b9ba901f682d6c1e8de19af26f9442685caf4"
LIBRESPEED_ARMV7_SHA256="527591b4049136feeed73a00203f27362ce6aab7f11973c4985d1507ee469ec4"
'''
if ookla_tail not in s:
    raise SystemExit('Ookla constants marker not found')
s = s.replace(ookla_tail, libre_constants, 1)

state_marker = 'MAINLAND_HTTP_FAILED=""\n'
state_add = r'''MAINLAND_HTTP_FAILED=""
LIBRESPEED_BIN=""
LIBRESPEED_SERVER_JSON="$TMP_DIR/librespeed-servers.json"
GLOBAL_FALLBACK_PROVIDER="NOT_RUN"
GLOBAL_FALLBACK_PASS=0
'''
if state_marker not in s:
    raise SystemExit('state marker not found')
s = s.replace(state_marker, state_add, 1)

insert_at = s.index('cloudflare_fallback(){')
libre_functions = r'''librespeed_arch(){
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
    printf '%sLibreSpeed checksum mismatch; global fallback skipped.%s\n' "$RED" "$RESET"
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
  timeout 35s "$LIBRESPEED_BIN" --json --local-json "$LIBRESPEED_SERVER_JSON" --server "$id" --no-icmp --duration 1 --concurrent 1 --chunks 5 --upload-size 256 --timeout 10 --telemetry-level disabled >"$out" 2>"$err"
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
      'Singapore') up=460.7; down=590.2; lat=164.8 ;;
      'Tokyo') up=520.1; down=680.4; lat=108.6 ;;
      *) return 1 ;;
    esac
    printf 'ls-demo\t%s\tPASS\tLIBRESPEED_FALLBACK\t%s\t%s\t%s\n' "$display" "$up" "$down" "$lat" >>"$NETWORK_TSV"
    printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\n' \
      "$YELLOW" "$display" "$RESET" "$GREEN" "$up Mbps" "$RESET" "$RED" "$down Mbps" "$RESET" "$BLUE" "$lat ms" "$RESET" "$GREEN" 'PASS' "$RESET" 'LIBRESPEED'
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
      printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\n' \
        "$YELLOW" "$display" "$RESET" "$GREEN" "$up Mbps" "$RESET" "$RED" "$down Mbps" "$RESET" "$BLUE" "$lat ms" "$RESET" "$GREEN" 'PASS' "$RESET" 'LIBRESPEED'
      return 0
    fi
  done
  printf 'ls-none\t%s\tFAIL\tLIBRESPEED_UNAVAILABLE\t-\t-\t-\n' "$display" >>"$NETWORK_TSV"
  tty_clean_line
  printf ' %s%-17s%s %-13s %-15s %-9s %s%-7s%s %s%-18s%s\n' \
    "$YELLOW" "$display" "$RESET" '-' '-' '-' "$RED" 'FAIL' "$RESET" "$YELLOW" 'LIBRESPEED_UNAVAILABLE' "$RESET"
  return 1
}
librespeed_global_fallback(){
  printf ' %sGlobal fallback     : LibreSpeed multi-region quick test%s\n' "$BLUE" "$RESET"
  if ! prepare_librespeed; then
    GLOBAL_FALLBACK_PROVIDER="UNAVAILABLE"
    printf ' %sLibreSpeed fallback unavailable.%s\n' "$YELLOW" "$RESET"
    return 1
  fi
  GLOBAL_FALLBACK_PROVIDER="LIBRESPEED"
  GLOBAL_FALLBACK_PASS=0
  librespeed_region_pool 'US West'    '91|Los Angeles Sharktech' '54|Los Angeles Clouvider' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  librespeed_region_pool 'US Central' '93|Chicago Sharktech' '92|Denver Sharktech' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  librespeed_region_pool 'US East'    '52|New York Clouvider' '78|Virginia Riverside' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  librespeed_region_pool 'Europe'     '50|Frankfurt Clouvider' '94|Amsterdam Sharktech' '49|London Clouvider' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  librespeed_region_pool 'Singapore'  '68|Singapore' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  librespeed_region_pool 'Tokyo'      '82|Tokyo' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true
  (( GLOBAL_FALLBACK_PASS >= 3 ))
}
'''
s = s[:insert_at] + libre_functions + s[insert_at:]

# Cloudflare remains a supplemental baseline; it is never the global replacement.
s = s.replace("printf 'cf-fallback\\tCloudflare Edge\\tPASS\\tFALLBACK", "printf 'cf-fallback\\tCloudflare Edge\\tPASS\\tSUPPLEMENTAL", 2)
s = s.replace("'PASS' \"$RESET\" 'FALLBACK'", "'PASS' \"$RESET\" 'SUPPLEMENTAL'", 2)

stack_marker = 'print_network(){\n'
stack_fn = r'''global_fallback_stack(){
  librespeed_global_fallback || true
  printf ' %sSupplemental        : Cloudflare Edge single-edge baseline%s\n' "$BLUE" "$RESET"
  cloudflare_fallback || printf ' %sCloudflare supplemental baseline unavailable.%s\n' "$YELLOW" "$RESET"
}

print_network(){
'''
if stack_marker not in s:
    raise SystemExit('print_network marker not found')
s = s.replace(stack_marker, stack_fn, 1)

old1 = '''    printf ' %sSpeedtest backend unavailable; Ookla node tests skipped.%s\\n' "$YELLOW" "$RESET"
    printf ' %sFallback           : Cloudflare Edge download/upload baseline%s\\n' "$YELLOW" "$RESET"
    cloudflare_fallback || printf ' %sCloudflare fallback unavailable.%s\\n' "$YELLOW" "$RESET"
    return 0
'''
new1 = '''    printf ' %sSpeedtest backend unavailable; Ookla node tests skipped.%s\\n' "$YELLOW" "$RESET"
    global_fallback_stack
    return 0
'''
if old1 not in s:
    raise SystemExit('prepare fallback marker not found')
s = s.replace(old1, new1, 1)

old2 = '''    printf ' %sSpeedtest backend preflight failed: %s. Remaining Ookla nodes skipped.%s\\n' "$YELLOW" "$pre_reason" "$RESET"
    printf ' %sFallback           : Cloudflare Edge download/upload baseline%s\\n' "$YELLOW" "$RESET"
    cloudflare_fallback || printf ' %sCloudflare fallback unavailable.%s\\n' "$YELLOW" "$RESET"
    return 0
'''
new2 = '''    printf ' %sSpeedtest backend preflight failed: %s. Remaining Ookla nodes skipped.%s\\n' "$YELLOW" "$pre_reason" "$RESET"
    global_fallback_stack
    return 0
'''
if old2 not in s:
    raise SystemExit('provider fallback marker not found')
s = s.replace(old2, new2, 1)

# Lock the new fallback and official package hashes into self-test.
self_marker = '  [[ ${#OOKLA_ARMEL_SHA256} -eq 64 ]] || f=1\n'
self_add = self_marker + r'''  [[ ${#LIBRESPEED_386_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_AMD64_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_ARM64_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_ARMV5_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_ARMV6_SHA256} -eq 64 ]] || f=1
  [[ ${#LIBRESPEED_ARMV7_SHA256} -eq 64 ]] || f=1
'''
if self_marker not in s:
    raise SystemExit('self hash marker not found')
s = s.replace(self_marker, self_add, 1)

cf_self = '''  DEMO=1; : >"$NETWORK_TSV"; cloudflare_fallback >/dev/null || f=1
  [[ "$(awk -F '\\t' '$2=="Cloudflare Edge" && $3=="PASS" && $4=="FALLBACK"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1
'''
new_cf_self = '''  DEMO=1; : >"$NETWORK_TSV"; cloudflare_fallback >/dev/null || f=1
  [[ "$(awk -F '\\t' '$2=="Cloudflare Edge" && $3=="PASS" && $4=="SUPPLEMENTAL"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1
  : >"$NETWORK_TSV"; GLOBAL_FALLBACK_PASS=0; librespeed_global_fallback >/dev/null || f=1
  [[ "$(awk -F '\\t' '$4=="LIBRESPEED_FALLBACK" && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "6" ]] || f=1
'''
if cf_self not in s:
    raise SystemExit('Cloudflare self-test marker not found')
s = s.replace(cf_self, new_cf_self, 1)

p.write_text(s)
