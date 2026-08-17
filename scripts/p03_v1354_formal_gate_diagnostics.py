#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

p=Path(sys.argv[1] if len(sys.argv)>1 else 'scripts/p03_v1354_formal_artifact_pre_gate.sh')
s=p.read_text(encoding='utf-8')
old="grep -q '升级完成' \"$GATE_ROOT/repair-result.html\";test ! -e \"$UP_RT/repair-v1.35.4.php\";grep -Fq \"define('VFAB_VERSION', '1.35.4');\" \"$UP_RT/app/bootstrap.php\";grep -Fq \"define('VFAB_SCHEMA_VERSION', 30);\" \"$UP_RT/app/bootstrap.php\""
new="""if ! grep -q '升级完成' \"$GATE_ROOT/repair-result.html\"; then
  python3 - \"$GATE_ROOT/repair-result.html\" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8',errors='replace').read()
s=re.sub(r'<script\\b[^>]*>.*?</script>',' ',s,flags=re.I|re.S)
s=re.sub(r'<style\\b[^>]*>.*?</style>',' ',s,flags=re.I|re.S)
s=re.sub(r'<[^>]+>',' ',s)
s=html.unescape(re.sub(r'\\s+',' ',s)).strip()
print('ATOMIC_RESULT_PAGE='+s[:1200])
PY
  echo 'FORMAL_ATOMIC_EXECUTION=FAIL' >&2
  exit 93
fi
test ! -e \"$UP_RT/repair-v1.35.4.php\";grep -Fq \"define('VFAB_VERSION', '1.35.4');\" \"$UP_RT/app/bootstrap.php\";grep -Fq \"define('VFAB_SCHEMA_VERSION', 30);\" \"$UP_RT/app/bootstrap.php\""""
if new in s:
    print('FORMAL_GATE_DIAGNOSTICS=ALREADY_APPLIED');raise SystemExit(0)
if s.count(old)!=1: raise SystemExit('FORMAL_GATE_DIAGNOSTIC_ANCHOR_MISMATCH')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8',newline='\n')
print('FORMAL_GATE_DIAGNOSTICS=PASS atomic_result_page_safe_text')
