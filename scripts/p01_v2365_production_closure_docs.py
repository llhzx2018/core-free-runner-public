from __future__ import annotations

import json
from pathlib import Path

root = Path('product')

EVIDENCE_PATH = root / 'docs/evidence/P01_V2.36.5_OWNER_PRODUCTION_CLOSURE_20260902.md'
EVIDENCE_PATH.write_text('''# P01 · V2.36.5 Owner Production Closure · 2026-09-02

## Verdict

`PASS / OWNER PRODUCTION V2.36.5 / CURRENT = LATEST / TERMINAL UI READBACK PASS`

Owner 已通过 VF Start 正式在线升级完成 `V2.36.4 → V2.36.5`。Assistant 没有直接写 Owner Production。

## Final Owner Evidence

```text
Current Version: V2.36.5
Latest Version: V2.36.5
Update State: 已是最新版本。
Footer: VF Start · V2.36.5
Last Check: 2026-09-02 03:56:37
Update History: 2.36.4 -> 2.36.5 / success
Update Completed At: 2026-09-02 03:56:41
Screenshot Size: 1319 x 641
Screenshot SHA256: b9fbd5cc5002a3b38f9f341679ac79adf9d9ad8e4c00ecef6974ac50733527dc
Assistant Production Write: NO
```

## Published Release Binding

```text
Version: 2.36.5
Tag: v2.36.5
GitHub Release ID: 380771266
Formal Source: ef86eba16aec71c1d0dabc16ad23089a78ee5057
Formal Tree: 926504354eaf4354e852e78b19c0fde69513a133
Runtime Tree: a7f472ec1f449ada1152d271f2723c52e7b58144
Schema: 2026082901
Migration: NONE
FULL Bytes: 587547
FULL SHA256: 6718216489852bd4f326f05371b590d8089a63e5ee76f56fc992afa58f8c33cf
UPDATE Asset: VF_Start_V2.36.5_UPDATE.zip
UPDATE Bytes: 1238610
UPDATE SHA256: bb28284f15e8e94673f604c43f1b89692134dc92fdce8343cefc90431e52f6b6
repair Bytes: 3595293
repair SHA256: b3a3e1a4cc9c6133ea0579430e2bbd900e4bd3a4126ad66abf0d89fecc34a2ee
```

Release chain: Candidate R2 `33547215072` PASS; Formal Bind `33547455556` PASS; Formal Artifact `33547781563` PASS; Strict Fresh Formal R3 `33548565663` PASS; Release Publish `33550328295` PASS. Candidate Readiness R1 `33546946198`, Strict Fresh R1 `33548191297`, Strict Fresh R2 `33548388404` remain retained as harness-only failure evidence.

## core-updates Closure

`core-updates` PR `#37` promoted the exact single-hop `V2.36.4 → V2.36.5` manifest after Manifest Gate R3 `33550645516` PASS.

```text
core-updates main: 61a3e93868fa8c497f4934744498e73ec0790a5f
P01 manifest blob: a28bfaf9ffb5e2e7a4867555ae0812a3a09dfaee
Online contract: 2.36.4 -> 2.36.5
```

Manifest Gate R1 `33550481109` and R2 `33550561059` remain retained as harness-only evidence; the candidate manifest itself did not fail its contract.

## Production Boundary

```text
Owner Production Runtime: V2.36.5 / PASS
Owner Production Schema: 2026082901
Published Latest: V2.36.5
Current = Latest: YES
Terminal UI Readback: PASS
Production Closure: PASS
Assistant Production Write: NO
Product runtime mutation in closure docs step: NO
Tag/Release mutation in closure docs step: NO
core-updates mutation in closure docs step: NO
```

V2.36.5 Production Closure is complete. Runtime returns to L2 Product Optimization. Continue from Fresh Owner feedback and develop working truth; do not re-run the already-passed Formal Artifact / Strict Fresh gates.
''', encoding='utf-8')

section = '''<!-- P01_V2365_OWNER_PRODUCTION_CLOSURE -->
## V2.36.5 Owner Production Closure · 2026-09-02

- Final Owner Readback：Current `V2.36.5` = Latest `V2.36.5`，状态 `已是最新版本。`，Footer `V2.36.5`，历史 `2.36.4 → 2.36.5 / success`，Last Check `2026-09-02 03:56:37`。
- Final Screenshot：`1319×641` / SHA-256 `b9fbd5cc5002a3b38f9f341679ac79adf9d9ad8e4c00ecef6974ac50733527dc`。
- Formal Source `ef86eba16aec71c1d0dabc16ad23089a78ee5057` / Formal Tree `926504354eaf4354e852e78b19c0fde69513a133` / Runtime Tree `a7f472ec1f449ada1152d271f2723c52e7b58144` / Release ID `380771266` / Schema `2026082901`。
- Release Publish `33550328295` PASS；core-updates Manifest Gate R3 `33550645516` PASS；live P01 manifest 为严格 `V2.36.4 → V2.36.5`，blob `a28bfaf9ffb5e2e7a4867555ae0812a3a09dfaee`。
- Verdict：**OWNER PRODUCTION V2.36.5 / PRODUCTION CLOSURE PASS**；Assistant direct Production write `NO`。
- Runtime：正式切回 **L2 Product Optimization**；继续从 Fresh Owner feedback + develop working truth 推进，不重复 Formal Artifact / Strict Fresh。

> 以下旧段落保留历史证据；如与本段冲突，以本段为 Current Production Authority。

'''

for rel in ('docs/authority/CURRENT.md', 'docs/handoff/CURRENT_STATE.md'):
    p = root / rel
    text = p.read_text(encoding='utf-8')
    if '<!-- P01_V2365_OWNER_PRODUCTION_CLOSURE -->' not in text:
        first = text.find('\n') + 1
        text = text[:first] + '\n' + section + text[first:].lstrip('\n')
    p.write_text(text, encoding='utf-8')

p = root / 'VF_PROJECT.json'
data = json.loads(p.read_text(encoding='utf-8'))
data['status'] = 'V2.36.5 OWNER PRODUCTION / PUBLISHED / PRODUCTION CLOSURE PASS / L2 PRODUCT OPTIMIZATION'
data['production_version'] = '2.36.5'
data['working_version'] = '2.36.5'
data['target_release_version'] = '2.36.5'
data['current_phase'] = 'V2.36.5 OWNER PRODUCTION CLOSURE PASS / L2 PRODUCT OPTIMIZATION'
release = {
    'version': '2.36.5', 'tag': 'v2.36.5', 'release_id': 380771266,
    'release_source': 'ef86eba16aec71c1d0dabc16ad23089a78ee5057',
    'release_tree': '926504354eaf4354e852e78b19c0fde69513a133',
    'runtime_tree': 'a7f472ec1f449ada1152d271f2723c52e7b58144',
    'schema_version': '2026082901',
    'live_core_updates_commit': '61a3e93868fa8c497f4934744498e73ec0790a5f',
    'live_online_next_hop': '2.36.5 / FROM 2.36.4',
    'online_asset': 'VF_Start_V2.36.5_UPDATE.zip', 'online_asset_bytes': 1238610,
    'online_asset_sha256': 'bb28284f15e8e94673f604c43f1b89692134dc92fdce8343cefc90431e52f6b6',
    'full_asset': 'VF-Start-V2.36.5-FULL.zip', 'full_asset_bytes': 587547,
    'full_asset_sha256': '6718216489852bd4f326f05371b590d8089a63e5ee76f56fc992afa58f8c33cf',
    'repair_asset': 'repair-v2.36.5.php', 'repair_asset_bytes': 3595293,
    'repair_asset_sha256': 'b3a3e1a4cc9c6133ea0579430e2bbd900e4bd3a4126ad66abf0d89fecc34a2ee',
    'release_state': 'PUBLISHED / OWNER INSTALLED / PRODUCTION CLOSURE PASS',
    'assistant_production_write': False,
    'candidate_readiness_r2': 33547215072, 'formal_bind_gate': 33547455556,
    'formal_artifact_gate': 33547781563, 'strict_fresh_formal_r3': 33548565663,
    'release_publish_gate': 33550328295, 'core_updates_manifest_gate_r3': 33550645516,
    'owner_production_runtime': '2.36.5', 'owner_production_schema': '2026082901',
    'production_closure': 'PASS', 'owner_production_upgrade': '2.36.4 -> 2.36.5 / SUCCESS',
    'owner_version_readback': 'Current V2.36.5 / Latest V2.36.5 / history 2.36.4 -> 2.36.5 success',
    'owner_browser_footer_readback': 'V2.36.5 / PASS', 'owner_terminal_ui_last_check': '2026-09-02 03:56:37',
    'owner_terminal_ui_screenshot_sha256': 'b9fbd5cc5002a3b38f9f341679ac79adf9d9ad8e4c00ecef6974ac50733527dc',
    'owner_terminal_ui_screenshot_size': '1319x641', 'owner_online_state': 'CURRENT=LATEST / NO UPDATE AVAILABLE',
    'p01_manifest_promotion_commit': '61a3e93868fa8c497f4934744498e73ec0790a5f',
    'core_updates_repository_head_at_closure': '61a3e93868fa8c497f4934744498e73ec0790a5f',
    'p01_manifest_blob_at_closure': 'a28bfaf9ffb5e2e7a4867555ae0812a3a09dfaee'
}
data['production_release'] = release
data['published_release'] = dict(release)
auth = data.setdefault('authority', {})
auth['current_production_evidence'] = 'docs/evidence/P01_V2.36.5_OWNER_PRODUCTION_CLOSURE_20260902.md'
auth['current_formal_release_evidence'] = 'docs/evidence/P01_V2.36.5_OWNER_PRODUCTION_CLOSURE_20260902.md'
data['candidate_version'] = '2.36.5'
data['candidate_schema_version'] = '2026082901'
data['candidate_state'] = 'CLOSED / PUBLISHED / OWNER PRODUCTION'
data['formal_release_state'] = 'V2.36.5 PUBLISHED / OWNER PRODUCTION V2.36.5 / PRODUCTION CLOSURE PASS'
data['develop_state'] = 'L2 WORKING TRUTH / PRESERVE DEVELOP AUTHORITY / NEXT PRODUCT FEEDBACK'
data['current_authority'] = 'Owner Production V2.36.5 / Published Latest V2.36.5 / Production Closure PASS / L2 Product Optimization'
data['next_action'] = 'Continue L2 Product Optimization from Fresh Owner feedback. Do not repeat V2.36.5 release gates or rebuild frozen artifacts.'
data['owner_production_activation_evidence'] = {
    'version': '2.36.5', 'schema': '2026082901',
    'final_screenshot_sha256': 'b9fbd5cc5002a3b38f9f341679ac79adf9d9ad8e4c00ecef6974ac50733527dc',
    'screenshot_size': '1319x641', 'current': '2.36.5', 'latest': '2.36.5', 'footer': '2.36.5',
    'state': '已是最新版本。', 'history': '2.36.4 -> 2.36.5 / success', 'last_check': '2026-09-02 03:56:37',
    'terminal_ui_visual_closure': 'PASS', 'assistant_production_write': False
}
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
