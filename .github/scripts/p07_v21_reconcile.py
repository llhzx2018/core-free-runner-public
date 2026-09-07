from pathlib import Path

p = Path('experiments/p07-vps-audit-v21.sh')
s = p.read_text(encoding='utf-8')

needle = '''FIO_VERDICT="未执行"\nFIO_SMALL="未知"\nFIO_LARGE="未知"\nROUTE_VERDICT="未执行"\n'''
replacement = '''FIO_VERDICT="未执行"\nFIO_SMALL="未知"\nFIO_LARGE="未知"\nROUTE_VERDICT="未执行"\nBASE_OUTPUT="$TMP/base-output.txt"\nBASE_PLAIN="$TMP/base-plain.txt"\n: >"$BASE_OUTPUT"\n: >"$BASE_PLAIN"\nBASE_GRADE="未知"\nBASE_SCORE="未知"\nBASE_RECOMMEND="未知"\nFINAL_RECOMMEND="未知"\n'''
assert needle in s
s = s.replace(needle, replacement, 1)

needle = '''run_base(){\n  [[ "${P07_V21_SKIP_BASE:-0}" == 1 ]] && return 0\n'''
insert = r'''strip_terminal_codes(){
  sed -E $'s/\x1B\\[[0-9;?]*[ -/]*[@-~]//g; s/\r$//'
}
normalize_base_output(){
  sed -u \
    -e 's/P07 VPS 一键验机 2\.0/P07 VPS 一键验机 V2.1.0/g' \
    -e 's/2\.0\.0-rc3-zh/V2.1.0/g' \
    -e 's/2\.0\.0-rc4-zh/V2.1.0/g' \
    -e 's/ 最终验机结论/ 基础综合结论/g' \
    -e 's/ 总耗时             :/ 基础验机耗时       :/g' \
    -e 's/ 完成时间           :/ 基础验机完成       :/g'
}

run_base(){
  [[ "${P07_V21_SKIP_BASE:-0}" == 1 ]] && return 0
'''
assert needle in s
s = s.replace(needle, insert, 1)

old = '''  set +e\n  bash "$base"\n  rc=$?\n  set -e 2>/dev/null || true\n  return "$rc"\n}\n'''
new = '''  set +e\n  if command -v script >/dev/null 2>&1 && [[ -t 1 && -z "${NO_COLOR:-}" ]]; then\n    script -qec "bash '$base'" /dev/null | normalize_base_output | tee "$BASE_OUTPUT"\n    rc=${PIPESTATUS[0]}\n  else\n    bash "$base" 2>&1 | normalize_base_output | tee "$BASE_OUTPUT"\n    rc=${PIPESTATUS[0]}\n  fi\n  set -e 2>/dev/null || true\n  strip_terminal_codes <"$BASE_OUTPUT" >"$BASE_PLAIN"\n  return "$rc"\n}\n'''
assert old in s
s = s.replace(old, new, 1)

needle = '''write_markdown(){\n'''
insert = r'''extract_base_summary(){
  [[ -s "$BASE_PLAIN" ]] || return 0
  BASE_GRADE="$(awk -F: '$1 ~ /^[[:space:]]*综合评级[[:space:]]*$/{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}' "$BASE_PLAIN")"
  BASE_SCORE="$(awk -F: '$1 ~ /^[[:space:]]*综合得分[[:space:]]*$/{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}' "$BASE_PLAIN")"
  BASE_RECOMMEND="$(awk -F: '$1 ~ /^[[:space:]]*建议[[:space:]]*$/{sub(/^[^:]*:/, ""); gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0); print; exit}' "$BASE_PLAIN")"
  [[ -n "$BASE_GRADE" ]] || BASE_GRADE="未知"
  [[ -n "$BASE_SCORE" ]] || BASE_SCORE="未知"
  [[ -n "$BASE_RECOMMEND" ]] || BASE_RECOMMEND="未知"
}
build_final_recommendation(){
  FINAL_RECOMMEND="$BASE_RECOMMEND"
  [[ "$FINAL_RECOMMEND" != 未知 ]] || FINAL_RECOMMEND="请结合基础验机与增强项判断"
  case "$FIO_VERDICT" in
    需观察) FINAL_RECOMMEND="${FINAL_RECOMMEND}；数据库/混合磁盘负载需观察" ;;
    证据不足|未执行) FINAL_RECOMMEND="${FINAL_RECOMMEND}；增强磁盘证据不足" ;;
  esac
}

write_markdown(){
'''
assert needle in s
s = s.replace(needle, insert, 1)

old = '''    printf -- '- 说明：仅保存本机，不自动上传第三方。\\n\\n'\n    printf '## 增强磁盘低负载测试\\n\\n'\n'''
new = '''    printf -- '- 说明：仅保存本机，不自动上传第三方。\\n\\n'\n    if [[ -s "$BASE_PLAIN" ]]; then\n      printf '## 基础与网络验机输出\\n\\n```text\\n'\n      cat "$BASE_PLAIN"\n      printf '\\n```\\n\\n'\n    fi\n    printf '## 增强磁盘低负载测试\\n\\n'\n'''
assert old in s
s = s.replace(old, new, 1)

old = '''printf '%s%s V2.1.0 增强项结论%s\\n' "$BOLD" "$CYAN" "$RESET"\nprintf ' 增强磁盘           : %s\\n' "$FIO_VERDICT"\nprintf ' 中国三网回程       : %s\\n' "$ROUTE_VERDICT"\nprintf ' 增强项总耗时       : %s 秒\\n' "$((end_epoch-START_EPOCH))"\nprintf ' 说明               : V2.0.0 基础验机保留；增强 fio 与三网回程均为 fail-closed，不会因单项失败拖住整套验机。\\n'\n'''
new = '''printf '%s%s 最终验机结论%s\\n' "$BOLD" "$CYAN" "$RESET"\nprintf ' 综合评级           : %s\\n' "$BASE_GRADE"\nprintf ' 基础得分           : %s\\n' "$BASE_SCORE"\nprintf ' 增强磁盘           : %s\\n' "$FIO_VERDICT"\nprintf ' 中国三网回程       : %s\\n' "$ROUTE_VERDICT"\nprintf ' 建议               : %s\\n' "$FINAL_RECOMMEND"\nprintf ' 完整验机总耗时     : %s 秒\\n' "$((end_epoch-START_EPOCH))"\nprintf ' 说明               : 增强 fio 与三网回程均为 fail-closed，单项失败不会拖住整套验机。\\n'\n'''
assert old in s
s = s.replace(old, new, 1)

old = '''print_fio\nprint_three_carrier_route\nwrite_markdown\nend_epoch="$(date +%s)"\n'''
new = '''print_fio\nprint_three_carrier_route\nextract_base_summary\nbuild_final_recommendation\nwrite_markdown\nend_epoch="$(date +%s)"\n'''
assert old in s
s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
