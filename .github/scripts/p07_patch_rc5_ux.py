from pathlib import Path
import re

p = Path('experiments/p07-bench.sh')
s = p.read_text(encoding='utf-8')


def replace_once(old: str, new: str, label: str):
    global s
    if old not in s:
        raise SystemExit(f'PATCH_ANCHOR_MISSING:{label}')
    s = s.replace(old, new, 1)


def regex_once(pattern: str, repl: str, label: str):
    global s
    s2, n = re.subn(pattern, repl, s, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f'PATCH_REGEX_MISSING:{label}:{n}')
    s = s2


replace_once('VERSION="1.0.0-rc4-zh"', 'VERSION="1.0.0-rc5-zh"', 'version')

# New Southeast Asia names are explicit, user-facing and provider-neutral.
replace_once("    'Singapore, SG'|'Singapore') printf '新加坡' ;;\n", "    'Singapore, SG'|'Singapore') printf '新加坡' ;;\n    'Kuala Lumpur') printf '马来西亚·吉隆坡' ;;\n    'Jakarta') printf '印度尼西亚·雅加达' ;;\n    'Bangkok') printf '泰国·曼谷' ;;\n", 'sea names')

# Terminal alignment: printf field width does not understand CJK double-width.
# GNU wc -L with C.UTF-8 does, so all network rows go through one renderer.
replace_once(
    "rule(){ printf '%s\\n' '----------------------------------------------------------------------'; }\n",
    """rule(){ printf '%s\\n' '----------------------------------------------------------------------'; }\ndisplay_width(){\n  local text=\"$1\" w\n  w=\"$(LC_ALL=C.UTF-8 printf '%s\\n' \"$text\" | wc -L 2>/dev/null | tr -d '[:space:]')\"\n  [[ \"$w\" =~ ^[0-9]+$ ]] || w=${#text}\n  printf '%s' \"$w\"\n}\npad_cell(){\n  local text=\"$1\" width=\"$2\" w pad\n  w=\"$(display_width \"$text\")\"\n  pad=$(( width - w ))\n  (( pad < 0 )) && pad=0\n  printf '%s' \"$text\"\n  printf '%*s' \"$pad\" ''\n}\nprint_net_header(){\n  printf '%s ' \"$BOLD$YELLOW\"\n  pad_cell '节点/地区' 22; printf ' '\n  pad_cell '上传' 15; printf ' '\n  pad_cell '下载' 15; printf ' '\n  pad_cell '延迟' 11; printf ' '\n  pad_cell '状态' 8; printf ' '\n  pad_cell '说明' 18\n  printf '%s\\n' \"$RESET\"\n}\nprint_net_row(){\n  local name=\"$1\" up=\"$2\" down=\"$3\" lat=\"$4\" state=\"$5\" reason=\"$6\"\n  local shown_name shown_up shown_down shown_lat shown_state shown_reason state_color\n  shown_name=\"$(zh_name \"$name\")\"\n  if [[ \"$state\" == PASS ]]; then\n    shown_up=\"${up} Mbps\"; shown_down=\"${down} Mbps\"; shown_lat=\"${lat} ms\"; shown_state='正常'\n    case \"$reason\" in\n      SUPPLEMENTAL) shown_reason='补充参考' ;;\n      *) shown_reason='-' ;;\n    esac\n    state_color=\"$GREEN\"\n  else\n    shown_up='-'; shown_down='-'; shown_lat='-'; shown_state=\"$(zh_state \"$state\")\"; shown_reason=\"$(zh_reason \"$reason\")\"\n    state_color=\"$RED\"\n  fi\n  printf ' '\n  printf '%s' \"$YELLOW\"; pad_cell \"$shown_name\" 22; printf '%s ' \"$RESET\"\n  printf '%s' \"$GREEN\"; pad_cell \"$shown_up\" 15; printf '%s ' \"$RESET\"\n  printf '%s' \"$RED\"; pad_cell \"$shown_down\" 15; printf '%s ' \"$RESET\"\n  printf '%s' \"$BLUE\"; pad_cell \"$shown_lat\" 11; printf '%s ' \"$RESET\"\n  printf '%s' \"$state_color\"; pad_cell \"$shown_state\" 8; printf '%s ' \"$RESET\"\n  pad_cell \"$shown_reason\" 18\n  printf '\\n'\n}\n""",
    'aligned renderer')

# speed_node final renderer.
regex_once(
    r'''  tty_clean_line\n  if \[\[ "\$state" == PASS \]\]; then\n    printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\\n' \\\n      "\$YELLOW" "\$\(zh_name "\$name"\)" "\$RESET" "\$GREEN" "\$up Mbps" "\$RESET" "\$RED" "\$down Mbps" "\$RESET" "\$BLUE" "\$lat ms" "\$RESET" "\$GREEN" "正常" "\$RESET" '-'\n  else\n    printf ' %s%-17s%s %-13s %-15s %-9s %s%-7s%s %s%-18s%s\\n' \\\n      "\$YELLOW" "\$\(zh_name "\$name"\)" "\$RESET" '-' '-' '-' "\$RED" "\$\(zh_state "\$state"\)" "\$RESET" "\$YELLOW" "\$\(zh_reason "\$reason"\)" "\$RESET"\n  fi''',
    '''  tty_clean_line\n  print_net_row "$name" "$up" "$down" "$lat" "$state" "$reason"''',
    'speed_node renderer')

# speed_node_pool success and failure renderers.
regex_once(
    r'''      tty_clean_line\n      printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\\n' \\\n        "\$YELLOW" "\$\(zh_name "\$display"\)" "\$RESET" "\$GREEN" "\$up Mbps" "\$RESET" "\$RED" "\$down Mbps" "\$RESET" "\$BLUE" "\$lat ms" "\$RESET" "\$GREEN" "正常" "\$RESET" '-''',
    '''      tty_clean_line\n      print_net_row "$display" "$up" "$down" "$lat" PASS NONE''',
    'pool success renderer')
regex_once(
    r'''  tty_clean_line\n  printf ' %s%-17s%s %-13s %-15s %-9s %s%-7s%s %s%-18s%s\\n' \\\n    "\$YELLOW" "\$\(zh_name "\$display"\)" "\$RESET" '-' '-' '-' "\$RED" "失败" "\$RESET" "\$YELLOW" "\$\(zh_reason "\$best_reason"\)" "\$RESET"''',
    '''  tty_clean_line\n  print_net_row "$display" '-' '-' '-' FAIL "$best_reason"''',
    'pool failure renderer')

# speedtest-go gets extra Southeast Asia coordinates and uses the same renderer.
replace_once("      'Singapore') up=460.4; down=610.6; lat=171.2 ;;\n", "      'Singapore') up=460.4; down=610.6; lat=171.2 ;;\n      'Kuala Lumpur') up=430.8; down=570.5; lat=176.4 ;;\n      'Jakarta') up=390.6; down=520.3; lat=188.7 ;;\n      'Bangkok') up=410.2; down=545.8; lat=181.5 ;;\n", 'speedtestgo demo sea')
regex_once(
    r'''  tty_clean_line\n  printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\\n' \\\n    "\$YELLOW" "\$\(zh_name "\$display"\)" "\$RESET" "\$GREEN" "\$up Mbps" "\$RESET" "\$RED" "\$down Mbps" "\$RESET" "\$BLUE" "\$lat ms" "\$RESET" "\$GREEN" '正常' "\$RESET" '备用测速'\n  return 0\n}\nspeedtestgo_global_fallback''',
    '''  tty_clean_line\n  print_net_row "$display" "$up" "$down" "$lat" PASS SPEEDTESTGO_FALLBACK\n  return 0\n}\nspeedtestgo_global_fallback''',
    'speedtestgo renderer')
replace_once(
    "  speedtestgo_region 'Singapore' '1.3521,103.8198' && pass=$((pass+1)) || true\n  speedtestgo_region 'Tokyo'     '35.6762,139.6503' && pass=$((pass+1)) || true\n",
    "  speedtestgo_region 'Singapore'    '1.3521,103.8198' && pass=$((pass+1)) || true\n  speedtestgo_region 'Kuala Lumpur' '3.1390,101.6869' && pass=$((pass+1)) || true\n  speedtestgo_region 'Jakarta'      '-6.2088,106.8456' && pass=$((pass+1)) || true\n  speedtestgo_region 'Tokyo'        '35.6762,139.6503' && pass=$((pass+1)) || true\n",
    'fallback sea expansion')

# Add a quiet SEA supplement for the normal Ookla path. Failed supplementary nodes are not printed.
replace_once(
    "fallback_has_pass(){\n",
    """speedtestgo_sea_supplement(){\n  prepare_speedtestgo || return 0\n  speedtestgo_region 'Kuala Lumpur' '3.1390,101.6869' || true\n  speedtestgo_region 'Jakarta' '-6.2088,106.8456' || true\n}\n\nfallback_has_pass(){\n""",
    'sea supplement function')

# LibreSpeed paths must share the same aligned renderer too.
regex_once(
    r'''    printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\\n' \\\n      "\$YELLOW" "\$\(zh_name "\$display"\)" "\$RESET" "\$GREEN" "\$up Mbps" "\$RESET" "\$RED" "\$down Mbps" "\$RESET" "\$BLUE" "\$lat ms" "\$RESET" "\$GREEN" '正常' "\$RESET" '备用测速'\n    return 0''',
    '''    print_net_row "$display" "$up" "$down" "$lat" PASS LIBRESPEED_FALLBACK\n    return 0''',
    'librespeed demo renderer')
regex_once(
    r'''      tty_clean_line\n      printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\\n' \\\n        "\$YELLOW" "\$\(zh_name "\$display"\)" "\$RESET" "\$GREEN" "\$up Mbps" "\$RESET" "\$RED" "\$down Mbps" "\$RESET" "\$BLUE" "\$lat ms" "\$RESET" "\$GREEN" '正常' "\$RESET" '备用测速'\n      return 0''',
    '''      tty_clean_line\n      print_net_row "$display" "$up" "$down" "$lat" PASS LIBRESPEED_FALLBACK\n      return 0''',
    'librespeed real renderer')
regex_once(
    r'''  tty_clean_line\n  printf ' %s%-17s%s %-13s %-15s %-9s %s%-7s%s %s%-18s%s\\n' \\\n    "\$YELLOW" "\$\(zh_name "\$display"\)" "\$RESET" '-' '-' '-' "\$RED" '失败' "\$RESET" "\$YELLOW" '备用测速节点不可用' "\$RESET"\n  return 1''',
    '''  tty_clean_line\n  # Supplementary fallback failures stay internal; only useful rows are shown.\n  return 1''',
    'librespeed failed row suppression')

# Cloudflare supplemental line shares the renderer.
regex_once(
    r'''  if \(\( DEMO \)\); then\n    printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\\n' \\\n      "\$YELLOW" 'Cloudflare 边缘基准' "\$RESET" "\$GREEN" '850.0 Mbps' "\$RESET" "\$RED" '920.0 Mbps' "\$RESET" "\$BLUE" '24.0 ms' "\$RESET" "\$GREEN" '正常' "\$RESET" '补充基准'\n    printf 'cf-fallback\\tCloudflare Edge\\tPASS\\tSUPPLEMENTAL\\t850.0\\t920.0\\t24.0\\n' >>"\$NETWORK_TSV"\n    return 0\n  fi''',
    '''  if (( DEMO )); then\n    print_net_row 'Cloudflare Edge' '850.0' '920.0' '24.0' PASS SUPPLEMENTAL\n    printf 'cf-fallback\\tCloudflare Edge\\tPASS\\tSUPPLEMENTAL\\t850.0\\t920.0\\t24.0\\n' >>"$NETWORK_TSV"\n    return 0\n  fi''',
    'cloudflare demo renderer')
regex_once(
    r'''  tty_clean_line\n  printf ' %s%-17s%s %s%-13s%s %s%-15s%s %s%-9s%s %s%-7s%s %-18s\\n' \\\n    "\$YELLOW" 'Cloudflare 边缘基准' "\$RESET" "\$GREEN" "\$up_mbps Mbps" "\$RESET" "\$RED" "\$down_mbps Mbps" "\$RESET" "\$BLUE" "\$ttfb_ms ms" "\$RESET" "\$GREEN" '正常' "\$RESET" '补充基准'\n  return 0''',
    '''  tty_clean_line\n  print_net_row 'Cloudflare Edge' "$up_mbps" "$down_mbps" "$ttfb_ms" PASS SUPPLEMENTAL\n  return 0''',
    'cloudflare real renderer')

# Header uses the same fixed visual columns.
replace_once(
    "  printf '%s 节点/地区              上传          下载            延迟      状态       原因%s\\n' \"$BOLD$YELLOW\" \"$RESET\"\n",
    "  print_net_header\n",
    'network header')

# Remove the chronically unavailable mainland carrier nodes from the default user run.
# They neither prove nor disprove mainland reachability and only add delay/noise.
regex_once(
    r'''  local cn_primary_pass=0\n  speed_node_pool 'China Unicom, CN'.*?  speed_node_retry 32155   'Hong Kong, CN' \|\| true''',
    '''  speed_node_retry 32155   'Hong Kong, CN' || true''',
    'remove dead mainland pool')

# Add two verified Southeast Asia regions to the normal path after Singapore.
replace_once(
    "  speed_node_retry 13623   'Singapore, SG' || true\n  speed_node_retry 65092   'Taipei, CN' || true\n",
    "  speed_node_retry 13623   'Singapore, SG' || true\n  speedtestgo_sea_supplement\n  speed_node_retry 65092   'Taipei, CN' || true\n",
    'normal sea supplement')

# Replace the weak outbound-only China assessment with a compact decision summary.
# Mainland outbound HTTPS is preserved nowhere in the visible UI because it does not answer
# whether mainland users can reach this VPS.
regex_once(
    r'''china_assessment\(\)\{.*?\n\}\n\n\nwrite_reports\(\)\{''',
    r'''china_assessment(){
  local measured_pass sea_pass overall
  measured_pass="$(awk -F '\t' '$3=="PASS" && $2!="Cloudflare Edge"{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  sea_pass="$(awk -F '\t' '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Jakarta|Bangkok)/{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  CHINA_VERDICT="UNKNOWN"
  EVIDENCE_QUALITY="LOW"
  MAINLAND_HTTP_PASS=0
  MAINLAND_HTTP_FAIL=0
  MAINLAND_HTTP_FAILED=""
  if [[ "$IO_STATE" == PASS && "$measured_pass" -ge 5 && "$sea_pass" -ge 2 ]]; then
    overall=PASS
    CHINA_RECOMMENDATION="服务器基础性能与国际/东南亚网络表现可用；中国大陆直连必须用大陆入口探针单独验证"
  elif [[ "$measured_pass" -ge 3 ]]; then
    overall=PARTIAL
    CHINA_RECOMMENDATION="基础网络有有效结果，但覆盖不足；中国大陆直连仍需大陆入口探针"
  else
    overall=RISK
    CHINA_RECOMMENDATION="有效测速地区过少，建议先排查网络再迁移"
  fi

  rule
  printf '%s%s 验机结论%s\n' "$BOLD" "$BLUE" "$RESET"
  printf ' 基础验机结果       : '; color_state "$overall"; printf '\n'
  printf ' 全球有效测速       : %s 个地区\n' "$measured_pass"
  printf ' 东南亚有效测速     : %s 个地区\n' "$sea_pass"
  printf ' 中国大陆直连       : %s未直接检测%s\n' "$YELLOW" "$RESET"
  printf ' 说明               : 当前 VPS→外部 的测速不能代表中国大陆用户→VPS 的真实访问\n'
  printf ' 建议               : %s%s%s\n' "$YELLOW" "$CHINA_RECOMMENDATION" "$RESET"
}


write_reports(){''',
    'replace china assessment')

# Self-test no longer expects fake mainland carrier nodes.
s = re.sub(r'''  : >"\$NETWORK_TSV"\n  speed_node '' 'Speedtest.net' >/dev/null \|\| f=1\n  speed_node_pool 'China Unicom, CN'.*?  DEMO="\$old_demo"''',
           '''  : >"$NETWORK_TSV"\n  speed_node '' 'Speedtest.net' >/dev/null || f=1\n  speedtestgo_sea_supplement >/dev/null || true\n  [[ "$(awk -F '\\t' '$2=="Kuala Lumpur" && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1\n  [[ "$(awk -F '\\t' '$2=="Jakarta" && $3=="PASS"{n++} END{print n+0}' "$NETWORK_TSV")" == "1" ]] || f=1\n  DEMO="$old_demo"''',
           s, count=1, flags=re.S)

p.write_text(s, encoding='utf-8')
print('PATCH_RC5_UX=OK')
