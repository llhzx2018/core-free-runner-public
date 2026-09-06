from pathlib import Path

p=Path('experiments/p07-bench.sh')
s=p.read_text(encoding='utf-8')

if ' 多核扩展效率       :' not in s:
    needle="""      printf ' SHA256 多核        : %s MB/s  （最多使用 4 核）
' "$V20_CPU_MULTI"
"""
    insert=needle+"""      printf ' 多核扩展效率       : %s%%
' "$V20_CPU_SCALE_EFF"
"""
    if needle not in s:
        raise SystemExit('split-line cpu multi source not found')
    s=s.replace(needle,insert,1)

p.write_text(s,encoding='utf-8')
print('PATCH_V20_RC3_DETAIL=OK')
