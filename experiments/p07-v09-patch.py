from pathlib import Path

p = Path('experiments/p07-bench.sh')
s = p.read_text()

s = s.replace('VERSION="0.8.0"', 'VERSION="0.9.0"', 1)

s = s.replace('    PASS|NORMAL) printf \'%s%s%s\' "$GREEN" "$1" "$RESET" ;;\n    RISK|PARTIAL|INCONCLUSIVE|SKIPPED|UNAVAILABLE) printf \'%s%s%s\' "$YELLOW" "$1" "$RESET" ;;',
              '    PASS|NORMAL) printf \'%s%s%s\' "$GREEN" "$1" "$RESET" ;;\n    RISK|PARTIAL|INCONCLUSIVE|UNKNOWN|SKIPPED|UNAVAILABLE) printf \'%s%s%s\' "$YELLOW" "$1" "$RESET" ;;', 1)

s = s.replace('SPEEDTEST_BIN=""\nSPEEDTEST_TEMP=0\n', '''SPEEDTEST_BIN=""
SPEEDTEST_TEMP=0
OOKLA_PROVIDER_STATE="NOT_RUN"
OOKLA_PROVIDER_REASON="NOT_RUN"
EVIDENCE_QUALITY="UNKNOWN"
MAINLAND_HTTP_PASS=0
MAINLAND_HTTP_FAIL=0
MAINLAND_HTTP_FAILED=""
''', 1)

s = s.replace("      'Speedtest.net') state=PASS; reason=NONE; up=1180.2; down=1260.4; lat=1.1 ;;",
'''      'Speedtest.net')
        if [[ -n "${P07_BENCH_DEMO_BACKEND_REASON:-}" ]]; then
          state=FAIL; reason="$P07_BENCH_DEMO_BACKEND_REASON"; up='-'; down='-'; lat='-'
        else
          state=PASS; reason=NONE; up=1180.2; down=1260.4; lat=1.1
        fi
        ;;''', 1)

s = s.replace('''  if ! prepare_speedtest; then
    SPEEDTEST_BIN=""
    speed_node '' 'Speedtest.net' || true
    printf ' %sSpeedtest backend unavailable; Ookla node tests skipped.%s\\n' "$YELLOW" "$RESET"
''', '''  if ! prepare_speedtest; then
    SPEEDTEST_BIN=""
    OOKLA_PROVIDER_STATE="UNAVAILABLE"
    OOKLA_PROVIDER_REASON="SPEEDTEST_UNAVAILABLE"
    speed_node '' 'Speedtest.net' || true
    printf ' %sSpeedtest backend unavailable; Ookla node tests skipped.%s\\n' "$YELLOW" "$RESET"
''', 1)

s = s.replace('''  pre_state="$(awk -F '\\t' '$2=="Speedtest.net"{s=$3} END{print s}' "$NETWORK_TSV")"
  pre_reason="$(awk -F '\\t' '$2=="Speedtest.net"{r=$4} END{print r}' "$NETWORK_TSV")"
  if [[ "$pre_state" != PASS && "$pre_reason" =~ ^(RATE_LIMITED|BACKEND_UNAVAILABLE|BACKEND_FAILURE)$ ]]; then
''', '''  pre_state="$(awk -F '\\t' '$2=="Speedtest.net"{s=$3} END{print s}' "$NETWORK_TSV")"
  pre_reason="$(awk -F '\\t' '$2=="Speedtest.net"{r=$4} END{print r}' "$NETWORK_TSV")"
  OOKLA_PROVIDER_STATE="$pre_state"
  OOKLA_PROVIDER_REASON="${pre_reason:-UNKNOWN}"
  if [[ "$pre_state" != PASS && "$pre_reason" =~ ^(RATE_LIMITED|BACKEND_UNAVAILABLE|BACKEND_FAILURE)$ ]]; then
''', 1)

s = s.replace('''http_probe(){
  local url="$1"
  if (( DEMO )); then
    return 0
  fi
''', '''http_probe(){
  local url="$1"
  if (( DEMO )); then
    if [[ -n "${P07_BENCH_DEMO_MAINLAND_FAIL_HOST:-}" && "$url" == *"$P07_BENCH_DEMO_MAINLAND_FAIL_HOST"* ]]; then
      return 1
    fi
    return 0
  fi
''', 1)

start = s.index('china_assessment(){')
end = s.index('\n\n\nwrite_reports(){', start)
old = s[start:end]
new = r'''china_assessment(){
  local overseas_http=0 mainland_http=0 mainland_fail=0 u host mainland_failed=""
  local cn_speed_pass cn_speed_fail cn_speed_total cn_path_fail cn_node_unavailable
  local fallback_pass fallback_fail overseas_speed_pass evidence_quality cf_pass carrier_line
  local primary_pattern='China Unicom, CN|China Telecom, CN'
  local fallback_pattern='China Backup, CN'
  for u in https://www.cloudflare.com/ https://github.com/ https://www.google.com/; do http_probe "$u" && overseas_http=$((overseas_http+1)); done
  for u in https://www.baidu.com/ https://www.qq.com/ https://www.taobao.com/ https://www.189.cn/ https://www.10010.com/ https://www.10086.cn/; do
    if http_probe "$u"; then
      mainland_http=$((mainland_http+1))
    else
      mainland_fail=$((mainland_fail+1))
      host="${u#https://}"; host="${host%%/*}"
      mainland_failed="${mainland_failed}${mainland_failed:+,}${host}"
    fi
  done
  MAINLAND_HTTP_PASS="$mainland_http"
  MAINLAND_HTTP_FAIL="$mainland_fail"
  MAINLAND_HTTP_FAILED="$mainland_failed"

  cn_speed_pass="$(count_speed "$primary_pattern" PASS)"
  cn_speed_fail="$(count_speed "$primary_pattern" FAIL)"
  cn_speed_total=$((cn_speed_pass+cn_speed_fail))
  fallback_pass="$(count_speed "$fallback_pattern" PASS)"
  fallback_fail="$(count_speed "$fallback_pattern" FAIL)"
  cf_pass="$(count_speed '^Cloudflare Edge$' PASS)"
  cn_path_fail="$(count_speed_reason "$primary_pattern" '^(TIMEOUT|CONNECTION_FAILED|DNS_FAILURE|TLS_FAILURE)$')"
  cn_node_unavailable="$(count_speed_reason "$primary_pattern" '^NODE_UNAVAILABLE$')"
  overseas_speed_pass="$(awk -F '\t' '$2 !~ /China Unicom, CN|China Telecom, CN|China Backup, CN/ && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")"

  if [[ "$OOKLA_PROVIDER_STATE" != PASS && "$cn_speed_total" -eq 0 && "$fallback_pass" -eq 0 ]]; then
    CHINA_VERDICT="UNKNOWN"
    if (( mainland_http >= 4 || cf_pass >= 1 )); then evidence_quality="PARTIAL"; else evidence_quality="LOW"; fi
    carrier_line="NOT_RUN (Ookla ${OOKLA_PROVIDER_REASON})"
    case "$OOKLA_PROVIDER_REASON" in
      RATE_LIMITED) CHINA_RECOMMENDATION="OOKLA RATE LIMITED; NO IP-BLOCKING VERDICT FROM SPEEDTEST" ;;
      BACKEND_UNAVAILABLE|BACKEND_FAILURE) CHINA_RECOMMENDATION="OOKLA BACKEND UNAVAILABLE; NO IP-BLOCKING VERDICT FROM SPEEDTEST" ;;
      *) CHINA_RECOMMENDATION="CARRIER SPEED NOT RUN; VERIFY FROM MAINLAND" ;;
    esac
  else
    CHINA_VERDICT="$(china_verdict_from_counts "$cn_speed_pass" "$cn_path_fail" "$cn_node_unavailable" "$overseas_speed_pass" "$mainland_http" "$mainland_fail" "$overseas_http")"
    if (( cn_speed_pass >= 1 )); then evidence_quality=GOOD
    elif (( fallback_pass >= 1 || mainland_http >= 4 || cf_pass >= 1 )); then evidence_quality=PARTIAL
    else evidence_quality=LOW
    fi
    carrier_line="${cn_speed_pass}/${cn_speed_total} PASS | Fallback ${fallback_pass} PASS"
    case "$CHINA_VERDICT" in
      NORMAL) CHINA_RECOMMENDATION="OUTBOUND LOOKS NORMAL; VERIFY MAINLAND -> VPS BEFORE CUTOVER" ;;
      HIGH_RISK) CHINA_RECOMMENDATION="CHANGE IP BEFORE MIGRATION" ;;
      RISK) CHINA_RECOMMENDATION="VERIFY FROM MAINLAND BEFORE MIGRATION" ;;
      *)
        if (( cn_speed_pass == 0 && fallback_pass >= 1 )); then
          CHINA_RECOMMENDATION="CARRIER NODES UNAVAILABLE; VERIFY FROM MAINLAND"
        else
          CHINA_RECOMMENDATION="MAINLAND SIGNAL INCONCLUSIVE"
        fi
        ;;
    esac
  fi
  EVIDENCE_QUALITY="$evidence_quality"

  rule
  printf '%s%s China Access Assessment%s\n' "$BOLD" "$BLUE" "$RESET"
  printf ' Outbound HTTPS      : Overseas %s/3 | Mainland %s/6\n' "$overseas_http" "$mainland_http"
  [[ -n "$mainland_failed" ]] && printf ' Mainland HTTPS Fail : %s\n' "$mainland_failed"
  printf ' Carrier Speed       : %s\n' "$carrier_line"
  printf ' Evidence Quality    : %s\n' "$evidence_quality"
  printf ' Mainland -> VPS     : %sNOT_RUN%s\n' "$YELLOW" "$RESET"
  printf ' China IP Risk       : '; color_state "$CHINA_VERDICT"; printf '\n'
  printf ' Advice              : %s%s%s\n' "$YELLOW" "$CHINA_RECOMMENDATION" "$RESET"
  if [[ "$OOKLA_PROVIDER_STATE" != PASS ]]; then
    printf ' %sNote: Ookla provider failure is test-platform evidence, not IP-blocking evidence.%s\n' "$GRAY" "$RESET"
  else
    printf ' %sNote: fallback-only evidence cannot produce NORMAL; NODE_UNAVAILABLE is neutral.%s\n' "$GRAY" "$RESET"
  fi
}'''
s = s[:start] + new + s[end:]

old_call = '''    python3 - "$REPORT_JSON" "$VERSION" "$OS" "$CPU" "$CORES" "$RAM_TOTAL" "$DISK_TOTAL" "$DISK_USED" "$DISK_SCOPE" "$IPV4" "$ORG" "$CITY" "$COUNTRY" "$IO_STATE" "$IO_AVG_MB" "$CHINA_VERDICT" "$CHINA_RECOMMENDATION" "$elapsed" "$NETWORK_TSV" <<'PY' 2>/dev/null || true
'''
new_call = '''    python3 - "$REPORT_JSON" "$VERSION" "$OS" "$CPU" "$CORES" "$RAM_TOTAL" "$DISK_TOTAL" "$DISK_USED" "$DISK_SCOPE" "$IPV4" "$ORG" "$CITY" "$COUNTRY" "$IO_STATE" "$IO_AVG_MB" "$CHINA_VERDICT" "$CHINA_RECOMMENDATION" "$elapsed" "$NETWORK_TSV" "$OOKLA_PROVIDER_STATE" "$OOKLA_PROVIDER_REASON" "$EVIDENCE_QUALITY" "$MAINLAND_HTTP_PASS" "$MAINLAND_HTTP_FAIL" "$MAINLAND_HTTP_FAILED" <<'PY' 2>/dev/null || true
'''
if old_call not in s:
    raise SystemExit('report call marker not found')
s = s.replace(old_call, new_call, 1)

s = s.replace("(path,version,osname,cpu,cores,ram,disk,disk_used,disk_scope,ipv4,org,city,country,io_state,io_avg,verdict,reco,elapsed,tsv)=sys.argv[1:]",
              "(path,version,osname,cpu,cores,ram,disk,disk_used,disk_scope,ipv4,org,city,country,io_state,io_avg,verdict,reco,elapsed,tsv,provider_state,provider_reason,evidence_quality,mainland_pass,mainland_fail,mainland_failed)=sys.argv[1:]", 1)

s = s.replace("'schema_version':2,'module':'p07-bench','version':version,", "'schema_version':3,'module':'p07-bench','version':version,", 1)

old_assessment = "  'china_ip_assessment':{'verdict':verdict,'recommendation':reco,'evidence_scope':'VPS_OUTBOUND_ONLY','mainland_origin_probe':'NOT_IMPLEMENTED'},"
new_assessment = "  'china_ip_assessment':{'verdict':verdict,'recommendation':reco,'evidence_scope':'VPS_OUTBOUND_ONLY','mainland_origin_probe':'NOT_IMPLEMENTED','evidence_quality':evidence_quality,'ookla_provider':{'state':provider_state,'reason':provider_reason},'mainland_https':{'pass':int(mainland_pass),'fail':int(mainland_fail),'failed_hosts':[x for x in mainland_failed.split(',') if x]}},"
if old_assessment not in s:
    raise SystemExit('json assessment marker not found')
s = s.replace(old_assessment, new_assessment, 1)

# Add regression assertions for reason classification and keep the script one-shot.
marker = '  [[ "$(network_reason 1 \'Cannot retrieve speedtest configuration\')" == BACKEND_UNAVAILABLE ]] || f=1\n'
if marker not in s:
    raise SystemExit('self-test marker not found')
s = s.replace(marker, marker + '  [[ "$(network_reason 1 \'HTTP 429 Too Many Requests\')" == RATE_LIMITED ]] || f=1\n', 1)

p.write_text(s)
