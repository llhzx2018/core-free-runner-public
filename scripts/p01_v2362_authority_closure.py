from pathlib import Path
import json,re

root=Path('.')

evidence='''# P01 · VF Start · V2.36.2 Release Closure Evidence

## Verdict

**PASS / PUBLISHED / SEQUENTIAL ONLINE UPGRADE PATH PRESERVED**

Owner Production remains **V2.36.0** / Schema **2026082901**. This release closure did **not** write Owner Production.

V2.36.2 is formally published, but its Atomic updater is intentionally strict **V2.36.1 → V2.36.2**. Because Owner Production is still V2.36.0, the live core-updates manifest continues to offer the safe V2.36.0 → V2.36.1 hop. The V2.36.2 manifest is validated and staged, but is not promoted until Owner Production reaches V2.36.1.

## Exact Release Identity

- Formal Source: `4fd25a5ce4383dc456e755fc2e031a861d6ff655`
- Formal Tree: `0f0e5329098ad5a87a4a72dbd368c88d7a44b339`
- Runtime Tree: `55bc3143df6ca4e8e66b3e8d3e0f01b3ec343424`
- Schema: `2026082901`
- Migration: `NONE`
- Tag: `v2.36.2`
- GitHub Release ID: `380317968`
- Live core-updates main: `416cc8089b39349eb7ee62638b5267335d406320` → safe next hop V2.36.1
- V2.36.2 manifest candidate: `3ddf344872744ba4e9e407c99fe704b90a4cda97`

## Release Assets

- `VF-Start-V2.36.2-FULL.zip`: `649250` bytes / `sha256:4a2defd88b5e25d8a5a431dfa00a23cea9370d9ea4f0f68255e483b25f2ff90c`
- `VF_Start_V2.36.2_UPDATE.zip`: `1396364` bytes / `sha256:1718db148ea91987a8b3dee2474892b3df84b4b93cd8298e2e261153fa99c3ea`
- `repair-v2.36.2.php`: `4024813` bytes / `sha256:70f1221555b2d318081bead944ff1912f6e5ec9b919a2e340fb490614e33e797`

## Gate Chain

- Product Auth Entry Gate `33477309212` — PASS
- Candidate Readiness `33478737169` — PASS
- Formal Bind `33479052985` — PASS
- Formal Artifact `33485021418` — PASS
- Strict Fresh `33485364786` — PASS
- Main Promotion `33485493941` — PASS
- Publication `33485613966` — PASS
- V2.36.2 core-updates Candidate `33486145556` — PASS / PROMOTION HELD BY OWNER VERSION
- Remote Release Truth `33486270599` — PASS

## Remote Truth Evidence

Remote Release Truth Artifact `9791880245` / `sha256:be76242d0793329d913e8f3ab141c9f8e5bf0ad3f38a36bc0ced7ae4119618e2`.

The remote gate independently confirmed `vf-start/main`, tag `v2.36.2`, Release `380317968`, all release asset hashes/sizes, the live V2.36.0 → V2.36.1 core-updates authority, the staged V2.36.1 → V2.36.2 manifest candidate, and unchanged Runner main.

## Product Contract

V2.36.2 fixes the real login/logout visibility gap while preserving the single-frontend authentication model:

- anonymous users see public resources and a visible Login entry;
- after login, the same frontend shows public + private resources, management entry and visible Logout;
- after logout, the same route returns to public-only state;
- no administrator/public-preview dual-view subsystem was reintroduced.

## Production Boundary / Next Hop

- Owner Production before/after this closure: `V2.36.0`
- Published Latest: `V2.36.2`
- Live online safe next hop for current Owner Production: `V2.36.1`
- V2.36.2 Manifest Candidate: `READY`, promotion intentionally held until Owner reaches V2.36.1
- Assistant Owner Production write: `NO`
- Next: Owner performs V2.36.0 → V2.36.1 using the existing live online updater. After Owner readback confirms V2.36.1, promote the validated V2.36.2 manifest candidate and then perform the V2.36.1 → V2.36.2 Owner update/closure.
'''
(root/'docs/evidence/P01_V2.36.2_RELEASE_CLOSURE_20260901.md').write_text(evidence,encoding='utf-8')

section='''<!-- P01_V2362_RELEASE_CLOSURE -->
## V2.36.2 Release Closure · 2026-09-01

- Owner Production：`V2.36.0` / Schema `2026082901` / previous Production Closure PASS。
- Published Latest：`V2.36.2`。
- Formal Source：`4fd25a5ce4383dc456e755fc2e031a861d6ff655`；Runtime Tree：`55bc3143df6ca4e8e66b3e8d3e0f01b3ec343424`。
- Tag / Release：`v2.36.2` / `380317968`。
- Formal Artifact Gate：`33485021418` = PASS；Strict Fresh：`33485364786` = PASS；Publication：`33485613966` = PASS。
- Remote Release Truth：`33486270599` = **PASS**；Artifact `9791880245`；Digest `sha256:be76242d0793329d913e8f3ab141c9f8e5bf0ad3f38a36bc0ced7ae4119618e2`。
- V2.36.2 Atomic 仅支持 `V2.36.1 → V2.36.2`；当前 Owner Production 仍为 V2.36.0，因此 live core-updates 继续保留 `V2.36.0 → V2.36.1`：`416cc8089b39349eb7ee62638b5267335d406320`。
- V2.36.2 Manifest Candidate：`3ddf344872744ba4e9e407c99fe704b90a4cda97`；Gate `33486145556` = PASS；**待 Owner 到 V2.36.1 后再晋级**。
- 登录模型：一个前台；匿名公开 + Login；登录后公开 + 私人 + 管理 + Logout；退出恢复公开；未重新引入双视角。
- Assistant Production Write：**NO**。
- Next：Owner 先执行 V2.36.0 → V2.36.1；回读确认后再晋级 V2.36.2 Manifest，并完成第二跳 Owner 更新。

> 以下旧段落保留历史证据；如与本段冲突，以本段为 Current Release Authority。

'''
for rel,title in [('docs/authority/CURRENT.md','# P01 · VF Start · Current Authority\n\n'),('docs/handoff/CURRENT_STATE.md','# CURRENT STATE · P01 VF Start\n\n')]:
    p=root/rel;s=p.read_text(encoding='utf-8')
    if not s.startswith(title): raise SystemExit(f'unexpected header: {rel}')
    p.write_text(title+section+s[len(title):],encoding='utf-8')

readme=root/'README.md';s=readme.read_text(encoding='utf-8')
replacement='''## Current Truth

```text
Owner Production: V2.36.0
Owner Schema: 2026082901
Published Latest: V2.36.2
Formal Release Source: 4fd25a5ce4383dc456e755fc2e031a861d6ff655
Formal Release Tree: 0f0e5329098ad5a87a4a72dbd368c88d7a44b339
Runtime src Tree: 55bc3143df6ca4e8e66b3e8d3e0f01b3ec343424
Tag: v2.36.2
GitHub Release ID: 380317968
Live Online Next Hop: V2.36.1
Live core-updates: 416cc8089b39349eb7ee62638b5267335d406320
V2.36.2 Manifest Candidate: 3ddf344872744ba4e9e407c99fe704b90a4cda97 / PASS / HELD
Remote Release Truth Gate: 33486270599 / PASS
Owner Production Closure: V2.36.0 / PASS
Assistant Production Write: NO
```

V2.36.2 已正式发布并通过 Formal Artifact、Strict Fresh、Main Promotion、Publication 与 Remote Release Truth Gate。由于 V2.36.2 Atomic 严格从 V2.36.1 起跳，而真实 Owner Production 仍是 V2.36.0，在线更新保持安全的顺序升级：当前 live manifest 先提供 V2.36.0 → V2.36.1；V2.36.2 manifest 已验证并暂存，待 Owner 到 V2.36.1 后再晋级。

'''
s2,n=re.subn(r'## Current Truth\n.*?(?=## Product Structure)',replacement,s,flags=re.S)
if n!=1: raise SystemExit(f'Current Truth section replace count={n}')
if 'docs/evidence/P01_V2.36.2_RELEASE_CLOSURE_20260901.md' not in s2:
    marker='## Product Structure'
    s2=s2.replace(marker,'Release evidence: [`docs/evidence/P01_V2.36.2_RELEASE_CLOSURE_20260901.md`](docs/evidence/P01_V2.36.2_RELEASE_CLOSURE_20260901.md)\n\n'+marker,1)
readme.write_text(s2,encoding='utf-8')

p=root/'VF_PROJECT.json';d=json.loads(p.read_text(encoding='utf-8'))
d['status']='V2.36.0 OWNER PRODUCTION / V2.36.2 PUBLISHED / SEQUENTIAL ONLINE UPGRADE'
d['production_version']='2.36.0';d['working_version']='2.36.2';d['target_release_version']='2.36.2'
d['current_phase']='V2.36.2 PUBLISHED / OWNER MUST COMPLETE V2.36.1 HOP FIRST'
d['published_release']={
 'version':'2.36.2','tag':'v2.36.2','release_id':380317968,
 'release_source':'4fd25a5ce4383dc456e755fc2e031a861d6ff655','release_tree':'0f0e5329098ad5a87a4a72dbd368c88d7a44b339','runtime_tree':'55bc3143df6ca4e8e66b3e8d3e0f01b3ec343424','schema_version':'2026082901',
 'live_core_updates_commit':'416cc8089b39349eb7ee62638b5267335d406320','live_online_next_hop':'2.36.1',
 'v2_36_2_manifest_candidate':'3ddf344872744ba4e9e407c99fe704b90a4cda97','manifest_candidate_state':'PASS / HELD UNTIL OWNER V2.36.1',
 'online_asset':'VF_Start_V2.36.2_UPDATE.zip','online_asset_bytes':1396364,'online_asset_sha256':'1718db148ea91987a8b3dee2474892b3df84b4b93cd8298e2e261153fa99c3ea',
 'full_asset':'VF-Start-V2.36.2-FULL.zip','full_asset_bytes':649250,'full_asset_sha256':'4a2defd88b5e25d8a5a431dfa00a23cea9370d9ea4f0f68255e483b25f2ff90c',
 'repair_asset':'repair-v2.36.2.php','repair_asset_bytes':4024813,'repair_asset_sha256':'70f1221555b2d318081bead944ff1912f6e5ec9b919a2e340fb490614e33e797',
 'release_state':'PUBLISHED / SEQUENTIAL OWNER UPGRADE REQUIRED','assistant_production_write':False,
 'candidate_readiness_gate':33478737169,'formal_bind_gate':33479052985,'formal_artifact_gate':33485021418,'strict_fresh_install_gate':33485364786,'main_promotion_gate':33485493941,'publication_gate':33485613966,'core_updates_candidate_gate':33486145556,'remote_release_truth_gate':33486270599,'remote_release_truth_artifact':9791880245,'remote_release_truth_artifact_sha256':'be76242d0793329d913e8f3ab141c9f8e5bf0ad3f38a36bc0ced7ae4119618e2'
}
cc=d.get('current_change',{});cc['result']='RELEASED AS V2.36.2 / SEQUENTIAL ONLINE UPGRADE PRESERVED';cc['main_write']=True;cc['production_write']=False;cc['runner_main_write']=False;d['current_change']=cc
d['formal_release_state']='V2.36.2 PUBLISHED / REMOTE RELEASE TRUTH PASS / V2.36.2 MANIFEST HELD UNTIL OWNER V2.36.1'
d['develop_state']='V2.36.2 RELEASED / RELEASE AUTHORITY CLOSED'
d['current_authority']='Owner Production V2.36.0 / Published Latest V2.36.2 / Live next hop V2.36.1 / V2.36.2 manifest candidate PASS-held'
d['next_action']='Owner performs V2.36.0 -> V2.36.1 using current live updater. After Owner readback confirms V2.36.1, promote core-updates candidate 3ddf344872744ba4e9e407c99fe704b90a4cda97, then perform Owner V2.36.1 -> V2.36.2 update and closure. Assistant must not write Owner Production.'
d.setdefault('authority',{})['current_formal_release_evidence']='docs/evidence/P01_V2.36.2_RELEASE_CLOSURE_20260901.md'
d['v2_36_2_release_chain']={'candidate_readiness_gate':33478737169,'formal_bind_gate':33479052985,'formal_artifact_gate':33485021418,'strict_fresh_gate':33485364786,'main_promotion_gate':33485493941,'publication_gate':33485613966,'core_updates_candidate_gate':33486145556,'remote_release_truth_gate':33486270599,'remote_release_truth_artifact':9791880245,'remote_release_truth_artifact_sha256':'be76242d0793329d913e8f3ab141c9f8e5bf0ad3f38a36bc0ced7ae4119618e2','live_core_updates_commit':'416cc8089b39349eb7ee62638b5267335d406320','manifest_candidate':'3ddf344872744ba4e9e407c99fe704b90a4cda97','result':'PASS / PUBLISHED / SEQUENTIAL ONLINE UPGRADE PRESERVED'}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
