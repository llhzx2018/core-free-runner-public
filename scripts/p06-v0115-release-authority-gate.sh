#!/usr/bin/env bash
set -Eeuo pipefail
: "${GH_TOKEN:?GH_TOKEN required}"

AUTH='64781f1c6c881e5365839223b1e92df1480b4334'
BASE='a9300382d3a862fb599b8b928961ead38dee8f31'
CORE='0e834d734a0a1ed6b2173feee3435eb8f6015d96'
ROOT="$RUNNER_TEMP/p06-v0115-authority-gate"
rm -rf "$ROOT" && mkdir -p "$ROOT"

test "$(gh api repos/llhzx2018/vf-press/git/ref/heads/main --jq .object.sha)" = "$BASE"
test "$(gh api repos/llhzx2018/vf-press/git/ref/heads/governance/p06-v0115-release-authority-closure-20260828 --jq .object.sha)" = "$AUTH"
test "$(gh api repos/llhzx2018/core-updates/git/ref/heads/main --jq .object.sha)" = "$CORE"

gh api repos/llhzx2018/vf-press/compare/$BASE...$AUTH > "$ROOT/compare.json"
python3 - "$ROOT/compare.json" <<'PY'
import json,sys
c=json.load(open(sys.argv[1]))
files=[x['filename'] for x in c['files']]
assert files==['VF_PROJECT.json'],files
assert c['ahead_by']==1,c['ahead_by']
print('P06_V0115_AUTHORITY_DIFF=PASS')
PY

gh api "repos/llhzx2018/vf-press/contents/VF_PROJECT.json?ref=$AUTH" --jq .content | tr -d '\n' | base64 -d > "$ROOT/VF_PROJECT.json"
python3 - "$ROOT/VF_PROJECT.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))
assert p['project_id']=='P06'
assert p['version']=='0.1.15' and p['schema']==3
assert p['lifecycle']=='RELEASE_CURRENT_PRODUCTION_PENDING_OWNER_UPDATE'
assert p['current_phase']=='V0_1_15_RELEASE_CURRENT_PRODUCTION_PENDING_OWNER_UPDATE'
assert p['next_gate']=='OWNER_AUTHENTICATED_PRODUCTION_UPDATE_TO_V0_1_15'
assert p['human_ui_exposure_v0_1_15']['state']=='RELEASED'
r=p['release_evidence']
assert r['tag']=='v0.1.15'
assert r['product_exact_source']=='561e59a82f035e2622c4567710bec06a1c50dab3'
assert r['source_sha']=='a9300382d3a862fb599b8b928961ead38dee8f31'
assert r['release_id']==378572142
assert r['full_asset_id']==533972860 and r['full_bytes']==271733
assert r['full_sha256']=='03702b4c0401f5777cfbe52702821f84a11a83e1ea2a06680b0ead3808820cd7'
assert r['update_asset_id']==533972862 and r['update_bytes']==278578
assert r['update_sha256']=='152c44d18c55d9d022b8eabf71628d3faf9edc229a54badf1c9887fe8324e5fe'
assert r['core_updates_manifest_commit']=='0e834d734a0a1ed6b2173feee3435eb8f6015d96'
assert r['supported_from_versions']==['0.1.12','0.1.13','0.1.14']
assert r['online_discovery']=='PASS_REAL_V0_1_12_SERVICE'
assert r['production_write']=='NOT_EXECUTED_OWNER_ACTION_REQUIRED'
prod=p['production_update_state']
assert prod['observed_runtime_version']=='0.1.12'
assert prod['observed_runtime_evidence']=='OWNER_DIRECT_READBACK_2026_08_24'
assert prod['observed_schema']=='UNKNOWN'
assert prod['target_version']=='0.1.15'
assert prod['supported_from_versions']==['0.1.12','0.1.13','0.1.14']
assert prod['production_update']=='PENDING_OWNER_AUTHENTICATED_UPDATE_TO_V0_1_15'
assert prod['agent_production_write']=='NOT_EXECUTED'
assert prod['release_available']=='0.1.15'
print('P06_V0115_AUTHORITY_FIELDS=PASS')
print('P06_V0115_PRODUCTION_TRUTH_PRESERVED=PASS')
PY

# Independent live release + manifest fences.
test "$(gh api repos/llhzx2018/vf-press/git/ref/tags/v0.1.15 --jq .object.sha)" = "$BASE"
gh api repos/llhzx2018/vf-press/releases/tags/v0.1.15 > "$ROOT/release.json"
gh api "repos/llhzx2018/core-updates/contents/projects/P06.json?ref=$CORE" --jq .content | tr -d '\n' | base64 -d > "$ROOT/P06.json"
python3 - "$ROOT/release.json" "$ROOT/P06.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); m=json.load(open(sys.argv[2]))
assert r['id']==378572142 and r['tag_name']=='v0.1.15'
a={x['name']:x for x in r['assets']}['VF_Press_V0.1.15_UPDATE.zip']
assert a['id']==533972862 and a['size']==278578
assert a.get('digest')=='sha256:152c44d18c55d9d022b8eabf71628d3faf9edc229a54badf1c9887fe8324e5fe'
assert m['target_version']=='0.1.15'
assert m['from_versions']==['0.1.12','0.1.13','0.1.14']
assert m['release_id']==378572142
assert m['product_identity']=='a9300382d3a862fb599b8b928961ead38dee8f31'
assert m['asset_name']=='VF_Press_V0.1.15_UPDATE.zip'
assert m['asset_bytes']==278578
assert m['asset_sha256']=='152c44d18c55d9d022b8eabf71628d3faf9edc229a54badf1c9887fe8324e5fe'
print('P06_V0115_LIVE_RELEASE_MANIFEST_FENCE=PASS')
PY

echo P06_V0115_AUTHORITY_SOURCE="$AUTH"
echo P06_V0115_AUTHORITY_GATE=PASS
