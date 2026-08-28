from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'gov')

OVERLAY = '''# skill-book V5.3 Candidate Overlay

Status: `CANDIDATE / NOT CURRENT`

Source Current remains: `skill-book V3.5`.
Previous Published Candidate: `skill-book V5.2`.
Installed Runtime Observation remains: `skill-book V4.7 CANDIDATE`.

## Purpose

V5.3 is a Bug Closure release opened by the Fresh V5.2 A1 standalone result. That run materially improved READ and TRAIN but still compressed professional DO depth, and its external-opaque holdout dependency prevented a legal FIRST_FREEZE in an ordinary standalone window.

V5.3 closes three defects without weakening evidence truth:

1. `Book-Promise Responsibility Depth` infers non-compressible responsibilities from the declared reader transformation / book promise before Draft and requires real three-layer coverage: Reading Core + Operator Reference + executable Template/Worksheet. A fluent reading path cannot silently delete delivery, identity/routing, discoverability, acquisition/activation, observability/decision or rollback/recovery responsibilities when the promise requires them.
2. FIRST_FREEZE now freezes reader-facing bytes before the standalone frozen holdout. The deterministic local holdout runs against frozen bytes; any content repair mutates the tree, invalidates Freeze Integrity and requires a new freeze/holdout cycle.
3. A local frozen holdout is explicitly evidence class `LOCAL_FROZEN_NON_OPAQUE`. It can close the standalone machine gate but never masquerades as an external opaque evaluator. External opaque evidence remains stronger and independently reportable.

Runtime Contract ID: `SB53-RUNTIME-CONTRACT-A73E19C4`.

## Validation

- Local full regression: `86/86 PASS`
- Remote reconstructed-source regression: `86/86 PASS`
- Exact remote staging regression: `86/86 PASS`
- Release exact-source regression: `86/86 PASS`
- Python syntax: `35/35 PASS`
- Fresh V5.2 A1 defect replay under V5.3: correctly `BLOCK` at PRE_DRAFT because six promise responsibilities lacked independent three-layer depth; this is defect-detection evidence, not a V5.3 book superiority claim.
- Frozen local holdout ordering / mutation tests: `PASS`
- Deterministic Candidate ZIP reproduction: `PASS / exact local-remote identity MATCH`
- Remote release download readback: `PASS`
- Fresh V5.3 standalone book benchmark: `NOT_RUN`
- External opaque holdout for a V5.3 book: `NOT_RUN`
- Backend-installed V5.3 Runtime: `NOT_RUN`
- Real Reader READ / LEARN / TRAIN evidence for a V5.3 book: `NOT_RUN`
- Current Promotion: `NOT_AUTHORIZED`

## Published Distribution Authority

- Exact Source Commit: `c7c32f9294ebf8fe4aade9b0668103407e8a520f`
- Tag: `skill-book-v5.3-candidate-20260828`
- Release ID: `378678631`
- ZIP Asset ID: `534177144`
- SHA Asset ID: `534177145`
- Bytes: `346582`
- SHA-256: `fefb93eaab47255b33e1c4cd21800daab3bcfb4d70b9b92043b1a0a1c11767d8`
- Public Runner Source Validation Run / Job: `33198063963 / 98940207768`
- Public Runner Release Run / Job: `33198298125 / 98941018383`
- Remote Download Readback: `PASS`
- Distribution Status: `PUBLISHED_REMOTE_VERIFIED`

## Authority Boundary

This publication makes V5.3 the latest published Candidate only. It does not change Source Current, does not claim Backend-installed V5.3 Runtime evidence, and does not turn machine holdout evidence into Real Reader READ / LEARN / TRAIN evidence or a replacement-superiority claim.
'''

README = '''# skill-book V5.3 Candidate · Source Distribution

> 状态：`CANDIDATE / NOT CURRENT`  
> Distribution：`PUBLISHED_REMOTE_VERIFIED`  
> Source Authority：`skills/skill-book/V5.3/`  
> Candidate Mother Overlay：`mother-specs/skill-book/V5.3/SKILL_BOOK_V5.3_CANDIDATE_OVERLAY.md`  
> Source Current保持：`skill-book V3.5`

## Candidate Purpose

V5.3 来自 Fresh V5.2 A1 的真实回归：V5.2 已明显改善 READ / TRAIN，但独立生成时仍会把“上线/运营”类 DO 深度压薄，同时 ordinary standalone 环境因缺少 external opaque evaluator 而无法形成合法 FIRST_FREEZE。

V5.3 新增 Book-Promise Responsibility Depth，要求书的承诺在 PRE_DRAFT 就映射为不可静默压缩的三层 Value Bundle；并将 standalone holdout 调整到 FIRST_FREEZE 之后，只允许对 frozen bytes 做 deterministic holdout。该证据明确标记为 `LOCAL_FROZEN_NON_OPAQUE`，不会伪装成 external opaque evidence。

## Published Candidate Authority

- Exact Source Commit：`c7c32f9294ebf8fe4aade9b0668103407e8a520f`
- Tag：`skill-book-v5.3-candidate-20260828`
- Release ID：`378678631`
- File：`skill-book_V5.3_CANDIDATE_20260828.zip`
- Bytes：`346582`
- SHA-256：`fefb93eaab47255b33e1c4cd21800daab3bcfb4d70b9b92043b1a0a1c11767d8`
- Remote Asset ID：`534177144`
- SHA Asset ID：`534177145`
- Source Validation Run / Job：`33198063963 / 98940207768`
- Release Runner Run / Job：`33198298125 / 98941018383`
- Unit Tests：`86/86 PASS reconstructed + 86/86 PASS exact remote staging + 86/86 PASS release exact source`
- Python Syntax：`35/35 PASS`
- V5.2 Fresh A1 Defect Replay：`PRE_DRAFT BLOCK AS EXPECTED`
- Frozen Local Holdout Evidence Class：`LOCAL_FROZEN_NON_OPAQUE`
- ZIP Container：`ZIP_STORED + fixed timestamp / permissions / path ordering`
- Local / Remote ZIP Identity：`MATCH`
- Remote Download Readback：`PASS`
- ZIP CRC：`PASS`
- Unsafe Path / Duplicate Path / pycache：`0`

直接下载：`https://github.com/llhzx2018/gov-doc/releases/download/skill-book-v5.3-candidate-20260828/skill-book_V5.3_CANDIDATE_20260828.zip`

SHA 文件：`https://github.com/llhzx2018/gov-doc/releases/download/skill-book-v5.3-candidate-20260828/skill-book_V5.3_CANDIDATE_20260828.zip.sha256`

## Authority Boundary

- Latest Candidate：`V5.3`
- Source Current：`skill-book V3.5`
- Installed Runtime Observation：`skill-book V4.7 CANDIDATE`
- Fresh V5.3 standalone book benchmark：`NOT_RUN`
- Backend-installed V5.3 Runtime：`NOT_RUN`
- External Opaque Holdout：`NOT_RUN`
- Real Reader Evidence：`NOT_RUN`
- Current Promotion：`NOT_AUTHORIZED`

本次 Publication 只完成 V5.3 Candidate 发行闭环；下一阶段仍需要安装 V5.3 后做全新窗口真实写书测试，再与历史 Canonical 做 POST-FREEZE 对比。
'''

MIRROR = '''# Runtime ZIP Mirror Status · skill-book V5.3

状态：`PUBLISHED_REMOTE_VERIFIED`

V5.3 Candidate 已完成 Public Runner reconstructed Source、exact remote staging、release exact Source 三轮 86/86 tests，35/35 Python syntax、portable deterministic build、prerelease upload、remote download readback 与 local/remote identity verification。

Temporary Public Runner PR #376：`PENDING_FINAL_CLOSE / MUST NOT MERGE`。

## Published Distribution Authority

- Release：`skill-book V5.3 Candidate`（prerelease）
- Tag：`skill-book-v5.3-candidate-20260828`
- Release ID：`378678631`
- File：`skill-book_V5.3_CANDIDATE_20260828.zip`
- Remote Asset ID：`534177144`
- SHA Asset ID：`534177145`
- Bytes：`346582`
- SHA-256：`fefb93eaab47255b33e1c4cd21800daab3bcfb4d70b9b92043b1a0a1c11767d8`
- Exact Source Commit：`c7c32f9294ebf8fe4aade9b0668103407e8a520f`
- Source Validation Run / Job：`33198063963 / 98940207768`
- Release Run / Job：`33198298125 / 98941018383`
- Unit Tests：`86/86 PASS reconstructed + 86/86 PASS exact remote staging + 86/86 PASS release exact source`
- Python Syntax：`35/35 PASS`
- V5.2 Fresh A1 Defect Replay：`PRE_DRAFT BLOCK AS EXPECTED`
- Frozen Local Holdout Evidence Class：`LOCAL_FROZEN_NON_OPAQUE`
- Fresh V5.3 standalone book benchmark：`NOT_RUN`
- External Opaque Holdout：`NOT_RUN`
- Backend-installed V5.3 Runtime：`NOT_RUN`
- Real Reader Evidence：`NOT_RUN`
- Local / Remote Identity：`MATCH`
- Remote Download Readback：`PASS`
- ZIP CRC：`PASS`
- Unsafe Path / Duplicate Path / pycache：`0`
- Current Promotion：`NOT_AUTHORIZED`
- Software Production Write：`0`

下载地址：`https://github.com/llhzx2018/gov-doc/releases/download/skill-book-v5.3-candidate-20260828/skill-book_V5.3_CANDIDATE_20260828.zip`

SHA 文件：`https://github.com/llhzx2018/gov-doc/releases/download/skill-book-v5.3-candidate-20260828/skill-book_V5.3_CANDIDATE_20260828.zip.sha256`

## Authority Boundary

- Source：`skills/skill-book/V5.3/`
- Mother Overlay：`mother-specs/skill-book/V5.3/SKILL_BOOK_V5.3_CANDIDATE_OVERLAY.md`
- Latest Candidate：`V5.3`
- Source Current：`V3.5`
- Installed Runtime Observation：`V4.7 CANDIDATE`
- Current Promotion：`NOT_AUTHORIZED`
'''

CANDIDATE_INDEX = '''## Candidate（不改变 Current）

`skill-book V5.3` 是最新 `CANDIDATE / NOT CURRENT`；Source Current仍为V3.5，V5.3不包含在Current总包中。Installed Runtime Observation仍为V4.7 Candidate。

- [直接下载 skill-book V5.3 Candidate ZIP](https://github.com/llhzx2018/gov-doc/releases/download/skill-book-v5.3-candidate-20260828/skill-book_V5.3_CANDIDATE_20260828.zip)
- [下载 SHA-256 文件](https://github.com/llhzx2018/gov-doc/releases/download/skill-book-v5.3-candidate-20260828/skill-book_V5.3_CANDIDATE_20260828.zip.sha256)
- [查看 V5.3 Candidate Release](https://github.com/llhzx2018/gov-doc/releases/tag/skill-book-v5.3-candidate-20260828)
- [查看 V5.3 Candidate Source](https://github.com/llhzx2018/gov-doc/tree/main/skills/skill-book/V5.3)
- [查看 V5.3 Candidate Mother Overlay](https://github.com/llhzx2018/gov-doc/blob/main/mother-specs/skill-book/V5.3/SKILL_BOOK_V5.3_CANDIDATE_OVERLAY.md)
- [查看 V5.3 Candidate 分发说明](https://github.com/llhzx2018/gov-doc/blob/main/distribution/skills/candidates/skill-book/V5.3/README.md)

Published Distribution Identity：

- Bytes：`346582`
- SHA-256：`fefb93eaab47255b33e1c4cd21800daab3bcfb4d70b9b92043b1a0a1c11767d8`
- Release ID：`378678631`
- Remote Asset ID：`534177144`
- SHA Asset ID：`534177145`
- Exact Source Commit：`c7c32f9294ebf8fe4aade9b0668103407e8a520f`
- Source Validation Run / Job：`33198063963 / 98940207768`
- Release Run / Job：`33198298125 / 98941018383`
- Unit Tests：`86/86 PASS (remote reconstructed source) + 86/86 PASS (exact remote staging) + 86/86 PASS (release exact source)`
- Python Syntax：`35/35 PASS`
- Local / Remote ZIP Identity：`MATCH`
- Remote Download Readback：`PASS`
- ZIP CRC / Unsafe Path / Duplicate Path / pycache：`PASS`
- V5.2 Fresh A1 Defect Replay：`PRE_DRAFT BLOCK AS EXPECTED`
- Frozen Local Holdout Evidence Class：`LOCAL_FROZEN_NON_OPAQUE`
- Fresh V5.3 standalone book benchmark：`NOT_RUN`
- External Opaque Holdout：`NOT_RUN`
- Backend-installed V5.3 Runtime：`NOT_RUN`
- Real Reader Evidence：`NOT_RUN`
- Current Promotion：`NOT_AUTHORIZED`
- Status：`PUBLISHED_REMOTE_VERIFIED`

V5.3 Candidate Publication仅完成分发闭环，不将Source Current从V3.5晋升；Local Frozen Holdout不冒充External Opaque或真人Reader Outcome。

历史 Candidate：

- [skill-book V5.2](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V5.2)
- [skill-book V5.1](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V5.1)
- [skill-book V5.0](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V5.0)
- [skill-book V4.9](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.9)
- [skill-book V4.8](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.8)
- [skill-book V4.7](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.7)
- [skill-book V4.6](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.6)
- [skill-book V4.5](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.5)
- [skill-book V4.4](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.4)
- [skill-book V4.3](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.3)
- [skill-book V4.2](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.2)
- [skill-book V4.1](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.1)
- [skill-book V4.0](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.0)
'''

for rel, content in [
    ('mother-specs/skill-book/V5.3/SKILL_BOOK_V5.3_CANDIDATE_OVERLAY.md', OVERLAY),
    ('distribution/skills/candidates/skill-book/V5.3/README.md', README),
    ('distribution/skills/candidates/skill-book/V5.3/RUNTIME_ZIP_MIRROR_STATUS.md', MIRROR),
]:
    p = root / rel
    if p.exists():
        raise SystemExit(f'refuse existing governance path: {rel}')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)

current = root / 'CURRENT.md'
s = current.read_text()
old = '`skill-book V4.0/V4.1/V4.2/V4.3/V4.4/V4.5/V4.6/V4.7/V4.8/V4.9/V5.0/V5.1` 为保留的历史 Candidate，`V5.2` 为最新 Candidate；十三个 Candidate 版本均未晋升 Source Current。V5.2 已进入 Candidate Distribution，但未进入 Current Distribution。'
new = '`skill-book V4.0/V4.1/V4.2/V4.3/V4.4/V4.5/V4.6/V4.7/V4.8/V4.9/V5.0/V5.1/V5.2` 为保留的历史 Candidate，`V5.3` 为最新 Candidate；十四个 Candidate 版本均未晋升 Source Current。V5.3 已进入 Candidate Distribution，但未进入 Current Distribution。'
if s.count(old) != 1:
    raise SystemExit(f'CURRENT pointer count={s.count(old)}')
s = s.replace(old, new)
if '| skill-book | V3.5 | V4.7 CANDIDATE（非 Current） |' not in s:
    raise SystemExit('Source Current / installed observation drift')
current.write_text(s)

index = root / 'distribution/skills/CURRENT_SKILL_DOWNLOAD_INDEX.md'
s = index.read_text()
marker = '## Candidate（不改变 Current）\n'
if s.count(marker) != 1:
    raise SystemExit(f'candidate marker count={s.count(marker)}')
prefix = s.split(marker, 1)[0]
if '| skill-book | V3.5 | `skill-book_V3.5_INSTALL_20260825.zip`' not in prefix:
    raise SystemExit('Current 10 Skills skill-book row drift')
index.write_text(prefix + CANDIDATE_INDEX)

print('V53_RECONCILIATION_SCRIPT=PASS')
