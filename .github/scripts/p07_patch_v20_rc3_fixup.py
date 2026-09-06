from pathlib import Path
import re

p=Path('experiments/p07-bench.sh')
s=p.read_text(encoding='utf-8')

# Healthy demo should not deliberately model poor multi-core scaling.
s=s.replace("if (( DEMO )); then printf 'PASS|780.0|1420.0|0.40'; return; fi", "if (( DEMO )); then printf 'PASS|780.0|2800.0|0.40'; return; fi",1)

# User-facing labels: effective limits, not cgroup jargon.
s=s.replace(' CPU 配额           : ',' CPU 有效配额       : ')
s=s.replace(' 内存 cgroup 上限   : ',' 内存有效上限       : ')
s=s.replace(' Swap cgroup 上限   : ',' Swap 有效上限      : ')

# Resource health: include CPU, memory, swap and PID effective limits.
resource=r'''v20_resource_health(){
  v20_read_resource_limits
  local base raw mem_kb mem_bytes swap_kb swap_bytes limited=0 partial=0 evidence=0
  [[ "$V20_CPU_QUOTA_STATE" == NORMAL ]] && evidence=$((evidence+1))
  [[ "$V20_MEM_LIMIT" != UNKNOWN ]] && evidence=$((evidence+1))
  [[ "$V20_SWAP_LIMIT" != UNKNOWN ]] && evidence=$((evidence+1))
  [[ "$V20_PIDS_LIMIT" != UNKNOWN ]] && evidence=$((evidence+1))

  if [[ "$V20_CPU_QUOTA_STATE" == LIMITED ]]; then
    limited=1; v20_add_issue "CPU 有效配额低于系统可见核心"
  fi

  base="$V20_CGROUP_BASE"
  if [[ "$base" != UNKNOWN && -r "$base/memory.max" ]]; then
    raw="$(cat "$base/memory.max" 2>/dev/null)"; mem_kb="$(awk '/^MemTotal:/{print $2;exit}' /proc/meminfo 2>/dev/null)"
    if [[ "$raw" =~ ^[0-9]+$ && "$mem_kb" =~ ^[0-9]+$ ]]; then
      mem_bytes=$((mem_kb*1024))
      if awk -v lim="$raw" -v visible="$mem_bytes" 'BEGIN{exit !(lim<visible*0.90)}'; then limited=1; v20_add_issue "内存有效上限低于系统可见内存"; fi
    fi
  fi

  if [[ "$base" != UNKNOWN && -r "$base/memory.swap.max" ]]; then
    raw="$(cat "$base/memory.swap.max" 2>/dev/null)"; swap_kb="$(awk '/^SwapTotal:/{print $2;exit}' /proc/meminfo 2>/dev/null)"
    if [[ "$raw" =~ ^[0-9]+$ && "$swap_kb" =~ ^[0-9]+$ && "$swap_kb" -gt 0 ]]; then
      swap_bytes=$((swap_kb*1024))
      if awk -v lim="$raw" -v visible="$swap_bytes" 'BEGIN{exit !(lim<visible*0.90)}'; then limited=1; v20_add_issue "Swap 有效上限低于系统可见 Swap"; fi
    fi
  fi

  if [[ "$V20_PIDS_LIMIT" =~ ^[0-9]+$ ]]; then
    if (( V20_PIDS_LIMIT<256 )); then limited=1; v20_add_issue "进程数上限异常偏低（${V20_PIDS_LIMIT}）"
    elif (( V20_PIDS_LIMIT<512 )); then partial=1; v20_add_issue "进程数上限偏低（${V20_PIDS_LIMIT}）"
    fi
  fi

  if (( limited )); then V20_RESOURCE_STATE=LIMITED
  elif (( partial )); then V20_RESOURCE_STATE=PARTIAL
  elif (( evidence>=4 )); then V20_RESOURCE_STATE=NORMAL
  elif (( evidence>=2 )); then V20_RESOURCE_STATE=PARTIAL
  else V20_RESOURCE_STATE=UNKNOWN
  fi
}'''
s,n=re.subn(r'v20_resource_health\(\)\{.*?\n\}',resource,s,count=1,flags=re.S)
if n!=1: raise SystemExit('resource health fixup failed')

# Workload fit must consider the actual bottlenecks, not just global grade.
usecase=r'''v20_usecase_fit(){
  V20_SITE_FIT='观察'; V20_SEA_FIT='较弱'; V20_DB_FIT='较弱'
  local steal="$V20_CPU_LOAD_STEAL"
  [[ "$steal" =~ ^[0-9.]+$ ]] || steal="$V20_CPU_STEAL"

  if [[ "$V20_RESOURCE_STATE" == LIMITED ]] || (( V20_HTTPS_TOTAL>0 && V20_HTTPS_PASS<12 )); then
    V20_SITE_FIT='不建议'
  elif [[ "$V20_IP_HEALTH" == NORMAL && "$V20_DISK_IOPS" =~ ^[0-9.]+$ && "$V20_FSYNC_P95" =~ ^[0-9.]+$ && "$V20_GLOBAL_MEDIAN_DOWN" =~ ^[0-9.]+$ ]] \
       && awk -v i="$V20_DISK_IOPS" -v f="$V20_FSYNC_P95" -v d="$V20_GLOBAL_MEDIAN_DOWN" 'BEGIN{exit !(i>=500 && f<=5 && d>=20)}'; then
    V20_SITE_FIT='适合'
  fi

  if [[ "$V20_SEA_MEDIAN_UP" =~ ^[0-9.]+$ && "$V20_SEA_MEDIAN_DOWN" =~ ^[0-9.]+$ ]]; then
    if awk -v u="$V20_SEA_MEDIAN_UP" -v d="$V20_SEA_MEDIAN_DOWN" 'BEGIN{exit !(u>=50&&d>=100)}'; then V20_SEA_FIT='良好'
    elif awk -v u="$V20_SEA_MEDIAN_UP" -v d="$V20_SEA_MEDIAN_DOWN" 'BEGIN{exit !(u>=15&&d>=30)}'; then V20_SEA_FIT='可用'
    else V20_SEA_FIT='较弱'; fi
  fi

  if [[ "$V20_DISK_IOPS" =~ ^[0-9.]+$ && "$V20_FSYNC_P95" =~ ^[0-9.]+$ ]]; then
    if awk -v i="$V20_DISK_IOPS" -v f="$V20_FSYNC_P95" 'BEGIN{exit !(i>=1000&&f<=2)}'; then V20_DB_FIT='良好'
    elif awk -v i="$V20_DISK_IOPS" -v f="$V20_FSYNC_P95" 'BEGIN{exit !(i>=500&&f<=5)}'; then V20_DB_FIT='一般'
    else V20_DB_FIT='较弱'; fi
  fi

  if [[ "$steal" =~ ^[0-9.]+$ ]] && awk -v x="$steal" 'BEGIN{exit !(x>10)}'; then
    [[ "$V20_SITE_FIT" == '适合' ]] && V20_SITE_FIT='观察'
    [[ "$V20_DB_FIT" == '良好' ]] && V20_DB_FIT='一般'
  fi
}'''
s,n=re.subn(r'v20_usecase_fit\(\)\{.*?\n\}',usecase,s,count=1,flags=re.S)
if n!=1: raise SystemExit('usecase fixup failed')

# JSON: workload fit and cgroup path are machine-readable too.
old="'resource_constraints':{'state':__import__('os').environ.get('P07_V20_RESOURCE_STATE','UNKNOWN'),'scope':'HIDDEN_LIMIT_SIGNALS_ONLY','memory_limit':__import__('os').environ.get('P07_V20_MEM_LIMIT','UNKNOWN'),'swap_limit':__import__('os').environ.get('P07_V20_SWAP_LIMIT','UNKNOWN'),'pids_limit':__import__('os').environ.get('P07_V20_PIDS_LIMIT','UNKNOWN')},\n  'verdict':"
new="'resource_constraints':{'state':__import__('os').environ.get('P07_V20_RESOURCE_STATE','UNKNOWN'),'scope':'EFFECTIVE_CGROUP_LIMIT_SIGNALS','cgroup_base':__import__('os').environ.get('P07_V20_CGROUP_BASE','UNKNOWN'),'memory_limit':__import__('os').environ.get('P07_V20_MEM_LIMIT','UNKNOWN'),'swap_limit':__import__('os').environ.get('P07_V20_SWAP_LIMIT','UNKNOWN'),'pids_limit':__import__('os').environ.get('P07_V20_PIDS_LIMIT','UNKNOWN')},\n  'workload_fit':{'website_wordpress':__import__('os').environ.get('P07_V20_SITE_FIT','UNKNOWN'),'southeast_asia':__import__('os').environ.get('P07_V20_SEA_FIT','UNKNOWN'),'database':__import__('os').environ.get('P07_V20_DB_FIT','UNKNOWN')},\n  'verdict':"
if old not in s: raise SystemExit('json resource anchor missing')
s=s.replace(old,new,1)

old='P07_V20_RESOURCE_STATE="$V20_RESOURCE_STATE" P07_V20_MEM_LIMIT="$V20_MEM_LIMIT"'
new='P07_V20_RESOURCE_STATE="$V20_RESOURCE_STATE" P07_V20_CGROUP_BASE="$V20_CGROUP_BASE" P07_V20_SITE_FIT="$V20_SITE_FIT" P07_V20_SEA_FIT="$V20_SEA_FIT" P07_V20_DB_FIT="$V20_DB_FIT" P07_V20_MEM_LIMIT="$V20_MEM_LIMIT"'
if old not in s: raise SystemExit('json export anchor missing')
s=s.replace(old,new,1)

# RC3 changes the machine-readable contract.
s=s.replace("d['schema_version']=4", "d['schema_version']=5",1)

p.write_text(s,encoding='utf-8')
print('PATCH_V20_RC3_FIXUP=OK')
