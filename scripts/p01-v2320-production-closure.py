#!/usr/bin/env python3
from __future__ import annotations
import json, os, re
from pathlib import Path

RUN_ID = int(os.environ.get('GITHUB_RUN_ID', '0'))
ROOT = Path('.')


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def write(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip() + '\n', encoding='utf-8')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f'{label}: expected exactly one anchor, got {text.count(old)}')
    return text.replace(old, new, 1)

# Machine-readable authority
vf_path = ROOT / 'VF_PROJECT.json'
vf = json.loads(vf_path.read_text(encoding='utf-8'))
vf['status'] = 'V2.32.0 OWNER PRODUCTION / PRODUCTION CLOSED / L2 OPTIMIZATION READY'
vf['production_version'] = '2.32.0'
vf['working_version'] = '2.32.0'
vf['target_release_version'] = '2.32.0'
vf['current_working_branch'] = 'main / develop'
vf['current_phase'] = 'V2.32.0 PRODUCTION CLOSED / NEXT L2 PRODUCT OPTIMIZATION'
formal = vf['current_change']['formal_release']
vf['production_release'] = {
    'version': '2.32.0',
    'tag': 'v2.32.0',
    'release_id': 379046260,
    'release_source': '120a42667fce7357fdaef03b64cb7ea41392040d',
    'release_tree': 'd0fa7c87ebefef083712ec0b7707a6c4273943f2',
    'runtime_tree': 'f348cb314623906acc851cb79d75b1c8f6637aff',
    'release_promotion_main': '120a42667fce7357fdaef03b64cb7ea41392040d',
    'schema_version': '2026082901',
    'core_updates_commit': 'e61b366d7d63faf19b895b8334c3b9900b83a7a8',
    'online_asset': 'VF_Start_V2.32.0_UPDATE.zip',
    'online_asset_bytes': 1351066,
    'online_asset_sha256': '262efaf80564f7c5942c37e1ba797434da277a8344b92cd0a7783edb90f1725a',
    'formal_artifact_gate': 33264371922,
    'main_promotion_gate': 33264426723,
    'publication_gate': 33264522854,
    'manifest_gate': 33264613957,
    'remote_online_update_gate': 33264951077,
    'remote_online_update_artifact': 9718369328,
    'remote_online_update_artifact_sha256': '86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15',
    'formal_release_docs_closure_gate': 33265148601,
    'owner_production_runtime': '2.32.0',
    'owner_production_schema': '2026082901',
    'owner_production_upgrade': '2.31.0 -> 2.32.0 / SUCCESS / 2026-08-30 01:26:32 Owner UI',
    'owner_version_readback': 'CURRENT 2.32.0 = LATEST 2.32.0 / PASS',
    'owner_last_check_readback': '2026-08-30 01:26:35 / PASS',
    'sidebar_version_readback': 'VF Start · V2.32.0 / PASS AFTER REFRESH',
    'transient_sidebar_readback': 'Immediately after upgrade the already-open page still showed VF Start · V2.31.0; after page refresh the shell showed V2.32.0. Classified as stale pre-refresh DOM, not Product FAIL.',
    'production_closure_gate': RUN_ID,
    'production_closure': 'PASS / CLOSED',
    'assistant_production_write': False,
}
vf['current_change']['result'] = 'OWNER PRODUCTION PASS / PRODUCTION CLOSED'
vf['current_change']['owner_production'] = {
    'runtime': '2.32.0',
    'schema': '2026082901',
    'upgrade': '2.31.0 -> 2.32.0 / success / 2026-08-30 01:26:32',
    'current_equals_latest': '2.32.0 = 2.32.0 / PASS',
    'last_check': '2026-08-30 01:26:35',
    'sidebar_after_refresh': 'VF Start · V2.32.0 / PASS',
    'assistant_write': False,
    'production_closure_gate': RUN_ID,
}
vf['authority']['current_production_evidence'] = 'docs/evidence/P01_V2.32.0_PRODUCTION_CLOSURE_20260830.md'
vf['candidate_state'] = 'CLOSED / PROMOTED_TO_PRODUCTION'
vf['formal_release_state'] = 'PUBLISHED / CLOSED'
vf['current_authority'] = 'Owner Production V2.32.0 / Schema 2026082901 / release and online upgrade closed'
vf['next_action'] = 'L2 product optimization from real V2.32 usage friction; one continuous problem domain at a time'
vf['v2_32_tag_state'] = 'PUBLISHED / IMMUTABLE'
vf['core_updates_v2_32_state'] = 'PUBLISHED / CLOSED'
vf_path.write_text(json.dumps(vf, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

current = f'''# P01 · VF Start · Current Authority

> 更新时间：2026-08-30
> 状态：`CURRENT / V2.32.0 OWNER PRODUCTION / PRODUCTION CLOSED`

## Production Truth

```text
Owner Production Runtime: V2.32.0
Owner Production Schema: 2026082901
Formal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d
Formal Release Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2
Runtime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff
Tag: v2.32.0 -> 120a42667fce7357fdaef03b64cb7ea41392040d
GitHub Release ID: 379046260
core-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8
Schema: 2026082901 (unchanged)
Migration: NONE
Production Closure Gate: {RUN_ID} PASS
Assistant Production Write: NO
```

Owner 已在真实后台手工完成 `2.31.0 -> 2.32.0` 在线升级。生产 UI 回读：Current=`V2.32.0`、Latest=`V2.32.0`、更新记录=`2.31.0 -> 2.32.0 / success / 2026-08-30 01:26:32`、Last Check=`2026-08-30 01:26:35`，刷新页面后 Sidebar=`VF Start · V2.32.0`。

升级完成后的第一个未刷新的页面曾短暂保留 Sidebar `V2.31.0`；刷新后 Shell 立即读取到 `V2.32.0`。这属于旧页面 DOM / 资源仍在内存中的瞬时状态，不是 Product FAIL，也没有版本文件或 Release 身份分叉。

## V2.32 Product Truth

V2.32 将登录后的根入口升级为轻量 Owner Home Command Center，同时保持 `surfaces.php` 为完整“全部资源”工作区、匿名 `/` 为 Public Navigator。

- Home 汇总真实待整理、最近使用、收藏、最近操作和条件式网址健康信号；
- Home 不创建第二套任务 / History / Health Authority；
- Start 打开行为记录真实 `last_opened_at + click_count`；
- 最近操作读取 `VfOperationHistory::recent()`；健康信号读取 `VfLinkHealth::status()`；
- `0` 待整理 / `0` 健康异常不显示填充卡；
- Public/Private、URL Identity、Atomic Add/Edit、Backup/Recovery/Update Authority 保持；
- Schema 继续为 `2026082901`，无 Migration。

## Release / Machine Evidence

```text
33263475338 PASS  Unified Candidate Readiness
33263665703 PASS  Final Metadata Fence
33264371922 PASS  Formal Artifact Gate
33264426723 PASS  Exact main Promotion
33264522854 PASS  immutable Tag + GitHub Release Publication
33264613957 PASS  core-updates V2.32 Manifest Gate
33264951077 PASS  Final V2.31 -> V2.32 Remote Online Update Gate
33265148601 PASS  Formal Release Docs Closure
{RUN_ID} PASS  Owner Production Closure Gate
```

Final Remote Evidence：`9718369328 / sha256:86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15`。

## Current Boundary

**V2.32.0 = FORMAL RELEASE PASS / REMOTE ONLINE UPDATE PASS / OWNER PRODUCTION PASS / PRODUCTION CLOSED.**

下一阶段返回 L2 产品优化，只从 V2.32 真实使用摩擦继续；不得重写 `v2.32.0` Tag/Release，不得为普通 L2 自动写 Production。
'''
write('docs/authority/CURRENT.md', current)

acceptance = f'''# P01 · VF Start · Current Acceptance Matrix

> Production Baseline：`V2.32.0 / Schema 2026082901`
> State：`OWNER PRODUCTION / PRODUCTION CLOSED`
> Next Boundary：`L2 product optimization only`

## A. Production / Publication Truth

| Gate / Contract | Result |
|---|---|
| Owner Production Runtime | `V2.32.0` / PASS |
| Owner Current = Latest | `V2.32.0 = V2.32.0` / PASS |
| Owner upgrade record | `2.31.0 -> 2.32.0 / success / 2026-08-30 01:26:32` |
| Owner last check | `2026-08-30 01:26:35` / PASS |
| Sidebar version after refresh | `VF Start · V2.32.0` / PASS |
| Schema | `2026082901` / unchanged |
| Migration | NONE |
| Formal Release Source | `120a42667fce7357fdaef03b64cb7ea41392040d` |
| Formal Release Tree | `d0fa7c87ebefef083712ec0b7707a6c4273943f2` |
| Runtime src Tree | `f348cb314623906acc851cb79d75b1c8f6637aff` |
| Tag | `v2.32.0` / PASS |
| GitHub Release | `379046260` / PUBLISHED |
| core-updates main | `e61b366d7d63faf19b895b8334c3b9900b83a7a8` |
| Online asset | `VF_Start_V2.32.0_UPDATE.zip` |
| Online asset bytes | `1351066` |
| Online asset SHA256 | `262efaf80564f7c5942c37e1ba797434da277a8344b92cd0a7783edb90f1725a` |
| Formal Artifact Gate | `33264371922` / PASS |
| main Promotion Gate | `33264426723` / PASS |
| Publication Gate | `33264522854` / PASS |
| core-updates Manifest Gate | `33264613957` / PASS |
| Final Remote Online Update Gate | `33264951077` / PASS |
| Formal Release Docs Closure | `33265148601` / PASS |
| Owner Production Closure Gate | `{RUN_ID}` / PASS |

## B. Core Functional / Data Contract

| Capability | Result |
|---|---|
| One URL/Data Authority retained | PASS |
| URL Identity = `links` | PASS |
| Navigation Category Authority = `categories` | PASS |
| Domain Profile Authority = `resource_domain_profiles` | PASS |
| Attachment Authority = `resource_asset_files` | PASS |
| Shadow URL/Category/Privacy Authority introduced | NO |
| Schema Change in V2.32 | NO |
| Migration in V2.32 | NONE |
| Navigation ancestor privacy inheritance | PASS |
| Non-navigation link privacy | PASS |
| Anonymous private-resource leak | NO |
| Hosted HTML sandbox retained | PASS |
| Atomic Create / Edit retained | PASS |
| Backup / Recovery / Atomic Update weakened | NO |
| SQLite integrity / FK | PASS |

## C. V2.32 UX / Interaction Contract

| Capability | Result |
|---|---|
| Authenticated `/` -> Home Command Center | PASS |
| Anonymous `/` remains Public Navigator | PASS |
| All Resources remains separate full workspace | PASS |
| Home Recent | PASS |
| Home Favorite Launchpad | PASS |
| Home Activity Rail | PASS |
| Home conditional Health Signal | PASS |
| Zero pending / zero health empty-card suppression | PASS |
| Start open records `last_opened_at + click_count` | PASS |
| Desktop Home | PASS |
| Mobile Home | PASS |
| Document-level horizontal overflow | NO |
| Current-domain Add / All Resources Add contracts | PASS |
| Public / Private boundary | PASS |

## D. Production Readback Classification

升级完成后的已打开页面曾暂时保留 Sidebar `VF Start · V2.31.0`，而主更新卡已显示 `V2.32.0`。刷新页面后 Sidebar 正确显示 `VF Start · V2.32.0`。该现象归类为 stale pre-refresh DOM，不是 Product FAIL。

## E. Production Verdict

**V2.32.0 = FORMAL RELEASE PASS / REMOTE ONLINE UPDATE PASS / OWNER PRODUCTION PASS / PRODUCTION CLOSED.**
'''
write('docs/authority/ACCEPTANCE_MATRIX.md', acceptance)

# SSOT: preserve long-term engineering contract, only move current identity/UX/release boundary.
ssot = read('docs/authority/SSOT.md')
ssot = ssot.replace('CURRENT / V2.31.0 OWNER PRODUCTION / PRODUCTION CLOSED', 'CURRENT / V2.32.0 OWNER PRODUCTION / PRODUCTION CLOSED')
ssot = re.sub(r'当前正式身份：\n\n```text\n.*?```', '''当前正式身份：\n\n```text\nOwner Production: V2.32.0\nSchema: 2026082901\nFormal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d\nFormal Release Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2\nRuntime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff\nTag: v2.32.0\nGitHub Release ID: 379046260\ncore-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8\nFinal Remote Online Update Gate: 33264951077 / PASS\nProduction Closure Gate: %d / PASS\n```''' % RUN_ID, ssot, count=1, flags=re.S)
ssot = ssot.replace('V2.31 当前生产 UX 额外要求：', 'V2.32 当前生产 UX 额外要求：')
ssot = ssot.replace('- 五域全局导航保持 `首页 / 导航 / 频道 / 影视 / 专题`；', '- 登录后的 `/` 为 Home Command Center，匿名 `/` 仍为 Public Navigator；\n- 五域全局导航保持 `首页 / 导航 / 频道 / 影视 / 专题`；')
ssot = re.sub(r'## 8\. Release / Production Boundary\n.*?## 9\. Current Evidence', f'''## 8. Release / Production Boundary\n\nV2.32.0 已完成 Candidate、Formal Artifact、main Promotion、immutable Tag、GitHub Release、core-updates、真实 V2.31->V2.32 Remote Online Update 与 Owner 手动 Production Upgrade。\n\nOwner Production UI 回读：Current=`V2.32.0`、Latest=`V2.32.0`、升级记录=`2.31.0 -> 2.32.0 / success / 2026-08-30 01:26:32`，刷新后 Sidebar=`VF Start · V2.32.0`。\n\n当前页面升级后未刷新时曾短暂显示旧 Sidebar 版本，刷新后恢复正确；该状态不构成 Runtime/Release Identity 分叉。\n\nProduction Closure 只更新 Git 文档 Authority，不写 Owner Production Server，不改 Runtime、Schema、Tag、Release 或 core-updates。\n\n## 9. Current Evidence''', ssot, count=1, flags=re.S)
ssot = re.sub(r'```text\n33239989166 PASS  Candidate Readiness.*?Artifact 9715951877.*?```', f'''```text\n33263475338 PASS  Candidate Readiness\n33263665703 PASS  Metadata Fence\n33264371922 PASS  Formal Artifact\n33264426723 PASS  main Promotion\n33264522854 PASS  Publication\n33264613957 PASS  core-updates Manifest\n33264951077 PASS  Final Remote Online Update\n33265148601 PASS  Formal Release Docs Closure\n{RUN_ID} PASS  Owner Production Closure\nArtifact 9718369328\n```''', ssot, count=1, flags=re.S)
write('docs/authority/SSOT.md', ssot)

# RPD: preserve product definition and replace current production/evidence/next-stage truth.
rpd = read('docs/authority/RPD.md')
rpd = rpd.replace('CURRENT / V2.31.0 OWNER PRODUCTION / PRODUCTION CLOSED', 'CURRENT / V2.32.0 OWNER PRODUCTION / PRODUCTION CLOSED')
rpd = rpd.replace('V2.31.0 已完成正式 Release、真实 V2.30→V2.31 在线升级验证和 Owner 手动 Production Upgrade。', 'V2.32.0 已完成正式 Release、真实 V2.31→V2.32 在线升级验证和 Owner 手动 Production Upgrade。')
rpd = rpd.replace('V2.31 Production 已锁定：', 'V2.32 Production 已锁定：\n\n- 登录后的 `/` 为轻量 Home Command Center；匿名 `/` 继续为 Public Navigator；\n- Home 聚合真实最近使用、收藏、待整理、Operation History 与条件式 Health Signal；\n- `surfaces.php` 保持完整“全部资源”工作区；')
rpd = re.sub(r'## 7\. 当前证据\n.*?## 8\. 明确不做', f'''## 7. 当前证据\n\n```text\nV2.32 Formal Release Source:\n120a42667fce7357fdaef03b64cb7ea41392040d\n\nFormal Artifact Gate: 33264371922 / PASS\nmain Promotion: 33264426723 / PASS\nPublication: 33264522854 / PASS\ncore-updates Manifest: 33264613957 / PASS\nFinal Remote Online Update: 33264951077 / PASS\nProduction Closure: {RUN_ID} / PASS\nEvidence Artifact: 9718369328\nDigest: sha256:86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15\nOwner Production: V2.32.0 / PASS\nSchema: 2026082901\n```\n\n## 8. 明确不做''', rpd, count=1, flags=re.S)
rpd = rpd.replace('不重写已经发布的 `v2.31.0` Tag / Release。', '不重写已经发布的 `v2.32.0` Tag / Release。')
rpd = re.sub(r'## 9\. 下一阶段 · L2 Product Optimization\n.*$', '''## 9. 下一阶段 · L2 Product Optimization\n\nV2.32 Production Closure 已结束。下一阶段不再重做产品定义，而是从真实使用摩擦继续：\n\n1. 一次选择一个连续问题域；\n2. 先确认现有 Functional Contract，不重复大范围 RPD；\n3. 用最小产品改动解决真实效率/可读性/一致性问题；\n4. 必须保持数据、隐私、Atomic Update、安全边界；\n5. 通过必要 Machine + UI Gate 后再形成下一 Candidate；\n6. Release / Production 仍与普通 L2 开发分开处理。''', rpd, count=1, flags=re.S)
write('docs/authority/RPD.md', rpd)

# Functional Contract: preserve full contract; update current production and current evidence sections.
fc = read('docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md')
fc = fc.replace('Current Production: `V2.31.0 / Schema 2026082901`', 'Current Production: `V2.32.0 / Schema 2026082901`')
fc = fc.replace('V2.31 起，具体资源域 Add 只显示本域有意义字段；All Resources 保留跨域添加。', 'V2.31 起，具体资源域 Add 只显示本域有意义字段；All Resources 保留跨域添加。V2.32 起，登录后的 `/` 为 Home Command Center，`surfaces.php` 继续承担完整 All Resources，匿名 `/` Public Navigator 不变。')
fc = fc.replace('当前 V2.31 的“私人”状态视觉采用正常受保护的 VF 青色语义；', '当前 V2.32 延续“私人”状态的正常受保护 VF 青色语义；')
fc = re.sub(r'## 12\. Current V2\.31 Production Result\n.*?## 13\. Current Evidence', '''## 12. Current V2.32 Production Result\n\nV2.29 完成 Functional + Resource Domain Rebaseline；V2.30 完成五域 IA/UX 收口；V2.31 完成 contextual Add/Privacy/Action 精修；V2.32 将登录后的根入口升级为轻量 Home Command Center，并已进入 Owner Production。\n\nV2.32 正式身份：\n\n```text\nFormal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d\nFormal Release Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2\nRuntime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff\nTag: v2.32.0\nGitHub Release ID: 379046260\ncore-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8\nSchema: 2026082901\nMigration: NONE\nOwner Production: V2.32.0\n```\n\n## 13. Current Evidence''', fc, count=1, flags=re.S)
fc = re.sub(r'V2\.31 current production chain：\n\n```text\n.*?```', f'''V2.32 current production chain：\n\n```text\nHome Command Center: 33259830188 / PASS\nHome Polish: 33260391147 / PASS\nHome Activity Rail: 33261107637 / PASS\nHome Health Signal: 33261678947 / PASS\nHome Activity Time: 33262598059 / PASS\nUnified Candidate Readiness: 33263475338 / PASS\nFinal Metadata Fence: 33263665703 / PASS\nFormal Artifact Gate: 33264371922 / PASS\nmain Promotion: 33264426723 / PASS\nPublication: 33264522854 / PASS\ncore-updates Manifest Gate: 33264613957 / PASS\nFinal V2.31 -> V2.32 Remote Online Update: 33264951077 / PASS\nFormal Release Docs Closure: 33265148601 / PASS\nOwner Production Closure: {RUN_ID} / PASS\nEvidence Artifact: 9718369328\nArtifact Digest: sha256:86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15\n```''', fc, count=1, flags=re.S)
fc = re.sub(r'## 14\. Release / Next Boundary\n.*$', '''## 14. Release / Next Boundary\n\n```text\nCurrent Production Version: 2.32.0\nSchema: 2026082901\nProduction Closure: PASS / CLOSED\nTag v2.32.0: PUBLISHED / DO NOT REWRITE\nGitHub Release: 379046260 / PUBLISHED\ncore-updates 2.32.0: PUBLISHED\nOwner Production Write by Assistant: NO\n```\n\n下一阶段从 V2.32.0 Production Baseline 返回 L2 产品优化。普通 L2 工作不得自动 main Promotion / Release / Production；除非产品方向发生真实变化，否则不重复大范围 RPD / Prototype / Portfolio。''', fc, count=1, flags=re.S)
write('docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md', fc)

# README current truth
readme = read('README.md')
readme = re.sub(r'## Current Truth\n\n```text\n.*?```\n\n.*?\n\n## Product Structure', f'''## Current Truth\n\n```text\nOwner Production: V2.32.0\nSchema: 2026082901\nFormal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d\nFormal Release Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2\nRuntime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff\nTag: v2.32.0\nGitHub Release ID: 379046260\ncore-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8\nFinal Remote Online Update Gate: 33264951077 / PASS\nProduction Closure Gate: {RUN_ID} / PASS\nProduction Closure: PASS / CLOSED\n```\n\nOwner 已通过后台真实完成 `2.31.0 -> 2.32.0` 在线升级；生产 UI 回读 Current=`V2.32.0`、Latest=`V2.32.0`，刷新后 Sidebar=`VF Start · V2.32.0`。\n\n## Product Structure''', readme, count=1, flags=re.S)
readme = readme.replace('## V2.31 Production UX', '## V2.32 Production UX')
readme = readme.replace('- 固定五域全局导航：`首页 / 导航 / 频道 / 影视 / 专题`；', '- 登录后的 `/` 是 Home Command Center；匿名 `/` 保持 Public Navigator；\n- Home 使用真实待整理、最近使用、收藏、Operation History 与条件式 Health Signal；\n- `surfaces.php` 保持完整“全部资源”工作区；\n- 固定五域全局导航：`首页 / 导航 / 频道 / 影视 / 专题`；')
readme = re.sub(r'7\. \[`docs/evidence/P01_V2\.31\.0_PRODUCTION_CLOSURE_20260829\.md`\].*', '7. [`docs/evidence/P01_V2.32.0_PRODUCTION_CLOSURE_20260830.md`](docs/evidence/P01_V2.32.0_PRODUCTION_CLOSURE_20260830.md) — 当前 Production Closure Evidence。', readme)
readme = readme.replace('- V2.31 Tag / Release 不重写；\n- 后续从 V2.31 Production Baseline 进入 L2 产品优化；', '- V2.32 Tag / Release 不重写；\n- 后续从 V2.32 Production Baseline 进入 L2 产品优化；')
write('README.md', readme)

# docs/README current truth
docs_readme = read('docs/README.md')
docs_readme = re.sub(r'> Current Production：`V2\.31\.0`\n> Production Closure：`PASS / CLOSED`\n> Schema：`2026082901`\n> Next Phase：`L2 Product Optimization`', '> Current Production：`V2.32.0`\n> Production Closure：`PASS / CLOSED`\n> Schema：`2026082901`\n> Next Phase：`L2 Product Optimization`', docs_readme, count=1)
docs_readme = docs_readme.replace('evidence/P01_V2.31.0_PRODUCTION_CLOSURE_20260829.md', 'evidence/P01_V2.32.0_PRODUCTION_CLOSURE_20260830.md')
docs_readme = re.sub(r'## 2\. Current Production / Release Truth\n\n```text\n.*?```\n\n.*?\n\n## 3\.', f'''## 2. Current Production / Release Truth\n\n```text\nOwner Production: V2.32.0\nSchema: 2026082901\nFormal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d\nFormal Release Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2\nRuntime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff\nTag: v2.32.0\nGitHub Release ID: 379046260\ncore-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8\nOnline Asset: VF_Start_V2.32.0_UPDATE.zip\nOnline SHA256: 262efaf80564f7c5942c37e1ba797434da277a8344b92cd0a7783edb90f1725a\nFinal Remote Gate: 33264951077 / PASS\nProduction Closure Gate: {RUN_ID} / PASS\n```\n\nOwner 已手动完成 `2.31.0 -> 2.32.0` 在线升级，生产 UI 回读 Current=`V2.32.0`、Latest=`V2.32.0`、刷新后 Sidebar=`VF Start · V2.32.0`。\n\n## 3.''', docs_readme, count=1, flags=re.S)
docs_readme = docs_readme.replace('## 4. V2.31 Production Capability', '## 4. V2.32 Production Capability')
docs_readme = docs_readme.replace('- 五域全局导航与各域独立内容密度；', '- 登录后的 `/` Home Command Center 与独立 All Resources；\n- Home 真实最近使用 / 收藏 / Activity / 条件式 Health Signal；\n- 五域全局导航与各域独立内容密度；')
docs_readme = re.sub(r'## 5\. Current Evidence\n\n```text\n.*?```', f'''## 5. Current Evidence\n\n```text\n33263475338 PASS  Unified Candidate Readiness\n33263665703 PASS  Final Metadata Fence\n33264371922 PASS  Formal Artifact Gate\n33264426723 PASS  main Promotion\n33264522854 PASS  Tag + GitHub Release Publication\n33264613957 PASS  core-updates Manifest Gate\n33264951077 PASS  Final V2.31 -> V2.32 Remote Online Update Gate\n33265148601 PASS  Formal Release Docs Closure\n{RUN_ID} PASS  Owner Production Closure\nArtifact: 9718369328\nDigest: sha256:86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15\n```''', docs_readme, count=1, flags=re.S)
docs_readme = docs_readme.replace('Living Current 文件必须以 V2.31 Production 为准。', 'Living Current 文件必须以 V2.32 Production 为准。')
write('docs/README.md', docs_readme)

# CHANGELOG: only replace top V2.32 section.
ch = read('CHANGELOG.md')
new_top = f'''## V2.32.0 · Formal Release / Owner Production · 2026-08-30\n\n- 登录后的根入口升级为轻量 Home Command Center；`surfaces.php` 继续作为完整“全部资源”工作区，匿名 `/` Public Navigator 不变。\n- Home 使用现有真实 Authority 展示待整理、最近使用、我的收藏、最近操作和条件式网址异常；不创建第二套任务、历史或健康系统。\n- Product PR #61～#65、Candidate Readiness `33263475338`、Formal Artifact `33264371922`、main Promotion `33264426723`、Publication `33264522854`、Manifest `33264613957`、Final Remote Online Update `33264951077` 全部 PASS。\n- Formal Release Source=`120a42667fce7357fdaef03b64cb7ea41392040d` / Tree=`d0fa7c87ebefef083712ec0b7707a6c4273943f2` / Runtime src Tree=`f348cb314623906acc851cb79d75b1c8f6637aff`；Schema=`2026082901`，无 Migration。\n- Tag=`v2.32.0`；GitHub Release ID=`379046260`；core-updates main=`e61b366d7d63faf19b895b8334c3b9900b83a7a8`；正式 UPDATE SHA256=`262efaf80564f7c5942c37e1ba797434da277a8344b92cd0a7783edb90f1725a`。\n- Owner 已在后台真实完成 `2.31.0 -> 2.32.0` 在线升级：Current=`V2.32.0`、Latest=`V2.32.0`、Update History=`success / 2026-08-30 01:26:32`、刷新后 Sidebar=`VF Start · V2.32.0`。\n- 升级完成后未刷新的旧页面曾暂时保留 Sidebar `V2.31.0`；刷新后恢复 V2.32.0，归类为 stale pre-refresh DOM，不是 Product FAIL。\n- Production Closure Gate `{RUN_ID}` PASS；Owner Production 现为 `V2.32.0 / Schema 2026082901 / CLOSED`。助手未执行 Owner Production Write。\n'''
ch, n = re.subn(r'^## V2\.32\.0 · Formal Release / Owner Production Pending · 2026-08-30\n.*?(?=\n## V2\.31\.0)', new_top.rstrip() + '\n', ch, count=1, flags=re.S)
if n != 1:
    raise SystemExit(f'CHANGELOG top anchor drift: {n}')
write('CHANGELOG.md', ch)

handoff = f'''# CURRENT STATE · P01 VF Start

更新时间：2026-08-30

```text
Project: P01 · VF Start
Owner Production: V2.32.0 / Schema 2026082901 / CLOSED
main/develop docs head before closure merge: 3fd2d9a4a8de1c36a062183ee52db64872e56905
Formal Release Source / immutable tag source: 120a42667fce7357fdaef03b64cb7ea41392040d
Formal Release Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2
Runtime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff
Tag: v2.32.0
GitHub Release ID: 379046260
core-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8
Final Remote Gate: 33264951077 PASS
Owner Production Closure Gate: {RUN_ID} PASS
Assistant Production Write: NO
```

## OWNER PRODUCTION READBACK

- Current Version：`V2.32.0`；
- Latest Version：`V2.32.0`；
- Update History：`2.31.0 -> 2.32.0 / success / 2026-08-30 01:26:32`；
- Last Check：`2026-08-30 01:26:35`；
- Sidebar after refresh：`VF Start · V2.32.0`；
- Schema：`2026082901`，无 Migration；
- Production Closure：`PASS / CLOSED`。

升级完成后的未刷新旧页面曾暂时显示 Sidebar `V2.31.0`；刷新后显示 `V2.32.0`，没有 Runtime/Tag/Release 分叉。

## V2.32 PRODUCT SCOPE

- Owner Home Command Center；
- 独立 All Resources 工作区；
- Recent / Favorite launchpad；
- Operation History activity rail；
- conditional Link Health signal；
- Start real open record；
- Public Navigator / Private boundary / Atomic Add/Edit / Backup/Recovery/Update contracts retained。

## NEXT ACTION

L3 Release / Production Closure 到此结束。下一阶段回到 L2，只从真实 V2.32 使用摩擦选择一个连续问题域继续；不重写 `v2.32.0` Tag/Release，不自动写 Production。
'''
write('docs/handoff/CURRENT_STATE.md', handoff)

evidence = f'''# P01 · V2.32.0 Production Closure Evidence · 2026-08-30

Result: **PASS / CLOSED**

## Formal Release Identity

```text
Formal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d
Formal Release Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2
Runtime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff
Tag: v2.32.0
GitHub Release ID: 379046260
core-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8
Schema: 2026082901
Migration: NONE
```

## Machine Closure

```text
33263475338 PASS  Unified Candidate Readiness
33263665703 PASS  Final Metadata Fence
33264371922 PASS  Formal Artifact Gate
33264426723 PASS  Exact main Promotion
33264522854 PASS  Tag + GitHub Release Publication
33264613957 PASS  core-updates Manifest Gate
33264951077 PASS  Final V2.31 -> V2.32 Remote Online Update Gate
33265148601 PASS  Formal Release Docs Closure
{RUN_ID} PASS  Owner Production Closure Gate
```

Final Remote Evidence：`9718369328 / sha256:86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15`。

## Owner Production Evidence

Owner 在真实 P01 后台手工执行在线升级。升级页截图明确显示：

```text
Current Version: V2.32.0
Latest Version: V2.32.0
Update History: 2.31.0 -> 2.32.0 / success
Completed At: 2026-08-30 01:26:32
Last Check: 2026-08-30 01:26:35
```

刷新后的第二张 Owner 截图进一步确认 Sidebar Footer：`VF Start · V2.32.0`。

第一张升级后截图中 Sidebar 仍显示 `V2.31.0`，但主体已经读取 `V2.32.0`。刷新后 Sidebar 正常变为 `V2.32.0`。该瞬时差异属于已打开旧页面 DOM 的 stale state，不是 Product FAIL；正式 Runtime、VERSION、Tag、Release、Manifest 没有发生分叉。

## Closure Boundary

- Owner Production Write：**Owner 手工执行**；
- Assistant Production Write：**NO**；
- 本 Closure 只更新 Git 中 Current Authority / Evidence；
- Runtime / Schema / immutable Tag / Release Assets / core-updates：**不修改**。

Final Verdict：**V2.32.0 OWNER PRODUCTION PASS / PRODUCTION CLOSED / L2 OPTIMIZATION READY**。
'''
write('docs/evidence/P01_V2.32.0_PRODUCTION_CLOSURE_20260830.md', evidence)
