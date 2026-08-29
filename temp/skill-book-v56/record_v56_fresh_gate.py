from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
skill = root / 'skills/skill-book/V5.6'
design = root / 'mother-specs/skill-book/V5.6/SKILL_BOOK_V5.6_DESIGN_GATE.md'
manifest_path = skill / 'MANIFEST.json'
sums_path = skill / 'SHA256SUMS.txt'

assert skill.is_dir()
assert design.is_file()
assert manifest_path.is_file()
assert sums_path.is_file()

# Record the already-completed exact-source fresh non-A1 generation evidence.
text = design.read_text(encoding='utf-8')
assert '## 15. Fresh Non-A1 Generation Evidence' not in text
assert '- V5.6 Candidate: `NOT_AUTHORIZED`' in text
text = text.rstrip() + r'''

## 15. Fresh Non-A1 Generation Evidence

Status: `PASS` on exact V5.6 WIP source `c3b19fe5ccb751019443495f3dc975f3ab8ab046`.

Test identity:

- Test ID: `V5.6_FRESH_NON_A1_READING_CLUB_20260829`
- Domain: `20-person offline reading club`
- Runner workflow run / job: `33258236680 / 99115573137`
- Canonical used during generation: `false`
- Real Reader Evidence: `NOT_RUN`
- Fresh reader-facing chapters: `3`
- Fresh practical assets: `8`

Good-generation gates:

- Generation Responsibility PRE_DRAFT: `PASS`
- Generation Responsibility PRE_FREEZE: `PASS`
- Operational Closure PRE_DRAFT: `PASS`
- Operational Closure PRE_FREEZE: `PASS`
- Training Feedback PRE_FREEZE: `PASS`
- Adequacy: `PASS`
- Practical Asset Depth: `PASS`
- Pre-freeze Random Open: `PASS`
- Shadow Local Value: `PASS`

Adversarial proof:

1. Replace `templates/07_post_event_iteration_log.md` with a long, structured, keyword-complete but trace-shallow asset.
2. Existing Adequacy Gate: `PASS_FALSE_GREEN_REPRODUCED`.
3. V5.6 Practical Asset Depth Gate: `BLOCK_AS_REQUIRED` with:
   - `PRACTICAL_ASSET_EVIDENCE_LOG_SHALLOW`
   - `PRACTICAL_ASSET_RECOVERY_LOOP_INCOMPLETE`
4. Restore the original generated asset without changing verifier or contract.
5. Practical Asset Depth Gate: `PASS`.

This closes the mandatory fresh non-A1 generation requirement in the Design Gate sequence. It does **not** constitute Real Reader evidence and does **not** by itself authorize Candidate or Current promotion.

## 16. Post-Fresh-Gate Decision

- V5.5: `100% COMPLETE / IMMUTABLE PUBLISHED CANDIDATE`
- V5.6 Design Gate implementation: `FUNCTIONALLY CLOSED PENDING COMMITTED-STATE RESEAL`
- Fresh non-A1 generation: `PASS`
- Real Reader Evidence: `NOT_RUN`
- V5.6 Candidate: `NOT_AUTHORIZED` pending committed-state manifest/SHA reconciliation and exact full regression.
- Source Current promotion: `NOT_AUTHORIZED`
'''
design.write_text(text + '\n', encoding='utf-8')

manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
assert manifest['artifact_id'] == 'SKILL-BOOK-V5.6-DESIGN-GATE-WIP'
assert manifest['version'] == '5.6'
assert manifest['status'] == 'DESIGN_GATE_WIP_NOT_CANDIDATE_NOT_CURRENT'
assert manifest['runtime_contract_id'] == 'SB56-RUNTIME-CONTRACT-CBE00206'
assert manifest['validation']['fresh_non_a1_generation'] == 'NOT_RUN'
assert manifest['validation']['source_non_manifest_tree_sha256'] == 'cb1c2f0229e8b748490c447c919feed4cb40d0bc80068c58711f0cd772a2b190'
assert manifest['candidate_authorization'] == 'NOT_AUTHORIZED'
assert manifest['current_promotion'] == 'NOT_AUTHORIZED'

manifest['validation']['fresh_non_a1_generation'] = 'PASS'
manifest['validation']['fresh_non_a1_test_id'] = 'V5.6_FRESH_NON_A1_READING_CLUB_20260829'
manifest['validation']['fresh_non_a1_runner_run_job'] = '33258236680 / 99115573137'
manifest['validation']['fresh_non_a1_good_generation_gates'] = '9/9 PASS'
manifest['validation']['fresh_non_a1_adversarial'] = 'OLD_ADEQUACY_FALSE_GREEN_REPRODUCED -> DEPTH_BLOCK_AS_REQUIRED -> REPAIR_PASS'
manifest['validation']['fresh_non_a1_depth_blocks'] = [
    'PRACTICAL_ASSET_EVIDENCE_LOG_SHALLOW',
    'PRACTICAL_ASSET_RECOVERY_LOOP_INCOMPLETE',
]
manifest['validation']['fresh_non_a1_verifier_changed_during_repair'] = False
manifest['validation']['fresh_non_a1_contract_changed_during_repair'] = False
manifest['validation']['real_reader_evidence'] = 'NOT_RUN'
manifest['stability'] = 'DESIGN_GATE_WIP_FRESH_NON_A1_PASS_PENDING_RESEAL'
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Rebuild SHA256SUMS deterministically. SHA256SUMS cannot hash itself.
rows = []
for p in sorted(x for x in skill.rglob('*') if x.is_file() and x.name != 'SHA256SUMS.txt'):
    rel = p.relative_to(skill).as_posix()
    if '__pycache__' in p.parts or p.suffix == '.pyc':
        raise AssertionError(f'forbidden generated file: {rel}')
    rows.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel}")
sums_path.write_text('\n'.join(rows) + '\n', encoding='utf-8')

# The source tree excluding MANIFEST/SHA is unchanged by this evidence-only reconciliation.
h = hashlib.sha256()
for p in sorted(x for x in skill.rglob('*') if x.is_file() and x.name not in {'MANIFEST.json', 'SHA256SUMS.txt'}):
    rel = p.relative_to(skill).as_posix()
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    h.update(f'{rel}  {digest}\n'.encode())
assert h.hexdigest() == manifest['validation']['source_non_manifest_tree_sha256']

print('V56_FRESH_GATE_EVIDENCE_RECORDED')
print('SOURCE_NON_MANIFEST_TREE_SHA256=' + h.hexdigest())
print('SHA_ROWS=' + str(len(rows)))
