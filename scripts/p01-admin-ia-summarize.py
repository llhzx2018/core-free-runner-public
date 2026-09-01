#!/usr/bin/env python3
from pathlib import Path
import json,sys
E=Path(sys.argv[1])
s=json.loads((E/'static.json').read_text(encoding='utf-8'))
b=json.loads((E/'browser.json').read_text(encoding='utf-8'))
lines=['P01_ADMIN_IA_AUDIT_SUMMARY','']
lines.append('TOP_LEVEL='+ ' / '.join(x['label'] for x in s['admin_modules']))
lines.append('SHELL_ROOT_PAGES='+','.join(s['admin_shell_root_pages']))
lines.append('')
lines.append('CANONICAL 1440')
for label,d in b['widths']['1440']['canonical'].items():
    lines.append(f"{label}: req={d['requested']} final={d['finalRoute']} status={d['status']} shell={d['shell']} group={d['group']} h1={d['h1']} sub={','.join(d['railSub'])} controls={d['controls']} overflow={d['overflowX']}")
lines.append('')
lines.append('LOW FREQUENCY / DIRECT 1440')
for label,d in b['widths']['1440']['low'].items():
    ref=s['reference_graph'].get(d['requested'].split('?')[0],{'total':0})['total']
    links=len(b['lowFrequencyLinkCounts'].get(label,{}).get('visibleCanonicalLinks',[]))
    redirect='YES' if d['finalRoute'].split('#')[0]!=d['requested'].split('#')[0] else 'NO'
    lines.append(f"{label}: req={d['requested']} final={d['finalRoute']} redirect={redirect} status={d['status']} shell={d['shell']} group={d['group']} h1={d['h1']} canonicalVisibleLinks={links} staticRefs={ref} controls={d['controls']} overflow={d['overflowX']}")
lines.append('')
lines.append('MOBILE OVERFLOW')
for kind in ['canonical','low']:
  bad=[]
  for label,d in b['widths']['390'][kind].items():
    if d['overflowX'] not in (None,0) and d['overflowX']>1: bad.append(f"{label}:{d['overflowX']}")
  lines.append(f"{kind}="+('PASS' if not bad else 'FAIL '+','.join(bad)))
lines.append('')
lines.append('TECH TERM SIGNALS 1440')
for kind in ['canonical','low']:
  for label,d in b['widths']['1440'][kind].items():
    hot={k:v for k,v in d['techTerms'].items() if v}
    if hot: lines.append(f"{kind}/{label}: {hot}")
(E/'summary.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines))
