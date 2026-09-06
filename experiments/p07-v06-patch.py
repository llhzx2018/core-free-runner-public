from pathlib import Path

p = Path('experiments/p07-bench.sh')
s = p.read_text()
s = s.replace('VERSION="0.5.0"', 'VERSION="0.6.0"', 1)

old = r'''speed_node_retry(){
  local id="$1" name="$2" original="$NETWORK_TSV" tmp="$TMP_DIR/retry-$$-$RANDOM.tsv"
  local output row state reason attempt
  for attempt in 1 2; do
    : >"$tmp"
    NETWORK_TSV="$tmp"
    output="$(speed_node "$id" "$name" || true)"
    NETWORK_TSV="$original"
    row="$(tail -n1 "$tmp" 2>/dev/null || true)"
    [[ -n "$row" ]] || continue
    IFS=$'\t' read -r _ _ state reason _ <<<"$row"
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

new = r'''speed_node_retry(){
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

if old not in s:
    raise SystemExit('old retry function not found')
s = s.replace(old, new, 1)

marker = r'''  DEMO="$old_demo"
  if (( f )); then printf 'SELF_TEST=FAIL\n'; return 1; else printf 'SELF_TEST=PASS\n'; fi
'''

repl = r'''  DEMO="$old_demo"
  # Retry lifecycle regression: exercise non-demo retry twice with a fake backend.
  local fake="$TMP_DIR/fake-speedtest" saved_bin="$SPEEDTEST_BIN" saved_temp="$SPEEDTEST_TEMP" saved_demo="$DEMO" saved_tsv="$NETWORK_TSV"
  cat >"$fake" <<'EOFFAKE'
#!/usr/bin/env bash
printf '%s\n' '{"ping":{"latency":1.25},"download":{"bandwidth":4000000},"upload":{"bandwidth":2000000}}'
EOFFAKE
  chmod +x "$fake"
  SPEEDTEST_BIN="$fake"; SPEEDTEST_TEMP=0; DEMO=0; NETWORK_TSV="$TMP_DIR/lifecycle.tsv"; : >"$NETWORK_TSV"
  speed_node_retry '' 'Lifecycle A' >/dev/null || f=1
  [[ -x "$fake" && -d "$TMP_DIR" ]] || f=1
  speed_node_retry '' 'Lifecycle B' >/dev/null || f=1
  [[ "$(awk -F '\t' '$3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "2" ]] || f=1
  [[ -x "$fake" && -d "$TMP_DIR" ]] || f=1
  SPEEDTEST_BIN="$saved_bin"; SPEEDTEST_TEMP="$saved_temp"; DEMO="$saved_demo"; NETWORK_TSV="$saved_tsv"
  if (( f )); then printf 'SELF_TEST=FAIL\n'; return 1; else printf 'SELF_TEST=PASS\n'; fi
'''

if marker not in s:
    raise SystemExit('self test marker not found')
s = s.replace(marker, repl, 1)
p.write_text(s)
