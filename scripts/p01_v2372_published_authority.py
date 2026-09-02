from pathlib import Path
import json, re

ROOT=Path('product')
FORMAL='1f5a16796511620760a45cb81b3c8019b91e505b'
FORMAL_TREE='e423df9391c48e4176c041db0f38a32b28c21d44'
RUNTIME='70b627513327aee0a37fae245b0f4042ad69b5a4'
CORE='58e3b69c1ecab7af2de26bcffdcd66eb08bf89f3'
MANIFEST_BLOB='edbf386e6d9c8140d6f2f2cbc4f7c8d3728cc28b'
RELEASE_ID=381010644

published_block="""<!-- P01_V2372_PUBLISHED_PENDING_OWNER_PRODUCTION -->
## V2.37.2 Published · Owner Production V2.37.1 · 2026-09-02

- Owner 实际页面已观察到运行 `V2.37.1`；V2.37.1 Production Closure 因爱一帆移动链接封面兼容缺口而延后，并由 V2.37.2 Hotfix 接续。
- Published Latest：`V2.37.2`；Tag `v2.37.2` 精确绑定 Formal Source `1f5a16796511620760a45cb81b3c8019b91e505b`。
- Formal Tree：`e423df9391c48e4176c041db0f38a32b28c21d44`；Runtime Tree：`70b627513327aee0a37fae245b0f4042ad69b5a4`；Release ID `381010644`。
- UPDATE：`VF_Start_V2.37.2_UPDATE.zip` = `1271430 bytes` / `sha256:ac90582128a0d081b460f9887cb43d5e917ee0da23d4c1d81f1518b6f7b8bb8f`。
- FULL：`601883 bytes` / `sha256:613e224e7585929fb96b41873a8a1c5159b89776d5d1da417d1ee71c5a3186ba`；repair：`3694377 bytes` / `sha256:6dadfbf10efcf18f9b959c0850b6aba200160a5f96f4b75685b71c749cd24d52`。
- Same-token Diagnostic R2 `33596050361`、Focused Hotfix Gate `33596187097`、Stage `33596726377`、Candidate Readiness `33596855241`、Formal Bind `33596932298`、Formal Artifact `33597034240`、Strict Fresh `33597157139`、Release Publish R2 `33597479888`、Manifest Gate `33597620743`：**PASS**。
- Release Publish R1 `33597340771` 在正确创建 Tag 后因 `gh release create` 私有仓读取边界失败；R2 保留正确 Tag，使用 Draft → 8 assets → UPDATE bytes/SHA readback → Stable 的 REST 路径完成发布，未重建冻结 Artifact。
- `core-updates/main = 58e3b69c1ecab7af2de26bcffdcd66eb08bf89f3`；P01 manifest blob `edbf386e6d9c8140d6f2f2cbc4f7c8d3728cc28b`；严格单跳 `V2.37.1 → V2.37.2`，不允许 V2.37.0 跨级。
- 修复语义：用户保存的 `mview.iyf.tv/play/<ID>` URL 不改写；只在封面抓取时临时尝试同 ID 的 `www.iyf.tv/play/<ID>`；浏览器失败重试 revision 为 `v3`。
- Schema `2026082901` 不变，无 Migration；Owner Production 不由 Assistant 写入。
- Current State：**PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION V2.37.1**。
- Next：Owner 在后台执行 `V2.37.1 → V2.37.2`；升级后回读 Current / Latest / History / Footer，并验证 IYF 封面后完成 Production Closure。

> 本段是当前 Release Authority；下面 V2.37.2 Candidate、V2.37.1 Published 与更早段落均为历史证据，冲突时以本段为准。

"""

# README.md Current Truth
p=ROOT/'README.md'; s=p.read_text(encoding='utf-8')
start=s.index('## Current Truth')
end=s.find('\n## ', start+4)
if end<0: end=len(s)
section="""## Current Truth

```text
Owner Production: V2.37.1 (OBSERVED / V2.37.1 closure deferred by IYF bug)
Owner Schema: 2026082901
Published Latest: V2.37.2
Published State: PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION V2.37.1
Formal Source / Tag: 1f5a16796511620760a45cb81b3c8019b91e505b / v2.37.2
Release ID: 381010644
Live Online Update: V2.37.1 -> V2.37.2 ONLY
core-updates main: 58e3b69c1ecab7af2de26bcffdcd66eb08bf89f3
Browser Helper: 1.6.5
Assistant Production Write: NO
```

V2.37.2 已完成 Candidate Readiness、Formal Bind、Formal Artifact、Strict Fresh、Stable GitHub Release 与 core-updates Manifest Gate。正式 UPDATE 已冻结且不得重建。当前等待 Owner 从 V2.37.1 执行在线更新；升级后验证 IYF 移动链接封面并完成 Production Closure。
"""
p.write_text(s[:start]+section+s[end:],encoding='utf-8')

# docs/README.md
p=ROOT/'docs/README.md'; s=p.read_text(encoding='utf-8')
first=s.index('\n## 1. Current Authority')
prefix="""# P01 · VF Start · 文档中心

> Owner Production：`V2.37.1`（Observed；V2.37.1 Closure 被 IYF Hotfix 接续）
> Published Latest：`V2.37.2`
> Schema：`2026082901`
> Release State：`PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION V2.37.1`
> Online Update：`V2.37.1 → V2.37.2 ONLY`
"""
s=prefix+s[first:]
s=s.replace('1. `evidence/P01_V2.37.1_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md` — 当前 Published checkpoint；','1. `evidence/P01_V2.37.2_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md` — 当前 Published checkpoint；')
a=s.index('## 2. Current Release Truth')
b=s.index('\n## 3.',a)
truth="""## 2. Current Release Truth

```text
Owner Production: V2.37.1 (OBSERVED)
Published Latest: V2.37.2
Formal Source: 1f5a16796511620760a45cb81b3c8019b91e505b
Formal Tree: e423df9391c48e4176c041db0f38a32b28c21d44
Runtime Tree: 70b627513327aee0a37fae245b0f4042ad69b5a4
Tag: v2.37.2
Release ID: 381010644
core-updates main: 58e3b69c1ecab7af2de26bcffdcd66eb08bf89f3
Manifest: V2.37.1 -> V2.37.2 ONLY
Assistant Production Write: NO
```
"""
s=s[:a]+truth+s[b:]
p.write_text(s,encoding='utf-8')

# CHANGELOG heading and publication overlay
p=ROOT/'CHANGELOG.md'; s=p.read_text(encoding='utf-8')
s=s.replace('## V2.37.2 · IYF Mobile Cover Fallback Hotfix Candidate · 2026-09-02','## V2.37.2 · IYF Mobile Cover Fallback Hotfix · Published · 2026-09-02',1)
anchor='- Schema 保持 `2026082901`，无 Migration；目标 Atomic 严格为 `V2.37.1 → V2.37.2`。\n'
extra='- Formal Source `1f5a16796511620760a45cb81b3c8019b91e505b`；Release ID `381010644`；Strict Fresh `33597157139` PASS；Release Publish R2 `33597479888` PASS；Manifest Gate `33597620743` PASS。\n- `core-updates/main = 58e3b69c1ecab7af2de26bcffdcd66eb08bf89f3`，在线更新严格 `V2.37.1 → V2.37.2`；Owner Production write = NO。\n'
if extra not in s:
    if anchor not in s: raise SystemExit('changelog anchor missing')
    s=s.replace(anchor,anchor+extra,1)
p.write_text(s,encoding='utf-8')

# CURRENT + HANDOFF: replace candidate block with published block
for rel in ['docs/authority/CURRENT.md','docs/handoff/CURRENT_STATE.md']:
    p=ROOT/rel; s=p.read_text(encoding='utf-8')
    marker='<!-- P01_V2372_RELEASE_CANDIDATE -->'
    if marker not in s: raise SystemExit(f'marker missing {rel}')
    a=s.index(marker); b=s.find('<!-- ',a+len(marker))
    if b<0: raise SystemExit(f'next marker missing {rel}')
    s=s[:a]+published_block+s[b:]
    s=s.replace('> 本段是当前 Release Authority；下面 V2.37.1 Candidate 与 V2.37.0 Production Closure 段落保留历史证据，冲突时以本段为准。','> 本段为 V2.37.1 历史 Published Authority；当前真相以文件顶部 V2.37.2 Published 段为准。')
    p.write_text(s,encoding='utf-8')

# Machine Authority
p=ROOT/'VF_PROJECT.json'; d=json.loads(p.read_text(encoding='utf-8'))
assert d['production_version']=='2.37.1'
assert d['candidate_version']=='2.37.2'
d['status']='V2.37.1 OWNER PRODUCTION OBSERVED / V2.37.2 PUBLISHED / OWNER UPDATE PENDING'
d['working_version']='2.37.2'; d['target_release_version']='2.37.2'
d['current_phase']='V2.37.2 PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION V2.37.1'
d['candidate_state']='PUBLISHED / OWNER PRODUCTION PENDING'
d['formal_release_state']='V2.37.2 PUBLISHED / ONLINE UPDATE AVAILABLE / OWNER PRODUCTION V2.37.1'
d['current_authority']='Owner Production V2.37.1 OBSERVED / Published Latest V2.37.2 / Online Update Available'
d['next_action']='Owner executes V2.37.1 -> V2.37.2 online update; then verify Current/Latest/History/Footer and IYF cover hydration, followed by Production Closure. Do not rebuild frozen release artifacts.'
d['published_release']={
 'version':'2.37.2','tag':'v2.37.2','release_id':RELEASE_ID,'release_source':FORMAL,'release_tree':FORMAL_TREE,'runtime_tree':RUNTIME,
 'schema_version':'2026082901','live_core_updates_commit':CORE,'live_online_next_hop':'2.37.2 / FROM 2.37.1',
 'online_asset':'VF_Start_V2.37.2_UPDATE.zip','online_asset_bytes':1271430,'online_asset_sha256':'ac90582128a0d081b460f9887cb43d5e917ee0da23d4c1d81f1518b6f7b8bb8f',
 'full_asset':'VF-Start-V2.37.2-FULL.zip','full_asset_bytes':601883,'full_asset_sha256':'613e224e7585929fb96b41873a8a1c5159b89776d5d1da417d1ee71c5a3186ba',
 'repair_asset':'repair-v2.37.2.php','repair_asset_bytes':3694377,'repair_asset_sha256':'6dadfbf10efcf18f9b959c0850b6aba200160a5f96f4b75685b71c749cd24d52',
 'release_state':'PUBLISHED / OWNER PRODUCTION PENDING','assistant_production_write':False,
 'same_token_diagnostic':33596050361,'hotfix_gate':33596187097,'stage_gate':33596726377,'candidate_readiness':33596855241,
 'formal_bind_gate':33596932298,'formal_artifact_gate':33597034240,'strict_fresh_gate':33597157139,
 'release_publish_r1':33597340771,'release_publish_r1_classification':'TAG_CREATED_CORRECTLY / GH_RELEASE_CREATE_PRIVATE_READ_BOUNDARY',
 'release_publish_gate':33597479888,'core_updates_manifest_gate':33597620743,'core_updates_promotion_commit':CORE,
 'p01_manifest_blob':MANIFEST_BLOB,'production_closure':'PENDING OWNER UPDATE'
}
c=d['current_change']; c.update({'release_completed':True,'main_write':True,'production_write':False,'formal_source':FORMAL,'formal_tree':FORMAL_TREE,'runtime_tree':RUNTIME,'formal_bind_gate':33596932298,'formal_artifact_gate':33597034240,'strict_fresh_gate':33597157139,'release_publish_r1':33597340771,'release_publish_gate':33597479888,'release_id':RELEASE_ID,'tag':'v2.37.2','core_updates_manifest_gate':33597620743,'core_updates_promotion_commit':CORE})
r=d['v2_37_2_release_candidate']; r.update({'formal_source':FORMAL,'formal_tree':FORMAL_TREE,'runtime_tree':RUNTIME,'formal_bind_gate':33596932298,'formal_artifact_gate':33597034240,'strict_fresh_gate':33597157139,'release_publish_gate':33597479888,'release_id':RELEASE_ID,'core_updates_manifest_gate':33597620743,'core_updates_promotion_commit':CORE,'state':'PUBLISHED / OWNER PRODUCTION PENDING'})
d['authority']['current_formal_release_evidence']='docs/evidence/P01_V2.37.2_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Evidence
p=ROOT/'docs/evidence/P01_V2.37.2_PUBLISHED_PENDING_OWNER_PRODUCTION_20260902.md'
p.write_text(f"""# P01 · VF Start · V2.37.2 Published / Owner Production Pending

- Date: 2026-09-02
- Owner Production Observed: `V2.37.1` / Schema `2026082901`; V2.37.1 closure deferred by IYF mview cover bug.
- Published Latest: `V2.37.2`
- Formal Source: `{FORMAL}`
- Formal Tree: `{FORMAL_TREE}`
- Runtime Tree: `{RUNTIME}`
- Tag: `v2.37.2`
- Release ID: `{RELEASE_ID}` / Stable / 8 frozen assets
- FULL: `601883 bytes` / `sha256:613e224e7585929fb96b41873a8a1c5159b89776d5d1da417d1ee71c5a3186ba`
- UPDATE: `1271430 bytes` / `sha256:ac90582128a0d081b460f9887cb43d5e917ee0da23d4c1d81f1518b6f7b8bb8f`
- repair: `3694377 bytes` / `sha256:6dadfbf10efcf18f9b959c0850b6aba200160a5f96f4b75685b71c749cd24d52`
- Same-token Diagnostic R2: `33596050361` PASS
- Focused Hotfix Gate: `33596187097` PASS
- Stage: `33596726377` PASS
- Candidate Readiness: `33596855241` PASS
- Formal Bind: `33596932298` PASS
- Formal Artifact: `33597034240` PASS / Artifact `9833750309` / outer sha256 `648b10eea296360dd600cf38d8eaf3c5fc4eb2d14a8936be0e03fce28366da9b`
- Strict Fresh: `33597157139` PASS
- Release Publish R1: `33597340771` — correct Tag created, then `gh release create` hit private-repo read boundary; frozen bytes untouched.
- Release Publish R2: `33597479888` PASS — existing exact Tag → Draft Release → 8 frozen assets → UPDATE bytes/SHA readback → Stable.
- Manifest Gate: `33597620743` PASS
- core-updates main: `{CORE}`
- Manifest blob: `{MANIFEST_BLOB}`
- Live Online Update: strict `V2.37.1 → V2.37.2` only; no `V2.37.0 → V2.37.2` cross-grade.
- Schema: `2026082901 → 2026082901`; Migration: NONE.
- Stored IYF URL: unchanged. Metadata-only fallback: `mview.iyf.tv/play/<ID>` → same-ID `www.iyf.tv/play/<ID>` for cover lookup.
- Assistant Production Write: NO.
- Production Closure: PENDING OWNER UPDATE + IYF visual verification.
""",encoding='utf-8')
