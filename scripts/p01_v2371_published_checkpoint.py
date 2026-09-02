from pathlib import Path
import json

root = Path('product')
marker = '<!-- P01_V2371_PUBLISHED_PENDING_OWNER_PRODUCTION -->'
published_block = '''<!-- P01_V2371_PUBLISHED_PENDING_OWNER_PRODUCTION -->
## V2.37.1 Published · Owner Production Pending · 2026-09-02

- Owner Production：`V2.37.0` / Schema `2026082901`；Assistant 未写 Owner Production。
- Published Latest：`V2.37.1`；Tag `v2.37.1` 精确绑定 Formal Source `0838e47ec49bb961131da81b0b314ebf77f1e126`。
- Formal Tree：`bd61c31288dce1e0bf7de28b6980cd075ebc0381`；Runtime Tree：`37f3be264892224e2f3041564844c2aebd471064`；Release ID `380993116`。
- UPDATE：`VF_Start_V2.37.1_UPDATE.zip` = `1270892 bytes` / `sha256:9422135d4f91e937f5fa93ae1aef9a991ae858aa304150a81719547a78cdbd09`。
- FULL：`601679 bytes` / `sha256:679ca8b476f6c67aa2567bfcba3357daf5d88a92a1f81777a72e5d6e7e7440e3`；repair：`3692829 bytes` / `sha256:82ca5edef176d1334080a253280a8eab17532b70f678deae3efe1f9401eb8c0b`。
- Candidate Readiness R2 `33593775142`、Formal Bind `33593861390`、Formal Artifact `33593977785`、Strict Fresh `33594101321`、Release Publish `33594204780`、Manifest Gate R3 `33594521454`：**PASS**。
- `core-updates/main = 1f640592e97a5e670c75cb00cf89adf661f07a16`；P01 manifest blob `87f1fcb80bfc85db9d47b37628bbb093faff27ab`；严格单跳 `V2.37.0 → V2.37.1`，不允许 V2.36.5 跨级。
- V2.37.1 是影视封面补全 Hotfix：支持 lazy-load / JSON-LD 海报候选并刷新浏览器失败重试 revision；Schema 不变，无 Migration。
- Current State：**PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION PENDING**。
- Next：Owner 在后台在线更新页执行 `V2.37.0 → V2.37.1`；升级后做 Fresh Current / Latest / History / Footer 回读并完成 Production Closure。禁止重建已冻结 Artifact。

> 本段是当前 Release Authority；下面 V2.37.1 Candidate 与 V2.37.0 Production Closure 段落保留历史证据，冲突时以本段为准。
'''

for rel in ['docs/authority/CURRENT.md', 'docs/handoff/CURRENT_STATE.md']:
    p = root / rel
    text = p.read_text(encoding='utf-8')
    if marker not in text:
        first_nl = text.find('\n')
        text = text[:first_nl + 1] + '\n' + published_block + '\n' + text[first_nl + 1:]
        p.write_text(text, encoding='utf-8')

(root / 'README.md').write_text('''# P01 · VF Start

VF Start 是单管理员、个人使用优先的**个人互联网资产工作区**。

长期产品定义：

```text
One System
+ One URL/Data Authority
+ One Private Workspace
+ Multiple Resource Domains
```

## Current Truth

```text
Owner Production: V2.37.0
Owner Schema: 2026082901
Published Latest: V2.37.1
Published State: PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION PENDING
Formal Source / Tag: 0838e47ec49bb961131da81b0b314ebf77f1e126 / v2.37.1
Release ID: 380993116
Live Online Update: V2.37.0 -> V2.37.1 ONLY
core-updates main: 1f640592e97a5e670c75cb00cf89adf661f07a16
Browser Helper: 1.6.5
Assistant Production Write: NO
```

V2.37.1 已完成 Candidate Readiness、Formal Bind、Formal Artifact、Strict Fresh、GitHub Release 与 core-updates Manifest Gate。正式 UPDATE 已冻结，不得重建。当前只等待 Owner 从 V2.37.0 执行在线更新；完成后再记录 Production Closure。

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
- Schema = `2026082901`。

## Frontend Contract

**只有一个前台：Functional Workspace。** 匿名与登录态使用同一 Shell；登录只改变可见数据与管理能力，不切换页面系统。`index.php` 是 canonical frontend entry，`start.php` 仅为兼容入口。

## V2.37.1 Hotfix

本补丁针对影视资源自动封面：补充 `data-original / data-src / data-lazy-src / JSON-LD` 等真实海报来源，保留 OpenGraph 优先级，并刷新浏览器失败重试 revision。真实验证覆盖爱壹帆桌面播放页、小宝影院、小黑米、小鸭看看；`mview.iyf.tv` 纯 JS 壳无静态海报元数据仍属于已知边界。

## Current Authority

优先读取：

1. `docs/evidence/P01_V2.37.1_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md` — 当前 Published checkpoint；
2. `docs/authority/CURRENT.md` — Current / 历史 Authority；
3. `docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md` — Functional Contract；
4. `docs/authority/RPD.md` — 产品定义；
5. `docs/authority/SSOT.md` — 工程/数据合同；
6. `docs/authority/ACCEPTANCE_MATRIX.md` — 验收矩阵；
7. `VF_PROJECT.json` — 机器可读 Current Truth；
8. `docs/handoff/CURRENT_STATE.md` — 转窗/接管 Current State。

## Next Boundary

Owner Production 仍为 V2.37.0。下一步仅执行后台在线更新 `V2.37.0 → V2.37.1`；Owner 成功后再做 Production Closure。不要重复已经 PASS 的 Formal Artifact / Strict Fresh / Release Gate。
''', encoding='utf-8')

(root / 'docs/README.md').write_text('''# P01 · VF Start · 文档中心

> Owner Production：`V2.37.0`  
> Published Latest：`V2.37.1`  
> Schema：`2026082901`  
> Release State：`PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION PENDING`  
> Online Update：`V2.37.0 → V2.37.1 ONLY`

## 1. Current Authority · 必读

1. `evidence/P01_V2.37.1_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md` — 当前 Published checkpoint；
2. `authority/CURRENT.md` — Current / 历史 Authority；
3. `authority/P01_FUNCTIONAL_CONTRACT_20260829.md` — Functional Authority；
4. `authority/RPD.md` — 产品定义；
5. `authority/SSOT.md` — 数据、隐私、Domain、Mutation 工程合同；
6. `authority/ACCEPTANCE_MATRIX.md` — 验收矩阵；
7. `../VF_PROJECT.json` — 机器可读 Current Truth；
8. `handoff/CURRENT_STATE.md` — 当前接管状态。

## 2. Current Release Truth

```text
Owner Production: V2.37.0
Published Latest: V2.37.1
Formal Source: 0838e47ec49bb961131da81b0b314ebf77f1e126
Formal Tree: bd61c31288dce1e0bf7de28b6980cd075ebc0381
Runtime Tree: 37f3be264892224e2f3041564844c2aebd471064
Tag: v2.37.1
Release ID: 380993116
core-updates main: 1f640592e97a5e670c75cb00cf89adf661f07a16
Manifest: V2.37.0 -> V2.37.1 ONLY
Assistant Production Write: NO
```

## 3. V2.37.1 Gate Chain

- Hotfix R2 `33591609518` PASS；
- 四站诊断 `33592368667` PASS；
- 详情诊断 `33592546995` PASS；
- Stage `33593456078` PASS；
- Candidate Readiness R2 `33593775142` PASS；
- Formal Bind `33593861390` PASS；
- Formal Artifact `33593977785` PASS；
- Strict Fresh `33594101321` PASS；
- Release Publish `33594204780` PASS；
- Manifest Gate R3 `33594521454` PASS。

R1/R2 的 Manifest 失败仅是跨私有仓 Token Harness 问题；candidate Manifest 内容没有改变，R3 完整回读 Release UPDATE bytes/SHA 后 PASS。

## 4. Product Model

`ONE SYSTEM + ONE URL/DATA AUTHORITY + ONE PRIVATE WORKSPACE + MULTIPLE RESOURCE DOMAINS`

唯一前台是 Functional Workspace；匿名与登录态共用同一 Shell。资源域为 `首页 / 导航 / 频道 / 影视 / 专题`。

## 5. Release Boundary

V2.37.1 的 Tag / Stable Release / FULL / UPDATE / repair / core-updates 已完成并冻结。**不得重建正式 Artifact，不得改写 Tag/Release。** Owner Production 仍为 V2.37.0，Assistant 不直接写 Production。

## 6. Next

Owner 在 VF Start 后台在线更新页执行 `V2.37.0 → V2.37.1`。成功后提供或回读 Current / Latest / Update History / Footer，再完成 V2.37.1 Production Closure，并回到 L2 Product Optimization。
''', encoding='utf-8')

changelog = root / 'CHANGELOG.md'
ct = changelog.read_text(encoding='utf-8')
cm = '<!-- P01_V2371_PUBLISHED_CHANGELOG -->'
if cm not in ct:
    first_nl = ct.find('\n')
    section = '''
<!-- P01_V2371_PUBLISHED_CHANGELOG -->
## V2.37.1 · Published · 2026-09-02

- 影视封面补全 Hotfix：支持 lazy-load 属性与 JSON-LD 海报候选，保留 OpenGraph 优先；浏览器失败重试 revision 刷新。
- 真实影视源诊断覆盖爱壹帆桌面播放页、小宝影院、小黑米、小鸭看看；已知边界：`mview.iyf.tv` 纯 JS 壳无静态海报元数据。
- Formal Source `0838e47ec49bb961131da81b0b314ebf77f1e126`；Tag `v2.37.1`；Release `380993116`。
- Frozen UPDATE `1270892 bytes` / `sha256:9422135d4f91e937f5fa93ae1aef9a991ae858aa304150a81719547a78cdbd09`。
- `core-updates` 严格单跳 `V2.37.0 → V2.37.1`；Schema `2026082901` 不变，无 Migration。
- Owner Production 尚为 V2.37.0；Production Closure 待 Owner 在线更新后完成。
'''
    ct = ct[:first_nl + 1] + section + '\n' + ct[first_nl + 1:]
    changelog.write_text(ct, encoding='utf-8')

evidence = '''# P01 · VF Start · V2.37.1 Published / Owner Production Pending

Date: 2026-09-02

## Current Truth

- Owner Production: `V2.37.0`
- Owner Schema: `2026082901`
- Published Latest: `V2.37.1`
- State: `PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION PENDING`
- Assistant Production Write: `NO`

## Formal Identity

- Formal Source: `0838e47ec49bb961131da81b0b314ebf77f1e126`
- Formal Tree: `bd61c31288dce1e0bf7de28b6980cd075ebc0381`
- Runtime Tree: `37f3be264892224e2f3041564844c2aebd471064`
- Tag: `v2.37.1`
- Release ID: `380993116`

## Frozen Assets

- UPDATE: `VF_Start_V2.37.1_UPDATE.zip` / `1270892 bytes` / `9422135d4f91e937f5fa93ae1aef9a991ae858aa304150a81719547a78cdbd09`
- FULL: `VF-Start-V2.37.1-FULL.zip` / `601679 bytes` / `679ca8b476f6c67aa2567bfcba3357daf5d88a92a1f81777a72e5d6e7e7440e3`
- repair: `repair-v2.37.1.php` / `3692829 bytes` / `82ca5edef176d1334080a253280a8eab17532b70f678deae3efe1f9401eb8c0b`
- Formal Artifact Run: `33593977785`
- Outer Artifact Digest: `97b2b5e5c3aef27c62eca113a9ac20f23eeb6106104ecf606c85bc92c58cd963`

## Gates

- Hotfix R1 `33591472844`: harness-only workflow config failure; no product write.
- Hotfix R2 `33591609518`: PASS.
- Four-site diagnostic `33592368667`: PASS.
- Detail-level diagnostic `33592546995`: PASS.
- Stage `33593456078`: PASS.
- Candidate Readiness R1 `33593631445`: harness-only evidence-directory failure before product gates.
- Candidate Readiness R2 `33593775142`: PASS.
- Formal Bind `33593861390`: PASS.
- Formal Artifact `33593977785`: PASS.
- Strict Fresh `33594101321`: PASS.
- Release Publish `33594204780`: PASS.
- Manifest Gate R1 `33594358584`: harness-only core-updates cross-repo auth failure before assertions.
- Manifest Gate R2 `33594456329`: Manifest content boundary PASS; Release API cross-repo auth harness failure.
- Manifest Gate R3 `33594521454`: PASS.

## Online Update Authority

- `core-updates/main`: `1f640592e97a5e670c75cb00cf89adf661f07a16`
- P01 Manifest blob: `87f1fcb80bfc85db9d47b37628bbb093faff27ab`
- Current: `2.37.0`
- Target: `2.37.1`
- Allowed from_versions: `[2.37.0]`
- Cross-grade from `2.36.5`: `NO`
- Schema change: `NO`
- Migration: `NONE`

## Next

Owner executes the VF Start online update `V2.37.0 → V2.37.1`. After success, record Fresh Current / Latest / History / Footer evidence and create the V2.37.1 Owner Production Closure. Do not rebuild or replace the frozen release assets.
'''
(root / 'docs/evidence/P01_V2.37.1_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md').write_text(evidence, encoding='utf-8')

jp = root / 'VF_PROJECT.json'
data = json.loads(jp.read_text(encoding='utf-8'))
data['status'] = 'V2.37.0 OWNER PRODUCTION / V2.37.1 PUBLISHED / OWNER UPDATE PENDING'
data['production_version'] = '2.37.0'
data['working_version'] = '2.37.1'
data['target_release_version'] = '2.37.1'
data['schema_version'] = '2026082901'
data['working_schema_version'] = '2026082901'
data['current_phase'] = 'V2.37.1 PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION PENDING'
data['published_release'] = {
    'version': '2.37.1',
    'tag': 'v2.37.1',
    'release_id': 380993116,
    'release_source': '0838e47ec49bb961131da81b0b314ebf77f1e126',
    'release_tree': 'bd61c31288dce1e0bf7de28b6980cd075ebc0381',
    'runtime_tree': '37f3be264892224e2f3041564844c2aebd471064',
    'schema_version': '2026082901',
    'live_core_updates_commit': '1f640592e97a5e670c75cb00cf89adf661f07a16',
    'live_online_next_hop': '2.37.1 / FROM 2.37.0',
    'online_asset': 'VF_Start_V2.37.1_UPDATE.zip',
    'online_asset_bytes': 1270892,
    'online_asset_sha256': '9422135d4f91e937f5fa93ae1aef9a991ae858aa304150a81719547a78cdbd09',
    'full_asset': 'VF-Start-V2.37.1-FULL.zip',
    'full_asset_bytes': 601679,
    'full_asset_sha256': '679ca8b476f6c67aa2567bfcba3357daf5d88a92a1f81777a72e5d6e7e7440e3',
    'repair_asset': 'repair-v2.37.1.php',
    'repair_asset_bytes': 3692829,
    'repair_asset_sha256': '82ca5edef176d1334080a253280a8eab17532b70f678deae3efe1f9401eb8c0b',
    'release_state': 'PUBLISHED / OWNER PRODUCTION PENDING',
    'assistant_production_write': False,
    'stage_gate': 33593456078,
    'candidate_readiness': 33593775142,
    'formal_bind_gate': 33593861390,
    'formal_artifact_gate': 33593977785,
    'strict_fresh_gate': 33594101321,
    'release_publish_gate': 33594204780,
    'core_updates_manifest_gate': 33594521454,
    'core_updates_promotion_commit': '1f640592e97a5e670c75cb00cf89adf661f07a16',
    'p01_manifest_blob': '87f1fcb80bfc85db9d47b37628bbb093faff27ab',
    'production_closure': 'PENDING OWNER UPDATE'
}
cc = data.setdefault('current_change', {})
cc.update({
    'formal_source': '0838e47ec49bb961131da81b0b314ebf77f1e126',
    'formal_tree': 'bd61c31288dce1e0bf7de28b6980cd075ebc0381',
    'runtime_tree': '37f3be264892224e2f3041564844c2aebd471064',
    'formal_bind_gate': 33593861390,
    'formal_artifact_gate': 33593977785,
    'strict_fresh_gate': 33594101321,
    'release_publish_gate': 33594204780,
    'release_id': 380993116,
    'tag': 'v2.37.1',
    'core_updates_manifest_gate': 33594521454,
    'core_updates_promotion_commit': '1f640592e97a5e670c75cb00cf89adf661f07a16',
    'main_write': True,
    'production_write': False,
    'release_completed': True
})
auth = data.setdefault('authority', {})
auth['current_formal_release_evidence'] = 'docs/evidence/P01_V2.37.1_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md'
auth['current_production_evidence'] = 'docs/evidence/P01_V2.37.0_OWNER_PRODUCTION_CLOSURE_20260902.md'
data['candidate_version'] = '2.37.1'
data['candidate_schema_version'] = '2026082901'
data['candidate_state'] = 'PUBLISHED / OWNER PRODUCTION PENDING'
data['formal_release_state'] = 'V2.37.1 PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION PENDING'
data['current_authority'] = 'Owner Production V2.37.0 / Published Latest V2.37.1 / Online Update Available'
data['next_action'] = 'Owner executes V2.37.0 -> V2.37.1 online update; after Fresh readback, record Production Closure. Do not rebuild frozen release artifacts.'
data['published_release_checkpoint'] = {
    'date': '2026-09-02',
    'owner_production': '2.37.0',
    'published_latest': '2.37.1',
    'formal_source': '0838e47ec49bb961131da81b0b314ebf77f1e126',
    'release_id': 380993116,
    'manifest_gate': 33594521454,
    'core_updates_main': '1f640592e97a5e670c75cb00cf89adf661f07a16',
    'manifest_blob': '87f1fcb80bfc85db9d47b37628bbb093faff27ab',
    'online_path': '2.37.0 -> 2.37.1 only',
    'schema_change': False,
    'migration': None,
    'assistant_production_write': False,
    'owner_production_pending': True
}
jp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
