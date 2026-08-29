from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()
current=root/'CURRENT.md'
text=current.read_text(encoding='utf-8')
old='`skill-book V4.0/V4.1/V4.2/V4.3/V4.4/V4.5/V4.6/V4.7/V4.8/V4.9/V5.0/V5.1/V5.2/V5.3/V5.4` 为保留的历史 Candidate，`V5.5` 为最新 Candidate；十六个 Candidate 版本均未晋升 Source Current。V5.5 已进入 Candidate Distribution，但未进入 Current Distribution。'
new='`skill-book V4.0/V4.1/V4.2/V4.3/V4.4/V4.5/V4.6/V4.7/V4.8/V4.9/V5.0/V5.1/V5.2/V5.3/V5.4/V5.5` 为保留的历史 Candidate，`V5.6` 为最新 Candidate；十七个 Candidate 版本均未晋升 Source Current。V5.6 已进入 Candidate Distribution，但未进入 Current Distribution。'
assert text.count(old)==1
current.write_text(text.replace(old,new),encoding='utf-8')

overlay=root/'mother-specs/skill-book/V5.6/SKILL_BOOK_V5.6_CANDIDATE_OVERLAY.md'
overlay.parent.mkdir(parents=True,exist_ok=True)
assert not overlay.exists()
overlay.write_text(r'''# skill-book V5.6 Candidate Overlay

Status: `CANDIDATE / NOT CURRENT`

Source Current remains: `skill-book V3.5`.
Previous Published Candidate: `skill-book V5.5`.
Installed Runtime Observation remains: `skill-book V4.7 CANDIDATE`.

## Purpose

V5.6 closes `Practical Asset Depth / Adequacy`. It addresses the false-green class where an operator asset can mention many responsibility dimensions and satisfy shell/structure checks while remaining too shallow to support evidence trace, decision reconstruction, validation, recovery, change control, or next-action handoff.

Runtime Contract ID: `SB56-RUNTIME-CONTRACT-CBE00206`.

The gate remains role-sensitive and domain-generic. Historical Canonical is not restored as a generation template. The mandatory non-A1 domain is a 20-person offline reading club, intentionally avoiding website, SEO, deployment, and software vocabulary.

## Validation

- Non-A1 Practical Asset Depth targeted matrix: `12/12 PASS`
- Inherited Adequacy targeted suite: `6/6 PASS`
- Runtime depth integration gate: `36/36 PASS`
- Final immutable Candidate full regression: `122/122 PASS`
- Python compile on immutable Candidate bytes: `39/39 PASS`
- Fresh non-A1 generation: `9/9 PASS`
- Fresh non-A1 test ID: `V5.6_FRESH_NON_A1_READING_CLUB_20260829`
- Fresh generation Runner: `33258236680 / 99115573137`
- Adversarial proof: `OLD_ADEQUACY_FALSE_GREEN_REPRODUCED -> DEPTH_BLOCK_AS_REQUIRED -> REPAIR_PASS`
- Required Depth blocks reproduced: `PRACTICAL_ASSET_EVIDENCE_LOG_SHALLOW`, `PRACTICAL_ASSET_RECOVERY_LOOP_INCOMPLETE`
- Verifier changed during repair: `false`
- Contract changed during repair: `false`
- Final non-manifest source tree SHA-256: `31a0b22fdb6f7d957f22316c3a20cd1c3688784359ee6a575fae3f089649c123`
- Manifest source inventory: `96 files`
- Candidate ZIP files: `98`
- Internal SHA256SUMS: `97/97 PASS`
- Deterministic Candidate A/B identity: `PASS`
- ZIP CRC / path safety / duplicate-path / pycache checks: `PASS / 0 defects`
- Candidate staging run / job: `33258680813 / 99116743325`
- Final local byte-seal run / job: `33258765687 / 99116962027`
- Remote exact-source / release run / job: `33258854513 / 99117205434`
- Historical Canonical boundary: `FIRST_FREEZE+ evaluator-only; never generation template`
- Real Reader Evidence: `NOT_RUN`
- Current Promotion: `NOT_AUTHORIZED`

## Published Distribution Authority

- Exact Source Commit: `b32fda1c75fdbc4d2e40aaaa444ba7b31e06bd28`
- Tag: `skill-book-v5.6-candidate-20260829`
- Release ID: `379016022`
- ZIP Asset ID: `535344499`
- SHA Asset ID: `535344498`
- File: `skill-book_V5.6_CANDIDATE_20260829.zip`
- Bytes: `197611`
- SHA-256: `57ba8943013946d22ec1555619ea07797f93a89ae1966c38f341e7e3c372f48a`
- Tag target exact source: `PASS`
- Remote exact-source deterministic rebuild: `PASS`
- Remote release metadata readback: `PASS`
- Remote asset download readback: `PASS`
- ZIP CRC / internal SHA readback: `PASS`
- Distribution Status: `PUBLISHED_REMOTE_VERIFIED`

## Reader Outcome / Authority Boundary

Machine evidence proves enforcement and generation/verification behavior, not Real Reader Outcome. V5.6 has no new Real Reader READ / LEARN / TRAIN evidence and records that fact as `NOT_RUN`.

This publication makes V5.6 the latest published Candidate only. It does not change Source Current (`V3.5`), Current Distribution, Installed Runtime Observation (`V4.7 CANDIDATE`), or authorize Current promotion.
''',encoding='utf-8')

readme=root/'distribution/skills/candidates/skill-book/V5.6/README.md'
readme.parent.mkdir(parents=True,exist_ok=True)
assert not readme.exists()
readme.write_text(r'''# skill-book V5.6 Candidate · Source Distribution

> 状态：`CANDIDATE / NOT CURRENT`  
> Distribution：`PUBLISHED_REMOTE_VERIFIED`  
> Source Authority：`skills/skill-book/V5.6/`  
> Candidate Mother Overlay：`mother-specs/skill-book/V5.6/SKILL_BOOK_V5.6_CANDIDATE_OVERLAY.md`  
> Source Current保持：`skill-book V3.5`

## Candidate Purpose

V5.6 是 `Practical Asset Depth / Adequacy` closure。它解决的是“责任维度看起来齐全，但资产仍无法让 operator 重建证据、判断、验证、恢复、变更与下一动作”的 false-green，而不是靠加字数、加表格或恢复 Historical Canonical 模板来获得机器 PASS。

强制非 A1 域采用 20 人线下读书会。旧 Adequacy 对一个长且结构完整但 trace/recovery 浅的 iteration log 仍可 false-green；V5.6 Depth 正确 BLOCK，恢复真实深度资产后 PASS，期间 verifier 与 contract 均未修改。

## Published Candidate Authority

- Exact Source Commit：`b32fda1c75fdbc4d2e40aaaa444ba7b31e06bd28`
- Non-manifest Source Tree SHA：`31a0b22fdb6f7d957f22316c3a20cd1c3688784359ee6a575fae3f089649c123`
- Runtime Contract ID：`SB56-RUNTIME-CONTRACT-CBE00206`
- Tag：`skill-book-v5.6-candidate-20260829`
- Release ID：`379016022`
- File：`skill-book_V5.6_CANDIDATE_20260829.zip`
- Bytes：`197611`
- SHA-256：`57ba8943013946d22ec1555619ea07797f93a89ae1966c38f341e7e3c372f48a`
- Remote ZIP Asset ID：`535344499`
- SHA Asset ID：`535344498`
- Final Local Seal Run / Job：`33258765687 / 99116962027`
- Remote Exact-source / Release Run / Job：`33258854513 / 99117205434`
- Practical Asset Depth targeted：`12/12 PASS`
- Inherited Adequacy：`6/6 PASS`
- Runtime Depth Integration：`36/36 PASS`
- Full Regression：`122/122 PASS`
- Python Compile：`39/39 PASS`
- Fresh Non-A1 Generation：`9/9 PASS`
- Internal SHA256SUMS：`97/97 PASS`
- ZIP Files：`98`
- ZIP Container：`ZIP_DEFLATED level 9 + fixed timestamp / permissions / path ordering`
- Deterministic Local / Remote ZIP Identity：`MATCH`
- Tag Target Exact Source：`PASS`
- Remote Download Readback：`PASS`
- ZIP CRC / path safety / duplicate path / pycache：`PASS / 0 defects`

直接下载：`https://github.com/llhzx2018/gov-doc/releases/download/skill-book-v5.6-candidate-20260829/skill-book_V5.6_CANDIDATE_20260829.zip`

SHA 文件：`https://github.com/llhzx2018/gov-doc/releases/download/skill-book-v5.6-candidate-20260829/skill-book_V5.6_CANDIDATE_20260829.zip.sha256`

## Authority Boundary

- Latest Published Candidate（治理对账完成后）：`V5.6`
- Previous Published Candidate：`V5.5`
- Source Current：`skill-book V3.5`
- Installed Runtime Observation：`skill-book V4.7 CANDIDATE`
- Current Promotion：`NOT_AUTHORIZED`
- Current Distribution：`UNCHANGED`
- Historical Canonical：`FIRST_FREEZE+ evaluator-only; never generation template`
- Backend-installed V5.6 Runtime：`NOT_RUN`
- Real Reader Evidence：`NOT_RUN`

Machine PASS 只证明 machine contract、生成与验证闭环；不替代 READ / LEARN / TRAIN / DO 的 Real Reader Outcome。V5.6 Publication 只完成 Candidate 发行，不晋升 Source Current，也不写 Current Distribution。
''',encoding='utf-8')

mirror=root/'distribution/skills/candidates/skill-book/V5.6/RUNTIME_ZIP_MIRROR_STATUS.md'
assert not mirror.exists()
mirror.write_text(r'''# Runtime ZIP Mirror Status · skill-book V5.6

状态：`PUBLISHED_REMOTE_VERIFIED / GOVERNANCE_RECONCILED_PENDING_RUNNER_CLOSE`

V5.6 Candidate 已完成 Practical Asset Depth design gate、fresh non-A1 generation、final-byte regression、deterministic Candidate build、remote exact-source rebuild、main exact-source fast-forward、prerelease upload、tag target verification、release metadata readback与 remote asset download readback。

Temporary Public Runner PR #397：`OPEN / DO NOT MERGE / CLOSE PENDING`。

## Published Distribution Authority

- Release：`skill-book V5.6 Candidate · 2026-08-29`（prerelease）
- Tag：`skill-book-v5.6-candidate-20260829`
- Release ID：`379016022`
- File：`skill-book_V5.6_CANDIDATE_20260829.zip`
- Remote ZIP Asset ID：`535344499`
- SHA Asset ID：`535344498`
- Bytes：`197611`
- SHA-256：`57ba8943013946d22ec1555619ea07797f93a89ae1966c38f341e7e3c372f48a`
- Final Source Commit：`b32fda1c75fdbc4d2e40aaaa444ba7b31e06bd28`
- Non-manifest Source Tree SHA：`31a0b22fdb6f7d957f22316c3a20cd1c3688784359ee6a575fae3f089649c123`
- Runtime Contract ID：`SB56-RUNTIME-CONTRACT-CBE00206`
- Python Compile：`39/39 PASS`
- Full Regression：`122/122 PASS`
- Practical Asset Depth targeted：`12/12 PASS`
- Inherited Adequacy：`6/6 PASS`
- Runtime Depth Integration：`36/36 PASS`
- Fresh non-A1 generation：`9/9 PASS`
- Internal SHA256SUMS：`97/97 PASS`
- ZIP Files：`98`
- Deterministic Candidate ZIP：`PASS / local-remote exact identity`
- Remote Download Readback：`PASS`
- ZIP CRC / unsafe path / duplicate path / pycache：`PASS / 0 defects`
- Real Reader Evidence：`NOT_RUN`
- Historical Canonical：`FIRST_FREEZE+ evaluator-only; never generation template`

## Runner / Governance Evidence

- Design Gate Closure Run / Job：`33258515860 / 99116309698`
- Candidate Stage Run / Job：`33258680813 / 99116743325`
- Final Local Seal Run / Job：`33258765687 / 99116962027`
- Remote Exact-source / Release Run / Job：`33258854513 / 99117205434`
- Temporary Runner PR：`#397 OPEN / DO NOT MERGE`

## Authority Boundary

- Source：`skills/skill-book/V5.6/`
- Mother Overlay：`mother-specs/skill-book/V5.6/SKILL_BOOK_V5.6_CANDIDATE_OVERLAY.md`
- Candidate Distribution：`distribution/skills/candidates/skill-book/V5.6/`
- Latest Published Candidate：`V5.6`
- Source Current：`V3.5`
- Installed Runtime Observation：`V4.7 CANDIDATE`
- Current Promotion：`NOT_AUTHORIZED`
- Current Distribution Write：`0`
- Software Production Write：`0`

Current Distribution remains untouched. Final governance closure requires only closing temporary Public Runner PR #397 without merge and recording that closure here.
''',encoding='utf-8')

print('V56_GOVERNANCE_RECONCILIATION_PREPARED')
