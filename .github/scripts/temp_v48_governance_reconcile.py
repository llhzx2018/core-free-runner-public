from pathlib import Path

SOURCE_COMMIT = 'd5d809172f23b31212cf6b66551f775b2e07e35f'
TAG = 'skill-book-v4.8-candidate-20260827'
RELEASE_ID = '378052388'
ASSET_NAME = 'skill-book_V4.8_CANDIDATE_20260827.zip'
ASSET_ID = '532735275'
SHA_ASSET_ID = '532735276'
ASSET_BYTES = '156008'
ASSET_SHA256 = 'df933b799e7e56a662f055abfe9825d15a4470c86cf9b41a34e30cbb98bf4c4b'
RUNNER_RUN = '33105833415'
RUNNER_JOB = '98635300217'
BASE_URL = f'https://github.com/llhzx2018/gov-doc/releases/download/{TAG}'

root = Path('.')

readme = root / 'distribution/skills/candidates/skill-book/V4.8/README.md'
readme.write_text(f'''# skill-book V4.8 Candidate · Source Distribution

> 状态：`CANDIDATE / NOT CURRENT`  
> Distribution：`PUBLISHED_REMOTE_VERIFIED`  
> Source Authority：`skills/skill-book/V4.8/`  
> Candidate Mother Overlay：`mother-specs/skill-book/V4.8/SKILL_BOOK_V4.8_CANDIDATE_OVERLAY.md`  
> Source Current保持：`skill-book V3.5`

## Candidate Purpose

V4.8基于真实V4.7 Backend SEALED A1 failure修复Runtime Truth Enforcement：加入Runtime Entry Receipt、Skill-internal canary、Declarative Evidence First、External Verifier Authority、Manifest key normalization、Runtime path discovery、SEALED baseline truth与false-green final decision detection。

这些改动服务于READ / LEARN / TRAIN / DO的真实Reader Outcome；机器Gate用于防止假绿，不能替代真人Reader Evidence。

## Published Candidate Authority

- Exact Source Commit：`{SOURCE_COMMIT}`
- Tag：`{TAG}`
- Release ID：`{RELEASE_ID}`
- File：`{ASSET_NAME}`
- Bytes：`{ASSET_BYTES}`
- SHA-256：`{ASSET_SHA256}`
- Remote Asset ID：`{ASSET_ID}`
- SHA Asset ID：`{SHA_ASSET_ID}`
- Runner Run：`{RUNNER_RUN}`
- Runner Job：`{RUNNER_JOB}`
- Unit Tests：`38/38 PASS (modular execution)`
- Python Syntax：`PASS`
- ZIP Container：`ZIP_STORED + fixed timestamp / permissions / path ordering`
- Local / Remote ZIP Identity：`MATCH`
- Remote Download Readback：`PASS`
- ZIP CRC：`PASS`
- Unsafe Path：`0`
- Duplicate Path：`0`
- pycache/pyc：`0`

直接下载：`{BASE_URL}/{ASSET_NAME}`

SHA 文件：`{BASE_URL}/{ASSET_NAME}.sha256`

## Authority Boundary

- Latest Candidate：`V4.8`
- Source Current：`skill-book V3.5`
- Installed Runtime Observation：`skill-book V4.7`
- Backend V4.8 Runtime Test：`NOT_RUN`
- Real Reader Forward Evidence：`NOT_RUN`
- Current Promotion：`NOT_AUTHORIZED`

本次Publication只完成V4.8 Candidate发行闭环，不将V4.8晋升为Source Current，也不声称Reader Outcome真人闭环已完成。
''', encoding='utf-8')

mirror = root / 'distribution/skills/candidates/skill-book/V4.8/RUNTIME_ZIP_MIRROR_STATUS.md'
mirror.write_text(f'''# Runtime ZIP Mirror Status · skill-book V4.8

状态：`PUBLISHED_REMOTE_VERIFIED`

V4.8 Candidate已完成Public Runner exact Source checkout、38/38 modular tests、portable deterministic build、prerelease upload、remote download readback与byte-for-byte identity verification。临时Public Runner PR #366只用于发布验证，必须关闭且不得merge进Runner Current。

## Published Distribution Authority

- Release：`skill-book V4.8 Candidate`（prerelease）
- Tag：`{TAG}`
- Release ID：`{RELEASE_ID}`
- File：`{ASSET_NAME}`
- Remote Asset ID：`{ASSET_ID}`
- SHA Asset ID：`{SHA_ASSET_ID}`
- Bytes：`{ASSET_BYTES}`
- SHA-256：`{ASSET_SHA256}`
- Exact Source Commit：`{SOURCE_COMMIT}`
- Runner Run：`{RUNNER_RUN}`
- Runner Job：`{RUNNER_JOB}`
- Unit Tests：`38/38 PASS (modular execution)`
- Python Syntax：`PASS`
- Local / Remote Identity：`MATCH`
- Remote Download Readback：`PASS`
- ZIP CRC：`PASS`
- Unsafe Path：`0`
- Duplicate Path：`0`
- pycache/pyc：`0`
- Software Production Write：`0`

下载地址：`{BASE_URL}/{ASSET_NAME}`

SHA 文件：`{BASE_URL}/{ASSET_NAME}.sha256`

## Authority Boundary

- Source：`skills/skill-book/V4.8/`
- Mother Overlay：`mother-specs/skill-book/V4.8/SKILL_BOOK_V4.8_CANDIDATE_OVERLAY.md`
- Latest Candidate：`V4.8`
- Source Current：`V3.5`
- Installed Runtime Observation：`V4.7`
- Backend V4.8 Runtime Test：`NOT_RUN`
- Real Reader Evidence：`NOT_RUN`
- Current Promotion：`NOT_AUTHORIZED`
- Temporary Public Runner PR：`#366 CLOSED / NOT MERGED`（最终关闭后成立；本文件由关闭前reconciliation生成，最终状态由远端PR回读确认）
''', encoding='utf-8')

current = root / 'CURRENT.md'
t = current.read_text(encoding='utf-8')
old_row = '| skill-book | V3.5 | V4.6 CANDIDATE（非 Current） |'
new_row = '| skill-book | V3.5 | V4.7 CANDIDATE（非 Current） |'
if old_row in t:
    t = t.replace(old_row, new_row, 1)
elif new_row not in t:
    raise SystemExit('CURRENT_SKILL_BOOK_RUNTIME_ROW_UNEXPECTED')
old_sentence = '`skill-book V4.0/V4.1/V4.2/V4.3/V4.4/V4.5/V4.6` 为保留的历史 Candidate，`V4.7` 为最新 Candidate；八者均未晋升 Source Current。V4.7 已进入 Candidate Distribution，但未进入 Current Distribution。'
new_sentence = '`skill-book V4.0/V4.1/V4.2/V4.3/V4.4/V4.5/V4.6/V4.7` 为保留的历史 Candidate，`V4.8` 为最新 Candidate；九者均未晋升 Source Current。V4.8 已进入 Candidate Distribution，但未进入 Current Distribution。'
if old_sentence in t:
    t = t.replace(old_sentence, new_sentence, 1)
elif new_sentence not in t:
    raise SystemExit('CURRENT_SKILL_BOOK_CANDIDATE_SENTENCE_UNEXPECTED')
current.write_text(t, encoding='utf-8')

idx = root / 'distribution/skills/CURRENT_SKILL_DOWNLOAD_INDEX.md'
t = idx.read_text(encoding='utf-8')
marker = '## Candidate（不改变 Current）'
if marker not in t:
    raise SystemExit('CANDIDATE_MARKER_MISSING')
head = t.split(marker, 1)[0]
tail = f'''{marker}

`skill-book V4.8` 是最新 `CANDIDATE / NOT CURRENT`；Source Current仍为V3.5，且V4.8不包含在Current总包中。Installed Runtime Observation为V4.7 Candidate。

- [直接下载 skill-book V4.8 Candidate ZIP]({BASE_URL}/{ASSET_NAME})
- [下载 SHA-256 文件]({BASE_URL}/{ASSET_NAME}.sha256)
- [查看 V4.8 Candidate Release](https://github.com/llhzx2018/gov-doc/releases/tag/{TAG})
- [查看 V4.8 Candidate Source](https://github.com/llhzx2018/gov-doc/tree/main/skills/skill-book/V4.8)
- [查看 V4.8 Candidate Mother Overlay](https://github.com/llhzx2018/gov-doc/blob/main/mother-specs/skill-book/V4.8/SKILL_BOOK_V4.8_CANDIDATE_OVERLAY.md)
- [查看 V4.8 Candidate 分发说明](https://github.com/llhzx2018/gov-doc/blob/main/distribution/skills/candidates/skill-book/V4.8/README.md)

Published Distribution Identity：

- Bytes：`{ASSET_BYTES}`
- SHA-256：`{ASSET_SHA256}`
- Release ID：`{RELEASE_ID}`
- Remote Asset ID：`{ASSET_ID}`
- SHA Asset ID：`{SHA_ASSET_ID}`
- Exact Source Commit：`{SOURCE_COMMIT}`
- Runner Run：`{RUNNER_RUN}`
- Runner Job：`{RUNNER_JOB}`
- Unit Tests：`38/38 PASS (modular execution)`
- Python Syntax：`PASS`
- Local / Remote ZIP Identity：`MATCH`
- Remote Download Readback：`PASS`
- ZIP CRC：`PASS`
- Unsafe Path：`0`
- Duplicate Path：`0`
- pycache/pyc：`0`
- Status：`PUBLISHED_REMOTE_VERIFIED`
- Current Promotion：`NOT_AUTHORIZED`

历史 Candidate：

- [skill-book V4.7](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.7)
- [skill-book V4.6](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.6)
- [skill-book V4.5](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.5)
- [skill-book V4.4](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.4)
- [skill-book V4.3](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.3)
- [skill-book V4.2](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.2)
- [skill-book V4.1](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.1)
- [skill-book V4.0](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.0)
'''
idx.write_text(head + tail, encoding='utf-8')

print('V48_GOVERNANCE_RECONCILE_FILES_PREPARED=PASS')
