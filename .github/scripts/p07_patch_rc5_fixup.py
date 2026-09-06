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

# Remove Jakarta from the visible RC5 default set until it has its own clean proof.
s = s.replace("    'Jakarta') printf '印度尼西亚·雅加达' ;;\n", "")

p.write_text(s, encoding='utf-8')
print('PATCH_RC5_FIXUP=OK')
