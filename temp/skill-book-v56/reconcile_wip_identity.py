from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path('.')
OLD_RID = 'SB55-RUNTIME-CONTRACT-6B3D9F21'
NEW_RID = 'SB56-RUNTIME-CONTRACT-CBE00206'


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding='utf-8')


def repl(rel: str, old: str, new: str, count: int = 1) -> None:
    s = read(rel)
    got = s.count(old)
    assert got == count, (rel, old, got, count)
    write(rel, s.replace(old, new))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


# VERSION + agent metadata
write('VERSION', '5.6\n')
agent = read('agents/openai.yaml')
assert agent.count('version: 5.5') == 1
assert agent.count('status: candidate_not_current') == 1
agent = agent.replace('version: 5.5', 'version: 5.6')
agent = agent.replace('status: candidate_not_current', 'status: design_gate_wip_not_candidate')
agent = agent.replace(
    'book-promise responsibility depth, externally verifiable adequacy,',
    'book-promise responsibility depth, role-sensitive practical-asset depth, externally verifiable adequacy,',
)
write('agents/openai.yaml', agent)

# SKILL entry identity + executable V5.6 practical-asset depth rule.
skill = read('SKILL.md')
assert skill.count('# skill-book V5.5 Candidate') == 1
skill = skill.replace(
    '# skill-book V5.5 Candidate',
    '# skill-book V5.6 Design Gate WIP\n\nStatus: `DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT`  \nScope: `Practical Asset Depth / Adequacy`  \nBase: published `skill-book V5.5 Candidate`; Source Current remains `V3.5`.',
)
assert skill.count('## 0A. Runtime Hard Entry Protocol · V5.5 可证明执行入口') == 1
skill = skill.replace('## 0A. Runtime Hard Entry Protocol · V5.5 可证明执行入口', '## 0A. Runtime Hard Entry Protocol · V5.6 可证明执行入口')
skill = skill.replace(OLD_RID, NEW_RID)
assert skill.count('declared_skill_version = 5.5') == 1
skill = skill.replace('declared_skill_version = 5.5', 'declared_skill_version = 5.6')
assert skill.count('evidence/generation_responsibility_pre_draft.json\n') == 1
skill = skill.replace('evidence/generation_responsibility_pre_draft.json\n', 'evidence/generation_responsibility_pre_draft.json\nevidence/generation_responsibility_pre_freeze.json\n')
assert skill.count('evidence/operational_closure_pre_draft.json\n') == 1
skill = skill.replace('evidence/operational_closure_pre_draft.json\n', 'evidence/operational_closure_pre_draft.json\nevidence/operational_closure_pre_freeze.json\n')
assert skill.count('evidence/training_feedback_contract.json\n') == 1
skill = skill.replace('evidence/training_feedback_contract.json\n', 'evidence/training_feedback_contract.json\nevidence/training_feedback_pre_freeze.json\n')
assert skill.count('evidence/adequacy_audit.json\n') == 1
skill = skill.replace('evidence/adequacy_audit.json\n', 'evidence/adequacy_audit.json\nevidence/practical_asset_depth_contract.json\nevidence/practical_asset_depth_audit.json\n')
assert skill.count('evidence/canonical_evidence_requirements.json\n') == 1
skill = skill.replace('evidence/canonical_evidence_requirements.json\n', 'evidence/canonical_evidence_requirements.json\nevidence/random_open_holdout.json\n')
marker = 'Frozen Candidate之后必须先闭合 Baseline Applicability：'
assert skill.count(marker) == 1
depth_rule = '''### V5.6 Practical Asset Depth · 生成期职责深度硬门\n\nV5.6 不再把“出现了某个维度/关键词”当作 Practical Asset 已经够深。对 Reader-facing Practical Asset：\n\n1. **PRE_DRAFT / before asset drafting**：`practical_asset_depth_contract.json` 必须从当前 Book Promise、Reader Transformation、Lifecycle 与 asset role 声明 `roles / complexity / required_dimensions / depth_requirements / promise_links`；不得读取历史 Canonical 来生成字段。\n2. **Role-sensitive depth**：evidence capture、decision record、plan/contract、execution log、acceptance、baseline、iteration、next decision 各自有不同 mandatory sub-responsibilities；不得让一个万能空表自称覆盖全部角色。\n3. **PRE_FREEZE**：必须对实际 Reader-facing assets 运行 `practical_asset_depth_audit.py` 并写 `practical_asset_depth_audit.json`。Keyword presence、字符数、标题数只能作为风险信号，不能替代 evidence→judgment/action、change→revalidation、failure→diagnosis→retry→stop、expected→actual→acceptance 等闭环。\n4. **False-green blocks remain hard**：浅 provenance、断裂 trace chain、只有 Version 字段的 change control、Date/Note-only evidence log、缺 diagnosis/stop 的 retry、单一样例值冒充 guidance 都必须 BLOCK。\n5. **Domain-neutral**：规则不得包含 A1、网站、SEO、部署或软件专用字段；Canonical 仍只允许 FIRST_FREEZE+ evaluator-only。\n\n详细合同见 `references/practical_asset_depth_contract.md`；Runtime Acceptance 必须独立重跑该 verifier，缺 contract/audit evidence 或 external re-audit BLOCK 时不得授权 PASS。\n\n'''
skill = skill.replace(marker, depth_rule + marker)
assert skill.count('`CANDIDATE / NOT CURRENT`：Source Current仍为V3.5。V4.8') == 1
skill = skill.replace('`CANDIDATE / NOT CURRENT`：Source Current仍为V3.5。V4.8', '**Historical V4.8 candidate note**：Source Current当时与现在均为V3.5。V4.8')
write('SKILL.md', skill)

# Runtime receipt / enforcement / fidelity references.
repl('references/runtime_enforcement_contract.md', OLD_RID, NEW_RID)
entry = read('references/runtime_entry_receipt_contract.md')
assert entry.count('# Runtime Entry Receipt Contract · V5.5') == 1
entry = entry.replace('# Runtime Entry Receipt Contract · V5.5', '# Runtime Entry Receipt Contract · V5.6')
entry = entry.replace(OLD_RID, NEW_RID)
assert entry.count('"declared_skill_version": "5.5"') == 1
entry = entry.replace('"declared_skill_version": "5.5"', '"declared_skill_version": "5.6"')
assert entry.count('"evidence/adequacy_audit.json",\n') == 1
entry = entry.replace('"evidence/adequacy_audit.json",\n', '"evidence/adequacy_audit.json",\n    "evidence/practical_asset_depth_contract.json",\n    "evidence/practical_asset_depth_audit.json",\n')
assert entry.count('Skill 版本由 Skill 自身声明为 `5.4`') == 1
entry = entry.replace('Skill 版本由 Skill 自身声明为 `5.4`', 'Skill 版本由 Skill 自身声明为 `5.6`')
entry += '''\n## V5.6 Practical Asset Depth mandatory evidence\n\n`practical_asset_depth_contract.json` is declared from current-run promise / transformation / lifecycle / role responsibilities, and `practical_asset_depth_audit.json` is recomputed on the actual reader-facing assets before Freeze. Both are canonical Runtime Authority inputs; missing or shallow evidence remains BLOCK. Historical Canonical must not be used to generate this contract before FIRST_FREEZE.\n'''
write('references/runtime_entry_receipt_contract.md', entry)

fid = read('references/runtime_authority_fidelity_contract.md')
assert fid.count('# Runtime Authority Fidelity Contract · V5.5') == 1
fid = fid.replace('# Runtime Authority Fidelity Contract · V5.5', '# Runtime Authority Fidelity Contract · V5.6')
fid = fid.replace(OLD_RID, NEW_RID)
assert fid.count('"declared_skill_version": "5.5"') == 1
fid = fid.replace('"declared_skill_version": "5.5"', '"declared_skill_version": "5.6"')
fid += '''\n## V5.6 depth authority inputs\n\nThe canonical input set includes both `evidence/practical_asset_depth_contract.json` and `evidence/practical_asset_depth_audit.json`. A weaker alternate audit cannot authorize Runtime Acceptance when either input is absent or when the published depth verifier blocks.\n'''
write('references/runtime_authority_fidelity_contract.md', fid)

# Runtime executables.
for rel in ('scripts/runtime_acceptance_audit.py', 'scripts/runtime_authority_fidelity_audit.py'):
    s = read(rel)
    assert OLD_RID in s, rel
    s = s.replace(OLD_RID, NEW_RID)
    if rel.endswith('runtime_acceptance_audit.py'):
        assert "EXPECTED_SKILL_VERSION='5.5'" in s
        s = s.replace("EXPECTED_SKILL_VERSION='5.5'", "EXPECTED_SKILL_VERSION='5.6'")
    else:
        assert "VERSION='5.5'" in s
        s = s.replace("VERSION='5.5'", "VERSION='5.6'")
    write(rel, s)

# Runtime fixtures/tests.
for rel in ('tests/test_runtime_acceptance_audit.py', 'tests/test_runtime_authority_fidelity_audit.py'):
    s = read(rel)
    assert OLD_RID in s, rel
    s = s.replace(OLD_RID, NEW_RID)
    n = s.count("'declared_skill_version':'5.5'")
    assert n >= 1, (rel, n)
    s = s.replace("'declared_skill_version':'5.5'", "'declared_skill_version':'5.6'")
    write(rel, s)

# Package self-contract test becomes WIP identity aware while preserving inherited gates.
t = read('tests/test_skill_contract.py')
t = t.replace("self.assertEqual((R/'VERSION').read_text().strip(),'5.5')", "self.assertEqual((R/'VERSION').read_text().strip(),'5.6')")
t = t.replace("self.assertIn('version: 5.5',s);self.assertIn('status: candidate_not_current',s)", "self.assertIn('version: 5.6',s);self.assertIn('status: design_gate_wip_not_candidate',s)")
t = t.replace("self.assertIn('skill-book V5.5 Candidate',s);self.assertIn('CANDIDATE / NOT CURRENT',s)", "self.assertIn('skill-book V5.6 Design Gate WIP',s);self.assertIn('DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT',s)")
t = t.replace(OLD_RID, NEW_RID)
t = t.replace("self.assertIn('\"5.5\"',r)", "self.assertIn('\"5.6\"',r)")
needle = "for p in ['scripts/adequacy_audit.py','scripts/postdraft_baseline_audit.py','scripts/generation_responsibility_audit.py','scripts/prefreeze_random_open_audit.py','scripts/runtime_acceptance_audit.py']:"
assert needle in t
t = t.replace(needle, "for p in ['scripts/adequacy_audit.py','scripts/practical_asset_depth_audit.py','scripts/postdraft_baseline_audit.py','scripts/generation_responsibility_audit.py','scripts/prefreeze_random_open_audit.py','scripts/runtime_acceptance_audit.py']:")
needle2 = "self.assertTrue((R/'references/phase_depth_preservation_contract.md').exists())\n  r=(R/'references/runtime_entry_receipt_contract.md').read_text();"
assert needle2 in t
t = t.replace(needle2, "self.assertTrue((R/'references/phase_depth_preservation_contract.md').exists());self.assertTrue((R/'references/practical_asset_depth_contract.md').exists())\n  self.assertIn('Practical Asset Depth',s)\n  r=(R/'references/runtime_entry_receipt_contract.md').read_text();")
write('tests/test_skill_contract.py', t)

# WIP source identity: truthful, explicitly non-candidate.
source_identity = f'''# skill-book V5.6 Design Gate WIP Source Identity\n\n- Version: `5.6`\n- Status: `DESIGN_GATE / WIP / NOT CANDIDATE / NOT CURRENT`\n- Runtime Contract ID: `{NEW_RID}`\n- Base: published `skill-book V5.5 Candidate` exact source commit `b3b73d2a05e7ef2e497817cea7210c7f4504db05`\n- Previous Published Candidate: `V5.5`\n- Source Current: `V3.5`\n- Scope: `Practical Asset Depth / Adequacy`\n- Non-A1 adversarial domain: `20-person offline reading club`\n- Non-A1 targeted depth matrix: `12/12 PASS`\n- Inherited Adequacy targeted suite: `6/6 PASS`\n- Runtime depth integration gate: `36/36 PASS`\n- Exact WIP full regression before identity reconciliation: `122/122 PASS`\n- Python compile before identity reconciliation: `39/39 PASS`\n- Fresh non-A1 generation test: `NOT_RUN`\n- Historical Canonical boundary: `FIRST_FREEZE+ evaluator-only; never generation template`\n- Real Reader Evidence: `NOT_RUN`\n- Candidate Authorization: `NOT_AUTHORIZED`\n- Current Promotion: `NOT_AUTHORIZED`\n- Release / prerelease / immutable candidate seal: `NOT_APPLICABLE_WIP`\n\nThis WIP exists to close responsibility-depth false greens without restoring historical Canonical structure. Machine PASS does not establish Reader Outcome or Candidate authorization.\n'''
write('SOURCE_PACKAGE_IDENTITY.md', source_identity)

# Rebuild truthful WIP manifest from current bytes, excluding manifest + checksum file from its own tree basis.
excluded = {'MANIFEST.json', 'SHA256SUMS.txt'}
paths = sorted(
    p for p in ROOT.rglob('*')
    if p.is_file()
    and '__pycache__' not in p.parts
    and p.relative_to(ROOT).as_posix() not in excluded
)
files = []
tree_lines = []
for p in paths:
    rel = p.relative_to(ROOT).as_posix()
    data = p.read_bytes()
    h = sha256_bytes(data)
    files.append({'path': rel, 'bytes': len(data), 'sha256': h})
    tree_lines.append(f'{h}  {rel}\n')
tree_sha = sha256_bytes(''.join(tree_lines).encode('utf-8'))
manifest = {
    'artifact_id': 'SKILL-BOOK-V5.6-DESIGN-GATE-WIP',
    'version': '5.6',
    'status': 'DESIGN_GATE_WIP_NOT_CANDIDATE_NOT_CURRENT',
    'build_date': '2026-08-29',
    'method_lineage': 'V3.5 Current -> V4.x/V5.x Candidates -> V5.5 Published Candidate -> V5.6 Design Gate WIP',
    'previous_published_candidate_skill': '5.5',
    'source_current_skill': '3.5',
    'runtime_contract_id': NEW_RID,
    'v56_scope': 'PRACTICAL_ASSET_DEPTH_ADEQUACY',
    'package_seal_state': {
        'candidate_seal': 'NOT_APPLICABLE_WIP_NOT_CANDIDATE',
        'deterministic_candidate_zip': 'NOT_RUN',
        'remote_exact_source': 'NOT_RUN',
        'prerelease': 'NOT_AUTHORIZED',
    },
    'validation': {
        'source_non_manifest_tree_sha256': tree_sha,
        'source_non_manifest_tree_basis': 'sorted path + two spaces + sha256 + LF; excludes MANIFEST.json and SHA256SUMS.txt',
        'non_a1_practical_asset_depth': '12/12 PASS',
        'inherited_adequacy': '6/6 PASS',
        'runtime_depth_integration': '36/36 PASS',
        'pre_identity_full_regression': '122/122 PASS',
        'pre_identity_python_compile': '39/39 PASS',
        'fresh_non_a1_generation': 'NOT_RUN',
        'real_reader_evidence': 'NOT_RUN',
    },
    'stability': 'DESIGN_GATE_WIP_NOT_CANDIDATE',
    'backend_installed_runtime': 'NOT_RUN',
    'real_reader_evidence': 'NOT_RUN',
    'candidate_authorization': 'NOT_AUTHORIZED',
    'current_promotion': 'NOT_AUTHORIZED',
    'historical_canonical_policy': 'FIRST_FREEZE_PLUS_EVALUATOR_ONLY_NOT_GENERATION_TEMPLATE',
    'files': files,
}
write('MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')

# SHA256SUMS covers every package file except SHA256SUMS itself, including MANIFEST.
sum_paths = sorted(
    p for p in ROOT.rglob('*')
    if p.is_file()
    and '__pycache__' not in p.parts
    and p.relative_to(ROOT).as_posix() != 'SHA256SUMS.txt'
)
write('SHA256SUMS.txt', ''.join(f'{sha256_file(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in sum_paths))

print(f'V56_WIP_IDENTITY_RECONCILED runtime_contract_id={NEW_RID} files={len(files)+2} sha_entries={len(sum_paths)} tree_sha={tree_sha}')
