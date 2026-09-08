#!/usr/bin/env bash
set -euo pipefail
: "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}"
echo 'BUMP_GATE=WRITE_BRANCH_ONLY MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
rm -rf /tmp/vf-theme-13522-bump
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" /tmp/vf-theme-13522-bump
cd /tmp/vf-theme-13522-bump
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
mapfile -t identity < <(git grep -l -E '1\.35\.21|V1\.35\.21_S01_UPDATE_CREDENTIAL_FIRST_CLOSURE' -- ':!docs/**' ':!*.md' | sort)
expected_identity=(VERSION src/style.css tests/update-refresh-policy-contract.php tests/visible-console-v2-contract.php tests/workbench-primary-action-contract.php)
printf '%s\n' "${identity[@]}" >/tmp/identity; printf '%s\n' "${expected_identity[@]}"|sort >/tmp/expected_identity; diff -u /tmp/expected_identity /tmp/identity
python3 - <<'PY'
from pathlib import Path
paths=['VERSION','src/style.css','tests/update-refresh-policy-contract.php','tests/visible-console-v2-contract.php','tests/workbench-primary-action-contract.php']
for p in paths:
    f=Path(p)
    s=f.read_text()
    s=s.replace('V1.35.21_S01_UPDATE_CREDENTIAL_FIRST_CLOSURE','V1.35.22_S01_ADMIN_PAGE_BY_PAGE_UX_CLOSURE').replace('1.35.21','1.35.22')
    f.write_text(s)
PY
test "$(tr -d '\r\n' < VERSION)" = '1.35.22'
grep -q 'Version: 1.35.22' src/style.css
grep -q 'V1.35.22_S01_ADMIN_PAGE_BY_PAGE_UX_CLOSURE' src/style.css
if git grep -n -E '1\.35\.21|V1\.35\.21_S01_UPDATE_CREDENTIAL_FIRST_CLOSURE' -- ':!docs/**' ':!*.md'; then echo 'FAIL_STALE_VERSION_IDENTITY'; exit 1; fi
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
for js in src/assets/js/admin/admin-brand.js src/assets/js/admin/admin-layout.js src/assets/js/admin/admin-navigation.js src/assets/js/admin/admin-preview.js src/assets/js/admin/admin-recovery-v510.js; do node --check "$js" >/dev/null; done
for t in \
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
mapfile -t changed < <(git diff --name-only "$BASE_SHA" -- | sort)
expected=(VERSION src/style.css tests/update-refresh-policy-contract.php tests/visible-console-v2-contract.php tests/workbench-primary-action-contract.php)
printf '%s\n' "${changed[@]}" >/tmp/changed; printf '%s\n' "${expected[@]}"|sort >/tmp/expected; diff -u /tmp/expected /tmp/changed
git config user.name VictorForge; git config user.email llhzx2018@gmail.com; git add "${expected[@]}"; git commit -m 'release(S01-C01): prepare admin page UX closure 1.35.22'; git push -q origin "$BRANCH"
echo "THEME_13522_BUMP_HEAD=$(git rev-parse HEAD)"; echo 'PASS_S01_C01_13522_BUMP_GATE'