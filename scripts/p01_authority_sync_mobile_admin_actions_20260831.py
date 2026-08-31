from pathlib import Path
import json

SOURCE='7a9e9fd3e2505e85d7aa5781da8b23db7d961a9f'
TREE='d322efb883301c4f79570372908a0319b21c45a3'
CANDIDATE='285a25a7aa2741687a45d73191aaa4bfcd6f39f1'
BLOB='fbfe49ec284ade03414010466e83d9ffd590f94a'
DIAG=33399500538
DIAG_ART=9760671622
DIAG_DIGEST='9154a884b17a313f0b2d008f8d9dffd6fb2d1a81e155bed0120ef50eadab411a'
GATE=33399954260
ART=9760859985
DIGEST='43a7a2d252e7346159900137f77ff8e2c119a25c1f394df999e96bcfe14af5c4'

current_section=f'''### Shared mobile admin action targets\n\nPR #151 normalizes high-frequency mobile admin action touch targets across the five permanent backend modules and is merged to `develop` only.\n\n```text\nPR: #151 / MERGED\nExact Product Candidate: {CANDIDATE}\nCurrent L2 runtime Product Source: {SOURCE}\nCurrent L2 runtime Product Tree: {TREE}\nScope: src/assets/admin-consolidation.css only / +5 -0\nMerged blob: {BLOB}\nDiagnostic Run: {DIAG} / SHARED DEFECT REPRODUCED\nDiagnostic Artifact: {DIAG_ART}\nDiagnostic Digest: sha256:{DIAG_DIGEST}\nAuthoritative Machine Gate: {GATE} / PASS\nEvidence Artifact: {ART}\nDigest: sha256:{DIGEST}\n```\n\nThe 390px diagnostic showed the shared mobile Shell menu/return controls at 36x36px and primary page actions commonly at 34-35px across `links-admin`, `browser-helper`, `data-safety`, `settings` and `update`, while every page remained horizontally overflow-free and SQLite remained healthy. The final <=768px CSS-only rule sets mobile Shell menu/return to at least 40x40 and visible page `.btn` / expandable `summary` actions to at least 40px high. Final Chromium verified all five permanent modules at 390px with action targets >=40px and document overflow 0, while 1440px stayed outside the mobile rule. Existing links-admin page-select/filter/mode/lifecycle/state-aware batch regressions remain PASS; SQLite integrity=`ok`, FK=`0`. Inputs/selects/file controls were intentionally not generalized by this change because the diagnostic did not establish them as a usability defect. Schema/version are unchanged; Release/Tag/core-updates/Owner Production/Runner main writes are NO.\n\n'''

# CURRENT.md
p=Path('docs/authority/CURRENT.md'); s=p.read_text()
assert '### Shared mobile admin action targets' not in s
if '> 状态：`CURRENT / V2.35.3 PRODUCTION CLOSURE PASS / L2 MOBILE TOUCH TARGET PASS`' in s:
    s=s.replace('> 状态：`CURRENT / V2.35.3 PRODUCTION CLOSURE PASS / L2 MOBILE TOUCH TARGET PASS`','> 状态：`CURRENT / V2.35.3 PRODUCTION CLOSURE PASS / L2 MOBILE ADMIN ACTION TARGETS PASS`',1)
marker='## Branch Boundary'; assert marker in s
head,tail=s.split(marker,1); head+=current_section
# only current boundary text after marker
tail=tail.replace('L2 runtime Product Source = 192a6684975138871a2f2539ff9c511f34d3fe59',f'L2 runtime Product Source = {SOURCE}',1)
tail=tail.replace('L2 runtime Product Tree = 94e620562dd71c7134bfa6921bae4b200490eb5a',f'L2 runtime Product Tree = {TREE}',1)
tail=tail.replace('Continue evidence-driven L2 product optimization from the PR #149 mobile touch-target PASS runtime.','Continue evidence-driven L2 product optimization from the PR #151 shared mobile admin action-target PASS runtime.',1)
p.write_text(head+marker+tail)

# CURRENT_STATE.md
p=Path('docs/handoff/CURRENT_STATE.md'); s=p.read_text()
assert '## L2 DEVELOP · SHARED MOBILE ADMIN ACTION TARGETS' not in s
s=s.replace('Current L2 runtime Product Source: 192a6684975138871a2f2539ff9c511f34d3fe59',f'Current L2 runtime Product Source: {SOURCE}',1)
s=s.replace('Current L2 runtime Product Tree: 94e620562dd71c7134bfa6921bae4b200490eb5a',f'Current L2 runtime Product Tree: {TREE}',1)
s=s.replace('L2 Product State: #142-#149 MERGED TO DEVELOP / MOBILE TOUCH TARGET MACHINE PASS / NOT RELEASED','L2 Product State: #142-#151 MERGED TO DEVELOP / SHARED MOBILE ADMIN ACTION TARGETS PASS / NOT RELEASED',1)
section=f'''## L2 DEVELOP · SHARED MOBILE ADMIN ACTION TARGETS\n\n```text\nPR: #151 / MERGED\nExact Product Candidate: {CANDIDATE}\nCurrent runtime Product Source: {SOURCE}\nCurrent runtime Product Tree: {TREE}\nScope: src/assets/admin-consolidation.css only / +5 -0\nMerged blob: {BLOB}\nDiagnostic: {DIAG} / shared mobile Shell 36x36 and page actions 34-35px / DEFECT REPRODUCED\nDiagnostic Artifact: {DIAG_ART}\nDiagnostic Digest: sha256:{DIAG_DIGEST}\nAuthoritative Gate: {GATE} PASS\nEvidence Artifact: {ART}\nDigest: sha256:{DIGEST}\n```\n\nAt `<=768px`, the shared server admin Shell menu/return controls are at least 40x40 and visible page `.btn` / expandable `summary` actions are at least 40px high. All five permanent backend modules passed Chromium 390 with document overflow 0; Chromium 1440 remained outside the mobile rule. Existing links-admin selection/filter/mode/lifecycle/state-aware batch contracts passed unchanged. SQLite integrity is `ok`, FK is `0`. Inputs/selects/file controls are intentionally unchanged because the diagnostic did not prove a usability defect there. No Schema/version/main/Release/Tag/core-updates/Runner main/Owner Production write.\n\n'''
marker='## CURRENT BOUNDARY'; assert marker in s
head,tail=s.split(marker,1); head+=section
tail=tail.replace('L2 runtime Product Source = 192a6684975138871a2f2539ff9c511f34d3fe59',f'L2 runtime Product Source = {SOURCE}',1)
tail=tail.replace('L2 runtime Product Tree = 94e620562dd71c7134bfa6921bae4b200490eb5a',f'L2 runtime Product Tree = {TREE}',1)
tail=tail.replace('Continue evidence-driven L2 product optimization from the PR #149 mobile touch-target PASS runtime.','Continue evidence-driven L2 product optimization from the PR #151 shared mobile admin action-target PASS runtime.',1)
p.write_text(head+marker+tail)

# Evidence
p=Path('docs/evidence/P01_L2_PRODUCT_WAVE_DEVELOP_MERGE_20260831.md'); s=p.read_text()
assert '## PR #151 · Shared Mobile Admin Action Targets' not in s
s=s.replace('Current Product Source on develop: 192a6684975138871a2f2539ff9c511f34d3fe59',f'Current Product Source on develop: {SOURCE}',1)
s=s.replace('Current Product Tree: 94e620562dd71c7134bfa6921bae4b200490eb5a',f'Current Product Tree: {TREE}',1)
s=s.replace('Latest Product PR: #149 / MERGED','Latest Product PR: #151 / MERGED',1)
section=f'''## PR #151 · Shared Mobile Admin Action Targets\n\nA Fresh Runtime cross-page diagnostic tested the five permanent backend modules at 390px before changing Product bytes. It reproduced a shared operability inconsistency: the Shell menu/return controls were 36x36px and primary `.btn` actions were commonly 34-35px, despite the links-admin page-selection/touch-target work already reaching 40px. No page had horizontal overflow and SQLite remained healthy.\n\n```text\nDiagnostic Run: {DIAG} / DEFECT REPRODUCED\nDiagnostic Artifact: {DIAG_ART}\nDiagnostic Digest: sha256:{DIAG_DIGEST}\nExact Product Candidate: {CANDIDATE}\nScope: src/assets/admin-consolidation.css only / +5 -0\nCSS fence: server AdminShell + max-width:768px action controls only\nAuthoritative Gate: {GATE} / PASS\nEvidence Artifact: {ART}\nDigest: sha256:{DIGEST}\nPR: #151 / MERGED TO DEVELOP ONLY\nDevelop Product Merge: {SOURCE}\nCurrent Product Tree: {TREE}\nMerged CSS Blob: {BLOB}\n```\n\nFinal Chromium 390 verified `links-admin.php`, `browser-helper.php`, `data-safety.php`, `settings.php` and `update.php`: Shell menu/return are 40x40; visible `.btn` and expandable `summary` actions are at least 40px high; document horizontal overflow is 0 on all five pages. Links-admin page-select, filter-selection clearing, URL/category mode clearing, lifecycle hidden-state and state-aware batch actions all remain PASS. Chromium 1440 confirmed the mobile media rule is inactive and overflow remains 0. SQLite integrity=`ok`, FK=`0`. Form inputs/selects/file controls were deliberately excluded because the diagnostic did not establish an actual usability defect. No JS/PHP/API/Schema/Migration/version/main/Release/Tag/core-updates/Owner Production/Runner main mutation occurred.\n\n'''
marker='## Post-Merge Blob Readback'; assert marker in s
head,tail=s.split(marker,1); head+=section
tail=tail.replace('src/assets/admin-consolidation.css 56fbf3bf8447bc571750daf32ad30af6b37bd8a6',f'src/assets/admin-consolidation.css {BLOB}',1)
tail=tail.replace('The current develop-only Product runtime is source `192a6684975138871a2f2539ff9c511f34d3fe59` / tree `94e620562dd71c7134bfa6921bae4b200490eb5a` after PR #149 Machine PASS. It remains unreleased and is not present in Owner Production.',f'The current develop-only Product runtime is source `{SOURCE}` / tree `{TREE}` after PR #151 Machine PASS. It remains unreleased and is not present in Owner Production.',1)
p.write_text(head+marker+tail)

# VF_PROJECT.json
p=Path('VF_PROJECT.json'); d=json.loads(p.read_text())
d['status']='V2.35.3 PRODUCTION CLOSURE PASS / L2 SHARED MOBILE ADMIN ACTION TARGETS PASS'
d['current_change']={
 'change_id':'P01-L2-SHARED-MOBILE-ADMIN-ACTION-TARGETS-20260831',
 'base':'PR #149 MOBILE LINKS TOUCH TARGET PASS / AUTHORITY DEVELOP ee5954a652f7f0b874ff3edcebdadb6691cf0546',
 'result':'SHARED MOBILE ADMIN ACTION TARGETS PASS / MERGED TO DEVELOP / NOT RELEASED',
 'schema_change':False,'migration':None,'latest_merge_pr':151,
 'runtime_product_source':SOURCE,'runtime_product_tree':TREE,'latest_product_blob':BLOB,
 'machine_gate':GATE,'evidence_artifact':ART,'evidence_artifact_sha256':DIGEST,
 'owner_production_write':False,'runner_main_write':False
}
d['develop_state']='L2 #142-#151 MERGED / SHARED MOBILE ADMIN ACTION TARGETS PASS / AHEAD OF MAIN / NOT RELEASED'
d['current_authority']=f'Owner Production V2.35.3 Closure PASS / main Production Truth / develop runtime source {SOURCE} tree {TREE} / PR #151 Gate {GATE} PASS'
d['next_action']='Continue evidence-driven L2 product optimization from the PR #151 shared mobile admin action-target PASS runtime. Do not treat 36-37px form controls as a defect without focused usability evidence. Do not promote to main, publish a Release, mutate core-updates or write Owner Production without a separate formal Release Gate.'
d['l2_mobile_admin_action_targets']={
 'pr':151,'diagnostic_run':DIAG,'diagnostic_artifact':DIAG_ART,'diagnostic_artifact_sha256':DIAG_DIGEST,
 'product_candidate':CANDIDATE,'product_source':SOURCE,'product_tree':TREE,'scope':['src/assets/admin-consolidation.css'],'product_blob':BLOB,
 'machine_gate':GATE,'evidence_artifact':ART,'evidence_artifact_sha256':DIGEST,
 'mobile_390_permanent_modules':['links-admin.php','browser-helper.php','data-safety.php','settings.php','update.php'],
 'mobile_shell_actions_min_px':40,'page_button_actions_min_px':40,'horizontal_overflow':'0 / PASS','desktop_1440_mobile_rule':'INACTIVE / PASS',
 'links_admin_regressions':'PAGE SELECT / FILTER / MODE / LIFECYCLE HIDDEN / STATE-AWARE BATCH / PASS',
 'form_controls':'INTENTIONALLY UNCHANGED / NO DEFECT EVIDENCE','sqlite_integrity':'ok','foreign_key_errors':0,
 'schema_change':False,'version_change':False,'release':False,'main_write':False,'core_updates_write':False,'owner_production_write':False,'runner_main_write':False,
 'state':'MERGED TO DEVELOP / MACHINE PASS / NOT RELEASED'
}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

print('P01_AUTHORITY_SYNC_MOBILE_ADMIN_ACTIONS=PASS')
