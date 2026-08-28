#!/usr/bin/env bash
set -Eeuo pipefail
: "${GH_TOKEN:?GH_TOKEN required}"

CORE_SOURCE='0e834d734a0a1ed6b2173feee3435eb8f6015d96'
RELEASE_SOURCE='a9300382d3a862fb599b8b928961ead38dee8f31'
RELEASE_ID='378572142'
UPDATE_ASSET_ID='533972862'
UPDATE_BYTES='278578'
UPDATE_SHA='152c44d18c55d9d022b8eabf71628d3faf9edc229a54badf1c9887fe8324e5fe'
ROOT="$RUNNER_TEMP/p06-v0115-manifest-gate"
rm -rf "$ROOT" && mkdir -p "$ROOT"

CURRENT_CORE="$(gh api repos/llhzx2018/core-updates/git/ref/heads/main --jq .object.sha)"
test "$CURRENT_CORE" = "$CORE_SOURCE"

gh api "repos/llhzx2018/core-updates/contents/projects/P06.json?ref=$CORE_SOURCE" --jq .content | tr -d '\n' | base64 -d > "$ROOT/P06.json"
python3 - "$ROOT/P06.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
expected={
 'schema_version':'1.0','project_id':'P06','component_id':'APP','enabled':True,
 'target_version':'0.1.15','update_type':'ATOMIC','from_versions':['0.1.12','0.1.13','0.1.14'],
 'schema_from':'3','schema_to':'3','repository':'llhzx2018/vf-press','release_tag':'v0.1.15',
 'release_id':378572142,'product_identity':'a9300382d3a862fb599b8b928961ead38dee8f31',
 'asset_name':'VF_Press_V0.1.15_UPDATE.zip','asset_bytes':278578,
 'asset_sha256':'152c44d18c55d9d022b8eabf71628d3faf9edc229a54badf1c9887fe8324e5fe',
 'backup_required':True,'rollback_supported':True,'minimum_php':'8.2.0',
 'released_at':'2026-08-28T15:18:03Z'
}
for k,v in expected.items(): assert m.get(k)==v,(k,m.get(k),v)
print('P06_V0115_MANIFEST_FIELDS=PASS')
PY

TAG_SHA="$(gh api repos/llhzx2018/vf-press/git/ref/tags/v0.1.15 --jq .object.sha)"
test "$TAG_SHA" = "$RELEASE_SOURCE"
gh api repos/llhzx2018/vf-press/releases/tags/v0.1.15 > "$ROOT/release.json"
python3 - "$ROOT/release.json" "$RELEASE_ID" "$UPDATE_ASSET_ID" "$UPDATE_BYTES" "$UPDATE_SHA" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); rid=int(sys.argv[2]); aid=int(sys.argv[3]); size=int(sys.argv[4]); sha=sys.argv[5]
assert r['id']==rid,(r['id'],rid)
assert r['tag_name']=='v0.1.15' and not r['draft'] and not r['prerelease']
a={x['name']:x for x in r['assets']}['VF_Press_V0.1.15_UPDATE.zip']
assert a['id']==aid,(a['id'],aid)
assert a['size']==size,(a['size'],size)
assert a.get('digest')==f'sha256:{sha}',(a.get('digest'),sha)
print('P06_V0115_RELEASE_ASSET_BINDING=PASS')
PY

gh release download v0.1.15 -R llhzx2018/vf-press -p 'VF_Press_V0.1.15_UPDATE.zip' -D "$ROOT"
test "$(stat -c %s "$ROOT/VF_Press_V0.1.15_UPDATE.zip")" = "$UPDATE_BYTES"
test "$(sha256sum "$ROOT/VF_Press_V0.1.15_UPDATE.zip" | awk '{print $1}')" = "$UPDATE_SHA"
echo P06_V0115_DOWNLOADED_UPDATE_SHA=PASS
echo P06_V0115_CORE_UPDATES_SOURCE="$CORE_SOURCE"
echo P06_V0115_SUPPORTED_FROM='0.1.12,0.1.13,0.1.14'
echo P06_V0115_DISTRIBUTION_MANIFEST_GATE=PASS
