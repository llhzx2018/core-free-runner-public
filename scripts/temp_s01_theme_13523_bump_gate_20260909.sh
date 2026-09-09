#!/usr/bin/env bash
set -Eeuo pipefail
: "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${MAIN_SHA:?}" "${BASE_SHA:?}"
echo 'BUMP_GATE=WRITE_RELEASE_BRANCH_ONLY MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
rm -rf /tmp/vf-theme-13523-bump
GIT_TERMINAL_PROMPT=0 git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" /tmp/vf-theme-13523-bump
cd /tmp/vf-theme-13523-bump
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
test "$(git ls-remote origin refs/heads/main | awk '{print $1}')" = "$MAIN_SHA"
git merge-base --is-ancestor "$MAIN_SHA" "$BASE_SHA"
test "$(tr -d '\r\n' < VERSION)" = '1.35.22'
grep -F 'Version: 1.35.22' src/style.css >/dev/null
grep -F 'V1.35.22_S01_ADMIN_PAGE_BY_PAGE_UX_CLOSURE' src/style.css >/dev/null
test ! -e src/assets/js/admin/admin-seo-page-refinement-v1.js

# Exact Page 1-5 source fence. This excludes the unfinished Page 6 sidecar and all release/version writes.
git diff --name-only "$MAIN_SHA" "$BASE_SHA" | sort >/tmp/page15_actual
cat >/tmp/page15_expected <<'EOF'
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
tests/brand-page-live-preview-contract.php
tests/layout-page-workflow-contract.php
tests/mature-product-v5-contract.php
tests/navigation-page-refinement-contract.php
tests/render-page-refinement-contract.php
tests/render-workflow-v4-contract.php
tests/workbench-page-refresh-parity-contract.php
EOF
sort -o /tmp/page15_expected /tmp/page15_expected
diff -u /tmp/page15_expected /tmp/page15_actual

# Security/update boundary: this candidate does not mutate updater/auth/recovery/data/migration code.
if git diff --name-only "$MAIN_SHA" "$BASE_SHA" | grep -E '(^|/)(update|migration|schema|recovery|secrets?|credentials?)(/|\.|$)'; then
  echo FAIL_RELEASE_SURFACE_BOUNDARY; exit 1
fi
grep -F "current_user_can('vf_manage_theme_profile')" src/inc/admin/admin-render-actions.php >/dev/null
grep -F "check_ajax_referer('theme.render.save', 'nonce')" src/inc/admin/admin-render-actions.php >/dev/null
grep -F "add_action('wp_ajax_vf_theme_render_save', 'vf_theme_render_save_ajax')" src/inc/admin/admin-render-actions.php >/dev/null

# Version identity inventory may live only in machine tests plus the two canonical version surfaces.
mapfile -t identity < <(git grep -l -E '1\.35\.22|V1\.35\.22_S01_ADMIN_PAGE_BY_PAGE_UX_CLOSURE' -- ':!docs/**' ':!*.md' | sort)
((${#identity[@]} >= 2))
printf '%s\n' "${identity[@]}" >/tmp/identity
for p in "${identity[@]}"; do
  case "$p" in
    VERSION|src/style.css|tests/*.php) ;;
    *) echo "FAIL_UNEXPECTED_VERSION_IDENTITY=$p"; exit 1;;
  esac
done
grep -Fx VERSION /tmp/identity >/dev/null
grep -Fx src/style.css /tmp/identity >/dev/null
python3 - "${identity[@]}" <<'PY'
from pathlib import Path
import sys
for raw in sys.argv[1:]:
    p=Path(raw)
    s=p.read_text()
    s=s.replace('V1.35.22_S01_ADMIN_PAGE_BY_PAGE_UX_CLOSURE','V1.35.23_S01_MATURE_ADMIN_PAGE1_5_PREVIEW')
    s=s.replace('1.35.22','1.35.23')
    p.write_text(s)
PY
test "$(tr -d '\r\n' < VERSION)" = '1.35.23'
grep -F 'Version: 1.35.23' src/style.css >/dev/null
grep -F 'V1.35.23_S01_MATURE_ADMIN_PAGE1_5_PREVIEW' src/style.css >/dev/null
if git grep -n -E '1\.35\.22|V1\.35\.22_S01_ADMIN_PAGE_BY_PAGE_UX_CLOSURE' -- ':!docs/**' ':!*.md'; then echo FAIL_STALE_VERSION_IDENTITY; exit 1; fi

# TESTING / SECURITY / UA_UI regression gates.
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
for js in \
 src/assets/js/admin/admin-dashboard.js \
 src/assets/js/admin/admin-brand.js \
 src/assets/js/admin/admin-brand-page-refinement-v1.js \
 src/assets/js/admin/admin-layout.js \
 src/assets/js/admin/admin-layout-page-refinement-v1.js \
 src/assets/js/admin/admin-navigation.js \
 src/assets/js/admin/admin-navigation-page-refinement-v1.js \
 src/assets/js/admin/admin-render.js \
 src/assets/js/admin/admin-preview.js \
 src/assets/js/admin/admin-recovery-v510.js; do node --check "$js" >/dev/null; done
for t in \
 tests/mature-product-v5-contract.php \
 tests/workbench-page-refresh-parity-contract.php \
 tests/brand-page-live-preview-contract.php \
 tests/layout-page-workflow-contract.php \
 tests/navigation-page-refinement-contract.php \
 tests/render-page-refinement-contract.php \
 tests/update-center-human-language-contract.php \
 tests/workbench-primary-action-contract.php \
 tests/final-admin-human-closure-contract.php \
 tests/deep-admin-human-language-contract.php \
 tests/layout-workflow-v4-contract.php \
 tests/navigation-workflow-v4-contract.php \
 tests/render-workflow-v4-contract.php \
 tests/render-settings-human-language-contract.php \
 tests/seo-workflow-v4-contract.php \
 tests/preview-workflow-v4-contract.php \
 tests/preview-human-language-followup-contract.php \
 tests/recovery-workflow-v4-contract.php \
 tests/recovery-human-language-closure-contract.php \
 tests/update-refresh-policy-contract.php \
 tests/visible-console-v2-contract.php; do php "$t"; done
git diff --check "$BASE_SHA" --

# The bump may change only the exact version identity files discovered above.
git diff --name-only "$BASE_SHA" -- | sort >/tmp/bump_changed
sort -o /tmp/identity /tmp/identity
diff -u /tmp/identity /tmp/bump_changed

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add "${identity[@]}"
git commit -m 'release(S01-C01): prepare mature admin Page 1-5 preview 1.35.23'
git push -q origin "$BRANCH"
echo "THEME_13523_BUMP_HEAD=$(git rev-parse HEAD)"
echo "VERSION_IDENTITY_FILES=${#identity[@]}"
echo 'PUBLIC_AUTHORITY_UPGRADE=PASS_BOUNDARY'
echo 'PUBLIC_AUTHORITY_TESTING=PASS_MACHINE_REGRESSION'
echo 'PUBLIC_AUTHORITY_SECURITY=PASS_NO_SECURITY_SURFACE_DRIFT'
echo 'PUBLIC_AUTHORITY_GIT=PASS_EXACT_SOURCE_NON_FORCE'
echo 'PUBLIC_AUTHORITY_UA_UI=PASS_CONTRACT_REGRESSION'
echo 'PASS_S01_C01_13523_BUMP_GATE'