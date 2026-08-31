from pathlib import Path
import json, sys
root = Path(sys.argv[1])
run = 33402358873
artifact = 9761745494
digest = 'sha256:fe008d42501ee011dfa9bb8df53cf9f6c1969c1ea3674c6c0fdcd9cd9fc73620'
product = '7a9e9fd3e2505e85d7aa5781da8b23db7d961a9f'
tree = 'd322efb883301c4f79570372908a0319b21c45a3'
base = '3eddb4ceb20743528a386b98dfee72c217bc284d'

vf = root / 'VF_PROJECT.json'
data = json.loads(vf.read_text(encoding='utf-8'))
data['status'] = 'V2.35.3 PRODUCTION CLOSURE PASS / L2 MOBILE FORM USABILITY NO PRODUCT CHANGE'
data['develop_state'] = 'L2 #142-#152 MERGED / MOBILE FORM USABILITY NO PRODUCT CHANGE / AHEAD OF MAIN / NOT RELEASED'
data['current_authority'] = f'Owner Production V2.35.3 Closure PASS / main Production Truth / develop runtime source {product} tree {tree} / Browser Helper token hit-test {run} PASS_NO_PRODUCT_CHANGE'
data['next_action'] = 'Continue evidence-driven L2 product optimization from the current Product runtime. Mobile form heights around 36-37px and Browser Helper token-copy are closed as NO PRODUCT CHANGE unless new real-device or Chromium evidence shows a task failure. Do not promote to main, publish a Release, mutate core-updates or write Owner Production without a separate formal Release Gate.'
data['l2_mobile_form_usability'] = {
    'authority_base': base,
    'product_source': product,
    'product_tree': tree,
    'initial_diagnostic_runs': [33401007608, 33401391734],
    'initial_diagnostic_classification': 'HARNESS ONLY / HEADLESS CLIPBOARD CLICK COMPLETION / NOT PRODUCT FAIL',
    'authoritative_hit_test_run': run,
    'artifact': artifact,
    'artifact_sha256': digest.removeprefix('sha256:'),
    'viewport': '390x844',
    'copy_button_geometry': '318x48',
    'center_hit_test': 'BUTTON SELF / PASS',
    'trial_click': 'PASS',
    'pointer_click': 'PASS',
    'clipboard_state': 'COPIED / PASS',
    'horizontal_overflow': 0,
    'sqlite_integrity': 'ok',
    'foreign_key_errors': 0,
    'verdict': 'PASS / NO PRODUCT CHANGE',
    'product_change': False,
    'main_write': False,
    'production_write': False,
    'runner_main_write': False
}
vf.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

block = f'''\n\n## L2 Mobile Form Usability / Browser Helper Token Copy Closure · 2026-08-31\n\n- Authority baseline before this evidence-only update: `{base}`.\n- Product runtime remains `{product}` / tree `{tree}`; **NO Product/source change**.\n- Initial runs `33401007608` and `33401391734` are classified **HARNESS ONLY / NOT PRODUCT FAIL**. The blocking behavior came from headless clipboard/click completion, not from a proven UI obstruction.\n- Authoritative focused hit-test: Run `{run}` = **PASS / NO PRODUCT CHANGE**. Artifact `{artifact}`; digest `{digest}`.\n- Chromium 390x844 measured the token-copy action at **318x48px**; center `elementFromPoint()` hit the button itself; `pointer-events:auto`; trial click PASS; deterministic clipboard patch + real pointer click PASS; copied state became `已复制 ✓`; document horizontal overflow = `0`.\n- SQLite integrity = `ok`; foreign-key errors = `0`.\n- Decision: do **not** enlarge 36-37px form controls or modify Browser Helper token-copy code based on the earlier harness failures. Re-open only with new real-device/Chromium evidence of an actual task failure.\n- Boundaries unchanged: `main` / Release / Tag / core-updates / Owner Production / `core-free-runner-public/main` were not written.\n'''
for rel in [
    'docs/authority/CURRENT.md',
    'docs/handoff/CURRENT_STATE.md',
    'docs/evidence/P01_L2_PRODUCT_WAVE_DEVELOP_MERGE_20260831.md',
]:
    p = root / rel
    text = p.read_text(encoding='utf-8')
    marker = '## L2 Mobile Form Usability / Browser Helper Token Copy Closure · 2026-08-31'
    if marker not in text:
        p.write_text(text.rstrip() + block.rstrip() + '\n', encoding='utf-8')
