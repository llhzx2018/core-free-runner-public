#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo P02_V2529_PUBLICATION_ERROR_LINE=$LINENO' ERR

PRODUCT_REPO=llhzx2018/vf-library
UPDATES_REPO=llhzx2018/core-updates
TAG=v2.5.29
VERSION=2.5.29
SOURCE=387655e222c1fed0b6e4559b66d254dba5d3c8e4
SOURCE_TREE=aac3c6d27a33dbbf9f036720c0f2b66d6dbae5f5
MERGE_MAIN=e02551fc21a8dfab2d08b77eac0a3eb383cecc62
FORMAL_RUN=33122167549
FORMAL_JOB=98691461762
FORMAL_ARTIFACT=9666882798
ARTIFACT_NAME=P02-V2.5.29-FORMAL-RELEASE-SET
WORK="${RUNNER_TEMP:-/tmp}/p02-v2529-publish-${GITHUB_RUN_ID:-local}"
rm -rf "$WORK"; mkdir -p "$WORK"
cd "$WORK"

echo '== Source / main / tag fence =='
git clone -q --filter=blob:none "https://x-access-token:${WRITE_TOKEN}@github.com/${PRODUCT_REPO}.git" product
cd product
git fetch -q origin "$SOURCE" main
MAIN=$(git rev-parse origin/main)
test "$MAIN" = "$MERGE_MAIN"
test "$(git show -s --format=%T "$SOURCE")" = "$SOURCE_TREE"
test "$(git show -s --format=%T "$MAIN")" = "$SOURCE_TREE"
test "$(git merge-base "$SOURCE" "$MAIN")" = "$SOURCE"
if git ls-remote --exit-code origin "refs/tags/$TAG" >/dev/null 2>&1; then echo "Tag $TAG already exists" >&2; exit 1; fi
cd ..
echo P02_PUBLICATION_SOURCE_FENCE=PASS

echo '== Fetch exact PASS artifact =='
mkdir release-set
gh run download "$FORMAL_RUN" --repo llhzx2018/core-free-runner-public --name "$ARTIFACT_NAME" --dir release-set
# Artifact preserves product/build/v2529-a or flattens to files depending on action packaging; locate authoritative SHA file.
SUMS=$(find release-set -type f -name SHA256SUMS.txt -print -quit)
test -n "$SUMS"
ASSET_DIR=$(dirname "$SUMS")
cd "$ASSET_DIR"
sha256sum -c SHA256SUMS.txt
for f in \
  VF_Library_V2.5.29_FULL.zip \
  VF_Library_V2.5.29_UPDATE.zip \
  VF_Library_V2.5.29_ATOMIC.zip \
  repair-v2.5.29.php \
  VF_Library_V2.5.29_SOURCE.zip \
  VF_Library_V2.5.29_RELEASE_MANIFEST.json \
  VF_Library_V2.5.29_RELEASE_NOTES.md \
  SHA256SUMS.txt; do test -f "$f"; done
UPDATE_SHA=$(sha256sum VF_Library_V2.5.29_UPDATE.zip|awk '{print $1}')
UPDATE_BYTES=$(stat -c%s VF_Library_V2.5.29_UPDATE.zip)
FULL_SHA=$(sha256sum VF_Library_V2.5.29_FULL.zip|awk '{print $1}')
FULL_BYTES=$(stat -c%s VF_Library_V2.5.29_FULL.zip)
REPAIR_SHA=$(sha256sum repair-v2.5.29.php|awk '{print $1}')
REPAIR_BYTES=$(stat -c%s repair-v2.5.29.php)
python3 - <<'PY'
import json
m=json.load(open('VF_Library_V2.5.29_RELEASE_MANIFEST.json',encoding='utf-8'))
assert m['project_id']=='P02' and m['version']=='2.5.29' and m['schema_version']==2401
assert m['source_commit']=='387655e222c1fed0b6e4559b66d254dba5d3c8e4'
assert m['source_tree']=='aac3c6d27a33dbbf9f036720c0f2b66d6dbae5f5'
assert m['production_changed'] is False
PY
cd "$WORK"
echo P02_PUBLICATION_ARTIFACT_FENCE=PASS

echo '== Exact tag and GitHub Release =='
# Lightweight tag points exactly to machine-verified source.
gh api --method POST "repos/${PRODUCT_REPO}/git/refs" -f ref="refs/tags/${TAG}" -f sha="$SOURCE" >/tmp/p02-tag.json
gh release create "$TAG" --repo "$PRODUCT_REPO" --title "VF Library V2.5.29" --notes-file "$ASSET_DIR/VF_Library_V2.5.29_RELEASE_NOTES.md" \
  "$ASSET_DIR/VF_Library_V2.5.29_FULL.zip" \
  "$ASSET_DIR/VF_Library_V2.5.29_UPDATE.zip" \
  "$ASSET_DIR/VF_Library_V2.5.29_ATOMIC.zip" \
  "$ASSET_DIR/repair-v2.5.29.php" \
  "$ASSET_DIR/VF_Library_V2.5.29_SOURCE.zip" \
  "$ASSET_DIR/VF_Library_V2.5.29_RELEASE_MANIFEST.json" \
  "$ASSET_DIR/VF_Library_V2.5.29_RELEASE_NOTES.md" \
  "$ASSET_DIR/SHA256SUMS.txt"
RELEASE_JSON=$(gh api "repos/${PRODUCT_REPO}/releases/tags/${TAG}")
RELEASE_ID=$(printf '%s' "$RELEASE_JSON"|jq -r .id)
RELEASED_AT=$(printf '%s' "$RELEASE_JSON"|jq -r .published_at)
test "$RELEASE_ID" != null
test -n "$RELEASED_AT"
echo P02_GITHUB_RELEASE=PASS

echo '== Remote asset byte/hash readback =='
mkdir remote-assets
for f in \
  VF_Library_V2.5.29_FULL.zip \
  VF_Library_V2.5.29_UPDATE.zip \
  VF_Library_V2.5.29_ATOMIC.zip \
  repair-v2.5.29.php \
  VF_Library_V2.5.29_SOURCE.zip \
  VF_Library_V2.5.29_RELEASE_MANIFEST.json \
  VF_Library_V2.5.29_RELEASE_NOTES.md \
  SHA256SUMS.txt; do gh release download "$TAG" --repo "$PRODUCT_REPO" --pattern "$f" --dir remote-assets; done
for f in remote-assets/*; do n=$(basename "$f"); test "$(sha256sum "$f"|awk '{print $1}')" = "$(sha256sum "$ASSET_DIR/$n"|awk '{print $1}')"; test "$(stat -c%s "$f")" = "$(stat -c%s "$ASSET_DIR/$n")"; done
( cd remote-assets && sha256sum -c SHA256SUMS.txt )
echo P02_REMOTE_ASSETS=PASS

echo '== Publish core-updates P02 =='
git clone -q --branch main "https://x-access-token:${WRITE_TOKEN}@github.com/${UPDATES_REPO}.git" updates
cd updates
python3 - "$UPDATE_BYTES" "$UPDATE_SHA" "$RELEASE_ID" "$RELEASED_AT" <<'PY'
from pathlib import Path
import json,sys
p=Path('projects/P02.json'); d=json.loads(p.read_text(encoding='utf-8'))
assert d['project_id']=='P02' and d['component_id']=='APP'
assert d['target_version']=='2.5.28' and d['from_versions']==['2.5.27']
assert d['release_tag']=='v2.5.28' and d['release_id']==375316679
assert d['product_identity']=='7861999d99a8de385bdd73f7892477e197c4559c'
d.update({
 'current_version':'2.5.28',
 'target_version':'2.5.29',
 'update_type':'ATOMIC',
 'from_versions':['2.5.28'],
 'schema_from':'2401','schema_to':'2401',
 'repository':'llhzx2018/vf-library',
 'release_tag':'v2.5.29',
 'release_id':int(sys.argv[3]),
 'product_identity':'387655e222c1fed0b6e4559b66d254dba5d3c8e4',
 'asset_name':'VF_Library_V2.5.29_UPDATE.zip',
 'asset_bytes':int(sys.argv[1]),
 'asset_sha256':sys.argv[2],
 'backup_required':True,
 'rollback_supported':True,
 'released_at':sys.argv[4],
 'notes':'P02 · VF Library V2.5.29 正式交付 Common Product Baseline V2：统一 System Info / System Baseline / Runtime Health / Online Update / Backup-Restore 运维语义，并采用 PERSONAL_SINGLE_ADMIN 会话与高风险 Step-up 基线。Schema 2401 不变、无迁移。Formal Gate Run 33122167549 / Job 98691461762 PASS；FULL 全新安装、Common Baseline V2 DRIFT=0/UNKNOWN=0、V2.5.28 → V2.5.29 Atomic 数据保留升级、SQLite 完整性与外键均真实通过。Production 需 Owner 在后台执行在线升级后另行收口。'
})
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
PY
python3 -m json.tool projects/P02.json >/dev/null
git diff --check
test "$(git diff --name-only)" = projects/P02.json
git config user.name VictorForge; git config user.email llhzx2018@gmail.com
git add projects/P02.json
git commit -m 'release(P02): publish V2.5.29 update channel'
git push origin main
UPDATES_COMMIT=$(git rev-parse HEAD)
cd "$WORK"
echo P02_CORE_UPDATES_WRITE=PASS

echo '== Final remote publication truth =='
gh api "repos/${PRODUCT_REPO}/git/ref/tags/${TAG}" --jq .object.sha | grep -Fx "$SOURCE"
gh api "repos/${PRODUCT_REPO}/releases/tags/${TAG}" --jq '.draft==false and .prerelease==false' | grep -Fx true
REMOTE_MANIFEST=$(gh api "repos/${UPDATES_REPO}/contents/projects/P02.json?ref=main" --jq .content | base64 -d)
printf '%s' "$REMOTE_MANIFEST" | jq -e --arg sha "$UPDATE_SHA" --argjson bytes "$UPDATE_BYTES" --argjson rid "$RELEASE_ID" '.target_version=="2.5.29" and .current_version=="2.5.28" and .from_versions==["2.5.28"] and .schema_from=="2401" and .schema_to=="2401" and .release_tag=="v2.5.29" and .release_id==$rid and .product_identity=="387655e222c1fed0b6e4559b66d254dba5d3c8e4" and .asset_name=="VF_Library_V2.5.29_UPDATE.zip" and .asset_sha256==$sha and .asset_bytes==$bytes and .backup_required==true and .rollback_supported==true' >/dev/null
mkdir -p "$GITHUB_WORKSPACE/vf-agent/results"
cat > "$GITHUB_WORKSPACE/vf-agent/results/P02-V2.5.29-FORMAL-RELEASE.json" <<EOF
{
  "schema":"vf-public-runner-result/v1",
  "project_id":"P02",
  "gate":"V2.5.29_FORMAL_RELEASE",
  "status":"SUCCESS",
  "pass":true,
  "version":"2.5.29",
  "source_version":"2.5.28",
  "candidate_source_sha":"$SOURCE",
  "candidate_source_tree":"$SOURCE_TREE",
  "product_main_merge_sha":"$MERGE_MAIN",
  "schema_version":"2401",
  "formal_gate":{"run_id":$FORMAL_RUN,"job_id":$FORMAL_JOB,"artifact_id":$FORMAL_ARTIFACT,"status":"PASS"},
  "tag":"$TAG",
  "release_id":$RELEASE_ID,
  "released_at":"$RELEASED_AT",
  "assets":{"update":{"name":"VF_Library_V2.5.29_UPDATE.zip","bytes":$UPDATE_BYTES,"sha256":"$UPDATE_SHA"},"full":{"bytes":$FULL_BYTES,"sha256":"$FULL_SHA"},"repair":{"bytes":$REPAIR_BYTES,"sha256":"$REPAIR_SHA"}},
  "core_updates":{"commit":"$UPDATES_COMMIT","target_version":"2.5.29","from_versions":["2.5.28"]},
  "production":{"changed_by_publication":false,"status":"UPGRADE_REQUIRED"}
}
EOF
cat "$GITHUB_WORKSPACE/vf-agent/results/P02-V2.5.29-FORMAL-RELEASE.json"
echo P02_V2529_PUBLICATION=PASS
