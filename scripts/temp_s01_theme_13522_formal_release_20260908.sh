#!/usr/bin/env bash
set -Eeuo pipefail
: "${READ_TOKEN:?}" "${WRITE_TOKEN:?}" "${SHA:?}" "${BASE_SHA:?}" "${TAG:?}" "${ASSET:?}"
echo 'PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO MIGRATION_USED=NO OPS_WRITE_USED=NO M3U8_WRITE_USED=NO'
export GH_TOKEN="$WRITE_TOKEN"
repo='llhzx2018/vf-tools-theme'
test "$(gh api repos/$repo/branches/main --jq '.commit.sha')" = "$SHA"
if gh api repos/$repo/git/ref/tags/$TAG >/dev/null 2>&1; then echo TAG_ALREADY_EXISTS; exit 1; fi
if gh api repos/$repo/releases/tags/$TAG >/dev/null 2>&1; then echo RELEASE_ALREADY_EXISTS; exit 1; fi
rm -rf repo
git clone -q "https://x-access-token:${READ_TOKEN}@github.com/${repo}.git" repo
git -C repo checkout -q "$SHA"
test "$(git -C repo rev-parse HEAD)" = "$SHA"
test "$(tr -d '\r\n' < repo/VERSION)" = '1.35.22'
grep -F 'Version: 1.35.22' repo/src/style.css >/dev/null
grep -F 'V1.35.22_S01_ADMIN_PAGE_BY_PAGE_UX_CLOSURE' repo/src/style.css >/dev/null
# Page-by-page UX identity checks.
grep -F 'vf-update-credential-setup' repo/src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F '先配置更新凭证，再检查或安装此组件的更新。' repo/src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F 'vf-workbench-v4' repo/src/inc/admin/views/tabs/overview.php >/dev/null
grep -F 'class="button button-primary vf-workbench-v5141__action"' repo/src/inc/admin/views/tabs/overview.php >/dev/null
grep -F 'data-vf-brand-save' repo/src/inc/admin/views/brand.php >/dev/null
grep -F 'data-vf-layout-save-dock' repo/src/inc/admin/views/layout.php >/dev/null
grep -F 'data-vf-navigation-save-dock' repo/src/inc/admin/views/navigation.php >/dev/null
grep -F 'vf-render-side-actions' repo/src/inc/admin/views/render.php >/dev/null
grep -F 'data-vf-seo-save-dock' repo/src/inc/admin/views/seo.php >/dev/null
grep -F 'vf-preview-v510__run-action' repo/src/inc/admin/views/preview.php >/dev/null
grep -F 'data-vf-recovery-action-dock' repo/src/inc/admin/views/recovery-v510.php >/dev/null
grep -F "restoreConfirm?.value.trim() === 'RESTORE'" repo/src/assets/js/admin/admin-recovery-v510.js >/dev/null
find repo/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
for js in repo/src/assets/js/admin/admin-brand.js repo/src/assets/js/admin/admin-layout.js repo/src/assets/js/admin/admin-navigation.js repo/src/assets/js/admin/admin-preview.js repo/src/assets/js/admin/admin-recovery-v510.js; do node --check "$js" >/dev/null; done
for t in \
 repo/tests/update-center-human-language-contract.php \
 repo/tests/workbench-primary-action-contract.php \
 repo/tests/final-admin-human-closure-contract.php \
 repo/tests/deep-admin-human-language-contract.php \
 repo/tests/layout-workflow-v4-contract.php \
 repo/tests/navigation-workflow-v4-contract.php \
 repo/tests/render-workflow-v4-contract.php \
 repo/tests/render-settings-human-language-contract.php \
 repo/tests/seo-workflow-v4-contract.php \
 repo/tests/preview-workflow-v4-contract.php \
 repo/tests/preview-human-language-followup-contract.php \
 repo/tests/recovery-workflow-v4-contract.php \
 repo/tests/recovery-human-language-closure-contract.php \
 repo/tests/update-refresh-policy-contract.php \
 repo/tests/visible-console-v2-contract.php; do php "$t"; done
# Exact main diff fence from 1.35.21 main to 1.35.22 main.
git -C repo diff --name-only "$BASE_SHA" "$SHA" | sort >/tmp/actual
cat >/tmp/expected <<'EOF'
VERSION
src/assets/css/admin/admin-update-center.css
src/assets/css/admin/pages/brand/admin-page-brand.css
src/assets/css/admin/pages/maintenance/recovery/admin-page-recovery-v510.css
src/assets/css/admin/pages/navigation/admin-page-navigation.css
src/assets/css/admin/pages/page-structure/admin-page-layout.css
src/assets/css/admin/pages/preview/admin-page-preview.css
src/assets/css/admin/pages/render/admin-page-render.css
src/assets/css/admin/pages/seo/admin-page-seo.css
src/assets/css/admin/pages/workbench/admin-page-workbench.css
src/inc/admin/admin-shell.php
src/inc/admin/views/brand.php
src/inc/admin/views/layout.php
src/inc/admin/views/navigation.php
src/inc/admin/views/preview.php
src/inc/admin/views/recovery-v510.php
src/inc/admin/views/render.php
src/inc/admin/views/seo.php
src/inc/admin/views/tabs/overview.php
src/inc/update/class-vf-wp-update-admin-v1.php
src/style.css
tests/final-admin-human-closure-contract.php
tests/layout-workflow-v4-contract.php
tests/navigation-workflow-v4-contract.php
tests/preview-workflow-v4-contract.php
tests/recovery-workflow-v4-contract.php
tests/render-workflow-v4-contract.php
tests/seo-workflow-v4-contract.php
tests/update-center-human-language-contract.php
tests/update-refresh-policy-contract.php
tests/visible-console-v2-contract.php
tests/workbench-primary-action-contract.php
EOF
sort -o /tmp/expected /tmp/expected
diff -u /tmp/expected /tmp/actual
mkdir -p "$RUNNER_TEMP/a" "$RUNNER_TEMP/b"
python3 - <<'PY' > "$RUNNER_TEMP/metrics.env"
from pathlib import Path
import hashlib,os,zipfile
src=Path('repo/src')
rows=[(p.relative_to(src).as_posix(),p.read_bytes()) for p in sorted(src.rglob('*'),key=lambda x:x.relative_to(src).as_posix()) if p.is_file()]
assert len(rows)>=440
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
a=build(Path(os.environ['RUNNER_TEMP'])/'a'/os.environ['ASSET']); b=build(Path(os.environ['RUNNER_TEMP'])/'b'/os.environ['ASSET']); assert a==b
print(f'FILES={a[0]}'); print(f'BYTES={a[1]}'); print(f'SHA256={a[2]}')
PY
cat "$RUNNER_TEMP/metrics.env" >> "$GITHUB_ENV"; set -a; source "$RUNNER_TEMP/metrics.env"; set +a
cmp "$RUNNER_TEMP/a/$ASSET" "$RUNNER_TEMP/b/$ASSET"
python3 - <<'PY'
import os,zipfile
p=os.environ['RUNNER_TEMP']+'/a/'+os.environ['ASSET']
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    style=z.read('vf-tools-theme/style.css')
    assert b'Version: 1.35.22' in style and b'V1.35.22_S01_ADMIN_PAGE_BY_PAGE_UX_CLOSURE' in style
    update=z.read('vf-tools-theme/inc/update/class-vf-wp-update-admin-v1.php')
    assert '先配置更新凭证，再检查或安装此组件的更新。'.encode() in update
    layout=z.read('vf-tools-theme/inc/admin/views/layout.php'); assert b'data-vf-layout-save-dock' in layout
    nav=z.read('vf-tools-theme/inc/admin/views/navigation.php'); assert b'data-vf-navigation-save-dock' in nav
    preview=z.read('vf-tools-theme/inc/admin/views/preview.php'); assert b'vf-preview-v510__run-action' in preview
    recovery=z.read('vf-tools-theme/inc/admin/views/recovery-v510.php'); assert b'data-vf-recovery-action-dock' in recovery
PY
created_tag=0; created_release=0
cleanup(){ rc=$?; if [ "$rc" -ne 0 ]; then if [ "$created_release" -eq 1 ]; then gh release delete "$TAG" --repo "$repo" --cleanup-tag --yes >/dev/null 2>&1||true; fi; if [ "$created_tag" -eq 1 ]; then gh api --method DELETE "repos/$repo/git/refs/tags/$TAG" >/dev/null 2>&1||true; fi; fi; exit "$rc"; }; trap cleanup EXIT
gh api --method POST "repos/$repo/git/refs" -f ref="refs/tags/$TAG" -f sha="$SHA" >/dev/null; created_tag=1
test "$(gh api "repos/$repo/git/ref/tags/$TAG" --jq '.object.sha')" = "$SHA"
printf 'S01-C01 Admin Page-by-Page UX Closure. Exact main source: %s\nWhole-batch Final Audit: 34208200303 PASS\n1.35.22 Bump Gate: 34208626261 PASS\nNine Theme admin pages now keep the unique primary action in the active task context; recovery confirmation guards remain intact.\nProduction: NOT_RUN\nStatic: NOT_RUN\nOnline: NOT_RUN\n' "$SHA" > "$RUNNER_TEMP/notes"
gh release create "$TAG" "$RUNNER_TEMP/a/$ASSET" --repo "$repo" --title 'VF Tools Theme V1.35.22' --notes-file "$RUNNER_TEMP/notes" --draft --verify-tag; created_release=1
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
echo 'C01_13522_FORMAL_RELEASE=PASS'