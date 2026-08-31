from pathlib import Path
import json, sys
root = Path(sys.argv[1])
base = 'c23fd9fe207b654c6bd29d859113caa56c5e7701'
product = '7a9e9fd3e2505e85d7aa5781da8b23db7d961a9f'
tree = 'd322efb883301c4f79570372908a0319b21c45a3'
browser_run = 33403054640
browser_artifact = 9762024302
browser_digest = 'sha256:d00fa360aea98fe2894932ad5170ad9f04574d9d8f0e0c49c6f9f71d6221032c'
api_run = 33404335855
api_artifact = 9762513419
api_digest = 'sha256:09c9e12482749ddd5c36c8d9f23200c9f4fd817e35975ed889b2f142eaf4413a'

vf = root / 'VF_PROJECT.json'
data = json.loads(vf.read_text(encoding='utf-8'))
data['status'] = 'V2.35.3 PRODUCTION CLOSURE PASS / L2 DATA SAFETY MOBILE DYNAMIC ACTIONS NO PRODUCT CHANGE'
data['develop_state'] = 'L2 THROUGH PR #153 MERGED / DATA SAFETY DYNAMIC ACTIONS NO PRODUCT CHANGE / AHEAD OF MAIN / NOT RELEASED'
data['current_authority'] = f'Owner Production V2.35.3 Closure PASS / main Production Truth / develop runtime source {product} tree {tree} / Data Safety dynamic API contract {api_run} PASS_NO_PRODUCT_CHANGE'
data['next_action'] = 'Continue evidence-driven L2 product optimization from the current Product runtime. Data Safety dynamic backup action layout and backup lifecycle are closed as NO PRODUCT CHANGE unless new real-device or Chromium evidence shows an actual task failure. Do not promote to main, publish a Release, mutate core-updates or write Owner Production without a separate formal Release Gate.'
data['l2_data_safety_mobile_dynamic_actions'] = {
    'authority_base': base,
    'product_source': product,
    'product_tree': tree,
    'browser_diagnostic_run': browser_run,
    'browser_artifact': browser_artifact,
    'browser_artifact_sha256': browser_digest.removeprefix('sha256:'),
    'browser_classification': 'HARNESS-ONLY FAILURE AFTER PRODUCT CHECKS PASSED / ReferenceError round is not defined',
    'browser_checks_before_harness_failure': [
        'Fresh Runtime', '390px dynamic backup item created', 'five visible backup actions >=40px',
        'actions not clipped', 'horizontal overflow=0', 'verify', 'protect', 'unprotect', 'restore preview reached'
    ],
    'authoritative_api_run': api_run,
    'api_artifact': api_artifact,
    'api_artifact_sha256': api_digest.removeprefix('sha256:'),
    'api_checks': ['create', 'verify', 'protect', 'unprotect', 'preview_restore', 'download', 'delete'],
    'sqlite_integrity': 'ok',
    'foreign_key_errors': 0,
    'verdict': 'PASS / NO PRODUCT CHANGE',
    'product_change': False,
    'main_write': False,
    'production_write': False,
    'runner_main_write': False
}
vf.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

block = f'''\n\n## L2 Data Safety Mobile Dynamic Actions Closure · 2026-08-31\n\n- Authority baseline before this evidence-only update: `{base}`.\n- Product runtime remains `{product}` / tree `{tree}`; **NO Product/source change**.\n- Chromium dynamic-list diagnostic Run `{browser_run}` reached and passed Fresh Runtime, creation of a real SQLite backup row, five visible backup action touch targets >=40px, no clipping, document horizontal overflow `0`, verify, protect, unprotect, and restore-preview request. It then failed inside the test harness because `round` was referenced inside the browser evaluation context; Artifact `{browser_artifact}`, digest `{browser_digest}`. This is **HARNESS ONLY / NOT PRODUCT FAIL**.\n- Authoritative behavior contract Run `{api_run}` = **PASS / NO PRODUCT CHANGE**; Artifact `{api_artifact}`, digest `{api_digest}`. It passed create -> verify -> protect -> unprotect -> restore preview -> download -> delete on a Fresh Runtime.\n- SQLite integrity = `ok`; foreign-key errors = `0`.\n- Decision: dynamic backup actions and lifecycle are closed as **NO PRODUCT CHANGE**. Re-open only with new real-device/Chromium evidence of an actual task failure.\n- A supplemental Chromium R3 may exist on a temporary Runner branch, but it is not used as authority for this decision.\n- Boundaries unchanged: `main` / Release / Tag / core-updates / Owner Production / `core-free-runner-public/main` were not written.\n'''
for rel in [
    'docs/authority/CURRENT.md',
    'docs/handoff/CURRENT_STATE.md',
    'docs/evidence/P01_L2_PRODUCT_WAVE_DEVELOP_MERGE_20260831.md',
]:
    p = root / rel
    text = p.read_text(encoding='utf-8')
    marker = '## L2 Data Safety Mobile Dynamic Actions Closure · 2026-08-31'
    if marker not in text:
        p.write_text(text.rstrip() + block.rstrip() + '\n', encoding='utf-8')
