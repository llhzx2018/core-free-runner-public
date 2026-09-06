from pathlib import Path
import re

p = Path('experiments/p07-bench.sh')
s = p.read_text()
s = s.replace('VERSION="0.6.0"', 'VERSION="0.7.0"', 1)

# Better global backend classification.
s = re.sub(
    r"network_reason\(\)\{.*?\n\}\nparse_speed_text\(\)\{",
    r'''network_reason(){
  local rc="$1" text="$2"
  if (( rc == 124 )); then printf TIMEOUT
  elif grep -qiE 'too many requests|rate.?limit|http[^0-9]*429|\b429\b' <<<"$text"; then printf RATE_LIMITED
  elif grep -qiE 'cannot retrieve.*configuration|failed to retrieve.*configuration|configurationerror|configuration.*failed|service unavailable|temporarily unavailable' <<<"$text"; then printf BACKEND_UNAVAILABLE
  elif grep -qiE 'server.*not found|no servers|invalid server' <<<"$text"; then printf NODE_UNAVAILABLE
  elif grep -qiE 'resolve|dns' <<<"$text"; then printf DNS_FAILURE
  elif grep -qiE 'ssl|tls|certificate' <<<"$text"; then printf TLS_FAILURE
  elif grep -qiE 'connect|network|route|unreachable' <<<"$text"; then printf CONNECTION_FAILED
  elif (( rc != 0 )); then printf BACKEND_FAILURE
  else printf PARSE_ERROR
  fi
}
parse_speed_text(){''',
    s,
    count=1,
    flags=re.S,
)

# Retry stays in the same shell and backs off once on transient global/backend errors.
old_retry = r'''speed_node_retry(){
  local id="$1" name="$2" original="$NETWORK_TSV" tmp="$TMP_DIR/retry-$$-$RANDOM.tsv"
  local out="$TMP_DIR/retry-output-$$-$RANDOM.txt" output row state reason attempt
  for attempt in 1 2; do
    : >"$tmp"; : >"$out"
    NETWORK_TSV="$tmp"
    speed_node "$id" "$name" >"$out" || true
    NETWORK_TSV="$original"
    output="$(cat "$out" 2>/dev/null || true)"
    row="$(tail -n1 "$tmp" 2>/dev/null || true)"
    [[ -n "$row" ]] || continue
    state="$(awk -F '\t' 'END{print $3}' "$tmp")"
    reason="$(awk -F '\t' 'END{print $4}' "$tmp")"
    if [[ "$state" == PASS || ! "$reason" =~ ^(BACKEND_FAILURE|TIMEOUT|CONNECTION_FAILED)$ || "$attempt" == 2 ]]; then
      cat "$tmp" >>"$original"
      printf '%s\n' "$output"
      [[ "$state" == PASS ]]
      return
    fi
  done
  NETWORK_TSV="$original"
  [[ -s "$tmp" ]] && cat "$tmp" >>"$original"
  [[ -n "${output:-}" ]] && printf '%s\n' "$output"
  return 1
}
'''
new_retry = r'''speed_node_retry(){
  local id="$1" name="$2" original="$NETWORK_TSV" tmp="$TMP_DIR/retry-$$-$RANDOM.tsv"
  local out="$TMP_DIR/retry-output-$$-$RANDOM.txt" output row state reason attempt
  for attempt in 1 2; do
    : >"$tmp"; : >"$out"
    NETWORK_TSV="$tmp"
    speed_node "$id" "$name" >"$out" || true
    NETWORK_TSV="$original"
    output="$(cat "$out" 2>/dev/null || true)"
    row="$(tail -n1 "$tmp" 2>/dev/null || true)"
    [[ -n "$row" ]] || continue
    state="$(awk -F '\t' 'END{print $3}' "$tmp")"
    reason="$(awk -F '\t' 'END{print $4}' "$tmp")"
    if [[ "$state" == PASS || ! "$reason" =~ ^(BACKEND_FAILURE|BACKEND_UNAVAILABLE|RATE_LIMITED|TIMEOUT|CONNECTION_FAILED)$ || "$attempt" == 2 ]]; then
      cat "$tmp" >>"$original"
      printf '%s\n' "$output"
      [[ "$state" == PASS ]]
      return
    fi
    (( DEMO )) || sleep 2
  done
  NETWORK_TSV="$original"
  [[ -s "$tmp" ]] && cat "$tmp" >>"$original"
  [[ -n "${output:-}" ]] && printf '%s\n' "$output"
  return 1
}
'''
if old_retry not in s:
    raise SystemExit('v0.6 retry function not found')
s = s.replace(old_retry, new_retry, 1)

# Eliminate the remaining command-substitution execution from China pool.
start = s.index('speed_node_pool(){')
end = s.index('print_network(){', start)
new_pool = r'''speed_node_pool(){
  local display="$1"; shift
  local original="$NETWORK_TSV" tmp="$TMP_DIR/pool-$$-$RANDOM.tsv"
  local out="$TMP_DIR/pool-output-$$-$RANDOM.txt" spec id label row state reason up down lat output best_reason=NODE_UNAVAILABLE best_id=0
  for spec in "$@"; do
    IFS='|' read -r id label <<<"$spec"
    : >"$tmp"; : >"$out"
    NETWORK_TSV="$tmp"
    speed_node "$id" "$label" >"$out" || true
    NETWORK_TSV="$original"
    output="$(cat "$out" 2>/dev/null || true)"
    row="$(tail -n1 "$tmp" 2>/dev/null || true)"
    [[ -n "$row" ]] || continue
    state="$(awk -F '\t' 'END{print $3}' "$tmp")"
    reason="$(awk -F '\t' 'END{print $4}' "$tmp")"
    up="$(awk -F '\t' 'END{print $5}' "$tmp")"
    down="$(awk -F '\t' 'END{print $6}' "$tmp")"
    lat="$(awk -F '\t' 'END{print $7}' "$tmp")"
    if [[ "$state" == PASS ]]; then
      printf '%s\t%s\tPASS\tNONE\t%s\t%s\t%s\n' "$id" "$display" "$up" "$down" "$lat" >>"$original"
      tty_clean_line
      printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\n' \
        "$YELLOW" "$display" "$RESET" "$GREEN" "$up Mbps" "$RESET" "$RED" "$down Mbps" "$RESET" "$BLUE" "$lat ms" "$RESET" "$GREEN" "PASS" "$RESET" '-'
      return 0
    fi
    if [[ "$reason" != NODE_UNAVAILABLE ]]; then best_reason="$reason"; best_id="$id"; fi
  done
  NETWORK_TSV="$original"
  printf '%s\t%s\tFAIL\t%s\t-\t-\t-\n' "$best_id" "$display" "$best_reason" >>"$original"
  tty_clean_line
  printf ' %s%-17s%s %-13s %-15s %-9s %s%-7s%s %s%-18s%s\n' \
    "$YELLOW" "$display" "$RESET" '-' '-' '-' "$RED" "FAIL" "$RESET" "$YELLOW" "$best_reason" "$RESET"
  return 1
}
'''
s = s[:start] + new_pool + s[end:]

# Global preflight: one default test is authoritative for backend health.
old_head = r'''  : >"$NETWORK_TSV"
  if ! prepare_speedtest; then SPEEDTEST_BIN=""; fi

  speed_node_retry ''      'Speedtest.net' || true
  speed_node_retry 7190    'Los Angeles, US' || true
'''
new_head = r'''  : >"$NETWORK_TSV"
  if ! prepare_speedtest; then
    SPEEDTEST_BIN=""
    speed_node '' 'Speedtest.net' || true
    printf ' %sSpeedtest backend unavailable; node throughput tests skipped.%s\n' "$YELLOW" "$RESET"
    return 0
  fi

  speed_node_retry '' 'Speedtest.net' || true
  local pre_state pre_reason
  pre_state="$(awk -F '\t' '$2=="Speedtest.net"{s=$3} END{print s}' "$NETWORK_TSV")"
  pre_reason="$(awk -F '\t' '$2=="Speedtest.net"{r=$4} END{print r}' "$NETWORK_TSV")"
  if [[ "$pre_state" != PASS && "$pre_reason" =~ ^(RATE_LIMITED|BACKEND_UNAVAILABLE|BACKEND_FAILURE)$ ]]; then
    printf ' %sSpeedtest backend preflight failed: %s. Remaining node tests skipped.%s\n' "$YELLOW" "$pre_reason" "$RESET"
    return 0
  fi

  speed_node_retry 7190    'Los Angeles, US' || true
'''
if old_head not in s:
    raise SystemExit('print_network head not found')
s = s.replace(old_head, new_head, 1)

# Extend lifecycle self-test to cover pool wrapper and global error classification.
needle = r'''  [[ -x "$fake" && -d "$TMP_DIR" ]] || f=1
  SPEEDTEST_BIN="$saved_bin"; SPEEDTEST_TEMP="$saved_temp"; DEMO="$saved_demo"; NETWORK_TSV="$saved_tsv"
'''
repl = r'''  [[ -x "$fake" && -d "$TMP_DIR" ]] || f=1
  : >"$NETWORK_TSV"
  speed_node_pool 'Lifecycle Pool' '1|Lifecycle A' '2|Lifecycle B' >/dev/null || f=1
  [[ "$(awk -F '\t' '$2=="Lifecycle Pool" && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1
  [[ -x "$fake" && -d "$TMP_DIR" ]] || f=1
  [[ "$(network_reason 1 'HTTP 429 Too Many Requests')" == RATE_LIMITED ]] || f=1
  [[ "$(network_reason 1 'Cannot retrieve speedtest configuration')" == BACKEND_UNAVAILABLE ]] || f=1
  SPEEDTEST_BIN="$saved_bin"; SPEEDTEST_TEMP="$saved_temp"; DEMO="$saved_demo"; NETWORK_TSV="$saved_tsv"
'''
if needle not in s:
    raise SystemExit('lifecycle self-test insertion point not found')
s = s.replace(needle, repl, 1)

p.write_text(s)
