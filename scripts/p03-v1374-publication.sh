#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo P03_V1374_PUBLICATION_ERROR_LINE=$LINENO' ERR
: "${WRITE_TOKEN:?}"
: "${GH_TOKEN:?}"
REPO='llhzx2018/vf-forge'
UPDATES='llhzx2018/core-updates'
TAG='v1.37.4'
SOURCE='b215f510a543ca5cf85af9e87257e2acb63d74ab'
SOURCE_TREE='75b65d094f3f487faefe5680ae4cc5162fc26552'
MERGED_MAIN='216944156c94c743f3e13635a6e4a0ac7ef5a313'
UPDATES_BASE='ea9b9e401597f50dce18ceaeb468be85dc36d2a4'
RUN_ID=33124160111
ARTIFACT_ID=9667684606
WORK="$RUNNER_TEMP/p03-v1374-publication"
rm -rf "$WORK"; mkdir -p "$WORK/release"

printf '\n== Publication source fences ==\n'
test "$(gh api repos/$REPO/branches/main --jq .commit.sha)" = "$MERGED_MAIN"
test "$(gh api repos/$UPDATES/branches/main --jq .commit.sha)" = "$UPDATES_BASE"
if gh api "repos/$REPO/git/ref/tags/$TAG" >/dev/null 2>&1; then echo 'v1.37.4 tag already exists before publication'; exit 1; fi
if gh api "repos/$REPO/releases/tags/$TAG" >/dev/null 2>&1; then echo 'v1.37.4 release already exists before publication'; exit 1; fi
echo P03_V1374_PUBLICATION_SOURCE_FENCE=PASS

printf '\n== Download exact PASS artifact ==\n'
gh run download "$RUN_ID" -R llhzx2018/core-free-runner-public -n P03-V1.37.4-FORMAL-RELEASE-SET -D "$WORK/formal"
test -f "$WORK/formal/VF_Forge_V1.37.4_Atomic_Upgrade.zip"
test -f "$WORK/formal/VF_Forge_V1.37.4_FULL.zip"
test -f "$WORK/formal/P03_V1.37.4_RELEASE_MANIFEST.json"
test -f "$WORK/formal/RELEASE_SHA256SUMS.txt"
(cd "$WORK/formal" && sha256sum -c RELEASE_SHA256SUMS.txt)
python3 - "$WORK/formal/P03_V1.37.4_RELEASE_MANIFEST.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m['schema']=='vf-p03-release/1' and m['project_id']=='P03'
assert m['version']=='1.37.4' and m['source_version']=='1.37.3' and m['schema_version']==30
assert m['candidate_source_sha']=='b215f510a543ca5cf85af9e87257e2acb63d74ab'
assert m['production_changed'] is False
PY
cp "$WORK/formal/VF_Forge_V1.37.4_Atomic_Upgrade.zip" "$WORK/release/VF_Forge_V1.37.4_UPDATE.zip"
cp "$WORK/formal/VF_Forge_V1.37.4_FULL.zip" "$WORK/release/VF_Forge_V1.37.4_FULL.zip"
test "$(sha256sum "$WORK/formal/VF_Forge_V1.37.4_Atomic_Upgrade.zip"|awk '{print $1}')" = "$(sha256sum "$WORK/release/VF_Forge_V1.37.4_UPDATE.zip"|awk '{print $1}')"
(cd "$WORK/release" && sha256sum VF_Forge_V1.37.4_UPDATE.zip VF_Forge_V1.37.4_FULL.zip > RELEASE_SHA256SUMS.txt && sha256sum -c RELEASE_SHA256SUMS.txt)
echo P03_V1374_PUBLICATION_ARTIFACT_FENCE=PASS

printf '\n== Exact tag and GitHub Release ==\n'
gh api --method POST "repos/$REPO/git/refs" -f ref="refs/tags/$TAG" -f sha="$SOURCE" >/dev/null
test "$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq .object.sha)" = "$SOURCE"
cat >"$WORK/release-notes.md" <<'EOF'
# P03 · VF Forge V1.37.4

Common Product Baseline V2 正式发布。

- 统一 System Info / System Baseline / Runtime Health / Online Update / Backup-Restore 运维语义。
- PERSONAL_SINGLE_ADMIN 会话与高风险 Step-up 基线正式进入可发布运行态。
- Common Baseline V2：DRIFT=0 / UNKNOWN=0；既有受控 Exception/N_A 保持可追踪。
- Fresh Install / Schema 30 / Backup-Restore / Project Intelligence / MCP E2E / Browser E2E 全部真实通过。
- V1.37.3 → V1.37.4 Atomic Success PASS；Source + SQLite Failure Rollback PASS。
- Schema 30 不变，Migration NONE。
- Project Asset Storage 继续保持 NONE；不建立第二套 Truth Store。
- Production 不由发布动作自动修改，需 Owner 在 VF Forge 后台确认后执行在线升级。

Formal Gate: Run 33124160111 / Job 98698131192 = PASS.
Final Exact Source Gate: Run 33124356465 / Job 98698772368 = PASS.
EOF
gh release create "$TAG" \
  "$WORK/release/VF_Forge_V1.37.4_UPDATE.zip" \
  "$WORK/release/VF_Forge_V1.37.4_FULL.zip" \
  "$WORK/release/RELEASE_SHA256SUMS.txt" \
  -R "$REPO" --title 'P03 · VF Forge V1.37.4' --notes-file "$WORK/release-notes.md" --verify-tag
REL="$WORK/release.json"; gh api "repos/$REPO/releases/tags/$TAG" > "$REL"
RELEASE_ID=$(jq -r .id "$REL"); RELEASED_AT=$(jq -r .published_at "$REL")
UPDATE_NAME='VF_Forge_V1.37.4_UPDATE.zip'
UPDATE_ID=$(jq -r --arg n "$UPDATE_NAME" '.assets[]|select(.name==$n)|.id' "$REL")
UPDATE_BYTES=$(stat -c%s "$WORK/release/$UPDATE_NAME")
UPDATE_SHA=$(sha256sum "$WORK/release/$UPDATE_NAME"|awk '{print $1}')
FULL_BYTES=$(stat -c%s "$WORK/release/VF_Forge_V1.37.4_FULL.zip")
FULL_SHA=$(sha256sum "$WORK/release/VF_Forge_V1.37.4_FULL.zip"|awk '{print $1}')
test "$(jq -r '.draft' "$REL")" = false
test "$(jq -r '.prerelease' "$REL")" = false
test "$(jq '.assets|length' "$REL")" -eq 3
python3 - "$REL" "$UPDATE_NAME" "$UPDATE_SHA" "$FULL_SHA" <<'PY'
import json,sys
r=json.load(open(sys.argv[1],encoding='utf-8')); un,us,fs=sys.argv[2:]
a={x['name']:x for x in r['assets']}
assert a[un]['digest']=='sha256:'+us
assert a['VF_Forge_V1.37.4_FULL.zip']['digest']=='sha256:'+fs
assert 'RELEASE_SHA256SUMS.txt' in a
PY
echo P03_V1374_GITHUB_RELEASE=PASS

printf '\n== Publish core-updates P03 ==\n'
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${UPDATES}.git" "$WORK/core-updates"
cd "$WORK/core-updates"
test "$(git rev-parse HEAD)" = "$UPDATES_BASE"
python3 - "projects/P03.json" "$RELEASE_ID" "$RELEASED_AT" "$UPDATE_ID" "$UPDATE_BYTES" "$UPDATE_SHA" <<'PY'
import json,sys
p=sys.argv[1]; rid=int(sys.argv[2]); released=sys.argv[3]; aid=int(sys.argv[4]); size=int(sys.argv[5]); sha=sys.argv[6]
d=json.load(open(p,encoding='utf-8'))
assert d['project_id']=='P03' and d['target_version']=='1.37.3' and d['from_versions']==['1.37.2']
assert d['schema_from']==d['schema_to']=='30'
d.update({
 'target_version':'1.37.4','update_type':'ATOMIC','from_versions':['1.37.3'],
 'schema_from':'30','schema_to':'30','repository':'llhzx2018/vf-forge',
 'release_tag':'v1.37.4','release_id':rid,
 'product_identity':'b215f510a543ca5cf85af9e87257e2acb63d74ab',
 'asset_name':'VF_Forge_V1.37.4_UPDATE.zip','asset_id':aid,'asset_bytes':size,'asset_sha256':sha,
 'backup_required':True,'rollback_supported':True,'released_at':released,
 'release_notes':{'summary':'V1.37.4：Common Product Baseline V2 正式进入 VF Forge 发布通道；Schema 30 不变，V1.37.3 → V1.37.4 Atomic/rollback 真实 PASS。'},
 'notes':'Schema 30 unchanged. Upgrade from V1.37.3 only. Migration NONE. Common Baseline V2 DRIFT=0/UNKNOWN=0. Fresh Install / Backup-Restore / Project Intelligence / MCP / Browser PASS. Atomic success and source+database rollback PASS. PROJECT-ASSET STORAGE = NONE. Production upgrade requires Owner action.'})
open(p,'w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
PY
python3 -m json.tool projects/P03.json >/dev/null
git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add projects/P03.json
git commit -m 'release(P03): publish V1.37.4 update channel'
git fetch origin main
test "$(git rev-parse origin/main)" = "$UPDATES_BASE"
git push origin HEAD:main
UPDATES_COMMIT=$(git rev-parse HEAD)
echo P03_V1374_CORE_UPDATES_WRITE=PASS

printf '\n== Final remote publication truth ==\n'
test "$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq .object.sha)" = "$SOURCE"
gh api "repos/$REPO/releases/tags/$TAG" > "$WORK/remote-release.json"
python3 - "$WORK/remote-release.json" "$UPDATE_SHA" "$FULL_SHA" <<'PY'
import json,sys
r=json.load(open(sys.argv[1],encoding='utf-8')); u,f=sys.argv[2:]
assert r['draft'] is False and r['prerelease'] is False and len(r['assets'])==3
a={x['name']:x for x in r['assets']}
assert a['VF_Forge_V1.37.4_UPDATE.zip']['digest']=='sha256:'+u
assert a['VF_Forge_V1.37.4_FULL.zip']['digest']=='sha256:'+f
PY
gh api "repos/$UPDATES/contents/projects/P03.json?ref=main" --jq .content | base64 -d > "$WORK/remote-P03.json"
python3 - "$WORK/remote-P03.json" "$RELEASE_ID" "$UPDATE_ID" "$UPDATE_BYTES" "$UPDATE_SHA" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
assert d['target_version']=='1.37.4' and d['from_versions']==['1.37.3']
assert d['schema_from']==d['schema_to']=='30' and d['release_tag']=='v1.37.4'
assert d['release_id']==int(sys.argv[2]) and d['asset_id']==int(sys.argv[3]) and d['asset_bytes']==int(sys.argv[4]) and d['asset_sha256']==sys.argv[5]
assert d['product_identity']=='b215f510a543ca5cf85af9e87257e2acb63d74ab'
assert d['backup_required'] is True and d['rollback_supported'] is True
PY
mkdir -p "$PWD/../publication-evidence"
cat > "$PWD/../publication-evidence/P03-V1.37.4-FORMAL-RELEASE.json" <<EOF
{
  "schema":"vf-public-runner-result/v1",
  "project_id":"P03",
  "gate":"V1.37.4_FORMAL_RELEASE",
  "status":"SUCCESS",
  "pass":true,
  "version":"1.37.4",
  "source_version":"1.37.3",
  "candidate_source_sha":"$SOURCE",
  "candidate_source_tree":"$SOURCE_TREE",
  "product_main_merge_sha":"$MERGED_MAIN",
  "schema_version":"30",
  "formal_gate":{"run_id":33124160111,"job_id":98698131192,"artifact_id":9667684606,"status":"PASS"},
  "final_exact_gate":{"run_id":33124356465,"job_id":98698772368,"status":"PASS"},
  "tag":"v1.37.4",
  "release_id":$RELEASE_ID,
  "released_at":"$RELEASED_AT",
  "assets":{"update":{"id":$UPDATE_ID,"name":"$UPDATE_NAME","bytes":$UPDATE_BYTES,"sha256":"$UPDATE_SHA"},"full":{"bytes":$FULL_BYTES,"sha256":"$FULL_SHA"}},
  "core_updates":{"commit":"$UPDATES_COMMIT","target_version":"1.37.4","from_versions":["1.37.3"]},
  "production":{"changed_by_publication":false,"status":"UPGRADE_REQUIRED"}
}
EOF
python3 -m json.tool "$PWD/../publication-evidence/P03-V1.37.4-FORMAL-RELEASE.json" >/dev/null
echo P03_V1374_PUBLICATION=PASS
echo RELEASE=YES
echo PRODUCTION=NO
