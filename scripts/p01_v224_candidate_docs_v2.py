from pathlib import Path
import runpy, json
runpy.run_path('../runner/scripts/p01_v224_candidate_docs.py', run_name='__main__')
root=Path('.')
old='4a064d7ea34998b4f8103d23e96b2e10be46267c'
new='bc1cc0e3640de4547a1453c1b15fa740f8fae9f3'
gate='33153766756'

def edit(path, fn):
    p=root/path; p.write_text(fn(p.read_text(encoding='utf-8')),encoding='utf-8')

edit('docs/authority/CURRENT.md',lambda t:t.replace(f'V2.24 Candidate Runtime Source: {old}',f'V2.24 Candidate Runtime Source: {new}').replace(f'PR #27 -> develop: {old}',f'PR #27 -> develop: {old}\nPR #26 Human-readable System Baseline -> develop: {new} / Gate {gate} PASS'))
edit('docs/authority/SSOT.md',lambda t:t.replace(f'Current Candidate Runtime Source: {old}',f'PR #27 UX Runtime Source: {old}\nHuman-readable System Baseline: {new} / {gate} PASS\nCurrent Candidate Runtime Source: {new}'))
edit('docs/authority/RPD.md',lambda t:t.replace(f'当前 Candidate Runtime Source：`{old}`',f'当前 Candidate Runtime Source：`{new}`（含 PR #26 Human-readable System Baseline；`{gate}` PASS）'))
edit('docs/architecture/P01_MULTI_SURFACE_ARCHITECTURE.md',lambda t:t.replace(f'Candidate Runtime Source: {old}',f'PR #27 UX Runtime Source: {old}\nHuman-readable System Baseline: {new} / {gate} PASS\nCandidate Runtime Source: {new}'))
edit('docs/authority/ACCEPTANCE_MATRIX.md',lambda t:t.replace(f'| PR #27 -> develop runtime source | PASS / `{old}` |',f'| PR #27 -> develop UX runtime source | PASS / `{old}` |\n| PR #26 Human-readable System Baseline | PASS / `{new}` / `{gate}` |\n| Current Candidate Runtime Source | `{new}` |'))
for name in ['README.md','docs/README.md']:
    edit(name,lambda t:t.replace(f'Candidate Runtime Source：`{old}`',f'Candidate Runtime Source：`{new}`'))
edit('docs/evidence/P01_V2.24.0_UX_UI_CANDIDATE_20260828.md',lambda t:t.replace(f'- PR #27 develop runtime source: `{old}`',f'- PR #27 UX develop source: `{old}`\n- PR #26 Human-readable System Baseline develop source: `{new}` / Run `{gate}` PASS\n- Current Candidate Runtime Source: `{new}`'))
edit('CHANGELOG.md',lambda t:t.replace(f'Candidate runtime source `{old}`',f'Candidate runtime source `{new}`').replace('- Schema unchanged; no V2.24 Release or Production write.','- Human-readable System Baseline integrated by PR #26 / `33153766756` PASS.\n- Schema unchanged; no V2.24 Release or Production write.',1))
p=root/'VF_PROJECT.json'; j=json.loads(p.read_text(encoding='utf-8')); c=j.setdefault('current_change',{}); c['pr27_ux_runtime_source']=old; c['human_readable_system_baseline_source']=new; c['human_readable_system_baseline_gate']=int(gate); c['human_readable_system_baseline_result']='PASS'; c['final_runtime_source']=new; j['current_authority']=f'Owner Production V2.23.0 / Schema 2026082801; V2.24.0 Candidate Runtime {new}; UX/UI screenshot audit, fixes and human-readable System Baseline PASS; not released'; p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
