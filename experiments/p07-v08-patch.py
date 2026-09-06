from pathlib import Path

p=Path('experiments/p07-bench.sh')
s=p.read_text()
s=s.replace('VERSION="0.7.0"','VERSION="0.8.0"',1)

insert_before='''print_network(){\n'''
cf_func=r'''cloudflare_fallback(){
  local down_url='https://speed.cloudflare.com/__down?bytes=50000000'
  local up_url='https://speed.cloudflare.com/__up'
  local dres ures d_speed d_ttfb d_code u_speed u_code up_file down_mbps up_mbps ttfb_ms
  if (( DEMO )); then
    printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\n' \
      "$YELLOW" 'Cloudflare Edge' "$RESET" "$GREEN" '850.0 Mbps' "$RESET" "$RED" '920.0 Mbps' "$RESET" "$BLUE" '24.0 ms' "$RESET" "$GREEN" 'PASS' "$RESET" 'FALLBACK'
    printf 'cf-fallback\tCloudflare Edge\tPASS\tFALLBACK\t850.0\t920.0\t24.0\n' >>"$NETWORK_TSV"
    return 0
  fi
  command -v curl >/dev/null 2>&1 || return 1
  dres="$(curl -fLsS --connect-timeout 5 --max-time 35 -o /dev/null -w '%{speed_download}|%{time_starttransfer}|%{http_code}' "$down_url" 2>/dev/null || true)"
  IFS='|' read -r d_speed d_ttfb d_code <<<"$dres"
  [[ "$d_code" == 200 && "$d_speed" =~ ^[0-9.]+$ ]] || return 1
  up_file="$TMP_DIR/cf-upload.bin"
  dd if=/dev/zero of="$up_file" bs=1M count=10 status=none 2>/dev/null || return 1
  ures="$(curl -fLsS --connect-timeout 5 --max-time 35 -X POST --data-binary @"$up_file" -o /dev/null -w '%{speed_upload}|%{http_code}' "$up_url" 2>/dev/null || true)"
  IFS='|' read -r u_speed u_code <<<"$ures"
  [[ "$u_code" =~ ^2[0-9][0-9]$ && "$u_speed" =~ ^[0-9.]+$ ]] || u_speed=0
  down_mbps="$(awk -v b="$d_speed" 'BEGIN{printf "%.1f",b*8/1000000}')"
  up_mbps="$(awk -v b="$u_speed" 'BEGIN{printf "%.1f",b*8/1000000}')"
  ttfb_ms="$(awk -v t="$d_ttfb" 'BEGIN{printf "%.1f",t*1000}')"
  printf 'cf-fallback\tCloudflare Edge\tPASS\tFALLBACK\t%s\t%s\t%s\n' "$up_mbps" "$down_mbps" "$ttfb_ms" >>"$NETWORK_TSV"
  tty_clean_line
  printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\n' \
    "$YELLOW" 'Cloudflare Edge' "$RESET" "$GREEN" "$up_mbps Mbps" "$RESET" "$RED" "$down_mbps Mbps" "$RESET" "$BLUE" "$ttfb_ms ms" "$RESET" "$GREEN" 'PASS' "$RESET" 'FALLBACK'
  return 0
}
'''
if insert_before not in s:
    raise SystemExit('print_network marker not found')
s=s.replace(insert_before,cf_func+insert_before,1)

old=r'''  if [[ "$pre_state" != PASS && "$pre_reason" =~ ^(RATE_LIMITED|BACKEND_UNAVAILABLE|BACKEND_FAILURE)$ ]]; then
    printf ' %sSpeedtest backend preflight failed: %s. Remaining node tests skipped.%s\n' "$YELLOW" "$pre_reason" "$RESET"
    return 0
  fi
'''
new=r'''  if [[ "$pre_state" != PASS && "$pre_reason" =~ ^(RATE_LIMITED|BACKEND_UNAVAILABLE|BACKEND_FAILURE)$ ]]; then
    printf ' %sSpeedtest backend preflight failed: %s. Remaining Ookla nodes skipped.%s\n' "$YELLOW" "$pre_reason" "$RESET"
    printf ' %sFallback           : Cloudflare Edge download/upload baseline%s\n' "$YELLOW" "$RESET"
    cloudflare_fallback || printf ' %sCloudflare fallback unavailable.%s\n' "$YELLOW" "$RESET"
    return 0
  fi
'''
if old not in s:
    raise SystemExit('v0.7 preflight block not found')
s=s.replace(old,new,1)

# Also use fallback when Ookla cannot be prepared at all.
old2=r'''  if ! prepare_speedtest; then
    SPEEDTEST_BIN=""
    speed_node '' 'Speedtest.net' || true
    printf ' %sSpeedtest backend unavailable; node throughput tests skipped.%s\n' "$YELLOW" "$RESET"
    return 0
  fi
'''
new2=r'''  if ! prepare_speedtest; then
    SPEEDTEST_BIN=""
    speed_node '' 'Speedtest.net' || true
    printf ' %sSpeedtest backend unavailable; Ookla node tests skipped.%s\n' "$YELLOW" "$RESET"
    printf ' %sFallback           : Cloudflare Edge download/upload baseline%s\n' "$YELLOW" "$RESET"
    cloudflare_fallback || printf ' %sCloudflare fallback unavailable.%s\n' "$YELLOW" "$RESET"
    return 0
  fi
'''
if old2 not in s:
    raise SystemExit('prepare failure block not found')
s=s.replace(old2,new2,1)

# Self-test fallback renderer without network impact.
needle=r'''  [[ "$(network_reason 1 'Cannot retrieve speedtest configuration')" == BACKEND_UNAVAILABLE ]] || f=1
  SPEEDTEST_BIN="$saved_bin"; SPEEDTEST_TEMP="$saved_temp"; DEMO="$saved_demo"; NETWORK_TSV="$saved_tsv"
'''
repl=r'''  [[ "$(network_reason 1 'Cannot retrieve speedtest configuration')" == BACKEND_UNAVAILABLE ]] || f=1
  DEMO=1; : >"$NETWORK_TSV"; cloudflare_fallback >/dev/null || f=1
  [[ "$(awk -F '\t' '$2=="Cloudflare Edge" && $3=="PASS" && $4=="FALLBACK"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1
  SPEEDTEST_BIN="$saved_bin"; SPEEDTEST_TEMP="$saved_temp"; DEMO="$saved_demo"; NETWORK_TSV="$saved_tsv"
'''
if needle not in s:
    raise SystemExit('self-test marker not found')
s=s.replace(needle,repl,1)

p.write_text(s)
