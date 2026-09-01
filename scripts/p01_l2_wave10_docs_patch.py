from pathlib import Path
import json, re, subprocess

DEV = '923368dc7152b6063c0e4d1aeec3afc849bfff18'
MAIN = '4a41d3533fe8450c3f491d5aaf28417536012ba0'
SCHEMA = '2026082901'
WAVES = [
    (1,202,33555093483,'首次使用 + 真正全局搜索','a04631226e5be8f37388bbf0eb7fb7d34027a409'),
    (2,203,33555366786,'Ctrl/Cmd+K + 搜索相关性','65abfb77eb66202c61f13940ec188b99b6c9b125'),
    (3,204,33556060719,'Browser Helper 三步连接','564b437fdeb13d3fe09c033d08fdd0518779e98e'),
    (4,205,33556510987,'Browser Helper 1.6.5 日常闭环','b9c69eedec17979d2897e85f40d11cabfe1199e2'),
    (5,206,33556702984,'网址健康中心统一入口','65e6b882cee2ac20eb61bc3c959f16af005ef7a4'),
    (6,207,33559741011,'首页数据安全状态','00a96a449a6f78b44b705555a51be494d64e1130'),
    (7,208,33560626141,'URL-first 导航新增','bb1b9723919841fe5ae2148ab47c042b09258b9a'),
    (8,209,33560836974,'搜索零结果 URL → 保存','7de314fc5acd4e3a85bc9760799fede3cd1265ab'),
    (9,210,33561083446,'浏览器书签导入 onboarding-first','e65d75b2eb4e425b2b35a25d044dcc94c8915fd8'),
    (10,211,33561344420,'移入回收站后 30 秒内联撤销','923368dc7152b6063c0e4d1aeec3afc849bfff18'),
]

def read(path): return Path(path).read_text(encoding='utf-8')
def write(path, text): Path(path).write_text(text.rstrip()+'\n', encoding='utf-8')
def after_title(text, block):
    lines=text.splitlines()
    if not lines or not lines[0].startswith('#'): raise SystemExit('missing title')
    return lines[0]+'\n\n'+block.strip()+'\n\n'+'\n'.join(lines[1:]).lstrip()

def wave_table():
    rows=['| Wave | PR | Gate | Product outcome | Develop merge |','|---:|---:|---:|---|---|']
    rows += [f'| {n} | #{pr} | `{gate}` PASS | {desc} | `{merge}` |' for n,pr,gate,desc,merge in WAVES]
    return '\n'.join(rows)

current_block=f'''<!-- P01_L2_WAVE10_CURRENT_TRUTH -->
## Current Truth · V2.36.5 Production + L2 Wave 1–10

```text
Owner Production: V2.36.5
Owner Schema: {SCHEMA}
Published Latest: V2.36.5
Production main: {MAIN}
V2.36.5 Formal Source: ef86eba16aec71c1d0dabc16ad23089a78ee5057
V2.36.5 Runtime Tree: a7f472ec1f449ada1152d271f2723c52e7b58144
Current develop before docs checkpoint: {DEV}
Develop state: L2 Product Optimization Wave 1–10 / UNRELEASED / DEVELOP ONLY
Browser Helper: 1.6.5 on develop
Develop VERSION / src/VERSION.txt: 2.36.4 (historical working-branch value; NOT Production Authority)
Formal release candidate after Wave 10: NONE
Assistant direct Production write: NO
```

V2.36.5 已完成 Owner Production Closure。`develop` 与 `main` 有历史分叉，因此 **Production 版本必须读取 main / Owner Production Authority，不得用 develop 的 VERSION 文件反推生产版本**。Wave 1–10 均只在 `develop`，未进入 main / Tag / Release / core-updates / Owner Production。

当前 L2 证据：[`docs/evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md`](docs/evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md)。'''

# README: replace obsolete Current Truth/P0 block, keep stable product model below.
p='README.md'; t=read(p)
replacement='## Current Truth\n\n'+current_block.split('\n',1)[1]+'\n\n## Current Authority\n\n1. [`docs/authority/CURRENT.md`](docs/authority/CURRENT.md) — Current Production + Develop Authority；\n2. [`docs/authority/P01_L2_PRODUCT_OPT_CHECKPOINT_20260902.md`](docs/authority/P01_L2_PRODUCT_OPT_CHECKPOINT_20260902.md) — Wave 1–10 L2 checkpoint；\n3. [`docs/evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md`](docs/evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md) — exact Wave evidence；\n4. [`VF_PROJECT.json`](VF_PROJECT.json) — machine authority；\n5. [`docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md`](docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md) — functional contract；\n6. RPD / SSOT / Acceptance Matrix 中旧版本段落保留历史，不得覆盖上述 Current Authority。\n\n'
m=re.search(r'## Current Truth\n.*?(?=## Product Structure)',t,flags=re.S)
if not m: raise SystemExit('README current truth section not found')
t=t[:m.start()]+replacement+t[m.end():]
# Remove later duplicate old Current Authority section if present.
t=re.sub(r'\n## Current Authority\n\n优先读取：.*?(?=\n## |\Z)','\n',t,flags=re.S)
write(p,t)

# docs/README is a current index, replace fully.
doc_index=f'''# P01 · VF Start · 文档中心

> Owner Production：`V2.36.5`  
> Published Latest：`V2.36.5`  
> Schema：`{SCHEMA}`  
> Production main：`{MAIN}`  
> Current develop：`{DEV}`（Wave 1–10，UNRELEASED / DEVELOP ONLY）  
> Browser Helper：`1.6.5` on develop

## 1. Current Authority · 必读

1. [`authority/CURRENT.md`](authority/CURRENT.md) — 当前 Production + Develop 双层真相；
2. [`authority/P01_L2_PRODUCT_OPT_CHECKPOINT_20260902.md`](authority/P01_L2_PRODUCT_OPT_CHECKPOINT_20260902.md) — Wave 1–10 产品优化 checkpoint；
3. [`evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md`](evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md) — Exact PR / Gate / merge 证据；
4. [`../VF_PROJECT.json`](../VF_PROJECT.json) — 机器 Authority；
5. [`authority/P01_FUNCTIONAL_CONTRACT_20260829.md`](authority/P01_FUNCTIONAL_CONTRACT_20260829.md) — 功能语义 Authority。

`RPD.md`、`SSOT.md`、`ACCEPTANCE_MATRIX.md` 中旧版本内容保留为 Historical Baseline；如果与本页 / CURRENT / VF_PROJECT 冲突，以更晚 Current Truth 为准。

## 2. Production Truth

- Owner Production / Published Latest：**V2.36.5**。
- main：`{MAIN}`。
- Formal Source：`ef86eba16aec71c1d0dabc16ad23089a78ee5057`。
- Runtime Tree：`a7f472ec1f449ada1152d271f2723c52e7b58144`。
- Release ID：`380771266`。
- Schema：`{SCHEMA}`，无 Migration。
- Owner upgrade：`2.36.4 → 2.36.5 / success`；Production Closure PASS。

## 3. Develop Truth

- Exact source before docs checkpoint：`{DEV}`。
- L2 Product Optimization Wave 1–10 已全部合并 develop。
- Browser Helper component：`1.6.5`。
- Wave 1–10：**UNRELEASED / DEVELOP ONLY**。
- develop 根 `VERSION` 与 `src/VERSION.txt` 仍为 `2.36.4`，这是历史工作分支值，不是 Production Authority；本次 docs-only checkpoint 不改它。
- 当前没有新的 Formal Release Candidate，也没有自动 Release 授权。

## 4. Product Direction

P01 当前中心是：**导入 → 收藏 → 查找 → 使用 → 整理 → 健康 → 备份/恢复**。不横向扩张天气、股票、Todo、笔记、聊天机器人等通用 Dashboard 模块。

## 5. Release Boundary

普通 L2 工作只进入 `develop`。只有 Owner 明确授权 Release 后，才重新建立 Exact Source / Version / Artifact / Fresh / Atomic / Publication / core-updates 链；不得从 develop 的历史 VERSION 值推断或自动创建版本。
'''
write('docs/README.md',doc_index)

# CHANGELOG: add a clearly unreleased section.
p='CHANGELOG.md'; t=read(p)
marker='## Unreleased · L2 Product Optimization Wave 1–10 · 2026-09-02'
if marker not in t:
    bullets='\n'.join([f'- Wave {n} / PR #{pr} / Gate `{gate}` PASS：{desc}。' for n,pr,gate,desc,_ in WAVES])
    sec=f'''{marker}\n\n- Production baseline remains **V2.36.5**; these changes are **UNRELEASED / DEVELOP ONLY**.\n- Develop exact source before this docs checkpoint: `{DEV}`.\n- Browser Helper component on develop: `1.6.5`.\n- No Schema / Migration / main / Tag / Release / core-updates / Owner Production write in these waves.\n{bullets}\n\n'''
    t=sec+t
write(p,t)

# Current authority: prepend current block, historical closure remains below.
p='docs/authority/CURRENT.md'; t=read(p)
if '<!-- P01_L2_WAVE10_CURRENT_TRUTH -->' not in t:
    t=after_title(t,current_block)
write(p,t)

# Current state: prepend compact current block.
p='docs/handoff/CURRENT_STATE.md'; t=read(p)
state_block=f'''<!-- P01_L2_WAVE10_HANDOFF_CURRENT -->
## Current Handoff · V2.36.5 Production / L2 Wave 1–10 · 2026-09-02

- Owner Production / Published Latest：`V2.36.5`；Production Closure **PASS**。
- Product main：`{MAIN}`；Schema `{SCHEMA}`。
- Current develop before docs checkpoint：`{DEV}`；Wave 1–10 **UNRELEASED / DEVELOP ONLY**。
- Browser Helper：`1.6.5` on develop。
- develop `VERSION` / `src/VERSION.txt` = `2.36.4` is historical working-branch value only; do not use it as Production Authority。
- Next：继续 L2 Product Optimization；当前优先候选方向为 suggest-only 自动分类建议 / mobile quick-save feasibility，不自动 Release。
- main / Tag / Release / core-updates / Owner Production：本 checkpoint **NO WRITE**。

> 以下旧段落保留历史证据；与本段冲突时，以本段 + `docs/authority/CURRENT.md` 为准。'''
if '<!-- P01_L2_WAVE10_HANDOFF_CURRENT -->' not in t:
    t=after_title(t,state_block)
write(p,t)

# Replace current checkpoints entirely.
checkpoint=f'''# P01 · L2 Product Optimization Checkpoint · 2026-09-02

## Authority

- Owner Production / Published Latest：`V2.36.5` / Production Closure PASS。
- Product main：`{MAIN}`。
- Schema：`{SCHEMA}` / no migration。
- Develop exact source before this docs checkpoint：`{DEV}`。
- Browser Helper：`1.6.5` on develop。
- Wave 1–10：**UNRELEASED / DEVELOP ONLY**。
- Develop `VERSION` / `src/VERSION.txt` remain `2.36.4`; this is a historical working-branch value, **not** current Production Authority。
- No formal release candidate exists after Wave 10; do not auto-release.

## Wave 1–10

{wave_table()}

## Product Outcome

Wave 1–10 将现有能力收束成更完整的普通用户链路：

`首次进入/导入 → 全局搜索 → 快速收藏 → 健康整理 → 数据安全 → URL-first 新增 → 搜索即收藏 → 导入闭环 → 安全删除可撤销`

原则不变：单一 URL/Data Authority；Browser Helper 复用现有私密待整理链；网址健康不自动合并/删除；备份状态复用 BackupManager；删除仍是回收站语义；没有第二套搜索、收藏、恢复或数据系统。

## Release Boundary

- Product src changes are already merged to develop in PR #202–#211.
- This docs checkpoint itself changes documentation / machine authority only.
- VERSION / `src/VERSION.txt`: NO CHANGE.
- Schema / Migration: NO CHANGE.
- main / Tag / Release / core-updates / Owner Production: NO WRITE.
- Next release must explicitly reconcile the historical develop version files with an authorized Formal Source; this checkpoint does not do so.
'''
write('docs/authority/P01_L2_PRODUCT_OPT_CHECKPOINT_20260902.md',checkpoint)

handoff=f'''# P01 · L2 Current Handoff Checkpoint · 2026-09-02

## Start Here

Continue from `docs/authority/P01_L2_PRODUCT_OPT_CHECKPOINT_20260902.md` and `docs/evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md`.

## Current Truth

- Repository：`llhzx2018/vf-start`。
- Runtime：L2 Product Optimization。
- Owner Production / Published Latest：`V2.36.5`。
- main：`{MAIN}`。
- develop before docs checkpoint：`{DEV}`。
- Browser Helper：`1.6.5` on develop。
- Wave 1–10：UNRELEASED / DEVELOP ONLY。
- Schema：`{SCHEMA}`。
- develop VERSION files still read `2.36.4`; never use them to override Production V2.36.5.

## Closed L2 Wave

PR #202–#211 have merged with their exact gates PASS. Do not re-run them unless new evidence shows a regression.

## Next Product Direction

Continue the same product center: `导入 → 收藏 → 查找 → 使用 → 整理 → 健康 → 备份/恢复`.

Highest-value remaining items from the approved roadmap:
1. suggest-only 自动分类建议 inside import / 待整理；never auto-reclassify Owner data；
2. mobile quick-save feasibility using existing save authority (Web Share Target / lightweight share path), not a second product or native app by default；
3. tags / smart collections remain restrained; no complex rules engine yet.

## Hard Boundaries

No main / Tag / Release / core-updates / Owner Production write from ordinary L2 work. No automatic version bump. No second frontend, second URL authority, second save system, or AI semantic-search expansion without a later explicit product decision.
'''
write('docs/handoff/P01_L2_CURRENT_CHECKPOINT_20260902.md',handoff)

# Historical / long-lived authority overlays.
historical=f'''<!-- P01_CURRENT_TRUTH_OVERLAY_20260902 -->
> **Current Truth Overlay · 2026-09-02**  
> Owner Production / Published Latest：`V2.36.5`；main `{MAIN}`；Schema `{SCHEMA}`。  
> Develop before this docs checkpoint：`{DEV}`，L2 Wave 1–10 **UNRELEASED / DEVELOP ONLY**，Browser Helper `1.6.5`。  
> 本文后续出现的 V2.33/V2.34 等“Current”表述属于其成文时的 Historical Baseline；当前状态请以 [`CURRENT.md`](CURRENT.md) 与 [`P01_L2_PRODUCT_OPT_CHECKPOINT_20260902.md`](P01_L2_PRODUCT_OPT_CHECKPOINT_20260902.md) 为准。'''
for p in ['docs/authority/SSOT.md','docs/authority/RPD.md','docs/authority/ACCEPTANCE_MATRIX.md']:
    t=read(p)
    if '<!-- P01_CURRENT_TRUTH_OVERLAY_20260902 -->' not in t: t=after_title(t,historical)
    write(p,t)

p='docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md'; t=read(p)
t=t.replace('> Current Production: `V2.33.0 / Schema 2026082901`','> Current Production: `V2.36.5 / Schema 2026082901`')
functional=f'''<!-- P01_L2_FUNCTIONAL_OVERLAY_20260902 -->
> **L2 Functional Overlay · 2026-09-02**  
> Production remains `V2.36.5`; develop `{DEV}` adds Wave 1–10 as **UNRELEASED / DEVELOP ONLY**. These waves preserve this contract's single URL/Data Authority and add no second save/search/backup/recovery system. Browser Helper component on develop is `1.6.5`.'''
if '<!-- P01_L2_FUNCTIONAL_OVERLAY_20260902 -->' not in t: t=after_title(t,functional)
write(p,t)

# New exact evidence file.
evidence=f'''# P01 · L2 Product Optimization Wave 1–10 Evidence · 2026-09-02

## Exact Boundary

- Owner Production：`V2.36.5` / Schema `{SCHEMA}` / Closure PASS。
- Production main：`{MAIN}`。
- Develop source before docs checkpoint：`{DEV}`。
- Scope represented here：PR `#202` through `#211`。
- State：**UNRELEASED / DEVELOP ONLY**。
- Browser Helper component：`1.6.5` on develop。

## Verified Waves

{wave_table()}

## Invariants

- No Wave 1–10 changed Schema or added a migration.
- No Wave 1–10 wrote main / Tag / GitHub Release / core-updates / Owner Production.
- Existing single URL/Data Authority is preserved.
- Browser Helper continues to save into the existing private-pending capture flow.
- Link Health Center reuses existing health + duplicate engines; no auto-merge.
- Home backup signal reuses `VfBackupManager` authority.
- URL-first add keeps core Repository title invariant; only Workspace create boundary derives a hostname fallback.
- Search-to-save reuses the existing add drawer / create authority.
- Bookmark import reuses existing preview/apply/restore-point contracts.
- Delete undo reuses recycle-bin restore and never changes permanent-delete semantics.

## Version Divergence Note

`develop` root `VERSION` and `src/VERSION.txt` still contain `2.36.4`. This is a historical working-branch value caused by intentional branch divergence and **must not be interpreted as Owner Production**. Current Production Authority is V2.36.5 from main / Owner Closure. A future authorized release must reconcile release-version metadata explicitly at Formal Source construction time.
'''
Path('docs/evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md').write_text(evidence.rstrip()+'\n',encoding='utf-8')

# Machine authority: copy Production fields from main, preserve develop component/work truth, then add exact L2 wave object.
p='VF_PROJECT.json'; dev=json.loads(read(p))
main=json.loads(subprocess.check_output(['git','show','origin/main:VF_PROJECT.json'],text=True))
for key in ['status','production_version','target_release_version','schema_version','production_release','published_release','formal_release_state']:
    dev[key]=main[key]
dev['working_version']='2.36.4'
dev['working_version_note']='develop VERSION files remain 2.36.4 as historical working-branch value; Production Authority is V2.36.5 on main'
dev['current_phase']='V2.36.5 OWNER PRODUCTION CLOSURE PASS / L2 PRODUCT OPTIMIZATION WAVE 1-10'
dev.setdefault('component_versions',{})['browser_helper']='1.6.5'
dev['candidate_state']='NO FORMAL RELEASE CANDIDATE / DEVELOP-ONLY WAVE 1-10 / VERSION FILES REMAIN HISTORICAL 2.36.4'
dev['develop_state']='L2 PRODUCT OPTIMIZATION WAVE 1-10 MERGED / UNRELEASED / DEVELOP ONLY'
dev['current_authority']=f'Owner Production V2.36.5 / main {MAIN} / develop {DEV} Wave 1-10 unreleased / Browser Helper 1.6.5'
dev['next_action']='Continue L2 Product Optimization; prioritize suggest-only classification assistance and mobile quick-save feasibility; no automatic release.'
dev['current_change']={
    'change_id':'P01-L2-PRODUCT-OPT-WAVE-1-10-20260902','type':'PRODUCT OPTIMIZATION / DEVELOP ONLY',
    'production_main':MAIN,'production_version':'2.36.5','develop_exact_source_before_docs_checkpoint':DEV,
    'product_prs':[x[1] for x in WAVES],'product_gates':[x[2] for x in WAVES],
    'schema_change':False,'migration':None,'version_change':False,'release':False,'main_write':False,'production_write':False,'runner_main_write':False
}
dev['l2_product_wave_20260902']={
    'state':'WAVE 1-10 MERGED TO DEVELOP / UNRELEASED','develop_exact_source':DEV,'browser_helper':'1.6.5',
    'waves':[{'wave':n,'pr':pr,'gate':gate,'outcome':desc,'develop_merge':merge} for n,pr,gate,desc,merge in WAVES],
    'version_files':'2.36.4 / historical develop value / not production authority','schema_version':SCHEMA,
    'main_write':False,'release_write':False,'production_write':False
}
auth=dev.setdefault('authority',{})
auth['current_production_evidence']='docs/evidence/P01_V2.36.5_OWNER_PRODUCTION_CLOSURE_20260902.md'
auth['current_formal_release_evidence']='docs/evidence/P01_V2.36.5_OWNER_PRODUCTION_CLOSURE_20260902.md'
auth['current_l2_develop_evidence']='docs/evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md'
# Keep owner activation object current by copying main if present.
if 'owner_production_activation_evidence' in main: dev['owner_production_activation_evidence']=main['owner_production_activation_evidence']
write(p,json.dumps(dev,ensure_ascii=False,indent=2))

print('P01 L2 WAVE 1-10 DOC PATCH APPLIED')
