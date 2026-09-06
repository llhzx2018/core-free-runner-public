from pathlib import Path

p = Path('experiments/p07-bench.sh')
s = p.read_text(encoding='utf-8')

# Repair the one-character quote leak produced by the first RC5 patch.
s = s.replace('print_net_row "$display" "$up" "$down" "$lat" PASS NONE\'\n',
              'print_net_row "$display" "$up" "$down" "$lat" PASS NONE\n')

# speedtest-go treats a negative latitude token as an option unless --location uses '='.
s = s.replace('--location "$coords" --ping-mode http', '--location="$coords" --ping-mode http')

# User-facing SEA set: keep only regions already proven by the public real probe.
# Singapore already exists; use Kuala Lumpur + Bangkok as the two extra SEA rows.
s = s.replace("  speedtestgo_region 'Jakarta'      '-6.2088,106.8456' && pass=$((pass+1)) || true\n",
              "  speedtestgo_region 'Bangkok'      '13.7563,100.5018' && pass=$((pass+1)) || true\n")
s = s.replace("  speedtestgo_region 'Jakarta' '-6.2088,106.8456' || true\n",
              "  speedtestgo_region 'Bangkok' '13.7563,100.5018' || true\n")
s = s.replace("    'Jakarta') printf '印度尼西亚·雅加达' ;;\n", "")

# Retire the old self-test that required fake China carrier rows.
old = '''  speed_node_pool 'China Unicom, CN' '24447|China Unicom 5G' '43752|BJ Unicom' >/dev/null || f=1\n  [[ "$(awk -F '\\t' '$2=="China Unicom, CN"{print $1":"$3}' "$NETWORK_TSV")" == "43752:PASS" ]] || f=1\n'''
new = '''  speedtestgo_sea_supplement >/dev/null || true\n  [[ "$(awk -F '\\t' '$2=="Kuala Lumpur" && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1\n  [[ "$(awk -F '\\t' '$2=="Bangkok" && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1\n'''
if old not in s:
    raise SystemExit('FIXUP_SELFTEST_ANCHOR_MISSING')
s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('PATCH_RC5_FIXUP=OK')
