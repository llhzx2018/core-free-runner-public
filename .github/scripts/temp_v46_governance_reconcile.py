from pathlib import Path
import json, os, subprocess, shutil

REPO='llhzx2018/gov-doc'
TAG='skill-book-v4.6-candidate-20260827'
SOURCE='27ca368b9f7bc8d6160ff5049562c74cb440144b'
ASSET='skill-book_V4.6_CANDIDATE_20260827.zip'
SHA_ASSET=ASSET+'.sha256'
EXPECTED_SHA='edb4c3a25a46f652424787888bad8bb2e02e615c58c9684a38aba46b981049a3'
EXPECTED_BYTES=57864
RUN_ID='33062040916'
JOB_ID='98482926278'

read=os.environ['READ_TOKEN']; write=os.environ['RELEASE_TOKEN']
assert read and write

env=os.environ.copy(); env['GH_TOKEN']=write
raw=subprocess.check_output(['gh','api',f'repos/{REPO}/releases/tags/{TAG}'],env=env,text=True)
release=json.loads(raw)
assert release['prerelease'] is True and release['draft'] is False
release_id=str(release['id'])
assets={a['name']:a for a in release['assets']}
za=assets[ASSET]; sa=assets[SHA_ASSET]
assert za['size']==EXPECTED_BYTES, za['size']
assert za['digest']==f'sha256:{EXPECTED_SHA}', za['digest']
asset_id=str(za['id']); sha_asset_id=str(sa['id'])

root=Path('gov-live')
if root.exists(): shutil.rmtree(root)
subprocess.run(['git','clone','--depth','1',f'https://x-access-token:{read}@github.com/{REPO}.git',str(root)],check=True)

def write_text(rel,text):
    (root/rel).write_text(text,encoding='utf-8')

mirror=f'''# Runtime ZIP Mirror Status · skill-book V4.6

状态：`PUBLISHED_REMOTE_VERIFIED`

V4.6 Candidate 已通过 `core-free-runner-public` 临时机器 Release Gate 完成远端 Candidate Asset 发布；临时 Workflow 只用于本次发布验证，不进入 Public Runner Current。

## Published Distribution Authority

- Release：`skill-book V4.6 Candidate`（prerelease）
- Tag：`{TAG}`
- Release ID：`{release_id}`
- File：`{ASSET}`
- Remote Asset ID：`{asset_id}`
- Bytes：`{EXPECTED_BYTES}`
- SHA-256：`{EXPECTED_SHA}`
- SHA Asset ID：`{sha_asset_id}`
- Source Commit：`{SOURCE}`
- Runner Run：`{RUN_ID}`
- Runner Job：`{JOB_ID}`
- Unit Tests：`27/27 PASS`
- Remote download readback：PASS
- ZIP CRC：PASS
- Unsafe Path：0
- Duplicate Path：0
- pycache/pyc：0
- Production Write：0

下载地址：

`https://github.com/llhzx2018/gov-doc/releases/download/{TAG}/{ASSET}`

SHA 文件：

`https://github.com/llhzx2018/gov-doc/releases/download/{TAG}/{SHA_ASSET}`

## Authority Boundary

- Source：`skills/skill-book/V4.6/`
- Mother Overlay：`mother-specs/skill-book/V4.6/SKILL_BOOK_V4.6_CANDIDATE_OVERLAY.md`
- Source Current：`skill-book V3.5`
- V4.6：`CANDIDATE / NOT CURRENT`
- Installed Runtime Observation：`skill-book V4.5 Candidate`
- Real Reader Forward Evidence：`NOT_RUN`
- Backend V4.6 Runtime Forward Test：`NOT_RUN`
- Current Promotion：`NOT_AUTHORIZED`

发布前本地 ZIP `SHA-256=aa7909d64928dfe59ec0aee8383d3d1efd89ad67aa92ffaf847a2ce9e43b5d4e` 只保留为 pre-release local build identity；远端下载回读验证通过的 `{EXPECTED_SHA}` 为 Published Distribution Authority。
'''
write_text('distribution/skills/candidates/skill-book/V4.6/RUNTIME_ZIP_MIRROR_STATUS.md',mirror)

readme=f'''# skill-book V4.6 Candidate · Source Distribution

> 状态：`CANDIDATE / NOT CURRENT`  
> Distribution：`PUBLISHED_REMOTE_VERIFIED`  
> Source Authority：`skills/skill-book/V4.6/`  
> Candidate Mother Overlay：`mother-specs/skill-book/V4.6/SKILL_BOOK_V4.6_CANDIDATE_OVERLAY.md`  
> Source Current保持：`skill-book V3.5`

## Candidate Purpose

V4.6 保留 V4.5 已验证有效的 Reader-facing Cleanliness、Pedagogical Rhythm Diversity、Feedback Closure 与独立 DO Evidence 边界，并新增 Adequacy Closure：Complexity-Calibrated Chapter Depth、Practical Asset Adequacy、Training Instrument Strength、SEALED_STANDALONE_FORWARD、Post-Draft Baseline Differential。

目标不是让书更长，而是阻止“读起来更自然，但复杂任务和关键工具仍被系统性写薄”的假成功。

## Source Validation

- Source Commit：`{SOURCE}`
- Python unit tests：`27/27 PASS`
- Python syntax：`PASS`
- Real Reader Forward Evidence：`NOT_RUN`
- Backend V4.6 Runtime Forward Test：`NOT_RUN`
- Current Promotion：`NOT_AUTHORIZED`

## Published Candidate ZIP

- Tag：`{TAG}`
- Release ID：`{release_id}`
- File：`{ASSET}`
- Bytes：`{EXPECTED_BYTES}`
- SHA-256：`{EXPECTED_SHA}`
- Asset ID：`{asset_id}`
- SHA Asset ID：`{sha_asset_id}`
- Runner Run：`{RUN_ID}`
- Remote Download Readback：`PASS`
- ZIP CRC / Unsafe Path / Duplicate Path / pycache：`PASS`

直接下载：`https://github.com/llhzx2018/gov-doc/releases/download/{TAG}/{ASSET}`

V4.6 仍为 `CANDIDATE / NOT CURRENT`。Source Current 保持 V3.5；Installed Runtime Observation 在用户实际更新前仍为 V4.5。真人 READ / LEARN / TRAIN Evidence 与后台 V4.6 SEALED Runtime 测试尚未执行，因此不得晋升 Current。
'''
write_text('distribution/skills/candidates/skill-book/V4.6/README.md',readme)

p=root/'CURRENT.md'; s=p.read_text(encoding='utf-8')
old='`skill-book V4.0/V4.1/V4.2/V4.3/V4.4` 为保留的历史 Candidate，`V4.5` 为最新 Candidate；六者均未晋升 Source Current，也未进入 Current Distribution。'
new='`skill-book V4.0/V4.1/V4.2/V4.3/V4.4/V4.5` 为保留的历史 Candidate，`V4.6` 为最新 Candidate；七者均未晋升 Source Current。V4.6 已进入 Candidate Distribution，但未进入 Current Distribution。'
if old in s: s=s.replace(old,new)
else: assert new in s
assert '| skill-book | V3.5 | V4.5 CANDIDATE（非 Current） |' in s
p.write_text(s,encoding='utf-8')

p=root/'distribution/skills/CURRENT_SKILL_DOWNLOAD_INDEX.md'; s=p.read_text(encoding='utf-8'); marker='## Candidate（不改变 Current）'; assert s.count(marker)==1; head=s.split(marker,1)[0]
block=f'''## Candidate（不改变 Current）

`skill-book V4.6` 是最新 `CANDIDATE / NOT CURRENT`；Source Current 仍为 V3.5，且 V4.6 不包含在 Current 总包中。Installed Runtime Observation 在用户实际更新前仍为 V4.5。

- [直接下载 skill-book V4.6 Candidate ZIP](https://github.com/llhzx2018/gov-doc/releases/download/{TAG}/{ASSET})
- [下载 SHA-256 文件](https://github.com/llhzx2018/gov-doc/releases/download/{TAG}/{SHA_ASSET})
- [查看 V4.6 Candidate Release](https://github.com/llhzx2018/gov-doc/releases/tag/{TAG})
- [查看 V4.6 Candidate Source](https://github.com/llhzx2018/gov-doc/tree/main/skills/skill-book/V4.6)
- [查看 V4.6 Candidate Mother Overlay](https://github.com/llhzx2018/gov-doc/blob/main/mother-specs/skill-book/V4.6/SKILL_BOOK_V4.6_CANDIDATE_OVERLAY.md)
- [查看 V4.6 Candidate 分发说明](https://github.com/llhzx2018/gov-doc/blob/main/distribution/skills/candidates/skill-book/V4.6/README.md)

Published Distribution Identity：

- Bytes：`{EXPECTED_BYTES}`
- SHA-256：`{EXPECTED_SHA}`
- Release ID：`{release_id}`
- Remote Asset ID：`{asset_id}`
- SHA Asset ID：`{sha_asset_id}`
- Exact Source Commit：`{SOURCE}`
- Runner Run：`{RUN_ID}`
- Runner Job：`{JOB_ID}`
- Unit Tests：`27/27 PASS`
- Remote Download Readback：`PASS`
- ZIP CRC / Unsafe Path / Duplicate Path / pycache：`PASS`
- Status：`PUBLISHED_REMOTE_VERIFIED`

发布前本地构建 SHA `aa7909d64928dfe59ec0aee8383d3d1efd89ad67aa92ffaf847a2ce9e43b5d4e` 只保留为 pre-release local build identity；正式 Candidate Distribution 以远端回读验证通过的 `{EXPECTED_SHA}` 为 Authority。

历史 Candidate：

- [skill-book V4.5](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.5)
- [skill-book V4.4](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.4)
- [skill-book V4.3](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.3)
- [skill-book V4.2](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.2)
- [skill-book V4.1](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.1)
- [skill-book V4.0](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.0)
'''
p.write_text(head+block,encoding='utf-8')

changed=subprocess.check_output(['git','-C',str(root),'diff','--name-only'],text=True).splitlines()
expected=['CURRENT.md','distribution/skills/CURRENT_SKILL_DOWNLOAD_INDEX.md','distribution/skills/candidates/skill-book/V4.6/README.md','distribution/skills/candidates/skill-book/V4.6/RUNTIME_ZIP_MIRROR_STATUS.md']
assert sorted(changed)==sorted(expected),(changed,expected)
subprocess.run(['git','-C',str(root),'config','user.name','VF Release Automation'],check=True)
subprocess.run(['git','-C',str(root),'config','user.email','release@kewaro.com'],check=True)
subprocess.run(['git','-C',str(root),'add',*expected],check=True)
subprocess.run(['git','-C',str(root),'commit','-m','skill-book: reconcile V4.6 published candidate authority'],check=True)
commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
subprocess.run(['git','-C',str(root),'remote','set-url','origin',f'https://x-access-token:{write}@github.com/{REPO}.git'],check=True)
subprocess.run(['git','-C',str(root),'push','origin','HEAD:main'],check=True)
subprocess.run(['git','-C',str(root),'fetch','origin','main'],check=True)
remote=subprocess.check_output(['git','-C',str(root),'rev-parse','origin/main'],text=True).strip(); assert remote==commit,(remote,commit)
cur=subprocess.check_output(['git','-C',str(root),'show','origin/main:CURRENT.md'],text=True); assert '`V4.6` 为最新 Candidate' in cur
idx=subprocess.check_output(['git','-C',str(root),'show','origin/main:distribution/skills/CURRENT_SKILL_DOWNLOAD_INDEX.md'],text=True); assert EXPECTED_SHA in idx
mir=subprocess.check_output(['git','-C',str(root),'show','origin/main:distribution/skills/candidates/skill-book/V4.6/RUNTIME_ZIP_MIRROR_STATUS.md'],text=True); assert 'PUBLISHED_REMOTE_VERIFIED' in mir and asset_id in mir
print(f'V46_GOV_DOC_RECONCILE_COMMIT={commit}')
print(f'FINAL_RELEASE_ID={release_id}')
print(f'FINAL_ASSET_ID={asset_id}')
print(f'FINAL_SHA_ASSET_ID={sha_asset_id}')
print('V46_GOVERNANCE_REMOTE_READBACK=PASS')
