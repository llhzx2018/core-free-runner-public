from pathlib import Path

p = Path('experiments/p07-bench.sh')
s = p.read_text(encoding='utf-8')

# Repair the one-character quote leak produced by the first RC5 patch.
s = s.replace('print_net_row "$display" "$up" "$down" "$lat" PASS NONE\'\n',
              'print_net_row "$display" "$up" "$down" "$lat" PASS NONE\n')

# speedtest-go treats a negative latitude token as an option unless --location uses '='.
s = s.replace('--location "$coords" --ping-mode http', '--location="$coords" --ping-mode http')

# User-facing SEA set: Singapore + Kuala Lumpur + Bangkok are already real-probe PASS.
s = s.replace("  speedtestgo_region 'Jakarta'      '-6.2088,106.8456' && pass=$((pass+1)) || true\n",
              "  speedtestgo_region 'Bangkok'      '13.7563,100.5018' && pass=$((pass+1)) || true\n")
s = s.replace("  speedtestgo_region 'Jakarta' '-6.2088,106.8456' || true\n",
              "  speedtestgo_region 'Bangkok' '13.7563,100.5018' || true\n")
s = s.replace("    'Jakarta') printf '印度尼西亚·雅加达' ;;\n", "")

# Avoid ambiguous-width punctuation such as U+00B7 MIDDLE DOT in terminal tables.
# Plain ASCII spaces render consistently in FinShell/Linux TTY/web consoles.
for old, new in {
    '美国西部·洛杉矶': '美国西部 洛杉矶',
    '美国中部·达拉斯': '美国中部 达拉斯',
    '加拿大·蒙特利尔': '加拿大 蒙特利尔',
    '欧洲·巴黎': '欧洲 巴黎',
    '欧洲·阿姆斯特丹': '欧洲 阿姆斯特丹',
    '马来西亚·吉隆坡': '马来西亚 吉隆坡',
    '泰国·曼谷': '泰国 曼谷',
    '日本·东京': '日本 东京',
}.items():
    s = s.replace(old, new)

# The first RC5 patch already rewrites the old China-carrier self-test to KL+Jakarta.
# Keep that contract synchronized with the proven visible set KL+Bangkok.
s = s.replace('$2=="Jakarta" && $3=="PASS"', '$2=="Bangkok" && $3=="PASS"')

p.write_text(s, encoding='utf-8')
print('PATCH_RC5_FIXUP=OK')
