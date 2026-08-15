#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve()
p=root/'scripts/build-v251-maintenance-release.py'
s=p.read_text(encoding='utf-8')
a="if(class_exists('Web')){Web::headers($cspNonce);}else{"
b="if(class_exists('Web')){{Web::headers($cspNonce);}}else{{"
if s.count(a)!=1: raise SystemExit(f'Atomic CSP open-brace sentinel count={s.count(a)}')
s=s.replace(a,b,1)
a="header('Cache-Control: no-store, private');}$cls='state-'.$state;"
b="header('Cache-Control: no-store, private');}}$cls='state-'.$state;"
if s.count(a)!=1: raise SystemExit(f'Atomic CSP close-brace sentinel count={s.count(a)}')
s=s.replace(a,b,1)
p.write_text(s,encoding='utf-8')
print('ATOMIC_TEMPLATE_FSTRING_ESCAPE=PASS')
