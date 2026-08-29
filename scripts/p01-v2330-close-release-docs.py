#!/usr/bin/env python3
from pathlib import Path
import json

ROOT=Path('.')
BASE='8c819c8bfd055d16b3ac367cef15f723431d9a42'
TREE='db5a6e2b6a852e6925727b974fb7130359e3cdf8'
RUNTIME='febc1b01a5b59963bc974cdc6455cfa824c0adc3'
SCHEMA='2026082901'

# Machine-readable current truth.
p=ROOT/'VF_PROJECT.json'; d=json.loads(p.read_text(encoding='utf-8'))
d['status']='V2.32.0 OWNER PRODUCTION / V2.33.0 FORMAL RELEASE PUBLISHED'
d['current_working_branch']='main / develop'
d['current_phase']='V2.33.0 FORMAL RELEASE CLOSED / OWNER PRODUCTION UPGRADE PENDING'
c=d['current_change']; c['result']='FORMAL RELEASE PUBLISHED / REMOTE ONLINE UPDATE PASS / OWNER PRODUCTION PENDING'
c['gates'].update({
 'final_metadata_fence':33268277822,
 'formal_artifact':33268865316,
 'strict_fresh_install':33269044619,
 'main_promotion':33269077239,
 'publication':33269116444,
 'manifest':33269187425,
 'remote_online_update':33269384118,
})
c['formal_release']={
 'version':'2.33.0','release_source':BASE,'release_tree':TREE,'runtime_tree':RUNTIME,
 'tag':'v2.33.0','release_id':379071259,'schema_version':SCHEMA,'schema_change':False,'migration':None,
 'formal_artifact_gate':33268865316,
 'formal_artifact_id':9719477166,'formal_artifact_digest':'sha256:90f30085ce4599bebba1e6c0713e77b8a1286472b7abbe41ad067684bfeb5897',
 'formal_evidence_id':9719477445,'formal_evidence_digest':'sha256:544fcfdc0dd5c3b993200036cac4c970c67098a0b0c32f7c2426bc8283126925',
 'strict_fresh_install_gate':33269044619,'strict_fresh_evidence_id':9719526774,'strict_fresh_evidence_digest':'sha256:097b77d7108507f2281f9d0b5b5685735bcedd2a52b442d97080780e5d633f64',
 'full_asset':'VF-Start-V2.33.0-FULL.zip','full_bytes':625219,'full_sha256':'0b7c7c2d43c4d399dff562a7b08d008bbe6019d1e04b6637cf0196278def5df0',
 'update_asset':'VF_Start_V2.33.0_UPDATE.zip','update_bytes':1343451,'update_sha256':'9520e7f45b37341456fe9f1dba1f248fe02e84143c52230760fcddb307226a9c',
 'repair_sha256':'7283a4f96dabb1ba926aad726f8021f1bbf8676982adfa6abee8df488f8dcab5',
 'main_promotion_gate':33269077239,'publication_gate':33269116444,
 'publication_evidence_id':9719548640,'publication_evidence_digest':'sha256:a81fb35e8296d63aed72dc77d8cff3dcb04fcd5e70dcfaafaa633aec23c294ac',
 'core_updates_commit':'7d0949e2b8e5fa11e53286685fb7fc8635b04974','manifest_gate':33269187425,
 'manifest_evidence_id':9719567908,'manifest_evidence_digest':'sha256:be323a7e281b568b87cd45e61adf1ba365269ef0ae32b9e964ecb1c655bf2694',
 'remote_online_update_gate':33269384118,'remote_online_update_evidence_id':9719633688,
 'remote_online_update_evidence_digest':'sha256:f49ea1fd0988e24c5663df4d98f4b082e2a90d97b97e482b14f784c05c4727e8',
 'remote_upgrade':'2.32.0 -> 2.33.0 / PASS / NON-PRODUCTION','health_triage_remote':'PASS','owner_production_write':False,
}
d['authority']['current_formal_release_evidence']='docs/evidence/P01_V2.33.0_RELEASE_CLOSURE_20260830.md'
d['candidate_state']='CLOSED / PROMOTED_TO_FORMAL_RELEASE'
d['formal_release_state']='PUBLISHED / REMOTE_GATE_PASS / OWNER_PRODUCTION_PENDING'
d['current_authority']='Owner Production V2.32.0 / Schema 2026082901 + V2.33.0 Formal Release Published / Remote Verified'
d['next_action']='Owner manually upgrades Production from V2.32.0 to V2.33.0 in the product UI; then perform Production readback and Production Closure. Assistant must not perform Owner Production write.'
d['v2_33_tag_state']='PUBLISHED / IMMUTABLE'
d['core_updates_v2_33_state']='PUBLISHED / REMOTE VERIFIED'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

(ROOT/'docs/authority/CURRENT.md').write_text(f'''# P01 · VF Start · Current Authority

> 更新时间：2026-08-30
> 状态：`CURRENT / V2.32.0 OWNER PRODUCTION / V2.33.0 FORMAL RELEASE PUBLISHED`

## Production Truth

```text
Owner Production Runtime: V2.32.0
Owner Production Schema: {SCHEMA}
Production Closure: PASS / CLOSED
Assistant Production Write: NO
```

Owner Production 仍是 V2.32.0；V2.33.0 已完成正式发布与非生产远程在线升级验证，但尚未写入 Owner Production。

## V2.33 Formal Release Truth

```text
Formal Release Source: {BASE}
Formal Release Tree: {TREE}
Runtime src Tree: {RUNTIME}
Tag: v2.33.0
GitHub Release ID: 379071259
core-updates published commit: 7d0949e2b8e5fa11e53286685fb7fc8635b04974
Schema: {SCHEMA} (unchanged)
Migration: NONE
Formal Artifact Gate: 33268865316 PASS
Strict Fresh Install Fence: 33269044619 PASS
main Promotion Gate: 33269077239 PASS
Publication Gate: 33269116444 PASS
Manifest Gate: 33269187425 PASS
Final Remote Online Update Gate: 33269384118 PASS
Remote Evidence: 9719633688 / sha256:f49ea1fd0988e24c5663df4d98f4b082e2a90d97b97e482b14f784c05c4727e8
Owner Production Write: NO
```

正式 UPDATE：`VF_Start_V2.33.0_UPDATE.zip` / `1343451` bytes / SHA256 `9520e7f45b37341456fe9f1dba1f248fe02e84143c52230760fcddb307226a9c`。

## V2.33 Product Scope

V2.33 只处理“网址健康治理”这一连续问题域：保留既有 LinkHealth Authority 与 legacy `problems` 兼容字段；Home 改用真正需要行动的 `needsAction`；`restricted` 明确为人工确认而非失效；ignored 不污染 review；Health 工作区提供一等“打开网址”动作，并保留 retry / history / ignore / confirm / pending / trash。

最终远程 Gate 在真实 `2.32.0 -> 2.33.0` Online Update 后再次验证：数据保留、SQLite/FK、Public/Private、Home `needsAction=6`、restricted review `42`、Ignore/Restore Authority、Desktop/Mobile 与 Anonymous Boundary 全部 PASS。

## Current Boundary

V2.33.0 Formal Release 已 CLOSED，状态为 `PUBLISHED / REMOTE_GATE_PASS / OWNER_PRODUCTION_PENDING`。下一步仅由 Owner 在后台手工执行 V2.32.0 → V2.33.0 在线升级；成功后再做 Production Readback / Production Closure。助手不得执行 Owner Production Write。
''',encoding='utf-8')

(ROOT/'docs/authority/ACCEPTANCE_MATRIX.md').write_text(f'''# P01 · VF Start · Current Acceptance Matrix

> Owner Production Baseline：`V2.32.0 / Schema {SCHEMA}`
> Published Upgrade Target：`V2.33.0 / Schema {SCHEMA}`
> State：`FORMAL RELEASE PASS / REMOTE ONLINE UPDATE PASS / OWNER PRODUCTION PENDING`

## A. Release / Upgrade Truth

| Gate / Contract | Result |
|---|---|
| Owner Production Runtime | `V2.32.0` / CLOSED |
| V2.33 Formal Release Source | `{BASE}` |
| V2.33 Formal Release Tree | `{TREE}` |
| V2.33 Runtime src Tree | `{RUNTIME}` |
| Schema | `{SCHEMA}` / unchanged |
| Migration | NONE |
| Tag | `v2.33.0` / IMMUTABLE |
| GitHub Release | `379071259` / PUBLISHED |
| core-updates V2.33 publication | `7d0949e2b8e5fa11e53286685fb7fc8635b04974` |
| Online asset | `VF_Start_V2.33.0_UPDATE.zip` |
| Online asset bytes | `1343451` |
| Online asset SHA256 | `9520e7f45b37341456fe9f1dba1f248fe02e84143c52230760fcddb307226a9c` |
| Health Triage Browser Gate V4 | `33267181746` / PASS |
| Candidate Readiness | `33268162412` / PASS |
| Final Metadata Fence | `33268277822` / PASS |
| Formal Artifact Gate | `33268865316` / PASS |
| Strict Fresh Install Fence | `33269044619` / PASS |
| main Promotion Gate | `33269077239` / PASS |
| Publication Gate | `33269116444` / PASS |
| core-updates Manifest Gate | `33269187425` / PASS |
| Final Remote Online Update Gate | `33269384118` / PASS |

## B. Upgrade Safety Contract

| Capability | Result |
|---|---|
| Real non-production `2.32.0 -> 2.33.0` online update | PASS |
| Data preservation | PASS |
| SQLite integrity / FK | PASS |
| Idempotence | PASS |
| Failure rollback | PASS |
| Interruption recovery | PASS |
| Strict fresh install | PASS |
| Schema change | NO |
| Migration | NONE |
| Public / Private boundary | PASS |
| Anonymous private-resource leak | NO |
| Owner Production write by assistant | NO |

## C. V2.33 Health Triage Contract

| Capability | Result |
|---|---|
| legacy raw `problems` compatibility | PASS |
| Home actionable `needsAction` | PASS |
| Restricted separated from invalid | PASS |
| Restricted manual review count | PASS |
| Ignored excluded from review | PASS |
| Open URL action | PASS |
| Ignore / Restore Authority | PASS |
| Legacy Health actions retained | PASS |
| Desktop / Mobile | PASS |
| Anonymous boundary | PASS |

## D. Verdict

**V2.33.0 = FORMAL RELEASE PASS / STRICT FRESH PASS / REMOTE ONLINE UPDATE PASS / READY FOR OWNER MANUAL PRODUCTION UPGRADE.**

Owner Production remains V2.32.0 until the Owner performs the upgrade in the product UI.
''',encoding='utf-8')

(ROOT/'docs/handoff/CURRENT_STATE.md').write_text(f'''# CURRENT STATE · P01 VF Start

更新时间：2026-08-30

```text
Project: P01 · VF Start
Owner Production: V2.32.0 / Schema {SCHEMA} / CLOSED
Published Target: V2.33.0 / Schema {SCHEMA}
Formal Release Source: {BASE}
Formal Release Tree: {TREE}
Runtime src Tree: {RUNTIME}
Tag: v2.33.0
GitHub Release ID: 379071259
core-updates: 7d0949e2b8e5fa11e53286685fb7fc8635b04974
Final Remote Online Update Gate: 33269384118 PASS
Remote Evidence: 9719633688 / sha256:f49ea1fd0988e24c5663df4d98f4b082e2a90d97b97e482b14f784c05c4727e8
Owner Production Write: NO
```

## V2.33 CLOSED RELEASE CHAIN

Health Triage V4 `33267181746` → Candidate Readiness `33268162412` → Final Metadata Fence `33268277822` → Formal Artifact `33268865316` → Strict Fresh Install `33269044619` → main Promotion `33269077239` → Publication `33269116444` → Manifest `33269187425` → Final Remote Online Update `33269384118`，全部 PASS。

Final Remote Gate 真实通过产品 Online Updater 从 V2.32.0 升级到 V2.33.0，并验证数据保留、SQLite/FK、Public/Private、Health Triage、Home needsAction、restricted manual review、Ignore/Restore、Desktop/Mobile 与匿名边界。

## NEXT ACTION

Owner 在真实后台手工执行 V2.32.0 → V2.33.0 在线升级。完成后回读 Current / Latest / Update History / Sidebar / Schema，再做 Production Closure。助手不得代替 Owner 写 Production。
''',encoding='utf-8')

(ROOT/'docs/evidence/P01_V2.33.0_RELEASE_CLOSURE_20260830.md').write_text(f'''# P01 · V2.33.0 Formal Release Closure · 2026-08-30

> Result: `PASS / READY_FOR_OWNER_PRODUCTION_UPGRADE`

## Immutable Release Identity

```text
Release Source: {BASE}
Release Tree: {TREE}
Runtime src Tree: {RUNTIME}
Version: 2.33.0
Schema: {SCHEMA}
Migration: NONE
Tag: v2.33.0
GitHub Release ID: 379071259
```

## Machine Chain

```text
33267181746 PASS  Health Triage Browser Gate V4
33268162412 PASS  Unified Candidate Readiness
33268277822 PASS  Final Metadata Fence
33268865316 PASS  Formal Artifact Gate
33269044619 PASS  Strict Fresh Install Fence
33269077239 PASS  main Promotion
33269116444 PASS  Publication
33269187425 PASS  core-updates Manifest Gate
33269384118 PASS  Final Remote Online Update Gate
```

The original Formal Artifact workflow contained a Harness-only fresh-install assertion path that could mask a fixture exception. Product bytes were not changed. The independent Strict Fresh Install Fence `33269044619` closed this evidence defect and passed against the exact formal source.

## Published Update

```text
core-updates commit: 7d0949e2b8e5fa11e53286685fb7fc8635b04974
Asset: VF_Start_V2.33.0_UPDATE.zip
Bytes: 1343451
SHA256: 9520e7f45b37341456fe9f1dba1f248fe02e84143c52230760fcddb307226a9c
Remote Evidence Artifact: 9719633688
Remote Evidence Digest: sha256:f49ea1fd0988e24c5663df4d98f4b082e2a90d97b97e482b14f784c05c4727e8
```

## Final Remote Result

A real isolated V2.32.0 runtime used the product Online Updater to discover current `core-updates/main`, prepare the published V2.33.0 GitHub Release asset, and install it. Post-upgrade checks passed for version, schema, data preservation, SQLite integrity/FK, anonymous public/private boundaries, actionable Health Triage semantics, Ignore/Restore authority, and Desktop/Mobile rendering.

## Boundary

Owner Production remains V2.32.0. This closure does not write the Owner server. The only next production action is the Owner manually initiating the V2.32.0 → V2.33.0 online upgrade in the product UI.
''',encoding='utf-8')

# CHANGELOG top: replace candidate section only.
p=ROOT/'CHANGELOG.md'; s=p.read_text(encoding='utf-8'); marker='## V2.32.0 · Formal Release / Owner Production · 2026-08-30'
assert marker in s
rest=s[s.index(marker):]
head=f'''## V2.33.0 · Formal Release / Owner Production Pending · 2026-08-30\n\n- 网址健康治理语义正式升级：访问受限独立为人工确认，不再直接等价于网址失效；Home 只显示真正需要处理的 `needsAction`。\n- Health 工作区新增一等“打开网址”动作，ignored 不污染 review，既有 retry / history / ignore / confirm / pending / trash 保持。\n- Health Triage V4 `33267181746`、Candidate `33268162412`、Formal Artifact `33268865316`、Strict Fresh `33269044619`、main Promotion `33269077239`、Publication `33269116444`、Manifest `33269187425`、Final Remote `33269384118` 全部 PASS。\n- Formal Release Source=`{BASE}` / Tree=`{TREE}` / Runtime src Tree=`{RUNTIME}`；Schema=`{SCHEMA}`，无 Migration。\n- Tag=`v2.33.0`；GitHub Release ID=`379071259`；core-updates publication=`7d0949e2b8e5fa11e53286685fb7fc8635b04974`。\n- UPDATE=`VF_Start_V2.33.0_UPDATE.zip` / 1343451 bytes / SHA256=`9520e7f45b37341456fe9f1dba1f248fe02e84143c52230760fcddb307226a9c`。\n- Final Remote Evidence=`9719633688` / `sha256:f49ea1fd0988e24c5663df4d98f4b082e2a90d97b97e482b14f784c05c4727e8`；真实非生产 V2.32.0 → V2.33.0 Online Update、数据保留、SQLite、隐私边界、Health Triage 与 Desktop/Mobile 全 PASS。\n- Owner Production 仍为 V2.32.0；等待 Owner 后台手工升级。助手未执行 Production Write。\n\n'''
p.write_text(head+rest,encoding='utf-8')

# README: keep long-term structure, update Current Truth and boundary.
p=ROOT/'README.md'; s=p.read_text(encoding='utf-8')
a=s.index('## Current Truth'); b=s.index('## Product Structure')
block=f'''## Current Truth\n\n```text\nOwner Production: V2.32.0\nSchema: {SCHEMA}\nPublished Upgrade Target: V2.33.0\nV2.33 Formal Release Source: {BASE}\nV2.33 Runtime src Tree: {RUNTIME}\nTag: v2.33.0\nGitHub Release ID: 379071259\ncore-updates: 7d0949e2b8e5fa11e53286685fb7fc8635b04974\nFinal Remote Online Update Gate: 33269384118 / PASS\nUpgrade Readiness: READY_FOR_OWNER_PRODUCTION_UPGRADE\n```\n\nOwner Production 仍为 V2.32.0；V2.33.0 已发布并通过真实非生产在线升级 Gate，下一步由 Owner 在后台手工升级。\n\n'''
s=s[:a]+block+s[b:]
s=s.replace('## V2.32 Production UX','## V2.33 Release / V2.32 Production UX',1)
s=s.replace('- Home 使用真实待整理、最近使用、收藏、Operation History 与条件式 Health Signal；','- Home 使用真实待整理、最近使用、收藏、Operation History 与条件式 Health Signal；V2.33 将健康信号收敛为 actionable needsAction，并把访问受限独立为人工确认；',1)
s=s.replace('- V2.32 Tag / Release 不重写；\n- 后续从 V2.32 Production Baseline 进入 L2 产品优化；','- V2.32 Tag / Release 不重写；\n- V2.33 Tag / Release 已发布且不可重写；\n- 当前下一步是 Owner 手工 V2.32 → V2.33 在线升级并随后做 Production Closure；',1)
p.write_text(s,encoding='utf-8')

# docs/README: update summary and release/evidence sections without deleting architecture index.
p=ROOT/'docs/README.md'; s=p.read_text(encoding='utf-8')
s=s.replace('> Next Phase：`L2 Product Optimization`','> Published Upgrade Target：`V2.33.0 / READY_FOR_OWNER_PRODUCTION_UPGRADE`',1)
a=s.index('## 2. Current Production / Release Truth'); b=s.index('## 3. Current Product Model')
block=f'''## 2. Current Production / Release Truth\n\n```text\nOwner Production: V2.32.0\nSchema: {SCHEMA}\nPublished Target: V2.33.0\nV2.33 Release Source: {BASE}\nV2.33 Release Tree: {TREE}\nV2.33 Runtime src Tree: {RUNTIME}\nTag: v2.33.0\nGitHub Release ID: 379071259\ncore-updates publication: 7d0949e2b8e5fa11e53286685fb7fc8635b04974\nOnline Asset: VF_Start_V2.33.0_UPDATE.zip\nOnline SHA256: 9520e7f45b37341456fe9f1dba1f248fe02e84143c52230760fcddb307226a9c\nFinal Remote Gate: 33269384118 / PASS\n```\n\nOwner Production 仍为 V2.32.0；V2.33.0 正式发布与远程升级验证已完成，等待 Owner 后台手工升级。\n\n'''
s=s[:a]+block+s[b:]
start=s.index('## 5. Current Evidence'); end=s.index('## 6. Architecture / Decisions')
ev='''## 5. Current Evidence\n\n```text\n33267181746 PASS  Health Triage Browser Gate V4\n33268162412 PASS  Unified Candidate Readiness\n33268277822 PASS  Final Metadata Fence\n33268865316 PASS  Formal Artifact Gate\n33269044619 PASS  Strict Fresh Install Fence\n33269077239 PASS  main Promotion\n33269116444 PASS  Tag + GitHub Release Publication\n33269187425 PASS  core-updates Manifest Gate\n33269384118 PASS  Final V2.32 -> V2.33 Remote Online Update Gate\nArtifact: 9719633688\nDigest: sha256:f49ea1fd0988e24c5663df4d98f4b082e2a90d97b97e482b14f784c05c4727e8\n```\n\n'''
s=s[:start]+ev+s[end:]
s=s.replace('历史 Evidence 不删除、不改写成当前 Truth；Living Current 文件必须以 V2.32 Production 为准。','历史 Evidence 不删除、不改写成当前 Truth；Living Current 文件必须同时区分 Owner Production V2.32.0 与已发布、待 Owner 升级的 V2.33.0。',1)
start=s.index('## 8. Next Boundary')
s=s[:start]+'''## 8. Next Boundary\n\nV2.33 L3 Formal Release 已完成。下一步：Owner 在后台手工执行 V2.32.0 → V2.33.0 在线升级；成功后执行 Production Readback / Production Closure。助手不自动写 Owner Production。\n'''
p.write_text(s,encoding='utf-8')

print('P01_V2330_RELEASE_DOCS_WRITTEN=PASS')
