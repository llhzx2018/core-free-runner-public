#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

repo=Path(sys.argv[1]).resolve()
root=repo/'skills'/'skill-book'/'V5.7'
RID='SB57-RUNTIME-CONTRACT-8ADCAF17'
VERSION='5.7'

ALLOWED={
 'VERSION','agents/openai.yaml','SKILL.md','SOURCE_PACKAGE_IDENTITY.md','MANIFEST.json','SHA256SUMS.txt',
 'references/runtime_entry_receipt_contract.md','references/runtime_authority_fidelity_contract.md','references/runtime_enforcement_contract.md',
 'scripts/runtime_acceptance_audit.py','scripts/runtime_authority_fidelity_audit.py',
 'tests/test_runtime_acceptance_audit.py','tests/test_runtime_authority_fidelity_audit.py','tests/test_skill_contract.py',
}

def read(rel): return (root/rel).read_text(encoding='utf-8')
def write(rel,text):
    p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')
def replace(rel,old,new,count=1):
    s=read(rel)
    if s.count(old)<count: raise SystemExit(f'ANCHOR_MISSING {rel}: {old[:100]!r}')
    write(rel,s.replace(old,new,count))
def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def compact_tree_hash():
    rows=[]
    for p in sorted(x for x in root.rglob('*') if x.is_file()):
        rel=p.relative_to(root).as_posix()
        if rel in {'MANIFEST.json','SHA256SUMS.txt'}: continue
        rows.append(f'{rel}  {sha(p)}')
    return hashlib.sha256(('\n'.join(rows)+'\n').encode()).hexdigest(),rows

# VERSION / agent metadata.
write('VERSION','5.7\n')
write('agents/openai.yaml',"""name: skill-book
version: 5.7
status: design_gate_wip_not_candidate_not_current
entry: SKILL.md
summary: Reader-outcome book generation with runtime-entry receipts, baseline applicability, freeze integrity, operational closure, training feedback, practical-asset depth, and V5.7 blind-reader transfer validation across READ / LEARN / TRAIN / DO. Blind-reader proxy evidence never authorizes Real Reader evidence.

# V5.7 WIP: reader transfer / blind reader outcome validation
""")

# SKILL active identity and Reader Transfer entry contract.
replace('SKILL.md','# skill-book V5.6 Candidate','# skill-book V5.7 Design Gate WIP')
replace('SKILL.md','Status: `CANDIDATE / NOT CURRENT`  \nScope: `Practical Asset Depth / Adequacy`  \nBase: published `skill-book V5.5 Candidate`; Source Current remains `V3.5`.','Status: `DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT`  \nScope: `Reader Transfer / Blind Reader Outcome Validation`  \nBase: published `skill-book V5.6 Candidate`; Source Current remains `V3.5`.')
replace('SKILL.md','## 0A. Runtime Hard Entry Protocol · V5.6 可证明执行入口','## 0A. Runtime Hard Entry Protocol · V5.7 可证明执行入口')
replace('SKILL.md','RUNTIME_CONTRACT_ID = SB56-RUNTIME-CONTRACT-CBE00206`、`declared_skill_version = 5.6','RUNTIME_CONTRACT_ID = SB57-RUNTIME-CONTRACT-8ADCAF17`、`declared_skill_version = 5.7')
replace('SKILL.md','evidence/practical_asset_depth_contract.json\nevidence/practical_asset_depth_audit.json\nevidence/prefreeze_random_open.json','evidence/practical_asset_depth_contract.json\nevidence/practical_asset_depth_audit.json\nevidence/reader_transfer_contract.json\nevidence/reader_transfer_proxy.json\nevidence/reader_transfer_audit.json\nevidence/prefreeze_random_open.json')
anchor='详细合同见 `references/practical_asset_depth_contract.md`；Runtime Acceptance 必须独立重跑该 verifier，缺 contract/audit evidence 或 external re-audit BLOCK 时不得授权 PASS。\n'
section='''\n### V5.7 Reader Transfer · Blind Reader Outcome Validation 硬门\n\nV5.7 在 V5.6 Practical Asset Depth 之后增加一个不同的问题：**资产本身够深，不代表第一次接触它的读者真的能迁移判断并继续执行。** 因此在适用的 FULL_BOOK / SEALED 候选进入 Candidate 授权前，必须产生：\n\n```text\nevidence/reader_transfer_contract.json\nevidence/reader_transfer_proxy.json\nevidence/reader_transfer_audit.json\n```\n\n规则：\n\n1. Proxy 必须声明 `kind = BLIND_READER_PROXY`、`fresh = true`、`real_reader = false`，并且 blind to `generation_contract / verifier / canonical`。\n2. **READ** 必须从 reader-facing bytes 取回 sequence / boundary / next decision。\n3. **LEARN** 必须在 changed case 上解释 rule/rationale，并识别 intentionally plausible near-miss；选错必须 `NEAR_MISS_CONFUSION = BLOCK`。\n4. **TRAIN** 必须存在真实 first-attempt responsibility failure → targeted feedback → materially changed retry；重试未修复原失败职责必须 `RETRY_DID_NOT_REPAIR_RESPONSIBILITY = BLOCK`。\n5. **DO** 必须产出 actionable artifact + acceptance results；需要 handoff 时 operator 2 必须从 linked state / evidence / next action 独立继续，否则 `OPERATOR_HANDOFF_NOT_SELF_SUFFICIENT = BLOCK`。\n6. `BLIND_READER_PROXY_PASS != REAL_READER_PASS`。Proxy 永远不能把 `REAL_READER_EVIDENCE` 从 `NOT_RUN` 提升为 PASS/PARTIAL。\n7. Unit fixture PASS 不能授权 Candidate。Candidate 前还必须执行一次与 unit fixtures 隔离的 fresh blind proxy；若运行环境无法提供真正隔离的 proxy，则记录 `FRESH_ISOLATED_BLIND_PROXY = NOT_RUN / BLOCK`，不得伪造。\n\n详细合同见 `references/reader_transfer_contract.md`；Runtime Acceptance 必须重新执行 `reader_transfer_audit.py`，而 Runtime Authority Fidelity 必须把三份 Reader Transfer evidence 视为 canonical inputs。\n'''
if anchor not in read('SKILL.md'): raise SystemExit('SKILL_TRANSFER_INSERT_ANCHOR_MISSING')
write('SKILL.md',read('SKILL.md').replace(anchor,anchor+section,1))

# Runtime receipt contract identity + transfer inputs.
s=read('references/runtime_entry_receipt_contract.md')
s=s.replace('# Runtime Entry Receipt Contract · V5.6','# Runtime Entry Receipt Contract · V5.7',1)
s=s.replace('SB56-RUNTIME-CONTRACT-CBE00206',RID)
s=s.replace('"declared_skill_version": "5.6"','"declared_skill_version": "5.7"',1)
s=s.replace('Skill 版本由 Skill 自身声明为 `5.6`','Skill 版本由 Skill 自身声明为 `5.7`',1)
s=s.replace('    "evidence/practical_asset_depth_audit.json",\n    "evidence/prefreeze_random_open.json",','    "evidence/practical_asset_depth_audit.json",\n    "evidence/reader_transfer_contract.json",\n    "evidence/reader_transfer_proxy.json",\n    "evidence/reader_transfer_audit.json",\n    "evidence/prefreeze_random_open.json",',1)
s += '''\n\n## V5.7 Reader Transfer mandatory evidence\n\n`reader_transfer_contract.json`, `reader_transfer_proxy.json`, and `reader_transfer_audit.json` are canonical Runtime Authority inputs. A proxy receipt must remain blind/fresh/non-human, and even `BLIND_READER_PROXY_PASS` leaves `REAL_READER_EVIDENCE = NOT_RUN`. Candidate authorization additionally requires a fresh isolated proxy run outside the unit-fixture path.\n'''
write('references/runtime_entry_receipt_contract.md',s)

# Runtime fidelity contract identity and transfer authority inputs.
s=read('references/runtime_authority_fidelity_contract.md')
s=s.replace('# Runtime Authority Fidelity Contract · V5.6','# Runtime Authority Fidelity Contract · V5.7',1)
s=s.replace('SB56-RUNTIME-CONTRACT-CBE00206',RID)
s=s.replace('"declared_skill_version": "5.6"','"declared_skill_version": "5.7"',1)
s += '''\n\n## V5.7 Reader Transfer authority inputs\n\nThe canonical Runtime input set additionally includes `evidence/reader_transfer_contract.json`, `evidence/reader_transfer_proxy.json`, and `evidence/reader_transfer_audit.json`. Missing inputs or a blocked external re-audit forbid Runtime Acceptance. Proxy authority is strictly machine/proxy-only and cannot promote Real Reader status.\n'''
write('references/runtime_authority_fidelity_contract.md',s)

# Runtime enforcement active RID and transfer evidence.
s=read('references/runtime_enforcement_contract.md').replace('RUNTIME_CONTRACT_ID = SB56-RUNTIME-CONTRACT-CBE00206',f'RUNTIME_CONTRACT_ID = {RID}',1)
s=s.replace('- `evidence/adequacy_contract.json`\n- `evidence/adequacy_audit.json`','- `evidence/adequacy_contract.json`\n- `evidence/adequacy_audit.json`\n- `evidence/reader_transfer_contract.json`\n- `evidence/reader_transfer_proxy.json`\n- `evidence/reader_transfer_audit.json`',1)
s += '''\n\n## V5.7 Reader Transfer enforcement\n\nA structurally adequate/deep book may still fail transfer. Runtime Acceptance therefore independently re-runs the Reader Transfer verifier. Near-miss confusion, non-repairing retry, non-actionable DO output, or a broken operator handoff remains BLOCK. `BLIND_READER_PROXY_PASS` never authorizes Real Reader evidence.\n'''
write('references/runtime_enforcement_contract.md',s)

# Active Runtime code identity.
for rel in ('scripts/runtime_acceptance_audit.py','scripts/runtime_authority_fidelity_audit.py'):
    s=read(rel).replace('SB56-RUNTIME-CONTRACT-CBE00206',RID).replace("EXPECTED_SKILL_VERSION='5.6'","EXPECTED_SKILL_VERSION='5.7'").replace("VERSION='5.6'","VERSION='5.7'")
    write(rel,s)

# Runtime tests active identity.
for rel in ('tests/test_runtime_acceptance_audit.py','tests/test_runtime_authority_fidelity_audit.py'):
    s=read(rel).replace('SB56-RUNTIME-CONTRACT-CBE00206',RID)
    s=s.replace("declared_skill_version':'5.6'","declared_skill_version':'5.7'")
    write(rel,s)

# Skill contract tests: WIP identity + Reader Transfer presence.
s=read('tests/test_skill_contract.py')
s=s.replace("'5.6')","'5.7')",1)
s=s.replace("'version: 5.6'","'version: 5.7'",1).replace("'status: candidate_not_current'","'status: design_gate_wip_not_candidate_not_current'",1)
s=s.replace("self.assertIn('skill-book V5.6 Candidate',s);self.assertIn('CANDIDATE / NOT CURRENT',s)","self.assertIn('skill-book V5.7 Design Gate WIP',s);self.assertIn('DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT',s)",1)
s=s.replace('SB56-RUNTIME-CONTRACT-CBE00206',RID)
s=s.replace("self.assertIn('\"5.6\"',r)","self.assertIn('\"5.7\"',r)",1)
needle="  self.assertIn('Practical Asset Depth',s)\n"
insert="  self.assertIn('Practical Asset Depth',s)\n  for x in ['V5.7 Reader Transfer','BLIND_READER_PROXY_PASS != REAL_READER_PASS','reader_transfer_contract.json','reader_transfer_proxy.json','reader_transfer_audit.json','FRESH_ISOLATED_BLIND_PROXY']:\n   self.assertIn(x,s)\n  for p in ['references/reader_transfer_contract.md','scripts/reader_transfer_audit.py','tests/test_reader_transfer_audit.py','tests/test_reader_transfer_v56_false_green_bridge.py']:\n   self.assertTrue((R/p).exists())\n"
if needle not in s: raise SystemExit('SKILL_TEST_INSERT_ANCHOR_MISSING')
s=s.replace(needle,insert,1)
write('tests/test_skill_contract.py',s)

# WIP source package identity (avoid recursive package hash claims here).
write('SOURCE_PACKAGE_IDENTITY.md',f'''# skill-book V5.7 WIP Source Package Identity\n\n- Version: `5.7`\n- Status: `DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT`\n- Runtime Contract ID: `{RID}`\n- Base: published `skill-book V5.6 Candidate` exact source commit `b32fda1c75fdbc4d2e40aaaa444ba7b31e06bd28`\n- Previous Published Candidate: `V5.6`\n- Source Current: `V3.5`\n- Scope: `Reader Transfer / Blind Reader Outcome Validation`\n- RED baseline: `PASS` — `33260166701 / 99120618260`\n- Test-first implementation RED: `PASS` — `33260287817 / 99120939742`\n- Reader Transfer targeted: `13/13 PASS`\n- V5.6-depth-green / V5.7-transfer-red bridge: `3/3 PASS`\n- Runtime transfer integration: `42/42 PASS` — `33260531471 / 99121582353`\n- Pre-identity full regression: `140/140 PASS`\n- Pre-identity Python compile: `42/42 PASS`\n- Fresh isolated blind proxy: `NOT_RUN / BLOCK`\n- Real Reader Evidence: `NOT_RUN`\n- Candidate Authorization: `NOT_AUTHORIZED / BLOCKED_PENDING_FRESH_ISOLATED_PROXY`\n- Current Promotion: `NOT_AUTHORIZED`\n- Historical Canonical boundary: `FIRST_FREEZE+ evaluator-only; never generation template`\n\nMachine tests prove verifier behavior and runtime integration only. They do not constitute an isolated blind-reader execution and do not constitute Real Reader evidence.\n''')

# Rebuild WIP manifest from actual source bytes, excluding recursive manifest/SHA entries.
tree_sha,tree_rows=compact_tree_hash()
files=[]
for p in sorted(x for x in root.rglob('*') if x.is_file()):
    rel=p.relative_to(root).as_posix()
    if rel in {'MANIFEST.json','SHA256SUMS.txt'}: continue
    files.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha(p)})
manifest={
 'artifact_id':'SKILL-BOOK-V5.7-DESIGN-GATE-WIP',
 'version':'5.7',
 'status':'DESIGN_GATE_WIP_NOT_CANDIDATE_NOT_CURRENT',
 'build_date':'2026-08-29',
 'method_lineage':'V3.5 Current -> V4.x/V5.x Candidates -> V5.6 Published Candidate -> V5.7 Design Gate WIP',
 'previous_published_candidate_skill':'5.6',
 'source_current_skill':'3.5',
 'runtime_contract_id':RID,
 'v57_scope':'READER_TRANSFER_BLIND_READER_OUTCOME_VALIDATION',
 'validation':{
   'expected_red_baseline':'PASS','expected_red_runner_run_job':'33260166701 / 99120618260',
   'test_first_implementation_red':'13/13 EXPECTED RED','test_first_red_runner_run_job':'33260287817 / 99120939742',
   'reader_transfer_targeted':'13/13 PASS','v56_depth_green_v57_transfer_red_bridge':'3/3 PASS',
   'runtime_transfer_integration':'42/42 PASS','runtime_transfer_runner_run_job':'33260531471 / 99121582353',
   'pre_identity_full_regression':'140/140 PASS','pre_identity_python_compile':'42/42 PASS',
   'source_non_manifest_tree_sha256':tree_sha,
   'source_non_manifest_tree_basis':'sorted path + two spaces + sha256 + LF; excludes MANIFEST.json and SHA256SUMS.txt',
   'fresh_isolated_blind_proxy':'NOT_RUN','real_reader_evidence':'NOT_RUN'
 },
 'candidate_authorization':'NOT_AUTHORIZED_BLOCKED_PENDING_FRESH_ISOLATED_PROXY',
 'current_promotion':'NOT_AUTHORIZED',
 'backend_installed_runtime':'NOT_RUN',
 'real_reader_evidence':'NOT_RUN',
 'historical_canonical_policy':'FIRST_FREEZE_PLUS_EVALUATOR_ONLY_NOT_GENERATION_TEMPLATE',
 'files':files,
}
write('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

# SHA256SUMS covers every file except itself, including the final WIP manifest.
sha_rows=[]
for p in sorted(x for x in root.rglob('*') if x.is_file()):
    rel=p.relative_to(root).as_posix()
    if rel=='SHA256SUMS.txt': continue
    sha_rows.append(f'{sha(p)}  {rel}')
write('SHA256SUMS.txt','\n'.join(sha_rows)+'\n')

# Hard identity assertions before caller runs tests.
assert read('VERSION').strip()=='5.7'
assert RID in read('SKILL.md') and 'V5.7 Reader Transfer' in read('SKILL.md')
assert 'DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT' in read('SKILL.md')
assert 'FRESH_ISOLATED_BLIND_PROXY' in read('SKILL.md')
assert manifest['candidate_authorization'].startswith('NOT_AUTHORIZED')
assert manifest['validation']['fresh_isolated_blind_proxy']=='NOT_RUN'
assert manifest['real_reader_evidence']=='NOT_RUN'
print('V57_WIP_IDENTITY_RECONCILIATION_APPLIED')
print(f'V57_NON_MANIFEST_TREE_SHA256={tree_sha}')
print(f'V57_MANIFEST_SOURCE_FILES={len(files)}')
print(f'V57_SHA_ENTRIES={len(sha_rows)}')
