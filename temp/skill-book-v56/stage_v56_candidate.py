from __future__ import annotations

import hashlib,json,sys
from pathlib import Path

root=Path(sys.argv[1]).resolve()
skill=root/'skills/skill-book/V5.6'
design=root/'mother-specs/skill-book/V5.6/SKILL_BOOK_V5.6_DESIGN_GATE.md'

def read(p): return p.read_text(encoding='utf-8')
def write(p,s): p.write_text(s,encoding='utf-8')

# SKILL identity only; functional rules stay unchanged.
p=skill/'SKILL.md'; s=read(p)
assert '# skill-book V5.6 Design Gate WIP' in s
assert 'Status: `DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT`' in s
s=s.replace('# skill-book V5.6 Design Gate WIP','# skill-book V5.6 Candidate',1)
s=s.replace('Status: `DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT`','Status: `CANDIDATE / NOT CURRENT`',1)
write(p,s)

p=skill/'agents/openai.yaml'; s=read(p)
assert 'status: design_gate_wip_not_candidate' in s
s=s.replace('status: design_gate_wip_not_candidate','status: candidate_not_current',1)
write(p,s)

# Package self-contract follows the staged Candidate identity.
p=skill/'tests/test_skill_contract.py'; s=read(p)
assert "self.assertIn('status: design_gate_wip_not_candidate',s)" in s
assert "self.assertIn('skill-book V5.6 Design Gate WIP',s);self.assertIn('DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT',s)" in s
s=s.replace("self.assertIn('status: design_gate_wip_not_candidate',s)","self.assertIn('status: candidate_not_current',s)")
s=s.replace("self.assertIn('skill-book V5.6 Design Gate WIP',s);self.assertIn('DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT',s)","self.assertIn('skill-book V5.6 Candidate',s);self.assertIn('CANDIDATE / NOT CURRENT',s)")
write(p,s)

# Source package identity: Candidate authorized, final-byte/release seal still pending.
p=skill/'SOURCE_PACKAGE_IDENTITY.md'; s=read(p)
assert '# skill-book V5.6 Design Gate WIP Source Identity' in s
assert '- Status: `DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT`' in s
assert '- Candidate Authorization: `NOT_AUTHORIZED`' in s
assert '- Release / prerelease / immutable candidate seal: `NOT_APPLICABLE_WIP`' in s
s=s.replace('# skill-book V5.6 Design Gate WIP Source Identity','# skill-book V5.6 Source Package Identity',1)
s=s.replace('- Status: `DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT`','- Status: `CANDIDATE / NOT CURRENT`',1)
s=s.replace('- Candidate Authorization: `NOT_AUTHORIZED`','- Candidate Authorization: `AUTHORIZED_TO_SEAL_CANDIDATE`',1)
s=s.replace('- Release / prerelease / immutable candidate seal: `NOT_APPLICABLE_WIP`','- Candidate publication: `PENDING_LOCAL_FINAL_BYTES_AND_REMOTE_VALIDATION`',1)
write(p,s)

# Design Gate records the separate authorization decision.
d=read(design)
assert '## 17. Candidate Authorization Review' not in d
assert 'FUNCTIONALLY CLOSED / COMMITTED-STATE RESEALED' in d
d=d.rstrip()+r'''

## 17. Candidate Authorization Review

Decision: `AUTHORIZED_TO_ENTER_CANDIDATE_SEAL`.

Authority basis:

- Design Gate functional closure: `PASS`.
- Non-A1 targeted Practical Asset Depth: `12/12 PASS`.
- Inherited Adequacy: `6/6 PASS`.
- Runtime depth integration: `36/36 PASS`.
- Fresh non-A1 generation: `9/9 PASS` on the reading-club domain.
- Adversarial old-Adequacy false-green: reproduced; V5.6 Depth blocked the shallow trace/recovery asset; restored asset passed without verifier/contract mutation.
- Committed-state package closure: SHA `97/97`, Python compile `39/39`, full regression `122/122`.
- Design-gate closure Runner: `33258515860 / 99116309698`.
- Real Reader Evidence: `NOT_RUN`; this is preserved as NOT_RUN and is not converted into machine evidence.

This decision authorizes Candidate **seal work only**. It does not authorize Source Current promotion, does not publish a release, and does not permit skipping final-byte regression, deterministic double build, remote exact-source validation, or prerelease governance.
'''
write(design,d+'\n')

# Candidate staging manifest. Final bytes remain explicitly pending.
p=skill/'MANIFEST.json'; m=json.loads(read(p))
assert m['artifact_id']=='SKILL-BOOK-V5.6-DESIGN-GATE-WIP'
assert m['status']=='DESIGN_GATE_WIP_NOT_CANDIDATE_NOT_CURRENT'
assert m['stability']=='DESIGN_GATE_FUNCTIONALLY_CLOSED_RESEALED_NOT_CANDIDATE'
assert m['candidate_authorization']=='NOT_AUTHORIZED'
assert m['current_promotion']=='NOT_AUTHORIZED'
assert m['real_reader_evidence']=='NOT_RUN'
m['artifact_id']='SKILL-BOOK-V5.6-CANDIDATE'
m['status']='CANDIDATE_NOT_CURRENT'
m['method_lineage']='V3.5 Current -> V4.x/V5.x Candidates -> V5.5 Published Candidate -> V5.6 Candidate'
m['package_seal_state']={
 'local_final_bytes':'PENDING_FINAL_BYTE_RERUN_AFTER_CANDIDATE_IDENTITY',
 'deterministic_double_build':'PENDING_FINAL_CANDIDATE_BYTES',
 'remote_exact_source':'PENDING_AFTER_LOCAL_FINAL_BYTES',
 'prerelease':'NOT_AUTHORIZED_UNTIL_REMOTE_EXACT_SOURCE_PASS',
}
m['validation']['candidate_authorization_review']='PASS_AUTHORIZED_TO_ENTER_CANDIDATE_SEAL'
m['validation']['candidate_authorization_runner_run_job']='33258515860 / 99116309698'
m['validation']['final_byte_rerun_required']=True
m['stability']='CANDIDATE_STAGED_PENDING_FINAL_BYTE_SEAL'
m['candidate_authorization']='AUTHORIZED_TO_SEAL_CANDIDATE'

# Rebuild source inventory and tree hash after identity/test metadata changes.
excluded={'MANIFEST.json','SHA256SUMS.txt'}
paths=sorted(x for x in skill.rglob('*') if x.is_file() and '__pycache__' not in x.parts and x.relative_to(skill).as_posix() not in excluded)
files=[]; lines=[]
for x in paths:
 rel=x.relative_to(skill).as_posix(); data=x.read_bytes(); h=hashlib.sha256(data).hexdigest()
 files.append({'path':rel,'bytes':len(data),'sha256':h}); lines.append(f'{h}  {rel}\n')
m['files']=files
m['validation']['source_non_manifest_tree_sha256']=hashlib.sha256(''.join(lines).encode()).hexdigest()
p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Rebuild SHA sums, including MANIFEST but excluding SHA itself.
rows=[]
for x in sorted(y for y in skill.rglob('*') if y.is_file() and y.name!='SHA256SUMS.txt' and '__pycache__' not in y.parts and y.suffix!='.pyc'):
 rel=x.relative_to(skill).as_posix(); rows.append(f'{hashlib.sha256(x.read_bytes()).hexdigest()}  {rel}')
(skill/'SHA256SUMS.txt').write_text('\n'.join(rows)+'\n',encoding='utf-8')

print('V56_CANDIDATE_STAGING_PREPARED')
print('TREE_SHA='+m['validation']['source_non_manifest_tree_sha256'])
print('SOURCE_FILES='+str(len(files)))
print('SHA_ROWS='+str(len(rows)))
