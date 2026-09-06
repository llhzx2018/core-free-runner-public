from pathlib import Path
import re

p=Path('experiments/p07-bench.sh')
s=p.read_text(encoding='utf-8')
s=s.replace('VERSION="2.0.0-rc2-zh"','VERSION="2.0.0-rc3-zh"',1)

s=s.replace('V20_CPU_LOAD_STEAL="UNKNOWN"\nV20_GLOBAL_MEDIAN_UP=', 'V20_CPU_LOAD_STEAL="UNKNOWN"\nV20_CPU_SCALE_EFF="UNKNOWN"\nV20_CGROUP_BASE="UNKNOWN"\nV20_MEM_LIMIT="UNKNOWN"\nV20_SWAP_LIMIT="UNKNOWN"\nV20_PIDS_LIMIT="UNKNOWN"\nV20_GLOBAL_MEDIAN_UP=',1)

helpers=r'''v20_cgroup2_base(){
  local rel base
  rel="$(awk -F: '$1=="0"{print $3; exit}' /proc/self/cgroup 2>/dev/null)"
  [[ -n "$rel" ]] || rel='/'
  base="/sys/fs/cgroup${rel%/}"
  if [[ -d "$base" ]]; then printf '%s' "$base"; return; fi
  [[ -d /sys/fs/cgroup ]] && printf '/sys/fs/cgroup' || printf 'UNKNOWN'
}

v20_human_limit(){
  local x="$1"
  if [[ "$x" == max || "$x" == '-1' ]]; then printf '无限制';
  elif [[ "$x" =~ ^[0-9]+$ ]]; then awk -v x="$x" 'BEGIN{if(x>=1073741824)printf "%.2f GiB",x/1073741824; else if(x>=1048576)printf "%.1f MiB",x/1048576; else printf "%s B",x}'
  else printf '未知'; fi
}

v20_read_resource_limits(){
  local base raw
  base="$(v20_cgroup2_base)"; V20_CGROUP_BASE="$base"
  if [[ "$base" != UNKNOWN && -r "$base/memory.max" ]]; then raw="$(cat "$base/memory.max" 2>/dev/null)"; V20_MEM_LIMIT="$(v20_human_limit "$raw")"; else V20_MEM_LIMIT=UNKNOWN; fi
  if [[ "$base" != UNKNOWN && -r "$base/memory.swap.max" ]]; then raw="$(cat "$base/memory.swap.max" 2>/dev/null)"; V20_SWAP_LIMIT="$(v20_human_limit "$raw")"; else V20_SWAP_LIMIT=UNKNOWN; fi
  if [[ "$base" != UNKNOWN && -r "$base/pids.max" ]]; then raw="$(cat "$base/pids.max" 2>/dev/null)"; [[ "$raw" == max ]] && V20_PIDS_LIMIT='无限制' || V20_PIDS_LIMIT="${raw:-UNKNOWN}"; else V20_PIDS_LIMIT=UNKNOWN; fi
}

'''
s=s.replace('v20_cpu_quota(){\n',helpers+'v20_cpu_quota(){\n',1)

quota=r'''v20_cpu_quota(){
  if (( DEMO )); then printf '%s 核|%s' "$CORES" NORMAL; return; fi
  local quota period cores state=NORMAL base rel
  base="$(v20_cgroup2_base)"
  if [[ "$base" != UNKNOWN && -r "$base/cpu.max" ]]; then
    read -r quota period <"$base/cpu.max" || true
    if [[ "$quota" == max || -z "$quota" ]]; then printf '无限制|NORMAL'; return; fi
  elif [[ -r /sys/fs/cgroup/cpu.max ]]; then
    read -r quota period </sys/fs/cgroup/cpu.max || true
    if [[ "$quota" == max || -z "$quota" ]]; then printf '无限制|NORMAL'; return; fi
  elif [[ -r /sys/fs/cgroup/cpu/cpu.cfs_quota_us && -r /sys/fs/cgroup/cpu/cpu.cfs_period_us ]]; then
    quota="$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null)"; period="$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null)"
    if [[ "$quota" == -1 ]]; then printf '无限制|NORMAL'; return; fi
  else printf '未知|UNKNOWN'; return; fi
  if [[ "$quota" =~ ^[0-9]+$ && "$period" =~ ^[0-9]+$ && "$period" -gt 0 ]]; then
    cores="$(awk -v q="$quota" -v p="$period" 'BEGIN{printf "%.2f",q/p}')"
    if awk -v q="$cores" -v c="${CORES:-1}" 'BEGIN{exit !(q+0.01<c*0.90)}'; then state=LIMITED; fi
    printf '%s 核|%s' "$cores" "$state"
  else printf '未知|UNKNOWN'; fi
}'''
s,n=re.subn(r'v20_cpu_quota\(\)\{.*?\n\}',quota,s,count=1,flags=re.S)
if n!=1: raise SystemExit('quota not replaced')

# Calculate multi-core scaling after the benchmark.
s=s.replace("IFS='|' read -r V20_CPU_BENCH_STATE V20_CPU_SINGLE V20_CPU_MULTI V20_CPU_LOAD_STEAL <<<\"$(v20_cpu_bench)\"", "IFS='|' read -r V20_CPU_BENCH_STATE V20_CPU_SINGLE V20_CPU_MULTI V20_CPU_LOAD_STEAL <<<\"$(v20_cpu_bench)\"\n  if [[ \"$V20_CPU_BENCH_STATE\" == PASS && \"$V20_CPU_SINGLE\" =~ ^[0-9.]+$ && \"$V20_CPU_MULTI\" =~ ^[0-9.]+$ ]]; then local w=\"${CORES:-1}\"; [[ \"$w\" =~ ^[0-9]+$ ]] || w=1; ((w>4))&&w=4; ((w<1))&&w=1; V20_CPU_SCALE_EFF=\"$(awk -v m=\"$V20_CPU_MULTI\" -v s=\"$V20_CPU_SINGLE\" -v w=\"$w\" 'BEGIN{if(s>0&&w>0){x=100*m/(s*w); if(x>120)x=120; printf \"%.1f\",x}else print \"UNKNOWN\"}')\"; fi")
s=s.replace("      printf ' SHA256 多核        : %s MB/s  （最多使用 4 核）\\n' \"$V20_CPU_MULTI\"", "      printf ' SHA256 多核        : %s MB/s  （最多使用 4 核）\\n' \"$V20_CPU_MULTI\"\n      printf ' 多核扩展效率       : %s%%\\n' \"$V20_CPU_SCALE_EFF\"")

# Resource health now includes current-process memory/PID limits and detects hidden caps.
resource=r'''v20_resource_health(){
  v20_read_resource_limits
  if [[ "$V20_CPU_QUOTA_STATE" == LIMITED ]]; then V20_RESOURCE_STATE=LIMITED; v20_add_issue "检测到 CPU cgroup 配额低于系统可见核心"; return; fi
  local base raw mem_kb mem_bytes limited=0 evidence=0
  [[ "$V20_CPU_QUOTA_STATE" == NORMAL ]] && evidence=$((evidence+1))
  [[ "$V20_MEM_LIMIT" != UNKNOWN ]] && evidence=$((evidence+1))
  [[ "$V20_SWAP_LIMIT" != UNKNOWN ]] && evidence=$((evidence+1))
  [[ "$V20_PIDS_LIMIT" != UNKNOWN ]] && evidence=$((evidence+1))
  base="$V20_CGROUP_BASE"
  if [[ "$base" != UNKNOWN && -r "$base/memory.max" ]]; then
    raw="$(cat "$base/memory.max" 2>/dev/null)"; mem_kb="$(awk '/MemTotal:/{print $2;exit}' /proc/meminfo 2>/dev/null)"
    if [[ "$raw" =~ ^[0-9]+$ && "$mem_kb" =~ ^[0-9]+$ ]]; then
      mem_bytes=$((mem_kb*1024))
      if awk -v lim="$raw" -v visible="$mem_bytes" 'BEGIN{exit !(lim<visible*0.90)}'; then limited=1; v20_add_issue "cgroup 内存上限低于系统可见内存"; fi
    fi
  fi
  if [[ "$V20_PIDS_LIMIT" =~ ^[0-9]+$ ]] && (( V20_PIDS_LIMIT<256 )); then limited=1; v20_add_issue "进程数上限偏低（${V20_PIDS_LIMIT}）"; fi
  if (( limited )); then V20_RESOURCE_STATE=LIMITED
  elif (( evidence>=4 )); then V20_RESOURCE_STATE=NORMAL
  elif (( evidence>=2 )); then V20_RESOURCE_STATE=PARTIAL
  else V20_RESOURCE_STATE=UNKNOWN
  fi
}'''
s,n=re.subn(r'v20_resource_health\(\)\{.*?\n\}',resource,s,count=1,flags=re.S)
if n!=1: raise SystemExit('resource health rc3 not replaced')

# CPU 3 points now measure multi-core scaling, not mere command execution.
s=s.replace("if [[ \"$V20_CPU_BENCH_STATE\" == PASS ]]; then tested=$((tested+3)); score=$((score+3)); fi", "if [[ \"$V20_CPU_BENCH_STATE\" == PASS && \"$V20_CPU_SCALE_EFF\" =~ ^[0-9.]+$ ]]; then tested=$((tested+3)); if awk -v x=\"$V20_CPU_SCALE_EFF\" 'BEGIN{exit !(x>=75)}'; then score=$((score+3)); elif awk -v x=\"$V20_CPU_SCALE_EFF\" 'BEGIN{exit !(x>=55)}'; then score=$((score+2)); elif awk -v x=\"$V20_CPU_SCALE_EFF\" 'BEGIN{exit !(x>=35)}'; then score=$((score+1)); else v20_add_issue \"CPU 多核扩展效率偏低（${V20_CPU_SCALE_EFF}%）\"; fi; fi")

# Use-case fit helpers.
usecase=r'''v20_usecase_fit(){
  V20_SITE_FIT='观察'
  V20_SEA_FIT='较弱'
  V20_DB_FIT='较弱'
  if [[ "$V20_IP_HEALTH" == NORMAL && "$V20_HTTPS_PASS" -ge 12 && "$V20_GRADE" != POOR ]]; then V20_SITE_FIT='适合'; fi
  if [[ "$V20_SEA_MEDIAN_UP" =~ ^[0-9.]+$ && "$V20_SEA_MEDIAN_DOWN" =~ ^[0-9.]+$ ]]; then
    if awk -v u="$V20_SEA_MEDIAN_UP" -v d="$V20_SEA_MEDIAN_DOWN" 'BEGIN{exit !(u>=50&&d>=50)}'; then V20_SEA_FIT='良好'
    elif awk -v u="$V20_SEA_MEDIAN_UP" -v d="$V20_SEA_MEDIAN_DOWN" 'BEGIN{exit !(u>=20&&d>=20)}'; then V20_SEA_FIT='可用'; fi
  fi
  if [[ "$V20_DISK_IOPS" =~ ^[0-9.]+$ && "$V20_FSYNC_P95" =~ ^[0-9.]+$ ]]; then
    if awk -v i="$V20_DISK_IOPS" -v l="$V20_FSYNC_P95" 'BEGIN{exit !(i>=500&&l<10)}'; then V20_DB_FIT='良好'
    elif awk -v i="$V20_DISK_IOPS" -v l="$V20_FSYNC_P95" 'BEGIN{exit !(i>=100&&l<20)}'; then V20_DB_FIT='一般'; fi
  fi
}

'''
s=s.replace('v20_final_verdict(){\n  v20_score_and_verdict',usecase+'v20_final_verdict(){\n  v20_score_and_verdict\n  v20_usecase_fit',1)

s=s.replace("  printf ' 磁盘 4K IOPS       : %s\\n' \"$V20_DISK_IOPS\"", "  printf ' CPU 多核效率       : %s%%\\n' \"$V20_CPU_SCALE_EFF\"\n  printf ' 磁盘 4K IOPS       : %s\\n' \"$V20_DISK_IOPS\"")
s=s.replace("  printf ' 资源说明           : 未输入购买套餐，本项只检查隐藏限额/异常，不声称套餐规格完全一致\\n'", "  printf ' 内存 cgroup 上限   : %s\\n' \"$V20_MEM_LIMIT\"\n  printf ' Swap cgroup 上限   : %s\\n' \"$V20_SWAP_LIMIT\"\n  printf ' 进程数上限         : %s\\n' \"$V20_PIDS_LIMIT\"\n  printf ' 资源说明           : 未输入购买套餐，本项只检查隐藏限额/异常，不声称套餐规格完全一致\\n'")
s=s.replace("  if [[ -n \"$V20_ISSUES\" ]]; then printf ' 主要问题", "  printf ' 常规网站/WordPress : %s\\n' \"$V20_SITE_FIT\"\n  printf ' 东南亚业务         : %s\\n' \"$V20_SEA_FIT\"\n  printf ' 数据库型负载       : %s\\n' \"$V20_DB_FIT\"\n  printf ' 时段说明           : 本次为即时验机；陌生商家建议晚高峰再运行同一命令复测\\n'\n  if [[ -n \"$V20_ISSUES\" ]]; then printf ' 主要问题")

# JSON additions.
s=s.replace("'bench_state':__import__('os').environ.get('P07_V20_CPU_BENCH_STATE','UNKNOWN'),'load_steal_percent':__import__('os').environ.get('P07_V20_CPU_LOAD_STEAL','UNKNOWN')", "'bench_state':__import__('os').environ.get('P07_V20_CPU_BENCH_STATE','UNKNOWN'),'load_steal_percent':__import__('os').environ.get('P07_V20_CPU_LOAD_STEAL','UNKNOWN'),'multi_core_efficiency_percent':__import__('os').environ.get('P07_V20_CPU_SCALE_EFF','UNKNOWN')")
s=s.replace("'resource_constraints':{'state':__import__('os').environ.get('P07_V20_RESOURCE_STATE','UNKNOWN'),'scope':'HIDDEN_LIMIT_SIGNALS_ONLY'}", "'resource_constraints':{'state':__import__('os').environ.get('P07_V20_RESOURCE_STATE','UNKNOWN'),'scope':'HIDDEN_LIMIT_SIGNALS_ONLY','memory_limit':__import__('os').environ.get('P07_V20_MEM_LIMIT','UNKNOWN'),'swap_limit':__import__('os').environ.get('P07_V20_SWAP_LIMIT','UNKNOWN'),'pids_limit':__import__('os').environ.get('P07_V20_PIDS_LIMIT','UNKNOWN')}")
s=s.replace('P07_V20_RESOURCE_STATE="$V20_RESOURCE_STATE" P07_V20_CPU_BENCH_STATE=', 'P07_V20_RESOURCE_STATE="$V20_RESOURCE_STATE" P07_V20_MEM_LIMIT="$V20_MEM_LIMIT" P07_V20_SWAP_LIMIT="$V20_SWAP_LIMIT" P07_V20_PIDS_LIMIT="$V20_PIDS_LIMIT" P07_V20_CPU_SCALE_EFF="$V20_CPU_SCALE_EFF" P07_V20_CPU_BENCH_STATE=',1)

p.write_text(s,encoding='utf-8')
print('PATCH_V20_RC3=OK')
