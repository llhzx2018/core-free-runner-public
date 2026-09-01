#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "product")

PROD_MAIN = "4a41d3533fe8450c3f491d5aaf28417536012ba0"
DEVELOP = "f036cd0f5833ef2639970db336c62393cf43cce0"
SCHEMA = "2026082901"
EVIDENCE = "docs/evidence/P01_L2_PERSONAL_INTERNET_JOURNEY_WAVE_1_13_20260902.md"

waves = [
    (1, 202, 33555093483, "首次使用 + 真正全局搜索", "a04631226e5be8f37388bbf0eb7fb7d34027a409"),
    (2, 203, 33555366786, "Ctrl/Cmd+K + 搜索相关性", "65abfb77eb66202c61f13940ec188b99b6c9b125"),
    (3, 204, 33556060719, "Browser Helper 三步连接", "564b437fdeb13d3fe09c033d08fdd0518779e98e"),
    (4, 205, 33556510987, "Browser Helper 1.6.5 日常闭环", "b9c69eedec17979d2897e85f40d11cabfe1199e2"),
    (5, 206, 33556702984, "网址健康中心统一入口", "65e6b882cee2ac20eb61bc3c959f16af005ef7a4"),
    (6, 207, 33559741011, "首页数据安全状态", "00a96a449a6f78b44b705555a51be494d64e1130"),
    (7, 208, 33560626141, "URL-first 导航新增", "bb1b9723919841fe5ae2148ab47c042b09258b9a"),
    (8, 209, 33560836974, "搜索零结果 URL → 保存", "7de314fc5acd4e3a85bc9760799fede3cd1265ab"),
    (9, 210, 33561083446, "浏览器书签导入 onboarding-first", "e65d75b2eb4e425b2b35a25d044dcc94c8915fd8"),
    (10, 211, 33561344420, "移入回收站后 30 秒内联撤销", "923368dc7152b6063c0e4d1aeec3afc849bfff18"),
    (11, 213, 33563667758, "待整理 = is_pending + suggest-only 现有分类建议", "7054ac145be3dd8bbfb8978c4e5356167e71aa61"),
    (12, 214, 33563991791, "Mobile Quick Save foundation / 私人待整理 capture", "8a8bb39b55f90b60cef86be21b8bd47bf5c49552"),
    (13, 215, 33564224738, "首页最多 6 条真正最近使用", DEVELOP),
]


def read(rel):
    return (root / rel).read_text(encoding="utf-8")


def write(rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def sub_once(rel, pattern, replacement, flags=0):
    text = read(rel)
    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"expected one replacement in {rel}, got {count}: {pattern}")
    write(rel, new)


current_block = f'''<!-- P01_L2_WAVE13_CURRENT_TRUTH -->
## Current Truth · V2.36.5 Production + L2 Wave 1–13

```text
Owner Production: V2.36.5
Owner Schema: {SCHEMA}
Published Latest: V2.36.5
Production main: {PROD_MAIN}
V2.36.5 Formal Source: ef86eba16aec71c1d0dabc16ad23089a78ee5057
V2.36.5 Runtime Tree: a7f472ec1f449ada1152d271f2723c52e7b58144
Current develop before docs checkpoint: {DEVELOP}
Develop state: L2 Product Optimization Wave 1–13 / PERSONAL INTERNET JOURNEY PASS / UNRELEASED / DEVELOP ONLY
Browser Helper: 1.6.5 on develop
Develop VERSION / src/VERSION.txt: 2.36.4 (historical working-branch value; NOT Production Authority)
Personal Internet Journey Closure R3: 33565412715 / PASS
Formal release candidate after Wave 13: NONE
Assistant direct Production write: NO
```

V2.36.5 已完成 Owner Production Closure。`develop` 与 `main` 有历史分叉，因此 **Production 版本必须读取 main / Owner Production Authority，不得用 develop 的 VERSION 文件反推生产版本**。Wave 1–13 均只在 `develop`，未进入 main / Tag / Release / core-updates / Owner Production。

Wave 1–13 的大众用户主链已由 Personal Internet Journey Closure R3 `33565412715` 验证 PASS；R1 `33564418437` 与 R2 `33565270107` 均为静态 Harness 断言定位错误，失败证据保留，不覆盖 Product Truth。

当前 L2 证据：[`docs/evidence/P01_L2_PERSONAL_INTERNET_JOURNEY_WAVE_1_13_20260902.md`](docs/evidence/P01_L2_PERSONAL_INTERNET_JOURNEY_WAVE_1_13_20260902.md)。

'''
sub_once(
    "docs/authority/CURRENT.md",
    r"<!-- P01_L2_WAVE10_CURRENT_TRUTH -->.*?(?=<!-- P01_V2364_OWNER_PRODUCTION_CLOSURE -->)",
    current_block,
    re.S,
)

handoff_block = f'''<!-- P01_L2_WAVE13_HANDOFF_CURRENT -->
## Current Handoff · V2.36.5 Production / L2 Wave 1–13 / Journey PASS · 2026-09-02

- Owner Production / Published Latest：`V2.36.5`；Production Closure **PASS**。
- Product main：`{PROD_MAIN}`；Schema `{SCHEMA}`。
- Current develop before docs checkpoint：`{DEVELOP}`；Wave 1–13 **UNRELEASED / DEVELOP ONLY**。
- Personal Internet Journey Closure：R3 `33565412715` **PASS**；R1 `33564418437` / R2 `33565270107` 保留为 Harness-only 历史。
- Browser Helper：`1.6.5` on develop。
- develop `VERSION` / `src/VERSION.txt` = `2.36.4` is historical working-branch value only; do not use it as Production Authority。
- Next：继续普通 L2，但默认以真实 Owner 使用反馈、BUG、别扭 UX 为输入，不再横向扩张功能清单；Android PWA Share Target 仅为以后可选项，不构成当前承诺。
- main / Tag / Release / core-updates / Owner Production：本 checkpoint **NO WRITE**。

> 以下旧段落保留历史证据；与本段冲突时，以本段 + `docs/authority/CURRENT.md` 为准。

'''
sub_once(
    "docs/handoff/CURRENT_STATE.md",
    r"<!-- P01_L2_WAVE10_HANDOFF_CURRENT -->.*?(?=<!-- P01_V2364_OWNER_PRODUCTION_CLOSURE -->)",
    handoff_block,
    re.S,
)

# Current overlays in historical long-form authority docs: update overlay only.
overlay_old = (
    "> Develop before this docs checkpoint：`923368dc7152b6063c0e4d1aeec3afc849bfff18`，"
    "L2 Wave 1–10 **UNRELEASED / DEVELOP ONLY**，Browser Helper `1.6.5`。"
)
overlay_new = (
    f"> Develop before this docs checkpoint：`{DEVELOP}`，L2 Wave 1–13 **UNRELEASED / DEVELOP ONLY**，"
    "Browser Helper `1.6.5`；Personal Internet Journey R3 `33565412715` **PASS**。"
)
for rel in ["docs/authority/ACCEPTANCE_MATRIX.md", "docs/authority/RPD.md", "docs/authority/SSOT.md"]:
    text = read(rel)
    if overlay_old not in text:
        raise SystemExit(f"overlay anchor missing in {rel}")
    write(rel, text.replace(overlay_old, overlay_new, 1))

functional_old = (
    "> Production remains `V2.36.5`; develop `923368dc7152b6063c0e4d1aeec3afc849bfff18` adds Wave 1–10 as **UNRELEASED / DEVELOP ONLY**. "
    "These waves preserve this contract's single URL/Data Authority and add no second save/search/backup/recovery system. Browser Helper component on develop is `1.6.5`."
)
functional_new = (
    f"> Production remains `V2.36.5`; develop `{DEVELOP}` adds Wave 1–13 as **UNRELEASED / DEVELOP ONLY**. "
    "These waves preserve this contract's single URL/Data Authority and add no second save/search/backup/recovery system. "
    "Browser Helper component on develop is `1.6.5`; Personal Internet Journey R3 `33565412715` is **PASS**."
)
text = read("docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md")
if functional_old not in text:
    raise SystemExit("functional overlay anchor missing")
write("docs/authority/P01_FUNCTIONAL_CONTRACT_20260829.md", text.replace(functional_old, functional_new, 1))

# Machine authority: mutate only existing current-state structures plus explicit journey evidence keys.
p = root / "VF_PROJECT.json"
data = json.loads(p.read_text(encoding="utf-8"))
if data.get("production_version") != "2.36.5" or data.get("schema_version") != SCHEMA:
    raise SystemExit("production/schema authority drift")
if data.get("working_version") != "2.36.4":
    raise SystemExit("historical working version drift")
data["current_phase"] = "V2.36.5 OWNER PRODUCTION CLOSURE PASS / L2 PRODUCT OPTIMIZATION WAVE 1-13 / PERSONAL INTERNET JOURNEY PASS"
cc = data.get("current_change")
if not isinstance(cc, dict):
    raise SystemExit("current_change missing")
cc["change_id"] = "P01-L2-PRODUCT-OPT-WAVE-1-13-JOURNEY-CLOSURE-20260902"
cc["type"] = "PRODUCT OPTIMIZATION / PERSONAL INTERNET JOURNEY CLOSURE / DEVELOP ONLY"
cc["production_main"] = PROD_MAIN
cc["production_version"] = "2.36.5"
cc["develop_exact_source_before_docs_checkpoint"] = DEVELOP
cc["product_prs"] = [w[1] for w in waves]
cc["product_gates"] = [w[2] for w in waves]
cc["journey_closure"] = "PASS"
cc["journey_gate_r3"] = 33565412715
cc["journey_harness_failures"] = [33564418437, 33565270107]
cc["schema_change"] = False
cc["migration"] = None
cc["version_change"] = False
cc["release"] = False
cc["main_write"] = False
cc["production_write"] = False
cc["runner_main_write"] = False
auth = data.get("authority")
if not isinstance(auth, dict):
    raise SystemExit("authority missing")
auth["current_l2_develop_evidence"] = EVIDENCE
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Checkpoint: intentionally concise current snapshot; older Wave 1-10 evidence remains immutable.
rows = "\n".join(
    f"| {wave} | #{pr} | `{gate}` PASS | {outcome} | `{merge}` |"
    for wave, pr, gate, outcome, merge in waves
)
checkpoint = f'''# P01 · L2 Product Optimization Checkpoint · 2026-09-02

## Authority

- Owner Production / Published Latest：`V2.36.5` / Production Closure PASS。
- Product main：`{PROD_MAIN}`。
- Schema：`{SCHEMA}` / no migration。
- Develop exact source before this docs checkpoint：`{DEVELOP}`。
- Browser Helper：`1.6.5` on develop。
- Wave 1–13：**UNRELEASED / DEVELOP ONLY**。
- Personal Internet Journey Closure：R3 `33565412715` **PASS**。
- Develop `VERSION` / `src/VERSION.txt` remain `2.36.4`; this is a historical working-branch value, **not** current Production Authority。
- No formal release candidate exists after Wave 13; do not auto-release。

## Wave 1–13

| Wave | PR | Gate | Product outcome | Develop merge |
|---:|---:|---:|---|---|
{rows}

## Personal Internet Journey Closure

The current develop source was checked as one continuous personal-internet journey:

`首次进入/书签导入 → 全局搜索 → URL/手机快速收藏 → 私人待整理 → suggest-only 分类整理 → 网址健康 → 最近使用 → 备份安全 → 回收站撤销`

- R1 `33564418437`：**FAIL / HARNESS ONLY**。Gate 把 `transfer_preview` / `transfer_apply` 错误要求在 `transfer.php`；真实调用位于 `assets/transfer.js`，产品导入与恢复点合同未缺失。
- R2 `33565270107`：**FAIL / HARNESS ONLY**。Gate 要求不存在的 `data-web-search-fallback` / `data-save-search-url` 属性；真实 Search→Save 合同使用 `searchUrlCandidate` / `data-prefill-url` / “保存这个网址” / Google fallback。
- R3 `33565412715`：**PASS**。Exact develop fence、PHP lint、首次导入、搜索、快速收藏、待整理/分类、健康/备份、最近使用/安全删除、版本边界全部 PASS。

R1/R2 失败证据保留，不删除、不改写；R3 是本次 Journey Closure Authority。此 Gate 验证的是 develop 产品合同与运行时静态/语义闭环，不等同于 Owner Production 部署。

## Product Outcome

Wave 1–13 已把 P01 的普通用户主链收束为：

`导入 → 收藏/快速捕获 → 查找 → 使用 → 整理 → 健康 → 备份/恢复`

关键新增收口：真实 `is_pending` Inbox、只建议不自动重排的现有分类建议、跨平台 Quick Save foundation、首页轻量最近使用。原则仍是单一 URL/Data Authority；不新增第二套搜索、收藏、分类、恢复或数据系统。

## Release Boundary

- Product src changes are already merged to develop in PR #202–#211 and #213–#215.
- PR #212 is the earlier docs-only Wave 1–10 checkpoint and is not a product wave.
- This Wave 1–13 checkpoint changes documentation / machine authority only.
- VERSION / `src/VERSION.txt`: NO CHANGE (`2.36.4` historical develop value).
- Schema / Migration: NO CHANGE.
- main / Tag / Release / core-updates / Owner Production: NO WRITE.
- Next：保持 L2，以真实 Owner 使用中的 BUG / 别扭 UX / 阻塞为主要输入；不默认继续横向加功能，也不自动 Release。
'''
write("docs/authority/P01_L2_PRODUCT_OPT_CHECKPOINT_20260902.md", checkpoint)

handoff = f'''# P01 · L2 Current Handoff Checkpoint · 2026-09-02

## Start Here

Continue from `docs/authority/P01_L2_PRODUCT_OPT_CHECKPOINT_20260902.md` and `{EVIDENCE}`.
The older `docs/evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md` remains immutable historical checkpoint evidence.

## Current Truth

- Repository：`llhzx2018/vf-start`。
- Runtime：L2 Product Optimization。
- Owner Production / Published Latest：`V2.36.5`。
- main：`{PROD_MAIN}`。
- develop before docs checkpoint：`{DEVELOP}`。
- Browser Helper：`1.6.5` on develop。
- Wave 1–13：UNRELEASED / DEVELOP ONLY。
- Personal Internet Journey Closure R3：`33565412715` PASS。
- Schema：`{SCHEMA}`。
- develop VERSION files still read `2.36.4`; never use them to override Production V2.36.5.

## Closed L2 Wave

Product PR #202–#211 and #213–#215 have merged with their exact gates PASS. PR #212 is docs-only. Journey R3 is PASS. Do not re-run these gates unless new evidence shows a regression.

## Current Product Center

P01 now has a coherent ordinary-user loop:

`导入 → 收藏/快速捕获 → 查找 → 使用 → 整理 → 健康 → 备份/恢复`

Wave 11 delivered suggest-only category recommendations inside the real Pending inbox. Wave 12 delivered a shared private-Pending mobile quick-save foundation. Wave 13 added only six recent-use items to Home without creating a second navigation wall.

## Next Product Direction

Continue from real Owner usage, bugs, awkward UX, or broken daily workflow. Do **not** invent a Wave 14 merely to keep adding features.

Android PWA Share Target can be revisited later as an optional layer over `quick-save.php`; it is not a current commitment and must not be presented as cross-platform iOS support. Tags / smart collections remain restrained; no complex rules engine or AI semantic-search expansion by default.

## Hard Boundaries

No main / Tag / Release / core-updates / Owner Production write from ordinary L2 work. No automatic version bump. No second frontend, second URL authority, second save system, or silent automatic reclassification of Owner data.
'''
write("docs/handoff/P01_L2_CURRENT_CHECKPOINT_20260902.md", handoff)

# Evidence package for current L2 truth.
evidence_rows = "\n".join(
    f"| {wave} | #{pr} | `{gate}` PASS | `{merge}` | {outcome} |"
    for wave, pr, gate, outcome, merge in waves
)
evidence = f'''# P01 · L2 Personal Internet Journey · Wave 1–13 Evidence · 2026-09-02

## Exact Authority

- Owner Production / Published Latest：`V2.36.5`。
- Production main：`{PROD_MAIN}`。
- Production Formal Source：`ef86eba16aec71c1d0dabc16ad23089a78ee5057`。
- Production Runtime Tree：`a7f472ec1f449ada1152d271f2723c52e7b58144`。
- Schema：`{SCHEMA}`。
- Develop exact source before docs closure：`{DEVELOP}`。
- Browser Helper：`1.6.5` on develop。
- Develop `VERSION` / `src/VERSION.txt`：`2.36.4` historical working-branch value only; **NOT Production Authority**。
- State：Wave 1–13 **UNRELEASED / DEVELOP ONLY**；no formal release candidate。

## Product Wave Evidence

| Wave | PR | Gate | Develop merge | Outcome |
|---:|---:|---:|---|---|
{evidence_rows}

PR #212 is intentionally excluded from the product-wave sequence because it is the earlier docs-only Wave 1–10 Current Truth checkpoint.

## Personal Internet Journey Closure

Target journey:

`第一次进入 → 书签导入 → 全局搜索 → 快速收藏 → 待整理 → 分类建议 → 网址健康 → 最近使用 → 备份安全 → 误删撤销`

### R1 · `33564418437` · FAIL / HARNESS ONLY

- Exact develop fence：PASS。
- Runtime lint：PASS。
- Failure：Harness incorrectly required `transfer_preview` / `transfer_apply` to appear in `src/transfer.php`.
- Actual authority：those calls live in `src/assets/transfer.js`; `transfer.php` contains the user-facing browser import and recovery-point contract.
- Product mutation caused by R1：NONE。

### R2 · `33565270107` · FAIL / HARNESS ONLY

- First-use / import journey：PASS。
- Failure：Harness required nonexistent `data-web-search-fallback` / `data-save-search-url` attribute names.
- Actual authority：Search→Save is implemented with `$searchUrlCandidate`, `data-prefill-url`, “保存这个网址”, direct-open, and normal Google fallback.
- Product mutation caused by R2：NONE。

### R3 · `33565412715` · PASS

All closure steps PASS:

1. Exact develop fence；
2. Runtime PHP lint；
3. First-use and browser-bookmark import；
4. Personal/global search and Search→Save fallback；
5. Browser/mobile capture sharing private Pending authority；
6. Real Pending + suggest-only classification；
7. Health center + BackupManager Home status；
8. Home recent use + safe-delete inline undo；
9. `VERSION` / `src/VERSION.txt` boundary unchanged at historical develop `2.36.4`。

Verdict：**P01 PERSONAL INTERNET JOURNEY WAVE 1–13 PASS**。

## Boundary

This evidence closes the current develop product journey only. It does not promote `develop` to `main`, does not create a Tag/Release, does not change core-updates, and does not write Owner Production. Production remains V2.36.5 until a separately authorized release cycle occurs.
'''
write(EVIDENCE, evidence)

# README current block.
sub_once(
    "README.md",
    r"## Current Truth\n\n## Current Truth · V2\.36\.5 Production \+ L2 Wave 1–10.*?(?=## Current Authority)",
    f'''## Current Truth\n\n## Current Truth · V2.36.5 Production + L2 Wave 1–13\n\n```text\nOwner Production: V2.36.5\nOwner Schema: {SCHEMA}\nPublished Latest: V2.36.5\nProduction main: {PROD_MAIN}\nV2.36.5 Formal Source: ef86eba16aec71c1d0dabc16ad23089a78ee5057\nV2.36.5 Runtime Tree: a7f472ec1f449ada1152d271f2723c52e7b58144\nCurrent develop before docs checkpoint: {DEVELOP}\nDevelop state: L2 Product Optimization Wave 1–13 / PERSONAL INTERNET JOURNEY PASS / UNRELEASED / DEVELOP ONLY\nBrowser Helper: 1.6.5 on develop\nDevelop VERSION / src/VERSION.txt: 2.36.4 (historical working-branch value; NOT Production Authority)\nPersonal Internet Journey Closure R3: 33565412715 / PASS\nFormal release candidate after Wave 13: NONE\nAssistant direct Production write: NO\n```\n\nV2.36.5 已完成 Owner Production Closure。Production 必须读取 main / Owner Production Authority，不得用 develop 的历史 VERSION 文件反推。Wave 1–13 仍仅在 develop，未进入 main / Tag / Release / core-updates / Owner Production。\n\n当前 L2 证据：[`{EVIDENCE}`]({EVIDENCE})。\n\n''',
    re.S,
)
text = read("README.md")
text = text.replace("— Wave 1–10 L2 checkpoint；", "— Wave 1–13 L2 checkpoint；", 1)
text = text.replace(
    "[`docs/evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md`](docs/evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md) — exact Wave evidence；",
    f"[`{EVIDENCE}`]({EVIDENCE}) — Wave 1–13 + Journey Closure evidence；",
    1,
)
write("README.md", text)

# docs/README is a compact pointer page; replacements are deliberately scoped to its current section.
text = read("docs/README.md")
replacements = [
    ("Current develop：`923368dc7152b6063c0e4d1aeec3afc849bfff18`（Wave 1–10，UNRELEASED / DEVELOP ONLY）", f"Current develop：`{DEVELOP}`（Wave 1–13 / Journey PASS，UNRELEASED / DEVELOP ONLY）"),
    ("— Wave 1–10 产品优化 checkpoint；", "— Wave 1–13 产品优化 checkpoint；"),
    ("[`evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md`](evidence/P01_L2_PRODUCT_OPT_WAVE_1_10_CHECKPOINT_20260902.md) — Exact PR / Gate / merge 证据；", "[`evidence/P01_L2_PERSONAL_INTERNET_JOURNEY_WAVE_1_13_20260902.md`](evidence/P01_L2_PERSONAL_INTERNET_JOURNEY_WAVE_1_13_20260902.md) — Wave 1–13 + Journey Closure 证据；"),
    ("Exact source before docs checkpoint：`923368dc7152b6063c0e4d1aeec3afc849bfff18`。", f"Exact source before docs checkpoint：`{DEVELOP}`。"),
    ("L2 Product Optimization Wave 1–10 已全部合并 develop。", "L2 Product Optimization Wave 1–13 已全部合并 develop，Personal Internet Journey R3 `33565412715` PASS。"),
    ("Wave 1–10：**UNRELEASED / DEVELOP ONLY**。", "Wave 1–13：**UNRELEASED / DEVELOP ONLY**。"),
]
for old, new in replacements:
    if old not in text:
        raise SystemExit(f"docs/README anchor missing: {old}")
    text = text.replace(old, new, 1)
write("docs/README.md", text)

# CHANGELOG current Unreleased section only.
changelog_rows = "\n".join(
    f"- Wave {wave} / PR #{pr} / Gate `{gate}` PASS：{outcome}。"
    for wave, pr, gate, outcome, _ in waves
)
changelog = f'''## Unreleased · L2 Product Optimization Wave 1–13 · Personal Internet Journey PASS · 2026-09-02

- Production baseline remains **V2.36.5**; these changes are **UNRELEASED / DEVELOP ONLY**.
- Develop exact source before this docs checkpoint: `{DEVELOP}`.
- Browser Helper component on develop: `1.6.5`.
- No Schema / Migration / main / Tag / Release / core-updates / Owner Production write in these waves.
{changelog_rows}
- Journey Closure R1 `33564418437` FAIL：HARNESS ONLY，错误假设导入 API 名称必须位于 `transfer.php`；Product 未变。
- Journey Closure R2 `33565270107` FAIL：HARNESS ONLY，错误假设 Search→Save 使用不存在的 data attribute；Product 未变。
- Journey Closure R3 `33565412715` PASS：首次导入 → 搜索 → 快速收藏 → 待整理/分类 → 健康/备份 → 最近使用/安全删除整条主链闭环。

'''
sub_once("CHANGELOG.md", r"## Unreleased · L2 Product Optimization Wave 1–10 · 2026-09-02.*?(?=## V2\.36\.4)", changelog, re.S)

# Final local semantic assertions.
assert json.loads((root / "VF_PROJECT.json").read_text(encoding="utf-8"))["production_version"] == "2.36.5"
assert (root / "VERSION").read_text(encoding="utf-8").strip() == "2.36.4"
assert (root / "src/VERSION.txt").read_text(encoding="utf-8").strip() == "2.36.4"
print("P01 Wave 1-13 authority patch prepared")
