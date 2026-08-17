#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
p=Path(sys.argv[1] if len(sys.argv)>1 else 'scripts/p03_v1354_formal_builder.py')
s=p.read_text(encoding='utf-8')
marker='from p03_v1354_two_phase_repair import repair_php as repair_php\n\ndef main()->int:'
if marker in s:
    print('TWO_PHASE_ATOMIC_BUILDER_NORMALIZATION=ALREADY_APPLIED');raise SystemExit(0)
anchor='def main()->int:'
if s.count(anchor)!=1:raise SystemExit('TWO_PHASE_ATOMIC_MAIN_ANCHOR_MISMATCH')
s=s.replace(anchor,'from p03_v1354_two_phase_repair import repair_php as repair_php\n\n'+anchor,1)
p.write_text(s,encoding='utf-8',newline='\n')
print('TWO_PHASE_ATOMIC_BUILDER_NORMALIZATION=PASS source_switch_request=1 migration_request=2 csrf_nonce=REQUIRED')
