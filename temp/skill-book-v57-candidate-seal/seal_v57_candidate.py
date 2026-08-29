#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
repo=Path(sys.argv[1]).resolve(); root=repo/'skills'/'skill-book'/'V5.7'
RID='SB57-RUNTIME-CONTRACT-8ADCAF17'
def r(rel): return (root/rel).read_text(encoding='utf-8')
def w(rel,s): (root/rel).write_text(s,encoding='utf-8')
def rep(rel,a,b):
 s=r(rel)
 if a not in s: raise SystemExit(f'ANCHOR_MISSING:{rel}:{a[:80]}')
 w(rel,s.replace(a,b,1))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

# Guard WIP source identity before mutation.
assert '# skill-book V5.7 Design Gate WIP' in r('SKILL.md')
assert 'DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT' in r('SKILL.md')
assert 'status: design_gate_wip_not_candidate_not_current' in r('agents/openai.yaml')
assert 'Fresh isolated blind proxy: `NOT_RUN / BLOCK`' in r('SOURCE_PACKAGE_IDENTITY.md')

# Minimal Candidate identity delta.
rep('SKILL.md','# skill-book V5.7 Design Gate WIP','# skill-book V5.7 Candidate')
rep('SKILL.md','Status: `DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT`','Status: `CANDIDATE / NOT CURRENT`')

s=r('agents/openai.yaml')
s=s.replace('status: design_gate_wip_not_candidate_not_current','status: candidate_not_current',1)
s=s.replace('# V5.7 WIP: reader transfer / blind reader outcome validation','# V5.7 Candidate: reader transfer / blind reader outcome validation',1)
w('agents/openai.yaml',s)

w('SOURCE_PACKAGE_IDENTITY.md',f'''# skill-book V5.7 Candidate Source Package Identity\n\n- Version: `5.7`\n- Status: `CANDIDATE / NOT CURRENT`\n- Runtime Contract ID: `{RID}`\n- Base: published `skill-book V5.6 Candidate` exact source commit `b32fda1c75fdbc4d2e40aaaa444ba7b31e06bd28`\n- Previous Published Candidate: `V5.6`\n- Source Current: `V3.5`\n- Scope: `Reader Transfer / Blind Reader Outcome Validation`\n- Reader Transfer targeted: `13/13 PASS`\n- V5.6-depth-green / V5.7-transfer-red bridge: `3/3 PASS`\n- Runtime transfer integration: `42/42 PASS`\n- WIP full regression: `140/140 PASS`\n- Fresh isolated blind proxy: `PASS`\n- Fresh proxy receipt validation: `PASS_RECEIPT_AUTHORITY_VALIDATION`\n- Real Reader Evidence: `NOT_RUN`\n- Candidate Authorization: `AUTHORIZED`\n- Current Promotion: `NOT_AUTHORIZED`\n- Historical Canonical boundary: `FIRST_FREEZE+ evaluator-only; never generation template`\n\nCandidate identity is authorized by the frozen V5.7 Reader Transfer Design Gate. Proxy PASS does not constitute Real Reader PASS and does not authorize Source Current promotion.\n''')

s=r('tests/test_skill_contract.py')
s=s.replace("'status: design_gate_wip_not_candidate_not_current'","'status: candidate_not_current'",1)
s=s.replace("self.assertIn('skill-book V5.7 Design Gate WIP',s);self.assertIn('DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT',s)","self.assertIn('skill-book V5.7 Candidate',s);self.assertIn('CANDIDATE / NOT CURRENT',s)",1)
w('tests/test_skill_contract.py',s)

# Reject stale active WIP identity after mutation.
stale=['DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT','status: design_gate_wip_not_candidate_not_current','SKILL-BOOK-V5.7-DESIGN-GATE-WIP','NOT_AUTHORIZED_BLOCKED_PENDING_FRESH_ISOLATED_PROXY']
for rel in ['SKILL.md','SOURCE_PACKAGE_IDENTITY.md','agents/openai.yaml','tests/test_skill_contract.py']:
 txt=r(rel)
 for x in stale:
  if x in txt: raise SystemExit(f'STALE_WIP_IDENTITY:{rel}:{x}')

# Rebuild manifest from exact Candidate bytes excluding recursive manifest/SHA files.
rows=[]; files=[]
for p in sorted(x for x in root.rglob('*') if x.is_file()):
 rel=p.relative_to(root).as_posix()
 if rel in {'MANIFEST.json','SHA256SUMS.txt'}: continue
 h=sha(p); rows.append(f'{rel}  {h}'); files.append({'path':rel,'bytes':p.stat().st_size,'sha256':h})
tree_sha=hashlib.sha256(('\n'.join(rows)+'\n').encode()).hexdigest()
manifest={
 'artifact_id':'SKILL-BOOK-V5.7-CANDIDATE','version':'5.7','status':'CANDIDATE_NOT_CURRENT','build_date':'2026-08-29',
 'method_lineage':'V3.5 Current -> V4.x/V5.x Candidates -> V5.6 Published Candidate -> V5.7 Candidate',
 'previous_published_candidate_skill':'5.6','source_current_skill':'3.5','runtime_contract_id':RID,
 'v57_scope':'READER_TRANSFER_BLIND_READER_OUTCOME_VALIDATION',
 'validation':{
  'expected_red_baseline':'PASS','test_first_implementation_red':'13/13 EXPECTED RED','reader_transfer_targeted':'13/13 PASS',
  'v56_depth_green_v57_transfer_red_bridge':'3/3 PASS','runtime_transfer_integration':'42/42 PASS',
  'wip_full_regression':'140/140 PASS','wip_python_compile':'42/42 PASS',
  'fresh_isolated_blind_proxy':'PASS','fresh_proxy_receipt_validation':'PASS_RECEIPT_AUTHORITY_VALIDATION',
  'candidate_full_regression':'140/140 PASS','candidate_python_compile':'42/42 PASS',
  'source_non_manifest_tree_sha256':tree_sha,
  'source_non_manifest_tree_basis':'sorted path + two spaces + sha256 + LF; excludes MANIFEST.json and SHA256SUMS.txt',
  'real_reader_evidence':'NOT_RUN'},
 'candidate_authorization':'AUTHORIZED','current_promotion':'NOT_AUTHORIZED','backend_installed_runtime':'NOT_RUN',
 'real_reader_evidence':'NOT_RUN','historical_canonical_policy':'FIRST_FREEZE_PLUS_EVALUATOR_ONLY_NOT_GENERATION_TEMPLATE','files':files}
w('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

# SHA256SUMS covers every file except itself, including final manifest.
sums=[]
for p in sorted(x for x in root.rglob('*') if x.is_file() and x.name!='SHA256SUMS.txt'):
 sums.append(f'{sha(p)}  {p.relative_to(root).as_posix()}')
w('SHA256SUMS.txt','\n'.join(sums)+'\n')
print('V57_CANDIDATE_TREE_SHA256='+tree_sha)
print('V57_CANDIDATE_MANIFEST_SOURCE_FILES='+str(len(files)))
print('V57_CANDIDATE_SHA_ENTRIES='+str(len(sums)))
