#!/usr/bin/env python3
from pathlib import Path
import json
import os
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'p01')
product = os.environ['PRODUCT_COMMIT']
tree = os.environ['PRODUCT_TREE']
main = os.environ['REMOTE_MAIN']
develop = os.environ['REMOTE_DEVELOP']
release_id = int(os.environ['RELEASE_ID'])
update_bytes = int(os.environ['UPDATE_BYTES'])
update_sha = os.environ['UPDATE_SHA']
full_bytes = int(os.environ['FULL_BYTES'])
full_sha = os.environ['FULL_SHA']
core = os.environ['CORE_UPDATES_COMMIT']
branch = os.environ['P01_BRANCH']
upgrade_time = '2026-08-16 17:11:23 +08:00'

p = root / 'VF_PROJECT.json'
d = json.loads(p.read_text(encoding='utf-8'))
d['status'] = 'V2.21.17 PRODUCTION / FINAL ONLINE PASS / CLOSED'
d['production_version'] = '2.21.17'
d['working_version'] = None
d['candidate_version'] = None
d['candidate_state'] = 'NONE / V2.21.17 RELEASED TO PRODUCTION'
d['current_phase'] = 'STABLE_OPERATIONS / V2.21.17 PRODUCTION CLOSED'
d['current_authority'] = 'V2.21.17 PRODUCTION CLOSURE SEAL'
d['current_state'] = 'PRODUCTION 2.21.17 = LATEST 2.21.17 / CLOSED'
d['lifecycle'] = 'STABLE_OPERATIONS / CLOSED'
d['verified_release_ready'] = True
d['release_ready'] = 'RELEASED / CLOSED'
d['formal_artifact_gate'] = 'PASS'
d['release_authorization'] = 'AUTHORIZED / EXECUTED / CLOSED'
d.setdefault('authority', {})['v2_21_17_production_closure'] = 'docs/evidence/V2.21.17_PRODUCTION_CLOSURE_20260816.md'
d['production_gates'] = {
    'scope': 'V2.21.17 PRODUCTION CLOSURE',
    'formal_release': 'PASS',
    'online_discovery': 'PASS / MASTER-CONFIRMED PRODUCTION BACKEND',
    'production_atomic_upgrade': 'PASS / 2.21.16 -> 2.21.17',
    'production_version_readback': 'PASS / 2.21.17',
    'production_latest_readback': 'PASS / 2.21.17',
    'production_equals_latest': 'YES',
    'schema': '2026080902 / UNCHANGED',
    'upgrade_history': 'PASS / 2026-08-16 17:11:23 +08:00',
    'product_failure': 'NONE',
    'project_block': 'NONE'
}
d['production_closure'] = {
    'version': '2.21.17',
    'latest': '2.21.17',
    'schema': '2026080902',
    'online_discovery': 'PASS',
    'production_upgrade': 'PASS',
    'production_version_readback': 'PASS',
    'production_equals_latest': True,
    'upgrade_history': {
        'from': '2.21.16',
        'to': '2.21.17',
        'result': 'success',
        'timestamp': upgrade_time,
        'authority': 'MASTER-CONFIRMED PRODUCTION SCREENSHOT'
    },
    'public_bootstrap_readback': 'PASS / 2.21.17',
    'browser_extension_boundary': '1.6.4 / UNCHANGED',
    'rollback': 'NOT REQUIRED / SUCCESSFUL UPGRADE'
}
d['release'] = {
    'scope': 'V2.21.17 CURRENT FORMAL RELEASE',
    'tag': 'v2.21.17',
    'release_id': release_id,
    'candidate_commit': product,
    'candidate_tree': tree,
    'update_asset': 'VF_Start_V2.21.17_UPDATE.zip',
    'update_bytes': update_bytes,
    'update_sha256': update_sha,
    'full_asset': 'VF_Start_V2.21.17_FULL.zip',
    'full_bytes': full_bytes,
    'full_sha256': full_sha,
    'release_identity': 'PASS / IMMUTABLE BY VF RELEASE CONTRACT'
}
d['update_system'] = {
    'project_id': 'P01',
    'component_id': 'APP',
    'source_version': '2.21.16',
    'target_version': '2.21.17',
    'production_version': '2.21.17',
    'schema_from': '2026080902',
    'schema_to': '2026080902',
    'manifest_truth': 'llhzx2018/core-updates/projects/P01.json',
    'release_truth': 'GitHub Release v2.21.17',
    'formal_tag': 'v2.21.17',
    'candidate_commit': product,
    'update_asset': 'VF_Start_V2.21.17_UPDATE.zip',
    'update_asset_bytes': update_bytes,
    'update_asset_sha256': update_sha,
    'core_updates': '2.21.17 / VERIFIED',
    'core_updates_commit': core,
    'production_discovery': 'PASS',
    'production_upgrade': 'PASS',
    'production_equals_latest': 'YES',
    'legacy_bridge': 'RETIRED / NOT REINTRODUCED',
    'browser_extension_unit': 'INDEPENDENT / 1.6.4 / UNCHANGED'
}
d['git_closure'] = {
    'scope': 'V2.21.17 PRODUCTION CLOSURE / AUTHORITY-ONLY',
    'remote_main': main,
    'remote_develop': develop,
    'candidate_authority_branch': branch,
    'candidate_product_identity': product,
    'candidate_product_tree': tree,
    'product_source_changed_after_candidate_identity': False,
    'main_promotion': 'NOT EXECUTED IN THIS CLOSURE DIRECTIVE',
    'develop_promotion': 'NOT EXECUTED IN THIS CLOSURE DIRECTIVE',
    'note': 'Remote main/develop are recorded exactly; this closure does not misstate unexecuted Git promotion as PASS.'
}
d['vf_release_executed'] = True
d['formal_release_complete'] = True
d['formal_tag_created'] = True
d['publication_completed'] = True
d['production_deployed'] = True
d['production_exact_reconciliation'] = 'NOT EXECUTED / NOT REQUIRED BY THIS CLOSURE DIRECTIVE'
d['main_updated'] = False
d['develop_updated'] = False
d['main_alignment'] = 'NOT EXECUTED FOR V2.21.17 / REMOTE main REMAINS ' + main
d['final_online_pass'] = 'YES'
d['repository_block'] = []
d['project_block'] = []
d['product_failure'] = 'NONE CONFIRMED'
d['next_action'] = 'STOP FOR MASTER / P01 V2.21.17 CLOSED'
d['v2_21_17_production_closure'] = {
    'formal_release': 'PASS',
    'online_discovery': 'PASS',
    'production_upgrade': 'PASS',
    'production_version_readback': 'PASS',
    'production_current': '2.21.17',
    'production_latest': '2.21.17',
    'production_equals_latest': 'YES',
    'schema': '2026080902',
    'upgrade_from': '2.21.16',
    'upgrade_to': '2.21.17',
    'upgrade_result': 'success',
    'upgrade_time': upgrade_time,
    'release_tag': 'v2.21.17',
    'release_id': release_id,
    'release_product_commit': product,
    'release_product_tree': tree,
    'update_asset': 'VF_Start_V2.21.17_UPDATE.zip',
    'update_bytes': update_bytes,
    'update_sha256': update_sha,
    'core_updates_commit': core,
    'core_updates_identity': 'PASS',
    'product_failure': 'NONE',
    'project_block': 'NONE',
    'status': 'CLOSED'
}
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

current = f'''# P01 · VF Start · Current Authority Overlay

> 更新时间：2026-08-16 17:11:23 +08:00
> 状态：CURRENT / V2.21.17 PRODUCTION CLOSED
> 本文件是当前 Production / Release / Online Update / Closure 的最高优先级状态覆盖；历史 SSOT 与矩阵中的旧 CURRENT 仅作为历史证据。

## 最终状态

```text
Project: P01 · VF Start
Repository: llhzx2018/vf-start

Production Current: 2.21.17
Latest: 2.21.17
Production = Latest: YES
Schema: 2026080902 / UNCHANGED
Browser Helper: 1.6.4 / UNCHANGED

Formal Release: PASS
Online Discovery: PASS
Production Upgrade: PASS
Production Version Readback: PASS
Final Online Pass: YES
Product Failure: NONE
Project Block: NONE
Status: CLOSED
```

## Release Identity

```text
Candidate Product Commit: {product}
Candidate Product Tree: {tree}
Tag: v2.21.17
Release ID: {release_id}
UPDATE: VF_Start_V2.21.17_UPDATE.zip
UPDATE bytes: {update_bytes}
UPDATE SHA-256: {update_sha}
FULL: VF_Start_V2.21.17_FULL.zip
FULL bytes: {full_bytes}
FULL SHA-256: {full_sha}
```

Release / Tag / Asset identity 已发布并按 vf-release V2.2 合同封为不可变身份，本轮未重新发布、覆盖或替换任何正式资产。

## core-updates Identity

```text
Repository: llhzx2018/core-updates
Commit: {core}
Current source: 2.21.16
Target: 2.21.17
Schema: 2026080902 -> 2026080902
Release: v2.21.17
Asset: VF_Start_V2.21.17_UPDATE.zip
bytes: {update_bytes}
SHA-256: {update_sha}
Release ID: {release_id}
```

## Production Upgrade Result

主控已根据真实 Production 后台截图确认：

```text
Production Current: 2.21.17
Latest: 2.21.17
Upgrade History: 2.21.16 -> 2.21.17
Result: success
Time: {upgrade_time}
```

公共只读 `bootstrap` 同步回读为 `2.21.17`。本轮封板没有再次执行 Production Upgrade。

## Git Remote Truth

```text
main: {main}
develop: {develop}
Authority Branch: {branch}
Product Identity: {product}
Product Source Changed After Product Identity: NO
```

本轮只做 Authority-only Production Closure Seal，未执行 `main` / `develop` 晋级，因此不得把未执行的 Git Promotion 写成 PASS。线上 Production Runtime 已由真实升级与版本回读确认是 2.21.17；Git 分支 HEAD 按本轮 Remote Truth 原样记录。

## NEXT

```text
STOP FOR MASTER
P01 · VF Start · V2.21.17 CLOSED
```
'''
(root / 'docs/authority/CURRENT.md').write_text(current, encoding='utf-8')

handoff = f'''# CURRENT STATE · P01 VF Start

更新时间：2026-08-16 17:11:23 +08:00

```text
Project: P01 · VF Start
State: V2.21.17 PRODUCTION CLOSED
Production: 2.21.17
Latest: 2.21.17
Schema: 2026080902
Formal Release: PASS
Online Discovery: PASS
Production Upgrade: PASS
Production Version Readback: PASS
Production = Latest: YES
Product Failure: NONE
Project Block: NONE
Final Online Pass: YES

Release Tag: v2.21.17
Release ID: {release_id}
Product Commit: {product}
Product Tree: {tree}
UPDATE: VF_Start_V2.21.17_UPDATE.zip / {update_bytes} bytes / {update_sha}
core-updates: {core}

Production Upgrade History:
2.21.16 -> 2.21.17 / success / {upgrade_time}

Remote main: {main}
Remote develop: {develop}
Git Promotion This Closure: NOT EXECUTED
Product Source Modification This Closure: NO
```

## NEXT ACTION

```text
STOP FOR MASTER
P01 V2.21.17 CLOSED
```
'''
(root / 'docs/handoff/CURRENT_STATE.md').write_text(handoff, encoding='utf-8')

evidence = f'''# P01 · VF Start · V2.21.17 Production Closure

## Final Verdict

- Formal Release：PASS
- Online Discovery：PASS
- Production Upgrade：PASS
- Production Version Readback：PASS
- Production = Latest：YES
- Product Failure：NONE
- Project Block：NONE
- Final Status：CLOSED

## Production Evidence

主控根据真实 Production 后台截图确认：

- Production Current：`2.21.17`
- Latest：`2.21.17`
- Upgrade：`2.21.16 -> 2.21.17`
- Result：`success`
- Time：`{upgrade_time}`

本次 Closure 另外通过公开只读 bootstrap 回读 `2.21.17`；没有再次执行 Production Upgrade。

## Release Identity

- Product Commit：`{product}`
- Product Tree：`{tree}`
- Tag：`v2.21.17`
- Release ID：`{release_id}`
- UPDATE：`VF_Start_V2.21.17_UPDATE.zip` / `{update_bytes}` bytes / `{update_sha}`
- FULL：`VF_Start_V2.21.17_FULL.zip` / `{full_bytes}` bytes / `{full_sha}`

## core-updates Identity

- Commit：`{core}`
- Source：`2.21.16`
- Target：`2.21.17`
- Schema：`2026080902 -> 2026080902`
- Release：`v2.21.17`
- Asset identity：PASS

## Git Remote Truth at Closure

- main：`{main}`
- develop：`{develop}`
- Authority Branch：`{branch}`
- Product source changed after `{product}`：NO
- main/develop promotion in this closure：NOT EXECUTED

本 Evidence 不把未执行的 Git Promotion 伪写成 PASS。Production Runtime 与 Git Remote HEAD 分别按各自真实证据记录。
'''
(root / 'docs/evidence/V2.21.17_PRODUCTION_CLOSURE_20260816.md').write_text(evidence, encoding='utf-8')

sp = root / 'docs/authority/SSOT.md'
s = sp.read_text(encoding='utf-8')
replacements = {
    '> **SSOT Revision**：`R2026.08.15-V22115-UPDATE-CORE-CANDIDATE`  ': '> **SSOT Revision**：`R2026.08.16-V22117-PRODUCTION-CLOSED`  ',
    '> **Production Authority**：`VF Start V2.21.14`  ': '> **Production Authority**：`VF Start V2.21.17`  ',
    '> **Current Production**：`VF Start V2.21.14 / PRODUCTION / CURRENT`  ': '> **Current Production**：`VF Start V2.21.17 / PRODUCTION / CURRENT / CLOSED`  ',
    '> **Development Source Baseline**：`VF Start V2.21.15 · UPDATE CORE CANDIDATE`  ': f'> **Development Source Baseline**：`V2.21.17 RELEASE PRODUCT IDENTITY {product}`  ',
    '> **Current Lifecycle**：`CANDIDATE_VALIDATION`  ': '> **Current Lifecycle**：`STABLE_OPERATIONS / CLOSED`  ',
    '> **当前阶段**：`V2.21.15 CANDIDATE VALIDATION / V2.21.14 PRODUCTION UNCHANGED`  ': '> **当前阶段**：`V2.21.17 PRODUCTION CLOSED`  ',
    '> **V2.21.14**：`PRODUCTION / CURRENT`  ': '> **V2.21.14**：`HISTORICAL / PREVIOUS PRODUCTION`  ',
    '> **V2.21.15**：`ENGINEERING / CANDIDATE / NOT PRODUCTION`  ': '> **V2.21.15**：`HISTORICAL / SUPERSEDED RELEASE`  '
}
for old, new in replacements.items():
    if old not in s:
        raise SystemExit('SSOT metadata drift: ' + old)
    s = s.replace(old, new, 1)
marker = '> **V2.21.15**：`HISTORICAL / SUPERSEDED RELEASE`  \n'
s = s.replace(marker, marker + '> **V2.21.16**：`HISTORICAL / PREVIOUS PRODUCTION`  \n> **V2.21.17**：`PRODUCTION / CURRENT / CLOSED`  \n', 1)
section = f'''# 0.00000 CURRENT · 2026-08-16 V2.21.17 Production Closure

```text
Production: 2.21.17
Latest: 2.21.17
Production = Latest: YES
Schema: 2026080902 / UNCHANGED
Formal Release: PASS
Online Discovery: PASS
Production Upgrade: PASS
Production Version Readback: PASS
Upgrade History: 2.21.16 -> 2.21.17 / success / {upgrade_time}
Release Tag: v2.21.17
Release ID: {release_id}
Release Product Identity: {product}
Release Product Tree: {tree}
UPDATE: VF_Start_V2.21.17_UPDATE.zip / {update_bytes} bytes / {update_sha}
core-updates: {core} / PASS
Remote main: {main}
Remote develop: {develop}
Git Promotion This Closure: NOT EXECUTED
Product Failure: NONE
Project Block: NONE
FINAL_ONLINE_PASS: YES
Status: CLOSED
```

本节是当前最高优先级 Production Closure 覆盖。旧的 V2.21.15、V2.21.16 `CURRENT` 文本继续作为生成时点历史证据保留，不得覆盖本节。Production Runtime 与 Git Remote HEAD 分别按真实证据记录；本轮未执行 `main` / `develop` 晋级，因此不把未执行 Git Promotion 写成 PASS。

'''
first = '---\n\n'
if first not in s:
    raise SystemExit('SSOT section anchor missing')
s = s.replace(first, first + section, 1)
sp.write_text(s, encoding='utf-8')

mp = root / 'docs/authority/ACCEPTANCE_MATRIX.md'
m = mp.read_text(encoding='utf-8')
meta = {
    '> **Matrix Revision**：`R2026.08.15-V22115-UPDATE-CORE-CANDIDATE`  ': '> **Matrix Revision**：`R2026.08.16-V22117-PRODUCTION-CLOSED`  ',
    '> **当前阶段**：`V2.21.15 CANDIDATE VALIDATION / V2.21.14 PRODUCTION UNCHANGED`  ': '> **当前阶段**：`V2.21.17 PRODUCTION CLOSED`  ',
    '> **Production Authority**：`VF Start V2.21.14`  ': '> **Production Authority**：`VF Start V2.21.17`  ',
    '> **Development Source Baseline**：`VF Start V2.21.15 · UPDATE CORE CANDIDATE`  ': f'> **Development Source Baseline**：`V2.21.17 RELEASE PRODUCT IDENTITY {product}`  ',
    '> **Target**：`VF Start V2.21.15 · CANDIDATE / NOT PRODUCTION`  ': '> **Target**：`VF Start V2.21.17 · PRODUCTION / CLOSED`  '
}
for old, new in meta.items():
    if old not in m:
        raise SystemExit('Matrix metadata drift: ' + old)
    m = m.replace(old, new, 1)
matrix_section = f'''# 0.00000 CURRENT · V2.21.17 Production Closure Gates

| ID | Gate | Evidence / Result | Status |
|---|---|---|---|
| V22117-PROD-01 | Exact Product Identity | `{product}` / `{tree}` | PASS |
| V22117-PROD-02 | Formal Release | `v2.21.17` / Release `{release_id}` | PASS |
| V22117-PROD-03 | UPDATE Identity | `{update_bytes}` bytes / `{update_sha}` | PASS |
| V22117-PROD-04 | core-updates | `{core}` / 2.21.16 -> 2.21.17 | PASS |
| V22117-PROD-05 | Online Discovery | Production backend confirmed 2.21.17 available | PASS |
| V22117-PROD-06 | Production Upgrade | `2.21.16 -> 2.21.17` / success / `{upgrade_time}` | PASS |
| V22117-PROD-07 | Production Version Readback | `2.21.17` | PASS |
| V22117-PROD-08 | Production Latest Readback | `2.21.17` | PASS |
| V22117-PROD-09 | Production = Latest | YES | PASS |
| V22117-PROD-10 | Schema | `2026080902` / unchanged | PASS |
| V22117-PROD-11 | Product Failure | NONE | PASS |
| V22117-PROD-12 | Project Block | NONE | PASS |
| V22117-PROD-13 | FINAL_ONLINE_PASS | YES | PASS |
| V22117-PROD-14 | main/develop Promotion This Closure | not executed; remote truth recorded separately | N/A |

**Current Phase：`STABLE_OPERATIONS / V2.21.17 PRODUCTION CLOSED`。** 本节是当前最高优先级矩阵覆盖；下面旧版本 CURRENT 行仅为历史证据。

'''
anchor = '# 0.000 CURRENT · V2.21.15 Unified Update Candidate Gates\n'
if anchor not in m:
    raise SystemExit('Matrix current anchor missing')
m = m.replace(anchor, matrix_section + anchor, 1)
mp.write_text(m, encoding='utf-8')

print('P01_V22117_AUTHORITY_WRITE=PASS')
