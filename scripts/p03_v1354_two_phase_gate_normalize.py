#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

p=Path(sys.argv[1] if len(sys.argv)>1 else 'scripts/p03_v1354_formal_artifact_pre_gate.sh')
s=p.read_text(encoding='utf-8')
canonical='''curl -fsS -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" --data-urlencode "_csrf=$RCSRF" --data-urlencode 'confirmation=UPGRADE' "$UP_BASE/repair-v1.35.4.php" -o "$GATE_ROOT/repair-phase1.html"
grep -q 'name="phase" value="migrate"' "$GATE_ROOT/repair-phase1.html"
read -r MCSRF MOP MNONCE < <(python3 - "$GATE_ROOT/repair-phase1.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read()
def v(name):
 m=re.search(r'name="'+re.escape(name)+r'" value="([^"]+)"',s);assert m,name;return html.unescape(m.group(1))
assert v('phase')=='migrate' and v('confirmation')=='MIGRATE'
csrf,op,nonce=v('_csrf'),v('op'),v('nonce')
assert re.fullmatch(r'\\d{8}-\\d{6}-[a-f0-9]{8}',op)
assert re.fullmatch(r'[a-f0-9]{64}',nonce)
print(csrf,op,nonce)
PY
)
curl -fsS -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" --data-urlencode "_csrf=$MCSRF" --data-urlencode 'phase=migrate' --data-urlencode "op=$MOP" --data-urlencode "nonce=$MNONCE" --data-urlencode 'confirmation=MIGRATE' "$UP_BASE/repair-v1.35.4.php" -o "$GATE_ROOT/repair-result.html"
'''
if 'repair-phase1.html' in s and "--data-urlencode 'phase=migrate'" in s:
    print('TWO_PHASE_ATOMIC_GATE_NORMALIZATION=ALREADY_APPLIED');raise SystemExit(0)
old='''curl -fsS -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" --data-urlencode "_csrf=$RCSRF" --data-urlencode 'confirmation=UPGRADE' "$UP_BASE/repair-v1.35.4.php" -o "$GATE_ROOT/repair-result.html"
'''
if s.count(old)!=1:raise SystemExit('TWO_PHASE_ATOMIC_GATE_ANCHOR_MISMATCH')
s=s.replace(old,canonical,1)
p.write_text(s,encoding='utf-8',newline='\n')
print('TWO_PHASE_ATOMIC_GATE_NORMALIZATION=PASS request1=SOURCE_SWITCH request2=M030 csrf_nonce=REQUIRED')
