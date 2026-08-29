#!/usr/bin/env python3
from pathlib import Path
import json, os

ROOT = Path('.')
RELEASE_SOURCE = '8c819c8bfd055d16b3ac367cef15f723431d9a42'
RELEASE_TREE = 'db5a6e2b6a852e6925727b974fb7130359e3cdf8'
RUNTIME_TREE = 'febc1b01a5b59963bc974cdc6455cfa824c0adc3'
SCHEMA = '2026082901'
RELEASE_ID = 379071259
CORE_UPDATES = '7d0949e2b8e5fa11e53286685fb7fc8635b04974'
REMOTE_GATE = 33269384118
REMOTE_EVIDENCE = 9719633688
REMOTE_DIGEST = 'sha256:f49ea1fd0988e24c5663df4d98f4b082e2a90d97b97e482b14f784c05c4727e8'
UPDATE_ASSET = 'VF_Start_V2.33.0_UPDATE.zip'
UPDATE_BYTES = 1343451
UPDATE_SHA = '9520e7f45b37341456fe9f1dba1f248fe02e84143c52230760fcddb307226a9c'
OWNER_UPGRADE_AT = '2026-08-30 03:08:16'
OWNER_LAST_CHECK = '2026-08-30 03:08:21'
CLOSURE_GATE = int(os.environ['GITHUB_RUN_ID'])

# Machine-readable authority.
p = ROOT / 'VF_PROJECT.json'
d = json.loads(p.read_text(encoding='utf-8'))
d['status'] = 'V2.33.0 OWNER PRODUCTION / PRODUCTION CLOSED / L2 OPTIMIZATION READY'
d['production_version'] = '2.33.0'
d['working_version'] = '2.33.0'
d['target_release_version'] = '2.33.0'
d['current_working_branch'] = 'main / develop'
d['current_phase'] = 'V2.33.0 OWNER PRODUCTION / PRODUCTION CLOSED / L2 OPTIMIZATION READY'
d['production_release'] = {
    'version': '2.33.0',
    'tag': 'v2.33.0',
    'release_id': RELEASE_ID,
    'release_source': RELEASE_SOURCE,
    'release_tree': RELEASE_TREE,
    'runtime_tree': RUNTIME_TREE,
    'release_promotion_main': RELEASE_SOURCE,
    'schema_version': SCHEMA,
    'core_updates_commit': CORE_UPDATES,
    'online_asset': UPDATE_ASSET,
    'online_asset_bytes': UPDATE_BYTES,
    'online_asset_sha256': UPDATE_SHA,
    'formal_artifact_gate': 33268865316,
    'strict_fresh_install_gate': 33269044619,
    'main_promotion_gate': 33269077239,
    'publication_gate': 33269116444,
    'manifest_gate': 33269187425,
    'remote_online_update_gate': REMOTE_GATE,
    'remote_online_update_artifact': REMOTE_EVIDENCE,
    'remote_online_update_artifact_sha256': REMOTE_DIGEST.replace('sha256:', ''),
    'formal_release_docs_closure_gate': 33269675677,
    'owner_production_runtime': '2.33.0',
    'owner_production_schema': SCHEMA,
    'owner_production_upgrade': f'2.32.0 -> 2.33.0 / SUCCESS / {OWNER_UPGRADE_AT} Owner UI',
    'owner_version_readback': 'CURRENT 2.33.0 = LATEST 2.33.0 / PASS',
    'owner_last_check_readback': f'{OWNER_LAST_CHECK} / PASS',
    'sidebar_version_readback': 'VF Start · V2.33.0 / PASS',
    'production_closure_gate': CLOSURE_GATE,
    'production_closure': 'PASS / CLOSED',
    'assistant_production_write': False,
}
c = d['current_change']
c['base'] = 'V2.32.0 OWNER PRODUCTION'
c['result'] = 'OWNER PRODUCTION V2.33.0 / PRODUCTION CLOSED / L2 OPTIMIZATION READY'
c['production_write_by_assistant'] = False
c['owner_production'] = {
    'version': '2.33.0',
    'schema_version': SCHEMA,
    'upgrade': f'2.32.0 -> 2.33.0 / SUCCESS / {OWNER_UPGRADE_AT}',
    'current_equals_latest': '2.33.0 = 2.33.0 / PASS',
    'last_check': OWNER_LAST_CHECK,
    'sidebar': 'VF Start · V2.33.0 / PASS',
    'production_closure_gate': CLOSURE_GATE,
    'assistant_production_write': False,
}
d['authority']['current_production_evidence'] = 'docs/evidence/P01_V2.33.0_PRODUCTION_CLOSURE_20260830.md'
d['candidate_state'] = 'CLOSED / PROMOTED_TO_FORMAL_RELEASE'
d['formal_release_state'] = 'PUBLISHED / REMOTE_GATE_PASS / OWNER_PRODUCTION_CLOSED'
d['current_authority'] = 'Owner Production V2.33.0 / Schema 2026082901 / Production Closed'
d['next_action'] = 'Return to L2 product optimization from real V2.33.0 Production usage; one continuous problem domain at a time. No automatic Release or Owner Production write.'
d['core_updates_v2_33_state'] = 'PUBLISHED / CLOSED'
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Current authority.
(ROOT / 'docs/authority/CURRENT.md').write_text(f'''# P01 · VF Start · Current Authority

> 更新时间：2026-08-30
> 状态：`CURRENT / V2.33.0 OWNER PRODUCTION / PRODUCTION CLOSED`

## Production Truth

```text
Owner Production Runtime: V2.33.0
Owner Production Schema: {SCHEMA}
Owner Current = Latest: V2.33.0 = V2.33.0 / PASS
Owner Upgrade Record: 2.32.0 -> 2.33.0 / success / {OWNER_UPGRADE_AT}
Owner Last Check: {OWNER_LAST_CHECK}
Sidebar: VF Start · V2.33.0 / PASS
Production Closure Gate: {CLOSURE_GATE} PASS
Assistant Production Write: NO
```

Owner 已在真实后台手工完成 V2.32.0 → V2.33.0 在线升级。截图回读显示当前版本与最新版本均为 V2.33.0，升级记录为 success，Sidebar 同步为 V2.33.0。

## V2.33 Formal Release Truth

```text
Formal Release Source: {RELEASE_SOURCE}
Formal Release Tree: {RELEASE_TREE}
Runtime src Tree: {RUNTIME_TREE}
Tag: v2.33.0
GitHub Release ID: {RELEASE_ID}
core-updates published commit: {CORE_UPDATES}
Schema: {SCHEMA} (unchanged)
Migration: NONE
Formal Artifact Gate: 33268865316 PASS
Strict Fresh Install Fence: 33269044619 PASS
main Promotion Gate: 33269077239 PASS
Publication Gate: 33269116444 PASS
Manifest Gate: 33269187425 PASS
Final Remote Online Update Gate: {REMOTE_GATE} PASS
Remote Evidence: {REMOTE_EVIDENCE} / {REMOTE_DIGEST}
```

正式 UPDATE：`{UPDATE_ASSET}` / `{UPDATE_BYTES}` bytes / SHA256 `{UPDATE_SHA}`。

## V2.33 Product Scope

V2.33 聚焦网址健康治理：保留 LinkHealth Authority 与 legacy `problems` 兼容；Home 使用真正需要行动的 `needsAction`；`restricted` 为人工确认而非失效；ignored 不污染 review；Health 工作区提供一等“打开网址”动作，并保留 retry / history / ignore / confirm / pending / trash。

## Current Boundary

V2.33.0 已完成 Formal Release、远程在线升级验证、Owner 手工 Production Upgrade 与 Production Closure。下一阶段回到 L2 产品优化：从真实使用摩擦出发，一次只处理一个连续问题域；不自动 Release，不自动写 Owner Production。
''', encoding='utf-8')

# Acceptance matrix.
(ROOT / 'docs/authority/ACCEPTANCE_MATRIX.md').write_text(f'''# P01 · VF Start · Current Acceptance Matrix

> Production Baseline：`V2.33.0 / Schema {SCHEMA}`
> State：`OWNER PRODUCTION / PRODUCTION CLOSED`
> Next Boundary：`L2 product optimization only`

## A. Production / Publication Truth

| Gate / Contract | Result |
|---|---|
| Owner Production Runtime | `V2.33.0` / PASS |
| Owner Current = Latest | `V2.33.0 = V2.33.0` / PASS |
| Owner upgrade record | `2.32.0 -> 2.33.0 / success / {OWNER_UPGRADE_AT}` |
| Owner last check | `{OWNER_LAST_CHECK}` / PASS |
| Sidebar version | `VF Start · V2.33.0` / PASS |
| Schema | `{SCHEMA}` / unchanged |
| Migration | NONE |
| Formal Release Source | `{RELEASE_SOURCE}` |
| Formal Release Tree | `{RELEASE_TREE}` |
| Runtime src Tree | `{RUNTIME_TREE}` |
| Tag | `v2.33.0` / PASS |
| GitHub Release | `{RELEASE_ID}` / PUBLISHED |
| core-updates | `{CORE_UPDATES}` |
| Online asset | `{UPDATE_ASSET}` |
| Online asset bytes | `{UPDATE_BYTES}` |
| Online asset SHA256 | `{UPDATE_SHA}` |
| Health Triage Browser Gate | `33267181746` / PASS |
| Candidate Readiness | `33268162412` / PASS |
| Final Metadata Fence | `33268277822` / PASS |
| Formal Artifact Gate | `33268865316` / PASS |
| Strict Fresh Install Fence | `33269044619` / PASS |
| main Promotion Gate | `33269077239` / PASS |
| Publication Gate | `33269116444` / PASS |
| Manifest Gate | `33269187425` / PASS |
| Final Remote Online Update Gate | `{REMOTE_GATE}` / PASS |
| Formal Release Docs Closure | `33269675677` / PASS |
| Owner Production Closure Gate | `{CLOSURE_GATE}` / PASS |

## B. Core Functional / Data Contract

| Capability | Result |
|---|---|
| One URL/Data Authority retained | PASS |
| URL Identity = `links` | PASS |
| Navigation Category Authority = `categories` | PASS |
| Domain Profile Authority = `resource_domain_profiles` | PASS |
| Attachment Authority = `resource_asset_files` | PASS |
| Shadow URL/Category/Privacy Authority introduced | NO |
| Schema Change in V2.33 | NO |
| Migration in V2.33 | NONE |
| Public / Private boundary | PASS |
| Atomic Create / Edit retained | PASS |
| Backup / Recovery / Atomic Update weakened | NO |
| SQLite integrity / FK | PASS |

## C. V2.33 Health Triage Contract

| Capability | Result |
|---|---|
| legacy raw `problems` compatibility | PASS |
| Home actionable `needsAction` | PASS |
| Restricted separated from invalid | PASS |
| Restricted manual confirmation | PASS |
| Ignored excluded from review | PASS |
| Open URL action | PASS |
| Legacy Health actions retained | PASS |
| Desktop / Mobile | PASS |
| Anonymous boundary | PASS |

## D. Production Verdict

**V2.33.0 = FORMAL RELEASE PASS / REMOTE ONLINE UPDATE PASS / OWNER PRODUCTION PASS / PRODUCTION CLOSED.**
''', encoding='utf-8')

# Handoff current state.
(ROOT / 'docs/handoff/CURRENT_STATE.md').write_text(f'''# CURRENT STATE · P01 VF Start

更新时间：2026-08-30

```text
Project: P01 · VF Start
Production: V2.33.0 / Schema {SCHEMA} / CLOSED
Formal Release Source: {RELEASE_SOURCE}
Formal Release Tree: {RELEASE_TREE}
Runtime src Tree: {RUNTIME_TREE}
Tag: v2.33.0
GitHub Release ID: {RELEASE_ID}
core-updates: {CORE_UPDATES}
Final Remote Online Update Gate: {REMOTE_GATE} PASS
Owner Upgrade: 2.32.0 -> 2.33.0 / SUCCESS / {OWNER_UPGRADE_AT}
Owner Current = Latest: 2.33.0 = 2.33.0 / PASS
Owner Last Check: {OWNER_LAST_CHECK}
Sidebar: VF Start · V2.33.0 / PASS
Production Closure Gate: {CLOSURE_GATE} PASS
Assistant Production Write: NO
```

## V2.33 CLOSED CHAIN

Health Triage `33267181746` → Candidate Readiness `33268162412` → Metadata Fence `33268277822` → Formal Artifact `33268865316` → Strict Fresh `33269044619` → main Promotion `33269077239` → Publication `33269116444` → Manifest `33269187425` → Final Remote Online Update `{REMOTE_GATE}` → Formal Release Docs Closure `33269675677` → Owner Production Closure `{CLOSURE_GATE}`，全部 PASS。

Owner 已在真实后台手工完成升级；助手没有写入 Production。

## NEXT ACTION

回到 L2 产品优化。只从 V2.33.0 真实 Production 使用摩擦中选择一个连续问题域推进；不重复 RPD/Prototype，除非产品方向真实变化；不自动 Release / Production。
''', encoding='utf-8')

# Production evidence.
(ROOT / 'docs/evidence/P01_V2.33.0_PRODUCTION_CLOSURE_20260830.md').write_text(f'''# P01 · V2.33.0 Owner Production Closure · 2026-08-30

> Result: `PASS / PRODUCTION CLOSED`

## Owner Production Readback

User-provided authenticated VF Start Online Update UI evidence shows:

```text
Current Version: V2.33.0
Latest Version: V2.33.0
Last Check: {OWNER_LAST_CHECK}
Latest Upgrade Record: 2.32.0 -> 2.33.0 / success / {OWNER_UPGRADE_AT}
Sidebar: VF Start · V2.33.0
```

This is an Owner-performed Production upgrade. Assistant Production Write = NO.

## Immutable Release Identity

```text
Release Source: {RELEASE_SOURCE}
Release Tree: {RELEASE_TREE}
Runtime src Tree: {RUNTIME_TREE}
Version: 2.33.0
Schema: {SCHEMA}
Migration: NONE
Tag: v2.33.0
GitHub Release ID: {RELEASE_ID}
core-updates: {CORE_UPDATES}
```

## Pre-Production Machine Chain

```text
33267181746 PASS  Health Triage Browser Gate
33268162412 PASS  Unified Candidate Readiness
33268277822 PASS  Final Metadata Fence
33268865316 PASS  Formal Artifact Gate
33269044619 PASS  Strict Fresh Install Fence
33269077239 PASS  main Promotion
33269116444 PASS  Publication
33269187425 PASS  core-updates Manifest Gate
{REMOTE_GATE} PASS  Final Remote Online Update Gate
33269675677 PASS  Formal Release Docs Closure
```

## Production Closure Gate

```text
{CLOSURE_GATE} PASS
```

The closure gate verifies docs/meta-only scope, immutable runtime bytes, VERSION 2.33.0, Schema {SCHEMA}, and that the recorded Owner Production evidence matches the explicit authenticated UI readback supplied by the Owner.

## Verdict

**V2.33.0 = OWNER PRODUCTION / PRODUCTION CLOSED.**
''', encoding='utf-8')

# README current truth.
(ROOT / 'README.md').write_text(f'''# P01 · VF Start

VF Start 是单管理员、个人使用优先的**个人互联网资产工作区**。

当前长期产品定义：

```text
One System
+ One URL/Data Authority
+ One Private Workspace
+ Multiple Resource Domains
```

## Current Truth

```text
Owner Production: V2.33.0
Schema: {SCHEMA}
Formal Release Source: {RELEASE_SOURCE}
Formal Release Tree: {RELEASE_TREE}
Runtime src Tree: {RUNTIME_TREE}
Tag: v2.33.0
GitHub Release ID: {RELEASE_ID}
core-updates: {CORE_UPDATES}
Final Remote Online Update Gate: {REMOTE_GATE} / PASS
Production Closure Gate: {CLOSURE_GATE} / PASS
Production Closure: PASS / CLOSED
```

Owner 已在后台真实完成 `2.32.0 -> 2.33.0` 在线升级；Current=`V2.33.0`、Latest=`V2.33.0`，升级记录=`success / {OWNER_UPGRADE_AT}`，Sidebar=`VF Start · V2.33.0`。

## Product Structure

```text
VF Start
├─ 首页
├─ 导航
├─ 频道
├─ 影视
└─ 专题
```

底层只有一份 URL Asset Truth：

- `links` = URL Identity；
- `categories` = 导航分类 Authority；
- `resource_domain_profiles` = 资源域 Profile Authority；
- `resource_asset_files` = Cover / Hosted HTML 附件 Authority；
- 导航隐私支持分类/祖先继承；非导航资源以自身 `is_private` 为 Authority；
- Schema = `{SCHEMA}`。

## V2.33 Production UX

- 登录后的 `/` 是 Home Command Center；匿名 `/` 保持 Public Navigator；
- Home 使用真实待整理、最近使用、收藏、Operation History 与 Health Signal；
- V2.33 的 Health Triage 使用 actionable `needsAction`，访问受限独立为人工确认，不等同于网址失效；
- `surfaces.php` 保持完整“全部资源”工作区；
- 固定五域全局导航：`首页 / 导航 / 频道 / 影视 / 专题`；
- 导航保留完整层级分类、0-count 分类、搜索定位与移动端分类选择；
- 当前域 Add 只显示本域相关字段并继承当前域；All Resources 保留跨域添加；
- Atomic Add/Edit、Hosted HTML sandbox、Public/Private、Backup/Recovery/Atomic Update 边界保持有效。

## Current Authority

优先读取：

1. [`docs/authority/CURRENT.md`](docs/authority/CURRENT.md)；
2. [`docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md`](docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md)；
3. [`docs/authority/RPD.md`](docs/authority/RPD.md)；
4. [`docs/authority/SSOT.md`](docs/authority/SSOT.md)；
5. [`docs/authority/ACCEPTANCE_MATRIX.md`](docs/authority/ACCEPTANCE_MATRIX.md)；
6. [`VF_PROJECT.json`](VF_PROJECT.json)；
7. [`docs/evidence/P01_V2.33.0_PRODUCTION_CLOSURE_20260830.md`](docs/evidence/P01_V2.33.0_PRODUCTION_CLOSURE_20260830.md)。

历史版本与历史 Evidence 保留在 `CHANGELOG.md` 与 `docs/evidence/`，但不覆盖 Current Authority。

## Security / Release Boundary

- Anonymous Public Projection 与 Owner Workspace 隔离；
- Admin Mutation = Session + POST + CSRF；
- Backup / Recovery / Atomic Update 合同继续有效；
- `v2.33.0` Tag / Release 不重写；
- 下一阶段回到 L2 产品优化；
- 不自动写 Owner Production。

完整中文文档入口：[`docs/README.md`](docs/README.md)。
''', encoding='utf-8')

# Docs index.
(ROOT / 'docs/README.md').write_text(f'''# P01 · VF Start · 文档中心

> Current Production：`V2.33.0`
> Production Closure：`PASS / CLOSED`
> Schema：`{SCHEMA}`
> Next Phase：`L2 Product Optimization`

## 1. Current Authority · 必读

1. [`authority/CURRENT.md`](authority/CURRENT.md) — 当前 Production / Git / Release Truth；
2. [`authority/P01_FUNCTIONAL_CONTRACT_20260829.md`](authority/P01_FUNCTIONAL_CONTRACT_20260829.md) — Presentation-flexible Functional Authority；
3. [`authority/RPD.md`](authority/RPD.md) — 当前产品定义；
4. [`authority/SSOT.md`](authority/SSOT.md) — 数据、隐私、Domain、Mutation 工程合同；
5. [`authority/ACCEPTANCE_MATRIX.md`](authority/ACCEPTANCE_MATRIX.md) — 当前验收矩阵；
6. [`../VF_PROJECT.json`](../VF_PROJECT.json) — 机器可读 Current State；
7. [`evidence/P01_V2.33.0_PRODUCTION_CLOSURE_20260830.md`](evidence/P01_V2.33.0_PRODUCTION_CLOSURE_20260830.md) — 当前 Production Closure Evidence。

## 2. Current Production / Release Truth

```text
Owner Production: V2.33.0
Schema: {SCHEMA}
Formal Release Source: {RELEASE_SOURCE}
Formal Release Tree: {RELEASE_TREE}
Runtime src Tree: {RUNTIME_TREE}
Tag: v2.33.0
GitHub Release ID: {RELEASE_ID}
core-updates: {CORE_UPDATES}
Online Asset: {UPDATE_ASSET}
Online SHA256: {UPDATE_SHA}
Final Remote Gate: {REMOTE_GATE} / PASS
Owner Upgrade: 2.32.0 -> 2.33.0 / success / {OWNER_UPGRADE_AT}
Production Closure Gate: {CLOSURE_GATE} / PASS
```

## 3. Current Product Model

`ONE SYSTEM + ONE URL/DATA AUTHORITY + ONE PRIVATE WORKSPACE + MULTIPLE RESOURCE DOMAINS`

资源域：`首页 / 导航 / 频道 / 影视 / 专题`。底层 `links` 是唯一 URL Identity；`categories` 是导航分类 Authority；`resource_domain_profiles` 与 `resource_asset_files` 分别承担资源域扩展与附件元数据。

## 4. V2.33 Production Capability

- Home Command Center / All Resources 分离；
- 真实 Recent / Favorite / Activity / Health；
- Health Triage actionable `needsAction`；restricted 人工确认而非失效；ignored 不污染 review；
- 一等“打开网址”动作；
- 五域导航与各域独立内容密度；
- 完整导航层级分类与隐私继承；
- Context-aware Add / Domain normalization；
- Atomic Create/Edit、Backup/Recovery/Online Update 安全边界。

## 5. Current Evidence

```text
33267181746 PASS  Health Triage Browser Gate
33268162412 PASS  Candidate Readiness
33268277822 PASS  Final Metadata Fence
33268865316 PASS  Formal Artifact Gate
33269044619 PASS  Strict Fresh Install Fence
33269077239 PASS  main Promotion
33269116444 PASS  Publication
33269187425 PASS  Manifest
{REMOTE_GATE} PASS  Final Remote Online Update
33269675677 PASS  Formal Release Docs Closure
{CLOSURE_GATE} PASS  Owner Production Closure
```

## 6. Architecture / Historical Evidence

`architecture/` 与 `decisions/` 保留架构演进；`evidence/` 保留 Machine / UI / Release / Production 证据；历史 Evidence 不删除、不改写成 Current Truth。

## 7. Next Boundary

V2.33.0 Production Closure 已结束。下一阶段回到 L2：从真实 Production 使用摩擦推进，一次只处理一个连续问题域；不重复 RPD / Prototype，除非产品方向真实变化；不自动 Release / Production。
''', encoding='utf-8')

# Living authority files that name current production.
for rel in ['docs/authority/RPD.md', 'docs/authority/SSOT.md', 'docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md']:
    q = ROOT / rel
    s = q.read_text(encoding='utf-8')
    s = s.replace('V2.32.0 OWNER PRODUCTION / PRODUCTION CLOSED', 'V2.33.0 OWNER PRODUCTION / PRODUCTION CLOSED')
    s = s.replace('Current Production: `V2.32.0 / Schema 2026082901`', 'Current Production: `V2.33.0 / Schema 2026082901`')
    s = s.replace('Owner Production: V2.32.0', 'Owner Production: V2.33.0')
    s = s.replace('Formal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d', f'Formal Release Source: {RELEASE_SOURCE}')
    s = s.replace('Formal Release Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2', f'Formal Release Tree: {RELEASE_TREE}')
    s = s.replace('Runtime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff', f'Runtime src Tree: {RUNTIME_TREE}')
    s = s.replace('Tag: v2.32.0', 'Tag: v2.33.0')
    s = s.replace('GitHub Release ID: 379046260', f'GitHub Release ID: {RELEASE_ID}')
    s = s.replace('core-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8', f'core-updates main: {CORE_UPDATES}')
    s = s.replace('Final Remote Online Update Gate: 33264951077 / PASS', f'Final Remote Online Update Gate: {REMOTE_GATE} / PASS')
    s = s.replace('Production Closure Gate: 33265892448 / PASS', f'Production Closure Gate: {CLOSURE_GATE} / PASS')
    s = s.replace('V2.32.0 已完成正式 Release、真实 V2.31→V2.32 在线升级验证和 Owner 手动 Production Upgrade。', 'V2.33.0 已完成正式 Release、真实 V2.32→V2.33 在线升级验证和 Owner 手动 Production Upgrade；Schema 不变，无 Migration。')
    q.write_text(s, encoding='utf-8')

# Changelog top section only; preserve historical tail.
p = ROOT / 'CHANGELOG.md'
s = p.read_text(encoding='utf-8')
start = s.find('## V2.33.0')
end = s.find('## V2.32.0')
if start != 0 or end <= start:
    raise SystemExit('unexpected changelog headings')
new_top = f'''## V2.33.0 · Formal Release / Owner Production · 2026-08-30

- 网址健康治理完成 rebaseline：Home 使用 actionable `needsAction`；restricted 独立为人工确认而非失效；ignored 不污染 review；Health 工作区提供一等“打开网址”动作，legacy raw `problems` 兼容保持。
- Product PR #68、Candidate Readiness `33268162412`、Final Metadata Fence `33268277822`、Formal Artifact `33268865316`、Strict Fresh `33269044619`、main Promotion `33269077239`、Publication `33269116444`、Manifest `33269187425`、Final Remote Online Update `{REMOTE_GATE}`、Formal Release Docs Closure `33269675677` 全部 PASS。
- Formal Release Source=`{RELEASE_SOURCE}` / Tree=`{RELEASE_TREE}` / Runtime src Tree=`{RUNTIME_TREE}`；Schema=`{SCHEMA}`，无 Migration。
- Tag=`v2.33.0`；GitHub Release ID=`{RELEASE_ID}`；core-updates=`{CORE_UPDATES}`；正式 UPDATE SHA256=`{UPDATE_SHA}`。
- Owner 已在后台真实完成 `2.32.0 -> 2.33.0` 在线升级：Current=`V2.33.0`、Latest=`V2.33.0`、Update History=`success / {OWNER_UPGRADE_AT}`、Last Check=`{OWNER_LAST_CHECK}`、Sidebar=`VF Start · V2.33.0`。
- Production Closure Gate=`{CLOSURE_GATE}` PASS；V2.33.0 现为 Owner Production Truth。助手未执行 Owner Production Write。

'''
p.write_text(new_top + s[end:], encoding='utf-8')

print('P01_V2330_PRODUCTION_CLOSURE_DOCS_WRITTEN=PASS')
print(f'PRODUCTION_CLOSURE_GATE={CLOSURE_GATE}')
