#!/usr/bin/env python3
from pathlib import Path
import json

PRODUCT_SOURCE = 'faf853ab897c9e9b080dd365ab54df7698a8428c'
PRODUCT_TREE = 'f81d776da1fa92d04acd31ccbe6444cb1d9f0d43'
GATE_RUN = 33267181746
GATE_ARTIFACT = 9718999692
GATE_DIGEST = 'sha256:9b702201f22f4ce8a3a0d7fe2300aa273997259eed59e77e2a559f60a17f7164'

assert Path('VERSION').read_text(encoding='utf-8').strip() == '2.32.0'
assert Path('src/VERSION.txt').read_text(encoding='utf-8').strip() == '2.32.0'
Path('VERSION').write_text('2.33.0\n', encoding='utf-8')
Path('src/VERSION.txt').write_text('2.33.0\n', encoding='utf-8')

bp = Path('src/app/bootstrap.php')
bs = bp.read_text(encoding='utf-8')
old = "define('VF_VERSION', '2.32.0');"
new = "define('VF_VERSION', '2.33.0');"
assert bs.count(old) == 1
assert new not in bs
bp.write_text(bs.replace(old, new, 1), encoding='utf-8')

pj = Path('VF_PROJECT.json')
data = json.loads(pj.read_text(encoding='utf-8'))
assert data['production_version'] == '2.32.0'
assert data['schema_version'] == '2026082901'
data['status'] = 'V2.32.0 OWNER PRODUCTION / V2.33.0 RELEASE CANDIDATE'
data['working_version'] = '2.33.0'
data['target_release_version'] = '2.33.0'
data['working_schema_version'] = '2026082901'
data['current_working_branch'] = 'release/p01-v2.33.0-candidate-20260830'
data['current_phase'] = 'V2.33.0 CANDIDATE CLOSURE / UNIFIED READINESS GATE PENDING'
data['current_change'] = {
    'change_id': 'P01-V233-HEALTH-TRIAGE-20260830',
    'base': 'V2.32.0 OWNER PRODUCTION',
    'result': 'PRODUCT COMPLETE / VERSIONED CANDIDATE / UNIFIED GATE PENDING',
    'product_develop_source': PRODUCT_SOURCE,
    'product_develop_tree': PRODUCT_TREE,
    'schema_change': False,
    'migration': None,
    'health_triage_rebaseline': True,
    'legacy_raw_problems_compatibility': True,
    'home_needs_action_excludes_restricted_noise': True,
    'restricted_requires_manual_confirmation': True,
    'ignored_excluded_from_review_counts': True,
    'open_url_action': True,
    'desktop_mobile_verified': True,
    'anonymous_boundary_verified': True,
    'production_write_by_assistant': False,
    'prs_merged_to_develop': [68],
    'gates': {
        'health_triage': GATE_RUN,
        'candidate_readiness': None,
        'final_metadata_fence': None
    },
    'health_triage_evidence': {
        'run': GATE_RUN,
        'artifact_id': GATE_ARTIFACT,
        'artifact_digest': GATE_DIGEST,
        'raw_problems_compat_49': 'PASS',
        'home_needs_action_6': 'PASS',
        'restricted_review_42': 'PASS',
        'restricted_not_invalid': 'PASS',
        'open_url_action': 'PASS',
        'ignore_excluded_from_review': 'PASS',
        'desktop_mobile': 'PASS',
        'anonymous_boundary': 'PASS'
    }
}
auth = data.setdefault('authority', {})
auth['current_candidate_evidence'] = 'docs/evidence/P01_V2.33.0_CANDIDATE_READINESS_20260830.md'
data['candidate_version'] = '2.33.0'
data['candidate_schema_version'] = '2026082901'
data['candidate_state'] = 'VERSIONED / UNIFIED READINESS GATE PENDING'
data['formal_release_state'] = 'NOT_STARTED / CANDIDATE ONLY'
data['v2_33_tag_state'] = 'NOT_CREATED'
data['core_updates_v2_33_state'] = 'NOT_PUBLISHED'
data['current_authority'] = 'Owner Production V2.32.0 / Schema 2026082901 + V2.33.0 Health Triage Candidate'
data['next_action'] = 'Run V2.33 unified Candidate Readiness Gate; no main/tag/release/core-updates/Production before PASS'
pj.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

Path('docs/authority/CURRENT.md').write_text('''# P01 · VF Start · Current Authority

> 更新时间：2026-08-30
> 状态：`CURRENT / V2.32.0 OWNER PRODUCTION / V2.33.0 RELEASE CANDIDATE`

## Production Truth

```text
Owner Production Runtime: V2.32.0
Owner Production Schema: 2026082901
Formal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d
Tag: v2.32.0
GitHub Release ID: 379046260
core-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8
Production Closure: PASS / CLOSED
Assistant Production Write: NO
```

V2.32.0 继续是唯一 Owner Production Truth；V2.33 Candidate 不改变 main、Tag、Release、core-updates 或 Owner Production。

## V2.33 Candidate Truth

```text
Product Develop Source: faf853ab897c9e9b080dd365ab54df7698a8428c
Product Develop Tree: f81d776da1fa92d04acd31ccbe6444cb1d9f0d43
Candidate Branch: release/p01-v2.33.0-candidate-20260830
Candidate Version: 2.33.0
Schema: 2026082901 (unchanged)
Migration: NONE
Release: NO
Production Write: NO
```

V2.33 只处理一个连续问题域：网址健康治理。底层检测 Authority 保持不变，重点修正“访问受限不等于失效”的治理语义，并给人工核验提供一等“打开网址”动作。

### Product Scope

- legacy `problems` 兼容字段保持；
- Home 使用新的 `needsAction` 行动计数，排除 restricted 噪声；
- `restricted` 独立为人工确认，不再表达为失效；
- ignored 项不进入 review / Home 行动计数；
- health list 每行提供“打开网址”；
- confirmed / suspected / temporary / restricted 均显示治理建议；
- 既有 retry / history / ignore / confirm / pending / trash 合同保持；
- Schema、Atomic、Public/Private、Backup/Recovery/Update Authority 均不变。

### Verified Product Evidence

```text
PR #68 · Health Triage Rebaseline
Run 33267181746 PASS
Artifact 9718999692
Digest sha256:9b702201f22f4ce8a3a0d7fe2300aa273997259eed59e77e2a559f60a17f7164
Raw problems compatibility 49: PASS
Home needsAction 6: PASS
Restricted manual review 42: PASS
Desktop / Mobile / Anonymous Boundary: PASS
```

Candidate Readiness Evidence：`docs/evidence/P01_V2.33.0_CANDIDATE_READINESS_20260830.md`。

## Current Boundary

当前只允许完成 V2.33 Candidate Readiness / Metadata Fence。统一 Candidate Gate PASS 前，不进入 main Promotion、Tag、GitHub Release、core-updates 或 Owner Production。
''', encoding='utf-8')

Path('docs/handoff/CURRENT_STATE.md').write_text('''# CURRENT STATE · P01 VF Start

更新时间：2026-08-30

```text
Project: P01 · VF Start
Production: V2.32.0 / Schema 2026082901 / CLOSED
Candidate: V2.33.0 / Schema 2026082901
Candidate Branch: release/p01-v2.33.0-candidate-20260830
Product Develop Source: faf853ab897c9e9b080dd365ab54df7698a8428c
Product Develop Tree: f81d776da1fa92d04acd31ccbe6444cb1d9f0d43
Candidate Gate: PENDING
Release: NO
Production Write: NO
```

## V2.33 COMPLETED PRODUCT CHAIN

- PR #68 · Health Triage Rebaseline · `33267181746 PASS`
- Evidence Artifact `9718999692`
- Evidence Digest `sha256:9b702201f22f4ce8a3a0d7fe2300aa273997259eed59e77e2a559f60a17f7164`

最终 Product Runtime Delta 相对 V2.32 Production 为 4 个文件：

```text
src/app/FunctionalHome.php
src/app/LinkHealth.php
src/assets/health.js
src/health.php
```

核心结果：legacy raw problems 兼容保持；Home 只把真正需要行动的项目计入 needsAction；restricted 独立为人工确认；ignored 不污染 review；提供一等“打开网址”动作。

Schema 保持 `2026082901`；无 Migration；Atomic、Public/Private、Backup/Recovery/Update 合同保持。

## NEXT ACTION

执行 V2.33.0 Unified Candidate Readiness Gate，绑定最终 Versioned Candidate Source/Tree，并验证 Fresh Runtime、真实 `2.32.0 -> 2.33.0` 非生产升级、数据保留、网址健康治理语义、Desktop/Mobile、Public/Private、SQLite/FK。

Gate PASS 前：不动 main、Tag、Release、core-updates、Owner Production。
''', encoding='utf-8')

evidence = Path('docs/evidence/P01_V2.33.0_CANDIDATE_READINESS_20260830.md')
assert not evidence.exists()
evidence.write_text('''# P01 · VF Start · V2.33.0 Candidate Readiness

> Date: 2026-08-30
> Status: `CANDIDATE CLOSURE / UNIFIED READINESS GATE PENDING`
> Owner Production Write: `NO`
> Formal Release Published: `NO`
> Schema Change: `NO`

## 1. Production Baseline

```text
Owner Production: V2.32.0
Schema: 2026082901
Formal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d
Tag: v2.32.0
GitHub Release ID: 379046260
core-updates: e61b366d7d63faf19b895b8334c3b9900b83a7a8
```

## 2. V2.33 Product Baseline

```text
Develop Merge Source: faf853ab897c9e9b080dd365ab54df7698a8428c
Develop/Product Tree: f81d776da1fa92d04acd31ccbe6444cb1d9f0d43
Candidate Branch: release/p01-v2.33.0-candidate-20260830
Version Identity Target: 2.33.0
Schema: 2026082901
Migration: NONE
```

Runtime delta vs V2.32 Production is exactly 4 files: `FunctionalHome.php`, `LinkHealth.php`, `health.js`, `health.php`.

## 3. Product Evidence

```text
PR #68 · Health Triage Rebaseline
Run: 33267181746 PASS
Artifact: 9718999692
Digest: sha256:9b702201f22f4ce8a3a0d7fe2300aa273997259eed59e77e2a559f60a17f7164
```

PASS includes raw-problems compatibility, Home needsAction rebaseline, restricted manual-review semantics, restricted-not-invalid, first-class Open URL, ignore exclusion, legacy health actions, Desktop/Mobile, anonymous boundary, Fresh Runtime, SQLite/FK, unchanged Schema.

## 4. Candidate Gate Contract

Unified Candidate Readiness 必须绑定最终 versioned Candidate Source，并至少验证：

- root `VERSION` / `src/VERSION.txt` / `VF_VERSION` = `2.33.0`；
- Schema=`2026082901`，无 Migration；
- V2.32 Production → V2.33 Candidate 的 4-file runtime delta；
- PHP + JS syntax + Fresh Runtime + `cli/verify.php`；
- SQLite integrity / foreign keys；
- 真实非生产 `2.32.0 -> 2.33.0` Atomic Update / data preservation；
- Health status compatibility and `needsAction` semantics；
- restricted manual-confirmation semantics；
- ignored exclusion；
- Open URL + legacy health actions；
- Desktop + Mobile + anonymous boundary；
- `OWNER_PRODUCTION_WRITE=NO`。

## 5. Boundary

此文档当前只证明 Product Chain 已完成且可以进入 Unified Candidate Gate。它不等于 Formal Release Approval。Candidate Gate PASS 后再回写最终 Candidate Source / Tree / Run / Artifact / Digest，并执行 Final Metadata Fence。
''', encoding='utf-8')

cp = Path('CHANGELOG.md')
old_changelog = cp.read_text(encoding='utf-8')
assert not old_changelog.startswith('## V2.33.0')
entry = '''## V2.33.0 · Release Candidate · 2026-08-30

- 重做网址健康的治理语义：401/403/429 等“访问受限”不再直接等于“网址失效”，而是独立为人工确认信号。
- Home 新增 `needsAction` 行动口径，仅统计确认失效 / 疑似失效 / 暂时异常中的有效 review 项；legacy `problems` 兼容字段保持。
- ignored 自动检查项不再污染 Home / review 计数；health list 增加一等“打开网址”动作，并给各健康状态提供治理建议。
- 既有 retry / history / ignore / confirm / pending / trash 行为保持，底层 LinkHealth 检测 Authority 不重写。
- PR #68 已合并到 develop；Browser Gate `33267181746` PASS，Evidence Artifact `9718999692`，Digest `sha256:9b702201f22f4ce8a3a0d7fe2300aa273997259eed59e77e2a559f60a17f7164`。
- Product Develop Source=`faf853ab897c9e9b080dd365ab54df7698a8428c` / Tree=`f81d776da1fa92d04acd31ccbe6444cb1d9f0d43`；Candidate 版本推进为 `2.33.0`，Schema 保持 `2026082901`，无 Migration。
- 当前仅进入 Candidate Readiness；main / Tag / GitHub Release / core-updates / Owner Production 均未修改。

'''
cp.write_text(entry + old_changelog, encoding='utf-8')
