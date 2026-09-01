#!/usr/bin/env python3
import json
from pathlib import Path

BASE = 'f19f2b9c0819acf2fa19adb5d2b403a68b5d9352'
RUNTIME_BASE = '5f1deb37a7f8b3828bd9617b6a0a14f045a3e096'
RUNTIME_TREE = 'a467ab0a90656312bd297dfd5ecb51da396990b6'

Path('VERSION').write_text('1.2.3\n')

pkg = Path('package.json')
pkg_data = json.loads(pkg.read_text())
assert pkg_data['version'] == '1.2.2'
pkg_data['version'] = '1.2.3'
pkg.write_text(json.dumps(pkg_data, ensure_ascii=False, indent=2) + '\n')

app = Path('src/client/ProductApp.tsx')
app_text = app.read_text()
old_label = 'P05 · Product Optimization · v1.2.2'
assert app_text.count(old_label) == 1
app.write_text(app_text.replace(old_label, 'P05 · Product Optimization · v1.2.3', 1))

vf = Path('VF_PROJECT.json')
data = json.loads(vf.read_text())
assert data['version'] == '1.2.2'
assert data['production_version'] == '1.2.2'
assert data['formal_release'] == 'v1.2.2'
data['status'] = 'V1.2.3_RELEASE_CANDIDATE / FINAL_MACHINE_GATE_PENDING / RELEASE_AND_PRODUCTION_CLOSURE_AUTHORIZED / PRODUCTION_V1.2.2_OWNER_OBSERVED'
data['version'] = '1.2.3'
data['production_version'] = '1.2.2'
data['target_version'] = '1.2.3'
data['working_version'] = '1.2.3'
data['version_change'] = True
data['working_branch'] = 'release/p05-v1.2.3-readiness-20260902'
data['candidate_authorization'] = 'RELEASE_READINESS / OWNER_AUTHORIZED_V1.2.3'
data['release_authorization'] = 'OWNER_AUTHORIZED_V1.2.3 / EXECUTION_PENDING'
data['production_deployment_authorization'] = 'OWNER_AUTHORIZED_V1.2.3_FULL_CLOSURE / EXECUTION_PENDING'
data['next_action'] = 'V1.2.3 FINAL EXACT SOURCE GATE → MAIN PROMOTION → FORMAL FULL/TAG/RELEASE → V1.2.2→V1.2.3 ATOMIC → CORE-UPDATES → PRODUCTION CLOSURE'
data['deployment_readiness'] = 'V1.2.3_CANDIDATE_FINAL_GATE_PENDING / PRODUCTION_BASELINE_V1.2.2_OWNER_OBSERVED'
data['authority']['release_candidate'] = 'docs/authority/RELEASE_V1.2.3_CANDIDATE.md'
post = data['post_v1_2_2_update_service']
assert post['recommended_patch_release'] == 'v1.2.3'
post['release_authorization'] = 'OWNER_AUTHORIZED_V1.2.3 / EXECUTION_PENDING'
post['production_adoption'] = 'V1.2.3_RELEASE_AND_PRODUCTION_CLOSURE_AUTHORIZED / EXECUTION_PENDING'
post['machine_production_readback'] = 'NOT_CLAIMED'
data['release_closure_authorization_20260902'] = {
    'version': 'v1.2.3',
    'state': 'OWNER_AUTHORIZED',
    'scope': 'VERSION_LOCK → FINAL_EXACT_SOURCE → FORMAL_FULL_TAG_RELEASE → DIRECT_V1.2.2_TO_V1.2.3_ATOMIC → CORE_UPDATES → PRODUCTION_CLOSURE',
    'production_execution': 'AUTHORIZED_BUT_OWNER_VPS_ACTION_MAY_BE_REQUIRED_IF_NO_MACHINE_CHANNEL_EXISTS',
    'frozen_pre_release_main': BASE,
    'runtime_code_baseline': RUNTIME_BASE,
    'runtime_code_tree': RUNTIME_TREE,
}
vf.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

candidate = Path('docs/authority/RELEASE_V1.2.3_CANDIDATE.md')
candidate.write_text(f'''# P05 · VF SEO v1.2.3 Release Candidate

Status: `RELEASE_AND_PRODUCTION_CLOSURE_AUTHORIZED / FINAL_EXACT_SOURCE_GATE_PENDING`

## Release basis

- Frozen pre-release `main`: `{BASE}`
- Post-release runtime code baseline after PR #139: `{RUNTIME_BASE}`
- Runtime baseline tree: `{RUNTIME_TREE}`
- Current formal Product Release: `v1.2.2`
- Owner-observed Production baseline: `v1.2.2`
- Target candidate: `v1.2.3`
- Schema: `VF-SEO-SCHEMA@1 / 1` unchanged
- Default database: SQLite unchanged

## Patch scope already merged and machine-verified

PR #138 keeps the missing-update-credential state truthful and keeps browser GitHub Secret / administrator-password collection forbidden. Exact Source R4: Run `33540256003` / Job `99964446091` = PASS.

PR #139 adds CLI-only `php/bin/init-update-service.php`: server process `VF_PRIVATE_READ_TOKEN` → verified private `core-updates` + P05 Release identity → Runtime Pointer-bound private `runtime.env`; the Secret is never returned to Product browser. Native CI: Run `33541470290` / Job `99968501815` = PASS. Exact Source R2: Run `33541894604` / Job `99969918142` = PASS.

PR #140 and PR #141 are Current Truth documentation only and add no Product runtime behavior.

## Version authority

- `VERSION=1.2.3`.
- `package.json` mirrors `VERSION`.
- `package-lock.json` remains dependency-graph authority and is intentionally unchanged.
- Product visible release label is `v1.2.3`.
- Formal Release and Production remain `v1.2.2` until publication/deployment actually completes.

## Security / update authority

- Browser GitHub Secret collection remains `FORBIDDEN_LOCKED`.
- Update read authority remains global server-side `VF_PRIVATE_READ_TOKEN`.
- `llhzx2018/core-updates` remains private Online Update Manifest Authority.
- No third/project-specific GitHub Token is introduced.

## Owner authorization

On 2026-09-02 the Owner explicitly authorized the complete closure chain:

`Version Lock → Final Exact Source Gate → Formal FULL / Tag / Release → v1.2.2→v1.2.3 Atomic → core-updates → Production Closure`.

Production PASS still requires real runtime evidence; no Machine Production Readback may be fabricated. If no proven machine→VPS channel exists, closure may stop only at the irreducible Owner VPS action.
''')
