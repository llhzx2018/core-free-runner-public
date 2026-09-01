from pathlib import Path
import json, sys
root=Path(sys.argv[1])
p=root/'VF_PROJECT.json'
d=json.loads(p.read_text())
d['status']='V2.36.3 OWNER PRODUCTION / PUBLISHED / PRODUCTION CLOSURE PASS'
d['production_version']='2.36.3'
d['working_version']='2.36.3'
d['target_release_version']='2.36.3'
d['current_phase']='V2.36.3 PRODUCTION CLOSURE PASS / L2 PRODUCT OPTIMIZATION READY'
pub=dict(d['published_release'])
pub.update({
 'release_state':'PUBLISHED / OWNER INSTALLED / PRODUCTION CLOSURE PASS',
 'owner_production_runtime':'2.36.3','owner_production_schema':'2026082901',
 'owner_production_upgrade':'2.36.2 -> 2.36.3 / SUCCESS',
 'owner_version_readback':'Current V2.36.3 / Latest V2.36.3 / history 2.36.2 -> 2.36.3 success',
 'owner_browser_footer_readback':'V2.36.3 / PASS','owner_terminal_ui_last_check':'2026-09-01 21:35:48',
 'production_closure':'PASS','assistant_production_write':False})
d['published_release']=pub
d['production_release']=dict(pub)
cur=d.get('current_change',{})
cur.update({'result':'PUBLISHED / OWNER INSTALLED / PRODUCTION CLOSURE PASS','production_write':False,'runner_main_write':False})
d['current_change']=cur
auth=d.get('authority',{})
auth['current_production_evidence']='docs/evidence/P01_V2.36.3_OWNER_PRODUCTION_CLOSURE_20260901.md'
auth['current_formal_release_evidence']='docs/evidence/P01_V2.36.3_RELEASE_CLOSURE_20260901.md'
auth['current_l2_develop_evidence']='docs/evidence/P01_V2.36.3_OWNER_PRODUCTION_CLOSURE_20260901.md'
d['authority']=auth
d['formal_release_state']='V2.36.3 PUBLISHED / OWNER PRODUCTION CLOSURE PASS'
d['develop_state']='V2.36.3 PRODUCTION CLOSURE PASS / L2 PRODUCT OPTIMIZATION READY'
d['current_authority']='Owner Production V2.36.3 / Published Latest V2.36.3 / Production Closure PASS'
d['next_action']='继续 evidence-driven L2 Product Optimization；优先真实 Owner 截图/反馈与 Fresh Runtime 证据。不要自动 bump 新版本。'
d['owner_production_closure_evidence']={'version':'2.36.3','schema':'2026082901','current':'2.36.3','latest':'2.36.3','footer':'2.36.3','history':'2.36.2 -> 2.36.3 / success','last_check':'2026-09-01 21:35:48','screenshot_size':'1319x641','state':'PASS','assistant_production_write':False}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
block='''<!-- P01_V2363_OWNER_PRODUCTION_CLOSURE -->
## V2.36.3 Owner Production Closure · 2026-09-01

- Fresh Owner Readback：Current `V2.36.3` / Latest `V2.36.3`。
- 更新历史：`2.36.2 → 2.36.3 / success`。
- Last Check：`2026-09-01 21:35:48`。
- Footer：`VF Start · V2.36.3`。
- Schema：`2026082901`，无 Migration。
- Formal Source / Tag：`718e043e3715ef7b21849bc08634fca89bf92c1f` / `v2.36.3`；Release ID `380449563`。
- Runtime Tree：`820724b585cb59864211f77c4fb33537b2345029`。
- core-updates live：`650935cc9d71570a7ab7a0dd1c615ea5e3bf74bf`；本次 Closure 不修改更新源。
- Owner Production Write：由 Owner 自己通过在线升级完成；Assistant direct Production write = **NO**。
- Verdict：**PRODUCTION CLOSURE PASS**。V2.36.2 已成为历史 Production，V2.36.3 为 Current Production Truth。
- Next：恢复 L2 Product Optimization；只按真实 Owner 反馈 / Fresh Runtime 证据继续，不自动创建 V2.36.4。

> 以下旧段落保留历史证据；如与本段冲突，以本段为 Current Production Authority。

'''
for rel in ['docs/authority/CURRENT.md','docs/handoff/CURRENT_STATE.md']:
 q=root/rel; old=q.read_text()
 if '<!-- P01_V2363_OWNER_PRODUCTION_CLOSURE -->' not in old:
  lines=old.splitlines(True); pos=1 if lines and lines[0].startswith('# ') else 0
  q.write_text(''.join(lines[:pos])+('\n' if pos else '')+block+''.join(lines[pos:]))
ev=root/'docs/evidence/P01_V2.36.3_OWNER_PRODUCTION_CLOSURE_20260901.md'
ev.write_text('''# P01 · V2.36.3 Owner Production Closure · 2026-09-01

## Verdict

**PASS — Owner Production has successfully upgraded from V2.36.2 to V2.36.3.**

## Fresh Owner readback

- Current: `V2.36.3`
- Latest: `V2.36.3`
- History: `2.36.2 -> 2.36.3 / success`
- Last Check: `2026-09-01 21:35:48`
- Footer: `VF Start · V2.36.3`
- Screenshot size observed in chat: `1319x641`
- Assistant direct Production write: `NO`

The screenshot was supplied directly by the Owner in the active conversation. No screenshot SHA-256 is asserted because this closure does not bind an independently materialized screenshot file.

## Engineering identity retained

- Formal Source / Tag: `718e043e3715ef7b21849bc08634fca89bf92c1f` / `v2.36.3`
- Release ID: `380449563`
- Runtime Tree: `820724b585cb59864211f77c4fb33537b2345029`
- Schema: `2026082901`
- core-updates live: `650935cc9d71570a7ab7a0dd1c615ea5e3bf74bf`
- Online update: strict `V2.36.2 -> V2.36.3`
- Release Remote Truth R2: `33504969865` PASS
- Main Authority Remote Closure: `33506764054` PASS

## Product outcome

V2.36.3 closes the V2.36.2 P0 dual-shell regression by restoring ONE FRONTEND semantics and also contains the shared sticky-toolbar overlap correction. Owner Production now matches Published Latest.

## Boundary

This evidence records Owner-observed Production state only. The assistant did not directly write Production data or files.
''')
