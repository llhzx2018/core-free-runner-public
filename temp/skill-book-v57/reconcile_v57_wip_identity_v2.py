#!/usr/bin/env python3
from __future__ import annotations
import os,sys
from pathlib import Path

base=Path(__file__).with_name('reconcile_v57_wip_identity.py')
s=base.read_text(encoding='utf-8')
old='summary: Reader-outcome book generation with runtime-entry receipts, baseline applicability, freeze integrity, operational closure, training feedback, practical-asset depth, and V5.7 blind-reader transfer validation across READ / LEARN / TRAIN / DO. Blind-reader proxy evidence never authorizes Real Reader evidence.'
new='summary: Reader-outcome book generation with runtime-entry receipts, baseline applicability, freeze integrity, operational closure, training feedback, practical-asset depth, post-freeze frozen local holdout, and V5.7 blind-reader transfer validation across READ / LEARN / TRAIN / DO. Blind-reader proxy evidence never authorizes Real Reader evidence.'
if s.count(old)!=1:
    raise SystemExit('V57_RECONCILE_V2_SUMMARY_ANCHOR_MISMATCH')
s=s.replace(old,new,1)
tmp=base.with_name('_reconcile_v57_wip_identity_v2_effective.py')
tmp.write_text(s,encoding='utf-8')
os.execv(sys.executable,[sys.executable,str(tmp),*sys.argv[1:]])
