from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
skill = root / 'skills/skill-book/V5.6'
design = root / 'mother-specs/skill-book/V5.6/SKILL_BOOK_V5.6_DESIGN_GATE.md'
identity = skill / 'SOURCE_PACKAGE_IDENTITY.md'
manifest_path = skill / 'MANIFEST.json'
sums_path = skill / 'SHA256SUMS.txt'

for p in (design, identity, manifest_path, sums_path):
    assert p.is_file(), p

# 1) Source identity: record completed fresh gate and committed-state reseal, without Candidate promotion.
s = identity.read_text(encoding='utf-8')
assert '- Fresh non-A1 generation test: `NOT_RUN`' in s
assert '- Candidate Authorization: `NOT_AUTHORIZED`' in s
assert '- Current Promotion: `NOT_AUTHORIZED`' in s
s = s.replace(
    '- Fresh non-A1 generation test: `NOT_RUN`',
    '- Fresh non-A1 generation test: `PASS` — `V5.6_FRESH_NON_A1_READING_CLUB_20260829` on functional source `c3b19fe5ccb751019443495f3dc975f3ab8ab046`\n'
    '- Fresh non-A1 Runner evidence: `33258236680 / 99115573137`\n'
    '- Fresh non-A1 adversarial proof: `OLD_ADEQUACY_FALSE_GREEN -> DEPTH_BLOCK -> REPAIR_PASS`\n'
    '- Committed-state evidence reseal: `PASS` — Runner `33258401492 / 99116008440`\n'
    '- Committed-state full regression after Fresh evidence reconciliation: `122/122 PASS`\n'
    '- Committed-state Python compile: `39/39 PASS`\n'
    '- Committed-state SHA coverage: `97/97 PASS`'
)
identity.write_text(s, encoding='utf-8')

# 2) Design Gate: convert pending-reseal wording to completed-reseal truth; still not Candidate.
d = design.read_text(encoding='utf-8')
assert 'FUNCTIONALLY CLOSED PENDING COMMITTED-STATE RESEAL' in d
assert 'NOT_AUTHORIZED` pending committed-state manifest/SHA reconciliation and exact full regression.' in d
d = d.replace('FUNCTIONALLY CLOSED PENDING COMMITTED-STATE RESEAL', 'FUNCTIONALLY CLOSED / COMMITTED-STATE RESEALED')
d = d.replace(
    '- V5.6 Candidate: `NOT_AUTHORIZED` pending committed-state manifest/SHA reconciliation and exact full regression.',
    '- Committed-state reseal: `PASS` — Runner `33258401492 / 99116008440`, SHA `97/97`, Python compile `39/39`, full regression `122/122`.\n'
    '- V5.6 Candidate: `NOT_AUTHORIZED` pending separate Candidate authorization review and Candidate-specific seal.'
)
design.write_text(d, encoding='utf-8')

# 3) Manifest: preserve all governance boundaries, add reseal evidence, rebuild source-file inventory/tree hash.
m = json.loads(manifest_path.read_text(encoding='utf-8'))
assert m['artifact_id'] == 'SKILL-BOOK-V5.6-DESIGN-GATE-WIP'
assert m['version'] == '5.6'
assert m['status'] == 'DESIGN_GATE_WIP_NOT_CANDIDATE_NOT_CURRENT'
assert m['runtime_contract_id'] == 'SB56-RUNTIME-CONTRACT-CBE00206'
assert m['validation']['fresh_non_a1_generation'] == 'PASS'
assert m['candidate_authorization'] == 'NOT_AUTHORIZED'
assert m['current_promotion'] == 'NOT_AUTHORIZED'
assert m['real_reader_evidence'] == 'NOT_RUN'

m['validation']['committed_state_reseal'] = 'PASS'
m['validation']['committed_state_reseal_runner_run_job'] = '33258401492 / 99116008440'
m['validation']['committed_state_sha_coverage'] = '97/97 PASS'
m['validation']['committed_state_python_compile'] = '39/39 PASS'
m['validation']['committed_state_full_regression'] = '122/122 PASS'
m['stability'] = 'DESIGN_GATE_FUNCTIONALLY_CLOSED_RESEALED_NOT_CANDIDATE'

excluded = {'MANIFEST.json', 'SHA256SUMS.txt'}
paths = sorted(
    p for p in skill.rglob('*')
    if p.is_file() and '__pycache__' not in p.parts and p.relative_to(skill).as_posix() not in excluded
)
files=[]
tree_lines=[]
for p in paths:
    rel=p.relative_to(skill).as_posix()
    data=p.read_bytes()
    h=hashlib.sha256(data).hexdigest()
    files.append({'path':rel,'bytes':len(data),'sha256':h})
    tree_lines.append(f'{h}  {rel}\n')
tree_sha=hashlib.sha256(''.join(tree_lines).encode('utf-8')).hexdigest()
m['validation']['source_non_manifest_tree_sha256']=tree_sha
m['validation']['source_non_manifest_tree_basis']='sorted path + two spaces + sha256 + LF; excludes MANIFEST.json and SHA256SUMS.txt'
m['files']=files
manifest_path.write_text(json.dumps(m, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

# 4) Full SHA sums over all package files except SHA itself.
rows=[]
for p in sorted(x for x in skill.rglob('*') if x.is_file() and x.name!='SHA256SUMS.txt' and '__pycache__' not in x.parts and x.suffix!='.pyc'):
    rel=p.relative_to(skill).as_posix()
    rows.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel}')
sums_path.write_text('\n'.join(rows)+'\n', encoding='utf-8')

print('V56_DESIGN_GATE_RESEAL_CLOSURE_PREPARED')
print('SOURCE_NON_MANIFEST_TREE_SHA256='+tree_sha)
print('SOURCE_FILE_COUNT='+str(len(files)))
print('SHA_ROWS='+str(len(rows)))
