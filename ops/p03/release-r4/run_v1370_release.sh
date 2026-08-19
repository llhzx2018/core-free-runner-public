#!/usr/bin/env bash
set -Eeuo pipefail

: "${P03_REPOSITORY:?}"
: "${CANDIDATE_COMMIT:?}"
: "${PRODUCT_EXACT_COMMIT:?}"
: "${PRODUCTION_MAIN_BEFORE:?}"
: "${SOURCE_VERSION:?}"
: "${TARGET_VERSION:?}"
: "${TARGET_SCHEMA:?}"
: "${RELEASE_TAG:?}"
: "${ASSET_NAME:?}"
: "${PHP_TEST_IMAGE:?}"
: "${FIXTURE_PASS:?}"
: "${RELEASE_TOKEN:?}"

BASE_RT="$RUNNER_TEMP/v1370-base-runtime"
TARGET_RT="$RUNNER_TEMP/v1370-target-runtime"
RELEASE_DIR="$RUNNER_TEMP/v1370-release"
AUTH=(-H "Authorization: Bearer $RELEASE_TOKEN" -H 'Accept: application/vnd.github+json' -H 'X-GitHub-Api-Version: 2022-11-28')

branch_sha(){
  local branch="$1"
  curl -fsS "${AUTH[@]}" "https://api.github.com/repos/$P03_REPOSITORY/branches/$branch" | python3 -c 'import json,sys; print(json.load(sys.stdin)["commit"]["sha"])'
}

printf '%s\n' '=== CURRENT TRUTH ==='
test "$(git -C candidate rev-parse HEAD)" = "$CANDIDATE_COMMIT"
test "$(git -C production rev-parse HEAD)" = "$PRODUCTION_MAIN_BEFORE"
test "$(tr -d '\r\n' < candidate/VERSION)" = "$TARGET_VERSION"
test "$(tr -d '\r\n' < production/VERSION)" = "$SOURCE_VERSION"
test "$(tr -d '\r\n' < candidate/database/schema/SCHEMA_VERSION)" = "$TARGET_SCHEMA"
test "$(tr -d '\r\n' < production/database/schema/SCHEMA_VERSION)" = "$TARGET_SCHEMA"
remote_main=$(branch_sha main)
remote_develop=$(branch_sha develop)
test "$remote_main" = "$PRODUCTION_MAIN_BEFORE" || { echo "PRODUCTION_MAIN_DRIFT=$remote_main"; exit 73; }
test "$remote_develop" = "$CANDIDATE_COMMIT" || { echo "DEVELOP_DRIFT=$remote_develop"; exit 73; }
git -C candidate merge-base --is-ancestor "$PRODUCTION_MAIN_BEFORE" "$CANDIDATE_COMMIT"
git -C candidate merge-base --is-ancestor "$PRODUCT_EXACT_COMMIT" "$CANDIDATE_COMMIT"
bad=$(git -C candidate diff --name-only "$PRODUCT_EXACT_COMMIT" "$CANDIDATE_COMMIT" -- ':(exclude).github/**' ':(exclude)tests/**' || true)
test -z "$bad" || { echo 'RUNTIME_DRIFT_AFTER_EXACT_CANDIDATE'; echo "$bad"; exit 74; }
python3 - <<'PY'
import json
p=json.load(open('candidate/VF_PROJECT.json',encoding='utf-8'))
assert p['production_version']=='1.36.2'
assert p['candidate_version']=='1.37.0'
assert p['schema_version']==30
assert p['migration']=='NONE'
assert p['version_semantics']['allowed_source_versions']==['1.36.2']
assert p['permanent_boundaries']['project_asset_storage']=='NONE'
assert p['production_write']=='NO'
print('CURRENT_TRUTH=PASS')
PY

printf '%s\n' '=== EXACT SOURCE REGRESSION ==='
(
  cd candidate
  python3 scripts/repo_health.py .
  python3 tests/unit/schema_contract_test.py
  python3 tests/unit/project_intelligence_contract_test.py
  python3 tests/unit/project_intelligence_mcp_contract_test.py
  python3 tests/integration/schema_sqlite_test.py
  find src public -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$RUNNER_TEMP/v1370-php-lint.txt"
  node --check public/assets/app.js
  node --check public/assets/experience.js
  node --check public/assets/project-intelligence.js
)
echo "V1370_EXACT_SOURCE_REGRESSION=PASS php=$(wc -l <"$RUNNER_TEMP/v1370-php-lint.txt")"

printf '%s\n' '=== RECONSTRUCT RUNTIMES ==='
rm -rf "$BASE_RT" "$TARGET_RT" "$RELEASE_DIR"
python3 production/scripts/build_runtime.py "$BASE_RT" >/dev/null
python3 candidate/scripts/build_runtime.py "$TARGET_RT" >/dev/null
grep -Fq "define('VFAB_VERSION', '1.36.2');" "$BASE_RT/app/bootstrap.php"
grep -Fq "define('VFAB_VERSION', '1.37.0');" "$TARGET_RT/app/bootstrap.php"
grep -Fq "define('VFAB_SCHEMA_VERSION', 30);" "$BASE_RT/app/bootstrap.php"
grep -Fq "define('VFAB_SCHEMA_VERSION', 30);" "$TARGET_RT/app/bootstrap.php"
test -f "$TARGET_RT/intelligence-api.php"
test -f "$TARGET_RT/memory-api.php"
test -f "$TARGET_RT/app/ProjectIntelligenceService.php"
test -f "$TARGET_RT/assets/project-intelligence.js"
test ! -e "$TARGET_RT/app/.runtime.php"
echo "RUNTIME_RECONSTRUCTION=PASS base=$(find "$BASE_RT" -type f | wc -l) target=$(find "$TARGET_RT" -type f | wc -l)"

printf '%s\n' '=== CANONICAL ATOMIC BUILD ==='
python3 candidate/scripts/build_atomic.py --base-runtime "$BASE_RT" --target-runtime "$TARGET_RT" --output "$RELEASE_DIR" | tee "$RUNNER_TEMP/v1370-package-output.json"
(
  cd "$RELEASE_DIR"
  sha256sum -c SHA256SUMS.txt
  unzip -t VF_Forge_V1.37.0_Atomic_Upgrade.zip >/dev/null
  test "$(unzip -Z1 VF_Forge_V1.37.0_Atomic_Upgrade.zip)" = 'repair-v1.37.0.php'
  test "$(unzip -Z1 VF_Forge_V1.37.0_Atomic_Upgrade.zip | wc -l | tr -d ' ')" = '1'
  php -l repair-v1.37.0.php
  grep -Fq "const VFF_PACKAGE_ID='vf-forge';" repair-v1.37.0.php
  grep -Fq "const VFF_PACKAGE_TYPE='app';" repair-v1.37.0.php
  grep -Fq "const VFF_ATOMIC_TARGET='1.37.0';" repair-v1.37.0.php
  grep -Fq 'const VFF_ATOMIC_SCHEMA=30;' repair-v1.37.0.php
  grep -Fq 'const VFF_ATOMIC_ALLOWED=["1.36.2"];' repair-v1.37.0.php
  python3 - <<'PY'
import json
p=json.load(open('PACKAGE_MANIFEST.json',encoding='utf-8'))
assert p['package_id']=='vf-forge'
assert p['package_type']=='app'
assert p['version']=='1.37.0'
assert p['schema']==30
assert p['allowed_source_versions']==['1.36.2']
assert p['source_file_count'] > 0
m=open('SOURCE_MANIFEST.txt',encoding='utf-8').read()
for x in ['intelligence-api.php','memory-api.php','app/ProjectIntelligenceService.php','assets/project-intelligence.js']:
    assert x in m,x
for bad in ['PRIVATE_DATA','.runtime.php','storage/private','.sqlite','.db']:
    assert bad.lower() not in m.lower(),bad
print('CANONICAL_ATOMIC_REVERSE_VERIFY=PASS',p['atomic_sha256'],p['source_manifest_sha256'],p['source_file_count'])
PY
  cp VF_Forge_V1.37.0_Atomic_Upgrade.zip "$ASSET_NAME"
)
UPDATE_SHA=$(sha256sum "$RELEASE_DIR/$ASSET_NAME" | awk '{print $1}')
UPDATE_BYTES=$(stat -c%s "$RELEASE_DIR/$ASSET_NAME")
SOURCE_MANIFEST_SHA=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source_manifest_sha256"])' "$RELEASE_DIR/PACKAGE_MANIFEST.json")
echo "FORMAL_ARTIFACT=PASS sha256=$UPDATE_SHA bytes=$UPDATE_BYTES source_manifest=$SOURCE_MANIFEST_SHA"

printf '%s\n' '=== ATOMIC SUCCESS + ROLLBACK E2E ==='
(
  cd candidate
  BASE_SHA="$PRODUCTION_MAIN_BEFORE" \
  V1370_RELEASE_DIR="$RELEASE_DIR" \
  V1370_TARGET_RUNTIME="$TARGET_RT" \
  FIXTURE_PASS="$FIXTURE_PASS" \
  PHP_TEST_IMAGE="$PHP_TEST_IMAGE" \
  bash tests/maintenance/v1370_atomic_e2e.sh
) | tee "$RUNNER_TEMP/v1370-atomic-e2e.log"
grep -q 'V1370_ATOMIC_SUCCESS_PASS' "$RUNNER_TEMP/v1370-atomic-e2e.log"
grep -q 'V1370_SOURCE_AND_DATABASE_ROLLBACK_PASS' "$RUNNER_TEMP/v1370-atomic-e2e.log"
grep -q 'V1370_ATOMIC_E2E_PASS' "$RUNNER_TEMP/v1370-atomic-e2e.log"
echo 'ATOMIC_SUCCESS_AND_ROLLBACK=PASS'

printf '%s\n' '=== RELEASE PUBLICATION ==='
cat >"$RUNNER_TEMP/V1370_RELEASE_NOTES.md" <<'EOF'
# P03 · VF Forge V1.37.0

Project Intelligence / Engineering Memory 重构正式版本。

- Upgrade: V1.36.2 → V1.37.0
- Schema: 30 → 30 (Migration NONE)
- PROJECT-ASSET STORAGE: NONE
- Atomic success upgrade: PASS
- Injected failure source + SQLite rollback: PASS
- Project Intelligence / MCP contracts: PASS
- Production write during release publication: NO
EOF
export GH_TOKEN="$RELEASE_TOKEN"
if gh release view "$RELEASE_TAG" --repo "$P03_REPOSITORY" >/dev/null 2>&1; then
  rm -rf "$RUNNER_TEMP/existing-release"; mkdir -p "$RUNNER_TEMP/existing-release"
  gh release download "$RELEASE_TAG" --repo "$P03_REPOSITORY" -p "$ASSET_NAME" -D "$RUNNER_TEMP/existing-release"
  test "$(sha256sum "$RUNNER_TEMP/existing-release/$ASSET_NAME" | awk '{print $1}')" = "$UPDATE_SHA"
  test "$(stat -c%s "$RUNNER_TEMP/existing-release/$ASSET_NAME")" = "$UPDATE_BYTES"
else
  gh release create "$RELEASE_TAG" "$RELEASE_DIR/$ASSET_NAME" --repo "$P03_REPOSITORY" --target "$CANDIDATE_COMMIT" --title 'P03 · VF Forge V1.37.0' --notes-file "$RUNNER_TEMP/V1370_RELEASE_NOTES.md"
fi
gh api "repos/$P03_REPOSITORY/releases/tags/$RELEASE_TAG" > "$RUNNER_TEMP/v1370-release.json"
python3 - "$RUNNER_TEMP/v1370-release.json" "$ASSET_NAME" "$UPDATE_BYTES" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); name=sys.argv[2]; size=int(sys.argv[3])
assert r['tag_name']=='v1.37.0'
assert not r['draft'] and not r['prerelease']
a=[x for x in r.get('assets',[]) if x['name']==name]
assert len(a)==1,a
assert a[0]['size']==size,(a[0]['size'],size)
print('FORMAL_RELEASE_READBACK=PASS','release_id='+str(r['id']),'asset_id='+str(a[0]['id']),'bytes='+str(size),'created_at='+str(r.get('published_at') or r.get('created_at')))
PY
remote_main_after=$(branch_sha main)
tag_sha=$(curl -fsS "${AUTH[@]}" "https://api.github.com/repos/$P03_REPOSITORY/git/ref/tags/$RELEASE_TAG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["object"]["sha"])')
test "$remote_main_after" = "$PRODUCTION_MAIN_BEFORE"
test "$tag_sha" = "$CANDIDATE_COMMIT"
echo "PRODUCTION_MAIN_UNTOUCHED=PASS sha=$remote_main_after"
echo "V1370_RELEASE_READY asset=$ASSET_NAME sha256=$UPDATE_SHA bytes=$UPDATE_BYTES source_manifest=$SOURCE_MANIFEST_SHA candidate=$CANDIDATE_COMMIT production_main=$PRODUCTION_MAIN_BEFORE"
