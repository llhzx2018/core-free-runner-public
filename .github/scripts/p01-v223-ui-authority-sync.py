from pathlib import Path
import json

root = Path('product')

p = root / 'VF_PROJECT.json'
d = json.loads(p.read_text(encoding='utf-8'))
d['status'] = 'V2.22.1 PRODUCTION RUNTIME / V2.23.0 UNIFIED SURFACE UI CANDIDATE'
d['production_version'] = '2.22.1'
d['working_version'] = '2.23.0'
d['target_release_version'] = '2.23.0'
d['schema_version'] = '2026082801'
d['working_schema_version'] = '2026082801'
d['current_working_branch'] = 'feature/p01-unified-surface-ui-v223-20260828'
d['current_phase'] = 'V2.23.0 UNIFIED SURFACE UI / FEATURE EXACT SOURCE PASS -> PR/DEVELOP GATE'
d['production_release'] = {
    'version': '2.22.1', 'tag': 'v2.22.1', 'release_id': 378275999,
    'release_source': 'a31bafac5efc97efa537b645f03bc99ed0ea5b43',
    'release_tree': '76aa42eb2e9abd0e0d543a7eba1241a3ff26eb59',
    'runtime_merge': '203d3c1236624ab846555167d217978694e11e88',
    'schema_version': '2026082801',
    'production_upgrade': 'PASS / OWNER UI 2026-08-28 13:52 +08:00'
}
d['current_change'] = {
    'change_id': 'P01-UNIFIED-SURFACE-UI-V223-20260828',
    'base': 'V2.22.1 PRODUCTION',
    'functional_source_commit': '35926810f1f59738b3b47f7dff690253f4da0e1b',
    'functional_machine_run': 33146698728,
    'functional_machine_result': 'PASS',
    'target_release': '2.23.0', 'schema_change': False, 'schema': '2026082801',
    'admin_root_dashboard': 'PASS', 'anonymous_root_unchanged': 'PASS',
    'classic_start_entry': 'PASS', 'channels_unified_shell': 'PASS',
    'watch_unified_shell': 'PASS', 'real_data_dashboard': 'PASS',
    'php_syntax': 'PASS', 'javascript_syntax': 'PASS', 'fresh_install': 'PASS',
    'surface_contract': 'PASS', 'sqlite_integrity': 'PASS', 'foreign_keys': 'PASS',
    'common_baseline': 'PASS / DRIFT 0 / UNKNOWN 0', 'production_write': False
}
d['candidate_version'] = '2.23.0'
d['candidate_schema_version'] = '2026082801'
d['candidate_state'] = 'FEATURE EXACT SOURCE MACHINE PASS / NOT RELEASED'
d['current_authority'] = 'Production V2.22.1 / Schema 2026082801; V2.23.0 Unified Surface UI source 35926810... / Machine 33146698728 PASS; not released yet'
d['next_action'] = 'V2.23.0 UI PR -> develop -> develop Exact Source Gate -> Release Candidate -> Release'
d.setdefault('authority', {})['unified_ui_machine_evidence'] = 'docs/evidence/P01_V2.23.0_UNIFIED_SURFACE_UI_MACHINE_20260828.md'
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

(root / 'docs/authority/CURRENT.md').write_text("""# P01 · VF Start · Current Authority Overlay

> 更新时间：2026-08-28  
> 状态：`CURRENT / V2.22.1 PRODUCTION / V2.23.0 UNIFIED SURFACE UI CANDIDATE`

## 1. Production Truth

```text
Owner Runtime: V2.22.1
Schema: 2026082801
Upgrade: 2.21.25 -> 2.22.1 / SUCCESS（Owner UI）
Formal Release: v2.22.1 / Release ID 378275999
Production Write by V2.23.0 work: NO
```

V2.22.1 已在 Owner 后台显示“当前版本 V2.22.1 / 最新版本 V2.22.1”，更新记录 `2.21.25 -> 2.22.1 success`。

## 2. V2.23.0 Unified Surface UI · Working Truth

V2.22.1 已有 Multi-Surface 数据与业务能力，但实际 UI 仍主要停留在旧导航 + Preview 页面，没有实现已确认设计稿中的统一产品体验。本轮把该差距视为真实未完成交付，而不是视觉微调。

```text
Branch: feature/p01-unified-surface-ui-v223-20260828
Functional Source: 35926810f1f59738b3b47f7dff690253f4da0e1b
Feature Exact Source Gate: 33146698728 / PASS
Target Release: V2.23.0
Schema Change: NO
Schema: 2026082801
```

## 3. UI Product Contract

- 管理员访问 `/`：进入统一 Multi-Surface Dashboard；
- 匿名访问 `/`：继续现有公开导航，不影响公开 SEO / 旧入口；
- `start.php`：显式进入成熟的 Classic Start 导航；
- `surfaces.php`：固定深色侧栏 + 顶部搜索 + Start / Channels / Watch 三列 Dashboard；
- `channels.php` / `watch.php`：共用统一 Shell，但保留各自业务心智；
- Dashboard 展示真实 P01 数据，不写死演示统计；
- 不增加新数据库、不复制 URL、不引入第三方 Feed/媒体托管。

## 4. Machine Evidence

Run `33146698728` = PASS：Exact Source / 6-file UI scope / PHP+JS syntax / Fresh Install / Schema / Surface Verify / Baseline / SQLite-FK / anonymous root / actual API login / admin root redirect / Classic Start / Channels+Watch Shell / real test-data projection 全部通过。

Canonical Evidence：`docs/evidence/P01_V2.23.0_UNIFIED_SURFACE_UI_MACHINE_20260828.md`。

## 5. Boundary

V2.23.0 当前是 Working Candidate，不是 Formal Release，也没有写入 Owner Production。V2.22.1 Release / Tag / Evidence 保持历史不变。

## 6. Next Gate

`Feature Source PASS -> PR to develop -> develop Exact Source PASS -> V2.23.0 Release Candidate -> Artifact/Update Gate -> main Promotion -> Release -> Owner Production Upgrade`。
""", encoding='utf-8', newline='\n')

(root / 'docs/authority/SSOT.md').write_text("""# P01 · VF Start · Current Engineering SSOT

> 状态：`CURRENT / V2.22.1 PRODUCTION + V2.23.0 UNIFIED UI WORKING CONTRACT`  
> Rebaseline：2026-08-28

## 1. Authority

`OWNER 最新明确裁决 -> Production Evidence -> Git Current Source -> Current RPD/SSOT/Acceptance -> 历史 Evidence`。

## 2. Runtime / Data

Production：V2.22.1 / Schema `2026082801`。V2.23.0 不改变 Schema、`links` URL Identity、`resource_surface_profiles` 稀疏模型、认证、备份、恢复或 Atomic Update 数据合同。

## 3. Unified Surface Shell

```text
Admin / -> surfaces.php -> Unified Dashboard
Anonymous / -> legacy public Start navigator
start.php -> classic Start navigator
Channels / Watch -> shared sidebar + topbar shell
```

管理员 Dashboard 与公开 `/` 必须隔离。

## 4. Dashboard Data Contract

Dashboard 只聚合现有 Repository / SurfaceRepository：Start 分类/常用网址；Channels 内容源/Rediscovery；Watch 想看/最近添加/随机；Footer 统计。不得建立 Shadow Table 或硬编码设计稿示例业务数据。

## 5. Page Contract

- `src/index.php`：管理员 302 到 `surfaces.php`；匿名继续旧导航；
- `src/start.php`：`VF_START_CLASSIC_ENTRY` 复用原 `index.php`；
- `src/surfaces.php`：Unified Dashboard；
- `src/surface.php`：Channels / Watch 统一 Shell；
- `src/assets/surface-home.css/js`：新 Shell 样式与交互；
- SurfaceRepository / Schema 不改。

## 6. Security / Privacy

私人 Surface metadata 继续服从 V2.22.1 Public Projection；UI 不得绕过 Session/CSRF。匿名根页不得进入 Owner Dashboard。

## 7. Machine Contract

Exact Source、PHP/JS syntax、Fresh Install、Surface Verify、Common Baseline、SQLite/FK、匿名根路由、真实 API Login、管理员根重定向、Classic Start bypass、Channels/Watch Shell 与真实测试数据投影必须 PASS。Feature Gate `33146698728 = PASS`。

## 8. Release Contract

目标版本 V2.23.0；这是 Material Product UI / IA 交付，Schema 保持 `2026082801`。Release 与 Owner Production Upgrade 为独立 Gate。
""", encoding='utf-8', newline='\n')

(root / 'docs/authority/ACCEPTANCE_MATRIX.md').write_text("""# P01 · VF Start · Current Acceptance Matrix

> Scope：`V2.23.0 Unified Surface UI`  
> Production Baseline：`V2.22.1 / Schema 2026082801`

| Gate | Result |
|---|---|
| V2.22.1 Owner Runtime Upgrade | PASS / Owner UI |
| UI Functional Exact Source | PASS / `35926810f1f59738b3b47f7dff690253f4da0e1b` |
| Exact Source Machine Gate | PASS / `33146698728` |
| Source Scope = 6 UI/route files | PASS |
| PHP Syntax / JavaScript Syntax | PASS |
| Fresh Install / Surface Verify | PASS |
| Common Product Baseline | PASS / DRIFT 0 / UNKNOWN 0 |
| SQLite integrity / FK | PASS / ok / 0 |
| Anonymous `/` stays public Start | PASS |
| Admin `/` -> `surfaces.php` | PASS |
| `start.php` Classic Start | PASS |
| Unified dark sidebar + topbar shell | PASS / machine-visible |
| Start / Channels / Watch real-data Dashboard | PASS |
| Channels / Watch unified shell | PASS |
| Schema Change | NO |
| Production Write | NO |
| PR -> develop | PENDING |
| develop Exact Source Gate | PENDING |
| V2.23.0 Release | PENDING |
| Owner Production Upgrade V2.23.0 | OUT / separate gate |

Machine-visible UI contract PASS 不等于像素级视觉证明；Owner 真实浏览器截图仍是最终 UA/UI 精修依据。
""", encoding='utf-8', newline='\n')

rpd = root / 'docs/authority/RPD.md'
s = rpd.read_text(encoding='utf-8')
s = s.replace('> 状态：`CURRENT / MULTI-SURFACE PRODUCT DEFINITION`', '> 状态：`CURRENT / MULTI-SURFACE PRODUCT DEFINITION + UNIFIED SURFACE UI`', 1)
if '## Unified Surface UI · V2.23.0' not in s:
    s += """

## Unified Surface UI · V2.23.0

V2.22.x 已证明 Multi-Surface 数据模型与独立页面可用，但“独立页面存在”不等于完成统一产品体验。V2.23.0 把已确认设计稿正式落到运行 UI：管理员首页使用深色侧栏、顶部全局搜索、Start / Channels / Watch 三列聚合 Dashboard 与真实资产统计；Start 保留经典导航入口；Channels / Watch 共用同一 Shell。匿名公开 `/` 不改变。

设计稿是方向 Authority，不把示例封面、数字、频道名硬编码成业务数据；真实界面必须由 P01 当前资产驱动。
"""
rpd.write_text(s, encoding='utf-8', newline='\n')

arch = root / 'docs/architecture/P01_MULTI_SURFACE_ARCHITECTURE.md'
s = arch.read_text(encoding='utf-8')
if '## Unified Surface Shell · V2.23.0' not in s:
    s += """

## Unified Surface Shell · V2.23.0

V2.23.0 在 Shared Data / Separate Surfaces 架构上增加统一 Presentation Shell，不增加数据权威：管理员 `/` -> `surfaces.php`；匿名 `/` 继续公开 Start；`start.php` 是 Classic Start；Channels / Watch 共用 Sidebar + Topbar。Dashboard 聚合现有 Repository，不建立 Shadow Cache/Table。
"""
arch.write_text(s, encoding='utf-8', newline='\n')

(root / 'docs/evidence/P01_V2.23.0_UNIFIED_SURFACE_UI_MACHINE_20260828.md').write_text("""# P01 · V2.23.0 Unified Surface UI · Machine Evidence

```text
Functional Source: 35926810f1f59738b3b47f7dff690253f4da0e1b
Base main: 45503b3a6483ea89a6b076822b3661a9b32bcbf4
Public Runner: 33146698728
Machine Result: PASS
Target Release: 2.23.0
Schema: 2026082801 / unchanged
Production Write: NO
```

验证覆盖：Exact Source/Branch/Base、6-file UI scope、全 PHP/JS syntax、Fresh Install、Surface Verify、Common Baseline、SQLite/FK、真实 Start/Channels/Watch 测试资产、匿名根页保持公开导航、真实 API 管理员登录、管理员根页 302 到 Unified Dashboard、Classic Start bypass、Channels/Watch unified shell 与最终 Regression。

本 Evidence 证明机器可执行 UI/route contract；不声称像素级视觉一致。
""", encoding='utf-8', newline='\n')

for rel, title in [
    ('README.md', '## V2.23.0 Unified Surface UI · Working Candidate'),
    ('docs/README.md', '## V2.23.0 Unified Surface UI · Current Working'),
    ('src/README.md', '## V2.23.0 Unified Surface UI · Working Runtime')
]:
    q = root / rel
    s = q.read_text(encoding='utf-8')
    if title not in s:
        block = f"\n{title}\n\n- Production Runtime：`V2.22.1` / Schema `2026082801`；\n- Working Functional Source：`35926810f1f59738b3b47f7dff690253f4da0e1b`；\n- Machine Gate：`33146698728 / PASS`；\n- 管理员 `/` 进入统一 Dashboard；匿名 `/` 保持公开 Start；`start.php` 保留 Classic Start；\n- Channels / Watch 使用统一 Shell；Schema 不变；\n- Target Release：`V2.23.0`，当前未发布、未写 Production。\n\n"
        pos = s.find('\n') + 1
        s = s[:pos] + block + s[pos:]
    q.write_text(s, encoding='utf-8', newline='\n')

ch = root / 'CHANGELOG.md'
s = ch.read_text(encoding='utf-8')
if '## VF Start V2.23.0 — Unified Surface UI · Unreleased' not in s:
    first = s.find('\n') + 1
    entry = """
## VF Start V2.23.0 — Unified Surface UI · Unreleased
- 修正 V2.22.x“Multi-Surface 能力已存在但主界面仍像旧导航/Preview”的产品交付缺口。
- 管理员根首页改为 Unified Surface Dashboard；匿名根首页继续公开导航。
- 新增深色固定侧栏、顶部全局搜索、Start / Channels / Watch 三列真实数据 Dashboard、今日发现与底部资产统计。
- `start.php` 保留 Classic Start；Channels / Watch 接入统一 Shell。
- 新增 `surface-home.css/js`；不改 Schema、不复制 URL、不新增媒体/Feed 数据源。
- Feature Exact Source `35926810f1f59738b3b47f7dff690253f4da0e1b`，Machine `33146698728 = PASS`。
- 当前仍为 Working Candidate，尚未发布 V2.23.0。

"""
    s = s[:first] + entry + s[first:]
ch.write_text(s, encoding='utf-8', newline='\n')
