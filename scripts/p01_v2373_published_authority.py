from pathlib import Path
import json

ROOT=Path('product')
FORMAL='cec95e310771feb6813a51c7ee3340884295ee38'
FORMAL_TREE='8fc025e93aaf730414e70a3fcbdc6d43fe954653'
RUNTIME='e56459ebadc120c749cc5336821d762001db5218'
CORE='dac1d05f3273daa7760b2f1820163df21116a145'
MANIFEST_BLOB='4ec59b3d30f632d73745ba7a81f58e4a73ea459f'
RELEASE_ID=381039491
UPDATE_SHA='8042c324e59136a70893b9cc839569f3fbcbbaa7184c3855e0b81c37b9556e75'
FULL_SHA='448b86a7a4abc375470dfa0159ef31c85e4ae471a7712ddf0a813dbc8accd1af'
REPAIR_SHA='e3e25a750a544b0f01c22809ebcb151433d84ae30d59b6a94d9253b56c9c0a74'

block=f'''<!-- P01_V2373_PUBLISHED_PENDING_OWNER_PRODUCTION -->
## V2.37.3 Published · Owner Production V2.37.2 · 2026-09-02

- Owner 已实测运行 `V2.37.2` / Schema `2026082901`；更新页 Current/Latest 均为 V2.37.2，但 IYF 封面仍缺失，因此 V2.37.2 Production Closure 被 V2.37.3 接续，不标记 PASS。
- Published Latest：`V2.37.3`；Tag `v2.37.3` 精确绑定 Formal Source `{FORMAL}`。
- Formal Tree：`{FORMAL_TREE}`；Runtime Tree：`{RUNTIME}`；Release ID `{RELEASE_ID}`。
- UPDATE：`VF_Start_V2.37.3_UPDATE.zip` = `1271655 bytes` / `sha256:{UPDATE_SHA}`。
- FULL：`601957 bytes` / `sha256:{FULL_SHA}`；repair：`3694733 bytes` / `sha256:{REPAIR_SHA}`。
- Focused Hotfix Gate R3 `33600058990`、Stage `33600341324`、Candidate Readiness `33600570356`、Formal Bind `33600694106`、Formal Artifact `33600796537`、Strict Fresh R2 `33601748436`、Release Publish `33601937056`、Manifest Gate `33602093093`：**PASS**。
- Strict Fresh R1 `33601613222` 为 Harness-only：已安装 Fresh 环境被再次交给期待未安装环境的 setup helper；冻结 FULL、真实 Atomic 与数据保留均已先通过，R2 仅隔离测试环境且不重建字节。
- Frozen FULL 内真实 IYF E2E：三条独立资源首次自动封面 `3/3 PASS`；`resource-cover.php` 实际输出 `3/3 PASS`。
- `core-updates/main = {CORE}`；P01 manifest blob `{MANIFEST_BLOB}`；严格单跳 `V2.37.2 → V2.37.3`，不允许 V2.37.1 跨级。
- 修复语义：远程自动封面在文件魔数、尺寸与有效图片校验后安全接受 GIF；手动封面上传仍仅 PNG/JPG/WebP；失败重试 revision 为 `v4`；不改用户保存 URL，不改数据库。
- Schema `2026082901` 不变，无 Migration；Owner Production 不由 Assistant 写入。
- Current State：**PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION V2.37.2**。
- Next：Owner 在后台执行 `V2.37.2 → V2.37.3`；升级后必须同时验证 Current/Latest/History/Footer 与真实 IYF 封面，才允许 Production Closure。

> 本段是当前 Release Authority；下面 V2.37.3 Candidate、V2.37.2 Published 与更早段落均为历史证据，冲突时以本段为准。

'''

# README current truth
p=ROOT/'README.md'; s=p.read_text(encoding='utf-8')
a=s.index('## Current Truth'); b=s.index('\n## Product Structure',a)
section=f'''## Current Truth

```text
Owner Production: V2.37.2 (OBSERVED / closure deferred by IYF GIF bug)
Owner Schema: 2026082901
Published Latest: V2.37.3
Published State: PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION V2.37.2
Formal Source / Tag: {FORMAL} / v2.37.3
Release ID: {RELEASE_ID}
Live Online Update: V2.37.2 -> V2.37.3 ONLY
core-updates main: {CORE}
Browser Helper: 1.6.5
Assistant Production Write: NO
```

V2.37.3 已完成真实 IYF 首刷 3/3 E2E、Candidate Readiness、Formal Bind、Formal Artifact、Strict Fresh R2、Stable GitHub Release 与 core-updates Manifest Gate。正式 UPDATE 已冻结且不得重建。当前等待 Owner 从 V2.37.2 在线更新，并以真实 IYF 封面加载结果作为 Production Closure 必要证据。
'''
p.write_text(s[:a]+section+s[b:],encoding='utf-8')

# docs README is a current index; rewrite compactly
p=ROOT/'docs/README.md'
p.write_text(f'''# P01 · VF Start · 文档中心

> Owner Production：`V2.37.2`（Observed；Closure 被 IYF GIF Hotfix 接续）
> Published Latest：`V2.37.3`
> Schema：`2026082901`
> Release State：`PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION V2.37.2`
> Online Update：`V2.37.2 → V2.37.3 ONLY`

## 1. Current Authority · 必读

1. `evidence/P01_V2.37.3_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md` — 当前 Published checkpoint；
2. `authority/CURRENT.md` — Current / 历史 Authority；
3. `authority/P01_FUNCTIONAL_CONTRACT_20260829.md` — Functional Authority；
4. `authority/RPD.md` — 产品定义；
5. `authority/SSOT.md` — 数据、隐私、Domain、Mutation 工程合同；
6. `authority/ACCEPTANCE_MATRIX.md` — 验收矩阵；
7. `../VF_PROJECT.json` — 机器可读 Current Truth；
8. `handoff/CURRENT_STATE.md` — 当前接管状态。

## 2. Current Release Truth

```text
Owner Production: V2.37.2 (OBSERVED)
Published Latest: V2.37.3
Formal Source: {FORMAL}
Formal Tree: {FORMAL_TREE}
Runtime Tree: {RUNTIME}
Tag: v2.37.3
Release ID: {RELEASE_ID}
core-updates main: {CORE}
Manifest: V2.37.2 -> V2.37.3 ONLY
Assistant Production Write: NO
```

## 3. V2.37.3 Gate Chain

- Focused Hotfix Gate R3 `33600058990` PASS；
- Stage `33600341324` PASS；
- Candidate Readiness `33600570356` PASS；
- Formal Bind `33600694106` PASS；
- Formal Artifact `33600796537` PASS；
- Strict Fresh R1 `33601613222` Harness-only；Strict Fresh R2 `33601748436` PASS；
- Release Publish `33601937056` PASS；
- Manifest Gate `33602093093` PASS。

冻结 FULL 内真实 IYF 首次自动封面 `3/3 PASS`，`resource-cover.php` 输出 `3/3 PASS`。R1 仅为测试环境重复 setup，不涉及产品或冻结字节失败。

## 4. Product Model

`ONE SYSTEM + ONE URL/DATA AUTHORITY + ONE PRIVATE WORKSPACE + MULTIPLE RESOURCE DOMAINS`

唯一前台是 Functional Workspace；匿名与登录态共用同一 Shell。资源域为 `首页 / 导航 / 频道 / 影视 / 专题`。

## 5. Release Boundary

V2.37.3 的 Tag / Stable Release / FULL / UPDATE / repair / core-updates 已完成并冻结。**不得重建正式 Artifact，不得改写 Tag/Release。** Owner Production 仍为 V2.37.2，Assistant 不直接写 Production。

## 6. Next

Owner 在 VF Start 后台执行 `V2.37.2 → V2.37.3`。升级后不仅核对 Current / Latest / Update History / Footer，还必须验证真实 IYF 影视封面已经出现；两类证据都满足后再完成 V2.37.3 Production Closure。
''',encoding='utf-8')

# changelog publish overlay
p=ROOT/'CHANGELOG.md'; s=p.read_text(encoding='utf-8')
s=s.replace('## V2.37.3 · IYF GIF Auto-cover Hotfix Candidate · 2026-09-02','## V2.37.3 · IYF GIF Auto-cover Hotfix · Published · 2026-09-02',1)
anchor='- Schema 保持 `2026082901`，无 Migration；目标 Atomic 严格为 `V2.37.2 → V2.37.3`。\n'
extra=f'- Formal Source `{FORMAL}`；Release ID `{RELEASE_ID}`；Strict Fresh R2 `33601748436` PASS；Release Publish `33601937056` PASS；Manifest Gate `33602093093` PASS。\n- 冻结 FULL 内真实 IYF 首刷 `3/3 PASS`，`resource-cover.php` 输出 `3/3 PASS`；`core-updates/main = {CORE}`，在线更新严格 `V2.37.2 → V2.37.3`。\n'
if extra not in s:
    assert anchor in s
    s=s.replace(anchor,anchor+extra,1)
p.write_text(s,encoding='utf-8')

# current/handoff: replace top candidate block only
for rel in ['docs/authority/CURRENT.md','docs/handoff/CURRENT_STATE.md']:
    p=ROOT/rel; s=p.read_text(encoding='utf-8')
    a=s.index('<!-- P01_V2373_RELEASE_CANDIDATE -->')
    b=s.index('<!-- P01_V2372_PUBLISHED_PENDING_OWNER_PRODUCTION -->',a)
    s=s[:a]+block+s[b:]
    p.write_text(s,encoding='utf-8')

# machine authority
p=ROOT/'VF_PROJECT.json'; d=json.loads(p.read_text(encoding='utf-8'))
assert d['production_version']=='2.37.2'
d['status']='V2.37.2 OWNER PRODUCTION OBSERVED / V2.37.3 PUBLISHED / OWNER UPDATE PENDING'
d['working_version']='2.37.3'; d['target_release_version']='2.37.3'; d['candidate_version']='2.37.3'
d['current_phase']='V2.37.3 PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION V2.37.2'
d['candidate_state']='PUBLISHED / OWNER PRODUCTION PENDING'
d['formal_release_state']='V2.37.3 PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION V2.37.2'
d['current_authority']='Owner Production V2.37.2 OBSERVED / Published Latest V2.37.3 / Online Update Available'
d['next_action']='Owner executes V2.37.2 -> V2.37.3 online update; then verify Current/Latest/History/Footer and real IYF cover hydration before Production Closure. Do not rebuild frozen release artifacts.'
d['published_release']={
 'version':'2.37.3','tag':'v2.37.3','release_id':RELEASE_ID,'release_source':FORMAL,'release_tree':FORMAL_TREE,'runtime_tree':RUNTIME,
 'schema_version':'2026082901','live_core_updates_commit':CORE,'live_online_next_hop':'2.37.3 / FROM 2.37.2',
 'online_asset':'VF_Start_V2.37.3_UPDATE.zip','online_asset_bytes':1271655,'online_asset_sha256':UPDATE_SHA,
 'full_asset':'VF-Start-V2.37.3-FULL.zip','full_asset_bytes':601957,'full_asset_sha256':FULL_SHA,
 'repair_asset':'repair-v2.37.3.php','repair_asset_bytes':3694733,'repair_asset_sha256':REPAIR_SHA,
 'release_state':'PUBLISHED / OWNER PRODUCTION PENDING','assistant_production_write':False,
 'hotfix_gate':33600058990,'stage_gate':33600341324,'candidate_readiness':33600570356,'formal_bind_gate':33600694106,
 'formal_artifact_gate':33600796537,'strict_fresh_r1':33601613222,'strict_fresh_r1_classification':'HARNESS_ONLY_ALREADY_INSTALLED_SETUP_REUSE',
 'strict_fresh_gate':33601748436,'release_publish_gate':33601937056,'core_updates_manifest_gate':33602093093,
 'core_updates_promotion_commit':CORE,'p01_manifest_blob':MANIFEST_BLOB,'production_closure':'PENDING OWNER UPDATE AND REAL IYF COVER VERIFICATION'
}
c=d['current_change']; c.update({'release_completed':True,'main_write':True,'production_write':False,'formal_source':FORMAL,'formal_tree':FORMAL_TREE,'runtime_tree':RUNTIME,'formal_bind_gate':33600694106,'formal_artifact_gate':33600796537,'strict_fresh_r1':33601613222,'strict_fresh_gate':33601748436,'release_publish_gate':33601937056,'release_id':RELEASE_ID,'tag':'v2.37.3','core_updates_manifest_gate':33602093093,'core_updates_promotion_commit':CORE})
d['v2_37_3_release_candidate']={'state':'PUBLISHED / OWNER PRODUCTION PENDING','formal_source':FORMAL,'formal_tree':FORMAL_TREE,'runtime_tree':RUNTIME,'schema_change':False,'migration':None,'hotfix_gate':33600058990,'candidate_readiness':33600570356,'formal_bind_gate':33600694106,'formal_artifact_gate':33600796537,'strict_fresh_gate':33601748436,'release_publish_gate':33601937056,'release_id':RELEASE_ID,'core_updates_manifest_gate':33602093093,'core_updates_promotion_commit':CORE}
d['authority']['current_formal_release_evidence']='docs/evidence/P01_V2.37.3_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# evidence
p=ROOT/'docs/evidence/P01_V2.37.3_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md'
p.write_text(f'''# P01 · VF Start · V2.37.3 Published / Owner Production Pending

- Date: 2026-09-02
- Owner Production Observed: `V2.37.2` / Schema `2026082901`; update page Current=Latest=V2.37.2, but IYF covers remained absent, so V2.37.2 Closure was deferred.
- Owner screenshot: `1319×641` / SHA-256 `74a110f575530beb0c678822742babfca6adf2cffbd5215feccc861eadf44502`.
- Published Latest: `V2.37.3`
- Formal Source: `{FORMAL}`
- Formal Tree: `{FORMAL_TREE}`
- Runtime Tree: `{RUNTIME}`
- Tag: `v2.37.3`
- Release ID: `{RELEASE_ID}` / Stable / 8 frozen assets
- FULL: `601957 bytes` / `sha256:{FULL_SHA}`
- UPDATE: `1271655 bytes` / `sha256:{UPDATE_SHA}`
- repair: `3694733 bytes` / `sha256:{REPAIR_SHA}`
- Focused Hotfix Gate R3: `33600058990` PASS
- Stage: `33600341324` PASS
- Candidate Readiness: `33600570356` PASS
- Formal Bind: `33600694106` PASS
- Formal Artifact: `33600796537` PASS / Artifact `9835093365`
- Strict Fresh R1: `33601613222` Harness-only (already-installed setup reuse); frozen package install/atomic was not the failure.
- Strict Fresh R2: `33601748436` PASS; frozen FULL IYF first-attempt `3/3 PASS`, `resource-cover.php` `3/3 PASS`.
- Release Publish: `33601937056` PASS
- Manifest Gate: `33602093093` PASS
- core-updates main: `{CORE}`
- P01 manifest blob: `{MANIFEST_BLOB}`
- Online update: `V2.37.2 → V2.37.3 ONLY`; no cross-hop from V2.37.1.
- Schema: `2026082901 → 2026082901`; Migration: none.
- Owner Production write by Assistant: `NO`.
- Production Closure: `PENDING OWNER UPDATE + REAL IYF COVER VERIFICATION`.
''',encoding='utf-8')
