#!/usr/bin/env python3
from pathlib import Path
import json, os

ROOT = Path.cwd()
RUN = os.environ.get('GITHUB_RUN_ID', 'UNKNOWN')

# 1) Structured project authority.
p = ROOT / 'VF_PROJECT.json'
data = json.loads(p.read_text(encoding='utf-8'))
data['status'] = 'V2.31.0 OWNER PRODUCTION / V2.32.0 FORMAL RELEASE PUBLISHED'
data['current_working_branch'] = 'main / develop'
data['current_phase'] = 'V2.32.0 FORMAL RELEASE CLOSED / OWNER PRODUCTION UPGRADE PENDING'
cc = data['current_change']
cc['result'] = 'FORMAL RELEASE PUBLISHED / REMOTE ONLINE UPDATE PASS / OWNER PRODUCTION PENDING'
cc['gates']['final_metadata_fence'] = 33263665703
cc['gates']['formal_artifact'] = 33264371922
cc['gates']['main_promotion'] = 33264426723
cc['gates']['publication'] = 33264522854
cc['gates']['manifest'] = 33264613957
cc['gates']['remote_online_update'] = 33264951077
cc['formal_release'] = {
    'version': '2.32.0',
    'release_source': '120a42667fce7357fdaef03b64cb7ea41392040d',
    'release_tree': 'd0fa7c87ebefef083712ec0b7707a6c4273943f2',
    'runtime_tree': 'f348cb314623906acc851cb79d75b1c8f6637aff',
    'tag': 'v2.32.0',
    'release_id': 379046260,
    'schema_version': '2026082901',
    'schema_change': False,
    'migration': None,
    'formal_artifact_gate': 33264371922,
    'formal_artifact_id': 9718189503,
    'formal_artifact_digest': 'sha256:7e47950f2203d33ad2dba4bd194715d3c3e69733ef6a9ed354721c34a3f0744b',
    'formal_evidence_id': 9718189670,
    'formal_evidence_digest': 'sha256:722be951a6dfeca1712b9d4df9f7edd034112761898c6ce03cf39a01a9a125c8',
    'full_asset': 'VF-Start-V2.32.0-FULL.zip',
    'full_bytes': 624392,
    'full_sha256': '603f356e53e72d4bae04645393934456cef2c5cc15595221bfacef903c9f98e0',
    'update_asset': 'VF_Start_V2.32.0_UPDATE.zip',
    'update_bytes': 1351066,
    'update_sha256': '262efaf80564f7c5942c37e1ba797434da277a8344b92cd0a7783edb90f1725a',
    'repair_sha256': '6312ea943f3057ca49508c39d73769c45f8350e1b1118ab245519181f65d0906',
    'main_promotion_gate': 33264426723,
    'publication_gate': 33264522854,
    'publication_evidence_id': 9718228856,
    'publication_evidence_digest': 'sha256:1b9210b2b95b887a6229c55f757b9a220b7dc662e75fac782ae3a8558f49ab28',
    'core_updates_commit': 'e61b366d7d63faf19b895b8334c3b9900b83a7a8',
    'manifest_gate': 33264613957,
    'manifest_evidence_id': 9718253885,
    'manifest_evidence_digest': 'sha256:abcd0e6b2bccb363dd470b5f9784567f86bb48c823e7d745160b029d5d6c9941',
    'remote_online_update_gate': 33264951077,
    'remote_online_update_evidence_id': 9718369328,
    'remote_online_update_evidence_digest': 'sha256:86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15',
    'remote_upgrade': '2.31.0 -> 2.32.0 / PASS / NON-PRODUCTION',
    'owner_production_write': False,
}
data['candidate_state'] = 'CLOSED / PROMOTED_TO_FORMAL_RELEASE'
data['formal_release_state'] = 'PUBLISHED / REMOTE_GATE_PASS / OWNER_PRODUCTION_PENDING'
data['v2_32_tag_state'] = 'PUBLISHED / IMMUTABLE'
data['core_updates_v2_32_state'] = 'PUBLISHED / REMOTE VERIFIED'
data['current_authority'] = 'Owner Production V2.31.0 / Schema 2026082901 + V2.32.0 Formal Release Published / Remote Verified'
data['next_action'] = 'Owner manually upgrades Production from V2.31.0 to V2.32.0 in the product UI; then perform Production readback and Production Closure. Assistant must not perform Owner Production write.'
data['authority']['current_formal_release_evidence'] = 'docs/evidence/P01_V2.32.0_RELEASE_CLOSURE_20260830.md'
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# 2) Current Authority.
(ROOT / 'docs/authority/CURRENT.md').write_text(f'''# P01 · VF Start · Current Authority

> 更新时间：2026-08-30
> 状态：`CURRENT / V2.31.0 OWNER PRODUCTION / V2.32.0 FORMAL RELEASE PUBLISHED + REMOTE VERIFIED`

## Owner Production Truth

```text
Owner Production Runtime: V2.31.0
Owner Production Schema: 2026082901
Owner Production Closure: PASS / CLOSED
Assistant Production Write: NO
```

Owner Production **尚未升级到 V2.32.0**。当前真实生产运行时仍是 V2.31.0；任何 V2.32 Production 结论都必须等 Owner 在后台手工执行在线升级并完成运行时回读后才能成立。

## V2.32 Formal Release Truth

```text
Formal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d
Formal Release Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2
Runtime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff
Version: 2.32.0
Schema: 2026082901 (unchanged)
Migration: NONE
Tag: v2.32.0 -> 120a42667fce7357fdaef03b64cb7ea41392040d
GitHub Release ID: 379046260
core-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8
Formal Artifact Gate: 33264371922 PASS
Main Promotion Gate: 33264426723 PASS
Publication Gate: 33264522854 PASS
Manifest Gate: 33264613957 PASS
Final Remote Online Update Gate: 33264951077 PASS
Remote Evidence: 9718369328 / sha256:86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15
Owner Production Write: NO
```

### Formal Assets

```text
VF-Start-V2.32.0-FULL.zip
  bytes: 624392
  sha256: 603f356e53e72d4bae04645393934456cef2c5cc15595221bfacef903c9f98e0

VF_Start_V2.32.0_UPDATE.zip
  bytes: 1351066
  sha256: 262efaf80564f7c5942c37e1ba797434da277a8344b92cd0a7783edb90f1725a

repair-v2.32.0.php
  sha256: 6312ea943f3057ca49508c39d73769c45f8350e1b1118ab245519181f65d0906
```

## V2.32 Product Scope

V2.32 将登录后的根入口升级为 Owner Home Command Center；`surfaces.php` 继续承担完整“全部资源”工作区，匿名 `/` 继续保持 Public Navigator。

- Home 使用既有 Authority 汇总待整理、最近使用、收藏、最近操作和条件式健康信号；
- Start 打开行为记录真实 `last_opened_at + click_count`；
- 最近操作读取 `VfOperationHistory::recent()`；健康信号读取 `VfLinkHealth::status()`；
- 不新增任务/历史/健康 Shadow System；
- Public/Private、URL Identity、Atomic Add/Edit、Backup/Recovery/Update Authority 不变；
- Schema 保持 `2026082901`，无 Migration。

## Machine Closure

Final Remote Online Update Gate `33264951077` 已从 immutable V2.31.0 Runtime 出发，经公开 `core-updates/main` 发现并下载正式 GitHub Release UPDATE，真实完成非生产 `2.31.0 -> 2.32.0` 在线升级。升级后验证：Version/Schema、数据保留、SQLite integrity/FK、匿名 Public/Private HTTP、登录 Home Desktop/Mobile、“全部资源”独立工作区、无横向溢出全部 PASS。

前两次 Remote Gate 红灯已明确归类为 Runner Harness：一次是 fixture count 断言错误，一次是把 Home 摘要误当完整私人资源列表；均未修改产品、Release、Manifest 或 Production。最终权威结果仅为 `33264951077 PASS`。

正式发布证据：`docs/evidence/P01_V2.32.0_RELEASE_CLOSURE_20260830.md`。

## Current Boundary

V2.32.0 的 **Formal Release Closure 已完成**，状态为 `READY_FOR_OWNER_PRODUCTION_UPGRADE`。下一步只能由 Owner 在真实后台手工执行 V2.31.0 → V2.32.0 在线升级；完成后再做 Production Runtime / Schema / Update History / Sidebar 回读与 Production Closure。

当前窗口不得自动写 Owner Production。
''', encoding='utf-8')

# 3) Handoff.
(ROOT / 'docs/handoff/CURRENT_STATE.md').write_text(f'''# CURRENT STATE · P01 VF Start

更新时间：2026-08-30

```text
Project: P01 · VF Start
Owner Production: V2.31.0 / Schema 2026082901 / CLOSED
Formal Release: V2.32.0 / Schema 2026082901 / PUBLISHED + REMOTE VERIFIED
Formal Source: 120a42667fce7357fdaef03b64cb7ea41392040d
Formal Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2
Runtime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff
Tag: v2.32.0
GitHub Release ID: 379046260
core-updates main: e61b366d7d63faf19b895b8334c3b9900b83a7a8
Remote Online Update Gate: 33264951077 PASS
Remote Evidence: 9718369328 / sha256:86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15
Owner Production Write: NO
```

## V2.32 RELEASE GATE CHAIN

- Candidate Readiness `33263475338` PASS
- Final Metadata Fence `33263665703` PASS
- Formal Artifact `33264371922` PASS
- Main Promotion `33264426723` PASS
- Publication `33264522854` PASS
- core-updates Manifest `33264613957` PASS
- Final Remote Online Update `33264951077` PASS

正式 UPDATE：`VF_Start_V2.32.0_UPDATE.zip` / `1351066 bytes` / `sha256:262efaf80564f7c5942c37e1ba797434da277a8344b92cd0a7783edb90f1725a`。

Remote Gate 已真实验证公开 Manifest + 正式 Release 下载和安装、V2.31.0 → V2.32.0 数据保留、Schema `2026082901`、SQLite integrity/FK、匿名五个入口隐私边界，以及真实升级后的 Home Desktop/Mobile 和独立“全部资源”工作区。

## NEXT ACTION

**仅剩 Owner Production 手工升级。**

Owner 在真实 VF Start 后台看到 V2.32.0 更新后，可手工执行在线升级。完成后新的窗口只做：

1. 回读 Current / Latest 是否均为 `2.32.0`；
2. 回读 Schema 是否仍为 `2026082901`；
3. 回读升级记录是否 `success`；
4. 回读 Sidebar 是否显示 `VF Start · V2.32.0`；
5. 完成 V2.32.0 Production Closure 文档。

禁止助手代替 Owner 点击/执行 Production Upgrade；在 Owner 确认前不得写“V2.32.0 Owner Production”。
''', encoding='utf-8')

# 4) Formal release evidence.
ev = ROOT / 'docs/evidence/P01_V2.32.0_RELEASE_CLOSURE_20260830.md'
ev.write_text(f'''# P01 · VF Start V2.32.0 · Formal Release Closure · 2026-08-30

## Verdict

`PASS / FORMAL RELEASE CLOSED / READY_FOR_OWNER_PRODUCTION_UPGRADE`

Owner Production Write：`NO`。

## Exact Authority

```text
Product Source: 8944677974e3a512d846f0740897a7a98e4b7b53
Product Tree: 09412d1b7df21deb01a45e3069ecd48e564fb458
Formal Release Source: 120a42667fce7357fdaef03b64cb7ea41392040d
Formal Release Tree: d0fa7c87ebefef083712ec0b7707a6c4273943f2
Runtime src Tree: f348cb314623906acc851cb79d75b1c8f6637aff
Version: 2.32.0
Schema: 2026082901
Migration: NONE
```

## Release Gate Chain

| Gate | Run | Result |
|---|---:|---|
| Candidate Readiness | 33263475338 | PASS |
| Final Metadata Fence | 33263665703 | PASS |
| Formal Artifact | 33264371922 | PASS |
| Main Promotion | 33264426723 | PASS |
| Publication | 33264522854 | PASS |
| core-updates Manifest | 33264613957 | PASS |
| Final Remote Online Update | 33264951077 | PASS |

## Formal Artifact

Formal Artifact Run `33264371922`：

- artifact `9718189503` / `sha256:7e47950f2203d33ad2dba4bd194715d3c3e69733ef6a9ed354721c34a3f0744b`
- evidence `9718189670` / `sha256:722be951a6dfeca1712b9d4df9f7edd034112761898c6ce03cf39a01a9a125c8`
- FULL `VF-Start-V2.32.0-FULL.zip` / 624392 bytes / `603f356e53e72d4bae04645393934456cef2c5cc15595221bfacef903c9f98e0`
- UPDATE `VF_Start_V2.32.0_UPDATE.zip` / 1351066 bytes / `262efaf80564f7c5942c37e1ba797434da277a8344b92cd0a7783edb90f1725a`
- Repair `6312ea943f3057ca49508c39d73769c45f8350e1b1118ab245519181f65d0906`

Formal Artifact Gate 真实执行 V2.31.0 → V2.32.0 Atomic Upgrade、数据保留、幂等、故障回滚、硬中断恢复、Fresh Runtime；全部 PASS。

## Publication

- `main = develop = 120a42667fce7357fdaef03b64cb7ea41392040d` at formal publication boundary
- immutable tag `v2.32.0 -> 120a42667fce7357fdaef03b64cb7ea41392040d`
- GitHub Release ID `379046260`
- Publication Gate `33264522854 PASS`
- Publication evidence `9718228856` / `sha256:1b9210b2b95b887a6229c55f757b9a220b7dc662e75fac782ae3a8558f49ab28`

## core-updates

- `core-updates/main = e61b366d7d63faf19b895b8334c3b9900b83a7a8`
- only `projects/P01.json` changed from the V2.31 manifest authority
- Manifest Gate `33264613957 PASS`
- evidence `9718253885` / `sha256:abcd0e6b2bccb363dd470b5f9784567f86bb48c823e7d745160b029d5d6c9941`
- published path: V2.31.0 → V2.32.0 / Schema 2026082901 → 2026082901 / Atomic

## Final Remote Online Update

Authoritative run：`33264951077 PASS`。

Evidence：`9718369328` / `sha256:86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15`。

该 Gate 从 immutable `v2.31.0` Runtime 启动，通过已发布 `core-updates/main` 发现 V2.32.0，再从正式 GitHub Release 下载 `VF_Start_V2.32.0_UPDATE.zip` 并真实安装。结果：

- `REMOTE_UPDATE_PASS`
- Post `VERIFY_PASS=YES`
- Version = 2.32.0
- Schema = 2026082901
- seeded public/private/domain data preservation = PASS
- SQLite integrity / foreign keys = PASS
- anonymous `/` / start / channels / watch / topics Public/Private HTTP boundary = PASS
- authenticated Home Desktop = PASS
- authenticated Home Mobile = PASS
- All Resources remains separate = PASS
- no horizontal overflow = PASS

前两轮 Remote Gate 的红灯均为 Runner Harness：fixture 计数期望错误，以及把 Home 摘要错误要求为完整私人资源列表。两次修正均只修改 Runner 测试，不修改产品、Release、Manifest 或 Owner Production。

## Production Boundary

Formal Release Closure 到此完成。Owner Production 仍是 V2.31.0 / Schema 2026082901。

下一步只允许 Owner 在真实后台手工执行 V2.31.0 → V2.32.0 在线升级；升级后必须再做 Production Runtime / Schema / Update History / Sidebar 远端回读，才能把 V2.32.0 认定为 Owner Production Truth。

Docs Closure Gate：`{RUN}`。
''', encoding='utf-8')

# 5) Changelog: replace only the V2.32 candidate section, preserve all historical content.
cp = ROOT / 'CHANGELOG.md'
s = cp.read_text(encoding='utf-8')
marker = '## V2.31.0 · Formal Release / Owner Production · 2026-08-29'
if marker not in s:
    raise SystemExit('V2.31 changelog anchor missing')
tail = s[s.index(marker):]
head = '''## V2.32.0 · Formal Release / Owner Production Pending · 2026-08-30

- 将登录后的根入口升级为真正的 Home Command Center；`surfaces.php` 继续作为完整“全部资源”工作区，匿名 `/` Public Navigator 不变。
- Home 使用既有 Authority 展示待整理、最近使用、我的收藏、四个资源域、最近操作和条件式网址异常；不创建第二套任务、历史或健康系统。
- Product PR #61～#65 已完成；Candidate Readiness `33263475338`、Formal Artifact `33264371922`、main Promotion `33264426723`、Publication `33264522854`、Manifest `33264613957`、Final Remote Online Update `33264951077` 全部 PASS。
- Formal Release Source=`120a42667fce7357fdaef03b64cb7ea41392040d` / Tree=`d0fa7c87ebefef083712ec0b7707a6c4273943f2` / Runtime src Tree=`f348cb314623906acc851cb79d75b1c8f6637aff`；Schema=`2026082901`，无 Migration。
- Tag=`v2.32.0`；GitHub Release ID=`379046260`；core-updates main=`e61b366d7d63faf19b895b8334c3b9900b83a7a8`。
- 正式 UPDATE=`VF_Start_V2.32.0_UPDATE.zip` / 1351066 bytes / SHA256=`262efaf80564f7c5942c37e1ba797434da277a8344b92cd0a7783edb90f1725a`。
- Final Remote Evidence=`9718369328` / Digest=`sha256:86855b630bcfb0d8ffa8ad042cd68876ec8c944289e7e630954a0078edb3db15`；真实非生产 V2.31.0 → V2.32.0 在线升级、数据保留、SQLite、隐私边界和升级后 Home Desktop/Mobile 全部 PASS。
- **Owner Production 仍为 V2.31.0**；当前仅允许 Owner 在后台手工升级，助手未执行 Production Write。

'''
cp.write_text(head + tail, encoding='utf-8')
