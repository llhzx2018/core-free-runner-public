#!/usr/bin/env bash
set -Eeuo pipefail
: "${READ_TOKEN:?}" "${WRITE_TOKEN:?}" "${SHA:?}" "${BASE_SHA:?}" "${TAG:?}" "${ASSET:?}"
echo 'FORMAL_RELEASE_GATE=ON PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO MIGRATION_USED=NO OPS_WRITE_USED=NO M3U8_WRITE_USED=NO'
export GH_TOKEN="$WRITE_TOKEN"
repo='llhzx2018/vf-tools-theme'
test "$(gh api repos/$repo/branches/main --jq '.commit.sha')" = "$SHA"
if gh api repos/$repo/git/ref/tags/$TAG >/dev/null 2>&1; then echo TAG_ALREADY_EXISTS; exit 1; fi
if gh api repos/$repo/releases/tags/$TAG >/dev/null 2>&1; then echo RELEASE_ALREADY_EXISTS; exit 1; fi
rm -rf repo
GIT_TERMINAL_PROMPT=0 git clone -q "https://x-access-token:${READ_TOKEN}@github.com/${repo}.git" repo
git -C repo checkout -q "$SHA"
test "$(git -C repo rev-parse HEAD)" = "$SHA"
test "$(tr -d '\r\n' < repo/VERSION)" = '1.35.23'
grep -F 'Version: 1.35.23' repo/src/style.css >/dev/null
grep -F 'V1.35.23_S01_MATURE_ADMIN_PAGE1_5_PREVIEW' repo/src/style.css >/dev/null
test ! -e repo/src/assets/js/admin/admin-seo-page-refinement-v1.js

# Exact release diff fence from the previous stable main.
git -C repo diff --name-only "$BASE_SHA" "$SHA" | sort >/tmp/actual
cat >/tmp/expected <<'EOF'
VERSION
src/assets/css/admin/admin-mature-product-v5.css
src/assets/css/admin/pages/brand/admin-page-brand-refinement-v1.css
src/assets/css/admin/pages/navigation/admin-page-navigation-refinement-v1.css
src/assets/css/admin/pages/page-structure/admin-page-layout-refinement-v1.css
src/assets/css/admin/pages/render/admin-page-render-refinement-v1.css
src/assets/css/admin/pages/workbench/admin-page-workbench.css
src/assets/js/admin/admin-brand-page-refinement-v1.js
src/assets/js/admin/admin-dashboard.js
src/assets/js/admin/admin-layout-page-refinement-v1.js
src/assets/js/admin/admin-navigation-page-refinement-v1.js
src/assets/js/admin/admin-render.js
src/inc/admin/admin-s01-uiux-polish.php
src/inc/admin/views/render.php
src/inc/admin/views/tabs/overview.php
src/inc/bootstrap/manifests/admin-tabs/render.php
src/style.css
tests/brand-page-live-preview-contract.php
tests/layout-page-workflow-contract.php
tests/mature-product-v5-contract.php
tests/navigation-page-refinement-contract.php
tests/render-page-refinement-contract.php
tests/render-settings-human-language-contract.php
tests/render-workflow-v4-contract.php
tests/update-refresh-policy-contract.php
tests/visible-console-v2-contract.php
tests/workbench-page-refresh-parity-contract.php
tests/workbench-primary-action-contract.php
EOF
sort -o /tmp/expected /tmp/expected
diff -u /tmp/expected /tmp/actual

# Security/upgrade invariants: no updater, recovery, schema, migration or credential implementation drift.
if git -C repo diff --name-only "$BASE_SHA" "$SHA" | grep -E '(^|/)(update|migration|schema|recovery|secrets?|credentials?)(/|\.|$)'; then echo FAIL_RELEASE_SURFACE_BOUNDARY; exit 1; fi
grep -F "current_user_can('vf_manage_theme_profile')" repo/src/inc/admin/admin-render-actions.php >/dev/null
grep -F "check_ajax_referer('theme.render.save', 'nonce')" repo/src/inc/admin/admin-render-actions.php >/dev/null
grep -F 'VF_WP_COMPONENT_RUNTIME_AUTHORITY_V1' repo/src/inc/update/class-vf-theme-runtime-authority-v1.php >/dev/null

find repo/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
for js in repo/src/assets/js/admin/admin-dashboard.js repo/src/assets/js/admin/admin-brand.js repo/src/assets/js/admin/admin-brand-page-refinement-v1.js repo/src/assets/js/admin/admin-layout.js repo/src/assets/js/admin/admin-layout-page-refinement-v1.js repo/src/assets/js/admin/admin-navigation.js repo/src/assets/js/admin/admin-navigation-page-refinement-v1.js repo/src/assets/js/admin/admin-render.js repo/src/assets/js/admin/admin-preview.js repo/src/assets/js/admin/admin-recovery-v510.js; do node --check "$js" >/dev/null; done
for t in repo/tests/mature-product-v5-contract.php repo/tests/workbench-page-refresh-parity-contract.php repo/tests/brand-page-live-preview-contract.php repo/tests/layout-page-workflow-contract.php repo/tests/navigation-page-refinement-contract.php repo/tests/render-page-refinement-contract.php repo/tests/update-center-human-language-contract.php repo/tests/workbench-primary-action-contract.php repo/tests/final-admin-human-closure-contract.php repo/tests/deep-admin-human-language-contract.php repo/tests/layout-workflow-v4-contract.php repo/tests/navigation-workflow-v4-contract.php repo/tests/render-workflow-v4-contract.php repo/tests/render-settings-human-language-contract.php repo/tests/seo-workflow-v4-contract.php repo/tests/preview-workflow-v4-contract.php repo/tests/preview-human-language-followup-contract.php repo/tests/recovery-workflow-v4-contract.php repo/tests/recovery-human-language-closure-contract.php repo/tests/update-refresh-policy-contract.php repo/tests/visible-console-v2-contract.php; do php "$t"; done

git -C repo diff --check "$BASE_SHA" "$SHA"
mkdir -p "$RUNNER_TEMP/a" "$RUNNER_TEMP/b"
python3 - <<'PY' > "$RUNNER_TEMP/metrics.env"
from pathlib import Path
import hashlib, os, zipfile, stat
src=Path('repo/src')
rows=[(p.relative_to(src).as_posix(),p.read_bytes()) for p in sorted(src.rglob('*'),key=lambda x:x.relative_to(src).as_posix()) if p.is_file()]
assert len(rows)>=440
assert all(not r.startswith('/') and '..' not in r.split('/') for r,_ in rows)
def build(path):
    dirs={'vf-tools-theme/'}
    for rel,_ in rows:
        cur='vf-tools-theme'
        for part in rel.split('/')[:-1]: cur+='/'+part; dirs.add(cur+'/')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for d in sorted(dirs):
            zi=zipfile.ZipInfo(d); zi.date_time=(1980,1,1,0,0,0); zi.external_attr=(0o40755<<16)|0x10; z.writestr(zi,b'')
        for rel,b in rows:
            zi=zipfile.ZipInfo('vf-tools-theme/'+rel); zi.date_time=(1980,1,1,0,0,0); zi.compress_type=zipfile.ZIP_DEFLATED; zi.external_attr=0o100644<<16; z.writestr(zi,b)
    data=Path(path).read_bytes(); return len(rows),len(data),hashlib.sha256(data).hexdigest()
a=build(Path(os.environ['RUNNER_TEMP'])/'a'/os.environ['ASSET'])
b=build(Path(os.environ['RUNNER_TEMP'])/'b'/os.environ['ASSET'])
assert a==b
print(f'FILES={a[0]}'); print(f'BYTES={a[1]}'); print(f'SHA256={a[2]}')
PY
cat "$RUNNER_TEMP/metrics.env" >> "$GITHUB_ENV"; set -a; source "$RUNNER_TEMP/metrics.env"; set +a
cmp "$RUNNER_TEMP/a/$ASSET" "$RUNNER_TEMP/b/$ASSET"
python3 - <<'PY'
import os,zipfile
p=os.environ['RUNNER_TEMP']+'/a/'+os.environ['ASSET']
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    names=z.namelist()
    assert names and all(n.startswith('vf-tools-theme/') for n in names)
    assert all(not n.startswith('/') and '..' not in n.split('/') for n in names)
    assert 'vf-tools-theme/assets/js/admin/admin-seo-page-refinement-v1.js' not in names
    style=z.read('vf-tools-theme/style.css')
    assert b'Version: 1.35.23' in style and b'V1.35.23_S01_MATURE_ADMIN_PAGE1_5_PREVIEW' in style
    assert b'admin-mature-product-v5.css' not in style
    assert '工具页默认怎么显示'.encode() in z.read('vf-tools-theme/inc/admin/views/render.php')
    assert b'admin-page-render-refinement-v1.css' in z.read('vf-tools-theme/inc/admin/admin-s01-uiux-polish.php')
PY

created_tag=0; created_release=0
cleanup(){ rc=$?; if [ "$rc" -ne 0 ]; then if [ "$created_release" -eq 1 ]; then gh release delete "$TAG" --repo "$repo" --cleanup-tag --yes >/dev/null 2>&1||true; fi; if [ "$created_tag" -eq 1 ]; then gh api --method DELETE "repos/$repo/git/refs/tags/$TAG" >/dev/null 2>&1||true; fi; fi; exit "$rc"; }; trap cleanup EXIT
gh api --method POST "repos/$repo/git/refs" -f ref="refs/tags/$TAG" -f sha="$SHA" >/dev/null; created_tag=1
test "$(gh api "repos/$repo/git/ref/tags/$TAG" --jq '.object.sha')" = "$SHA"
printf 'S01-C01 Mature Admin Page 1-5 Preview Release.\nExact main source: %s\nBump/Regression Gate: 34345427488 PASS\nScope: Workbench, Brand, Layout, Navigation/Footer and Tool Page Render refinements.\nPage 6 Technical SEO refinement is explicitly excluded from this release.\nPublic Authority: UPGRADE/TESTING/SECURITY/GIT/UA_UI PASS at release scope.\nProduction: NOT_RUN\nStatic: NOT_RUN\nOnline install: NOT_RUN\n' "$SHA" > "$RUNNER_TEMP/notes"
gh release create "$TAG" "$RUNNER_TEMP/a/$ASSET" --repo "$repo" --title 'VF Tools Theme V1.35.23' --notes-file "$RUNNER_TEMP/notes" --draft --verify-tag; created_release=1
mkdir "$RUNNER_TEMP/r"; gh release download "$TAG" --repo "$repo" --pattern "$ASSET" --dir "$RUNNER_TEMP/r"
test "$(stat -c %s "$RUNNER_TEMP/r/$ASSET")" = "$BYTES"
test "$(sha256sum "$RUNNER_TEMP/r/$ASSET"|awk '{print $1}')" = "$SHA256"
gh release edit "$TAG" --repo "$repo" --draft=false
gh api "repos/$repo/releases/tags/$TAG" > "$RUNNER_TEMP/final.json"
test "$(jq -r '.draft' "$RUNNER_TEMP/final.json")" = false
test "$(jq -r '.prerelease' "$RUNNER_TEMP/final.json")" = false
test "$(jq -r --arg a "$ASSET" '.assets[]|select(.name==$a)|.size' "$RUNNER_TEMP/final.json")" = "$BYTES"
test "$(jq -r --arg a "$ASSET" '.assets[]|select(.name==$a)|.digest' "$RUNNER_TEMP/final.json")" = "sha256:$SHA256"
trap - EXIT
echo "TAG_TARGET=$(gh api "repos/$repo/git/ref/tags/$TAG" --jq '.object.sha')"
echo "RELEASE_ID=$(jq -r '.id' "$RUNNER_TEMP/final.json")"
echo "ASSET_ID=$(jq -r --arg a "$ASSET" '.assets[]|select(.name==$a)|.id' "$RUNNER_TEMP/final.json")"
echo "REMOTE_BYTES=$BYTES"
echo "ASSET_SHA256=$SHA256"
echo "SOURCE_ZIP_FILES=$FILES"
echo 'TESTED_ARTIFACT_EQUALS_DELIVERED_ARTIFACT=PASS'
echo 'C01_13523_FORMAL_RELEASE=PASS'