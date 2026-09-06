from pathlib import Path

p=Path('experiments/p07-bench.sh')
s=p.read_text(encoding='utf-8')

if ' 多核扩展效率       :' not in s:
    lines=s.splitlines(keepends=True)
    for i,line in enumerate(lines):
        if 'SHA256 多核' in line and '$V20_CPU_MULTI' in line:
            indent=line[:len(line)-len(line.lstrip())]
            lines.insert(i+1, indent + "printf ' 多核扩展效率       : %s%%\\n' \"$V20_CPU_SCALE_EFF\"\n")
            break
    else:
        raise SystemExit('semantic cpu multi row not found')
    s=''.join(lines)

p.write_text(s,encoding='utf-8')
print('PATCH_V20_RC3_DETAIL=OK')
