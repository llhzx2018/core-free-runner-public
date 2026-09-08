#!/usr/bin/env bash
set -Eeuo pipefail
: "${READ_TOKEN:?}" "${WRITE_TOKEN:?}" "${CORE_REPO:?}" "${CORE_BRANCH:?}" "${CORE_BASE:?}" "${THEME_SHA:?}"
echo 'PRODUCT_WRITE_USED=NO RELEASE_WRITE_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO MIGRATION_USED=NO OPS_WRITE_USED=NO M3U8_WRITE_USED=NO'
export GH_TOKEN="$WRITE_TOKEN"
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${CORE_REPO}.git" core
cd core
git checkout -q "$CORE_BRANCH"
test "$(git rev-parse HEAD)" = "$CORE_BASE"
test "$(git rev-parse origin/main)" = "$CORE_BASE"
test "$(git hash-object projects/S01-C01.json)" = 'd6e614a91cd6a3bb08a58505bf069dad1eb01497'
test "$(git hash-object projects/S01-C02.json)" = '2896cb2d284d3c1d3ded8cd189b20049bef15d5a'
test "$(git hash-object projects/S01-C03.json)" = '5d27495f15ceb92581eb1cd227770b2d02158d4b'
test "$(gh api repos/llhzx2018/vf-tools-theme/branches/main --jq '.commit.sha')" = "$THEME_SHA"
test "$(gh api repos/llhzx2018/vf-tools-theme/git/ref/tags/v1.35.21 --jq '.object.sha')" = "$THEME_SHA"
gh api repos/llhzx2018/vf-tools-theme/releases/tags/v1.35.21 >/tmp/release.json
test "$(jq -r '.draft' /tmp/release.json)" = false
test "$(jq -r '.prerelease' /tmp/release.json)" = false
test "$(jq -r '.id' /tmp/release.json)" = '384478983'
test "$(jq -r '.assets[]|select(.name=="vf-tools-theme_V1.35.21.zip")|.id' /tmp/release.json)" = '549965404'
test "$(jq -r '.assets[]|select(.name=="vf-tools-theme_V1.35.21.zip")|.size' /tmp/release.json)" = '1806724'
test "$(jq -r '.assets[]|select(.name=="vf-tools-theme_V1.35.21.zip")|.digest' /tmp/release.json)" = 'sha256:c4f93351290385dd072b05b1a1b687fee9e05d0bfbf924c15171ba9c0ae4737e'
python3 - <<'PY'
import json
from pathlib import Path
p=Path('projects/S01-C01.json'); c=json.loads(p.read_text())
assert c['target_version']=='1.35.20'
assert c['release_tag']=='v1.35.20'
assert c['asset_sha256']=='779c48f2bbe450c5a50b01118b7cc9655e5184b41fbbcd45ca1a0158afa386b1'
assert c['runtime_files']==446
assert c['runtime_fingerprint']=='ec60d9d98b6a7406ff17d91367c03918034ac438970bc441b74b90b589508e3c'
old=c['target_version']
if old not in c['from_versions']: c['from_versions'].append(old)
c.update({
  'target_version':'1.35.21',
  'release_tag':'v1.35.21',
  'asset_name':'vf-tools-theme_V1.35.21.zip',
  'asset_bytes':1806724,
  'asset_sha256':'c4f93351290385dd072b05b1a1b687fee9e05d0bfbf924c15171ba9c0ae4737e',
  'runtime_files':446,
  'runtime_fingerprint':'9a187cc517d96014f414d70949a256aab0b001db03f9648e73137aad6c9c2c0e',
  'released_at':'2026-09-08T06:02:52Z',
  'notes':'S01-C01 1.35.21 UPDATE CREDENTIAL FIRST CLOSURE. Exact released source e27aebdc3d1674711a2ec6e9e113119bf2d9071a. In the single Tools → VF 在线更新 entry, a missing VF private update credential now changes the dominant action from a guaranteed-failing update check to 配置更新凭证 and exposes a default-visible first-run credential form. When a credential is configured, 检查全部 VF 更新 remains the primary action. Raw component state, credential source and Runtime Authority details remain in the collapsed advanced panel; token replacement and destructive clear-token confirmation remain unchanged. Credential-first Candidate Gate 34192689077 PASS; 1.35.21 Bump Gate 34192834993 PASS; Formal Release 34192974202 PASS. Release ID 384478983; asset ID 549965404; delivered asset 1806724 bytes / SHA256 c4f93351290385dd072b05b1a1b687fee9e05d0bfbf924c15171ba9c0ae4737e. Delivered Runtime Authority probe 34193034870 PASS: 446 files / 9a187cc517d96014f414d70949a256aab0b001db03f9648e73137aad6c9c2c0e. Direct upgrade eligibility from 1.35.8 through 1.35.20 is preserved. Publication does not claim Production, Static, Online or FINAL_ONLINE_PASS.'
})
assert c['from_versions']==['1.35.8','1.35.9','1.35.10','1.35.11','1.35.12','1.35.13','1.35.14','1.35.15','1.35.16','1.35.17','1.35.18','1.35.19','1.35.20']
assert c['schema_from']==c['schema_to']=='N/A'
p.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
PY
jq -e . projects/S01-C01.json >/dev/null
python3 scripts/check_manifest_contract.py >/tmp/contract.json
jq -e '.status=="PASS"' /tmp/contract.json >/dev/null
find update-core/php -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php update-core/php/tests/run.php
test "$(git hash-object projects/S01-C02.json)" = '2896cb2d284d3c1d3ded8cd189b20049bef15d5a'
test "$(git hash-object projects/S01-C03.json)" = '5d27495f15ceb92581eb1cd227770b2d02158d4b'
git diff --name-only "$CORE_BASE" | sort >/tmp/actual
printf '%s\n' projects/S01-C01.json >/tmp/expected
diff -u /tmp/expected /tmp/actual
git diff --check
git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add projects/S01-C01.json
git commit -m 'S01: stage Theme 1.35.21 update channel'
git push -q origin HEAD:"$CORE_BRANCH"
echo "CORE_C01_13521_CANDIDATE_HEAD=$(git rev-parse HEAD)"
echo 'PASS_S01_C01_13521_CORE_CANDIDATE'
