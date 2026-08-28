from pathlib import Path
import json, os

source=os.environ['EXACT_SOURCE']
gate=int(os.environ['GATE_RUN'])
evidence='docs/evidence/P01_V2.24.0_UX_REBASELINE_MACHINE_20260828.md'

def prepend_once(path, marker, block):
    p=Path(path); text=p.read_text(encoding='utf-8')
    if marker in text: return
    p.write_text(block.rstrip()+'\n\n'+text,encoding='utf-8',newline='\n')

def append_once(path, marker, block):
    p=Path(path); text=p.read_text(encoding='utf-8')
    if marker in text: return
    p.write_text(text.rstrip()+'\n\n'+block.rstrip()+'\n',encoding='utf-8',newline='\n')

Path(evidence).write_text(f'''# P01 · V2.24.0 UX Rebaseline · Machine Evidence

> Date: 2026-08-28  
> Status: `PASS / WORKING CANDIDATE / NOT RELEASED`

## Exact Source

```text
Branch: feature/p01-ux-rebaseline-v224-20260828
Exact Source: {source}
Machine Run: {gate}
Machine Result: PASS
Owner Production: V2.23.0 / Schema 2026082801
Target Release: V2.24.0
Schema Change: NO
Production Write: NO
```

## Proven UX Contract

- Admin `/` -> unified Home; anonymous `/` stays the public Start navigator.
- Home is one task-oriented dashboard instead of three equal mini-app columns.
- Global Home search searches Start / Channels / Watch and does not redirect into the organizer.
- Admin `Start` is now a first-class view inside the shared Surface Shell.
- `start.php?classic=1` preserves Classic Start as an explicit compatibility view.
- Channels / Watch / Resource Organizer use the same Sidebar + Topbar shell and the same teal VF visual authority.
- Existing-content classification suggestions surface in Home/Organizer; no silent reclassification was introduced.
- “常用网址” is backed by real `click_count`; no fake recent-visit timestamp was invented.

## Machine Coverage

Run `{gate}` passed Exact Identity / 7-file UX scope / PHP+JS syntax / Fresh Install / Schema / Surface Contract / authenticated route tests / cross-surface search / unified Start / Classic compatibility / Channels / Watch / Organizer / Common Baseline / SQLite integrity / FK.

## Boundary

This evidence does not authorize Release or Production. Version files remain V2.23.0 until an explicit V2.24.0 Release Candidate gate.
''',encoding='utf-8',newline='\n')

summary=f'''## V2.24.0 UX Rebaseline · Working Candidate

- Owner Production Runtime：**V2.23.0 / Schema 2026082801**（Owner UI 已确认 `2.22.1 -> 2.23.0 success`）；
- Working Exact Source：`{source}`；
- Machine Gate：`{gate} / PASS`；
- 目标：把 Home / Start / Channels / Watch / 资源整理从“多个独立小系统”收敛成一个 P01 工作空间；
- Schema：不变；Release / Production：未执行。
'''
prepend_once('README.md','## V2.24.0 UX Rebaseline · Working Candidate',summary)
prepend_once('docs/README.md','## V2.24.0 UX Rebaseline · Current Working',summary.replace('## V2.24.0 UX Rebaseline · Working Candidate','## V2.24.0 UX Rebaseline · Current Working'))
prepend_once('CHANGELOG.md','## VF Start V2.24.0 — UX Rebaseline · Unreleased',f'''## VF Start V2.24.0 — UX Rebaseline · Unreleased
- 基于 Owner V2.23.0 真实使用截图重做 Multi-Surface UX：不再把 Start / Channels / Watch 当三个等权小产品并排展示。
- 新增共享 `SurfaceShell`，Home / Start / Channels / Watch / 资源整理使用同一侧栏、Topbar、搜索与 VF 青色视觉 Authority。
- Home 改成任务型首页：常用入口、继续内容、内容待整理、今日发现、资产概览；Surface 只是模式入口。
- 全局搜索改为真正跨 Surface 搜索，不再把“搜索一切”提交到 `surface-manager.php`。
- 管理员 `start.php` 进入统一 Start；`start.php?classic=1` 保留 Classic Start；匿名公开 Start 不变。
- 资源整理并入共享 Shell；Channels / Watch 空态会显示现有收藏归属建议并引导显式确认。
- 取消依赖紫/橙大面积 Surface 配色，统一回到 VF Start 青色主视觉。
- 不伪造“最近访问”：当前服务器只有可靠 `click_count`，统一 UI 使用“常用网址”。
- Exact Source `{source}` / Machine `{gate} PASS`；Schema `2026082801` 不变；当前未 Release / 未写 Production。
''')
prepend_once('docs/authority/CURRENT.md','## V2.24.0 UX Rebaseline · Current Working Truth',f'''# P01 · VF Start · Current Authority Overlay — V2.24 UX Rebaseline

## V2.24.0 UX Rebaseline · Current Working Truth

```text
Owner Production Runtime: V2.23.0
Owner Production Schema: 2026082801
Owner Upgrade: 2.22.1 -> 2.23.0 / SUCCESS
Formal Release: V2.23.0 / PASS
Working Branch: feature/p01-ux-rebaseline-v224-20260828
Working Exact Source: {source}
Machine Run: {gate} / PASS
Target Release: V2.24.0
Schema Change: NO
Release: NO
Production Write by V2.24 work: NO
```

Current product correction: P01 must feel like one system. Home is task-oriented; Start / Channels / Watch are resource modes; Resource Organizer is a shared workspace, not a fourth product. Global search remains in the product surface rather than entering an admin management page.
''')
append_once('docs/authority/RPD.md','## V2.24.0 UX Rebaseline',f'''## V2.24.0 UX Rebaseline

Owner V2.23.0 real-use evidence showed that “shared sidebar + three columns” still felt like three independent products. V2.24 changes the mental model from **three mini apps** to **one personal internet workspace with three resource modes**.

Required outcomes: task-oriented Home; one navigation/search/visual authority; Start itself in the shared Shell; Classic Start only as compatibility; Resource Organizer as the same-system inbox; explicit classification suggestions; cross-Surface global search; VF teal as the primary system color.
''')
append_once('docs/authority/SSOT.md','## V2.24.0 One-System UX Contract',f'''## V2.24.0 One-System UX Contract

Presentation authority is `src/app/SurfaceShell.php`. Private Home / Start / Channels / Watch / Resource Organizer consume this shared shell rather than duplicate Sidebar / Topbar markup. Public `/` remains the mature anonymous Start. Admin `start.php` is unified; `start.php?classic=1` is explicit compatibility. Global Home search reads the existing Repository/SurfaceRepository projection only. No Shadow Table, media store or Schema is introduced.

Machine Authority: `{source}` / Run `{gate}` PASS.
''')
append_once('docs/architecture/P01_MULTI_SURFACE_ARCHITECTURE.md','## 11. One-System Presentation Architecture · V2.24',f'''## 11. One-System Presentation Architecture · V2.24

```text
shared data authority -> SurfaceRepository -> SurfaceShell.php
                                         -> Home / Start / Channels / Watch
                                         -> Resource Organizer
```

The shell is shared; resource semantics remain separate. Home composes tasks and discovery rather than rendering three mini-app homepages. Classic Start remains an explicit compatibility path. Presentation/IA only; Schema stays `2026082801`.

Exact Source `{source}` / Machine `{gate}` PASS.
''')
append_once('docs/authority/ACCEPTANCE_MATRIX.md','## V2.24.0 UX Rebaseline Matrix',f'''## V2.24.0 UX Rebaseline Matrix

| Gate | Result |
|---|---|
| Owner Production V2.23.0 | PASS / Owner UI |
| V2.24 UX Exact Source | `{source}` |
| Final Head Machine Gate | PASS / `{gate}` |
| Shared SurfaceShell | PASS |
| Home task-oriented IA | PASS |
| Cross-Surface global search | PASS |
| Admin Start in shared Shell | PASS |
| Classic Start compatibility | PASS |
| Channels / Watch / Organizer shared Shell | PASS |
| Existing-content suggestions visible | PASS |
| Silent reclassification | NO |
| PHP / JavaScript Syntax | PASS |
| Fresh Install / Surface Verify | PASS |
| Common Baseline | PASS / DRIFT 0 / UNKNOWN 0 |
| SQLite integrity / FK | PASS / ok / 0 |
| Schema Change | NO |
| Release V2.24.0 | PENDING |
| Production Write | NO |
''')

p=Path('VF_PROJECT.json'); d=json.loads(p.read_text(encoding='utf-8'))
previous=d.get('current_change')
d['status']='V2.23.0 OWNER PRODUCTION / V2.24.0 UX REBASELINE CANDIDATE'
d['production_version']='2.23.0'; d['working_version']='2.24.0'; d['target_release_version']='2.24.0'
d['current_working_branch']='feature/p01-ux-rebaseline-v224-20260828'; d['current_phase']='V2.24.0 UX REBASELINE / FINAL EXACT SOURCE MACHINE PASS'
d['production_release']={'version':'2.23.0','tag':'v2.23.0','release_id':378293470,'release_source':'6e7d30e6ea0c8f5f70076a69b0d1e6fb9be620b2','release_tree':'8bc7b4c2f643566d3688ecdeda74a47c320cbc2f','runtime_merge':'8bbb51b38bddd769613b12dd6bf015b784c89f86','schema_version':'2026082801','production_upgrade':'PASS / OWNER UI 2026-08-28 15:14 +08:00'}
if previous: d['previous_change']=previous
d['current_change']={'change_id':'P01-UX-REBASELINE-V224-20260828','base':'V2.23.0 OWNER PRODUCTION','functional_source_commit':source,'functional_machine_run':gate,'functional_machine_result':'PASS','target_release':'2.24.0','schema_change':False,'schema':'2026082801','shared_shell':'PASS','home_task_ia':'PASS','cross_surface_search':'PASS','admin_start_unified':'PASS','classic_start_compatibility':'PASS','channels_unified':'PASS','watch_unified':'PASS','organizer_unified':'PASS','suggestion_onboarding':'PASS','silent_reclassification':False,'production_write':False}
d.setdefault('authority',{})['ux_rebaseline_machine_evidence']=evidence
d['candidate_version']='2.24.0'; d['candidate_schema_version']='2026082801'; d['candidate_state']='FINAL EXACT SOURCE MACHINE PASS / NOT RELEASED'
d['current_authority']=f'Owner Production V2.23.0 / Schema 2026082801; V2.24.0 UX Rebaseline {source} / Machine {gate} PASS; not released'
d['next_action']='V2.24.0 UX PR -> develop -> develop Exact Source Gate -> owner/release decision'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
