from pathlib import Path

p = Path('experiments/p07-bench.sh')
s = p.read_text(encoding='utf-8')

s = s.replace('APP="P07 VPS 一键验机"\nVERSION="1.0.0-rc5-zh"', 'APP="P07 VPS 一键验机 2.0"\nVERSION="2.0.0-rc1-zh"')

marker = 'self_test(){\n'
if marker not in s:
    raise SystemExit('self_test marker not found')

block = r'''# ===== P07 VPS Audit 2.0 =====
V20_CPU_STEAL="UNKNOWN"
V20_CPU_QUOTA="UNKNOWN"
V20_CPU_QUOTA_STATE="UNKNOWN"
V20_CPU_SINGLE="UNKNOWN"
V20_CPU_MULTI="UNKNOWN"
V20_DISK_IOPS="UNKNOWN"
V20_FSYNC_AVG="UNKNOWN"
V20_FSYNC_P95="UNKNOWN"
V20_PING_STATE="NOT_RUN"
V20_PING_LOSS="UNKNOWN"
V20_PING_JITTER="UNKNOWN"
V20_HTTPS_PASS=0
V20_HTTPS_TOTAL=0
V20_HTTPS_JITTER="UNKNOWN"
V20_DNS_PASS=0
V20_DNS_TOTAL=0
V20_IP_HEALTH="UNKNOWN"
V20_SCORE=0
V20_COMPLETENESS=0
V20_GRADE="UNKNOWN"
V20_ADVICE="UNKNOWN"
V20_ISSUES=""

v20_add_issue(){
  local x="$1"
  [[ -n "$x" ]] || return 0
  if [[ -n "$V20_ISSUES" ]]; then V20_ISSUES+="；$x"; else V20_ISSUES="$x"; fi
}

v20_cpu_steal(){
  if (( DEMO )); then printf '0.30'; return; fi
  [[ -r /proc/stat ]] || { printf 'UNKNOWN'; return; }
  local a b t1 t2 s1 s2
  a="$(awk '/^cpu /{for(i=2;i<=NF;i++)t+=$i; print t"|"$9; exit}' /proc/stat 2>/dev/null)"
  sleep 2
  b="$(awk '/^cpu /{for(i=2;i<=NF;i++)t+=$i; print t"|"$9; exit}' /proc/stat 2>/dev/null)"
  IFS='|' read -r t1 s1 <<<"$a"; IFS='|' read -r t2 s2 <<<"$b"
  if [[ "$t1" =~ ^[0-9]+$ && "$t2" =~ ^[0-9]+$ && "$s1" =~ ^[0-9]+$ && "$s2" =~ ^[0-9]+$ ]] && (( t2 > t1 )); then
    awk -v ds="$((s2-s1))" -v dt="$((t2-t1))" 'BEGIN{printf "%.2f",100*ds/dt}'
  else printf 'UNKNOWN'; fi
}

v20_cpu_quota(){
  if (( DEMO )); then printf '%s|%s' "$CORES" NORMAL; return; fi
  local quota period cores state=NORMAL
  if [[ -r /sys/fs/cgroup/cpu.max ]]; then
    read -r quota period </sys/fs/cgroup/cpu.max || true
    if [[ "$quota" == max || -z "$quota" ]]; then printf '无限制|NORMAL'; return; fi
  elif [[ -r /sys/fs/cgroup/cpu/cpu.cfs_quota_us && -r /sys/fs/cgroup/cpu/cpu.cfs_period_us ]]; then
    quota="$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null)"
    period="$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null)"
    if [[ "$quota" == -1 ]]; then printf '无限制|NORMAL'; return; fi
  else printf '未知|UNKNOWN'; return; fi
  if [[ "$quota" =~ ^[0-9]+$ && "$period" =~ ^[0-9]+$ && "$period" -gt 0 ]]; then
    cores="$(awk -v q="$quota" -v p="$period" 'BEGIN{printf "%.2f",q/p}')"
    if awk -v q="$cores" -v c="${CORES:-1}" 'BEGIN{exit !(q+0.01<c*0.90)}'; then state=LIMITED; fi
    printf '%s 核|%s' "$cores" "$state"
  else printf '未知|UNKNOWN'; fi
}

v20_cpu_bench(){
  local multi workers out single total
  if (( DEMO )); then printf '780.0|1420.0'; return; fi
  command -v openssl >/dev/null 2>&1 || { printf 'UNKNOWN|UNKNOWN'; return; }
  out="$(timeout 12s openssl speed -seconds 2 -evp sha256 2>&1 || true)"
  single="$(awk '$1=="sha256"{x=$NF; gsub(/k/,"",x); if(x~/^[0-9.]+$/)printf "%.1f",x/1000}' <<<"$out" | tail -n1)"
  workers="${CORES:-1}"; [[ "$workers" =~ ^[0-9]+$ ]] || workers=1; (( workers > 4 )) && workers=4; (( workers < 1 )) && workers=1
  if (( workers > 1 )); then
    out="$(timeout 15s openssl speed -seconds 2 -multi "$workers" -evp sha256 2>&1 || true)"
    total="$(awk '$1=="sha256"{x=$NF; gsub(/k/,"",x); if(x~/^[0-9.]+$/)printf "%.1f",x/1000}' <<<"$out" | tail -n1)"
  else total="$single"; fi
  printf '%s|%s' "${single:-UNKNOWN}" "${total:-UNKNOWN}"
}

v20_cpu_test(){
  rule
  printf '%s%s CPU 真实表现%s\n' "$BOLD" "$MAGENTA" "$RESET"
  V20_CPU_STEAL="$(v20_cpu_steal)"
  IFS='|' read -r V20_CPU_QUOTA V20_CPU_QUOTA_STATE <<<"$(v20_cpu_quota)"
  IFS='|' read -r V20_CPU_SINGLE V20_CPU_MULTI <<<"$(v20_cpu_bench)"
  printf ' CPU Steal          : %s%%  （宿主机争抢信号，越低越好）\n' "$V20_CPU_STEAL"
  if [[ "$V20_CPU_QUOTA_STATE" == LIMITED ]]; then
    printf ' CPU 配额           : %s%s%s  （低于系统可见 %s 核）\n' "$RED" "$V20_CPU_QUOTA" "$RESET" "$CORES"
  else
    printf ' CPU 配额           : %s\n' "$V20_CPU_QUOTA"
  fi
  if [[ "$V20_CPU_SINGLE" != UNKNOWN ]]; then
    printf ' SHA256 单核        : %s MB/s\n' "$V20_CPU_SINGLE"
    printf ' SHA256 多核        : %s MB/s  （最多使用 4 核）\n' "$V20_CPU_MULTI"
  else
    printf ' CPU 轻量跑分       : 未执行（缺少 OpenSSL）\n'
  fi
}

v20_disk_sync_probe(){
  local file="$BENCH_DIR/.p07-v20-disk-$$.bin"
  if (( DEMO )); then printf '820|1.20|2.80'; return; fi
  command -v python3 >/dev/null 2>&1 || { printf 'UNKNOWN|UNKNOWN|UNKNOWN'; return; }
  python3 - "$file" <<'PYV20DISK' 2>/dev/null || printf 'UNKNOWN|UNKNOWN|UNKNOWN'
import os,sys,time,random,statistics
p=sys.argv[1]
try:
    fd=os.open(p,os.O_CREAT|os.O_RDWR|os.O_TRUNC,0o600)
    size=16*1024*1024
    os.ftruncate(fd,size)
    buf=b'0'*4096
    n=128
    start=time.perf_counter()
    for _ in range(n):
        off=random.randrange(0,size//4096)*4096
        os.pwrite(fd,buf,off)
        os.fdatasync(fd)
    elapsed=time.perf_counter()-start
    iops=n/elapsed if elapsed>0 else 0
    samples=[]
    for _ in range(40):
        off=random.randrange(0,size//4096)*4096
        t=time.perf_counter(); os.pwrite(fd,buf,off); os.fsync(fd); samples.append((time.perf_counter()-t)*1000)
    os.close(fd); os.unlink(p)
    s=sorted(samples); p95=s[max(0,min(len(s)-1,int(len(s)*0.95)-1))]
    print(f'{iops:.0f}|{statistics.mean(samples):.2f}|{p95:.2f}')
except Exception:
    try: os.close(fd)
    except Exception: pass
    try: os.unlink(p)
    except Exception: pass
    raise
PYV20DISK
}

v20_disk_test(){
  printf '%s%s 磁盘数据库型负载%s\n' "$BOLD" "$MAGENTA" "$RESET"
  if (( ! DEMO )); then
    [[ -d "$BENCH_DIR" && -w "$BENCH_DIR" ]] || { printf ' 4K / fsync         : 目录不可写，已跳过\n'; return; }
    local fs; fs="$(df -PT "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $2}')"
    [[ "$fs" != tmpfs && "$fs" != devtmpfs ]] || { printf ' 4K / fsync         : 内存文件系统，已跳过\n'; return; }
  fi
  IFS='|' read -r V20_DISK_IOPS V20_FSYNC_AVG V20_FSYNC_P95 <<<"$(v20_disk_sync_probe)"
  if [[ "$V20_DISK_IOPS" != UNKNOWN ]]; then
    printf ' 4K 同步写 IOPS     : %s\n' "$V20_DISK_IOPS"
    printf ' fsync 平均延迟     : %s ms\n' "$V20_FSYNC_AVG"
    printf ' fsync P95 延迟     : %s ms\n' "$V20_FSYNC_P95"
  else
    printf ' 4K / fsync         : 未执行（缺少 Python3 或文件系统不支持）\n'
  fi
}

v20_ping_target(){
  local target="$1" out loss jitter
  out="$(ping -n -c 10 -i 0.2 -W 1 "$target" 2>/dev/null || true)"
  loss="$(grep -oE '[0-9.]+% packet loss' <<<"$out" | tail -n1 | awk '{print $1}' | tr -d '%')"
  jitter="$(awk -F'=' '/(rtt|round-trip).*min\/avg\/max\/(mdev|stddev)/{gsub(/ ms/,"",$2); split($2,a,"/"); gsub(/ /,"",a[4]); print a[4]}' <<<"$out" | tail -n1)"
  [[ "$loss" =~ ^[0-9.]+$ ]] || return 1
  [[ "$jitter" =~ ^[0-9.]+$ ]] || jitter=UNKNOWN
  printf '%s|%s' "$loss" "$jitter"
}

v20_ping_stability(){
  if (( DEMO )); then printf 'PASS|0.0|0.45|3'; return; fi
  command -v ping >/dev/null 2>&1 || { printf 'NOT_RUN|UNKNOWN|UNKNOWN|0'; return; }
  local t r loss jit ok=0 worst=0 maxjit=0
  for t in 1.1.1.1 8.8.8.8 9.9.9.9; do
    r="$(v20_ping_target "$t" || true)"; [[ -n "$r" ]] || continue
    IFS='|' read -r loss jit <<<"$r"; ok=$((ok+1))
    worst="$(awk -v a="$worst" -v b="$loss" 'BEGIN{print (b>a)?b:a}')"
    if [[ "$jit" =~ ^[0-9.]+$ ]]; then maxjit="$(awk -v a="$maxjit" -v b="$jit" 'BEGIN{print (b>a)?b:a}')"; fi
  done
  if (( ok == 0 )); then printf 'NOT_RUN|UNKNOWN|UNKNOWN|0'; else printf 'PASS|%s|%s|%s' "$worst" "$maxjit" "$ok"; fi
}

v20_https_stability(){
  if (( DEMO )); then printf '15|15|8.40'; return; fi
  command -v curl >/dev/null 2>&1 || { printf '0|0|UNKNOWN'; return; }
  local url i result code t tmp="$TMP_DIR/v20-https.tsv"
  : >"$tmp"
  for url in 'https://www.cloudflare.com/cdn-cgi/trace' 'https://github.com/' 'https://www.google.com/generate_204'; do
    for i in 1 2 3 4 5; do
      result="$(curl -LsS -o /dev/null --connect-timeout 4 --max-time 8 -w '%{http_code}|%{time_starttransfer}' "$url" 2>/dev/null || true)"
      IFS='|' read -r code t <<<"$result"
      if [[ "$code" =~ ^[23][0-9][0-9]$ && "$t" =~ ^[0-9.]+$ ]]; then printf '1\t%s\n' "$t" >>"$tmp"; else printf '0\t0\n' >>"$tmp"; fi
    done
  done
  awk -F '\t' '{n++; if($1==1){p++; x=$2*1000; s+=x; ss+=x*x}} END{if(p>1){m=s/p; v=ss/p-m*m; if(v<0)v=0; j=sqrt(v); printf "%d|%d|%.2f",p,n,j}else printf "%d|%d|UNKNOWN",p,n}' "$tmp"
}

v20_network_stability(){
  rule
  printf '%s%s 网络稳定性%s\n' "$BOLD" "$MAGENTA" "$RESET"
  local ping_ok
  IFS='|' read -r V20_PING_STATE V20_PING_LOSS V20_PING_JITTER ping_ok <<<"$(v20_ping_stability)"
  IFS='|' read -r V20_HTTPS_PASS V20_HTTPS_TOTAL V20_HTTPS_JITTER <<<"$(v20_https_stability)"
  if [[ "$V20_PING_STATE" == PASS ]]; then
    printf ' ICMP 丢包（最差）  : %s%%  （%s/3 个探针有效）\n' "$V20_PING_LOSS" "$ping_ok"
    printf ' ICMP 抖动（最差）  : %s ms\n' "$V20_PING_JITTER"
  else
    printf ' ICMP 丢包/抖动     : 未执行（机房可能禁 ICMP，不直接判坏）\n'
  fi
  printf ' HTTPS 稳定性       : %s/%s 成功\n' "$V20_HTTPS_PASS" "$V20_HTTPS_TOTAL"
  printf ' HTTPS 响应抖动     : %s ms\n' "$V20_HTTPS_JITTER"
}

v20_dns_health(){
  if (( DEMO )); then printf '4|4'; return; fi
  local h ok=0 total=0
  for h in github.com cloudflare.com google.com baidu.com; do
    total=$((total+1))
    if command -v getent >/dev/null 2>&1 && getent ahosts "$h" >/dev/null 2>&1; then ok=$((ok+1));
    elif command -v nslookup >/dev/null 2>&1 && nslookup "$h" >/dev/null 2>&1; then ok=$((ok+1)); fi
  done
  printf '%s|%s' "$ok" "$total"
}

v20_ip_test(){
  rule
  printf '%s%s IP 与基础可达性%s\n' "$BOLD" "$MAGENTA" "$RESET"
  IFS='|' read -r V20_DNS_PASS V20_DNS_TOTAL <<<"$(v20_dns_health)"
  printf ' DNS 解析           : %s/%s 正常\n' "$V20_DNS_PASS" "$V20_DNS_TOTAL"
  printf ' HTTPS 基础连通     : %s/%s 正常\n' "$V20_HTTPS_PASS" "$V20_HTTPS_TOTAL"
  printf ' ASN / 运营商       : %s\n' "${ORG:-未知}"
  if [[ "$IPV4" != OFFLINE && "$ORG" != UNKNOWN && "$V20_DNS_PASS" -ge 3 && "$V20_HTTPS_PASS" -ge 12 ]]; then V20_IP_HEALTH=NORMAL; else V20_IP_HEALTH=PARTIAL; fi
  printf ' IP 基础健康        : '; color_state "$V20_IP_HEALTH"; printf '\n'
  printf ' 说明               : 这里只检查基础健康，不使用不可靠的免费黑名单给 IP 下结论\n'
}

v20_score_and_verdict(){
  local score=0 tested=0 global sea seq
  global="$(awk -F '\t' '$3=="PASS" && $2!="Cloudflare Edge"{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  sea="$(awk -F '\t' '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Bangkok)/{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"

  # Network 50
  tested=$((tested+20)); if (( global>=7 )); then score=$((score+20)); elif ((global>=5)); then score=$((score+16)); elif ((global>=3)); then score=$((score+10)); else score=$((score+4)); fi
  tested=$((tested+10)); if (( sea>=3 )); then score=$((score+10)); elif ((sea==2)); then score=$((score+7)); elif ((sea==1)); then score=$((score+3)); fi
  if [[ "$V20_PING_STATE" == PASS && "$V20_PING_LOSS" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+10));
    if awk -v x="$V20_PING_LOSS" 'BEGIN{exit !(x<=1)}'; then score=$((score+10)); elif awk -v x="$V20_PING_LOSS" 'BEGIN{exit !(x<=3)}'; then score=$((score+7)); elif awk -v x="$V20_PING_LOSS" 'BEGIN{exit !(x<=5)}'; then score=$((score+4)); else v20_add_issue "网络丢包偏高（${V20_PING_LOSS}%）"; fi
  fi
  tested=$((tested+10)); if (( V20_HTTPS_TOTAL>0 && V20_HTTPS_PASS==V20_HTTPS_TOTAL )); then score=$((score+10)); elif (( V20_HTTPS_PASS>=12 )); then score=$((score+7)); else v20_add_issue "HTTPS 稳定性不足（${V20_HTTPS_PASS}/${V20_HTTPS_TOTAL}）"; fi

  # CPU 15
  if [[ "$V20_CPU_STEAL" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+8));
    if awk -v x="$V20_CPU_STEAL" 'BEGIN{exit !(x<=2)}'; then score=$((score+8)); elif awk -v x="$V20_CPU_STEAL" 'BEGIN{exit !(x<=5)}'; then score=$((score+6)); elif awk -v x="$V20_CPU_STEAL" 'BEGIN{exit !(x<=10)}'; then score=$((score+3)); v20_add_issue "CPU Steal 偏高（${V20_CPU_STEAL}%）"; else v20_add_issue "CPU Steal 很高（${V20_CPU_STEAL}%）"; fi
  fi
  if [[ "$V20_CPU_QUOTA_STATE" != UNKNOWN ]]; then tested=$((tested+4)); if [[ "$V20_CPU_QUOTA_STATE" == NORMAL ]]; then score=$((score+4)); else v20_add_issue "CPU 配额低于系统可见核心"; fi; fi
  if [[ "$V20_CPU_SINGLE" != UNKNOWN ]]; then tested=$((tested+3)); score=$((score+3)); fi

  # Disk 15
  if [[ "$IO_STATE" == PASS && "$IO_AVG_MB" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+5));
    if awk -v x="$IO_AVG_MB" 'BEGIN{exit !(x>=500)}'; then score=$((score+5)); elif awk -v x="$IO_AVG_MB" 'BEGIN{exit !(x>=200)}'; then score=$((score+4)); elif awk -v x="$IO_AVG_MB" 'BEGIN{exit !(x>=100)}'; then score=$((score+3)); else score=$((score+1)); v20_add_issue "顺序磁盘写入较慢"; fi
  fi
  if [[ "$V20_DISK_IOPS" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+5));
    if awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=1000)}'; then score=$((score+5)); elif awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=300)}'; then score=$((score+4)); elif awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=100)}'; then score=$((score+3)); elif awk -v x="$V20_DISK_IOPS" 'BEGIN{exit !(x>=30)}'; then score=$((score+2)); else v20_add_issue "4K 同步写 IOPS 很低"; fi
  fi
  if [[ "$V20_FSYNC_P95" =~ ^[0-9.]+$ ]]; then
    tested=$((tested+5));
    if awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<5)}'; then score=$((score+5)); elif awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<10)}'; then score=$((score+4)); elif awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<20)}'; then score=$((score+3)); elif awk -v x="$V20_FSYNC_P95" 'BEGIN{exit !(x<50)}'; then score=$((score+1)); v20_add_issue "fsync 延迟偏高"; else v20_add_issue "fsync 延迟很高"; fi
  fi

  # IP 10
  tested=$((tested+10)); if [[ "$V20_IP_HEALTH" == NORMAL ]]; then score=$((score+10)); else score=$((score+5)); v20_add_issue "IP/DNS/HTTPS 基础健康存在缺项"; fi

  V20_SCORE="$score"; V20_COMPLETENESS="$tested"
  local normalized=0
  (( tested>0 )) && normalized=$(( score*100/tested ))
  if (( normalized>=85 )); then V20_GRADE=GOOD; V20_ADVICE='建议保留';
  elif (( normalized>=70 )); then V20_GRADE=FAIR; V20_ADVICE='可以使用，建议观察';
  elif (( normalized>=55 )); then V20_GRADE=CAUTION; V20_ADVICE='谨慎保留，建议观察稳定性';
  else V20_GRADE=POOR; V20_ADVICE='建议更换或先排查明显问题'; fi
  if (( tested<75 )); then
    [[ "$V20_GRADE" == GOOD ]] && V20_GRADE=FAIR
    V20_ADVICE="${V20_ADVICE}（部分测试未完成）"
  fi
}

v20_grade_zh(){
  case "$1" in GOOD) printf '良好';; FAIR) printf '一般';; CAUTION) printf '偏弱';; POOR) printf '较差';; *) printf '未知';; esac
}

v20_final_verdict(){
  v20_score_and_verdict
  local global sea
  global="$(awk -F '\t' '$3=="PASS" && $2!="Cloudflare Edge"{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  sea="$(awk -F '\t' '$3=="PASS" && $2~/(Singapore|Kuala Lumpur|Bangkok)/{seen[$2]=1} END{for(k in seen)n++;print n+0}' "$NETWORK_TSV")"
  rule
  printf '%s%s 最终验机结论%s\n' "$BOLD" "$BLUE" "$RESET"
  printf ' 综合评级           : %s%s%s\n' "$GREEN" "$(v20_grade_zh "$V20_GRADE")" "$RESET"
  printf ' 建议               : %s%s%s\n' "$YELLOW" "$V20_ADVICE" "$RESET"
  printf ' 评分 / 证据完整度  : %s / %s%%\n' "$V20_SCORE" "$V20_COMPLETENESS"
  printf ' 全球有效测速       : %s 个地区\n' "$global"
  printf ' 东南亚有效测速     : %s/3\n' "$sea"
  printf ' CPU Steal          : %s%%\n' "$V20_CPU_STEAL"
  printf ' 磁盘 4K IOPS       : %s\n' "$V20_DISK_IOPS"
  printf ' 网络丢包           : %s\n' "$([[ "$V20_PING_STATE" == PASS ]] && printf '%s%%' "$V20_PING_LOSS" || printf '未直接测得')"
  printf ' IP 基础健康        : '; color_state "$V20_IP_HEALTH"; printf '\n'
  printf ' 中国大陆入站       : %s未直接检测%s（需要大陆来源探针，当前不据此扣分）\n' "$YELLOW" "$RESET"
  if [[ -n "$V20_ISSUES" ]]; then printf ' 主要问题           : %s%s%s\n' "$YELLOW" "$V20_ISSUES" "$RESET"; else printf ' 主要问题           : 未发现明显硬伤\n'; fi
}

v20_patch_report_json(){
  [[ -f "${REPORT_JSON:-}" ]] || return 0
  command -v python3 >/dev/null 2>&1 || return 0
  python3 - "$REPORT_JSON" "$V20_CPU_STEAL" "$V20_CPU_QUOTA" "$V20_CPU_QUOTA_STATE" "$V20_CPU_SINGLE" "$V20_CPU_MULTI" "$V20_DISK_IOPS" "$V20_FSYNC_AVG" "$V20_FSYNC_P95" "$V20_PING_STATE" "$V20_PING_LOSS" "$V20_PING_JITTER" "$V20_HTTPS_PASS" "$V20_HTTPS_TOTAL" "$V20_HTTPS_JITTER" "$V20_DNS_PASS" "$V20_DNS_TOTAL" "$V20_IP_HEALTH" "$V20_SCORE" "$V20_COMPLETENESS" "$V20_GRADE" "$V20_ADVICE" "$V20_ISSUES" <<'PYV20JSON' 2>/dev/null || true
import json,sys
p=sys.argv[1]; a=sys.argv[2:]
try:
 d=json.load(open(p,encoding='utf-8'))
 d['schema_version']=4
 d['vps_audit_v20']={
  'cpu':{'steal_percent':a[0],'quota':a[1],'quota_state':a[2],'sha256_single_mb_s':a[3],'sha256_multi_mb_s':a[4]},
  'disk':{'sync_4k_iops':a[5],'fsync_avg_ms':a[6],'fsync_p95_ms':a[7]},
  'stability':{'icmp_state':a[8],'worst_loss_percent':a[9],'worst_jitter_ms':a[10],'https_pass':int(a[11]),'https_total':int(a[12]),'https_ttfb_jitter_ms':a[13]},
  'ip_health':{'dns_pass':int(a[14]),'dns_total':int(a[15]),'state':a[16]},
  'verdict':{'score':int(a[17]),'evidence_completeness_percent':int(a[18]),'grade':a[19],'advice':a[20],'issues':[x for x in a[21].split('；') if x]},
  'mainland_inbound_probe':'NOT_RUN'
 }
 json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
except Exception: pass
PYV20JSON
}

v20_self_test(){
  local old="$DEMO" f=0
  DEMO=1
  collect_system
  v20_cpu_test >/dev/null || f=1
  print_io >/dev/null || f=1
  v20_disk_test >/dev/null || f=1
  : >"$NETWORK_TSV"
  for n in 'US West' 'US East' 'Europe' 'Hong Kong' 'Singapore' 'Kuala Lumpur' 'Bangkok' 'Tokyo'; do
    printf 'demo\t%s\tPASS\tSPEEDTESTGO_FALLBACK\t500\t600\t50\n' "$n" >>"$NETWORK_TSV"
  done
  v20_network_stability >/dev/null || f=1
  v20_ip_test >/dev/null || f=1
  v20_final_verdict >/dev/null || f=1
  [[ "$V20_CPU_STEAL" == '0.30' ]] || f=1
  [[ "$V20_DISK_IOPS" == '820' ]] || f=1
  [[ "$V20_HTTPS_PASS" == '15' ]] || f=1
  [[ "$V20_GRADE" == GOOD ]] || f=1
  DEMO="$old"
  (( f==0 )) && printf 'V20_SELF_TEST=PASS\n' || { printf 'V20_SELF_TEST=FAIL\n'; return 1; }
}
# ===== /P07 VPS Audit 2.0 =====

'''

s = s.replace(marker, block + marker, 1)
s = s.replace('if (( SELF_TEST )); then self_test; exit $?; fi', 'if (( SELF_TEST )); then self_test && v20_self_test; exit $?; fi')
old_flow = 'collect_system\nprint_system\nprint_io\nprint_network\nchina_assessment\nrule\n'
new_flow = 'collect_system\nprint_system\nv20_cpu_test\nprint_io\nv20_disk_test\nprint_network\nv20_network_stability\nv20_ip_test\nv20_final_verdict\nrule\n'
if old_flow not in s:
    raise SystemExit('main flow marker not found')
s = s.replace(old_flow, new_flow, 1)
s = s.replace('write_reports\nprintf \' 中文报告', 'write_reports\nv20_patch_report_json\nprintf \' 中文报告', 1)
p.write_text(s, encoding='utf-8')
print('PATCH_V20_RC1=OK')
