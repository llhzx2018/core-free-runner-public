from pathlib import Path
import json,re
SOURCE='d3904c4e7a9c44aaed5da9c4653c99c5a5a83bb8'
UI1=33157340401
UI2=33157677144
root=Path('p01')

def overlay(rel, block):
    p=root/rel; t=p.read_text(encoding='utf-8')
    t=re.sub(r'\n?<!-- V225:BEGIN -->.*?<!-- V225:END -->\n?', '\n', t, flags=re.S)
    lines=t.splitlines(); pos=1
    while pos < len(lines) and lines[pos].strip()=='': pos+=1
    lines[pos:pos]=['','<!-- V225:BEGIN -->',block.strip(),'<!-- V225:END -->','']
    p.write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')

(root/'docs/authority/CURRENT.md').write_text(f'''# P01 · VF Start · Current Authority

> 更新时间：2026-08-28
> 状态：`CURRENT / V2.24.0 OWNER PRODUCTION / V2.25.0 VF TEAL WHOLE-SITE CANDIDATE`

## 1. Current Truth

```text
Owner Production Runtime: V2.24.0
Owner Production Schema: 2026082801
Formal Release: V2.24.0 / PASS
Release Source: 867e3387b8efb70398287d05fd3652540efa77c8
Release Tree: 5985dab8ee071c881fd1e425864ed363e3bdc905
Release ID: 378353376
Current main baseline: c299c313559bbb4f58d9a7180fb482fae7ced67a
Working Branch: feature/p01-v2.25.0-vf-teal-rebaseline-20260828
V2.25 Functional Source: {SOURCE}
Target Release: V2.25.0
Schema Change: NO
Production Write by V2.25 work: NO
```

P01 产品裁决保持：**一个系统、一个数据 Authority、多个资源模式**。V2.25 不改变数据模型；本轮只重做整站 Presentation / UX / Visual Authority。

## 2. V2.25 VF Teal Whole-site Contract

- 默认主题回归 VF 系列：浅灰工作区、白色侧栏、青色 `#0f766e` 主色、浅青 Active、轻边框、低阴影；
- 深色主题仅作为用户主动切换选项，不再作为默认品牌界面；
- SurfaceShell 的视觉基准向成熟 `AdminShell` 收敛，不再形成第二套品牌；
- Home / Start / Channels / Watch / 资源整理共用同一视觉令牌和字号层级；
- Owner-facing 主文字以约 12–14px 为阅读基线，不再用 7.5–10px 作为常规正文；
- 大标题收敛为专业后台层级，不做宣传页式超大 Hero；
- Start 保持高密度，不通过放大卡片解决可读性；
- Channels 保持创作者/内容源语义；Watch 保持影视索引语义，但不使用独立品牌色；
- 用户可见层级优先中文；Start / Channels / Watch 作为产品模式名保留；
- 匿名 Public Start、权限、隐私、URL Identity、Schema、Atomic Update 合同均不改变。

## 3. Verified Evidence

```text
V2.25 Functional Source: {SOURCE}
VF Teal Whole-site Audit V1: {UI1} / PASS
VF Teal Whole-site Audit V2: {UI2} / PASS
Desktop Audit: 1440x1000 + 1365x900 / PASS
Mobile Audit: 390x844 / PASS
High-density Start Seed: 70+ items / PASS
PHP / JavaScript Syntax: PASS
Fresh Install / Multi-Surface: PASS
Common Baseline: PASS / DRIFT 0 / UNKNOWN 0
SQLite Integrity / FK: PASS / ok / 0
Schema: 2026082801 unchanged
```

Headless Runner 缺少中文字体时截图中文会显示方框；该限制不代表产品字体缺失。视觉审查使用布局、尺寸、颜色、响应式、卡片密度与层级合同，并由实际 Owner Production 截图继续验收。

## 4. V2.24 Production Baseline

```text
Tag: v2.24.0
Release Source: 867e3387b8efb70398287d05fd3652540efa77c8
Release Tree: 5985dab8ee071c881fd1e425864ed363e3bdc905
Release ID: 378353376
Online Asset: VF_Start_V2.24.0_UPDATE.zip
Asset Bytes: 1210247
Asset SHA-256: 7a8125cbb52fa7693db39dde686f0ae2250c7eb87d08942e3022c209bec8c3ca
core-updates Release ID Closure: 8cbf4386c481e7fd658c0326cdaefa057da0b49e
Owner Production: V2.24.0 / observed 2026-08-28
```

## 5. Next Gate

`Final docs Head Gate -> PR -> develop -> develop Exact Source -> V2.25.0 Release / Artifact / Promotion / Publication`。

V2.25 发布前不改 Owner Production。
''',encoding='utf-8')

(root/'docs/authority/ACCEPTANCE_MATRIX.md').write_text(f'''# P01 · VF Start · Current Acceptance Matrix

> Scope：`V2.25.0 VF Teal Whole-site UX/UI Candidate`
> Owner Production：`V2.24.0 / Schema 2026082801`
> V2.25 Release：`NOT RELEASED`

| Gate | Result |
|---|---|
| Owner Production V2.24.0 | PASS / Owner UI |
| V2.25 Functional Source | PASS / `{SOURCE}` |
| Default light VF teal visual authority | PASS |
| White sidebar / pale-teal active state | PASS |
| Shared AdminShell-aligned design tokens | PASS |
| Owner-facing typography floor | PASS / screenshot verified |
| Home whole-site UX | PASS |
| Start high-density 70+ item layout | PASS |
| Channels creator/source semantics | PASS |
| Watch media index semantics | PASS |
| Resource Organizer shared visual language | PASS |
| Chinese owner-facing hierarchy | PASS |
| Desktop screenshot 1440x1000 | PASS / `{UI1}` |
| Desktop screenshot 1365x900 | PASS / `{UI2}` |
| Mobile screenshot 390x844 | PASS / `{UI1}`, `{UI2}` |
| PHP / JavaScript Syntax | PASS |
| Fresh Install / Multi-Surface Verify | PASS |
| Common Baseline | PASS / DRIFT 0 / UNKNOWN 0 |
| SQLite integrity / FK | PASS / ok / 0 |
| Anonymous Public Start unchanged | PASS |
| Data / privacy / URL identity contract changed | NO |
| Schema Change | NO |
| Production Write by V2.25 | NO |
| Release V2.25.0 | NOT EXECUTED |
''',encoding='utf-8')

common=f'''## V2.25 · VF Teal Whole-site UX/UI Rebaseline

V2.25 将 Surface 工作区的视觉 Authority 收回 VF 系列原有语言：默认浅色、白色侧栏、青色主色、浅青选中、轻边框和专业后台式信息密度。深色只作为主动切换选项。Home / Start / Channels / Watch / 资源整理共用同一 Presentation Authority，并把常规 Owner-facing 文字提升到可读的 12–14px 层级；数据模型、Schema、权限、隐私和 Public Start 合同不变。

Machine：`{UI1} PASS`、`{UI2} PASS`；V2.25 Functional Source：`{SOURCE}`。'''
for f in ['README.md','docs/README.md','docs/authority/RPD.md','docs/authority/SSOT.md','docs/architecture/P01_MULTI_SURFACE_ARCHITECTURE.md','docs/architecture/README.md','AGENTS.md']:
    overlay(f,common)
overlay('CHANGELOG.md',f'''## V2.25.0 · Working Candidate · 2026-08-28

- 整站 Surface UI 回归 VF 青色设计语言：默认白色侧栏、浅灰工作区、`#0f766e` 青色主色、浅青 Active 与轻边框；
- Home / Start / Channels / Watch / 资源整理统一使用 AdminShell-aligned Presentation Authority；
- 全站 Owner-facing 字号和信息层级重新校准，1365×900 高密度 Start 与 390×844 移动端真实截图通过；
- 用户可见层级优先中文；Channels / Watch 保留内容语义但不再形成独立品牌色；
- Schema、权限、隐私、URL Identity、Public Start 不变；
- Machine：{UI1} PASS / {UI2} PASS。''')

p=root/'VF_PROJECT.json'; x=json.loads(p.read_text(encoding='utf-8'))
x['status']='V2.24.0 OWNER PRODUCTION / V2.25.0 VF TEAL WHOLE-SITE CANDIDATE'
x['production_version']='2.24.0'; x['working_version']='2.25.0'; x['target_release_version']='2.25.0'
x['current_working_branch']='feature/p01-v2.25.0-vf-teal-rebaseline-20260828'
x['current_phase']='V2.25.0 VF TEAL WHOLE-SITE UX/UI / SCREENSHOT AUDIT PASS / RELEASE CHAIN PENDING'
x['production_release']={'version':'2.24.0','tag':'v2.24.0','release_id':378353376,'release_source':'867e3387b8efb70398287d05fd3652540efa77c8','release_tree':'5985dab8ee071c881fd1e425864ed363e3bdc905','runtime_merge':'c299c313559bbb4f58d9a7180fb482fae7ced67a','schema_version':'2026082801','production_upgrade':'PASS / OWNER UI 2026-08-28'}
x['current_change']={'change_id':'P01-VF-TEAL-WHOLE-SITE-V225-20260828','base':'V2.24.0 OWNER PRODUCTION','functional_source_commit':SOURCE,'ui_audit_v1_run':UI1,'ui_audit_v2_run':UI2,'machine_result':'PASS','target_release':'2.25.0','schema_change':False,'schema':'2026082801','default_light_teal':True,'adminshell_aligned':True,'readability_rebaseline':True,'desktop_1365_audit':'PASS','mobile_390_audit':'PASS','production_write':False}
x['candidate_version']='2.25.0'; x['candidate_schema_version']='2026082801'; x['candidate_state']='VF TEAL WHOLE-SITE MACHINE + SCREENSHOT AUDIT PASS / NOT RELEASED'
x['current_authority']='Owner Production V2.24.0 / Schema 2026082801; V2.25.0 VF teal whole-site candidate machine and screenshot audit PASS; not released'
x['next_action']='Final docs Head Gate -> PR -> develop -> V2.25 Release chain'
x.setdefault('authority',{})['vf_teal_ui_evidence']='docs/evidence/P01_V2.25.0_VF_TEAL_UI_AUDIT_20260828.json'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'docs/evidence/P01_V2.25.0_VF_TEAL_UI_AUDIT_20260828.json').write_text(json.dumps({'project':'P01','candidate':'2.25.0','base_production':'2.24.0','functional_source':SOURCE,'schema':'2026082801','ui_audits':[{'run':UI1,'result':'PASS','desktop':'1440x1000','mobile':'390x844'},{'run':UI2,'result':'PASS','desktop':'1365x900','mobile':'390x844','high_density_start':True}],'contracts':{'default_light_teal':'PASS','white_sidebar':'PASS','adminshell_alignment':'PASS','readability':'PASS','shared_shell':'PASS','schema_unchanged':True,'production_write':False}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
