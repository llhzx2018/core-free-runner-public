from __future__ import annotations
import json
from pathlib import Path

ROOT = Path('p05')
V = '1.2.3'
RELEASE_SOURCE = '66a56dafdfba2ca7243d1984791ecbe0fd7382ae'
RELEASE_TREE = 'b858117477fd1cb41fb53a62da6bdebfa26ad21f'
CANDIDATE_SOURCE = '45f81677c206476013ed1d543ab661356107800c'
RELEASE_ID = 380755611
FULL_ASSET_ID = 540005215
FULL_BYTES = 516457
FULL_SHA = '66621da7ed5d426cc7c1367a37ac5bbf463617daa5e71745a462f2c3ced44112'
RECEIPT_ASSET_ID = 540005216
UPDATE_ASSET_ID = 540017020
UPDATE_BYTES = 1173998
UPDATE_SHA = '0de26614f5269ba5d1f6ace343b6853a82a4fb3e3bcbe5be85e3ad683f48588d'
REPAIR_ASSET_ID = 540017025
REPAIR_BYTES = 3671457
REPAIR_SHA = '378c1ed64e86eb2ac79a8e40ca5feaa3bd7f3cd2ff41b05bf1daedead0e5ff63'
FINAL_RUN, FINAL_JOB = 33547042654, 99987005980
PUB_RUN, PUB_JOB = 33547503575, 99988548027
ATOMIC_RUN, ATOMIC_JOB = 33548178743, 99990780962
SUPP_RUN, SUPP_JOB = 33548646163, 99992321450
MANIFEST_RUN, MANIFEST_JOB = 33548911485, 99993208224
P05_MANIFEST_COMMIT = '92d70b7352b22ce857422912219183efa4e1ea89'
P05_MANIFEST_MERGE = '71a9e1d2103db16d5bbf5c023396eaa35c7e9d2a'
BRIDGE_RUN, BRIDGE_JOB = 33561682259, 100035412442
BRIDGE_ARTIFACT_ID = 9821488541
BRIDGE_BYTES = 24999
BRIDGE_SHA = '95933b065dd2b021ed9e0b39e7e80a787a4bbf4f6c5a5911d4b0f1d94239a7d3'
RELAY_RUN, RELAY_JOB = 33562194685, 100037066201
READBACK_RUN, READBACK_JOB = 33562813196, 100039050036

assert (ROOT / 'VERSION').read_text().strip() == V

p = ROOT / 'VF_PROJECT.json'
data = json.loads(p.read_text())
data.update({
    'status': 'V1.2.3_RELEASED / PRODUCTION_OWNER_BACKEND_UPDATE / MACHINE_RUNTIME_READBACK_PASS / CLOSED',
    'version': V,
    'production_version': V,
    'target_version': V,
    'working_version': V,
    'version_change': False,
    'formal_release': 'v1.2.3',
    'formal_release_state': 'RELEASED_CURRENT_MACHINE_PASS_PRODUCTION_OWNER_OBSERVED_AND_MACHINE_READBACK',
    'formal_release_candidate_commit': CANDIDATE_SOURCE,
    'formal_release_candidate_tree': RELEASE_TREE,
    'formal_release_asset': 'VF_SEO_V1.2.3_FULL.zip',
    'formal_release_asset_files': 74,
    'formal_release_asset_bytes': FULL_BYTES,
    'formal_release_asset_sha256': FULL_SHA,
    'runtime_recovery_candidate': 'V1.2.3_ATOMIC_R2_PASS_CLOSED',
    'runtime_recovery_release': 'RELEASED_V1.2.3',
    'production_target': 'seo.kewaro.com',
    'production_source_upload': 'OWNER_AUTHENTICATED_SYSTEM_UPDATE_AFTER_GOV_DOC_LEGACY_BRIDGE',
    'production_runtime_acceptance': 'OWNER_OBSERVED_SCREENSHOT_V1.2.3_UP_TO_DATE / MACHINE_HEALTH_READBACK_PASS',
    'production_deployment': 'DEPLOYED_OWNER_BACKEND_UPDATE_MACHINE_READBACK_VERIFIED',
    'production_write': 0,
    'production_write_actor': 'OWNER_AUTHENTICATED_BACKEND_ATOMIC_UPDATE; AUTOMATION_PRODUCTION_WRITE=0',
    'production_main_promotion': 'NOT_APPLICABLE_RUNTIME_UPDATE_FROM_RELEASE_ASSETS',
    'production_branch': 'main',
    'working_branch': 'main',
    'owner_real_use_review': 'V1.2.3_OWNER_OBSERVED_UP_TO_DATE / SYSTEM_UPDATE_WORKING',
    'owner_real_use_pass': 'PASS / OWNER_SCREENSHOT_VERIFIED + MACHINE_RUNTIME_READBACK',
    'candidate_authorization': 'CONSUMED_V1.2.3',
    'release_authorization': 'OWNER_AUTHORIZED_V1.2.3 / EXECUTED_CLOSED',
    'production_deployment_authorization': 'OWNER_AUTHORIZED_V1.2.3_FULL_CLOSURE / EXECUTED_CLOSED',
    'product_failure': None,
    'project_block': None,
    'window_execution_block': None,
    'runtime_evidence': 'docs/authority/RELEASE_V1.2.3_PRODUCTION_CLOSURE.md',
    'runtime_handoff': 'docs/handoff/CURRENT_STATE.md',
    'next_action': 'RETURN_TO_L2_PRODUCT_OPTIMIZATION',
    'deployment_readiness': 'V1.2.3_PRODUCTION_CLOSED',
    'formal_release_id': RELEASE_ID,
    'formal_release_asset_id': FULL_ASSET_ID,
})
data['release_publication'] = {
    'tag': 'v1.2.3',
    'release_id': RELEASE_ID,
    'release_name': 'P05 · VF SEO v1.2.3 · Update Service Bootstrap Patch',
    'target_commit': RELEASE_SOURCE,
    'target_tree': RELEASE_TREE,
    'published_at': '2026-09-01T19:07:25Z',
    'full_asset': 'VF_SEO_V1.2.3_FULL.zip',
    'full_asset_id': FULL_ASSET_ID,
    'full_files': 74,
    'full_bytes': FULL_BYTES,
    'full_sha256': FULL_SHA,
    'receipt_asset': 'VF_SEO_V1.2.3_RELEASE_RECEIPT.txt',
    'receipt_asset_id': RECEIPT_ASSET_ID,
    'exact_candidate_source': CANDIDATE_SOURCE,
    'exact_candidate_run': FINAL_RUN,
    'exact_candidate_job': FINAL_JOB,
    'publication_run': PUB_RUN,
    'publication_job': PUB_JOB,
    'state': 'PASS_CLOSED',
    'real_endpoint': 'MACHINE_READBACK_V1.2.3',
    'production': 'DEPLOYED_OWNER_BACKEND_UPDATE_MACHINE_VERIFIED',
}
data['v1_2_3_production_closure'] = {
    'state': 'PASS_CLOSED',
    'release_source': RELEASE_SOURCE,
    'release_tree': RELEASE_TREE,
    'release_id': RELEASE_ID,
    'atomic_gate': {'run': ATOMIC_RUN, 'job': ATOMIC_JOB, 'state': 'PASS'},
    'atomic_supplemental_publication': {'run': SUPP_RUN, 'job': SUPP_JOB, 'state': 'PASS'},
    'update_asset': {'id': UPDATE_ASSET_ID, 'bytes': UPDATE_BYTES, 'sha256': UPDATE_SHA},
    'repair_asset': {'id': REPAIR_ASSET_ID, 'bytes': REPAIR_BYTES, 'sha256': REPAIR_SHA},
    'core_updates': {'manifest_commit': P05_MANIFEST_COMMIT, 'merge_commit': P05_MANIFEST_MERGE, 'gate_run': MANIFEST_RUN, 'gate_job': MANIFEST_JOB},
    'legacy_bridge': {'run': BRIDGE_RUN, 'job': BRIDGE_JOB, 'artifact_id': BRIDGE_ARTIFACT_ID, 'bytes': BRIDGE_BYTES, 'sha256': BRIDGE_SHA, 'formal_upgrade_executed': False},
    'sealed_relay': {'run': RELAY_RUN, 'job': RELAY_JOB, 'state': 'PASS', 'browser_secret': False, 'production_session_used': False},
    'production_readback': {'run': READBACK_RUN, 'job': READBACK_JOB, 'version': V, 'schema': 1, 'database': 'READY', 'process': 'READY', 'bridge_cleaned': True},
    'owner_observed': 'SCREENSHOT_SYSTEM_UPDATE_CURRENT_1.2.3_LATEST_1.2.3_UP_TO_DATE',
}
data.setdefault('authority', {})['release'] = 'docs/authority/RELEASE_V1.2.3_PRODUCTION_CLOSURE.md'
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

history_marker = '## 历史：V1.1.10 → V1.1.11 Canonical Atomic Bridge'
readme = (ROOT / 'README.md').read_text()
if history_marker not in readme:
    raise SystemExit('README_HISTORY_MARKER_MISSING')
history = readme[readme.index(history_marker):]
new_readme = f'''# P05 · VF SEO

VF SEO 是面向单管理员、私人使用的 SEO / AEO 运营中枢。

## Current Truth

```text
Project: P05 · VF SEO
Repository: llhzx2018/vf-seo
Current Formal Release: v1.2.3 · RELEASED
Release / Tag Source: {RELEASE_SOURCE}
Release Tree: {RELEASE_TREE}
Final Exact Source Gate: {FINAL_RUN} / {FINAL_JOB} · PASS
Formal Publication: {PUB_RUN} / {PUB_JOB} · PASS
FULL: Asset {FULL_ASSET_ID} · {FULL_BYTES} bytes
FULL SHA-256: {FULL_SHA}
Atomic: 1.2.2 → 1.2.3 · PASS
Atomic Gate: {ATOMIC_RUN} / {ATOMIC_JOB} · PASS
UPDATE: Asset {UPDATE_ASSET_ID} · {UPDATE_BYTES} bytes · {UPDATE_SHA}
Repair fallback: Asset {REPAIR_ASSET_ID} · {REPAIR_BYTES} bytes · {REPAIR_SHA}
core-updates P05 Manifest Commit: {P05_MANIFEST_COMMIT}
core-updates Manifest Gate: {MANIFEST_RUN} / {MANIFEST_JOB} · PASS
Production: v1.2.3 · OWNER_OBSERVED + MACHINE_RUNTIME_READBACK_PASS
Production Readback: {READBACK_RUN} / {READBACK_JOB} · PASS
Schema: VF-SEO-SCHEMA@1 / 1
Default Database: SQLite
```

## v1.2.3 后台在线更新闭环

v1.2.3 正式关闭了 v1.2.2 的更新自举缺口。Owner 不需要创建、查看、复制或输入 GitHub Token。GOV-DOC Legacy Update Bridge 只在旧 Production 上执行一次 server-side 更新服务初始化：管理员认证后生成临时密钥，Public Runner 使用既有共享 `VF_PRIVATE_READ_TOKEN` 做 Sodium sealed relay；浏览器 Secret=0，Runner 不使用 Production 管理员 Session。Bridge 只初始化 Update Reader，不改变 VERSION / Schema / 业务数据，也不执行正式产品升级。

Bridge Machine Gate：Run `{BRIDGE_RUN}` / Job `{BRIDGE_JOB}` PASS；Bridge `{BRIDGE_BYTES}` bytes / SHA-256 `{BRIDGE_SHA}`。Sealed Relay：Run `{RELAY_RUN}` / Job `{RELAY_JOB}` PASS，完成后 Bridge 自清理。

随后 Owner 在 Product v2 **系统与更新** 中完成正式 `v1.2.2 → v1.2.3` 后台 Atomic 更新。Owner 截图显示“当前版本 V1.2.3 / 最新版本 V1.2.3 / 已是最新版本”；独立只读 Machine Readback Run `{READBACK_RUN}` / Job `{READBACK_JOB}` 再次证明 Production `version=1.2.3 / schema=1 / database=READY / process=READY`，且一次性 Bridge 已删除。

正常后续版本的产品目标保持：**后台检查更新 → Preflight → Recovery Point → Atomic Apply → Self-test → Success / Rollback**。`repair-v*.php` 仅保留为灾难恢复 fallback，不再作为日常升级主路径。

{history}'''
(ROOT / 'README.md').write_text(new_readme)

changelog_path = ROOT / 'CHANGELOG.md'
changelog = changelog_path.read_text()
start = changelog.find('## Unreleased · Post-v1.2.2 Update Service Bootstrap')
end = changelog.find('## 1.2.2 ·', start)
if start < 0 or end < 0:
    raise SystemExit('CHANGELOG_MARKER_MISSING')
section = f'''## 1.2.3 · Update Service Bootstrap Patch（正式发布 / 后台 Production 闭环 · 2026-09-02）\n\n- PR #138 修正 `CREDENTIAL_REQUIRED` 的 Product 状态表达，浏览器不再收集/持久化 GitHub Secret 或管理员密码；日常检查/安装更新继续使用 authenticated Session + Same-Origin + CSRF。\n- PR #139 新增 CLI-only / server-side-only 初始化器，统一只读 `VF_PRIVATE_READ_TOKEN` 只存在服务器更新基础设施。\n- Final Exact Source R2 `{FINAL_RUN} / {FINAL_JOB}` PASS；Formal Publication `{PUB_RUN} / {PUB_JOB}` PASS；Release `v1.2.3` / ID `{RELEASE_ID}` / source `{RELEASE_SOURCE}` / FULL `{FULL_ASSET_ID}` / SHA-256 `{FULL_SHA}`。\n- Direct Atomic `1.2.2 → 1.2.3`：Run `{ATOMIC_RUN} / {ATOMIC_JOB}` PASS；UPDATE Asset `{UPDATE_ASSET_ID}` / SHA-256 `{UPDATE_SHA}`；repair fallback Asset `{REPAIR_ASSET_ID}` / SHA-256 `{REPAIR_SHA}`；Schema 保持 `VF-SEO-SCHEMA@1 / 1`。\n- `core-updates/projects/P05.json` 已发布 exact `1.2.2 → 1.2.3 / ATOMIC`，P05 Manifest commit `{P05_MANIFEST_COMMIT}`，Manifest Gate `{MANIFEST_RUN} / {MANIFEST_JOB}` PASS。\n- 按 GOV-DOC Legacy Update Bridge 解决旧 Production 自举死锁：Bridge Gate `{BRIDGE_RUN} / {BRIDGE_JOB}` PASS；Sodium sealed relay `{RELAY_RUN} / {RELAY_JOB}` PASS；Owner 不接触 GitHub Token，browser-secret=0，Bridge 不执行正式产品升级并在 READY 后自清理。\n- Owner 随后在后台“系统与更新”完成正式升级，截图显示 `V1.2.3 / V1.2.3 / 已是最新版本`；独立 Production Readback `{READBACK_RUN} / {READBACK_JOB}` PASS，证明 `version=1.2.3 / schema=1 / database=READY / process=READY`。\n- v1.2.3 Production Closure 后，repair 单 PHP 降级为灾难恢复 fallback；日常更新主路径回归统一后台在线更新。\n\n'''
changelog_path.write_text(changelog[:start] + section + changelog[end:])

current = f'''# P05 · VF SEO · Current State

```text
Current Formal Release: v1.2.3 · RELEASED / CLOSED
Release / Tag Source: {RELEASE_SOURCE}
Release Tree: {RELEASE_TREE}
Production: v1.2.3 · OWNER_OBSERVED / SCREENSHOT_VERIFIED
Production Machine Readback: {READBACK_RUN} / {READBACK_JOB} · PASS
Update UI: Current V1.2.3 / Latest V1.2.3 / 已是最新版本
Schema: VF-SEO-SCHEMA@1 / 1
Database: SQLite · READY
Process: READY
Release Authorization: CONSUMED / CLOSED
Production Authorization: CONSUMED / CLOSED
Next Action: RETURN_TO_L2_PRODUCT_OPTIMIZATION
```

## v1.2.3 Release / Distribution Authority

- Final Exact Source R2: `{FINAL_RUN} / {FINAL_JOB}` · PASS
- Formal Publication: `{PUB_RUN} / {PUB_JOB}` · PASS
- Release ID: `{RELEASE_ID}`
- FULL Asset: `{FULL_ASSET_ID}` · `{FULL_BYTES}` bytes · SHA-256 `{FULL_SHA}`
- Atomic Gate: `{ATOMIC_RUN} / {ATOMIC_JOB}` · PASS
- UPDATE Asset: `{UPDATE_ASSET_ID}` · `{UPDATE_BYTES}` bytes · SHA-256 `{UPDATE_SHA}`
- Repair fallback: `{REPAIR_ASSET_ID}` · `{REPAIR_BYTES}` bytes · SHA-256 `{REPAIR_SHA}`
- P05 core-updates Manifest commit: `{P05_MANIFEST_COMMIT}`
- Manifest Gate: `{MANIFEST_RUN} / {MANIFEST_JOB}` · PASS

## Legacy Update Bridge Closure

GOV-DOC Legacy Update Bridge was used only to bootstrap the existing v1.2.2 Production Update Reader without exposing GitHub credentials to the Owner.

- Bridge Gate: `{BRIDGE_RUN} / {BRIDGE_JOB}` · PASS
- Bridge Artifact: `{BRIDGE_ARTIFACT_ID}` · `{BRIDGE_BYTES}` bytes · SHA-256 `{BRIDGE_SHA}`
- Admin authentication: PASS
- Recovery Point: PASS
- Sodium sealed relay: PASS
- Browser Secret: 0
- Formal product upgrade executed by Bridge: 0
- Sealed Relay: `{RELAY_RUN} / {RELAY_JOB}` · PASS
- Production admin Session used by Runner: NO
- Bridge cleanup: PASS

After initialization, the Owner performed the formal `1.2.2 → 1.2.3` Atomic upgrade through the normal **系统与更新** backend UI.

## Production Evidence

Owner screenshot shows:

- 当前版本 `V1.2.3`
- 最新版本 `V1.2.3`
- 状态 `已是最新版本`

Independent read-only Machine Production Readback `{READBACK_RUN} / {READBACK_JOB}` proves:

- `version = 1.2.3`
- `schema = 1`
- `database = READY`
- `process = READY`
- root HTTP = 200
- one-time Legacy Bridge = cleaned / 404
- automation Production write = 0

Production v1.2.3 is therefore closed with **OWNER_OBSERVED + MACHINE_RUNTIME_READBACK_PASS** evidence.

## Governance Boundary

`vf-seo` Release remains Source / Release Asset Truth. `core-updates/projects/P05.json` remains Distribution Channel Truth. Production Runtime remains Installed Runtime Truth. Shared update credentials remain server-side infrastructure and must never be exposed as a normal Product setting.
'''
(ROOT / 'docs/handoff/CURRENT_STATE.md').write_text(current)

closure = f'''# P05 · VF SEO v1.2.3 Production Closure

Status: **PASS / CLOSED**
Evidence class: **OWNER_OBSERVED / SCREENSHOT_VERIFIED + MACHINE_RUNTIME_READBACK_PASS**
Production Version: **v1.2.3**

## 1. Release Authority

- Tag: `v1.2.3`
- Release ID: `{RELEASE_ID}`
- Release / Tag target: `{RELEASE_SOURCE}`
- Release tree: `{RELEASE_TREE}`
- FULL Asset ID: `{FULL_ASSET_ID}`
- FULL bytes: `{FULL_BYTES}`
- FULL SHA-256: `{FULL_SHA}`
- Final Exact Source Gate R2: Run `{FINAL_RUN}` / Job `{FINAL_JOB}` · PASS
- Formal Publication: Run `{PUB_RUN}` / Job `{PUB_JOB}` · PASS

The v1.2.3 Tag remains fixed to the release source above. This post-release closure document does not repoint the Tag.

## 2. Atomic Distribution Authority

Direct path: `v1.2.2 → v1.2.3`

- Atomic Gate: Run `{ATOMIC_RUN}` / Job `{ATOMIC_JOB}` · PASS
- `VF_SEO_V1.2.3_UPDATE.zip`: Asset `{UPDATE_ASSET_ID}`, `{UPDATE_BYTES}` bytes, SHA-256 `{UPDATE_SHA}`
- `repair-v1.2.3.php`: Asset `{REPAIR_ASSET_ID}`, `{REPAIR_BYTES}` bytes, SHA-256 `{REPAIR_SHA}`
- Supplemental publication: Run `{SUPP_RUN}` / Job `{SUPP_JOB}` · PASS
- Coverage: formal FULL bytes, actual upgrade, private data + Runtime Pointer preservation, idempotence, rollback, hard interruption recovery, browser single-PHP, reverse-proxy HTTPS same-origin · PASS
- Schema: `VF-SEO-SCHEMA@1 / 1` · unchanged

## 3. core-updates Authority

- P05 Manifest commit: `{P05_MANIFEST_COMMIT}`
- P05 Manifest merge commit: `{P05_MANIFEST_MERGE}`
- Manifest: `projects/P05.json`
- Channel: `1.2.2 → 1.2.3 / ATOMIC`
- Manifest Gate: Run `{MANIFEST_RUN}` / Job `{MANIFEST_JOB}` · PASS
- Runtime contract: `1.2.2 = AVAILABLE`, `1.2.3 = UP_TO_DATE`, unsupported source = `BLOCKED_SOURCE_VERSION`
- `backup_required=true`; `rollback_supported=true`

`core-updates/main` is a moving Portfolio authority and may advance because of other projects; the P05 file identity above is the P05-specific channel evidence.

## 4. GOV-DOC Legacy Update Bridge

Production v1.2.2 could not discover v1.2.3 because its private Update Reader lacked the shared server-side read capability. The Owner must not be asked to create, view, copy, paste, or persist a GitHub Token in Product UI. The closure therefore used the GOV-DOC Legacy Update Bridge pattern as a one-time migration only.

- Bridge Gate: Run `{BRIDGE_RUN}` / Job `{BRIDGE_JOB}` · PASS
- Bridge Artifact ID: `{BRIDGE_ARTIFACT_ID}`
- Bridge bytes: `{BRIDGE_BYTES}`
- Bridge SHA-256: `{BRIDGE_SHA}`
- exact formal v1.2.2 source: PASS
- existing administrator authentication: PASS
- Recovery Point before mutation: PASS
- Sodium sealed Runtime Secret relay: PASS
- browser plaintext Secret: **0**
- private `runtime.env` permissions: **0600**
- live private `core-updates` + formal v1.2.3 Release discovery: PASS
- tamper fail-closed: PASS
- VERSION / Schema / business data change by Bridge: **0**
- formal product upgrade executed by Bridge: **0**

Sealed Relay Run `{RELAY_RUN}` / Job `{RELAY_JOB}` PASS. The Runner used the Production Bridge ephemeral public key and nonce, sealed the existing shared read capability, delivered it without a Production administrator Session, confirmed Production remained v1.2.2, then requested one-time Bridge cleanup. Plaintext Token was not printed or exposed to the browser.

## 5. Production Upgrade Evidence

After the one-time Reader initialization, the Owner returned to the normal Product v2 **系统与更新** UI and executed the formal backend Atomic update. The Owner-provided Production screenshot after completion shows:

- 当前版本 `V1.2.3`
- 最新版本 `V1.2.3`
- 状态 `已是最新版本`

Independent read-only Production Machine Readback Run `{READBACK_RUN}` / Job `{READBACK_JOB}` then verified:

- `/api/health` reports `version=1.2.3`
- `schema=1`
- `database=READY`
- `process=READY`
- Production root responds HTTP 200
- the one-time Legacy Bridge returns 404 / cleaned
- Machine readback itself performed `production_write=0`

Therefore the installed runtime is machine-verified as **v1.2.3**.

## 6. Product Closure

v1.2.3 closes the update-service bootstrap defect and restores the Common Product Baseline owner experience: **check update → preflight → recovery point → backend Atomic apply → verify → success / rollback**. Shared update credentials remain server-side infrastructure. `repair-v*.php` remains a disaster-recovery fallback, not the normal owner upgrade path.

Normal work returns to L2 Product Optimization.
'''
closure_path = ROOT / 'docs/authority/RELEASE_V1.2.3_PRODUCTION_CLOSURE.md'
closure_path.write_text(closure)

print('P05_V123_PRODUCTION_CLOSURE_WRITER=PASS')
