from pathlib import Path

p=Path('experiments/p07-bench.sh')
s=p.read_text()

s=s.replace('VERSION="0.4.0"','VERSION="0.5.0"',1)

anchor='''}\nspeed_node_pool(){\n'''
retry='''}\nspeed_node_retry(){
  local id="$1" name="$2" original="$NETWORK_TSV" tmp="$TMP_DIR/retry-$$-$RANDOM.tsv"
  local output row state reason attempt
  for attempt in 1 2; do
    : >"$tmp"
    NETWORK_TSV="$tmp"
    output="$(speed_node "$id" "$name" || true)"
    NETWORK_TSV="$original"
    row="$(tail -n1 "$tmp" 2>/dev/null || true)"
    [[ -n "$row" ]] || continue
    IFS=$'\\t' read -r _ _ state reason _ <<<"$row"
    if [[ "$state" == PASS || ! "$reason" =~ ^(BACKEND_FAILURE|TIMEOUT|CONNECTION_FAILED)$ || "$attempt" == 2 ]]; then
      cat "$tmp" >>"$original"
      printf '%s\\n' "$output"
      [[ "$state" == PASS ]]
      return
    fi
  done
  NETWORK_TSV="$original"
  [[ -s "$tmp" ]] && cat "$tmp" >>"$original"
  [[ -n "${output:-}" ]] && printf '%s\\n' "$output"
  return 1
}
speed_node_pool(){
'''
if anchor not in s:
    raise SystemExit('speed_node_pool anchor missing')
s=s.replace(anchor,retry,1)

old_nodes='''  speed_node ''      'Speedtest.net'
  speed_node 7190    'Los Angeles, US'
  speed_node 22288   'Dallas, US'
  speed_node 64420   'Montreal, CA'
  speed_node 61933   'Paris, FR'
  speed_node 41423   'Amsterdam, NL'
'''
new_nodes='''  speed_node_retry ''      'Speedtest.net' || true
  speed_node_retry 7190    'Los Angeles, US' || true
  speed_node_retry 22288   'Dallas, US' || true
  speed_node_retry 64420   'Montreal, CA' || true
  speed_node_retry 61933   'Paris, FR' || true
  speed_node_retry 41423   'Amsterdam, NL' || true
'''
if old_nodes not in s:
    raise SystemExit('global nodes head missing')
s=s.replace(old_nodes,new_nodes,1)

old_tail='''  speed_node 32155   'Hong Kong, CN'
  speed_node 13623   'Singapore, SG'
  speed_node 65092   'Taipei, CN'
  speed_node 48463   'Tokyo, JP'
'''
new_tail='''  speed_node_retry 32155   'Hong Kong, CN' || true
  speed_node_retry 13623   'Singapore, SG' || true
  speed_node_retry 65092   'Taipei, CN' || true
  speed_node_retry 48463   'Tokyo, JP' || true
'''
if old_tail not in s:
    raise SystemExit('global nodes tail missing')
s=s.replace(old_tail,new_tail,1)

start=s.index('china_assessment(){')
end=s.index('\n\n\nwrite_reports(){',start)
china='''china_assessment(){
  local overseas_http=0 mainland_http=0 mainland_fail=0 u
  local cn_speed_pass cn_speed_fail cn_speed_total cn_path_fail cn_node_unavailable
  local fallback_pass fallback_fail overseas_speed_pass evidence_quality
  local primary_pattern='China Unicom, CN|China Telecom, CN'
  local fallback_pattern='China Backup, CN'
  for u in https://www.cloudflare.com/ https://github.com/ https://www.google.com/; do http_probe "$u" && overseas_http=$((overseas_http+1)); done
  for u in https://www.baidu.com/ https://www.qq.com/ https://www.taobao.com/ https://www.189.cn/ https://www.10010.com/ https://www.10086.cn/; do
    if http_probe "$u"; then mainland_http=$((mainland_http+1)); else mainland_fail=$((mainland_fail+1)); fi
  done
  cn_speed_pass="$(count_speed "$primary_pattern" PASS)"
  cn_speed_fail="$(count_speed "$primary_pattern" FAIL)"
  cn_speed_total=$((cn_speed_pass+cn_speed_fail))
  fallback_pass="$(count_speed "$fallback_pattern" PASS)"
  fallback_fail="$(count_speed "$fallback_pattern" FAIL)"
  cn_path_fail="$(count_speed_reason "$primary_pattern" '^(TIMEOUT|CONNECTION_FAILED|DNS_FAILURE|TLS_FAILURE)$')"
  cn_node_unavailable="$(count_speed_reason "$primary_pattern" '^NODE_UNAVAILABLE$')"
  overseas_speed_pass="$(awk -F '\\t' '$2 !~ /China Unicom, CN|China Telecom, CN|China Backup, CN/ && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")"
  CHINA_VERDICT="$(china_verdict_from_counts "$cn_speed_pass" "$cn_path_fail" "$cn_node_unavailable" "$overseas_speed_pass" "$mainland_http" "$mainland_fail" "$overseas_http")"
  if (( cn_speed_pass >= 1 )); then evidence_quality=GOOD
  elif (( fallback_pass >= 1 || mainland_http >= 4 )); then evidence_quality=PARTIAL
  else evidence_quality=LOW
  fi
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
  rule
  printf '%s%s China Access Assessment%s\\n' "$BOLD" "$BLUE" "$RESET"
  printf ' Outbound HTTPS      : Overseas %s/3 | Mainland %s/6\\n' "$overseas_http" "$mainland_http"
  printf ' Carrier Speed       : %s/%s PASS | Fallback %s PASS\\n' "$cn_speed_pass" "$cn_speed_total" "$fallback_pass"
  printf ' Evidence Quality    : %s\\n' "$evidence_quality"
  printf ' Mainland -> VPS     : %sNOT_RUN%s\\n' "$YELLOW" "$RESET"
  printf ' Outbound Verdict    : '; color_state "$CHINA_VERDICT"; printf '\\n'
  printf ' Advice              : %s%s%s\\n' "$YELLOW" "$CHINA_RECOMMENDATION" "$RESET"
  printf ' %sNote: fallback-only evidence cannot produce NORMAL; NODE_UNAVAILABLE is neutral.%s\\n' "$GRAY" "$RESET"
}'''
s=s[:start]+china+s[end:]

# Lock the V0.4 field regression: backup-only success must remain inconclusive.
needle='''  [[ "$(china_verdict_from_counts 0 0 2 9 6 0 3)" == "INCONCLUSIVE" ]] || f=1
'''
if needle not in s:
    raise SystemExit('verdict self-test anchor missing')
s=s.replace(needle,needle+'''  [[ "$(china_verdict_from_counts 1 0 1 9 6 0 3)" == "NORMAL" ]] || f=1
''',1)

p.write_text(s)
