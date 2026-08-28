from pathlib import Path
import json, re

root=Path('.')
prod='2.23.0'; schema='2026082801'
code_develop='4a064d7ea34998b4f8103d23e96b2e10be46267c'

current=f'''# P01 · VF Start · Current Authority

> 更新时间：2026-08-28  
> 状态：`CURRENT / V2.23.0 OWNER PRODUCTION / V2.24.0 UX/UI RELEASE CANDIDATE`

## 1. Current Truth

```text
Owner Production Runtime: V2.23.0
Owner Production Schema: {schema}
Owner Upgrade: 2.22.1 -> 2.23.0 / SUCCESS / 2026-08-28
Formal Release: V2.23.0 / PASS
Current main: f00a7d5dfe61d429a845bb1931065653e7750337
V2.24 Candidate Runtime Source: {code_develop}
Target Release: V2.24.0
Schema Change: NO
Release V2.24.0: NO
Production Write by V2.24 work: NO
```

P01 当前产品裁决：**一个系统、一个数据 Authority、多个资源模式**。Home / Start / Channels / Watch / 资源整理共用 SurfaceShell；资源语义可以不同，但不得呈现成多个独立产品。

## 2. V2.24 UX/UI Contract

- Home：任务与发现中心，不再把 Start / Channels / Watch 做成三套并列小首页；
- Start：管理员默认进入共享 Shell；`start.php?classic=1` 保留 Classic Start 兼容入口；
- Channels：频道 / 创作者 / Podcast 长期记忆库，采用创作者/内容源卡片，不使用视频缩略图墙语义；
- Watch：电影 / 剧集 / 纪录片 / 视听索引，继续保持海报/Watchlist 心智；
- Resource Organizer：共享资源整理入口，不是第四个产品；
- Global Search：跨 Surface 检索，不跳转旧管理壳；
- Branding：SurfaceShell 与 AdminShell 读取同一 `branding.logoUrl` Authority；
- Mobile：底部四个主入口必须同时显示图标与文字；
- 历史 URL 不静默迁移；归属建议必须由管理员显式确认；
- 匿名 `/` 继续公开 Start，SEO/公开投影合同不变。

## 3. V2.24 Verified Evidence

```text
Core UX Functional Source: c96178b1112dca20af0b15b557a54abcb4211bed
Core UX Machine: 33151873413 / PASS
Final PR Head Gate: 33152147817 / PASS
PR #24 -> develop: 537c96c569203b09bfdec563aef8daf7b105e424
Develop Gate: 33152360233 / PASS
Branding Source: 5941e62717b9fa5509df24175a1676e1127b6926
Branding Machine: 33153030288 / PASS
PR #25 -> develop: 5b6f8c63b0040deaa60e69f08a7cec33e31a052b
Full UX/UI Screenshot Audit: 33153164979 / PASS
UI Audit Fix Source: f0882eceec27796da5a43e0169f7c8e980fb1814
UI Audit Fix Machine + Screenshots: 33153514954 / PASS
PR #27 -> develop: {code_develop}
Schema: {schema}
Common Baseline: PASS / DRIFT 0 / UNKNOWN 0
SQLite Integrity / FK: PASS / ok / 0
```

Screenshot Audit 使用 Fresh Runtime + 代表性 Start / Channels / Watch 数据，真实 Headless Chrome 覆盖桌面与 390×844 移动端。Runner 缺少中文字体导致截图中文字形显示为方框，不属于产品字体合同失败；布局、层级、响应式与卡片语义可被验证。

## 4. V2.23 Production / Release Baseline

```text
Tag: v2.23.0
Release ID: 378293470
Release Source: 6e7d30e6ea0c8f5f70076a69b0d1e6fb9be620b2
Release Tree: 8bc7b4c2f643566d3688ecdeda74a47c320cbc2f
Publication: 33147522304 / PASS
core-updates: 2.23.0 / cf3a89a722cf190ed5b94184a92feceba1f0dd32
Online Asset: VF_Start_V2.23.0_UPDATE.zip
SHA-256: a1e09774fc88281b5c2e10f1481947d94c9378472862907cc89aeb1308d97c11
Owner Production Upgrade: PASS
```

## 5. Next Gate

`Authority docs -> develop merge -> final develop Exact Source Candidate Gate -> Release Decision`。

在 Release Decision 之前，不创建 V2.24 Tag / GitHub Release，不更新 core-updates，不修改 Production。
'''
(root/'docs/authority/CURRENT.md').write_text(current,encoding='utf-8')

accept=f'''# P01 · VF Start · Current Acceptance Matrix

> Scope：`V2.24.0 One-System UX/UI Release Candidate`  
> Owner Production：`V2.23.0 / Schema {schema}`  
> V2.24 Release：`NOT RELEASED`

| Gate | Result |
|---|---|
| Owner Production V2.23.0 | PASS / Owner UI |
| V2.24 Core UX Functional Source | PASS / `c96178b1112dca20af0b15b557a54abcb4211bed` |
| Core UX Machine Gate | PASS / `33151873413` |
| Final PR Head Gate | PASS / `33152147817` |
| PR #24 -> develop | PASS / `537c96c569203b09bfdec563aef8daf7b105e424` |
| Develop Exact Source Gate | PASS / `33152360233` |
| Shared SurfaceShell | PASS |
| Home task-oriented IA | PASS |
| Cross-Surface Search | PASS |
| Admin Start unified / Classic compatibility | PASS |
| Channels / Watch / Organizer shared Shell | PASS |
| Same Branding Authority | PASS / `33153030288` |
| PR #25 -> develop | PASS / `5b6f8c63b0040deaa60e69f08a7cec33e31a052b` |
| Desktop + Mobile Screenshot Audit | PASS / `33153164979` |
| Mobile primary nav text labels | PASS / screenshot verified |
| Channels creator/source card semantics | PASS / screenshot verified |
| UI Audit Fix Source | PASS / `f0882eceec27796da5a43e0169f7c8e980fb1814` |
| UI Audit Fix Machine | PASS / `33153514954` |
| PR #27 -> develop runtime source | PASS / `{code_develop}` |
| PHP / JavaScript Syntax | PASS |
| Fresh Install / Multi-Surface Verify | PASS |
| Common Baseline | PASS / DRIFT 0 / UNKNOWN 0 |
| SQLite integrity / FK | PASS / ok / 0 |
| Anonymous `/` stays Public Start | PASS |
| Silent Reclassification | NO |
| Schema Change | NO |
| Release V2.24.0 | NOT EXECUTED |
| Production Write by V2.24 | NO |

## V2.23 Production Baseline

V2.23.0 Formal Release、GitHub Release、正式附件、core-updates 与 Owner `2.22.1 -> 2.23.0` 在线升级均已完成。V2.24 Candidate 不重写该历史证据，只在其上进行 Presentation / IA / UX 收口。
'''
(root/'docs/authority/ACCEPTANCE_MATRIX.md').write_text(accept,encoding='utf-8')

ssot=f'''# P01 · VF Start · Current Engineering SSOT

> 状态：`CURRENT / V2.23.0 OWNER PRODUCTION / V2.24.0 UX/UI RELEASE CANDIDATE`  
> Rebaseline：2026-08-28

## 1. Authority

`OWNER 最新明确裁决 -> Production Evidence -> Git Current Source -> Current RPD/SSOT/Acceptance -> 历史 Evidence`。

Production Runtime 当前为 V2.23.0 / Schema `{schema}`。V2.24.0 仍是未发布 Candidate，任何 Machine PASS 都不得写成 Release 或 Production。

## 2. Data / Security Authority

- URL Identity：现有 `links`；
- Surface 稀疏扩展：`resource_surface_profiles`；
- 无 Profile：Start；
- Schema Head：`{schema}`，V2.24 不改 Schema；
- Public Projection、Session、CSRF、Backup、Recovery、Atomic Update 继续使用既有 Core Authority；
- UI 不得建立 Shadow Table，不复制 URL，不托管媒体文件。

## 3. Presentation Authority

```text
Repository / SurfaceRepository
          -> SurfaceShell.php
             -> Home
             -> Start
             -> Channels
             -> Watch
             -> Resource Organizer
```

`src/app/SurfaceShell.php` 是私人产品面的共享 Shell Authority。品牌读取与 AdminShell 相同的 `branding.logoUrl`；`surface-home.css` 提供基础统一视觉，`surface-branding.css` 负责品牌适配，`surface-ux-closure.css` 负责经真实截图 Audit 后确认的响应式/语义收口。

## 4. Route Contract

```text
Admin /            -> surfaces.php / Unified Home
Admin start.php    -> Unified Start
start.php?classic=1-> Classic Start compatibility
Anonymous /        -> Public Start
channels.php       -> Channels creator/source library
watch.php          -> Watch index/watchlist
surface-manager.php-> Resource Organizer in shared shell
```

管理员与匿名投影必须隔离。

## 5. UX Contract

- Home 负责待整理、继续内容、发现与跨 Surface 资产入口，不做三套小首页；
- Channels 是长期内容源记忆，不做 YouTube Feed/视频墙；
- Watch 保持海报/视听索引语义；
- 移动端四个主 Surface 必须有可读文字标签，不能只依赖图标；
- 分类、收藏、Surface、行为状态彼此独立；
- 归属建议只读，采纳必须显式提交。

## 6. Candidate Machine Authority

```text
Core UX: c96178b1112dca20af0b15b557a54abcb4211bed / 33151873413 PASS
PR Head: 33152147817 PASS
Develop: 537c96c569203b09bfdec563aef8daf7b105e424 / 33152360233 PASS
Branding: 5941e62717b9fa5509df24175a1676e1127b6926 / 33153030288 PASS
Screenshot Audit Develop: 5b6f8c63b0040deaa60e69f08a7cec33e31a052b / 33153164979 PASS
UI Audit Fix: f0882eceec27796da5a43e0169f7c8e980fb1814 / 33153514954 PASS
Current Candidate Runtime Source: {code_develop}
```

## 7. Release Boundary

当前不得创建 V2.24 Tag / GitHub Release，不得更新 core-updates，不得修改 Production。下一 Gate 是 Authority Closure 合入 develop 后，对新的 develop merge commit 做 Final Exact Source Candidate Gate，再由 OWNER 决定是否进入 Release。
'''
(root/'docs/authority/SSOT.md').write_text(ssot,encoding='utf-8')

# RPD: repair current route/product language without rewriting historical product rationale.
p=root/'docs/authority/RPD.md'; t=p.read_text(encoding='utf-8')
t=t.replace('> 状态：`CURRENT / V2.23.0 MULTI-SURFACE + UNIFIED SURFACE UI`','> 状态：`CURRENT / V2.23.0 OWNER PRODUCTION / V2.24.0 ONE-SYSTEM UX/UI CANDIDATE`')
t=t.replace('- 管理员根 `/` 不再直接显示 Classic Start，而是进入 Unified Dashboard；\n- `start.php` 是显式 Classic Start 入口；\n- 匿名根 `/` 继续公开 Start，不改变 SEO/公开导航行为。','- 管理员根 `/` 进入 Unified Home；\n- 管理员 `start.php` 在共享 SurfaceShell 内提供 Start 工作区；\n- `start.php?classic=1` 保留成熟 Classic Start 兼容入口；\n- 匿名根 `/` 继续公开 Start，不改变 SEO/公开导航行为。')
t=re.sub(r'## 6\. Unified Surface UI · V2\.23\.0.*?(?=## 7\. 管理与整理合同)',f'''## 6. One-System UX/UI · V2.24.0 Candidate\n\nV2.23.0 已证明统一 Surface 入口可发布；Owner 升级后真实使用反馈证明“三列 Dashboard + 独立 Start”仍有明显拼装感。V2.24 的产品修正是：\n\n```text\nHome = 任务 / 发现 / 待整理\nStart = 网站工作区\nChannels = 创作者 / 内容源长期记忆\nWatch = 影视 / 视听索引\nResource Organizer = 共享整理工作区\n\n全部私人产品面 -> 同一个 SurfaceShell\n```\n\nChannels 的主要卡片必须表现为“创作者 / 内容源”，而不是视频缩略图；Watch 保持海报心智。移动端四个主入口必须同时显示图标与文字。全局搜索保持在产品面并跨 Surface 返回结果。\n\n当前 Candidate Runtime Source：`{code_develop}`。Screenshot Audit `33153164979` PASS，UI Audit Fix Gate `33153514954` PASS。Schema 不变，Release / Production 未执行。\n\n''',t,flags=re.S)
p.write_text(t,encoding='utf-8')

# Architecture: repair current route/shell sections and append exact candidate closure.
p=root/'docs/architecture/P01_MULTI_SURFACE_ARCHITECTURE.md'; t=p.read_text(encoding='utf-8')
t=t.replace('> Current Architecture · V2.23.0 · 2026-08-28','> Current Architecture · V2.24.0 Candidate · 2026-08-28')
t=re.sub(r'## 5\. Route / Shell 边界.*?(?=## 6\. Unified Surface Shell)',r'''## 5. Route / Shell 边界\n\n| Route | V2.24 责任 |\n|---|---|\n| `/` / `index.php` | 管理员进入 Unified Home；匿名继续 Public Start |\n| `surfaces.php` | 任务/发现型 Unified Home |\n| `start.php` | 管理员共享 Shell 的 Start 工作区 |\n| `start.php?classic=1` | Classic Start 兼容入口 |\n| `channels.php` | Channels 创作者/内容源长期记忆库 |\n| `watch.php` | Watch 影视/视听索引 |\n| `surface.php` | Channels / Watch 共享安全渲染内核 |\n| `surface-manager.php` | 共享 Shell 的 Resource Organizer |\n| `surface-open.php` | 管理员打开记录与安全重定向 |\n\nClassic Start 只保留兼容，不再成为管理员主体验。\n\n''',t,flags=re.S)
t=re.sub(r'## 6\. Unified Surface Shell.*?(?=## 7\. Channels Resurfacing)',r'''## 6. Unified Surface Shell\n\n```text\nSurfaceShell.php\n├─ Home: tasks / discovery / organizer signals\n├─ Start: website workspace\n├─ Channels: creator/source memory\n├─ Watch: poster/watchlist semantics\n└─ Resource Organizer\n```\n\nSurface 的消费语义不同，但 Sidebar、Topbar、Search、Branding、Responsive Navigation 是同一 Presentation Authority。移动端主导航使用图标 + 文字；Channels 主卡使用圆形创作者/来源 Identity，避免视频墙语义。\n\n''',t,flags=re.S)
t=re.sub(r'## 11\. One-System Presentation Architecture · V2\.24.*?\Z','',t,flags=re.S).rstrip()+f'''\n\n## 13. V2.24 Candidate Closure\n\n```text\nCore UX Machine: 33151873413 PASS\nBranding Machine: 33153030288 PASS\nDesktop/Mobile Screenshot Audit: 33153164979 PASS\nUI Audit Fix Machine: 33153514954 PASS\nCandidate Runtime Source: {code_develop}\nSchema: {schema}\n```\n\nV2.24 仍为未发布 Candidate。\n'''
p.write_text(t,encoding='utf-8')

# Machine-readable state.
p=root/'VF_PROJECT.json'; j=json.loads(p.read_text(encoding='utf-8'))
j['status']='V2.23.0 OWNER PRODUCTION / V2.24.0 UX/UI RELEASE CANDIDATE'
j['current_working_branch']='develop'
j['current_phase']='V2.24.0 UX/UI CANDIDATE / SCREENSHOT AUDIT CLOSED / RELEASE DECISION PENDING'
c=j.setdefault('current_change',{})
c.update({'final_runtime_source':code_develop,'branding_source':'5941e62717b9fa5509df24175a1676e1127b6926','branding_machine_run':33153030288,'branding_machine_result':'PASS','screenshot_audit_source':'5b6f8c63b0040deaa60e69f08a7cec33e31a052b','screenshot_audit_run':33153164979,'screenshot_audit_result':'PASS','ui_audit_fix_source':'f0882eceec27796da5a43e0169f7c8e980fb1814','ui_audit_fix_run':33153514954,'ui_audit_fix_result':'PASS','mobile_nav_labels':'PASS','channels_creator_card_semantics':'PASS'})
j['candidate_state']='UX/UI MACHINE + SCREENSHOT AUDIT PASS / AUTHORITY CLOSURE / NOT RELEASED'
j['current_authority']=f'Owner Production V2.23.0 / Schema {schema}; V2.24.0 Candidate Runtime {code_develop}; UX/UI screenshot audit and fixes PASS; not released'
j['next_action']='Merge V2.24 authority closure -> final develop Exact Source Candidate Gate -> owner Release decision'
j['authority']['ux_ui_candidate_evidence']='docs/evidence/P01_V2.24.0_UX_UI_CANDIDATE_20260828.md'
p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# README current overlays; keep historical sections but remove stale production claims.
for name in ['README.md','docs/README.md']:
    p=root/name; t=p.read_text(encoding='utf-8')
    marker='# P01 · VF Start' if name=='README.md' else '# P01 · VF Start 文档中心'
    rest=t[t.find(marker):]
    overlay=f'''## V2.24.0 One-System UX/UI · Release Candidate\n\n- Owner Production Runtime：**V2.23.0 / Schema {schema}**；\n- Candidate Runtime Source：`{code_develop}`；\n- Core UX / Branding / Screenshot Audit / UI Audit Fix：**PASS**；\n- 移动端主导航已补齐文字；Channels 已按创作者/内容源语义收口；\n- Schema：不变；V2.24 Release / Production：**未执行**。\n\n'''
    rest=rest.replace('Owner Production Runtime：`V2.22.1` / Schema `2026082801`；','Owner Production Runtime：`V2.23.0` / Schema `2026082801`；')
    rest=rest.replace('V2.23.0 Owner Production Upgrade：`PENDING / separate gate`。','V2.23.0 Owner Production Upgrade：`PASS / Owner UI`。')
    rest=rest.replace('Owner Production Upgrade V2.23.0：`PENDING`。','Owner Production Upgrade V2.23.0：`PASS`。')
    rest=rest.replace('Owner Production Runtime: V2.22.1','Owner Production Runtime: V2.23.0').replace('Production Upgrade V2.23.0: NOT EXECUTED','Production Upgrade V2.23.0: PASS')
    if name=='README.md':
        rest=rest.replace('- [V2.23.0 Publication Evidence](docs/evidence/P01_V2.23.0_PUBLICATION_20260828.md)','- [V2.23.0 Publication Evidence](docs/evidence/P01_V2.23.0_PUBLICATION_20260828.md)\n- [V2.24.0 UX/UI Candidate Evidence](docs/evidence/P01_V2.24.0_UX_UI_CANDIDATE_20260828.md)')
    else:
        rest=rest.replace('## V2.23.0 Evidence','## V2.24.0 Candidate Evidence\n\n- [V2.24.0 UX/UI Candidate Evidence](evidence/P01_V2.24.0_UX_UI_CANDIDATE_20260828.md)\n\n## V2.23.0 Evidence')
    p.write_text(overlay+rest,encoding='utf-8')

# Evidence and changelog.
ev=f'''# P01 · V2.24.0 UX/UI Candidate Evidence · 2026-08-28\n\n## Verdict\n\n`CANDIDATE = PASS` / `RELEASE = NO` / `PRODUCTION = NO`\n\n## Exact Evidence\n\n- Core UX Source: `c96178b1112dca20af0b15b557a54abcb4211bed` / Run `33151873413` PASS\n- Final PR Head: Run `33152147817` PASS\n- PR #24 develop merge: `537c96c569203b09bfdec563aef8daf7b105e424` / Run `33152360233` PASS\n- Branding Source: `5941e62717b9fa5509df24175a1676e1127b6926` / Run `33153030288` PASS\n- PR #25 develop merge: `5b6f8c63b0040deaa60e69f08a7cec33e31a052b`\n- Full desktop/mobile Screenshot Audit: Run `33153164979` PASS\n- UI Audit Fix Source: `f0882eceec27796da5a43e0169f7c8e980fb1814` / Run `33153514954` PASS\n- PR #27 develop runtime source: `{code_develop}`\n- Schema: `{schema}` / unchanged\n- Baseline: PASS / DRIFT 0 / UNKNOWN 0\n- SQLite integrity: ok / Foreign Keys: 0\n\n## UI Audit Closure\n\n1. Home / Start / Channels / Watch / Resource Organizer share one SurfaceShell.\n2. SurfaceShell and AdminShell share the existing Branding Authority.\n3. Mobile 390×844 bottom navigation now exposes labels together with icons.\n4. Channels main library uses creator/source identity cards rather than video-thumbnail semantics.\n5. Watch remains poster/watchlist-oriented.\n6. Anonymous Public Start remains unchanged.\n\nRunner screenshot environment lacks Chinese fonts; square glyphs in audit images are infrastructure presentation only, not a product fallback-font failure.\n'''
(root/'docs/evidence/P01_V2.24.0_UX_UI_CANDIDATE_20260828.md').write_text(ev,encoding='utf-8')

p=root/'CHANGELOG.md'; t=p.read_text(encoding='utf-8')
entry=f'''## V2.24.0 · Candidate / Not Released · 2026-08-28\n\n- Rebaseline private P01 into one shared Home / Start / Channels / Watch / Resource Organizer workspace.\n- Add cross-Surface search and task-oriented Home.\n- Reuse the existing P01 Branding Authority in SurfaceShell.\n- Close mobile navigation readability and Channels creator/source card semantics after real desktop/mobile screenshot audit.\n- Candidate runtime source `{code_develop}`; Machine runs `33151873413`, `33153030288`, `33153164979`, `33153514954` PASS.\n- Schema unchanged; no V2.24 Release or Production write.\n\n'''
if '## V2.24.0 · Candidate / Not Released' not in t:
    t=entry+t
p.write_text(t,encoding='utf-8')
