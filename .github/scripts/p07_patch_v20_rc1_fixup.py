from pathlib import Path

p=Path('experiments/p07-bench.sh')
s=p.read_text(encoding='utf-8')

# User-visible title, demo quota wording, and hidden-limit state translation.
s=s.replace('-------------------- P07 VPS 一键验机 --------------------','-------------------- P07 VPS 一键验机 2.0 --------------------')
s=s.replace("if (( DEMO )); then printf '%s|%s' \"$CORES\" NORMAL; return; fi","if (( DEMO )); then printf '%s 核|%s' \"$CORES\" NORMAL; return; fi")
s=s.replace("    LOW) printf '较低' ;;", "    LOW) printf '较低' ;;\n    LIMITED) printf '发现限额' ;;")

# Legacy report writer compatibility. The old China-assessment object is explicitly neutral;
# authoritative V2 semantics live in vps_audit_v20.
needle='V20_IP_HEALTH="UNKNOWN"\nV20_SCORE=0'
repl='''V20_IP_HEALTH="UNKNOWN"
V20_RESOURCE_STATE="UNKNOWN"
CHINA_VERDICT="UNKNOWN"
CHINA_RECOMMENDATION="VPS 验机 2.0 请读取 vps_audit_v20.verdict"
EVIDENCE_QUALITY="V20"
MAINLAND_HTTP_PASS=0
MAINLAND_HTTP_FAIL=0
MAINLAND_HTTP_FAILED=""
V20_SCORE=0'''
if needle not in s: raise SystemExit('init anchor missing')
s=s.replace(needle,repl,1)

# Add resource/hidden-limit health. We intentionally do not claim purchased-plan parity
# because the user does not provide a plan spec.
anchor='v20_score_and_verdict(){\n'
resource=r'''v20_resource_health(){
  if [[ "$V20_CPU_QUOTA_STATE" == LIMITED ]]; then
    V20_RESOURCE_STATE=LIMITED
    v20_add_issue "检测到 CPU cgroup 配额低于系统可见核心"
    return
  fi
  local ok=0
  [[ "${CORES:-}" =~ ^[0-9]+$ && "${CORES:-0}" -gt 0 ]] && ok=$((ok+1))
  [[ -n "${RAM_TOTAL:-}" && "${RAM_TOTAL:-UNKNOWN}" != UNKNOWN ]] && ok=$((ok+1))
  [[ -n "${DISK_TOTAL:-}" && "${DISK_TOTAL:-UNKNOWN}" != UNKNOWN ]] && ok=$((ok+1))
  [[ -n "${VIRT:-}" && "${VIRT:-UNKNOWN}" != UNKNOWN ]] && ok=$((ok+1))
  if (( ok >= 4 )); then V20_RESOURCE_STATE=NORMAL
  elif (( ok >= 2 )); then V20_RESOURCE_STATE=PARTIAL
  else V20_RESOURCE_STATE=UNKNOWN
  fi
}

'''
if anchor not in s: raise SystemExit('score anchor missing')
s=s.replace(anchor,resource+anchor,1)

# Add 10% resource/runtime constraint category and expose a normalized 0-100 score.
needle='''  # IP 10
  tested=$((tested+10)); if [[ "$V20_IP_HEALTH" == NORMAL ]]; then score=$((score+10)); else score=$((score+5)); v20_add_issue "IP/DNS/HTTPS 基础健康存在缺项"; fi

  V20_SCORE="$score"; V20_COMPLETENESS="$tested"
  local normalized=0
  (( tested>0 )) && normalized=$(( score*100/tested ))'''
repl='''  # IP 10
  tested=$((tested+10)); if [[ "$V20_IP_HEALTH" == NORMAL ]]; then score=$((score+10)); else score=$((score+5)); v20_add_issue "IP/DNS/HTTPS 基础健康存在缺项"; fi

  # Resource/runtime constraints 10. This detects hidden limits/signals only; no purchased-plan claim.
  v20_resource_health
  tested=$((tested+10))
  case "$V20_RESOURCE_STATE" in
    NORMAL) score=$((score+10)) ;;
    PARTIAL) score=$((score+6)); v20_add_issue "资源限制信息不完整" ;;
    LIMITED) score=$((score+2)) ;;
    *) score=$((score+4)); v20_add_issue "资源限制信号无法完整判断" ;;
  esac

  V20_COMPLETENESS="$tested"
  local normalized=0
  (( tested>0 )) && normalized=$(( score*100/tested ))
  V20_SCORE="$normalized"'''
if needle not in s: raise SystemExit('IP/score anchor missing')
s=s.replace(needle,repl,1)

# Print score and evidence completeness separately; add resource state to the final verdict.
s=s.replace("  printf ' 评分 / 证据完整度  : %s / %s%%\\n' \"$V20_SCORE\" \"$V20_COMPLETENESS\"", "  printf ' 综合得分           : %s/100\\n' \"$V20_SCORE\"\n  printf ' 证据完整度         : %s%%\\n' \"$V20_COMPLETENESS\"")
needle="  printf ' IP 基础健康        : '; color_state \"$V20_IP_HEALTH\"; printf '\\n'\n  printf ' 中国大陆入站"
repl="  printf ' IP 基础健康        : '; color_state \"$V20_IP_HEALTH\"; printf '\\n'\n  printf ' 资源限制信号       : '; color_state \"$V20_RESOURCE_STATE\"; printf '\\n'\n  printf ' 资源说明           : 未输入购买套餐，本项只检查隐藏限额/异常，不声称套餐规格完全一致\\n'\n  printf ' 中国大陆入站"
if needle not in s: raise SystemExit('final verdict anchor missing')
s=s.replace(needle,repl,1)

# Extend V2 JSON with resource state without disturbing the legacy writer.
needle="  'ip_health':{'dns_pass':int(a[14]),'dns_total':int(a[15]),'state':a[16]},\n  'verdict':"
repl="  'ip_health':{'dns_pass':int(a[14]),'dns_total':int(a[15]),'state':a[16]},\n  'resource_constraints':{'state':__import__('os').environ.get('P07_V20_RESOURCE_STATE','UNKNOWN'),'scope':'HIDDEN_LIMIT_SIGNALS_ONLY'},\n  'verdict':"
if needle not in s: raise SystemExit('json anchor missing')
s=s.replace(needle,repl,1)

# Export resource state only for the JSON patch call; no global environment mutation needed afterwards.
s=s.replace('v20_patch_report_json\nprintf \' 中文报告', 'P07_V20_RESOURCE_STATE="$V20_RESOURCE_STATE" v20_patch_report_json\nprintf \' 中文报告',1)

p.write_text(s,encoding='utf-8')
print('PATCH_V20_RC1_FIXUP=OK')
