from pathlib import Path

p = Path('experiments/p07-bench.sh')
s = p.read_text()

s = s.replace('VERSION="0.3.0"', 'VERSION="0.4.0"', 1)

anchor = '''parse_speed_text(){
  local text="$1" up down lat
  up="$(awk '/Upload:/{print $2;exit}' <<<"$text")"
  down="$(awk '/Download:/{print $2;exit}' <<<"$text")"
  lat="$(awk '/Latency:/{print $2;exit}' <<<"$text")"
  [[ -n "$up" && -n "$down" && -n "$lat" ]] && printf '%s|%s|%s' "$up" "$down" "$lat"
}
'''
addition = anchor + '''parse_speed_json_file(){
  local file="$1"
  command -v python3 >/dev/null 2>&1 || return 1
  python3 - "$file" <<'PYJSON' 2>/dev/null
import json,sys
from pathlib import Path
text=Path(sys.argv[1]).read_text(errors='replace').lstrip('\\ufeff').strip()
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
'''
if anchor not in s:
    raise SystemExit('parse_speed_text anchor missing')
s = s.replace(anchor, addition, 1)

old = '''    if command -v python3 >/dev/null 2>&1; then
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
'''
new = '''    local key out_file err_file
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
'''
if old not in s:
    raise SystemExit('speed json block missing')
s = s.replace(old, new, 1)

needle = '''}
print_network(){
'''
pool = '''}
speed_node_pool(){
  local display="$1"; shift
  local original="$NETWORK_TSV" tmp="$TMP_DIR/pool-$$-$RANDOM.tsv"
  local spec id label row state reason up down lat output best_reason=NODE_UNAVAILABLE best_id=0
  for spec in "$@"; do
    IFS='|' read -r id label <<<"$spec"
    : >"$tmp"
    NETWORK_TSV="$tmp"
    output="$(speed_node "$id" "$label" || true)"
    NETWORK_TSV="$original"
    row="$(tail -n1 "$tmp" 2>/dev/null || true)"
    [[ -n "$row" ]] || continue
    IFS=$'\\t' read -r _ _ state reason up down lat <<<"$row"
    if [[ "$state" == PASS ]]; then
      printf '%s\\t%s\\tPASS\\tNONE\\t%s\\t%s\\t%s\\n' "$id" "$display" "$up" "$down" "$lat" >>"$original"
      tty_clean_line
      printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\\n' \\
        "$YELLOW" "$display" "$RESET" "$GREEN" "$up Mbps" "$RESET" "$RED" "$down Mbps" "$RESET" "$BLUE" "$lat ms" "$RESET" "$GREEN" "PASS" "$RESET" '-'
      return 0
    fi
    if [[ "$reason" != NODE_UNAVAILABLE ]]; then best_reason="$reason"; best_id="$id"; fi
  done
  NETWORK_TSV="$original"
  printf '%s\\t%s\\tFAIL\\t%s\\t-\\t-\\t-\\n' "$best_id" "$display" "$best_reason" >>"$original"
  tty_clean_line
  printf ' %s%-17s%s %-13s %-15s %-9s %s%-7s%s %s%-18s%s\\n' \\
    "$YELLOW" "$display" "$RESET" '-' '-' '-' "$RED" "FAIL" "$RESET" "$YELLOW" "$best_reason" "$RESET"
  return 1
}
print_network(){
'''
if needle not in s:
    raise SystemExit('speed_node end anchor missing')
s = s.replace(needle, pool, 1)

old_nodes = '''  speed_node 41423   'Amsterdam, NL'
  speed_node 5396    'Suzhou, CN'
  speed_node 59387   'Ningbo, CN'
  speed_node 32155   'Hong Kong, CN'
'''
new_nodes = '''  speed_node 41423   'Amsterdam, NL'
  local cn_primary_pass=0
  speed_node_pool 'China Unicom, CN' '24447|China Unicom 5G' '43752|BJ Unicom' && cn_primary_pass=$((cn_primary_pass+1)) || true
  speed_node_pool 'China Telecom, CN' '36663|China Telecom JiangSu 5G' '5396|China Telecom JiangSu 5G' '59387|Zhejiang Telecom' && cn_primary_pass=$((cn_primary_pass+1)) || true
  if (( cn_primary_pass == 0 )); then
    speed_node_pool 'China Backup, CN' '16204|JSQY' '30852|Duke Kunshan University' || true
  fi
  speed_node 32155   'Hong Kong, CN'
'''
if old_nodes not in s:
    raise SystemExit('mainland node block missing')
s = s.replace(old_nodes, new_nodes, 1)

start = s.index('china_assessment(){')
end = s.index('\n\n\nwrite_reports(){', start)
china = '''china_assessment(){
  local overseas_http=0 mainland_http=0 mainland_fail=0 u cn_speed_pass cn_speed_fail cn_speed_total cn_path_fail cn_node_unavailable overseas_speed_pass
  local cn_pattern='China Unicom, CN|China Telecom, CN|China Backup, CN'
  for u in https://www.cloudflare.com/ https://github.com/ https://www.google.com/; do http_probe "$u" && overseas_http=$((overseas_http+1)); done
  for u in https://www.baidu.com/ https://www.qq.com/ https://www.taobao.com/ https://www.189.cn/ https://www.10010.com/ https://www.10086.cn/; do
    if http_probe "$u"; then mainland_http=$((mainland_http+1)); else mainland_fail=$((mainland_fail+1)); fi
  done
  cn_speed_pass="$(count_speed "$cn_pattern" PASS)"
  cn_speed_fail="$(count_speed "$cn_pattern" FAIL)"
  cn_speed_total=$((cn_speed_pass+cn_speed_fail))
  cn_path_fail="$(count_speed_reason "$cn_pattern" '^(TIMEOUT|CONNECTION_FAILED|DNS_FAILURE|TLS_FAILURE)$')"
  cn_node_unavailable="$(count_speed_reason "$cn_pattern" '^NODE_UNAVAILABLE$')"
  overseas_speed_pass="$(awk -F '\\t' '$2 !~ /China Unicom, CN|China Telecom, CN|China Backup, CN/ && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")"
  CHINA_VERDICT="$(china_verdict_from_counts "$cn_speed_pass" "$cn_path_fail" "$cn_node_unavailable" "$overseas_speed_pass" "$mainland_http" "$mainland_fail" "$overseas_http")"
  case "$CHINA_VERDICT" in
    NORMAL) CHINA_RECOMMENDATION="OUTBOUND OK; VERIFY MAINLAND -> VPS BEFORE CUTOVER" ;;
    HIGH_RISK) CHINA_RECOMMENDATION="CHANGE IP BEFORE MIGRATION" ;;
    RISK) CHINA_RECOMMENDATION="VERIFY FROM MAINLAND BEFORE MIGRATION" ;;
    *) CHINA_RECOMMENDATION="MAINLAND SIGNAL INCONCLUSIVE" ;;
  esac
  rule
  printf '%s%s China Access Assessment%s\\n' "$BOLD" "$BLUE" "$RESET"
  printf ' Outbound HTTPS      : Overseas %s/3 | Mainland %s/6\\n' "$overseas_http" "$mainland_http"
  printf ' Mainland Speed      : %s/%s PASS | PathFail %s | NodeOff %s\\n' "$cn_speed_pass" "$cn_speed_total" "$cn_path_fail" "$cn_node_unavailable"
  printf ' Mainland -> VPS     : %sNOT_RUN%s\\n' "$YELLOW" "$RESET"
  printf ' Outbound Verdict    : '; color_state "$CHINA_VERDICT"; printf '\\n'
  printf ' Advice              : %s%s%s\\n' "$YELLOW" "$CHINA_RECOMMENDATION" "$RESET"
  printf ' %sNote: outbound-only; NODE_UNAVAILABLE is not IP-block evidence.%s\\n' "$GRAY" "$RESET"
}'''
s = s[:start] + china + s[end:]

self_anchor = '''  [[ "$(format_mb_rate '1500.00')" == "1.50 GB/s" ]] || f=1
'''
self_add = self_anchor + '''  local jf="$TMP_DIR/self-json.txt"
  cat >"$jf" <<'EOFJ'
warning-prefix
{"ping":{"latency":1.23},"download":{"bandwidth":4000000},"upload":{"bandwidth":2000000}}
EOFJ
  [[ "$(parse_speed_json_file "$jf")" == "16.00|32.00|1.23" ]] || f=1
'''
if self_anchor not in s:
    raise SystemExit('self-test anchor missing')
s = s.replace(self_anchor, self_add, 1)

old_self_nodes = '''  speed_node 5396 'Suzhou, CN' >/dev/null
  speed_node 59387 'Ningbo, CN' >/dev/null
  [[ "$(count_speed 'Suzhou, CN|Ningbo, CN' FAIL)" == "2" ]] || f=1
'''
new_self_nodes = '''  speed_node '' 'Speedtest.net' >/dev/null || f=1
  speed_node_pool 'China Unicom, CN' '24447|China Unicom 5G' '43752|BJ Unicom' >/dev/null || f=1
  [[ "$(awk -F '\\t' '$2=="China Unicom, CN"{print $1":"$3}' "$NETWORK_TSV")" == "43752:PASS" ]] || f=1
'''
if old_self_nodes not in s:
    raise SystemExit('self-test nodes anchor missing')
s = s.replace(old_self_nodes, new_self_nodes, 1)

p.write_text(s)
