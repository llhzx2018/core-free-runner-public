from pathlib import Path
import json, os, subprocess, shutil

REPO='llhzx2018/gov-doc'
TAG='skill-book-v4.6-candidate-20260827'
SOURCE='27ca368b9f7bc8d6160ff5049562c74cb440144b'
ASSET='skill-book_V4.6_CANDIDATE_20260827.zip'
SHA_ASSET=ASSET+'.sha256'
EXPECTED_SHA='edb4c3a25a46f652424787888bad8bb2e02e615c58c9684a38aba46b981049a3'
EXPECTED_BYTES=57864

read=os.environ['READ_TOKEN']
assert read

env=os.environ.copy()
env['GH_TOKEN']=read
raw=subprocess.check_output(['gh','api',f'repos/{REPO}/releases/tags/{TAG}'],env=env,text=True)
release=json.loads(raw)
assert release['prerelease'] is True and release['draft'] is False
assert str(release['id'])=='377727178'
assets={a['name']:a for a in release['assets']}
za=assets[ASSET]
sa=assets[SHA_ASSET]
assert za['size']==EXPECTED_BYTES, za['size']
assert za['digest']==f'sha256:{EXPECTED_SHA}', za['digest']
asset_id=str(za['id'])
sha_asset_id=str(sa['id'])

root=Path('gov-live')
if root.exists():
    shutil.rmtree(root)
subprocess.run(['git','clone','--depth','1',f'https://x-access-token:{read}@github.com/{REPO}.git',str(root)],check=True)

current=(root/'CURRENT.md').read_text(encoding='utf-8')
assert '| skill-book | V3.5 | V4.5 CANDIDATE（非 Current） |' in current
assert '`V4.6` 为最新 Candidate' in current
assert 'V4.6 已进入 Candidate Distribution，但未进入 Current Distribution' in current

index=(root/'distribution/skills/CURRENT_SKILL_DOWNLOAD_INDEX.md').read_text(encoding='utf-8')
assert '`skill-book V4.6` 是最新 `CANDIDATE / NOT CURRENT`' in index
assert EXPECTED_SHA in index
assert f'Remote Asset ID：`{asset_id}`' in index
assert f'SHA Asset ID：`{sha_asset_id}`' in index
assert SOURCE in index
assert 'Status：`PUBLISHED_REMOTE_VERIFIED`' in index

mirror=(root/'distribution/skills/candidates/skill-book/V4.6/RUNTIME_ZIP_MIRROR_STATUS.md').read_text(encoding='utf-8')
assert '状态：`PUBLISHED_REMOTE_VERIFIED`' in mirror
assert EXPECTED_SHA in mirror
assert f'Remote Asset ID：`{asset_id}`' in mirror
assert f'SHA Asset ID：`{sha_asset_id}`' in mirror
assert SOURCE in mirror
assert 'Source Current：`skill-book V3.5`' in mirror
assert 'Installed Runtime Observation：`skill-book V4.5 Candidate`' in mirror
assert 'Backend V4.6 Runtime Forward Test：`NOT_RUN`' in mirror
assert 'Current Promotion：`NOT_AUTHORIZED`' in mirror

readme=(root/'distribution/skills/candidates/skill-book/V4.6/README.md').read_text(encoding='utf-8')
assert 'Distribution：`PUBLISHED_REMOTE_VERIFIED`' in readme
assert EXPECTED_SHA in readme
assert SOURCE in readme

version=(root/'skills/skill-book/V4.6/VERSION').read_text(encoding='utf-8').strip()
assert version=='4.6'

print('V46_GOVERNANCE_REMOTE_READBACK=PASS')
print('V46_GOVERNANCE_WRITE=0')
print('SOURCE_CURRENT=V3.5')
print('LATEST_CANDIDATE=V4.6')
print('INSTALLED_RUNTIME_OBSERVATION=V4.5')
print(f'FINAL_RELEASE_ID={release["id"]}')
print(f'FINAL_ASSET_ID={asset_id}')
print(f'FINAL_SHA_ASSET_ID={sha_asset_id}')
print(f'FINAL_ASSET_BYTES={EXPECTED_BYTES}')
print(f'FINAL_ASSET_SHA256={EXPECTED_SHA}')
