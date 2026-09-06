from pathlib import Path
import re

p=Path('experiments/p07-bench.sh')
s=p.read_text(encoding='utf-8')
s=s.replace('VERSION="2.0.0-rc1-zh"','VERSION="2.0.0-rc2-zh"',1)

# New RC2 state.
s=s.replace('V20_CPU_MULTI="UNKNOWN"\nV20_DISK_IOPS=', 'V20_CPU_MULTI="UNKNOWN"\nV20_CPU_BENCH_STATE="NOT_RUN"\nV20_CPU_LOAD_STEAL="UNKNOWN"\nV20_GLOBAL_MEDIAN_UP="UNKNOWN"\nV20_GLOBAL_MEDIAN_DOWN="UNKNOWN"\nV20_SEA_MEDIAN_UP="UNKNOWN"\nV20_SEA_MEDIAN_DOWN="UNKNOWN"\nV20_SLOW_REGION_COUNT=0\nV20_ASYMMETRY_COUNT=0\nV20_DISK_IOPS=',1)

cpu_bench=r'''v20_parse_sha_mb(){
  awk '$1=="sha256"{x=$NF; sub(/k$/,"",x); if(x~/^[0-9.]+$/)v=x/1000} END{if(v>0)printf "%.1f",v}'
}

v20_cpu_stat_pair(){
  awk '/^cpu /{for(i=2;i<=NF;i++)t+=$i; print t"|"$9; exit}' /proc/stat 2>/dev/null
}

v20_cpu_bench(){
  local workers single out i f val total before after t1 st1 t2 st2 loadsteal=UNKNOWN
  if (( DEMO )); then printf 'PASS|780.0|1420.0|0.40'; return; fi
  command -v openssl >/dev/null 2>&1 || { printf 'MISSING|UNKNOWN|UNKNOWN|UNKNOWN'; return; }

  # OpenSSL speed visits six block sizes. One-second mode needs about six seconds,
  # so allow enough wall time for the summary line instead of killing it early.
  out="$(timeout 10s openssl speed -seconds 1 -evp sha256 2>&1 || true)"
  single="$(v20_parse_sha_mb <<<"$out")"
  [[ "$single" =~ ^[0-9.]+$ ]] || { printf 'PARSE_ERROR|UNKNOWN|UNKNOWN|UNKNOWN'; return; }

  workers="${CORES:-1}"; [[ "$workers" =~ ^[0-9]+$ ]] || workers=1
  (( workers>4 )) && workers=4; (( workers<1 )) && workers=1
  before="$(v20_cpu_stat_pair)"
  for ((i=1;i<=workers;i++)); do
    f="$TMP_DIR/cpu-worker-$i.txt"
    timeout 10s openssl speed -seconds 1 -evp sha256 >"$f" 2>&1 &
  done
  wait || true
  after="$(v20_cpu_stat_pair)"
  total=0
  for ((i=1;i<=workers;i++)); do
    val="$(v20_parse_sha_mb <"$TMP_DIR/cpu-worker-$i.txt")"
    [[ "$val" =~ ^[0-9.]+$ ]] || { printf 'PARSE_ERROR|%s|UNKNOWN|UNKNOWN' "$single"; return; }
    total="$(awk -v a="$total" -v b="$val" 'BEGIN{printf "%.1f",a+b}')"
  done
  if [[ "$before" == *'|'* && "$after" == *'|'* ]]; then
    IFS='|' read -r t1 st1 <<<"$before"; IFS='|' read -r t2 st2 <<<"$after"
    if [[ "$t1" =~ ^[0-9]+$ && "$t2" =~ ^[0-9]+$ && "$st1" =~ ^[0-9]+$ && "$st2" =~ ^[0-9]+$ ]] && (( t2>t1 )); then
      loadsteal="$(awk -v ds="$((st2-st1))" -v dt="$((t2-t1))" 'BEGIN{printf "%.2f",100*ds/dt}')"
    fi
  fi
  printf 'PASS|%s|%s|%s' "$single" "$total" "$loadsteal"
}'''
s,n=re.subn(r'v20_cpu_bench\(\)\{.*?\n\}',cpu_bench,s,count=1,flags=re.S)
if n!=1: raise SystemExit('cpu bench function not replaced')

cpu_test=r'''v20_cpu_test(){
  rule
  printf '%s%s CPU 真实表现%s\n' "$BOLD" "$MAGENTA" "$RESET"
  V20_CPU_STEAL="$(v20_cpu_steal)"
  IFS='|' read -r V20_CPU_QUOTA V20_CPU_QUOTA_STATE <<<"$(v20_cpu_quota)"
  IFS='|' read -r V20_CPU_BENCH_STATE V20_CPU_SINGLE V20_CPU_MULTI V20_CPU_LOAD_STEAL <<<"$(v20_cpu_bench)"
  printf ' CPU Steal（空载）  : %s%%  （宿主机争抢信号，越低越好）\n' "$V20_CPU_STEAL"
  if [[ "$V20_CPU_LOAD_STEAL" =~ ^[0-9.]+$ ]]; then printf ' CPU Steal（负载）  : %s%%\n' "$V20_CPU_LOAD_STEAL"; fi
  if [[ "$V20_CPU_QUOTA_STATE" == LIMITED ]]; then
    printf ' CPU 配额           : %s%s%s  （低于系统可见 %s 核）\n' "$RED" "$V20_CPU_QUOTA" "$RESET" "$CORES"
  else
    printf ' CPU 配额           : %s\n' "$V20_CPU_QUOTA"
  fi
  case "$V20_CPU_BENCH_STATE" in
    PASS)
      printf ' SHA256 单核        : %s MB/s\n' "$V20_CPU_SINGLE"
      printf ' SHA256 多核        : %s MB/s  （最多使用 4 核）\n' "$V20_CPU_MULTI"
      ;;
    MISSING) printf ' CPU 轻量跑分       : 未执行（系统没有 OpenSSL）\n' ;;
    PARSE_ERROR) printf ' CPU 轻量跑分       : 已执行，但结果解析失败（不据此扣分）\n' ;;
    *) printf ' CPU 轻量跑分       : 未执行\n' ;;
  esac
}'''
s,n=re.subn(r'v20_cpu_test\(\)\{.*?\n\}',cpu_test,s,count=1,flags=re.S)
if n!=1: raise SystemExit('cpu test function not replaced')

ping_stability=r'''v20_ping_stability(){
  if (( DEMO )); then printf 'PASS|0.0|0.45|3'; return; fi
  command -v ping >/dev/null 2>&1 || { printf 'NOT_RUN|UNKNOWN|UNKNOWN|0'; return; }
  local t r loss jit ok=0 worst=0 maxjit=0 all100=1
  for t in 1.1.1.1 8.8.8.8 9.9.9.9; do
    r="$(v20_ping_target "$t" || true)"; [[ -n "$r" ]] || continue
    IFS='|' read -r loss jit <<<"$r"; ok=$((ok+1))
    worst="$(awk -v a="$worst" -v b="$loss" 'BEGIN{print (b>a)?b:a}')"
    if awk -v x="$loss" 'BEGIN{exit !(x<100)}'; then all100=0; fi
    if [[ "$jit" =~ ^[0-9.]+$ ]]; then maxjit="$(awk -v a="$maxjit" -v b="$jit" 'BEGIN{print (b>a)?b:a}')"; fi
  done
  if (( ok==0 )); then printf 'NOT_RUN|UNKNOWN|UNKNOWN|0'
  elif (( all100==1 )); then printf 'ICMP_BLOCKED|UNKNOWN|UNKNOWN|%s' "$ok"
  else printf 'PASS|%s|%s|%s' "$worst" "$maxjit" "$ok"; fi
}'''
s,n=re.subn(r'v20_ping_stability\(\)\{.*?\n\}',ping_stability,s,count=1,flags=re.S)
if n!=1: raise SystemExit('ping stability not replaced')

# Replace network stability display to distinguish ICMP policy from packet loss.
network_stability=r'''v20_network_stability(){
  rule
  printf '%s%s 网络稳定性%s\n' "$BOLD" "$MAGENTA" "$RESET"
  local ping_ok
  IFS='|' read -r V20_PING_STATE V20_PING_LOSS V20_PING_JITTER ping_ok <<<"$(v20_ping_stability)"
  IFS='|' read -r V20_HTTPS_PASS V20_HTTPS_TOTAL V20_HTTPS_JITTER <<<"$(v20_https_stability)"
  case "$V20_PING_STATE" in
    PASS)
      printf ' ICMP 丢包（最差）  : %s%%  （%s/3 个探针有效）\n' "$V20_PING_LOSS" "$ping_ok"
      printf ' ICMP 抖动（最差）  : %s ms\n' "$V20_PING_JITTER"
      ;;
    ICMP_BLOCKED)
      printf ' ICMP 丢包/抖动     : 受限（%s/3 目标均不响应，不作为线路丢包证据）\n' "$ping_ok"
      ;;
    *) printf ' ICMP 丢包/抖动     : 未执行（不据此判坏）\n' ;;
  esac
  printf ' HTTPS 稳定性       : %s/%s 成功\n' "$V20_HTTPS_PASS" "$V20_HTTPS_TOTAL"
  printf ' HTTPS 响应抖动     : %s ms\n' "$V20_HTTPS_JITTER"
}'''
s,n=re.subn(r'v20_network_stability\(\)\{.*?\n\}',network_stability,s,count=1,flags=re.S)
if n!=1: raise SystemExit('network stability not replaced')

# Resource evidence: unknown quota must remain partial, not silently become normal.
resource_health=r'''v20_resource_health(){
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
  if [[ "$V20_CPU_QUOTA_STATE" == UNKNOWN ]]; then
    V20_RESOURCE_STATE=PARTIAL
  elif (( ok>=4 )); then V20_RESOURCE_STATE=NORMAL
  elif (( ok>=2 )); then V20_RESOURCE_STATE=PARTIAL
  else V20_RESOURCE_STATE=UNKNOWN
  fi
}'''
s,n=re.subn(r'v20_resource_health\(\)\{.*?\n\}',resource_health,s,count=1,flags=re.S)
if n!=1: raise SystemExit('resource health not replaced')

# Network medians and anomaly signals.
metric_block=r'''v20_median_col(){
  local filter="$1" col="$2"
  awk -F '\t' "$filter" "$NETWORK_TSV" 2>/dev/null | sort -n | awk '{a[NR]=$1} END{if(NR==0)print "UNKNOWN"; else if(NR%2)printf "%.2f",a[(NR+1)/2]; else printf "%.2f",(a[NR/2]+a[NR/2+1])/2}'
}

v20_network_metrics(){
  V20_GLOBAL_MEDIAN_UP="$(v20_median_col '$3=="PASS" && $2!="Cloudflare Edge" && $5+0>0 {print $5}' 5)"
  V20_GLOBAL_MEDIAN_DOWN="$(v20_median_col '$3=="PASS" && $2!="Cloudflare Edge" && $6+0>0 {print $6}' 6)"
  V20_SEA_MEDIAN_UP="$(v20_median_col '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Bangkok)/ && $5+0>0 {print $5}' 5)"
  V20_SEA_MEDIAN_DOWN="$(v20_median_col '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Bangkok)/ && $6+0>0 {print $6}' 6)"
  V20_SLOW_REGION_COUNT="$(awk -F '\t' '$3=="PASS" && $2!="Cloudflare Edge" && (($5+0<5)||($6+0<5)){n++} END{print n+0}' "$NETWORK_TSV")"
  V20_ASYMMETRY_COUNT="$(awk -F '\t' '$3=="PASS" && $2!="Cloudflare Edge" && $5+0>0 && $6+0>0 {a=$5+0;b=$6+0; lo=(a<b?a:b); hi=(a>b?a:b); if(lo<10 && hi/lo>=10)n++} END{print n+0}' "$NETWORK_TSV")"
}

'''
s=s.replace('v20_score_and_verdict(){\n',metric_block+'v20_score_and_verdict(){\n',1)

# Replace full score function so network quality is speed-aware and missing evidence reduces completeness.
score_fn=r'''v20_score_and_verdict(){
  local score=0 tested=0 global sea x
  global="$(awk -F '\t' '$3=="PASS" && $2!="Cloudflare Edge"{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  sea="$(awk -F '\t' '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Bangkok)/{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  v20_network_metrics

  # Network 50: coverage 8 + global throughput 12 + SEA 10 + ICMP 10 + HTTPS 10.
  tested=$((tested+8)); if (( global>=8 )); then score=$((score+8)); elif ((global>=6)); then score=$((score+7)); elif ((global>=4)); then score=$((score+5)); elif ((global>=2)); then score=$((score+2)); fi
  if [[ "$V20_GLOBAL_MEDIAN_UP" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+8)); x="$V20_GLOBAL_MEDIAN_UP"
    if awk -v x="$x" 'BEGIN{exit !(x>=100)}'; then score=$((score+8)); elif awk -v x="$x" 'BEGIN{exit !(x>=50)}'; then score=$((score+7)); elif awk -v x="$x" 'BEGIN{exit !(x>=20)}'; then score=$((score+5)); elif awk -v x="$x" 'BEGIN{exit !(x>=10)}'; then score=$((score+3)); else score=$((score+1)); v20_add_issue "全球上行中位数偏低（${x} Mbps）"; fi
  fi
  if [[ "$V20_GLOBAL_MEDIAN_DOWN" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+4)); x="$V20_GLOBAL_MEDIAN_DOWN"
    if awk -v x="$x" 'BEGIN{exit !(x>=200)}'; then score=$((score+4)); elif awk -v x="$x" 'BEGIN{exit !(x>=100)}'; then score=$((score+3)); elif awk -v x="$x" 'BEGIN{exit !(x>=50)}'; then score=$((score+2)); elif awk -v x="$x" 'BEGIN{exit !(x>=20)}'; then score=$((score+1)); else v20_add_issue "全球下行中位数偏低（${x} Mbps）"; fi
  fi
  tested=$((tested+4)); if ((sea>=3)); then score=$((score+4)); elif ((sea==2)); then score=$((score+3)); elif ((sea==1)); then score=$((score+1)); fi
  if [[ "$V20_SEA_MEDIAN_UP" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+4)); x="$V20_SEA_MEDIAN_UP"
    if awk -v x="$x" 'BEGIN{exit !(x>=100)}'; then score=$((score+4)); elif awk -v x="$x" 'BEGIN{exit !(x>=50)}'; then score=$((score+3)); elif awk -v x="$x" 'BEGIN{exit !(x>=20)}'; then score=$((score+2)); elif awk -v x="$x" 'BEGIN{exit !(x>=10)}'; then score=$((score+1)); else v20_add_issue "东南亚上行中位数偏低（${x} Mbps）"; fi
  fi
  if [[ "$V20_SEA_MEDIAN_DOWN" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+2)); x="$V20_SEA_MEDIAN_DOWN"
    if awk -v x="$x" 'BEGIN{exit !(x>=100)}'; then score=$((score+2)); elif awk -v x="$x" 'BEGIN{exit !(x>=50)}'; then score=$((score+1)); else v20_add_issue "东南亚下行中位数偏低（${x} Mbps）"; fi
  fi
  if [[ "$V20_PING_STATE" == PASS && "$V20_PING_LOSS" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+10));
    if awk -v x="$V20_PING_LOSS" 'BEGIN{exit !(x<=1)}'; then score=$((score+10)); elif awk -v x="$V20_PING_LOSS" 'BEGIN{exit !(x<=3)}'; then score=$((score+7)); elif awk -v x="$V20_PING_LOSS" 'BEGIN{exit !(x<=5)}'; then score=$((score+4)); else v20_add_issue "网络丢包偏高（${V20_PING_LOSS}%）"; fi
  fi
  tested=$((tested+10)); if (( V20_HTTPS_TOTAL>0 && V20_HTTPS_PASS==V20_HTTPS_TOTAL )); then score=$((score+10)); elif (( V20_HTTPS_PASS>=12 )); then score=$((score+7)); else v20_add_issue "HTTPS 稳定性不足（${V20_HTTPS_PASS}/${V20_HTTPS_TOTAL}）"; fi
  (( V20_SLOW_REGION_COUNT>0 )) && v20_add_issue "存在 ${V20_SLOW_REGION_COUNT} 个极慢测速地区（<5 Mbps）"
  (( V20_ASYMMETRY_COUNT>0 )) && v20_add_issue "存在 ${V20_ASYMMETRY_COUNT} 个严重上下行不对称地区"

  # CPU 15: steal 8, quota 4, actual benchmark 3.
  local steal_for_score="$V20_CPU_LOAD_STEAL"
  [[ "$steal_for_score" =~ ^[0-9.]+$ ]] || steal_for_score="$V20_CPU_STEAL"
  if [[ "$steal_for_score" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+8));
    if awk -v x="$steal_for_score" 'BEGIN{exit !(x<=2)}'; then score=$((score+8)); elif awk -v x="$steal_for_score" 'BEGIN{exit !(x<=5)}'; then score=$((score+6)); elif awk -v x="$steal_for_score" 'BEGIN{exit !(x<=10)}'; then score=$((score+3)); v20_add_issue "CPU Steal 偏高（${steal_for_score}%）"; else v20_add_issue "CPU Steal 很高（${steal_for_score}%）"; fi
  fi
  if [[ "$V20_CPU_QUOTA_STATE" != UNKNOWN ]]; then tested=$((tested+4)); if [[ "$V20_CPU_QUOTA_STATE" == NORMAL ]]; then score=$((score+4)); else v20_add_issue "CPU 配额低于系统可见核心"; fi; fi
  if [[ "$V20_CPU_BENCH_STATE" == PASS ]]; then tested=$((tested+3)); score=$((score+3)); fi

  # Disk 15.
  if [[ "$IO_STATE" == PASS && "$IO_AVG_MB" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+5)); if awk -v x="$IO_AVG_MB" 'BEGIN{exit !(x>=500)}'; then score=$((score+5)); elif awk -v x="$IO_AVG_MB" 'BEGIN{exit !(x>=200)}'; then score=$((score+4)); elif awk -v x="$IO_AVG_MB" 'BEGIN{exit !(x>=100)}'; then score=$((score+3)); else score=$((score+1)); v20_add_issue "顺序磁盘写入较慢"; fi
  fi
  if [[ "$V20_DISK_IOPS" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+5)); if awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=1000)}'; then score=$((score+5)); elif awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=300)}'; then score=$((score+4)); elif awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=100)}'; then score=$((score+3)); elif awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=30)}'; then score=$((score+2)); else v20_add_issue "4K 同步写 IOPS 很低"; fi
  fi
  if [[ "$V20_FSYNC_P95" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+5)); if awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<5)}'; then score=$((score+5)); elif awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<10)}'; then score=$((score+4)); elif awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<20)}'; then score=$((score+3)); elif awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<50)}'; then score=$((score+1)); v20_add_issue "fsync 延迟偏高"; else v20_add_issue "fsync 延迟很高"; fi
  fi

  # IP 10.
  tested=$((tested+10)); if [[ "$V20_IP_HEALTH" == NORMAL ]]; then score=$((score+10)); else score=$((score+5)); v20_add_issue "IP/DNS/HTTPS 基础健康存在缺项"; fi

  # Resource constraints 10; missing quota evidence reduces completeness instead of pretending PASS.
  v20_resource_health
  case "$V20_RESOURCE_STATE" in
    NORMAL) tested=$((tested+10)); score=$((score+10)) ;;
    PARTIAL) tested=$((tested+6)); score=$((score+6)); v20_add_issue "CPU 配额信息不可确认，资源证据部分有效" ;;
    LIMITED) tested=$((tested+10)); score=$((score+2)) ;;
    *) tested=$((tested+3)); score=$((score+3)); v20_add_issue "资源限制信号无法完整判断" ;;
  esac

  V20_COMPLETENESS="$tested"
  local normalized=0
  (( tested>0 )) && normalized=$(( score*100/tested ))
  V20_SCORE="$normalized"
  if (( normalized>=85 )); then V20_GRADE=GOOD; V20_ADVICE='建议保留';
  elif (( normalized>=70 )); then V20_GRADE=FAIR; V20_ADVICE='可以使用，建议观察';
  elif (( normalized>=55 )); then V20_GRADE=CAUTION; V20_ADVICE='谨慎保留，建议观察稳定性';
  else V20_GRADE=POOR; V20_ADVICE='建议更换或先排查明显问题'; fi
  if (( tested<75 )); then [[ "$V20_GRADE" == GOOD ]] && V20_GRADE=FAIR; V20_ADVICE="${V20_ADVICE}（部分测试未完成）"; fi
}'''
s,n=re.subn(r'v20_score_and_verdict\(\)\{.*?\n\}',score_fn,s,count=1,flags=re.S)
if n!=1: raise SystemExit('score function not replaced')

# Final verdict: expose actual throughput medians and ICMP policy semantics.
s=s.replace("  printf ' 全球有效测速       : %s 个地区\\n' \"$global\"\n  printf ' 东南亚有效测速     : %s/3\\n' \"$sea\"", "  printf ' 全球有效测速       : %s 个地区\\n' \"$global\"\n  printf ' 全球上行中位数     : %s Mbps\\n' \"$V20_GLOBAL_MEDIAN_UP\"\n  printf ' 全球下行中位数     : %s Mbps\\n' \"$V20_GLOBAL_MEDIAN_DOWN\"\n  printf ' 东南亚有效测速     : %s/3\\n' \"$sea\"\n  printf ' 东南亚上行中位数   : %s Mbps\\n' \"$V20_SEA_MEDIAN_UP\"\n  printf ' 东南亚下行中位数   : %s Mbps\\n' \"$V20_SEA_MEDIAN_DOWN\"")
s=s.replace("  printf ' CPU Steal          : %s%%\\n' \"$V20_CPU_STEAL\"", "  printf ' CPU Steal（空载）  : %s%%\\n' \"$V20_CPU_STEAL\"\n  if [[ \"$V20_CPU_LOAD_STEAL\" =~ ^[0-9.]+$ ]]; then printf ' CPU Steal（负载）  : %s%%\\n' \"$V20_CPU_LOAD_STEAL\"; fi")
s=s.replace("  printf ' 网络丢包           : %s\\n' \"$([[ \"$V20_PING_STATE\" == PASS ]] && printf '%s%%' \"$V20_PING_LOSS\" || printf '未直接测得')\"", "  if [[ \"$V20_PING_STATE\" == PASS ]]; then printf ' 网络丢包           : %s%%\\n' \"$V20_PING_LOSS\"; elif [[ \"$V20_PING_STATE\" == ICMP_BLOCKED ]]; then printf ' 网络丢包           : ICMP 受限，未作为丢包证据\\n'; else printf ' 网络丢包           : 未直接测得\\n'; fi")

# Add RC2 JSON fields to existing vps_audit_v20 payload.
s=s.replace("'cpu':{'steal_percent':a[0],'quota':a[1],'quota_state':a[2],'sha256_single_mb_s':a[3],'sha256_multi_mb_s':a[4]},", "'cpu':{'steal_percent':a[0],'quota':a[1],'quota_state':a[2],'sha256_single_mb_s':a[3],'sha256_multi_mb_s':a[4],'bench_state':__import__('os').environ.get('P07_V20_CPU_BENCH_STATE','UNKNOWN'),'load_steal_percent':__import__('os').environ.get('P07_V20_CPU_LOAD_STEAL','UNKNOWN')},")
s=s.replace("'stability':{'icmp_state':a[8],'worst_loss_percent':a[9],'worst_jitter_ms':a[10],'https_pass':int(a[11]),'https_total':int(a[12]),'https_ttfb_jitter_ms':a[13]},", "'stability':{'icmp_state':a[8],'worst_loss_percent':a[9],'worst_jitter_ms':a[10],'https_pass':int(a[11]),'https_total':int(a[12]),'https_ttfb_jitter_ms':a[13]},\n  'network_quality':{'global_median_upload_mbps':__import__('os').environ.get('P07_V20_GLOBAL_MEDIAN_UP','UNKNOWN'),'global_median_download_mbps':__import__('os').environ.get('P07_V20_GLOBAL_MEDIAN_DOWN','UNKNOWN'),'sea_median_upload_mbps':__import__('os').environ.get('P07_V20_SEA_MEDIAN_UP','UNKNOWN'),'sea_median_download_mbps':__import__('os').environ.get('P07_V20_SEA_MEDIAN_DOWN','UNKNOWN'),'slow_region_count':int(__import__('os').environ.get('P07_V20_SLOW_REGION_COUNT','0')),'severe_asymmetry_count':int(__import__('os').environ.get('P07_V20_ASYMMETRY_COUNT','0'))},")
s=s.replace('P07_V20_RESOURCE_STATE="$V20_RESOURCE_STATE" v20_patch_report_json', 'P07_V20_RESOURCE_STATE="$V20_RESOURCE_STATE" P07_V20_CPU_BENCH_STATE="$V20_CPU_BENCH_STATE" P07_V20_CPU_LOAD_STEAL="$V20_CPU_LOAD_STEAL" P07_V20_GLOBAL_MEDIAN_UP="$V20_GLOBAL_MEDIAN_UP" P07_V20_GLOBAL_MEDIAN_DOWN="$V20_GLOBAL_MEDIAN_DOWN" P07_V20_SEA_MEDIAN_UP="$V20_SEA_MEDIAN_UP" P07_V20_SEA_MEDIAN_DOWN="$V20_SEA_MEDIAN_DOWN" P07_V20_SLOW_REGION_COUNT="$V20_SLOW_REGION_COUNT" P07_V20_ASYMMETRY_COUNT="$V20_ASYMMETRY_COUNT" v20_patch_report_json',1)

# Update self-test expectations for new CPU result shape.
s=s.replace("[[ \"$V20_CPU_STEAL\" == '0.30' ]] || f=1", "[[ \"$V20_CPU_STEAL\" == '0.30' ]] || f=1\n  [[ \"$V20_CPU_BENCH_STATE\" == PASS ]] || f=1\n  [[ \"$V20_CPU_LOAD_STEAL\" == '0.40' ]] || f=1")

p.write_text(s,encoding='utf-8')
print('PATCH_V20_RC2=OK')
