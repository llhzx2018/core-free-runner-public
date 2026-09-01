#!/usr/bin/env python3
from pathlib import Path
import json

root=Path('.')
evidence='''# P01 · Shared Sticky Filter Scroll Overlap Fix · 2026-09-01

## Verdict

**PASS / MERGED TO DEVELOP / NOT RELEASED**

This is a post-V2.36.2 L2 Product bug fix. It does not alter the already published V2.36.2 Tag/Release and does not write Owner Production.

## User-visible defect

The shared filter/tab toolbar on `start.php`, `channels.php`, `watch.php`, and `topics.php` became visually broken while scrolling: cards and text appeared to pass underneath and through the controls.

## Root cause

`src/assets/workspace-domain-nav.css` overrode the shared sticky `.vf-workspace-toolbar` with `background: transparent`; desktop also used an extra 8px offset below the search/subbar.

## Fresh Runtime diagnostic

- Exact Source: `4ec93adad93977a519675b55806866c896bad09f`
- Diagnostic Run: `33491021229` — PASS
- Artifact: `9793757582`
- Digest: `sha256:93848135fbd3a141a0dc836cfdc37e25eb07ec78937b1acb9128056e5f9860d4`
- Dataset: 96 navigation links, 48 channels, 48 watch items, 40 topics, 8 categories.
- Browser matrix: 390 + 1440, all four routes, multiple scroll depths.
- Horizontal overflow: 0.
- Reproduced toolbar background: fully transparent.
- Reproduced desktop sticky gap: 8px.

## Product fix

- Candidate: `ee568178804bf8c98abcf4b85f4dc20939712070`
- Exact scope: `src/assets/workspace-domain-nav.css`
- Keep toolbar sticky.
- Use opaque `var(--ws-bg)` background.
- Remove desktop 8px sticky gap.
- No card/page redesign.

## Machine Gate

- Fix Gate Run: `33491546225` — PASS
- Artifact: `9793960558`
- Digest: `sha256:ce5c98f1511c7d90b93468d763d26d7a7e5235a2e9db180ee63e2ef684c6c2df`
- 390 + 1440 / Start + Channels + Watch + Topics / mid + deep scroll: PASS.
- Toolbar opaque: PASS.
- Desktop toolbar top equals subbar bottom: PASS.
- Mobile toolbar top equals global domain-nav bottom: PASS.
- Horizontal overflow: PASS.
- SQLite integrity / foreign keys: PASS.
- Gate screenshots visually reread: PASS.

## Merge truth

- Product PR: `#176`
- develop merge: `bd7f08b3fde91e4a20b0970deb5fec325e869159`
- Repository Tree: `f3eb1ab9f8c5a6ea6a66cf4374a6fa5dc25b19d7`
- Runtime Tree: `f6ec50d94dd5023050ccf1aedc3df879603cb5db`
- Schema / Migration / Version: unchanged.
- main / Tag / Release / core-updates / Owner Production: no write by this fix.

## Release boundary

Published Latest remains V2.36.2. Owner Production remains V2.36.0, with safe live online next hop V2.36.1. This L2 fix is currently **develop-only / not released**.
'''
(root/'docs/evidence/P01_SCROLL_STICKY_OVERLAP_FIX_20260901.md').write_text(evidence,encoding='utf-8')

section='''<!-- P01_SCROLL_STICKY_OVERLAP_FIX -->
## 共享滚动筛选条穿透修复 · 2026-09-01

- 类型：**真实共享 UX BUG 修复**；不是新功能。
- 用户现象：导航 / 频道 / 影视 / 专题滚动时，搜索/筛选条与下方内容叠压，内容像从控件后面穿过去。
- 根因：`workspace-domain-nav.css` 将 sticky `.vf-workspace-toolbar` 覆盖为 `background: transparent`，桌面同时额外留出 `8px` sticky 间隙。
- Fresh Runtime Diagnostic：Run `33491021229` = **PASS**；Artifact `9793757582`；Digest `sha256:93848135fbd3a141a0dc836cfdc37e25eb07ec78937b1acb9128056e5f9860d4`。
- Product Candidate：`ee568178804bf8c98abcf4b85f4dc20939712070`；仅改 `src/assets/workspace-domain-nav.css` 1 文件。
- 修复：保留 sticky；背景改为实色 `var(--ws-bg)`；桌面去掉 8px 漏缝；不重设计页面。
- Fix Gate：Run `33491546225` = **PASS**；Artifact `9793960558`；Digest `sha256:ce5c98f1511c7d90b93468d763d26d7a7e5235a2e9db180ee63e2ef684c6c2df`。
- Gate：390 + 1440、四页、mid/deep scroll、sticky 层连续、背景不透明、无横向溢出、SQLite/FK 全 PASS；截图人工回读 PASS。
- Product PR `#176` 已合并 develop：`bd7f08b3fde91e4a20b0970deb5fec325e869159`；Runtime Tree `f6ec50d94dd5023050ccf1aedc3df879603cb5db`。
- Schema / Migration / Version：**UNCHANGED**。
- Published Latest 仍为 `V2.36.2`；本修复当前 **DEVELOP ONLY / NOT RELEASED**。
- `main` / Tag / Release / core-updates / Owner Production：**NO WRITE BY THIS FIX**。

> 以下旧段落继续保留历史证据；如与本段的当前 L2 Develop 状态冲突，以本段为 Current L2 Authority。

'''
for rel,title in [('docs/authority/CURRENT.md','# P01 · VF Start · Current Authority\n\n'),('docs/handoff/CURRENT_STATE.md','# CURRENT STATE · P01 VF Start\n\n')]:
    p=root/rel
    s=p.read_text(encoding='utf-8')
    assert s.startswith(title)
    p.write_text(title+section+s[len(title):],encoding='utf-8')

p=root/'VF_PROJECT.json'
d=json.loads(p.read_text(encoding='utf-8'))
d['status']='V2.36.0 OWNER PRODUCTION / V2.36.2 PUBLISHED / L2 PRODUCT OPTIMIZATION'
d['current_phase']='V2.36.2 PUBLISHED / L2 SCROLL STICKY FIX MERGED TO DEVELOP / OWNER MUST COMPLETE V2.36.1 HOP FIRST'
d['develop_state']='POST-V2.36.2 L2 / SCROLL STICKY OVERLAP FIX MERGED / MACHINE PASS / NOT RELEASED'
d['current_authority']='Owner Production V2.36.0 / Published Latest V2.36.2 / develop L2 scroll sticky fix PASS / Live next hop V2.36.1'
d['next_action']='Continue evidence-driven L2 product optimization on develop. Owner Production remains V2.36.0; when Owner chooses to upgrade, use the safe V2.36.0 -> V2.36.1 hop before promoting the staged V2.36.2 manifest. Assistant must not write Owner Production.'
change={
  'change_id':'P01-SCROLL-STICKY-OVERLAP-FIX-20260901','type':'BUG FIX / SHARED UX','base':'4ec93adad93977a519675b55806866c896bad09f','result':'MERGED TO DEVELOP / MACHINE PASS / NOT RELEASED','scope':['src/assets/workspace-domain-nav.css'],'schema_change':False,'migration':None,'version_change':False,
  'diagnostic_run':33491021229,'diagnostic_artifact':9793757582,'diagnostic_artifact_sha256':'93848135fbd3a141a0dc836cfdc37e25eb07ec78937b1acb9128056e5f9860d4','product_candidate':'ee568178804bf8c98abcf4b85f4dc20939712070','machine_gate':33491546225,'evidence_artifact':9793960558,'evidence_artifact_sha256':'ce5c98f1511c7d90b93468d763d26d7a7e5235a2e9db180ee63e2ef684c6c2df','product_pr':176,'develop_merge':'bd7f08b3fde91e4a20b0970deb5fec325e869159','repository_tree':'f3eb1ab9f8c5a6ea6a66cf4374a6fa5dc25b19d7','runtime_product_tree':'f6ec50d94dd5023050ccf1aedc3df879603cb5db','browser_gate':'390 + 1440 / START + CHANNELS + WATCH + TOPICS / MID + DEEP SCROLL / PASS','root_cause':'STICKY FILTER TOOLBAR TRANSPARENT + DESKTOP 8PX GAP','visual_readback':'PASS','sqlite_integrity_fk':'PASS','main_write':False,'production_write':False,'runner_main_write':False
}
d['current_change']=change
d['l2_scroll_sticky_fix']=change.copy()
d.setdefault('authority',{})['current_l2_develop_evidence']='docs/evidence/P01_SCROLL_STICKY_OVERLAP_FIX_20260901.md'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
