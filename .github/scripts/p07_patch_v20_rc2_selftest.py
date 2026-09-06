from pathlib import Path

p=Path('experiments/p07-bench.sh')
s=p.read_text(encoding='utf-8')

marker='v20_self_test(){\n'
if marker not in s:
    raise SystemExit('v20_self_test anchor missing')

block=r'''v20_rc2_semantic_self_test(){
  local f=0 n
  : >"$NETWORK_TSV"
  # Adversarial case: every region connects, but performance is unusably low.
  for n in 'US West' 'US East' 'Europe' 'Hong Kong' 'Singapore' 'Kuala Lumpur' 'Bangkok' 'Tokyo'; do
    printf 'test\t%s\tPASS\tSPEEDTESTGO_FALLBACK\t2.00\t2.00\t80\n' "$n" >>"$NETWORK_TSV"
  done
  V20_PING_STATE=ICMP_BLOCKED
  V20_PING_LOSS=UNKNOWN
  V20_PING_JITTER=UNKNOWN
  V20_HTTPS_PASS=15; V20_HTTPS_TOTAL=15; V20_HTTPS_JITTER=5.0
  V20_CPU_STEAL=0.10; V20_CPU_LOAD_STEAL=0.20
  V20_CPU_QUOTA='无限制'; V20_CPU_QUOTA_STATE=NORMAL
  V20_CPU_BENCH_STATE=PASS; V20_CPU_SINGLE=500; V20_CPU_MULTI=1000
  IO_STATE=PASS; IO_AVG_MB=500
  V20_DISK_IOPS=1000; V20_FSYNC_P95=2; V20_FSYNC_AVG=1
  V20_IP_HEALTH=NORMAL
  CORES=2; RAM_TOTAL='2.0 GiB'; DISK_TOTAL='50 GiB'; VIRT='KVM'
  V20_ISSUES=''
  v20_score_and_verdict
  [[ "$V20_GRADE" != GOOD ]] || f=1
  (( V20_SCORE < 85 )) || f=1
  [[ "$V20_ISSUES" != *'网络丢包偏高'* ]] || f=1
  [[ "$V20_GLOBAL_MEDIAN_UP" == '2.00' ]] || f=1
  [[ "$V20_SEA_MEDIAN_UP" == '2.00' ]] || f=1

  # Missing CPU quota evidence must reduce evidence, not masquerade as healthy.
  V20_CPU_QUOTA_STATE=UNKNOWN
  v20_resource_health
  [[ "$V20_RESOURCE_STATE" == PARTIAL ]] || f=1

  if (( f==0 )); then printf 'V20_RC2_SEMANTIC_SELF_TEST=PASS\n'; else printf 'V20_RC2_SEMANTIC_SELF_TEST=FAIL\n'; return 1; fi
}

'''
s=s.replace(marker,block+marker,1)
s=s.replace('if (( SELF_TEST )); then self_test && v20_self_test; exit $?; fi','if (( SELF_TEST )); then self_test && v20_self_test && v20_rc2_semantic_self_test; exit $?; fi',1)
p.write_text(s,encoding='utf-8')
print('PATCH_V20_RC2_SELFTEST=OK')
